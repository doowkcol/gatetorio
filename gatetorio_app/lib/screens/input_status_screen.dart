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
            // Header row with input name, state, and ADC
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // Input name and state indicator inline
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
                // ADC label
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.blue.shade100,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    input.adcLabel,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Colors.blue.shade900,
                    ),
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
    );
  }
}

class _InfoChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _InfoChip({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '$label: ',
            style: TextStyle(
              fontSize: 13,
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
          Flexible(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 13,
                color: color,
                fontWeight: FontWeight.bold,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
