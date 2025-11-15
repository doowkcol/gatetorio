import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../services/log_service.dart';
import '../models/log_entry.dart';

class LogsScreen extends StatefulWidget {
  const LogsScreen({super.key});

  @override
  State<LogsScreen> createState() => _LogsScreenState();
}

class _LogsScreenState extends State<LogsScreen> {
  final Set<LogLevel> _selectedLevels = {};
  final Set<LogCategory> _selectedCategories = {};
  TimeRange _timeRange = TimeRange.all;
  String _searchQuery = '';
  String? _expandedLogId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Device Logs'),
        actions: [
          PopupMenuButton(
            icon: const Icon(Icons.more_vert),
            itemBuilder: (context) => [
              PopupMenuItem(
                child: const Row(
                  children: [
                    Icon(Icons.download),
                    SizedBox(width: 8),
                    Text('Export as TXT'),
                  ],
                ),
                onTap: () => _exportLogs('txt'),
              ),
              PopupMenuItem(
                child: const Row(
                  children: [
                    Icon(Icons.table_chart),
                    SizedBox(width: 8),
                    Text('Export as CSV'),
                  ],
                ),
                onTap: () => _exportLogs('csv'),
              ),
              const PopupMenuDivider(),
              PopupMenuItem(
                child: const Row(
                  children: [
                    Icon(Icons.delete_forever, color: Colors.red),
                    SizedBox(width: 8),
                    Text('Clear Logs', style: TextStyle(color: Colors.red)),
                  ],
                ),
                onTap: () => _confirmClearLogs(),
              ),
            ],
          ),
        ],
      ),
      body: Consumer<LogService>(
        builder: (context, logService, child) {
          final filteredLogs = logService.getFilteredLogs(
            levels: _selectedLevels.isEmpty ? null : _selectedLevels,
            categories: _selectedCategories.isEmpty ? null : _selectedCategories,
            timeRange: _timeRange,
            searchQuery: _searchQuery.isEmpty ? null : _searchQuery,
          );

          return Column(
            children: [
              // Header Stats
              _buildHeaderStats(logService, filteredLogs.length),

              // Search Bar
              _buildSearchBar(),

              // Filter Chips
              _buildFilterChips(),

              // Logs List
              Expanded(
                child: filteredLogs.isEmpty
                    ? _buildEmptyState()
                    : _buildLogsList(filteredLogs),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildHeaderStats(LogService logService, int filteredCount) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E1E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF4CAF50), width: 2),
      ),
      child: Row(
        children: [
          Expanded(
            child: _buildStatCard(
              'Total',
              logService.totalLogs.toString(),
              Icons.list,
              Colors.blue,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _buildStatCard(
              'Warnings',
              logService.warningCount.toString(),
              Icons.warning,
              Colors.orange,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _buildStatCard(
              'Errors',
              logService.errorCount.toString(),
              Icons.error,
              Colors.red,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _buildStatCard(
              'Filtered',
              filteredCount.toString(),
              Icons.filter_list,
              const Color(0xFF4CAF50),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
    return Column(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: Colors.grey),
        ),
      ],
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: TextField(
        onChanged: (value) => setState(() => _searchQuery = value),
        decoration: InputDecoration(
          hintText: 'Search logs...',
          prefixIcon: const Icon(Icons.search),
          suffixIcon: _searchQuery.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: () => setState(() => _searchQuery = ''),
                )
              : null,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          filled: true,
          fillColor: const Color(0xFF1E1E1E),
        ),
      ),
    );
  }

  Widget _buildFilterChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          // Time Range Dropdown
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: const Color(0xFF1E1E1E),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: Colors.grey.shade700),
            ),
            child: DropdownButton<TimeRange>(
              value: _timeRange,
              underline: const SizedBox(),
              icon: const Icon(Icons.arrow_drop_down, size: 20),
              style: const TextStyle(color: Colors.white, fontSize: 13),
              dropdownColor: const Color(0xFF1E1E1E),
              items: TimeRange.values.map((range) {
                return DropdownMenuItem(
                  value: range,
                  child: Text(range.displayName),
                );
              }).toList(),
              onChanged: (value) {
                if (value != null) setState(() => _timeRange = value);
              },
            ),
          ),
          const SizedBox(width: 8),

          // Level Filters
          ...LogLevel.values.map((level) {
            final isSelected = _selectedLevels.contains(level);
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilterChip(
                label: Text(level.displayName),
                selected: isSelected,
                onSelected: (selected) {
                  setState(() {
                    if (selected) {
                      _selectedLevels.add(level);
                    } else {
                      _selectedLevels.remove(level);
                    }
                  });
                },
                selectedColor: _getLevelColor(level).withOpacity(0.3),
                checkmarkColor: _getLevelColor(level),
                labelStyle: TextStyle(
                  color: isSelected ? _getLevelColor(level) : Colors.grey,
                  fontSize: 12,
                ),
              ),
            );
          }),

          // Category Filters
          ...LogCategory.values.map((category) {
            final isSelected = _selectedCategories.contains(category);
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilterChip(
                label: Text(category.displayName),
                selected: isSelected,
                onSelected: (selected) {
                  setState(() {
                    if (selected) {
                      _selectedCategories.add(category);
                    } else {
                      _selectedCategories.remove(category);
                    }
                  });
                },
                selectedColor: const Color(0xFF4CAF50).withOpacity(0.3),
                checkmarkColor: const Color(0xFF4CAF50),
                labelStyle: TextStyle(
                  color: isSelected ? const Color(0xFF4CAF50) : Colors.grey,
                  fontSize: 12,
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildLogsList(List<LogEntry> logs) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: logs.length,
      itemBuilder: (context, index) {
        final log = logs[index];
        final isExpanded = _expandedLogId == log.id;

        // Check if we need a date header
        bool showDateHeader = false;
        if (index == 0) {
          showDateHeader = true;
        } else {
          final prevLog = logs[index - 1];
          showDateHeader = log.formattedDate != prevLog.formattedDate;
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (showDateHeader) ...[
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  log.formattedDate,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
              ),
            ],
            _buildLogCard(log, isExpanded),
          ],
        );
      },
    );
  }

  Widget _buildLogCard(LogEntry log, bool isExpanded) {
    final levelColor = _getLevelColor(log.level);

    return Card(
      margin: const EdgeInsets.only(bottom: 8, left: 12),
      color: const Color(0xFF1E1E1E),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: levelColor.withOpacity(0.3), width: 2),
      ),
      child: InkWell(
        onTap: () => setState(() {
          _expandedLogId = isExpanded ? null : log.id;
        }),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header Row
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Timeline Dot
                  Container(
                    margin: const EdgeInsets.only(top: 4),
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: levelColor,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: levelColor.withOpacity(0.5),
                          blurRadius: 4,
                          spreadRadius: 1,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Content
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Level and Category Badges
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: levelColor.withOpacity(0.2),
                                borderRadius: BorderRadius.circular(4),
                                border: Border.all(color: levelColor),
                              ),
                              child: Text(
                                log.level.displayName,
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: levelColor,
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: Colors.grey.shade800,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                log.category.displayName,
                                style: const TextStyle(
                                  fontSize: 10,
                                  color: Colors.grey,
                                ),
                              ),
                            ),
                            const Spacer(),
                            Text(
                              log.relativeTime,
                              style: const TextStyle(
                                fontSize: 11,
                                color: Colors.grey,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),

                        // Message
                        Text(
                          log.message,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),

                        // Timestamp
                        const SizedBox(height: 4),
                        Text(
                          log.formattedTime,
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.grey.shade600,
                          ),
                        ),

                        // Metadata (if expanded)
                        if (isExpanded && log.metadata != null && log.metadata!.isNotEmpty) ...[
                          const SizedBox(height: 12),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.black.withOpacity(0.3),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Metadata:',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 12,
                                    color: Colors.grey,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                ...log.metadata!.entries.map((entry) {
                                  return Padding(
                                    padding: const EdgeInsets.only(bottom: 4),
                                    child: Row(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        SizedBox(
                                          width: 100,
                                          child: Text(
                                            '${entry.key}:',
                                            style: TextStyle(
                                              fontSize: 11,
                                              color: Colors.grey.shade400,
                                            ),
                                          ),
                                        ),
                                        Expanded(
                                          child: Text(
                                            entry.value.toString(),
                                            style: const TextStyle(
                                              fontSize: 11,
                                              color: Colors.white,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  );
                                }),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),

                  // Expand indicator
                  Icon(
                    isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: Colors.grey,
                    size: 20,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.info_outline, size: 64, color: Colors.grey.shade600),
          const SizedBox(height: 16),
          Text(
            'No logs found',
            style: TextStyle(color: Colors.grey.shade400, fontSize: 16),
          ),
          const SizedBox(height: 8),
          Text(
            'Try adjusting your filters',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Color _getLevelColor(LogLevel level) {
    switch (level) {
      case LogLevel.info:
        return const Color(0xFF64B5F6);
      case LogLevel.warning:
        return const Color(0xFFFFB74D);
      case LogLevel.error:
        return const Color(0xFFFF6B6B);
      case LogLevel.critical:
        return const Color(0xFFD32F2F);
    }
  }

  void _exportLogs(String format) {
    Future.delayed(const Duration(milliseconds: 100), () {
      final logService = Provider.of<LogService>(context, listen: false);
      final content = format == 'csv'
          ? logService.exportLogsAsCsv()
          : logService.exportLogsAsText();

      Clipboard.setData(ClipboardData(text: content));

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Logs exported as ${format.toUpperCase()} and copied to clipboard'),
            backgroundColor: const Color(0xFF4CAF50),
            action: SnackBarAction(
              label: 'OK',
              textColor: Colors.white,
              onPressed: () {},
            ),
          ),
        );
      }
    });
  }

  void _confirmClearLogs() {
    Future.delayed(const Duration(milliseconds: 100), () {
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: const Color(0xFF1E1E1E),
          title: const Text('Clear All Logs?'),
          content: const Text(
            'This will permanently delete all log entries. This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                Provider.of<LogService>(context, listen: false).clearLogs();
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('All logs cleared'),
                    backgroundColor: Color(0xFFFF6B6B),
                  ),
                );
              },
              child: const Text('Clear', style: TextStyle(color: Colors.red)),
            ),
          ],
        ),
      );
    });
  }
}
