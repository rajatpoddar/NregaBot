import customtkinter as ctk
import tkinter
import tkinter as tk
import webbrowser
import os
import re
import time
import platform
import subprocess
import threading
import queue
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from PIL import Image
from src import config
from src.utils import resource_path, get_logger, get_data_path
from src.i18n import tr, get_language, get_available_languages, set_language, LANGUAGES, suggest_language_for_state

logger = get_logger()

# --- 0. AFTER TRACKER (Callback Cleanup Utility) ---
class AfterTracker:
    """
    Tracks after() callbacks and auto-cancels them on widget destroy.
    
    Prevents "ghost callbacks" — after() timers that continue firing
    after the associated widget has been destroyed or hidden.
    
    Usage:
        self._tracker = AfterTracker(self)
        self._tracker.after(1000, self.my_method)
        # Auto-cancels when widget is destroyed via <Destroy> binding
        # You can also manually call: self._tracker.cancel_all()
    """
    def __init__(self, widget: Any) -> None:
        self.widget = widget
        self._ids: Set[str] = set()
        # Auto-cancel on widget destroy
        widget.bind("<Destroy>", self._on_destroy_evt, add="+")

    def __call__(self, ms: int, callback: Callable, *args: Any) -> str:
        """Allows the tracker instance to be called directly.
        e.g. self.tracker(1000, callback) instead of self.tracker.after(1000, callback).
        This enables HomeTab's pattern: self.safe_after = AfterTracker(self)."""
        return self.after(ms, callback, *args)

    def after(self, ms: int, callback: Callable, *args: Any) -> str:
        """Register a tracked after() callback.
        Auto-cancels when widget is destroyed. Use this instead of widget.after()."""
        after_id = self.widget.after(ms, lambda: self._wrap(callback, args))
        self._ids.add(after_id)
        return after_id

    def after_id(self, after_id: str) -> str:
        """Track an externally-created after() ID."""
        self._ids.add(after_id)
        return after_id

    def _wrap(self, callback: Callable, args: Tuple) -> None:
        """Wrap the callback so it's safe even after widget destruction."""
        try:
            if self.widget.winfo_exists():
                callback(*args)
        except Exception as e:
            logger.debug("AfterTracker._wrap: callback failed (widget may be destroyed): %s", e)

    def _on_destroy_evt(self, event: Any) -> None:
        """Cancel all tracked callbacks when this specific widget is destroyed.
        The event.widget check prevents us from responding to child widget destroys."""
        if event.widget is not self.widget:
            return
        self.cancel_all()

    def cancel_all(self) -> None:
        """Cancel all pending tracked callbacks immediately."""
        for after_id in list(self._ids):
            try:
                self.widget.after_cancel(after_id)
            except Exception as e:
                logger.debug("Failed to cancel after_id %s: %s", after_id, e)
        self._ids.clear()

    def __del__(self) -> None:
        self.cancel_all()

# --- 1. COLLAPSIBLE FRAME (Sidebar Categories) ---
class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent: Any, title: str = "") -> None:
        # OPTIMIZATION: corner_radius=0 for faster rendering
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.title = title

        # Header Frame
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(10, 2)) # Padding reduced
        
        self.header_label = ctk.CTkLabel(
            self.header_frame, 
            text=self.title.upper(),
            anchor="w", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("gray40", "gray60")
        )
        self.header_label.pack(side="left", fill="x", expand=True)

        # OPTIMIZATION: Removed Separator Line (Performance Boost)
        # Jo line pehle thi wo ab widget load nahi badhayegi

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_frame.grid(row=1, column=0, sticky="ew", padx=(0, 0))

    def add_widget(self, widget: Any, **pack_options: Any) -> Any:
        widget.pack(in_=self.content_frame, **pack_options)
        return widget

# --- 3. SKELETON LOADER (Loading Effect) ---

class FormSkeleton(tk.Frame):
    def __init__(self, parent: Any, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        # Background color aapke app theme ke hisab se set karein
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.bind("<Configure>", self.redraw)

    def redraw(self, event: Any = None) -> None:
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # Skeleton color (Light Grey)
        skel_color = config.COLORS["skel_light"] 

        # 1. Title/Header Block (Top Left)
        self.canvas.create_rectangle(20, 20, 300, 50, fill=skel_color, outline="")

        # 2. Form Fields (Rows of Label + Input)
        # Yeh loop 8 lines/rows banayega jo aapke 'data texts' ko represent karega
        start_y = 80
        gap = 60 # Har row ke beech ka gap
        
        for i in range(8): 
            y = start_y + (i * gap)
            
            # Label Skeleton (Chota box left side)
            self.canvas.create_rectangle(20, y, 150, y+20, fill=skel_color, outline="")
            
            # Input Field Skeleton (Lamba box right side)
            self.canvas.create_rectangle(170, y, w - 50, y+35, fill=skel_color, outline="")

        # 3. Action Buttons (Bottom)
        btn_y = start_y + (8 * gap) + 20
        self.canvas.create_rectangle(20, btn_y, 140, btn_y+40, fill=skel_color, outline="")
        self.canvas.create_rectangle(160, btn_y, 280, btn_y+40, fill=skel_color, outline="")
class SkeletonLoader(ctk.CTkFrame):
    """R6: Canvas-based skeleton loading effect.
    Replaces 55+ CTkFrame placeholders with a single tk.Canvas
    for much faster rendering and less GPU canvas redraw overhead.
    """
    def __init__(self, parent: Any, rows: int = 8, **kwargs: Any) -> None:
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.pack(fill="both", expand=True, padx=20, pady=20)

        # Use plain tk.Canvas instead of 55+ CTkFrames
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self._items: List[int] = []  # Canvas item IDs
        self._rows = rows
        self._animating = True
        self._animate_step = 0

        # Draw skeleton shapes on the canvas when widget is first sized
        self.bind("<Configure>", self._on_resize)

        # Create AfterTracker for auto-cleanup on destroy
        self._tracker = AfterTracker(self)
        self._tracker.after(1000, self._animate)

    def _get_colors(self) -> Tuple[str, Any, str, str]:
        """Return (bg_light, bg_dark, item_light, item_dark) based on current theme."""
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            return ("#2b2b2b", None, config.COLORS["skel_dark_1"], config.COLORS["skel_dark_2"])
        else:
            return ("#f0f0f0", None, config.COLORS["skel_light"], config.COLORS["skel_light_alt"])

    def _on_resize(self, event: Any = None) -> None:
        """Redraw skeleton shapes when widget resizes."""
        if not self.winfo_exists():
            return
        self._draw_skeleton()

    def _draw_skeleton(self) -> None:
        """Draw all skeleton placeholders on the canvas.
        Visual layout matches the original CTkFrame-based design:
          - Title bar (top-left)
          - 4 stat cards with circle + text lines
          - Table header + row data
        """
        self.canvas.delete("all")
        self._items = []

        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 400
        bg, _, color_a, _ = self._get_colors()

        # Set canvas background to match theme
        self.canvas.configure(bg=bg)

        # --- 1. Header Title ---
        y = 20
        _id = self.canvas.create_rectangle(20, y, 250, y + 30, fill=color_a, outline="", tags="skel")
        self._items.append(_id)

        # --- 2. Top Info Cards (4 stat cards) ---
        y = 75
        card_w = (w - 60) // 4  # 4 cards with padding
        for i in range(4):
            cx = 20 + i * (card_w + 8)
            # Card background
            self.canvas.create_rectangle(cx, y, cx + card_w, y + 65, fill=bg, outline="", tags="skel_bg")
            # Circle (icon placeholder)
            _id = self.canvas.create_oval(cx + 12, y + 10, cx + 12 + 40, y + 10 + 40, fill=color_a, outline="", tags="skel")
            self._items.append(_id)
            # Text line 1
            _id = self.canvas.create_rectangle(cx + 62, y + 12, cx + 62 + 60, y + 12 + 12, fill=color_a, outline="", tags="skel")
            self._items.append(_id)
            # Text line 2
            _id = self.canvas.create_rectangle(cx + 62, y + 30, cx + 62 + 40, y + 30 + 10, fill=color_a, outline="", tags="skel")
            self._items.append(_id)

        # --- 3. Table area ---
        y = 165
        table_h = h - y - 20
        # Table background
        self.canvas.create_rectangle(20, y, w - 20, y + table_h, fill=bg, outline="", tags="skel_bg")

        # Table header
        hy = y + 15
        _id = self.canvas.create_rectangle(40, hy, 140, hy + 18, fill=color_a, outline="", tags="skel")
        self._items.append(_id)
        _id = self.canvas.create_rectangle(160, hy, 300, hy + 18, fill=color_a, outline="", tags="skel")
        self._items.append(_id)

        # Table rows
        ry = hy + 35
        row_gap = 32
        for i in range(self._rows):
            if ry + 20 > y + table_h:
                break
            _id = self.canvas.create_rectangle(40, ry, 70, ry + 16, fill=color_a, outline="", tags="skel")
            self._items.append(_id)
            w2 = 180 if i % 2 == 0 else 120
            _id = self.canvas.create_rectangle(90, ry, 90 + w2, ry + 16, fill=color_a, outline="", tags="skel")
            self._items.append(_id)
            _id = self.canvas.create_rectangle(90 + w2 + 20, ry, w - 50, ry + 16, fill=color_a, outline="", tags="skel")
            self._items.append(_id)
            ry += row_gap

    def _animate(self) -> None:
        """Pulse animation: alternates between two shades for all skeleton items."""
        if not self._animating or not self.winfo_exists():
            return

        # Skip animation when not visible
        if not self.winfo_viewable():
            self._tracker.after(1000, self._animate)
            return

        # Get current theme colors
        _, _, color_a, color_b = self._get_colors()
        fill = color_b if self._animate_step == 0 else color_a
        self._animate_step = 1 - self._animate_step

        # Batch-update all skeleton item colors
        for item_id in self._items:
            try:
                self.canvas.itemconfig(item_id, fill=fill)
            except Exception as e:
                logger.debug("SkeletonLoader animate itemconfig failed: %s", e)

        self._tracker.after(1000, self._animate)

    def stop(self):
        """Stop animation and destroy the skeleton loader."""
        self._animating = False
        self._tracker.cancel_all()
        self.destroy()

# --- 4. MARQUEE LABEL (Running Text) ---
class MarqueeLabel(ctk.CTkFrame):
    def __init__(self, parent: Any, text: str, speed: int = 2, **kwargs: Any) -> None:
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.speed = speed
        self.raw_text = text
        self.safe_bg = (config.COLORS["bg_light"], config.COLORS["bg_darker"])
        
        self.canvas = tkinter.Canvas(
            self, 
            bg=self._apply_appearance_mode(self.safe_bg), 
            bd=0, 
            highlightthickness=0, 
            height=30,
            cursor="arrow" 
        )
        self.canvas.pack(fill="both", expand=True)
        
        self.items = [] 
        self.total_width = 0
        self.canvas_width = 1
        self.is_running = True
        
        # Create AfterTracker for auto-cleanup on destroy
        self._tracker = AfterTracker(self)
        
        self.bind("<Configure>", self._on_resize)
        self.bind("<Destroy>", self._on_destroy)
        self.update_text(text) 
        self._tracker.after(50, self._animate)

    def _on_destroy(self, event: Any) -> None:
        self.is_running = False
        self._tracker.cancel_all()

    def _on_resize(self, event: Any) -> None:
        self.canvas_width = event.width
        self.update_colors()

    def update_colors(self) -> None:
        try:
            if not self.winfo_exists(): return
            mode = ctk.get_appearance_mode()
            bg_color = self._apply_appearance_mode(self.safe_bg)
            self.canvas.configure(bg=bg_color)
            default_color = "gray90" if mode == "Dark" else "gray40"
            for item in self.items:
                if not item.get('is_link'):
                    self.canvas.itemconfig(item['id'], fill=default_color)
        except Exception as e:
            logger.debug("MarqueeLabel.update_colors failed: %s", e)

    def _parse_html(self, text: str) -> List[Dict[str, Any]]:
        pattern = re.compile(r'(<a\s+href="([^"]+)">(.+?)</a>|<b>(.+?)</b>|<i>(.+?)</i>)')
        parts = []
        last_pos = 0
        for match in pattern.finditer(text):
            if match.start() > last_pos:
                parts.append({'text': text[last_pos:match.start()], 'type': 'normal'})
            full_match = match.group(0)
            if full_match.startswith('<a'):
                parts.append({'text': match.group(3), 'type': 'link', 'url': match.group(2)})
            elif full_match.startswith('<b>'):
                parts.append({'text': match.group(4), 'type': 'bold'})
            elif full_match.startswith('<i>'):
                parts.append({'text': match.group(5), 'type': 'italic'})
            last_pos = match.end()
        if last_pos < len(text):
            parts.append({'text': text[last_pos:], 'type': 'normal'})
        return parts if parts else [{'text': text, 'type': 'normal'}]

    def update_text(self, new_text: str) -> None:
        if not self.winfo_exists(): return
        self.raw_text = new_text
        self.canvas.delete("all")
        self.items = []
        self.total_width = 0
        
        mode = ctk.get_appearance_mode()
        default_color = "gray90" if mode == "Dark" else "gray40"
        link_color = config.COLORS["blue"]
        base_font_family = "Segoe UI" if os.name == "nt" else "Arial"
        
        parsed_segments = self._parse_html(new_text)
        current_x = 10 
        y_pos = 15
        
        for seg in parsed_segments:
            text_content = seg['text']
            font_spec = (base_font_family, 13)
            fill_color = default_color
            is_link = False
            
            if seg['type'] == 'bold': font_spec = (base_font_family, 13, "bold")
            elif seg['type'] == 'italic': font_spec = (base_font_family, 13, "italic")
            elif seg['type'] == 'link':
                font_spec = (base_font_family, 13, "underline")
                fill_color = link_color
                is_link = True
            
            text_id = self.canvas.create_text(current_x, y_pos, text=text_content, anchor="w", fill=fill_color, font=font_spec)
            bbox = self.canvas.bbox(text_id)
            width = bbox[2] - bbox[0] if bbox else 0
            
            item_data = {'id': text_id, 'width': width, 'is_link': is_link, 'url': seg.get('url')}
            self.items.append(item_data)
            
            if is_link:
                self.canvas.tag_bind(text_id, "<Button-1>", lambda e, url=seg['url']: webbrowser.open(url))
                self.canvas.tag_bind(text_id, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(text_id, "<Leave>", lambda e: self.canvas.configure(cursor="arrow"))
            
            current_x += width
        self.total_width = current_x

    def pause(self):
        """Pause the marquee animation (called during window resize)."""
        self.is_paused = True

    def resume(self):
        """Resume the marquee animation (called after window resize ends)."""
        if hasattr(self, 'is_paused'):
            self.is_paused = False

    def _animate(self):
        if not self.is_running: return
        try:
            if not self.winfo_exists():
                self.is_running = False
                return
        except Exception:
            self.is_running = False
            return

        # Skip animation when widget is not visible on screen
        # Prevents unnecessary canvas operations when minimized/covered
        if not self.winfo_viewable():
            self._tracker.after(200, self._animate)
            return

        if not self.items:
            self._tracker.after(100, self._animate)
            return
        
        # Skip animation frames when paused (during resize) to avoid competing
        # with the window manager's repaint cycle.
        if getattr(self, 'is_paused', False):
            self._tracker.after(100, self._animate)  # Check less frequently when paused
            return

        try:
            first_item = self.items[0]
            try: self.canvas.bbox(first_item['id'])
            except: return 

            last_item = self.items[-1]
            last_coords = self.canvas.coords(last_item['id'])
            
            if not last_coords: 
                self._tracker.after(50, self._animate)
                return

            if last_coords[0] + last_item['width'] < 0:
                offset = self.canvas_width + 20
                current_x_reset = offset
                for item in self.items:
                    self.canvas.coords(item['id'], current_x_reset, 15)
                    current_x_reset += item['width']
            else:
                for item in self.items:
                    self.canvas.move(item['id'], -self.speed, 0)

            self._tracker.after(50, self._animate)
        except Exception:
            self.is_running = False

# --- 5. PROFESSIONAL TOAST NOTIFICATION ---
# A sleek, modern notification system that slides in from the bottom-right
# of the parent window. Features:
#   - Smooth eased slide + fade-in/out animations (16ms frames)
#   - Auto-dismiss with a silky progress bar (50ms updates)
#   - Title + message + details support
#   - Close button (click to dismiss instantly) + click-anywhere-to-dismiss
#   - Color-coded themes: success(green) / error(red) / warning(amber)
#     / info(blue) / automation(indigo) / running(cyan)
#   - Always-on-top watchdog that periodically re-asserts topmost + lift so
#     the toast never slips behind the app or other windows
#   - Stacking queue (max 3) with smooth reflow when a toast is dismissed

class ToastNotification(ctk.CTkToplevel):
    """Professional toast notification with smooth slide-in, progress bar, and close button.

    Kept as a standalone Toplevel (no parent passed to super().__init__()) so
    -topmost can raise it above ALL windows including the main app, browser, etc.
    A child Toplevel may stack behind other windows in some window managers
    despite -topmost.
    """

    _active_toasts: List['ToastNotification'] = []  # Class-level queue (newest first)
    _MAX_VISIBLE = 3  # Max toasts shown simultaneously
    _WIDTH = 380       # Fixed professional width
    _EDGE_MARGIN = 16  # Horizontal gap from the parent window edge
    _BOTTOM_OFFSET = 48  # Clear the app footer / OS taskbar
    _STACK_GAP = 10    # Vertical gap between stacked toasts
    _KEEP_TOP_MS = 350  # Watchdog interval for re-asserting topmost

    def __init__(self, parent: Any, message: str, kind: str = "success",
                 duration: int = 4000, title: str = "", details: str = "") -> None:
        # IMPORTANT: Do NOT pass parent to super().__init__(). A standalone
        # Toplevel (no parent) with -topmost=True stays above ALL windows
        # including the main app, browser, etc. A child Toplevel may stack
        # behind other windows in some window managers despite -topmost.
        super().__init__()
        self.parent = parent
        self._kind = kind
        self._duration = max(int(duration), 1500)
        self._start_time: Optional[float] = None
        self._progress_after_id: Optional[str] = None
        self._keep_top_after_id: Optional[str] = None
        self._fade_out_started = False
        self._destroyed = False
        self._animating_in = False
        self._reflow_epoch = 0  # Invalidates stale reflow animation loops

        # ── Theme-aware colors ──
        self._configs = {
            "success": {
                "icon": "✅", "bg": ("#065F46", "#065F46"),
                "border": ("#34D399", "#34D399"),
                "progress": ("#34D399", "#6EE7B7"),
                "accent": ("#6EE7B7", "#6EE7B7"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#D1FAE5", "#D1FAE5"),
                "hover": ("#047857", "#047857"),
            },
            "error": {
                "icon": "❌", "bg": ("#7F1D1D", "#7F1D1D"),
                "border": ("#F87171", "#FCA5A5"),
                "progress": ("#F87171", "#FCA5A5"),
                "accent": ("#FCA5A5", "#FCA5A5"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#FEE2E2", "#FEE2E2"),
                "hover": ("#B91C1C", "#B91C1C"),
            },
            "info": {
                "icon": "ℹ️", "bg": ("#1E3A5F", "#1E3A5F"),
                "border": ("#60A5FA", "#93C5FD"),
                "progress": ("#60A5FA", "#93C5FD"),
                "accent": ("#93C5FD", "#93C5FD"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#DBEAFE", "#DBEAFE"),
                "hover": ("#1E40AF", "#1E40AF"),
            },
            "warning": {
                "icon": "⚠️", "bg": ("#78350F", "#78350F"),
                "border": ("#FBBF24", "#FCD34D"),
                "progress": ("#FBBF24", "#FCD34D"),
                "accent": ("#FCD34D", "#FCD34D"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#FEF3C7", "#FEF3C7"),
                "hover": ("#B45309", "#B45309"),
            },
            "automation": {
                "icon": "🤖", "bg": ("#312E81", "#312E81"),
                "border": ("#818CF8", "#A5B4FC"),
                "progress": ("#818CF8", "#A5B4FC"),
                "accent": ("#A5B4FC", "#A5B4FC"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#E0E7FF", "#E0E7FF"),
                "hover": ("#3730A3", "#3730A3"),
            },
            "running": {
                "icon": "⚙️", "bg": ("#164E63", "#164E63"),
                "border": ("#38BDF8", "#7DD3FC"),
                "progress": ("#38BDF8", "#7DD3FC"),
                "accent": ("#7DD3FC", "#7DD3FC"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#CFFAFE", "#CFFAFE"),
                "hover": ("#0C4A6E", "#0C4A6E"),
            },
        }

        cfg = self._configs.get(kind, self._configs["info"])

        # ── Window setup ──
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=cfg["bg"])
        self.resizable(False, False)

        # ── Main frame ──
        self.frame = ctk.CTkFrame(self, fg_color=cfg["bg"], corner_radius=12,
                                   border_width=1, border_color=cfg["border"])
        self.frame.pack(fill="both", expand=True)

        # ── Left accent bar (subtle color stripe for a premium look) ──
        accent_bar = ctk.CTkFrame(self.frame, width=3, corner_radius=1,
                                   fg_color=cfg["accent"])
        accent_bar.place(relx=0.02, rely=0.5, relheight=0.82, anchor="w")

        # ── Content area ──
        self.content = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.content.pack(fill="x", padx=(20, 16), pady=(12, 6))
        self.content.grid_columnconfigure(2, weight=1)

        # Icon
        icon_lbl = ctk.CTkLabel(self.content, text=cfg["icon"],
                                font=("Segoe UI", 20), text_color=cfg["title_color"])
        icon_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 12), sticky="n")

        # Title (bold)
        title_text = title or kind.capitalize()
        self._title_label = ctk.CTkLabel(self.content, text=title_text,
                                          font=("Segoe UI", 13, "bold"),
                                          text_color=cfg["title_color"],
                                          anchor="w")
        self._title_label.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 2))

        # Message
        self._msg_label = ctk.CTkLabel(self.content, text=message,
                                        font=("Segoe UI", 12),
                                        text_color=cfg["msg_color"],
                                        wraplength=self._WIDTH - 110, justify="left",
                                        anchor="w")
        self._msg_label.grid(row=1, column=1, sticky="ew")

        # Details (optional, smaller text below)
        if details:
            self._details_label = ctk.CTkLabel(self.content, text=details,
                                               font=("Segoe UI", 10),
                                               text_color=cfg["msg_color"],
                                               wraplength=self._WIDTH - 110, justify="left",
                                               anchor="w")
            self._details_label.grid(row=2, column=1, sticky="ew", pady=(2, 0))

        # Close button (X)
        self._close_btn = ctk.CTkButton(
            self.content, text="✕", width=24, height=24, corner_radius=12,
            font=("Segoe UI", 12, "bold"),
            fg_color="transparent",
            hover_color=cfg["hover"],
            text_color=cfg["title_color"],
            command=self._animate_out,
        )
        self._close_btn.grid(row=0, column=3, rowspan=2, sticky="ne", padx=(8, 0))

        # ── Progress bar ──
        progress_color = cfg["progress"]
        self._progress_bg = ctk.CTkFrame(self.frame, height=3, corner_radius=0,
                                          fg_color=("#E5E7EB", "#374151"))
        self._progress_bg.pack(fill="x", side="bottom", padx=0, pady=0)

        self._progress_fill = ctk.CTkFrame(self._progress_bg, height=3, corner_radius=0,
                                            fg_color=progress_color, width=0)
        self._progress_fill.pack(side="left", fill="y")

        # ── Position & animate ──
        self.update_idletasks()

        # Register in queue (newest first → appears at the bottom of the stack)
        ToastNotification._active_toasts.insert(0, self)
        while len(ToastNotification._active_toasts) > ToastNotification._MAX_VISIBLE:
            oldest = ToastNotification._active_toasts.pop()  # oldest sits on top
            try:
                if oldest.winfo_exists() and not oldest._fade_out_started:
                    oldest._animate_out()
            except Exception:
                pass

        self._position_window(initial=True)
        ToastNotification._reflow()  # shift existing toasts up to make room
        self._animate_in()

        # Start progress bar
        self._start_time = time.time()
        self._update_progress()

        # Auto-dismiss after duration
        self.after(self._duration, self._on_auto_dismiss)

        # Keep-on-top watchdog — periodically re-assert topmost + lift so the
        # toast never slips behind the app, browser, or any other window.
        self.after(120, self._keep_on_top)

        # ── Bindings ──
        _bind_widgets = [self, self.frame, self.content, icon_lbl,
                         self._title_label, self._msg_label]
        if details:
            _bind_widgets.append(self._details_label)
        for widget in _bind_widgets:
            try:
                widget.bind("<Button-1>", lambda e: self._animate_out())
            except Exception:
                pass

    # ── Positioning ──────────────────────────────────────────────────────────
    def _parent_bounds(self) -> Tuple[int, int, int, int]:
        """Return (root_x, root_y, width, height) of the reference window.
        Falls back to the whole screen when the parent is minimized/hidden."""
        try:
            if self.parent is not None and self.parent.winfo_exists():
                w = self.parent.winfo_width()
                h = self.parent.winfo_height()
                if w > 100 and h > 100 and self.parent.winfo_viewable():
                    return (self.parent.winfo_rootx(), self.parent.winfo_rooty(), w, h)
        except Exception:
            pass
        return (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())

    def _compute_target(self) -> Tuple[int, int]:
        """Final (x, y) for this toast based on its index in the stack.
        Index 0 (newest) sits at the bottom; older toasts stack upward."""
        px, py, pw, ph = self._parent_bounds()
        my_w = self._WIDTH
        my_h = self.winfo_reqheight()

        my_idx = 0
        for i, t in enumerate(ToastNotification._active_toasts):
            if t is self:
                my_idx = i
                break

        base_x = px + pw - my_w - self._EDGE_MARGIN
        base_y = py + ph - my_h - self._BOTTOM_OFFSET - (my_idx * (my_h + self._STACK_GAP))
        return int(base_x), int(base_y)

    def _position_window(self, initial: bool = False) -> None:
        """Place the toast at its target. When `initial`, start off-screen to
        the right so `_animate_in()` can slide it in.
        (Reflow movement is handled by `_animate_to_target()` instead.)"""
        try:
            tx, ty = self._compute_target()
            self._target_x, self._target_y = tx, ty
            if not initial:
                return
            px, py, pw, ph = self._parent_bounds()
            self._start_x = int(px + pw + 20)  # Off-screen right
            self.geometry(f"{self._WIDTH}x{self.winfo_reqheight()}+{self._start_x}+{ty}")
        except Exception as e:
            logger.debug("ToastNotification._position_window failed: %s", e)

    @classmethod
    def _reflow(cls) -> None:
        """Re-position remaining toasts (smooth slide) after add/remove."""
        for t in list(cls._active_toasts):
            try:
                if t.winfo_exists() and not t._fade_out_started and not t._destroyed:
                    t._animate_to_target()
            except Exception:
                pass

    def _animate_to_target(self, steps: int = 8, step: int = 0,
                           start_y: Optional[int] = None,
                           epoch: Optional[int] = None) -> None:
        """Smoothly move this toast to its computed stack position.
        Uses an epoch counter so a newer reflow invalidates older animation
        loops that may still be running (prevents overlapping y-jitter)."""
        if self._fade_out_started or self._destroyed:
            return
        try:
            if not self.winfo_exists():
                return
            _, ty = self._compute_target()
            self._target_y = ty
            if self._animating_in:
                return  # slide-in will land on the updated target anyway
            if epoch is None:
                # Fresh reflow — bump the epoch so any older loop bows out.
                self._reflow_epoch += 1
                epoch = self._reflow_epoch
                start_y = self.winfo_y()
                if abs(start_y - ty) < 2:
                    return
            elif epoch != self._reflow_epoch:
                return  # A newer reflow superseded this loop.
            t = (step + 1) / steps
            eased = 1 - (1 - t) ** 3  # ease-out cubic
            y = int(start_y + (ty - start_y) * eased)
            self.geometry(f"+{self.winfo_x()}+{y}")
            if step < steps - 1:
                self.after(14, lambda: self._animate_to_target(steps, step + 1, start_y, epoch))
        except Exception:
            pass

    # ── Animations ───────────────────────────────────────────────────────────
    def _animate_in(self, steps: int = 14, step: int = 0) -> None:
        """Slide in from the right with a smooth ease-out + fade-in."""
        if self._destroyed or self._fade_out_started:
            return  # bail if a fade-out was already started (e.g. X clicked mid-slide)
        try:
            if not self.winfo_exists():
                return
            if step >= steps:
                self._animating_in = False
                self.attributes("-alpha", 1.0)
                self.geometry(f"+{self._target_x}+{self._target_y}")
                return
            self._animating_in = True
            t = (step + 1) / steps
            eased = 1 - (1 - t) ** 3  # ease-out cubic
            current_x = int(self._start_x + (self._target_x - self._start_x) * eased)
            self.attributes("-alpha", min(1.0, 0.15 + 0.85 * eased))
            self.geometry(f"+{current_x}+{self._target_y}")
            self.after(16, lambda: self._animate_in(steps, step + 1))
        except Exception:
            pass

    def _animate_out(self, steps: int = 14) -> None:
        """Slide out to the right with an ease-in + fade-out."""
        if self._fade_out_started or self._destroyed:
            return
        self._fade_out_started = True

        # Stop the keep-on-top watchdog & progress bar
        if self._keep_top_after_id:
            try:
                self.after_cancel(self._keep_top_after_id)
            except Exception:
                pass
            self._keep_top_after_id = None

        try:
            start_x = self.winfo_x()
            start_y = self.winfo_y()
        except Exception:
            start_x, start_y = self._target_x, self._target_y

        def _animate(step: int = 0):
            if self._destroyed:
                return
            try:
                if not self.winfo_exists():
                    return
                if step >= steps:
                    self.destroy()
                    return
                t = (step + 1) / steps
                eased = t * t  # ease-in quad
                x = int(start_x + (self._start_x - start_x) * eased)
                self.attributes("-alpha", max(0.0, 1.0 - eased))
                self.geometry(f"+{x}+{start_y}")
                self.after(16, lambda: _animate(step + 1))
            except Exception:
                try:
                    self.destroy()
                except Exception:
                    pass

        _animate()

    # ── Progress bar & watchdog ─────────────────────────────────────────────
    def _update_progress(self) -> None:
        """Smoothly shrink the progress bar to show remaining time."""
        if self._fade_out_started or self._destroyed or not self.winfo_exists():
            return
        try:
            if self._start_time is None:
                return
            elapsed = (time.time() - self._start_time) * 1000
            remaining = max(0.0, 1.0 - (elapsed / self._duration))
            bar_w = self._progress_bg.winfo_width() or self._WIDTH
            self._progress_fill.configure(width=int(remaining * bar_w))
            self._progress_bg.update_idletasks()
            if remaining > 0:
                self._progress_after_id = self.after(50, self._update_progress)
            else:
                self._progress_after_id = None
        except Exception:
            pass

    def _keep_on_top(self) -> None:
        """Watchdog: periodically re-assert topmost + lift so the toast stays
        above the app and any other window on screen."""
        if self._destroyed or self._fade_out_started:
            return
        try:
            if not self.winfo_exists():
                return
            self.attributes("-topmost", True)
            self.lift()
            self._keep_top_after_id = self.after(self._KEEP_TOP_MS, self._keep_on_top)
        except Exception:
            pass

    def _on_auto_dismiss(self) -> None:
        """Called when duration expires — fade out."""
        self._animate_out()

    # ── Cleanup ──────────────────────────────────────────────────────────────
    def destroy(self) -> None:
        """Cancel timers, remove from the queue, and reflow remaining toasts."""
        self._destroyed = True
        if self._progress_after_id:
            try:
                self.after_cancel(self._progress_after_id)
            except Exception:
                pass
            self._progress_after_id = None
        if self._keep_top_after_id:
            try:
                self.after_cancel(self._keep_top_after_id)
            except Exception:
                pass
            self._keep_top_after_id = None
        try:
            if self in ToastNotification._active_toasts:
                ToastNotification._active_toasts.remove(self)
        except Exception:
            pass
        try:
            super().destroy()
        except Exception:
            pass
        ToastNotification._reflow()

# --- 6. ONBOARDING GUIDE (Modern interactive wizard) ---
def _is_chrome_running(timeout: float = 0.4) -> bool:
    """True if a Chrome instance with the app's debug port (9222) is already
    running — i.e. we can connect to it instead of launching a new one."""
    try:
        import socket
        with socket.create_connection(("127.0.0.1", 9222), timeout=timeout):
            return True
    except Exception:
        return False


def _state_portal_host(state: str) -> str:
    """Portal host for the given state key (case-insensitive), falling back to
    the default host. Delegates to config.get_state_portal_host() — same
    lookup get_state_portal_url() uses, so dono kabhi mismatch nahi karte."""
    return config.get_state_portal_host(state) or config.DEFAULT_PORTAL_HOST


class OnboardingGuide(ctk.CTkToplevel):
    """Modern first-run wizard that actually SETS UP the user:

      1. Welcome          — what the app does
      2. Language         — pick language (applies immediately)
      3. Browser & Login  — launch Chrome, login to the portal
      4. Add Panchayats   — scrape Panchayat + Villages right here
      5. Emergency Stop   — what the footer STOP button does
      6. How to Use       — pick a task, fill details, Start Automation
      7. Done             — summary + finish

    ``replay=True`` (from the About tab) shows the tour again WITHOUT
    writing the first-run flag.
    """

    STEPS = 7
    SPINNER_FRAMES = ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷")

    def __init__(self, parent: Any, replay: bool = False, start_step: int = 0) -> None:
        super().__init__(parent)
        self.parent = parent
        self.replay = replay
        # start_step: tour ko kisi specific step se kholo (e.g. panchayat step
        # jab tour complete hai par panchayat abhi add nahi hua).
        self.current_step = max(0, min(int(start_step), self.STEPS - 1))
        self._browser_launched = False
        self._panchayat_added = False
        self._language_note = ""
        self._lang_applied = False
        self._spinner_after = None
        self._login_epoch = 0

        self.title(tr("onboarding.title"))
        w, h = 640, 580
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.grab_set()
        # X-close behaves like Skip — flag is written so the tour never nags again.
        self.protocol("WM_DELETE_WINDOW", self._finish)

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(18, 2))
        icon = self.parent.icon_images.get("onboarding_start") if hasattr(self.parent, 'icon_images') else None
        if icon:
            ctk.CTkLabel(header, text="", image=icon).pack(side="left", padx=(0, 12))
        else:
            ctk.CTkLabel(header, text="🏛️", font=ctk.CTkFont(size=30)).pack(side="left", padx=(0, 12))
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")
        self.header_title = ctk.CTkLabel(title_box, text=tr("onboarding.title"),
                                         font=ctk.CTkFont(size=20, weight="bold"))
        self.header_title.pack(anchor="w")
        self.header_sub = ctk.CTkLabel(title_box, text=tr("onboarding.subtitle"),
                                       font=ctk.CTkFont(size=11),
                                       text_color=("gray50", "gray60"))
        self.header_sub.pack(anchor="w")

        # ── Progress bar + step counter ──
        progress_row = ctk.CTkFrame(self, fg_color="transparent")
        progress_row.grid(row=1, column=0, sticky="ew", padx=26, pady=(4, 2))
        progress_row.grid_columnconfigure(0, weight=1)
        self.progress_bar = ctk.CTkProgressBar(progress_row, height=8)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.step_label = ctk.CTkLabel(progress_row, text="", font=ctk.CTkFont(size=11),
                                       text_color=("gray50", "gray60"), width=70)
        self.step_label.grid(row=0, column=1)

        # ── Content card ──
        self.content_card = ctk.CTkFrame(self, corner_radius=14,
                                         fg_color=("gray95", "gray20"),
                                         border_width=1, border_color=("gray85", "gray30"))
        self.content_card.grid(row=2, column=0, sticky="nsew", padx=26, pady=(4, 6))
        self.content_card.grid_columnconfigure(0, weight=1)
        self.content_card.grid_rowconfigure(0, weight=1)

        # ── Footer buttons ──
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=26, pady=(2, 16))
        footer.grid_columnconfigure(0, weight=1)

        self.back_btn = ctk.CTkButton(footer, text=tr("onboarding.back"), width=90,
                                      fg_color=("gray85", "gray25"),
                                      text_color=("gray20", "gray80"),
                                      hover_color=("gray75", "gray35"),
                                      command=self._go_back)
        self.back_btn.grid(row=0, column=1, padx=(0, 8))

        self.skip_btn = ctk.CTkButton(footer, text=tr("onboarding.skip"), width=100,
                                      fg_color="transparent", text_color=("gray40", "gray60"),
                                      hover_color=("gray90", "gray25"),
                                      command=self._finish)
        self.skip_btn.grid(row=0, column=2, padx=(0, 8))

        self.next_btn = ctk.CTkButton(footer, text=tr("onboarding.next"), width=130,
                                      command=self._go_next)
        self.next_btn.grid(row=0, column=3)

        self._render_step(self.current_step)
        self.after(120, self.focus_force)

    # ── Navigation ───────────────────────────────────────────────────
    def _clear_content(self) -> None:
        for w in self.content_card.winfo_children():
            w.destroy()

    def _go_back(self) -> None:
        if self.current_step > 0:
            self._render_step(self.current_step - 1)

    def _go_next(self) -> None:
        if self.current_step < self.STEPS - 1:
            self._render_step(self.current_step + 1)
        else:
            self._finish()

    def _refresh_labels(self) -> None:
        """Rebuild tr()-driven labels after a language change."""
        try:
            self.title(tr("onboarding.title"))
            self.header_title.configure(text=tr("onboarding.title"))
            self.header_sub.configure(text=tr("onboarding.subtitle"))
            self.back_btn.configure(text=tr("onboarding.back"))
            self.skip_btn.configure(text=tr("onboarding.skip"))
            if self.current_step == self.STEPS - 1:
                self.next_btn.configure(text=tr("onboarding.finish"))
            else:
                self.next_btn.configure(text=tr("onboarding.next"))
            self.step_label.configure(text=tr("onboarding.step",
                                               current=self.current_step + 1,
                                               total=self.STEPS))
        except Exception:
            pass

    def _finish(self) -> None:
        """Mark onboarding complete (unless replay), close, restart if needed."""
        if not self.replay:
            try:
                with open(get_data_path('.first_run_complete'), 'w') as f:
                    f.write(datetime.now().isoformat())
            except Exception as e:
                logger.warning("Could not write first run flag: %s", e)
        self.destroy()
        # Panchayats added mid-tour → restart so every tab's dropdown picks them up.
        if self._panchayat_added and not self.replay:
            try:
                from src.tabs.settings_tab import restart_application
                self.parent.after(500, lambda: restart_application(self.parent))
            except Exception:
                pass

    def _render_step(self, idx: int) -> None:
        self._spinner_stop()  # purane step ka spinner turant band (widgets destroy hone se pehle)
        self._clear_content()
        self.current_step = idx
        self.progress_bar.set((idx + 1) / self.STEPS)
        self.step_label.configure(text=tr("onboarding.step", current=idx + 1, total=self.STEPS))
        self.back_btn.configure(state="normal" if idx > 0 else "disabled")
        if idx == self.STEPS - 1:
            self.next_btn.configure(text=tr("onboarding.finish"))
        else:
            self.next_btn.configure(text=tr("onboarding.next"))

        builders = [self._step_welcome, self._step_language, self._step_browser,
                    self._step_panchayat, self._step_stop, self._step_how, self._step_done]
        builders[idx]()

    # ── Step builders ────────────────────────────────────────────────
    def _card_inner(self) -> ctk.CTkFrame:
        inner = ctk.CTkFrame(self.content_card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        return inner

    def _step_welcome(self) -> None:
        inner = self._card_inner()
        icon = self.parent.icon_images.get("onboarding_start") if hasattr(self.parent, 'icon_images') else None
        if icon:
            ctk.CTkLabel(inner, text="", image=icon).pack(pady=(0, 14))
        else:
            ctk.CTkLabel(inner, text="🎉", font=ctk.CTkFont(size=52)).pack(pady=(0, 14))
        ctk.CTkLabel(inner, text=tr("onboarding.welcome.title"),
                     font=ctk.CTkFont(size=24, weight="bold")).pack()
        ctk.CTkLabel(inner, text=tr("onboarding.welcome.desc"),
                     font=ctk.CTkFont(size=13), text_color=("gray35", "gray70"),
                     wraplength=500, justify="center").pack(pady=(12, 0))
        ctk.CTkLabel(inner, text=tr("onboarding.welcome.hint"),
                     font=ctk.CTkFont(size=11), text_color=("gray45", "gray60"),
                     wraplength=480, justify="center").pack(pady=(16, 0))

    def _step_language(self) -> None:
        inner = self._card_inner()
        ctk.CTkLabel(inner, text="🌐", font=ctk.CTkFont(size=46)).pack(pady=(0, 10))
        ctk.CTkLabel(inner, text=tr("onboarding.lang.title"),
                     font=ctk.CTkFont(size=22, weight="bold")).pack()
        ctk.CTkLabel(inner, text=tr("onboarding.lang.desc"),
                     font=ctk.CTkFont(size=13), text_color=("gray35", "gray70"),
                     wraplength=480, justify="center").pack(pady=(10, 12))

        available = [c for c in get_available_languages() if c in LANGUAGES]
        current = get_language()
        lang_var = ctk.StringVar(value=LANGUAGES.get(current, current))
        menu = ctk.CTkOptionMenu(inner, variable=lang_var,
                                 values=[LANGUAGES.get(c, c) for c in available],
                                 width=280, font=ctk.CTkFont(size=13))
        menu.pack()

        try:
            lic = getattr(self.parent, 'license_info', None) or {}
            state = (lic.get('user_state') or '').strip().upper()
            suggested = suggest_language_for_state(state)
            if suggested in LANGUAGES:
                ctk.CTkLabel(inner, text=tr("onboarding.lang.suggested", lang=LANGUAGES[suggested]),
                             font=ctk.CTkFont(size=11),
                             text_color=("#0284C7", "#38BDF8")).pack(pady=(8, 0))
        except Exception:
            pass

        # Revisit (navigate away/back) par bhi applied message dikhe — status
        # empty na rahe jab language pehle apply ho chuki ho.
        self._lang_status = ctk.CTkLabel(
            inner,
            text=self._language_note if getattr(self, '_lang_applied', False) else "",
            font=ctk.CTkFont(size=12),
            text_color=("#16A34A", "#4ADE80"),
            wraplength=440, justify="center")
        self._lang_status.pack(pady=(12, 0))

        def _apply():
            display = lang_var.get()
            code = next((c for c, n in LANGUAGES.items() if n == display), None)
            if not code:
                return
            set_language(code)
            self._language_note = tr("onboarding.lang.applied")
            self._lang_applied = True
            self._refresh_labels()
            # Rebuild the current step so its own title/desc/dropdown/button
            # also switch to the newly selected language.
            self._render_step(self.current_step)
            try:
                self._lang_status.configure(text=tr("onboarding.lang.applied"),
                                            text_color=("#16A34A", "#4ADE80"))
            except Exception:
                pass
            try:  # live-refresh the most visible app surfaces
                if hasattr(self.parent, '_create_nav_buttons'):
                    self.parent._create_nav_buttons(self.parent.sidebar_header,
                                                    self.parent.nav_scroll_frame)
            except Exception:
                pass
            try:
                if hasattr(self.parent, 'announcement_label') and self.parent.announcement_label:
                    self.parent.announcement_label.configure(text=tr("app.welcome_loading"))
            except Exception:
                pass
            try:
                if hasattr(self.parent, 'status_label') and self.parent.status_label:
                    self.parent.status_label.configure(text=tr("app.status_ready"))
            except Exception:
                pass

        apply_btn = ctk.CTkButton(inner, text=tr("onboarding.lang.apply"), width=200, height=38,
                                  fg_color=("#0284C7", "#0284C7"), text_color="white",
                                  hover_color=("#0369A1", "#0369A1"),
                                  font=ctk.CTkFont(size=13, weight="bold"),
                                  command=_apply)

        def _sync_apply_state(*_args):
            """Dropdown me nayi language chunne par apply button wapas enable —
            kyunki nayi selection abhi apply nahi hui hai."""
            try:
                if getattr(self, '_lang_applied', False):
                    self._lang_applied = False
                    apply_btn.configure(state="normal",
                                        text=tr("onboarding.lang.apply"),
                                        fg_color=("#0284C7", "#0284C7"),
                                        hover_color=("#0369A1", "#0369A1"))
                    self._lang_status.configure(text="")
            except Exception:
                pass

        lang_var.trace_add("write", _sync_apply_state)

        apply_btn.pack(pady=(16, 0))
        if getattr(self, '_lang_applied', False):
            # Language apply ho chuki hai — button locked green, clear feedback
            apply_btn.configure(state="disabled",
                                text=tr("onboarding.lang.applied_btn"),
                                fg_color=("#16A34A", "#16A34A"),
                                hover_color=("#15803D", "#15803D"))

    def _step_browser(self) -> None:
        inner = self._card_inner()
        icon = self.parent.icon_images.get("onboarding_launch") if hasattr(self.parent, 'icon_images') else None
        if icon:
            ctk.CTkLabel(inner, text="", image=icon).pack(pady=(0, 8))
        else:
            ctk.CTkLabel(inner, text="🚀", font=ctk.CTkFont(size=44)).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=tr("onboarding.browser.title"),
                     font=ctk.CTkFont(size=22, weight="bold")).pack()
        ctk.CTkLabel(inner, text=tr("onboarding.browser.desc"),
                     font=ctk.CTkFont(size=13), text_color=("gray35", "gray70"),
                     wraplength=490, justify="center").pack(pady=(10, 14))

        self._browser_status = ctk.CTkLabel(inner, text="", font=ctk.CTkFont(size=12),
                                            text_color=("#16A34A", "#4ADE80"))
        self._browser_status.pack(pady=(0, 10))

        def _update_status(running: bool):
            try:
                if running:
                    self._browser_launched = True
                    self._browser_status.configure(text=tr("onboarding.browser.connected"),
                                                   text_color=("#16A34A", "#4ADE80"))
                    if hasattr(self, '_browser_btn'):
                        self._browser_btn.configure(text=tr("onboarding.browser.connect_btn"))
                else:
                    self._browser_status.configure(text=tr("onboarding.browser.not_running"),
                                                   text_color=("gray50", "gray60"))
            except Exception:
                pass

        def _check_running():
            # Background thread — port check is fast but must never freeze UI.
            try:
                running = _is_chrome_running()
                self.after(0, lambda: _update_status(running))
            except Exception:
                pass

        def _connect_existing():
            """Already-running Chrome se REAL driver session establish karo
            (sirf port-check nahi) — get_driver() khud detect + connect karta
            hai. Fail hone par clear error dikhao."""
            try:
                driver = self.parent.get_driver()
                if driver is not None:
                    _update_status(True)
                else:
                    self._browser_status.configure(
                        text=tr("onboarding.browser.connect_failed"),
                        text_color=("#DC2626", "#F87171"))
            except Exception as e:
                self._browser_status.configure(text=f"❌ {e}",
                                               text_color=("#DC2626", "#F87171"))

        def _launch():
            # Pehle se Chrome chal raha hai → naya launch nahi, bas connect.
            if _is_chrome_running():
                _connect_existing()
                return
            try:
                self.parent.launch_chrome_detached()
                self._browser_launched = True
                self._browser_status.configure(text=tr("onboarding.browser.launched"),
                                               text_color=("#16A34A", "#4ADE80"))
                if hasattr(self, '_browser_btn'):
                    self._browser_btn.configure(text=tr("onboarding.browser.connect_btn"))
            except Exception as e:
                self._browser_status.configure(text=f"❌ {e}", text_color=("#DC2626", "#F87171"))

        self._browser_btn = ctk.CTkButton(inner, text=tr("onboarding.browser.launch_btn"),
                                          width=240, height=40,
                                          fg_color=("#DC2626", "#DC2626"), text_color="white",
                                          hover_color=("#B91C1C", "#B91C1C"),
                                          font=ctk.CTkFont(size=14, weight="bold"),
                                          command=_launch)
        self._browser_btn.pack(pady=(6, 10))

        # State-aware login hint — saved state ke hisaab se host dikhao
        # (Rajasthan → vbgramgde3.dord.gov.in).
        _host_state = ""
        try:
            _sugg = self.parent.history_manager.get_suggestions("location_state") or []
            if _sugg:
                _host_state = str(_sugg[0]).strip()
        except Exception:
            pass
        _host = _state_portal_host(_host_state)
        _login_hint = tr("onboarding.browser.login_hint").replace("vbgramgde2.dord.gov.in", _host)

        login_box = ctk.CTkFrame(inner, corner_radius=10, fg_color=("gray90", "gray25"))
        login_box.pack(fill="x", padx=30, pady=(4, 4))
        ctk.CTkLabel(login_box, text=_login_hint,
                     font=ctk.CTkFont(size=12), text_color=("gray40", "gray75"),
                     wraplength=460, justify="center").pack(padx=14, pady=10)

        # Already-running Chrome ko turant detect karo aur user ko dikhao.
        threading.Thread(target=_check_running, daemon=True).start()

    # ── Spinner (processing indicator) ──────────────────────────────────
    def _spinner_start(self, step: int = 0) -> None:
        """Rotating braille spinner — processing ke time gol-gol ghumta hua
        indicator dikhata hai (same style app ke loading icon ki tarah)."""
        try:
            if not self.winfo_exists():
                return
            spin = getattr(self, "_panch_spinner", None)
            if spin is None or not spin.winfo_exists():
                return
            spin.configure(text=self.SPINNER_FRAMES[step % len(self.SPINNER_FRAMES)])
            self._spinner_after = self.after(120, lambda: self._spinner_start(step + 1))
        except Exception:
            pass

    def _spinner_stop(self) -> None:
        """Spinner band karo aur label clear karo (agar step destroy ho gaya ho
        to safely ignore)."""
        try:
            if getattr(self, "_spinner_after", None):
                self.after_cancel(self._spinner_after)
                self._spinner_after = None
        except Exception:
            pass
        spin = getattr(self, "_panch_spinner", None)
        if spin is not None:
            try:
                if spin.winfo_exists():
                    spin.configure(text="")
            except Exception:
                pass

    # ── Background login check (Add Panchayat step) ────────────────────
    def _check_login_background(self) -> None:
        """Step khulte hi background me login status check — user ko bina
        kisi button dabaye pata chale ki browser me login hai ya nahi.

        Logged-in (GP) → demand automation khud panchayat/villages add kar
        dega, to bas 'Next' dabana hai. Logged-out → clear 'login karo'
        message dikhta hai.
        """
        try:
            self._panch_btn.configure(state="disabled")
        except Exception:
            pass
        try:
            self._panch_status.configure(text=tr("onboarding.panch.login_checking"),
                                         text_color=("gray50", "gray60"))
        except Exception:
            pass
        self._spinner_start()
        self._login_epoch += 1
        threading.Thread(target=self._check_login_thread,
                         args=(self._login_epoch,), daemon=True).start()

    def _check_login_thread(self, epoch: int) -> None:
        """Background thread: browser connect + demand page par login check.

        UI kabhi touch nahi hota — result main thread par after(0) se
        update hota hai. Login detection shared helper
        (src.portal_login.detect_portal_login) use karta hai — wahi
        Session Expired trick. Epoch guard: agar user step se bahar jaa kar
        wapas aaya (nayi check start hui), purane thread ka result ignore
        ho jata hai.
        """
        from src.portal_login import detect_portal_login
        from src.tabs.settings_tab import _state_aware_demand_url

        status, level = None, None
        try:
            driver = self.parent.get_driver()
            if not driver:
                status = "no_browser"
            else:
                try:
                    cur = (driver.current_url or "").lower()
                    body = (driver.page_source or "").lower()
                except Exception:
                    cur, body = "", ""
                if "session expired" in body:
                    # Portal ka session expiry trick — demand page logged-out
                    # par sirf 'Session Expired!' dikhata hai. Bina navigate
                    # kiye hi pata chal gaya.
                    status = "not_logged_in"
                elif "login" in cur:
                    # User abhi login form par hai — navigate NAHI karte
                    # (login input kharab na ho jaye), bas guide kar dete hain.
                    status = "on_login_page"
                else:
                    demand_url = _state_aware_demand_url(self.parent)
                    detected, level = detect_portal_login(driver, demand_url=demand_url)
                    status = "logged_in" if detected in ("po", "gp") else detected
        except Exception:
            status = "error"
        try:
            # Guide destroy ho chuka ho (user ne onboarding band kiya) to
            # after() TclError de sakta hai — safely ignore.
            self.after(0, lambda: self._apply_login_check(status, level, epoch))
        except Exception:
            pass

    def _apply_login_check(self, status: Optional[str], level: Optional[str],
                           epoch: int) -> None:
        """Login check result UI par dikhata hai (main thread par).

        Epoch guard: purane check ka result naye step ke status ko overwrite
        na kare (user step chhod kar wapas aaya ho to nayi check chalti hai).
        """
        if epoch != self._login_epoch:
            return  # stale result — nayi check chalu ho chuki hai
        self._spinner_stop()
        try:
            self._panch_btn.configure(state="normal")
        except Exception:
            pass
        try:
            if status == "logged_in" and level in ("GP", "PO"):
                # Level persist + header dot update (automation detect jaisa hi)
                try:
                    self.parent.set_user_level(level)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if status == "logged_in":
                if level == "GP":
                    self._panch_status.configure(
                        text=tr("onboarding.panch.login_ok_gp"),
                        text_color=("#16A34A", "#4ADE80"))
                else:
                    self._panch_status.configure(
                        text=tr("onboarding.panch.login_ok_po"),
                        text_color=("#16A34A", "#4ADE80"))
            elif status == "on_login_page":
                self._panch_status.configure(
                    text=tr("onboarding.panch.on_login_page"),
                    text_color=("#D97706", "#FBBF24"))
            elif status == "not_logged_in":
                self._panch_status.configure(
                    text=tr("onboarding.panch.login_needed"),
                    text_color=("#DC2626", "#F87171"))
            elif status == "no_browser":
                self._panch_status.configure(
                    text=tr("onboarding.panch.no_browser"),
                    text_color=("#D97706", "#FBBF24"))
            else:
                self._panch_status.configure(
                    text=tr("onboarding.panch.login_check_failed"),
                    text_color=("gray50", "gray60"))
        except Exception:
            pass
        # Browser navigate hua → focus wapas app/guide par (user browser me
        # na atak jaye).
        try:
            self.parent.bring_to_front()
        except Exception:
            pass
        try:
            self.lift()
            self.after(100, self.focus_force)
        except Exception:
            pass

    def _step_panchayat(self) -> None:
        inner = self._card_inner()
        icon = self.parent.icon_images.get("onboarding_select") if hasattr(self.parent, 'icon_images') else None
        if icon:
            ctk.CTkLabel(inner, text="", image=icon).pack(pady=(0, 8))
        else:
            ctk.CTkLabel(inner, text="🏘️", font=ctk.CTkFont(size=44)).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=tr("onboarding.panch.title"),
                     font=ctk.CTkFont(size=22, weight="bold")).pack()
        ctk.CTkLabel(inner, text=tr("onboarding.panch.desc"),
                     font=ctk.CTkFont(size=13), text_color=("gray35", "gray70"),
                     wraplength=490, justify="center").pack(pady=(10, 14))

        # Status row: rotating spinner + message
        status_row = ctk.CTkFrame(inner, fg_color="transparent")
        status_row.pack(pady=(0, 10))
        self._panch_spinner = ctk.CTkLabel(status_row, text="",
                                           font=ctk.CTkFont(size=14),
                                           text_color=("#0284C7", "#38BDF8"))
        self._panch_spinner.pack(side="left", padx=(0, 6))
        self._panch_status = ctk.CTkLabel(status_row, text="",
                                          font=ctk.CTkFont(size=12),
                                          text_color=("gray50", "gray60"),
                                          wraplength=460, justify="left")
        self._panch_status.pack(side="left")

        def _start():
            from src.tabs.settings_tab import run_panchayat_scrape
            self._panch_btn.configure(state="disabled", text=tr("onboarding.panch.scraping"))
            self._panch_status.configure(text=tr("onboarding.panch.connecting"),
                                         text_color=("gray50", "gray60"))
            self._spinner_start()

            def _status(msg):
                try:
                    self._panch_status.configure(text=msg, text_color=("gray50", "gray60"))
                except Exception:
                    pass

            def _done(saved_panch, saved_vill, all_panch_villages, gp_mode):
                self._spinner_stop()
                try:
                    self._panch_btn.configure(state="normal", text=tr("onboarding.panch.btn"))
                    if saved_panch:
                        self._panchayat_added = True
                        done_txt = tr("onboarding.panch.done", panch=saved_panch, vill=saved_vill)
                        if gp_mode:
                            done_txt += "\n" + tr("onboarding.panch.gp_note")
                        self._panch_status.configure(
                            text=done_txt,
                            text_color=("#16A34A", "#4ADE80"))
                    else:
                        self._panch_status.configure(
                            text=tr("onboarding.panch.none"),
                            text_color=("#D97706", "#FBBF24"))
                    # Chrome par scrape khatam → focus wapas guide/app par.
                    self.lift()
                    # settings_tab ka finally block app.bring_to_front() bhi
                    # queue karta hai (after(0)) — wo lift/focus_force ke baad
                    # chalta hai, isliye guide apna focus yahan thodi der baad
                    # wapas assert karta hai taaki guide hi focused rahe.
                    self.after(100, self.focus_force)
                except Exception:
                    pass

            def _failed(msg):
                self._spinner_stop()
                try:
                    self._panch_btn.configure(state="normal", text=tr("onboarding.panch.btn"))
                    self._panch_status.configure(text=f"❌ {msg}",
                                                 text_color=("#DC2626", "#F87171"))
                except Exception:
                    pass

            run_panchayat_scrape(self.parent, on_status=_status,
                                 on_success=_done, on_failed=_failed)

        self._panch_btn = ctk.CTkButton(inner, text=tr("onboarding.panch.btn"), width=260, height=40,
                                        fg_color=("#F97316", "#EA580C"), text_color="white",
                                        hover_color=("#EA580C", "#C2410C"),
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        command=_start)
        self._panch_btn.pack(pady=(6, 8))
        ctk.CTkLabel(inner, text=tr("onboarding.panch.skip_hint"),
                     font=ctk.CTkFont(size=11), text_color=("gray45", "gray60"),
                     wraplength=440, justify="center").pack()

        # ── Background login check — step khulte hi chalta hai. GP login ho to
        # demand automation panchayat/villages khud add kar dega (bas 'Next'
        # dabana hai); logged-out ho to clear 'login karo' message dikhta hai. ──
        self._check_login_background()

    def _step_stop(self) -> None:
        inner = self._card_inner()
        ctk.CTkLabel(inner, text="🛑", font=ctk.CTkFont(size=46)).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=tr("onboarding.stop.title"),
                     font=ctk.CTkFont(size=22, weight="bold")).pack()
        ctk.CTkLabel(inner, text=tr("onboarding.stop.desc"),
                     font=ctk.CTkFont(size=13), text_color=("gray35", "gray70"),
                     wraplength=500, justify="center").pack(pady=(10, 16))

        # Visual mock of the footer STOP button
        mock = ctk.CTkFrame(inner, corner_radius=10, fg_color=("gray90", "gray25"),
                            border_width=1, border_color=("gray80", "gray40"))
        mock.pack(padx=40, pady=(0, 12))
        mock_row = ctk.CTkFrame(mock, fg_color="transparent")
        mock_row.pack(padx=16, pady=10)
        red_dot = ctk.CTkFrame(mock_row, width=12, height=12, corner_radius=6,
                               fg_color=("#DC2626", "#EF4444"))
        red_dot.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(mock_row, text=tr("app.stop_all"), font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#DC2626", "#EF4444")).pack(side="left")
        ctk.CTkLabel(mock, text=tr("onboarding.stop.caption"),
                     font=ctk.CTkFont(size=11), text_color=("gray45", "gray65"),
                     wraplength=420, justify="center").pack(padx=14, pady=(0, 10))

        for line in [tr("onboarding.stop.when1"), tr("onboarding.stop.when2"),
                     tr("onboarding.stop.when3")]:
            ctk.CTkLabel(inner, text=line, font=ctk.CTkFont(size=12),
                         text_color=("gray40", "gray75"),
                         wraplength=470, justify="left").pack(pady=2)

    def _step_how(self) -> None:
        inner = self._card_inner()
        ctk.CTkLabel(inner, text="🧭", font=ctk.CTkFont(size=44)).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=tr("onboarding.how.title"),
                     font=ctk.CTkFont(size=22, weight="bold")).pack()
        ctk.CTkLabel(inner, text=tr("onboarding.how.desc"),
                     font=ctk.CTkFont(size=13), text_color=("gray35", "gray70"),
                     wraplength=500, justify="center").pack(pady=(10, 14))

        steps = [tr("onboarding.how.step1"), tr("onboarding.how.step2"),
                 tr("onboarding.how.step3")]
        for i, s in enumerate(steps, start=1):
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", padx=36, pady=4)
            ctk.CTkLabel(row, text=f"{i}", width=26, height=26, corner_radius=13,
                         fg_color=("#0284C7", "#0EA5E9"), text_color="white",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text=s, font=ctk.CTkFont(size=12),
                         text_color=("gray30", "gray75"), justify="left",
                         wraplength=420).pack(side="left", padx=(10, 0))

    def _step_done(self) -> None:
        inner = self._card_inner()
        icon = self.parent.icon_images.get("onboarding_start") if hasattr(self.parent, 'icon_images') else None
        if icon:
            ctk.CTkLabel(inner, text="", image=icon).pack(pady=(0, 10))
        else:
            ctk.CTkLabel(inner, text="🎉", font=ctk.CTkFont(size=48)).pack(pady=(0, 10))
        ctk.CTkLabel(inner, text=tr("onboarding.done.title"),
                     font=ctk.CTkFont(size=24, weight="bold")).pack()
        ctk.CTkLabel(inner, text=tr("onboarding.done.desc"),
                     font=ctk.CTkFont(size=13), text_color=("gray35", "gray70"),
                     wraplength=500, justify="center").pack(pady=(12, 4))

        summary = [tr("onboarding.done.lang" ), tr("onboarding.done.browser")]
        if self._panchayat_added:
            summary.append(tr("onboarding.done.panch"))
        for s in summary:
            ctk.CTkLabel(inner, text=f"✅  {s}", font=ctk.CTkFont(size=12),
                         text_color=("#166534", "#4ADE80")).pack(pady=2)

        if self._panchayat_added:
            ctk.CTkLabel(inner, text=tr("onboarding.done.restart"),
                         font=ctk.CTkFont(size=11), text_color=("gray45", "gray60"),
                         wraplength=460, justify="center").pack(pady=(12, 0))

# --- 7. COMING SOON TAB ---
class ComingSoonTab(ctk.CTkFrame):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.pack(expand=True, fill="both")
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        try:
            icon_image = app_instance.icon_images.get("onboarding_launch") 
            if icon_image:
                 ctk.CTkLabel(container, text="", image=icon_image).pack(pady=(0, 20))
        except Exception as e:
            logger.debug("ComingSoonTab failed to load icon: %s", e)

        ctk.CTkLabel(container, text="Coming Soon", font=ctk.CTkFont(size=28, weight="bold")).pack()
        ctk.CTkLabel(container, text="Sarkar Aapke Dwar Automation is under development.", 
                     font=ctk.CTkFont(size=14), text_color="gray60").pack(pady=(10, 0))


# --- 8. PERFORMANCE MONITOR (Sidebar Bottom) ---
class PerformanceMonitor(ctk.CTkFrame):
    """
    Lightweight system resource monitor for the sidebar footer.
    Shows RAM, CPU usage and active thread count.
    Updates every 5 seconds via a single persistent worker thread
    (queue-based) instead of spawning a new thread each cycle.
    """
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self.app = app_instance
        self._running = True

        # ---- Separator ----
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=("gray85", "gray35")).pack(fill="x", padx=10, pady=(4, 6))

        # ---- Title ----
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x", padx=12, pady=(0, 4))
        thunder_icon = self.app.icon_images.get("performance_thunder")
        ctk.CTkLabel(
            title_row,
            text=" Performance",
            image=thunder_icon,
            compound="left",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=(config.COLORS["dark_goldenrod"], config.COLORS["gold"]),  # DarkGoldenrod light / Gold dark
        ).pack(anchor="center")

        # ---- Metric rows ----
        row_height = 18
        font_style = ctk.CTkFont(size=12, weight="bold")

        self.ram_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.ram_frame.pack(fill="x", padx=12, pady=0)
        ctk.CTkLabel(self.ram_frame, text="RAM", font=ctk.CTkFont(size=10),
                     text_color=("gray50", "gray60")).pack(side="left")
        self.ram_label = ctk.CTkLabel(self.ram_frame, text="—", font=font_style,
                                      text_color=config.COLORS["badge_success"])
        self.ram_label.pack(side="right")

        self.cpu_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cpu_frame.pack(fill="x", padx=12, pady=0)
        ctk.CTkLabel(self.cpu_frame, text="CPU", font=ctk.CTkFont(size=10),
                     text_color=("gray50", "gray60")).pack(side="left")
        self.cpu_label = ctk.CTkLabel(self.cpu_frame, text="—", font=font_style,
                                      text_color=config.COLORS["badge_info"])
        self.cpu_label.pack(side="right")

        self.thread_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.thread_frame.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(self.thread_frame, text="Threads", font=ctk.CTkFont(size=10),
                     text_color=("gray50", "gray60")).pack(side="left")
        self.thread_label = ctk.CTkLabel(self.thread_frame, text="—", font=font_style,
                                         text_color=config.COLORS["badge_warning"])
        self.thread_label.pack(side="right")

        # --- Persistent Background Worker ---
        # Instead of spawning a new thread every 5 seconds, use a single
        # daemon thread with a queue. This eliminates thread creation overhead
        # and keeps a predictable thread count.
        self._update_queue = queue.Queue(maxsize=1)  # At most 1 pending update
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="PerfMon-Worker"
        )
        self._worker_thread.start()

        # Create AfterTracker for auto-cleanup on destroy
        self._tracker = AfterTracker(self)
        
        # ---- Start periodic update (deferred) ----
        self._cached_ram = None
        self._cached_cpu = None
        # Defer the first _schedule_update() call to avoid blocking initial UI rendering
        # with subprocess calls (wmic/powershell/ps). The labels show '—' until
        # the 5-second mark, which is fine for a sidebar footer widget.
        self._tracker.after(5000, self._schedule_update)

    def _worker_loop(self) -> None:
        """Persistent worker thread. Waits for update requests via queue.
        This replaces the old pattern of spawning a new thread every 5 seconds."""
        while self._running:
            try:
                # Wait for update request (1s timeout allows checking _running)
                self._update_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            if not self._running:
                break
            
            # --- Run I/O-bound subprocess calls ---
            ram, cpu = self._get_process_info()
            thread_count = threading.active_count()
            
            # --- Report back to main thread ---
            if self._running:
                self.after(0, lambda r=ram, c=cpu, t=thread_count: 
                           self._apply_update(r, c, t))

    def _get_process_info(self) -> Tuple[Optional[float], Optional[float]]:
        """Get RAM (RSS in MB) and CPU %.
        Uses subprocess calls — MUST be called from a background thread
        because wmic/powershell/ps can block for 50-300ms on slow systems.
        Returns (ram_mb, cpu_pct).
        """
        pid = os.getpid()
        ram_mb = None
        cpu_pct = None

        try:
            system = platform.system()
            if system == "Windows":
                # --- RAM via wmic (WorkingSetSize in bytes, simple number output) ---
                try:
                    out = subprocess.check_output(
                        ["wmic", "process", "where", f"ProcessId={pid}", "get", "WorkingSetSize"],
                        timeout=2, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    ).decode("utf-8", errors="replace")
                    for line in out.splitlines():
                        line = line.strip()
                        if line and line.isdigit():
                            ram_mb = round(int(line) / (1024 * 1024), 1)
                            break
                except Exception:
                    # Fallback: PowerShell (works on all Windows versions)
                    try:
                        out = subprocess.check_output(
                            ["powershell", "-noprofile", "-command",
                             f"(Get-Process -Id {pid}).WorkingSet64 / 1MB"],
                            timeout=3, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        ).decode("utf-8", errors="replace").strip()
                        if out and out.replace('.', '', 1).replace(',', '', 1).isdigit():
                            ram_mb = round(float(out), 1)
                    except Exception:
                        pass

                # --- CPU via wmic (total system CPU percentage) ---
                # Note: wmic is deprecated on Win 11 22H2+ and removed on 24H2+
                # We try wmic first, then fall back to PowerShell
                try:
                    out = subprocess.check_output(
                        ["wmic", "cpu", "get", "loadpercentage"],
                        timeout=2, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    ).decode("utf-8", errors="replace")
                    for line in out.splitlines():
                        line = line.strip()
                        if line and line.replace('.', '', 1).isdigit():
                            cpu_pct = float(line)
                            break
                except Exception:
                    # Fallback: PowerShell (works on all Windows versions including 24H2+)
                    try:
                        out = subprocess.check_output(
                            ["powershell", "-noprofile", "-command",
                             "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"],
                            timeout=3, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        ).decode("utf-8", errors="replace").strip()
                        if out and out.replace('.', '', 1).isdigit():
                            cpu_pct = float(out)
                    except Exception:
                        pass
            else:
                # macOS / Linux — single ps call for both RSS and CPU
                try:
                    out = subprocess.check_output(
                        ["ps", "-o", "rss=,%cpu=", "-p", str(pid)],
                        timeout=0.5, stderr=subprocess.DEVNULL
                    ).decode("utf-8", errors="replace").strip()
                    if out:
                        parts = out.split()
                        if len(parts) >= 1:
                            ram_mb = round(int(parts[0]) / 1024, 1)
                        if len(parts) >= 2:
                            cpu_pct = float(parts[1])
                except Exception:
                    pass
        except Exception:
            pass

        return ram_mb, cpu_pct

    def _schedule_update(self) -> None:
        """Called every 5 seconds from main thread via after().
        Sends an update request to the persistent worker thread via queue.
        If worker is still busy with previous update, the cycle is skipped."""
        if not self._running:
            return
        try:
            if not self.winfo_exists():
                self._running = False
                return
        except Exception:
            self._running = False
            return

        # Skip update when paused (during window resize) to avoid
        # subprocess overhead competing with the window manager
        if getattr(self, '_paused', False):
            try:
                self._tracker.after(5000, self._schedule_update)
            except Exception:
                self._running = False
            return

        # Send update request to persistent worker (non-blocking)
        # If queue is full, worker is still busy — skip this cycle gracefully
        try:
            self._update_queue.put_nowait(True)
        except queue.Full:
            pass  # Worker busy, will pick up next 5s tick

        try:
            self._tracker.after(5000, self._schedule_update)
        except Exception:
            self._running = False

    def _apply_update(self, ram: Optional[float], cpu: Optional[float], threads: int) -> None:
        """Safely updates label widgets on the main thread."""
        if not self._running:
            return
        try:
            if not self.winfo_exists():
                self._running = False
                return
        except Exception:
            self._running = False
            return

        # Only update when value actually changes (rounded to avoid
        # tiny fluctuations like 245.1→245.2 causing unnecessary re-renders)
        if ram is not None and round(ram, 0) != round(self._cached_ram or 0, 0):
            self.ram_label.configure(text=f"{ram:.0f} MB")
            self._cached_ram = ram
        if cpu is not None and round(cpu, 1) != round(self._cached_cpu or 0, 1):
            self.cpu_label.configure(text=f"{cpu:.1f}%")
            self._cached_cpu = cpu
        if threads is not None:
            self.thread_label.configure(text=str(threads))

    def pause(self):
        """Pause periodic updates during window resize to avoid subprocess overhead."""
        self._paused = True

    def resume(self):
        """Resume periodic updates after window resize ends."""
        self._paused = False

    def stop(self):
        """Stop the monitor and signal worker thread to exit."""
        self._running = False
        # Wake up worker thread so it immediately checks _running and exits
        try:
            self._update_queue.put_nowait(None)
        except queue.Full:
            pass