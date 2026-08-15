# tabs/mb_entry_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, os, json, sys, subprocess, random
import re
from datetime import datetime, date

# Selenium Imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    UnexpectedAlertPresentException, 
    NoSuchElementException, 
    TimeoutException
)

# Excel Imports
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side



from src import config
from .base_tab import BaseAutomationTab
from src.utils import get_logger, truncate_workcode
from src.i18n import tr
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException  # noqa: F401


logger = get_logger()

class MbEntryTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        """Initializes the eMB Entry tab."""
        super().__init__(parent, app_instance, automation_key="mb_entry")
        
        # Path to save/load form inputs
        self.config_file = self.app.get_data_path("mb_entry_inputs.json")

        self.mapping_file = self.app.get_data_path("mb_panchayat_mate_map.json")
        self.mapping_data = {}
        self._load_mapping_data()
        
        # Dictionary to hold form field variables
        self.config_vars = {}
        
        # Variable for the "Auto MB No." checkbox
        self.auto_mb_no_var = ctk.BooleanVar(value=True)
        
        # --- Panchayat-dependent mate name logic ---
        self.panchayat_after_id = None 
        self.notebook = None 
        # ---

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        
        # Create and load UI elements
        self._create_widgets(); self._load_inputs()
        self._toggle_mb_no_entry() 
    def _create_widgets(self) -> None:
        """Creates and places all UI elements for this tab."""
        
        # --- Header / intro card (P7.2: pending-bills style) ---
        self._create_header_card(self, "📝", tr("tab.mb_entry.title"), tr("tab.mb_entry.subtitle"),
                                 icon_key="emoji_mb_entry")

        # --- Tab View (top): Settings | Work Codes | Results | Logs ---
        self.notebook = ctk.CTkTabview(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        settings_frame = self.notebook.add("Settings")
        work_codes_frame = self.notebook.add("Work Codes")
        results_frame = self.notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=self.notebook)

        # ════════════════ SETTINGS TAB ════════════════
        settings_frame.grid_columnconfigure(0, weight=1)
        settings_frame.grid_rowconfigure(0, weight=1)

        config_frame = ctk.CTkFrame(settings_frame, corner_radius=12, border_width=1,
                                    border_color=("gray85", "gray30"))
        config_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        config_frame.grid_columnconfigure((1, 3), weight=1)
        
        # --- Form Fields ---
        self.panchayat_entry = self._create_option_field(config_frame, "location_panchayat", "Panchayat Name", 0, 0)
        self._with_all_panchayats(self.panchayat_entry)
        self.config_vars["location_panchayat"].set(config.ALL_PANCHAYATS_LABEL)
        self.config_vars["location_panchayat"].trace_add("write", self._on_panchayat_change_debounced)
        
        # --- MB No. with Auto Checkbox ---
        ctk.CTkLabel(config_frame, text=tr("form.mb_entry.mb_no")).grid(row=1, column=0, sticky='w', padx=15, pady=5)
        mb_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        mb_frame.grid(row=1, column=1, sticky='ew', padx=15, pady=5)
        mb_frame.grid_columnconfigure(0, weight=1)
        
        mb_var = ctk.StringVar()
        self.config_vars["measurement_book_no"] = mb_var
        self.mb_no_entry = ctk.CTkEntry(mb_frame, textvariable=mb_var)
        self.mb_no_entry.grid(row=0, column=0, sticky='ew')

        self.auto_mb_no_checkbox = ctk.CTkCheckBox(
            mb_frame, text=tr("form.mb_entry.auto"), variable=self.auto_mb_no_var,
            command=self._toggle_mb_no_entry
        )
        self.auto_mb_no_checkbox.grid(row=0, column=1, padx=(10, 0))
        # --- End MB No. Section ---

        self.page_no_entry = self._create_field(config_frame, "page_no", "Page No.", 1, 2)
        self.unit_cost_entry = self._create_field(config_frame, "unit_cost", "Unit Cost (₹)", 2, 0)
        self.pit_count_entry = self._create_field(config_frame, "default_pit_count", "Pit Count", 2, 2)
        
        self.mate_name_entry = self._create_field(config_frame, "mate_name", "Mate Names (comma-separated)", 3, 0)
        self._on_panchayat_change()

        # ── 💡 Usage Notes info card (pending-bills style) ──
        info_card = ctk.CTkFrame(config_frame, corner_radius=10, border_width=1,
                                 border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        info_card.grid(row=4, column=0, columnspan=4, sticky="ew", padx=15, pady=(10, 15))
        info_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            info_card, text=tr("form.mb_entry.usage_notes"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=(config.COLORS["blue_dark"], config.COLORS["blue_light"])
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            info_card,
            text=tr("form.mb_entry.info_card_text"),
            justify="left", anchor="w", font=ctk.CTkFont(size=11),
            text_color=(config.COLORS["text_dark_alt"], config.COLORS["text_light"])
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        # --- Action Buttons (Start, Stop, Reset) — outside the card ---
        action_frame = self._create_action_buttons(parent_frame=settings_frame)
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 15))


        # --- Work Codes Tab ---
        work_codes_frame.grid_columnconfigure(0, weight=1); work_codes_frame.grid_rowconfigure(1, weight=1)
        wc_controls_frame = ctk.CTkFrame(work_codes_frame, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew')
        
        clear_button = ctk.CTkButton(wc_controls_frame, text=tr("common.clear"), width=80, command=lambda: self.work_codes_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', pady=(5,0), padx=(0,5))
        
        extract_button = ctk.CTkButton(wc_controls_frame, text=tr("common.extract_from_text"), width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_codes_text))
        extract_button.pack(side='right', pady=(5,0), padx=(0, 5))
        
        self.work_codes_text = ctk.CTkTextbox(work_codes_frame, wrap=tkinter.WORD)
        self.work_codes_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        # --- Results Tab ---
        results_frame.grid_columnconfigure(0, weight=1); results_frame.grid_rowconfigure(1, weight=1)
        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        
        # Updated Export Menu
        self.export_button = ctk.CTkButton(export_controls_frame, text=tr("common.export_excel"), command=self.export_report, fg_color="#107C10")
        self.export_button.pack(side='left')

        # --- Results Treeview ---
        cols = ("Panchayat", "Work Code", "Work Name", "Muster Roll No", "MR Period", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        
        for col in cols: 
            self.results_tree.heading(col, text=col)
        
        self.results_tree.column("Panchayat", width=100)
        self.results_tree.column("Work Code", width=120)
        self.results_tree.column("Work Name", width=250)
        self.results_tree.column("Muster Roll No", width=120)
        self.results_tree.column("MR Period", width=150)
        self.results_tree.column("Status", width=80, anchor='center')
        self.results_tree.column("Details", width=200)
        self.results_tree.column("Timestamp", width=80, anchor='center')
        
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree); self._setup_treeview_sorting(self.results_tree)

    def _toggle_mb_no_entry(self):
        """Enables or disables the MB No. entry based on the 'Auto' checkbox."""
        if self.auto_mb_no_var.get():
            self.mb_no_entry.configure(state="disabled")
            self.config_vars["measurement_book_no"].set("Auto from Workcode")
        else:
            self.mb_no_entry.configure(state="normal")
            saved_data = {}
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r') as f: saved_data = json.load(f)
                except (json.JSONDecodeError, IOError): pass
            self.config_vars["measurement_book_no"].set(saved_data.get("measurement_book_no", ""))



    def _create_field(self, parent, key, text, row, col=0, **kwargs):
        """Label + entry stored in self.config_vars[key] (base implementation)."""
        kwargs.setdefault("store", "config_vars")
        return super()._create_field(parent, key, text, row, col=col, **kwargs)

    def _create_option_field(self, parent, key, text, row, col=0, **kwargs):
        """Label + suggestion dropdown stored in self.config_vars[key] (base implementation)."""
        kwargs.setdefault("store", "config_vars")
        return super()._create_option_field(parent, key, text, row, col=col, **kwargs)

    # --- Panchayat-dependent mate name logic ---
    def _get_current_mate_key(self):
        panchayat_name = self.config_vars["location_panchayat"].get().strip().lower()
        panchayat_safe_name = "".join(c for c in panchayat_name if c.isalnum() or c == '_').rstrip()
        if not panchayat_safe_name: return "mate_name_default"
        return f"mate_name_{panchayat_safe_name}"

    def _on_panchayat_change_debounced(self, *args):
        if self.panchayat_after_id: self.after_cancel(self.panchayat_after_id)
        self.panchayat_after_id = self.after(300, self._on_panchayat_change)

    def _load_mapping_data(self):
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, 'r') as f: raw = json.load(f)
                # Normalize keys to lowercase for case-insensitive lookup — same as
                # Muster Roll Gen. The Settings tab saves panchayat names as-typed
                # (usually UPPERCASE), so without normalization the lookup in
                # _on_panchayat_change() would never match and mate auto-fill breaks.
                self.mapping_data = {str(k).strip().lower(): v for k, v in raw.items()}
            except Exception: self.mapping_data = {}

    def _save_mapping_pair(self, panchayat, mate_names):
        if not panchayat or not mate_names: return
        key = panchayat.strip().lower()
        self.mapping_data[key] = mate_names.strip()
        try:
            with open(self.mapping_file, 'w') as f: json.dump(self.mapping_data, f, indent=4)
        except Exception as e: logger.debug("MBEntry: Could not save mapping: %s", e)

    def _on_panchayat_change(self):
        if self.panchayat_after_id: self.after_cancel(self.panchayat_after_id); self.panchayat_after_id = None
        if self.mate_name_entry:
            # Typeable entry (comma-separated names allowed) — mapping se
            # saved list auto-fill hota hai, user manually bhi edit kar sakta hai.
            current_panchayat = self.config_vars["location_panchayat"].get().strip().lower()
            if current_panchayat in self.mapping_data:
                saved_mate = self.mapping_data[current_panchayat]
                if self.config_vars["mate_name"].get().strip() != saved_mate:
                    self.config_vars["mate_name"].set(saved_mate)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running) 
        state = "disabled" if running else "normal"
        self.work_codes_text.configure(state=state)
        self.panchayat_entry.configure(state=state)
        self.page_no_entry.configure(state=state)
        self.unit_cost_entry.configure(state=state)
        self.mate_name_entry.configure(state=state)
        self.pit_count_entry.configure(state=state)
        self.export_button.configure(state=state)
        self.auto_mb_no_checkbox.configure(state=state)
        if state == "normal":
            self._toggle_mb_no_entry()
        else:
            self.mb_no_entry.configure(state="disabled")
    def reset_ui(self) -> None:
        if messagebox.askokcancel(tr("dialogs.reset_form"), tr("dialogs.reset_confirm_logs")):
            self._mr_tracking_panchayat_data = None
            self._load_inputs()
            self.config_vars['location_panchayat'].set("") 
            self.work_codes_text.configure(state="normal")
            self.work_codes_text.delete("1.0", tkinter.END)
            self.work_codes_text.configure(state="disabled")
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    # --- NEW: Override Retry Logic for MB Entry ---
    def retry_logic_handler(self) -> None:
        """
        Custom retry logic for MB Entry Tab because columns are different.
        Tree Columns: 
        0=Panchayat, 1=Work Code, 2=Name, 3=MR, 4=Period, 5=Status, 6=Details
        """
        failed_items = []
        all_items = self.results_tree.get_children()
        
        if not all_items:
            messagebox.showinfo(tr("base.error_tab.retry_btn"), tr("base.retry_no_results"))
            return

        for item_id in all_items:
            values = self.results_tree.item(item_id)['values']
            # Extract relevant columns
            work_code = str(values[1])
            status = str(values[5]).lower()
            
            # Check status
            if "success" not in status:
                failed_items.append(work_code)
        
        if not failed_items:
            messagebox.showinfo(tr("dialogs.great"), tr("base.retry_no_fails"))
            return

        if not messagebox.askyesno(tr("base.retry_confirm_title"), tr("dialogs.retry_failed_now", count=len(failed_items))):
            return

        # 1. Update Input Widget
        self.work_codes_text.configure(state="normal")
        self.work_codes_text.delete("1.0", tkinter.END)
        self.work_codes_text.insert("1.0", "\n".join(failed_items))
        self.work_codes_text.configure(state="disabled")

        # 2. Clear Results
        for item in all_items:
            self.results_tree.delete(item)

        # 3. Auto Start
        self.start_automation()
    def start_automation(self) -> None:
        cfg = {key: var.get().strip() for key, var in self.config_vars.items()}
        if not self.auto_mb_no_var.get() and not cfg.get("measurement_book_no"):
            messagebox.showwarning(tr("errors.input_error"), tr("dialogs.mb_no_required"))
            return
        required_fields = ["location_panchayat", "page_no", "unit_cost", "default_pit_count", "mate_name"]
        if any(not cfg.get(key) for key in required_fields):
            messagebox.showwarning(tr("errors.input_error"), tr("dialogs.all_config_required"))
            return
        work_codes_raw = [line.strip() for line in self.work_codes_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]
        
        if not work_codes_raw:
            proceed = messagebox.askyesno(
                tr("form.mb_entry.no_work_codes"),
                tr("form.mb_entry.no_work_codes_msg")
            )
            if not proceed:
                return
            self.log_info("ℹ️ No work codes provided. Will process all works from dropdown.")
            self._save_mapping_pair(cfg['location_panchayat'], cfg['mate_name'])
        self._save_inputs(cfg)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(cfg, work_codes_raw))
    
    def _save_inputs(self, cfg):
        try:
            self.app.history_manager.save_tab_inputs_batch("mb_entry", cfg)
        except Exception as e: self.log_warning(f"Could not save inputs: {e}")
    def _load_inputs(self):
        saved_data = self.app.history_manager.get_tab_inputs("mb_entry")
        for key, var in self.config_vars.items():
            default_value = config.MB_ENTRY_CONFIG["defaults"].get(key, "")
            saved = saved_data.get(key)
            if key == "location_panchayat":
                # Default to All Panchayats when nothing useful was saved
                default_value = config.ALL_PANCHAYATS_LABEL
                if not saved or saved == config.ALL_PANCHAYATS_LABEL:
                    saved = config.ALL_PANCHAYATS_LABEL
            var.set(saved if saved is not None else default_value)
        self.after(100, self._on_panchayat_change)

    def run_automation_logic(self, cfg, work_codes_raw):
        self.app.after(0, self.set_ui_state, True) 
        self.app.clear_log(self.log_display) 
        self.safe_tree_clear()
        self.log_info("Starting eMB Entry automation...")
        self.app.after(0, self.app.set_status, "Running eMB Entry...") 
        
        try:
            driver = self.app.get_driver()
            if not driver: return 

            mate_names_list = [name.strip() for name in cfg["mate_name"].split(',') if name.strip()]
            if not mate_names_list:
                messagebox.showerror(tr("errors.input_error"), tr("dialogs.mate_name_required"))
                return

            # Determine which panchayats to process
            grouped_data = getattr(self, '_mr_tracking_panchayat_data', None) or {}
            self._mr_tracking_panchayat_data = None
            panchayat_target = cfg['location_panchayat']
            panchayats_to_process = []
            if grouped_data:
                # 📦 MR Tracking grouped mode — process every panchayat's own codes
                panchayats_to_process = list(grouped_data.keys())
                self.log_info(f"📦 MR Tracking data: processing {len(panchayats_to_process)} panchayats.")
            else:
                all_mode = panchayat_target in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL)
                saved_mode = panchayat_target == config.MY_PANCHAYATS_LABEL
                if all_mode:
                    driver.get(self.resolve_portal_url(config.MB_ENTRY_CONFIG["url"]))
                    # Central helper — GP login has no dropdown; ⭐ My
                    # Saved mode me Settings ke saved panchayats directly use.
                    panchayats_to_process, _is_gp = self._fetch_panchayats_from_website(
                        driver, wait, ['ctl00_ContentPlaceHolder1_ddl_panch'],
                        saved_mode=saved_mode)
                    if saved_mode:
                        self.log_info(f"⭐ My Saved Panchayats mode: {len(panchayats_to_process)} saved panchayat(s) will be processed.")
                    else:
                        self.log_info(f"🌐 All Panchayats mode: found {len(panchayats_to_process)} panchayats.")
                    if self._abort_if_no_saved_panchayats(panchayats_to_process):
                        return
                else:
                    panchayats_to_process = [panchayat_target]

            total_p = len(panchayats_to_process)
            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped():
                    self.log_warning("Automation stopped.")
                    break
                self.app.after(0, self.update_status, f"{p_name}: processing...", p_idx / max(total_p, 1))
                cfg['location_panchayat'] = p_name
                self.log_info(f"=== Panchayat {p_idx+1}/{total_p}: {p_name} ===")

                if not self.is_stopped():
                    self.app.update_history("location_panchayat", p_name)
                    mate_key = self._get_current_mate_key()
                    for mate in mate_names_list:
                        self.app.update_history(mate_key, mate)

                # Per-panchayat codes in MR Tracking grouped mode, else user-entered codes
                codes_for_panchayat = grouped_data.get(p_name, []) if grouped_data else work_codes_raw

                # If no work codes entered by user, process all works from dropdown
                if not codes_for_panchayat:
                    self._process_all_works_from_dropdown(driver, cfg, mate_names_list)
                    continue

                processed_codes = set()
                total = len(codes_for_panchayat)
                self.app.after(0, self.app.set_status, f"eMB Entry for {p_name}: {total} workcodes...")

                for i, work_code in enumerate(codes_for_panchayat):
                    if self.is_stopped():
                        self.log_warning("Automation stopped.")
                        break

                    self.app.after(0, self.update_status, f"{p_name}: {i+1}/{total}", (p_idx + (i + 1) / max(total, 1)) / max(total_p, 1))

                    if work_code in processed_codes:
                        self._log_result(cfg, work_code, "Skipped", "Duplicate entry.")
                        continue

                    self._process_single_work_code(driver, work_code, cfg, mate_names_list)
                    processed_codes.add(work_code)

            final_msg = "Automation finished." if not self.is_stopped() else "Stopped."
            self.app.after(0, self.update_status, final_msg, 1.0)
            if not self.is_stopped():
                messagebox.showinfo(tr("dialogs.complete"), tr("dialogs.emb_finished"))
        
        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror(tr("base.automation_error.title"), tr("dialogs.an_error_occurred_detail", error=e))
        finally:
            # Count success/fail from results_tree
            success_count = 0
            fail_count = 0
            for item in self.results_tree.get_children():
                vals = self.results_tree.item(item)['values']
                if len(vals) >= 6:
                    status = str(vals[5]).lower()
                    if 'success' in status:
                        success_count += 1
                    else:
                        fail_count += 1
            self.log_info(f"📊 eMB Entry Complete: ✅ {success_count} measurements entered, ❌ {fail_count} failed (of {success_count + fail_count} total)")
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _log_result(self, cfg, work_code, status, details, work_name="-", mr_no="-", mr_period="-"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        panchayat = cfg.get('location_panchayat', '-')
        tags = ('failed',) if 'success' not in status.lower() else ()
        values = (panchayat, truncate_workcode(work_code), work_name, mr_no, mr_period, status, details, timestamp)
        self.safe_tree_insert(values, tags)

    def _process_single_work_code(self, driver, work_code, cfg, mate_names_list):
        wait = WebDriverWait(driver, 25) 
        extracted_work_name = "-"; extracted_mr_no = "-"; extracted_mr_period = "-"
        
        try:
            self.app.after(0, self.app.set_status, f"Navigating for {work_code}...")
            if "MustorRoll/MeasurementBook.aspx" not in driver.current_url: driver.get(self.resolve_portal_url(config.MB_ENTRY_CONFIG["url"]))

            try:
                # Central helper — GP login (no panchayat dropdown) par
                # selection is skipped; no timeout/error occurs.
                status, _ = self._select_panchayat_or_skip(
                    driver, wait, cfg['location_panchayat'],
                    ['ctl00_ContentPlaceHolder1_ddl_panch'])
                if status == "selected":
                    try:
                        dd = wait.until(EC.presence_of_element_located(
                            (By.ID, 'ctl00_ContentPlaceHolder1_ddl_panch')))
                        wait.until(EC.staleness_of(dd))
                        wait.until(EC.presence_of_element_located(
                            (By.ID, 'ctl00_ContentPlaceHolder1_ddl_panch')))
                    except Exception:
                        pass
            except Exception as e: logger.debug("MBEntry: Panchayat select wait failed: %s", e)
            
            wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_txtMBNo')))

            mb_no_to_use = cfg["measurement_book_no"]
            if self.auto_mb_no_var.get() and len(work_code) >= 4: mb_no_to_use = work_code[-4:] 

            self.app.after(0, self.app.set_status, f"Searching {work_code}...")
            driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtMBNo').value = '{mb_no_to_use}';")
            driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtpageno').value = '{cfg['page_no']}';")
            driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtWrkCode').value = '{work_code}';")
            
            work_dropdown_old = driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_ddlSelWrk')
            search_btn = driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_imgButtonSearch')
            driver.execute_script("arguments[0].click();", search_btn)
            
            self.app.after(0, self.app.set_status, "Waiting for search results...")
            try: wait.until(EC.staleness_of(work_dropdown_old))
            except TimeoutException: pass

            self.app.after(0, self.app.set_status, f"Selecting work details...")
            select_work_elem = wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ddlSelWrk')))
            select_work = Select(select_work_elem)
            found_work = False; target_index = 1 
            clean_search_code = str(work_code).strip()
            
            for index, option in enumerate(select_work.options):
                if (clean_search_code in option.get_attribute("value")) or (clean_search_code in option.text):
                    target_index = index; found_work = True; break
            
            try: extracted_work_name = re.findall(r'\((.*?)\)', select_work.options[target_index].text)[-1]
            except: extracted_work_name = "Unknown"

            element_to_go_stale = select_work_elem 
            select_work.select_by_index(target_index)
            try: wait.until(EC.staleness_of(element_to_go_stale))
            except TimeoutException: pass

            # Re-set page no after dropdown selection (page refresh may clear it)
            driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtpageno').value = '{cfg['page_no']}';")

            self.log_info("🔘 Clicking Radio Button...")
            radio_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_rddist_0")))
            driver.execute_script("arguments[0].click();", radio_btn)
            time.sleep(1.0)  # Short wait after click

            self.log_info("⏳ Waiting for Period Dropdown...")
            # Process EVERY available Measurement Period for this work — not
            # just the first (top) one. Previously only index 1 was processed;
            # now all available dates in the dropdown get an entry saved.
            self._process_all_measurement_periods(
                driver, wait, cfg, work_code, extracted_work_name, mate_names_list,
            )
        
        except Exception as e:
            err_msg = str(e).splitlines()[0]
            self.log_error(f"Error on {work_code}: {err_msg}")
            self._log_result(cfg, work_code, "Failed", "Script Error", extracted_work_name, extracted_mr_no, extracted_mr_period)

    def _process_all_works_from_dropdown(self, driver, cfg, mate_names_list):
        """
        Processes ALL available works from the 'Select Work' dropdown.
        Used when user does NOT provide specific work codes.
        The dropdown list is NOT cleared after each entry.
        """
        wait = WebDriverWait(driver, 25)

        # Step 1: Navigate to page & set panchayat
        self.app.after(0, self.app.set_status, "Navigating to MB Entry page...")
        if "MustorRoll/MeasurementBook.aspx" not in driver.current_url:
            driver.get(self.resolve_portal_url(config.MB_ENTRY_CONFIG["url"]))

        try:
            status, _ = self._select_panchayat_or_skip(
                driver, wait, cfg['location_panchayat'],
                ['ctl00_ContentPlaceHolder1_ddl_panch'])
            if status == "selected":
                try:
                    dd = wait.until(EC.presence_of_element_located(
                        (By.ID, 'ctl00_ContentPlaceHolder1_ddl_panch')))
                    wait.until(EC.staleness_of(dd))
                    wait.until(EC.presence_of_element_located(
                        (By.ID, 'ctl00_ContentPlaceHolder1_ddl_panch')))
                except Exception:
                    pass
        except Exception:
            pass

        wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_txtMBNo')))

        # Step 2: Fill search fields (leave work code empty to fetch all works)
        # For search, use a generic MB No — will be updated per work later for auto mode
        search_mb_no = cfg["measurement_book_no"] if cfg["measurement_book_no"] else "Auto"
        driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtMBNo').value = '{search_mb_no}';")
        driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtpageno').value = '{cfg['page_no']}';")
        driver.execute_script("document.getElementById('ctl00_ContentPlaceHolder1_txtWrkCode').value = '';")

        # Step 3: Click search
        self.log_info("🔍 Searching for all available works...")
        work_dropdown_old = driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_ddlSelWrk')
        search_btn = driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_imgButtonSearch')
        driver.execute_script("arguments[0].click();", search_btn)

        # Wait for dropdown to refresh
        try:
            wait.until(EC.staleness_of(work_dropdown_old))
        except TimeoutException:
            pass

        # Step 4: Extract all work options from dropdown
        select_work_elem = wait.until(
            EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ddlSelWrk'))
        )
        select_work = Select(select_work_elem)

        work_options = []
        for option in select_work.options:
            val = option.get_attribute("value")
            if val and val != "0":
                option_text = option.text
                try:
                    extracted_name = re.findall(r'\((.*?)\)', option_text)[-1]
                except Exception:
                    extracted_name = option_text
                # Extract work code from option text (before $ sign)
                # Dropdown format: workcode$workname
                wc_from_text = option_text.split('$')[0] if '$' in option_text else val
                work_options.append((val, extracted_name, wc_from_text))

        if not work_options:
            self.log_error("❌ No works found in dropdown!")
            self._log_result(cfg, "N/A", "Failed", "No works found in dropdown after search")
            return

        self.log_info(f"✅ Found {len(work_options)} works to process from dropdown.")
        total = len(work_options)
        processed_codes = set()

        # Step 5: Process each work from the dropdown
        for i, (work_code, work_name, wc_from_text) in enumerate(work_options):
            if self.is_stopped():
                self.log_warning("Automation stopped.")
                break

            if work_code in processed_codes:
                self._log_result(cfg, work_code, "Skipped", "Duplicate entry (already processed)", work_name)
                continue

            self.app.after(0, self.update_status, f"Processing {i+1}/{total}: {work_code}", (i + 1) / total)

            try:
                processed_codes.add(work_code)
                # Re-fetch dropdown and select this work
                select_work_elem = wait.until(
                    EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ddlSelWrk'))
                )
                select_work = Select(select_work_elem)

                # Find matching option
                found_idx = None
                for idx, option in enumerate(select_work.options):
                    if option.get_attribute("value") == work_code:
                        found_idx = idx
                        break

                if found_idx is None:
                    self._log_result(cfg, work_code, "Failed", "Work disappeared from dropdown", work_name)
                    continue

                # Select the work from dropdown
                stale_marker = select_work_elem
                select_work.select_by_index(found_idx)
                try:
                    wait.until(EC.staleness_of(stale_marker))
                except TimeoutException:
                    pass

                # Re-set page no after dropdown selection (page refresh may clear it)
                driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtpageno').value = '{cfg['page_no']}';")

                # --- Auto MB No: update MB No field based on work code from option text ---
                # Dropdown text format = workcode$workname → take last 4 digits before $
                if self.auto_mb_no_var.get() and len(wc_from_text) >= 4:
                    auto_mb = wc_from_text[-4:]
                    driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtMBNo').value = '{auto_mb}';")

                # Click Radio Button (district = first option)
                radio_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_rddist_0")))
                driver.execute_script("arguments[0].click();", radio_btn)
                time.sleep(1.0)  # Short wait after click

                # Process EVERY available Measurement Period for this work
                # (previously only the first/top period was processed).
                self._process_all_measurement_periods(
                    driver, wait, cfg, work_code, work_name, mate_names_list,
                )

                # Small delay between works
                time.sleep(2)

            except Exception as e:
                err_msg = str(e).splitlines()[0]
                self.log_error(f"Error on {work_code}: {err_msg}")
                self._log_result(cfg, work_code, "Failed", "Script Error", work_name)

        self.log_info("✅ All dropdown works processed.")

    def _process_all_measurement_periods(self, driver, wait, cfg, work_code, work_name, mate_names_list):
        """Process EVERY available Measurement Period for the currently selected work.

        The 'Select Measurement Period' dropdown (ddlSelMPeriod) lists one option
        per MR period / date range (e.g. '06/07/2026~~~~19/07/2026'). Previously
        only the FIRST (top) option was processed; now every period gets its own
        measurement entry saved, so all available dates are covered.
        """
        # Read all available periods (skip the '-----Select-----' placeholder)
        period_elem = wait.until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlSelMPeriod"))
        )
        period_select = Select(period_elem)
        period_options = [o for o in period_select.options if o.get_attribute("value")]
        if not period_options:
            self._log_result(cfg, work_code, "Failed", "No measurement period found", work_name)
            return

        self.log_info(f"   Found {len(period_options)} measurement period(s) for {work_code}:")
        for opt in period_options:
            self.log_info(f"      - {opt.text}")

        for idx, period_option in enumerate(period_options, 1):
            if self.is_stopped():
                self.log_warning("Automation stopped.")
                break
            period_value = period_option.get_attribute("value")
            period_text = period_option.text
            self.app.after(0, self.app.set_status, f"{work_code}: period {idx}/{len(period_options)} ({period_text})")
            self.app.after(0, self.update_status,
                           f"{work_code}: period {idx}/{len(period_options)} ({period_text})",
                           idx / len(period_options))
            self.log_info(f"   [{idx}/{len(period_options)}] Processing period: {period_text}")

            try:
                # Clear any lingering alert from the previous save before
                # touching the page — an open alert would make the next
                # select/postback throw 'unexpected alert open'.
                try:
                    driver.switch_to.alert.accept()
                    time.sleep(1)
                except Exception:
                    pass

                # Re-fetch the period dropdown fresh each iteration — the page
                # state can change after the previous save — then select this
                # period by its VALUE (robust even if the dropdown was reset).
                period_elem = wait.until(
                    EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlSelMPeriod"))
                )
                period_select = Select(period_elem)
                target_idx = None
                for i, o in enumerate(period_select.options):
                    if o.get_attribute("value") == period_value:
                        target_idx = i
                        break
                if target_idx is None:
                    self._log_result(cfg, work_code, "Failed", f"Period '{period_text}' disappeared from dropdown",
                                     work_name, "-", period_text)
                    continue

                # If this period is ALREADY the active selection, the onchange
                # postback won't fire and person-days could stay stale from the
                # previous period/work. Reset to the placeholder first so the
                # target select below is guaranteed to trigger a postback.
                try:
                    if period_select.first_selected_option.get_attribute("value") == period_value:
                        period_select.select_by_index(0)  # '-----Select-----'
                        try:
                            wait.until(EC.staleness_of(period_elem))
                        except TimeoutException:
                            pass
                        period_elem = wait.until(
                            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlSelMPeriod"))
                        )
                        period_select = Select(period_elem)
                        for i, o in enumerate(period_select.options):
                            if o.get_attribute("value") == period_value:
                                target_idx = i
                                break
                except Exception:
                    pass

                period_stale = period_elem
                period_select.select_by_index(target_idx)
                try:
                    wait.until(EC.staleness_of(period_stale))
                except TimeoutException:
                    pass

                # Wait for person days to load for this period
                wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_lbl_person_days')))
                wait.until(
                    lambda d: d.find_element(By.ID, 'ctl00_ContentPlaceHolder1_lbl_person_days').get_attribute('value') != ''
                )

                try:
                    mr_no = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_lbl_msr").text
                except Exception:
                    mr_no = "-"

                pd_elem = driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_lbl_person_days')
                total_persondays = int(pd_elem.get_attribute('value') or 0)
                if total_persondays == 0:
                    self.log_info(f"      Period '{period_text}': 0 persondays / eMB already booked — skipping.")
                    self._log_result(cfg, work_code, "Skipped", "0 Persondays / eMB already Booked",
                                     work_name, mr_no, period_text)
                    continue

                # Fill activity details
                self.app.after(0, self.app.set_status, f"Filling activity details for {period_text}...")
                prefix = self._find_activity_prefix(driver)
                total_cost = total_persondays * int(cfg["unit_cost"])

                driver.execute_script(f"document.getElementsByName('{prefix}$qty')[0].value = '{total_persondays}';")
                driver.execute_script(f"document.getElementsByName('{prefix}$unitcost')[0].value = '{cfg['unit_cost']}';")
                self.log_info("⚙️ Triggering Auto-Calculation (check)...")
                driver.execute_script("if(typeof check === 'function') { check(); }")
                driver.execute_script(f"document.getElementsByName('{prefix}$labcomp')[0].value = '{total_cost}';")
                self.log_info("⚙️ Triggering Validation (checkLabCom)...")
                driver.execute_script("if(typeof checkLabCom === 'function') { checkLabCom(); }")

                try:
                    driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txtpit').value = '{cfg['default_pit_count']}';")
                except Exception as e:
                    logger.debug("MBEntry: Could not set pit count: %s", e)

                random_mate = random.choice(mate_names_list)
                driver.execute_script(f"document.getElementById('ctl00_ContentPlaceHolder1_txt_mat_name').value = '{random_mate}';")

                # Save
                self.app.after(0, self.app.set_status, f"Saving {work_code} ({period_text})...")
                save_btn = driver.find_element(By.XPATH, '//input[@value="Save"]')
                driver.execute_script("arguments[0].click();", save_btn)

                # Handle alert
                try:
                    alert = wait.until(EC.alert_is_present())
                    alert_text = alert.text
                    alert.accept()
                    status = "Success" if "success" in alert_text.lower() or "saved" in alert_text.lower() else "Failed"
                    self._log_result(cfg, work_code, status, alert_text, work_name, mr_no, period_text)
                    self.log_info(f"      {period_text}: {status} — {alert_text}")
                except TimeoutException:
                    self._log_result(cfg, work_code, "Failed", "No Alert Received", work_name, mr_no, period_text)

                # Let the postback settle before the next period
                time.sleep(2)

            except Exception as e:
                err_msg = str(e).splitlines()[0]
                self.log_error(f"Error on {work_code} period '{period_text}': {err_msg}")
                self._log_result(cfg, work_code, "Failed", "Script Error", work_name, "-", period_text)
                # Continue with the next period — a transient error on one period
                # shouldn't abort the remaining periods of this work.
                continue

    def _find_activity_prefix(self, driver):
        self.log_info("Searching for 'Earth work' activity...")
        for i in range(1, 61): 
            try:
                activity_id = f"ctl00_ContentPlaceHolder1_activity_ctl{str(i).zfill(2)}_act_name"
                element = driver.find_element(By.ID, activity_id)
                text = element.get_attribute("innerText").lower()
                if "earth work" in text:
                    self.log_success(f"Found 'Earth work' in row #{i}.")
                    return f"ctl00$ContentPlaceHolder1$activity$ctl{str(i).zfill(2)}"
            except NoSuchElementException: continue 
        self.log_warning("⚠️ 'Earth work' not found, defaulting to first row (ctl01).")
        return "ctl00$ContentPlaceHolder1$activity$ctl01"
    
    def export_report(self):
        """Export results to professional Excel using the base class method."""
        panchayat = self.config_vars["location_panchayat"].get().strip()
        date_str = datetime.now().strftime("%d-%m-%Y")
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"eMB_Report_{panchayat or 'Report'}_{date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=f"e-MB Entry Report: {panchayat or 'N/A'}"
        )
    
    def load_data_from_mr_tracking(self, workcodes, panchayat_name: str):
        self._mr_tracking_panchayat_data = None

        # --- Grouped multi-panchayat data: {panchayat: [codes]} ---
        if isinstance(workcodes, dict) and workcodes:
            self._mr_tracking_panchayat_data = {
                p: list(dict.fromkeys(c)) for p, c in workcodes.items() if c
            }
            all_codes = [code for codes in self._mr_tracking_panchayat_data.values() for code in codes]
            display_text = "\n".join(all_codes)
            self.config_vars["location_panchayat"].set(panchayat_name or config.ALL_PANCHAYATS_LABEL)
            self._on_panchayat_change()

            self.work_codes_text.configure(state="normal")
            self.work_codes_text.delete("1.0", tkinter.END)
            self.work_codes_text.insert("1.0", display_text)
            self.work_codes_text.configure(state="disabled")

            if self.notebook:
                self.notebook.set("Work Codes")

            count = len(all_codes)
            self.log_info(f"Loaded {count} codes across {len(self._mr_tracking_panchayat_data)} panchayats from MR Tracking: "
                          f"{', '.join(self._mr_tracking_panchayat_data.keys())}")
            return

        # --- Single panchayat: flat string/list of codes ---
        self.config_vars["location_panchayat"].set(panchayat_name)
        self._on_panchayat_change()
        
        # --- UPDATE: Handle List input from Macro ---
        display_text = ""
        if isinstance(workcodes, list):
            display_text = "\n".join(workcodes)
        else:
            display_text = str(workcodes)

        self.work_codes_text.configure(state="normal")
        self.work_codes_text.delete("1.0", tkinter.END)
        self.work_codes_text.insert("1.0", display_text)
        self.work_codes_text.configure(state="disabled")
        
        if self.notebook: self.notebook.set("Work Codes")
        
        count = len(display_text.splitlines()) if display_text else 0
        self.log_info(f"Loaded {count} codes for {panchayat_name}.")