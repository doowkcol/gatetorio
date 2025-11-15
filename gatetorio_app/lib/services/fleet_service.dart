import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/fleet_device.dart';

/// Service for managing fleet of gate controllers
/// Currently uses demo data - will be replaced with real WebSocket/HTTP in Phase 2
class FleetService extends ChangeNotifier {
  // Fleet state
  bool _serverConnected = false;
  DateTime _lastSync = DateTime.now();
  List<FleetDevice> _devices = [];
  Timer? _heartbeatTimer;

  // Getters
  bool get serverConnected => _serverConnected;
  DateTime get lastSync => _lastSync;
  List<FleetDevice> get devices => _devices;

  int get totalDevices => _devices.length;
  int get onlineDevices => _devices.where((d) => d.isOnline).length;
  int get offlineDevices => _devices.where((d) => !d.isOnline).length;

  FleetService() {
    _initializeDemoData();
  }

  /// Initialize with demo data
  void _initializeDemoData() {
    _serverConnected = true;
    _lastSync = DateTime.now();

    // Create 7 demo devices with varied states
    _devices = [
      FleetDevice(
        deviceId: 'GT-A4F2B8C1',
        customName: 'Main Gate - North Entrance',
        location: 'Warehouse Complex A',
        isOnline: true,
        lastSeen: DateTime.now().subtract(const Duration(minutes: 2)),
        signalStrength: 92,
        firmwareVersion: '1.2.3',
        gateType: 'dual_motor',
        currentState: 'idle',
      ),
      FleetDevice(
        deviceId: 'GT-7D3E9A12',
        customName: 'Service Gate - East Side',
        location: 'Manufacturing Plant B',
        isOnline: true,
        lastSeen: DateTime.now().subtract(const Duration(minutes: 5)),
        signalStrength: 78,
        firmwareVersion: '1.2.3',
        gateType: 'dual_motor',
        currentState: 'opening',
      ),
      FleetDevice(
        deviceId: 'GT-B5C4D6E2',
        customName: 'Loading Dock Gate',
        location: 'Distribution Center',
        isOnline: false,
        lastSeen: DateTime.now().subtract(const Duration(hours: 3)),
        signalStrength: 0,
        firmwareVersion: '1.2.1',
        gateType: 'single_motor',
        currentState: null,
      ),
      FleetDevice(
        deviceId: 'GT-E8F1A3C7',
        customName: 'Security Checkpoint 1',
        location: 'Corporate Office',
        isOnline: true,
        lastSeen: DateTime.now().subtract(const Duration(seconds: 45)),
        signalStrength: 65,
        firmwareVersion: '1.2.3',
        gateType: 'dual_motor',
        currentState: 'idle',
      ),
      FleetDevice(
        deviceId: 'GT-C9D2E4F6',
        customName: 'Parking Lot Gate',
        location: 'Shopping Center',
        isOnline: true,
        lastSeen: DateTime.now().subtract(const Duration(minutes: 1)),
        signalStrength: 88,
        firmwareVersion: '1.2.2',
        gateType: 'dual_motor',
        currentState: 'closing',
      ),
      FleetDevice(
        deviceId: 'GT-F3A7B2C9',
        customName: 'Perimeter Gate - South',
        location: 'Industrial Park',
        isOnline: false,
        lastSeen: DateTime.now().subtract(const Duration(days: 2)),
        signalStrength: 0,
        firmwareVersion: '1.1.8',
        gateType: 'single_motor',
        currentState: null,
      ),
      FleetDevice(
        deviceId: 'GT-D4E6F8A1',
        customName: 'Emergency Exit Gate',
        location: 'Hospital Campus',
        isOnline: true,
        lastSeen: DateTime.now().subtract(const Duration(minutes: 8)),
        signalStrength: 42,
        firmwareVersion: '1.2.3',
        gateType: 'dual_motor',
        currentState: 'idle',
      ),
    ];

    // Start simulated heartbeat updates
    _startHeartbeatSimulation();

    notifyListeners();
  }

  /// Start simulating heartbeat updates for demo
  void _startHeartbeatSimulation() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      // Update last seen times for online devices
      _devices = _devices.map((device) {
        if (device.isOnline) {
          return FleetDevice(
            deviceId: device.deviceId,
            customName: device.customName,
            location: device.location,
            isOnline: device.isOnline,
            lastSeen: DateTime.now().subtract(Duration(
              seconds: (device.deviceId.hashCode % 60).abs(),
            )),
            signalStrength: device.signalStrength,
            firmwareVersion: device.firmwareVersion,
            gateType: device.gateType,
            currentState: device.currentState,
          );
        }
        return device;
      }).toList();

      _lastSync = DateTime.now();
      notifyListeners();
    });
  }

  /// Refresh fleet data (simulated)
  Future<void> refreshFleet() async {
    debugPrint('FleetService: Refreshing fleet data...');

    // Simulate network delay
    await Future.delayed(const Duration(seconds: 1));

    _lastSync = DateTime.now();
    notifyListeners();

    debugPrint('FleetService: Fleet refreshed - ${_devices.length} devices');
  }

  /// Connect to fleet server (simulated)
  Future<bool> connectToServer() async {
    debugPrint('FleetService: Connecting to fleet server...');

    // Simulate connection delay
    await Future.delayed(const Duration(seconds: 2));

    _serverConnected = true;
    _lastSync = DateTime.now();
    notifyListeners();

    return true;
  }

  /// Disconnect from fleet server
  void disconnect() {
    _serverConnected = false;
    _heartbeatTimer?.cancel();
    notifyListeners();
  }

  /// Get device by ID
  FleetDevice? getDevice(String deviceId) {
    try {
      return _devices.firstWhere((d) => d.deviceId == deviceId);
    } catch (e) {
      return null;
    }
  }

  /// Filter devices by online status
  List<FleetDevice> getDevicesByStatus(bool online) {
    return _devices.where((d) => d.isOnline == online).toList();
  }

  /// Search devices by name or location
  List<FleetDevice> searchDevices(String query) {
    if (query.isEmpty) return _devices;

    final lowerQuery = query.toLowerCase();
    return _devices.where((d) {
      return d.customName.toLowerCase().contains(lowerQuery) ||
             d.location.toLowerCase().contains(lowerQuery) ||
             d.deviceId.toLowerCase().contains(lowerQuery);
    }).toList();
  }

  /// Sort devices
  void sortDevices(DeviceSortOption option) {
    switch (option) {
      case DeviceSortOption.name:
        _devices.sort((a, b) => a.customName.compareTo(b.customName));
        break;
      case DeviceSortOption.status:
        _devices.sort((a, b) {
          if (a.isOnline == b.isOnline) return 0;
          return a.isOnline ? -1 : 1;
        });
        break;
      case DeviceSortOption.lastSeen:
        _devices.sort((a, b) => b.lastSeen.compareTo(a.lastSeen));
        break;
      case DeviceSortOption.signal:
        _devices.sort((a, b) => b.signalStrength.compareTo(a.signalStrength));
        break;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _heartbeatTimer?.cancel();
    super.dispose();
  }
}

/// Device sorting options
enum DeviceSortOption {
  name,
  status,
  lastSeen,
  signal;

  String get displayName {
    switch (this) {
      case DeviceSortOption.name:
        return 'Name';
      case DeviceSortOption.status:
        return 'Status';
      case DeviceSortOption.lastSeen:
        return 'Last Seen';
      case DeviceSortOption.signal:
        return 'Signal';
    }
  }
}
