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

                    return _InputCard(
                      input: input,
                      isActive: isActive,
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

  const _InputCard({
    required this.input,
    required this.isActive,
  });

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

    return GestureDetector(
      onTap: () => _showInputEditor(context),
      child: Card(
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
            // Header row with input name and state indicator
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
                Text(
                  input.name,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.bold,
                    color: Colors.cyan,
                  ),
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

            // 8K2 specific info (if applicable)
            if (input.type == '8K2' && input.learnedResistance != null) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  Icon(Icons.settings_input_component, size: 14, color: Colors.amber.shade700),
                  const SizedBox(width: 4),
                  Text(
                    '${input.learnedResistance!.toStringAsFixed(0)}Ω ±${input.tolerancePercent?.toStringAsFixed(1)}%',
                    style: TextStyle(
                      fontSize: 10,
                      color: Colors.amber.shade800,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
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
  bool _isSaving = false;

  // Available input types
  static const List<String> _types = ['NO', 'NC', '8K2'];

  // Available functions with display names
  static const Map<String?, String> _functionOptions = {
    null: 'Not Used',
    'close_limit_m1': 'Close Limit M1',
    'open_limit_m1': 'Open Limit M1',
    'close_limit_m2': 'Close Limit M2',
    'open_limit_m2': 'Open Limit M2',
    'cmd_open': 'Cmd Open',
    'cmd_close': 'Cmd Close',
    'cmd_stop': 'Cmd Stop',
    'safety_stop_opening': 'Safety Stop Opening',
    'safety_stop_closing': 'Safety Stop Closing',
    'partial_1': 'Partial 1',
    'partial_2': 'Partial 2',
  };

  @override
  void initState() {
    super.initState();
    _type = widget.input.type;
    _function = widget.input.function;
    _enabled = widget.input.enabled;
    _description = widget.input.description;
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
        tolerancePercent: widget.input.tolerancePercent,
        learnedResistance: widget.input.learnedResistance,
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

  @override
  Widget build(BuildContext context) {
    return Container(
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
            decoration: const InputDecoration(
              labelText: 'Function',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.settings_input_component),
            ),
            items: _functionOptions.entries.map((entry) {
              return DropdownMenuItem(
                value: entry.key,
                child: Text(entry.value),
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
    );
  }
}
