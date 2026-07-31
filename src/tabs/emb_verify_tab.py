# tabs/emb_verify_tab.py
import subprocess
import sys
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time
from datetime import datetime
from src import config
from .base_tab import BaseAutomationTab

from src.utils import get_logger, truncate_workcode
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException, UnexpectedAlertPresentException  # noqa: F401


logger = get_logger()

class EmbVerifyTab(BaseAutomationTab):
    """
    A tab for automating the e-Measurement Book (eMB) verification process.
    """
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="emb_verify")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) 
        self._create_widgets()
    def _create_widgets(self) -> None:

        """Creates the user interface elements for the tab."""
        # ── Header card ──
        self._create_header_card(self, "🔍", "eMB Verify",
                                 "Verify eMB entries against the sanctioned amount for the selected Panchayat.",
                                 icon_key="emoji_emb_verify")

        # --- Top Frame for Configuration (bordered card) ---
        config_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                    border_color=("gray85", "gray30"))
        config_frame.grid(row=1, column=0, sticky='ew', padx=12, pady=6)
        config_frame.grid_columnconfigure(1, weight=1)

        # Panchayat input field
        ctk.CTkLabel(config_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=15, pady=15)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(config_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=15)
        
        # Verify Amount input field
        ctk.CTkLabel(config_frame, text="Verify Amount (₹):").grid(row=1, column=0, sticky='w', padx=15, pady=(0, 15))
        self.verify_amount_entry = ctk.CTkEntry(config_frame)
        self.verify_amount_entry.insert(0, "300")
        self.verify_amount_entry.grid(row=1, column=1, sticky='ew', padx=15, pady=(0, 15))

        # Action buttons (OUTSIDE the card)
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        
        # --- Bottom Frame for Data Tabs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        work_codes_tab = notebook.add("Work Codes")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)
        
        # --- Work Codes Tab Content ---
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1)
        
        wc_header_frame = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        ctk.CTkLabel(wc_header_frame, text="Enter Work Codes (one per line). Leave blank to process all.").pack(side="left", padx=5)
        
        clear_wc_button = ctk.CTkButton(wc_header_frame, text="Clear", width=80, command=lambda: self.work_codes_text.delete("1.0", "end"))
        clear_wc_button.pack(side="right", padx=(0, 5))
        
        # --- NEW: Added the Extract from Text button (using correct frame name) ---
        extract_button = ctk.CTkButton(wc_header_frame, text="Extract from Text", width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_codes_text))
        extract_button.pack(side='right', padx=(0, 5))
        # ---
        
        self.work_codes_text = ctk.CTkTextbox(work_codes_tab, height=150)
        self.work_codes_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)


        # --- Results Tab UI ---
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side='left')

        cols = ("Work Code", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Work Code", width=250); self.results_tree.column("Status", width=100, anchor='center'); self.results_tree.column("Details", width=350); self.results_tree.column("Timestamp", width=120, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)



    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        """Enable or disable UI elements based on automation state."""
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.verify_amount_entry.configure(state=state)
        self.work_codes_text.configure(state=state)
        self.export_button.configure(state=state)
    def reset_ui(self) -> None:
        """Resets the UI to its initial state."""
        if messagebox.askokcancel("Reset Form?", "This will clear all inputs and results. Continue?"):
            self.panchayat_var.set("")
            self.verify_amount_entry.delete(0, tkinter.END)
            self.verify_amount_entry.insert(0, "300")
            self.work_codes_text.delete("1.0", tkinter.END)
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
    def start_automation(self) -> None:
        """Validates inputs and starts the automation thread."""
        panchayat = self.panchayat_var.get().strip()
        verify_amount = self.verify_amount_entry.get().strip()
        
        if not panchayat or not verify_amount:
            messagebox.showwarning("Input Error", "Panchayat Name and Verify Amount are required.")
            return

        work_codes = [line.strip() for line in self.work_codes_text.get("1.0", "end-1c").splitlines() if line.strip()]
        
        self.app.update_history("location_panchayat", panchayat)
        for wc in work_codes:
            self.app.update_history("work_code", wc)

        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(panchayat, verify_amount, work_codes))

    def _log_result(self, work_code, status, details):
        """Logs a result to the treeview with professional status tracking."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        work_code = truncate_workcode(work_code)
        status_lower = status.lower()
        tags = ('success',) if 'success' in status_lower or 'verified' in status_lower else ()
        if 'fail' in status_lower or 'rejected' in status_lower or 'error' in status_lower:
            tags = ('failed',)
        self.safe_tree_insert((work_code, status, details, timestamp), tags)

    def _show_emb_summary(self, total_work):
        """Show professional summary after eMB verification finishes."""
        if not self._is_alive():
            return
        success = sum(1 for item in self.results_tree.get_children() if 'success' in str(self.results_tree.item(item)['values'][1]).lower() or 'verified' in str(self.results_tree.item(item)['values'][1]).lower())
        failed = total_work - success
        summary = f"✅ Verified: {success}\n❌ Failed/Rejected: {failed}\n📊 Total: {total_work}"
        self.update_status(f"✅ {success}/{total_work} verified", 1.0)
        self.log_info(f"\n{'='*40}\n📊 eMB Verification Summary\n{summary}\n{'='*40}")
        if total_work > 0:
            self.log_info(f"\n📊 eMB Verification Complete: {summary}")

    def run_automation_logic(self, panchayat, verify_amount, work_codes_from_ui):
        """The main logic for the eMB verification automation."""
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.safe_tree_clear()
        self.log_info(f"Starting eMB Verification for Panchayat: {panchayat}")
        self.app.after(0, self.app.set_status, "Running eMB Verification...")
        total = 0

        try:
            driver = self.app.get_driver()
            if not driver: return

            driver.get(config.EMB_VERIFY_CONFIG["url"])
            wait = WebDriverWait(driver, 20) 

            self.log_info(f"Selecting Panchayat: {panchayat}")
            panchayat_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_panch"))))
            self._select_by_text_case_insensitive(panchayat_select, panchayat)
            
            self.log_info("Waiting for page to reload...")
            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work")))
            time.sleep(1.5)  # Brief wait for postback to begin
            self.log_info("Page reloaded successfully.")
            
            work_codes_to_process = []
            use_search = bool(work_codes_from_ui)

            if use_search:
                work_codes_to_process = work_codes_from_ui
                self.log_info(f"Processing {len(work_codes_to_process)} work codes from input.")
            else:
                self.log_info("No work codes provided. Fetching all from dropdown...")
                work_code_select_element = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work"))))
                work_codes_to_process = [opt.text for opt in work_code_select_element.options if opt.get_attribute('value')]
                if not work_codes_to_process:
                    self.log_warning("No work codes found for this Panchayat.")
                    self._log_result("N/A", "Skipped", "No work codes found.")
            
            total = len(work_codes_to_process)
            for i, current_wc in enumerate(work_codes_to_process):
                if self.is_stopped():
                    self.log_warning("⏹️ Automation stopped by user.")
                    break
                
                pct = (i + 1) / total * 100
                self.log_info(f"  🔄 [{i+1}/{total}] Verifying: {truncate_workcode(current_wc)} ({pct:.0f}%)")
                self.app.after(0, self.update_status, f"Processing {i+1}/{total}: {current_wc}", (i+1)/total)
                self._process_single_work_code(driver, wait, current_wc, use_search, verify_amount)

                if use_search and i < total - 1:
                    self.log_info("Navigating back for next work code...")
                    driver.get(config.EMB_VERIFY_CONFIG["url"])
                    panchayat_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_panch"))))
                    self._select_by_text_case_insensitive(panchayat_select, panchayat)
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work")))
                    time.sleep(1.5)  # Brief wait for postback to begin

            # Queue summary on main thread after inserts are processed
            self.app.after(200, lambda: self._show_emb_summary(total))

        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror("Automation Error", f"An unexpected error occurred:\n\n{e}")
            # Still show summary if some results exist
            try:
                self.app.after(200, lambda: self._show_emb_summary(total))
            except Exception:
                pass

        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror("Automation Error", f"An unexpected error occurred:\n\n{e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _process_single_work_code(self, driver, wait, work_code, use_search, verify_amount):
        """Handles the logic for a single work code verification."""
        try:
            self.log_info(f"Selecting work code: {work_code}")
            work_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_work"))))
            
            found = False
            for option in work_select.options:
                if work_code in option.text:
                    work_select.select_by_visible_text(option.text)
                    found = True
                    break
            
            if not found:
                raise NoSuchElementException(f"Work code containing '{work_code}' not found in dropdown.")
            
            self.log_info("Work selected. Pausing for page to update...")
            time.sleep(1.5)  # Brief wait for postback to begin

            self.log_info("Selecting 'Musterroll Period Wise'.")
            period_radio_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_rbl_mustrolltype_0")))
            driver.execute_script("arguments[0].click();", period_radio_btn)
            
            self.log_info("Waiting for measurement periods to load...")
            period_dropdown_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddl_mperiod")))
            time.sleep(1.5)  # Brief wait for postback to begin

            period_select = Select(period_dropdown_element)
            if len(period_select.options) <= 1:
                self._log_result(work_code, "Skipped", "No measurement period available.")
                return
            period_select.select_by_index(1)
            
            self.log_info("Waiting for activity table to load...")
            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_grd_activitycomponent_ctl02_lbl_act_unitcost")))
            
            unit_cost = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_grd_activitycomponent_ctl02_lbl_act_unitcost").text.strip()
            wage_per_day = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_grd_activitycomponent_ctl02_lbl_wageperday").text.strip()

            self.log_info(f"Found Unit Cost: {unit_cost}, Wage Per Day: {wage_per_day} for {work_code}")

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)

            if unit_cost == verify_amount and wage_per_day == verify_amount:
                self._find(driver, By.ID, "ctl00_ContentPlaceHolder1_btn_verify").click()
                self._log_result(work_code, "Verified", f"Unit Cost & Wage were correct ({verify_amount}).")
            else:
                rejection_reason = "unit cost is not correct"
                self.log_warning(f"Rejecting. Unit Cost: {unit_cost}, Wage: {wage_per_day}")
                self._find(driver, By.ID, "ctl00_ContentPlaceHolder1_txt_rejection_reason").send_keys(rejection_reason)
                self._find(driver, By.ID, "ctl00_ContentPlaceHolder1_btn_reject").click()
                self._log_result(work_code, "Rejected", f"Unit Cost: {unit_cost}, Wage: {wage_per_day}. Reason sent.")

            try:
                final_alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                self.log_info(f"Confirmation: {final_alert.text}")
                final_alert.accept()
            except TimeoutException:
                self.log_info("No final confirmation alert appeared.")

        except UnexpectedAlertPresentException as e:
            try:
                alert = driver.switch_to.alert
                self._log_result(work_code, "Failed", f"Unexpected Alert: {alert.text}")
                alert.accept()
            except Exception as e: logger.warning("EmbVerify: Failed to dismiss alert: %s", e)
        except (TimeoutException, NoSuchElementException) as e:
            self._log_result(work_code, "Failed", f"Could not find a required element or work code not found.")
            self.log_error(f"Error details: {e}")
        except Exception as e:
            self._log_result(work_code, "Error", f"An unexpected error occurred: {e}")

    def export_report(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="emb_verify_results.xlsx",
            filter_mode="Export All",
            title_prefix="eMB Verification Report"
        )
