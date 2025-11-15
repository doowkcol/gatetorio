import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';

class ConnectionStatus extends StatelessWidget {
  const ConnectionStatus({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<BleService>(
      builder: (context, bleService, child) {
        if (bleService.lastError != null) {
          return Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            color: Colors.red.shade100,
            child: Row(
              children: [
                Icon(Icons.error, color: Colors.red.shade900),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    bleService.lastError!,
                    style: TextStyle(color: Colors.red.shade900),
                  ),
                ),
              ],
            ),
          );
        }

        if (bleService.isConnected) {
          return Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            color: Colors.green.shade100,
            child: Row(
              children: [
                Icon(Icons.bluetooth_connected, color: Colors.green.shade900),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Connected to ${bleService.connectedDeviceName}',
                    style: TextStyle(
                      color: Colors.green.shade900,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
          );
        }

        if (bleService.isScanning) {
          return Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            color: Colors.blue.shade100,
            child: Row(
              children: [
                SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.blue.shade900,
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  'Scanning for devices...',
                  style: TextStyle(color: Colors.blue.shade900),
                ),
              ],
            ),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }
}
