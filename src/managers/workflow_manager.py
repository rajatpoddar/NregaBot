import threading
import time
from tkinter import messagebox
import tkinter
from src.utils import get_logger

logger = get_logger()

class WorkflowManager:
    def __init__(self, app):
        self.app = app
        self.pipeline_queue = []
        self.is_pipeline_running = False
        # Central execution queue — ab ye Macro Manager tab par nahi, YAHAN
        # rehta hai. Koi bhi automation tab 'Add to Queue' se item add kar
        # sakta hai, aur tab destroy ho jane par bhi queue safe rehta hai.
        self.queue_items = []

    # --- HELPER: LOGGING ---
    def _log(self, macro_tab, msg, level="info"):
        """Logs message to the Macro Manager's log display."""
        if macro_tab and hasattr(macro_tab, 'log_display'):
            self.app.log_message(macro_tab.log_display, msg, level)

    # --- HELPER: WAITS ---
    def _wait_and_execute(self, tab_name, action_callback):
        if tab_name in self.app.tab_instances:
            self.app.after(500, action_callback)
        else:
            self.app.after(100, lambda: self._wait_and_execute(tab_name, action_callback))

    def _wait_for_automation_finish(self, key, timeout=900, macro_tab=None):
        """Blocks thread until automation key is active AND THEN clears."""
        start = time.time()
        
        # 1. Wait for automation to START
        self._log(macro_tab, f"Waiting for '{key}' automation to start...")
        automation_started = False
        
        # Wait loop (30s) to detect start
        for _ in range(30): 
            if key in self.app.active_automations:
                automation_started = True
                break
            time.sleep(1)
        
        if not automation_started:
            # DEBUG INFO: Show what is actually running
            running_keys = list(self.app.active_automations)
            self._log(macro_tab, f"Error: Automation '{key}' did not start. Running: {running_keys}", "error")
            return False

        self._log(macro_tab, f"Automation '{key}' detected running... Waiting for completion.")
        
        # 2. Wait for automation to FINISH
        while key in self.app.active_automations:
            if self.app.stop_events.get("macro") and self.app.stop_events["macro"].is_set(): 
                self._log(macro_tab, "Macro stopped by user.", "warning")
                return False
            
            if time.time() - start > timeout: 
                self._log(macro_tab, f"Timeout: Automation '{key}' took too long.", "error")
                return False
            time.sleep(1)
            
        self._log(macro_tab, f"Automation '{key}' finished.")
        return True

    def _ensure_automation_stopped(self, key, *, max_polls: int = 10):
        """Ensures a specific automation is definitely stopped before starting.

        Polls ``self.app.active_automations`` until the given ``key`` is no
        longer present, up to ``max_polls`` iterations. Each iteration
        sleeps approximately one second (``time.sleep(1)``), so wall-clock
        time may exceed ``max_polls`` seconds on a slow host. This is **not**
        a strict wall-clock timeout — it is a polling-iteration cap.

        Returns ``None`` regardless of whether the key disappears; the
        caller is expected to proceed either way.

        Args:
            key: Automation key to wait for (e.g. ``"demand"``).
            max_polls: Maximum number of polling iterations. Must be ``>= 1``.
                Default is ``10`` (preserves prior hardcoded behavior).
        """
        if max_polls < 1:
            raise ValueError("max_polls must be >= 1")
        if key in self.app.active_automations:
            self.app.after(0, self.app.set_status, f"Waiting for {key} to clear...")
            for _ in range(max_polls):
                if key not in self.app.active_automations: break
                time.sleep(1)

    # --- HELPER: DATA SCRAPING ---
    def _scrape_workcodes_from_active_tab(self, tab_name):
        codes = []
        try:
            tab = self.app.tab_instances.get(tab_name)
            if hasattr(tab, 'get_clean_workcodes'):
                return tab.get_clean_workcodes()

            if tab and hasattr(tab, 'results_tree'):
                time.sleep(1) 
                for child in tab.results_tree.get_children():
                    vals = tab.results_tree.item(child)['values']
                    for v in vals:
                        s = str(v)
                        if "/" in s and len(s) > 10: 
                            codes.append(s)
                            break
        except Exception as e:
            print(f"Scrape Error: {e}")
        return list(set(codes))

    # --- HELPER: GENERIC RUNNER ---
    def _set_target_on_tab(self, tab, target, entry_attr="panchayat_entry", sync=False):
        """
        Set the panchayat/agency name on a tab.

        Some tabs use a CTkEntry named *_entry (e.g. `panchayat_entry`), others
        use a CTkOptionMenu + StringVar (e.g. `panchayat_var`/`panchayat_menu`
        in Muster Roll Gen, MR Tracking, Wagelist Gen, Job Card Verify, ABPS
        Verify). This helper tries the entry widget first, then falls back to the
        matching StringVar / option menu so macros work on every tab.

        `sync=True` is for callers already running on the main thread (e.g. inside
        an `after(0, ...)` callback) that must read the value immediately after —
        otherwise the update is scheduled via `after(...)`.
        """
        entry_widget = getattr(tab, entry_attr, None)
        if not entry_widget and hasattr(tab, "agency_entry"):
            entry_widget = tab.agency_entry

        if entry_widget is not None:
            if sync:
                entry_widget.delete(0, "end")
                entry_widget.insert(0, target)
            else:
                self.app.after(0, lambda: entry_widget.delete(0, "end"))
                self.app.after(100, lambda: entry_widget.insert(0, target))
            return

        # Fall back to a matching StringVar / option menu (case-insensitive match
        # on existing dropdown options so the stored panchayat casing is kept).
        setter_var = None
        var_attr = entry_attr.replace("_entry", "_var")
        menu_attr = entry_attr.replace("_entry", "_menu")
        for attr_name in (var_attr, menu_attr, "panchayat_var", "agency_var"):
            candidate = getattr(tab, attr_name, None)
            if candidate is not None and hasattr(candidate, "set"):
                setter_var = candidate
                break

        if setter_var is not None:
            def _set_target():
                try:
                    if hasattr(setter_var, "cget"):
                        for v in list(setter_var.cget("values")):
                            if str(v).strip().lower() == str(target).strip().lower():
                                setter_var.set(v)
                                return
                    setter_var.set(target)
                except Exception as e:
                    logger.debug("WorkflowManager: failed to set target %s on %s: %s", target, type(tab).__name__, e)
            if sync:
                _set_target()
            else:
                self.app.after(0, _set_target)

    def _run_generic_task(self, tab_name, target, automation_key, entry_attr="panchayat_entry", macro_tab=None):
        self.app.after(0, self.app.set_status, f"Macro: Starting {tab_name} for {target}...")
        self._log(macro_tab, f"Switching to {tab_name} tab...")
        
        self.app.after(0, lambda: self.app.show_frame(tab_name))
        time.sleep(1.5) 
        
        tab = self.app.tab_instances.get(tab_name)
        if not tab: raise Exception(f"Tab {tab_name} not found")

        self._ensure_automation_stopped(automation_key)
        
        # Set the panchayat/agency (supports both entry widgets and option menus).
        # Empty target (bina panchayat wale tabs) set nahi karte — tab apna
        # default UI use karta hai.
        if target:
            self._set_target_on_tab(tab, target, entry_attr)

        # 2. Trigger Staff Auto-fill (Fix for Muster Roll Gen)
        # ERROR FIXED HERE: Changed 'mr_gen' to 'muster'
        if automation_key == "muster" and hasattr(tab, '_auto_fill_staff'):
            self._log(macro_tab, f"Updating Technical Staff for {target}...")
            self.app.after(500, lambda: tab._auto_fill_staff())
        
        self._log(macro_tab, f"Starting automation '{automation_key}' for {target}...")
        
        # 3. Start Automation
        # P1: Removed unnecessary update_idletasks — the 3s delay before
        # start_automation gives the event loop plenty of time to flush
        # pending UI updates naturally.
        self.app.after(3000, lambda: tab.start_automation())
        
        return self._wait_for_automation_finish(automation_key, macro_tab=macro_tab)

    # --- SAFE MACRO TAB UI CALLS (background queue ke liye) ---
    def _macro_call(self, macro_tab, method, *args):
        """macro_tab par safe UI call — jab queue background me chale (Macro
        Manager tab loaded nahi / destroy ho chuka) to silently skip karo."""
        try:
            if macro_tab is not None and hasattr(macro_tab, method):
                alive = getattr(macro_tab, '_is_alive', lambda: True)
                if alive():
                    getattr(macro_tab, method)(*args)
        except Exception:
            pass

    def _update_item_status(self, item_id, status, msg="", macro_tab=None):
        """Queue item ka status update — hamesha item dict me (central store),
        aur Macro Manager tab loaded + alive ho to tree me bhi."""
        for item in self.queue_items:
            if str(item.get('id')) == str(item_id):
                item['status'] = status
                item['msg'] = msg
                break
        self._macro_call(macro_tab, "update_item_status", item_id, status, msg)

    # --- CORE: GLOBAL QUEUE PROCESSOR ---
    def process_global_queue(self, macro_tab=None):
        self.app.after(0, lambda m=macro_tab: self._macro_call(m, "set_ui_state", True))
        self.app.play_sound("macro_start")

        try:
            for item in self.queue_items:
                if self.app.stop_events["macro"].is_set(): break
                if item['status'] == 'Success': continue 

                # UI Update
                self._update_item_status(item['id'], "Running", "Starting...", macro_tab)
                self._log(macro_tab, f"--- Processing Item #{item['id']}: {item['type']} ---", "info")
                
                success = False
                msg = "Finished"

                try:
                    task_type = item['type']
                    target = item.get('target', '')

                    # === 0. TAB-QUEUED ITEMS (Add-to-Queue from any automation tab) ===
                    # 'Add to Queue' se aaye items me tab_name + automation_key
                    # hota hai — generic runner unhe directly chala deta hai.
                    # Ye branch PEHLE hai kyunki display name (type) kisi
                    # existing macro task string se collide kar sakta hai.
                    if item.get('tab_name') and item.get('automation_key'):
                        success = self._run_generic_task(
                            item['tab_name'], target, item['automation_key'], macro_tab=macro_tab)
                        msg = f"Finished: {item['type']}" if success else f"Failed: {item['type']}"

                    # === 1. WAGELIST GEN + AUTO SEND ===
                    elif "Wagelist Gen" in task_type or task_type == 'wagelist_gen_send':
                        self._log(macro_tab, "Step 1: Generating Wagelists...")
                        success_gen = self._run_generic_task("Gen Wagelist", target, "gen", entry_attr="agency_entry", macro_tab=macro_tab)
                        
                        if success_gen:
                            self._log(macro_tab, "Generation complete. Checking for auto-send handoff...")
                            time.sleep(3) 
                            if "send" in self.app.active_automations:
                                self._log(macro_tab, "Step 2: Sending Wagelists (Automation detected)...")
                                success_send = self._wait_for_automation_finish("send", timeout=1200, macro_tab=macro_tab)
                                msg = "Wagelist Generated & Sent" if success_send else "Generation OK, Sending Failed"
                                success = success_send
                            else:
                                success = True; msg = "Wagelist Generated (Nothing to send?)"
                        else:
                            success = False; msg = "Generation Failed"

                    # === 2. MR TRACKING CYCLES ===
                    elif "MR Tracking" in task_type or "mr_track" in task_type:
                        dest_tab = ""
                        wait_key = ""
                        if "MR Payment" in task_type or task_type == 'mr_track_payment': dest_tab = "MR Payment"; wait_key = "msr"
                        elif "eMB Entry" in task_type or task_type == 'mr_track_emb': dest_tab = "eMB Entry"; wait_key = "mb_entry"
                        elif "Zero MR" in task_type or task_type == 'mr_track_zero': dest_tab = "Zero MR"; wait_key = "zero_mr"

                        self._log(macro_tab, "Step 1: Running MR Tracking...")
                        self._update_item_status(item['id'], "Running", "Tracking...", macro_tab)
                        self.app.after(0, lambda: self.app.show_frame("MR Tracking"))
                        time.sleep(2.0)
                        track_tab = self.app.tab_instances.get("MR Tracking")
                        
                        if hasattr(self, '_ensure_automation_stopped'): self._ensure_automation_stopped("mr_tracking")

                        def _configure_tracking():
                            if hasattr(track_tab, 'pending_only_var'): track_tab.pending_only_var.set(0)
                            if hasattr(track_tab, 'zero_mr_filter_var'): track_tab.zero_mr_filter_var.set(0)
                            if hasattr(track_tab, 'abps_pending_var'): track_tab.abps_pending_var.set(0)
                            
                            if dest_tab == "Zero MR":
                                if hasattr(track_tab, 'zero_mr_filter_var'): track_tab.zero_mr_filter_var.set(1)
                            else:
                                if hasattr(track_tab, 'pending_only_var'): track_tab.pending_only_var.set(1)
                            
                            if hasattr(track_tab, '_on_filter_check_changed'): track_tab._on_filter_check_changed()
                            p_name = target if target else item.get('panchayat', '')
                            # MR Tracking uses panchayat_var/panchayat_menu (not a
                            # panchayat_entry widget) — use the shared setter.
                            # sync=True because this callback runs on the main
                            # thread and start_automation() reads the value next.
                            self._set_target_on_tab(track_tab, p_name, "panchayat_entry", sync=True)
                            track_tab.start_automation()

                        self.app.after(0, _configure_tracking)
                        if not self._wait_for_automation_finish("mr_tracking", timeout=900, macro_tab=macro_tab):
                            raise Exception("MR Tracking Failed/Timeout")

                        self._log(macro_tab, "Step 2: Scrapping Workcodes...")
                        codes = self._scrape_workcodes_from_active_tab("MR Tracking")
                        
                        if not codes:
                            msg = "No Data Found in Tracking"; self._log(macro_tab, "No workcodes found.", "warning"); success = False 
                        else:
                            self._log(macro_tab, f"Step 3: Handoff to {dest_tab} ({len(codes)} codes)...")
                            self._update_item_status(item['id'], "Running", f"Running {dest_tab}...", macro_tab)
                            p_name = target if target else item.get('panchayat', '')

                            if dest_tab == "Zero MR": self.switch_to_zero_mr_tab_with_data(codes) 
                            elif dest_tab == "MR Payment": self.switch_to_msr_tab_with_data(codes, p_name)
                            else: self.switch_to_emb_entry_with_data(codes, p_name)
                            
                            if self._wait_for_automation_finish(wait_key, timeout=1200, macro_tab=macro_tab):
                                success = True; msg = f"Processed {len(codes)} codes"
                            else:
                                msg = f"{dest_tab} Timeout"; success = False

                    # === 3. OTHER GENERIC TASKS ===
                    elif "Verify Job Card" in task_type or task_type == 'jobcard_verify':
                        p_name = target if target else item.get('panchayat', '')
                        success = self._run_generic_task("Job Card Verify", p_name, "jobcard_verify", macro_tab=macro_tab)
                    
                    elif "Verify ABPS" in task_type:
                        success = self._run_generic_task("Verify ABPS", target, "verify_abps", macro_tab=macro_tab)
                    
                    elif "Generate MR" in task_type:
                        success = self._run_generic_task("Muster Roll Gen", target, "muster", entry_attr="panchayat_entry", macro_tab=macro_tab)

                    # === 4. NEW: BULK DEMAND (UPDATED) ===
                    elif task_type == 'bulk_demand':
                        self._log(macro_tab, "Step 1: Starting Demand Automation...")
                        # Pass macro_tab here to avoid NoneType error in logging
                        self.run_bulk_demand_sequence(item, macro_tab)
                        success = True
                        msg = "Demand & Allocation Done"

                except Exception as e:
                    msg = str(e); self._log(macro_tab, f"Exception in task: {e}", "error"); success = False

                self._update_item_status(item['id'], "Success" if success else "Failed", msg, macro_tab)
                self._log(macro_tab, f"Task finished: {msg}", "success" if success else "error")
                self.app.after(0, self.app.set_status, f"Macro: {task_type} - {msg}")
                time.sleep(3)

        except Exception as e:
            self.app.after(0, messagebox.showerror, "Macro Error", str(e))
        finally:
            self.app.after(0, lambda m=macro_tab: self._macro_call(m, "set_ui_state", False))
            self.app.after(0, self.app.set_status, "Macro Queue Finished")
            self.app.play_sound("macro_finish")
            self._log(macro_tab, ">>> Macro Queue Execution Finished.")

    # --- HANDOFF METHODS ---
    def switch_to_msr_tab_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("MR Payment")
        def _action():
            tab = self.app.tab_instances["MR Payment"]
            final_data = workcodes
            if isinstance(workcodes, list): final_data = "\n".join(workcodes)
            tab.load_data_from_mr_tracking(final_data, panchayat_name)
            self.app.after(3000, lambda: tab.start_automation())
        self._wait_and_execute("MR Payment", _action)

    def switch_to_emb_entry_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("eMB Entry")
        def _action():
            tab = self.app.tab_instances["eMB Entry"]
            final_data = workcodes
            if isinstance(workcodes, list): final_data = "\n".join(workcodes)
            tab.load_data_from_mr_tracking(final_data, panchayat_name)
            self.app.after(3000, lambda: tab.start_automation())
        self._wait_and_execute("eMB Entry", _action)

    def switch_to_zero_mr_tab_with_data(self, data_list):
        self.app.show_frame("Zero MR")
        def _action():
            tab = self.app.tab_instances["Zero MR"]
            if hasattr(tab, 'load_data_from_mr_tracking'):
                tab.load_data_from_mr_tracking(data_list)
                self.app.after(3000, lambda: tab.start_automation())
        self._wait_and_execute("Zero MR", _action)

    def send_wagelist_data_and_switch_tab(self, wagelists, auto_start=False):
        self.app.show_frame("Send Wagelist")
        def _action():
            tab = self.app.tab_instances["Send Wagelist"]
            tab.populate_wagelist_data(wagelists)
            if auto_start and hasattr(tab, 'start_automation'):
                self.app.after(2000, tab.start_automation)
        self._wait_and_execute("Send Wagelist", _action)

    def run_work_allocation_from_demand(self, panchayat_name, work_key):
        # FIX: Changed "Allocation" to "Work Allocation" to match the actual tab name
        target_tab = "Work Allocation"
        
        self.app.show_frame(target_tab)
        
        def _action():
            # Ensure the tab instance exists before calling the method
            if target_tab in self.app.tab_instances:
                self.app.tab_instances[target_tab].run_automation_from_demand(panchayat_name, work_key)
            else:
                print(f"Error: Tab '{target_tab}' not found in tab_instances.")

        self._wait_and_execute(target_tab, _action)

    def switch_to_if_edit_with_data(self, data):
        self.app.show_frame("IF Editor")
        def _action():
            self.app.tab_instances["IF Editor"].load_data_from_wc_gen(data)
            self.app.play_sound("success")
        self._wait_and_execute("IF Editor", _action)

    def switch_to_mr_fill_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("MR Fill")
        def _action():
            self.app.tab_instances["MR Fill"].load_data_from_dashboard(workcodes, panchayat_name)
        self._wait_and_execute("MR Fill", _action)

    def switch_to_mr_tracking_for_abps(self, location_data=None):
        """
        Switches to MR Tracking tab, CLEARS previous filters, sets ABPS pending filter,
        and populates location data.
        """
        self.app.show_frame("MR Tracking")
        
        # We need to wait for the frame to actually load
        def _action():
            tab = self.app.tab_instances.get("MR Tracking")
            if not tab: return

            # --- 1. Clear/Reset Other Checkboxes/Filters ---
            vars_to_clear = [
                'pending_only_var', 
                'zero_mr_filter_var'
            ]
            
            for var_name in vars_to_clear:
                if hasattr(tab, var_name):
                    try: getattr(tab, var_name).set(0)
                    except Exception as e: logger.debug("Failed to clear var %s: %s", var_name, e)

            # --- 2. Set "Show Pending for ABPS" Checkbox ---
            if hasattr(tab, 'abps_pending_var'):
                try:
                    tab.abps_pending_var.set(1)
                    # Trigger visual update (checkbox state change)
                    if hasattr(tab, '_on_filter_check_changed'):
                        tab._on_filter_check_changed()
                except Exception:
                    pass

            # --- 3. Handle Autocomplete Fields ---
            def update_field(entry_attr, value):
                if hasattr(tab, entry_attr) and value:
                    widget = getattr(tab, entry_attr)
                    # Check if it is an AutocompleteEntry or CTkEntry
                    if hasattr(widget, 'delete') and hasattr(widget, 'insert'):
                        widget.configure(state="normal") # Ensure it's editable
                        widget.delete(0, 'end')
                        widget.insert(0, value)
            
            if location_data:
                update_field('district_entry', location_data.get('district'))
                update_field('block_entry', location_data.get('block'))
                update_field('panchayat_entry', location_data.get('panchayat'))

        self._wait_and_execute("MR Tracking", _action)

    def switch_to_duplicate_mr_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("Duplicate MR Print")
        def _action():
            self.app.tab_instances["Duplicate MR Print"].load_data_from_report(workcodes, panchayat_name)
        self._wait_and_execute("Duplicate MR Print", _action)

    def run_bulk_demand_sequence(self, item, macro_tab=None):
        """
        Executes Demand Automation using provided CSV and Panchayat, 
        then automatically handles Allocation via the existing hook.
        """
        panchayat = item['panchayat']
        filepath = item['filepath']
        
        # Safe logging to Macro Tab
        if macro_tab:
            self._log(macro_tab, f"Starting Bulk Demand for: {panchayat}...", "info")
        else:
            print(f"Starting Bulk Demand for: {panchayat}")
        
        # 1. Switch to Demand Tab
        self.app.show_frame("Demand")
        
        def _start_demand():
            if "Demand" in self.app.tab_instances:
                tab = self.app.tab_instances["Demand"]
                
                # Inject Data
                if hasattr(tab, 'set_automation_inputs'):
                    tab.set_automation_inputs(panchayat, filepath)
                
                # Start Automation
                if hasattr(tab, 'start_automation'):
                    tab.start_automation()
                else:
                    raise Exception("Demand tab missing start_automation method.")
            else:
                raise Exception("Demand tab not found.")

        self._wait_and_execute("Demand", _start_demand)
        
        # 2. Wait for Demand to Finish
        self._wait_for_automation_finish("demand")
        
        # 3. Handle Work Allocation (Optional Wait)
        time.sleep(5) 
        if "work_allocation" in self.app.active_automations:
             if macro_tab: self._log(macro_tab, "Allocation started, waiting to finish...")
             self._wait_for_automation_finish("work_allocation")
        
        time.sleep(2)