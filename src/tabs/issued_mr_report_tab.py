# tabs/issued_mr_report_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time, os, re, json
from datetime import datetime

# --- Imports ---
# --- End Imports ---

from src.utils import resource_path, get_logger
from .base_tab import BaseAutomationTab

logger = get_logger()
from src import config
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._imports import *  # noqa: F403,F401

from webdriver_manager.chrome import ChromeDriverManager

class IssuedMrReportTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="issued_mr_report")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) 
        
        # Headers for Standard Issued MR Report
        self.report_headers = [
            "S No.", "Panchayat", "Work Code", "Work Name", 
            "Work Category", "Work Type", "Agency Name"
        ]

        # --- NEW: Headers for ABPS Pending Report ---
        self.abps_report_headers = [
            "S No.", "Panchayat", "Jobcard No.", "Worker Name", "ABPS Status"
        ]
        
        # Shared browser use karega (self.app.get_driver()) — apna driver nahi banayega
        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:

        # Frame for all user input controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="new", padx=10, pady=10)
        controls_frame.grid_columnconfigure(1, weight=1)

        # --- Input Fields ---
        # --- Create all entries first (no cross-references) ---
        ctk.CTkLabel(controls_frame, text="State:").grid(row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        s_vals = self.app.history_manager.get_suggestions("location_state") or [""]
        self.state_var = ctk.StringVar()
        self.state_menu = ctk.CTkOptionMenu(controls_frame, variable=self.state_var, values=s_vals)
        self.state_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))

        ctk.CTkLabel(controls_frame, text="District:").grid(row=1, column=0, sticky='w', padx=15, pady=5)
        d_vals = self.app.history_manager.get_suggestions("location_district") or [""]
        self.district_var = ctk.StringVar()
        self.district_menu = ctk.CTkOptionMenu(controls_frame, variable=self.district_var, values=d_vals)
        self.district_menu.grid(row=1, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text="Block:").grid(row=2, column=0, sticky='w', padx=15, pady=5)
        b_vals = self.app.history_manager.get_suggestions("location_block") or [""]
        self.block_var = ctk.StringVar()
        self.block_menu = ctk.CTkOptionMenu(controls_frame, variable=self.block_var, values=b_vals)
        self.block_menu.grid(row=2, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=3, column=0, sticky='w', padx=15, pady=5)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=3, column=1, sticky='ew', padx=15, pady=5)

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
            self.panchayat_var.set("")
            vals = self.app.history_manager.get_filtered_suggestions("location_panchayat", "location_block", self.block_var.get()) or [""]
            self.panchayat_menu.configure(values=vals)
        self.block_var.trace_add("write", _on_block_change)

        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=4, column=0, columnspan=2, pady=10)

        # --- NEW BUTTON FOR ABPS CHECK ---
        self.btn_abps_check = ctk.CTkButton(
            controls_frame,
            text="Pending demand labour for abps",
            command=self.start_abps_automation,
            fg_color=config.COLORS["purple_report"], # Purple color to distinguish
            hover_color=config.COLORS["purple_report_hover"]
        )
        self.btn_abps_check.grid(row=5, column=0, columnspan=2, pady=(0, 10))

        # --- Output Tabs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        workcode_tab = notebook.add("Workcode List")
        results_tab = notebook.add("Results Table")
        
        # --- NEW TAB FOR ABPS ---
        abps_tab = notebook.add("ABPS Pending Results")
        
        self._create_log_and_status_area(parent_notebook=notebook)

        # 1. Workcode List Tab
        workcode_tab.grid_columnconfigure(0, weight=1)
        workcode_tab.grid_rowconfigure(1, weight=1)
        
        copy_frame = ctk.CTkFrame(workcode_tab, fg_color="transparent")
        copy_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        self.copy_wc_button = ctk.CTkButton(copy_frame, text="Copy Workcodes", command=self._copy_workcodes)
        self.copy_wc_button.pack(side="left")

        self.run_dup_mr_button = ctk.CTkButton(copy_frame,
                                                  text="Run Duplicate MR Print",
                                                  command=self._run_duplicate_mr,
                                                  fg_color="#D35400", 
                                                  hover_color="#E67E22")
        self.run_dup_mr_button.pack_forget() 

        self.workcode_textbox = ctk.CTkTextbox(workcode_tab, state="disabled")
        self.workcode_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # 2. Results Tab (Table)
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        export_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.export_button = ctk.CTkButton(export_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side="left")

        self.results_tree = ttk.Treeview(results_tab, columns=self.report_headers, show='headings')
        for col in self.report_headers: 
            self.results_tree.heading(col, text=col)
            
        self.results_tree.column("S No.", width=40, anchor='center')
        self.results_tree.column("Panchayat", width=100)
        self.results_tree.column("Work Code", width=200)
        self.results_tree.column("Work Name", width=350)
        self.results_tree.column("Work Category", width=150)
        self.results_tree.column("Work Type", width=150)
        self.results_tree.column("Agency Name", width=100)

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

        # 3. ABPS Pending Results Tab (NEW)
        abps_tab.grid_columnconfigure(0, weight=1)
        abps_tab.grid_rowconfigure(1, weight=1)

        abps_export_frame = ctk.CTkFrame(abps_tab, fg_color="transparent")
        abps_export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.abps_export_button = ctk.CTkButton(abps_export_frame, text="Export ABPS Data", command=self.export_abps_report)
        self.abps_export_button.pack(side="left")

        self.abps_tree = ttk.Treeview(abps_tab, columns=self.abps_report_headers, show='headings')
        for col in self.abps_report_headers:
            self.abps_tree.heading(col, text=col)
        
        self.abps_tree.column("S No.", width=50, anchor="center")
        self.abps_tree.column("Panchayat", width=150)
        self.abps_tree.column("Jobcard No.", width=200)
        self.abps_tree.column("Worker Name", width=250)
        self.abps_tree.column("ABPS Status", width=100, anchor="center")

        self.abps_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        abps_scrollbar = ctk.CTkScrollbar(abps_tab, command=self.abps_tree.yview)
        self.abps_tree.configure(yscroll=abps_scrollbar.set); abps_scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.abps_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.state_menu.configure(state=state)
        self.district_menu.configure(state=state)
        self.block_menu.configure(state=state)
        self.panchayat_menu.configure(state=state)
        self.run_dup_mr_button.configure(state=state)
        self.btn_abps_check.configure(state=state)
        self.abps_export_button.configure(state=state)
    def reset_ui(self) -> None:
        self.state_var.set("")
        self.district_var.set("")
        self.block_var.set("")
        self.panchayat_var.set("")
        
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        for item in self.abps_tree.get_children(): self.abps_tree.delete(item)
        self._update_workcode_textbox("")
        
        self.log_info("Form has been reset.")
        self.update_status("Ready", 0.0)
        

    def start_automation(self) -> None:
        """Standard Issued MR Report Automation (Specific Panchayat)"""
        self.run_dup_mr_button.pack_forget()
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self._update_workcode_textbox("") 
        
        inputs = {
            'state': self.state_var.get().strip(), 
            'district': self.district_var.get().strip(), 
            'block': self.block_var.get().strip(),
            'panchayat': self.panchayat_var.get().strip(),
        }
        
        if not all([inputs['state'], inputs['district'], inputs['block'], inputs['panchayat']]):
            messagebox.showwarning("Input Error", "All fields are required."); return
        
        self.save_inputs(inputs)
        
        driver = self.app.get_driver()
        if not driver:
            messagebox.showwarning("Browser Required", "Kripya pehle 'Launch Chrome' button se browser start karein.")
            return
        
        self.app.after(0, self.set_ui_state, True) 
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def start_abps_automation(self):
        """Logic for the new ABPS Check Button (All Panchayats in Block)"""
        for item in self.abps_tree.get_children(): self.abps_tree.delete(item)
        
        inputs = {
            'state': self.state_entry.get().strip(), 
            'district': self.district_entry.get().strip(), 
            'block': self.block_entry.get().strip(),
            # Panchayat is intentionally ignored here
        }
        
        if not all([inputs['state'], inputs['district'], inputs['block']]):
            messagebox.showwarning("Input Error", "State, District and Block are required."); return
        
        driver = self.app.get_driver()
        if not driver:
            messagebox.showwarning("Browser Required", "Kripya pehle 'Launch Chrome' button se browser start karein.")
            return
        
        self.app.after(0, self.set_ui_state, True) 
        self.app.start_automation_thread(self.automation_key, self.run_abps_automation_logic, args=(inputs,))

    def _solve_captcha(self, driver, wait):
        self.log_info("Attempting to solve CAPTCHA...")
        captcha_label_id = "ContentPlaceHolder1_lblStopSpam"; captcha_textbox_id = "ContentPlaceHolder1_txtCaptcha"; verify_button_id = "ContentPlaceHolder1_btnLogin"
        try:
            captcha_element = wait.until(EC.presence_of_element_located((By.ID, captcha_label_id)))
            captcha_text = captcha_element.text
            match = re.search(r'(\d+)\s*([+\-*])\s*(\d+)', captcha_text)
            if not match: raise ValueError("Could not parse CAPTCHA expression.")
            num1, operator, num2 = match.groups(); num1, num2 = int(num1), int(num2)
            result = 0
            if operator == '+': result = num1 + num2
            elif operator == '-': result = num1 - num2
            elif operator == '*': result = num1 * num2
            self.log_info(f"Solved: {captcha_text.strip()} = {result}")
            driver.find_element(By.ID, captcha_textbox_id).send_keys(str(result))
            driver.find_element(By.ID, verify_button_id).click()
            time.sleep(1.0)  # Short wait after click
            if "Invalid Captcha Code" in driver.page_source:
                raise ValueError("CAPTCHA verification failed.")
            return True
        except TimeoutException:
            self.log_info("CAPTCHA not found or already bypassed.")
            return True 
        except ValueError as e:
            self.log_error(f"CAPTCHA Error: {e}")
            raise 

    def run_automation_logic(self, inputs, retries=1):
        # Standard Issued MR Report Logic (Panchayat Specific)
        self.app.after(0, self.app.set_status, "Starting Issued MR Report...") 
        self.app.after(0, self.update_status, "Initializing...", 0.0)
        self.app.clear_log(self.log_display)
        self.log_info("Starting Issued MR Report automation...")
        try:
            driver = self.app.get_driver()
            if not driver: return 

            wait = WebDriverWait(driver, 20)

            self.app.after(0, self.app.set_status, "Navigating to MIS portal...")
            driver.get(config.MIS_REPORTS_CONFIG["base_url"])

            self._solve_captcha(driver, wait)

            self.log_info(f"Selecting State: {inputs['state']}...")
            state_select = wait.until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_States")))
            self._select_by_text_case_insensitive(Select(state_select), inputs['state'])
            wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Dashboard for Delay Monitoring System")))

            self.log_info("Opening Report...")
            report_link_text = "MGNREGS daily status as per e-muster issued"
            report_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, report_link_text)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", report_link)
            time.sleep(1); report_link.click()

            self.log_info(f"Drilling down to Block: {inputs['block']}")
            wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, inputs['district'].upper()))).click()
            wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, inputs['block'].upper()))).click()

            # --- Specific Panchayat Logic ---
            self.log_info(f"Finding Panchayat: {inputs['panchayat']}")            
            main_table_xpath = "//table[.//b[text()='SNo.'] and .//b[text()='Panchayats']]"
            wait.until(EC.presence_of_element_located((By.XPATH, f"{main_table_xpath}//tr[1]/td/b[text()='Panchayats']")))

            panchayat_row_xpath = f"{main_table_xpath}//tr[td[2][normalize-space()='{inputs['panchayat']}']]"
            panchayat_row = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, panchayat_row_xpath)))

            target_cell = panchayat_row.find_element(By.XPATH, "./td[6]") # Column 6 for MR Issued

            try:
                target_link = target_cell.find_element(By.TAG_NAME, "a")
                link_text = target_link.text.strip()
                if link_text == '0':
                    self.log_warning("Value is 0. No data.")
                    self.success_message = "No data found (Value 0)"
                    return

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_link)
                time.sleep(0.5)
                target_link.click()

            except NoSuchElementException:
                 self.log_warning("No link found in cell.")
                 return

            self.log_info("Scraping final table...")
            FINAL_TABLE_XPATH = "//table[@align='center' and .//b[text()='Work Code']]"
            table = wait.until(EC.presence_of_element_located((By.XPATH, FINAL_TABLE_XPATH)))
            rows = table.find_elements(By.XPATH, ".//tr[position()>1]")

            workcode_list = []
            scraped_mr_count = 0

            for i, row in enumerate(rows):
                if self.is_stopped(): break

                cells = row.find_elements(By.TAG_NAME, "td")
                if not cells or len(cells) < len(self.report_headers): continue

                scraped_data = [cell.text.strip() for cell in cells[:len(self.report_headers)]]
                work_code = scraped_data[2]
                scraped_mr_count += 1
                row_data = tuple(scraped_data)

                self.app.after(0, lambda data=row_data: self.results_tree.insert("", "end", values=data))
                if work_code: workcode_list.append(work_code)

            unique_workcodes = list(dict.fromkeys(workcode_list))
            self.app.after(0, self._update_workcode_textbox, "\n".join(unique_workcodes))

            self.log_success(f"Completed. Found {scraped_mr_count} MRs.")
            self.success_message = f"Found {scraped_mr_count} Issued MRs in {inputs['panchayat']}."

        except Exception as e:
            self.log_error(f"Error: {e}")
            self.success_message = None
        finally:
            # Shared browser use kar rahe hain — isliye driver.quit() nahi karte
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")
            if hasattr(self, 'success_message') and self.success_message:
                self.log_info(f"📊 Issued MR Report Complete: {self.success_message}")

    def run_abps_automation_logic(self, inputs):
        """New Logic for scanning the whole block for ABPS Pending workers."""
        self.app.after(0, self.app.set_status, "Scanning Block for ABPS Pending...") 
        self.app.after(0, self.update_status, "Initializing...", 0.0)
        self.app.clear_log(self.log_display)
        self.log_info("Starting ABPS Pending Scan (All Panchayats)...")
        try:
            driver = self.app.get_driver()
            if not driver: return 
            wait = WebDriverWait(driver, 20)

            # 1. Navigate to Block Dashboard (Reuse logic)
            self.log_info("Navigating to Dashboard...")
            driver.get(config.MIS_REPORTS_CONFIG["base_url"])
            self._solve_captcha(driver, wait)

            state_select = wait.until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_ddl_States")))
            self._select_by_text_case_insensitive(Select(state_select), inputs['state'])
            wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Dashboard for Delay Monitoring System")))

            report_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "MGNREGS daily status as per e-muster issued")))
            report_link.click()

            wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, inputs['district'].upper()))).click()
            wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, inputs['block'].upper()))).click()

            # 2. Scrape All Panchayat Links from Column 5
            self.log_info("Scanning Dashboard for Panchayat Links (Column 5)...")            
            # Use specific XPath for table
            table_xpath = "//table[.//b[text()='Panchayats']]"
            wait.until(EC.presence_of_element_located((By.XPATH, table_xpath)))
            
            # Find all rows (skip headers)
            all_rows = driver.find_elements(By.XPATH, f"{table_xpath}//tr[td]")
            
            panchayat_links = []
            
            for row in all_rows:
                try:
                    # Col 2 = Panchayat Name
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 5: continue
                    
                    p_name = cols[1].text.strip()
                    
                    # --- FILTERS ADDED ---
                    # 1. Skip Total Row
                    if p_name.lower() == "total": continue 
                    # 2. Skip Number Row (Header like "1", "2"...) - Yahi error de raha tha
                    if p_name.isdigit(): continue
                    
                    # Col 5 = Expected Labour (Link)
                    try:
                        link_elem = cols[4].find_element(By.TAG_NAME, "a")
                        href = link_elem.get_attribute("href")
                        
                        # Only add if it's a real link, not a javascript postback (sorting arrows)
                        if href and "javascript" not in href.lower():
                            panchayat_links.append((p_name, href))
                    except NoSuchElementException:
                        # Value is 0 or text, skip
                        pass
                except Exception:
                    pass
            
            total_gps = len(panchayat_links)
            self.log_info(f"Found {total_gps} Panchayats with data to scan.")            
            if total_gps == 0:
                self.log_warning("No data found in Column 5 for any Panchayat.")
                return

            # 3. Iterate through each Panchayat Link
            count = 0
            for index, (p_name, href) in enumerate(panchayat_links):
                if self.is_stopped(): break
                
                progress = (index / total_gps)
                self.app.after(0, self.update_status, f"Scanning {p_name}...", progress)
                self.log_info(f"Checking Panchayat: {p_name} ({index+1}/{total_gps})")                
                try:
                    driver.get(href) # Direct navigation
                    
                    # Wait for Detail Table
                    detail_table_id = "ContentPlaceHolder1_GridFtomusteroll"
                    
                    # Short timeout check, if no data, skip
                    try:
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, detail_table_id)))
                    except TimeoutException:
                        self.log_info(f"   > No table found for {p_name}. Skipping.")
                        continue

                    # Scan Rows
                    # Get rows where Last Column (ABPS) contains "No"
                    # Optimization: Get all rows first
                    rows = driver.find_elements(By.XPATH, f"//table[@id='{detail_table_id}']//tr[position()>1]")
                    
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if not cells: continue
                        
                        # Indices (0-based):
                        # 1: Jobcard No
                        # 2: Worker Name
                        # Last: ABPS Enabled
                        
                        abps_status = cells[-1].text.strip()
                        
                        if abps_status.lower() == "no":
                            count += 1
                            jobcard = cells[1].text.strip()
                            name = cells[2].text.strip()
                            
                            row_data = (count, p_name, jobcard, name, "No")
                            self.app.after(0, lambda data=row_data: self.abps_tree.insert("", "end", values=data))
                            
                except Exception as e:
                    self.log_error(f"   > Error scanning {p_name}: {str(e)[:50]}")
                    continue

            self.success_message = f"ABPS Scan Complete. Found {count} pending workers."
            self.log_success(self.success_message)
        except Exception as e:
            self.log_error(f"Critical Error in ABPS Scan: {e}")
            self.success_message = None
        finally:
            # Shared browser use kar rahe hain — isliye driver.quit() nahi karte
            self.app.after(0, self.set_ui_state, False)
            if hasattr(self, 'success_message') and self.success_message:
                self.log_info(f"📊 Issued MR Complete: {self.success_message}")

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

    def _run_duplicate_mr(self):
        workcodes = self.workcode_textbox.get("1.0", tkinter.END).strip()
        panchayat_name = self.panchayat_var.get().strip()

        if not workcodes:
            messagebox.showwarning("No Data", "There are no workcodes to send.", parent=self)
            return
        
        if not panchayat_name:
            messagebox.showwarning("No Data", "Panchayat name is missing.", parent=self)
            return

        self.app.switch_to_duplicate_mr_with_data(workcodes, panchayat_name)

    def export_report(self):
        """Export results to professional Excel."""
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "There are no results to export.")
            return

        panchayat = self.panchayat_var.get().strip() or "Report"
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', panchayat)
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"Issued_MR_{safe_panchayat}-{current_date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=f"Issued MR Report - {panchayat}"
        )

    def export_abps_report(self):
        """Export ABPS report to professional Excel."""
        if not self.abps_tree.get_children():
            messagebox.showinfo("No Data", "There are no ABPS results to export.")
            return
            
        block = self.block_var.get().strip() or "Block"
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', block)
        current_date_str = datetime.now().strftime("%d-%b-%Y")
        
        self.export_treeview_to_excel(
            tree=self.abps_tree,
            default_filename=f"ABPS_Pending_Report_{safe_name}_{current_date_str}.xlsx",
            filter_mode="Export All",
            title_prefix=f"ABPS Pendency Report - {block}"
        )
                

    def generate_report_pdf(self, data, headers, col_widths, title, date_str, file_path):
        return super().generate_report_pdf(data, headers, col_widths, title, date_str, file_path)

    def _wrap_text(self, text, font, max_width):
        return super()._wrap_text(text, font, max_width)

        
    def save_inputs(self, inputs):
        save_data = {k: inputs.get(k) for k in ('state', 'district', 'block', 'panchayat')}
        try:
            self.app.history_manager.save_tab_inputs_batch("issued_mr_report", save_data)
        except Exception as e:
            logger.warning("Failed to save Issued MR inputs: %s", e)

    def load_inputs(self):
        """Load previously saved inputs from DB."""
        try:
            data = self.app.history_manager.get_tab_inputs("issued_mr_report")
            if data:
                self.state_var.set(data.get('state', ''))
                self.district_var.set(data.get('district', ''))
                self.block_var.set(data.get('block', ''))
                self.panchayat_var.set(data.get('panchayat', ''))
        except Exception as e:
            logger.warning("Failed to load Issued MR inputs: %s", e)