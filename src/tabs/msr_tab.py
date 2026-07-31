# tabs/msr_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import os, random, time
from datetime import datetime
from src import config
from src.utils import truncate_workcode
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoAlertPresentException, NoSuchElementException, TimeoutException  # noqa: F401


class MsrTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="msr")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(3, weight=1)
        self._create_widgets()
    def _create_widgets(self) -> None:

        # --- Header / intro card (P7.2: pending-bills style) ---
        self._create_header_card(self, "💵", "MR Payment (MSR)",
                                 "Process & verify Muster Roll payments against the sanctioned wage amount.",
                                 icon_key="emoji_mr_payment")

        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        controls_frame.grid_columnconfigure((0, 1), weight=1)
        
        panchayat_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        panchayat_frame.grid(row=0, column=0, sticky='new', padx=15, pady=(10,0))
        ctk.CTkLabel(panchayat_frame, text="Panchayat Name", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(panchayat_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.pack(fill='x', pady=(5,0))

        
        amount_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        amount_frame.grid(row=0, column=1, sticky='new', padx=15, pady=(10,0))
        ctk.CTkLabel(amount_frame, text="Verify Amount (₹)", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        self.verify_amount_entry = ctk.CTkEntry(amount_frame)
        self.verify_amount_entry.insert(0, "300")
        self.verify_amount_entry.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(amount_frame, text="Reject if amount does not match this value.", text_color="gray50").pack(anchor='w')

        ctk.CTkLabel(controls_frame, text="💡 Note: If using GP Login, Panchayat selection is not required and will be skipped.", text_color="gray50").grid(row=1, column=0, columnspan=2, sticky='w', padx=15, pady=(10,15))

        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky='ew', padx=10, pady=(0, 10))

        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew")
        work_codes_frame = data_notebook.add("Work Codes"); results_frame = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        work_codes_frame.grid_columnconfigure(0, weight=1); work_codes_frame.grid_rowconfigure(1, weight=1)
        wc_controls_frame = ctk.CTkFrame(work_codes_frame, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew')
        clear_button = ctk.CTkButton(wc_controls_frame, text="Clear", width=80, command=lambda: self.work_key_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', pady=(5,0), padx=(0,5))
        # --- MODIFIED: Update the command to use the base method ---
        extract_button = ctk.CTkButton(wc_controls_frame, text="Extract from Text", width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_key_text))
        extract_button.pack(side='right', pady=(5,0), padx=(0, 5))
        # ---
        self.work_key_text = ctk.CTkTextbox(work_codes_frame, wrap=tkinter.WORD)
        self.work_key_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        results_frame.grid_columnconfigure(0, weight=1); results_frame.grid_rowconfigure(1, weight=1)
        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10))
        
        # --- NEW: Unified Export Controls ---
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side='left')
        # --- End of Unified Export Controls ---

        cols = ("Workcode", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Status", anchor='center', width=150); self.results_tree.column("Details", width=350)
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree); self._setup_treeview_sorting(self.results_tree)
    
    def load_data_from_mr_tracking(self, workcodes, location_panchayat: str):
        """Public method to receive data from other tabs."""
        # Set Panchayat Name
        self.panchayat_var.set(location_panchayat)
        
        # Determine how to display workcodes (Handle List or String)
        display_text = ""
        if isinstance(workcodes, list):
            display_text = "\n".join(workcodes)
        else:
            display_text = str(workcodes)

        # Set Work Codes in Textbox
        self.work_key_text.configure(state="normal")
        self.work_key_text.delete("1.0", tkinter.END)
        self.work_key_text.insert("1.0", display_text)
        self.work_key_text.configure(state="disabled")
        
        # Log info
        count = len(display_text.splitlines()) if display_text else 0
        self.log_info(f"Loaded {count} workcodes and panchayat '{location_panchayat}' from MR Tracking.")


    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.verify_amount_entry.configure(state=state)
        self.work_key_text.configure(state=state)
        # --- Update State Management for New Controls ---
        self.export_button.configure(state=state)

    # ... (start_automation, reset_ui, run_automation_logic, etc., are unchanged)
    def start_automation(self) -> None:
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic)
    def reset_ui(self) -> None:
        if messagebox.askokcancel("Reset Form?", "Clear all inputs, results, and logs?"):
            self.panchayat_var.set("")
            self.verify_amount_entry.delete(0, tkinter.END); self.verify_amount_entry.insert(0, "300")
            self.work_key_text.configure(state="normal"); self.work_key_text.delete("1.0", tkinter.END); self.work_key_text.configure(state="disabled")
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
            
    def run_automation_logic(self):
        self.app.after(0, self.set_ui_state, True)
        self.safe_tree_clear()
        self.app.clear_log(self.log_display)
        self.log_info("Starting MSR processing...")
        self.app.after(0, self.app.set_status, "Running MSR Payment...")
        
        location_panchayat = self.panchayat_var.get().strip()
        verify_amount_str = self.verify_amount_entry.get().strip()
        
        self.work_key_text.configure(state="normal") # Enable to read
        work_keys = [line.strip() for line in self.work_key_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]
        self.work_key_text.configure(state="disabled") # Disable again

        if not work_keys: messagebox.showerror("Input Error", "No work keys provided."); self.app.after(0, self.set_ui_state, False); return
        try: verify_amount = float(verify_amount_str)
        except ValueError: messagebox.showerror("Input Error", "Verify Amount must be a valid number."); self.app.after(0, self.set_ui_state, False); return

        try:
            driver = self.app.get_driver()
            if not driver: return
            
            wait = WebDriverWait(driver, 15)
            if driver.current_url != config.MSR_CONFIG["url"]: driver.get(config.MSR_CONFIG["url"])
            
            try:
                panchayat_select_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, "ddlPanchayat")))
                if not location_panchayat: messagebox.showerror("Input Error", "Panchayat name is required for Block Login."); self.app.after(0, self.set_ui_state, False); return
                panchayat_select = Select(panchayat_select_element)
                match = next((opt.text for opt in panchayat_select.options if location_panchayat.strip().lower() in opt.text.lower()), None)
                if not match: raise ValueError(f"Panchayat '{location_panchayat}' not found.")
                panchayat_select.select_by_visible_text(match)
                self.app.update_history("location_panchayat", location_panchayat)
                self.log_success(f"Successfully selected Panchayat: {match}"); time.sleep(2)
            except TimeoutException: self.log_info("Panchayat selection not found/required (GP Login). Proceeding...")
            total = len(work_keys)
            for i, work_key in enumerate(work_keys, 1):
                if self.is_stopped(): self.log_warning("Automation stopped by user."); break
                # --- MODIFICATION ---
                status_msg = f"Processing {i}/{total}: {work_key}"
                progress = (i / total)
                self.app.after(0, self.app.set_status, status_msg) # मुख्य (main) स्टेटस बार को अपडेट करें
                self.app.after(0, self.update_status, status_msg, progress) # टैब के स्टेटस बार को अपडेट करें
                # --- END MODIFICATION ---
                self._process_single_work_code(driver, wait, work_key, verify_amount)
                
            if not self.is_stopped(): self.log_info("📊 Automation finished. Check the 'Results' tab for details.")
        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror("MSR Error", f"An error occurred: {e}")
        finally:
            # Count success/fail from results_tree
            success_count = sum(1 for item in self.results_tree.get_children() if 'success' in str(self.results_tree.item(item)['values'][1]).lower())
            fail_count = sum(1 for item in self.results_tree.get_children() if 'success' not in str(self.results_tree.item(item)['values'][1]).lower())
            total_count = success_count + fail_count
            self.log_info(f"📊 MSR Processing Complete: ✅ {success_count} Success, ❌ {fail_count} Failed (of {total_count} total)")
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished.", 1.0)
            self.app.after(0, self.app.set_status, "Automation Finished")
            
    # Inside tabs/msr_tab.py
    def retry_logic_handler(self) -> None:
        """
        Overriding base method to connect the Retry button to 
        the specific text box used in this tab (work_key_text).
        """
        self.retry_failed_automation(self.work_key_text)

    def _process_single_work_code(self, driver, wait, work_key, verify_amount):
        """
        Processes a single work code for MSR payment.
        Includes robust waiting for Slow Internet (Wait for Postback).
        """
        try:
            # Dismiss alert if present
            try: driver.switch_to.alert.accept()
            except NoAlertPresentException: pass
            
            # --- 1. Search Work Code (Background Safe) ---
            # Capture the old dropdown element to check for page refresh (staleness) later
            try:
                old_work_code_ddl = driver.find_element(By.ID, "ddlWorkCode")
            except NoSuchElementException:
                old_work_code_ddl = None

            # Use Presence
            search_box = wait.until(EC.presence_of_element_located((By.ID, "txtSearch")))
            # JS Set Value
            driver.execute_script("arguments[0].value = arguments[1];", search_box, work_key)
            
            # JS Click Search Button
            search_btn = wait.until(EC.presence_of_element_located((By.ID, "ImgbtnSearch")))
            driver.execute_script("arguments[0].click();", search_btn)
            
            # --- CRITICAL FIX FOR SLOW INTERNET ---
            # Wait for the old dropdown to become 'stale' (meaning page has refreshed/reloaded)
            if old_work_code_ddl:
                try:
                    wait.until(EC.staleness_of(old_work_code_ddl))
                except TimeoutException:
                    self.log_warning("Page did not refresh quickly, forcing wait...")            
            # Wait a tiny bit extra for the new DOM to settle
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                pass

            # --- 2. Check Errors ---
            # Check for error label (Use innerText for background safety)
            try:
                error_span = driver.find_element(By.ID, "lblError")
                err_text = error_span.get_attribute("innerText").strip()
                if err_text: raise ValueError(f"Site error: '{err_text}'")
            except NoSuchElementException: pass

            # --- 3. Select Lists (Safe) ---
            # Re-find the element after the refresh
            work_code_select_elem = wait.until(EC.presence_of_element_located((By.ID, "ddlWorkCode")))
            work_code_select = Select(work_code_select_elem)
            
            # Check if options are loaded (more than just "Select")
            if len(work_code_select.options) <= 1:
                # Retry once if options haven't populated yet
                # Element wait handled by WebDriverWait below
                work_code_select = Select(driver.find_element(By.ID, "ddlWorkCode"))

            if len(work_code_select.options) <= config.MSR_CONFIG["work_code_index"]: 
                raise IndexError("Work code not found (Dropdown empty or index out of bounds).")
            
            work_code_select.select_by_index(config.MSR_CONFIG["work_code_index"])
            
            # Wait for the next dropdown (MSR No) to load after selecting Work Code
            # (Selecting work code triggers another mini-update)
            # Element wait handled by WebDriverWait below
            
            msr_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlMsrNo"))))
            if len(msr_select.options) <= config.MSR_CONFIG["muster_roll_index"]: 
                raise IndexError("Muster Roll (MSR) not found.")
            
            msr_select.select_by_index(config.MSR_CONFIG["muster_roll_index"])
            time.sleep(1.5)

            # --- 4. Verify Amount ---
            wage_inputs = driver.find_elements(By.XPATH, "//input[starts-with(@name, 'wage_per_day')]")
            filled_wages = [float(inp.get_attribute('value')) for inp in wage_inputs if inp.get_attribute('value') and float(inp.get_attribute('value')) > 0]
            
            if not filled_wages:
                self._log_result("Skipped", work_key, "Pending for JE or AE Approval")
                return
            
            for wage in filled_wages:
                if wage != verify_amount:
                    self._log_result("Rejected", work_key, f"Verify amount not matched ({wage} != {verify_amount})")
                    return

            # --- 5. Save/Submit (Background Safe) ---
            # JS Click for Save
            save_btn = wait.until(EC.presence_of_element_located((By.ID, "btnSave")))
            driver.execute_script("arguments[0].click();", save_btn)
            
            # Handle Alert
            WebDriverWait(driver, 10).until(EC.alert_is_present()).accept()
            
            outcome_found = False
            for _ in range(3):
                try:
                    final_alert = driver.switch_to.alert; final_alert_text = final_alert.text.strip(); final_alert.accept()
                    if "Muster Roll Payment has been saved" in final_alert_text: self._log_result("Success", work_key, final_alert_text)
                    elif "and hence it is not saved" in final_alert_text: self._log_result("Success", work_key, "Saved (ignorable attendance error)")
                    else: self._log_result("Failed", work_key, f"Unknown Alert: {final_alert_text}")
                    outcome_found = True; break
                except NoAlertPresentException:
                    if "Expenditure on unskilled labours exceeds sanction amount" in driver.page_source: 
                        self._log_result("Failed", work_key, "Exceeds Labour Payment"); outcome_found = True; break
                    time.sleep(1)
            
            if not outcome_found: self._log_result("Failed", work_key, "No final confirmation found (Timeout).")
            
            delay = random.uniform(config.MSR_CONFIG["min_delay"], config.MSR_CONFIG["max_delay"])
            self.app.after(0, self.update_status, f"Waiting {delay:.1f}s...")
            time.sleep(delay)

        except (ValueError, IndexError, NoSuchElementException, TimeoutException) as e:
            display_msg = "MR not Filled yet." if isinstance(e, IndexError) else "Page timed out or element not found." if isinstance(e, TimeoutException) else str(e)
            self._log_result("Failed", work_key, display_msg)
        except Exception as e: self._log_result("Failed", work_key, f"CRITICAL ERROR: {type(e).__name__}")
        
    def _log_result(self, status, work_key, msg):
        # Determine level for log file
        level = "success" if status.lower() == "success" else "error"
        timestamp = datetime.now().strftime("%H:%M:%S")
        work_key = truncate_workcode(work_key)
        
        # Clean up details text
        details = msg.replace("\n", " ").replace("\r", " ")
        if "No final confirmation found" in msg: details = "Pending for JE & AE Approval"
        elif "Muster Roll (MSR) not found" in msg: details = "MR not Filled yet."
        elif "Work code not found" in msg: details = "Work Code not found."
        
        # Log to the text box (use appropriate log level)
        if level == "success":
            self.log_success(f"'{work_key}' - {status.upper()}: {details}")
        elif level == "error":
            self.log_error(f"'{work_key}' - {status.upper()}: {details}")
        else:
            self.log_info(f"'{work_key}' - {status.upper()}: {details}")        
        # --- FIX: Set the tag to 'success' explicitly for Green color ---
        tags = ('success',) if 'success' in status.lower() else ('failed',)
        
        # Insert into table with the correct tag
        self.safe_tree_insert((work_key, status.upper(), details, timestamp), tags)

    # --- NEW: Central Export Function ---
    def export_report(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="msr_results.xlsx",
            filter_mode="Export All",
            title_prefix="MSR Report"
        )


    
