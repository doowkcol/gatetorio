/// Represents a discovered Gatetorio BLE device
class BleDeviceInfo {
  final String deviceId;
  final String deviceName;
  final int rssi;
  final bool isConnected;

  BleDeviceInfo({
    required this.deviceId,
    required this.deviceName,
    required this.rssi,
    this.isConnected = false,
  });

  /// Check if this is likely a Gatetorio device
  bool get isGatetorioDevice {
    return deviceName.toLowerCase().contains('gatetorio');
  }

  /// Get signal strength category
  SignalStrength get signalStrength {
    if (rssi >= -50) return SignalStrength.excellent;
    if (rssi >= -60) return SignalStrength.good;
    if (rssi >= -70) return SignalStrength.fair;
    return SignalStrength.poor;
  }

  @override
  String toString() {
    return 'BleDeviceInfo(name: $deviceName, id: $deviceId, rssi: $rssi, connected: $isConnected)';
  }
}

enum SignalStrength {
  excellent,
  good,
  fair,
  poor;

  String get displayName {
    switch (this) {
      case SignalStrength.excellent:
        return 'Excellent';
      case SignalStrength.good:
        return 'Good';
      case SignalStrength.fair:
        return 'Fair';
      case SignalStrength.poor:
        return 'Poor';
    }
  }

  int get bars {
    switch (this) {
      case SignalStrength.excellent:
        return 4;
      case SignalStrength.good:
        return 3;
      case SignalStrength.fair:
        return 2;
      case SignalStrength.poor:
        return 1;
    }
  }
}
