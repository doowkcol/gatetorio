#!/bin/bash
#
# Gatetorio BLE Server Startup Script
#
# This script ensures a clean Bluetooth state before starting the BLE server.
# Run with: sudo ./start_ble_server.sh
#

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Gatetorio BLE Server Startup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    echo "Usage: sudo ./start_ble_server.sh"
    exit 1
fi

# Check for other gate controller instances
echo "Step 1: Checking for existing gate controller instances..."
GATE_PROCS=$(ps aux | grep -E "gate_controller_v2.py|gate_ui.py" | grep -v grep | wc -l)
if [ "$GATE_PROCS" -gt 0 ]; then
    echo -e "${YELLOW}WARNING: Found $GATE_PROCS gate controller process(es) running${NC}"
    echo "The BLE server will create its own controller instance."
    echo "Close the desktop launcher to avoid conflicts."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled"
        exit 0
    fi
else
    echo -e "${GREEN}✓ No existing controller instances found${NC}"
fi

echo ""
echo "Step 2: Cleaning Bluetooth state..."

# Stop any existing BLE server instances
if pgrep -f "ble_server_bluezero.py" > /dev/null; then
    echo "  Stopping existing BLE server..."
    pkill -f "ble_server_bluezero.py" || true
    sleep 1
fi

# Restart Bluetooth service to clear advertisements
echo "  Restarting Bluetooth service to clear old advertisements..."
systemctl restart bluetooth
sleep 2

# Power cycle the Bluetooth adapter (more aggressive cleanup)
echo "  Power cycling Bluetooth adapter..."
hciconfig hci0 down 2>/dev/null || true
sleep 1
hciconfig hci0 up 2>/dev/null || true
sleep 2

# Verify Bluetooth is running
if systemctl is-active --quiet bluetooth; then
    echo -e "${GREEN}✓ Bluetooth service is running${NC}"
else
    echo -e "${RED}ERROR: Bluetooth service failed to start${NC}"
    systemctl status bluetooth --no-pager
    exit 1
fi

# Check Bluetooth adapter
echo ""
echo "Step 3: Checking Bluetooth adapter..."
if hciconfig hci0 up 2>/dev/null; then
    ADAPTER_INFO=$(hciconfig hci0 | head -1)
    echo -e "${GREEN}✓ Bluetooth adapter UP: $ADAPTER_INFO${NC}"
else
    echo -e "${RED}ERROR: Bluetooth adapter not found or not accessible${NC}"
    echo "Check: hciconfig -a"
    exit 1
fi

echo ""
echo "Step 4: Starting BLE server..."
echo "=========================================="
echo ""

# Change to code directory
cd /home/doowkcol/Gatetorio_Code

# Run BLE server
python3 ble_server_bluezero.py

# If we get here, server stopped (Ctrl+C or error)
echo ""
echo "=========================================="
echo "BLE server stopped"
echo "=========================================="
