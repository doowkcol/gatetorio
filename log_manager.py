#!/usr/bin/env python3
"""
Log Manager - Centralized logging system for Gatetorio gate controller

Provides structured logging with:
- Multiple log levels (INFO, WARNING, ERROR, CRITICAL)
- Categories for filtering (COMMAND, MOTOR, INPUT, SAFETY, etc.)
- In-memory ring buffer for efficient access
- Inter-process safe via multiprocessing.Queue
- Optional metadata for contextual information
"""

import time
import threading
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any
import multiprocessing


# Log Levels (matching Python logging module)
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50

LEVEL_NAMES = {
    DEBUG: 'DEBUG',
    INFO: 'INFO',
    WARNING: 'WARNING',
    ERROR: 'ERROR',
    CRITICAL: 'CRITICAL'
}

# Log Categories
COMMAND = 'COMMAND'      # User commands (OPEN/CLOSE/STOP/PARTIAL)
MOTOR = 'MOTOR'          # Motor position/speed changes
INPUT = 'INPUT'          # Input state changes
SAFETY = 'SAFETY'        # Safety edges, photocells, reversals
LIMIT = 'LIMIT'          # Limit switch events
CONFIG = 'CONFIG'        # Configuration changes
BLE = 'BLE'              # BLE connections/commands
SYSTEM = 'SYSTEM'        # System health, processes
FAULT = 'FAULT'          # Degraded mode, errors
TIMING = 'TIMING'        # Movement timing analysis
AUTO_CLOSE = 'AUTO_CLOSE'  # Auto-close timer events


class LogManager:
    """
    Centralized logging manager for gatetorio gate controller

    Features:
    - Ring buffer with configurable size
    - Inter-process safe via queue
    - Non-blocking log writes
    - Filtering by level and category
    - Optional metadata support
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize log manager

        Args:
            max_size: Maximum number of log entries to keep in memory (default 1000)
        """
        self.max_size = max_size

        # Ring buffer for log entries (thread-safe with lock)
        self.log_buffer = deque(maxlen=max_size)
        self.buffer_lock = threading.Lock()

        # Inter-process queue for receiving logs from other processes
        self.log_queue = multiprocessing.Queue()

        # Background thread for processing queue
        self.running = False
        self.processor_thread = None

        # Statistics
        self.total_logs = 0
        self.logs_by_level = {DEBUG: 0, INFO: 0, WARNING: 0, ERROR: 0, CRITICAL: 0}
        self.logs_by_category = {}

    def start(self):
        """Start the log processor thread"""
        if self.running:
            return

        self.running = True
        self.processor_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.processor_thread.start()

    def stop(self):
        """Stop the log processor thread"""
        self.running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=1.0)

    def _process_queue(self):
        """Background thread that processes log entries from queue"""
        while self.running:
            try:
                # Non-blocking get with timeout
                log_entry = self.log_queue.get(timeout=0.1)

                with self.buffer_lock:
                    self.log_buffer.append(log_entry)

                    # Update statistics
                    self.total_logs += 1
                    level = log_entry.get('level', INFO)
                    category = log_entry.get('category', 'UNKNOWN')

                    if level in self.logs_by_level:
                        self.logs_by_level[level] += 1

                    if category not in self.logs_by_category:
                        self.logs_by_category[category] = 0
                    self.logs_by_category[category] += 1

            except:
                # Queue empty or timeout - continue
                continue

    def log(self, level: int, category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a log entry

        Args:
            level: Log level (INFO, WARNING, ERROR, CRITICAL)
            category: Log category (COMMAND, MOTOR, INPUT, etc.)
            message: Human-readable log message
            metadata: Optional dictionary with additional context
        """
        entry = {
            'timestamp': time.time(),
            'level': level,
            'level_name': LEVEL_NAMES.get(level, 'UNKNOWN'),
            'category': category,
            'message': message,
            'metadata': metadata or {}
        }

        # Put in queue (non-blocking)
        try:
            self.log_queue.put_nowait(entry)
        except:
            # Queue full - skip this log (shouldn't happen with unbounded queue)
            pass

    def info(self, category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log an INFO level message"""
        self.log(INFO, category, message, metadata)

    def warning(self, category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a WARNING level message"""
        self.log(WARNING, category, message, metadata)

    def error(self, category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log an ERROR level message"""
        self.log(ERROR, category, message, metadata)

    def critical(self, category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a CRITICAL level message"""
        self.log(CRITICAL, category, message, metadata)

    def get_logs(self,
                 limit: Optional[int] = None,
                 min_level: Optional[int] = None,
                 category: Optional[str] = None,
                 since: Optional[float] = None) -> List[Dict]:
        """
        Retrieve log entries with optional filtering

        Args:
            limit: Maximum number of entries to return (most recent first)
            min_level: Minimum log level (e.g., WARNING to exclude INFO)
            category: Filter by category
            since: Only return logs since this timestamp (time.time())

        Returns:
            List of log entry dictionaries
        """
        with self.buffer_lock:
            # Convert deque to list (most recent last)
            logs = list(self.log_buffer)

        # Apply filters
        if min_level is not None:
            logs = [log for log in logs if log['level'] >= min_level]

        if category is not None:
            logs = [log for log in logs if log['category'] == category]

        if since is not None:
            logs = [log for log in logs if log['timestamp'] >= since]

        # Reverse to get most recent first
        logs.reverse()

        # Apply limit
        if limit is not None:
            logs = logs[:limit]

        return logs

    def get_statistics(self) -> Dict:
        """Get logging statistics"""
        with self.buffer_lock:
            return {
                'total_logs': self.total_logs,
                'buffer_size': len(self.log_buffer),
                'buffer_max': self.max_size,
                'by_level': dict(self.logs_by_level),
                'by_category': dict(self.logs_by_category)
            }

    def clear(self):
        """Clear all log entries"""
        with self.buffer_lock:
            self.log_buffer.clear()
            self.total_logs = 0
            self.logs_by_level = {DEBUG: 0, INFO: 0, WARNING: 0, ERROR: 0, CRITICAL: 0}
            self.logs_by_category = {}

    @staticmethod
    def format_timestamp(timestamp: float, relative: bool = True) -> str:
        """
        Format a timestamp for display

        Args:
            timestamp: Unix timestamp from time.time()
            relative: If True, return relative time (e.g., "2m ago"), else absolute

        Returns:
            Formatted timestamp string
        """
        if relative:
            elapsed = time.time() - timestamp

            if elapsed < 1:
                return "just now"
            elif elapsed < 60:
                return f"{int(elapsed)}s ago"
            elif elapsed < 3600:
                return f"{int(elapsed / 60)}m ago"
            elif elapsed < 86400:
                return f"{int(elapsed / 3600)}h ago"
            else:
                return f"{int(elapsed / 86400)}d ago"
        else:
            # Absolute timestamp
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')


# Global instance (can be accessed by all modules)
_global_log_manager = None


def get_log_manager() -> Optional[LogManager]:
    """Get the global log manager instance"""
    return _global_log_manager


def set_log_manager(log_manager: LogManager):
    """Set the global log manager instance"""
    global _global_log_manager
    _global_log_manager = log_manager


def log(level: int, category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to log to global instance"""
    if _global_log_manager:
        _global_log_manager.log(level, category, message, metadata)


def info(category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to log INFO to global instance"""
    if _global_log_manager:
        _global_log_manager.info(category, message, metadata)


def warning(category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to log WARNING to global instance"""
    if _global_log_manager:
        _global_log_manager.warning(category, message, metadata)


def error(category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to log ERROR to global instance"""
    if _global_log_manager:
        _global_log_manager.error(category, message, metadata)


def critical(category: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience function to log CRITICAL to global instance"""
    if _global_log_manager:
        _global_log_manager.critical(category, message, metadata)
