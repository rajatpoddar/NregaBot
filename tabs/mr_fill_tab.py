# tabs/mr_fill_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, random, time, sys, subprocess, re, json
from datetime import datetime
from fpdf import FPDF
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException, NoAlertPresentException
import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class MrFillTab(BaseAutomationTab):
    """
    This Tab handles filling Muster Roll (MR) attendance.
    It selects Panchayat, searches Work Code, selects MR,
    marks specified holiday columns, and then saves.
    """
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="mr_fill")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        
        # --- Config file for saving inputs ---
        self.config_file = self.app.get_data_path("mr_fill_inputs.json")
        self.config_vars = {} # Dictionary to hold UI variables

        # --- UI Variables ---
        self.panchayat_var = ctk.StringVar()
        self.manual_mode_var = ctk.BooleanVar(value=False)
        self.holiday_cols_var = ctk.StringVar()
        
        # Store variables for easy save/load
        self.config_vars["panchayat_name"] = self.panchayat_var
        self.config_vars["holiday_cols"] = self.holiday_cols_var
        self.config_vars["manual_mode"] = self.manual_mode_var

        self._create_widgets()
        self._load_inputs() # Load saved inputs on startup

    def _create_widgets(self):
        """Creates all the UI elements for the tab."""
        
        # --- Configuration Frame ---
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Panchayat Entry
        panchayat_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        panchayat_frame.grid(row=0, column=0, sticky='ew', padx=15, pady=(10,0))
        ctk.CTkLabel(panchayat_frame, text="Panchayat Name", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        self.panchayat_entry = AutocompleteEntry(
            panchayat_frame, 
            textvariable=self.panchayat_var, # Link to variable
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app,
            history_key="panchayat_name"
        )
        self.panchayat_entry.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(panchayat_frame, text="e.g., Palojori (skip if using GP login)", text_color="gray50").pack(anchor='w')
        
        # Holiday Columns Entry
        holiday_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        holiday_frame.grid(row=0, column=1, sticky='ew', padx=15, pady=(10,0))
        ctk.CTkLabel(holiday_frame, text="Mark Holiday Columns (comma-separated)", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        self.holiday_cols_entry = ctk.CTkEntry(holiday_frame, textvariable=self.holiday_cols_var) # Link to variable
        self.holiday_cols_entry.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(holiday_frame, text="e.g., 7, 14 (will mark 7th and 14th columns as holiday)", text_color="gray50").pack(anchor='w')

        # Manual Mode Checkbox
        self.manual_mode_checkbox = ctk.CTkCheckBox(
            controls_frame, 
            text="Manual Mode (Pause after marking holidays for you to mark absentees)",
            variable=self.manual_mode_var # Link to variable
        )
        self.manual_mode_checkbox.grid(row=1, column=0, columnspan=2, sticky='w', padx=15, pady=(10,0))

        # Action Buttons (Start, Stop, Reset)
        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(15, 15))

        # --- Data Tabs (Work Codes, Results, Logs) ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=1, column=0, sticky="nsew")
        work_codes_frame = data_notebook.add("Work Codes")
        results_frame = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # Work Codes Tab
        work_codes_frame.grid_columnconfigure(0, weight=1); work_codes_frame.grid_rowconfigure(1, weight=1)
        wc_controls_frame = ctk.CTkFrame(work_codes_frame, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew')
        
        clear_button = ctk.CTkButton(wc_controls_frame, text="Clear", width=80, command=lambda: self.work_key_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', pady=(5,0), padx=(0,5))
        
        extract_button = ctk.CTkButton(wc_controls_frame, text="Extract from Text", width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_key_text))
        extract_button.pack(side='right', pady=(5,0), padx=(0, 5))
        
        self.work_key_text = ctk.CTkTextbox(work_codes_frame, wrap=tkinter.WORD)
        self.work_key_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # Results Tab
        results_frame.grid_columnconfigure(0, weight=1); results_frame.grid_rowconfigure(1, weight=1)
        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10))
        
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side='left')
        self.export_format_menu = ctk.CTkOptionMenu(export_controls_frame, width=130, values=["PDF (.pdf)", "CSV (.csv)"], command=self._on_format_change)
        self.export_format_menu.pack(side='left', padx=5)
        self.export_filter_menu = ctk.CTkOptionMenu(export_controls_frame, width=150, values=["Export All", "Success Only", "Failed Only"])
        self.export_filter_menu.pack(side='left', padx=(0, 5))

        # Results Treeview
        cols = ("Workcode", "MR No.", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Workcode", width=200)
        self.results_tree.column("MR No.", width=80, anchor='center')
        self.results_tree.column("Status", anchor='center', width=100)
        self.results_tree.column("Details", width=300)
        self.results_tree.column("Timestamp", width=100, anchor='center')
        
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree); self._setup_treeview_sorting(self.results_tree)

    def load_data_from_dashboard(self, workcodes: str, panchayat_name: str):
        """Public method to receive data from the Dashboard Report tab."""
        # Set Panchayat Name
        self.panchayat_var.set(panchayat_name)
        
        # Set Work Codes
        self.work_key_text.configure(state="normal")
        self.work_key_text.delete("1.0", tkinter.END)
        self.work_key_text.insert("1.0", workcodes)
        self.work_key_text.configure(state="disabled")
        
        self.app.log_message(self.log_display, f"Loaded {len(workcodes.splitlines())} workcodes and panchayat '{panchayat_name}' from Dashboard Report.", "info")
    # --- END NEW METHOD ---
    
    # --- Save and Load Inputs ---
    def _save_inputs(self, cfg):
        """Saves the current UI inputs to a JSON file."""
        try:
            with open(self.config_file, 'w') as f: 
                json.dump(cfg, f, indent=4)
        except Exception as e: 
            self.app.log_message(self.log_display, f"Could not save inputs: {e}", "warning")

    def _load_inputs(self):
        """Loads inputs from the JSON file on startup."""
        saved_data = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f: 
                    saved_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e: 
                self.app.log_message(self.log_display, f"Could not load inputs: {e}", "warning")
        
        # Set values from saved_data, falling back to defaults
        self.panchayat_var.set(saved_data.get("panchayat_name", ""))
        self.holiday_cols_var.set(saved_data.get("holiday_cols", ""))
        self.manual_mode_var.set(saved_data.get("manual_mode", False))
    # --- END ---

    def _on_format_change(self, selected_format):
        """Disables the filter menu for CSV format."""
        if "CSV" in selected_format:
            self.export_filter_menu.configure(state="disabled")
        else:
            self.export_filter_menu.configure(state="normal")

    def set_ui_state(self, running: bool):
        """Enables/disables UI elements based on automation state."""
        self.set_common_ui_state(running) # Handles Start, Stop, Reset
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.holiday_cols_entry.configure(state=state)
        self.manual_mode_checkbox.configure(state=state)
        self.work_key_text.configure(state=state)
        self.export_button.configure(state=state)
        self.export_format_menu.configure(state=state)
        self.export_filter_menu.configure(state=state)
        if state == "normal": self._on_format_change(self.export_format_menu.get())

    def reset_ui(self):
        """Resets the form to its default state."""
        if messagebox.askokcancel("Reset Form?", "Clear all inputs, results, and logs?"):
            self._load_inputs() # Load saved inputs
            # Clear text boxes and results
            self.work_key_text.configure(state="normal"); self.work_key_text.delete("1.0", tkinter.END); self.work_key_text.configure(state="disabled")
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.app.log_message(self.log_display, "Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
            
    def start_automation(self):
        """Validates inputs and starts the automation thread."""
        
        # Get inputs from variables and save them
        cfg = {
            "panchayat_name": self.panchayat_var.get().strip(),
            "holiday_cols": self.holiday_cols_var.get().strip(),
            "manual_mode": self.manual_mode_var.get()
        }
        
        self.work_key_text.configure(state="normal") # Enable to read
        work_keys = [line.strip() for line in self.work_key_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]
        self.work_key_text.configure(state="disabled") # Disable again

        if not work_keys: 
            messagebox.showerror("Input Error", "No work keys (Search Key) provided."); 
            return
            
        self._save_inputs(cfg) # Save the current inputs
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(cfg, work_keys))
        
    def run_automation_logic(self, cfg, work_keys):
        """Main automation logic that runs in a separate thread."""
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, lambda: [self.results_tree.delete(item) for item in self.results_tree.get_children()])
        self.app.clear_log(self.log_display)
        self.app.log_message(self.log_display, "Starting MR Fill (Attendance) processing...")
        self.app.after(0, self.app.set_status, "Running MR Fill...")
        
        # --- 1. Get inputs from the passed cfg dictionary ---
        panchayat_name = cfg["panchayat_name"]
        holiday_cols_str = cfg["holiday_cols"]
        is_manual_mode = cfg["manual_mode"]
        
        holiday_cols = [col.strip() for col in holiday_cols_str.split(',') if col.strip().isdigit()]

        try:
            driver = self.app.get_driver()
            if not driver: return
            
            wait = WebDriverWait(driver, 15)
            
            # --- 2. Navigate to Page FIRST ---
            # --- MODIFICATION: Navigate to the URL before trying to select Panchayat ---
            driver.get(config.MR_FILL_CONFIG["url"])
            
            # --- 3. Panchayat Selection Logic (with 2 attempts) ---
            panchayat_selected = False
            for attempt in range(2):
                if self.app.stop_events[self.automation_key].is_set(): break
                try:
                    # Try to find dropdown with a 3-second wait
                    panchayat_select_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, "ddlPanchayat")))
                    
                    if not panchayat_name: 
                        messagebox.showerror("Input Error", "Panchayat name is required for Block Login."); 
                        self.app.after(0, self.set_ui_state, False); return

                    panchayat_select = Select(panchayat_select_element)
                    match = next((opt.text for opt in panchayat_select.options if panchayat_name.strip().lower() in opt.text.lower()), None)
                    if not match: raise ValueError(f"Panchayat '{panchayat_name}' not found.")
                    
                    panchayat_select.select_by_visible_text(match)
                    self.app.update_history("panchayat_name", panchayat_name) # Save to autocomplete history
                    self.app.log_message(self.log_display, f"Successfully selected Panchayat: {match}", "success")
                    time.sleep(2) # Wait for page to reload
                    panchayat_selected = True
                    break # Exit loop on success
                
                except TimeoutException:
                    self.app.log_message(self.log_display, f"Panchayat dropdown not found (Attempt {attempt + 1}/2).", "info")
                    time.sleep(1) # Wait before retrying
                
            if not panchayat_selected and not self.app.stop_events[self.automation_key].is_set():
                self.app.log_message(self.log_display, "Panchayat selection not found/required (GP Login). Proceeding...", "info")
            # --- End Panchayat Logic ---

            # --- 4. Work Key Loop ---
            total = len(work_keys)
            for i, work_key in enumerate(work_keys, 1):
                if self.app.stop_events[self.automation_key].is_set(): 
                    self.app.log_message(self.log_display, "Automation stopped by user.", "warning"); break
                
                self.app.after(0, self.update_status, f"Processing {i}/{total}: {work_key}", (i/total))
                
                self._process_single_work_code(driver, wait, work_key, holiday_cols, is_manual_mode)
                
            if not self.app.stop_events[self.automation_key].is_set(): 
                messagebox.showinfo("Completed", "Automation finished! Check the 'Results' tab for details.")
        
        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
            messagebox.showerror("MR Fill Error", f"An error occurred: {e}")
        
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished.", 1.0)
            self.app.after(0, self.app.set_status, "Automation Finished")
            
    def _process_single_work_code(self, driver, wait, work_key, holiday_cols, is_manual_mode):
        """
        Processes a single work code and its first available MR.
        BACKGROUND-SAFE UPDATE: Uses JS for inputs/clicks to support Minimized Browser.
        """
        current_mr_no = "N/A"
        try:
            # Dismiss any previous alerts
            try: driver.switch_to.alert.accept()
            except NoAlertPresentException: pass
            
            # Navigate to the page if not already on it
            if driver.current_url != config.MR_FILL_CONFIG["url"]:
                driver.get(config.MR_FILL_CONFIG["url"])

            # --- 1. Work Code Search (Background Safe) ---
            self.app.after(0, self.app.set_status, f"Searching for Work Key: {work_key}")
            
            # Use Presence Check
            search_box = wait.until(EC.presence_of_element_located((By.ID, "txtSearch")))
            # Use JS to set value (Works in background)
            driver.execute_script("arguments[0].value = arguments[1];", search_box, work_key)
            
            # Use JS Click
            search_btn = wait.until(EC.presence_of_element_located((By.ID, "ImgbtnSearch")))
            driver.execute_script("arguments[0].click();", search_btn)
            
            time.sleep(1) # Wait for search

            # Check for 'lblmsg' error (like Geotag)
            try:
                error_span = driver.find_element(By.ID, "lblmsg")
                # Use innerText for background reading
                error_text = error_span.get_attribute("innerText").strip()
                if error_text: 
                    raise ValueError(f"{error_text}")
            except NoSuchElementException:
                pass

            # --- 2. Work Code Select ---
            self.app.after(0, self.app.set_status, f"Selecting Work Code...")
            work_code_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlWorkCode"))))
            if len(work_code_select.options) <= 1: 
                raise IndexError("Work code not found after search.")
            work_code_select.select_by_index(1) # Select the first work code
            time.sleep(1.5) # Wait for MR list to load

            # --- 3. MR No. Select ---
            self.app.after(0, self.app.set_status, f"Selecting MR No...")
            msr_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlMsrNo"))))
            if len(msr_select.options) <= 1: 
                raise IndexError("Muster Roll (MR) not found for this work code.")
            
            current_mr_no = msr_select.options[1].text # Store the first MR No.
            msr_select.select_by_index(1)
            self.app.log_message(self.log_display, f"Processing Work Key: {work_key}, MR No: {current_mr_no}")
            
            # Wait for table (Check for Save button presence)
            wait.until(EC.presence_of_element_located((By.ID, "btnsave")))
            time.sleep(1) 

            # --- 4. Mark Holidays ---
            if holiday_cols:
                self.app.after(0, self.app.set_status, f"Marking holidays for MR: {current_mr_no}")
                self.app.log_message(self.log_display, f"Marking holiday columns: {', '.join(holiday_cols)}")
                for col_num in holiday_cols:
                    try:
                        holiday_checkbox_id = f"c_p{col_num}"
                        # Try to find check box
                        checkbox = driver.find_element(By.ID, holiday_checkbox_id)
                        if not checkbox.is_selected():
                            # JS Click is safest for background
                            driver.execute_script("arguments[0].click();", checkbox)
                    except NoSuchElementException:
                        self.app.log_message(self.log_display, f"Warning: Holiday column {col_num} not found.", "warning")
            
            # --- Fill 'Work Start Date' (Background Safe) ---
            try:
                work_start_input = driver.find_element(By.ID, "txtWrkStartDate")
                # Check if empty
                if not work_start_input.get_attribute("value").strip():
                    date_from_val = driver.find_element(By.ID, "txtDatefrm").get_attribute("value")
                    if date_from_val:
                        # JS Set Value
                        driver.execute_script("arguments[0].value = arguments[1];", work_start_input, date_from_val)
                        self.app.log_message(self.log_display, f"Auto-filled Work Start Date: {date_from_val}", "info")
            except Exception as e:
                self.app.log_message(self.log_display, f"Warning: Could not auto-fill date: {e}", "warning")

            # --- 5. Manual Mode Logic ---
            if is_manual_mode:
                self.app.after(0, self.app.set_status, f"Manual Mode: Pausing for MR: {current_mr_no}")
                self.app.log_message(self.log_display, f"Manual Mode: Pausing for MR: {current_mr_no}. Please mark absentees and click 'Save'.", "info")
                try:
                    alert = WebDriverWait(driver, 600).until(EC.alert_is_present())
                    alert_text = alert.text 
                    alert.accept()
                    self.app.log_message(self.log_display, f"User action detected. Bot handled first alert: '{alert_text}'", "info")
                except TimeoutException:
                    raise ValueError("Manual mode timed out. User did not click 'Save'.")

            else:
                # --- 6. Auto-Submit Logic (Background Safe) ---
                self.app.after(0, self.app.set_status, f"Auto-submitting MR: {current_mr_no}")
                self.app.log_message(self.log_display, "Auto-submitting attendance...")
                
                # JS Click for Save
                save_btn = driver.find_element(By.ID, "btnsave")
                driver.execute_script("arguments[0].click();", save_btn)
                
                # Handle first confirmation alert
                WebDriverWait(driver, 10).until(EC.alert_is_present()).accept()

            # --- 7. Final Alert Handling ---
            self.app.after(0, self.app.set_status, f"Waiting for final confirmation...")
            outcome_found = False
            for _ in range(3): 
                try:
                    final_alert = driver.switch_to.alert
                    final_alert_text = final_alert.text.strip()
                    final_alert.accept()
                    
                    if "Muster Roll Saved Successfully" in final_alert_text or "Muster Roll has been saved" in final_alert_text:
                        self._log_result(work_key, current_mr_no, "Success", final_alert_text)
                    else:
                        self._log_result(work_key, current_mr_no, "Failed", f"Unknown Alert: {final_alert_text}")
                    
                    outcome_found = True; break
                except NoAlertPresentException:
                    time.sleep(1)
            
            if not outcome_found: 
                self._log_result(work_key, current_mr_no, "Failed", "No final confirmation alert found (Timeout).")

        except ValueError as e:
            error_message = str(e)
            self._log_result(work_key, current_mr_no, "Failed", error_message)
        
        except (IndexError, NoSuchElementException) as e:
            display_msg = str(e)
            if "Muster Roll (MR) not found" in display_msg: details = "MR not found (or not available)."
            elif "Work code not found" in display_msg: details = "Work Code not found."
            else: details = f"Element not found: {e}"
            self._log_result(work_key, current_mr_no, "Failed", details)

        except TimeoutException as e:
            self.app.log_message(self.log_display, f"Timeout processing {work_key}: {e}", "error")
            self._log_result(work_key, current_mr_no, "Failed", "Page timed out or element not found.")
        
        except Exception as e:
            self.app.log_message(self.log_display, f"Critical error processing {work_key}: {e}", "error")
            self._log_result(work_key, current_mr_no, "Failed", f"CRITICAL ERROR: {type(e).__name__}")
        
    # ... inside MrFillTab class ...

    # 1. FIX: Add this method to handle the Retry button correctly
    def retry_logic_handler(self):
        """Override default retry logic to map to the correct text widget (work_key_text)."""
        self.retry_failed_automation(self.work_key_text)

    # 2. FIX: Update this method to apply the 'success' tag for green color
    def _log_result(self, work_key, mr_no, status, msg):
        """Logs the result to the log display and the results tree."""
        level = "success" if status.lower() == "success" else "error"
        timestamp = datetime.now().strftime("%H:%M:%S")
        details = msg.replace("\n", " ").replace("\r", " ")
        
        self.app.log_message(self.log_display, f"'{work_key}' (MR: {mr_no}) - {status.upper()}: {details}", level=level)
        
        # --- FIX: Explicitly apply 'success' tag for green styling ---
        if 'success' in status.lower():
            tags = ('success',)
        else:
            tags = ('failed',)
        
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(work_key, mr_no, status.upper(), details, timestamp), tags=tags))

    def export_report(self):
        """Exports the data in the results tree to PDF or CSV."""
        export_format = self.export_format_menu.get()
        panchayat_name = self.panchayat_var.get() # Get from variable

        if not panchayat_name:
            messagebox.showwarning("Input Needed", "Please enter a Panchayat Name to include in the report filename.", parent=self)
            return

        if "CSV" in export_format:
            safe_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"MR_Fill_Report_{safe_name}_{timestamp}.csv"
            self.export_treeview_to_csv(self.results_tree, default_filename)
            return
            
        data, file_path = self._get_filtered_data_and_filepath(export_format)
        if not data: return

        if "PDF" in export_format:
            self._handle_pdf_export(data, file_path)

    def _get_filtered_data_and_filepath(self, export_format):
        """Filters data based on UI selection and gets a save file path from the user."""
        all_items = self.results_tree.get_children()
        if not all_items: messagebox.showinfo("No Data", "There are no results to export."); return None, None
        panchayat_name = self.panchayat_var.get() # Get from variable
        if not panchayat_name: messagebox.showwarning("Input Needed", "Please enter a Panchayat Name for the report title."); return None, None

        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in all_items:
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[2].upper() # Status column
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status: data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status: data_to_export.append(row_values)
        if not data_to_export: messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'."); return None, None

        safe_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        file_details = {
            "PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")], "title": "Save Report as PDF"},
        }
        details = file_details[export_format] # Assume PDF
        filename = f"MR_Fill_Report_{safe_name}_{timestamp}{details['ext']}"

        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_user_downloads_path(), initialfile=filename, title=details['title'])
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, file_path):
        """Generates the PDF report."""
        try:
            headers = self.results_tree['columns']
            # ("Workcode", "MR No.", "Status", "Details", "Timestamp")
            col_widths = [60, 25, 30, 130, 25] # Widths for A4 Landscape
            title = f"MR Fill (Attendance) Report: {self.panchayat_var.get()}" # Get from variable
            report_date = datetime.now().strftime('%d %b %Y')
            
            success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
            
            if success:
                if messagebox.askyesno("Success", f"PDF Report exported to:\n{file_path}\n\nDo you want to open the file?"):
                    if sys.platform == "win32":
                        os.startfile(file_path)
                    else:
                        subprocess.call(['open', file_path])
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to create PDF file.\n\nError: {e}")

