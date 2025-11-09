#!/usr/bin/env python3
"""
Simple touchscreen UI for gate controller
Three big buttons: OPEN | STOP | CLOSE
With settings page for config editing
"""

import tkinter as tk
from tkinter import ttk
from gate_controller_v2 import GateController
import threading
import json

class GateUI:
    def __init__(self):
        self.controller = GateController()
        
        # Create window
        self.root = tk.Tk()
        self.root.title("Gate Controller")
        self.root.geometry("800x480")  # Set size instead of fullscreen for testing
        self.root.configure(bg='black')
        print("Window created")
        
        # Create main frame, settings frame, input status frame, and command editor frame
        self.main_frame = tk.Frame(self.root, bg='black')
        self.settings_frame = tk.Frame(self.root, bg='black')
        self.input_status_frame = tk.Frame(self.root, bg='black')
        self.command_editor_frame = tk.Frame(self.root, bg='black')
        
        # Build all pages
        self.build_main_page()
        self.build_settings_page()
        self.build_input_status_page()
        self.build_command_editor_page()
        
        # Show main page initially
        self.show_main_page()
        
        print("Window created")
        
        # Start status update loop AFTER window is shown
        self.root.after(100, self.update_status)
        print("Starting mainloop")
    
    def show_main_page(self):
        """Show the main control page"""
        self.settings_frame.pack_forget()
        self.input_status_frame.pack_forget()
        self.command_editor_frame.pack_forget()
        self.main_frame.pack(expand=True, fill='both')
    
    def show_settings_page(self):
        """Show the settings page"""
        self.main_frame.pack_forget()
        self.input_status_frame.pack_forget()
        self.command_editor_frame.pack_forget()
        self.load_current_config()
        self.settings_frame.pack(expand=True, fill='both')
    
    def show_input_status_page(self):
        """Show the input status page"""
        self.main_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.command_editor_frame.pack_forget()
        self.input_status_frame.pack(expand=True, fill='both')
    
    def show_command_editor_page(self):
        """Show the command editor page"""
        self.main_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.input_status_frame.pack_forget()
        self.load_input_config_for_editor()
        self.command_editor_frame.pack(expand=True, fill='both')
    
    def build_main_page(self):
        """Build the main control page"""
        # Status label
        self.status_label = tk.Label(
            self.main_frame,
            text="CLOSED",
            font=('Arial', 24, 'bold'),
            bg='black',
            fg='white'
        )
        self.status_label.pack(pady=20)
        print("Status label created")
        
        # Button frame
        button_frame = tk.Frame(self.main_frame, bg='black')
        button_frame.pack(expand=True, fill='both', padx=20, pady=10)
        
        # Button states
        self.open_active = False
        self.stop_active = False
        self.close_active = False
        
        # OPEN button
        self.open_btn = tk.Button(
            button_frame,
            text="OPEN",
            font=('Arial', 32, 'bold'),
            bg='green',
            fg='white',
            command=self.toggle_open,
            relief='raised',
            bd=5
        )
        self.open_btn.pack(side='left', expand=True, fill='both', padx=5)
        print("Open button created")
        
        # STOP button
        self.stop_btn = tk.Button(
            button_frame,
            text="STOP",
            font=('Arial', 32, 'bold'),
            bg='red',
            fg='white',
            command=self.toggle_stop,
            relief='raised',
            bd=5
        )
        self.stop_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # CLOSE button
        self.close_btn = tk.Button(
            button_frame,
            text="CLOSE",
            font=('Arial', 32, 'bold'),
            bg='blue',
            fg='white',
            command=self.toggle_close,
            relief='raised',
            bd=5
        )
        self.close_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # Photocell button frame (smaller buttons below)
        photocell_frame = tk.Frame(self.main_frame, bg='black')
        photocell_frame.pack(fill='x', padx=20, pady=5)
        
        # Photocell state tracking
        self.closing_photo_active = False
        self.opening_photo_active = False
        
        # CLOSING PHOTOCELL button
        self.closing_photo_btn = tk.Button(
            photocell_frame,
            text="CLOSING\nPHOTO",
            font=('Arial', 12, 'bold'),
            bg='yellow',
            fg='black',
            command=self.toggle_closing_photo,
            relief='raised',
            bd=3
        )
        self.closing_photo_btn.pack(side='left', expand=True, fill='both', padx=3)
        
        # OPENING PHOTOCELL button
        self.opening_photo_btn = tk.Button(
            photocell_frame,
            text="OPENING\nPHOTO",
            font=('Arial', 12, 'bold'),
            bg='orange',
            fg='black',
            command=self.toggle_opening_photo,
            relief='raised',
            bd=3
        )
        self.opening_photo_btn.pack(side='left', expand=True, fill='both', padx=3)
        
        # Partial open state tracking
        self.partial_1_active = False
        self.partial_2_active = False
        
        # PARTIAL 1 button - NO PERCENTAGE
        self.partial_1_btn = tk.Button(
            photocell_frame,
            text="PO1",
            font=('Arial', 12, 'bold'),
            bg='purple',
            fg='white',
            command=self.toggle_partial_1,
            relief='raised',
            bd=3
        )
        self.partial_1_btn.pack(side='left', expand=True, fill='both', padx=3)
        
        # PARTIAL 2 button - NO PERCENTAGE
        self.partial_2_btn = tk.Button(
            photocell_frame,
            text="PO2",
            font=('Arial', 12, 'bold'),
            bg='violet',
            fg='white',
            command=self.toggle_partial_2,
            relief='raised',
            bd=3
        )
        self.partial_2_btn.pack(side='left', expand=True, fill='both', padx=3)
        
        # Safety edge button frame
        safety_frame = tk.Frame(self.main_frame, bg='black')
        safety_frame.pack(fill='x', padx=20, pady=5)
        
        # Safety edge state tracking
        self.stop_closing_active = False
        self.stop_opening_active = False
        
        # STOP CLOSING edge button
        self.stop_closing_btn = tk.Button(
            safety_frame,
            text="STOP\nCLOSING",
            font=('Arial', 14, 'bold'),
            bg='red',
            fg='white',
            command=self.toggle_stop_closing,
            relief='raised',
            bd=3
        )
        self.stop_closing_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # STOP OPENING edge button
        self.stop_opening_btn = tk.Button(
            safety_frame,
            text="STOP\nOPENING",
            font=('Arial', 14, 'bold'),
            bg='darkred',
            fg='white',
            command=self.toggle_stop_opening,
            relief='raised',
            bd=3
        )
        self.stop_opening_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # Deadman control frame
        deadman_frame = tk.Frame(self.main_frame, bg='black')
        deadman_frame.pack(fill='x', padx=20, pady=5)
        
        # Deadman state tracking
        self.deadman_open_active = False
        self.deadman_close_active = False
        
        # DEADMAN OPEN button
        self.deadman_open_btn = tk.Button(
            deadman_frame,
            text="DEADMAN\nOPEN",
            font=('Arial', 14, 'bold'),
            bg='lightgreen',
            fg='black',
            command=self.toggle_deadman_open,
            relief='raised',
            bd=3
        )
        self.deadman_open_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # DEADMAN CLOSE button
        self.deadman_close_btn = tk.Button(
            deadman_frame,
            text="DEADMAN\nCLOSE",
            font=('Arial', 14, 'bold'),
            bg='lightblue',
            fg='black',
            command=self.toggle_deadman_close,
            relief='raised',
            bd=3
        )
        self.deadman_close_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # Timed open button (toggle style like photocells)
        self.timed_open_active = False
        self.timed_open_btn = tk.Button(
            deadman_frame,
            text="TIMED\nOPEN",
            font=('Arial', 14, 'bold'),
            bg='purple',
            fg='white',
            command=self.toggle_timed_open,
            relief='raised',
            bd=3
        )
        self.timed_open_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # Step logic button (momentary - creates impulse)
        self.step_logic_active = False
        self.step_logic_btn = tk.Button(
            deadman_frame,
            text="STEP\nLOGIC",
            font=('Arial', 14, 'bold'),
            bg='cyan',
            fg='black',
            command=self.step_logic_pulse,
            relief='raised',
            bd=3
        )
        self.step_logic_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # Bottom button frame for EXIT and SETTINGS
        bottom_frame = tk.Frame(self.main_frame, bg='black')
        bottom_frame.pack(fill='x', padx=20, pady=5)
        
        # Exit button
        exit_btn = tk.Button(
            bottom_frame,
            text="EXIT",
            font=('Arial', 12),
            command=self.on_exit,
            bg='darkgray'
        )
        exit_btn.pack(side='left', padx=5)
        
        # Settings button
        settings_btn = tk.Button(
            bottom_frame,
            text="SETTINGS",
            font=('Arial', 12),
            command=self.show_settings_page,
            bg='darkblue',
            fg='white'
        )
        settings_btn.pack(side='left', padx=5)
        
        # Input Status button
        input_status_btn = tk.Button(
            bottom_frame,
            text="INPUTS",
            font=('Arial', 12),
            command=self.show_input_status_page,
            bg='darkorange',
            fg='white'
        )
        input_status_btn.pack(side='left', padx=5)
        
        # Command Editor button
        command_editor_btn = tk.Button(
            bottom_frame,
            text="COMMANDS",
            font=('Arial', 12),
            command=self.show_command_editor_page,
            bg='darkmagenta',
            fg='white'
        )
        command_editor_btn.pack(side='left', padx=5)
        
        print("All UI elements created")
    
    def build_settings_page(self):
        """Build the settings configuration page"""
        # Title
        title = tk.Label(
            self.settings_frame,
            text="SETTINGS",
            font=('Arial', 24, 'bold'),
            bg='black',
            fg='white'
        )
        title.pack(pady=10)
        
        # Scrollable frame for settings
        canvas = tk.Canvas(self.settings_frame, bg='black', highlightthickness=0)
        scrollbar = tk.Scrollbar(self.settings_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='black')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Dictionary to hold entry widgets
        self.config_entries = {}
        
        # Config fields with labels and descriptions
        config_fields = [
            ('run_time', 'Full Travel Time (s)', 'Time for gate to fully open/close'),
            ('pause_time', 'Pause Time (s)', 'Pause between movements'),
            ('motor1_open_delay', 'Motor 1 Open Delay (s)', 'Delay before M1 starts opening'),
            ('motor2_close_delay', 'Motor 2 Close Delay (s)', 'Delay before M2 starts closing'),
            ('auto_close_time', 'Auto-Close Time (s)', 'Seconds before auto-close from OPEN'),
            ('safety_reverse_time', 'Safety Reverse Time (s)', 'Reverse duration on safety trigger'),
            ('deadman_speed', 'Deadman Speed (0-1)', 'Speed multiplier for deadman control'),
            ('step_logic_mode', 'Step Logic Mode (1-4)', 'Step logic behavior mode'),
            ('partial_1_percent', 'PO1 Position (%)', 'Partial open 1 target percentage'),
            ('partial_2_percent', 'PO2 Position (%)', 'Partial open 2 target percentage'),
            ('partial_1_auto_close_time', 'PO1 Auto-Close (s)', 'Auto-close time for partial position 1'),
            ('partial_2_auto_close_time', 'PO2 Auto-Close (s)', 'Auto-close time for partial position 2'),
            ('partial_return_pause', 'Partial Return Pause (s)', 'Pause before returning from partial'),
        ]
        
        for key, label, description in config_fields:
            frame = tk.Frame(scrollable_frame, bg='black')
            frame.pack(fill='x', padx=20, pady=5)
            
            # Label
            lbl = tk.Label(
                frame,
                text=label,
                font=('Arial', 12, 'bold'),
                bg='black',
                fg='white',
                anchor='w'
            )
            lbl.pack(side='left', fill='x', expand=True)
            
            # Entry
            entry = tk.Entry(frame, font=('Arial', 12), width=10)
            entry.pack(side='right', padx=5)
            self.config_entries[key] = entry
            
            # Description
            desc = tk.Label(
                scrollable_frame,
                text=description,
                font=('Arial', 9),
                bg='black',
                fg='gray',
                anchor='w'
            )
            desc.pack(fill='x', padx=40, pady=(0, 10))
        
        # Auto-close enabled checkbox
        auto_close_frame = tk.Frame(scrollable_frame, bg='black')
        auto_close_frame.pack(fill='x', padx=20, pady=5)
        
        self.auto_close_var = tk.BooleanVar()
        auto_close_check = tk.Checkbutton(
            auto_close_frame,
            text="Auto-Close Enabled",
            variable=self.auto_close_var,
            font=('Arial', 12, 'bold'),
            bg='black',
            fg='white',
            selectcolor='black',
            activebackground='black',
            activeforeground='white'
        )
        auto_close_check.pack(side='left')
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        # Button frame at bottom
        button_frame = tk.Frame(self.settings_frame, bg='black')
        button_frame.pack(fill='x', padx=20, pady=10)
        
        # Save button
        save_btn = tk.Button(
            button_frame,
            text="SAVE",
            font=('Arial', 16, 'bold'),
            bg='green',
            fg='white',
            command=self.save_config,
            relief='raised',
            bd=5
        )
        save_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # Back button
        back_btn = tk.Button(
            button_frame,
            text="BACK",
            font=('Arial', 16, 'bold'),
            bg='blue',
            fg='white',
            command=self.show_main_page,
            relief='raised',
            bd=5
        )
        back_btn.pack(side='left', expand=True, fill='both', padx=5)
    
    def build_input_status_page(self):
        """Build the input status monitoring page"""
        # Title
        title = tk.Label(
            self.input_status_frame,
            text="INPUT STATUS",
            font=('Arial', 24, 'bold'),
            bg='black',
            fg='white'
        )
        title.pack(pady=10)
        
        # Scrollable frame for inputs
        canvas = tk.Canvas(self.input_status_frame, bg='black', highlightthickness=0)
        scrollbar = tk.Scrollbar(self.input_status_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='black')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Dictionary to hold input display widgets
        self.input_displays = {}
        
        # Load input config to get list of inputs
        # The input_manager uses default config when file doesn't have 'inputs' key
        # So we'll do the same here
        try:
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'r') as f:
                input_config = json.load(f)
            inputs = input_config.get('inputs', None)
            
            # If no 'inputs' key, use defaults (same as input_manager)
            if inputs is None or len(inputs) == 0:
                print("No 'inputs' key in config, using defaults")
                inputs = {
                    'CMD_OPEN': {'channel': 0, 'type': 'NC'},
                    'CMD_CLOSE': {'channel': 1, 'type': 'NC'},
                    'CMD_STOP': {'channel': 2, 'type': 'NC'},
                    'PHOTOCELL_CLOSE': {'channel': 3, 'type': 'NO'}
                }
        except Exception as e:
            print(f"Warning: Failed to load input config: {e}")
            # Use same defaults as input_manager
            inputs = {
                'CMD_OPEN': {'channel': 0, 'type': 'NC'},
                'CMD_CLOSE': {'channel': 1, 'type': 'NC'},
                'CMD_STOP': {'channel': 2, 'type': 'NC'},
                'PHOTOCELL_CLOSE': {'channel': 3, 'type': 'NO'}
            }
        
        print(f"Building input displays for {len(inputs)} inputs: {list(inputs.keys())}")
        
        # Create display for each input
        for input_name, input_cfg in inputs.items():
            print(f"Creating display for {input_name}...")
            input_frame = tk.Frame(scrollable_frame, bg='#222222', relief='ridge', bd=2)
            input_frame.pack(fill='x', padx=10, pady=5)
            
            # Input name header with channel
            name_label = tk.Label(
                input_frame,
                text=f"{input_name} (ADC CH{input_cfg['channel']})",
                font=('Arial', 14, 'bold'),
                bg='#222222',
                fg='cyan',
                anchor='w'
            )
            name_label.pack(fill='x', padx=5, pady=2)
            
            # Info frame for type, function, state
            info_frame = tk.Frame(input_frame, bg='#222222')
            info_frame.pack(fill='x', padx=5, pady=2)
            
            # Type label
            type_label = tk.Label(
                info_frame,
                text=f"Type: {input_cfg.get('type', 'NO')}",
                font=('Arial', 10),
                bg='#222222',
                fg='white',
                anchor='w'
            )
            type_label.pack(side='left', padx=5)
            
            # Function/Command label
            function = input_cfg.get('function', None)
            function_text = f"→ {function}" if function else "→ [unassigned]"
            function_color = 'lime' if function else 'orange'
            function_label = tk.Label(
                info_frame,
                text=function_text,
                font=('Arial', 10, 'bold'),
                bg='#222222',
                fg=function_color,
                anchor='w'
            )
            function_label.pack(side='left', padx=5)
            
            # State indicator (will be updated dynamically)
            state_label = tk.Label(
                info_frame,
                text="State: ???",
                font=('Arial', 10, 'bold'),
                bg='#222222',
                fg='gray',
                anchor='w'
            )
            state_label.pack(side='left', padx=5)
            
            # Description label (optional)
            description = input_cfg.get('description', '')
            if description:
                desc_label = tk.Label(
                    input_frame,
                    text=description,
                    font=('Arial', 9),
                    bg='#222222',
                    fg='gray',
                    anchor='w'
                )
                desc_label.pack(fill='x', padx=5, pady=(0, 2))
            
            # Values frame
            values_frame = tk.Frame(input_frame, bg='#222222')
            values_frame.pack(fill='x', padx=5, pady=2)
            
            # Voltage label
            voltage_label = tk.Label(
                values_frame,
                text="Voltage: ?.??V",
                font=('Arial', 9),
                bg='#222222',
                fg='lightgray',
                anchor='w'
            )
            voltage_label.pack(side='left', padx=5)
            
            # Resistance label (if applicable)
            resistance_label = tk.Label(
                values_frame,
                text="R: ???",
                font=('Arial', 9),
                bg='#222222',
                fg='lightgray',
                anchor='w'
            )
            resistance_label.pack(side='left', padx=5)
            
            # Store references for updating
            self.input_displays[input_name] = {
                'state': state_label,
                'voltage': voltage_label,
                'resistance': resistance_label,
                'frame': input_frame
            }
            print(f"  ✓ Display created for {input_name}")
        
        print(f"Total input displays created: {len(self.input_displays)}")
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        # Button frame at bottom
        button_frame = tk.Frame(self.input_status_frame, bg='black')
        button_frame.pack(fill='x', padx=20, pady=10)
        
        # Back button
        back_btn = tk.Button(
            button_frame,
            text="BACK",
            font=('Arial', 16, 'bold'),
            bg='blue',
            fg='white',
            command=self.show_main_page,
            relief='raised',
            bd=5
        )
        back_btn.pack(expand=True, fill='both', padx=5)
    
    def build_command_editor_page(self):
        """Build the command assignment editor page"""
        # Title
        title = tk.Label(
            self.command_editor_frame,
            text="COMMAND EDITOR",
            font=('Arial', 24, 'bold'),
            bg='black',
            fg='white'
        )
        title.pack(pady=10)
        
        # Instructions
        instructions = tk.Label(
            self.command_editor_frame,
            text="Assign commands to physical input terminals",
            font=('Arial', 12),
            bg='black',
            fg='gray'
        )
        instructions.pack(pady=5)
        
        # Scrollable frame for input assignments
        canvas = tk.Canvas(self.command_editor_frame, bg='black', highlightthickness=0)
        scrollbar = tk.Scrollbar(self.command_editor_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='black')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Available commands list
        self.available_commands = [
            ('none', '[None - Disabled]'),
            ('cmd_open', 'Open Command'),
            ('cmd_close', 'Close Command'),
            ('cmd_stop', 'Stop Command'),
            ('photocell_closing', 'Photocell (Closing)'),
            ('photocell_opening', 'Photocell (Opening)'),
            ('safety_stop_closing', 'Safety Edge (Stop Closing)'),
            ('safety_stop_opening', 'Safety Edge (Stop Opening)'),
            ('deadman_open', 'Deadman Open'),
            ('deadman_close', 'Deadman Close'),
            ('timed_open', 'Timed Open'),
            ('partial_1', 'Partial Open 1'),
            ('partial_2', 'Partial Open 2'),
            ('step_logic', 'Step Logic')
        ]
        
        # Input type options
        self.input_types = ['NO', 'NC', '8K2']
        
        # Dictionary to hold dropdown and type widgets
        self.command_dropdowns = {}
        self.type_dropdowns = {}
        self.enabled_vars = {}
        
        # Will be populated when load_input_config_for_editor is called
        self.editor_inputs = {}
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        # Store references to scrollable frame for dynamic content
        self.editor_scrollable_frame = scrollable_frame
        
        # Button frame at bottom
        button_frame = tk.Frame(self.command_editor_frame, bg='black')
        button_frame.pack(fill='x', padx=20, pady=10)
        
        # Save button
        save_btn = tk.Button(
            button_frame,
            text="SAVE ASSIGNMENTS",
            font=('Arial', 16, 'bold'),
            bg='green',
            fg='white',
            command=self.save_command_assignments,
            relief='raised',
            bd=5
        )
        save_btn.pack(side='left', expand=True, fill='both', padx=5)
        
        # Back button
        back_btn = tk.Button(
            button_frame,
            text="BACK",
            font=('Arial', 16, 'bold'),
            bg='blue',
            fg='white',
            command=self.show_main_page,
            relief='raised',
            bd=5
        )
        back_btn.pack(side='left', expand=True, fill='both', padx=5)
    
    def load_input_config_for_editor(self):
        """Load input configuration and populate the editor"""
        # Clear existing widgets in scrollable frame
        for widget in self.editor_scrollable_frame.winfo_children():
            widget.destroy()
        
        # Reset dictionaries
        self.command_dropdowns = {}
        self.type_dropdowns = {}
        self.enabled_vars = {}
        
        # Load config
        try:
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'r') as f:
                config = json.load(f)
            self.editor_inputs = config.get('inputs', {})
        except Exception as e:
            print(f"Error loading input config: {e}")
            self.editor_inputs = {}
        
        # Create editor row for each input
        for input_name in sorted(self.editor_inputs.keys()):
            input_cfg = self.editor_inputs[input_name]
            
            # Main frame for this input
            input_frame = tk.Frame(self.editor_scrollable_frame, bg='#333333', relief='ridge', bd=2)
            input_frame.pack(fill='x', padx=10, pady=5)
            
            # Header with input name and channel
            header_frame = tk.Frame(input_frame, bg='#333333')
            header_frame.pack(fill='x', padx=5, pady=5)
            
            # Enabled checkbox
            enabled_var = tk.BooleanVar(value=input_cfg.get('enabled', True))
            self.enabled_vars[input_name] = enabled_var
            
            enabled_check = tk.Checkbutton(
                header_frame,
                text="",
                variable=enabled_var,
                font=('Arial', 12),
                bg='#333333',
                selectcolor='#333333',
                activebackground='#333333'
            )
            enabled_check.pack(side='left', padx=5)
            
            name_label = tk.Label(
                header_frame,
                text=f"{input_name} (ADC CH{input_cfg['channel']})",
                font=('Arial', 14, 'bold'),
                bg='#333333',
                fg='cyan',
                anchor='w'
            )
            name_label.pack(side='left', fill='x', expand=True, padx=5)
            
            # Settings frame
            settings_frame = tk.Frame(input_frame, bg='#333333')
            settings_frame.pack(fill='x', padx=5, pady=5)
            
            # Input type dropdown
            type_label = tk.Label(
                settings_frame,
                text="Type:",
                font=('Arial', 11, 'bold'),
                bg='#333333',
                fg='white'
            )
            type_label.pack(side='left', padx=5)
            
            type_var = tk.StringVar(value=input_cfg.get('type', 'NO'))
            type_dropdown = ttk.Combobox(
                settings_frame,
                textvariable=type_var,
                values=self.input_types,
                state='readonly',
                width=8,
                font=('Arial', 11)
            )
            type_dropdown.pack(side='left', padx=5)
            self.type_dropdowns[input_name] = type_var
            
            # Command assignment dropdown
            command_label = tk.Label(
                settings_frame,
                text="Command:",
                font=('Arial', 11, 'bold'),
                bg='#333333',
                fg='white'
            )
            command_label.pack(side='left', padx=5)
            
            # Get current function (convert None to 'none')
            current_function = input_cfg.get('function', None)
            if current_function is None:
                current_function = 'none'
            
            command_var = tk.StringVar(value=current_function)
            command_dropdown = ttk.Combobox(
                settings_frame,
                textvariable=command_var,
                values=[cmd[0] for cmd in self.available_commands],
                state='readonly',
                width=20,
                font=('Arial', 11)
            )
            command_dropdown.pack(side='left', padx=5)
            self.command_dropdowns[input_name] = command_var
            
            # Add description label that shows friendly name
            def update_description(event, input_name=input_name):
                var = self.command_dropdowns[input_name]
                cmd_value = var.get()
                friendly_name = next((name for cmd, name in self.available_commands if cmd == cmd_value), '')
                self.desc_labels[input_name].config(text=friendly_name)
            
            command_dropdown.bind('<<ComboboxSelected>>', update_description)
            
            # Description label
            current_friendly = next((name for cmd, name in self.available_commands if cmd == current_function), '')
            desc_label = tk.Label(
                input_frame,
                text=current_friendly,
                font=('Arial', 10),
                bg='#333333',
                fg='lime',
                anchor='w'
            )
            desc_label.pack(fill='x', padx=5, pady=(0, 5))
            
            # Store description label
            if not hasattr(self, 'desc_labels'):
                self.desc_labels = {}
            self.desc_labels = getattr(self, 'desc_labels', {})
            self.desc_labels[input_name] = desc_label
            
            # 8K2 Learning Section (only show if type is 8K2)
            resistance_frame = tk.Frame(input_frame, bg='#444444')
            
            # Store frame reference for show/hide based on type
            if not hasattr(self, 'resistance_frames'):
                self.resistance_frames = {}
            self.resistance_frames[input_name] = resistance_frame
            
            # Tolerance entry
            tolerance_label = tk.Label(
                resistance_frame,
                text="Tolerance (%):",
                font=('Arial', 10),
                bg='#444444',
                fg='white'
            )
            tolerance_label.pack(side='left', padx=5, pady=3)
            
            tolerance_var = tk.StringVar(value=str(input_cfg.get('tolerance_percent', 10)))
            tolerance_entry = tk.Entry(
                resistance_frame,
                textvariable=tolerance_var,
                font=('Arial', 10),
                width=6
            )
            tolerance_entry.pack(side='left', padx=5)
            
            # Store tolerance variable
            if not hasattr(self, 'tolerance_vars'):
                self.tolerance_vars = {}
            self.tolerance_vars[input_name] = tolerance_var
            
            # Learn button
            learn_btn = tk.Button(
                resistance_frame,
                text="LEARN",
                font=('Arial', 10, 'bold'),
                bg='orange',
                fg='black',
                command=lambda name=input_name: self.learn_resistance(name),
                relief='raised',
                bd=2
            )
            learn_btn.pack(side='left', padx=5)
            
            # Learned resistance display
            learned_r = input_cfg.get('learned_resistance', None)
            if learned_r:
                learned_text = f"Learned: {learned_r:.0f}Ω"
                learned_color = 'lime'
            else:
                learned_text = "Not learned"
                learned_color = 'gray'
            
            learned_label = tk.Label(
                resistance_frame,
                text=learned_text,
                font=('Arial', 10, 'bold'),
                bg='#444444',
                fg=learned_color
            )
            learned_label.pack(side='left', padx=5)
            
            # Store learned label for updates
            if not hasattr(self, 'learned_labels'):
                self.learned_labels = {}
            self.learned_labels[input_name] = learned_label
            
            # Show/hide based on current type
            if input_cfg.get('type', 'NO') == '8K2':
                resistance_frame.pack(fill='x', padx=5, pady=3)
            
            # Bind type dropdown change to show/hide resistance frame
            def on_type_change(event, name=input_name):
                if self.type_dropdowns[name].get() == '8K2':
                    self.resistance_frames[name].pack(fill='x', padx=5, pady=3)
                else:
                    self.resistance_frames[name].pack_forget()
            
            type_dropdown.bind('<<ComboboxSelected>>', on_type_change)
    
    def learn_resistance(self, input_name):
        """Learn current resistance value for an 8K2 input"""
        # Get current resistance from shared memory
        resistance = self.controller.shared.get(f'{input_name}_resistance', None)
        
        if resistance is None or resistance == float('inf') or resistance == 0.0:
            print(f"Cannot learn resistance for {input_name}: invalid reading ({resistance})")
            # Show error message
            self.show_learn_error(input_name, "Invalid resistance reading")
            return
        
        # Update config in memory
        if input_name in self.editor_inputs:
            self.editor_inputs[input_name]['learned_resistance'] = resistance
            
            # Format display text (show in kΩ if >= 1kΩ)
            if resistance >= 1000:
                display_text = f"Learned: {resistance/1000:.1f}kΩ"
            else:
                display_text = f"Learned: {resistance:.0f}Ω"
            
            # Update display
            self.learned_labels[input_name].config(
                text=display_text,
                fg='lime'
            )
            
            print(f"Learned resistance for {input_name}: {resistance:.0f}Ω")
            
            # Flash the label to show it was learned
            original_bg = self.learned_labels[input_name].cget('bg')
            self.learned_labels[input_name].config(bg='yellow')
            self.root.after(300, lambda: self.learned_labels[input_name].config(bg=original_bg))
    
    def show_learn_error(self, input_name, message):
        """Show error message when learning fails"""
        # Temporarily show error in learned label
        self.learned_labels[input_name].config(text=message, fg='red')
        self.root.after(2000, lambda: self.learned_labels[input_name].config(
            text="Not learned", fg='gray'
        ))
    
    def save_command_assignments(self):
        """Save the command assignments to config file"""
        try:
            # Build updated config
            updated_config = {'inputs': {}}
            
            for input_name, input_cfg in self.editor_inputs.items():
                # Get values from dropdowns
                function = self.command_dropdowns[input_name].get()
                if function == 'none':
                    function = None
                
                input_type = self.type_dropdowns[input_name].get()
                enabled = self.enabled_vars[input_name].get()
                
                # Build base config
                config_entry = {
                    'channel': input_cfg['channel'],
                    'enabled': enabled,
                    'type': input_type,
                    'function': function,
                    'description': input_cfg.get('description', '')
                }
                
                # Add 8K2-specific fields if type is 8K2
                if input_type == '8K2':
                    # Get tolerance percentage
                    try:
                        tolerance = float(self.tolerance_vars[input_name].get())
                        config_entry['tolerance_percent'] = tolerance
                    except (ValueError, KeyError):
                        config_entry['tolerance_percent'] = 10  # Default
                    
                    # Get learned resistance if it exists
                    learned_r = input_cfg.get('learned_resistance', None)
                    if learned_r is not None:
                        config_entry['learned_resistance'] = learned_r
                
                updated_config['inputs'][input_name] = config_entry
            
            # Write to file
            with open('/home/doowkcol/Gatetorio_Code/input_config.json', 'w') as f:
                json.dump(updated_config, f, indent=2)
            
            print("Command assignments saved!")
            
            # Show confirmation
            self.show_command_save_confirmation()
            
        except Exception as e:
            print(f"Error saving command assignments: {e}")
    
    def show_command_save_confirmation(self):
        """Show a temporary 'Saved!' message"""
        confirm = tk.Label(
            self.command_editor_frame,
            text="SAVED!\nRestart gate controller to apply changes",
            font=('Arial', 16, 'bold'),
            bg='green',
            fg='white'
        )
        confirm.place(relx=0.5, rely=0.5, anchor='center')
        
        # Remove it after 2 seconds
        self.root.after(2000, confirm.destroy)
    
    def load_current_config(self):
        """Load current config values into the entry fields"""
        config_file = '/home/doowkcol/Gatetorio_Code/gate_config.json'
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            for key, entry in self.config_entries.items():
                if key in config:
                    entry.delete(0, tk.END)
                    entry.insert(0, str(config[key]))
            
            self.auto_close_var.set(config.get('auto_close_enabled', False))
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save_config(self):
        """Save the config values from entry fields"""
        config_file = '/home/doowkcol/Gatetorio_Code/gate_config.json'
        
        try:
            # Stop gate before saving config changes
            print("Stopping gate before config save...")
            self.controller.shared['cmd_stop_active'] = True
            self.controller.shared['cmd_open_active'] = False
            self.controller.shared['cmd_close_active'] = False
            
            # Build new config from entries
            new_config = {}
            
            for key, entry in self.config_entries.items():
                value = entry.get()
                # Convert to appropriate type
                if key in ['run_time', 'pause_time', 'motor1_open_delay', 'motor2_close_delay',
                          'auto_close_time', 'safety_reverse_time', 'partial_auto_close_time',
                          'partial_return_pause']:
                    new_config[key] = float(value)
                elif key in ['step_logic_mode', 'partial_1_percent', 'partial_2_percent']:
                    new_config[key] = int(value)
                elif key == 'deadman_speed':
                    new_config[key] = float(value)
            
            new_config['auto_close_enabled'] = self.auto_close_var.get()
            
            # Write to file
            with open(config_file, 'w') as f:
                json.dump(new_config, f, indent=2)
            
            print("Config saved successfully!")
            
            # Reload config in the controller
            if self.controller.reload_config():
                print("Controller config reloaded!")
            
            # Show confirmation message
            self.show_save_confirmation()
            
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def show_save_confirmation(self):
        """Show a temporary 'Saved!' message"""
        # Create a temporary label
        confirm = tk.Label(
            self.settings_frame,
            text="SAVED!",
            font=('Arial', 20, 'bold'),
            bg='green',
            fg='white'
        )
        confirm.place(relx=0.5, rely=0.5, anchor='center')
        
        # Remove it after 1 second
        self.root.after(1000, confirm.destroy)
    
    def toggle_open(self):
        """Toggle OPEN command"""
        self.open_active = not self.open_active
        self.controller.shared['cmd_open_active'] = self.open_active
        
        if self.open_active:
            print("OPEN button activated!")
            self.open_btn.config(relief='sunken', bg='darkgreen', text="OPEN\n[ON]")
        else:
            print("OPEN button deactivated")
            self.open_btn.config(relief='raised', bg='green', text="OPEN")
    
    def toggle_stop(self):
        """Toggle STOP command"""
        self.stop_active = not self.stop_active
        self.controller.shared['cmd_stop_active'] = self.stop_active
        
        if self.stop_active:
            print("STOP button activated!")
            self.stop_btn.config(relief='sunken', bg='darkred', text="STOP\n[ON]")
        else:
            print("STOP button deactivated")
            self.stop_btn.config(relief='raised', bg='red', text="STOP")
    
    def toggle_close(self):
        """Toggle CLOSE command"""
        self.close_active = not self.close_active
        self.controller.shared['cmd_close_active'] = self.close_active
        
        if self.close_active:
            print("CLOSE button activated!")
            self.close_btn.config(relief='sunken', bg='darkblue', text="CLOSE\n[ON]")
        else:
            print("CLOSE button deactivated")
            self.close_btn.config(relief='raised', bg='blue', text="CLOSE")
    
    def toggle_closing_photo(self):
        """Toggle closing photocell"""
        self.closing_photo_active = not self.closing_photo_active
        self.controller.shared['photocell_closing_active'] = self.closing_photo_active
        
        if self.closing_photo_active:
            print("CLOSING photocell activated (blocked)!")
            self.closing_photo_btn.config(relief='sunken', bg='darkorange', text="CLOSING\nPHOTO\n[BLOCKED]")
        else:
            print("CLOSING photocell deactivated (clear)")
            self.closing_photo_btn.config(relief='raised', bg='yellow', text="CLOSING\nPHOTO")
    
    def toggle_opening_photo(self):
        """Toggle opening photocell"""
        self.opening_photo_active = not self.opening_photo_active
        self.controller.shared['photocell_opening_active'] = self.opening_photo_active
        
        if self.opening_photo_active:
            print("OPENING photocell activated (blocked)!")
            self.opening_photo_btn.config(relief='sunken', bg='darkorange', text="OPENING\nPHOTO\n[BLOCKED]")
        else:
            print("OPENING photocell deactivated (clear)")
            self.opening_photo_btn.config(relief='raised', bg='orange', text="OPENING\nPHOTO")
    
    def toggle_partial_1(self):
        """Toggle partial open 1"""
        self.partial_1_active = not self.partial_1_active
        self.controller.shared['partial_1_active'] = self.partial_1_active
        
        if self.partial_1_active:
            print("PARTIAL 1 activated!")
            self.partial_1_btn.config(relief='sunken', bg='darkviolet', text="PO1\n[ON]")
        else:
            print("PARTIAL 1 deactivated")
            self.partial_1_btn.config(relief='raised', bg='purple', text="PO1")
    
    def toggle_partial_2(self):
        """Toggle partial open 2"""
        self.partial_2_active = not self.partial_2_active
        self.controller.shared['partial_2_active'] = self.partial_2_active
        
        if self.partial_2_active:
            print("PARTIAL 2 activated!")
            self.partial_2_btn.config(relief='sunken', bg='darkviolet', text="PO2\n[ON]")
        else:
            print("PARTIAL 2 deactivated")
            self.partial_2_btn.config(relief='raised', bg='violet', text="PO2")
    
    def toggle_stop_closing(self):
        """Toggle stop closing safety edge"""
        self.stop_closing_active = not self.stop_closing_active
        self.controller.shared['safety_stop_closing_active'] = self.stop_closing_active
        
        if self.stop_closing_active:
            print("STOP CLOSING edge activated!")
            self.stop_closing_btn.config(relief='sunken', bg='darkred', text="STOP\nCLOSING\n[ACTIVE]")
        else:
            print("STOP CLOSING edge deactivated")
            self.stop_closing_btn.config(relief='raised', bg='red', text="STOP\nCLOSING")
    
    def toggle_stop_opening(self):
        """Toggle stop opening safety edge"""
        self.stop_opening_active = not self.stop_opening_active
        self.controller.shared['safety_stop_opening_active'] = self.stop_opening_active
        
        if self.stop_opening_active:
            print("STOP OPENING edge activated!")
            self.stop_opening_btn.config(relief='sunken', bg='darkred', text="STOP\nOPENING\n[ACTIVE]")
        else:
            print("STOP OPENING edge deactivated")
            self.stop_opening_btn.config(relief='raised', bg='darkred', text="STOP\nOPENING")
    
    def toggle_deadman_open(self):
        """Toggle deadman open"""
        self.deadman_open_active = not self.deadman_open_active
        self.controller.shared['deadman_open_active'] = self.deadman_open_active
        
        if self.deadman_open_active:
            print("DEADMAN OPEN activated!")
            self.deadman_open_btn.config(relief='sunken', bg='darkgreen', text="DEADMAN\nOPEN\n[ON]")
        else:
            print("DEADMAN OPEN deactivated")
            self.deadman_open_btn.config(relief='raised', bg='lightgreen', text="DEADMAN\nOPEN")
    
    def toggle_deadman_close(self):
        """Toggle deadman close"""
        self.deadman_close_active = not self.deadman_close_active
        self.controller.shared['deadman_close_active'] = self.deadman_close_active
        
        if self.deadman_close_active:
            print("DEADMAN CLOSE activated!")
            self.deadman_close_btn.config(relief='sunken', bg='darkblue', text="DEADMAN\nCLOSE\n[ON]")
        else:
            print("DEADMAN CLOSE deactivated")
            self.deadman_close_btn.config(relief='raised', bg='lightblue', text="DEADMAN\nCLOSE")
    
    def toggle_timed_open(self):
        """Toggle timed open command"""
        self.timed_open_active = not self.timed_open_active
        self.controller.shared['timed_open_active'] = self.timed_open_active
        
        if self.timed_open_active:
            print("TIMED OPEN activated!")
            self.timed_open_btn.config(relief='sunken', bg='darkviolet', text="TIMED\nOPEN\n[ON]")
        else:
            print("TIMED OPEN deactivated")
            self.timed_open_btn.config(relief='raised', bg='purple', text="TIMED\nOPEN")
    
    def step_logic_pulse(self):
        """Send a momentary step logic pulse"""
        print("STEP LOGIC pulse!")
        self.controller.shared['step_logic_pulse'] = True
        
        # Visual feedback
        self.step_logic_btn.config(relief='sunken', bg='darkcyan')
        self.root.after(200, lambda: self.step_logic_btn.config(relief='raised', bg='cyan'))
    
    def update_status(self):
        """Update status display"""
        status = self.controller.get_status()
        state = status['state']
        m1_percent = status['m1_percent']
        m2_percent = status['m2_percent']
        m1_speed = status['m1_speed']
        m2_speed = status['m2_speed']
        auto_close_active = status['auto_close_active']
        auto_close_countdown = status['auto_close_countdown']
        partial_1_auto_close_active = status['partial_1_auto_close_active']
        partial_1_auto_close_countdown = status['partial_1_auto_close_countdown']
        partial_2_auto_close_active = status['partial_2_auto_close_active']
        partial_2_auto_close_countdown = status['partial_2_auto_close_countdown']
        
        # Build status text with individual motor positions and speeds
        status_text = f"{state}\nM1: {m1_percent:.0f}% (spd:{m1_speed:.0f}%)  M2: {m2_percent:.0f}% (spd:{m2_speed:.0f}%)"
        
        # Show appropriate countdown (priority: full > PO1 > PO2)
        if auto_close_active:
            status_text += f"\nAuto-close: {auto_close_countdown}s"
        elif partial_1_auto_close_active:
            status_text += f"\nPO1 auto-close: {partial_1_auto_close_countdown}s"
        elif partial_2_auto_close_active:
            status_text += f"\nPO2 auto-close: {partial_2_auto_close_countdown}s"
        
        self.status_label.config(text=status_text)
        
        # Re-assert sustained command flags every cycle (critical for sustained commands)
        # BUT: Only set to True if button active - don't clear flags set by controller (like auto-close)
        if self.open_active:
            self.controller.shared['cmd_open_active'] = True
        if self.close_active:
            self.controller.shared['cmd_close_active'] = True
        if self.stop_active:
            self.controller.shared['cmd_stop_active'] = True
        
        # Clear flags when buttons are released (but only if they were set by us)
        if not self.open_active and self.controller.shared['cmd_open_active']:
            # Only clear if we're not in auto-close or other automated operation
            if state in ['CLOSED', 'STOPPED', 'PARTIAL_1', 'PARTIAL_2']:
                self.controller.shared['cmd_open_active'] = False
        if not self.close_active and self.controller.shared['cmd_close_active']:
            # Only clear if we're not in automated closing
            if state in ['CLOSED', 'STOPPED']:
                self.controller.shared['cmd_close_active'] = False
        if not self.stop_active:
            self.controller.shared['cmd_stop_active'] = False
        
        # Re-assert safety edge flags
        self.controller.shared['safety_stop_closing_active'] = self.stop_closing_active
        self.controller.shared['safety_stop_opening_active'] = self.stop_opening_active
        
        # Re-assert photocell flags
        self.controller.shared['photocell_closing_active'] = self.closing_photo_active
        self.controller.shared['photocell_opening_active'] = self.opening_photo_active
        
        # Re-assert deadman flags
        self.controller.shared['deadman_open_active'] = self.deadman_open_active
        self.controller.shared['deadman_close_active'] = self.deadman_close_active
        
        # Re-assert partial and timed open flags
        self.controller.shared['partial_1_active'] = self.partial_1_active
        self.controller.shared['partial_2_active'] = self.partial_2_active
        self.controller.shared['timed_open_active'] = self.timed_open_active
        
        # Update input status displays (if on that page)
        self.update_input_displays()
        
        # Schedule next update
        self.root.after(100, self.update_status)
    
    def update_input_displays(self):
        """Update input status displays with current values from shared memory"""
        # Only update if we have input displays initialized
        if not hasattr(self, 'input_displays'):
            return
        
        for input_name, widgets in self.input_displays.items():
            # Get values from shared memory
            state = self.controller.shared.get(f'{input_name}_state', False)
            voltage = self.controller.shared.get(f'{input_name}_voltage', 0.0)
            resistance = self.controller.shared.get(f'{input_name}_resistance', None)
            
            # Update state label
            if state:
                widgets['state'].config(text="State: ACTIVE", fg='lime')
                widgets['frame'].config(bg='#003300')  # Dark green background
            else:
                widgets['state'].config(text="State: INACTIVE", fg='gray')
                widgets['frame'].config(bg='#222222')  # Normal dark background
            
            # Update voltage label
            widgets['voltage'].config(text=f"Voltage: {voltage:.2f}V")
            
            # Update resistance label
            if resistance is None:
                widgets['resistance'].config(text="R: N/A")
            elif resistance == float('inf'):
                widgets['resistance'].config(text="R: OPEN")
            elif resistance == 0.0:
                widgets['resistance'].config(text="R: SHORT")
            elif resistance >= 1000:
                widgets['resistance'].config(text=f"R: {resistance/1000:.1f}k")
            else:
                widgets['resistance'].config(text=f"R: {resistance:.0f}ohm")
    
    def on_exit(self):
        """Handle exit - properly kill all processes"""
        print("Exit button pressed - shutting down all processes")
        
        # Stop all control loops
        self.controller.shared['running'] = False
        
        # Give processes a moment to see the flag
        import time
        time.sleep(0.2)
        
        # Terminate motor manager process
        if hasattr(self.controller, 'motor_process') and self.controller.motor_process.is_alive():
            print("Terminating motor manager process...")
            self.controller.motor_process.terminate()
            self.controller.motor_process.join(timeout=2)
            if self.controller.motor_process.is_alive():
                print("Force killing motor manager...")
                self.controller.motor_process.kill()
        
        # Cleanup motors and GPIO
        try:
            self.controller.cleanup()
        except:
            pass
        
        # Destroy GUI
        self.root.quit()
        self.root.destroy()
        
        # Force exit the entire Python process
        import sys
        print("Exiting Python process")
        sys.exit(0)
    
    def run(self):
        """Start the UI"""
        self.root.mainloop()

if __name__ == "__main__":
    app = None
    try:
        app = GateUI()
        app.run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt - shutting down...")
        if app:
            app.on_exit()
        else:
            import sys
            sys.exit(0)
