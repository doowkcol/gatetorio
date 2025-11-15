import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import '../models/gate_status.dart';
import '../models/gate_command.dart';
import '../models/ble_device_info.dart';
import '../models/gate_config.dart';
import '../models/input_config.dart';

/// BLE Service for communicating with Gatetorio gate controller
/// Handles device scanning, connection, and GATT operations
class BleService extends ChangeNotifier {
  // GATT Service and Characteristic UUIDs (matching ble_server_bluezero.py)
  static const String _baseUuidTemplate = "0000{}-4751-5445-5254-494F00000000";

  // Services
  static final Guid _gateControlServiceUuid = Guid(_formatUuid(0x1000));
  static final Guid _configurationServiceUuid = Guid(_formatUuid(0x2000));
  static final Guid _diagnosticsServiceUuid = Guid(_formatUuid(0x3000));

  // Gate Control Characteristics
  static final Guid _commandTxUuid = Guid(_formatUuid(0x1001));
  static final Guid _commandResponseUuid = Guid(_formatUuid(0x1002));
  static final Guid _statusUuid = Guid(_formatUuid(0x1003));

  // Configuration Characteristics
  static final Guid _configDataUuid = Guid(_formatUuid(0x2001));
  static final Guid _inputConfigUuid = Guid(_formatUuid(0x2003));

  // Diagnostics Characteristics
  static final Guid _inputStatesUuid = Guid(_formatUuid(0x3001));

  // Helper to format UUIDs
  static String _formatUuid(int code) {
    return _baseUuidTemplate.replaceFirst('{}', code.toRadixString(16).padLeft(4, '0').toUpperCase());
  }

  // BLE State
  BluetoothDevice? _connectedDevice;
  BluetoothCharacteristic? _commandTxChar;
  BluetoothCharacteristic? _commandResponseChar;
  BluetoothCharacteristic? _statusChar;
  BluetoothCharacteristic? _configDataChar;
  BluetoothCharacteristic? _inputConfigChar;
  BluetoothCharacteristic? _inputStatesChar;

  GateStatus? _currentStatus;
  GateConfig? _currentConfig;
  InputConfigData? _inputConfig;
  InputStates? _inputStates;
  List<BleDeviceInfo> _discoveredDevices = [];
  bool _isScanning = false;
  bool _isConnecting = false;
  String? _lastError;

  // Demo mode
  bool _isDemoMode = false;

  // Stream subscriptions
  StreamSubscription<List<ScanResult>>? _scanSubscription;
  StreamSubscription<BluetoothConnectionState>? _connectionSubscription;
  StreamSubscription<List<int>>? _statusSubscription;

  // Getters
  bool get isConnected => _connectedDevice != null || _isDemoMode;
  bool get isScanning => _isScanning;
  bool get isConnecting => _isConnecting;
  bool get isDemoMode => _isDemoMode;
  GateStatus? get currentStatus => _currentStatus;
  GateConfig? get currentConfig => _currentConfig;
  InputConfigData? get inputConfig => _inputConfig;
  InputStates? get inputStates => _inputStates;
  List<BleDeviceInfo> get discoveredDevices => _discoveredDevices;
  String? get lastError => _lastError;
  String? get connectedDeviceName =>
      _isDemoMode ? 'Demo Gate (Static UI)' : _connectedDevice?.platformName;

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
      final results = FlutterBluePlus.lastScanResults;
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

      // Find gate control characteristics
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

      // Find Configuration Service (optional - may not exist on all devices)
      try {
        final configService = services.firstWhere(
          (s) => s.uuid == _configurationServiceUuid,
        );

        _configDataChar = configService.characteristics.firstWhere(
          (c) => c.uuid == _configDataUuid,
        );

        _inputConfigChar = configService.characteristics.firstWhere(
          (c) => c.uuid == _inputConfigUuid,
        );
      } catch (e) {
        debugPrint("Configuration service not available: $e");
        _configDataChar = null;
        _inputConfigChar = null;
      }

      // Find Diagnostics Service (optional - may not exist on all devices)
      try {
        final diagnosticsService = services.firstWhere(
          (s) => s.uuid == _diagnosticsServiceUuid,
        );

        _inputStatesChar = diagnosticsService.characteristics.firstWhere(
          (c) => c.uuid == _inputStatesUuid,
        );
      } catch (e) {
        debugPrint("Diagnostics service not available: $e");
        _inputStatesChar = null;
      }

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
    // Handle demo mode
    if (_isDemoMode) {
      debugPrint("Demo mode: Simulating command: $command");
      _lastError = null;
      notifyListeners();
      return true;
    }

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

  /// Read configuration from BLE device
  Future<GateConfig?> readConfig() async {
    // Handle demo mode
    if (_isDemoMode) {
      debugPrint("Demo mode: Returning sample config");
      return _currentConfig;
    }

    if (_configDataChar == null) {
      _lastError = "Configuration characteristic not available";
      notifyListeners();
      return null;
    }

    try {
      debugPrint("Reading configuration...");
      final value = await _configDataChar!.read();
      if (value.isNotEmpty) {
        _currentConfig = GateConfig.fromBytes(value);
        debugPrint("Config loaded: $_currentConfig");
        notifyListeners();
        return _currentConfig;
      }
    } catch (e) {
      _lastError = "Failed to read config: $e";
      notifyListeners();
    }
    return null;
  }

  /// Write configuration to BLE device
  Future<bool> writeConfig(GateConfig config) async {
    // Handle demo mode
    if (_isDemoMode) {
      debugPrint("Demo mode: Simulating config write");
      _currentConfig = config;
      _lastError = null;
      notifyListeners();
      return true;
    }

    if (_configDataChar == null) {
      _lastError = "Configuration characteristic not available";
      notifyListeners();
      return false;
    }

    try {
      debugPrint("Writing configuration: $config");
      await _configDataChar!.write(config.toBytes(), withoutResponse: false);
      _currentConfig = config;
      _lastError = null;
      notifyListeners();
      return true;
    } catch (e) {
      _lastError = "Failed to write config: $e";
      notifyListeners();
      return false;
    }
  }

  /// Read input configuration from BLE device
  Future<InputConfigData?> readInputConfig() async {
    // Handle demo mode
    if (_isDemoMode) {
      debugPrint("Demo mode: Returning sample input config");
      return _inputConfig;
    }

    if (_inputConfigChar == null) {
      _lastError = "Input config characteristic not available";
      notifyListeners();
      return null;
    }

    try {
      debugPrint("Reading input configuration...");
      final value = await _inputConfigChar!.read();
      if (value.isNotEmpty) {
        _inputConfig = InputConfigData.fromBytes(value);
        debugPrint("Input config loaded: $_inputConfig");
        notifyListeners();
        return _inputConfig;
      }
    } catch (e) {
      _lastError = "Failed to read input config: $e";
      notifyListeners();
    }
    return null;
  }

  /// Read input states from BLE device
  Future<InputStates?> readInputStates() async {
    // Handle demo mode
    if (_isDemoMode) {
      debugPrint("Demo mode: Returning sample input states");
      return _inputStates;
    }

    if (_inputStatesChar == null) {
      _lastError = "Input states characteristic not available";
      notifyListeners();
      return null;
    }

    try {
      debugPrint("Reading input states...");
      final value = await _inputStatesChar!.read();
      if (value.isNotEmpty) {
        _inputStates = InputStates.fromBytes(value);
        debugPrint("Input states loaded: $_inputStates");
        notifyListeners();
        return _inputStates;
      }
    } catch (e) {
      _lastError = "Failed to read input states: $e";
      notifyListeners();
    }
    return null;
  }

  /// Enable demo mode with static sample data
  void enableDemoMode() {
    debugPrint('BleService: Entering enableDemoMode()');

    try {
      _isDemoMode = true;
      debugPrint('BleService: Set _isDemoMode = true');

      _currentStatus = GateStatus(
        state: GateState.idle,
        m1Percent: 45,
        m2Percent: 48,
        m1Speed: 0,
        m2Speed: 0,
        autoCloseCountdown: 0,
        timestamp: DateTime.now(),
      );
      debugPrint('BleService: Created _currentStatus');

      _currentConfig = GateConfig.defaults();
      debugPrint('BleService: Created _currentConfig');

      // Create sample input config
      debugPrint('BleService: Creating sample input config...');
      _inputConfig = InputConfigData(inputs: {
        'IN1': InputConfig(name: 'IN1', channel: 0, enabled: true, type: 'NC', function: 'cmd_open', description: 'Open command button'),
        'IN2': InputConfig(name: 'IN2', channel: 1, enabled: true, type: 'NO', function: 'cmd_close', description: 'Close command button'),
        'IN3': InputConfig(name: 'IN3', channel: 2, enabled: true, type: 'NO', function: 'cmd_stop', description: 'Stop command button'),
        'IN4': InputConfig(name: 'IN4', channel: 3, enabled: true, type: 'NC', function: 'photocell_closing', description: 'Closing photocell'),
        'IN5': InputConfig(name: 'IN5', channel: 4, enabled: true, type: 'NO', function: 'open_limit_m1', description: 'M1 Open Limit'),
        'IN6': InputConfig(name: 'IN6', channel: 5, enabled: true, type: '8K2', function: 'safety_stop_opening', description: 'Safety edge', tolerancePercent: 5.0, learnedResistance: 8200.0),
        'IN7': InputConfig(name: 'IN7', channel: 6, enabled: false, type: 'NO', function: null, description: 'Unassigned'),
        'IN8': InputConfig(name: 'IN8', channel: 7, enabled: false, type: 'NO', function: null, description: 'Unassigned'),
      });
      debugPrint('BleService: Created _inputConfig = $_inputConfig');

      // Create sample input states (some active, some inactive)
      debugPrint('BleService: Creating sample input states...');
      _inputStates = InputStates(
        states: {
          'IN1': false,
          'IN2': false,
          'IN3': false,
          'IN4': true,  // Photocell active
          'IN5': true,  // Limit switch active
          'IN6': false,
          'IN7': false,
          'IN8': false,
        },
        timestamp: DateTime.now(),
      );
      debugPrint('BleService: Created _inputStates = $_inputStates');

      _lastError = null;
      debugPrint('BleService: Calling notifyListeners()');
      notifyListeners();
      debugPrint('BleService: enableDemoMode() completed successfully');
    } catch (e, stackTrace) {
      debugPrint('BleService: ERROR in enableDemoMode(): $e');
      debugPrint('BleService: Stack trace: $stackTrace');
      _lastError = 'Demo mode error: $e';
      notifyListeners();
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
      _configDataChar = null;
      _inputConfigChar = null;
      _inputStatesChar = null;
      _currentStatus = null;
      _currentConfig = null;
      _inputConfig = null;
      _inputStates = null;
      _isDemoMode = false;

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
