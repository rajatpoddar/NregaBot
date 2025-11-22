# tabs/sarkar_aapke_dwar_tab.py
import tkinter
from tkinter import messagebox, filedialog
import customtkinter as ctk
import json
import os, time, csv
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
        
        # Variable for Backlog Toggle
        self.backlog_mode_var = ctk.BooleanVar(value=False)

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
        
        # --- NEW: Backlog Mode Switch ---
        self.backlog_switch = ctk.CTkSwitch(
            header_frame, 
            text="Backlog Entry Mode", 
            variable=self.backlog_mode_var,
            onvalue=True, 
            offvalue=False,
            command=self._on_mode_switch
        )
        self.backlog_switch.pack(side="right", padx=10)
        # --------------------------------

        # --- MODE 1: CSV Bulk Upload (Optional) ---
        bulk_frame = ctk.CTkFrame(controls_frame, fg_color=("gray90", "gray20"))
        bulk_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        bulk_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bulk_frame, text="Mode 1: Bulk Entry (via CSV)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=5)
        
        self.csv_path_entry = ctk.CTkEntry(bulk_frame, placeholder_text="Select CSV file with Applicant Details...")
        self.csv_path_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        btn_frame = ctk.CTkFrame(bulk_frame, fg_color="transparent")
        btn_frame.grid(row=1, column=2, padx=5)
        
        ctk.CTkButton(btn_frame, text="Browse", width=80, command=self.browse_csv).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Get Demo CSV", width=100, fg_color="green", command=self.generate_demo_csv).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Clear", width=60, fg_color="#C53030", hover_color="#9B2C2C", command=self.clear_csv_selection).pack(side="left", padx=2)
        
        note_text = ("ℹ️ Monitor Mode: Leave CSV empty & click Start. Bot will auto-fill Scheme details when you open a new form.\n"
                     "ℹ️ Bulk Mode: Select CSV to auto-fill applicants. Columns: Name, Father Name, Age, Mobile, Village, Address.")
        
        ctk.CTkLabel(bulk_frame, text=note_text, text_color="gray60", 
                     font=ctk.CTkFont(size=11), justify="left", anchor="w").grid(row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(5, 5))

        # --- Settings (Applied to ALL Modes) ---
        settings_frame = ctk.CTkFrame(controls_frame)
        settings_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        settings_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(settings_frame, text="Common Settings (Applied to CSV & Manual Mode)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # 1. Applicant Remarks
        ctk.CTkLabel(settings_frame, text="Applicant Remarks:").grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self.app_remarks_entry = ctk.CTkEntry(settings_frame, placeholder_text="Enter Applicant Remarks (e.g. Camp)")
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
            "झारखंड राज्य सेवा देने की गारंटी अधिनियम 2011 से जुड़ी अन्य सेवाएं (Other Services under Jharkhand Right to Guarantee of Services Act 2011)",
            "अन्य लोक कल्याणकारी योजनाएँ (Other Welfare Schemes)"
        ]
        self.service_combobox = ctk.CTkComboBox(settings_frame, values=service_options, width=300)
        self.service_combobox.grid(row=3, column=1, columnspan=2, sticky="ew", padx=10, pady=2)

        # 4. Scheme Remarks
        ctk.CTkLabel(settings_frame, text="Scheme Remarks:").grid(row=4, column=0, sticky="w", padx=10, pady=2)
        self.scheme_remarks_entry = ctk.CTkEntry(settings_frame, placeholder_text="Enter Scheme Remarks")
        self.scheme_remarks_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=10, pady=2)

        # Action Buttons (Wrapper handles centering)
        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        # Using pack with expand/center from the wrapper logic in base_tab
        action_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=15)

        # --- Logs & Status Area ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._create_log_and_status_area(parent_notebook=data_notebook)

    def _on_mode_switch(self):
        """Optional: Logic when switch is toggled (e.g., change label color)."""
        mode = "Backlog" if self.backlog_mode_var.get() else "Normal"
        # You could add UI feedback here if desired, but the switch itself is visual enough.
        pass

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.app_remarks_entry.configure(state=state)
        self.scheme_type_combobox.configure(state=state)
        self.service_combobox.configure(state=state)
        self.scheme_remarks_entry.configure(state=state)
        self.csv_path_entry.configure(state=state)
        self.backlog_switch.configure(state=state) # Disable switch while running

    def browse_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            self.csv_path_entry.delete(0, tkinter.END)
            self.csv_path_entry.insert(0, file_path)

    def generate_demo_csv(self):
        headers = [
            "Applicant Name", "Father/Husband Name", "Age", "Mobile No", 
            "Is WhatsApp (Y/N)", "Village", "Address"
        ]
        demo_data = [
            "Ramesh Kumar", "Suresh Kumar", "45", "9876543210", "Y", "Ratu", "House No 12, Main Road"
        ]
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("CSV Files", "*.csv")],
            initialfile="SAD_Bulk_Simple_Demo.csv",
            title="Save Demo CSV"
        )
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerow(demo_data)
                messagebox.showinfo("Success", "Demo CSV saved! Please fill applicant details only.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")

    def start_automation(self):
        inputs = {
            'csv_file': self.csv_path_entry.get().strip(),
            'app_remarks': self.app_remarks_entry.get().strip(),
            'scheme_type': self.scheme_type_combobox.get().strip(),
            'service': self.service_combobox.get().strip(),
            'scheme_remarks': self.scheme_remarks_entry.get().strip(),
            'is_backlog': self.backlog_mode_var.get() # Capture the switch state
        }

        if not inputs['scheme_type'] or not inputs['service']:
            messagebox.showwarning("Input Error", "Please select 'Scheme Type' and 'Service' from the dropdowns.")
            return

        if inputs['csv_file'] and not os.path.exists(inputs['csv_file']):
            messagebox.showerror("File Error", "Selected CSV File does not exist.")
            return

        self.save_inputs(inputs)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        
        try:
            driver = self.app.get_driver()
            if not driver:
                self.app.after(0, self.set_ui_state, False)
                return
            wait = WebDriverWait(driver, 10)

            mode_str = "BACKLOG Entry" if inputs['is_backlog'] else "NORMAL Entry"
            
            if inputs['csv_file']:
                self.app.log_message(self.log_display, f"Starting BULK Mode ({mode_str}) via CSV...")
                self.app.log_message(self.log_display, f"Common Service: {inputs['service']}")
                self._run_bulk_mode(driver, wait, inputs)
            else:
                self.app.log_message(self.log_display, f"Starting MONITOR Mode ({mode_str})...")
                self._run_monitor_mode(driver, wait, inputs)

        except Exception as e:
            self.app.log_message(self.log_display, f"Critical Error: {e}", "error")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Stopped")

    def _run_bulk_mode(self, driver, wait, inputs):
        data = []
        try:
            with open(inputs['csv_file'], 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                data = list(reader)
        except Exception as e:
            self.app.log_message(self.log_display, f"Error reading CSV: {e}", "error")
            return

        total = len(data)
        
        # --- URL LOGIC ---
        url_fragment = "application/createBackLog" if inputs['is_backlog'] else "application/create"
        target_url = f"https://sarkaraapkedwar.jharkhand.gov.in/#/{url_fragment}"
        
        self.app.log_message(self.log_display, f"Loaded {total} records. Target: {url_fragment}")

        for i, row in enumerate(data):
            if self.app.stop_events[self.automation_key].is_set(): break
            
            applicant_name = row.get("Applicant Name", "").strip()
            self.app.log_message(self.log_display, f"Processing ({i+1}/{total}): {applicant_name}")
            self.app.after(0, self.update_status, f"Processing {applicant_name}...", (i+1)/total)

            try:
                # --- Check and Navigate to correct URL ---
                if url_fragment not in driver.current_url:
                    driver.get(target_url)
                    time.sleep(2)

                # Wait for form to be ready
                wait.until(EC.presence_of_element_located((By.NAME, "applicantName")))

                # --- 1. Fill Applicant Details ---
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
                        village_input.send_keys(village)
                        time.sleep(1)
                        village_input.send_keys(Keys.ENTER)
                    except NoSuchElementException:
                        try:
                            village_input = driver.find_element(By.CSS_SELECTOR, ".css-13cymwt-control input")
                            village_input.send_keys(village)
                            time.sleep(1)
                            village_input.send_keys(Keys.ENTER)
                        except: pass

                self._safe_send_keys(driver, "address", row.get("Address", ""))
                
                # --- 2. Fill Remarks ---
                self._safe_send_keys(driver, "remarks", inputs['app_remarks'])

                # --- 3. Fill Scheme Details ---
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                try:
                    Select(driver.find_element(By.NAME, "schemeId")).select_by_visible_text(inputs['scheme_type'])
                    time.sleep(1) 
                except NoSuchElementException:
                    self.app.log_message(self.log_display, f"Error: Scheme Type '{inputs['scheme_type']}' not found.", "error")
                    continue

                try:
                    svc_select = Select(wait.until(EC.presence_of_element_located((By.NAME, "schemeService"))))
                    try:
                        svc_select.select_by_visible_text(inputs['service'])
                    except:
                        found = False
                        for opt in svc_select.options:
                            if inputs['service'].lower() in opt.text.lower():
                                svc_select.select_by_visible_text(opt.text)
                                found = True
                                break
                        if not found:
                            self.app.log_message(self.log_display, f"Error: Service '{inputs['service']}' not found.", "error")
                except Exception as e:
                    self.app.log_message(self.log_display, f"Error selecting Service: {e}", "error")

                self._safe_send_keys(driver, "schemeRemarks", inputs['scheme_remarks'])

                # --- 4. Submit ---
                try:
                    driver.find_element(By.XPATH, "//button[contains(., 'Add Service')]").click()
                    time.sleep(1)
                    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Create Application')]"))).click()
                    time.sleep(2) # Success Wait
                    
                    # Reset
                    try:
                        driver.find_element(By.XPATH, "//button[contains(., 'Reset')]").click()
                        time.sleep(1)
                    except:
                        driver.refresh()
                        time.sleep(2)

                    self.app.log_message(self.log_display, f"Success: {applicant_name}", "success")
                except Exception as e:
                    self.app.log_message(self.log_display, f"Error clicking submit: {e}", "error")

            except Exception as e:
                self.app.log_message(self.log_display, f"Failed {applicant_name}: {e}", "error")
                driver.refresh()
                time.sleep(3)

    def _run_monitor_mode(self, driver, wait, inputs):
        self.app.log_message(self.log_display, "Monitor Mode Active: Navigate to 'Create Application' or 'Backlog Entry'.")
        last_log_time = 0

        while not self.app.stop_events[self.automation_key].is_set():
            try:
                # 1. Check URL (Supports BOTH Normal and Backlog pages automatically)
                curr_url = driver.current_url
                if "application/create" not in curr_url and "application/createBackLog" not in curr_url:
                    # Log status occasionally so user knows it's waiting
                    if time.time() - last_log_time > 8:
                        self.app.log_message(self.log_display, "Waiting... Please open an Entry page.")
                        last_log_time = time.time()
                    time.sleep(2)
                    continue

                # 2. Check if Scheme is already added (Prevent double entry)
                try:
                    # Check if table has rows (meaning service is already added)
                    tbody = driver.find_element(By.CSS_SELECTOR, "table tbody")
                    rows = tbody.find_elements(By.TAG_NAME, "tr")
                    # If rows exist and it's not a "No data" row, skip filling
                    if len(rows) > 0 and "No data" not in rows[0].text:
                        time.sleep(2)
                        continue
                except NoSuchElementException: 
                    pass # Table might not exist yet, proceed to fill

                # 3. Check Scheme Dropdown & Fill
                try:
                    scheme_dd = driver.find_element(By.NAME, "schemeId")
                    select_obj = Select(scheme_dd)
                    
                    # Robust Check: Check by Value ("-1") OR Text ("Select...")
                    selected_val = select_obj.first_selected_option.get_attribute("value")
                    selected_text = select_obj.first_selected_option.text.strip()

                    # If default is selected, start filling
                    if selected_val == "-1" or "Select Scheme" in selected_text:
                        
                        self.app.log_message(self.log_display, "New blank form detected. Auto-filling details...")
                        
                        # Fill Applicant Remarks
                        if inputs['app_remarks']: 
                            self._safe_send_keys(driver, "remarks", inputs['app_remarks'])
                        
                        # Select Scheme Type
                        try:
                            select_obj.select_by_visible_text(inputs['scheme_type'])
                        except NoSuchElementException:
                            self.app.log_message(self.log_display, f"Scheme Type '{inputs['scheme_type']}' not found.", "warning")
                            time.sleep(2); continue

                        time.sleep(1) # Wait for services to load
                        
                        # Select Service
                        svc_select = Select(driver.find_element(By.NAME, "schemeService"))
                        
                        # Retry loop for Service Dropdown population
                        for _ in range(10):
                            if len(svc_select.options) > 1: break
                            time.sleep(0.5)
                        
                        try:
                            # Try exact match first, then partial match
                            try:
                                svc_select.select_by_visible_text(inputs['service'])
                            except:
                                found = False
                                for opt in svc_select.options:
                                    if inputs['service'].lower() in opt.text.lower():
                                        svc_select.select_by_visible_text(opt.text)
                                        found = True
                                        break
                                if not found:
                                    self.app.log_message(self.log_display, f"Service '{inputs['service']}' not found in list.", "warning")
                        except Exception as e:
                            self.app.log_message(self.log_display, f"Error selecting service: {e}", "error")
                        
                        # Fill Scheme Remarks
                        if inputs['scheme_remarks']: 
                            self._safe_send_keys(driver, "schemeRemarks", inputs['scheme_remarks'])
                        
                        # Click Add Service
                        try:
                            add_btn = driver.find_element(By.XPATH, "//button[contains(., 'Add Service')]")
                            add_btn.click()
                            self.app.log_message(self.log_display, "✅ Details Filled & Service Added.")
                        except NoSuchElementException:
                            self.app.log_message(self.log_display, "Add Service button not found.", "error")
                        
                        # Wait to avoid repeating immediately
                        time.sleep(3)
                    else:
                        # Form is already filled/selected, just wait
                        time.sleep(1)

                except StaleElementReferenceException:
                    time.sleep(1) # Page refreshed/changed
                except NoSuchElementException:
                    time.sleep(1) # Element not ready

            except Exception as e:
                # Suppress minor errors in monitor loop
                time.sleep(1)

    def _safe_send_keys(self, driver, element_name, value):
        if not value: return
        try:
            elem = driver.find_element(By.NAME, element_name)
            elem.clear()
            elem.send_keys(value)
        except: pass

    def reset_ui(self):
        self.csv_path_entry.delete(0, tkinter.END)
        self.app_remarks_entry.delete(0, tkinter.END)
        self.scheme_type_combobox.set("Service Focus Area")
        self.service_combobox.set("")
        self.scheme_remarks_entry.delete(0, tkinter.END)
        self.backlog_switch.deselect() # Reset switch to Normal
        self.app.clear_log(self.log_display)
        self.app.after(0, self.app.set_status, "Ready")

    def save_inputs(self, inputs):
        try:
            with open(self.config_file, 'w') as f: json.dump(inputs, f, indent=4)
        except Exception as e: print(f"Error saving SAD inputs: {e}")

    def load_inputs(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.csv_path_entry.insert(0, data.get('csv_file', ''))
                    self.app_remarks_entry.insert(0, data.get('app_remarks', ''))
                    self.scheme_type_combobox.set(data.get('scheme_type', 'Service Focus Area'))
                    self.service_combobox.set(data.get('service', ''))
                    self.scheme_remarks_entry.insert(0, data.get('scheme_remarks', ''))
                    
                    # Load Switch State
                    if data.get('is_backlog', False):
                        self.backlog_switch.select()
                    else:
                        self.backlog_switch.deselect()
        except Exception as e: print(f"Error loading SAD inputs: {e}")

    def clear_csv_selection(self):
        self.csv_path_entry.delete(0, tkinter.END)