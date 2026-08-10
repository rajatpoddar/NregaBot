# tabs/zero_mr_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import json
import os, sys, subprocess, time
from datetime import datetime
from src import config
from src.utils import truncate_workcode
from src.i18n import tr
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, StaleElementReferenceException, TimeoutException  # noqa: F401


class ZeroMrTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="zero_mr")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:

        # --- Header / intro card (P7.2: pending-bills style) ---
        self._create_header_card(self, "🔢", tr("tab.zero_mr.title"), tr("tab.zero_mr.subtitle"),
                                 icon_key="emoji_zero_mr")

        # Frame for all user input controls (bordered card)
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 0))
        controls_frame.grid_columnconfigure((1, 3), weight=1)

        # --- Row 0: Financial Year ---
        ctk.CTkLabel(controls_frame, text=tr("form.zero_mr.financial_year")).grid(row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        # Get current year and create a list for the past few years
        current_year = datetime.now().year
        fin_year_list = [f"{year}-{year+1}" for year in range(current_year + 1, current_year - 5, -1)]
        self.fin_year_menu = ctk.CTkOptionMenu(controls_frame, values=fin_year_list)
        self.fin_year_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))

        # --- Row 1: Panchayat Name ---
        ctk.CTkLabel(controls_frame, text=tr("common.panchayat_name_label")).grid(row=1, column=0, sticky='w', padx=15, pady=5)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=1, column=1, columnspan=3, sticky='ew', padx=15, pady=5)


        # --- Row 3: Action Buttons (outside the card) ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)

        # --- Data Tabs (Work List, Results, Logs) ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        work_list_tab = data_notebook.add("Work List")
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # --- 1. Work List Tab ---
        work_list_tab.grid_columnconfigure(0, weight=1)
        work_list_tab.grid_rowconfigure(1, weight=1)
        
        wc_controls_frame = ctk.CTkFrame(work_list_tab, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=(5,0))
        
        ctk.CTkLabel(wc_controls_frame, text=tr("form.zero_mr.format_hint")).pack(side='left', padx=5)
        clear_button = ctk.CTkButton(wc_controls_frame, text=tr("common.clear"), width=80, command=lambda: self.work_list_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', padx=5)

        self.work_list_text = ctk.CTkTextbox(work_list_tab)
        self.work_list_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        # self.work_list_text.insert("1.0", "Example: 58744,32158") # <-- Placeholder removed

        # --- 2. Results Tab ---
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10))
        
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text=tr("common.export_excel"), command=self.export_report)
        self.export_button.pack(side='left')

        # --- Results Treeview ---
        cols = ("Panchayat", "Search Key", "MSR No", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Search Key", anchor='center', width=100)
        self.results_tree.column("MSR No", anchor='center', width=100)
        self.results_tree.column("Status", anchor='center', width=100)
        self.results_tree.column("Details", width=350)
        self.results_tree.column("Timestamp", anchor='center', width=100)
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.fin_year_menu.configure(state=state)
        self.panchayat_menu.configure(state=state)
        self.work_list_text.configure(state=state)
        self.export_button.configure(state=state)
    def reset_ui(self) -> None:
        self._mr_tracking_panchayat_data = None
        self.panchayat_var.set("")
        self.work_list_text.delete("1.0", tkinter.END)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.app.clear_log(self.log_display)
        self.update_status("Ready", 0.0)
        self.log_info("Form has been reset.")
        self.app.after(0, self.app.set_status, "Ready")
    def start_automation(self) -> None:
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.app.clear_log(self.log_display)

        inputs = {
            'fin_year': self.fin_year_menu.get(),
            'panchayat_name': self.panchayat_var.get().strip(),
            'work_list_raw': self.work_list_text.get("1.0", tkinter.END).strip()
        }

        if not inputs['panchayat_name'] or not inputs['work_list_raw']:
            messagebox.showwarning(tr("errors.input_error"), tr("dialogs.panchayat_worklist_required"))
            return

        # Parse the work list
        work_items = []
        try:
            lines = inputs['work_list_raw'].splitlines()
            for i, line in enumerate(lines):
                if not line.strip() or "Example:" in line:
                    continue
                parts = line.split(',')
                if len(parts) != 2:
                    raise ValueError(f"Line {i+1} is not in the correct 'SearchKey,MSRNo' format.")
                work_key = parts[0].strip()
                msr_no = parts[1].strip()
                if not work_key or not msr_no:
                    raise ValueError(f"Line {i+1} has missing data.")
                work_items.append((work_key, msr_no))
        except Exception as e:
            messagebox.showerror(tr("errors.input_error"), tr("dialogs.failed_parse_worklist", error=e))
            return

        if not work_items:
            messagebox.showwarning(tr("errors.input_error"), tr("dialogs.no_valid_items"))
            return

        inputs['work_items'] = work_items
        self.app.update_history("location_panchayat", inputs['panchayat_name'])
        self._save_inputs(inputs)
        
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, self.app.set_status, "Starting Zero MR...")
        self.log_info("Starting Zero MR automation...")
        
        try:
            driver = self.app.get_driver()
            if not driver:
                self.app.after(0, self.set_ui_state, False)
                return
                
            wait = WebDriverWait(driver, 20)
            
            self.log_info(f"Navigating to Zero MR page...")
            driver.get(config.ZERO_MR_CONFIG["url"])

            # --- FIX: Add explicit wait for page to be fully interactive ---
            self.log_info("Waiting for page elements to load...")
            try:
                wait.until(EC.presence_of_element_located((By.ID, "ddlfin")))
                fin_year_dropdown_element = wait.until(EC.element_to_be_clickable((By.ID, "ddlfin")))
                self.log_info("Page loaded successfully.")
            except TimeoutException:
                self.log_error("Page did not load correctly or Fin Year dropdown not found.")
                raise Exception("Page load timeout or essential element 'ddlfin' not found.")
            # --- END FIX ---

            # --- Set Fin Year and Panchayat (only once) ---
            self.app.after(0, self.app.set_status, "Setting Financial Year...")
            self.log_info(f"Selecting Financial Year: {inputs['fin_year']}")
            
            fin_year_select = Select(fin_year_dropdown_element)
            if fin_year_select.first_selected_option.text != inputs['fin_year']:
                fin_year_select.select_by_visible_text(inputs['fin_year'])
                self.log_info("Waiting for Fin Year postback...")
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                except TimeoutException:
                    pass

            self.app.after(0, self.app.set_status, "Setting Panchayat...")

            # --- Multi-panchayat data from MR Tracking? Process every panchayat ---
            grouped_items = getattr(self, '_mr_tracking_panchayat_data', None)
            self._mr_tracking_panchayat_data = None
            if grouped_items:
                groups = {}
                for item in grouped_items:
                    p = (item.get("panchayat") or "").strip()
                    wc = (item.get("work_code") or "").strip()
                    msr = (item.get("msr_no") or "").strip()
                    if not p or not wc or not msr:
                        continue
                    groups.setdefault(p, []).append((wc, msr))
                total_groups = len(groups)
                for g_idx, (p_name, items) in enumerate(groups.items(), 1):
                    if self.is_stopped():
                        self.log_warning("Stop signal received.")
                        break
                    self.log_info(f"===== Panchayat {g_idx}/{total_groups}: {p_name} =====")
                    try:
                        self._select_zero_mr_panchayat(driver, wait, p_name)
                    except ValueError as e:
                        self.log_error(f"⛔ Skipping panchayat '{p_name}': {e}")
                        continue
                    total_items = len(items)
                    for i, (work_key, msr_no) in enumerate(items, 1):
                        if self.is_stopped():
                            self.log_warning("Stop signal received.")
                            break
                        status_msg = f"Processing [{g_idx}/{total_groups}] {i}/{total_items}: Key={work_key}, MSR={msr_no}"
                        self.app.after(0, self.app.set_status, status_msg)
                        self.app.after(0, self.update_status, status_msg, i / max(total_items, 1))
                        self._process_single_item(driver, wait, work_key, msr_no, p_name)
            else:
                # --- Single panchayat ---
                self._select_zero_mr_panchayat(driver, wait, inputs['panchayat_name'])
                self.log_success("Setup complete. Starting item processing...")
                total_items = len(inputs['work_items'])
                for i, (work_key, msr_no) in enumerate(inputs['work_items']):
                    if self.is_stopped():
                        self.log_warning("Stop signal received.")
                        break
                    status_msg = f"Processing {i+1}/{total_items}: Key={work_key}, MSR={msr_no}"
                    self.app.after(0, self.app.set_status, status_msg)
                    self.app.after(0, self.update_status, status_msg, (i+1)/total_items)
                    self._process_single_item(driver, wait, work_key, msr_no, inputs['panchayat_name'])

        except Exception as e:
            error_msg = f"A critical error occurred: {e}"
            self.log_error(error_msg)
            messagebox.showerror(tr("dialogs.critical_error"), error_msg)
            self.app.after(0, self.app.set_status, "Error")
        finally:
            # Count success/fail from results_tree
            success_count = sum(1 for item in self.results_tree.get_children() if 'success' in str(self.results_tree.item(item)['values'][3]).lower())
            fail_count = sum(1 for item in self.results_tree.get_children() if 'success' not in str(self.results_tree.item(item)['values'][3]).lower())
            total_count = success_count + fail_count
            self.log_info(f"📊 Zero MR Complete: ✅ {success_count} generated, ❌ {fail_count} failed (of {total_count} total)")
            self.app.after(0, self.set_ui_state, False)
            final_status = "Automation Finished"
            if self.is_stopped():
                final_status = "Automation Stopped"
            self.app.after(0, self.app.set_status, final_status)
            self.app.after(0, self.update_status, final_status, 1.0)
            self.log_info(f"📊 {final_status}")

    def _select_zero_mr_panchayat(self, driver, wait, panchayat_name):
        """Selects the panchayat dropdown on the Zero MR page (postback aware)."""
        self.app.after(0, self.app.set_status, f"Setting Panchayat: {panchayat_name}")
        self.log_info(f"Selecting Panchayat: {panchayat_name}")
        # Central helper — GP login (no dropdown) par selection skip hota hai.
        status, _ = self._select_panchayat_or_skip(
            driver, wait, panchayat_name, ["ddlpanch"])
        if status == "notfound":
            raise ValueError(f"Panchayat '{panchayat_name}' not found in dropdown.")
        if status == "missing":
            raise ValueError("Panchayat name is required.")
        if status == "selected":
            self.log_info("Waiting for Panchayat postback...")
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                pass
        # status == "gp" → panchayat skip (GP login), aage badho

    def _process_single_item(self, driver, wait, work_key, msr_no, panchayat):
        try:
            self.log_info(f"   - Processing Key: {work_key}, MSR: {msr_no}")
            
            # --- RETRY LOGIC: Find search box safely ---
            search_box = None
            for attempt in range(3):
                try:
                    search_box = wait.until(EC.element_to_be_clickable((By.ID, "txtsearch_work")))
                    search_box.clear()
                    search_box.send_keys(work_key)
                    break # Success
                except StaleElementReferenceException:
                    if attempt == 2: 
                        raise # Re-raise if failed 3 times
                    self.log_warning("Page updating, retrying search...")
                    time.sleep(2)
            
            # 2. Trigger postback (by clicking body)
            driver.find_element(By.TAG_NAME, 'body').click()
            self.log_info("   - Waiting for work code...")
            
            # --- IMPROVED: Wait for specific Work Code in dropdown ---
            # Instead of just waiting for *any* options, we wait until an option 
            # containing our 'work_key' actually appears. This prevents reading stale data.
            def work_code_option_present(d):
                try:
                    select_elem = d.find_element(By.ID, "ddlworkcode")
                    # Get all options. Using find_elements is safer/faster than Select.options loop for simple text check
                    options = select_elem.find_elements(By.TAG_NAME, "option")
                    
                    # Ensure we aren't just seeing the default "Select" or empty list
                    if len(options) <= 1:
                        return False
                        
                    for opt in options:
                        if work_key in opt.text:
                            return opt.text # Return the text so we can select it later
                    return False
                except StaleElementReferenceException:
                    return False

            try:
                # Wait up to 10 seconds for the dropdown to populate with the correct item
                found_option_text = WebDriverWait(driver, 10).until(work_code_option_present)
            except TimeoutException:
                # Diagnostics: What IS in the dropdown?
                try:
                    debug_select = Select(driver.find_element(By.ID, "ddlworkcode"))
                    options_preview = [o.text for o in debug_select.options[:3]]
                except:
                    options_preview = "Unknown"
                raise NoSuchElementException(f"Could not find a work code matching '{work_key}' in the dropdown. Available: {options_preview}...")

            # Select the found option
            work_code_select = Select(driver.find_element(By.ID, "ddlworkcode"))
            work_code_select.select_by_visible_text(found_option_text)
            self.log_info(f"   - Selected work code: {found_option_text}")
            
            # --- CRITICAL WAIT: Wait for MSR list update ---
            self.log_info("   - Waiting for MSR list update...")
            time.sleep(2.5) # Explicit wait for AJAX/Postback to populate MSR list

            # 4. Select MSR No (Modified for Partial Matching)
            wait.until(EC.presence_of_element_located((By.ID, "ddlmustroll")))
            msr_select = Select(driver.find_element(By.ID, "ddlmustroll"))
            
            target_msr = msr_no.strip()
            found_msr_text = None

            # Iterate options to find partial match
            for option in msr_select.options:
                if "Select" in option.text: continue
                if target_msr in option.text:
                    found_msr_text = option.text
                    break
            
            if found_msr_text:
                msr_select.select_by_visible_text(found_msr_text)
                self.log_info(f"   - MSR selected: {found_msr_text}. Clicking save.")
            else:
                # Debug info
                options_preview = [o.text for o in msr_select.options if "Select" not in o.text][:3]
                error_msg = f"MSR '{target_msr}' not found in dropdown. Available: {options_preview}..."
                self.log_error(f"   - FAILED: {error_msg}")
                self._log_result(panchayat, work_key, msr_no, "Failed", error_msg)
                return

            # 5. Click Save
            save_btn = wait.until(EC.element_to_be_clickable((By.ID, "btnSave")))
            save_btn.click()
            
            # 6. Handle on-page message
            self.log_info("   - Waiting for result message...")
            
            def message_or_error_visible(d):
                msg = d.find_elements(By.ID, "lblmsg")
                err = d.find_elements(By.ID, "ValidationSummary1")
                if msg and msg[0].is_displayed() and msg[0].text.strip(): return msg[0]
                if err and err[0].is_displayed() and err[0].text.strip(): return err[0]
                return False

            result_element = WebDriverWait(driver, 10).until(message_or_error_visible)
            message_text = result_element.text.strip().replace("\n", " ")

            if "successfully" in message_text.lower() or "saved" in message_text.lower() or "updated" in message_text.lower():
                self.log_success(f"   - Success: {message_text}")
                self._log_result(panchayat, work_key, msr_no, "Success", message_text)
            else:
                self.log_error(f"   - Failed: {message_text}")
                self._log_result(panchayat, work_key, msr_no, "Failed", message_text)
            
            time.sleep(1)

        except (TimeoutException, NoSuchElementException) as e:
            error_msg = f"Element not found/timeout. {str(e).splitlines()[0]}"
            self.log_error(f"   - FAILED: {error_msg}")
            self._log_result(panchayat, work_key, msr_no, "Failed", error_msg)
        except Exception as e:
            if "stale element" in str(e).lower():
                error_msg = "Page refreshed unexpectedly."
            else:
                error_msg = f"Unexpected error: {e}"
            self.log_error(f"   - FAILED: {error_msg}")
            self._log_result(panchayat, work_key, msr_no, "Failed", error_msg)
    def retry_logic_handler(self) -> None:
        """
        Custom Retry Logic for Work Allocation.
        Extracts failed Work Keys from the results tree and restarts automation
        specifically for those keys.
        """
        failed_keys = []
        all_items = self.results_tree.get_children()
        
        if not all_items:
            messagebox.showinfo(tr("base.error_tab.retry_btn"), tr("base.retry_no_results"))
            return

        for item_id in all_items:
            values = self.results_tree.item(item_id)['values']
            # Tree columns: Work Key, Work Code, Status, Details, Timestamp
            # Index 0 is Work Key, Index 2 is Status
            work_key = str(values[1]).strip()
            status = str(values[3]).lower()
            
            # Check for failure keywords (non-success)
            if "success" not in status:
                if work_key and work_key not in failed_keys:
                    failed_keys.append(work_key)
        
        if not failed_keys:
            messagebox.showinfo(tr("dialogs.great"), tr("base.retry_no_fails"))
            return

        # Confirm before action
        if not messagebox.askyesno(tr("base.retry_confirm_title"), tr("dialogs.retry_failed_keys", count=len(failed_keys))):
            return

        # 1. Update Input Widget (Switch to Manual/Bulk Mode for Retry)
        try:
            self.work_list_text.configure(state="normal") # Ensure it's editable
            self.work_list_text.delete("1.0", tkinter.END)
            self.work_list_text.insert("1.0", "\n".join(failed_keys))
            # Note: We keep it 'normal' here so start_automation can read it properly
        except Exception as e:
            messagebox.showerror(tr("dialogs.error"), tr("dialogs.failed_update_worklist", error=e))
            return

        # 2. Reset CSV Data (Crucial: Forces logic to read from text box)
        self.csv_allocation_data = {} 
        self.file_label.configure(text=tr("form.zero_mr.retry_mode"), text_color="orange")
        
        # 3. Clear Previous Results
        for item in all_items:
            self.results_tree.delete(item)

        # 4. Auto Start with a slight delay
        # The delay ensures the text box is fully updated before the automation reads it
        self.log_info(f"Retrying {len(failed_keys)} failed work keys...")
        self.app.after(200, self.start_automation)

    def _log_result(self, panchayat, work_key, msr_no, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (panchayat, truncate_workcode(work_key), msr_no, status, details, timestamp)
        tags = ('failed',) if 'success' not in status.lower() else ()
        self.safe_tree_insert(values, tags)

    def export_report(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="zero_mr_results.xlsx",
            filter_mode="Export All",
            title_prefix="Zero MR Report"
        )

    def _get_filtered_data_and_filepath(self, export_format):
        all_items = self.results_tree.get_children()
        if not all_items: messagebox.showinfo(tr("dialogs.no_data"), tr("dialogs.no_results_to_export")); return None, None
        
        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in all_items:
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[3].upper()
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status: data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status: data_to_export.append(row_values)
        if not data_to_export: messagebox.showinfo(tr("dialogs.no_data"), tr("dialogs.no_records_for_filter", filter=filter_option)); return None, None

        safe_name = "".join(c for c in self.panchayat_var.get().strip() if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        file_details = {"PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")], "title": "Save Report as PDF"}}
        details = file_details[export_format]
        filename = f"Zero_MR_Report_{safe_name}_{timestamp}{details['ext']}"

        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_report_path("Zero MR"), initialfile=filename, title=details['title'])
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, file_path):
        try:
            headers = self.results_tree['columns']
            col_widths = [40, 40, 40, 130, 40] # Adjusted widths for A4 Landscape
            title = f"Zero MR Status Report: {self.panchayat_var.get().strip()}"
            report_date = datetime.now().strftime('%d %b %Y')
            
            success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
            
            if success:
                if messagebox.askyesno(tr("dialogs.success"), tr("dialogs.pdf_report_exported", path=file_path)):
                    if sys.platform == "win32":
                        os.startfile(file_path)
                    else:
                        subprocess.call(['open', file_path])
        except Exception as e:
            messagebox.showerror(tr("dialogs.export_error"), tr("dialogs.failed_create_pdf", error=e))

    def load_data_from_mr_tracking(self, data_list: list):
        """
        Receives data from the MR Tracking tab and populates the form.
        Supports multi-panchayat data — every panchayat's items are kept and
        processed panchayat-by-panchayat during the automation.
        """
        if not data_list:
            messagebox.showwarning(tr("dialogs.no_data"), tr("dialogs.no_data_from_mr_tracking"), parent=self)
            return

        self.log_info(f"Received {len(data_list)} items from MR Tracking.")
        
        # Clear current form and results
        self.panchayat_var.set("")
        self.work_list_text.delete("1.0", tkinter.END)
        self.safe_tree_clear()
        self._mr_tracking_panchayat_data = None

        # Keep ALL valid items (multi-panchayat support)
        valid_items = []
        for item in data_list:
            panchayat = (item.get("panchayat") or "").strip()
            work_code = (item.get("work_code") or "").strip()
            msr_no = (item.get("msr_no") or "").strip()
            if not all([panchayat, work_code, msr_no]):
                self.log_warning(f"Skipping invalid item: {item}")
                continue
            valid_items.append({"panchayat": panchayat, "work_code": work_code, "msr_no": msr_no})

        if not valid_items:
            messagebox.showerror(tr("dialogs.data_error"), tr("dialogs.missing_panchayat_workcode_msr"), parent=self)
            return

        self._mr_tracking_panchayat_data = valid_items

        # Group panchayats for display
        panchayats = list(dict.fromkeys(item["panchayat"] for item in valid_items))
        self.panchayat_var.set(panchayats[0])
        self.log_info(f"Set Panchayat to: {panchayats[0]}")

        work_list_entries = [f"{item['work_code']},{item['msr_no']}" for item in valid_items]
        self.work_list_text.insert("1.0", "\n".join(work_list_entries))
        self.log_success(f"Loaded {len(work_list_entries)} items across {len(panchayats)} panchayat(s).")
        if len(panchayats) > 1:
            self.log_info(f"Panchayats: {', '.join(panchayats)}")

    def _save_inputs(self, inputs):
        """Saves the financial year and panchayat name."""
        save_data = {
            'fin_year': inputs.get('fin_year'),
            'panchayat_name': inputs.get('panchayat_name')
        }
        try:
            self.app.history_manager.save_tab_inputs_batch("zero_mr", save_data)
        except Exception as e:
            print(f"Error saving Zero MR inputs: {e}")

    def load_inputs(self):
        """Loads the saved financial year and panchayat name."""
        data = self.app.history_manager.get_tab_inputs("zero_mr")
        if not data:
            return
        saved_fin_year = data.get('fin_year', '')
        if saved_fin_year:
            if saved_fin_year in self.fin_year_menu.cget("values"):
                self.fin_year_menu.set(saved_fin_year)
        self.panchayat_var.set(data.get('panchayat_name', ''))