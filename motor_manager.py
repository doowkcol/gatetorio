#!/usr/bin/env python3
"""
Motor Manager - Separate process for motor control
Handles physical motor control based on shared memory state
"""

from gpiozero import Motor, Device
from time import time, sleep
import multiprocessing
import lgpio

class MotorManager:
    def __init__(self, shared_dict, config):
        """Initialize motor manager with shared memory and config"""
        self.shared = shared_dict
        
        # Config values
        self.motor1_run_time = config['motor1_run_time']
        self.motor2_run_time = config['motor2_run_time']
        self.motor2_enabled = config.get('motor2_enabled', True)
        self.motor1_open_delay = config['motor1_open_delay']
        self.motor2_close_delay = config['motor2_close_delay']
        self.partial_1_position = config['partial_1_position']
        self.partial_2_position = config['partial_2_position']
        self.deadman_speed = config['deadman_speed']
        self.ramp_time = config.get('ramp_time', 0.5)  # Default 0.5s if not in config

        # Limit switch configuration
        self.limit_switches_enabled = config.get('limit_switches_enabled', False)
        self.motor1_use_limit_switches = config.get('motor1_use_limit_switches', False)
        self.motor2_use_limit_switches = config.get('motor2_use_limit_switches', False)
        self.limit_switch_creep_speed = config.get('limit_switch_creep_speed', 0.2)
        self.opening_slowdown_percent = config.get('opening_slowdown_percent', 2.0)
        self.closing_slowdown_percent = config.get('closing_slowdown_percent', 10.0)
        self.slowdown_distance = config.get('slowdown_distance', 2.0)  # Seconds for gradual slowdown
        self.learning_speed = config.get('learning_speed', 0.3)
        self.open_speed = config.get('open_speed', 1.0)  # User-configurable open speed (0.1-1.0)
        self.close_speed = config.get('close_speed', 1.0)  # User-configurable close speed (0.1-1.0)
        
        # Force release ALL GPIO at system level before initializing motors
        # This fixes "GPIO busy" error from crashed previous sessions
        try:
            # Close any existing gpiozero pin factory
            if Device.pin_factory is not None:
                Device.pin_factory.close()
        except:
            pass
        
        # Also try to close any orphaned lgpio handles (Pi 5 uses chip 4)
        try:
            for handle in range(256):  # Check possible handle values
                try:
                    lgpio.gpiochip_close(handle)
                except:
                    pass
        except:
            pass
        
        # Initialize motors
        self.motor1 = Motor(forward=17, backward=18, enable=27, pwm=True)
        self.motor2 = Motor(forward=22, backward=23, enable=4, pwm=True)

        # Fault tracking (per motor, degrades globally)
        self.m1_consecutive_faults = 0
        self.m2_consecutive_faults = 0
        self.degraded_mode = False  # True when in 30% speed fallback mode
        self.degraded_speed = 0.3   # Speed to use when degraded

        # Fault detection thresholds
        self.over_travel_threshold = 1.20  # 120% of expected position
        self.limit_release_check = 0.50    # Check at 50% travel that starting limit released
        self.fault_trigger_count = 5       # Degrade after this many consecutive faults

        print("Motor Manager initialized")
    
    def _reload_config(self):
        """Reload config from shared memory"""
        print("Motor Manager: Reloading config from shared memory...")
        self.motor1_run_time = self.shared.get('config_motor1_run_time', self.motor1_run_time)
        self.motor2_run_time = self.shared.get('config_motor2_run_time', self.motor2_run_time)
        self.motor2_enabled = self.shared.get('config_motor2_enabled', self.motor2_enabled)
        self.motor1_open_delay = self.shared.get('config_motor1_open_delay', self.motor1_open_delay)
        self.motor2_close_delay = self.shared.get('config_motor2_close_delay', self.motor2_close_delay)
        self.partial_1_position = self.shared.get('config_partial_1_position', self.partial_1_position)
        self.partial_2_position = self.shared.get('config_partial_2_position', self.partial_2_position)
        self.deadman_speed = self.shared.get('config_deadman_speed', self.deadman_speed)
        self.ramp_time = self.shared.get('config_ramp_time', self.ramp_time)
        self.limit_switches_enabled = self.shared.get('config_limit_switches_enabled', self.limit_switches_enabled)
        self.motor1_use_limit_switches = self.shared.get('config_motor1_use_limit_switches', self.motor1_use_limit_switches)
        self.motor2_use_limit_switches = self.shared.get('config_motor2_use_limit_switches', self.motor2_use_limit_switches)
        self.limit_switch_creep_speed = self.shared.get('config_limit_switch_creep_speed', self.limit_switch_creep_speed)
        self.opening_slowdown_percent = self.shared.get('config_opening_slowdown_percent', self.opening_slowdown_percent)
        self.closing_slowdown_percent = self.shared.get('config_closing_slowdown_percent', self.closing_slowdown_percent)
        self.slowdown_distance = self.shared.get('config_slowdown_distance', self.slowdown_distance)
        self.learning_speed = self.shared.get('config_learning_speed', self.learning_speed)
        self.open_speed = self.shared.get('config_open_speed', self.open_speed)
        self.close_speed = self.shared.get('config_close_speed', self.close_speed)
        print(f"Motor Manager: Config reloaded - M1: {self.motor1_run_time}s, M2: {self.motor2_run_time}s (enabled={self.motor2_enabled}), open_speed={self.open_speed}, close_speed={self.close_speed}")

    def _record_fault(self, motor_num, fault_type, details=""):
        """Record a fault for the specified motor and check if degradation needed"""
        if motor_num == 1:
            self.m1_consecutive_faults += 1
            fault_count = self.m1_consecutive_faults
        else:
            self.m2_consecutive_faults += 1
            fault_count = self.m2_consecutive_faults

        print(f"[FAULT] M{motor_num} {fault_type}: {details} (consecutive: {fault_count})")

        # Check if we need to degrade (either motor hitting fault threshold triggers degradation)
        if fault_count >= self.fault_trigger_count or self.m1_consecutive_faults >= self.fault_trigger_count or self.m2_consecutive_faults >= self.fault_trigger_count:
            if not self.degraded_mode:
                self._enter_degraded_mode(motor_num, fault_type)

    def _clear_fault(self, motor_num):
        """Clear fault counter for a motor after successful movement"""
        if motor_num == 1:
            if self.m1_consecutive_faults > 0:
                print(f"[FAULT] M1 fault counter cleared (was {self.m1_consecutive_faults})")
                self.m1_consecutive_faults = 0
        else:
            if self.m2_consecutive_faults > 0:
                print(f"[FAULT] M2 fault counter cleared (was {self.m2_consecutive_faults})")
                self.m2_consecutive_faults = 0

    def _enter_degraded_mode(self, motor_num, fault_type):
        """Enter degraded mode: disable limit switches, set speed to 30%, log fault"""
        self.degraded_mode = True
        print(f"")
        print(f"{'='*60}")
        print(f"[FAULT] ENTERING DEGRADED MODE")
        print(f"  Trigger: M{motor_num} {fault_type}")
        print(f"  M1 faults: {self.m1_consecutive_faults}, M2 faults: {self.m2_consecutive_faults}")
        print(f"  Action: Switching to time-based mode at {self.degraded_speed*100}% speed")
        print(f"{'='*60}")
        print(f"")

        # Disable limit switches and switch to time-based operation
        self.motor1_use_limit_switches = False
        self.motor2_use_limit_switches = False
        self.limit_switches_enabled = False

        # Force speed to degraded level
        self.open_speed = self.degraded_speed
        self.close_speed = self.degraded_speed

        # Update shared memory for UI visibility
        self.shared['degraded_mode'] = True
        self.shared['config_open_speed'] = self.degraded_speed
        self.shared['config_close_speed'] = self.degraded_speed

    def _check_over_travel(self, motor_num, position, expected_time, direction):
        """Check if motor has over-traveled (120% threshold)"""
        over_travel_position = expected_time * self.over_travel_threshold

        if position > over_travel_position:
            self._record_fault(motor_num, "OVER_TRAVEL",
                             f"{direction} - position {position:.2f}s exceeds {over_travel_position:.2f}s ({self.over_travel_threshold*100}%)")
            return True
        return False

    def _check_limit_release(self, motor_num, position, expected_time, direction, start_limit_active):
        """Check if starting limit has released at 50% travel"""
        halfway_position = expected_time * self.limit_release_check

        if position >= halfway_position and start_limit_active:
            self._record_fault(motor_num, "LIMIT_STUCK",
                             f"{direction} - {direction.lower().replace('ing','')} limit still active at {position:.2f}s (50% = {halfway_position:.2f}s)")
            return True
        return False

    def _check_limit_activation(self, motor_num, position, expected_time, direction,
                               target_limit_active, start_limit_active, close_limit_active, open_limit_active):
        """Check limit switch states at expected completion"""
        # At full travel, check if we reached the correct limit
        over_travel_position = expected_time * self.over_travel_threshold

        if position >= expected_time and position < over_travel_position:
            # We're at or past expected position but haven't exceeded safety margin
            if not target_limit_active:
                # Target limit not active - could be faulty limit or motor issue
                if direction == "OPENING":
                    if start_limit_active and close_limit_active:
                        # Both close limits still active - motor likely not moving
                        self._record_fault(motor_num, "MOTOR_STALLED",
                                         f"{direction} - close limits still active, motor may not be running")
                    else:
                        self._record_fault(motor_num, "LIMIT_MISSING",
                                         f"{direction} - open limit not activated at {position:.2f}s")
                else:  # CLOSING
                    if start_limit_active and open_limit_active:
                        # Both open limits still active - motor likely not moving
                        self._record_fault(motor_num, "MOTOR_STALLED",
                                         f"{direction} - open limits still active, motor may not be running")
                    else:
                        self._record_fault(motor_num, "LIMIT_MISSING",
                                         f"{direction} - close limit not activated at {position:.2f}s")
                return True
            else:
                # Successfully reached limit - clear fault counter
                self._clear_fault(motor_num)
                return False
        return False

    def run(self):
        """Main motor control loop - runs at 20Hz"""
        print("Motor Manager process started")

        while self.shared['running']:
            now = time()

            # Update heartbeat
            self.shared['motor_manager_heartbeat'] = now

            # Check for config reload request
            if self.shared.get('config_reload_flag', False):
                self._reload_config()
                self.shared['config_reload_flag'] = False

            # If auto-learn is active, handle it exclusively
            if self.shared.get('auto_learn_active', False):
                self._process_auto_learn(now)
                sleep(0.05)
                continue

            # Check deadman controls (direct motor control)
            deadman_active = self._process_deadman_controls(now)

            # Process limit switches (detection and learning mode)
            if self.limit_switches_enabled:
                self._process_limit_switches(now)

            # Update motor positions if moving (but not during safety reversal)
            if self.shared['movement_start_time'] and not self.shared['opening_paused'] and not self.shared['safety_reversing'] and not deadman_active:
                self._update_motor_positions(now)

            # Update motor speeds (ALWAYS - handles safety reversal, deadman, and normal movement)
            if not deadman_active:
                self._update_motor_speeds(now)

            # Sleep 50ms (20Hz)
            sleep(0.05)
        
        # Cleanup on exit
        self.motor1.stop()
        self.motor2.stop()
        print("Motor Manager process stopped")

    def _process_auto_learn(self, now):
        """Process auto-learn state machine - progressive learning: 0.25 -> 0.5 -> full speed"""
        # Initialize state on first call or restart after completion
        # Check if state is missing OR count variables don't exist (means we need to re-initialize)
        if not self.shared.get('auto_learn_state') or 'auto_learn_m1_open_count' not in self.shared:
            self.shared['auto_learn_state'] = 'IDLE'
            self.shared['auto_learn_phase_start'] = now
            self.shared['auto_learn_m1_start'] = None
            self.shared['auto_learn_m2_start'] = None
            # Running averages for each motor and direction
            self.shared['auto_learn_m1_open_avg'] = 0.0
            self.shared['auto_learn_m1_close_avg'] = 0.0
            self.shared['auto_learn_m2_open_avg'] = 0.0
            self.shared['auto_learn_m2_close_avg'] = 0.0
            # Counts for averaging
            self.shared['auto_learn_m1_open_count'] = 0
            self.shared['auto_learn_m1_close_count'] = 0
            self.shared['auto_learn_m2_open_count'] = 0
            self.shared['auto_learn_m2_close_count'] = 0
            # Full-speed cycle counter
            self.shared['auto_learn_cycle'] = 0

        state = self.shared['auto_learn_state']

        # State: IDLE - Check initial position and decide where to start
        if state == 'IDLE':
            print("\n=== AUTO-LEARN: PROGRESSIVE SEQUENCE ===")

            # Check if we're already at open limits
            m1_at_open = self.shared.get('open_limit_m1_active', False)
            m2_at_open = self.shared.get('open_limit_m2_active', False)

            if m1_at_open or m2_at_open:
                # Already at open position - need to close first to get to known state
                print("Detected motors at open limits - closing to starting position first...")
                self.shared['auto_learn_state'] = 'INITIAL_CLOSE_M2'
                self.shared['auto_learn_status_msg'] = 'Closing to start position...'
                self.shared['auto_learn_m2_start'] = now
            else:
                # Start normal sequence - open M1 first
                print("Step 1: Opening M1 at 0.25 speed to find open limit...")
                self.shared['auto_learn_state'] = 'M1_OPEN_025'
                self.shared['auto_learn_status_msg'] = 'Opening M1 at 0.25 speed...'
                self.shared['auto_learn_m1_start'] = now
                self.shared['m1_position'] = 0.0
                self.shared['m2_position'] = 0.0

        # State: INITIAL_CLOSE_M2 - Close M2 to get to starting position
        elif state == 'INITIAL_CLOSE_M2':
            self.motor1.stop()
            self.motor2.backward(0.25)
            if self.shared.get('close_limit_m2_active', False):
                print("M2 at close limit")
                self.motor2.stop()
                self.shared['auto_learn_state'] = 'INITIAL_CLOSE_M1'
                self.shared['auto_learn_m1_start'] = now

        # State: INITIAL_CLOSE_M1 - Close M1 to get to starting position
        elif state == 'INITIAL_CLOSE_M1':
            self.motor1.backward(0.25)
            self.motor2.stop()
            if self.shared.get('close_limit_m1_active', False):
                print("M1 at close limit - ready to start learning sequence")
                self.motor1.stop()
                # Reset positions and start the normal sequence
                self.shared['m1_position'] = 0.0
                self.shared['m2_position'] = 0.0
                self.shared['auto_learn_state'] = 'PAUSE_BEFORE_START'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_BEFORE_START - Brief pause before starting learning sequence
        elif state == 'PAUSE_BEFORE_START':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 1.0:
                print("\nStarting learning sequence from closed position...")
                print("Step 1: Opening M1 at 0.25 speed to find open limit...")
                self.shared['auto_learn_state'] = 'M1_OPEN_025'
                self.shared['auto_learn_status_msg'] = 'Opening M1 at 0.25 speed...'
                self.shared['auto_learn_m1_start'] = now

        # State: M1_OPEN_025 - M1 opening at 0.25 speed to find limit
        elif state == 'M1_OPEN_025':
            self.motor1.forward(0.25)
            self.motor2.stop()
            if self.shared.get('open_limit_m1_active', False):
                time_taken = now - self.shared['auto_learn_m1_start']
                # Convert to full-speed equivalent: time * speed
                full_speed_time = time_taken * 0.25
                # Update running average
                count = self.shared['auto_learn_m1_open_count']
                if count == 0:
                    self.shared['auto_learn_m1_open_avg'] = full_speed_time
                else:
                    avg = self.shared['auto_learn_m1_open_avg']
                    self.shared['auto_learn_m1_open_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m1_open_count'] = count + 1
                print(f"M1 open: {time_taken:.2f}s at 0.25 speed = {full_speed_time:.2f}s full speed")
                print(f"  M1 open average: {self.shared['auto_learn_m1_open_avg']:.2f}s ({self.shared['auto_learn_m1_open_count']} samples)")
                self.motor1.stop()

                self.shared['auto_learn_state'] = 'PAUSE_1'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_1 - Brief pause before M2 opens
        elif state == 'PAUSE_1':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                print("Step 2: Opening M2 at 0.25 speed to find open limit...")
                self.shared['auto_learn_state'] = 'M2_OPEN_025'
                self.shared['auto_learn_status_msg'] = 'Opening M2 at 0.25 speed...'
                self.shared['auto_learn_m2_start'] = now

        # State: M2_OPEN_025 - M2 opening at 0.25 speed to find limit
        elif state == 'M2_OPEN_025':
            self.motor1.stop()
            self.motor2.forward(0.25)
            if self.shared.get('open_limit_m2_active', False):
                time_taken = now - self.shared['auto_learn_m2_start']
                full_speed_time = time_taken * 0.25
                count = self.shared['auto_learn_m2_open_count']
                if count == 0:
                    self.shared['auto_learn_m2_open_avg'] = full_speed_time
                else:
                    avg = self.shared['auto_learn_m2_open_avg']
                    self.shared['auto_learn_m2_open_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m2_open_count'] = count + 1
                print(f"M2 open: {time_taken:.2f}s at 0.25 speed = {full_speed_time:.2f}s full speed")
                print(f"  M2 open average: {self.shared['auto_learn_m2_open_avg']:.2f}s ({self.shared['auto_learn_m2_open_count']} samples)")
                self.motor2.stop()

                self.shared['auto_learn_state'] = 'PAUSE_2'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_2 - Brief pause before M2 closes
        elif state == 'PAUSE_2':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                print("Step 3: Closing M2 at 0.25 speed to record close time...")
                self.shared['auto_learn_state'] = 'M2_CLOSE_025'
                self.shared['auto_learn_status_msg'] = 'Closing M2 at 0.25 speed...'
                self.shared['auto_learn_m2_start'] = now

        # State: M2_CLOSE_025 - M2 closing at 0.25 speed, record time
        elif state == 'M2_CLOSE_025':
            self.motor1.stop()
            self.motor2.backward(0.25)
            if self.shared.get('close_limit_m2_active', False):
                time_taken = now - self.shared['auto_learn_m2_start']
                full_speed_time = time_taken * 0.25
                count = self.shared['auto_learn_m2_close_count']
                if count == 0:
                    self.shared['auto_learn_m2_close_avg'] = full_speed_time
                else:
                    avg = self.shared['auto_learn_m2_close_avg']
                    self.shared['auto_learn_m2_close_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m2_close_count'] = count + 1
                print(f"M2 close: {time_taken:.2f}s at 0.25 speed = {full_speed_time:.2f}s full speed")
                print(f"  M2 close average: {self.shared['auto_learn_m2_close_avg']:.2f}s ({self.shared['auto_learn_m2_close_count']} samples)")
                self.motor2.stop()

                self.shared['auto_learn_state'] = 'PAUSE_3'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_3 - Brief pause before M1 closes
        elif state == 'PAUSE_3':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                print("Step 4: Closing M1 at 0.25 speed to record close time...")
                self.shared['auto_learn_state'] = 'M1_CLOSE_025'
                self.shared['auto_learn_status_msg'] = 'Closing M1 at 0.25 speed...'
                self.shared['auto_learn_m1_start'] = now

        # State: M1_CLOSE_025 - M1 closing at 0.25 speed, record time
        elif state == 'M1_CLOSE_025':
            self.motor1.backward(0.25)
            self.motor2.stop()
            if self.shared.get('close_limit_m1_active', False):
                time_taken = now - self.shared['auto_learn_m1_start']
                full_speed_time = time_taken * 0.25
                count = self.shared['auto_learn_m1_close_count']
                if count == 0:
                    self.shared['auto_learn_m1_close_avg'] = full_speed_time
                else:
                    avg = self.shared['auto_learn_m1_close_avg']
                    self.shared['auto_learn_m1_close_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m1_close_count'] = count + 1
                print(f"M1 close: {time_taken:.2f}s at 0.25 speed = {full_speed_time:.2f}s full speed")
                print(f"  M1 close average: {self.shared['auto_learn_m1_close_avg']:.2f}s ({self.shared['auto_learn_m1_close_count']} samples)")
                self.motor1.stop()

                self.shared['auto_learn_state'] = 'PAUSE_4'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_4 - Brief pause before 0.5 speed cycles
        elif state == 'PAUSE_4':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 1.0:
                print("\n=== Phase 2: 0.5 Speed Cycles ===")
                print("Step 5: Opening M1 at 0.5 speed...")
                self.shared['auto_learn_state'] = 'M1_OPEN_05'
                self.shared['auto_learn_status_msg'] = 'Opening M1 at 0.5 speed...'
                self.shared['auto_learn_m1_start'] = now

        # State: M1_OPEN_05 - M1 opening at 0.5 speed
        elif state == 'M1_OPEN_05':
            self.motor1.forward(0.5)
            self.motor2.stop()
            if self.shared.get('open_limit_m1_active', False):
                time_taken = now - self.shared['auto_learn_m1_start']
                full_speed_time = time_taken * 0.5
                count = self.shared['auto_learn_m1_open_count']
                avg = self.shared['auto_learn_m1_open_avg']
                self.shared['auto_learn_m1_open_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m1_open_count'] = count + 1
                print(f"M1 open: {time_taken:.2f}s at 0.5 speed = {full_speed_time:.2f}s full speed")
                print(f"  M1 open average: {self.shared['auto_learn_m1_open_avg']:.2f}s ({self.shared['auto_learn_m1_open_count']} samples)")
                self.motor1.stop()

                self.shared['auto_learn_state'] = 'PAUSE_5'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_5 - Brief pause before M2 opens at 0.5
        elif state == 'PAUSE_5':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                print("Step 6: Opening M2 at 0.5 speed...")
                self.shared['auto_learn_state'] = 'M2_OPEN_05'
                self.shared['auto_learn_status_msg'] = 'Opening M2 at 0.5 speed...'
                self.shared['auto_learn_m2_start'] = now

        # State: M2_OPEN_05 - M2 opening at 0.5 speed
        elif state == 'M2_OPEN_05':
            self.motor1.stop()
            self.motor2.forward(0.5)
            if self.shared.get('open_limit_m2_active', False):
                time_taken = now - self.shared['auto_learn_m2_start']
                full_speed_time = time_taken * 0.5
                count = self.shared['auto_learn_m2_open_count']
                avg = self.shared['auto_learn_m2_open_avg']
                self.shared['auto_learn_m2_open_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m2_open_count'] = count + 1
                print(f"M2 open: {time_taken:.2f}s at 0.5 speed = {full_speed_time:.2f}s full speed")
                print(f"  M2 open average: {self.shared['auto_learn_m2_open_avg']:.2f}s ({self.shared['auto_learn_m2_open_count']} samples)")
                self.motor2.stop()

                self.shared['auto_learn_state'] = 'PAUSE_6'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_6 - Brief pause before M2 closes at 0.5
        elif state == 'PAUSE_6':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                print("Step 7: Closing M2 at 0.5 speed...")
                self.shared['auto_learn_state'] = 'M2_CLOSE_05'
                self.shared['auto_learn_status_msg'] = 'Closing M2 at 0.5 speed...'
                self.shared['auto_learn_m2_start'] = now

        # State: M2_CLOSE_05 - M2 closing at 0.5 speed
        elif state == 'M2_CLOSE_05':
            self.motor1.stop()
            self.motor2.backward(0.5)
            if self.shared.get('close_limit_m2_active', False):
                time_taken = now - self.shared['auto_learn_m2_start']
                full_speed_time = time_taken * 0.5
                count = self.shared['auto_learn_m2_close_count']
                avg = self.shared['auto_learn_m2_close_avg']
                self.shared['auto_learn_m2_close_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m2_close_count'] = count + 1
                print(f"M2 close: {time_taken:.2f}s at 0.5 speed = {full_speed_time:.2f}s full speed")
                print(f"  M2 close average: {self.shared['auto_learn_m2_close_avg']:.2f}s ({self.shared['auto_learn_m2_close_count']} samples)")
                self.motor2.stop()

                self.shared['auto_learn_state'] = 'PAUSE_7'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_7 - Brief pause before M1 closes at 0.5
        elif state == 'PAUSE_7':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                print("Step 8: Closing M1 at 0.5 speed...")
                self.shared['auto_learn_state'] = 'M1_CLOSE_05'
                self.shared['auto_learn_status_msg'] = 'Closing M1 at 0.5 speed...'
                self.shared['auto_learn_m1_start'] = now

        # State: M1_CLOSE_05 - M1 closing at 0.5 speed
        elif state == 'M1_CLOSE_05':
            self.motor1.backward(0.5)
            self.motor2.stop()
            if self.shared.get('close_limit_m1_active', False):
                time_taken = now - self.shared['auto_learn_m1_start']
                full_speed_time = time_taken * 0.5
                count = self.shared['auto_learn_m1_close_count']
                avg = self.shared['auto_learn_m1_close_avg']
                self.shared['auto_learn_m1_close_avg'] = (avg * count + full_speed_time) / (count + 1)
                self.shared['auto_learn_m1_close_count'] = count + 1
                print(f"M1 close: {time_taken:.2f}s at 0.5 speed = {full_speed_time:.2f}s full speed")
                print(f"  M1 close average: {self.shared['auto_learn_m1_close_avg']:.2f}s ({self.shared['auto_learn_m1_close_count']} samples)")
                self.motor1.stop()

                self.shared['auto_learn_state'] = 'PAUSE_8'
                self.shared['auto_learn_phase_start'] = now
                self.shared['auto_learn_cycle'] = 0

        # State: PAUSE_8 - Prepare for full-speed cycles
        elif state == 'PAUSE_8':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 1.0:
                print("\n=== Phase 3: Full-Speed Cycles with Minimal Slowdown ===")
                self.shared['auto_learn_cycle'] = 1
                self.shared['auto_learn_state'] = 'FULL_OPEN_START'
                self.shared['auto_learn_status_msg'] = 'Full-speed cycle 1: Opening...'

        # State: FULL_OPEN_START - Start full-speed opening (M1 then M2 with delay)
        elif state == 'FULL_OPEN_START':
            cycle = self.shared['auto_learn_cycle']
            print(f"\nCycle {cycle}: Opening at full speed (M1 then M2 with {self.motor1_open_delay}s delay)...")
            self.shared['auto_learn_state'] = 'FULL_OPEN'
            self.shared['auto_learn_m1_start'] = now
            self.shared['auto_learn_m2_start'] = now + self.motor1_open_delay
            self.shared['auto_learn_m1_slowdown'] = False
            self.shared['auto_learn_m2_slowdown'] = False

        # State: FULL_OPEN - Both motors opening at full speed with minimal slowdown
        elif state == 'FULL_OPEN':
            # Get expected times for slowdown calculation
            m1_expected = self.shared.get('auto_learn_m1_open_avg', 10.0)
            m2_expected = self.shared.get('auto_learn_m2_open_avg', 10.0)

            # Very short slowdown zone (2% of expected time)
            m1_slowdown_point = m1_expected * 0.98
            m2_slowdown_point = m2_expected * 0.98

            # M1 control
            m1_done = False
            if self.shared['auto_learn_m1_start'] and now >= self.shared['auto_learn_m1_start']:
                m1_elapsed = now - self.shared['auto_learn_m1_start']
                if not self.shared.get('open_limit_m1_active', False):
                    # Not at limit yet - keep moving
                    if m1_elapsed < m1_slowdown_point:
                        self.motor1.forward(1.0)  # Full speed
                    else:
                        # In slowdown zone - creep to limit
                        if not self.shared.get('auto_learn_m1_slowdown'):
                            print(f"  M1 slowdown at {m1_elapsed:.2f}s (expected {m1_expected:.2f}s)")
                            self.shared['auto_learn_m1_slowdown'] = True
                        self.motor1.forward(self.limit_switch_creep_speed)
                else:
                    # Hit limit!
                    if self.shared['auto_learn_m1_start']:
                        total_time = now - self.shared['auto_learn_m1_start']
                        count = self.shared['auto_learn_m1_open_count']
                        avg = self.shared['auto_learn_m1_open_avg']
                        self.shared['auto_learn_m1_open_avg'] = (avg * count + total_time) / (count + 1)
                        self.shared['auto_learn_m1_open_count'] = count + 1
                        print(f"  M1 open limit: {total_time:.2f}s at full speed")
                        print(f"    M1 open average: {self.shared['auto_learn_m1_open_avg']:.2f}s ({self.shared['auto_learn_m1_open_count']} samples)")
                        self.shared['auto_learn_m1_start'] = None
                    self.motor1.stop()
                    m1_done = True
            else:
                self.motor1.stop()
                m1_done = True

            # M2 control (starts after delay)
            m2_done = False
            if self.shared['auto_learn_m2_start'] and now >= self.shared['auto_learn_m2_start']:
                m2_elapsed = now - self.shared['auto_learn_m2_start']
                if not self.shared.get('open_limit_m2_active', False):
                    if m2_elapsed < m2_slowdown_point:
                        self.motor2.forward(1.0)  # Full speed
                    else:
                        if not self.shared.get('auto_learn_m2_slowdown'):
                            print(f"  M2 slowdown at {m2_elapsed:.2f}s (expected {m2_expected:.2f}s)")
                            self.shared['auto_learn_m2_slowdown'] = True
                        self.motor2.forward(self.limit_switch_creep_speed)
                else:
                    if self.shared['auto_learn_m2_start']:
                        total_time = now - self.shared['auto_learn_m2_start']
                        count = self.shared['auto_learn_m2_open_count']
                        avg = self.shared['auto_learn_m2_open_avg']
                        self.shared['auto_learn_m2_open_avg'] = (avg * count + total_time) / (count + 1)
                        self.shared['auto_learn_m2_open_count'] = count + 1
                        print(f"  M2 open limit: {total_time:.2f}s at full speed")
                        print(f"    M2 open average: {self.shared['auto_learn_m2_open_avg']:.2f}s ({self.shared['auto_learn_m2_open_count']} samples)")
                        self.shared['auto_learn_m2_start'] = None
                    self.motor2.stop()
                    m2_done = True
            else:
                self.motor2.stop()
                m2_done = True

            # When both motors at open limit, pause before close
            if m1_done and m2_done:
                self.shared['auto_learn_state'] = 'PAUSE_BEFORE_FULL_CLOSE'
                self.shared['auto_learn_phase_start'] = now

        # State: PAUSE_BEFORE_FULL_CLOSE
        elif state == 'PAUSE_BEFORE_FULL_CLOSE':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                cycle = self.shared['auto_learn_cycle']
                print(f"Cycle {cycle}: Closing at full speed (M2 then M1 with {self.motor2_close_delay}s delay)...")
                self.shared['auto_learn_state'] = 'FULL_CLOSE'
                self.shared['auto_learn_status_msg'] = f'Cycle {cycle}: Closing...'
                self.shared['auto_learn_m2_start'] = now
                self.shared['auto_learn_m1_start'] = now + self.motor2_close_delay
                self.shared['auto_learn_m1_slowdown'] = False
                self.shared['auto_learn_m2_slowdown'] = False

        # State: FULL_CLOSE - Both motors closing at full speed with minimal slowdown
        elif state == 'FULL_CLOSE':
            # Get expected times for slowdown calculation
            m1_expected = self.shared.get('auto_learn_m1_close_avg', 10.0)
            m2_expected = self.shared.get('auto_learn_m2_close_avg', 10.0)

            # Very short slowdown zone
            m1_slowdown_point = m1_expected * 0.98
            m2_slowdown_point = m2_expected * 0.98

            # M2 control (closes first)
            m2_done = False
            if self.shared['auto_learn_m2_start'] and now >= self.shared['auto_learn_m2_start']:
                m2_elapsed = now - self.shared['auto_learn_m2_start']
                if not self.shared.get('close_limit_m2_active', False):
                    if m2_elapsed < m2_slowdown_point:
                        self.motor2.backward(1.0)  # Full speed
                    else:
                        if not self.shared.get('auto_learn_m2_slowdown'):
                            print(f"  M2 slowdown at {m2_elapsed:.2f}s (expected {m2_expected:.2f}s)")
                            self.shared['auto_learn_m2_slowdown'] = True
                        self.motor2.backward(self.limit_switch_creep_speed)
                else:
                    if self.shared['auto_learn_m2_start']:
                        total_time = now - self.shared['auto_learn_m2_start']
                        count = self.shared['auto_learn_m2_close_count']
                        avg = self.shared['auto_learn_m2_close_avg']
                        self.shared['auto_learn_m2_close_avg'] = (avg * count + total_time) / (count + 1)
                        self.shared['auto_learn_m2_close_count'] = count + 1
                        print(f"  M2 close limit: {total_time:.2f}s at full speed")
                        print(f"    M2 close average: {self.shared['auto_learn_m2_close_avg']:.2f}s ({self.shared['auto_learn_m2_close_count']} samples)")
                        self.shared['auto_learn_m2_start'] = None
                    self.motor2.stop()
                    m2_done = True
            else:
                self.motor2.stop()
                m2_done = True

            # M1 control (starts after delay)
            m1_done = False
            if self.shared['auto_learn_m1_start'] and now >= self.shared['auto_learn_m1_start']:
                m1_elapsed = now - self.shared['auto_learn_m1_start']
                if not self.shared.get('close_limit_m1_active', False):
                    if m1_elapsed < m1_slowdown_point:
                        self.motor1.backward(1.0)  # Full speed
                    else:
                        if not self.shared.get('auto_learn_m1_slowdown'):
                            print(f"  M1 slowdown at {m1_elapsed:.2f}s (expected {m1_expected:.2f}s)")
                            self.shared['auto_learn_m1_slowdown'] = True
                        self.motor1.backward(self.limit_switch_creep_speed)
                else:
                    if self.shared['auto_learn_m1_start']:
                        total_time = now - self.shared['auto_learn_m1_start']
                        count = self.shared['auto_learn_m1_close_count']
                        avg = self.shared['auto_learn_m1_close_avg']
                        self.shared['auto_learn_m1_close_avg'] = (avg * count + total_time) / (count + 1)
                        self.shared['auto_learn_m1_close_count'] = count + 1
                        print(f"  M1 close limit: {total_time:.2f}s at full speed")
                        print(f"    M1 close average: {self.shared['auto_learn_m1_close_avg']:.2f}s ({self.shared['auto_learn_m1_close_count']} samples)")
                        self.shared['auto_learn_m1_start'] = None
                    self.motor1.stop()
                    m1_done = True
            else:
                self.motor1.stop()
                m1_done = True

            # When both motors at close limit, check if need more cycles
            if m1_done and m2_done:
                cycle = self.shared['auto_learn_cycle']
                print(f"Cycle {cycle} complete")

                if cycle < 3:  # Do 3 full-speed cycles
                    self.shared['auto_learn_cycle'] = cycle + 1
                    self.shared['auto_learn_state'] = 'PAUSE_BEFORE_NEXT_CYCLE'
                    self.shared['auto_learn_phase_start'] = now
                else:
                    # All cycles done - move to final calculations
                    self.shared['auto_learn_state'] = 'COMPLETE'

        # State: PAUSE_BEFORE_NEXT_CYCLE
        elif state == 'PAUSE_BEFORE_NEXT_CYCLE':
            self.motor1.stop()
            self.motor2.stop()
            if now - self.shared['auto_learn_phase_start'] >= 1.0:
                self.shared['auto_learn_state'] = 'FULL_OPEN_START'

        # State: COMPLETE - Calculate final averages and overall work time
        elif state == 'COMPLETE':
            self.motor1.stop()
            self.motor2.stop()

            print("\n=== AUTO-LEARN COMPLETE ===")

            # Display individual averages
            m1_open_avg = self.shared.get('auto_learn_m1_open_avg', 0.0)
            m1_close_avg = self.shared.get('auto_learn_m1_close_avg', 0.0)
            m2_open_avg = self.shared.get('auto_learn_m2_open_avg', 0.0)
            m2_close_avg = self.shared.get('auto_learn_m2_close_avg', 0.0)

            print(f"M1 open average: {m1_open_avg:.2f}s ({self.shared['auto_learn_m1_open_count']} samples)")
            print(f"M1 close average: {m1_close_avg:.2f}s ({self.shared['auto_learn_m1_close_count']} samples)")
            print(f"M2 open average: {m2_open_avg:.2f}s ({self.shared['auto_learn_m2_open_count']} samples)")
            print(f"M2 close average: {m2_close_avg:.2f}s ({self.shared['auto_learn_m2_close_count']} samples)")

            # Calculate single averaged work time (average of all four values)
            overall_avg = (m1_open_avg + m1_close_avg + m2_open_avg + m2_close_avg) / 4.0
            print(f"\nSingle averaged work time: {overall_avg:.2f}s")

            # Store results in shared memory for UI to save
            self.shared['learning_m1_open_time'] = m1_open_avg
            self.shared['learning_m1_close_time'] = m1_close_avg
            self.shared['learning_m2_open_time'] = m2_open_avg
            self.shared['learning_m2_close_time'] = m2_close_avg
            self.shared['learning_overall_avg_time'] = overall_avg

            # Clear flags and temporary variables (so they get re-initialized on next run)
            self.shared['auto_learn_active'] = False
            self.shared['auto_learn_state'] = 'IDLE'
            self.shared['auto_learn_status_msg'] = 'Complete! Save times and exit engineer mode.'
            self.shared['m1_position'] = 0.0
            self.shared['m2_position'] = 0.0

            # Remove temporary count/average variables to trigger re-initialization on next run
            if 'auto_learn_m1_open_count' in self.shared:
                del self.shared['auto_learn_m1_open_count']
            if 'auto_learn_m1_close_count' in self.shared:
                del self.shared['auto_learn_m1_close_count']
            if 'auto_learn_m2_open_count' in self.shared:
                del self.shared['auto_learn_m2_open_count']
            if 'auto_learn_m2_close_count' in self.shared:
                del self.shared['auto_learn_m2_close_count']
            if 'auto_learn_m1_open_avg' in self.shared:
                del self.shared['auto_learn_m1_open_avg']
            if 'auto_learn_m1_close_avg' in self.shared:
                del self.shared['auto_learn_m1_close_avg']
            if 'auto_learn_m2_open_avg' in self.shared:
                del self.shared['auto_learn_m2_open_avg']
            if 'auto_learn_m2_close_avg' in self.shared:
                del self.shared['auto_learn_m2_close_avg']

            print("Gates in closed position - ready to save times")

    def _process_limit_switches(self, now):
        """Process limit switches - handle detection, learning mode, and position correction"""
        learning_mode = self.shared.get('learning_mode_enabled', False)

        # Check Motor 1 OPEN limit switch
        if self.motor1_use_limit_switches and self.shared.get('open_limit_m1_active', False):
            if self.shared['movement_command'] == 'OPEN' and self.shared['m1_move_start']:
                # Limit switch triggered - stop motor and set position
                if learning_mode:
                    # Record learned run time for M1 opening
                    if self.shared.get('learning_m1_start_time'):
                        learned_time = now - self.shared['learning_m1_start_time']
                        self.shared['learning_m1_open_time'] = learned_time
                        print(f"[LEARNING] M1 open time recorded: {learned_time:.2f}s")
                        self.shared['learning_m1_start_time'] = None

                # Stop motor and set to full open position
                self.motor1.stop()
                print(f"[LIMIT SWITCH] M1 OPEN limit reached - position was {self.shared['m1_position']:.2f}s, setting to {self.motor1_run_time:.2f}s")
                self.shared['m1_position'] = self.motor1_run_time
                self.shared['m1_speed'] = 0.0

        # Check Motor 1 CLOSE limit switch
        if self.motor1_use_limit_switches and self.shared.get('close_limit_m1_active', False):
            if self.shared['movement_command'] == 'CLOSE' and self.shared['m1_move_start']:
                # Limit switch triggered - stop motor and set position
                if learning_mode:
                    # Record learned run time for M1 closing
                    if self.shared.get('learning_m1_start_time'):
                        learned_time = now - self.shared['learning_m1_start_time']
                        self.shared['learning_m1_close_time'] = learned_time
                        print(f"[LEARNING] M1 close time recorded: {learned_time:.2f}s")
                        self.shared['learning_m1_start_time'] = None

                # Stop motor and set to fully closed position
                self.motor1.stop()
                self.shared['m1_position'] = 0.0
                self.shared['m1_speed'] = 0.0
                print(f"[LIMIT SWITCH] M1 CLOSE limit reached - position set to 0.0s")

        # Check Motor 2 OPEN limit switch
        if self.motor2_use_limit_switches and self.shared.get('open_limit_m2_active', False):
            if self.shared['movement_command'] == 'OPEN' and self.shared['m2_move_start']:
                # Limit switch triggered - stop motor and set position
                if learning_mode:
                    # Record learned run time for M2 opening
                    if self.shared.get('learning_m2_start_time'):
                        learned_time = now - self.shared['learning_m2_start_time']
                        self.shared['learning_m2_open_time'] = learned_time
                        print(f"[LEARNING] M2 open time recorded: {learned_time:.2f}s")
                        self.shared['learning_m2_start_time'] = None

                # Stop motor and set to full open position
                self.motor2.stop()
                self.shared['m2_position'] = self.motor2_run_time
                self.shared['m2_speed'] = 0.0
                print(f"[LIMIT SWITCH] M2 OPEN limit reached - position set to {self.motor2_run_time:.2f}s")

        # Check Motor 2 CLOSE limit switch
        if self.motor2_use_limit_switches and self.shared.get('close_limit_m2_active', False):
            if self.shared['movement_command'] == 'CLOSE' and self.shared['m2_move_start']:
                # Limit switch triggered - stop motor and set position
                if learning_mode:
                    # Record learned run time for M2 closing
                    if self.shared.get('learning_m2_start_time'):
                        learned_time = now - self.shared['learning_m2_start_time']
                        self.shared['learning_m2_close_time'] = learned_time
                        print(f"[LEARNING] M2 close time recorded: {learned_time:.2f}s")
                        self.shared['learning_m2_start_time'] = None

                # Stop motor and set to fully closed position
                self.motor2.stop()
                self.shared['m2_position'] = 0.0
                self.shared['m2_speed'] = 0.0
                print(f"[LIMIT SWITCH] M2 CLOSE limit reached - position set to 0.0s")

        # Start learning timers when movement begins
        if learning_mode:
            # Motor 1 learning
            if self.motor1_use_limit_switches and self.shared['m1_move_start']:
                if not self.shared.get('learning_m1_start_time'):
                    self.shared['learning_m1_start_time'] = now
                    print(f"[LEARNING] M1 learning timer started")

            # Motor 2 learning
            if self.motor2_use_limit_switches and self.shared['m2_move_start']:
                if not self.shared.get('learning_m2_start_time'):
                    self.shared['learning_m2_start_time'] = now
                    print(f"[LEARNING] M2 learning timer started")

    def _process_deadman_controls(self, now):
        """Handle deadman controls - direct motor operation"""
        if self.shared['deadman_open_active'] and self.shared['deadman_close_active']:
            return False
        
        if self.shared['deadman_open_active']:
            # Use each motor's actual run time (learned if available, else configured)
            if self.shared['m1_position'] < self.motor1_run_time or self.shared['m2_position'] < self.motor2_run_time:
                self.motor1.forward(self.deadman_speed)
                self.motor2.forward(self.deadman_speed)
                self.shared['m1_position'] = min(self.motor1_run_time, self.shared['m1_position'] + 0.05 * self.deadman_speed)
                self.shared['m2_position'] = min(self.motor2_run_time, self.shared['m2_position'] + 0.05 * self.deadman_speed)
            else:
                self.motor1.stop()
                self.motor2.stop()
                self.shared['state'] = 'OPEN'
            return True
        
        elif self.shared['deadman_close_active']:
            if self.shared['m1_position'] > 0 or self.shared['m2_position'] > 0:
                self.motor1.backward(self.deadman_speed)
                self.motor2.backward(self.deadman_speed)
                self.shared['m1_position'] = max(0, self.shared['m1_position'] - 0.05 * self.deadman_speed)
                self.shared['m2_position'] = max(0, self.shared['m2_position'] - 0.05 * self.deadman_speed)
            else:
                self.motor1.stop()
                self.motor2.stop()
                self.shared['state'] = 'CLOSED'
            return True
        
        return False
    
    def _update_motor_positions(self, now):
        """Update motor positions based on actual motor speed over time"""
        ramp_time = self.ramp_time
        
        if self.shared['movement_command'] == 'OPEN':
            # Motor 1 position update
            if self.shared['m1_move_start']:
                elapsed = now - self.shared['m1_move_start']
                
                # Determine target position based on state
                if self.shared['state'] == 'OPENING_TO_PARTIAL_1':
                    target_position = self.partial_1_position
                elif self.shared['state'] == 'OPENING_TO_PARTIAL_2':
                    target_position = self.partial_2_position
                else:
                    # Use M1's actual run time (learned if available, else configured)
                    target_position = self.motor1_run_time

                # DEBUG: Log partial position movements
                if self.shared['state'] in ['OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                    if not hasattr(self, '_last_partial_open_debug') or (now - self._last_partial_open_debug) > 0.5:
                        print(f"[PARTIAL DEBUG OPEN] M1: pos={self.shared['m1_position']:.2f}s target={target_position:.2f}s motor1_run_time={self.motor1_run_time:.2f}s")
                        self._last_partial_open_debug = now

                # Only update if not yet at target
                if self.shared['m1_position'] < target_position:
                    # Calculate remaining distance
                    remaining = target_position - self.shared['m1_position']
                    remaining = max(0, remaining)

                    # Calculate current speed using same ramping logic
                    speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                    speed = max(0.0, min(1.0, speed))

                    # Apply speed multiplier (learning mode or user-configured open speed)
                    if self.shared.get('learning_mode_enabled', False):
                        speed_multiplier = self.learning_speed
                    else:
                        speed_multiplier = self.open_speed

                    # Update position: position += (elapsed_time * current_speed * speed_multiplier)
                    # Using 0.05s as the loop interval (20Hz)
                    self.shared['m1_position'] = min(target_position, self.shared['m1_position'] + (0.05 * speed * speed_multiplier))
            
            # Motor 2 position update
            if self.shared['m2_move_start']:
                # Only update if not yet at target (use M2's actual run time)
                if self.shared['m2_position'] < self.motor2_run_time:
                    elapsed = now - self.shared['m2_move_start']
                    remaining = self.motor2_run_time - self.shared['m2_position']
                    remaining = max(0, remaining)

                    # Calculate current speed
                    speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                    speed = max(0.0, min(1.0, speed))

                    # Apply speed multiplier (learning mode or user-configured open speed)
                    if self.shared.get('learning_mode_enabled', False):
                        speed_multiplier = self.learning_speed
                    else:
                        speed_multiplier = self.open_speed

                    # Update position: position += (elapsed_time * current_speed * speed_multiplier)
                    self.shared['m2_position'] = min(self.motor2_run_time, self.shared['m2_position'] + (0.05 * speed * speed_multiplier))
            elif (self.shared['m1_move_start'] and 
                  (now - self.shared['movement_start_time']) >= self.motor1_open_delay and
                  self.shared['state'] not in ['OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']):
                self.shared['m2_move_start'] = now
                self.shared['m2_target'] = self.shared['m2_position']
        
        elif self.shared['movement_command'] == 'CLOSE':
            # Motor 2 position update (closes first)
            if self.shared['m2_move_start']:
                # Only update if not yet at target
                if self.shared['m2_position'] > 0:
                    elapsed = now - self.shared['m2_move_start']
                    remaining = self.shared['m2_position']
                    remaining = max(0, remaining)

                    # Calculate current speed
                    speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                    speed = max(0.0, min(1.0, speed))

                    # Apply speed multiplier (learning mode or user-configured close speed)
                    if self.shared.get('learning_mode_enabled', False):
                        speed_multiplier = self.learning_speed
                    else:
                        speed_multiplier = self.close_speed

                    # Update position: position -= (elapsed_time * current_speed * speed_multiplier)
                    self.shared['m2_position'] = max(0, self.shared['m2_position'] - (0.05 * speed * speed_multiplier))
            
            # Motor 1 position update
            if self.shared['m1_move_start']:
                # Determine target position based on state
                if self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                    target_position = self.partial_1_position
                elif self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                    target_position = self.partial_2_position
                else:
                    target_position = 0

                # DEBUG: Log partial position movements
                if self.shared['state'] in ['CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                    if not hasattr(self, '_last_partial_debug') or (now - self._last_partial_debug) > 0.5:
                        print(f"[PARTIAL DEBUG] M1: pos={self.shared['m1_position']:.2f}s target={target_position:.2f}s motor1_run_time={self.motor1_run_time:.2f}s")
                        self._last_partial_debug = now

                # Only update if not yet at target
                if self.shared['m1_position'] > target_position:
                    elapsed = now - self.shared['m1_move_start']

                    # Calculate remaining distance
                    remaining = self.shared['m1_position'] - target_position
                    remaining = max(0, remaining)

                    # Calculate current speed
                    speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                    speed = max(0.0, min(1.0, speed))

                    # Apply speed multiplier (learning mode or user-configured close speed)
                    if self.shared.get('learning_mode_enabled', False):
                        speed_multiplier = self.learning_speed
                    else:
                        speed_multiplier = self.close_speed

                    # Update position: position -= (elapsed_time * current_speed * speed_multiplier)
                    self.shared['m1_position'] = max(target_position, self.shared['m1_position'] - (0.05 * speed * speed_multiplier))
            elif (self.shared['m2_move_start'] and
                  (now - self.shared['movement_start_time']) >= (0 if not self.motor2_enabled else self.motor2_close_delay)):
                # Start M1 after delay for ALL closing operations (including partial)
                # Skip delay if motor2 is disabled
                # Only exclude if we're moving FROM a partial position (not returning from OPEN)
                if not (self.shared['state'] in ['CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2'] and
                        not self.shared.get('returning_from_full_open', False)):
                    self.shared['m1_move_start'] = now
                    self.shared['m1_target'] = self.shared['m1_position']
    
    def _update_motor_speeds(self, now):
        """Set motor speeds based on position and ramping"""
        # Handle safety reversal - full speed reverse
        if self.shared['safety_reversing']:
            if self.shared['state'] == 'REVERSING_FROM_CLOSE':
                # Was closing, now reverse (open direction)
                self.motor1.forward(1.0)
                self.motor2.forward(1.0)
                self.shared['m1_speed'] = 1.0  # Full speed (0-1.0 scale)
                self.shared['m2_speed'] = 1.0
            elif self.shared['state'] == 'REVERSING_FROM_OPEN':
                # Was opening, now reverse (close direction)
                self.motor1.backward(1.0)
                self.motor2.backward(1.0)
                self.shared['m1_speed'] = 1.0  # Full speed (0-1.0 scale)
                self.shared['m2_speed'] = 1.0
            return
        
        if not self.shared['movement_start_time'] or self.shared['opening_paused']:
            self.motor1.stop()
            self.motor2.stop()
            self.shared['m1_speed'] = 0.0
            self.shared['m2_speed'] = 0.0
            return
        
        ramp_time = self.ramp_time
        
        if self.shared['opening_paused']:
            self.motor1.stop()
            self.motor2.stop()
            self.shared['m1_speed'] = 0
            self.shared['m2_speed'] = 0
            return
        
        # Motor 1
        if self.shared['m1_move_start']:
            elapsed = now - self.shared['m1_move_start']

            # Check if we should ignore position limits for speed calculation
            # When using limit switches, we don't decelerate based on position
            ignore_position_limits = (self.shared.get('learning_mode_enabled', False) and
                                     self.motor1_use_limit_switches) or self.motor1_use_limit_switches

            if ignore_position_limits:
                # When ignoring position limits, only ramp up based on time, no deceleration
                # Use a large remaining value to prevent deceleration in _calculate_ramp_speed
                remaining = 999.0  # Large value ensures no deceleration
                speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                speed = max(0.0, min(1.0, speed))
            else:
                # Normal position-based speed calculation
                if self.shared['state'] == 'OPENING_TO_PARTIAL_1':
                    remaining = self.partial_1_position - self.shared['m1_position']
                elif self.shared['state'] == 'OPENING_TO_PARTIAL_2':
                    remaining = self.partial_2_position - self.shared['m1_position']
                elif self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                    remaining = self.shared['m1_position'] - self.partial_1_position
                elif self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                    remaining = self.shared['m1_position'] - self.partial_2_position
                else:
                    remaining = self.motor1_run_time - self.shared['m1_position'] if self.shared['movement_command'] == 'OPEN' else self.shared['m1_position']

                remaining = max(0, remaining)
                speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                speed = max(0.0, min(1.0, speed))

            # Apply learning speed if in learning mode
            if self.shared.get('learning_mode_enabled', False):
                speed = min(speed, self.learning_speed)
            else:
                # Apply user-configurable speed and gradual slowdown for limit switches
                if self.shared['movement_command'] == 'OPEN':
                    # Apply user's open speed
                    max_speed = self.open_speed
                    speed = speed * max_speed

                    # Apply gradual slowdown ONLY when approaching OPEN limit (not partial positions)
                    if (self.motor1_use_limit_switches and self.motor1_run_time and
                        self.shared['state'] not in ['OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']):
                        remaining_distance = self.motor1_run_time - self.shared['m1_position']
                        speed = self._apply_gradual_slowdown(speed, remaining_distance, max_speed, True)

                elif self.shared['movement_command'] == 'CLOSE':
                    # Apply user's close speed
                    max_speed = self.close_speed
                    speed = speed * max_speed

                    # Apply gradual slowdown ONLY when approaching CLOSE limit (not partial positions)
                    if (self.motor1_use_limit_switches and self.motor1_run_time and
                        self.shared['state'] not in ['CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']):
                        remaining_distance = self.shared['m1_position']
                        speed = self._apply_gradual_slowdown(speed, remaining_distance, max_speed, True)

            self.shared['m1_speed'] = speed

            # Check if we should ignore position limits and keep running until limit switch
            # This applies in two cases:
            # 1. Learning mode with limit switches enabled
            # 2. Normal mode with limit switches enabled (must creep to find limits!)
            ignore_position_limits = (self.shared.get('learning_mode_enabled', False) and
                                     self.motor1_use_limit_switches) or self.motor1_use_limit_switches

            if self.shared['state'] in ['OPENING', 'OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                # Use M1's actual run time (learned if available, else configured)
                target_position = self.motor1_run_time
                if self.shared['state'] == 'OPENING_TO_PARTIAL_1':
                    target_position = self.partial_1_position
                elif self.shared['state'] == 'OPENING_TO_PARTIAL_2':
                    target_position = self.partial_2_position

                # When limit switches enabled, keep running until limit triggers (with safety margin)
                # Fault detection prevents infinite running if limit switch fails
                if ignore_position_limits:
                    # Perform fault checks
                    open_limit_m1 = self.shared.get('open_limit_m1_active', False)
                    close_limit_m1 = self.shared.get('close_limit_m1_active', False)

                    # Check for over-travel (120% threshold)
                    if self._check_over_travel(1, self.shared['m1_position'], target_position, "OPENING"):
                        self.motor1.stop()
                    # Check limit release at 50% travel
                    elif self._check_limit_release(1, self.shared['m1_position'], target_position, "OPENING", close_limit_m1):
                        self.motor1.forward(speed)  # Continue but fault is logged
                    # Check limit activation at expected position
                    elif self._check_limit_activation(1, self.shared['m1_position'], target_position, "OPENING",
                                                      open_limit_m1, close_limit_m1, close_limit_m1, open_limit_m1):
                        self.motor1.forward(speed)  # Continue but fault is logged
                    # Normal operation - keep running until limit hits
                    elif not open_limit_m1:
                        self.motor1.forward(speed)
                    else:
                        # Successfully hit limit
                        self.motor1.stop()
                else:
                    # Normal position-based stopping
                    # Use small tolerance to avoid floating point precision issues
                    position_tolerance = 0.05  # One control loop cycle
                    if self.shared['m1_position'] < target_position - position_tolerance:
                        self.motor1.forward(speed)
                    else:
                        self.motor1.stop()
                        # Snap to exact target when stopped
                        if abs(self.shared['m1_position'] - target_position) > 0.01:
                            print(f"[MOTOR MGR] Snapping M1: {self.shared['m1_position']:.10f} -> {target_position}")
                        self.shared['m1_position'] = target_position
            else:
                target_position = 0
                if self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                    target_position = self.partial_1_position
                elif self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                    target_position = self.partial_2_position

                # Partial positions don't have limit switches - always use position-based stopping
                # Only ignore position limits when closing to FULL close (state = 'CLOSING')
                use_limit_switch_mode = (ignore_position_limits and
                                        self.shared['state'] == 'CLOSING')

                # DEBUG: Show motor control decisions for M1 closing
                if self.shared['movement_command'] == 'CLOSE':
                    print(f"[M1 MOTOR] State={self.shared['state']} Pos={self.shared['m1_position']:.1f} Target={target_position:.1f} LimitMode={use_limit_switch_mode} IgnoreLimits={ignore_position_limits}")

                # When limit switches enabled, keep running until limit triggers (with fault detection)
                if use_limit_switch_mode:
                    # Perform fault checks
                    open_limit_m1 = self.shared.get('open_limit_m1_active', False)
                    close_limit_m1 = self.shared.get('close_limit_m1_active', False)

                    # For closing, position goes from motor1_run_time down to 0
                    # So over-travel means position going significantly below 0
                    # Check using absolute position value
                    if self.shared['m1_position'] < -0.5:  # More than 0.5s below zero is over-travel
                        self._record_fault(1, "OVER_TRAVEL", f"CLOSING - position {self.shared['m1_position']:.2f}s below zero")
                        self.motor1.stop()
                    # Check limit release - at 50% travel from open, open limit should be off
                    elif self._check_limit_release(1, self.motor1_run_time - self.shared['m1_position'],
                                                   self.motor1_run_time, "CLOSING", open_limit_m1):
                        self.motor1.backward(speed)  # Continue but fault is logged
                    # Check limit activation at expected position
                    elif self.shared['m1_position'] <= 0.1 and not close_limit_m1:
                        # Near zero but close limit not active
                        if open_limit_m1:
                            self._record_fault(1, "LIMIT_MISSING", "CLOSING - close limit not activated, open still active")
                        else:
                            self._record_fault(1, "LIMIT_MISSING", "CLOSING - close limit not activated at position 0")
                        self.motor1.backward(speed)  # Continue but fault is logged
                    # Normal operation - keep running until limit hits
                    elif not close_limit_m1:
                        self.motor1.backward(speed)
                    else:
                        # Successfully hit limit
                        self._clear_fault(1)
                        self.motor1.stop()
                else:
                    # Normal position-based stopping
                    # Use small tolerance to avoid floating point precision issues
                    position_tolerance = 0.05  # One control loop cycle
                    if self.shared['m1_position'] > target_position + position_tolerance:
                        self.motor1.backward(speed)
                        if self.shared['movement_command'] == 'CLOSE':
                            print(f"[M1 MOTOR] Running: Pos {self.shared['m1_position']:.2f} > Target {target_position:.2f} (+{position_tolerance})")
                    else:
                        self.motor1.stop()
                        if self.shared['movement_command'] == 'CLOSE':
                            print(f"[M1 MOTOR] STOPPED: Pos {self.shared['m1_position']:.2f} <= Target {target_position:.2f} (+{position_tolerance})")
                        # Snap to exact target when stopped
                        self.shared['m1_position'] = target_position
        else:
            # No move command - ensure motor is stopped
            self.motor1.stop()
            self.shared['m1_speed'] = 0.0
        
        # Motor 2 (skip if disabled)
        if self.motor2_enabled and self.shared['m2_move_start']:
            elapsed = now - self.shared['m2_move_start']

            # Check if we should ignore position limits for speed calculation
            # When using limit switches, we don't decelerate based on position
            ignore_position_limits_m2 = (self.shared.get('learning_mode_enabled', False) and
                                        self.motor2_use_limit_switches) or self.motor2_use_limit_switches

            if ignore_position_limits_m2:
                # When ignoring position limits, only ramp up based on time, no deceleration
                # Use a large remaining value to prevent deceleration in _calculate_ramp_speed
                remaining = 999.0  # Large value ensures no deceleration
                speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                speed = max(0.0, min(1.0, speed))
            else:
                # Normal position-based speed calculation
                remaining = self.motor2_run_time - self.shared['m2_position'] if self.shared['movement_command'] == 'OPEN' else self.shared['m2_position']
                remaining = max(0, remaining)

                speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                speed = max(0.0, min(1.0, speed))

            # Apply learning speed if in learning mode
            if self.shared.get('learning_mode_enabled', False):
                speed = min(speed, self.learning_speed)
            else:
                # Apply user-configurable speed and gradual slowdown for limit switches
                if self.shared['movement_command'] == 'OPEN':
                    # Apply user's open speed
                    max_speed = self.open_speed
                    speed = speed * max_speed

                    # Apply gradual slowdown when approaching open limit (M2 has no partial positions)
                    if self.motor2_use_limit_switches and self.motor2_run_time:
                        remaining_distance = self.motor2_run_time - self.shared['m2_position']
                        speed = self._apply_gradual_slowdown(speed, remaining_distance, max_speed, True)

                elif self.shared['movement_command'] == 'CLOSE':
                    # Apply user's close speed
                    max_speed = self.close_speed
                    speed = speed * max_speed

                    # Apply gradual slowdown when approaching close limit (M2 has no partial positions)
                    if self.motor2_use_limit_switches and self.motor2_run_time:
                        remaining_distance = self.shared['m2_position']
                        speed = self._apply_gradual_slowdown(speed, remaining_distance, max_speed, True)

            self.shared['m2_speed'] = speed

            if self.shared['movement_command'] == 'OPEN':
                # When limit switches enabled, keep running until limit triggers (with fault detection)
                if ignore_position_limits_m2:
                    # Perform fault checks
                    open_limit_m2 = self.shared.get('open_limit_m2_active', False)
                    close_limit_m2 = self.shared.get('close_limit_m2_active', False)

                    # Check for over-travel (120% threshold)
                    if self._check_over_travel(2, self.shared['m2_position'], self.motor2_run_time, "OPENING"):
                        self.motor2.stop()
                    # Check limit release at 50% travel
                    elif self._check_limit_release(2, self.shared['m2_position'], self.motor2_run_time, "OPENING", close_limit_m2):
                        self.motor2.forward(speed)  # Continue but fault is logged
                    # Check limit activation at expected position
                    elif self._check_limit_activation(2, self.shared['m2_position'], self.motor2_run_time, "OPENING",
                                                      open_limit_m2, close_limit_m2, close_limit_m2, open_limit_m2):
                        self.motor2.forward(speed)  # Continue but fault is logged
                    # Normal operation - keep running until limit hits
                    elif not open_limit_m2:
                        self.motor2.forward(speed)
                    else:
                        # Successfully hit limit
                        self.motor2.stop()
                else:
                    # Normal position-based stopping (use M2's actual run time)
                    # Use small tolerance to avoid floating point precision issues
                    position_tolerance = 0.05  # One control loop cycle
                    if self.shared['m2_position'] < self.motor2_run_time - position_tolerance:
                        self.motor2.forward(speed)
                    else:
                        self.motor2.stop()
                        # Snap to exact target when stopped
                        if abs(self.shared['m2_position'] - self.motor2_run_time) > 0.01:
                            print(f"[MOTOR MGR] Snapping M2: {self.shared['m2_position']:.10f} -> {self.motor2_run_time}")
                        self.shared['m2_position'] = self.motor2_run_time
            else:
                # When limit switches enabled, keep running until limit triggers (with fault detection)
                if ignore_position_limits_m2:
                    # Perform fault checks
                    open_limit_m2 = self.shared.get('open_limit_m2_active', False)
                    close_limit_m2 = self.shared.get('close_limit_m2_active', False)

                    # For closing, position goes from motor2_run_time down to 0
                    # Check for over-travel (significantly below zero)
                    if self.shared['m2_position'] < -0.5:  # More than 0.5s below zero is over-travel
                        self._record_fault(2, "OVER_TRAVEL", f"CLOSING - position {self.shared['m2_position']:.2f}s below zero")
                        self.motor2.stop()
                    # Check limit release - at 50% travel from open, open limit should be off
                    elif self._check_limit_release(2, self.motor2_run_time - self.shared['m2_position'],
                                                   self.motor2_run_time, "CLOSING", open_limit_m2):
                        self.motor2.backward(speed)  # Continue but fault is logged
                    # Check limit activation at expected position
                    elif self.shared['m2_position'] <= 0.1 and not close_limit_m2:
                        # Near zero but close limit not active
                        if open_limit_m2:
                            self._record_fault(2, "LIMIT_MISSING", "CLOSING - close limit not activated, open still active")
                        else:
                            self._record_fault(2, "LIMIT_MISSING", "CLOSING - close limit not activated at position 0")
                        self.motor2.backward(speed)  # Continue but fault is logged
                    # Normal operation - keep running until limit hits
                    elif not close_limit_m2:
                        self.motor2.backward(speed)
                    else:
                        # Successfully hit limit
                        self._clear_fault(2)
                        self.motor2.stop()
                else:
                    # Normal position-based stopping
                    # Use small tolerance to avoid floating point precision issues
                    position_tolerance = 0.05  # One control loop cycle
                    if self.shared['m2_position'] > position_tolerance:
                        self.motor2.backward(speed)
                    else:
                        self.motor2.stop()
                        # Snap to exact target when stopped
                        self.shared['m2_position'] = 0
        elif self.motor2_enabled:
            # No move command - ensure motor is stopped
            self.motor2.stop()
            self.shared['m2_speed'] = 0.0

        # If motor2 disabled, ensure it's always stopped
        if not self.motor2_enabled:
            self.motor2.stop()
            self.shared['m2_speed'] = 0.0
            self.shared['m2_position'] = 0.0
    
    def _calculate_ramp_speed(self, elapsed, remaining, ramp_time):
        """Calculate speed with acceleration and deceleration"""
        if self.shared['resume_time'] and (time() - self.shared['resume_time']) < 0.5:
            time_since_resume = time() - self.shared['resume_time']
            return max(0.0, min(1.0, time_since_resume / 0.5))

        if elapsed < ramp_time:
            return min(1.0, elapsed / ramp_time)
        elif remaining < ramp_time:
            return max(0.0, min(1.0, remaining / ramp_time))
        else:
            return 1.0

    def _apply_gradual_slowdown(self, speed, remaining_distance, max_speed, use_limit_switches):
        """
        Apply gradual slowdown when approaching limit switches.

        Instead of abrupt switch to creep speed, this creates a smooth deceleration
        zone that transitions from max_speed down to creep_speed over slowdown_distance.

        The slowdown_distance is in POSITION units (seconds at full speed), NOT real time.
        At slower speeds, the slowdown takes proportionally longer in real time, which is correct.

        Args:
            speed: Current calculated speed from ramp
            remaining_distance: Distance to target in seconds (position-based time)
            max_speed: Maximum speed for this movement (open_speed or close_speed)
            use_limit_switches: Whether limit switches are enabled for this motor

        Returns:
            Adjusted speed with gradual slowdown applied
        """
        if not use_limit_switches:
            # No limit switches, no special slowdown
            return speed

        if remaining_distance >= self.slowdown_distance:
            # Outside slowdown zone, use normal speed
            return speed

        # Inside slowdown zone - gradual deceleration from max_speed to creep_speed
        # Formula: speed = creep + (max_speed - creep) * (remaining / slowdown_distance)
        # At remaining = slowdown_distance: speed = max_speed
        # At remaining = 0: speed = creep_speed
        speed_range = max_speed - self.limit_switch_creep_speed
        target_speed = self.limit_switch_creep_speed + (speed_range * (remaining_distance / self.slowdown_distance))

        # Use minimum of ramp speed and slowdown target
        # This ensures we don't speed up during slowdown
        return min(speed, target_speed)


def motor_manager_process(shared_dict, config):
    """Entry point for motor manager process"""
    manager = MotorManager(shared_dict, config)
    manager.run()
