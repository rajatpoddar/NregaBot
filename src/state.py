# state.py
# A4: Centralized application state management for NREGA Bot.
# All application state is defined in a single AppState dataclass
# for consistency, type safety, and self-documentation.
#
# Accessed via ``self.state`` on the NregaBotApp instance.
# See also: backward-compatible properties on NregaBotApp that
# delegate to self.state for tab files accessing self.app.<attr>.

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union


@dataclass
class AppState:
    """
    Centralized application state for NREGA Bot.

    All state is grouped into logical categories with typed fields
    and docstrings.  Accessed via ``self.state`` on NregaBotApp.

    **NOTE:** UI widget references (labels, buttons, frames) are NOT stored
    here — they remain as direct attributes on NregaBotApp because they are
    created during UI construction and are tightly coupled to the GUI lifecycle.
    """

    # ═══════════════════════════════════════════════════════════════════
    # LICENSE & AUTH  (owned by LicenseMixin)
    # ═══════════════════════════════════════════════════════════════════

    is_licensed: bool = False
    """Whether the current session has a valid license (full or trial)."""

    license_info: Dict[str, Any] = field(default_factory=dict)
    """License metadata: key, expires_at, user_name, key_type, total_usage, …"""

    is_validating_license: bool = False
    """True while a background license validation is in progress."""

    global_disabled_features: Union[List[str], Dict[str, Any]] = field(
        default_factory=list
    )
    """Features disabled server-wide (list of tab names or dict of tab → metadata)."""

    trial_restricted_features: List[str] = field(default_factory=list)
    """Features locked for trial users (list of tab names)."""

    expiry_alert_message: Optional[str] = None
    """Message shown when the license is expiring within 7 days."""

    open_on_about_tab: bool = False
    """If True, navigate to About tab on startup (used for expiry alert)."""

    machine_id: str = ""
    """Unique machine identifier for license binding."""

    # ═══════════════════════════════════════════════════════════════════
    # AUTOMATION & BROWSER  (owned by AutomationMixin)
    # ═══════════════════════════════════════════════════════════════════

    driver: Any = None
    """Active Selenium WebDriver instance (Firefox managed) or None."""

    active_browser: Optional[str] = None
    """Which browser is active: 'chrome', 'edge', 'firefox', or None."""

    active_automations: Set[str] = field(default_factory=set)
    """Set of tab keys currently running automations."""

    automation_threads: Dict[str, Any] = field(default_factory=dict)
    """Mapping of tab key → threading.Thread for running automations."""

    stop_events: Dict[str, Any] = field(default_factory=dict)
    """Mapping of tab key → threading.Event for signalling stop to running tasks."""

    sleep_prevention_process: Any = None
    """Subprocess reference for sleep prevention (Windows-only)."""

    # ═══════════════════════════════════════════════════════════════════
    # UI STATE  (owned by UIMixin)
    # ═══════════════════════════════════════════════════════════════════

    sound_switch_var: Any = None
    """tkinter.BooleanVar for sound on/off.  Set during __init__ (needs Tk root)."""

    minimize_var: Any = None
    """tkinter.BooleanVar for auto-minimize on start.  Set during __init__."""

    current_theme_mode: str = "System"
    """Current theme: 'System', 'Light', or 'Dark'."""

    is_animating: bool = False
    """True while the loading-spinner animation is active."""

    # ═══════════════════════════════════════════════════════════════════
    # NAVIGATION  (owned by NavMixin)
    # ═══════════════════════════════════════════════════════════════════

    nav_buttons: Dict[str, Any] = field(default_factory=dict)
    """Mapping of tab name → CTkButton widget for sidebar navigation."""

    content_frames: Dict[str, Any] = field(default_factory=dict)
    """Mapping of tab name → CTkFrame widget for the content area."""

    tab_instances: Dict[str, Any] = field(default_factory=dict)
    """Cached instances of loaded tabs, keyed by tab name."""

    button_to_category_frame: Dict[str, Any] = field(default_factory=dict)
    """Mapping of tab name → CollapsibleFrame for category grouping."""

    category_frames: Dict[str, Any] = field(default_factory=dict)
    """Mapping of category name → CollapsibleFrame widget."""

    last_selected_category: str = "All Automations"
    """The currently-selected category filter in the sidebar."""

    _category_icons_loaded: Set[str] = field(default_factory=set)
    """Track which categories have had their nav icons loaded (P5 lazy loading)."""

    _tab_icon_keys: Dict[str, Optional[str]] = field(default_factory=dict)
    """Mapping of tab name → icon key string for lazy icon loading."""

    tab_icon_map: Dict[str, Any] = field(default_factory=dict)
    """Mapping of tab name → CTkImage for nav-button icons."""

    _last_active_nav: Optional[str] = None
    """Name of the last active navigation button (highlight tracking)."""

    current_active_tab: Optional[str] = None
    """Name of the currently active / displayed tab."""

    _history_window: Any = None
    """Reference to the current history-window instance (single-instance guard)."""

    # ═══════════════════════════════════════════════════════════════════
    # NETWORK / SESSION  (owned by NregaBotApp)
    # ═══════════════════════════════════════════════════════════════════

    http_session: Any = None
    """Reusable requests.Session for all HTTP calls.  Set during __init__."""

    update_info: Dict[str, Any] = field(
        default_factory=lambda: {
            "status": "Checking...",
            "version": None,
            "url": None,
        }
    )
    """Latest update-check result: status, version, download URL."""

    current_toast: Any = None
    """Reference to the currently-visible ToastNotification instance."""

    # ═══════════════════════════════════════════════════════════════════
    # INTERNAL / LIFECYCLE  (owned by NregaBotApp / UIMixin)
    # ═══════════════════════════════════════════════════════════════════

    _layout_ready: bool = False
    """True once the main UI layout is fully constructed."""

    _is_resizing: bool = False
    """True while a window resize is in progress (debounce tracking)."""

    _is_theme_transitioning: bool = False
    """Prevents rapid re-triggering of theme cycling."""

    _resize_timer: Any = None
    """after() timer ID for resize debounce."""

    _resize_overlay: Any = None
    """tk.Frame overlay shown during resize to hide flickering."""

    _last_resize_w: Optional[int] = None
    """Last recorded window width for resize delta detection."""

    _last_resize_h: Optional[int] = None
    """Last recorded window height for resize delta detection."""

    _cached_style: Any = None
    """ttk.Style singleton — created once, reused (P7 optimization)."""

    _gc_timer_id: Any = None
    """after() timer ID for periodic garbage collection (P6)."""

    _focus_validation_timer: Any = None
    """after() timer ID for delayed license validation on window focus."""

    _original_showinfo: Any = None
    """Stored original messagebox.showinfo for override / reset."""

    _original_showwarning: Any = None
    """Stored original messagebox.showwarning for override / reset."""

    _original_showerror: Any = None
    """Stored original messagebox.showerror for override / reset."""
