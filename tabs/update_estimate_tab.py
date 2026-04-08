# tabs/update_estimate_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, csv, sys, os, subprocess, re  # <-- ADD 're'
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoAlertPresentException
from datetime import datetime
import config
from .base_tab import BaseAutomationTab

class UpdateEstimateTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="update_estimate")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_widgets()

    def _create_widgets(self):
        """Creates the UI elements for the tab, inspired by the MSR Tab layout."""
        # --- Top Controls Frame ---
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,0))
        controls_frame.grid_columnconfigure(0, weight=1)

        # Estimated Outcome Input
        outcome_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        outcome_frame.grid(row=0, column=0, sticky='ew', padx=15, pady=(10,0))
        ctk.CTkLabel(outcome_frame, text="Estimated Outcome", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        self.estimated_outcome_entry = ctk.CTkEntry(outcome_frame)
        self.estimated_outcome_entry.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(outcome_frame, text="This value will be used for all work codes processed.", text_color="gray50").pack(anchor='w')

        # Action Buttons (Start, Stop, Reset)
        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=15)

        # --- Main Tab View for Inputs and Results ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        work_codes_frame = data_notebook.add("Work Codes")
        results_frame = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # --- Work Codes Tab ---
        work_codes_frame.grid_columnconfigure(0, weight=1)
        work_codes_frame.grid_rowconfigure(1, weight=1)
        wc_controls_frame = ctk.CTkFrame(work_codes_frame, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew')
        
        ctk.CTkLabel(wc_controls_frame, text="Enter one Work Code per line.", text_color="gray50").pack(side='left', padx=5)
        
        clear_button = ctk.CTkButton(wc_controls_frame, text="Clear", width=80, command=lambda: self.work_key_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', pady=(5,0), padx=(0,5))
        
        # --- NEW: Extract Button (points to a new local method) ---
        extract_button = ctk.CTkButton(wc_controls_frame, text="Extract from Text", width=120,
                                       command=self._extract_full_workcodes)
        extract_button.pack(side='right', pady=(5,0), padx=(0, 5))
        # ---
        
        self.work_key_text = ctk.CTkTextbox(work_codes_frame, wrap=tkinter.WORD)
        self.work_key_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # --- Results Tab ---
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1)
        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10))
        
        # Export Controls
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 5))
        self.export_button = ctk.CTkButton(export_controls_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side='left')
        self.export_format_menu = ctk.CTkOptionMenu(export_controls_frame, width=130, values=["PDF (.pdf)", "CSV (.csv)"])
        self.export_format_menu.pack(side='left', padx=5)

        # Results Treeview
        cols = ("Work Code", "Outcome Value", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Work Code", width=250)
        self.results_tree.column("Outcome Value", width=100, anchor='center')
        self.results_tree.column("Status", width=100, anchor='center')
        self.results_tree.column("Details", width=350)
        self.results_tree.column("Timestamp", width=100, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)

    def set_ui_state(self, running: bool):
        """Enables or disables UI elements based on automation status."""
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.estimated_outcome_entry.configure(state=state)
        self.work_key_text.configure(state=state)
        self.export_button.configure(state=state)
        self.export_format_menu.configure(state=state)

    def start_automation(self):
        """Starts the automation logic in a separate thread."""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.app.start_automation_thread(key=self.automation_key, target=self.run_automation_logic)

    def reset_ui(self):
        """Resets the UI to its initial state."""
        if messagebox.askokcancel("Reset Form?", "This will clear all inputs, results, and logs. Continue?"):
            self.estimated_outcome_entry.delete(0, tkinter.END)
            self.work_key_text.delete("1.0", tkinter.END)
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.app.log_message(self.log_display, "Form has been reset.")

    def run_automation_logic(self):
        """The core logic for the Update Estimate automation."""
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, self.app.set_status, "Running: Update Estimate")
        self.app.log_message(self.log_display, "Starting Update Estimate automation...")

        outcome_value = self.estimated_outcome_entry.get().strip()
        work_codes = [line.strip() for line in self.work_key_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]

        if not outcome_value:
            messagebox.showerror("Input Error", "Estimated Outcome cannot be empty.")
            self.app.after(0, self.set_ui_state, False); return
        if not work_codes:
            messagebox.showerror("Input Error", "No work codes provided.")
            self.app.after(0, self.set_ui_state, False); return

        try:
            driver = self.app.get_driver()
            if not driver: return

            wait = WebDriverWait(driver, 15)
            driver.get(config.UPDATE_ESTIMATE_CONFIG["url"])
            
            total_tasks = len(work_codes)
            for i, work_code in enumerate(work_codes, 1):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Automation stopped by user.", "warning"); break
                
                self.app.after(0, self.update_status, f"Processing {i}/{total_tasks}: {work_code}", (i / total_tasks))
                self._process_single_task(driver, wait, work_code, outcome_value)

            if not self.app.stop_events[self.automation_key].is_set():
                messagebox.showinfo("Completed", "Automation finished! Check the 'Results' tab for details.")

        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
            messagebox.showerror("Automation Error", f"An unexpected error occurred: {e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Finished", 1.0)
            self.app.after(0, self.app.set_status, "Ready")

    def _process_single_task(self, driver, wait, work_code, outcome):
        """Processes a single work code and outcome value."""
        try:
            # Add a 1-second delay before starting to avoid race conditions
            time.sleep(1)

            search_box = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtwrksearchkey")))
            search_box.clear()
            search_box.send_keys(work_code)
            driver.execute_script("arguments[0].onchange();", search_box)
            
            work_dropdown_element = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlworkName")))
            wait.until(lambda d: len(Select(d.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlworkName")).options) > 1)
            Select(work_dropdown_element).select_by_index(1)

            outcome_box = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_Txtest_outcome")))
            outcome_box.clear()
            outcome_box.send_keys(outcome)

            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_Btnsubmit").click()

            # --- NEW LOGIC: Check for on-page message first, then alert ---
            try:
                # Wait up to 5 seconds for the success message to appear
                success_label = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_Lblerror"))
                )
                message_text = success_label.text
                if "update successfully" in message_text.lower():
                    self._log_result(work_code, outcome, "Success", message_text)
                else:
                    self._log_result(work_code, outcome, "Failed", message_text, is_error=True)
            except TimeoutException:
                # If the label doesn't appear, check for an alert as a fallback
                try:
                    alert = wait.until(EC.alert_is_present())
                    alert_text = alert.text
                    alert.accept()
                    self._log_result(work_code, outcome, "Failed", f"Alert: {alert_text}", is_error=True)
                except TimeoutException:
                    self._log_result(work_code, outcome, "Failed", "No success message or alert found after saving.", is_error=True)

        except (TimeoutException, NoSuchElementException) as e:
            error_msg = "Page timed out or element not found." if isinstance(e, TimeoutException) else "A required element was not found on the page."
            self._log_result(work_code, outcome, "Failed", error_msg, is_error=True)
        except Exception as e:
            self._log_result(work_code, outcome, "Failed", f"An unexpected error occurred: {e}", is_error=True)

    # --- NEW: Local extractor for FULL work codes ---
    def _extract_full_workcodes(self):
        """
        Extracts full work codes (e.g., 34.../.../123) from the textbox content.
        This is a local method because this tab requires the FULL work code,
        not the 6-digit suffix from the base tab's extractor.
        """
        try:
            input_content = self.work_key_text.get("1.0", tkinter.END)
            if not input_content.strip():
                return

            # Pattern for full work codes (e.g., 3404003009/IF/123456)
            work_code_pattern = re.compile(r'\b(34\d{8}(?:/\w+)+/\d+)\b')
            
            found_work_codes = work_code_pattern.findall(input_content)

            # Remove duplicates while preserving order
            final_results = list(dict.fromkeys(found_work_codes))

            if final_results:
                self.work_key_text.configure(state="normal")
                self.work_key_text.delete("1.0", tkinter.END)
                self.work_key_text.insert("1.0", "\n".join(final_results))
                messagebox.showinfo("Extraction Complete", f"Found and extracted {len(final_results)} unique full work codes.", parent=self)
            else:
                messagebox.showinfo("No Codes Found", "Could not find any matching full work codes (e.g., 34.../.../...).", parent=self)
        
        except Exception as e:
            messagebox.showerror("Extraction Error", f"An error occurred during extraction: {e}", parent=self)

    def _log_result(self, work_code, outcome, status, details, is_error=False):
        """Logs the result to the UI."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_level = "error" if is_error else "success"
        self.app.log_message(self.log_display, f"'{work_code}' - {status.upper()}: {details}", level=log_level)
        tags = ('failed',) if is_error else ()
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(work_code, outcome, status.upper(), details, timestamp), tags=tags))
    
    def export_report(self):
        """Exports the data from the results tree to the selected format."""
        export_format = self.export_format_menu.get()
        
        all_items = self.results_tree.get_children()
        if not all_items:
            messagebox.showinfo("No Data", "There are no results to export.")
            return

        data_to_export = [self.results_tree.item(item_id)['values'] for item_id in all_items]
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Update_Estimate_Report_{timestamp}"

        if "CSV" in export_format:
            self.export_treeview_to_csv(self.results_tree, f"{filename}.csv")
        elif "PDF" in export_format:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF Document", "*.pdf")],
                initialdir=self.app.get_user_downloads_path(),
                initialfile=f"{filename}.pdf",
                title="Save PDF Report"
            )
            if not file_path: return
            
            try:
                headers = self.results_tree['columns']
                col_widths = [70, 35, 35, 110, 25] # Adjusted for A4 Landscape
                title = "Update Estimate Report"
                report_date = datetime.now().strftime('%d %b %Y')
                
                success = self.generate_report_pdf(data_to_export, headers, col_widths, title, report_date, file_path)
                
                if success:
                    if messagebox.askyesno("Success", f"PDF Report exported to:\n{file_path}\n\nDo you want to open the file?"):
                        if sys.platform == "win32": os.startfile(file_path)
                        else: subprocess.call(['open', file_path])
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to create PDF file.\n\nError: {e}")