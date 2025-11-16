#!/usr/bin/env python3
"""
Gatetorio BLE GATT Server - Pure localGATT implementation

Complete rewrite using localGATT.Application + manual Advertisement.
This bypasses peripheral.Peripheral to gain full control over advertisement payload.
"""

import sys
import json
import time
from bluezero import adapter, localGATT, GATT, advertisement, async_tools

# Import the main BLE server to reuse config and command handling
from ble_server_bluezero import (
    GatetorioBLEServer,
    SERVICE_GATE_CONTROL, SERVICE_CONFIGURATION, SERVICE_DIAGNOSTICS,
    CHAR_COMMAND_TX, CHAR_COMMAND_RESPONSE, CHAR_STATUS,
    CHAR_INPUT_CONFIG, CHAR_INPUT_STATES,
    STATUS_UPDATE_INTERVAL
)

class GateControlService(localGATT.Service):
    """Gate Control service with command and status characteristics"""

    def __init__(self, service_id, ble_server):
        self.ble_server = ble_server
        super().__init__(service_id, SERVICE_GATE_CONTROL, True)  # PRIMARY

        # Add characteristics
        self.add_characteristic(CommandTxChar(1, self.ble_server))
        self.add_characteristic(CommandResponseChar(2, self.ble_server))
        self.add_characteristic(StatusChar(3, self.ble_server))


class CommandTxChar(localGATT.Characteristic):
    """Command TX characteristic (write-only)"""

    def __init__(self, char_id, ble_server):
        self.ble_server = ble_server
        super().__init__(char_id, CHAR_COMMAND_TX, ['write'], localGATT.Service)

    def WriteValue(self, value, options):
        """Handle command write"""
        try:
            raw_bytes = bytes(value)
            print(f"[BLE] Command received: {raw_bytes}")
            response = self.ble_server.handle_command(raw_bytes)
            self.ble_server.last_command_response = json.dumps(response).encode('utf-8')
            print(f"[BLE] Response: {response}")
        except Exception as e:
            print(f"[BLE] Error handling command: {e}")
            self.ble_server.last_command_response = json.dumps({
                "success": False, "message": str(e)
            }).encode('utf-8')


class CommandResponseChar(localGATT.Characteristic):
    """Command Response characteristic (read-only)"""

    def __init__(self, char_id, ble_server):
        self.ble_server = ble_server
        super().__init__(char_id, CHAR_COMMAND_RESPONSE, ['read'], localGATT.Service)

    def ReadValue(self, options):
        """Return last command response"""
        return list(self.ble_server.last_command_response)


class StatusChar(localGATT.Characteristic):
    """Status characteristic (read + notify)"""

    def __init__(self, char_id, ble_server):
        self.ble_server = ble_server
        super().__init__(char_id, CHAR_STATUS, ['read', 'notify'], localGATT.Service)
        self.notifying = False

    def ReadValue(self, options):
        """Return current status"""
        return list(self.ble_server._get_status_json())

    def StartNotify(self):
        """Client enabled notifications"""
        if not self.notifying:
            self.notifying = True
            print("[BLE] Status notifications enabled")
            # Start 1Hz update timer
            async_tools.add_timer_seconds(STATUS_UPDATE_INTERVAL, self._update_status)

    def StopNotify(self):
        """Client disabled notifications"""
        self.notifying = False
        print("[BLE] Status notifications disabled")

    def _update_status(self):
        """Timer callback to send status updates"""
        if self.notifying:
            try:
                status_json = self.ble_server._get_status_json()
                self.set_value(list(status_json))
                return True  # Continue timer
            except Exception as e:
                print(f"[BLE] Error in status update: {e}")
                return False
        return False  # Stop timer


class ConfigurationService(localGATT.Service):
    """Configuration service with input config"""

    def __init__(self, service_id, ble_server):
        self.ble_server = ble_server
        super().__init__(service_id, SERVICE_CONFIGURATION, True)  # PRIMARY

        # Add Input Config characteristic
        self.add_characteristic(InputConfigChar(1, self.ble_server))


class InputConfigChar(localGATT.Characteristic):
    """Input Configuration characteristic (read-only)"""

    def __init__(self, char_id, ble_server):
        self.ble_server = ble_server
        super().__init__(char_id, CHAR_INPUT_CONFIG, ['read'], localGATT.Service)

    def ReadValue(self, options):
        """Return input_config.json"""
        try:
            print("[BLE] Input Config READ")
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'r') as f:
                config = json.load(f)
            config_json = json.dumps(config).encode('utf-8')
            print(f"[BLE] Sending {len(config_json)} bytes")
            return list(config_json)
        except Exception as e:
            print(f"[BLE] Error reading input config: {e}")
            return list(b'{"error":"not available"}')


class DiagnosticsService(localGATT.Service):
    """Diagnostics service with input states"""

    def __init__(self, service_id, ble_server):
        self.ble_server = ble_server
        super().__init__(service_id, SERVICE_DIAGNOSTICS, True)  # PRIMARY

        # Add Input States characteristic
        self.add_characteristic(InputStatesChar(1, self.ble_server))


class InputStatesChar(localGATT.Characteristic):
    """Input States characteristic (read-only)"""

    def __init__(self, char_id, ble_server):
        self.ble_server = ble_server
        super().__init__(char_id, CHAR_INPUT_STATES, ['read'], localGATT.Service)

    def ReadValue(self, options):
        """Return current input states"""
        try:
            print("[BLE] Input States READ")
            states = {}
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'r') as f:
                input_config = json.load(f)['inputs']

            for input_name, config in input_config.items():
                is_active = self.ble_server.controller.shared.get(f'{input_name}_state', False)
                states[input_name] = {
                    "active": is_active,
                    "function": config.get('function'),
                    "type": config.get('type'),
                    "channel": config.get('channel')
                }

            states_json = json.dumps(states).encode('utf-8')
            print(f"[BLE] Sending {len(states_json)} bytes")
            return list(states_json)
        except Exception as e:
            print(f"[BLE] Error reading input states: {e}")
            return list(b'{"error":"not available"}')


def start_localgatt_server(ble_server: GatetorioBLEServer):
    """
    Start BLE server using pure localGATT approach
    """
    print("=" * 60)
    print("Gatetorio BLE Server - localGATT Implementation")
    print("=" * 60)

    try:
        # Get Bluetooth adapter
        dongle = next(adapter.Adapter.available())
        dongle_addr = dongle.address
        print(f"[BLE] Using adapter: {dongle_addr}")

        if not dongle.powered:
            print("[BLE] Powering on adapter...")
            dongle.powered = True
            time.sleep(1)

        # Create GATT Application
        print("[BLE] Creating GATT application...")
        app = localGATT.Application()

        # Add services
        print("[BLE] Adding Gate Control service (PRIMARY)...")
        gate_service = GateControlService(1, ble_server)
        app.add_service(gate_service)

        print("[BLE] Adding Configuration service (PRIMARY)...")
        config_service = ConfigurationService(2, ble_server)
        app.add_service(config_service)

        print("[BLE] Adding Diagnostics service (PRIMARY)...")
        diag_service = DiagnosticsService(3, ble_server)
        app.add_service(diag_service)

        # Register GATT application
        print("[BLE] Registering GATT application with BlueZ...")
        gatt_mgr = GATT.GattManager(dongle_addr)
        gatt_mgr.register_application(app, {})
        print("[BLE] ✓ GATT application registered")

        # Create advertisement with ONLY Gate Control UUID
        device_name = f"Gatetorio-{ble_server.hardware_id[-4:]}"
        print(f"[BLE] Creating advertisement: {device_name}")
        print(f"[BLE] Advertising ONLY: {SERVICE_GATE_CONTROL}")
        print("[BLE] Note: Config/Diagnostics are PRIMARY (discoverable after connection)")

        advert = advertisement.Advertisement(1, 'peripheral', local_name=device_name)
        advert.service_UUIDs = [SERVICE_GATE_CONTROL]  # ONLY one UUID
        advert.appearance = 0x0000

        # Register advertisement
        print("[BLE] Registering advertisement...")
        ad_mgr = advertisement.AdvertisingManager(dongle_addr)
        ad_mgr.register_advertisement(advert, {})
        print("[BLE] ✓ Advertisement registered successfully!")
        print()
        print("[BLE] ✓✓✓ BLE SERVER READY ✓✓✓")
        print("[BLE] Ready for connections!")
        print("[BLE] Press Ctrl+C to stop")

        # Start mainloop
        app.start()

    except KeyboardInterrupt:
        print("\n[BLE] Shutting down...")
    except Exception as e:
        print(f"[BLE] ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # This would be called from main script
    print("This module should be imported and used with GatetorioBLEServer")
    print("See ble_server_bluezero.py for full implementation")
