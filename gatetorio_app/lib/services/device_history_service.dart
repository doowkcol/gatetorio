import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/known_device.dart';
import '../models/gate_config.dart';
import '../models/input_config.dart';

/// Service for managing known/whitelisted devices
/// Persists device history to local storage for reconnection and offline viewing
class DeviceHistoryService extends ChangeNotifier {
  static const String _storageKey = 'known_devices';

  final Map<String, KnownDevice> _knownDevices = {};
  bool _isLoaded = false;

  /// Get list of all known devices sorted by last seen (most recent first)
  List<KnownDevice> get knownDevices {
    final devices = _knownDevices.values.toList();
    devices.sort((a, b) => b.lastSeen.compareTo(a.lastSeen));
    return devices;
  }

  /// Get a specific device by ID
  KnownDevice? getDevice(String deviceId) {
    return _knownDevices[deviceId];
  }

  /// Check if a device is known
  bool isKnown(String deviceId) {
    return _knownDevices.containsKey(deviceId);
  }

  /// Initialize - load saved devices from storage
  Future<void> initialize() async {
    if (_isLoaded) return;

    debugPrint('[DeviceHistory] Loading known devices from storage...');
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString(_storageKey);

      if (jsonString != null) {
        final List<dynamic> jsonList = jsonDecode(jsonString);
        _knownDevices.clear();

        for (final json in jsonList) {
          try {
            final device = KnownDevice.fromJson(json as Map<String, dynamic>);
            _knownDevices[device.deviceId] = device;
          } catch (e) {
            debugPrint('[DeviceHistory] Error parsing device: $e');
          }
        }

        debugPrint('[DeviceHistory] Loaded ${_knownDevices.length} known devices');
      } else {
        debugPrint('[DeviceHistory] No saved devices found');
      }

      _isLoaded = true;
      notifyListeners();
    } catch (e) {
      debugPrint('[DeviceHistory] Error loading devices: $e');
    }
  }

  /// Save devices to storage
  Future<void> _saveToStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonList = _knownDevices.values.map((d) => d.toJson()).toList();
      final jsonString = jsonEncode(jsonList);
      await prefs.setString(_storageKey, jsonString);
      debugPrint('[DeviceHistory] Saved ${_knownDevices.length} devices to storage');
    } catch (e) {
      debugPrint('[DeviceHistory] Error saving devices: $e');
    }
  }

  /// Add or update a known device
  Future<void> addOrUpdateDevice({
    required String deviceId,
    String? customName,
    String? manufacturerName,
    GateConfig? cachedConfig,
    InputConfigData? cachedInputConfig,
    String? ipAddress,
    String? lastKnownRssi,
  }) async {
    final now = DateTime.now();
    final existing = _knownDevices[deviceId];

    if (existing != null) {
      // Update existing device
      _knownDevices[deviceId] = existing.copyWith(
        customName: customName ?? existing.customName,
        manufacturerName: manufacturerName ?? existing.manufacturerName,
        lastSeen: now,
        cachedConfig: cachedConfig ?? existing.cachedConfig,
        cachedInputConfig: cachedInputConfig ?? existing.cachedInputConfig,
        ipAddress: ipAddress ?? existing.ipAddress,
        lastKnownRssi: lastKnownRssi ?? existing.lastKnownRssi,
      );
      debugPrint('[DeviceHistory] Updated device: $deviceId');
    } else {
      // Add new device
      _knownDevices[deviceId] = KnownDevice(
        deviceId: deviceId,
        customName: customName,
        manufacturerName: manufacturerName,
        firstSeen: now,
        lastSeen: now,
        cachedConfig: cachedConfig,
        cachedInputConfig: cachedInputConfig,
        ipAddress: ipAddress,
        lastKnownRssi: lastKnownRssi,
      );
      debugPrint('[DeviceHistory] Added new device: $deviceId');
    }

    await _saveToStorage();
    notifyListeners();
  }

  /// Update device's cached configuration
  Future<void> updateCachedConfig({
    required String deviceId,
    GateConfig? config,
    InputConfigData? inputConfig,
  }) async {
    final device = _knownDevices[deviceId];
    if (device == null) return;

    _knownDevices[deviceId] = device.copyWith(
      cachedConfig: config ?? device.cachedConfig,
      cachedInputConfig: inputConfig ?? device.cachedInputConfig,
      lastSeen: DateTime.now(),
    );

    await _saveToStorage();
    notifyListeners();
  }

  /// Update custom name for a device
  Future<void> updateDeviceName(String deviceId, String customName) async {
    final device = _knownDevices[deviceId];
    if (device == null) return;

    _knownDevices[deviceId] = device.copyWith(customName: customName);
    await _saveToStorage();
    notifyListeners();
  }

  /// Remove a device from history
  Future<void> removeDevice(String deviceId) async {
    if (_knownDevices.remove(deviceId) != null) {
      debugPrint('[DeviceHistory] Removed device: $deviceId');
      await _saveToStorage();
      notifyListeners();
    }
  }

  /// Clear all known devices
  Future<void> clearAll() async {
    _knownDevices.clear();
    await _saveToStorage();
    notifyListeners();
    debugPrint('[DeviceHistory] Cleared all devices');
  }

  /// Touch device to update last seen timestamp
  Future<void> touchDevice(String deviceId) async {
    final device = _knownDevices[deviceId];
    if (device == null) return;

    _knownDevices[deviceId] = device.copyWith(lastSeen: DateTime.now());
    await _saveToStorage();
    notifyListeners();
  }

  @override
  void dispose() {
    _knownDevices.clear();
    super.dispose();
  }
}
