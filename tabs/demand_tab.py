# tabs/demand_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog, Toplevel
import customtkinter as ctk
import os, csv, time, threading, json, re, requests
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, UnexpectedAlertPresentException
from selenium.webdriver.common.keys import Keys

import config
import sys, subprocess
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

# --- Cloud File Picker Toplevel Window ---
class CloudFilePicker(ctk.CTkToplevel):
    """
    A Toplevel window to select a file from the user's cloud storage.
    """
    def __init__(self, parent, app_instance):
        """
        Initializes the Toplevel window for the cloud file picker.
        """
        super().__init__(parent)
        self.app = app_instance
        self.selected_file = None # This will store the {'id': ..., 'filename': ...} dict
        self.current_folder_id = None
        self.current_path_str = "/"
        self.history = [] # Stack to store (folder_id, path_str)

        self.title("Select File from Cloud")
        w, h = 400, 500
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Frame for back button and path
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        self.back_button = ctk.CTkButton(self.header_frame, text="< Back", width=60, command=self._go_back, state="disabled")
        self.back_button.pack(side="left")

        self.path_label = ctk.CTkLabel(self.header_frame, text=self.current_path_str, anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True, padx=10)

        # Status label (e.g., "Loading...")
        self.status_label = ctk.CTkLabel(self, text="Loading files...", text_color="gray")
        self.status_label.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        # Scrollable frame for file/folder list
        self.file_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.file_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Start loading files from the root
        threading.Thread(target=self._load_files, args=(None,), daemon=True).start()

    def _load_files(self, folder_id):
        """
        Fetches the list of files and folders from the cloud server
        for a given folder_id (or root if None).
        """
        self.after(0, self.status_label.configure, {"text": "Loading..."})
        self.after(0, self._clear_list)
        
        token = self.app.license_info.get('key')
        if not token:
            self.after(0, self.status_label.configure, {"text": "Error: Not authenticated."})
            return

        headers = {'Authorization': f'Bearer {token}'}
        base_url = f"{config.LICENSE_SERVER_URL}/files/api/list"
        url = f"{base_url}/{folder_id}" if folder_id else base_url
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if not resp.ok:
                raise Exception(f"Server error: {resp.status_code}")
                
            data = resp.json()
            if data.get('status') == 'success':
                files = data.get('files', [])
                # Filter for folders and CSV files
                display_items = [f for f in files if f['is_folder'] or f['filename'].lower().endswith('.csv')]
                self.after(0, self._populate_list, display_items)
            else:
                raise Exception(data.get('reason', 'Failed to list files.'))
        except Exception as e:
            self.after(0, self.status_label.configure, {"text": f"Error: {e}"})

    def _populate_list(self, files):
        """
        Populates the scrollable frame with buttons for each file/folder.
        """
        self._clear_list()
        self.status_label.configure(text="Select a file or folder:")
        
        if not files:
            ctk.CTkLabel(self.file_frame, text="No .csv files or folders found.", text_color="gray").pack(pady=10)
            return

        # Sort: Folders first, then by name
        files.sort(key=lambda x: (not x['is_folder'], x['filename'].lower()))

        for file_data in files:
            icon = "📁" if file_data['is_folder'] else "📄"
            btn_text = f"{icon} {file_data['filename']}"
            
            btn = ctk.CTkButton(
                self.file_frame, 
                text=btn_text, 
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"), # Theme-aware text color
                hover_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
                command=lambda f=file_data: self._on_item_click(f)
            )
            btn.pack(fill='x', padx=5, pady=2)

    def _clear_list(self):
        """
        Removes all widgets from the file list frame.
        """
        for widget in self.file_frame.winfo_children():
            widget.destroy()

    def _on_item_click(self, file_data):
        """
        Handles clicks on a file or folder.
        If folder, navigates into it. If file, selects it and closes.
        """
        if file_data['is_folder']:
            # Save current state to history
            self.history.append((self.current_folder_id, self.current_path_str))
            
            # Update current state
            self.current_folder_id = file_data['id']
            self.current_path_str = f"{self.current_path_str}{file_data['filename']}/"
            
            # Update UI
            self.path_label.configure(text=self.current_path_str)
            self.back_button.configure(state="normal")
            
            # Load files for the new folder
            threading.Thread(target=self._load_files, args=(self.current_folder_id,), daemon=True).start()
        else:
            # This is a file, select it and close
            self.selected_file = file_data
            self.grab_release()
            self.destroy()
            
    def _on_close(self):
        """Handles the window being closed via the 'X' button."""
        self.grab_release()
        self.destroy()

    def _go_back(self):
        """
        Navigates to the previous folder in the history.
        """
        if not self.history:
            return
            
        # Restore previous state from history
        prev_folder_id, prev_path_str = self.history.pop()
        
        self.current_folder_id = prev_folder_id
        self.current_path_str = prev_path_str
        
        # Update UI
        self.path_label.configure(text=self.current_path_str)
        if not self.history:
            self.back_button.configure(state="disabled")
            
        # Load files for the parent folder
        threading.Thread(target=self._load_files, args=(self.current_folder_id,), daemon=True).start()

# --- End of CloudFilePicker Class ---


class DemandTab(BaseAutomationTab):
    """
    The main class for the "Demand" automation tab.
    """
    def __init__(self, parent, app_instance):
        """
        Initializes the Demand automation tab.
        """
        super().__init__(parent, app_instance, automation_key="demand")
        # self.worker_thread = None <-- This is now managed by main_app
        self.csv_path = None # Stores the path to the *processed* file (local or temp)
        self.config_file = self.app.get_data_path("demand_inputs.json")

        self.all_applicants_data = [] # Holds all data from CSV
        self.displayed_checkboxes = [] # Holds currently visible widgets (checkboxes, labels)
        self.next_jc_separator_shown = False # Flag for sequential display
        self.next_jc_separator = None # Placeholder for separator label
        
        self.work_key_list = [] # Store work keys for autocomplete

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_widgets()
        self.load_inputs()

    def _create_widgets(self):
        """
        Creates all the UI elements (buttons, entries, frames) for the tab.
        """
        # Main tab view
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        settings_tab = notebook.add("Settings")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(notebook)

        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(2, weight=1)
        
        # --- Settings Tab Widgets ---
        controls_frame = ctk.CTkFrame(settings_tab)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        # 4 columns for compact layout
        controls_frame.grid_columnconfigure((1, 3), weight=1)
        controls_frame.grid_columnconfigure((0, 2), weight=0)

        # --- Row 0: State and Panchayat ---
        ctk.CTkLabel(controls_frame, text="State:").grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
        self.state_combobox = ctk.CTkComboBox(controls_frame, values=list(config.STATE_DEMAND_CONFIG.keys()))
        self.state_combobox.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")

        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=0, column=2, padx=(0, 5), pady=5, sticky="w")
        self.panchayat_entry = AutocompleteEntry(controls_frame, suggestions_list=self.app.history_manager.get_suggestions("panchayat"))
        self.panchayat_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        # --- Row 1: Demand Date (From) and Override To Date ---
        ctk.CTkLabel(controls_frame, text="Demand Date:").grid(row=1, column=0, padx=(10, 5), pady=5, sticky="w")

        # Demand Date Frame
        d_date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        d_date_frame.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="ew")
        self.demand_date_entry = ctk.CTkEntry(d_date_frame, placeholder_text="DD/MM/YYYY")
        self.demand_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(d_date_frame, text="📅", width=30, fg_color=("gray85", "gray25"), text_color=("black", "white"),
                    command=lambda: self.open_date_picker(lambda d: [self.demand_date_entry.delete(0, "end"), self.demand_date_entry.insert(0, d)])).pack(side="right", padx=(5,0))

        ctk.CTkLabel(controls_frame, text="Override To Date:").grid(row=1, column=2, padx=(0, 5), pady=5, sticky="w")

        # Override Date Frame
        to_date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        to_date_frame.grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        self.demand_to_date_entry = ctk.CTkEntry(to_date_frame, placeholder_text="Optional")
        self.demand_to_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(to_date_frame, text="📅", width=30, fg_color=("gray85", "gray25"), text_color=("black", "white"),
                    command=lambda: self.open_date_picker(lambda d: [self.demand_to_date_entry.delete(0, "end"), self.demand_to_date_entry.insert(0, d)])).pack(side="right", padx=(5,0))

        # --- Row 2: Days and No. of Labour ---
        
        # Days Input
        ctk.CTkLabel(controls_frame, text="Days:").grid(row=2, column=0, padx=(10, 5), pady=5, sticky="w")
        self.days_entry = ctk.CTkEntry(controls_frame, validate="key", validatecommand=(self.register(lambda P: P.isdigit() or P == ""), '%P'))
        self.days_entry.grid(row=2, column=1, padx=(0, 10), pady=5, sticky="ew")
        self.days_entry.insert(0, self.app.history_manager.get_suggestions("demand_days")[0] if self.app.history_manager.get_suggestions("demand_days") else "14")
        
        # No. of Labour (Custom Selection)
        ctk.CTkLabel(controls_frame, text="No. of Labour:").grid(row=2, column=2, padx=(0, 5), pady=5, sticky="w")
        
        custom_select_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        custom_select_frame.grid(row=2, column=3, sticky="ew", padx=5, pady=5)
        custom_select_frame.grid_columnconfigure(0, weight=1) 
        
        # UPDATED: Removed width=70
        self.custom_select_entry = ctk.CTkEntry(custom_select_frame, validate="key", validatecommand=(self.register(lambda P: P.isdigit() or P == ""), '%P'), placeholder_text="Count")
        self.custom_select_entry.grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.custom_select_button = ctk.CTkButton(custom_select_frame, text="Select", command=self._select_custom_number, width=70)
        self.custom_select_button.grid(row=0, column=1, sticky="e")
        
        # --- Row 3: Work Key ---
        ctk.CTkLabel(controls_frame, text="Work Key:").grid(row=3, column=0, padx=(10, 5), pady=5, sticky="w")
        
        work_key_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        work_key_frame.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        work_key_frame.grid_columnconfigure(0, weight=1) 
        
        self.allocation_work_key_entry = AutocompleteEntry(
            work_key_frame, 
            suggestions_list=self.work_key_list,
            placeholder_text="Optional: Enter Work Key or Load from Cloud"
        )
        self.allocation_work_key_entry.grid(row=0, column=0, sticky="ew")

        self.load_work_key_button = ctk.CTkButton(
            work_key_frame, 
            text="Load", 
            width=60, 
            command=self._load_work_key_list_from_cloud
        )
        self.load_work_key_button.grid(row=0, column=1, padx=(5, 0))
        
        # --- END Row 3 ---

        # Start/Stop/Reset buttons
        buttons_frame = ctk.CTkFrame(settings_tab); buttons_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        buttons_frame.grid_columnconfigure(0, weight=1)
        action_buttons = self._create_action_buttons(buttons_frame); action_buttons.pack(expand=True, fill="x")

        # Applicant selection frame
        applicant_frame = ctk.CTkFrame(settings_tab); applicant_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        applicant_frame.grid_columnconfigure(0, weight=1); applicant_frame.grid_rowconfigure(3, weight=1)

        applicant_header = ctk.CTkFrame(applicant_frame, fg_color="transparent"); applicant_header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        applicant_header.grid_columnconfigure(1, weight=1)

        left_buttons_frame = ctk.CTkFrame(applicant_header, fg_color="transparent")
        left_buttons_frame.grid(row=0, column=0, sticky="w")

        self.select_csv_button = ctk.CTkButton(left_buttons_frame, text="Upload from Computer", command=self._select_csv_from_computer)
        self.select_csv_button.pack(side="left", padx=(0, 10), pady=5)
        
        self.cloud_csv_button = ctk.CTkButton(left_buttons_frame, text="Select from Cloud", command=self._select_csv_from_cloud, fg_color="teal", hover_color="#00695C")
        self.cloud_csv_button.pack(side="left", padx=(0, 10), pady=5)
        
        self.demo_csv_button = ctk.CTkButton(left_buttons_frame, text="Demo CSV", command=lambda: self.app.save_demo_csv("demand"), fg_color="#2E8B57", hover_color="#257247", width=100)
        self.demo_csv_button.pack(side="left", padx=(0, 10), pady=5)

        # Select All/Clear buttons are placed here (visibility managed by _update_applicant_display)
        self.select_all_button = ctk.CTkButton(left_buttons_frame, text="Select All (≤400)", command=self._select_all_applicants)
        self.clear_selection_button = ctk.CTkButton(left_buttons_frame, text="Clear", command=self._clear_selection, fg_color="gray", hover_color="gray50")
        
        self.file_label = ctk.CTkLabel(applicant_header, text="No file loaded.", text_color="gray", anchor="w")
        self.file_label.grid(row=1, column=0, pady=(5,0), sticky="w")
        self.selection_summary_label = ctk.CTkLabel(applicant_header, text="0 applicants selected", text_color="gray", anchor="w")
        self.selection_summary_label.grid(row=2, column=0, columnspan=2, pady=(0, 5), sticky="w")
        self.search_entry = ctk.CTkEntry(applicant_header, placeholder_text="Load a CSV, then type here to search...")
        self.search_entry.grid(row=3, column=0, columnspan=2, pady=5, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._update_applicant_display)

        self.applicant_scroll_frame = ctk.CTkScrollableFrame(applicant_frame, label_text="Select Applicants to Process")
        self.applicant_scroll_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0,10)) 

        # --- Results Tab Widgets ---
        # Configure row weights
        results_tab.grid_rowconfigure(0, weight=1) # Treeview
        results_tab.grid_rowconfigure(1, weight=0) # Button frame
        
        # Configure column weights
        results_tab.grid_columnconfigure(0, weight=1) # Treeview
        results_tab.grid_columnconfigure(1, weight=0) # Scrollbar

        # Treeview
        cols = ("#", "Job Card No", "Applicant Name", "Status")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        self.results_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Scrollbar
        vsb = ttk.Scrollbar(results_tab, orient="vertical", command=self.results_tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        self.results_tree.configure(yscrollcommand=vsb.set)
        
        # ... inside _create_widgets method ...

        # Button Frame for Results
        results_button_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))

        # Left Side: Retry Button
        self.retry_failed_button = ctk.CTkButton(results_button_frame, text="Retry Failed Applicants", command=self._retry_failed_applicants)
        self.retry_failed_button.pack(side="left", padx=5)

        # Right Side: Unified Export Controls
        export_controls_frame = ctk.CTkFrame(results_button_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))

        self.export_button = ctk.CTkButton(export_controls_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side='left')
        
        self.export_format_menu = ctk.CTkOptionMenu(export_controls_frame, width=130, values=["PDF (.pdf)", "CSV (.csv)"], command=self._on_format_change)
        self.export_format_menu.pack(side='left', padx=5)

        self.export_filter_menu = ctk.CTkOptionMenu(export_controls_frame, width=150, values=["Export All", "Success Only", "Failed Only"])
        self.export_filter_menu.pack(side='left', padx=(0, 5))

        self._setup_results_treeview()

    def _select_all_applicants(self):
        """
        Selects all valid (not disabled) applicants in the list,
        up to a hardcoded limit of 400.
        """
        if not self.all_applicants_data: return
        if len(self.all_applicants_data) > 400: # Limit changed to 400
             messagebox.showinfo("Limit Exceeded", f"Cannot Select All (>400 applicants loaded: {len(self.all_applicants_data)}).")
             return
        selected_count = 0
        # Update the master data list
        for applicant_data in self.all_applicants_data:
            if "*" not in applicant_data.get('Name of Applicant', ''):
                applicant_data['_selected'] = True; selected_count += 1
        # Update the currently visible checkboxes
        for checkbox in self.displayed_checkboxes:
             if isinstance(checkbox, ctk.CTkCheckBox):
                applicant_data = checkbox.applicant_data
                if "*" not in applicant_data.get('Name of Applicant', ''):
                    checkbox.select()
        self._update_selection_summary()
        self.app.log_message(self.log_display, f"Selected all {selected_count} valid applicants.")

    def _select_custom_number(self):
        """
        Selects a custom number of applicants from the top of the list.
        """
        if not self.all_applicants_data:
            messagebox.showwarning("No Data", "Please load a CSV file first.")
            return

        try:
            num_to_select = int(self.custom_select_entry.get().strip())
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number of applicants to select.")
            return

        if num_to_select <= 0:
            messagebox.showwarning("Invalid Input", "Number must be greater than zero.")
            return
            
        if num_to_select > len(self.all_applicants_data):
            num_to_select = len(self.all_applicants_data)
            messagebox.showinfo("Adjustment", f"Selecting maximum available applicants: {num_to_select}.")

        self._clear_selection() # Clear any existing selection first

        selected_count = 0
        
        # Iterate through the master list and select the first 'num_to_select' valid entries
        for i, applicant_data in enumerate(self.all_applicants_data):
            if selected_count >= num_to_select:
                break
            
            # Check if the applicant is valid (no '*')
            if "*" not in applicant_data.get('Name of Applicant', ''):
                applicant_data['_selected'] = True
                selected_count += 1
            
        # Update the visible checkboxes
        for checkbox in self.displayed_checkboxes:
             if isinstance(checkbox, ctk.CTkCheckBox):
                if checkbox.applicant_data.get('_selected', False):
                    checkbox.select()
                else:
                    checkbox.deselect()

        self._update_selection_summary()
        self.app.log_message(self.log_display, f"Selected first {selected_count} valid applicants.")

    def _clear_processed_selection(self):
        """
        Deselects ONLY successfully processed applicants.
        Keeps 'Failed' or 'Skipped' applicants selected for easy retry.
        """
        self.app.log_message(self.log_display, "Updating selection based on results...", "info")
        
        # 1. Collect Successful JobCard+Name pairs from results
        successful_pairs = set()
        for item in self.results_tree.get_children():
            values = self.results_tree.item(item)['values']
            # values = (RowID, JC, Name, Status)
            if len(values) >= 4:
                jc = str(values[1]).strip()
                name = str(values[2]).strip()
                status = str(values[3]).lower()
                
                # Agar status me Success ya Already hai, tabhi uncheck karein
                if "success" in status or "already" in status:
                    successful_pairs.add((jc, name))

        # 2. Update Master Data
        deselected_count = 0
        for app_data in self.all_applicants_data:
            jc_no = app_data.get('Job card number', '').strip()
            app_name = app_data.get('Name of Applicant', '').strip()
            
            # Agar ye pair successful list me hai, to deselect karo
            if (jc_no, app_name) in successful_pairs:
                app_data['_selected'] = False
                deselected_count += 1
            # Warna selected rehne do (agar pehle se selected tha)

        # 3. Update Visual Checkboxes
        for widget in self.displayed_checkboxes:
            if isinstance(widget, ctk.CTkCheckBox):
                if not widget.applicant_data.get('_selected', False):
                    widget.deselect()
                else:
                    widget.select() # Ensure failed ones stay selected

        self._update_selection_summary()
        self.app.log_message(self.log_display, f"Deselected {deselected_count} successful applicants. Failed items remain checked.")

    def _select_csv_from_computer(self):
        """
        Opens a file dialog to select a local CSV.
        It then processes the CSV and starts a background upload to the cloud.
        """
        path = filedialog.askopenfilename(title="Select Demand CSV", filetypes=[("CSV", "*.csv")])
        if not path: 
            return
        
        # 1. Process the data immediately
        self._process_csv_data(path)
        
        # 2. Start background upload (non-blocking)
        self.app.log_message(self.log_display, f"Starting background upload for '{os.path.basename(path)}'...", "info")
        threading.Thread(target=self._upload_file_to_cloud, args=(path,), daemon=True).start()

    def _process_csv_data(self, path):
        """
        Reads a CSV file (from a local or temp path) and populates
        the self.all_applicants_data list.
        """
        self.csv_path = path 
        self.file_label.configure(text=os.path.basename(path))
        self.all_applicants_data = []

        try:
            with open(path, mode='r', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                try: 
                    header = next(reader)
                except StopIteration: 
                    raise ValueError("CSV file is empty.")
                
                norm_headers = [h.lower().replace(" ", "").replace("_", "") for h in header]
                
                try: 
                    name_idx = norm_headers.index("nameofapplicant")
                    jc_idx = norm_headers.index("jobcardnumber")
                except ValueError: 
                    raise ValueError("CSV Headers missing 'Name of Applicant' or 'Job card number'.")

                for row_num, row in enumerate(reader, 1):
                     if not row or len(row) <= max(name_idx, jc_idx): 
                         continue
                     name, job_card = row[name_idx].strip(), row[jc_idx].strip()
                     if name and job_card:
                        self.all_applicants_data.append({'original_index': row_num, 'Name of Applicant': name, 'Job card number': job_card, '_selected': False})

            loaded_count = len(self.all_applicants_data)
            self.app.log_message(self.log_display, f"Loaded {loaded_count} applicants from '{os.path.basename(path)}'.")
            
            # UPDATED: Call display update to handle button visibility
            self._update_applicant_display()

        except Exception as e:
            messagebox.showerror("Error Reading CSV", f"Could not read CSV.\nError: {e}")
            self.csv_path = None
            self.all_applicants_data = []
            self.file_label.configure(text="No file")
            self._update_applicant_display() # Ensure UI resets even on error
            self._update_selection_summary()

    def _upload_file_to_cloud(self, local_path):
        """
        Uploads a local file to the 'Uploads/' folder in cloud storage.
        This runs in a background thread and does not block the UI.
        """
        token = self.app.license_info.get('key')
        if not token:
            self.app.log_message(self.log_display, "Cloud Upload Failed: Not licensed.", "warning")
            return

        headers = {'Authorization': f'Bearer {token}'}
        filename = os.path.basename(local_path)
        
        # We will upload to a root folder named "Uploads"
        # The API will create it if it doesn't exist
        data = {'relative_path': f'Uploads/{filename}'}
        
        try:
            with open(local_path, 'rb') as f:
                files = {'file': (filename, f, 'text/csv')}
                
                resp = requests.post(
                    f"{config.LICENSE_SERVER_URL}/files/api/upload",
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=30
                )
            
            if resp.status_code == 201:
                self.app.log_message(self.log_display, f"Successfully uploaded '{filename}' to cloud.", "info")
            elif resp.status_code == 409: # File already exists
                 self.app.log_message(self.log_display, f"'{filename}' already exists in cloud.", "info")
            else:
                self.app.log_message(self.log_display, f"Cloud upload failed ({resp.status_code}): {resp.text}", "warning")
        except Exception as e:
            self.app.log_message(self.log_display, f"Cloud upload thread error: {e}", "warning")

    def _select_csv_from_cloud(self):
        """
        Opens the CloudFilePicker to select a CSV file from cloud storage.
        If a file is selected, it's downloaded and processed.
        """
        token = self.app.license_info.get('key')
        if not token:
            messagebox.showerror("Error", "You must be licensed to use cloud storage.")
            return

        picker = CloudFilePicker(parent=self, app_instance=self.app)
        self.wait_window(picker) # Wait for user to select a file
        
        selected_file = picker.selected_file
        
        if selected_file:
            file_id = selected_file['id']
            filename = selected_file['filename']
            
            self.app.log_message(self.log_display, f"Downloading '{filename}' from cloud...")
            temp_path = self._download_file_from_cloud(file_id, filename)
            
            if temp_path:
                self._process_csv_data(temp_path)

    def _download_file_from_cloud(self, file_id, filename):
        """
        Downloads a specific file from cloud storage to a temporary local path.
        Returns the path to the downloaded file, or None on failure.
        """
        token = self.app.license_info.get('key')
        if not token:
            self.app.log_message(self.log_display, "Cloud Download Failed: Not licensed.", "error")
            return None

        headers = {'Authorization': f'Bearer {token}'}
        url = f"{config.LICENSE_SERVER_URL}/files/api/download/{file_id}"
        
        # Save to a temp location in the app's data folder
        temp_path = self.app.get_data_path(f"cloud_download_{filename}")
        
        try:
            with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status() # Check for HTTP errors
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): 
                        f.write(chunk)
            
            self.app.log_message(self.log_display, f"Successfully downloaded '{filename}'.", "info")
            return temp_path
        except Exception as e:
            self.app.log_message(self.log_display, f"Cloud download failed: {e}", "error")
            messagebox.showerror("Download Failed", f"Could not download file: {e}")
            return None

    def _load_work_key_list_from_cloud(self):
        """
        Opens the CloudFilePicker to select a work key CSV.
        """
        token = self.app.license_info.get('key')
        if not token:
            messagebox.showerror("Error", "You must be licensed to use cloud storage.")
            return

        picker = CloudFilePicker(parent=self, app_instance=self.app)
        self.wait_window(picker) # Wait for user to select a file
        
        selected_file = picker.selected_file
        
        if selected_file:
            # Run download and processing in a thread
            file_id = selected_file['id']
            filename = selected_file['filename']
            self.app.log_message(self.log_display, f"Downloading work list '{filename}' from cloud...")
            
            # Disable button to prevent double-click
            self.load_work_key_button.configure(state="disabled") 
            
            threading.Thread(
                target=self._download_and_process_work_key_csv_thread,
                args=(file_id, filename),
                daemon=True
            ).start()

    def _download_and_process_work_key_csv_thread(self, file_id, filename):
        """
        Handles the download and processing of the work key CSV in a background thread.
        """
        try:
            # Re-use the existing download function
            temp_path = self._download_file_from_cloud(file_id, filename)
            
            if temp_path:
                # Process the file
                self._process_work_key_csv(temp_path)
            
        except Exception as e:
            # Log error
            self.app.after(0, self.app.log_message, self.log_display, f"Failed to load work keys: {e}", "error")
            self.app.after(0, messagebox.showerror, "Error Loading Work Keys", f"An error occurred: {e}")
        finally:
            # Re-enable the button from the main thread
            self.app.after(0, self.load_work_key_button.configure, {"state": "normal"})

    def _process_work_key_csv(self, path):
        """
        Reads the downloaded work key CSV and populates the autocomplete list.
        This function is called from a background thread.
        """
        temp_key_list = []
        
        try:
            with open(path, mode='r', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                try: 
                    header = next(reader)
                except StopIteration: 
                    self.app.after(0, self.app.log_message, self.log_display, "Work key file is empty.", "warning")
                    return
                
                norm_headers = [h.lower().replace(" ", "").replace("_", "") for h in header]
                
                key_idx = -1
                # Look for common headers for work codes
                possible_headers = ['workcode', 'workkey', 'fullworkcode', 'work_code', 'work_key', 'work']
                for i, h in enumerate(norm_headers):
                    if h in possible_headers:
                        key_idx = i
                        break
                
                rows_to_read = []
                if key_idx == -1: 
                    key_idx = 0 # Assume first column
                    self.app.after(0, self.app.log_message, self.log_display, "Work Key header not found, assuming column 0.", "info")
                    # Add header back to be processed as a row
                    rows_to_read = [header] + list(reader)
                else: 
                    self.app.after(0, self.app.log_message, self.log_display, f"Found Work Key header: '{header[key_idx]}'", "info")
                    rows_to_read = reader

                for row in rows_to_read:
                     if row and len(row) > key_idx: 
                         work_key = row[key_idx].strip()
                         # Add if it's a valid-looking work key (contains a number)
                         if work_key and any(char.isdigit() for char in work_key): 
                             temp_key_list.append(work_key)

            # Update AutocompleteEntry's suggestion list from main thread
            def update_ui_with_keys():
                self.work_key_list.clear()
                self.work_key_list.extend(temp_key_list)
                self.allocation_work_key_entry.suggestions = self.work_key_list
                self.app.log_message(self.log_display, f"Loaded {len(self.work_key_list)} work keys for autocomplete.")
                
            self.app.after(0, update_ui_with_keys)

        except Exception as e:
            self.app.after(0, messagebox.showerror, "Error Reading Work Key CSV", f"Could not read CSV.\nError: {e}")
            
            def clear_ui_keys():
                self.work_key_list.clear()
                self.allocation_work_key_entry.suggestions = self.work_key_list
            self.app.after(0, clear_ui_keys)

    def _update_applicant_display(self, event=None):
        """
        Updates the applicant checkbox list based on the search query or
        shows the first 50 if no search.
        """
        # 1. Clear existing widgets
        for widget in self.displayed_checkboxes: widget.destroy()
        if self.next_jc_separator: self.next_jc_separator.destroy(); self.next_jc_separator = None
        self.displayed_checkboxes.clear(); self.next_jc_separator_shown = False

        # 2. Handle Button Visibility FIRST (So they always appear)
        loaded_count = len(self.all_applicants_data)
        
        # Handle Select All Button (Limit 400)
        if 0 < loaded_count <= 400: 
            self.select_all_button.configure(text=f"Select All (≤400)")
            self.select_all_button.pack(side="left", padx=(0, 10), pady=5)
        else:
            self.select_all_button.pack_forget()

        # Handle Clear Button
        if loaded_count > 0:
            self.clear_selection_button.pack(side="left", padx=(0, 10), pady=5)
        else:
            self.clear_selection_button.pack_forget()

        # 3. Logic for Displaying the List
        if not self.all_applicants_data: return

        search = self.search_entry.get().lower().strip()
        
        # If search is short, don't filter, just stop rendering list (but buttons are already shown!)
        if search and len(search) < 3: 
            return 

        # Determine matches
        if search:
             matches = [row for row in self.all_applicants_data if
                   (search in row.get('Job card number','').lower() or
                    search in row.get('Name of Applicant','').lower())]
        else:
             # If no search, take the first 50 rows (Deleted the 'return' line that caused the bug)
             matches = self.all_applicants_data[:50]

        limit = 50
        for row in matches[:limit]: self._create_applicant_checkbox(row)
        
        # Add "..." label if there are more items
        if len(matches) > limit or (not search and len(self.all_applicants_data) > limit):
             label = ctk.CTkLabel(self.applicant_scroll_frame, text=f"... (showing first {limit} items)", text_color="gray")
             label.pack(anchor="w", padx=10, pady=2); self.displayed_checkboxes.append(label)

        # Scroll to top
        try: self.applicant_scroll_frame._parent_canvas.yview_moveto(0)
        except Exception: pass

    def _create_applicant_checkbox(self, row_data, is_next_jc=False):
        """
        Creates a single checkbox widget for an applicant.
        """
        text = f"{row_data['Job card number']}  -  {row_data['Name of Applicant']}"
        var = ctk.StringVar(value="on" if row_data['_selected'] else "off")
        cmd = lambda data=row_data, state=var: self._on_applicant_select(data, state.get())
        cb = ctk.CTkCheckBox(self.applicant_scroll_frame, text=text, variable=var, onvalue="on", offvalue="off", command=cmd)
        cb.applicant_data = row_data

        # Disable checkbox if applicant name has a '*' (e.g., marked as ineligible)
        if "*" in row_data.get('Name of Applicant', ''): cb.configure(text_color="gray50", state="disabled")
        # Highlight if it's from a 'next' job card
        elif is_next_jc: cb.configure(text_color="#a0a0ff")

        cb.pack(anchor="w", padx=10, pady=2, fill="x"); self.displayed_checkboxes.append(cb)

    def _on_applicant_select(self, applicant_data, new_state):
        """
        Handles the event when an applicant's checkbox is clicked.
        Updates the master data and the selection summary.
        """
        applicant_data['_selected'] = (new_state == "on")
        self._update_selection_summary()
        if new_state == "on": self._add_next_jobcards_to_display(applicant_data)

    def _add_next_jobcards_to_display(self, selected_applicant_data):
        """
        Intelligently displays applicants from the next few job cards
        when one is selected, to make selecting families easier.
        """
        try:
            sel_idx = next((i for i, d in enumerate(self.all_applicants_data) if d['original_index'] == selected_applicant_data['original_index']), -1)
            if sel_idx == -1: return

            sel_jc = selected_applicant_data['Job card number']; next_jcs = set(); apps_to_add = []
            max_next = 5 # Show applicants from the next 5 job cards

            for i in range(sel_idx + 1, len(self.all_applicants_data)):
                curr_app = self.all_applicants_data[i]; curr_jc = curr_app['Job card number']
                if curr_jc == sel_jc: continue # Skip applicants from the *same* JC
                if curr_jc not in next_jcs:
                    if len(next_jcs) >= max_next: break
                    next_jcs.add(curr_jc)
                if curr_jc in next_jcs: apps_to_add.append(curr_app)

            if not apps_to_add: return

            # Add a separator label if it's not already there
            if not self.next_jc_separator_shown:
                self.next_jc_separator = ctk.CTkLabel(self.applicant_scroll_frame, text=f"--- Applicants from Next {max_next} Job Card(s) ---", text_color="gray")
                self.next_jc_separator.pack(anchor="w", padx=10, pady=(10, 2)); self.displayed_checkboxes.append(self.next_jc_separator); self.next_jc_separator_shown = True

            # Add checkboxes for the newly found applicants
            displayed_indices = {cb.applicant_data['original_index'] for cb in self.displayed_checkboxes if hasattr(cb, 'applicant_data')}
            for app_data in apps_to_add:
                if app_data['original_index'] not in displayed_indices: self._create_applicant_checkbox(app_data, is_next_jc=True)

        except Exception as e: self.app.log_message(self.log_display, f"Error adding next JCs: {e}", "warning")

    def _update_selection_summary(self):
        """
        Updates the label showing the count of selected applicants and unique job cards.
        """
        selected = [r for r in self.all_applicants_data if r.get('_selected', False)]
        unique_jcs = len(set(r.get('Job card number') for r in selected))
        self.selection_summary_label.configure(text=f"{len(selected)} applicants / {unique_jcs} unique job cards")

    def set_ui_state(self, running: bool):
        """
        Enables or disables UI elements based on whether automation is running.
        """
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        
        self.state_combobox.configure(state=state)
        self.panchayat_entry.configure(state=state)
        self.days_entry.configure(state=state)
        self.select_csv_button.configure(state=state)
        self.cloud_csv_button.configure(state=state)
        self.search_entry.configure(state=state)
        self.demand_date_entry.configure(state=state)
        self.demand_to_date_entry.configure(state=state)
        self.select_all_button.configure(state=state)
        self.clear_selection_button.configure(state=state)
        self.allocation_work_key_entry.configure(state=state)
        self.load_work_key_button.configure(state=state)
        self.retry_failed_button.configure(state=state)
        
        # New Export Controls
        self.export_button.configure(state=state)
        self.export_format_menu.configure(state=state)
        self.export_filter_menu.configure(state=state)
        if state == "normal": self._on_format_change(self.export_format_menu.get())

        for widget in self.displayed_checkboxes:
             if isinstance(widget, ctk.CTkCheckBox) and "*" not in widget.cget("text"):
                 widget.configure(state=state)

    def _get_village_code(self, job_card, state_logic_key):
        """
        Extracts the village code from a job card number based on state-specific logic.
        """
        try:
            jc = job_card.split('/')[0]
            if state_logic_key == "jh": return jc.split('-')[-1]
            elif state_logic_key == "rj": return jc[-3:]
            else: self.app.log_message(self.log_display, f"Warn: Unknown state logic '{state_logic_key}'."); return jc.split('-')[-1]
        except IndexError: return None

    def start_automation(self):
        """
        Validates all user inputs and starts the main automation thread
        using the app's built-in thread manager (which plays sound).
        """
        # --- 1. Get and Validate Inputs ---
        state = self.state_combobox.get()
        if not state: messagebox.showerror("Input Error", "Select state."); return
        try: cfg = config.STATE_DEMAND_CONFIG[state]; logic_key = cfg["village_code_logic"]; url = cfg["base_url"]
        except KeyError: messagebox.showerror("Config Error", f"Demand config missing for: {state}"); return

        selected = [r for r in self.all_applicants_data if r.get('_selected', False)]
        panchayat = self.panchayat_entry.get().strip(); days_str = self.days_entry.get().strip()
        work_key_for_allocation = self.allocation_work_key_entry.get().strip()
        
        demand_to_date_str = self.demand_to_date_entry.get().strip() # Get override date

        try: 
            demand_dt_str = self.demand_date_entry.get()
            demand_dt = datetime.strptime(demand_dt_str, '%d/%m/%Y').date() 
            work_start = demand_dt.strftime('%d/%m/%Y') 
        except ValueError: messagebox.showerror("Invalid Date", "Use DD/MM/YYYY."); return

        # Validate Override Date if present
        if demand_to_date_str:
            try:
                 datetime.strptime(demand_to_date_str, '%d/%m/%Y')
            except ValueError:
                 messagebox.showerror("Invalid To Date", "Override Date must be DD/MM/YYYY."); return

        if demand_dt < datetime.now().date():
            messagebox.showerror("Invalid Date", "Demand/Work Date cannot be in the past. Please select today or a future date.")
            return

        if not days_str: messagebox.showerror("Missing Info", "Days required."); return
        if not self.csv_path: messagebox.showerror("Missing Info", "Load CSV."); return
        if not selected: messagebox.showwarning("No Selection", "Select applicants."); return
        try: days_int = int(days_str); assert days_int > 0
        except (ValueError, AssertionError): messagebox.showerror("Invalid Input", "Days must be positive number."); return

        # --- 2. Setup UI for Running State ---
        # self.stop_event.clear(); <-- Handled by app.start_automation_thread
        self.app.clear_log(self.log_display)
        for i in self.results_tree.get_children(): self.results_tree.delete(i)
        self.app.log_message(self.log_display, f"Starting demand: {len(selected)} applicant(s), State: {state}...")
        if work_key_for_allocation:
            self.app.log_message(self.log_display, f"   -> Auto-allocation is ENABLED for Work Key: {work_key_for_allocation}")
        if demand_to_date_str:
            self.app.log_message(self.log_display, f"   -> Demand To Date OVERRIDE is ENABLED: {demand_to_date_str}")

        
        # self.app.set_status("Running..."); <-- Handled by app.start_automation_thread
        self.set_ui_state(running=True) # Disable UI elements

        # --- 3. Save History and Group Data ---
        self.app.history_manager.save_entry("panchayat", panchayat); self.app.history_manager.save_entry("demand_days", days_str)
        self.save_inputs({
            "state": state, 
            "panchayat": panchayat, 
            "demand_date": demand_dt_str, 
            "days": days_str, 
            "work_key_for_allocation": work_key_for_allocation,
            "demand_to_date": demand_to_date_str
        })

        # Group selected applicants by Village Code -> Job Card
        grouped = {}; skipped_malformed = 0
        for app in selected:
            jc = app.get('Job card number', '').strip()
            if not jc: continue
            vc = self._get_village_code(jc, logic_key)
            if not vc: skipped_malformed += 1; continue
            if vc not in grouped: grouped[vc] = {}
            if jc not in grouped[vc]: grouped[vc][jc] = []
            grouped[vc][jc].append(app)
        if skipped_malformed: self.app.log_message(self.log_display, f"Warn: Skipped {skipped_malformed} malformed Job Cards.", "warning")

        # --- 4. Start Worker Thread using the App's Method ---
        # This will play the sound and manage the thread
        args_tuple = (
            state, panchayat, days_int, work_start, 
            work_start, grouped, url, work_key_for_allocation, demand_to_date_str
        )
        self.app.start_automation_thread(
            key=self.automation_key,
            target=self._process_demand,
            args=args_tuple
        )

    def reset_ui(self):
        """
        Resets all inputs, selections, and logs on the tab.
        """
        if not messagebox.askokcancel("Reset?", "Clear inputs, selections, logs?"): return
        self.state_combobox.set(""); self.panchayat_entry.delete(0, 'end'); self.days_entry.delete(0, 'end'); self.search_entry.delete(0, 'end')
        self.allocation_work_key_entry.delete(0, 'end')
        
        # --- FIX: Use delete(0, 'end') instead of clear() ---
        self.demand_date_entry.delete(0, 'end')
        self.demand_to_date_entry.delete(0, 'end')
        # ----------------------------------------------------

        self.csv_path = None; self.all_applicants_data.clear()
        self.file_label.configure(text="No file loaded.", text_color="gray")
        self.select_all_button.pack_forget(); self.clear_selection_button.pack_forget()
        # Clear work key list
        self.work_key_list.clear()
        self.allocation_work_key_entry.suggestions = self.work_key_list
        
        self._update_applicant_display(); self._update_selection_summary()
        for i in self.results_tree.get_children(): self.results_tree.delete(i)
        self.app.clear_log(self.log_display); self.app.after(0, self.app.set_status, "Ready"); self.app.log_message(self.log_display, "Form reset.")

    def _setup_results_treeview(self):
        """
        Configures the columns and headings for the results table.
        """
        cols = ("#", "Job Card No", "Applicant Name", "Status")
        self.results_tree["columns"] = cols
        self.results_tree.column("#0", width=0, stretch=tkinter.NO); self.results_tree.column("#", anchor='c', width=40)
        self.results_tree.column("Job Card No", anchor='w', width=180); self.results_tree.column("Applicant Name", anchor='w', width=150)
        self.results_tree.column("Status", anchor='w', width=250)
        self.results_tree.heading("#0", text=""); self.results_tree.heading("#", text="#")
        self.results_tree.heading("Job Card No", text="Job Card No"); self.results_tree.heading("Applicant Name", text="Applicant Name")
        self.results_tree.heading("Status", text="Status")
        self.style_treeview(self.results_tree)

    def _process_demand(self, state, panchayat, user_days, demand_from, work_start, grouped, base_url, work_key_for_allocation, demand_to_override):
        """
        The main automation function that runs in a thread.
        It loops through villages and job cards.
        """
        driver = None
        try:
            driver = self.app.get_driver();
            if not driver: self.app.after(0, self.app.log_message, self.log_display, "ERROR: WebDriver unavailable."); return
            driver.get(base_url)
            wait, short_wait = WebDriverWait(driver, 20), WebDriverWait(driver, 5)

            # Define potential element IDs for different state portals
            p_ids = ["ctl00_ContentPlaceHolder1_DDL_panchayat", "ctl00_ContentPlaceHolder1_ddlPanchayat"]
            v_ids = ["ctl00_ContentPlaceHolder1_DDL_Village", "ctl00_ContentPlaceHolder1_ddlvillage"]
            j_ids = ["ctl00_ContentPlaceHolder1_DDL_Registration", "ctl00_ContentPlaceHolder1_ddlJobcard"]
            days_worked_ids = ["ctl00_ContentPlaceHolder1_Lbldays"]
            grid_ids = ["ctl00_ContentPlaceHolder1_gvData", "ctl00_ContentPlaceHolder1_GridView1"]
            btn_ids = ["ctl00_ContentPlaceHolder1_btnProceed", "ctl00_ContentPlaceHolder1_btnSave"]
            err_msg_ids = ["ctl00_ContentPlaceHolder1_Lblmsgerr"]

            # --- Detect Login Mode (Block vs GP) ---
            self.app.after(0, self.app.set_status, "Detecting login mode...") # <-- STATUS UPDATE
            is_gp = False
            panchayat_selector = ", ".join([f"#{pid}" for pid in p_ids])
            
            try:
                WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, panchayat_selector)))
                is_gp = False
                self.app.after(0, self.app.log_message, self.log_display, "Block Login Mode assumed (Panchayat found).", "info")
            except TimeoutException:
                is_gp = True
                self.app.after(0, self.app.log_message, self.log_display, "GP Login Mode assumed (Panchayat dropdown not found).", "info")
            
            # --- Handle Block Login (Select Panchayat) ---
            if not is_gp:
                if not panchayat:
                    self.app.after(0, self.app.log_message, self.log_display, "ERROR: Panchayat name required for Block Login.", "error")
                    for vc, jcs_in_v in grouped.items():
                        for jc_err, apps_err in jcs_in_v.items():
                            for app_data_err in apps_err: self.app.after(0, self._update_results_tree, (jc_err, app_data_err.get('Name of Applicant'), "FAIL: Panchayat Name Required"))
                    return 
                
                try:
                    self.app.after(0, self.app.set_status, f"Selecting Panchayat: {panchayat}") # <-- STATUS UPDATE
                    self.app.after(0, self.app.log_message, self.log_display, f"Selecting Panchayat: {panchayat}")
                    panchayat_dropdown = driver.find_element(By.CSS_SELECTOR, panchayat_selector)
                    Select(panchayat_dropdown).select_by_visible_text(panchayat)
                    self.app.after(0, self.app.log_message, self.log_display, "Waiting for villages to load after P selection...")
                    wait.until(EC.any_of(EC.presence_of_element_located((By.XPATH, f"//select[@id='{v_ids[0]}']/option[position()>1]")), EC.presence_of_element_located((By.XPATH, f"//select[@id='{v_ids[1]}']/option[position()>1]"))))
                except NoSuchElementException as e_select:
                    self.app.after(0, self.app.log_message, self.log_display, f"ERROR: Panchayat '{panchayat}' not found in dropdown. Stopping.", "error")
                    raise e_select
            else: # GP Login
                self.app.after(0, self.app.set_status, "Waiting for villages (GP Mode)...") # <-- STATUS UPDATE
                self.app.after(0, self.app.log_message, self.log_display, "Waiting for villages (GP Mode)...")
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"#{v_ids[0]}, #{v_ids[1]}")))
                wait.until(EC.any_of(EC.presence_of_element_located((By.XPATH, f"//select[@id='{v_ids[0]}']/option[position()>1]")), EC.presence_of_element_located((By.XPATH, f"//select[@id='{v_ids[1]}']/option[position()>1]"))))

            # --- Loop Through Villages ---
            total_v, proc_v = len(grouped), 0
            for vc, jcs_in_v in grouped.items():
                proc_v += 1
                if self.app.stop_events[self.automation_key].is_set(): break
                try:
                    self.app.after(0, self.app.set_status, f"V {proc_v}/{total_v}: Selecting Village {vc}...") # <-- STATUS UPDATE
                    self.app.after(0, self.app.log_message, self.log_display, f"--- Village {proc_v}/{total_v} (Code: {vc}) ---")
                    v_el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"#{v_ids[0]}, #{v_ids[1]}"))); v_sel = Select(v_el); found_v = False
                    for opt in v_sel.options:
                        if opt.get_attribute('value').endswith(vc): v_sel.select_by_value(opt.get_attribute('value')); self.app.after(0, self.app.log_message, self.log_display, f"Selected Village '{opt.text}' (...{vc})."); found_v = True; break
                    if not found_v: raise NoSuchElementException(f"Village code {vc} not found.")

                    self.app.after(0, self.app.set_status, f"V {proc_v}/{total_v}: Loading job cards...") # <-- STATUS UPDATE
                    self.app.after(0, self.app.log_message, self.log_display, "Waiting for job cards..."); time.sleep(0.5)
                    wait.until(EC.any_of(EC.presence_of_element_located((By.XPATH, f"//select[@id='{j_ids[0]}']/option[position()>1]")), EC.presence_of_element_located((By.XPATH, f"//select[@id='{j_ids[1]}']/option[position()>1]"))))

                    # --- Loop Through Job Cards in Village ---
                    total_jc, proc_jc = len(jcs_in_v), 0
                    for jc, apps in jcs_in_v.items():
                        proc_jc += 1
                        if self.app.stop_events[self.automation_key].is_set(): break
                        
                        # This updates the *internal* tab status
                        self.app.after(0, self.update_status, f"V {proc_v}/{total_v}, JC {proc_jc}/{total_jc}", (proc_v-1 + proc_jc/total_jc)/total_v)
                        # This updates the *main app* status
                        self.app.after(0, self.app.set_status, f"V {proc_v}/{total_v}, JC {proc_jc}/{total_jc}: {jc.split('/')[-1]}") # <-- STATUS UPDATE
                        
                        self._process_single_job_card(driver, wait, short_wait, jc, apps, user_days, demand_from, work_start, days_worked_ids, j_ids, grid_ids, btn_ids, err_msg_ids, base_url, state, demand_to_override)

                except Exception as e: 
                    self.app.after(0, self.app.log_message, self.log_display, f"ERROR Village {vc}: {type(e).__name__} - {e}. Skipping.", "error")
                    for jc_err, apps_err in jcs_in_v.items():
                         for app_data_err in apps_err: self.app.after(0, self._update_results_tree, (jc_err, app_data_err.get('Name of Applicant'), f"Skipped (Village Error)"))
                    continue 

            if not self.app.stop_events[self.automation_key].is_set():
                self.app.after(0, self.app.log_message, self.log_display, "✅ All processed.")

        except Exception as e:
            self.app.after(0, self.app.log_message, self.log_display, f"CRITICAL ERROR: {type(e).__name__} - {e}", "error")
            self.app.after(0, self.update_status, f"Error: {type(e).__name__}", 0.0) 
            self.app.after(0, lambda: messagebox.showerror("Error", f"Automation stopped: {e}"))
        finally:
            final_status_text = "Finished"
            final_tab_status = "Finished" # For internal tab status
            final_progress = 1.0
            
            if self.app.stop_events[self.automation_key].is_set():
                self.app.after(0, self.app.log_message, self.log_display, "Stopped by user.", "warning")
                final_status_text = "Stopped"
                final_tab_status = "Stopped"
            elif 'e' in locals():
                final_status_text = f"Error: {type(e).__name__}"
                final_tab_status = f"Error: {type(e).__name__}"
                final_progress = 0.0
            else:
                # If auto-allocation is set, trigger it
                if work_key_for_allocation and not self.app.stop_events[self.automation_key].is_set():
                    self.app.after(0, self.app.log_message, self.log_display, f"✅ Demand finished. Triggering auto-allocation for Panchayat: {panchayat}, Work Key: {work_key_for_allocation}")
                    self.app.after(500, self.app.run_work_allocation_from_demand, panchayat, work_key_for_allocation)
                else:
                    self.app.after(100, lambda: messagebox.showinfo("Complete", "Demand automation finished."))
                self.app.after(0, self._clear_processed_selection)
            
            # Unlock the UI
            self.app.after(0, self.set_ui_state, False)
            
            # --- FIX: Update BOTH status bars ---
            self.app.after(0, self.app.set_status, final_status_text) # Main app footer status
            self.app.after(0, self.update_status, final_tab_status, final_progress) # Internal tab status
            
            # Reset status to "Ready" after 5 seconds if finished successfully
            if not self.app.stop_events[self.automation_key].is_set() and 'e' not in locals():
                 self.app.after(5000, lambda: self.app.set_status("Ready")) 
                 self.app.after(5000, lambda: self.update_status("Ready", 0.0))

    # --- Helper Function for Background Execution (Add this above _process_single_job_card) ---
    def safe_js_fill(self, driver, element, value):
        """
        Fills an input using JavaScript and triggers all necessary events 
        (input, change, blur) to simulate real user interaction.
        Works in background/minimized mode.
        """
        try:
            driver.execute_script(
                """
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """,
                element, value
            )
        except Exception:
            # Fallback if JS fails
            try:
                element.clear()
                element.send_keys(value + Keys.TAB)
            except:
                pass

    def _process_single_job_card(self, driver, wait, short_wait, jc, apps_in_jc,
                                 user_days, demand_from, work_start,
                                 days_worked_ids, jc_ids, grid_ids, btn_ids,
                                 err_msg_ids,
                                 base_url, state, demand_to_override): 
        """
        Handles the selenium logic for processing a single job card.
        MINIMIZE-FRIENDLY UPDATE:
        1. Uses 'EC.presence_of...' instead of 'visibility' (Works when minimized).
        2. Uses JavaScript for Clicking (Bypasses UI checks).
        3. Uses 'innerText' for reading text (Works without rendering).
        """

        def get_worked_days_ultra_fast():
            """Reads 'Total Days worked' - Minimized Friendly."""
            try:
                # 'presence_of' use kar rahe hain taaki minimize me bhi detect ho
                days_el = WebDriverWait(driver, 1.0).until(EC.presence_of_element_located((By.ID, days_worked_ids[0])))
                
                # .text minimize me kabhi kabhi empty aata hai, isliye 'innerText' use kiya
                worked_str = days_el.get_attribute("innerText").strip()
                
                if not worked_str: return 0
                return int(worked_str) if worked_str.isdigit() else 0
            except Exception: return 0

        def fill_demand_data(days_distribution): 
            """Finds the applicants in the web table and fills their demand data."""
            nonlocal filled, processed
            applicants_not_found = set(targets) 
            fill_success = False
            
            # 1. Wait for Table (Presence check)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"table[id='{grid_id}'] > tbody > tr")))
            except Exception: 
                self.app.after(0, self.app.log_message, self.log_display, f"   ERROR: Grid not found.", "error")
                return False

            # --- PASS 1: CLEANING ---
            rows = driver.find_elements(By.CSS_SELECTOR, f"table[id='{grid_id}'] > tbody > tr")
            for i, r in enumerate(rows):
                if i == 0: continue 
                try:
                    # Use execute_script/innerText for faster checking in background
                    name_span = r.find_element(By.CSS_SELECTOR, f"span[id*='_job']") 
                    name_web = name_span.get_attribute("innerText").strip()
                    is_target = any("".join(tn.lower().split()) in "".join(name_web.lower().split()) for tn in targets)
                    
                    if not is_target:
                        pfx = f"{grid_id}_ctl{i+1:02d}_"
                        try:
                            date_fld = r.find_element(By.ID, f"{pfx}dt_app")
                            if date_fld.get_attribute('value'):
                                date_fld.clear()
                        except: pass
                except: pass

            # --- PASS 2: FILLING ---
            for target_name, days_to_fill in days_distribution.items():
                if self.app.stop_events[self.automation_key].is_set(): return False
                
                if days_to_fill == 0:
                    processed.add(target_name); applicants_not_found.discard(target_name); fill_success = True; continue
                
                found = False
                # Re-fetch rows
                rows = driver.find_elements(By.CSS_SELECTOR, f"table[id='{grid_id}'] > tbody > tr") 

                for i, r in enumerate(rows):
                    if i == 0: continue
                    try:
                        # Presence check instead of visibility
                        name_span = short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#{grid_id}_ctl{i+1:02d}_job")))
                        name_web = name_span.get_attribute("innerText").strip()
                        
                        if "".join(target_name.lower().split()) in "".join(name_web.lower().split()):
                            applicants_not_found.discard(target_name)
                            pfx = f"{grid_id}_ctl{i+1:02d}_"; ids = {k: pfx+v for k,v in {'from':'dt_app','start':'dt_from','days':'d3','till':'dt_to'}.items()}
                            
                            # Presence checks for inputs
                            from_in = wait.until(EC.presence_of_element_located((By.ID, ids['from'])))
                            start_in = wait.until(EC.presence_of_element_located((By.ID, ids['start'])))

                            days_in_val = ""
                            try: days_in_val = driver.find_element(By.ID, ids['days']).get_attribute('value')
                            except: pass

                            needs_upd = True 
                            if not demand_to_override:
                                needs_upd = (from_in.get_attribute('value') != demand_from or start_in.get_attribute('value') != work_start or days_in_val != str(days_to_fill))

                            if needs_upd:
                                self.app.after(0, self.app.log_message, self.log_display, f"   -> Updating: '{name_web}' ({days_to_fill}d)...")
                                
                                if from_in.get_attribute('value') != demand_from: 
                                    from_in.clear(); from_in.send_keys(demand_from + Keys.TAB); time.sleep(0.1)
                                
                                start_in = wait.until(EC.presence_of_element_located((By.ID, ids['start']))) 
                                if start_in.get_attribute('value') != work_start: 
                                    start_in.clear(); start_in.send_keys(work_start + Keys.TAB); time.sleep(0.3) 
                                else: 
                                    start_in.send_keys(Keys.TAB); time.sleep(0.3) 

                                days_in = wait.until(EC.presence_of_element_located((By.ID, ids['days']))) 
                                days_after = days_in.get_attribute('value')
                                
                                if days_after != str(days_to_fill):
                                    # JavaScript Click for checkbox/field if needed
                                    # driver.execute_script("arguments[0].click();", days_in) # Optional safe click
                                    days_in.click(); time.sleep(0.1)
                                    
                                    cvl = len(days_after or "")
                                    [(days_in.send_keys(Keys.BACKSPACE), time.sleep(0.05)) for _ in range(cvl + 2)]
                                    
                                    days_in.send_keys(str(days_to_fill) + Keys.TAB)
                                    
                                    try: wait.until(lambda d: d.find_element(By.ID, ids['till']).get_attribute("value") != "")
                                    except: pass 
                                else:
                                    days_in.send_keys(Keys.TAB); time.sleep(0.2)
                            
                            if demand_to_override:
                                try:
                                    till_in = driver.find_element(By.ID, ids['till'])
                                    current_till = till_in.get_attribute("value")
                                    if current_till != demand_to_override:
                                        till_in.click(); time.sleep(0.1)
                                        [(till_in.send_keys(Keys.BACKSPACE), time.sleep(0.02)) for _ in range(len(current_till or "") + 3)]
                                        till_in.send_keys(demand_to_override + Keys.TAB); time.sleep(0.2)
                                except Exception: pass

                            filled = True; processed.add(target_name); found = True; fill_success = True; break
                    except Exception: continue

                if not found: time.sleep(0.1); continue

            for nf in applicants_not_found: 
                processed.add(nf) 
                self.app.after(0, self._update_results_tree, (jc, nf, "Failed (Not found in Table)"))
            
            return fill_success

        # --- Main logic ---
        try:
            jc_suffix = jc.split('/')[-1]
            self.app.after(0, self.app.log_message, self.log_display, f"Processing JC Suffix: {jc_suffix}")
            
            old_days_label = None
            try: old_days_label = driver.find_element(By.ID, days_worked_ids[0])
            except: pass

            try:
                # Use 'presence_of' instead of 'element_to_be_clickable'
                jc_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#{jc_ids[0]}, #{jc_ids[1]}")))
                jc_val = jc.split('/')[0]
                try: Select(jc_el).select_by_value(jc_val)
                except NoSuchElementException:
                    possible_prefixes = [f"{jc_suffix}-", f"{jc_suffix.zfill(2)}-", f"{jc_suffix.zfill(3)}-"]
                    found_by_text = False
                    for prefix in possible_prefixes:
                        try:
                            xpath = f".//option[starts-with(normalize-space(.), '{prefix}')]"
                            opt = jc_el.find_element(By.XPATH, xpath)
                            Select(jc_el).select_by_visible_text(opt.text)
                            found_by_text = True; break
                        except NoSuchElementException: continue
                    if not found_by_text: raise NoSuchElementException(f"Couldn't find JC '{jc_suffix}'.")
            
                if old_days_label:
                    self.app.after(0, self.app.set_status, "Waiting for page refresh...")
                    try: wait.until(EC.staleness_of(old_days_label))
                    except TimeoutException: pass

            except NoSuchElementException:
                [self.app.after(0, self._update_results_tree, (jc, a.get('Name of Applicant'), "FAIL: JC Not Found")) for a in apps_in_jc]; return

            targets = [a.get('Name of Applicant', '').strip() for a in apps_in_jc]
            if not targets: return

            self.app.after(0, self.app.set_status, f"JC {jc_suffix}: Reading worked days...")
            
            err_found = False; msg = ""
            try:
                WebDriverWait(driver, 1.0).until(EC.presence_of_element_located((By.XPATH, "//font[contains(text(), 'not yet issued')]")))
                msg = "Skipped (JC Not Issued)"; err_found = True
            except: pass

            if err_found:
                 [self.app.after(0, self._update_results_tree, (jc, a.get('Name of Applicant'), msg)) for a in apps_in_jc]; return

            worked = get_worked_days_ultra_fast()
            avail = 100 - worked 
            days_distribution = {} 
            
            if avail <= 0: 
                [self.app.after(0, self._update_results_tree, (jc, a.get('Name of Applicant'), "Skipped (100 days)")) for a in apps_in_jc]; return

            adj_days_per_app = user_days 
            total_needed = user_days * len(targets)
            if total_needed > avail: adj_days_per_app = avail // len(targets) 
            elif user_days > avail: adj_days_per_app = avail
            
            for target_name in targets:
                days_distribution[target_name] = adj_days_per_app if adj_days_per_app > 0 else (avail if targets.index(target_name)==0 else 0)

            grid_id = "";
            try: 
                grid_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#{grid_ids[0]}, #{grid_ids[1]}"))); 
                grid_id = grid_el.get_attribute("id")
            except TimeoutException:
                [self.app.after(0, self._update_results_tree, (jc, a.get('Name of Applicant'), "Skipped (Table fail)")) for a in apps_in_jc]; return

            self.app.after(0, self.app.set_status, f"JC {jc_suffix}: Filling data...") 
            processed = set(); filled = False;
            
            filled = fill_demand_data(days_distribution) 

            # 7. Submit (MINIMIZE FRIENDLY)
            if filled:
                self.app.after(0, self.app.set_status, f"JC {jc_suffix}: Submitting...")
                # Use 'presence' instead of 'clickable'
                btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#{btn_ids[0]}, #{btn_ids[1]}")))
                
                # JAVASCRIPT CLICK - The Secret to Minimized Automation
                driver.execute_script("arguments[0].click();", btn)
                
                res = ""; alert_ok = False; 
                
                try: 
                    alert = WebDriverWait(driver, 3).until(EC.alert_is_present())
                    res = alert.text.strip()
                    self.app.after(0, self.app.log_message, self.log_display, f"   RESULT (Alert): {res}")
                    alert.accept()
                    alert_ok = True
                except TimeoutException: 
                    try:
                        # Use presence for error msg reading
                        potential_messages = short_wait.until(EC.presence_of_all_elements_located((By.XPATH, "//font[@color='red'] | //span[contains(@id, '_lblmsg')]")))
                        res = " ".join([el.get_attribute("innerText").strip() for el in potential_messages if el.get_attribute("innerText").strip()]) 
                        if not res: res = "Unknown (No Alert/Msg)"
                        self.app.after(0, self.app.log_message, self.log_display, f"   RESULT: {res}", "warning")
                    except: 
                        res = "Unknown (Timeout)"

                # Final Status Logic
                for app_data in apps_in_jc:
                    name = app_data.get('Name of Applicant', 'N/A')
                    if name not in processed: 
                        self.app.after(0, self._update_results_tree, (jc, name, "Failed (Skipped/Not Processed)"))
                        continue
                    
                    status_text = res.lower()
                    is_failure = any(x in status_text for x in ['error', 'fail', 'not saved', 'problem', 'contact', 'select'])
                    
                    if alert_ok and not is_failure: 
                        final_status = f"Success"
                    else:
                        final_status = f"FAIL: {res}"
                        
                    self.app.after(0, self._update_results_tree, (jc, name, final_status))
            
            else:
                 for app_data in apps_in_jc:
                     name = app_data.get('Name of Applicant', 'N/A')
                     if name in processed: 
                         self.app.after(0, self._update_results_tree, (jc, name, "Already Correct"))
                     else:
                         self.app.after(0, self._update_results_tree, (jc, name, "Failed (Grid Error)"))

        except Exception as e:
            self.app.after(0, self.app.log_message, self.log_display, f"CRITICAL ERROR processing {jc}: {e}", "error")
            [self.app.after(0, self._update_results_tree, (jc, a.get('Name of Applicant'), f"FAIL: {type(e).__name__}")) for a in apps_in_jc]
            try: driver.get(base_url); time.sleep(1)
            except: pass
            
                          
    def _update_results_tree(self, data):
        """
        Adds a new row to the results treeview with correct color tags.
        """
        jc, name, status = data
        row_id = len(self.results_tree.get_children()) + 1
        
        status_str = str(status)
        status_low = status_str.lower()
        tags = () # Default: No Color (White/Black)

        # 1. Failed Logic (Red)
        if any(e in status_low for e in ['fail', 'error', 'crash', 'not found', 'invalid', 'aadhaar', 'not saved', 'not issued']):
            tags = ('failed',)
            
        # 2. Warning Logic (Yellow) - 'skipped' is also mapped to warning color now
        elif any(w in status_low for w in ['skip', 'adjust', 'limit', '100 days']):
            tags = ('warning',)
            
        # 3. Success Logic (Green) - YE MISSING THA
        elif any(s in status_low for s in ['success', 'saved', 'already', 'done']):
            tags = ('success',)

        # Display Text Truncation
        disp_status = (status_str[:100] + '...') if len(status_str) > 100 else status_str
        
        self.results_tree.insert("", "end", iid=row_id, values=(row_id, jc, name, disp_status), tags=tags)
        self.results_tree.yview_moveto(1)

    def _retry_failed_applicants(self):
        """
        Re-selects all applicants who are marked as 'failed' in the
        results table, so the user can run the automation again for them.
        """
        self.app.log_message(self.log_display, "Re-selecting failed applicants...", "info")
        failed_items = self.results_tree.tag_has('failed')
        
        if not failed_items:
            self.app.log_message(self.log_display, "No failed applicants found in results.", "info")
            messagebox.showinfo("Retry Failed", "No failed applicants found in the results table.")
            return

        re_selected_count = 0
        
        # Clear current selection in the main data
        for app_data in self.all_applicants_data:
            app_data['_selected'] = False

        # Iterate through failed items in the tree
        for item_id in failed_items:
            try:
                values = self.results_tree.item(item_id, 'values')
                if not values: continue
                
                jc_no = values[1]
                name = values[2]

                # Find this applicant in the master data list and mark for re-selection
                found = False
                for app_data in self.all_applicants_data:
                    if app_data['Job card number'] == jc_no and app_data['Name of Applicant'] == name:
                        app_data['_selected'] = True
                        re_selected_count += 1
                        found = True
                        break
                
                if not found:
                    self.app.log_message(self.log_display, f"Could not find {name} ({jc_no}) in original CSV.", "warning")
                        
            except Exception as e:
                self.app.log_message(self.log_display, f"Error processing item {item_id}: {e}", "error")

        # Update all visible checkboxes to reflect the new selection
        for widget in self.displayed_checkboxes:
            if isinstance(widget, ctk.CTkCheckBox):
                if widget.applicant_data.get('_selected', False):
                    widget.select()
                else:
                    widget.deselect()

        self._update_selection_summary()
        self.app.log_message(self.log_display, f"Re-selected {re_selected_count} failed applicants.")
        messagebox.showinfo("Retry Failed", f"Re-selected {re_selected_count} failed applicants.\n\n"
                                             "Please fix any issues (like un-issued job cards) and then click 'Start Automation' to retry.")

    def export_results(self):
        """
        Exports the contents of the results treeview to a CSV file.
        """
        if not self.results_tree.get_children(): messagebox.showinfo("Export", "No results."); return
        p = self.panchayat_entry.get().strip().replace(" ", "_") or "UnknownPanchayat"; s = self.state_combobox.get() or "UnknownState"
        fname = f"Demand_Report_{s}_{p}_{datetime.now():%Y%m%d_%H%M}.csv"; self.export_treeview_to_csv(self.results_tree, fname)

    def save_inputs(self, inputs):
        """
        Saves the current UI inputs (state, panchayat, etc.) to a JSON file.
        """
        try:
            with open(self.config_file, 'w') as f: json.dump(inputs, f, indent=4)
        except Exception as e: print(f"Err saving demand inputs: {e}")

    def load_inputs(self):
        """
        Loads the last saved inputs from the JSON file on tab startup.
        """
        today = datetime.now().strftime('%d/%m/%Y'); date_to_set = today
        days_to_set = self.app.history_manager.get_suggestions("demand_days")[0] if self.app.history_manager.get_suggestions("demand_days") else "14"
        work_key_to_set = ""
        demand_to_date_set = ""
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f: data = json.load(f)
                self.state_combobox.set(data.get('state', '')); self.panchayat_entry.insert(0, data.get('panchayat', ''))
                days_to_set = data.get('days', days_to_set)
                work_key_to_set = data.get('work_key_for_allocation', '')
                demand_to_date_set = data.get('demand_to_date', '')
                
                loaded = data.get('demand_date', '');
                try: datetime.strptime(loaded, '%d/%m/%Y'); date_to_set = loaded
                except ValueError: pass
            except Exception as e: print(f"Err loading demand inputs: {e}")
            
        # --- FIX: Use delete/insert ---
        self.demand_date_entry.delete(0, "end")
        self.demand_date_entry.insert(0, date_to_set)
        
        self.demand_to_date_entry.delete(0, "end")
        if demand_to_date_set:
             self.demand_to_date_entry.insert(0, demand_to_date_set)
        # ------------------------------
        
        self.days_entry.delete(0, 'end')
        self.days_entry.insert(0, days_to_set)
        
        self.allocation_work_key_entry.delete(0, 'end')
        self.allocation_work_key_entry.insert(0, work_key_to_set)

    def _clear_selection(self):
        """
        Clears the current selection of all applicants.
        """
        if not any(a.get('_selected', False) for a in self.all_applicants_data): self.app.log_message(self.log_display, "No selection.", "info"); return
        # Update master data
        for a in self.all_applicants_data: a['_selected'] = False
        # Update visible checkboxes
        for w in self.displayed_checkboxes:
             if isinstance(w, ctk.CTkCheckBox) and w.get() == "on": w.deselect()
        self._update_selection_summary(); self.app.log_message(self.log_display, "Selection cleared.")
        
        # Force re-evaluation of button visibility using the main update function
        self._update_applicant_display()


    def _on_format_change(self, selected_format):
        """Disables the filter menu for CSV format as it exports all data."""
        if "CSV" in selected_format:
            self.export_filter_menu.configure(state="disabled")
        else:
            self.export_filter_menu.configure(state="normal")

    def export_report(self):
        """
        Central function to handle exporting results to PDF or CSV.
        """
        export_format = self.export_format_menu.get()
        panchayat_name = self.panchayat_entry.get().strip()
        state_name = self.state_combobox.get().strip()

        # Ensure Panchayat name is provided for the filename
        if not panchayat_name:
            messagebox.showwarning("Input Needed", "Please enter a Panchayat Name to include in the report filename.")
            return

        # CSV Logic
        if "CSV" in export_format:
            # Use existing CSV logic, but allow custom filename
            safe_p = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
            safe_s = "".join(c for c in state_name if c.isalnum() or c in (' ', '_')).rstrip()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            default_filename = f"Demand_Report_{safe_s}_{safe_p}_{timestamp}.csv"
            self.export_treeview_to_csv(self.results_tree, default_filename)
            return
            
        # PDF Logic
        data, file_path = self._get_filtered_data_and_filepath(export_format)
        if not data: return

        if "PDF" in export_format:
            self._handle_pdf_export(data, file_path)

    def _get_filtered_data_and_filepath(self, export_format):
        """
        Gathers data from Treeview based on filters (Success/Failed) and asks user for save path.
        """
        all_items = self.results_tree.get_children()
        if not all_items: 
            messagebox.showinfo("No Data", "There are no results to export.")
            return None, None
            
        panchayat_name = self.panchayat_entry.get().strip()
        state_name = self.state_combobox.get().strip()

        filter_option = self.export_filter_menu.get()
        data_to_export = []
        
        for item_id in all_items:
            # Treeview columns: ("#", "Job Card No", "Applicant Name", "Status")
            # Values index: 0=RowID, 1=JC, 2=Name, 3=Status
            row_values = self.results_tree.item(item_id)['values']
            status = str(row_values[3]).upper() # Status is at index 3
            
            should_include = False
            if filter_option == "Export All": 
                should_include = True
            elif filter_option == "Success Only" and ("SUCCESS" in status or "ALREADY" in status): 
                should_include = True
            elif filter_option == "Failed Only" and not ("SUCCESS" in status or "ALREADY" in status): 
                should_include = True
                
            if should_include:
                data_to_export.append(row_values)
                
        if not data_to_export: 
            messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'.")
            return None, None

        safe_p = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
        safe_s = "".join(c for c in state_name if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        
        file_details = {
            "PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")], "title": "Save Report as PDF"},
        }
        details = file_details.get(export_format, file_details["PDF (.pdf)"])
        filename = f"Demand_Report_{safe_s}_{safe_p}_{timestamp}{details['ext']}"

        file_path = filedialog.asksaveasfilename(
            defaultextension=details['ext'], 
            filetypes=details['types'], 
            initialdir=self.app.get_user_downloads_path(), 
            initialfile=filename, 
            title=details['title']
        )
        return (data_to_export, file_path) if file_path else (None, None)

    def _handle_pdf_export(self, data, file_path):
        """Handles the generation of the PDF report."""
        try:
            # Treeview columns: ("#", "Job Card No", "Applicant Name", "Status")
            headers = ["#", "Job Card No", "Applicant Name", "Status"]
            
            # Adjusted column widths for A4 Landscape (Approx total 280mm)
            # Row ID(15), JC(65), Name(60), Status(140)
            col_widths = [15, 65, 60, 140] 
            
            title = f"Demand Automation Report: {self.panchayat_entry.get().strip()} ({self.state_combobox.get()})"
            report_date = datetime.now().strftime('%d %b %Y')
            
            # Using base_tab.py's generate_report_pdf
            success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
            
            if success:
                if messagebox.askyesno("Success", f"PDF Report exported to:\n{file_path}\n\nDo you want to open the file?"):
                    if sys.platform == "win32":
                        os.startfile(file_path)
                    else:
                        subprocess.call(['open', file_path])
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to create PDF file.\n\nError: {e}")