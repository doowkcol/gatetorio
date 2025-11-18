import 'dart:convert';
import 'gate_config.dart';
import 'input_config.dart';

/// Represents a device that has been previously connected/whitelisted
/// Allows reconnection to stealth-mode devices and viewing cached data offline
class KnownDevice {
  final String deviceId;        // BLE MAC address or unique identifier
  final String? customName;     // User-assigned friendly name
  final String? manufacturerName; // From BLE device info
  final DateTime firstSeen;     // When first discovered/connected
  final DateTime lastSeen;      // Last successful connection

  // Cached data (last known state)
  final GateConfig? cachedConfig;
  final InputConfigData? cachedInputConfig;

  // Connection info
  final String? ipAddress;      // For web access
  final String? lastKnownRssi;  // Signal strength when last seen

  KnownDevice({
    required this.deviceId,
    this.customName,
    this.manufacturerName,
    required this.firstSeen,
    required this.lastSeen,
    this.cachedConfig,
    this.cachedInputConfig,
    this.ipAddress,
    this.lastKnownRssi,
  });

  /// Get display name (custom name if set, otherwise manufacturer name or device ID)
  String get displayName {
    if (customName != null && customName!.isNotEmpty) {
      return customName!;
    }
    if (manufacturerName != null && manufacturerName!.isNotEmpty) {
      return manufacturerName!;
    }
    // Return last 6 chars of device ID as fallback
    return deviceId.length > 6 ? deviceId.substring(deviceId.length - 6) : deviceId;
  }

  /// Check if device was seen recently (within last 5 minutes)
  bool get isOnline {
    return DateTime.now().difference(lastSeen).inMinutes < 5;
  }

  /// Get human-readable "last seen" string
  String get lastSeenString {
    if (isOnline) return 'Online';

    final diff = DateTime.now().difference(lastSeen);

    if (diff.inMinutes < 60) {
      return '${diff.inMinutes}m ago';
    } else if (diff.inHours < 24) {
      return '${diff.inHours}h ago';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}d ago';
    } else {
      return '${(diff.inDays / 7).floor()}w ago';
    }
  }

  /// Convert to JSON for persistence
  Map<String, dynamic> toJson() {
    return {
      'deviceId': deviceId,
      'customName': customName,
      'manufacturerName': manufacturerName,
      'firstSeen': firstSeen.toIso8601String(),
      'lastSeen': lastSeen.toIso8601String(),
      'cachedConfig': cachedConfig?.toJson(),
      'cachedInputConfig': cachedInputConfig?.toJson(),
      'ipAddress': ipAddress,
      'lastKnownRssi': lastKnownRssi,
    };
  }

  /// Create from JSON
  factory KnownDevice.fromJson(Map<String, dynamic> json) {
    return KnownDevice(
      deviceId: json['deviceId'] as String,
      customName: json['customName'] as String?,
      manufacturerName: json['manufacturerName'] as String?,
      firstSeen: DateTime.parse(json['firstSeen'] as String),
      lastSeen: DateTime.parse(json['lastSeen'] as String),
      cachedConfig: json['cachedConfig'] != null
          ? GateConfig.fromJson(json['cachedConfig'] as Map<String, dynamic>)
          : null,
      cachedInputConfig: json['cachedInputConfig'] != null
          ? InputConfigData.fromJson(json['cachedInputConfig'] as Map<String, dynamic>)
          : null,
      ipAddress: json['ipAddress'] as String?,
      lastKnownRssi: json['lastKnownRssi'] as String?,
    );
  }

  /// Create a copy with updated fields
  KnownDevice copyWith({
    String? deviceId,
    String? customName,
    String? manufacturerName,
    DateTime? firstSeen,
    DateTime? lastSeen,
    GateConfig? cachedConfig,
    InputConfigData? cachedInputConfig,
    String? ipAddress,
    String? lastKnownRssi,
  }) {
    return KnownDevice(
      deviceId: deviceId ?? this.deviceId,
      customName: customName ?? this.customName,
      manufacturerName: manufacturerName ?? this.manufacturerName,
      firstSeen: firstSeen ?? this.firstSeen,
      lastSeen: lastSeen ?? this.lastSeen,
      cachedConfig: cachedConfig ?? this.cachedConfig,
      cachedInputConfig: cachedInputConfig ?? this.cachedInputConfig,
      ipAddress: ipAddress ?? this.ipAddress,
      lastKnownRssi: lastKnownRssi ?? this.lastKnownRssi,
    );
  }

  @override
  String toString() {
    return 'KnownDevice($displayName, $deviceId, ${isOnline ? "online" : lastSeenString})';
  }
}
