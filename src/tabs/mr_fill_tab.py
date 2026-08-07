# tabs/mr_fill_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, random, time, sys, subprocess, re, json
from datetime import datetime
from fpdf import FPDF
from src import config
from .base_tab import BaseAutomationTab

from src.utils import get_logger, truncate_workcode
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoAlertPresentException, NoSuchElementException, TimeoutException  # noqa: F401


logger = get_logger()

class MrFillTab(BaseAutomationTab):
    """
    This Tab handles filling Muster Roll (MR) attendance.
    It selects Panchayat, searches Work Code, selects MR,
    marks specified holiday columns, and then saves.
    """
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="mr_fill")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(3, weight=1)
        
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
    def _create_widgets(self) -> None:

        """Creates all the UI elements for the tab."""

        # --- Header / intro card (pending-bills style) ---
        self._create_header_card(self, "📝", "MR Fill",
                                 "Mark holiday columns and fill Muster Roll attendance for the selected Panchayat.",
                                 icon_key="emoji_mr_fill")

        # --- Configuration Card ---
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        controls_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Panchayat Entry
        panchayat_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        panchayat_frame.grid(row=0, column=0, sticky='ew', padx=15, pady=(12,0))
        ctk.CTkLabel(panchayat_frame, text="Panchayat Name", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(panchayat_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(panchayat_frame, text="e.g., Palojori (skip if using GP login)", text_color="gray50").pack(anchor='w')
        
        # Holiday Columns Entry
        holiday_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        holiday_frame.grid(row=0, column=1, sticky='ew', padx=15, pady=(12,0))
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
        self.manual_mode_checkbox.grid(row=1, column=0, columnspan=2, sticky='w', padx=15, pady=(10,15))

        # Action Buttons (Start, Stop, Reset) — outside the card
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        # --- Data Tabs (Work Codes, Results, Logs) ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
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
        self.export_button = ctk.CTkButton(export_controls_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side='left')

        # Results Treeview
        cols = ("Panchayat", "Workcode", "MR No.", "Status", "Details", "Timestamp")
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
        
        self.log_info(f"Loaded {len(workcodes.splitlines())} workcodes and panchayat '{panchayat_name}' from Dashboard Report.")    # --- END NEW METHOD ---
    
    # --- Save and Load Inputs ---
    def _save_inputs(self, cfg):
        """Saves the current UI inputs to DB."""
        try:
            self.app.history_manager.save_tab_inputs_batch("mr_fill", cfg)
        except Exception as e: 
            self.log_warning(f"Could not save inputs: {e}")
    def _load_inputs(self):
        """Loads inputs from DB on startup."""
        saved_data = self.app.history_manager.get_tab_inputs("mr_fill")
        
        # Set values from saved_data, falling back to defaults
        self.panchayat_var.set(saved_data.get("panchayat_name", ""))
        self.holiday_cols_var.set(saved_data.get("holiday_cols", ""))
        # Coerce to a real bool: saved data may hold "", "True", "False", "1", etc.
        self.manual_mode_var.set(str(saved_data.get("manual_mode", False)).strip().lower() in ("1", "true", "yes", "on"))
    # --- END ---

    def _on_format_change(self, selected_format):
        """Disables the filter menu for CSV format."""
        if "CSV" in selected_format:
            self.export_filter_menu.configure(state="disabled")
        else:
            self.export_filter_menu.configure(state="normal")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        """Enables/disables UI elements based on automation state."""
        self.set_common_ui_state(running) # Handles Start, Stop, Reset
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.holiday_cols_entry.configure(state=state)
        self.manual_mode_checkbox.configure(state=state)
        self.work_key_text.configure(state=state)
        self.export_button.configure(state=state)
    def reset_ui(self) -> None:
        """Resets the form to its default state."""
        if messagebox.askokcancel("Reset Form?", "Clear all inputs, results, and logs?"):
            self._load_inputs() # Load saved inputs
            # Clear text boxes and results
            self.work_key_text.configure(state="normal"); self.work_key_text.delete("1.0", tkinter.END); self.work_key_text.configure(state="disabled")
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
    def start_automation(self) -> None:
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
        
    # Inside tabs/mr_fill_tab.py

    def run_automation_logic(self, cfg, work_keys):
        """Main automation logic that runs in a separate thread."""
        self.app.after(0, self.set_ui_state, True)
        self.safe_tree_clear()
        self.app.clear_log(self.log_display)
        self.log_info("Starting MR Fill (Attendance) processing...")
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
            if driver.current_url != config.MR_FILL_CONFIG["url"]:
                driver.get(config.MR_FILL_CONFIG["url"])
            
            # --- 3. Initial Panchayat Selection ---
            self._ensure_panchayat_selected(driver, wait, panchayat_name)

            # --- 4. Work Key Loop ---
            total = len(work_keys)
            for i, work_key in enumerate(work_keys, 1):
                if self.is_stopped(): 
                    self.log_warning("Automation stopped by user."); break
                
                self.app.after(0, self.update_status, f"Processing {i}/{total}: {work_key}", (i/total))
                
                # PASSING PANCHAYAT NAME HERE to handle re-selection if page reloads
                self._process_single_work_code(driver, wait, work_key, holiday_cols, is_manual_mode, panchayat_name)
                
            if not self.is_stopped(): 
                self.log_info("📊 Automation finished. Check the 'Results' tab for details.")        
        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror("MR Fill Error", f"An error occurred: {e}")
        
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished.", 1.0)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _ensure_panchayat_selected(self, driver, wait, panchayat_name):
        """Helper to check and select Panchayat if it's not already selected."""
        if not panchayat_name: return # Skip if GP Login (empty name)

        try:
            panchayat_ddl = wait.until(EC.presence_of_element_located((By.ID, "ddlPanchayat")))
            select = Select(panchayat_ddl)
            
            # Check if already selected to save time
            if panchayat_name.lower() in select.first_selected_option.text.lower():
                return

            # If not selected, select it
            match = next((opt.text for opt in select.options if panchayat_name.strip().lower() in opt.text.lower()), None)
            if match:
                select.select_by_visible_text(match)
                self.log_info(f"Selected Panchayat: {match}")
                time.sleep(2) # Wait for page refresh
            else:
                self.log_warning(f"Panchayat '{panchayat_name}' not found in list.")
        except Exception:
            pass # Ignore errors for GP login scenarios

    def _process_single_work_code(self, driver, wait, work_key, holiday_cols, is_manual_mode, panchayat_name):
        """
        Processes a single work code with improved error handling for 'MR Already Filled'.
        """
        current_mr_no = "N/A"
        try:
            # Dismiss alerts if any
            try: driver.switch_to.alert.accept()
            except NoAlertPresentException: pass
            
            # 1. URL & Panchayat Safety Check
            if "Mustroll_Fill.aspx" not in driver.current_url:
                driver.get(config.MR_FILL_CONFIG["url"])
                self._ensure_panchayat_selected(driver, wait, panchayat_name)
            
            self._ensure_panchayat_selected(driver, wait, panchayat_name)

            # --- 2. Work Code Search ---
            self.app.after(0, self.app.set_status, f"Searching: {work_key}")
            
            # Check for stale element to detect page refresh later
            try: old_wc_ddl = driver.find_element(By.ID, "ddlWorkCode")
            except: old_wc_ddl = None

            search_box = wait.until(EC.presence_of_element_located((By.ID, "txtSearch")))
            driver.execute_script("arguments[0].value = arguments[1];", search_box, work_key)
            
            search_btn = wait.until(EC.presence_of_element_located((By.ID, "ImgbtnSearch")))
            driver.execute_script("arguments[0].click();", search_btn)
            
            # Wait for reload
            if old_wc_ddl:
                try: wait.until(EC.staleness_of(old_wc_ddl))
                except TimeoutException: pass
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, 'lblmsg'))
                )
            except (TimeoutException, NoSuchElementException):
                pass

            # Check for Search Error (e.g., Work code not found)
            try:
                error_span = driver.find_element(By.ID, "lblmsg")
                if error_span.text.strip(): raise ValueError(f"Site Msg: {error_span.text}")
            except NoSuchElementException: pass

            # --- 3. Select Work Code ---
            wc_ddl_elem = wait.until(EC.presence_of_element_located((By.ID, "ddlWorkCode")))
            work_code_select = Select(wc_ddl_elem)
            
            if len(work_code_select.options) <= 1:
                # Element wait handled by WebDriverWait below
                work_code_select = Select(driver.find_element(By.ID, "ddlWorkCode"))

            if len(work_code_select.options) <= 1: 
                raise IndexError("Work code not found in dropdown.")
            
            work_code_select.select_by_index(1) 
            time.sleep(1.5)

            # --- 4. Select MR No. ---
            msr_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlMsrNo"))))
            if len(msr_select.options) <= 1: 
                raise IndexError("No MR found for this Work Code.")
            
            current_mr_no = msr_select.options[1].text
            msr_select.select_by_index(1)
            
            # --- IMPROVED ERROR CHECK: Check for "Already Filled" / Date Error ---
            # The site shows: <font color="red"> No Future Dates Plz in Date To Field !!!</font>
            time.sleep(1) # Short wait for server validation
            
            # Quick check in page source first (faster than finding element)
            if "No Future Dates Plz" in driver.page_source:
                # Confirm it is the error message
                try:
                    self._find(driver, By.XPATH, "//*[contains(text(), 'No Future Dates Plz')]")
                    raise ValueError("MR Already Filled")
                except NoSuchElementException:
                    pass # Text might exist elsewhere, ignore if not in an element we expect

            # Wait for "Save" button to confirm table loaded
            try:
                wait.until(EC.presence_of_element_located((By.ID, "btnsave")))
            except TimeoutException:
                # If Save button doesn't appear, check for other errors one last time
                if "No Future Dates Plz" in driver.page_source:
                    raise ValueError("MR Already Filled")
                raise ValueError("Table did not load (Timeout)")

            time.sleep(0.5)

            # --- 5. Mark Holidays ---
            if holiday_cols:
                self.app.after(0, self.app.set_status, f"Marking Holidays...")
                for col_num in holiday_cols:
                    try:
                        chk = driver.find_element(By.ID, f"c_p{col_num}")
                        if not chk.is_selected(): driver.execute_script("arguments[0].click();", chk)
                    except Exception as e: logger.debug("MrFill: Checkbox click failed: %s", e)

            # Auto-fill Date (Optional fix for some forms)
            try:
                if not driver.find_element(By.ID, "txtWrkStartDate").get_attribute("value"):
                    val = driver.find_element(By.ID, "txtDatefrm").get_attribute("value")
                    if val: driver.execute_script(f"document.getElementById('txtWrkStartDate').value = '{val}';")
            except Exception as e: logger.debug("MrFill: Could not auto-fill date: %s", e)

            # --- 6. Submission ---
            if is_manual_mode:
                self.app.after(0, self.app.set_status, "Manual Mode: Paused")
                self.log_info(f"Manual Mode: Fill details for MR {current_mr_no} and click Save.")
                WebDriverWait(driver, 600).until(EC.alert_is_present()).accept()
            else:
                self.app.after(0, self.app.set_status, "Saving...")
                driver.execute_script("document.getElementById('btnsave').click();")
                WebDriverWait(driver, 10).until(EC.alert_is_present()).accept()

            # --- 7. Final Verification ---
            outcome_found = False
            for _ in range(3):
                try:
                    alert = driver.switch_to.alert; txt = alert.text; alert.accept()
                    if "Saved Successfully" in txt or "has been saved" in txt:
                        self._log_result(panchayat_name, work_key, current_mr_no, "Success", txt)
                    else:
                        self._log_result(panchayat_name, work_key, current_mr_no, "Failed", txt)
                    outcome_found = True; break
                except NoAlertPresentException: time.sleep(1)

            if not outcome_found: 
                self._log_result(panchayat_name, work_key, current_mr_no, "Failed", "Timeout: No confirmation alert.")

        except Exception as e:
            # --- ERROR CLEANING ---
            # Split the error message to remove the massive Stacktrace
            err_msg = str(e)
            if "Stacktrace:" in err_msg:
                err_msg = err_msg.split("Stacktrace:")[0].strip()
            if "Message:" in err_msg:
                 err_msg = err_msg.replace("Message:", "").strip()
            
            self._log_result(panchayat_name, work_key, current_mr_no, "Failed", err_msg)
    def retry_logic_handler(self) -> None:
        """
        Retry Logic: Reads 'Failed' items from Results and restarts automation.
        """
        failed_items = []
        all_items = self.results_tree.get_children()
        
        if not all_items:
            messagebox.showinfo("Retry", "No results found to retry.")
            return

        for item_id in all_items:
            values = self.results_tree.item(item_id)['values']
            # Column 1 is Workcode, Column 3 is Status (0 = Panchayat)
            work_code = str(values[1])
            status = str(values[3]).upper()
            
            if "SUCCESS" not in status:
                failed_items.append(work_code)
        
        if not failed_items:
            messagebox.showinfo("Great!", "No failed items found.")
            return

        if messagebox.askyesno("Retry Failed", f"Found {len(failed_items)} failed items.\nRetry now?"):
            # 1. Update Input Box
            self.work_key_text.configure(state="normal")
            self.work_key_text.delete("1.0", tkinter.END)
            self.work_key_text.insert("1.0", "\n".join(failed_items))
            self.work_key_text.configure(state="disabled")
            
            # 2. Clear Results
            for item in all_items: self.results_tree.delete(item)
            
            # 3. Auto Start
            self.start_automation()

    # 2. FIX: Update this method to apply the 'success' tag for green color
    def _log_result(self, panchayat, work_key, mr_no, status, msg):
        """Logs the result to the log display and the results tree."""
        # Clean up message for display
        details = msg.replace("\n", " ").replace("\r", " ").strip()
        work_key = truncate_workcode(work_key)
        
        # Determine Tag and Log Level
        level = "error"
        tag = "failed"
        
        if "success" in status.lower():
            level = "success"
            tag = "success"
        elif "mr already filled" in details.lower() or "mr already filled" in status.lower():
            # Treat "Already Filled" as a warning/info rather than a hard crash
            level = "warning"
            tag = "failed" # Keep red in treeview, or use a new tag if you want yellow
            details = "MR Already Filled" # Shorten details for the table

        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if level == "success":
            self.log_success(f"'{work_key}' (MR: {mr_no}) - {status.upper()}: {details}")
        elif level == "warning":
            self.log_warning(f"'{work_key}' (MR: {mr_no}) - {status.upper()}: {details}")
        elif level == "error":
            self.log_error(f"'{work_key}' (MR: {mr_no}) - {status.upper()}: {details}")
        else:
            self.log_info(f"'{work_key}' (MR: {mr_no}) - {status.upper()}: {details}")        
        self.safe_tree_insert((panchayat, work_key, mr_no, status.upper(), details, timestamp), (tag,))

    def export_report(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="mr_fill_results.xlsx",
            filter_mode="Export All",
            title_prefix="MR Fill Report"
        )

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
            status = row_values[3].upper() # Status column
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

        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_report_path("MR Fill"), initialfile=filename, title=details['title'])
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

