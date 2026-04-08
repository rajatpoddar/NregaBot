# tabs/jobcard_verify_tab.py
import tkinter
from tkinter import messagebox, filedialog
import customtkinter as ctk
import time, os, sys, json
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class JobcardVerifyTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="jc_verify")
        self.photo_folder_path = ""
        self.pref_file = os.path.join(os.path.abspath("."), "jc_verify_prefs.json") 
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        self._create_widgets()
        self._load_saved_preferences()

    def _create_widgets(self):
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(controls_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=15, pady=10)
        self.panchayat_entry = AutocompleteEntry(controls_frame, suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"))
        self.panchayat_entry.grid(row=0, column=1, sticky='ew', padx=15, pady=10)
        
        ctk.CTkLabel(controls_frame, text="Village Name:").grid(row=1, column=0, sticky='w', padx=15, pady=10)
        self.village_entry = AutocompleteEntry(controls_frame, suggestions_list=self.app.history_manager.get_suggestions("village_name"))
        self.village_entry.grid(row=1, column=1, sticky='ew', padx=15, pady=10)

        # Checkbox Frame
        chk_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        chk_frame.grid(row=2, column=1, sticky='w', padx=15, pady=(0, 10))

        self.process_all_villages_var = tkinter.BooleanVar()
        self.process_all_checkbox = ctk.CTkCheckBox(
            chk_frame,
            text="Process all villages in this Panchayat",
            variable=self.process_all_villages_var,
            command=self._toggle_village_entry
        )
        self.process_all_checkbox.grid(row=0, column=0, sticky='w', padx=(0, 15))

        self.verify_account_only_var = tkinter.BooleanVar()
        self.verify_account_only_chk = ctk.CTkCheckBox(
            chk_frame,
            text="Verify only with Account Number",
            variable=self.verify_account_only_var
        )
        self.verify_account_only_chk.grid(row=0, column=1, sticky='w')

        photo_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        photo_frame.grid(row=3, column=0, columnspan=2, sticky='ew', padx=15, pady=10)
        photo_frame.grid_columnconfigure(1, weight=1)
        
        self.select_folder_button = ctk.CTkButton(photo_frame, text="Select Photo Folder...", command=self.select_photo_folder)
        self.select_folder_button.grid(row=0, column=0, sticky='w')
        self.photo_path_label = ctk.CTkLabel(photo_frame, text=f"No folder selected (will use default '{config.JOBCARD_VERIFY_CONFIG['default_photo']}')", text_color="gray", anchor='w')
        self.photo_path_label.grid(row=0, column=1, sticky='ew', padx=10)
        
        instruction_text = "Note: Name photos with the last part of the Jobcard No. (e.g., 417.jpg for ...01/417)"
        ctk.CTkLabel(photo_frame, text=instruction_text, text_color="gray50").grid(row=1, column=0, columnspan=2, sticky='w', pady=2)

        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=4, column=0, columnspan=2, sticky='ew', pady=15)

        notebook = ctk.CTkTabview(self)
        notebook.grid(row=1, column=0, sticky="nsew")
        self._create_log_and_status_area(parent_notebook=notebook)
        self.progress_bar.grid_forget()

    def _toggle_village_entry(self):
        if self.process_all_villages_var.get():
            self.village_entry.configure(state="disabled")
        else:
            self.village_entry.configure(state="normal")

    def _load_saved_preferences(self):
        try:
            if os.path.exists(self.pref_file):
                with open(self.pref_file, 'r') as f:
                    data = json.load(f)
                    if "panchayat" in data: self.panchayat_entry.insert(0, data["panchayat"])
                    if "village" in data: self.village_entry.insert(0, data["village"])
                    if "folder" in data and os.path.exists(data["folder"]):
                        self.photo_folder_path = data["folder"]
                        self.photo_path_label.configure(text=self.photo_folder_path)
        except Exception as e:
            print(f"Error loading prefs: {e}")

    def _save_preferences(self, panchayat, village):
        try:
            data = {"panchayat": panchayat, "village": village, "folder": self.photo_folder_path}
            with open(self.pref_file, 'w') as f:
                json.dump(data, f)
        except Exception: pass

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.select_folder_button.configure(state=state)
        self.process_all_checkbox.configure(state=state)
        self.verify_account_only_chk.configure(state=state)
        if running or self.process_all_villages_var.get():
            self.village_entry.configure(state="disabled")
        else:
            self.village_entry.configure(state="normal")

    def select_photo_folder(self):
        path = filedialog.askdirectory(title="Select Folder Containing Photos")
        if path:
            self.photo_folder_path = path
            self.photo_path_label.configure(text=self.photo_folder_path)
            self.app.log_message(self.log_display, f"Selected photo folder: {self.photo_folder_path}")

    def reset_ui(self):
        if messagebox.askokcancel("Reset Form?", "Are you sure?"):
            self.panchayat_entry.delete(0, tkinter.END)
            self.village_entry.delete(0, tkinter.END)
            self.process_all_villages_var.set(False)
            self.verify_account_only_var.set(False)
            self._toggle_village_entry()
            self.photo_folder_path = ""
            self.photo_path_label.configure(text=f"No folder selected (will use default '{config.JOBCARD_VERIFY_CONFIG['default_photo']}')")
            self.app.clear_log(self.log_display)
            self.update_status("Ready")
            self.app.after(0, self.app.set_status, "Ready")

    def start_automation(self):
        panchayat = self.panchayat_entry.get().strip()
        village = self.village_entry.get().strip()
        process_all = self.process_all_villages_var.get()
        verify_account_only = self.verify_account_only_var.get()

        if not panchayat:
            messagebox.showwarning("Input Required", "Panchayat name is required.")
            return
        if not process_all and not village:
            messagebox.showwarning("Input Required", "Please enter a Village name or check 'Process all villages'.")
            return
            
        inputs = {
            'panchayat': panchayat, 
            'village': village, 
            'process_all': process_all,
            'verify_account_only': verify_account_only
        }
        self._save_preferences(panchayat, village)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def _get_photo_for_jobcard(self, jobcard_no):
        try:
            jobcard_key = jobcard_no.split('/')[-1]
            if self.photo_folder_path:
                for ext in ['.jpg', '.jpeg', '.png']:
                    photo_path = os.path.join(self.photo_folder_path, jobcard_key + ext)
                    if os.path.exists(photo_path):
                        self.app.log_message(self.log_display, f"Found photo: {os.path.basename(photo_path)}"); return photo_path
            
            default_photo_path = resource_path(config.JOBCARD_VERIFY_CONFIG["default_photo"])
            if os.path.exists(default_photo_path):
                self.app.log_message(self.log_display, f"Using default photo '{config.JOBCARD_VERIFY_CONFIG['default_photo']}'.", "warning"); return default_photo_path
            
            self.app.log_message(self.log_display, f"No photo found for {jobcard_key}.", "error"); return None
        except Exception as e:
            self.app.log_message(self.log_display, f"Error finding photo for {jobcard_no}: {e}", "error"); return None

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.app.log_message(self.log_display, "🚀 Starting Jobcard Verification...")
        self.app.after(0, self.app.set_status, "Running Jobcard Verification...")
        
        try:
            driver = self.app.get_driver()
            if not driver: return
            wait = WebDriverWait(driver, 20)
            url = config.JOBCARD_VERIFY_CONFIG["url"]
            driver.get(url)
            
            villages_to_process = []
            self.app.log_message(self.log_display, f"Selecting Panchayat: {inputs['panchayat']}")
            html_element = driver.find_element(By.TAG_NAME, "html")
            Select(wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlpnch")))).select_by_visible_text(inputs['panchayat'])
            wait.until(EC.staleness_of(html_element))

            if inputs['process_all']:
                self.app.log_message(self.log_display, "Finding all villages in Panchayat...")
                village_dropdown = Select(wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlVillage"))))
                villages_to_process = [opt.text for opt in village_dropdown.options if "--Select" not in opt.text]
                self.app.log_message(self.log_display, f"Found {len(villages_to_process)} villages.")
            else:
                villages_to_process.append(inputs['village'])

            self.app.update_history("panchayat_name", inputs['panchayat'])

            for village_name in villages_to_process:
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "🛑 Stop signal received.", "warning"); break
                
                self.app.log_message(self.log_display, f"\n--- Processing Village: {village_name} ---")
                self.app.after(0, self.update_status, f"Processing Village: {village_name}")
                self.app.update_history("village_name", village_name)
                
                html_element = driver.find_element(By.TAG_NAME, "html")
                Select(wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlVillage")))).select_by_visible_text(village_name)
                wait.until(EC.staleness_of(html_element))
                
                try:
                    driver.implicitly_wait(1)
                    msg_element = driver.find_elements(By.ID, "ctl00_ContentPlaceHolder1_lblmsg")
                    if msg_element and msg_element[0].is_displayed() and "no record found" in msg_element[0].text.lower():
                        self.app.log_message(self.log_display, f"   - Village has no records. Skipping.", "info")
                        continue
                finally:
                    driver.implicitly_wait(20)

                # --- PAGINATION LOOP ---
                page_count = 1
                while not self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, f"   > Processing Page {page_count}")
                    
                    self._process_jobcards_for_current_page(driver, wait, inputs['verify_account_only'])
                    
                    # Pass the current page number so we know what to look for (Next = page_count + 1)
                    if not self._handle_pagination(driver, wait, page_count):
                        self.app.log_message(self.log_display, "   - End of pages for this village.", "info")
                        break 
                    
                    page_count += 1
                    time.sleep(2)

            if not self.app.stop_events[self.automation_key].is_set():
                messagebox.showinfo("Success", "Jobcard verification complete for all selected villages.")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e).splitlines()[0]}"; self.app.log_message(self.log_display, f"Error: {error_msg}", "error"); messagebox.showerror("Automation Error", f"An error occurred: {error_msg}")
        finally:
            self.app.after(0, self.update_status, "Finished"); self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")
    
    def _process_jobcards_for_current_page(self, driver, wait, verify_account_only):
        row_index = 2 
        while not self.app.stop_events[self.automation_key].is_set():
            row_id_base = f"ctl00_ContentPlaceHolder1_grdData_ctl{row_index:02d}"
            
            # FAST FAIL: Check if row exists without waiting 20s
            driver.implicitly_wait(0) 
            row_check = driver.find_elements(By.ID, f"{row_id_base}_hidd_reg")
            driver.implicitly_wait(20) 
            
            if not row_check:
                break # End of this page
            
            jobcard_no = row_check[0].get_attribute("value")
            
            should_skip = False
            if verify_account_only:
                try:
                    ac_element = driver.find_elements(By.ID, f"{row_id_base}_lblAc")
                    if not ac_element or not ac_element[0].text.strip():
                        self.app.log_message(self.log_display, f"   - Skipping Jobcard {jobcard_no} (No Account Number)", "info")
                        should_skip = True
                except Exception: should_skip = True

            if should_skip:
                row_index += 1
                continue

            self.app.log_message(self.log_display, f"   - Verifying Jobcard: {jobcard_no}")
            photo_to_upload = self._get_photo_for_jobcard(jobcard_no)
            
            upload_link = None
            try:
                links = driver.find_elements(By.ID, f"{row_id_base}_link_img_F")
                if not links: links = driver.find_elements(By.ID, f"{row_id_base}_link_img_W")
                if links: upload_link = links[0]
            except: pass

            if upload_link and photo_to_upload:
                try:
                    main_handle = driver.current_window_handle
                    driver.execute_script("arguments[0].click();", upload_link)
                    wait.until(EC.number_of_windows_to_be(2))
                    popup = [h for h in driver.window_handles if h != main_handle][0]
                    driver.switch_to.window(popup)
                    WebDriverWait(driver, 5).until(lambda d: "UploadPhoto" in d.current_url)
                    
                    file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                    file_input.send_keys(photo_to_upload)
                    driver.find_element(By.CSS_SELECTOR, 'input[type="submit"]').click()
                    wait.until(EC.alert_is_present()).accept()
                    self.app.log_message(self.log_display, "     - Photo uploaded successfully.", "success")
                except Exception as ex:
                     self.app.log_message(self.log_display, f"     - Upload failed: {str(ex)}", "error")
                finally:
                    if len(driver.window_handles) > 1: driver.close()
                    driver.switch_to.window(main_handle)
            
            try:
                rblDmd = wait.until(EC.presence_of_element_located((By.ID, f"{row_id_base}_rblDmd_0")))
                driver.execute_script("arguments[0].click();", rblDmd)
                
                html_element = driver.find_element(By.TAG_NAME, "html")
                rblJCVer = wait.until(EC.presence_of_element_located((By.ID, f"{row_id_base}_rblJCVer_0")))
                driver.execute_script("arguments[0].click();", rblJCVer)
                wait.until(EC.staleness_of(html_element))
                
                date_input = wait.until(EC.presence_of_element_located((By.ID, f"{row_id_base}_txt_DtrblJCVer")))
                driver.execute_script("arguments[0].value = arguments[1];", date_input, datetime.now().strftime("%d/%m/%Y"))
                
                update_btn = driver.find_element(By.ID, f"{row_id_base}_BtnUpdate")
                driver.execute_script("arguments[0].click();", update_btn)
                
                final_alert = wait.until(EC.alert_is_present())
                self.app.log_message(self.log_display, f"     - Saved: {final_alert.text}", "success")
                final_alert.accept()
                
                time.sleep(1)
                wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlpnch")))
                row_index = 2
            except Exception as e:
                self.app.log_message(self.log_display, f"     - Error saving row: {e}", "error")
                row_index += 1

    def _handle_pagination(self, driver, wait, current_page_num):
        """Attempts to find and click the next page button using Link Text (Numbers) or '...'"""
        try:
            # IMPORTANT: Disable implicit wait for this check so we don't wait 20s if page not found
            driver.implicitly_wait(0)
            
            next_page_str = str(current_page_num + 1)
            
            # 1. Try finding exact number "2", "3", "4"
            # Since the user HTML showed <a ...>2</a>, Link Text is the most reliable way.
            next_btn = driver.find_elements(By.LINK_TEXT, next_page_str)
            
            # 2. If not found, check for "..." (Next block of pages) or "Next"
            if not next_btn:
                # We prioritize the LAST "..." because sometimes there is one at the start for 'previous'
                candidates = driver.find_elements(By.XPATH, "//a[text()='...' or text()='Next' or text()='>>']")
                if candidates:
                    next_btn = [candidates[-1]]

            if next_btn:
                self.app.log_message(self.log_display, f"   - Switching to Page {next_page_str}...", "info")
                html_element = driver.find_element(By.TAG_NAME, "html")
                driver.execute_script("arguments[0].click();", next_btn[0])
                wait.until(EC.staleness_of(html_element))
                return True
            
            return False # No more pages found

        except Exception as e:
            self.app.log_message(self.log_display, f"   - Pagination check failed: {e}", "warning")
            return False
        finally:
            # ALWAYS restore standard wait time
            driver.implicitly_wait(20)