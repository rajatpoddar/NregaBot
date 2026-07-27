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
    A professional dropdown selector that looks like a native combobox.

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
    COL_BG = ("#FFFFFF", "#2D2D2D")          # Clean white / dark
    COL_BORDER = ("#D0D0D0", "#555555")       # Subtle border
    COL_BORDER_FOCUS = ("#3B82F6", "#60A5FA") # Blue border on hover/open
    COL_ARROW_BG = ("#F5F5F5", "#3A3A3A")     # Arrow area bg
    COL_ARROW_HOVER = ("#E8E8E8", "#4A4A4A")  # Arrow area hover
    COL_HOVER = ("#BFDBFE", "#3B82F6")        # Blue hover (popup items)
    COL_TEXT = ("gray10", "gray90")
    COL_PLACEHOLDER = ("gray45", "gray60")
    COL_SETTINGS_TEXT = ("#2563EB", "#60A5FA")
    COL_SETTINGS_BG = ("#DBEAFE", "#1E3A5F")
    COL_POPUP_BG = ("#FFFFFF", "#2D2D2D")
    COL_POPUP_BORDER = ("#D0D0D0", "#4A4A4A")

    ITEM_H = 34
    SETTINGS_LABEL = "⚙️  Set in Settings"
    ARROW_TEXT = "▼"

    def __init__(self, parent, suggestions_list=None, app_instance=None,
                 history_key=None, command=None, show_settings_option=True,
                 filter_func=None, **kwargs):
        width = kwargs.pop('width', 160)
        height = kwargs.pop('height', 32)
        corner_radius = kwargs.pop('corner_radius', 6)
        font = kwargs.pop('font', ctk.CTkFont(size=13))

        super().__init__(parent, width=width, height=height,
                         fg_color=self.COL_BG,
                         border_width=1, border_color=self.COL_BORDER,
                         corner_radius=corner_radius)
        self._command = command
        self.grid_propagate(False)

        self.app = app_instance
        self.history_key = history_key
        self.suggestions = list(suggestions_list) if suggestions_list else []
        self._show_settings_option = show_settings_option
        self.filter_func = filter_func
        self._popup: Optional[ctk.CTkToplevel] = None
        self._selected: str = ""
        self._corner_radius = corner_radius
        self._disabled = False

        # ── Inner layout (text on left, arrow on right) ──
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # Left: text label
        self._label = ctk.CTkLabel(
            inner,
            text="",
            anchor="w",
            text_color=self.COL_PLACEHOLDER,
            font=font,
        )
        self._label.pack(side="left", fill="x", expand=True, padx=(10, 4))

        # Right: arrow button
        self._arrow_btn = ctk.CTkButton(
            inner,
            text=self.ARROW_TEXT,
            width=28,
            fg_color=self.COL_ARROW_BG,
            hover_color=self.COL_ARROW_HOVER,
            text_color=self.COL_TEXT,
            font=ctk.CTkFont(size=10),
            corner_radius=4,
            command=self._toggle,
        )
        self._arrow_btn.pack(side="right", padx=(0, 3), pady=3)

        # Make the label clickable too
        self._inner = inner

        # Store bound callbacks so we can unbind/rebind on disable
        self._bindings_active = True
        self._bind_click()

        # ── Keyboard bindings on label ──
        self._label.bind("<Down>", lambda e: self._show(), add="+")
        self._label.bind("<Return>", lambda e: self._show(), add="+")

        self._update_display()

    # ────────────────────────────────────────────────────────────────
    # DISPLAY HELPERS
    # ────────────────────────────────────────────────────────────────

    def _update_display(self):
        """Update label text based on state."""
        has_data = bool([s for s in self.suggestions if s])
        if self._selected:
            self._label.configure(text=self._selected, text_color=self.COL_TEXT)
        elif has_data:
            self._label.configure(text="Select...", text_color=self.COL_PLACEHOLDER)
        else:
            self._label.configure(text="Click to select", text_color=self.COL_PLACEHOLDER)

    def _set_focused_style(self, focused: bool):
        """Toggle border color on open/hover."""
        color = self.COL_BORDER_FOCUS if focused else self.COL_BORDER
        try:
            self.configure(border_color=color)
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────
    # POPUP MANAGEMENT
    # ────────────────────────────────────────────────────────────────
    def _bind_click(self):
        """Bind click events to open dropdown (unbinds first to prevent duplicates)."""
        try:
            self._label.unbind("<Button-1>")
            self._inner.unbind("<Button-1>")
        except Exception:
            pass
        self._label.bind("<Button-1>", lambda e: self._toggle())
        self._inner.bind("<Button-1>", lambda e: self._toggle())
        self._bindings_active = True

    def _unbind_click(self):
        """Remove click bindings (used when disabled)."""
        try:
            self._label.unbind("<Button-1>")
            self._inner.unbind("<Button-1>")
        except Exception:
            pass
        self._bindings_active = False

    def _toggle(self):
        if self._disabled:
            return
        if self._popup and self._popup.winfo_exists():
            self._hide()
        else:
            self._show()

    def _show(self):
        """Build and show the dropdown popup."""
        if self._disabled:
            return
        if self._popup and self._popup.winfo_exists():
            return

        self._set_focused_style(True)

        # Refresh suggestions
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

        # Build sorted, deduped items
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

        # ── Create popup ──
        self._popup = ctk.CTkToplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)

        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height() - 1
            w = max(self.winfo_width(), 180)
        except Exception:
            self._popup = None
            self._set_focused_style(False)
            return

        popup_h = len(items) * self.ITEM_H + 6
        screen_h = self.winfo_screenheight()
        if y + popup_h > screen_h:
            y = self.winfo_rooty() - popup_h
            if y < 30:
                y = 30

        self._popup.geometry(f"{w}x{popup_h}+{x}+{y}")

        # ── Popup container with border/shadow effect ──
        frame = ctk.CTkFrame(
            self._popup,
            fg_color=self.COL_POPUP_BG,
            border_width=1,
            border_color=self.COL_POPUP_BORDER,
            corner_radius=self._corner_radius,
        )
        frame.pack(fill="both", expand=True)

        # ── Item buttons ──
        for i, item in enumerate(items):
            is_settings = (item == self.SETTINGS_LABEL)
            top_pad = 2 if i == 0 else 0
            btn = ctk.CTkButton(
                frame,
                text=item,
                anchor="w",
                fg_color=self.COL_SETTINGS_BG if is_settings else "transparent",
                text_color=self.COL_SETTINGS_TEXT if is_settings else self.COL_TEXT,
                hover_color=self.COL_HOVER,
                corner_radius=0,
                height=self.ITEM_H,
                font=ctk.CTkFont(size=13),
                command=lambda v=item: self._select(v),
            )
            btn.pack(fill="x", padx=1, pady=(top_pad, 0))

        # Hide on focus loss
        self._label.bind("<FocusOut>", self._on_focusout, add="+")
        self._arrow_btn.bind("<FocusOut>", self._on_focusout, add="+")

    def _on_focusout(self, event):
        """Hide popup after delay so item click registers first."""
        self.after(350, self._safe_hide)

    def _hide(self):
        """Destroy the popup immediately."""
        self._set_focused_style(False)
        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        try:
            self._label.unbind("<FocusOut>", self._on_focusout)
        except Exception:
            pass
        try:
            self._arrow_btn.unbind("<FocusOut>", self._on_focusout)
        except Exception:
            pass

    def _safe_hide(self):
        if self._popup and self._popup.winfo_exists():
            self._hide()

    # ────────────────────────────────────────────────────────────────
    # SELECTION
    # ────────────────────────────────────────────────────────────────

    def _select(self, value):
        """Handle user selecting an item from the dropdown."""
        self._hide()

        # Restore focus
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

        self._selected = value
        self._update_display()

        # Save to history
        if self.history_key and self.app and hasattr(self.app, 'update_history'):
            try:
                self.app.update_history(self.history_key, value)
            except Exception:
                pass

        # Call command callback
        if self._command:
            try:
                self._command(value)
            except Exception:
                pass

        # Trigger bound events
        try:
            self.event_generate("<<DropdownSelect>>")
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────
    # COMPATIBILITY METHODS
    # ────────────────────────────────────────────────────────────────

    def get(self) -> str:
        return self._selected

    def delete(self, first=0, last=None):
        self._selected = ""
        self._update_display()

    def insert(self, index, value: str):
        if value:
            self._selected = value
            self._update_display()

    def configure(self, **kwargs):
        # Handle state="disabled" / state="normal" — disable entire widget
        if 'state' in kwargs:
            state = kwargs.pop('state')
            self._disabled = (state == 'disabled')
            self._arrow_btn.configure(state=state)
            if self._disabled:
                self._unbind_click()
                self._label.configure(text_color=("#AAAAAA", "#666666"))
            else:
                self._bind_click()
                self._update_display()

        # Pass remaining visual kwargs to arrow button
        btn_keys = {'fg_color', 'text_color', 'hover_color', 'font'}
        btn_kwargs = {k: kwargs.pop(k) for k in list(kwargs.keys()) if k in btn_keys}
        if btn_kwargs:
            self._arrow_btn.configure(**btn_kwargs)
        super().configure(**kwargs)

    def set(self, value: str):
        self.delete(0, 'end')
        if value:
            self.insert(0, value)


# ════════════════════════════════════════════════════════════════════
# CENTRALIZED DROPDOWN FACTORY
# ════════════════════════════════════════════════════════════════════

def create_dropdown(parent, suggestions_list=None, app_instance=None,
                    history_key=None, command=None, width=160,
                    placeholder_text=None, show_settings_option=True,
                    **kwargs):
    """Create a consistent DropdownSelect widget across the entire app."""
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
# ALIASES
# ────────────────────────────────────────────────────────────────────

class AutocompleteEntry(DropdownSelect):
    """Alias for DropdownSelect — old code compatibility."""
    pass


class LiteDropdown(DropdownSelect):
    """Alias for DropdownSelect used by the lite app monkey-patch."""
    pass
