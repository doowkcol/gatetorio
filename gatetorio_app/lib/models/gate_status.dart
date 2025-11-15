import 'dart:convert';

/// Represents the current status of the gate system
/// Matches the JSON structure from BLE Status characteristic (00001003-4751...)
class GateStatus {
  final GateState state;
  final int m1Percent;
  final int m2Percent;
  final int m1Speed;
  final int m2Speed;
  final int autoCloseCountdown;
  final DateTime timestamp;

  GateStatus({
    required this.state,
    required this.m1Percent,
    required this.m2Percent,
    required this.m1Speed,
    required this.m2Speed,
    required this.autoCloseCountdown,
    required this.timestamp,
  });

  /// Parse from JSON received from BLE
  factory GateStatus.fromJson(Map<String, dynamic> json) {
    return GateStatus(
      state: GateState.fromString(json['state'] ?? 'UNKNOWN'),
      m1Percent: (json['m1_percent'] as num?)?.toInt() ?? 0,
      m2Percent: (json['m2_percent'] as num?)?.toInt() ?? 0,
      m1Speed: (json['m1_speed'] as num?)?.toInt() ?? 0,
      m2Speed: (json['m2_speed'] as num?)?.toInt() ?? 0,
      autoCloseCountdown: (json['auto_close_countdown'] as num?)?.toInt() ?? 0,
      timestamp: DateTime.fromMillisecondsSinceEpoch(
        ((json['timestamp'] as num?) ?? 0).toInt() * 1000,
      ),
    );
  }

  /// Parse from raw bytes received from BLE characteristic
  factory GateStatus.fromBytes(List<int> bytes) {
    final jsonString = utf8.decode(bytes);
    final json = jsonDecode(jsonString) as Map<String, dynamic>;
    return GateStatus.fromJson(json);
  }

  /// Check if commands can be sent in the current state
  bool get canSendCommand => state.canSendCommand;

  @override
  String toString() {
    return 'GateStatus(state: $state, m1: $m1Percent%, m2: $m2Percent%, '
        'm1Speed: $m1Speed, m2Speed: $m2Speed, autoClose: $autoCloseCountdown)';
  }
}

/// Gate state enum matching the Python backend states
enum GateState {
  unknown,
  idle,
  opening,
  closing,
  partialOpen,
  error,
  calibrating,
  stopped;

  static GateState fromString(String state) {
    switch (state.toUpperCase()) {
      case 'IDLE':
        return GateState.idle;
      case 'OPENING':
        return GateState.opening;
      case 'CLOSING':
        return GateState.closing;
      case 'PARTIAL_OPEN':
      case 'PARTIALOPEN':
        return GateState.partialOpen;
      case 'ERROR':
        return GateState.error;
      case 'CALIBRATING':
        return GateState.calibrating;
      case 'STOPPED':
        return GateState.stopped;
      default:
        return GateState.unknown;
    }
  }

  String get displayName {
    switch (this) {
      case GateState.idle:
        return 'Idle';
      case GateState.opening:
        return 'Opening';
      case GateState.closing:
        return 'Closing';
      case GateState.partialOpen:
        return 'Partial Open';
      case GateState.error:
        return 'Error';
      case GateState.calibrating:
        return 'Calibrating';
      case GateState.stopped:
        return 'Stopped';
      case GateState.unknown:
        return 'Unknown';
    }
  }

  bool get isMoving =>
      this == GateState.opening || this == GateState.closing;

  bool get canSendCommand =>
      this != GateState.error && this != GateState.unknown;
}
