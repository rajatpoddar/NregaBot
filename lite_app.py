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
import subprocess




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
    resource_path, get_data_path, get_user_downloads_path, get_nregabot_path,
    get_report_path, get_config, save_config, validate_config,
    setup_logging, get_logger, _suppress_overscroll, install_crash_reporter
)

# --- Shared automation display names for the footer's "▶ Running: ..."
# indicator — single source of truth lives in src/app/app_automation.py.
from src.app.app_automation import AUTOMATION_DISPLAY_NAMES, _automation_display_name

# --- Replace AutocompleteEntry with LiteDropdown for the lite app ---
# Every tab that imports AutocompleteEntry from autocomplete_widget will get
# LiteDropdown instead — a read-only dropdown with NO typing/autocomplete.
# This is a clean monkey-patch that requires zero changes to tab files.
from src.tabs import autocomplete_widget as _acw
_acw.AutocompleteEntry = _acw.LiteDropdown

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

# Crash reporter — uncaught exceptions Temp/crashes/ me save hote hain
install_crash_reporter()

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
        
        # Check if launched from lite_loader.py — skip splash + redundant update check
        self._from_loader = os.environ.pop('LITE_LOADER_ACTIVE', None) == '1'

        # macOS Tk bug: withdraw+deiconify on main window breaks mouse event
        # delivery. On macOS we keep the window visible from the start with an
        # in-window splash. On Windows we withdraw during build for smooth launch.
        self._on_windows = config.OS_SYSTEM == "Windows"

        self.title(f"{config.APP_NAME}")
        
        self.initial_width = 920
        self.initial_height = 680
        self.minsize(800, 550)
        
        # Root-window background — drive it through CTk's fg_color as a
        # (light, dark) tuple so it follows the theme (plain `bg=` is ignored
        # by macOS Aqua and a hardcoded colour never changes).
        self.configure(fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))
        
        # --- State ---
        self.http_session = requests.Session()
        self.stop_events: Dict[str, Any] = {}
        self.tab_instances: Dict[str, Any] = {}
        self.content_frames: Dict[str, Any] = {}  # Per-tab wrapper frames (like main app)
        self.active_automations: Set[str] = set()
        self.automation_threads: Dict[str, Any] = {}
        self._automation_progress: Dict[str, float] = {}  # footer '%' display ke liye
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
        self._last_active_nav: Optional[str] = None  # Track for fast highlight update
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

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self._final_w = min(self.initial_width, sw - 40)
        self._final_h = min(self.initial_height, sh - 40)
        self._final_w = max(self._final_w, 850)
        self._final_h = max(self._final_h, 600)
        self._final_x = (sw // 2) - (self._final_w // 2)
        self._final_y = (sh // 2) - (self._final_h // 2)

        if self._from_loader:
            # Launched from lite_loader.py — show a compact splash during UI build.
            # Main window appears only after UI is ready (in _build_ui_on_main_thread).
            # Platform-specific: Windows uses Toplevel + withdraw, macOS uses in-window
            # frame (withdraw+deiconify on macOS permanently breaks mouse events).
            if self._on_windows:
                self.withdraw()
                self._splash_window = self._create_splash_toplevel()
            else:
                self._splash_window = self._create_splash_frame()
                self._splash_window.pack(expand=True, fill="both")
                self.deiconify()
                self.update()
            self._splash_window.update()
        elif self._on_windows:
            # Windows: build UI completely while withdrawn for jank-free reveal
            self.withdraw()
            self._splash_window = self._create_splash_toplevel()
            self._splash_window.update()
        else:
            # macOS: in-window splash to avoid withdraw/deiconify bug
            self._splash_window = self._create_splash_frame()
            self._splash_window.pack(expand=True, fill="both")
            self.geometry(f'{self._final_w}x{self._final_h}+{self._final_x}+{self._final_y}')
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
        
    def _create_splash_toplevel(self) -> ctk.CTkToplevel:
        """Create a Toplevel splash matching the main app's loader design.
        Compact size, same branding — "NREGA Bot" + "VB-G-RAM-G Portal Support".
        """
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)
        w, h = 380, 250
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        x, y = (sw // 2) - (w // 2), (sh // 2) - (h // 2)
        splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        splash.configure(fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))

        # Flag to stop splash animation when window is destroyed
        splash._running = True

        # Outer card (matching main loader: corner_radius=20, border_width=2)
        outer = ctk.CTkFrame(splash,
                             fg_color=("#FFFFFF", "#2B2B2B"),
                             corner_radius=20, border_width=2,
                             border_color=("#E2E8F0", "#404040"))
        outer.pack(fill="both", expand=True, padx=4, pady=4)

        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=24, pady=18)

        # Emoji logo
        ctk.CTkLabel(inner, text="🏛️", font=ctk.CTkFont(size=28)).pack(pady=(4, 2))

        # App title — exactly like main loader: "NREGA Bot"
        ctk.CTkLabel(inner, text="NREGA Bot",
                     font=ctk.CTkFont(family="Helvetica Neue", size=22, weight="bold"),
                     text_color=("#1E293B", "#F1F5F9")
                     ).pack(pady=(2, 1))

        # Tagline — exactly like main loader: "VB-G-RAM-G Portal Support"
        ctk.CTkLabel(inner, text="VB-G-RAM-G Portal Support",
                     font=ctk.CTkFont(family="Helvetica Neue", size=11),
                     text_color=("#3B82F6", "#60A5FA")
                     ).pack(pady=(0, 14))

        # Animated dots
        splash.dots_label = ctk.CTkLabel(
            inner, text="Loading",
            font=ctk.CTkFont(family="Helvetica Neue", size=11),
            text_color=("#64748B", "#94A3B8")
        )
        splash.dots_label.pack()

        def _splash_animate():
            try:
                if not splash._running or not splash.winfo_exists():
                    return
                d = "." * ((getattr(splash, '_dot_count', 0) % 4) + 1)
                splash._dot_count = getattr(splash, '_dot_count', 0) + 1
                try:
                    splash.dots_label.configure(text=f"Loading{d}")
                except Exception:
                    splash._running = False
                    return
                splash.after(120, _splash_animate)
            except Exception:
                splash._running = False
        _splash_animate()

        # Version footer
        ctk.CTkLabel(inner, text=f"v{config.APP_VERSION.replace('-LITE','')} \u00b7 NregaBot.com",
                     font=ctk.CTkFont(family="Helvetica Neue", size=9),
                     text_color=("#CBD5E1", "#475569")
                     ).pack(side="bottom", pady=(0, 2))

        splash.lift()
        splash.attributes("-topmost", True)
        return splash

    def _create_splash_frame(self) -> ctk.CTkFrame:
        """Create a compact in-window splash matching the main app's loader design.
        Uses a centered card — "NREGA Bot" + "VB-G-RAM-G Portal Support".
        """
        splash = ctk.CTkFrame(self, corner_radius=0,
                              fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))

        # Compact centered card (matching main loader style)
        card_w, card_h = 360, 230
        card = ctk.CTkFrame(splash, corner_radius=20,
                            fg_color=("#FFFFFF", "#2B2B2B"),
                            border_width=2,
                            border_color=("#E2E8F0", "#404040"),
                            width=card_w, height=card_h)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=22, pady=16)

        # Emoji logo
        ctk.CTkLabel(inner, text="🏛️", font=ctk.CTkFont(size=26)).pack(pady=(4, 2))

        # App title — "NREGA Bot" (no "Lite" branding on splash)
        ctk.CTkLabel(inner, text="NREGA Bot",
                     font=ctk.CTkFont(family="Helvetica Neue", size=20, weight="bold"),
                     text_color=("#1E293B", "#F1F5F9")
                     ).pack(pady=(2, 1))

        # Tagline — "VB-G-RAM-G Portal Support"
        ctk.CTkLabel(inner, text="VB-G-RAM-G Portal Support",
                     font=ctk.CTkFont(family="Helvetica Neue", size=11),
                     text_color=("#3B82F6", "#60A5FA")
                     ).pack(pady=(0, 12))

        # Animated dots
        self._frame_dots_lbl = ctk.CTkLabel(
            inner, text="Loading",
            font=ctk.CTkFont(family="Helvetica Neue", size=11),
            text_color=("#64748B", "#94A3B8")
        )
        self._frame_dots_lbl.pack()
        self._animate_frame_dots()

        # Version footer
        ctk.CTkLabel(inner, text=f"v{config.APP_VERSION.replace('-LITE','')} \u00b7 NregaBot.com",
                     font=ctk.CTkFont(family="Helvetica Neue", size=9),
                     text_color=("#CBD5E1", "#475569")
                     ).pack(side="bottom", pady=(0, 2))

        return splash

    def _animate_frame_dots(self) -> None:
        """Animate the in-window splash dots."""
        if not self._frame_dots_lbl or not self._frame_dots_lbl.winfo_exists():
            return
        d = "." * ((getattr(self, '_frame_dot_idx', 0) % 4) + 1)
        self._frame_dot_idx = getattr(self, '_frame_dot_idx', 0) + 1
        try:
            self._frame_dots_lbl.configure(text=f"Loading{d}")
            self.after(120, self._animate_frame_dots)
        except Exception:
            pass

    def _build_ui_on_main_thread(self) -> None:
        """Build the UI structure.
        On macOS: destroy in-window splash first, build UI, then show window.
        On Windows: destroy Toplevel splash, build UI, then reveal main window.
        
        When launched from lite_loader.py, splash is already skipped in __init__.
        Preloads the Home tab in-place so the content area is fully populated
        when the window first appears — no flickering.
        """
        # Stop splash animation first (avoids after() timer firing on dead window)
        if self._splash_window:
            try:
                self._splash_window._running = False
            except Exception:
                pass
            try:
                self._splash_window.destroy()
            except Exception:
                pass
            self._splash_window = None
            # Stop in-window splash dots animation (for macOS _create_splash_frame)
            self._frame_dots_lbl = None

        self._build_ui()

        # Preload Home tab directly into _tab_container
        if "Home" not in self.tab_instances:
            tabs = self._get_cached_tabs()
            for cat, tab_items in tabs.items():
                if "Home" in tab_items:
                    try:
                        frame = ctk.CTkFrame(self._tab_container, corner_radius=0)
                        frame.grid(row=0, column=0, sticky="nsew")
                        instance = tab_items["Home"]["creation_func"](frame, self)
                        instance.pack(expand=True, fill="both")
                        self.content_frames["Home"] = frame
                        self.tab_instances["Home"] = instance
                    except Exception as e:
                        logger.debug("Failed to preload Home tab: %s", e)
                    break

        self.app_state._layout_ready = True

        # Show the fully-built main window
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
        footer.grid_columnconfigure(0, weight=0)
        footer.grid_columnconfigure(1, weight=1)
        footer.grid_columnconfigure(2, weight=0)

        # Left: "© 2025 NREGA Bot | ▶ Running: X | Status: ..." (one sequence)
        left_frame = ctk.CTkFrame(footer, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="w", padx=10)

        ctk.CTkLabel(
            left_frame, text="© 2025 NREGA Bot",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray50", "gray50")
        ).pack(side="left", padx=(0, 10))

        # Running Automation Indicator (clickable chips) — naam par click karne
        # se woh automation ka tab khul jata hai.
        self.running_automation_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        self.running_automation_frame.pack(side="left", padx=(0, 5))
        self.running_automation_prefix = ctk.CTkLabel(
            self.running_automation_frame, text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#2563EB", "#60A5FA")
        )
        self.running_automation_prefix.pack(side="left")
        self.running_automation_chips: List[Any] = []

        ctk.CTkFrame(left_frame, width=1, height=14, fg_color=("gray80", "gray40")).pack(side="left", padx=(8, 0))

        self.status_label = ctk.CTkLabel(left_frame, text="Ready", text_color="gray60", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left", padx=(8, 0))

        # Right: right-side widgets container (avoids grid overlap)
        right_frame = ctk.CTkFrame(footer, fg_color="transparent")
        right_frame.grid(row=0, column=2, sticky="e", padx=10)

        # Server status dot
        self.server_status_indicator = ctk.CTkFrame(right_frame, width=8, height=8, corner_radius=4, fg_color="gray")
        self.server_status_indicator.pack(side="left")

        # Separator between status and emergency stop
        ctk.CTkFrame(right_frame, width=1, height=14, fg_color=("gray80", "gray40")).pack(side="left", padx=(8, 6))

        # Emergency Stop — clickable dot + label
        _stop_cmd = lambda e: self._emergency_stop_all()
        self.emergency_stop_frame = ctk.CTkFrame(right_frame, fg_color="transparent", cursor="hand2")
        self.emergency_stop_frame.pack(side="left", padx=(0, 4))
        self.emergency_stop_frame.bind("<Button-1>", _stop_cmd)

        self.emergency_stop_indicator = ctk.CTkFrame(
            self.emergency_stop_frame, width=10, height=10, corner_radius=5,
            fg_color="transparent",
        )
        self.emergency_stop_indicator.pack(side="left", padx=(0, 4))
        self.emergency_stop_indicator.bind("<Button-1>", _stop_cmd)

        self.emergency_stop_label = ctk.CTkLabel(
            self.emergency_stop_frame,
            text="STOP",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=("gray50", "gray50"),
            cursor="hand2",
        )
        self.emergency_stop_label.pack(side="left")
        self.emergency_stop_label.bind("<Button-1>", _stop_cmd)

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
        """Load and show a tab (lazy loading).
        
        Lite version: simplified tab switching without skeleton loaders.
        - Cached tabs: raises the wrapper frame immediately
        - New tabs: creates in-place without intermediate loading frames
        """
        # If already loaded, just raise the existing wrapper frame
        if page_name in self.tab_instances:
            frame = self.content_frames.get(page_name)
            if frame and frame.winfo_exists():
                frame.tkraise()
            self._update_nav_highlight(page_name)
            return

        # Load new tab directly — no skeleton, no deferral, no flicker
        try:
            tabs = self._get_cached_tabs()
            for cat, tab_items in tabs.items():
                if page_name in tab_items:
                    frame = ctk.CTkFrame(self._tab_container, corner_radius=0)
                    frame.grid(row=0, column=0, sticky="nsew")

                    instance = tab_items[page_name]["creation_func"](frame, self)
                    instance.pack(expand=True, fill="both")

                    self.content_frames[page_name] = frame
                    self.tab_instances[page_name] = instance

                    frame.tkraise()
                    self._update_nav_highlight(page_name)

                    if page_name == "About" and self.license_info:
                        self._update_about_tab_info()
                    break
        except Exception as e:
            logger.error("Error loading tab %s: %s", page_name, e)

    def _get_cached_tabs(self) -> Dict[str, Dict[str, Any]]:
        """Return cached tab definitions — built once, reused forever."""
        if self._tabs_cache is None:
            self._tabs_cache = get_tabs_definition_lite(self)
        return self._tabs_cache

    def _update_nav_highlight(self, page_name: str) -> None:
        """Highlight the active nav button.
        Only updates the previously-active and newly-active buttons
        instead of iterating ALL buttons — reduces layout churn on Windows.
        """
        # Reset previous active button (if different)
        if self._last_active_nav and self._last_active_nav != page_name:
            btn = self.nav_buttons.get(self._last_active_nav)
            if btn:
                btn.configure(fg_color="transparent",
                              text_color=("gray30", "gray80"),
                              font=ctk.CTkFont(size=12))

        # Highlight new active button
        btn = self.nav_buttons.get(page_name)
        if btn:
            btn.configure(fg_color=("#E3F2FD", "#374151"),
                          text_color=("#1565C0", "#60A5FA"),
                          font=ctk.CTkFont(size=12, weight="bold"))

        self._last_active_nav = page_name

    def _show_window(self) -> None:
        """Activate the fully-built window.
        On Windows: window was withdrawn, so deiconify reveals it for the
        first time with all widgets already laid out (no flicker).
        On macOS: window was already visible with in-window splash, so
        deiconify is a safe no-op; just ensure focus.
        
        Uses a single update() call for Windows — reduces flicker from
        multiple paint cycles.
        """
        self._initial_geometry_set = True  # Prevent CTk's 20ms timer from overriding

        if self._on_windows:
            self.geometry(f'{self._final_w}x{self._final_h}+{self._final_x}+{self._final_y}')
            self.deiconify()
            self.update()  # Single paint cycle — enough on Windows
        else:
            self.deiconify()  # Safe no-op on macOS

        self.focus_force()
        self.lift()
        self._window_shown = True

    def _on_licensed(self) -> None:
        """Set up UI for licensed user.
        Show Home directly — no About preload that could cause flicker.
        About tab loads lazily when user clicks it.
        
        Starts background services: update check (skipped when launched from
        lite_loader.py since the loader already handled it), GC collection.
        Server status is updated by validate_on_server (started from check_license).
        """
        self.set_status("Ready")
        self.show_frame("Home")
        # Start background services (skip update check if loader already did it)
        if not self._from_loader:
            self.check_for_updates_background()
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
        # Fresh run: purana progress clear karo
        self._automation_progress.pop(key, None)
        self._update_emergency_stop_btn()
        self._update_running_automation_indicator()

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
        self._automation_progress.pop(key, None)
        self._update_running_automation_indicator()
        self.set_status("Ready")
        if not self.active_automations:
            self._update_emergency_stop_btn()

    def _emergency_stop_all(self) -> None:
        """Emergency stop ALL running automations immediately."""
        if not self.active_automations:
            return
        for key in list(self.active_automations):
            if key in self.stop_events:
                self.stop_events[key].set()
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                self.active_browser = None
        except Exception:
            pass
        count = len(self.active_automations)
        self.active_automations.clear()
        # Emergency stop → koi automation active nahi — progress state bhi clean
        self._automation_progress.clear()
        self._update_running_automation_indicator()
        self.set_status(f"Stopped {count} automation(s)")
        self.show_toast(f"🛑 Stopped {count} automation(s)", "warning", duration=5000)
        self._update_emergency_stop_btn()

    def _update_running_automation_indicator(self) -> None:
        """Update the footer's '▶ Running: ...' indicator with the currently
        active automation display names. Har naam ek clickable chip hai jo us
        automation ka tab kholta hai. Safe to call before the footer is built."""
        frame = getattr(self, 'running_automation_frame', None)
        if frame is None:
            return
        try:
            if not frame.winfo_exists():
                return
            active = list(self.active_automations)
            if not active:
                self._clear_running_chips()
                self.running_automation_prefix.configure(text="")
                return
            # Sirf tab set change hone par rebuild karo (avoid churn)
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
                                       font=ctk.CTkFont(size=11, weight="bold"))
                    sep.pack(side="left")
                    self.running_automation_chips.append(sep)
                name = _automation_display_name(k)
                tab_name = tab_map.get(k)
                chip = ctk.CTkLabel(
                    frame, text=name,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=("#2563EB", "#60A5FA"),
                    cursor="hand2" if tab_name else ""
                )
                chip.pack(side="left")
                if tab_name:
                    chip.bind("<Button-1>", lambda e, tn=tab_name: self.show_frame(tn))
                    chip.bind("<Enter>", lambda e, c=chip: c.configure(text_color=("#1E40AF", "#93C5FD")))
                    chip.bind("<Leave>", lambda e, c=chip: c.configure(text_color=("#2563EB", "#60A5FA")))
                self.running_automation_chips.append(chip)
                # Progress % label — sirf agar tab ne progress report kiya ho
                pct = self._automation_progress.get(k)
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
            pass

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

    def _automation_key_to_tab_name(self) -> Dict[str, str]:
        """Map automation_key → tab display name for footer chip clicks.

        Loaded tab instances are authoritative (their automation_key matches
        the active_automations keys). Falls back to the lite tab_config 'key'
        field, then a small override map for known mismatches.
        """
        mapping: Dict[str, str] = {}
        try:
            for name, inst in self.tab_instances.items():
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
            "abps_verify": "Verify ABPS",
            "resend_wg": "Resend Rejected WG",
            "sad_auto": "Sarkar Aapke Dwar",
            "fto_gen_del": "FTO Generation",
            "macro": "Macro Manager",
            "pdf_merger": "PDF Merger",
        }.items():
            mapping.setdefault(k, n)
        return mapping

    def report_automation_progress(self, key: str, fraction: float) -> None:
        """Automation tab apna progress fraction (0.0–1.0) yahan report karta hai.
        Footer me us automation ke naam ke aage '%' dikhata hai (thread-safe)."""
        try:
            frac = max(0.0, min(1.0, float(fraction)))
            if abs(self._automation_progress.get(key, -1.0) - frac) < 0.001:
                return
            self._automation_progress[key] = frac
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
                    frac = self._automation_progress.get(k)
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
        """Toggle emergency stop indicator + label. Red when active, dim when idle."""
        ind = getattr(self, 'emergency_stop_indicator', None)
        lbl = getattr(self, 'emergency_stop_label', None)
        if self.active_automations:
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

    # ============================================================================
    # UTILITY
    # ============================================================================

    def set_status(self, message: str, color=None) -> None:
        if self.status_label:
            self.status_label.configure(text=f"Status: {message}")

    def set_server_status(self, is_connected: bool) -> None:
        if self.server_status_indicator:
            self.server_status_indicator.configure(fg_color="green" if is_connected else "red")
        # Also update About tab's header banner if loaded
        about_tab = self.tab_instances.get("About")
        if about_tab:
            color = "green" if is_connected else "red"
            text = "Connected" if is_connected else "Disconnected"
            try:
                if hasattr(about_tab, 'server_dot') and about_tab.server_dot.winfo_exists():
                    about_tab.server_dot.configure(fg_color=color)
                if hasattr(about_tab, 'server_status_label') and about_tab.server_status_label.winfo_exists():
                    about_tab.server_status_label.configure(text=text)
            except Exception:
                pass

    def show_toast(self, message: str, kind: str = "success", duration: int = 3000) -> None:
        """Simple toast notification."""
        try:
            # Multiple toasts stack gracefully (max 3) — no forced destroy here.
            self.current_toast = ToastNotification(self, message, kind, duration=duration)
        except Exception:
            pass

    def get_data_path(self, filename: str) -> str:
        return get_data_path(filename)

    def get_user_downloads_path(self) -> str:
        return get_user_downloads_path()

    def get_nregabot_path(self, subdir: str = "") -> str:
        return get_nregabot_path(subdir)

    def get_report_path(self, category: str = "", fin_year: str = "") -> str:
        return get_report_path(category, fin_year)

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
    # WORKFLOW DELEGATION METHODS
    # These are called by various tabs (e.g. MrTrackingTab._run_mr_payment)
    # and delegate to WorkflowManager just like the full app's NavMixin.
    # ============================================================================

    def switch_to_if_edit_with_data(self, data):
        self.workflows.switch_to_if_edit_with_data(data)

    def run_work_allocation_from_demand(self, p_name, w_key):
        self.workflows.run_work_allocation_from_demand(p_name, w_key)

    def switch_to_msr_tab_with_data(self, wc, p_name):
        self.workflows.switch_to_msr_tab_with_data(wc, p_name)

    def switch_to_emb_entry_with_data(self, wc, p_name):
        self.workflows.switch_to_emb_entry_with_data(wc, p_name)

    def switch_to_mr_fill_with_data(self, wc, p_name):
        self.workflows.switch_to_mr_fill_with_data(wc, p_name)

    def switch_to_mr_tracking_for_abps(self, location_data=None):
        self.workflows.switch_to_mr_tracking_for_abps(location_data)

    def switch_to_duplicate_mr_with_data(self, wc, p_name):
        self.workflows.switch_to_duplicate_mr_with_data(wc, p_name)

    def switch_to_zero_mr_tab_with_data(self, data_list):
        self.workflows.switch_to_zero_mr_tab_with_data(data_list)

    def send_wagelist_data_and_switch_tab(self, start, end, auto_start=False):
        self.workflows.send_wagelist_data_and_switch_tab(start, end, auto_start=auto_start)

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

    def show_update_prompt(self, version: str, is_hotfix: bool = False) -> None:
        """Auto-download and install update — exactly like the main app's loader.
        Shows a progress dialog, downloads in background, then applies the update
        and restarts. No user interaction required beyond the initial notification.
        """
        info = self.update_info
        if not info or not info.get('url'):
            self.show_toast("Update failed: No download URL", "error")
            return

        url = info['url']
        is_smart = info.get('is_smart_update', False)

        # ── Progress dialog ──
        win = ctk.CTkToplevel(self)
        win.title(f"Updating {config.APP_SHORT_NAME}")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = 360, 140
        x, y = (sw // 2) - (w // 2), (sh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.transient(self)
        win.grab_set()

        outer = ctk.CTkFrame(win, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=18, pady=18)

        status_lbl = ctk.CTkLabel(
            outer, text=f"⬇️  Downloading v{version}...",
            font=ctk.CTkFont(size=13), anchor="w"
        )
        status_lbl.pack(fill="x", pady=(0, 10))

        prog_bar = ctk.CTkProgressBar(outer, height=8, corner_radius=4)
        prog_bar.pack(fill="x")
        prog_bar.set(0)

        pct_lbl = ctk.CTkLabel(
            outer, text="0%",
            font=ctk.CTkFont(size=11), text_color="gray50"
        )
        pct_lbl.pack(pady=(6, 0))

        def _download_thread():
            try:
                filename = url.split('/')[-1]
                dl_path = os.path.join(get_user_downloads_path(), filename)

                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    unknown_size = total == 0
                    if unknown_size:
                        self.after(0, lambda: prog_bar.configure(mode="indeterminate"))
                        self.after(0, lambda: prog_bar.start())
                        self.after(0, lambda: pct_lbl.configure(text="Downloading..."))
                    with open(dl_path, 'wb') as f:
                        for chunk in r.iter_content(8192):
                            if chunk:
                                f.write(chunk)
                                if not unknown_size:
                                    downloaded += len(chunk)
                                    pct = downloaded / total
                                    pct_int = int(pct * 100)
                                    self.after(0, lambda v=pct: prog_bar.set(v))
                                    self.after(0, lambda v=pct_int: pct_lbl.configure(text=f"{v}%"))

                self.after(0, lambda: status_lbl.configure(text="🔧  Installing update..."))

                if is_smart and url.endswith(".zip"):
                    def _do_apply():
                        if win.winfo_exists():
                            win.destroy()
                        self._apply_smart_update(dl_path)
                    self.after(500, _do_apply)
                else:
                    def _do_open():
                        if win.winfo_exists():
                            win.destroy()
                        if sys.platform == "win32":
                            os.startfile(dl_path)
                        else:
                            subprocess.call(["open", dl_path])
                        self.after(1000, os._exit, 0)
                    self.after(500, _do_open)

            except Exception as e:
                def _show_error():
                    if not win.winfo_exists():
                        return
                    status_lbl.configure(text=f"❌  Download failed: {str(e)[:60]}", text_color="red")
                    win.after(3000, lambda: win.destroy() if win.winfo_exists() else None)
                self.after(0, _show_error)

        threading.Thread(target=_download_thread, daemon=True).start()

    def download_and_install_update(self, url: str, version: str) -> None:
        """Download and install an update."""
        self.services.download_and_install_update(url, version)

    def _apply_smart_update(self, zip_path: str) -> None:
        """Apply a smart (in-place) update from a downloaded zip file.
        Extracts the zip over the existing installation, then restarts.
        Called by ServiceManager when is_smart_update is True.
        """
        import zipfile
        import shutil
        import subprocess

        if sys.platform == "darwin":
            try:
                from appdirs import user_data_dir
                local_dir = user_data_dir("NREGABot", "PoddarSolutions")
                core_zip_path = os.path.join(local_dir, "core.zip")
                version_file = os.path.join(local_dir, "core_version.json")

                if os.path.exists(core_zip_path):
                    os.remove(core_zip_path)
                shutil.copy2(zip_path, core_zip_path)

                try:
                    new_ver = self.update_info.get('version', '0.0.0')
                    new_hash = self.update_info.get('hash', '') or ''
                    with open(version_file, 'w') as f:
                        json.dump({"version": new_ver, "hash": new_hash}, f)
                except Exception:
                    pass

                try:
                    os.remove(zip_path)
                except Exception:
                    pass

                messagebox.showinfo("Update Ready",
                                    "Update applied successfully.\nThe application will now restart.")
                self.on_closing(force=True)
                subprocess.Popen([sys.executable])
                sys.exit(0)

            except Exception as e:
                messagebox.showerror("Update Error", f"Failed to apply update:\n{e}")
                return

        # Windows path — extract zip, create updater.bat, restart
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
                messagebox.showinfo("Dev Mode",
                                    "Update extracted to 'update_temp'. Cannot auto-restart in dev mode.")
                return

            messagebox.showinfo("Update Ready", "Application will restart to apply changes.")

            batch_script_path = self.get_data_path("updater.bat")
            script_content = f"""
@echo off
title Updating NREGA Bot Lite...
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
                new_ver = self.update_info.get('version', '0.0.0')
                new_hash = self.update_info.get('hash', '') or ''
                vf = self.get_data_path("core_version.json")
                with open(vf, 'w') as f:
                    json.dump({"version": new_ver, "hash": new_hash}, f)
            except Exception:
                pass

            self.on_closing(force=True)
            sys.exit(0)

        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to apply smart update:\n{e}")

    def _update_about_tab_info(self) -> None:
        """Update About tab's subscription, version info, and header server status."""
        about_tab = self.tab_instances.get("About")
        if about_tab:
            # --- Update subscription details ---
            if hasattr(about_tab, 'update_subscription_details'):
                about_tab.update_subscription_details(self.license_info)

            # --- Update header server status (above Account Management) ---
            # The header initially shows "Checking..." and is ONLY updated by
            # set_server_status() which runs from background validate_on_server.
            # If validate_on_server hasn't completed yet, the label stays stuck.
            # Here we optimistically update it based on cached license data.
            if self.license_info and self.license_info.get('key'):
                try:
                    if (hasattr(about_tab, 'server_status_label') and
                        about_tab.server_status_label.winfo_exists() and
                        about_tab.server_status_label.cget("text") == "Checking..."):
                        about_tab.server_status_label.configure(text="Connected")
                    if (hasattr(about_tab, 'server_dot') and
                        about_tab.server_dot.winfo_exists() and
                        about_tab.server_dot.cget("fg_color") == "gray"):
                        about_tab.server_dot.configure(fg_color="green")
                except Exception:
                    pass

            # --- Update version info ---
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
            else:
                status = info.get('status') if info else ''
                if status == 'error':
                    try:
                        about_tab.latest_version_label.configure(text="Latest Version: Check failed")
                        about_tab.update_button.configure(text="Check for Updates", state="normal",
                                                           command=about_tab.check_for_updates)
                    except Exception:
                        pass
                elif status == 'Checking...':
                    # Still in initial 'Checking...' state — update check wasn't triggered.
                    # Show "Not checked yet" so user knows they can click the button.
                    try:
                        about_tab.latest_version_label.configure(text="Latest Version: Not checked yet")
                        about_tab.update_button.configure(
                            text="Check for Updates", state="normal",
                            command=about_tab.check_for_updates
                        )
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

        # Home page cards ko bhi naye feature flags ke saath sync karo —
        # blocked/premium tabs wahan se bhi access na ho payen.
        try:
            home_tab = self.tab_instances.get("Home")
            if home_tab is not None and hasattr(home_tab, 'refresh_feature_states'):
                home_tab.refresh_feature_states()
        except Exception:
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
