# tabs/work_allocation_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import csv
import os
import re
import time
from datetime import datetime

from src import config
from src.utils import truncate_workcode
from src.i18n import tr
from .base_tab import BaseAutomationTab

from typing import Any, Dict, List, Optional
from ._imports import (By, Select, WebDriverWait, EC, NoAlertPresentException,
                       NoSuchElementException, StaleElementReferenceException,
                       TimeoutException)  # noqa: F401


class WorkAllocationTab(BaseAutomationTab):
    """
    Work Allocation automation — allocates labourers to work codes on the portal.

    Two input modes:
      * Bulk      — work keys typed in the text box -> 'Allocate All' checkbox.
      * Granular  — a Demand CSV is loaded (worker name + work code) and only the
                    matching labourers get checked for each work code.
    The Demand tab hands over automatically after demand creation (per-worker
    work codes from the report CSV take priority over a single typed work key).
    """

    # --- Portal element IDs (verified against the live saved page) ---
    SUCCESS_MARKERS = ("allocation has been done", "allocated successfully",
                       "allocation done", "record saved", "data saved successfully")
    PANCHAYAT_IDS = ["ctl00_ContentPlaceHolder1_ddlpanchayat_code"]
    CATEGORY_ID = "ctl00_ContentPlaceHolder1_ddlworkcategory"
    SEARCH_KEY_ID = "ctl00_ContentPlaceHolder1_txtwrksearchkey"
    WORK_CODE_ID = "ctl00_ContentPlaceHolder1_ddlWork_code"
    GRID_ID = "ctl00_ContentPlaceHolder1_GridView1"
    ALLOCATE_ALL_ID = "ctl00_ContentPlaceHolder1_GridView1_ctl01_chkHAllocate"
    SAVE_IDS = ["ctl00_ContentPlaceHolder1_cmdSave"]
    OVERLAY_ID = "ctl00_ContentPlaceHolder1_PageUpdateProgress"
    REG_COL_INDEX = 1   # 'Registration No.*' column = the job card number
    NAME_COL_INDEX = 3  # 'Job seeker name*' column in the workers grid
    ROW_CHECKBOX_CSS = "input[type='checkbox'][id*='chkAllocate']"

    WORK_CATEGORY_OPTIONS = [
        "Anganwadi/Other Rural Infrastructure", "Coastal Areas", "Drought Proofing",
        "Rural Drinking Water", "Food Grain", "Flood Control and Protection",
        "Fisheries", "Micro Irrigation Works",
        "Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers",
        "Land Development", "Other Works", "Play Ground", "Rural Connectivity",
        "Rural Sanitation", "Bharat Nirman Sewa Kendra",
        "Water Conservation and Water Harvesting", "Renovation of traditional water bodies",
    ]

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="work_allocation")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.has_failures = False          # tracks errors for the final summary
        self.csv_allocation_data: Dict[str, List[str]] = {}  # work_code -> [names]
        # Structured rows of every successfully allocated labourer — powers the
        # 'Export for Demand' CSV (job card + name + work key) so the Demand tab
        # can re-load the same workers next week.
        self.allocated_workers_data: List[Dict] = []

        self._create_widgets()
        self.load_inputs()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        # ── Header card ──
        self._create_header_card(self, "📌", tr("tab.work_allocation.title"), tr("tab.work_allocation.subtitle"),
                                 icon_key="emoji_work_allocation")

        # ── Input controls (bordered card) ──
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        controls_frame.grid_columnconfigure(1, weight=1)

        # Row 0: Panchayat
        ctk.CTkLabel(controls_frame, text=tr("common.panchayat_name_label")).grid(
            row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))

        # Row 1: Work Category
        ctk.CTkLabel(controls_frame, text=tr("form.work_alloc.work_category")).grid(
            row=1, column=0, padx=15, pady=5, sticky="w")
        self.work_category_var = ctk.StringVar(value=self.WORK_CATEGORY_OPTIONS[8])
        self.work_category_menu = ctk.CTkOptionMenu(
            controls_frame, variable=self.work_category_var, values=self.WORK_CATEGORY_OPTIONS)
        self.work_category_menu.grid(row=1, column=1, sticky="ew", padx=15, pady=5)

        # Row 2: Demand CSV upload (granular mode)
        ctk.CTkLabel(controls_frame, text=tr("form.work_alloc.use_demand_csv")).grid(
            row=2, column=0, padx=15, pady=5, sticky="w")

        csv_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        csv_frame.grid(row=2, column=1, sticky="ew", padx=15, pady=5)

        self.load_csv_btn = ctk.CTkButton(csv_frame, text=tr("form.work_alloc.load_demand_csv"),
                                          command=self._load_demand_csv,
                                          fg_color="#D35400", hover_color="#A04000", width=150)
        self.load_csv_btn.pack(side="left", padx=(0, 10))

        self.file_label = ctk.CTkLabel(csv_frame, text=tr("common.no_file_selected"), text_color="gray")
        self.file_label.pack(side="left")

        # ── Action buttons (Start / Stop / Reset / Retry) ──
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky='ew', padx=12, pady=6)

        # ── Data tabs (Work Key List, Results, Logs) ──
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        work_list_tab = data_notebook.add("Work Key List")
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # Work Key List tab
        work_list_tab.grid_columnconfigure(0, weight=1)
        work_list_tab.grid_rowconfigure(1, weight=1)

        wc_controls_frame = ctk.CTkFrame(work_list_tab, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=(5, 0))

        ctk.CTkLabel(wc_controls_frame, text=tr("form.work_alloc.work_key_hint")).pack(side='left', padx=5)
        ctk.CTkButton(wc_controls_frame, text=tr("common.clear"), width=80,
                      command=lambda: self.work_list_text.delete("1.0", tkinter.END)).pack(side='right', padx=5)

        self.work_list_text = ctk.CTkTextbox(work_list_tab)
        self.work_list_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # Results tab
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10))

        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_demand_button = ctk.CTkButton(export_controls_frame, text=tr("form.work_alloc.export_demand"),
                                                  command=self.export_for_demand,
                                                  fg_color="#2E7D32", hover_color="#1B5E20")
        self.export_demand_button.pack(side='left', padx=(0, 10))
        self.export_button = ctk.CTkButton(export_controls_frame, text=tr("common.export_excel"),
                                           command=self.export_report)
        self.export_button.pack(side='left')

        cols = ("Panchayat", "Work Key", "Work Name", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        self.results_tree.column("Work Key", anchor='center', width=100)
        self.results_tree.column("Work Name", width=250)
        self.results_tree.column("Status", anchor='center', width=100)
        self.results_tree.column("Details", width=250)
        self.results_tree.column("Timestamp", anchor='center', width=100)
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')

        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)

    def set_ui_state(self, running: bool) -> None:
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.work_category_menu.configure(state=state)
        self.work_list_text.configure(state=state)
        self.load_csv_btn.configure(state=state)
        self.export_button.configure(state=state)
        self.export_demand_button.configure(state=state)

    def reset_ui(self) -> None:
        self.panchayat_var.set("")
        self.csv_allocation_data = {}
        self.allocated_workers_data = []
        self.file_label.configure(text=tr("common.no_file_selected"), text_color="gray")
        self.work_list_text.configure(state="normal")
        self.work_list_text.delete("1.0", tkinter.END)
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.app.clear_log(self.log_display)
        self.update_status("Ready", 0.0)
        self.log_info("Form has been reset.")
        self.app.after(0, self.app.set_status, "Ready")

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------
    def run_automation_from_demand(self, panchayat_name: str, allocation_data: Any) -> None:
        """
        Starts Work Allocation automatically from the Demand tab.

        'allocation_data' is either:
          1. A string  — a single global work key for all successful labourers.
          2. A dict    — { work_code: [labourer_name, ...] } (per-worker codes).
        """
        self.log_info("--- Starting Auto-Allocation from Demand Tab ---")
        self.allocated_workers_data = []
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.app.clear_log(self.log_display)
        self.work_list_text.delete("1.0", tkinter.END)

        inputs: Dict[str, Any] = {
            'panchayat_name': panchayat_name,
            'work_category': self.work_category_var.get(),
        }

        if isinstance(allocation_data, str):
            self.log_info(f"Mode: Bulk Allocation (Single Key: {allocation_data})")
            self.work_list_text.insert("1.0", allocation_data)
            inputs['work_keys'] = [allocation_data]
            inputs['allocation_map'] = None
        elif isinstance(allocation_data, dict):
            self.log_info(f"Mode: Granular Allocation ({len(allocation_data)} work codes)")
            self.work_list_text.insert("1.0", "\n".join(allocation_data.keys()))
            inputs['work_keys'] = list(allocation_data.keys())
            inputs['allocation_map'] = allocation_data
        else:
            messagebox.showerror(tr("dialogs.error"), tr("dialogs.invalid_demand_data"))
            return

        self.panchayat_var.set(panchayat_name)
        self.log_info(f"Panchayat: {panchayat_name}")
        self.log_info(f"Work Category: {inputs['work_category']}")

        self._save_inputs(inputs)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def start_automation(self) -> None:
        self.allocated_workers_data = []
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.app.clear_log(self.log_display)

        inputs: Dict[str, Any] = {
            'panchayat_name': self.panchayat_var.get().strip(),
            'work_category': self.work_category_var.get(),
            'work_list_raw': self.work_list_text.get("1.0", tkinter.END).strip(),
        }

        if not inputs['work_category']:
            messagebox.showwarning(tr("errors.input_error"), tr("dialogs.work_category_required"))
            return

        if self.csv_allocation_data:
            # Granular mode: CSV drives the work codes + labourers
            inputs['work_keys'] = list(self.csv_allocation_data.keys())
            inputs['allocation_map'] = self.csv_allocation_data
            self.log_info(f"Mode: CSV Allocation ({len(inputs['work_keys'])} works loaded)")
        else:
            # Bulk mode: work keys typed in the text box
            if not inputs['work_list_raw']:
                messagebox.showwarning(tr("errors.input_error"), tr("dialogs.enter_work_keys_or_csv"))
                return
            work_keys = [line.strip() for line in inputs['work_list_raw'].splitlines() if line.strip()]
            if not work_keys:
                messagebox.showwarning(tr("errors.input_error"), tr("dialogs.no_valid_work_keys"))
                return
            inputs['work_keys'] = work_keys
            inputs['allocation_map'] = None

        if inputs['panchayat_name']:
            self.app.update_history("location_panchayat", inputs['panchayat_name'])
        self._save_inputs(inputs)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    # ------------------------------------------------------------------
    # Automation
    # ------------------------------------------------------------------
    def _settle(self, driver, reason: str = "") -> None:
        """Short pause after an ASP.NET postback. Silently waits for the
        'Please Wait...' overlay (if it appears) to clear, then a small fixed
        delay. No log spam — the element waits that follow are the real signal
        that a postback finished."""
        try:
            WebDriverWait(driver, 15).until(
                EC.invisibility_of_element_located((By.ID, self.OVERLAY_ID)))
        except Exception:
            pass
        time.sleep(0.5)

    def run_automation_logic(self, inputs: Dict[str, Any]) -> None:
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, self.app.set_status, "Starting Work Allocation...")
        self.log_info("Starting Work Allocation automation...")
        self.has_failures = False

        driver = None
        had_error = False
        try:
            driver = self.app.get_driver()
            if not driver:
                self.app.after(0, self.set_ui_state, False)
                return

            wait = WebDriverWait(driver, 20)
            save_wait = WebDriverWait(driver, 90)  # long wait for the Save confirmation

            self.log_info("Navigating to Work Allocation page...")
            driver.get(config.WORK_ALLOCATION_CONFIG["url"])

            self._setup_page(driver, wait, inputs)

            work_keys: List[str] = inputs.get('work_keys', [])
            allocation_map = inputs.get('allocation_map')
            total_items = len(work_keys)

            for i, work_key in enumerate(work_keys):
                if self.is_stopped():
                    self.log_warning("Stop signal received.")
                    break

                status_msg = f"Processing {i + 1}/{total_items}: Key={work_key}"
                self.app.after(0, self.app.set_status, status_msg)
                self.app.after(0, self.update_status, status_msg, (i + 1) / total_items)

                target_applicants = None
                if allocation_map and work_key in allocation_map:
                    target_applicants = allocation_map[work_key]

                self._process_single_work_key(driver, wait, work_key, target_applicants, save_wait)

        except ValueError as e:
            had_error = True
            error_msg = str(e)
            self.log_error(error_msg)
            messagebox.showerror(tr("errors.input_error"), error_msg)
            self.app.after(0, self.app.set_status, "Error")
        except Exception as e:
            had_error = True
            error_msg = f"A critical error occurred: {e}"
            self.log_error(error_msg)
            messagebox.showerror(tr("dialogs.critical_error"), error_msg)
            self.app.after(0, self.app.set_status, "Error")
        finally:
            self.app.after(0, self.set_ui_state, False)
            if self.is_stopped():
                final_status = "Automation Stopped"
            elif had_error:
                final_status = "Automation Finished with Error"
            elif self.has_failures:
                final_status = "Finished with Errors"
            else:
                final_status = "Automation Finished"
            self.app.after(0, self.app.set_status, final_status)
            self.app.after(0, self.update_status, final_status, 1.0)

            # Don't show a 'success' dialog when the run actually errored
            if "Stopped" not in final_status and "Error" not in final_status:
                kind = "warning" if self.has_failures else "info"
                self.app.after(100, lambda: getattr(messagebox, f"show{kind}")("Complete", f"{final_status}. Check results."))

    def _setup_page(self, driver, wait, inputs: Dict[str, Any]) -> None:
        """Selects panchayat (if a dropdown exists) and the work category.

        Central _select_panchayat_or_skip helper: selects via the dropdown on
        Block/PO login; on Panchayat/GP login (no dropdown) selection is skipped.
        """
        self._disable_smooth_scroll(driver)
        status, _ = self._select_panchayat_or_skip(
            driver, wait, inputs.get('panchayat_name'), self.PANCHAYAT_IDS)
        if status == "missing":
            # Surface to the caller (run_automation_logic shows the error dialog)
            self.log_error("Panchayat Name is required for PO login.")
            raise ValueError("Panchayat Name is required for PO login.")
        if status == "notfound":
            self.log_error(f"Panchayat '{inputs.get('panchayat_name')}' not found in dropdown.")
            raise ValueError(f"Panchayat '{inputs.get('panchayat_name')}' not found in dropdown.")
        if status == "selected":
            self._settle(driver, "Panchayat")
            self.log_info("   - Panchayat selected.")

        self.app.after(0, self.app.set_status, "Setting Work Category...")
        category_select_element = wait.until(EC.element_to_be_clickable((By.ID, self.CATEGORY_ID)))
        category_select = Select(category_select_element)
        if category_select.first_selected_option.text.strip() != inputs['work_category'].strip():
            category_select.select_by_visible_text(inputs['work_category'])
            self._settle(driver, "Category")
            self.log_info("   - Category selected.")

        self.log_success("Setup complete. Starting item processing...")

    def _process_single_work_key(self, driver, wait, work_key: str,
                                 target_applicants: Optional[List[str]] = None,
                                 save_wait: Optional[Any] = None) -> None:
        """Processes one work key: search -> select code -> allocate -> save."""
        if save_wait is None:
            save_wait = wait
        selected_work_code_text = "N/A"
        found_count = 0

        # A mid-run driver.get() (reload after a page error) resets the CSS
        # scroll-behavior — re-disable smooth scrolling so checkbox ticks and
        # the Save click always land correctly.
        self._disable_smooth_scroll(driver)

        try:
            self.log_info(f"   - Processing Key: {work_key}")
            if target_applicants:
                self.log_info(f"     (Granular Mode: Allocating {len(target_applicants)} specific laborers)")

            # 1. Type the work key into the search box (triggers a postback)
            self._enter_work_key(driver, wait, work_key)

            # 2. Pick the matching work code from the refreshed dropdown
            selected_work_code_text = self._select_work_code(driver, wait, work_key)
            if selected_work_code_text is None:
                self._log_result(self.panchayat_var.get().strip(), work_key, "N/A",
                                 "Failed", "Workcode not found in dropdown.")
                return

            # 3. Wait for the workers grid to populate (postback after code selection)
            if not self._wait_for_grid(driver, wait):
                self._log_result(self.panchayat_var.get().strip(), work_key,
                                 selected_work_code_text, "Failed", "Workers grid did not load.")
                return

            # 4. Check the target labourers
            found_count = self._allocate_workers(driver, wait, target_applicants)
            if target_applicants and found_count == 0:
                msg = "Skipped: Labours not found in table."
                self.log_warning(f"   - {msg}")
                self._log_result(self.panchayat_var.get().strip(), work_key,
                                 selected_work_code_text, "Skipped", msg)
                return

            # 4b. Capture which labourers are checked NOW — before Save, because
            # the save postback re-renders the page and the checkboxes reset.
            allocated_workers = self._capture_allocated_workers(driver)

            # 5. Save and read the confirmation
            alert_text = self._save_and_collect(driver, wait, save_wait)
            if alert_text is None:
                self._log_result(self.panchayat_var.get().strip(), work_key,
                                 selected_work_code_text, "Failed", "No confirmation after save.")
                return

            # The portal may also alert about errors (e.g. 'Please select at
            # least one worker') — treat those as failures, not success.
            low = alert_text.lower()
            if any(x in low for x in ("error", "fail", "please", "invalid",
                                      "cannot", "could not", "not found",
                                      "select at least", "not possible")):
                self.log_error(f"   - FAILED: {alert_text}")
                self._log_result(self.panchayat_var.get().strip(), work_key,
                                 selected_work_code_text, "Failed", alert_text)
                return

            # 6. Which labourers got allocated (captured pre-Save above)
            if target_applicants:
                detail_msg = f"{alert_text} (Allocated: {found_count}/{len(target_applicants)})"
            else:
                detail_msg = alert_text
            if allocated_workers:
                names = ", ".join(w['name'] for w in allocated_workers[:12])
                extra = f" (+{len(allocated_workers) - 12})" if len(allocated_workers) > 12 else ""
                detail_msg = f"{detail_msg} | {len(allocated_workers)} labourers: {names}{extra}"
                for w in allocated_workers:
                    self.allocated_workers_data.append({
                        'panchayat': self.panchayat_var.get().strip(),
                        'work_key': work_key,
                        'work_name': selected_work_code_text,
                        'jc': w['jc'],
                        'name': w['name'],
                        'status': 'Success',
                    })

            self.log_success(f"   - Success: {alert_text}")
            self._log_result(self.panchayat_var.get().strip(), work_key,
                             selected_work_code_text, "Success", detail_msg)

        except (TimeoutException, NoAlertPresentException, StaleElementReferenceException) as e:
            error_msg = f"Page error (Timeout/Alert): {str(e).splitlines()[0]}"
            self.log_error(f"   - FAILED: {error_msg}")
            self._log_result(self.panchayat_var.get().strip(), work_key,
                             selected_work_code_text, "Failed", error_msg)
            try:
                driver.get(config.WORK_ALLOCATION_CONFIG["url"])
                self.log_info("   - Refreshing page...")
            except Exception:
                pass

        except Exception as e:
            error_msg = f"Critical error: {e}"
            self.log_error(f"   - FAILED: {error_msg}")
            self._log_result(self.panchayat_var.get().strip(), work_key,
                             selected_work_code_text, "Failed", error_msg)

    # --- single steps for _process_single_work_key ---------------------
    def _enter_work_key(self, driver, wait, work_key: str) -> None:
        search_box = wait.until(EC.element_to_be_clickable((By.ID, self.SEARCH_KEY_ID)))
        search_box.clear()
        search_box.send_keys(work_key)
        driver.find_element(By.TAG_NAME, 'body').click()
        self._settle(driver, "Work Key Search")

    def _select_work_code(self, driver, wait, work_key: str) -> Optional[str]:
        """
        Waits for the work-code dropdown to refresh, then selects the option
        whose text contains the work key. Returns the selected text, or None.
        """
        def _has_options(d):
            try:
                return len(d.find_elements(By.XPATH,
                        f"//select[@id='{self.WORK_CODE_ID}']/option[position()>1]")) > 0
            except Exception:
                return False
        try:
            WebDriverWait(driver, 10).until(_has_options)
        except TimeoutException:
            self.log_info("   - Work code dropdown has no options.")
            return None

        work_code_select_element = wait.until(EC.element_to_be_clickable((By.ID, self.WORK_CODE_ID)))
        work_code_select = Select(work_code_select_element)

        matching_option = None
        for option in work_code_select.options:
            if work_key in option.text:
                matching_option = option
                break
        if not matching_option:
            return None

        work_code_select.select_by_visible_text(matching_option.text)
        self._settle(driver, "Work Code Selection")
        # The work NAME is the part inside parentheses, e.g. '66859 (Provision
        # of Irrigation facility ...)'. Fall back to the full option text.
        return self._extract_work_name(matching_option.text)

    @staticmethod
    def _extract_work_name(option_text: str) -> str:
        """Returns the work name from the dropdown option text — the part
        inside parentheses: '66859 (Provision of Irrigation facility ...)'
        -> 'Provision of Irrigation facility ...'."""
        m = re.search(r"\(([^)]*)\)", option_text or "")
        name = (m.group(1) or "").strip() if m else ""
        return name or (option_text or "").strip()

    def _wait_for_grid(self, driver, wait) -> bool:
        """Waits for the workers grid to gain at least one worker checkbox after
        the work-code selection postback.

        Counts real worker checkboxes (id contains 'chkAllocate') instead of
        <tr> rows — the empty grid still renders a header row plus the
        'Allocate All' (chkHAllocate) row, so a row count would always pass.
        """
        def _has_workers(d):
            try:
                return len(d.find_elements(By.CSS_SELECTOR,
                        f"table[id='{self.GRID_ID}'] {self.ROW_CHECKBOX_CSS}")) > 0
            except Exception:
                return False
        try:
            WebDriverWait(driver, 10).until(_has_workers)
            return True
        except TimeoutException:
            return False

    @staticmethod
    def _names_match(web_name: str, target_name: str) -> bool:
        """True when the two names match, ignoring case/space (exact first,
        then substring — covers prefixes and minor spacing differences)."""
        w = "".join((web_name or "").lower().split())
        t = "".join((target_name or "").lower().split())
        return t == w or (t and t in w)

    @staticmethod
    def _disable_smooth_scroll(driver) -> None:
        """Turns off the portal's CSS smooth scrolling.

        Bootstrap 5 sets `scroll-behavior: smooth` on :root. WebDriver's native
        click() scrolls the target into view and then clicks at the computed
        coordinates — but an ANIMATED scroll keeps the page moving while the
        click fires, so in a long workers grid only the first few checkboxes
        get ticked (the rest are silently missed). Making scrollIntoView
        instant lets every click land on the right row.

        A full page load (driver.get) resets the style, so call this again
        after any mid-run reload (see _process_single_work_key).
        """
        try:
            driver.execute_script("document.documentElement.style.scrollBehavior='auto';")
        except Exception:
            pass

    @staticmethod
    def _tick_checkbox(driver, checkbox) -> bool:
        """Ticks a grid checkbox reliably; returns True only when a NEW tick
        was performed (checkbox was unchecked and is now checked).

        A native checkbox.click() makes the browser scroll the element into
        view first. With the portal's smooth scrolling the page is still
        animating when WebDriver computes the click coordinates, so lower
        checkboxes get silently missed. Instead we scroll via JS (instant) and
        dispatch the click directly on the element — no hit-testing, no
        scrolling race, and it cannot be intercepted by the 'Please Wait'
        overlay. Works for plain row checkboxes and the 'Allocate All' header
        checkbox (its __doPostBack onclick still fires from the JS click).
        """
        try:
            if checkbox.is_selected():
                return False  # already ticked — nothing new done
        except Exception:
            pass
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", checkbox)
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].click();", checkbox)
        except Exception:
            return False
        try:
            return bool(checkbox.is_selected())
        except Exception:
            return False

    def _allocate_workers(self, driver, wait, target_applicants: Optional[List[str]]) -> int:
        """Checks the right checkboxes. Bulk mode -> 'Allocate All' (returns 1).
        Granular mode -> checks only matching labourers (returns count found)."""
        if not target_applicants:
            self.log_info("   - Clicking 'Allocate All'...")
            alloc_checkbox = wait.until(EC.element_to_be_clickable((By.ID, self.ALLOCATE_ALL_ID)))
            was_selected = False
            try:
                was_selected = bool(alloc_checkbox.is_selected())
            except Exception:
                pass
            if not was_selected:
                if not self._tick_checkbox(driver, alloc_checkbox):
                    # JS click failed (rare) — fall back to the native click
                    try:
                        if not alloc_checkbox.is_selected():
                            alloc_checkbox.click()
                    except Exception:
                        pass
                # 'Allocate All' triggers a __doPostBack — give the grid a
                # moment to re-render before we capture the checked labourers.
                self._settle(driver, "Allocate All")
            return 1

        self.log_info("   - Selecting specific applicants...")
        found_count = 0
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, f"table[id='{self.GRID_ID}'] > tbody > tr")
            for i, row in enumerate(rows):
                if i == 0:
                    continue
                try:
                    name_cell = row.find_elements(By.TAG_NAME, "td")[self.NAME_COL_INDEX]
                    name_text = name_cell.get_attribute("innerText").strip()

                    if any(self._names_match(name_text, tn) for tn in target_applicants):
                        checkbox = row.find_element(By.CSS_SELECTOR, self.ROW_CHECKBOX_CSS)
                        if self._tick_checkbox(driver, checkbox):
                            found_count += 1
                        elif not checkbox.is_selected():
                            # Matched labourer, but the tick did not stick —
                            # log it so partial selection is never invisible.
                            self.log_warning(
                                f"   - Could not tick '{name_text.strip()}' — checkbox click did not register.")
                except (StaleElementReferenceException, NoSuchElementException, IndexError):
                    continue
                except Exception:
                    continue
            self.log_info(f"   - Selected {found_count}/{len(target_applicants)} applicants found on page.")
        except Exception as e:
            self.log_error(f"   - Error traversing table: {e}")
        return found_count

    def _capture_allocated_workers(self, driver) -> List[Dict]:
        """Reads the workers grid and returns {jc, name} for every CHECKED row.

        The grid columns are: S.No | Registration No.* | Family days |
        Job seeker name*  — Registration No. is the job card number.
        """
        workers: List[Dict] = []
        try:
            rows = driver.find_elements(By.CSS_SELECTOR,
                                        f"table[id='{self.GRID_ID}'] > tbody > tr")
            for i, row in enumerate(rows):
                if i == 0:
                    continue
                try:
                    cb = row.find_element(By.CSS_SELECTOR, self.ROW_CHECKBOX_CSS)
                    if not cb.is_selected():
                        continue
                    cells = row.find_elements(By.TAG_NAME, "td")
                    name = cells[self.NAME_COL_INDEX].get_attribute("innerText").strip()
                    jc = cells[self.REG_COL_INDEX].get_attribute("innerText").strip() \
                        if len(cells) > self.REG_COL_INDEX else ""
                    if name:
                        workers.append({'jc': jc, 'name': name})
                except (StaleElementReferenceException, NoSuchElementException, IndexError):
                    continue
                except Exception:
                    continue
        except Exception:
            pass
        return workers

    def _save_and_collect(self, driver, wait, save_wait) -> Optional[str]:
        """Clicks Save and waits for the confirmation alert. Returns alert text
        (or None if no alert appeared within the long timeout).

        The Save button sits below a long workers grid, so it is scrolled into
        view and the 'Please wait' overlay is given time to clear before the
        click — a stale overlay was intercepting the click (ElementClickIntercepted
        at the bottom of the viewport). A JS click is used as a last resort.
        """
        self.log_info("   - Clicking 'Save'...")
        save_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
            ", ".join(f"#{x}" for x in self.SAVE_IDS))))

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_button)
        except Exception:
            pass
        self._settle(driver, "Pre-Save")

        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                ", ".join(f"#{x}" for x in self.SAVE_IDS))))
            save_button.click()
        except Exception:
            # Overlay/footer covering the button -> force the click via JS
            try:
                driver.execute_script("arguments[0].click();", save_button)
            except Exception:
                # The success alert may already be blocking — accept it if so
                try:
                    alert = driver.switch_to.alert
                    text = (alert.text or "").strip()
                    try:
                        alert.accept()
                    except Exception:
                        pass
                    return text or "Allocation has been done"
                except Exception:
                    return None

        self.log_info("   - Waiting for allocation confirmation...")
        # The portal confirms a successful save with the JS alert
        # 'Allocation has been done' (rendered in the postback response). Poll
        # for BOTH the live alert and that marker in the page source — the alert
        # can fire during the postback and be missed by alert_is_present.
        timeout = getattr(save_wait, '_timeout', 90) or 90
        deadline = time.time() + timeout
        last_progress_log = time.time()
        while time.time() < deadline:
            if self.is_stopped():
                return None
            try:
                alert = driver.switch_to.alert
                text = (alert.text or "").strip()
                try:
                    alert.accept()
                except Exception:
                    pass
                return text or "Allocation has been done"
            except NoAlertPresentException:
                pass
            except Exception:
                pass
            try:
                src_low = driver.page_source.lower()
                if any(m in src_low for m in self.SUCCESS_MARKERS):
                    return "Allocation has been done"
            except Exception:
                pass
            if time.time() - last_progress_log >= 15:
                last_progress_log = time.time()
                self.log_info("      ...still waiting for confirmation (allocation may already be saved).")
            time.sleep(0.7)
        return None

    # ------------------------------------------------------------------
    # CSV input (granular mode)
    # ------------------------------------------------------------------
    def _load_demand_csv(self) -> None:
        """Loads a Demand CSV and groups workers by their work code."""
        file_path = filedialog.askopenfilename(
            title=tr("form.work_alloc.select_demand_csv"),
            filetypes=[("CSV Files", "*.csv")]
        )
        if not file_path:
            return

        try:
            self.csv_allocation_data = {}
            count = 0

            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                # Map normalized header names -> the actual header casing, so
                # legacy CSVs work whatever the exact spelling/case is.
                header_map = {}
                for h in (reader.fieldnames or []):
                    header_map[str(h).strip().lower().replace(' ', '')] = h

                wc_key = next((header_map[k] for k in ('allocationworkcode', 'workcode')
                               if k in header_map), None)
                if wc_key is None:
                    messagebox.showerror(tr("dialogs.error"), tr("dialogs.csv_allocation_column"))
                    return
                name_key = next((header_map[k] for k in
                                 ('nameofapplicant', 'name', 'applicantname', 'workername')
                                 if k in header_map), None)

                for row in reader:
                    work_code = (row.get(wc_key) or '').strip()
                    person_name = (row.get(name_key) or '').strip() if name_key else ''
                    if work_code and person_name:
                        self.csv_allocation_data.setdefault(work_code, []).append(person_name)
                        count += 1

            filename = os.path.basename(file_path)
            self.file_label.configure(text=f"Loaded: {filename}", text_color="green")
            self.log_info(f"CSV Loaded: {filename}")
            self.log_info(f"Found {len(self.csv_allocation_data)} works with {count} workers.")

            self.work_list_text.configure(state="normal")
            self.work_list_text.delete("1.0", tkinter.END)
            self.work_list_text.insert("1.0",
                f"[CSV Loaded] {filename}\nContains {len(self.csv_allocation_data)} Work Codes.\n\nClick 'Start' to proceed.")
            self.work_list_text.configure(state="disabled")

        except Exception as e:
            self.log_error(f"Error loading CSV: {e}")
            messagebox.showerror(tr("dialogs.error"), tr("dialogs.failed_load_csv", error=e))

    # ------------------------------------------------------------------
    # Results / retry / persistence
    # ------------------------------------------------------------------
    def _log_result(self, panchayat: str, work_key: str, work_code: str,
                    status: str, details: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (panchayat, work_key, truncate_workcode(work_code), status, details, timestamp)

        tags = ()
        if 'success' in status.lower():
            tags = ('success',)
        elif 'failed' in status.lower() or 'error' in status.lower() or 'timeout' in status.lower():
            self.has_failures = True
            tags = ('failed',)

        self.safe_tree_insert(values, tags)

    def retry_logic_handler(self) -> None:
        """Retries failed work keys (granular CSV map is cleared so the keys are
        processed in bulk mode from the text box)."""
        failed_keys = []
        all_items = self.results_tree.get_children()

        if not all_items:
            messagebox.showinfo(tr("base.error_tab.retry_btn"), tr("base.retry_no_results"))
            return

        for item_id in all_items:
            values = self.results_tree.item(item_id)['values']
            work_key = str(values[1])
            status = str(values[3]).lower()
            if "success" not in status and work_key not in failed_keys:
                failed_keys.append(work_key)

        if not failed_keys:
            messagebox.showinfo(tr("dialogs.great"), tr("base.retry_no_fails"))
            return

        if not messagebox.askyesno(tr("base.retry_confirm_title"),
                                   tr("dialogs.retry_failed_keys", count=len(failed_keys))):
            return

        self.work_list_text.configure(state="normal")
        self.work_list_text.delete("1.0", tkinter.END)
        self.work_list_text.insert("1.0", "\n".join(failed_keys))

        # Force bulk mode for the retry (ignore the loaded CSV)
        self.csv_allocation_data = {}
        self.file_label.configure(text=tr("form.work_alloc.retry_mode"), text_color="orange")

        for item in all_items:
            self.results_tree.delete(item)

        self.log_info(f"Retrying {len(failed_keys)} failed work keys...")
        self.start_automation()

    def export_report(self) -> None:
        panchayat_name = self.panchayat_var.get().strip()
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"Work_Allocation_Report_{panchayat_name or 'Report'}_{datetime.now():%Y%m%d_%H%M}.xlsx",
            filter_mode="Export All",
            title_prefix=f"Work Allocation Report: {panchayat_name or 'N/A'}"
        )

    def export_for_demand(self) -> None:
        """Saves a Demand-ready CSV — one row per allocated labourer with the
        job card number, applicant name and work key — so the Demand tab can
        load it next week and re-do demand + allocation for the same workers."""
        if not self.allocated_workers_data:
            messagebox.showinfo(
                tr("errors.no_data"), tr("dialogs.no_allocated_labourers"))
            return
        path = filedialog.asksaveasfilename(
            title=tr("form.work_alloc.export_demand_title"),
            defaultextension=".csv",
            initialfile=f"Work_Allocation_Demand_{datetime.now():%Y%m%d_%H%M}.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            fields = ["Job Card Number", "Applicant Name", "Work Key",
                      "Work Name", "Status", "Panchayat"]
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                for r in self.allocated_workers_data:
                    w.writerow({
                        "Job Card Number": r.get('jc', ''),
                        "Applicant Name": r.get('name', ''),
                        "Work Key": r.get('work_key', ''),
                        "Work Name": r.get('work_name', ''),
                        "Status": r.get('status', 'Success'),
                        "Panchayat": r.get('panchayat', ''),
                    })
            self.log_info(f"Demand-ready CSV exported: {path} ({len(self.allocated_workers_data)} labourers)")
            messagebox.showinfo(tr("dialogs.export"), tr("dialogs.export_csv_saved", path=path))
        except Exception as e:
            messagebox.showerror(tr("dialogs.export_error"), str(e))

    def _save_inputs(self, inputs: Dict[str, Any]) -> None:
        save_data = {
            'panchayat_name': inputs.get('panchayat_name'),
            'work_category': inputs.get('work_category')
        }
        try:
            self.app.history_manager.save_tab_inputs_batch("work_alloc", save_data)
        except Exception as e:
            print(f"Error saving Work Allocation inputs: {e}")

    def load_inputs(self) -> None:
        data = self.app.history_manager.get_tab_inputs("work_alloc")
        if not data:
            return
        saved_panchayat = data.get('panchayat_name')
        if saved_panchayat:
            self.panchayat_var.set(saved_panchayat)
        saved_category = data.get('work_category')
        if saved_category and saved_category in self.work_category_menu.cget("values"):
            self.work_category_var.set(saved_category)
