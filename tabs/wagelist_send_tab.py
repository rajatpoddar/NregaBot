# tabs/wagelist_send_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import config
from .base_tab import BaseAutomationTab

class WagelistSendTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="send")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) 
        
        self._create_widgets()

    def _create_widgets(self):
        settings_container = ctk.CTkFrame(self)
        settings_container.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        settings_container.grid_columnconfigure(1, weight=1)

        # Financial Year Selection
        ctk.CTkLabel(settings_container, text="Financial Year:").grid(row=0, column=0, padx=(15, 5), pady=10, sticky="w")
        
        current_year = datetime.now().year
        year_options = [f"{year}-{year+1}" for year in range(current_year + 1, current_year - 10, -1)]
        
        self.fin_year_combobox = ctk.CTkComboBox(settings_container, values=year_options)
        default_year = f"{current_year}-{current_year+1}" if datetime.now().month >= 4 else f"{current_year-1}-{current_year}"
        self.fin_year_combobox.set(default_year)
        self.fin_year_combobox.grid(row=0, column=1, padx=(0, 15), pady=10, sticky="ew")

        # --- NEW: Wagelist Range Selection ---
        ctk.CTkLabel(settings_container, text="Start Wagelist (optional):").grid(row=1, column=0, padx=(15, 5), pady=5, sticky="w")
        self.start_wagelist_entry = ctk.CTkEntry(settings_container, placeholder_text="e.g., 34...WL068545")
        self.start_wagelist_entry.grid(row=1, column=1, padx=(0, 15), pady=5, sticky="ew")

        ctk.CTkLabel(settings_container, text="End Wagelist (optional):").grid(row=2, column=0, padx=(15, 5), pady=5, sticky="w")
        self.end_wagelist_entry = ctk.CTkEntry(settings_container, placeholder_text="e.g., 34...WL068548")
        self.end_wagelist_entry.grid(row=2, column=1, padx=(0, 15), pady=5, sticky="ew")

        ctk.CTkLabel(settings_container, text="ℹ️ Leave both fields blank to process all wagelists for the selected year.", text_color="gray50").grid(row=3, column=0, columnspan=2, padx=15, pady=(5, 10))


        # Action Buttons
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        # Results and Logs
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0,10))
        results_frame = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        results_frame.grid_columnconfigure(0, weight=1); results_frame.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10), padx=5)

        self.export_csv_button = ctk.CTkButton(
            results_action_frame, 
            text="Export to CSV", 
            command=lambda: self.export_treeview_to_csv(self.results_tree, "wagelist_send_results.csv")
        )
        self.export_csv_button.pack(side="left")

        cols = ("Wagelist No.", "Status", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.fin_year_combobox.configure(state=state)
        self.start_wagelist_entry.configure(state=state)
        self.end_wagelist_entry.configure(state=state)

    def reset_ui(self):
        if messagebox.askokcancel("Reset Form?", "Are you sure?"):
            self.start_wagelist_entry.delete(0, tkinter.END)
            self.end_wagelist_entry.delete(0, tkinter.END)
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.app.log_message(self.log_display, "Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    def start_automation(self):
        fin_year = self.fin_year_combobox.get()
        if not fin_year:
            messagebox.showerror("Input Error", "Please select a Financial Year.")
            return
            
        start_wl = self.start_wagelist_entry.get().strip()
        end_wl = self.end_wagelist_entry.get().strip()

        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(fin_year, start_wl, end_wl))

    def populate_wagelist_data(self, start_wagelist, end_wagelist):
        """Receives data from another tab and updates the input fields."""
        # Clear existing content and insert the new values
        self.start_wagelist_entry.delete(0, 'end') 
        self.start_wagelist_entry.insert(0, start_wagelist)
        
        self.end_wagelist_entry.delete(0, 'end')
        self.end_wagelist_entry.insert(0, end_wagelist)
        
        self.app.log_message(self.log_display, f"Received Wagelist range: {start_wagelist} to {end_wagelist}")
        self.app.set_status("Ready to send wagelists")

    def run_automation_logic(self, fin_year, start_wl, end_wl):
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, lambda: [self.results_tree.delete(item) for item in self.results_tree.get_children()])
        self.app.clear_log(self.log_display)
        self.app.log_message(self.log_display, "Starting automation...")
        self.app.after(0, self.app.set_status, "Running Wagelist Send...")
        self.app.after(0, self.update_status, "Initializing...", 0.0) # <-- UPDATED
        
        automation_failed = False # Track errors
        
        try:
            driver = self.app.get_driver()
            if not driver: return
            wait = WebDriverWait(driver, 15)

            driver.get(config.WAGELIST_SEND_CONFIG["url"])
            
            self.app.log_message(self.log_display, f"Selecting Financial Year: {fin_year}")
            Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlfin")))).select_by_value(fin_year)
            
            self.app.log_message(self.log_display, "Waiting for wagelists to load...")
            wait.until(EC.element_to_be_clickable((By.XPATH, "//select[@id='ctl00_ContentPlaceHolder1_ddl_sel']/option[position()>1]")))
            time.sleep(1)

            all_wagelists = [o.get_attribute("value") for o in Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddl_sel")).options if o.get_attribute("value") != "select"]
            if not all_wagelists:
                self.app.log_message(self.log_display, "No wagelists found for the selected year.", "warning")
                messagebox.showwarning("No Wagelists", f"No wagelists were found for the financial year {fin_year}.")
                return
            
            # --- NEW: Filter wagelists based on user-provided range ---
            wagelists_to_process = all_wagelists
            if start_wl or end_wl:
                self.app.log_message(self.log_display, f"Filtering wagelists from '{start_wl or 'start'}' to '{end_wl or 'end'}'.")
                try:
                    start_index = all_wagelists.index(start_wl) if start_wl else 0
                    end_index = all_wagelists.index(end_wl) if end_wl else len(all_wagelists) - 1

                    if start_index > end_index:
                        messagebox.showerror("Input Error", "Start Wagelist must appear before End Wagelist in the dropdown.")
                        return
                    
                    wagelists_to_process = all_wagelists[start_index : end_index + 1]
                except ValueError:
                    messagebox.showerror("Input Error", "The specified Start or End Wagelist was not found in the list for this financial year.")
                    return
            
            self.app.log_message(self.log_display, f"Found {len(wagelists_to_process)} wagelists to process.")
            total = len(wagelists_to_process)
            for idx, wagelist in enumerate(wagelists_to_process, 1):
                if self.app.stop_events[self.automation_key].is_set():
                    break
                
                # --- UPDATED: Set both tab and app status ---
                status_msg = f"Processing {idx}/{total}: {wagelist}"
                self.app.after(0, self.update_status, status_msg, idx / total)
                self.app.after(0, self.app.set_status, status_msg)
                
                success = self._process_single_wagelist(driver, wait, wagelist, fin_year)
                self.app.after(0, lambda w=wagelist, s="Success" if success else "Failed", t=datetime.now().strftime("%H:%M:%S"): self.results_tree.insert("", tkinter.END, values=(w, s, t)))
                time.sleep(1)

        except Exception as e:
            automation_failed = True # Track errors
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
            messagebox.showerror("Automation Error", f"An error occurred: {e}")
        finally:
            stopped = self.app.stop_events[self.automation_key].is_set()

            # --- UPDATED: More robust final status logic ---
            if stopped:
                final_tab_msg = "Process stopped by user."
                final_app_msg = "Automation Stopped"
            elif automation_failed:
                final_tab_msg = "Failed"
                final_app_msg = "Automation Failed"
            else:
                final_tab_msg = "✅ All wagelists processed."
                final_app_msg = "Automation Finished"

            self.app.after(0, self.update_status, final_tab_msg, 1.0)
            self.app.after(0, self.app.set_status, final_app_msg)
            
            self.app.after(0, self.set_ui_state, False)
            
            if not stopped and not automation_failed:
                self.app.after(0, lambda: messagebox.showinfo("Automation Complete", "Wagelist sending process finished."))
            
            # Add delayed reset, like in mr_tracking_tab
            self.app.after(5000, lambda: self.app.set_status("Ready"))
            self.app.after(5000, lambda: self.update_status("Ready", 0.0))

    def _process_single_wagelist(self, driver, wait, wagelist, fin_year):
        """Processes a single wagelist (Background Safe)."""
        for attempt in range(2):
            if self.app.stop_events[self.automation_key].is_set(): return False
            try:
                # Select Wagelist (Presence check)
                wl_dropdown = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_sel")))
                Select(wl_dropdown).select_by_value(wagelist)
                
                wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_GridView1")))
                
                self.app.log_message(self.log_display, f"Selecting all EFMS options for {wagelist}...")
                
                # JS Script checks checkboxes (Already good in previous code, kept same)
                js_script = """
                    const radios = document.querySelectorAll("input[id$='_rdbPayment_2']");
                    let clickedCount = 0;
                    radios.forEach(radio => {
                        if (!radio.disabled && !radio.checked) {
                            radio.checked = true;
                            clickedCount++;
                        }
                    });
                    return clickedCount;
                """
                clicked_count = driver.execute_script(js_script)
                self.app.log_message(self.log_display, f"   - Instantly selected {clicked_count} EFMS options.")
                
                if self.app.stop_events[self.automation_key].is_set(): return False
                
                # --- FIX: JS Click for Submit Button (Background Safe) ---
                submit_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btnsubmit")
                driver.execute_script("arguments[0].click();", submit_btn)
                
                WebDriverWait(driver, 5).until(EC.alert_is_present()).accept()
                
                self.app.log_message(self.log_display, f"✅ {wagelist} submitted successfully.", "success")
                return True
            except Exception as e:
                self.app.log_message(self.log_display, f"[WARN] Attempt {attempt+1} failed for {wagelist}: {type(e).__name__}", "warning")
                if (attempt == 0):
                    driver.refresh()
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlfin")))
                    Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlfin")).select_by_value(fin_year)
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_sel")))

        self.app.log_message(self.log_display, f"❌ {wagelist} failed after multiple attempts.", "error")
        return False