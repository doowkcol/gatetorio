import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/fleet_service.dart';
import '../models/fleet_device.dart';

class FleetManagementScreen extends StatefulWidget {
  const FleetManagementScreen({super.key});

  @override
  State<FleetManagementScreen> createState() => _FleetManagementScreenState();
}

class _FleetManagementScreenState extends State<FleetManagementScreen> {
  String _searchQuery = '';
  DeviceSortOption _sortOption = DeviceSortOption.status;
  bool _showOnlineOnly = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fleet Management'),
        actions: [
          PopupMenuButton<DeviceSortOption>(
            icon: const Icon(Icons.sort),
            tooltip: 'Sort by',
            onSelected: (option) {
              setState(() => _sortOption = option);
              Provider.of<FleetService>(context, listen: false).sortDevices(option);
            },
            itemBuilder: (context) => DeviceSortOption.values.map((option) {
              return PopupMenuItem(
                value: option,
                child: Row(
                  children: [
                    if (_sortOption == option)
                      const Icon(Icons.check, size: 18)
                    else
                      const SizedBox(width: 18),
                    const SizedBox(width: 8),
                    Text(option.displayName),
                  ],
                ),
              );
            }).toList(),
          ),
        ],
      ),
      body: Consumer<FleetService>(
        builder: (context, fleetService, child) {
          return RefreshIndicator(
            onRefresh: () => fleetService.refreshFleet(),
            child: Column(
              children: [
                // Fleet Status Header
                _buildFleetStatusHeader(fleetService),

                // Search Bar
                _buildSearchBar(),

                // Filter Chips
                _buildFilterChips(fleetService),

                // Device List
                Expanded(
                  child: _buildDeviceList(fleetService),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildFleetStatusHeader(FleetService fleetService) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E1E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: fleetService.serverConnected
              ? const Color(0xFF4CAF50)
              : const Color(0xFFFF6B6B),
          width: 2,
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: fleetService.serverConnected
                      ? const Color(0xFF4CAF50)
                      : const Color(0xFFFF6B6B),
                  shape: BoxShape.circle,
                  boxShadow: [
                    if (fleetService.serverConnected)
                      BoxShadow(
                        color: const Color(0xFF4CAF50).withOpacity(0.5),
                        blurRadius: 8,
                        spreadRadius: 2,
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Text(
                fleetService.serverConnected
                    ? 'Fleet Server Connected'
                    : 'Fleet Server Disconnected',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),
              const Spacer(),
              Text(
                'Last sync: ${_formatTime(fleetService.lastSync)}',
                style: TextStyle(
                  color: Colors.grey.shade400,
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildStatusCard(
                  'Total',
                  fleetService.totalDevices.toString(),
                  Icons.devices,
                  Colors.blue,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildStatusCard(
                  'Online',
                  fleetService.onlineDevices.toString(),
                  Icons.check_circle,
                  const Color(0xFF4CAF50),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildStatusCard(
                  'Offline',
                  fleetService.offlineDevices.toString(),
                  Icons.error,
                  const Color(0xFFFF6B6B),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatusCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey.shade400,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: TextField(
        onChanged: (value) => setState(() => _searchQuery = value),
        decoration: InputDecoration(
          hintText: 'Search by name, location, or ID...',
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

  Widget _buildFilterChips(FleetService fleetService) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          FilterChip(
            label: const Text('Online Only'),
            selected: _showOnlineOnly,
            onSelected: (value) => setState(() => _showOnlineOnly = value),
            selectedColor: const Color(0xFF4CAF50).withOpacity(0.3),
            checkmarkColor: const Color(0xFF4CAF50),
          ),
          const SizedBox(width: 8),
          Chip(
            label: Text(
              '${_getFilteredDevices(fleetService).length} device${_getFilteredDevices(fleetService).length == 1 ? '' : 's'}',
            ),
            backgroundColor: Colors.grey.shade800,
          ),
        ],
      ),
    );
  }

  List<FleetDevice> _getFilteredDevices(FleetService fleetService) {
    var devices = fleetService.searchDevices(_searchQuery);
    if (_showOnlineOnly) {
      devices = devices.where((d) => d.isOnline).toList();
    }
    return devices;
  }

  Widget _buildDeviceList(FleetService fleetService) {
    final devices = _getFilteredDevices(fleetService);

    if (devices.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.devices_other, size: 64, color: Colors.grey.shade600),
            const SizedBox(height: 16),
            Text(
              _searchQuery.isNotEmpty
                  ? 'No devices match your search'
                  : 'No devices available',
              style: TextStyle(color: Colors.grey.shade400, fontSize: 16),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: devices.length,
      itemBuilder: (context, index) {
        return _buildDeviceCard(devices[index]);
      },
    );
  }

  Widget _buildDeviceCard(FleetDevice device) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => _showDeviceDetails(device),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header Row
              Row(
                children: [
                  // Status Indicator
                  Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: device.isOnline
                          ? const Color(0xFF4CAF50)
                          : const Color(0xFFFF6B6B),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 12),
                  // Device Name
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          device.customName,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          device.location,
                          style: TextStyle(
                            color: Colors.grey.shade400,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Status Badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: device.isOnline
                          ? const Color(0xFF4CAF50).withOpacity(0.2)
                          : const Color(0xFFFF6B6B).withOpacity(0.2),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: device.isOnline
                            ? const Color(0xFF4CAF50)
                            : const Color(0xFFFF6B6B),
                      ),
                    ),
                    child: Text(
                      device.isOnline ? 'ONLINE' : 'OFFLINE',
                      style: TextStyle(
                        color: device.isOnline
                            ? const Color(0xFF4CAF50)
                            : const Color(0xFFFF6B6B),
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              // Device Info
              Row(
                children: [
                  _buildInfoChip(Icons.fingerprint, device.shortId),
                  const SizedBox(width: 8),
                  _buildInfoChip(Icons.memory, device.firmwareVersion),
                  const SizedBox(width: 8),
                  _buildInfoChip(Icons.settings_input_component, device.gateTypeDisplay),
                ],
              ),
              const SizedBox(height: 12),
              // Signal & Last Seen
              Row(
                children: [
                  Icon(
                    Icons.signal_cellular_alt,
                    size: 16,
                    color: _getSignalColor(device.signalStrength),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    device.isOnline
                        ? '${device.signalStrength}% ${device.signalQuality.displayName}'
                        : 'No signal',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade400,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Icon(Icons.access_time, size: 16, color: Colors.grey.shade400),
                  const SizedBox(width: 4),
                  Text(
                    device.isOnline ? device.timeSinceLastSeen : 'Last seen: ${device.timeSinceLastSeen}',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade400,
                    ),
                  ),
                ],
              ),
              if (device.currentState != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.info_outline, size: 16, color: Colors.grey.shade400),
                    const SizedBox(width: 4),
                    Text(
                      'Current state: ${device.currentState}',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade400,
                        fontStyle: FontStyle.italic,
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

  Widget _buildInfoChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.grey.shade800,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.grey.shade400),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(fontSize: 11, color: Colors.grey.shade300),
          ),
        ],
      ),
    );
  }

  Color _getSignalColor(int strength) {
    if (strength >= 75) return const Color(0xFF4CAF50);
    if (strength >= 50) return Colors.lightGreen;
    if (strength >= 25) return Colors.orange;
    return const Color(0xFFFF6B6B);
  }

  String _formatTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);

    if (diff.inSeconds < 60) return '${diff.inSeconds}s ago';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    return '${diff.inHours}h ago';
  }

  void _showDeviceDetails(FleetDevice device) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1E1E1E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 16,
                  height: 16,
                  decoration: BoxDecoration(
                    color: device.isOnline
                        ? const Color(0xFF4CAF50)
                        : const Color(0xFFFF6B6B),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    device.customName,
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildDetailRow('Device ID', device.deviceId),
            _buildDetailRow('Location', device.location),
            _buildDetailRow('Gate Type', device.gateTypeDisplay),
            _buildDetailRow('Firmware', device.firmwareVersion),
            _buildDetailRow('Status', device.isOnline ? 'Online' : 'Offline'),
            if (device.isOnline) ...[
              _buildDetailRow('Signal', '${device.signalStrength}% (${device.signalQuality.displayName})'),
              _buildDetailRow('Last Seen', device.timeSinceLastSeen),
            ],
            if (device.currentState != null)
              _buildDetailRow('Current State', device.currentState!),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: device.isOnline ? () {
                      Navigator.pop(context);
                      // TODO: Connect to this device
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Connecting to ${device.customName}...')),
                      );
                    } : null,
                    icon: const Icon(Icons.link),
                    label: const Text('Connect'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF4CAF50),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      // TODO: Show device settings
                    },
                    icon: const Icon(Icons.settings),
                    label: const Text('Settings'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
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

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: TextStyle(
                color: Colors.grey.shade400,
                fontSize: 14,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
