# tabs/del_work_alloc_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException,
    WebDriverException
)

import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class DelWorkAllocTab(BaseAutomationTab):
    """
    A specific tab class for automating the deletion of Work Allocations on the NREGA website.
    Features:
    - Robust Page Loading (Handles 'execution context' errors).
    - Search by Panchayat (Case insensitive).
    - Filter by 'From Date'.
    - Manual List vs Auto Mode.
    """
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="del_work_alloc")
        
        # Configure Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) 
        
        self._create_widgets()

    def _create_widgets(self):
        """Initializes and packs the UI components."""
        
        # --- Section 1: Input Controls ---
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure(1, weight=1)

        # 1. Panchayat Name Input (with Autocomplete)
        ctk.CTkLabel(controls_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=(15, 5), pady=15)
        self.panchayat_entry = AutocompleteEntry(
            controls_frame, 
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app,
            history_key="panchayat_name"
        )
        self.panchayat_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=15)

        # 2. Date Filter Input (From Date Only)
        date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        date_frame.grid(row=0, column=2, sticky='e', padx=15, pady=15)

        ctk.CTkLabel(date_frame, text="From Date:").pack(side="left", padx=(5, 5))
        
        self.from_date_entry = ctk.CTkEntry(date_frame, placeholder_text="DD/MM/YYYY", width=100)
        self.from_date_entry.pack(side="left", padx=5)

        # Calendar Icon Button
        self.cal_btn = ctk.CTkButton(
            date_frame, 
            text="📅", 
            width=35, 
            fg_color=("gray85", "gray25"), 
            hover_color=("gray75", "gray35"),
            text_color=("black", "white"),
            command=self._on_calendar_click
        )
        self.cal_btn.pack(side="left", padx=2)

        # 3. Explanatory Note
        note_text = "Note: Optional. Select a date to delete specific allocations only. Leave empty to delete ALL."
        note_label = ctk.CTkLabel(
            controls_frame, 
            text=note_text, 
            font=ctk.CTkFont(size=11, slant="italic"), 
            text_color="gray60", 
            justify="left"
        )
        note_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 10))

        # --- Section 2: Action Buttons (Start/Stop) ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,10))

        # --- Section 3: Data Notebook ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0,10))
        
        jobcards_tab = data_notebook.add("Jobcards / Reg IDs")
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # Tab A: Jobcards / Registration IDs
        jobcards_tab.grid_rowconfigure(1, weight=1)
        jobcards_tab.grid_columnconfigure(0, weight=1)

        jc_header_frame = ctk.CTkFrame(jobcards_tab, fg_color="transparent")
        jc_header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        ctk.CTkLabel(jc_header_frame, text="Enter Jobcard / Registration IDs (one per line).\nIf left empty, the bot will process all IDs for the selected Panchayat.", wraplength=700, justify="left").pack(side="left", padx=5)
        
        clear_jc_button = ctk.CTkButton(jc_header_frame, text="Clear", width=80, command=lambda: self.jobcards_text.delete("1.0", "end"))
        clear_jc_button.pack(side="right")

        self.jobcards_text = ctk.CTkTextbox(jobcards_tab, height=150)
        self.jobcards_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # Tab B: Results Table
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        self.export_csv_button = ctk.CTkButton(results_action_frame, text="Export to CSV", command=lambda: self.export_treeview_to_csv(self.results_tree, "delete_work_alloc_results.csv"))
        self.export_csv_button.pack(side="left")

        cols = ("Timestamp", "Panchayat", "Jobcard/RegID", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        
        self.results_tree.column("Timestamp", width=80, anchor='center')
        self.results_tree.column("Panchayat", width=150)
        self.results_tree.column("Jobcard/RegID", width=200)
        self.results_tree.column("Status", width=100, anchor='center')
        self.results_tree.column("Details", width=350)
        
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        
        self.style_treeview(self.results_tree)

    def _on_calendar_click(self):
        """Uses the BaseAutomationTab's centralized method to open the date picker."""
        def set_date(selected_date):
            self.from_date_entry.delete(0, tkinter.END)
            self.from_date_entry.insert(0, selected_date)
            
        self.open_date_picker(set_date)

    def set_ui_state(self, running: bool):
        """Locks/Unlocks UI elements during automation."""
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.from_date_entry.configure(state=state)
        self.cal_btn.configure(state=state)
        self.jobcards_text.configure(state=state)

    def start_automation(self):
        """Validates inputs and spawns the automation thread."""
        panchayat = self.panchayat_entry.get().strip()
        from_date = self.from_date_entry.get().strip()

        if not panchayat:
            messagebox.showwarning("Input Error", "Panchayat Name is required.")
            return

        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        jobcard_list = [line.strip() for line in self.jobcards_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]
        
        self.app.update_history("panchayat_name", panchayat)
        
        # Start Thread
        self.app.start_automation_thread(
            self.automation_key, 
            self.run_automation_logic, 
            args=(panchayat, jobcard_list, from_date)
        )

    def reset_ui(self):
        """Resets the form to default state."""
        if messagebox.askokcancel("Reset Form?", "Clear all inputs and logs?"):
            self.panchayat_entry.delete(0, tkinter.END)
            self.from_date_entry.delete(0, tkinter.END)
            self.jobcards_text.delete('1.0', tkinter.END)
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.app.log_message(self.log_display, "Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    def _safe_load_page(self, driver, url):
        """
        Robustly loads a page with retries, specifically handling
        'frame does not have execution context' errors.
        """
        for attempt in range(3):
            try:
                self.app.log_message(self.log_display, f"Loading page (Attempt {attempt+1})...")
                driver.get(url)
                # Check for alert immediately after load (session expired?)
                try:
                    WebDriverWait(driver, 2).until(EC.alert_is_present())
                    driver.switch_to.alert.accept()
                except TimeoutException:
                    pass
                return True
            except Exception as e:
                err_msg = str(e).lower()
                if "execution context" in err_msg or "target window already closed" in err_msg:
                    self.app.log_message(self.log_display, "   -> Browser glitch detected. Retrying...", "warning")
                    try: 
                        # Try to stop loading or refresh to reset state
                        driver.execute_script("window.stop();")
                    except: 
                        pass
                    time.sleep(2)
                else:
                    raise e # Raise other errors normally
        return False

    def run_automation_logic(self, panchayat, jobcard_list, target_from_date):
        """
        The main worker function.
        """
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        
        mode_msg = f"Filtering Date: {target_from_date}" if target_from_date else "Mode: Delete ALL"
        self.app.log_message(self.log_display, f"Starting Delete Work Alloc. {mode_msg}")
        self.app.after(0, self.app.set_status, "Running Delete Work Allocation...")

        try:
            driver = self.app.get_driver()
            if not driver:
                return

            auto_mode = not bool(jobcard_list)
            items_to_process = []

            # 1. Navigate Safely
            url = config.DEL_WORK_ALLOC_CONFIG["url"]
            if not self._safe_load_page(driver, url):
                raise Exception("Failed to load page after multiple attempts.")

            # 2. Select Panchayat (With Fuzzy Match)
            wait = WebDriverWait(driver, 20)
            
            try:
                # Ensure the dropdown is actually visible and interactive
                panchayat_dropdown_elem = wait.until(EC.visibility_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code")))
                panchayat_dropdown = Select(panchayat_dropdown_elem)
                
                # --- Fuzzy Matching Logic ---
                target_p = panchayat.strip().lower()
                found_option_text = None
                
                for opt in panchayat_dropdown.options:
                    if opt.text.strip().lower() == target_p:
                        found_option_text = opt.text
                        break
                
                if found_option_text:
                    self.app.log_message(self.log_display, f"Selecting Panchayat: '{found_option_text}'...")
                    
                    # Store current body element to check for staleness (Postback detection)
                    body_elem = driver.find_element(By.TAG_NAME, "body")
                    
                    panchayat_dropdown.select_by_visible_text(found_option_text)
                    
                    # --- CRITICAL: Wait for Postback ---
                    # Selection triggers __doPostBack. We MUST wait for the page to reload.
                    self.app.log_message(self.log_display, "Waiting for page reload (Postback)...")
                    try:
                        wait.until(EC.staleness_of(body_elem))
                    except TimeoutException:
                        self.app.log_message(self.log_display, "Warning: Page did not seem to reload. Continuing...", "warning")
                    
                    # Wait for Registration dropdown to come back
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration")))
                    self.app.log_message(self.log_display, "Panchayat selected successfully.", "success")
                    
                else:
                    available = [o.text for o in panchayat_dropdown.options[:10]]
                    raise ValueError(f"Panchayat '{panchayat}' not found. Did you mean: {available}?")

            except Exception as e:
                self.app.log_message(self.log_display, f"Error selecting Panchayat: {e}", "error")
                return

            # 3. Determine Items to Process
            if auto_mode:
                self.app.log_message(self.log_display, "Auto Mode: Fetching all Registration IDs.")
                # Locate dropdown again after refresh
                reg_id_dropdown = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration"))))
                items_to_process = [opt.get_attribute("value") for opt in reg_id_dropdown.options if opt.get_attribute("value") and "Select" not in opt.text]
                
                if not items_to_process:
                    self.app.log_message(self.log_display, "No Registration IDs found for this Panchayat.", "warning")
            else:
                self.app.log_message(self.log_display, f"Manual Mode: Processing {len(jobcard_list)} provided IDs.")
                items_to_process = jobcard_list

            # 4. Process Loop
            total_items = len(items_to_process)
            for i, item_id in enumerate(items_to_process):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Automation stopped by user.", "warning")
                    break
                
                self.app.after(0, self.update_status, f"Processing {i+1}/{total_items}: {item_id}", (i+1) / total_items)
                
                # Execute the scraping/action logic
                self._process_single_id(driver, wait, panchayat, item_id, auto_mode, target_from_date)

            # 5. Completion
            final_msg = "Automation finished." if not self.app.stop_events[self.automation_key].is_set() else "Stopped."
            self.app.after(0, self.update_status, final_msg, 1.0)
            if not self.app.stop_events[self.automation_key].is_set():
                messagebox.showinfo("Complete", "Delete Work Allocation process has finished.")

        except Exception as e:
            # Uses the Centralized Error Handler from BaseAutomationTab
            self.handle_error(e)

        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _process_single_id(self, driver, wait, panchayat, item_id, is_auto_mode, filter_from):
        """
        Processes a single Jobcard/Reg ID.
        """
        try:
            # A. Select or Search the ID
            if not is_auto_mode:
                self.app.log_message(self.log_display, f"Searching for Jobcard/RegID: {item_id}")
                search_box = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtRegSearch")))
                search_box.clear()
                search_box.send_keys(item_id)
                search_box.send_keys(Keys.TAB)
                
                # Wait for dropdown update
                # Using a generic wait to allow the dropdown to repopulate
                time.sleep(1.5) 

            reg_id_dropdown_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration")))
            reg_id_dropdown = Select(reg_id_dropdown_element)

            if is_auto_mode:
                reg_id_dropdown.select_by_value(item_id)
            else: 
                # In manual mode, select index 1 (the result of search)
                if len(reg_id_dropdown.options) > 1:
                    reg_id_dropdown.select_by_index(1)
                else:
                    raise ValueError("Jobcard search returned no results.")

            # B. Check the Grid View
            grid_view = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_GridView1")))
            self.app.log_message(self.log_display, f"Details loaded for {item_id}.")
            
            any_checked = False
            
            # C. Logic: Filter by Date OR Select All
            if filter_from:
                # --- Filter Mode ---
                date_labels = grid_view.find_elements(By.XPATH, ".//span[contains(@id, '_lblAllocFrom')]")
                
                if not date_labels:
                        self._log_result(panchayat, item_id, "Skipped", "No allocation rows found.")
                        return

                matches_found = 0
                for from_label in date_labels:
                    row_from_text = from_label.text.strip()
                    
                    if row_from_text == filter_from:
                        # Derive checkbox ID from the label ID
                        # ID format: ..._lblAllocFrom -> ..._chkAllocate
                        chk_id = from_label.get_attribute("id").replace("lblAllocFrom", "chkAllocate")
                        try:
                            checkbox = driver.find_element(By.ID, chk_id)
                            if not checkbox.is_selected():
                                checkbox.click()
                                any_checked = True
                                matches_found += 1
                        except NoSuchElementException:
                            continue
                        
                if not any_checked:
                    self._log_result(panchayat, item_id, "Skipped", f"No rows matched date: {filter_from}")
                    return
                else:
                    self.app.log_message(self.log_display, f"Found {matches_found} matching allocation(s).")

            else:
                # --- Select All Mode ---
                try:
                    select_all_checkbox = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_GridView1_ctl01_chkHAllocate")
                    select_all_checkbox.click()
                    any_checked = True
                except NoSuchElementException:
                    self._log_result(panchayat, item_id, "Skipped", "No work allocations found to delete.")
                    return

            # D. Submit if necessary
            if any_checked:
                time.sleep(0.5)
                proceed_button = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_cmdUpdate")
                proceed_button.click()
                
                try:
                    # Wait for page reload (stale element)
                    wait.until(EC.staleness_of(grid_view))
                    msg = f"Allocations deleted (Date: {filter_from})" if filter_from else "All allocations deleted."
                    self._log_result(panchayat, item_id, "Success", msg)
                except TimeoutException:
                    # Check for explicit error message on page
                    try:
                        error_element = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_lblMsg")
                        error_text = error_element.text.strip()
                        self._log_result(panchayat, item_id, "Failed", error_text if error_text else "Unknown error after clicking proceed.")
                    except NoSuchElementException:
                        self._log_result(panchayat, item_id, "Failed", "Page did not reload and no error message found.")

        except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ValueError) as e:
            # Handle item-specific errors without crashing the whole thread
            error_msg = str(e).split('\n')[0]
            self.app.log_message(self.log_display, f"Failed to process {item_id}: {error_msg}", "error")
            self._log_result(panchayat, item_id, "Failed", error_msg)
            
            # Attempt Recovery (Reload page to reset state)
            try:
                driver.get(config.DEL_WORK_ALLOC_CONFIG["url"])
                # We need to re-select Panchayat here because page reloaded to start fresh
                # But implementing full re-selection logic here is complex. 
                # Better to just let the loop continue; the next iteration will fail and trigger this block again if not careful.
                # However, since we are inside a loop that assumes Panchayat is selected, we must re-select it.
                
                wait.until(EC.visibility_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code")))
                p_dropdown = Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code"))
                
                # Quick Fuzzy Match
                target_p = panchayat.strip().lower()
                for opt in p_dropdown.options:
                    if opt.text.strip().lower() == target_p:
                        p_dropdown.select_by_visible_text(opt.text)
                        break
                
                wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlRegistration")))

            except Exception as recovery_e:
                self.app.log_message(self.log_display, f"Recovery failed: {recovery_e}", "error")

    def _log_result(self, panchayat, item_id, status, details):
        """Adds a row to the Results Treeview."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (timestamp, panchayat, item_id, status, details)
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=values))