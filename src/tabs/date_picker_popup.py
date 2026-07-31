# tabs/date_picker_popup.py
#
# A2: Extracted from base_tab.py to separate file.
# Reusable modal popup for selecting a date.
#
# Usage:
#   from tabs.date_picker_popup import DatePickerPopup
#   DatePickerPopup(parent, on_date_select=lambda date_str: ...)

import calendar
import customtkinter as ctk
from datetime import datetime
from typing import Any, Callable

from src import config
from src.utils import get_logger

logger = get_logger()


class DatePickerPopup(ctk.CTkToplevel):
    """
    Clean, compact modal popup for selecting a date.

    Pre-creates all day buttons ONCE in __init__, then reuses them
    on month navigation — no widget destruction/creation overhead.

    Features:
    - Centered on the main application window.
    - Compact rounded day grid with 2-letter weekday headers.
    - Highlights Today (Blue), Mondays (soft green), Sundays (soft red).
    - 'Today' shortcut button to jump straight back to the current date.
    """
    def __init__(self, parent: Any, on_date_select: Callable[[str], None]) -> None:
        super().__init__(parent)
        self.on_date_select = on_date_select
        self.title("Select Date")

        # Dimensions (compact & clean)
        width, height = 285, 330

        # Calculate Center Position relative to Parent
        try:
            parent.update_idletasks()
            x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
            y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
        except Exception:
            # Fallback if parent coords aren't ready
            x, y = 100, 100

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.transient(parent)  # Keeps it on top of the parent window

        self.current_year = datetime.now().year
        self.current_month = datetime.now().month

        # --- Header Section (Month/Year & Navigation) ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=10, pady=(12, 4))

        nav_style = {
            "width": 32, "height": 30, "corner_radius": 8,
            "fg_color": ("gray88", "gray25"), "hover_color": ("gray75", "gray38"),
            "text_color": ("black", "white"), "font": ctk.CTkFont(size=13, weight="bold"),
        }
        ctk.CTkButton(self.header_frame, text="◀", command=self.prev_month, **nav_style).pack(side="left")

        self.lbl_month_year = ctk.CTkLabel(
            self.header_frame, text="",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=(config.COLORS["blue_dark"], config.COLORS["blue_light"])
        )
        self.lbl_month_year.pack(side="left", expand=True)

        ctk.CTkButton(self.header_frame, text="▶", command=self.next_month, **nav_style).pack(side="right")

        # --- Calendar Grid Section ---
        self.cal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cal_frame.pack(expand=True, fill="both", padx=10, pady=(2, 2))

        # Pre-create weekday headers ONCE (never destroyed) — 2-letter, muted
        days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for i, day_name in enumerate(days):
            t_color = (config.COLORS["red_text"], config.COLORS["red_text_light"]) if i == 6 \
                else (config.COLORS["text_medium"], config.COLORS["text_light"])
            ctk.CTkLabel(
                self.cal_frame, text=day_name,
                font=ctk.CTkFont(size=11, weight="bold"), text_color=t_color
            ).grid(row=0, column=i, padx=2, pady=(0, 4))

        # Pre-create 42 reusable day buttons (6 rows x 7 cols)
        self.day_buttons = []  # 2D list: day_buttons[row][col]
        for r in range(6):
            row_btns = []
            for c in range(7):
                btn = ctk.CTkButton(
                    self.cal_frame, text="", width=32, height=30, corner_radius=8,
                    fg_color="transparent",
                    hover_color=("gray80", "gray32"),
                    text_color=("black", "white"),
                    command=lambda d=0: self._on_day_click(d)
                )
                btn.grid(row=r + 1, column=c, padx=2, pady=2)
                row_btns.append(btn)
            self.day_buttons.append(row_btns)

        # Populate buttons for current month
        self._update_calendar()

        # --- Footer: Today shortcut ---
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkButton(
            self.footer_frame, text="📅 Today", width=80, height=28, corner_radius=8,
            fg_color=(config.COLORS["blue"], config.COLORS["blue_hover"]),
            hover_color=(config.COLORS["blue_hover"], config.COLORS["blue_dark"]),
            text_color="white", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._select_today
        ).pack(side="right")

        self.focus_force()

    def _on_day_click(self, day: int) -> None:
        """Handle a day button click — guard against zero-day (empty cell)."""
        if day > 0:
            selected_date = f"{day:02d}/{self.current_month:02d}/{self.current_year}"
            self.on_date_select(selected_date)
            self.destroy()

    def _select_today(self) -> None:
        """Jump back to the current month and select today."""
        now = datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        self._update_calendar()
        self._on_day_click(now.day)

    def _update_calendar(self) -> None:
        """
        Reuses pre-created day buttons instead of destroying/creating widgets.
        Only updates text, colors, and commands — no widget creation overhead.
        """
        # Update header
        month_name = calendar.month_name[self.current_month]
        self.lbl_month_year.configure(text=f"{month_name} {self.current_year}")

        cal = calendar.monthcalendar(self.current_year, self.current_month)
        now = datetime.now()
        today = (now.day, now.month, now.year)

        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                btn = self.day_buttons[r][c]
                if day != 0:
                    # Defaults
                    fg = "transparent"
                    hov = ("gray80", "gray32")
                    txt = ("black", "white")

                    if c == 0:  # Monday — soft green
                        fg = (config.COLORS["green_very_light"], config.COLORS["green_dark_btn"])
                    elif c == 6:  # Sunday — soft red
                        fg = (config.COLORS["red_very_light"], config.COLORS["red_dark"])
                        txt = (config.COLORS["red_text"], config.COLORS["red_text_light"])

                    # Highlight Today — Blue
                    if day == today[0] and self.current_month == today[1] and self.current_year == today[2]:
                        fg = (config.COLORS["blue"], config.COLORS["blue_hover"])
                        txt = "white"
                        hov = (config.COLORS["blue_hover_nav"], config.COLORS["blue_dark"])

                    btn.configure(
                        text=str(day),
                        fg_color=fg,
                        hover_color=hov,
                        text_color=txt,
                        state="normal",
                        command=lambda d=day: self._on_day_click(d)
                    )
                else:
                    # Empty cell — hide button (reset colors so a previously
                    # highlighted green/red/blue cell doesn't linger as a square)
                    btn.configure(
                        text="", state="disabled",
                        fg_color="transparent",
                        hover_color=("gray80", "gray32"),
                        text_color=("black", "white"),
                    )

    def prev_month(self) -> None:
        self.current_month -= 1
        if self.current_month == 0:
            self.current_month = 12
            self.current_year -= 1
        self._update_calendar()

    def next_month(self) -> None:
        self.current_month += 1
        if self.current_month == 13:
            self.current_month = 1
            self.current_year += 1
        self._update_calendar()

    def select_date(self, day: int) -> None:
        """Legacy method kept for backward compatibility."""
        if day > 0:
            selected_date = f"{day:02d}/{self.current_month:02d}/{self.current_year}"
            self.on_date_select(selected_date)
            self.destroy()
