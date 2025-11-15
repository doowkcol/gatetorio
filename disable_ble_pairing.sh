#!/bin/bash
#
# Disable BLE Pairing Prompts for Testing
#
# This script configures bluetoothd to not require pairing/bonding,
# making testing easier without security prompts.
#

echo "Disabling BLE pairing requirements for testing..."

# Stop bluetooth service
sudo systemctl stop bluetooth

# Configure bluetoothd to run without pairing agent
# Create a drop-in config to disable pairing
sudo mkdir -p /etc/systemd/system/bluetooth.service.d/

cat << 'EOF' | sudo tee /etc/systemd/system/bluetooth.service.d/override.conf
[Service]
# Disable pairing prompts for testing
# Remove this file for production use!
ExecStart=
ExecStart=/usr/lib/bluetooth/bluetoothd --noplugin=* --experimental
EOF

# Reload systemd and restart bluetooth
sudo systemctl daemon-reload
sudo systemctl start bluetooth

# Wait for bluetooth to initialize
sleep 2

# Set adapter to not require pairing
bluetoothctl << EOF
pairable off
EOF

echo ""
echo "✓ BLE pairing disabled for testing"
echo ""
echo "To re-enable pairing later:"
echo "  sudo rm /etc/systemd/system/bluetooth.service.d/override.conf"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl restart bluetooth"
echo ""
