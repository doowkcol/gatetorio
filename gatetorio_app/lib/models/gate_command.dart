import 'dart:convert';

/// Represents a command to send to the gate controller
/// Matches the JSON structure expected by BLE Command TX characteristic (00001001-4751...)
class GateCommand {
  final String cmd;
  final String? key;
  final dynamic value;
  final int? timestamp;

  GateCommand({
    required this.cmd,
    this.key,
    this.value,
    this.timestamp,
  });

  /// Create a pulse command (standard gate control)
  factory GateCommand.pulse(String key) {
    return GateCommand(
      cmd: 'pulse',
      key: key,
      timestamp: DateTime.now().millisecondsSinceEpoch ~/ 1000,
    );
  }

  /// Create an engineer pulse command (direct motor control - bypasses safety!)
  factory GateCommand.engineerPulse(String key) {
    return GateCommand(
      cmd: 'engineer_pulse',
      key: key,
      timestamp: DateTime.now().millisecondsSinceEpoch ~/ 1000,
    );
  }

  /// Pre-defined standard commands
  static GateCommand get open => GateCommand.pulse('cmd_open');
  static GateCommand get close => GateCommand.pulse('cmd_close');
  static GateCommand get stop => GateCommand.pulse('cmd_stop');
  static GateCommand get partial1 => GateCommand.pulse('partial_1');
  static GateCommand get partial2 => GateCommand.pulse('partial_2');
  static GateCommand get stepLogic => GateCommand.pulse('step_logic');

  /// Engineer mode commands (use with caution!)
  static GateCommand get motor1Open => GateCommand.engineerPulse('motor1_open');
  static GateCommand get motor1Close =>
      GateCommand.engineerPulse('motor1_close');
  static GateCommand get motor2Open => GateCommand.engineerPulse('motor2_open');
  static GateCommand get motor2Close =>
      GateCommand.engineerPulse('motor2_close');

  /// Configuration commands
  static GateCommand get getConfig => GateCommand(cmd: 'get_config');
  static GateCommand get reloadConfig => GateCommand(cmd: 'reload_config');
  static GateCommand get saveLearned =>
      GateCommand(cmd: 'save_learned_times');

  /// System commands
  static GateCommand get reboot => GateCommand(cmd: 'reboot');
  static GateCommand get getDiagnostics =>
      GateCommand(cmd: 'get_diagnostics');

  /// Auto-learn commands
  static GateCommand get startAutoLearn => GateCommand(cmd: 'start_auto_learn');
  static GateCommand get stopAutoLearn => GateCommand(cmd: 'stop_auto_learn');
  static GateCommand get getAutoLearnStatus =>
      GateCommand(cmd: 'get_auto_learn_status');

  static GateCommand enableEngineerMode(bool enable) {
    return GateCommand(
      cmd: 'enable_engineer_mode',
      value: enable,
    );
  }

  static GateCommand setConfig(Map<String, dynamic> config) {
    return GateCommand(
      cmd: 'set_config',
      value: config,
    );
  }

  /// Convert to JSON for BLE transmission
  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{'cmd': cmd};

    if (key != null) json['key'] = key;
    if (value != null) json['value'] = value;
    if (timestamp != null) json['timestamp'] = timestamp;

    return json;
  }

  /// Convert to bytes for BLE write operation
  List<int> toBytes() {
    return utf8.encode(jsonEncode(toJson()));
  }

  @override
  String toString() {
    return 'GateCommand(${toJson()})';
  }
}
