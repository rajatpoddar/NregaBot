# tabs/issued_mr_report_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time, os, re, json
from datetime import datetime

# --- Imports ---
# --- End Imports ---

from src.utils import resource_path, get_logger
from .base_tab import BaseAutomationTab

logger = get_logger()
from src import config
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException  # noqa: F401


from webdriver_manager.chrome import ChromeDriverManager

class IssuedMrReportTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="issued_mr_report")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1) 
        
        # Headers for Standard Issued MR Report
        self.report_headers = [
            "S No.", "Panchayat", "Work Code", "Work Name", 
            "Work Category", "Work Type", "Agency Name"
        ]

        # --- NEW: Headers for ABPS Pending Report ---
        self.abps_report_headers = [
            "S No.", "Panchayat", "Jobcard No.", "Worker Name", "ABPS Status"
        ]
        
        # Shared browser use karega (self.app.get_driver()) — apna driver nahi banayega
        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:

        # ── Header card ──
        self._create_header_card(self, "📄", "Issued MR Report",
                                 "Pull issued muster-roll reports with workcodes, results and ABPS data.",
                                 icon_key="emoji_issued_mr_report")

        # Frame for all user input controls
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        controls_frame.grid(row=1, column=0, sticky="new", padx=10, pady=(0, 6))
        controls_frame.grid_columnconfigure(1, weight=1)

        # --- Input Fields ---
        # --- Create all entries first (no cross-references) ---
        ctk.CTkLabel(controls_frame, text="State:").grid(row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        s_vals = self.app.history_manager.get_suggestions("location_state") or [""]
        self.state_var = ctk.StringVar()
        self.state_menu = ctk.CTkOptionMenu(controls_frame, variable=self.state_var, values=s_vals)
        self.state_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))

        ctk.CTkLabel(controls_frame, text="District:").grid(row=1, column=0, sticky='w', padx=15, pady=5)
        d_vals = self.app.history_manager.get_suggestions("location_district") or [""]
        self.district_var = ctk.StringVar()
        self.district_menu = ctk.CTkOptionMenu(controls_frame, variable=self.district_var, values=d_vals)
        self.district_menu.grid(row=1, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text="Block:").grid(row=2, column=0, sticky='w', padx=15, pady=5)
        b_vals = self.app.history_manager.get_suggestions("location_block") or [""]
        self.block_var = ctk.StringVar()
        self.block_menu = ctk.CTkOptionMenu(controls_frame, variable=self.block_var, values=b_vals)
        self.block_menu.grid(row=2, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=3, column=0, sticky='w', padx=15, pady=5)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=config.ALL_PANCHAYATS_LABEL)
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=self._all_panchayat_values(p_vals))
        self.panchayat_menu.grid(row=3, column=1, sticky='ew', padx=15, pady=5)

        # --- Wire up location hierarchy callbacks now (all widgets exist) ---
        def _on_state_change(*_):
            self.district_var.set(""); self.block_var.set(""); self.panchayat_var.set("")
            vals = self.app.history_manager.get_filtered_suggestions("location_district", "location_state", self.state_var.get()) or [""]
            self.district_menu.configure(values=vals)
        self.state_var.trace_add("write", _on_state_change)
        
        def _on_district_change(*_):
            self.block_var.set(""); self.panchayat_var.set("")
            vals = self.app.history_manager.get_filtered_suggestions("location_block", "location_district", self.district_var.get()) or [""]
            self.block_menu.configure(values=vals)
        self.district_var.trace_add("write", _on_district_change)
        
        def _on_block_change(*_):
            self.panchayat_var.set(config.ALL_PANCHAYATS_LABEL)
            vals = self.app.history_manager.get_filtered_suggestions("location_panchayat", "location_block", self.block_var.get()) or [""]
            self.panchayat_menu.configure(values=self._all_panchayat_values(vals))
        self.block_var.trace_add("write", _on_block_change)

        # ── Action buttons (OUTSIDE the card) ──
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        # --- NEW BUTTON FOR ABPS CHECK (next to main actions) ---
        self.btn_abps_check = ctk.CTkButton(
            self,
            text="Pending demand labour for abps",
            command=self.start_abps_automation,
            fg_color=config.COLORS["purple_report"], # Purple color to distinguish
            hover_color=config.COLORS["purple_report_hover"]
        )
        self.btn_abps_check.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 6))

        # --- Output Tabs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        workcode_tab = notebook.add("Workcode List")
        results_tab = notebook.add("Results Table")
        
        # --- NEW TAB FOR ABPS ---
        abps_tab = notebook.add("ABPS Pending Results")
        
        self._create_log_and_status_area(parent_notebook=notebook)

        # 1. Workcode List Tab
        workcode_tab.grid_columnconfigure(0, weight=1)
        workcode_tab.grid_rowconfigure(1, weight=1)
        
        copy_frame = ctk.CTkFrame(workcode_tab, fg_color="transparent")
        copy_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        self.copy_wc_button = ctk.CTkButton(copy_frame, text="Copy Workcodes", command=self._copy_workcodes)
        self.copy_wc_button.pack(side="left")

        self.run_dup_mr_button = ctk.CTkButton(copy_frame,
                                                  text="Run Duplicate MR Print",
                                                  command=self._run_duplicate_mr,
                                                  fg_color="#D35400", 
                                                  hover_color="#E67E22")
        self.run_dup_mr_button.pack_forget() 

        self.workcode_textbox = ctk.CTkTextbox(workcode_tab, state="disabled")
        self.workcode_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # 2. Results Tab (Table)
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        export_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.export_button = ctk.CTkButton(export_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side="left")

        self.results_tree = ttk.Treeview(results_tab, columns=self.report_headers, show='headings')
        for col in self.report_headers: 
            self.results_tree.heading(col, text=col)
            
        self.results_tree.column("S No.", width=40, anchor='center')
        self.results_tree.column("Panchayat", width=100)
        self.results_tree.column("Work Code", width=200)
        self.results_tree.column("Work Name", width=350)
        self.results_tree.column("Work Category", width=150)
        self.results_tree.column("Work Type", width=150)
        self.results_tree.column("Agency Name", width=100)

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

        # 3. ABPS Pending Results Tab (NEW)
        abps_tab.grid_columnconfigure(0, weight=1)
        abps_tab.grid_rowconfigure(1, weight=1)

        abps_export_frame = ctk.CTkFrame(abps_tab, fg_color="transparent")
        abps_export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.abps_export_button = ctk.CTkButton(abps_export_frame, text="Export ABPS Data", command=self.export_abps_report)
        self.abps_export_button.pack(side="left")

        self.abps_tree = ttk.Treeview(abps_tab, columns=self.abps_report_headers, show='headings')
        for col in self.abps_report_headers:
            self.abps_tree.heading(col, text=col)
        
        self.abps_tree.column("S No.", width=50, anchor="center")
        self.abps_tree.column("Panchayat", width=150)
        self.abps_tree.column("Jobcard No.", width=200)
        self.abps_tree.column("Worker Name", width=250)
        self.abps_tree.column("ABPS Status", width=100, anchor="center")

        self.abps_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        abps_scrollbar = ctk.CTkScrollbar(abps_tab, command=self.abps_tree.yview)
        self.abps_tree.configure(yscroll=abps_scrollbar.set); abps_scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.abps_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.state_menu.configure(state=state)
        self.district_menu.configure(state=state)
        self.block_menu.configure(state=state)
        self.panchayat_menu.configure(state=state)
        self.run_dup_mr_button.configure(state=state)
        self.btn_abps_check.configure(state=state)
        self.abps_export_button.configure(state=state)
    def reset_ui(self) -> None:
        self.state_var.set("")
        self.district_var.set("")
        self.block_var.set("")
        self.panchayat_var.set(config.ALL_PANCHAYATS_LABEL)
        
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        for item in self.abps_tree.get_children(): self.abps_tree.delete(item)
        self._update_workcode_textbox("")
        
        self.log_info("Form has been reset.")
        self.update_status("Ready", 0.0)
        

    def start_automation(self) -> None:
        """Standard Issued MR Report Automation (Specific Panchayat)"""
        self.run_dup_mr_button.pack_forget()
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self._update_workcode_textbox("") 
        
        inputs = {
            'state': self.state_var.get().strip(), 
            'district': self.district_var.get().strip(), 
            'block': self.block_var.get().strip(),
            'panchayat': self.panchayat_var.get().strip(),
        }
        
        if not all([inputs['state'], inputs['district'], inputs['block'], inputs['panchayat']]):
            messagebox.showwarning("Input Error", "All fields are required."); return
        if inputs['panchayat'] == config.ALL_PANCHAYATS_LABEL:
            if not messagebox.askyesno("Confirm", "This will process ALL panchayats in the block. Continue?"):
                return
        
        self.save_inputs(inputs)
        
        driver = self.app.get_driver()
        if not driver:
            messagebox.showwarning("Browser Required", "Kripya pehle 'Launch Chrome' button se browser start karein.")
            return
        
        self.app.after(0, self.set_ui_state, True) 
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def start_abps_automation(self):
        """Logic for the new ABPS Check Button (All Panchayats in Block)"""
        for item in self.abps_tree.get_children(): self.abps_tree.delete(item)
        
        inputs = {
            'state': self.state_var.get().strip(), 
            'district': self.district_var.get().strip(), 
            'block': self.block_var.get().strip(),
            # Panchayat is intentionally ignored here
        }
        
        if not all([inputs['state'], inputs['district'], inputs['block']]):
            messagebox.showwarning("Input Error", "State, District and Block are required."); return
        
        driver = self.app.get_driver()
        if not driver:
            messagebox.showwarning("Browser Required", "Kripya pehle 'Launch Chrome' button se browser start karein.")
            return
        
        self.app.after(0, self.set_ui_state, True) 
        self.app.start_automation_thread(self.automation_key, self.run_abps_automation_logic, args=(inputs,))

    def _solve_captcha(self, driver, wait):
        """Solve CAPTCHA — tries hidden field answer first, falls back to math parsing."""
        self.log_info("Attempting to solve CAPTCHA...")
        textbox_id = "ContentPlaceHolder1_txtCaptcha"
        btn_id = "ContentPlaceHolder1_btnLogin"

        # Strategy 1: Read the hidden answer field (new portal has hfCaptcha)
        try:
            hf = driver.find_element(By.ID, "ContentPlaceHolder1_hfCaptcha")
            answer = hf.get_attribute("value")
            if answer and answer.strip().isdigit():
                self.log_info(f"CAPTCHA solved via hidden field: {answer.strip()}")
                driver.find_element(By.ID, textbox_id).send_keys(answer.strip())
                driver.find_element(By.ID, btn_id).click()
                time.sleep(2)
                if "Invalid Captcha Code" not in driver.page_source:
                    return True
        except Exception:
            pass

        # Strategy 2: Parse the math expression from label
        captcha_label_id = "ContentPlaceHolder1_lblStopSpam"
        try:
            captcha_text = wait.until(EC.presence_of_element_located((By.ID, captcha_label_id))).text
            match = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha_text)
            if not match:
                raise ValueError(f"Could not parse CAPTCHA from: {captcha_text}")
            num1, operator, num2 = match.groups(); num1, num2 = int(num1), int(num2)
            result = { '+': num1 + num2, '-': num1 - num2, '*': num1 * num2 }[operator]
            self.log_info(f"CAPTCHA solved: {captcha_text.strip()} = {result}")
            driver.find_element(By.ID, textbox_id).send_keys(str(result))
            driver.find_element(By.ID, btn_id).click()
            time.sleep(2)
            return True
        except TimeoutException:
            self.log_info("CAPTCHA not found or already bypassed.")
            return True
        except Exception as e:
            self.log_error(f"CAPTCHA Error: {e}")
            raise

    def _handle_report_drilldown(self, driver, wait, inputs):
        """
        After opening a report page, drill down to district/block level.
        Handles two patterns:
        1. Dropdown-based (district→block select elements) — new portal
        2. Link-based (click district name → click block name) — old portal
        """
        state = inputs.get('state', '')
        district = inputs.get('district', '')
        block = inputs.get('block', '')

        # Pattern 1: Check for state/district/block dropdowns on the report page
        try:
            state_select = driver.find_element(By.ID, "ContentPlaceHolder1_ddl_States")
            if state_select.is_displayed():
                self.log_info("State dropdown found on report page, selecting...")
                self._select_by_text_case_insensitive(Select(state_select), state)
                time.sleep(2)

                # Check for district dropdown
                try:
                    district_select = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_District"))
                    )
                    if district_select.is_displayed() and district:
                        self.log_info(f"District dropdown found, selecting: {district}")
                        self._select_by_text_case_insensitive(Select(district_select), district)
                        time.sleep(2)

                        # Check for block dropdown
                        try:
                            block_select = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_Block"))
                            )
                            if block_select.is_displayed() and block:
                                self.log_info(f"Block dropdown found, selecting: {block}")
                                self._select_by_text_case_insensitive(Select(block_select), block)
                                time.sleep(2)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # Pattern 2: Check for district/block links on page (old portal style)
        if district:
            try:
                district_link = driver.find_element(By.XPATH, f"//a[contains(normalize-space(), '{district.upper()}')]")
                if district_link.is_displayed():
                    self.log_info(f"Clicking district link: {district}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", district_link)
                    time.sleep(0.5)
                    district_link.click()
                    time.sleep(2)

                    if block:
                        try:
                            block_link = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, f"//a[contains(normalize-space(), '{block.upper()}')]"))
                            )
                            self.log_info(f"Clicking block link: {block}")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", block_link)
                            time.sleep(0.5)
                            block_link.click()
                            time.sleep(2)
                        except Exception:
                            pass
            except Exception:
                pass

    def run_automation_logic(self, inputs, retries=1):
        # Standard Issued MR Report Logic (Panchayat Specific)
        self.app.after(0, self.app.set_status, "Starting Issued MR Report...") 
        self.app.after(0, self.update_status, "Initializing...", 0.0)
        self.app.clear_log(self.log_display)
        self.log_info("Starting Issued MR Report automation...")
        try:
            driver = self.app.get_driver()
            if not driver: return 

            wait = WebDriverWait(driver, 20)

            self.app.after(0, self.app.set_status, "Navigating to MIS portal...")
            driver.get(config.MIS_REPORTS_CONFIG["base_url"])

            self._solve_captcha(driver, wait)

            self.log_info(f"Selecting State: {inputs['state']}...")
            state_select = wait.until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_States")))
            self._select_by_text_case_insensitive(Select(state_select), inputs['state'])
            time.sleep(4)  # Wait for postback to load accordion
            self.log_info("Waiting for report accordion to load...")
            wait.until(EC.presence_of_element_located((By.ID, "accordionMain")))

            # Expand all accordion sections so report links are visible
            self.log_info("Opening Report...")
            driver.execute_script("""
                document.querySelectorAll('.accordion-collapse').forEach(function(el) {
                    el.classList.add('show');
                });
            """)
            time.sleep(0.5)

            report_link_text = "VBGRAMG daily status as per e-muster issued"
            report_link = driver.find_element(By.XPATH, f"//a[contains(normalize-space(.), '{report_link_text}')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", report_link)
            time.sleep(0.5); report_link.click()

            self.log_info(f"Drilling down to district/block: {inputs['district']} > {inputs['block']}")
            self._handle_report_drilldown(driver, wait, inputs)

            # --- Specific Panchayat Logic ---
            self.log_info(f"Finding Panchayat: {inputs['panchayat']}")

            # Find the panchayat summary table
            main_table_xpath = "//table[@width='80%'][.//b[text()='SNo.'] and .//b[text()='Panchayats']]"
            wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))

            def _reopen_report():
                """Re-navigate to the issued MR summary page (all panchayats of the block)."""
                driver.get(config.MIS_REPORTS_CONFIG["base_url"])
                self._solve_captcha(driver, wait)
                state_select = wait.until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_States")))
                self._select_by_text_case_insensitive(Select(state_select), inputs['state'])
                time.sleep(4)
                wait.until(EC.presence_of_element_located((By.ID, "accordionMain")))
                driver.execute_script("""
                    document.querySelectorAll('.accordion-collapse').forEach(function(el) {
                        el.classList.add('show');
                    });
                """)
                time.sleep(0.5)
                report_link = driver.find_element(By.XPATH, "//a[contains(normalize-space(.), 'VBGRAMG daily status as per e-muster issued')]")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", report_link)
                time.sleep(0.5); report_link.click()
                self._handle_report_drilldown(driver, wait, inputs)
                wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))

            target_panchayat = inputs['panchayat'].strip()
            all_mode = target_panchayat in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL)
            saved_mode = target_panchayat == config.MY_PANCHAYATS_LABEL

            # Collect target panchayat name(s) from the summary table
            panchayat_names = []
            rows_all = driver.find_elements(By.XPATH, f"{main_table_xpath}//tr[td]")
            for row in rows_all:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 6:
                    p_name = cells[1].text.strip()
                    if all_mode:
                        if p_name and not self._is_aggregate_panchayat_name(p_name):
                            panchayat_names.append(p_name)
                    elif p_name.lower() == target_panchayat.lower():
                        panchayat_names.append(p_name)
                        break
            if saved_mode:
                panchayat_names = self._filter_panchayats_to_saved(panchayat_names)
                self.log_info(f"⭐ My Saved Panchayats mode: {len(panchayat_names)} saved panchayat(s) will be processed.")
            if not panchayat_names:
                if all_mode:
                    if saved_mode:
                        self.log_warning("⚠️ No saved panchayat found in the summary table. Check Settings > Location Data.")
                    else:
                        self.log_warning("No panchayats found in the summary table.")
                    self.success_message = None
                    return
                raise ValueError(f"Panchayat '{target_panchayat}' not found in table.")

            workcode_list = []
            scraped_mr_count = 0
            total_p = len(panchayat_names)
            need_back = False
            for p_idx, p_name in enumerate(panchayat_names):
                if self.is_stopped(): break
                self.log_info(f"===== Panchayat {p_idx+1}/{total_p}: {p_name} =====")
                self.app.after(0, self.update_status, f"Scanning {p_name} ({p_idx+1}/{total_p})...", p_idx / max(total_p, 1))

                # Navigate to the summary table: fast path = 1 step back (only if
                # the previous panchayat actually opened a report page);
                # fallback = full report reload
                panchayat_row = None
                for nav_attempt in range(2):
                    if nav_attempt == 0:
                        if need_back:
                            try:
                                driver.back()
                                time.sleep(0.5)
                                WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, main_table_xpath))
                                )
                            except Exception:
                                self.log_info("Back navigation failed, re-opening report...")
                                _reopen_report()
                    else:
                        self.log_info("Reloading report to find the panchayat...")
                        _reopen_report()

                    # Re-locate the panchayat row (case-insensitive, with retry)
                    panchayat_row = None
                    for attempt in range(3):
                        rows = driver.find_elements(By.XPATH, f"{main_table_xpath}//tr[td]")
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 6 and cells[1].text.strip().lower() == p_name.lower():
                                panchayat_row = row
                                break
                        if panchayat_row is not None:
                            break
                        time.sleep(1)
                    if panchayat_row is not None:
                        break
                if panchayat_row is None:
                    self.log_warning(f"Panchayat '{p_name}' not found in table. Skipping.")
                    need_back = False
                    continue

                self.log_info(f"Found row for {p_name}. Looking for MR Issued link in column 6...")
                target_cell = panchayat_row.find_element(By.XPATH, "./td[6]") # Column 6 = No. of Ongoing Works (MRs Issued)

                try:
                    target_link = target_cell.find_element(By.TAG_NAME, "a")
                    link_text = target_link.text.strip()
                    if link_text == '0':
                        if not all_mode:
                            self.log_warning("Value is 0. No data.")
                            self.success_message = "No data found (Value 0)"
                            return
                        self.log_warning(f"Value is 0 for {p_name}. No data.")
                        need_back = False
                        continue

                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_link)
                    time.sleep(0.5)
                    target_link.click()
                    need_back = True

                except NoSuchElementException:
                    need_back = False
                    if not all_mode:
                        self.log_warning("No link found in cell.")
                        self.success_message = "No data found (Value 0)"
                        return
                    self.log_warning(f"No link found in cell for {p_name}. Skipping.")
                    continue

                self.log_info(f"Scraping final table for {p_name}...")
                # Detail page table: Bootstrap-styled with <th> headers (not <b> inside <td>)
                FINAL_TABLE_XPATH = "//table[contains(@class, 'table-striped') and .//th[contains(text(), 'Work Code')]]"
                try:
                    table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, FINAL_TABLE_XPATH)))
                except TimeoutException:
                    # Report page didn't load — assume no navigation happened
                    need_back = False
                    self.log_warning(f"Final table not found for {p_name}. Skipping.")
                    continue
                # ⚡ FAST READ: fetch the entire table's cell text in ONE round trip
                try:
                    all_rows_data = driver.execute_script(
                        "var rows = arguments[0].querySelectorAll('tr'); var out = []; "
                        "for (var r = 1; r < rows.length; r++) { var c = rows[r].querySelectorAll('td'); var arr = []; "
                        "for (var i = 0; i < c.length; i++) { arr.push((c[i].innerText || '').trim()); } out.push(arr); } return out;",
                        table
                    ) or []
                except Exception as e:
                    self.log_warning(f"Could not read final table for {p_name}: {str(e)[:120]} Skipping.")
                    continue

                insert_buffer = []
                for i, row_data in enumerate(all_rows_data):
                    if self.is_stopped(): break

                    if not row_data or len(row_data) < len(self.report_headers): continue

                    scraped_data = row_data[:len(self.report_headers)]
                    # Continuous S.No. across all panchayats + explicit Panchayat name
                    scraped_mr_count += 1
                    scraped_data[0] = str(scraped_mr_count)
                    scraped_data[1] = p_name
                    work_code = scraped_data[2]
                    insert_buffer.append(tuple(scraped_data))
                    if work_code: workcode_list.append(work_code)

                    # Batched tree inserts (keeps the UI snappy)
                    if len(insert_buffer) >= 50:
                        batch = list(insert_buffer)
                        insert_buffer.clear()
                        self.app.after(0, lambda b=batch: self._insert_rows_batch(b))

                    # Throttled progress — keyed on the row index
                    if i % 50 == 0 or i == len(all_rows_data) - 1:
                        self.app.after(0, self.update_status, f"Scraping {p_name} ({i+1}/{len(all_rows_data)})...", 0.55 + ((i+1)/max(len(all_rows_data), 1))*0.3)

                if insert_buffer:
                    batch = list(insert_buffer)
                    insert_buffer.clear()
                    self.app.after(0, lambda b=batch: self._insert_rows_batch(b))

            unique_workcodes = list(dict.fromkeys(workcode_list))
            self.app.after(0, self._update_workcode_textbox, "\n".join(unique_workcodes))

            self.log_success(f"Completed. Found {scraped_mr_count} MRs.")
            self.success_message = f"Found {scraped_mr_count} Issued MRs in {inputs['panchayat']}."


        except Exception as e:
            self.log_error(f"Error: {e}")
            self.success_message = None
        finally:
            # Shared browser use kar rahe hain — isliye driver.quit() nahi karte
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")
            if hasattr(self, 'success_message') and self.success_message:
                self.log_info(f"📊 Issued MR Report Complete: {self.success_message}")

    def run_abps_automation_logic(self, inputs):
        """New Logic for scanning the whole block for ABPS Pending workers."""
        self.app.after(0, self.app.set_status, "Scanning Block for ABPS Pending...") 
        self.app.after(0, self.update_status, "Initializing...", 0.0)
        self.app.clear_log(self.log_display)
        self.log_info("Starting ABPS Pending Scan (All Panchayats)...")
        try:
            driver = self.app.get_driver()
            if not driver: return 
            wait = WebDriverWait(driver, 20)

            # 1. Navigate to Block Dashboard (Reuse logic)
            self.log_info("Navigating to Dashboard...")
            driver.get(config.MIS_REPORTS_CONFIG["base_url"])
            self._solve_captcha(driver, wait)

            state_select = wait.until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_States")))
            self._select_by_text_case_insensitive(Select(state_select), inputs['state'])
            time.sleep(4)  # Wait for postback to load accordion
            self.log_info("Waiting for report accordion to load...")
            wait.until(EC.presence_of_element_located((By.ID, "accordionMain")))

            # Expand all accordion sections so report links are visible
            self.log_info("Opening Report...")
            driver.execute_script("""
                document.querySelectorAll('.accordion-collapse').forEach(function(el) {
                    el.classList.add('show');
                });
            """)
            time.sleep(0.5)

            report_link = driver.find_element(By.XPATH, f"//a[contains(normalize-space(.), 'VBGRAMG daily status as per e-muster issued')]")
            report_link.click()
            time.sleep(3)

            self.log_info(f"Drilling down to district/block: {inputs['district']} > {inputs['block']}")
            self._handle_report_drilldown(driver, wait, inputs)

            # 2. Scrape All Panchayat Links from Column 5
            self.log_info("Scanning Dashboard for Panchayat Links (Column 5)...")            
            # Use specific XPath for table
            table_xpath = "//table[.//b[text()='Panchayats']]"
            wait.until(EC.presence_of_element_located((By.XPATH, table_xpath)))
            
            # Find all rows (skip headers)
            all_rows = driver.find_elements(By.XPATH, f"{table_xpath}//tr[td]")
            
            panchayat_links = []
            
            for row in all_rows:
                try:
                    # Col 2 = Panchayat Name
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 5: continue
                    
                    p_name = cols[1].text.strip()
                    
                    # --- FILTERS ADDED ---
                    # 1. Skip Total Row
                    if p_name.lower() == "total": continue 
                    # 2. Skip Number Row (Header like "1", "2"...) - Yahi error de raha tha
                    if p_name.isdigit(): continue
                    
                    # Col 5 = Expected Labour (Link)
                    try:
                        link_elem = cols[4].find_element(By.TAG_NAME, "a")
                        href = link_elem.get_attribute("href")
                        
                        # Only add if it's a real link, not a javascript postback (sorting arrows)
                        if href and "javascript" not in href.lower():
                            panchayat_links.append((p_name, href))
                    except NoSuchElementException:
                        # Value is 0 or text, skip
                        pass
                except Exception:
                    pass
            
            total_gps = len(panchayat_links)
            self.log_info(f"Found {total_gps} Panchayats with data to scan.")            
            if total_gps == 0:
                self.log_warning("No data found in Column 5 for any Panchayat.")
                return

            # 3. Iterate through each Panchayat Link
            count = 0
            for index, (p_name, href) in enumerate(panchayat_links):
                if self.is_stopped(): break
                
                progress = (index / total_gps)
                self.app.after(0, self.update_status, f"Scanning {p_name}...", progress)
                self.log_info(f"Checking Panchayat: {p_name} ({index+1}/{total_gps})")                
                try:
                    driver.get(href) # Direct navigation
                    
                    # Wait for Detail Table
                    detail_table_id = "ContentPlaceHolder1_GridFtomusteroll"
                    
                    # Short timeout check, if no data, skip
                    try:
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, detail_table_id)))
                    except TimeoutException:
                        self.log_info(f"   > No table found for {p_name}. Skipping.")
                        continue

                    # Scan Rows
                    # Get rows where Last Column (ABPS) contains "No"
                    # Optimization: Get all rows first
                    rows = driver.find_elements(By.XPATH, f"//table[@id='{detail_table_id}']//tr[position()>1]")
                    
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if not cells: continue
                        
                        # Indices (0-based):
                        # 1: Jobcard No
                        # 2: Worker Name
                        # Last: ABPS Enabled
                        
                        abps_status = cells[-1].text.strip()
                        
                        if abps_status.lower() == "no":
                            count += 1
                            jobcard = cells[1].text.strip()
                            name = cells[2].text.strip()
                            
                            row_data = (count, p_name, jobcard, name, "No")
                            self.app.after(0, lambda data=row_data: self.abps_tree.insert("", "end", values=data))
                            
                except Exception as e:
                    self.log_error(f"   > Error scanning {p_name}: {str(e)[:50]}")
                    continue

            self.success_message = f"ABPS Scan Complete. Found {count} pending workers."
            self.log_success(self.success_message)
        except Exception as e:
            self.log_error(f"Critical Error in ABPS Scan: {e}")
            self.success_message = None
        finally:
            # Shared browser use kar rahe hain — isliye driver.quit() nahi karte
            self.app.after(0, self.set_ui_state, False)
            if hasattr(self, 'success_message') and self.success_message:
                self.log_info(f"📊 Issued MR Complete: {self.success_message}")

    def _update_workcode_textbox(self, text):
        self.workcode_textbox.configure(state="normal")
        self.workcode_textbox.delete("1.0", tkinter.END)
        self.workcode_textbox.insert("1.0", text)
        self.workcode_textbox.configure(state="disabled")

    def _copy_workcodes(self):
        text = self.workcode_textbox.get("1.0", tkinter.END).strip()
        if text:
            self.app.clipboard_clear()
            self.app.clipboard_append(text)
            messagebox.showinfo("Copied", f"{len(text.splitlines())} workcodes copied to clipboard.", parent=self)
        else:
            messagebox.showwarning("Empty", "There are no workcodes to copy.", parent=self)

    def _run_duplicate_mr(self):
        workcodes = self.workcode_textbox.get("1.0", tkinter.END).strip()
        panchayat_name = self.panchayat_var.get().strip()

        if not workcodes:
            messagebox.showwarning("No Data", "There are no workcodes to send.", parent=self)
            return
        
        if not panchayat_name:
            messagebox.showwarning("No Data", "Panchayat name is missing.", parent=self)
            return

        self.app.switch_to_duplicate_mr_with_data(workcodes, panchayat_name)

    def export_report(self):
        """Export results to professional Excel."""
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "There are no results to export.")
            return

        panchayat = self.panchayat_var.get().strip() or "Report"
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', panchayat)
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"Issued_MR_{safe_panchayat}-{current_date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=f"Issued MR Report - {panchayat}"
        )

    def export_abps_report(self):
        """Export ABPS report to professional Excel."""
        if not self.abps_tree.get_children():
            messagebox.showinfo("No Data", "There are no ABPS results to export.")
            return
            
        block = self.block_var.get().strip() or "Block"
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', block)
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        
        self.export_treeview_to_excel(
            tree=self.abps_tree,
            default_filename=f"ABPS_Pending_Report_{safe_name}_{current_date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=f"ABPS Pendency Report - {block}"
        )
                

    def generate_report_pdf(self, data, headers, col_widths, title, date_str, file_path):
        return super().generate_report_pdf(data, headers, col_widths, title, date_str, file_path)

    def _wrap_text(self, text, font, max_width):
        return super()._wrap_text(text, font, max_width)

        
    def save_inputs(self, inputs):
        save_data = {k: inputs.get(k) for k in ('state', 'district', 'block', 'panchayat')}
        try:
            self.app.history_manager.save_tab_inputs_batch("issued_mr_report", save_data)
        except Exception as e:
            logger.warning("Failed to save Issued MR inputs: %s", e)

    def load_inputs(self):
        """Load previously saved inputs from DB."""
        try:
            data = self.app.history_manager.get_tab_inputs("issued_mr_report")
            if data:
                self.state_var.set(data.get('state', ''))
                self.district_var.set(data.get('district', ''))
                self.block_var.set(data.get('block', ''))
                self.panchayat_var.set(data.get('panchayat') or config.ALL_PANCHAYATS_LABEL)
        except Exception as e:
            logger.warning("Failed to load Issued MR inputs: %s", e)