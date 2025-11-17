# Gatetorio Flutter App

A Flutter mobile application for controlling the Gatetorio gate system via Bluetooth Low Energy (BLE).

## Features

- **BLE Device Scanning**: Automatically finds Gatetorio gate controllers nearby
- **Real-time Status**: Displays live gate position, speed, and state updates at 1Hz
- **Gate Control**: Open, Close, and Stop commands with single tap
- **Partial Open**: Support for partial open positions (Partial 1, Partial 2)
- **Step Logic**: Cycle through gate states
- **Visual Feedback**: Progress bars showing motor positions and speeds
- **Auto-close Countdown**: Displays countdown when auto-close is active
- **Connection Management**: Easy connect/disconnect with status indicators

## Getting Started

### Prerequisites

- Flutter SDK (3.10.0 or higher)
- Android Studio or VS Code with Flutter extensions
- Android device or emulator
- Gatetorio BLE server running on Raspberry Pi

### Installation

1. Install dependencies:
   ```bash
   cd gatetorio_app
   flutter pub get
   ```

2. Verify BLE permissions in `android/app/src/main/AndroidManifest.xml` (already configured)

3. Connect your Android device or start an emulator

4. Run the app:
   ```bash
   flutter run
   ```

### First-Time Setup

1. Make sure the Gatetorio BLE server is running on your Raspberry Pi
2. Ensure Bluetooth is enabled on your mobile device
3. Grant Bluetooth and location permissions when prompted
4. The app will start in scanning mode

## Usage

### Connecting to Your Gate

1. Tap **"Start Scanning"** on the home screen
2. Wait for your Gatetorio device to appear (named "Gatetorio-XXXX")
3. Tap **"Connect"** on the device card
4. Wait for connection confirmation

### Controlling the Gate

Once connected, you'll see:

- **Status Card**: Shows current gate state (Idle, Opening, Closing, etc.)
- **Control Buttons**:
  - **OPEN** (Green): Opens the gate
  - **STOP** (Orange): Stops gate movement
  - **CLOSE** (Red): Closes the gate
- **Position Indicators**: Real-time motor positions and speeds
- **Additional Controls**: Partial open and step logic buttons

### Disconnecting

Tap the Bluetooth disconnect icon in the top-right corner to disconnect from the gate.

## Architecture

```
Flutter App (BLE Client)
    ↕ BLE GATT Protocol
Python BLE Server (ble_server_bluezero.py)
    ↕ API Calls
GateController → MotorManager → Hardware
```

### GATT Communication

- **Service UUID**: `00001000-4751-5445-5254-494F00000000`
- **Command TX**: `00001001-4751-5445-5254-494F00000000` (Write)
- **Command Response**: `00001002-4751-5445-5254-494F00000000` (Read)
- **Status**: `00001003-4751-5445-5254-494F00000000` (Read + Notify @ 1Hz)

### Command Format

Commands are sent as JSON:
```json
{
  "cmd": "pulse",
  "key": "cmd_open",
  "timestamp": 1699999999
}
```

### Status Format

Status notifications received as JSON:
```json
{
  "state": "OPENING",
  "m1_percent": 45,
  "m2_percent": 42,
  "m1_speed": 85,
  "m2_speed": 82,
  "auto_close_countdown": 0,
  "timestamp": 1699999999
}
```

## Project Structure

```
lib/
├── main.dart                    # App entry point with Provider setup
├── models/
│   ├── gate_status.dart         # Gate status data model
│   ├── gate_command.dart        # Command data model
│   └── ble_device_info.dart     # BLE device info model
├── services/
│   └── ble_service.dart         # BLE communication service
├── screens/
│   └── home_screen.dart         # Main app screen
└── widgets/
    ├── connection_status.dart   # Connection status banner
    ├── device_scanner.dart      # Device scanning UI
    └── gate_controller.dart     # Gate control interface
```

## Dependencies

- **flutter_blue_plus** (^1.32.12): BLE communication
- **provider** (^6.1.2): State management
- **permission_handler** (^11.3.1): Runtime permissions

## Troubleshooting

### "Bluetooth permissions not granted"
- Ensure location services are enabled (required for BLE scanning on Android)
- Grant all Bluetooth permissions when prompted

### "Device not found"
- Verify the BLE server is running: `sudo systemctl status gatetorio-ble`
- Check that you're within Bluetooth range (typically <10 meters)
- Make sure the device is in pairing mode (30-second window after boot)

### "Connection failed"
- Restart the BLE server: `sudo systemctl restart gatetorio-ble`
- Clear Bluetooth cache on Android (Settings → Apps → Bluetooth → Clear Cache)
- Try rebooting the Raspberry Pi

### Status not updating
- Check that notifications are enabled (should happen automatically)
- Verify BLE server is sending status updates (check logs: `journalctl -u gatetorio-ble -f`)

## Testing

### With Real Hardware
1. Ensure BLE server is running on Raspberry Pi
2. Connect app to gate controller
3. Test all commands (Open, Close, Stop)
4. Verify real-time status updates

### With BLE Simulator
Use nRF Connect or LightBlue to simulate the Gatetorio BLE server:
1. Create GATT service with UUID `00001000-4751-5445-5254-494F00000000`
2. Add characteristics for Command TX, Command Response, and Status
3. Enable notifications on Status characteristic
4. Send test JSON status updates

## Security Notes

- The app communicates locally via BLE only (no internet connection)
- All commands require active BLE connection
- BLE server has whitelist protection (only bonded devices can connect)
- Engineer mode commands are NOT exposed in this UI (safety feature)

## Future Enhancements

Potential improvements:
- [ ] Settings screen for app configuration
- [ ] Command history and logging
- [ ] Engineer mode toggle (with warning)
- [ ] Custom partial open positions
- [ ] Multi-device support
- [ ] Dark mode theme toggle

## Support

For issues or questions:
- Check BLE server logs: `journalctl -u gatetorio-ble -f`
- Review BLE_TESTING_GUIDE.md in the main project
- Check BLE_TROUBLESHOOTING.md for common issues

## License

Part of the Gatetorio gate control system project.
