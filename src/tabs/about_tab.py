# tabs/about_tab.py
import tkinter
from tkinter import messagebox
import customtkinter as ctk
import webbrowser
import requests
import threading
from src import config
import os
import sys
import json
from PIL import Image
from datetime import datetime
from urllib.parse import urlencode

# --- MODIFIED IMPORT ---
# Assuming utils.py has resource_path, get_data_path, get_config, save_config
from src.utils import resource_path, get_data_path, get_config, save_config, get_logger, format_bytes
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = get_logger()

# ── License & Terms content ──────────────────────────────────────────────
# Full EULA docs/license.txt se load hota hai (ab build me bundled). Agar
# packaged app me file na mile (purana build), to ye condensed fallback
# dikhta hai — License & Terms tab kabhi khali nahi rahta.
_LICENSE_FALLBACK = """\
NREGA BOT — END USER LICENSE AGREEMENT (SUMMARY)
Copyright (c) 2025-2026 Rajat Poddar (PoddarSolutions). All rights reserved.

The complete End User License Agreement is available at
https://nregabot.com/terms.html and in docs/license.txt.

1. LICENSE GRANT
   You are granted a personal, non-exclusive, non-transferable,
   revocable license to use NREGA Bot on your own device(s), per
   the plan you purchased (Trial / Monthly / Quarterly / Yearly).
   License keys are device-bound and may not be shared or resold.

2. RESTRICTIONS
   You may not sell, rent, redistribute or sublicense the Software
   or its license keys; reverse engineer, decompile or modify it;
   share license keys; or use tools that bypass activation or
   trial restrictions.

3. GOVERNMENT PORTAL USE
   The Software automates data entry on government portals using
   credentials you provide. It does not bypass login or security
   controls. You are solely responsible for the credentials you
   enter, your authority to use the portal, compliance with
   applicable rules, and the accuracy of all data submitted.
   Always verify automated output against official records.

4. USER DATA & PRIVACY (DPDP Act 2023)
   Aadhaar numbers and other sensitive identifiers are NEVER
   stored or transmitted in readable form — they are masked at
   every storage boundary. Portal credentials are never stored.
   Only non-sensitive activity metadata and data you explicitly
   sync (cloud backup, WhatsApp reports) leave your device.

5. DISCLAIMER OF WARRANTIES
   The Software is provided "AS IS" without warranty of any kind.
   The author is not affiliated with any government body and is
   not responsible for portal changes, data entry errors, or any
   consequences of use.

6. LIMITATION OF LIABILITY
   To the maximum extent permitted by law, the author shall not
   be liable for indirect or consequential damages. Total
   aggregate liability is limited to the amount paid in the
   12 months preceding the claim.

7. TERMINATION / REFUNDS
   Violation of these terms revokes your license. Payments are
   generally non-refundable; see https://nregabot.com/refund.html
   for exceptions.

8. GOVERNING LAW
   This agreement is governed by the laws of the Republic of India.

Full terms: https://nregabot.com/terms.html
Contact    : nregabot@gmail.com
"""

_DISCLAIMER_TEXT = """\
DISCLAIMER — NREGA Bot

1. NO GOVERNMENT AFFILIATION
   NREGA Bot is an independent software product. We are not
   affiliated with, endorsed by, or connected to any government
   body, department, or the MGNREGA / VB-G-RAM-G scheme.

2. AUTOMATION OF LIVE GOVERNMENT WEBSITES
   The Software automates data entry on live government portals
   using credentials that YOU provide. It does not bypass login,
   authentication, or security controls — it performs the same
   actions a human operator would perform.
   • You are responsible for the credentials you enter.
   • You must have the authority to access the portal and
     perform the automated operations.
   • You are responsible for compliance with your organization's
     policies and applicable government rules.
   • You are responsible for the accuracy of all data submitted.

3. PORTAL CHANGES
   Government portals may change their structure or policies at
   any time. If the portal changes, some features may break until
   the Software is updated.

4. DATA PRIVACY & AADHAAR (DPDP Act 2023)
   • Portal credentials are never stored.
   • Aadhaar numbers and sensitive identifiers are never stored
     or transmitted in readable form — always masked.
   • Beneficiary data stays on your computer unless you opt into
     cloud features (masked before sync).

5. NO WARRANTY
   The Software is provided "AS IS". Automated output should
   always be verified against official records. The developer is
   not liable for data entry errors, missed entries, portal
   downtime, or any consequences of use.

6. NOT GOVERNMENT ADVICE
   Nothing in the Software or its documentation constitutes
   government advice or endorsement.

Full terms: https://nregabot.com/disclaimer.html
Contact    : nregabot@gmail.com
"""

class AboutTab(ctk.CTkFrame):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.license_info = {}
        self.device_buttons = {} # Store references {machine_id: {'reset': btn, 'edit': btn}}
        self.device_labels = {} # Store references {machine_id: label}
        self.device_name_map = {} # Will be populated by update_subscription_details
        self._referral_code_to_copy = "N/A"

        # ── Header Banner ──
        self._create_header_banner()

        # ── Main Content Area ──
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(1, weight=1)

        self._create_left_frame()
        self._create_right_frame()

    # --- REMOVED ---
    # def _load_device_names(self): ...
    # def _save_device_names(self): ...

    def _get_display_name(self, machine_id):
        """Gets the custom name if available, otherwise returns the machine ID."""
        return self.device_name_map.get(machine_id, machine_id)

    def _create_header_banner(self) -> None:
        """Top header with app branding."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(15, 10))
        header.grid_columnconfigure(2, weight=1)

        # App icon (PNG with emoji fallback)
        _ab_icon = None
        try:
            _ab_icon = self.app.icon_images.get_sized("nrega", (32, 32))
        except Exception:
            _ab_icon = None
        icon_label = ctk.CTkLabel(header, text="🏛️" if _ab_icon is None else "",
                                  image=_ab_icon, font=ctk.CTkFont(size=32))
        icon_label.grid(row=0, column=0, padx=(0, 12))

        # Title block
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            title_frame, text="NREGA Bot",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame, text=f"Version {config.APP_VERSION}  |  Powerful NREGA Automation",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).pack(anchor="w")

        # Server status dot
        self.server_dot = ctk.CTkFrame(header, width=10, height=10, corner_radius=5, fg_color="gray")
        self.server_dot.grid(row=0, column=3, padx=(10, 0))
        self.server_status_label = ctk.CTkLabel(header, text="Checking...", font=ctk.CTkFont(size=10), text_color="gray50")
        self.server_status_label.grid(row=0, column=4, padx=(4, 0))

    def _create_left_frame(self):
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        self.tab_view = ctk.CTkTabview(left_frame, fg_color="transparent")
        self.tab_view.grid(row=1, column=0, sticky="nsew")
        self.tab_view.add("Subscription")
        self.tab_view.add("Changelog")
        self.tab_view.add("Updates")

        # ── SUBSCRIPTION TAB ──
        sub_tab = self.tab_view.tab("Subscription")
        sub_tab.grid_columnconfigure(0, weight=1)
        sub_tab.grid_rowconfigure(2, weight=1)  # Push referral card to bottom

        # ── Welcome Banner Card ──
        self.welcome_card = ctk.CTkFrame(sub_tab, corner_radius=10)
        self.welcome_card.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))
        self.welcome_card.grid_columnconfigure(0, weight=1)

        welcome_top = ctk.CTkFrame(self.welcome_card, fg_color="transparent")
        welcome_top.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(welcome_top, text="👋", font=ctk.CTkFont(size=22)).pack(side="left", padx=(0, 8))
        
        self.welcome_prefix_label = ctk.CTkLabel(welcome_top, text="Welcome", font=ctk.CTkFont(size=16, weight="bold"))
        self.welcome_prefix_label.pack(side="left")
        self.welcome_name_label = ctk.CTkLabel(welcome_top, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.welcome_name_label.pack(side="left", padx=(4, 0))
        self.welcome_suffix_label = ctk.CTkLabel(welcome_top, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.welcome_suffix_label.pack(side="left", padx=(2, 0))

        # ── License Status Card ──
        self.status_card = ctk.CTkFrame(sub_tab, corner_radius=10, border_width=2)
        self.status_card.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.status_card.grid_columnconfigure((0, 1), weight=1)

        # Left side: status badge + days
        left = ctk.CTkFrame(self.status_card, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 14))
        
        self.status_label = ctk.CTkLabel(
            left, text="INACTIVE",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="gray", corner_radius=8,
            text_color="white", padx=16, pady=4
        )
        self.status_label.pack(anchor="w")
        
        ctk.CTkLabel(left, text="License Status", font=ctk.CTkFont(size=10), text_color=("gray50", "gray60")).pack(anchor="w", pady=(6, 0))

        # Right side: plan type + expiry
        right = ctk.CTkFrame(self.status_card, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=18, pady=(14, 14))

        plan_frame = ctk.CTkFrame(right, fg_color="transparent")
        plan_frame.pack(anchor="e")
        ctk.CTkLabel(plan_frame, text="📋", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 6))
        self.plan_type_label = ctk.CTkLabel(plan_frame, text="N/A", font=ctk.CTkFont(size=14, weight="bold"))
        self.plan_type_label.pack(side="left")

        days_frame = ctk.CTkFrame(right, fg_color="transparent")
        days_frame.pack(anchor="e", pady=(6, 0))
        ctk.CTkLabel(days_frame, text="⏱️", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.days_remaining_label = ctk.CTkLabel(days_frame, text="-- days remaining", font=ctk.CTkFont(size=12))
        self.days_remaining_label.pack(side="left")

        ctk.CTkLabel(right, text="Expires On:", font=ctk.CTkFont(size=10), text_color=("gray50", "gray60")).pack(anchor="e", pady=(4, 0))
        self.expires_on_value_label = ctk.CTkLabel(right, text="N/A", font=ctk.CTkFont(size=11, weight="bold"))
        self.expires_on_value_label.pack(anchor="e")

        # ── DETAILS CARD ──
        details_card = ctk.CTkFrame(sub_tab, corner_radius=10)
        details_card.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        details_card.grid_columnconfigure(0, weight=1)

        # Scrollable details area
        details_scroll = ctk.CTkScrollableFrame(details_card, fg_color="transparent")
        details_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        details_scroll.grid_columnconfigure(1, weight=1)

        row_idx = [0]
        def add_detail_row(label_text, default_text, copy_cmd=None, label_kwargs=None):
            """Create a label-value row. Returns the value label for later updates."""
            r = row_idx[0]
            ctk.CTkLabel(
                details_scroll, text=label_text,
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "gray60")
            ).grid(row=r, column=0, sticky="w", padx=(12, 10), pady=6)

            val_frame = ctk.CTkFrame(details_scroll, fg_color="transparent")
            val_frame.grid(row=r, column=1, sticky="ew", padx=(0, 12), pady=6)

            # Create label INSIDE val_frame — avoids mix of grid/pack on details_scroll
            kwargs = {"font": ctk.CTkFont(size=12, weight="bold")}
            if label_kwargs:
                kwargs.update(label_kwargs)
            val_label = ctk.CTkLabel(val_frame, text=default_text, **kwargs)
            val_label.grid(row=0, column=0, sticky="w")

            if copy_cmd:
                copy_btn = ctk.CTkButton(
                    val_frame, text="📋 Copy", width=60, height=22,
                    font=ctk.CTkFont(size=10),
                    fg_color=("#E2E8F0", "#334155"),
                    text_color=("#1E293B", "#F1F5F9"),
                    hover_color=("#CBD5E1", "#475569"),
                    command=copy_cmd
                )
                copy_btn.grid(row=0, column=1, padx=(10, 0))

            row_idx[0] += 1
            return val_label

        # Create all detail rows — widgets are created inside add_detail_row
        self.email_label = add_detail_row("📧 Email:", "N/A")
        self.key_label = add_detail_row("🔑 License Key:", "N/A", self._copy_key,
                                         label_kwargs={"font": ctk.CTkFont(family="monospace", size=11)})
        self.machine_id_label = add_detail_row("💻 Machine ID:", "N/A", self._copy_machine_id,
                                                label_kwargs={"font": ctk.CTkFont(family="monospace", size=11)})
        self.devices_used_label = add_detail_row("📱 Devices:", "N/A")
        self.storage_label = add_detail_row("💾 Storage:", "N/A")

        # Separator
        sep = ctk.CTkFrame(details_scroll, height=1, corner_radius=0, fg_color=("gray85", "gray35"))
        sep.grid(row=row_idx[0], column=0, columnspan=2, sticky="ew", padx=12, pady=6)
        row_idx[0] += 1

        # Referral Code
        self.referral_code_label = add_detail_row("🎁 Referral Code:", "N/A", self._copy_referral_code,
                                                   label_kwargs={
                                                       "font": ctk.CTkFont(family="monospace", size=12, weight="bold"),
                                                       "text_color": ("#2563EB", "#60A5FA")
                                                   })

        # ── REFERRAL INFO BOX (at bottom of tab, outside scroll) ──
        referral_card = ctk.CTkFrame(sub_tab, corner_radius=8, fg_color=("#EFF6FF", "#1E3A5F"))
        referral_card.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(
            referral_card,
            text="🎁 Referral Program",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("#1D4ED8", "#60A5FA")
        ).pack(anchor="w", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            referral_card,
            text="1. Share your referral code with new users.\n"
                 "2. They enter it during trial registration.\n"
                 "3. When they purchase a plan, you get 15 days free!",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray80"),
            wraplength=400,
            justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # --- Changelog Tab ---
        changelog_tab = self.tab_view.tab("Changelog")
        changelog_tab.grid_rowconfigure(0, weight=1); changelog_tab.grid_columnconfigure(0, weight=1)
        self.changelog_text = ctk.CTkTextbox(changelog_tab, wrap=tkinter.WORD, state="disabled")
        self.changelog_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._load_changelog_from_file()

        # --- Updates Tab ---
        update_tab = self.tab_view.tab("Updates")
        update_tab.grid_rowconfigure(5, weight=1) # Allow changelog textbox to expand
        update_tab.grid_columnconfigure(0, weight=1)

        update_wrapper_frame = ctk.CTkFrame(update_tab, fg_color="transparent")
        update_wrapper_frame.grid(row=0, column=0, sticky='nsew', padx=15, pady=15)
        update_wrapper_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(update_wrapper_frame, text="Application Updates", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, pady=(0, 10))
        ctk.CTkLabel(update_wrapper_frame, text="Keep your NREGA Bot up-to-date to get the latest features, bug fixes, and performance improvements.", wraplength=400, justify="center").grid(row=1, column=0, pady=(0, 20))

        status_frame = ctk.CTkFrame(update_wrapper_frame)
        status_frame.grid(row=2, column=0, pady=10, sticky='ew')
        status_frame.grid_columnconfigure(0, weight=1)

        self.current_version_label = ctk.CTkLabel(status_frame, text=f"Current Version: {config.APP_VERSION}")
        self.latest_version_label = ctk.CTkLabel(status_frame, text="Latest Version: Checking...")
        self.current_version_label.pack(pady=2)
        self.latest_version_label.pack(pady=2)

        self.update_button = ctk.CTkButton(update_wrapper_frame, text="Check for Updates", command=self.check_for_updates)
        self.update_button.grid(row=3, column=0, pady=(20, 10), ipady=4, ipadx=10)

        # Beta builds: updates are disabled from version.json
        if config.BETA_BUILD:
            self.update_button.configure(state="disabled", text="Beta Build — No Updates")
            self.latest_version_label.configure(text="Latest Version: Updates disabled (Beta build)")

        self.update_progress = ctk.CTkProgressBar(update_wrapper_frame)
        self.update_progress.set(0) # Initially hidden

        # Widgets for showing new version changelog (initially hidden)
        self.new_version_changelog_label = ctk.CTkLabel(update_tab, text="What's New in the Next Version:", font=ctk.CTkFont(weight="bold"))
        self.new_version_changelog_textbox = ctk.CTkTextbox(update_tab, wrap=tkinter.WORD, state="disabled", fg_color=(config.COLORS["gray90"], config.COLORS["gray20"]))

        versions_url = f"{config.MAIN_WEBSITE_URL}/versions.html"
        versions_link = ctk.CTkLabel(update_tab, text="View Full Version History Online ↗", text_color=(config.COLORS["blue"], config.COLORS["blue_light"]), cursor="hand2")
        versions_link.grid(row=6, column=0, sticky='s', pady=(10, 5))
        versions_link.bind("<Button-1>", lambda e: webbrowser.open(versions_url))

        # --- License & Terms Tab (EULA + Disclaimer) ---
        lt_tab = self.tab_view.add("License & Terms")
        lt_tab.grid_rowconfigure(0, weight=1)
        lt_tab.grid_columnconfigure(0, weight=1)

        self.lt_tabview = ctk.CTkTabview(lt_tab, fg_color="transparent")
        self.lt_tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.lt_tabview.add("End User License Agreement")
        self.lt_tabview.add("Disclaimer")

        # EULA sub-tab
        eula_sub = self.lt_tabview.tab("End User License Agreement")
        eula_sub.grid_rowconfigure(0, weight=1)
        eula_sub.grid_columnconfigure(0, weight=1)
        self.eula_text = ctk.CTkTextbox(eula_sub, wrap=tkinter.WORD, state="disabled",
                                        font=ctk.CTkFont(size=12))
        self.eula_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.eula_text.configure(state="normal")
        self.eula_text.delete("1.0", tkinter.END)
        self.eula_text.insert(tkinter.END, self._load_license_text())
        self.eula_text.configure(state="disabled")

        # Disclaimer sub-tab
        disc_sub = self.lt_tabview.tab("Disclaimer")
        disc_sub.grid_rowconfigure(0, weight=1)
        disc_sub.grid_columnconfigure(0, weight=1)
        self.disclaimer_text = ctk.CTkTextbox(disc_sub, wrap=tkinter.WORD, state="disabled",
                                              font=ctk.CTkFont(size=12))
        self.disclaimer_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.disclaimer_text.configure(state="normal")
        self.disclaimer_text.delete("1.0", tkinter.END)
        self.disclaimer_text.insert(tkinter.END, self._load_disclaimer_text())
        self.disclaimer_text.configure(state="disabled")

    # --- License & Terms content loaders ---
    def _load_license_text(self) -> str:
        """Full EULA docs/license.txt se load karo; na mile to summary fallback."""
        try:
            path = resource_path(os.path.join("docs", "license.txt"))
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return _LICENSE_FALLBACK

    def _load_disclaimer_text(self) -> str:
        return _DISCLAIMER_TEXT

    def update_subscription_details(self, license_info):
        self.license_info = license_info
        
        # --- NEW: Update local device_name_map from server data ---
        if 'device_name_map' in license_info:
            self.device_name_map = license_info.get('device_name_map', {})
        # --- END NEW ---

        # --- Welcome Message ---
        user_name = license_info.get('user_name')
        key_type = license_info.get('key_type')

        if user_name:
            self.welcome_prefix_label.configure(text="Welcome, ")
            self.welcome_name_label.configure(text=user_name)
            self.welcome_suffix_label.configure(text="!")

            if key_type != 'trial': # Premium user styling
                self.welcome_name_label.configure(text_color=(config.COLORS["gold4"], config.COLORS["gold"]), font=ctk.CTkFont(size=18, weight="bold"))
            else: # Trial user styling (default)
                default_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
                self.welcome_name_label.configure(text_color=default_color, font=ctk.CTkFont(size=18, weight="bold"))
        else: # Fallback if no name
            self.welcome_prefix_label.configure(text="Welcome!")
            self.welcome_name_label.configure(text=""); self.welcome_suffix_label.configure(text="")

        self.machine_id_label.configure(text=self.app.machine_id)

        # --- Status and Expiry ---
        expires_at_str = license_info.get('expires_at')
        status, days_remaining, status_color = "Inactive", None, "gray"

        if expires_at_str:
            try:
                expiry_date = datetime.fromisoformat(expires_at_str.split('T')[0]).date()
                delta = expiry_date - datetime.now().date()
                days_remaining = delta.days
                if days_remaining < 0: status, status_color = "Expired", config.COLORS["red_expired"] # Red
                elif days_remaining <= 15: status, status_color = "Expires Soon", config.COLORS["orange_expires"] # Orange
                else: status, status_color = "Active", config.COLORS["green_status"] # Green
            except (ValueError, TypeError): pass

        self.status_label.configure(text=status.upper(), fg_color=status_color)
        if days_remaining is not None:
            if days_remaining < 0: self.days_remaining_label.configure(text=f"Expired {-days_remaining} day{'s' if days_remaining != -1 else ''} ago")
            else: self.days_remaining_label.configure(text=f"{days_remaining} day{'s' if days_remaining != 1 else ''} remaining")
        else: self.days_remaining_label.configure(text="--")

        # --- Other Details ---
        self.plan_type_label.configure(text=f"{str(key_type).capitalize()} Plan" if key_type else 'N/A')
        self.email_label.configure(text=license_info.get('user_email', 'N/A'))
        self.key_label.configure(text=license_info.get('key', 'N/A'))
        self.expires_on_value_label.configure(text=expires_at_str.split('T')[0] if expires_at_str else 'N/A')

        max_devices = license_info.get('max_devices', 1)
        activated_machines_str = license_info.get('activated_machines', '')
        activated_count = len([mid for mid in activated_machines_str.split(',') if mid]) if activated_machines_str else 0
        self.devices_used_label.configure(text=f"{activated_count} of {max_devices} used")

        # --- MODIFIED ---
        full_key = license_info.get('key', 'N/A')
        referral_code = full_key.split('-')[-1] if '-' in full_key else full_key
        self.referral_code_label.configure(text=referral_code)
        self._referral_code_to_copy = referral_code # Store for copy function
        # --- END MODIFIED ---

        self.update_storage_display(license_info.get('total_usage'), license_info.get('max_storage'))

        self._update_action_panel(status, key_type)

    def _create_right_frame(self):
        self.action_panel_container = ctk.CTkFrame(self)
        self.action_panel_container.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.action_panel_container.grid_columnconfigure(0, weight=1)
        self.action_panel_container.grid_rowconfigure(0, weight=1)
        self._update_action_panel("Loading", "N/A")

    def _create_disclaimer_frame(self, parent):
        """Card-style disclaimer with warning accent and emoji icons (safe across all versions)."""
        disclaimer_frame = ctk.CTkFrame(
            parent,
            corner_radius=10,
            border_width=1,
            border_color=("#FDE68A", "#78350F"),  # amber border
            fg_color=("#FFFBEB", "#1C1917")  # amber-tinted bg in light, dark warm in dark
        )
        disclaimer_frame.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(disclaimer_frame, fg_color="transparent")
        header.pack(pady=(12, 8), padx=16, anchor="w", fill="x")
        ctk.CTkLabel(header, text="⚠️", font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(header, text="Disclaimer", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#92400E", "#FBBF24")).pack(side="left")

        # Row 1
        row1 = ctk.CTkFrame(disclaimer_frame, fg_color="transparent")
        row1.pack(pady=(0, 8), padx=16, anchor="w", fill="x")
        ctk.CTkLabel(row1, text="⚡", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8), pady=2, anchor="n")
        ctk.CTkLabel(
            row1, text="This tool interacts with a live government website. "
                       "If the portal's structure changes, some features may break until updated.",
            wraplength=300, justify="left",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).pack(side="left", fill="x", expand=True)

        # Row 2
        row2 = ctk.CTkFrame(disclaimer_frame, fg_color="transparent")
        row2.pack(pady=(0, 14), padx=16, anchor="w", fill="x")
        ctk.CTkLabel(row2, text="🔧", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8), pady=2, anchor="n")
        ctk.CTkLabel(
            row2, text="Use this tool responsibly. The author provides no warranties "
                       "and is not liable for data entry errors. Always double-check automated work.",
            wraplength=300, justify="left",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).pack(side="left", fill="x", expand=True)

        return disclaimer_frame

    def _update_action_panel(self, status, key_type):
        # Only rebuild if panel type actually changed — prevents 2-4 sec blink
        current_type = getattr(self, '_current_panel_type', None)
        current_status = getattr(self, '_current_panel_status', None)
        
        if current_type == key_type and current_status == status:
            # Same panel — just update device names / labels in-place
            return
        
        self._current_panel_type = key_type
        self._current_panel_status = status
        
        # Clear previous widgets and reset button/label references
        for widget in self.action_panel_container.winfo_children():
            widget.destroy()
        self.device_buttons.clear()
        self.device_labels.clear()

        def create_manage_button(parent):
            # (Keep this helper function as is)
            def open_manage_url():
                # Secure path: signed token fetch → browser (raw key kabhi
                # URL mein nahi). User ka account page bina login khul jata hai.
                self.app.open_web_page('account')
            return ctk.CTkButton(parent, text="Manage on Website", fg_color="transparent", border_width=1, text_color=(config.COLORS["gray10"], config.COLORS["text_bright"]), command=open_manage_url)

        # --- Trial Panel ---
        if key_type == 'trial':
            # (Keep this section as is)
            panel = ctk.CTkFrame(self.action_panel_container, border_color=config.COLORS["blue"], border_width=2) # Blue border
            panel.grid(row=0, column=0, sticky="nsew")
            panel.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(panel, text="Trial Version Active", font=ctk.CTkFont(size=16, weight="bold"), text_color=config.COLORS["blue"]).pack(pady=(20,10), padx=20)
            ctk.CTkLabel(panel, text="Upgrade to a full license to unlock all features permanently and remove limitations.", wraplength=300, justify="center").pack(pady=5, padx=20)
            ctk.CTkButton(panel, text="Upgrade to Full License", command=lambda: self.app.show_purchase_window(context='upgrade')).pack(pady=20, ipady=5)
            button_container = ctk.CTkFrame(panel, fg_color="transparent")
            button_container.pack(fill='x', padx=10, pady=(0, 15))
            button_container.grid_columnconfigure(0, weight=1)
            create_manage_button(button_container).grid(row=0, column=0, sticky="ew")
            self._create_disclaimer_frame(panel).pack(side='bottom', fill='x', pady=15, padx=10)
            return

        # --- Expired / Expires Soon Panel ---
        elif status in ["Expired", "Expires Soon"]:
            # (Keep this section as is)
            border_color = config.COLORS["red_expired"] if status == "Expired" else config.COLORS["orange_expires"] # Red or Orange border
            panel = ctk.CTkFrame(self.action_panel_container, border_color=border_color, border_width=2)
            panel.grid(row=0, column=0, sticky="nsew")
            panel.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(panel, text="Your License Needs Attention!", font=ctk.CTkFont(size=16, weight="bold"), text_color=border_color).pack(pady=(20,10), padx=20)
            ctk.CTkLabel(panel, text="Renew your subscription to continue using all features without interruption.", wraplength=300, justify="center").pack(pady=5, padx=20)
            ctk.CTkButton(panel, text="Renew Subscription Now", command=lambda: self.app.show_purchase_window(context='renew')).pack(pady=20, ipady=5)
            self._create_disclaimer_frame(panel).pack(side='bottom', fill='x', pady=15, padx=10)
            return

        # --- Active Paid License Panel ---
        panel = ctk.CTkFrame(self.action_panel_container)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        # ── Compact Account Management Header ──
        header_card = ctk.CTkFrame(panel, corner_radius=10, fg_color="transparent")
        header_card.pack(fill="x", padx=18, pady=(14, 4))

        title_frame = ctk.CTkFrame(header_card, fg_color="transparent")
        title_frame.pack(anchor="w")
        ctk.CTkLabel(title_frame, text="👤", font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(title_frame, text="Account Management", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")

        ctk.CTkLabel(
            header_card,
            text="Rename your devices using the ✏️ icon.",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            wraplength=320, justify="left"
        ).pack(anchor="w", pady=(3, 0))

        scroll_area = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        scroll_area.pack(expand=True, fill="both", padx=14, pady=(6, 0))

        max_devices = self.license_info.get('max_devices', 1)
        activated_machines_str = self.license_info.get('activated_machines', '')
        activated_machines = [mid for mid in activated_machines_str.split(',') if mid]
        activated_count = len(activated_machines)

        if not activated_machines:
            empty_card = ctk.CTkFrame(scroll_area, corner_radius=8, fg_color=("gray95", "gray25"))
            empty_card.pack(pady=15, padx=10, fill="x")
            ctk.CTkLabel(empty_card, text="📭 No devices activated yet.",
                         font=ctk.CTkFont(size=12),
                         text_color="gray50").pack(pady=15)
        else:
            for machine_id in activated_machines:
                is_current_device = (machine_id == self.app.machine_id)
                display_name = self._get_display_name(machine_id)

                # Compact device card
                device_entry_frame = ctk.CTkFrame(
                    scroll_area,
                    corner_radius=6,
                    border_width=1,
                    border_color=("#22C55E", "#166534") if is_current_device else ("#E5E7EB", "#374151"),
                    fg_color=("#F0FDF4", "#052E16") if is_current_device else "transparent"
                )
                device_entry_frame.pack(fill="x", pady=(0, 4))

                # Left: device info
                label_frame = ctk.CTkFrame(device_entry_frame, fg_color="transparent")
                label_frame.pack(side="left", fill="x", expand=True, padx=10, pady=6)

                name_row = ctk.CTkFrame(label_frame, fg_color="transparent")
                name_row.pack(anchor="w", fill="x")

                device_icon = "💻" if not is_current_device else "🖥️"
                ctk.CTkLabel(name_row, text=device_icon, font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 4))

                device_label = ctk.CTkLabel(
                    name_row, text=display_name,
                    anchor="w", font=ctk.CTkFont(size=11, weight="bold")
                )
                device_label.pack(side="left")

                if is_current_device:
                    ctk.CTkLabel(
                        name_row, text="THIS DEVICE",
                        font=ctk.CTkFont(size=7, weight="bold"),
                        fg_color=("#22C55E", "#16A34A"),
                        text_color="white",
                        corner_radius=3, padx=5, pady=1
                    ).pack(side="left", padx=(5, 0))

                if display_name != machine_id:
                    ctk.CTkLabel(
                        label_frame, text=machine_id,
                        anchor="w",
                        font=ctk.CTkFont(family="monospace", size=8),
                        text_color=("gray50", "gray60")
                    ).pack(anchor="w", padx=(15, 0))

                self.device_labels[machine_id] = device_label

                # Right: edit button only
                edit_btn = ctk.CTkButton(
                    device_entry_frame,
                    text="✏️", width=28, height=26,
                    font=ctk.CTkFont(size=11),
                    fg_color="transparent",
                    hover_color=("gray80", "gray30"),
                    command=lambda mid=machine_id: self._rename_device_popup(mid),
                )
                edit_btn.pack(side="right", padx=(0, 6))

                self.device_buttons[machine_id] = {'edit': edit_btn}

        # ── Bottom: Disclaimer + Action Buttons ──
        bottom_frame = ctk.CTkFrame(panel)
        bottom_frame.pack(fill='x', side='bottom')

        self._create_disclaimer_frame(bottom_frame).pack(fill='x', padx=10, pady=(10, 0))

        button_container = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        button_container.pack(fill='x', padx=12, pady=(10, 14))
        button_container.grid_columnconfigure((0, 1), weight=1)

        # Manage on Website button
        manage_btn = create_manage_button(button_container)
        manage_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        # Contact Support button
        support_btn = ctk.CTkButton(
            button_container, text="📧 Contact Support",
            fg_color="transparent", border_width=1,
            text_color=(config.COLORS["gray10"], config.COLORS["text_bright"]),
            command=self.contact_support_email
        )
        support_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))


    # Deactivation request removed — users can manage devices from their account on the website.


    def update_storage_display(self, usage, limit):
        if usage is not None and limit is not None and limit > 0:
            usage_str = format_bytes(usage)
            limit_str = format_bytes(limit)
            self.storage_label.configure(text=f"{usage_str} of {limit_str}")
        else:
            usage_str = format_bytes(usage if usage is not None else 0)
            self.storage_label.configure(text=f"{usage_str} Used (Limit N/A)")

    # --- NEW/MODIFIED: Popup for renaming device ---
    def _rename_device_popup(self, machine_id):
        
        current_name = self._get_display_name(machine_id)
        
        # --- Create a custom dialog window ---
        dialog = ctk.CTkToplevel(self)
        dialog.title("Rename Device")
        dialog.attributes("-topmost", True) # Keep it on top

        # --- Center Manually (Optional but recommended) ---
        try:
            main_geo = self.app.geometry() # e.g., "1100x800+100+100"
            main_parts = main_geo.split('+')
            main_size = main_parts[0].split('x')
            main_w, main_h = int(main_size[0]), int(main_size[1])
            main_x, main_y = int(main_parts[1]), int(main_parts[2])
            dialog_w, dialog_h = 350, 200 # Increased width for text
            center_x = main_x + (main_w // 2) - (dialog_w // 2)
            center_y = main_y + (main_h // 2) - (dialog_h // 2)
            dialog.geometry(f"{dialog_w}x{dialog_h}+{center_x}+{center_y}")
        except Exception as e:
            print(f"Could not center dialog: {e}") # Non-critical error
            dialog.geometry("350x200") # Fallback

        dialog.resizable(False, False)
        dialog.grab_set() # Make it modal

        # --- Store result ---
        result = {"value": None} # Use a dict to pass by reference

        # --- Add widgets ---
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=15, pady=15)
        main_frame.grid_columnconfigure(0, weight=1)

        # Problem 2 Fix: Add wraplength and better text
        prompt_text = f"Enter a name for this device:\n(MAC: {machine_id})"
        prompt_label = ctk.CTkLabel(main_frame, text=prompt_text, wraplength=320, justify="center")
        prompt_label.grid(row=0, column=0, columnspan=2, pady=(0, 15))

        # This is our own entry, not from the dialog
        entry = ctk.CTkEntry(main_frame, width=320)
        entry.grid(row=1, column=0, columnspan=2, pady=(0, 20))
        
        # Problem 1 Fix: Pre-fill our own entry
        if current_name != machine_id:
            entry.insert(0, current_name)
        
        entry.focus_set() # Focus the entry box

        def on_ok():
            result["value"] = entry.get()
            dialog.grab_release()
            dialog.destroy()

        def on_cancel():
            result["value"] = None # Explicitly set to None
            dialog.grab_release()
            dialog.destroy()
            
        dialog.protocol("WM_DELETE_WINDOW", on_cancel) # Handle 'X' button

        ok_button = ctk.CTkButton(main_frame, text="Ok", command=on_ok, width=150,
                                  fg_color=config.COLORS["blue"], hover_color=config.COLORS["blue_hover"])
        ok_button.grid(row=2, column=0, padx=(0, 5))
        
        cancel_button = ctk.CTkButton(main_frame, text="Cancel", command=on_cancel, width=150,
                                      fg_color="gray50", hover_color="gray60")
        cancel_button.grid(row=2, column=1, padx=(5, 0))
        
        # --- Make it blocking ---
        self.app.wait_window(dialog)

        new_name = result["value"]
        # --- End custom dialog ---

        if new_name is not None: # User didn't cancel
            new_name_clean = new_name.strip()
            
            # Start background thread to save the name
            self._send_rename_request_api(machine_id, new_name_clean)

    # --- NEW: API call to save device name ---
    def _send_rename_request_api(self, machine_id, new_name):
        buttons = self.device_buttons.get(machine_id)
        if not buttons or not buttons.get('edit'): return
        button = buttons['edit'] # Get the edit button

        original_text = button.cget("text") # Store original emoji
        button.configure(state="disabled", text="...") # Indicate submitting

        def _worker():
            try:
                license_key = self.app.license_info.get('key')
                if not license_key: raise ValueError("License key not found.")

                headers = {'Authorization': f'Bearer {license_key}'}
                payload = {'machine_id': machine_id, 'name': new_name}
                
                # Use the *same* endpoint as the web page
                response = self.app.http_session.post(
                    f"{config.LICENSE_SERVER_URL}/api/set-device-name",
                    json=payload, headers=headers, timeout=15
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status") == "success":
                    # --- SYNC: Update local state and UI ---
                    self.device_name_map[machine_id] = new_name
                    self.app.after(0, self._update_device_label_text, machine_id)
                    # --- END SYNC ---
                else:
                    self.app.after(0, lambda: messagebox.showerror("Request Failed", result.get("reason", "Unknown server error."), parent=self))

            except Exception as e:
                self.app.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=self))
            finally:
                # --- FIX: Check if button still exists before configuring ---
                def safe_re_enable_button():
                    if button.winfo_exists():
                        button.configure(state="normal", text=original_text)
                
                self.app.after(0, safe_re_enable_button)
                # --- END FIX ---

        threading.Thread(target=_worker, daemon=True).start()

    # --- NEW: Helper to update label text (called by rename functions) ---
    def _update_device_label_text(self, machine_id):
        label = self.device_labels.get(machine_id)
        if label:
            display_name = self._get_display_name(machine_id)
            is_current_device = (machine_id == self.app.machine_id)
            label_text = display_name + (" (This Device)" if is_current_device else "")
            
            # --- MODIFIED: Update label text and potentially show/hide MAC ---
            label.configure(text=label_text)
            
            # Find the parent (label_frame)
            label_frame = label.master
            # Find the MAC label (second child, if it exists)
            mac_label = label_frame.winfo_children()[1] if len(label_frame.winfo_children()) > 1 else None

            if display_name != machine_id:
                # Custom name exists, make sure MAC label is visible
                if not mac_label:
                    ctk.CTkLabel(label_frame, text=machine_id, anchor="w", font=ctk.CTkFont(family="monospace", size=10), text_color="gray50").pack(side="top", anchor="w")
                else:
                    mac_label.configure(text=machine_id) # Just in case
            else:
                # No custom name, hide the MAC label if it exists
                if mac_label:
                    mac_label.destroy() # Remove the redundant MAC label
            # --- END MODIFIED ---

    def contact_support_email(self):
        # (Keep this method as is)
        user_name = self.license_info.get('user_name', 'N/A')
        license_key = self.license_info.get('key', 'N/A')
        subject = "NREGA Bot Support Request"
        body = (f"Hello Support Team,\n\n[Please describe your issue here]\n\n--- My License Details for Reference ---\nName: {user_name}\nLicense Key: {license_key}\nApp Version: {config.APP_VERSION}\nMachine ID: {self.app.machine_id}")
        self._open_mailto_url(subject, body)

    def _open_mailto_url(self, subject, body):
        # (Keep this method as is)
        params = {'subject': subject, 'body': body}
        encoded_params = urlencode(params)
        mailto_url = f"mailto:{config.SUPPORT_EMAIL}?{encoded_params}"
        try: webbrowser.open(mailto_url)
        except Exception as e: messagebox.showerror("Error", f"Could not open email client. Please manually email {config.SUPPORT_EMAIL}.\n\nError: {e}")

    def _copy_key(self):
        # (Keep this method as is)
        key_to_copy = self.key_label.cget("text")
        if key_to_copy and key_to_copy != "N/A":
            self.app.clipboard_clear(); self.app.clipboard_append(key_to_copy)
            messagebox.showinfo("Copied", "License key copied to clipboard.")

    # --- START: MODIFIED COPY REFERRAL METHOD ---
    def _copy_referral_code(self):
        code_to_copy = getattr(self, '_referral_code_to_copy', 'N/A') # Use the stored value
        if code_to_copy and code_to_copy != "N/A":
            self.app.clipboard_clear()
            self.app.clipboard_append(code_to_copy)
            messagebox.showinfo("Copied", "Referral code copied to clipboard.")
    # --- END: MODIFIED COPY REFERRAL METHOD ---

    def _copy_machine_id(self):
        # (Keep this method as is)
        self.app.clipboard_clear(); self.app.clipboard_append(self.app.machine_id)
        messagebox.showinfo("Copied", "Machine ID copied to clipboard.")

    def check_for_updates(self):
        if config.BETA_BUILD:
            self.latest_version_label.configure(text="Updates are disabled in this Beta build.")
            return
        self.update_button.configure(state="disabled", text="Checking...")
        self.app.check_for_updates_background()

    def download_and_install_update(self, url, version):
        # (Keep this method as is)
        self.app.download_and_install_update(url, version)

    def show_new_version_changelog(self, changelog_notes):
        # (Keep this method as is)
        self.new_version_changelog_label.grid(row=4, column=0, pady=(15, 5), padx=5, sticky='w')
        self.new_version_changelog_textbox.grid(row=5, column=0, sticky='nsew', padx=5, pady=(0,5))
        self.new_version_changelog_textbox.configure(state="normal")
        self.new_version_changelog_textbox.delete("1.0", tkinter.END)
        if changelog_notes:
            for change in changelog_notes: self.new_version_changelog_textbox.insert(tkinter.END, f"• {change}\n")
        else: self.new_version_changelog_textbox.insert(tkinter.END, "Changelog not available for this version.")
        self.new_version_changelog_textbox.configure(state="disabled")

    def hide_new_version_changelog(self):
        # (Keep this method as is)
        self.new_version_changelog_label.grid_forget()
        self.new_version_changelog_textbox.grid_forget()

    def _load_changelog_from_file(self):
        # (Keep this method as is)
        changelog_content = {}
        try:
            changelog_path = resource_path(os.path.join("docs", "changelog.json"))
            with open(changelog_path, 'r', encoding='utf-8') as f: changelog_content = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e: changelog_content = {"Error": [f"Could not load changelog.json: {e}"]}
        self.changelog_text.configure(state="normal")
        self.changelog_text.delete("1.0", tkinter.END)
        self.changelog_text.tag_config("bold", underline=True)
        for version, changes in changelog_content.items():
            self.changelog_text.insert(tkinter.END, f"Version {version}\n", "bold")
            for change in changes: self.changelog_text.insert(tkinter.END, f"  • {change}\n")
            self.changelog_text.insert(tkinter.END, "\n")
        self.changelog_text.configure(state="disabled")