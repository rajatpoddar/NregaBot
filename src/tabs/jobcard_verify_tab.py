# tabs/jobcard_verify_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, os, sys, json
from datetime import datetime
from src import config
from .base_tab import BaseAutomationTab

from src.utils import get_logger
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC  # noqa: F401


logger = get_logger()

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class JobcardVerifyTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="jc_verify")
        self.photo_folder_path = ""
        self.pref_file = os.path.join(os.path.abspath("."), "jc_verify_prefs.json") 
        # Result tracking (WhatsApp summary + Excel report ke liye)
        self._jc_success = 0
        self._jc_failed = 0
        self._jc_skipped = 0
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(3, weight=1)
        self._create_widgets()
        self._load_saved_preferences()
    def _create_widgets(self) -> None:

        # ── Header card ──
        self._create_header_card(self, "🪪", "Verify Jobcard",
                                 "Verify jobcards with photo upload and account-number checks in bulk.",
                                 icon_key="emoji_verify_jobcard")

        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        controls_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(controls_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=15, pady=10)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=config.ALL_PANCHAYATS_LABEL)
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var,
                                                values=self._all_panchayat_values(p_vals))
        self.panchayat_menu.grid(row=0, column=1, sticky='ew', padx=15, pady=10)
        ctk.CTkLabel(controls_frame, text="💡 Select '🌐 All Panchayats' to verify jobcards in every panchayat of the block.",
                     text_color="gray50", font=ctk.CTkFont(size=11)).grid(row=4, column=0, columnspan=2, sticky='w', padx=15, pady=(0, 10))
        
        ctk.CTkLabel(controls_frame, text="Village Name:").grid(row=1, column=0, sticky='w', padx=15, pady=10)
        v_vals = self.app.history_manager.get_suggestions("location_village") or [""]
        self.village_var = ctk.StringVar()
        self.village_menu = ctk.CTkOptionMenu(controls_frame, variable=self.village_var, values=v_vals)
        self.village_menu.grid(row=1, column=1, sticky='ew', padx=15, pady=10)

        # Filter villages when panchayat changes
        def _on_panchayat_change(*_):
            pan = self.panchayat_var.get()
            if pan:
                vals = self.app.history_manager.get_filtered_suggestions("location_village", "location_panchayat", pan) or [""]
            else:
                vals = self.app.history_manager.get_suggestions("location_village") or [""]
            self.village_var.set("")
            self.village_menu.configure(values=vals)
        self.panchayat_var.trace_add("write", _on_panchayat_change)

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
        
        instruction_text = "💡 Note: Name photos with the last part of the Jobcard No. (e.g., 417.jpg for ...01/417)"
        ctk.CTkLabel(photo_frame, text=instruction_text, text_color="gray50").grid(row=1, column=0, columnspan=2, sticky='w', pady=2)

        # ── Action buttons (OUTSIDE the card) ──
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew")
        self._create_log_and_status_area(parent_notebook=notebook)
        self.progress_bar.grid_forget()

        # ── Results Tab (results_tree → WhatsApp summary + Excel report) ──
        results_tab = notebook.add("Results")
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(0, weight=1)
        self.results_tree = ttk.Treeview(
            results_tab, columns=("timestamp", "panchayat", "village", "jobcard", "status", "details"),
            show="headings")
        for col, text, width, anchor in [
            ("timestamp", "Time", 70, "center"),
            ("panchayat", "Panchayat", 110, "w"),
            ("village", "Village", 110, "w"),
            ("jobcard", "Jobcard No", 150, "w"),
            ("status", "Status", 100, "center"),
            ("details", "Details", 260, "w"),
        ]:
            self.results_tree.heading(col, text=text)
            self.results_tree.column(col, width=width, anchor=anchor)
        self.style_treeview(self.results_tree)
        rsb = ttk.Scrollbar(results_tab, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=rsb.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        rsb.grid(row=0, column=1, sticky="ns")

    def _toggle_village_entry(self):
        if self.process_all_villages_var.get():
            self.village_menu.configure(state="disabled")
        else:
            self.village_menu.configure(state="normal")

    def _load_saved_preferences(self):
        try:
            if os.path.exists(self.pref_file):
                with open(self.pref_file, 'r') as f:
                    data = json.load(f)
                    if "panchayat" in data: self.panchayat_var.set(data["panchayat"])
                    if "village" in data: self.village_var.set(data["village"])
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
        except Exception as e: logger.debug("JobcardVerify: Could not save preferences: %s", e)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.select_folder_button.configure(state=state)
        self.process_all_checkbox.configure(state=state)
        self.verify_account_only_chk.configure(state=state)
        if running or self.process_all_villages_var.get():
            self.village_menu.configure(state="disabled")
        else:
            self.village_menu.configure(state="normal")

    def select_photo_folder(self):
        path = filedialog.askdirectory(title="Select Folder Containing Photos")
        if path:
            self.photo_folder_path = path
            self.photo_path_label.configure(text=self.photo_folder_path)
            self.log_info(f"Selected photo folder: {self.photo_folder_path}")
    def reset_ui(self) -> None:
        if messagebox.askokcancel("Reset Form?", "Are you sure?"):
            self.panchayat_var.set("")
            self.village_var.set("")
            self.process_all_villages_var.set(False)
            self.verify_account_only_var.set(False)
            self._toggle_village_entry()
            self.photo_folder_path = ""
            self.photo_path_label.configure(text=f"No folder selected (will use default '{config.JOBCARD_VERIFY_CONFIG['default_photo']}')")
            self.app.clear_log(self.log_display)
            self.update_status("Ready")
            self.app.after(0, self.app.set_status, "Ready")
    def start_automation(self) -> None:
        panchayat = self.panchayat_var.get().strip()
        village = self.village_var.get().strip()
        process_all = self.process_all_villages_var.get()
        verify_account_only = self.verify_account_only_var.get()

        all_panchayats = panchayat == config.ALL_PANCHAYATS_LABEL

        if not panchayat:
            messagebox.showwarning("Input Required", "Panchayat name is required.")
            return
        if not all_panchayats and not process_all and not village:
            messagebox.showwarning("Input Required", "Please enter a Village name or check 'Process all villages'.")
            return
        if all_panchayats:
            # Each panchayat's villages are processed automatically
            process_all = True
            village = ""
            
        inputs = {
            'panchayat': panchayat, 
            'village': village, 
            'process_all': process_all,
            'verify_account_only': verify_account_only,
            'all_panchayats': all_panchayats
        }
        if not all_panchayats:
            self._save_preferences(panchayat, village)
        # Fresh run: reset result counters + clear previous results tree
        self._jc_success = 0
        self._jc_failed = 0
        self._jc_skipped = 0
        try:
            for i in self.results_tree.get_children():
                self.results_tree.delete(i)
        except Exception:
            pass
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def _get_photo_for_jobcard(self, jobcard_no):
        try:
            jobcard_key = jobcard_no.split('/')[-1]
            if self.photo_folder_path:
                for ext in ['.jpg', '.jpeg', '.png']:
                    photo_path = os.path.join(self.photo_folder_path, jobcard_key + ext)
                    if os.path.exists(photo_path):
                        self.log_info(f"Found photo: {os.path.basename(photo_path)}"); return photo_path
            
            default_photo_path = resource_path(config.JOBCARD_VERIFY_CONFIG["default_photo"])
            if os.path.exists(default_photo_path):
                self.log_warning(f"Using default photo '{config.JOBCARD_VERIFY_CONFIG['default_photo']}'."); return default_photo_path
            
            self.log_error(f"No photo found for {jobcard_key}."); return None
        except Exception as e:
            self.log_error(f"Error finding photo for {jobcard_no}: {e}"); return None

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.log_info("🚀 Starting Jobcard Verification...")
        self.app.after(0, self.app.set_status, "Running Jobcard Verification...")
        
        try:
            driver = self.app.get_driver()
            if not driver: return
            wait = WebDriverWait(driver, 20)
            url = config.JOBCARD_VERIFY_CONFIG["url"]
            driver.get(url)
            
            all_mode = inputs.get('all_panchayats', False) or inputs['panchayat'] == config.ALL_PANCHAYATS_LABEL
            panchayats_to_process = []
            if all_mode:
                panch_dd = Select(wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlpnch"))))
                panchayats_to_process = [t for t in self._get_select_option_texts(panch_dd) if "--Select" not in t]
                self.log_info(f"🌐 All Panchayats mode: found {len(panchayats_to_process)} panchayats.")
            else:
                panchayats_to_process = [inputs['panchayat']]

            total_p = len(panchayats_to_process)
            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped():
                    self.log_warning("🛑 Stop signal received.")
                    break
                self.log_info(f"\n===== Panchayat {p_idx+1}/{total_p}: {p_name} =====")
                self.app.after(0, self.update_status, f"{p_name}: selecting...", p_idx / max(total_p, 1))
                inputs['panchayat'] = p_name

                html_element = driver.find_element(By.TAG_NAME, "html")
                selected = self.select_dropdown(html_element, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlpnch", p_name)
                if selected is None:
                    self.log_warning(f"   Panchayat '{p_name}' not found on the website. Skipping.")
                    continue
                wait.until(EC.staleness_of(html_element))

                villages_to_process = []
                if inputs['process_all']:
                    self.log_info("Finding all villages in Panchayat...")
                    village_dropdown = Select(wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlVillage"))))
                    villages_to_process = [opt.text for opt in village_dropdown.options if "--Select" not in opt.text]
                    self.log_info(f"Found {len(villages_to_process)} villages.")
                else:
                    villages_to_process.append(inputs['village'])

                self.app.update_history("location_panchayat", p_name)

                for location_village in villages_to_process:
                    if self.is_stopped():
                        self.log_warning("🛑 Stop signal received.")
                        break
                    self._process_single_village(driver, wait, inputs, location_village)

            # ── Structured completion summary ──
            total = self._jc_success + self._jc_failed + self._jc_skipped
            self.log_info(f"\n{'='*40}")
            self.log_info("📊 Jobcard Verification Summary")
            self.log_info(f"✅ Success: {self._jc_success}")
            self.log_info(f"❌ Failed: {self._jc_failed}")
            self.log_info(f"⏭️ Skipped: {self._jc_skipped}")
            self.log_info(f"📁 Total processed: {total}")
            self.log_info(f"{'='*40}")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e).splitlines()[0]}"
            self.log_error(f"Error: {error_msg}")
            messagebox.showerror("Automation Error", f"An error occurred: {error_msg}")
        finally:
            self.app.after(0, self.update_status, "Finished")
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")
    
    def _process_single_village(self, driver, wait, inputs, location_village):
        """Processes one village (photo upload + jobcard verification, with pagination)."""
        self.log_info(f"\n--- Processing Village: {location_village} ---")
        self.app.after(0, self.update_status, f"Processing Village: {location_village}")
        self.app.update_history("location_village", location_village)

        html_element = driver.find_element(By.TAG_NAME, "html")
        self.select_dropdown(html_element, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlVillage", location_village)
        wait.until(EC.staleness_of(html_element))

        try:
            driver.implicitly_wait(1)
            msg_element = driver.find_elements(By.ID, "ctl00_ContentPlaceHolder1_lblmsg")
            if msg_element and msg_element[0].is_displayed() and "no record found" in msg_element[0].text.lower():
                self.log_info(f"   - Village has no records. Skipping.")
                return
        finally:
            driver.implicitly_wait(20)

        # --- PAGINATION LOOP ---
        page_count = 1
        while not self.is_stopped():
            self.log_info(f"   > Processing Page {page_count}")
            self._process_jobcards_for_current_page(
                driver, wait, inputs['verify_account_only'], inputs['panchayat'], location_village)

            # Pass the current page number so we know what to look for (Next = page_count + 1)
            if not self._handle_pagination(driver, wait, page_count):
                self.log_info("   - End of pages for this village.")
                break

            page_count += 1
            time.sleep(2)

    def _add_jc_result_row(self, panchayat, village, jobcard_no, status, details):
        """Insert a row into results_tree (thread-safe) + track counters.

        `safe_tree_insert` via app.after(0, ...) se main thread par insert
        hota hai — WhatsApp summary/Excel `results_tree` se hi banta hai.
        """
        status_lower = status.lower()
        if 'success' in status_lower:
            self._jc_success += 1
            tags = ("success",)
        elif 'fail' in status_lower:
            self._jc_failed += 1
            tags = ("failed",)
        else:
            self._jc_skipped += 1
            tags = ("skipped",)
        self.safe_tree_insert(
            (datetime.now().strftime("%H:%M:%S"), panchayat, village, jobcard_no, status, details),
            tags=tags,
        )

    def _process_jobcards_for_current_page(self, driver, wait, verify_account_only, panchayat, village):
        row_index = 2 
        while not self.is_stopped():
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
                        self.log_info(f"   - Skipping Jobcard {jobcard_no} (No Account Number)")
                        self._add_jc_result_row(panchayat, village, jobcard_no, "⏭️ Skipped", "No Account Number")
                        should_skip = True
                except Exception:
                    self._add_jc_result_row(panchayat, village, jobcard_no, "⏭️ Skipped", "Account check error")
                    should_skip = True

            if should_skip:
                row_index += 1
                continue

            self.log_info(f"   - Verifying Jobcard: {jobcard_no}")
            photo_to_upload = self._get_photo_for_jobcard(jobcard_no)
            
            upload_link = None
            upload_ok = False
            try:
                links = driver.find_elements(By.ID, f"{row_id_base}_link_img_F")
                if not links: links = driver.find_elements(By.ID, f"{row_id_base}_link_img_W")
                if links: upload_link = links[0]
            except Exception as e: logger.debug("JobcardVerify: Could not find upload link: %s", e)

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
                    upload_ok = True
                    self.log_success("     - Photo uploaded successfully.")
                except Exception as ex:
                    self.log_error(f"     - Upload failed: {str(ex)}")
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
                self.log_success(f"     - Saved: {final_alert.text}")
                final_alert.accept()
                
                # Element wait handled by WebDriverWait below
                wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_UC_panch_vill_reg1_ddlpnch")))
                row_index = 2
                detail = "Photo uploaded + Saved" if upload_ok else "Saved"
                self._add_jc_result_row(panchayat, village, jobcard_no, "✅ Success", detail)
            except Exception as e:
                self.log_error(f"     - Error saving row: {e}")
                self._add_jc_result_row(panchayat, village, jobcard_no, "❌ Failed", str(e)[:150])
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
                self.log_info(f"   - Switching to Page {next_page_str}...")
                html_element = driver.find_element(By.TAG_NAME, "html")
                driver.execute_script("arguments[0].click();", next_btn[0])
                wait.until(EC.staleness_of(html_element))
                return True
            
            return False # No more pages found

        except Exception as e:
            self.log_warning(f"   - Pagination check failed: {e}")
            return False
        finally:
            # ALWAYS restore standard wait time
            driver.implicitly_wait(20)