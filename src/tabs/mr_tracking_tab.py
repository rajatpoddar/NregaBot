# tabs/mr_tracking_tab.py
import subprocess
import json
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, os, re
from datetime import datetime

# --- Imports jo add kiye gaye hain ---
# --- End Imports ---


from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont # Import Pillow
from src.utils import resource_path, get_logger

logger = get_logger()
from .base_tab import BaseAutomationTab
from src import config  # <-- Make sure config is imported
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, StaleElementReferenceException, TimeoutException, Alignment, Border, Font, PatternFill, Side, import_pandas  # noqa: F401


# Thread-safe lazy pandas load — see import_pandas() docstring in _imports.py.
# (Previously a module-level `import pandas as pd` here — a migration artifact
#  that, combined with _imports.py's old pandas import, could crash tab opening
#  with 'partially initialized module pandas' under concurrent imports.)
pd = import_pandas()

class MrTrackingTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="mr_tracking")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) # Main notebook takes up space
        
        self.report_headers = [
            "SNo.", "Panchayat Name", "Muster roll number", "Technical Staff (Designation)", 
            "Record No.", "Work Code", "date of Closure of Muster Roll", "Muster Roll Filling Status", 
            "date of generation of Wage List", "Wagelist No.", "FTO No.", "Date of generation of FTO", 
            "Date of 1st sign", "Date of 2nd sign"
        ]
        
        # --- NEW: Headers for the ABPS results tab ---
        self.abps_report_headers = [
            "Panchayat Name", "Muster Roll No.", "Work Code", "Wagelist Number", "Labour Name", "Jobcard Number"
        ]
        
        # Is tab ka apna driver nahi hoga — shared browser use karega (self.app.get_driver())
        
        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:

        # ── Header card ──
        self._create_header_card(self, "📍", "MR Tracking",
                                 "Track muster-roll status, pendency and ABPS — with one-click actions.",
                                 icon_key="emoji_mr_tracking")

        # Frame for all user input controls
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        controls_frame.grid(row=1, column=0, sticky="new", padx=10, pady=(0, 6))
        # Configure 4 columns for compact layout
        controls_frame.grid_columnconfigure(1, weight=1)
        controls_frame.grid_columnconfigure(3, weight=1)

        # --- Row 0: State & District ---
        ctk.CTkLabel(controls_frame, text="State:").grid(row=0, column=0, sticky='w', padx=(15, 5), pady=10)
        # --- Create all entries first (no cross-references) ---
        s_vals = self.app.history_manager.get_suggestions("location_state") or [""]
        self.state_var = ctk.StringVar()
        self.state_menu = ctk.CTkOptionMenu(controls_frame, variable=self.state_var, values=s_vals)
        self.state_menu.grid(row=0, column=1, sticky='ew', padx=5, pady=10)

        ctk.CTkLabel(controls_frame, text="District:").grid(row=0, column=2, sticky='w', padx=(15, 5), pady=10)
        d_vals = self.app.history_manager.get_suggestions("location_district") or [""]
        self.district_var = ctk.StringVar()
        self.district_menu = ctk.CTkOptionMenu(controls_frame, variable=self.district_var, values=d_vals)
        self.district_menu.grid(row=0, column=3, sticky='ew', padx=(5, 15), pady=10)

        # --- Row 1: Block & Panchayat ---
        ctk.CTkLabel(controls_frame, text="Block:").grid(row=1, column=0, sticky='w', padx=(15, 5), pady=5)
        b_vals = self.app.history_manager.get_suggestions("location_block") or [""]
        self.block_var = ctk.StringVar()
        self.block_menu = ctk.CTkOptionMenu(controls_frame, variable=self.block_var, values=b_vals)
        self.block_menu.grid(row=1, column=1, sticky='ew', padx=5, pady=5)

        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=1, column=2, sticky='w', padx=(15, 5), pady=5)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=config.ALL_PANCHAYATS_LABEL)
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=self._all_panchayat_values(p_vals))
        self.panchayat_menu.grid(row=1, column=3, sticky='ew', padx=(5, 15), pady=5)

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

        # --- Row 2: Filter Checkboxes (Compact Text) ---
        filter_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        filter_frame.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=10)

        self.pending_only_var = tkinter.IntVar(value=0)
        self.pending_only_check = ctk.CTkCheckBox(filter_frame, 
                                                  text="Pending for Filling", # Shortened
                                                  variable=self.pending_only_var,
                                                  command=self._on_filter_check_changed)
        self.pending_only_check.pack(side="left", padx=(5, 0))

        self.zero_mr_filter_var = tkinter.IntVar(value=0)
        self.zero_mr_filter_check = ctk.CTkCheckBox(filter_frame,
                                                    text="T+8 to T+15 (Zero MR)", # Shortened
                                                    variable=self.zero_mr_filter_var,
                                                    command=self._on_filter_check_changed)
        self.zero_mr_filter_check.pack(side="left", padx=(15, 0))

        self.abps_pending_var = tkinter.IntVar(value=0)
        self.abps_pending_check = ctk.CTkCheckBox(filter_frame, 
                                                  text="Pending for ABPS", # Shortened
                                                  variable=self.abps_pending_var,
                                                  command=self._on_filter_check_changed)
        self.abps_pending_check.pack(side="left", padx=(15, 0))



        # --- Row 3: Action Buttons (OUTSIDE the card) ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        # --- Output Tabs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        workcode_tab = notebook.add("Workcode List")
        results_tab = notebook.add("Results Table")
        abps_results_tab = notebook.add("ABPS Pendency Results") 
        self._create_log_and_status_area(parent_notebook=notebook)

        # 1. Workcode List Tab
        workcode_tab.grid_columnconfigure(0, weight=1)
        workcode_tab.grid_rowconfigure(1, weight=1)
        
        copy_frame = ctk.CTkFrame(workcode_tab, fg_color="transparent")
        copy_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        
        self.copy_wc_button = ctk.CTkButton(copy_frame, text="Copy Workcodes", command=self._copy_workcodes)
        self.copy_wc_button.pack(side="left")

        self.run_mr_payment_button = ctk.CTkButton(copy_frame, text="Run MR Payment", command=self._run_mr_payment, fg_color="#108842", hover_color="#1A994C")
        self.run_mr_payment_button.pack_forget() 
        
        self.run_emb_entry_button = ctk.CTkButton(copy_frame, text="Run eMB Entry", command=self._run_emb_entry, fg_color="#0A708C", hover_color="#0E95BA")
        self.run_emb_entry_button.pack_forget() 

        self.run_zero_mr_button = ctk.CTkButton(copy_frame, text="Forward to Zero MR", command=self._run_zero_mr, fg_color="#D9534F", hover_color="#C9302C")
        self.run_zero_mr_button.pack_forget()

        self.workcode_textbox = ctk.CTkTextbox(workcode_tab, state="disabled")
        self.workcode_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # 2. Results Tab
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        export_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        self.export_button = ctk.CTkButton(export_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side="left")

        self.generate_pendency_btn = ctk.CTkButton(export_frame, text="Generate Pendency Report (T0-T8)", command=self._open_pendency_report_window, fg_color="#B45309", hover_color="#92400E")
        self.generate_pendency_btn.pack(side="left", padx=15)

        self.results_tree = ttk.Treeview(results_tab, columns=self.report_headers, show='headings')
        for col in self.report_headers: self.results_tree.heading(col, text=col)
        self.results_tree.column("SNo.", width=40, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        
        # 3. ABPS Results Tab
        abps_results_tab.grid_columnconfigure(0, weight=1)
        abps_results_tab.grid_rowconfigure(1, weight=1)
        
        abps_export_frame = ctk.CTkFrame(abps_results_tab, fg_color="transparent")
        abps_export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.abps_export_button = ctk.CTkButton(abps_export_frame, text="Export ABPS Report", command=self._export_abps_report)
        self.abps_export_button.pack(side="left")
        self.abps_export_format_menu = ctk.CTkOptionMenu(abps_export_frame, values=["Excel (.xlsx)"])
        self.abps_export_format_menu.pack(side="left", padx=5)

        self.abps_results_tree = ttk.Treeview(abps_results_tab, columns=self.abps_report_headers, show='headings')
        for col in self.abps_report_headers: self.abps_results_tree.heading(col, text=col)
        self.abps_results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        abps_scrollbar = ctk.CTkScrollbar(abps_results_tab, command=self.abps_results_tree.yview)
        self.abps_results_tree.configure(yscroll=abps_scrollbar.set); abps_scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.abps_results_tree)

    def _on_filter_check_changed(self):
        if self.zero_mr_filter_var.get() == 1:
            self.pending_only_check.configure(state="disabled")
            self.abps_pending_check.configure(state="disabled")
            self.pending_only_var.set(0)
            self.abps_pending_var.set(0)
        elif self.abps_pending_var.get() == 1:
            self.pending_only_check.configure(state="disabled")
            self.zero_mr_filter_check.configure(state="disabled")
            self.pending_only_var.set(0)
            self.zero_mr_filter_var.set(0)
        elif self.pending_only_var.get() == 1:
            self.abps_pending_check.configure(state="disabled")
            self.zero_mr_filter_check.configure(state="disabled")
            self.abps_pending_var.set(0)
            self.zero_mr_filter_var.set(0)
        else:
            self.pending_only_check.configure(state="normal")
            self.abps_pending_check.configure(state="normal")
            self.zero_mr_filter_check.configure(state="normal")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        
        self.state_menu.configure(state=state)
        self.district_menu.configure(state=state)
        self.block_menu.configure(state=state)
        self.panchayat_menu.configure(state=state)
        
        self.pending_only_check.configure(state=state)
        self.abps_pending_check.configure(state=state)
        self.zero_mr_filter_check.configure(state=state)

        
        if state == "normal":
            self._on_filter_check_changed()
        
        self.run_mr_payment_button.configure(state=state)
        self.run_emb_entry_button.configure(state=state)
        self.run_zero_mr_button.configure(state=state)
        self.generate_pendency_btn.configure(state=state) 
        
        self.abps_export_button.configure(state=state)
        self.abps_export_format_menu.configure(state=state)

    def set_for_abps_check(self):
        self.reset_ui(reset_all_filters=False) 
        self.abps_pending_var.set(1)
        self._on_filter_check_changed()

    def reset_ui(self, reset_all_filters=True):
        if reset_all_filters:
            self.pending_only_var.set(0)
            self.abps_pending_var.set(0)
            self.zero_mr_filter_var.set(0)
            self._on_filter_check_changed()
        
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        for item in self.abps_results_tree.get_children(): self.abps_results_tree.delete(item)
        self._update_workcode_textbox("")
        
        self.log_info("Form has been reset.")
        self.update_status("Ready", 0.0)
        

    def start_automation(self) -> None:
        self.run_mr_payment_button.pack_forget() 
        self.run_emb_entry_button.pack_forget() 
        self.run_zero_mr_button.pack_forget() 
        
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        for item in self.abps_results_tree.get_children(): self.abps_results_tree.delete(item) 
        self._update_workcode_textbox("") 
        
        inputs = {
            'state': self.state_var.get().strip(), 
            'district': self.district_var.get().strip(), 
            'block': self.block_var.get().strip(),
            'panchayat': self.panchayat_var.get().strip(),
            'pending_only': self.pending_only_var.get() == 1,
            'abps_pending': self.abps_pending_var.get() == 1,
            'zero_mr_filter': self.zero_mr_filter_var.get() == 1
        }
        
        if not all([inputs['state'], inputs['district'], inputs['block'], inputs['panchayat']]):
            messagebox.showwarning("Input Error", "State, District, Block, and Panchayat are required."); return
        if inputs['panchayat'] == config.ALL_PANCHAYATS_LABEL:
            if not messagebox.askyesno("Confirm", "This will process ALL panchayats in the block. Continue?"):
                return
        
        self.save_inputs(inputs)
        self.app.update_history("location_state", inputs['state'])
        self.app.update_history("location_district", inputs['district'])
        self.app.update_history("location_block", inputs['block'])
        if inputs['panchayat'] not in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL):
            self.app.update_history("location_panchayat", inputs['panchayat'])
        
        driver = self.app.get_driver()
        if not driver:
            self.log_error("ERROR: Pehle Launch Chrome karein.")
            messagebox.showwarning("Browser Required", "Kripya pehle 'Launch Chrome' button se browser start karein.")
            return
        
        self.app.after(0, self.set_ui_state, True) 
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.app.set_status, "Starting MR Tracking...") 
        self.app.after(0, self.update_status, "Initializing...", 0.0) 
        self.app.clear_log(self.log_display)
        self.log_info("Starting MR Tracking automation...")        
        self.zero_mr_data = [] 
        
        try:
            driver = self.app.get_driver()
            if not driver:
                self.log_error("ERROR: Browser driver not found.")
                return 
                
            wait = WebDriverWait(driver, 20)
            
            url = config.MR_TRACKING_CONFIG["url"]
            main_window_handle = driver.current_window_handle

            # VB-G-RAM-G portal uses IDs WITHOUT the ctl00 prefix
            STATE_ID = "ContentPlaceHolder1_ddl_state"
            DIST_ID = "ContentPlaceHolder1_ddl_dist"
            BLOCK_ID = "ContentPlaceHolder1_ddl_blk"
            PANCH_ID = "ContentPlaceHolder1_ddl_pan"
            RADIO_PAYMENT_PENDING_ID = "ContentPlaceHolder1_Rbtn_pay_1"
            RADIO_T8_T15_ID = "ContentPlaceHolder1_Rbtn_pay_2"
            SUBMIT_BTN_ID = "ContentPlaceHolder1_Button1"
            TABLE_XPATH = "//table[@bordercolor='#EBEBEB' and .//b[text()='SNo.']]"

            def wait_for_dropdown(dropdown_id, step_name, progress):
                """
                Dropdown ke populate hone ka wait karta hai.
                Asli postback ke liye 'onchange' event fire karna zaroori hai jo
                __doPostBack trigger karta hai — lekin Selenium ka select_by_visible_text
                woh event fire nahi karta. Isliye yahan select ke baad manually
                dropdown ki option count check ki jaati hai.
                """
                self.app.after(0, self.app.set_status, f"Waiting for {step_name}...")
                self.app.after(0, self.update_status, f"Waiting for {step_name}...", progress)
                self.log_info(f"⏳ Waiting for '{step_name}' dropdown ({dropdown_id}) to populate via postback...")
                try:
                    wait.until(
                        EC.presence_of_element_located((By.XPATH, f"//select[@id='{dropdown_id}']/option[position()>1]"))
                    )
                    self.log_info(f"✅ '{step_name}' dropdown populated with options.")
                    time.sleep(0.5)
                except TimeoutException:
                    self.log_warning(f"'{step_name}' dropdown ({dropdown_id}) populate nahi hua (postback timeout).")
                    raise TimeoutException(f"Dropdown '{step_name}' ({dropdown_id}) did not populate after state selection.")

            def select_location(progress_start):
                """Navigate to MR Tracking and select state/district/block.
                Returns the populated panchayat dropdown."""
                self.app.after(0, self.app.set_status, "Navigating to MR Tracking...")
                self.app.after(0, self.update_status, "Navigating...", progress_start)
                self.log_info("Navigating to MR Tracking page...")
                driver.get(url)

                self.app.after(0, self.app.set_status, f"Selecting State: {inputs['state']}")
                self.app.after(0, self.update_status, "Selecting State...", progress_start + 0.05)
                self.log_info(f"Selecting State: {inputs['state']}")
                state_select = Select(wait.until(EC.element_to_be_clickable((By.ID, STATE_ID))))
                self._select_by_text_case_insensitive(state_select, inputs['state'])
                wait_for_dropdown(DIST_ID, "Districts", progress_start + 0.1)

                self.app.after(0, self.app.set_status, f"Selecting District: {inputs['district']}")
                self.app.after(0, self.update_status, "Selecting District...", progress_start + 0.15)
                self.log_info(f"Selecting District: {inputs['district']}")
                dist_select = Select(wait.until(EC.element_to_be_clickable((By.ID, DIST_ID))))
                self._select_by_text_case_insensitive(dist_select, inputs['district'])
                wait_for_dropdown(BLOCK_ID, "Blocks", progress_start + 0.2)

                self.app.after(0, self.app.set_status, f"Selecting Block: {inputs['block']}")
                self.app.after(0, self.update_status, "Selecting Block...", progress_start + 0.25)
                self.log_info(f"Selecting Block: {inputs['block']}")
                self.select_dropdown(driver, BLOCK_ID, inputs['block'])

                # Wait for the panchayat dropdown to populate after block postback
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, f"//select[@id='{PANCH_ID}']/option[position()>1]")))
                except TimeoutException:
                    self.log_warning("Panchayat dropdown did not populate after block selection.")
                time.sleep(0.5)
                return Select(wait.until(EC.element_to_be_clickable((By.ID, PANCH_ID))))

            # --- Determine which panchayats to process ---
            all_mode = inputs['panchayat'] in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL)
            saved_mode = inputs['panchayat'] == config.MY_PANCHAYATS_LABEL
            panchayats_to_process = []
            skip_first_nav = False
            if all_mode:
                # The portal already has a built-in 'ALL' option in the panchayat
                # dropdown that returns every panchayat's records in one report.
                self.log_info("🌐 All Panchayats mode: checking for the portal's built-in 'ALL' option...")
                panchayat_dd = select_location(0.0)
                all_option = None
                for opt in panchayat_dd.options:
                    t = opt.text.strip()
                    if t.upper() in ("ALL", "ALL PANCHAYATS", "ALL PANCHAYAT", "ALL GPs", "ALL GP"):
                        all_option = t
                        break
                if all_option and not saved_mode:
                    panchayats_to_process = [all_option]
                    skip_first_nav = True
                    self.log_info(f"🌐 Portal has a built-in '{all_option}' option — processing all panchayats in one run.")
                else:
                    panchayats_to_process = [t for t in self._get_select_option_texts(panchayat_dd)
                                             if t and t.strip().upper() not in ("ALL", "ALL PANCHAYATS", "ALL PANCHAYAT", "ALL GPs", "ALL GP")]
                    if saved_mode:
                        panchayats_to_process = self._filter_panchayats_to_saved(panchayats_to_process)
                        self.log_info(f"⭐ My Saved Panchayats mode: {len(panchayats_to_process)} saved panchayat(s) will be processed.")
                    else:
                        self.log_info(f"🌐 No built-in 'ALL' option found — looping over {len(panchayats_to_process)} panchayats.")
                if self._abort_if_no_saved_panchayats(panchayats_to_process):
                    return
            else:
                panchayats_to_process = [inputs['panchayat']]

            total_p = len(panchayats_to_process)
            workcode_list = []
            displayed_rows = 0
            abps_pending_count = 0
            pending_filling_count = 0
            abps_pending_mrs = []

            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped():
                    self.log_warning("Stop signal received.")
                    break

                self.log_info(f"===== Panchayat {p_idx+1}/{total_p}: {p_name} =====")
                if skip_first_nav and p_idx == 0:
                    # Reuse the page already loaded during the pre-fetch above
                    pass
                else:
                    panchayat_dd = select_location(0.0)

                self.app.after(0, self.app.set_status, f"Selecting Panchayat: {p_name}")
                self.app.after(0, self.update_status, f"Selecting Panchayat ({p_idx+1}/{total_p})...", 0.3)
                self.log_info(f"Selecting Panchayat: {p_name}")
                self._select_by_text_case_insensitive(panchayat_dd, p_name)
                # Wait for the panchayat postback to settle
                try:
                    wait.until(lambda d: Select(d.find_element(By.ID, PANCH_ID)).first_selected_option.text.strip().lower() == p_name.lower())
                except TimeoutException:
                    pass
                time.sleep(0.5)

                self.app.after(0, self.app.set_status, "Setting filter...")
                self.app.after(0, self.update_status, "Setting filter...", 0.35)
                if inputs['zero_mr_filter']:
                    self.log_info("Selecting '...T+8 and T+15'")
                    wait.until(EC.element_to_be_clickable((By.ID, RADIO_T8_T15_ID))).click()
                else:
                    self.log_info("Selecting 'Where payment is pending'")
                    wait.until(EC.element_to_be_clickable((By.ID, RADIO_PAYMENT_PENDING_ID))).click()

                self.app.after(0, self.app.set_status, "Submitting form...")
                self.app.after(0, self.update_status, "Submitting form...", 0.4)
                self.log_info("Submitting form...")
                wait.until(EC.element_to_be_clickable((By.ID, SUBMIT_BTN_ID))).click()

                self.app.after(0, self.app.set_status, "Waiting for report...")
                self.app.after(0, self.update_status, "Waiting for report...", 0.45)
                self.log_info("Waiting for report table...")
                try:
                    table = wait.until(EC.presence_of_element_located((By.XPATH, TABLE_XPATH)))
                except TimeoutException:
                    self.log_warning(f"No report table found for {p_name}. Skipping.")
                    continue

                # ⚡ FAST READ: fetch the ENTIRE table's cell text in ONE round trip
                # (instead of ~15 Selenium round-trips per row, which made big
                # reports take minutes instead of seconds).
                try:
                    all_rows_data = driver.execute_script(
                        "var rows = arguments[0].querySelectorAll('tr'); var out = []; "
                        "for (var r = 1; r < rows.length; r++) { var c = rows[r].querySelectorAll('td'); var arr = []; "
                        "for (var i = 0; i < c.length; i++) { arr.push((c[i].innerText || '').trim()); } out.push(arr); } return out;",
                        table
                    ) or []
                except Exception as e:
                    self.log_warning(f"Could not read report table for {p_name}: {str(e)[:120]} Skipping.")
                    continue

                total_rows = len(all_rows_data)
                if total_rows == 0:
                    if not all_mode:
                        self.log_warning("No records found for the selected criteria.")
                        messagebox.showinfo("No Data", "No records found for the selected criteria.")
                        self.success_message = None
                        return
                    self.log_warning(f"No records found for {p_name}.")
                    continue

                self.log_info(f"Found {total_rows} records in {p_name}. Processing...")
                insert_buffer = []
                for i, row_data in enumerate(all_rows_data):
                    if self.is_stopped():
                        self.log_warning("Stop signal received.")
                        break

                    if not row_data or len(row_data) < len(self.report_headers):
                        continue

                    panchayat_name = row_data[1] if len(row_data) > 1 else ""
                    muster_roll_no = row_data[2] if len(row_data) > 2 else ""
                    work_code = row_data[5] if len(row_data) > 5 else ""
                    muster_status = row_data[7] if len(row_data) > 7 else ""
                    wagelist_no = row_data[9] if len(row_data) > 9 else ""
                    fto_no = row_data[10] if len(row_data) > 10 else ""
                    fto_date = row_data[11] if len(row_data) > 11 else ""
                    first_sign_date = row_data[12] if len(row_data) > 12 else ""

                    is_abps_pending = "Pending for signature of 1st Signatory" in first_sign_date and not fto_no and not fto_date
                    is_pending_filling = "Pending for filling" in muster_status

                    if inputs['abps_pending']:
                        if not is_abps_pending:
                            continue
                    elif inputs['pending_only']:
                        if not is_pending_filling:
                            continue

                        if "since 0 days" in muster_status or "since 1 days" in muster_status or "since 1 Day" in muster_status:
                            self.log_info(f"Skipping MR {muster_roll_no} (0/1 days pending).")
                            continue

                    elif inputs['zero_mr_filter']:
                        self.zero_mr_data.append({
                            "panchayat": panchayat_name,
                            "work_code": work_code,
                            "msr_no": muster_roll_no
                        })

                    insert_buffer.append(tuple(row_data))
                    displayed_rows += 1

                    if work_code:
                        workcode_list.append(work_code)

                    if is_abps_pending:
                        abps_pending_count += 1
                        abps_pending_mrs.append({
                            "panchayat": panchayat_name,
                            "mr_no": muster_roll_no,
                            "work_code": work_code,
                            "wagelist_no": wagelist_no
                        })
                    if is_pending_filling:
                        pending_filling_count += 1

                    # Batched tree inserts (keeps the UI snappy)
                    if len(insert_buffer) >= 50:
                        batch = list(insert_buffer)
                        insert_buffer.clear()
                        self.app.after(0, lambda b=batch: self._insert_rows_batch(b))

                    # Throttled progress — keyed on the row INDEX so filter-heavy
                    # modes (where most rows are skipped) still show movement
                    if i % 50 == 0 or i == total_rows - 1:
                        self.app.after(0, self.update_status, f"Processing row {i+1}/{total_rows} ({p_name})", 0.4 + ((i + 1) / max(total_rows, 1)) * 0.3)

                if insert_buffer:
                    batch = list(insert_buffer)
                    insert_buffer.clear()
                    self.app.after(0, lambda b=batch: self._insert_rows_batch(b))



            if self.is_stopped():
                 self.log_warning("Automation stopped by user.")
                 self.success_message = None 
                 return 

            self.app.after(0, self._update_workcode_textbox, "\n".join(workcode_list))
            
            if inputs['abps_pending'] and abps_pending_mrs:
                self.log_info(f"Found {abps_pending_count} MRs pending for ABPS. Now finding workers...")                
                wagelists_to_search = {}
                for mr in abps_pending_mrs:
                  wl = mr["wagelist_no"]
                  if not wl: 
                      self.log_warning(f"Skipping MR {mr['mr_no']} (Workcode: {mr['work_code']}) as Wagelist No. is blank.")
                      continue
                  if wl not in wagelists_to_search:
                    wagelists_to_search[wl] = []
                  wagelists_to_search[wl].append(mr)
                
                self.log_info(f"Found {len(wagelists_to_search)} unique wagelists to scan.")                
                total_wl = len(wagelists_to_search)
                for i, (wagelist_no, mr_list) in enumerate(wagelists_to_search.items()):
                    if self.is_stopped(): break
                    
                    progress = 0.8 + ( (i + 1) / total_wl ) * 0.2
                    status_msg = f"Scanning Wagelist {i+1}/{total_wl} ({wagelist_no})"
                    self.app.after(0, self.app.set_status, status_msg)
                    self.app.after(0, self.update_status, status_msg, progress)
                    
                    self._search_wagelist_for_pending_abps(driver, wait, inputs, wagelist_no, mr_list, main_window_handle)

                if driver.current_window_handle != main_window_handle:
                    driver.switch_to.window(main_window_handle)

            if inputs['abps_pending']:
                self.success_message = f"MR Tracking complete. Found {abps_pending_count} MRs pending for ABPS."
            elif inputs['pending_only']:
                self.success_message = f"MR Tracking complete. Found {pending_filling_count} MRs pending for filling."
            elif inputs['zero_mr_filter']:
                self.success_message = f"MR Tracking complete. Found {len(self.zero_mr_data)} MRs for Zero MR processing."
            else:
                self.success_message = f"MR Tracking complete. Displayed {displayed_rows} total records."
            
            self.log_success(f"Processing complete. {self.success_message.replace('MR Tracking complete. ', '')}")            
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
            err_text = str(e).splitlines()[0] if str(e).strip() else "Element not found on page"
            if driver and "Session Expired" in driver.page_source:
                self.log_error("❌ Session expired. Please Login again and retry.")
                messagebox.showerror("Session Expired", "Session expired. Please Login again and retry.")
            else:
                self.log_error(f"{err_text}")
                messagebox.showerror("Automation Error",
                    f"{err_text}\n\n"
                    f"💡 Tip: Check if the page has changed. "
                    f"Element IDs might need updating in the code.")
                
            self.app.after(0, self.app.set_status, "Error")
            self.success_message = None
        except Exception as e:
            self.log_error(f"An unexpected error occurred: {e}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred: {e}")
            self.app.after(0, self.app.set_status, "Unexpected Error")
            self.success_message = None
        finally:
            # Shared browser use kar rahe hain — isliye driver.quit() nahi karte
            self.app.after(0, self.set_ui_state, False) 
            
            final_app_status = "Automation Stopped" if self.is_stopped() else \
                              ("Automation Finished" if hasattr(self, 'success_message') and self.success_message else "Automation Failed")
            final_tab_status = "Stopped" if self.is_stopped() else \
                              ("Finished" if hasattr(self, 'success_message') and self.success_message else "Failed")

            self.app.after(0, self.app.set_status, final_app_status)
            self.app.after(0, self.update_status, final_tab_status, 1.0)

            if not self.is_stopped():
                 self.app.after(5000, lambda: self.app.set_status("Ready")) 
                 self.app.after(5000, lambda: self.update_status("Ready", 0.0)) 

            if hasattr(self, 'success_message') and self.success_message and not self.is_stopped():
                self.log_info(f"📊 MR Tracking Complete: {self.success_message}")
                
                if inputs.get('zero_mr_filter', False):
                    self.app.after(0, lambda: self.run_zero_mr_button.pack(side="left", padx=(10, 0)))
                else:
                    self.app.after(0, lambda: self.run_mr_payment_button.pack(side="left", padx=(10, 0)))
                    self.app.after(0, lambda: self.run_emb_entry_button.pack(side="left", padx=(10, 0)))

    def _search_wagelist_for_pending_abps(self, driver, wait, inputs, wagelist_no, mr_list, main_window_handle):
        try:
            self.log_info(f"   Opening homesearch tab for {wagelist_no}...")
            driver.execute_script("window.open(arguments[0], '_blank');", "https://mnregaweb4.nic.in/netnrega/homesearch.htm")
            time.sleep(1) 
            
            popup_handle = [handle for handle in driver.window_handles if handle != main_window_handle][-1]
            driver.switch_to.window(popup_handle)

            self.log_info("   Waiting for iframe...")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))
            self.log_info("   ...Switched to iframe.")            
            self.log_info("   Selecting 'WageList' from dropdown...")
            Select(wait.until(EC.element_to_be_clickable((By.ID, "ddl_search")))).select_by_value("WageList")
            
            self.log_info("   Waiting for State dropdown to populate (Postback 1)...")
            wait.until(EC.presence_of_element_located((By.XPATH, "//select[@id='ddl_state']/option[text()='ANDAMAN AND NICOBAR']")))
            self.log_info("   ...State dropdown populated.")            
            self.log_info(f"   Selecting State: {inputs['state'].upper()}...")
            state_select = Select(wait.until(EC.element_to_be_clickable((By.ID, "ddl_state"))))
            self._select_by_text_case_insensitive(state_select, inputs['state'])
            
            self.log_info("   Waiting for District dropdown to populate (Postback 2)...")
            wait.until(EC.presence_of_element_located((By.XPATH, f"//select[@id='ddl_district']/option[text()='{inputs['district'].upper()}']")))
            self.log_info("   ...District dropdown populated.")            
            self.log_info(f"   Selecting District: {inputs['district'].upper()}...")
            dist_select = Select(driver.find_element(By.ID, "ddl_district"))
            self._select_by_text_case_insensitive(dist_select, inputs['district']) 
            
            self.log_info("   Waiting for final postback (2 sec)...")
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                pass
            self.log_info("   ...Wait complete.")
            self.log_info(f"   Entering Wagelist No: {wagelist_no}...")
            keyword_box = wait.until(EC.element_to_be_clickable((By.ID, "txt_keyword2")))
            keyword_box.send_keys(wagelist_no)
            
            self.log_info("   Clicking 'GO'...")
            self._find(driver, By.XPATH, "//input[@value='GO']").click()

            self.log_info("   Waiting for search result popup...")
            wait.until(EC.number_of_windows_to_be(3))
            self.log_info("   ...Search result popup appeared.")            
            wagelist_search_popup_handle = [h for h in driver.window_handles if h != main_window_handle and h != popup_handle][0]
            driver.switch_to.window(wagelist_search_popup_handle)

            self.log_info("   Clicking wagelist link in popup...")
            wl_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, wagelist_no)))
            wl_link.click()

            self.log_info("   Waiting for wagelist details page...")
            wait.until(EC.presence_of_element_located((By.ID, "lb_main")))
            self.log_info("   ...Wagelist details page loaded.")            
            self.log_info(f"   Scanning {wagelist_no} for pending workers...")
            details_table = wait.until(EC.presence_of_element_located((By.XPATH, "//span[@id='lb_main']/ancestor::center/table[1]")))
            worker_rows = details_table.find_elements(By.XPATH, ".//tr[position() > 1]") 
            
            found_workers = set() 
            
            for row in worker_rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                
                if len(cells) < 15: continue 
                
                jobcard_no = cells[8].text.strip()
                applicant_name = cells[9].text.strip()
                fto_no = cells[12].text.strip()
                
                if not fto_no and (jobcard_no, applicant_name) not in found_workers:
                    found_workers.add((jobcard_no, applicant_name))
                    self.log_info(f"      > Found pending: {applicant_name} ({jobcard_no})")
                    for mr in mr_list:
                        result_data = (mr["panchayat"], mr["mr_no"], mr["work_code"], wagelist_no, applicant_name, jobcard_no)
                        self.app.after(0, lambda data=result_data: self.abps_results_tree.insert("", "end", values=data))
            
            if not found_workers:
                 self.log_info(f"   No pending workers found in {wagelist_no}.")
        except Exception as e:
            self.log_error(f"   ERROR scanning wagelist {wagelist_no}: {type(e).__name__} {str(e).splitlines()[0]}")
        finally:
            self.log_info("   Closing popup windows...")
            for handle in driver.window_handles:
                if handle != main_window_handle:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(main_window_handle)
            self.log_info("   ...Finished wagelist scan.")
            time.sleep(0.5) 

    # --- PENDENCY REPORT FEATURE (T0 to T8+) ---

    # --- UPDATED PENDENCY REPORT FEATURE (Matches Reference Image) ---

    def _open_pendency_report_window(self):
        """Calculates and displays the Pendency Report based on current table data."""
        items = self.results_tree.get_children()
        if not items:
            messagebox.showinfo("No Data", "Please run the MR Tracking automation first to get data.")
            return

        # --- Calculate Data ---
        summary_data = self._process_pendency_data(items)
        if not summary_data:
            messagebox.showinfo("No Pendency Data", "Could not find any 'since X days' text in the current results.")
            return

        # --- Create Popup Window ---
        win = ctk.CTkToplevel(self)
        win.title("Pendency Report (T0 - T8)")
        win.geometry("1000x600")
        win.transient(self) 
        
        # Grid Configuration
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(win, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkLabel(header_frame, text="Panchayat-wise Pendency Analysis", font=("Arial", 16, "bold")).pack(side="left")
        
        export_btn = ctk.CTkButton(header_frame, text="Download Excel Report", 
                                   command=lambda: self._export_pendency_excel(summary_data),
                                   fg_color="#108842", hover_color="#1A994C")
        export_btn.pack(side="right")

        # Table
        cols = ["SL NO", "Panchayat", "Total Pending", "T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8+"]
        tree = ttk.Treeview(win, columns=cols, show='headings')
        
        for col in cols:
            tree.heading(col, text=col)
            width = 150 if col == "Panchayat" else 60
            tree.column(col, width=width, anchor="center")
            
        tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        scrollbar = ctk.CTkScrollbar(win, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 10))
        
        # Populate Table
        sorted_panchayats = sorted(summary_data.keys())
        
        grand_totals = {key: 0 for key in ["Total", "T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]}

        for idx, panch in enumerate(sorted_panchayats):
            row = summary_data[panch]
            # Calculate total for this row
            row_total = sum(row[f"T{i}"] for i in range(9))
            
            # Update Grand Totals
            grand_totals["Total"] += row_total
            for i in range(9):
                grand_totals[f"T{i}"] += row[f"T{i}"]

            values = (
                idx + 1,
                panch, row_total,
                row["T0"], row["T1"], row["T2"], row["T3"],
                row["T4"], row["T5"], row["T6"], row["T7"], row["T8"]
            )
            tree.insert("", "end", values=values)

        # Add Total Row in UI
        total_values = (
            "", "TOTAL", grand_totals["Total"],
            grand_totals["T0"], grand_totals["T1"], grand_totals["T2"], grand_totals["T3"],
            grand_totals["T4"], grand_totals["T5"], grand_totals["T6"], grand_totals["T7"], grand_totals["T8"]
        )
        total_item = tree.insert("", "end", values=total_values, tags=('total_row',))
        tree.tag_configure('total_row', background='#FFFF00', foreground='black', font=("Arial", 10, "bold"))
            
        self.style_treeview(tree)

    def _process_pendency_data(self, tree_items):
        """Parses tree items to count days pending."""
        summary = {} # { "PanchayatName": {T0:0, T1:0... seen_mrs: set()} }
        
        # Regex to find number of days: "since 5 days"
        regex = re.compile(r'since\s+(\d+)\s*(?:days|day)', re.IGNORECASE)

        for item_id in tree_items:
            values = self.results_tree.item(item_id, 'values')
            if not values: continue
            
            panchayat = values[1]
            mr_no = values[2]
            full_text = f"{values[7]} {values[12]} {values[13]}"
            
            match = regex.search(full_text)
            if not match: continue
                
            days_pending = int(match.group(1))
            
            if panchayat not in summary:
                summary[panchayat] = {f"T{i}": 0 for i in range(9)}
                summary[panchayat]["seen_mrs"] = set()
            
            if mr_no in summary[panchayat]["seen_mrs"]: continue
            
            summary[panchayat]["seen_mrs"].add(mr_no)
            
            if days_pending >= 8:
                summary[panchayat]["T8"] += 1
            else:
                summary[panchayat][f"T{days_pending}"] += 1
                
        return summary

    def _export_pendency_excel(self, summary_data):
        if not summary_data: return
        
        # 1. Prepare Data with SL NO and Calculation
        export_list = []
        sorted_keys = sorted(summary_data.keys())
        
        # Initialize Grand Totals
        grand_totals = [0] * 10 # 0=Total, 1=T0 ... 9=T8+
        
        for idx, panch in enumerate(sorted_keys):
            row = summary_data[panch]
            row_total = sum(row[f"T{i}"] for i in range(9))
            
            # Add to Grand Totals
            grand_totals[0] += row_total
            for i in range(9):
                grand_totals[i+1] += row[f"T{i}"]
                
            export_list.append([
                idx + 1,       # SL NO
                panch,         # Panchayat
                row_total,     # Total Pending
                row["T0"], row["T1"], row["T2"], row["T3"],
                row["T4"], row["T5"], row["T6"], row["T7"], row["T8"]
            ])
            
        columns = ["SL NO", "Panchayat", "Total Pending", "T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8+"]
        
        # File Dialog
        filename = f"Pendency_Report_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            initialdir=self.app.get_report_path("MR Tracking"),
            initialfile=filename,
            filetypes=[("Excel Files", "*.xlsx")]
        )
        if not save_path: return
        
        try:
            df = pd.DataFrame(export_list, columns=columns)
            
            # Formatting with OpenPyXL
            with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                sheet_name = 'Pendency'
                # Data starts from Row 2 (Row 1 is Header)
                df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1)
                
                wb = writer.book
                ws = writer.sheets[sheet_name]
                
                # --- Styles Definition ---
                # 1. Header Style (Dark Blue, White Text)
                header_fill = PatternFill(start_color="17365D", end_color="17365D", fill_type="solid")
                header_font = Font(bold=True, color="FFFFFF", size=11)
                
                # 2. Total Row Style (Bright Yellow, Bold Black)
                total_row_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
                total_row_font = Font(bold=True, color="000000", size=11)
                
                # 3. Column Specific Tints
                t0_t2_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid") # Light Yellow
                t3_t5_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Light Green
                t6_t7_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid") # Light Pink
                
                # 4. Critical Alert (Red BG, White Text)
                red_alert_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                red_alert_font = Font(bold=True, color="FFFFFF")
                
                # Borders & Alignment
                thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                     top=Side(style='thin'), bottom=Side(style='thin'))
                center_align = Alignment(horizontal="center", vertical="center")
                left_align = Alignment(horizontal="left", vertical="center")

                # --- APPLY HEADERS (Row 1 is Title, Row 2 is Headers) ---
                # Removed ws.insert_rows(1) because pandas startrow=1 already leaves Row 1 empty
                ws.merge_cells('A1:L1')
                ws['A1'] = "PENDENCY REPORT (T0 - T8+)"
                ws['A1'].font = Font(size=14, bold=True, color="FFFFFF")
                ws['A1'].fill = header_fill
                ws['A1'].alignment = center_align

                # Apply Header Style to Row 2
                for cell in ws[2]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = center_align
                    cell.border = thin_border

                # --- APPLY DATA ROWS & CONDITIONAL FORMATTING ---
                data_start = 3
                last_data_row = data_start + len(export_list) - 1
                
                for row_idx, row in enumerate(ws.iter_rows(min_row=data_start, max_row=last_data_row, min_col=1, max_col=12)):
                    for cell in row:
                        cell.border = thin_border
                        
                        # SL NO and Panchayat
                        if cell.column == 1: # SL NO
                            cell.alignment = center_align
                        elif cell.column == 2: # Panchayat
                            cell.alignment = left_align
                            cell.font = Font(bold=True)
                        else:
                            cell.alignment = center_align
                            
                            # Base Colors for Columns (T0-T8)
                            if 4 <= cell.column <= 6: # T0, T1, T2
                                cell.fill = t0_t2_fill
                            elif 7 <= cell.column <= 9: # T3, T4, T5
                                cell.fill = t3_t5_fill
                            elif 10 <= cell.column <= 11: # T6, T7
                                cell.fill = t6_t7_fill
                                
                            # Critical Overrides (T8+ is Column 12)
                            val = cell.value
                            if val and isinstance(val, (int, float)) and val > 0:
                                if cell.column == 12: # T8+
                                    cell.fill = red_alert_fill
                                    cell.font = red_alert_font
                                elif 10 <= cell.column <= 11: # T6, T7 highlight
                                    cell.font = Font(bold=True, color="C00000") # Dark Red Text

                # --- ADD TOTAL ROW AT BOTTOM ---
                total_row_idx = last_data_row + 1
                ws.cell(row=total_row_idx, column=1).value = "" # No SL NO
                ws.cell(row=total_row_idx, column=2).value = "TOTAL"
                
                # Fill Totals
                for i, total_val in enumerate(grand_totals):
                    # grand_totals indices: 0=TotalPending, 1=T0... 
                    # Excel Columns: 3=TotalPending, 4=T0...
                    ws.cell(row=total_row_idx, column=i+3).value = total_val

                # Style Total Row
                for cell in ws[total_row_idx]:
                    cell.fill = total_row_fill
                    cell.font = total_row_font
                    cell.alignment = center_align
                    cell.border = thin_border

                # --- COLUMN WIDTHS ---
                ws.column_dimensions['A'].width = 8  # SL NO
                ws.column_dimensions['B'].width = 25 # Panchayat
                ws.column_dimensions['C'].width = 12 # Total
                for col_char in ['D','E','F','G','H','I','J','K','L']:
                    ws.column_dimensions[col_char].width = 8

            messagebox.showinfo("Success", f"Report saved successfully:\n{save_path}")
            try:
                os.startfile(save_path) if os.name == 'nt' else subprocess.call(['open', save_path])
            except Exception as e: logger.debug("MRTracking: Could not open file: %s", e)
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save Excel:\n{e}")

    # --- END PENDENCY REPORT FEATURE ---

    # --- HELPER METHOD: Codes ko clean karne ke liye (Add this method) ---
    def get_clean_workcodes(self):
        """
        Returns a list of correctly formatted work codes (last 6 digits)
        extracted from the current results.
        """
        workcodes_raw = self.workcode_textbox.get("1.0", tkinter.END).strip()
        if not workcodes_raw: return []
        
        processed_list = []
        for code in workcodes_raw.splitlines():
            code = code.strip()
            # Agar code me '/' hai to split karke last 6 digit nikalo
            if code and "/" in code:
                try:
                    short_code = code.split('/')[-1][-6:]
                    processed_list.append(short_code)
                except Exception as e:
                    logger.debug("MRTracking: Could not parse code: %s", e)
            elif code:
                # Agar simple code hai to waisa hi lelo
                processed_list.append(code)
        
        # Duplicates hata kar list return karo
        return list(set(processed_list))

    # --- UPDATED RUN METHODS (Replace existing ones with these) ---

    def _run_mr_payment(self):
        """Send clean codes to MR Payment tab"""
        clean_codes = self.get_clean_workcodes()
        panchayat_name = self.panchayat_var.get().strip()

        if not clean_codes:
            messagebox.showwarning("No Data", "No valid workcodes found to transfer.", parent=self)
            return
        
        # List ko string bana kar bhejo, taaki old logic bhi support kare
        final_workcodes = "\n".join(clean_codes)
        self.app.switch_to_msr_tab_with_data(final_workcodes, panchayat_name)

    def _run_emb_entry(self):
        """Send clean codes to eMB Entry tab"""
        clean_codes = self.get_clean_workcodes()
        panchayat_name = self.panchayat_var.get().strip()

        if not clean_codes:
            messagebox.showwarning("No Data", "No valid workcodes found.", parent=self)
            return

        final_workcodes = "\n".join(clean_codes)
        self.app.switch_to_emb_entry_with_data(final_workcodes, panchayat_name)

    def _run_zero_mr(self):
        """Send clean codes to Zero MR tab"""
        if not hasattr(self, 'zero_mr_data') or not self.zero_mr_data:
            messagebox.showwarning("No Data", "No Zero MR data found.", parent=self)
            return
            
        # Logic to clean Zero MR data
        processed_data = []
        for item in self.zero_mr_data:
            # Code clean karo
            original = item['work_code']
            short_wc = original.split('/')[-1][-6:] if "/" in original else original
            
            processed_data.append({
                "panchayat": item['panchayat'], 
                "work_code": short_wc, 
                "msr_no": item['msr_no']
            })
            
        self.app.switch_to_zero_mr_tab_with_data(processed_data)

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

    def export_report(self):
        """Export results to professional Excel."""
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "There are no results to export.")
            return
            
        panchayat = self.panchayat_var.get().strip() or "Report"
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', panchayat) 
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        title = f"MR Tracking Report Panchayat - {panchayat}"
        
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"MR_Tracking_{safe_panchayat}-{current_date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=title
        )

    def _export_abps_report(self):
        """Export ABPS results to professional Excel."""
        if not self.abps_results_tree.get_children():
            messagebox.showinfo("No Data", "There are no ABPS results to export.")
            return
            
        panchayat = self.panchayat_var.get().strip() or "Report"
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', panchayat) 
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        
        self.export_treeview_to_excel(
            tree=self.abps_results_tree,
            default_filename=f"ABPS_Pendency_{safe_panchayat}-{current_date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=f"ABPS Pendency Report - {panchayat}"
        )

    def generate_report_pdf(self, data, headers, col_widths, title, date_str, file_path):
        class PDFWithFooter(FPDF):
            def footer(self):
                self.set_y(-15) 
                try:
                    self.set_font(font_name, '', 8) 
                except NameError: 
                    self.set_font('Helvetica', '', 8) 
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
                self.set_xy(self.l_margin, -15)
                self.cell(0, 10, 'Report Generated by NregaBot.com', 0, 0, 'L')

        try:
            pdf = PDFWithFooter(orientation="L", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=15) 
            pdf.add_page()
            
            try:
                font_path_regular = resource_path("assets/fonts/NotoSansDevanagari-Regular.ttf")
                font_path_bold = resource_path("assets/fonts/NotoSansDevanagari-Bold.ttf")
                pdf.add_font("NotoSansDevanagari", "", font_path_regular, uni=True)
                pdf.add_font("NotoSansDevanagari", "B", font_path_bold, uni=True)
                font_name = "NotoSansDevanagari"
            except RuntimeError:
                font_name = "Helvetica" 

            pdf.set_font(font_name, "B", 14) 
            pdf.cell(0, 10, title, 0, 1, "C")
            pdf.set_font(font_name, "", 10) 
            pdf.cell(0, 8, date_str, 0, 1, "R") 
            pdf.ln(4) 

            pdf.set_font(font_name, "B", 7) 
            pdf.set_fill_color(200, 220, 255)
            header_height = 8 
            
            if len(col_widths) != len(headers):
                self.log_warning("PDF Export Warning: Column width count mismatch.")
                col_widths = [(pdf.w - 2 * pdf.l_margin) / len(headers)] * len(headers)
                
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], header_height, header, 1, 0, "C", fill=True) 
            pdf.ln()

            pdf.set_font(font_name, "", 6) 
            line_height = 4 
            
            for row_data in data:
                if len(row_data) != len(headers):
                    continue

                max_lines = 1
                for i, cell_text in enumerate(row_data):
                    lines = pdf.multi_cell(col_widths[i], line_height, str(cell_text), border=0, align='L', split_only=True)
                    current_lines = len(lines) if lines else 1 
                    if current_lines > max_lines: max_lines = current_lines
                
                row_height = line_height * max_lines
                
                if pdf.get_y() + row_height > pdf.page_break_trigger:
                    pdf.add_page()
                    pdf.set_font(font_name, "B", 7)
                    for i, header in enumerate(headers):
                         pdf.cell(col_widths[i], header_height, header, 1, 0, "C", fill=True)
                    pdf.ln()
                    pdf.set_font(font_name, "", 6) 

                y_start = pdf.get_y()
                x_start = pdf.l_margin 
                
                for i, cell_text in enumerate(row_data):
                    col_width = col_widths[i]
                    x_current = x_start + sum(col_widths[:i]) 
                    pdf.set_xy(x_current, y_start) 
                    pdf.multi_cell(col_width, line_height, str(cell_text), border=1, align='L', max_line_height=line_height) 
                
                pdf.set_y(y_start + row_height) 

            pdf.output(file_path)
            return True
        except Exception as e:
            messagebox.showerror("PDF Export Error", f"Could not generate PDF report.\nError: {e}", parent=self)
            return False

    def _wrap_text(self, text, font, max_width):
        """Helper to wrap text for Pillow."""
        if not text:
            return [""]
        words = text.split(' ')
        lines = []
        current_line = []
        for word in words:
            if font.getlength(' '.join(current_line + [word])) <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        return lines

    def save_inputs(self, inputs):
        """Saves non-sensitive inputs for this tab."""
        save_data = {
            'state': inputs.get('state'),
            'district': inputs.get('district'),
            'block': inputs.get('block'),
            'panchayat': inputs.get('panchayat')
        }
        try:
            self.app.history_manager.save_tab_inputs_batch("mr_tracking", save_data)
        except Exception as e:
            print(f"Error saving MR Tracking inputs: {e}")

    def load_inputs(self):
        """Loads saved inputs for this tab."""
        data = self.app.history_manager.get_tab_inputs("mr_tracking")
        if not data:
            return
        self.state_var.set(data.get('state', ''))
        self.district_var.set(data.get('district', ''))
        self.block_var.set(data.get('block', ''))
        self.panchayat_var.set(data.get('panchayat') or config.ALL_PANCHAYATS_LABEL)