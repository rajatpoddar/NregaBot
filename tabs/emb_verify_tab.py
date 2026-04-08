# tabs/emb_verify_tab.py
import subprocess
import sys
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, UnexpectedAlertPresentException
import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class EmbVerifyTab(BaseAutomationTab):
    """
    A tab for automating the e-Measurement Book (eMB) verification process.
    """
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="emb_verify")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) 
        self._create_widgets()

    def _create_widgets(self):
        """Creates the user interface elements for the tab."""
        # --- Top Frame for Configuration ---
        config_frame = ctk.CTkFrame(self)
        config_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        config_frame.grid_columnconfigure(1, weight=1)

        # Panchayat input field
        ctk.CTkLabel(config_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=15, pady=15)
        self.panchayat_entry = AutocompleteEntry(config_frame, suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"))
        self.panchayat_entry.grid(row=0, column=1, sticky='ew', padx=15, pady=15)
        
        # Verify Amount input field
        ctk.CTkLabel(config_frame, text="Verify Amount (₹):").grid(row=1, column=0, sticky='w', padx=15, pady=(0, 15))
        self.verify_amount_entry = ctk.CTkEntry(config_frame)
        self.verify_amount_entry.insert(0, "282")
        self.verify_amount_entry.grid(row=1, column=1, sticky='ew', padx=15, pady=(0, 15))

        # Action buttons
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        # --- Bottom Frame for Data Tabs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        work_codes_tab = notebook.add("Work Codes")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)
        
        # --- Work Codes Tab Content ---
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1)
        
        wc_header_frame = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        ctk.CTkLabel(wc_header_frame, text="Enter Work Codes (one per line). Leave blank to process all.").pack(side="left", padx=5)
        
        clear_wc_button = ctk.CTkButton(wc_header_frame, text="Clear", width=80, command=lambda: self.work_codes_text.delete("1.0", "end"))
        clear_wc_button.pack(side="right", padx=(0, 5))
        
        # --- NEW: Added the Extract from Text button (using correct frame name) ---
        extract_button = ctk.CTkButton(wc_header_frame, text="Extract from Text", width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_codes_text))
        extract_button.pack(side='right', padx=(0, 5))
        # ---
        
        self.work_codes_text = ctk.CTkTextbox(work_codes_tab, height=150)
        self.work_codes_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)


        # --- Results Tab UI ---
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side='left')
        self.export_format_menu = ctk.CTkOptionMenu(export_controls_frame, width=130, values=["PDF (.pdf)", "CSV (.csv)"], command=self._on_format_change)
        self.export_format_menu.pack(side='left', padx=5)
        self.export_filter_menu = ctk.CTkOptionMenu(export_controls_frame, width=150, values=["Export All", "Success Only", "Failed Only"])
        self.export_filter_menu.pack(side='left', padx=(0, 5))

        cols = ("Work Code", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Work Code", width=250); self.results_tree.column("Status", width=100, anchor='center'); self.results_tree.column("Details", width=350); self.results_tree.column("Timestamp", width=120, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)

    def _on_format_change(self, selected_format):
        if "CSV" in selected_format: self.export_filter_menu.configure(state="disabled")
        else: self.export_filter_menu.configure(state="normal")

    def set_ui_state(self, running: bool):
        """Enable or disable UI elements based on automation state."""
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.verify_amount_entry.configure(state=state)
        self.work_codes_text.configure(state=state)
        self.export_button.configure(state=state)
        self.export_format_menu.configure(state=state)
        self.export_filter_menu.configure(state=state)
        if state == "normal": self._on_format_change(self.export_format_menu.get())

    def reset_ui(self):
        """Resets the UI to its initial state."""
        if messagebox.askokcancel("Reset Form?", "This will clear all inputs and results. Continue?"):
            self.panchayat_entry.delete(0, tkinter.END)
            self.verify_amount_entry.delete(0, tkinter.END)
            self.verify_amount_entry.insert(0, "282")
            self.work_codes_text.delete("1.0", tkinter.END)
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.app.log_message(self.log_display, "Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    def start_automation(self):
        """Validates inputs and starts the automation thread."""
        panchayat = self.panchayat_entry.get().strip()
        verify_amount = self.verify_amount_entry.get().strip()
        
        if not panchayat or not verify_amount:
            messagebox.showwarning("Input Error", "Panchayat Name and Verify Amount are required.")
            return

        work_codes = [line.strip() for line in self.work_codes_text.get("1.0", "end-1c").splitlines() if line.strip()]
        
        self.app.update_history("panchayat_name", panchayat)
        for wc in work_codes:
            self.app.update_history("work_code", wc)

        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(panchayat, verify_amount, work_codes))

    def _log_result(self, work_code, status, details):
        """Logs a result to the treeview."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        tags = ('failed',) if 'success' not in status.lower() and 'verified' not in status.lower() else ()
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(work_code, status, details, timestamp), tags=tags))

    def run_automation_logic(self, panchayat, verify_amount, work_codes_from_ui):
        """The main logic for the eMB verification automation."""
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.app.after(0, lambda: [self.results_tree.delete(item) for item in self.results_tree.get_children()])
        self.app.log_message(self.log_display, f"Starting eMB Verification for Panchayat: {panchayat}")
        self.app.after(0, self.app.set_status, "Running eMB Verification...")

        try:
            driver = self.app.get_driver()
            if not driver: return

            driver.get(config.EMB_VERIFY_CONFIG["url"])
            wait = WebDriverWait(driver, 20) 

            self.app.log_message(self.log_display, f"Selecting Panchayat: {panchayat}")
            panchayat_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_panch"))))
            panchayat_select.select_by_visible_text(panchayat)
            
            self.app.log_message(self.log_display, "Waiting for page to reload...")
            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work")))
            time.sleep(1) 
            self.app.log_message(self.log_display, "Page reloaded successfully.")
            
            work_codes_to_process = []
            use_search = bool(work_codes_from_ui)

            if use_search:
                work_codes_to_process = work_codes_from_ui
                self.app.log_message(self.log_display, f"Processing {len(work_codes_to_process)} work codes from input.")
            else:
                self.app.log_message(self.log_display, "No work codes provided. Fetching all from dropdown...")
                work_code_select_element = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work"))))
                work_codes_to_process = [opt.text for opt in work_code_select_element.options if opt.get_attribute('value')]
                if not work_codes_to_process:
                    self.app.log_message(self.log_display, "No work codes found for this Panchayat.", "warning")
                    self._log_result("N/A", "Skipped", "No work codes found.")
            
            total = len(work_codes_to_process)
            for i, current_wc in enumerate(work_codes_to_process):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Automation stopped by user.", "warning")
                    break
                
                self.app.after(0, self.update_status, f"Processing {i+1}/{total}: {current_wc}", (i+1)/total)
                self._process_single_work_code(driver, wait, current_wc, use_search, verify_amount)

                if use_search and i < total - 1:
                    self.app.log_message(self.log_display, "Navigating back for next work code...")
                    driver.get(config.EMB_VERIFY_CONFIG["url"])
                    panchayat_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_panch"))))
                    panchayat_select.select_by_visible_text(panchayat)
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work")))
                    time.sleep(1)

            final_msg = "Automation finished." if not self.app.stop_events[self.automation_key].is_set() else "Stopped."
            self.app.after(0, self.update_status, final_msg, 1.0)
            if not self.app.stop_events[self.automation_key].is_set():
                messagebox.showinfo("Complete", "e-MB Verification process has finished.")

        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
            messagebox.showerror("Automation Error", f"An unexpected error occurred:\n\n{e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _process_single_work_code(self, driver, wait, work_code, use_search, verify_amount):
        """Handles the logic for a single work code verification."""
        try:
            self.app.log_message(self.log_display, f"Selecting work code: {work_code}")
            work_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work"))))
            
            found = False
            for option in work_select.options:
                if work_code in option.text:
                    work_select.select_by_visible_text(option.text)
                    found = True
                    break
            
            if not found:
                raise NoSuchElementException(f"Work code containing '{work_code}' not found in dropdown.")
            
            self.app.log_message(self.log_display, "Work selected. Pausing for page to update...")
            time.sleep(2) 

            self.app.log_message(self.log_display, "Selecting 'Musterroll Period Wise'.")
            period_radio_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_rbl_mustrolltype_0")))
            driver.execute_script("arguments[0].click();", period_radio_btn)
            
            self.app.log_message(self.log_display, "Waiting for measurement periods to load...")
            period_dropdown_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddl_mperiod")))
            time.sleep(2) 

            period_select = Select(period_dropdown_element)
            if len(period_select.options) <= 1:
                self._log_result(work_code, "Skipped", "No measurement period available.")
                return
            period_select.select_by_index(1)
            
            self.app.log_message(self.log_display, "Waiting for activity table to load...")
            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_grd_activitycomponent_ctl02_lbl_act_unitcost")))
            
            unit_cost = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_grd_activitycomponent_ctl02_lbl_act_unitcost").text.strip()
            wage_per_day = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_grd_activitycomponent_ctl02_lbl_wageperday").text.strip()

            self.app.log_message(self.log_display, f"Found Unit Cost: {unit_cost}, Wage Per Day: {wage_per_day} for {work_code}")

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)

            if unit_cost == verify_amount and wage_per_day == verify_amount:
                driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btn_verify").click()
                self._log_result(work_code, "Verified", f"Unit Cost & Wage were correct ({verify_amount}).")
            else:
                rejection_reason = "unit cost is not correct"
                self.app.log_message(self.log_display, f"Rejecting. Unit Cost: {unit_cost}, Wage: {wage_per_day}", "warning")
                driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txt_rejection_reason").send_keys(rejection_reason)
                driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btn_reject").click()
                self._log_result(work_code, "Rejected", f"Unit Cost: {unit_cost}, Wage: {wage_per_day}. Reason sent.")

            try:
                final_alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                self.app.log_message(self.log_display, f"Confirmation: {final_alert.text}")
                final_alert.accept()
            except TimeoutException:
                self.app.log_message(self.log_display, "No final confirmation alert appeared.", "info")

        except UnexpectedAlertPresentException as e:
            try:
                alert = driver.switch_to.alert
                self._log_result(work_code, "Failed", f"Unexpected Alert: {alert.text}")
                alert.accept()
            except: pass
        except (TimeoutException, NoSuchElementException) as e:
            self._log_result(work_code, "Failed", f"Could not find a required element or work code not found.")
            self.app.log_message(self.log_display, f"Error details: {e}", "error")
        except Exception as e:
            self._log_result(work_code, "Error", f"An unexpected error occurred: {e}")

    def export_report(self):
        export_format = self.export_format_menu.get()
        if "CSV" in export_format:
            self.export_treeview_to_csv(self.results_tree, "emb_verify_results.csv")
            return
            
        data, file_path = self._get_filtered_data_and_filepath(export_format)
        if not data: return
        
        headers = self.results_tree['columns']
        col_widths = [70, 35, 140, 25]

        if "PDF" in export_format:
            self._handle_pdf_export(data, headers, col_widths, file_path)

    def _get_filtered_data_and_filepath(self, export_format):
        if not self.results_tree.get_children(): messagebox.showinfo("No Data", "No results to export."); return None, None
        panchayat_name = self.panchayat_entry.get().strip()
        if not panchayat_name: messagebox.showwarning("Input Needed", "Panchayat Name is required for report title."); return None, None
        
        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in self.results_tree.get_children():
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[1].upper() # Status is at index 1
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and ("SUCCESS" in status or "VERIFIED" in status): data_to_export.append(row_values)
            elif filter_option == "Failed Only" and not ("SUCCESS" in status or "VERIFIED" in status): data_to_export.append(row_values)
        if not data_to_export: messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'."); return None, None

        safe_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        details = {"PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")]}}[export_format]
        filename = f"eMB_Verify_Report_{safe_name}_{timestamp}{details['ext']}"
        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_user_downloads_path(), initialfile=filename, title="Save Report")
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, headers, col_widths, file_path):
        title = f"eMB Verification Report: {self.panchayat_entry.get().strip()}"
        report_date = datetime.now().strftime('%d %b %Y')
        success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
        if success and messagebox.askyesno("Success", f"PDF Report saved to:\n{file_path}\n\nDo you want to open it?"):
            if sys.platform == "win32": os.startfile(file_path)
            else: subprocess.call(['open', file_path])
