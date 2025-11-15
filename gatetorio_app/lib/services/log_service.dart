import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/log_entry.dart';

/// Service for managing device logs
/// Currently uses demo data - will be replaced with real log manager in Phase 2
class LogService extends ChangeNotifier {
  final List<LogEntry> _logs = [];
  int _logIdCounter = 0;

  // Getters
  List<LogEntry> get logs => List.unmodifiable(_logs);
  int get totalLogs => _logs.length;
  int get errorCount => _logs.where((l) => l.level == LogLevel.error || l.level == LogLevel.critical).length;
  int get warningCount => _logs.where((l) => l.level == LogLevel.warning).length;

  LogService() {
    _initializeDemoLogs();
  }

  /// Initialize with comprehensive demo logs
  void _initializeDemoLogs() {
    final now = DateTime.now();

    // Create 60+ demo logs spanning different time periods
    final demoLogs = [
      // Recent system logs
      _createLog(now.subtract(const Duration(seconds: 30)), LogLevel.info, LogCategory.system,
          'System running normally', {'uptime': '2h 15m', 'cpu_temp': '42°C'}),

      // Command logs
      _createLog(now.subtract(const Duration(minutes: 1)), LogLevel.info, LogCategory.command,
          'OPEN command executed', {'source': 'BLE', 'user': 'Engineer App'}),
      _createLog(now.subtract(const Duration(minutes: 2)), LogLevel.info, LogCategory.command,
          'Gate reached OPEN position', {'duration': '18.5s'}),
      _createLog(now.subtract(const Duration(minutes: 5)), LogLevel.info, LogCategory.command,
          'CLOSE command received', {'source': 'Remote Button', 'input': 'IN2'}),
      _createLog(now.subtract(const Duration(minutes: 6)), LogLevel.info, LogCategory.command,
          'STOP command executed', {'source': 'Photocell', 'reason': 'Safety trigger'}),
      _createLog(now.subtract(const Duration(minutes: 8)), LogLevel.info, LogCategory.command,
          'Partial open 1 (50%) executed', {'target': '50%', 'actual': '49.8%'}),

      // Motor logs
      _createLog(now.subtract(const Duration(minutes: 1, seconds: 15)), LogLevel.info, LogCategory.motor,
          'M1 position changed: 45% → 100%', {'speed': '0.95', 'current': '2.1A'}),
      _createLog(now.subtract(const Duration(minutes: 1, seconds: 30)), LogLevel.info, LogCategory.motor,
          'M2 position changed: 48% → 100%', {'speed': '0.92', 'current': '2.3A'}),
      _createLog(now.subtract(const Duration(minutes: 3)), LogLevel.info, LogCategory.motor,
          'M1 speed adjusted to 80%', {'from': '100%', 'to': '80%', 'reason': 'Slowdown zone'}),
      _createLog(now.subtract(const Duration(minutes: 10)), LogLevel.warning, LogCategory.motor,
          'M2 current spike detected', {'peak': '3.8A', 'threshold': '3.0A'}),
      _createLog(now.subtract(const Duration(minutes: 15)), LogLevel.info, LogCategory.motor,
          'Motor positions synchronized', {'m1': '0%', 'm2': '0%', 'delta': '0.2%'}),

      // Input logs
      _createLog(now.subtract(const Duration(minutes: 2, seconds: 30)), LogLevel.info, LogCategory.input,
          'IN4 (Photocell) activated', {'state': 'ACTIVE', 'duration': '1.2s'}),
      _createLog(now.subtract(const Duration(minutes: 4)), LogLevel.info, LogCategory.input,
          'IN5 (M1 Limit) triggered', {'type': 'NO', 'position': '100%'}),
      _createLog(now.subtract(const Duration(minutes: 7)), LogLevel.info, LogCategory.input,
          'IN6 (Safety edge) resistance OK', {'value': '8.15kΩ', 'nominal': '8.2kΩ', 'tolerance': '±5%'}),
      _createLog(now.subtract(const Duration(minutes: 12)), LogLevel.warning, LogCategory.input,
          'IN3 (Stop button) bouncing detected', {'triggers': 3, 'window': '200ms'}),
      _createLog(now.subtract(const Duration(minutes: 20)), LogLevel.info, LogCategory.input,
          'IN1 (Open button) pressed', {'type': 'NC', 'state': 'closed'}),
      _createLog(now.subtract(const Duration(minutes: 25)), LogLevel.error, LogCategory.input,
          'IN6 resistance out of range', {'value': '12.3kΩ', 'expected': '8.2kΩ ±5%'}),

      // Config logs
      _createLog(now.subtract(const Duration(minutes: 18)), LogLevel.info, LogCategory.config,
          'Auto-close time updated', {'from': '30s', 'to': '45s'}),
      _createLog(now.subtract(const Duration(hours: 1)), LogLevel.info, LogCategory.config,
          'Motor 1 run time changed', {'from': '22.0s', 'to': '24.5s'}),
      _createLog(now.subtract(const Duration(hours: 2)), LogLevel.info, LogCategory.config,
          'Speed profile updated', {'open': '95%', 'close': '90%', 'learning': '30%'}),
      _createLog(now.subtract(const Duration(hours: 3)), LogLevel.info, LogCategory.config,
          'Configuration saved to flash', {'size': '2.4KB', 'checksum': '0xA3F2'}),
      _createLog(now.subtract(const Duration(hours: 5)), LogLevel.warning, LogCategory.config,
          'Config validation warning', {'field': 'motor2_delay', 'value': '0.1s', 'min_recommended': '0.5s'}),

      // BLE logs
      _createLog(now.subtract(const Duration(minutes: 30)), LogLevel.info, LogCategory.ble,
          'BLE client connected', {'device': 'Engineer Phone', 'mac': 'A4:5E:60:C2:1F:88'}),
      _createLog(now.subtract(const Duration(minutes: 45)), LogLevel.info, LogCategory.ble,
          'Command received via BLE', {'characteristic': '0x1001', 'length': '24 bytes'}),
      _createLog(now.subtract(const Duration(hours: 1, minutes: 15)), LogLevel.warning, LogCategory.ble,
          'BLE connection unstable', {'rssi': '-88 dBm', 'packet_loss': '12%'}),
      _createLog(now.subtract(const Duration(hours: 2, minutes: 30)), LogLevel.info, LogCategory.ble,
          'BLE advertising started', {'interval': '100ms', 'tx_power': '0dBm'}),
      _createLog(now.subtract(const Duration(hours: 4)), LogLevel.error, LogCategory.ble,
          'BLE connection dropped', {'reason': 'Timeout', 'duration': '45s'}),

      // System logs
      _createLog(now.subtract(const Duration(hours: 6)), LogLevel.info, LogCategory.system,
          'Device boot completed', {'version': 'v1.2.3', 'boot_time': '2.8s'}),
      _createLog(now.subtract(const Duration(hours: 8)), LogLevel.info, LogCategory.system,
          'Watchdog timer reset', {'uptime': '72h 15m'}),
      _createLog(now.subtract(const Duration(hours: 12)), LogLevel.info, LogCategory.system,
          'Memory usage normal', {'used': '45%', 'free': '110KB'}),
      _createLog(now.subtract(const Duration(hours: 16)), LogLevel.warning, LogCategory.system,
          'CPU temperature high', {'temp': '68°C', 'threshold': '65°C'}),
      _createLog(now.subtract(const Duration(hours: 20)), LogLevel.info, LogCategory.system,
          'Auto-learn completed', {'m1_open': '24.2s', 'm1_close': '23.8s', 'm2_open': '24.0s', 'm2_close': '24.1s'}),
      _createLog(now.subtract(const Duration(days: 1)), LogLevel.info, LogCategory.system,
          'Daily diagnostics passed', {'checks': 15, 'warnings': 0, 'errors': 0}),

      // Fault logs
      _createLog(now.subtract(const Duration(minutes: 35)), LogLevel.error, LogCategory.fault,
          'Safety edge triggered during closing', {'position': '65%', 'action': 'Reverse'}),
      _createLog(now.subtract(const Duration(hours: 1, minutes: 45)), LogLevel.critical, LogCategory.fault,
          'Motor 1 timeout', {'position': '82%', 'expected_time': '22s', 'actual_time': '35s'}),
      _createLog(now.subtract(const Duration(hours: 3, minutes: 20)), LogLevel.error, LogCategory.fault,
          'Photocell fault detected', {'input': 'IN4', 'state': 'Stuck HIGH'}),
      _createLog(now.subtract(const Duration(hours: 6, minutes: 15)), LogLevel.warning, LogCategory.fault,
          'Position drift detected', {'m1': '2.5%', 'm2': '1.8%', 'threshold': '3%'}),
      _createLog(now.subtract(const Duration(hours: 10)), LogLevel.critical, LogCategory.fault,
          'Emergency stop activated', {'source': 'IN3', 'reason': 'User abort'}),
      _createLog(now.subtract(const Duration(days: 1, hours: 2)), LogLevel.error, LogCategory.fault,
          'Limit switch not reached', {'motor': 'M2', 'direction': 'OPEN', 'timeout': '30s'}),

      // More varied logs across different times
      _createLog(now.subtract(const Duration(days: 2)), LogLevel.info, LogCategory.system,
          'Firmware update initiated', {'from': 'v1.2.2', 'to': 'v1.2.3'}),
      _createLog(now.subtract(const Duration(days: 2, minutes: 5)), LogLevel.info, LogCategory.system,
          'Firmware update completed', {'duration': '4m 32s', 'status': 'SUCCESS'}),
      _createLog(now.subtract(const Duration(days: 3)), LogLevel.info, LogCategory.command,
          'Manual calibration started', {'mode': 'AUTO_LEARN'}),
      _createLog(now.subtract(const Duration(days: 3, hours: 1)), LogLevel.info, LogCategory.motor,
          'Travel time learned: M1 OPEN', {'time': '24.2s', 'method': 'Limit switch'}),
      _createLog(now.subtract(const Duration(days: 4)), LogLevel.warning, LogCategory.ble,
          'Pairing request rejected', {'device': 'Unknown-Device', 'reason': 'Not whitelisted'}),
      _createLog(now.subtract(const Duration(days: 5)), LogLevel.info, LogCategory.config,
          'Factory reset performed', {'user': 'Installer', 'confirm': 'YES'}),
      _createLog(now.subtract(const Duration(days: 6)), LogLevel.error, LogCategory.fault,
          'Power supply brownout', {'voltage': '10.2V', 'threshold': '11.0V', 'duration': '120ms'}),
      _createLog(now.subtract(const Duration(days: 7)), LogLevel.info, LogCategory.system,
          'Device commissioned', {'installer': 'TechCorp', 'site': 'Warehouse A'}),

      // Additional command sequences
      _createLog(now.subtract(const Duration(hours: 7)), LogLevel.info, LogCategory.command,
          'Step logic mode activated', {'mode': '3', 'sequence': 'OPEN-STOP-CLOSE-STOP'}),
      _createLog(now.subtract(const Duration(hours: 9)), LogLevel.info, LogCategory.command,
          'Partial close 2 (25%) executed', {'target': '25%', 'actual': '25.1%'}),

      // Input resistance tracking
      _createLog(now.subtract(const Duration(hours: 11)), LogLevel.info, LogCategory.input,
          'IN6 resistance logged', {'value': '8.18kΩ', 'temp': '22°C'}),
      _createLog(now.subtract(const Duration(hours: 13)), LogLevel.info, LogCategory.input,
          'IN6 resistance logged', {'value': '8.22kΩ', 'temp': '24°C'}),

      // Motor current monitoring
      _createLog(now.subtract(const Duration(hours: 14)), LogLevel.info, LogCategory.motor,
          'M1 current profile logged', {'avg': '2.2A', 'peak': '2.8A', 'duration': '18s'}),
      _createLog(now.subtract(const Duration(hours: 15)), LogLevel.info, LogCategory.motor,
          'M2 current profile logged', {'avg': '2.4A', 'peak': '3.0A', 'duration': '18s'}),

      // BLE heartbeats
      _createLog(now.subtract(const Duration(hours: 17)), LogLevel.info, LogCategory.ble,
          'Heartbeat sent to server', {'rssi': '-72 dBm', 'uptime': '120h'}),

      // System health checks
      _createLog(now.subtract(const Duration(hours: 18)), LogLevel.info, LogCategory.system,
          'Flash wear level check', {'cycles': '1,245', 'limit': '100,000', 'health': '98%'}),
      _createLog(now.subtract(const Duration(hours: 19)), LogLevel.info, LogCategory.system,
          'RTC battery OK', {'voltage': '3.1V', 'threshold': '2.8V'}),

      // Config backups
      _createLog(now.subtract(const Duration(days: 8)), LogLevel.info, LogCategory.config,
          'Configuration backed up', {'slot': '1', 'timestamp': '2025-11-08 14:23:01'}),
    ];

    // Add all demo logs
    _logs.addAll(demoLogs);

    // Sort by timestamp (newest first - LIFO)
    _logs.sort((a, b) => b.timestamp.compareTo(a.timestamp));

    debugPrint('LogService: Initialized with ${_logs.length} demo logs');
  }

  /// Create a log entry
  LogEntry _createLog(DateTime timestamp, LogLevel level, LogCategory category,
      String message, [Map<String, dynamic>? metadata]) {
    return LogEntry(
      id: 'log_${_logIdCounter++}',
      timestamp: timestamp,
      level: level,
      category: category,
      message: message,
      metadata: metadata,
    );
  }

  /// Add a new log entry (for future real-time logging)
  void addLog(LogLevel level, LogCategory category, String message,
      [Map<String, dynamic>? metadata]) {
    final log = _createLog(DateTime.now(), level, category, message, metadata);
    _logs.insert(0, log); // Add to beginning (LIFO)
    notifyListeners();
  }

  /// Get logs filtered by criteria
  List<LogEntry> getFilteredLogs({
    Set<LogLevel>? levels,
    Set<LogCategory>? categories,
    TimeRange? timeRange,
    String? searchQuery,
  }) {
    var filtered = _logs.asMap().entries.map((e) => e.value).toList();

    // Filter by log level
    if (levels != null && levels.isNotEmpty) {
      filtered = filtered.where((log) => levels.contains(log.level)).toList();
    }

    // Filter by category
    if (categories != null && categories.isNotEmpty) {
      filtered = filtered.where((log) => categories.contains(log.category)).toList();
    }

    // Filter by time range
    if (timeRange != null && timeRange.startDate != null) {
      filtered = filtered.where((log) => log.timestamp.isAfter(timeRange.startDate!)).toList();
    }

    // Filter by search query
    if (searchQuery != null && searchQuery.isNotEmpty) {
      final query = searchQuery.toLowerCase();
      filtered = filtered.where((log) {
        return log.message.toLowerCase().contains(query) ||
               log.category.displayName.toLowerCase().contains(query) ||
               log.level.displayName.toLowerCase().contains(query);
      }).toList();
    }

    return filtered;
  }

  /// Clear all logs
  void clearLogs() {
    _logs.clear();
    notifyListeners();
  }

  /// Export logs as text
  String exportLogsAsText() {
    final buffer = StringBuffer();
    buffer.writeln('Gatetorio Device Logs');
    buffer.writeln('Generated: ${DateTime.now()}');
    buffer.writeln('Total entries: ${_logs.length}');
    buffer.writeln('=' * 80);
    buffer.writeln();

    for (final log in _logs) {
      buffer.writeln('[${log.fullTimestamp}] ${log.level.displayName} - ${log.category.displayName}');
      buffer.writeln('  ${log.message}');
      if (log.metadata != null && log.metadata!.isNotEmpty) {
        buffer.writeln('  Metadata: ${log.metadata}');
      }
      buffer.writeln();
    }

    return buffer.toString();
  }

  /// Export logs as CSV
  String exportLogsAsCsv() {
    final buffer = StringBuffer();
    buffer.writeln('Timestamp,Level,Category,Message,Metadata');

    for (final log in _logs) {
      final metadataStr = log.metadata?.entries
          .map((e) => '${e.key}=${e.value}')
          .join('; ') ?? '';
      buffer.writeln('"${log.fullTimestamp}","${log.level.displayName}",'
          '"${log.category.displayName}","${log.message}","$metadataStr"');
    }

    return buffer.toString();
  }
}
