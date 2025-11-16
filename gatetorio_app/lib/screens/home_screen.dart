import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../services/fleet_service.dart';
import '../widgets/device_scanner.dart';
import '../widgets/gate_controller.dart';
import '../widgets/connection_status.dart';
import 'settings_screen.dart';
import 'input_status_screen.dart';
import 'fleet_management_screen.dart';
import 'logs_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              'assets/images/GateTorio lightmode icon.png',
              height: 28,
              fit: BoxFit.contain,
            ),
            const SizedBox(width: 8),
            const Flexible(
              child: Text(
                'Gatetorio',
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          // Fleet Management - always visible
          Consumer<FleetService>(
            builder: (context, fleetService, child) {
              return Stack(
                children: [
                  IconButton(
                    icon: const Icon(Icons.dashboard),
                    tooltip: 'Fleet Management',
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const FleetManagementScreen(),
                        ),
                      );
                    },
                  ),
                  // Offline device badge
                  if (fleetService.offlineDevices > 0)
                    Positioned(
                      right: 8,
                      top: 8,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: const BoxDecoration(
                          color: Color(0xFFFF6B6B),
                          shape: BoxShape.circle,
                        ),
                        constraints: const BoxConstraints(
                          minWidth: 16,
                          minHeight: 16,
                        ),
                        child: Text(
                          fleetService.offlineDevices.toString(),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
          // Device-specific actions - only when connected
          Consumer<BleService>(
            builder: (context, bleService, child) {
              if (bleService.isConnected) {
                return Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.article),
                      tooltip: 'Logs',
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const LogsScreen(),
                          ),
                        );
                      },
                    ),
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
      body: Stack(
        children: [
          // Background image
          Positioned.fill(
            child: Image.asset(
              'assets/images/background.png',
              fit: BoxFit.cover,
            ),
          ),
          // Main content
          SafeArea(
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
        ],
      ),
    );
  }
}
