import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../widgets/device_scanner.dart';
import '../widgets/gate_controller.dart';
import '../widgets/connection_status.dart';
import 'settings_screen.dart';
import 'input_status_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gatetorio Gate Controller'),
        backgroundColor: Theme.of(context).colorScheme.primaryContainer,
        actions: [
          Consumer<BleService>(
            builder: (context, bleService, child) {
              if (bleService.isConnected) {
                return Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.electrical_services),
                      tooltip: 'Input Status',
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const InputStatusScreen(),
                          ),
                        );
                      },
                    ),
                    IconButton(
                      icon: const Icon(Icons.settings),
                      tooltip: 'Settings',
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const SettingsScreen(),
                          ),
                        );
                      },
                    ),
                    IconButton(
                      icon: const Icon(Icons.bluetooth_disabled),
                      tooltip: 'Disconnect',
                      onPressed: () async {
                        await bleService.disconnect();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Disconnected')),
                          );
                        }
                      },
                    ),
                  ],
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Consumer<BleService>(
          builder: (context, bleService, child) {
            return Column(
              children: [
                // Connection status banner
                const ConnectionStatus(),

                // Main content
                Expanded(
                  child: bleService.isConnected
                      ? const GateController()
                      : const DeviceScanner(),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
