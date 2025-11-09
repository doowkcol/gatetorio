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
        self.run_time = config['run_time']
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
        self.motor1_learned_run_time = config.get('motor1_learned_run_time', None)
        self.motor2_learned_run_time = config.get('motor2_learned_run_time', None)
        self.limit_switch_creep_speed = config.get('limit_switch_creep_speed', 0.2)
        self.opening_slowdown_percent = config.get('opening_slowdown_percent', 2.0)
        self.closing_slowdown_percent = config.get('closing_slowdown_percent', 10.0)
        self.learning_speed = config.get('learning_speed', 0.3)

        # Use learned run times if available, otherwise use standard run_time
        self.motor1_run_time = self.motor1_learned_run_time if self.motor1_learned_run_time else self.run_time
        self.motor2_run_time = self.motor2_learned_run_time if self.motor2_learned_run_time else self.run_time
        
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
        
        print("Motor Manager initialized")
    
    def _reload_config(self):
        """Reload config from shared memory"""
        print("Motor Manager: Reloading config from shared memory...")
        self.run_time = self.shared.get('config_run_time', self.run_time)
        self.motor1_open_delay = self.shared.get('config_motor1_open_delay', self.motor1_open_delay)
        self.motor2_close_delay = self.shared.get('config_motor2_close_delay', self.motor2_close_delay)
        self.partial_1_position = self.shared.get('config_partial_1_position', self.partial_1_position)
        self.partial_2_position = self.shared.get('config_partial_2_position', self.partial_2_position)
        self.deadman_speed = self.shared.get('config_deadman_speed', self.deadman_speed)
        self.ramp_time = self.shared.get('config_ramp_time', self.ramp_time)
        self.limit_switches_enabled = self.shared.get('config_limit_switches_enabled', self.limit_switches_enabled)
        self.motor1_use_limit_switches = self.shared.get('config_motor1_use_limit_switches', self.motor1_use_limit_switches)
        self.motor2_use_limit_switches = self.shared.get('config_motor2_use_limit_switches', self.motor2_use_limit_switches)
        self.motor1_learned_run_time = self.shared.get('config_motor1_learned_run_time', self.motor1_learned_run_time)
        self.motor2_learned_run_time = self.shared.get('config_motor2_learned_run_time', self.motor2_learned_run_time)
        self.limit_switch_creep_speed = self.shared.get('config_limit_switch_creep_speed', self.limit_switch_creep_speed)
        self.opening_slowdown_percent = self.shared.get('config_opening_slowdown_percent', self.opening_slowdown_percent)
        self.closing_slowdown_percent = self.shared.get('config_closing_slowdown_percent', self.closing_slowdown_percent)
        self.learning_speed = self.shared.get('config_learning_speed', self.learning_speed)

        # Update individual motor run times
        self.motor1_run_time = self.motor1_learned_run_time if self.motor1_learned_run_time else self.run_time
        self.motor2_run_time = self.motor2_learned_run_time if self.motor2_learned_run_time else self.run_time
        print(f"Motor Manager: Config reloaded - run_time={self.run_time}s, ramp_time={self.ramp_time}s, limit_switches={self.limit_switches_enabled}")
    
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
        """Process auto-learn state machine - progressive learning with slow discovery then full-speed cycles"""
        # Initialize state on first call
        if not self.shared.get('auto_learn_state'):
            self.shared['auto_learn_state'] = 'IDLE'
            self.shared['auto_learn_phase_start'] = now
            self.shared['auto_learn_m1_start'] = None
            self.shared['auto_learn_m2_start'] = None
            self.shared['auto_learn_m1_open_slow'] = None
            self.shared['auto_learn_m2_open_slow'] = None
            self.shared['auto_learn_m1_close_slow'] = None
            self.shared['auto_learn_m2_close_slow'] = None
            self.shared['auto_learn_m1_expected'] = None
            self.shared['auto_learn_m2_expected'] = None
            self.shared['auto_learn_m1_times'] = []
            self.shared['auto_learn_m2_times'] = []
            self.shared['auto_learn_cycle'] = 0
            self.shared['auto_learn_slowdown_start'] = None

        state = self.shared['auto_learn_state']

        # State: IDLE - Initialize and start M1 opening
        if state == 'IDLE':
            print("\n=== AUTO-LEARN: PHASE 1 - SLOW DISCOVERY ===")
            print("Opening M1 slowly to find open limit...")
            self.shared['auto_learn_state'] = 'M1_OPEN_SLOW'
            self.shared['auto_learn_status_msg'] = 'Phase 1: Opening M1 slowly...'
            self.shared['auto_learn_m1_start'] = now
            self.shared['m1_position'] = 0.0
            self.shared['m2_position'] = 0.0

        # State: M1_OPEN_SLOW - M1 opening slowly, record time
        elif state == 'M1_OPEN_SLOW':
            self.motor1.forward(self.learning_speed)
            self.motor2.stop()

            if self.shared.get('open_limit_m1_active', False):
                learned_time = now - self.shared['auto_learn_m1_start']
                self.shared['auto_learn_m1_open_slow'] = learned_time
                print(f"M1 open limit: {learned_time:.2f}s at {self.learning_speed*100:.0f}% speed")
                self.motor1.stop()

                self.shared['auto_learn_state'] = 'M2_OPEN_SLOW'
                self.shared['auto_learn_status_msg'] = 'Phase 1: Opening M2 slowly...'
                self.shared['auto_learn_m2_start'] = now
                print("Opening M2 slowly to find open limit...")

        # State: M2_OPEN_SLOW - M2 opening slowly, record time
        elif state == 'M2_OPEN_SLOW':
            self.motor1.stop()
            self.motor2.forward(self.learning_speed)

            if self.shared.get('open_limit_m2_active', False):
                learned_time = now - self.shared['auto_learn_m2_start']
                self.shared['auto_learn_m2_open_slow'] = learned_time
                print(f"M2 open limit: {learned_time:.2f}s at {self.learning_speed*100:.0f}% speed")
                self.motor2.stop()

                self.shared['auto_learn_state'] = 'PAUSE_BEFORE_M2_CLOSE'
                self.shared['auto_learn_status_msg'] = 'Pausing...'
                self.shared['auto_learn_phase_start'] = now
                print("Pausing before M2 close...")

        # State: PAUSE_BEFORE_M2_CLOSE
        elif state == 'PAUSE_BEFORE_M2_CLOSE':
            self.motor1.stop()
            self.motor2.stop()

            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                self.shared['auto_learn_state'] = 'M2_CLOSE_SLOW'
                self.shared['auto_learn_status_msg'] = 'Phase 1: Closing M2 slowly...'
                self.shared['auto_learn_m2_start'] = now
                print("Closing M2 slowly to record close time...")

        # State: M2_CLOSE_SLOW - M2 closing slowly, record time
        elif state == 'M2_CLOSE_SLOW':
            self.motor1.stop()
            self.motor2.backward(self.learning_speed)

            if self.shared.get('close_limit_m2_active', False):
                learned_time = now - self.shared['auto_learn_m2_start']
                self.shared['auto_learn_m2_close_slow'] = learned_time
                print(f"M2 close limit: {learned_time:.2f}s at {self.learning_speed*100:.0f}% speed")
                self.motor2.stop()

                self.shared['auto_learn_state'] = 'PAUSE_BEFORE_M1_CLOSE'
                self.shared['auto_learn_status_msg'] = 'Pausing...'
                self.shared['auto_learn_phase_start'] = now
                print("Pausing before M1 close...")

        # State: PAUSE_BEFORE_M1_CLOSE
        elif state == 'PAUSE_BEFORE_M1_CLOSE':
            self.motor1.stop()
            self.motor2.stop()

            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                self.shared['auto_learn_state'] = 'M1_CLOSE_SLOW'
                self.shared['auto_learn_status_msg'] = 'Phase 1: Closing M1 slowly...'
                self.shared['auto_learn_m1_start'] = now
                print("Closing M1 slowly to record close time...")

        # State: M1_CLOSE_SLOW - M1 closing slowly, record time
        elif state == 'M1_CLOSE_SLOW':
            self.motor1.backward(self.learning_speed)
            self.motor2.stop()

            if self.shared.get('close_limit_m1_active', False):
                learned_time = now - self.shared['auto_learn_m1_start']
                self.shared['auto_learn_m1_close_slow'] = learned_time
                print(f"M1 close limit: {learned_time:.2f}s at {self.learning_speed*100:.0f}% speed")
                self.motor1.stop()

                # Move to calculate expected times
                self.shared['auto_learn_state'] = 'CALCULATE_EXPECTED'
                print("\n=== Slow discovery complete ===")

        # State: CALCULATE_EXPECTED - Calculate full-speed estimates
        elif state == 'CALCULATE_EXPECTED':
            self.motor1.stop()
            self.motor2.stop()

            # Calculate expected full-speed times: slow_time * learning_speed
            m1_open = self.shared.get('auto_learn_m1_open_slow')
            m2_open = self.shared.get('auto_learn_m2_open_slow')
            m1_close = self.shared.get('auto_learn_m1_close_slow')
            m2_close = self.shared.get('auto_learn_m2_close_slow')

            if m1_open and m1_close:
                m1_expected = ((m1_open + m1_close) / 2.0) * self.learning_speed
                self.shared['auto_learn_m1_expected'] = m1_expected
                print(f"M1 expected full-speed time: {m1_expected:.2f}s")

            if m2_open and m2_close:
                m2_expected = ((m2_open + m2_close) / 2.0) * self.learning_speed
                self.shared['auto_learn_m2_expected'] = m2_expected
                print(f"M2 expected full-speed time: {m2_expected:.2f}s")

            # Start fast learning cycles
            self.shared['auto_learn_cycle'] = 1
            self.shared['auto_learn_state'] = 'PAUSE_BEFORE_FAST_OPEN'
            self.shared['auto_learn_phase_start'] = now
            self.shared['auto_learn_status_msg'] = 'Preparing fast cycle 1...'
            print("\n=== AUTO-LEARN: PHASE 2 - FULL SPEED CYCLES ===")
            print("Starting fast learning cycles with slowdown...")

        # State: PAUSE_BEFORE_FAST_OPEN
        elif state == 'PAUSE_BEFORE_FAST_OPEN':
            self.motor1.stop()
            self.motor2.stop()

            if now - self.shared['auto_learn_phase_start'] >= 1.0:
                cycle = self.shared['auto_learn_cycle']
                self.shared['auto_learn_state'] = 'FAST_OPEN'
                self.shared['auto_learn_status_msg'] = f'Cycle {cycle}: Opening full speed...'
                self.shared['auto_learn_m1_start'] = now
                self.shared['auto_learn_m2_start'] = now + self.motor1_open_delay
                self.shared['auto_learn_slowdown_start'] = None
                print(f"\nCycle {cycle}: Opening at full speed with {self.opening_slowdown_percent}% slowdown...")

        # State: FAST_OPEN - Full speed opening with slowdown
        elif state == 'FAST_OPEN':
            m1_expected = self.shared.get('auto_learn_m1_expected', 10.0)
            m2_expected = self.shared.get('auto_learn_m2_expected', 10.0)

            # Calculate slowdown points (percentage of expected time)
            m1_slowdown_point = m1_expected * (1.0 - self.opening_slowdown_percent / 100.0)
            m2_slowdown_point = m2_expected * (1.0 - self.opening_slowdown_percent / 100.0)

            # M1 control
            if self.shared['auto_learn_m1_start'] and now >= self.shared['auto_learn_m1_start']:
                m1_elapsed = now - self.shared['auto_learn_m1_start']
                if m1_elapsed < m1_slowdown_point and not self.shared.get('open_limit_m1_active', False):
                    self.motor1.forward(1.0)  # Full speed
                elif not self.shared.get('open_limit_m1_active', False):
                    if not self.shared.get('auto_learn_slowdown_start'):
                        print(f"M1 slowdown at {m1_elapsed:.2f}s (expected {m1_expected:.2f}s)")
                        self.shared['auto_learn_slowdown_start'] = now
                    self.motor1.forward(self.limit_switch_creep_speed)  # Creep speed
                else:
                    if self.shared['auto_learn_m1_start']:
                        total_time = now - self.shared['auto_learn_m1_start']
                        print(f"M1 open limit hit at {total_time:.2f}s")
                        # Store time
                        times = list(self.shared.get('auto_learn_m1_times', []))
                        times.append(total_time)
                        self.shared['auto_learn_m1_times'] = times
                        self.shared['auto_learn_m1_start'] = None
                    self.motor1.stop()
            else:
                self.motor1.stop()

            # M2 control (starts after delay)
            if self.shared['auto_learn_m2_start'] and now >= self.shared['auto_learn_m2_start']:
                m2_elapsed = now - self.shared['auto_learn_m2_start']
                if m2_elapsed < m2_slowdown_point and not self.shared.get('open_limit_m2_active', False):
                    self.motor2.forward(1.0)  # Full speed
                elif not self.shared.get('open_limit_m2_active', False):
                    self.motor2.forward(self.limit_switch_creep_speed)  # Creep speed
                else:
                    if self.shared['auto_learn_m2_start']:
                        total_time = now - self.shared['auto_learn_m2_start']
                        print(f"M2 open limit hit at {total_time:.2f}s")
                        # Store time
                        times = list(self.shared.get('auto_learn_m2_times', []))
                        times.append(total_time)
                        self.shared['auto_learn_m2_times'] = times
                        self.shared['auto_learn_m2_start'] = None
                    self.motor2.stop()
            else:
                self.motor2.stop()

            # When both done, move to close
            if (self.shared.get('open_limit_m1_active', False) and
                self.shared.get('open_limit_m2_active', False) and
                not self.shared['auto_learn_m1_start'] and
                not self.shared['auto_learn_m2_start']):

                self.shared['auto_learn_state'] = 'PAUSE_BEFORE_FAST_CLOSE'
                self.shared['auto_learn_phase_start'] = now
                self.shared['auto_learn_status_msg'] = f'Cycle {self.shared["auto_learn_cycle"]}: Pausing...'
                print("Both motors at open limit, pausing...")

        # State: PAUSE_BEFORE_FAST_CLOSE
        elif state == 'PAUSE_BEFORE_FAST_CLOSE':
            self.motor1.stop()
            self.motor2.stop()

            if now - self.shared['auto_learn_phase_start'] >= 0.5:
                cycle = self.shared['auto_learn_cycle']
                self.shared['auto_learn_state'] = 'FAST_CLOSE'
                self.shared['auto_learn_status_msg'] = f'Cycle {cycle}: Closing full speed...'
                self.shared['auto_learn_m2_start'] = now
                self.shared['auto_learn_m1_start'] = now + self.motor2_close_delay
                self.shared['auto_learn_slowdown_start'] = None
                print(f"Cycle {cycle}: Closing at full speed with {self.closing_slowdown_percent}% slowdown...")

        # State: FAST_CLOSE - Full speed closing with slowdown
        elif state == 'FAST_CLOSE':
            m1_expected = self.shared.get('auto_learn_m1_expected', 10.0)
            m2_expected = self.shared.get('auto_learn_m2_expected', 10.0)

            # Calculate slowdown points
            m1_slowdown_point = m1_expected * (1.0 - self.closing_slowdown_percent / 100.0)
            m2_slowdown_point = m2_expected * (1.0 - self.closing_slowdown_percent / 100.0)

            # M2 control (closes first)
            if self.shared['auto_learn_m2_start'] and now >= self.shared['auto_learn_m2_start']:
                m2_elapsed = now - self.shared['auto_learn_m2_start']
                if m2_elapsed < m2_slowdown_point and not self.shared.get('close_limit_m2_active', False):
                    self.motor2.backward(1.0)  # Full speed
                elif not self.shared.get('close_limit_m2_active', False):
                    self.motor2.backward(self.limit_switch_creep_speed)  # Creep speed
                else:
                    if self.shared['auto_learn_m2_start']:
                        total_time = now - self.shared['auto_learn_m2_start']
                        print(f"M2 close limit hit at {total_time:.2f}s")
                        # Store time
                        times = list(self.shared.get('auto_learn_m2_times', []))
                        times.append(total_time)
                        self.shared['auto_learn_m2_times'] = times
                        self.shared['auto_learn_m2_start'] = None
                    self.motor2.stop()
            else:
                self.motor2.stop()

            # M1 control (starts after delay)
            if self.shared['auto_learn_m1_start'] and now >= self.shared['auto_learn_m1_start']:
                m1_elapsed = now - self.shared['auto_learn_m1_start']
                if m1_elapsed < m1_slowdown_point and not self.shared.get('close_limit_m1_active', False):
                    self.motor1.backward(1.0)  # Full speed
                elif not self.shared.get('close_limit_m1_active', False):
                    self.motor1.backward(self.limit_switch_creep_speed)  # Creep speed
                else:
                    if self.shared['auto_learn_m1_start']:
                        total_time = now - self.shared['auto_learn_m1_start']
                        print(f"M1 close limit hit at {total_time:.2f}s")
                        # Store time
                        times = list(self.shared.get('auto_learn_m1_times', []))
                        times.append(total_time)
                        self.shared['auto_learn_m1_times'] = times
                        self.shared['auto_learn_m1_start'] = None
                    self.motor1.stop()
            else:
                self.motor1.stop()

            # When both done, check if need more cycles
            if (self.shared.get('close_limit_m1_active', False) and
                self.shared.get('close_limit_m2_active', False) and
                not self.shared['auto_learn_m1_start'] and
                not self.shared['auto_learn_m2_start']):

                cycle = self.shared['auto_learn_cycle']
                print(f"Cycle {cycle} complete")

                if cycle < 2:  # Do 2 full-speed cycles
                    self.shared['auto_learn_cycle'] = cycle + 1
                    self.shared['auto_learn_state'] = 'PAUSE_BEFORE_FAST_OPEN'
                    self.shared['auto_learn_phase_start'] = now
                    print(f"Preparing for cycle {cycle + 1}...")
                else:
                    # All cycles done
                    self.shared['auto_learn_state'] = 'COMPLETE'
                    print("\n=== All cycles complete ===")

        # State: COMPLETE - Calculate final averages
        elif state == 'COMPLETE':
            self.motor1.stop()
            self.motor2.stop()

            m1_times = list(self.shared.get('auto_learn_m1_times', []))
            m2_times = list(self.shared.get('auto_learn_m2_times', []))

            print("\n=== AUTO-LEARN COMPLETE ===")
            print(f"M1 times recorded: {m1_times}")
            print(f"M2 times recorded: {m2_times}")

            if m1_times:
                m1_avg = sum(m1_times) / len(m1_times)
                self.shared['learning_m1_close_time'] = m1_avg
                self.shared['learning_m1_open_time'] = m1_avg
                print(f"M1 average time: {m1_avg:.2f}s")

            if m2_times:
                m2_avg = sum(m2_times) / len(m2_times)
                self.shared['learning_m2_close_time'] = m2_avg
                self.shared['learning_m2_open_time'] = m2_avg
                print(f"M2 average time: {m2_avg:.2f}s")

            # Clear flags
            self.shared['auto_learn_active'] = False
            self.shared['auto_learn_state'] = 'IDLE'
            self.shared['auto_learn_status_msg'] = 'Complete! Save times and exit engineer mode.'
            self.shared['m1_position'] = 0.0
            self.shared['m2_position'] = 0.0

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
                self.shared['m1_position'] = self.motor1_run_time
                self.shared['m1_speed'] = 0.0
                print(f"[LIMIT SWITCH] M1 OPEN limit reached - position set to {self.motor1_run_time:.2f}s")

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
            if self.shared['m1_position'] < self.run_time or self.shared['m2_position'] < self.run_time:
                self.motor1.forward(self.deadman_speed)
                self.motor2.forward(self.deadman_speed)
                self.shared['m1_position'] = min(self.run_time, self.shared['m1_position'] + 0.05 * self.deadman_speed)
                self.shared['m2_position'] = min(self.run_time, self.shared['m2_position'] + 0.05 * self.deadman_speed)
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
                    target_position = self.run_time
                
                # Only update if not yet at target
                if self.shared['m1_position'] < target_position:
                    # Calculate remaining distance
                    remaining = target_position - self.shared['m1_position']
                    remaining = max(0, remaining)
                    
                    # Calculate current speed using same ramping logic
                    speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                    speed = max(0.0, min(1.0, speed))
                    
                    # Update position: position += (elapsed_time * current_speed)
                    # Using 0.05s as the loop interval (20Hz)
                    self.shared['m1_position'] = min(target_position, self.shared['m1_position'] + (0.05 * speed))
            
            # Motor 2 position update
            if self.shared['m2_move_start']:
                # Only update if not yet at target
                if self.shared['m2_position'] < self.run_time:
                    elapsed = now - self.shared['m2_move_start']
                    remaining = self.run_time - self.shared['m2_position']
                    remaining = max(0, remaining)
                    
                    # Calculate current speed
                    speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                    speed = max(0.0, min(1.0, speed))
                    
                    # Update position: position += (elapsed_time * current_speed)
                    self.shared['m2_position'] = min(self.run_time, self.shared['m2_position'] + (0.05 * speed))
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
                    
                    # Update position: position -= (elapsed_time * current_speed)
                    self.shared['m2_position'] = max(0, self.shared['m2_position'] - (0.05 * speed))
            
            # Motor 1 position update
            if self.shared['m1_move_start']:
                # Determine target position based on state
                if self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                    target_position = self.partial_1_position
                elif self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                    target_position = self.partial_2_position
                elif self.shared['partial_2_active'] and self.shared['returning_from_full_open']:
                    target_position = self.partial_2_position
                elif self.shared['partial_1_active'] and self.shared['returning_from_full_open']:
                    target_position = self.partial_1_position
                else:
                    target_position = 0
                
                # Only update if not yet at target
                if self.shared['m1_position'] > target_position:
                    elapsed = now - self.shared['m1_move_start']
                    
                    # Calculate remaining distance
                    remaining = self.shared['m1_position'] - target_position
                    remaining = max(0, remaining)
                    
                    # Calculate current speed
                    speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
                    speed = max(0.0, min(1.0, speed))
                    
                    # Update position: position -= (elapsed_time * current_speed)
                    self.shared['m1_position'] = max(target_position, self.shared['m1_position'] - (0.05 * speed))
            elif (self.shared['m2_move_start'] and 
                  (now - self.shared['movement_start_time']) >= self.motor2_close_delay):
                # Start M1 after delay for ALL closing operations (including partial)
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
            
            if self.shared['state'] == 'OPENING_TO_PARTIAL_1':
                remaining = self.partial_1_position - self.shared['m1_position']
            elif self.shared['state'] == 'OPENING_TO_PARTIAL_2':
                remaining = self.partial_2_position - self.shared['m1_position']
            elif self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                remaining = self.shared['m1_position'] - self.partial_1_position
            elif self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                remaining = self.shared['m1_position'] - self.partial_2_position
            else:
                remaining = self.run_time - self.shared['m1_position'] if self.shared['movement_command'] == 'OPEN' else self.shared['m1_position']
            
            remaining = max(0, remaining)
            speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
            speed = max(0.0, min(1.0, speed))

            # Apply learning speed if in learning mode
            if self.shared.get('learning_mode_enabled', False):
                speed = min(speed, self.learning_speed)
            # Apply creep speed if using limit switches and near expected end of travel
            elif self.motor1_use_limit_switches and self.motor1_learned_run_time:
                if self.shared['movement_command'] == 'OPEN':
                    # Check if we've reached slowdown threshold (remaining % of travel time)
                    remaining_percent = ((self.motor1_learned_run_time - self.shared['m1_position']) / self.motor1_learned_run_time) * 100
                    if remaining_percent <= self.opening_slowdown_percent:
                        # Within slowdown threshold - switch to creep speed
                        speed = min(speed, self.limit_switch_creep_speed)
                elif self.shared['movement_command'] == 'CLOSE':
                    # Check if we've reached slowdown threshold (remaining % of travel time)
                    remaining_percent = (self.shared['m1_position'] / self.motor1_learned_run_time) * 100
                    if remaining_percent <= self.closing_slowdown_percent:
                        # Within slowdown threshold - switch to creep speed
                        speed = min(speed, self.limit_switch_creep_speed)

            self.shared['m1_speed'] = speed

            # Check if we're in learning mode with limit switches - if so, ignore position limits
            learning_with_limits = (self.shared.get('learning_mode_enabled', False) and
                                   self.motor1_use_limit_switches)

            if self.shared['state'] in ['OPENING', 'OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                target_position = self.run_time
                if self.shared['state'] == 'OPENING_TO_PARTIAL_1':
                    target_position = self.partial_1_position
                elif self.shared['state'] == 'OPENING_TO_PARTIAL_2':
                    target_position = self.partial_2_position

                # In learning mode with limit switches, keep running regardless of position
                if learning_with_limits or self.shared['m1_position'] < target_position:
                    self.motor1.forward(speed)
                else:
                    self.motor1.stop()
                    # Snap to exact target when stopped
                    if self.shared['m1_position'] != target_position:
                        print(f"[MOTOR MGR] Snapping M1: {self.shared['m1_position']:.10f} -> {target_position}")
                    self.shared['m1_position'] = target_position
            else:
                target_position = 0
                if self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                    target_position = self.partial_1_position
                elif self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                    target_position = self.partial_2_position
                elif self.shared['partial_2_active'] and self.shared['returning_from_full_open']:
                    target_position = self.partial_2_position
                elif self.shared['partial_1_active'] and self.shared['returning_from_full_open']:
                    target_position = self.partial_1_position

                # In learning mode with limit switches, keep running regardless of position
                if learning_with_limits or self.shared['m1_position'] > target_position:
                    self.motor1.backward(speed)
                else:
                    self.motor1.stop()
                    # Snap to exact target when stopped
                    self.shared['m1_position'] = target_position
        else:
            # No move command - ensure motor is stopped
            self.motor1.stop()
            self.shared['m1_speed'] = 0.0
        
        # Motor 2
        if self.shared['m2_move_start']:
            elapsed = now - self.shared['m2_move_start']
            remaining = self.run_time - self.shared['m2_position'] if self.shared['movement_command'] == 'OPEN' else self.shared['m2_position']
            remaining = max(0, remaining)
            
            speed = self._calculate_ramp_speed(elapsed, remaining, ramp_time)
            speed = max(0.0, min(1.0, speed))

            # Apply learning speed if in learning mode
            if self.shared.get('learning_mode_enabled', False):
                speed = min(speed, self.learning_speed)
            # Apply creep speed if using limit switches and near expected end of travel
            elif self.motor2_use_limit_switches and self.motor2_learned_run_time:
                if self.shared['movement_command'] == 'OPEN':
                    # Check if we've reached slowdown threshold (remaining % of travel time)
                    remaining_percent = ((self.motor2_learned_run_time - self.shared['m2_position']) / self.motor2_learned_run_time) * 100
                    if remaining_percent <= self.opening_slowdown_percent:
                        # Within slowdown threshold - switch to creep speed
                        speed = min(speed, self.limit_switch_creep_speed)
                elif self.shared['movement_command'] == 'CLOSE':
                    # Check if we've reached slowdown threshold (remaining % of travel time)
                    remaining_percent = (self.shared['m2_position'] / self.motor2_learned_run_time) * 100
                    if remaining_percent <= self.closing_slowdown_percent:
                        # Within slowdown threshold - switch to creep speed
                        speed = min(speed, self.limit_switch_creep_speed)

            self.shared['m2_speed'] = speed

            # Check if we're in learning mode with limit switches - if so, ignore position limits
            learning_with_limits_m2 = (self.shared.get('learning_mode_enabled', False) and
                                       self.motor2_use_limit_switches)

            if self.shared['movement_command'] == 'OPEN':
                # In learning mode with limit switches, keep running regardless of position
                if learning_with_limits_m2 or self.shared['m2_position'] < self.run_time:
                    self.motor2.forward(speed)
                else:
                    self.motor2.stop()
                    # Snap to exact target when stopped
                    if self.shared['m2_position'] != self.run_time:
                        print(f"[MOTOR MGR] Snapping M2: {self.shared['m2_position']:.10f} -> {self.run_time}")
                    self.shared['m2_position'] = self.run_time
            else:
                # In learning mode with limit switches, keep running regardless of position
                if learning_with_limits_m2 or self.shared['m2_position'] > 0:
                    self.motor2.backward(speed)
                else:
                    self.motor2.stop()
                    # Snap to exact target when stopped
                    self.shared['m2_position'] = 0
        else:
            # No move command - ensure motor is stopped
            self.motor2.stop()
            self.shared['m2_speed'] = 0.0
    
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


def motor_manager_process(shared_dict, config):
    """Entry point for motor manager process"""
    manager = MotorManager(shared_dict, config)
    manager.run()
