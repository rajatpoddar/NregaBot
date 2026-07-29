# tabs/mate_mr_gen_tab.py
# Automation for Mate/Mistri (Skilled/Semi-Skilled) Muster Roll generation.
# Mirrors the regular MR gen flow but clicks the Skilled/Semi-Skilled checkbox
# and fills the "No. of workers can fit in one Muster roll form" field.

import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, json, time, base64, sys, subprocess, threading
from datetime import datetime
from pypdf import PdfWriter
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from src import config
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple

from ._imports import *  # noqa: F403,F401


class MateMrGenTab(BaseAutomationTab):
    """Generates Mate/Mistri (Skilled/Semi-Skilled) blank muster rolls."""

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="mate_mr")
        self.config_file = self.app.get_data_path("mate_mr_inputs.json")

        self.success_count = 0
        self.skipped_count = 0
        self.output_dir = ""
        self.current_session_files = []
        self.panchayat_after_id = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._create_widgets()
        self.load_inputs()

    #  UI Construction                                                     #
    def _create_widgets(self) -> None:
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        controls_frame.grid_columnconfigure((1, 3), weight=1)

        # Row 0 – Panchayat
        ctk.CTkLabel(controls_frame, text="Panchayat Name:").grid(
            row=0, column=0, sticky='w', padx=15, pady=(15, 0))
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=0, column=1, columnspan=3, sticky='ew', padx=15, pady=(15, 0))



        # Row 2 – Dates
        ctk.CTkLabel(controls_frame, text="तारीख से (DD/MM/YYYY):").grid(
            row=2, column=0, sticky='w', padx=15, pady=5)
        start_date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        start_date_frame.grid(row=2, column=1, sticky='ew', padx=(15, 5), pady=5)
        self.start_date_entry = ctk.CTkEntry(start_date_frame, placeholder_text="DD/MM/YYYY")
        self.start_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            start_date_frame, text="📅", width=30,
            fg_color=("gray85", "gray25"), text_color=("black", "white"),
            command=lambda: self.open_date_picker(
                lambda d: [self.start_date_entry.delete(0, "end"), self.start_date_entry.insert(0, d)])
        ).pack(side="right", padx=(5, 0))

        ctk.CTkLabel(controls_frame, text="तारीख को (DD/MM/YYYY):").grid(
            row=2, column=2, sticky='w', padx=10, pady=5)
        end_date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        end_date_frame.grid(row=2, column=3, sticky='ew', padx=(5, 15), pady=5)
        self.end_date_entry = ctk.CTkEntry(end_date_frame, placeholder_text="DD/MM/YYYY")
        self.end_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            end_date_frame, text="📅", width=30,
            fg_color=("gray85", "gray25"), text_color=("black", "white"),
            command=lambda: self.open_date_picker(
                lambda d: [self.end_date_entry.delete(0, "end"), self.end_date_entry.insert(0, d)])
        ).pack(side="right", padx=(5, 0))

        # Row 3 – No. of MRs to print & Workers per MR
        ctk.CTkLabel(controls_frame, text="No. of MRs to Print:").grid(
            row=3, column=0, sticky='w', padx=15, pady=5)
        self.num_mr_entry = ctk.CTkEntry(controls_frame, placeholder_text="e.g. 5")
        self.num_mr_entry.grid(row=3, column=1, sticky='ew', padx=(15, 5), pady=5)

        ctk.CTkLabel(controls_frame, text="Workers per MR Form:").grid(
            row=3, column=2, sticky='w', padx=10, pady=5)
        self.workers_per_mr_entry = ctk.CTkEntry(
            controls_frame, placeholder_text="e.g. 10")
        self.workers_per_mr_entry.grid(row=3, column=3, sticky='ew', padx=(5, 15), pady=5)

        # Row 4 – Output action
        ctk.CTkLabel(controls_frame, text="Output Action:").grid(
            row=4, column=0, sticky='w', padx=15, pady=5)
        self.output_action_var = ctk.StringVar(value="Save as PDF")
        self.output_action_menu = ctk.CTkOptionMenu(
            controls_frame, variable=self.output_action_var, values=["Save as PDF", "Print"])
        self.output_action_menu.grid(row=4, column=1, sticky='ew', padx=(15, 5), pady=5)

        # Row 5 – Orientation & Scale
        ctk.CTkLabel(controls_frame, text="Orientation:").grid(
            row=5, column=0, sticky='w', padx=15, pady=5)
        self.orientation_var = ctk.StringVar(value="Landscape")
        self.orientation_segmented_button = ctk.CTkSegmentedButton(
            controls_frame, variable=self.orientation_var, values=["Landscape", "Portrait"])
        self.orientation_segmented_button.grid(row=5, column=1, sticky='ew', padx=(15, 5), pady=5)

        ctk.CTkLabel(controls_frame, text="PDF Scale:").grid(
            row=5, column=2, sticky='w', padx=10, pady=5)
        scale_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        scale_frame.grid(row=5, column=3, sticky="ew", padx=(5, 15), pady=5)
        scale_frame.grid_columnconfigure(0, weight=1)
        self.scale_slider = ctk.CTkSlider(
            scale_frame, from_=50, to=100, number_of_steps=50, command=self._update_scale_label)
        self.scale_slider.set(75)
        self.scale_slider.grid(row=0, column=0, sticky="ew")
        self.scale_label = ctk.CTkLabel(scale_frame, text="75%", width=40)
        self.scale_label.grid(row=0, column=1, padx=(10, 0))

        ctk.CTkLabel(
            controls_frame,
            text="ℹ️ Mate/Mistri MRs saved in 'Downloads/NregaBot/MateMR_Output'.",
            text_color="gray50"
        ).grid(row=6, column=0, columnspan=4, sticky='e', padx=15, pady=(5, 15))

        # Action buttons row
        action_frame_container = ctk.CTkFrame(self)
        action_frame_container.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        action_frame = self._create_action_buttons(parent_frame=action_frame_container)
        action_frame.pack(expand=True, fill='x')

        # Notebook – Work codes + Results + Log
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        work_codes_tab = data_notebook.add("Work Search Keys (or auto)")
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # Work codes tab
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1)
        wc_controls = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_controls.grid(row=0, column=0, sticky='ew')
        ctk.CTkButton(
            wc_controls, text="Clear", width=80,
            command=lambda: self.work_codes_text.delete("1.0", tkinter.END)
        ).pack(side='right', pady=(5, 0), padx=(0, 5))
        ctk.CTkButton(
            wc_controls, text="Extract from Text", width=120,
            command=lambda: self._extract_and_update_workcodes(self.work_codes_text)
        ).pack(side='right', pady=(5, 0), padx=(0, 5))
        self.work_codes_text = ctk.CTkTextbox(work_codes_tab, height=100)
        self.work_codes_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # Results tab
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(2, weight=1)

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10), padx=5)
        self.merge_pdfs_button = ctk.CTkButton(
            results_action_frame, text="Merge Saved PDFs", command=self.merge_saved_pdfs)
        self.merge_pdfs_button.pack(side='left', padx=(0, 10))

        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(
            export_controls_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side='left')

        summary_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        summary_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        summary_frame.grid_columnconfigure((0, 1), weight=1)
        self.success_label = ctk.CTkLabel(
            summary_frame, text="Success: 0",
            text_color="#2E8B57", font=ctk.CTkFont(weight="bold"))
        self.success_label.grid(row=0, column=0, sticky='w')
        self.skipped_label = ctk.CTkLabel(
            summary_frame, text="Skipped/Failed: 0",
            text_color="#DAA520", font=ctk.CTkFont(weight="bold"))
        self.skipped_label.grid(row=0, column=1, sticky='w')

        cols = ("Timestamp", "Work Code/Key", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=80, anchor='center')
        self.results_tree.column("Work Code/Key", width=250)
        self.results_tree.column("Status", width=100, anchor='center')
        self.results_tree.column("Details", width=400)
        self.results_tree.grid(row=2, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=2, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)

    #  UI Helpers                                                          #


    def _update_scale_label(self, value):
        self.scale_label.configure(text=f"{int(value)}%")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        for widget in (
            self.panchayat_menu, self.start_date_entry, self.end_date_entry,
            self.orientation_segmented_button, self.scale_slider,
            self.output_action_menu, self.work_codes_text,
            self.num_mr_entry, self.workers_per_mr_entry,
            self.export_button, self.export_format_menu,
            self.export_filter_menu, self.merge_pdfs_button,
        ):
            widget.configure(state=state)
        if state == "normal":
            self._on_format_change(self.export_format_menu.get())

    #  Persist / restore inputs                                           #
    def save_inputs(self, inputs):
        try:
            to_save = {k: v for k, v in inputs.items()
                       if k not in ('work_codes_raw', 'work_codes', 'auto_mode')}
            self.app.history_manager.save_tab_inputs_batch("mate_mr", to_save)
        except Exception as e:
            print(f"Error saving inputs: {e}")

    def load_inputs(self):
        data = self.app.history_manager.get_tab_inputs("mate_mr")
        if data:
            self.panchayat_var.set(data.get('panchayat', ''))
            self.start_date_entry.delete(0, "end")
            self.start_date_entry.insert(0, data.get('start_date', ''))
            self.end_date_entry.delete(0, "end")
            self.end_date_entry.insert(0, data.get('end_date', ''))
            self.num_mr_entry.delete(0, "end")
            self.num_mr_entry.insert(0, data.get('num_mr', ''))
            self.workers_per_mr_entry.delete(0, "end")
            self.workers_per_mr_entry.insert(0, data.get('workers_per_mr', ''))
            self.orientation_var.set(data.get('orientation', 'Landscape'))
            self.scale_slider.set(float(data.get('scale', 75)))
            self._update_scale_label(self.scale_slider.get())
            self.output_action_var.set(data.get('output_action', 'Save as PDF'))

    #  Results helpers                                                     #
    def _log_result(self, item_key, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (timestamp, item_key, status, details)
        tags = ('success',) if 'success' in status.lower() else ('failed',)
        if status == "Success":
            self.success_count += 1
            self.app.after(0, lambda: self.success_label.configure(
                text=f"Success: {self.success_count}"))
        else:
            self.skipped_count += 1
            self.app.after(0, lambda: self.skipped_label.configure(
                text=f"Skipped/Failed: {self.skipped_count}"))
        self.safe_tree_insert(values, tags)

    #  Automation entry point                                             #
    def start_automation(self) -> None:
        self.safe_tree_clear()
        self.success_count, self.skipped_count = 0, 0
        self.current_session_files = []
        self.success_label.configure(text="Success: 0")
        self.skipped_label.configure(text="Skipped/Failed: 0")

        inputs = {
            'panchayat':      self.panchayat_var.get().strip(),
            'start_date':     self.start_date_entry.get().strip(),
            'end_date':       self.end_date_entry.get().strip(),
            'num_mr':         self.num_mr_entry.get().strip(),
            'workers_per_mr': self.workers_per_mr_entry.get().strip(),
            'orientation':    self.orientation_var.get(),
            'scale':          self.scale_slider.get(),
            'output_action':  self.output_action_var.get(),
            'work_codes_raw': self.work_codes_text.get("1.0", tkinter.END).strip(),
        }

        required = ['start_date', 'end_date', 'workers_per_mr']
        if not all(inputs[k] for k in required):
            messagebox.showwarning(
                "Input Error",
                "Dates and Workers per MR Form are required.")
            return

        # Work codes box must not be empty (auto mode is not allowed without work codes)
        if not inputs['work_codes_raw'].strip():
            messagebox.showwarning(
                "Input Error",
                "Work Search Keys box is empty.\nPlease enter at least one work code or search key.")
            return

        if not inputs['workers_per_mr'].isdigit():
            messagebox.showwarning("Input Error", "'Workers per MR Form' must be a number.")
            return

        if inputs['num_mr'] and not inputs['num_mr'].isdigit():
            messagebox.showwarning("Input Error", "'No. of MRs to Print' must be a number.")
            return

        self.app.update_history("location_panchayat", inputs['panchayat'])
        inputs['work_codes'] = [
            line.strip() for line in inputs['work_codes_raw'].split('\n') if line.strip()]
        inputs['auto_mode'] = not bool(inputs['work_codes'])
        self.save_inputs(inputs)
        self.app.start_automation_thread(
            self.automation_key, self.run_automation_logic, args=(inputs,))
    def retry_logic_handler(self) -> None:
        failed_items = []
        for item_id in self.results_tree.get_children():
            values = self.results_tree.item(item_id)['values']
            if "success" not in str(values[2]).lower():
                failed_items.append(str(values[1]))
        if not failed_items:
            messagebox.showinfo("Retry", "No failed items found to retry.")
            return
        if not messagebox.askyesno(
                "Retry Failed",
                f"Found {len(failed_items)} failed/skipped items.\nLoad them and retry?"):
            return
        self.work_codes_text.configure(state="normal")
        self.work_codes_text.delete("1.0", tkinter.END)
        self.work_codes_text.insert("1.0", "\n".join(failed_items))
        self.work_codes_text.configure(state="disabled")
        self.safe_tree_clear()
        self.success_count = self.skipped_count = 0
        self.update_status("Retrying failed items...", 0.0)
        self.start_automation()
    def reset_ui(self) -> None:
        if messagebox.askokcancel("Reset Form?", "Clear all inputs and logs?"):
            self.panchayat_var.set("")
            self.start_date_entry.delete(0, "end")
            self.end_date_entry.delete(0, "end")
            self.num_mr_entry.delete(0, "end")
            self.workers_per_mr_entry.delete(0, "end")
            self.orientation_var.set('Landscape')
            self.scale_slider.set(75)
            self.scale_label.configure(text="75%")
            self.output_action_var.set('Save as PDF')
            self.work_codes_text.delete('1.0', tkinter.END)
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.success_label.configure(text="Success: 0")
            self.skipped_label.configure(text="Skipped/Failed: 0")
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    #  Output directory                                                   #
    def _get_output_dir(self, location_panchayat):
        try:
            safe = "".join(c for c in location_panchayat if c.isalnum() or c in (' ', '_')).rstrip()
            if not safe:
                safe = "Unknown_Panchayat"
            date_str = datetime.now().strftime('%Y-%m-%d')
            output_dir = os.path.join(
                self.app.get_nregabot_path("MateMR_Output"), safe, date_str)
            os.makedirs(output_dir, exist_ok=True)
            return output_dir
        except Exception as e:
            self.log_error(f"Error creating output directory: {e}")
            messagebox.showerror("Directory Error", f"Could not create output directory: {e}")
            return None

    #  Automation logic (runs in thread)                                  #
    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.log_info(f"Starting Mate/Mistri MR generation for: {inputs['panchayat'] or '(Panchayat not specified)'}")
        self.app.after(0, self.app.set_status, "Running Mate/Mistri MR Generation...")

        self.output_dir = self._get_output_dir(inputs['panchayat'] or "MateMistri")
        if not self.output_dir:
            self.log_error("Failed to create output directory. Aborting.")
            self.app.after(0, self.set_ui_state, False)
            return

        try:
            driver = self.app.get_driver()
            if not driver:
                self.app.after(0, self.set_ui_state, False)
                return
            wait = WebDriverWait(driver, 20)

            self.log_info(f"Output will be in: {self.output_dir}")

            if not self._validate_panchayat(driver, wait, inputs['panchayat']):
                self.app.after(0, self.set_ui_state, False)
                return

            self.app.update_history("location_panchayat", inputs['panchayat'])

            items_to_process = self._get_items_to_process(driver, wait, inputs)
            session_skip_list = set()
            total_items = len(items_to_process)

            for index, item in enumerate(items_to_process):
                if self.is_stopped():
                    self.log_warning("Stop signal received.")
                    break
                self.log_info(f"Processing item ({index + 1}/{total_items}): {item}")
                self.app.after(
                    0, self.update_status,
                    f"Processing {item}", (index + 1) / total_items)
                self._process_single_item(
                    driver, wait, inputs, item, self.output_dir, session_skip_list)

        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror(
                "Critical Error",
                f"An unexpected error stopped the automation.\n\nError: {e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished.", 1.0)
            self.app.after(100, self._show_completion_dialog, self.output_dir)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _show_completion_dialog(self, output_dir):
        summary = (f"Automation complete.\n"
                   f"Success: {self.success_count}\n"
                   f"Skipped/Failed: {self.skipped_count}")
        if "macro" in self.app.active_automations:
            self.log_info(f"Batch Finished. Output: {output_dir}")
            return
        if self.success_count > 0 and output_dir and os.path.exists(output_dir):
            if messagebox.askyesno("Task Finished",
                                   f"{summary}\n\nOpen the output folder?"):
                self.app.open_folder(output_dir)
        else:
            self.log_info(f"📊 {summary}")
    #  Panchayat validation                                               #
    def _validate_panchayat(self, driver, wait, location_panchayat):
        """If location_panchayat is empty, skip validation and return True."""
        if not location_panchayat:
            self.log_info("Panchayat not provided — skipping validation.")
            return True
        try:
            self.log_info("Validating Panchayat name...")
            driver.get(config.MUSTER_ROLL_CONFIG["base_url"])
            panchayat_dropdown = Select(
                wait.until(EC.presence_of_element_located((By.ID, "exe_agency"))))
            target = config.AGENCY_PREFIX + location_panchayat
            if target not in [opt.text for opt in panchayat_dropdown.options]:
                err = (f"Panchayat '{location_panchayat}' not found on the portal. "
                       "Please check spelling.")
                if "macro" in self.app.active_automations:
                    self.log_error(f"Skipping: {err}")
                    return False
                messagebox.showerror("Validation Error", err)
                return False
            self.log_success("Panchayat name is valid.")
            return True
        except Exception as e:
            self.log_error(f"Validation failed: {e}")
            return False

    #  Items to process                                                    #
    def _get_items_to_process(self, driver, wait, inputs):
        """
        Auto mode  – click Skilled/Semi-Skilled checkbox, select panchayat,
                     then read all available work codes from ddlWorkCode.
        Manual mode – return provided search keys as-is.
        """
        if inputs['auto_mode']:
            self.log_info("Auto Mode: Fetching available work codes...")
            try:
                # Select panchayat (case-insensitive)
                agency_select = Select(driver.find_element(By.ID, "exe_agency"))
                self._select_by_text_case_insensitive(
                    agency_select, config.AGENCY_PREFIX + inputs['panchayat'])

                # Click Skilled/Semi-Skilled checkbox
                self._select_skilled_checkbox(driver, wait)

                wait.until(lambda d: len(
                    Select(d.find_element(By.ID, "ddlWorkCode")).options) > 1)
                items = [
                    opt.text
                    for opt in Select(driver.find_element(By.ID, "ddlWorkCode")).options
                    if opt.get_attribute("value")
                ]
                self.log_info(f"Found {len(items)} available work codes.")
                return items
            except Exception as e:
                self.log_error(f"Could not fetch work codes automatically: {e}")
                return []
        else:
            self.log_info(f"Processing {len(inputs['work_codes'])} provided work keys.")
            return inputs['work_codes']

    #  Skilled/Semi-Skilled checkbox helper                               #
    def _select_skilled_checkbox(self, driver, wait):
        """
        Ensures the 'Skilled/Semi-Skilled' radio/checkbox is selected.
        The page shows two Worker Category options: Unskilled (default) and
        Skilled/Semi-Skilled.  We locate by value or label and click if not
        already checked.
        """
        try:
            # Try by value attribute first (common pattern for these pages)
            skilled_cb = driver.find_element(
                By.XPATH,
                "//input[@type='radio' or @type='checkbox'][contains(@value,'Skilled') "
                "or contains(@value,'skilled') or contains(@value,'S')]"
                "[following-sibling::text()[contains(.,'Skilled')] "
                " or preceding-sibling::text()[contains(.,'Skilled')] "
                " or parent::*[contains(.,'Skilled')]]"
            )
        except NoSuchElementException:
            # Fallback: find by label text
            try:
                skilled_cb = driver.find_element(
                    By.XPATH,
                    "//label[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                    "'abcdefghijklmnopqrstuvwxyz'),'skilled')]"
                    "/preceding-sibling::input | "
                    "//label[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                    "'abcdefghijklmnopqrstuvwxyz'),'skilled')]"
                    "/following-sibling::input"
                )
            except NoSuchElementException:
                self.log_warning(
                    "   - Could not locate Skilled/Semi-Skilled checkbox. "
                    "Page may have changed.")
                return

        if not skilled_cb.is_selected():
            driver.execute_script("arguments[0].click();", skilled_cb)
            self.log_info("   - Clicked 'Skilled/Semi-Skilled' checkbox.")
            time.sleep(1)   # brief wait for any page reload triggered by the click
        else:
            self.log_info("   - 'Skilled/Semi-Skilled' already selected.")

    #  Single item processing                                             #
    def _process_single_item(self, driver, wait, inputs, item, output_dir, session_skip_list):
        full_work_code_text = ""
        try:
            self.log_info("   - Navigating to MR page...")
            driver.get(config.MUSTER_ROLL_CONFIG["base_url"])

            # 1. Select Panchayat (optional — skip if not provided)
            self.log_info("   - Selecting Panchayat...")
            if inputs['panchayat']:
                panchayat_dropdown = wait.until(
                    EC.presence_of_element_located((By.ID, "exe_agency")))
                self._select_by_text_case_insensitive(
                    Select(panchayat_dropdown), config.AGENCY_PREFIX + inputs['panchayat'])
            else:
                self.log_info("   - Panchayat not provided, skipping selection.")

            # 2. Select Skilled/Semi-Skilled worker category
            self.log_info("   - Selecting Skilled/Semi-Skilled category...")
            self._select_skilled_checkbox(driver, wait)

            # 3. Select Work Code
            self.log_info(f"   - Selecting work code for '{item}'...")
            full_work_code_text = self._select_work_code(
                driver, wait, item, inputs['auto_mode'])

            if full_work_code_text in session_skip_list:
                self._log_result(item, "Skipped", "Already processed in this session.")
                return

            # 4. Fill dates via JS (bypasses datepicker widget)
            self.log_info("   - Entering dates...")
            driver.execute_script(
                f"document.getElementById('txtDateFrom').value = '{inputs['start_date']}';")
            driver.execute_script(
                f"document.getElementById('txtDateTo').value = '{inputs['end_date']}';")

            # 5. Fill number of muster rolls to be printed (optional field)
            if inputs.get('num_mr'):
                try:
                    num_mr_field = wait.until(
                        EC.presence_of_element_located((By.ID, "txtnoofmsr")))
                    driver.execute_script(
                        "arguments[0].value = arguments[1]; "
                        "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                        num_mr_field, str(inputs['num_mr']))
                    self.log_info(f"   - Set No. of MRs to print: {inputs['num_mr']}")
                except (NoSuchElementException, TimeoutException):
                    self.log_warning("   - 'No. of MRs' field not found, skipping.")

            # 6. Fill number of workers per MR form (field ID: txtMsrPage)
            self.log_info(f"   - Setting workers per MR: {inputs['workers_per_mr']}...")
            try:
                workers_field = wait.until(
                    EC.presence_of_element_located((By.ID, "txtMsrPage")))
                driver.execute_script(
                    "arguments[0].removeAttribute('disabled'); "
                    "arguments[0].removeAttribute('readonly'); "
                    "arguments[0].value = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    workers_field, str(inputs['workers_per_mr']))
                self.log_info(f"   - Set Workers per MR: {inputs['workers_per_mr']}")
            except (TimeoutException, NoSuchElementException):
                self.log_warning("   - 'Workers per MR' field not found, skipping.")

            # 7. Submit
            self.log_info("   - Submitting form...")
            body_element = driver.find_element(By.TAG_NAME, 'body')
            btn_proceed = wait.until(
                EC.presence_of_element_located((By.ID, "btnProceed")))
            driver.execute_script("arguments[0].click();", btn_proceed)

            # Handle possible alert
            try:
                WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert_text = alert.text
                alert.accept()
                self._log_result(item, "Failed", f"Server Alert: {alert_text}")
                return
            except TimeoutException:
                pass

            wait.until(EC.staleness_of(body_element))

            # 9. Check known error messages
            error_reason = self._check_for_page_errors(driver)
            if error_reason:
                self._log_result(item, "Skipped", error_reason)
                session_skip_list.add(full_work_code_text)
                return

            # 10. Save PDF
            self.log_info("   - Muster Roll is valid. Generating PDF...")
            pdf_path = self._save_mr_as_pdf(
                driver, full_work_code_text, output_dir,
                inputs['orientation'], inputs['scale'])

            log_detail = (f"Saved as {os.path.basename(pdf_path)}"
                          if pdf_path else "PDF Save Failed")
            if pdf_path:
                self.current_session_files.append(pdf_path)

            if inputs['output_action'] == "Print" and pdf_path:
                self._print_file(pdf_path)

            self._log_result(item, "Success" if pdf_path else "Failed", log_detail)
            session_skip_list.add(full_work_code_text)

        except TimeoutException:
            self.log_error(f"Error on '{item}': Timeout (Slow Network)")
            self._log_result(item, "Failed", "Timeout - Slow Network")
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "Unknown Error"
            self.log_error(f"Error on '{item}': {error_msg}")
            self._log_result(item, "Failed", error_msg)

    #  Page error checker                                                 #
    def _check_for_page_errors(self, driver) -> str | None:
        src = driver.page_source.lower()
        if "skill semiskilled muster roll cannot be generated before unskilled" in src:
            return "Skipped: Unskilled MR not generated yet for this work code"
        if "geotag is not received" in src:
            return "Skipped: Geotag not received"
        if "greater than allowed limit" in src:
            return "Skipped: Greater than allowed limit"
        if "no worker available" in src:
            return "Skipped: No worker available"
        if "no muster roll available" in src:
            return "Skipped: No Muster Roll available"
        if "overlap that period" in src:
            return "Skipped: Date period overlaps with existing MR"
        return None

    #  Work code selection (manual / auto, with stale-element retry)     #
    def _select_work_code(self, driver, wait, item, is_auto_mode):
        work_code_locator = (By.ID, "ddlWorkCode")
        for attempt in range(3):
            try:
                if is_auto_mode:
                    wait.until(EC.presence_of_element_located(work_code_locator))
                    wait.until(lambda d: len(
                        Select(d.find_element(*work_code_locator)).options) > 1)
                    dd = Select(driver.find_element(*work_code_locator))
                    found = next(
                        (opt for opt in dd.options
                         if opt.text == item and opt.get_attribute("value")), None)
                    if found:
                        dd.select_by_visible_text(found.text)
                        self.log_info(f"   - Selected: {found.text}")
                        return found.text
                    raise NoSuchElementException(
                        f"Work '{item}' not found in dropdown.")
                else:
                    search_box = wait.until(
                        EC.presence_of_element_located((By.ID, "txtWork")))
                    driver.execute_script(
                        "arguments[0].value = arguments[1];", search_box, item)
                    old_dd = driver.find_element(*work_code_locator)
                    search_btn = driver.find_element(By.ID, "imgButtonSearch")
                    driver.execute_script("arguments[0].click();", search_btn)
                    try:
                        wait.until(EC.staleness_of(old_dd))
                    except TimeoutException:
                        pass
                    wait.until(EC.presence_of_element_located(work_code_locator))
                    wait.until(lambda d: len(
                        Select(d.find_element(*work_code_locator)).options) > 1)
                    dd = Select(driver.find_element(*work_code_locator))
                    found = next(
                        (opt for opt in dd.options
                         if item in opt.text and opt.get_attribute("value")), None)
                    if found:
                        dd.select_by_visible_text(found.text)
                        self.log_info(f"   - Selected: {found.text}")
                        return found.text
                    raise NoSuchElementException(
                        f"No work found for search key '{item}'.")
            except StaleElementReferenceException:
                if attempt < 2:
                    self.log_warning("   - Stale element, retrying...")
                    time.sleep(2)
                    continue
                raise
            except Exception:
                raise

    #  PDF save (identical to regular MR gen)                            #
    def _save_mr_as_pdf(self, driver, full_work_code, output_dir, orientation, scale):
        try:
            safe_code = full_work_code.split('/')[-1][-6:]
            base_filename = safe_code
            extension = ".pdf"
            counter = 1
            pdf_filename = f"{base_filename}{extension}"
            save_path = os.path.join(output_dir, pdf_filename)
            while os.path.exists(save_path):
                pdf_filename = f"{base_filename} ({counter}){extension}"
                save_path = os.path.join(output_dir, pdf_filename)
                counter += 1

            is_landscape = (orientation == "Landscape")
            pdf_scale = scale / 100.0
            pdf_data_base64 = None

            if is_landscape:
                driver.execute_script(
                    "var css = '@page { size: landscape; }';"
                    "var head = document.head || document.getElementsByTagName('head')[0];"
                    "var style = document.createElement('style');"
                    "style.type = 'text/css'; style.media = 'print';"
                    "if (style.styleSheet){ style.styleSheet.cssText = css; }"
                    "else { style.appendChild(document.createTextNode(css)); }"
                    "head.appendChild(style);"
                )

            # Remove blank pages
            driver.execute_script("""
                var styleTag = document.createElement('style');
                styleTag.innerHTML = `@media print {
                    * { page-break-after: auto !important; page-break-before: auto !important;
                        break-after: auto !important; break-before: auto !important; }
                    body::after { display: none !important; content: none !important; }
                }`;
                document.head.appendChild(styleTag);
                var bodyChildren = Array.from(document.body.children);
                for (var i = bodyChildren.length - 1; i >= 0; i--) {
                    var el = bodyChildren[i];
                    if (el.innerText.trim() === '' &&
                        el.querySelectorAll('img,input,table,iframe,canvas,video').length === 0) {
                        el.parentNode.removeChild(el);
                    } else { break; }
                }
                var allEls = document.querySelectorAll('*');
                allEls.forEach(function(el) {
                    el.style.pageBreakAfter = 'auto'; el.style.pageBreakBefore = 'auto';
                    el.style.breakAfter = 'auto'; el.style.breakBefore = 'auto';
                });
            """)

            if self.app.active_browser == 'firefox':
                driver.execute_script("""
                    var footer = document.createElement('div');
                    footer.innerText = 'NregaBot.com';
                    footer.style.cssText = 'position:fixed;bottom:0;right:0;padding:10px;'
                        + 'font-size:10px;color:#cccccc;font-family:Arial,sans-serif;z-index:9999;';
                    document.body.appendChild(footer);
                """)
                pdf_data_base64 = driver.print_page()

            elif self.app.active_browser == 'chrome':
                driver.execute_script("""
                    if (!document.getElementById('nregabot-footer')) {
                        var f = document.createElement('div');
                        f.id = 'nregabot-footer';
                        f.innerText = 'NregaBot.com';
                        f.style.cssText = 'position:fixed;bottom:6px;right:10px;'
                            + 'font-size:9px;color:#d3d3d3;font-family:Helvetica,sans-serif;z-index:9999;';
                        document.body.appendChild(f);
                    }
                """)
                result = driver.execute_cdp_cmd("Page.printToPDF", {
                    "landscape": is_landscape,
                    "displayHeaderFooter": False,
                    "printBackground": False,
                    "scale": pdf_scale,
                    "marginTop": 0.4, "marginBottom": 0.4,
                    "marginLeft": 0.4, "marginRight": 0.4,
                })
                pdf_data_base64 = result['data']

            if pdf_data_base64:
                with open(save_path, 'wb') as f:
                    f.write(base64.b64decode(pdf_data_base64))
                return save_path
            self.log_error("PDF data not generated.")
            return None

        except Exception as e:
            self.log_error(f"Error saving PDF: {e}")
            return None

    #  Print file                                                         #
    def _print_file(self, file_path):
        try:
            if not os.path.exists(file_path):
                self.log_error(f"Print Error: File not found at {file_path}")
                return
            if sys.platform == "win32":
                os.startfile(file_path, "print")
            else:
                subprocess.run(["lpr", file_path], check=True)
            self.log_info(f"Sent {os.path.basename(file_path)} to printer.")
            time.sleep(2)
        except Exception as e:
            msg = f"An unexpected error occurred while printing: {e}"
            self.log_error(msg)
            self.app.after(0, lambda: messagebox.showwarning("Print Error", msg))

    #  Export report                                                      #
    def export_report(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="mate_mr_gen_results.xlsx",
            filter_mode="Export All",
            title_prefix="Mate MR Generation Report"
        )

    def _get_filtered_data_and_filepath(self, export_format):
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "No results to export.")
            return None, None
        location_panchayat = self.panchayat_var.get().strip()
        if not location_panchayat:
            messagebox.showwarning("Input Needed", "Panchayat Name is required for report title.")
            return None, None

        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in self.results_tree.get_children():
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[2].upper()
            if filter_option == "Export All":
                data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status:
                data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status:
                data_to_export.append(row_values)

        if not data_to_export:
            messagebox.showinfo("No Data", f"No records for filter '{filter_option}'.")
            return None, None

        safe_name = "".join(
            c for c in location_panchayat if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        details = {
            "PDF (.pdf)": {"ext": ".pdf", "types": [("PDF Document", "*.pdf")]},
        }.get(export_format, {"ext": ".pdf", "types": [("PDF Document", "*.pdf")]})
        filename = f"MateMR_Report_{safe_name}_{timestamp}{details['ext']}"
        file_path = filedialog.asksaveasfilename(
            defaultextension=details['ext'],
            filetypes=details['types'],
            initialdir=self.app.get_nregabot_path("Reports"),
            initialfile=filename,
            title="Save Report")
        return (data_to_export, file_path) if file_path else (None, None)

    def _handle_pdf_export(self, data, headers, col_widths, file_path):
        title = f"Mate/Mistri MR Report: {self.panchayat_var.get().strip()}"
        report_date = datetime.now().strftime('%d %b %Y')
        success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
        if success and messagebox.askyesno(
                "Success", f"PDF saved to:\n{file_path}\n\nOpen it?"):
            if sys.platform == "win32":
                os.startfile(file_path)
            else:
                subprocess.call(['open', file_path])

    #  Merge saved PDFs                                                   #
    def merge_saved_pdfs(self):
        self.log_info("Starting PDF merge...")
        pdf_files = self.current_session_files
        if not pdf_files:
            self.log_warning("No PDFs generated in this session to merge.")
            messagebox.showinfo(
                "No Files",
                "No MRs have been successfully generated in this cycle yet.\n"
                "Run the automation first.", parent=self)
            return

        self.log_info(f"Merging {len(pdf_files)} files generated in this session.")

        dialog = ctk.CTkInputDialog(
            text="Enter a base name for the merged file:", title="Merge PDFs")
        base_name = dialog.get_input()
        if not base_name:
            self.log_info("Merge cancelled.")
            return

        try:
            merge_dir = self.app.get_nregabot_path("Merged_PDF")
            os.makedirs(merge_dir, exist_ok=True)
            date_str = datetime.now().strftime("%d-%b-%Y")
            file_name = f"{base_name}_{date_str}.pdf"
            output_path = os.path.join(merge_dir, file_name)
            count = 1
            while os.path.exists(output_path):
                file_name = f"{base_name}_{date_str}({count}).pdf"
                output_path = os.path.join(merge_dir, file_name)
                count += 1
        except Exception as e:
            messagebox.showerror("Path Error", f"Could not create merge path: {e}", parent=self)
            return

        self.app.start_automation_thread(
            "pdf_merger_mate_mr", self._run_merge_logic, args=(pdf_files, output_path))

    def _run_merge_logic(self, file_list, output_path):
        self.app.after(0, self.set_ui_state, True)
        self.log_info(f"Merging {len(file_list)} files...")
        self.app.after(0, self.app.set_status, "Merging PDFs...")
        try:
            merger = PdfWriter()
            for pdf_path in file_list:
                if self.app.stop_events.get(
                        "pdf_merger_mate_mr", threading.Event()).is_set():
                    self.log_warning("Merge cancelled.")
                    merger.close()
                    return
                merger.append(pdf_path)
            with open(output_path, "wb") as f_out:
                merger.write(f_out)
            merger.close()
            self.log_success("Merge complete!")
            messagebox.showinfo(
                "Success",
                f"Merged {len(file_list)} files into:\n{output_path}", parent=self)
            if messagebox.askyesno("Open Location?", "Open the Merged PDFs folder?", parent=self):
                self.app.open_folder(os.path.dirname(output_path))
        except Exception as e:
            self.log_error(f"Merge error: {e}")
            messagebox.showerror("Merge Error", f"An error occurred: {e}", parent=self)
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")
