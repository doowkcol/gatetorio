#!/usr/bin/env python3
"""
Gate Controller V2 - Multiprocessing architecture
Step 3: Added input manager process
"""

from time import time, sleep
import json
import threading
import multiprocessing
from motor_manager import motor_manager_process
from input_manager import input_manager_process  # Safe now - no GPIO claim at import

class GateController:
    def __init__(self, config_file='/home/doowkcol/Gatetorio_Code/gate_config.json'):
        # Load config
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Config values
        self.run_time = config['run_time']
        self.motor1_open_delay = config.get('motor1_open_delay', 0)
        self.motor2_close_delay = config.get('motor2_close_delay', 0)
        self.auto_close_enabled = config.get('auto_close_enabled', False)
        self.auto_close_time = config.get('auto_close_time', 10)
        self.safety_reverse_time = config.get('safety_reverse_time', 1.5)
        self.deadman_speed = config.get('deadman_speed', 0.3)
        self.step_logic_mode = config.get('step_logic_mode', 3)
        self.partial_1_percent = config.get('partial_1_percent', 30)
        self.partial_2_percent = config.get('partial_2_percent', 60)
        # Separate auto-close times for each partial position
        self.partial_1_auto_close_time = config.get('partial_1_auto_close_time', 10)
        self.partial_2_auto_close_time = config.get('partial_2_auto_close_time', 10)
        self.partial_return_pause = config.get('partial_return_pause', 2)

        # Limit switch configuration (MUST load learned times BEFORE calculating partial positions)
        self.limit_switches_enabled = config.get('limit_switches_enabled', False)
        self.motor1_use_limit_switches = config.get('motor1_use_limit_switches', False)
        self.motor2_use_limit_switches = config.get('motor2_use_limit_switches', False)
        self.motor1_learned_run_time = config.get('motor1_learned_run_time', None)
        self.motor2_learned_run_time = config.get('motor2_learned_run_time', None)

        # Partial positions should be based on M1's actual run time (learned if available, else configured)
        # This ensures partial percentages are accurate even when M1 has a different learned time
        motor1_effective_time = self.motor1_learned_run_time if self.motor1_learned_run_time else self.run_time
        self.partial_1_position = (self.partial_1_percent / 100.0) * motor1_effective_time
        self.partial_2_position = (self.partial_2_percent / 100.0) * motor1_effective_time
        self.limit_switch_creep_speed = config.get('limit_switch_creep_speed', 0.2)
        self.learning_mode_enabled = config.get('learning_mode_enabled', False)
        self.opening_slowdown_percent = config.get('opening_slowdown_percent', 2.0)
        self.closing_slowdown_percent = config.get('closing_slowdown_percent', 10.0)
        self.slowdown_distance = config.get('slowdown_distance', 2.0)  # Seconds for gradual slowdown
        self.learning_speed = config.get('learning_speed', 0.3)
        self.open_speed = config.get('open_speed', 1.0)  # User-configurable open speed (0.1-1.0)
        self.close_speed = config.get('close_speed', 1.0)  # User-configurable close speed (0.1-1.0)
        # Engineer mode is runtime-only, never persisted - always starts disabled
        self.engineer_mode_enabled = False

        # Create shared memory dict
        self.manager = multiprocessing.Manager()
        self.shared = self.manager.dict()
        
        # Initialize shared state
        self._init_shared_state()
        
        # Prepare config for motor manager
        motor_config = {
            'run_time': self.run_time,
            'motor1_open_delay': self.motor1_open_delay,
            'motor2_close_delay': self.motor2_close_delay,
            'partial_1_position': self.partial_1_position,
            'partial_2_position': self.partial_2_position,
            'deadman_speed': self.deadman_speed,
            'limit_switches_enabled': self.limit_switches_enabled,
            'motor1_use_limit_switches': self.motor1_use_limit_switches,
            'motor2_use_limit_switches': self.motor2_use_limit_switches,
            'motor1_learned_run_time': self.motor1_learned_run_time,
            'motor2_learned_run_time': self.motor2_learned_run_time,
            'limit_switch_creep_speed': self.limit_switch_creep_speed,
            'opening_slowdown_percent': self.opening_slowdown_percent,
            'closing_slowdown_percent': self.closing_slowdown_percent,
            'slowdown_distance': self.slowdown_distance,
            'learning_speed': self.learning_speed,
            'open_speed': self.open_speed,
            'close_speed': self.close_speed
        }
        
        # Start motor manager process
        self.motor_process = multiprocessing.Process(
            target=motor_manager_process,
            args=(self.shared, motor_config),
            daemon=True
        )
        self.motor_process.start()
        
        # Prepare config for input manager
        input_config = {
            'num_inputs': 8,  # Dual ADS1115 = 8 channels
            'input_sample_rate': 0.1  # 10Hz sampling
        }
        
        # Start input manager process
        self.input_process = multiprocessing.Process(
            target=input_manager_process,
            args=(self.shared, input_config),
            daemon=True
        )
        self.input_process.start()
        
        # Start control thread (decision making only)
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()

        print(f"Gate Controller V2 (Step 3 - Three Processes) initialized")
        print(f"  Full travel time: {self.run_time}s")
        print(f"  Motor Manager PID: {self.motor_process.pid}")
        print(f"  Input Manager PID: {self.input_process.pid}")
        print(f"  Auto-close: {'ENABLED' if self.auto_close_enabled else 'DISABLED'} ({self.auto_close_time}s)")

        # Wait briefly for input manager to read limit switches, then detect initial position
        sleep(0.5)
        self._detect_initial_position()
    
    def reload_config(self, config_file='/home/doowkcol/Gatetorio_Code/gate_config.json'):
        """Reload configuration from file - updates runtime parameters
        
        Note: UI should stop gate before calling this to avoid mid-movement issues
        """
        print("Reloading configuration...")
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Update config values
            self.run_time = config['run_time']
            self.motor1_open_delay = config.get('motor1_open_delay', 0)
            self.motor2_close_delay = config.get('motor2_close_delay', 0)
            self.auto_close_enabled = config.get('auto_close_enabled', False)
            self.auto_close_time = config.get('auto_close_time', 10)
            self.safety_reverse_time = config.get('safety_reverse_time', 1.5)
            self.deadman_speed = config.get('deadman_speed', 0.3)
            self.step_logic_mode = config.get('step_logic_mode', 3)
            self.partial_1_percent = config.get('partial_1_percent', 30)
            self.partial_2_percent = config.get('partial_2_percent', 60)
            self.partial_1_auto_close_time = config.get('partial_1_auto_close_time', 10)
            self.partial_2_auto_close_time = config.get('partial_2_auto_close_time', 10)
            self.partial_return_pause = config.get('partial_return_pause', 2)

            # Limit switch configuration (must load learned times BEFORE calculating partial positions)
            self.limit_switches_enabled = config.get('limit_switches_enabled', False)
            self.motor1_use_limit_switches = config.get('motor1_use_limit_switches', False)
            self.motor2_use_limit_switches = config.get('motor2_use_limit_switches', False)
            self.motor1_learned_run_time = config.get('motor1_learned_run_time', None)
            self.motor2_learned_run_time = config.get('motor2_learned_run_time', None)

            # Partial positions should be based on M1's actual run time (learned if available, else configured)
            # This ensures partial percentages are accurate even when M1 has a different learned time
            motor1_effective_time = self.motor1_learned_run_time if self.motor1_learned_run_time else self.run_time
            self.partial_1_position = (self.partial_1_percent / 100.0) * motor1_effective_time
            self.partial_2_position = (self.partial_2_percent / 100.0) * motor1_effective_time
            self.limit_switch_creep_speed = config.get('limit_switch_creep_speed', 0.2)
            self.learning_mode_enabled = config.get('learning_mode_enabled', False)
            self.opening_slowdown_percent = config.get('opening_slowdown_percent', 2.0)
            self.closing_slowdown_percent = config.get('closing_slowdown_percent', 10.0)
            self.slowdown_distance = config.get('slowdown_distance', 2.0)
            self.learning_speed = config.get('learning_speed', 0.3)
            self.open_speed = config.get('open_speed', 1.0)
            self.close_speed = config.get('close_speed', 1.0)
            # Engineer mode is runtime-only, don't change it during reload
            # self.engineer_mode_enabled - keep current runtime value

            # Update motor manager config via shared memory
            self.shared['config_run_time'] = self.run_time
            self.shared['config_motor1_open_delay'] = self.motor1_open_delay
            self.shared['config_motor2_close_delay'] = self.motor2_close_delay
            self.shared['config_partial_1_position'] = self.partial_1_position
            self.shared['config_partial_2_position'] = self.partial_2_position
            self.shared['config_deadman_speed'] = self.deadman_speed
            self.shared['config_limit_switches_enabled'] = self.limit_switches_enabled
            self.shared['config_motor1_use_limit_switches'] = self.motor1_use_limit_switches
            self.shared['config_motor2_use_limit_switches'] = self.motor2_use_limit_switches
            self.shared['config_motor1_learned_run_time'] = self.motor1_learned_run_time
            self.shared['config_motor2_learned_run_time'] = self.motor2_learned_run_time
            self.shared['config_limit_switch_creep_speed'] = self.limit_switch_creep_speed
            self.shared['config_opening_slowdown_percent'] = self.opening_slowdown_percent
            self.shared['config_closing_slowdown_percent'] = self.closing_slowdown_percent
            self.shared['config_slowdown_distance'] = self.slowdown_distance
            self.shared['config_learning_speed'] = self.learning_speed
            self.shared['config_open_speed'] = self.open_speed
            self.shared['config_close_speed'] = self.close_speed
            self.shared['config_reload_flag'] = True  # Signal motor manager to reload
            
            print(f"  Config reloaded successfully")
            print(f"  Run time: {self.run_time}s")
            print(f"  Auto-close: {'ENABLED' if self.auto_close_enabled else 'DISABLED'} ({self.auto_close_time}s)")
            print(f"  PO1: {self.partial_1_percent}%, PO2: {self.partial_2_percent}%")
            
            return True
            
        except Exception as e:
            print(f"Error reloading config: {e}")
            return False
    
    def _init_shared_state(self):
        """Initialize all shared memory variables"""
        self.shared['state'] = 'CLOSED'
        self.shared['m1_position'] = 0.0
        self.shared['m2_position'] = 0.0
        self.shared['m1_speed'] = 0.0
        self.shared['m2_speed'] = 0.0
        self.shared['cmd_open_active'] = False
        self.shared['cmd_close_active'] = False
        self.shared['cmd_stop_active'] = False
        self.shared['step_last_state'] = False
        self.shared['step_command_active'] = False
        self.shared['stopped_after_opening'] = False
        self.shared['stopped_after_closing'] = False
        self.shared['movement_start_time'] = None
        self.shared['movement_command'] = None
        self.shared['m1_move_start'] = None
        self.shared['m2_move_start'] = None
        self.shared['m1_target'] = None
        self.shared['m2_target'] = None
        self.shared['opening_paused'] = False
        self.shared['pause_time'] = None
        self.shared['resume_time'] = None
        self.shared['last_open_position'] = None
        self.shared['photocell_closing_active'] = False
        self.shared['photocell_opening_active'] = False
        self.shared['photocell_closing_triggered'] = False
        self.shared['photocell_opening_triggered'] = False
        self.shared['safety_stop_closing_active'] = False
        self.shared['safety_stop_opening_active'] = False
        self.shared['safety_reversing'] = False
        self.shared['safety_reverse_start'] = None
        self.shared['safety_stop_closing_triggered'] = False
        self.shared['safety_stop_opening_triggered'] = False
        self.shared['safety_stop_closing_reversed'] = False  # Becomes full STOP after reversal
        self.shared['safety_stop_opening_reversed'] = False  # Becomes full STOP after reversal
        self.shared['deadman_open_active'] = False
        self.shared['deadman_close_active'] = False
        self.shared['timed_open_active'] = False
        self.shared['timed_open_triggered'] = False
        self.shared['partial_1_active'] = False
        self.shared['partial_2_active'] = False
        # Separate auto-close tracking for PO1 and PO2
        self.shared['partial_1_auto_close_countdown'] = 0
        self.shared['partial_1_auto_close_active'] = False
        self.shared['partial_2_auto_close_countdown'] = 0
        self.shared['partial_2_auto_close_active'] = False
        self.shared['returning_from_full_open'] = False
        self.shared['closing_from_partial'] = None
        self.shared['auto_close_countdown'] = 0
        self.shared['auto_close_active'] = False
        self.shared['running'] = True
        self.shared['motor_manager_heartbeat'] = time()
        self.shared['controller_heartbeat'] = time()

        # Safety reversal command flags (for motor manager)
        self.shared['execute_safety_reverse'] = False
        self.shared['safety_reverse_direction'] = None  # 'OPEN' or 'CLOSE'
        self.shared['safety_reverse_start_time'] = None

        # Limit switch flags
        self.shared['open_limit_m1_active'] = False
        self.shared['close_limit_m1_active'] = False
        self.shared['open_limit_m2_active'] = False
        self.shared['close_limit_m2_active'] = False

        # Learning mode flags
        self.shared['learning_mode_enabled'] = False
        self.shared['learning_m1_start_time'] = None
        self.shared['learning_m2_start_time'] = None
        self.shared['learning_m1_open_time'] = None
        self.shared['learning_m1_close_time'] = None
        self.shared['learning_m2_open_time'] = None
        self.shared['learning_m2_close_time'] = None
        self.shared['engineer_mode_enabled'] = False

        # Auto-learn state machine
        self.shared['auto_learn_active'] = False
        self.shared['auto_learn_state'] = 'IDLE'
        self.shared['auto_learn_cycle'] = 0
        self.shared['auto_learn_m1_times'] = []
        self.shared['auto_learn_m2_times'] = []
        self.shared['auto_learn_m1_expected'] = None
        self.shared['auto_learn_m2_expected'] = None
        self.shared['auto_learn_phase_start'] = None
        self.shared['auto_learn_status_msg'] = 'Ready'

    def _detect_initial_position(self):
        """Detect initial gate position based on limit switch states at startup"""
        if not self.limit_switches_enabled:
            return  # No limit switches, stick with default CLOSED state

        # Check limit switch states
        m1_open = self.shared.get('open_limit_m1_active', False)
        m2_open = self.shared.get('open_limit_m2_active', False)
        m1_close = self.shared.get('close_limit_m1_active', False)
        m2_close = self.shared.get('close_limit_m2_active', False)

        # Determine initial state based on limit switches
        if m1_open and m2_open:
            # Both motors at open limits
            self.shared['state'] = 'OPEN'
            # Set positions based on learned or configured run times
            if self.motor1_learned_run_time:
                self.shared['m1_position'] = self.motor1_learned_run_time
            else:
                self.shared['m1_position'] = self.run_time

            if self.motor2_learned_run_time:
                self.shared['m2_position'] = self.motor2_learned_run_time
            else:
                self.shared['m2_position'] = self.run_time

            print("[STARTUP] Detected gate at OPEN position (both open limits active)")
        elif m1_close and m2_close:
            # Both motors at close limits (or default)
            self.shared['state'] = 'CLOSED'
            self.shared['m1_position'] = 0.0
            self.shared['m2_position'] = 0.0
            print("[STARTUP] Detected gate at CLOSED position (both close limits active)")
        elif not m1_open and not m2_open and not m1_close and not m2_close:
            # No limits active - assume closed (default)
            self.shared['state'] = 'CLOSED'
            self.shared['m1_position'] = 0.0
            self.shared['m2_position'] = 0.0
            print("[STARTUP] No limits active - defaulting to CLOSED position")
        else:
            # Partial position or inconsistent state - keep default but warn
            print(f"[STARTUP] WARNING: Inconsistent limit switch state detected:")
            print(f"  M1: open={m1_open}, close={m1_close}")
            print(f"  M2: open={m2_open}, close={m2_close}")
            print(f"  Defaulting to CLOSED position")

    def _control_loop(self):
        """Main control loop - decision making only (no motor control)"""
        last_auto_close_update = time()
        last_partial_1_update = time()  # Separate timer for PO1
        last_partial_2_update = time()  # Separate timer for PO2

        while self.shared['running']:
            now = time()

            # Update heartbeat
            self.shared['controller_heartbeat'] = now

            # If auto-learn is active, skip all normal controller logic
            # Motor manager handles everything during auto-learn
            if self.shared.get('auto_learn_active', False):
                sleep(0.05)
                continue

            # STEP 1: Evaluate commands
            self._evaluate_commands(now)

            # STEP 2: Check safety edges
            self._process_safety_edges(now)

            # STEP 3: Check photocell logic
            if not self.shared['safety_reversing']:
                self._process_photocells()

            # STEP 4: Check movement completion
            # Use small tolerance for floating point comparison
            POSITION_TOLERANCE = 0.01  # 0.01 seconds = 10ms tolerance

            if self.shared['movement_command'] == 'OPEN':
                # Debug: Print position check for opening
                if self.shared['state'] == 'OPENING':
                    if self.shared['m1_position'] >= self.run_time - 0.1 or self.shared['m2_position'] >= self.run_time - 0.1:
                        print(f"[COMPLETION CHECK] OPENING: M1={self.shared['m1_position']:.2f}/{self.run_time}, M2={self.shared['m2_position']:.2f}/{self.run_time}, state={self.shared['state']}")
                        print(f"  EXACT VALUES: M1={self.shared['m1_position']!r}, M2={self.shared['m2_position']!r}, run_time={self.run_time!r}")
                        print(f"  Check 3 (FULL): M1>={self.run_time-POSITION_TOLERANCE}={self.shared['m1_position'] >= (self.run_time - POSITION_TOLERANCE)}, M2>={self.run_time-POSITION_TOLERANCE}={self.shared['m2_position'] >= (self.run_time - POSITION_TOLERANCE)}")
                
                if self.shared['state'] == 'OPENING_TO_PARTIAL_1' and self.shared['m1_position'] >= (self.partial_1_position - POSITION_TOLERANCE):
                    self._complete_partial_1()
                elif self.shared['state'] == 'OPENING_TO_PARTIAL_2' and self.shared['m1_position'] >= (self.partial_2_position - POSITION_TOLERANCE):
                    self._complete_partial_2()
                else:
                    # Check for full open - use limit switches if enabled, otherwise use position
                    open_complete = False
                    if self.limit_switches_enabled and (self.motor1_use_limit_switches or self.motor2_use_limit_switches):
                        # With limit switches: check each motor individually
                        m1_limit_check = self.shared.get('open_limit_m1_active', False)
                        m2_limit_check = self.shared.get('open_limit_m2_active', False)

                        # For motors WITH limit switches: wait for limit
                        # For motors WITHOUT limit switches: use position
                        if self.motor1_use_limit_switches:
                            m1_done = m1_limit_check
                            m1_reason = f"limit={m1_limit_check}"
                        else:
                            m1_done = self.shared['m1_position'] >= (self.run_time - POSITION_TOLERANCE)
                            m1_reason = f"pos={self.shared['m1_position']:.2f}>={self.run_time - POSITION_TOLERANCE:.2f}"

                        if self.motor2_use_limit_switches:
                            m2_done = m2_limit_check
                            m2_reason = f"limit={m2_limit_check}"
                        else:
                            m2_done = self.shared['m2_position'] >= (self.run_time - POSITION_TOLERANCE)
                            m2_reason = f"pos={self.shared['m2_position']:.2f}>={self.run_time - POSITION_TOLERANCE:.2f}"

                        open_complete = m1_done and m2_done

                        # Debug: show why we're waiting (only print when close to completion)
                        if not open_complete and (self.shared['m1_position'] >= 11.5 or self.shared['m2_position'] >= 11.5):
                            if not m1_done:
                                print(f"[WAITING] M1 not done: {m1_reason}")
                            if not m2_done:
                                print(f"[WAITING] M2 not done: {m2_reason}")

                        if open_complete:
                            print(f"[COMPLETION] OPEN complete! M1: {m1_reason}, M2: {m2_reason}")
                    else:
                        # Without limit switches: use position
                        open_complete = (self.shared['m1_position'] >= (self.run_time - POSITION_TOLERANCE) and
                                       self.shared['m2_position'] >= (self.run_time - POSITION_TOLERANCE))
                        if open_complete:
                            print(f"[COMPLETION] Position reached - M1={self.shared['m1_position']:.2f}, M2={self.shared['m2_position']:.2f}")

                    if open_complete:
                        self._complete_open()
            elif self.shared['movement_command'] == 'CLOSE':
                # Debug: Print position check for closing
                if self.shared['state'] == 'CLOSING':
                    if self.shared['m1_position'] <= 0.1 or self.shared['m2_position'] <= 0.1:
                        print(f"[COMPLETION CHECK] CLOSING: M1={self.shared['m1_position']:.2f}/0, M2={self.shared['m2_position']:.2f}/0")
                
                if self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                    # Only complete when BOTH M1 at partial AND M2 fully closed
                    if (self.shared['m1_position'] <= (self.partial_1_position + POSITION_TOLERANCE) and 
                        self.shared['m2_position'] <= POSITION_TOLERANCE):
                        self._complete_partial_1()
                elif self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                    # Only complete when BOTH M1 at partial AND M2 fully closed
                    if (self.shared['m1_position'] <= (self.partial_2_position + POSITION_TOLERANCE) and 
                        self.shared['m2_position'] <= POSITION_TOLERANCE):
                        self._complete_partial_2()
                elif self.shared['partial_2_active'] and self.shared['m1_position'] <= (self.partial_2_position + POSITION_TOLERANCE) and self.shared['returning_from_full_open']:
                    if self.shared['m2_position'] <= POSITION_TOLERANCE:
                        self._complete_partial_2()
                elif self.shared['partial_1_active'] and self.shared['m1_position'] <= (self.partial_1_position + POSITION_TOLERANCE) and self.shared['returning_from_full_open']:
                    if self.shared['m2_position'] <= POSITION_TOLERANCE:
                        self._complete_partial_1()
                else:
                    # Check for full close - use limit switches if enabled, otherwise use position
                    close_complete = False
                    if self.limit_switches_enabled and (self.motor1_use_limit_switches or self.motor2_use_limit_switches):
                        # With limit switches: check each motor individually
                        m1_limit_check = self.shared.get('close_limit_m1_active', False)
                        m2_limit_check = self.shared.get('close_limit_m2_active', False)

                        # For motors WITH limit switches: wait for limit
                        # For motors WITHOUT limit switches: use position
                        if self.motor1_use_limit_switches:
                            m1_done = m1_limit_check
                            m1_reason = f"limit={m1_limit_check}"
                        else:
                            m1_done = self.shared['m1_position'] <= POSITION_TOLERANCE
                            m1_reason = f"pos={self.shared['m1_position']:.2f}<={POSITION_TOLERANCE:.2f}"

                        if self.motor2_use_limit_switches:
                            m2_done = m2_limit_check
                            m2_reason = f"limit={m2_limit_check}"
                        else:
                            m2_done = self.shared['m2_position'] <= POSITION_TOLERANCE
                            m2_reason = f"pos={self.shared['m2_position']:.2f}<={POSITION_TOLERANCE:.2f}"

                        close_complete = m1_done and m2_done

                        # Debug: show why we're waiting (only print when close to completion)
                        if not close_complete and (self.shared['m1_position'] <= 0.5 or self.shared['m2_position'] <= 0.5):
                            if not m1_done:
                                print(f"[WAITING] M1 not done: {m1_reason}")
                            if not m2_done:
                                print(f"[WAITING] M2 not done: {m2_reason}")

                        if close_complete:
                            print(f"[COMPLETION] CLOSE complete! M1: {m1_reason}, M2: {m2_reason}")
                    else:
                        # Without limit switches: use position
                        close_complete = (self.shared['m1_position'] <= POSITION_TOLERANCE and
                                        self.shared['m2_position'] <= POSITION_TOLERANCE)
                        if close_complete:
                            print(f"[COMPLETION] Position reached - M1={self.shared['m1_position']:.2f}, M2={self.shared['m2_position']:.2f}")

                    if close_complete:
                        self._complete_close()

            # STEP 5: Auto-close countdown
            if self.shared['auto_close_active'] and (now - last_auto_close_update) >= 1.0:
                self.shared['auto_close_countdown'] -= 1
                last_auto_close_update = now
                if self.shared['auto_close_countdown'] <= 0:
                    print("Auto-close triggered (from full OPEN) - sending momentary CLOSE pulse")
                    # Send momentary pulse (200ms) instead of sustained command
                    self.shared['auto_close_pulse'] = True
                    self.shared['auto_close_pulse_time'] = now
                    self.shared['auto_close_active'] = False
            
            # Clear auto-close pulse after 200ms
            if self.shared.get('auto_close_pulse', False) and (now - self.shared.get('auto_close_pulse_time', 0)) >= 0.2:
                self.shared['auto_close_pulse'] = False
            
            # Partial 1 auto-close countdown (SEPARATE timer)
            if self.shared['partial_1_auto_close_active'] and (now - last_partial_1_update) >= 1.0:
                self.shared['partial_1_auto_close_countdown'] -= 1
                last_partial_1_update = now
                if self.shared['partial_1_auto_close_countdown'] <= 0:
                    print("Partial 1 auto-close triggered - sending momentary CLOSE pulse")
                    self.shared['partial_1_auto_close_active'] = False
                    self.shared['closing_from_partial'] = 'P1'
                    # Send momentary pulse (200ms) instead of sustained command
                    self.shared['partial_1_auto_close_pulse'] = True
                    self.shared['partial_1_auto_close_pulse_time'] = now
            
            # Clear partial 1 auto-close pulse after 200ms
            if self.shared.get('partial_1_auto_close_pulse', False) and (now - self.shared.get('partial_1_auto_close_pulse_time', 0)) >= 0.2:
                self.shared['partial_1_auto_close_pulse'] = False
            
            # Partial 2 auto-close countdown (SEPARATE timer)
            if self.shared['partial_2_auto_close_active'] and (now - last_partial_2_update) >= 1.0:
                self.shared['partial_2_auto_close_countdown'] -= 1
                last_partial_2_update = now
                if self.shared['partial_2_auto_close_countdown'] <= 0:
                    print("Partial 2 auto-close triggered - sending momentary CLOSE pulse")
                    self.shared['partial_2_auto_close_active'] = False
                    self.shared['closing_from_partial'] = 'P2'
                    # Send momentary pulse (200ms) instead of sustained command
                    self.shared['partial_2_auto_close_pulse'] = True
                    self.shared['partial_2_auto_close_pulse_time'] = now
            
            # Clear partial 2 auto-close pulse after 200ms
            if self.shared.get('partial_2_auto_close_pulse', False) and (now - self.shared.get('partial_2_auto_close_pulse_time', 0)) >= 0.2:
                self.shared['partial_2_auto_close_pulse'] = False
            
            # Clear timed open close pulse after 200ms
            if self.shared.get('timed_open_close_pulse', False) and (now - self.shared.get('timed_open_close_pulse_time', 0)) >= 0.2:
                self.shared['timed_open_close_pulse'] = False
            
            # Sleep 50ms (20Hz)
            threading.Event().wait(0.05)

    def _evaluate_commands(self, now):
        """
        Evaluate current input states against gate state each cycle.
        Decide if operations should start, stop, or continue.
        This runs EVERY cycle - inputs are read from flags.
        """
        
        # DEBUG: Print ALL command flags every cycle when any safety edge active
        if self.shared['safety_stop_opening_active'] or self.shared['safety_stop_closing_active']:
            print(f"\n[CYCLE DEBUG] state={self.shared['state']}, "
                  f"reversing={self.shared['safety_reversing']}, "
                  f"movement_cmd={self.shared['movement_command']}")
            print(f"  Commands: open={self.shared['cmd_open_active']}, "
                  f"close={self.shared['cmd_close_active']}, "
                  f"stop={self.shared['cmd_stop_active']}")
            print(f"  Safety: stop_opening_active={self.shared['safety_stop_opening_active']}, "
                  f"stop_opening_reversed={self.shared.get('safety_stop_opening_reversed', False)}, "
                  f"stop_opening_triggered={self.shared.get('safety_stop_opening_triggered', False)}")
            print(f"  Safety: stop_closing_active={self.shared['safety_stop_closing_active']}, "
                  f"stop_closing_reversed={self.shared.get('safety_stop_closing_reversed', False)}, "
                  f"stop_closing_triggered={self.shared.get('safety_stop_closing_triggered', False)}")
        
        # Debug: Print flag states when any command is active (DISABLED - too spammy)
        # if self.shared['cmd_open_active'] or self.shared['cmd_close_active'] or self.shared['cmd_stop_active']:
        #     print(f"[EVAL] State:{self.shared['state']} Open:{self.shared['cmd_open_active']} Close:{self.shared['cmd_close_active']} Stop:{self.shared['cmd_stop_active']}")
        
        # DEADMAN CONTROLS - Override everything (except safety which runs separately)
        if self.shared['deadman_open_active'] or self.shared['deadman_close_active']:
            # Let _process_deadman_controls handle this
            return
        
        # SAFETY EDGES SUSTAINED - After reversal, act as full STOP
        # Before reversal: block movement in their direction only
        # After reversal: block ALL movement (like STOP button)
        # DURING reversal: also block ALL movement (don't let commands restart movement)
        
        # Check if either edge has completed reversal and is still sustained
        # OR if we're currently doing a safety reversal (block during reversal too)
        safety_edge_acting_as_stop = (
            self.shared['safety_reversing'] or  # DURING reversal
            (self.shared['safety_stop_closing_active'] and self.shared.get('safety_stop_closing_reversed', False)) or
            (self.shared['safety_stop_opening_active'] and self.shared.get('safety_stop_opening_reversed', False))
        )
        
        # DEBUG: Print flag states when safety edges active
        if self.shared['safety_stop_opening_active'] or self.shared['safety_stop_closing_active']:
            print(f"[SAFETY DEBUG] stop_opening_active={self.shared['safety_stop_opening_active']}, "
                  f"stop_opening_reversed={self.shared.get('safety_stop_opening_reversed', False)}, "
                  f"stop_closing_active={self.shared['safety_stop_closing_active']}, "
                  f"stop_closing_reversed={self.shared.get('safety_stop_closing_reversed', False)}, "
                  f"safety_reversing={self.shared['safety_reversing']}, "
                  f"acting_as_stop={safety_edge_acting_as_stop}, "
                  f"state={self.shared['state']}, "
                  f"cmd_open={self.shared['cmd_open_active']}, "
                  f"cmd_close={self.shared['cmd_close_active']}")
        
        if safety_edge_acting_as_stop:
            # Act exactly like sustained STOP - block everything
            print(f"[SAFETY BLOCK] Safety edge acting as STOP - blocking all commands")
            # Stop any active movement
            if self.shared['state'] not in ['STOPPED', 'CLOSED', 'OPEN', 'PARTIAL_1', 'PARTIAL_2', 'REVERSING_FROM_OPEN', 'REVERSING_FROM_CLOSE']:
                self._execute_stop()
            # Block ALL command processing - don't let anything through
            return
        
        # Safety edges before reversal - block their respective directions
        if self.shared['safety_stop_closing_active']:
            # Block ANY close-direction movement while sustained
            # This includes: CLOSE command, auto-close, partial auto-close
            # CRITICAL: This must block regardless of current state (STOPPED, CLOSING, OPEN, etc.)
            if self.shared['cmd_close_active'] or self.shared.get('auto_close_pulse', False) or self.shared.get('partial_1_auto_close_pulse', False) or self.shared.get('partial_2_auto_close_pulse', False) or self.shared.get('timed_open_close_pulse', False):
                # If we're in a closing state and not doing safety reversal, stop
                # BUT: allow _process_safety_edges to initiate the reversal first
                if self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                    if not self.shared['safety_reversing'] and self.shared['safety_stop_closing_triggered']:
                        # Only stop if reversal already happened (triggered flag is set)
                        self._execute_stop()
                # BLOCK all closing commands completely - return regardless of state
                return
        
        if self.shared['safety_stop_opening_active']:
            # Block ANY open-direction movement while sustained
            # This includes: OPEN command, TIMED OPEN, PARTIAL commands
            # CRITICAL: This must block regardless of current state (STOPPED, OPENING, PARTIAL, etc.)
            if self.shared['cmd_open_active'] or self.shared['timed_open_active'] or self.shared['partial_1_active'] or self.shared['partial_2_active']:
                # If we're in an opening state and not doing safety reversal, stop
                # BUT: allow _process_safety_edges to initiate the reversal first
                if self.shared['state'] in ['OPENING', 'OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                    if not self.shared['safety_reversing'] and self.shared['safety_stop_opening_triggered']:
                        # Only stop if reversal already happened (triggered flag is set)
                        self._execute_stop()
                # BLOCK all opening commands completely - return regardless of state
                return
        
        # SUSTAINED STOP - Blocks everything
        if self.shared['cmd_stop_active']:
            if self.shared['state'] not in ['STOPPED', 'CLOSED', 'OPEN', 'PARTIAL_1', 'PARTIAL_2']:
                self._execute_stop()
            return
        
        # PRIORITY CHECK: If OPEN command active while CLOSING, reverse immediately
        # This allows user to interrupt auto-close by pressing OPEN
        if self.shared['cmd_open_active'] and self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
            if self.shared['movement_command'] == 'CLOSE':  # Make sure we're actually moving
                print("OPEN command while closing - reversing (priority override)")
                self._execute_open()
            return
        
        # AUTO-CLOSE PULSE - Process momentary pulse from auto-close timer
        # This is processed with high priority but after OPEN override check
        if self.shared.get('auto_close_pulse', False):
            if self.shared['state'] == 'OPEN':
                # Check if partial commands are sustained - if so, return to that partial
                if self.shared['partial_2_active']:  # PO2 has priority
                    print("Auto-close pulse - PO2 sustained, moving to PARTIAL_2")
                    self._move_to_partial_2_from_open()
                elif self.shared['partial_1_active']:
                    print("Auto-close pulse - PO1 sustained, moving to PARTIAL_1")
                    self._move_to_partial_1_from_open()
                else:
                    # No partial sustained - close fully
                    print("Auto-close pulse - no PO sustained, closing fully")
                    self._execute_close()
            return
        
        # PARTIAL 1 AUTO-CLOSE PULSE - Process momentary pulse from PO1 timer
        if self.shared.get('partial_1_auto_close_pulse', False):
            if self.shared['state'] == 'PARTIAL_1':
                print("Partial 1 auto-close pulse received - closing from PARTIAL_1")
                self._execute_close()
            return
        
        # PARTIAL 2 AUTO-CLOSE PULSE - Process momentary pulse from PO2 timer
        if self.shared.get('partial_2_auto_close_pulse', False):
            if self.shared['state'] == 'PARTIAL_2':
                print("Partial 2 auto-close pulse received - closing from PARTIAL_2")
                self._execute_close()
            return
        
        # TIMED OPEN CLOSE PULSE - Process momentary pulse from timed open release
        if self.shared.get('timed_open_close_pulse', False):
            if self.shared['state'] == 'OPEN':
                # Check if partial commands are sustained - if so, return to that partial
                if self.shared['partial_2_active']:  # PO2 has priority
                    print("Timed open close pulse - PO2 sustained, moving to PARTIAL_2")
                    self._move_to_partial_2_from_open()
                elif self.shared['partial_1_active']:
                    print("Timed open close pulse - PO1 sustained, moving to PARTIAL_1")
                    self._move_to_partial_1_from_open()
                else:
                    # No partial sustained - close fully
                    print("Timed open close pulse - no PO sustained, closing fully")
                    self._execute_close()
            return
        
        # CLOSE COMMAND ACTIVE
        if self.shared['cmd_close_active']:
            # If at OPEN with sustained partial, close to that partial (not block!)
            if self.shared['state'] == 'OPEN' and (self.shared['partial_1_active'] or self.shared['partial_2_active']):
                # Mark that we're returning from full open to partial
                self.shared['returning_from_full_open'] = True
                self._execute_close()
                return
            
            # Block if sustained partial commands active (but not at OPEN - handled above)
            if self.shared['partial_1_active'] or self.shared['partial_2_active']:
                return
            
            # If opening, stop and reverse
            if self.shared['state'] in ['OPENING', 'OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                if self.shared['movement_command'] == 'OPEN':  # Make sure we're actually moving
                    print("CLOSE command while opening - reversing")
                    self._execute_close()
                return
            
            # If at OPEN, start closing
            if self.shared['state'] == 'OPEN':
                self._execute_close()
                return
            
            # If at STOPPED, start closing
            if self.shared['state'] == 'STOPPED':
                self._execute_close()
                return
            
            # If at partial positions and no partial sustained
            if self.shared['state'] in ['PARTIAL_1', 'PARTIAL_2']:
                if not self.shared['partial_1_active'] and not self.shared['partial_2_active']:
                    self._execute_close()
                return
            
            # If already closing, let it continue
            return
        
        # OPEN COMMAND ACTIVE
        if self.shared['cmd_open_active']:
            # If closing, stop and reverse
            if self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                if self.shared['movement_command'] == 'CLOSE':  # Make sure we're actually moving
                    print("OPEN command while closing - reversing")
                    self._execute_open()
                return
            
            # If opening to partial, change to full open
            if self.shared['state'] in ['OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                print(f"OPEN command during {self.shared['state']} - changing to full OPEN")
                self.shared['state'] = 'OPENING'
                # Targets are already set correctly, just change state
                return
            
            # If at CLOSED, start opening
            if self.shared['state'] == 'CLOSED':
                self._execute_open()
                return
            
            # If at STOPPED, start opening
            if self.shared['state'] == 'STOPPED':
                self._execute_open()
                return
            
            # If at OPEN, block auto-close timer while sustained
            if self.shared['state'] == 'OPEN':
                self.shared['auto_close_active'] = False
                return
            
            # If at partial, open to full (partials can be sustained - OPEN overrides to full)
            if self.shared['state'] in ['PARTIAL_1', 'PARTIAL_2']:
                self._execute_open()
                return
            
            # If already opening, let it continue
            return
        
        # OPEN COMMAND NOT ACTIVE - Check if auto-close should start
        # If at OPEN state and no OPEN/TIMED_OPEN sustained, start auto-close if enabled
        if not self.shared['cmd_open_active'] and not self.shared['timed_open_active']:
            if self.shared['state'] == 'OPEN' and self.auto_close_enabled and not self.shared['auto_close_active']:
                print("Starting auto-close timer (OPEN released)")
                self.shared['auto_close_active'] = True
                self.shared['auto_close_countdown'] = self.auto_close_time
        
        # PARTIAL COMMANDS NOT ACTIVE - Check if partial auto-close should start
        # If at PARTIAL_1 and PO1 not sustained, start PO1 auto-close timer
        if not self.shared['partial_1_active']:
            if self.shared['state'] == 'PARTIAL_1' and self.auto_close_enabled and not self.shared['partial_1_auto_close_active']:
                print(f"Starting PO1 auto-close timer ({self.partial_1_auto_close_time}s)")
                self.shared['partial_1_auto_close_active'] = True
                self.shared['partial_1_auto_close_countdown'] = self.partial_1_auto_close_time
        
        # If at PARTIAL_2 and PO2 not sustained, start PO2 auto-close timer
        if not self.shared['partial_2_active']:
            if self.shared['state'] == 'PARTIAL_2' and self.auto_close_enabled and not self.shared['partial_2_auto_close_active']:
                print(f"Starting PO2 auto-close timer ({self.partial_2_auto_close_time}s)")
                self.shared['partial_2_auto_close_active'] = True
                self.shared['partial_2_auto_close_countdown'] = self.partial_2_auto_close_time
        
        # TIMED OPEN - Opens while sustained, immediately closes when released
        # PRIORITY: Evaluated BEFORE partials so it can override sustained PO commands
        if self.shared['timed_open_active']:
            # Mark that timed open is controlling the gate
            if not self.shared['timed_open_triggered']:
                self.shared['timed_open_triggered'] = True
            
            # If closing, stop and reverse (just like normal OPEN)
            if self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                if self.shared['movement_command'] == 'CLOSE':  # Make sure we're actually moving
                    print("TIMED OPEN command while closing - reversing")
                    self._execute_open()
                return
            
            # If at CLOSED or STOPPED, start opening
            if self.shared['state'] == 'CLOSED':
                self._execute_open()
                return
            elif self.shared['state'] == 'STOPPED':
                self._execute_open()
                return
            
            # If at OPEN, block auto-close timer while sustained
            if self.shared['state'] == 'OPEN':
                self.shared['auto_close_active'] = False
                return
            
            # If at partial, open to full (TIMED OPEN overrides sustained partials)
            if self.shared['state'] in ['PARTIAL_1', 'PARTIAL_2']:
                print("TIMED OPEN overriding sustained partial - opening to full")
                self._execute_open()
                return
            
            # If already opening, let it continue
            return
        
        # TIMED OPEN RELEASED - Send momentary close pulse
        # Detect falling edge: was active, now released, and gate is open
        if not self.shared['timed_open_active'] and self.shared['timed_open_triggered']:
            if self.shared['state'] == 'OPEN':
                print("TIMED OPEN released - sending momentary CLOSE pulse")
                self.shared['timed_open_triggered'] = False  # Clear trigger flag
                # Send momentary pulse (200ms) instead of sustained command
                self.shared['timed_open_close_pulse'] = True
                self.shared['timed_open_close_pulse_time'] = now
                return
        
        # PARTIAL 2 COMMAND ACTIVE (PO2 has priority over PO1)
        if self.shared['partial_2_active']:
            # Block if CLOSE sustained
            if self.shared['cmd_close_active']:
                return
            
            # If at closed, stopped, or other partial, move to partial 2
            if self.shared['state'] == 'CLOSED':
                self._move_to_partial_2()
                return
            elif self.shared['state'] == 'STOPPED':
                self._move_to_partial_2()
                return
            elif self.shared['state'] == 'PARTIAL_1':
                self._move_to_partial_2()
                return
            
            # If at partial 2, block auto-close
            if self.shared['state'] == 'PARTIAL_2':
                self.shared['partial_auto_close_active'] = False
                return
            
            return
        
        # PARTIAL 1 COMMAND ACTIVE
        if self.shared['partial_1_active']:
            # Block if CLOSE sustained
            if self.shared['cmd_close_active']:
                return

            # If closing from PO1, reverse back to PO1
            if self.shared['state'] == 'CLOSING_TO_PARTIAL_1':
                print("PO1 command while closing from PO1 - reversing M1 back to PO1")
                self._move_to_partial_1()
                return

            # If at closed, stopped, or other partial, move to partial 1
            if self.shared['state'] == 'CLOSED':
                self._move_to_partial_1()
                return
            elif self.shared['state'] == 'STOPPED':
                self._move_to_partial_1()
                return
            elif self.shared['state'] == 'PARTIAL_2':
                self._move_to_partial_1()
                return

            # If at partial 1, block auto-close
            if self.shared['state'] == 'PARTIAL_1':
                self.shared['partial_auto_close_active'] = False
                return

            return
        
        # PARTIAL 2 COMMAND ACTIVE
        if self.shared['partial_2_active']:
            # Block if CLOSE sustained
            if self.shared['cmd_close_active']:
                return

            # If closing from PO2, reverse back to PO2
            if self.shared['state'] == 'CLOSING_TO_PARTIAL_2':
                print("PO2 command while closing from PO2 - reversing M1 back to PO2")
                self._move_to_partial_2()
                return

            # If at closed, stopped, or other partial, move to partial 2
            if self.shared['state'] == 'CLOSED':
                self._move_to_partial_2()
                return
            elif self.shared['state'] == 'STOPPED':
                self._move_to_partial_2()
                return
            elif self.shared['state'] == 'PARTIAL_1':
                self._move_to_partial_2()
                return

            # If at partial 2, block auto-close
            if self.shared['state'] == 'PARTIAL_2':
                self.shared['partial_auto_close_active'] = False
                return

            return
        
    

    def _check_command_conflicts(self):
        """Handle command blocking and conflicts"""
        # Both deadman controls = STOP
        if self.shared['deadman_open_active'] and self.shared['deadman_close_active']:
            print("Both deadman controls active - STOPPING")
            self.shared['deadman_open_active'] = False
            self.shared['deadman_close_active'] = False
            self.cmd_stop()
        
        # STOP blocks auto-close timers
        if self.shared['cmd_stop_active']:
            if self.shared['auto_close_active']:
                print("STOP blocking auto-close timer")
                self.shared['auto_close_active'] = False
            if self.shared['partial_auto_close_active']:
                print("STOP blocking partial auto-close timer")
                self.shared['partial_auto_close_active'] = False
        
        # Sustained OPEN resets auto-close timer
        if self.shared['cmd_open_active'] and self.shared['state'] == 'OPEN' and self.shared['auto_close_active']:
            self.shared['auto_close_countdown'] = self.auto_close_time
        
        # If OPEN released while at full OPEN, start auto-close (unless STOP active)
        if not self.shared['cmd_open_active'] and self.shared['state'] == 'OPEN' and not self.shared['auto_close_active'] and self.auto_close_enabled and not self.shared['timed_open_active'] and not self.shared['cmd_stop_active']:
            print("OPEN command released - starting auto-close")
            self.shared['auto_close_active'] = True
            self.shared['auto_close_countdown'] = self.auto_close_time
        
        # Sustained PARTIAL commands reset partial auto-close timer
        if self.shared['state'] == 'PARTIAL_1' and self.shared['partial_1_active'] and self.shared['partial_auto_close_active']:
            self.shared['partial_auto_close_countdown'] = self.partial_auto_close_time
        if self.shared['state'] == 'PARTIAL_2' and self.shared['partial_2_active'] and self.shared['partial_auto_close_active']:
            self.shared['partial_auto_close_countdown'] = self.partial_auto_close_time
        
        # PO2 takes precedence over PO1
        if self.shared['partial_1_active'] and self.shared['partial_2_active']:
            # Both active - ensure we're at PO2
            if self.shared['state'] == 'PARTIAL_1':
                print("Both PO1 and PO2 active - moving to PO2 (higher priority)")
                self._move_to_partial_2()
        
        # If at PO2 and PO2 released but PO1 still active, move to PO1
        if self.shared['state'] == 'PARTIAL_2' and not self.shared['partial_2_active'] and self.shared['partial_1_active']:
            print("PO2 released with PO1 active - moving to PO1")
            self._move_to_partial_1()
        
        # Retry sustained commands if safety edges cleared
        if not self.shared['safety_stop_closing_active'] and not self.shared['safety_stop_opening_active']:
            # Safety clear - retry sustained commands if they're active
            if self.shared['cmd_open_active'] and self.shared['state'] != 'OPENING' and self.shared['state'] != 'OPEN':
                print("Safety cleared - resuming OPEN command")
                self.cmd_open()
            elif self.shared['cmd_close_active'] and self.shared['state'] != 'CLOSING' and self.shared['state'] != 'CLOSED':
                print("Safety cleared - resuming CLOSE command")
                self.cmd_close()
        
        # Retry sustained CLOSE if closing photocell cleared and gate was stopped
        if not self.shared['photocell_closing_active'] and self.shared['cmd_close_active']:
            if self.shared['state'] == 'STOPPED' or self.shared['state'] == 'OPEN':
                print("Closing photocell cleared - resuming CLOSE command")
                self.cmd_close()
    
    def _process_timed_open(self):
        """Handle timed open control - designed for time clocks"""
        if self.shared['timed_open_active']:
            # Command active - ensure gate is open
            if not self.shared['timed_open_triggered']:
                print("Timed open activated - opening gate")
                self.cmd_open()
                self.shared['timed_open_triggered'] = True
            # Cancel auto-close while timed open active
            self.shared['auto_close_active'] = False
        else:
            # Command removed - trigger immediate close
            if self.shared['timed_open_triggered']:
                print("Timed open deactivated - closing gate")
                self.cmd_close()
                self.shared['timed_open_triggered'] = False
    
    
    def _execute_open(self):
        """Start opening operation - called from command evaluator"""
        print(f"\n>>> [_execute_open CALLED] M1:{self.shared['m1_position']:.1f}s M2:{self.shared['m2_position']:.1f}s")
        print(f"    Current state: {self.shared['state']}, safety_reversing: {self.shared['safety_reversing']}")
        print(f"    Flags: cmd_open={self.shared['cmd_open_active']}, stop_opening_active={self.shared['safety_stop_opening_active']}")
        
        # Stop motors first (important when reversing direction)
        
        # Cancel timers
        self.shared['auto_close_active'] = False
        self.shared['partial_auto_close_active'] = False
        
        # Clear pause state if resuming
        if self.shared['opening_paused']:
            print("Resuming from pause")
            self.shared['resume_time'] = time()
            self.shared['opening_paused'] = False
            return
        
        # Start fresh open operation
        self.shared['state'] = 'OPENING'
        self.shared['movement_start_time'] = time()
        self.shared['movement_command'] = 'OPEN'
        self.shared['resume_time'] = None
        self.shared['stopped_after_opening'] = False
        self.shared['opening_paused'] = False
        self.shared['returning_from_full_open'] = False
        
        # M1 starts immediately
        self.shared['m1_move_start'] = time()
        self.shared['m1_target'] = self.shared['m1_position']
        
        # M2 will start after delay (handled in position update)
        self.shared['m2_move_start'] = None
        self.shared['m2_target'] = self.shared['m2_position']
    
    def _execute_close(self):
        """Start closing operation - called from command evaluator"""
        print(f"\n>>> CLOSE command - M1:{self.shared['m1_position']:.1f}s M2:{self.shared['m2_position']:.1f}s")
        
        # Stop motors first (important when reversing direction)
        
        # Cancel auto-close
        self.shared['auto_close_active'] = False
        self.shared['partial_auto_close_active'] = False
        
        # Start movement
        self.shared['state'] = 'CLOSING'
        self.shared['movement_start_time'] = time()
        self.shared['movement_command'] = 'CLOSE'
        self.shared['resume_time'] = None
        self.shared['stopped_after_closing'] = False
        
        # M2 starts immediately
        self.shared['m2_move_start'] = time()
        self.shared['m2_target'] = self.shared['m2_position']
        
        # M1 will start after delay (handled in position update)
        self.shared['m1_move_start'] = None
        self.shared['m1_target'] = self.shared['m1_position']
    
    def _execute_stop(self):
        """Stop operation - called from command evaluator"""
        print(f"\n>>> STOP command - M1:{self.shared['m1_position']:.1f}s M2:{self.shared['m2_position']:.1f}s")
        
        # Remember what we were doing for 3/4-step logic
        if self.shared['state'] == 'OPENING':
            self.shared['stopped_after_opening'] = True
            self.shared['stopped_after_closing'] = False
        elif self.shared['state'] == 'CLOSING':
            self.shared['stopped_after_closing'] = True
            self.shared['stopped_after_opening'] = False
        
        # Stop movement
        self.shared['state'] = 'STOPPED'
        self.shared['movement_start_time'] = None
        self.shared['movement_command'] = None
        self.shared['m1_move_start'] = None
        self.shared['m2_move_start'] = None
        self.shared['auto_close_active'] = False
        self.shared['opening_paused'] = False
    
    def _check_command_conflicts(self):
        """Handle command blocking and conflicts"""
        # Both deadman controls = STOP
        if self.shared['deadman_open_active'] and self.shared['deadman_close_active']:
            print("Both deadman controls active - STOPPING")
            self.shared['deadman_open_active'] = False
            self.shared['deadman_close_active'] = False
            self.cmd_stop()
        
        # STOP blocks auto-close timers
        if self.shared['cmd_stop_active']:
            if self.shared['auto_close_active']:
                print("STOP blocking auto-close timer")
                self.shared['auto_close_active'] = False
            if self.shared['partial_auto_close_active']:
                print("STOP blocking partial auto-close timer")
                self.shared['partial_auto_close_active'] = False
        
        # Sustained OPEN resets auto-close timer
        if self.shared['cmd_open_active'] and self.shared['state'] == 'OPEN' and self.shared['auto_close_active']:
            self.shared['auto_close_countdown'] = self.auto_close_time
        
        # If OPEN released while at full OPEN, start auto-close (unless STOP active)
        if not self.shared['cmd_open_active'] and self.shared['state'] == 'OPEN' and not self.shared['auto_close_active'] and self.auto_close_enabled and not self.shared['timed_open_active'] and not self.shared['cmd_stop_active']:
            print("OPEN command released - starting auto-close")
            self.shared['auto_close_active'] = True
            self.shared['auto_close_countdown'] = self.auto_close_time
        
        # Sustained PARTIAL commands reset partial auto-close timer
        if self.shared['state'] == 'PARTIAL_1' and self.shared['partial_1_active'] and self.shared['partial_auto_close_active']:
            self.shared['partial_auto_close_countdown'] = self.partial_auto_close_time
        if self.shared['state'] == 'PARTIAL_2' and self.shared['partial_2_active'] and self.shared['partial_auto_close_active']:
            self.shared['partial_auto_close_countdown'] = self.partial_auto_close_time
        
        # PO2 takes precedence over PO1
        if self.shared['partial_1_active'] and self.shared['partial_2_active']:
            # Both active - ensure we're at PO2
            if self.shared['state'] == 'PARTIAL_1':
                print("Both PO1 and PO2 active - moving to PO2 (higher priority)")
                self._move_to_partial_2()
        
        # If at PO2 and PO2 released but PO1 still active, move to PO1
        if self.shared['state'] == 'PARTIAL_2' and not self.shared['partial_2_active'] and self.shared['partial_1_active']:
            print("PO2 released with PO1 active - moving to PO1")
            self._move_to_partial_1()
        
        # Retry sustained commands if safety edges cleared
        if not self.shared['safety_stop_closing_active'] and not self.shared['safety_stop_opening_active']:
            # Safety clear - retry sustained commands if they're active
            if self.shared['cmd_open_active'] and self.shared['state'] != 'OPENING' and self.shared['state'] != 'OPEN':
                print("Safety cleared - resuming OPEN command")
                self.cmd_open()
            elif self.shared['cmd_close_active'] and self.shared['state'] != 'CLOSING' and self.shared['state'] != 'CLOSED':
                print("Safety cleared - resuming CLOSE command")
                self.cmd_close()
        
        # Retry sustained CLOSE if closing photocell cleared and gate was stopped
        if not self.shared['photocell_closing_active'] and self.shared['cmd_close_active']:
            if self.shared['state'] == 'STOPPED' or self.shared['state'] == 'OPEN':
                print("Closing photocell cleared - resuming CLOSE command")
                self.cmd_close()
    

    def _process_safety_edges(self, now):
        """Handle safety edge logic - highest priority"""
        # Check if currently doing safety reversal
        if self.shared['safety_reversing']:
            elapsed = now - self.shared['safety_reverse_start']
            if elapsed >= self.safety_reverse_time:
                # Reversal complete - STOP and mark as reversed
                print("Safety reversal complete - STOPPING")
                self.shared['safety_reversing'] = False
                self.shared['execute_safety_reverse'] = False
                # Mark that this edge has completed reversal (becomes full STOP)
                # Use state to determine which edge triggered reversal (more reliable than checking if still active)
                if self.shared['state'] == 'REVERSING_FROM_CLOSE':
                    # Was reversing from closing, so STOP CLOSING edge triggered it
                    self.shared['safety_stop_closing_reversed'] = True
                    print(f"  Marked STOP CLOSING as reversed (edge still active: {self.shared['safety_stop_closing_active']})")
                elif self.shared['state'] == 'REVERSING_FROM_OPEN':
                    # Was reversing from opening, so STOP OPENING edge triggered it
                    self.shared['safety_stop_opening_reversed'] = True
                    print(f"  Marked STOP OPENING as reversed (edge still active: {self.shared['safety_stop_opening_active']})")
                self.cmd_stop()
            # Motor manager handles the actual reversal via shared memory flags
            return
        
        # Reset trigger flags and reversed status when each edge is released
        if not self.shared['safety_stop_closing_active']:
            self.shared['safety_stop_closing_triggered'] = False
            self.shared['safety_stop_closing_reversed'] = False
        if not self.shared['safety_stop_opening_active']:
            self.shared['safety_stop_opening_triggered'] = False
            self.shared['safety_stop_opening_reversed'] = False
        
        # STOP CLOSING edge
        if self.shared['safety_stop_closing_active'] and not self.shared['safety_stop_closing_triggered']:
            # Only act if at resting position or actively moving
            if self.shared['state'] == 'OPEN':
                # Reset auto-close timer if active
                if self.shared['auto_close_active']:
                    self.shared['auto_close_countdown'] = self.auto_close_time
                self.shared['safety_stop_closing_triggered'] = True
            elif self.shared['state'] == 'PARTIAL_1':
                # Reset PO1 auto-close timer if active
                if self.shared['partial_1_auto_close_active']:
                    self.shared['partial_1_auto_close_countdown'] = self.partial_1_auto_close_time
                self.shared['safety_stop_closing_triggered'] = True
            elif self.shared['state'] == 'PARTIAL_2':
                # Reset PO2 auto-close timer if active
                if self.shared['partial_2_auto_close_active']:
                    self.shared['partial_2_auto_close_countdown'] = self.partial_2_auto_close_time
                self.shared['safety_stop_closing_triggered'] = True
            elif self.shared['state'] == 'CLOSED':
                # At fully closed - just mark as triggered, no action needed
                self.shared['safety_stop_closing_triggered'] = True
            elif self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                # Actively closing - trigger reversal
                print(f"STOP CLOSING triggered during {self.shared['state']} - {self.safety_reverse_time}s full reverse then STOP")
                self.shared['safety_reversing'] = True
                self.shared['safety_reverse_start'] = now
                self.shared['state'] = 'REVERSING_FROM_CLOSE'
                self.shared['movement_command'] = None
                self.shared['m1_move_start'] = None
                self.shared['m2_move_start'] = None
                self.shared['safety_stop_closing_triggered'] = True
            # If STOPPED or REVERSING states, do nothing (don't trigger)
        
        # STOP OPENING edge
        if self.shared['safety_stop_opening_active'] and not self.shared['safety_stop_opening_triggered']:
            # Only act if at resting position or actively moving
            if self.shared['state'] == 'OPEN':
                # Reset auto-close timer if active
                if self.shared['auto_close_active']:
                    self.shared['auto_close_countdown'] = self.auto_close_time
                self.shared['safety_stop_opening_triggered'] = True
            elif self.shared['state'] == 'PARTIAL_1':
                # Reset PO1 auto-close timer if active
                if self.shared['partial_1_auto_close_active']:
                    self.shared['partial_1_auto_close_countdown'] = self.partial_1_auto_close_time
                self.shared['safety_stop_opening_triggered'] = True
            elif self.shared['state'] == 'PARTIAL_2':
                # Reset PO2 auto-close timer if active
                if self.shared['partial_2_auto_close_active']:
                    self.shared['partial_2_auto_close_countdown'] = self.partial_2_auto_close_time
                self.shared['safety_stop_opening_triggered'] = True
            elif self.shared['state'] == 'CLOSED':
                # At fully closed - just mark as triggered, no action needed
                self.shared['safety_stop_opening_triggered'] = True
            elif self.shared['state'] in ['OPENING', 'OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                # Actively opening - trigger reversal (or immediate stop if closing photocell also active)
                if self.shared['photocell_closing_active']:
                    print("STOP OPENING + closing photocell - immediate STOP")
                    self.cmd_stop()
                    self.shared['safety_stop_opening_triggered'] = True
                else:
                    # Full reverse then stop
                    print(f"STOP OPENING triggered during {self.shared['state']} - {self.safety_reverse_time}s full reverse then STOP")
                    self.shared['safety_reversing'] = True
                    self.shared['safety_reverse_start'] = now
                    self.shared['state'] = 'REVERSING_FROM_OPEN'
                    self.shared['movement_command'] = None
                    self.shared['m1_move_start'] = None
                    self.shared['m2_move_start'] = None
                    self.shared['safety_stop_opening_triggered'] = True
            # If STOPPED or REVERSING states, do nothing (don't trigger)
    
    def _process_photocells(self):
        """Handle photocell logic - completely rewritten for correct behavior"""
        
        # Reset trigger flags when photocells released
        if not self.shared['photocell_closing_active']:
            self.shared['photocell_closing_triggered'] = False
        if not self.shared['photocell_opening_active']:
            self.shared['photocell_opening_triggered'] = False
        
        # === CLOSING PHOTOCELL (CX) LOGIC ===
        if self.shared['photocell_closing_active']:
            # At open positions - hold/reset ALL active auto-close timers (full, PO1, PO2)
            if self.shared['auto_close_active']:
                self.shared['auto_close_countdown'] = self.auto_close_time
            if self.shared['partial_1_auto_close_active']:
                self.shared['partial_1_auto_close_countdown'] = self.partial_1_auto_close_time
            if self.shared['partial_2_auto_close_active']:
                self.shared['partial_2_auto_close_countdown'] = self.partial_2_auto_close_time
            
            # During CLOSING - trigger reopen to last position (only once)
            if not self.shared['photocell_closing_triggered']:
                if self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                    self.shared['photocell_closing_triggered'] = True
                    print(f"CLOSING PHOTOCELL triggered during {self.shared['state']} - reopening to {self.shared['last_open_position']}")
                    
                    # Reopen to last peak position
                    if self.shared['last_open_position'] == 'OPEN':
                        self._execute_open()
                    elif self.shared['last_open_position'] == 'PARTIAL_1':
                        self._move_to_partial_1()
                    elif self.shared['last_open_position'] == 'PARTIAL_2':
                        self._move_to_partial_2()
                    else:
                        # Fallback - reopen fully
                        print("Warning: last_open_position not set, defaulting to full OPEN")
                        self._execute_open()
        
        # === OPENING PHOTOCELL (CY) LOGIC ===
        if self.shared['photocell_opening_active']:
            # At open positions - hold/reset ALL active auto-close timers (full, PO1, PO2)
            if self.shared['auto_close_active']:
                self.shared['auto_close_countdown'] = self.auto_close_time
            if self.shared['partial_1_auto_close_active']:
                self.shared['partial_1_auto_close_countdown'] = self.partial_1_auto_close_time
            if self.shared['partial_2_auto_close_active']:
                self.shared['partial_2_auto_close_countdown'] = self.partial_2_auto_close_time
            
            # During OPENING - PAUSE until released
            if self.shared['state'] in ['OPENING', 'OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                if not self.shared['opening_paused']:
                    print(f"OPENING PHOTOCELL triggered - PAUSING {self.shared['state']}")
                    self.shared['opening_paused'] = True
                    self.shared['pause_time'] = time()
                    # Motors will be stopped by motor speed logic checking opening_paused flag
            
            # During CLOSING - PAUSE until released, then reopen
            if self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                if not self.shared['opening_paused']:
                    print(f"OPENING PHOTOCELL triggered - PAUSING {self.shared['state']}")
                    self.shared['opening_paused'] = True
                    self.shared['pause_time'] = time()
                    # Motors will be stopped by motor speed logic checking opening_paused flag
        
        else:
            # OPENING PHOTOCELL RELEASED
            if self.shared['opening_paused']:
                # Were we closing? Reopen to last position
                if self.shared['state'] in ['CLOSING', 'CLOSING_TO_PARTIAL_1', 'CLOSING_TO_PARTIAL_2']:
                    print(f"OPENING PHOTOCELL released - reopening to {self.shared['last_open_position']}")
                    self.shared['opening_paused'] = False
                    
                    # Reopen to last peak position
                    if self.shared['last_open_position'] == 'OPEN':
                        self._execute_open()
                    elif self.shared['last_open_position'] == 'PARTIAL_1':
                        self._move_to_partial_1()
                    elif self.shared['last_open_position'] == 'PARTIAL_2':
                        self._move_to_partial_2()
                    else:
                        # Fallback
                        print("Warning: last_open_position not set, defaulting to full OPEN")
                        self._execute_open()
                
                # Were we opening? Resume opening
                elif self.shared['state'] in ['OPENING', 'OPENING_TO_PARTIAL_1', 'OPENING_TO_PARTIAL_2']:
                    print(f"OPENING PHOTOCELL released - RESUMING {self.shared['state']}")
                    self.shared['opening_paused'] = False
                    self.shared['resume_time'] = time()
                    now = time()
                    pause_duration = now - self.shared['pause_time']
                    # Adjust move start times to account for pause
                    if self.shared['m1_move_start']:
                        self.shared['m1_move_start'] += pause_duration
                    if self.shared['m2_move_start']:
                        self.shared['m2_move_start'] += pause_duration
    
    
    
    
    def _complete_open(self):
        """Movement complete - gates open"""
        print(f"[_complete_open] BEFORE: state={self.shared['state']}, M1={self.shared['m1_position']:.2f}, M2={self.shared['m2_position']:.2f}")
        
        self.shared['state'] = 'OPEN'
        self.shared['movement_start_time'] = None
        self.shared['movement_command'] = None
        self.shared['m1_move_start'] = None
        self.shared['m2_move_start'] = None
        self.shared['m1_position'] = self.run_time
        self.shared['m2_position'] = self.run_time
        self.shared['stopped_after_opening'] = False  # Clear 4-step flag
        
        # Remember this position for photocell reopening
        self.shared['last_open_position'] = 'OPEN'
        
        print(f"[_complete_open] AFTER: state={self.shared['state']}, movement_command={self.shared['movement_command']}")
        print("Gates OPEN")
        
        # Start auto-close (check BEFORE clearing cmd_open_active!)
        # Blocked by sustained OPEN or timed open
        if self.auto_close_enabled and not self.shared['timed_open_active'] and not self.shared['cmd_open_active']:
            self.shared['auto_close_active'] = True
            self.shared['auto_close_countdown'] = self.auto_close_time
        
        # DON'T clear cmd_open_active here - let UI manage it
        # Only exception: if we're NOT at open state somehow, clear it
        # (this shouldn't happen but defensive programming)
    
    def _complete_close(self):
        """Movement complete - gates closed"""
        print(f"[_complete_close] BEFORE: state={self.shared['state']}, M1={self.shared['m1_position']:.2f}, M2={self.shared['m2_position']:.2f}")
        
        self.shared['state'] = 'CLOSED'
        self.shared['movement_start_time'] = None
        self.shared['movement_command'] = None
        self.shared['m1_move_start'] = None
        self.shared['m2_move_start'] = None
        self.shared['m1_position'] = 0
        self.shared['m2_position'] = 0
        self.shared['stopped_after_closing'] = False  # Clear 4-step flag
        self.shared['returning_from_full_open'] = False
        self.shared['closing_from_partial'] = None  # Clear partial closing flag
        
        # Clear cmd_close_active ONLY if we're truly at CLOSED
        # This handles the auto-close case where flag was set by timer
        # UI-triggered closes should have flag cleared by UI
        if self.shared['state'] == 'CLOSED':
            self.shared['cmd_close_active'] = False
        
        print(f"[_complete_close] AFTER: state={self.shared['state']}, movement_command={self.shared['movement_command']}")
        print("Gates CLOSED")
    
    def _complete_partial_1(self):
        """Movement complete - M1 at partial position 1, M2 closed"""
        self.shared['state'] = 'PARTIAL_1'
        self.shared['movement_start_time'] = None
        self.shared['movement_command'] = None
        self.shared['m1_move_start'] = None
        self.shared['m2_move_start'] = None
        self.shared['m1_position'] = self.partial_1_position
        self.shared['m2_position'] = 0
        self.shared['returning_from_full_open'] = False
        
        # Remember this position for photocell reopening
        self.shared['last_open_position'] = 'PARTIAL_1'
        
        print(f"M1 at PARTIAL_1 ({self.partial_1_percent}%), M2 CLOSED")
        
        # Start partial 1 auto-close if enabled AND partial 1 command NOT sustained
        if self.auto_close_enabled and not self.shared['partial_1_active']:
            self.shared['partial_1_auto_close_active'] = True
            self.shared['partial_1_auto_close_countdown'] = self.partial_1_auto_close_time
    
    def _complete_partial_2(self):
        """Movement complete - M1 at partial position 2, M2 closed"""
        self.shared['state'] = 'PARTIAL_2'
        self.shared['movement_start_time'] = None
        self.shared['movement_command'] = None
        self.shared['m1_move_start'] = None
        self.shared['m2_move_start'] = None
        self.shared['m1_position'] = self.partial_2_position
        self.shared['m2_position'] = 0
        self.shared['returning_from_full_open'] = False
        
        # Remember this position for photocell reopening
        self.shared['last_open_position'] = 'PARTIAL_2'
        
        print(f"M1 at PARTIAL_2 ({self.partial_2_percent}%), M2 CLOSED")
        
        # Start partial 2 auto-close if enabled AND partial 2 command NOT sustained
        if self.auto_close_enabled and not self.shared['partial_2_active']:
            self.shared['partial_2_auto_close_active'] = True
            self.shared['partial_2_auto_close_countdown'] = self.partial_2_auto_close_time
    
    def cmd_open(self, sustained=False):
        """Execute OPEN command"""
        # Set sustained flag
        if sustained:
            self.shared['cmd_open_active'] = True
        
        # Block if sustained STOP active
        if self.shared['cmd_stop_active']:
            print("OPEN blocked - STOP command sustained")
            return
        
        # Block if CLOSE command sustained
        if self.shared['cmd_close_active']:
            print("OPEN blocked - CLOSE command sustained")
            return
        
        # Block if deadman controls active
        if self.shared['deadman_open_active'] or self.shared['deadman_close_active']:
            print("OPEN blocked - deadman control active")
            return
        
        # Block if STOP OPENING safety edge active (directional blocking)
        if self.shared['safety_stop_opening_active']:
            print("OPEN blocked - stop opening edge active")
            return
        
        # If already open and auto-close counting, reset timer
        if self.shared['state'] == 'OPEN' and self.shared['auto_close_active']:
            self.shared['auto_close_countdown'] = self.auto_close_time
            print("Auto-close timer RESET")
            return
        
        if self.shared['movement_command'] == 'OPEN':
            print("Already opening")
            return
        
        print(f"\n>>> OPEN command - M1:{self.shared['m1_position']:.1f}s M2:{self.shared['m2_position']:.1f}s")
        
        # If coming from partial position, mark as returning (for intercept logic)
        if self.shared['partial_1_active'] or self.shared['partial_2_active']:
            self.shared['returning_from_full_open'] = True
        
        # Cancel auto-close and partial auto-close
        self.shared['auto_close_active'] = False
        self.shared['partial_auto_close_active'] = False
        
        # Start movement
        self.shared['state'] = 'OPENING'
        self.shared['movement_start_time'] = time()
        self.shared['movement_command'] = 'OPEN'
        self.shared['resume_time'] = None  # Clear resume flag
        
        # M1 starts immediately
        self.shared['m1_move_start'] = time()
        self.shared['m1_target'] = self.shared['m1_position']
        
        # M2 will start after delay (handled in control loop)
        self.shared['m2_move_start'] = None
        self.shared['m2_target'] = self.shared['m2_position']
    
    def cmd_close(self, sustained=False):
        """Execute CLOSE command"""
        # Set sustained flag
        if sustained:
            self.shared['cmd_close_active'] = True
        
        # Block if sustained STOP active
        if self.shared['cmd_stop_active']:
            print("CLOSE blocked - STOP command sustained")
            return
        
        # Block if OPEN command sustained
        if self.shared['cmd_open_active']:
            print("CLOSE blocked - OPEN command sustained")
            return
        
        # Block if sustained partial commands active
        if self.shared['partial_1_active'] or self.shared['partial_2_active']:
            print("CLOSE blocked - partial command sustained")
            return
        
        # Block if deadman controls active
        if self.shared['deadman_open_active'] or self.shared['deadman_close_active']:
            print("CLOSE blocked - deadman control active")
            return
        
        # Block if STOP CLOSING safety edge active (directional blocking)
        if self.shared['safety_stop_closing_active']:
            print("CLOSE blocked - stop closing edge active")
            return
        
        if self.shared['movement_command'] == 'CLOSE':
            print("Already closing")
            return
        
        print(f"\n>>> CLOSE command - M1:{self.shared['m1_position']:.1f}s M2:{self.shared['m2_position']:.1f}s")
        
        # Cancel auto-close
        self.shared['auto_close_active'] = False
        
        # Start movement
        self.shared['state'] = 'CLOSING'
        self.shared['movement_start_time'] = time()
        self.shared['movement_command'] = 'CLOSE'
        self.shared['resume_time'] = None  # Clear resume flag
        
        # M2 starts immediately
        self.shared['m2_move_start'] = time()
        self.shared['m2_target'] = self.shared['m2_position']
        
        # M1 will start after delay (handled in control loop)
        self.shared['m1_move_start'] = None
        self.shared['m1_target'] = self.shared['m1_position']
    
    def cmd_stop(self, sustained=False):
        """Execute STOP command"""
        # Set sustained flag
        if sustained:
            self.shared['cmd_stop_active'] = True

        # Deadman controls override STOP (not blocked)
        if self.shared['deadman_open_active'] or self.shared['deadman_close_active']:
            # Allow deadman to override, don't print block message
            return

        print(f"\n>>> STOP command - M1:{self.shared['m1_position']:.1f}s M2:{self.shared['m2_position']:.1f}s")

        # Remember what we were doing for 3/4-step logic
        if self.shared['state'] == 'OPENING':
            self.shared['stopped_after_opening'] = True
            self.shared['stopped_after_closing'] = False
        elif self.shared['state'] == 'CLOSING':
            self.shared['stopped_after_closing'] = True
            self.shared['stopped_after_opening'] = False

        # Stop movement
        self.shared['state'] = 'STOPPED'
        self.shared['movement_start_time'] = None
        self.shared['movement_command'] = None
        self.shared['m1_move_start'] = None
        self.shared['m2_move_start'] = None
        self.shared['auto_close_active'] = False
        self.shared['opening_paused'] = False

        # Stop auto-learn if active
        if self.shared.get('auto_learn_active', False):
            print("Stopping auto-learn sequence...")
            self.shared['auto_learn_active'] = False
            self.shared['auto_learn_state'] = 'IDLE'
            self.shared['learning_mode_enabled'] = False
    
    def cmd_photocell_closing(self, active):
        """Set closing photocell state"""
        self.shared['photocell_closing_active'] = active
        if active:
            print("Closing photocell ACTIVE")
        else:
            print("Closing photocell CLEARED")
    
    def cmd_photocell_opening(self, active):
        """Set opening photocell state"""
        self.shared['photocell_opening_active'] = active
        if active:
            print("Opening photocell ACTIVE")
        else:
            print("Opening photocell CLEARED")
    
    def cmd_safety_stop_closing(self, active):
        """Set stop closing safety edge state"""
        self.shared['safety_stop_closing_active'] = active
        if active:
            print("STOP CLOSING edge ACTIVE")
        else:
            print("STOP CLOSING edge CLEARED")
    
    def cmd_safety_stop_opening(self, active):
        """Set stop opening safety edge state"""
        self.shared['safety_stop_opening_active'] = active
        if active:
            print("STOP OPENING edge ACTIVE")
        else:
            print("STOP OPENING edge CLEARED")
    
    def cmd_deadman_open(self, active):
        """Set deadman open control"""
        self.shared['deadman_open_active'] = active
        if active:
            print(f"DEADMAN OPEN active - {self.deadman_speed*100:.0f}% speed")
        else:
            print("DEADMAN OPEN released")
    
    def cmd_deadman_close(self, active):
        """Set deadman close control"""
        self.shared['deadman_close_active'] = active
        if active:
            print(f"DEADMAN CLOSE active - {self.deadman_speed*100:.0f}% speed")
        else:
            print("DEADMAN CLOSE released")
    
    def cmd_timed_open(self, active):
        """Set timed open control"""
        self.shared['timed_open_active'] = active
        if active:
            print("TIMED OPEN command received")
        else:
            print("TIMED OPEN command removed")
    
    def cmd_partial_1(self, active):
        """Set partial open 1 control"""
        self.shared['partial_1_active'] = active
        if active:
            print(f"PARTIAL 1 command received ({self.partial_1_percent}%)")
            
            # Block if CLOSE command sustained
            if self.shared['cmd_close_active']:
                print("PARTIAL 1 blocked - CLOSE command sustained")
                return
            
            # Block if safety edges active
            if self.shared['safety_stop_closing_active'] or self.shared['safety_stop_opening_active']:
                print("PARTIAL 1 movement blocked - safety edge active")
                return
            
            # If at closed, partial, or closing - move to partial 1
            if self.shared['state'] == 'CLOSED' or self.shared['state'].startswith('PARTIAL') or self.shared['state'] == 'CLOSING':
                self._move_to_partial_1()
        else:
            print("PARTIAL 1 command removed")
            # If currently at partial 1, start auto-close countdown
            if self.shared['state'] == 'PARTIAL_1' and self.auto_close_enabled:
                print("Starting partial auto-close countdown")
                self.shared['partial_auto_close_active'] = True
                self.shared['partial_auto_close_countdown'] = self.partial_auto_close_time
    
    def cmd_partial_2(self, active):
        """Set partial open 2 control"""
        self.shared['partial_2_active'] = active
        if active:
            print(f"PARTIAL 2 command received ({self.partial_2_percent}%)")
            
            # Block if CLOSE command sustained
            if self.shared['cmd_close_active']:
                print("PARTIAL 2 blocked - CLOSE command sustained")
                return
            
            # Block if safety edges active
            if self.shared['safety_stop_closing_active'] or self.shared['safety_stop_opening_active']:
                print("PARTIAL 2 movement blocked - safety edge active")
                return
            
            # If at closed, partial, or closing - move to partial 2
            if self.shared['state'] == 'CLOSED' or self.shared['state'].startswith('PARTIAL') or self.shared['state'] == 'CLOSING':
                self._move_to_partial_2()
        else:
            print("PARTIAL 2 command removed")
            # Check if we need to transition to P1 or start auto-close
            if self.shared['state'] == 'PARTIAL_2':
                if self.shared['partial_1_active']:
                    # P1 still active, move to P1
                    print("Transitioning from PARTIAL_2 to PARTIAL_1")
                    self._move_to_partial_1()
                elif self.auto_close_enabled:
                    # No partial commands active, start auto-close
                    print("Starting partial auto-close countdown")
                    self.shared['partial_auto_close_active'] = True
                    self.shared['partial_auto_close_countdown'] = self.partial_auto_close_time
    
    def _move_to_partial_1(self):
        """Move M1 to partial position 1"""
        if self.shared['m1_position'] >= self.partial_1_position:
            # Already past partial 1, need to close to it
            print(f"Moving to PARTIAL_1 ({self.partial_1_percent}%)")
            # Preserve M2's movement if already closing (e.g. when PO1 pressed during CLOSING_TO_PARTIAL_1)
            preserve_m2 = (self.shared['state'] == 'CLOSING_TO_PARTIAL_1' and
                          self.shared.get('m2_move_start') is not None and
                          self.shared['m2_position'] > 0)

            self.shared['state'] = 'CLOSING_TO_PARTIAL_1'
            self.shared['movement_start_time'] = time()
            self.shared['movement_command'] = 'CLOSE'
            self.shared['m1_move_start'] = time()
            self.shared['m1_target'] = self.shared['m1_position']

            # M2 doesn't move for partials UNLESS already closing to 0
            if not preserve_m2:
                self.shared['m2_move_start'] = None

            self.shared['partial_auto_close_active'] = False
        else:
            # Below partial 1, need to open to it
            print(f"Opening to PARTIAL_1 ({self.partial_1_percent}%)")
            self.shared['state'] = 'OPENING_TO_PARTIAL_1'
            self.shared['movement_start_time'] = time()
            self.shared['movement_command'] = 'OPEN'
            self.shared['m1_move_start'] = time()
            self.shared['m1_target'] = self.shared['m1_position']
            # M2 doesn't move for partials
            self.shared['m2_move_start'] = None
            self.shared['partial_auto_close_active'] = False
    
    def _move_to_partial_2(self):
        """Move M1 to partial position 2"""
        if self.shared['m1_position'] >= self.partial_2_position:
            # Already past partial 2, need to close to it
            print(f"Moving to PARTIAL_2 ({self.partial_2_percent}%)")
            # Preserve M2's movement if already closing (e.g. when PO2 pressed during CLOSING_TO_PARTIAL_2)
            preserve_m2 = (self.shared['state'] == 'CLOSING_TO_PARTIAL_2' and
                          self.shared.get('m2_move_start') is not None and
                          self.shared['m2_position'] > 0)

            self.shared['state'] = 'CLOSING_TO_PARTIAL_2'
            self.shared['movement_start_time'] = time()
            self.shared['movement_command'] = 'CLOSE'
            self.shared['m1_move_start'] = time()
            self.shared['m1_target'] = self.shared['m1_position']

            # M2 doesn't move for partials UNLESS already closing to 0
            if not preserve_m2:
                self.shared['m2_move_start'] = None

            self.shared['partial_auto_close_active'] = False
        else:
            # Below partial 2, need to open to it
            print(f"Opening to PARTIAL_2 ({self.partial_2_percent}%)")
            self.shared['state'] = 'OPENING_TO_PARTIAL_2'
            self.shared['movement_start_time'] = time()
            self.shared['movement_command'] = 'OPEN'
            self.shared['m1_move_start'] = time()
            self.shared['m1_target'] = self.shared['m1_position']
            # M2 doesn't move for partials
            self.shared['m2_move_start'] = None
            self.shared['partial_auto_close_active'] = False
    
    def _move_to_partial_1_from_open(self):
        """Close from OPEN to PARTIAL_1 (M2 closes fully, M1 stops at PO1)"""
        print(f"Closing from OPEN to PARTIAL_1 ({self.partial_1_percent}%)")
        self.shared['state'] = 'CLOSING_TO_PARTIAL_1'
        self.shared['movement_start_time'] = time()
        self.shared['movement_command'] = 'CLOSE'
        self.shared['returning_from_full_open'] = True
        self.shared['closing_from_partial'] = 'P1'
        
        # M2 starts closing immediately (goes to 0)
        self.shared['m2_move_start'] = time()
        self.shared['m2_target'] = self.shared['m2_position']
        
        # M1 will start after delay, target is partial position
        self.shared['m1_move_start'] = None
        self.shared['m1_target'] = self.shared['m1_position']
        
        # Cancel auto-close
        self.shared['auto_close_active'] = False
        self.shared['partial_1_auto_close_active'] = False
        self.shared['partial_2_auto_close_active'] = False
    
    def _move_to_partial_2_from_open(self):
        """Close from OPEN to PARTIAL_2 (M2 closes fully, M1 stops at PO2)"""
        print(f"Closing from OPEN to PARTIAL_2 ({self.partial_2_percent}%)")
        self.shared['state'] = 'CLOSING_TO_PARTIAL_2'
        self.shared['movement_start_time'] = time()
        self.shared['movement_command'] = 'CLOSE'
        self.shared['returning_from_full_open'] = True
        self.shared['closing_from_partial'] = 'P2'
        
        # M2 starts closing immediately (goes to 0)
        self.shared['m2_move_start'] = time()
        self.shared['m2_target'] = self.shared['m2_position']
        
        # M1 will start after delay, target is partial position
        self.shared['m1_move_start'] = None
        self.shared['m1_target'] = self.shared['m1_position']
        
        # Cancel auto-close
        self.shared['auto_close_active'] = False
        self.shared['partial_1_auto_close_active'] = False
        self.shared['partial_2_auto_close_active'] = False
    
    def cmd_step_logic(self, active):
        """Step logic command - impulse based (rising edge only)"""
        # Detect rising edge
        if active and not self.shared['step_last_state']:
            # Check if blocked by sustained commands
            if (self.shared['cmd_open_active'] or self.shared['cmd_close_active'] or self.shared['cmd_stop_active'] or
                self.shared['deadman_open_active'] or self.shared['deadman_close_active'] or
                self.shared['safety_stop_closing_active'] or self.shared['safety_stop_opening_active'] or
                self.shared['timed_open_active']):
                print("STEP command blocked - sustained command active")
                self.shared['step_last_state'] = active
                return
            
            # Impulse detected
            print(f"\n>>> STEP command (mode: {self.step_logic_mode}step) - State: {self.shared['state']}")
            
            if self.step_logic_mode == 2:
                self._step_2()
            elif self.step_logic_mode == 3:
                self._step_3()
            elif self.step_logic_mode == 4:
                self._step_4()
        
        self.shared['step_last_state'] = active
    
    def _step_2(self):
        """2-step logic"""
        if self.shared['state'] == 'CLOSED':
            self.cmd_open()
        elif self.shared['state'] == 'OPEN':
            self.cmd_close()
        elif self.shared['state'] == 'CLOSING':
            self.cmd_open()  # Reverse
        elif self.shared['state'] == 'OPENING':
            self.cmd_close()  # Reverse
    
    def _step_3(self):
        """3-step logic"""
        if self.shared['state'] == 'CLOSED':
            self.cmd_open()
        elif self.shared['state'] == 'OPEN':
            self.cmd_close()
        elif self.shared['state'] == 'OPENING':
            self.cmd_stop()
        elif self.shared['state'] == 'STOPPED':
            # After stop while opening -> close
            if self.shared['stopped_after_opening']:
                self.cmd_close()
            # After stop while closing -> open
            elif self.shared['stopped_after_closing']:
                self.cmd_open()
            else:
                # Unknown stop state, try closing
                self.cmd_close()
        elif self.shared['state'] == 'CLOSING':
            self.cmd_open()  # Reverse
    
    def _step_4(self):
        """4-step logic"""
        if self.shared['state'] == 'CLOSED':
            self.cmd_open()
        elif self.shared['state'] == 'OPEN':
            self.cmd_close()
        elif self.shared['state'] == 'CLOSING':
            self.cmd_stop()
            self.shared['stopped_after_closing'] = True
            self.shared['stopped_after_opening'] = False
        elif self.shared['state'] == 'OPENING':
            self.cmd_stop()
            self.shared['stopped_after_opening'] = True
            self.shared['stopped_after_closing'] = False
        elif self.shared['state'] == 'STOPPED':
            if self.shared['stopped_after_closing']:
                self.cmd_open()
            elif self.shared['stopped_after_opening']:
                self.cmd_close()
            else:
                # Default to opening if unknown
                self.cmd_open()
    
    def enable_learning_mode(self):
        """Enable learning mode to record motor travel times"""
        self.shared['learning_mode_enabled'] = True
        print("Learning mode ENABLED - motor travel times will be recorded")

    def disable_learning_mode(self):
        """Disable learning mode"""
        self.shared['learning_mode_enabled'] = False
        print("Learning mode DISABLED")

    def save_learned_times(self, config_file='/home/doowkcol/Gatetorio_Code/gate_config.json'):
        """Save learned motor run times to config file"""
        try:
            # Get learned times from shared memory
            m1_open_time = self.shared.get('learning_m1_open_time')
            m1_close_time = self.shared.get('learning_m1_close_time')
            m2_open_time = self.shared.get('learning_m2_open_time')
            m2_close_time = self.shared.get('learning_m2_close_time')

            # Average open and close times for each motor
            m1_learned = None
            if m1_open_time and m1_close_time:
                m1_learned = (m1_open_time + m1_close_time) / 2.0
            elif m1_open_time:
                m1_learned = m1_open_time
            elif m1_close_time:
                m1_learned = m1_close_time

            m2_learned = None
            if m2_open_time and m2_close_time:
                m2_learned = (m2_open_time + m2_close_time) / 2.0
            elif m2_open_time:
                m2_learned = m2_open_time
            elif m2_close_time:
                m2_learned = m2_close_time

            if not m1_learned and not m2_learned:
                print("No learned times to save - complete a full open/close cycle first")
                return False

            # Load current config
            with open(config_file, 'r') as f:
                config = json.load(f)

            # Update learned times
            if m1_learned:
                config['motor1_learned_run_time'] = m1_learned
                print(f"Learned M1 run time: {m1_learned:.2f}s")

            if m2_learned:
                config['motor2_learned_run_time'] = m2_learned
                print(f"Learned M2 run time: {m2_learned:.2f}s")

            # Save config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)

            print("Learned times saved to config - reload config to apply")
            return True

        except Exception as e:
            print(f"Error saving learned times: {e}")
            return False

    def get_learning_status(self):
        """Get current learning mode status and recorded times"""
        return {
            'learning_mode_enabled': self.shared.get('learning_mode_enabled', False),
            'm1_open_time': self.shared.get('learning_m1_open_time'),
            'm1_close_time': self.shared.get('learning_m1_close_time'),
            'm2_open_time': self.shared.get('learning_m2_open_time'),
            'm2_close_time': self.shared.get('learning_m2_close_time')
        }

    def start_auto_learn(self):
        """Start the automated learning sequence - motor_manager handles the actual learning"""
        if not self.shared.get('engineer_mode_enabled', False):
            print("ERROR: Engineer mode must be enabled to start auto-learn")
            return False

        if self.shared['auto_learn_active']:
            print("Auto-learn already running")
            return False

        # Check that limit switches are enabled
        if not self.motor1_use_limit_switches or not self.motor2_use_limit_switches:
            print("ERROR: Auto-learn requires limit switches to be enabled for both motors")
            print("Please enable M1 and M2 limit switches in the learning configuration")
            self.shared['auto_learn_status_msg'] = 'Error: Limit switches not enabled'
            return False

        # Stop any current movement
        self.cmd_stop()

        # Clear previous learning data
        self.shared['learning_m1_open_time'] = None
        self.shared['learning_m1_close_time'] = None
        self.shared['learning_m2_open_time'] = None
        self.shared['learning_m2_close_time'] = None

        # Signal motor_manager to start auto-learn
        # Motor manager will handle the entire sequence
        self.shared['auto_learn_active'] = True
        self.shared['auto_learn_status_msg'] = 'Starting auto-learn sequence...'

        print("=== AUTO-LEARN STARTED ===")
        print("Motor manager will handle the learning sequence")

        return True

    def stop_auto_learn(self):
        """Stop the automated learning sequence"""
        if not self.shared['auto_learn_active']:
            return False

        print("=== AUTO-LEARN STOPPED ===")
        self.shared['auto_learn_active'] = False
        self.shared['auto_learn_status_msg'] = 'Stopped by user'

        return True

    def get_auto_learn_status(self):
        """Get current auto-learn status"""
        return {
            'active': self.shared.get('auto_learn_active', False),
            'state': self.shared.get('auto_learn_state', 'IDLE'),
            'cycle': self.shared.get('auto_learn_cycle', 0),
            'status_msg': self.shared.get('auto_learn_status_msg', 'Ready'),
            'm1_times': list(self.shared.get('auto_learn_m1_times', [])),
            'm2_times': list(self.shared.get('auto_learn_m2_times', []))
        }

    def get_status(self):
        """Get current status"""
        avg_pos = (self.shared['m1_position'] + self.shared['m2_position']) / 2
        
        return {
            'state': self.shared['state'],
            'position': avg_pos,
            'total_time': self.run_time,
            'position_percent': (avg_pos / self.run_time) * 100,
            'm1_percent': (self.shared['m1_position'] / self.run_time) * 100,
            'm2_percent': (self.shared['m2_position'] / self.run_time) * 100,
            'm1_speed': self.shared['m1_speed'] * 100,  # Convert to percentage
            'm2_speed': self.shared['m2_speed'] * 100,  # Convert to percentage
            'auto_close_active': self.shared['auto_close_active'],
            'auto_close_countdown': self.shared['auto_close_countdown'],
            # Separate partial timers
            'partial_1_auto_close_active': self.shared['partial_1_auto_close_active'],
            'partial_1_auto_close_countdown': self.shared['partial_1_auto_close_countdown'],
            'partial_2_auto_close_active': self.shared['partial_2_auto_close_active'],
            'partial_2_auto_close_countdown': self.shared['partial_2_auto_close_countdown']
        }
    
    def cleanup(self):
        """Clean up processes"""
        print("Shutting down gate controller...")
        self.shared['running'] = False
        
        # Wait for motor process to stop
        if self.motor_process.is_alive():
            self.motor_process.join(timeout=1.0)
            if self.motor_process.is_alive():
                print("Warning: Motor process did not stop gracefully")
                self.motor_process.terminate()
        
        # Wait for input process to stop
        if self.input_process.is_alive():
            self.input_process.join(timeout=1.0)
            if self.input_process.is_alive():
                print("Warning: Input process did not stop gracefully")
                self.input_process.terminate()
        
        print("Gate controller shutdown complete")
