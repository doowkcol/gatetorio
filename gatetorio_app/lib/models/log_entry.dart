/// Represents a single log entry in the system
class LogEntry {
  final String id;
  final DateTime timestamp;
  final LogLevel level;
  final LogCategory category;
  final String message;
  final Map<String, dynamic>? metadata;

  LogEntry({
    required this.id,
    required this.timestamp,
    required this.level,
    required this.category,
    required this.message,
    this.metadata,
  });

  /// Get relative time string (e.g., "2 minutes ago")
  String get relativeTime {
    final duration = DateTime.now().difference(timestamp);

    if (duration.inSeconds < 60) {
      return '${duration.inSeconds}s ago';
    } else if (duration.inMinutes < 60) {
      return '${duration.inMinutes}m ago';
    } else if (duration.inHours < 24) {
      return '${duration.inHours}h ago';
    } else {
      return '${duration.inDays}d ago';
    }
  }

  /// Get formatted timestamp (e.g., "14:32:15")
  String get formattedTime {
    return '${timestamp.hour.toString().padLeft(2, '0')}:'
        '${timestamp.minute.toString().padLeft(2, '0')}:'
        '${timestamp.second.toString().padLeft(2, '0')}';
  }

  /// Get formatted date (e.g., "Nov 15, 2025")
  String get formattedDate {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${months[timestamp.month - 1]} ${timestamp.day}, ${timestamp.year}';
  }

  /// Get full timestamp (e.g., "Nov 15, 2025 14:32:15")
  String get fullTimestamp {
    return '$formattedDate $formattedTime';
  }

  @override
  String toString() {
    return 'LogEntry($level, $category, $message)';
  }
}

/// Log severity levels
enum LogLevel {
  info,
  warning,
  error,
  critical;

  String get displayName {
    switch (this) {
      case LogLevel.info:
        return 'INFO';
      case LogLevel.warning:
        return 'WARNING';
      case LogLevel.error:
        return 'ERROR';
      case LogLevel.critical:
        return 'CRITICAL';
    }
  }

  String get emoji {
    switch (this) {
      case LogLevel.info:
        return 'ℹ️';
      case LogLevel.warning:
        return '⚠️';
      case LogLevel.error:
        return '❌';
      case LogLevel.critical:
        return '🔥';
    }
  }
}

/// Log entry categories
enum LogCategory {
  command,
  motor,
  input,
  config,
  ble,
  system,
  fault;

  String get displayName {
    switch (this) {
      case LogCategory.command:
        return 'COMMAND';
      case LogCategory.motor:
        return 'MOTOR';
      case LogCategory.input:
        return 'INPUT';
      case LogCategory.config:
        return 'CONFIG';
      case LogCategory.ble:
        return 'BLE';
      case LogCategory.system:
        return 'SYSTEM';
      case LogCategory.fault:
        return 'FAULT';
    }
  }

  String get icon {
    switch (this) {
      case LogCategory.command:
        return '🎮';
      case LogCategory.motor:
        return '⚙️';
      case LogCategory.input:
        return '🔌';
      case LogCategory.config:
        return '⚙️';
      case LogCategory.ble:
        return '📡';
      case LogCategory.system:
        return '💻';
      case LogCategory.fault:
        return '⚠️';
    }
  }
}

/// Time range filter options
enum TimeRange {
  today,
  last7Days,
  last30Days,
  all;

  String get displayName {
    switch (this) {
      case TimeRange.today:
        return 'Today';
      case TimeRange.last7Days:
        return 'Last 7 Days';
      case TimeRange.last30Days:
        return 'Last 30 Days';
      case TimeRange.all:
        return 'All Time';
    }
  }

  DateTime? get startDate {
    final now = DateTime.now();
    switch (this) {
      case TimeRange.today:
        return DateTime(now.year, now.month, now.day);
      case TimeRange.last7Days:
        return now.subtract(const Duration(days: 7));
      case TimeRange.last30Days:
        return now.subtract(const Duration(days: 30));
      case TimeRange.all:
        return null;
    }
  }
}
