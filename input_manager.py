#!/usr/bin/env python3
"""
Input Manager Process - Handles ADC reading and input state tracking
Runs as separate process, updates shared memory
"""

import time
import json
from collections import deque

# Don't import board/busio at module level - only when actually needed
# This prevents GPIO chip from being claimed when module is imported
ADC_AVAILABLE = False
board = None
busio = None
ADS = None
AnalogIn = None

def check_adc_hardware():
    """Check if ADC hardware libraries are available and working"""
    global ADC_AVAILABLE, board, busio, ADS, AnalogIn
    
    try:
        import board as _board
        import busio as _busio
        import adafruit_ads1x15.ads1115 as _ADS
        from adafruit_ads1x15.analog_in import AnalogIn as _AnalogIn
        from adafruit_ads1x15.ads1x15 import Pin
        
        # Test if channel attributes exist (A0, A1, A2, A3)
        if not hasattr(Pin, 'A0'):
            return False
            
        board = _board
        busio = _busio
        ADS = _ADS
        AnalogIn = _AnalogIn
        ADC_AVAILABLE = True
        return True
    except (ImportError, AttributeError) as e:
        return False


class InputManager:
    def __init__(self, shared_dict, config):
        """Initialize input manager

        Args:
            shared_dict: Multiprocessing shared dictionary
            config: Configuration dict with:
                - num_inputs: Number of analog inputs (8 for dual ADS1115)
                - input_sample_rate: Sampling rate in seconds (default 0.005 = 200Hz for fast safety-critical response)
        """
        self.shared = shared_dict
        self.config = config
        self.num_inputs = config.get('num_inputs', 8)
        self.sample_rate = config.get('input_sample_rate', 0.005)  # 200Hz default for fast safety-critical inputs

        # Initialize ADCs if available
        self.adc1 = None  # First ADC at 0x48 (ADDR->GND, default)
        self.adc2 = None  # Second ADC at 0x49 (ADDR->VDD)
        self.analog_inputs = []

        # Check if ADC hardware is actually available and working
        self.adc_available = check_adc_hardware()

        # ONLY try to initialize I2C/ADC if hardware check passed
        if self.adc_available:
            try:
                from adafruit_ads1x15.ads1x15 import Pin

                i2c = busio.I2C(board.SCL, board.SDA)

                # Initialize first ADC at default address 0x48 (ADDR->GND)
                try:
                    self.adc1 = ADS.ADS1115(i2c, address=0x48)
                    print("Input Manager: ADC1 initialized at address 0x48 (ADDR->GND)")
                except Exception as e:
                    print(f"Input Manager: Failed to initialize ADC1 at 0x48: {e}")

                # Initialize second ADC at address 0x49 (ADDR->VDD)
                try:
                    self.adc2 = ADS.ADS1115(i2c, address=0x49)
                    print("Input Manager: ADC2 initialized at address 0x49 (ADDR->VDD)")
                except Exception as e:
                    print(f"Input Manager: Failed to initialize ADC2 at 0x49: {e}")

                # Create analog input objects for all 8 channels
                # Channels 0-3: ADC1 (address 0x48)
                # Channels 4-7: ADC2 (address 0x49)
                if self.adc1:
                    self.analog_inputs.extend([
                        AnalogIn(self.adc1, Pin.A0),  # Channel 0
                        AnalogIn(self.adc1, Pin.A1),  # Channel 1
                        AnalogIn(self.adc1, Pin.A2),  # Channel 2
                        AnalogIn(self.adc1, Pin.A3)   # Channel 3
                    ])
                else:
                    # Add None placeholders if ADC1 failed
                    self.analog_inputs.extend([None, None, None, None])

                if self.adc2:
                    self.analog_inputs.extend([
                        AnalogIn(self.adc2, Pin.A0),  # Channel 4
                        AnalogIn(self.adc2, Pin.A1),  # Channel 5
                        AnalogIn(self.adc2, Pin.A2),  # Channel 6
                        AnalogIn(self.adc2, Pin.A3)   # Channel 7
                    ])
                else:
                    # Add None placeholders if ADC2 failed
                    self.analog_inputs.extend([None, None, None, None])

                adc_count = (1 if self.adc1 else 0) + (1 if self.adc2 else 0)
                print(f"Input Manager: {adc_count} ADC(s) initialized successfully ({len([a for a in self.analog_inputs if a is not None])} channels available)")

            except Exception as e:
                print(f"Input Manager: Failed to initialize ADC system: {e}")
                print("Running in simulation mode")
                self.adc_available = False
        else:
            print("Input Manager: ADC hardware not available, running in simulation mode")

        # Load input configuration
        self.input_config = self._load_input_config()

        # Initialize shared memory for input states
        self._init_shared_inputs()

        # Resistance history for trending (used for 8.2k detection over time)
        # Store last 10 samples per input for stability checks
        self.resistance_history = {}
        for input_name in self.input_config.keys():
            self.resistance_history[input_name] = deque(maxlen=10)

        # Safety input deactivation tracking - requires 1 second of continuous
        # inactive signal before deactivating (prevents cycling on sustained commands)
        self.safety_deactivation_times = {}
        for input_name in self.input_config.keys():
            self.safety_deactivation_times[input_name] = None

        print(f"Input Manager initialized:")
        print(f"  Inputs configured: {len(self.input_config)}")
        print(f"  Sample rate: {self.sample_rate}s ({1.0/self.sample_rate:.1f}Hz)")
        print(f"  ADC available: {self.adc_available}")
        print(f"  Channels available: {len([a for a in self.analog_inputs if a is not None])}")
    
    def _load_input_config(self):
        """Load input configuration from JSON file"""
        try:
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'r') as f:
                config = json.load(f)
            return config['inputs']
        except Exception as e:
            print(f"Warning: Failed to load input config: {e}")
            # Return default configuration - DISABLED in simulation mode
            # These should be configured properly before enabling
            return {
                'CMD_OPEN': {'channel': 0, 'type': 'NC', 'function': None},
                'CMD_CLOSE': {'channel': 1, 'type': 'NC', 'function': None},
                'CMD_STOP': {'channel': 2, 'type': 'NC', 'function': None},
                'PHOTOCELL_CLOSE': {'channel': 3, 'type': 'NO', 'function': None}
            }

    def _reload_input_config(self):
        """Reload input configuration from file - hot reload for quick testing"""
        print("Reloading input configuration...")

        try:
            # Load new config
            new_config = self._load_input_config()

            # Update input_config
            self.input_config = new_config

            # Reinitialize shared memory for any new inputs
            self._init_shared_inputs()

            # Reset safety deactivation timers for new inputs
            self.safety_deactivation_times = {}
            for input_name in self.input_config.keys():
                self.safety_deactivation_times[input_name] = None

            # Reset resistance history for new inputs
            self.resistance_history = {}
            for input_name in self.input_config.keys():
                self.resistance_history[input_name] = deque(maxlen=10)

            print("================================================================================")
            print(f"INPUT CONFIG RELOADED ({len(self.input_config)} inputs):")
            print("================================================================================")
            for input_name, cfg in self.input_config.items():
                enabled_str = "[ENABLED]" if cfg.get('enabled', True) else "[DISABLED]"
                func_str = cfg.get('function', 'None')
                type_str = cfg.get('type', 'NO')
                ch_str = cfg.get('channel', '?')
                print(f"  {input_name:20s} Ch={ch_str:2} Type={type_str:3s} Func={func_str:25s} {enabled_str}")
            print("================================================================================")

        except Exception as e:
            print(f"Error reloading input config: {e}")

    def _init_shared_inputs(self):
        """Initialize shared memory for all configured inputs"""
        for input_name, input_cfg in self.input_config.items():
            # State (True = active, False = inactive)
            self.shared[f'{input_name}_state'] = False
            
            # Raw values
            self.shared[f'{input_name}_voltage'] = 0.0
            self.shared[f'{input_name}_resistance'] = None
            
            # Timestamps
            self.shared[f'{input_name}_last_change'] = time.time()
            self.shared[f'{input_name}_active_duration'] = 0.0
        
        # Input manager heartbeat
        self.shared['input_manager_heartbeat'] = time.time()
    
    def run(self):
        """Main input manager loop - runs continuously"""
        print("Input Manager: Starting main loop")

        # Diagnostic: Show all configured inputs
        print(f"\n{'='*80}")
        print(f"CONFIGURED INPUTS ({len(self.input_config)} total):")
        print(f"{'='*80}")
        for input_name, cfg in self.input_config.items():
            enabled = cfg.get('enabled', True)
            function = cfg.get('function', None)
            function_str = str(function) if function else 'None'
            channel = cfg.get('channel', '?')
            input_type = cfg.get('type', 'NO')
            status = "ENABLED" if enabled else "DISABLED"
            print(f"  {input_name:20s} Ch={channel:2} Type={input_type:3s} Func={function_str:20s} [{status}]")
        print(f"{'='*80}\n")

        last_sample = time.time()

        # Track consecutive samples for debouncing ALL inputs
        # Prevents toggling on marginal/noisy signals - requires multiple consecutive
        # samples to change state (both activation and deactivation)
        consecutive_active = {}
        consecutive_inactive = {}
        for input_name in self.input_config.keys():
            consecutive_active[input_name] = 0
            consecutive_inactive[input_name] = 0

        while self.shared.get('running', True):
            now = time.time()

            # Update heartbeat
            self.shared['input_manager_heartbeat'] = now

            # Check for input config reload signal
            if self.shared.get('input_config_reload_flag', False):
                self._reload_input_config()
                self.shared['input_config_reload_flag'] = False
                # Reset debouncing state after reload
                for input_name in self.input_config.keys():
                    consecutive_active[input_name] = 0
                    consecutive_inactive[input_name] = 0

            # Sample all inputs at configured rate (default 0.005s = 200Hz for fast safety-critical response)
            # Much faster than previous 0.1s = 10Hz to prevent race conditions with controller
            if (now - last_sample) >= self.sample_rate:
                self._sample_all_inputs(consecutive_active, consecutive_inactive)
                last_sample = now

            # Sleep briefly to avoid CPU hammering (but much less than sample rate)
            time.sleep(0.002)  # 2ms sleep, allows up to 500Hz sampling if configured

        print("Input Manager: Shutting down")
    
    def _sample_all_inputs(self, consecutive_active, consecutive_inactive):
        """Sample all configured inputs and update shared memory with universal debouncing

        Args:
            consecutive_active: Dict tracking consecutive active samples per input
            consecutive_inactive: Dict tracking consecutive inactive samples per input

        All inputs use debouncing to prevent state changes from noise/glitches.
        Requires multiple consecutive samples in the new state before changing.
        Safety inputs use more aggressive debouncing than command inputs.

        THREE-PHASE PROCESSING:
        Phase 1: Sample ALL inputs and determine their debounced states (collect in dict)
        Phase 2: Apply conflict blocking (safety edges block conflicting commands)
        Phase 3: Update shared memory flags with conflict-resolved states
        This prevents flickering inputs from creating conflicting command states.
        """
        now = time.time()

        # PHASE 1: Sample all inputs and collect their NEW states (don't set flags yet)
        new_states = {}  # function -> is_active

        for input_name, input_cfg in self.input_config.items():
            is_active = self._determine_input_state(input_name, input_cfg, consecutive_active,
                                                    consecutive_inactive, now)
            function = input_cfg.get('function')
            if function:
                new_states[function] = is_active

        # PHASE 2: Apply conflict blocking BEFORE setting any flags
        # If safety edges are active, block conflicting commands
        if new_states.get('safety_stop_opening', False):
            # Block all opening commands
            for cmd in ['cmd_open', 'timed_open', 'partial_1', 'partial_2']:
                if new_states.get(cmd, False):
                    if not hasattr(self, '_last_blocked_open') or (now - self._last_blocked_open) > 0.5:
                        print(f"[INPUT BLOCKED] {cmd:20s} blocked by active safety_stop_opening")
                        self._last_blocked_open = now
                    new_states[cmd] = False  # Block it

        if new_states.get('safety_stop_closing', False):
            # Block all closing commands
            if new_states.get('cmd_close', False):
                if not hasattr(self, '_last_blocked_close') or (now - self._last_blocked_close) > 0.5:
                    print(f"[INPUT BLOCKED] cmd_close blocked by active safety_stop_closing")
                    self._last_blocked_close = now
                new_states['cmd_close'] = False  # Block it

        # Conflicting command resolution: open + close = stop
        if new_states.get('cmd_open', False) and new_states.get('cmd_close', False):
            if not hasattr(self, '_last_blocked_open_close') or (now - self._last_blocked_open_close) > 0.5:
                print(f"[INPUT BLOCKED] cmd_open + cmd_close conflict → activating cmd_stop")
                self._last_blocked_open_close = now
            new_states['cmd_open'] = False
            new_states['cmd_close'] = False
            new_states['cmd_stop'] = True

        # Conflicting command resolution: partial_1 + partial_2 = partial_2 (partial_2 wins)
        if new_states.get('partial_1', False) and new_states.get('partial_2', False):
            if not hasattr(self, '_last_blocked_partial') or (now - self._last_blocked_partial) > 0.5:
                print(f"[INPUT BLOCKED] partial_1 + partial_2 conflict → partial_2 takes priority")
                self._last_blocked_partial = now
            new_states['partial_1'] = False  # Block partial_1, keep partial_2

        # Conflicting command resolution: both safety edges active = stop
        if new_states.get('safety_stop_opening', False) and new_states.get('safety_stop_closing', False):
            if not hasattr(self, '_last_blocked_both_safety') or (now - self._last_blocked_both_safety) > 0.5:
                print(f"[INPUT BLOCKED] safety_stop_opening + safety_stop_closing conflict → activating cmd_stop")
                self._last_blocked_both_safety = now
            new_states['safety_stop_opening'] = False
            new_states['safety_stop_closing'] = False
            new_states['cmd_stop'] = True

        # Conflicting command resolution: cmd_stop + anything (except safety limits) = stop
        if new_states.get('cmd_stop', False):
            # Block all movement commands when stop is active (safety limits can remain)
            blocked_commands = []
            for cmd in ['cmd_open', 'cmd_close', 'timed_open', 'partial_1', 'partial_2']:
                if new_states.get(cmd, False):
                    new_states[cmd] = False
                    blocked_commands.append(cmd)

            if blocked_commands:
                if not hasattr(self, '_last_blocked_by_stop') or (now - self._last_blocked_by_stop) > 0.5:
                    print(f"[INPUT BLOCKED] {', '.join(blocked_commands)} blocked by active cmd_stop")
                    self._last_blocked_by_stop = now

        # PHASE 3: Update shared memory with conflict-resolved states
        for input_name, input_cfg in self.input_config.items():
            function = input_cfg.get('function')
            if function and function in new_states:
                is_active = new_states[function]
                self._trigger_command(function, is_active)

    def _determine_input_state(self, input_name, input_cfg, consecutive_active,
                                consecutive_inactive, now):
        """Determine the debounced state of a single input WITHOUT setting shared memory

        Returns:
            bool: True if input is active (after debouncing), False otherwise
        """
        # Skip disabled inputs
        if not input_cfg.get('enabled', True):
            return False

        channel = input_cfg['channel']
        input_type = input_cfg.get('type', 'NO')  # NO or NC or 8K2

        # Read ADC value
        if self.adc_available and channel < len(self.analog_inputs) and self.analog_inputs[channel] is not None:
            voltage = self.analog_inputs[channel].voltage
            value = self.analog_inputs[channel].value
        else:
            # Simulation mode - read from shared dict if UI set it
            voltage = self.shared.get(f'{input_name}_sim_voltage', 0.0)
            value = int((voltage / 3.3) * 32767)  # Simulate 15-bit ADC

        # Calculate resistance if pullup present
        resistance = self._calculate_resistance(voltage, pullup_ohms=10000, vcc=3.3)

        # Get learned resistance parameters if configured
        learned_resistance = input_cfg.get('learned_resistance', None)
        tolerance_percent = input_cfg.get('tolerance_percent', None)

        # Determine raw active state based on type
        was_active = self.shared[f'{input_name}_state']
        is_active_raw = self._determine_active_state(voltage, resistance, input_type,
                                                learned_resistance, tolerance_percent)

        # Debug: Show voltage changes for enabled inputs with functions
        function = input_cfg.get('function')
        if function:
            # Track previous voltage to detect changes
            if not hasattr(self, '_voltage_monitor'):
                self._voltage_monitor = {}

            prev_voltage = self._voltage_monitor.get(input_name, voltage)
            voltage_change = abs(voltage - prev_voltage)

            # Show significant voltage changes (> 0.5V)
            if voltage_change > 0.5:
                print(f"[INPUT VOLTAGE] {input_name:20s} V={prev_voltage:.2f}→{voltage:.2f} (Δ{voltage_change:.2f}V)")
                self._voltage_monitor[input_name] = voltage

            # Show raw state changes (before debouncing)
            if is_active_raw != was_active:
                print(f"[INPUT RAW] {input_name:20s} func={function:20s} raw={'ACTIVE' if is_active_raw else 'inactive'} was={'ACTIVE' if was_active else 'inactive'} V={voltage:.2f}")

        # UNIVERSAL DEBOUNCING: All inputs require multiple consecutive samples to change state
        # This prevents race conditions with faster control loop and filters electrical noise
        # Safety inputs need more samples (more conservative) than command inputs
        function = input_cfg.get('function')
        safety_functions = ['photocell_closing', 'photocell_opening',
                          'safety_stop_closing', 'safety_stop_opening']

        if function in safety_functions:
            # Safety inputs: Immediate activation, 3-sample deactivation (15ms @ 200Hz)
            activate_samples = 1
            deactivate_samples = 3
        else:
            # Command inputs: 1-sample activation, 2-sample deactivation (5ms/10ms @ 200Hz)
            # Fast activation for responsive button presses, slower deactivation filters bounce
            activate_samples = 1
            deactivate_samples = 2

        # Debouncing state machine
        if is_active_raw:
            # Raw signal is active
            consecutive_inactive[input_name] = 0
            consecutive_active[input_name] += 1

            # Clear safety deactivation timer since we're active again
            if function in safety_functions:
                self.safety_deactivation_times[input_name] = None

            if was_active:
                # Already active, stay active
                is_active = True
            else:
                # Was inactive, check if enough consecutive samples to activate
                if consecutive_active[input_name] >= activate_samples:
                    is_active = True  # Activate now
                else:
                    is_active = False  # Still debouncing, stay inactive
        else:
            # Raw signal is inactive
            consecutive_active[input_name] = 0
            consecutive_inactive[input_name] += 1

            if not was_active:
                # Already inactive, stay inactive
                is_active = False
                # Ensure deactivation timer is cleared when already inactive
                if function in safety_functions:
                    self.safety_deactivation_times[input_name] = None
            else:
                # Was active, check if enough consecutive samples to deactivate
                # SAFETY INPUTS: Require 1 second of continuous inactivity before deactivating
                # This prevents cycling when both OPEN and SAFETY_STOP_OPENING are sustained
                if function in safety_functions:
                    # Start tracking deactivation time if not already tracking
                    if self.safety_deactivation_times[input_name] is None:
                        self.safety_deactivation_times[input_name] = now
                        print(f"[SAFETY DEACTIVATION] {input_name:20s} - starting 1.0s hold-off timer")

                    # Check if we've been inactive for 1+ second
                    time_inactive = now - self.safety_deactivation_times[input_name]
                    if time_inactive >= 1.0:
                        # 1 second has passed - allow deactivation
                        is_active = False
                        self.safety_deactivation_times[input_name] = None  # Clear timer
                        print(f"[SAFETY DEACTIVATION] {input_name:20s} - 1.0s elapsed, deactivating")
                    else:
                        # Still within 1 second - stay active
                        is_active = True
                        # Optional debug: show countdown (throttled to avoid spam)
                        if not hasattr(self, '_last_safety_debug') or (now - self._last_safety_debug) > 0.2:
                            print(f"[SAFETY DEACTIVATION] {input_name:20s} - holding for {1.0 - time_inactive:.2f}s more")
                            self._last_safety_debug = now
                else:
                    # Non-safety inputs: Use standard debouncing
                    if consecutive_inactive[input_name] >= deactivate_samples:
                        is_active = False  # Deactivate now
                    else:
                        is_active = True  # Still debouncing, stay active (latch-on)

        # Update voltage/resistance in shared memory (diagnostics only, not used for decisions)
        self.shared[f'{input_name}_voltage'] = voltage
        self.shared[f'{input_name}_resistance'] = resistance

        # Store resistance in history for trending
        if resistance is not None:
            self.resistance_history[input_name].append({
                'timestamp': now,
                'resistance': resistance
            })

        # Update shared memory state (will be overwritten by conflict-resolved value later)
        self.shared[f'{input_name}_state'] = is_active

        # Track state changes for logging/timestamps
        if is_active != was_active:
            self.shared[f'{input_name}_last_change'] = now
            # Debug: Show debounced state changes
            if function:
                print(f"[INPUT DEBOUNCED] {input_name:20s} func={function:20s} → {'ACTIVE' if is_active else 'inactive'}")

        # Update active duration
        if is_active:
            last_change = self.shared[f'{input_name}_last_change']
            self.shared[f'{input_name}_active_duration'] = now - last_change
        else:
            self.shared[f'{input_name}_active_duration'] = 0.0

        # Return the debounced state (before conflict resolution)
        return is_active
    
    def _calculate_resistance(self, voltage, pullup_ohms=10000, vcc=3.3):
        """Calculate resistance from voltage divider
        
        Assumes: VCC -- pullup -- [voltage measured here] -- unknown_R -- GND
        
        Returns resistance in ohms, or None if calculation invalid
        """
        if voltage <= 0.01:  # Near ground = short circuit
            return 0.0
        elif voltage >= (vcc - 0.01):  # Near VCC = open circuit
            return float('inf')
        else:
            # Voltage divider: V_measured = VCC * (R_unknown / (R_pullup + R_unknown))
            # Solve for R_unknown: R_unknown = (V_measured * R_pullup) / (VCC - V_measured)
            try:
                resistance = (voltage * pullup_ohms) / (vcc - voltage)
                return resistance
            except ZeroDivisionError:
                return float('inf')
    
    def _determine_active_state(self, voltage, resistance, input_type, learned_resistance=None, tolerance_percent=None):
        """Determine if input is active based on type
        
        Args:
            voltage: Measured voltage (0-3.3V)
            resistance: Calculated resistance (ohms)
            input_type: 'NO', 'NC', or '8K2'
            learned_resistance: Learned resistance value (ohms) for 8K2 inputs
            tolerance_percent: Tolerance percentage for learned resistance
        
        Returns:
            True if input is active, False otherwise
        """
        if input_type == 'NO':
            # Normally Open: Active when voltage HIGH (contact closed)
            # Threshold: > 2.0V = active
            return voltage > 2.0
        
        elif input_type == 'NC':
            # Normally Closed: Active when voltage LOW (contact open)
            # Threshold: < 1.0V = active (contact opened, pulled to ground)
            return voltage < 1.0
        
        elif input_type == '8K2':
            # 8.2kΩ safety resistor: INACTIVE when resistance in range, ACTIVE when out of range
            # This is inverted from NO/NC logic:
            # - Normal state (safe): resistance matches learned value within tolerance
            # - Active state (fault/trigger): resistance outside tolerance, short, or open
            
            # If learned resistance is configured, use it with tolerance
            if learned_resistance is not None and tolerance_percent is not None:
                if resistance is None or resistance == float('inf'):
                    return True  # Open circuit = ACTIVE (fault)
                
                if resistance == 0.0:
                    return True  # Short circuit = ACTIVE (fault)
                
                # Calculate acceptable range based on learned value and tolerance
                tolerance_factor = tolerance_percent / 100.0
                min_resistance = learned_resistance * (1.0 - tolerance_factor)
                max_resistance = learned_resistance * (1.0 + tolerance_factor)
                
                # INACTIVE if within tolerance range (normal/safe)
                # ACTIVE if outside tolerance range (fault/triggered)
                if min_resistance <= resistance <= max_resistance:
                    return False  # Within range = INACTIVE (safe/normal)
                else:
                    return True  # Outside range = ACTIVE (fault/triggered)
            
            else:
                # Use default hardcoded range (inverted logic)
                # Typical: 7.5kΩ - 9.0kΩ = inactive (safety device OK)
                # < 7.5kΩ = active (short circuit fault)
                # > 9.0kΩ = active (open circuit fault)
                if resistance is None or resistance == float('inf'):
                    return True  # Open circuit = ACTIVE (fault)
                elif resistance == 0.0:
                    return True  # Short circuit = ACTIVE (fault)
                elif 7500 <= resistance <= 9000:
                    return False  # In range = INACTIVE (OK)
                else:
                    return True  # Out of range = ACTIVE (fault)
        
        else:
            # Unknown type, default to NO behavior
            return voltage > 2.0
    
    def _trigger_command(self, function, active):
        """Trigger gate controller command function

        Maps input function names to shared memory command flags
        NOTE: Conflict blocking is now handled in _sample_all_inputs() Phase 2
        """
        # Map function names to shared dict flags
        command_map = {
            'cmd_open': 'cmd_open_active',
            'cmd_close': 'cmd_close_active',
            'cmd_stop': 'cmd_stop_active',
            'photocell_closing': 'photocell_closing_active',
            'photocell_opening': 'photocell_opening_active',
            'safety_stop_closing': 'safety_stop_closing_active',
            'safety_stop_opening': 'safety_stop_opening_active',
            'deadman_open': 'deadman_open_active',
            'deadman_close': 'deadman_close_active',
            'timed_open': 'timed_open_active',
            'partial_1': 'partial_1_active',
            'partial_2': 'partial_2_active',
            'step_logic': 'step_command_active',
            # Limit switches for Motor 1 and Motor 2
            'open_limit_m1': 'open_limit_m1_active',
            'close_limit_m1': 'close_limit_m1_active',
            'open_limit_m2': 'open_limit_m2_active',
            'close_limit_m2': 'close_limit_m2_active'
        }

        # Update shared memory flag (already conflict-resolved in Phase 2)
        flag_name = command_map.get(function)
        if flag_name:
            # Track previous state to detect transitions
            if not hasattr(self, '_command_states'):
                self._command_states = {}

            previous_state = self._command_states.get(function, None)
            self.shared[flag_name] = active
            self._command_states[function] = active

            # Debug: Show state transitions for command inputs (not limit switches or every cycle)
            # This helps diagnose if switches are being ignored
            command_inputs = ['cmd_open', 'cmd_close', 'cmd_stop', 'partial_1', 'partial_2',
                            'timed_open', 'step_logic', 'deadman_open', 'deadman_close',
                            'safety_stop_opening', 'safety_stop_closing']

            if function in command_inputs:
                # Only print when state changes (transitions)
                if previous_state is not None and previous_state != active:
                    state_str = "ACTIVE" if active else "inactive"
                    print(f"[INPUT] {function:20s} → {state_str}")
                elif previous_state is None and active:
                    # First time seeing this command and it's active
                    print(f"[INPUT] {function:20s} → ACTIVE (first activation)")



def input_manager_process(shared_dict, config):
    """Entry point for input manager process"""
    manager = InputManager(shared_dict, config)
    manager.run()
