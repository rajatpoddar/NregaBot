# tabs/del_demand_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime
import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class DelDemandTab(BaseAutomationTab):
    """
    Tab for automating the deletion of Demands on the VB-G-RAM-G portal.
    Features:
    - Supports both PO and GP logins (auto-detects Panchayat dropdown).
    - Can process a single village or iterate through ALL villages in a Panchayat.
    - Handles JavaScript confirmation alerts automatically.
    - Smart checkbox toggle to bypass NREGA state persistence bugs.
    - Captures and logs Jobcard & Applicant Name for each deleted row.
    """
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="del_demand")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) 
        
        self._create_widgets()

    def _create_widgets(self):
        # --- Section 1: Input Controls ---
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure(1, weight=1)
        controls_frame.grid_columnconfigure(3, weight=1)

        # 1. Panchayat Name Input
        ctk.CTkLabel(controls_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=(15, 5), pady=15)
        self.panchayat_entry = AutocompleteEntry(
            controls_frame, 
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app,
            history_key="panchayat_name"
        )
        self.panchayat_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=15)

        # 2. Village Name Input (Optional)
        ctk.CTkLabel(controls_frame, text="Village Name:").grid(row=0, column=2, sticky='w', padx=(15, 5), pady=15)
        self.village_entry = AutocompleteEntry(
            controls_frame, 
            suggestions_list=self.app.history_manager.get_suggestions("village_name"),
            app_instance=self.app,
            history_key="village_name"
        )
        self.village_entry.grid(row=0, column=3, sticky='ew', padx=(5, 15), pady=15)

        # 3. Explanatory Note
        note_text = "Note: If Village Name is left empty, the bot will process ALL villages in the selected Panchayat."
        note_label = ctk.CTkLabel(controls_frame, text=note_text, font=ctk.CTkFont(size=11, slant="italic"), text_color="gray60")
        note_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=15, pady=(0, 10))

        # --- Section 2: Action Buttons ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,10))

        # --- Section 3: Data Notebook ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0,10))
        
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # Tab: Results Table
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        self.export_csv_button = ctk.CTkButton(results_action_frame, text="Export to CSV", command=lambda: self.export_treeview_to_csv(self.results_tree, "delete_demand_results.csv"))
        self.export_csv_button.pack(side="left")

        # Naya Column add kiya gaya hai: Applicant Info
        cols = ("Timestamp", "Panchayat", "Village", "Applicant Info", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        
        self.results_tree.column("Timestamp", width=80, anchor='center')
        self.results_tree.column("Panchayat", width=120)
        self.results_tree.column("Village", width=120)
        self.results_tree.column("Applicant Info", width=250)
        self.results_tree.column("Status", width=90, anchor='center')
        self.results_tree.column("Details", width=200)
        
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.village_entry.configure(state=state)

    def start_automation(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver
        panchayat = self.panchayat_entry.get().strip()
        village = self.village_entry.get().strip()

        if not panchayat:
            messagebox.showwarning("Input Error", "Panchayat Name is required.")
            return

        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        self.app.update_history("panchayat_name", panchayat)
        if village:
            self.app.update_history("village_name", village)
        
        self.app.start_automation_thread(
            self.automation_key, 
            self.run_automation_logic, 
            args=(panchayat, village)
        )

    def run_automation_logic(self, target_panchayat, target_village):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        
        mode_msg = f"Target Village: {target_village}" if target_village else "Mode: ALL Villages"
        self.app.log_message(self.log_display, f"Starting Delete Demand. {mode_msg}")
        self.app.after(0, self.app.set_status, "Running Delete Demand...")

        try:
            driver = self.app.get_driver()
            if not driver: return

            wait = WebDriverWait(driver, 15)
            url = config.DEL_DEMAND_CONFIG.get("url", "https://nregade4.dord.gov.in/Netnrega/deletedemand.aspx")
            
            self.app.log_message(self.log_display, "Navigating to Delete Demand page...")
            driver.get(url)

            # 1. Select Panchayat (If Dropdown Exists - Handles PO vs GP login)
            try:
                panchayat_dd_elem = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Panchyt")
                panchayat_dropdown = Select(panchayat_dd_elem)
                
                found_p = None
                target_p_lower = target_panchayat.lower()
                for opt in panchayat_dropdown.options:
                    if target_p_lower in opt.text.lower():
                        found_p = opt.text
                        break
                        
                if found_p:
                    self.app.log_message(self.log_display, f"Selecting Panchayat: '{found_p}'...")
                    panchayat_dropdown.select_by_visible_text(found_p)

                    # Wait for village dropdown to populate after panchayat postback
                    fast_wait = WebDriverWait(driver, 20, poll_frequency=0.3)
                    try:
                        fast_wait.until(lambda d: len(Select(
                            d.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")
                        ).options) > 1)
                    except TimeoutException:
                        pass
                else:
                    raise ValueError(f"Panchayat '{target_panchayat}' not found in dropdown.")
            except NoSuchElementException:
                self.app.log_message(self.log_display, "Panchayat dropdown not found. Assuming GP Login.", "info")

            # 2. Get list of Villages
            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")))
            village_dropdown = Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village"))
            
            villages_to_process = []
            if target_village:
                for opt in village_dropdown.options:
                    if target_village.lower() in opt.text.lower() and "Select" not in opt.text:
                        villages_to_process.append(opt.text)
                        break
                if not villages_to_process:
                    raise ValueError(f"Village '{target_village}' not found.")
            else:
                villages_to_process = [opt.text for opt in village_dropdown.options if "Select" not in opt.text]

            self.app.log_message(self.log_display, f"Found {len(villages_to_process)} village(s) to process.")

            # 3. Iterate through Villages
            total_v = len(villages_to_process)
            for i, v_name in enumerate(villages_to_process):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Automation stopped by user.", "warning")
                    break
                    
                self.app.after(0, self.update_status, f"Processing {i+1}/{total_v}: {v_name}", (i+1)/total_v)
                
                # After first village, re-navigate and RESET page state completely
                if i > 0:
                    self.app.log_message(self.log_display, f"Re-navigating to page for next village...")
                    
                    # ⬇️ FIX: Navigate to blank page FIRST to clear ASP.NET session/viewstate
                    try:
                        driver.get("about:blank")
                        WebDriverWait(driver, 10).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                    except Exception:
                        pass
                    time.sleep(0.5)
                    
                    driver.get(url)
                    try:
                        WebDriverWait(driver, 20).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                    except Exception:
                        pass
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_'))
                        )
                    except (TimeoutException, NoSuchElementException):
                        pass
                    
                    try:
                        wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDL_Panchyt")))
                    except TimeoutException:
                        self.app.log_message(self.log_display, f"   ⚠️ Panchayat dropdown not found after re-navigation!", "warning")
                        continue  # Skip this village instead of crashing
                    
                    try:
                        panchayat_dd_elem = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Panchyt")
                        panchayat_dropdown = Select(panchayat_dd_elem)
                        found_p = None
                        target_p_lower = target_panchayat.lower()
                        for opt in panchayat_dropdown.options:
                            if target_p_lower in opt.text.lower():
                                found_p = opt.text
                                break
                        if found_p:
                            panchayat_dropdown.select_by_visible_text(found_p)
                            time.sleep(0.5)  # Wait for postback to begin
                            fast_wait = WebDriverWait(driver, 20, poll_frequency=0.3)
                            try:
                                fast_wait.until(lambda d: len(Select(
                                    d.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")
                                ).options) > 1)
                            except TimeoutException:
                                self.app.log_message(self.log_display, f"   ⚠️ Village dropdown didn't populate after panchayat re-select.", "warning")
                    except NoSuchElementException:
                        self.app.log_message(self.log_display, f"   ⚠️ Panchayat dropdown not found (GP Login?).", "info")
                
                self._process_village(driver, wait, target_panchayat, v_name)

            final_msg = "Finished" if not self.app.stop_events[self.automation_key].is_set() else "Stopped"
            self.app.after(0, self.update_status, final_msg, 1.0)
            if not self.app.stop_events[self.automation_key].is_set():
                messagebox.showinfo("Complete", "Delete Demand process has finished.")

        except Exception as e:
            self.handle_error(e)
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")

    def _process_village(self, driver, wait, panchayat, village_name):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium import webdriver
        try:
            # Re-find dropdown (to avoid stale element after postbacks)
            village_dd_elem = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")))
            village_dropdown = Select(village_dd_elem)
            
            # Verify the village option exists before selecting
            village_texts = [opt.text.strip() for opt in village_dropdown.options]
            if village_name not in village_texts:
                self.app.log_message(self.log_display, f"   ⚠️ Village '{village_name}' not in dropdown options. Skipping.", "warning")
                self._log_result(panchayat, village_name, "-", "Skipped", "Village not found in dropdown after navigation.")
                return
            
            village_dropdown.select_by_visible_text(village_name)
            self.app.log_message(self.log_display, f"📍 Selected: {village_name}. Waiting for data...")

            no_data_locator = (By.ID, "ctl00_ContentPlaceHolder1_nodata_msg")
            grid_locator    = (By.ID, "ctl00_ContentPlaceHolder1_grd_AppRecord")

            # Wait for AJAX postback to complete (slower server = longer wait)
            fast_wait = WebDriverWait(driver, 20, poll_frequency=0.3)

            def page_settled(d):
                # Confirm dropdown selection took effect
                # ---- Lazy imports ----
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import Select, WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
                from selenium import webdriver
                try:
                    dd = Select(d.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village"))
                    if dd.first_selected_option.text.strip() != village_name:
                        return False  # AJAX still running, dropdown reset
                except Exception:
                    return False

                # Check 1: message element has non-empty text (no-data / already deleted)
                try:
                    msg = d.find_element(*no_data_locator)
                    if msg.text.strip():
                        return True
                except Exception:
                    pass

                # Check 2: grid is visible and has data rows (demands loaded)
                try:
                    grid_el = d.find_element(*grid_locator)
                    if grid_el.is_displayed():
                        rows = grid_el.find_elements(By.XPATH, ".//tr[position()>1]")
                        if rows:
                            return True  # Grid with data rows = page settled
                except Exception:
                    pass

                # Neither message nor grid with data found yet — KEEP WAITING!
                return False

            try:
                fast_wait.until(page_settled)
            except TimeoutException:
                self.app.log_message(self.log_display, f"   ⏱ Village {village_name}: AJAX postback timed out, proceeding anyway...", "warning")

            # --- Early exit: "no data" / "already deleted" message ---
            try:
                msg_elem = driver.find_element(*no_data_locator)
                msg_text = msg_elem.text.strip()
                if msg_text:
                    self.app.log_message(self.log_display, f"   ℹ️ {village_name}: {msg_text}. Skipping.")
                    self._log_result(panchayat, village_name, "-", "Skipped", msg_text)
                    return
            except NoSuchElementException:
                pass

            # Step A: Check if grid exists
            try:
                grid = driver.find_element(*grid_locator)
                if not grid.is_displayed():
                    self.app.log_message(self.log_display, f"   ℹ️ {village_name}: Grid hidden. No pending demands.", "info")
                    self._log_result(panchayat, village_name, "-", "Skipped", "Grid not visible - no data.")
                    return
            except NoSuchElementException:
                self.app.log_message(self.log_display, f"   ℹ️ {village_name}: No grid found. No pending demands.", "info")
                self._log_result(panchayat, village_name, "-", "Skipped", "No pending demands found in this village.")
                return

            # Step B: Extract Jobcard and Applicant Details
            jobcards_in_village = []
            rows = grid.find_elements(By.XPATH, ".//tr[position()>1]") # Skip header row
            for row in rows:
                tds = row.find_elements(By.TAG_NAME, "td")
                if len(tds) >= 3:
                    # Column 0: Reg No. | Column 2: Applicant Name
                    jc_no = tds[0].text.strip()
                    app_name = tds[2].text.strip()
                    if jc_no:
                        jobcards_in_village.append(f"{jc_no} | {app_name}")
            
            if not jobcards_in_village:
                self.app.log_message(self.log_display, f"   ℹ️ {village_name}: No valid data rows in grid.", "info")
                self._log_result(panchayat, village_name, "-", "Skipped", "No valid data rows found in grid.")
                return

            self.app.log_message(self.log_display, f"   ✅ Found {len(jobcards_in_village)} demand(s) to delete in {village_name}.")

            # Step C: Smart Checkbox Toggle (User's Logic)
            try:
                check_all_box = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_chkdel")
                
                # ⬇️ FIX: Scroll into view + JavaScript click (works even if tab is in background)
                driver.execute_script("arguments[0].scrollIntoView(true);", check_all_box)
                time.sleep(0.3)
                
                if check_all_box.is_selected():
                    self.app.log_message(self.log_display, f"   🔄 Checkbox was already checked, toggling...")
                    driver.execute_script("arguments[0].click();", check_all_box)
                    time.sleep(0.3)
                
                # JavaScript click — works reliably even when tab is not focused
                driver.execute_script("arguments[0].click();", check_all_box)
                time.sleep(0.5)
                
                # Verify checkbox state — retry once if not checked
                if not check_all_box.is_selected():
                    self.app.log_message(self.log_display, f"   🔄 First JS click didn't register, retrying...")
                    driver.execute_script("arguments[0].click();", check_all_box)
                    time.sleep(0.3)
                
                checked = check_all_box.is_selected()
                if checked:
                    self.app.log_message(self.log_display, f"   ☑️ Select All checkbox ticked successfully!")
                else:
                    self.app.log_message(self.log_display, f"   ❌ Could not tick the select-all checkbox!", "error")
                    self._log_result(panchayat, village_name, "-", "Failed", "Could not tick select-all checkbox.")
                    return
                    
            except NoSuchElementException:
                self.app.log_message(self.log_display, f"   ❌ {village_name}: Check ALL box not found!", "error")
                self._log_result(panchayat, village_name, "-", "Failed", "Check ALL box not found.")
                return

            # Step D: Click Delete Button
            try:
                delete_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btndel")
                delete_btn.click()
                self.app.log_message(self.log_display, f"   🗑️ Delete button clicked, handling confirmation...")
                
                # Handle JS Alert
                try:
                    alert = wait.until(EC.alert_is_present())
                    alert_text = alert.text
                    self.app.log_message(self.log_display, f"   ⚠️ Alert: '{alert_text}' → Accepting...")
                    alert.accept()
                    time.sleep(0.5)  # Brief wait for postback to begin
                except TimeoutException:
                    self.app.log_message(self.log_display, f"   ℹ️ No JS alert appeared, proceeding...", "info")
                
                # Step E: Wait for Success Message and Log Results
                success_msg_locator = (By.ID, "ctl00_ContentPlaceHolder1_del_msg")
                try:
                    msg_elem = wait.until(EC.presence_of_element_located(success_msg_locator))
                    server_msg = msg_elem.text.strip()
                    self.app.log_message(self.log_display, f"   ✅ {village_name}: Server response: '{server_msg}'")
                    
                    # Log each deleted jobcard individually
                    for info in jobcards_in_village:
                        self._log_result(panchayat, village_name, info, "Success", server_msg)
                        
                except TimeoutException:
                    self.app.log_message(self.log_display, f"   ⚠️ {village_name}: Could not verify success message (timeout).", "warning")
                    for info in jobcards_in_village:
                        self._log_result(panchayat, village_name, info, "Failed", "Could not verify success message.")

            except NoSuchElementException:
                self.app.log_message(self.log_display, f"   ❌ {village_name}: Delete button not found!", "error")
                self._log_result(panchayat, village_name, "-", "Failed", "Delete button not found.")

        except (StaleElementReferenceException, Exception) as e:
            error_msg = str(e).split('\n')[0]
            self.app.log_message(self.log_display, f"   ❌ Error on {village_name}: {error_msg}", "error")
            self._log_result(panchayat, village_name, "-", "Error", error_msg)

    def _log_result(self, panchayat, village, applicant_info, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (timestamp, panchayat, village, applicant_info, status, details)
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=values))