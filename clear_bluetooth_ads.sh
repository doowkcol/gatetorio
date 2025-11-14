#!/bin/bash
#
# Clear Bluetooth Advertisements
#
# This script forcefully clears any stale BLE advertisements that might
# be preventing new registrations.
#

echo "Clearing Bluetooth advertisements..."

# Method 1: Remove advertisement via bluetoothctl
echo "Attempting to remove via bluetoothctl..."
timeout 2s bluetoothctl <<EOF
remove-advertisement
exit
EOF

# Method 2: Restart Bluetooth service
echo "Restarting Bluetooth service..."
sudo systemctl restart bluetooth
sleep 2

# Method 3: Power cycle the adapter
echo "Power cycling Bluetooth adapter..."
sudo hciconfig hci0 down
sleep 1
sudo hciconfig hci0 up
sleep 1

# Verify adapter is up
if hciconfig hci0 | grep -q "UP RUNNING"; then
    echo "✓ Bluetooth adapter is UP and ready"
else
    echo "✗ Warning: Bluetooth adapter may not be ready"
    hciconfig hci0
fi

echo ""
echo "Bluetooth state cleared. You can now start the BLE server."
echo "Run: sudo ./start_ble_server.sh"
