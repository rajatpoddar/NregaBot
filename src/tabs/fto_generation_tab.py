# tabs/fto_generation_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, json, os, re
import threading
from datetime import datetime

from src import config
from src.i18n import tr
from .base_tab import BaseAutomationTab
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, StaleElementReferenceException, TimeoutException  # noqa: F401


class FtoGenerationTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="fto_gen")
        self.automation_has_run = False 
        self.stored_location_data = {} 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        
        # Default common paths for Old Firefox
        self.default_paths = [
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            r"C:\Program Files\Mozilla Firefox\firefox.exe"
        ]
        
        self._create_widgets()
        self._load_saved_path()
    def _create_widgets(self) -> None:

        # ── Header card ──
        self._create_header_card(self, "✍️", tr("tab.fto_generation.title"), tr("tab.fto_generation.subtitle"),
                                 icon_key="emoji_fto_gen")

        # Main settings card (bordered, pending-bills style)
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        controls_frame.grid_columnconfigure(0, weight=1)

        note_text = tr("form.fto.instructions")
        ctk.CTkLabel(controls_frame, text=note_text, justify="left").grid(row=0, column=0, sticky='w', padx=15, pady=(5, 2))
        
        # --- NEW: Browser Setup Frame ---
        setup_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        setup_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 2))
        setup_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(setup_frame, text=tr("form.fto.old_ff_path"), font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        self.ff_path_entry = ctk.CTkEntry(setup_frame, placeholder_text="e.g. C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe")
        self.ff_path_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=5)

        self.browse_btn = ctk.CTkButton(setup_frame, text=tr("common.browse"), width=70, command=self._browse_firefox)
        self.browse_btn.grid(row=0, column=2, padx=5, pady=5)

        self.check_install_btn = ctk.CTkButton(setup_frame, text=tr("form.fto.check_install"), width=100, fg_color=config.COLORS["orange"], hover_color=config.COLORS["orange_hover"], command=self._check_installation)
        self.check_install_btn.grid(row=0, column=3, padx=5, pady=5)

        self.launch_btn = ctk.CTkButton(setup_frame, text=tr("form.fto.launch_old_ff"), fg_color=config.COLORS["green_launch"], hover_color=config.COLORS["teal_green_hover"], command=self._launch_firefox)
        self.launch_btn.grid(row=0, column=4, padx=5, pady=5)

        # --- ABPS Check Button Container (hidden until used) ---
        self.abps_container = ctk.CTkFrame(controls_frame, fg_color="transparent", height=0)
        self.abps_container.grid(row=2, column=0, sticky="ew", pady=(0, 0))
        self.abps_container.grid_remove() # Hide initially
        
        self.check_abps_button = ctk.CTkButton(
            self.abps_container, 
            text=tr("form.fto.check_pending_abps"), 
            command=self._go_to_mr_tracking,
            width=200,
            height=32,
            fg_color=config.COLORS["blue"],
            hover_color=config.COLORS["blue_hover"],
            font=ctk.CTkFont(size=13, weight="bold")
        )

        # --- Action buttons (OUTSIDE the card) ---
        action_frame_wrapper = self._create_action_buttons(parent_frame=self)
        action_frame_wrapper.grid(row=2, column=0, sticky='ew', pady=(2, 6), padx=15)

        # Access inner container to add separator and Delete button
        inner_container = action_frame_wrapper.winfo_children()[0] 
        
        # Separator (Visual Gap)
        ctk.CTkFrame(inner_container, width=2, height=20, fg_color="gray60").pack(side="left", padx=15)

        # Delete Button (Separated from Reset)
        self.delete_btn = ctk.CTkButton(
            inner_container, 
            text=tr("form.fto.delete_ftos"), 
            command=self.start_delete_automation,
            fg_color="#9B2C2C", 
            hover_color="#7F1D1D",
            width=110,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.delete_btn.pack(side="left", padx=(0, 0))
        
        # --- Results Area ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        
        self._create_log_and_status_area(parent_notebook=notebook)
        results_frame = notebook.add("Results")

        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)
        
        cols = ("Panchayat", "Type", "Status", "Info", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Panchayat", width=140)
        self.results_tree.column("Type", width=150)
        self.results_tree.column("Status", width=100)
        self.results_tree.column("Info", width=300)
        self.results_tree.column("Timestamp", width=100, anchor='center')
        self.results_tree.grid(row=0, column=0, sticky='nsew')
        
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    # ============================================================================
    # NEW OLD FIREFOX SETUP LOGIC
    # ============================================================================

    def _browse_firefox(self):
        path = filedialog.askopenfilename(
            title=tr("form.fto.select_ff_exe"),
            filetypes=[("Executable Files", "*.exe")]
        )
        if path:
            self.ff_path_entry.delete(0, tkinter.END)
            self.ff_path_entry.insert(0, path)
            self._save_path(path)

    def _check_installation(self):
        path = self.ff_path_entry.get().strip()
        if not path:
            for p in self.default_paths:
                if os.path.exists(p):
                    path = p
                    self.ff_path_entry.insert(0, path)
                    break
        
        if path and os.path.exists(path):
            messagebox.showinfo(tr("status.success"), tr("dialogs.ff_found", path=path))
            self._save_path(path)
        else:
            messagebox.showwarning(tr("dialogs.not_found"), tr("dialogs.ff_not_found"))

    def _launch_firefox(self):
        path = self.ff_path_entry.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showerror(tr("dialogs.error"), tr("dialogs.valid_ff_required"))
            return
        
        self.log_info("Launching Old Firefox...")
        self.launch_btn.configure(state="disabled", text=tr("form.fto.launching"))
        
        url = "https://nregade4.nic.in/netnrega/Login.aspx?&level=HomePO&state_code=34"

        def _thread():
            # Yeh call aapke browser_manager.py ka naya function hit karegi
            success, msg = self.app.browser_manager.launch_old_firefox(path, url)
            if success:
                self.log_success("Browser Launched. Please login manually, plug in your DSC token, then click Start.")
                self.app.after(0, lambda: messagebox.showinfo(tr("dialogs.browser_ready"), tr("dialogs.ff_open_msg")))
            else:
                self.log_error(msg)
                self.app.after(0, lambda: messagebox.showerror(tr("dialogs.browser_error"), msg))
            
            self.app.after(0, lambda: self.launch_btn.configure(state="normal", text=tr("form.fto.launch_old_ff")))

        threading.Thread(target=_thread, daemon=True).start()

    def _save_path(self, path):
        self.app.update_history("old_firefox_path", path)

    def _load_saved_path(self):
        saved = self.app.history_manager.get_suggestions("old_firefox_path")
        if saved:
            self.ff_path_entry.insert(0, saved[0])

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        self.delete_btn.configure(state="disabled" if running else "normal")
        self.ff_path_entry.configure(state="disabled" if running else "normal")
        self.browse_btn.configure(state="disabled" if running else "normal")
        self.check_install_btn.configure(state="disabled" if running else "normal")
        self.launch_btn.configure(state="disabled" if running else "normal")
        
        if running:
            self.check_abps_button.pack_forget()
            self.abps_container.grid_remove() 
        elif self.automation_has_run:
            self.abps_container.grid() 
            self.check_abps_button.pack(anchor="center", pady=(5, 5)) 
        else:
             self.check_abps_button.pack_forget()
             self.abps_container.grid_remove() 
    def start_automation(self) -> None:
        self.automation_has_run = False 
        self.stored_location_data = {} 
        self.check_abps_button.pack_forget()
        self.abps_container.grid_remove() 
        self.app.start_automation_thread(self.automation_key, self.run_generation_logic)

    def start_delete_automation(self):
        if not messagebox.askyesno(tr("dialogs.confirm_delete"), tr("dialogs.delete_fto_confirm")):
            return
        self.app.start_automation_thread(self.automation_key + "_del", self.run_delete_logic)

    def _log_result(self, r_type, status, info):
        panchayat = (self.stored_location_data or {}).get('panchayat', '') or '-'
        self.safe_tree_insert((panchayat, r_type, status, info, datetime.now().strftime("%H:%M:%S")))

    # ============================================================================
    # GENERATION LOGIC (WITH FIXED SCRAPING) - UNTOUCHED
    # ============================================================================

    def run_generation_logic(self):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.safe_tree_clear()
        self.update_status("Starting Generation...", 0)
        
        success_count = 0
        total_steps = 2
        try:
            driver = self.app.get_driver()
            if not driver: return
            cfg = config.FTO_GEN_CONFIG
            wait = WebDriverWait(driver, 15)
            
            self.log_info("🔐 Step 1/2: Processing Aadhaar FTO...")
            self.update_status("Processing Aadhaar FTO...", 0.25)
            result_1 = self._process_verification_page(driver, wait, cfg["aadhaar_fto_url"], "Aadhaar Gen")
            if result_1: success_count += 1

            self.log_info("🔐 Step 2/2: Processing Top-Up FTO...")
            self.update_status("Processing Top-Up FTO...", 0.75)
            result_2 = self._process_verification_page(driver, wait, cfg["top_up_fto_url"], "Top-Up Gen")
            if result_2: success_count += 1
            
            self.log_info(f"{'='*50}")
            if success_count == total_steps:
                self.log_success(f"FTO Generation Complete! Both steps processed successfully.")
            elif success_count > 0:
                self.log_warning(f"FTO Generation: {success_count}/{total_steps} steps completed.")
            else:
                self.log_error(f"FTO Generation: No steps completed successfully.")
                self.log_info(f"{'='*50}")
        except Exception as e:
            self.log_error(f"Error: {e}")
        finally:
            self.automation_has_run = True
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Finished", 1.0)
            self.app.after(0, self.app.set_status, "Ready")

    def _process_verification_page(self, driver, wait, url, name):
        try:
            self.log_info(f"🌐 Navigating to {name}...")
            driver.get(url)
            
            # --- SCRAPE LOCATION DATA IMMEDIATELY ---
            if not self.stored_location_data: 
                self._scrape_location_from_page(driver)

            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_wage_list_verify")))
            
            if not driver.find_elements(By.XPATH, "//input[contains(@id, '_auth')]"):
                self.log_warning(f"  ⏭️ {name}: No records found to process.")
                self._log_result(name, "Skipped", "No records found")
                return False

            self.log_info(f"  🔘 Selecting all authorization checkboxes...")
            driver.execute_script("document.querySelectorAll('input[id*=\"_auth\"]').forEach(radio => radio.click());")
            
            self.log_info(f"  👆 Clicking 'Verified' button...")
            submit_btn = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ch_verified")))
            driver.execute_script("arguments[0].click();", submit_btn)
            
            self.log_info(f"  🖊️ Clicking Digital Signature button...")
            auth_btn = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_btn")))
            driver.execute_script("arguments[0].click();", auth_btn)
            
            alert = wait.until(EC.alert_is_present())
            fto_match = re.search(r'FTO No : \((.*?)\)', alert.text)
            fto = fto_match.group(1) if fto_match else "Generated"
            
            self.log_success(f"  ✅ {name}: FTO Generated — {fto}")
            self._log_result(name, "Success", f"FTO: {fto}")
            alert.accept()
            return True
        except TimeoutException:
            self._log_result(name, "Failed", "Page load / Login error")
            self.log_error(f"  ❌ {name}: Timeout — page load ya login error")
            return False
        except Exception as e:
            self._log_result(name, "Error", str(e)[:100])
            self.log_error(f"  ❌ {name}: {str(e).splitlines()[0]}")
            return False

    def _scrape_location_from_page(self, driver):
        """Helper to scrape District, Block, Panchayat from TABLE CELLS (Not IDs)."""
        try:
            self.log_info("Capturing location info...")            
            def get_text_by_xpath(label):
                try:
                    # Finds <td> containing "District" and gets text
                    elem = driver.find_element(By.XPATH, f"//td[contains(text(), '{label}')]")
                    text = elem.text 
                    if ":" in text:
                        return text.split(":")[1].strip()
                    return text.strip()
                except:
                    return None

            # 1. District
            dist = get_text_by_xpath("District")
            if dist: self.stored_location_data['district'] = dist

            # 2. Block
            blk = get_text_by_xpath("Block")
            if blk: self.stored_location_data['block'] = blk

            # 3. Panchayat
            panch = get_text_by_xpath("Panch")
            if panch:
                self.stored_location_data['panchayat'] = panch

            if self.stored_location_data:
                self.log_info(f"Location captured: {self.stored_location_data}")
            else:
                self.log_warning("Could not capture location data using XPath.")
        except Exception as e:
            print(f"Scrape Error: {e}")

    # ============================================================================
    # DELETION LOGIC (WITH SCROLL FIX) - UNTOUCHED
    # ============================================================================
    
    def run_delete_logic(self):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.update_status("Starting Deletion...", 0)
        
        try:
            driver = self.app.get_driver()
            if not driver: return
            cfg = config.FTO_GEN_CONFIG
            wait = WebDriverWait(driver, 10)

            self.update_status("Deleting from Link 1...", 0.2)
            self._process_deletion_page(driver, wait, cfg["delete_url_1"], "Delete (Type 1)")

            self.update_status("Deleting from Link 2...", 0.6)
            self._process_deletion_page(driver, wait, cfg["delete_url_2"], "Delete (Type 2)")
            
            self.log_info("Deletion process finished.")
            messagebox.showinfo(tr("dialogs.finished"), tr("dialogs.fto_delete_complete"))

        except Exception as e:
            self.log_error(f"Critical Error: {e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Ready", 1.0)

    def _process_deletion_page(self, driver, wait, url, log_name):
        try:
            self.log_info(f"Navigating to {log_name}...")
            driver.get(url)
            
            try:
                dd_elem = wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
                select = Select(dd_elem)
            except:
                self.log_warning("Dropdown not found.")
                self._log_result(log_name, "Skipped", "Dropdown not found")
                return

            if len(select.options) <= 1:
                self.log_info("No FTOs available.")
                self._log_result(log_name, "Skipped", "No FTOs")
                return

            fto_text = select.options[1].text
            self.log_info(f"Selecting: {fto_text}")
            select.select_by_index(1)

            self.log_info("Waiting for reload...")
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                pass
            
            self.log_info("Scrolling to bottom...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)  # Brief wait for postback to begin

            max_retries = 3
            radio_found = False
            for i in range(max_retries):
                try:
                    no_radio = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_rb_chkfto_n")))
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", no_radio)
                    time.sleep(1.5)  # Brief wait for postback to begin
                    driver.execute_script("arguments[0].click();", no_radio)
                    self.log_info("Selected 'No'.")
                    radio_found = True
                    break
                except StaleElementReferenceException:
                    time.sleep(1.5)  # Brief wait for postback to begin
                except Exception:
                    time.sleep(1.5)  # Brief wait for postback to begin

            if not radio_found:
                self.log_error("Could not find 'No' radio button (Check filters or scroll).")
                return

            time.sleep(1.5)  # Brief wait for postback to begin
            try:
                sign_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btn")
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", sign_btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", sign_btn)
                self.log_info("Clicked Signature.")                
                try:
                    alert = wait.until(EC.alert_is_present())
                    alert.accept()
                    self._log_result(log_name, "Success", f"Deleted {fto_text}")
                except TimeoutException:
                    self._log_result(log_name, "Check", f"Attempted {fto_text}")
            except Exception as e:
                self.log_error(f"Sign Error: {e}")
        except Exception as e:
            self._log_result(log_name, "Error", str(e))

    def _go_to_mr_tracking(self):
        """Uses data scraped DURING generation to switch tabs."""
        print(f"DEBUG: Using Stored Data: {self.stored_location_data}")
        self.app.switch_to_mr_tracking_for_abps(self.stored_location_data)