# Gatetorio Gate States - Complete Reference

The gate controller uses **14 different states**. The Flutter app must handle ALL of these states to correctly display the gate status.

## Current Issue

**Problem:** App receives `"state": "CLOSED"` but displays as `GateState.unknown`
**Cause:** App doesn't recognize the "CLOSED" state string
**Fix:** Update Flutter app's state parser to handle all 14 states below

## All Gate States

### Primary States (User-Visible)

1. **`CLOSED`** - Gate is fully closed
   - Both motors at close limit positions
   - Motors stopped

2. **`OPEN`** - Gate is fully open
   - Both motors at open limit positions
   - Motors stopped
   - May trigger auto-close countdown

3. **`PARTIAL_1`** - Gate at partial open position 1
   - M1 at configured partial position
   - M2 fully closed
   - Motors stopped

4. **`PARTIAL_2`** - Gate at partial open position 2
   - M1 at configured partial position
   - M2 fully closed
   - Motors stopped

5. **`STOPPED`** - Gate stopped mid-movement
   - User pressed STOP command
   - Neither at limit nor at partial position
   - Motors stopped

6. **`UNKNOWN`** - Position unknown (power-on state)
   - Controller doesn't know where gate is
   - Requires limit hunt or manual positioning
   - Motors stopped

### Movement States

7. **`OPENING`** - Gate is opening to full open
   - Motors running in open direction
   - Not at open limit yet

8. **`CLOSING`** - Gate is closing to full closed
   - Motors running in close direction
   - Not at close limit yet

9. **`OPENING_TO_PARTIAL_1`** - Moving to partial position 1
   - Opening from closed/partial_2
   - Target: partial_1 position

10. **`OPENING_TO_PARTIAL_2`** - Moving to partial position 2
    - Opening from closed/partial_1
    - Target: partial_2 position

11. **`CLOSING_TO_PARTIAL_1`** - Closing to partial position 1
    - Closing from open/partial_2
    - Target: partial_1 position

12. **`CLOSING_TO_PARTIAL_2`** - Closing to partial position 2
    - Closing from open/partial_1
    - Target: partial_2 position

### Safety States

13. **`REVERSING_FROM_OPEN`** - Reversing after safety edge triggered while opening
    - Safety photocell/edge detected obstacle during opening
    - Gate automatically closing to clear obstacle
    - Will stop when clear or at close limit

14. **`REVERSING_FROM_CLOSE`** - Reversing after safety edge triggered while closing
    - Safety photocell/edge detected obstacle during closing
    - Gate automatically opening to clear obstacle
    - Will stop when clear or at open limit

## State Flow Examples

### Normal Open/Close Cycle
```
CLOSED → (open cmd) → OPENING → (limit reached) → OPEN
OPEN → (close cmd) → CLOSING → (limit reached) → CLOSED
```

### Partial Position
```
CLOSED → (partial 1 cmd) → OPENING_TO_PARTIAL_1 → PARTIAL_1
PARTIAL_1 → (close cmd) → CLOSING → CLOSED
```

### Safety Reversal
```
OPENING → (obstacle detected) → REVERSING_FROM_OPEN → CLOSED
CLOSING → (obstacle detected) → REVERSING_FROM_CLOSE → OPEN
```

### Stop Mid-Movement
```
OPENING → (stop cmd) → STOPPED
STOPPED → (open cmd) → OPENING
STOPPED → (close cmd) → CLOSING
```

## JSON Format (from BLE Status Characteristic)

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

## Flutter App Implementation

Your app's GateState enum should include:

```dart
enum GateState {
  closed,           // "CLOSED"
  open,             // "OPEN"
  partial1,         // "PARTIAL_1"
  partial2,         // "PARTIAL_2"
  stopped,          // "STOPPED"
  unknown,          // "UNKNOWN"
  opening,          // "OPENING"
  closing,          // "CLOSING"
  openingToPartial1,   // "OPENING_TO_PARTIAL_1"
  openingToPartial2,   // "OPENING_TO_PARTIAL_2"
  closingToPartial1,   // "CLOSING_TO_PARTIAL_1"
  closingToPartial2,   // "CLOSING_TO_PARTIAL_2"
  reversingFromOpen,   // "REVERSING_FROM_OPEN"
  reversingFromClose,  // "REVERSING_FROM_CLOSE"
}
```

### State Parser Example

```dart
GateState parseState(String stateStr) {
  switch (stateStr) {
    case 'CLOSED':
      return GateState.closed;
    case 'OPEN':
      return GateState.open;
    case 'PARTIAL_1':
      return GateState.partial1;
    case 'PARTIAL_2':
      return GateState.partial2;
    case 'STOPPED':
      return GateState.stopped;
    case 'UNKNOWN':
      return GateState.unknown;
    case 'OPENING':
      return GateState.opening;
    case 'CLOSING':
      return GateState.closing;
    case 'OPENING_TO_PARTIAL_1':
      return GateState.openingToPartial1;
    case 'OPENING_TO_PARTIAL_2':
      return GateState.openingToPartial2;
    case 'CLOSING_TO_PARTIAL_1':
      return GateState.closingToPartial1;
    case 'CLOSING_TO_PARTIAL_2':
      return GateState.closingToPartial2;
    case 'REVERSING_FROM_OPEN':
      return GateState.reversingFromOpen;
    case 'REVERSING_FROM_CLOSE':
      return GateState.reversingFromClose;
    default:
      print('Unknown state: $stateStr');
      return GateState.unknown;
  }
}
```

## UI Display Recommendations

### Simplified Display
Most users don't need to see all 14 states. Consider grouping:

- **Opening**: `OPENING`, `OPENING_TO_PARTIAL_1`, `OPENING_TO_PARTIAL_2`, `REVERSING_FROM_CLOSE`
- **Closing**: `CLOSING`, `CLOSING_TO_PARTIAL_1`, `CLOSING_TO_PARTIAL_2`, `REVERSING_FROM_OPEN`
- **Stopped**: `STOPPED`, `UNKNOWN`
- **Open**: `OPEN`
- **Closed**: `CLOSED`
- **Partial**: `PARTIAL_1`, `PARTIAL_2`

### Detailed Display (Engineer Mode)
Show exact state for troubleshooting:
- Full state name
- Motor positions (m1_percent, m2_percent)
- Motor speeds (m1_speed, m2_speed)
- Auto-close countdown if active

## Testing States

To test each state on the Pi:

```bash
# CLOSED (default startup with limit switches)
# OPEN (send open command, wait for completion)
# OPENING (send open command, check immediately)
# CLOSING (send close command, check immediately)
# STOPPED (send open, then stop mid-movement)
# PARTIAL_1 (send partial 1 command)
# PARTIAL_2 (send partial 2 command)
```

Safety reversal states require triggering photocells/safety edges.
