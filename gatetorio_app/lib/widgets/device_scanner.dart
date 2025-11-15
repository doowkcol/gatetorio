import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../models/ble_device_info.dart';

class DeviceScanner extends StatelessWidget {
  const DeviceScanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<BleService>(
      builder: (context, bleService, child) {
        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      Icon(
                        Icons.bluetooth_searching,
                        size: 64,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Find Your Gate Controller',
                        style: Theme.of(context).textTheme.headlineSmall,
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Make sure Bluetooth is enabled and the gate controller is powered on.',
                        style: Theme.of(context).textTheme.bodyMedium,
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Scan button
              ElevatedButton.icon(
                onPressed: bleService.isScanning
                    ? null
                    : () => bleService.startScan(),
                icon: Icon(bleService.isScanning
                    ? Icons.stop
                    : Icons.bluetooth_searching),
                label: Text(bleService.isScanning
                    ? 'Scanning...'
                    : 'Start Scanning'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.primary,
                  foregroundColor: Theme.of(context).colorScheme.onPrimary,
                ),
              ),
              const SizedBox(height: 12),

              // Demo Mode button
              OutlinedButton.icon(
                onPressed: () => bleService.enableDemoMode(),
                icon: const Icon(Icons.preview),
                label: const Text('Demo Mode (Preview UI)'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.orange,
                  side: const BorderSide(color: Colors.orange),
                ),
              ),
              const SizedBox(height: 24),

              // Device list
              if (bleService.discoveredDevices.isNotEmpty) ...[
                Text(
                  'Available Devices',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
              ],

              Expanded(
                child: bleService.discoveredDevices.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.devices,
                              size: 64,
                              color: Colors.grey.shade400,
                            ),
                            const SizedBox(height: 16),
                            Text(
                              'No devices found',
                              style: TextStyle(
                                color: Colors.grey.shade600,
                                fontSize: 16,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Tap "Start Scanning" to search',
                              style: TextStyle(
                                color: Colors.grey.shade500,
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        itemCount: bleService.discoveredDevices.length,
                        itemBuilder: (context, index) {
                          final device = bleService.discoveredDevices[index];
                          return DeviceListItem(
                            device: device,
                            onTap: () => _connectToDevice(context, bleService, device),
                          );
                        },
                      ),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _connectToDevice(
    BuildContext context,
    BleService bleService,
    BleDeviceInfo device,
  ) async {
    // Show connecting dialog
    if (!context.mounted) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const AlertDialog(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Connecting...'),
          ],
        ),
      ),
    );

    // Attempt connection
    final success = await bleService.connect(device.deviceId);

    // Close dialog
    if (context.mounted) {
      Navigator.of(context).pop();

      // Show result
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success
              ? 'Connected to ${device.deviceName}'
              : 'Failed to connect: ${bleService.lastError ?? "Unknown error"}'),
          backgroundColor: success ? Colors.green : Colors.red,
        ),
      );
    }
  }
}

class DeviceListItem extends StatelessWidget {
  final BleDeviceInfo device;
  final VoidCallback onTap;

  const DeviceListItem({
    super.key,
    required this.device,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(
          Icons.router,
          size: 40,
          color: Theme.of(context).colorScheme.primary,
        ),
        title: Text(
          device.deviceName,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('ID: ${device.deviceId}'),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(
                  Icons.signal_cellular_alt,
                  size: 16,
                  color: _getSignalColor(),
                ),
                const SizedBox(width: 4),
                Text(
                  '${device.signalStrength.displayName} (${device.rssi} dBm)',
                  style: TextStyle(
                    color: _getSignalColor(),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ],
        ),
        trailing: ElevatedButton(
          onPressed: onTap,
          child: const Text('Connect'),
        ),
        isThreeLine: true,
      ),
    );
  }

  Color _getSignalColor() {
    switch (device.signalStrength) {
      case SignalStrength.excellent:
        return Colors.green;
      case SignalStrength.good:
        return Colors.lightGreen;
      case SignalStrength.fair:
        return Colors.orange;
      case SignalStrength.poor:
        return Colors.red;
    }
  }
}
