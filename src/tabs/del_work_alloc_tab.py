# tabs/del_work_alloc_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException,
    WebDriverException
)

from src import config
from .base_tab import BaseAutomationTab

from src.utils import get_logger
from src.i18n import tr
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Keys, Select, WebDriverWait, EC, NoSuchElementException, StaleElementReferenceException, TimeoutException  # noqa: F401


logger = get_logger()

class DelWorkAllocTab(BaseAutomationTab):
    """
    A specific tab class for automating the deletion of Work Allocations on the VB-G-RAM-G portal.
    Features:
    - Robust Page Loading (Handles 'execution context' errors).
    - Search by Panchayat (Case insensitive).
    - Filter by multiple 'From Dates'.
    - Skips gracefully if applicant row is missing.
    - Manual List vs Auto Mode.
    """
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="del_work_alloc")
        
        # Configure Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) 
        
        self._create_widgets()
    def _create_widgets(self) -> None:
        """Initializes and packs the UI components."""

        # --- Header / intro card (pending-bills style) ---
        self._create_header_card(self, "🗑️", tr("tab.del_work_alloc.title"), tr("tab.del_work_alloc.subtitle"),
                                 icon_key="emoji_del_work_alloc")
        
        # --- Section 1: Input Controls (card) ---
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        controls_frame.grid_columnconfigure(1, weight=1)

        # 1. Panchayat Name Input (with Autocomplete)
        ctk.CTkLabel(controls_frame, text=tr("common.panchayat_name_label")).grid(row=0, column=0, sticky='w', padx=(15, 5), pady=12)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=config.ALL_PANCHAYATS_LABEL)
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var,
                                                values=self._all_panchayat_values(p_vals))
        self.panchayat_menu.grid(row=0, column=1, sticky='ew', padx=5, pady=12)

        # 2. Date Filter Input (Multiple Dates Support)
        date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        date_frame.grid(row=0, column=2, sticky='e', padx=15, pady=12)

        ctk.CTkLabel(date_frame, text=tr("common.from_dates")).pack(side="left", padx=(5, 5))
        
        self.from_date_entry = ctk.CTkEntry(date_frame, placeholder_text=tr("form.del_work_alloc.date_placeholder"), width=180)
        self.from_date_entry.pack(side="left", padx=5)

        # Calendar Icon Button
        self.cal_btn = ctk.CTkButton(
            date_frame, 
            text="📅", 
            width=35, 
            fg_color=("gray85", "gray25"), 
            hover_color=("gray75", "gray35"),
            text_color=("black", "white"),
            command=self._on_calendar_click
        )
        self.cal_btn.pack(side="left", padx=2)

        # 3. Explanatory Note
        note_text = "💡 Select '🌐 All Panchayats' to process every panchayat. Optional: type multiple dates (comma-separated) to delete only specific allocations; leave empty to delete ALL."
        note_label = ctk.CTkLabel(
            controls_frame, 
            text=note_text, 
            font=ctk.CTkFont(size=11, slant="italic"), 
            text_color="gray60", 
            justify="left"
        )
        note_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 12))

        # --- Section 2: Action Buttons (Start/Stop) ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,10))

        # --- Section 3: Data Notebook ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0,10))
        
        jobcards_tab = data_notebook.add("Jobcards / Reg IDs")
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # Tab A: Jobcards / Registration IDs
        jobcards_tab.grid_rowconfigure(1, weight=1)
        jobcards_tab.grid_columnconfigure(0, weight=1)

        jc_header_frame = ctk.CTkFrame(jobcards_tab, fg_color="transparent")
        jc_header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        ctk.CTkLabel(jc_header_frame, text="Enter Jobcard / Registration IDs (one per line).\nIf left empty, the bot will process all IDs for the selected Panchayat.", wraplength=700, justify="left").pack(side="left", padx=5)
        
        clear_jc_button = ctk.CTkButton(jc_header_frame, text=tr("common.clear"), width=80, command=lambda: self.jobcards_text.delete("1.0", "end"))
        clear_jc_button.pack(side="right")

        self.jobcards_text = ctk.CTkTextbox(jobcards_tab, height=150)
        self.jobcards_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # Tab B: Results Table
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        self.export_csv_button = ctk.CTkButton(results_action_frame, text=tr("common.export_excel"), command=lambda: self.export_treeview_to_excel(self.results_tree, default_filename="delete_work_alloc_results.xlsx", filter_mode="Export All"))
        self.export_csv_button.pack(side="left")

        cols = ("Timestamp", "Panchayat", "Jobcard/RegID", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        
        self.results_tree.column("Timestamp", width=80, anchor='center')
        self.results_tree.column("Panchayat", width=150)
        self.results_tree.column("Jobcard/RegID", width=200)
        self.results_tree.column("Status", width=100, anchor='center')
        self.results_tree.column("Details", width=350)
        
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        
        self.style_treeview(self.results_tree)

    def _on_calendar_click(self):
        """Uses the BaseAutomationTab's centralized method to open the date picker and appends the date."""
        def append_date(selected_date):
            current_text = self.from_date_entry.get().strip()
            if current_text:
                # Add comma if there are already dates
                self.from_date_entry.insert(tkinter.END, f", {selected_date}")
            else:
                self.from_date_entry.insert(0, selected_date)
            
        self.open_date_picker(append_date)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        """Locks/Unlocks UI elements during automation."""
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.from_date_entry.configure(state=state)
        self.cal_btn.configure(state=state)
        self.jobcards_text.configure(state=state)
    def start_automation(self) -> None:
        """Validates inputs and spawns the automation thread."""
        panchayat = self.panchayat_var.get().strip()
        from_dates_raw = self.from_date_entry.get().strip()

        if not panchayat:
            messagebox.showwarning(tr("errors.input_error"), tr("dialogs.panchayat_name_required"))
            return
        if self._is_panchayat_label(panchayat):
            if not messagebox.askyesno(tr("dialogs.confirm"), tr("dialogs.process_all_panchayats")):
                return

        # Clear previous results
        self.safe_tree_clear()

        jobcard_list = [line.strip() for line in self.jobcards_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]
        
        # Parse multiple dates
        target_dates = [d.strip() for d in from_dates_raw.split(',') if d.strip()]
        
        if not self._is_panchayat_label(panchayat):
            self.app.update_history("location_panchayat", panchayat)
        
        # Start Thread
        self.app.start_automation_thread(
            self.automation_key, 
            self.run_automation_logic, 
            args=(panchayat, jobcard_list, target_dates)
        )
    def reset_ui(self) -> None:
        """Resets the form to default state."""
        if messagebox.askokcancel(tr("dialogs.reset_form"), tr("dialogs.reset_confirm_logs")):
            self.panchayat_var.set("")
            self.from_date_entry.delete(0, tkinter.END)
            self.jobcards_text.delete('1.0', tkinter.END)
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    def _safe_load_page(self, driver, url):
        """
        Robustly loads a page with retries, specifically handling
        'frame does not have execution context' errors.
        """
        for attempt in range(3):
            try:
                self.log_info(f"Loading page (Attempt {attempt+1})...")
                driver.get(url)
                # Check for alert immediately after load (session expired?)
                try:
                    WebDriverWait(driver, 2).until(EC.alert_is_present())
                    driver.switch_to.alert.accept()
                except TimeoutException:
                    pass
                return True
            except Exception as e:
                err_msg = str(e).lower()
                if "execution context" in err_msg or "target window already closed" in err_msg:
                    self.log_warning("Browser glitch detected. Retrying...")
                    try: 
                        # Try to stop loading or refresh to reset state
                        driver.execute_script("window.stop();")
                    except Exception as e:
                        logger.debug("DelWorkAlloc: Could not stop page load: %s", e)
                    time.sleep(2)
                else:
                    raise e # Raise other errors normally
        return False

    def run_automation_logic(self, panchayat, jobcard_list, target_dates):
        """
        The main worker function.
        """
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        
        mode_msg = f"Filtering Dates: {', '.join(target_dates)}" if target_dates else "Mode: Delete ALL"
        self.log_info(f"Starting Delete Work Alloc. {mode_msg}")
        self.app.after(0, self.app.set_status, "Running Delete Work Allocation...")

        try:
            driver = self.app.get_driver()
            if not driver:
                return

            auto_mode = not bool(jobcard_list)
            url = self.resolve_portal_url(config.DEL_WORK_ALLOC_CONFIG["url"])
            wait = WebDriverWait(driver, 20)

            # Determine which panchayats to process
            all_mode = self._is_panchayat_label(panchayat)
            saved_mode = self._is_my_saved_panchayat(panchayat)
            panchayats_to_process = []
            if all_mode:
                if not self._safe_load_page(driver, url):
                    raise Exception("Failed to load page after multiple attempts.")
                panchayat_dropdown = Select(wait.until(EC.visibility_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code"))))
                panchayats_to_process = [t for t in self._get_select_option_texts(panchayat_dropdown) if t]
                if saved_mode:
                    panchayats_to_process = self._filter_panchayats_to_saved(panchayats_to_process)
                    self.log_info(f"⭐ My Saved Panchayats mode: {len(panchayats_to_process)} saved panchayat(s) will be processed.")
                else:
                    self.log_info(f"🌐 All Panchayats mode: found {len(panchayats_to_process)} panchayats.")
                if self._abort_if_no_saved_panchayats(panchayats_to_process):
                    return
            else:
                panchayats_to_process = [panchayat]

            total_p = len(panchayats_to_process)
            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped():
                    self.log_warning("⏹️ Automation stopped by user.")
                    break
                self.log_info(f"===== Panchayat {p_idx+1}/{total_p}: {p_name} =====")
                self.app.after(0, self.update_status, f"{p_name}: selecting...", p_idx / max(total_p, 1))
                if not self._safe_load_page(driver, url):
                    self.log_error(f"Failed to load page for {p_name}. Skipping.")
                    continue

                # 2. Select Panchayat (central helper — fuzzy match; GP login
                # has no dropdown, so selection is skipped)
                try:
                    status, _ = self._select_panchayat_or_skip(
                        driver, wait, p_name,
                        ["ctl00_ContentPlaceHolder1_ddlpanchayat_code"])
                    if status == "notfound":
                        try:
                            dd = Select(wait.until(EC.visibility_of_element_located(
                                (By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code"))))
                            available = [o.text for o in dd.options[:10]]
                        except Exception:
                            available = []
                        self.log_warning(f"Panchayat '{p_name}' not found. Did you mean: {available}? Skipping.")
                        continue
                    if status == "selected":
                        self.log_info(f"Selecting Panchayat: '{p_name}'...")

                        # --- CRITICAL: Wait for Postback ---
                        # Selection triggers __doPostBack. We MUST wait for the page to reload.
                        self.log_info("Waiting for page reload (Postback)...")
                        try:
                            body_elem = driver.find_element(By.TAG_NAME, "body")
                            wait.until(EC.staleness_of(body_elem))
                        except TimeoutException:
                            self.log_warning("Page did not seem to reload. Continuing...")

                        # Wait for Registration dropdown to come back
                        wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration")))
                        self.log_success("Panchayat selected successfully.")
                    # status == "gp" → selection skip (GP login)

                except Exception as e:
                    self.log_error(f"Error selecting Panchayat {p_name}: {e}")
                    continue

                # 3. Determine Items to Process
                items_to_process = []
                if auto_mode:
                    self.log_info("Auto Mode: Fetching all Registration IDs.")
                    # Locate dropdown again after refresh
                    reg_id_dropdown = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration"))))
                    items_to_process = [opt.get_attribute("value") for opt in reg_id_dropdown.options if opt.get_attribute("value") and "Select" not in opt.text]

                    if not items_to_process:
                        self.log_warning(f"No Registration IDs found for {p_name}.")
                else:
                    self.log_info(f"Manual Mode: Processing {len(jobcard_list)} provided IDs.")
                    items_to_process = jobcard_list

                # 4. Process Loop
                total_items = len(items_to_process)
                for i, item_id in enumerate(items_to_process):
                    if self.is_stopped():
                        self.log_warning("⏹️ Automation stopped by user.")
                        break

                    pct = (i + 1) / max(total_items, 1) * 100
                    self.log_info(f"  🔄 [{i+1}/{total_items}] Processing: {item_id} ({pct:.0f}%)")
                    self.app.after(0, self.update_status, f"{p_name}: {i+1}/{total_items}", (p_idx + (i + 1) / max(total_items, 1)) / max(total_p, 1))

                    # Execute the scraping/action logic
                    self._process_single_id(driver, wait, p_name, item_id, auto_mode, target_dates)

            # 5. Completion
            final_msg = "Automation finished." if not self.is_stopped() else "Stopped."
            self.app.after(0, self.update_status, final_msg, 1.0)

            # Count results from tree
            success_count = 0
            fail_count = 0
            for item_id in self.results_tree.get_children():
                vals = self.results_tree.item(item_id)['values']
                if len(vals) >= 4:
                    st = str(vals[3]).lower()
                    if 'success' in st:
                        success_count += 1
                    elif 'fail' in st or 'error' in st:
                        fail_count += 1
            self.log_info(f"\n{'='*50}")
            self.log_info(f"📊 Delete Work Allocation: ✅ {success_count} deleted, ❌ {fail_count} failed (of {total_p} panchayats)")
            self.log_info(f"{'='*50}")

        except Exception as e:
            # Uses the Centralized Error Handler from BaseAutomationTab
            self.handle_error(e)

        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _process_single_id(self, driver, wait, panchayat, item_id, is_auto_mode, filter_dates):
        """
        Processes a single Jobcard/Reg ID.
        """
        try:
            # A. Select or Search the ID
            if not is_auto_mode:
                self.log_info(f"Searching for Jobcard/RegID: {item_id}")
                search_box = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtRegSearch")))
                search_box.clear()
                search_box.send_keys(item_id)
                search_box.send_keys(Keys.TAB)
                
                # Wait for dropdown update
                # Element wait handled by WebDriverWait below

            reg_id_dropdown_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration")))
            reg_id_dropdown = Select(reg_id_dropdown_element)

            if is_auto_mode:
                reg_id_dropdown.select_by_value(item_id)
            else: 
                # In manual mode, select index 1 (the result of search)
                if len(reg_id_dropdown.options) > 1:
                    reg_id_dropdown.select_by_index(1)
                else:
                    raise ValueError("Jobcard search returned no results.")

            # B. Check the Grid View (with short wait for graceful skip)
            try:
                grid_wait = WebDriverWait(driver, 4) # Shorter wait to prevent getting stuck
                grid_view = grid_wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_GridView1")))
                self.log_info(f"Details loaded for {item_id}.")
            except TimeoutException:
                self.log_info(f"No applicant rows/allocations found for {item_id}. Skipping.")
                self._log_result(panchayat, item_id, "Skipped", "No allocations found.")
                return # Exit gracefully and move to the next ID
            
            any_checked = False
            
            # C. Logic: Filter by Date OR Select All
            if filter_dates:
                # --- Filter Mode ---
                date_labels = grid_view.find_elements(By.XPATH, ".//span[contains(@id, '_lblAllocFrom')]")
                
                if not date_labels:
                        self._log_result(panchayat, item_id, "Skipped", "No allocation rows found.")
                        return

                matches_found = 0
                for from_label in date_labels:
                    row_from_text = from_label.text.strip()
                    
                    if row_from_text in filter_dates:
                        # Derive checkbox ID from the label ID
                        # ID format: ..._lblAllocFrom -> ..._chkAllocate
                        chk_id = from_label.get_attribute("id").replace("lblAllocFrom", "chkAllocate")
                        try:
                            checkbox = driver.find_element(By.ID, chk_id)
                            if not checkbox.is_selected():
                                checkbox.click()
                                any_checked = True
                                matches_found += 1
                        except NoSuchElementException:
                            continue
                        
                if not any_checked:
                    self._log_result(panchayat, item_id, "Skipped", f"No rows matched selected dates.")
                    return
                else:
                    self.log_info(f"Found {matches_found} matching allocation(s).")

            else:
                # --- Select All Mode ---
                try:
                    select_all_checkbox = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_GridView1_ctl01_chkHAllocate")
                    select_all_checkbox.click()
                    any_checked = True
                except NoSuchElementException:
                    self._log_result(panchayat, item_id, "Skipped", "No work allocations found to delete.")
                    return

            # D. Submit if necessary
            if any_checked:
                time.sleep(0.5)
                proceed_button = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_cmdUpdate")
                proceed_button.click()
                
                try:
                    # Wait for page reload (stale element)
                    wait.until(EC.staleness_of(grid_view))
                    msg = f"Allocations deleted (Dates: {', '.join(filter_dates)})" if filter_dates else "All allocations deleted."
                    self._log_result(panchayat, item_id, "Success", msg)
                except TimeoutException:
                    # Check for explicit error message on page
                    try:
                        error_element = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_lblMsg")
                        error_text = error_element.text.strip()
                        self._log_result(panchayat, item_id, "Failed", error_text if error_text else "Unknown error after clicking proceed.")
                    except NoSuchElementException:
                        self._log_result(panchayat, item_id, "Failed", "Page did not reload and no error message found.")

        except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ValueError) as e:
            # Handle item-specific errors without crashing the whole thread
            error_msg = str(e).split('\n')[0]
            self.log_error(f"Failed to process {item_id}: {error_msg}")
            self._log_result(panchayat, item_id, "Failed", error_msg)
            
            # Attempt Recovery (Reload page to reset state)
            try:
                driver.get(self.resolve_portal_url(config.DEL_WORK_ALLOC_CONFIG["url"]))
                # We need to re-select Panchayat here because page reloaded to start fresh
                
                wait.until(EC.visibility_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code")))
                p_dropdown = Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code"))
                
                # Quick Fuzzy Match
                target_p = panchayat.strip().lower()
                for opt in p_dropdown.options:
                    if opt.text.strip().lower() == target_p:
                        p_dropdown.select_by_visible_text(opt.text)
                        break
                
                wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration")))

            except Exception as recovery_e:
                self.log_error(f"Recovery failed: {recovery_e}")

    def _log_result(self, panchayat, item_id, status, details):
        """Adds a row to the Results Treeview."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (timestamp, panchayat, item_id, status, details)
        self.safe_tree_insert(values)