import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/device_history_service.dart';
import '../services/ble_service.dart';
import '../models/known_device.dart';
import 'device_scanner.dart' as scanner;

/// Screen showing all previously connected/whitelisted devices
/// Allows reconnection to stealth-mode devices and viewing cached data offline
class KnownDevicesScreen extends StatelessWidget {
  const KnownDevicesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Known Devices'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add Device',
            onPressed: () => _showAddDeviceDialog(context),
          ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          image: DecorationImage(
            image: AssetImage('assets/images/background.png'),
            fit: BoxFit.cover,
          ),
        ),
        child: Consumer<DeviceHistoryService>(
          builder: (context, historyService, child) {
            final devices = historyService.knownDevices;

            if (devices.isEmpty) {
              return _buildEmptyState(context);
            }

            return ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: devices.length,
              itemBuilder: (context, index) {
                return _buildDeviceCard(context, devices[index]);
              },
            );
          },
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Container(
        padding: const EdgeInsets.all(32),
        margin: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.7),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFF2196F3)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.devices, size: 64, color: Color(0xFF2196F3)),
            const SizedBox(height: 16),
            const Text(
              'No Known Devices',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Connect to a device to add it to your known devices',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => _showAddDeviceDialog(context),
              icon: const Icon(Icons.add),
              label: const Text('Add Device'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF2196F3),
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDeviceCard(BuildContext context, KnownDevice device) {
    final bleService = Provider.of<BleService>(context, listen: false);
    final isCurrentlyConnected = bleService.isConnected &&
        bleService.connectedDevice?.remoteId.toString() == device.deviceId;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: Colors.black.withOpacity(0.7),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: device.isOnline ? const Color(0xFF4CAF50) : Colors.grey.shade800,
          width: 2,
        ),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _viewDeviceDetails(context, device),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Device name and status indicator
              Row(
                children: [
                  Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: device.isOnline ? const Color(0xFF4CAF50) : Colors.grey,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      device.displayName,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  if (isCurrentlyConnected)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFF4CAF50),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Text(
                        'CONNECTED',
                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 8),

              // Last seen
              Text(
                'Last seen: ${device.lastSeenString}',
                style: TextStyle(
                  color: device.isOnline ? const Color(0xFF4CAF50) : Colors.grey,
                  fontSize: 14,
                ),
              ),

              // Device ID
              if (device.customName != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    device.deviceId.length > 17
                        ? '${device.deviceId.substring(device.deviceId.length - 17)}'
                        : device.deviceId,
                    style: const TextStyle(color: Colors.grey, fontSize: 12),
                  ),
                ),

              const SizedBox(height: 12),

              // Action buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: isCurrentlyConnected
                          ? null
                          : () => _connectBluetooth(context, device),
                      icon: Icon(
                        Icons.bluetooth,
                        size: 16,
                        color: isCurrentlyConnected ? Colors.grey : const Color(0xFF2196F3),
                      ),
                      label: Text(
                        isCurrentlyConnected ? 'Connected' : 'BT',
                        style: TextStyle(
                          color: isCurrentlyConnected ? Colors.grey : const Color(0xFF2196F3),
                        ),
                      ),
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(
                          color: isCurrentlyConnected ? Colors.grey : const Color(0xFF2196F3),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: device.ipAddress != null
                          ? () => _openWebInterface(context, device)
                          : null,
                      icon: Icon(
                        Icons.language,
                        size: 16,
                        color: device.ipAddress != null ? const Color(0xFF2196F3) : Colors.grey,
                      ),
                      label: Text(
                        'Web',
                        style: TextStyle(
                          color: device.ipAddress != null ? const Color(0xFF2196F3) : Colors.grey,
                        ),
                      ),
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(
                          color: device.ipAddress != null ? const Color(0xFF2196F3) : Colors.grey,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.edit, size: 20, color: Colors.grey),
                    onPressed: () => _editDeviceName(context, device),
                    tooltip: 'Rename',
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete, size: 20, color: Colors.red),
                    onPressed: () => _deleteDevice(context, device),
                    tooltip: 'Remove',
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showAddDeviceDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1E1E1E),
        title: const Text('Add Device', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Use the scanner to discover and connect to nearby devices. Once connected, they will be saved to your known devices.',
          style: TextStyle(color: Colors.grey),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              // Navigate to scanner (this will be the home screen scanner)
              Navigator.of(context).pushReplacementNamed('/');
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF2196F3)),
            child: const Text('Open Scanner'),
          ),
        ],
      ),
    );
  }

  void _connectBluetooth(BuildContext context, KnownDevice device) async {
    final bleService = Provider.of<BleService>(context, listen: false);

    // Show connecting dialog
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const AlertDialog(
        backgroundColor: Color(0xFF1E1E1E),
        content: Row(
          children: [
            CircularProgressIndicator(),
            SizedBox(width: 16),
            Text('Connecting...', style: TextStyle(color: Colors.white)),
          ],
        ),
      ),
    );

    try {
      // Direct connect using device ID
      await bleService.connect(device.deviceId);

      if (context.mounted) {
        Navigator.pop(context); // Close connecting dialog

        if (bleService.isConnected) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Connected to ${device.displayName}'),
              backgroundColor: Colors.green,
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to connect to ${device.displayName}'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        Navigator.pop(context); // Close connecting dialog
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Connection error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _openWebInterface(BuildContext context, KnownDevice device) {
    // TODO: Open web browser or WebView
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Web interface: http://${device.ipAddress}:8080'),
      ),
    );
  }

  void _viewDeviceDetails(BuildContext context, KnownDevice device) {
    // TODO: Navigate to device details screen showing cached config
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Device details view - coming soon'),
      ),
    );
  }

  void _editDeviceName(BuildContext context, KnownDevice device) {
    final controller = TextEditingController(text: device.customName);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1E1E1E),
        title: const Text('Rename Device', style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: controller,
          autofocus: true,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: 'Enter device name',
            hintStyle: TextStyle(color: Colors.grey),
            enabledBorder: UnderlineInputBorder(
              borderSide: BorderSide(color: Colors.grey),
            ),
            focusedBorder: UnderlineInputBorder(
              borderSide: BorderSide(color: Color(0xFF2196F3)),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              final historyService = Provider.of<DeviceHistoryService>(context, listen: false);
              historyService.updateDeviceName(device.deviceId, controller.text);
              Navigator.pop(context);
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF2196F3)),
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _deleteDevice(BuildContext context, KnownDevice device) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1E1E1E),
        title: const Text('Remove Device', style: TextStyle(color: Colors.white)),
        content: Text(
          'Remove ${device.displayName} from known devices?',
          style: const TextStyle(color: Colors.grey),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              final historyService = Provider.of<DeviceHistoryService>(context, listen: false);
              historyService.removeDevice(device.deviceId);
              Navigator.pop(context);
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
  }
}
