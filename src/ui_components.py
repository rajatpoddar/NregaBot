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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from PIL import Image
from src import config
from src.utils import resource_path, get_logger

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

# --- 2. ONBOARDING STEP (Guide UI) ---
class OnboardingStep(ctk.CTkFrame):
    def __init__(self, parent: Any, title: str, description: str, icon: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.pack(expand=True, fill="both", padx=20, pady=(10, 0))

        if icon:
            icon_label = ctk.CTkLabel(self, image=icon, text="")
            icon_label.pack(pady=(10, 15))

        title_label = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(0, 10))

        desc_label = ctk.CTkLabel(self, text=description, wraplength=380, justify="center")
        desc_label.pack(pady=(0, 20))

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
#   - Slide-in animation from right edge
#   - Auto-dismiss with visible progress bar
#   - Title + message + details support
#   - Close button (click to dismiss instantly)
#   - Click-to-dismiss anywhere
#   - Color-coded by type (success/error/info/warning)
#   - Duration display

class ToastNotification(ctk.CTkToplevel):
    """Professional toast notification with slide-in, progress bar, and close button."""

    _active_toasts: List['ToastNotification'] = []  # Class-level queue
    _MAX_VISIBLE = 3  # Max toasts shown simultaneously

    def __init__(self, parent: Any, message: str, kind: str = "success",
                 duration: int = 4000, title: str = "", details: str = "") -> None:
        super().__init__(parent)
        self.parent = parent
        self._duration = duration
        self._start_time: Optional[float] = None
        self._progress_after_id: Optional[str] = None
        self._fade_out_started = False

        # ── Theme-aware colors ──
        mode = ctk.get_appearance_mode()
        is_dark = mode == "Dark"

        self._configs = {
            "success": {
                "icon": "✅", "bg": ("#065F46", "#065F46"),
                "border": ("#34D399", "#34D399"),
                "progress": ("#34D399", "#6EE7B7"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#D1FAE5", "#D1FAE5"),
            },
            "error": {
                "icon": "❌", "bg": ("#7F1D1D", "#7F1D1D"),
                "border": ("#F87171", "#FCA5A5"),
                "progress": ("#F87171", "#FCA5A5"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#FEE2E2", "#FEE2E2"),
            },
            "info": {
                "icon": "ℹ️", "bg": ("#1E3A5F", "#1E3A5F"),
                "border": ("#60A5FA", "#93C5FD"),
                "progress": ("#60A5FA", "#93C5FD"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#DBEAFE", "#DBEAFE"),
            },
            "warning": {
                "icon": "⚠️", "bg": ("#78350F", "#78350F"),
                "border": ("#FBBF24", "#FCD34D"),
                "progress": ("#FBBF24", "#FCD34D"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#FEF3C7", "#FEF3C7"),
            },
            "automation": {
                "icon": "🤖", "bg": ("#312E81", "#312E81"),
                "border": ("#818CF8", "#A5B4FC"),
                "progress": ("#818CF8", "#A5B4FC"),
                "title_color": ("#FFFFFF", "#FFFFFF"),
                "msg_color": ("#E0E7FF", "#E0E7FF"),
            },
        }

        cfg = self._configs.get(kind, self._configs["info"])

        # ── Window setup ──
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=cfg["bg"])

        # ── Main frame ──
        self.frame = ctk.CTkFrame(self, fg_color=cfg["bg"], corner_radius=10,
                                   border_width=1, border_color=cfg["border"])
        self.frame.pack(fill="both", expand=True)

        # ── Content area ──
        self.content = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.content.pack(fill="x", padx=16, pady=(12, 4))
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
                                        wraplength=320, justify="left",
                                        anchor="w")
        self._msg_label.grid(row=1, column=1, sticky="ew")

        # Details (optional, smaller text below)
        if details:
            self._details_label = ctk.CTkLabel(self.content, text=details,
                                               font=("Segoe UI", 10),
                                               text_color=cfg["msg_color"],
                                               wraplength=320, justify="left",
                                               anchor="w")
            self._details_label.grid(row=2, column=1, sticky="ew", pady=(2, 0))

        # Close button (X)
        self._close_btn = ctk.CTkButton(
            self.content, text="✕", width=24, height=24, corner_radius=12,
            font=("Segoe UI", 12, "bold"),
            fg_color="transparent",
            hover_color=("#E5E7EB", "#374151"),
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

        # Register in queue (dismiss oldest if > MAX_VISIBLE)
        ToastNotification._active_toasts.append(self)
        while len(ToastNotification._active_toasts) > ToastNotification._MAX_VISIBLE:
            oldest = ToastNotification._active_toasts.pop(0)
            try:
                if oldest.winfo_exists():
                    oldest.destroy()
            except Exception:
                pass

        self._position_window()
        self._animate_in()

        # Start progress bar
        self._start_time = time.time()
        self._update_progress()

        # Auto-dismiss after duration
        self.after(duration, self._on_auto_dismiss)

        # ── Bindings ──
        for widget in [self, self.frame, self.content, icon_lbl, self._title_label, self._msg_label]:
            try:
                widget.bind("<Button-1>", lambda e: self._animate_out())
            except Exception:
                pass

    def _position_window(self) -> None:
        """Position at bottom-right of parent window, stacking if multiple toasts visible."""
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()

            my_w = max(self.winfo_reqwidth(), 380)
            my_h = self.winfo_reqheight()

            # Find position among active toasts
            my_idx = 0
            for i, t in enumerate(ToastNotification._active_toasts):
                if t is self:
                    my_idx = i
                    break

            # Stack from bottom-right: each toast goes up by (my_h + 10) pixels
            base_x = parent_x + parent_w - my_w - 20
            base_y = parent_y + parent_h - my_h - 60 - (my_idx * (my_h + 10))

            # Start off-screen to the right (for slide-in effect)
            self._target_x = int(base_x)
            self._target_y = int(base_y)
            self._start_x = int(parent_x + parent_w + 20)  # Off-screen right

            # Set initial position off-screen
            self.geometry(f"{my_w}x{my_h}+{self._start_x}+{self._target_y}")
        except Exception as e:
            logger.debug("ToastNotification._position_window failed: %s", e)

    def _animate_in(self, step: int = 0) -> None:
        """Slide in from right with fade."""
        if step > 12:
            return
        try:
            if not self.winfo_exists():
                return
            # Slide: interpolate x from _start_x to _target_x
            progress = step / 12
            current_x = int(self._start_x + (self._target_x - self._start_x) * progress)
            alpha = progress
            self.attributes("-alpha", alpha)
            self.geometry(f"+{current_x}+{self._target_y}")
            self.after(20, lambda: self._animate_in(step + 1))
        except Exception:
            pass

    def _update_progress(self) -> None:
        """Update the progress bar to show remaining time."""
        if self._fade_out_started or not self.winfo_exists():
            return
        try:
            if self._start_time is None:
                return
            elapsed = (time.time() - self._start_time) * 1000
            remaining = max(0, 1.0 - (elapsed / self._duration))
            pw = int(remaining * 380)
            self._progress_fill.configure(width=pw)
            self._progress_bg.update_idletasks()
            if remaining > 0:
                self._progress_after_id = self.after(100, self._update_progress)
        except Exception:
            pass

    def _on_auto_dismiss(self) -> None:
        """Called when duration expires — fade out."""
        self._animate_out()

    def _animate_out(self, step: int = 12) -> None:
        """Slide out to the right with fade."""
        if self._fade_out_started:
            return
        self._fade_out_started = True

        def _animate(step: int = 12):
            if step < 0:
                # Remove from queue and destroy
                try:
                    if self in ToastNotification._active_toasts:
                        ToastNotification._active_toasts.remove(self)
                except Exception:
                    pass
                try:
                    self.destroy()
                except Exception:
                    pass
                return
            try:
                if not self.winfo_exists():
                    return
                progress = step / 12
                current_x = int(self._target_x + (self._start_x - self._target_x) * (1 - progress))
                alpha = progress
                self.attributes("-alpha", alpha)
                self.geometry(f"+{current_x}+{self._target_y}")
                self.after(20, lambda: _animate(step - 1))
            except Exception:
                try:
                    self.destroy()
                except Exception:
                    pass

        _animate()

    def destroy(self) -> None:
        """Clean up progress bar timer on destroy."""
        if self._progress_after_id:
            try:
                self.after_cancel(self._progress_after_id)
            except Exception:
                pass
        try:
            if self in ToastNotification._active_toasts:
                ToastNotification._active_toasts.remove(self)
        except Exception:
            pass
        super().destroy()

# --- 6. ONBOARDING GUIDE ---
class OnboardingGuide(ctk.CTkToplevel):
    def __init__(self, parent: Any) -> None:
        super().__init__(parent)
        self.parent = parent
        self.current_step = 0

        self.title("Welcome to NREGA Bot!")
        w, h = 450, 350
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.grab_set()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scrollable_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.steps_data = [
            {"title": "Step 1: Launch a Browser", "desc": "First, click one of the 'Chrome' buttons in the main app to open a special browser. We recommend Chrome.", "icon": self.parent.icon_images.get("onboarding_launch")},
            {"title": "Step 2: Log In to the Portal", "desc": "In the new browser window, log in to the VB-G-RAM-G portal (vbgramgde2.dord.gov.in) with your official credentials.", "icon": self.parent.icon_images.get("onboarding_login")},
            {"title": "Step 3: Choose Your Task", "desc": "Once logged in, return to this app and select your desired automation task from the navigation menu on the left.", "icon": self.parent.icon_images.get("onboarding_select")},
            {"title": "You're All Set!", "desc": "Fill in the required details for your chosen task and click 'Start Automation'. For more help, visit our website from the link in the footer.", "icon": self.parent.icon_images.get("onboarding_start")}
        ]

        self.step_frames = []
        for i, step_info in enumerate(self.steps_data):
            frame = OnboardingStep(self.scrollable_container, step_info["title"], step_info["desc"], step_info["icon"])
            self.step_frames.append(frame)

        self.footer = ctk.CTkFrame(self)
        self.footer.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 20))
        self.footer.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self.footer, height=10)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 15))

        self.next_button = ctk.CTkButton(self.footer, text="Next", command=self.show_next_step, width=100)
        self.next_button.grid(row=0, column=1)

        self.show_step(0)
        self.focus_force()

    def show_step(self, step_index: int) -> None:
        for i, frame in enumerate(self.step_frames):
            if i == step_index:
                frame.pack(expand=True, fill="both")
                frame.tkraise()
            else:
                frame.pack_forget()

        progress_value = (step_index + 1) / len(self.steps_data)
        self.progress_bar.set(progress_value)

        if step_index == len(self.steps_data) - 1:
            self.next_button.configure(text="Finish", command=self.destroy)
        else:
            self.next_button.configure(text="Next")

    def show_next_step(self) -> None:
        self.current_step += 1
        if self.current_step < len(self.steps_data):
            self.show_step(self.current_step)

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