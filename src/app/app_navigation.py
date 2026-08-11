# app_navigation.py — Navigation & Tab Management Mixin
#
# P3: Extracted from main_app.py.
# Uses mixin pattern combined with NregaBotApp.

import threading
import tkinter
import traceback
from tkinter import messagebox, filedialog, ttk
import customtkinter as ctk
from PIL import Image
from typing import Any, Dict, List, Optional, Tuple

from src import config
from src.tab_config import get_tabs_definition
from src.ui_components import CollapsibleFrame, SkeletonLoader
from src.utils import resource_path, get_config, save_config, get_logger
from src.i18n import tr


logger = get_logger()


class NavMixin:
    """Mixin: navigation buttons, tab management, frame switching."""

    def _nav_tab_name(self, name: str) -> str:
        """Translated display name for a sidebar tab (internal key stays English)."""
        return tr(f"nav.tab.{name}", default=name)

    def _nav_cat_name(self, cat: str) -> str:
        """Translated display name for a sidebar category (internal key stays English)."""
        return tr(f"nav.cat.{cat}", default=cat)

    def _create_nav_buttons(self, header_parent: Any, content_parent: Any) -> None:
        self.app_state.nav_buttons.clear()
        self.app_state.button_to_category_frame.clear()
        self.app_state.category_frames.clear()
        self.app_state.tab_icon_map = {}
        self.app_state._tab_icon_keys = {}
        self.app_state._category_icons_loaded = set()

        # P5: Mapping of tab display name → LazyIconManager key for lazy loading.
        # Only Home icon is eagerly loaded (it's pinned and always visible).
        _ICON_KEYS = {
            # MR & Wage Management
            "Demand": "emoji_demand",
            "Work Allocation": "emoji_work_allocation",
            "Muster Roll Gen": "emoji_mr_gen",
            "Mate/Mistri MR": "emoji_mr_gen",
            "MR Fill": "emoji_mr_fill",
            "MR Payment": "emoji_mr_payment",
            "Gen Wagelist": "emoji_gen_wagelist",
            "Send Wagelist": "emoji_send_wagelist",
            "FTO Generation": "emoji_fto_gen",
            "Duplicate MR Print": "emoji_duplicate_mr",
            "Material Entry": "emoji_material_entry",
            # JE & AE Approval
            "eMB Entry": "emoji_mb_entry",
            "eMB Verify": "emoji_emb_verify",
            # Schemes Related
            "Work Code Gen": "emoji_wc_gen",
            "IF Editor": "emoji_if_editor",
            "Update Estimate": "emoji_update_estimate",
            "Physical Complete": "emoji_physical_complete",
            "Scheme Closing": "emoji_scheme_closing",
            "Add Activity": "emoji_add_activity",
            # Verification & Utility
            "Job Card Verify": "emoji_verify_jobcard",
            "Verify ABPS": "emoji_verify_abps",
            "Del Work Alloc": "emoji_del_work_alloc",
            "Delete Demand": "emoji_del_demand",
            "Delete Applicant": "emoji_delete_applicant",
            "Zero MR": "emoji_zero_mr",
            "Resend Rejected WG": "emoji_resend_wg",
            "Sarkar Aapke Dwar": "emoji_sad_status",
            "SAD Update Status": "emoji_update_outcome",
            # Reports & Tracking
            "MR Tracking": "emoji_mr_tracking",
            "Dashboard Report": "emoji_dashboard_report",
            "MIS Reports": "emoji_mis_reports",
            "Issued MR Details": "emoji_issued_mr_report",
            "eKYC Report": "emoji_ekyc_report",
            "Social Audit Report": "emoji_social_audit",
            "NMMS Attendance": "emoji_nmms_attendance",
            "Pending Bills": "emoji_pending_bills",
            # Smart Tools
            "Macro Manager": "emoji_tools",
            "PDF Merger": "emoji_pdf_merger",
            "Workcode Extractor": "emoji_wc_extractor",
            "File Manager": "emoji_file_manager",
            # About & Help
            "About": "emoji_about",
            "Settings": "emoji_tools",
            "Feedback": "emoji_feedback",
            "WhatsApp Chat": "whatsapp",
        }

        for widget in header_parent.winfo_children(): widget.destroy()

        # --- Pinned Home button (always visible, above everything) ---
        _home_icon = None
        try:
            _home_icon = ctk.CTkImage(Image.open(resource_path("assets/icons/home.png")), size=(18, 18))
        except Exception as e:
            logger.debug("Failed to load home icon: %s", e)
        self.home_nav_btn = ctk.CTkButton(
            header_parent,
            text=f"  {self._nav_tab_name('Home')}",
            image=_home_icon,
            compound="left",
            command=lambda: self.show_frame("Home"),
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=32,
            corner_radius=6,
            fg_color="transparent",
            text_color=("#1565C0", "#60A5FA"),
            hover_color=("#BBDEFB", "#4B5563"),
            border_spacing=7
        )
        self.home_nav_btn.pack(fill="x", padx=5, pady=(8, 2))
        self.app_state.nav_buttons["Home"] = self.home_nav_btn
        # Keep icon reference so _update_nav_button_color doesn't wipe it
        self.app_state.tab_icon_map["Home"] = _home_icon

        # Thin separator
        ctk.CTkFrame(header_parent, height=1, corner_radius=0, fg_color=("gray85", "gray35")).pack(fill="x", padx=15, pady=(2, 5))

        # --- Category Filter (without Dashboard) — clean, modern look ---
        all_cats = list(self.get_tabs_definition().keys())
        filtered_cats = [c for c in all_cats if c != "Dashboard"]
        categories = ["All Automations"] + filtered_cats
        # Guard: if saved category no longer exists (e.g. old "Dashboard"), reset
        if self.app_state.last_selected_category not in categories:
            self.app_state.last_selected_category = "All Automations"
        
        # Display values are translated; internal keys stay English.
        self._cat_display_map = {cat: self._nav_cat_name(cat) for cat in categories}
        self._cat_internal_map = {disp: cat for cat, disp in self._cat_display_map.items()}
        display_categories = [self._cat_display_map[c] for c in categories]
        
        self.category_filter_var = ctk.StringVar()
        self.category_filter_menu = ctk.CTkOptionMenu(
            header_parent,
            variable=self.category_filter_var,
            values=display_categories,
            command=self._on_category_filter_change,
            width=180, height=28,
        )
        self.category_filter_var.set(self._cat_display_map.get(
            self.app_state.last_selected_category,
            self._cat_display_map["All Automations"]))
        self.category_filter_menu.pack(fill="x", pady=(5, 5), padx=5)

        # ── Tab Search (55 tabs me se turant dhundho — Ctrl+K focus) ──
        self.nav_search_var = ctk.StringVar()
        self.nav_search_entry = ctk.CTkEntry(
            header_parent,
            placeholder_text=tr("nav.search_placeholder", default="🔍 Search tabs..."),
            textvariable=self.nav_search_var,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            border_width=1,
            border_color=("#D1D5DB", "#4B5563"),
        )
        self.nav_search_entry.pack(fill="x", pady=(0, 5), padx=5)
        self.nav_search_entry.bind("<KeyRelease>", self._on_nav_search_change)
        self.nav_search_entry.bind("<Escape>", lambda e: self._clear_nav_search())
        # Ctrl+K → sidebar search par focus (global shortcut)
        try:
            if not getattr(self, '_nav_search_shortcut_bound', False):
                self._nav_search_shortcut_bound = True
                self.bind_all("<Control-k>", lambda e: self._focus_nav_search(), add="+")
        except Exception:
            pass

        # ── Automation keyboard shortcuts (global, guarded) ──
        # Ctrl+Enter → current tab start · Ctrl+S → stop · Ctrl+R → retry
        try:
            if not getattr(self, '_automation_shortcuts_bound', False):
                self._automation_shortcuts_bound = True
                self.bind_all("<Control-Return>", lambda e: self._shortcut_start(), add="+")
                self.bind_all("<Control-s>", lambda e: self._shortcut_stop(), add="+")
                self.bind_all("<Control-r>", lambda e: self._shortcut_retry(), add="+")
        except Exception:
            pass

        # Category colors matching the Home page card colors
        _CATEGORY_BG = {
            "MR & Wage Management": {"bg": ("#EFF6FF", "#1E3A5F"), "border": ("#BFDBFE", "#3B82F6"), "accent": ("#3B82F6", "#60A5FA")},
            "JE & AE Approval":      {"bg": ("#F0FDF4", "#14532D"), "border": ("#BBF7D0", "#22C55E"), "accent": ("#16A34A", "#4ADE80")},
            "Schemes Related":       {"bg": ("#FFF7ED", "#431407"), "border": ("#FED7AA", "#F97316"), "accent": ("#EA580C", "#FB923C")},
            "Verification & Utility":{"bg": ("#F5F3FF", "#2E1065"), "border": ("#DDD6FE", "#8B5CF6"), "accent": ("#7C3AED", "#A78BFA")},
            "Reports & Tracking":    {"bg": ("#FEF2F2", "#450A0A"), "border": ("#FECACA", "#EF4444"), "accent": ("#DC2626", "#F87171")},
            "Smart Tools":           {"bg": ("#FEFCE8", "#422006"), "border": ("#FDE68A", "#EAB308"), "accent": ("#CA8A04", "#FACC15")},
            "About & Help":          {"bg": ("#F0F9FF", "#0C4A6E"), "border": ("#BAE6FD", "#0EA5E9"), "accent": ("#0284C7", "#38BDF8")},
        }

        for cat, tabs in self.get_tabs_definition().items():
            if cat == "Dashboard":
                continue  # Skip Dashboard category — Home is pinned separately

            cat_frame = CollapsibleFrame(content_parent, title=self._nav_cat_name(cat))
            # Apply category background and border to the sidebar section
            colors = _CATEGORY_BG.get(cat)
            if colors:
                cat_frame.configure(
                    fg_color=colors["bg"],
                    border_width=1,
                    border_color=colors["border"]
                )
                cat_frame.header_label.configure(text_color=colors["accent"])
                self.app_state.category_frames[cat] = cat_frame
            
            for name, data in tabs.items():
                # P5: Store icon key for lazy loading — don't load the icon yet
                icon_key = _ICON_KEYS.get(name)
                self.app_state._tab_icon_keys[name] = icon_key
                # tab_icon_map starts empty; icons are populated on first category show

                # P5: Create button WITHOUT image (icon loaded lazily when category is shown)
                btn = ctk.CTkButton(
                    cat_frame.content_frame, 
                    text=self._nav_tab_name(name), 
                    image=None, 
                    compound="left", 
                    command=lambda n=name: self.show_frame(n), 
                    anchor="w", 
                    font=ctk.CTkFont(family="Segoe UI", size=12, weight="normal"), 
                    height=32,           
                    corner_radius=6,    
                    fg_color="transparent", 
                    text_color=("gray30", "gray80"), 
                    hover_color=("gray90", "gray25"),
                    border_spacing=8     
                )
                btn.pack(fill="x", padx=5, pady=1) 
                
                self.app_state.nav_buttons[name] = btn
                self.app_state.button_to_category_frame[name] = cat_frame

                is_disabled = False
                if isinstance(self.app_state.global_disabled_features, list):
                    if name in self.app_state.global_disabled_features: is_disabled = True
                elif isinstance(self.app_state.global_disabled_features, dict):
                    if name in self.app_state.global_disabled_features: is_disabled = True
                
                if is_disabled:
                    btn.configure(
                        state="normal", 
                        text=f"{self._nav_tab_name(name)} ⚠️",
                        fg_color=("#FEF2F2", "#450A0A"), 
                        text_color=("#DC2626", "#F87171"), 
                        hover_color=("#FEE2E2", "#7F1D1D") 
                    )

        # P5: Call _filter_nav_menu to show the saved category (loads icons for visible cats)
        self._filter_nav_menu(self.app_state.last_selected_category)


    def get_tabs_definition(self) -> Dict[str, Dict[str, Any]]:
        return get_tabs_definition(self)


    def _create_content_frames(self) -> None:
        self.app_state.content_frames.clear()
        self.app_state.tab_instances.clear()
        self.show_frame("About", raise_frame=False)
    

    def show_frame(self, page_name, raise_frame=True):
        self.app_state.current_active_tab = page_name
        
        # A3: Clean up stale error frame from a previous failed load attempt
        stale_key = page_name + "_error"
        stale = self.app_state.content_frames.pop(stale_key, None)
        if stale:
            try:
                stale.destroy()
            except Exception:
                pass
        
        # Keep tabs that have run an automation (running OR completed) —
        # destroying them loses logs, results, and button state.
        # Home and About are always cached.
        if page_name not in ("Home", "About") and page_name in self.app_state.tab_instances:
            old_instance = self.app_state.tab_instances.get(page_name)
            # Check if this tab has ever run an automation
            has_automated = getattr(old_instance, '_has_automated', False)
            
            if not has_automated:
                old_instance = self.app_state.tab_instances.pop(page_name, None)
                old_frame = self.app_state.content_frames.pop(page_name, None)
                if old_instance:
                    try:
                        old_instance.destroy()
                    except Exception:
                        pass
                if old_frame:
                    try:
                        old_frame.destroy()
                    except Exception:
                        pass
        
        if page_name in self.app_state.tab_instances:
            if raise_frame:
                self.app_state.content_frames[page_name].tkraise()
                self._update_nav_button_color(page_name)
            # Track usage and refresh Home page's Most Used when navigating back
            self._track_tab_usage(page_name)
            if page_name == "Home":
                # Brief delay so the frame renders before the widget rebuild
                self.after(80, self._refresh_home_most_used)
            return

        loading_frame = ctk.CTkFrame(self.content_area, corner_radius=0)
        loading_frame.grid(row=0, column=0, sticky="nsew")
        skeleton = SkeletonLoader(loading_frame, rows=10)
        loading_frame.tkraise()
        self.update_idletasks()
        
        def load_actual_tab():
            try:
                tabs = self.get_tabs_definition()
                for cat, tab_items in tabs.items():
                    if page_name in tab_items:
                        frame = ctk.CTkFrame(self.content_area, corner_radius=0)
                        frame.grid(row=0, column=0, sticky="nsew")
                        self.app_state.content_frames[page_name] = frame
                        
                        instance = tab_items[page_name]["creation_func"](frame, self)
                        instance.pack(expand=True, fill="both")
                        self.app_state.tab_instances[page_name] = instance
                        
                        skeleton.stop()
                        loading_frame.destroy()
                        
                        if raise_frame:
                            frame.tkraise()
                            self._update_nav_button_color(page_name)
                        # Track usage on first load too; refresh Most Used if loading Home
                        self._track_tab_usage(page_name)
                        if page_name == "Home":
                            self._refresh_home_most_used()
                        break
            except Exception as e:
                logger.error("Error loading tab %s: %s", page_name, e)
                traceback.print_exc()
                skeleton.stop()
                loading_frame.destroy()
                # A3: Show graceful error UI with retry in the content area
                # Also pop any previous stale error frame to prevent orphan accumulation
                stale_key = page_name + "_error"
                stale = self.app_state.content_frames.pop(stale_key, None)
                if stale:
                    try:
                        stale.destroy()
                    except Exception:
                        pass
                self._show_tab_error_ui(page_name, e)

        self.after(1, load_actual_tab)


    def _show_tab_error_ui(self, page_name: str, exception: Exception) -> None:
        """A3: Display a graceful error UI in the content area when a tab fails to load.
        
        Shows an error card with:
          - Error icon + heading
          - Tab name and brief error description
          - "Retry" button (re-invokes show_frame)
          - "Go Home" button (navigates to Home dashboard)
          - Expandable technical details (traceback)
        
        Args:
            page_name: The name of the tab that failed to load.
            exception: The exception that was raised.
        """
        # Create error frame in the content area
        error_frame = ctk.CTkFrame(self.content_area, corner_radius=0)
        error_frame.grid(row=0, column=0, sticky="nsew")
        error_frame.grid_rowconfigure(0, weight=1)
        error_frame.grid_columnconfigure(0, weight=1)
        
        # Center container
        container = ctk.CTkFrame(error_frame, fg_color="transparent")
        container.grid(row=0, column=0)
        
        # --- Error Icon ---
        ctk.CTkLabel(
            container,
            text="⚠️",
            font=ctk.CTkFont(size=48),
            text_color=(config.COLORS["red"], config.COLORS["red_light"])
        ).pack(pady=(30, 5))
        
        # --- Error Heading ---
        ctk.CTkLabel(
            container,
            text=tr("base.error_tab.title"),
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"])
        ).pack(pady=(5, 5))
        
        # --- Tab Name ---
        ctk.CTkLabel(
            container,
            text=f"'{self._nav_tab_name(page_name)}'",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"])
        ).pack(pady=(0, 15))
        
        # --- Explanation ---
        ctk.CTkLabel(
            container,
            text=tr("base.error_tab.subtitle"),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"]),
            justify="center",
            wraplength=400
        ).pack(pady=(0, 10))
        
        # --- Exception Type + Message (visible without expanding traceback) ---
        exc_type = type(exception).__name__
        exc_msg = str(exception)[:200]
        ctk.CTkLabel(
            container,
            text=f"{exc_type}: {exc_msg}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=(config.COLORS["red"], config.COLORS["red_light"]),
            justify="center",
            wraplength=450
        ).pack(pady=(0, 15))
        
        # --- Action Buttons Row ---
        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(pady=(0, 15))
        
        # Retry button
        retry_btn = ctk.CTkButton(
            btn_row,
            text=tr("base.error_tab.retry_btn"),
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=(config.COLORS["blue"], config.COLORS["blue"]),
            hover_color=(config.COLORS["blue_hover"], config.COLORS["blue_dark"]),
            text_color="white",
            height=36,
            width=120,
            corner_radius=8,
            command=lambda: self._retry_tab(page_name, error_frame)
        )
        retry_btn.pack(side="left", padx=5)
        
        # Go Home button
        home_btn = ctk.CTkButton(
            btn_row,
            text=tr("base.error_tab.home_btn"),
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=("#E2E8F0", "#334155"),
            hover_color=("#CBD5E1", "#475569"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"]),
            height=36,
            width=120,
            corner_radius=8,
            command=lambda: self.show_frame("Home")
        )
        home_btn.pack(side="left", padx=5)
        
        # --- Expandable Error Details ---
        details_btn = ctk.CTkButton(
            container,
            text=tr("base.error_tab.show_details"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            hover_color=("gray90", "gray25"),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"]),
            height=28,
            corner_radius=6,
            command=None  # Will be set below
        )
        details_btn.pack(pady=(5, 5))
        
        # Details textbox (hidden initially)
        details_text = ctk.CTkTextbox(
            container,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("#F9FAFB", "#1E1E1E"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"]),
            height=150,
            width=500,
            corner_radius=8,
            border_width=1,
            border_color=("#E5E7EB", "#333333"),
            state="disabled"
        )
        
        # Format traceback
        tb_text = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        details_text.configure(state="normal")
        details_text.insert("1.0", tb_text)
        details_text.configure(state="disabled")
        
        # Track details visibility
        _details_visible = [False]
        
        def toggle_details():
            _details_visible[0] = not _details_visible[0]
            if _details_visible[0]:
                details_text.pack(pady=(0, 15), padx=20, fill="x")
                details_btn.configure(text=tr("base.error_tab.hide_details"))
            else:
                details_text.pack_forget()
                details_btn.configure(text=tr("base.error_tab.show_details"))
        
        details_btn.configure(command=toggle_details)
        
        # Store reference so it can be cleaned up
        error_frame.tkraise()
        self.app_state.content_frames[page_name + "_error"] = error_frame


    def _retry_tab(self, page_name: str, old_error_frame: ctk.CTkFrame) -> None:
        """A3: Clean up the error UI and retry loading the tab."""
        # Remove error frame from tracking
        self.app_state.content_frames.pop(page_name + "_error", None)
        try:
            old_error_frame.destroy()
        except Exception:
            pass
        # Re-invoke show_frame to retry
        self.show_frame(page_name)


    def _refresh_home_most_used(self):
        """Refresh the Home tab's Most Used section if the tab is loaded."""
        home = self.app_state.tab_instances.get("Home")
        if home and hasattr(home, "refresh"):
            try:
                home.refresh()
            except Exception:
                pass


    def _track_tab_usage(self, page_name):
        """Track usage of a tab for the Home dashboard's 'Most Used' section.
        Runs DB write in background thread so UI stays snappy."""
        if page_name in ("Home", "About", "Feedback"):
            return
        tabs = self.get_tabs_definition()
        for cat, tab_items in tabs.items():
            if page_name in tab_items:
                tab_key = tab_items[page_name].get("key", page_name)
                # Non-blocking: offload DB write to thread pool
                threading.Thread(
                    target=self.history_manager.increment_usage,
                    args=(tab_key,),
                    daemon=True
                ).start()
                break


    def _update_nav_button_color(self, page_name):
        """
        Update nav button highlights. Also lazy-loads the tab's icon
        if it hasn't been loaded yet (e.g., tab opened programmatically
        before its category was ever expanded).
        """
        prev_active = getattr(self.app_state, '_last_active_nav', None)
        
        # Only update previously-active (if different from new)
        if prev_active and prev_active != page_name:
            btn = self.app_state.nav_buttons.get(prev_active)
            if btn:
                txt = btn.cget("text")
                if "⚠️" not in txt and "🔒" not in txt:
                    # P5: Get icon, lazy-load if needed
                    img = self.app_state.tab_icon_map.get(prev_active)
                    if img is None and prev_active in self.app_state._tab_icon_keys:
                        icon_key = self.app_state._tab_icon_keys.get(prev_active)
                        if icon_key:
                            img = self.icon_images.get(icon_key)
                            if img:
                                self.app_state.tab_icon_map[prev_active] = img
                    btn.configure(
                        fg_color="transparent",
                        text_color=("gray30", "gray80"),
                        font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"),
                        image=img
                    )
        
        # Update newly-active
        btn = self.app_state.nav_buttons.get(page_name)
        if btn:
            txt = btn.cget("text")
            if "⚠️" not in txt and "🔒" not in txt:
                # P5: Get icon, lazy-load if needed
                img = self.app_state.tab_icon_map.get(page_name)
                if img is None and page_name in self.app_state._tab_icon_keys:
                    icon_key = self.app_state._tab_icon_keys.get(page_name)
                    if icon_key:
                        img = self.icon_images.get(icon_key)
                        if img:
                            self.app_state.tab_icon_map[page_name] = img
                btn.configure(
                    fg_color=("#E3F2FD", "#374151"),
                    text_color=("#1565C0", "#60A5FA"),
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    image=img
                )
        
        self.app_state._last_active_nav = page_name



    def _on_category_filter_change(self, selected_display: str):
        self.play_sound("select")
        # Map the translated dropdown value back to the internal English key.
        selected_category = getattr(self, '_cat_internal_map', {}).get(selected_display, selected_display)
        save_config('last_selected_category', selected_category)
        # Search active ho to pehle clear karo — warna search se chhupe
        # buttons category filter ke baad bhi hidden rahenge.
        try:
            if getattr(self, 'nav_search_var', None) is not None and self.nav_search_var.get().strip():
                self.nav_search_var.set("")
                for name, btn in self.app_state.nav_buttons.items():
                    if name == "Home":
                        continue
                    try:
                        if btn.winfo_manager() != "pack":
                            btn.pack(fill="x", padx=5, pady=1)
                    except Exception:
                        pass
        except Exception:
            pass
        self._filter_nav_menu(selected_category)


    def _load_category_icons(self, cat_name):
        """P5: Lazily load nav button icons for a category on first show.
        Each category's icons are loaded exactly once — when its category
        frame is first packed into the sidebar. Subsequent show/hide of
        the same category reuses the cached icons.
        """
        if cat_name == "All Automations":
            # Load icons for all categories that haven't been loaded yet
            for cat in list(self.app_state.category_frames.keys()):
                self._load_category_icons(cat)
            return

        if cat_name in self.app_state._category_icons_loaded:
            return
        cat_frame = self.app_state.category_frames.get(cat_name)
        if not cat_frame:
            return

        # Find all buttons in this category and load their icons
        for name, frame in self.app_state.button_to_category_frame.items():
            if frame is cat_frame:
                icon_key = self.app_state._tab_icon_keys.get(name)
                if icon_key:
                    icon = self.icon_images.get(icon_key)
                    if icon:
                        btn = self.app_state.nav_buttons.get(name)
                        if btn:
                            try:
                                btn.configure(image=icon)
                            except Exception:
                                pass
                        self.app_state.tab_icon_map[name] = icon
        self.app_state._category_icons_loaded.add(cat_name)


    def _filter_nav_menu(self, selected_category: str):
        if selected_category == "All Automations":
            for cat, frame in self.app_state.category_frames.items():
                if frame.winfo_exists() and frame.winfo_manager() != "pack":
                    frame.pack(fill="x", pady=5, padx=2)
                    self._load_category_icons(cat)
        else:
            for cat, frame in self.app_state.category_frames.items():
                if not frame.winfo_exists():
                    continue
                if cat == selected_category:
                    if frame.winfo_manager() != "pack":
                        frame.pack(fill="x", pady=5, padx=2)
                        self._load_category_icons(cat)
                else:
                    if frame.winfo_manager() == "pack":
                        frame.pack_forget()
        
        self.nav_scroll_frame.update_idletasks()

    # ────────────────────────────────────────────────────────────────
    # TAB SEARCH — sidebar me 55 tabs me se dhundho
    # ────────────────────────────────────────────────────────────────

    def _current_tab_instance(self):
        """Currently active tab ka instance (ya None)."""
        try:
            name = getattr(self.app_state, 'current_active_tab', None)
            if not name:
                return None
            return self.app_state.tab_instances.get(name)
        except Exception:
            return None

    def _shortcut_start(self) -> None:
        """Ctrl+Enter → current tab ki automation start karo (agar tab start
        kar sakta hai). Keyboard focus entry/text me ho to skip (typing me
        dastak nahi)."""
        try:
            inst = self._current_tab_instance()
            if inst is None or not hasattr(inst, 'start_automation'):
                return
            # Text entry me typing ho to shortcut trigger na ho
            w = self.focus_get()
            if w is not None:
                cls = w.winfo_class()
                if cls in ("Entry", "Text", "TEntry", "TText"):
                    return
            # Already running ho to double-start mat karo (app-level tracker)
            key = getattr(inst, 'automation_key', None)
            running = getattr(self.app_state, 'active_automations', set())
            if key and key in running:
                return
            inst.start_automation()
        except Exception:
            pass

    def _shortcut_stop(self) -> None:
        """Ctrl+S → current tab ka automation stop karo (agar chal raha hai)."""
        try:
            inst = self._current_tab_instance()
            if inst is None or not hasattr(inst, 'stop_automation'):
                return
            w = self.focus_get()
            if w is not None:
                cls = w.winfo_class()
                if cls in ("Entry", "Text", "TEntry", "TText"):
                    return
            inst.stop_automation()
        except Exception:
            pass

    def _shortcut_retry(self) -> None:
        """Ctrl+R → current tab ke failed entries retry karo."""
        try:
            inst = self._current_tab_instance()
            if inst is None or not hasattr(inst, 'retry_logic_handler'):
                return
            w = self.focus_get()
            if w is not None:
                cls = w.winfo_class()
                if cls in ("Entry", "Text", "TEntry", "TText"):
                    return
            inst.retry_logic_handler()
        except Exception:
            pass

    def _focus_nav_search(self) -> None:
        """Focus the sidebar search box (Ctrl+K shortcut)."""
        entry = getattr(self, 'nav_search_entry', None)
        try:
            if entry is not None and entry.winfo_exists():
                entry.focus_set()
                entry.select_range(0, 'end')  # select all so typing replaces
        except Exception:
            pass

    def _clear_nav_search(self) -> None:
        """Clear search + restore the saved category filter view.

        IMPORTANT: search ke dauran pack_forget() kiye gaye buttons ko pehle
        wapas pack karo — `_filter_nav_menu` sirf category FRAMES manage karta
        hai, buttons nahi. Ye restore na karne par cleared search ke baad
        sidebar ka aadha hissa gayab rehta (until nav rebuild).
        """
        try:
            if getattr(self, 'nav_search_var', None) is not None:
                self.nav_search_var.set("")
            # Search mode me chhupe hue buttons ko wapas pack karo
            for name, btn in self.app_state.nav_buttons.items():
                if name == "Home":
                    continue
                try:
                    if btn.winfo_manager() != "pack":
                        btn.pack(fill="x", padx=5, pady=1)
                except Exception:
                    pass
            self._filter_nav_menu(getattr(self.app_state, 'last_selected_category', 'All Automations'))
        except Exception:
            pass

    def _on_nav_search_change(self, event=None) -> None:
        """
        Sidebar search box ke typing par saare nav buttons filter karo.

        - Query match (case-insensitive) translated name par hota hai
          (aur English internal key par bhi — translated tab dhundhna
          easy ho).
        - Match hone par button pack, warna pack_forget.
        - Category frames jo completely empty ho jaate hain wo hide ho
          jaate hain taaki sidebar clean rahe.
        - Query empty → saved category filter restore hota hai.
        """
        query = self.nav_search_var.get().strip().lower()
        if not query:
            self._clear_nav_search()
            return

        # Filter mode: saare categories show karo (jisse matches kahin bhi dikhe)
        for cat, frame in self.app_state.category_frames.items():
            if frame.winfo_exists() and frame.winfo_manager() != "pack":
                frame.pack(fill="x", pady=5, padx=2)
                self._load_category_icons(cat)

        for name, btn in self.app_state.nav_buttons.items():
            if name == "Home":
                continue  # Home hamesha pinned rahta hai
            try:
                display = self._nav_tab_name(name)
                match = (query in display.lower()
                         or query in name.lower())
                if match:
                    if btn.winfo_manager() != "pack":
                        btn.pack(fill="x", padx=5, pady=1)
                else:
                    if btn.winfo_manager() == "pack":
                        btn.pack_forget()
            except Exception:
                pass

        # Empty ho jaane wale category frames ko hide karo
        for cat, frame in self.app_state.category_frames.items():
            if not frame.winfo_exists():
                continue
            has_visible = False
            for name, btn in self.app_state.nav_buttons.items():
                if self.app_state.button_to_category_frame.get(name) is frame:
                    try:
                        if btn.winfo_manager() == "pack":
                            has_visible = True
                            break
                    except Exception:
                        pass
            if not has_visible and frame.winfo_manager() == "pack":
                frame.pack_forget()

        self.nav_scroll_frame.update_idletasks()







    def show_activity_log_tab(self):
        """
        Navigate to Settings → Activity Log tab.
        Replaces the old popup history window.
        """
        self.show_frame("Settings")
        # After frame loads, switch to the Activity Log sub-tab
        def _switch_tab():
            try:
                settings_instance = self.app_state.tab_instances.get("Settings")
                if settings_instance and hasattr(settings_instance, 'tab_view'):
                    settings_instance.tab_view.set(f"  📋 {tr('settings.tab.activity')}  ")
                    if hasattr(settings_instance, '_refresh_activity_log'):
                        settings_instance._refresh_activity_log()
            except Exception as e:
                logger.debug("Failed to switch to Activity Log tab: %s", e)
        self.after(200, _switch_tab)

    def show_history_window(self):
        """Modern Activity Log window with stats, search, and filtered treeview.
        
        DEPRECATED: Use show_activity_log_tab() instead to redirect to Settings.
        Kept for backward compatibility.
        """
        self.show_activity_log_tab()
        return
    def switch_to_if_edit_with_data(self, data):
        self.workflows.switch_to_if_edit_with_data(data)
    

    def run_work_allocation_from_demand(self, p_name, w_key):
        self.workflows.run_work_allocation_from_demand(p_name, w_key)


    def switch_to_msr_tab_with_data(self, wc, p_name):
        self.workflows.switch_to_msr_tab_with_data(wc, p_name)


    def switch_to_emb_entry_with_data(self, wc, p_name):
        self.workflows.switch_to_emb_entry_with_data(wc, p_name)


    def switch_to_mr_fill_with_data(self, wc, p_name):
        self.workflows.switch_to_mr_fill_with_data(wc, p_name)


    def switch_to_mr_tracking_for_abps(self, location_data=None):
        self.workflows.switch_to_mr_tracking_for_abps(location_data)


    def switch_to_duplicate_mr_with_data(self, wc, p_name):
        self.workflows.switch_to_duplicate_mr_with_data(wc, p_name)


    def switch_to_zero_mr_tab_with_data(self, data_list):
        self.workflows.switch_to_zero_mr_tab_with_data(data_list)


    def send_wagelist_data_and_switch_tab(self, wagelists, auto_start=False):
        self.workflows.send_wagelist_data_and_switch_tab(wagelists, auto_start=auto_start)

