# tabs/settings_tab.py
"""
Settings Tab — User-friendly settings for NREGA Bot.

Allows users to:
  1. Panchayat Suggestions — View and delete saved panchayat autocomplete suggestions
  2. Staff Mapping — View and edit MR & MB staff/mate mappings per panchayat
  3. Default Values — Set default values used across automation tabs
"""

import os
import json
import tkinter
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

import customtkinter as ctk

from src import config
from src.utils import get_data_path, get_logger
from src.ui_components import AfterTracker

logger = get_logger()


class SettingsTab(ctk.CTkFrame):
    """Main Settings dashboard with 3 user-friendly tabs."""

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self._tracker = AfterTracker(self)

        # Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──
        self._build_header()

        # ── Tab View ──
        self.tab_view = ctk.CTkTabview(self, corner_radius=8)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 20))

        self.tab_panchayat = self.tab_view.add("  🏘️  Panchayat Suggestions  ")
        self.tab_state     = self.tab_view.add("  🗺️  State/District/Block  ")
        self.tab_mapping  = self.tab_view.add("  👥  Staff Mapping  ")
        self.tab_defaults = self.tab_view.add("  ⚙️  Default Values  ")

        # Build each tab
        self._build_panchayat_tab()
        self._build_state_tab()
        self._build_mapping_tab()
        self._build_defaults_tab()

    # ────────────────────────────────────────────────────────────────
    # HEADER
    # ────────────────────────────────────────────────────────────────
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="⚙️", font=ctk.CTkFont(size=28)
        ).grid(row=0, column=0, padx=(0, 12))

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            title_frame, text="Settings",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame,
            text="Manage saved data, staff mappings, and default values",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        ).pack(anchor="w")

    # ════════════════════════════════════════════════════════════════
    # TAB 1: PANCHAYAT SUGGESTIONS
    # ════════════════════════════════════════════════════════════════
    def _build_panchayat_tab(self) -> None:
        container = self.tab_panchayat
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Info banner
        info_frame = ctk.CTkFrame(container, fg_color=("gray95", "gray25"), corner_radius=8)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ctk.CTkLabel(
            info_frame,
            text="💡 Jab bhi aap kisi automation tab mein Panchayat name type karte hain, "
                 "to wo automatically save ho jata hai taki agli baar suggestion aaye. "
                 "Yahan se aap naye panchayat add kar sakte hain ya purane hata sakte hain.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray80"),
            wraplength=700,
            justify="left",
        ).pack(padx=15, pady=10)

        # Add new panchayat row
        add_frame = ctk.CTkFrame(container, fg_color="transparent")
        add_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))
        add_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            add_frame, text="➕ Add New:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(5, 10))

        self.add_panchayat_entry = ctk.CTkEntry(
            add_frame, placeholder_text="Panchayat name likhein...",
            font=ctk.CTkFont(size=13),
        )
        self.add_panchayat_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.add_panchayat_entry.bind("<Return>", lambda e: self._add_panchayat())

        ctk.CTkButton(
            add_frame, text="➕ Add", width=70, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#16A34A", "#16A34A"),
            text_color="white",
            hover_color=("#15803D", "#15803D"),
            command=self._add_panchayat,
        ).grid(row=0, column=2, sticky="w", padx=(0, 5))

        # Toolbar
        toolbar = ctk.CTkFrame(container, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 5))
        toolbar.grid_columnconfigure(0, weight=1)

        self.panchayat_count_label = ctk.CTkLabel(
            toolbar, text="", font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        )
        self.panchayat_count_label.pack(side="left")

        ctk.CTkButton(
            toolbar, text="🔄 Refresh", width=90, height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"),
            hover_color=("#CBD5E1", "#475569"),
            command=self._refresh_panchayat_list,
        ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            toolbar, text="🗑️ Delete Selected", height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#FEE2E2", "#450A0A"),
            text_color=("#DC2626", "#F87171"),
            hover_color=("#FECACA", "#7F1D1D"),
            command=self._delete_selected_panchayat,
        ).pack(side="right", padx=(5, 0))

        # Listbox with scrollbar
        list_container = ctk.CTkFrame(container, fg_color="transparent")
        list_container.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        # Native tk widgets need SINGLE color strings, NOT CTk-style tuples
        _border_color = self._resolve_color(("#CBD5E1", "#475569"))
        self.panchayat_listbox = tkinter.Listbox(
            list_container,
            selectmode=tkinter.EXTENDED,
            font=("Segoe UI", 12),
            bg=self._get_listbox_bg(),
            fg=self._get_listbox_fg(),
            selectbackground="#3B82F6",
            selectforeground="white",
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=_border_color,
            highlightbackground=_border_color,
        )
        self.panchayat_listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ctk.CTkScrollbar(list_container, command=self.panchayat_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.panchayat_listbox.configure(yscrollcommand=scrollbar.set)

        # Bind double-click to delete
        self.panchayat_listbox.bind("<Double-1>", lambda e: self._delete_selected_panchayat())
        self.panchayat_listbox.bind("<Delete>", lambda e: self._delete_selected_panchayat())

        self._refresh_panchayat_list()

    def _get_listbox_bg(self) -> str:
        return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#ffffff"

    def _get_listbox_fg(self) -> str:
        return "#e5e7eb" if ctk.get_appearance_mode() == "Dark" else "#374151"

    @staticmethod
    def _resolve_color(ctk_tuple):
        """Resolve a CTk-style (light, dark) color tuple to a single Tk color string."""
        if isinstance(ctk_tuple, tuple):
            return ctk_tuple[1] if ctk.get_appearance_mode() == "Dark" else ctk_tuple[0]
        return ctk_tuple

    def _refresh_panchayat_list(self) -> None:
        """Load all panchayat_name suggestions from the history DB."""
        self.panchayat_listbox.delete(0, "end")
        suggestions = self.app.history_manager.get_suggestions("panchayat_name")
        # Also include other panchayat field keys
        all_panchayats = set(suggestions)
        for key in ["panchayat", "dashboard_panchayat", "mr_track_panchayat",
                     "issued_mr_panchayat", "audit_panchayat_respond"]:
            for s in self.app.history_manager.get_suggestions(key):
                all_panchayats.add(s)

        sorted_panchayats = sorted(all_panchayats)
        for p in sorted_panchayats:
            self.panchayat_listbox.insert("end", p)

        self.panchayat_count_label.configure(
            text=f"Total: {len(sorted_panchayats)} panchayat(s)"
        )

    def _delete_selected_panchayat(self) -> None:
        """Delete the selected panchayat(s) from all suggestion lists."""
        selected = self.panchayat_listbox.curselection()
        if not selected:
            messagebox.showinfo("No Selection", "Kisi panchayat ko select karein.", parent=self.winfo_toplevel())
            return

        names = [self.panchayat_listbox.get(i) for i in selected]
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Kya aap ye {len(names)} panchayat name(s) delete karna chahte hain?\n\n"
            + "\n".join(f"  • {n}" for n in names) +
            "\n\nYe ab panchayat field mein suggestion nahi aayenge.",
            parent=self.winfo_toplevel()
        )
        if not confirm:
            return

        hm = self.app.history_manager
        for name in names:
            # Delete from all possible panchayat field keys
            for key in ["panchayat_name", "panchayat", "dashboard_panchayat",
                         "mr_track_panchayat", "issued_mr_panchayat", "audit_panchayat_respond"]:
                hm.remove_entry(key, name)

        self.app.play_sound("success")
        self._refresh_panchayat_list()
        messagebox.showinfo("Deleted", f"{len(names)} panchayat(s) delete kar diye gaye.", parent=self.winfo_toplevel())

    def _add_panchayat(self) -> None:
        """Add a new panchayat name to suggestion lists (auto-uppercased)."""
        name = self.add_panchayat_entry.get().strip().upper()
        if not name:
            messagebox.showinfo("No Input", "Panchayat name likhein.", parent=self.winfo_toplevel())
            return

        hm = self.app.history_manager
        # Save to all common panchayat field keys so it shows up everywhere
        saved_count = 0
        for key in ["panchayat_name", "panchayat", "dashboard_panchayat",
                     "mr_track_panchayat", "issued_mr_panchayat", "audit_panchayat_respond"]:
            try:
                hm.save_entry(key, name)
                saved_count += 1
            except Exception:
                pass

        self.add_panchayat_entry.delete(0, "end")
        self.app.play_sound("success")
        self._refresh_panchayat_list()
        messagebox.showinfo("Added", f"'{name}' add kar diya gaya.\nAb ye sabhi automation tabs mein suggestion ke roop mein dikhega.", parent=self.winfo_toplevel())

    # ════════════════════════════════════════════════════════════════
    # TAB 2: STATE / DISTRICT / BLOCK SUGGESTIONS
    # ════════════════════════════════════════════════════════════════
    def _build_state_tab(self) -> None:
        container = self.tab_state
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Info banner
        info_frame = ctk.CTkFrame(container, fg_color=("gray95", "gray25"), corner_radius=8)
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ctk.CTkLabel(
            info_frame,
            text="💡 Yahan aap State, District aur Block ke naam add/delete kar sakte hain. "
                 "Ye sabhi automation tabs (MR Tracking, MIS Reports, Dashboard, Issued MR) mein "
                 "suggestion ke roop mein dikhenge aur case-insensitive matching hogi.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray80"),
            wraplength=700,
            justify="left",
        ).pack(padx=15, pady=10)

        # ── Type Selector ──
        type_frame = ctk.CTkFrame(container, fg_color="transparent")
        type_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))
        type_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            type_frame, text="Type:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(5, 10))

        self.state_type_var = ctk.StringVar(value="State")
        self.state_type_menu = ctk.CTkSegmentedButton(
            type_frame,
            values=["State", "District", "Block"],
            variable=self.state_type_var,
            command=lambda v: self._refresh_state_list(),
        )
        self.state_type_menu.grid(row=0, column=1, sticky="w", padx=(0, 10))

        # ── Add new row ──
        add_frame = ctk.CTkFrame(container, fg_color="transparent")
        add_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 5))
        add_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            add_frame, text="➕ Add New:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(5, 10))

        self.add_state_entry = ctk.CTkEntry(
            add_frame, placeholder_text="Naam likhein (e.g., JHARKHAND)...",
            font=ctk.CTkFont(size=13),
        )
        self.add_state_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.add_state_entry.bind("<Return>", lambda e: self._add_state_value())

        ctk.CTkButton(
            add_frame, text="➕ Add", width=70, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#16A34A", "#16A34A"),
            text_color="white",
            hover_color=("#15803D", "#15803D"),
            command=self._add_state_value,
        ).grid(row=0, column=2, sticky="w", padx=(0, 5))

        # ── Toolbar ──
        toolbar = ctk.CTkFrame(container, fg_color="transparent")
        toolbar.grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 5))
        toolbar.grid_columnconfigure(0, weight=1)

        self.state_count_label = ctk.CTkLabel(
            toolbar, text="", font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        )
        self.state_count_label.pack(side="left")

        ctk.CTkButton(
            toolbar, text="🔄 Refresh", width=90, height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"),
            hover_color=("#CBD5E1", "#475569"),
            command=self._refresh_state_list,
        ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            toolbar, text="🗑️ Delete Selected", height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#FEE2E2", "#450A0A"),
            text_color=("#DC2626", "#F87171"),
            hover_color=("#FECACA", "#7F1D1D"),
            command=self._delete_selected_state,
        ).pack(side="right", padx=(5, 0))

        # ── Listbox with scrollbar ──
        list_container = ctk.CTkFrame(container, fg_color="transparent")
        list_container.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        _border_color = self._resolve_color(("#CBD5E1", "#475569"))
        self.state_listbox = tkinter.Listbox(
            list_container,
            selectmode=tkinter.EXTENDED,
            font=("Segoe UI", 12),
            bg=self._get_listbox_bg(),
            fg=self._get_listbox_fg(),
            selectbackground="#3B82F6",
            selectforeground="white",
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=_border_color,
            highlightbackground=_border_color,
        )
        self.state_listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ctk.CTkScrollbar(list_container, command=self.state_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.state_listbox.configure(yscrollcommand=scrollbar.set)

        self.state_listbox.bind("<Double-1>", lambda e: self._delete_selected_state())
        self.state_listbox.bind("<Delete>", lambda e: self._delete_selected_state())

        self._refresh_state_list()

    # ── Helper: get all history keys for current state type ──
    def _get_current_state_keys(self) -> list:
        t = self.state_type_var.get()
        if t == "State":
            return ["mr_track_state", "issued_mr_state", "mis_state", "dashboard_state"]
        elif t == "District":
            return ["mr_track_district", "issued_mr_district", "mis_district", "dashboard_district"]
        else:  # Block
            return ["mr_track_block", "issued_mr_block", "mis_block", "dashboard_block"]

    def _refresh_state_list(self) -> None:
        """Load current type suggestions from history DB."""
        self.state_listbox.delete(0, "end")
        keys = self._get_current_state_keys()
        all_values = set()
        hm = self.app.history_manager
        for key in keys:
            for s in hm.get_suggestions(key):
                all_values.add(s)

        sorted_vals = sorted(all_values)
        for v in sorted_vals:
            self.state_listbox.insert("end", v)

        type_label = self.state_type_var.get()
        self.state_count_label.configure(
            text=f"Total {type_label}(s): {len(sorted_vals)}"
        )

    def _delete_selected_state(self) -> None:
        """Delete the selected value(s) from all relevant history keys."""
        selected = self.state_listbox.curselection()
        if not selected:
            messagebox.showinfo("No Selection", "Kisi item ko select karein.", parent=self.winfo_toplevel())
            return

        names = [self.state_listbox.get(i) for i in selected]
        type_label = self.state_type_var.get()
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Kya aap ye {len(names)} {type_label}(s) delete karna chahte hain?\n\n"
            + "\n".join(f"  • {n}" for n in names) +
            f"\n\nYe ab {type_label} field mein suggestion nahi aayenge.",
            parent=self.winfo_toplevel()
        )
        if not confirm:
            return

        keys = self._get_current_state_keys()
        hm = self.app.history_manager
        for name in names:
            for key in keys:
                hm.remove_entry(key, name)

        self.app.play_sound("success")
        self._refresh_state_list()
        messagebox.showinfo("Deleted", f"{len(names)} {type_label}(s) delete kar diye gaye.", parent=self.winfo_toplevel())

    def _add_state_value(self) -> None:
        """Add a new value to all relevant history keys (auto-uppercased)."""
        name = self.add_state_entry.get().strip().upper()
        if not name:
            messagebox.showinfo("No Input", "Kuch likhein.", parent=self.winfo_toplevel())
            return

        keys = self._get_current_state_keys()
        hm = self.app.history_manager
        saved_count = 0
        for key in keys:
            try:
                hm.save_entry(key, name)
                saved_count += 1
            except Exception:
                pass

        self.add_state_entry.delete(0, "end")
        self.app.play_sound("success")
        self._refresh_state_list()
        type_label = self.state_type_var.get()
        messagebox.showinfo(
            "Added",
            f"'{name}' add kar diya gaya.\nAb ye sabhi automation tabs mein suggestion ke roop mein dikhega.",
            parent=self.winfo_toplevel()
        )

    # ════════════════════════════════════════════════════════════════
    # TAB 3: STAFF MAPPING
    # ════════════════════════════════════════════════════════════════
    def _build_mapping_tab(self) -> None:
        container = self.tab_mapping
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Info + tab selector
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="💡 Har panchayat ke liye staff/mate ka naam save ho jata hai jab aap automation chalate hain. "
                 "Yahan aap dekh aur update kar sakte hain.",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Mapping type selector
        type_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        type_frame.pack(fill="x")

        self.mapping_type_var = ctk.StringVar(value="MR Staff")
        self.mapping_type_menu = ctk.CTkSegmentedButton(
            type_frame,
            values=["MR Staff", "MB Mate"],
            variable=self.mapping_type_var,
            command=self._on_mapping_type_change,
        )
        self.mapping_type_menu.pack(side="left")

        ctk.CTkButton(
            type_frame, text="🔄 Refresh", width=90, height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"),
            hover_color=("#CBD5E1", "#475569"),
            command=self._refresh_mapping_list,
        ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            type_frame, text="💾 Save Changes", height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#DBEAFE", "#1E3A5F"),
            text_color=("#1D4ED8", "#60A5FA"),
            hover_color=("#BFDBFE", "#1E40AF"),
            command=self._save_current_mapping,
        ).pack(side="right", padx=(5, 0))

        # Main content: treeview + edit panel
        content = ctk.CTkFrame(container, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        # Left: mapping list
        list_frame = ctk.CTkFrame(content, fg_color="transparent")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            list_frame, text="Panchayat → Staff/Mate Mapping",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Treeview for mapping
        style = ttk.Style()
        style.theme_use("clam")
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            tv_bg, tv_fg, tv_sel = "#2b2b2b", "#e5e7eb", "#3B82F6"
            tv_hdr_bg, tv_hdr_fg = "#1f2937", "#ffffff"
        else:
            tv_bg, tv_fg, tv_sel = "#ffffff", "#374151", "#3B82F6"
            tv_hdr_bg, tv_hdr_fg = "#f9fafb", "#111827"

        style.configure("Mapping.Treeview",
                        background=tv_bg, foreground=tv_fg,
                        fieldbackground=tv_bg, rowheight=28,
                        font=("Segoe UI", 11), borderwidth=0)
        style.map("Mapping.Treeview",
                  background=[('selected', tv_sel)], foreground=[('selected', 'white')])
        style.configure("Mapping.Treeview.Heading",
                        background=tv_hdr_bg, foreground=tv_hdr_fg,
                        relief="flat", font=("Segoe UI", 11, "bold"))

        columns = ("panchayat", "staff")
        self.mapping_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings",
            style="Mapping.Treeview", selectmode="browse",
        )
        self.mapping_tree.grid(row=1, column=0, sticky="nsew")
        self.mapping_tree.heading("panchayat", text="Panchayat", anchor="w")
        self.mapping_tree.heading("staff", text="Staff / Mate Name", anchor="w")
        self.mapping_tree.column("panchayat", width=180, minwidth=120)
        self.mapping_tree.column("staff", width=250, minwidth=150)
        self.mapping_tree.bind("<<TreeviewSelect>>", self._on_mapping_select)

        v_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.mapping_tree.yview)
        v_scroll.grid(row=1, column=1, sticky="ns")
        self.mapping_tree.configure(yscrollcommand=v_scroll.set)

        # Right: edit panel
        edit_frame = ctk.CTkFrame(content, fg_color="transparent", width=300)
        edit_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        edit_frame.grid_columnconfigure(0, weight=1)
        edit_frame.grid_propagate(False)

        ctk.CTkLabel(
            edit_frame, text="✏️ Edit Mapping",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        ctk.CTkLabel(edit_frame, text="Panchayat Name:").grid(row=1, column=0, sticky="w")
        self.mapping_panchayat_entry = ctk.CTkEntry(edit_frame, font=ctk.CTkFont(size=12))
        self.mapping_panchayat_entry.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(edit_frame, text="Staff / Mate Name:").grid(row=3, column=0, sticky="w")
        self.mapping_staff_entry = ctk.CTkEntry(edit_frame, font=ctk.CTkFont(size=12))
        self.mapping_staff_entry.grid(row=4, column=0, sticky="ew", pady=(0, 15))

        btn_row = ctk.CTkFrame(edit_frame, fg_color="transparent")
        btn_row.grid(row=5, column=0, sticky="ew")

        ctk.CTkButton(
            btn_row, text="💾 Save", width=80, height=30,
            font=ctk.CTkFont(size=11),
            fg_color=("#DBEAFE", "#1E3A5F"),
            text_color=("#1D4ED8", "#60A5FA"),
            hover_color=("#BFDBFE", "#1E40AF"),
            command=self._save_current_mapping,
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            btn_row, text="🗑️ Delete", width=80, height=30,
            font=ctk.CTkFont(size=11),
            fg_color=("#FEE2E2", "#450A0A"),
            text_color=("#DC2626", "#F87171"),
            hover_color=("#FECACA", "#7F1D1D"),
            command=self._delete_selected_mapping,
        ).pack(side="left")

        # Load initial data
        self._current_mapping_file = None
        self._current_mapping_data = {}
        self._refresh_mapping_list()

    def _get_mapping_file_path(self) -> str:
        """Return the path to the current mapping file based on selected type."""
        if self.mapping_type_var.get() == "MR Staff":
            return get_data_path("mr_panchayat_staff_map.json")
        else:
            return get_data_path("mb_panchayat_mate_map.json")

    def _on_mapping_type_change(self, value: str) -> None:
        self._refresh_mapping_list()

    def _load_mapping_file(self) -> Dict[str, str]:
        path = self._get_mapping_file_path()
        self._current_mapping_file = path
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_mapping_file(self, data: Dict[str, str]) -> bool:
        if not self._current_mapping_file:
            return False
        try:
            with open(self._current_mapping_file, "w") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            logger.error("Failed to save mapping: %s", e)
            return False

    def _refresh_mapping_list(self) -> None:
        """Load mapping data and populate the treeview."""
        for item in self.mapping_tree.get_children():
            self.mapping_tree.delete(item)

        self._current_mapping_data = self._load_mapping_file()

        if not self._current_mapping_data:
            self.mapping_tree.insert("", "end", values=(
                "— No mappings found —",
                "Run automation first to save mappings"
            ))
            return

        for panchayat, staff in sorted(self._current_mapping_data.items()):
            self.mapping_tree.insert("", "end", values=(panchayat, staff))

    def _on_mapping_select(self, event) -> None:
        """When a mapping is selected, populate the edit fields."""
        sel = self.mapping_tree.selection()
        if not sel:
            return
        values = self.mapping_tree.item(sel[0], "values")
        if values and len(values) >= 2:
            self.mapping_panchayat_entry.delete(0, "end")
            self.mapping_panchayat_entry.insert(0, values[0])
            self.mapping_staff_entry.delete(0, "end")
            self.mapping_staff_entry.insert(0, values[1])

    def _save_current_mapping(self) -> None:
        """Save the currently edited mapping pair."""
        panchayat = self.mapping_panchayat_entry.get().strip().lower()
        staff = self.mapping_staff_entry.get().strip()

        if not panchayat or not staff:
            messagebox.showwarning("Input Error", "Dono fields bharo: Panchayat aur Staff/Mate Name.", parent=self.winfo_toplevel())
            return

        self._current_mapping_data[panchayat] = staff
        if self._save_mapping_file(self._current_mapping_data):
            self.app.play_sound("success")
            self._refresh_mapping_list()
            messagebox.showinfo("Saved", f"Mapping saved:\n{panchayat} → {staff}", parent=self.winfo_toplevel())
        else:
            self.app.play_sound("error")
            messagebox.showerror("Error", "Mapping save nahi ho paya.", parent=self.winfo_toplevel())

    def _delete_selected_mapping(self) -> None:
        """Delete the selected mapping entry."""
        sel = self.mapping_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Koi mapping select karein.", parent=self.winfo_toplevel())
            return

        values = self.mapping_tree.item(sel[0], "values")
        if not values or len(values) < 1:
            return

        panchayat_key = values[0].lower()

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Kya aap '{values[0]}' ki mapping delete karna chahte hain?",
            parent=self.winfo_toplevel()
        ):
            return

        if panchayat_key in self._current_mapping_data:
            del self._current_mapping_data[panchayat_key]
            if self._save_mapping_file(self._current_mapping_data):
                self.app.play_sound("success")
                self._refresh_mapping_list()
                self.mapping_panchayat_entry.delete(0, "end")
                self.mapping_staff_entry.delete(0, "end")
            else:
                self.app.play_sound("error")
                messagebox.showerror("Error", "Delete nahi ho paya.", parent=self.winfo_toplevel())

    # ════════════════════════════════════════════════════════════════
    # TAB 3: DEFAULT VALUES
    # ════════════════════════════════════════════════════════════════
    def _build_defaults_tab(self) -> None:
        container = self.tab_defaults
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            scroll, text="⚙️ Default Values for Automations",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(5, 15))

        row_num = [1]
        fields: List[Dict] = []

        def add_section(title: str):
            ctk.CTkLabel(
                scroll, text=title,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=("#2563EB", "#60A5FA"),
            ).grid(row=row_num[0], column=0, columnspan=3, sticky="w", padx=10, pady=(15, 5))
            row_num[0] += 1
            ctk.CTkFrame(
                scroll, height=1, corner_radius=0,
                fg_color=("gray85", "gray35"),
            ).grid(row=row_num[0], column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
            row_num[0] += 1

        def add_field(label: str, key: str, default: str, tooltip: str = "") -> ctk.CTkEntry:
            ctk.CTkLabel(
                scroll, text=label,
                font=ctk.CTkFont(size=13),
            ).grid(row=row_num[0], column=0, sticky="w", padx=15, pady=5)
            entry = ctk.CTkEntry(scroll, font=ctk.CTkFont(size=13), width=120)
            entry.insert(0, default)
            entry.grid(row=row_num[0], column=1, sticky="w", padx=10, pady=5)
            if tooltip:
                ctk.CTkLabel(
                    scroll, text=tooltip,
                    font=ctk.CTkFont(size=10),
                    text_color=("gray50", "gray60"),
                ).grid(row=row_num[0], column=2, sticky="w", padx=(5, 10), pady=5)
            fields.append({"key": key, "entry": entry})
            row_num[0] += 1
            return entry

        # ── eMB Entry Defaults ──
        add_section("📝 eMB Entry Defaults")
        mb_defaults = config.MB_ENTRY_CONFIG["defaults"]
        add_field("Unit Cost (₹):", "mb_unit_cost", mb_defaults["unit_cost"],
                  "Per-unit cost for work (₹ 300 w.e.f. April 2025)")
        add_field("Pit Count:", "mb_pit_count", mb_defaults["default_pit_count"],
                  "Default pit count for measurement")
        add_field("MB Page No.:", "mb_page_no", mb_defaults.get("page_no", ""),
                  "Default page number")
        add_field("JE Designation:", "mb_je_desig", mb_defaults.get("je_designation", "JE"))

        # ── eMB Verify Defaults ──
        add_section("🔍 eMB Verify Defaults")
        add_field("Verify Amount (₹):", "emb_verify_amt", "300",
                  "Amount se match nahi hua to reject. Now ₹ 300")

        # ── MSR Payment Defaults ──
        add_section("💳 MR Payment (MSR) Defaults")
        add_field("Verify Amount (₹):", "msr_verify_amt", "300",
                  "Wage per day amount to verify against. Now ₹ 300")

        # ── Add Activity Defaults ──
        add_section("🪄 Add Activity Defaults")
        add_field("Unit Price (₹):", "add_activity_price", config.ADD_ACTIVITY_CONFIG["defaults"]["unit_price"],
                  "Unit price for add activity (₹ 300 now)")
        add_field("Quantity:", "add_activity_qty", config.ADD_ACTIVITY_CONFIG["defaults"]["quantity"])

        # ── Buttons ──
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.grid(row=row_num[0], column=0, columnspan=3, sticky="w", padx=10, pady=(20, 10))
        row_num[0] += 1

        ctk.CTkButton(
            btn_row, text="💾 Save All to Files", height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#3B82F6", "#3B82F6"),
            text_color="white",
            hover_color=("#2563EB", "#2563EB"),
            command=self._save_all_defaults,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text="🔄 Reset to Defaults", height=36,
            font=ctk.CTkFont(size=13),
            fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"),
            hover_color=("#CBD5E1", "#475569"),
            command=self._reset_defaults_to_300,
        ).pack(side="left")

        # Store fields for later use
        self._defaults_fields = fields

        # Status label
        self.defaults_status = ctk.CTkLabel(
            scroll, text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        )
        self.defaults_status.grid(row=row_num[0], column=0, columnspan=3, sticky="w", padx=10, pady=(5, 0))

    def _save_all_defaults(self) -> None:
        """Save default values to input JSON files and config defaults."""
        saved_count = 0

        for field in self._defaults_fields:
            key = field["key"]
            value = field["entry"].get().strip()
            if not value:
                continue

            try:
                if key == "mb_unit_cost":
                    self._save_tab_input("mb_entry_inputs.json", "unit_cost", value)
                    saved_count += 1
                elif key == "mb_pit_count":
                    self._save_tab_input("mb_entry_inputs.json", "default_pit_count", value)
                    saved_count += 1
                elif key == "mb_page_no":
                    self._save_tab_input("mb_entry_inputs.json", "page_no", value)
                    saved_count += 1
                elif key == "mb_je_desig":
                    self._save_tab_input("mb_entry_inputs.json", "je_designation", value)
                    saved_count += 1
                elif key == "emb_verify_amt":
                    self._save_tab_input("emb_verify_inputs.json", "verify_amount", value)
                    saved_count += 1
                elif key == "msr_verify_amt":
                    # MSR reads from file saved per tab context
                    self._save_tab_input("msr_inputs.json", "verify_amount", value)
                    saved_count += 1
                elif key == "add_activity_price":
                    self._save_tab_input("add_activity_inputs.json", "unit_price", value)
                    saved_count += 1
                elif key == "add_activity_qty":
                    self._save_tab_input("add_activity_inputs.json", "quantity", value)
                    saved_count += 1
            except Exception:
                pass

        self.app.play_sound("success")
        self.defaults_status.configure(
            text=f"✅ {saved_count} default value(s) saved. Agli baar automation mein naye values dikhenge."
        )

    def _save_tab_input(self, filename: str, field_key: str, value: str) -> None:
        """Save a single field value into a tab's input JSON file."""
        filepath = get_data_path(filename)
        data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        data[field_key] = value
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)

    def _reset_defaults_to_300(self) -> None:
        """Reset all default values to ₹300 (current labour rate)."""
        if not messagebox.askyesno(
            "Reset Defaults",
            "Sabhi default values ₹ 300 par reset ho jayenge?\n\n"
            "(Unit Cost, Verify Amount, Unit Price sab ₹ 300 ho jayenge)",
            parent=self.winfo_toplevel()
        ):
            return

        # Update all entry fields
        for field in self._defaults_fields:
            entry = field["entry"]
            key = field["key"]
            if "cost" in key or "price" in key or "amt" in key or key == "mb_unit_cost":
                entry.delete(0, "end")
                entry.insert(0, "300")
            elif key == "mb_pit_count":
                entry.delete(0, "end")
                entry.insert(0, "112")
            elif key == "mb_page_no":
                entry.delete(0, "end")
                entry.insert(0, "1")
            elif key == "mb_je_desig":
                entry.delete(0, "end")
                entry.insert(0, "JE")

        self.app.play_sound("success")
        self.defaults_status.configure(
            text="✅ Defaults reset to ₹ 300. 'Save All to Files' dabayein to save ho jayega."
        )
