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
import re
import tkinter
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

import customtkinter as ctk

from src import config
from src.utils import get_data_path, get_logger, get_config, save_config
from src.ui_components import AfterTracker
from src.location_hierarchy import get_hierarchy, HIERARCHY_TYPES, TYPE_TO_PREFIX
from src.tabs.activity_log_tab import ActivityLogTab

# Selenium imports (used in _scrape_from_website)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

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
        self.tab_activity  = self.tab_view.add("  📋 Activity Log  ")
        self.tab_factory   = self.tab_view.add("  🏭  Factory Reset  ")

        self._build_location_tab()
        self._build_mapping_tab()
        self._build_defaults_tab()
        self._build_activity_log_tab()
        self._build_factory_reset_tab()

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
    # TAB 1: LOCATION DATA — Panchayat & Village
    # ════════════════════════════════════════════════════════════════
    def _build_location_tab(self) -> None:
        c = self.tab_location
        c.grid_rowconfigure(4, weight=1)
        c.grid_columnconfigure(0, weight=1)

        # Info banner
        info = ctk.CTkFrame(c, fg_color=("gray95", "gray25"), corner_radius=8)
        info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ctk.CTkLabel(info,
            text="💡 State, District aur Block server se auto-sync hote hain. Panchayat aur Village data 'Scrape from Website' "
                 "se fetch karein. Yahan sirf delete kar sakte hain — koi Panchayat delete karenge to uske villages bhi delete ho jayenge.",
            font=ctk.CTkFont(size=12), text_color=("gray40", "gray80"),
            wraplength=700, justify="left",
        ).pack(padx=15, pady=10)

        # ── Server Synced Data Card ──
        self._server_data_frame = ctk.CTkFrame(c, fg_color=("#F0FDF4", "#0F2A1D"), corner_radius=8,
                                                border_width=1, border_color=("#BBF7D0", "#166534"))
        self._server_data_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 2))
        self._server_data_frame.grid_columnconfigure(0, weight=1)

        # Header row
        srv_header = ctk.CTkFrame(self._server_data_frame, fg_color="transparent")
        srv_header.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(srv_header, text="☁️  Server Synced Data",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#166534", "#4ADE80")).pack(side="left")
        self._srv_status_label = ctk.CTkLabel(srv_header, text="",
                                                font=ctk.CTkFont(size=10),
                                                text_color=("gray50", "gray60"))
        self._srv_status_label.pack(side="right")

        # Values row (stored as instance var for easy refresh)
        self._srv_vals_frame = ctk.CTkFrame(self._server_data_frame, fg_color="transparent")
        self._srv_vals_frame.pack(fill="x", padx=12, pady=(2, 5))

        lic = self.app.license_info if hasattr(self.app, 'license_info') else {}
        srv_state = (lic.get('user_state') or '').strip().upper()
        srv_dist  = (lic.get('user_district') or '').strip().upper()
        srv_block = (lic.get('user_block') or '').strip().upper()

        def _srv_badge(parent, label, value):
            if not value:
                return
            badge = ctk.CTkFrame(parent, fg_color=("#DCFCE7", "#14532D"), corner_radius=6,
                                 border_width=1, border_color=("#86EFAC", "#22C55E"))
            badge.pack(side="left", padx=(0, 8), pady=2)
            ctk.CTkLabel(badge, text=f"  {label}: {value}  ",
                         font=ctk.CTkFont(size=11),
                         text_color=("#166534", "#86EFAC")).pack()

        if srv_state or srv_dist or srv_block:
            if srv_state:
                _srv_badge(self._srv_vals_frame, "🏛️", srv_state)
            if srv_dist:
                _srv_badge(self._srv_vals_frame, "📍", srv_dist)
            if srv_block:
                _srv_badge(self._srv_vals_frame, "📦", srv_block)
            ctk.CTkLabel(self._srv_vals_frame, text="✅ Auto-synced from your license",
                         font=ctk.CTkFont(size=10),
                         text_color=("#166534", "#86EFAC")).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkLabel(self._srv_vals_frame, text="ℹ️  Server par location data set nahi hai.",
                         font=ctk.CTkFont(size=11),
                         text_color=("gray50", "gray60")).pack(side="left")

        # Sync button row
        srv_btn_row = ctk.CTkFrame(self._server_data_frame, fg_color="transparent")
        srv_btn_row.pack(fill="x", padx=12, pady=(0, 8))

        self._srv_sync_btn = ctk.CTkButton(
            srv_btn_row, text="🔄 Sync Now", width=110, height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#16A34A", "#16A34A"), text_color="white",
            hover_color=("#15803D", "#15803D"),
            command=self._sync_from_server,
        )
        self._srv_sync_btn.pack(side="left")

        self._srv_sync_status = ctk.CTkLabel(srv_btn_row, text="",
                                               font=ctk.CTkFont(size=10),
                                               text_color=("gray50", "gray60"))
        self._srv_sync_status.pack(side="left", padx=(8, 0))

        # ── Scrape from Live Website Card ──
        self._scrape_frame = ctk.CTkFrame(c, fg_color=("#FFF7ED", "#1C1917"), corner_radius=8,
                                            border_width=1, border_color=("#FDBA74", "#9A3412"))
        self._scrape_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(3, 5))
        self._scrape_frame.grid_columnconfigure(0, weight=1)

        # Header
        sc_header = ctk.CTkFrame(self._scrape_frame, fg_color="transparent")
        sc_header.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(sc_header, text="🌐  Scrape from Live NREGA Website",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#9A3412", "#FDBA74")).pack(side="left")

        # Info note
        sc_note = ctk.CTkFrame(self._scrape_frame, fg_color="transparent")
        sc_note.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkLabel(sc_note,
            text="ℹ️  Pehle Login Automation se NREGA mein login karein, fir yahan 'Scrape Now' dabayein.\n"
                 "Bot automatically Demand page se Panchayat aur Village names scrape karega.",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60"),
            wraplength=650, justify="left",
        ).pack(anchor="w")

        # Button row
        sc_btn_row = ctk.CTkFrame(self._scrape_frame, fg_color="transparent")
        sc_btn_row.pack(fill="x", padx=12, pady=(2, 6))

        self._scrape_btn = ctk.CTkButton(sc_btn_row, text="🚀 Scrape Now", width=120, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#F97316", "#EA580C"), text_color="white",
            hover_color=("#EA580C", "#C2410C"),
            command=self._scrape_from_website,
        )
        self._scrape_btn.pack(side="left")

        self._scrape_status = ctk.CTkLabel(sc_btn_row, text="",
                                            font=ctk.CTkFont(size=10),
                                            text_color=("gray50", "gray60"))
        self._scrape_status.pack(side="left", padx=(8, 0))

        # ── Toolbar ──
        toolbar = ctk.CTkFrame(c, fg_color="transparent")
        toolbar.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 2))
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
        lc.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
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

    def _get_panchayat_keys(self) -> list:
        return ["location_panchayat", "panchayat_name", "panchayat",
                "dashboard_panchayat", "mr_track_panchayat",
                "issued_mr_panchayat", "audit_panchayat_respond"]

    def _get_village_keys(self) -> list:
        return ["location_village", "village_name"]

    def _refresh_loc_list(self) -> None:
        """Show Panchayat names in the list. Villages are shown under their parent when viewing hierarchy."""
        self.loc_listbox.delete(0, "end")
        hm = self.app.history_manager
        hier = get_hierarchy()
        
        panch_vals = set()
        for k in self._get_panchayat_keys():
            for s in hm.get_suggestions(k):
                panch_vals.add(s)
        
        # Show panchayats with their village count
        for p in sorted(panch_vals):
            villages = hier.get_children("Panchayat", p, "Village")
            v_count = len(villages)
            if v_count > 0:
                village_label = "village" if v_count == 1 else "villages"
                self.loc_listbox.insert("end", f"🏘️ {p}  ({v_count} {village_label})")
            else:
                self.loc_listbox.insert("end", f"🏘️ {p}")
        
        total_v = 0
        for k in self._get_village_keys():
            for s in hm.get_suggestions(k):
                total_v += 1
        
        self.loc_count_label.configure(text=f"🏘️ {len(panch_vals)} Panchayat(s)  |  🏠 {total_v} Village(s)")

    def _delete_selected_loc(self) -> None:
        sel = self.loc_listbox.curselection()
        if not sel:
            messagebox.showinfo("No Selection", "Kisi item ko select karein.", parent=self.winfo_toplevel())
            return
        raw_names = [self.loc_listbox.get(i) for i in sel]
        
        # Extract panchayat names from the display format "🏘️ NAME  (X villages)" or "🏘️ NAME"
        panch_names = []
        for n in raw_names:
            m = re.match(r'🏘️\s*(.+?)(?:\s*\(\d+ villages\))?$', n)
            if m:
                panch_names.append(m.group(1).strip())
            else:
                panch_names.append(n)
        
        if not messagebox.askyesno("Confirm Delete",
            f"Kya aap ye {len(panch_names)} Panchayat(s) delete karna chahte hain?\n\n"
            + "\n".join(f"  • {n}" for n in panch_names)
            + f"\n\n⚠️ Inke saath judi hui Villages bhi delete ho jayengi!",
            parent=self.winfo_toplevel()):
            return
        
        hm = self.app.history_manager
        hier = get_hierarchy()
        deleted_panch = 0
        deleted_vill = 0
        
        for name in panch_names:
            # 1. Get all villages under this panchayat from hierarchy
            villages = hier.get_children("Panchayat", name, "Village")
            
            # 2. Delete villages from history
            for v in villages:
                for k in self._get_village_keys():
                    hm.remove_entry(k, v)
                deleted_vill += 1
            
            # 3. Remove hierarchy relationships for villages
            hier.remove_all_children_of("Panchayat", name)
            
            # 4. Delete panchayat from history
            for k in self._get_panchayat_keys():
                hm.remove_entry(k, name)
            deleted_panch += 1
        
        self._refresh_loc_list()
        msg = f"{deleted_panch} Panchayat(s) delete kar diye gaye."
        if deleted_vill:
            msg += f"\n{deleted_vill} Village(s) bhi delete ho gaye."
        messagebox.showinfo("Deleted", msg, parent=self.winfo_toplevel())

    def _sync_from_server(self) -> None:
        """
        Server se user_state/user_district/user_block fetch karke
        local history manager mein save kare.
        """
        try:
            lic = self.app.license_info if hasattr(self.app, 'license_info') else {}
            state = (lic.get('user_state') or '').strip().upper()
            dist  = (lic.get('user_district') or '').strip().upper()
            block = (lic.get('user_block') or '').strip().upper()

            hm = self.app.history_manager
            synced = []

            if state:
                for k in ["location_state", "mr_track_state", "issued_mr_state",
                          "mis_state", "dashboard_state"]:
                    hm.save_entry(k, state)
                synced.append(f"State: {state}")
            if dist:
                for k in ["location_district", "mr_track_district", "issued_mr_district",
                          "mis_district", "dashboard_district"]:
                    hm.save_entry(k, dist)
                synced.append(f"District: {dist}")
            if block:
                for k in ["location_block", "mr_track_block", "issued_mr_block",
                          "mis_block", "dashboard_block"]:
                    hm.save_entry(k, block)
                synced.append(f"Block: {block}")

            if synced:
                self._srv_sync_status.configure(
                    text=f"✅ Synced: {', '.join(synced)}",
                    text_color=("#16A34A", "#4ADE80")
                )
                # Refresh the listbox and server card
                self._refresh_loc_list()
                self._refresh_server_data_card()
                self._srv_status_label.configure(
                    text="✅ Auto-synced from server",
                    text_color=("#16A34A", "#4ADE80")
                )
                self.after(5000, lambda: self._srv_sync_status.configure(text=""))
            else:
                self._srv_sync_status.configure(
                    text="ℹ️  Server par koi location data nahi hai",
                    text_color=("gray50", "gray60")
                )
                self.after(5000, lambda: self._srv_sync_status.configure(text=""))
        except Exception as e:
            logger.error("Sync from server failed: %s", e)
            self._srv_sync_status.configure(
                text=f"❌ Sync failed: {e}",
                text_color=("#DC2626", "#F87171")
            )
            self.after(5000, lambda: self._srv_sync_status.configure(text=""))

    def _scrape_from_website(self) -> None:
        """
        Live NREGA website se ALL Panchayat aur unke saare Village data scrape karta hai.
        Har panchayat ko select karta hai, uske villages scrape karta hai,
        aur Panchayat→Village hierarchy build karta hai.
        """
        self._scrape_btn.configure(state="disabled", text="⏳ Scraping...")
        self._scrape_status.configure(text="⏳ Browser connect ho raha hai...")

        def _run_scrape():
            driver = None
            try:
                driver = self.app.get_driver()
                if not driver:
                    self.after(0, self._scrape_failed,
                        "Browser connect nahi hua. Pehle browser launch karein.")
                    return

                self.after(0, lambda: self._scrape_status.configure(
                    text="⏳ Demand page par ja rahe hain..."))

                demand_url = "https://vbgramgde2.dord.gov.in/vbgramg/demand_new.aspx"
                driver.get(demand_url)
                wait = WebDriverWait(driver, 15)

                # ── Step 1: Get all panchayat names ──
                self.after(0, lambda: self._scrape_status.configure(
                    text="⏳ Panchayat list fetch ho raha hai..."))

                panch_select_el = wait.until(
                    EC.presence_of_element_located(
                        (By.ID, "ctl00_ContentPlaceHolder1_DDL_panchayat")
                    )
                )
                panch_select = Select(panch_select_el)

                panch_options = []  # list of (index, value, name)
                for i, opt in enumerate(panch_select.options):
                    val = opt.get_attribute("value")
                    text = opt.text.strip()
                    if val and val != "00" and text and text != "---Select---":
                        panch_options.append((i, val, text.upper()))

                if not panch_options:
                    self.after(0, self._scrape_failed,
                        "Panchayat dropdown me koi option nahi mila. Aap login nahi hain?")
                    return

                # ── Step 2: For EACH panchayat, select it and get villages ──
                hm = self.app.history_manager
                hier = get_hierarchy()

                all_panch_villages = {}  # {panchayat_name: [village_names]}
                total_panch = len(panch_options)

                for idx, (opt_idx, opt_val, panch_name) in enumerate(panch_options):
                    self.after(0, lambda idx=idx, total=total_panch, name=panch_name: self._scrape_status.configure(
                        text=f"⏳ [{idx+1}/{total}] {name} — villages scrape ho rahe hain..."))

                    try:
                        # Re-find the panchayat select (it may have been refreshed by postback)
                        panch_el = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_panchayat")
                        p_select = Select(panch_el)
                        p_select.select_by_index(opt_idx)

                        # Wait for village dropdown to update
                        WebDriverWait(driver, 15).until(
                            lambda d: len(Select(d.find_element(
                                By.ID, "ctl00_ContentPlaceHolder1_DDL_Village"
                            )).options) > 1
                        )

                        # Extract villages for THIS panchayat
                        vill_el = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")
                        v_select = Select(vill_el)

                        villages = []
                        for opt in v_select.options:
                            v_val = opt.get_attribute("value")
                            v_text = opt.text.strip()
                            if v_val and v_val != "00" and v_text and v_text != "---Select---":
                                villages.append(v_text.upper())

                        all_panch_villages[panch_name] = villages

                    except (StaleElementReferenceException, TimeoutException):
                        # If panchayat selection fails, skip and continue
                        all_panch_villages[panch_name] = []
                        continue

                # ── Step 3: Save everything with hierarchy ──
                saved_panch = 0
                saved_vill = 0

                for panch_name, villages in all_panch_villages.items():
                    # Save panchayat to history
                    for k in self._get_panchayat_keys():
                        hm.save_entry(k, panch_name)
                    saved_panch += 1

                    # Save villages and build hierarchy
                    for v_name in villages:
                        for k in self._get_village_keys():
                            hm.save_entry(k, v_name)
                        hier.add_child("Panchayat", panch_name, "Village", v_name)
                        saved_vill += 1

                # ── Step 4: Show results ──
                self.after(0, self._scrape_success,
                           saved_panch, saved_vill, all_panch_villages)

            except TimeoutException:
                self.after(0, self._scrape_failed,
                    "Page load timeout. NREGA website slow ho ya login required ho.")
            except NoSuchElementException as e:
                self.after(0, self._scrape_failed,
                    f"Website ka structure change ho gaya? Element nahi mila: {e}")
            except Exception as e:
                self.after(0, self._scrape_failed, str(e))

        import threading
        threading.Thread(target=_run_scrape, daemon=True).start()

    def _scrape_success(self, saved_panch, saved_vill, all_panch_villages):
        """Update UI on successful scrape with full hierarchy data."""
        parts = []
        if saved_panch:
            parts.append(f"🏘️ {saved_panch} Panchayat(s)")
        if saved_vill:
            parts.append(f"🏠 {saved_vill} Village(s)")
        result = f"✅ Scraped: {', '.join(parts)}"

        self._scrape_status.configure(
            text=result,
            text_color=("#16A34A", "#4ADE80")
        )
        self._scrape_btn.configure(state="normal", text="🚀 Scrape Now")

        # Show detail popup
        detail_lines = []
        if all_panch_villages:
            for p in sorted(all_panch_villages.keys())[:20]:
                v_list = all_panch_villages[p]
                v_text = f" ({len(v_list)} villages)" if v_list else ""
                detail_lines.append(f"🏘️ {p}{v_text}")
            if len(all_panch_villages) > 20:
                detail_lines.append(f"   ... aur {len(all_panch_villages) - 20} aur Panchayats")

        messagebox.showinfo(
            "✅ Scrape Complete",
            f"{result}\n\n" + "\n".join(detail_lines) +
            "\n\nHierarchy bhi save ho gayi hai — Panchayat delete karenge to uske villages bhi delete ho jayenge.",
            parent=self.winfo_toplevel()
        )

        self._refresh_loc_list()
        self.after(8000, lambda: self._scrape_status.configure(text=""))

    def _scrape_failed(self, error_msg):
        """Update UI on scrape failure."""
        self._scrape_status.configure(
            text=f"❌ {error_msg}",
            text_color=("#DC2626", "#F87171")
        )
        self._scrape_btn.configure(state="normal", text="🚀 Scrape Now")
        messagebox.showerror("Scrape Failed",
            f"Data scrape nahi ho paya.\n\n{error_msg}",
            parent=self.winfo_toplevel())
        self.after(8000, lambda: self._scrape_status.configure(text=""))

    def _refresh_server_data_card(self) -> None:
        """Refresh the server synced data badges in the card."""
        try:
            lic = self.app.license_info if hasattr(self.app, 'license_info') else {}
            srv_state = (lic.get('user_state') or '').strip().upper()
            srv_dist  = (lic.get('user_district') or '').strip().upper()
            srv_block = (lic.get('user_block') or '').strip().upper()

            # Clear existing badges/labels, keep the frame itself
            for w in self._srv_vals_frame.winfo_children():
                w.destroy()

            def _srv_badge(parent, label, value):
                if not value:
                    return
                badge = ctk.CTkFrame(parent, fg_color=("#DCFCE7", "#14532D"), corner_radius=6,
                                     border_width=1, border_color=("#86EFAC", "#22C55E"))
                badge.pack(side="left", padx=(0, 8), pady=2)
                ctk.CTkLabel(badge, text=f"  {label}: {value}  ",
                             font=ctk.CTkFont(size=11),
                             text_color=("#166534", "#86EFAC")).pack()

            if srv_state or srv_dist or srv_block:
                if srv_state:
                    _srv_badge(self._srv_vals_frame, "🏛️", srv_state)
                if srv_dist:
                    _srv_badge(self._srv_vals_frame, "📍", srv_dist)
                if srv_block:
                    _srv_badge(self._srv_vals_frame, "📦", srv_block)
                ctk.CTkLabel(self._srv_vals_frame, text="✅ Auto-synced from your license",
                             font=ctk.CTkFont(size=10),
                             text_color=("#166534", "#86EFAC")).pack(side="left", padx=(4, 0))
            else:
                ctk.CTkLabel(self._srv_vals_frame, text="ℹ️  Server par location data set nahi hai.",
                             font=ctk.CTkFont(size=11),
                             text_color=("gray50", "gray60")).pack(side="left")
        except Exception as e:
            logger.debug("_refresh_server_data_card failed: %s", e)

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

        self.map_panchayat_var = ctk.StringVar()
        self.map_panchayat_dropdown = ctk.CTkOptionMenu(row0, variable=self.map_panchayat_var, values=panchayats if panchayats else [""])
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
            self.map_panchayat_var.set(vals[0])

    def _get_current_map_panchayat(self) -> str:
        return self.map_panchayat_var.get().strip()

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
            self.map_panchayat_var.set("")
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

    def _on_whatsapp_notify_toggle(self) -> None:
        """Toggle WhatsApp notification on automation finish."""
        val = self._whatsapp_notify_var.get()
        save_config("whatsapp_automation_notify", val)
        self._update_notif_status_badge()
        if val:
            self._set_fr_status("📱 WhatsApp notifications enabled!", "green")
        else:
            self._set_fr_status("📱 WhatsApp notifications disabled", "gray")

    def _update_notif_status_badge(self) -> None:
        """Update the notification status badge ON/OFF."""
        if not hasattr(self, '_notif_status_badge') or not self._notif_status_badge.winfo_exists():
            return
        val = self._whatsapp_notify_var.get()
        if val:
            self._notif_status_badge.configure(
                text="✅ ON",
                text_color=("#16A34A", "#4ADE80"),
            )
        else:
            self._notif_status_badge.configure(
                text="⏸️ OFF",
                text_color=("gray50", "gray60"),
            )

    def _on_tab_changed(self) -> None:
        """Refresh panels when tab gains focus."""
        current = self.tab_view.get()
        if "Location Data" in current:
            self._refresh_server_data_card()
            self._refresh_loc_list()
        elif "Staff Mapping" in current:
            self._refresh_map_panel()
        elif "Activity Log" in current:
            self._refresh_activity_log()
        elif "Factory Reset" in current:
            self._refresh_fr_stats()

    # ════════════════════════════════════════════════════════════════
    # HELPERS for other tabs (Staff Mapping uses these)
    # ════════════════════════════════════════════════════════════════
    def _get_panchayat_suggestions(self) -> list:
        """Get all unique panchayat names from history."""
        hm = self.app.history_manager
        vals = set()
        for k in self._get_panchayat_keys():
            for s in hm.get_suggestions(k):
                vals.add(s)
        return sorted(vals)

    # ════════════════════════════════════════════════════════════════
    # TAB 4: ACTIVITY LOG — View automation history
    # ════════════════════════════════════════════════════════════════
    def _build_activity_log_tab(self) -> None:
        """Embed the ActivityLogTab widget inside the tab."""
        self._activity_log_widget = ActivityLogTab(self.tab_activity, self.app)
        self._activity_log_widget.pack(fill="both", expand=True, padx=0, pady=0)

    def _refresh_activity_log(self) -> None:
        """Refresh the activity log when its tab is shown."""
        if hasattr(self, '_activity_log_widget') and self._activity_log_widget.winfo_exists():
            self._activity_log_widget._refresh_log()

    # ════════════════════════════════════════════════════════════════
    # TAB 5: FACTORY RESET — Restore app to fresh-install state
    # ════════════════════════════════════════════════════════════════
    def _build_factory_reset_tab(self) -> None:
        c = self.tab_factory
        c.grid_rowconfigure(0, weight=1)
        c.grid_columnconfigure(0, weight=1)

        bg = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        scroll = ctk.CTkScrollableFrame(c, fg_color=bg)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(1, weight=1)

        # ── Header ──
        ctk.CTkLabel(scroll, text="🏭 Restore Factory Settings",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(scroll,
            text="App ko wapas naye installation jaisa fresh bana dein.\n"
                 "Saara saved data — history, suggestions, location data, staff mappings, "
                 "default values, aur settings sab clear ho jayenge.\n\n"
                 "Sirf aapka license activation (license.dat) safe rahega — "
                 "aapko dubara activate nahi karna padega.",
            font=ctk.CTkFont(size=12), text_color=("gray50", "gray60"),
            wraplength=650, justify="left",
                     ).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 15))

        # ── Data usage summary cards ──
        self._fr_stats_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._fr_stats_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 15))
        self._refresh_fr_stats()

        # ── What will be reset ──
        reset_frame = ctk.CTkFrame(scroll, fg_color=("#FEF2F2", "#450A0A"), corner_radius=10)
        reset_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        ctk.CTkLabel(reset_frame, text="🗑️  Ye Sab DELETE Ho Jayega:",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=("#DC2626", "#F87171"),
                     ).pack(anchor="w", padx=15, pady=(12, 5))
        reset_items = [
            "📝 Saari autocomplete suggestions aur history",
            "📊 Usage stats aur 'Most Used' section",
            "🏘️ Location data (Panchayat, Village)",
            "👥 Staff aur Mate mappings",
            "⚙️ Default values (₹ 300, pit count, page no., etc.)",
            "📁 Location hierarchy relationships",
            "📋 Activity log",
            "🔧 App config (theme, browser preference) — defaults par reset",
            "📄 Sabhi saved tab inputs aur form data",
        ]
        for item in reset_items:
            ctk.CTkLabel(reset_frame, text=item, font=ctk.CTkFont(size=12),
                         text_color=("#991B1B", "#FCA5A5"),
                         anchor="w", justify="left",
                         ).pack(anchor="w", padx=25, pady=1)
        ctk.CTkLabel(reset_frame, text="", font=ctk.CTkFont(size=4)).pack()

        # ── What will be kept ──
        keep_frame = ctk.CTkFrame(scroll, fg_color=("#F0FDF4", "#14532D"), corner_radius=10)
        keep_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 15))
        ctk.CTkLabel(keep_frame, text="✅  Ye Safe Rahega:",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=("#16A34A", "#4ADE80"),
                     ).pack(anchor="w", padx=15, pady=(12, 5))
        keep_items = [
            "🔑 Aapka license activation (dubara activate nahi karna padega)",
            "🖥️ App version aur program files",
            "📂 ~/Downloads/NregaBot/ folder mein saved reports aur files",
        ]
        for item in keep_items:
            ctk.CTkLabel(keep_frame, text=item, font=ctk.CTkFont(size=12),
                         text_color=("#166534", "#86EFAC"),
                         anchor="w", justify="left",
                         ).pack(anchor="w", padx=25, pady=1)
        ctk.CTkLabel(keep_frame, text="", font=ctk.CTkFont(size=4)).pack()

        # ── Action button + status ──
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 10))
        btn_frame.grid_columnconfigure(0, weight=1)

        self._fr_status = ctk.CTkLabel(btn_frame, text="", font=ctk.CTkFont(size=12),
                                        text_color=("gray50", "gray60"))
        self._fr_status.pack(side="left", padx=(0, 15))

        self._fr_button = ctk.CTkButton(
            btn_frame, text="⚠️  Restore Factory Settings", height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#DC2626", "#B91C1C"), text_color="white",
            hover_color=("#B91C1C", "#991B1B"),
            command=self._perform_factory_reset,
        )
        self._fr_button.pack(side="right", padx=(5, 0))

        # ── Note ──
        ctk.CTkLabel(scroll, text="💡  Restore karne ke baad app ko restart karne ki salah di jaati hai taake sab changes effect mein aayein.",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60"),
                     wraplength=600, justify="left",
                     ).grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 0))

    def _refresh_fr_stats(self) -> None:
        """Refresh the summary stats cards."""
        for w in self._fr_stats_frame.winfo_children():
            w.destroy()

        hm = self.app.history_manager
        total_suggestions = hm.get_total_suggestions_count()
        total_usage = hm.get_usage_stats_count()
        count_by_key = hm.get_suggestions_count_by_key()

        card_frame = ctk.CTkFrame(self._fr_stats_frame, fg_color="transparent")
        card_frame.pack(fill="x")

        def _stat_card(parent, label, count, icon, color):
            card = ctk.CTkFrame(parent, fg_color=color, corner_radius=10, height=70,
                                border_width=1, border_color=("white", "#333333"))
            card.pack(side="left", padx=4, expand=True, fill="x")
            card.pack_propagate(False)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=20)).pack()
            ctk.CTkLabel(inner, text=str(count), font=ctk.CTkFont(size=20, weight="bold"),
                         text_color=("#1E293B", "#F1F5F9")).pack()
            ctk.CTkLabel(inner, text=label, font=ctk.CTkFont(size=10),
                         text_color=("gray20", "gray80")).pack()

        _stat_card(card_frame, "Suggestions", total_suggestions, "💾",
                   ("#EFF6FF", "#1E3A5F"))
        _stat_card(card_frame, "Field Types", len(count_by_key), "📋",
                   ("#F0FDF4", "#14532D"))
        _stat_card(card_frame, "Usage Stats", total_usage, "📊",
                   ("#FEFCE8", "#422006"))

    def _perform_factory_reset(self) -> None:
        """Execute full factory reset with confirmation."""
        # ── Step 1: Double confirmation ──
        if not messagebox.askyesno(
            "⚠️ Confirm Factory Reset",
            "Kya aap sach mein app ko factory settings par reset karna chahte hain?\n\n"
            "ISSE: \n"
            "• Saari history, suggestions, aur saved data DELETE ho jayega\n"
            "• Location data aur staff mappings DELETE ho jayega\n"
            "• Default values ₹ 300 par reset ho jayenge\n"
            "• Theme aur settings default par reset ho jayenge\n\n"
            "Sirf aapka license activation safe rahega.\n\n"
            "Kya aap sure hain?",
            icon="warning",
            parent=self.winfo_toplevel()
        ):
            return

        if not messagebox.askyesno(
            "🛑 Final Confirmation",
            "YEH LAST WARNING HAI!\n\n"
            "Factory reset ke baad aapka saara saved data hamesha ke liye delete ho jayega.\n"
            "Isse wapas nahi laaya ja sakta.\n\n"
            "Agar aapke paas koi important location data ya mapping hai, "
            "to pehle unhe note kar lein.\n\n"
            "Kya aap sach mein proceed karna chahte hain?",
            icon="warning",
            parent=self.winfo_toplevel()
        ):
            return

        # ── Step 2: Disable button to prevent double-click ──
        self._fr_button.configure(state="disabled", text="⏳ Resetting...")
        self._set_fr_status("🔄 Factory reset in progress...", "gray")
        self.update_idletasks()

        try:
            hm = self.app.history_manager
            deleted_files = []
            failed_files = []

            # ── 1. Clear the SQLite database ──
            if hm.factory_reset():
                deleted_files.append("🗄️ Database (history, stats, inputs)")
            else:
                failed_files.append("🗄️ Database clear failed")

            # ── 2. Delete location_hierarchy.json ──
            hier_path = get_data_path("location_hierarchy.json")
            if os.path.exists(hier_path):
                try:
                    os.remove(hier_path)
                    deleted_files.append("🏘️ Location hierarchy")
                except Exception as e:
                    failed_files.append(f"🏘️ Location hierarchy: {e}")

            # ── 3. Delete staff mapping files ──
            for map_file in ["mr_panchayat_staff_map.json", "mb_panchayat_mate_map.json"]:
                fp = get_data_path(map_file)
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                        deleted_files.append(f"👥 {map_file}")
                    except Exception as e:
                        failed_files.append(f"👥 {map_file}: {e}")

            # ── 3b. Delete Login Automation saved location pref ──
            login_pref = get_data_path("user_location_pref.json")
            if os.path.exists(login_pref):
                try:
                    os.remove(login_pref)
                    deleted_files.append("🔑 Login location pref")
                except Exception as e:
                    failed_files.append(f"🔑 Login location pref: {e}")

            # ── 4. Delete default values JSON files ──
            for def_file in ["mb_entry_inputs.json", "emb_verify_inputs.json",
                             "msr_inputs.json", "add_activity_inputs.json",
                             "wagelist_send_config.json"]:
                fp = get_data_path(def_file)
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                        deleted_files.append(f"⚙️ {def_file}")
                    except Exception as e:
                        failed_files.append(f"⚙️ {def_file}: {e}")

            # ── 5. Reset config.json to defaults ──
            try:
                config.create_default_config_if_not_exists()
                # Force overwrite with defaults
                default_config = {
                    "theme": "System",
                    "last_used_browser": "chrome",
                    "onboarding_complete": False,
                }
                with open(get_data_path("config.json"), "w") as f:
                    json.dump(default_config, f, indent=4)
                # Reload config into app
                self.app.app_state.current_theme_mode = "System"
                ctk.set_appearance_mode("System")
                deleted_files.append("🔧 config.json (reset to defaults)")
            except Exception as e:
                failed_files.append(f"🔧 config.json: {e}")

            # ── 6. Delete log files ──
            log_path = get_data_path("nregabot.log")
            if os.path.exists(log_path):
                try:
                    os.remove(log_path)
                    deleted_files.append("📄 nregabot.log")
                except Exception as e:
                    failed_files.append(f"📄 nregabot.log: {e}")
            # Also delete rotated logs
            for i in range(1, 3):
                rotated = f"{log_path}.{i}"
                if os.path.exists(rotated):
                    try:
                        os.remove(rotated)
                    except Exception:
                        pass

            # ── 7. Clear all open tab inputs ──
            self._clear_all_tab_widgets()

            # ── 8. Refresh UI ──
            self._refresh_fr_stats()

            # ── Show result ──
            result_msg = f"✅ Factory reset complete!\n\n"
            result_msg += f"🗑️ {len(deleted_files)} items cleared successfully.\n"
            for f in deleted_files:
                result_msg += f"  ✅ {f}\n"
            if failed_files:
                result_msg += f"\n⚠️ {len(failed_files)} items had errors:\n"
                for f in failed_files:
                    result_msg += f"  ❌ {f}\n"
            result_msg += "\n💡 App ko restart karne ki salah di jaati hai."

            messagebox.showinfo("✅ Factory Reset Complete", result_msg,
                                parent=self.winfo_toplevel())

            self._set_fr_status(
                f"✅ Reset complete! {len(deleted_files)} items cleared. App restart suggested.",
                "green"
            )

        except Exception as e:
            logger.error("Factory reset failed: %s", e)
            self._set_fr_status(f"❌ Reset failed: {e}", "red")
            messagebox.showerror("Error", f"Factory reset failed:\n\n{e}",
                                 parent=self.winfo_toplevel())
        finally:
            self._fr_button.configure(state="normal", text="⚠️  Restore Factory Settings")

    def _set_fr_status(self, msg: str, color: str = "gray") -> None:
        colors = {"green": ("#16A34A", "#4ADE80"), "red": ("#DC2626", "#F87171"),
                  "gray": ("gray50", "gray60")}
        self._fr_status.configure(text=msg, text_color=colors.get(color, colors["gray"]))
        self._fr_status.after(8000, lambda: self._fr_status.configure(text=""))

    def _clear_all_tab_widgets(self) -> None:
        """
        Clear ALL input fields across every open tab after factory reset.
        
        Instead of maintaining a fragile list of attribute names, this
        dynamically inspects every attribute of each tab instance and
        clears it based on its widget type:
          - CTkEntry / tkinter.Entry        → delete(0, 'end')
          - CTkTextbox / tkinter.Text       → delete('1.0', 'end')
          - CTkComboBox / ttk.Combobox      → set('')
          - CTkOptionMenu                   → set('')
          - tkinter.Listbox                 → delete(0, 'end')
          - ttk.Treeview                    → delete all children
          - tkinter.StringVar/BooleanVar    → set('') / set(False)
        """
        try:
            tab_instances = getattr(self.app, 'app_state', None)
            if not tab_instances:
                return
            tab_instances = getattr(tab_instances, 'tab_instances', {})

            for page_name, instance in tab_instances.items():
                # Skip non-frame objects like None or primitives
                if instance is None:
                    continue
                # Get all attribute names from the instance
                for attr_name in dir(instance):
                    # Skip private/dunder attrs and methods
                    if attr_name.startswith('_'):
                        continue
                    widget = getattr(instance, attr_name, None)
                    if widget is None:
                        continue

                    try:
                        # ── CTkEntry / tkinter Entry ──
                        if isinstance(widget, (ctk.CTkEntry, tkinter.Entry)):
                            widget.delete(0, 'end')

                        # ── CTkTextbox / tkinter Text ──
                        elif isinstance(widget, (ctk.CTkTextbox, tkinter.Text)):
                            widget.delete('1.0', 'end')

                        # ── CTkComboBox / ttk.Combobox ──
                        elif isinstance(widget, (ctk.CTkComboBox, ttk.Combobox)):
                            widget.set('')

                        # ── CTkOptionMenu ──
                        elif isinstance(widget, ctk.CTkOptionMenu):
                            widget.set('')

                        # ── tkinter.Listbox ──
                        elif isinstance(widget, tkinter.Listbox):
                            widget.delete(0, 'end')

                        # ── ttk.Treeview ──
                        elif isinstance(widget, ttk.Treeview):
                            for item in widget.get_children():
                                widget.delete(item)

                        # ── tkinter.StringVar / BooleanVar / DoubleVar / IntVar ──
                        elif isinstance(widget, tkinter.StringVar):
                            widget.set('')
                        elif isinstance(widget, tkinter.BooleanVar):
                            widget.set(False)
                        elif isinstance(widget, (tkinter.DoubleVar, tkinter.IntVar)):
                            widget.set(0)

                    except Exception:
                        pass  # Silently skip incompatible widgets

        except Exception as e:
            logger.debug("_clear_all_tab_widgets failed: %s", e)

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

        # ── 🔝 NOTIFICATION SETTINGS (Top pe rakha gaya hai taake user sabse pehle dekhe) ──
        ctk.CTkLabel(scroll, text="📢 Notification Settings", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=("#EA580C", "#FB923C"),
                     ).grid(row=row_num[0], column=0, columnspan=3, sticky="w", padx=10, pady=(10, 2))
        row_num[0] += 1

        # Banner-style notification card
        notif_card = ctk.CTkFrame(scroll, fg_color=("#FFF7ED", "#1C1917"), corner_radius=10,
                                   border_width=1, border_color=("#FDBA74", "#9A3412"))
        notif_card.grid(row=row_num[0], column=0, columnspan=3, sticky="ew", padx=10, pady=(2, 10))
        row_num[0] += 1

        # Icon + Title in banner
        notif_header = ctk.CTkFrame(notif_card, fg_color="transparent")
        notif_header.pack(fill="x", padx=15, pady=(10, 2))
        ctk.CTkLabel(notif_header, text="📱", font=ctk.CTkFont(size=22)).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(notif_header,
                     text="WhatsApp Automation Notification",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=("#9A3412", "#FDBA74")).pack(side="left")

        # Switch row
        switch_row = ctk.CTkFrame(notif_card, fg_color="transparent")
        switch_row.pack(fill="x", padx=15, pady=(2, 2))

        self._whatsapp_notify_var = tkinter.BooleanVar(
            value=get_config("whatsapp_automation_notify", False)
        )
        self._whatsapp_notify_switch = ctk.CTkSwitch(
            switch_row, text="🔔  Automation Finish par WhatsApp notification bhejein",
            variable=self._whatsapp_notify_var,
            command=self._on_whatsapp_notify_toggle,
            font=ctk.CTkFont(size=13),
            switch_width=50, switch_height=24,
        )
        self._whatsapp_notify_switch.pack(side="left", padx=(0, 12), pady=5)

        # Status indicator (ON/OFF badge)
        self._notif_status_badge = ctk.CTkLabel(
            switch_row, text="", font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=4,
        )
        self._notif_status_badge.pack(side="left", padx=(0, 10))
        self._update_notif_status_badge()

        # Description
        ctk.CTkLabel(notif_card,
            text="ℹ️ Jab bhi koi automation finish hogi (success/fail), aapke registered WhatsApp number par ek summary message bhej diya jayega.\n"
                 "Message mein task ka naam, panchayat, duration aur result details honge.",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            wraplength=650, justify="left",
        ).pack(padx=15, pady=(2, 10), anchor="w")

        # Thin separator below notification card
        ctk.CTkFrame(scroll, height=1, corner_radius=0,
                     fg_color=("gray85", "gray35"),
                     ).grid(row=row_num[0], column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 5))
        row_num[0] += 1

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
