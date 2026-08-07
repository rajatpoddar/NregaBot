# tabs/msr_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import os, random, re, time
from datetime import datetime
from src import config
from src.utils import truncate_workcode
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoAlertPresentException, NoSuchElementException, TimeoutException  # noqa: F401
from selenium.common.exceptions import InvalidArgumentException, StaleElementReferenceException, UnexpectedAlertPresentException


class MsrTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="msr")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(3, weight=1)
        self._create_widgets()
    def _create_widgets(self) -> None:

        # --- Header / intro card (P7.2: pending-bills style) ---
        self._create_header_card(self, "💵", "MR Payment (MSR)",
                                 "Process & verify Muster Roll payments against the sanctioned wage amount.",
                                 icon_key="emoji_mr_payment")

        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        controls_frame.grid_columnconfigure((0, 1), weight=1)
        
        panchayat_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        panchayat_frame.grid(row=0, column=0, sticky='new', padx=15, pady=(10,0))
        ctk.CTkLabel(panchayat_frame, text="Panchayat Name", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(panchayat_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.pack(fill='x', pady=(5,0))

        
        amount_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        amount_frame.grid(row=0, column=1, sticky='new', padx=15, pady=(10,0))
        ctk.CTkLabel(amount_frame, text="Verify Amount (₹)", font=ctk.CTkFont(weight="bold")).pack(anchor='w')
        self.verify_amount_entry = ctk.CTkEntry(amount_frame)
        self.verify_amount_entry.insert(0, "300")
        self.verify_amount_entry.pack(fill='x', pady=(5,0))
        ctk.CTkLabel(amount_frame, text="Reject if amount does not match this value.", text_color="gray50").pack(anchor='w')

        ctk.CTkLabel(controls_frame, text="💡 Note: If using GP Login, Panchayat selection is not required and will be skipped.", text_color="gray50").grid(row=1, column=0, columnspan=2, sticky='w', padx=15, pady=(10,15))

        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky='ew', padx=10, pady=(0, 10))

        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew")
        work_codes_frame = data_notebook.add("Work Codes"); results_frame = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        work_codes_frame.grid_columnconfigure(0, weight=1); work_codes_frame.grid_rowconfigure(1, weight=1)
        wc_controls_frame = ctk.CTkFrame(work_codes_frame, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew')
        clear_button = ctk.CTkButton(wc_controls_frame, text="Clear", width=80, command=lambda: self.work_key_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', pady=(5,0), padx=(0,5))
        # --- MODIFIED: Update the command to use the base method ---
        extract_button = ctk.CTkButton(wc_controls_frame, text="Extract from Text", width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_key_text))
        extract_button.pack(side='right', pady=(5,0), padx=(0, 5))
        # ---
        self.work_key_text = ctk.CTkTextbox(work_codes_frame, wrap=tkinter.WORD)
        self.work_key_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        results_frame.grid_columnconfigure(0, weight=1); results_frame.grid_rowconfigure(1, weight=1)
        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10))
        
        # --- NEW: Unified Export Controls ---
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side='left')
        # --- End of Unified Export Controls ---

        cols = ("Panchayat", "Workcode", "Scheme Name", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Panchayat", width=110)
        self.results_tree.column("Workcode", width=90, anchor='center')
        self.results_tree.column("Scheme Name", width=260)
        self.results_tree.column("Status", anchor='center', width=110)
        self.results_tree.column("Details", width=300)
        self.results_tree.column("Timestamp", width=90, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree); self._setup_treeview_sorting(self.results_tree)
    
    def load_data_from_mr_tracking(self, workcodes, location_panchayat: str):
        """Public method to receive data from other tabs.

        Supports both flat code lists (single panchayat) and a grouped dict
        {panchayat_name: [codes]} (multi-panchayat from MR Tracking) — in the
        grouped case every panchayat's codes are processed under that panchayat.
        """
        # --- Grouped multi-panchayat data: {panchayat: [codes]} ---
        if isinstance(workcodes, dict) and workcodes:
            self._mr_tracking_panchayat_data = {
                p: list(dict.fromkeys(c)) for p, c in workcodes.items() if c
            }
            all_codes = [code for codes in self._mr_tracking_panchayat_data.values() for code in codes]
            display_text = "\n".join(all_codes)
            self.panchayat_var.set(location_panchayat or "")

            self.work_key_text.configure(state="normal")
            self.work_key_text.delete("1.0", tkinter.END)
            self.work_key_text.insert("1.0", display_text)
            self.work_key_text.configure(state="disabled")

            self.log_info(f"Loaded {len(all_codes)} workcodes across {len(self._mr_tracking_panchayat_data)} panchayats from MR Tracking: "
                          f"{', '.join(self._mr_tracking_panchayat_data.keys())}")
            return

        # --- Single panchayat: flat string/list of codes ---
        self._mr_tracking_panchayat_data = None
        # Set Panchayat Name
        self.panchayat_var.set(location_panchayat)
        
        # Determine how to display workcodes (Handle List or String)
        display_text = ""
        if isinstance(workcodes, list):
            display_text = "\n".join(workcodes)
        else:
            display_text = str(workcodes)

        # Set Work Codes in Textbox
        self.work_key_text.configure(state="normal")
        self.work_key_text.delete("1.0", tkinter.END)
        self.work_key_text.insert("1.0", display_text)
        self.work_key_text.configure(state="disabled")
        
        # Log info
        count = len(display_text.splitlines()) if display_text else 0
        self.log_info(f"Loaded {count} workcodes and panchayat '{location_panchayat}' from MR Tracking.")


    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.verify_amount_entry.configure(state=state)
        self.work_key_text.configure(state=state)
        # --- Update State Management for New Controls ---
        self.export_button.configure(state=state)

    # ... (start_automation, reset_ui, run_automation_logic, etc., are unchanged)
    def start_automation(self) -> None:
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic)
    def reset_ui(self) -> None:
        if messagebox.askokcancel("Reset Form?", "Clear all inputs, results, and logs?"):
            self._mr_tracking_panchayat_data = None
            self.panchayat_var.set("")
            self.verify_amount_entry.delete(0, tkinter.END); self.verify_amount_entry.insert(0, "300")
            self.work_key_text.configure(state="normal"); self.work_key_text.delete("1.0", tkinter.END); self.work_key_text.configure(state="disabled")
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
            
    def run_automation_logic(self):
        self.app.after(0, self.set_ui_state, True)
        self.safe_tree_clear()
        self.app.clear_log(self.log_display)
        self.log_info("Starting MSR processing...")
        self.app.after(0, self.app.set_status, "Running MSR Payment...")
        
        location_panchayat = self.panchayat_var.get().strip()
        verify_amount_str = self.verify_amount_entry.get().strip()
        
        self.work_key_text.configure(state="normal") # Enable to read
        work_keys = [line.strip() for line in self.work_key_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]
        self.work_key_text.configure(state="disabled") # Disable again

        # Multi-panchayat data from MR Tracking ({panchayat: [codes]}) — one run
        grouped_data = getattr(self, '_mr_tracking_panchayat_data', None) or {}
        self._mr_tracking_panchayat_data = None

        if not grouped_data and not work_keys:
            messagebox.showerror("Input Error", "No work keys provided.")
            self.app.after(0, self.set_ui_state, False)
            return
        try:
            verify_amount = float(verify_amount_str)
        except ValueError:
            messagebox.showerror("Input Error", "Verify Amount must be a valid number.")
            self.app.after(0, self.set_ui_state, False)
            return

        try:
            driver = self.app.get_driver()
            if not driver:
                return
            
            wait = WebDriverWait(driver, 15)
            if driver.current_url != config.MSR_CONFIG["url"]:
                driver.get(config.MSR_CONFIG["url"])
            
            if grouped_data:
                # ═══ Multi-panchayat run (from MR Tracking) — every panchayat's
                # codes are processed under that panchayat. ═══
                groups = [(p, list(codes)) for p, codes in grouped_data.items() if codes]
                total_groups = len(groups)
                for g_idx, (p_name, p_codes) in enumerate(groups, 1):
                    if self.is_stopped():
                        self.log_warning("Automation stopped by user.")
                        break
                    self.log_info(f"===== Panchayat {g_idx}/{total_groups}: {p_name} =====")
                    try:
                        self._select_panchayat(driver, wait, p_name)
                    except ValueError as e:
                        self.log_error(f"⛔ Skipping panchayat '{p_name}': {e}")
                        continue
                    for i, work_key in enumerate(p_codes, 1):
                        if self.is_stopped():
                            break
                        status_msg = f"[{g_idx}/{total_groups}] {p_name}: {work_key} ({i}/{len(p_codes)})"
                        progress = (g_idx - 1 + i / max(len(p_codes), 1)) / max(total_groups, 1)
                        self.app.after(0, self.app.set_status, status_msg)
                        self.app.after(0, self.update_status, status_msg, progress)
                        self._process_single_work_code(driver, wait, work_key, verify_amount, p_name)
            else:
                # ═══ Single-panchayat run (manual / macro) ═══
                self._select_panchayat(driver, wait, location_panchayat)
                total = len(work_keys)
                for i, work_key in enumerate(work_keys, 1):
                    if self.is_stopped():
                        self.log_warning("Automation stopped by user.")
                        break
                    status_msg = f"Processing {i}/{total}: {work_key}"
                    progress = (i / total)
                    self.app.after(0, self.app.set_status, status_msg)
                    self.app.after(0, self.update_status, status_msg, progress)
                    self._process_single_work_code(driver, wait, work_key, verify_amount, location_panchayat)
                
            if not self.is_stopped():
                self.log_info("📊 Automation finished. Check the 'Results' tab for details.")
        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror("MSR Error", f"An error occurred: {e}")
        finally:
            # Count success/skipped/failed separately from results_tree
            # (columns: Panchayat, Workcode, Scheme Name, Status, Details, Timestamp → status at index 3)
            status_counts = {}
            for item in self.results_tree.get_children():
                status = str(self.results_tree.item(item)['values'][3]).lower()
                status_counts[status] = status_counts.get(status, 0) + 1
            success_count = status_counts.get('success', 0)
            skipped_count = status_counts.get('skipped', 0) + status_counts.get('rejected', 0)
            fail_count = status_counts.get('failed', 0)
            total_count = sum(status_counts.values())
            self.log_info(f"📊 MSR Processing Complete: ✅ {success_count} Success, ⚠️ {skipped_count} Skipped/Rejected, ❌ {fail_count} Failed (of {total_count} total)")
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished.", 1.0)
            self.app.after(0, self.app.set_status, "Automation Finished")
            
    # Inside tabs/msr_tab.py
    def retry_logic_handler(self) -> None:
        """
        Custom Retry for MSR tab — rebuilds the grouped panchayat data for the
        failed work codes (columns: Panchayat, Workcode, Scheme Name, Status, ...).
        """
        failed_groups = {}
        all_items = self.results_tree.get_children()

        if not all_items:
            messagebox.showinfo("Retry", "No results found to retry.")
            return

        for item_id in all_items:
            values = self.results_tree.item(item_id)['values']
            if len(values) < 4:
                continue
            panchayat = str(values[0]).strip() or self.panchayat_var.get().strip() or "Unknown"
            code = str(values[1]).strip()
            status = str(values[3]).lower()
            if "success" not in status and code:
                failed_groups.setdefault(panchayat, set()).add(code)

        total_failed = sum(len(codes) for codes in failed_groups.values())
        if not total_failed:
            messagebox.showinfo("Great!", "No failed items found.")
            return

        if not messagebox.askyesno(
            "Retry Failed",
            f"Found {total_failed} failed work codes across {len(failed_groups)} panchayat(s).\nDo you want to retry them now?"
        ):
            return

        # Rebuild grouped data so each failed code is retried under its panchayat
        self._mr_tracking_panchayat_data = {p: list(codes) for p, codes in failed_groups.items()}
        all_codes = [c for codes in failed_groups.values() for c in codes]
        self.work_key_text.configure(state="normal")
        self.work_key_text.delete("1.0", tkinter.END)
        self.work_key_text.insert("1.0", "\n".join(all_codes))
        self.work_key_text.configure(state="disabled")

        for item in all_items:
            self.results_tree.delete(item)

        self.log_info(f"Retrying {total_failed} failed work codes across {len(failed_groups)} panchayats...")
        self.app.after(200, self.start_automation)

    def _process_single_work_code(self, driver, wait, work_key, verify_amount, panchayat_name="", attempt=0):
        """
        Processes a single work code for MSR payment with automatic retry on
        transient WebDriver errors (slow internet / mid-postback races that
        surface as InvalidArgumentException or StaleElementReferenceException).
        """
        try:
            self._process_work_code_attempt(driver, wait, work_key, verify_amount, panchayat_name)
        except (InvalidArgumentException, StaleElementReferenceException, UnexpectedAlertPresentException) as e:
            if attempt < 2:
                self.log_warning(f"⚠️ Transient error ({type(e).__name__}) for {work_key} — retrying ({attempt+1}/2)...")
                self._recover_page(driver, wait, panchayat_name)
                self._process_single_work_code(driver, wait, work_key, verify_amount, panchayat_name, attempt + 1)
            else:
                self._log_result("Failed", work_key, f"CRITICAL ERROR: {type(e).__name__}", panchayat_name)
        except (ValueError, IndexError, NoSuchElementException, TimeoutException) as e:
            display_msg = "MR not Filled yet." if isinstance(e, IndexError) else "Page timed out or element not found." if isinstance(e, TimeoutException) else str(e)
            self._log_result("Failed", work_key, display_msg, panchayat_name)
        except Exception as e:
            self._log_result("Failed", work_key, f"CRITICAL ERROR: {type(e).__name__}", panchayat_name)

    def _recover_page(self, driver, wait, panchayat_name=""):
        """Reloads the MSR page (and re-selects the panchayat) after a transient error."""
        try:
            driver.get(config.MSR_CONFIG["url"])
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                pass
            time.sleep(1)
            if panchayat_name:
                try:
                    self._select_panchayat(driver, wait, panchayat_name)
                except Exception as e:
                    self.log_warning(f"Could not re-select panchayat during recovery: {e}")
        except Exception as e:
            self.log_warning(f"Page recovery failed: {e}")

    def _select_panchayat(self, driver, wait, location_panchayat):
        """Selects the panchayat on the MSR page.
        Raises ValueError if a Block-login panchayat is required but missing/not found.
        Skipped silently for GP-login pages (no panchayat dropdown).
        """
        try:
            panchayat_select_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, "ddlPanchayat")))
            if not location_panchayat:
                raise ValueError("Panchayat name is required for Block Login.")
            panchayat_select = Select(panchayat_select_element)
            match = next((opt.text for opt in panchayat_select.options if location_panchayat.strip().lower() in opt.text.lower()), None)
            if not match:
                raise ValueError(f"Panchayat '{location_panchayat}' not found.")
            panchayat_select.select_by_visible_text(match)
            self.app.update_history("location_panchayat", location_panchayat)
            self.log_success(f"Successfully selected Panchayat: {match}")
            time.sleep(2)
        except TimeoutException:
            self.log_info("Panchayat selection not found/required (GP Login). Proceeding...")

    def _process_work_code_attempt(self, driver, wait, work_key, verify_amount, panchayat_name=""):
        """
        Processes a single work code for MSR payment (one attempt).
        Transient WebDriver errors are allowed to propagate so the caller can retry.
        Includes robust waiting for Slow Internet (Wait for Postback).
        """
        # Dismiss alert if present
        try: driver.switch_to.alert.accept()
        except NoAlertPresentException: pass
        
        # --- 1. Search Work Code (Background Safe) ---
        # Capture the old dropdown element to check for page refresh (staleness) later
        try:
            old_work_code_ddl = driver.find_element(By.ID, "ddlWorkCode")
        except NoSuchElementException:
            old_work_code_ddl = None

        # Use Presence
        search_box = wait.until(EC.presence_of_element_located((By.ID, "txtSearch")))
        # JS Set Value
        driver.execute_script("arguments[0].value = arguments[1];", search_box, work_key)
        
        # JS Click Search Button
        search_btn = wait.until(EC.presence_of_element_located((By.ID, "ImgbtnSearch")))
        driver.execute_script("arguments[0].click();", search_btn)
        
        # --- CRITICAL FIX FOR SLOW INTERNET ---
        # Wait for the old dropdown to become 'stale' (meaning page has refreshed/reloaded)
        if old_work_code_ddl:
            try:
                wait.until(EC.staleness_of(old_work_code_ddl))
            except TimeoutException:
                self.log_warning("Page did not refresh quickly, forcing wait...")            
        # Wait a tiny bit extra for the new DOM to settle
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except TimeoutException:
            pass

        # --- 2. Check Errors ---
        # Check for error label (Use innerText for background safety)
        try:
            error_span = driver.find_element(By.ID, "lblError")
            err_text = error_span.get_attribute("innerText").strip()
            if err_text: raise ValueError(f"Site error: '{err_text}'")
        except NoSuchElementException: pass

        # --- 3. Select Lists (Safe) ---
        # Re-find the element after the refresh
        work_code_select_elem = wait.until(EC.presence_of_element_located((By.ID, "ddlWorkCode")))
        work_code_select = Select(work_code_select_elem)
        
        # Check if options are loaded (more than just "Select")
        if len(work_code_select.options) <= 1:
            # Retry once if options haven't populated yet
            # Element wait handled by WebDriverWait below
            work_code_select = Select(driver.find_element(By.ID, "ddlWorkCode"))

        if len(work_code_select.options) <= config.MSR_CONFIG["work_code_index"]: 
            raise IndexError("Work code not found (Dropdown empty or index out of bounds).")
        
        work_code_select.select_by_index(config.MSR_CONFIG["work_code_index"])
        
        # Wait for the next dropdown (MSR No) to load after selecting Work Code
        # (Selecting work code triggers another mini-update)
        # Element wait handled by WebDriverWait below
        
        msr_select = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlMsrNo"))))
        if len(msr_select.options) <= config.MSR_CONFIG["muster_roll_index"]: 
            raise IndexError("Muster Roll (MSR) not found.")
        
        msr_select.select_by_index(config.MSR_CONFIG["muster_roll_index"])
        time.sleep(1.5)

        # --- 3b. Scheme / Work Name (attendance page khula hai) ---
        # lblWorkName only renders when the MR is actually filled, so an empty
        # value here simply means the page didn't open (e.g. MR not filled yet).
        scheme_name = ""
        try:
            scheme_name = driver.find_element(By.ID, "lblWorkName").text.strip()
        except (NoSuchElementException, StaleElementReferenceException):
            pass

        # --- 4. Verify Amount ---
        wage_inputs = driver.find_elements(By.XPATH, "//input[starts-with(@name, 'wage_per_day')]")
        filled_wages = [float(inp.get_attribute('value')) for inp in wage_inputs if inp.get_attribute('value') and float(inp.get_attribute('value')) > 0]
        
        if not filled_wages:
            self._log_result("Skipped", work_key, "Pending for JE or AE Approval", panchayat_name, scheme_name)
            return
        
        for wage in filled_wages:
            if wage != verify_amount:
                self._log_result("Rejected", work_key, f"Verify amount not matched ({wage} != {verify_amount})", panchayat_name, scheme_name)
                return

        # --- 5. Save/Submit (Background Safe) ---
        # JS Click for Save
        save_btn = wait.until(EC.presence_of_element_located((By.ID, "btnSave")))
        driver.execute_script("arguments[0].click();", save_btn)
        
        # ── FIXED ALERT HANDLING ──
        # Real portal flow: clicking Save shows a CONFIRM alert
        #   "Total No. of selected worker is X ... Do you want to Save ?"
        # and AFTER accepting it, the save postback finishes and a SECOND alert
        # ("Muster Roll Payment has been saved") appears. We must poll for that
        # second alert — otherwise the confirm text alone is reported as failed.
        def _read_page_outcome(fallback_text):
            """Checks known on-page outcome markers; falls back to fallback_text."""
            try:
                page = driver.page_source
            except Exception:
                return fallback_text
            if "Expenditure on unskilled labours exceeds sanction amount" in page:
                return "Expenditure on unskilled labours exceeds sanction amount"
            if "Muster Roll Payment has been saved" in page:
                return "Muster Roll Payment has been saved"
            return fallback_text

        outcome_text = None
        first_text = None
        try:
            first_alert = WebDriverWait(driver, 10).until(EC.alert_is_present())
            first_text = first_alert.text.strip()
            first_alert.accept()
        except TimeoutException:
            # Some portal versions show the alert a moment later
            for _ in range(3):
                try:
                    late_alert = driver.switch_to.alert
                    first_text = late_alert.text.strip()
                    late_alert.accept()
                    break
                except NoAlertPresentException:
                    time.sleep(1)

        if first_text and "do you want to save" in first_text.lower():
            # First alert is the CONFIRM — poll for the actual outcome alert
            # after the save postback (up to ~10s for slow internet).
            for _ in range(10):
                try:
                    second_alert = driver.switch_to.alert
                    outcome_text = second_alert.text.strip()
                    second_alert.accept()
                    break
                except NoAlertPresentException:
                    time.sleep(1)
            if outcome_text is None:
                # No second alert — check on-page outcome markers (e.g. the
                # 'exceeds sanction amount' error shown after a rejected save).
                outcome_text = _read_page_outcome(first_text)
        elif first_text:
            outcome_text = first_text
        else:
            # No alert at all — check on-page outcome markers
            outcome_text = _read_page_outcome("")

        if not outcome_text:
            self._log_result("Failed", work_key, "No final confirmation found (Timeout).", panchayat_name, scheme_name)
        elif "Muster Roll Payment has been saved" in outcome_text:
            self._log_result("Success", work_key, outcome_text, panchayat_name, scheme_name)
        elif "and hence it is not saved" in outcome_text:
            self._log_result("Success", work_key, "Saved (ignorable attendance error)", panchayat_name, scheme_name)
        elif "exceeds sanction amount" in outcome_text:
            self._log_result("Failed", work_key, "Exceeds Labour Payment", panchayat_name, scheme_name)
        else:
            self._log_result("Failed", work_key, f"Unknown Alert: {outcome_text}", panchayat_name, scheme_name)
        
        delay = random.uniform(config.MSR_CONFIG["min_delay"], config.MSR_CONFIG["max_delay"])
        self.app.after(0, self.update_status, f"Waiting {delay:.1f}s...")
        time.sleep(delay)
        
    def _log_result(self, status, work_key, msg, panchayat="", scheme_name=""):
        """Logs a result row. Skipped/Rejected are shown as warnings, not failures."""
        status_lower = status.lower()
        if status_lower == "success":
            level = "success"
            tags = ('success',)
        elif status_lower in ("skipped", "rejected"):
            level = "warning"
            tags = ('skipped',)
        else:
            level = "error"
            tags = ('failed',)
        timestamp = datetime.now().strftime("%H:%M:%S")
        work_key = truncate_workcode(work_key)
        
        # Clean up details text
        details = msg.replace("\n", " ").replace("\r", " ")
        if "No final confirmation found" in msg: details = "Pending for JE & AE Approval"
        elif "Muster Roll (MSR) not found" in msg: details = "MR not Filled yet."
        elif "Work code not found" in msg: details = "Work Code not found."
        
        # Log to the text box (use appropriate log level)
        if level == "success":
            self.log_success(f"'{work_key}' - {status.upper()}: {details}")
        elif level == "warning":
            self.log_warning(f"'{work_key}' - {status.upper()}: {details}")
        else:
            self.log_error(f"'{work_key}' - {status.upper()}: {details}")
        
        # Insert into table with the correct tag
        # columns: Panchayat, Workcode, Scheme Name, Status, Details, Timestamp
        self.safe_tree_insert((panchayat, work_key, scheme_name, status.upper(), details, timestamp), tags)

    # --- NEW: Central Export Function ---
    def export_report(self):
        """Export results — filename includes panchayat(s) + date + time."""
        panchayats = []
        try:
            for item in self.results_tree.get_children():
                values = self.results_tree.item(item)['values']
                if values and str(values[0]).strip() and str(values[0]).strip() not in panchayats:
                    panchayats.append(str(values[0]).strip())
        except Exception:
            panchayats = []

        if panchayats:
            name_part = "_".join(panchayats[:2])
            if len(panchayats) > 2:
                name_part += f"_plus{len(panchayats)-2}"
            panchayat_display = ", ".join(panchayats[:2]) + (f" +{len(panchayats)-2} more" if len(panchayats) > 2 else "")
        else:
            name_part = self.panchayat_var.get().strip() or "All"
            panchayat_display = name_part

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name_part)
        timestamp = datetime.now().strftime("%d-%b-%Y_%H%M%S")
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"MSR_Payment_{safe_name}_{timestamp}.xlsx",
            filter_mode="Export All",
            title_prefix=f"MSR Payment Report - {panchayat_display}"
        )


    
