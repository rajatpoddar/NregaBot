# tabs/sarkar_aapke_dwar_tab.py
import tkinter
from tkinter import messagebox, filedialog, ttk
import customtkinter as ctk
import json
import os, time, csv, re, sys, subprocess
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from .base_tab import BaseAutomationTab

class SarkarAapkeDwarTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="sad_auto")
        self.config_file = self.app.get_data_path("sad_inputs.json")
        
        self.backlog_mode_var = ctk.BooleanVar(value=False)
        self.success_count = 0
        self.fail_count = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._create_widgets()
        self.load_inputs()

    def _create_widgets(self):
        # --- Configuration Frame ---
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        controls_frame.grid_columnconfigure(1, weight=1)

        # --- Header Row ---
        header_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(5, 0))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Sarkar Aapke Dwar Automation", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=10)
        
        self.backlog_switch = ctk.CTkSwitch(
            header_frame, 
            text="Backlog Entry Mode", 
            variable=self.backlog_mode_var,
            onvalue=True, 
            offvalue=False,
            command=self._on_mode_switch
        )
        self.backlog_switch.pack(side="right", padx=10)

        # --- MODE 1: Bulk Upload (Excel/CSV) ---
        bulk_frame = ctk.CTkFrame(controls_frame, fg_color=("gray90", "gray20"))
        bulk_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        bulk_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bulk_frame, text="Mode 1: Bulk Entry (via Excel or CSV)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=5)
        
        self.file_path_entry = ctk.CTkEntry(bulk_frame, placeholder_text="Select .xlsx or .csv file with Applicant Details...")
        self.file_path_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        btn_frame = ctk.CTkFrame(bulk_frame, fg_color="transparent")
        btn_frame.grid(row=1, column=2, padx=5)
        
        ctk.CTkButton(btn_frame, text="Browse", width=80, command=self.browse_file).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Get Template", width=100, fg_color="green", command=self.generate_demo_template).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Clear", width=60, fg_color="#C53030", hover_color="#9B2C2C", command=self.clear_file_selection).pack(side="left", padx=2)
        
        note_text = ("ℹ️ Monitor Mode: Leave File empty. Bot auto-fills Scheme details when you open a new form.\n"
                     "ℹ️ Bulk Mode: Select Excel/CSV. Bot fills Applicant + Scheme details and Extracts Ack No.\n"
                     "ℹ️ Manual Remarks: To enter remarks manually in the UI, click 'Clear' to unlock the fields.")
        
        ctk.CTkLabel(bulk_frame, text=note_text, text_color="gray60", 
                     font=ctk.CTkFont(size=11), justify="left", anchor="w").grid(row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(5, 5))

        # --- Settings ---
        settings_frame = ctk.CTkFrame(controls_frame)
        settings_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        settings_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(settings_frame, text="Common Settings", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # 1. Applicant Remarks
        ctk.CTkLabel(settings_frame, text="Applicant Remarks:").grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self.app_remarks_entry = ctk.CTkEntry(settings_frame, placeholder_text="Default Applicant Remarks (if not in file)")
        self.app_remarks_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=10, pady=2)

        # 2. Scheme Type Dropdown
        ctk.CTkLabel(settings_frame, text="Scheme Type:").grid(row=2, column=0, sticky="w", padx=10, pady=2)
        scheme_types = ["Service Focus Area"] 
        self.scheme_type_combobox = ctk.CTkComboBox(settings_frame, values=scheme_types, width=300)
        self.scheme_type_combobox.set("Service Focus Area")
        self.scheme_type_combobox.grid(row=2, column=1, columnspan=2, sticky="ew", padx=10, pady=2)

        # 3. Scheme/Service Dropdown
        ctk.CTkLabel(settings_frame, text="Scheme/Service:").grid(row=3, column=0, sticky="w", padx=10, pady=2)
        service_options = [
            "जाति प्रमाण पत्र (Caste Certificate)",
            "आय प्रमाण पत्र (Income Certificate)",
            "जन्म प्रमाण पत्र (Birth Certificate)",
            "मृत्यु प्रमाण पत्र (Death Certificate)",
            "दाखिल खारिज वादों का निष्पादन (Mutation/Disposal of Land Cases)",
            "भूमि की मापी (Measurement of Land)",
            "भूमि धारण प्रमाण पत्र (Land Holding Certificate)",
            "नया राशन कार्ड (New Ration Card)",
            "स्थानीय निवासी प्रमाण पत्र (Local Resident Certificate)",
            "वृद्धा पेंशन (Old Age Pension)",
            "विधवा पेंशन (Widow Pension)",
            "विकलांग पेंशन (Disability Pension)",
            "झारखंड राज्य सेवा देने की गारंटी अधिनियम 2011 से जुड़ी अन्य सेवाएं",
            "अन्य लोक कल्याणकारी योजनाएँ (Other Welfare Schemes)"
        ]
        self.service_combobox = ctk.CTkComboBox(settings_frame, values=service_options, width=300)
        self.service_combobox.grid(row=3, column=1, columnspan=2, sticky="ew", padx=10, pady=2)

        # 4. Scheme Remarks
        ctk.CTkLabel(settings_frame, text="Scheme Remarks:").grid(row=4, column=0, sticky="w", padx=10, pady=2)
        self.scheme_remarks_entry = ctk.CTkEntry(settings_frame, placeholder_text="Default Scheme Remarks (if not in file)")
        self.scheme_remarks_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=10, pady=2)

        # Action Buttons
        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=15)

        # --- Results & Logs Notebook ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tab_view.add("Results")
        self.tab_view.add("Logs")

        # --- TAB 1: Results (Treeview) with Export ---
        res_tab = self.tab_view.tab("Results")
        res_tab.grid_columnconfigure(0, weight=1)
        res_tab.grid_rowconfigure(1, weight=1)

        # Export Controls
        export_frame = ctk.CTkFrame(res_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.export_button = ctk.CTkButton(export_frame, text="Export Result", width=100, command=self.export_report)
        self.export_button.pack(side="left", padx=(0, 5))
        
        self.export_format_menu = ctk.CTkOptionMenu(export_frame, width=120, values=["PDF (.pdf)", "CSV (.csv)"], command=self._on_format_change)
        self.export_format_menu.pack(side="left", padx=5)
        
        self.export_filter_menu = ctk.CTkOptionMenu(export_frame, width=120, values=["Export All", "Success Only", "Failed Only"])
        self.export_filter_menu.pack(side="left", padx=5)

        # Treeview
        cols = ("Time", "Applicant Name", "Scheme Remarks", "Status", "Ack Number")
        self.results_tree = ttk.Treeview(res_tab, columns=cols, show='headings')
        
        self.results_tree.heading("Time", text="Time")
        self.results_tree.heading("Applicant Name", text="Applicant Name")
        self.results_tree.heading("Scheme Remarks", text="Scheme Remarks") 
        self.results_tree.heading("Status", text="Status")
        self.results_tree.heading("Ack Number", text="Ack Number")

        self.results_tree.column("Time", width=80, anchor="center")
        self.results_tree.column("Applicant Name", width=150, anchor="w")
        self.results_tree.column("Scheme Remarks", width=150, anchor="w")
        self.results_tree.column("Status", width=80, anchor="center")
        self.results_tree.column("Ack Number", width=200, anchor="w")

        self.results_tree.grid(row=1, column=0, sticky="nsew")
        
        vsb = ctk.CTkScrollbar(res_tab, orientation="vertical", command=self.results_tree.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=vsb.set)

        self.style_treeview(self.results_tree)
        self.results_tree.tag_configure('Success', foreground='green')
        self.results_tree.tag_configure('Failed', foreground='red')
        self.results_tree.tag_configure('Info', foreground='#2B6CB0')

        # Summary Label
        self.summary_label = ctk.CTkLabel(res_tab, text="Success: 0 | Failed: 0", font=ctk.CTkFont(weight="bold"))
        self.summary_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)

        # --- TAB 2: Logs ---
        log_tab = self.tab_view.tab("Logs")
        log_tab.grid_columnconfigure(0, weight=1)
        log_tab.grid_rowconfigure(0, weight=1)
        
        self.log_display = ctk.CTkTextbox(log_tab, state="disabled", font=("Consolas", 12))
        self.log_display.grid(row=0, column=0, sticky="nsew")

        # Status Bar
        status_frame = ctk.CTkFrame(self, height=30, fg_color="transparent")
        status_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
        
        self.progress_bar = ctk.CTkProgressBar(status_frame, height=8)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", expand=True)

    def _on_mode_switch(self):
        pass

    def _on_format_change(self, selected_format):
        if "CSV" in selected_format: self.export_filter_menu.configure(state="disabled")
        else: self.export_filter_menu.configure(state="normal")

    def _log_result(self, name, scheme_rem, status, ack_no):
        """Adds a row to the Result Treeview."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = 'Success' if status == 'Success' else ('Failed' if status == 'Failed' else 'Info')
        
        self.results_tree.insert("", "0", values=(timestamp, name, scheme_rem, status, ack_no), tags=(tag,))
        
        if status == "Success": self.success_count += 1
        elif status == "Failed": self.fail_count += 1
            
        self.summary_label.configure(text=f"Success: {self.success_count} | Failed: {self.fail_count}")

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        
        # We handle remarks state separately if a file is loaded
        has_file = bool(self.file_path_entry.get().strip())
        
        if running:
             self.app_remarks_entry.configure(state="disabled")
             self.scheme_remarks_entry.configure(state="disabled")
        elif not has_file:
             self.app_remarks_entry.configure(state="normal")
             self.scheme_remarks_entry.configure(state="normal")
             
        self.scheme_type_combobox.configure(state=state)
        self.service_combobox.configure(state=state)
        self.file_path_entry.configure(state=state)
        self.backlog_switch.configure(state=state)
        self.export_button.configure(state=state)
        
        if state == "normal": self._on_format_change(self.export_format_menu.get())

    def _update_remarks_state(self, has_file):
        """Disables remark fields if file is loaded, indicating file data takes precedence."""
        state = "disabled" if has_file else "normal"
        # Visual cue is automatic with state change in CustomTkinter
        self.app_remarks_entry.configure(state=state)
        self.scheme_remarks_entry.configure(state=state)

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel/CSV Files", "*.csv *.xlsx"), ("Excel Files", "*.xlsx")])
        if file_path:
            self.file_path_entry.delete(0, tkinter.END)
            self.file_path_entry.insert(0, file_path)
            self._update_remarks_state(True) # Disable UI remarks

    def clear_file_selection(self):
        self.file_path_entry.delete(0, tkinter.END)
        self._update_remarks_state(False) # Enable UI remarks

    def generate_demo_template(self):
        # UPDATED: Added Applicant Remarks and Scheme Remarks columns
        headers = [
            "Applicant Name", "Father/Husband Name", "Age", "Mobile No", 
            "Is WhatsApp (Y/N)", "Village", "Address", 
            "Applicant Remarks", "Scheme Remarks"
        ]
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], initialfile="SAD_Bulk_Template.csv")
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    csv.writer(f).writerow(headers)
                messagebox.showinfo("Success", "Template saved with Remark columns!")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")

    def start_automation(self):
        inputs = {
            'file_path': self.file_path_entry.get().strip(),
            'app_remarks': self.app_remarks_entry.get().strip(),
            'scheme_type': self.scheme_type_combobox.get().strip(),
            'service': self.service_combobox.get().strip(),
            'scheme_remarks': self.scheme_remarks_entry.get().strip(),
            'is_backlog': self.backlog_mode_var.get()
        }

        if not inputs['scheme_type'] or not inputs['service']:
            messagebox.showwarning("Input Error", "Please select 'Scheme Type' and 'Service'.")
            return

        if inputs['file_path'] and not os.path.exists(inputs['file_path']):
            messagebox.showerror("File Error", "Selected file does not exist.")
            return

        self.save_inputs(inputs)
        self.success_count = 0
        self.fail_count = 0
        self.summary_label.configure(text="Success: 0 | Failed: 0")
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
            
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def _read_file_data(self, file_path):
        """Reads data from CSV (robust) or Excel."""
        data = []
        if file_path.lower().endswith(".xlsx"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                sheet = wb.active
                rows = list(sheet.iter_rows(values_only=True))
                if not rows: return []
                headers = [str(h).strip() for h in rows[0] if h]
                for row in rows[1:]:
                    if not any(row): continue
                    row_dict = {}
                    for i, header in enumerate(headers):
                        val = row[i] if i < len(row) else ""
                        row_dict[header] = str(val).strip() if val is not None else ""
                    data.append(row_dict)
                return data
            except ImportError: raise Exception("Install openpyxl to read Excel.")
            except Exception as e: raise Exception(f"Excel Error: {e}")
        else:
            for enc in ['utf-8-sig', 'cp1252', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        return list(csv.DictReader(f))
                except: continue
            raise Exception("Failed to read CSV.")

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.tab_view.set("Results")
        
        try:
            driver = self.app.get_driver()
            if not driver: return
            wait = WebDriverWait(driver, 10)

            mode_str = "Backlog" if inputs['is_backlog'] else "Normal"
            
            if inputs['file_path']:
                self.app.log_message(self.log_display, f"Starting BULK Mode ({mode_str})...")
                self._run_bulk_mode(driver, wait, inputs)
            else:
                self.app.log_message(self.log_display, f"Starting MONITOR Mode ({mode_str})...")
                self._run_monitor_mode(driver, wait, inputs)

        except Exception as e:
            self.app.log_message(self.log_display, f"Critical Error: {e}", "error")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")
            self.app.after(0, self.progress_bar.set, 0)

    def _run_bulk_mode(self, driver, wait, inputs):
        try:
            data = self._read_file_data(inputs['file_path'])
        except Exception as e:
            self.app.log_message(self.log_display, str(e), "error")
            return

        total = len(data)
        url_fragment = "application/createBackLog" if inputs['is_backlog'] else "application/create"
        target_url = f"https://sarkaraapkedwar.jharkhand.gov.in/#/{url_fragment}"
        
        self.app.log_message(self.log_display, f"Loaded {total} records.")

        for i, row in enumerate(data):
            if self.app.stop_events[self.automation_key].is_set(): break
            
            applicant_name = row.get("Applicant Name", "").strip()
            status_msg = f"Processing {i+1}/{total}: {applicant_name}"
            
            # --- Logic to prioritize Remarks from File ---
            row_app_remark = row.get("Applicant Remarks", "").strip()
            final_app_remark = row_app_remark if row_app_remark else inputs['app_remarks']

            row_scheme_remark = row.get("Scheme Remarks", "").strip()
            final_scheme_remark = row_scheme_remark if row_scheme_remark else inputs['scheme_remarks']
            # ---------------------------------------------
            
            self.app.after(0, self.app.set_status, status_msg)
            self.app.after(0, self.progress_bar.set, (i+1)/total)
            
            try:
                if url_fragment not in driver.current_url:
                    driver.get(target_url)
                    time.sleep(2)

                wait.until(EC.presence_of_element_located((By.NAME, "applicantName")))

                # 1. Fill Applicant
                self._safe_send_keys(driver, "applicantName", applicant_name)
                self._safe_send_keys(driver, "fatherHusbandName", row.get("Father/Husband Name", ""))
                self._safe_send_keys(driver, "age", row.get("Age", ""))
                self._safe_send_keys(driver, "mobileNo", row.get("Mobile No", ""))
                
                is_whatsapp = row.get("Is WhatsApp (Y/N)", "N").upper()
                try:
                    chk = driver.find_element(By.ID, "isWhatsAppMobile")
                    if (is_whatsapp.startswith("Y") and not chk.selected) or (is_whatsapp.startswith("N") and chk.selected):
                        chk.click()
                except: pass

                # Village
                village = row.get("Village", "")
                if village:
                    try:
                        village_input = driver.find_element(By.ID, "react-select-2-input")
                        village_input.send_keys(village); time.sleep(1)
                        village_input.send_keys(Keys.ENTER)
                    except: pass

                self._safe_send_keys(driver, "address", row.get("Address", ""))
                self._safe_send_keys(driver, "remarks", final_app_remark)

                # 2. Fill Scheme
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                try:
                    Select(driver.find_element(By.NAME, "schemeId")).select_by_visible_text(inputs['scheme_type'])
                    time.sleep(1) 
                except:
                    self._log_result(applicant_name, final_scheme_remark, "Failed", "Scheme Type Error")
                    continue

                try:
                    svc_select = Select(wait.until(EC.presence_of_element_located((By.NAME, "schemeService"))))
                    try: svc_select.select_by_visible_text(inputs['service'])
                    except:
                        found = False
                        for opt in svc_select.options:
                            if inputs['service'].lower() in opt.text.lower():
                                svc_select.select_by_visible_text(opt.text); found = True; break
                        if not found:
                            self._log_result(applicant_name, final_scheme_remark, "Failed", "Service Error")
                            continue
                except: pass

                self._safe_send_keys(driver, "schemeRemarks", final_scheme_remark)

                # 3. Submit & Extract Ack No
                try:
                    driver.find_element(By.XPATH, "//button[contains(., 'Add Service')]").click()
                    time.sleep(1)
                    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Create Application')]"))).click()
                    
                    # --- EXTRACT ACKNOWLEDGEMENT ---
                    ack_number = "N/A"
                    try:
                        # Wait for popup (SweetAlert)
                        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "swal2-popup")))
                        
                        # Get text
                        popup_text = ""
                        try: popup_text = driver.find_element(By.CLASS_NAME, "swal2-content").text
                        except: 
                            try: popup_text = driver.find_element(By.CLASS_NAME, "swal2-html-container").text
                            except: pass
                        
                        # Regex Extract: 3/28/1913/3608040
                        match = re.search(r'Acknowledgement No is\s*:\s*([\d/]+)', popup_text)
                        if match:
                            ack_number = match.group(1)
                        
                        # Close popup
                        try: driver.find_element(By.CSS_SELECTOR, "button.swal2-confirm").click()
                        except: pass
                        
                    except Exception as e:
                        self.app.log_message(self.log_display, f"Popup Error: {e}", "warning")

                    # Reset form for next entry
                    try:
                        driver.find_element(By.XPATH, "//button[contains(., 'Reset')]").click()
                        time.sleep(1)
                    except: driver.refresh(); time.sleep(2)

                    self._log_result(applicant_name, final_scheme_remark, "Success", ack_number)
                except Exception as e:
                    self._log_result(applicant_name, final_scheme_remark, "Failed", f"Submit Error: {e}")

            except Exception as e:
                self._log_result(applicant_name, final_scheme_remark, "Failed", str(e))
                driver.refresh(); time.sleep(3)

    def _run_monitor_mode(self, driver, wait, inputs):
        self.app.log_message(self.log_display, "Monitor Mode Active. Waiting for form...")
        last_log_time = 0

        while not self.app.stop_events[self.automation_key].is_set():
            try:
                curr_url = driver.current_url
                if "application/create" not in curr_url and "application/createBackLog" not in curr_url:
                    if time.time() - last_log_time > 8:
                        self.app.after(0, self.app.set_status, "Waiting for Entry Page...")
                        last_log_time = time.time()
                    time.sleep(2); continue

                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    if len(rows) > 0 and "No data" not in rows[0].text:
                        time.sleep(2); continue
                except: pass

                try:
                    scheme_dd = driver.find_element(By.NAME, "schemeId")
                    select_obj = Select(scheme_dd)
                    val = select_obj.first_selected_option.get_attribute("value")

                    if val == "-1" or "Select" in select_obj.first_selected_option.text:
                        app_name = "Unknown"
                        try:
                            app_name = driver.find_element(By.NAME, "applicantName").get_attribute("value")
                            if not app_name: app_name = "New Applicant"
                        except: pass
                        
                        self.app.after(0, self.app.set_status, "Auto-filling Form...")
                        
                        if inputs['app_remarks']: self._safe_send_keys(driver, "remarks", inputs['app_remarks'])
                        
                        try: select_obj.select_by_visible_text(inputs['scheme_type'])
                        except: time.sleep(2); continue

                        time.sleep(1)
                        svc_select = Select(driver.find_element(By.NAME, "schemeService"))
                        
                        for _ in range(10):
                            if len(svc_select.options) > 1: break
                            time.sleep(0.5)
                        
                        try:
                            try: svc_select.select_by_visible_text(inputs['service'])
                            except:
                                for opt in svc_select.options:
                                    if inputs['service'].lower() in opt.text.lower():
                                        svc_select.select_by_visible_text(opt.text); break
                        except: pass
                        
                        if inputs['scheme_remarks']: self._safe_send_keys(driver, "schemeRemarks", inputs['scheme_remarks'])
                        
                        try:
                            driver.find_element(By.XPATH, "//button[contains(., 'Add Service')]").click()
                            # Monitor mode just fills service, it doesn't submit final app, 
                            # so we don't get Ack No. here.
                            self._log_result(app_name, inputs['scheme_remarks'], "Success", "Service Added")
                        except: pass
                        
                        time.sleep(3)
                    else: time.sleep(1)

                except StaleElementReferenceException: time.sleep(1)
                except NoSuchElementException: time.sleep(1)

            except Exception: time.sleep(1)

    def _safe_send_keys(self, driver, element_name, value):
        if not value: return
        try:
            elem = driver.find_element(By.NAME, element_name)
            elem.clear(); elem.send_keys(value)
        except: pass

    def reset_ui(self):
        self.file_path_entry.delete(0, tkinter.END)
        self.app_remarks_entry.delete(0, tkinter.END)
        self.scheme_type_combobox.set("Service Focus Area")
        self.service_combobox.set("")
        self.scheme_remarks_entry.delete(0, tkinter.END)
        self.backlog_switch.deselect()
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.app.after(0, self.app.set_status, "Ready")
        # Ensure fields are re-enabled
        self._update_remarks_state(False)

    def save_inputs(self, inputs):
        try:
            with open(self.config_file, 'w') as f: json.dump(inputs, f, indent=4)
        except: pass

    def load_inputs(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    file_path = data.get('file_path', '')
                    self.file_path_entry.insert(0, file_path)
                    
                    self.app_remarks_entry.insert(0, data.get('app_remarks', ''))
                    self.scheme_type_combobox.set(data.get('scheme_type', 'Service Focus Area'))
                    self.service_combobox.set(data.get('service', ''))
                    self.scheme_remarks_entry.insert(0, data.get('scheme_remarks', ''))
                    if data.get('is_backlog', False): self.backlog_switch.select()
                    else: self.backlog_switch.deselect()
                    
                    # Check if file exists to toggle state
                    if file_path:
                        self._update_remarks_state(True)
        except: pass

    def clear_file_selection(self):
        self.file_path_entry.delete(0, tkinter.END)
        self._update_remarks_state(False) # Enable UI remarks

    # --- Export Logic ---
    def export_report(self):
        export_format = self.export_format_menu.get()
        if "CSV" in export_format:
            self.export_treeview_to_csv(self.results_tree, "sad_entry_results.csv")
            return
            
        data, file_path = self._get_filtered_data_and_filepath(export_format)
        if not data: return

        # Map data for PDF: [Time, Name, Scheme Remarks, Status, Ack No]
        report_data = [[row[0], row[1], row[2], row[3], row[4]] for row in data]
        report_headers = ["Time", "Applicant Name", "Scheme Remarks", "Status", "Ack Number"]
        col_widths = [40, 100, 100, 40, 80]

        if "PDF" in export_format:
            self._handle_pdf_export(report_data, report_headers, col_widths, file_path)

    def _get_filtered_data_and_filepath(self, export_format):
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "No results to export.")
            return None, None
        
        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in self.results_tree.get_children():
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[3].upper() # Status is column 3 (0-based)
            
            if filter_option == "Export All":
                data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status:
                data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status:
                data_to_export.append(row_values)
                
        if not data_to_export:
            messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'.")
            return None, None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        details = {"PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")]}}
        if export_format not in details: return None, None
        
        filename = f"SAD_Report_{timestamp}{details[export_format]['ext']}"
        file_path = filedialog.asksaveasfilename(
            defaultextension=details[export_format]['ext'],
            filetypes=details[export_format]['types'],
            initialdir=self.app.get_user_downloads_path(),
            initialfile=filename,
            title="Save Report"
        )
        return (data_to_export, file_path) if file_path else (None, None)

    def _handle_pdf_export(self, data, headers, col_widths, file_path):
        title = f"Sarkar Aapke Dwar Report"
        report_date = datetime.now().strftime('%d %b %Y')
        success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
        
        if success and messagebox.askyesno("Success", f"PDF Report saved to:\n{file_path}\n\nDo you want to open it?"):
            if sys.platform == "win32": os.startfile(file_path)
            else: subprocess.call(['open', file_path])