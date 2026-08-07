# tabs/SA_report_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time, os, sys, re
from datetime import datetime

from src.utils import resource_path, get_logger
from .base_tab import BaseAutomationTab

logger = get_logger()
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, StaleElementReferenceException, TimeoutException  # noqa: F401


class SAReportTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="social_audit_respond")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._create_widgets()
    def _create_widgets(self) -> None:

        # ── Header / intro card (pending-bills style) ──
        self._create_header_card(self, "🛡️", "Social Audit Report",
                                 "View and respond to social audit issues for the selected panchayat.",
                                 icon_key="emoji_social_audit")

        # Frame for all user input controls (settings card)
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="new", padx=10, pady=(6, 10))
        controls_frame.grid_columnconfigure(1, weight=1)

        # --- Input Fields for the NEW page ---
        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))
        ctk.CTkLabel(controls_frame, text="On PO LOGIN, go to D23 > Social Audit View, then start the automation. Stay on that page.", text_color="gray50").grid(row=1, column=1, sticky='w', padx=15, pady=(0,10))


        ctk.CTkLabel(controls_frame, text="Audit Conducted in:").grid(row=2, column=0, sticky='w', padx=15, pady=5)
        current_year = datetime.now().year
        years = [f"{year}-{year+1}" for year in range(current_year, current_year - 8, -1)]
        default_year = f"{current_year}-{current_year+1}" if datetime.now().month >= 4 else f"{current_year-1}-{current_year}"
        self.year_var = ctk.StringVar(value=default_year)
        self.year_menu = ctk.CTkOptionMenu(controls_frame, variable=self.year_var, values=years)
        self.year_menu.grid(row=2, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text="Issue Status:").grid(row=3, column=0, sticky='w', padx=15, pady=5)
        status_options = ["Pending", "Closed"]
        self.status_var = ctk.StringVar(value="Pending")
        self.status_menu = ctk.CTkOptionMenu(controls_frame, variable=self.status_var, values=status_options)
        self.status_menu.grid(row=3, column=1, sticky='ew', padx=15, pady=5)

        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)

        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        export_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.export_button = ctk.CTkButton(export_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side="left")

        cols = ("SR#", "District", "Block", "Panchayat", "Issue Number", "Issue Type", "Forwarded To", "Status", "Issue Description")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        
        self.results_tree.column("SR#", width=40, anchor='center'); self.results_tree.column("District", width=100); self.results_tree.column("Block", width=100); self.results_tree.column("Panchayat", width=100); self.results_tree.column("Issue Number", width=120); self.results_tree.column("Issue Type", width=150); self.results_tree.column("Forwarded To", width=80); self.results_tree.column("Status", width=80); self.results_tree.column("Issue Description", width=350)

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running); state = "disabled" if running else "normal"; self.panchayat_menu.configure(state=state); self.year_menu.configure(state=state); self.status_menu.configure(state=state)
    def reset_ui(self) -> None:
        """Resets inputs to default."""
        super().reset_ui() # Call base to clear logs/status
        
        # Clear Panchayat
        self.panchayat_var.set("")
        
        # Reset Dropdowns (Select first option if available)
        try:
            current_year = datetime.now().year
            default_year = f"{current_year}-{current_year+1}"
            self.year_var.set(default_year)
            self.status_var.set("Pending")
        except Exception as e: logger.debug("SA: Could not set default status: %s", e)
        
        # Clear Treeview
        self.safe_tree_clear()
    def start_automation(self) -> None:
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        inputs = {'panchayat': self.panchayat_var.get().strip(), 'year': self.year_var.get(), 'status': self.status_var.get()}
        if not all(inputs.values()): messagebox.showwarning("Input Error", "All fields are required."); return
        
        self.app.update_history("location_panchayat", inputs['panchayat'])
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True); self.app.clear_log(self.log_display); self.log_info("Starting SA View/Respond Issue automation...")
        try:
            driver = self.app.get_driver();
            if not driver: return
            wait = WebDriverWait(driver, 20); url = "https://mnregaweb2.nic.in/netnrega/SocialAuditFindings/SA-ViewRespond-Issue.aspx"; driver.get(url)
            PANCHAYAT_ID, YEAR_ID, STATUS_ID, GET_DETAILS_BTN_ID, RESULTS_TABLE_ID, SPINNER_ID = ("ContentPlaceHolder1_ddlPanchayat", "ContentPlaceHolder1_ddlAuditConduct", "ContentPlaceHolder1_ddlStatus", "ContentPlaceHolder1_btnFilterData", "ContentPlaceHolder1_grd_IssueDetails", "ContentPlaceHolder1_UpdateProgress1")

            self.log_info(f"Selecting Panchayat: {inputs['panchayat']}"); self.select_dropdown(driver, PANCHAYAT_ID, inputs['panchayat']); wait.until(EC.invisibility_of_element_located((By.ID, SPINNER_ID)))
            self.log_info(f"Selecting Year: {inputs['year']}"); Select(wait.until(EC.element_to_be_clickable((By.ID, YEAR_ID)))).select_by_visible_text(inputs['year']); wait.until(EC.invisibility_of_element_located((By.ID, SPINNER_ID)))
            self.log_info(f"Selecting Status: {inputs['status']}"); Select(wait.until(EC.element_to_be_clickable((By.ID, STATUS_ID)))).select_by_visible_text(inputs['status'])
            self.log_info("Fetching details...");
            try: old_first_row = driver.find_element(By.XPATH, f"//table[@id='{RESULTS_TABLE_ID}']//tr[2]")
            except NoSuchElementException: old_first_row = None
            driver.find_element(By.ID, GET_DETAILS_BTN_ID).click(); wait.until(EC.invisibility_of_element_located((By.ID, SPINNER_ID)))
            if old_first_row:
                try: wait.until(EC.staleness_of(old_first_row))
                except TimeoutException: self.log_warning("Staleness check timed out, proceeding...")

            table = wait.until(EC.presence_of_element_located((By.ID, RESULTS_TABLE_ID))); total_rows = len(table.find_elements(By.XPATH, ".//tr[position()>1]")); self.log_info(f"Found {total_rows} records.")
            for i in range(total_rows):
                if self.is_stopped(): self.log_warning("Stop signal received."); break
                
                # --- UPDATE: Better Status ---
                status_msg = f"Processing row {i+1}/{total_rows}"
                self.app.after(0, self.app.set_status, status_msg)
                self.app.after(0, self.update_status, status_msg, (i+1)/total_rows)
                # --- END UPDATE ---
                
                row = wait.until(EC.presence_of_element_located((By.XPATH, f"//table[@id='{RESULTS_TABLE_ID}']//tr[{i+2}]"))); cells = row.find_elements(By.TAG_NAME, "td")
                
                sr_no, district, block, panchayat, issue_no, issue_type, forwarded_to, status = (cells[0].text.strip(), cells[1].text.strip(), cells[2].text.strip(), cells[3].text.strip(), cells[4].text.strip(), cells[5].text.strip(), cells[6].text.strip(), cells[7].text.strip())
                self.log_info(f"({sr_no}/{total_rows}) Clicking 'View' for Issue: {issue_no}"); view_button = cells[9].find_element(By.TAG_NAME, "input"); driver.execute_script("arguments[0].click();", view_button)
                modal_wait = WebDriverWait(driver, 10); issue_description = modal_wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_lblIssueDesc"))).text.strip()
                modal_wait.until(EC.element_to_be_clickable((By.ID, "btnCloseModel"))).click(); modal_wait.until(EC.invisibility_of_element_located((By.ID, "successModal")))
                try: modal_wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))
                except TimeoutException: self.log_warning("Modal backdrop did not disappear normally. Proceeding...")
                
                result_data = (sr_no, district, block, panchayat, issue_no, issue_type, forwarded_to, status, issue_description)
                # Website ka SR# ignore — local serial auto-fill hota hai (_tree_insert)
                self.app.after(0, lambda data=result_data: self._tree_insert(self.results_tree, data))
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e: error_msg = f"A browser error occurred: {str(e).splitlines()[0]}"; self.log_error(error_msg); messagebox.showerror("Automation Error", error_msg)
        except Exception as e: self.log_error(f"An unexpected error occurred: {e}"); messagebox.showerror("Critical Error", f"An unexpected error occurred: {e}")
        finally:
            # Count results from tree
            issue_count = 0
            closed_count = 0
            for item_id in self.results_tree.get_children():
                vals = self.results_tree.item(item_id)['values']
                if len(vals) >= 8:
                    st = str(vals[7]).lower()  # Status column index
                    if 'closed' in st:
                        closed_count += 1
                    else:
                        issue_count += 1
            
            self.app.after(0, self.set_ui_state, False); self.app.after(0, self.update_status, "Automation Finished", 1.0); self.app.after(0, self.app.set_status, "Automation Finished")
            if not self.is_stopped():
                total_issues = issue_count + closed_count
                self.app.after(100, lambda: self.log_info(f"\n{'='*50}\n📊 Social Audit Summary: {total_issues} issues found (⏳ {issue_count} pending, ✅ {closed_count} closed)\n{'='*50}"))
            
            # Reset status after 5 seconds
            self.app.after(5000, lambda: self.app.set_status("Ready"))
            self.app.after(5000, lambda: self.update_status("Ready", 0.0))

    def export_report(self):
        """Export results to professional Excel."""
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "There are no results to export.")
            return

        title = "Social Audit Status Report"
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="Social_Audit_Report.xlsx",
            filter_mode="Export All",
            title_prefix=title
        )
        