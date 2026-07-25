# tabs/autocomplete_widget.py
import customtkinter as ctk
from src.utils import get_logger
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = get_logger()

class AutocompleteEntry(ctk.CTkEntry):
    def __init__(self, parent, suggestions_list=None, app_instance=None, history_key=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.suggestions = suggestions_list if suggestions_list is not None else []
        self.app = app_instance
        self.history_key = history_key
        
        self._suggestion_toplevel = None
        self._suggestion_listbox = None
        
        # Widget Pooling
        self._pool_frames = [] 
        self._pool_labels = []
        self._MAX_SUGGESTIONS = 10  # Increased for better dropdown feel
        self._visible_suggestions = []
        
        # Debounce Timer
        self._typing_timer = None
        self._is_selecting = False 
        self._active_suggestion_index = -1

        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Down>", self._on_arrow_down)
        self.bind("<Up>", self._on_arrow_up)
        self.bind("<Return>", self._on_enter)
        
        # Bind destroy event to cleanup timers
        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event):
        """Clean up timers and toplevels to prevent crashes."""
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
            self._typing_timer = None
        if self._suggestion_toplevel:
            self._suggestion_toplevel.destroy()
            self._suggestion_toplevel = None

    # ────────────────────────────────────────────────────────────────
    # DROPDOWN ON FOCUS / CLICK
    # ────────────────────────────────────────────────────────────────
    def _on_focus_in(self, event):
        """Show all suggestions when field gets focus (dropdown-like)."""
        self.after(100, self._show_all_suggestions)

    def _on_click(self, event):
        """Show all suggestions on click (dropdown-like)."""
        self.after(100, self._show_all_suggestions)

    def _show_all_suggestions(self):
        """Show ALL saved suggestions in UPPERCASE sorted order (dropdown feel)."""
        try:
            if not self.winfo_exists(): return
        except Exception:
            return

        current_text = self.get().strip()
        if current_text:
            self._process_filtering()
            return

        # No text typed — show ALL suggestions in uppercase
        uppercase_suggestions = sorted(set(s.upper() for s in self.suggestions if s))
        if not uppercase_suggestions:
            self._hide_suggestions()
            return

        # Show LIMITED set (max 10)
        limited = uppercase_suggestions[:self._MAX_SUGGESTIONS]
        self._show_suggestions(limited)

    # ────────────────────────────────────────────────────────────────
    # AUTO-UPPERCASE + FILTER ON KEY RELEASE
    # ────────────────────────────────────────────────────────────────
    def _on_key_release(self, event):
        if self._is_selecting:
            return
        if event.keysym in ("Up", "Down", "Return", "Enter", "Tab", "Escape"):
            return
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return

        # Auto-uppercase as user types
        current = self.get()
        upper = current.upper()
        if current != upper:
            self.delete(0, "end")
            self.insert(0, upper)

        if self._typing_timer:
            self.after_cancel(self._typing_timer)
        self._typing_timer = self.after(150, self._process_filtering)

    def _process_filtering(self):
        """Filter suggestions based on current text (case-insensitive) and show in UPPERCASE."""
        try:
            if not self.winfo_exists(): return
        except Exception:
            return

        current_text = self.get()  # Already uppercase
        if not current_text:
            self._show_all_suggestions()
            return

        matches = []
        for s in self.suggestions:
            if current_text in s.upper():
                matches.append(s.upper())
                if len(matches) >= self._MAX_SUGGESTIONS:
                    break

        if matches:
            self._show_suggestions(matches)
        else:
            self._hide_suggestions()

    # ────────────────────────────────────────────────────────────────
    # POPUP MANAGEMENT
    # ────────────────────────────────────────────────────────────────
    def _init_popup(self):
        if self._suggestion_toplevel and self._suggestion_toplevel.winfo_exists():
            return

        self._suggestion_toplevel = ctk.CTkToplevel(self)
        self._suggestion_toplevel.wm_overrideredirect(True)
        try:
            self._suggestion_toplevel.transient(self.winfo_toplevel())
        except Exception as e:
            logger.debug("Autocomplete: failed to set transient: %s", e)
        self._suggestion_toplevel.attributes("-topmost", True)
        self._suggestion_toplevel.withdraw()

        self._suggestion_listbox = ctk.CTkFrame(self._suggestion_toplevel, fg_color=("gray90", "gray20"))
        self._suggestion_listbox.pack(expand=True, fill="both")

        self._pool_frames = []
        self._pool_labels = []

        for i in range(self._MAX_SUGGESTIONS):
            frame = ctk.CTkFrame(self._suggestion_listbox, fg_color="transparent", corner_radius=0)

            lbl = ctk.CTkLabel(frame, text="", anchor="w", padx=5, font=ctk.CTkFont(size=13, weight="bold"))
            lbl.pack(fill="x", expand=True)

            frame.bind("<Button-1>", lambda e, idx=i: self._on_click_suggestion(idx))
            lbl.bind("<Button-1>", lambda e, idx=i: self._on_click_suggestion(idx))
            frame.bind("<Enter>", lambda e, idx=i: self._highlight_suggestion(idx))

            self._pool_frames.append(frame)
            self._pool_labels.append(lbl)

    def _show_suggestions(self, suggestions):
        self._init_popup()
        self._visible_suggestions = suggestions

        try:
            if not self.winfo_exists():
                return
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            w = self.winfo_width()
            self._suggestion_toplevel.wm_geometry(f"{w}x{len(suggestions)*30}+{x}+{y}")
            self._suggestion_toplevel.deiconify()
            self._suggestion_toplevel.lift()
            self._suggestion_toplevel.attributes("-topmost", True)
        except Exception:
            return

        self._active_suggestion_index = -1

        for i in range(self._MAX_SUGGESTIONS):
            if i < len(suggestions):
                text = suggestions[i]
                self._pool_labels[i].configure(text=text)
                self._pool_frames[i].pack(fill="x", ipady=2)
                self._pool_frames[i].configure(fg_color="transparent")
            else:
                self._pool_frames[i].pack_forget()

    def _hide_suggestions(self):
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
            self._typing_timer = None
        if self._suggestion_toplevel:
            self._suggestion_toplevel.withdraw()
        self._active_suggestion_index = -1

    # ────────────────────────────────────────────────────────────────
    # SELECTION & NAVIGATION
    # ────────────────────────────────────────────────────────────────
    def _on_click_suggestion(self, index):
        if 0 <= index < len(self._visible_suggestions):
            self._select_suggestion(self._visible_suggestions[index])

    def _select_suggestion(self, value):
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
        self._is_selecting = True

        self.delete(0, "end")
        self.insert(0, value.upper())  # Always uppercase

        try:
            self._hide_suggestions()
            self.focus_force()
            self.event_generate("<KeyRelease>")
        except Exception as e:
            logger.debug("Autocomplete: failed to generate KeyRelease: %s", e)
        self._is_selecting = False

    def _on_focus_out(self, event):
        try:
            self.after(250, lambda: self._hide_suggestions() if self.winfo_exists() else None)
        except Exception as e:
            logger.debug("Autocomplete: failed to schedule hide: %s", e)

    def _highlight_suggestion(self, index):
        try:
            for i, frame in enumerate(self._pool_frames):
                if not frame.winfo_ismapped():
                    continue
                color = ("gray80", "gray30") if i == index else "transparent"
                frame.configure(fg_color=color)
            self._active_suggestion_index = index
        except Exception as e:
            logger.debug("Autocomplete: failed to highlight suggestion: %s", e)

    def _on_arrow_down(self, event):
        if not self._visible_suggestions:
            return
        self._active_suggestion_index = (self._active_suggestion_index + 1) % len(self._visible_suggestions)
        self._highlight_suggestion(self._active_suggestion_index)
        return "break"

    def _on_arrow_up(self, event):
        if not self._visible_suggestions:
            return
        self._active_suggestion_index = (self._active_suggestion_index - 1) % len(self._visible_suggestions)
        self._highlight_suggestion(self._active_suggestion_index)
        return "break"

    def _on_enter(self, event):
        if self._visible_suggestions and self._active_suggestion_index != -1:
            self._select_suggestion(self._visible_suggestions[self._active_suggestion_index])
            return "break"
