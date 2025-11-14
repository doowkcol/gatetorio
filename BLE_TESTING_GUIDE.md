# Gatetorio BLE Testing Guide

## Overview

This guide provides step-by-step instructions for testing the Gatetorio BLE GATT server using generic BLE mobile apps before developing the custom Flutter app.

---

## Prerequisites

### On Raspberry Pi

1. **Install BLE dependencies** (one-time setup):
   ```bash
   cd /home/doowkcol/Gatetorio_Code
   sudo ./install_ble_dependencies.sh
   ```

2. **Verify Bluetooth is running**:
   ```bash
   sudo systemctl status bluetooth
   sudo hciconfig hci0 up  # If adapter is down
   ```

3. **Check Bluetooth adapter**:
   ```bash
   hciconfig -a
   # Should show: UP RUNNING
   ```

### On Mobile Device

Install one of these BLE testing apps:

**Android:**
- **nRF Connect** (recommended) - Nordic Semiconductor
  - Download: Google Play Store
  - Free, full-featured, industry standard

**iOS:**
- **LightBlue** - Punch Through
  - Download: App Store
  - Free, good for testing

---

## Phase 1: Manual BLE Server Testing

### Step 1: Start the BLE Server

On the Raspberry Pi:

```bash
cd /home/doowkcol/Gatetorio_Code

# Make sure gate controller is NOT already running
# (BLE server will start it internally)

# Run BLE server manually (for testing)
sudo python3 ble_server_bluezero.py
```

**Expected output:**
```
============================================================
Gatetorio BLE Server v1.0.0 (bluezero)
============================================================
Hardware ID: ABCD1234
User ID: gatetorio-default
Stealth mode: True
Whitelist enabled: True
[BLE] Unexpected boot detected
[BLE] Opening pairing window for 30 seconds...
[BLE] Building GATT server...
[BLE] Adding Device Info service...
[BLE] Adding Gate Control service...
[BLE] Adding Configuration service...
[BLE] Adding Diagnostics service...
[BLE] Adding Security service...
[BLE] GATT server built successfully
[BLE] Status update thread started
[BLE] Starting GATT server...
[BLE] Ready for connections!
[BLE] Press Ctrl+C to stop
```

**Note:** You have 30 seconds to connect from this point!

### Step 2: Scan for Device (nRF Connect)

1. Open **nRF Connect** app
2. Tap **SCAN** button (top right)
3. Look for device named: **Gatetorio-XXXX** (last 4 digits of hardware ID)
4. Should appear in "Scanner" list within a few seconds

**Troubleshooting:**
- Not visible? Check the 30-second pairing window hasn't expired
  - Restart the BLE server (`Ctrl+C` then run again)
- Still not visible? Check Bluetooth:
  ```bash
  sudo systemctl restart bluetooth
  sudo hciconfig hci0 up
  ```

### Step 3: Connect to Device

1. In nRF Connect, tap on **Gatetorio-XXXX**
2. Tap **CONNECT** button
3. Wait for connection (2-5 seconds)
4. You should see "Connected" status

**On Pi, you should see:**
```
[BLE] New connection from: XX:XX:XX:XX:XX:XX
```

### Step 4: Explore GATT Services

After connecting, nRF Connect will automatically discover services. You should see:

#### Service 1: Device Information (0000180A-...)
- **Hardware ID** (`00000101-4751...`) - Read
  - Tap **Read** → Should show hardware ID (e.g., "ABCD1234")
- **Software Version** (`00000102-4751...`) - Read
  - Tap **Read** → Should show "1.0.0"
- **User ID** (`00000103-4751...`) - Read/Write
  - Tap **Read** → Should show "gatetorio-default"
  - Tap **Write** → Change to "my-gate-001"

#### Service 2: Gate Control (00001000-4751-...)
- **Command TX** (`00001001-4751...`) - Write
  - This is where you send commands (see below)
- **Command Response** (`00001002-4751...`) - Read
  - Tap **Read** → Shows last command result
- **Status** (`00001003-4751...`) - Read/Notify
  - Tap **Read** → Shows current gate status
  - Enable **Notify** → Get updates every 1 second

#### Service 3: Configuration (00002000-4751-...)
- **Config Data** (`00002001-4751...`) - Read/Write
  - Tap **Read** → See full gate configuration JSON

#### Service 4: Diagnostics (00003000-4751-...)
- **System Status** (`00003001-4751...`) - Read
  - Tap **Read** → See CPU temp, uptime, memory

#### Service 5: Security (00004000-4751-...)
- **Pairing Control** (`00004001-4751...`) - Write
- **Engineer Mode** (`00004003-4751...`) - Read/Write

---

## Phase 2: Command Testing

### Sending Commands via BLE

Commands are sent as **JSON strings** to the **Command TX** characteristic.

#### Test 1: Basic Gate Commands

1. In nRF Connect, find **Gate Control** service → **Command TX** characteristic
2. Tap the **Write** icon (↑ arrow)
3. Select **Text** (or **UTF-8 String**)
4. Enter this JSON:
   ```json
   {"cmd":"pulse","key":"cmd_open"}
   ```
5. Tap **Send**

**Expected result:**
- Gate should start opening
- Pi console shows: `[BLE] Command: pulse cmd_open`
- Read **Command Response** to see: `{"success":true,"message":"Pulse sent: cmd_open"}`

#### Test 2: Monitor Status (Real-time)

1. Find **Status** characteristic (`00001003-4751...`)
2. Tap the **Notify** icon (three vertical dots with lines)
3. Enable notifications
4. Watch status update every second:
   ```json
   {
     "state": "OPENING",
     "m1_percent": 45,
     "m2_percent": 42,
     "m1_speed": 85,
     "m2_speed": 82,
     "auto_close_countdown": 0,
     "timestamp": 1731619200
   }
   ```

#### Test 3: Other Gate Commands

Test each command by writing to **Command TX**:

**Close gate:**
```json
{"cmd":"pulse","key":"cmd_close"}
```

**Stop gate:**
```json
{"cmd":"pulse","key":"cmd_stop"}
```

**Partial open 1:**
```json
{"cmd":"pulse","key":"partial_1"}
```

**Step logic:**
```json
{"cmd":"pulse","key":"step_logic"}
```

#### Test 4: Get Configuration

1. Find **Configuration** service → **Config Data**
2. Tap **Read**
3. Should see full gate configuration JSON (may be large, 500+ bytes)

Example response:
```json
{
  "gate_open_time": 18.0,
  "gate_close_time": 18.0,
  "auto_close_delay": 30,
  "partial_1_percent": 50,
  ...
}
```

#### Test 5: System Diagnostics

1. Find **Diagnostics** service → **System Status**
2. Tap **Read**
3. See system information:
   ```json
   {
     "uptime": 86400,
     "cpu_temp": 45.5,
     "memory_percent": 32.1,
     "ble_connected": true,
     "connection_count": 1
   }
   ```

---

## Phase 3: Engineer Mode Testing

**⚠️ WARNING: Engineer mode bypasses ALL safety systems. Use with extreme caution.**

### Enable Engineer Mode

1. Find **Security** service → **Engineer Mode** characteristic
2. Tap **Write**
3. Select **Byte Array** or **Hex**
4. Write: `31` (hex) or `1` (text) to enable
5. Tap **Send**

**Expected:**
- Pi console shows: `[BLE] Engineer mode enabled`
- Read the characteristic to verify: should return `31` (enabled)

### Test Individual Motor Control

**Open Motor 1:**
```json
{"cmd":"engineer_pulse","key":"motor1_open"}
```

**Close Motor 1:**
```json
{"cmd":"engineer_pulse","key":"motor1_close"}
```

**Open Motor 2:**
```json
{"cmd":"engineer_pulse","key":"motor2_open"}
```

**Close Motor 2:**
```json
{"cmd":"engineer_pulse","key":"motor2_close"}
```

**Important:**
- These commands run motors at **30% speed**
- They **bypass limit switches** and all safety logic
- Motors run **while button/command is held** (for mobile app future)
- Current BLE version sends pulse, not continuous hold

### Disable Engineer Mode

Write `30` (hex) or `0` (text) to Engineer Mode characteristic.

---

## Phase 4: Stealth Mode Testing

### Test Pairing Window Expiration

1. Start BLE server
2. Wait 30 seconds without connecting
3. Run BLE scan on phone
4. **Gatetorio-XXXX should disappear** from scanner

**Expected:**
- Pi console shows: `[BLE] Pairing window closed - entering stealth mode`
- Device no longer visible in scans
- Already-connected devices remain connected

### Test Whitelist (After Pairing)

1. Connect during pairing window
2. Your device MAC is added to whitelist automatically
3. Disconnect
4. Restart BLE server (simulates reboot)
5. Your device can still connect even though pairing window closed

**Verify whitelist:**
```bash
cat /home/doowkcol/Gatetorio_Code/ble_whitelist.json
# Should show your device MAC address
```

### Manually Open Pairing Window

Write to **Pairing Control** characteristic:
```json
{"action":"open_window","duration":30}
```

This reopens the pairing window for 30 more seconds.

---

## Common Issues & Troubleshooting

### Issue: Device not visible in scan

**Causes:**
1. Pairing window expired (30 seconds)
2. Bluetooth adapter not UP
3. BLE server not running

**Solutions:**
```bash
# Check Bluetooth
sudo systemctl status bluetooth
sudo hciconfig hci0 up

# Restart BLE server
sudo python3 ble_server_bluezero.py

# Check for errors in Pi console
```

### Issue: Cannot connect to device

**Causes:**
1. Whitelist enabled but device not whitelisted
2. Bluetooth interference
3. Multiple connections (Pi 3 limit: 3-7 devices)

**Solutions:**
```bash
# Temporarily disable whitelist
# Edit ble_config.json: "whitelist_enabled": false

# Restart BLE server
```

### Issue: Characteristics not readable

**Causes:**
1. Permission issues (wrong flags)
2. BLE server crashed
3. D-Bus/BlueZ issues

**Solutions:**
```bash
# Check BLE server console for errors

# Restart Bluetooth service
sudo systemctl restart bluetooth

# Check BlueZ version (needs 5.48+)
bluetoothctl --version
```

### Issue: Commands not executing

**Causes:**
1. Invalid JSON format
2. Gate controller not running
3. Engineer mode required but not enabled

**Solutions:**
1. Verify JSON syntax (use online validator)
2. Check Pi console for error messages
3. Read **Command Response** characteristic for error details

### Issue: Status notifications not updating

**Causes:**
1. Notifications not enabled on characteristic
2. Status update thread crashed
3. MTU too small (rare)

**Solutions:**
1. Re-enable notifications in nRF Connect
2. Check Pi console for thread errors
3. Restart BLE server

---

## Expected Performance

- **Connection time:** 2-5 seconds
- **Command latency:** 100-300ms (BLE → gate action)
- **Status update rate:** 1Hz (every second)
- **Range:** 10-15m (Pi 3/4), 15-20m (Pi 5)
- **Concurrent connections:** 3-7 devices (Pi 3), 10+ (Pi 5)

---

## Next Steps

Once BLE testing is successful:

1. **Document any issues** encountered
2. **Test all command types** (pulse, engineer, config)
3. **Verify stealth mode** behavior
4. **Test whitelist** functionality
5. **Proceed to Flutter app development** (Phase 2)

---

## LightBlue (iOS) Quick Reference

LightBlue has similar UI to nRF Connect:

1. **Scan** → Shows nearby BLE devices
2. Tap device → **Connect**
3. Tap service → View characteristics
4. Tap characteristic → **Read/Write/Subscribe**
5. For writing:
   - Select **UTF-8 String**
   - Enter JSON command
   - Tap **Write**

---

## Useful Commands Summary

| Action | JSON Command |
|--------|-------------|
| Open gate | `{"cmd":"pulse","key":"cmd_open"}` |
| Close gate | `{"cmd":"pulse","key":"cmd_close"}` |
| Stop gate | `{"cmd":"pulse","key":"cmd_stop"}` |
| Partial 1 | `{"cmd":"pulse","key":"partial_1"}` |
| Get config | `{"cmd":"get_config"}` |
| Get diagnostics | `{"cmd":"get_diagnostics"}` |
| Enable engineer mode | `{"cmd":"enable_engineer_mode","value":true}` |
| Disable engineer mode | `{"cmd":"enable_engineer_mode","value":false}` |
| Motor 1 open (engineer) | `{"cmd":"engineer_pulse","key":"motor1_open"}` |

---

## Safety Notes

- Always test in **manual mode** first (not auto-close)
- Keep **emergency stop** accessible during testing
- **Engineer mode** should only be used for recovery/diagnostics
- Monitor **status notifications** during operation
- Test **limit switches** are working before engineer mode use

---

## For Developers

### Characteristic UUIDs Quick Reference

```
Device Info Service:    0000180A-0000-1000-8000-00805F9B34FB
├─ Hardware ID:         00000101-4751-5445-5254-494F00000000 (Read)
├─ Software Version:    00000102-4751-5445-5254-494F00000000 (Read)
└─ User ID:             00000103-4751-5445-5254-494F00000000 (Read/Write)

Gate Control Service:   00001000-4751-5445-5254-494F00000000
├─ Command TX:          00001001-4751-5445-5254-494F00000000 (Write)
├─ Command Response:    00001002-4751-5445-5254-494F00000000 (Read)
└─ Status:              00001003-4751-5445-5254-494F00000000 (Read/Notify)

Configuration Service:  00002000-4751-5445-5254-494F00000000
└─ Config Data:         00002001-4751-5445-5254-494F00000000 (Read/Write)

Diagnostics Service:    00003000-4751-5445-5254-494F00000000
└─ System Status:       00003001-4751-5445-5254-494F00000000 (Read)

Security Service:       00004000-4751-5445-5254-494F00000000
├─ Pairing Control:     00004001-4751-5445-5254-494F00000000 (Write)
└─ Engineer Mode:       00004003-4751-5445-5254-494F00000000 (Read/Write)
```

---

**Good luck with testing! 🚀**
