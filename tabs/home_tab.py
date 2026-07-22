# tabs/home_tab.py
"""
Home Dashboard Tab — A visual landing page that displays all automations
categorized, with a "Most Used" section at the top based on usage history.
"""

import customtkinter as ctk
import tkinter as tk
from PIL import Image
from utils import resource_path


class HomeTab(ctk.CTkFrame):
    """Main dashboard landing page showing all automations in a card layout."""

    # Colors for card variants (light / dark)
    CARD_COLORS = {
        "MR & Wage Management": {
            "bg": ("#EFF6FF", "#1E3A5F"),
            "border": ("#BFDBFE", "#3B82F6"),
            "accent": ("#3B82F6", "#60A5FA"),
        },
        "JE & AE Approval": {
            "bg": ("#F0FDF4", "#14532D"),
            "border": ("#BBF7D0", "#22C55E"),
            "accent": ("#16A34A", "#4ADE80"),
        },
        "Schemes Related": {
            "bg": ("#FFF7ED", "#431407"),
            "border": ("#FED7AA", "#F97316"),
            "accent": ("#EA580C", "#FB923C"),
        },
        "Verification & Utility": {
            "bg": ("#F5F3FF", "#2E1065"),
            "border": ("#DDD6FE", "#8B5CF6"),
            "accent": ("#7C3AED", "#A78BFA"),
        },
        "Reports & Tracking": {
            "bg": ("#FEF2F2", "#450A0A"),
            "border": ("#FECACA", "#EF4444"),
            "accent": ("#DC2626", "#F87171"),
        },
        "Smart Tools": {
            "bg": ("#FEFCE8", "#422006"),
            "border": ("#FDE68A", "#EAB308"),
            "accent": ("#CA8A04", "#FACC15"),
        },
        "About & Help": {
            "bg": ("#F0F9FF", "#0C4A6E"),
            "border": ("#BAE6FD", "#0EA5E9"),
            "accent": ("#0284C7", "#38BDF8"),
        },
    }

    def __init__(self, parent, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.pack(expand=True, fill="both")

        # Cache all tabs by name
        self._all_tabs = {}
        for cat, tabs in app_instance.get_tabs_definition().items():
            for name, data in tabs.items():
                self._all_tabs[name] = {**data, "category": cat}

        # --- Main scrollable container ---
        self.scroll_container = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=("gray80", "gray30"),
            scrollbar_button_hover_color=("gray70", "gray20"),
        )
        self.scroll_container.pack(expand=True, fill="both", padx=5, pady=5)
        self.scroll_container.grid_columnconfigure(0, weight=1)

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
        greet = f"Welcome, {user_name}!" if user_name else "Welcome!"
        ctk.CTkLabel(
            header_frame,
            text=greet,
            font=ctk.CTkFont(family="Helvetica Neue", size=26, weight="bold"),
            text_color=("#111827", "#F3F4F6"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header_frame,
            text="Select an automation below to get started. Quickly find what you need.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#6B7280", "#9CA3AF"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Quick action buttons row
        actions_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions_frame.grid(row=2, column=0, sticky="w", pady=(15, 5))

        btn_style = {
            "height": 34,
            "corner_radius": 10,
            "font": ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            "fg_color": ("#E5E7EB", "#374151"),
            "hover_color": ("#D1D5DB", "#4B5563"),
            "text_color": ("#1F2937", "#F3F4F6"),
        }

        ctk.CTkButton(
            actions_frame, text="🚀 Launch Chrome",
            command=self.app.launch_chrome_detached, **btn_style
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions_frame, text="🔐 Auto Login",
            command=self.app._quick_login_automation, **btn_style
        ).pack(side="left", padx=(0, 8))

        # Quick stats bar
        total = len(self._all_tabs)
        most = len(self._get_most_used_names())
        ctk.CTkLabel(
            actions_frame,
            text=f"📊 {total} Automations Available",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#6B7280", "#9CA3AF"),
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
            placeholder_text="🔍  Search automations...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=38,
            corner_radius=12,
            fg_color=("#F9FAFB", "#333333"),
            border_color=("#D1D5DB", "#555555"),
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
            fg_color=("#E5E7EB", "#4B5563"),
            hover_color=("#D1D5DB", "#6B7280"),
            text_color=("#6B7280", "#D1D5DB"),
            command=self._clear_search
        )
        self.clear_search_btn.grid(row=0, column=1)

    def _clear_search(self):
        """Clear the search field and reset the view."""
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
            text="⭐ Most Used",
            font=ctk.CTkFont(family="Helvetica Neue", size=18, weight="bold"),
            text_color=("#111827", "#F3F4F6"),
        ).grid(row=0, column=0, sticky="w")

        self.most_used_grid = ctk.CTkFrame(
            self.most_used_container, fg_color="transparent"
        )
        self.most_used_grid.grid(row=1, column=0, sticky="ew")

        self._refresh_most_used()

    def _get_most_used_names(self, limit=6):
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
        # No fallback padding — stays empty until user uses automations
        return names

    def _refresh_most_used(self):
        for w in self.most_used_grid.winfo_children():
            w.destroy()

        names = self._get_most_used_names(8)
        cols = 4
        for idx, name in enumerate(names):
            row = idx // cols
            col = idx % cols
            card = self._create_automation_card(
                self.most_used_grid, name, large=True
            )
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            self.most_used_grid.grid_columnconfigure(col, weight=1, uniform="most")

        # If no most-used, show a placeholder
        if not names:
            ctk.CTkLabel(
                self.most_used_grid,
                text="Start using automations — your most-used will appear here.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=("#9CA3AF", "#6B7280"),
            ).grid(row=0, column=0, pady=20)

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
            accent = colors.get("accent", ("#3B82F6", "#60A5FA"))

            ctk.CTkLabel(
                cat_header,
                text=cat,
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

        bg_color = colors.get("bg", ("#F9FAFB", "#2D2D2D"))
        border_color = colors.get("border", ("#E5E7EB", "#444444"))

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

        # Icon display
        if icon:
            icon_label = ctk.CTkLabel(inner, image=icon, text="", width=icon_size, height=icon_size)
        else:
            # Fallback: show emoji based on name
            icon_label = ctk.CTkLabel(
                inner, text="⚙️", font=ctk.CTkFont(size=icon_size + 2)
            )
        icon_label.pack(pady=(0, pad))

        name_label = ctk.CTkLabel(
            inner,
            text=name,
            font=ctk.CTkFont(family="Segoe UI", size=font_size, weight="bold"),
            text_color=("#1F2937", "#F3F4F6"),
        )
        name_label.pack()

        # Store automation name as an attribute for search filtering
        card._automation_name = name

        # --- Hover effects ---
        hover_bg = self._lighten(bg_color[0], -15) if ctk.get_appearance_mode() == "Light" else self._lighten(bg_color[1], 20)

        def on_enter(e, c=card, hb=hover_bg):
            c.configure(
                fg_color=hb,
                border_width=2,
                border_color=border_color,
            )

        def on_leave(e, c=card, bg=bg_color, bc=border_color):
            c.configure(
                fg_color=bg,
                border_width=1,
                border_color=bc,
            )

        def on_click(e=None):
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
    # 7. HELPERS
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
