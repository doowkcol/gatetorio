import 'dart:convert';

/// Represents the configuration of a single input
class InputConfig {
  final String name;
  final int channel;
  final bool enabled;
  final String type; // NO, NC, or 8K2
  final String? function;
  final String description;
  final double? tolerancePercent; // For 8K2 type
  final double? learnedResistance; // For 8K2 type

  InputConfig({
    required this.name,
    required this.channel,
    required this.enabled,
    required this.type,
    this.function,
    required this.description,
    this.tolerancePercent,
    this.learnedResistance,
  });

  /// Parse from JSON received from BLE
  /// Supports both old format and new compact format with keys:
  /// - "c" = channel
  /// - "e" = enabled
  /// - "t" = type
  /// - "f" = function
  /// - "d" = description
  factory InputConfig.fromJson(String name, Map<String, dynamic> json) {
    return InputConfig(
      name: name,
      channel: (json['c'] ?? json['channel'] as num?)?.toInt() ?? 0,
      enabled: json['e'] ?? json['enabled'] ?? true,
      type: json['t'] ?? json['type'] ?? 'NO',
      function: json['f'] ?? json['function'],
      description: json['d'] ?? json['description'] ?? '',
      tolerancePercent: (json['tol'] ?? json['tolerance_percent'] as num?)?.toDouble(),
      learnedResistance: (json['lr'] ?? json['learned_resistance'] as num?)?.toDouble(),
    );
  }

  /// Convert to JSON for BLE transmission
  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{
      'channel': channel,
      'enabled': enabled,
      'type': type,
      'description': description,
    };

    if (function != null) json['function'] = function;
    if (tolerancePercent != null) json['tolerance_percent'] = tolerancePercent;
    if (learnedResistance != null) json['learned_resistance'] = learnedResistance;

    return json;
  }

  /// Get ADC number (1 or 2)
  int get adcNumber => channel < 4 ? 1 : 2;

  /// Get physical channel on the ADC (0-3)
  int get physicalChannel => channel % 4;

  /// Get ADC label string
  String get adcLabel => 'ADC$adcNumber CH$physicalChannel';

  /// Get function display name
  String get functionDisplayName {
    if (function == null || function!.isEmpty) return '[Unassigned]';
    return _formatFunctionName(function!);
  }

  /// Format function name for display
  String _formatFunctionName(String func) {
    // Convert snake_case to Title Case
    return func
        .split('_')
        .map((word) => word[0].toUpperCase() + word.substring(1))
        .join(' ');
  }

  @override
  String toString() {
    return 'InputConfig($name, CH$channel, $type, $functionDisplayName)';
  }
}

/// Container for all input configurations
class InputConfigData {
  final Map<String, InputConfig> inputs;

  InputConfigData({required this.inputs});

  /// Parse from JSON received from BLE
  /// Supports both old format with wrapper and new compact format:
  /// - Old: {"inputs": {"IN1": {...}, "IN2": {...}}}
  /// - New: {"IN1": {...}, "IN2": {...}}
  factory InputConfigData.fromJson(Map<String, dynamic> json) {
    Map<String, dynamic> inputsMap;

    // Check if using old format (has 'inputs' wrapper) or new compact format
    if (json.containsKey('inputs')) {
      // Old format with wrapper
      inputsMap = json['inputs'] as Map<String, dynamic>? ?? {};
    } else {
      // New compact format - input names are at top level
      inputsMap = json;
    }

    final inputs = <String, InputConfig>{};

    inputsMap.forEach((key, value) {
      if (value is Map<String, dynamic>) {
        inputs[key] = InputConfig.fromJson(key, value);
      }
    });

    return InputConfigData(inputs: inputs);
  }

  /// Parse from raw bytes received from BLE characteristic
  factory InputConfigData.fromBytes(List<int> bytes) {
    final jsonString = utf8.decode(bytes);
    final json = jsonDecode(jsonString) as Map<String, dynamic>;
    return InputConfigData.fromJson(json);
  }

  /// Convert to JSON for BLE transmission
  Map<String, dynamic> toJson() {
    final inputsJson = <String, dynamic>{};
    inputs.forEach((key, value) {
      inputsJson[key] = value.toJson();
    });
    return {'inputs': inputsJson};
  }

  /// Convert to bytes for BLE write operation
  List<int> toBytes() {
    return utf8.encode(jsonEncode(toJson()));
  }

  /// Get sorted list of input names
  List<String> get sortedInputNames {
    final names = inputs.keys.toList();
    names.sort();
    return names;
  }

  @override
  String toString() {
    return 'InputConfigData(${inputs.length} inputs)';
  }
}

/// Represents the live state of inputs
class InputStates {
  final Map<String, bool> states; // input name -> active state
  final Map<String, double> rawValues; // input name -> raw value (optional)
  final DateTime timestamp;

  InputStates({
    required this.states,
    this.rawValues = const {},
    required this.timestamp,
  });

  /// Parse from JSON received from BLE
  /// Supports both old format and new compact format with keys:
  /// - "a" = active (replaces "active")
  /// - "f" = function (replaces "function")
  /// - "t" = type (replaces "type")
  /// - "c" = channel (replaces "channel")
  factory InputStates.fromJson(Map<String, dynamic> json) {
    final statesMap = <String, bool>{};
    final rawValuesMap = <String, double>{};

    // Check if using old format (has 'states' key) or new compact format
    if (json.containsKey('states')) {
      // OLD FORMAT: {"states": {"IN1": true, ...}, "raw_values": {...}, "timestamp": ...}
      final statesJson = json['states'] as Map<String, dynamic>? ?? {};
      statesJson.forEach((key, value) {
        statesMap[key] = value as bool? ?? false;
      });

      final rawJson = json['raw_values'] as Map<String, dynamic>? ?? {};
      rawJson.forEach((key, value) {
        rawValuesMap[key] = (value as num?)?.toDouble() ?? 0.0;
      });
    } else {
      // NEW COMPACT FORMAT: {"IN1": {"a": true, "f": "...", "t": "...", "c": 0}, ...}
      json.forEach((key, value) {
        if (key == 'timestamp') return; // Skip timestamp key

        if (value is Map<String, dynamic>) {
          // Extract active state using compact key "a" or fallback to "active"
          statesMap[key] = value['a'] as bool? ?? value['active'] as bool? ?? false;

          // Extract raw value if present (voltage or other measurement)
          final rawValue = value['v'] ?? value['voltage'] ?? value['raw'];
          if (rawValue != null) {
            rawValuesMap[key] = (rawValue as num?)?.toDouble() ?? 0.0;
          }
        } else if (value is bool) {
          // Simple format: just input name -> active state
          statesMap[key] = value;
        }
      });
    }

    return InputStates(
      states: statesMap,
      rawValues: rawValuesMap,
      timestamp: DateTime.fromMillisecondsSinceEpoch(
        ((json['timestamp'] as num?) ?? (DateTime.now().millisecondsSinceEpoch ~/ 1000)).toInt() * 1000,
      ),
    );
  }

  /// Parse from raw bytes received from BLE characteristic
  factory InputStates.fromBytes(List<int> bytes) {
    final jsonString = utf8.decode(bytes);
    final json = jsonDecode(jsonString) as Map<String, dynamic>;
    return InputStates.fromJson(json);
  }

  /// Check if an input is active
  bool isActive(String inputName) => states[inputName] ?? false;

  /// Get raw value for an input
  double? getRawValue(String inputName) => rawValues[inputName];

  @override
  String toString() {
    return 'InputStates(${states.length} inputs, ${states.values.where((v) => v).length} active)';
  }
}
