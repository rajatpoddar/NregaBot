# app_license.py — License & Authentication Mixin
#
# P3: Extracted from main_app.py to reduce file size.
# Uses mixin pattern: inheriting class (NregaBotApp) provides
# all instance variables and non-license methods via self.

import threading
import os
import json
import webbrowser
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import tkinter
from tkinter import messagebox
import customtkinter as ctk
import requests
from PIL import Image
from src import config
from src.utils import (
    resource_path, get_data_path, get_user_downloads_path,
    get_config, save_config, get_logger, parse_version
)
from src.location_data import STATE_DISTRICT_MAP

logger = get_logger()


class LicenseMixin:
    """Mixin: license validation, activation, feature flags, alerts."""

    # ------------------------------------------------------------------
    # LICENSE CHECK & ACTIVATION FLOW
    # ------------------------------------------------------------------

    def perform_license_check_flow(self) -> None:
        self.app_state.is_licensed = self.check_license()
        self.after(0, self._setup_licensed_ui if self.app_state.is_licensed else self._setup_unlicensed_ui)

    def _preload_and_update_about_tab(self) -> None:
        if "About" not in self.app_state.tab_instances:
            self.show_frame("About", raise_frame=False)
        self._update_about_tab_info()
        self.update_idletasks()

    def check_license(self) -> bool:
        return self.services.check_license()

    def validate_on_server(self, key: str, is_startup_check: bool = False) -> bool:
        return self.services.validate_on_server(key, is_startup_check)

    # ------------------------------------------------------------------
    # LICENSED / UNLICENSED UI SETUP
    # ------------------------------------------------------------------

    def _setup_licensed_ui(self) -> None:
        self._unlock_app()
        try:
            self.app_state.global_disabled_features = self.app_state.license_info.get('global_disabled_features', [])
            key_type = str(self.app_state.license_info.get('key_type', '')).lower()
            if key_type == 'trial':
                if 'trial_restricted_features' in self.app_state.license_info:
                    self.app_state.trial_restricted_features = self.app_state.license_info['trial_restricted_features']
                else:
                    self.app_state.trial_restricted_features = [
                        "Sarkar Aapke Dwar", "SAD Update Status", "FTO Generation",
                        "MR Gen", "MR Fill", "MR Payment", "Gen Wagelist",
                        "Send Wagelist", "Demand", "Allocation", "Work Allocation",
                        "eMB Entry", "eMB Verify", "WC Gen", "IF Editor"
                    ]
            else:
                self.app_state.trial_restricted_features = []
            self._apply_feature_flags()
        except Exception as e:
            logger.error("Error applying local restrictions: %s", e)

        is_expiring = self.check_expiry_and_notify()
        self._preload_and_update_about_tab()
        self._ping_server_in_background()
        try:
            self.show_frame("Home" if not is_expiring else "About")
        except Exception as e:
            logger.warning("Failed to show default frame: %s", e)
            try:
                first_tab = list(list(self.get_tabs_definition().values())[0].keys())[0]
                self.show_frame("About" if is_expiring else first_tab)
            except Exception as e2:
                logger.warning("Failed to show fallback frame: %s", e2)
                self.show_frame("About")
        self._sync_location_from_server()
        self.check_for_updates_background()
        self.set_status("Ready")
        self.after(500, self.run_onboarding_if_needed)

    def _setup_unlicensed_ui(self) -> None:
        self._preload_and_update_about_tab()
        self.set_status("Activation Required")
        if self.show_activation_window():
            self.app_state.is_licensed = True
            self._setup_licensed_ui()
        else:
            self.on_closing(force=True)

    def _sync_location_from_server(self) -> None:
        """
        Server se aaye user_state/user_district/user_block ko
        history manager mein save karo taake automation tabs
        mein dropdown mein dikhe.
        """
        try:
            lic = self.app_state.license_info
            state = (lic.get('user_state') or '').strip().upper()
            dist  = (lic.get('user_district') or '').strip().upper()
            block = (lic.get('user_block') or '').strip().upper()

            synced = []
            if state:
                self.history_manager.save_entry("location_state", state)
                self.history_manager.save_entry("mr_track_state", state)
                self.history_manager.save_entry("issued_mr_state", state)
                self.history_manager.save_entry("mis_state", state)
                self.history_manager.save_entry("dashboard_state", state)
                synced.append(f"State: {state}")
            if dist:
                self.history_manager.save_entry("location_district", dist)
                self.history_manager.save_entry("mr_track_district", dist)
                self.history_manager.save_entry("issued_mr_district", dist)
                self.history_manager.save_entry("mis_district", dist)
                self.history_manager.save_entry("dashboard_district", dist)
                synced.append(f"District: {dist}")
            if block:
                self.history_manager.save_entry("location_block", block)
                self.history_manager.save_entry("mr_track_block", block)
                self.history_manager.save_entry("issued_mr_block", block)
                self.history_manager.save_entry("mis_block", block)
                self.history_manager.save_entry("dashboard_block", block)
                synced.append(f"Block: {block}")

            if synced:
                logger.info("Location synced from server: %s", ", ".join(synced))
            else:
                logger.debug("No location data found on server to sync.")
        except Exception as e:
            logger.debug("Failed to sync location from server: %s", e)

    # ------------------------------------------------------------------
    # ACTIVATION WINDOW
    # ------------------------------------------------------------------

    def show_activation_window(self) -> bool:
        win = ctk.CTkToplevel(self); win.title(f"{config.APP_SHORT_NAME} - Activate")
        win.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(500, sw-40), min(600, sh-40)
        win.geometry(f'{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}')
        win.resizable(False, False); win.transient(self); win.grab_set()

        # --- Main container ---
        outer = ctk.CTkFrame(win, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=24, pady=20)

        activated = tkinter.BooleanVar(value=False)

        # Progress bar (shown during validation)
        progress_bar = ctk.CTkProgressBar(outer, height=4, corner_radius=2,
                                           mode="indeterminate")
        progress_bar.pack(fill="x", pady=(0, 5))
        progress_bar.pack_forget()  # hidden initially

        # ==============================================================
        # SLOTS FULL UI — replaces entire window content
        # ==============================================================
        def show_slots_full_ui(data):
            for widget in outer.winfo_children():
                widget.destroy()

            # Warning header
            ctk.CTkLabel(outer, text="⚠️  All Device Slots Full",
                         font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=config.COLORS["red_expired"]).pack(pady=(5, 2))
            ctk.CTkLabel(outer, text="Deactivate an old device to activate this one.",
                         font=ctk.CTkFont(size=12)).pack(pady=(0, 15))

            # Device list
            device_frame = ctk.CTkFrame(outer, fg_color="transparent")
            device_frame.pack(fill="x", pady=5)
            temp_key = data.get('license_key')
            devices = data.get('devices', [])

            for dev in devices:
                row = ctk.CTkFrame(device_frame,
                                   fg_color=(config.COLORS["gray90"], config.COLORS["gray30"]),
                                   corner_radius=8)
                row.pack(fill="x", pady=4, padx=5)

                info_frame = ctk.CTkFrame(row, fg_color="transparent")
                info_frame.pack(side="left", padx=12, pady=8, fill="x", expand=True)

                ctk.CTkLabel(info_frame, text=dev['name'],
                             font=ctk.CTkFont(size=13, weight="bold"),
                             anchor="w").pack(fill="x")

                if dev['name'] != dev['id']:
                    ctk.CTkLabel(info_frame, text=f"ID: {dev['id']}",
                                 font=ctk.CTkFont(size=10),
                                 text_color="gray60", anchor="w").pack(fill="x")

                if dev.get('is_pending'):
                    ctk.CTkLabel(row, text="⏳  Pending Approval",
                                 text_color=config.COLORS["device_pending_text"],
                                 font=ctk.CTkFont(size=12, weight="bold")
                                 ).pack(side="right", padx=15)
                else:
                    remove_btn = ctk.CTkButton(row, text="Request Removal",
                                                width=120, height=30,
                                                fg_color=config.COLORS["btn_stop"],
                                                hover_color=config.COLORS["btn_stop_hover"],
                                                font=ctk.CTkFont(size=12))
                    remove_btn.pack(side="right", padx=10)

                    def request_remove(mid=dev['id'], btn=remove_btn):
                        if not messagebox.askyesno("Confirm",
                                                    f"Request removal of device\n\n{mid}?",
                                                    parent=win):
                            return
                        btn.configure(state="disabled", text="Sending...")

                        def _req_thread():
                            try:
                                headers = {'Authorization': f'Bearer {temp_key}'}
                                resp = self.app_state.http_session.post(
                                    f"{config.LICENSE_SERVER_URL}/api/request-deactivation",
                                    json={'machine_id': mid}, headers=headers, timeout=10)
                                res = resp.json()
                                if resp.status_code == 200 and res.get("status") == "success":
                                    self.after(0, lambda: [
                                        messagebox.showinfo("Success",
                                            "Request Sent! Admin will review it.",
                                            parent=win),
                                        win.destroy()
                                    ])
                                else:
                                    self.after(0, lambda: [
                                        messagebox.showerror("Error",
                                            res.get("reason", "Failed"), parent=win),
                                        btn.configure(state="normal", text="Request Removal")
                                    ])
                            except Exception as e:
                                self.after(0, lambda: [
                                    messagebox.showerror("Error", str(e), parent=win),
                                    btn.configure(state="normal", text="Request Removal")
                                ])

                        threading.Thread(target=_req_thread, daemon=True).start()

                    remove_btn.configure(
                        command=lambda m=dev['id'], fn=request_remove: fn(m))

            # Contact info
            ct_frame = ctk.CTkFrame(outer, fg_color="transparent")
            ct_frame.pack(fill="x", pady=(20, 0))
            ctk.CTkLabel(ct_frame, text="Need help? Contact us:",
                         font=ctk.CTkFont(size=12, weight="bold")).pack()

            email_lbl = ctk.CTkLabel(ct_frame,
                                      text="📧  nregabot@gmail.com",
                                      text_color=(config.COLORS["blue"], config.COLORS["blue_light"]),
                                      cursor="hand2", font=ctk.CTkFont(size=12))
            email_lbl.pack(pady=2)
            email_lbl.bind("<Button-1>", lambda e: webbrowser.open("mailto:nregabot@gmail.com"))

            wa_lbl = ctk.CTkLabel(ct_frame,
                                   text="💬  Join WhatsApp Community",
                                   text_color=config.COLORS["whatsapp_green"],
                                   cursor="hand2", font=ctk.CTkFont(size=12, weight="bold"))
            wa_lbl.pack(pady=2)
            wa_lbl.bind("<Button-1>", lambda e: webbrowser.open(
                "https://chat.whatsapp.com/Bup3hDCH3wn2shbUryv8wn"))

            ctk.CTkButton(outer, text="←  Back",
                          command=lambda: [win.destroy(), self.show_activation_window()],
                          fg_color="gray", width=120,
                          font=ctk.CTkFont(size=12)).pack(pady=20)

        # ==============================================================
        # BRANDING HEADER
        # ==============================================================
        brand = ctk.CTkFrame(outer, fg_color="transparent")
        brand.pack(fill="x", pady=(0, 15))

        try:
            logo_img = ctk.CTkImage(Image.open(resource_path("assets/logo.png")),
                                     size=(42, 42))
            ctk.CTkLabel(brand, image=logo_img, text="").pack(side="left", padx=(0, 10))
        except Exception:
            ctk.CTkLabel(brand, text="🏛️", font=ctk.CTkFont(size=28)).pack(side="left", padx=(0, 10))

        text_col = ctk.CTkFrame(brand, fg_color="transparent")
        text_col.pack(side="left")
        ctk.CTkLabel(text_col, text=f"{config.APP_NAME}",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(text_col, text="Activate your license to get started",
                     font=ctk.CTkFont(size=11), text_color="gray60",
                     anchor="w").pack(fill="x")

        # ==============================================================
        # TAB VIEW: License Key  |  Email & OTP
        # ==============================================================
        tab_view = ctk.CTkTabview(outer, corner_radius=8)
        tab_view.pack(fill="both", expand=True, pady=(0, 12))

        # -------- TAB 1: License Key --------
        tab_key = tab_view.add("🔑  License Key")

        key_inner = ctk.CTkFrame(tab_key, fg_color="transparent")
        key_inner.pack(expand=True, fill="both", padx=16, pady=(16, 10))

        ctk.CTkLabel(key_inner, text="Already own a license?",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(key_inner, text="Paste your key below to activate instantly.",
                     font=ctk.CTkFont(size=11), text_color="gray60",
                     anchor="w").pack(fill="x", pady=(0, 12))

        key_entry = ctk.CTkEntry(key_inner, placeholder_text="e.g. NREGABOT-MONTHLY-XXXXXXXX",
                                  font=ctk.CTkFont(size=13))
        key_entry.pack(fill="x", ipady=4, pady=(0, 4))
        if get_config('last_used_license_key'):
            key_entry.insert(0, get_config('last_used_license_key'))

        # Inline status for key tab
        key_status = ctk.CTkLabel(key_inner, text="", font=ctk.CTkFont(size=11), anchor="w")
        key_status.pack(fill="x", pady=(0, 8))

        def on_key_activate():
            key_val = key_entry.get().strip()
            if not key_val:
                self.play_sound("error")
                key_status.configure(text="⚠️  Please enter a license key.",
                                     text_color=("#DC2626", "#EF4444"))
                return

            # Show progress
            progress_bar.pack(fill="x", pady=(0, 8), before=tab_view)
            progress_bar.start()
            key_status.configure(text="⏳  Validating your license...",
                                 text_color=("#2563EB", "#60A5FA"))
            key_activate_btn.configure(state="disabled", text="⏳ Validating...")

            def _key_activate_thread():
                try:
                    payload = {
                        "key": key_val,
                        "machine_id": self.app_state.machine_id,
                        "app_version": config.APP_VERSION_WIRE
                    }
                    resp = self.app_state.http_session.post(
                        f"{config.LICENSE_SERVER_URL}/api/validate",
                        json=payload, timeout=15)
                    try:
                        data = resp.json()
                    except Exception:
                        raise Exception(
                            f"Server returned an unexpected response (status {resp.status_code}).")

                    self.after(0, self.set_server_status, True)

                    if resp.status_code == 200 and data.get("status") == "valid":
                        def _save_success():
                            if not win.winfo_exists():
                                return
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            save_config('last_used_license_key', key_val)
                            self.app_state.license_info.update({**data, 'key': key_val})
                            with open(get_data_path('license.dat'), 'w') as f:
                                json.dump(self.app_state.license_info, f)
                            self.play_sound("success")
                            key_status.configure(text="✅  Activated successfully!",
                                                 text_color=("#059669", "#10B981"))
                            win.after(500, lambda: [activated.set(True), win.destroy()])
                        self.after(0, _save_success)
                    elif resp.status_code == 403 and data.get("status") == "slots_full":
                        def _show_full():
                            if not win.winfo_exists():
                                return
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            self.play_sound("error")
                            show_slots_full_ui(data)
                        self.after(0, _show_full)
                    else:
                        reason = data.get("reason", "Activation failed.")
                        action = data.get("action")
                        if action == "redirect":
                            url = data.get("url")
                            self.after(0, lambda r=reason, u=url: (
                                self.play_sound("error"),
                                messagebox.askyesno("Action Required",
                                                     r + "\n\nOpen website?",
                                                     parent=win)
                                and webbrowser.open(u)
                            ))
                        else:
                            self.after(0, lambda r=reason: [
                                self.play_sound("error"),
                                key_status.configure(text=f"❌  {r.split(chr(10))[0][:60]}",
                                                     text_color=("#DC2626", "#EF4444")),
                                messagebox.showerror("Failed", r, parent=win) if win.winfo_exists() else None
                            ])

                        def _reset_btn():
                            if key_activate_btn.winfo_exists():
                                progress_bar.stop()
                                progress_bar.pack_forget()
                                key_activate_btn.configure(state="normal", text="Activate")

                        self.after(0, _reset_btn)

                except Exception as e:
                    def _error():
                        if not win.winfo_exists():
                            return
                        progress_bar.stop()
                        progress_bar.pack_forget()
                        self.play_sound("error")
                        key_status.configure(text=f"❌  {str(e).split(chr(10))[0][:60]}",
                                             text_color=("#DC2626", "#EF4444"))
                        messagebox.showerror("Error", str(e), parent=win)
                        if key_activate_btn.winfo_exists():
                            key_activate_btn.configure(state="normal", text="Activate")
                    self.after(0, _error)

            threading.Thread(target=_key_activate_thread, daemon=True).start()

        key_activate_btn = ctk.CTkButton(
            key_inner, text="Activate", command=on_key_activate,
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            height=40, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        key_activate_btn.pack(pady=(6, 8), ipady=2, fill='x')

        buy_link_key = ctk.CTkLabel(
            key_inner, text="🛒  Don't have a license? Purchase one",
            text_color=("#2563EB", "#60A5FA"), cursor="hand2",
            font=ctk.CTkFont(size=12))
        buy_link_key.pack(pady=(4, 0))
        buy_link_key.bind("<Button-1>",
                           lambda e: webbrowser.open_new_tab(
                               f"{config.LICENSE_SERVER_URL}/buy"))

        # -------- TAB 2: Email & OTP --------
        tab_email = tab_view.add("📧  Email & OTP")

        email_inner = ctk.CTkFrame(tab_email, fg_color="transparent")
        email_inner.pack(expand=True, fill="both", padx=16, pady=(16, 10))

        ctk.CTkLabel(email_inner, text="Login with your registered email",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(email_inner, text="We'll send a one-time passcode to your email.",
                     font=ctk.CTkFont(size=11), text_color="gray60",
                     anchor="w").pack(fill="x", pady=(0, 12))

        email_entry = ctk.CTkEntry(email_inner, placeholder_text="Enter your email address",
                                    font=ctk.CTkFont(size=13))
        email_entry.pack(fill="x", ipady=4)
        if get_config('last_used_email'):
            email_entry.insert(0, get_config('last_used_email'))

        # OTP row: input + send button
        otp_row = ctk.CTkFrame(email_inner, fg_color="transparent")
        otp_row.pack(fill="x", pady=(10, 0))

        otp_entry = ctk.CTkEntry(otp_row, placeholder_text="Enter OTP",
                                  font=ctk.CTkFont(size=13))
        otp_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)

        # ── OTP resend countdown state ──
        _otp_timer = [None]
        _otp_remaining = [0]

        def _update_otp_btn():
            try:
                if not send_otp_btn.winfo_exists():
                    return
            except Exception:
                return
            if _otp_remaining[0] > 0:
                send_otp_btn.configure(state="disabled", text=f"Resend in {_otp_remaining[0]}s")
                _otp_remaining[0] -= 1
                _otp_timer[0] = win.after(1000, _update_otp_btn)
            else:
                send_otp_btn.configure(state="normal", text="Send OTP")

        def send_otp_login():
            email_val = email_entry.get().strip()
            if "@" not in email_val:
                messagebox.showwarning("Invalid", "Enter a valid email to send OTP.",
                                        parent=win)
                return
            send_otp_btn.configure(state="disabled", text="⏳ Sending...")
            email_status.configure(text="⏳  Sending OTP...",
                                   text_color=("#2563EB", "#60A5FA"))
            try:
                resp = self.app_state.http_session.post(
                    f"{config.LICENSE_SERVER_URL}/api/send-otp",
                    json={"identifier": email_val}, timeout=10)
                if resp.status_code == 200:
                    result = resp.json()
                    channel = result.get("channel", "email")
                    self.play_sound("success")
                    email_status.configure(
                        text=f"✅  OTP sent to your {channel}. Please check.",
                        text_color=("#059669", "#10B981"))
                    _otp_remaining[0] = 30
                    _update_otp_btn()
                else:
                    try:
                        reason = resp.json().get("reason", "Failed")
                    except Exception:
                        reason = f"Server returned status {resp.status_code}"
                    self.play_sound("error")
                    email_status.configure(text=f"❌  {reason}",
                                           text_color=("#DC2626", "#EF4444"))
                    send_otp_btn.configure(state="normal", text="Send OTP")
            except Exception as e:
                self.play_sound("error")
                email_status.configure(text=f"❌  {str(e)}",
                                       text_color=("#DC2626", "#EF4444"))
                send_otp_btn.configure(state="normal", text="Send OTP")

        send_otp_btn = ctk.CTkButton(
            otp_row, text="Send OTP", command=send_otp_login,
            fg_color="gray", width=110, height=34,
            font=ctk.CTkFont(size=12)
        )
        send_otp_btn.pack(side="right")

        # Inline status for email tab
        email_status = ctk.CTkLabel(email_inner, text="",
                                     font=ctk.CTkFont(size=11), anchor="w")
        email_status.pack(fill="x", pady=(8, 4))

        def on_email_activate():
            email_val = email_entry.get().strip()
            otp_val = otp_entry.get().strip()
            if not email_val or "@" not in email_val:
                self.play_sound("error")
                email_status.configure(text="⚠️  Please enter a valid email address.",
                                       text_color=("#DC2626", "#EF4444"))
                return
            if not otp_val:
                self.play_sound("error")
                email_status.configure(text="⚠️  Please enter the OTP from your email.",
                                       text_color=("#DC2626", "#EF4444"))
                return

            email_activate_btn.configure(state="disabled", text="⏳ Activating...")
            email_status.configure(text="⏳  Verifying OTP and activating...",
                                   text_color=("#2563EB", "#60A5FA"))
            progress_bar.pack(fill="x", pady=(0, 8), before=tab_view)
            progress_bar.start()

            def _email_activate_thread():
                try:
                    resp = self.app_state.http_session.post(
                        f"{config.LICENSE_SERVER_URL}/api/login-for-activation",
                        json={
                            "email": email_val,
                            "machine_id": self.app_state.machine_id,
                            "otp": otp_val,
                            "app_version": config.APP_VERSION_WIRE
                        },
                        timeout=15
                    )
                    try:
                        data = resp.json()
                    except Exception:
                        raise Exception(
                            f"Server returned an unexpected response (status {resp.status_code}).")

                    if resp.status_code == 200 and data.get("status") == "success":
                        def _email_success():
                            if not win.winfo_exists():
                                return
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            save_config('last_used_email', email_val)
                            self.app_state.license_info = data
                            with open(get_data_path('license.dat'), 'w') as f:
                                json.dump(self.app_state.license_info, f)
                            self.play_sound("success")
                            email_status.configure(text="✅  Activated successfully!",
                                                   text_color=("#059669", "#10B981"))
                            win.after(500, lambda: [activated.set(True), win.destroy()])
                        self.after(0, _email_success)
                    elif resp.status_code == 403 and data.get("status") == "slots_full":
                        def _email_full():
                            if not win.winfo_exists():
                                return
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            self.play_sound("error")
                            show_slots_full_ui(data)
                        self.after(0, _email_full)
                    else:
                        reason = data.get("reason", "Activation failed.")
                        action = data.get("action")
                        if action == "redirect":
                            url = data.get("url")
                            self.after(0, lambda r=reason, u=url: [
                                self.play_sound("error"),
                                email_status.configure(text=f"❌  {r.split(chr(10))[0][:60]}",
                                                       text_color=("#DC2626", "#EF4444")),
                                messagebox.askyesno("Action Required",
                                                     r + "\n\nOpen website?",
                                                     parent=win) and webbrowser.open(u)
                            ])
                        else:
                            self.after(0, lambda r=reason: (
                                self.play_sound("error") or
                                email_status.configure(text=f"❌  {r.split(chr(10))[0][:60]}",
                                                       text_color=("#DC2626", "#EF4444")) or
                                messagebox.showerror("Failed", r, parent=win)
                                if win.winfo_exists() else None
                            ))

                        def _reset_email():
                            if email_activate_btn.winfo_exists():
                                progress_bar.stop()
                                progress_bar.pack_forget()
                                email_activate_btn.configure(state="normal", text="Login & Activate")
                        self.after(0, _reset_email)

                except Exception as e:
                    def _email_error():
                        if not win.winfo_exists():
                            return
                        progress_bar.stop()
                        progress_bar.pack_forget()
                        self.play_sound("error")
                        email_status.configure(text=f"❌  {str(e).split(chr(10))[0][:60]}",
                                               text_color=("#DC2626", "#EF4444"))
                        messagebox.showerror("Error", str(e), parent=win)
                        if email_activate_btn.winfo_exists():
                            email_activate_btn.configure(state="normal", text="Login & Activate")
                    self.after(0, _email_error)

            threading.Thread(target=_email_activate_thread, daemon=True).start()

        email_activate_btn = ctk.CTkButton(
            email_inner, text="Login & Activate", command=on_email_activate,
            height=40, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        email_activate_btn.pack(pady=(10, 8), ipady=2, fill='x')

        # Trial link inside email tab
        def _start_trial():
            win.withdraw()
            if self.show_trial_registration_window(
                    on_login=lambda: tab_view.set("📧  Email & OTP")):
                activated.set(True)
                win.destroy()
            else:
                win.deiconify()

        trial_link = ctk.CTkLabel(
            email_inner, text="🎯  New user? Start a Free Trial",
            text_color=("#059669", "#10B981"), cursor="hand2",
            font=ctk.CTkFont(size=12, weight="bold"))
        trial_link.pack(pady=(4, 0))
        trial_link.bind("<Button-1>", lambda e: _start_trial())

        # ==============================================================
        # BOTTOM SECTION (outside tabs)
        # ==============================================================
        sep = ctk.CTkFrame(outer, height=1, fg_color=("gray85", "gray35"))
        sep.pack(fill="x", pady=(0, 12))

        ctk.CTkButton(
            outer, text="🎯  Start 30-Day Free Trial",
            command=_start_trial,
            fg_color=("#059669", "#10B981"),
            hover_color=("#047857", "#059669"),
            height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=(0, 4), ipady=2, fill='x')

        self.wait_window(win)
        return activated.get()

    # ------------------------------------------------------------------
    # TRIAL REGISTRATION
    # ------------------------------------------------------------------

    def show_trial_registration_window(self, on_login: Optional[Any] = None) -> bool:
        """30-day free trial signup (compact).

        On open, the server is asked whether this device (machine id) is
        already registered. If it is, only two options are shown:
        Login (existing license) or Renew Subscription.
        """
        win = ctk.CTkToplevel(self)
        win.title(f"{config.APP_SHORT_NAME} - Free Trial")
        win.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(500, sw-40), min(580, sh-40)
        win.geometry(f'{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}')
        win.resizable(False, False); win.transient(self); win.grab_set()

        outer = ctk.CTkFrame(win, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=18, pady=12)

        # ── Branding header (compact) ──
        brand = ctk.CTkFrame(outer, fg_color="transparent")
        brand.pack(fill="x", pady=(0, 8))
        try:
            logo_img = ctk.CTkImage(Image.open(resource_path("assets/logo.png")), size=(34, 34))
            ctk.CTkLabel(brand, image=logo_img, text="").pack(side="left", padx=(0, 8))
        except Exception:
            ctk.CTkLabel(brand, text="🎯", font=ctk.CTkFont(size=22)).pack(side="left", padx=(0, 8))
        text_col = ctk.CTkFrame(brand, fg_color="transparent")
        text_col.pack(side="left")
        ctk.CTkLabel(text_col, text="Start Your 30-Day Free Trial",
                     font=ctk.CTkFont(size=16, weight="bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(text_col, text="No payment needed. Full access to most features.",
                     font=ctk.CTkFont(size=10), text_color="gray60", anchor="w").pack(fill="x")

        # ── Progress bar (shown while submitting) ──
        progress_bar = ctk.CTkProgressBar(outer, height=4, corner_radius=2, mode="indeterminate")
        progress_bar.pack(fill="x", pady=(0, 6))
        progress_bar.pack_forget()

        # ── Shared inline status line ──
        status_label = ctk.CTkLabel(outer, text="", font=ctk.CTkFont(size=11),
                                    anchor="w", justify="left", wraplength=w-50)
        status_label.pack(fill="x", pady=(6, 2))

        # ── Content area (swapped between states) ──
        content = ctk.CTkFrame(outer, fg_color="transparent")
        content.pack(expand=True, fill="both")

        successful = tkinter.BooleanVar(value=False)

        # ══════════════════════════════════════════════════════════════
        # STATE 1 — Device already registered → only Login / Renew
        # ══════════════════════════════════════════════════════════════
        def show_registered_panel():
            for wgt in content.winfo_children():
                wgt.destroy()

            ctk.CTkLabel(content, text="⚠️  Device Already Registered",
                         font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=config.COLORS["red_expired"]).pack(pady=(10, 2))
            ctk.CTkLabel(content, text=("This device is already associated with a license.\n"
                                        "Only one trial is allowed per device."),
                         font=ctk.CTkFont(size=11), text_color="gray60",
                         justify="center").pack(pady=(0, 12))

            def _go_login():
                if on_login:
                    try:
                        on_login()
                    except Exception:
                        logger.debug("on_login callback failed", exc_info=True)
                win.destroy()

            def _go_renew():
                webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/buy")

            login_btn = ctk.CTkButton(content, text="🔑  Login with Email & OTP",
                                      command=_go_login,
                                      fg_color=("#2563EB", "#3B82F6"),
                                      hover_color=("#1D4ED8", "#2563EB"),
                                      height=38, corner_radius=8,
                                      font=ctk.CTkFont(size=13, weight="bold"))
            login_btn.pack(fill="x", padx=10, pady=(0, 8))

            renew_btn = ctk.CTkButton(content, text="🛒  Renew Subscription",
                                      command=_go_renew,
                                      fg_color=("#059669", "#10B981"),
                                      hover_color=("#047857", "#059669"),
                                      height=38, corner_radius=8,
                                      font=ctk.CTkFont(size=13, weight="bold"))
            renew_btn.pack(fill="x", padx=10, pady=(0, 6))

            back_lbl = ctk.CTkLabel(content, text="←  Back", cursor="hand2",
                                    text_color=("#2563EB", "#60A5FA"),
                                    font=ctk.CTkFont(size=12))
            back_lbl.pack(pady=(10, 0))
            back_lbl.bind("<Button-1>", lambda e: win.destroy())

        # ══════════════════════════════════════════════════════════════
        # STATE 2 — Compact trial form
        # ══════════════════════════════════════════════════════════════
        entries: Dict[str, Any] = {}
        _dupe_timers: Dict[str, Any] = {}
        _otp_timer = [None]
        _otp_remaining = [0]

        def build_form():
            for wgt in content.winfo_children():
                wgt.destroy()

            # ── Card container — groups the fields into one polished card ──
            card = ctk.CTkFrame(content, fg_color=config.COLORS["gray_card_bg"], corner_radius=12)
            card.pack(expand=True, fill="both", pady=(0, 8))
            card.grid_columnconfigure(0, weight=1, uniform="f")
            card.grid_columnconfigure(1, weight=1, uniform="f")

            def _pad(col, span):
                left = 14 if col == 0 else 3
                right = 14 if (span == 2 or col == 1) else 3
                return (left, right)

            def add_field(row, col, label, key, placeholder="", span=1, with_check=False):
                cell = ctk.CTkFrame(card, fg_color="transparent")
                cell.grid(row=row, column=col, columnspan=span, sticky="ew",
                          padx=_pad(col, span), pady=(6, 3))
                ctk.CTkLabel(cell, text=label, anchor="w",
                             font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x")
                entry = ctk.CTkEntry(cell, placeholder_text=placeholder,
                                     font=ctk.CTkFont(size=12), height=32)
                entry.pack(fill="x", pady=(2, 0))
                check = None
                if with_check:
                    check = ctk.CTkLabel(cell, text="", font=ctk.CTkFont(size=9), anchor="w")
                    check.pack(fill="x")
                entries[key] = entry
                return entry, check

            def add_menu(row, col, label, key, values, initial, state="normal"):
                cell = ctk.CTkFrame(card, fg_color="transparent")
                cell.grid(row=row, column=col, sticky="ew",
                          padx=_pad(col, 1), pady=(6, 3))
                ctk.CTkLabel(cell, text=label, anchor="w",
                             font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x")
                var = tkinter.StringVar(value=initial)
                menu = ctk.CTkOptionMenu(cell, values=values, variable=var,
                                         height=32, font=ctk.CTkFont(size=12), state=state)
                menu.pack(fill="x", pady=(2, 0))
                entries[key] = var
                return var, menu

            # Row 0: Full Name | Mobile Number — both keep a check-label slot
            # (with_check=True) so the two cells are the SAME height and the
            # entries align perfectly (grid centers unequal-height cells).
            _, _ = add_field(0, 0, "Full Name", "name", placeholder="e.g. Ramesh Kumar",
                             with_check=True)
            mobile_entry, mobile_check = add_field(0, 1, "Mobile Number", "mobile",
                                                   placeholder="10-digit mobile",
                                                   with_check=True)

            # Row 1: Email (full width, with live duplicate check)
            email_entry, email_check = add_field(1, 0, "Email", "email",
                                                 placeholder="you@example.com", span=2, with_check=True)
            if get_config('last_used_email'):
                email_entry.insert(0, get_config('last_used_email'))

            # Row 2: OTP (full width) + inline Send button
            otp_cell = ctk.CTkFrame(card, fg_color="transparent")
            otp_cell.grid(row=2, column=0, columnspan=2, sticky="ew",
                          padx=_pad(0, 2), pady=(6, 3))
            ctk.CTkLabel(otp_cell, text="One-Time Passcode", anchor="w",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x")
            otp_inner = ctk.CTkFrame(otp_cell, fg_color="transparent")
            otp_inner.pack(fill="x", pady=(2, 0))
            otp_entry = ctk.CTkEntry(otp_inner, placeholder_text="Enter OTP (email / WhatsApp)",
                                     font=ctk.CTkFont(size=12), height=32)
            otp_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            entries['otp'] = otp_entry

            # Row 3: State | District (dependent dropdowns, aligned together)
            state_var, state_menu = add_menu(3, 0, "State", "state",
                                             sorted(list(STATE_DISTRICT_MAP.keys())), "Select a State")
            dist_var, dist_menu = add_menu(3, 1, "District", "district",
                                           ["Select State First"], "Select State First", state="disabled")

            def on_state(s):
                dists = STATE_DISTRICT_MAP.get(s, [])
                if dists:
                    dist_menu.configure(values=dists, state="normal")
                    if dist_var.get() not in dists:
                        dist_var.set("Select District")
                else:
                    dist_menu.configure(state="disabled")
            state_var.trace_add("write", lambda *args: on_state(state_var.get()))

            # Row 4: Block | Referral Code (optional, both entries, aligned)
            _, _ = add_field(4, 0, "Block", "block", placeholder="Block name")
            _, _ = add_field(4, 1, "Referral Code (Optional)", "referral_code",
                             placeholder="Ask your friend for a code")

            # ── Real-time duplicate checks (debounced) ──
            def _check_duplicate(field, value, lbl):
                value = value.strip()
                if not value:
                    lbl.configure(text="", text_color="gray60")
                    return
                if field == 'email' and '@' not in value:
                    return
                if field == 'mobile' and len(value) < 10:
                    return
                lbl.configure(text="⏳ Checking availability...", text_color=("gray40", "gray60"))

                def _thread():
                    try:
                        resp = self.app_state.http_session.post(
                            f"{config.LICENSE_SERVER_URL}/api/check-duplicate",
                            json={"field": field, "value": value}, timeout=8)
                        res = resp.json()
                        ok = resp.status_code == 200 and res.get("status") == "success"
                        reason = res.get("reason", "")

                        def _update():
                            if not win.winfo_exists():
                                return
                            lbl.configure(text=reason,
                                          text_color=("#059669", "#10B981") if ok else ("#DC2626", "#EF4444"))
                        self.after(0, _update)
                    except Exception:
                        # Silent on network errors; the final check happens at submit time.
                        pass
                threading.Thread(target=_thread, daemon=True).start()

            def _debounced_check(field, entry, lbl):
                def _on_change(*_):
                    t = _dupe_timers.get(field)
                    if t:
                        try:
                            win.after_cancel(t)
                        except Exception:
                            pass
                    _dupe_timers[field] = win.after(700, lambda: _check_duplicate(field, entry.get(), lbl))
                return _on_change

            email_entry.bind("<KeyRelease>", _debounced_check('email', email_entry, email_check))
            mobile_entry.bind("<KeyRelease>", _debounced_check('mobile', mobile_entry, mobile_check))

            # ── OTP send with resend countdown ──
            def _update_otp_btn():
                try:
                    if not send_otp_btn.winfo_exists():
                        return
                except Exception:
                    return
                if _otp_remaining[0] > 0:
                    send_otp_btn.configure(state="disabled", text=f"Resend in {_otp_remaining[0]}s")
                    _otp_remaining[0] -= 1
                    _otp_timer[0] = win.after(1000, _update_otp_btn)
                else:
                    send_otp_btn.configure(state="normal", text="Send OTP")

            def send_otp_action():
                email_val = email_entry.get().strip()
                if '@' not in email_val:
                    self.play_sound("error")
                    status_label.configure(text="⚠️  Enter a valid email first.",
                                           text_color=("#DC2626", "#EF4444"))
                    return
                send_otp_btn.configure(state="disabled", text="⏳ Sending...")
                payload: Dict[str, Any] = {"identifier": email_val}
                mobile_val = mobile_entry.get().strip()
                if mobile_val and len(mobile_val) >= 10:
                    payload["mobile"] = mobile_val  # OTP also goes to WhatsApp

                def _thread():
                    try:
                        resp = self.app_state.http_session.post(
                            f"{config.LICENSE_SERVER_URL}/api/send-otp", json=payload, timeout=10)
                        res = resp.json()
                        ok = resp.status_code == 200 and res.get("status") == "success"
                        if ok:
                            channel = res.get("channel", "email")
                            msg = "✅  OTP sent to your email" + (" & WhatsApp" if "whatsapp" in channel else "") + "."

                            # Set countdown BEFORE scheduling the callback to avoid a
                            # race where the main loop runs _success before the value lands.
                            _otp_remaining[0] = 30

                            def _success():
                                if not win.winfo_exists():
                                    return
                                status_label.configure(text=msg, text_color=("#059669", "#10B981"))
                                self.play_sound("success")
                                _update_otp_btn()
                            self.after(0, _success)
                        else:
                            reason = res.get("reason", "Failed")

                            def _fail(r=reason):
                                if not win.winfo_exists():
                                    return
                                self.play_sound("error")
                                status_label.configure(text=f"❌  {r}", text_color=("#DC2626", "#EF4444"))
                                send_otp_btn.configure(state="normal", text="Send OTP")
                            self.after(0, _fail)
                    except Exception as e:
                        err = str(e)

                        def _error(err=err):
                            if not win.winfo_exists():
                                return
                            self.play_sound("error")
                            status_label.configure(text=f"❌  {err}", text_color=("#DC2626", "#EF4444"))
                            send_otp_btn.configure(state="normal", text="Send OTP")
                        self.after(0, _error)
                threading.Thread(target=_thread, daemon=True).start()

            send_otp_btn = ctk.CTkButton(otp_inner, text="Send OTP", width=110, height=30,
                                         command=send_otp_action, fg_color="gray",
                                         font=ctk.CTkFont(size=12))
            send_otp_btn.pack(side="right")

            # ── Submit ──
            def submit():
                data: Dict[str, Any] = {
                    "name": entries['name'].get().strip().title(),
                    "email": entries['email'].get().strip().lower(),
                    "mobile": entries['mobile'].get().strip(),
                    "otp": entries['otp'].get().strip(),
                    "block": entries['block'].get().strip(),
                    "state": entries['state'].get(),
                    "district": entries['district'].get(),
                    "referral_code": entries['referral_code'].get().strip(),
                }
                missing = []
                if not data['name']:
                    missing.append("Full Name")
                if '@' not in data['email']:
                    missing.append("Email")
                if len(data['mobile']) < 10:
                    missing.append("Mobile")
                if not data['otp']:
                    missing.append("OTP")
                if not data['state'] or data['state'] == "Select a State":
                    missing.append("State")
                if not data['district'] or data['district'] == "Select District":
                    missing.append("District")
                if missing:
                    self.play_sound("error")
                    status_label.configure(text=f"⚠️  Please fill: {', '.join(missing)}",
                                           text_color=("#DC2626", "#EF4444"))
                    return

                data["machine_id"] = self.app_state.machine_id
                data["app_version"] = config.APP_VERSION_WIRE
                submit_btn.configure(state="disabled", text="⏳ Creating your trial...")
                progress_bar.pack(fill="x", pady=(0, 6), before=status_label)
                progress_bar.start()
                status_label.configure(text="⏳  Activating your free trial...",
                                       text_color=("#2563EB", "#60A5FA"))

                def _thread():
                    try:
                        resp = self.app_state.http_session.post(
                            f"{config.LICENSE_SERVER_URL}/api/request-trial", json=data, timeout=20)
                        try:
                            res = resp.json()
                        except Exception:
                            raise Exception(
                                f"Server returned an unexpected response (status {resp.status_code}). Please try again.")

                        if resp.status_code == 200 and res.get("status") == "success":
                            def _success():
                                if not win.winfo_exists():
                                    return
                                progress_bar.stop()
                                progress_bar.pack_forget()
                                save_config('last_used_email', data['email'])
                                license_info = {
                                    'key': res.get("key"),
                                    'expires_at': res.get("expires_at"),
                                    'key_type': 'trial',
                                    'user_name': res.get("user_name") or data['name'],
                                    'user_email': res.get("user_email") or data['email'],
                                    'user_mobile': res.get("user_mobile") or data['mobile'],
                                    'max_devices': res.get("max_devices", 1),
                                }
                                self.app_state.license_info.update(license_info)
                                with open(get_data_path('license.dat'), 'w') as f:
                                    json.dump(self.app_state.license_info, f)
                                self.play_sound("success")
                                status_label.configure(text="✅  Trial activated successfully!",
                                                       text_color=("#059669", "#10B981"))
                                successful.set(True)
                                win.after(500, win.destroy)
                            self.after(0, _success)
                        else:
                            reason = res.get("reason", "Error")

                            def _fail(r=reason):
                                if not win.winfo_exists():
                                    return
                                self.play_sound("error")
                                progress_bar.stop()
                                progress_bar.pack_forget()
                                status_label.configure(text=f"❌  {r}", text_color=("#DC2626", "#EF4444"))
                                submit_btn.configure(state="normal", text="🎯  Start Free Trial")
                            self.after(0, _fail)
                    except Exception as e:
                        err = str(e)

                        def _error(err=err):
                            if not win.winfo_exists():
                                return
                            self.play_sound("error")
                            progress_bar.stop()
                            progress_bar.pack_forget()
                            status_label.configure(text=f"❌  {err}", text_color=("#DC2626", "#EF4444"))
                            submit_btn.configure(state="normal", text="🎯  Start Free Trial")
                        self.after(0, _error)
                threading.Thread(target=_thread, daemon=True).start()

            submit_btn = ctk.CTkButton(content, text="🎯  Start Free Trial", command=submit,
                                       fg_color=("#059669", "#10B981"),
                                       hover_color=("#047857", "#059669"),
                                       height=38, corner_radius=8,
                                       font=ctk.CTkFont(size=13, weight="bold"))
            submit_btn.pack(fill="x", pady=(2, 3))

            ctk.CTkLabel(content,
                         text="One trial per user/device. Upgrade anytime to unlock all features.",
                         font=ctk.CTkFont(size=9), text_color="gray60").pack()

        # ══════════════════════════════════════════════════════════════
        # OPEN: machine pre-check → panel or form
        # ══════════════════════════════════════════════════════════════
        checking_lbl = ctk.CTkLabel(content, text="⏳  Checking device status...",
                                    font=ctk.CTkFont(size=12), text_color="gray60")
        checking_lbl.pack(pady=(40, 0))

        def _machine_thread():
            registered = False
            try:
                resp = self.app_state.http_session.post(
                    f"{config.LICENSE_SERVER_URL}/api/check-duplicate",
                    json={"field": "machine", "value": self.app_state.machine_id}, timeout=8)
                registered = resp.status_code == 409
            except Exception:
                # Server unreachable → fall through to the form; the server
                # still enforces the one-trial-per-device rule at submit time.
                registered = False

            def _swap():
                if not win.winfo_exists():
                    return
                if registered:
                    show_registered_panel()
                else:
                    build_form()
            self.after(0, _swap)

        threading.Thread(target=_machine_thread, daemon=True).start()

        self.wait_window(win)
        return successful.get()

    def show_purchase_window(self, context: str = 'upgrade') -> None:
        if not self.app_state.license_info.get('key'): self.play_sound("error"); messagebox.showerror("Error", "License key missing"); return
        webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/buy?existing_key={self.app_state.license_info['key']}")

    def check_expiry_and_notify(self) -> bool:
        exp = self.app_state.license_info.get('expires_at')
        if not exp: return False
        try:
            days = (datetime.fromisoformat(exp.split('T')[0]).date() - datetime.now().date()).days
            if 0 <= days < 7:
                self.app_state.expiry_alert_message = f"License expires in {days} days."
                self.app_state.open_on_about_tab = True
                return True
        except Exception:
            logger.debug("check_expiry_and_notify: date parsing failed", exc_info=True)
            return False

    def _lock_app_to_about_tab(self) -> None:
        self.show_frame("About")
        for name, btn in self.app_state.nav_buttons.items():
            if name != "About": btn.configure(state="disabled")
        if hasattr(self, 'launch_chrome_btn'):
            self.launch_chrome_btn.configure(state="disabled")
            self.launch_edge_btn.configure(state="disabled")
            self.launch_firefox_btn.configure(state="disabled")
            self.theme_combo.configure(state="disabled")
            if hasattr(self, 'sound_switch'): self.sound_switch.configure(state="disabled")

    def _unlock_app(self) -> None:
        for btn in self.app_state.nav_buttons.values(): btn.configure(state="normal")
        self.launch_chrome_btn.configure(state="normal"); self.launch_edge_btn.configure(state="normal"); self.launch_firefox_btn.configure(state="normal")
        self.theme_combo.configure(state="normal")
        if hasattr(self, 'sound_switch'): self.sound_switch.configure(state="normal")

    def _validate_in_background(self) -> None:
        try:
            self.app_state.is_validating_license = True
            if self.validate_on_server(self.app_state.license_info.get('key'), is_startup_check=True):
                self.after(0, self._update_about_tab_info)
                fm_tab = self.app_state.tab_instances.get("File Manager")
                if fm_tab:
                    self.after(0, lambda: fm_tab.update_storage_info(self.app_state.license_info.get('total_usage'), self.app_state.license_info.get('max_storage')))
                    self.after(0, lambda: fm_tab.refresh_files(fm_tab.current_folder_id, add_to_history=False))
        finally: self.app_state.is_validating_license = False

    # ------------------------------------------------------------------
    # SERVER SYNC & FEATURE FLAGS
    # ------------------------------------------------------------------

    def _ping_server_in_background(self):
        """Optimized unified background sync using requests.Session()"""
        def sync_worker():
            ping_counter = 0
            _cookie_req_count = 0  # M4: tracks HTTP requests for periodic cookie clearing
            _shutdown = False
            while not _shutdown:
                # 1. Ping Server — always schedule UI update via after(0, ...);
                #    no winfo_exists() check from background thread (not thread-safe).
                try:
                    self.app_state.http_session.get(config.LICENSE_SERVER_URL, timeout=5)
                    _cookie_req_count += 1
                    try:
                        self.after(0, self.set_server_status, True)
                    except Exception:
                        _shutdown = True
                        break
                except requests.exceptions.RequestException:
                    try:
                        self.after(0, self.set_server_status, False)
                    except Exception:
                        _shutdown = True
                        break

                # 2. Fetch App Config (Every 120s -> 6 loops of 20s)
                if ping_counter % 6 == 0:
                    try:
                        url = f"{config.LICENSE_SERVER_URL}/api/app-config"
                        resp = self.app_state.http_session.get(url, timeout=10)
                        _cookie_req_count += 1
                        if resp.status_code == 200:
                            data = resp.json()
                            msg = data.get("global_announcement", "")
                            final_msg = msg if msg else "Welcome to NREGA Bot! Ready to automate."
                            try:
                                self.after(0, lambda m=final_msg: (
                                    self.announcement_label.update_text(m)
                                ))
                            except Exception:
                                _shutdown = True
                                break

                            self.app_state.global_disabled_features = data.get("disabled_features", [])
                            if (self.app_state.license_info.get('key_type') or '').lower() == 'trial':
                                self.app_state.trial_restricted_features = data.get("trial_restricted_features", [])
                            else:
                                self.app_state.trial_restricted_features = []

                            try:
                                self.after(0, self._apply_feature_flags)
                            except Exception:
                                _shutdown = True
                                break
                    except Exception as e:
                        logger.error("Config Fetch Error: %s", e)
                    ping_counter = 0

                # M4: Periodically clear accumulated session cookies (~60 reqs ≈ 15-20 min)
                # Prevents stale cookies from growing unbounded over long app sessions.
                if _cookie_req_count >= 60:
                    _cookie_req_count = 0
                    cookie_count = len(self.app_state.http_session.cookies)
                    self.app_state.http_session.cookies.clear()
                    if cookie_count > 0:
                        logger.debug("Cleared %s session cookies (periodic cleanup)", cookie_count)

                ping_counter += 1
                time.sleep(20)

        threading.Thread(target=sync_worker, daemon=True).start()

    def _fetch_app_config(self):
        pass  # Deprecated: merged into _ping_server_in_background

    def _apply_feature_flags(self) -> None:
        current_ver = parse_version(config.APP_VERSION)
        for name, btn in self.app_state.nav_buttons.items():
            current_text = btn.cget("text")
            clean_text = current_text.replace(" ⚠️", "").replace(" 🔒", "").replace(" (Update)", "").replace(" (Maintenance)", "")
            new_state = "normal"
            new_fg = "transparent"
            new_text = clean_text
            new_cmd = lambda n=name: self.show_frame(n)
            disabled_data = None
            if isinstance(self.app_state.global_disabled_features, list):
                if name in self.app_state.global_disabled_features: disabled_data = {"fix_version": None}
            elif isinstance(self.app_state.global_disabled_features, dict):
                disabled_data = self.app_state.global_disabled_features.get(name)
            if disabled_data:
                fix_version_str = disabled_data.get('fix_version')
                is_update_available = False
                try:
                    if fix_version_str and parse_version(fix_version_str) > current_ver:
                        is_update_available = True
                except Exception:
                    logger.debug("Version comparison failed for fix_version_str=%s", fix_version_str)
                if is_update_available:
                    new_fg = ("orange", "#D97706")
                    new_text = f"{clean_text} ⚠️ (Update)"
                    new_cmd = lambda n=name, v=fix_version_str: self.show_feature_update_alert(n, v)
                else:
                    new_fg = ("red", "#991B1B")
                    new_text = f"{clean_text} ⚠️ (Maintenance)"
                    new_cmd = lambda n=name: self.show_feature_maintenance_alert(n)
            elif name in self.app_state.trial_restricted_features:
                new_fg = ("gray95", "gray25")
                new_text = f"{clean_text} 🔒"
                new_cmd = lambda n=name: self.show_trial_lock_alert(n)
            if btn.cget("text") != new_text or btn.cget("fg_color") != new_fg:
                btn.configure(state=new_state, fg_color=new_fg, text=new_text, command=new_cmd)

    def _start_validation_thread(self):
        if not self.app_state.is_validating_license:
            threading.Thread(target=self._validate_in_background, daemon=True).start()

    # ------------------------------------------------------------------
    # HEADER WELCOME & ABOUT TAB
    # ------------------------------------------------------------------

    def _update_header_welcome_message(self):
        if not self.header_welcome_prefix_label: return
        user_name, key_type = self.app_state.license_info.get('user_name'), self.app_state.license_info.get('key_type')
        if user_name:
            self.header_welcome_prefix_label.configure(text=f"v{config.APP_VERSION} | Welcome, ")
            self.header_welcome_name_label.configure(text=user_name)
            self.header_welcome_suffix_label.configure(text=" !")
            if key_type != 'trial':
                self.header_welcome_name_label.configure(text_color=("gold4", "#FFD700"), font=ctk.CTkFont(size=13, weight="bold"))
            else:
                self.header_welcome_name_label.configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"], font=ctk.CTkFont(size=13, weight="normal"))
        else:
            self.header_welcome_prefix_label.configure(text=f"v{config.APP_VERSION} | Log in, then select a task.")
            self.header_welcome_name_label.configure(text=""); self.header_welcome_suffix_label.configure(text="")

    def _update_about_tab_info(self) -> None:
        self._update_header_welcome_message()
        about_tab = self.app_state.tab_instances.get("About")
        if about_tab:
            about_tab.update_subscription_details(self.app_state.license_info)
            info = self.app_state.update_info
            if config.BETA_BUILD:
                # Beta builds: show beta state, disable update button
                about_tab.latest_version_label.configure(text="Latest Version: Updates disabled (Beta build)")
                try:
                    about_tab.update_button.configure(state="disabled", text="Beta Build — No Updates")
                except Exception:
                    pass
            elif info.get('status') == 'available':
                about_tab.latest_version_label.configure(text=f"Latest Version: {info['version']}")
            elif info.get('status') == 'updated':
                about_tab.latest_version_label.configure(text="Latest Version: Up to date")
                about_tab.update_button.configure(state="normal", text="Check for Updates")
            elif info.get('status') == 'error':
                about_tab.latest_version_label.configure(text="Latest Version: Check failed")
                about_tab.update_button.configure(state="normal", text="Retry Check")

    # ------------------------------------------------------------------
    # LICENSED FEATURE ALERTS
    # ------------------------------------------------------------------

    def show_trial_lock_alert(self, feature_name):
        self.play_sound("error")
        if messagebox.askyesno("Premium Feature", f"'{feature_name}' is a premium feature available in paid plans.\n\nUpgrade to a full license to unlock unlimited access.\n\nWould you like to upgrade now?"):
            self.show_purchase_window()

    def show_feature_update_alert(self, feature_name, fix_version):
        self.play_sound("error")
        if messagebox.askyesno("Update Required", f"'{feature_name}' requires version {fix_version} or higher.\n\nPlease update to the latest version.\n\nWould you like to check for updates?"):
            self.show_frame("About")
            self.app_state.tab_instances.get("About").tab_view.set("Updates")
            self.check_for_updates_background()

    def show_feature_maintenance_alert(self, feature_name):
        self.play_sound("error")
        messagebox.showwarning("Under Maintenance", f"'{feature_name}' is currently under maintenance.\n\nPlease try again later.")

    # ------------------------------------------------------------------
    # CUSTOM MESSAGEBOX OVERRIDES
    # ------------------------------------------------------------------

    def _custom_showinfo(self, title, message, **options):
        active_tab = getattr(self.app_state, 'current_active_tab', 'System')
        extra_info = self._get_active_tab_context()

        log_msg = f"[{active_tab}] {message}"
        if extra_info:
            log_msg += f" ({extra_info})"

        self.history_manager.log_activity("SUCCESS", log_msg)

        if len(message) < 60 or "success" in message.lower() or "complete" in message.lower() or "finished" in message.lower():
            self.show_toast(message, kind="success")
            return "ok"
        else:
            self.play_sound("success")
            return self.app_state._original_showinfo(title, message, **options)

    def _custom_showwarning(self, title, message, **options):
        active_tab = getattr(self.app_state, 'current_active_tab', 'System')
        extra_info = self._get_active_tab_context()

        log_msg = f"[{active_tab}] {message}"
        if extra_info:
            log_msg += f" ({extra_info})"

        self.history_manager.log_activity("WARNING", log_msg)

        if len(message) < 50:
            self.show_toast(message, kind="warning")
            return "ok"

        self.play_sound("error")
        return self.app_state._original_showwarning(title, message, **options)

    def _custom_showerror(self, title, message, **options):
        active_tab = getattr(self.app_state, 'current_active_tab', 'System')
        extra_info = self._get_active_tab_context()

        log_msg = f"[{active_tab}] Error: {message}"
        if extra_info:
            log_msg += f" ({extra_info})"

        self.history_manager.log_activity("ERROR", log_msg)

        self.play_sound("error")
        return self.app_state._original_showerror(title, message, **options)

    def _get_active_tab_context(self):
        try:
            if not self.app_state.current_active_tab:
                return ""

            tab = self.app_state.tab_instances.get(self.app_state.current_active_tab)
            if not tab:
                return ""

            found_values = []
            target_keywords = ['panchayat', 'gp', 'block', 'mandal', 'village', 'selected', 'agency']

            for var_name, var_obj in vars(tab).items():
                name_lower = var_name.lower()

                if any(k in name_lower for k in target_keywords):
                    val = ""
                    if hasattr(var_obj, 'get'):
                        try:
                            val = var_obj.get()
                        except Exception:
                            logger.debug("Failed to get variable value via .get()", exc_info=True)
                    elif hasattr(var_obj, 'winfo_exists') and hasattr(var_obj, 'get'):
                        try:
                            val = var_obj.get()
                        except Exception:
                            logger.debug("Failed to get variable value via .get() (with winfo_exists check)", exc_info=True)

                    if val and isinstance(val, str) and len(val) > 2:
                        if "select" not in val.lower() and "choose" not in val.lower():
                            found_values.append(val)

            if found_values:
                return " | ".join(sorted(list(set(found_values))))

            return ""
        except Exception as e:
            logger.warning("Context Error: %s", e)
            return ""
