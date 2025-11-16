import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../models/gate_config.dart';
import '../models/gate_command.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();

  // Controllers for text fields
  final Map<String, TextEditingController> _controllers = {};

  // Values for sliders and switches
  double _openSpeed = 1.0;
  double _closeSpeed = 1.0;
  double _learningSpeed = 0.3;
  double _openingSlowdownPercent = 2.0;
  double _closingSlowdownPercent = 10.0;
  bool _motor1UseLimitSwitches = false;
  bool _motor2UseLimitSwitches = false;
  bool _autoCloseEnabled = false;

  bool _isLoading = false;
  bool _hasChanges = false;

  @override
  void initState() {
    super.initState();
    _initializeControllers();
    // Defer config loading until after first build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadConfiguration();
    });
  }

  void _initializeControllers() {
    final fields = [
      'motor1_run_time',
      'motor2_run_time',
      'pause_time',
      'motor1_open_delay',
      'motor2_close_delay',
      'auto_close_time',
      'safety_reverse_time',
      'deadman_speed',
      'step_logic_mode',
      'partial_1_percent',
      'partial_2_percent',
      'partial_1_auto_close_time',
      'partial_2_auto_close_time',
      'partial_return_pause',
    ];

    for (final field in fields) {
      _controllers[field] = TextEditingController();
      _controllers[field]!.addListener(() => setState(() => _hasChanges = true));
    }
  }

  Future<void> _loadConfiguration() async {
    debugPrint('SettingsScreen: _loadConfiguration() called');
    setState(() => _isLoading = true);

    final bleService = Provider.of<BleService>(context, listen: false);
    debugPrint('SettingsScreen: isConnected=${bleService.isConnected}, isDemoMode=${bleService.isDemoMode}');

    final config = await bleService.readConfig();
    debugPrint('SettingsScreen: readConfig() returned: $config');

    if (config != null && mounted) {
      debugPrint('SettingsScreen: Populating form fields with config data');
      setState(() {
        // Text fields
        _controllers['motor1_run_time']!.text = config.motor1RunTime.toString();
        _controllers['motor2_run_time']!.text = config.motor2RunTime.toString();
        _controllers['pause_time']!.text = config.pauseTime.toString();
        _controllers['motor1_open_delay']!.text = config.motor1OpenDelay.toString();
        _controllers['motor2_close_delay']!.text = config.motor2CloseDelay.toString();
        _controllers['auto_close_time']!.text = config.autoCloseTime.toString();
        _controllers['safety_reverse_time']!.text = config.safetyReverseTime.toString();
        _controllers['deadman_speed']!.text = config.deadmanSpeed.toString();
        _controllers['step_logic_mode']!.text = config.stepLogicMode.toString();
        _controllers['partial_1_percent']!.text = config.partial1Percent.toString();
        _controllers['partial_2_percent']!.text = config.partial2Percent.toString();
        _controllers['partial_1_auto_close_time']!.text = config.partial1AutoCloseTime.toString();
        _controllers['partial_2_auto_close_time']!.text = config.partial2AutoCloseTime.toString();
        _controllers['partial_return_pause']!.text = config.partialReturnPause.toString();

        // Sliders
        _openSpeed = config.openSpeed;
        _closeSpeed = config.closeSpeed;
        _learningSpeed = config.learningSpeed;
        _openingSlowdownPercent = config.openingSlowdownPercent;
        _closingSlowdownPercent = config.closingSlowdownPercent;

        // Switches
        _motor1UseLimitSwitches = config.motor1UseLimitSwitches;
        _motor2UseLimitSwitches = config.motor2UseLimitSwitches;
        _autoCloseEnabled = config.autoCloseEnabled;

        _hasChanges = false;
        _isLoading = false;
      });
      debugPrint('SettingsScreen: Form fields populated successfully');
    } else {
      debugPrint('SettingsScreen: Config was null or widget not mounted');
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to load configuration: ${bleService.lastError ?? "Unknown error"}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _saveConfiguration() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final config = GateConfig(
        motor1RunTime: double.parse(_controllers['motor1_run_time']!.text),
        motor2RunTime: double.parse(_controllers['motor2_run_time']!.text),
        motor2Enabled: true, // Always enabled for now
        pauseTime: double.parse(_controllers['pause_time']!.text),
        motor1OpenDelay: double.parse(_controllers['motor1_open_delay']!.text),
        motor2CloseDelay: double.parse(_controllers['motor2_close_delay']!.text),
        autoCloseTime: double.parse(_controllers['auto_close_time']!.text),
        autoCloseEnabled: _autoCloseEnabled,
        safetyReverseTime: double.parse(_controllers['safety_reverse_time']!.text),
        deadmanSpeed: double.parse(_controllers['deadman_speed']!.text),
        stepLogicMode: int.parse(_controllers['step_logic_mode']!.text),
        partial1Percent: int.parse(_controllers['partial_1_percent']!.text),
        partial2Percent: int.parse(_controllers['partial_2_percent']!.text),
        partial1AutoCloseTime: double.parse(_controllers['partial_1_auto_close_time']!.text),
        partial2AutoCloseTime: double.parse(_controllers['partial_2_auto_close_time']!.text),
        partialReturnPause: double.parse(_controllers['partial_return_pause']!.text),
        motor1UseLimitSwitches: _motor1UseLimitSwitches,
        motor2UseLimitSwitches: _motor2UseLimitSwitches,
        openSpeed: _openSpeed,
        closeSpeed: _closeSpeed,
        learningSpeed: _learningSpeed,
        openingSlowdownPercent: _openingSlowdownPercent,
        closingSlowdownPercent: _closingSlowdownPercent,
      );

      final bleService = Provider.of<BleService>(context, listen: false);
      final success = await bleService.writeConfig(config);

      if (mounted) {
        setState(() {
          _isLoading = false;
          _hasChanges = false;
        });

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(success ? 'Configuration saved' : 'Failed to save configuration'),
            backgroundColor: success ? Colors.green : Colors.red,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings & Configuration'),
        backgroundColor: Theme.of(context).colorScheme.primaryContainer,
        actions: [
          if (_hasChanges)
            Padding(
              padding: const EdgeInsets.only(right: 8.0),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.orange,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text(
                    'Unsaved',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ),
        ],
      ),
      body: Stack(
        children: [
          // Background image
          Positioned.fill(
            child: Image.asset(
              'assets/images/background.png',
              fit: BoxFit.cover,
            ),
          ),
          // Main content
          _isLoading
              ? const Center(child: CircularProgressIndicator())
              : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(16.0),
                children: [
                  // Basic Timing Settings Section
                  _buildSectionHeader('⚙️ Basic Timing Settings', Icons.timer),
                  _buildNumberField(
                    'Motor 1 Travel Time (s)',
                    'motor1_run_time',
                    'Time for M1 to fully open/close',
                  ),
                  _buildNumberField(
                    'Motor 2 Travel Time (s)',
                    'motor2_run_time',
                    'Time for M2 to fully open/close',
                  ),
                  _buildNumberField(
                    'Pause Time (s)',
                    'pause_time',
                    'Pause between movements',
                  ),
                  _buildNumberField(
                    'M2 Opening Delay (s)',
                    'motor1_open_delay',
                    'Delay before M2 starts opening (M1 goes first)',
                  ),
                  _buildNumberField(
                    'M1 Closing Delay (s)',
                    'motor2_close_delay',
                    'Delay before M1 starts closing (M2 goes first)',
                  ),
                  _buildNumberField(
                    'Auto-Close Time (s)',
                    'auto_close_time',
                    'Seconds before auto-close from OPEN',
                  ),
                  _buildSwitchTile(
                    'Auto-Close Enabled',
                    _autoCloseEnabled,
                    (value) => setState(() {
                      _autoCloseEnabled = value;
                      _hasChanges = true;
                    }),
                  ),
                  _buildNumberField(
                    'Safety Reverse Time (s)',
                    'safety_reverse_time',
                    'Reverse duration on safety trigger',
                  ),
                  _buildNumberField(
                    'Deadman Speed (0-1)',
                    'deadman_speed',
                    'Speed multiplier for deadman control',
                  ),
                  _buildNumberField(
                    'Step Logic Mode (1-4)',
                    'step_logic_mode',
                    'Step logic behavior mode',
                    isInt: true,
                  ),
                  _buildNumberField(
                    'PO1 Position (%)',
                    'partial_1_percent',
                    'Partial open 1 target percentage',
                    isInt: true,
                  ),
                  _buildNumberField(
                    'PO2 Position (%)',
                    'partial_2_percent',
                    'Partial open 2 target percentage',
                    isInt: true,
                  ),
                  _buildNumberField(
                    'PO1 Auto-Close (s)',
                    'partial_1_auto_close_time',
                    'Auto-close time for partial position 1',
                  ),
                  _buildNumberField(
                    'PO2 Auto-Close (s)',
                    'partial_2_auto_close_time',
                    'Auto-close time for partial position 2',
                  ),
                  _buildNumberField(
                    'Partial Return Pause (s)',
                    'partial_return_pause',
                    'Pause before returning from partial',
                  ),

                  const SizedBox(height: 24),

                  // Speed & Slowdown Settings Section
                  _buildSectionHeader('🎚️ Speed & Slowdown Settings', Icons.speed),
                  _buildSlider(
                    'Open Speed',
                    _openSpeed,
                    0.1,
                    1.0,
                    (value) => setState(() {
                      _openSpeed = value;
                      _hasChanges = true;
                    }),
                    '${(_openSpeed * 100).toInt()}%',
                  ),
                  _buildSlider(
                    'Close Speed',
                    _closeSpeed,
                    0.1,
                    1.0,
                    (value) => setState(() {
                      _closeSpeed = value;
                      _hasChanges = true;
                    }),
                    '${(_closeSpeed * 100).toInt()}%',
                  ),
                  _buildSlider(
                    'Learning Speed',
                    _learningSpeed,
                    0.1,
                    1.0,
                    (value) => setState(() {
                      _learningSpeed = value;
                      _hasChanges = true;
                    }),
                    '${(_learningSpeed * 100).toInt()}%',
                  ),
                  _buildSlider(
                    'Opening Slowdown %',
                    _openingSlowdownPercent,
                    0.5,
                    20.0,
                    (value) => setState(() {
                      _openingSlowdownPercent = value;
                      _hasChanges = true;
                    }),
                    '${_openingSlowdownPercent.toStringAsFixed(1)}%',
                  ),
                  _buildSlider(
                    'Closing Slowdown %',
                    _closingSlowdownPercent,
                    0.5,
                    20.0,
                    (value) => setState(() {
                      _closingSlowdownPercent = value;
                      _hasChanges = true;
                    }),
                    '${_closingSlowdownPercent.toStringAsFixed(1)}%',
                  ),

                  const SizedBox(height: 24),

                  // Limit Switch Configuration Section
                  _buildSectionHeader('🔌 Limit Switch Configuration', Icons.electrical_services),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                    child: Text(
                      'Enable if motors have physical limit switches at end positions',
                      style: TextStyle(color: Colors.grey, fontSize: 13),
                    ),
                  ),
                  _buildSwitchTile(
                    'Motor 1 use limit switches',
                    _motor1UseLimitSwitches,
                    (value) => setState(() {
                      _motor1UseLimitSwitches = value;
                      _hasChanges = true;
                    }),
                  ),
                  _buildSwitchTile(
                    'Motor 2 use limit switches',
                    _motor2UseLimitSwitches,
                    (value) => setState(() {
                      _motor2UseLimitSwitches = value;
                      _hasChanges = true;
                    }),
                  ),

                  const SizedBox(height: 24),

                  // Auto-Learn Travel Times Section
                  _buildSectionHeader('🤖 Auto-Learn Travel Times', Icons.auto_fix_high),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                    child: Text(
                      'Automatically measure motor travel times using limit switches',
                      style: TextStyle(color: Colors.grey, fontSize: 13),
                    ),
                  ),

                  // Learned Times Display
                  Consumer<BleService>(
                    builder: (context, bleService, child) {
                      final config = bleService.currentConfig;
                      return Container(
                        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.blue.shade300),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(Icons.schedule, color: Colors.blue.shade700, size: 20),
                                const SizedBox(width: 8),
                                Text(
                                  'Learned Travel Times',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: Colors.blue.shade900,
                                    fontSize: 15,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            _buildLearnedTime('M1 Open', config?.learnedM1Open),
                            _buildLearnedTime('M1 Close', config?.learnedM1Close),
                            _buildLearnedTime('M2 Open', config?.learnedM2Open),
                            _buildLearnedTime('M2 Close', config?.learnedM2Close),
                          ],
                        ),
                      );
                    },
                  ),

                  // Engineer Mode Warning
                  Container(
                    margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade100,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.orange.shade300, width: 2),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.warning_amber, color: Colors.orange.shade900, size: 24),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Engineer Mode Required',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.orange.shade900,
                                  fontSize: 14,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Auto-learn requires engineer mode and configured limit switches. Enable via BLE security service.',
                                style: TextStyle(
                                  color: Colors.orange.shade800,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Auto-learn note
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Text(
                      'Note: Auto-learn control is available through the main Python UI or BLE commands when engineer mode is enabled.',
                      style: TextStyle(
                        color: Colors.grey.shade600,
                        fontSize: 12,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ),

                  const SizedBox(height: 32),

                  // Save Button
                  ElevatedButton.icon(
                    onPressed: _hasChanges && !_isLoading ? _saveConfiguration : null,
                    icon: const Icon(Icons.save),
                    label: const Text('SAVE CONFIGURATION'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Reload Button
                  OutlinedButton.icon(
                    onPressed: !_isLoading ? _loadConfiguration : null,
                    icon: const Icon(Icons.refresh),
                    label: const Text('RELOAD FROM DEVICE'),
                  ),

                  const SizedBox(height: 32),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16, top: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: Theme.of(context).colorScheme.primary.withOpacity(0.5),
        ),
      ),
      child: Row(
        children: [
          Icon(icon, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.primary,
                  ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNumberField(
    String label,
    String key,
    String hint, {
    bool isInt = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
          ),
          const SizedBox(height: 4),
          TextFormField(
            controller: _controllers[key],
            keyboardType: TextInputType.numberWithOptions(decimal: !isInt),
            inputFormatters: isInt
                ? [FilteringTextInputFormatter.digitsOnly]
                : [FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d*'))],
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: const TextStyle(fontSize: 12, color: Colors.grey),
              border: const OutlineInputBorder(),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            ),
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Please enter a value';
              }
              if (isInt) {
                if (int.tryParse(value) == null) {
                  return 'Please enter a valid integer';
                }
              } else {
                if (double.tryParse(value) == null) {
                  return 'Please enter a valid number';
                }
              }
              return null;
            },
          ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.only(left: 12.0),
            child: Text(
              hint,
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSlider(
    String label,
    double value,
    double min,
    double max,
    ValueChanged<double> onChanged,
    String valueText,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                label,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.amber,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  valueText,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
              ),
            ],
          ),
          Slider(
            value: value,
            min: min,
            max: max,
            divisions: ((max - min) / 0.05).round(),
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }

  Widget _buildSwitchTile(String title, bool value, ValueChanged<bool> onChanged) {
    return SwitchListTile(
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w500)),
      value: value,
      onChanged: onChanged,
      activeColor: Theme.of(context).colorScheme.primary,
    );
  }

  Widget _buildLearnedTime(String label, double? time) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 13,
              color: Colors.blue.shade700,
              fontWeight: FontWeight.w500,
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: time != null ? Colors.green.shade100 : Colors.grey.shade200,
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: time != null ? Colors.green.shade300 : Colors.grey.shade400,
              ),
            ),
            child: Text(
              time != null ? '${time.toStringAsFixed(2)}s' : 'Not learned',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: time != null ? Colors.green.shade900 : Colors.grey.shade600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
