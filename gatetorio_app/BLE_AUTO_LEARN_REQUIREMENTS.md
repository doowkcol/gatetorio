# BLE Auto-Learn Command Requirements

## Overview
The Flutter app now includes a complete Auto-Learn UI with engineer mode controls. However, the BLE bridge server needs to be updated to support the new auto-learn commands.

## Missing BLE Commands

The following commands need to be added to `bluetooth_bridge_ble.py`:

### 1. start_auto_learn
**Command JSON:**
```json
{
  "cmd": "start_auto_learn"
}
```

**Handler Implementation:**
```python
elif cmd_type == 'start_auto_learn':
    return await self._handle_start_auto_learn()
```

**Handler Method:**
```python
async def _handle_start_auto_learn(self) -> Dict:
    """Handle start auto-learn command"""
    if not self.config.engineer_mode_enabled:
        return {"success": False, "message": "Engineer mode not enabled"}

    success = self.controller.start_auto_learn()
    if success:
        return {"success": True, "message": "Auto-learn started"}
    else:
        return {"success": False, "message": "Failed to start auto-learn"}
```

### 2. stop_auto_learn
**Command JSON:**
```json
{
  "cmd": "stop_auto_learn"
}
```

**Handler Implementation:**
```python
elif cmd_type == 'stop_auto_learn':
    return await self._handle_stop_auto_learn()
```

**Handler Method:**
```python
async def _handle_stop_auto_learn(self) -> Dict:
    """Handle stop auto-learn command"""
    self.controller.stop_auto_learn()
    return {"success": True, "message": "Auto-learn stopped"}
```

### 3. get_auto_learn_status
**Command JSON:**
```json
{
  "cmd": "get_auto_learn_status"
}
```

**Handler Implementation:**
```python
elif cmd_type == 'get_auto_learn_status':
    return await self._handle_get_auto_learn_status()
```

**Handler Method:**
```python
async def _handle_get_auto_learn_status(self) -> Dict:
    """Handle get auto-learn status command"""
    status = self.controller.get_auto_learn_status()
    return {
        "success": True,
        "data": status
    }
```

## Flutter App Implementation

The Flutter app has already been updated with:

✅ **gate_command.dart** - Added static getters:
- `GateCommand.startAutoLearn`
- `GateCommand.stopAutoLearn`
- `GateCommand.getAutoLearnStatus`

✅ **settings_screen.dart** - Added UI:
- Engineer mode toggle with red warning frame
- Auto-learn control buttons (Start/Stop)
- Auto-learn status display
- Save learned times button
- Automatic engineer mode disable after saving

## Existing BLE Commands
The following related commands are already implemented:
- ✅ `enable_engineer_mode` - Enable/disable engineer mode
- ✅ `save_learned_times` - Save learned travel times to config

## Testing
Once the BLE bridge is updated:
1. Enable engineer mode via the settings screen
2. Ensure limit switches are enabled for both motors
3. Click "START AUTO-LEARN" button
4. Observe the auto-learn sequence
5. Click "STOP AUTO-LEARN" if needed
6. Click "SAVE LEARNED TIMES" when complete
7. Verify engineer mode is automatically disabled after save

## Priority
**Medium** - The UI is ready but commands will fail until the server is updated. Users can still use the Python UI for auto-learn functionality in the meantime.
