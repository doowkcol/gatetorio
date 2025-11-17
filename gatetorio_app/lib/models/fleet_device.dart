/// Represents a single gate controller device in the fleet
class FleetDevice {
  final String deviceId;          // Hardware ID hash (e.g., "GT-A4F2B8C1")
  final String customName;        // User-defined name
  final String location;          // Installation site
  final bool isOnline;           // Current online status
  final DateTime lastSeen;       // Last heartbeat timestamp
  final int signalStrength;      // 0-100 percentage
  final String firmwareVersion;  // e.g., "1.2.3"
  final String gateType;         // "dual_motor" / "single_motor"
  final String? currentState;    // Current gate state (idle, opening, closing, etc.)

  FleetDevice({
    required this.deviceId,
    required this.customName,
    required this.location,
    required this.isOnline,
    required this.lastSeen,
    required this.signalStrength,
    required this.firmwareVersion,
    required this.gateType,
    this.currentState,
  });

  /// Get formatted device ID (short version)
  String get shortId {
    if (deviceId.length > 12) {
      return '${deviceId.substring(0, 12)}...';
    }
    return deviceId;
  }

  /// Get time since last seen as human-readable string
  String get timeSinceLastSeen {
    final duration = DateTime.now().difference(lastSeen);

    if (duration.inMinutes < 1) {
      return 'Just now';
    } else if (duration.inMinutes < 60) {
      return '${duration.inMinutes} min ago';
    } else if (duration.inHours < 24) {
      return '${duration.inHours} hour${duration.inHours > 1 ? 's' : ''} ago';
    } else {
      return '${duration.inDays} day${duration.inDays > 1 ? 's' : ''} ago';
    }
  }

  /// Get signal strength category
  SignalQuality get signalQuality {
    if (signalStrength >= 75) return SignalQuality.excellent;
    if (signalStrength >= 50) return SignalQuality.good;
    if (signalStrength >= 25) return SignalQuality.fair;
    return SignalQuality.poor;
  }

  /// Get gate type display name
  String get gateTypeDisplay {
    switch (gateType) {
      case 'dual_motor':
        return 'Dual Motor';
      case 'single_motor':
        return 'Single Motor';
      default:
        return 'Unknown';
    }
  }

  @override
  String toString() {
    return 'FleetDevice($customName, $deviceId, ${isOnline ? 'Online' : 'Offline'})';
  }
}

/// Signal quality categories
enum SignalQuality {
  excellent,
  good,
  fair,
  poor;

  String get displayName {
    switch (this) {
      case SignalQuality.excellent:
        return 'Excellent';
      case SignalQuality.good:
        return 'Good';
      case SignalQuality.fair:
        return 'Fair';
      case SignalQuality.poor:
        return 'Poor';
    }
  }
}
