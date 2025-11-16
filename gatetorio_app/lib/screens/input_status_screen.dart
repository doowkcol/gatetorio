import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../models/input_config.dart';

class InputStatusScreen extends StatefulWidget {
  const InputStatusScreen({super.key});

  @override
  State<InputStatusScreen> createState() => _InputStatusScreenState();
}

class _InputStatusScreenState extends State<InputStatusScreen> {
  bool _isLoading = false;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    // Defer data loading until after first build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadInputData();
      _startPolling();
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  /// Start polling input states at 1Hz
  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      _pollInputStates();
    });
  }

  /// Poll only input states (config doesn't change)
  Future<void> _pollInputStates() async {
    if (!mounted) return;

    final bleService = Provider.of<BleService>(context, listen: false);

    // Only poll if connected and not in demo mode
    if (!bleService.isDemoMode && bleService.isConnected) {
      try {
        await bleService.readInputStates();
      } catch (e) {
        // Silently fail - don't spam logs with poll errors
      }
    }
  }

  Future<void> _loadInputData() async {
    debugPrint('=== InputStatusScreen._loadInputData() called ===');
    setState(() => _isLoading = true);

    final bleService = Provider.of<BleService>(context, listen: false);

    // Debug: Check connection and mode
    debugPrint('InputStatusScreen: isConnected = ${bleService.isConnected}');
    debugPrint('InputStatusScreen: isDemoMode = ${bleService.isDemoMode}');
    debugPrint('InputStatusScreen: inputConfig before read = ${bleService.inputConfig}');
    debugPrint('InputStatusScreen: inputStates before read = ${bleService.inputStates}');

    // In demo mode, data is already available
    if (!bleService.isDemoMode) {
      debugPrint('InputStatusScreen: Not in demo mode, attempting to read from BLE...');

      try {
        // Load both input config and input states from BLE
        debugPrint('InputStatusScreen: Calling readInputConfig()...');
        final configResult = await bleService.readInputConfig();
        debugPrint('InputStatusScreen: readInputConfig() returned: $configResult');

        debugPrint('InputStatusScreen: Calling readInputStates()...');
        final statesResult = await bleService.readInputStates();
        debugPrint('InputStatusScreen: readInputStates() returned: $statesResult');
      } catch (e, stackTrace) {
        debugPrint('InputStatusScreen: ERROR loading input data: $e');
        debugPrint('InputStatusScreen: Stack trace: $stackTrace');
      }
    } else {
      debugPrint('InputStatusScreen: In demo mode, using existing data');
    }

    debugPrint('InputStatusScreen: inputConfig after read = ${bleService.inputConfig}');
    debugPrint('InputStatusScreen: inputStates after read = ${bleService.inputStates}');

    if (mounted) {
      setState(() => _isLoading = false);
    }
    debugPrint('=== InputStatusScreen._loadInputData() completed ===');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Input Status Monitor'),
        backgroundColor: Theme.of(context).colorScheme.primaryContainer,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: _isLoading ? null : _loadInputData,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Consumer<BleService>(
              builder: (context, bleService, child) {
                final inputConfig = bleService.inputConfig;
                final inputStates = bleService.inputStates;

                if (inputConfig == null) {
                  return Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.error_outline, size: 64, color: Colors.grey.shade400),
                        const SizedBox(height: 16),
                        Text(
                          'No input configuration available',
                          style: TextStyle(color: Colors.grey.shade600, fontSize: 16),
                        ),
                        const SizedBox(height: 24),
                        ElevatedButton.icon(
                          onPressed: _loadInputData,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  );
                }

                final sortedInputs = inputConfig.sortedInputNames;

                return ListView.builder(
                  padding: const EdgeInsets.all(16.0),
                  itemCount: sortedInputs.length + 1, // +1 for header
                  itemBuilder: (context, index) {
                    if (index == 0) {
                      // Header
                      return _buildHeader(context);
                    }

                    final inputName = sortedInputs[index - 1];
                    final input = inputConfig.inputs[inputName]!;
                    final isActive = inputStates?.isActive(inputName) ?? false;
                    final voltage = inputStates?.getRawValue(inputName);

                    return _InputCard(
                      input: input,
                      isActive: isActive,
                      voltage: voltage,
                    );
                  },
                );
              },
            ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Theme.of(context).colorScheme.primary.withOpacity(0.5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.electrical_services,
                color: Theme.of(context).colorScheme.primary,
                size: 28,
              ),
              const SizedBox(width: 12),
              Text(
                'Physical Input Status',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).colorScheme.primary,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Real-time monitoring of all physical input terminals',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.grey.shade700,
                ),
          ),
        ],
      ),
    );
  }
}

class _InputCard extends StatelessWidget {
  final InputConfig input;
  final bool isActive;
  final double? voltage;

  // Constants for resistance calculation
  static const double _VCC = 3.3; // Raspberry Pi supply voltage
  static const double _PULLUP_RESISTANCE = 10000.0; // 10K pull-up resistor

  const _InputCard({
    required this.input,
    required this.isActive,
    this.voltage,
  });

  /// Calculate resistance from voltage using voltage divider formula
  /// V_measured = Vcc * (R_sensor / (R_pullup + R_sensor))
  /// Solving for R_sensor: R_sensor = (V_measured * R_pullup) / (Vcc - V_measured)
  double? _calculateResistance(double voltage) {
    if (voltage <= 0 || voltage >= _VCC) return null;

    final resistance = (voltage * _PULLUP_RESISTANCE) / (_VCC - voltage);
    return resistance;
  }

  void _showInputEditor(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => _InputEditor(input: input),
    );
  }

  @override
  Widget build(BuildContext context) {
    final stateColor = isActive ? Colors.green : Colors.grey;
    final stateText = isActive ? 'ACTIVE' : 'INACTIVE';

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: isActive ? 4 : 2,
      color: isActive ? Colors.green.shade50 : null,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(
          color: isActive
              ? Colors.green.withOpacity(0.7)
              : Colors.grey.withOpacity(0.2),
          width: isActive ? 3 : 2,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(10.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row with input name, state indicator, and edit button
            Row(
              children: [
                // State dot
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: stateColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                // Input name
                Expanded(
                  child: Text(
                    input.name,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.bold,
                      color: Colors.cyan,
                    ),
                  ),
                ),
                // Edit button
                IconButton(
                  icon: const Icon(Icons.settings, size: 20),
                  onPressed: () => _showInputEditor(context),
                  tooltip: 'Configure input',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  color: Colors.grey.shade700,
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Type, Function, and State on one line
            Row(
              children: [
                // Type badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.purple.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: Colors.purple.withOpacity(0.3)),
                  ),
                  child: Text(
                    input.type,
                    style: const TextStyle(
                      fontSize: 11,
                      color: Colors.purple,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                // Function
                Expanded(
                  child: Text(
                    input.functionDisplayName,
                    style: TextStyle(
                      fontSize: 12,
                      color: input.function != null ? Colors.teal : Colors.orange,
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                // State text
                Text(
                  stateText,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: stateColor.shade700,
                  ),
                ),
              ],
            ),

            // 8K2 specific info (calculated resistance and learned resistance)
            if (input.type == '8K2') ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  Icon(Icons.electrical_services, size: 14, color: Colors.amber.shade700),
                  const SizedBox(width: 4),
                  if (voltage != null && _calculateResistance(voltage!) != null)
                    Text(
                      '${_calculateResistance(voltage!)!.toStringAsFixed(0)}Ω',
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.amber.shade800,
                        fontWeight: FontWeight.bold,
                      ),
                    )
                  else if (voltage != null)
                    Text(
                      'Out of range',
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.red.shade600,
                        fontWeight: FontWeight.bold,
                      ),
                    )
                  else
                    Text(
                      'No reading',
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.grey.shade600,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  if (input.learnedResistance != null) ...[
                    const SizedBox(width: 8),
                    Icon(Icons.settings_input_component, size: 14, color: Colors.grey.shade600),
                    const SizedBox(width: 4),
                    Text(
                      'Target: ${input.learnedResistance!.toStringAsFixed(0)}Ω ±${input.tolerancePercent?.toStringAsFixed(1)}%',
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.grey.shade700,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _InputEditor extends StatefulWidget {
  final InputConfig input;

  const _InputEditor({required this.input});

  @override
  State<_InputEditor> createState() => _InputEditorState();
}

class _InputEditorState extends State<_InputEditor> {
  late String _type;
  late String? _function;
  late bool _enabled;
  late String _description;
  late double? _tolerancePercent;
  late double? _learnedResistance;
  bool _isSaving = false;
  bool _isLearning = false;

  // Available input types
  static const List<String> _types = ['NO', 'NC', '8K2'];

  // Available functions with display names (matches gate_ui.py)
  static const Map<String?, String> _functionOptions = {
    null: '[None - Disabled]',
    'cmd_open': 'Open Command',
    'cmd_close': 'Close Command',
    'cmd_stop': 'Stop Command',
    'photocell_closing': 'Photocell (Closing)',
    'photocell_opening': 'Photocell (Opening)',
    'safety_stop_closing': 'Safety Edge (Stop Closing)',
    'safety_stop_opening': 'Safety Edge (Stop Opening)',
    'deadman_open': 'Deadman Open',
    'deadman_close': 'Deadman Close',
    'timed_open': 'Timed Open',
    'partial_1': 'Partial Open 1',
    'partial_2': 'Partial Open 2',
    'step_logic': 'Step Logic',
    'open_limit_m1': 'Limit Switch - M1 OPEN',
    'close_limit_m1': 'Limit Switch - M1 CLOSE',
    'open_limit_m2': 'Limit Switch - M2 OPEN',
    'close_limit_m2': 'Limit Switch - M2 CLOSE',
  };

  @override
  void initState() {
    super.initState();
    _type = widget.input.type;
    _function = widget.input.function;
    _enabled = widget.input.enabled;
    _description = widget.input.description;
    _tolerancePercent = widget.input.tolerancePercent ?? 10.0;
    _learnedResistance = widget.input.learnedResistance;
  }

  Future<void> _save() async {
    setState(() => _isSaving = true);

    try {
      final bleService = Provider.of<BleService>(context, listen: false);

      // Create updated input config
      final updatedInput = InputConfig(
        name: widget.input.name,
        channel: widget.input.channel,
        enabled: _enabled,
        type: _type,
        function: _function,
        description: _description,
        tolerancePercent: _tolerancePercent,
        learnedResistance: _learnedResistance,
      );

      // Update in the service's inputConfig
      if (bleService.inputConfig != null) {
        final updatedInputs = Map<String, InputConfig>.from(bleService.inputConfig!.inputs);
        updatedInputs[widget.input.name] = updatedInput;

        // Write to BLE - this will write the entire config back
        await bleService.writeInputConfig(InputConfigData(inputs: updatedInputs));

        if (mounted) {
          Navigator.of(context).pop();
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${widget.input.name} configuration saved'),
              backgroundColor: Colors.green,
            ),
          );
        }
      }
    } catch (e) {
      debugPrint('Error saving input config: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error saving configuration: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isSaving = false);
      }
    }
  }

  Future<void> _reload() async {
    try {
      final bleService = Provider.of<BleService>(context, listen: false);
      await bleService.readInputConfig();

      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Configuration reloaded from device'),
            backgroundColor: Colors.blue,
          ),
        );
      }
    } catch (e) {
      debugPrint('Error reloading input config: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error reloading configuration: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _learn() async {
    setState(() => _isLearning = true);

    try {
      final bleService = Provider.of<BleService>(context, listen: false);

      // Read current input states to get the voltage reading
      final inputStates = await bleService.readInputStates();

      if (inputStates != null) {
        final voltage = inputStates.getRawValue(widget.input.name);

        if (voltage != null && voltage > 0 && voltage.isFinite) {
          // Successfully learned the resistance
          setState(() {
            _learnedResistance = voltage; // Store voltage as resistance value
          });

          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Learned: ${voltage.toStringAsFixed(3)}V'),
                backgroundColor: Colors.green,
              ),
            );
          }
        } else {
          // Invalid reading
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Invalid reading: ${voltage?.toString() ?? "null"}'),
                backgroundColor: Colors.orange,
              ),
            );
          }
        }
      } else {
        throw Exception('Failed to read input states');
      }
    } catch (e) {
      debugPrint('Error learning resistance: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error learning: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLearning = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Container(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
          Row(
            children: [
              Icon(
                Icons.edit,
                color: Theme.of(context).colorScheme.primary,
                size: 24,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Configure ${widget.input.name}',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Channel info (read-only)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                const Icon(Icons.info_outline, size: 20, color: Colors.grey),
                const SizedBox(width: 8),
                Text(
                  'Channel ${widget.input.channel} • ${widget.input.adcLabel}',
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.grey,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Type dropdown
          DropdownButtonFormField<String>(
            value: _type,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Input Type',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.electrical_services),
            ),
            items: _types.map((type) {
              return DropdownMenuItem(
                value: type,
                child: Text(type),
              );
            }).toList(),
            onChanged: (value) {
              if (value != null) {
                setState(() => _type = value);
              }
            },
          ),
          const SizedBox(height: 16),

          // Function dropdown
          DropdownButtonFormField<String?>(
            value: _function,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Function',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.settings_input_component),
            ),
            items: _functionOptions.entries.map((entry) {
              return DropdownMenuItem(
                value: entry.key,
                child: Text(
                  entry.value,
                  overflow: TextOverflow.ellipsis,
                ),
              );
            }).toList(),
            onChanged: (value) {
              setState(() => _function = value);
            },
          ),
          const SizedBox(height: 16),

          // Enabled toggle
          SwitchListTile(
            title: const Text('Enabled'),
            subtitle: Text(_enabled ? 'Input is active' : 'Input is disabled'),
            value: _enabled,
            onChanged: (value) {
              setState(() => _enabled = value);
            },
            secondary: const Icon(Icons.power_settings_new),
          ),
          const SizedBox(height: 16),

          // Description field
          TextField(
            controller: TextEditingController(text: _description),
            decoration: const InputDecoration(
              labelText: 'Description',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.description),
            ),
            maxLines: 2,
            onChanged: (value) {
              _description = value;
            },
          ),

          // 8K2 specific controls (tolerance and learn)
          if (_type == '8K2') ...[
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.amber.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.amber.shade300),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.settings_input_component, size: 20, color: Colors.amber.shade800),
                      const SizedBox(width: 8),
                      Text(
                        '8K2 Safety Edge Configuration',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                          color: Colors.amber.shade900,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Tolerance field
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: TextEditingController(
                            text: _tolerancePercent?.toStringAsFixed(1) ?? '10.0',
                          ),
                          decoration: const InputDecoration(
                            labelText: 'Tolerance (%)',
                            border: OutlineInputBorder(),
                            prefixIcon: Icon(Icons.tune),
                            filled: true,
                            fillColor: Colors.white,
                          ),
                          keyboardType: TextInputType.numberWithOptions(decimal: true),
                          onChanged: (value) {
                            final parsed = double.tryParse(value);
                            if (parsed != null) {
                              _tolerancePercent = parsed;
                            }
                          },
                        ),
                      ),
                      const SizedBox(width: 12),

                      // Learn button
                      ElevatedButton.icon(
                        onPressed: _isLearning ? null : _learn,
                        icon: _isLearning
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                ),
                              )
                            : const Icon(Icons.psychology),
                        label: Text(_isLearning ? 'Learning...' : 'LEARN'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.orange,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                        ),
                      ),
                    ],
                  ),

                  // Show learned value
                  if (_learnedResistance != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Learned: ${_learnedResistance!.toStringAsFixed(3)}V ±${_tolerancePercent?.toStringAsFixed(1)}%',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.green.shade700,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ] else ...[
                    const SizedBox(height: 8),
                    const Text(
                      'Not learned yet',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),

          // Action buttons
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _isSaving ? null : _reload,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Reload'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: ElevatedButton.icon(
                  onPressed: _isSaving ? null : _save,
                  icon: _isSaving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Icon(Icons.save),
                  label: Text(_isSaving ? 'Saving...' : 'Save'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        ],
        ),
      ),
    );
  }
}
