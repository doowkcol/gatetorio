import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import '../models/gate_status.dart';
import '../models/gate_command.dart';
import '../models/ble_device_info.dart';

/// BLE Service for communicating with Gatetorio gate controller
/// Handles device scanning, connection, and GATT operations
class BleService extends ChangeNotifier {
  // GATT Service and Characteristic UUIDs (matching ble_server_bluezero.py)
  static const String _baseUuidTemplate = "0000{}-4751-5445-5254-494F00000000";

  // Services
  static final Guid _gateControlServiceUuid = Guid(_formatUuid(0x1000));

  // Characteristics
  static final Guid _commandTxUuid = Guid(_formatUuid(0x1001));
  static final Guid _commandResponseUuid = Guid(_formatUuid(0x1002));
  static final Guid _statusUuid = Guid(_formatUuid(0x1003));

  // Helper to format UUIDs
  static String _formatUuid(int code) {
    return _baseUuidTemplate.replaceFirst('{}', code.toRadixString(16).padLeft(4, '0').toUpperCase());
  }

  // BLE State
  BluetoothDevice? _connectedDevice;
  BluetoothCharacteristic? _commandTxChar;
  BluetoothCharacteristic? _commandResponseChar;
  BluetoothCharacteristic? _statusChar;

  GateStatus? _currentStatus;
  List<BleDeviceInfo> _discoveredDevices = [];
  bool _isScanning = false;
  bool _isConnecting = false;
  String? _lastError;

  // Stream subscriptions
  StreamSubscription<List<ScanResult>>? _scanSubscription;
  StreamSubscription<BluetoothConnectionState>? _connectionSubscription;
  StreamSubscription<List<int>>? _statusSubscription;

  // Getters
  bool get isConnected => _connectedDevice != null;
  bool get isScanning => _isScanning;
  bool get isConnecting => _isConnecting;
  GateStatus? get currentStatus => _currentStatus;
  List<BleDeviceInfo> get discoveredDevices => _discoveredDevices;
  String? get lastError => _lastError;
  String? get connectedDeviceName => _connectedDevice?.platformName;

  BleService() {
    _initialize();
  }

  /// Initialize BLE adapter
  Future<void> _initialize() async {
    try {
      // Check if Bluetooth is supported
      if (await FlutterBluePlus.isSupported == false) {
        _lastError = "Bluetooth not supported on this device";
        notifyListeners();
        return;
      }

      // Listen to adapter state
      FlutterBluePlus.adapterState.listen((state) {
        if (state != BluetoothAdapterState.on) {
          _lastError = "Bluetooth is turned off";
          notifyListeners();
        } else {
          _lastError = null;
          notifyListeners();
        }
      });
    } catch (e) {
      _lastError = "BLE initialization failed: $e";
      notifyListeners();
    }
  }

  /// Request necessary BLE permissions
  Future<bool> requestPermissions() async {
    try {
      if (defaultTargetPlatform == TargetPlatform.android) {
        // Request Bluetooth permissions
        Map<Permission, PermissionStatus> statuses = await [
          Permission.bluetoothScan,
          Permission.bluetoothConnect,
          Permission.location,
        ].request();

        bool allGranted = statuses.values.every((status) => status.isGranted);
        if (!allGranted) {
          _lastError = "Bluetooth permissions not granted";
          notifyListeners();
          return false;
        }
      }
      return true;
    } catch (e) {
      _lastError = "Permission request failed: $e";
      notifyListeners();
      return false;
    }
  }

  /// Start scanning for Gatetorio devices
  Future<void> startScan({Duration timeout = const Duration(seconds: 10)}) async {
    if (_isScanning) return;

    try {
      _isScanning = true;
      _discoveredDevices = [];
      _lastError = null;
      notifyListeners();

      // Request permissions first
      if (!await requestPermissions()) {
        _isScanning = false;
        notifyListeners();
        return;
      }

      // Start scanning
      await FlutterBluePlus.startScan(timeout: timeout);

      // Listen to scan results
      _scanSubscription?.cancel();
      _scanSubscription = FlutterBluePlus.scanResults.listen((results) {
        _discoveredDevices = results
            .where((r) =>
                r.device.platformName.isNotEmpty &&
                r.device.platformName.toLowerCase().contains('gatetorio'))
            .map((r) => BleDeviceInfo(
                  deviceId: r.device.remoteId.toString(),
                  deviceName: r.device.platformName,
                  rssi: r.rssi,
                  isConnected: false,
                ))
            .toList();
        notifyListeners();
      });

      // Auto-stop after timeout
      Future.delayed(timeout, () {
        if (_isScanning) {
          stopScan();
        }
      });
    } catch (e) {
      _lastError = "Scan failed: $e";
      _isScanning = false;
      notifyListeners();
    }
  }

  /// Stop scanning
  Future<void> stopScan() async {
    try {
      await FlutterBluePlus.stopScan();
      _isScanning = false;
      notifyListeners();
    } catch (e) {
      _lastError = "Stop scan failed: $e";
      notifyListeners();
    }
  }

  /// Connect to a device by ID
  Future<bool> connect(String deviceId) async {
    if (_isConnecting) return false;

    try {
      _isConnecting = true;
      _lastError = null;
      notifyListeners();

      // Stop scanning if active
      if (_isScanning) {
        await stopScan();
      }

      // Find the device
      final results = await FlutterBluePlus.lastScanResults;
      final result = results.firstWhere(
        (r) => r.device.remoteId.toString() == deviceId,
        orElse: () => throw Exception("Device not found"),
      );

      final device = result.device;

      // Listen to connection state
      _connectionSubscription?.cancel();
      _connectionSubscription = device.connectionState.listen((state) {
        if (state == BluetoothConnectionState.disconnected) {
          _handleDisconnection();
        }
      });

      // Connect with timeout
      await device.connect(timeout: const Duration(seconds: 15));
      _connectedDevice = device;

      // Discover services and characteristics
      final success = await _discoverServices();
      if (!success) {
        await disconnect();
        _isConnecting = false;
        notifyListeners();
        return false;
      }

      // Subscribe to status notifications
      await _subscribeToStatus();

      _isConnecting = false;
      notifyListeners();
      return true;
    } catch (e) {
      _lastError = "Connection failed: $e";
      _isConnecting = false;
      _connectedDevice = null;
      notifyListeners();
      return false;
    }
  }

  /// Discover GATT services and characteristics
  Future<bool> _discoverServices() async {
    if (_connectedDevice == null) return false;

    try {
      final services = await _connectedDevice!.discoverServices();

      // Find Gate Control Service
      final gateControlService = services.firstWhere(
        (s) => s.uuid == _gateControlServiceUuid,
        orElse: () => throw Exception("Gate Control Service not found"),
      );

      // Find characteristics
      _commandTxChar = gateControlService.characteristics.firstWhere(
        (c) => c.uuid == _commandTxUuid,
        orElse: () => throw Exception("Command TX characteristic not found"),
      );

      _commandResponseChar = gateControlService.characteristics.firstWhere(
        (c) => c.uuid == _commandResponseUuid,
        orElse: () => throw Exception("Command Response characteristic not found"),
      );

      _statusChar = gateControlService.characteristics.firstWhere(
        (c) => c.uuid == _statusUuid,
        orElse: () => throw Exception("Status characteristic not found"),
      );

      return true;
    } catch (e) {
      _lastError = "Service discovery failed: $e";
      return false;
    }
  }

  /// Subscribe to status notifications (1Hz updates from BLE server)
  Future<void> _subscribeToStatus() async {
    if (_statusChar == null) return;

    try {
      // Enable notifications
      await _statusChar!.setNotifyValue(true);

      // Listen to status updates
      _statusSubscription?.cancel();
      _statusSubscription = _statusChar!.lastValueStream.listen((value) {
        if (value.isNotEmpty) {
          try {
            _currentStatus = GateStatus.fromBytes(value);
            notifyListeners();
          } catch (e) {
            debugPrint("Failed to parse status: $e");
          }
        }
      });

      // Also read current status immediately
      await readStatus();
    } catch (e) {
      _lastError = "Failed to subscribe to status: $e";
    }
  }

  /// Read current status (one-time read)
  Future<GateStatus?> readStatus() async {
    if (_statusChar == null) return null;

    try {
      final value = await _statusChar!.read();
      if (value.isNotEmpty) {
        _currentStatus = GateStatus.fromBytes(value);
        notifyListeners();
        return _currentStatus;
      }
    } catch (e) {
      _lastError = "Failed to read status: $e";
    }
    return null;
  }

  /// Send a command to the gate controller
  Future<bool> sendCommand(GateCommand command) async {
    if (_commandTxChar == null) {
      _lastError = "Not connected to device";
      notifyListeners();
      return false;
    }

    try {
      debugPrint("Sending command: $command");
      await _commandTxChar!.write(command.toBytes(), withoutResponse: false);

      // Optionally read response
      if (_commandResponseChar != null) {
        final response = await _commandResponseChar!.read();
        if (response.isNotEmpty) {
          final responseStr = utf8.decode(response);
          debugPrint("Command response: $responseStr");
        }
      }

      _lastError = null;
      notifyListeners();
      return true;
    } catch (e) {
      _lastError = "Failed to send command: $e";
      notifyListeners();
      return false;
    }
  }

  /// Disconnect from current device
  Future<void> disconnect() async {
    try {
      await _statusSubscription?.cancel();
      _statusSubscription = null;

      await _connectedDevice?.disconnect();
      _connectedDevice = null;
      _commandTxChar = null;
      _commandResponseChar = null;
      _statusChar = null;
      _currentStatus = null;

      notifyListeners();
    } catch (e) {
      _lastError = "Disconnect failed: $e";
      notifyListeners();
    }
  }

  /// Handle unexpected disconnection
  void _handleDisconnection() {
    _connectedDevice = null;
    _commandTxChar = null;
    _commandResponseChar = null;
    _statusChar = null;
    _currentStatus = null;
    _lastError = "Device disconnected";
    notifyListeners();
  }

  @override
  void dispose() {
    _scanSubscription?.cancel();
    _connectionSubscription?.cancel();
    _statusSubscription?.cancel();
    disconnect();
    super.dispose();
  }
}
