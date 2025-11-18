import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../services/device_history_service.dart';
import '../models/ble_device_info.dart';

class DeviceScanner extends StatelessWidget {
  const DeviceScanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<BleService>(
      builder: (context, bleService, child) {
        return SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Simplified Header
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Text(
                    'Connect to Gate Controller',
                    style: Theme.of(context).textTheme.titleMedium,
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Connection method buttons
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: bleService.isScanning
                          ? () => bleService.stopScan()
                          : () => bleService.startScan(),
                      icon: Icon(bleService.isScanning
                          ? Icons.stop
                          : Icons.bluetooth),
                      label: Text(bleService.isScanning
                          ? 'Stop'
                          : 'Bluetooth'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1565C0),
                        foregroundColor: Colors.white,
                        minimumSize: const Size(0, 48),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: () {
                        // TODO: Implement web connection
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Web connection coming soon'),
                            backgroundColor: Colors.orange,
                          ),
                        );
                      },
                      icon: const Icon(Icons.language),
                      label: const Text('Web'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1565C0),
                        foregroundColor: Colors.white,
                        minimumSize: const Size(0, 48),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Device list
              if (bleService.discoveredDevices.isNotEmpty) ...[
                Text(
                  'Available Devices',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
              ],

              // Device list or empty state
              bleService.discoveredDevices.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.symmetric(vertical: 48.0),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.devices,
                            size: 48,
                            color: Colors.grey.shade400,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            'No devices found',
                            style: TextStyle(
                              color: Colors.grey.shade600,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Tap "Bluetooth" to search',
                            style: TextStyle(
                              color: Colors.grey.shade500,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: bleService.discoveredDevices.length,
                      itemBuilder: (context, index) {
                        final device = bleService.discoveredDevices[index];
                        return DeviceListItem(
                          device: device,
                          onTap: () => _connectToDevice(context, bleService, device),
                        );
                      },
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

      // If connection successful, save to known devices
      if (success) {
        final historyService = Provider.of<DeviceHistoryService>(context, listen: false);
        await historyService.addOrUpdateDevice(
          deviceId: device.deviceId,
          manufacturerName: device.deviceName,
          lastKnownRssi: device.rssi.toString(),
        );
      }

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

class DeviceListItem extends StatefulWidget {
  final BleDeviceInfo device;
  final Future<void> Function() onTap;

  const DeviceListItem({
    super.key,
    required this.device,
    required this.onTap,
  });

  @override
  State<DeviceListItem> createState() => _DeviceListItemState();
}

class _DeviceListItemState extends State<DeviceListItem> {
  bool _isConnecting = false;

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
          widget.device.deviceName,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'ID: ${widget.device.deviceId}',
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(
                  Icons.signal_cellular_alt,
                  size: 16,
                  color: _getSignalColor(),
                ),
                const SizedBox(width: 4),
                Flexible(
                  child: Text(
                    '${widget.device.signalStrength.displayName} (${widget.device.rssi} dBm)',
                    style: TextStyle(
                      color: _getSignalColor(),
                      fontSize: 12,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],
        ),
        trailing: ElevatedButton(
          onPressed: _isConnecting
              ? null
              : () async {
                  setState(() => _isConnecting = true);
                  await widget.onTap();
                  if (mounted) {
                    setState(() => _isConnecting = false);
                  }
                },
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.green,
            foregroundColor: Colors.white,
          ),
          child: _isConnecting
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                  ),
                )
              : const Text('Connect'),
        ),
        isThreeLine: true,
      ),
    );
  }

  Color _getSignalColor() {
    switch (widget.device.signalStrength) {
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
