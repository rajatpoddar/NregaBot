# tabs/mis_reports_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, os, json
from datetime import datetime
import re
from io import StringIO


# --- MODIFIED IMPORTS ---

from .base_tab import BaseAutomationTab
from src import config
from src.utils import get_logger
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, Alignment, Border, Font, PatternFill, Side, get_column_letter, import_pandas  # noqa: F401


logger = get_logger()

# Thread-safe lazy pandas load — see import_pandas() docstring in _imports.py.
pd = import_pandas()

class MisReportsTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="mis_reports")
        self.config_file = self.app.get_data_path("mis_reports_inputs.json")
        self.report_checkboxes = {}
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:

        # Main tab view to organize Settings, Results, and Logs
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        settings_tab = notebook.add("Settings")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(notebook) # Creates "Logs & Status" tab

        # Configure the layout for the tabs
        settings_tab.grid_rowconfigure(2, weight=1)
        settings_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        results_tab.grid_columnconfigure(0, weight=1)

        # ── Header / intro card (pending-bills style) ──
        self._create_header_card(settings_tab, "📊", "MIS Reports",
                                 "Download multiple NREGA MIS reports into a single formatted Excel file.",
                                 icon_key="emoji_mis_reports")

        # 1. Populate the "Settings" Tab
        settings_container = ctk.CTkFrame(settings_tab, fg_color="transparent")
        settings_container.grid(row=1, column=0, sticky="nsew", padx=5)
        settings_container.grid_columnconfigure(1, weight=1)
        
        # --- Create all entries first (no cross-references) ---
        ctk.CTkLabel(settings_container, text="State:").grid(row=0, column=0, sticky='w', padx=15, pady=5)
        s_vals = self.app.history_manager.get_suggestions("location_state") or [""]
        self.state_var = ctk.StringVar()
        self.state_menu = ctk.CTkOptionMenu(settings_container, variable=self.state_var, values=s_vals)
        self.state_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(settings_container, text="District:").grid(row=1, column=0, sticky='w', padx=15, pady=5)
        d_vals = self.app.history_manager.get_suggestions("location_district") or [""]
        self.district_var = ctk.StringVar()
        self.district_menu = ctk.CTkOptionMenu(settings_container, variable=self.district_var, values=d_vals)
        self.district_menu.grid(row=1, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(settings_container, text="Block:").grid(row=2, column=0, sticky='w', padx=15, pady=5)
        b_vals = self.app.history_manager.get_suggestions("location_block") or [""]
        self.block_var = ctk.StringVar()
        self.block_menu = ctk.CTkOptionMenu(settings_container, variable=self.block_var, values=b_vals)
        self.block_menu.grid(row=2, column=1, sticky='ew', padx=15, pady=5)

        # --- Wire up location hierarchy callbacks now (all widgets exist) ---
        def _on_state_change(*_):
            self.district_var.set(""); self.block_var.set("")
            vals = self.app.history_manager.get_filtered_suggestions("location_district", "location_state", self.state_var.get()) or [""]
            self.district_menu.configure(values=vals)
        self.state_var.trace_add("write", _on_state_change)
        
        def _on_district_change(*_):
            self.block_var.set("")
            vals = self.app.history_manager.get_filtered_suggestions("location_block", "location_district", self.district_var.get()) or [""]
            self.block_menu.configure(values=vals)
        self.district_var.trace_add("write", _on_district_change)

        # Checkbox list for reports
        self.reports_frame = ctk.CTkFrame(settings_tab, corner_radius=12, border_width=1,
                                          border_color=("gray85", "gray30"))
        self.reports_frame.grid(row=2, column=0, sticky='nsew', padx=5, pady=10)
        self.reports_frame.grid_columnconfigure(0, weight=1)
        self.reports_frame.grid_rowconfigure(1, weight=1)
        
        self.reports_header = ctk.CTkFrame(self.reports_frame, fg_color="transparent")
        self.reports_header.grid(row=0, column=0, sticky='ew', padx=10, pady=(5,0))
        
        ctk.CTkLabel(self.reports_header, text="Reports to Download:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        btn_frame = ctk.CTkFrame(self.reports_header, fg_color="transparent")
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="Select All", width=100, command=self._toggle_all_checkboxes).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Deselect All", width=100, command=lambda: self._toggle_all_checkboxes(select=False)).pack(side="left")
        
        scrollable_frame = ctk.CTkScrollableFrame(self.reports_frame, label_text="")
        scrollable_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)

        # ── Original 9 reports from old portal (with new-portal name mappings) ──
        self.report_list = [
            "Dashboard for Delay Monitoring System",
            "VBGRAMG daily status as per e-muster issued",
            "Employment Pattern During the year",
            "SC ST Employment Status",
            "Total No. of Aadhaar Nos. Entered for VBGRAMG",
            "Employment Provided Period wise",
            "Yearly Work Completion Rate",
            "Rejected Wage/Material/admin Transaction Reconciliation",
            "Verification of Job cards",
        ]
        
        self.report_checkboxes = {}
        for report_name in self.report_list:
            var = tkinter.IntVar(value=1)
            cb = ctk.CTkCheckBox(scrollable_frame, text=report_name, variable=var)
            cb.pack(anchor="w", padx=10, pady=5)
            self.report_checkboxes[report_name] = var

        action_frame = self._create_action_buttons(parent_frame=settings_tab)
        action_frame.grid(row=3, column=0, pady=10)

        # 2. Populate the "Results" Tab
        res_btn_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        res_btn_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 0))
        self.export_button = ctk.CTkButton(res_btn_frame, text="📥 Export to Excel", fg_color="#107C10", hover_color="#0B5E0B", command=self.export_report)
        self.export_button.pack(side="right")

        cols = ("Report Name", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Report Name", width=300); self.results_tree.column("Status", width=100); self.results_tree.column("Details", width=300)
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def _toggle_all_checkboxes(self, select=True):
        for var in self.report_checkboxes.values():
            var.set(1 if select else 0)
    
    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        # This function correctly disables UI elements during automation
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        
        # Disable the individual text entry fields
        self.state_menu.configure(state=state)
        self.district_menu.configure(state=state)
        self.block_menu.configure(state=state)

        # Disable export button during automation
        if hasattr(self, 'export_button'):
            try:
                self.export_button.configure(state=state)
            except Exception:
                pass

        # Disable all widgets within the reports_frame (checkboxes, buttons)
        # This is the corrected logic that avoids the winfo_descendants error.
        if hasattr(self, 'reports_frame'):
            # Loop through all direct children of the frame
            for widget in self.reports_frame.winfo_children():
                try:
                    # Attempt to configure the state of each child widget
                    widget.configure(state=state)
                except Exception:
                    # Failsafe for widgets that don't have a 'state' property (like sub-frames)
                    pass
    def start_automation(self) -> None:
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        
        selected_reports = [name for name, var in self.report_checkboxes.items() if var.get() == 1]
        
        inputs = {'state': self.state_var.get().strip(), 'district': self.district_var.get().strip(), 'block': self.block_var.get().strip(), 'reports': selected_reports}
        
        if not all([inputs['state'], inputs['reports']]):
            messagebox.showwarning("Input Error", "State and at least one Report are required."); return
        
        self.save_inputs({'state': inputs['state'], 'district': inputs['district'], 'block': inputs['block']})
        self.app.update_history("location_state", inputs['state']); self.app.update_history("location_district", inputs['district']); self.app.update_history("location_block", inputs['block'])
        
        # --- NEW: Create suggested directory structure (standardized) ---
        try:
            target_dir = self.app.get_report_path("MIS")
            today_str_file = datetime.now().strftime("%d-%m-%Y_%H%M%S")
            initial_filename = f"MIS_Reports_{today_str_file}.xlsx"
        except Exception as e:
            messagebox.showerror("Folder Error", f"Could not create default save directory.\n{e}")
            target_dir = self.app.get_user_downloads_path() # Fallback
            initial_filename = "MIS_Reports.xlsx"
        # --- END NEW ---

        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            filetypes=[("Excel Workbook", "*.xlsx")], 
            title="Save MIS Reports As", 
            initialdir=target_dir, # <-- Use new target dir
            initialfile=initial_filename # <-- Use new initial filename
        )
        if not save_path: return
        
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs, save_path))

    def _solve_captcha(self, driver, wait):
        """Solve CAPTCHA — tries hidden field answer first, falls back to math parsing."""
        self.log_info("Attempting to solve CAPTCHA...")
        textbox_id = "ContentPlaceHolder1_txtCaptcha"
        btn_id = "ContentPlaceHolder1_btnLogin"
        
        # Strategy 1: Read the hidden answer field directly (new portal has hfCaptcha)
        try:
            hf = driver.find_element(By.ID, "ContentPlaceHolder1_hfCaptcha")
            answer = hf.get_attribute("value")
            if answer and answer.strip().isdigit():
                self.log_info(f"CAPTCHA solved via hidden field: {answer.strip()}")
                driver.find_element(By.ID, textbox_id).send_keys(answer.strip())
                driver.find_element(By.ID, btn_id).click()
                time.sleep(2)
                return True
        except Exception:
            pass
        
        # Strategy 2: Parse the math expression from label
        captcha_label_id = "ContentPlaceHolder1_lblStopSpam"
        captcha_text = wait.until(EC.presence_of_element_located((By.ID, captcha_label_id))).text
        match = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha_text)
        if not match:
            raise ValueError(f"Could not parse CAPTCHA expression from: {captcha_text}")
        num1, operator, num2 = match.groups(); num1, num2 = int(num1), int(num2)
        result = { '+': num1 + num2, '-': num1 - num2, '*': num1 * num2 }[operator]
        self.log_info(f"CAPTCHA solved: {captcha_text.strip()} = {result}")
        driver.find_element(By.ID, textbox_id).send_keys(str(result))
        driver.find_element(By.ID, btn_id).click()
        time.sleep(2)
        return True

    def _handle_report_drilldown(self, driver, wait, inputs):
        """
        After opening a report page, check for state/district/block dropdowns
        and interact with them to drill down to the correct location.

        Handles two patterns:
        1. Dropdown-based (state→district→block select elements)
        2. Link-based (click district name → click block name)
        """
        state = inputs.get('state', '')
        district = inputs.get('district', '')
        block = inputs.get('block', '')

        # Pattern 1: Check for state dropdown on the report page
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

        # Pattern 2: Check for district/block links on page
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

    def _fix_header_row(self, df):
        """
        Check if the first data row is actually a sub-header row.
        If so, use it as column names and drop the row.

        Government tables have multi-level HTML headers where:
        - Row 0 (after header=0) has generic labels like 'No of MRs'
        - Row 1 has the actual sub-headers like 'Attendance not filled in T+2'
        """
        if len(df) < 2:
            return df

        first_row = [str(df.iloc[0, c]).replace('\xa0', ' ').strip().lower() if pd.notna(df.iloc[0, c]) else '' for c in range(df.shape[1])]
        
        # Check first 3 columns for sub-header patterns
        sub_header_keywords = ['s no', 'panchayat', 'district', 'block', 'attendance',
                               'measurement', 'wagelist', 'pending', 'total', 'household',
                               'persondays', 'financial year', 'no of works', 'completed',
                               'rate', 'issued', 'verified', 'seeded', 'authentication',
                               'npcimapper', 'rejected', 'regeneration', 'districts',
                               'all', 'active', 'count', '%']
        match_count = sum(1 for val in first_row[:3] if any(kw in val for kw in sub_header_keywords))
        
        # Check if column names look generic (has .1/.2 suffixes, or is short/label-like)
        col_names = [str(c).strip().lower() for c in df.columns]
        generic_count = sum(1 for c in col_names[:3] if (
            c in ['s no.', 's no', 'panchayat', 'no of mrs', '-', ''] or 
            '.1' in c or '.2' in c or '.3' in c or '.4' in c
        ))
        
        # Also check if column names are very short (1-3 chars) indicating placeholder
        short_count = sum(1 for c in col_names[:5] if len(c) <= 3 and c not in ['s no', 'sno', '#'])

        if (match_count >= 2 and generic_count >= 1) or match_count >= 3 or short_count >= 3:
            self.log_info("First data row detected as sub-header — promoting to column names.")
            new_cols = []
            for c in range(df.shape[1]):
                val = str(df.iloc[0, c]).replace('\xa0', ' ').strip() if pd.notna(df.iloc[0, c]) else ''
                if not val or val == 'nan':
                    val = str(df.columns[c])
                new_cols.append(val)
            # Deduplicate identical column names (pandas will add .1, .2)
            seen = {}
            deduped = []
            for c in new_cols:
                if c in seen:
                    seen[c] += 1
                    deduped.append(f"{c}_{seen[c]}")
                else:
                    seen[c] = 0
                    deduped.append(c)
            df.columns = deduped
            df = df.iloc[1:].reset_index(drop=True)

        return df

    def _compact_dataframe(self, df):
        """REMOVED — transpose caused data corruption. Data kept in original orientation."""
        return df

    def _pick_best_dataframe(self, df_list):
        """From parsed DataFrames, pick the one most likely to be the actual data table.

        Criteria:
        - Skip tables with ≤2 rows (navigation, headers, footers)
        - Pick the table with the most columns (data tables are wide)
        - If tied, pick the one with the most rows
        """
        if not df_list:
            return pd.DataFrame()

        # Filter out single-cell or tiny tables (headings, nav, footers)
        candidates = [df for df in df_list if len(df) >= 3 and df.shape[1] >= 2]

        if candidates:
            # Pick by most columns first (data tables are wide), then by most rows
            return max(candidates, key=lambda df: (df.shape[1], len(df)))

        # If all tables are small, return the largest anyway
        return max(df_list, key=lambda df: (len(df), df.shape[1]))

    def _parse_report_tables(self, page_source):
        """Parse HTML tables from page and return the best DataFrame.

        Tries multiple header strategies and selects the table with the most actual data.
        """
        # Strategy 1: header=0 (most common for government tables)
        try:
            df_list = pd.read_html(StringIO(page_source), header=0)
            if df_list:
                best = self._pick_best_dataframe(df_list)
                if len(best) > 2:
                    best = self._fix_header_row(best)
                    if len(best) > 2:
                        return best
        except Exception:
            pass

        # Strategy 2: header=[0,1] (multi-level headers, e.g. merged cells)
        try:
            df_list = pd.read_html(StringIO(page_source), header=[0, 1])
            if df_list:
                # Pick the best table from the list
                df = self._pick_best_dataframe(df_list)
                if not df.empty and df.shape[1] >= 2:
                    # Flatten multi-level columns properly
                    new_cols = []
                    for col in df.columns:
                        col_str = str(col[1]).strip() if len(col) > 1 else str(col[0]).strip()
                        col_parent = str(col[0]).strip() if len(col) > 1 else ''
                        # If sub-header is empty or 'Unnamed', use parent header
                        if not col_str or 'Unnamed' in col_str:
                            col_str = col_parent
                        # If both are same or parent is empty, just use sub-header
                        elif col_parent and col_str and col_parent != col_str:
                            col_str = f"{col_parent} ({col_str})" if len(col_parent) < 30 else col_str
                        new_cols.append(col_str)
                    df.columns = new_cols
                    
                    # Remove junk numeric header row (some govt tables have '1' '2026-27' as first data row)
                    if len(df) > 1 and str(df.iloc[0, 0]).strip().isdigit():
                        # Check if second row has proper header names
                        first_val = str(df.iloc[0, 1]).strip() if df.shape[1] > 1 else ''
                        if first_val and not first_val.isdigit():
                            # First row looks like a header, not data
                            new_cols = [str(df.iloc[0, c]).strip() if pd.notna(df.iloc[0, c]) else new_cols[c] for c in range(df.shape[1])]
                            df.columns = new_cols
                            df = df.iloc[1:].reset_index(drop=True)
                    
                    if len(df) > 2:
                        return df
        except Exception:
            pass

        # Strategy 3: No header (fallback for weirdly structured tables)
        try:
            df_list = pd.read_html(StringIO(page_source))
            if df_list:
                best = self._pick_best_dataframe(df_list)
                if len(best) > 2:
                    self.log_info(f"Parsed {len(best)} rows with auto-header.")
                    return best
                elif len(best) >= 1:
                    # Return small result anyway (might be genuine 1-row data)
                    self.log_info(f"Parsed {len(best)} rows with auto-header (small table).")
                    return best
        except Exception:
            pass

        return pd.DataFrame()

    def run_automation_logic(self, inputs, save_path):
        self.app.after(0, self.set_ui_state, True); self.app.clear_log(self.log_display); self.log_info("Starting MIS Report generation...")
        try:
            driver = self.app.get_driver()
            if not driver: return
            wait = WebDriverWait(driver, 20)
            
            total_reports = len(inputs['reports'])
            sheets_written = 0
            
            # ═══════════════════════════════════════════════
            # PHASE 1: Solve CAPTCHA + Select State (ONCE)
            # ═══════════════════════════════════════════════
            self.log_info("Navigating to MIS portal...")
            driver.get(config.MIS_REPORTS_CONFIG["base_url"])
            self._solve_captcha(driver, wait)
            
            self.log_info(f"Selecting state: {inputs['state']}")
            state_dropdown = wait.until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_States")))
            self._select_by_text_case_insensitive(Select(state_dropdown), inputs['state'])
            time.sleep(4)  # Wait for postback to load accordion
            
            # Wait for accordion to appear on the reloaded page
            self.log_info("Waiting for report accordion to load...")
            wait.until(EC.presence_of_element_located((By.ID, "accordionMain")))
            self.log_info("✅ Accordion loaded successfully.")
            
            writer = pd.ExcelWriter(save_path, engine='openpyxl')
            try:
                # ═══════════════════════════════════════════════
                # PHASE 2: Process each report
                # ═══════════════════════════════════════════════
                for i, report_name in enumerate(inputs['reports']):
                    if self.is_stopped():
                        self.log_warning("Stop signal received.")
                        break
                    
                    status_msg = f"Processing report {i+1}/{total_reports}..."
                    self.app.after(0, self.app.set_status, status_msg)
                    self.app.after(0, self.update_status, f"Processing {report_name}", (i+1)/total_reports)
                    self.log_info(f"--- Processing report {i+1}/{total_reports}: {report_name} ---")
                    
                    report_df = pd.DataFrame()
                    
                    try:
                        # Expand all accordion sections so all links are visible
                        driver.execute_script("""
                            document.querySelectorAll('.accordion-collapse').forEach(function(el) {
                                el.classList.add('show');
                            });
                        """)
                        time.sleep(0.5)
                        
                        # Find report link by text (using normalize-space to handle <u> inside <a>)
                        self.log_info(f"Searching for: {report_name}")
                        link = driver.find_element(
                            By.XPATH,
                            f"//a[contains(normalize-space(.), '{report_name.strip()}')]"
                        )
                        href = link.get_attribute("href")
                        self.log_info(f"Opening: {href[:100]}...")
                        
                        # ── Open report in NEW TAB (preserves accordion page) ──
                        main_tab = driver.current_window_handle
                        # Use Selenium 4 switch_to.new_window() — not blocked by popup blockers
                        driver.switch_to.new_window('tab')
                        driver.get(href)
                        time.sleep(3)
                        
                        # ── Check for drill-down (state→district→block) on report page ──
                        self._handle_report_drilldown(driver, wait, inputs)
                        time.sleep(2)
                        
                        # ── Read table data ──
                        self.log_info("Reading table data...")
                        
                        # First, check if there are actual HTML tables on the page
                        page_tables = driver.find_elements(By.TAG_NAME, "table")
                        if not page_tables:
                            self.log_warning(f"No HTML tables found on this page. Data may be rendered via JavaScript.")
                            self.app.after(0, lambda r=report_name: self._tree_insert(self.results_tree, (r, "Failed", "No HTML tables on page"), ('failed',)))
                            driver.close()
                            driver.switch_to.window(main_tab)
                            time.sleep(1)
                            continue
                        
                        self.log_info(f"Found {len(page_tables)} HTML table(s), parsing...")
                        
                        # ── Parse HTML tables ──
                        report_df = self._parse_report_tables(driver.page_source)
                        
                        if report_df.empty:
                            self.log_warning(f"No data found for '{report_name}'.")
                            self.app.after(0, lambda r=report_name: self._tree_insert(self.results_tree, (r, "Failed", "No data found"), ('failed',)))
                            try:
                                driver.close()
                            except: pass
                            driver.switch_to.window(main_tab)
                            time.sleep(1)
                            continue
                        
                        # ── Compact: transpose if wide, then write to Excel ──
                        report_df = self._compact_dataframe(report_df)
                        
                        sheet_name = re.sub(r'[\\/*?:\[\]]', '', report_name)[:30]
                        report_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1)
                        sheets_written += 1
                        worksheet = writer.sheets[sheet_name]
                        
                        # ── Ultra-Compact Excel Formatting ──
                        # 1. Title row (compact)
                        worksheet['A1'] = report_name
                        worksheet['A1'].font = Font(bold=True, size=10, color="1F4E79")
                        if not report_df.empty:
                            worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=worksheet.max_column)
                            worksheet['A1'].alignment = Alignment(horizontal='center', vertical='center')
                        
                        # 2. Header row (row 2) — compact with wrap
                        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
                        header_font = Font(bold=True, color="FFFFFF", size=8)
                        thin_border = Border(
                            left=Side(style='thin', color='D0D0D0'),
                            right=Side(style='thin', color='D0D0D0'),
                            top=Side(style='thin', color='D0D0D0'),
                            bottom=Side(style='thin', color='D0D0D0')
                        )
                        center_wrap = Alignment(horizontal='center', vertical='center', wrap_text=True)
                        left_wrap = Alignment(horizontal='left', vertical='center', wrap_text=True)
                        
                        for col_idx in range(1, worksheet.max_column + 1):
                            cell = worksheet.cell(row=2, column=col_idx)
                            cell.fill = header_fill
                            cell.font = header_font
                            cell.alignment = center_wrap
                            cell.border = thin_border
                        
                        # 3. Data rows — compact alternating colors
                        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
                        gray_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
                        data_font = Font(size=8)
                        for row_idx in range(3, worksheet.max_row + 1):
                            row_fill = gray_fill if (row_idx - 3) % 2 == 1 else white_fill
                            for col_idx in range(1, worksheet.max_column + 1):
                                cell = worksheet.cell(row=row_idx, column=col_idx)
                                cell.fill = row_fill
                                cell.border = thin_border
                                cell.alignment = left_wrap if col_idx == 1 else center_wrap
                                cell.font = data_font
                        
                        # 4. Ultra-compact column widths
                        for col_idx in range(1, worksheet.max_column + 1):
                            col_letter = get_column_letter(col_idx)
                            max_len = 0
                            is_number_col = True
                            is_panchayat = col_idx == 1
                            for cell in worksheet[col_letter]:
                                if cell.row == 1: continue
                                val = str(cell.value) if cell.value is not None else ''
                                if len(val) > max_len:
                                    max_len = len(val)
                                if val and not val.replace('.','').replace('-','').replace('%','').strip().isdigit():
                                    is_number_col = False
                            if is_panchayat:
                                worksheet.column_dimensions[col_letter].width = min(max_len + 2, 16)
                            elif is_number_col:
                                worksheet.column_dimensions[col_letter].width = min(max(max_len + 2, 6), 9)
                            else:
                                worksheet.column_dimensions[col_letter].width = min(max_len + 2, 12)
                        
                        # 5. Auto-filter
                        if worksheet.max_row > 2:
                            last_col_letter = get_column_letter(worksheet.max_column)
                            worksheet.auto_filter.ref = f"A2:{last_col_letter}{worksheet.max_row}"
                        
                        # 6. Freeze panes — keep Panchayat column + header visible
                        worksheet.freeze_panes = "B3"
                        worksheet.sheet_properties.tabColor = "1F4E79"
                        
                        # 7. Print settings — Landscape, fit to page
                        try:
                            worksheet.page_setup.orientation = 'landscape'
                            worksheet.page_setup.fitToWidth = 1
                            worksheet.page_setup.fitToHeight = 0
                            worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
                        except:
                            pass
                        
                        self.log_success(f"'{report_name}' saved ({len(report_df)} rows).")
                        self.app.after(0, lambda r=report_name: self._tree_insert(self.results_tree, (r, "Success", f"{len(report_df)} rows")))
                        
                        # ── Close new tab and switch back to accordion ──
                        try:
                            driver.close()
                        except: pass
                        driver.switch_to.window(main_tab)
                        time.sleep(1)
                        
                    except NoSuchElementException:
                        self.log_warning(f"Report '{report_name}' not found in accordion.")
                        self.app.after(0, lambda r=report_name: self._tree_insert(self.results_tree, (r, "Failed", "Link not found"), ('failed',)))
                    except Exception as e:
                        error_msg = str(e).split('\n')[0]
                        self.log_error(f"Failed to process '{report_name}': {error_msg}")
                        self.app.after(0, lambda r=report_name, d=error_msg: self._tree_insert(self.results_tree, (r, "Failed", d), ('failed',)))
                        # Try to close the new tab and go back to accordion
                        try:
                            driver.close()
                        except: pass
                        try:
                            driver.switch_to.window(main_tab)
                        except: pass
            
            finally:
                if sheets_written > 0:
                    writer.close()
                    self.log_success(f"Process complete. Excel file saved at: {save_path}")
                else:
                    self.log_warning("No reports were successfully processed. Excel file not saved.")
                    if os.path.exists(save_path):
                        try: os.remove(save_path)
                        except: pass
        except Exception as e:
            error_msg = str(e).split('\n')[0]; self.log_error(f"Critical error: {error_msg}"); messagebox.showerror("Critical Error", error_msg)
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished", 1.0)
            self.app.after(0, self.app.set_status, "Automation Finished")
            
            if not self.is_stopped():
                self.log_info(f"📊 MIS Report generated. File(s) saved near: {save_path}")
            
            self.app.after(5000, lambda: self.app.set_status("Ready"))
            self.app.after(5000, lambda: self.update_status("Ready", 0.0))

    def save_inputs(self, inputs):
        try:
            self.app.history_manager.save_tab_inputs_batch("mis_reports", inputs)
        except Exception as e:
            print(f"Error saving MIS inputs: {e}")

    def load_inputs(self):
        data = self.app.history_manager.get_tab_inputs("mis_reports")
        if data:
            self.state_var.set(data.get('state', ''))
            self.district_var.set(data.get('district', ''))
            self.block_var.set(data.get('block', ''))
    def export_report(self):
        """Export results log to professional Excel using the base class method."""
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="mis_reports_results.xlsx",
            filter_mode="Export All",
            title_prefix="MIS Reports — Results Log"
        )

    def reset_ui(self) -> None:
        """Resets inputs and checkboxes."""
        super().reset_ui() # Call base to clear logs/status
        
        # Clear Text Inputs
        self.state_var.set("")
        self.district_var.set("")
        self.block_var.set("")
        
        # Reset Checkboxes to Checked
        self._toggle_all_checkboxes(select=True)
        
        # Clear Treeview
        self.safe_tree_clear()