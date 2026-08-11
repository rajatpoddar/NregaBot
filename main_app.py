# main_app.py

# ============================================================================
# IMPORTS
# ============================================================================

# --- Standard Library ---
import threading
import time
import subprocess
import os
import sys
import json
import logging
import socket
import shutil
import re
import gc
from urllib.parse import urlencode
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# --- Third Party UI & System ---
import tkinter
from tkinter import messagebox, filedialog, ttk
import customtkinter as ctk
import requests
from PIL import Image
from dotenv import load_dotenv
# --- Windows Specific ---
from src import config
if config.OS_SYSTEM == "Windows":
    import ctypes
    try:
        # Enable per-monitor DPI awareness (v2) for smooth rendering on hi-DPI displays
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # Fallback: system DPI awareness
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# --- Local Modules / UI Components ---
from src.ui_components import (
    CollapsibleFrame, SkeletonLoader, MarqueeLabel,
    ToastNotification, OnboardingGuide, ComingSoonTab, PerformanceMonitor
)
from src.managers.browser_manager import BrowserManager
from src.managers.services import ServiceManager
from src.tab_config import get_tabs_definition
from src.managers.icon_manager import create_icon_manager
from src.managers.sound_manager import SoundManager
from src.app.app_license import LicenseMixin
from src.app.app_navigation import NavMixin
from src.app.app_automation import AutomationMixin
from src.app.app_ui import UIMixin
from src.managers.workflow_manager import WorkflowManager
from src.location_data import STATE_DISTRICT_MAP
from src.tabs.history_manager import HistoryManager
from src.tabs.macro_manager_tab import MacroManagerTab
from src.state import AppState
from src.utils import (
    resource_path, get_data_path, get_user_downloads_path, get_nregabot_path,
    get_report_path, get_config, save_config, validate_config,
    setup_logging, get_logger, install_crash_reporter
)

# Note: Heavy libraries (Selenium) are imported inside
# functions to speed up startup time.

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================

# C8: Initialize centralized logging before anything else
setup_logging()
logger = get_logger()

# Crash reporter — uncaught exceptions Temp/crashes/ me save hote hain
install_crash_reporter()

load_dotenv()
config.create_default_config_if_not_exists()
# A5: Validate config.json before use — auto-resets if corrupted
validate_config()

# Store original messagebox functions to override them later
_original_showinfo = messagebox.showinfo
_original_showwarning = messagebox.showwarning
_original_showerror = messagebox.showerror

# Theme Setup
ctk.set_default_color_theme(resource_path(os.path.join("config", "theme.json")))
ctk.set_appearance_mode("System")


class NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin):
    """
    Main Application Class for NREGA Bot.
    Handles UI orchestration, navigation, license management, and automation dispatching.
    """

    # ============================================================================
    # 1. INITIALIZATION & LIFECYCLE
    # ============================================================================

    def __init__(self) -> None:
        super().__init__()

        # Initial Window State
        self.withdraw()  # Hide initially for smooth splash transition
        self.title(f"{config.APP_NAME}")

        # Dimensions & Constraints
        self.initial_width = 1100
        self.initial_height = 800
        # Chhoti screens (720p laptops) ke liye compact minimum — content
        # neeche se na kate (Settings ke cards/buttons visible rahen).
        self.minsize(960, 620)

        # Root-window background — drive it through CTk's fg_color as a
        # (light, dark) tuple so it follows the theme on every switch
        # (a plain `bg=` is ignored by the macOS Aqua theme and a hardcoded
        # colour never changes). Kept in sync by _sync_root_background().
        self.configure(fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))

        # A4: Centralized application state — all state lives in self.app_state dataclass
        self.app_state = AppState()

        # --- Service Managers ---
        self.history_manager = HistoryManager(self.get_data_path)
        self.browser_manager = BrowserManager(self)
        self.services = ServiceManager(self)
        self.sound_manager = SoundManager(self)
        self.workflows = WorkflowManager(self)

        # A4: State that requires Tk root or services before initialization
        self.app_state.http_session = requests.Session()  # Optimized network session
        self.app_state.machine_id = self._get_machine_id()
        self.app_state.sound_switch_var = tkinter.BooleanVar(value=get_config('sound_enabled', True))
        self.app_state.minimize_var = tkinter.BooleanVar(value=True)
        self.app_state.last_selected_category = get_config('last_selected_category', 'All Automations')

        # --- Non-state: service references / UI placeholders built later ---
        self.icon_images = {}
        self.status_label = None
        self.server_status_indicator = None
        self.loading_animation_label = None
        self.splash = None

        # --- GC Tuning: Reduce memory fragmentation for long-running GUI app ---
        gc.set_threshold(700, 10, 5)
        gc.freeze()

        # --- STARTUP SEQUENCE ---

        # 1. Show Splash Screen
        self.splash = self._create_splash_screen()
        self.splash.update()

        # 2. Initialize Lazy Icon Manager (definitions only, no image loading yet)
        self.icon_images = create_icon_manager()
        # Preload essential icons (browser, settings, dock) into cache
        # so UI creation doesn't trigger on-demand disk I/O on main thread
        self.icon_images.preload_essential()

        # 3. Start Background Initialization (Heavy Tasks)
        threading.Thread(target=self._background_initialization, daemon=True).start()

        # 4. Set Cleanup Protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 5. Start periodic GC (5min interval) to prevent memory fragmentation
        self.after(300000, self._gc_collection_loop)  # First run after 5 min

    def _create_splash_screen(self) -> ctk.CTkToplevel:
        """Creates a clean, modern splash screen with high readability on both themes."""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)
        w, h = 380, 260
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        x, y = (sw // 2) - (w // 2), (sh // 2) - (h // 2)
        splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        # Base window color blends seamlessly with outer frame (no border needed)
        splash.configure(fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))

        # Outer frame - seamless card, no awkward border
        outer = ctk.CTkFrame(
            splash, fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]), corner_radius=16,
            border_width=0
        )
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=30, pady=22)

        try:
            logo = ctk.CTkImage(Image.open(resource_path("assets/logo.png")), size=(64, 64))
            ctk.CTkLabel(inner, image=logo, text="").pack(pady=(5, 10))
        except Exception as e:
            logger.debug("Failed to load splash screen logo: %s", e)

        # App Name - Large, bold, high contrast on both themes
        ctk.CTkLabel(
            inner, text=f"{config.APP_NAME}",
            font=ctk.CTkFont(family="Helvetica Neue", size=24, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"])
        ).pack()

        # Portal tag - bright blue for both themes with enough contrast
        ctk.CTkLabel(
            inner, text="VB-G-RAM-G Portal Support",
            font=ctk.CTkFont(family="Helvetica Neue", size=12, weight="bold"),
            text_color=(config.COLORS["blue_hover"], config.COLORS["blue_light"])
        ).pack(pady=(2, 18))

        # Animated dots - medium gray, crisp & readable
        self._splash_dots = 0
        splash.dots_label = ctk.CTkLabel(
            inner, text="Initializing",
            font=ctk.CTkFont(family="Helvetica Neue", size=12),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"])
        )
        splash.dots_label.pack(pady=(0, 0))

        # Animate dots
        def _splash_animate():
            try:
                if splash.winfo_exists():
                    self._splash_dots += 1
                    d = "." * (self._splash_dots % 4)
                    splash.dots_label.configure(text=f"Loading{d}")
                    splash.after(120, _splash_animate)
            except Exception as e:
                logger.debug("Splash animation error: %s", e)
        _splash_animate()

        # Version - Larger and bold for better visibility
        ctk.CTkLabel(
            inner, text=f"v{config.APP_VERSION}",
            font=ctk.CTkFont(family="Helvetica Neue", size=13, weight="bold"),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"])
        ).pack(side="bottom", pady=(0, 5))

        splash.lift()
        splash.attributes("-topmost", True)
        return splash

    def _background_initialization(self) -> None:
        """Loads heavy libraries and assets in background to keep UI responsive."""
        # 1. Store original messagebox functions in centralized state
        self.app_state._original_showinfo = _original_showinfo
        self.app_state._original_showwarning = _original_showwarning
        self.app_state._original_showerror = _original_showerror

        # 2. Apply Patches to Messagebox
        messagebox.showinfo = self._custom_showinfo
        messagebox.showwarning = self._custom_showwarning
        messagebox.showerror = self._custom_showerror

        # 3. Trigger UI Setup on Main Thread
        self.after(10, self._finish_startup)

    def _finish_startup(self) -> None:
        """Called on main thread after background loading is done.
        Progressively renders UI sections so low-end devices see smooth,
        staged appearance instead of a long freeze followed by partial widgets.
        """
        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<FocusIn>", self._on_window_focus)

        # Detect window state changes (maximize/restore) to smooth transitions
        self.bind("<Configure>", self._on_window_resize_detect, add="+")

        self.style_treeview()

        # Build Grid Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # BG FIX: Place a full-window background frame that covers the root
        # window completely. On macOS, the root Tk window's `bg` property does
        # not reliably update when the theme changes (Aqua ignores it). A
        # CTkFrame with a theme-aware fg_color tuple placed behind all other
        # widgets ensures the padding gaps (padx/pady around header/main/footer)
        # always show the correct background color without any restart needed.
        self._bg_frame = ctk.CTkFrame(
            self, corner_radius=0,
            fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"])
        )
        self._bg_frame.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_frame.lower()  # Keep it behind all other widgets

        # --- Stage 1: Header ---
        # P1: Removed intermediate update_idletasks() calls — splash screen is still
        # visible during these stages, so progressive rendering provides no visual benefit.
        self._create_header()

        # --- Stage 2: Footer ---
        self._create_footer()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Mac OS Specific: force one paint cycle to wake up the event loop.
        # P1: Removed time.sleep(0.1) — the update() alone is sufficient to
        # flush the event queue on macOS without blocking the main thread.
        if config.OS_SYSTEM == "Darwin":
            self.update()

        # --- Stage 3: Main Layout (sidebar + content area) ---
        self._create_main_layout(for_activation=True)
        self.app_state._layout_ready = True  # Signal that critical UI structure is built
        self.update_idletasks()

        self.set_status("Initializing...")

        # License Check Flow
        self.perform_license_check_flow()

        # Transition Splash — Smart wait:
        # Minimum 600ms to avoid flash on fast devices, but also waits for
        # _layout_ready in case device is slow and UI isn't built yet.
        self.after(600, self._check_splash_ready)

    def _check_splash_ready(self, retries: int = 0) -> None:
        """Waits for both minimum time AND layout readiness before fading splash.
        On low-end devices _layout_ready may not be True by the 600ms mark
        because widget creation takes longer — this loop keeps checking.

        Args:
            retries: Internal counter to prevent infinite loop (~5s max wait).
        """
        if getattr(self.app_state, '_layout_ready', False) and self.splash:
            self._transition_from_splash()
        elif self.splash and retries < 50:
            # Keep checking every 100ms (50 retries = ~5s total safety net)
            # After that, force transition regardless of layout state
            self.after(100, lambda: self._check_splash_ready(retries + 1))
        elif self.splash:
            # Safety net: force transition after ~5s even if layout isn't ready
            self._transition_from_splash()
        # If splash is already gone (e.g. error case), do nothing

    def _transition_from_splash(self) -> None:
        """Initiates splash fade out."""
        if self.splash:
            self._fade_out_splash(self.splash, step=0)

    def _fade_out_splash(self, splash: ctk.CTkToplevel, step: int) -> None:
        """Recursively fades out the splash screen (15 steps for smooth animation)."""
        total_steps = 15
        if step <= total_steps:
            try:
                if splash.winfo_exists():
                    splash.attributes("-alpha", 1.0 - (step / total_steps))
                    self.after(20, lambda: self._fade_out_splash(splash, step + 1))
                else:
                    self._fade_in_main_window()
            except Exception as e:
                logger.debug("Splash fade error: %s", e)
                self._fade_in_main_window()
        else:
            if splash.winfo_exists():
                splash.destroy()
            self.splash = None
            self.after(0, self._fade_in_main_window)

    def _get_style(self) -> ttk.Style:
        """Return a cached ttk.Style singleton.
        Creating a new ttk.Style() on every style_treeview() call is expensive
        because it re-reads all theme defaults. We cache it after first use."""
        if self.app_state._cached_style is None:
            self.app_state._cached_style = ttk.Style()
            self.app_state._cached_style.theme_use("clam")
        return self.app_state._cached_style

    def style_treeview(self, treeview_widget: Optional[Any] = None) -> None:
        style = self._get_style()

        # 1. Theme Detection
        mode = ctk.get_appearance_mode()

        if mode == "Dark":
            bg_color = config.COLORS["tv_bg_dark"]
            text_color = config.COLORS["tv_fg_dark"]
            row_hover = config.COLORS["tv_hover_dark"]
            selected_bg = config.COLORS["tv_sel"]
            header_bg = config.COLORS["tv_header_bg_dark"]
            header_fg = config.COLORS["tv_header_fg_dark"]
            header_hover = config.COLORS["tv_header_hover_dark"]
        else:
            bg_color = config.COLORS["tv_bg_light"]
            text_color = config.COLORS["text_dark_alt"]
            row_hover = config.COLORS["tv_hover_light"]
            selected_bg = config.COLORS["tv_sel"]
            header_bg = config.COLORS["tv_header_bg_light"]
            header_fg = config.COLORS["tv_header_fg_light"]
            header_hover = config.COLORS["tv_header_hover_light"]

        style.configure("Treeview",
                        background=bg_color,
                        foreground=text_color,
                        fieldbackground=bg_color,
                        rowheight=35,
                        font=("Segoe UI", 11),
                        borderwidth=0)

        style.map("Treeview",
                  background=[('selected', selected_bg), ('active', row_hover)],
                  foreground=[('selected', 'white'), ('active', text_color)])

        style.configure("Treeview.Heading",
                        background=header_bg,
                        foreground=header_fg,
                        relief="flat",
                        font=("Segoe UI", 12, "bold"))

        style.map("Treeview.Heading",
                  background=[('active', header_hover)])

        if treeview_widget:
            treeview_widget.configure(style="Treeview")

    def _fade_in_main_window(self) -> None:
        """Positions and shows the main application window fully rendered.

        On low-end devices tkinter's deiconify() can show the window before
        all widgets are painted, causing a "part by part" appearance.

        Fix: show at alpha=0 (invisible), force a full paint cycle with
        self.update(), then set alpha=1. The user sees the COMPLETE window
        in one frame — no progressive rendering.
        """
        # P1: Removed standalone update_idletasks() — the 2x paint loop
        # below already handles all pending layout calculations.
        work_x, work_y, work_width, work_height = self._get_work_area()
        min_w, min_h = 960, 620
        # Small screens par window kabhi bhi work-area se badi na ho —
        # nahi to bottom/side content cut ho jata hai (resolution issue).
        avail_h = max(min_h, work_height - 40)
        avail_w = max(min_w, work_width - 40)
        app_height = min(self.initial_height, avail_h, max(min_h, work_height))
        app_width = min(self.initial_width, avail_w, max(min_w, work_width))

        x = work_x + (work_width // 2) - (app_width // 2)
        y = work_y + (work_height // 2) - (app_height // 2)

        self.geometry(f'{app_width}x{app_height}+{x}+{y}')

        # Step 1: Make visible but fully transparent
        self.attributes("-alpha", 0.0)
        self.deiconify()

        # Step 2: Force tkinter to paint everything NOW while still invisible
        # P1: Reduced from 3 to 2 passes. Two full paint cycles (update +
        # update_idletasks) are sufficient for layout calculation AND pixel
        # composition — even on low-end GPUs that may skip composition for
        # transparent windows. The third pass was redundant.
        for _ in range(2):
            self.update()
            self.update_idletasks()

        # Step 3: Now show the fully-rendered window (all widgets painted in one frame)
        self.attributes("-alpha", 1.0)
        self.lift()
        self.focus_force()

        if getattr(self, 'state', None) and self.app_state.expiry_alert_message:
            def _show_delayed():
                self.play_sound("error")
                self.show_toast(self.app_state.expiry_alert_message, kind="warning", duration=6000)
                self.app_state.expiry_alert_message = None

            self.after(1500, _show_delayed)

    def run_onboarding_if_needed(self) -> None:
        """Runs the onboarding tour for first-time users, and re-shows it
        (at the Panchayat step) whenever no panchayat/village is saved yet —
        jab tak setup complete na ho (tour + panchayat), onboarding nag karta
        hai. The guide itself writes the .first_run_complete flag when the
        user finishes (or skips) the tour — replay from About never rewrites it.
        """
        flag_path = get_data_path('.first_run_complete')
        if not os.path.exists(flag_path):
            OnboardingGuide(self)
            return
        # Tour pehle complete ho chuki hai, par panchayat/villages abhi add
        # nahi hue → full tour dobara mat chalao, seedha Panchayat step kholo.
        if not self._has_saved_panchayats():
            OnboardingGuide(self, start_step=3)

    def _has_saved_panchayats(self) -> bool:
        """True jab Settings > Location Data me koi panchayat/village saved ho
        (history me). Panchayat add hone par hi onboarding nag karna band.
        Keys settings_tab.PANCHAYAT_KEYS/VILLAGE_KEYS se aati hain — single
        source of truth (lazy import, tab module heavy nahi hai)."""
        try:
            from src.tabs.settings_tab import PANCHAYAT_KEYS, VILLAGE_KEYS
            hm = self.history_manager
            for k in (*PANCHAYAT_KEYS, *VILLAGE_KEYS):
                if hm.get_suggestions(k):
                    return True
        except Exception as e:
            logger.warning("Could not check saved panchayats: %s", e)
        return False

    def _gc_collection_loop(self) -> None:
        """P6: Periodic garbage collection to prevent memory fragmentation.
        Runs gc.collect() every 5 minutes during long app sessions.
        gc.freeze() at startup prevents scanning startup objects,
        so this only collects cycles created during runtime.

        M3: Also prunes completed thread references from automation_threads
        so thread objects can be garbage collected.
        """
        try:
            # Only collect if the app window still exists
            if self.winfo_exists():
                collected = gc.collect()
                if collected > 0:
                    logger.info("GC Collected %s objects (periodic cleanup)", collected)

                # M3: Prune dead thread entries so completed thread objects
                # are no longer held by the dict and can be garbage collected.
                dead_threads = [
                    key for key, thread in self.app_state.automation_threads.items()
                    if not thread.is_alive()
                ]
                for key in dead_threads:
                    self.app_state.automation_threads.pop(key, None)
                if dead_threads:
                    logger.debug("Pruned %s completed thread(s) from automation_threads", len(dead_threads))

        except Exception as e:
            logger.debug("GC collection failed: %s", e)
        # Schedule next run in 5 minutes (300000ms)
        try:
            if self.winfo_exists():
                self.app_state._gc_timer_id = self.after(300000, self._gc_collection_loop)
        except Exception as e:
            logger.debug("Failed to schedule next GC collection: %s", e)

    def on_closing(self, force: bool = False) -> None:
        """Handles application shutdown gracefully and cleans up browsers."""
        if force or messagebox.askokcancel("Quit", "Quit application?", parent=self):
            # Stop performance monitor updates
            try:
                if hasattr(self, 'performance_monitor'):
                    self.performance_monitor.stop()
            except Exception as e:
                logger.debug("Failed to stop performance monitor during shutdown: %s", e)

            # Cancel periodic GC timer
            if self.app_state._gc_timer_id:
                try:
                    self.after_cancel(self.app_state._gc_timer_id)
                except Exception as e:
                    logger.warning("Failed to cancel GC timer during shutdown: %s", e)

            try:
                self.play_sound("shutdown")
                # Kill lingering audio process immediately (no orphan afplay)
                if hasattr(self, 'sound_manager'):
                    self.sound_manager.cleanup()
                self.attributes("-alpha", 0.0) # Hide window immediately
            except Exception as e:
                logger.warning("Failed to play shutdown sound or hide window: %s", e)

            # Force garbage collection before exit
            gc.collect()

            # Cleanup zombie browser process
            try:
                if self.app_state.driver:
                    self.app_state.driver.quit()
            except Exception as e:
                logger.debug("Failed to quit browser driver during shutdown: %s", e)

            # Force Kill Process
            import os
            os._exit(0)


    def _fetch_app_config(self):
        # Deprecated: Now merged into _ping_server_in_background sync_worker
        pass

    def check_for_updates_background(self) -> None:
        self.services.check_for_updates_background()

    def show_update_prompt(self, version, is_hotfix=False):
        if config.BETA_BUILD:
            return  # Beta builds never prompt for updates
        self.play_sound("update")
        if is_hotfix:
            msg = f"A bug-fix update for v{version} is available. View?"
        else:
            msg = f"Version {version} available. View?"
        if messagebox.askyesno("Update", msg):
            self.show_frame("About"); self.app_state.tab_instances.get("About").tab_view.set("Updates")

    def download_and_install_update(self, url: str, version: str) -> None:
        if config.BETA_BUILD:
            self.show_toast("Updates are disabled in this Beta build.", kind="info")
            return
        self.services.download_and_install_update(url, version)

    def _apply_smart_update(self, zip_path):
        import zipfile

        if sys.platform == "darwin":
            try:
                from appdirs import user_data_dir

                local_dir = user_data_dir("NREGABot", "PoddarSolutions")
                core_zip_path = os.path.join(local_dir, "core.zip")
                version_file = os.path.join(local_dir, "core_version.json")

                self.play_sound("update")

                if os.path.exists(core_zip_path):
                    os.remove(core_zip_path)

                shutil.copy2(zip_path, core_zip_path)

                try:
                    new_ver = self.app_state.update_info.get('version', '0.0.0')
                    new_hash = self.app_state.update_info.get('hash', '') or ''
                    with open(version_file, 'w') as f:
                        json.dump({"version": new_ver, "hash": new_hash}, f)
                except Exception:
                    logger.warning("Failed to write version file: %s", version_file)

                try: os.remove(zip_path)
                except Exception as e: logger.debug("Failed to remove old zip file: %s", e)

                messagebox.showinfo("Update Ready", "Update applied successfully.\nThe application will now restart.")

                # IMPORTANT ORDER: on_closing(force=True) calls os._exit(0) which
                # kills this process IMMEDIATELY — so the relaunch MUST be
                # scheduled BEFORE it, or Popen below never runs and the app
                # silently closes without restarting.
                # Also, run_application() has a single-instance socket guard
                # (port 60123): a freshly spawned instance sees the still-alive
                # old process, sends 'focus', and exits. Delay the relaunch ~2s
                # so the old process fully exits and frees the port first.
                try:
                    subprocess.Popen(
                        ["sh", "-c", f'sleep 2; exec "{sys.executable}"'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    subprocess.Popen([sys.executable])
                self.on_closing(force=True)  # os._exit(0) — old process ends, port freed
                sys.exit(0)

            except Exception as e:
                messagebox.showerror("Update Error", f"Failed to apply update:\n{e}")
                return

        extract_dir = self.get_data_path("update_temp")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            current_exe = sys.executable
            app_dir = os.path.dirname(current_exe)

            if not getattr(sys, 'frozen', False):
                messagebox.showinfo("Dev Mode", "Update extracted to 'update_temp'. Cannot auto-restart in dev mode.")
                return

            self.play_sound("update")
            messagebox.showinfo("Update Ready", "Application will restart to apply changes.")

            batch_script_path = self.get_data_path("updater.bat")
            script_content = f"""
@echo off
title Updating NREGA Bot...
echo Waiting for application to close...
timeout /t 2 /nobreak > NUL

echo Installing updates...
xcopy /s /y "{extract_dir}\\*" "{app_dir}\\"

echo Cleaning up...
rmdir /s /q "{extract_dir}"
del "{zip_path}"

echo Restarting Application...
start "" "{current_exe}"

echo Done.
del "%~f0" & exit
"""
            with open(batch_script_path, "w") as bat:
                bat.write(script_content)
            os.startfile(batch_script_path)

            # Record the applied version + zip hash so the loader does not
            # re-download the same content on the next launch.
            try:
                new_ver = self.app_state.update_info.get('version', '0.0.0')
                new_hash = self.app_state.update_info.get('hash', '') or ''
                vf = self.get_data_path("core_version.json")
                with open(vf, 'w') as f:
                    json.dump({"version": new_ver, "hash": new_hash}, f)
            except Exception as e:
                logger.debug("Failed to write version file after smart update: %s", e)

            self.on_closing(force=True)
            sys.exit(0)

        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to apply smart update:\n{e}")

    # ============================================================================
    # 4. EVENTS & INTERACTIONS
    # ============================================================================

    def _on_window_focus(self, event=None):
        if not self.app_state.is_licensed:
            return

        if self.app_state.is_validating_license:
            return

        if self.app_state._is_resizing:
            return

        if self.app_state._focus_validation_timer:
            try:
                self.after_cancel(self.app_state._focus_validation_timer)
            except Exception as e: logger.debug("Failed to cancel focus validation timer: %s", e)

        self.app_state._focus_validation_timer = self.after(2000, self._start_validation_thread)

    def _on_global_click(self, event: Any) -> None:
        """Global click listener optimized to prevent CPU usage loop lags."""
        try:
            widget = event.widget
            w_class = widget.winfo_class().lower()
            w_name = str(widget).lower()

            # Fast exit
            if "scrollbar" in w_class or "trough" in w_name or "canvas" in w_class or "slider" in w_class:
                return

            depth = 0
            while widget and depth < 4:
                if isinstance(widget, (ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkSwitch, ctk.CTkCheckBox, ctk.CTkRadioButton)):
                    btn_text = ""
                    try:
                        btn_text = widget.cget("text").lower()
                    except Exception:
                        logger.debug("Failed to read button text from nav widget", exc_info=True)

                    if "stop" in btn_text or "start automation" in btn_text: return
                    self.play_sound("click")
                    return
                widget = widget.master
                depth += 1
        except Exception:
            pass

    def get_data_path(self, filename): return get_data_path(filename)
    def get_user_downloads_path(self) -> str: return get_user_downloads_path()
    def get_nregabot_path(self, subdir: str = "") -> str: return get_nregabot_path(subdir)
    def get_report_path(self, category: str = "", fin_year: str = "") -> str:
        return get_report_path(category, fin_year)

    def open_folder(self, path):
        try:
            if os.path.exists(path):
                if sys.platform == "win32": os.startfile(path)
                else: subprocess.call(["open" if sys.platform == "darwin" else "xdg-open", path])
        except Exception as e:
            self.play_sound("error")
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def open_web_file_manager(self):
        # Secure path: signed token fetch → browser (raw key kabhi URL mein nahi)
        self.open_web_page('files')

    def save_demo_csv(self, file_type: str):
        try:
            # Demo CSVs live in assets/demo/ (they were moved into that
            # subfolder; the old flat path is kept as a fallback).
            src = resource_path(f"assets/demo/demo_{file_type}.csv")
            if not os.path.exists(src):
                src = resource_path(f"assets/demo_{file_type}.csv")
            if not os.path.exists(src): self.play_sound("error"); messagebox.showerror("Error", "Demo file not found"); return
            demo_dir = self.get_nregabot_path("Demo")
            save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialdir=demo_dir, initialfile=f"{file_type}_data.csv")
            if save_path: shutil.copyfile(src, save_path); self.play_sound("success"); messagebox.showinfo("Success", f"Demo file saved to:\n{save_path}")
        except Exception as e: self.play_sound("error"); messagebox.showerror("Error", str(e))

    def play_sound(self, sound_name: str):
        self.sound_manager.play(sound_name)

    def show_toast(self, message, kind="success", duration=4000, title="", details=""):
        try:
            if not self.winfo_exists():
                return

            # Multiple toasts stack gracefully (max 3) — the previous toast is
            # NOT force-destroyed here; ToastNotification manages the queue.

            auto_kind = kind
            if not title:
                if kind == "success": title = "Success"
                elif kind == "error": title = "Error"
                elif kind == "info": title = "Info"
                elif kind == "warning": title = "Warning"
                elif kind == "automation": title = "Automation"
                elif kind == "running": title = "Running"

            # Play appropriate sound
            sound_map = {
                "success": "complete",
                "error": "error",
                "warning": "error",
                "automation": "complete",
                "running": "click",
            }
            self.play_sound(sound_map.get(kind, "click"))

            try:
                self.app_state.current_toast = ToastNotification(
                    self, message, kind=kind, duration=duration,
                    title=title, details=details
                )
            except Exception:
                pass

        except Exception as e:
            logger.warning("Toast Error: %s", e)

    def set_status(self, message, color=None):
        if self.status_label:
            message_lower = message.lower()
            final_color = color
            should_animate = False
            if final_color is None:
                if any(x in message_lower for x in ["running", "starting", "navigating", "processing", "loading"]):
                    final_color = "#3B82F6"; should_animate = True
                elif "finished" in message_lower: final_color = "#E53E3E"
                elif "ready" in message_lower:
                    final_color = "#38A169"
                    if message == "Ready": self.play_sound("success")
                elif "error" in message_lower or "failed" in message_lower:
                    final_color = "#E53E3E"
                    if not "session expired" in message_lower: self.play_sound("error")
                else: final_color = "gray50"

            if should_animate and not self.app_state.is_animating:
                self.app_state.is_animating = True; self._animate_loading_icon()
            elif not should_animate: self.app_state.is_animating = False

            self.status_label.configure(text=f"Status: {message}", text_color=final_color)
            if not self.app_state.is_animating and self.loading_animation_label: self.loading_animation_label.configure(text="")

    def _animate_loading_icon(self, frame_index=0):
        if not self.app_state.is_animating:
            if self.loading_animation_label: self.loading_animation_label.configure(text="")
            return
        frames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
        if self.loading_animation_label: self.loading_animation_label.configure(text=frames[frame_index])
        # Optimized animation speed
        self.after(200, self._animate_loading_icon, (frame_index + 1) % len(frames))

    def set_server_status(self, is_connected: bool):
        if self.server_status_indicator: self.server_status_indicator.configure(fg_color="green" if is_connected else "red")
        # Also update About tab's header banner if loaded
        about_tab = self.app_state.tab_instances.get("About")
        if about_tab:
            color = "green" if is_connected else "red"
            text = "Connected" if is_connected else "Disconnected"
            try:
                if hasattr(about_tab, 'server_dot') and about_tab.server_dot.winfo_exists():
                    about_tab.server_dot.configure(fg_color=color)
                if hasattr(about_tab, 'server_status_label') and about_tab.server_status_label.winfo_exists():
                    about_tab.server_status_label.configure(text=text)
            except Exception as e:
                logger.debug("Failed to update About tab server status: %s", e)

    def bring_to_front(self):
        """Brings the app window to the front (and de-minimizes it).
        Panchayat scrape / automation ke baad focus wapas app par laane ke
        liye use hota hai — user Chrome pe na atak jaye."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _get_work_area(self) -> Tuple[int, int, int, int]:
        if config.OS_SYSTEM == "Windows":
            try:
                SPI_GETWORKAREA = 0x0030
                rect = (ctypes.c_long * 4)()
                ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
                return (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
            except Exception:
                logger.debug("Failed to query Windows work area, using fallback", exc_info=True)
        return (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())

    def _get_machine_id(self) -> str:
        return self.services.machine_id

    def log_message(self, log, msg, level="info"):
        """Append a timestamped message to a log textbox.

        Safe to call with a destroyed widget — checks winfo_exists()
        first to prevent TclError: invalid command name.
        """
        try:
            if not log.winfo_exists():
                return
        except Exception:
            return
        try:
            log.configure(state="normal")
            log.insert(tkinter.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            log.configure(state="disabled")
            log.see(tkinter.END)
        except Exception:
            pass

    def clear_log(self, log):
        """Clear all content from a log textbox.

        Safe to call with a destroyed widget — checks winfo_exists()
        first to prevent TclError: invalid command name.
        """
        try:
            if not log.winfo_exists():
                return
        except Exception:
            return
        try:
            log.configure(state="normal")
            log.delete("1.0", tkinter.END)
            log.configure(state="disabled")
        except Exception:
            pass

    def update_history(self, key, val): self.history_manager.save_entry(key, val)
    def remove_history(self, key, val): self.history_manager.remove_entry(key, val)

    def on_theme_change(self, new_theme: str):
        ctk.set_appearance_mode(new_theme)
        if hasattr(self, '_sync_root_background'):
            self._sync_root_background()
        self.after(100, self.restyle_all_treeviews)
    def restyle_all_treeviews(self):
        # Only restyle treeviews that have actually been instantiated.
        # Lazy-loaded tabs that were never shown don't need style updates.
        for tab in self.app_state.tab_instances.values():
            if hasattr(tab, 'style_treeview'):
                # Only restyle if the tab actually exists and has visible treeviews
                if hasattr(tab, 'results_tree'):
                    try:
                        if tab.results_tree.winfo_exists():
                            tab.style_treeview(tab.results_tree)
                    except Exception:
                        pass
                if hasattr(tab, 'files_tree'):
                    try:
                        if tab.files_tree.winfo_exists():
                            tab.style_treeview(tab.files_tree)
                    except Exception:
                        pass

    # ============================================================================
    # 6. BACKWARD-COMPATIBLE STATE PROPERTIES
    # A4: These properties allow the 40+ tab files accessing self.app.<attr>
    # to continue working without modification, while the actual state lives
    # in self.app_state.<attr> (AppState dataclass).
    # ============================================================================

    @property
    def stop_events(self) -> Dict[str, Any]:
        return self.app_state.stop_events

    @stop_events.setter
    def stop_events(self, value: Dict[str, Any]) -> None:
        self.app_state.stop_events = value

    @property
    def http_session(self) -> Any:
        return self.app_state.http_session

    @http_session.setter
    def http_session(self, value: Any) -> None:
        self.app_state.http_session = value

    @property
    def active_browser(self) -> Optional[str]:
        return self.app_state.active_browser

    @active_browser.setter
    def active_browser(self, value: Optional[str]) -> None:
        self.app_state.active_browser = value

    @property
    def machine_id(self) -> str:
        return self.app_state.machine_id

    @machine_id.setter
    def machine_id(self, value: str) -> None:
        self.app_state.machine_id = value

    @property
    def sound_switch_var(self) -> Any:
        """Forward to app_state so SoundManager.play() can read the live
        toggle (it checks self.app.sound_switch_var). Without this property
        the mute guard never ran and sound kept playing even when off."""
        return self.app_state.sound_switch_var

    @sound_switch_var.setter
    def sound_switch_var(self, value: Any) -> None:
        self.app_state.sound_switch_var = value

    @property
    def tab_instances(self) -> Dict[str, Any]:
        return self.app_state.tab_instances

    @tab_instances.setter
    def tab_instances(self, value: Dict[str, Any]) -> None:
        self.app_state.tab_instances = value

    @property
    def active_automations(self) -> Set[str]:
        return self.app_state.active_automations

    @active_automations.setter
    def active_automations(self, value: Set[str]) -> None:
        self.app_state.active_automations = value

    @property
    def update_info(self) -> Dict[str, Any]:
        return self.app_state.update_info

    @update_info.setter
    def update_info(self, value: Dict[str, Any]) -> None:
        self.app_state.update_info = value

    @property
    def license_info(self) -> Dict[str, Any]:
        return self.app_state.license_info

    @license_info.setter
    def license_info(self, value: Dict[str, Any]) -> None:
        self.app_state.license_info = value

    @property
    def is_licensed(self) -> bool:
        return self.app_state.is_licensed

    @is_licensed.setter
    def is_licensed(self, value: bool) -> None:
        self.app_state.is_licensed = value

    @property
    def driver(self) -> Any:
        return self.app_state.driver

    @driver.setter
    def driver(self, value: Any) -> None:
        self.app_state.driver = value

    @property
    def is_validating_license(self) -> bool:
        return self.app_state.is_validating_license

    @is_validating_license.setter
    def is_validating_license(self, value: bool) -> None:
        self.app_state.is_validating_license = value

    @property
    def global_disabled_features(self) -> Union[List[str], Dict[str, Any]]:
        return self.app_state.global_disabled_features

    @global_disabled_features.setter
    def global_disabled_features(self, value: Union[List[str], Dict[str, Any]]) -> None:
        self.app_state.global_disabled_features = value

    @property
    def trial_restricted_features(self) -> List[str]:
        return self.app_state.trial_restricted_features

    @trial_restricted_features.setter
    def trial_restricted_features(self, value: List[str]) -> None:
        self.app_state.trial_restricted_features = value

    # ============================================================================
    # 7. CUSTOM MESSAGE BOX OVERRIDES
    # ============================================================================

# ============================================================================
# MAIN EXECUTION ENTRY POINT
# ============================================================================

def run_application():
    logging.basicConfig(level=logging.INFO)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 60123))
    except:
        try:
            s.connect(("127.0.0.1", 60123))
            s.sendall(b'focus')
            s.close()
        except Exception as e: logger.debug("Failed to send focus signal via socket: %s", e)
        sys.exit(0)

    try:
        app = NregaBotApp()

        def listen():
            s.listen(1)
            while True:
                try:
                    c, a = s.accept()
                    d = c.recv(1024)
                    if d == b'focus':
                        app.after(0, app.bring_to_front)
                    c.close()
                except (OSError, ValueError):
                    break
        threading.Thread(target=listen, daemon=True).start()

        app.mainloop()

    except Exception as e:
        messagebox.showerror("Fatal Error", str(e))
    finally:
        s.close()

if __name__ == '__main__':
    run_application()