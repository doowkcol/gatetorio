# Gatetorio BLE App Development Reference

Quick reference for building the Flutter app. Everything you need to communicate with the Pi BLE server.

## BLE Connection

**Device Name:** `Gatetorio-7DF6` (last 4 chars of hardware ID)

**Service UUIDs:**
```
Gate Control (PRIMARY):    00001000-4751-5445-5254-494F00000000
Device Info (secondary):   0000180A-0000-1000-8000-00805F9B34FB
Configuration (secondary): 00002000-4751-5445-5254-494F00000000
Diagnostics (secondary):   00003000-4751-5445-5254-494F00000000
Security (secondary):      00004000-4751-5445-5254-494F00000000
```

**Key Characteristics:**
```
Command TX:       00001001-4751-5445-5254-494F00000000  [WRITE]
Command Response: 00001002-4751-5445-5254-494F00000000  [READ]
Status:           00001003-4751-5445-5254-494F00000000  [READ, NOTIFY]
Input Config:     00002003-4751-5445-5254-494F00000000  [READ]
Input States:     00003001-4751-5445-5254-494F00000000  [READ]
```

## Sending Commands

**Write JSON to Command TX characteristic:**

```json
{"cmd": "pulse", "key": "cmd_open"}      // Open gate
{"cmd": "pulse", "key": "cmd_close"}     // Close gate
{"cmd": "pulse", "key": "cmd_stop"}      // Stop gate
{"cmd": "pulse", "key": "partial_1"}     // Go to partial position 1
{"cmd": "pulse", "key": "partial_2"}     // Go to partial position 2
```

**Response (read from Command Response):**
```json
{"success": true, "message": "Pulse sent: cmd_open"}
{"success": false, "message": "Error: ..."}
```

## Status Updates (1Hz Notifications)

**Subscribe to Status characteristic** to receive updates every second:

```json
{
  "state": "CLOSED",
  "m1_percent": 0,
  "m2_percent": 0,
  "m1_speed": 0.0,
  "m2_speed": 0.0,
  "auto_close_countdown": 0.0,
  "timestamp": 1763247466
}
```

### Field Details

**`state`** (string) - See GATE_STATES.md for all 14 states. Key ones:
- `"CLOSED"` - Gate closed
- `"OPEN"` - Gate fully open
- `"OPENING"` - Currently opening
- `"CLOSING"` - Currently closing
- `"STOPPED"` - Stopped mid-movement
- `"PARTIAL_1"` / `"PARTIAL_2"` - At partial positions

**`m1_percent`** (int, 0-100) - Motor 1 position as percentage
- `0` = fully closed
- `100` = fully open
- Updates in real-time during movement

**`m2_percent`** (int, 0-100) - Motor 2 position as percentage
- Same scale as M1
- Usually moves with M1 (dual motor gate)

**`m1_speed`** (float, 0.0-1.0) - Motor 1 current speed
- `0.0` = stopped
- `1.0` = full speed
- Shows slowdown when approaching limits

**`m2_speed`** (float, 0.0-1.0) - Motor 2 current speed

**`auto_close_countdown`** (float, seconds) - Auto-close timer
- `0.0` = not active
- `> 0.0` = seconds until auto-close starts
- Only active when `state == "OPEN"`

**`timestamp`** (int) - Unix timestamp of status update

## Motor Position Details

**Travel Time:**
- M1: ~7.8 seconds (close to open)
- M2: ~8.6 seconds (close to open)

**Position Calculation:**
- Position = elapsed time since movement started
- Percent = (current_position / total_travel_time) * 100
- Updates every ~8ms during movement

**Partial Positions:**
- Configurable via config characteristic
- Default: P1 at 50%, P2 at 75%
- M2 fully closes when at partial positions

## Movement Behavior

**Opening:**
```
State: CLOSED → OPENING → OPEN
m1_percent: 0 → 50 → 100 (over ~7.8s)
m1_speed: 0.0 → 1.0 → 0.8 → 0.0 (ramps up, slows down, stops)
```

**Closing:**
```
State: OPEN → CLOSING → CLOSED
m1_percent: 100 → 50 → 0 (over ~7.8s)
m1_speed: 0.0 → 1.0 → 0.8 → 0.0
```

**Auto-Close:**
```
State: OPEN, auto_close_countdown: 5.0 → 4.0 → 3.0 → 2.0 → 1.0 → 0.0
Then: State changes to CLOSING automatically
```

## UI Recommendations

**Position Display:**
- Show `m1_percent` as progress bar or numeric (0-100%)
- Animate smoothly between updates (receiving 1Hz, can interpolate)

**Speed Indicator:**
- `m1_speed > 0` = show motion indicator/animation
- `m1_speed == 0` = static
- Can show slowdown near limits (speed < 1.0 but > 0)

**Auto-Close:**
- Show countdown timer when `auto_close_countdown > 0`
- Format: "Auto-closing in X seconds"
- Tap to cancel = send stop command

**State Colors:**
- CLOSED: Green
- OPEN: Blue
- OPENING/CLOSING: Yellow (animated)
- STOPPED: Orange
- REVERSING_*: Red (safety triggered)

## Connection Tips

**MTU:** Request 185 bytes or less (512 can cause timeouts)

**Connection Parameters:** Let OS handle (no custom intervals needed)

**Notifications:** Must subscribe to Status characteristic to receive updates

**Service Discovery:** Wait for complete discovery before accessing secondary services

## Testing Commands

**Basic Flow:**
```dart
// 1. Connect to device
// 2. Discover services
// 3. Subscribe to Status (00001003-...)
// 4. Send command to Command TX (00001001-...)
// 5. Receive status updates (1 per second)
```

**Example Status While Opening:**
```json
{"state": "OPENING", "m1_percent": 0, "m1_speed": 0.0, ...}   // Just started
{"state": "OPENING", "m1_percent": 12, "m1_speed": 1.0, ...}  // 1 sec later
{"state": "OPENING", "m1_percent": 25, "m1_speed": 1.0, ...}  // 2 sec later
{"state": "OPENING", "m1_percent": 87, "m1_speed": 0.7, ...}  // Near end (slowing)
{"state": "OPEN", "m1_percent": 100, "m1_speed": 0.0, ...}    // Reached limit
```

## Error Handling

**Connection Loss:**
- Status notifications stop
- Reconnect and resubscribe to Status

**Command Fails:**
- Check `success: false` in response
- Common: safety edge blocking command, gate already moving

**Invalid State:**
- Use `"UNKNOWN"` as fallback in state parser
- Log unrecognized states for debugging

## Input Monitoring (NEW)

**Input Config Characteristic (0x2003):**

Returns configuration for all 8 inputs:
```json
{
  "inputs": {
    "IN1": {
      "channel": 0,
      "enabled": true,
      "type": "NC",
      "function": "close_limit_m1",
      "description": "Motor 1 close limit"
    },
    "IN2": {"channel": 1, "type": "NO", "function": "open_limit_m1", ...},
    "IN5": {"channel": 4, "type": "NO", "function": "cmd_open", ...},
    "IN6": {"channel": 5, "type": "8K2", "function": "safety_stop_opening", ...}
  }
}
```

**Input States Characteristic (0x3001):**

Returns current state of all inputs:
```json
{
  "IN1": {"active": true, "function": "close_limit_m1", "type": "NC", "channel": 0},
  "IN2": {"active": false, "function": "open_limit_m1", "type": "NO", "channel": 1},
  "IN5": {"active": false, "function": "cmd_open", "type": "NO", "channel": 4},
  "IN6": {"active": false, "function": "safety_stop_opening", "type": "8K2", "channel": 5}
}
```

**Input Types:**
- `"NO"` - Normally Open (active when voltage present)
- `"NC"` - Normally Closed (active when voltage absent)
- `"8K2"` - 8.2kΩ resistor (safety edge, requires learned resistance)

**Usage:**
1. Read Input Config once on connect to get input definitions
2. Read Input States to get current state (can poll or add notify later)
3. Display inputs with their functions and current active/inactive state

## Quick Reference Card

```
OPEN gate:  {"cmd":"pulse","key":"cmd_open"}
CLOSE gate: {"cmd":"pulse","key":"cmd_close"}
STOP gate:  {"cmd":"pulse","key":"cmd_stop"}

Status arrives every 1 second via notifications
Motor position: m1_percent (0-100)
Motor moving: m1_speed > 0
Auto-close active: auto_close_countdown > 0

Input config: Read 0x2003 once
Input states: Read 0x3001 (poll as needed)
```

That's it! See GATE_STATES.md for complete state details.
