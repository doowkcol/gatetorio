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
                - input_sample_rate: Sampling rate in seconds (default 0.01 = 100Hz for safety-critical response)
        """
        self.shared = shared_dict
        self.config = config
        self.num_inputs = config.get('num_inputs', 8)
        self.sample_rate = config.get('input_sample_rate', 0.01)  # 100Hz default for safety-critical inputs

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

            # Sample all inputs at configured rate (default 0.01s = 100Hz for safety-critical response)
            # Much faster than previous 0.1s = 10Hz to prevent race conditions with controller
            if (now - last_sample) >= self.sample_rate:
                self._sample_all_inputs(consecutive_active, consecutive_inactive)
                last_sample = now

            # Sleep briefly to avoid CPU hammering (but much less than sample rate)
            time.sleep(0.005)  # 5ms sleep, allows up to 200Hz sampling if configured

        print("Input Manager: Shutting down")
    
    def _sample_all_inputs(self, consecutive_active, consecutive_inactive):
        """Sample all configured inputs and update shared memory with universal debouncing

        Args:
            consecutive_active: Dict tracking consecutive active samples per input
            consecutive_inactive: Dict tracking consecutive inactive samples per input

        All inputs use debouncing to prevent state changes from noise/glitches.
        Requires multiple consecutive samples in the new state before changing.
        Safety inputs use more aggressive debouncing than command inputs.
        """
        now = time.time()

        for input_name, input_cfg in self.input_config.items():
            # Skip disabled inputs
            if not input_cfg.get('enabled', True):
                continue

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

            # UNIVERSAL DEBOUNCING: All inputs require multiple consecutive samples to change state
            # This prevents race conditions with faster control loop and filters electrical noise
            # Safety inputs need more samples (more conservative) than command inputs
            function = input_cfg.get('function')
            safety_functions = ['photocell_closing', 'photocell_opening',
                              'safety_stop_closing', 'safety_stop_opening']

            if function in safety_functions:
                # Safety inputs: Immediate activation, 3-sample deactivation (30ms @ 100Hz)
                activate_samples = 1
                deactivate_samples = 3
            else:
                # Command inputs: 2-sample activation, 2-sample deactivation (20ms @ 100Hz)
                activate_samples = 2
                deactivate_samples = 2

            # Debouncing state machine
            if is_active_raw:
                # Raw signal is active
                consecutive_inactive[input_name] = 0
                consecutive_active[input_name] += 1

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
                else:
                    # Was active, check if enough consecutive samples to deactivate
                    if consecutive_inactive[input_name] >= deactivate_samples:
                        is_active = False  # Deactivate now
                    else:
                        is_active = True  # Still debouncing, stay active (latch-on)

            # Update shared memory
            self.shared[f'{input_name}_voltage'] = voltage
            self.shared[f'{input_name}_resistance'] = resistance
            self.shared[f'{input_name}_state'] = is_active
            
            # Track state changes for logging/timestamps
            if is_active != was_active:
                self.shared[f'{input_name}_last_change'] = now
                # Log state change (optional)
                # print(f"Input {input_name}: {was_active} -> {is_active}")
            
            # ALWAYS trigger command function with current state (every cycle)
            # This ensures sustained commands stay active even if something clears the flag
            function = input_cfg.get('function')
            if function:
                self._trigger_command(function, is_active)
            
            # Update active duration
            if is_active:
                last_change = self.shared[f'{input_name}_last_change']
                self.shared[f'{input_name}_active_duration'] = now - last_change
            else:
                self.shared[f'{input_name}_active_duration'] = 0.0
            
            # Store resistance in history for trending
            if resistance is not None:
                self.resistance_history[input_name].append({
                    'timestamp': now,
                    'resistance': resistance
                })
    
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
        
        # Update shared memory flag
        flag_name = command_map.get(function)
        if flag_name:
            self.shared[flag_name] = active
            
            # Debug print (optional)
            # print(f"Input Manager: {function} = {active}")


def input_manager_process(shared_dict, config):
    """Entry point for input manager process"""
    manager = InputManager(shared_dict, config)
    manager.run()
