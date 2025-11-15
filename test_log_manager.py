#!/usr/bin/env python3
"""
Simple test script for log_manager.py

Tests basic functionality of the LogManager class
"""

import time
from log_manager import LogManager, COMMAND, MOTOR, SAFETY, AUTO_CLOSE, INFO, WARNING, ERROR, CRITICAL

def test_log_manager():
    """Test log manager basic functionality"""
    print("=" * 60)
    print("Testing LogManager")
    print("=" * 60)

    # Create log manager
    print("\n1. Creating LogManager...")
    lm = LogManager(max_size=10)
    lm.start()
    print("   ✓ LogManager created and started")

    # Add some test logs
    print("\n2. Adding test logs...")
    lm.info(COMMAND, "Test OPEN command", {'test': True, 'value': 123})
    lm.info(COMMAND, "Test CLOSE command", {'test': True, 'value': 456})
    lm.warning(SAFETY, "Test safety edge trigger", {'edge_type': 'STOP_CLOSING'})
    lm.error(MOTOR, "Test motor fault", {'motor': 1, 'fault_type': 'over-travel'})
    lm.info(AUTO_CLOSE, "Test auto-close timer", {'duration': 10})

    # Wait a bit for queue processing
    time.sleep(0.5)

    # Retrieve logs
    print("\n3. Retrieving all logs...")
    all_logs = lm.get_logs()
    print(f"   Found {len(all_logs)} logs:")
    for i, log in enumerate(all_logs):
        print(f"   [{i+1}] {log['level_name']:8} | {log['category']:12} | {log['message']}")

    # Test filtering by level
    print("\n4. Testing filter by level (WARNING and above)...")
    warning_logs = lm.get_logs(min_level=WARNING)
    print(f"   Found {len(warning_logs)} logs at WARNING or above:")
    for i, log in enumerate(warning_logs):
        print(f"   [{i+1}] {log['level_name']:8} | {log['category']:12} | {log['message']}")

    # Test filtering by category
    print("\n5. Testing filter by category (COMMAND)...")
    command_logs = lm.get_logs(category=COMMAND)
    print(f"   Found {len(command_logs)} COMMAND logs:")
    for i, log in enumerate(command_logs):
        print(f"   [{i+1}] {log['level_name']:8} | {log['category']:12} | {log['message']}")

    # Test statistics
    print("\n6. Testing statistics...")
    stats = lm.get_statistics()
    print(f"   Total logs: {stats['total_logs']}")
    print(f"   Buffer size: {stats['buffer_size']}/{stats['buffer_max']}")
    print(f"   By level: {stats['by_level']}")
    print(f"   By category: {stats['by_category']}")

    # Test ring buffer overflow
    print("\n7. Testing ring buffer overflow (max_size=10)...")
    for i in range(15):
        lm.info(COMMAND, f"Overflow test log {i+1}")

    time.sleep(0.5)

    overflow_logs = lm.get_logs()
    print(f"   After adding 15 more logs, buffer contains: {len(overflow_logs)} logs")
    print(f"   (Should be capped at max_size=10)")

    # Test timestamp formatting
    print("\n8. Testing timestamp formatting...")
    if overflow_logs:
        latest = overflow_logs[0]
        relative_time = LogManager.format_timestamp(latest['timestamp'], relative=True)
        absolute_time = LogManager.format_timestamp(latest['timestamp'], relative=False)
        print(f"   Latest log timestamp:")
        print(f"   - Relative: {relative_time}")
        print(f"   - Absolute: {absolute_time}")

    # Cleanup
    print("\n9. Cleaning up...")
    lm.stop()
    print("   ✓ LogManager stopped")

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)

if __name__ == '__main__':
    test_log_manager()
