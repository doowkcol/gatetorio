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
    CHAR_CONFIG_DATA, CHAR_INPUT_CONFIG, CHAR_INPUT_STATES,
    STATUS_UPDATE_INTERVAL,
    INPUT_FUNCTION_CODES
)

class GateControlService(localGATT.Service):
    """Gate Control service with command and status characteristics"""

    def __init__(self, service_id, ble_server):
        self.ble_server = ble_server
        self.service_id = service_id  # Store for characteristics
        super().__init__(service_id, SERVICE_GATE_CONTROL, True)  # PRIMARY


class CommandTxChar(localGATT.Characteristic):
    """Command TX characteristic (write-only)"""

    def __init__(self, index, service, ble_server):
        self.ble_server = ble_server
        super().__init__(
            service.service_id,  # service_id (int)
            index,               # characteristic_id (int)
            CHAR_COMMAND_TX,     # uuid (str)
            [],                  # value
            False,               # notifying
            ['write']            # flags
        )

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

    def __init__(self, index, service, ble_server):
        self.ble_server = ble_server
        super().__init__(
            service.service_id,    # service_id (int)
            index,                 # characteristic_id (int)
            CHAR_COMMAND_RESPONSE, # uuid (str)
            [],
            False,
            ['read']
        )

    def ReadValue(self, options):
        """Return last command response"""
        return list(self.ble_server.last_command_response)


class StatusChar(localGATT.Characteristic):
    """Status characteristic (read + notify)"""

    def __init__(self, index, service, ble_server):
        self.ble_server = ble_server
        super().__init__(
            service.service_id,  # service_id (int)
            index,               # characteristic_id (int)
            CHAR_STATUS,         # uuid (str)
            [],
            False,
            ['read', 'notify']
        )
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
    """Configuration service with gate config and input config"""

    def __init__(self, service_id, ble_server):
        self.ble_server = ble_server
        self.service_id = service_id  # Store for characteristics
        super().__init__(service_id, SERVICE_CONFIGURATION, True)  # PRIMARY


class ConfigDataChar(localGATT.Characteristic):
    """Gate Configuration characteristic (read/write)"""

    def __init__(self, index, service, ble_server):
        self.ble_server = ble_server
        super().__init__(
            service.service_id,
            index,
            CHAR_CONFIG_DATA,  # 0x2001 - Gate configuration
            [],
            False,
            ['read', 'write']
        )

    def ReadValue(self, options):
        """Return gate configuration"""
        try:
            print("[BLE] Config Data READ")
            config_json = json.dumps(self.ble_server.controller.config, separators=(',', ':')).encode('utf-8')
            print(f"[BLE] Sending {len(config_json)} bytes (gate config)")
            return list(config_json)
        except Exception as e:
            print(f"[BLE] Error reading config: {e}")
            return list(b'{}')

    def WriteValue(self, value, options):
        """Write gate configuration"""
        try:
            raw_bytes = bytes(value)
            print(f"[BLE] Config Data WRITE: {len(raw_bytes)} bytes")
            config_data = json.loads(raw_bytes.decode('utf-8'))
            response = self.ble_server._handle_set_config(config_data)
            print(f"[BLE] Config updated successfully")
        except Exception as e:
            print(f"[BLE] Error writing config: {e}")


class InputConfigChar(localGATT.Characteristic):
    """Input Configuration characteristic (read-only)"""

    def __init__(self, index, service, ble_server):
        self.ble_server = ble_server
        super().__init__(
            service.service_id,  # service_id (int)
            index,               # characteristic_id (int)
            CHAR_INPUT_CONFIG,   # uuid (str)
            [],
            False,
            ['read']
        )

    def ReadValue(self, options):
        """Return input_config.json (ultra-compressed array format)"""
        try:
            print("[BLE] Input Config READ")
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'r') as f:
                full_config = json.load(f)

            # Ultra-compress: Use array format [name, function_code, type, channel]
            # Type codes: NC=1, NO=2, 8K2=3
            TYPE_CODES = {"NC": 1, "NO": 2, "8K2": 3}

            inputs = full_config.get('inputs', {})
            compressed = []
            for name, cfg in inputs.items():
                function_name = cfg.get('function')
                function_code = INPUT_FUNCTION_CODES.get(function_name, 0)
                type_str = cfg.get('type')
                type_code = TYPE_CODES.get(type_str, 0)
                channel = cfg.get('channel', 0)

                # Array format: [name, func, type, chan]
                compressed.append([name, function_code, type_code, channel])

            config_json = json.dumps(compressed, separators=(',', ':')).encode('utf-8')
            print(f"[BLE] Sending {len(config_json)} bytes (array format)")
            print(f"[BLE] Format: [[name,func,type,chan],...]")
            if len(config_json) > 186:
                print(f"[BLE] WARNING: Data ({len(config_json)} bytes) may exceed BLE buffer limit (~186 bytes)")
            return list(config_json)
        except Exception as e:
            print(f"[BLE] Error reading input config: {e}")
            import traceback
            traceback.print_exc()
            return list(b'{"error":"not available"}')


class DiagnosticsService(localGATT.Service):
    """Diagnostics service with input states"""

    def __init__(self, service_id, ble_server):
        self.ble_server = ble_server
        self.service_id = service_id  # Store for characteristics
        super().__init__(service_id, SERVICE_DIAGNOSTICS, True)  # PRIMARY


class InputStatesChar(localGATT.Characteristic):
    """Input States characteristic (read-only)"""

    def __init__(self, index, service, ble_server):
        self.ble_server = ble_server
        super().__init__(
            service.service_id,  # service_id (int)
            index,               # characteristic_id (int)
            CHAR_INPUT_STATES,   # uuid (str)
            [],
            False,
            ['read']
        )

    def ReadValue(self, options):
        """Return current input states (active flags + resistance for 8K2)"""
        try:
            print("[BLE] Input States READ")
            states = {}
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'r') as f:
                input_config = json.load(f)['inputs']

            # Send active state + resistance for 8K2 inputs
            for input_name, config in input_config.items():
                is_active = self.ble_server.controller.shared.get(f'{input_name}_state', False)
                input_type = config.get('type')

                # For 8K2 inputs, include resistance reading
                if input_type == '8K2':
                    # Get voltage reading from shared dict
                    voltage = self.ble_server.controller.shared.get(f'{input_name}_voltage', 0.0)
                    # Send as [active, voltage] to save space
                    states[input_name] = [is_active, round(voltage, 2)]
                else:
                    # Just boolean for NO/NC inputs
                    states[input_name] = is_active

            states_json = json.dumps(states, separators=(',', ':')).encode('utf-8')
            print(f"[BLE] Sending {len(states_json)} bytes (active states + 8K2 voltages)")
            if len(states_json) > 186:
                print(f"[BLE] WARNING: Data ({len(states_json)} bytes) may exceed BLE buffer limit (~186 bytes)")
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

        # Add Gate Control service and characteristics
        print("[BLE] Adding Gate Control service (PRIMARY)...")
        gate_service = GateControlService(1, ble_server)
        cmd_tx_char = CommandTxChar(1, gate_service, ble_server)
        cmd_resp_char = CommandResponseChar(2, gate_service, ble_server)
        status_char = StatusChar(3, gate_service, ble_server)

        app.add_managed_object(gate_service)
        app.add_managed_object(cmd_tx_char)
        app.add_managed_object(cmd_resp_char)
        app.add_managed_object(status_char)

        # Add Configuration service and characteristics
        print("[BLE] Adding Configuration service (PRIMARY)...")
        config_service = ConfigurationService(2, ble_server)
        config_data_char = ConfigDataChar(1, config_service, ble_server)
        input_config_char = InputConfigChar(2, config_service, ble_server)

        app.add_managed_object(config_service)
        app.add_managed_object(config_data_char)
        app.add_managed_object(input_config_char)

        # Add Diagnostics service and characteristics
        print("[BLE] Adding Diagnostics service (PRIMARY)...")
        diag_service = DiagnosticsService(3, ble_server)
        input_states_char = InputStatesChar(1, diag_service, ble_server)

        app.add_managed_object(diag_service)
        app.add_managed_object(input_states_char)

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

        advert = advertisement.Advertisement(1, 'peripheral')
        advert.local_name = device_name
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
