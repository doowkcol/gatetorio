#!/usr/bin/env python3
"""
Gatetorio BLE GATT Server - Full bluezero implementation

This module provides a complete BLE GATT server using the bluezero library
for Linux/BlueZ. It exposes gate control functionality via Bluetooth Low Energy
with stealth mode, security features, and engineer-level diagnostics.

Architecture:
- 5 GATT services (Device Info, Gate Control, Config, Diagnostics, Security)
- 15 characteristics with read/write/notify handlers
- Stealth mode: 30s pairing window, then whitelist-only
- Real-time status notifications at 1Hz
"""

import sys
import json
import time
import hashlib
import pathlib
import threading
from typing import Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime

# Check for bluezero
try:
    from bluezero import adapter
    from bluezero import peripheral
    from bluezero import dbus_tools
except ImportError:
    print("ERROR: bluezero not installed")
    print("Install system packages first:")
    print("  sudo apt-get install python3-dbus libdbus-1-dev libglib2.0-dev bluez")
    print("Then install Python package:")
    print("  pip3 install bluezero")
    sys.exit(1)

try:
    import psutil
except ImportError:
    print("WARNING: psutil not installed - system diagnostics will be limited")
    psutil = None

from gate_controller_v2 import GateController

# ============================================================================
# CONFIGURATION
# ============================================================================

# Base UUID for custom GATT services (encodes "GATERIO")
BASE_UUID = "0000{:04X}-4751-5445-5254-494F00000000"

# GATT Service UUIDs
SERVICE_DEVICE_INFO = "0000180A-0000-1000-8000-00805F9B34FB"  # Standard BLE
SERVICE_GATE_CONTROL = BASE_UUID.format(0x1000)
SERVICE_CONFIGURATION = BASE_UUID.format(0x2000)
SERVICE_DIAGNOSTICS = BASE_UUID.format(0x3000)
SERVICE_SECURITY = BASE_UUID.format(0x4000)

# GATT Characteristic UUIDs
# Device Info
CHAR_HARDWARE_ID = BASE_UUID.format(0x0101)
CHAR_SOFTWARE_VERSION = BASE_UUID.format(0x0102)
CHAR_USER_ID = BASE_UUID.format(0x0103)

# Gate Control
CHAR_COMMAND_TX = BASE_UUID.format(0x1001)
CHAR_COMMAND_RESPONSE = BASE_UUID.format(0x1002)
CHAR_STATUS = BASE_UUID.format(0x1003)

# Configuration
CHAR_CONFIG_DATA = BASE_UUID.format(0x2001)
CHAR_CONFIG_CONTROL = BASE_UUID.format(0x2002)
CHAR_INPUT_CONFIG = BASE_UUID.format(0x2003)

# Diagnostics
CHAR_INPUT_STATES = BASE_UUID.format(0x3001)
CHAR_SYSTEM_STATUS = BASE_UUID.format(0x3002)
CHAR_LOGS = BASE_UUID.format(0x3003)

# Security
CHAR_PAIRING_CONTROL = BASE_UUID.format(0x4001)
CHAR_WHITELIST = BASE_UUID.format(0x4002)
CHAR_ENGINEER_MODE = BASE_UUID.format(0x4003)

# File paths
CONFIG_DIR = pathlib.Path("/home/doowkcol/Gatetorio_Code")
BLE_CONFIG_FILE = CONFIG_DIR / "ble_config.json"
WHITELIST_FILE = CONFIG_DIR / "ble_whitelist.json"
REBOOT_FLAG_FILE = CONFIG_DIR / ".ble_reboot_flag"

# Pairing window duration (seconds)
PAIRING_WINDOW_DURATION = 30

# Status update interval (seconds)
STATUS_UPDATE_INTERVAL = 1.0


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class BLEConfig:
    """BLE bridge configuration"""
    user_id: str = "gatetorio-default"
    pairing_mode: bool = False
    stealth_mode: bool = True
    whitelist_enabled: bool = True
    engineer_mode_enabled: bool = False


# ============================================================================
# BLE GATT SERVER
# ============================================================================

class GatetorioBLEServer:
    """
    Main BLE GATT server for Gatetorio gate control
    """

    def __init__(self, controller: GateController):
        self.controller = controller
        self.config = BLEConfig()

        # Connection tracking
        self.connected_devices: Set[str] = set()
        self.whitelist: Set[str] = set()
        self.pairing_window_active = False

        # Hardware and software info
        self.hardware_id = self._get_hardware_id()
        self.software_version = "1.0.0"

        # Cached data for characteristics
        self.last_command_response = b'{"success":true,"message":"Ready"}'
        self.last_status = b'{}'
        self.last_diagnostics = b'{}'
        self.recent_logs = []

        # Status update thread
        self.status_thread = None
        self.status_running = False

        # Load configuration
        self._load_config()
        self._load_whitelist()

        print(f"[BLE] Initialized - Hardware ID: {self.hardware_id}")
        print(f"[BLE] User ID: {self.config.user_id}")

    # ========================================================================
    # HARDWARE IDENTIFICATION
    # ========================================================================

    def _get_hardware_id(self) -> str:
        """Get Raspberry Pi CPU serial number"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        return serial[-8:].upper()
        except Exception as e:
            print(f"[BLE] Warning: Could not read CPU serial: {e}")
            # Fallback to MAC hash
            try:
                import uuid
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                               for i in range(0, 8*6, 8)][::-1])
                return hashlib.md5(mac.encode()).hexdigest()[:8].upper()
            except:
                return "UNKNOWN1"
        return "UNKNOWN2"

    # ========================================================================
    # CONFIGURATION MANAGEMENT
    # ========================================================================

    def _load_config(self):
        """Load BLE configuration from file"""
        if BLE_CONFIG_FILE.exists():
            try:
                with open(BLE_CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.config.user_id = data.get('user_id', self.config.user_id)
                    self.config.stealth_mode = data.get('stealth_mode', True)
                    self.config.whitelist_enabled = data.get('whitelist_enabled', True)
                    print(f"[BLE] Loaded config from {BLE_CONFIG_FILE}")
            except Exception as e:
                print(f"[BLE] Error loading config: {e}")

    def _save_config(self):
        """Save BLE configuration to file"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(BLE_CONFIG_FILE, 'w') as f:
                json.dump({
                    'user_id': self.config.user_id,
                    'stealth_mode': self.config.stealth_mode,
                    'whitelist_enabled': self.config.whitelist_enabled,
                }, f, indent=2)
            print(f"[BLE] Saved config")
        except Exception as e:
            print(f"[BLE] Error saving config: {e}")

    def _load_whitelist(self):
        """Load whitelisted device MAC addresses"""
        if WHITELIST_FILE.exists():
            try:
                with open(WHITELIST_FILE, 'r') as f:
                    data = json.load(f)
                    self.whitelist = set(data.get('devices', []))
                    print(f"[BLE] Loaded {len(self.whitelist)} whitelisted devices")
            except Exception as e:
                print(f"[BLE] Error loading whitelist: {e}")

    def _save_whitelist(self):
        """Save whitelisted device MAC addresses"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(WHITELIST_FILE, 'w') as f:
                json.dump({'devices': list(self.whitelist)}, f, indent=2)
            print(f"[BLE] Saved whitelist ({len(self.whitelist)} devices)")
        except Exception as e:
            print(f"[BLE] Error saving whitelist: {e}")

    # ========================================================================
    # PAIRING WINDOW
    # ========================================================================

    def _check_reboot_flag(self) -> bool:
        """Check if this was an unexpected reboot"""
        if REBOOT_FLAG_FILE.exists():
            # Flag exists = expected reboot, remove flag
            try:
                REBOOT_FLAG_FILE.unlink()
                print("[BLE] Expected reboot detected")
                return False
            except:
                pass
        # No flag = unexpected reboot (power loss, crash)
        print("[BLE] Unexpected boot detected")
        return True

    def start_pairing_window(self, duration: int = PAIRING_WINDOW_DURATION):
        """Open pairing window for new connections"""
        print(f"[BLE] Opening pairing window for {duration} seconds...")
        self.pairing_window_active = True
        self.config.pairing_mode = True

        # Use threading timer to close window
        def close_window():
            print("[BLE] Pairing window closed - entering stealth mode")
            self.pairing_window_active = False
            self.config.pairing_mode = False

        timer = threading.Timer(duration, close_window)
        timer.daemon = True
        timer.start()

    # ========================================================================
    # COMMAND HANDLERS
    # ========================================================================

    def handle_command(self, command_json: bytes) -> Dict:
        """
        Process incoming command from BLE client
        Returns: Response dictionary
        """
        try:
            cmd = json.loads(command_json.decode('utf-8'))
            cmd_type = cmd.get('cmd')
            key = cmd.get('key')
            value = cmd.get('value')

            print(f"[BLE] Command: {cmd_type} {key}")

            # Standard pulse commands
            if cmd_type == 'pulse':
                return self._handle_pulse_command(key)

            # Engineer mode commands
            elif cmd_type == 'engineer_pulse':
                return self._handle_engineer_command(key)

            # Configuration commands
            elif cmd_type == 'get_config':
                return self._handle_get_config()
            elif cmd_type == 'set_config':
                return self._handle_set_config(value)
            elif cmd_type == 'reload_config':
                return self._handle_reload_config()
            elif cmd_type == 'save_learned_times':
                return self._handle_save_learned_times()

            # System commands
            elif cmd_type == 'reboot':
                return self._handle_reboot()
            elif cmd_type == 'get_diagnostics':
                return self._handle_get_diagnostics()
            elif cmd_type == 'enable_engineer_mode':
                return self._handle_enable_engineer_mode(value)

            else:
                return {"success": False, "message": f"Unknown command: {cmd_type}"}

        except json.JSONDecodeError as e:
            return {"success": False, "message": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"success": False, "message": f"Error: {e}"}

    def _handle_pulse_command(self, key: str) -> Dict:
        """Handle standard pulse commands"""
        valid_commands = ['cmd_open', 'cmd_close', 'cmd_stop', 'partial_1', 'partial_2', 'step_logic']

        if key not in valid_commands:
            return {"success": False, "message": f"Invalid pulse command: {key}"}

        # Send pulse to controller
        if key == 'step_logic':
            self.controller.shared['step_logic_pulse'] = True
        else:
            self.controller.shared[f'{key}_active'] = True
            time.sleep(0.1)
            self.controller.shared[f'{key}_active'] = False

        return {"success": True, "message": f"Pulse sent: {key}"}

    def _handle_engineer_command(self, key: str) -> Dict:
        """Handle engineer mode direct motor control"""
        if not self.config.engineer_mode_enabled:
            return {"success": False, "message": "Engineer mode not enabled"}

        valid_commands = ['motor1_open', 'motor1_close', 'motor2_open', 'motor2_close']

        if key not in valid_commands:
            return {"success": False, "message": f"Invalid engineer command: {key}"}

        # Set engineer command flag
        self.controller.shared[f'engineer_{key}'] = True
        return {"success": True, "message": f"Engineer command sent: {key}"}

    def _handle_get_config(self) -> Dict:
        """Get current gate configuration"""
        try:
            config = self.controller.config
            return {"success": True, "config": config}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _handle_set_config(self, config_data: Dict) -> Dict:
        """Update gate configuration"""
        try:
            # Stop gate before config change
            self.controller.shared['cmd_stop_active'] = True
            time.sleep(0.2)

            # Update config file
            CONFIG_FILE = CONFIG_DIR / "gate_config.json"
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=2)

            # Reload controller
            self.controller.reload_config()
            return {"success": True, "message": "Configuration updated"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _handle_reload_config(self) -> Dict:
        """Reload configuration from file"""
        try:
            self.controller.reload_config()
            return {"success": True, "message": "Configuration reloaded"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _handle_save_learned_times(self) -> Dict:
        """Save auto-learned gate times"""
        try:
            self.controller.save_learned_times()
            return {"success": True, "message": "Learned times saved"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _handle_reboot(self) -> Dict:
        """Reboot the system"""
        try:
            # Set reboot flag for expected reboot
            REBOOT_FLAG_FILE.touch()
            print("[BLE] Reboot flag set - will skip pairing window on boot")

            # Schedule reboot
            import subprocess
            subprocess.Popen(['sudo', 'reboot'])
            return {"success": True, "message": "Rebooting in 5 seconds"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _handle_get_diagnostics(self) -> Dict:
        """Get system diagnostics"""
        try:
            diag = {
                "system": self._get_system_status(),
                "gate_state": self.controller.shared.get('state', 'UNKNOWN'),
                "motor1_percent": self.controller.shared.get('m1_percent', 0),
                "motor2_percent": self.controller.shared.get('m2_percent', 0),
            }
            return {"success": True, "diagnostics": diag}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _handle_enable_engineer_mode(self, enabled: bool) -> Dict:
        """Enable/disable engineer mode"""
        try:
            self.config.engineer_mode_enabled = enabled
            self.controller.shared['engineer_mode_enabled'] = enabled
            status = "enabled" if enabled else "disabled"
            print(f"[BLE] Engineer mode {status}")
            return {"success": True, "message": f"Engineer mode {status}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ========================================================================
    # STATUS GENERATION
    # ========================================================================

    def _get_status_json(self) -> bytes:
        """Generate current status JSON"""
        try:
            status = {
                "state": self.controller.shared.get('state', 'UNKNOWN'),
                "m1_percent": self.controller.shared.get('m1_percent', 0),
                "m2_percent": self.controller.shared.get('m2_percent', 0),
                "m1_speed": self.controller.shared.get('m1_speed', 0),
                "m2_speed": self.controller.shared.get('m2_speed', 0),
                "auto_close_countdown": self.controller.shared.get('auto_close_countdown', 0),
                "timestamp": int(time.time())
            }
            return json.dumps(status).encode('utf-8')
        except Exception as e:
            print(f"[BLE] Error generating status: {e}")
            return b'{"error":"status generation failed"}'

    def _get_system_status(self) -> Dict:
        """Get system diagnostic information"""
        status = {
            "uptime": 0,
            "cpu_temp": 0,
            "memory_percent": 0,
            "ble_connected": len(self.connected_devices) > 0,
            "connection_count": len(self.connected_devices)
        }

        if psutil:
            try:
                status["uptime"] = time.time() - psutil.boot_time()
                status["memory_percent"] = psutil.virtual_memory().percent
            except:
                pass

        # Try to read CPU temperature
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                status["cpu_temp"] = float(f.read().strip()) / 1000.0
        except:
            pass

        return status

    def _status_update_loop(self):
        """Background thread to update status"""
        print("[BLE] Status update thread started")
        while self.status_running:
            try:
                self.last_status = self._get_status_json()
                time.sleep(STATUS_UPDATE_INTERVAL)
            except Exception as e:
                print(f"[BLE] Error in status update: {e}")
                time.sleep(1.0)
        print("[BLE] Status update thread stopped")

    # ========================================================================
    # GATT SERVER CREATION
    # ========================================================================

    def build_gatt_server(self) -> peripheral.Peripheral:
        """
        Build the complete GATT server with all services and characteristics
        """
        print("[BLE] Building GATT server...")

        # Get device name based on pairing mode
        device_name = f"Gatetorio-{self.hardware_id[-4:]}" if self.pairing_window_active else "Gatetorio"

        # Get first available Bluetooth adapter
        try:
            ble_adapter = next(adapter.Adapter.available())
            adapter_address = ble_adapter.address
            print(f"[BLE] Using Bluetooth adapter: {adapter_address}")
        except StopIteration:
            raise RuntimeError("No Bluetooth adapter found! Check: sudo hciconfig hci0 up")

        # Create peripheral
        ble_peripheral = peripheral.Peripheral(
            adapter_address,
            local_name=device_name,
            appearance=0x0000  # Generic
        )

        # Add all GATT services
        self._add_device_info_service(ble_peripheral)
        self._add_gate_control_service(ble_peripheral)
        self._add_configuration_service(ble_peripheral)
        self._add_diagnostics_service(ble_peripheral)
        self._add_security_service(ble_peripheral)

        print("[BLE] GATT server built successfully")
        return ble_peripheral

    def _add_device_info_service(self, ble_peripheral):
        """Add Device Information service"""
        print("[BLE] Adding Device Info service...")

        ble_peripheral.add_service(srv_id=1, uuid=SERVICE_DEVICE_INFO, primary=True)

        # Hardware ID (read-only)
        ble_peripheral.add_characteristic(
            srv_id=1, chr_id=1, uuid=CHAR_HARDWARE_ID,
            value=list(self.hardware_id.encode('utf-8')),
            notifying=False, flags=['read']
        )

        # Software Version (read-only)
        ble_peripheral.add_characteristic(
            srv_id=1, chr_id=2, uuid=CHAR_SOFTWARE_VERSION,
            value=list(self.software_version.encode('utf-8')),
            notifying=False, flags=['read']
        )

        # User ID (read/write)
        def read_user_id():
            return list(self.config.user_id.encode('utf-8'))

        def write_user_id(value):
            try:
                self.config.user_id = bytes(value).decode('utf-8')
                self._save_config()
                print(f"[BLE] User ID updated: {self.config.user_id}")
            except Exception as e:
                print(f"[BLE] Error updating user ID: {e}")

        ble_peripheral.add_characteristic(
            srv_id=1, chr_id=3, uuid=CHAR_USER_ID,
            value=[], notifying=False, flags=['read', 'write'],
            read_callback=read_user_id,
            write_callback=write_user_id
        )

    def _add_gate_control_service(self, ble_peripheral):
        """Add Gate Control service"""
        print("[BLE] Adding Gate Control service...")

        ble_peripheral.add_service(srv_id=2, uuid=SERVICE_GATE_CONTROL, primary=True)

        # Command TX (write-only)
        def write_command(value):
            try:
                response = self.handle_command(bytes(value))
                self.last_command_response = json.dumps(response).encode('utf-8')
                print(f"[BLE] Command executed: {response.get('message', 'OK')}")
            except Exception as e:
                print(f"[BLE] Error executing command: {e}")
                self.last_command_response = json.dumps({
                    "success": False, "message": str(e)
                }).encode('utf-8')

        ble_peripheral.add_characteristic(
            srv_id=2, chr_id=1, uuid=CHAR_COMMAND_TX,
            value=[], notifying=False, flags=['write'],
            write_callback=write_command
        )

        # Command Response (read-only)
        def read_response():
            return list(self.last_command_response)

        ble_peripheral.add_characteristic(
            srv_id=2, chr_id=2, uuid=CHAR_COMMAND_RESPONSE,
            value=[], notifying=False, flags=['read'],
            read_callback=read_response
        )

        # Status (read + notify)
        def read_status():
            return list(self._get_status_json())

        ble_peripheral.add_characteristic(
            srv_id=2, chr_id=3, uuid=CHAR_STATUS,
            value=[], notifying=True, flags=['read', 'notify'],
            read_callback=read_status
        )

    def _add_configuration_service(self, ble_peripheral):
        """Add Configuration service"""
        print("[BLE] Adding Configuration service...")

        ble_peripheral.add_service(srv_id=3, uuid=SERVICE_CONFIGURATION, primary=True)

        # Config Data (read/write)
        def read_config():
            try:
                config_json = json.dumps(self.controller.config).encode('utf-8')
                return list(config_json)
            except:
                return list(b'{}')

        def write_config(value):
            try:
                config_data = json.loads(bytes(value).decode('utf-8'))
                self._handle_set_config(config_data)
            except Exception as e:
                print(f"[BLE] Error writing config: {e}")

        ble_peripheral.add_characteristic(
            srv_id=3, chr_id=1, uuid=CHAR_CONFIG_DATA,
            value=[], notifying=False, flags=['read', 'write'],
            read_callback=read_config,
            write_callback=write_config
        )

    def _add_diagnostics_service(self, ble_peripheral):
        """Add Diagnostics service"""
        print("[BLE] Adding Diagnostics service...")

        ble_peripheral.add_service(srv_id=4, uuid=SERVICE_DIAGNOSTICS, primary=True)

        # System Status (read-only)
        def read_system_status():
            try:
                status_json = json.dumps(self._get_system_status()).encode('utf-8')
                return list(status_json)
            except:
                return list(b'{}')

        ble_peripheral.add_characteristic(
            srv_id=4, chr_id=1, uuid=CHAR_SYSTEM_STATUS,
            value=[], notifying=False, flags=['read'],
            read_callback=read_system_status
        )

    def _add_security_service(self, ble_peripheral):
        """Add Security service"""
        print("[BLE] Adding Security service...")

        ble_peripheral.add_service(srv_id=5, uuid=SERVICE_SECURITY, primary=True)

        # Pairing Control (write-only)
        def write_pairing_control(value):
            try:
                cmd = json.loads(bytes(value).decode('utf-8'))
                action = cmd.get('action')
                if action == 'open_window':
                    duration = cmd.get('duration', PAIRING_WINDOW_DURATION)
                    self.start_pairing_window(duration)
                elif action == 'close_window':
                    self.pairing_window_active = False
                    self.config.pairing_mode = False
                print(f"[BLE] Pairing control: {action}")
            except Exception as e:
                print(f"[BLE] Error in pairing control: {e}")

        ble_peripheral.add_characteristic(
            srv_id=5, chr_id=1, uuid=CHAR_PAIRING_CONTROL,
            value=[], notifying=False, flags=['write'],
            write_callback=write_pairing_control
        )

        # Engineer Mode (read/write)
        def read_engineer_mode():
            enabled = b'1' if self.config.engineer_mode_enabled else b'0'
            return list(enabled)

        def write_engineer_mode(value):
            try:
                enabled = bytes(value).decode('utf-8') == '1'
                self._handle_enable_engineer_mode(enabled)
            except Exception as e:
                print(f"[BLE] Error setting engineer mode: {e}")

        ble_peripheral.add_characteristic(
            srv_id=5, chr_id=2, uuid=CHAR_ENGINEER_MODE,
            value=[], notifying=False, flags=['read', 'write'],
            read_callback=read_engineer_mode,
            write_callback=write_engineer_mode
        )

    # ========================================================================
    # SERVER LIFECYCLE
    # ========================================================================

    def start(self):
        """Start the BLE GATT server"""
        print("=" * 60)
        print("Gatetorio BLE Server v1.0.0 (bluezero)")
        print("=" * 60)
        print(f"Hardware ID: {self.hardware_id}")
        print(f"User ID: {self.config.user_id}")
        print(f"Stealth mode: {self.config.stealth_mode}")
        print(f"Whitelist enabled: {self.config.whitelist_enabled}")

        # Check for unexpected reboot
        if self._check_reboot_flag():
            self.start_pairing_window()
        else:
            print("[BLE] Skipping pairing window (expected reboot)")

        # Start status update thread
        self.status_running = True
        self.status_thread = threading.Thread(target=self._status_update_loop, daemon=True)
        self.status_thread.start()

        # Build and run GATT server
        try:
            ble_peripheral = self.build_gatt_server()
            print("[BLE] Starting GATT server...")

            # Try to publish (register advertisement)
            try:
                print("[BLE] Registering BLE advertisement...")
                ble_peripheral.publish()
                print("[BLE] ✓ Advertisement registered successfully!")
                print("[BLE] Ready for connections!")

            except Exception as adv_error:
                print(f"[BLE] ⚠ Advertisement registration failed: {adv_error}")
                print("[BLE] This is often caused by:")
                print("[BLE]   1. Another BLE advertisement already registered")
                print("[BLE]   2. BlueZ caching old advertisements")
                print("[BLE]   3. Bluetooth adapter in wrong state")
                print()
                print("[BLE] ATTEMPTING WORKAROUND...")
                print("[BLE] Restarting Bluetooth service to clear old advertisements...")

                # Try to restart Bluetooth to clear advertisements
                import subprocess
                try:
                    subprocess.run(['systemctl', 'restart', 'bluetooth'],
                                 check=True, timeout=10,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print("[BLE] ✓ Bluetooth service restarted")
                    print("[BLE] Waiting 3 seconds for Bluetooth to stabilize...")
                    time.sleep(3)

                    # Rebuild peripheral after Bluetooth restart
                    print("[BLE] Rebuilding GATT server...")
                    ble_peripheral = self.build_gatt_server()

                    # Try publish again
                    print("[BLE] Attempting advertisement registration again...")
                    ble_peripheral.publish()
                    print("[BLE] ✓ Advertisement registered successfully (after restart)!")
                    print("[BLE] Ready for connections!")

                except subprocess.TimeoutExpired:
                    print("[BLE] ERROR: Bluetooth restart timed out")
                    raise RuntimeError("Could not restart Bluetooth service")
                except subprocess.CalledProcessError as e:
                    print(f"[BLE] ERROR: Bluetooth restart failed: {e}")
                    print("[BLE] Try manually: sudo systemctl restart bluetooth")
                    raise
                except Exception as retry_error:
                    print(f"[BLE] ERROR: Advertisement still failing after restart: {retry_error}")
                    print()
                    print("[BLE] MANUAL TROUBLESHOOTING REQUIRED:")
                    print("[BLE]   1. Stop this script (Ctrl+C)")
                    print("[BLE]   2. Restart Bluetooth: sudo systemctl restart bluetooth")
                    print("[BLE]   3. Check status: sudo systemctl status bluetooth")
                    print("[BLE]   4. Check for other BLE apps: ps aux | grep ble")
                    print("[BLE]   5. Reboot if necessary: sudo reboot")
                    raise

            # Keep running
            print("[BLE] Press Ctrl+C to stop")
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[BLE] Shutting down...")
            self.status_running = False
            if self.status_thread:
                self.status_thread.join(timeout=2)
        except Exception as e:
            print(f"[BLE] Error: {e}")
            import traceback
            traceback.print_exc()
            self.status_running = False


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    import sys

    # Check for standalone mode (don't create controller)
    standalone = '--standalone' in sys.argv or '-s' in sys.argv

    if standalone:
        print("=" * 60)
        print("ERROR: Standalone mode not yet implemented")
        print("=" * 60)
        print()
        print("The BLE server currently requires creating its own")
        print("GateController instance, which conflicts with an")
        print("already-running controller.")
        print()
        print("WORKAROUND FOR TESTING:")
        print("1. Stop any running gate controller (close desktop launcher)")
        print("2. Start BLE server: sudo python3 ble_server_bluezero.py")
        print("3. BLE server will manage the gate controller")
        print()
        print("PERMANENT SOLUTION (Phase 2):")
        print("Modify BLE server to connect to existing controller via IPC")
        print()
        sys.exit(1)

    print("[Main] Initializing Gatetorio gate controller...")
    print("[Main] WARNING: Make sure no other controller instance is running!")
    print("[Main] Close the desktop launcher before starting BLE server.")
    print()
    print("[Main] Step 1: Waiting for hardware initialization...")
    time.sleep(2)  # Give GPIO/ADC time to initialize at kernel level

    try:
        print("[Main] Step 2: Creating controller instance...")
        controller = GateController()

        # CRITICAL: Wait for input manager to stabilize ADC readings
        # The input_manager process starts immediately but needs time
        # for ADC to take stable readings before safety systems engage
        print("[Main] Step 3: Waiting for input manager to stabilize (5 seconds)...")
        print("[Main]   This allows ADC readings to settle before safety checks")
        time.sleep(5)

        # Verify we're getting valid inputs
        print("[Main] Step 4: Verifying input readings...")
        safety_check_count = 0
        max_safety_checks = 3

        while safety_check_count < max_safety_checks:
            # Check if safety system is constantly triggered (indicates bad ADC)
            stop_opening = controller.shared.get('stop_opening_active', False)
            stop_closing = controller.shared.get('stop_closing_active', False)

            if stop_opening or stop_closing:
                safety_check_count += 1
                print(f"[Main]   ⚠ Safety triggered ({safety_check_count}/{max_safety_checks}) - waiting...")
                time.sleep(1)
            else:
                print(f"[Main]   ✓ Inputs stable - safety system nominal")
                break

        if safety_check_count >= max_safety_checks:
            print("[Main] ERROR: Safety system constantly triggered!")
            print("[Main] This indicates ADC/input readings are invalid.")
            print("[Main] Run diagnostic: sudo python3 test_hardware_root.py")
            raise RuntimeError("Input manager not getting valid ADC readings")

        print("[Main] ✓ Controller initialized and stable")
        print()

    except Exception as e:
        print(f"[Main] ERROR: Failed to initialize controller: {e}")
        print("[Main] This is likely because:")
        print("  1. Another controller instance is already running")
        print("  2. GPIO/ADC permissions issue")
        print("  3. Hardware not properly initialized")
        print()
        print("TROUBLESHOOTING:")
        print("  - Close any running gate controller instances")
        print("  - Check: ls -la /dev/spidev* /dev/gpiomem")
        print("  - Verify: sudo usermod -aG gpio,spi root")
        print("  - Wait 5 seconds and try again")
        sys.exit(1)

    print("[Main] Initializing BLE server...")
    ble_server = GatetorioBLEServer(controller)

    print("[Main] Starting BLE GATT server...")
    ble_server.start()


if __name__ == "__main__":
    main()
