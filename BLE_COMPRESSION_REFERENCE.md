# BLE Data Compression Reference

This document describes all data compression formats used in the BLE bridge for the Gatetorio gate controller.

**Critical Constraint**: BLE characteristic read buffer is limited to **~186 bytes**

---

## Input Function Codes

Maps input function names to numeric codes for compression.

```
0  = None (no function assigned)
1  = close_limit_m1
2  = open_limit_m1
3  = close_limit_m2
4  = open_limit_m2
5  = cmd_open
6  = cmd_close
7  = cmd_stop
8  = safety_stop_opening
9  = safety_stop_closing
10 = partial_1
11 = partial_2
```

---

## Input Type Codes

Maps input type names to numeric codes.

```
1 = NC   (Normally Closed)
2 = NO   (Normally Open)
3 = 8K2  (8.2k ohm safety edge resistor)
```

---

## Input Config Characteristic (0x2003)

**UUID**: `0000003-0000-1000-8000-00805f9b34fb`

### READ Format
Returns **all** inputs as array of arrays:
```json
[
  ["IN1", 1, 1, 0],
  ["IN2", 2, 1, 1],
  ["IN3", 5, 2, 2],
  ...
]
```

Each entry: `[name, function_code, type_code, channel]`
- `name` (string): Input name (e.g., "IN1", "IN2")
- `function_code` (int): 0-11 from Input Function Codes table
- `type_code` (int): 1=NC, 2=NO, 3=8K2
- `channel` (int): ADC channel number (0-7)

**Size**: ~113 bytes for 8 inputs

### WRITE Format
Write **single** input entry:
```json
["IN1", 5, 2, 0]
```

Format: `[name, function_code, type_code, channel]`

This updates only the specified input in `input_config.json` on the Pi.

---

## Config Data Characteristic (0x2001)

**UUID**: `00002001-0000-1000-8000-00805f9b34fb`

### Format (READ/WRITE)
Array of **26 values** in fixed order:

```json
[
  12.0,    // 0:  run_time
  5.0,     // 1:  pause_time
  100.0,   // 2:  m1_speed_close
  100.0,   // 3:  m1_speed_open
  100.0,   // 4:  m2_speed_close
  100.0,   // 5:  m2_speed_open
  50.0,    // 6:  m1_accel_close
  50.0,    // 7:  m1_accel_open
  50.0,    // 8:  m2_accel_close
  50.0,    // 9:  m2_accel_open
  50.0,    // 10: m1_decel_close
  50.0,    // 11: m1_decel_open
  50.0,    // 12: m2_decel_close
  50.0,    // 13: m2_decel_open
  50.0,    // 14: partial_1_open_percent
  75.0,    // 15: partial_2_open_percent
  30.0,    // 16: auto_close_delay
  0.0,     // 17: m1_start_delay
  0.0,     // 18: m2_start_delay
  0.0,     // 19: m1_stop_delay
  0.0,     // 20: m2_stop_delay
  0,       // 21: use_auto_close (0=false, 1=true)
  0,       // 22: use_partial_open (0=false, 1=true)
  0,       // 23: use_dual_motor (0=false, 1=true)
  0,       // 24: invert_m1 (0=false, 1=true)
  0        // 25: invert_m2 (0=false, 1=true)
]
```

**Notes**:
- Floats rounded to 2 decimal places
- Booleans encoded as 0 (false) or 1 (true)
- **Size**: 71 bytes

---

## Input States Characteristic (0x3001)

**UUID**: `00003001-0000-1000-8000-00805f9b34fb`

### Format (READ only)
Mixed format depending on input type:

```json
{
  "IN1": 1,              // NC/NO inputs: boolean (0=inactive, 1=active)
  "IN2": 0,
  "IN3": [1, 8.25],      // 8K2 inputs: [active, voltage]
  "IN4": 1,
  "IN5": [0, 0.15],
  ...
}
```

**For NC/NO inputs**: Single integer (0 or 1)
**For 8K2 inputs**: Array `[active, voltage]`
- `active` (int): 0 or 1
- `voltage` (float): Voltage reading rounded to 2 decimals

---

## Status Characteristic (0x1001)

**UUID**: `00001001-0000-1000-8000-00805f9b34fb`

### Format (READ only, updates every 200ms)
```json
{
  "state": "IDLE",           // Gate state string
  "m1_percent": 0,           // Motor 1 position (0-100)
  "m2_percent": 0,           // Motor 2 position (0-100)
  "auto_learn_active": false // Auto-learn status
}
```

---

## Command TX Characteristic (0x1002)

**UUID**: `00001002-0000-1000-8000-00805f9b34fb`

### Format (WRITE only)
Send commands as JSON:

```json
{
  "cmd": "pulse",
  "key": "cmd_open"
}
```

Common commands:
- `pulse`: Send pulse command (cmd_open, cmd_close, cmd_stop, partial_1, partial_2)
- `engineer_pulse`: Direct motor control (motor1_open, motor1_close, motor2_open, motor2_close)
- `enable_engineer_mode`: Enable/disable engineer mode (`"value": true/false`)
- `start_auto_learn`: Start auto-learn (requires engineer mode)
- `stop_auto_learn`: Stop auto-learn
- `get_auto_learn_status`: Get auto-learn status
- `save_learned_times`: Save learned times to config
- `reboot`: Reboot the system

---

## Command RX Characteristic (0x1003)

**UUID**: `00001003-0000-1000-8000-00805f9b34fb`

### Format (READ only)
Response from commands:

```json
{
  "success": true,
  "message": "Command executed"
}
```

Or with data:
```json
{
  "success": true,
  "data": {
    "active": true,
    "direction": "OPENING",
    "start_time": 1234567890.5
  }
}
```

---

## Share Key Characteristic (0x4004)

**UUID**: `00004004-0000-1000-8000-00805f9b34fb`

### READ Format
Generate a new one-time use share key for the connected device:
```json
{
  "share_key": "A7B3C9D2",
  "valid_until": "one-time use"
}
```

- User reads this characteristic to get a shareable key
- Key is 8 characters (alphanumeric, uppercase)
- Key is valid for one-time use only
- User can share this key with another person to grant them access

### WRITE Format
Redeem a share key to join the whitelist:
```json
{
  "share_key": "A7B3C9D2"
}
```

When a valid, unused share key is written:
- Device is added to the whitelist
- Key is marked as used (cannot be reused)
- Device gains permanent access to the gate controller

**Use Case**: User A connects during pairing window, gets whitelisted. User A reads share key and sends "A7B3C9D2" to User B. User B writes this key to join whitelist without needing pairing window.

---

## Stealth Mode Security

**Pairing Window**: 30 seconds after unexpected boot (power loss)
- During window: All devices can connect and are added to whitelist
- After window: Only whitelisted devices can connect
- Advertisement stops after 30s (becomes invisible)

**Expected Boot** (reboot command via app): No pairing window, enters stealth mode immediately

**Whitelist**: Stored in `/home/doowkcol/Gatetorio_Code/ble_whitelist.json`

**Share Keys**: Stored in `/home/doowkcol/Gatetorio_Code/ble_share_keys.json`

---

## Summary

| Characteristic | UUID   | Access | Size    | Format |
|---------------|--------|--------|---------|--------|
| Status        | 0x1001 | Read   | ~80 bytes | JSON object |
| Command TX    | 0x1002 | Write  | Variable | JSON command |
| Command RX    | 0x1003 | Read   | Variable | JSON response |
| Config Data   | 0x2001 | R/W    | 71 bytes | 26-element array |
| Input Config  | 0x2003 | R/W    | 113 bytes (read) | Array of arrays (read), single array (write) |
| Input States  | 0x3001 | Read   | ~93 bytes | JSON object (mixed types) |
| Share Key     | 0x4004 | R/W    | ~50 bytes | JSON object |

All characteristics use **JSON encoding** and **UTF-8** text transmission.
