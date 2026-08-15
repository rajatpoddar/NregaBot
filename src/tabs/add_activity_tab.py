# tabs/add_activity_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
from datetime import datetime

from src import config
from .base_tab import BaseAutomationTab
from src.utils import truncate_workcode
from src.i18n import tr
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Keys, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException  # noqa: F401


class AddActivityTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="add_activity")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._create_widgets()
    def _create_widgets(self) -> None:

        # ── Header / intro card (pending-bills style) ──
        self._create_header_card(self, "➕", tr("tab.add_activity.title"), tr("tab.add_activity.subtitle"),
                                 icon_key="emoji_add_activity")

        # ── Settings card: Price & Quantity ──
        top_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                 border_color=("gray85", "gray30"))
        top_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 10))
        top_frame.grid_columnconfigure(0, weight=1)

        # --- UPDATED: Input fields for Price and Quantity ---
        input_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        input_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        input_frame.grid_columnconfigure((1, 3), weight=1)
        
        defaults = config.ADD_ACTIVITY_CONFIG['defaults']
        ctk.CTkLabel(input_frame, text=tr("form.add_activity.default_code", code=defaults['activity_code']), font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(input_frame, text=tr("form.add_activity.unit_price")).grid(row=1, column=0, sticky="w", padx=15)
        self.unit_price_entry = ctk.CTkEntry(input_frame)
        self.unit_price_entry.grid(row=1, column=1, sticky="ew", padx=(0, 15))
        self.unit_price_entry.insert(0, defaults['unit_price'])

        ctk.CTkLabel(input_frame, text=tr("form.add_activity.quantity")).grid(row=1, column=2, sticky="w", padx=15)
        self.quantity_entry = ctk.CTkEntry(input_frame)
        self.quantity_entry.grid(row=1, column=3, sticky="ew", padx=(0, 15))
        self.quantity_entry.insert(0, defaults['quantity'])

        # Action buttons — OUTSIDE the card
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=2, column=0, sticky='ew', padx=10, pady=(0, 6))

        # Notebook for inputs and results
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        work_codes_frame = notebook.add("Work Keys")
        results_frame = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)

        # Work Keys Tab
        work_codes_frame.grid_columnconfigure(0, weight=1)
        work_codes_frame.grid_rowconfigure(1, weight=1) # <-- CORRECTED THIS LINE

        # --- NEW: Controls frame for buttons ---
        wc_controls_frame = ctk.CTkFrame(work_codes_frame, fg_color="transparent")
        wc_controls_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        clear_button = ctk.CTkButton(wc_controls_frame, text=tr("common.clear"), width=80, command=lambda: self.work_keys_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', padx=(0, 5))
        
        extract_button = ctk.CTkButton(wc_controls_frame, text=tr("common.extract_from_text"), width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_keys_text))
        extract_button.pack(side='right', padx=(0, 5))
        # --- END NEW ---

        self.work_keys_text = ctk.CTkTextbox(work_codes_frame, wrap=tkinter.WORD)
        self.work_keys_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5) # <-- Changed to row 1

        # Results Tab
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1) # Make space for the button

        results_action_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(5, 10), padx=5)
        self.export_csv_button = ctk.CTkButton(results_action_frame, text=tr("common.export_excel"), command=lambda: self.export_treeview_to_excel(self.results_tree, default_filename="add_activity_results.xlsx", filter_mode="Export All"))
        self.export_csv_button.pack(side="left")

        cols = ("Work Key", "Status", "Details", "Timestamp")
        self.results_tree = ttk.Treeview(results_frame, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        self.results_tree.column("Work Key", width=150)
        self.results_tree.column("Status", width=100, anchor='center')
        self.results_tree.column("Details", width=400)
        self.results_tree.column("Timestamp", width=100, anchor='center')
        self.results_tree.grid(row=1, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_frame, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.work_keys_text.configure(state=state)
        self.unit_price_entry.configure(state=state)
        self.quantity_entry.configure(state=state)
    def start_automation(self) -> None:
        work_keys = [line.strip() for line in self.work_keys_text.get("1.0", tkinter.END).strip().splitlines() if line.strip()]
        if not work_keys:
            messagebox.showwarning(tr("errors.input_required"), tr("dialogs.add_activity_need_key"))
            return
            
        # Get and validate the new inputs
        unit_price = self.unit_price_entry.get().strip()
        quantity = self.quantity_entry.get().strip()

        if not unit_price or not quantity:
            messagebox.showwarning(tr("errors.input_required"), tr("dialogs.add_activity_need_price"))
            return
        
        # Pass the inputs to the automation logic
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(work_keys, unit_price, quantity))
    def reset_ui(self) -> None:
        if messagebox.askokcancel(tr("dialogs.reset_form"), tr("dialogs.reset_confirm_logs")):
            self.work_keys_text.configure(state="normal")
            self.work_keys_text.delete("1.0", tkinter.END)
            # Reset price and quantity to defaults
            defaults = config.ADD_ACTIVITY_CONFIG['defaults']
            self.unit_price_entry.delete(0, tkinter.END)
            self.unit_price_entry.insert(0, defaults['unit_price'])
            self.quantity_entry.delete(0, tkinter.END)
            self.quantity_entry.insert(0, defaults['quantity'])
            
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    def run_automation_logic(self, work_keys, unit_price, quantity):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.safe_tree_clear()
        self.log_info("Starting 'Add Activity' automation...")
        self.app.after(0, self.app.set_status, "Running Add Activity...")

        try:
            driver = self.app.get_driver()
            if not driver:
                return

            total = len(work_keys)
            for i, work_key in enumerate(work_keys):
                if self.is_stopped():
                    self.log_warning("Automation stopped.")
                    break
                self.app.after(0, self.update_status, f"Processing {i+1}/{total}: {work_key}", (i+1) / total)
                self._process_single_work_key(driver, work_key, unit_price, quantity)

            # Queue summary on main thread after inserts are processed
            self.app.after(200, lambda: self._show_add_activity_summary(work_keys))
        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            messagebox.showerror(tr("base.automation_error.title"), f"An error occurred:\n\n{e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _log_result(self, work_key, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        work_key = truncate_workcode(work_key)
        status_lower = status.lower()
        tags = ()
        if 'success' in status_lower or 'saved' in status_lower:
            tags = ('success',)
        elif 'fail' in status_lower or 'error' in status_lower:
            tags = ('failed',)
        self.safe_tree_insert((work_key, status, details, timestamp), tags)

    def _show_add_activity_summary(self, work_keys):
        """Show professional summary after automation finishes.
        Called via app.after() on main thread after treeview inserts are processed."""
        if not self._is_alive():
            return
        total = len(work_keys)
        success = sum(1 for item in self.results_tree.get_children() if 'success' in str(self.results_tree.item(item)['values'][1]).lower())
        failed = total - success
        summary = f"✅ Success: {success}\n❌ Failed: {failed}\n📊 Total: {total}"
        self.update_status(f"✅ {success}/{total} success", 1.0)
        self.log_info(f"{'='*40}\n📊 Add Activity Summary\n{summary}\n{'='*40}")
        if total > 0:
            self.log_info(f"📊 Add Activity complete: {summary}")

    def retry_logic_handler(self) -> None:
        """Override to map the retry button to the work_keys_text box."""
        self.retry_failed_automation(self.work_keys_text)

    def _scroll_to(self, driver, element):
        """Scroll an element into view so clicks/keypresses land on it."""
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                element
            )
        except Exception:
            pass
        time.sleep(0.3)

    @staticmethod
    def _find_work_option(work_select, work_key):
        """Find the dropdown option that matches the work key.

        The redesigned page pre-loads EVERY work of the block into the work
        dropdown, so picking option index 1 would silently select the WRONG
        work code. Match precisely instead:
          1. exact option value           (full code, e.g. 3422003001/IF/IAY/18030)
          2. value ending '/<key>'        (last path segment, e.g. 18030)
          3. value ending with <key>      (loose suffix)
          4. option text contains <key>   (last resort)
        """
        key = (work_key or "").strip()
        if not key:
            return None
        # Drop the placeholder option(s) — value '00' only ever belongs to
        # "---Select---" / "--Select Activity--" placeholders on this page.
        options = [
            opt for opt in work_select.options
            if (opt.get_attribute("value") or "").strip() not in ("", "00")
        ]
        for opt in options:
            val = (opt.get_attribute("value") or "").strip()
            if val == key:
                return opt
        for opt in options:
            val = (opt.get_attribute("value") or "").strip()
            if val.endswith("/" + key):
                return opt
        for opt in options:
            val = (opt.get_attribute("value") or "").strip()
            if val.endswith(key):
                return opt
        for opt in options:
            if key in (opt.text or ""):
                return opt
        return None

    def _wait_for_settle(self, driver, timeout=20, action_name=""):
        """Wait for the UpdatePanelMain 'Please Wait...' overlay to finish.

        The activity section lives inside an UpdatePanel, so every action after
        selecting the work (activity dropdown, unit price, quantity, save) runs
        an ASYNC postback that swaps the panel content in place. Staleness waits
        are unreliable there — touching an element mid-swap raises
        stale-element errors — so we wait on the UpdateProgress overlay instead.
        """
        overlay_id = 'ctl00_ContentPlaceHolder1_UpdateProgress2'
        try:
            # Short wait: does the overlay appear at all? (fast postbacks <100ms
            # never show it because displayAfter=100).
            short = WebDriverWait(driver, 2)
            if short.until(EC.visibility_of_element_located((By.ID, overlay_id))):
                # Postback is running — wait for it to finish.
                WebDriverWait(driver, timeout).until(
                    EC.invisibility_of_element_located((By.ID, overlay_id))
                )
                if action_name:
                    self.log_info(f"   - Page settled after '{action_name}'.")
        except TimeoutException:
            pass  # overlay never appeared (fast async postback) — assume settled
        # Full postbacks (search, work select) reload the whole page — make sure
        # the document actually finished loading before touching anything.
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            pass
        time.sleep(0.6)

    def _js_set_value(self, driver, element, value):
        """Set an input's value WITHOUT firing its onchange handler.

        On this page the Unit Price & Quantity textboxes carry
        onchange=__doPostBack inside the UpdatePanel — send_keys into one and
        then focusing the sibling field BLURS the first one, firing an async
        postback that re-renders the panel and wipes both fields (live symptom:
        'Pls Enter Numeric...' at Save + page errors from the racing postback).
        Setting .value via JS keeps the change event silent; the value stays in
        the DOM and is submitted together with the Save postback.
        """
        driver.execute_script("arguments[0].value = arguments[1];", element, str(value))

    def _read_save_result(self, driver):
        """Read the post-save state: success/error labels and validation spans.

        btsave is a VALIDATED submit (WebForm_PostBackOptions with group 'aa') —
        if validation fails the click does NOT postback and nothing is saved, so
        we must detect the visible validator spans instead of assuming success.
        Returns (status, detail); status is None when no verdict found yet.
        """
        def _txt(eid):
            try:
                return driver.find_element(By.ID, eid).get_attribute("innerText").strip()
            except Exception:
                return ""

        msg = _txt('ctl00_ContentPlaceHolder1_lblmsg')
        err = _txt('ctl00_ContentPlaceHolder1_lblError')
        err1 = _txt('ctl00_ContentPlaceHolder1_lbl_err1')

        valid_txt = ""
        for vid in ('ctl00_ContentPlaceHolder1_req_act',
                    'ctl00_ContentPlaceHolder1_Req_txtMat_UnitPrice',
                    'ctl00_ContentPlaceHolder1_Req_txtMat_Qty'):
            try:
                el = driver.find_element(By.ID, vid)
                if el.is_displayed() and el.get_attribute("innerText").strip():
                    valid_txt = el.get_attribute("innerText").strip()
                    break
            except Exception:
                pass

        if err:
            return "Failed", err
        if err1:
            return "Failed", err1
        if valid_txt:
            return "Failed", f"Validation blocked save: {valid_txt}"
        if msg:
            return "Success", msg
        return None, ""

    def _grid_activity_codes(self, driver, grid_id):
        """Grid me currently present ACT CODES — row-level, precise.

        Har data row ke 'Act Code' cell ka text nikalta hai (span id
        `..._lblActCode`). Substring match se better: activity NAAM ya partial
        code (e.g. ACT105 vs ACT1050) kabhi galat match nahi karta.
        """
        try:
            grid = driver.find_element(By.ID, grid_id)
        except NoSuchElementException:
            return []
        codes = []
        try:
            # Precise: har row ka Act Code span (id suffix _lblActCode)
            spans = grid.find_elements(By.XPATH, ".//span[contains(@id, 'lblActCode')]")
            for s in spans:
                txt = (s.get_attribute("innerText") or "").strip().upper()
                if txt:
                    codes.append(txt)
        except Exception:
            pass
        if not codes:
            # Fallback: Act Code column = 2nd cell (1-indexed) of har data row
            try:
                rows = grid.find_elements(By.XPATH, ".//tr")
                for r in rows:
                    tds = r.find_elements(By.XPATH, "./td")
                    if len(tds) >= 2:
                        txt = (tds[1].get_attribute("innerText") or "").strip().upper()
                        if txt and txt != "ACT CODE":
                            codes.append(txt)
            except Exception:
                pass
        return codes

    def _wait_for_grid_decided(self, driver, grid_id, timeout=15):
        """Grid ka content 'decided' hone tak wait karo — async UpdatePanel
        populate khatam hone ka.

        Work select ke baad activity section UpdatePanel ke andar hota hai —
        grid element page render hote hi DOM me aa jata hai, par uski content
        (existing activities) async postback se aati hai. Agar check isse pehle
        chale to grid khali/'No Activity Found' dikhata hai → bot duplicate add
        kar deta hai. Ye tab tak wait karta hai jab tak content stable na ho:
        ya to 'No Activity Found' (sach me khali), ya populated content jo 2
        consecutive reads me same rahe.

        Returns: grid ka innerText ('' = grid abhi bhi missing/khali).
        """
        last = None
        stable_since = time.time()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                grid = driver.find_element(By.ID, grid_id)
                inner = (grid.get_attribute("innerText") or "").strip()
            except Exception:
                inner = ""
            if not inner:
                # Element hai par abhi khali — async populate chal raha hai
                last = inner
                stable_since = time.time()
            elif "No Activity Found" in inner:
                return inner  # decided: sach me khali
            elif inner == last:
                if time.time() - stable_since >= 1.5:
                    return inner  # 2 reads same → populate khatam
            else:
                last = inner
                stable_since = time.time()
            time.sleep(0.8)
        # Timeout — best effort
        try:
            return (driver.find_element(By.ID, grid_id).get_attribute("innerText") or "").strip()
        except Exception:
            return ""

    def _activity_in_grid(self, driver, grid_id, activity_code):
        """Ground truth: did the activity row actually land in the grid?"""
        try:
            grid = driver.find_element(By.ID, grid_id)
            inner = grid.get_attribute("innerText") or ""
            if "No Activity Found" in inner:
                return False
        except NoSuchElementException:
            return False
        return any(c == activity_code for c in self._grid_activity_codes(driver, grid_id))

    def _process_single_work_key(self, driver, work_key, unit_price, quantity):
        """
        Processes a single work key on the IAY_Act_Mat.aspx page.

        Rewritten for the redesigned portal (verified against saved live pages):
          * FRESH PAGE LOAD per key, then the work key is TYPED into the search
            box (txtwrksearchkey) — the portal filters the work dropdown on that
            postback (saved page 'add act.htm' shows the search box holding the
            work's last-6 digits and the dropdown filtered to that one work).
            The postback is a FULL page reload, so we wait for the OLD dropdown
            to go stale instead of a fixed sleep (the fixed sleep was the flaky
            part in an earlier version).
          * If the search doesn't surface the work, we fall back to matching
            directly from the fresh page's dropdown, which pre-loads EVERY work
            of the block (saved page 'add activity.htm').
          * The work is picked by EXACT option match, never index 1.
          * The activity section is inside an UpdatePanel (async postbacks) —
            each action waits for the 'Please Wait...' overlay to settle.
          * btsave is a VALIDATED submit — the save verdict checks the error
            labels AND the visible validator spans, and falls back to verifying
            the activity actually appears in the grid (no more blind
            "Implicit Success").
          * Alert dismissal is wrapped in a blanket except — the old code only
            caught UnexpectedAlertPresentException, so a page WITHOUT an alert
            raised NoAlertPresentException and failed EVERY work key instantly.
        """
        wait = WebDriverWait(driver, 20)
        activity_code = config.ADD_ACTIVITY_CONFIG['defaults']['activity_code']
        url = self.resolve_portal_url(config.ADD_ACTIVITY_CONFIG["url"])
        work_name_dd_id = 'ctl00_ContentPlaceHolder1_ddlworkName'
        activity_dd_id = 'ctl00_ContentPlaceHolder1_ddlAct'
        grid_id = 'ctl00_ContentPlaceHolder1_grdDisplayAct'

        try:
            # Dismiss alerts if any (blanket except — 'no alert' is the normal case)
            try:
                driver.switch_to.alert.accept()
            except Exception:
                pass

            # --- 1. Fresh page load, then SEARCH the work key ---
            # The portal filters the work dropdown on the search postback (the
            # user expects to see the key typed in the box). The search box is
            # outside the UpdatePanel, so its postback is a FULL page reload.
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.ID, work_name_dd_id)))

            self.log_info(f"Searching for work key: {work_key}")
            search_input = wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_ContentPlaceHolder1_txtwrksearchkey')))
            self._scroll_to(driver, search_input)
            search_input.clear()
            search_input.send_keys(work_key)

            # Capture the OLD dropdown — it goes stale when the search postback
            # reloads the page (deterministic wait, not a fixed sleep).
            old_work_ddl = driver.find_element(By.ID, work_name_dd_id)
            search_input.send_keys(Keys.TAB)   # blur → onchange → __doPostBack
            try:
                WebDriverWait(driver, 15).until(EC.staleness_of(old_work_ddl))
            except TimeoutException:
                time.sleep(2)  # page didn't reload — continue anyway

            # --- 2. Select the EXACT matching work (never blind index 1) ---
            work_ddl_element = wait.until(EC.presence_of_element_located((By.ID, work_name_dd_id)))
            target_option = self._find_work_option(Select(work_ddl_element), work_key)

            if target_option is None:
                # Search didn't surface our work — reload fresh: the initial
                # page pre-loads EVERY work of the block into the dropdown, so
                # match directly from that full list.
                self.log_info("Work not found after search — reloading full list...")
                driver.get(url)
                work_ddl_element = wait.until(EC.presence_of_element_located((By.ID, work_name_dd_id)))
                target_option = self._find_work_option(Select(work_ddl_element), work_key)
                if target_option is None:
                    self._log_result(work_key, "Failed", "Work Key not found in dropdown.")
                    return

            self._scroll_to(driver, work_ddl_element)
            Select(work_ddl_element).select_by_value(target_option.get_attribute("value"))
            self.log_info("Work selected. Loading details...")

            # --- 3. Wait for the activity section to appear (full postback).
            # The work selection is a FULL page reload — first let the document
            # finish loading (readyState check), then wait for the activity
            # section. The find_elements poll can raise during navigation, so
            # retry instead of letting a mid-nav exception kill the key.
            self._wait_for_settle(driver, timeout=25)
            # Poll for the activity section with a blanket except — mid-navigation
            # WebDriverException/StaleElement errors are normal here, so ANY
            # failure just means "keep polling" rather than killing the key.
            section_ok = False
            deadline = time.time() + 25
            while time.time() < deadline:
                try:
                    if driver.find_elements(By.ID, activity_dd_id) or driver.find_elements(By.ID, grid_id):
                        section_ok = True
                        break
                except Exception:
                    pass
                time.sleep(0.8)
            if not section_ok:
                self._log_result(work_key, "Failed", "Activity section not found after selecting work.")
                return

            # Skip if this activity is already present on the work.
            # Grid ke content ke 'decided' hone ka wait (async UpdatePanel
            # populate) — warna grid khali dekh kar duplicate add ho jata.
            grid_inner = self._wait_for_grid_decided(driver, grid_id, timeout=15)
            if grid_inner:
                codes = self._grid_activity_codes(driver, grid_id)
                if any(c == activity_code for c in codes):
                    self.log_warning("Activity already exists. Skipping.")
                    self._log_result(work_key, "Skipped", "An activity is already present.")
                    return
                if codes:
                    self.log_info("Work has other activities; adding the default one.")
                else:
                    self.log_info("Grid present but no activity rows; proceeding to add.")
            else:
                self.log_info("No activity grid; proceeding to add.")

            # --- 4. Select the activity code (fires an async postback — settle) ---
            act_dd = wait.until(EC.element_to_be_clickable((By.ID, activity_dd_id)))
            self._scroll_to(driver, act_dd)
            Select(act_dd).select_by_value(activity_code)
            self._wait_for_settle(driver, action_name="Activity Select")

            # --- 5/6. Fill Unit Price & Quantity.
            # CRITICAL: both textboxes carry onchange=__doPostBack (they live
            # inside UpdatePanelMain). send_keys into price and then moving
            # focus to qty BLURS price → its change event fires → an async
            # postback re-renders the panel and WIPES both fields. Live symptom
            # of that race: 'Pls Enter Numeric...' shown at Save (fields came
            # back empty) plus page errors from the racing postback. So the
            # values are set via JS (no blur, no change event, no postback) and
            # are submitted together with the Save postback.
            price_input = wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_txtAct_UnitPrice')))
            self._js_set_value(driver, price_input, unit_price)
            qty_input = wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_txtAct_Qty')))
            self._js_set_value(driver, qty_input, quantity)
            time.sleep(0.3)

            # --- 7. Re-verify fields (cheap guard) then Save (validated submit) ---
            re_selected = False
            try:
                sel = Select(driver.find_element(By.ID, activity_dd_id))
                if (sel.first_selected_option.get_attribute("value") or "") != activity_code:
                    sel.select_by_value(activity_code)
                    re_selected = True
            except Exception:
                pass
            if re_selected:
                self._wait_for_settle(driver, action_name="Activity re-select")
            for eid, expected in (('ctl00_ContentPlaceHolder1_txtAct_UnitPrice', unit_price),
                                  ('ctl00_ContentPlaceHolder1_txtAct_Qty', quantity)):
                try:
                    el = driver.find_element(By.ID, eid)
                    if (el.get_attribute("value") or "").strip() != expected.strip():
                        self._js_set_value(driver, el, expected)
                except Exception:
                    pass

            self.log_info("Saving activity...")
            save_button = wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_ContentPlaceHolder1_btsave')))
            self._scroll_to(driver, save_button)
            driver.execute_script("arguments[0].click();", save_button)
            self._wait_for_settle(driver, timeout=25, action_name="Save")

            # --- 8. Check Result (labels → validation spans → grid ground truth) ---
            outcome = None
            detail = ""
            for _ in range(3):
                outcome, detail = self._read_save_result(driver)
                if outcome:
                    break
                time.sleep(1.5)

            if outcome is None:
                if self._activity_in_grid(driver, grid_id, activity_code):
                    outcome, detail = "Success", "Activity saved (verified in grid)."
                else:
                    outcome, detail = "Failed", "Save completed but no confirmation found."

            self._log_result(work_key, outcome, detail)

        except Exception as e:
            self._log_result(work_key, "Failed", f"Error: {str(e).splitlines()[0]}")