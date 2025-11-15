#!/usr/bin/env python3
"""
Hardware Diagnostic Tool - Test GPIO/ADC as root

This script tests whether the ADC and GPIO hardware can be accessed
properly when running as root (needed for BLE server).

Run with: sudo python3 test_hardware_root.py
"""

import sys
import time

print("=" * 60)
print("Hardware Diagnostic Tool (Root Access Test)")
print("=" * 60)
print()

# Check if running as root
import os
if os.geteuid() != 0:
    print("ERROR: This script must be run as root (sudo)")
    print("Usage: sudo python3 test_hardware_root.py")
    sys.exit(1)

print("✓ Running as root")
print()

# Test 1: Check device files
print("[1/6] Checking device files...")
devices = ['/dev/gpiomem', '/dev/spidev0.0', '/dev/spidev0.1']
for dev in devices:
    if os.path.exists(dev):
        stat = os.stat(dev)
        print(f"  ✓ {dev} exists (mode: {oct(stat.st_mode)})")
    else:
        print(f"  ✗ {dev} NOT FOUND")

print()

# Test 2: Import libraries
print("[2/6] Testing library imports...")
try:
    import board
    print("  ✓ board imported")
except ImportError as e:
    print(f"  ✗ board import failed: {e}")
    sys.exit(1)

try:
    import busio
    print("  ✓ busio imported")
except ImportError as e:
    print(f"  ✗ busio import failed: {e}")
    sys.exit(1)

try:
    import digitalio
    print("  ✓ digitalio imported")
except ImportError as e:
    print(f"  ✗ digitalio import failed: {e}")
    sys.exit(1)

try:
    import adafruit_mcp3xxx.mcp3008 as MCP
    from adafruit_mcp3xxx.analog_in import AnalogIn
    print("  ✓ adafruit_mcp3xxx imported")
except ImportError as e:
    print(f"  ✗ adafruit_mcp3xxx import failed: {e}")
    print("  Install with: pip3 install adafruit-circuitpython-mcp3xxx")
    sys.exit(1)

print()

# Test 3: Initialize SPI
print("[3/6] Initializing SPI bus...")
try:
    spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
    print("  ✓ SPI bus initialized")
except Exception as e:
    print(f"  ✗ SPI initialization failed: {e}")
    print("  Check: ls -la /dev/spidev*")
    print("  Try: sudo usermod -aG spi root")
    sys.exit(1)

print()

# Test 4: Initialize ADC
print("[4/6] Initializing MCP3008 ADC...")
try:
    cs = digitalio.DigitalInOut(board.D5)  # Chip select on CE0
    mcp = MCP.MCP3008(spi, cs)
    print("  ✓ MCP3008 ADC initialized")
except Exception as e:
    print(f"  ✗ ADC initialization failed: {e}")
    print("  Check wiring and SPI connection")
    sys.exit(1)

print()

# Test 5: Read ADC channels
print("[5/6] Reading ADC channels (10 samples)...")
channels = []
for i in range(8):
    channels.append(AnalogIn(mcp, getattr(MCP, f'P{i}')))

print("  Ch0   Ch1   Ch2   Ch3   Ch4   Ch5   Ch6   Ch7")
print("  " + "-" * 55)

for sample in range(10):
    values = [ch.value for ch in channels]
    # Convert to human-readable (16-bit to percentage)
    percentages = [f"{(v/65535)*100:5.1f}%" for v in values]
    print("  " + "  ".join(percentages))
    time.sleep(0.2)

print()

# Test 6: Check for invalid readings
print("[6/6] Analyzing readings...")
valid = True
for i, ch in enumerate(channels):
    value = ch.value
    voltage = ch.voltage

    # Check for obviously invalid readings
    if value == 0 or value == 65535:
        print(f"  ⚠ Channel {i}: Possible issue (value={value}, voltage={voltage:.2f}V)")
        print(f"    This might indicate disconnected input or wiring issue")
    elif voltage > 3.5:
        print(f"  ⚠ Channel {i}: High voltage (value={value}, voltage={voltage:.2f}V)")
    else:
        print(f"  ✓ Channel {i}: OK (value={value}, voltage={voltage:.2f}V)")

print()
print("=" * 60)
print("Diagnostic Complete")
print("=" * 60)
print()
print("If all tests passed, the hardware is accessible from root.")
print("If input manager still spazzes, the issue is likely:")
print("  1. Race condition during controller initialization")
print("  2. Input manager starting before ADC is stable")
print("  3. Safety threshold configuration")
print()
print("Next step: Run BLE server with verbose input debugging")
print("  sudo python3 ble_server_bluezero.py")
