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

import customtkinter as ctk

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
        # Fresh run: purana progress clear karo (footer '%' stale na rahe)
        self.app_state.automation_progress.pop(key, None)
        self._update_emergency_stop_btn()
        self._update_running_automation_indicator()

        if self.app_state.minimize_var.get() and self.app_state.driver:
            self._minimize_active_browser()
            self.show_toast("Running in Background (Minimized)", "info")

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
            error_msg = ''  # set if target() raises — used to log status="failed"
            # Fresh run: forget any browser choice left over from a previous
            # run so this automation gets to pick (if multiple browsers).
            try:
                self.browser_manager.clear_thread_choice()
            except Exception:
                pass
            try:
                target(*args)
            except Exception as e:
                # Include the exception type — much more useful for the admin
                # error logs when debugging what went wrong.
                error_msg = f"{type(e).__name__}: {str(e)}"[:600]
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
                self.after(0, lambda k=key, dur=duration, inst=tab_instance, err=error_msg:
                           self.on_automation_finished(k, dur, inst, err))

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
            anchored = False
            try:
                while (worker_thread.is_alive()
                       and key in self.app_state.active_automations):
                    if marker_session is None:
                        marker_session, owns_session = self.browser_manager.connect_driver_no_dialog()
                        anchored = False
                    if marker_session is not None:
                        try:
                            if marker_session.window_handles:
                                if owns_session and not anchored:
                                    # Separate keeper session (chrome/edge): switch
                                    # to the automation tab ONCE to anchor the
                                    # session there. IMPORTANT: never switch again
                                    # — switch_to.window() brings the tab to the
                                    # FRONT in the browser UI, so doing it every
                                    # tick would yank the user off whatever tab
                                    # they are working on. apply_automation_marker()
                                    # uses execute_script() only, which does NOT
                                    # steal focus — so we can keep re-painting the
                                    # marker without disturbing the user's tab.
                                    target = self.browser_manager.resolve_automation_tab(marker_session)
                                    if target:
                                        # No-op anchor when the keeper session is
                                        # already on the automation tab (the common
                                        # case right at run start) — avoids even the
                                        # single focus steal. Window handles are
                                        # browser-level target IDs, stable across CDP
                                        # sessions, so this comparison is reliable.
                                        if marker_session.current_window_handle != target:
                                            marker_session.switch_to.window(target)
                                        anchored = True
                                # Shared in-app Firefox driver: do NOT switch
                                # windows — the automation may be working in a
                                # popup, and yanking the active window here
                                # would break it. Just paint the marker on the
                                # window the automation is currently using.
                                self.browser_manager.apply_automation_marker(marker_session)
                                # Re-force the tab ACTIVE + FOCUSED every tick:
                                # Chrome/Edge reset the web lifecycle state on
                                # every navigation, and a hidden tab silently
                                # breaks JS-driven controls (radio buttons,
                                # dropdown postbacks) — this undoes that while
                                # the user works on another tab. Safe no-op on
                                # Firefox (no execute_cdp_cmd).
                                self.browser_manager.keep_tab_active(marker_session)
                        except Exception:
                            marker_session = None
                            owns_session = False
                            anchored = False
                    time.sleep(2)
            finally:
                if owns_session and marker_session is not None:
                    try:
                        marker_session.quit()
                    except Exception:
                        pass

        threading.Thread(target=_marker_keeper, args=(t,), daemon=True).start()

    def _minimize_active_browser(self) -> None:
        """Minimize the active browser window on every platform.

        Previously only the in-app Firefox driver was reliably minimized
        (via Selenium). Detached Chrome/Edge sessions often ignore Selenium's
        minimize, so we add an OS-level fallback per browser:
          * macOS: osascript 'set minimized of windows to true' per app
          * Windows: Win32 ShowWindow(SW_MINIMIZE) on the browser's windows
        """
        browser = self.app_state.active_browser

        # 1) Selenium first (works for the in-app Firefox driver, and sometimes
        #    for CDP-connected Chrome/Edge).
        try:
            if self.app_state.driver:
                self.app_state.driver.minimize_window()
        except Exception:
            pass

        # 2) OS-level fallbacks (belt & suspenders — idempotent, safe to repeat).
        if config.OS_SYSTEM == "Darwin":
            app_name = {"chrome": "Google Chrome",
                        "edge": "Microsoft Edge"}.get(browser)
            if app_name:
                # Chrome/Edge expose a full scripting dictionary.
                try:
                    subprocess.run(
                        ["osascript", "-e",
                         f'tell application "{app_name}" to set minimized of windows to true'],
                        check=True, capture_output=True, timeout=5)
                except Exception:
                    logger.debug("osascript minimize failed for %s", app_name, exc_info=True)
            elif browser == "firefox":
                # Firefox has a minimal AppleScript dictionary — use System
                # Events accessibility (no-op if permission is missing).
                try:
                    subprocess.run(
                        ["osascript", "-e",
                         'tell application "System Events" to set value of attribute '
                         '"AXMinimized" of every window of process "Firefox" to true'],
                        check=True, capture_output=True, timeout=5)
                except Exception:
                    logger.debug("System Events minimize failed for Firefox", exc_info=True)
        elif config.OS_SYSTEM == "Windows":
            self._minimize_browser_windows_win32(browser)

    @staticmethod
    def _minimize_browser_windows_win32(browser: Optional[str]) -> None:
        """Minimize all visible top-level windows of the given browser on Windows."""
        if not browser:
            return
        try:
            import ctypes
            from ctypes import wintypes

            SW_MINIMIZE = 6
            # Chrome & Edge share the same Chromium window class.
            class_map = {"chrome": "Chrome_WidgetWin_1",
                         "edge": "Chrome_WidgetWin_1",
                         "firefox": "MozillaWindowClass"}
            target_class = class_map.get(browser)
            if not target_class:
                return

            user32 = ctypes.windll.user32
            windows: list = []

            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            @EnumWindowsProc
            def _enum(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetClassNameW(hwnd, None, 0)
                    if length:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetClassNameW(hwnd, buf, length + 1)
                        if buf.value == target_class:
                            windows.append(hwnd)
                return True

            user32.EnumWindows(_enum, 0)
            for hwnd in windows:
                user32.ShowWindow(hwnd, SW_MINIMIZE)
        except Exception:
            logger.debug("Win32 browser minimize failed for %s", browser, exc_info=True)

    def on_automation_finished(self, key, duration=0.0, tab_instance=None, error_msg=''):
        if key in self.app_state.active_automations:
            self.app_state.active_automations.remove(key)
        self.app_state.automation_progress.pop(key, None)
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
                
                # Determine status: uncaught error → failed, stop requested →
                # stopped, otherwise success.
                stop_event = self.app_state.stop_events.get(key)
                if error_msg:
                    status = "failed"
                elif stop_event and stop_event.is_set():
                    status = "stopped"
                else:
                    status = "success"

                # Prepend the error so the admin panel's Error Logs tab can
                # show exactly what went wrong.
                log_details = details
                if error_msg:
                    log_details = f"ERROR: {error_msg}" + (f" | {details}" if details else "")

                self.history_manager.log_automation_finish(
                    automation_key=key,
                    panchayat=panchayat,
                    village=village,
                    status=status,
                    duration_seconds=duration,
                    details=log_details
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
                # ── WhatsApp Report (single setting: summary + Excel sath) ──
                self._send_whatsapp_report_if_enabled(
                    key, panchayat, status, duration, details, tab_instance
                )

                # ── Cloud Reports: raw results (columns + rows) sync karo ──
                self._sync_automation_results_to_cloud(
                    key, panchayat, status, duration, details, tab_instance
                )
                
                # ── Sync activity log to server (Phase 2) ──
                lic = getattr(self.app_state, 'license_info', {}) or {}
                server_license_key = lic.get('key', '')
                self.history_manager.sync_activity_log_to_server(license_key=server_license_key)
            except Exception as e:
                logger.error(f"Failed to send notification/sync for {key}: {e}")

    def _send_whatsapp_report_if_enabled(self, key, panchayat, status, duration, details, tab_instance=None):
        """
        Ek hi setting (whatsapp_automation_notify) — ON hone par automation finish
        par summary message + results Excel dono bheje jaate hain.

        - Results data ho → EK hi WhatsApp message: Excel document jiska caption summary hai
          (message count aadha → throttling risk bhi kam).
        - Excel nahi bana (koi data nahi / >15MB / fail) → sirf summary text message.
        """
        if status not in ("success", "failed"):
            return

        # Fresh read of details on the MAIN thread — tabs jo rows async insert
        # karte hain (safe_tree_insert via app.after), unke pending inserts yahan
        # tak process ho chuke hote hain, isliye summary counts accurate milte hain
        # (wrapper() me bg-thread par liya gaya details stale ho sakta hai).
        if tab_instance is not None:
            try:
                details = getattr(tab_instance, 'activity_details', details) or details
            except Exception:
                pass

        # Single merged setting (legacy whatsapp_excel_send bhi honor karta hai)
        if not (get_config("whatsapp_automation_notify", False)
                or get_config("whatsapp_excel_send", False)):
            return

        # Success + koi result nahi → message bilkul na bhejo.
        # e.g. Mr Tracking me koi record nahi mila — bina result ke
        # "Completed Successfully" bhejne ka koi matlab nahi.
        # Par agar results_tree me data hai (Excel ban sakti hai) to report
        # chalti rahe — Excel hi result hai.
        # (Failed status ab bhi notify hota hai — user ko pata hona chahiye.)
        if status == "success" and (not details or not str(details).strip()):
            tree = getattr(tab_instance, 'results_tree', None) if tab_instance else None
            if tree is None or not tree.get_children():
                logger.info("WhatsApp report skipped for %s — success with no result data", key)
                return

        # Check if license_info has mobile number + key
        lic = getattr(self.app_state, 'license_info', {})
        user_mobile = (lic or {}).get('user_mobile', '')
        license_key = (lic or {}).get('key', '')
        if not user_mobile or not license_key:
            return

        # Build summary (Excel caption bhi yahi use hoga) — escaping-safe list + join
        duration_str = f"{duration:.0f}s" if duration < 60 else f"{duration/60:.1f}m"
        emoji = "✅" if status == "success" else "⚠️"
        status_word = "Completed Successfully" if status == "success" else "Completed with Issues"
        task_name = _automation_display_name(key)
        summary_lines = [f"{emoji} {task_name} — {status_word}"]
        if panchayat:
            summary_lines.append(f"📍 Panchayat: {panchayat}")
        summary_lines.append(f"⏱ Duration: {duration_str}")
        if details:
            summary_lines.append(f"📊 Result: {details}")
        summary = chr(10).join(summary_lines)

        # Send to server in background thread
        def _send():
            file_path = None
            try:
                server_url = config.LICENSE_SERVER_URL
                if not server_url:
                    return

                # ── Step 1: Try combined message — Excel with summary caption ──
                results_tree = getattr(tab_instance, 'results_tree', None) if tab_instance else None
                try:
                    if (results_tree is not None and results_tree.get_children()
                            and hasattr(tab_instance, 'export_treeview_to_excel_auto')):
                        title_prefix = key.replace('_', ' ').title()
                        filename = f"{key}_report.xlsx"
                        file_path = tab_instance.export_treeview_to_excel_auto(
                            results_tree, default_filename=filename, title_prefix=title_prefix
                        )
                        if file_path and os.path.exists(file_path):
                            size_mb = os.path.getsize(file_path) / (1024 * 1024)
                            if size_mb <= 15:
                                with open(file_path, "rb") as f:
                                    file_b64 = base64.b64encode(f.read()).decode('utf-8')
                                payload = {
                                    "user_mobile": user_mobile,
                                    "filename": filename,
                                    "file_data": file_b64,
                                    "caption": summary[:1000],  # Evolution caption limit ~1024
                                    "license_key": license_key,
                                }
                                resp = requests.post(f"{server_url}/api/whatsapp-send-excel",
                                                     json=payload, timeout=60)
                                if resp.status_code in (200, 201):
                                    logger.info("WhatsApp report (summary+Excel) sent for %s", key)
                                    return
                except Exception as e:
                    logger.debug("WhatsApp Excel send failed for %s: %s", key, e)

                # ── Step 2: Fallback — sirf summary text message ──
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
                resp = requests.post(f"{server_url}/api/whatsapp-notify-automation",
                                     json=payload, timeout=10)
                if resp.status_code in (200, 201):
                    logger.info("WhatsApp summary sent for %s", key)
                else:
                    logger.debug("WhatsApp summary failed: %s", resp.text)
            except Exception as e:
                logger.debug("WhatsApp report error: %s", e)
            finally:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

        threading.Thread(target=_send, daemon=True).start()

    # ════════════════════════════════════════════════════════════
    # CLOUD REPORTS — raw results sync (30-day web portal storage)
    # ════════════════════════════════════════════════════════════
    def _sync_automation_results_to_cloud(self, key, panchayat, status, duration,
                                          details, tab_instance=None):
        """
        Automation finish par results_tree ka raw data (columns + rows)
        server ko POST karta hai — web portal Reports page ke liye.

        - Sirf jab results data ho (rows empty ho to sync nahi)
        - Background thread me, non-blocking
        - Failed status bhi sync hota hai (details ke saath)
        """
        try:
            # Stopped automations sync nahi karte (partial data galat report banayega)
            if status not in ("success", "failed"):
                return
            if not tab_instance:
                return
            if not hasattr(tab_instance, '_extract_tree_columns_rows'):
                return

            columns, rows = tab_instance._extract_tree_columns_rows()
            if not rows:
                logger.debug("Cloud reports: no rows for %s — skip sync", key)
                return

            lic = getattr(self.app_state, 'license_info', {}) or {}
            license_key = (lic or {}).get('key', '')
            if not license_key:
                return
            server_url = config.LICENSE_SERVER_URL
            if not server_url:
                return

            payload = {
                "license_key": license_key,
                "automation_key": key,
                "run_timestamp": datetime.now().isoformat(),
                "panchayat": panchayat,
                "status": status,
                "duration_seconds": duration,
                "details": details,
                "columns": columns,
                "rows": rows,
            }

            def _send():
                try:
                    resp = requests.post(
                        f"{server_url}/api/automation-results/sync",
                        json=payload, timeout=20)
                    if resp.status_code in (200, 201):
                        logger.info("Cloud reports synced for %s (%d rows)", key, len(rows))
                    else:
                        logger.debug("Cloud reports sync failed for %s: %s", key, resp.text)
                except Exception as e:
                    logger.debug("Cloud reports sync error for %s: %s", key, e)

            threading.Thread(target=_send, daemon=True).start()
        except Exception as e:
            logger.debug("Cloud reports pre-check error for %s: %s", key, e)

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
        # Emergency stop → koi automation active nahi — progress state bhi clean
        self.app_state.automation_progress.clear()
        self.allow_sleep()

        self.play_sound("error")
        self.set_status(f"⚠ Emergency Stopped {count} automation(s)")
        self.show_toast(f"🛑 Emergency stopped {count} automation(s)", "warning", duration=5000)
        self.after(0, self._update_emergency_stop_btn)
        self.after(0, self._update_running_automation_indicator)

    def _update_running_automation_indicator(self) -> None:
        """Update the footer's '▶ Running: ...' indicator with the currently
        active automation display names. Har naam ek clickable chip hai jo
        us automation ka tab kholta hai. Safe to call before the footer is
        built (frame may not exist yet)."""
        frame = getattr(self, 'running_automation_frame', None)
        if frame is None:
            return
        try:
            if not frame.winfo_exists():
                return
            active = list(self.app_state.active_automations)
            if not active:
                self._clear_running_chips()
                self.running_automation_prefix.configure(text="")
                return
            # Sirf tab on change par rebuild karo (avoid churn)
            cur_keys = tuple(sorted(active))
            if getattr(self, '_running_chip_keys', None) == cur_keys:
                return
            self._running_chip_keys = cur_keys
            self._clear_running_chips()
            self.running_automation_prefix.configure(text="▶ Running: ")
            tab_map = self._automation_key_to_tab_name()
            for idx, k in enumerate(cur_keys):
                if idx > 0:
                    sep = ctk.CTkLabel(frame, text=",", text_color=("#2563EB", "#60A5FA"),
                                       font=ctk.CTkFont(size=12, weight="bold"))
                    sep.pack(side="left")
                    self.running_automation_chips.append(sep)
                name = _automation_display_name(k)
                tab_name = tab_map.get(k)
                chip = ctk.CTkLabel(
                    frame, text=name,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=("#2563EB", "#60A5FA"),
                    cursor="hand2" if tab_name else ""
                )
                chip.pack(side="left")
                if tab_name:
                    chip.bind("<Button-1>", lambda e, tn=tab_name: self._open_running_tab(tn))
                    chip.bind("<Enter>", lambda e, c=chip: c.configure(text_color=("#1E40AF", "#93C5FD")))
                    chip.bind("<Leave>", lambda e, c=chip: c.configure(text_color=("#2563EB", "#60A5FA")))
                self.running_automation_chips.append(chip)
                # Progress % label — sirf agar tab ne progress report kiya ho
                pct = self.app_state.automation_progress.get(k)
                pct_label = ctk.CTkLabel(
                    frame,
                    text=f" {int(round(float(pct) * 100))}%" if pct is not None else "",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=("#1E40AF", "#93C5FD")
                )
                pct_label.pack(side="left")
                self.running_automation_chips.append(pct_label)
                self._running_pct_labels[k] = pct_label
        except Exception:
            logger.debug("Failed to update running automation indicator", exc_info=True)

    def _clear_running_chips(self) -> None:
        """Destroy all footer running-indicator chips (comma separators included)."""
        try:
            for w in getattr(self, 'running_automation_chips', []):
                try:
                    if w.winfo_exists():
                        w.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        self.running_automation_chips = []
        self._running_pct_labels = {}

    def _open_running_tab(self, tab_name: str) -> None:
        """Footer '▶ Running' chip click → switch to the automation's tab."""
        try:
            self.show_frame(tab_name)
            self.set_status(f"Opened {tab_name}")
        except Exception as e:
            logger.debug("Failed to open running tab %s: %s", tab_name, e)

    def _automation_key_to_tab_name(self) -> Dict[str, str]:
        """Map automation_key → tab display name for footer chip clicks.

        Loaded tab instances are authoritative (their automation_key matches
        the active_automations keys exactly — e.g. 'gen' for Wagelist Gen).
        Falls back to the tab_config 'key' field, then a small override map
        for the known config-key vs automation-key mismatches.
        """
        mapping: Dict[str, str] = {}
        try:
            instances = getattr(self.app_state, 'tab_instances', {}) or {}
            for name, inst in instances.items():
                key = getattr(inst, 'automation_key', None)
                if key:
                    mapping.setdefault(key, name)
        except Exception:
            pass
        try:
            for _cat, tabs in self.get_tabs_definition().items():
                for name, info in tabs.items():
                    k = info.get("key")
                    if k:
                        mapping.setdefault(k, name)
        except Exception:
            pass
        for k, n in {
            "gen": "Gen Wagelist",
            "send": "Send Wagelist",
            "muster": "Muster Roll Gen",
            "msr": "MR Payment",
            "if_edit": "IF Editor",
            "jc_verify": "Job Card Verify",
            "jobcard_verify": "Job Card Verify",
            "abps_verify": "Verify ABPS",
            "verify_abps": "Verify ABPS",
            "resend_wg": "Resend Rejected WG",
            "sad_auto": "Sarkar Aapke Dwar",
            "fto_gen_del": "FTO Generation",
            "macro": "Macro Manager",
            "pdf_merger": "PDF Merger",
            "wc_extractor": "Workcode Extractor",
        }.items():
            mapping.setdefault(k, n)
        return mapping

    def report_automation_progress(self, key: str, fraction: float) -> None:
        """Automation tab apna progress fraction (0.0–1.0) yahan report karta hai.

        Footer me us automation ke naam ke aage '%' dikhata hai. Thread-safe:
        value store karke main-thread par label update schedule karta hai.
        """
        try:
            frac = max(0.0, min(1.0, float(fraction)))
            if abs(self.app_state.automation_progress.get(key, -1.0) - frac) < 0.001:
                return
            self.app_state.automation_progress[key] = frac
            self.after(0, self._refresh_running_pct_labels)
        except Exception:
            pass

    def _refresh_running_pct_labels(self) -> None:
        """Footer me '%' labels live-update karo — chip rebuild nahi, sirf text."""
        try:
            labels = getattr(self, '_running_pct_labels', None)
            if not labels:
                return
            for k, lbl in list(labels.items()):
                try:
                    if not lbl.winfo_exists():
                        continue
                    frac = self.app_state.automation_progress.get(k)
                    if frac is None:
                        txt = ""
                    else:
                        pct = min(99, int(round(float(frac) * 100)))
                        txt = f" {pct}%"
                    if lbl.cget("text") != txt:
                        lbl.configure(text=txt)
                except Exception:
                    pass
        except Exception:
            pass

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
                        "Pehle Settings > Location Data > 'Add Panchayat & Village' se sync karein.\n"
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
