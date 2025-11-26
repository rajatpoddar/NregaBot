# tabs/scheme_closing_tab.py
import subprocess
import sys
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os
import json
import time
import re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoAlertPresentException

import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry
from .date_entry_widget import DateEntry

class SchemeClosingTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="scheme_closing")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.skip_confirmation_var = tkinter.BooleanVar(value=False)
        
        self._create_widgets()
        self._load_saved_inputs()

    def _create_widgets(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_container.grid_columnconfigure(0, weight=1)

        # --- Input Frame ---
        input_frame = ctk.CTkFrame(main_container)
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        input_frame.grid_columnconfigure(1, weight=1)

        # Row 0: Panchayat
        ctk.CTkLabel(input_frame, text="Panchayat Name:").grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.panchayat_entry = AutocompleteEntry(
            input_frame, 
            placeholder_text="Enter the Panchayat name as it appears on the website",
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app,
            history_key="panchayat_name"
        )
        self.panchayat_entry.grid(row=0, column=1, columnspan=3, padx=15, pady=(15, 5), sticky="ew")

        # Row 1: Work Category
        ctk.CTkLabel(input_frame, text="Work Category:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        work_category_options = [
            "Anganwadi/Other Rural Infrastructure", "Coastal Areas", "Drought Proofing", "Rural Drinking Water",
            "Food Grain", "Flood Control and Protection", "Fisheries", "Micro Irrigation Works",
            "Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers",
            "Land Development", "Other Works", "Play Ground", "Rural Connectivity", "Rural Sanitation",
            "Bharat Nirman Sewa Kendra", "Water Conservation and Water Harvesting", "Renovation of traditional water bodies"
        ]
        self.work_category_var = ctk.StringVar(value=work_category_options[8])
        self.work_category_menu = ctk.CTkOptionMenu(input_frame, variable=self.work_category_var, values=work_category_options)
        self.work_category_menu.grid(row=1, column=1, columnspan=3, padx=15, pady=5, sticky="ew")

        # Row 2: Actual Benefited Area
        ctk.CTkLabel(input_frame, text="Actual Benefited Area:").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.area_entry = ctk.CTkEntry(input_frame, placeholder_text="e.g., 1")
        self.area_entry.grid(row=2, column=1, padx=15, pady=5, sticky="ew")

        # Row 3: Measured By (Designation)
        ctk.CTkLabel(input_frame, text="Measured by (Designation):").grid(row=3, column=0, padx=15, pady=5, sticky="w")
        designation_options = [
            "Account Assistant(BP)", "Acrited Engineer(AE)(GP)", "Assistant Engineer(BP)", "Block Development Officer(BP)",
            "Gram Rozgar Sewak(GP)", "Junior Engineer(BP)", "Junior Engineer(GP)", "Panchayat Sachiv(GP)",
            "Programme Officer(BP)", "Technical Assistant(BP)", "Technical Assistant(GP)"
        ]
        self.measured_by_var = ctk.StringVar(value="Junior Engineer(BP)")
        self.measured_by_menu = ctk.CTkOptionMenu(input_frame, variable=self.measured_by_var, values=designation_options)
        self.measured_by_menu.grid(row=3, column=1, padx=15, pady=5, sticky="ew")

        # Row 4: Measured By (Name)
        ctk.CTkLabel(input_frame, text="Measured by (Name):").grid(row=4, column=0, padx=15, pady=5, sticky="w")
        self.measured_name_entry = AutocompleteEntry(
            input_frame, 
            placeholder_text="e.g., AKHILESH KUMAR",
            suggestions_list=self.app.history_manager.get_suggestions("staff_name"),
            app_instance=self.app,
            history_key="staff_name"
        )
        self.measured_name_entry.grid(row=4, column=1, padx=15, pady=5, sticky="ew")
        
        # Row 5: Completion Certificate Start No
        ctk.CTkLabel(input_frame, text="Completion Cert. Start No:").grid(row=5, column=0, padx=15, pady=5, sticky="w")
        self.cert_no_entry = ctk.CTkEntry(input_frame, placeholder_text="e.g., 54 (will auto-increment for each work code)")
        self.cert_no_entry.grid(row=5, column=1, padx=15, pady=5, sticky="ew")

        # --- Row 6: Completion Date AND Checkbox Combined ---
        ctk.CTkLabel(input_frame, text="Completion Date:").grid(row=6, column=0, padx=15, pady=(5, 15), sticky="w")
        
        # Sub-frame to hold Date and Checkbox in one line
        date_check_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        date_check_frame.grid(row=6, column=1, sticky="ew", padx=15, pady=(5, 15))

        # Completion Date with Calendar Button
        self.completion_date_entry = ctk.CTkEntry(date_check_frame, placeholder_text="DD/MM/YYYY", width=120)
        self.completion_date_entry.pack(side="left")
        ctk.CTkButton(date_check_frame, text="📅", width=30, fg_color=("gray85", "gray25"), text_color=("black", "white"),
                    command=lambda: self.open_date_picker(lambda d: [self.completion_date_entry.delete(0, "end"), self.completion_date_entry.insert(0, d)])).pack(side="left", padx=(5,0))
        
        self.skip_confirm_checkbox = ctk.CTkCheckBox(
            date_check_frame, 
            text="Skip final confirmation", 
            variable=self.skip_confirmation_var, 
            onvalue=True, 
            offvalue=False
        )
        self.skip_confirm_checkbox.pack(side="left", padx=(20, 0))
        # ----------------------------------------------------

        # Action Buttons (Row 1 of Main Container)
        action_frame = self._create_action_buttons(main_container)
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        # Data Notebook (Row 2 of Main Container - Moved Up)
        notebook = ctk.CTkTabview(main_container)
        notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        work_codes_tab = notebook.add("Work Codes to Close")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(notebook)
        
        # ... (Rest of the logic remains same below) ...
        
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1)

        wc_header_frame = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        clear_wc_button = ctk.CTkButton(wc_header_frame, text="Clear", width=80, command=lambda: self.work_codes_textbox.delete("1.0", "end"))
        clear_wc_button.pack(side="right", padx=5)

        extract_button = ctk.CTkButton(wc_header_frame, text="Extract from Text", width=120,
                                       command=self._extract_work_codes_local)
        extract_button.pack(side='right', padx=(0, 5))
        
        self.work_codes_textbox = ctk.CTkTextbox(work_codes_tab, height=150)
        self.work_codes_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10), padx=5)
        
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side='left')
        self.export_format_menu = ctk.CTkOptionMenu(export_controls_frame, width=130, values=["PDF (.pdf)", "CSV (.csv)"], command=self._on_format_change)
        self.export_format_menu.pack(side='left', padx=5)
        self.export_filter_menu = ctk.CTkOptionMenu(export_controls_frame, width=150, values=["Export All", "Success Only", "Failed Only"])
        self.export_filter_menu.pack(side='left', padx=(0, 5))

        cols = ("Timestamp", "Work Code", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=100, anchor="center"); self.results_tree.column("Work Code", width=250); self.results_tree.column("Status", width=100, anchor="center"); self.results_tree.column("Details", width=350)
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree) 

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')

    def _extract_work_codes_local(self):
        """
        Extracts full work codes from the textbox.
        Uses a specific regex for full codes and does not remove duplicates.
        """
        input_content = self.work_codes_textbox.get("1.0", tkinter.END)
        if not input_content.strip():
            return

        # Regex for full work code, e.g., 3401001/IF/12345/1
        FULL_WC_REGEX = re.compile(r'\b(34\d{8}(?:/\w+)+/\d+)\b')
        found_work_codes = FULL_WC_REGEX.findall(input_content)
        
        # Do not remove duplicates
        final_results = found_work_codes

        # Display results
        self.work_codes_textbox.configure(state="normal")
        self.work_codes_textbox.delete("1.0", tkinter.END)
        if final_results:
            self.work_codes_textbox.insert("1.0", "\n".join(final_results))
        else:
            self.work_codes_textbox.insert("1.0", "No matching full work codes found.")
        self.work_codes_textbox.configure(state="disabled")

    def _on_format_change(self, selected_format):
        if "CSV" in selected_format: self.export_filter_menu.configure(state="disabled")
        else: self.export_filter_menu.configure(state="normal")

    def _get_inputs(self):
        inputs = {
            "panchayat": self.panchayat_entry.get().strip(),
            "work_category": self.work_category_var.get(),
            "area": self.area_entry.get().strip(),
            "measured_by": self.measured_by_var.get(),
            "measured_name": self.measured_name_entry.get().strip(),
            "cert_no_start": self.cert_no_entry.get().strip(),
            "completion_date": self.completion_date_entry.get().strip(),
            "work_codes_raw": self.work_codes_textbox.get("1.0", "end").strip()
        }
        inputs["work_codes"] = [line.strip() for line in inputs["work_codes_raw"].splitlines() if line.strip()]
        return inputs

    def _save_inputs(self, inputs):
        save_data = {k: v for k, v in inputs.items() if k not in ["work_codes_raw", "work_codes"]}
        try:
            with open(self.app.get_data_path("scheme_closing_inputs.json"), 'w') as f:
                json.dump(save_data, f, indent=4)
        except Exception as e:
            print(f"Error saving inputs: {e}")

    def _load_saved_inputs(self):
        try:
            with open(self.app.get_data_path("scheme_closing_inputs.json"), 'r') as f:
                data = json.load(f)
            self.panchayat_entry.insert(0, data.get("panchayat", ""))
            self.work_category_var.set(data.get("work_category", "Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers"))
            self.area_entry.insert(0, data.get("area", ""))
            self.measured_by_var.set(data.get("measured_by", "Junior Engineer(BP)"))
            self.measured_name_entry.insert(0, data.get("measured_name", ""))
            self.cert_no_entry.insert(0, data.get("cert_no_start", ""))
            
            # --- FIX: Use delete/insert instead of set_date ---
            date_val = data.get("completion_date", "")
            self.completion_date_entry.delete(0, "end")
            self.completion_date_entry.insert(0, date_val)
            
        except FileNotFoundError:
            # Set today's date if no file found
            self.completion_date_entry.delete(0, "end")
            self.completion_date_entry.insert(0, datetime.now().strftime("%d/%m/%Y"))
        except Exception as e:
            print(f"Error loading inputs: {e}")

    def start_automation(self):
        inputs = self._get_inputs()
        
        required_fields = ["panchayat", "work_category", "area", "measured_by", "measured_name", "cert_no_start", "completion_date", "work_codes"]
        if not all(inputs.get(field) for field in required_fields):
            messagebox.showwarning("Input Required", "All fields and at least one work code are required.")
            return
        
        try:
            inputs["cert_no_start"] = int(inputs["cert_no_start"])
        except ValueError:
            messagebox.showwarning("Input Error", "Completion Certificate Start No must be a number.")
            return

        self._save_inputs(inputs)
        
        # --- ADDED: Save inputs to history ---
        self.app.update_history("panchayat_name", inputs["panchayat"])
        self.app.update_history("staff_name", inputs["measured_name"])
        # ---
        
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        
        self.app.after(0, self.app.set_status, "Running Scheme Closing...")

        self.app.log_message(self.log_display, "--- Starting Scheme Closing ---")
        
        driver = self.app.get_driver()
        if not driver:
            messagebox.showerror("Browser Not Found", "Please launch a browser first.")
            self.app.after(0, self.set_ui_state, False)
            return

        try:
            total_codes = len(inputs["work_codes"])
            current_cert_no = inputs["cert_no_start"]
            success_count = 0
            fail_count = 0

            for i, work_code in enumerate(inputs["work_codes"]):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Automation stopped by user.", "warning")
                    break
                
                # --- MODIFICATION: Improved Status Reporting ---
                status_msg = f"Processing {i+1}/{total_codes}: {work_code}"
                progress = (i + 1) / total_codes
                self.app.after(0, self.app.set_status, status_msg) # मुख्य (main) स्टेटस बार
                self.app.after(0, self.update_status, status_msg, progress) # टैब का स्टेटस बार
                # --- END MODIFICATION ---
                
                self.app.log_message(self.log_display, f"\n--- Processing Work Code: {work_code} ---")
                
                status, details = self._process_single_work_code(driver, inputs, work_code, current_cert_no)
                self._log_result(work_code, status, details)
                
                if status == "Success":
                    current_cert_no += 1
                    success_count += 1
                else:
                    fail_count += 1

            completion_message = f"Automation Finished!\n\nSuccessful: {success_count}\nFailed/Cancelled: {fail_count}"
            messagebox.showinfo("Task Complete", completion_message)

        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {str(e).splitlines()[0]}", "error")
        
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.update_status("Automation Finished", 1.0)
            self.app.log_message(self.log_display, "\n--- Automation Finished ---")
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _log_result(self, work_code, status, details):
        timestamp = time.strftime("%H:%M:%S")
        tags = ('failed',) if 'success' not in status.lower() else ()
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(timestamp, work_code, status, details), tags=tags))

    def _process_single_work_code(self, driver, inputs, work_code, cert_no):
        wait = WebDriverWait(driver, 20)
        long_wait = WebDriverWait(driver, 35)
        url = "https://nregade4.nic.in/netnrega/compwork.aspx"
        
        try:
            driver.get(url)
            self.app.log_message(self.log_display, "   - Page 1: Selecting Panchayat...")
            panchayat_select_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlPanchayat")))
            Select(panchayat_select_element).select_by_visible_text(inputs["panchayat"])
            wait.until(EC.staleness_of(panchayat_select_element))

            self.app.log_message(self.log_display, "   - Page 1: Selecting Work Category...")
            category_select_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlWorkCategroy")))
            Select(category_select_element).select_by_visible_text(inputs["work_category"])
            wait.until(EC.staleness_of(category_select_element))

            self.app.log_message(self.log_display, "   - Page 1: Searching for Work Code...")
            wc_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txt_search_wrk")))

            time.sleep(1)

            wc_input.send_keys(work_code)
            wc_input.send_keys(Keys.TAB)
            wait.until(EC.staleness_of(wc_input))

            work_dropdown_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlworkcode")))
            work_dropdown = Select(work_dropdown_element)
            option_found = False
            for option in work_dropdown.options:
                if work_code in option.get_attribute("value"):
                    work_dropdown.select_by_value(option.get_attribute("value"))
                    option_found = True
                    break
            if not option_found: return "Failed", f"Work code {work_code} not found."
            wait.until(EC.staleness_of(work_dropdown_element))
            
            self.app.log_message(self.log_display, "   - Page 1: Filling completion details...")
            work_name_full = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_Pnl_lblworkcode"))).text
            
            area_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_Txtactualbenarea")))
            if not area_input.get_attribute("value"):
                area_input.send_keys(inputs["area"])
            else:
                self.app.log_message(self.log_display, "   - Actual Benefited Area is already filled, skipping.")

            Select(wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_Ddldesignation")))).select_by_visible_text(inputs["measured_by"])
            
            long_wait.until(EC.presence_of_element_located((By.XPATH, f"//select[@id='ctl00_ContentPlaceHolder1_Ddlmeasured']/option[text()='{inputs['measured_name']}']")))
            Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_Ddlmeasured")).select_by_visible_text(inputs["measured_name"])
            
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtccNo").send_keys(str(cert_no))
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtcc_dt").send_keys(inputs["completion_date"])

            # --- NEW: Check for the optional 'Excavation(cum)' field and fill it if empty ---
            try:
                excavation_input = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtcomp_add_unit"))
                )
                if not excavation_input.get_attribute("value"):
                    excavation_input.send_keys("1")
                    self.app.log_message(self.log_display, "   - Excavation(cum) field found and filled with '1'.", "info")
                else:
                    self.app.log_message(self.log_display, "   - Excavation(cum) field found but already filled.", "info")
            except TimeoutException:
                self.app.log_message(self.log_display, "   - Excavation(cum) field not found on this page, skipping.", "info")
            
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_BtnNext").click()
            
            self.app.log_message(self.log_display, "   - Page 2: Waiting for page to load...")
            asset_name_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_grdData_ctl02_txtAsset_Name")))
            asset_desc_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_grdData_ctl02_txtAsset_Description")))
            
            self.app.log_message(self.log_display, "   - Page 2: Filling Asset Name and Description...")
            asset_name_input.clear()
            asset_name_input.send_keys("Completed")
            asset_desc_input.clear()
            asset_desc_input.send_keys("Completed")
            
            if not self.skip_confirmation_var.get():
                confirm_text = f"You are about to close the following scheme:\n\n{work_name_full}\n\nDo you want to proceed?"
                if not messagebox.askyesno("Confirm Scheme Closing", confirm_text):
                    return "Cancelled", "User cancelled the operation."

            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btSave").click()
            
            try:
                alert_wait = WebDriverWait(driver, 5)
                alert = alert_wait.until(EC.alert_is_present())
                alert_text = alert.text
                alert.accept()
                
                if "Multiple Asset Detail Successfully Save" in alert_text:
                    return "Success", "Scheme closed successfully (alert)."
                else:
                    return "Failed", f"Unexpected alert: {alert_text}"

            except TimeoutException:
                self.app.log_message(self.log_display, "   - No success alert detected, checking page for status...")
                page_source = driver.page_source
                if "Work has been Completed Successfully" in page_source:
                    return "Success", "Work completed successfully (page)."
                else:
                    try:
                        error_label = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_lblmsg")
                        if error_label.text: return "Failed", error_label.text
                    except NoSuchElementException: pass
                    return "Failed", "Unknown error after saving (no alert or message found)."

        except (TimeoutException, NoSuchElementException, NoAlertPresentException) as e:
            error_message = str(e).splitlines()[0] if str(e) else "No error message"
            self.app.log_message(self.log_display, f"   - Error: {error_message}", "error")
            return "Failed", f"Error on page: {error_message}"
        except Exception as e:
            error_message = str(e).splitlines()[0] if str(e) else "No error message"
            self.app.log_message(self.log_display, f"   - An unexpected error occurred: {error_message}", "error")
            return "Failed", f"An unexpected error occurred: {error_message}"

    def reset_ui(self):
        if messagebox.askokcancel("Reset Form?", "Are you sure? This will clear all inputs."):
            self.panchayat_entry.delete(0, "end")
            self.work_category_var.set("Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers")
            self.area_entry.delete(0, "end")
            self.measured_by_var.set("Junior Engineer(BP)")
            self.measured_name_entry.delete(0, "end")
            self.cert_no_entry.delete(0, "end")
            
            # --- FIX: Use delete instead of clear() ---
            self.completion_date_entry.delete(0, "end")
            
            self.work_codes_textbox.delete("1.0", "end")
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.app.after(0, self.app.set_status, "Ready")

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.work_category_menu.configure(state=state)
        self.area_entry.configure(state=state)
        self.measured_by_menu.configure(state=state)
        self.measured_name_entry.configure(state=state)
        self.cert_no_entry.configure(state=state)
        self.completion_date_entry.configure(state=state)
        self.work_codes_textbox.configure(state=state)
        self.export_button.configure(state=state)
        self.export_format_menu.configure(state=state)
        self.export_filter_menu.configure(state=state)
        self.skip_confirm_checkbox.configure(state=state)
        if state == "normal": self._on_format_change(self.export_format_menu.get())

    def export_report(self):
        export_format = self.export_format_menu.get()
        if "CSV" in export_format:
            self.export_treeview_to_csv(self.results_tree, "scheme_closing_results.csv")
            return
            
        data, file_path = self._get_filtered_data_and_filepath(export_format)
        if not data: return
        
        report_data = [[row[1], row[2], row[3], row[0]] for row in data]
        report_headers = ["Work Code", "Status", "Details", "Timestamp"]
        col_widths = [70, 35, 140, 25]

        if "PDF" in export_format:
            self._handle_pdf_export(report_data, report_headers, col_widths, file_path)

    def _get_filtered_data_and_filepath(self, export_format):
        if not self.results_tree.get_children(): messagebox.showinfo("No Data", "No results to export."); return None, None
        panchayat_name = self.panchayat_entry.get().strip()
        if not panchayat_name: messagebox.showwarning("Input Needed", "Panchayat Name is required for report title."); return None, None
        
        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in self.results_tree.get_children():
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[2].upper()
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status: data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status: data_to_export.append(row_values)
        if not data_to_export: messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'."); return None, None

        safe_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        details = {"Image (.jpg)": { "ext": ".jpg", "types": [("JPEG Image", "*.jpg")]}, "PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")]}}[export_format]
        filename = f"Scheme_Closing_Report_{safe_name}_{timestamp}{details['ext']}"
        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_user_downloads_path(), initialfile=filename, title="Save Report")
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, headers, col_widths, file_path):
        title = f"Scheme Closing Report: {self.panchayat_entry.get().strip()}"
        report_date = datetime.now().strftime('%d %b %Y')
        success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
        if success and messagebox.askyesno("Success", f"PDF Report saved to:\n{file_path}\n\nDo you want to open it?"):
            if sys.platform == "win32": os.startfile(file_path)
            else: subprocess.call(['open', file_path])