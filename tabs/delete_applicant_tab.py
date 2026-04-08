# tabs/delete_applicant_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import csv
import time
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, UnexpectedAlertPresentException

import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class DeleteApplicantTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="delete_applicant")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.csv_data = [] # To store loaded CSV data
        
        self._create_widgets()
        
    def _create_widgets(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_container.grid_columnconfigure(0, weight=1)

        # --- Top Input Frame (General Details) ---
        input_frame = ctk.CTkFrame(main_container)
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        input_frame.grid_columnconfigure(1, weight=1)
        input_frame.grid_columnconfigure(3, weight=1)

        # Row 0
        ctk.CTkLabel(input_frame, text="Panchayat (For Block Login):").grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.panchayat_entry = AutocompleteEntry(
            input_frame, 
            placeholder_text="Leave blank for GP Login",
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app, 
            history_key="panchayat_name",
            width=220, height=30
        )
        self.panchayat_entry.grid(row=0, column=1, padx=15, pady=10, sticky="ew")

        ctk.CTkLabel(input_frame, text="Reason for Deletion:").grid(row=0, column=2, padx=15, pady=10, sticky="w")
        reason_options = [
            "Person Expired", 
            "Voluntary Surrender", 
            "Person shifted to a new family", 
            "Duplicate Applicant", 
            "Fake Applicant"
        ]
        self.reason_var = ctk.StringVar(value=reason_options[2])
        self.reason_menu = ctk.CTkOptionMenu(input_frame, variable=self.reason_var, values=reason_options, width=220, height=30)
        self.reason_menu.grid(row=0, column=3, padx=15, pady=10, sticky="ew")

        # Row 1
        ctk.CTkLabel(input_frame, text="Deletion Date (DD/MM/YYYY):").grid(row=1, column=0, padx=15, pady=10, sticky="w")
        date_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        date_frame.grid(row=1, column=1, sticky="ew", padx=15, pady=10)
        self.del_date_entry = ctk.CTkEntry(date_frame, placeholder_text="DD/MM/YYYY", height=30)
        self.del_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(date_frame, text="📅", width=35, height=30, fg_color=("gray85", "gray25"), text_color=("black", "white"),
                    command=lambda: self.open_date_picker(lambda d: [self.del_date_entry.delete(0, "end"), self.del_date_entry.insert(0, d)])).pack(side="right", padx=(5,0))

        # --- CSV Upload Frame ---
        csv_frame = ctk.CTkFrame(main_container)
        csv_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        csv_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(csv_frame, text="Upload Applicant Data (CSV):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        btn_frame = ctk.CTkFrame(csv_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="w", padx=15, pady=10)
        
        self.upload_btn = ctk.CTkButton(btn_frame, text="Browse CSV File", command=self.load_csv, width=150, fg_color="#3B82F6", hover_color="#2563EB")
        self.upload_btn.pack(side="left", padx=(0, 10))
        
        self.csv_status_lbl = ctk.CTkLabel(btn_frame, text="No file loaded.", text_color="gray60")
        self.csv_status_lbl.pack(side="left")

        demo_btn = ctk.CTkButton(csv_frame, text="Download Demo CSV", command=self._download_demo_csv, width=150, fg_color="transparent", border_width=1, text_color=("black", "white"))
        demo_btn.grid(row=0, column=2, padx=15, pady=10, sticky="e")

        # --- Action Buttons ---
        action_frame = self._create_action_buttons(main_container)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        # --- Notebook for Results & Logs ---
        notebook = ctk.CTkTabview(main_container)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(notebook)

        # Results Tab
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(0, weight=1)
        cols = ("Timestamp", "Jobcard No", "Applicant Name", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=80); self.results_tree.column("Jobcard No", width=150); self.results_tree.column("Applicant Name", width=150); self.results_tree.column("Status", width=100); self.results_tree.column("Details", width=300)
        self.results_tree.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        self.style_treeview(self.results_tree)

    def _download_demo_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="demo_delete_applicant.csv", title="Save Demo CSV")
        if file_path:
            try:
                with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Jobcard", "Applicant Name"])
                    writer.writerow(["JH-22-003-007-002/31", "BEDAN MURMU"])
                    writer.writerow(["JH-22-003-007-002/31", "MAKKU MARANDI"])
                messagebox.showinfo("Success", f"Demo CSV saved to:\n{file_path}", parent=self.app)
            except Exception as e:
                messagebox.showerror("Error", f"Could not save demo file:\n{e}", parent=self.app)

    def load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")], title="Select Applicant CSV")
        if not file_path: return
        
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = [h.lower().strip() for h in reader.fieldnames]
                
                # Basic column matching
                jc_col = next((h for h in headers if "jobcard" in h or "job card" in h), None)
                name_col = next((h for h in headers if "applicant" in h or "name" in h), None)
                
                if not jc_col or not name_col:
                    messagebox.showerror("Invalid CSV", "CSV must contain columns for 'Jobcard' and 'Applicant Name'.", parent=self.app)
                    return
                
                self.csv_data = []
                for row in reader:
                    # Map back to lowercase keys for safety
                    row_lower = {k.lower().strip(): v for k, v in row.items()}
                    jc = row_lower.get(jc_col, "").strip()
                    name = row_lower.get(name_col, "").strip()
                    if jc and name:
                        self.csv_data.append({"jobcard": jc, "applicant_name": name})
                
                if self.csv_data:
                    self.csv_status_lbl.configure(text=f"Loaded {len(self.csv_data)} applicants.", text_color="#10B981")
                    self.app.log_message(self.log_display, f"CSV Loaded: {len(self.csv_data)} records ready.")
                else:
                    self.csv_status_lbl.configure(text="CSV is empty.", text_color="#EF4444")
                    
        except Exception as e:
            messagebox.showerror("Error Reading CSV", f"An error occurred:\n{e}", parent=self.app)

    def _get_inputs(self):
        return {
            "panchayat": self.panchayat_entry.get().strip(),
            "reason": self.reason_var.get(),
            "date": self.del_date_entry.get().strip(),
            "data": self.csv_data
        }

    def start_automation(self):
        inputs = self._get_inputs()
        if not inputs["date"] or not inputs["data"]:
            messagebox.showwarning("Missing Input", "Deletion Date and a valid CSV upload are required.")
            return
            
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_common_ui_state, True)
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        
        driver = self.app.get_driver()
        if not driver:
            self.app.after(0, self.set_common_ui_state, False)
            return

        wait = WebDriverWait(driver, 15)
        
        # 1. Group data by Jobcard to minimize loading pages multiple times
        grouped_data = {}
        for item in inputs["data"]:
            jc = item["jobcard"].upper()
            name = item["applicant_name"].upper()
            if jc not in grouped_data:
                grouped_data[jc] = []
            grouped_data[jc].append(name)

        total_jc = len(grouped_data)
        
        try:
            # Main Loop
            for i, (jobcard, names_to_delete) in enumerate(grouped_data.items()):
                if self.app.stop_events[self.automation_key].is_set(): break
                
                self.update_status(f"Processing Jobcard: {jobcard}", (i+1)/total_jc)
                self.app.log_message(self.log_display, f"\n--- Processing Jobcard: {jobcard} ---")

                driver.get(config.DELETE_APPLICANT_CONFIG["url"])
                
                # A. Select Panchayat (If Block Login)
                if inputs['panchayat']:
                    try:
                        panchayat_dd = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpnch")))
                        Select(panchayat_dd).select_by_visible_text(inputs['panchayat'])
                        time.sleep(1) # wait for postback
                    except TimeoutException:
                        self.app.log_message(self.log_display, "Panchayat dropdown not found, assuming GP login.")
                
                # B. Smart Village Selection
                self.app.log_message(self.log_display, "Selecting Village intelligently...")
                village_dd_element = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlvillage")))
                village_dd = Select(village_dd_element)
                
                # Extract village code from jobcard
                try:
                    v_code = jobcard.split('/')[0].split('-')[-1]
                    found_village = False
                    for opt in village_dd.options:
                        if opt.get_attribute("value").endswith(v_code):
                            village_dd.select_by_value(opt.get_attribute("value"))
                            found_village = True
                            break
                            
                    if not found_village:
                        self._log_result(jobcard, "All", "Failed", f"Could not auto-detect village code '{v_code}'.")
                        continue
                except Exception as e:
                    self._log_result(jobcard, "All", "Failed", "Invalid Jobcard format for Village detection.")
                    continue
                    
                time.sleep(1.5) # Wait for Reg Dropdown postback

                # C. Select Registration No (Jobcard)
                self.app.log_message(self.log_display, "Selecting Registration No...")
                reg_dd = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlReg"))))
                found_reg = False
                for opt in reg_dd.options:
                    if opt.text.upper() == jobcard:
                        reg_dd.select_by_visible_text(opt.text)
                        found_reg = True
                        break
                
                if not found_reg:
                    self._log_result(jobcard, "All", "Failed", "Jobcard not found in this village.")
                    continue
                    
                time.sleep(1.5) # Wait for Table postback

                # D. Process Table Rows
                self.app.log_message(self.log_display, "Processing Applicant Table...")
                try:
                    table = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_grdData")))
                    rows = table.find_elements(By.TAG_NAME, "tr")[1:] # Skip header
                    
                    checked_count = 0
                    
                    for row in rows:
                        try:
                            # Safely find elements in the row
                            name_input = row.find_element(By.XPATH, ".//input[contains(@id, '_txtName')]")
                            app_name = name_input.get_attribute("value").strip().upper()
                            
                            if app_name in names_to_delete:
                                chk_box = row.find_element(By.XPATH, ".//input[contains(@id, '_chkDelete')]")
                                
                                # FIX: Removed the safety check for Orange Cell / Disabled status.
                                # Using JavaScript to force click the checkbox no matter what.
                                if not chk_box.is_selected():
                                    driver.execute_script("arguments[0].click();", chk_box)
                                
                                reason_dd = Select(row.find_element(By.XPATH, ".//select[contains(@id, '_ddlReason')]"))
                                reason_dd.select_by_visible_text(inputs["reason"])
                                
                                date_input = row.find_element(By.XPATH, ".//input[contains(@id, '_txtDate')]")
                                date_input.clear()
                                date_input.send_keys(inputs["date"])
                                date_input.send_keys(Keys.TAB)
                                
                                checked_count += 1
                                self.app.log_message(self.log_display, f"Filled deletion details for: {app_name}")
                                
                        except NoSuchElementException:
                            continue # Ignore empty/invalid rows

                    # E. Submit & Check Success
                    if checked_count > 0:
                        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_BtnDelete").click()
                        
                        try:
                            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                            alert_text = alert.text
                            alert.accept()
                            
                            if "cannot delete all the applicant" in alert_text.lower():
                                self._log_result(jobcard, "Multiple", "Failed", "Server blocked: Cannot delete ALL applicants using this option.")
                            else:
                                self._log_result(jobcard, f"{checked_count} Processed", "Success", f"Alert accepted: {alert_text}")
                        except TimeoutException:
                            self._log_result(jobcard, f"{checked_count} Processed", "Success", "Form submitted successfully.")
                    else:
                        self.app.log_message(self.log_display, "No valid applicants found to delete in this jobcard.", "warning")

                except Exception as e:
                    self._log_result(jobcard, "All", "Failed", f"Error interacting with table: {str(e).splitlines()[0]}")

        except Exception as e:
            self.handle_error(e)
            
        finally:
            self.app.after(0, self.set_common_ui_state, False)
            self.update_status("Task Finished", 1.0)
            messagebox.showinfo("Complete", "Applicant Deletion Automation finished.")

    def _log_result(self, jobcard, name, status, details):
        ts = datetime.now().strftime("%H:%M:%S")
        tags = ('success',) if 'success' in status.lower() else ('warning',) if 'skipped' in status.lower() else ('failed',)
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(ts, jobcard, name, status, details), tags=tags))

    def reset_ui(self):
        super().reset_ui()
        self.csv_data = []
        self.csv_status_lbl.configure(text="No file loaded.", text_color="gray60")
        for item in self.results_tree.get_children(): self.results_tree.delete(item)