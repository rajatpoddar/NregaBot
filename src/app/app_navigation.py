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


logger = get_logger()


class NavMixin:
    """Mixin: navigation buttons, tab management, frame switching."""

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
            text="  Home",
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
        
        self.category_filter_var = ctk.StringVar()
        self.category_filter_menu = ctk.CTkOptionMenu(
            header_parent,
            variable=self.category_filter_var,
            values=categories,
            command=self._on_category_filter_change,
            width=180, height=28,
        )
        self.category_filter_var.set(self.app_state.last_selected_category)
        self.category_filter_menu.pack(fill="x", pady=(5, 5), padx=5)

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

            cat_frame = CollapsibleFrame(content_parent, title=cat)
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
                    text=f"{name}", 
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
                        text=f"{name} ⚠️",
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
            text="Failed to Load Tab",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_white"])
        ).pack(pady=(5, 5))
        
        # --- Tab Name ---
        ctk.CTkLabel(
            container,
            text=f"'{page_name}'",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"])
        ).pack(pady=(0, 15))
        
        # --- Explanation ---
        ctk.CTkLabel(
            container,
            text="This tab encountered an error while loading.\nPlease check the details below or try again.",
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
            text="🔄 Retry",
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
            text="🏠 Go Home",
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
            text="▼ Show Technical Details",
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
                details_btn.configure(text="▲ Hide Technical Details")
            else:
                details_text.pack_forget()
                details_btn.configure(text="▼ Show Technical Details")
        
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



    def _on_category_filter_change(self, selected_category: str):
        self.play_sound("select")
        save_config('last_selected_category', selected_category)
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
                    settings_instance.tab_view.set("  📋 Activity Log  ")
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
        # --- FIX: Single instance guard ---
        if self.app_state._history_window and self.app_state._history_window.winfo_exists():
            self.app_state._history_window.lift()
            self.app_state._history_window.focus_force()
            return

        win = ctk.CTkToplevel(self)
        win.title("📋 Activity Log - Recent Tasks")
        win.geometry("900x650")
        win.minsize(700, 500)

        # --- FIX: Bring window to front ---
        win.transient(self)
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(100, lambda: safe_attr(win, "-topmost", False))

        def safe_attr(w, attr, val):
            try:
                if w.winfo_exists():
                    w.attributes(attr, val)
            except Exception as e:
                logger.debug("Failed to set window attr %s: %s", attr, e)

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (900 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (650 // 2)
        win.geometry(f"+{x}+{y}")

        # --- FIX: Track this window globally ---
        self.app_state._history_window = win
        def on_close():
            self.app_state._history_window = None
            try:
                win.destroy()
            except Exception as e:
                logger.debug("Failed to destroy history window: %s", e)
        win.protocol("WM_DELETE_WINDOW", on_close)

        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(3, weight=1)

        # ---------- 1. HEADER ----------
        header = ctk.CTkFrame(win, fg_color="transparent", height=50)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="📋", font=ctk.CTkFont(size=24)
        ).grid(row=0, column=0, padx=(0, 10))

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            title_frame, text="Activity Log", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame, text="Track all your automation activities",
            font=ctk.CTkFont(size=11), text_color=("gray50", "gray60")
        ).pack(anchor="w")

        # ---------- 2. STATS CARDS (Optimized) ----------
        stats_frame = ctk.CTkFrame(win, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(5, 10))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stats")

        # Fetch logs to compute stats
        all_logs = self.history_manager.get_recent_activity(200)
        total = len(all_logs)
        success_count = sum(1 for _, t, _ in all_logs if t == "SUCCESS")
        warning_count = sum(1 for _, t, _ in all_logs if t == "WARNING")
        error_count = sum(1 for _, t, _ in all_logs if t == "ERROR")

        def create_stat_card(parent, col, label, count, icon, bg_color, text_color, hover_bg):
            card = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=12, height=85,
                                border_width=1, border_color=("white", "#333333"))
            card.grid(row=0, column=col, sticky="nsew", padx=4)
            card.grid_propagate(False)

            # Hover effect
            def on_enter(e):
                card.configure(fg_color=hover_bg)
            def on_leave(e):
                card.configure(fg_color=bg_color)
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.place(relx=0.5, rely=0.5, anchor="center")

            ctk.CTkLabel(inner, text=icon, font=ctk.CTkFont(size=24)).pack()
            ctk.CTkLabel(
                inner, text=str(count), font=ctk.CTkFont(size=22, weight="bold"),
                text_color=text_color
            ).pack()
            ctk.CTkLabel(
                inner, text=label, font=ctk.CTkFont(size=11),
                text_color=("gray20", "gray80")
            ).pack()

        create_stat_card(stats_frame, 0, "Total Actions", total, "📊",
                         ("#F0F4FF", "#1E293B"), ("#3B82F6", "#60A5FA"),
                         ("#DBEAFE", "#0F172A"))
        create_stat_card(stats_frame, 1, "Success", success_count, "✅",
                         ("#F0FDF4", "#14532D"), ("#16A34A", "#4ADE80"),
                         ("#DCFCE7", "#052E16"))
        create_stat_card(stats_frame, 2, "Warnings", warning_count, "⚠️",
                         ("#FFFBEB", "#451A03"), ("#D97706", "#FBBF24"),
                         ("#FEF3C7", "#292524"))
        create_stat_card(stats_frame, 3, "Errors", error_count, "❌",
                         ("#FEF2F2", "#450A0A"), ("#DC2626", "#F87171"),
                         ("#FEE2E2", "#7F1D1D"))

        # ---------- 3. SEARCH & FILTER + ACTION BUTTONS ----------
        controls_frame = ctk.CTkFrame(win, fg_color="transparent")
        controls_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        controls_frame.grid_columnconfigure(0, weight=1)

        # Left: Search + Filter
        left_controls = ctk.CTkFrame(controls_frame, fg_color="transparent")
        left_controls.pack(side="left", fill="x", expand=True)

        search_var = tkinter.StringVar()
        search_entry = ctk.CTkEntry(
            left_controls, placeholder_text="🔍 Search activity...",
            width=250, height=32,
            font=ctk.CTkFont(size=12)
        )
        search_entry.pack(side="left", padx=(0, 10))

        filter_var = tkinter.StringVar(value="All")
        filter_menu = ctk.CTkOptionMenu(
            left_controls, values=["All", "✅ Success", "⚠️ Warning", "❌ Error"],
            variable=filter_var, width=130, height=32,
            font=ctk.CTkFont(size=12),
            dropdown_font=ctk.CTkFont(size=12)
        )
        filter_menu.pack(side="left")

        # Right: Action Buttons
        right_controls = ctk.CTkFrame(controls_frame, fg_color="transparent")
        right_controls.pack(side="right")

        def refresh_log():
            on_close()
            self.show_history_window()

        def clear_log():
            if messagebox.askyesno("Clear Activity Log?",
                                   "This will permanently delete all activity logs.\nAre you sure?",
                                   parent=win):
                try:
                    conn = self.history_manager._get_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM activity_log")
                    conn.commit()
                    conn.close()
                    refresh_log()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to clear logs: {e}", parent=win)

        def export_log():
            if not all_logs:
                messagebox.showinfo("No Data", "No logs to export.", parent=win)
                return
            reports_dir = self.get_nregabot_path("Reports")
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text File", "*.txt"), ("CSV File", "*.csv")],
                initialdir=reports_dir,
                initialfile=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                parent=win
            )
            if not file_path:
                return
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    if file_path.endswith(".csv"):
                        f.write("Timestamp,Type,Description\n")
                        for ts, tp, desc in all_logs:
                            safe_desc = desc.replace('"', '""')
                            f.write(f'"{ts}","{tp}","{safe_desc}"\n')
                    else:
                        f.write("=" * 80 + "\n")
                        f.write(f"  ACTIVITY LOG - {datetime.now().strftime('%d-%b-%Y %I:%M %p')}\n")
                        f.write(f"  Total: {total} | Success: {success_count} | Warnings: {warning_count} | Errors: {error_count}\n")
                        f.write("=" * 80 + "\n\n")
                        for ts, tp, desc in all_logs:
                            icon = {"SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(tp, "📌")
                            f.write(f"{ts} | {icon} [{tp}] {desc}\n")
                messagebox.showinfo("Exported", f"Log saved to:\n{file_path}", parent=win)
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}", parent=win)

        ctk.CTkButton(
            right_controls, text="🔄 Refresh", width=90, height=32,
            command=refresh_log,
            font=ctk.CTkFont(size=12),
            fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"),
            hover_color=("#CBD5E1", "#475569")
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            right_controls, text="🗑️ Clear", width=80, height=32,
            command=clear_log,
            font=ctk.CTkFont(size=12),
            fg_color=("#FEE2E2", "#450A0A"),
            text_color=("#DC2626", "#F87171"),
            hover_color=("#FECACA", "#7F1D1D")
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            right_controls, text="📥 Export", width=90, height=32,
            command=export_log,
            font=ctk.CTkFont(size=12),
            fg_color=("#DBEAFE", "#1E3A5F"),
            text_color=("#1D4ED8", "#60A5FA"),
            hover_color=("#BFDBFE", "#1E40AF")
        ).pack(side="left", padx=2)

        # ---------- 4. LOG ENTRIES (Treeview List) ----------
        log_container = ctk.CTkFrame(win, fg_color="transparent")
        log_container.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 10))
        log_container.grid_rowconfigure(0, weight=1)
        log_container.grid_columnconfigure(0, weight=1)

        # Treeview frame
        tree_frame = ctk.CTkFrame(log_container, fg_color="transparent")
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Style the treeview for dark/light mode
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            tv_bg = "#2b2b2b"
            tv_fg = "#e5e7eb"
            tv_hover = "#3f3f46"
            tv_sel = "#3B82F6"
            tv_header_bg = "#1f2937"
            tv_header_fg = "#ffffff"
        else:
            tv_bg = "#ffffff"
            tv_fg = "#374151"
            tv_hover = "#f3f4f6"
            tv_sel = "#3B82F6"
            tv_header_bg = "#f9fafb"
            tv_header_fg = "#111827"

        tree_style = ttk.Style()
        tree_style.theme_use("clam")
        tree_style.configure("ActivityLog.Treeview",
                             background=tv_bg,
                             foreground=tv_fg,
                             fieldbackground=tv_bg,
                             rowheight=28,
                             font=("Segoe UI", 11),
                             borderwidth=0)
        tree_style.map("ActivityLog.Treeview",
                       background=[('selected', tv_sel), ('active', tv_hover)],
                       foreground=[('selected', 'white'), ('active', tv_fg)])
        tree_style.configure("ActivityLog.Treeview.Heading",
                             background=tv_header_bg,
                             foreground=tv_header_fg,
                             relief="flat",
                             font=("Segoe UI", 11, "bold"))
        tree_style.map("ActivityLog.Treeview.Heading",
                       background=[('active', tv_hover)])

        # Treeview widget
        columns = ("type", "timestamp", "description")
        log_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                style="ActivityLog.Treeview", selectmode="browse", height=8)

        log_tree.heading("type", text="Type", anchor="w")
        log_tree.heading("timestamp", text="Timestamp", anchor="w")
        log_tree.heading("description", text="Description", anchor="w")

        log_tree.column("type", width=115, minwidth=90, anchor="w", stretch=False)
        log_tree.column("timestamp", width=165, minwidth=120, anchor="w", stretch=False)
        log_tree.column("description", width=400, minwidth=200, anchor="w", stretch=True)

        log_tree.grid(row=0, column=0, sticky="nsew")

        # Vertical scrollbar
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=log_tree.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        log_tree.configure(yscrollcommand=v_scroll.set)

        # Horizontal scrollbar
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=log_tree.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")
        log_tree.configure(xscrollcommand=h_scroll.set)

        # Tag colors
        log_tree.tag_configure('success_tag', foreground='#16A34A' if mode == 'Light' else '#4ADE80')
        log_tree.tag_configure('warning_tag', foreground='#D97706' if mode == 'Light' else '#FBBF24')
        log_tree.tag_configure('error_tag', foreground='#DC2626' if mode == 'Light' else '#F87171')
        log_tree.tag_configure('default_tag', foreground=tv_fg)

        # Internal storage for current data
        _all_data = list(all_logs)  # copy so we can re-filter

        def populate_tree(data_rows, search_text="", filter_text="All"):
            """Clears and fills the treeview with filtered rows."""
            for item in log_tree.get_children():
                log_tree.delete(item)

            filtered = []
            for ts, tp, desc in data_rows:
                # Type filter
                if filter_text == "✅ Success" and tp != "SUCCESS":
                    continue
                elif filter_text == "⚠️ Warning" and tp != "WARNING":
                    continue
                elif filter_text == "❌ Error" and tp != "ERROR":
                    continue
                # Search filter
                if search_text and search_text not in ts.lower() and search_text not in desc.lower():
                    continue
                filtered.append((ts, tp, desc))

            # Insert rows
            for ts, tp, desc in filtered:
                type_icon = {"SUCCESS": "✅ SUCCESS", "WARNING": "⚠️ WARNING", "ERROR": "❌ ERROR"}.get(tp, "📌")
                tag = {'SUCCESS': 'success_tag', 'WARNING': 'warning_tag', 'ERROR': 'error_tag'}.get(tp, 'default_tag')
                log_tree.insert("", "end", values=(type_icon, ts, desc), tags=(tag,))

            # Update footer
            shown = len(filtered)
            text = f"Showing {shown} of {len(data_rows)} total records"
            if shown != len(data_rows):
                text += " (filtered)"
            footer_label.configure(text=text)

        # Sorting
        def sort_tree(col_key, reverse):
            items = [(log_tree.set(k, col_key), k) for k in log_tree.get_children('')]
            try:
                items.sort(key=lambda t: float(t[0]) if t[0] else 0, reverse=reverse)
            except (ValueError, TypeError):
                items.sort(reverse=reverse)
            for index, (_, k) in enumerate(items):
                log_tree.move(k, '', index)
            # Toggle header command
            new_reverse = not reverse
            log_tree.heading(col_key, command=lambda c=col_key: sort_tree(c, new_reverse))

        log_tree.heading("type", command=lambda: sort_tree("type", False))
        log_tree.heading("timestamp", command=lambda: sort_tree("timestamp", True))
        log_tree.heading("description", command=lambda: sort_tree("description", False))

        # ---------- 5. FOOTER (Created BEFORE initial populate to avoid NameError) ----------
        footer_frame = ctk.CTkFrame(win, fg_color="transparent", height=26)
        footer_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 15))

        footer_label = ctk.CTkLabel(
            footer_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        footer_label.pack(side="left")
        ctk.CTkLabel(
            footer_frame,
            text="Click column headers to sort | Cleanup keeps latest 1000",
            font=ctk.CTkFont(size=10),
            text_color=("gray60", "gray70")
        ).pack(side="right")

        # Initial population (AFTER footer_label exists)
        populate_tree(_all_data)

        # Wire up search & filter
        def on_filter_change(*args):
            s = search_var.get().strip().lower()
            f = filter_var.get()
            populate_tree(_all_data, search_text=s, filter_text=f)

        search_var.trace_add("write", on_filter_change)
        filter_var.trace_add("write", on_filter_change)


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


    def send_wagelist_data_and_switch_tab(self, start, end, auto_start=False):
        self.workflows.send_wagelist_data_and_switch_tab(start, end, auto_start=auto_start)

