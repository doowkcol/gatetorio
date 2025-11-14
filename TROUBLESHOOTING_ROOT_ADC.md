# Troubleshooting: BLE Server "Spazzing" When Running as Root

## Problem Description

When running the BLE server with `sudo python3 ble_server_bluezero.py`, the terminal gets flooded with rapid state changes and the gate controller behaves erratically ("spazzing"). This happens even when no other controller instances are running.

## Root Cause

The **input_manager process** starts immediately when the controller initializes, but the **ADC (MCP3008) readings need time to stabilize**. When running as root, the timing is different than when running as a regular user, causing:

1. Input manager samples ADC before readings are stable
2. Safety photocells read garbage values
3. Safety system engages constantly
4. Gate state machine cycles rapidly
5. Terminal floods with debug output

## Solution

The BLE server now has a **multi-step startup sequence** that waits for hardware to stabilize:

### Step 1: Pull Latest Code

```bash
cd /home/doowkcol/Gatetorio_Code
git pull
```

### Step 2: Run Hardware Diagnostic (NEW)

Before starting the BLE server, verify hardware is accessible:

```bash
sudo python3 test_hardware_root.py
```

**Expected output:**
```
============================================================
Hardware Diagnostic Tool (Root Access Test)
============================================================

✓ Running as root

[1/6] Checking device files...
  ✓ /dev/gpiomem exists
  ✓ /dev/spidev0.0 exists
  ✓ /dev/spidev0.1 exists

[2/6] Testing library imports...
  ✓ board imported
  ✓ busio imported
  ✓ digitalio imported
  ✓ adafruit_mcp3xxx imported

[3/6] Initializing SPI bus...
  ✓ SPI bus initialized

[4/6] Initializing MCP3008 ADC...
  ✓ MCP3008 ADC initialized

[5/6] Reading ADC channels (10 samples)...
  Ch0   Ch1   Ch2   Ch3   Ch4   Ch5   Ch6   Ch7
  -------------------------------------------------------
  12.3%  45.6%  78.9%  10.2%  55.4%  33.1%  88.7%  22.5%
  ... (10 samples)

[6/6] Analyzing readings...
  ✓ Channel 0: OK (value=8192, voltage=1.65V)
  ✓ Channel 1: OK (value=29852, voltage=2.45V)
  ... (all channels)

Diagnostic Complete
```

**If diagnostic fails:**
- Check SPI permissions: `ls -la /dev/spidev*`
- Add root to SPI group: `sudo usermod -aG spi,gpio root`
- Reboot: `sudo reboot`

### Step 3: Start BLE Server

```bash
sudo python3 ble_server_bluezero.py
```

**Expected output (new multi-step startup):**
```
[Main] Initializing Gatetorio gate controller...
[Main] WARNING: Make sure no other controller instance is running!
[Main] Close the desktop launcher before starting BLE server.

[Main] Step 1: Waiting for hardware initialization...
[Main] Step 2: Creating controller instance...
Gate Controller V2 initialized
[Main] Step 3: Waiting for input manager to stabilize (5 seconds)...
[Main]   This allows ADC readings to settle before safety checks
[Main] Step 4: Verifying input readings...
[Main]   ✓ Inputs stable - safety system nominal
[Main] ✓ Controller initialized and stable

[BLE] Initialized - Hardware ID: 98697DF6
[BLE] Opening pairing window for 30 seconds...
[BLE] Ready for connections!
```

**If still spazzing:**

The BLE server will now detect this and fail early:
```
[Main] Step 4: Verifying input readings...
[Main]   ⚠ Safety triggered (1/3) - waiting...
[Main]   ⚠ Safety triggered (2/3) - waiting...
[Main]   ⚠ Safety triggered (3/3) - waiting...
[Main] ERROR: Safety system constantly triggered!
[Main] This indicates ADC/input readings are invalid.
[Main] Run diagnostic: sudo python3 test_hardware_root.py
```

---

## Common Issues & Fixes

### Issue 1: "No Bluetooth adapter found"

**Error:**
```
[BLE] Error: 'generator' object is not subscriptable
```

**Fixed in latest code.** Pull updates and try again.

### Issue 2: SPI Permission Denied

**Error:**
```
[3/6] Initializing SPI bus...
  ✗ SPI initialization failed: PermissionError
```

**Fix:**
```bash
# Add root to SPI group
sudo usermod -aG spi root
sudo usermod -aG gpio root

# Verify
groups root

# Reboot
sudo reboot
```

### Issue 3: ADC Not Found / Wiring Issue

**Error:**
```
[4/6] Initializing MCP3008 ADC...
  ✗ ADC initialization failed: RuntimeError
```

**Fix:**
- Check MCP3008 wiring
- Verify SPI connections (MOSI, MISO, SCLK, CE0)
- Test with user account first: `python3 test_hardware_root.py` (without sudo)

### Issue 4: ADC Readings All Zeros or Max

**Symptom:**
```
Channel 0: ⚠ Possible issue (value=0, voltage=0.00V)
Channel 1: ⚠ Possible issue (value=65535, voltage=3.30V)
```

**Causes:**
- Disconnected inputs
- Bad wiring
- ADC not getting power
- Wrong chip select pin

**Fix:**
- Verify 3.3V power to MCP3008
- Check ground connection
- Test each input with known voltage (e.g., 3.3V rail)

### Issue 5: Still Spazzing After All Checks Pass

**Last resort fixes:**

1. **Increase stabilization time:**
   Edit `ble_server_bluezero.py` line 794:
   ```python
   time.sleep(10)  # Increase from 5 to 10 seconds
   ```

2. **Disable safety temporarily (TESTING ONLY):**
   This is NOT recommended for production, but can help diagnose:
   ```python
   # In gate_controller_v2.py, comment out safety checks
   # OR set thresholds very high in input_config.json
   ```

3. **Run as user instead of root (if possible):**
   Not feasible for BLE server (needs root for Bluetooth), but helps diagnose.

---

## Technical Details

### Why It Happens Differently for Root vs User

**User context** (desktop launcher):
- Systemd or manual start
- Environment already initialized
- Hardware accessed in established session
- Timing more predictable

**Root context** (BLE server with sudo):
- Fresh environment
- Different library initialization order
- Potentially different SPI clock speed
- Hardware might not be "warm" yet

### The 5-Second Wait Explained

The BLE server now waits **5 seconds** after creating the controller instance before starting the BLE GATT server. This allows:

1. **SPI bus to stabilize** (chip select, clock lines)
2. **MCP3008 ADC to complete power-on reset** (~1-2ms typically, but we're generous)
3. **Input manager to take several samples** (runs at 100Hz, so 500 samples in 5 seconds)
4. **Photocell readings to settle** (ambient light, analog circuit settling time)
5. **Safety thresholds to calibrate** (based on first valid readings)

### Safety System Behavior

The safety system uses photocells on ADC channels:
- **Opening photocell**: Stops gate if beam is broken during opening
- **Closing photocell**: Stops gate if beam is broken during closing

If ADC reads **garbage** (0x0000 or 0xFFFF):
- Photocell appears "blocked" or "open circuit"
- Safety engages: `stop_opening_active=True`
- Gate state machine: "Someone is in the way!"
- Gate tries to reverse
- Loop repeats rapidly → spazzing

---

## Prevention for Production

Once testing is complete, run BLE server as a systemd service:

```bash
# Install service
sudo cp systemd/gatetorio-ble.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gatetorio-ble

# Start and monitor
sudo systemctl start gatetorio-ble
sudo systemctl status gatetorio-ble

# View logs
journalctl -u gatetorio-ble -f
```

The systemd service:
- Starts after Bluetooth is ready (`After=bluetooth.target`)
- Waits for hardware initialization
- Auto-restarts on failure
- Logs to journald (no terminal spam)

---

## Summary

**Problem:** BLE server spazzes when run as root due to ADC initialization timing

**Solution:**
1. Run hardware diagnostic: `sudo python3 test_hardware_root.py`
2. Fix any permission/wiring issues
3. Run BLE server: `sudo python3 ble_server_bluezero.py`
4. BLE server now waits for ADC to stabilize before proceeding

**If still issues:** Check logs, increase delays, verify wiring

---

**Status:** Fixed in commit 633a1fc
**Last Updated:** 2025-11-14
