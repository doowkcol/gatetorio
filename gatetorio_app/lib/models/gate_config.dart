import 'dart:convert';

/// Represents the gate controller configuration
/// Matches the JSON structure from gate_config.json
class GateConfig {
  // Basic timing settings
  final double motor1RunTime;
  final double motor2RunTime;
  final bool motor2Enabled;
  final double pauseTime;
  final double motor1OpenDelay;
  final double motor2CloseDelay;
  final double autoCloseTime;
  final bool autoCloseEnabled;
  final double safetyReverseTime;
  final double deadmanSpeed;
  final int stepLogicMode;
  final int partial1Percent;
  final int partial2Percent;
  final double partial1AutoCloseTime;
  final double partial2AutoCloseTime;
  final double partialReturnPause;

  // Limit switch configuration
  final bool motor1UseLimitSwitches;
  final bool motor2UseLimitSwitches;

  // Speed and slowdown settings
  final double openSpeed;
  final double closeSpeed;
  final double learningSpeed;
  final double openingSlowdownPercent;
  final double closingSlowdownPercent;

  // Learned travel times (optional)
  final double? learnedM1Open;
  final double? learnedM1Close;
  final double? learnedM2Open;
  final double? learnedM2Close;

  GateConfig({
    required this.motor1RunTime,
    required this.motor2RunTime,
    required this.motor2Enabled,
    required this.pauseTime,
    required this.motor1OpenDelay,
    required this.motor2CloseDelay,
    required this.autoCloseTime,
    required this.autoCloseEnabled,
    required this.safetyReverseTime,
    required this.deadmanSpeed,
    required this.stepLogicMode,
    required this.partial1Percent,
    required this.partial2Percent,
    required this.partial1AutoCloseTime,
    required this.partial2AutoCloseTime,
    required this.partialReturnPause,
    required this.motor1UseLimitSwitches,
    required this.motor2UseLimitSwitches,
    required this.openSpeed,
    required this.closeSpeed,
    required this.learningSpeed,
    required this.openingSlowdownPercent,
    required this.closingSlowdownPercent,
    this.learnedM1Open,
    this.learnedM1Close,
    this.learnedM2Open,
    this.learnedM2Close,
  });

  /// Parse from JSON received from BLE
  factory GateConfig.fromJson(Map<String, dynamic> json) {
    return GateConfig(
      motor1RunTime: (json['motor1_run_time'] ?? 15.0).toDouble(),
      motor2RunTime: (json['motor2_run_time'] ?? 15.0).toDouble(),
      motor2Enabled: json['motor2_enabled'] ?? true,
      pauseTime: (json['pause_time'] ?? 0.5).toDouble(),
      motor1OpenDelay: (json['motor1_open_delay'] ?? 0.0).toDouble(),
      motor2CloseDelay: (json['motor2_close_delay'] ?? 0.0).toDouble(),
      autoCloseTime: (json['auto_close_time'] ?? 60.0).toDouble(),
      autoCloseEnabled: json['auto_close_enabled'] ?? false,
      safetyReverseTime: (json['safety_reverse_time'] ?? 2.0).toDouble(),
      deadmanSpeed: (json['deadman_speed'] ?? 0.3).toDouble(),
      stepLogicMode: (json['step_logic_mode'] as num?)?.toInt() ?? 1,
      partial1Percent: (json['partial_1_percent'] as num?)?.toInt() ?? 30,
      partial2Percent: (json['partial_2_percent'] as num?)?.toInt() ?? 60,
      partial1AutoCloseTime: (json['partial_1_auto_close_time'] ?? 0.0).toDouble(),
      partial2AutoCloseTime: (json['partial_2_auto_close_time'] ?? 0.0).toDouble(),
      partialReturnPause: (json['partial_return_pause'] ?? 5.0).toDouble(),
      motor1UseLimitSwitches: json['motor1_use_limit_switches'] ?? false,
      motor2UseLimitSwitches: json['motor2_use_limit_switches'] ?? false,
      openSpeed: (json['open_speed'] ?? 1.0).toDouble(),
      closeSpeed: (json['close_speed'] ?? 1.0).toDouble(),
      learningSpeed: (json['learning_speed'] ?? 0.3).toDouble(),
      openingSlowdownPercent: (json['opening_slowdown_percent'] ?? 2.0).toDouble(),
      closingSlowdownPercent: (json['closing_slowdown_percent'] ?? 10.0).toDouble(),
      learnedM1Open: json['learned_m1_open']?.toDouble(),
      learnedM1Close: json['learned_m1_close']?.toDouble(),
      learnedM2Open: json['learned_m2_open']?.toDouble(),
      learnedM2Close: json['learned_m2_close']?.toDouble(),
    );
  }

  /// Parse from raw bytes received from BLE characteristic
  factory GateConfig.fromBytes(List<int> bytes) {
    final jsonString = utf8.decode(bytes);
    final json = jsonDecode(jsonString) as Map<String, dynamic>;
    return GateConfig.fromJson(json);
  }

  /// Convert to JSON for BLE transmission
  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{
      'motor1_run_time': motor1RunTime,
      'motor2_run_time': motor2RunTime,
      'motor2_enabled': motor2Enabled,
      'pause_time': pauseTime,
      'motor1_open_delay': motor1OpenDelay,
      'motor2_close_delay': motor2CloseDelay,
      'auto_close_time': autoCloseTime,
      'auto_close_enabled': autoCloseEnabled,
      'safety_reverse_time': safetyReverseTime,
      'deadman_speed': deadmanSpeed,
      'step_logic_mode': stepLogicMode,
      'partial_1_percent': partial1Percent,
      'partial_2_percent': partial2Percent,
      'partial_1_auto_close_time': partial1AutoCloseTime,
      'partial_2_auto_close_time': partial2AutoCloseTime,
      'partial_return_pause': partialReturnPause,
      'motor1_use_limit_switches': motor1UseLimitSwitches,
      'motor2_use_limit_switches': motor2UseLimitSwitches,
      'open_speed': openSpeed,
      'close_speed': closeSpeed,
      'learning_speed': learningSpeed,
      'opening_slowdown_percent': openingSlowdownPercent,
      'closing_slowdown_percent': closingSlowdownPercent,
    };

    // Only include learned times if they exist
    if (learnedM1Open != null) json['learned_m1_open'] = learnedM1Open;
    if (learnedM1Close != null) json['learned_m1_close'] = learnedM1Close;
    if (learnedM2Open != null) json['learned_m2_open'] = learnedM2Open;
    if (learnedM2Close != null) json['learned_m2_close'] = learnedM2Close;

    return json;
  }

  /// Convert to bytes for BLE write operation
  List<int> toBytes() {
    return utf8.encode(jsonEncode(toJson()));
  }

  /// Create a copy with modified fields
  GateConfig copyWith({
    double? motor1RunTime,
    double? motor2RunTime,
    bool? motor2Enabled,
    double? pauseTime,
    double? motor1OpenDelay,
    double? motor2CloseDelay,
    double? autoCloseTime,
    bool? autoCloseEnabled,
    double? safetyReverseTime,
    double? deadmanSpeed,
    int? stepLogicMode,
    int? partial1Percent,
    int? partial2Percent,
    double? partial1AutoCloseTime,
    double? partial2AutoCloseTime,
    double? partialReturnPause,
    bool? motor1UseLimitSwitches,
    bool? motor2UseLimitSwitches,
    double? openSpeed,
    double? closeSpeed,
    double? learningSpeed,
    double? openingSlowdownPercent,
    double? closingSlowdownPercent,
    double? learnedM1Open,
    double? learnedM1Close,
    double? learnedM2Open,
    double? learnedM2Close,
  }) {
    return GateConfig(
      motor1RunTime: motor1RunTime ?? this.motor1RunTime,
      motor2RunTime: motor2RunTime ?? this.motor2RunTime,
      motor2Enabled: motor2Enabled ?? this.motor2Enabled,
      pauseTime: pauseTime ?? this.pauseTime,
      motor1OpenDelay: motor1OpenDelay ?? this.motor1OpenDelay,
      motor2CloseDelay: motor2CloseDelay ?? this.motor2CloseDelay,
      autoCloseTime: autoCloseTime ?? this.autoCloseTime,
      autoCloseEnabled: autoCloseEnabled ?? this.autoCloseEnabled,
      safetyReverseTime: safetyReverseTime ?? this.safetyReverseTime,
      deadmanSpeed: deadmanSpeed ?? this.deadmanSpeed,
      stepLogicMode: stepLogicMode ?? this.stepLogicMode,
      partial1Percent: partial1Percent ?? this.partial1Percent,
      partial2Percent: partial2Percent ?? this.partial2Percent,
      partial1AutoCloseTime: partial1AutoCloseTime ?? this.partial1AutoCloseTime,
      partial2AutoCloseTime: partial2AutoCloseTime ?? this.partial2AutoCloseTime,
      partialReturnPause: partialReturnPause ?? this.partialReturnPause,
      motor1UseLimitSwitches: motor1UseLimitSwitches ?? this.motor1UseLimitSwitches,
      motor2UseLimitSwitches: motor2UseLimitSwitches ?? this.motor2UseLimitSwitches,
      openSpeed: openSpeed ?? this.openSpeed,
      closeSpeed: closeSpeed ?? this.closeSpeed,
      learningSpeed: learningSpeed ?? this.learningSpeed,
      openingSlowdownPercent: openingSlowdownPercent ?? this.openingSlowdownPercent,
      closingSlowdownPercent: closingSlowdownPercent ?? this.closingSlowdownPercent,
      learnedM1Open: learnedM1Open ?? this.learnedM1Open,
      learnedM1Close: learnedM1Close ?? this.learnedM1Close,
      learnedM2Open: learnedM2Open ?? this.learnedM2Open,
      learnedM2Close: learnedM2Close ?? this.learnedM2Close,
    );
  }

  /// Create default configuration
  factory GateConfig.defaults() {
    return GateConfig(
      motor1RunTime: 15.0,
      motor2RunTime: 15.0,
      motor2Enabled: true,
      pauseTime: 0.5,
      motor1OpenDelay: 0.0,
      motor2CloseDelay: 0.0,
      autoCloseTime: 60.0,
      autoCloseEnabled: false,
      safetyReverseTime: 2.0,
      deadmanSpeed: 0.3,
      stepLogicMode: 1,
      partial1Percent: 30,
      partial2Percent: 60,
      partial1AutoCloseTime: 0.0,
      partial2AutoCloseTime: 0.0,
      partialReturnPause: 5.0,
      motor1UseLimitSwitches: false,
      motor2UseLimitSwitches: false,
      openSpeed: 1.0,
      closeSpeed: 1.0,
      learningSpeed: 0.3,
      openingSlowdownPercent: 2.0,
      closingSlowdownPercent: 10.0,
    );
  }

  @override
  String toString() {
    return 'GateConfig(m1: ${motor1RunTime}s, m2: ${motor2RunTime}s, '
        'autoClose: $autoCloseEnabled, speeds: O${openSpeed}/C${closeSpeed})';
  }
}
