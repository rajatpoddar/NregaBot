# app_automation.py

# ============================================================================
# IMPORTS
# ============================================================================

import threading
import time
import subprocess
import socket
import os
import json
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional

from tkinter import messagebox

import requests

from src import config
from src.utils import get_logger, get_config

logger = get_logger()

# Friendly display names for automation keys shown in the footer's
# "▶ Running: ..." indicator. Keys are the automation_key values that
# tabs register via start_automation_thread().
AUTOMATION_DISPLAY_NAMES = {
    "pending_bills": "Pending Bills",
    "mr_tracking": "MR Tracking",
    "issued_mr_report": "Issued MR",
    "fto_gen": "FTO Generation",
    "fto_gen_del": "FTO Delete",
    "nmms_attendance": "NMMS Attendance",
    "work_allocation": "Work Allocation",
    "gen": "Wagelist",
    "mr_fill": "MR Fill",
    "emb_verify": "eMB Verify",
    "material_entry": "Material Entry",
    "mis_reports": "MIS",
    "physical_complete": "Physical Complete",
    "sad_update_status": "SAD Update",
    "add_activity": "Add Activity",
    "del_demand": "Delete Demand",
    "sad_auto": "Sarkar Aapke Dwar",
    "mb_entry": "MB Entry",
    "zero_mr": "Zero MR",
    "delete_applicant": "Delete Applicant",
    "demand": "Demand",
    "resend_wg": "Resend Rejected Wagelist",
    "update_estimate": "Update Estimate",
    "wc_gen": "Work Code Generation",
    "send": "Wagelist Send",
    "duplicate_mr": "Duplicate MR",
    "social_audit_respond": "Social Audit",
    "muster": "Muster Roll",
    "mate_mr": "Mate MR",
    "pdf_merger": "PDF Merger",
    "msr": "MR Payment",
    "dashboard_report": "Dashboard Report",
    "abps_verify": "ABPS Verify",
    "if_edit": "IF Edit",
    "jc_verify": "Jobcard Verify",
    "jobcard_verify": "Jobcard Verify",
    "verify_abps": "Verify ABPS",
    "del_work_alloc": "Delete Work Allocation",
    "macro": "Macro",
    "scheme_closing": "Scheme Closing",
    "ekyc_report": "eKYC Report",
}


def _automation_display_name(key: str) -> str:
    """Return a friendly name for an automation key, falling back to a
    prettified version of the raw key."""
    return AUTOMATION_DISPLAY_NAMES.get(key, key.replace("_", " ").title())


class AutomationMixin:
    """Mixin class containing browser and automation dispatch methods.

    Depends on these attributes being set by the host class (NregaBotApp):
        - self.browser_manager
        - self.driver
        - self.active_browser
        - self.stop_events
        - self.history_manager
        - self.automation_threads
        - self.active_automations
        - self.minimize_var
        - self.services
    """

    # ============================================================================
    # BROWSER & AUTOMATION METHODS
    # ============================================================================

    def get_driver(self) -> Any:
        driver = self.browser_manager.get_driver()
        if driver:
            self.app_state.driver = self.browser_manager.driver
            self.app_state.active_browser = self.browser_manager.active_browser
        return driver

    def launch_chrome_detached(self, target_urls: Optional[List[str]] = None) -> None:
        self.browser_manager.launch_chrome_detached(target_urls)

    def launch_edge_detached(self) -> None:
        self.browser_manager.launch_edge_detached()

    def launch_firefox_managed(self) -> None:
        self.browser_manager.launch_firefox_managed()

    def start_automation_thread(self, key, target, args=()):
        if self.app_state.automation_threads.get(key) and self.app_state.automation_threads[key].is_alive():
            self.play_sound("error")
            messagebox.showwarning("Busy", "Task running")
            return

        self.play_sound("start")
        self.history_manager.increment_usage(key)
        self.prevent_sleep()
        self.app_state.active_automations.add(key)
        self.app_state.stop_events[key] = threading.Event()
        self._update_emergency_stop_btn()
        self._update_running_automation_indicator()

        if self.app_state.minimize_var.get() and self.app_state.driver:
            try:
                self.app_state.driver.minimize_window()
                self.show_toast("Running in Background (Minimized)", "info")
                if config.OS_SYSTEM == "Darwin" and self.app_state.active_browser == "chrome":
                    try:
                        subprocess.run([
                            "osascript", "-e",
                            'tell application "Google Chrome" to set minimized of windows to true'
                        ])
                    except Exception:
                        pass
            except Exception:
                pass

        # Mark the tab as having run an automation — show_frame won't destroy it
        tab_instance = getattr(target, '__self__', None)
        if tab_instance is not None:
            tab_instance._has_automated = True
            # Record start time on the tab instance for duration tracking
            tab_instance.activity_start_time = time.time()
            # Refresh activity data from widgets before automation starts
            if hasattr(tab_instance, '_refresh_activity_data'):
                tab_instance._refresh_activity_data()
            # Log automation start
            panchayat = getattr(tab_instance, 'activity_panchayat', '')
            village = getattr(tab_instance, 'activity_village', '')
            self.history_manager.log_automation_start(
                automation_key=key,
                panchayat=panchayat,
                village=village,
                details=f"Started from tab"
            )

        def wrapper():
            # Fresh run: forget any browser choice left over from a previous
            # run so this automation gets to pick (if multiple browsers).
            try:
                self.browser_manager.clear_thread_choice()
            except Exception:
                pass
            try:
                target(*args)
            except Exception as e:
                # Safety net: never let an uncaught automation exception crash
                # the app (e.g. the user closed the browser tab mid-run).
                try:
                    em = str(e).lower()
                    if ("no such window" in em or "target window already closed" in em
                            or "web view not found" in em or "invalid session id" in em):
                        self.after(0, lambda: (
                            self.show_toast("🛑 Browser tab was closed — automation stopped.", "warning", duration=5000),
                            messagebox.showwarning(
                                "Browser Closed",
                                "Automation stopped because the browser tab was closed.\n\n"
                                "Relaunch the browser and run again."
                            )
                        ))
                    else:
                        logger.error("Unhandled automation error in %s: %s", key, e, exc_info=True)
                except Exception:
                    logger.error("Failed to report automation error for %s: %s", key, e)
            finally:
                # Run finished: clear the per-run browser choice so the NEXT
                # automation asks the user again instead of silently reusing it.
                try:
                    self.browser_manager.clear_thread_choice()
                except Exception:
                    pass
                # Calculate duration before cleanup
                end_time = time.time()
                tab_instance = getattr(target, '__self__', None)
                duration = 0.0
                if tab_instance is not None:
                    if hasattr(tab_instance, 'activity_start_time') and tab_instance.activity_start_time:
                        duration = end_time - tab_instance.activity_start_time
                    # Refresh details from results_tree
                    if hasattr(tab_instance, '_refresh_activity_data'):
                        tab_instance._refresh_activity_data()
                
                # Access the tab instance via target.__self__ (bound method)
                # and clean up its driver if it created one.
                # This is race-condition-free because each thread's closure
                # captures the correct tab instance — unlike a shared dict
                # where a new tab could overwrite the old driver reference.
                if tab_instance is not None and hasattr(tab_instance, 'driver'):
                    try:
                        if tab_instance.driver is not None:
                            tab_instance.driver.quit()
                    except Exception:
                        pass
                    tab_instance.driver = None
                self.after(0, lambda k=key, dur=duration, inst=tab_instance: self.on_automation_finished(k, dur, inst))

        t = threading.Thread(target=wrapper, daemon=True)
        self.app_state.automation_threads[key] = t
        t.start()

        # ── Tab marker keeper ────────────────────────────────────────────────
        # Re-applies the "🤖 NREGA-BOT Running" title + red-dot favicon on the
        # first browser tab while the automation runs (page navigations wipe
        # the marker, so it is re-applied periodically). Lets the user see at a
        # glance which tab is in use and avoids accidentally closing it.
        def _marker_keeper(worker_thread: threading.Thread) -> None:
            marker_session = None
            owns_session = False
            try:
                while (worker_thread.is_alive()
                       and key in self.app_state.active_automations):
                    if marker_session is None:
                        marker_session, owns_session = self.browser_manager.connect_driver_no_dialog()
                    if marker_session is not None:
                        try:
                            if marker_session.window_handles:
                                if owns_session:
                                    # Separate keeper session (chrome/edge): safe
                                    # to switch to the resolved automation tab.
                                    target = self.browser_manager.resolve_automation_tab(marker_session)
                                    if target:
                                        marker_session.switch_to.window(target)
                                # Shared in-app Firefox driver: do NOT switch
                                # windows — the automation may be working in a
                                # popup, and yanking the active window here
                                # would break it. Just paint the marker on the
                                # window the automation is currently using.
                                self.browser_manager.apply_automation_marker(marker_session)
                        except Exception:
                            marker_session = None
                            owns_session = False
                    time.sleep(2)
            finally:
                if owns_session and marker_session is not None:
                    try:
                        marker_session.quit()
                    except Exception:
                        pass

        threading.Thread(target=_marker_keeper, args=(t,), daemon=True).start()

    def on_automation_finished(self, key, duration=0.0, tab_instance=None):
        if key in self.app_state.active_automations:
            self.app_state.active_automations.remove(key)
        self._update_running_automation_indicator()
        self.set_status("Finished")
        self.after(5000, lambda: self.set_status("Ready"))
        if not self.app_state.active_automations:
            self.allow_sleep()
            self._update_emergency_stop_btn()
        
        # ── Log activity finish ──
        # Initialize defaults before any try blocks to prevent NameError 
        panchayat = ''
        village = ''
        details = ''
        status = 'success'
        
        if tab_instance:
            try:
                panchayat = getattr(tab_instance, 'activity_panchayat', '')
                village = getattr(tab_instance, 'activity_village', '')
                details = getattr(tab_instance, 'activity_details', '')
                
                # Determine status from stop_event
                stop_event = self.app_state.stop_events.get(key)
                status = "stopped" if (stop_event and stop_event.is_set()) else "success"
                
                self.history_manager.log_automation_finish(
                    automation_key=key,
                    panchayat=panchayat,
                    village=village,
                    status=status,
                    duration_seconds=duration,
                    details=details
                )
            except Exception as e:
                logger.error(f"Failed to log automation finish for {key}: {e}")
            
            # ── Show in-app toast notification (professional) ──
            try:
                if tab_instance is not None and hasattr(tab_instance, 'show_automation_notification'):
                    tab_instance.show_automation_notification(status=status)
            except Exception as e:
                logger.debug(f"Failed to show notification for {key}: {e}")

            # ── Notification + Sync (safely wrapped) ──
            try:
                # ── WhatsApp Notification (if enabled) ──
                self._send_whatsapp_notification_if_enabled(
                    key, panchayat, status, duration, details
                )
                
                # ── WhatsApp Excel File send (if enabled) ──
                self._send_excel_whatsapp_notification(key, status, tab_instance)
                
                # ── Sync activity log to server (Phase 2) ──
                lic = getattr(self.app_state, 'license_info', {}) or {}
                server_license_key = lic.get('key', '')
                self.history_manager.sync_activity_log_to_server(license_key=server_license_key)
            except Exception as e:
                logger.error(f"Failed to send notification/sync for {key}: {e}")

    def _send_whatsapp_notification_if_enabled(self, key, panchayat, status, duration, details):
        """
        WhatsApp notification bhejega agar user ne settings mein enable kiya hai.
        Notification sirf tab bheja jayega jab automation SUCCESS ya FAILED ho
        (stopped/error par nahi bhejenge to avoid spam).
        """
        if status not in ("success", "failed"):
            return
        
        # Check if WhatsApp notification is enabled in config
        whatsapp_enabled = get_config("whatsapp_automation_notify", False)
        if not whatsapp_enabled:
            return
        
        # Check if license_info has mobile number
        lic = getattr(self.app_state, 'license_info', {})
        if not lic or not lic.get('user_mobile'):
            return
        
        user_mobile = lic.get('user_mobile', '')
        license_key = lic.get('key', '')
        if not user_mobile or not license_key:
            return
        
        # Build summary message
        duration_str = f"{duration:.0f}s" if duration < 60 else f"{duration/60:.1f}m"
        emoji = "✅" if status == "success" else "⚠️"
        
        summary = f"{emoji} Automation Complete\n"
        summary += f"📋 Task: {key.replace('_', ' ').title()}\n"
        if panchayat:
            summary += f"📍 Panchayat: {panchayat}\n"
        summary += f"⏱ Duration: {duration_str}\n"
        if details:
            summary += f"📊 Result: {details}\n"
        
        # Send to server in background thread
        def _send():
            try:
                server_url = config.LICENSE_SERVER_URL
                if not server_url:
                    return
                payload = {
                    "license_key": license_key,
                    "user_mobile": user_mobile,
                    "automation_name": key,
                    "panchayat": panchayat,
                    "status": status,
                    "duration_seconds": duration,
                    "summary": summary,
                    "details": details,
                }
                resp = requests.post(
                    f"{server_url}/api/whatsapp-notify-automation",
                    json=payload,
                    timeout=10
                )
                if resp.status_code in (200, 201):
                    logger.info("WhatsApp notification sent for %s", key)
                else:
                    logger.debug("WhatsApp notification failed: %s", resp.text)
            except Exception as e:
                logger.debug("WhatsApp notification error: %s", e)
        
        threading.Thread(target=_send, daemon=True).start()

    def _send_excel_whatsapp_notification(self, key, status, tab_instance=None):
        """
        Automation finish par Excel file ko nrega-server par upload karta hai,
        aur server Evolution API ke through WhatsApp pe document bhejta hai.

        Ye tab kaam karta hai jab:
        - User ne setting mein "whatsapp_excel_send" enable kiya ho
        - User ke paas mobile number ho
        - Tab ke results_tree mein data ho
        - Status "success" ya "failed" ho (stopped par nahi bhejenge)
        """
        # Only send on success or failure (not stopped)
        if status not in ("success", "failed"):
            return

        # Check if Excel WhatsApp is enabled
        excel_enabled = get_config("whatsapp_excel_send", False)
        if not excel_enabled:
            return

        # Check if license_info has mobile number
        lic = getattr(self.app_state, 'license_info', {})
        if not lic or not lic.get('user_mobile'):
            return
        user_mobile = lic.get('user_mobile', '')
        if not user_mobile:
            return

        # Check if tab has results_tree with data
        if tab_instance is None:
            return
        results_tree = getattr(tab_instance, 'results_tree', None)
        if results_tree is None:
            return
        all_items = results_tree.get_children()
        if not all_items:
            return

        # Run in background thread
        def _send_excel():
            try:
                # ── Step 1: Auto-save Excel to temp ──
                if not hasattr(tab_instance, 'export_treeview_to_excel_auto'):
                    return
                title_prefix = key.replace('_', ' ').title()
                filename = f"{key}_report.xlsx"
                file_path = tab_instance.export_treeview_to_excel_auto(
                    results_tree, default_filename=filename, title_prefix=title_prefix
                )
                if not file_path or not os.path.exists(file_path):
                    logger.debug(f"Excel auto-save failed for {key}, skipping WhatsApp send")
                    return

                # ── Step 2: Check file size (limit ~15MB) ──
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > 15:
                    logger.debug(f"Excel file too large ({file_size_mb:.1f}MB), skipping WhatsApp send")
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    return

                # ── Step 3: Upload to nrega-server and send via Evolution API ──
                server_url = config.LICENSE_SERVER_URL
                if not server_url:
                    logger.debug("No server URL configured, skipping WhatsApp send")
                    return

                # Read file as base64 for upload
                with open(file_path, "rb") as f:
                    file_data = f.read()
                file_b64 = base64.b64encode(file_data).decode('utf-8')

                caption = f"📊 {title_prefix} — NREGA Bot"
                upload_payload = {
                    "user_mobile": user_mobile,
                    "filename": filename,
                    "file_data": file_b64,
                    "caption": caption,
                    "license_key": lic.get('key', ''),
                }

                resp = requests.post(
                    f"{server_url}/api/whatsapp-send-excel",
                    json=upload_payload,
                    timeout=60
                )
                if resp.status_code in (200, 201):
                    logger.info(f"Excel WhatsApp sent for {key} to {user_mobile}")
                else:
                    logger.debug(f"Excel WhatsApp send failed: {resp.status_code} {resp.text}")

                # ── Step 4: Clean up temp file ──
                try:
                    os.remove(file_path)
                except Exception:
                    pass

            except Exception as e:
                logger.debug(f"Excel WhatsApp send failed for {key}: {e}")

        threading.Thread(target=_send_excel, daemon=True).start()

    def _emergency_stop_all(self) -> None:
        """Emergency stop ALL running automations immediately.
        Sets stop events, force-quits browser, and resets UI.
        """
        if not self.app_state.active_automations:
            return

        # 1. Set ALL stop events
        for key in list(self.app_state.active_automations):
            if key in self.app_state.stop_events:
                self.app_state.stop_events[key].set()

        # 2. Force-quit the browser driver (unblocks stuck page loads)
        try:
            if self.app_state.driver:
                try:
                    self.app_state.driver.quit()
                except Exception:
                    try:
                        self.app_state.driver.close()
                    except Exception:
                        pass
                self.app_state.driver = None
                self.app_state.active_browser = None
        except Exception as e:
            logger.debug("Emergency stop driver cleanup: %s", e)

        # 3. Log emergency stop for all active automations
        stopped_keys = list(self.app_state.active_automations)
        for key in stopped_keys:
            self.history_manager.log_automation_finish(
                automation_key=key,
                panchayat="",
                village="",
                status="stopped",
                duration_seconds=0,
                details="Emergency stop"
            )
        
        # 4. Clean up all active automation tracking
        count = len(self.app_state.active_automations)
        self.app_state.active_automations.clear()
        self.allow_sleep()

        self.play_sound("error")
        self.set_status(f"⚠ Emergency Stopped {count} automation(s)")
        self.show_toast(f"🛑 Emergency stopped {count} automation(s)", "warning", duration=5000)
        self.after(0, self._update_emergency_stop_btn)
        self.after(0, self._update_running_automation_indicator)

    def _update_running_automation_indicator(self) -> None:
        """Update the footer's '▶ Running: ...' label with the currently
        active automation display names. Safe to call before the footer is
        built (label may not exist yet)."""
        label = getattr(self, 'running_automation_label', None)
        if label is None:
            return
        try:
            if not label.winfo_exists():
                return
            active = list(self.app_state.active_automations)
            if not active:
                label.configure(text="")
            else:
                names = [f"{_automation_display_name(k)}" for k in sorted(active)]
                label.configure(text="▶ Running: " + ", ".join(names))
        except Exception:
            logger.debug("Failed to update running automation indicator", exc_info=True)

    def _update_emergency_stop_btn(self) -> None:
        """Toggle emergency stop indicator + label state.
        Red dot + red label when active, transparent when idle.
        NEVER uses pack/pack_forget — stays packed always to avoid layout shift."""
        has_active = bool(self.app_state.active_automations)
        ind = getattr(self, 'emergency_stop_indicator', None)
        lbl = getattr(self, 'emergency_stop_label', None)
        if has_active:
            red = ("#DC2626", "#EF4444")
            if ind and ind.winfo_exists():
                ind.configure(fg_color=red)
            if lbl and lbl.winfo_exists():
                lbl.configure(text_color=red)
        else:
            gray = ("gray50", "gray50")
            if ind and ind.winfo_exists():
                ind.configure(fg_color="transparent")
            if lbl and lbl.winfo_exists():
                lbl.configure(text_color=gray)

    @staticmethod
    def _get_current_financial_year():
        """Returns current Indian financial year as 'YYYY-YYYY' (e.g. '2026-2027').
        Indian FY runs from April to March."""
        now = datetime.now()
        year = now.year
        if now.month < 4:
            return f"{year - 1}-{year}"
        else:
            return f"{year}-{year + 1}"

    def _select_dropdown_safe(self, wait, xpath, text, wait_for_options=False):
        """Helper to select a dropdown option with retry logic for stale elements."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import StaleElementReferenceException

        for _ in range(3):
            try:
                elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                sel = Select(elem)
                if wait_for_options:
                    d = self.get_driver()
                    if d:
                        WebDriverWait(d, 5).until(
                            lambda d: len(Select(d.find_element(By.XPATH, xpath)).options) > 1
                        )
                        sel = Select(d.find_element(By.XPATH, xpath))
                try:
                    sel.select_by_visible_text(text)
                except Exception:
                    found = False
                    for opt in sel.options:
                        if opt.text.strip().lower() == text.lower():
                            sel.select_by_visible_text(opt.text)
                            found = True
                            break
                    if not found:
                        raise Exception(f"Option '{text}' not found")
                return
            except StaleElementReferenceException:
                time.sleep(1)
        raise Exception(f"Failed to select '{text}' after retries")

    def _run_login_navigation_background(self, district, block):
        """Runs NREGA portal navigation (FY / District / Block selection)
        silently in background — no tab is opened, only footer status updates.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        fin_year = self._get_current_financial_year()

        self.set_status("Launching browser...")
        driver = self.get_driver()
        if not driver:
            self.set_status("Login: No browser found")
            return

        url = "https://vbgramgde2.dord.gov.in/VBGRAMG/Login.aspx?&level=HomePO&state_code=34"
        driver.get(url)
        wait = WebDriverWait(driver, 25)

        self.set_status(f"Login: Selecting FY {fin_year}...")
        self._select_dropdown_safe(wait, "//select[contains(@id, 'ddl_FinYr')]", fin_year)

        self.set_status(f"Login: Finding district '{district}'...")
        self._select_dropdown_safe(wait, "//select[contains(@id, 'ddl_District')]", district, wait_for_options=True)

        self.set_status(f"Login: Finding block '{block}'...")
        self._select_dropdown_safe(wait, "//select[contains(@id, 'ddl_Block')]", block, wait_for_options=True)

        self.set_status("Login: Waiting for page refresh...")
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except TimeoutException:
            pass

        self.set_status("Ready for Login")

    def _quick_login_automation(self) -> None:
        """Auto Login: Launches Chrome if needed, reads District & Block from
        history_manager (server-synced data), runs automation silently in
        background with only the footer status bar showing progress.
        No tab navigation happens.
        """
        def _runner():
            # --- 1. Check / Launch Browser ---
            chrome_running = False
            try:
                with socket.create_connection(("127.0.0.1", 9222), timeout=0.2):
                    chrome_running = True
            except Exception:
                pass

            if not chrome_running:
                login_url = "https://vbgramgde2.dord.gov.in/VBGRAMG/Login.aspx?&level=HomePO&state_code=34"
                self.after(0, lambda: self.launch_chrome_detached(target_urls=[login_url]))
                time.sleep(4)

            # --- 2. Read District & Block from history_manager (server-synced) ---
            hm = self.history_manager
            dist_suggestions = hm.get_suggestions("location_district")
            block_suggestions = hm.get_suggestions("location_block")
            lic = getattr(self.app_state, 'license_info', {})
            server_dist = (lic.get('user_district') or '').strip().upper() if lic else ''
            server_block = (lic.get('user_block') or '').strip().upper() if lic else ''

            district = dist_suggestions[0] if dist_suggestions else (server_dist or '')
            block = block_suggestions[0] if block_suggestions else (server_block or '')

            if not district or not block:
                self.after(0, lambda: (
                    self.play_sound("error"),
                    messagebox.showwarning(
                        "Setup Required",
                        "District ya Block data nahi mila.\n\n"
                        "Pehle Settings > Location Data > 'Scrape from Website' se data sync karein.\n"
                        "Ya Settings > Location Data mein manual add karein."
                    )
                ))
                return

            # --- 3. Data exists — run silently in background ---
            self._run_login_navigation_background(district, block)

        threading.Thread(target=_runner, daemon=True).start()

    def prevent_sleep(self):
        self.services.prevent_sleep()

    def allow_sleep(self):
        self.services.allow_sleep()
