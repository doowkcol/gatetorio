import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/ble_service.dart';
import 'services/fleet_service.dart';
import 'services/log_service.dart';
import 'services/device_history_service.dart';
import 'screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize device history service
  final deviceHistoryService = DeviceHistoryService();
  await deviceHistoryService.initialize();

  runApp(GateterioApp(deviceHistoryService: deviceHistoryService));
}

class GateterioApp extends StatelessWidget {
  final DeviceHistoryService deviceHistoryService;

  const GateterioApp({super.key, required this.deviceHistoryService});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => BleService()),
        ChangeNotifierProvider(create: (_) => FleetService()),
        ChangeNotifierProvider(create: (_) => LogService()),
        ChangeNotifierProvider.value(value: deviceHistoryService),
      ],
      child: MaterialApp(
        title: 'Gatetorio Controller',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF4CAF50), // Gatetorio green
            brightness: Brightness.dark,
            background: const Color(0xFF121212),
            surface: const Color(0xFF1E1E1E),
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF121212),
          cardTheme: CardThemeData(
            elevation: 2,
            color: const Color(0xFF1E1E1E),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          elevatedButtonTheme: ElevatedButtonThemeData(
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF1E1E1E),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
        ),
        themeMode: ThemeMode.dark,
        home: const HomeScreen(),
      ),
    );
  }
}
