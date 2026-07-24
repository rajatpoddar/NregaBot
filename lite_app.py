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
import time
import os
import webbrowser
import sys
import json
import logging
import socket
import gc
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import tkinter
from tkinter import messagebox, ttk
import customtkinter as ctk
import requests
from PIL import Image

# --- Apply Lite config overrides FIRST ---
from src import config
from src import lite_config
lite_config.apply_overrides()

# --- Lite-specific imports ---
from src.ui_components import ToastNotification, CollapsibleFrame
from src.managers.browser_manager import BrowserManager
from src.managers.services import ServiceManager
from src.managers.workflow_manager import WorkflowManager
from src.lite_tab_config import get_tabs_definition_lite
from src.managers.icon_manager import create_icon_manager
from src.app.app_license import LicenseMixin
from src.tabs.history_manager import HistoryManager
from src.utils import (
    resource_path, get_data_path, get_user_downloads_path,
    get_config, save_config, validate_config,
    setup_logging, get_logger
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
    """

    def __init__(self) -> None:
        super().__init__()

        self.withdraw()
        self.title(f"{config.APP_NAME}")
        
        self.initial_width = 1000
        self.initial_height = 750
        self.minsize(850, 600)
        
        self.configure(bg=config.COLORS["bg_dark"])
        
        # --- State ---
        self.http_session = requests.Session()
        self.stop_events: Dict[str, Any] = {}
        self.tab_instances: Dict[str, Any] = {}
        self.content_frames: Dict[str, Any] = {}
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
        
        # --- Services (must init BEFORE _get_machine_id since it depends on services) ---
        self.services = ServiceManager(self)
        self.machine_id: str = self._get_machine_id()
        self.browser_manager = BrowserManager(self)
        self.history_manager = HistoryManager(self.get_data_path)
        self.workflows = WorkflowManager(self)
        self.sound_manager = None  # No sounds in Lite
        
        # --- Icons (minimal set) ---
        self.icon_images = create_icon_manager()
        self.icon_images.preload_essential()
        
        # --- Splash (minimal, no animation) ---
        self._splash = self._create_splash()
        self._splash.update()
        
        # --- GC ---
        gc.set_threshold(500, 5, 3)
        gc.freeze()
        
        # --- Start background init ---
        threading.Thread(target=self._background_init, daemon=True).start()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def _create_splash(self) -> ctk.CTkToplevel:
        """Minimal splash screen — no animations, just branding."""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)
        w, h = 300, 200
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        x, y = (sw // 2) - (w // 2), (sh // 2) - (h // 2)
        splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        splash.configure(fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))
        
        inner = ctk.CTkFrame(splash, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=20, pady=20)
        
        ctk.CTkLabel(
            inner, text=f"{config.APP_NAME}",
            font=ctk.CTkFont(family="Helvetica Neue", size=20, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"])
        ).pack(pady=(15, 5))
        
        ctk.CTkLabel(
            inner, text="Lightweight Edition",
            font=ctk.CTkFont(size=11),
            text_color=(config.COLORS["blue_hover"], config.COLORS["blue_light"])
        ).pack()
        
        ctk.CTkLabel(
            inner, text=f"v{config.APP_VERSION}",
            font=ctk.CTkFont(size=11),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"])
        ).pack(side="bottom", pady=(0, 5))
        
        return splash

    def _background_init(self) -> None:
        """Simple background init — no animations, just build UI."""
        self.after(10, self._finish_startup)

    def _finish_startup(self) -> None:
        """Build the UI directly — no progressive rendering."""
        self._build_ui()
        
        # Use LicenseMixin's perform_license_check_flow pattern
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
        
        # Fade out splash
        self.after(200, self._hide_splash)

    def _build_ui(self) -> None:
        """Simplified UI — header, sidebar, content area, footer."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # --- Header ---
        header = ctk.CTkFrame(self, corner_radius=0, fg_color=(config.COLORS["bg_light"], config.COLORS["bg_darker"]))
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        header.grid_columnconfigure(1, weight=1)
        
        # Logo + Name
        branding = ctk.CTkFrame(header, fg_color="transparent")
        branding.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(branding, text=config.APP_NAME, font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkLabel(branding, text=f"v{config.APP_VERSION}", font=ctk.CTkFont(size=10), text_color="gray60").pack(side="left", padx=(5, 0))
        
        # Browser buttons
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=2, sticky="e", padx=10)
        
        for browser_name, cmd in [("chrome", self.launch_chrome_detached), 
                                   ("firefox", self.launch_firefox_managed)]:
            btn = ctk.CTkButton(
                controls, text="", image=self.icon_images.get(browser_name),
                width=32, height=32, corner_radius=8,
                fg_color="transparent", hover_color=("gray90", "gray30"),
                command=cmd
            )
            btn.pack(side="left", padx=2)
        
        # --- Main Layout ---
        main = ctk.CTkFrame(self, corner_radius=0)
        main.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 5))
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        
        # Sidebar
        sidebar = ctk.CTkFrame(main, width=200, corner_radius=0, fg_color="transparent")
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        sidebar.grid_rowconfigure(1, weight=1)
        
        self.nav_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent", corner_radius=0)
        self.nav_scroll.grid(row=1, column=0, sticky="nsew")
        
        # Content area
        self.content_area = ctk.CTkFrame(main, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)
        
        # Navigation buttons
        self._create_nav_buttons()
        
        # --- Footer ---
        footer = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))
        footer.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))
        footer.grid_propagate(False)
        
        self.status_label = ctk.CTkLabel(footer, text="Ready", text_color="gray60", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left", padx=10)
        
        self.server_status_indicator = ctk.CTkFrame(footer, width=8, height=8, corner_radius=4, fg_color="gray")
        self.server_status_indicator.pack(side="right", padx=10)

    def _create_nav_buttons(self) -> None:
        """Create sidebar navigation from lite_tab_config."""
        self.nav_buttons.clear()
        tabs = get_tabs_definition_lite(self)
        
        for cat_name, cat_tabs in tabs.items():
            if cat_name == "Dashboard":
                # Pin Home button at top
                for name, data in cat_tabs.items():
                    btn = ctk.CTkButton(
                        self.nav_scroll, text=name,
                        image=data.get("icon"),
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
                ctk.CTkFrame(self.nav_scroll, height=1, fg_color=("gray85", "gray35")).pack(fill="x", padx=15, pady=5)
            else:
                # Category label
                ctk.CTkLabel(
                    self.nav_scroll, text=cat_name,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=("gray50", "gray60")
                ).pack(fill="x", padx=10, pady=(5, 2))
                
                for name, data in cat_tabs.items():
                    btn = ctk.CTkButton(
                        self.nav_scroll, text=name,
                        image=data.get("icon"),
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
        """Load and show a tab (lazy loading)."""
        # Check if already loaded
        if page_name in self.tab_instances and page_name in self.content_frames:
            self.content_frames[page_name].tkraise()
            self._update_nav_highlight(page_name)
            return
        
        tabs = get_tabs_definition_lite(self)
        for cat, tab_items in tabs.items():
            if page_name in tab_items:
                frame = ctk.CTkFrame(self.content_area, corner_radius=0)
                frame.grid(row=0, column=0, sticky="nsew")
                
                instance = tab_items[page_name]["creation_func"](frame, self)
                instance.pack(expand=True, fill="both")
                
                self.content_frames[page_name] = frame
                self.tab_instances[page_name] = instance
                frame.tkraise()
                self._update_nav_highlight(page_name)
                return

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

    def _hide_splash(self) -> None:
        """Destroy splash and show main window."""
        if self._splash:
            try:
                self._splash.destroy()
            except Exception:
                pass
            self._splash = None
        
        work_x, work_y, work_w, work_h = 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
        app_w = min(self.initial_width, work_w - 40)
        app_h = min(self.initial_height, work_h - 40)
        app_w = max(app_w, 850)
        app_h = max(app_h, 600)
        
        x = (work_w // 2) - (app_w // 2)
        y = (work_h // 2) - (app_h // 2)
        
        self.geometry(f'{app_w}x{app_h}+{x}+{y}')
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_licensed(self) -> None:
        """Set up UI for licensed user."""
        self.set_status("Ready")
        self._show_frame_about()
        self.show_frame("Home")

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

    def play_sound(self, sound_name: str) -> None:
        """Silent in Lite version — no sound playback."""
        pass

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
    _layout_ready: bool = True
    _history_window: Any = None
    _focus_validation_timer: Any = None
    _cached_style: Any = None
    _gc_timer_id: Any = None
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

    def on_closing(self, force: bool = False) -> None:
        if force or messagebox.askokcancel("Quit", "Quit application?"):
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
