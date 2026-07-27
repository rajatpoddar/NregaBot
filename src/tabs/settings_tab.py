# tabs/settings_tab.py
"""
Settings Tab — NREGA Bot Settings.

Merged tabs:
  1. 🗺️ Location Data — Panchayat / State / District / Block in one place
  2. 👥 Staff Mapping — Panchayat-based dropdown, gated if no data
  3. ⚙️ Default Values — Persists correctly across restarts
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
from .autocomplete_widget import AutocompleteEntry
from src.location_hierarchy import get_hierarchy, HIERARCHY_TYPES, TYPE_TO_PREFIX

logger = get_logger()


class SettingsTab(ctk.CTkFrame):
    """Settings dashboard — 3 streamlined tabs."""

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self._tracker = AfterTracker(self)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()

        self.tab_view = ctk.CTkTabview(self, corner_radius=8,
                                         command=self._on_tab_changed)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 20))

        self.tab_location  = self.tab_view.add("  🗺️  Location Data  ")
        self.tab_mapping   = self.tab_view.add("  👥  Staff Mapping  ")
        self.tab_defaults  = self.tab_view.add("  ⚙️  Default Values  ")

        self._build_location_tab()
        self._build_mapping_tab()
        self._build_defaults_tab()

    # ────────────────────────────────────────────────────────────────
    # HEADER
    # ────────────────────────────────────────────────────────────────
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="⚙️", font=ctk.CTkFont(size=28)
                     ).grid(row=0, column=0, padx=(0, 12))
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(title_frame, text="Settings",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame,
                     text="Manage saved data, staff mappings, and default values",
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray60")).pack(anchor="w")

    # ════════════════════════════════════════════════════════════════
    # TAB 1: LOCATION DATA — Panchayat / State / District / Block / Village
    # ════════════════════════════════════════════════════════════════
    def _build_location_tab(self) -> None:
        c = self.tab_location
        c.grid_rowconfigure(5, weight=1)
        c.grid_columnconfigure(0, weight=1)

        # Info banner
        info = ctk.CTkFrame(c, fg_color=("gray95", "gray25"), corner_radius=8)
        info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ctk.CTkLabel(info,
            text="💡 Yahan aap State, District, Block, Panchayat aur Village ke naam add/delete kar sakte hain. "
                 "Ye sabhi automation tabs mein dropdown mein dikhenge.",
            font=ctk.CTkFont(size=12), text_color=("gray40", "gray80"),
            wraplength=700, justify="left",
        ).pack(padx=15, pady=10)

        # ── Type selector ──
        type_frame = ctk.CTkFrame(c, fg_color="transparent")
        type_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))
        type_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(type_frame, text="Type:", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=(5, 10))
        self.loc_type_var = ctk.StringVar(value="State")
        self.loc_type_menu = ctk.CTkSegmentedButton(
            type_frame, values=["State", "District", "Block", "Panchayat", "Village"],
            variable=self.loc_type_var, command=self._on_loc_type_change,
        )
        self.loc_type_menu.grid(row=0, column=1, sticky="w", padx=(0, 10))

        # ── Parent selector (for child types: District, Block, Panchayat, Village) ──
        self.loc_parent_frame = ctk.CTkFrame(c, fg_color="transparent")
        self.loc_parent_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 2))
        self.loc_parent_frame.grid_columnconfigure(1, weight=1)

        self.loc_parent_label = ctk.CTkLabel(self.loc_parent_frame,
            text="Under:", font=ctk.CTkFont(size=12, weight="bold"))
        self.loc_parent_label.grid(row=0, column=0, sticky="w", padx=(5, 10))

        self.loc_parent_dropdown = AutocompleteEntry(
            self.loc_parent_frame, suggestions_list=[],
            width=200, height=28,
            show_settings_option=False,
        )
        self.loc_parent_dropdown.grid(row=0, column=1, sticky="w", padx=(0, 10))

        # ── Add new ──
        add_frame = ctk.CTkFrame(c, fg_color="transparent")
        add_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(3, 5))
        add_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(add_frame, text="➕ Add New:", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=(5, 10))
        self.add_loc_entry = ctk.CTkEntry(add_frame,
            placeholder_text="Naam likhein (e.g., JHARKHAND)...", font=ctk.CTkFont(size=13))
        self.add_loc_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.add_loc_entry.bind("<Return>", lambda e: self._add_loc_value())
        ctk.CTkButton(add_frame, text="➕ Add", width=70, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#16A34A", "#16A34A"), text_color="white",
            hover_color=("#15803D", "#15803D"),
            command=self._add_loc_value).grid(row=0, column=2, sticky="w", padx=(0, 5))

        # ── Toolbar ──
        toolbar = ctk.CTkFrame(c, fg_color="transparent")
        toolbar.grid(row=4, column=0, sticky="ew", padx=10, pady=(2, 5))
        toolbar.grid_columnconfigure(0, weight=1)
        self.loc_count_label = ctk.CTkLabel(toolbar, text="", font=ctk.CTkFont(size=12),
                                             text_color=("gray50", "gray60"))
        self.loc_count_label.pack(side="left")
        ctk.CTkButton(toolbar, text="🔄 Refresh", width=90, height=28,
            font=ctk.CTkFont(size=11), fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"), hover_color=("#CBD5E1", "#475569"),
            command=self._refresh_loc_list).pack(side="right", padx=(5, 0))
        ctk.CTkButton(toolbar, text="🗑️ Delete Selected", height=28,
            font=ctk.CTkFont(size=11), fg_color=("#FEE2E2", "#450A0A"),
            text_color=("#DC2626", "#F87171"), hover_color=("#FECACA", "#7F1D1D"),
            command=self._delete_selected_loc).pack(side="right", padx=(5, 0))

        # ── Listbox ──
        lc = ctk.CTkFrame(c, fg_color="transparent")
        lc.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 10))
        lc.grid_rowconfigure(0, weight=1)
        lc.grid_columnconfigure(0, weight=1)
        bc = self._resolve_color(("#CBD5E1", "#475569"))
        self.loc_listbox = tkinter.Listbox(lc, selectmode=tkinter.EXTENDED,
            font=("Segoe UI", 12), bg=self._get_listbox_bg(), fg=self._get_listbox_fg(),
            selectbackground="#3B82F6", selectforeground="white",
            borderwidth=0, highlightthickness=1,
            highlightcolor=bc, highlightbackground=bc)
        self.loc_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ctk.CTkScrollbar(lc, command=self.loc_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.loc_listbox.configure(yscrollcommand=scrollbar.set)
        self.loc_listbox.bind("<Double-1>", lambda e: self._delete_selected_loc())
        self.loc_listbox.bind("<Delete>", lambda e: self._delete_selected_loc())
        self._refresh_loc_list()

    # ── Helpers ──
    LISTBOX_FG_LIGHT = "#374151"
    LISTBOX_FG_DARK  = "#e5e7eb"
    LISTBOX_BG_LIGHT = "#ffffff"
    LISTBOX_BG_DARK  = "#2b2b2b"

    def _get_listbox_bg(self) -> str:
        return self.LISTBOX_BG_DARK if ctk.get_appearance_mode() == "Dark" else self.LISTBOX_BG_LIGHT
    def _get_listbox_fg(self) -> str:
        return self.LISTBOX_FG_DARK if ctk.get_appearance_mode() == "Dark" else self.LISTBOX_FG_LIGHT

    @staticmethod
    def _resolve_color(t: tuple) -> str:
        return t[1] if ctk.get_appearance_mode() == "Dark" else t[0]

    def _get_loc_keys(self) -> list:
        t = self.loc_type_var.get()
        if t == "Panchayat":
            return ["location_panchayat", "panchayat_name", "panchayat",
                    "dashboard_panchayat", "mr_track_panchayat",
                    "issued_mr_panchayat", "audit_panchayat_respond"]
        elif t == "State":
            return ["location_state", "mr_track_state", "issued_mr_state",
                    "mis_state", "dashboard_state"]
        elif t == "District":
            return ["location_district", "mr_track_district", "issued_mr_district",
                    "mis_district", "dashboard_district"]
        elif t == "Village":
            return ["location_village", "village_name"]
        else:  # Block
            return ["location_block", "mr_track_block", "issued_mr_block",
                    "mis_block", "dashboard_block"]

    def _get_parent_options(self) -> list:
        """Get parent names — from hierarchy + history fallback."""
        t = self.loc_type_var.get()
        hier = get_hierarchy()
        parent_type = hier.get_parent_type(t)
        if not parent_type:
            return []
        parent_names = hier.get_parent_names(t)
        hm = self.app.history_manager
        parent_key = f"location_{TYPE_TO_PREFIX[parent_type].lower()}"
        for s in hm.get_suggestions(parent_key):
            if s not in parent_names:
                parent_names.append(s)
        return parent_names

    def _on_loc_type_change(self, selected_type: str):
        """When the type selector changes, show/hide the parent dropdown and refresh list."""
        hier = get_hierarchy()
        parent_type = hier.get_parent_type(selected_type)
        if parent_type:
            self.loc_parent_frame.grid()
            parent_names = self._get_parent_options()
            self.loc_parent_dropdown.suggestions = parent_names
            self.loc_parent_dropdown._update_display()
            self.loc_parent_dropdown.delete(0)
        else:
            self.loc_parent_frame.grid_remove()
        self._refresh_loc_list()

    def _refresh_loc_list(self) -> None:
        self.loc_listbox.delete(0, "end")
        keys = self._get_loc_keys()
        hm = self.app.history_manager
        vals = set()
        for k in keys:
            for s in hm.get_suggestions(k):
                vals.add(s)
        sv = sorted(vals)
        for v in sv:
            self.loc_listbox.insert("end", v)
        t = self.loc_type_var.get()
        self.loc_count_label.configure(text=f"Total {t}(s): {len(sv)}")

    def _add_loc_value(self) -> None:
        name = self.add_loc_entry.get().strip().upper()
        if not name:
            messagebox.showinfo("No Input", "Kuch likhein.", parent=self.winfo_toplevel())
            return

        t = self.loc_type_var.get()
        hier = get_hierarchy()
        parent_type = hier.get_parent_type(t)

        # If this type has a parent, check that parent is selected
        if parent_type:
            parent_name = self.loc_parent_dropdown.get().strip()
            if not parent_name:
                messagebox.showwarning("Parent Required",
                    f"Pehle '{parent_type}' select karein jiske under '{t}' add karna hai.",
                    parent=self.winfo_toplevel())
                return
            # Save hierarchy relationship
            hier.add_child(parent_type, parent_name, t, name)

        keys = self._get_loc_keys()
        hm = self.app.history_manager
        for k in keys:
            try:
                hm.save_entry(k, name)
            except Exception:
                pass
        self.add_loc_entry.delete(0, "end")

        # Refresh list only — preserve parent dropdown selection for fast sequential adds
        self._refresh_loc_list()

        # Refresh parent dropdown suggestions (newly added parent won't appear in child's list yet)
        if parent_type:
            self.loc_parent_dropdown.suggestions = self._get_parent_options()
            self.loc_parent_dropdown._update_display()

        messagebox.showinfo("Added",
            f"'{name}' add kar diya gaya.\nAb ye sabhi automation tabs mein dikhega.",
            parent=self.winfo_toplevel())

    def _delete_selected_loc(self) -> None:
        sel = self.loc_listbox.curselection()
        if not sel:
            messagebox.showinfo("No Selection", "Kisi item ko select karein.", parent=self.winfo_toplevel())
            return
        names = [self.loc_listbox.get(i) for i in sel]
        t = self.loc_type_var.get()
        if not messagebox.askyesno("Confirm Delete",
            f"Kya aap ye {len(names)} {t}(s) delete karna chahte hain?\n\n"
            + "\n".join(f"  • {n}" for n in names)
            + f"\n\nYe ab {t} field mein suggestion nahi aayenge.",
            parent=self.winfo_toplevel()):
            return
        keys = self._get_loc_keys()
        hm = self.app.history_manager
        hier = get_hierarchy()
        for name in names:
            for k in keys:
                hm.remove_entry(k, name)
            # Also remove hierarchy relationships
            parent_type = hier.get_parent_type(t)
            if parent_type:
                parent_name = self.loc_parent_dropdown.get().strip()
                if parent_name:
                    hier.remove_child(parent_type, parent_name, t, name)
            # Remove children from hierarchy
            child_type = hier.get_child_type(t)
            if child_type:
                hier.remove_all_children_of(t, name)
        self._on_loc_type_change(t)
        messagebox.showinfo("Deleted", f"{len(names)} {t}(s) delete kar diye gaye.",
                            parent=self.winfo_toplevel())

    # ════════════════════════════════════════════════════════════════
    # TAB 2: STAFF MAPPING — Panchayat-based, gated
    # ════════════════════════════════════════════════════════════════
    def _build_mapping_tab(self) -> None:
        c = self.tab_mapping
        c.grid_rowconfigure(1, weight=1)
        c.grid_columnconfigure(0, weight=1)

        # Header with type selector
        header = ctk.CTkFrame(c, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ctk.CTkLabel(header,
            text="💡 Har panchayat ke liye staff/mate ka naam yahan set karein.",
            font=ctk.CTkFont(size=12), text_color=("gray50", "gray60"),
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        type_row = ctk.CTkFrame(header, fg_color="transparent")
        type_row.pack(fill="x")
        self.map_type_var = ctk.StringVar(value="MR Staff")
        self.map_type_menu = ctk.CTkSegmentedButton(
            type_row, values=["MR Staff", "MB Mate"],
            variable=self.map_type_var, command=self._refresh_map_panel,
        )
        self.map_type_menu.pack(side="left")

        # ── Main content area — match parent fg to avoid white flash ──
        bg = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        self.map_content = ctk.CTkFrame(c, fg_color=bg)
        self.map_content.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.map_content.grid_columnconfigure(0, weight=1)
        self.map_content.grid_rowconfigure(0, weight=1)

        self._refresh_map_panel()

    def _get_panchayat_suggestions(self) -> list:
        """Get all unique panchayat names from history."""
        hm = self.app.history_manager
        vals = set()
        for k in ["location_panchayat", "panchayat_name", "panchayat",
                   "dashboard_panchayat", "mr_track_panchayat",
                   "issued_mr_panchayat", "audit_panchayat_respond"]:
            for s in hm.get_suggestions(k):
                vals.add(s)
        return sorted(vals)

    def _get_map_file_path(self) -> str:
        if self.map_type_var.get() == "MR Staff":
            return get_data_path("mr_panchayat_staff_map.json")
        return get_data_path("mb_panchayat_mate_map.json")

    def _load_map_data(self) -> Dict[str, str]:
        p = self._get_map_file_path()
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_map_data(self, data: Dict[str, str]) -> bool:
        p = self._get_map_file_path()
        try:
            with open(p, "w") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            logger.error("Failed to save mapping: %s", e)
            return False

    def _refresh_map_panel(self, *args) -> None:
        """Rebuild the mapping panel — always shows editor, even if panchayat list empty."""
        for w in self.map_content.winfo_children():
            w.destroy()

        self._show_map_editor(self._get_panchayat_suggestions())

    def _show_map_editor(self, panchayats: list) -> None:
        """Show the mapping editor with panchayat dropdown + staff field.
        If panchayats list is empty, the dropdown will simply show its empty-state
        message ("Set in Settings") — user can still manually type or set later.
        """
        editor = ctk.CTkFrame(self.map_content, fg_color="transparent")
        editor.pack(fill="both", expand=True, padx=5, pady=5)
        editor.grid_columnconfigure(0, weight=1)
        editor.grid_rowconfigure(3, weight=1)

        # ── Panchayat dropdown ──
        row0 = ctk.CTkFrame(editor, fg_color="transparent")
        row0.grid(row=0, column=0, sticky="ew", pady=(5, 5))
        row0.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row0, text="🏘️  Panchayat:",
                      font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=(5, 10))

        self.map_panchayat_dropdown = AutocompleteEntry(
            row0, suggestions_list=panchayats,
            app_instance=self.app, history_key="location_panchayat",
        )
        self.map_panchayat_dropdown.grid(row=0, column=1, sticky="ew", padx=(0, 5))

        # ── Staff name ──
        row1 = ctk.CTkFrame(editor, fg_color="transparent")
        row1.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        row1.grid_columnconfigure(1, weight=1)

        type_label = self.map_type_var.get()
        ctk.CTkLabel(row1, text=f"👤  {type_label} Name:",
                      font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=(5, 10))

        self.map_staff_entry = ctk.CTkEntry(row1, font=ctk.CTkFont(size=13),
                                             placeholder_text=f"Enter {type_label} name...")
        self.map_staff_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))

        # ── Action buttons ──
        btn_row = ctk.CTkFrame(editor, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        btn_row.grid_columnconfigure(0, weight=1)

        self.map_status_label = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=11),
                                              text_color=("gray50", "gray60"))
        self.map_status_label.pack(side="left", padx=(5, 10))

        ctk.CTkButton(btn_row, text="💾 Save", width=90, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#16A34A", "#16A34A"), text_color="white",
            hover_color=("#15803D", "#15803D"),
            command=self._save_map_entry).pack(side="right", padx=(5, 0))

        ctk.CTkButton(btn_row, text="🗑️ Delete", width=90, height=32,
            font=ctk.CTkFont(size=12), fg_color=("#FEE2E2", "#450A0A"),
            text_color=("#DC2626", "#F87171"), hover_color=("#FECACA", "#7F1D1D"),
            command=self._delete_map_entry).pack(side="right", padx=(5, 0))

        ctk.CTkButton(btn_row, text="🔄 Load", width=90, height=32,
            font=ctk.CTkFont(size=12), fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"), hover_color=("#CBD5E1", "#475569"),
            command=self._load_map_entry).pack(side="right", padx=(5, 0))

        # ── List of existing mappings ──
        list_frame = ctk.CTkFrame(editor, fg_color="transparent")
        list_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_frame, text="📋  Existing Mappings:",
                      font=ctk.CTkFont(size=12, weight="bold"),
                     ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.map_tree = ttk.Treeview(list_frame, columns=("panchayat", "staff"),
                                      show="headings", selectmode="browse")
        self.map_tree.grid(row=1, column=0, sticky="nsew")
        self.map_tree.heading("panchayat", text="Panchayat", anchor="w")
        self.map_tree.heading("staff", text="Staff / Mate Name", anchor="w")
        self.map_tree.column("panchayat", width=180, minwidth=120)
        self.map_tree.column("staff", width=250, minwidth=150)
        self.map_tree.bind("<<TreeviewSelect>>", self._on_map_tree_select)

        vs = ttk.Scrollbar(list_frame, orient="vertical", command=self.map_tree.yview)
        vs.grid(row=1, column=1, sticky="ns")
        self.map_tree.configure(yscrollcommand=vs.set)

        self._refresh_map_tree()

    def _refresh_map_tree(self) -> None:
        for item in self.map_tree.get_children():
            self.map_tree.delete(item)
        data = self._load_map_data()
        if not data:
            self.map_tree.insert("", "end", values=("— No mappings —", "Add one above"))
            return
        for p, s in sorted(data.items()):
            self.map_tree.insert("", "end", values=(p, s))

    def _on_map_tree_select(self, event) -> None:
        sel = self.map_tree.selection()
        if not sel:
            return
        vals = self.map_tree.item(sel[0], "values")
        if vals and len(vals) >= 2:
            self.map_staff_entry.delete(0, "end")
            self.map_staff_entry.insert(0, vals[1])
            # Set panchayat via insert for compatibility
            self.map_panchayat_dropdown.delete(0)
            self.map_panchayat_dropdown.insert(0, vals[0])

    def _get_current_map_panchayat(self) -> str:
        return self.map_panchayat_dropdown.get().strip()

    def _save_map_entry(self) -> None:
        panch = self._get_current_map_panchayat()
        staff = self.map_staff_entry.get().strip()
        if not panch or not staff:
            messagebox.showwarning("Input Error", "Dono fields bharo: Panchayat aur Staff/Mate Name.",
                                   parent=self.winfo_toplevel())
            return
        data = self._load_map_data()
        data[panch] = staff
        if self._save_map_data(data):
            self._refresh_map_tree()
            self.map_status_label.configure(text=f"✅ Saved: {panch} → {staff}",
                                            text_color=("#16A34A", "#4ADE80"))
        else:
            self.map_status_label.configure(text="❌ Save failed", text_color=("#DC2626", "#F87171"))

    def _delete_map_entry(self) -> None:
        panch = self._get_current_map_panchayat()
        if not panch:
            messagebox.showinfo("No Selection", "Pehle ek panchayat select karein.",
                                parent=self.winfo_toplevel())
            return
        data = self._load_map_data()
        if panch not in data:
            messagebox.showinfo("Not Found", f"'{panch}' ke liye koi mapping nahi mili.",
                                parent=self.winfo_toplevel())
            return
        if not messagebox.askyesno("Confirm Delete",
            f"Kya aap '{panch}' ki mapping delete karna chahte hain?",
            parent=self.winfo_toplevel()):
            return
        del data[panch]
        if self._save_map_data(data):
            self._refresh_map_tree()
            self.map_panchayat_dropdown.delete(0)
            self.map_staff_entry.delete(0, "end")
            self.map_status_label.configure(text=f"🗑️ Deleted: {panch}",
                                            text_color=("gray50", "gray60"))
        else:
            self.map_status_label.configure(text="❌ Delete failed", text_color=("#DC2626", "#F87171"))

    def _load_map_entry(self) -> None:
        """Load the current mapping for the selected panchayat."""
        panch = self._get_current_map_panchayat()
        if not panch:
            messagebox.showinfo("No Selection", "Pehle ek panchayat select karein.",
                                parent=self.winfo_toplevel())
            return
        data = self._load_map_data()
        if panch in data:
            self.map_staff_entry.delete(0, "end")
            self.map_staff_entry.insert(0, data[panch])
            self.map_status_label.configure(text=f"📂 Loaded: {panch} → {data[panch]}",
                                            text_color=("#2563EB", "#60A5FA"))
        else:
            self.map_staff_entry.delete(0, "end")
            self.map_status_label.configure(text=f"ℹ️ No mapping for '{panch}'",
                                            text_color=("gray50", "gray60"))

    def _on_tab_changed(self) -> None:
        """Refresh Staff Mapping panel only when that tab gains focus.
        CTkTabview.command() is called WITHOUT the tab name, so read from .get()."""
        if "Staff Mapping" in self.tab_view.get():
            self._refresh_map_panel()

    # ════════════════════════════════════════════════════════════════
    # TAB 3: DEFAULT VALUES — Fixed persistence
    # ════════════════════════════════════════════════════════════════
    def _build_defaults_tab(self) -> None:
        c = self.tab_defaults
        c.grid_rowconfigure(0, weight=1)
        c.grid_columnconfigure(0, weight=1)

        # Use theme's default frame bg for scroll container to prevent white flash
        bg = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        scroll = ctk.CTkScrollableFrame(c, fg_color=bg)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(scroll, text="⚙️ Default Values for Automations",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(5, 15))

        row_num = [1]
        fields: List[Dict] = []

        def add_section(title: str):
            ctk.CTkLabel(scroll, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=("#2563EB", "#60A5FA"),
                         ).grid(row=row_num[0], column=0, columnspan=3, sticky="w", padx=10, pady=(15, 5))
            row_num[0] += 1
            ctk.CTkFrame(scroll, height=1, corner_radius=0,
                         fg_color=("gray85", "gray35"),
                         ).grid(row=row_num[0], column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
            row_num[0] += 1

        def _load_saved(filename: str, field_key: str, fallback: str) -> str:
            """Load a value from a saved JSON file, falling back to given default."""
            fp = get_data_path(filename)
            if os.path.exists(fp):
                try:
                    with open(fp, "r") as f:
                        d = json.load(f)
                    return str(d.get(field_key, fallback))
                except Exception:
                    pass
            return fallback

        def add_field(label: str, key: str, filename: str, file_field: str,
                      fallback: str, tooltip: str = "") -> ctk.CTkEntry:
            val = _load_saved(filename, file_field, fallback)
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=13),
                         ).grid(row=row_num[0], column=0, sticky="w", padx=15, pady=5)
            entry = ctk.CTkEntry(scroll, font=ctk.CTkFont(size=13), width=120)
            entry.insert(0, val)
            entry.grid(row=row_num[0], column=1, sticky="w", padx=10, pady=5)
            if tooltip:
                ctk.CTkLabel(scroll, text=tooltip, font=ctk.CTkFont(size=10),
                             text_color=("gray50", "gray60"),
                             ).grid(row=row_num[0], column=2, sticky="w", padx=(5, 10), pady=5)
            fields.append({"key": key, "entry": entry, "filename": filename, "field": file_field})
            row_num[0] += 1
            return entry

        # ── eMB Entry Defaults ──
        mb_def = config.MB_ENTRY_CONFIG["defaults"]
        add_section("📝 eMB Entry Defaults")
        add_field("Unit Cost (₹):", "mb_unit_cost", "mb_entry_inputs.json", "unit_cost",
                  mb_def["unit_cost"], "Per-unit cost for work (₹ 300 w.e.f. April 2025)")
        add_field("Pit Count:", "mb_pit_count", "mb_entry_inputs.json", "default_pit_count",
                  mb_def["default_pit_count"], "Default pit count for measurement")
        add_field("MB Page No.:", "mb_page_no", "mb_entry_inputs.json", "page_no",
                  mb_def.get("page_no", ""), "Default page number")
        add_field("JE Designation:", "mb_je_desig", "mb_entry_inputs.json", "je_designation",
                  mb_def.get("je_designation", "JE"))

        # ── eMB Verify Defaults ──
        add_section("🔍 eMB Verify Defaults")
        add_field("Verify Amount (₹):", "emb_verify_amt", "emb_verify_inputs.json", "verify_amount",
                  "300", "Amount se match nahi hua to reject")

        # ── MSR Payment Defaults ──
        add_section("💳 MR Payment (MSR) Defaults")
        add_field("Verify Amount (₹):", "msr_verify_amt", "msr_inputs.json", "verify_amount",
                  "300", "Wage per day amount to verify against")

        # ── Add Activity Defaults ──
        add_def = config.ADD_ACTIVITY_CONFIG["defaults"]
        add_section("🪄 Add Activity Defaults")
        add_field("Unit Price (₹):", "add_activity_price", "add_activity_inputs.json", "unit_price",
                  add_def["unit_price"], "Unit price for add activity (₹ 300 now)")
        add_field("Quantity:", "add_activity_qty", "add_activity_inputs.json", "quantity",
                  add_def["quantity"])

        # ── Buttons ──
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.grid(row=row_num[0], column=0, columnspan=3, sticky="w", padx=10, pady=(20, 10))
        row_num[0] += 1

        ctk.CTkButton(btn_row, text="💾 Save All to Files", height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#3B82F6", "#3B82F6"), text_color="white",
            hover_color=("#2563EB", "#2563EB"),
            command=self._save_all_defaults).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="🔄 Reset to Defaults", height=36,
            font=ctk.CTkFont(size=13), fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"), hover_color=("#CBD5E1", "#475569"),
            command=self._reset_defaults).pack(side="left")

        self._defaults_fields = fields
        self.defaults_status = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=11),
                                             text_color=("gray50", "gray60"))
        self.defaults_status.grid(row=row_num[0], column=0, columnspan=3, sticky="w", padx=10, pady=(5, 0))

    def _save_tab_input(self, filename: str, field_key: str, value: str) -> None:
        fp = get_data_path(filename)
        data = {}
        if os.path.exists(fp):
            try:
                with open(fp, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[field_key] = value
        with open(fp, "w") as f:
            json.dump(data, f, indent=4)

    def _save_all_defaults(self) -> None:
        saved = 0
        for f in self._defaults_fields:
            val = f["entry"].get().strip()
            if not val:
                continue
            self._save_tab_input(f["filename"], f["field"], val)
            saved += 1
        self.defaults_status.configure(
            text=f"✅ {saved} default value(s) saved — ab aur agli baar bhi yaad rahega."
        )

    def _reset_defaults(self) -> None:
        if not messagebox.askyesno("Reset Defaults",
            "Sabhi default values ₹ 300 par reset ho jayenge?\n\n"
            "(Unit Cost, Verify Amount, Unit Price sab ₹ 300 ho jayenge)",
            parent=self.winfo_toplevel()):
            return
        for f in self._defaults_fields:
            e = f["entry"]
            k = f["key"]
            if "cost" in k or "price" in k or "amt" in k or k == "mb_unit_cost":
                e.delete(0, "end"); e.insert(0, "300")
            elif k == "mb_pit_count":
                e.delete(0, "end"); e.insert(0, "112")
            elif k == "mb_page_no":
                e.delete(0, "end"); e.insert(0, "1")
            elif k == "mb_je_desig":
                e.delete(0, "end"); e.insert(0, "JE")
        self.defaults_status.configure(
            text="✅ Defaults reset to ₹ 300. 'Save All to Files' dabayein to save ho jayega."
        )
