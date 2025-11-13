#!/usr/bin/env python3
"""
Gatetorio BLE Bridge - Bluetooth Low Energy server for gate control

This module provides a BLE GATT server that allows mobile apps to control
the gate system via Bluetooth. Features:
- Stealth mode: 30s pairing window on unexpected boot, then whitelist-only
- GATT services for commands, status, config, and diagnostics
- Real-time status notifications
- Engineer mode for direct motor control
- Whitelist management for security
"""

import asyncio
import json
import time
import hashlib
import pathlib
from typing import Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime

try:
    from bleak import BleakServer, BleakGATTCharacteristic, BleakGATTServiceCollection
    from bleak.backends.characteristic import GATTCharacteristicProperties
except ImportError:
    print("ERROR: bleak not installed. Install with: pip3 install -r requirements_bluetooth.txt")
    exit(1)

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


@dataclass
class SystemStatus:
    """System diagnostic information"""
    cpu_temp: float = 0.0
    uptime: float = 0.0
    memory_percent: float = 0.0
    ble_connected: bool = False
    connection_count: int = 0


# ============================================================================
# BLE BRIDGE CLASS
# ============================================================================

class GatetorioBLEBridge:
    """
    BLE GATT server for Gatetorio gate control system
    """

    def __init__(self, controller: GateController):
        self.controller = controller
        self.config = BLEConfig()
        self.system_status = SystemStatus()

        # Connection tracking
        self.connected_devices: Set[str] = set()
        self.whitelist: Set[str] = set()

        # Pairing window timer
        self.pairing_window_active = False
        self.pairing_window_task: Optional[asyncio.Task] = None

        # Status notification subscribers
        self.status_subscribers: Set[BleakGATTCharacteristic] = set()

        # Hardware and software info
        self.hardware_id = self._get_hardware_id()
        self.software_version = "1.0.0"

        # Last command response
        self.last_response = {"success": True, "message": "Ready"}

        # Load configuration
        self._load_config()
        self._load_whitelist()

        print(f"[BLE] Initialized with Hardware ID: {self.hardware_id}")
        print(f"[BLE] User ID: {self.config.user_id}")

    # ========================================================================
    # HARDWARE IDENTIFICATION
    # ========================================================================

    def _get_hardware_id(self) -> str:
        """Get Raspberry Pi CPU serial number (permanent hardware ID)"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        # Return last 8 characters for brevity
                        return serial[-8:].upper()
        except Exception as e:
            print(f"[BLE] Warning: Could not read CPU serial: {e}")
            # Fallback to MAC address hash
            try:
                import uuid
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                               for i in range(0,8*6,8)][::-1])
                return hashlib.md5(mac.encode()).hexdigest()[:8].upper()
            except:
                return "UNKNOWN1"
        return "UNKNOWN2"

    def _get_device_name(self) -> str:
        """Generate BLE device name"""
        if self.pairing_window_active:
            return f"Gatetorio-{self.hardware_id[-4:]}"
        return ""  # Stealth mode - no name

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
            print(f"[BLE] Saved config to {BLE_CONFIG_FILE}")
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
                json.dump({
                    'devices': list(self.whitelist),
                }, f, indent=2)
            print(f"[BLE] Saved whitelist with {len(self.whitelist)} devices")
        except Exception as e:
            print(f"[BLE] Error saving whitelist: {e}")

    # ========================================================================
    # PAIRING WINDOW MANAGEMENT
    # ========================================================================

    async def start_pairing_window(self, duration: int = PAIRING_WINDOW_DURATION):
        """
        Open pairing window for new device connections
        Args:
            duration: Duration in seconds (default 30)
        """
        print(f"[BLE] Opening pairing window for {duration} seconds...")
        self.pairing_window_active = True
        self.config.pairing_mode = True

        # Wait for duration
        await asyncio.sleep(duration)

        # Close pairing window
        print("[BLE] Pairing window closed - entering stealth mode")
        self.pairing_window_active = False
        self.config.pairing_mode = False

    def _should_allow_connection(self, device_address: str) -> bool:
        """
        Check if a device should be allowed to connect
        Args:
            device_address: BLE MAC address of connecting device
        Returns:
            True if connection should be allowed
        """
        # Always allow during pairing window
        if self.pairing_window_active:
            return True

        # In stealth mode, check whitelist
        if self.config.stealth_mode and self.config.whitelist_enabled:
            return device_address in self.whitelist

        # Default: allow
        return True

    # ========================================================================
    # COMMAND HANDLERS
    # ========================================================================

    async def _handle_command(self, command_json: str) -> Dict:
        """
        Process incoming command from BLE client
        Args:
            command_json: JSON string with command data
        Returns:
            Response dictionary
        """
        try:
            cmd = json.loads(command_json)
            cmd_type = cmd.get('cmd')
            key = cmd.get('key')
            value = cmd.get('value')

            print(f"[BLE] Command received: {cmd_type} {key}")

            # Standard pulse commands
            if cmd_type == 'pulse':
                return await self._handle_pulse_command(key)

            # Engineer mode commands
            elif cmd_type == 'engineer_pulse':
                return await self._handle_engineer_command(key)

            # Configuration commands
            elif cmd_type == 'get_config':
                return await self._handle_get_config()

            elif cmd_type == 'set_config':
                return await self._handle_set_config(value)

            elif cmd_type == 'reload_config':
                return await self._handle_reload_config()

            elif cmd_type == 'save_learned_times':
                return await self._handle_save_learned_times()

            # System commands
            elif cmd_type == 'reboot':
                return await self._handle_reboot()

            elif cmd_type == 'get_diagnostics':
                return await self._handle_get_diagnostics()

            elif cmd_type == 'enable_engineer_mode':
                return await self._handle_enable_engineer_mode(value)

            else:
                return {"success": False, "message": f"Unknown command: {cmd_type}"}

        except json.JSONDecodeError as e:
            return {"success": False, "message": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"success": False, "message": f"Error: {e}"}

    async def _handle_pulse_command(self, key: str) -> Dict:
        """Handle standard pulse commands"""
        valid_commands = [
            'cmd_open', 'cmd_close', 'cmd_stop',
            'partial_1', 'partial_2', 'step_logic'
        ]

        if key not in valid_commands:
            return {"success": False, "message": f"Invalid pulse command: {key}"}

        # Send pulse to controller
        if key == 'step_logic':
            self.controller.shared['step_logic_pulse'] = True
        else:
            # For other commands, use pulse method if available
            # Otherwise toggle on/off quickly
            self.controller.shared[f'{key}_active'] = True
            await asyncio.sleep(0.1)
            self.controller.shared[f'{key}_active'] = False

        return {"success": True, "message": f"Pulse sent: {key}"}

    async def _handle_engineer_command(self, key: str) -> Dict:
        """Handle engineer mode direct motor control"""
        if not self.config.engineer_mode_enabled:
            return {"success": False, "message": "Engineer mode not enabled"}

        valid_commands = [
            'motor1_open', 'motor1_close',
            'motor2_open', 'motor2_close'
        ]

        if key not in valid_commands:
            return {"success": False, "message": f"Invalid engineer command: {key}"}

        # Set engineer command flag in shared dict
        self.controller.shared[f'engineer_{key}'] = True

        return {"success": True, "message": f"Engineer command sent: {key}"}

    async def _handle_get_config(self) -> Dict:
        """Get current gate configuration"""
        try:
            config = self.controller.config
            return {
                "success": True,
                "config": config
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _handle_set_config(self, config_data: Dict) -> Dict:
        """Update gate configuration"""
        try:
            # Stop gate before config change
            self.controller.shared['cmd_stop_active'] = True
            await asyncio.sleep(0.2)

            # Update config file
            CONFIG_FILE = pathlib.Path("/home/doowkcol/Gatetorio_Code/gate_config.json")
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=2)

            # Reload controller
            self.controller.reload_config()

            return {"success": True, "message": "Configuration updated"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _handle_reload_config(self) -> Dict:
        """Reload configuration from file"""
        try:
            self.controller.reload_config()
            return {"success": True, "message": "Configuration reloaded"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _handle_save_learned_times(self) -> Dict:
        """Save learned motor times to config"""
        try:
            success = self.controller.save_learned_times()
            if success:
                return {"success": True, "message": "Learned times saved"}
            else:
                return {"success": False, "message": "No learned times available"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _handle_reboot(self) -> Dict:
        """Reboot the system (requires local-only restriction)"""
        # TODO: Add safety check - only allow from local BLE, not remote
        print("[BLE] Reboot requested - not implemented yet")
        return {"success": False, "message": "Reboot not implemented"}

    async def _handle_get_diagnostics(self) -> Dict:
        """Get system diagnostics"""
        try:
            # Get input states
            input_states = {}
            # TODO: Read from controller.shared for all inputs

            # Get system info
            try:
                import psutil
                cpu_temp = 0.0
                try:
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        cpu_temp = float(f.read()) / 1000.0
                except:
                    pass

                diagnostics = {
                    "cpu_temp": cpu_temp,
                    "memory_percent": psutil.virtual_memory().percent,
                    "uptime": time.time() - psutil.boot_time(),
                    "connected_devices": len(self.connected_devices),
                }
            except ImportError:
                diagnostics = {
                    "cpu_temp": 0.0,
                    "memory_percent": 0.0,
                    "uptime": 0.0,
                    "connected_devices": len(self.connected_devices),
                }

            return {"success": True, "diagnostics": diagnostics}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _handle_enable_engineer_mode(self, enabled: bool) -> Dict:
        """Enable/disable engineer mode"""
        self.config.engineer_mode_enabled = enabled
        self.controller.shared['engineer_mode_enabled'] = enabled
        return {
            "success": True,
            "message": f"Engineer mode {'enabled' if enabled else 'disabled'}"
        }

    # ========================================================================
    # STATUS UPDATES
    # ========================================================================

    def _get_status_json(self) -> str:
        """Generate current status as JSON string"""
        try:
            status = self.controller.get_status()

            # Add flags
            flags = {
                'open_limit_m1_active': self.controller.shared.get('open_limit_m1_active', False),
                'close_limit_m1_active': self.controller.shared.get('close_limit_m1_active', False),
                'open_limit_m2_active': self.controller.shared.get('open_limit_m2_active', False),
                'close_limit_m2_active': self.controller.shared.get('close_limit_m2_active', False),
            }
            status['flags'] = flags
            status['timestamp'] = int(time.time())

            return json.dumps(status)
        except Exception as e:
            print(f"[BLE] Error generating status: {e}")
            return json.dumps({"error": str(e)})

    async def _status_update_loop(self):
        """Periodically send status updates to subscribed clients"""
        print("[BLE] Status update loop started")
        while True:
            try:
                if self.status_subscribers:
                    status_json = self._get_status_json()
                    # TODO: Send notifications to subscribers
                    # This requires characteristic.notify() support in bleak

                await asyncio.sleep(STATUS_UPDATE_INTERVAL)
            except Exception as e:
                print(f"[BLE] Error in status update loop: {e}")
                await asyncio.sleep(1.0)

    # ========================================================================
    # GATT SERVER SETUP (PLACEHOLDER)
    # ========================================================================

    async def start_server(self):
        """
        Start BLE GATT server

        NOTE: This is a placeholder implementation. Bleak's BleakServer API
        is still experimental and varies by platform. For production, you'll
        need to use platform-specific BLE libraries:
        - Linux: Use python-gatt-server or bluezero
        - Or implement using D-Bus directly for BlueZ
        """
        print("[BLE] Starting BLE GATT server...")
        print("[BLE] WARNING: Full GATT server implementation requires platform-specific code")
        print(f"[BLE] Device name: {self._get_device_name()}")
        print(f"[BLE] Hardware ID: {self.hardware_id}")

        # Check if unexpected reboot (implement reboot detection logic)
        # For now, always open pairing window for testing
        if True:  # TODO: Check reboot flag
            await self.start_pairing_window()

        # Start status update loop
        asyncio.create_task(self._status_update_loop())

        # TODO: Implement full GATT server using bluezero or dbus-next
        # For now, just keep running
        print("[BLE] Server running (placeholder mode)")
        print("[BLE] Next step: Implement GATT server using bluezero or python-gatt-server")

        # Keep running
        while True:
            await asyncio.sleep(1.0)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Main entry point for BLE bridge"""
    print("=" * 60)
    print("Gatetorio BLE Bridge v1.0.0")
    print("=" * 60)

    # Create gate controller instance
    print("[Main] Initializing gate controller...")
    controller = GateController()

    # Create BLE bridge
    print("[Main] Initializing BLE bridge...")
    bridge = GatetorioBLEBridge(controller)

    # Start server
    try:
        await bridge.start_server()
    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
    except Exception as e:
        print(f"[Main] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
