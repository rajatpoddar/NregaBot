# tabs/about_tab.py
import tkinter
from tkinter import messagebox
import customtkinter as ctk
import webbrowser
import requests
import threading
import config
import os
import sys
import json
import humanize
from PIL import Image
from datetime import datetime
from urllib.parse import urlencode

# --- MODIFIED IMPORT ---
# Assuming utils.py has resource_path, get_data_path, get_config, save_config
from utils import resource_path, get_data_path, get_config, save_config

# --- REMOVED ---
# DEVICE_NAMES_FILE = 'device_names.json'

class AboutTab(ctk.CTkFrame):
    def __init__(self, parent, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.license_info = {}
        self.device_buttons = {} # Store references {machine_id: {'reset': btn, 'edit': btn}}
        self.device_labels = {} # Store references {machine_id: label}
        # --- MODIFIED: Load from license_info, not local file ---
        self.device_name_map = {} # Will be populated by update_subscription_details
        self._referral_code_to_copy = "N/A" # <-- YEH LINE ADD KAREIN
        

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(0, weight=1)

        self._create_left_frame()
        self._create_right_frame()

    # --- REMOVED ---
    # def _load_device_names(self): ...
    # def _save_device_names(self): ...

    def _get_display_name(self, machine_id):
        """Gets the custom name if available, otherwise returns the machine ID."""
        # --- MODIFIED: Use device_name_map ---
        return self.device_name_map.get(machine_id, machine_id)

    def _create_left_frame(self):
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(left_frame, fg_color="transparent")
        self.tab_view.grid(row=0, column=0, sticky="nsew")
        self.tab_view.add("Subscription")
        self.tab_view.add("Changelog")
        self.tab_view.add("Updates")

        # --- Subscription Tab ---
        sub_tab = self.tab_view.tab("Subscription")
        sub_tab.grid_columnconfigure(0, weight=1)

        sub_frame = ctk.CTkFrame(sub_tab, fg_color="transparent")
        sub_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        sub_frame.grid_columnconfigure(1, weight=1)

        welcome_frame = ctk.CTkFrame(sub_frame, fg_color="transparent")
        welcome_frame.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        self.welcome_prefix_label = ctk.CTkLabel(welcome_frame, text="Welcome!", font=ctk.CTkFont(size=18, weight="bold"))
        self.welcome_prefix_label.pack(side="left")

        self.welcome_name_label = ctk.CTkLabel(welcome_frame, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.welcome_name_label.pack(side="left", padx=(5, 0))

        self.welcome_suffix_label = ctk.CTkLabel(welcome_frame, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.welcome_suffix_label.pack(side="left")

        status_bar = ctk.CTkFrame(sub_frame, fg_color="transparent")
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))
        self.status_label = ctk.CTkLabel(status_bar, text="INACTIVE", font=ctk.CTkFont(size=12, weight="bold"), fg_color="gray", corner_radius=6, text_color="white")
        self.status_label.pack(side="left", padx=(0, 10), ipady=3, ipadx=8)
        self.days_remaining_label = ctk.CTkLabel(status_bar, text="-- days remaining", text_color="gray50")
        self.days_remaining_label.pack(side="left")

        details_frame = ctk.CTkFrame(sub_frame, fg_color="transparent")
        details_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 20))
        details_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(details_frame, text="Plan Type:", text_color="gray50").grid(row=0, column=0, sticky="w")
        self.plan_type_label = ctk.CTkLabel(details_frame, text="N/A", font=ctk.CTkFont(weight="bold"))
        self.plan_type_label.grid(row=0, column=1, sticky="w", padx=10)

        ctk.CTkLabel(details_frame, text="Email:", text_color="gray50").grid(row=1, column=0, sticky="w", pady=(5,0))
        self.email_label = ctk.CTkLabel(details_frame, text="N/A", font=ctk.CTkFont(weight="bold"))
        self.email_label.grid(row=1, column=1, sticky="w", padx=10, pady=(5,0))

        ctk.CTkLabel(details_frame, text="License Key:", text_color="gray50").grid(row=2, column=0, sticky="w", pady=(5,0))
        key_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        key_frame.grid(row=2, column=1, sticky="ew", padx=10, pady=(5,0))
        self.key_label = ctk.CTkLabel(key_frame, text="N/A", font=ctk.CTkFont(family="monospace"))
        self.key_label.pack(side="left")
        ctk.CTkButton(key_frame, text="Copy", width=50, command=self._copy_key).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(details_frame, text="Expires On:", text_color="gray50").grid(row=3, column=0, sticky="w", pady=(5,0))
        self.expires_on_value_label = ctk.CTkLabel(details_frame, text="N/A", font=ctk.CTkFont(weight="bold"))
        self.expires_on_value_label.grid(row=3, column=1, sticky="w", padx=10, pady=(5,0))

        ctk.CTkLabel(details_frame, text="Devices Used:", text_color="gray50").grid(row=4, column=0, sticky="w", pady=(5,0))
        self.devices_used_label = ctk.CTkLabel(details_frame, text="N/A", font=ctk.CTkFont(weight="bold"))
        self.devices_used_label.grid(row=4, column=1, sticky="w", padx=10, pady=(5,0))

        ctk.CTkLabel(details_frame, text="Storage Used:", text_color="gray50").grid(row=5, column=0, sticky="w", pady=(5,0))
        self.storage_label = ctk.CTkLabel(details_frame, text="N/A", font=ctk.CTkFont(weight="bold"))
        self.storage_label.grid(row=5, column=1, sticky="w", padx=10, pady=(5,0))

        ctk.CTkLabel(details_frame, text="Machine ID:", text_color="gray50").grid(row=6, column=0, sticky="w", pady=(5,0))
        machine_id_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        machine_id_frame.grid(row=6, column=1, sticky="ew", padx=10, pady=(5,0))
        self.machine_id_label = ctk.CTkLabel(machine_id_frame, text="N/A", font=ctk.CTkFont(family="monospace"))
        self.machine_id_label.pack(side="left")
        ctk.CTkButton(machine_id_frame, text="Copy", width=50, command=self._copy_machine_id).pack(side="left", padx=(10, 0))

        # --- START: NEW REFERRAL CODE ROW ---
        ctk.CTkLabel(details_frame, text="Referral Code:", text_color="gray50").grid(row=7, column=0, sticky="w", pady=(5,0))
        referral_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        referral_frame.grid(row=7, column=1, sticky="ew", padx=10, pady=(5,0))
        
        self.referral_code_label = ctk.CTkLabel(referral_frame, text="N/A", font=ctk.CTkFont(family="monospace"))
        self.referral_code_label.pack(side="left")
        
        self.copy_referral_btn = ctk.CTkButton(referral_frame, text="Copy", width=50, command=self._copy_referral_code)
        self.copy_referral_btn.pack(side="left", padx=(10, 0))
        # --- END: NEW REFERRAL CODE ROW ---

        # --- START: NEW REFERRAL INFO BOX ---
        info_frame = ctk.CTkFrame(details_frame, fg_color=("gray90", "gray20"))
        info_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=0, pady=(15, 0))
        
        info_text = "How the Referral Program Works:\n" \
            "1. Share your 'Referral Code' (given above) with new users.\n" \
            "2. When the new user registers for a trial, they will enter your code.\n" \
            "3. When that user purchases their first plan after the trial,\n" \
            "   you will get 15 days of free validity!"
        
        ctk.CTkLabel(info_frame, text=info_text, wraplength=300, justify="left", anchor="w").pack(padx=12, pady=10)
        # --- END: NEW REFERRAL INFO BOX ---

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

        self.update_progress = ctk.CTkProgressBar(update_wrapper_frame)
        self.update_progress.set(0) # Initially hidden

        # Widgets for showing new version changelog (initially hidden)
        self.new_version_changelog_label = ctk.CTkLabel(update_tab, text="What's New in the Next Version:", font=ctk.CTkFont(weight="bold"))
        self.new_version_changelog_textbox = ctk.CTkTextbox(update_tab, wrap=tkinter.WORD, state="disabled", fg_color=("gray90", "gray20"))

        versions_url = f"{config.MAIN_WEBSITE_URL}/versions.html"
        versions_link = ctk.CTkLabel(update_tab, text="View Full Version History Online ↗", text_color=("#3B82F6", "#60A5FA"), cursor="hand2")
        versions_link.grid(row=6, column=0, sticky='s', pady=(10, 5))
        versions_link.bind("<Button-1>", lambda e: webbrowser.open(versions_url))

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
                self.welcome_name_label.configure(text_color=("gold4", "#FFD700"), font=ctk.CTkFont(size=18, weight="bold"))
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
                if days_remaining < 0: status, status_color = "Expired", "#E53E3E" # Red
                elif days_remaining <= 15: status, status_color = "Expires Soon", "#DD6B20" # Orange
                else: status, status_color = "Active", "#38A169" # Green
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
        self.action_panel_container.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.action_panel_container.grid_columnconfigure(0, weight=1)
        self.action_panel_container.grid_rowconfigure(0, weight=1)
        self._update_action_panel("Loading", "N/A")

    def _create_disclaimer_frame(self, parent):
        disclaimer_frame = ctk.CTkFrame(parent, fg_color=("gray90", "gray20"))
        disclaimer_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(disclaimer_frame, text="Disclaimer", image=self.app.icon_images.get("disclaimer_warning"), compound="left", font=ctk.CTkFont(weight="bold"))
        title_label.pack(pady=(10, 5), padx=20, anchor="w")

        def create_disclaimer_row(parent_frame, icon_key, text):
            row_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            icon_label = ctk.CTkLabel(row_frame, text="", image=self.app.icon_images.get(icon_key))
            icon_label.pack(side="left", padx=(0, 10), pady=2, anchor="n")
            text_label = ctk.CTkLabel(row_frame, text=text, wraplength=280, justify="left")
            text_label.pack(side="left", fill="x", expand=True)
            return row_frame

        disclaimer_text1 = "This tool interacts with a live government website. If the portal's structure changes, some features may break until updated."
        row1 = create_disclaimer_row(disclaimer_frame, "disclaimer_thunder", disclaimer_text1)
        row1.pack(pady=(0, 10), padx=20, anchor="w", fill="x")

        disclaimer_text2 = "Use this tool responsibly. The author provides no warranties and is not liable for data entry errors. Always double-check automated work."
        row2 = create_disclaimer_row(disclaimer_frame, "disclaimer_tools", disclaimer_text2)
        row2.pack(pady=(0, 15), padx=20, anchor="w", fill="x")

        return disclaimer_frame

    def _update_action_panel(self, status, key_type):
        # Clear previous widgets and reset button/label references
        for widget in self.action_panel_container.winfo_children():
            widget.destroy()
        self.device_buttons.clear()
        self.device_labels.clear()

        def create_manage_button(parent):
            # (Keep this helper function as is)
            def open_manage_url():
                if self.license_info.get('key'):
                    auth_url = f"{config.LICENSE_SERVER_URL}/authenticate-from-app/{self.license_info['key']}"
                    webbrowser.open_new_tab(auth_url)
                else: messagebox.showerror("Error", "License key not found.")
            return ctk.CTkButton(parent, text="Manage on Website", fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=open_manage_url)

        # --- Trial Panel ---
        if key_type == 'trial':
            # (Keep this section as is)
            panel = ctk.CTkFrame(self.action_panel_container, border_color="#3B82F6", border_width=2) # Blue border
            panel.grid(row=0, column=0, sticky="nsew")
            panel.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(panel, text="Trial Version Active", font=ctk.CTkFont(size=16, weight="bold"), text_color="#3B82F6").pack(pady=(20,10), padx=20)
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
            border_color = "#E53E3E" if status == "Expired" else "#DD6B20" # Red or Orange border
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

        ctk.CTkLabel(panel, text="Account Management", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20,10), padx=20)

        devices_frame = ctk.CTkFrame(panel, fg_color="transparent")
        devices_frame.pack(expand=True, fill="both", padx=15, pady=(0, 10))

        max_devices = self.license_info.get('max_devices', 1)
        activated_machines_str = self.license_info.get('activated_machines', '')
        activated_machines = [mid for mid in activated_machines_str.split(',') if mid]
        activated_count = len(activated_machines)

        ctk.CTkLabel(devices_frame, text=f"Activated Devices ({activated_count} of {max_devices} used)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(devices_frame, text="Assign names to devices or request reset (admin approval needed, 1 req/30 days/device).", wraplength=300, justify="left", text_color="gray50").pack(anchor="w", pady=(0, 10))

        scroll_area = ctk.CTkScrollableFrame(devices_frame, fg_color="transparent")
        scroll_area.pack(expand=True, fill="both")

        if not activated_machines:
            ctk.CTkLabel(scroll_area, text="No devices activated yet.", text_color="gray50").pack(pady=10)
        else:
            for machine_id in activated_machines:
                is_current_device = (machine_id == self.app.machine_id)
                device_entry_frame = ctk.CTkFrame(scroll_area, fg_color=("gray85", "gray20"))
                device_entry_frame.pack(fill="x", pady=(0, 5))
                
                # --- MODIFIED: Display logic for name/mac ---
                display_name = self._get_display_name(machine_id)
                
                label_frame = ctk.CTkFrame(device_entry_frame, fg_color="transparent")
                label_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)

                label_text = display_name + (" (This Device)" if is_current_device else "")
                device_label = ctk.CTkLabel(label_frame, text=label_text, anchor="w", font=ctk.CTkFont(weight="bold"))
                device_label.pack(side="top", anchor="w")
                
                if display_name != machine_id: # Also show MAC if name is custom
                    ctk.CTkLabel(label_frame, text=machine_id, anchor="w", font=ctk.CTkFont(family="monospace", size=10), text_color="gray50").pack(side="top", anchor="w")
                
                self.device_labels[machine_id] = device_label # Store main label
                # --- END MODIFIED ---

                button_frame = ctk.CTkFrame(device_entry_frame, fg_color="transparent")
                button_frame.pack(side="right", padx=(0, 5))

                # --- UPDATED: Use PNG Icons instead of Emojis ---
                edit_btn = ctk.CTkButton(
                    button_frame,
                    text="",  # Text hata diya
                    image=self.app.icon_images.get("device_edit"), # PNG Icon use kiya
                    command=lambda mid=machine_id: self._rename_device_popup(mid),
                    width=35, 
                    height=30,
                    fg_color="transparent",
                    hover_color=("gray75", "gray25")
                )
                edit_btn.pack(side="left", padx=(0, 2))

                reset_btn = ctk.CTkButton(
                    button_frame,
                    text="", # Text hata diya
                    image=self.app.icon_images.get("device_reset"), # PNG Icon use kiya
                    command=lambda mid=machine_id: self._send_deactivation_request_api(mid),
                    width=35, 
                    height=30,
                    fg_color="transparent",
                    hover_color=("gray75", "gray25")
                )
                reset_btn.pack(side="left")
                # --- END UPDATE ---

                self.device_buttons[machine_id] = {'reset': reset_btn, 'edit': edit_btn}

        self._check_pending_deactivations(activated_machines)

        bottom_frame = ctk.CTkFrame(panel)
        bottom_frame.pack(fill='x', side='bottom')

        self._create_disclaimer_frame(bottom_frame).pack(fill='x', padx=10, pady=(10,0))

        button_container = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        button_container.pack(fill='x', padx=10, pady=(10, 15))
        button_container.grid_columnconfigure((0, 1), weight=1)

        create_manage_button(button_container).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(button_container, text="Contact Support", fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=self.contact_support_email).grid(row=0, column=1, sticky="ew", padx=(5, 0))


    # --- MODIFIED: _send_deactivation_request_api ---
    def _send_deactivation_request_api(self, machine_id):
        buttons = self.device_buttons.get(machine_id)
        if not buttons or not buttons.get('reset'): return
        button = buttons['reset'] # Get the specific reset button

        if button.cget("state") == "disabled": return

        if not messagebox.askyesno("Confirm Deactivation Request",
                                   f"Request deactivation for device:\n\n{self._get_display_name(machine_id)}\n({machine_id})\n\nAdmin must approve. Once per 30 days/device.",
                                   parent=self):
            return

        original_text = button.cget("text") # Store original emoji
        button.configure(state="disabled", text="...") # Indicate submitting

        def _worker():
            try:
                license_key = self.app.license_info.get('key')
                if not license_key: raise ValueError("License key not found.")

                headers = {'Authorization': f'Bearer {license_key}'}
                payload = {'machine_id': machine_id}
                response = requests.post(
                    f"{config.LICENSE_SERVER_URL}/api/request-deactivation",
                    json=payload, headers=headers, timeout=15
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status") == "success":
                    message = result.get("message", "Request sent successfully.")
                    # Keep button disabled, maybe change emoji or add tooltip later if needed
                    self.app.after(0, lambda: button.configure(text="⏳")) # Optional: Pending emoji
                    self.app.after(0, lambda: messagebox.showinfo("Request Submitted", message, parent=self))
                else:
                    self.app.after(0, lambda: button.configure(state="normal", text=original_text)) # Restore emoji on API error
                    self.app.after(0, lambda: messagebox.showerror("Request Failed", result.get("reason", "Unknown server error."), parent=self))

            except requests.exceptions.HTTPError as http_err:
                error_reason = f"HTTP Error: {http_err.response.status_code}"
                try: error_reason = http_err.response.json().get("reason", error_reason)
                except Exception: pass
                self.app.after(0, lambda: button.configure(state="normal", text=original_text)) # Restore emoji
                self.app.after(0, lambda: messagebox.showerror("Request Failed", error_reason, parent=self))
            except requests.exceptions.RequestException as req_err:
                self.app.after(0, lambda: button.configure(state="normal", text=original_text)) # Restore emoji
                self.app.after(0, lambda: messagebox.showerror("Connection Error", f"Could not send request: {req_err}", parent=self))
            except Exception as e:
                self.app.after(0, lambda: button.configure(state="normal", text=original_text)) # Restore emoji
                self.app.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=self))

        threading.Thread(target=_worker, daemon=True).start()


    def update_storage_display(self, usage, limit):
        if usage is not None and limit is not None and limit > 0:
            usage_str = humanize.naturalsize(usage)
            limit_str = humanize.naturalsize(limit)
            self.storage_label.configure(text=f"{usage_str} of {limit_str}")
        else:
            usage_str = humanize.naturalsize(usage if usage is not None else 0)
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
                                  fg_color="#3B82F6", hover_color="#2563EB")
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
                response = requests.post(
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


    def _check_pending_deactivations(self, machine_ids):
        # Placeholder - needs backend API support to be fully functional
        pass

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
        # (Keep this method as is)
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
            changelog_path = resource_path("changelog.json")
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