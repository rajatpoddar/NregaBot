# app_ui.py — UI Construction & Theme Mixin
#
# A1: Extracted from main_app.py to reduce file size.
# Contains methods for building the app layout (header, footer, sidebar),
# resize smoothing, theme switching, and UI event handlers.
#
# Uses mixin pattern: inheriting class (NregaBotApp) provides
# all instance variables via self.

import customtkinter as ctk
import tkinter
from tkinter import messagebox
import os
import webbrowser
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw

from src import config
from src.utils import resource_path, get_logger, get_config, save_config
from src.ui_components import MarqueeLabel, PerformanceMonitor

logger = get_logger()


class UIMixin:
    """Mixin: UI construction, resize smoothing, theme cycling, UI events."""

    # ============================================================================
    # UI CONSTRUCTION
    # ============================================================================

    def _create_header(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0,
                                 fg_color=(config.COLORS["bg_light"], config.COLORS["bg_darker"]))
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        header.grid_columnconfigure(1, weight=1)

        def add_status_hover(btn, message):
            def on_enter(e):
                if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                    self.status_label.configure(text=message, text_color=(config.COLORS["blue"], config.COLORS["blue_light"]))
            def on_leave(e):
                if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                    self.status_label.configure(text="Ready", text_color="gray60")
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

        branding_frame = ctk.CTkFrame(header, fg_color="transparent")
        branding_frame.grid(row=0, column=0, sticky="w", padx=15, pady=8)

        try:
            logo = ctk.CTkImage(Image.open(resource_path("assets/logo.png")), size=(38, 38))
            ctk.CTkLabel(branding_frame, image=logo, text="").pack(side="left", padx=(0, 12))
        except Exception:
            logger.debug("Failed to load header logo", exc_info=True)

        text_box = ctk.CTkFrame(branding_frame, fg_color="transparent")
        text_box.pack(side="left")

        ctk.CTkLabel(text_box, text=config.APP_NAME, font=ctk.CTkFont(size=18, weight="bold"), anchor="w", height=20).pack(anchor="w")

        welcome_sub_frame = ctk.CTkFrame(text_box, fg_color="transparent", height=15)
        welcome_sub_frame.pack(anchor="w")
        self.header_welcome_prefix_label = ctk.CTkLabel(welcome_sub_frame, text=f"v{config.APP_VERSION}", font=ctk.CTkFont(size=11), text_color="gray60")
        self.header_welcome_prefix_label.pack(side="left")
        self.header_welcome_name_label = ctk.CTkLabel(welcome_sub_frame, text="", font=ctk.CTkFont(size=11, weight="bold"))
        self.header_welcome_name_label.pack(side="left")
        self.header_welcome_suffix_label = ctk.CTkLabel(welcome_sub_frame, text="", font=ctk.CTkFont(size=11))
        self.header_welcome_suffix_label.pack(side="left")

        announcement_frame = ctk.CTkFrame(header, fg_color="transparent", height=30)
        announcement_frame.grid(row=0, column=1, sticky="ew", padx=20)
        announcement_frame.grid_propagate(False)

        self.announcement_label = MarqueeLabel(announcement_frame, text="Welcome to NREGA Bot! Loading...", width=300)
        self.announcement_label.pack(fill="both", expand=True, pady=5)

        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.grid(row=0, column=2, sticky="e", padx=15, pady=8)

        self.extractor_btn = ctk.CTkButton(
            controls_frame, text="", image=self.icon_images.get("extractor_icon"),
            width=35, height=35, corner_radius=8,
            fg_color=(config.COLORS["gray95"], config.COLORS["gray25"]), hover_color=(config.COLORS["gray85"], config.COLORS["gray35"]),
            command=lambda: self.show_frame("Workcode Extractor")
        )
        self.extractor_btn.pack(side="left", padx=(0, 10))
        add_status_hover(self.extractor_btn, "Open Workcode Extractor")

        self.quick_login_btn = ctk.CTkButton(
            controls_frame, text="", image=self.icon_images.get("emoji_login_automation"),
            width=35, height=35, corner_radius=8,
            fg_color=(config.COLORS["gray95"], config.COLORS["gray25"]), hover_color=(config.COLORS["gray85"], config.COLORS["gray35"]),
            command=self._quick_login_automation
        )
        self.quick_login_btn.pack(side="left", padx=(0, 10))
        add_status_hover(self.quick_login_btn, "Auto Login to NREGA")

        ctk.CTkFrame(controls_frame, width=2, height=20, corner_radius=0, fg_color=(config.COLORS["gray90"], config.COLORS["gray30"])).pack(side="left", padx=(0, 10))

        browser_group = ctk.CTkFrame(controls_frame, fg_color="transparent", corner_radius=0)
        browser_group.pack(side="left", padx=(0, 10))

        self.launch_chrome_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("chrome"),
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_chrome_detached
        )
        self.launch_chrome_btn.pack(side="left", padx=2)
        add_status_hover(self.launch_chrome_btn, "Launch Google Chrome")

        self.launch_edge_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("edge"),
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_edge_detached
        )
        self.launch_edge_btn.pack(side="left", padx=2)
        add_status_hover(self.launch_edge_btn, "Launch Microsoft Edge")

        self.launch_firefox_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("firefox"),
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_firefox_managed
        )
        self.launch_firefox_btn.pack(side="left", padx=2)
        add_status_hover(self.launch_firefox_btn, "Launch Mozilla Firefox")

        ctk.CTkFrame(controls_frame, width=2, height=20, corner_radius=0, fg_color=(config.COLORS["gray90"], config.COLORS["gray30"])).pack(side="left", padx=(0, 10))

        settings_group = ctk.CTkFrame(controls_frame, fg_color=(config.COLORS["gray95"], config.COLORS["gray25"]), corner_radius=20)
        settings_group.pack(side="left")

        self.app_state.current_theme_mode = get_config("theme_mode", "System")
        # Apply the saved theme at startup (module-level default is "System",
        # so without this the app would always launch in System mode even if
        # the user explicitly picked Light/Dark last time).
        ctk.set_appearance_mode(self.app_state.current_theme_mode)
        self._sync_root_background()
        self._sync_macos_titlebar()
        self.theme_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("theme_system"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._cycle_theme
        )
        self.theme_btn.pack(side="left", padx=(5, 2), pady=4)
        add_status_hover(self.theme_btn, "Switch Theme (Light/Dark)")
        self._update_theme_icon()

        self.sound_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("sound_on"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_sound_toggle_click
        )
        self.sound_btn.pack(side="left", padx=2, pady=4)
        add_status_hover(self.sound_btn, "Toggle Sound Effects")
        # Improved ON/OFF visual (green pill = on, red + muted icon = off)
        self._update_sound_btn_visual()

        self.minimize_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("minimize"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_minimize_toggle_click
        )
        self.minimize_btn.pack(side="left", padx=(2, 5), pady=4)
        add_status_hover(self.minimize_btn, "Auto-Minimize on Start")
        self._update_settings_btn_visuals(self.minimize_btn, self.app_state.minimize_var.get())

        self.theme_combo = ctk.CTkOptionMenu(self, width=0, height=0)

    def _create_main_layout(self, for_activation: bool = False) -> None:
        if hasattr(self, 'main_layout_frame') and self.main_layout_frame.winfo_exists():
            self.main_layout_frame.destroy()
            self.update_idletasks()

        # R1: Clean up previous persistent overlay if re-creating layout
        old_overlay = getattr(self.app_state, '_resize_overlay', None)
        if old_overlay:
            try:
                old_overlay.destroy()
            except Exception:
                pass
            self.app_state._resize_overlay = None

        self.main_layout_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_layout_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 10))
        self.main_layout_frame.grid_propagate(False)
        self.main_layout_frame.grid_rowconfigure(0, weight=1)
        self.main_layout_frame.grid_columnconfigure(1, weight=1)

        self.sidebar_container = ctk.CTkFrame(self.main_layout_frame, width=220, corner_radius=0, fg_color="transparent")
        self.sidebar_container.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.sidebar_container.grid_rowconfigure(1, weight=1)
        self.sidebar_container.grid_columnconfigure(0, weight=1)

        self.sidebar_header = ctk.CTkFrame(self.sidebar_container, fg_color="transparent")
        self.sidebar_header.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))

        self.nav_scroll_frame = ctk.CTkScrollableFrame(
            self.sidebar_container,
            label_text="",
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=("gray80", "gray30"),
            scrollbar_button_hover_color=("gray70", "gray20")
        )
        self.nav_scroll_frame.grid(row=1, column=0, sticky="nsew")

        # Performance Monitor at bottom of sidebar
        self.performance_monitor = PerformanceMonitor(self.sidebar_container, self)
        self.performance_monitor.grid(row=2, column=0, sticky="ew", padx=2, pady=(4, 2))

        self._create_nav_buttons(self.sidebar_header, self.nav_scroll_frame)

        self.content_area = ctk.CTkFrame(self.main_layout_frame, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self._create_content_frames()

        # R1: Pre-create a persistent resize overlay (CTkFrame with corner_radius=0).
        # Hidden by default; raised during resize to mask canvas redraw flicker.
        # Using CTkFrame ensures theme-consistent colors and proper coverage.
        # Plain tk.Frame had issues with color mismatch (solid vs themed gradients).
        self.app_state._resize_overlay = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"])
        )
        # place() covers the entire window; then lower() keeps it invisible
        self.app_state._resize_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.app_state._resize_overlay.lower()

        if for_activation:
            self._lock_app_to_about_tab()

    def _create_footer(self) -> None:
        footer = ctk.CTkFrame(self, height=50, corner_radius=0,
                                 fg_color=(config.COLORS["bg_light"], config.COLORS["bg_darker"]))
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        footer.grid_propagate(False)

        status_frame = ctk.CTkFrame(footer, fg_color="transparent")
        status_frame.pack(side="left", padx=20, fill="y")

        ctk.CTkLabel(
            status_frame,
            text="© 2025 NREGA Bot",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray50", "gray60")
        ).pack(side="left", padx=(0, 15))

        ctk.CTkFrame(status_frame, width=2, height=14, corner_radius=0, fg_color=("gray80", "gray40")).pack(side="left", padx=(0, 10))

        self.loading_animation_label = ctk.CTkLabel(status_frame, text="", width=20, font=ctk.CTkFont(size=14))
        self.loading_animation_label.pack(side="left")

        # ── Running Automation Indicator (clickable chips) ──
        # Shows WHICH automation(s) are currently running (e.g. "▶ Running: MR Tracking").
        # Har naam ek clickable chip hai — click karne par woh tab khul jata hai.
        # Updated by AutomationMixin._update_running_automation_indicator().
        self.running_automation_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        self.running_automation_frame.pack(side="left", padx=(0, 5))
        self.running_automation_prefix = ctk.CTkLabel(
            self.running_automation_frame, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#2563EB", "#60A5FA")
        )
        self.running_automation_prefix.pack(side="left")
        self.running_automation_chips: List[Any] = []

        # Separator between running automation name and status
        ctk.CTkFrame(status_frame, width=2, height=14, corner_radius=0,
                     fg_color=("gray80", "gray40")).pack(side="left", padx=(10, 0))

        # ── Status Label ──
        # Footer reads: "© 2025 NREGA Bot | ▶ Running: X | Status: ..."
        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color="gray60", font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=(8, 0))

        dock_frame = ctk.CTkFrame(footer, fg_color="transparent")
        dock_frame.pack(side="right", padx=15, pady=5)

        # Separator before the emergency-stop group
        ctk.CTkFrame(dock_frame, width=2, height=14, corner_radius=0, fg_color=("gray80", "gray40")).pack(side="left", padx=(0, 10))

        # ── Emergency Stop — clickable dot + label ──
        _stop_cmd = lambda e: self._emergency_stop_all()
        self.emergency_stop_frame = ctk.CTkFrame(dock_frame, fg_color="transparent", cursor="hand2")
        self.emergency_stop_frame.pack(side="left", padx=(4, 4))
        self.emergency_stop_frame.bind("<Button-1>", _stop_cmd)

        # Bigger red dot indicator
        self.emergency_stop_indicator = ctk.CTkFrame(
            self.emergency_stop_frame, width=16, height=16, corner_radius=8,
            fg_color="transparent",
        )
        self.emergency_stop_indicator.pack(side="left", padx=(0, 5))
        self.emergency_stop_indicator.bind("<Button-1>", _stop_cmd)

        # "STOP ALL" label
        self.emergency_stop_label = ctk.CTkLabel(
            self.emergency_stop_frame,
            text="STOP ALL",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray50", "gray50"),
            cursor="hand2",
        )
        self.emergency_stop_label.pack(side="left")
        self.emergency_stop_label.bind("<Button-1>", _stop_cmd)

        # Hover tooltip for the whole group
        def _stop_enter(e):
            if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                self.status_label.configure(text="Emergency Stop — Click to halt all automations", text_color=("#DC2626", "#EF4444"))
        def _stop_leave(e):
            if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                self.status_label.configure(text="Ready", text_color="gray60")
        self.emergency_stop_frame.bind("<Enter>", _stop_enter)
        self.emergency_stop_frame.bind("<Leave>", _stop_leave)
        self.emergency_stop_indicator.bind("<Enter>", _stop_enter)
        self.emergency_stop_indicator.bind("<Leave>", _stop_leave)
        self.emergency_stop_label.bind("<Enter>", _stop_enter)
        self.emergency_stop_label.bind("<Leave>", _stop_leave)

        def create_icon_btn(parent, icon_name, command, tooltip_text):
            icon = self.icon_images.get(icon_name)
            btn = ctk.CTkButton(
                parent, text="", image=icon, width=40, height=40, corner_radius=20,
                fg_color="transparent", hover_color=("gray90", "gray35"),
                command=command
            )
            btn.pack(side="left", padx=4)

            def on_enter(e):
                self.status_label.configure(text=tooltip_text, text_color=("#3B82F6", "#60A5FA"))
            def on_leave(e):
                self.status_label.configure(text="Ready", text_color="gray60")

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            return btn

        create_icon_btn(dock_frame, "history", lambda: self.show_activity_log_tab(), "View Activity Log (Settings → Activity Log)")
        create_icon_btn(dock_frame, "emoji_file_manager", self.open_web_file_manager, "Open Cloud Files")
        create_icon_btn(dock_frame, "whatsapp", lambda: webbrowser.open("https://chat.whatsapp.com/Bup3hDCH3wn2shbUryv8wn"), "Join Community")
        create_icon_btn(dock_frame, "settings", lambda: self.show_frame("Settings"), "Open Settings")

        ctk.CTkFrame(dock_frame, width=2, height=20, corner_radius=0, fg_color=("gray80", "gray40")).pack(side="left", padx=10)

        self.server_status_indicator = ctk.CTkFrame(dock_frame, width=12, height=12, corner_radius=6, fg_color="gray")
        self.server_status_indicator.pack(side="left", padx=(0, 5))

        def on_server_hover(e): self.status_label.configure(text="Server Connection Status")
        def on_server_leave(e): self.status_label.configure(text="Ready")
        self.server_status_indicator.bind("<Enter>", on_server_hover)
        self.server_status_indicator.bind("<Leave>", on_server_leave)

        self.set_status("Ready")

    # ============================================================================
    # RESIZE SMOOTHING
    # ============================================================================

    def _on_window_resize_detect(self, event: Any) -> None:
        """
        Detects window resize and shows a flat overlay to hide flickering
        from expensive canvas redraws (corner_radius, CTkScrollableFrame, etc.).
        """
        if event.widget is not self:
            return

        # Only act when size meaningfully changes
        old_w = getattr(self.app_state, '_last_resize_w', None)
        old_h = getattr(self.app_state, '_last_resize_h', None)
        cur_w, cur_h = event.width, event.height

        if old_w is not None and old_h is not None:
            dw, dh = abs(cur_w - old_w), abs(cur_h - old_h)
            if dw < 10 and dh < 10:
                return

        self.app_state._last_resize_w, self.app_state._last_resize_h = cur_w, cur_h

        if not self.app_state._is_resizing:
            self.app_state._is_resizing = True
            # Pause animations
            if hasattr(self, 'performance_monitor'):
                try: self.performance_monitor.pause()
                except Exception as e: logger.warning("Failed to pause performance monitor during resize: %s", e)
            if hasattr(self, 'announcement_label'):
                try: self.announcement_label.pause()
                except Exception as e: logger.warning("Failed to pause announcement label during resize: %s", e)
            # Show flat overlay to mask flickering canvas redraws
            self._show_resize_overlay()

        if self.app_state._resize_timer:
            try: self.after_cancel(self.app_state._resize_timer)
            except Exception as e: logger.warning("Failed to cancel resize timer: %s", e)
        self.app_state._resize_timer = self.after(150, self._on_window_resize_end)

    def _show_resize_overlay(self) -> None:
        """R1: Raise the persistent CTkFrame overlay to mask canvas redraw flicker
        during window resize/maximize/restore. The overlay is a CTkFrame with
        corner_radius=0 (no canvas overhead) and theme-matching background color.
        Pre-created in _create_main_layout() — no create/destroy overhead."""
        try:
            if not self.winfo_exists():
                return
            overlay = self.app_state._resize_overlay
            if overlay and overlay.winfo_exists():
                # Update fg_color to match current theme mode (ensures correct color
                # if the user switched themes since the overlay was created)
                mode = ctk.get_appearance_mode()
                bg = config.COLORS["bg_light"] if mode == "Light" else config.COLORS["bg_dark"]
                overlay.configure(fg_color=bg)
                overlay.tkraise()
        except Exception as e:
            logger.warning("Failed to show resize overlay: %s", e)

    def _hide_resize_overlay(self) -> None:
        """R1: Lower the persistent overlay after resize completes.
        The overlay remains alive (not destroyed) — just pushed behind
        all other widgets so the normal UI is visible."""
        overlay = self.app_state._resize_overlay
        if overlay:
            try:
                if overlay.winfo_exists():
                    overlay.lower()
            except Exception as e:
                logger.warning("Failed to hide resize overlay: %s", e)

    def _on_window_resize_end(self) -> None:
        """Called ~150ms after resize stops. Removes overlay and resumes animations."""
        self.app_state._is_resizing = False
        self.app_state._resize_timer = None
        self._hide_resize_overlay()
        if hasattr(self, 'performance_monitor'):
            try: self.performance_monitor.resume()
            except Exception as e: logger.warning("Failed to resume performance monitor after resize: %s", e)
        if hasattr(self, 'announcement_label'):
            try: self.announcement_label.resume()
            except Exception as e: logger.warning("Failed to resume announcement label after resize: %s", e)

    # ============================================================================
    # UI EVENTS
    # ============================================================================

    def _on_sound_toggle_click(self) -> None:
        new_val = not self.app_state.sound_switch_var.get()
        self.app_state.sound_switch_var.set(new_val)
        save_config('sound_enabled', new_val)

        # Improved ON/OFF visual feedback
        self._update_sound_btn_visual()
        if new_val:
            self.play_sound("success")

    def _on_minimize_toggle_click(self) -> None:
        new_val = not self.app_state.minimize_var.get()
        self.app_state.minimize_var.set(new_val)

        self._update_settings_btn_visuals(self.minimize_btn, new_val)

        state = "Enabled" if new_val else "Disabled"
        self.show_toast(f"Auto-Minimize {state}", "info")

    def _sync_root_background(self) -> None:
        """
        Keep the root-window background in sync with the active theme.

        CTk widgets use (light, dark) color tuples and repaint automatically on
        theme change — but the root window is a plain Tk window whose background
        must be driven through CTk's fg_color (a single `bg=` is ignored by the
        macOS Aqua theme, and a hardcoded single color never changes). Setting
        fg_color as a (light, dark) tuple makes CTk re-apply the right colour on
        every appearance-mode change automatically.
        """
        try:
            self.configure(fg_color=(config.COLORS["bg_light"], config.COLORS["bg_dark"]))
        except Exception:
            logger.debug("Failed to sync root background", exc_info=True)

    def _sync_macos_titlebar(self) -> None:
        """
        Sync the macOS window titlebar appearance with the current theme.

        On macOS with Python 3.10+, CTk's built-in dark titlebar method is a
        no-op (it only runs on Python < 3.10). We use the Tk unsupported
        MacWindowStyle API directly to force the titlebar to match the app theme.
        Options: 'aqua' (light), 'darkaqua' (dark), 'auto' (follows OS).
        """
        if config.OS_SYSTEM != "Darwin":
            return
        try:
            mode = ctk.get_appearance_mode()  # "Light" or "Dark"
            appearance = "darkaqua" if mode == "Dark" else "aqua"
            self.tk.call("tk::unsupported::MacWindowStyle", "appearance", self._w, appearance)
        except Exception:
            logger.debug("Failed to sync macOS titlebar appearance", exc_info=True)

    def _cycle_theme(self) -> None:
        """Cycle System → Light → Dark, skipping any mode that would be a no-op.

        'System' follows the OS, so when it already matches the current Light
        or Dark appearance, clicking past it would be a 'dead' click (this is
        why the old cycle needed 3-4 clicks for day↔night). Here we always jump
        to the NEXT mode whose effective appearance actually differs — so one
        click always flips day↔night, and System (auto) mode stays reachable.
        """
        if self.app_state._is_theme_transitioning:
            return
        self.app_state._is_theme_transitioning = True

        try:
            modes = ["System", "Light", "Dark"]
            current = self.app_state.current_theme_mode
            if current not in modes:
                current = "System"

            def _effective(mode: str) -> str:
                """Resolve a mode to its actual appearance (Light/Dark)."""
                if mode == "System":
                    return ctk.get_appearance_mode()  # always 'Light' or 'Dark'
                return mode

            current_effective = _effective(current)
            start_idx = modes.index(current)

            # Walk the cycle until we find a mode whose appearance DIFFERS —
            # this guarantees a single click always produces a visible change.
            next_mode = current
            for offset in range(1, len(modes) + 1):
                candidate = modes[(start_idx + offset) % len(modes)]
                if _effective(candidate) != current_effective:
                    next_mode = candidate
                    break

            self.app_state.current_theme_mode = next_mode

            # Step 1: Make window invisible (instant — no flicker possible)
            self.attributes("-alpha", 0.0)
            self.update_idletasks()

            # Step 2: Change theme (all CTk canvas redraws happen invisibly)
            ctk.set_appearance_mode(self.app_state.current_theme_mode)
            save_config("theme_mode", self.app_state.current_theme_mode)

            # Step 3: Force multiple paint cycles to complete all canvas redraws
            # while the window is still invisible.
            for _ in range(3):
                self.update_idletasks()
                self.update()

            # Step 4: M2 — Clear icon cache so CTkImage objects are recreated
            # with the new appearance mode on next access.
            if hasattr(self, 'icon_images'):
                self.icon_images.clear_cache()

            # Step 5: Update theme-dependent widgets + root-window background
            self._sync_root_background()
            self._sync_macos_titlebar()
            self._update_theme_icon()
            self.play_sound("click")

            if hasattr(self, 'announcement_label'):
                self.announcement_label.update_colors()

            # Step 6: Restyle treeviews while still invisible
            self.restyle_all_treeviews()
            self.update_idletasks()

            # Step 7: Smooth fade-in (6 steps x 20ms = 120ms — snappier)
            self._fade_in_after_theme(step=0)
        except Exception:
            # Safety: if anything goes wrong, ensure window is visible
            self.attributes("-alpha", 1.0)
            self.app_state._is_theme_transitioning = False
            raise

    def _fade_in_after_theme(self, step=0):
        """Recursively fades the window alpha from 0.0 -> 1.0 in 6 steps (~120ms)."""
        if step <= 6:
            try:
                if self.winfo_exists():
                    alpha = step / 6
                    self.attributes("-alpha", alpha)
                    self.after(20, lambda: self._fade_in_after_theme(step + 1))
                else:
                    self.app_state._is_theme_transitioning = False
            except Exception:
                self.attributes("-alpha", 1.0)
                self.app_state._is_theme_transitioning = False
        else:
            self.attributes("-alpha", 1.0)
            self.app_state._is_theme_transitioning = False

    def _update_theme_icon(self) -> None:
        icon_key = f"theme_{self.app_state.current_theme_mode.lower()}"
        new_icon = self.icon_images.get(icon_key, self.icon_images.get("theme_system"))
        self.theme_btn.configure(image=new_icon)

    def _update_settings_btn_visuals(self, btn, is_active):
        if is_active:
            btn.configure(fg_color=("#C8E6C9", "#1B5E20"))
        else:
            btn.configure(fg_color="transparent")

    def _update_sound_btn_visual(self) -> None:
        """Clear ON/OFF visual for the sound button:
        ON  -> green pill background + normal speaker icon
        OFF -> muted background + 'muted' icon (speaker with red slash)
        """
        if not hasattr(self, 'sound_btn') or self.sound_btn is None:
            return
        enabled = self.app_state.sound_switch_var.get()
        if enabled:
            self.sound_btn.configure(
                image=self.icon_images.get("sound_on"),
                fg_color=("#C8E6C9", "#1B5E20"))
        else:
            self.sound_btn.configure(
                image=self._make_muted_icon(),
                fg_color=("#FEE2E2", "#450A0A"))

    def _make_muted_icon(self) -> Any:
        """Generate a 'muted' variant of the sound icon (red slash overlay).
        IMPORTANT: sound.png is 512x512 — the CTkImage MUST be sized to the
        same small size the icon manager uses (18x18) or the button blows up
        to fill the window. Result is cached so toggles don't re-decode.
        """
        cached = getattr(self, "_muted_icon_cache", None)
        if cached is not None:
            return cached
        try:
            base = Image.open(resource_path("assets/icons/sound.png")).convert("RGBA")
            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay)
            w, h = base.size
            margin = max(2, w // 8)
            d.line([(margin, h - margin), (w - margin, margin)],
                   fill=(220, 38, 38, 235), width=max(2, w // 7))
            base = Image.alpha_composite(base, overlay)
            result = ctk.CTkImage(base, size=(18, 18))
            self._muted_icon_cache = result
            return result
        except Exception:
            return self.icon_images.get("sound_on")

    def _update_header_welcome_message(self):
        if not self.header_welcome_prefix_label:
            return
        user_name, key_type = self.app_state.license_info.get('user_name'), self.app_state.license_info.get('key_type')
        if user_name:
            self.header_welcome_prefix_label.configure(text=f"v{config.APP_VERSION} | Welcome, ")
            self.header_welcome_name_label.configure(text=user_name)
            self.header_welcome_suffix_label.configure(text=" !")
            if key_type != 'trial':
                self.header_welcome_name_label.configure(text_color=("gold4", "#FFD700"), font=ctk.CTkFont(size=13, weight="bold"))
            else:
                self.header_welcome_name_label.configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"], font=ctk.CTkFont(size=13, weight="normal"))
        else:
            self.header_welcome_prefix_label.configure(text=f"v{config.APP_VERSION} | Log in, then select a task.")
            self.header_welcome_name_label.configure(text="")
            self.header_welcome_suffix_label.configure(text="")
