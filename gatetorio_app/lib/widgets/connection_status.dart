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
            color: const Color(0xFF5C1010),
            child: Row(
              children: [
                const Icon(Icons.error, color: Color(0xFFFF6B6B)),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    bleService.lastError!,
                    style: const TextStyle(color: Color(0xFFFF6B6B)),
                  ),
                ),
              ],
            ),
          );
        }

        if (bleService.isConnected) {
          // Show different colors for demo mode vs real connection
          final isDemoMode = bleService.isDemoMode;
          final bgColor = isDemoMode ? const Color(0xFF5C3A10) : const Color(0xFF1B5E20);
          final textColor = isDemoMode ? const Color(0xFFFFB74D) : const Color(0xFF81C784);
          final icon = isDemoMode ? Icons.preview : Icons.bluetooth_connected;

          return Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            color: bgColor,
            child: Row(
              children: [
                Icon(icon, color: textColor),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    isDemoMode
                        ? 'Demo Mode - Static UI Preview (Not Connected)'
                        : 'Connected to ${bleService.connectedDeviceName}',
                    style: TextStyle(
                      color: textColor,
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
            color: const Color(0xFF0D47A1),
            child: const Row(
              children: [
                SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Color(0xFF64B5F6),
                  ),
                ),
                SizedBox(width: 12),
                Text(
                  'Scanning for devices...',
                  style: TextStyle(color: Color(0xFF64B5F6)),
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
