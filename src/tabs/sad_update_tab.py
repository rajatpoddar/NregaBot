# tabs/sad_update_tab.py
import tkinter
from tkinter import messagebox, filedialog, ttk
import customtkinter as ctk
import json
import os, time, csv, re
import threading
from .base_tab import BaseAutomationTab
from src.utils import get_logger
from src.i18n import tr
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Keys, Select, WebDriverWait, EC, TimeoutException, openpyxl  # noqa: F401


logger = get_logger()

# --- NAME CHANGED HERE (SADUpdateStatusTab -> SadUpdateTab) ---
class SadUpdateTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="sad_update_status")
        self.config_file = self.app.get_data_path("sad_update_inputs.json")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) 
        
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.main_scroll.grid_columnconfigure(0, weight=1)

        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:

        # ── Header card ──
        # main_scroll children are pack-managed, so wrap the header (grid-based)
        # in a pack-managed container to avoid mixing geometry managers.
        header_wrap = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        header_wrap.pack(fill="x", padx=0, pady=0)
        self._create_header_card(header_wrap, "🔄", tr("tab.sad_update.title"), tr("tab.sad_update.subtitle"),
                                 icon_key="emoji_update_outcome")

        # Action Selection (inside a small bordered row)
        action_container = ctk.CTkFrame(self.main_scroll, corner_radius=10, border_width=1,
                                        border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        action_container.pack(fill="x", padx=12, pady=(0, 4))
        action_container.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(action_container, text=tr("form.sad.select_action"), font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        self.action_var = ctk.StringVar(value="Dispose")
        self.action_menu = ctk.CTkOptionMenu(action_container, variable=self.action_var, values=["Dispose", "Reject", "In Progress", "Pending"], width=200)
        self.action_menu.grid(row=0, column=1, padx=12, pady=8, sticky="ew")

        note_text = ("💡 Smart Mode: Automatically extracts '1905/375853' from full codes.\n"
                     "💡 If Dropdown is missing (Already Disposed), it skips immediately.")
        ctk.CTkLabel(self.main_scroll, text=note_text, text_color="gray60", 
                     font=("Arial", 11), justify="left").pack(anchor="w", padx=16, pady=(2, 4))

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
        
        ctk.CTkLabel(text_tab, text=tr("form.sad.ack_label")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ctk.CTkButton(text_tab, text=tr("common.clear"), width=60, height=20, 
                      command=lambda: self.manual_text_area.delete("1.0", "end")).grid(row=0, column=1, sticky="e", padx=5)
        
        self.manual_text_area = ctk.CTkTextbox(text_tab)
        self.manual_text_area.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        # TAB 2: Upload File
        file_tab = self.main_tabs.tab("Upload File")
        file_tab.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(file_tab, text=tr("form.sad.select_file")).grid(row=0, column=0, sticky="w", padx=10, pady=20)
        self.file_entry = ctk.CTkEntry(file_tab, placeholder_text=tr("form.sad.select_excel_csv"))
        self.file_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=20)
        ctk.CTkButton(file_tab, text=tr("common.browse"), width=80, command=self.browse_file).grid(row=0, column=2, padx=10, pady=20)
        
        ctk.CTkLabel(file_tab, text=tr("form.sad.bot_scan_hint"), 
                     text_color="gray50").grid(row=1, column=0, columnspan=3, sticky="w", padx=10)

        # TAB 3: Results (Treeview)
        result_tab = self.main_tabs.tab("Results")
        result_tab.grid_columnconfigure(0, weight=1)
        result_tab.grid_rowconfigure(0, weight=1)

        cols = ("Ack Number", "Status", "Message")
        self.results_tree = ttk.Treeview(result_tab, columns=cols, show='headings', height=15)
        
        self.results_tree.heading("Ack Number", text=tr("form.sad.col_ack"))
        self.results_tree.heading("Status", text=tr("form.sad.col_status"))
        self.results_tree.heading("Message", text=tr("form.sad.col_message"))
        
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
        self.results_tree.tag_configure('Skipped', foreground='#D35400') # Burnt Orange

        # TAB 4: Logs
        log_tab = self.main_tabs.tab("Logs")
        log_tab.grid_columnconfigure(0, weight=1)
        log_tab.grid_rowconfigure(1, weight=1)
        
        log_tools = ctk.CTkFrame(log_tab, fg_color="transparent")
        log_tools.grid(row=0, column=0, sticky="ew", pady=5)

        def clear_logs():
            self.log_display.configure(state="normal")
            self.log_display.delete("1.0", tkinter.END)
            self.log_display.configure(state="disabled")

        ctk.CTkButton(log_tools, text=tr("common.clear_logs"), width=110,
                       fg_color=("#DC2626", "#EF4444"), hover_color=("#B91C1C", "#DC2626"),
                       command=clear_logs).pack(side="right", padx=5)
        ctk.CTkButton(log_tools, text=tr("common.copy_logs"), width=110, command=self.copy_logs).pack(side="right", padx=5)
        
        self.log_display = ctk.CTkTextbox(log_tab, state="disabled", font=("Consolas", 12))
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
        self.log_info(message)
    def add_result(self, ack_no, status, message):
        # Map status to tags for coloring
        tag = status 
        if status not in ['Success', 'Skipped']: tag = 'Failed'
        self._tree_insert_top(self.results_tree, (ack_no, status, message), (tag,))

    def copy_logs(self):
        try:
            log_content = self.log_display.get("1.0", "end")
            self.app.clipboard_clear()
            self.app.clipboard_append(log_content)
            messagebox.showinfo(tr("status.copied"), tr("dialogs.logs_copied"))
        except Exception as e:
            messagebox.showerror(tr("dialogs.error"), tr("dialogs.failed_copy", error=e))
    def reset_ui(self) -> None:
        self.file_entry.delete(0, tkinter.END)
        self.manual_text_area.delete("1.0", tkinter.END)
        self.app.clear_log(self.log_display)
        self.safe_tree_clear()
        self.log("UI Reset.")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.file_entry.configure(state=state)
        self.manual_text_area.configure(state=state)
        self.action_menu.configure(state=state)

    def save_inputs(self, inputs):
        try:
            self.app.history_manager.save_tab_inputs_batch("sad_update", inputs)
        except Exception as e:
            logger.warning("Failed to save SAD inputs: %s", e)

    def load_inputs(self):
        data = self.app.history_manager.get_tab_inputs("sad_update")
        if data:
            self.file_entry.insert(0, data.get('csv_file', ''))

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
                    except Exception: continue

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
    def start_automation(self) -> None:
        active_tab = self.main_tabs.get()
        items_to_process = []

        if active_tab in ["Results", "Logs"]:
            raw_text = self.manual_text_area.get("1.0", "end").strip()
            if raw_text:
                active_tab = "Paste Text"
            elif self.file_entry.get().strip():
                active_tab = "Upload File"
            else:
                messagebox.showwarning(tr("errors.input_needed"), tr("dialogs.sad_provide_input"))
                return

        if active_tab == "Paste Text":
            raw_text = self.manual_text_area.get("1.0", "end").strip()
            if not raw_text:
                messagebox.showwarning(tr("errors.input_error"), tr("dialogs.text_area_empty"))
                return
            for line in raw_text.split('\n'):
                val = self._parse_smart_ack_no(line)
                if val: items_to_process.append(val)
                
        elif active_tab == "Upload File":
            file_path = self.file_entry.get().strip()
            if not file_path or not os.path.exists(file_path):
                messagebox.showerror(tr("dialogs.error"), tr("dialogs.invalid_file_path"))
                return
            self.save_inputs({'csv_file': file_path})
            self.log(f"Scanning file: {os.path.basename(file_path)}...")
            found_items, err = self._scan_file_for_ack_numbers(file_path)
            if err: messagebox.showerror(tr("dialogs.file_error"), err); return
            if not found_items: messagebox.showwarning(tr("errors.no_data"), tr("dialogs.no_patterns_found")); return
            items_to_process = found_items

        if not items_to_process:
             messagebox.showwarning(tr("errors.no_data"), tr("dialogs.no_valid_items"))
             return

        self.safe_tree_clear()

        self.main_tabs.set("Results")

        action_map = {"Pending": "0", "In Progress": "1", "Dispose": "2", "Reject": "3"}
        action_text = self.action_var.get()
        
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
            wait = WebDriverWait(driver, 20)
            
            for idx, search_term in enumerate(items):
                if self.is_stopped():
                    self.log("!!! Stopped !!!"); break

                status_msg = f"Processing {idx+1}/{total}: {search_term}"
                self.log(status_msg)
                self.app.after(0, self.app.set_status, status_msg)

                try:
                    target_url = "https://sarkaraapkedwar.jharkhand.gov.in/#/application/search"
                    
                    # Refresh page logic
                    try:
                        driver.get(target_url)
                        time.sleep(3.0) # Increased sleep for React render
                        
                        # --- CRITICAL FIX: WAIT FOR OVERLAYS TO DISAPPEAR ---
                        try:
                            # Wait for any sweet alert container to NOT be visible
                            wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.swal2-container")))
                            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "swal2-shown")))
                        except Exception as e:
                            logger.debug("Sweet alert overlay wait failed: %s", e)
                        
                    except Exception as e:
                        self.log(f"Navigation Error: {e}")
                        continue

                    # --- MULTI-STRATEGY LOCATOR ---
                    inp = None
                    # Strategy 1: By Name (Standard)
                    try:
                        inp = wait.until(EC.visibility_of_element_located((By.NAME, "accNo")))
                    except TimeoutException:
                        # Strategy 2: By Placeholder (Visual)
                        try:
                            inp = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Enter Acknowledgement No']")))
                        except TimeoutException:
                            # Strategy 3: By Label proximity (Structure)
                            try:
                                inp = wait.until(EC.visibility_of_element_located((By.XPATH, "//label[contains(., 'Acknowledgement')]/following::input[1]")))
                            except TimeoutException:
                                self.log(f"--> Input Box Not Found (Timeout)")
                                self.add_result(search_term, "Failed", "Input box not found")
                                continue

                    # Robust clearing for React inputs (Ctrl+A -> Backspace)
                    try:
                        inp.click()
                        time.sleep(0.2)
                        inp.send_keys(Keys.CONTROL + "a")
                        inp.send_keys(Keys.BACK_SPACE)
                        time.sleep(0.2)
                        
                        # Type and Search
                        inp.send_keys(search_term)
                        inp.send_keys(Keys.TAB)
                        time.sleep(0.5)

                        search_btn = driver.find_element(By.XPATH, "//button[contains(., 'Search Applicant')]")
                        driver.execute_script("arguments[0].click();", search_btn)
                    except Exception as e:
                         self.log(f"--> Typing Error: {e}")
                         self.add_result(search_term, "Failed", "Typing Error")
                         continue

                    
                    # --- FIND UPDATE BUTTON (ICON) ---
                    try:
                        edit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'update-status')]")))
                        edit_btn.click()
                    except TimeoutException:
                        try:
                            fallback_btn = driver.find_element(By.XPATH, "//a[contains(., 'Update')]")
                            driver.execute_script("arguments[0].click();", fallback_btn)
                        except Exception:
                            self.log("--> Record Not Found")
                            self.add_result(search_term, "Failed", "Record/Update Link not found")
                            continue
                    
                    # --- CHECK FOR DROPDOWN OR DISPOSED STATUS ---
                    try:
                        # --- NETWORK FIX: Increased timeout ---
                        short_wait = WebDriverWait(driver, 10.0)
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
                        # Dropdown NOT found -> Mark as Already Disposed
                        self.log("--> Already Disposed (No dropdown)")
                        self.add_result(search_term, "Skipped", "Already Disposed")
                        continue 

                    except Exception as e:
                        self.log(f"--> Error finding Select: {e}")
                        self.add_result(search_term, "Failed", "Dropdown error")
                        continue

                    time.sleep(1.0) 

                    if action_val == "2": 
                        try:
                            set_docs_btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Set Documents')]")))
                            driver.execute_script("arguments[0].click();", set_docs_btn)
                            time.sleep(0.5)
                        except Exception as e:
                            logger.debug("Set Documents button not found: %s", e)

                    try:
                        update_btn = driver.find_element(By.XPATH, "//button[contains(., 'Update Status')]")
                        
                        if update_btn.is_enabled():
                            driver.execute_script("arguments[0].scrollIntoView();", update_btn)
                            driver.execute_script("arguments[0].click();", update_btn)
                            
                            try:
                                ok_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.swal2-confirm")))
                                driver.execute_script("arguments[0].click();", ok_btn)
                                WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.swal2-container")))
                            except Exception as e:
                                logger.debug("Sweet alert confirm button click failed: %s", e)
                            
                            processed_success += 1
                            self.log("--> Success"); self.add_result(search_term, "Success", "Updated")
                        else:
                            self.log("--> Button Disabled"); self.add_result(search_term, "Failed", "Update Button Disabled")
                    except Exception as e:
                        self.log(f"--> Update Error: {e}")
                        self.add_result(search_term, "Failed", "Click Failed")

                except Exception as e:
                    self.log(f"--> Error: {e}"); self.add_result(search_term, "Failed", str(e))

            if not self.is_stopped():
                self.log("Batch Ended.")
                self.log(f"📊 SAD Update Complete: Success: {processed_success}/{total}")

        except Exception as e:
            self.log(f"Critical Error: {e}")
            err_text = str(e)  # AUDIT FIX: closure-safe capture
            self.app.after(0, lambda: messagebox.showerror(tr("dialogs.error"), err_text))
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")