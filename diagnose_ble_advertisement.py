#!/usr/bin/env python3
"""
BLE Advertisement Diagnostic Tool

This script tests BLE advertisement registration at a low level
to diagnose why bluezero's Peripheral.publish() is failing.
"""

import sys
import subprocess

print("=" * 60)
print("BLE Advertisement Diagnostic Tool")
print("=" * 60)
print()

# Check if running as root
import os
if os.geteuid() != 0:
    print("ERROR: This script must be run as root (sudo)")
    sys.exit(1)

print("✓ Running as root")
print()

# Test 1: Check BlueZ version
print("[1/8] Checking BlueZ version...")
try:
    result = subprocess.run(['bluetoothctl', '--version'],
                          capture_output=True, text=True, timeout=5)
    version = result.stdout.strip()
    print(f"  BlueZ version: {version}")

    # Parse version number
    if version:
        parts = version.split()
        if len(parts) >= 2:
            ver_num = parts[1]
            major = int(ver_num.split('.')[0])
            minor = int(ver_num.split('.')[1]) if '.' in ver_num else 0

            if major < 5 or (major == 5 and minor < 48):
                print(f"  ⚠ WARNING: BlueZ {ver_num} is old. Recommended: 5.48+")
            else:
                print(f"  ✓ BlueZ {ver_num} is compatible")
except Exception as e:
    print(f"  ✗ Could not check BlueZ version: {e}")

print()

# Test 2: Check bluezero version
print("[2/8] Checking bluezero version...")
try:
    result = subprocess.run(['pip3', 'show', 'bluezero'],
                          capture_output=True, text=True, timeout=5)
    for line in result.stdout.split('\n'):
        if line.startswith('Version:'):
            print(f"  {line}")
            break
    else:
        print("  ✗ bluezero not installed")
except Exception as e:
    print(f"  ✗ Could not check bluezero: {e}")

print()

# Test 3: Check D-Bus
print("[3/8] Checking D-Bus system bus...")
try:
    import dbus
    bus = dbus.SystemBus()
    print("  ✓ D-Bus system bus accessible")
except Exception as e:
    print(f"  ✗ D-Bus error: {e}")

print()

# Test 4: Check bluetoothd is running
print("[4/8] Checking bluetoothd daemon...")
try:
    result = subprocess.run(['systemctl', 'is-active', 'bluetooth'],
                          capture_output=True, text=True)
    if result.stdout.strip() == 'active':
        print("  ✓ bluetoothd is running")
    else:
        print(f"  ✗ bluetoothd status: {result.stdout.strip()}")
except Exception as e:
    print(f"  ✗ Could not check bluetoothd: {e}")

print()

# Test 5: Check Bluetooth adapter via D-Bus
print("[5/8] Checking Bluetooth adapter via D-Bus...")
try:
    import dbus
    bus = dbus.SystemBus()
    manager = dbus.Interface(
        bus.get_object('org.bluez', '/'),
        'org.freedesktop.DBus.ObjectManager'
    )
    objects = manager.GetManagedObjects()

    adapters = []
    for path, interfaces in objects.items():
        if 'org.bluez.Adapter1' in interfaces:
            adapters.append(path)
            props = interfaces['org.bluez.Adapter1']
            print(f"  ✓ Found adapter: {path}")
            print(f"    Address: {props.get('Address', 'unknown')}")
            print(f"    Powered: {props.get('Powered', 'unknown')}")
            print(f"    Discoverable: {props.get('Discoverable', 'unknown')}")

    if not adapters:
        print("  ✗ No Bluetooth adapters found via D-Bus")

except Exception as e:
    print(f"  ✗ D-Bus adapter check failed: {e}")

print()

# Test 6: Check for existing advertisements
print("[6/8] Checking for existing BLE advertisements...")
try:
    import dbus
    bus = dbus.SystemBus()
    manager = dbus.Interface(
        bus.get_object('org.bluez', '/'),
        'org.freedesktop.DBus.ObjectManager'
    )
    objects = manager.GetManagedObjects()

    ad_count = 0
    for path, interfaces in objects.items():
        if 'org.bluez.LEAdvertisement1' in interfaces:
            ad_count += 1
            print(f"  Found advertisement: {path}")

    if ad_count == 0:
        print("  ✓ No existing advertisements found")
    else:
        print(f"  ⚠ Found {ad_count} existing advertisement(s)")
        print("    These may prevent new registrations")

except Exception as e:
    print(f"  Could not check advertisements: {e}")

print()

# Test 7: Try to register a test advertisement via D-Bus directly
print("[7/8] Attempting direct D-Bus advertisement registration...")
try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop

    DBusGMainLoop(set_as_default=True)

    class TestAdvertisement(dbus.service.Object):
        PATH = '/org/bluez/gatetorio/advertisement0'

        def __init__(self, bus):
            dbus.service.Object.__init__(self, bus, self.PATH)

        @dbus.service.method('org.freedesktop.DBus.Properties',
                           in_signature='s',
                           out_signature='a{sv}')
        def GetAll(self, interface):
            if interface != 'org.bluez.LEAdvertisement1':
                raise dbus.exceptions.DBusException(
                    'org.freedesktop.DBus.Error.InvalidArgs',
                    'Invalid interface')

            return {
                'Type': dbus.String('peripheral'),
                'ServiceUUIDs': dbus.Array([], signature='s'),
                'LocalName': dbus.String('GateterioTest'),
                'IncludeTxPower': dbus.Boolean(True),
            }

        @dbus.service.method('org.bluez.LEAdvertisement1',
                           in_signature='',
                           out_signature='')
        def Release(self):
            print("    Advertisement released")

    bus = dbus.SystemBus()

    # Find adapter
    manager = dbus.Interface(
        bus.get_object('org.bluez', '/'),
        'org.freedesktop.DBus.ObjectManager'
    )
    objects = manager.GetManagedObjects()

    adapter_path = None
    for path, interfaces in objects.items():
        if 'org.bluez.Adapter1' in interfaces:
            adapter_path = path
            break

    if not adapter_path:
        print("  ✗ No adapter found")
    else:
        # Create advertisement
        ad = TestAdvertisement(bus)

        # Try to register
        ad_manager = dbus.Interface(
            bus.get_object('org.bluez', adapter_path),
            'org.bluez.LEAdvertisingManager1'
        )

        print(f"  Registering test advertisement on {adapter_path}...")
        ad_manager.RegisterAdvertisement(
            ad.PATH,
            dbus.Dictionary({}, signature='sv')
        )

        print("  ✓ SUCCESS! D-Bus advertisement registered!")
        print("  The issue is likely with bluezero's Peripheral API, not BlueZ")

        # Unregister
        ad_manager.UnregisterAdvertisement(ad.PATH)
        print("  ✓ Unregistered test advertisement")

except dbus.exceptions.DBusException as e:
    print(f"  ✗ D-Bus advertisement failed: {e}")
    print("  This indicates a BlueZ/D-Bus level issue")
except Exception as e:
    print(f"  ✗ Test failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 8: Check bluezero import and basic functionality
print("[8/8] Testing bluezero imports...")
try:
    from bluezero import adapter
    print("  ✓ bluezero.adapter imported")

    from bluezero import peripheral
    print("  ✓ bluezero.peripheral imported")

    # Try to get adapter
    adapters = list(adapter.Adapter.available())
    if adapters:
        print(f"  ✓ Found {len(adapters)} adapter(s) via bluezero")
        for ad in adapters:
            print(f"    - {ad.address}")
    else:
        print("  ✗ No adapters found via bluezero")

except Exception as e:
    print(f"  ✗ bluezero test failed: {e}")

print()
print("=" * 60)
print("Diagnostic Complete")
print("=" * 60)
print()
print("RECOMMENDATIONS:")
print("1. If Test 7 succeeded: bluezero Peripheral API has issues")
print("   → Need to use direct D-Bus implementation")
print("2. If Test 7 failed: BlueZ/D-Bus level issue")
print("   → Check BlueZ version, update if needed")
print("3. If advertisements found in Test 6:")
print("   → Run: sudo systemctl restart bluetooth")
print()
