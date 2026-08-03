# tabs/del_demand_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime
from src import config
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, StaleElementReferenceException, TimeoutException  # noqa: F401


# Dropdown label used when the user wants to process ALL villages
ALL_VILLAGES_LABEL = "🌐 All Villages"


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
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="del_demand")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) 
        
        self._create_widgets()
    def _create_widgets(self) -> None:
        # --- Header / intro card (pending-bills style) ---
        self._create_header_card(self, "🗑️", "Delete Demand",
                                 "Delete demands for one village, or all villages in a Panchayat, on the portal.",
                                 icon_key="emoji_del_demand")

        # --- Section 1: Input Controls (card) ---
        controls_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        controls_frame.grid_columnconfigure(1, weight=1)
        controls_frame.grid_columnconfigure(3, weight=1)

        # 1. Panchayat Name Input
        ctk.CTkLabel(controls_frame, text="Panchayat Name:").grid(row=0, column=0, sticky='w', padx=(15, 5), pady=12)
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=config.ALL_PANCHAYATS_LABEL)
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var,
                                                values=self._all_panchayat_values(p_vals))
        self.panchayat_menu.grid(row=0, column=1, sticky='ew', padx=5, pady=12)

        # 2. Village Name Input (Optional)
        ctk.CTkLabel(controls_frame, text="Village Name:").grid(row=0, column=2, sticky='w', padx=(15, 5), pady=12)
        v_vals = self.app.history_manager.get_suggestions("location_village") or [""]
        self.village_var = ctk.StringVar(value=ALL_VILLAGES_LABEL)
        self.village_menu = ctk.CTkOptionMenu(controls_frame, variable=self.village_var,
                                              values=[ALL_VILLAGES_LABEL] + [v for v in v_vals if v])
        self.village_menu.grid(row=0, column=3, sticky='ew', padx=(5, 15), pady=12)

        # Filter villages when panchayat changes
        def _on_panchayat_change(*_):
            pan = self.panchayat_var.get()
            if pan:
                vals = self.app.history_manager.get_filtered_suggestions("location_village", "location_panchayat", pan) or []
            else:
                vals = self.app.history_manager.get_suggestions("location_village") or []
            self.village_var.set(ALL_VILLAGES_LABEL)
            self.village_menu.configure(values=[ALL_VILLAGES_LABEL] + [v for v in vals if v])
        self.panchayat_var.trace_add("write", _on_panchayat_change)

        # 3. Explanatory Note
        note_text = "💡 Select '🌐 All Panchayats' for all panchayats, and '🌐 All Villages' for all villages of a panchayat."
        note_label = ctk.CTkLabel(controls_frame, text=note_text, font=ctk.CTkFont(size=11, slant="italic"), text_color="gray60")
        note_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=15, pady=(0, 12))

        # --- Section 2: Action Buttons ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,10))

        # --- Section 3: Data Notebook ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0,10))
        
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # Tab: Results Table
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        self.export_csv_button = ctk.CTkButton(results_action_frame, text="📥 Export to Excel", command=lambda: self.export_treeview_to_excel(self.results_tree, default_filename="delete_demand_results.xlsx", filter_mode="Export All"))
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
        self.panchayat_menu.configure(state=state)
        self.village_menu.configure(state=state)
    def start_automation(self) -> None:
        panchayat = self.panchayat_var.get().strip()
        village = self.village_var.get().strip()
        if village == ALL_VILLAGES_LABEL:
            village = ""  # Process ALL villages in the panchayat

        if not panchayat:
            messagebox.showwarning("Input Error", "Panchayat Name is required.")
            return
        if panchayat == config.ALL_PANCHAYATS_LABEL:
            if not messagebox.askyesno("Confirm", "This will process ALL panchayats in the block. Continue?"):
                return

        self.safe_tree_clear()

        if panchayat != config.ALL_PANCHAYATS_LABEL:
            self.app.update_history("location_panchayat", panchayat)
        if village:
            self.app.update_history("location_village", village)
        
        self.app.start_automation_thread(
            self.automation_key, 
            self.run_automation_logic, 
            args=(panchayat, village)
        )

    def run_automation_logic(self, target_panchayat, target_village):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        
        mode_msg = f"Target Village: {target_village}" if target_village else "Mode: ALL Villages"
        self.log_info(f"Starting Delete Demand. {mode_msg}")
        self.app.after(0, self.app.set_status, "Running Delete Demand...")

        try:
            driver = self.app.get_driver()
            if not driver: return

            wait = WebDriverWait(driver, 15)
            url = config.DEL_DEMAND_CONFIG.get("url", "https://nregade4.dord.gov.in/Netnrega/deletedemand.aspx")
            
            # Determine which panchayats to process
            all_mode = target_panchayat == config.ALL_PANCHAYATS_LABEL
            panchayats_to_process = []
            if all_mode:
                self.log_info("Fetching all panchayats from the website...")
                driver.get(url)
                try:
                    panchayat_dd_elem = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Panchyt")
                    panchayat_dropdown = Select(panchayat_dd_elem)
                    panchayats_to_process = [t for t in self._get_select_option_texts(panchayat_dropdown) if t]
                except NoSuchElementException:
                    self.log_error("🌐 All Panchayats mode requires PO login (Panchayat dropdown not found).")
                    return
                self.log_info(f"🌐 All Panchayats mode: found {len(panchayats_to_process)} panchayats.")
            else:
                panchayats_to_process = [target_panchayat]

            total_p = len(panchayats_to_process)
            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped():
                    self.log_warning("⏹️ Automation stopped by user.")
                    break
                target_panchayat = p_name
                self.log_info(f"===== Panchayat {p_idx+1}/{total_p}: {target_panchayat} =====")
                self.app.after(0, self.update_status, f"{target_panchayat}...", p_idx / max(total_p, 1))
                self.log_info("Navigating to Delete Demand page...")
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
                        self.log_info(f"Selecting Panchayat: '{found_p}'...")
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
                        self.log_warning(f"Panchayat '{target_panchayat}' not found in dropdown. Skipping.")
                        continue
                except NoSuchElementException:
                    self.log_info("Panchayat dropdown not found. Assuming GP Login.")
                    if all_mode:
                        self.log_warning("All Panchayats mode not possible with GP login. Stopping.")
                        break

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
                        self.log_warning(f"Village '{target_village}' not found in {target_panchayat}. Skipping.")
                        continue
                else:
                    villages_to_process = [opt.text for opt in village_dropdown.options if "Select" not in opt.text]

                self.log_info(f"Found {len(villages_to_process)} village(s) to process.")
                # 3. Iterate through Villages
                total_v = len(villages_to_process)
                for i, v_name in enumerate(villages_to_process):
                    if self.is_stopped():
                        self.log_warning("⏹️ Automation stopped by user.")
                        break

                    pct = (i + 1) / max(total_v, 1) * 100
                    self.log_info(f"  🔄 [{i+1}/{total_v}] Village: {v_name} ({pct:.0f}%)")
                    self.app.after(0, self.update_status, f"{target_panchayat}: {i+1}/{total_v}", (p_idx + (i + 1) / max(total_v, 1)) / max(total_p, 1))

                    # After first village, re-navigate and RESET page state completely
                    if i > 0:
                        self.log_info(f"Re-navigating to page for next village...")
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
                        time.sleep(1.5)  # Brief wait for postback to begin

                        try:
                            wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDL_Panchyt")))
                        except TimeoutException:
                            self.log_warning(f"   ⚠️ Panchayat dropdown not found after re-navigation!")
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
                                    self.log_warning(f"   ⚠️ Village dropdown didn't populate after panchayat re-select.")
                        except NoSuchElementException:
                            self.log_info(f"   ⚠️ Panchayat dropdown not found (GP Login?).")

                    self._process_village(driver, wait, target_panchayat, v_name)
            # Count results from tree
            success_count = 0
            fail_count = 0
            skip_count = 0
            for item_id in self.results_tree.get_children():
                vals = self.results_tree.item(item_id)['values']
                if len(vals) >= 5:
                    st = str(vals[4]).lower()
                    if 'success' in st:
                        success_count += 1
                    elif 'fail' in st or 'error' in st:
                        fail_count += 1
                    elif 'skip' in st:
                        skip_count += 1

            final_msg = "Finished" if not self.is_stopped() else "Stopped"
            self.app.after(0, self.update_status, final_msg, 1.0)
            self.log_info(f"{'='*50}")
            self.log_info(f"📊 Delete Demand: ✅ {success_count} deleted, ❌ {fail_count} failed, ⏭️ {skip_count} skipped (of {total_p} panchayats)")
            self.log_info(f"{'='*50}")
        except Exception as e:
            self.handle_error(e)
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")

    def _process_village(self, driver, wait, panchayat, location_village):
        try:
            # Re-find dropdown (to avoid stale element after postbacks)
            village_dd_elem = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")))
            village_dropdown = Select(village_dd_elem)
            
            # Verify the village option exists before selecting
            village_texts = [opt.text.strip() for opt in village_dropdown.options]
            if location_village not in village_texts:
                self.log_warning(f"   ⚠️ Village '{location_village}' not in dropdown options. Skipping.")
                self._log_result(panchayat, location_village, "-", "Skipped", "Village not found in dropdown after navigation.")
                return
            
            self._select_by_text_case_insensitive(village_dropdown, location_village)
            self.log_info(f"📍 Selected: {location_village}. Waiting for data...")
            no_data_locator = (By.ID, "ctl00_ContentPlaceHolder1_nodata_msg")
            grid_locator    = (By.ID, "ctl00_ContentPlaceHolder1_grd_AppRecord")

            # Wait for AJAX postback to complete (slower server = longer wait)
            fast_wait = WebDriverWait(driver, 20, poll_frequency=0.3)

            def page_settled(d):
                # Confirm dropdown selection took effect
                try:
                    dd = Select(d.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village"))
                    if dd.first_selected_option.text.strip() != location_village:
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
                self.log_warning(f"   ⏱ Village {location_village}: AJAX postback timed out, proceeding anyway...")
            # --- Early exit: "no data" / "already deleted" message ---
            try:
                msg_elem = driver.find_element(*no_data_locator)
                msg_text = msg_elem.text.strip()
                if msg_text:
                    self.log_info(f"   ℹ️ {location_village}: {msg_text}. Skipping.")
                    self._log_result(panchayat, location_village, "-", "Skipped", msg_text)
                    return
            except NoSuchElementException:
                pass

            # Step A: Check if grid exists
            try:
                grid = driver.find_element(*grid_locator)
                if not grid.is_displayed():
                    self.log_info(f"   ℹ️ {location_village}: Grid hidden. No pending demands.")
                    self._log_result(panchayat, location_village, "-", "Skipped", "Grid not visible - no data.")
                    return
            except NoSuchElementException:
                self.log_info(f"   ℹ️ {location_village}: No grid found. No pending demands.")
                self._log_result(panchayat, location_village, "-", "Skipped", "No pending demands found in this village.")
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
                self.log_info(f"   ℹ️ {location_village}: No valid data rows in grid.")
                self._log_result(panchayat, location_village, "-", "Skipped", "No valid data rows found in grid.")
                return

            self.log_info(f"   ✅ Found {len(jobcards_in_village)} demand(s) to delete in {location_village}.")
            # Step C: Smart Checkbox Toggle (User's Logic)
            try:
                check_all_box = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_chkdel")
                
                # ⬇️ FIX: Scroll into view + JavaScript click (works even if tab is in background)
                driver.execute_script("arguments[0].scrollIntoView(true);", check_all_box)
                time.sleep(0.3)
                
                if check_all_box.is_selected():
                    self.log_info(f"   🔄 Checkbox was already checked, toggling...")
                    driver.execute_script("arguments[0].click();", check_all_box)
                    time.sleep(0.3)
                
                # JavaScript click — works reliably even when tab is not focused
                driver.execute_script("arguments[0].click();", check_all_box)
                time.sleep(0.5)
                
                # Verify checkbox state — retry once if not checked
                if not check_all_box.is_selected():
                    self.log_info(f"   🔄 First JS click didn't register, retrying...")
                    driver.execute_script("arguments[0].click();", check_all_box)
                    time.sleep(0.3)
                
                checked = check_all_box.is_selected()
                if checked:
                    self.log_info(f"   ☑️ Select All checkbox ticked successfully!")
                else:
                    self.log_error(f"   ❌ Could not tick the select-all checkbox!")
                    self._log_result(panchayat, location_village, "-", "Failed", "Could not tick select-all checkbox.")
                    return
                    
            except NoSuchElementException:
                self.log_error(f"   ❌ {location_village}: Check ALL box not found!")
                self._log_result(panchayat, location_village, "-", "Failed", "Check ALL box not found.")
                return

            # Step D: Click Delete Button
            try:
                delete_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_btndel")
                delete_btn.click()
                self.log_info(f"   🗑️ Delete button clicked, handling confirmation...")                
                # Handle JS Alert
                try:
                    alert = wait.until(EC.alert_is_present())
                    alert_text = alert.text
                    self.log_info(f"   ⚠️ Alert: '{alert_text}' → Accepting...")
                    alert.accept()
                    time.sleep(0.5)  # Brief wait for postback to begin
                except TimeoutException:
                    self.log_info(f"   ℹ️ No JS alert appeared, proceeding...")                
                # Step E: Wait for Success Message and Log Results
                success_msg_locator = (By.ID, "ctl00_ContentPlaceHolder1_del_msg")
                try:
                    msg_elem = wait.until(EC.presence_of_element_located(success_msg_locator))
                    server_msg = msg_elem.text.strip()
                    self.log_info(f"   ✅ {location_village}: Server response: '{server_msg}'")                    
                    # Log each deleted jobcard individually
                    for info in jobcards_in_village:
                        self._log_result(panchayat, location_village, info, "Success", server_msg)
                        
                except TimeoutException:
                    self.log_warning(f"   ⚠️ {location_village}: Could not verify success message (timeout).")
                    for info in jobcards_in_village:
                        self._log_result(panchayat, location_village, info, "Failed", "Could not verify success message.")

            except NoSuchElementException:
                self.log_error(f"   ❌ {location_village}: Delete button not found!")
                self._log_result(panchayat, location_village, "-", "Failed", "Delete button not found.")

        except (StaleElementReferenceException, Exception) as e:
            error_msg = str(e).split('\n')[0]
            self.log_error(f"   ❌ Error on {location_village}: {error_msg}")
            self._log_result(panchayat, location_village, "-", "Error", error_msg)

    def _log_result(self, panchayat, village, applicant_info, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (timestamp, panchayat, village, applicant_info, status, details)
        self.safe_tree_insert(values)