# Gatetorio BLE Implementation Guide

## Overview

This guide documents the Bluetooth Low Energy (BLE) implementation for the Gatetorio gate control system. The BLE bridge enables mobile app control via local Bluetooth connection with stealth mode, security features, and engineer-level diagnostics.

---

## Architecture

```
Flutter App (Android/iOS)
        ↓ BLE GATT
Python BLE Bridge (bluezero)
        ↓ Direct API calls
GateController + MotorManager
        ↓ GPIO
Gate Motors & Sensors
```

### Key Design Decisions

1. **BLE over Bluetooth Classic**: Avoids Apple MFi certification ($3000+/year), single codebase for Android/iOS
2. **Non-invasive bridge**: Separate process that talks to existing GateController - no modifications to core logic
3. **Stealth mode**: Device invisible except during 30s pairing window
4. **Engineer-focused**: Designed for maintenance and diagnostics, not daily homeowner use
5. **Pulse commands only**: No toggle states - reduces accidental activation risk

---

## Files Created/Modified

### New Files

| File | Purpose |
|------|---------|
| `bluetooth_bridge_ble.py` | BLE GATT server (placeholder - needs bluezero) |
| `requirements_bluetooth.txt` | Python dependencies for BLE support |
| `BLE_IMPLEMENTATION_GUIDE.md` | This document |

### Modified Files

| File | Changes |
|------|---------|
| `gate_controller_v2.py` | Added engineer mode commands (lines 1988-2094) |
| `motor_manager.py` | Added engineer motor control processing (lines 943-980) |

---

## GATT Service Structure

### Service UUIDs

**Base UUID**: `0000XXXX-4751-5445-5254-494F00000000` (encodes "GATERIO")

| Service | UUID | Purpose |
|---------|------|---------|
| Device Info | Standard `180A` | Hardware ID, software version, user ID |
| Gate Control | `00001000-4751...` | Commands, responses, status |
| Configuration | `00002000-4751...` | Config read/write, input config |
| Diagnostics | `00003000-4751...` | Input states, system status, logs |
| Security | `00004000-4751...` | Pairing control, whitelist, engineer mode |

### Key Characteristics

**Command TX** (`00001001-4751...`) - Write
```json
{
  "cmd": "pulse",
  "key": "cmd_open",
  "timestamp": 1699999999
}
```

**Status** (`00001003-4751...`) - Read, Notify (1Hz)
```json
{
  "state": "OPENING",
  "m1_percent": 45,
  "m2_percent": 42,
  "m1_speed": 85,
  "m2_speed": 82,
  "flags": {...},
  "timestamp": 1699999999
}
```

---

## Command Types

### Standard Commands (Pulse-only)
- `{"cmd": "pulse", "key": "cmd_open"}` - Open gate
- `{"cmd": "pulse", "key": "cmd_close"}` - Close gate
- `{"cmd": "pulse", "key": "cmd_stop"}` - Stop gate
- `{"cmd": "pulse", "key": "partial_1"}` - Partial open 1
- `{"cmd": "pulse", "key": "partial_2"}` - Partial open 2
- `{"cmd": "pulse", "key": "step_logic"}` - Step logic pulse

### Engineer Mode Commands (NEW)
**Requires `engineer_mode_enabled` flag**

- `{"cmd": "engineer_pulse", "key": "motor1_open"}` - Drive M1 open (hold-to-run)
- `{"cmd": "engineer_pulse", "key": "motor1_close"}` - Drive M1 close (hold-to-run)
- `{"cmd": "engineer_pulse", "key": "motor2_open"}` - Drive M2 open (hold-to-run)
- `{"cmd": "engineer_pulse", "key": "motor2_close"}` - Drive M2 close (hold-to-run)

**WARNING**: Engineer commands bypass ALL safety systems including limit switches!

### Configuration Commands
- `{"cmd": "get_config"}` - Get full config
- `{"cmd": "set_config", "value": {...}}` - Update config
- `{"cmd": "reload_config"}` - Reload from file
- `{"cmd": "save_learned_times"}` - Persist learned motor times

### System Commands
- `{"cmd": "reboot"}` - Reboot system (local only)
- `{"cmd": "get_diagnostics"}` - Get CPU temp, memory, uptime
- `{"cmd": "enable_engineer_mode", "value": true}` - Enable/disable engineer mode

---

## Stealth Mode & Security

### Boot Sequence
1. **Unexpected reboot** (power loss, crash) → 30s pairing window
2. **Scheduled reboot** (midnight, etc.) → Skip pairing, whitelist-only
3. **Manual trigger** → Re-enter pairing window via web UI or physical button

### Pairing Window (30 seconds)
- BLE advertisement active as "Gatetorio-XXXX" (last 4 of hardware ID)
- Accept new connections and bonding
- Add bonded devices to whitelist
- After 30s: Stop advertising, enter stealth mode

### Whitelist-Only Mode
- **No advertising** - invisible to BLE scans
- Only accept connections from bonded MAC addresses
- Bonded devices can connect anytime
- Whitelist stored in `/home/doowkcol/Gatetorio_Code/ble_whitelist.json`

### Dual-ID System
- **Hardware ID**: Raspberry Pi CPU serial (permanent, never changes)
- **User ID**: Changeable connection identifier (for access control)
- Both sent to Linux server for device registry (Phase 2)

---

## Engineer Mode Features

### Purpose
Direct motor control for:
- Recovering gates stuck beyond normal travel limits
- Diagnosing motor/wiring issues
- Manual positioning during installation
- Testing individual motors independently

### Safety Design
- **Requires explicit enable**: `enable_engineer_mode()` must be called first
- **Hold-to-run**: Motors only drive while button pressed (no latching)
- **Fixed speed**: 30% speed for all engineer commands
- **Visual warnings**: Clear UI warnings that safety is bypassed
- **Auto-disable**: Consider auto-disabling after timeout or gate return to normal position

### GateController Methods (gate_controller_v2.py)

```python
controller.enable_engineer_mode()              # Enable engineer controls
controller.disable_engineer_mode()             # Disable engineer controls
controller.cmd_engineer_motor1_open(True)      # M1 forward (hold)
controller.cmd_engineer_motor1_close(True)     # M1 backward (hold)
controller.cmd_engineer_motor2_open(True)      # M2 forward (hold)
controller.cmd_engineer_motor2_close(True)     # M2 backward (hold)
```

### MotorManager Processing (motor_manager.py)

Engineer mode has **highest priority** in the control loop:
1. Auto-learn mode (exclusive)
2. **Engineer mode (NEW - bypasses all safety)**
3. Deadman controls
4. Normal gate control logic

---

## Flutter App Structure (To Be Implemented)

### Dependencies
```yaml
dependencies:
  flutter_blue_plus: ^1.14.0    # BLE client
  provider: ^6.0.0               # State management
  shared_preferences: ^2.0.0     # Local storage
```

### Screens

#### 1. Connection Screen
- Scan for "Gatetorio-XXXX" devices
- Show pairing window status
- Auto-reconnect to last device
- Connection quality indicator

#### 2. Control Screen (Main)
**Separated from diagnostics to prevent accidental activation**

- Large status display (state, positions, speeds)
- Primary buttons: OPEN, STOP, CLOSE
- Secondary controls (collapsible):
  - Partial open 1/2
  - Step logic pulse
- Real-time position/speed progress bars
- Auto-close countdown

#### 3. Configuration Screen
- All 23+ gate parameters
- Categorized sections:
  - Motor settings
  - Auto-close settings
  - Safety settings
  - Partial open settings
- Save/reload buttons
- Input validation

#### 4. Diagnostics Screen
- Real-time input monitor (8 channels)
- Voltage/resistance readings
- System info (CPU temp, uptime, memory)
- Log viewer
- **Engineer Mode toggle and controls**

#### 5. Engineer Mode Sub-screen
**Requires engineer mode enabled**

- Big warning banner
- Individual motor controls:
  - M1 Open (hold button)
  - M1 Close (hold button)
  - M2 Open (hold button)
  - M2 Close (hold button)
- Disable engineer mode button

---

## Hardware Compatibility

| Feature | Pi 3 | Pi 5 | Notes |
|---------|------|------|-------|
| Bluetooth Version | 4.2 | 5.0 | Both support BLE adequately |
| Range | ~10m | ~15m | Both sufficient for local use |
| Throughput | ~1 Mbps | ~2 Mbps | More than enough for JSON |
| Concurrent Connections | 3-7 | 10+ | Single connection sufficient |
| bluezero Support | ✅ Yes | ✅ Yes | Full compatibility |

**Development target**: Pi 3 (lowest common denominator)

---

## Implementation Roadmap

### ✅ Phase 1a: Foundation (COMPLETED)
- [x] Design BLE architecture and GATT services
- [x] Create bluetooth_bridge_ble.py with command handlers
- [x] Implement stealth mode logic
- [x] Add engineer mode to GateController
- [x] Add engineer mode to MotorManager
- [x] Create requirements_bluetooth.txt

### 🔄 Phase 1b: BLE Server (IN PROGRESS)
- [ ] Install bluezero library: `pip3 install bluezero`
- [ ] Implement full GATT server using bluezero
- [ ] Test advertising and pairing
- [ ] Test characteristic read/write
- [ ] Test status notifications
- [ ] Create systemd service for auto-start

### 🔲 Phase 1c: Testing & Validation
- [ ] Test with nRF Connect app (Android)
- [ ] Test with LightBlue app (iOS)
- [ ] Verify stealth mode behavior
- [ ] Test all command types
- [ ] Validate engineer mode safety
- [ ] Performance testing (latency, throughput)

### 🔲 Phase 2: Flutter App Development
- [ ] Create Flutter project structure
- [ ] Implement BLE connection management
- [ ] Build UI screens (Connection, Control, Config, Diagnostics)
- [ ] Add state management (Provider/Riverpod)
- [ ] Implement command sending and status updates
- [ ] Add engineer mode UI with warnings
- [ ] Handle reconnection and errors
- [ ] Android testing and refinement
- [ ] iOS porting and testing (using cloud build)

### 🔲 Phase 3: Remote Connectivity (Future)
- [ ] Design Linux server architecture
- [ ] Implement device registry and heartbeat
- [ ] Create WebSocket relay for remote commands
- [ ] Build web portal for fleet management
- [ ] Add server communication to Pi
- [ ] Update app for remote device selection
- [ ] Security hardening and authentication

---

## Next Steps (Immediate)

### 1. Install bluezero
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-dbus libdbus-1-dev libglib2.0-dev
pip3 install bluezero
```

### 2. Implement GATT Server

Replace placeholder in `bluetooth_bridge_ble.py` with full bluezero implementation:

```python
from bluezero import adapter, peripheral, gatt_server

# Create GATT application
app = gatt_server.Application()

# Add services and characteristics
device_info_service = gatt_server.Service(SERVICE_DEVICE_INFO, True)
# ... add characteristics

# Start advertising
adapter.Adapter().powered = True
peripheral.Peripheral(adapter.Adapter().address, local_name=device_name)
```

Reference: https://ukbaz.github.io/bluezero/

### 3. Create Systemd Service

File: `/etc/systemd/system/gatetorio-ble.service`
```ini
[Unit]
Description=Gatetorio BLE Bridge
After=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/doowkcol/Gatetorio_Code/bluetooth_bridge_ble.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gatetorio-ble.service
sudo systemctl start gatetorio-ble.service
```

### 4. Test with Generic BLE App

**Android**: nRF Connect
- Scan for "Gatetorio-XXXX"
- Connect and bond
- Browse GATT services
- Write to Command TX characteristic
- Read Status characteristic
- Subscribe to notifications

**iOS**: LightBlue
- Same workflow as Android

### 5. Validate Engineer Mode

Test via web UI first:
```python
from gate_controller_v2 import GateController

controller = GateController()
controller.enable_engineer_mode()
controller.cmd_engineer_motor1_open(True)   # Motor should drive
# ... release button
controller.cmd_engineer_motor1_open(False)  # Motor should stop
```

---

## Security Considerations

### Command Restrictions
- **Remote safe**: Reboot, config changes, diagnostics, status queries
- **Local BLE only**: Factory reset, user ID changes, engineer mode

### Update Management
- Manual updates only - no auto-updates during gate operation
- App caches updates downloaded on WiFi
- Engineers pre-download for offline deployment
- Optional scheduled reboot for applying updates (e.g., midnight)
- Emergency force-update capability for critical fixes

### Connection Security
- BLE bonding/pairing with PIN (if required by platform)
- Whitelist enforcement in stealth mode
- Optional encryption layer (BLE already provides link-layer encryption)
- Rate limiting for commands
- Connection timeout handling

---

## Testing Checklist

### BLE Connectivity
- [ ] Device advertising visible during pairing window
- [ ] Device invisible after pairing window closes
- [ ] Bonding/pairing works on Android
- [ ] Bonding/pairing works on iOS
- [ ] Whitelisted device can reconnect
- [ ] Non-whitelisted device cannot connect in stealth mode
- [ ] Manual pairing window re-open works

### Command Functionality
- [ ] All standard pulse commands work
- [ ] Configuration read/write works
- [ ] Diagnostics data retrieved correctly
- [ ] Engineer mode enable/disable works
- [ ] Engineer motor commands work (M1/M2, open/close)
- [ ] Engineer commands blocked when mode disabled

### Status Updates
- [ ] Status notifications received at 1Hz
- [ ] All status fields accurate
- [ ] Flag states correct
- [ ] Limit switch states reflected

### Performance
- [ ] Command latency < 100ms
- [ ] Status update latency < 200ms
- [ ] No dropped notifications
- [ ] Stable connection over 30 minutes
- [ ] Reconnection after disconnect < 5s

### Safety
- [ ] Engineer mode requires explicit enable
- [ ] Engineer mode shows clear warnings
- [ ] Engineer commands are hold-to-run (no latching)
- [ ] Standard commands cannot activate during engineer mode
- [ ] Motors stop when engineer command released

---

## Troubleshooting

### Issue: Can't find device during scan
- Check pairing window is active (30s after unexpected boot)
- Verify Bluetooth is enabled on Pi: `sudo hciconfig hci0 up`
- Check advertising: `sudo hcitool lescan`
- Restart BLE service: `sudo systemctl restart gatetorio-ble`

### Issue: Connection fails immediately
- Check whitelist mode - might need to re-enter pairing window
- Verify device is bonded: `bluetoothctl devices`
- Check logs: `journalctl -u gatetorio-ble -f`

### Issue: Commands not executing
- Verify characteristic write permissions
- Check command JSON format
- Review command handler logs
- Test via web UI first to isolate BLE issue

### Issue: Status updates not received
- Check notification subscription
- Verify 1Hz update loop running
- Check MTU size (need >300 bytes for status)
- Try polling (read) instead of notifications

### Issue: Engineer mode not working
- Verify engineer_mode_enabled flag set
- Check motor manager processing engineer flags
- Test individual motor control via Python first
- Review motor manager logs for errors

---

## Performance Notes

### BLE Throughput
- Typical BLE throughput: 5-10 KB/s
- JSON command size: ~50 bytes
- JSON status size: ~300 bytes
- More than sufficient for 1Hz status + occasional commands

### Latency
- BLE connection interval: 7.5-4000ms (negotiable)
- Target: 20ms interval for low latency
- Expected command latency: 50-100ms
- Status update period: 1000ms (1Hz)

### Battery Impact (Mobile)
- BLE is low power by design
- Connection: ~1-5mA
- Notifications: Minimal overhead
- App should last full day with active connection
- iOS: Optimize for "energy-efficient" priority

---

## References

### BLE Resources
- [Bluezero Documentation](https://ukbaz.github.io/bluezero/)
- [Flutter Blue Plus](https://pub.dev/packages/flutter_blue_plus)
- [BLE GATT Specifications](https://www.bluetooth.com/specifications/gatt/)

### Gatetorio Resources
- `gate_controller_v2.py` - Main control logic
- `motor_manager.py` - Motor control and PWM
- `input_manager.py` - ADC input sampling
- `webui.py` - FastAPI REST endpoints

### Development Tools
- **nRF Connect** (Android/iOS) - BLE testing
- **LightBlue** (iOS) - BLE explorer
- **Wireshark** - BLE packet capture
- **bluetoothctl** - Linux Bluetooth CLI

---

## License & Support

This BLE implementation is part of the Gatetorio project.

For issues or questions:
1. Check this guide and troubleshooting section
2. Review code comments in `bluetooth_bridge_ble.py`
3. Test with generic BLE apps before debugging app-specific issues
4. Use web UI to isolate controller vs BLE issues

---

*Last Updated: 2025-11-13*
*Version: 1.0.0*
