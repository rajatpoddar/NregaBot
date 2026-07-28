# tabs/resend_rejected_wg_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime

from src import config
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple

class ResendRejectedWgTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        # Lazy imports
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        super().__init__(parent, app_instance, automation_key="resend_wg")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self._create_widgets()
    def _create_widgets(self) -> None:
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver

        # Frame for user controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure(1, weight=1)

        # Financial Year
        ctk.CTkLabel(controls_frame, text="Financial Year:").grid(row=0, column=0, padx=15, pady=10, sticky="w")
        current_year = datetime.now().year
        year_options = [f"{year}-{year+1}" for year in range(current_year + 1, current_year - 10, -1)]
        default_year = f"{current_year}-{current_year+1}" if datetime.now().month >= 4 else f"{current_year-1}-{current_year}"
        self.fin_year_var = ctk.StringVar(value=default_year)
        self.fin_year_menu = ctk.CTkOptionMenu(controls_frame, variable=self.fin_year_var, values=year_options)
        self.fin_year_menu.grid(row=0, column=1, padx=15, pady=10, sticky="ew")

        # Panchayat Selection
        ctk.CTkLabel(controls_frame, text="Panchayat (optional):").grid(row=1, column=0, padx=15, pady=(5,0), sticky="w")
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=1, column=1, padx=15, pady=(5,0), sticky="ew")
        
        self.process_all_var = tkinter.BooleanVar()
        self.process_all_checkbox = ctk.CTkCheckBox(
            controls_frame, 
            text="Process for ALL available Panchayats", 
            variable=self.process_all_var,
            command=self._toggle_panchayat_entry
        )
        self.process_all_checkbox.grid(row=2, column=1, padx=15, pady=(5,15), sticky="w")

        # Action Buttons
        action_frame_container = ctk.CTkFrame(self)
        action_frame_container.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,10))
        action_frame = self._create_action_buttons(parent_frame=action_frame_container)
        action_frame.pack(expand=True, fill='x')

        # Results and Logs
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0,10))
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        cols = ("Timestamp", "Panchayat", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=80, anchor='center')
        self.results_tree.column("Panchayat", width=180)
        self.results_tree.column("Status", width=100, anchor='center')
        self.results_tree.column("Details", width=400)
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def _toggle_panchayat_entry(self):
        if self.process_all_var.get():
            self.panchayat_menu.configure(state="disabled")
        else:
            self.panchayat_menu.configure(state="normal")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.fin_year_menu.configure(state=state)
        self.process_all_checkbox.configure(state=state)
        if not self.process_all_var.get():
            self.panchayat_menu.configure(state=state)
        if running:
             self.panchayat_menu.configure(state="disabled")
    def reset_ui(self) -> None:
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver
        if messagebox.askokcancel("Reset Form?", "This will clear all inputs and results."):
            self.panchayat_var.set("")
            self.process_all_var.set(False)
            self._toggle_panchayat_entry()
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
    def start_automation(self) -> None:
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        
        inputs = {
            'fin_year': self.fin_year_var.get(),
            'panchayat': self.panchayat_entry.get().strip(),
            'process_all': self.process_all_var.get()
        }

        if not inputs['fin_year']:
            messagebox.showerror("Input Error", "Please select a Financial Year.")
            return
        if not inputs['process_all'] and not inputs['panchayat']:
            messagebox.showerror("Input Error", "Please enter a Panchayat name or check the 'Process all' option.")
            return

        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, self.app.set_status, "Running Resend Rejected WG...")
        self.log_info("🚀 Starting Rejected Wagelist Automation...")        total_panchayats = 0
        
        try:
            driver = self.app.get_driver()
            if not driver: return
            wait = WebDriverWait(driver, 20)

            driver.get(config.REJECTED_WL_CONFIG["RESEND_REJECTED_WG"])
            
            self.log_info(f"Selecting Financial Year: {inputs['fin_year']}")            Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlstFinyear")))).select_by_value(inputs['fin_year'])
            
            self.log_info("Waiting for Panchayat list to populate...")            wait.until(EC.presence_of_element_located((By.XPATH, "//select[@id='ctl00_ContentPlaceHolder1_ddlpanch']/option[position()>1]")))

            panchayat_dropdown_element = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlpanch")
            panchayat_options = [opt.text for opt in Select(panchayat_dropdown_element).options if '--Select' not in opt.text]
            
            panchayats_to_process = []
            if inputs['process_all']:
                panchayats_to_process = panchayat_options
                self.log_info(f"Found {len(panchayats_to_process)} Panchayats to process.")            else:
                if inputs['panchayat'] in panchayat_options:
                    panchayats_to_process = [inputs['panchayat']]
                    self.app.update_history("location_panchayat", inputs['panchayat'])
                else:
                    messagebox.showerror("Panchayat Not Found", f"The Panchayat '{inputs['panchayat']}' was not found for the selected year.")
                    return

            total_panchayats = len(panchayats_to_process)
            for i, location_panchayat in enumerate(panchayats_to_process):
                if self.app.stop_events[self.automation_key].is_set():
                    self.log_warning("⏹️ Automation stopped by user.")                    break
                
                pct = (i + 1) / total_panchayats * 100
                self.log_info(f"  🔄 [{i+1}/{total_panchayats}] Panchayat: {location_panchayat} ({pct:.0f}%)")                self.app.after(0, self.update_status, f"Processing {i+1}/{total_panchayats}: {location_panchayat}", (i+1)/total_panchayats)
                self._process_single_panchayat(driver, wait, location_panchayat)

        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")            messagebox.showerror("Automation Error", f"An unexpected error occurred: {e}")
        finally:
            # Count results from tree
            success_count = 0
            fail_count = 0
            skip_count = 0
            for item_id in self.results_tree.get_children():
                vals = self.results_tree.item(item_id)['values']
                if len(vals) >= 3:
                    st = str(vals[2]).lower()
                    if 'success' in st:
                        success_count += 1
                    elif 'fail' in st or 'error' in st:
                        fail_count += 1
                    elif 'skip' in st:
                        skip_count += 1

            stopped = self.app.stop_events[self.automation_key].is_set()
            final_msg = "Process stopped by user." if stopped else "✅ Automation complete."
            self.app.after(0, self.update_status, final_msg, 1.0)
            self.app.after(0, self.set_ui_state, False)
            if not stopped:
                self.log_info(f"
{'='*50}")                self.log_info(f"📊 Resend Rejected WG: ✅ {success_count} sent, ❌ {fail_count} failed, ⏭️ {skip_count} skipped (of {total_panchayats} panchayats)")                self.log_info(f"{'='*50}")            self.app.after(0, self.app.set_status, "Automation Finished")
    
    def _process_single_panchayat(self, driver, wait, location_panchayat):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver
        try:
            html_element = driver.find_element(By.TAG_NAME, 'html')
            panchayat_dropdown = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpanch"))))
            self._select_by_text_case_insensitive(panchayat_dropdown, location_panchayat)
            self.log_info(f"   - Selected {location_panchayat}, waiting for page to update...")
            try:
                wait.until(EC.staleness_of(html_element))
                wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpanch")))
            except TimeoutException:
                self.log_error("   - ERROR: Page failed to load after selecting Panchayat. Server may be slow. Skipping.")                self._log_result(location_panchayat, "Failed", "Page load timeout")
                driver.refresh()
                wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlstFinyear")))
                return

            # --- KEY CHANGE: Use a precise XPath to find the "No Records Found" message in the table ---
            time.sleep(0.5) # Brief pause for content to render
            no_records_elements = driver.find_elements(By.XPATH, "//td[contains(text(), 'No Records Found')]")

            if no_records_elements:
                self.log_info("   - Result: No records found to process.")                self._log_result(location_panchayat, "Skipped", "No records found")
                return

            # If records exist, proceed
            generate_button = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btn_go")))
            self.log_info("   - Records found. Clicking 'Generate Wagelist'.")            generate_button.click()

            alert = wait.until(EC.alert_is_present())
            alert.accept()
            self.log_info("   - Accepted confirmation alert.")
            result_element = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_lblmsg")))
            result_text = result_element.text.strip() if result_element.text else "No specific message returned."
            
            status = "Success" if "successfully" in result_text.lower() else "Info"
            self.log_info(f"   - Result: {result_text}", "success" if status == "Success" else "info")            self._log_result(location_panchayat, status, result_text)
            
            time.sleep(1.5)  # Brief wait for postback to begin

        except Exception as e:
            error_msg = f"An unexpected error occurred: {str(e).splitlines()[0]}"
            self.log_error(f"   - ERROR: {error_msg}")            self._log_result(location_panchayat, "Failed", error_msg)

    def _log_result(self, panchayat, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (timestamp, panchayat, status, details)
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=values))