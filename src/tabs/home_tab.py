# tabs/home_tab.py
"""
Home Dashboard Tab — A visual landing page that displays all automations
categorized, with a "Most Used" section at the top based on usage history.
"""

import customtkinter as ctk
import tkinter as tk
from PIL import Image
from src.utils import resource_path, _suppress_overscroll
from src import config
from src.i18n import tr

from typing import Any, Callable, Dict, List, Optional, Tuple


class HomeTab(ctk.CTkFrame):
    """Main dashboard landing page showing all automations in a card layout."""

    # Colors for card variants (light / dark)
    CARD_COLORS = {
        "MR & Wage Management": config.COLORS["cat_mr_wage"],
        "JE & AE Approval": config.COLORS["cat_je_ae"],
        "Schemes Related":       config.COLORS["cat_schemes"],
        "Verification & Utility": config.COLORS["cat_verify"],
        "Reports & Tracking":    config.COLORS["cat_reports"],
        "Smart Tools":           config.COLORS["cat_tools"],
        "About & Help":          config.COLORS["cat_about"],
    }

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        # Geometry is managed by the caller (show_frame in lite_app/main_app)
        # Do NOT call self.pack() or self.grid() here — it conflicts with
        # the parent container's geometry manager.
        # See: _tkinter.TclError: cannot use geometry manager pack inside
        #      a frame that already has slaves managed by grid
        #
        # However, prevent pack propagration so HomeTab maintains the size
        # assigned by the parent's grid manager and doesn't shrink to fit
        # its packed children's minimal requested sizes.
        self.pack_propagate(False)
        


        # Cache all tabs by name
        self._all_tabs = {}
        for cat, tabs in app_instance.get_tabs_definition().items():
            for name, data in tabs.items():
                self._all_tabs[name] = {**data, "category": cat}

        # Blocked/premium cards ko re-style karne ke liye (feature flags update par)
        self._feature_cards: Dict[str, List[Any]] = {}

        # --- Main scrollable container ---
        self.scroll_container = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=(config.COLORS["gray80"], config.COLORS["gray30"]),
            scrollbar_button_hover_color=(config.COLORS["gray70"], config.COLORS["gray20"]),
        )
        self.scroll_container.pack(expand=True, fill="both", padx=5, pady=5)
        self.scroll_container.grid_columnconfigure(0, weight=1)
        _suppress_overscroll(self.scroll_container)

        # Build sections
        self._build_welcome_section()
        self._build_search_section()
        self._build_most_used_section()
        self._build_all_categories()

    # ──────────────────────────────────────────────
    # 1. WELCOME HEADER
    # ──────────────────────────────────────────────
    def _build_welcome_section(self):
        header_frame = ctk.CTkFrame(
            self.scroll_container, fg_color="transparent", corner_radius=0
        )
        header_frame.grid(row=0, column=0, sticky="ew", pady=(15, 5))
        header_frame.grid_columnconfigure(0, weight=1)

        # Greeting
        user_name = self.app.license_info.get("user_name", "")
        greet = tr("home.welcome", name=user_name) if user_name else tr("home.welcome_default")
        ctk.CTkLabel(
            header_frame,
            text=greet,
            font=ctk.CTkFont(family="Helvetica Neue", size=26, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"]),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header_frame,
            text=tr("home.subtitle"),
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"]),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Quick action buttons row — keep compact on the left
        actions_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions_frame.grid(row=2, column=0, sticky="w", pady=(15, 5))

        btn_style = {
            "height": 34,
            "corner_radius": 10,
            "font": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "fg_color": (config.COLORS["text_hover"], config.COLORS["text_hover_dark"]),
            "hover_color": (config.COLORS["text_border"], "#4B5563"),
            "text_color": (config.COLORS["tv_header_bg_dark"], config.COLORS["text_white"]),
        }

        ctk.CTkButton(
            actions_frame, text=tr("home.launch_chrome_btn"),
            image=self.app.icon_images.get("chrome"),
            compound="left",
            command=self.app.launch_chrome_detached, **btn_style
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions_frame, text=tr("home.auto_login_btn"),
            image=self.app.icon_images.get("emoji_login_automation"),
            compound="left",
            command=self.app._quick_login_automation, **btn_style
        ).pack(side="left", padx=(0, 8))

        # Quick stats bar
        total = len(self._all_tabs)
        most = len(self._get_most_used_names())
        stats_icon = self.app.icon_images.get("emoji_tools")
        ctk.CTkLabel(
            actions_frame,
            text=tr("home.stats_label", count=total),
            image=stats_icon,
            compound="left",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"]),
        ).pack(side="left", padx=(8, 0))

    # ──────────────────────────────────────────────
    # 2. SEARCH BAR
    # ──────────────────────────────────────────────
    def _build_search_section(self):
        search_frame = ctk.CTkFrame(
            self.scroll_container, fg_color="transparent", corner_radius=0
        )
        search_frame.grid(row=1, column=0, sticky="ew", pady=(5, 15))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search_change())

        # Search entry with clear button
        entry_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        entry_frame.grid(row=0, column=0, sticky="ew")
        entry_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            entry_frame,
            placeholder_text=tr("home.search_placeholder"),
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=38,
            corner_radius=12,
            fg_color=(config.COLORS["tv_header_bg_light"], config.COLORS["bg_medium"]),
            border_color=(config.COLORS["text_border"], "#555555"),
            textvariable=self.search_var,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        # Clear (X) button
        self.clear_search_btn = ctk.CTkButton(
            entry_frame,
            text="✕",
            width=34,
            height=38,
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=(config.COLORS["text_hover"], "#4B5563"),
            hover_color=(config.COLORS["text_border"], config.COLORS["text_medium"]),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_border"]),
            command=self._clear_search
        )
        self.clear_search_btn.grid(row=0, column=1)

    def _clear_search(self):
        """Clear the search field and reset the view."""
        self.app.play_sound("click")
        self.search_var.set("")
        self.search_entry.focus_set()

    # ──────────────────────────────────────────────
    # 3. MOST USED SECTION
    # ──────────────────────────────────────────────
    def _build_most_used_section(self):
        self.most_used_container = ctk.CTkFrame(
            self.scroll_container, fg_color="transparent", corner_radius=0
        )
        self.most_used_container.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        self.most_used_container.grid_columnconfigure(0, weight=1)

        # Section label
        label_frame = ctk.CTkFrame(self.most_used_container, fg_color="transparent")
        label_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        label_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            label_frame,
            text=tr("home.most_used_title"),
            font=ctk.CTkFont(family="Helvetica Neue", size=18, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"]),
        ).grid(row=0, column=0, sticky="w")

        self.most_used_grid = ctk.CTkFrame(
            self.most_used_container, fg_color="transparent"
        )
        self.most_used_grid.grid(row=1, column=0, sticky="ew")

        # Cache for most-used cards: list of (name, card_widget)
        self._most_used_cards: list = []
        self._most_used_placeholder: Optional[ctk.CTkLabel] = None
        self._most_used_names_cache: list = []

        self._refresh_most_used()

    def _get_most_used_names(self, limit=8):
        """Returns only tabs that have been actually used (usage count > 0).
        Starts empty and fills as the user uses automations."""
        keys = self.app.history_manager.get_most_used_keys(limit)
        names = []
        for k in keys:
            for name, data in self._all_tabs.items():
                if data.get("key") == k and name not in names:
                    names.append(name)
                    break
            if len(names) >= limit:
                break
        return names

    def _refresh_most_used(self):
        """Refresh most-used cards efficiently — only rebuilds when the list changes."""
        names = self._get_most_used_names(8)

        # Skip rebuild if the list hasn't changed
        if names == self._most_used_names_cache:
            return

        self._most_used_names_cache = list(names)

        # Destroy ALL existing cards (list changed, cheaper to rebuild)
        for name, card in self._most_used_cards:
            try:
                card.destroy()
            except Exception:
                pass
            # Prune stale callback references (memory-leak fix)
            if name in getattr(self, '_feature_cards', {}) and card in self._feature_cards[name]:
                try:
                    self._feature_cards[name].remove(card)
                except ValueError:
                    pass
        self._most_used_cards.clear()
        if self._most_used_placeholder:
            try:
                self._most_used_placeholder.destroy()
            except Exception:
                pass
            self._most_used_placeholder = None

        cols = 4
        for idx, name in enumerate(names):
            row = idx // cols
            col = idx % cols
            card = self._create_automation_card(
                self.most_used_grid, name, large=True
            )
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            self.most_used_grid.grid_columnconfigure(col, weight=1, uniform="most")
            self._most_used_cards.append((name, card))

        # Show placeholder if no most-used
        if not names:
            self._most_used_placeholder = ctk.CTkLabel(
                self.most_used_grid,
                text=tr("home.most_used_placeholder"),
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=(config.COLORS["text_light"], config.COLORS["text_medium"]),
            )
            self._most_used_placeholder.grid(row=0, column=0, pady=20)

    # ──────────────────────────────────────────────
    # 4. ALL CATEGORIES
    # ──────────────────────────────────────────────
    def _build_all_categories(self):
        self.all_categories_container = ctk.CTkFrame(
            self.scroll_container, fg_color="transparent", corner_radius=0
        )
        self.all_categories_container.grid(row=3, column=0, sticky="nsew")
        self.all_categories_container.grid_columnconfigure(0, weight=1)

        self._category_rows = {}  # name -> (label, grid_frame)
        self._filtered_state = {}  # name -> bool (visible/hidden)

        row_idx = 0
        for cat, tabs in self.app.get_tabs_definition().items():
            if cat in ("Dashboard", "About & Help"):
                continue  # Skip Dashboard (the Home tab itself) and About & Help

            # Category header
            cat_header = ctk.CTkFrame(
                self.all_categories_container, fg_color="transparent"
            )
            cat_header.grid(row=row_idx, column=0, sticky="ew", pady=(5, 5))
            cat_header.grid_columnconfigure(0, weight=1)

            colors = self.CARD_COLORS.get(cat, {})
            accent = colors.get("accent", (config.COLORS["blue"], config.COLORS["blue_light"]))

            ctk.CTkLabel(
                cat_header,
                text=tr(f"nav.cat.{cat}", default=cat),
                font=ctk.CTkFont(family="Helvetica Neue", size=16, weight="bold"),
                text_color=accent,
            ).grid(row=0, column=0, sticky="w")

            row_idx += 1

            # Grid for cards
            grid = ctk.CTkFrame(
                self.all_categories_container, fg_color="transparent"
            )
            grid.grid(row=row_idx, column=0, sticky="ew", pady=(0, 12))

            self._category_rows[cat] = (cat_header, grid)
            self._filtered_state[cat] = True

            # Fill cards
            tabs_list = list(tabs.items())
            # Place them with a separate info frame
            for j, (name, data) in enumerate(tabs_list):
                card = self._create_automation_card(grid, name, large=False)
                card.grid(row=j // 4, column=j % 4, sticky="nsew", padx=4, pady=4)

            for c in range(4):
                grid.grid_columnconfigure(c, weight=1, uniform="cat")

            row_idx += 1

    # ──────────────────────────────────────────────
    # 5. AUTOMATION CARD
    # ──────────────────────────────────────────────
    def _create_automation_card(self, parent, name, large=False):
        info = self._all_tabs.get(name, {})
        icon = info.get("icon")
        cat = info.get("category", "")
        colors = self.CARD_COLORS.get(cat, {})

        if large:
            w = 160
            h = 78
            icon_size = 20
            font_size = 11
            pad = 4
        else:
            w = 155
            h = 62
            icon_size = 16
            font_size = 10
            pad = 3

        bg_color = colors.get("bg", (config.COLORS["tv_header_bg_light"], config.COLORS["gray_2D2D2D"]))
        border_color = colors.get("border", (config.COLORS["text_hover"], config.COLORS["gray_444"]))

        card = ctk.CTkFrame(
            parent,
            width=w,
            height=h,
            corner_radius=10,
            fg_color=bg_color,
            border_width=1,
            border_color=border_color,
        )
        card.grid_propagate(False)
        card.configure(cursor="hand2")

        # --- Content ---
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # Icon display — supports both CTkImage (full app) and emoji string (Lite app)
        if isinstance(icon, str):
            # Unicode emoji character from Lite config
            icon_label = ctk.CTkLabel(
                inner, text=icon, font=ctk.CTkFont(size=icon_size + 4)
            )
        elif icon:
            # CTkImage object from full app
            icon_label = ctk.CTkLabel(inner, image=icon, text="", width=icon_size, height=icon_size)
        else:
            # Fallback
            icon_label = ctk.CTkLabel(
                inner, text="⚙️", font=ctk.CTkFont(size=icon_size + 2)
            )
        icon_label.pack(pady=(0, pad))

        name_label = ctk.CTkLabel(
            inner,
            text=tr(f"nav.tab.{name}", default=name),
            font=ctk.CTkFont(family="Segoe UI", size=font_size, weight="bold"),
            text_color=(config.COLORS["tv_header_bg_dark"], config.COLORS["text_white"]),
        )
        name_label.pack()

        # Store automation name as an attribute for search filtering
        card._automation_name = name

        # ── Feature state: blocked (admin) / premium (trial-locked) ──
        state = self._get_feature_state(name)

        # --- Hover effects ---
        hover_bg = self._lighten(bg_color[0], -15) if ctk.get_appearance_mode() == "Light" else self._lighten(bg_color[1], 20)
        original_text_color = (config.COLORS["tv_header_bg_dark"], config.COLORS["text_white"])
        hover_text_color = (config.COLORS["tv_header_fg_dark"], config.COLORS["text_white"])  # White in light mode, unchanged in dark

        # Blocked cards: greyed + red accent; premium: indigo accent
        if state == "blocked":
            card.configure(
                fg_color=("#FEF2F2", "#450A0A"),
                border_color=("#DC2626", "#F87171"),
                border_width=1,
            )
            name_label.configure(text=f"⚠️ {name}", text_color=("#DC2626", "#F87171"))
        elif state == "premium":
            card.configure(
                fg_color=("#EEF2FF", "#312E81"),
                border_color=("#6366F1", "#818CF8"),
                border_width=1,
            )
            name_label.configure(text=f"🔒 {name}", text_color=("#4F46E5", "#A5B4FC"))

        # Refresh helper — re-styles the card when feature flags update
        def _apply_card_state():
            s = self._get_feature_state(name)
            if s == "blocked":
                card.configure(fg_color=("#FEF2F2", "#450A0A"), border_color=("#DC2626", "#F87171"), border_width=1)
                name_label.configure(text=f"⚠️ {name}", text_color=("#DC2626", "#F87171"))
            elif s == "premium":
                card.configure(fg_color=("#EEF2FF", "#312E81"), border_color=("#6366F1", "#818CF8"), border_width=1)
                name_label.configure(text=f"🔒 {name}", text_color=("#4F46E5", "#A5B4FC"))
            else:
                card.configure(fg_color=bg_color, border_color=border_color, border_width=1)
                name_label.configure(text=name, text_color=original_text_color)

        # Live widget reference store — destroyed cards hata diye jate hain (no leak)
        card._apply_state_fn = _apply_card_state
        self._feature_cards.setdefault(name, []).append(card)

        def on_enter(e, c=card, nl=name_label, hb=hover_bg, htc=hover_text_color):
            # Dynamically re-check — stale card state par hover galat na lage
            if self._get_feature_state(name) is None:
                c.configure(fg_color=hb, border_width=2, border_color=border_color)
                nl.configure(text_color=htc)

        def on_leave(e, c=card):
            # Restore per the live feature state (keeps blocked/premium styling)
            _apply_card_state()

        def on_click(e=None):
            st = self._get_feature_state(name)
            if st == "blocked":
                alert = getattr(self.app, 'show_feature_maintenance_alert', None)
                if alert:
                    alert(name)  # internally plays the error sound
                else:  # Lite app fallback
                    self.app.play_sound("error")
                    tk.messagebox.showwarning(tr("home.maintenance_title"),
                                              tr("home.maintenance_msg", name=name))
                return
            if st == "premium":
                alert = getattr(self.app, 'show_trial_lock_alert', None)
                if alert:
                    alert(name)  # internally plays the error sound
                else:  # Lite app fallback
                    self.app.play_sound("error")
                    tk.messagebox.showinfo(tr("home.premium_feature_title"),
                                           tr("home.premium_feature_msg", name=name))
                return
            self.app.play_sound("click")
            self.app.show_frame(name)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        card.bind("<Button-1>", on_click)

        # Make ALL children clickable — every pixel of the card
        for child in [inner, icon_label, name_label]:
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)
            child.bind("<Button-1>", on_click)

        return card

    # ──────────────────────────────────────────────
    # 6. SEARCH / FILTER
    # ──────────────────────────────────────────────
    def _on_search_change(self):
        query = self.search_var.get().strip().lower()

        if not query:
            # Re-show most-used section
            self.most_used_container.grid()
            self._refresh_most_used()
            # Show all categories again — INCLUDING all children (fixes disappearing cards)
            for cat, (header, grid) in self._category_rows.items():
                header.grid()
                grid.grid()
                for child in grid.winfo_children():
                    try:
                        child.grid()
                    except Exception:
                        pass
                self._filtered_state[cat] = True
            return

        # Hide most-used section during search
        self.most_used_container.grid_remove()

        # Filter the cards inside categories using the stored _automation_name attribute
        for cat, (header, grid) in self._category_rows.items():
            has_match = False
            for child in grid.winfo_children():
                if not child.winfo_exists():
                    continue
                card_name = getattr(child, '_automation_name', '')
                if query in card_name.lower():
                    try:
                        child.grid()
                    except Exception:
                        pass
                    has_match = True
                else:
                    try:
                        child.grid_remove()
                    except Exception:
                        pass

            if has_match:
                header.grid()
                grid.grid()
            else:
                header.grid_remove()
                grid.grid_remove()

            self._filtered_state[cat] = has_match

    # ──────────────────────────────────────────────
    # 7. FEATURE STATE (blocked / premium)
    # ──────────────────────────────────────────────
    def _get_feature_state(self, name: str) -> Optional[str]:
        """
        Return 'blocked' | 'premium' | None for a tab name.

        Mirrors nav-button logic in _apply_feature_flags:
          - global_disabled_features → blocked (admin kill-switch / maintenance)
          - trial_restricted_features → premium (trial users ke liye locked)
        Home page cards ko bhi yahi guard apply hota hai.
        """
        disabled = getattr(self.app, 'global_disabled_features', None) or []
        restricted = getattr(self.app, 'trial_restricted_features', None) or []

        # Admin block (list OR legacy dict format)
        if isinstance(disabled, (list, tuple)):
            if name in disabled:
                return "blocked"
        elif isinstance(disabled, dict):
            if name in disabled:
                return "blocked"

        # Premium lock for trial users
        if isinstance(restricted, (list, tuple)) and name in restricted:
            return "premium"

        return None

    def refresh_feature_states(self):
        """Re-style all LIVE home cards when feature flags update.
        Called from _apply_feature_flags (main_app + lite_app)."""
        for cards in list(getattr(self, '_feature_cards', {}).values()):
            for card in cards:
                try:
                    if card.winfo_exists() and hasattr(card, '_apply_state_fn'):
                        card._apply_state_fn()
                except Exception:
                    pass

    # ──────────────────────────────────────────────
    # 8. HELPERS
    # ──────────────────────────────────────────────
    def _lighten(self, hex_color, amount):
        """Lighten or darken a hex color by amount (±)."""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = max(0, min(255, r + amount))
        g = max(0, min(255, g + amount))
        b = max(0, min(255, b + amount))
        return f"#{r:02x}{g:02x}{b:02x}"

    def refresh(self):
        """Re-build most-used section (called after a tab is used)."""
        if hasattr(self, "most_used_grid") and self.most_used_grid.winfo_exists():
            self._refresh_most_used()
