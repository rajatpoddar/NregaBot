# tabs/abps_verify_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time
import os
import re
from datetime import datetime

from src import config
from .base_tab import BaseAutomationTab

from src.utils import get_logger
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, StaleElementReferenceException, TimeoutException  # noqa: F401


logger = get_logger()

# Dropdown label used when the user wants to process ALL villages
ALL_VILLAGES_LABEL = "🌐 All Villages"

class AbpsVerifyTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="abps_verify")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._create_widgets()
    def _create_widgets(self) -> None:

        # ── Header card ──
        self._create_header_card(self, "✅", "Verify ABPS",
                                 "Verify ABPS (UID-linked) accounts for jobcard holders in bulk.",
                                 icon_key="emoji_verify_abps")

        # --- Controls Frame ---
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        controls_frame.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=config.ALL_PANCHAYATS_LABEL)
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var,
                                                values=self._all_panchayat_values(p_vals))
        self.panchayat_menu.grid(row=0, column=1, sticky="ew", padx=(0, 15), pady=(15, 5))

        ctk.CTkLabel(controls_frame, text="Village:").grid(row=0, column=2, sticky="w", padx=15, pady=(15, 5))
        v_vals = self.app.history_manager.get_suggestions("location_village") or [""]
        self.village_var = ctk.StringVar(value=ALL_VILLAGES_LABEL)
        self.village_menu = ctk.CTkOptionMenu(controls_frame, variable=self.village_var,
                                              values=[ALL_VILLAGES_LABEL] + [v for v in v_vals if v])
        self.village_menu.grid(row=0, column=3, sticky="ew", padx=(0, 15), pady=(15, 5))

        # Filter villages when panchayat changes
        def _on_panchayat_change(*_):
            pan = self.panchayat_var.get()
            if pan:
                vals = self.app.history_manager.get_filtered_suggestions("location_village", "location_panchayat", pan) or []
            else:
                vals = self.app.history_manager.get_suggestions("location_village") or []
            self.village_var.set(ALL_VILLAGES_LABEL)
            self.village_menu.configure(values=[ALL_VILLAGES_LABEL] + [v for v in vals if v])
        self.panchayat_var.trace_add("write", _on_panchayat_change)

        # --- Note for auto-mode ---
        ctk.CTkLabel(controls_frame, text="💡 Select '🌐 All Panchayats' for all panchayats, '⭐ My Saved Panchayats' for only your saved panchayats, and '🌐 All Villages' for all villages of a panchayat.", text_color="gray50").grid(row=1, column=1, columnspan=3, sticky="w", padx=15, pady=(0, 15))

        # --- Action Buttons (OUTSIDE the card) ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        # --- Results and Logs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        results_frame = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)

        # Results Frame Configuration
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1) 

        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        
        # --- Export Buttons ---
        self.export_csv_button = ctk.CTkButton(results_action_frame, text="📥 Export to Excel",
                                               command=self._export_excel_report)
        self.export_csv_button.pack(side="left", padx=(0, 10))

        # NEW: PDF Export Button
        self.export_pdf_button = ctk.CTkButton(
            results_action_frame, 
            text="Export to PDF", 
            command=self.export_to_pdf, 
            fg_color=config.COLORS["orange_abps"], 
            hover_color=config.COLORS["orange_abps_hover"]
        )
        self.export_pdf_button.pack(side="left")

        cols = ("Panchayat", "Job Card No.", "Applicant Name", "Status", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        self.results_tree.column("Job Card No.", width=200)
        self.results_tree.column("Applicant Name", width=200)
        self.results_tree.column("Status", width=150, anchor='center')
        self.results_tree.column("Timestamp", width=100, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        
        # Style Treeview and configure tags
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.village_menu.configure(state=state)
        self.export_csv_button.configure(state=state)
        self.export_pdf_button.configure(state=state)
    def start_automation(self) -> None:
        panchayat = self.panchayat_var.get().strip()
        village = self.village_var.get().strip()
        if village == ALL_VILLAGES_LABEL:
            village = ""  # Process all villages
        if not panchayat:
            messagebox.showwarning("Input Required", "Please enter a Panchayat name.")
            return
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(panchayat, village))
    def reset_ui(self) -> None:
        if messagebox.askokcancel("Reset Form?", "Clear all inputs and logs?"):
            self.panchayat_var.set("")
            self.village_var.set(ALL_VILLAGES_LABEL)
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    def run_automation_logic(self, panchayat, village):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.safe_tree_clear()
        self.log_info("Starting ABPS Verification...")
        self.app.after(0, self.app.set_status, "Running ABPS Verification...")

        session_processed_jobcards = set()

        try:
            driver = self.app.get_driver()
            if not driver: return

            wait = WebDriverWait(driver, 20)
            short_wait = WebDriverWait(driver, 5)
            
            driver.get(config.ABPS_VERIFY_CONFIG["url"])
            
            current_url = driver.current_url
            if "login" in current_url.lower():
                self.log_error("Error: Redirected to Login page.")
                return

            # Determine which panchayats to process
            all_mode = panchayat in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL)
            saved_mode = panchayat == config.MY_PANCHAYATS_LABEL
            panchayats_to_process = []
            if all_mode:
                panch_dd = Select(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select[id*='DDL_panchayat']"))))
                panchayats_to_process = [t for t in self._get_select_option_texts(panch_dd) if t]
                if saved_mode:
                    panchayats_to_process = self._filter_panchayats_to_saved(panchayats_to_process)
                    self.log_info(f"⭐ My Saved Panchayats mode: {len(panchayats_to_process)} saved panchayat(s) will be processed.")
                else:
                    self.log_info(f"🌐 All Panchayats mode: found {len(panchayats_to_process)} panchayats.")
                if self._abort_if_no_saved_panchayats(panchayats_to_process):
                    return
            else:
                panchayats_to_process = [panchayat]

            village_css = "select[id*='DDL_Village']"
            total_p = len(panchayats_to_process)
            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped():
                    break
                self.log_info(f"===== Panchayat {p_idx+1}/{total_p}: {p_name} =====")
                self.app.after(0, self.update_status, f"{p_name}: selecting...", p_idx / max(total_p, 1))
                driver.get(config.ABPS_VERIFY_CONFIG["url"])

                # --- 1. Select Panchayat ---
                self.log_info(f"Selecting Panchayat: {p_name}")
                try:
                    panchayat_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select[id*='DDL_panchayat']")))
                    selected_ok = self._select_by_text_case_insensitive(Select(panchayat_select), p_name)
                except Exception:
                    selected_ok = False
                if not selected_ok:
                    try:
                        panchayat_select = driver.find_element(By.NAME, "ctl00$ContentPlaceHolder1$DDL_panchayat")
                        selected_ok = self._select_by_text_case_insensitive(Select(panchayat_select), p_name)
                    except Exception:
                        selected_ok = False
                if not selected_ok:
                    self.log_warning(f"Could not find panchayat '{p_name}' on website. Skipping.")
                    continue
                self.app.update_history("location_panchayat", p_name)
                try:
                    # Real ID is ctl00_ContentPlaceHolder1_DDL_Village — must use
                    # the partial CSS selector, not By.ID 'DDL_Village' (would
                    # silently time out 10s every panchayat).
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, village_css)))
                except (TimeoutException, NoSuchElementException):
                    pass
                time.sleep(1)

                # --- 2. Handle Village Dropdown for this panchayat ---
                try:
                    wait.until(lambda d: len(Select(d.find_element(By.CSS_SELECTOR, village_css)).options) > 1)
                except TimeoutException:
                    self.log_warning(f"No villages found for {p_name}. Skipping.")
                    continue

                village_select_elem = driver.find_element(By.CSS_SELECTOR, village_css)
                all_villages = [opt.text for opt in Select(village_select_elem).options if opt.get_attribute("value") != "00"]

                villages_to_process = [village] if village else all_villages
                if village and village not in all_villages:
                    self.log_warning(f"Village '{village}' not found in {p_name}. Skipping.")
                    continue

                # --- VILLAGE LOOP ---
                for i, current_village in enumerate(villages_to_process):
                    if self.is_stopped():
                        break
                    self.log_info(f"--- Processing Village {i+1}/{len(villages_to_process)}: {current_village} ---")
                    self._process_single_village(driver, wait, short_wait, village_css, session_processed_jobcards, p_name, current_village)

            self.app.after(200, lambda: self._show_abps_summary())

        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror("Automation Error", f"An error occurred:\n\n{e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _process_single_village(self, driver, wait, short_wait, village_css, session_processed_jobcards, p_name, current_village):
        """ABPS verification for one village of one panchayat."""
        try:
            self._select_by_text_case_insensitive(Select(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, village_css)))), current_village)
            self.app.update_history("location_village", current_village)

            table_xpath = "//table[contains(@id, 'gvData')]"
            try:
                short_wait.until(EC.presence_of_element_located((By.XPATH, table_xpath)))
            except TimeoutException:
                self.log_warning(f"No records found for {current_village}. Skipping.")
                return

            page_number = 1
            while True:
                if self.is_stopped():
                    break
                self.log_info(f"Scanning page {page_number}...")
                page_processed_count = 0
                while True:
                    if self.is_stopped():
                        break

                    unprocessed_rows_xpath = f"//table[contains(@id, 'gvData')]/tbody/tr[position()>1 and .//input[contains(@id, 'btn_showuid')]]"
                    potential_rows = driver.find_elements(By.XPATH, unprocessed_rows_xpath)

                    row_to_process = None
                    job_card, app_name = "N/A", "N/A"
                    unique_key = None

                    # Row finding (No interaction here, so standard logic is fine)
                    for row in potential_rows:
                        try:
                            # Use innerText for background reading
                            jc_num = row.find_element(By.XPATH, ".//td[2]").get_attribute("innerText")
                            ap_name = row.find_element(By.XPATH, ".//td[4]").get_attribute("innerText")
                            key = (jc_num, ap_name)

                            if key not in session_processed_jobcards:
                                row_to_process = row
                                job_card = jc_num
                                app_name = ap_name
                                unique_key = key
                                break
                        except StaleElementReferenceException:
                            continue

                    if row_to_process is None:
                        self.log_info("No new unprocessed records found on this page view.")
                        break

                    try:
                        self.app.after(0, self.update_status, f"Processing: {app_name}", 0.5)

                        # --- FIX: JS Click for Show UID ---
                        show_btn = row_to_process.find_element(By.XPATH, ".//input[contains(@id, 'btn_showuid')]")
                        driver.execute_script("arguments[0].click();", show_btn)

                        wait.until(EC.staleness_of(row_to_process))

                        # Wait for row refresh
                        refreshed_row = wait.until(EC.presence_of_element_located((By.XPATH, f"//tr[contains(., '{job_card}') and contains(., '{app_name}')]")))

                        # --- FIX: JS Click for Verify UID ---
                        check_npci_btn = refreshed_row.find_element(By.XPATH, ".//input[contains(@id, 'btn_verifyuid')]")
                        driver.execute_script("arguments[0].click();", check_npci_btn)

                        wait.until(EC.staleness_of(refreshed_row))

                        # Read Status
                        final_row = wait.until(EC.presence_of_element_located((By.XPATH, f"//tr[contains(., '{job_card}') and contains(., '{app_name}')]")))
                        status_msg = final_row.find_element(By.XPATH, ".//td[9]/span").get_attribute("innerText")
                        self._log_result(p_name, job_card, app_name, status_msg or "Checked")

                    except (TimeoutException, StaleElementReferenceException, NoSuchElementException) as e:
                        self._log_result(p_name, job_card, app_name, f"Error: {type(e).__name__}")
                    finally:
                        if unique_key:
                            session_processed_jobcards.add(unique_key)
                            page_processed_count += 1

                if self.is_stopped():
                    break

                if page_processed_count > 0:
                    self.log_info("Saving all verified records for this page...")
                    # --- FIX: JS Click for Save ---
                    table_element = driver.find_element(By.XPATH, table_xpath)
                    save_btn = driver.find_element(By.CSS_SELECTOR, "input[id*='btnProceed2']")
                    driver.execute_script("arguments[0].click();", save_btn)

                    wait.until(EC.staleness_of(table_element))
                    self.log_info("Page saved.")
                try:
                    # --- FIX: JS Click for Next Page ---
                    next_page_link = driver.find_element(By.LINK_TEXT, str(page_number + 1))
                    table_element = driver.find_element(By.XPATH, table_xpath)
                    driver.execute_script("arguments[0].click();", next_page_link)
                    wait.until(EC.staleness_of(table_element))
                    page_number += 1
                except NoSuchElementException:
                    self.log_info(f"No more pages for {current_village}.")
                    break

        except Exception as village_error:
            self.log_error(f"Error in {current_village}: {village_error}. Skipping.")

    def _log_result(self, panchayat, job_card, app_name, status):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        tags = ()
        status_lower = status.lower()
        
        if "fail" in status_lower or "error" in status_lower:
            tags = ('failed',)
        elif "skip" in status_lower:
            tags = ('skipped',)
        # ABPS me aksar status blank ya 'Checked' aata hai success par
        elif "success" in status_lower or "checked" in status_lower or "verified" in status_lower:
            tags = ('success',)
        
        msg = f"📋 {job_card} ({app_name}): {status}"
        if tags == ('success',):
            self.log_success(msg)
        elif tags == ('failed',):
            self.log_error(msg)
        else:
            self.log_info(msg)
        self.safe_tree_insert((panchayat, job_card, app_name, status, timestamp), tags)

    def _show_abps_summary(self):
        """Show professional summary after ABPS verification finishes."""
        if not self._is_alive():
            return
        total = len(self.results_tree.get_children())
        success = sum(1 for item in self.results_tree.get_children() if 'success' in str(self.results_tree.item(item)['values'][3]).lower() or 'checked' in str(self.results_tree.item(item)['values'][3]).lower() or 'verified' in str(self.results_tree.item(item)['values'][3]).lower())
        failed = total - success
        summary = f"✅ Verified: {success}\n❌ Failed/Error: {failed}\n📊 Total: {total}"
        self.update_status(f"✅ {success}/{total} verified", 1.0)
        self.log_info(f"{'='*40}\n📊 ABPS Verification Summary\n{summary}\n{'='*40}")
        if total > 0:
            self.log_info(f"📊 ABPS Verification Complete: {summary}")
    def _export_excel_report(self):
        """Export ABPS verification results to Excel (standard report folder)."""
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "There are no results to export.")
            return
        panchayat = self.panchayat_var.get().strip() or "Report"
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', panchayat)
        date_str = datetime.now().strftime("%d-%m-%Y")
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"ABPS_Verify_{safe_panchayat}_{date_str}.xlsx",
            filter_mode="Export All",
            category="ABPS Verify")

    def export_to_pdf(self):
        """Exports the current Treeview results to a Professional PDF using base_tab utility."""
        
        # 1. Check if there is data
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "There are no results to export.")
            return

        # 2. Prepare Data — local serial pehle column, tree ka Panchayat col
        #    PDF ke in headers me nahi hai isliye skip (Job Card se aage).
        headers = ["Sr. No.", "Job Card No.", "Applicant Name", "Status", "Timestamp"]
        data = []
        for idx, item in enumerate(self.results_tree.get_children()):
            vals = list(self.results_tree.item(item)['values'])
            core = vals[1:] if len(vals) >= 2 else vals  # (Panchayat, JobCard, Name, Status, Time)
            data.append([idx + 1] + core)

        # 3. Setup Filename and Directory
        panchayat = self.panchayat_var.get().strip() or "Report"
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', panchayat)
        date_str = datetime.now().strftime("%d-%m-%Y")
        
        # Create Folder Structure (standardized)
        target_dir = self.app.get_report_path("ABPS Verify")
        
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
             messagebox.showerror("Folder Error", f"Could not create report directory:\n{target_dir}\nError: {e}")
             return

        # Default Filename
        default_filename = f"ABPS_Verify_{safe_panchayat}_{date_str}.pdf"
        title = f"ABPS Verification Report - {panchayat}"

        # 4. Ask User for Save Location
        file_path = filedialog.asksaveasfilename(
            initialdir=target_dir,
            initialfile=self._timestamped_filename(default_filename),
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")],
            title="Save PDF Report"
        )
        
        if not file_path:
            return

        # 5. Define Column Widths (in mm, total approx 280mm for A4 Landscape)
        # Headers: Sr.No, JobCard, Name, Status, Time
        col_widths = [15, 60, 90, 80, 40]

        # 6. Call Base Tab PDF Generator
        success = self.generate_report_pdf(data, headers, col_widths, title, f"Date: {date_str}", file_path)

        if success:
            messagebox.showinfo("Success", f"PDF report saved successfully to:\n{file_path}")
            # Try to open the file
            try:
                if os.name == 'nt': os.startfile(file_path)
                else: subprocess.call(['open', file_path])
            except Exception as e: logger.debug("ABPS: Failed to open exported PDF: %s", e)