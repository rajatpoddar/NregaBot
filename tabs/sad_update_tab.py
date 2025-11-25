# tabs/sad_update_tab.py
import tkinter
from tkinter import messagebox, filedialog, ttk
import customtkinter as ctk
import json
import os, time, csv, re
import threading
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from .base_tab import BaseAutomationTab

class SADUpdateStatusTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="sad_update_status")
        self.config_file = self.app.get_data_path("sad_update_inputs.json")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) 
        
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.main_scroll.grid_columnconfigure(0, weight=1)

        self._create_widgets()
        self.load_inputs()

    def _create_widgets(self):
        # --- Top Frame: Title & Action Selection ---
        top_frame = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top_frame, text="Sarkar Aapke Dwar - Update Status / Disposal", 
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")

        note_text = ("Smart Mode: Automatically extracts '1905/375853' from full codes.\n"
                     "If Dropdown is missing (Already Disposed), it skips immediately.")
        ctk.CTkLabel(top_frame, text=note_text, text_color="gray60", 
                     font=("Arial", 11), justify="left").pack(anchor="w", pady=(0, 5))

        # Action Selection
        action_container = ctk.CTkFrame(top_frame)
        action_container.pack(fill="x", pady=5)
        
        ctk.CTkLabel(action_container, text="Select Action:").pack(side="left", padx=10)
        self.action_combobox = ctk.CTkComboBox(action_container, values=["Dispose", "Reject", "In Progress", "Pending"], width=200)
        self.action_combobox.set("Dispose") 
        self.action_combobox.pack(side="left", padx=5)

        # --- Main TabView (Inputs + Results + Logs) ---
        self.main_tabs = ctk.CTkTabview(self.main_scroll, height=400)
        self.main_tabs.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.main_tabs.add("Paste Text")
        self.main_tabs.add("Upload File")
        self.main_tabs.add("Results")
        self.main_tabs.add("Logs")

        # TAB 1: Paste Text
        text_tab = self.main_tabs.tab("Paste Text")
        text_tab.grid_columnconfigure(0, weight=1)
        text_tab.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(text_tab, text="Enter Acknowledgement Numbers (One per line):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ctk.CTkButton(text_tab, text="Clear", width=60, height=20, 
                      command=lambda: self.manual_text_area.delete("1.0", "end")).grid(row=0, column=1, sticky="e", padx=5)
        
        self.manual_text_area = ctk.CTkTextbox(text_tab)
        self.manual_text_area.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        # TAB 2: Upload File
        file_tab = self.main_tabs.tab("Upload File")
        file_tab.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(file_tab, text="Select Excel/CSV File:").grid(row=0, column=0, sticky="w", padx=10, pady=20)
        self.file_entry = ctk.CTkEntry(file_tab, placeholder_text="Select .xlsx or .csv file")
        self.file_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=20)
        ctk.CTkButton(file_tab, text="Browse", width=80, command=self.browse_file).grid(row=0, column=2, padx=10, pady=20)
        
        ctk.CTkLabel(file_tab, text="ℹ️ Bot will scan all columns for pattern X/Y/Z/A automatically.", 
                     text_color="gray50").grid(row=1, column=0, columnspan=3, sticky="w", padx=10)

        # TAB 3: Results (Treeview)
        result_tab = self.main_tabs.tab("Results")
        result_tab.grid_columnconfigure(0, weight=1)
        result_tab.grid_rowconfigure(0, weight=1)

        cols = ("Ack Number", "Status", "Message")
        self.results_tree = ttk.Treeview(result_tab, columns=cols, show='headings', height=15)
        
        self.results_tree.heading("Ack Number", text="Ack Number")
        self.results_tree.heading("Status", text="Status")
        self.results_tree.heading("Message", text="Message")
        
        self.results_tree.column("Ack Number", width=150, anchor="w")
        self.results_tree.column("Status", width=100, anchor="center")
        self.results_tree.column("Message", width=300, anchor="w")
        
        self.results_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Scrollbar for Treeview
        vsb = ctk.CTkScrollbar(result_tab, orientation="vertical", command=self.results_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=vsb.set)
        
        # Style the treeview
        self.style_treeview(self.results_tree)
        self.results_tree.tag_configure('Success', foreground='green')
        self.results_tree.tag_configure('Failed', foreground='red')
        # --- ADDED: Yellow/Orange color for Skipped/Already Disposed ---
        self.results_tree.tag_configure('Skipped', foreground='#D35400') # Burnt Orange

        # TAB 4: Logs
        log_tab = self.main_tabs.tab("Logs")
        log_tab.grid_columnconfigure(0, weight=1)
        log_tab.grid_rowconfigure(1, weight=1)
        
        log_tools = ctk.CTkFrame(log_tab, fg_color="transparent")
        log_tools.grid(row=0, column=0, sticky="ew", pady=5)
        ctk.CTkButton(log_tools, text="Copy Logs", width=100, command=self.copy_logs).pack(side="right", padx=5)
        
        self.log_display = ctk.CTkTextbox(log_tab, state="disabled")
        self.log_display.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # --- Control Buttons (Bottom) ---
        btn_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        btn_container.pack(fill="x", pady=10)
        
        action_btn_frame = self._create_action_buttons(btn_container)
        action_btn_frame.pack(anchor="center")

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Data Files", "*.xlsx *.csv")])
        if file_path:
            self.file_entry.delete(0, tkinter.END)
            self.file_entry.insert(0, file_path)

    def log(self, message):
        self.app.log_message(self.log_display, message)

    def add_result(self, ack_no, status, message):
        # Map status to tags for coloring
        tag = status 
        if status not in ['Success', 'Skipped']: tag = 'Failed'
        self.results_tree.insert("", "0", values=(ack_no, status, message), tags=(tag,))

    def copy_logs(self):
        try:
            log_content = self.log_display.get("1.0", "end")
            self.app.clipboard_clear()
            self.app.clipboard_append(log_content)
            messagebox.showinfo("Copied", "Logs copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy: {e}")

    def reset_ui(self):
        self.file_entry.delete(0, tkinter.END)
        self.manual_text_area.delete("1.0", tkinter.END)
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.log("UI Reset.")

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.file_entry.configure(state=state)
        self.manual_text_area.configure(state=state)
        self.action_combobox.configure(state=state)

    def save_inputs(self, inputs):
        try:
            with open(self.config_file, 'w') as f: json.dump(inputs, f, indent=4)
        except: pass

    def load_inputs(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.file_entry.insert(0, data.get('csv_file', ''))
        except: pass

    # --- Parsing Logic ---
    def _parse_smart_ack_no(self, raw_text):
        if not raw_text: return None
        clean_text = str(raw_text).strip()
        parts = re.split(r'[/\\]', clean_text)
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return None

    def _scan_file_for_ack_numbers(self, file_path):
        ack_list = []
        file_ext = os.path.splitext(file_path)[1].lower()
        pattern = re.compile(r'\d+/\d+/\d+/\d+')
        
        try:
            rows_to_scan = []
            if file_ext == '.xlsx':
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True): rows_to_scan.append(row)
            else:
                encodings = ['utf-8-sig', 'cp1252', 'latin1']
                for enc in encodings:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            reader = csv.reader(f)
                            rows_to_scan = list(reader)
                        break
                    except: continue

            for row in rows_to_scan:
                if not row: continue
                for cell in row:
                    cell_str = str(cell).strip()
                    if pattern.search(cell_str):
                        match = pattern.search(cell_str).group(0)
                        smart_val = self._parse_smart_ack_no(match)
                        if smart_val: ack_list.append(smart_val)
            return list(dict.fromkeys(ack_list)), None
        except Exception as e:
            return [], f"File Scan Error: {str(e)}"

    def start_automation(self):
        active_tab = self.main_tabs.get()
        items_to_process = []

        if active_tab in ["Results", "Logs"]:
            raw_text = self.manual_text_area.get("1.0", "end").strip()
            if raw_text:
                active_tab = "Paste Text"
            elif self.file_entry.get().strip():
                active_tab = "Upload File"
            else:
                messagebox.showwarning("Input Needed", "Please go to 'Paste Text' or 'Upload File' tab and provide input.")
                return

        if active_tab == "Paste Text":
            raw_text = self.manual_text_area.get("1.0", "end").strip()
            if not raw_text:
                messagebox.showwarning("Input Error", "Text area is empty.")
                return
            for line in raw_text.split('\n'):
                val = self._parse_smart_ack_no(line)
                if val: items_to_process.append(val)
                
        elif active_tab == "Upload File":
            file_path = self.file_entry.get().strip()
            if not file_path or not os.path.exists(file_path):
                messagebox.showerror("Error", "Invalid file path.")
                return
            self.save_inputs({'csv_file': file_path})
            self.log(f"Scanning file: {os.path.basename(file_path)}...")
            found_items, err = self._scan_file_for_ack_numbers(file_path)
            if err: messagebox.showerror("File Error", err); return
            if not found_items: messagebox.showwarning("No Data", "No valid patterns found in file."); return
            items_to_process = found_items

        if not items_to_process:
             messagebox.showwarning("No Data", "No valid items found to process.")
             return

        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        self.main_tabs.set("Results")

        action_map = {"Pending": "0", "In Progress": "1", "Dispose": "2", "Reject": "3"}
        action_text = self.action_combobox.get()
        
        inputs = {
            'items': items_to_process,
            'action_val': action_map.get(action_text, "2"), 
            'action_text': action_text
        }
        
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        items = inputs['items']
        action_val = inputs['action_val']
        total = len(items)

        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.log(f"Starting Batch. Total Items: {total}")
        
        try:
            driver = self.app.get_driver()
            if not driver: return

            processed_success = 0
            
            for idx, search_term in enumerate(items):
                if self.app.stop_events[self.automation_key].is_set():
                    self.log("!!! Stopped !!!"); break

                status_msg = f"Processing {idx+1}/{total}: {search_term}"
                self.log(status_msg)
                self.app.after(0, self.app.set_status, status_msg)

                try:
                    driver.get("https://sarkaraapkedwar.jharkhand.gov.in/#/application/search")
                    wait = WebDriverWait(driver, 5)

                    inp = wait.until(EC.presence_of_element_located((By.NAME, "accNo")))
                    inp.clear(); inp.send_keys(search_term)
                    
                    # Tab out & Sleep
                    inp.send_keys(Keys.TAB)
                    time.sleep(0.5)

                    search_btn = driver.find_element(By.XPATH, "//button[contains(., 'Search Applicant')]")
                    driver.execute_script("arguments[0].click();", search_btn)
                    
                    # --- FIND UPDATE BUTTON (ICON) ---
                    try:
                        edit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'update-status')]")))
                        edit_btn.click()
                    except TimeoutException:
                        try:
                            fallback_btn = driver.find_element(By.XPATH, "//a[contains(., 'Update')]")
                            driver.execute_script("arguments[0].click();", fallback_btn)
                        except:
                            self.log("--> Not Found")
                            self.add_result(search_term, "Failed", "Record/Update Link not found")
                            continue
                    
                    # --- CHECK FOR DROPDOWN OR DISPOSED STATUS ---
                    try:
                        # --- FAST SKIP LOGIC ---
                        # Wait ONLY 2 seconds for dropdown. If not found, assume already disposed.
                        short_wait = WebDriverWait(driver, 0.5)
                        select_elem = short_wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
                        
                        # Dropdown found -> Select value
                        select_obj = Select(select_elem)
                        
                        option_found = False
                        for opt in select_obj.options:
                            if opt.get_attribute("value") == action_val:
                                option_found = True; break
                        
                        if option_found:
                            select_obj.select_by_value(action_val)
                        else:
                            self.log(f"--> Action Unavailable (Val: {action_val})")
                            self.add_result(search_term, "Skipped", "Option missing")
                            continue

                    except TimeoutException:
                        # Dropdown NOT found within 2 seconds -> Mark as Already Disposed
                        self.log("--> Already Disposed (No dropdown)")
                        self.add_result(search_term, "Skipped", "Already Disposed")
                        continue # Skip to next item immediately

                    except Exception as e:
                        self.log(f"--> Error finding Select: {e}")
                        self.add_result(search_term, "Failed", "Dropdown error")
                        continue

                    time.sleep(0.5)

                    if action_val == "2": 
                        try:
                            set_docs_btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Set Documents')]")))
                            driver.execute_script("arguments[0].click();", set_docs_btn)
                            time.sleep(0.5)
                        except: pass

                    try:
                        update_btn = driver.find_element(By.XPATH, "//button[contains(., 'Update Status')]")
                        
                        if update_btn.is_enabled():
                            driver.execute_script("arguments[0].scrollIntoView();", update_btn)
                            driver.execute_script("arguments[0].click();", update_btn)
                            
                            try:
                                ok_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.swal2-confirm")))
                                driver.execute_script("arguments[0].click();", ok_btn)
                                WebDriverWait(driver, 3).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.swal2-container")))
                            except: pass
                            
                            processed_success += 1
                            self.log("--> Success"); self.add_result(search_term, "Success", "Updated")
                        else:
                            self.log("--> Button Disabled"); self.add_result(search_term, "Failed", "Update Button Disabled")
                    except Exception as e:
                        self.log(f"--> Update Error: {e}")
                        self.add_result(search_term, "Failed", "Click Failed")

                except Exception as e:
                    self.log(f"--> Error: {e}"); self.add_result(search_term, "Failed", str(e))

            if not self.app.stop_events[self.automation_key].is_set():
                self.log("Batch Ended.")
                self.app.after(0, lambda: messagebox.showinfo("Completed", f"Success: {processed_success}/{total}"))

        except Exception as e:
            self.log(f"Critical Error: {e}")
            self.app.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")