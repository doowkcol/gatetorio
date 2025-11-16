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

  /// Map numeric function code to function name string
  /// Server sends compact numeric codes to save BLE bandwidth
  static String? _decodeFunctionCode(dynamic functionValue) {
    if (functionValue == null) return null;

    // If already a string, return it (backwards compatibility)
    if (functionValue is String) {
      return functionValue.isEmpty ? null : functionValue;
    }

    // Decode numeric function code
    if (functionValue is int) {
      switch (functionValue) {
        case 0: return null; // No function
        case 1: return 'close_limit_m1';
        case 2: return 'open_limit_m1';
        case 3: return 'close_limit_m2';
        case 4: return 'open_limit_m2';
        case 5: return 'cmd_open';
        case 6: return 'cmd_close';
        case 7: return 'cmd_stop';
        case 8: return 'safety_stop_opening';
        case 9: return 'safety_stop_closing';
        case 10: return 'partial_1';
        case 11: return 'partial_2';
        case 12: return 'photocell_closing';
        case 13: return 'photocell_opening';
        case 14: return 'deadman_open';
        case 15: return 'deadman_close';
        case 16: return 'timed_open';
        case 17: return 'step_logic';
        default: return null; // Unknown code
      }
    }

    return null;
  }

  /// Parse from JSON received from BLE
  /// Supports both old format and new compact format with keys:
  /// - "c" = channel
  /// - "e" = enabled
  /// - "t" = type
  /// - "f" = function (string or numeric code)
  /// - "d" = description
  factory InputConfig.fromJson(String name, Map<String, dynamic> json) {
    final functionValue = json['f'] ?? json['function'];

    return InputConfig(
      name: name,
      channel: (json['c'] ?? json['channel'] as num?)?.toInt() ?? 0,
      enabled: json['e'] ?? json['enabled'] ?? true,
      type: json['t'] ?? json['type'] ?? 'NO',
      function: _decodeFunctionCode(functionValue),
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
    if (function == null || function!.isEmpty) return 'Not Used';
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

  /// Map numeric type code to type string
  static String _decodeTypeCode(int typeCode) {
    switch (typeCode) {
      case 1: return 'NC';
      case 2: return 'NO';
      case 3: return '8K2';
      default: return 'NO';
    }
  }

  /// Parse from ultra-compact array format
  /// Format: [["IN1", func_code, type_code, channel], ...]
  /// Type codes: 1=NC, 2=NO, 3=8K2
  factory InputConfigData.fromArray(List<dynamic> array) {
    final inputs = <String, InputConfig>{};

    for (final item in array) {
      if (item is List && item.length >= 4) {
        final name = item[0] as String;
        final functionCode = item[1] as int;
        final typeCode = item[2] as int;
        final channel = item[3] as int;

        inputs[name] = InputConfig(
          name: name,
          channel: channel,
          enabled: true,
          type: _decodeTypeCode(typeCode),
          function: InputConfig._decodeFunctionCode(functionCode),
          description: '',
        );
      }
    }

    return InputConfigData(inputs: inputs);
  }

  /// Parse from JSON object format
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
  /// Supports both array format and object format
  factory InputConfigData.fromBytes(List<int> bytes) {
    final jsonString = utf8.decode(bytes);
    final decoded = jsonDecode(jsonString);

    // Check if array format or object format
    if (decoded is List) {
      // New ultra-compact array format
      return InputConfigData.fromArray(decoded);
    } else if (decoded is Map<String, dynamic>) {
      // Old object format
      return InputConfigData.fromJson(decoded);
    } else {
      throw FormatException('Unexpected InputConfig format');
    }
  }

  /// Encode function name to numeric code (inverse of _decodeFunctionCode)
  static int _encodeFunctionCode(String? function) {
    if (function == null || function.isEmpty) return 0;

    switch (function) {
      case 'close_limit_m1': return 1;
      case 'open_limit_m1': return 2;
      case 'close_limit_m2': return 3;
      case 'open_limit_m2': return 4;
      case 'cmd_open': return 5;
      case 'cmd_close': return 6;
      case 'cmd_stop': return 7;
      case 'safety_stop_opening': return 8;
      case 'safety_stop_closing': return 9;
      case 'partial_1': return 10;
      case 'partial_2': return 11;
      case 'photocell_closing': return 12;
      case 'photocell_opening': return 13;
      case 'deadman_open': return 14;
      case 'deadman_close': return 15;
      case 'timed_open': return 16;
      case 'step_logic': return 17;
      default: return 0; // Unknown function
    }
  }

  /// Encode type string to numeric code (inverse of _decodeTypeCode)
  static int _encodeTypeCode(String type) {
    switch (type) {
      case 'NC': return 1;
      case 'NO': return 2;
      case '8K2': return 3;
      default: return 2; // Default to NO
    }
  }

  /// Convert to ultra-compact array format for BLE transmission
  /// Format: [["IN1", func_code, type_code, channel], ...]
  List<dynamic> toArray() {
    final array = <List<dynamic>>[];

    // Sort input names for consistent ordering
    final sortedNames = sortedInputNames;

    for (final name in sortedNames) {
      final input = inputs[name]!;
      array.add([
        name,
        _encodeFunctionCode(input.function),
        _encodeTypeCode(input.type),
        input.channel,
      ]);
    }

    return array;
  }

  /// Convert to JSON for BLE transmission (old format)
  Map<String, dynamic> toJson() {
    final inputsJson = <String, dynamic>{};
    inputs.forEach((key, value) {
      inputsJson[key] = value.toJson();
    });
    return {'inputs': inputsJson};
  }

  /// Convert to bytes for BLE write operation (uses compact array format)
  List<int> toBytes() {
    return utf8.encode(jsonEncode(toArray()));
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
  /// Supports multiple formats:
  /// - Old format: {"states": {"IN1": true, ...}, "raw_values": {...}}
  /// - Compact object format: {"IN1": {"a": true, "v": 1.234}, ...}
  /// - Mixed-type format: {"IN1": true, "IN2": [true, 1.234], ...}
  ///   - boolean for NO/NC inputs
  ///   - [bool, float] for 8K2 inputs (state + voltage for diagnostics)
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
      // NEW FORMATS
      json.forEach((key, value) {
        if (key == 'timestamp') return; // Skip timestamp key

        if (value is List) {
          // MIXED-TYPE FORMAT (8K2): [bool, float] = [active, voltage]
          if (value.isNotEmpty) {
            statesMap[key] = (value[0] as bool?) ?? false;
            if (value.length > 1) {
              rawValuesMap[key] = (value[1] as num?)?.toDouble() ?? 0.0;
            }
          }
        } else if (value is Map<String, dynamic>) {
          // COMPACT OBJECT FORMAT: {"a": true, "v": 1.234}
          statesMap[key] = value['a'] as bool? ?? value['active'] as bool? ?? false;

          // Extract raw value if present (voltage or other measurement)
          final rawValue = value['v'] ?? value['voltage'] ?? value['raw'];
          if (rawValue != null) {
            rawValuesMap[key] = (rawValue as num?)?.toDouble() ?? 0.0;
          }
        } else if (value is bool) {
          // MIXED-TYPE FORMAT (NO/NC): boolean = active
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
