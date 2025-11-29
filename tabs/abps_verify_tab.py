# tabs/abps_verify_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException

import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class AbpsVerifyTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="abps_verify")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_widgets()

    def _create_widgets(self):
        # --- Controls Frame ---
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        controls_frame.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        self.panchayat_entry = AutocompleteEntry(controls_frame, suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"))
        self.panchayat_entry.grid(row=0, column=1, sticky="ew", padx=(0, 15), pady=(15, 5))

        ctk.CTkLabel(controls_frame, text="Village:").grid(row=0, column=2, sticky="w", padx=15, pady=(15, 5))
        self.village_entry = AutocompleteEntry(controls_frame, suggestions_list=self.app.history_manager.get_suggestions("village_name"))
        self.village_entry.grid(row=0, column=3, sticky="ew", padx=(0, 15), pady=(15, 5))

        # --- NEW: Note for auto-mode ---
        ctk.CTkLabel(controls_frame, text="ℹ️ Leave Village empty to process all villages automatically.", text_color="gray50").grid(row=1, column=1, columnspan=3, sticky="w", padx=15, pady=(0, 15))

        # --- Action Buttons ---
        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=15, padx=15)

        # --- Results and Logs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        results_frame = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)

        #Results Frame Configuration
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1) # Make space for the button

        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        self.export_csv_button = ctk.CTkButton(results_action_frame, text="Export to CSV", command=lambda: self.export_treeview_to_csv(self.results_tree, "abps_verify_results.csv"))
        self.export_csv_button.pack(side="left")

        cols = ("Job Card No.", "Applicant Name", "Status", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        self.results_tree.column("Job Card No.", width=200)
        self.results_tree.column("Applicant Name", width=200)
        self.results_tree.column("Status", width=150, anchor='center')
        self.results_tree.column("Timestamp", width=100, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.village_entry.configure(state=state)

    def start_automation(self):
        panchayat = self.panchayat_entry.get().strip()
        village = self.village_entry.get().strip() # Can be empty for auto-mode
        if not panchayat:
            messagebox.showwarning("Input Required", "Please enter a Panchayat name.")
            return
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(panchayat, village))

    def reset_ui(self):
        if messagebox.askokcancel("Reset Form?", "Clear all inputs and logs?"):
            self.panchayat_entry.delete(0, tkinter.END)
            self.village_entry.delete(0, tkinter.END)
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.app.log_message(self.log_display, "Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")


    def run_automation_logic(self, panchayat, village):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.app.after(0, lambda: [self.results_tree.delete(item) for item in self.results_tree.get_children()])
        self.app.log_message(self.log_display, "Starting ABPS Verification...")
        self.app.after(0, self.app.set_status, "Running ABPS Verification...")

        session_processed_jobcards = set()

        try:
            driver = self.app.get_driver()
            if not driver: return

            wait = WebDriverWait(driver, 20)
            short_wait = WebDriverWait(driver, 5)
            
            # Navigate
            driver.get(config.ABPS_VERIFY_CONFIG["url"])
            
            # --- CHECK URL (Prevent errors on Login Page) ---
            current_url = driver.current_url
            self.app.log_message(self.log_display, f"Loaded URL: {current_url}")
            
            if "login" in current_url.lower():
                self.app.log_message(self.log_display, "Error: Redirected to Login page. Please log in first.", "error")
                messagebox.showerror("Session Expired", "It seems your session has expired. Please log in again.")
                return

            # 1. Select Panchayat
            self.app.log_message(self.log_display, f"Selecting Panchayat: {panchayat}")

            # Strategy: Use CSS Selector with wildcard (id*='DDL_panchayat') to match ANY ID containing DDL_panchayat
            try:
                # First wait for ANY select to appear (ensures page loaded)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
                
                # Find Panchayat Dropdown Robustly
                panchayat_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select[id*='DDL_panchayat']")))
                
                # Scroll into view (fixes issues if element is off-screen)
                driver.execute_script("arguments[0].scrollIntoView(true);", panchayat_select)
                
                Select(panchayat_select).select_by_visible_text(panchayat)
                self.app.update_history("panchayat_name", panchayat)
                time.sleep(1) # Allow page to refresh
                
            except TimeoutException:
                # Fallback: Try Name attribute if ID fails
                try:
                    panchayat_select = driver.find_element(By.NAME, "ctl00$ContentPlaceHolder1$DDL_panchayat")
                    Select(panchayat_select).select_by_visible_text(panchayat)
                    self.app.update_history("panchayat_name", panchayat)
                    time.sleep(1)
                except Exception:
                     raise Exception("Could not find Panchayat dropdown. Please ensure you are logged in and on the correct page.")

            # 2. Handle Village Dropdown (CSS Selector)
            village_css = "select[id*='DDL_Village']"
            
            # Wait for options > 1 (Loaded)
            wait.until(lambda d: len(Select(d.find_element(By.CSS_SELECTOR, village_css)).options) > 1)
            
            village_select_elem = driver.find_element(By.CSS_SELECTOR, village_css)
            all_villages = [opt.text for opt in Select(village_select_elem).options if opt.get_attribute("value") != "00"]
            
            villages_to_process = [village] if village else all_villages
            if village and village not in all_villages:
                raise ValueError(f"Village '{village}' not found.")

            # --- VILLAGE LOOP ---
            for i, current_village in enumerate(villages_to_process):
                if self.app.stop_events[self.automation_key].is_set(): break
                self.app.log_message(self.log_display, f"\n--- Processing Village {i+1}/{len(villages_to_process)}: {current_village} ---")
                
                try:
                    # Re-find element using CSS Selector
                    Select(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, village_css)))).select_by_visible_text(current_village)
                    self.app.update_history("village_name", current_village)
                    
                    # Table handling...
                    table_xpath = "//table[contains(@id, 'gvData')]"
                    try:
                        short_wait.until(EC.presence_of_element_located((By.XPATH, table_xpath)))
                    except TimeoutException:
                        self.app.log_message(self.log_display, f"No records found for {current_village}. Skipping.", "warning")
                        continue

                    page_number = 1
                    while True:
                        if self.app.stop_events[self.automation_key].is_set(): break
                        self.app.log_message(self.log_display, f"Scanning page {page_number}...")
                        
                        page_processed_count = 0
                        while True:
                            if self.app.stop_events[self.automation_key].is_set(): break

                            # Row XPath logic
                            unprocessed_rows_xpath = f"//table[contains(@id, 'gvData')]/tbody/tr[position()>1 and .//input[contains(@id, 'btn_showuid')]]"
                            potential_rows = driver.find_elements(By.XPATH, unprocessed_rows_xpath)
                            
                            row_to_process = None
                            job_card, app_name = "N/A", "N/A"
                            unique_key = None
                            
                            for row in potential_rows:
                                try:
                                    jc_num = row.find_element(By.XPATH, ".//td[2]").text
                                    ap_name = row.find_element(By.XPATH, ".//td[4]").text
                                    key = (jc_num, ap_name) 

                                    if key not in session_processed_jobcards:
                                        row_to_process = row
                                        job_card = jc_num
                                        app_name = ap_name
                                        unique_key = key
                                        break
                                except StaleElementReferenceException: continue
                            
                            if row_to_process is None:
                                self.app.log_message(self.log_display, "No new unprocessed records found on this page view.")
                                break

                            try:
                                self.app.after(0, self.update_status, f"Page {page_number}, Processing: {app_name}", 0.5)

                                row_to_process.find_element(By.XPATH, ".//input[contains(@id, 'btn_showuid')]").click()
                                wait.until(EC.staleness_of(row_to_process))

                                refreshed_row = wait.until(EC.presence_of_element_located((By.XPATH, f"//tr[contains(., '{job_card}') and contains(., '{app_name}')]")))
                                check_npci_btn = wait.until(EC.element_to_be_clickable(refreshed_row.find_element(By.XPATH, ".//input[contains(@id, 'btn_verifyuid')]")))
                                check_npci_btn.click()
                                wait.until(EC.staleness_of(refreshed_row))

                                final_row = wait.until(EC.presence_of_element_located((By.XPATH, f"//tr[contains(., '{job_card}') and contains(., '{app_name}')]")))
                                status_msg = final_row.find_element(By.XPATH, ".//td[9]/span").text
                                self._log_result(job_card, app_name, status_msg or "Checked")
                                
                            except (TimeoutException, StaleElementReferenceException, NoSuchElementException) as e:
                                self._log_result(job_card, app_name, f"Error: {type(e).__name__}")
                            finally:
                                if unique_key:
                                    session_processed_jobcards.add(unique_key)
                                    page_processed_count += 1
                        
                        if self.app.stop_events[self.automation_key].is_set(): break
                        
                        if page_processed_count > 0:
                            self.app.log_message(self.log_display, "Saving all verified records for this page...")
                            save_btn_css = "input[id*='btnProceed2']"
                            table_element = driver.find_element(By.XPATH, table_xpath)
                            driver.find_element(By.CSS_SELECTOR, save_btn_css).click()
                            wait.until(EC.staleness_of(table_element))
                            self.app.log_message(self.log_display, "Page saved.")

                        try:
                            next_page_link = driver.find_element(By.LINK_TEXT, str(page_number + 1))
                            self.app.log_message(self.log_display, "Moving to next page...")
                            table_element = driver.find_element(By.XPATH, table_xpath)
                            next_page_link.click()
                            wait.until(EC.staleness_of(table_element))
                            page_number += 1
                        except NoSuchElementException:
                            self.app.log_message(self.log_display, f"No more pages for {current_village}.")
                            break

                except Exception as village_error:
                    self.app.log_message(self.log_display, f"Error in {current_village}: {village_error}. Skipping.", "error")
                    continue
            
            final_msg = "Automation finished." if not self.app.stop_events[self.automation_key].is_set() else "Stopped."
            self.app.after(0, self.update_status, final_msg, 1.0)
            messagebox.showinfo("Complete", "ABPS verification process has finished.")

        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
            messagebox.showerror("Automation Error", f"An error occurred:\n\n{e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _log_result(self, job_card, app_name, status):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(job_card, app_name, status, timestamp)))