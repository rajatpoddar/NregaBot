# tabs/work_allocation_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import json
import csv
import os, sys, subprocess, time
from datetime import datetime

import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry
from typing import Any, Callable, Dict, List, Optional, Tuple

class WorkAllocationTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        # Lazy imports
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoAlertPresentException, StaleElementReferenceException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoAlertPresentException, StaleElementReferenceException
        super().__init__(parent, app_instance, automation_key="work_allocation")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ID for the "Please Wait..." overlay
        self.wait_overlay_id = "ctl00_ContentPlaceHolder1_PageUpdateProgress"
        self.has_failures = False # Flag to track errors
        
        # Data holder for CSV based allocation
        self.csv_allocation_data = {} 

        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver

        # Frame for all user input controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        controls_frame.grid_columnconfigure(1, weight=1)

        # --- Row 0: Panchayat Name ---
        ctk.CTkLabel(controls_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        self.panchayat_entry = AutocompleteEntry(controls_frame,
                                                 placeholder_text="Enter the Panchayat name as it appears on the website",
                                                 suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
                                                 app_instance=self.app,
                                                 history_key="panchayat_name")
        self.panchayat_entry.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))

        # --- Row 1: Work Category ---
        ctk.CTkLabel(controls_frame, text="Work Category:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        # Options extracted from your provided 'Work Allocation.htm'
        work_category_options = [
            "Anganwadi/Other Rural Infrastructure", "Coastal Areas", "Drought Proofing", "Rural Drinking Water",
            "Food Grain", "Flood Control and Protection", "Fisheries", "Micro Irrigation Works",
            "Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers",
            "Land Development", "Other Works", "Play Ground", "Rural Connectivity", "Rural Sanitation",
            "Bharat Nirman Sewa Kendra", "Water Conservation and Water Harvesting", "Renovation of traditional water bodies"
        ]
        self.work_category_var = ctk.StringVar(value=work_category_options[8]) # Default to 'Provision of Irrigation...'
        self.work_category_menu = ctk.CTkOptionMenu(controls_frame, variable=self.work_category_var, values=work_category_options)
        self.work_category_menu.grid(row=1, column=1, sticky="ew", padx=15, pady=5)

        # --- Row 2: CSV Upload (NEW) ---
        ctk.CTkLabel(controls_frame, text="Use Demand CSV:").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        
        csv_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        csv_frame.grid(row=2, column=1, sticky="ew", padx=15, pady=5)
        
        self.load_csv_btn = ctk.CTkButton(csv_frame, text="Load Demand CSV", command=self._load_demand_csv, fg_color="#D35400", hover_color="#A04000", width=150)
        self.load_csv_btn.pack(side="left", padx=(0, 10))
        
        self.file_label = ctk.CTkLabel(csv_frame, text="No file selected", text_color="gray")
        self.file_label.pack(side="left")

        # --- Row 3: Action Buttons ---
        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=15)

        # --- Data Tabs (Work List, Results, Logs) ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        work_list_tab = data_notebook.add("Work Key List")
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # --- 1. Work Key List Tab ---
        work_list_tab.grid_columnconfigure(0, weight=1)
        work_list_tab.grid_rowconfigure(1, weight=1)
        
        wc_controls_frame = ctk.CTkFrame(work_list_tab, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=(5,0))
        
        ctk.CTkLabel(wc_controls_frame, text="Enter one Work Key (Search Key) per line.").pack(side='left', padx=5)
        clear_button = ctk.CTkButton(wc_controls_frame, text="Clear", width=80, command=lambda: self.work_list_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', padx=5)

        self.work_list_text = ctk.CTkTextbox(work_list_tab)
        self.work_list_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # --- 2. Results Tab ---
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10))
        
        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side='left')
        self.export_format_menu = ctk.CTkOptionMenu(export_controls_frame, width=130, values=["PDF (.pdf)", "CSV (.csv)"], command=self._on_format_change)
        self.export_format_menu.pack(side='left', padx=5)
        self.export_filter_menu = ctk.CTkOptionMenu(export_controls_frame, width=150, values=["Export All", "Success Only", "Failed Only"])
        self.export_filter_menu.pack(side='left', padx=(0, 5))

        # --- Results Treeview ---
        cols = ("Work Key", "Selected Work Code", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Work Key", anchor='center', width=100)
        self.results_tree.column("Selected Work Code", width=250)
        self.results_tree.column("Status", anchor='center', width=100)
        self.results_tree.column("Details", width=250)
        self.results_tree.column("Timestamp", anchor='center', width=100)
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)

    def _on_format_change(self, selected_format):
        if "CSV" in selected_format:
            self.export_filter_menu.configure(state="disabled")
        else:
            self.export_filter_menu.configure(state="normal")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.work_category_menu.configure(state=state)
        self.work_list_text.configure(state=state)
        self.export_button.configure(state=state)
        self.export_format_menu.configure(state=state)
        self.export_filter_menu.configure(state=state)
        if state == "normal": self._on_format_change(self.export_format_menu.get())
    def reset_ui(self) -> None:
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        self.panchayat_entry.delete(0, tkinter.END)
        self.work_list_text.delete("1.0", tkinter.END)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.app.clear_log(self.log_display)
        self.update_status("Ready", 0.0)
        self.app.log_message(self.log_display, "Form has been reset.")
        self.app.after(0, self.app.set_status, "Ready")

    def run_automation_from_demand(self, panchayat_name, allocation_data):
        """
        Starts the Work Allocation automation externally.
        'allocation_data' can be:
        1. A single String (Global Work Key for all successful laborers) - OLD Way
        2. A Dictionary { 'WorkKey': ['LaborerName1', 'LaborerName2'] } - NEW Way
        """
        self.app.log_message(self.log_display, "--- Starting Auto-Allocation from Demand Tab ---")
        
        # 1. Clear/Reset UI
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.app.clear_log(self.log_display)
        self.panchayat_entry.delete(0, tkinter.END)
        self.work_list_text.delete("1.0", tkinter.END)

        # 2. Set Inputs
        self.panchayat_entry.insert(0, panchayat_name)
        
        # Use the currently selected work category from the UI
        work_category = self.work_category_var.get()
        
        inputs = {
            'panchayat_name': panchayat_name,
            'work_category': work_category,
        }

        # 3. Process the Data Format
        if isinstance(allocation_data, str):
            # OLD/SIMPLE MODE: Bulk allocation to one key
            self.app.log_message(self.log_display, f"Mode: Bulk Allocation (Single Key: {allocation_data})")
            self.work_list_text.insert("1.0", allocation_data)
            inputs['work_keys'] = [allocation_data]
            inputs['allocation_map'] = None # No specific mapping, assume 'Allocate All'
            
        elif isinstance(allocation_data, dict):
            # NEW/GRANULAR MODE: Specific laborers for specific keys
            self.app.log_message(self.log_display, f"Mode: Granular Allocation ({len(allocation_data)} work codes)")
            
            # Display keys in text box for visual reference
            display_text = "\n".join(allocation_data.keys())
            self.work_list_text.insert("1.0", display_text)
            
            inputs['work_keys'] = list(allocation_data.keys())
            inputs['allocation_map'] = allocation_data # Pass the mapping to logic
            
        else:
            messagebox.showerror("Error", "Invalid data format received from Demand tab.")
            return

        self.app.log_message(self.log_display, f"Panchayat: {panchayat_name}")
        self.app.log_message(self.log_display, f"Work Category: {work_category}")

        # 4. Save and Start
        self._save_inputs(inputs)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))
    def start_automation(self) -> None:
        # Default start from UI (Bulk Mode or CSV Mode)
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.app.clear_log(self.log_display)

        inputs = {
            'panchayat_name': self.panchayat_entry.get().strip(),
            'work_category': self.work_category_var.get(),
            'work_list_raw': self.work_list_text.get("1.0", tkinter.END).strip()
        }

        if not inputs['work_category']:
            messagebox.showwarning("Input Error", "Work Category is required.")
            return

        # --- LOGIC SWITCH: CSV vs Text Box ---
        if self.csv_allocation_data:
            # Mode 1: Use Loaded CSV Data
            work_keys = list(self.csv_allocation_data.keys())
            inputs['work_keys'] = work_keys
            inputs['allocation_map'] = self.csv_allocation_data
            self.app.log_message(self.log_display, f"Mode: CSV Allocation ({len(work_keys)} works loaded)")
        else:
            # Mode 2: Use Text Box (Original)
            if not inputs['work_list_raw']:
                messagebox.showwarning("Input Error", "Please enter Work Keys or Load a CSV.")
                return
            work_keys = [line.strip() for line in inputs['work_list_raw'].splitlines() if line.strip()]
            if not work_keys:
                messagebox.showwarning("Input Error", "No valid items found in the Work Key List.")
                return
            inputs['work_keys'] = work_keys
            inputs['allocation_map'] = None 

        if inputs['panchayat_name']:
            self.app.update_history("panchayat_name", inputs['panchayat_name'])
        self._save_inputs(inputs)
        
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def _wait_for_settle(self, driver, long_wait, action_name=""):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        """
        Waits for the 'Please Wait...' overlay to disappear.
        Handles cases where the overlay is very fast or doesn't appear at all.
        """
        self.app.log_message(self.log_display, f"   - Waiting for page to settle after '{action_name}'...")
        try:
            # 1. Check if overlay is visible (with a very short timeout)
            short_wait = WebDriverWait(driver, 0.5) # 0.5 second check
            overlay_visible = short_wait.until(EC.visibility_of_element_located((By.ID, self.wait_overlay_id)))
            
            # 2. If it was visible, wait for it to disappear (with the long timeout)
            if overlay_visible:
                self.app.log_message(self.log_display, "   - Overlay detected, waiting for it to disappear...")
                long_wait.until(EC.invisibility_of_element_located((By.ID, self.wait_overlay_id)))
                self.app.log_message(self.log_display, "   - Page settled.")
            
        except TimeoutException:
            # This is the normal, fast path. The overlay was not visible (or gone in < 0.5s).
            self.app.log_message(self.log_display, "   - (No overlay) Page is settled.", "info")
        
        # Add a small fixed delay for extra safety after any postback
        time.sleep(0.5)

    def run_automation_logic(self, inputs):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, self.app.set_status, "Starting Work Allocation...")
        self.app.log_message(self.log_display, "Starting Work Allocation automation...")
        self.has_failures = False 
        
        try:
            driver = self.app.get_driver()
            if not driver:
                self.app.after(0, self.set_ui_state, False)
                return
                
            wait = WebDriverWait(driver, 20)
            # --- NEW: Long wait specifically for Save operation (5 Minutes) ---
            save_wait = WebDriverWait(driver, 300) 
            
            self.app.log_message(self.log_display, f"Navigating to Work Allocation page...")
            driver.get(config.WORK_ALLOCATION_CONFIG["url"])

            # --- START: Standard Setup (Panchayat/Category) ---
            self.app.log_message(self.log_display, "Checking for Panchayat dropdown...")
            try:
                short_wait = WebDriverWait(driver, 3)
                panchayat_select_element = short_wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code")))
                
                self.app.log_message(self.log_display, "Panchayat dropdown found. Selecting...")
                if not inputs['panchayat_name']: raise ValueError("Panchayat Name is required for PO login.")
                panchayat_select = Select(panchayat_select_element)
                if panchayat_select.first_selected_option.text.strip() != inputs['panchayat_name'].strip():
                    panchayat_select.select_by_visible_text(inputs['panchayat_name'])
                    self._wait_for_settle(driver, wait, "Panchayat Selection")
            except (TimeoutException, NoSuchElementException):
                self.app.log_message(self.log_display, "Panchayat dropdown not found. Assuming GP Login.", "info")
            except ValueError as e:
                self.app.log_message(self.log_display, str(e), "error"); messagebox.showerror("Input Error", str(e)); self.app.after(0, self.set_ui_state, False); return

            self.app.after(0, self.app.set_status, "Setting Work Category...")
            category_select_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlworkcategory")))
            category_select = Select(category_select_element)
            if category_select.first_selected_option.text.strip() != inputs['work_category'].strip():
                category_select.select_by_visible_text(inputs['work_category'])
                self._wait_for_settle(driver, wait, "Category Selection")
            # --- END: Standard Setup ---

            self.app.log_message(self.log_display, "Setup complete. Starting item processing...", "success")
            
            # --- Process each item (Updated Loop) ---
            work_keys = inputs.get('work_keys', [])
            allocation_map = inputs.get('allocation_map') # Can be None
            
            total_items = len(work_keys)
            for i, work_key in enumerate(work_keys):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Stop signal received.", "warning")
                    break
                
                status_msg = f"Processing {i+1}/{total_items}: Key={work_key}"
                self.app.after(0, self.app.set_status, status_msg)
                self.app.after(0, self.update_status, status_msg, (i+1)/total_items)
                
                # Determine specific targets for this key (if any)
                target_applicants = None
                if allocation_map and work_key in allocation_map:
                    target_applicants = allocation_map[work_key]
                
                # Pass save_wait to the processor
                self._process_single_work_key(driver, wait, work_key, target_applicants, save_wait) 

        except Exception as e:
            error_msg = f"A critical error occurred: {e}"
            self.app.log_message(self.log_display, error_msg, "error")
            messagebox.showerror("Critical Error", error_msg)
            self.app.after(0, self.app.set_status, "Error")
        finally:
            self.app.after(0, self.set_ui_state, False)
            final_status = "Automation Stopped" if self.app.stop_events[self.automation_key].is_set() else ("Finished with Errors" if self.has_failures else "Automation Finished")
            self.app.after(0, self.app.set_status, final_status)
            self.app.after(0, self.update_status, final_status, 1.0)
            
            if "Stopped" not in final_status:
                kind = "warning" if self.has_failures else "info"
                self.app.after(100, lambda: getattr(messagebox, f"show{kind}")("Complete", f"{final_status}. Check results."))

    def _process_single_work_key(self, driver, wait, work_key, target_applicants=None, save_wait=None): 
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        """
        Processing logic. Updated to skip saving if no labourers are found in granular mode.
        """
        # Fallback if save_wait is not passed
        if save_wait is None: save_wait = wait

        selected_work_code_text = "N/A"
        found_count = 0 # To track how many specific applicants were found

        try:
            self.app.log_message(self.log_display, f"   - Processing Key: {work_key}")
            if target_applicants:
                self.app.log_message(self.log_display, f"     (Granular Mode: Allocating {len(target_applicants)} specific laborers)")

            # --- Step 3: Enter Work Key ---
            search_box = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtwrksearchkey")))
            search_box.clear()
            search_box.send_keys(work_key)
            
            driver.find_element(By.TAG_NAME, 'body').click()
            self._wait_for_settle(driver, wait, f"Work Key Search ({work_key})")
            
            # --- Step 4: Select Matching Work Code ---
            work_code_select_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlWork_code")))
            work_code_select = Select(work_code_select_element)
            
            matching_option = None
            for option in work_code_select.options:
                # Flexible Match: Check if work_key is contained in option text
                if work_key in option.text: matching_option = option; break
            
            if not matching_option:
                error_msg = "Workcode not found in dropdown."
                self.app.log_message(self.log_display, f"   - FAILED: {error_msg}", "error")
                self._log_result(work_key, "N/A", "Failed", error_msg)
                return 
            
            selected_work_code_text = matching_option.text
            work_code_select.select_by_visible_text(selected_work_code_text)
            self._wait_for_settle(driver, wait, "Work Code Selection")

            # --- Step 5: Allocation Logic (Bulk vs Granular) ---
            
            if not target_applicants:
                # --- BULK MODE (Allocate All) ---
                self.app.log_message(self.log_display, "   - Clicking 'Allocate All'...")
                alloc_checkbox = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_GridView1_ctl01_chkHAllocate")))
                if not alloc_checkbox.is_selected():
                    alloc_checkbox.click()
                    self._wait_for_settle(driver, wait, "Allocate All")
            else:
                # --- GRANULAR MODE (Specific Checkboxes) ---
                self.app.log_message(self.log_display, "   - Selecting specific applicants...")
                grid_id = "ctl00_ContentPlaceHolder1_GridView1"
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, f"table[id='{grid_id}'] > tbody > tr")
                    for i, row in enumerate(rows):
                        if i == 0: continue 
                        try:
                            # Column 4 is Name (based on HTML structure)
                            name_cell = row.find_elements(By.TAG_NAME, "td")[3]
                            name_text = name_cell.get_attribute("innerText").strip()
                            
                            # Match CSV Name/Card with Table Name (Fuzzy Match)
                            is_target = any("".join(tn.lower().split()) in "".join(name_text.lower().split()) for tn in target_applicants)
                            
                            if is_target:
                                checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox'][id*='chkAllocate']")
                                if not checkbox.is_selected(): checkbox.click(); found_count += 1
                        except Exception: continue
                            
                    self.app.log_message(self.log_display, f"   - Selected {found_count}/{len(target_applicants)} applicants found on page.")
                except Exception as e:
                    self.app.log_message(self.log_display, f"   - Error traversing table: {e}", "error")

                # --- NEW LOGIC: Skip if no labourers found ---
                if found_count == 0:
                    msg = "Skipped: Labours not found in table."
                    self.app.log_message(self.log_display, f"   - {msg}", "warning")
                    # Use 'warning' tag (yellow) or 'failed' (red) as preferred. 
                    # Assuming 'skipped' tag maps to yellow in base_tab.
                    self._log_result(work_key, selected_work_code_text, "Skipped", msg)
                    return 
                # ---------------------------------------------

            # --- Step 6: Click Save (with 5 MIN WAIT) ---
            self.app.log_message(self.log_display, "   - Clicking 'Save' (Timeout set to 5 mins)...")
            save_button = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_cmdSave")))
            save_button.click()
            
            # Use save_wait (300s) for the alert
            self.app.log_message(self.log_display, "   - Waiting for confirmation alert...")
            alert = save_wait.until(EC.alert_is_present())
            alert_text = alert.text.strip()
            alert.accept()
            
            self.app.log_message(self.log_display, f"   - Success: {alert_text}", "success")
            
            # --- Reporting Logic ---
            if target_applicants:
                detail_msg = f"{alert_text} (Allocated: {found_count}/{len(target_applicants)})"
            else:
                detail_msg = alert_text

            self._log_result(work_key, selected_work_code_text, "Success", detail_msg)
            # Use save_wait for settling after save as well
            self._wait_for_settle(driver, save_wait, "Save")

        except (TimeoutException, NoAlertPresentException, StaleElementReferenceException) as e:
            error_msg = f"Page error (Timeout/Alert): {str(e).splitlines()[0]}"
            self.app.log_message(self.log_display, f"   - FAILED: {error_msg}", "error")
            self._log_result(work_key, selected_work_code_text, "Failed", error_msg)
            try: driver.get(config.WORK_ALLOCATION_CONFIG["url"]); self.app.log_message(self.log_display, "   - Refreshing page..."); return
            except Exception: return
        
        except Exception as e:
            error_msg = f"Critical error: {e}"
            self.app.log_message(self.log_display, f"   - FAILED: {error_msg}", "error")
            self._log_result(work_key, selected_work_code_text, "Failed", error_msg)

    def _load_demand_csv(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        """Loads the Demand CSV and groups workers by Work Code."""
        file_path = filedialog.askopenfilename(
            title="Select Demand CSV",
            filetypes=[("CSV Files", "*.csv")]
        )
        
        if not file_path: return

        try:
            self.csv_allocation_data = {}
            count = 0
            
            with open(file_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Basic Validation: Check for required columns
                # 'Allocation Work Code' and 'Name of Applicant' (or Job card) are needed
                # Based on your previous file, keys are: 'Name of Applicant', 'Job card number', 'Allocation Work Code'
                
                if 'Allocation Work Code' not in reader.fieldnames:
                    messagebox.showerror("Error", "CSV must have 'Allocation Work Code' column.")
                    return

                for row in reader:
                    work_code = row['Allocation Work Code'].strip()
                    # We use Name for matching since Job Card in table might differ slightly in format
                    # But Job Card is better if available. Let's store both or Name.
                    # Your CSV has 'Name of Applicant'. The table has Name in 4th Col.
                    person_name = row.get('Name of Applicant', '').strip()
                    
                    if work_code and person_name:
                        if work_code not in self.csv_allocation_data:
                            self.csv_allocation_data[work_code] = []
                        self.csv_allocation_data[work_code].append(person_name)
                        count += 1
            
            filename = os.path.basename(file_path)
            self.file_label.configure(text=f"Loaded: {filename}", text_color="green")
            self.app.log_message(self.log_display, f"CSV Loaded: {filename}")
            self.app.log_message(self.log_display, f"Found {len(self.csv_allocation_data)} works with {count} workers.")
            
            # Disable text box to indicate CSV mode is active
            self.work_list_text.delete("1.0", tkinter.END)
            self.work_list_text.insert("1.0", f"[CSV Loaded] {filename}\nContains {len(self.csv_allocation_data)} Work Codes.\n\nClick 'Start' to proceed.")
            self.work_list_text.configure(state="disabled")
            
        except Exception as e:
            self.app.log_message(self.log_display, f"Error loading CSV: {e}", "error")
            messagebox.showerror("Error", f"Failed to load CSV: {e}")

    def _log_result(self, work_key, work_code, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (work_key, work_code, status, details, timestamp)
        
        # --- Update: Color Tags ---
        tags = ()
        if 'success' in status.lower():
            tags = ('success',)
        elif 'failed' in status.lower() or 'error' in status.lower() or 'timeout' in status.lower():
            self.has_failures = True
            tags = ('failed',)
        # --------------------------
        
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=values, tags=tags))
    def retry_logic_handler(self) -> None:
        """
        Custom Retry Logic for Work Allocation.
        Extracts failed Work Keys from the results tree and restarts automation
        specifically for those keys.
        """
        failed_keys = []
        all_items = self.results_tree.get_children()
        
        if not all_items:
            messagebox.showinfo("Retry", "No results found to retry.")
            return

        for item_id in all_items:
            values = self.results_tree.item(item_id)['values']
            # Tree columns: Work Key, Work Code, Status, Details, Timestamp
            work_key = str(values[0])
            status = str(values[2]).lower()
            
            if "success" not in status:
                if work_key not in failed_keys:
                    failed_keys.append(work_key)
        
        if not failed_keys:
            messagebox.showinfo("Great!", "No failed items found.")
            return

        # Confirm before action
        if not messagebox.askyesno("Retry Failed", f"Found {len(failed_keys)} failed work keys.\nDo you want to retry them now?"):
            return

        # 1. Update Input Widget (Switch to Manual/Bulk Mode for Retry)
        self.work_list_text.configure(state="normal")
        self.work_list_text.delete("1.0", tkinter.END)
        self.work_list_text.insert("1.0", "\n".join(failed_keys))
        
        # 2. Reset CSV Data (Crucial: Forces logic to read from text box)
        self.csv_allocation_data = {} 
        self.file_label.configure(text="Retry Mode (Text)", text_color="orange")
        
        # 3. Clear Previous Results
        for item in all_items:
            self.results_tree.delete(item)

        # 4. Auto Start
        self.app.log_message(self.log_display, f"Retrying {len(failed_keys)} failed work keys...", "info")
        self.start_automation()

    def export_report(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        export_format = self.export_format_menu.get()
        panchayat_name = self.panchayat_entry.get().strip()

        if not panchayat_name:
            messagebox.showwarning("Input Needed", "Please enter a Panchayat Name for the report filename.", parent=self)
            return

        if "CSV" in export_format:
            safe_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"Work_Allocation_Report_{safe_name}_{timestamp}.csv"
            self.export_treeview_to_csv(self.results_tree, default_filename)
            return
            
        data, file_path = self._get_filtered_data_and_filepath(export_format)
        if not data: return

        if "PDF" in export_format:
            self._handle_pdf_export(data, file_path)

    def _get_filtered_data_and_filepath(self, export_format):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        all_items = self.results_tree.get_children()
        if not all_items: messagebox.showinfo("No Data", "There are no results to export."); return None, None
        
        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in all_items:
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[2].upper()
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status: data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status: data_to_export.append(row_values)
        if not data_to_export: messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'."); return None, None

        safe_name = "".join(c for c in self.panchayat_entry.get().strip() if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        file_details = {"PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")], "title": "Save Report as PDF"}}
        details = file_details[export_format]
        filename = f"Work_Allocation_Report_{safe_name}_{timestamp}{details['ext']}"

        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_user_downloads_path(), initialfile=filename, title=details['title'])
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, file_path):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import NoAlertPresentException
        from selenium import webdriver
        try:
            headers = self.results_tree['columns']
            col_widths = [40, 70, 40, 70, 40] # Adjusted widths
            title = f"Work Allocation Report: {self.panchayat_entry.get().strip()}"
            report_date = datetime.now().strftime('%d %b %Y')
            
            success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
            
            if success:
                if messagebox.askyesno("Success", f"PDF Report exported to:\n{file_path}\n\nDo you want to open the file?"):
                    if sys.platform == "win32":
                        os.startfile(file_path)
                    else:
                        subprocess.call(['open', file_path])
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to create PDF file.\nError: {e}")

    def _save_inputs(self, inputs):
        """Saves the panchayat name and work category."""
        save_data = {
            'panchayat_name': inputs.get('panchayat_name'),
            'work_category': inputs.get('work_category')
        }
        try:
            config_file = self.app.get_data_path("work_alloc_inputs.json")
            with open(config_file, 'w') as f:
                json.dump(save_data, f, indent=4)
        except Exception as e:
            print(f"Error saving Work Allocation inputs: {e}")

    def load_inputs(self):
        """Loads the saved panchayat name and work category."""
        try:
            config_file = self.app.get_data_path("work_alloc_inputs.json")
            if not os.path.exists(config_file):
                return
            
            with open(config_file, 'r') as f:
                data = json.load(f)
            
            self.panchayat_entry.delete(0, tkinter.END)
            self.panchayat_entry.insert(0, data.get('panchayat_name', ''))
            
            saved_category = data.get('work_category')
            if saved_category:
                if saved_category in self.work_category_menu.cget("values"):
                    self.work_category_var.set(saved_category)
        except Exception as e:
            print(f"Error loading Work Allocation inputs: {e}")