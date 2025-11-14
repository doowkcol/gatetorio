#!/bin/bash
#
# Gatetorio BLE Dependencies Installation Script
#
# This script installs all system and Python dependencies required for
# the Gatetorio BLE bridge using bluezero.
#
# Usage:
#   sudo ./install_ble_dependencies.sh
#
# Requirements:
#   - Raspberry Pi running Raspberry Pi OS (Debian-based)
#   - Root privileges (sudo)
#   - Internet connection

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Gatetorio BLE Dependencies Installer"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}WARNING: Not detected as Raspberry Pi - continuing anyway${NC}"
else
    MODEL=$(cat /proc/device-tree/model)
    echo "Detected: $MODEL"
fi

echo ""
echo "This will install the following:"
echo "  - BlueZ Bluetooth stack (system package)"
echo "  - Python D-Bus libraries"
echo "  - Python bluezero library"
echo "  - Python psutil library"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 0
fi

echo ""
echo -e "${GREEN}[1/5] Updating package lists...${NC}"
apt-get update

echo ""
echo -e "${GREEN}[2/5] Installing system dependencies...${NC}"
apt-get install -y \
    bluez \
    python3-pip \
    python3-dbus \
    libdbus-1-dev \
    libglib2.0-dev \
    python3-gi

echo ""
echo -e "${GREEN}[3/5] Checking Bluetooth service...${NC}"
systemctl status bluetooth --no-pager || true

if ! systemctl is-active --quiet bluetooth; then
    echo -e "${YELLOW}Bluetooth service not running - starting it...${NC}"
    systemctl start bluetooth
    systemctl enable bluetooth
fi

echo ""
echo -e "${GREEN}[4/5] Installing Python packages...${NC}"
pip3 install --upgrade pip
pip3 install -r /home/doowkcol/Gatetorio_Code/requirements_bluetooth.txt

echo ""
echo -e "${GREEN}[5/5] Verifying installation...${NC}"

# Check bluezero
python3 -c "import bluezero; print('✓ bluezero installed')" 2>/dev/null || \
    echo -e "${RED}✗ bluezero NOT installed${NC}"

# Check psutil
python3 -c "import psutil; print('✓ psutil installed')" 2>/dev/null || \
    echo -e "${YELLOW}✗ psutil NOT installed (optional)${NC}"

# Check Bluetooth adapter
if hciconfig -a | grep -q "UP RUNNING"; then
    echo "✓ Bluetooth adapter is UP"
else
    echo -e "${YELLOW}✗ Bluetooth adapter not UP - may need 'sudo hciconfig hci0 up'${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Test the BLE server:"
echo "     sudo python3 /home/doowkcol/Gatetorio_Code/ble_server_bluezero.py"
echo ""
echo "  2. Install systemd service (optional):"
echo "     sudo cp /home/doowkcol/Gatetorio_Code/systemd/gatetorio-ble.service /etc/systemd/system/"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable gatetorio-ble"
echo "     sudo systemctl start gatetorio-ble"
echo ""
echo "  3. Connect with mobile app (nRF Connect or LightBlue)"
echo "     Look for device: Gatetorio-XXXX"
echo ""
echo "Troubleshooting:"
echo "  - Check Bluetooth: systemctl status bluetooth"
echo "  - Check BLE service: systemctl status gatetorio-ble"
echo "  - View logs: journalctl -u gatetorio-ble -f"
echo ""
