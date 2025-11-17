import 'dart:convert';

/// Represents the current status of the gate system
/// Matches the JSON structure from BLE Status characteristic (00001003-4751...)
class GateStatus {
  final GateState state;
  final int m1Percent;
  final int m2Percent;
  final double m1Speed;  // 0.0 to 1.0 (motor speed as fraction of max)
  final double m2Speed;  // 0.0 to 1.0 (motor speed as fraction of max)
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
      m1Speed: (json['m1_speed'] as num?)?.toDouble() ?? 0.0,
      m2Speed: (json['m2_speed'] as num?)?.toDouble() ?? 0.0,
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

  /// Check if basic commands (OPEN, CLOSE, STOP) can be sent in the current state
  bool get canSendCommand => state.canSendCommand;

  /// Check if partial position commands (PO1, PO2) can be sent in the current state
  bool get canSendPartialCommand => state.canSendPartialCommand;

  /// Get M1 speed as percentage (0-100)
  int get m1SpeedPercent => (m1Speed * 100).round();

  /// Get M2 speed as percentage (0-100)
  int get m2SpeedPercent => (m2Speed * 100).round();

  @override
  String toString() {
    return 'GateStatus(state: $state, m1: $m1Percent%, m2: $m2Percent%, '
        'm1Speed: $m1SpeedPercent%, m2Speed: $m2SpeedPercent%, autoClose: $autoCloseCountdown)';
  }
}

/// Gate state enum matching the Python backend states
enum GateState {
  // Primary states (gate at rest)
  closed,            // Gate fully closed
  open,              // Gate fully open
  partial1,          // Gate at partial position 1
  partial2,          // Gate at partial position 2
  stopped,           // Gate stopped mid-movement
  unknown,           // Position unknown (power-on state)

  // Movement states
  opening,           // Opening to full open
  closing,           // Closing to full closed
  openingToPartial1, // Moving to partial position 1
  openingToPartial2, // Moving to partial position 2
  closingToPartial1, // Closing to partial position 1
  closingToPartial2, // Closing to partial position 2

  // Safety reversal states
  reversingFromOpen,  // Reversing after obstacle while opening
  reversingFromClose, // Reversing after obstacle while closing

  // Legacy/future states
  error,              // Error state
  calibrating;        // Calibration in progress

  static GateState fromString(String state) {
    switch (state.toUpperCase()) {
      // Primary states
      case 'CLOSED':
        return GateState.closed;
      case 'OPEN':
        return GateState.open;
      case 'PARTIAL_1':
      case 'PARTIAL1':
        return GateState.partial1;
      case 'PARTIAL_2':
      case 'PARTIAL2':
        return GateState.partial2;
      case 'STOPPED':
        return GateState.stopped;
      case 'UNKNOWN':
        return GateState.unknown;

      // Movement states
      case 'OPENING':
        return GateState.opening;
      case 'CLOSING':
        return GateState.closing;
      case 'OPENING_TO_PARTIAL_1':
      case 'OPENING_TO_PARTIAL1':
        return GateState.openingToPartial1;
      case 'OPENING_TO_PARTIAL_2':
      case 'OPENING_TO_PARTIAL2':
        return GateState.openingToPartial2;
      case 'CLOSING_TO_PARTIAL_1':
      case 'CLOSING_TO_PARTIAL1':
        return GateState.closingToPartial1;
      case 'CLOSING_TO_PARTIAL_2':
      case 'CLOSING_TO_PARTIAL2':
        return GateState.closingToPartial2;

      // Safety reversal states
      case 'REVERSING_FROM_OPEN':
        return GateState.reversingFromOpen;
      case 'REVERSING_FROM_CLOSE':
        return GateState.reversingFromClose;

      // Legacy states (for backward compatibility)
      case 'IDLE':
        return GateState.closed; // Map old IDLE to CLOSED
      case 'PARTIAL_OPEN':
      case 'PARTIALOPEN':
        return GateState.partial1; // Map old PARTIAL_OPEN to PARTIAL_1
      case 'ERROR':
        return GateState.error;
      case 'CALIBRATING':
        return GateState.calibrating;

      default:
        return GateState.unknown;
    }
  }

  String get displayName {
    switch (this) {
      case GateState.closed:
        return 'Closed';
      case GateState.open:
        return 'Open';
      case GateState.partial1:
        return 'Partial 1';
      case GateState.partial2:
        return 'Partial 2';
      case GateState.stopped:
        return 'Stopped';
      case GateState.unknown:
        return 'Unknown';
      case GateState.opening:
        return 'Opening';
      case GateState.closing:
        return 'Closing';
      case GateState.openingToPartial1:
        return 'Opening to P1';
      case GateState.openingToPartial2:
        return 'Opening to P2';
      case GateState.closingToPartial1:
        return 'Closing to P1';
      case GateState.closingToPartial2:
        return 'Closing to P2';
      case GateState.reversingFromOpen:
        return 'Safety Reverse';
      case GateState.reversingFromClose:
        return 'Safety Reverse';
      case GateState.error:
        return 'Error';
      case GateState.calibrating:
        return 'Calibrating';
    }
  }

  bool get isMoving =>
      this == GateState.opening ||
      this == GateState.closing ||
      this == GateState.openingToPartial1 ||
      this == GateState.openingToPartial2 ||
      this == GateState.closingToPartial1 ||
      this == GateState.closingToPartial2 ||
      this == GateState.reversingFromOpen ||
      this == GateState.reversingFromClose;

  /// Can send basic commands (OPEN, CLOSE, STOP)
  /// Only blocked in ERROR state
  bool get canSendCommand => this != GateState.error;

  /// Can send partial position commands (PO1, PO2)
  /// Requires known position - blocked in UNKNOWN and ERROR states
  bool get canSendPartialCommand =>
      this != GateState.error && this != GateState.unknown;
}
