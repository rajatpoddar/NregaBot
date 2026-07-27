# tabs/autocomplete_widget.py
"""
Professional dropdown selector widget for NREGA Bot.

Replaces the old AutocompleteEntry (typing + suggestions) with a clean,
CTkOptionMenu-style dropdown. Click to open, click item to select.

When the suggestions list is empty, shows a "⚙️  Set in Settings" option
that navigates the user to the Settings tab to add data.

Used by both lite app and main app via the AutocompleteEntry alias.
"""

import customtkinter as ctk
from src.utils import get_logger
from typing import Any, Dict, List, Optional

logger = get_logger()


class DropdownSelect(ctk.CTkFrame):
    """
    A clean dropdown selector that looks and behaves like CTkOptionMenu.

    Features:
    - Click to open dropdown, click item to select
    - Arrow keys + Enter/ESC for keyboard navigation
    - Empty state: shows "⚙️  Set in Settings" → redirects to Settings tab
    - Live refresh: fetches fresh suggestions from history_manager each time
    - Auto-saves selection to history on pick

    Provides get(), delete(), insert() for drop-in compatibility with
    existing tab code that previously used CTkEntry-based widgets.
    """

    # ── Color constants (light, dark) ──
    COL_BG = ("#E8E8E8", "#2D2D2D")
    COL_HOVER = ("#BFDBFE", "#3B82F6")      # Blue hover (MR category style)
    COL_HOVER_TEXT = ("#1E40AF", "white")    # Text on blue hover
    COL_TEXT = ("gray20", "gray80")
    COL_PLACEHOLDER = ("gray45", "gray55")
    COL_SETTINGS_TEXT = ("#2563EB", "#60A5FA")
    COL_SETTINGS_BG = ("#DBEAFE", "#1E3A5F")
    COL_SETTINGS_HOVER = ("#BFDBFE", "#2563EB")
    COL_POPUP_BG = ("gray90", "gray20")

    ITEM_H = 32
    SETTINGS_LABEL = "⚙️  Set in Settings"

    def __init__(self, parent, suggestions_list=None, app_instance=None,
                 history_key=None, command=None, show_settings_option=True,
                 filter_func=None, **kwargs):
        width = kwargs.pop('width', 160)
        height = kwargs.pop('height', 30)
        corner_radius = kwargs.pop('corner_radius', 6)
        font = kwargs.pop('font', ctk.CTkFont(size=13))

        super().__init__(parent, width=width, height=height, fg_color="transparent")
        self._command = command
        self.grid_propagate(False)

        self.app = app_instance
        self.history_key = history_key
        self.suggestions = list(suggestions_list) if suggestions_list else []
        self._show_settings_option = show_settings_option
        self.filter_func = filter_func  # Optional: function() -> list for dynamic filtering
        self._popup: Optional[ctk.CTkToplevel] = None
        self._selected: str = ""

        # ── Dropdown trigger button ──
        self._btn = ctk.CTkButton(
            self,
            text="",
            anchor="w",
            fg_color=self.COL_BG,
            text_color=self.COL_PLACEHOLDER,
            hover_color=self.COL_HOVER,
            corner_radius=corner_radius,
            height=height,
            font=font,
            command=self._toggle,
            **{k: v for k, v in kwargs.items() if k in ('width',)}
        )
        self._btn.pack(fill="both", expand=True)

        # ── Keyboard bindings ──
        self._btn.bind("<Down>", lambda e: self._show(), add="+")
        self._btn.bind("<Return>", lambda e: self._show(), add="+")

        self._update_display()

    # ────────────────────────────────────────────────────────────────
    # DISPLAY HELPERS
    # ────────────────────────────────────────────────────────────────

    def _update_display(self):
        """Update button text based on state."""
        has_data = bool([s for s in self.suggestions if s])
        if self._selected:
            self._btn.configure(text=self._selected, text_color=self.COL_TEXT)
        elif has_data:
            self._btn.configure(text="▾  Select...", text_color=self.COL_PLACEHOLDER)
        else:
            self._btn.configure(text="▾  Click to select", text_color=self.COL_PLACEHOLDER)

    # ────────────────────────────────────────────────────────────────
    # POPUP MANAGEMENT
    # ────────────────────────────────────────────────────────────────

    def _toggle(self):
        if self._popup and self._popup.winfo_exists():
            self._hide()
        else:
            self._show()

    def _show(self):
        """Build and show the dropdown popup."""
        if self._popup and self._popup.winfo_exists():
            return

        # Refresh suggestions — use filter_func if provided, else history_manager
        if self.filter_func:
            try:
                fresh = self.filter_func()
                if fresh is not None:
                    self.suggestions = list(fresh)
            except Exception:
                pass
        elif self.history_key and self.app and hasattr(self.app, 'history_manager'):
            try:
                fresh = self.app.history_manager.get_suggestions(self.history_key)
                if fresh:
                    self.suggestions = list(fresh)
            except Exception:
                pass

        # Dedup case-insensitively but preserve original case for display
        seen = set()
        items = []
        for s in sorted((x for x in self.suggestions if x), key=str.lower):
            low = s.lower()
            if low not in seen:
                seen.add(low)
                items.append(s)
        has_data = bool(items)

        if has_data:
            if self._show_settings_option:
                items.append(self.SETTINGS_LABEL)
        else:
            if self._show_settings_option:
                items = [self.SETTINGS_LABEL]

        # ── Create popup toplevel ──
        self._popup = ctk.CTkToplevel(self)
        self._popup.overrideredirect(True)
        # NOTE: Do NOT call transient() — it breaks click event delivery to
        # the main window after the popup is destroyed. overrideredirect + 
        # transient has a known Tk bug where mouse clicks stop working in
        # the main window until you click outside the application.
        self._popup.attributes("-topmost", True)

        # Position below button
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            w = max(self.winfo_width(), 180)
        except Exception:
            self._popup = None
            return

        popup_h = len(items) * self.ITEM_H + 4
        screen_h = self.winfo_screenheight()
        if y + popup_h > screen_h:
            y = self.winfo_rooty() - popup_h
            if y < 20:
                y = 20

        self._popup.geometry(f"{w}x{popup_h}+{x}+{y}")

        # ── Container frame ──
        frame = ctk.CTkFrame(self._popup, fg_color=self.COL_POPUP_BG, corner_radius=6)
        frame.pack(fill="both", expand=True)

        # ── Create item buttons ──
        for item in items:
            is_settings = (item == self.SETTINGS_LABEL)
            btn = ctk.CTkButton(
                frame,
                text=item,
                anchor="w",
                fg_color=self.COL_SETTINGS_BG if is_settings else "transparent",
                text_color=self.COL_SETTINGS_TEXT if is_settings else self.COL_TEXT,
                hover_color=self.COL_HOVER,
                corner_radius=0,
                height=self.ITEM_H,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda v=item: self._select(v),
            )
            btn.pack(fill="x")

        # When button loses focus (user clicks nav/elsewhere), hide popup
        self._btn.bind("<FocusOut>", self._on_btn_focusout, add="+")

    def _on_btn_focusout(self, event):
        """When the dropdown button loses focus, hide popup after a delay
        so that a click on a popup item registers first."""
        self.after(350, self._safe_hide)

    def _hide(self):
        """Destroy the popup immediately and unbind FocusOut."""
        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        try:
            self._btn.unbind("<FocusOut>", self._on_btn_focusout)
        except Exception:
            pass

    def _safe_hide(self):
        """Hide popup if it still exists (used after delay)."""
        if self._popup and self._popup.winfo_exists():
            self._hide()

    # ────────────────────────────────────────────────────────────────
    # SELECTION
    # ────────────────────────────────────────────────────────────────

    def _select(self, value):
        """Handle user selecting an item from the dropdown."""
        self._hide()

        # Force focus back to main window — _hide() alone doesn't restore
        # it, and transient() was removed because it breaks click delivery.
        try:
            tl = self.winfo_toplevel()
            if tl.winfo_exists():
                tl.focus_force()
        except Exception:
            pass

        if value == self.SETTINGS_LABEL:
            if self.app and hasattr(self.app, 'show_frame'):
                try:
                    self.app.show_frame("Settings")
                    if hasattr(self.app, 'show_toast'):
                        self.app.show_toast(
                            "Add data in Settings → Panchayat Suggestions",
                            kind="info", duration=4000,
                        )
                except Exception:
                    pass
            return

        # Store and display the selection
        self._selected = value
        self._btn.configure(text=value, text_color=self.COL_TEXT)

        # Save to history
        if self.history_key and self.app and hasattr(self.app, 'update_history'):
            try:
                self.app.update_history(self.history_key, value)
            except Exception:
                pass

        # Call command callback if provided
        if self._command:
            try:
                self._command(value)
            except Exception:
                pass

        # Trigger any bound events
        try:
            self.event_generate("<<DropdownSelect>>")
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────
    # COMPATIBILITY METHODS — match CTkEntry / AutocompleteEntry API
    # ────────────────────────────────────────────────────────────────

    def get(self) -> str:
        """Return currently selected value (empty string if none)."""
        return self._selected

    def delete(self, first=0, last=None):
        """Clear the current selection (matches CTkEntry.delete API)."""
        self._selected = ""
        self._update_display()

    def insert(self, index, value: str):
        """Set a value programmatically (matches CTkEntry.insert API)."""
        if value:
            self._selected = value
            self._btn.configure(text=self._selected, text_color=self.COL_TEXT)
            self._update_display()

    def configure(self, **kwargs):
        """Pass relevant config to internal button, rest to frame."""
        btn_keys = {'state', 'fg_color', 'text_color', 'hover_color', 'font'}
        btn_kwargs = {k: kwargs.pop(k) for k in list(kwargs.keys()) if k in btn_keys}
        if btn_kwargs:
            self._btn.configure(**btn_kwargs)
        super().configure(**kwargs)


    def set(self, value: str):
        """Direct setter — matches CTkComboBox.set() / CTkOptionMenu.set() API.
        Clears current selection and inserts the given value."""
        self.delete(0, 'end')
        if value:
            self.insert(0, value)


# ════════════════════════════════════════════════════════════════════
# CENTRALIZED DROPDOWN FACTORY
# Use this to create a consistent dropdown across the entire app.
# ════════════════════════════════════════════════════════════════════

def create_dropdown(parent, suggestions_list=None, app_instance=None,
                    history_key=None, command=None, width=160,
                    placeholder_text=None, show_settings_option=True,
                    **kwargs):
    """Create a consistent DropdownSelect widget across the entire app.
    
    All dropdowns should use this factory for a uniform look and feel.
    Supports CTkComboBox, CTkEntry, and AutocompleteEntry replacement.
    
    Args:
        parent: Parent widget
        suggestions_list: List of items to show in dropdown
        app_instance: App instance for history_manager access
        history_key: Key for saving/loading from history
        command: Callback when item is selected (receives selected value)
        width: Widget width
        placeholder_text: Placeholder text when nothing selected
        show_settings_option: Show "⚙️ Set in Settings" option (default True)
        **kwargs: Passed to DropdownSelect.__init__
    """
    return AutocompleteEntry(
        parent,
        suggestions_list=suggestions_list or [],
        app_instance=app_instance,
        history_key=history_key,
        command=command,
        width=width,
        show_settings_option=show_settings_option,
        **kwargs,
    )


# ────────────────────────────────────────────────────────────────────
# ALIAS — AutocompleteEntry is now DropdownSelect
# All tabs that import AutocompleteEntry will get this new widget.
# Lite app monkey-patches this same way via lite_app.py.
# ────────────────────────────────────────────────────────────────────

class AutocompleteEntry(DropdownSelect):
    """Alias for DropdownSelect — replaces old typing-based autocomplete.
    
    All existing tab imports of AutocompleteEntry now get a clean dropdown.
    Lite app monkey-patch in lite_app.py maps AutocompleteEntry → LiteDropdown,
    which is also this class (kept as alias for clarity).
    """
    pass


# LiteDropdown alias — used by lite_app.py monkey-patch
class LiteDropdown(DropdownSelect):
    """Alias for DropdownSelect used by the lite app monkey-patch."""
    pass
