# lite_app.py
# NREGA Bot Lite — Lightweight version for low-end devices.
#
# This is a separate entry point that creates a streamlined version
# of the application with:
#   - Only essential tabs (no Macros, File Manager, Feedback, etc.)
#   - No splash screen animations
#   - No sound effects
#   - No onboarding guide
#   - No performance monitor
#   - Unicode emoji icons instead of PNG image files (faster, lighter)
#   - Simplified UI with fewer transitions
#
# Run with:
#   python lite_app.py
#
# Build with PyInstaller:
#   pyinstaller --name="NREGABotLite" --windowed lite_app.py

# ============================================================================
# IMPORTS
# ============================================================================

import threading
import os
import webbrowser
import sys
import json
import logging
import socket
import gc
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import tkinter
from tkinter import messagebox
import customtkinter as ctk
import requests




# --- Apply Lite config overrides FIRST ---
from src import config
from src import lite_config
lite_config.apply_overrides()

# --- Lite-specific imports ---
from src.ui_components import ToastNotification
from src.managers.services import ServiceManager
from src.lite_tab_config import get_tabs_definition_lite
from src.managers.icon_manager import create_icon_manager
from src.app.app_license import LicenseMixin
from src.utils import (
    resource_path, get_data_path, get_user_downloads_path,
    get_config, save_config, validate_config,
    setup_logging, get_logger, _suppress_overscroll
)

# --- Windows DPI Awareness ---
if config.OS_SYSTEM == "Windows":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ============================================================================
# SETUP
# ============================================================================

setup_logging()
logger = get_logger()

config.create_default_config_if_not_exists()
validate_config()

ctk.set_default_color_theme(resource_path(os.path.join("config", "theme.json")))
ctk.set_appearance_mode("System")




class NregaBotLiteApp(ctk.CTk, LicenseMixin):
    """
    Lightweight version of NREGA Bot for low-end devices.
    
    Removed:
    - NavMixin (simplified tab switching)
    - AutomationMixin (simplified)
    - UIMixin (simplified UI)
    - PerformanceMonitor
    - Onboarding
    - Sound effects (except essential)
    - Animations & transitions
    - PNG image icons (uses Unicode emoji characters instead)
    """

    def __init__(self) -> None:
        super().__init__()
        
        # NOTE: CTk.__init__ already calls self.withdraw() internally.
        # We do NOT call self.withdraw() again — macOS has a known Tk bug
        # where withdraw+deiconify breaks mouse event delivery.
        # Instead, the splash is built as an internal Frame that covers
        # the window until the real UI is ready.

        self.title(f"{config.APP_NAME}")
        
        self.initial_width = 920
        self.initial_height = 680
        self.minsize(800, 550)
        
        self.configure(bg=config.COLORS["bg_dark"])
        
        # --- State ---
        self.http_session = requests.Session()
        self.stop_events: Dict[str, Any] = {}
        self.tab_instances: Dict[str, Any] = {}
        self.active_automations: Set[str] = set()
        self.automation_threads: Dict[str, Any] = {}
        self.license_info: Dict[str, Any] = {}
        self.update_info: Dict[str, Any] = {"status": "Checking...", "version": None, "url": None}
        self.is_licensed = False
        self.is_validating_license = False
        self.global_disabled_features: Union[List[str], Dict[str, Any]] = []
        self.trial_restricted_features: List[str] = []
        self.driver: Any = None
        self.active_browser: Optional[str] = None
        self.current_toast: Any = None
        self.status_label: Any = None
        self.server_status_indicator: Any = None
        self.announcement_label: Any = None
        self.nav_buttons: Dict[str, Any] = {}
        self.button_to_category_frame: Dict[str, Any] = {}
        self.category_frames: Dict[str, Any] = {}
        # For compatibility with tab files accessing self.app.app_state.xxx
        self._app_state_fallback: Dict[str, Any] = {}

        # --- Lazy-init placeholders (created on first access) ---
        self._browser_manager: Any = None
        self._workflows: Any = None
        self._history_manager: Any = None

        # --- Services (must init BEFORE _get_machine_id) ---
        self.services = ServiceManager(self)
        self.machine_id: str = self._get_machine_id()
        self.sound_manager = None  # No sounds in Lite

        # --- Internal state ---
        self._window_shown: bool = False

        # --- Icons (minimal set, for tab compatibility only) ---
        self.icon_images = create_icon_manager()

        # --- Splash frame (in-window, not a Toplevel child) ---
        # macOS Tk bug: a Toplevel child of a withdrawn parent can break
        # event delivery to the main window. Using a Frame instead avoids
        # this entirely.
        self._splash_frame = self._create_splash_frame()
        self._splash_frame.pack(expand=True, fill="both")

        # Show splash at FINAL app size — prevents visible resize flicker
        # when UI replaces the splash later.
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self._final_w = min(self.initial_width, sw - 40)
        self._final_h = min(self.initial_height, sh - 40)
        self._final_w = max(self._final_w, 850)
        self._final_h = max(self._final_h, 600)
        fx = (sw // 2) - (self._final_w // 2)
        fy = (sh // 2) - (self._final_h // 2)
        self.geometry(f'{self._final_w}x{self._final_h}+{int(fx)}+{int(fy)}')
        self.deiconify()
        self.update()

        # --- GC ---
        gc.set_threshold(*getattr(config, 'GC_THRESHOLD', (700, 10, 5)))
        gc.freeze()

        # --- Start background init ---
        self.after(10, self._build_ui_on_main_thread)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ============================================================================
    # LAZY PROPERTIES — heavy managers are created only on first access
    # ============================================================================

    @property
    def browser_manager(self) -> Any:
        """Lazy-initialized BrowserManager."""
        if self._browser_manager is None:
            from src.managers.browser_manager import BrowserManager
            self._browser_manager = BrowserManager(self)
        return self._browser_manager

    @browser_manager.setter
    def browser_manager(self, value: Any) -> None:
        self._browser_manager = value

    @property
    def workflows(self) -> Any:
        """Lazy-initialized WorkflowManager."""
        if self._workflows is None:
            from src.managers.workflow_manager import WorkflowManager
            self._workflows = WorkflowManager(self)
        return self._workflows

    @workflows.setter
    def workflows(self, value: Any) -> None:
        self._workflows = value

    @property
    def history_manager(self) -> Any:
        """Lazy-initialized HistoryManager."""
        if self._history_manager is None:
            from src.tabs.history_manager import HistoryManager
            self._history_manager = HistoryManager(self.get_data_path)
        return self._history_manager

    @history_manager.setter
    def history_manager(self, value: Any) -> None:
        self._history_manager = value
        
    def _create_splash_frame(self) -> ctk.CTkFrame:
        """Create a polished in-window splash — shown while UI loads.
        Uses all pack() (no place/grid mix) for consistent layout
        across platforms. Centered branding, subtle loading bar.
        """
        splash = ctk.CTkFrame(self, corner_radius=0,
                              fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))

        # Top spacer pushes center content down
        ctk.CTkFrame(splash, fg_color="transparent").pack(expand=True, fill="both")

        # Center branding block
        ctk.CTkLabel(
            splash, text="🏛️",
            font=ctk.CTkFont(size=36)
        ).pack()

        ctk.CTkLabel(
            splash, text=config.APP_NAME,
            font=ctk.CTkFont(family="Helvetica Neue", size=24, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"])
        ).pack(pady=(8, 2))

        ctk.CTkLabel(
            splash, text="Lightweight Edition",
            font=ctk.CTkFont(size=12),
            text_color=(config.COLORS["blue_hover"], config.COLORS["blue_light"])
        ).pack()

        # Bottom spacer keeps content centered
        ctk.CTkFrame(splash, fg_color="transparent").pack(expand=True, fill="both")

        # Loading bar just above bottom
        bar_frame = ctk.CTkFrame(splash, fg_color="transparent")
        bar_frame.pack(side="bottom", fill="x", padx=40, pady=(0, 22))

        progress = ctk.CTkProgressBar(
            bar_frame, height=3, corner_radius=2,
            mode="indeterminate",
            fg_color=("#E5E7EB", "#374151"),
            progress_color=(config.COLORS["blue_hover"], config.COLORS["blue_light"])
        )
        progress.pack(fill="x")
        progress.start()

        # Version at very bottom
        ctk.CTkLabel(
            splash, text=f"v{config.APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"])
        ).pack(side="bottom", pady=(0, 6))

        return splash

    def _build_ui_on_main_thread(self) -> None:
        """Build the UI structure.
        First destroy the splash frame so it doesn't conflict with
        _build_ui() which uses grid() on self (splash frame uses pack()).
        Once built, show main window properly sized.
        """
        # Destroy the in-window splash frame FIRST so self is free
        # for _build_ui() which uses grid() — pack + grid on same
        # parent causes TclError.
        if self._splash_frame:
            try:
                self._splash_frame.destroy()
            except Exception:
                pass
            self._splash_frame = None

        self._build_ui()
        self.app_state._layout_ready = True

        # Resize window to full size and ensure proper focus
        # (window was small for the splash)
        self._show_window()

        # Brief pause then run license check
        self.after(50, self._run_license_check)

    def _run_license_check(self) -> None:
        """Handle license validation after window is shown."""
        self.is_licensed = self.services.check_license()
        
        if self.is_licensed:
            self._on_licensed()
        else:
            self._show_frame_about()
            self.set_status("Activation Required")
            if self.show_activation_window():
                self.is_licensed = True
                self._on_licensed()
            else:
                self.on_closing(force=True)
                return

    def _build_ui(self) -> None:
        """Simplified UI — header, sidebar, content area, footer."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Header (flattened — no redundant branding wrapper) ---
        header = ctk.CTkFrame(self, corner_radius=0, fg_color=("#FFFFFF", "#1D1E1E"))
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        # App logo — load from PNG (16px instead of main app's 20px)
        try:
            from PIL import Image as PILImage
            logo_path = resource_path("assets/icons/nrega.png")
            pil_img = PILImage.open(logo_path)
            logo_img = ctk.CTkImage(pil_img, size=(16, 16))
            ctk.CTkLabel(header, image=logo_img, text="").pack(side="left", padx=(8, 2))
        except Exception:
            ctk.CTkLabel(header, text="🏛️", font=ctk.CTkFont(size=18)).pack(side="left", padx=(10, 2))
        ctk.CTkLabel(header, text=config.APP_NAME, font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text=f"v{config.APP_VERSION}", font=ctk.CTkFont(size=10), text_color="gray60").pack(side="left", padx=(5, 0))

        # Spacer pushes controls to the right
        ctk.CTkLabel(header, text="", width=0).pack(side="left", fill="x", expand=True)

        # Header action buttons
        for label, cmd in [
            ("🌐 Chrome", self.launch_chrome_detached),
            ("🦊 Firefox", self.launch_firefox_managed),
        ]:
            ctk.CTkButton(
                header, text=label,
                width=80, height=28, corner_radius=6,
                fg_color="transparent",
                text_color=("#333333", "#D1D5DB"),
                hover_color=("gray90", "gray30"),
                command=cmd, font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=2)

        ctk.CTkFrame(header, width=1, height=18, fg_color=("gray80", "gray50")).pack(side="left", padx=4)

        ctk.CTkButton(
            header, text="🔧 Extract",
            width=80, height=28, corner_radius=6,
            fg_color=("#E8F5E9", "#2E7D32"),
            hover_color=("#C8E6C9", "#1B5E20"),
            text_color=("#2E7D32", "#A5D6A7"),
            command=lambda: self.show_frame("Workcode Extractor"),
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(side="left", padx=2)

        # --- Main Layout ---
        main = ctk.CTkFrame(self, corner_radius=0)
        main.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 5))
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)

        # Sidebar — lightweight scrollable nav
        sidebar = ctk.CTkFrame(main, width=180, corner_radius=0, fg_color="transparent")
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_propagate(False)

        # Sidebar header
        nav_header = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        ctk.CTkLabel(
            nav_header, text="📋  Navigation",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray50", "gray55")
        ).pack(side="left")

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=("gray80", "gray35")).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 4)
        )

        self.nav_scroll = ctk.CTkScrollableFrame(
            sidebar,
            corner_radius=0,
            fg_color="transparent",
            scrollbar_button_color=("#BDBDBD", "#555555"),
            scrollbar_button_hover_color=("#9E9E9E", "#666666"),
        )
        self.nav_scroll.grid(row=2, column=0, sticky="nsew")
        _suppress_overscroll(self.nav_scroll)

        # Content area — single container that never gets destroyed
        self.content_area = ctk.CTkFrame(main, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self._tab_container = ctk.CTkFrame(self.content_area, corner_radius=0)
        self._tab_container.grid(row=0, column=0, sticky="nsew")
        self._tab_container.grid_rowconfigure(0, weight=1)
        self._tab_container.grid_columnconfigure(0, weight=1)

        # Navigation buttons
        self._create_nav_buttons()

        # NOTE: Resize overlay is disabled for now — it was causing
        # click-interception issues on macOS (Configure event storms).
        # self._create_resize_overlay()

        # --- Footer ---
        footer = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color=("#FFFFFF", "#2B2B2B"))
        footer.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))
        footer.grid_propagate(False)
        footer.grid_columnconfigure(0, weight=1)

        # Left: status
        self.status_label = ctk.CTkLabel(footer, text="Ready", text_color="gray60", font=ctk.CTkFont(size=11))
        self.status_label.grid(row=0, column=0, sticky="w", padx=10)

        # Center: Copyright
        ctk.CTkLabel(
            footer, text="© 2025 NREGA Bot",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray50")
        ).grid(row=0, column=0, sticky="")

        # Right: server status indicator
        self.server_status_indicator = ctk.CTkFrame(footer, width=8, height=8, corner_radius=4, fg_color="gray")
        self.server_status_indicator.grid(row=0, column=0, sticky="e", padx=10)

    def _create_nav_buttons(self) -> None:
        """Create sidebar navigation from lite_tab_config using emoji text icons."""
        self.nav_buttons.clear()
        # Use nav_scroll directly — CTkScrollableFrame supports
        # placing CTkButton/CTkLabel widgets natively.
        nav_parent = self.nav_scroll
        tabs = self._get_cached_tabs()
        
        for cat_name, cat_tabs in tabs.items():
            if cat_name == "Dashboard":
                # Pin Home button at top with emoji
                for name, data in cat_tabs.items():
                    emoji = data.get("icon", "")
                    btn_text = f"{emoji}  {name}" if emoji else name
                    btn = ctk.CTkButton(
                        nav_parent, text=btn_text,
                        compound="left", anchor="w",
                        font=ctk.CTkFont(size=12, weight="bold"),
                        height=30, corner_radius=6,
                        fg_color="transparent",
                        text_color=("#1565C0", "#60A5FA"),
                        hover_color=("#BBDEFB", "#4B5563"),
                        command=lambda n=name: self.show_frame(n)
                    )
                    btn.pack(fill="x", padx=5, pady=2)
                    self.nav_buttons[name] = btn
                # Separator
                ctk.CTkFrame(nav_parent, height=1, fg_color=("gray85", "gray35")).pack(fill="x", padx=15, pady=5)
            else:
                # Category label
                ctk.CTkLabel(
                    nav_parent, text=cat_name,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=("gray50", "gray60")
                ).pack(fill="x", padx=10, pady=(5, 2))
                
                for name, data in cat_tabs.items():
                    emoji = data.get("icon", "")
                    btn_text = f"{emoji}  {name}" if emoji else name
                    btn = ctk.CTkButton(
                        nav_parent, text=btn_text,
                        compound="left", anchor="w",
                        font=ctk.CTkFont(size=12),
                        height=28, corner_radius=6,
                        fg_color="transparent",
                        text_color=("gray30", "gray80"),
                        hover_color=("gray90", "gray25"),
                        command=lambda n=name: self.show_frame(n)
                    )
                    btn.pack(fill="x", padx=8, pady=1)
                    self.nav_buttons[name] = btn

    def show_frame(self, page_name: str) -> None:
        """Load and show a tab (lazy loading) into reusable container.
        No per-tab CTkFrame wrappers — saves memory and creation time.
        """
        # If already loaded, just raise the existing widget
        if page_name in self.tab_instances:
            self.tab_instances[page_name].tkraise()
            self._update_nav_highlight(page_name)
            return

        # Load new tab into the reusable container
        tabs = self._get_cached_tabs()
        for cat, tab_items in tabs.items():
            if page_name in tab_items:
                instance = tab_items[page_name]["creation_func"](self._tab_container, self)
                instance.grid(row=0, column=0, sticky="nsew")

                self.tab_instances[page_name] = instance
                instance.tkraise()
                self._update_nav_highlight(page_name)
                return

    def _get_cached_tabs(self) -> Dict[str, Dict[str, Any]]:
        """Return cached tab definitions — built once, reused forever."""
        if self._tabs_cache is None:
            self._tabs_cache = get_tabs_definition_lite(self)
        return self._tabs_cache

    def _update_nav_highlight(self, page_name: str) -> None:
        """Highlight the active nav button."""
        for name, btn in self.nav_buttons.items():
            if name == page_name:
                btn.configure(fg_color=("#E3F2FD", "#374151"),
                              text_color=("#1565C0", "#60A5FA"),
                              font=ctk.CTkFont(size=12, weight="bold"))
            else:
                btn.configure(fg_color="transparent",
                              text_color=("gray30", "gray80"),
                              font=ctk.CTkFont(size=12))

    def _show_window(self) -> None:
        """Activate the fully-built window with proper macOS focus.
        No geometry change needed — splash already set the final size.
        On macOS, focus_force() is critical because focus_set() doesn't
        always activate the window.
        """
        self._initial_geometry_set = True  # Prevent CTk's 20ms timer from overriding our geometry

        self.deiconify()  # Already shown, but safe no-op
        self.update()
        self.focus_force()
        self.lift()
        self._window_shown = True

    def _on_licensed(self) -> None:
        """Set up UI for licensed user.
        Show Home directly — no About preload that could cause flicker.
        About tab loads lazily when user clicks it.
        """
        self.set_status("Ready")
        self.show_frame("Home")
        # Start periodic GC collection after a short delay
        self.after(5000, self._gc_collection_loop)

    def get_tabs_definition(self) -> Dict[str, Dict[str, Any]]:
        """Delegate to lite_tab_config - HomeTab and other tabs call this."""
        return get_tabs_definition_lite(self)

    def _show_frame_about(self) -> None:
        """Preload About tab in background."""
        if "About" not in self.tab_instances:
            self.show_frame("About")

    # ============================================================================
    # BROWSER METHODS (delegated)
    # ============================================================================

    def get_driver(self) -> Any:
        driver = self.browser_manager.get_driver()
        if driver:
            self.driver = self.browser_manager.driver
            self.active_browser = self.browser_manager.active_browser
        return driver

    def launch_chrome_detached(self, target_urls: Optional[List[str]] = None) -> None:
        self.browser_manager.launch_chrome_detached(target_urls)

    def launch_firefox_managed(self) -> None:
        self.browser_manager.launch_firefox_managed()

    def _quick_login_automation(self) -> None:
        """Simplified quick login - launches Chrome to NREGA login page."""
        login_url = "https://vbgramgde2.dord.gov.in/VBGRAMG/Login.aspx?&level=HomePO&state_code=34"
        self.launch_chrome_detached(target_urls=[login_url])

    def prevent_sleep(self) -> None:
        self.services.prevent_sleep()

    def allow_sleep(self) -> None:
        self.services.allow_sleep()

    # ============================================================================
    # AUTOMATION (simplified)
    # ============================================================================

    def start_automation_thread(self, key: str, target: Any, args: tuple = ()) -> None:
        if self.automation_threads.get(key) and self.automation_threads[key].is_alive():
            messagebox.showwarning("Busy", "Task running")
            return

        self.active_automations.add(key)
        self.stop_events[key] = threading.Event()

        tab_instance = getattr(target, '__self__', None)
        if tab_instance is not None:
            tab_instance._has_automated = True

        def wrapper() -> None:
            try:
                target(*args)
            finally:
                tab_instance = getattr(target, '__self__', None)
                if tab_instance is not None and hasattr(tab_instance, 'driver'):
                    try:
                        if tab_instance.driver is not None:
                            tab_instance.driver.quit()
                    except Exception:
                        pass
                    tab_instance.driver = None
                self.after(0, self._on_automation_finished, key)

        t = threading.Thread(target=wrapper, daemon=True)
        self.automation_threads[key] = t
        t.start()

    def _on_automation_finished(self, key: str) -> None:
        self.active_automations.discard(key)
        self.set_status("Ready")

    # ============================================================================
    # UTILITY
    # ============================================================================

    def set_status(self, message: str, color=None) -> None:
        if self.status_label:
            self.status_label.configure(text=f"Status: {message}")

    def set_server_status(self, is_connected: bool) -> None:
        if self.server_status_indicator:
            self.server_status_indicator.configure(fg_color="green" if is_connected else "red")

    def show_toast(self, message: str, kind: str = "success", duration: int = 3000) -> None:
        """Simple toast notification."""
        try:
            if self.current_toast:
                try:
                    if self.current_toast.winfo_exists():
                        self.current_toast.destroy()
                except Exception:
                    pass
            self.current_toast = ToastNotification(self, message, kind, duration=duration)
        except Exception:
            pass

    def get_data_path(self, filename: str) -> str:
        return get_data_path(filename)

    def get_user_downloads_path(self) -> str:
        return get_user_downloads_path()

    def log_message(self, log, msg: str, level: str = "info") -> None:
        """Append a timestamped message to a log textbox.
        Safe to call with a destroyed widget.
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

    def update_history(self, key: str, val: Any) -> None:
        """Save an entry to usage history — needed by tabs extending BaseAutomationTab."""
        self.history_manager.save_entry(key, val)

    def remove_history(self, key: str, val: Any) -> None:
        """Remove an entry from usage history."""
        self.history_manager.remove_entry(key, val)

    def clear_log(self, log) -> None:
        """Clear all content from a log textbox. Safe to call with destroyed widget."""
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

    def play_sound(self, sound_name: str) -> None:
        """Silent in Lite version — no sound playback."""
        pass

    # ============================================================================
    # LITE ACTIVATION — Override the full version's show_activation_window
    # Simple license-key-only activation for low-end devices.
    # ============================================================================

    def show_activation_window(self) -> bool:
        """
        Lite version: polished dialog asking for a license key only.
        No email/OTP, no trial, no QR codes, no PIL — minimal & fast.
        """
        win = ctk.CTkToplevel(self)
        win.title(f"Activate {config.APP_SHORT_NAME}")
        win.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(420, sw - 40), min(320, sh - 40)
        win.geometry(f'{w}x{h}+{(sw // 2) - (w // 2)}+{(sh // 2) - (h // 2)}')
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        # --- Main container ---
        outer = ctk.CTkFrame(win, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=24, pady=24)

        # Brand header
        header_frame = ctk.CTkFrame(outer, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(header_frame, text="🏛️", font=ctk.CTkFont(size=28)).pack()
        ctk.CTkLabel(header_frame, text=f"{config.APP_SHORT_NAME}",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(2, 0))
        ctk.CTkLabel(header_frame, text="Enter your license key to activate",
                     font=ctk.CTkFont(size=12), text_color="gray60").pack(pady=(2, 0))

        # Key entry with icon-like frame
        entry_frame = ctk.CTkFrame(outer, fg_color="transparent")
        entry_frame.pack(fill="x", pady=(0, 12))
        key_entry = ctk.CTkEntry(entry_frame,
                                  placeholder_text="Paste License Key Here",
                                  font=ctk.CTkFont(size=13))
        key_entry.pack(fill="x", ipady=4)
        last_key = get_config('last_used_license_key')
        if last_key:
            key_entry.insert(0, last_key)

        # Inline status label
        status_label = ctk.CTkLabel(outer, text="", font=ctk.CTkFont(size=11), anchor="w")
        status_label.pack(fill="x", pady=(0, 8))

        # Progress bar (hidden by default)
        progress_bar = ctk.CTkProgressBar(outer, height=4, corner_radius=2,
                                           mode="indeterminate")
        # Don't pack yet — shown only during validation

        activated = tkinter.BooleanVar(value=False)

        def do_activate():
            key_val = key_entry.get().strip()
            if not key_val:
                status_label.configure(text="⚠️  Please enter a license key.",
                                       text_color=("#DC2626", "#EF4444"))
                return

            # Show progress
            progress_bar.pack(fill="x", pady=(0, 10))
            progress_bar.start()
            status_label.configure(text="⏳  Validating your license...",
                                   text_color=("#2563EB", "#60A5FA"))
            activate_btn.configure(state="disabled", text="⏳ Validating...")

            def _activate_thread():
                try:
                    payload = {
                        "key": key_val,
                        "machine_id": self.services.machine_id,
                        "app_version": config.APP_VERSION
                    }
                    resp = self.http_session.post(
                        f"{config.LICENSE_SERVER_URL}/api/validate",
                        json=payload, timeout=15
                    )
                    try:
                        data = resp.json()
                    except Exception:
                        raise Exception(
                            f"Unexpected server response (status {resp.status_code}).")

                    if resp.status_code == 200 and data.get("status") == "valid":
                        def _success():
                            if not win.winfo_exists():
                                return
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            save_config('last_used_license_key', key_val)
                            self.license_info.update({**data, 'key': key_val})
                            with open(get_data_path('license.dat'), 'w') as f:
                                json.dump(self.license_info, f)
                            self.set_server_status(True)
                            status_label.configure(text="✅  Activated successfully!",
                                                   text_color=("#059669", "#10B981"))
                            win.after(400, lambda: [activated.set(True), win.destroy()])
                        self.after(0, _success)
                    elif resp.status_code == 403 and data.get("status") == "slots_full":
                        def _full():
                            if not win.winfo_exists():
                                return
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            devices = data.get('devices', [])
                            dev_list = "\n".join(f"  • {d['name']}" for d in devices)
                            msg = (f"All device slots are full.\n\n"
                                   f"Active devices:\n{dev_list}\n\n"
                                   f"Please deactivate a device from your account page.")
                            status_label.configure(text="❌  Device slots full",
                                                   text_color=("#DC2626", "#EF4444"))
                            messagebox.showwarning("Slots Full", msg, parent=win)
                            if activate_btn.winfo_exists():
                                activate_btn.configure(state="normal", text="Activate")
                        self.after(0, _full)
                    else:
                        reason = data.get("reason", "Activation failed.")
                        def _fail():
                            if not win.winfo_exists():
                                return
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            status_label.configure(
                                text=f"❌  {reason.split(chr(10))[0][:60]}",
                                text_color=("#DC2626", "#EF4444"))
                            messagebox.showerror("Failed", reason, parent=win)
                            if activate_btn.winfo_exists():
                                activate_btn.configure(state="normal", text="Activate")
                        self.after(0, _fail)

                except Exception as e:
                    def _error():
                        if not win.winfo_exists():
                            return
                        progress_bar.stop()
                        progress_bar.pack_forget()
                        status_label.configure(text="❌  Connection error",
                                               text_color=("#DC2626", "#EF4444"))
                        messagebox.showerror("Error", str(e), parent=win)
                        if activate_btn.winfo_exists():
                            activate_btn.configure(state="normal", text="Activate")
                    self.after(0, _error)

            threading.Thread(target=_activate_thread, daemon=True).start()

        activate_btn = ctk.CTkButton(
            outer, text="Activate", command=do_activate,
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            height=40, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        activate_btn.pack(pady=(0, 4), ipady=2, fill='x')

        # Purchase link
        buy_link = ctk.CTkLabel(
            outer, text="🛒  Purchase a License Key",
            text_color=("#2563EB", "#60A5FA"), cursor="hand2",
            font=ctk.CTkFont(size=12)
        )
        buy_link.pack(pady=(8, 0))
        buy_link.bind("<Button-1>", lambda e: webbrowser.open_new_tab(
            f"{config.LICENSE_SERVER_URL}/buy"))

        self.wait_window(win)
        return activated.get()

    # ============================================================================
    # UPDATE METHODS (called by About tab and ServiceManager)
    # ============================================================================

    def check_for_updates_background(self) -> None:
        """Check for updates in a background thread."""
        self.services.check_for_updates_background()

    def show_update_prompt(self, version: str) -> None:
        """Show update notification and switch to Updates tab."""
        if messagebox.askyesno("Update", f"Version {version} available. View?"):
            self.show_frame("About")
            about_tab = self.tab_instances.get("About")
            if about_tab and hasattr(about_tab, 'tab_view'):
                about_tab.tab_view.set("Updates")

    def download_and_install_update(self, url: str, version: str) -> None:
        """Download and install an update."""
        self.services.download_and_install_update(url, version)

    def _update_about_tab_info(self) -> None:
        """Update About tab's subscription and version info after server response."""
        about_tab = self.tab_instances.get("About")
        if about_tab:
            if hasattr(about_tab, 'update_subscription_details'):
                about_tab.update_subscription_details(self.license_info)
            info = self.update_info
            if info and info.get('status') == 'available':
                try:
                    about_tab.latest_version_label.configure(text=f"Latest Version: {info['version']}")
                    about_tab.update_button.configure(
                        text=f"Download & Install v{info['version']}",
                        state="normal",
                        command=lambda: about_tab.download_and_install_update(
                            info['url'], info['version']
                        )
                    )
                    if hasattr(about_tab, 'show_new_version_changelog'):
                        about_tab.show_new_version_changelog(info.get('changelog', []))
                except Exception:
                    pass
            elif info and info.get('status') == 'updated':
                try:
                    about_tab.latest_version_label.configure(text="Latest Version: Up to date")
                    about_tab.update_button.configure(text="Check for Updates", state="normal",
                                                       command=about_tab.check_for_updates)
                except Exception:
                    pass

    def _apply_feature_flags(self) -> None:
        """Apply global_disabled_features and trial_restricted_features to nav buttons."""
        if not hasattr(self, 'nav_buttons'):
            return
        for name, btn in self.nav_buttons.items():
            current_text = btn.cget("text")
            clean_text = current_text.replace(" ⚠️", "").replace(" 🔒", "")
            new_state = "normal"
            new_fg = "transparent"
            new_text = clean_text
            is_disabled = False
            if isinstance(self.global_disabled_features, list):
                if name in self.global_disabled_features:
                    is_disabled = True
            elif isinstance(self.global_disabled_features, dict):
                if name in self.global_disabled_features:
                    is_disabled = True
            if is_disabled:
                new_state = "normal"
                new_text = f"{clean_text} ⚠️"
                new_fg = ("#FEF2F2", "#450A0A")
            btn.configure(text=new_text, fg_color=new_fg)

    def open_folder(self, path):
        try:
            if os.path.exists(path):
                if sys.platform == "win32":
                    os.startfile(path)
                else:
                    subprocess.call(["open" if sys.platform == "darwin" else "xdg-open", path])
        except Exception:
            pass

    # ============================================================================
    # APP STATE COMPATIBILITY
    # Tab files access self.app.app_state.field. This property makes those
    # lookups resolve to self.xxx on NregaBotLiteApp.
    # ============================================================================

    @property
    def app_state(self) -> 'NregaBotLiteApp':
        return self

    # Known state fields that may be accessed by tab files but aren't defined
    # on NregaBotLiteApp. If accessed, return None gracefully instead of
    # AttributeError.
    _layout_ready: bool = False
    _history_window: Any = None
    _focus_validation_timer: Any = None
    _cached_style: Any = None
    _gc_timer_id: Any = None
    _tabs_cache: Optional[Dict[str, Any]] = None
    update_info: Dict[str, Any] = None
    current_toast: Any = None
    announcement_label: Any = None
    performance_monitor: Any = None
    sound_switch_var: Any = None
    minimize_var: Any = None

    def _get_machine_id(self) -> str:
        if self.services:
            return self.services.machine_id
        return "unknown"

    def _gc_collection_loop(self) -> None:
        """Periodic GC collection to prevent memory fragmentation
        during long sessions. Runs every 3 minutes.
        """
        try:
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"GC collected {collected} objects")
        except Exception:
            pass
        interval = getattr(config, 'GC_INTERVAL_MS', 180000)
        self._gc_timer_id = self.after(interval, self._gc_collection_loop)

    def on_closing(self, force: bool = False) -> None:
        if force or messagebox.askokcancel("Quit", "Quit application?"):
            # Cancel periodic GC timer
            if self._gc_timer_id:
                try:
                    self.after_cancel(self._gc_timer_id)
                except Exception:
                    pass
            gc.collect()
            try:
                if self.driver:
                    self.driver.quit()
            except Exception:
                pass
            import os
            os._exit(0)


# ============================================================================
# ENTRY POINT
# ============================================================================

def run_lite_application() -> None:
    logging.basicConfig(level=logging.INFO)
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 60124))  # Different port from full app
    except Exception:
        sys.exit(0)
    
    try:
        app = NregaBotLiteApp()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("Fatal Error", str(e))
    finally:
        s.close()


if __name__ == '__main__':
    run_lite_application()
