# tabs/msr_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, random, time, sys, subprocess
from datetime import datetime
from fpdf import FPDF
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException, NoAlertPresentException
import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class MsrTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="msr")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        self._create_widgets()

    def _create_widgets(self):
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls_frame.grid_columnconfigure((0, 1), weight=1)
        
        panchayat_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        panchayat_frame.grid(row=0, column=0, sticky='ew', padx=15, pady=(10,0))
        ctk.CTkLabel(panchayat_frame, text="Panchayat Name", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        self.panchayat_entry = AutocompleteEntry(
            panchayat_frame, 
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app, # <-- ADD THIS LINE
            history_key="panchayat_name" # <-- ADD THIS LINE
        )
        self.panchayat_entry.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(panchayat_frame, text="e.g., Palojori (must exactly match the name on the website)", text_color="gray50").pack(anchor='w')
        
        amount_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        amount_frame.grid(row=0, column=1, sticky='ew', padx=15, pady=(10,0))
        ctk.CTkLabel(amount_frame, text="Verify Amount (₹)", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        self.verify_amount_entry = ctk.CTkEntry(amount_frame)
        self.verify_amount_entry.insert(0, "282")
        self.verify_amount_entry.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(amount_frame, text="Reject if amount does not match this value.", text_color="gray50").pack(anchor='w')

        ctk.CTkLabel(controls_frame, text="ℹ️ Note: If using GP Login, Panchayat selection is not required and will be skipped.", text_color="gray50").grid(row=1, column=0, columnspan=2, sticky='w', padx=15, pady=(10,0))

        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(15, 15))

        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=1, column=0, sticky="nsew")
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

        self.export_button = ctk.CTkButton(export_controls_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side='left')
        
        self.export_format_menu = ctk.CTkOptionMenu(export_controls_frame, width=130, values=["PDF (.pdf)", "CSV (.csv)"], command=self._on_format_change)
        self.export_format_menu.pack(side='left', padx=5)

        self.export_filter_menu = ctk.CTkOptionMenu(export_controls_frame, width=150, values=["Export All", "Success Only", "Failed Only"])
        self.export_filter_menu.pack(side='left', padx=(0, 5))
        # --- End of Unified Export Controls ---

        cols = ("Workcode", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Status", anchor='center', width=150); self.results_tree.column("Details", width=350)
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree); self._setup_treeview_sorting(self.results_tree)
    
    def load_data_from_mr_tracking(self, workcodes: str, panchayat_name: str):
        """Public method to receive data from other tabs."""
        # Set Panchayat Name
        self.panchayat_entry.delete(0, tkinter.END)
        self.panchayat_entry.insert(0, panchayat_name)
        
        # Set Work Codes
        self.work_key_text.configure(state="normal")
        self.work_key_text.delete("1.0", tkinter.END)
        self.work_key_text.insert("1.0", workcodes)
        self.work_key_text.configure(state="disabled")
        
        self.app.log_message(self.log_display, f"Loaded {len(workcodes.splitlines())} workcodes and panchayat '{panchayat_name}' from MR Tracking.", "info")

    def _on_format_change(self, selected_format):
        """Disables the filter menu for CSV format as it exports all data."""
        if "CSV" in selected_format:
            self.export_filter_menu.configure(state="disabled")
        else:
            self.export_filter_menu.configure(state="normal")

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.verify_amount_entry.configure(state=state)
        self.work_key_text.configure(state=state)
        # --- Update State Management for New Controls ---
        self.export_button.configure(state=state)
        self.export_format_menu.configure(state=state)
        self.export_filter_menu.configure(state=state)
        if state == "normal": self._on_format_change(self.export_format_menu.get())

    # ... (start_automation, reset_ui, run_automation_logic, etc., are unchanged)
    def start_automation(self):
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic)
        
    def reset_ui(self):
        if messagebox.askokcancel("Reset Form?", "Clear all inputs, results, and logs?"):
            self.panchayat_entry.delete(0, tkinter.END)
            self.verify_amount_entry.delete(0, tkinter.END); self.verify_amount_entry.insert(0, "282")
            self.work_key_text.configure(state="normal"); self.work_key_text.delete("1.0", tkinter.END); self.work_key_text.configure(state="disabled")
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.app.log_message(self.log_display, "Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
            
    def run_automation_logic(self):
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, lambda: [self.results_tree.delete(item) for item in self.results_tree.get_children()])
        self.app.clear_log(self.log_display)
        self.app.log_message(self.log_display, "Starting MSR processing...")
        self.app.after(0, self.app.set_status, "Running MSR Payment...")
        
        panchayat_name = self.panchayat_entry.get().strip()
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
                if not panchayat_name: messagebox.showerror("Input Error", "Panchayat name is required for Block Login."); self.app.after(0, self.set_ui_state, False); return
                panchayat_select = Select(panchayat_select_element)
                match = next((opt.text for opt in panchayat_select.options if panchayat_name.strip().lower() in opt.text.lower()), None)
                if not match: raise ValueError(f"Panchayat '{panchayat_name}' not found.")
                panchayat_select.select_by_visible_text(match)
                self.app.update_history("panchayat_name", panchayat_name)
                self.app.log_message(self.log_display, f"Successfully selected Panchayat: {match}", "success"); time.sleep(2)
            except TimeoutException: self.app.log_message(self.log_display, "Panchayat selection not found/required (GP Login). Proceeding...", "info")

            total = len(work_keys)
            for i, work_key in enumerate(work_keys, 1):
                if self.app.stop_events[self.automation_key].is_set(): self.app.log_message(self.log_display, "Automation stopped by user.", "warning"); break
                # --- MODIFICATION ---
                status_msg = f"Processing {i}/{total}: {work_key}"
                progress = (i / total)
                self.app.after(0, self.app.set_status, status_msg) # मुख्य (main) स्टेटस बार को अपडेट करें
                self.app.after(0, self.update_status, status_msg, progress) # टैब के स्टेटस बार को अपडेट करें
                # --- END MODIFICATION ---
                self._process_single_work_code(driver, wait, work_key, verify_amount)
                
            if not self.app.stop_events[self.automation_key].is_set(): messagebox.showinfo("Completed", "Automation finished! Check the 'Results' tab for details.")
        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
            messagebox.showerror("MSR Error", f"An error occurred: {e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished.", 1.0)
            self.app.after(0, self.app.set_status, "Automation Finished")
            
    def _process_single_work_code(self, driver, wait, work_key, verify_amount):
        """
        Processes a single work code for MSR payment.
        BACKGROUND-SAFE UPDATE: Uses JS for inputs/clicks and Presence checks.
        """
        try:
            # Dismiss alert if present
            try: driver.switch_to.alert.accept()
            except NoAlertPresentException: pass
            
            # --- 1. Search Work Code (Background Safe) ---
            # Use Presence
            search_box = wait.until(EC.presence_of_element_located((By.ID, "txtSearch")))
            # JS Set Value
            driver.execute_script("arguments[0].value = arguments[1];", search_box, work_key)
            
            # JS Click Search Button
            search_btn = wait.until(EC.presence_of_element_located((By.ID, "ImgbtnSearch")))
            driver.execute_script("arguments[0].click();", search_btn)
            
            time.sleep(1)

            # --- 2. Check Errors ---
            # Check for error label (Use innerText for background safety)
            try:
                error_span = driver.find_element(By.ID, "lblError")
                err_text = error_span.get_attribute("innerText").strip()
                if err_text: raise ValueError(f"Site error: '{err_text}'")
            except NoSuchElementException: pass

            # --- 3. Select Lists (Safe) ---
            work_code_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlWorkCode"))))
            if len(work_code_select.options) <= config.MSR_CONFIG["work_code_index"]: raise IndexError("Work code not found.")
            work_code_select.select_by_index(config.MSR_CONFIG["work_code_index"]); time.sleep(1.5)
            
            msr_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlMsrNo"))))
            if len(msr_select.options) <= config.MSR_CONFIG["muster_roll_index"]: raise IndexError("Muster Roll (MSR) not found.")
            msr_select.select_by_index(config.MSR_CONFIG["muster_roll_index"]); time.sleep(1.5)

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
        level = "success" if status.lower() == "success" else "error"
        timestamp = datetime.now().strftime("%H:%M:%S")
        details = msg.replace("\n", " ").replace("\r", " ")
        if "No final confirmation found" in msg: details = "Pending for JE & AE Approval"
        elif "Muster Roll (MSR) not found" in msg: details = "MR not Filled yet."
        elif "Work code not found" in msg: details = "Work Code not found."
        self.app.log_message(self.log_display, f"'{work_key}' - {status.upper()}: {details}", level=level)
        tags = ('failed',) if 'success' not in status.lower() else ()
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(work_key, status.upper(), details, timestamp), tags=tags))

    # --- NEW: Central Export Function ---
    def export_report(self):
        export_format = self.export_format_menu.get()
        panchayat_name = self.panchayat_entry.get().strip()

        # Ensure Panchayat name is provided for the filename
        if not panchayat_name:
            messagebox.showwarning("Input Needed", "Please enter a Panchayat Name to include in the report filename.", parent=self)
            return

        if "CSV" in export_format:
            safe_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"MSR_Report_{safe_name}_{timestamp}.csv"
            self.export_treeview_to_csv(self.results_tree, default_filename)
            return
            
        data, file_path = self._get_filtered_data_and_filepath(export_format)
        if not data: return

        if "PDF" in export_format:
            self._handle_pdf_export(data, file_path)

    def _get_filtered_data_and_filepath(self, export_format):
        all_items = self.results_tree.get_children()
        if not all_items: messagebox.showinfo("No Data", "There are no results to export."); return None, None
        panchayat_name = self.panchayat_entry.get().strip()
        if not panchayat_name: messagebox.showwarning("Input Needed", "Please enter a Panchayat Name for the report title."); return None, None

        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in all_items:
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[1].upper()
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status: data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status: data_to_export.append(row_values)
        if not data_to_export: messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'."); return None, None

        safe_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        file_details = {
            "Image (.jpg)": { "ext": ".jpg", "types": [("JPEG Image", "*.jpg")], "title": "Save Report as Image"},
            "PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")], "title": "Save Report as PDF"},
        }
        details = file_details[export_format]
        filename = f"MSR_Report_{safe_name}_{timestamp}{details['ext']}"

        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_user_downloads_path(), initialfile=filename, title=details['title'])
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, file_path):
        """Handles the generation of the improved PDF report for MSR."""
        try:
            headers = self.results_tree['columns']
            # Adjusted column widths for A4 Landscape (Approx total 280mm)
            # Workcode (50), Status (30), Details (160), Timestamp (40)
            col_widths = [50, 30, 160, 40] 
            
            title = f"MSR Payment Status Report: {self.panchayat_entry.get().strip()}"
            report_date = datetime.now().strftime('%d %b %Y')
            
            # This new method is in base_tab.py and handles all the styling
            success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
            
            if success:
                if messagebox.askyesno("Success", f"PDF Report exported to:\n{file_path}\n\nDo you want to open the file?"):
                    if sys.platform == "win32":
                        os.startfile(file_path)
                    else:
                        subprocess.call(['open', file_path])
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to create PDF file.\n\nError: {e}")