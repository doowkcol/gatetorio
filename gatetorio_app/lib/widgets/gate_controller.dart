import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/ble_service.dart';
import '../models/gate_command.dart';
import '../models/gate_status.dart';

class GateController extends StatelessWidget {
  const GateController({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<BleService>(
      builder: (context, bleService, child) {
        final status = bleService.currentStatus;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Status Card
              _StatusCard(status: status),
              const SizedBox(height: 16),

              // Main Control Buttons
              _ControlButtons(
                status: status,
                onCommand: (command) => _sendCommand(context, bleService, command),
              ),
              const SizedBox(height: 16),

              // Position Indicators
              if (status != null) ...[
                _PositionIndicators(status: status),
                const SizedBox(height: 16),
              ],

              // Additional Controls
              _AdditionalControls(
                status: status,
                onCommand: (command) => _sendCommand(context, bleService, command),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _sendCommand(
    BuildContext context,
    BleService bleService,
    GateCommand command,
  ) async {
    final success = await bleService.sendCommand(command);

    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success
              ? 'Command sent: ${command.cmd}'
              : 'Failed to send command'),
          duration: const Duration(seconds: 1),
          backgroundColor: success ? Colors.green : Colors.red,
        ),
      );
    }
  }
}

class _StatusCard extends StatelessWidget {
  final GateStatus? status;

  const _StatusCard({required this.status});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          children: [
            // State indicator
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  _getStateIcon(),
                  size: 48,
                  color: _getStateColor(),
                ),
                const SizedBox(width: 16),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Gate Status',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    Text(
                      status?.state.displayName ?? 'Unknown',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            color: _getStateColor(),
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                  ],
                ),
              ],
            ),

            // Auto-close countdown
            if (status != null && status!.autoCloseCountdown > 0) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.orange.shade100,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.timer, color: Colors.orange.shade900, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Auto-close in ${status!.autoCloseCountdown}s',
                      style: TextStyle(
                        color: Colors.orange.shade900,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ],

            // Last update time
            if (status != null) ...[
              const SizedBox(height: 12),
              Text(
                'Last update: ${_formatTime(status!.timestamp)}',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.grey.shade600,
                    ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  IconData _getStateIcon() {
    if (status == null) return Icons.help_outline;

    switch (status!.state) {
      // Primary states
      case GateState.closed:
        return Icons.lock;
      case GateState.open:
        return Icons.lock_open;
      case GateState.partial1:
      case GateState.partial2:
        return Icons.horizontal_rule;
      case GateState.stopped:
        return Icons.stop_circle;
      case GateState.unknown:
        return Icons.help_outline;

      // Movement states
      case GateState.opening:
      case GateState.openingToPartial1:
      case GateState.openingToPartial2:
        return Icons.arrow_upward;
      case GateState.closing:
      case GateState.closingToPartial1:
      case GateState.closingToPartial2:
        return Icons.arrow_downward;

      // Safety reversal states
      case GateState.reversingFromOpen:
        return Icons.warning;
      case GateState.reversingFromClose:
        return Icons.warning;

      // Legacy states
      case GateState.error:
        return Icons.error;
      case GateState.calibrating:
        return Icons.settings;
    }
  }

  Color _getStateColor() {
    if (status == null) return Colors.grey;

    switch (status!.state) {
      // Primary states
      case GateState.closed:
        return Colors.green;
      case GateState.open:
        return Colors.lightGreen;
      case GateState.partial1:
      case GateState.partial2:
        return Colors.teal;
      case GateState.stopped:
        return Colors.orange;
      case GateState.unknown:
        return Colors.grey;

      // Movement states
      case GateState.opening:
      case GateState.openingToPartial1:
      case GateState.openingToPartial2:
      case GateState.closing:
      case GateState.closingToPartial1:
      case GateState.closingToPartial2:
        return Colors.blue;

      // Safety reversal states
      case GateState.reversingFromOpen:
      case GateState.reversingFromClose:
        return Colors.amber;

      // Legacy states
      case GateState.error:
        return Colors.red;
      case GateState.calibrating:
        return Colors.purple;
    }
  }

  String _formatTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);

    if (diff.inSeconds < 60) {
      return '${diff.inSeconds}s ago';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}m ago';
    } else {
      return '${time.hour}:${time.minute.toString().padLeft(2, '0')}';
    }
  }
}

class _ControlButtons extends StatelessWidget {
  final GateStatus? status;
  final Function(GateCommand) onCommand;

  const _ControlButtons({
    required this.status,
    required this.onCommand,
  });

  @override
  Widget build(BuildContext context) {
    final canSendCommand = status?.canSendCommand ?? false;

    return Column(
      children: [
        // Open button
        SizedBox(
          width: double.infinity,
          height: 70,
          child: ElevatedButton.icon(
            onPressed: canSendCommand ? () => onCommand(GateCommand.open) : null,
            icon: const Icon(Icons.arrow_upward, size: 32),
            label: const Text('OPEN', style: TextStyle(fontSize: 20)),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
              foregroundColor: Colors.white,
              disabledBackgroundColor: Colors.grey.shade300,
            ),
          ),
        ),
        const SizedBox(height: 12),

        // Stop button
        SizedBox(
          width: double.infinity,
          height: 70,
          child: ElevatedButton.icon(
            onPressed: canSendCommand ? () => onCommand(GateCommand.stop) : null,
            icon: const Icon(Icons.stop, size: 32),
            label: const Text('STOP', style: TextStyle(fontSize: 20)),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
              foregroundColor: Colors.white,
              disabledBackgroundColor: Colors.grey.shade300,
            ),
          ),
        ),
        const SizedBox(height: 12),

        // Close button
        SizedBox(
          width: double.infinity,
          height: 70,
          child: ElevatedButton.icon(
            onPressed: canSendCommand ? () => onCommand(GateCommand.close) : null,
            icon: const Icon(Icons.arrow_downward, size: 32),
            label: const Text('CLOSE', style: TextStyle(fontSize: 20)),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
              disabledBackgroundColor: Colors.grey.shade300,
            ),
          ),
        ),
      ],
    );
  }
}

class _PositionIndicators extends StatelessWidget {
  final GateStatus status;

  const _PositionIndicators({required this.status});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Motor Positions',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),

            // Motor 1
            _MotorIndicator(
              motorName: 'Motor 1',
              percent: status.m1Percent,
              speed: status.m1SpeedPercent,
            ),
            const SizedBox(height: 12),

            // Motor 2
            _MotorIndicator(
              motorName: 'Motor 2',
              percent: status.m2Percent,
              speed: status.m2SpeedPercent,
            ),
          ],
        ),
      ),
    );
  }
}

class _MotorIndicator extends StatelessWidget {
  final String motorName;
  final int percent;
  final int speed;

  const _MotorIndicator({
    required this.motorName,
    required this.percent,
    required this.speed,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              motorName,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            Text(
              '$percent% (Speed: $speed%)',
              style: TextStyle(color: Colors.grey.shade700),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            value: percent / 100.0,
            minHeight: 20,
            backgroundColor: Colors.grey.shade200,
            valueColor: AlwaysStoppedAnimation<Color>(
              speed > 0 ? Colors.blue : Colors.grey.shade400,
            ),
          ),
        ),
      ],
    );
  }
}

class _AdditionalControls extends StatelessWidget {
  final GateStatus? status;
  final Function(GateCommand) onCommand;

  const _AdditionalControls({
    required this.status,
    required this.onCommand,
  });

  @override
  Widget build(BuildContext context) {
    final canSendPartial = status?.canSendPartialCommand ?? false;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Additional Controls',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: canSendPartial ? () => onCommand(GateCommand.partial1) : null,
                  icon: const Icon(Icons.looks_one),
                  label: const Text('Partial 1'),
                ),
                OutlinedButton.icon(
                  onPressed: canSendPartial ? () => onCommand(GateCommand.partial2) : null,
                  icon: const Icon(Icons.looks_two),
                  label: const Text('Partial 2'),
                ),
                OutlinedButton.icon(
                  onPressed: () => onCommand(GateCommand.stepLogic),
                  icon: const Icon(Icons.shuffle),
                  label: const Text('Step Logic'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
