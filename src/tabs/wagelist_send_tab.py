# tabs/wagelist_send_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime
from src import config
from .base_tab import BaseAutomationTab
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoAlertPresentException, TimeoutException, UnexpectedAlertPresentException  # noqa: F401


class WagelistSendTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="send")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        
        # List of generated wagelists handed over by 'Wagelist Gen'.
        # None → send ALL wagelists for the selected year.
        self._specific_wagelists = None
        
        self._create_widgets()
    def _create_widgets(self) -> None:
        # --- Header / intro card (pending-bills style) ---
        self._create_header_card(self, "📤", "Send Wagelist",
                                 "Send generated (or all) pending wagelists via the EFMS portal.",
                                 icon_key="emoji_send_wagelist")

        # --- Settings card: Financial Year + mode info ---
        settings_container = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                          border_color=("gray85", "gray30"))
        settings_container.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        settings_container.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(settings_container, text="Financial Year:").grid(row=0, column=0, padx=(15, 5), pady=15, sticky="w")
        
        current_year = datetime.now().year
        year_options = [f"{year}-{year+1}" for year in range(current_year + 1, current_year - 10, -1)]
        
        default_year = f"{current_year}-{current_year+1}" if datetime.now().month >= 4 else f"{current_year-1}-{current_year}"
        self.fin_year_var = ctk.StringVar(value=default_year)
        self.fin_year_menu = ctk.CTkOptionMenu(settings_container, variable=self.fin_year_var, values=year_options)
        self.fin_year_menu.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="ew")

        # Mode info label — updated by populate_wagelist_data()
        self.mode_label = ctk.CTkLabel(
            settings_container,
            text="💡 Will send ALL wagelists for the selected year. Run 'Wagelist Gen' to send only the generated ones.",
            text_color="gray50", justify="left", wraplength=560,
        )
        self.mode_label.grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 12), sticky="w")

        # Action Buttons
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        # Results and Logs
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0,10))
        results_frame = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        results_frame.grid_columnconfigure(0, weight=1); results_frame.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky='ew', pady=(5, 10), padx=5)

        self.export_csv_button = ctk.CTkButton(
            results_action_frame, 
            text="📥 Export to Excel", 
            command=lambda: self.export_treeview_to_excel(self.results_tree, default_filename="wagelist_send_results.xlsx", filter_mode="Export All")
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
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.fin_year_menu.configure(state=state)
    def reset_ui(self) -> None:
        if messagebox.askokcancel("Reset Form?", "Are you sure?"):
            self._specific_wagelists = None
            self.mode_label.configure(
                text="💡 Will send ALL wagelists for the selected year. Run 'Wagelist Gen' to send only the generated ones.",
                text_color="gray50",
            )
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
    def start_automation(self) -> None:
        fin_year = self.fin_year_var.get()
        if not fin_year:
            messagebox.showerror("Input Error", "Please select a Financial Year.")
            return

        specific = getattr(self, '_specific_wagelists', None)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(fin_year, specific))

    def populate_wagelist_data(self, wagelists):
        """
        Receives the generated wagelist list from 'Wagelist Gen' and stores it.
        When the send automation starts, ONLY these wagelists are sent.
        """
        self._specific_wagelists = list(wagelists) if wagelists else None
        count = len(self._specific_wagelists) if self._specific_wagelists else 0
        if count:
            self.mode_label.configure(
                text=f"💡 Will send {count} wagelist(s) generated by 'Wagelist Gen'.",
                text_color=("#059669", "#10B981"),
            )
        self.log_info(f"Received {count} generated wagelist(s) to send.")
        self.app.set_status("Ready to send wagelists")

    # Inside tabs/wagelist_send_tab.py
    def retry_logic_handler(self) -> None:
        """
        Retry Logic for Wagelist Send.
        Since successful items are processed and removed from the list (or marked done),
        restarting the automation effectively retries the remaining/failed items.
        """
        if messagebox.askyesno("Retry", "Retrying will process the remaining wagelists.\nContinue?"):
            self.start_automation()

    def run_automation_logic(self, fin_year, specific_wagelists=None):
        self.app.after(0, self.set_ui_state, True)
        self.safe_tree_clear()
        self.app.clear_log(self.log_display)
        self.log_info("Starting automation...")
        self.app.after(0, self.app.set_status, "Running Wagelist Send...")
        self.app.after(0, self.update_status, "Initializing...", 0.0)
        
        automation_failed = False
        total = 0
        
        try:
            driver = self.app.get_driver()
            if not driver: return
            wait = WebDriverWait(driver, 15)

            driver.get(config.WAGELIST_SEND_CONFIG["url"])
            
            self.log_info(f"Selecting Financial Year: {fin_year}")
            Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlfin")))).select_by_value(fin_year)
            
            self.log_info("Waiting for wagelists to load...")
            wait.until(EC.element_to_be_clickable((By.XPATH, "//select[@id='ctl00_ContentPlaceHolder1_ddl_sel']/option[position()>1]")))
            # Element wait handled by WebDriverWait below

            all_wagelists = [o.get_attribute("value") for o in Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddl_sel")).options if o.get_attribute("value") != "select"]
            if not all_wagelists:
                self.log_warning("No wagelists found for the selected year.")
                messagebox.showwarning("No Wagelists", f"No wagelists were found for the financial year {fin_year}.")
                return
            
            # Filter wagelists: if a specific list was handed over by 'Wagelist Gen',
            # send ONLY those; otherwise send ALL wagelists for the year.
            wagelists_to_process = all_wagelists
            if specific_wagelists:
                wanted = list(dict.fromkeys(specific_wagelists))
                matched = [w for w in all_wagelists if w in wanted]
                if not matched:
                    # Fallback: partial match (generated number appears inside the dropdown value)
                    matched = [w for w in all_wagelists if any(t in w for t in wanted)]
                if not matched:
                    self.log_warning("None of the generated wagelists were found in the dropdown.")
                    messagebox.showwarning("No Wagelists",
                                            "The generated wagelists were not found in the dropdown for this financial year.")
                    return
                wagelists_to_process = matched
                self.log_info(f"Found {len(wagelists_to_process)} generated wagelist(s) to send.")
            else:
                self.log_info(f"Found {len(all_wagelists)} wagelist(s) to send (ALL for {fin_year}).")
            total = len(wagelists_to_process)
            for idx, wagelist in enumerate(wagelists_to_process, 1):
                if self.is_stopped():
                    self.log_warning("⏹️ Automation stopped by user.")
                    break
                
                pct = idx / total * 100
                self.log_info(f"  🔄 [{idx}/{total}] Sending: {wagelist} ({pct:.0f}%)")
                status_msg = f"Processing {idx}/{total}: {wagelist}"
                self.app.after(0, self.update_status, status_msg, idx / total)
                self.app.after(0, self.app.set_status, status_msg)
                
                success = self._process_single_wagelist(driver, wait, wagelist, fin_year)
                
                # --- FIX: Apply 'success' tag here ---
                status_text = "Success" if success else "Failed"
                tags = ('success',) if success else ('failed',)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                self.app.after(0, lambda w=wagelist, s=status_text, t=timestamp, tg=tags: 
                               self.results_tree.insert("", tkinter.END, values=(w, s, t), tags=tg))

                time.sleep(1)

        except Exception as e:
            automation_failed = True 
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror("Automation Error", f"An error occurred: {e}")
        finally:
            stopped = self.is_stopped()

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

            # Clear the generated-list handoff so a future manual start sends ALL wagelists.
            self._specific_wagelists = None
            self.app.after(0, lambda: self.mode_label.configure(
                text="💡 Will send ALL wagelists for the selected year. Run 'Wagelist Gen' to send only the generated ones.",
                text_color="gray50",
            ))

            if not stopped and not automation_failed:
                # Count results from tree
                success_count = 0
                fail_count = 0
                for item_id in self.results_tree.get_children():
                    vals = self.results_tree.item(item_id)['values']
                    if len(vals) >= 2:
                        st = str(vals[1]).lower()
                        if 'success' in st:
                            success_count += 1
                        elif 'fail' in st or 'error' in st:
                            fail_count += 1
                self.log_info(f"{'='*50}")
                self.log_info(f"📊 Wagelist Send: ✅ {success_count} sent, ❌ {fail_count} failed (of {total} total)")
                self.log_info(f"{'='*50}")
            self.app.after(5000, lambda: self.app.set_status("Ready"))
            self.app.after(5000, lambda: self.update_status("Ready", 0.0))

    # ------------------------------------------------------------------
    # Alert helpers — the NREGA portal shows a JS alert ("Record Update
    # sucessfully") after every submit. The alert can appear LATE (after a
    # slow postback) or flash-and-vanish, which previously made the single
    # WebDriverWait(5).alert_is_present() miss it. A leftover open alert
    # then crashed the whole run at the next page interaction with
    # "unexpected alert open". These helpers make alert handling robust.
    # ------------------------------------------------------------------
    def _dismiss_pending_alert(self, driver, timeout=1.0):
        """Safely accept & clear any JavaScript alert that may be open.

        Returns True if an alert was handled. Never raises — a lingering
        alert must never abort the automation (the critical failure seen in
        production). Fast path: probes for an already-open alert first (the
        common leftover case) so the happy path costs ~0s; only if none is
        open does it briefly wait for a late-appearing alert.
        """
        try:
            alert = driver.switch_to.alert
        except NoAlertPresentException:
            # Not open right now — give a short window for a late alert from
            # the previous wagelist's slow postback.
            try:
                WebDriverWait(driver, timeout).until(EC.alert_is_present())
                alert = driver.switch_to.alert
            except TimeoutException:
                return False
            except Exception:
                return False
        except Exception:
            return False
        # Alert is present — accept it, retrying because the alert can
        # vanish between detection and accept() (flash behaviour).
        for _ in range(3):
            try:
                driver.switch_to.alert.accept()
                time.sleep(0.8)  # let the postback settle after accepting
                return True
            except (NoAlertPresentException, UnexpectedAlertPresentException):
                time.sleep(0.3)
            except Exception:
                time.sleep(0.3)
        return True

    def _accept_submit_alert(self, driver, timeout=6.0):
        """Wait for (up to `timeout`s) and accept the submit success alert.

        Polls frequently so a late-appearing alert is still caught, and
        retries accept() so a flashing alert is handled. Returns True when
        an alert was accepted.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_stopped():
                return False
            try:
                alert = driver.switch_to.alert
            except NoAlertPresentException:
                time.sleep(0.3)
                continue
            except UnexpectedAlertPresentException:
                time.sleep(0.3)
                continue
            try:
                alert.accept()
            except Exception:
                pass
            time.sleep(0.8)  # give the postback a moment to settle
            return True
        return False

    def _process_single_wagelist(self, driver, wait, wagelist, fin_year):
        """Processes a single wagelist (Background Safe)."""
        for attempt in range(2):
            if self.is_stopped(): return False
            try:
                # Any lingering alert from the PREVIOUS wagelist's late
                # postback must be dismissed BEFORE touching the page —
                # otherwise Selenium raises 'unexpected alert open' and the
                # whole multi-wagelist run crashes (reported bug).
                self._dismiss_pending_alert(driver)

                # Select Wagelist (Presence check)
                wl_dropdown = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_sel")))
                Select(wl_dropdown).select_by_value(wagelist)
                
                wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_GridView1")))
                
                self.log_info(f"Selecting all EFMS options for {wagelist}...")                
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
                self.log_info(f"   - Instantly selected {clicked_count} EFMS options.")                
                if self.is_stopped(): return False
                
                # --- FIX: JS Click for Submit Button (Background Safe) ---
                submit_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btnsubmit")
                driver.execute_script("arguments[0].click();", submit_btn)
                
                # Wait for the success alert ('Record Update sucessfully' etc.)
                # and accept it — tolerates alerts that appear late or flash.
                if not self._accept_submit_alert(driver):
                    # No alert surfaced within the window (some postbacks skip
                    # it or it appears later). The submit was clicked — mark it
                    # sent rather than crashing the run, but log it so support
                    # can tell this happened.
                    self.log_warning(f"   - No success alert observed for {wagelist}; assuming submitted.")
                self.log_success(f"{wagelist} submitted successfully.")
                return True
            except Exception as e:
                self.log_warning(f"[WARN] Attempt {attempt+1} failed for {wagelist}: {type(e).__name__}")
                if (attempt == 0):
                    # CRITICAL: clear any open alert BEFORE refresh() — an
                    # open alert makes driver.refresh() itself throw
                    # 'unexpected alert open' and abort the entire run.
                    self._dismiss_pending_alert(driver)
                    driver.refresh()
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlfin")))
                    Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlfin")).select_by_value(fin_year)
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddl_sel")))

        self.log_error(f"{wagelist} failed after multiple attempts.")
        return False