# tabs/dashboard_report_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time, os, re, json
from datetime import datetime

# --- EXCEL IMPORT ---

# Selenium Imports

# PDF & Image Imports
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont 
from src.utils import resource_path, get_logger
from .base_tab import BaseAutomationTab
from src import config
from src.i18n import tr
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException  # noqa: F401


logger = get_logger()

class DashboardReportTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="dashboard_report")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) 
        
        # Columns to scrape (Strictly 4 columns)
        self.report_headers = [
            "S No.", "Panchayat", "Project Name with code", "E-MR No.", "DateFrom-DateTo"
        ]
        
        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:

        # ── Header / intro card (pending-bills style) ──
        self._create_header_card(self, "📈", tr("tab.dashboard_report.title"), tr("tab.dashboard_report.subtitle"),
                                 icon_key="emoji_dashboard_report")

        # ── Settings card: Location + Delay column ──
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="new", padx=10, pady=(6, 10))
        controls_frame.grid_columnconfigure(1, weight=1)

        # --- Input Fields ---
        # --- Create all entries first (no cross-references) ---
        ctk.CTkLabel(controls_frame, text=tr("common.state_label")).grid(row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        s_vals = self.app.history_manager.get_suggestions("location_state") or [""]
        self.state_var = ctk.StringVar()
        self.state_menu = ctk.CTkOptionMenu(controls_frame, variable=self.state_var, values=s_vals)
        self.state_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))

        ctk.CTkLabel(controls_frame, text=tr("common.district_label")).grid(row=1, column=0, sticky='w', padx=15, pady=5)
        d_vals = self.app.history_manager.get_suggestions("location_district") or [""]
        self.district_var = ctk.StringVar()
        self.district_menu = ctk.CTkOptionMenu(controls_frame, variable=self.district_var, values=d_vals)
        self.district_menu.grid(row=1, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text=tr("common.block_label")).grid(row=2, column=0, sticky='w', padx=15, pady=5)
        b_vals = self.app.history_manager.get_suggestions("location_block") or [""]
        self.block_var = ctk.StringVar()
        self.block_menu = ctk.CTkOptionMenu(controls_frame, variable=self.block_var, values=b_vals)
        self.block_menu.grid(row=2, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text=tr("common.panchayat_label")).grid(row=3, column=0, sticky='w', padx=15, pady=5)
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

        ctk.CTkLabel(controls_frame, text=tr("form.dashboard.delay_column")).grid(row=4, column=0, sticky='w', padx=15, pady=5)
        self.delay_column_options = [
            "Attendance not filled in T+2 days",
            "Measurement Book not filled in T+5 days",
            "Wagelist not Sent in T+6 days",
            "Pending for I sig FTO in T+7 days",
            "Pending for II sig FTO in T+8 days"
        ]
        self.delay_column_var = ctk.StringVar(value=self.delay_column_options[0])
        self.delay_column_menu = ctk.CTkOptionMenu(controls_frame, variable=self.delay_column_var, values=self.delay_column_options)
        self.delay_column_menu.grid(row=4, column=1, sticky='ew', padx=15, pady=5)

        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        # --- Output Tabs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        workcode_tab = notebook.add("Workcode List")
        results_tab = notebook.add("Results Table")
        self._create_log_and_status_area(parent_notebook=notebook)

        # 1. Workcode List Tab
        workcode_tab.grid_columnconfigure(0, weight=1)
        workcode_tab.grid_rowconfigure(1, weight=1)
        
        copy_frame = ctk.CTkFrame(workcode_tab, fg_color="transparent")
        copy_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        self.copy_wc_button = ctk.CTkButton(copy_frame, text=tr("form.dashboard.copy_workcodes"), command=self._copy_workcodes)
        self.copy_wc_button.pack(side="left")

        self.run_mr_fill_button = ctk.CTkButton(copy_frame, text=tr("form.dashboard.run_mr_fill"), command=self._run_mr_fill,
                                                  fg_color=config.COLORS["green_dashboard"], hover_color=config.COLORS["green_dashboard_hover"])
        self.run_mr_fill_button.pack_forget()

        self.workcode_textbox = ctk.CTkTextbox(workcode_tab, state="disabled")
        self.workcode_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # 2. Results Tab
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        export_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.export_button = ctk.CTkButton(export_frame, text=tr("common.export_excel"), command=self.export_report)
        self.export_button.pack(side="left")

        # --- Treeview Config ---
        self.results_tree = ttk.Treeview(results_tab, columns=self.report_headers, show='headings')
        for col in self.report_headers: 
            self.results_tree.heading(col, text=col)
            
        self.results_tree.column("S No.", width=50, anchor='center')
        self.results_tree.column("Panchayat", width=130)
        self.results_tree.column("Project Name with code", width=450)
        self.results_tree.column("E-MR No.", width=120, anchor='center')
        self.results_tree.column("DateFrom-DateTo", width=180, anchor='center')

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.state_menu.configure(state=state)
        self.district_menu.configure(state=state)
        self.block_menu.configure(state=state)
        self.panchayat_menu.configure(state=state)
        self.delay_column_menu.configure(state=state)
        self.run_mr_fill_button.configure(state=state)
    def reset_ui(self) -> None:
        pass
    def start_automation(self) -> None:
        self.run_mr_fill_button.pack_forget()
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self._update_workcode_textbox("") 
        
        inputs = {
            'state': self.state_var.get().strip(), 
            'district': self.district_var.get().strip(), 
            'block': self.block_var.get().strip(),
            'panchayat': self.panchayat_var.get().strip(),
            'delay_column': self.delay_column_var.get()
        }
        
        if not all([inputs['state'], inputs['district'], inputs['block'], inputs['panchayat'], inputs['delay_column']]):
            messagebox.showwarning(tr("errors.input_error"), tr("errors.input_required")); return
        if inputs['panchayat'] == config.ALL_PANCHAYATS_LABEL:
            if not messagebox.askyesno(tr("dialogs.confirm"), tr("dialogs.process_all_panchayats")):
                return
        
        self.save_inputs(inputs)
        self.app.update_history("location_state", inputs['state'])
        self.app.update_history("location_district", inputs['district'])
        self.app.update_history("location_block", inputs['block'])
        if inputs['panchayat'] not in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL):
            self.app.update_history("location_panchayat", inputs['panchayat'])
        
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def _solve_captcha(self, driver, wait):
        """Solve CAPTCHA — tries hidden field answer first, falls back to math parsing."""
        self.log_info("Attempting to solve CAPTCHA...")
        textbox_id = "ContentPlaceHolder1_txtCaptcha"
        btn_id = "ContentPlaceHolder1_btnLogin"

        # Strategy 1: Read hidden answer field
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

        # Strategy 2: Parse math expression
        try:
            captcha_element = wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_lblStopSpam")))
            captcha_text = captcha_element.text
            match = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha_text)
            if not match: raise ValueError("Could not parse CAPTCHA.")
            num1, operator, num2 = match.groups(); num1, num2 = int(num1), int(num2)
            result = num1 + num2 if operator == '+' else (num1 - num2 if operator == '-' else num1 * num2)
            driver.find_element(By.ID, textbox_id).send_keys(str(result))
            driver.find_element(By.ID, btn_id).click()
            time.sleep(1.0)
            if "Invalid Captcha Code" in driver.page_source: raise ValueError("CAPTCHA failed.")
            return True
        except TimeoutException:
            self.log_info("CAPTCHA not found, skipping.")
            return True
        except ValueError as e:
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
                try:
                    district_select = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_District"))
                    )
                    if district_select.is_displayed() and district:
                        self.log_info(f"District dropdown found, selecting: {district}")
                        self._select_by_text_case_insensitive(Select(district_select), district)
                        time.sleep(2)
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

        # Pattern 2: Check for district/block links on page
        if district:
            try:
                district_link = driver.find_element(By.XPATH, f"//a[contains(normalize-space(), '{district.upper()}')]")
                if district_link.is_displayed():
                    self.log_info(f"Clicking district link: {district}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", district_link)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", district_link)
                    time.sleep(2)
                    if block:
                        try:
                            block_link = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, f"//a[contains(normalize-space(), '{block.upper()}')]"))
                            )
                            self.log_info(f"Clicking block link: {block}")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", block_link)
                            time.sleep(2)
                        except Exception:
                            pass
            except Exception:
                pass

    def run_automation_logic(self, inputs, retries=1):
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, self.app.set_status, "Starting Dashboard Report...") 
        self.app.after(0, self.update_status, "Initializing...", 0.0) 
        self.app.clear_log(self.log_display)

        try:
            driver = self.app.get_driver()
            if not driver: return 
            wait = WebDriverWait(driver, 20)

            # --- STANDARD FLOW ONLY (Accordion + Drilldown) ---
            self.log_info("Navigating to MIS portal...")
            driver.get(self.resolve_portal_url(config.MIS_REPORTS_CONFIG["base_url"]))
            self._solve_captcha(driver, wait)

            self.update_status("Selecting State...", 0.15)
            state_select = wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddl_States")))
            driver.execute_script("""
                arguments[0].scrollIntoView({block: 'center'});
                var select = arguments[0];
                var target = arguments[1].toLowerCase().trim();
                for (var i = 0; i < select.options.length; i++) {
                    if (select.options[i].text.toLowerCase().trim() === target) {
                        select.selectedIndex = i;
                        select.dispatchEvent(new Event('change', {bubbles: true}));
                        break;
                    }
                }
            """, state_select, inputs['state'])
            time.sleep(4)
            self.update_status("Waiting for report accordion...", 0.18)
            wait.until(EC.presence_of_element_located((By.ID, "accordionMain")))

            # Expand accordion and find the Dashboard link
            self.update_status("Opening Dashboard Report...", 0.2)
            driver.execute_script("""
                document.querySelectorAll('.accordion-collapse').forEach(function(el) {
                    el.classList.add('show');
                });
            """)
            time.sleep(0.5)

            report_link = driver.find_element(By.XPATH, "//a[contains(normalize-space(.), 'Dashboard for Delay Monitoring System')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", report_link)
            time.sleep(5)  # Wait for full dashboard page to load

            # Dashboard page loads with data via URL params — check if table already present
            self.update_status("Checking for panchayat table...", 0.25)
            main_table_xpath_gen = "//table[contains(., 'Panchayat') and contains(., 'S No')]"
            try:
                # Short wait (5s) to give the page time to render before giving up
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, main_table_xpath_gen)))
                self.log_info("Panchayat table already loaded, skipping drilldown.")
            except TimeoutException:
                self.log_info("Table not found directly, trying drilldown...")
                self._handle_report_drilldown(driver, wait, inputs)

            # --- Expand All on dashboard page: click radio buttons to trigger postback ---
            self.update_status("Expanding all data on dashboard...", 0.3)
            try:
                # Click 'All Districts' radio button (index 0) to ensure full data loads
                all_districts_rb = driver.find_element(By.ID, "ContentPlaceHolder1_rdbuttondistrict_0")
                if not all_districts_rb.is_selected():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", all_districts_rb)
                    self.log_info("Selected 'All Districts' radio button")
                    time.sleep(3)
            except Exception:
                pass
            try:
                # Click 'Consolidate for the Financial Year' radio button (index 0) for full data
                consolidate_rb = driver.find_element(By.ID, "ContentPlaceHolder1_RadioButtonList1_0")
                if not consolidate_rb.is_selected():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", consolidate_rb)
                    self.log_info("Selected 'Consolidate for the Financial Year' radio button")
                    time.sleep(3)
            except Exception:
                pass

            self.update_status("Finding Panchayats...", 0.35)
            # Find the panchayat summary table — 3 strategies:
            # 1. old portal: <b> inside <td>
            # 2. new portal Bootstrap: <th> elements
            # 3. Generic: any table containing 'Panchayat' and 'S No' (text-based)
            main_table_xpath = "//table[.//b[text()='SNo.'] and (.//b[text()='Panchayat'] or .//b[text()='Panchayats'])]"
            tables = driver.find_elements(By.XPATH, main_table_xpath)
            if not tables:
                main_table_xpath = "//table[.//th[contains(text(), 'SNo.')] and .//th[contains(text(), 'Panchayat')]]"
                tables = driver.find_elements(By.XPATH, main_table_xpath)
            if not tables:
                self.log_info("Trying generic text-based XPath...")
                main_table_xpath = "//table[contains(., 'Panchayat') and contains(., 'S No')]"
            wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))

            def _reopen_dashboard():
                """Re-navigate to the dashboard page and land on the panchayat summary table."""
                driver.get(self.resolve_portal_url(config.MIS_REPORTS_CONFIG["base_url"]))
                self._solve_captcha(driver, wait)
                state_select = wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddl_States")))
                driver.execute_script("""
                    arguments[0].scrollIntoView({block: 'center'});
                    var select = arguments[0];
                    var target = arguments[1].toLowerCase().trim();
                    for (var i = 0; i < select.options.length; i++) {
                        if (select.options[i].text.toLowerCase().trim() === target) {
                            select.selectedIndex = i;
                            select.dispatchEvent(new Event('change', {bubbles: true}));
                            break;
                        }
                    }
                """, state_select, inputs['state'])
                time.sleep(4)
                wait.until(EC.presence_of_element_located((By.ID, "accordionMain")))
                driver.execute_script("""
                    document.querySelectorAll('.accordion-collapse').forEach(function(el) {
                        el.classList.add('show');
                    });
                """)
                time.sleep(0.5)
                report_link = driver.find_element(By.XPATH, "//a[contains(normalize-space(.), 'Dashboard for Delay Monitoring System')]")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", report_link)
                time.sleep(5)
                try:
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, main_table_xpath_gen)))
                    self.log_info("Panchayat table already loaded, skipping drilldown.")
                except TimeoutException:
                    self.log_info("Table not found directly, trying drilldown...")
                    self._handle_report_drilldown(driver, wait, inputs)
                # Expand radios to load full data
                try:
                    all_districts_rb = driver.find_element(By.ID, "ContentPlaceHolder1_rdbuttondistrict_0")
                    if not all_districts_rb.is_selected():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", all_districts_rb)
                        self.log_info("Selected 'All Districts' radio button")
                        time.sleep(3)
                except Exception:
                    pass
                try:
                    consolidate_rb = driver.find_element(By.ID, "ContentPlaceHolder1_RadioButtonList1_0")
                    if not consolidate_rb.is_selected():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", consolidate_rb)
                        self.log_info("Selected 'Consolidate for the Financial Year' radio button")
                        time.sleep(3)
                except Exception:
                    pass
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

            self.update_status("Finding Column...", 0.4)
            target_col_index = -1
            # Try finding header cells — old portal: <b> inside <td>
            header_cells = driver.find_elements(By.XPATH, f"{main_table_xpath}//tr[.//b[contains(text(), 'T+2')]]/td/b")
            if not header_cells:
                # New portal: <th> elements
                header_cells = driver.find_elements(By.XPATH, f"{main_table_xpath}//tr[th[contains(text(), 'T+2')]]/th")
            for i, header_el in enumerate(header_cells):
                if ' '.join(inputs['delay_column'].split()).lower().strip() == ' '.join(header_el.text.split()).lower().strip():
                    target_col_index = i + 2
                    break

            if target_col_index == -1: raise ValueError(f"Column '{inputs['delay_column']}' not found.")

            workcode_list = []
            pending_mr_count = 0
            total_p = len(panchayat_names)
            need_back = False
            for p_idx, p_name in enumerate(panchayat_names):
                if self.is_stopped(): break
                self.log_info(f"===== Panchayat {p_idx+1}/{total_p}: {p_name} =====")
                self.update_status(f"Processing {p_name}...", 0.4 + (p_idx / max(total_p, 1)) * 0.1)

                # Navigate to the summary table: fast path = 1 step back (only if
                # the previous panchayat actually opened a report page);
                # fallback = full dashboard reload
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
                                self.log_info("Back navigation failed, re-opening dashboard...")
                                _reopen_dashboard()
                    else:
                        self.log_info("Reloading dashboard to find the panchayat...")
                        _reopen_dashboard()

                    # Re-locate the panchayat row (case-insensitive, with retry)
                    panchayat_row = None
                    for attempt in range(3):
                        rows = driver.find_elements(By.XPATH, f"{main_table_xpath}//tr[td]")
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 6:
                                p_name_in = cells[1].text.strip()
                                if p_name_in.lower() == p_name.lower():
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

                row_cells = panchayat_row.find_elements(By.TAG_NAME, "td")
                target_cell = row_cells[target_col_index]

                try:
                    target_link = target_cell.find_element(By.TAG_NAME, "a")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", target_link)
                    need_back = True
                except NoSuchElementException:
                    need_back = False
                    if target_cell.text.strip() == '0':
                        self.log_info(f"No records found (value=0) for {inputs['delay_column']} in {p_name}.")
                        continue
                    else:
                        self.log_warning(f"Target cell is not a clickable link for {p_name}. Skipping.")
                        continue

                self.update_status("Loading Final Report...", 0.55)
                # Dual-strategy: table with <th> containing 'E-MR' (new portal) OR old green-bordered table
                FINAL_TABLE_XPATH = (
                    "//table[.//th[contains(text(), 'E-MR')]]"
                    " | //table[@bordercolor='green' and .//b[contains(text(), 'E-MR No.')]]"
                )
                try:
                    table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, FINAL_TABLE_XPATH)))
                except TimeoutException:
                    # Report page didn't load — assume no navigation happened
                    need_back = False
                    self.log_warning(f"Final report table not found for {p_name}. Skipping.")
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

                if not all_rows_data:
                    self.log_warning(f"Table is empty for {p_name}.")
                    continue

                insert_buffer = []
                for i, row_data in enumerate(all_rows_data):
                    if self.is_stopped(): break

                    # Original Table Indices: 0:SNo, 1:Dist, 2:Blk, 3:GP, 4:Agency, 5:Project, 6:EMR, 7:Date
                    if not row_data or len(row_data) < 8: continue

                    project_name = row_data[5]
                    emr_no = row_data[6]
                    dates = row_data[7]

                    wc_match = re.search(r'\(([^)]+)\)$', project_name)
                    if wc_match: workcode_list.append(wc_match.group(1).strip())

                    # Continuous S.No. across all panchayats + explicit Panchayat column
                    pending_mr_count += 1
                    insert_buffer.append((pending_mr_count, p_name, project_name, emr_no, dates))

                    # Batched tree inserts (keeps the UI snappy)
                    if len(insert_buffer) >= 50:
                        batch = list(insert_buffer)
                        insert_buffer.clear()
                        self.app.after(0, lambda b=batch: self._insert_rows_batch(b))

                    # Throttled progress — keyed on the row index
                    if i % 50 == 0 or i == len(all_rows_data) - 1:
                        self.app.after(0, self.update_status, f"Processing {p_name} row {i+1}/{len(all_rows_data)}", 0.55 + ((i+1)/len(all_rows_data))*0.3)

                if insert_buffer:
                    batch = list(insert_buffer)
                    insert_buffer.clear()
                    self.app.after(0, lambda b=batch: self._insert_rows_batch(b))

            if self.is_stopped(): return
            self.app.after(0, self._update_workcode_textbox, "\n".join(workcode_list))
            self.success_message = f"Done.\n{pending_mr_count} Pending items found."


        except Exception as e:
            if "Session Expired" in str(e) and retries > 0:
                self.run_automation_logic(inputs, retries - 1)
                return
            self.log_error(f"Error: {e}")
            self.success_message = None
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")
            self.app.after(0, self.update_status, "Ready", 0.0)
            if hasattr(self, 'success_message') and self.success_message:
                self.log_info(f"📊 Dashboard Report Complete: {self.success_message}")
                if inputs['delay_column'] == "Attendance not filled in T+2 days":
                    self.app.after(0, lambda: self.run_mr_fill_button.pack(side="left", padx=(10, 0)))

    def _update_workcode_textbox(self, text):
        self.workcode_textbox.configure(state="normal")
        self.workcode_textbox.delete("1.0", tkinter.END)
        self.workcode_textbox.insert("1.0", text)
        self.workcode_textbox.configure(state="disabled")

    def _copy_workcodes(self):
        text = self.workcode_textbox.get("1.0", tkinter.END).strip()
        if text:
            self.app.clipboard_clear(); self.app.clipboard_append(text)
            messagebox.showinfo(tr("status.copied"), tr("dialogs.copied_to_clipboard"))
        else: messagebox.showwarning(tr("dialogs.empty"), tr("dialogs.no_workcodes_short"))

    def _run_mr_fill(self):
        wc = self.workcode_textbox.get("1.0", tkinter.END).strip()
        gp = self.panchayat_var.get().strip()
        if wc and gp: self.app.switch_to_mr_fill_with_data(wc, gp)
        else: messagebox.showwarning(tr("dialogs.error"), tr("dialogs.missing_data"))

    # =========================================================================
    # ==================== FINAL EXPORT LOGIC (FIXED) =========================
    # =========================================================================

    def export_report(self):
        """Export results to professional Excel."""
        if not self.results_tree.get_children():
            messagebox.showinfo(tr("errors.no_data"), tr("dialogs.no_results_export_short"))
            return

        delay_type = self.delay_column_var.get()
        if "Attendance" in delay_type: report_type = "Attendance Pending Report"
        elif "Measurement" in delay_type: report_type = "Measurement Book Pending Report"
        elif "Wagelist" in delay_type: report_type = "Wagelist Pending Report"
        elif "FTO" in delay_type: report_type = "FTO Pending Report"
        else: report_type = "Delay Compensation Report"

        main_title = f"{report_type.upper()}"
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', self.panchayat_var.get().strip() or "Report")

        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"{report_type.replace(' ','_')}_{safe_panchayat}_{current_date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=main_title
        )

    def generate_report_pdf(self, data, headers, col_widths, title, subtitle, file_path):
        class ProPDF(FPDF):
            def footer(self):
                self.set_y(-15); self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()} - Generated by NregaBot.com', 0, 0, 'C')

        try:
            pdf = ProPDF(orientation="L", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=15); pdf.add_page()
            
            # Font handling
            try:
                font_reg = resource_path("assets/fonts/NotoSansDevanagari-Regular.ttf")
                font_bold = resource_path("assets/fonts/NotoSansDevanagari-Bold.ttf")
                pdf.add_font("Custom", "", font_reg, uni=True)
                pdf.add_font("Custom", "B", font_bold, uni=True)
                f_name = "Custom"
            except: f_name = "Arial"

            # Title Block
            pdf.set_font(f_name, "B", 16)
            pdf.cell(0, 10, title, 0, 1, "C")
            
            # Subtitle (Location)
            pdf.set_font(f_name, "B", 10)
            pdf.set_fill_color(220, 230, 241) # Light Blue Bar
            pdf.cell(0, 8, subtitle, 0, 1, "C", fill=True)
            
            # Date
            pdf.set_font(f_name, "", 8) # Regular font (Not Italic to avoid crash)
            pdf.cell(0, 6, f"Date: {datetime.now().strftime('%d-%b-%Y')}", 0, 1, "R")
            pdf.ln(2)

            # Table Headers
            pdf.set_font(f_name, "B", 9)
            pdf.set_fill_color(31, 73, 125) # Dark Blue
            pdf.set_text_color(255, 255, 255) # White Text
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 10, h, 1, 0, "C", fill=True)
            pdf.ln()

            # Table Data (Improved Row Height Calculation)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font(f_name, "", 8)
            fill = False
            
            for row in data:
                pdf.set_fill_color(242, 242, 242) if fill else pdf.set_fill_color(255, 255, 255)
                
                # 1. Calculate Maximum Row Height First
                max_row_height = 0
                cell_lines = [] # Store line counts to avoid re-calculating
                for i, txt in enumerate(row):
                    # Get number of lines this cell will take
                    # FPDF multi_cell simply prints, so we use string width to estimate
                    # OR we use a temporary multi_cell approach
                    
                    # Robust method: split_only=True returns the lines
                    lines = pdf.multi_cell(col_widths[i], 5, str(txt), border=0, split_only=True)
                    num_lines = len(lines)
                    max_row_height = max(max_row_height, num_lines * 5)
                    cell_lines.append(num_lines)

                # Ensure minimum height
                max_row_height = max(max_row_height, 6)

                # 2. Check Page Break
                if pdf.get_y() + max_row_height > 190:
                    pdf.add_page()
                    # Re-print headers
                    pdf.set_font(f_name, "B", 9)
                    pdf.set_fill_color(31, 73, 125); pdf.set_text_color(255, 255, 255)
                    for i, h in enumerate(headers): pdf.cell(col_widths[i], 10, h, 1, 0, "C", fill=True)
                    pdf.ln(); pdf.set_text_color(0, 0, 0); pdf.set_font(f_name, "", 8)

                # 3. Print Cells
                current_x = pdf.get_x()
                current_y = pdf.get_y()
                
                for i, txt in enumerate(row):
                    # Save x position
                    pdf.set_xy(current_x, current_y)
                    
                    # Print MultiCell
                    # align='L' for Project Name (index 1), 'C' for others
                    align = 'L' if i == 1 else 'C'
                    pdf.multi_cell(col_widths[i], 5, str(txt), border=1, align=align, fill=True)
                    
                    # Move X pointer to next column
                    current_x += col_widths[i]
                
                # 4. Move Y pointer to next row start
                pdf.set_xy(10, current_y + max_row_height) # 10 is left margin
                
                fill = not fill

            pdf.output(file_path)
            return True
        except Exception as e:
            messagebox.showerror(tr("dialogs.pdf_error"), str(e)); return False

    def save_inputs(self, inputs):
        d = {k: inputs.get(k) for k in ('state', 'district', 'block', 'panchayat')}
        try:
            self.app.history_manager.save_tab_inputs_batch("dashboard_report", d)
        except Exception as e: logger.debug("Dashboard: Could not save inputs: %s", e)

    def load_inputs(self):
        data = self.app.history_manager.get_tab_inputs("dashboard_report")
        if data:
            self.state_var.set(data.get('state', ''))
            self.district_var.set(data.get('district', ''))
            self.block_var.set(data.get('block', ''))
            self.panchayat_var.set(data.get('panchayat') or config.ALL_PANCHAYATS_LABEL)