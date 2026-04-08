# tabs/if_edit_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, csv, time, pyperclip, json
from datetime import datetime
from collections import defaultdict
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
import config
from .base_tab import BaseAutomationTab

class IfEditTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="if_edit")
        self.csv_path = None
        self.csv_headers = []
        self.column_map = {}
        self.ui_fields = {}
        self.profiles = {}
        self.profile_file = self.app.get_data_path("if_edit_profiles.json")
        self.saved_config = {}
        self.data_from_wc_gen = None # NEW: To hold data from WC Gen tab

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_widgets()
        self._load_profiles_from_file()

    def _create_widgets(self):
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        settings_tab = notebook.add("Settings")
        results_tab = notebook.add("Results")

        settings_tab.grid_rowconfigure(0, weight=1)
        settings_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        results_tab.grid_columnconfigure(0, weight=1)
        
        settings_container = ctk.CTkScrollableFrame(settings_tab, label_text="Configuration & Actions")
        settings_container.grid(row=0, column=0, sticky="nsew")
        settings_container.grid_columnconfigure(0, weight=1)

        # Automation Mode Frame
        mode_frame = ctk.CTkFrame(settings_container)
        mode_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        mode_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(mode_frame, text="Automation Mode:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        # --- MODIFIED: Added new automation mode ---
        self.automation_mode_combo = ctk.CTkComboBox(mode_frame, values=["Full Process (All Pages)", "Page 2 & 3 Only", "Page 3 Only (Activities/Materials)"])
        self.automation_mode_combo.grid(row=0, column=1, padx=15, pady=10, sticky="ew")
        self.ui_fields['automation_mode'] = self.automation_mode_combo

        # Profile Management Frame
        profile_frame = ctk.CTkFrame(settings_container)
        profile_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        profile_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(profile_frame, text="Configuration Profile:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.profile_combobox = ctk.CTkComboBox(profile_frame, values=[], command=self._load_profile)
        self.profile_combobox.grid(row=0, column=1, padx=15, pady=10, sticky="ew")
        self.profile_name_entry = ctk.CTkEntry(profile_frame, placeholder_text="Enter new profile name to save")
        self.profile_name_entry.grid(row=1, column=1, padx=15, pady=5, sticky="ew")
        profile_actions = ctk.CTkFrame(profile_frame, fg_color="transparent")
        profile_actions.grid(row=1, column=0, padx=15, pady=5)
        self.save_profile_button = ctk.CTkButton(profile_actions, text="Save", command=self._save_profile)
        self.save_profile_button.pack(side="left", padx=(0, 5))
        self.delete_profile_button = ctk.CTkButton(profile_actions, text="Delete", fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=self._delete_profile)
        self.delete_profile_button.pack(side="left")

        # CSV Frame
        csv_frame = ctk.CTkFrame(settings_container)
        csv_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        csv_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(csv_frame, text="Data Source:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=15, pady=10)
        file_frame = ctk.CTkFrame(csv_frame, fg_color="transparent")
        file_frame.grid(row=0, column=1, sticky='ew', pady=10, padx=15)
        self.select_button = ctk.CTkButton(file_frame, text="Select CSV File", command=self.select_csv_file)
        self.select_button.pack(side="left", padx=(0, 10))
        self.demo_csv_button = ctk.CTkButton(file_frame, text="Download Demo CSV", command=lambda: self.app.save_demo_csv("if_edit"), fg_color="#2E8B57", hover_color="#257247")
        self.demo_csv_button.pack(side="left", padx=(0, 10))
        self.file_label = ctk.CTkLabel(file_frame, text="No data source selected", text_color="gray")
        self.file_label.pack(side="left")

        # Convergence Switch
        switch_frame = ctk.CTkFrame(settings_container)
        switch_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        self.convergence_switch = ctk.CTkSwitch(switch_frame, text="Enable Page 2 & 3 (Convergence Work)", command=self._toggle_page_settings)
        self.convergence_switch.grid(row=0, column=0, padx=15, pady=10)
        self.ui_fields['run_convergence'] = self.convergence_switch
        
        action_frame = self._create_action_buttons(parent_frame=settings_container)
        action_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=(10, 5))

        # Settings Notebook
        self.settings_notebook = ctk.CTkTabview(settings_container)
        self.settings_notebook.grid(row=5, column=0, sticky="ew", padx=5, pady=5)
        tab_p1 = self.settings_notebook.add("Page 1 Settings")
        tab_p2 = self.settings_notebook.add("Page 2 Settings")
        tab_p3 = self.settings_notebook.add("Page 3 Settings")

        self._create_page1_widgets(tab_p1)
        self._create_page2_widgets(tab_p2)
        self._create_page3_widgets(tab_p3)
        self._toggle_page_settings()

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10), padx=5)
        self.export_csv_button = ctk.CTkButton(results_action_frame, text="Export to CSV", command=lambda: self.export_treeview_to_csv(self.results_tree, "if_edit_results.csv"))
        self.export_csv_button.pack(side="left")

        cols = ("Work Code", "Job Card", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Work Code", width=200); self.results_tree.column("Job Card", width=200); self.results_tree.column("Status", width=100, anchor="center"); self.results_tree.column("Details", width=300)
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

        self._create_log_and_status_area(parent_notebook=notebook)

    def load_data_from_wc_gen(self, data):
        """Receives data from the WC Gen tab and prepares it for automation."""
        self.data_from_wc_gen = data
        self.csv_path = None  # Ensure we don't use a file
        self.select_button.configure(state="disabled")
        self.file_label.configure(text=f"{len(data)} work codes loaded from WC Gen tab.")
        self.app.log_message(self.log_display, f"Received {len(data)} work codes to process.")
        
    def _create_field(self, parent, key, text, row, col=0, widget_type='entry', values=None, **kwargs):
        ctk.CTkLabel(parent, text=text).grid(row=row, column=col, sticky="w", padx=15, pady=5)
        if widget_type == 'entry':
            widget = ctk.CTkEntry(parent, **kwargs)
        elif widget_type == 'combo':
            widget = ctk.CTkComboBox(parent, values=values or [], **kwargs)
        widget.grid(row=row, column=col+1, sticky="ew", padx=15, pady=5)
        self.ui_fields[key] = widget

    def _create_page1_widgets(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        self._create_field(parent, "estimated_pd", "Estimated PD:", 0)
        self._create_field(parent, "beneficiaries_count", "Beneficiaries Count:", 1)
        ctk.CTkLabel(parent, text="--- Convergence Settings (If Enabled) ---", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, columnspan=2, pady=(15,5))
        self._create_field(parent, "convergence_scheme_type", "Scheme Type:", 4, widget_type='combo', values=["State", "Centre"], command=self._toggle_scheme_dropdowns)
        state_schemes = ["ABUA AWAS YOJNA", "Agriculture", "Anganbari kendra Dumaria, Dahijor", "Animal Husbandry", "B.R.G.F", "Baba Saheb Bhim Rao Ambedkar Awaas Yojna", "Birsa Sichai Kup Samvardhan Yojana", "CONST. OF PANCHAYAT BHAWAN", "Department of School Education and Literacy", "Department of Tourism, Arts, Culture, Sports & You", "Diary Development", "EAST SINGHBHUM(DUMARIA BLOCK) ST BENIFIRIES", "Fisheries", "Integrated Action Plan", "IRRIGATION WELL", "JSLPS- Jharkhand State Livelihood Promotion Societ", "Mukhyamantri Grameen Path Yojna", "SINCHAI KUP NIRMAN , PESARDAH(BICHGARHA)", "Soil Conservation", "ST Benifiries", "TestScheme", "Water Harvestig"]
        self._create_field(parent, "state_scheme_name", "State Scheme Name:", 5, widget_type='combo', values=state_schemes)
        centre_schemes = ["B.R.G.F (NON)", "B.R.G.F (R.D.MINISTRY)", "bhart health nirman yojna (gramin health department)", "DMFT (Department of Mines & Geology)", "Fifteen Finance Commission (Ministry of Panchayati Raj)", "Fourteenth Finance Commission(FFC) (Ministry of Panchayati Raj)", "IAY (R.D.MINISTRY)", "ICDS (Ministry Of Women & Child Development)", "Integrated Action Plan (R.D.MINISTRY)", "Land Levling (NON)", "niramal bhart abhiyan (R.D.MINISTRY)", "NIRMAL BHART NIRMAN (R.D.MINISTRY)", "P.H.E.D. (R.D.MINISTRY)", "PMAY-G (R.D.MINISTRY)", "RKVY (MINISTRY OF AGRICULTURE)", "rural sanitation (R.D.MINISTRY)", "RURAL SANITATION (NON)", "WELL (NON)"]
        self._create_field(parent, "centre_scheme_name", "Centre Scheme Name:", 6, widget_type='combo', values=centre_schemes)

    def _create_page2_widgets(self, parent):
        parent.grid_columnconfigure((1, 3), weight=1)
        self._create_field(parent, "sanction_no", "Tech Sanction No:", 0, 0)
        self._create_field(parent, "sanction_date", "Tech Sanction Date:", 0, 2)
        self._create_field(parent, "est_time_completion", "Est. Time Completion:", 1, 0)
        self._create_field(parent, "avg_labour_per_day", "Avg. Labour/Day:", 1, 2)
        self._create_field(parent, "expected_mandays", "Expected Mandays:", 2, 0)
        self._create_field(parent, "tech_sanction_amount", "Tech Sanction Amt:", 2, 2)
        ctk.CTkLabel(parent, text="--- Estimated Cost (in Lakhs) ---", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, columnspan=4, pady=(15,5))
        self._create_field(parent, "unskilled_labour_cost", "Unskilled Labour:", 4, 0)
        self._create_field(parent, "mgnrega_material_cost", "MGNREGA Material:", 4, 2)
        self._create_field(parent, "skilled_labour_cost", "Skilled Labour:", 5, 0)
        self._create_field(parent, "semi_skilled_labour_cost", "Semi-Skilled Labour:", 5, 2)
        self._create_field(parent, "scheme1_cost", "Scheme 1 Cost:", 6, 0)
        ctk.CTkLabel(parent, text="--- Financial Sanction ---", font=ctk.CTkFont(weight="bold")).grid(row=7, column=0, columnspan=4, pady=(15,5))
        self._create_field(parent, "fin_sanction_no", "Fin. Sanction No:", 8, 0)
        self._create_field(parent, "fin_sanction_date", "Fin. Sanction Date:", 8, 2)
        self._create_field(parent, "fin_sanction_amount", "Fin. Sanction Amt:", 9, 0)
        self._create_field(parent, "fin_scheme_input", "Fin. Scheme Input:", 9, 2)

    def _create_page3_widgets(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(parent, text="Note: These values will be applied to all work codes in the CSV.", text_color="gray50").grid(row=0, column=0, padx=15, pady=(10,5))
        
        # --- Activity Section ---
        ctk.CTkLabel(parent, text="--- Add Activities ---", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, pady=(10,5))
        ctk.CTkLabel(parent, text="One activity per line. Format: Activity Code,Unit Price,Quantity", text_color="gray50").grid(row=2, column=0, padx=15, pady=(0,5))
        activities_textbox = ctk.CTkTextbox(parent, height=100)
        activities_textbox.grid(row=3, column=0, sticky="ew", padx=15, pady=5)
        self.ui_fields['activities_list'] = activities_textbox
        
        # --- Material Section ---
        ctk.CTkLabel(parent, text="--- Add Materials (Optional) ---", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, pady=(15,5))
        ctk.CTkLabel(parent, text="One material per line. Format: Material Name,Unit Price,Quantity", text_color="gray50").grid(row=5, column=0, padx=15, pady=(0,5))
        materials_textbox = ctk.CTkTextbox(parent, height=100)
        materials_textbox.grid(row=6, column=0, sticky="ew", padx=15, pady=5)
        self.ui_fields['materials_list'] = materials_textbox

    def _populate_defaults(self):
        cfg = {**config.IF_EDIT_CONFIG["page1"], **config.IF_EDIT_CONFIG["page2"]}
        if "defaults" in config.ADD_ACTIVITY_CONFIG:
            cfg.update(config.ADD_ACTIVITY_CONFIG["defaults"])

        for key, value in cfg.items():
            if key in self.ui_fields:
                widget = self.ui_fields[key]
                if isinstance(widget, ctk.CTkEntry):
                    widget.delete(0, tkinter.END); widget.insert(0, value)
                elif isinstance(widget, ctk.CTkComboBox):
                     widget.set(value)
        
        # Set defaults for new fields
        self.automation_mode_combo.set("Full Process (All Pages)")
        if 'activities_list' in self.ui_fields:
            self.ui_fields['activities_list'].delete("1.0", tkinter.END)
            default_activity = f"{cfg.get('activity_code', '')},{cfg.get('unit_price', '')},{cfg.get('quantity', '')}"
            self.ui_fields['activities_list'].insert("1.0", default_activity)

        if 'materials_list' in self.ui_fields:
            self.ui_fields['materials_list'].delete("1.0", tkinter.END)
        
        self.convergence_switch.select()
        self._toggle_page_settings()

    def _load_profiles_from_file(self):
        if not os.path.exists(self.profile_file):
            self.profiles = {}
            self._populate_defaults()
            return
        try:
            with open(self.profile_file, 'r') as f: self.profiles = json.load(f)
            profile_names = list(self.profiles.keys())
            self.profile_combobox.configure(values=profile_names)
            last_used = "Last Used Config"
            if last_used in profile_names:
                self.profile_combobox.set(last_used); self._load_profile(last_used)
            elif profile_names:
                self.profile_combobox.set(profile_names[0]); self._load_profile(profile_names[0])
            else: self._populate_defaults()
        except Exception as e:
            self.app.log_message(self.log_display, f"Could not load profiles: {e}", "warning")
            self.profiles = {}; self._populate_defaults()

    def _save_profile(self, profile_name=None, is_autosave=False):
        if not is_autosave:
            profile_name = self.profile_name_entry.get().strip()
            if not profile_name: messagebox.showwarning("Input Error", "Please enter a name for the profile."); return
        if not profile_name: return

        config_data = {}
        for key, field in self.ui_fields.items():
            if isinstance(field, ctk.CTkTextbox):
                config_data[key] = field.get("1.0", tkinter.END).strip()
            else: config_data[key] = field.get()
        self.profiles[profile_name] = config_data

        try:
            with open(self.profile_file, 'w') as f: json.dump(self.profiles, f, indent=4)
            profile_names = list(self.profiles.keys())
            if "Last Used Config" not in profile_names: profile_names.insert(0, "Last Used Config")
            self.profile_combobox.configure(values=profile_names)
            self.profile_combobox.set(profile_name)
            if not is_autosave:
                self.profile_name_entry.delete(0, tkinter.END)
                messagebox.showinfo("Success", f"Profile '{profile_name}' saved successfully.")
        except Exception as e:
            if not is_autosave: messagebox.showerror("Error", f"Failed to save profile: {e}")

    def _load_profile(self, profile_name):
        if not profile_name or not self.profiles: return
        self.saved_config = self.profiles.get(profile_name, {})
        if not self.saved_config: self._populate_defaults(); return

        for key, value in self.saved_config.items():
            if key in self.ui_fields:
                field = self.ui_fields[key]
                if isinstance(field, ctk.CTkEntry):
                    field.delete(0, tkinter.END); field.insert(0, value)
                elif isinstance(field, ctk.CTkComboBox):
                    field.set(value)
                elif isinstance(field, ctk.CTkSwitch):
                    if value == 1: field.select()
                    else: field.deselect()
                elif isinstance(field, ctk.CTkTextbox):
                    field.delete("1.0", tkinter.END)
                    if value: field.insert("1.0", value)
        self._toggle_page_settings()
        self.app.log_message(self.log_display, f"Profile '{profile_name}' loaded.")

    def _delete_profile(self):
        profile_name = self.profile_combobox.get()
        if not profile_name or profile_name not in self.profiles or profile_name == "Last Used Config":
            messagebox.showwarning("Selection Error", "Please select a valid, user-saved profile to delete."); return
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the profile '{profile_name}'?"): return
        del self.profiles[profile_name]
        try:
            with open(self.profile_file, 'w') as f: json.dump(self.profiles, f, indent=4)
            profile_names = list(self.profiles.keys())
            self.profile_combobox.configure(values=profile_names)
            if profile_names:
                self.profile_combobox.set(profile_names[0]); self._load_profile(profile_names[0])
            else:
                self.profile_combobox.set(""); self._populate_defaults()
            messagebox.showinfo("Success", f"Profile '{profile_name}' deleted.")
        except Exception as e: messagebox.showerror("Error", f"Failed to delete profile: {e}")

    def _toggle_page_settings(self):
        is_enabled = self.convergence_switch.get() == 1
        state = "normal" if is_enabled else "disabled"
        page_keys = ["sanction_no", "sanction_date", "est_time_completion", "avg_labour_per_day", "expected_mandays", "tech_sanction_amount", "unskilled_labour_cost", "mgnrega_material_cost", "skilled_labour_cost", "semi_skilled_labour_cost", "scheme1_cost", "fin_sanction_no", "fin_sanction_date", "fin_sanction_amount", "fin_scheme_input", "convergence_scheme_type", "state_scheme_name", "centre_scheme_name", "activities_list", "materials_list"]
        for key in page_keys:
            if key in self.ui_fields: self.ui_fields[key].configure(state=state)
        if is_enabled: self._toggle_scheme_dropdowns()

    def _toggle_scheme_dropdowns(self, _=None):
        if self.convergence_switch.get() == 0:
            self.ui_fields['state_scheme_name'].configure(state="disabled")
            self.ui_fields['centre_scheme_name'].configure(state="disabled")
            return
        is_state = self.ui_fields['convergence_scheme_type'].get() == "State"
        self.ui_fields['state_scheme_name'].configure(state="normal" if is_state else "disabled")
        self.ui_fields['centre_scheme_name'].configure(state="disabled" if is_state else "normal")

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        # Disable select button if data is loaded from WC Gen, even if not running
        select_state = state if not self.data_from_wc_gen else "disabled"
        self.select_button.configure(state=select_state)
        self.profile_combobox.configure(state=state)
        self.profile_name_entry.configure(state=state)
        self.save_profile_button.configure(state=state)
        self.delete_profile_button.configure(state=state)
        for field in self.ui_fields.values():
            if field.winfo_exists(): field.configure(state=state)
        if not running:
            for key in ['estimated_pd', 'beneficiaries_count', 'automation_mode']: self.ui_fields[key].configure(state="normal")
            self._toggle_page_settings()

    def reset_ui(self):
        if messagebox.askokcancel("Reset Form?", "Are you sure?"):
            self.file_label.configure(text="No data source selected")
            self.csv_path = None
            self.column_map = {}
            self.data_from_wc_gen = None # NEW
            self.select_button.configure(state="normal") # NEW
            self._populate_defaults()
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.app.after(0, self.app.set_status, "Ready")

    def select_csv_file(self):
        path = filedialog.askopenfilename(title="Select CSV", filetypes=[("CSV files", "*.csv")])
        if path:
            self.csv_path = path
            self.data_from_wc_gen = None # Clear any previously loaded data
            self.file_label.configure(text=os.path.basename(path))
            try:
                with open(path, 'r', encoding='utf-8-sig') as f: self.csv_headers = next(csv.reader(f))
                required_cols = ['work_code', 'beneficiary_type', 'job_card']
                self.column_map = {col: self.csv_headers.index(col) for col in required_cols}
                self.app.log_message(self.log_display, "CSV loaded. Required columns found.", "success")
            except Exception as e:
                messagebox.showerror("CSV Error", f"Required columns not in CSV header: {', '.join(required_cols)}\n\nError: {e}")
                self.csv_path = None; self.column_map = {}; self.file_label.configure(text="No data source selected")

    def start_automation(self):
        if not self.csv_path and not self.data_from_wc_gen:
            messagebox.showwarning("Input Missing", "Please select a CSV file or generate data from the WC Gen tab."); return
        self._save_profile(profile_name="Last Used Config", is_autosave=True)
        form_config = {}
        for key, field in self.ui_fields.items():
            if isinstance(field, ctk.CTkTextbox):
                form_config[key] = field.get("1.0", tkinter.END).strip()
            else: form_config[key] = field.get()
        form_config['convergence_scheme_name'] = form_config['state_scheme_name'] if form_config['convergence_scheme_type'] == "State" else form_config['centre_scheme_name']
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(form_config,))

    def run_automation_logic(self, form_config):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.app.after(0, self.app.set_status, "Running IF Editor...")
        try:
            driver = self.app.get_driver()
            if not driver: return
            
            rows_to_process = []
            if self.data_from_wc_gen:
                self.app.log_message(self.log_display, "Processing data received from WC Gen tab...")
                self.column_map = {'work_code': 0, 'beneficiary_type': 1, 'job_card': 2}
                rows_to_process = [
                    [d['work_code'], d['beneficiary_type'], d['job_card']]
                    for d in self.data_from_wc_gen
                ]
            else:
                self.app.log_message(self.log_display, f"Processing data from CSV file: {self.csv_path}")
                with open(self.csv_path, mode='r', encoding='utf-8-sig') as csvfile:
                    rows_to_process = list(csv.reader(csvfile))[1:]
            
            self.app.log_message(self.log_display, f"--- Starting IF Editor: {len(rows_to_process)} work codes to process ---")
            total = len(rows_to_process)
            for i, row in enumerate(rows_to_process):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Automation stopped.", "warning"); break
                work_code = row[self.column_map['work_code']]
                self.app.log_message(self.log_display, f"--- Processing {i+1}/{total}: WC={work_code} ---")
                self.app.after(0, self.update_status, f"Processing {i+1}/{total}: {work_code}", (i+1)/total)
                self._process_single_work_code(driver, row, form_config)
        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
        finally:
            self.app.after(0, self.app.log_message, self.log_display, "--- Automation Finished ---")
            self.app.after(0, self.set_ui_state, False)
            self.app.after(100, lambda: messagebox.showinfo("Complete", "IF Editor process has finished."))
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _log_result(self, work_code, job_card, status, details):
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(work_code, job_card, status, details)))
        level = "success" if status.lower() == "success" else "error" if status.lower() == "failed" else "info"
        self.app.log_message(self.log_display, f"'{work_code}' - {status}: {details}", level)
        
    def _scroll_to(self, driver, element):
        """Helper to scroll an element into view."""
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
        time.sleep(0.3) # Wait for scroll

    def _process_single_work_code(self, driver, row, cfg):
        work_code, beneficiary_type, job_card = row[self.column_map['work_code']], row[self.column_map['beneficiary_type']], row[self.column_map['job_card']]
        try:
            current_year, wait = datetime.now().year, WebDriverWait(driver, 20)
            mode = cfg.get('automation_mode')
            driver.get(config.IF_EDIT_CONFIG["url"])
            time.sleep(1)

            work_code_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtwrksearchkey")))
            self._scroll_to(driver, work_code_input)
            work_code_input.send_keys(work_code); work_code_input.send_keys(Keys.TAB); time.sleep(3)

            try:
                work_name_ddl = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlworkName")))
                self._scroll_to(driver, work_name_ddl)
                Select(work_name_ddl).select_by_index(1)
            except Exception:
                self._log_result(work_code, job_card, "Skipped", "Job card not found, skipped")
                return

            time.sleep(2)

            # --- Page 1 ---
            if mode == "Full Process (All Pages)":
                self.app.log_message(self.log_display, "Page 1: Entering work details...")
                
                est_pd_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_TxtEstpd")))
                self._scroll_to(driver, est_pd_input)
                est_pd_input.clear()
                est_pd_input.send_keys(cfg.get("estimated_pd", "0"))

                beneficiaries_input = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txt_nofobenificary")
                self._scroll_to(driver, beneficiaries_input)
                beneficiaries_input.send_keys(cfg.get("beneficiaries_count", "0"))
                beneficiaries_input.send_keys(Keys.TAB)
                time.sleep(2)

                try:
                    job_card_ddl = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_grdData_ctl02_ddljobcard")))
                    self._scroll_to(driver, job_card_ddl)
                    Select(job_card_ddl).select_by_value(job_card)
                except Exception:
                    self._log_result(work_code, job_card, "Skipped", "Job card not found, skipped")
                    return
                time.sleep(2)

                benef_type_ddl = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlTypeBenif")
                self._scroll_to(driver, benef_type_ddl)
                Select(benef_type_ddl).select_by_visible_text(beneficiary_type)
                
                present_status_ddl = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlpresentstatus")
                self._scroll_to(driver, present_status_ddl)
                Select(present_status_ddl).select_by_visible_text("Not Exist")

                if cfg['run_convergence'] == 1:
                    radio_yes = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_UCconverg_rblConverg_0")
                    self._scroll_to(driver, radio_yes)
                    radio_yes.click(); time.sleep(1)

                    scheme_type_ddl = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_UCconverg_ddlSchemeType1")
                    self._scroll_to(driver, scheme_type_ddl)
                    Select(scheme_type_ddl).select_by_visible_text(cfg['convergence_scheme_type']); time.sleep(1)
                    
                    scheme_name_ddl = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_UCconverg_ddlScheme1")
                    self._scroll_to(driver, scheme_name_ddl)
                    Select(scheme_name_ddl).select_by_visible_text(cfg["convergence_scheme_name"])
                else:
                    radio_no = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_UCconverg_rblConverg_1")
                    self._scroll_to(driver, radio_no)
                    radio_no.click()

            update_btn_p1 = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btupdate")))
            self._scroll_to(driver, update_btn_p1)
            update_btn_p1.click()

            if cfg['run_convergence'] == 0:
                self._log_result(work_code, job_card, "Success", "Page 1 submitted (non-convergence).")
                return

            # --- Page 2 ---
            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtsanctionno")))
            if mode in ["Full Process (All Pages)", "Page 2 & 3 Only"]:
                self.app.log_message(self.log_display, "Page 2: Entering sanction details...")

                def fill(id, val):
                    elem = wait.until(EC.presence_of_element_located((By.ID, id)))
                    self._scroll_to(driver, elem)
                    elem.clear()
                    elem.send_keys(val if val.strip() else "0")

                fill("ctl00_ContentPlaceHolder1_txtsanctionno", cfg.get("sanction_no", "0").format(year=current_year))
                fill("ctl00_ContentPlaceHolder1_txtsanctionDate", cfg.get("sanction_date", "0").format(year=current_year))
                fill("ctl00_ContentPlaceHolder1_txtEstTimecompWork", cfg.get("est_time_completion", "0"))
                fill("ctl00_ContentPlaceHolder1_txtAvglabourperday", cfg.get("avg_labour_per_day", "0"))
                fill("ctl00_ContentPlaceHolder1_txtExcpectedmanday", cfg.get("expected_mandays", "0"))
                fill("ctl00_ContentPlaceHolder1_txtTechsancAmt", cfg.get("tech_sanction_amount", "0"))
                fill("ctl00_ContentPlaceHolder1_Sanc_Tech_Labr_Unskilled", cfg.get("unskilled_labour_cost", "0"))
                fill("ctl00_ContentPlaceHolder1_Est_Cost_Material", cfg.get("mgnrega_material_cost", "0"))
                fill("ctl00_ContentPlaceHolder1_skilled", cfg.get("skilled_labour_cost", "0"))
                fill("ctl00_ContentPlaceHolder1_txt_semiskilled", cfg.get("semi_skilled_labour_cost", "0"))
                fill("ctl00_ContentPlaceHolder1_scheme_val1", cfg.get("scheme1_cost", "0"))
                fill("ctl00_ContentPlaceHolder1_txtFinsan_no", cfg.get("fin_sanction_no", "0").format(year=current_year))
                fill("ctl00_ContentPlaceHolder1_sanc_fin_date", cfg.get("fin_sanction_date", "0").format(year=current_year))
                fill("ctl00_ContentPlaceHolder1_sanc_fin_Amt", cfg.get("fin_sanction_amount", "0"))

                fin_scheme_input = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_fin_scheme1")
                self._scroll_to(driver, fin_scheme_input)
                fin_scheme_input.clear()
                fin_scheme_input.send_keys(cfg.get("fin_scheme_input", "0"))
                fin_scheme_input.send_keys(Keys.TAB)
                time.sleep(1)

            try:
                update_btn_p2 = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btUpdate")
            except NoSuchElementException:
                update_btn_p2 = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btSave")
            
            self._scroll_to(driver, update_btn_p2)
            driver.execute_script("arguments[0].click();", update_btn_p2)

            # --- Page 3 ---
            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlAct")))
            
            existing_activity_codes = {el.text for el in driver.find_elements(By.XPATH, "//span[starts-with(@id, 'ctl00_ContentPlaceHolder1_grdDisplayAct_') and contains(@id, '_lblActCode')]")}
            self.app.log_message(self.log_display, f"Page 3: Found existing activities: {existing_activity_codes or 'None'}")
            
            activities_raw = cfg.get("activities_list", "").strip()
            if activities_raw:
                for act_data in [line.strip().split(',') for line in activities_raw.splitlines() if line.strip()]:
                    if self.app.stop_events[self.automation_key].is_set(): break
                    if len(act_data) != 3: self.app.log_message(self.log_display, f"  > Skipping invalid activity line: {act_data}", "warning"); continue
                    
                    code_keyword, price, qty = act_data[0].strip(), act_data[1].strip(), act_data[2].strip()
                    
                    act_dropdown_element = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlAct")
                    act_select = Select(act_dropdown_element)
                    found_option = next((opt for opt in act_select.options if code_keyword in opt.get_attribute('value')), None)
                    
                    if not found_option:
                        self.app.log_message(self.log_display, f"  > Activity with keyword '{code_keyword}' not found in dropdown.", "warning")
                        continue
                    
                    actual_code = found_option.get_attribute('value')

                    if actual_code in existing_activity_codes: 
                        self.app.log_message(self.log_display, f"  > Skipping existing activity: {actual_code}"); continue
                    
                    self.app.log_message(self.log_display, f"  > Adding activity: {actual_code}")
                    try:
                        act_dropdown = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlAct")))
                        self._scroll_to(driver, act_dropdown)
                        Select(act_dropdown).select_by_value(actual_code); wait.until(EC.staleness_of(act_dropdown))
                        
                        price_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtAct_UnitPrice")))
                        self._scroll_to(driver, price_input)
                        price_input.send_keys(price); driver.find_element(By.TAG_NAME, 'body').click(); wait.until(EC.staleness_of(price_input))
                        
                        qty_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtAct_Qty")))
                        self._scroll_to(driver, qty_input)
                        qty_input.send_keys(qty); qty_input.send_keys(Keys.TAB); wait.until(EC.staleness_of(qty_input))
                        
                        save_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btsave")))
                        self._scroll_to(driver, save_btn)
                        save_btn.click(); wait.until(EC.staleness_of(save_btn))
                        
                        self.app.log_message(self.log_display, f"   - Successfully added activity '{actual_code}'.", "success"); existing_activity_codes.add(actual_code)
                    except Exception as act_e: self.app.log_message(self.log_display, f"   - ERROR adding activity '{actual_code}': {str(act_e).splitlines()[0]}", "error")

            materials_raw = cfg.get("materials_list", "").strip()
            if materials_raw:
                self.app.log_message(self.log_display, "Page 3: Adding materials...")

                # --- FINAL LOGIC: Using precise startswith matching and original user flow ---
                
                # 1. Get initial state
                wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_grdDisplayMat")))
                existing_material_names = {el.text.strip() for el in driver.find_elements(By.XPATH, "//span[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '_lblmatname')]")}
                self.app.log_message(self.log_display, f"Page 3: Found existing materials: {existing_material_names or 'None'}")
                
                mat_dropdown_element = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlMatname")
                all_options = Select(mat_dropdown_element).options
                
                # 2. Prepare a clean "to-do" list
                materials_to_process = []
                for line in materials_raw.splitlines():
                    if not line.strip(): continue
                    parts = line.strip().split(',')
                    if len(parts) != 3:
                        self.app.log_message(self.log_display, f"  > Skipping invalid UI line: {line}", "warning"); continue
                    
                    # Clean the user input keyword
                    keyword = parts[0].strip().split('$$')[0]
                    price, qty = parts[1].strip(), parts[2].strip()

                    # Find the option using the precise startswith check
                    found_option = next((opt for opt in all_options if opt.text.strip().startswith(keyword)), None)
                    
                    if not found_option:
                        self.app.log_message(self.log_display, f"  > Material starting with '{keyword}' not found in dropdown.", "warning"); continue
                        
                    actual_name = found_option.text.split('$$')[0].strip()
                    if actual_name not in existing_material_names:
                        materials_to_process.append({'option_text': found_option.text, 'name': actual_name, 'price': price, 'qty': qty})
                    else:
                        self.app.log_message(self.log_display, f"  > Skipping existing material: {actual_name}")

                # 3. Loop through the filtered list using the original proven flow
                is_first_addition = not existing_material_names
                for mat_info in materials_to_process:
                    if self.app.stop_events[self.automation_key].is_set(): break
                    
                    self.app.log_message(self.log_display, f"  > Processing material: {mat_info['name']} | Price: {mat_info['price']} | Qty: {mat_info['qty']}")
                    
                    try:
                        if is_first_addition:
                            # --- INSERT FLOW ---
                            mat_dropdown = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlMatname")))
                            self._scroll_to(driver, mat_dropdown)
                            Select(mat_dropdown).select_by_visible_text(mat_info['option_text'])

                            price_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtMat_UnitPrice")))
                            self._scroll_to(driver, price_input); price_input.send_keys(mat_info['price'])
                            driver.find_element(By.TAG_NAME, "body").click(); wait.until(EC.staleness_of(price_input))

                            qty_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtMat_Qty")))
                            self._scroll_to(driver, qty_input); qty_input.send_keys(mat_info['qty'])
                            driver.find_element(By.TAG_NAME, "body").click(); wait.until(EC.staleness_of(qty_input))

                            save_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btsave")))
                            self._scroll_to(driver, save_btn); save_btn.click(); wait.until(EC.staleness_of(save_btn))
                            
                            self.app.log_message(self.log_display, f"   - Inserted first material '{mat_info['name']}'.", "success")
                            is_first_addition = False 
                        else:
                            # --- EDIT FLOW (User's original logic) ---
                            edit_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, \"ctl00$ContentPlaceHolder1$grdDisplayMat','Edit$0\")]")))
                            self._scroll_to(driver, edit_link); edit_link.click(); time.sleep(1)
                            
                            driver.find_element(By.TAG_NAME, "body").click(); time.sleep(0.5)

                            mat_dropdown = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlMatname")))
                            self._scroll_to(driver, mat_dropdown)
                            Select(mat_dropdown).select_by_visible_text(mat_info['option_text'])

                            price_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtMat_UnitPrice")))
                            self._scroll_to(driver, price_input); price_input.send_keys(mat_info['price'])
                            driver.find_element(By.TAG_NAME, "body").click(); wait.until(EC.staleness_of(price_input))

                            qty_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtMat_Qty")))
                            self._scroll_to(driver, qty_input); qty_input.send_keys(mat_info['qty'])
                            driver.find_element(By.TAG_NAME, "body").click(); wait.until(EC.staleness_of(qty_input))

                            update_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, \"ctl00$ContentPlaceHolder1$grdDisplayMat$ctl02$ctl00\")]")))
                            self._scroll_to(driver, update_link); update_link.click(); wait.until(EC.staleness_of(update_link))

                            save_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btsave")))
                            self._scroll_to(driver, save_btn); save_btn.click(); wait.until(EC.staleness_of(save_btn))

                            self.app.log_message(self.log_display, f"   - Edited & saved material '{mat_info['name']}'.", "success")

                    except Exception as mat_e:
                        error_msg = str(mat_e).splitlines()[0].strip()
                        self.app.log_message(self.log_display, f"   - ERROR processing material '{mat_info['name']}': {error_msg}", "error")
                        break 

            self._log_result(work_code, job_card, "Success", "All pages processed.")
        except Exception as e:
            self._log_result(work_code, job_card, "Failed", str(e).splitlines()[0])

