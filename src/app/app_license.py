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
    get_config, save_config, get_logger, parse_version, format_bytes
)
from src.i18n import tr
from src.location_data import STATE_DISTRICT_MAP

logger = get_logger()


def _render_google_g_png(path: str, size: int = 128) -> None:
    """Render a small four-color Google 'G' logo PNG with PIL."""
    from PIL import Image as _PILImage, ImageDraw as _PILDraw
    img = _PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
    d = _PILDraw.Draw(img)
    w = max(5, size // 7)
    pad = size * 0.06
    bbox = [pad, pad, size - pad, size - pad]
    cx = cy = size / 2.0
    blue, red, yellow, green = "#4285F4", "#EA4335", "#FBBC05", "#34A853"
    # Ring segments (PIL angles: 0° = 3 o'clock, clockwise)
    d.arc(bbox, start=300, end=405, fill=blue, width=w)    # top
    d.arc(bbox, start=45, end=135, fill=red, width=w)      # right
    d.arc(bbox, start=135, end=225, fill=yellow, width=w)  # bottom
    d.arc(bbox, start=225, end=300, fill=green, width=w)   # left
    # Blue crossbar through the middle-left
    d.line([cx - size * 0.17, cy, cx + size * 0.10, cy], fill=blue, width=w)
    # Red right connector (joins top and bottom arcs)
    d.line([bbox[2] - w / 2.0, bbox[1] + w, bbox[2] - w / 2.0, bbox[3] - w], fill=red, width=w)
    # Green tail curl at bottom-left
    tbox = [bbox[0] + w * 0.7, bbox[3] - w * 2.2,
            bbox[0] + w * 0.7 + size * 0.30, bbox[3] - w * 2.2 + size * 0.30]
    d.arc(tbox, start=180, end=270, fill=green, width=w)
    img.save(path)


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
        self.set_status(tr("app.status_ready"))
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
    # GOOGLE / PASSKEY QUICK LOGIN
    # ------------------------------------------------------------------

    def _get_google_g_icon(self, size: int = 22):
        """Return a CTkImage of the Google 'G' logo (rendered once via PIL)."""
        try:
            path = get_data_path('google_g.png')
            if not os.path.exists(path):
                _render_google_g_png(path)
            return ctk.CTkImage(Image.open(path), size=(size, size))
        except Exception:
            logger.debug("Could not render Google G icon", exc_info=True)
            return None

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

        ctk.CTkLabel(email_inner, text="Login with your registered email / mobile",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(email_inner, text="OTP bheja jayega dono jagah — email aur WhatsApp par.",
                     font=ctk.CTkFont(size=11), text_color="gray60",
                     anchor="w").pack(fill="x", pady=(0, 12))

        email_entry = ctk.CTkEntry(email_inner, placeholder_text="Enter your registered email or mobile number",
                                    font=ctk.CTkFont(size=13))
        email_entry.pack(fill="x", ipady=4)
        if get_config('last_used_email'):
            email_entry.insert(0, get_config('last_used_email'))

        # OTP row: input + send button
        otp_row = ctk.CTkFrame(email_inner, fg_color="transparent")
        otp_row.pack(fill="x", pady=(10, 0))

        otp_entry = ctk.CTkEntry(otp_row, placeholder_text="Enter OTP (email / WhatsApp)",
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

        def _login_id_type(val: str) -> Optional[str]:
            """Classify a login identifier as 'email', 'mobile' or None."""
            v = val.strip()
            if "@" in v:
                return "email"
            m = v[3:] if v.startswith("+91") else v
            if len(m) == 10 and m.isdigit() and m[0] in "6789":
                return "mobile"
            return None

        def send_otp_login():
            id_val = email_entry.get().strip()
            id_type = _login_id_type(id_val)
            if not id_type:
                messagebox.showwarning(
                    "Invalid", "Enter a valid email or 10-digit mobile number to send OTP.",
                    parent=win)
                return
            send_otp_btn.configure(state="disabled", text="⏳ Sending...")
            email_status.configure(text="⏳  Sending OTP...",
                                   text_color=("#2563EB", "#60A5FA"))
            payload = {"identifier": id_val}
            if id_type == "mobile":
                payload["mobile"] = id_val  # OTP WhatsApp par bhi jayega
            try:
                resp = self.app_state.http_session.post(
                    f"{config.LICENSE_SERVER_URL}/api/send-otp",
                    json=payload, timeout=10)
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
            id_val = email_entry.get().strip()
            id_type = _login_id_type(id_val)
            otp_val = otp_entry.get().strip()
            if not id_type:
                self.play_sound("error")
                email_status.configure(text="⚠️  Please enter a valid email or mobile number.",
                                       text_color=("#DC2626", "#EF4444"))
                return
            if not otp_val:
                self.play_sound("error")
                email_status.configure(text="⚠️  Please enter the OTP sent to your email / WhatsApp.",
                                       text_color=("#DC2626", "#EF4444"))
                return

            email_activate_btn.configure(state="disabled", text="⏳ Activating...")
            email_status.configure(text="⏳  Verifying OTP and activating...",
                                   text_color=("#2563EB", "#60A5FA"))
            progress_bar.pack(fill="x", pady=(0, 8), before=tab_view)
            progress_bar.start()

            def _email_activate_thread():
                try:
                    payload = {
                        "identifier": id_val,
                        "machine_id": self.app_state.machine_id,
                        "otp": otp_val,
                        "app_version": config.APP_VERSION_WIRE
                    }
                    if id_type == "email":
                        payload["email"] = id_val
                    else:
                        payload["mobile"] = id_val
                    resp = self.app_state.http_session.post(
                        f"{config.LICENSE_SERVER_URL}/api/login-for-activation",
                        json=payload,
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
                            save_config('last_used_email', id_val)
                            self._storage_alert_shown = False
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
        # TAB 3: Quick Login (Google / Passkey)
        # ==============================================================
        tab_quick = tab_view.add("⚡  Quick Login")

        quick_inner = ctk.CTkFrame(tab_quick, fg_color="transparent")
        quick_inner.pack(expand=True, fill="both", padx=16, pady=(16, 10))

        _oauth_state = {"request_id": None, "poll_job": None, "deadline": 0}
        _quick_ui: Dict[str, Any] = {}

        def _quick_status(text: str, color: Any = None) -> None:
            st = _quick_ui.get("status")
            try:
                if st is not None and st.winfo_exists():
                    st.configure(text=text, text_color=color or ("gray40", "gray60"))
            except Exception:
                pass

        def _set_quick_buttons(state: str) -> None:
            for key in ("google", "passkey"):
                b = _quick_ui.get(key)
                try:
                    if b is not None and b.winfo_exists():
                        b.configure(state=state)
                except Exception:
                    pass

        def _build_quick_login_tab() -> None:
            """(Re)build the Quick Login tab buttons (used after profile form)."""
            for wgt in quick_inner.winfo_children():
                wgt.destroy()
            _quick_ui.clear()

            ctk.CTkLabel(quick_inner, text="Login with Google or Passkey",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         anchor="w").pack(fill="x")
            ctk.CTkLabel(quick_inner,
                         text=tr("license.browser_login_hint"),
                         font=ctk.CTkFont(size=11), text_color="gray60",
                         anchor="w", wraplength=390, justify="left").pack(fill="x", pady=(2, 14))

            g_icon = self._get_google_g_icon()
            google = ctk.CTkButton(
                quick_inner, text="  Continue with Google",
                image=g_icon if g_icon else None,
                compound="left",
                fg_color=("#FFFFFF", "#3A3A3A"),
                hover_color=("#F3F4F6", "#4A4A4A"),
                text_color=("#1F2937", "#F3F4F6"),
                border_width=1, border_color=("#D1D5DB", "#4B5563"),
                height=42, corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda: _start_oauth("google"),
            )
            google.pack(fill="x", ipady=2)
            _quick_ui["google"] = google

            passkey = ctk.CTkButton(
                quick_inner, text="🔐  Sign in with Passkey",
                fg_color=("#111827", "#E5E7EB"),
                hover_color=("#1F2937", "#D1D5DB"),
                text_color=("#FFFFFF", "#111827"),
                height=42, corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda: _start_oauth("passkey"),
            )
            passkey.pack(fill="x", pady=(10, 0), ipady=2)
            _quick_ui["passkey"] = passkey

            status = ctk.CTkLabel(quick_inner, text="", font=ctk.CTkFont(size=11),
                                  anchor="w", wraplength=390, justify="left")
            status.pack(fill="x", pady=(12, 6))
            _quick_ui["status"] = status

            cancel = ctk.CTkButton(quick_inner, text="Cancel", width=110, height=32,
                                   fg_color="gray", state="disabled",
                                   command=_cancel_oauth)
            cancel.pack()
            _quick_ui["cancel"] = cancel

        def _cancel_oauth() -> None:
            if _oauth_state["poll_job"]:
                try:
                    win.after_cancel(_oauth_state["poll_job"])
                except Exception:
                    pass
            _oauth_state["request_id"] = None
            _oauth_state["poll_job"] = None
            _set_quick_buttons("normal")
            cb = _quick_ui.get("cancel")
            if cb is not None:
                cb.configure(state="disabled")
            _quick_status("Cancelled.", ("gray40", "gray60"))

        def _activate_from_oauth(data: Dict[str, Any]) -> None:
            """Save the license payload returned by the server and close the window."""
            if not win.winfo_exists():
                return
            progress_bar.stop()
            progress_bar.pack_forget()
            try:
                save_config('last_used_email', data.get('user_email') or '')
                save_config('last_used_license_key', data.get('key') or '')
                self._storage_alert_shown = False
                self.app_state.license_info = data
                with open(get_data_path('license.dat'), 'w') as f:
                    json.dump(self.app_state.license_info, f)
                self.play_sound("success")
                _quick_status("✅  Activated successfully!", ("#059669", "#10B981"))
                win.after(500, lambda: [activated.set(True), win.destroy()])
            except Exception as e:
                logger.debug("activate_from_oauth failed: %s", e, exc_info=True)
                _quick_status(f"❌  {e}", ("#DC2626", "#EF4444"))
                _set_quick_buttons("normal")

        def _oauth_poll(rid: str) -> None:
            def _thread():
                try:
                    resp = self.app_state.http_session.get(
                        f"{config.LICENSE_SERVER_URL}/api/oauth/status",
                        params={"request_id": rid}, timeout=8)
                    data = resp.json()
                except Exception:
                    data = {"status": "error", "reason": tr("license.server_unreachable")}

                def _handle():
                    if not win.winfo_exists():
                        return
                    if _oauth_state.get("request_id") != rid:
                        return  # cancelled / replaced
                    st = data.get("status")
                    if st == "pending":
                        if time.time() > _oauth_state["deadline"]:
                            _quick_status(tr("license.session_expired"),
                                          ("#DC2626", "#EF4444"))
                            _set_quick_buttons("normal")
                            _oauth_state["request_id"] = None
                            return
                        _oauth_state["poll_job"] = win.after(2000, lambda: _oauth_poll(rid))
                    elif st == "needs_profile":
                        _show_profile_form(rid, data.get("profile") or {})
                    elif st == "success" or "key" in data:
                        _activate_from_oauth(data)
                    else:
                        _quick_status(f"❌  {data.get('reason', 'Login failed.')}",
                                      ("#DC2626", "#EF4444"))
                        _set_quick_buttons("normal")
                        _oauth_state["request_id"] = None

                self.after(0, _handle)

            threading.Thread(target=_thread, daemon=True).start()

        def _start_oauth(provider: str) -> None:
            if _oauth_state.get("request_id"):
                return
            _set_quick_buttons("disabled")
            cb = _quick_ui.get("cancel")
            if cb is not None:
                cb.configure(state="normal")
            _quick_status("⏳  Starting...", ("#2563EB", "#60A5FA"))

            def _thread():
                try:
                    resp = self.app_state.http_session.post(
                        f"{config.LICENSE_SERVER_URL}/api/oauth/begin",
                        json={"provider": provider, "machine_id": self.app_state.machine_id},
                        timeout=12)
                    data = resp.json()
                    if resp.status_code == 200 and data.get("status") == "success":
                        rid = data["request_id"]
                        _oauth_state["request_id"] = rid
                        _oauth_state["deadline"] = time.time() + 600

                        def _open():
                            webbrowser.open_new_tab(data["auth_url"])
                            _quick_status(tr("license.browser_opened"),
                                          ("#2563EB", "#60A5FA"))
                            _oauth_poll(rid)
                        self.after(0, _open)
                    else:
                        reason = data.get("reason", "Failed to start login.")
                        self.after(0, lambda: (
                            _quick_status(f"❌  {reason}", ("#DC2626", "#EF4444")),
                            _set_quick_buttons("normal"),
                        ))
                except Exception as e:
                    self.after(0, lambda: (
                        _quick_status(f"❌  {e}", ("#DC2626", "#EF4444")),
                        _set_quick_buttons("normal"),
                    ))

            threading.Thread(target=_thread, daemon=True).start()

        # ── Profile completion (registration gating for new Google users) ──
        def _show_profile_form(rid: str, profile: Dict[str, Any]) -> None:
            for wgt in quick_inner.winfo_children():
                wgt.destroy()
            _quick_ui.clear()

            ctk.CTkLabel(quick_inner,                          text=tr("license.registration_title"),
                         font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(fill="x")
            name_lbl = profile.get("name") or ""
            email_lbl = profile.get("email") or ""
            info_txt = f"Google: {email_lbl}"
            if name_lbl:
                info_txt = f"{name_lbl}\n{email_lbl}"
            ctk.CTkLabel(quick_inner, text=info_txt, font=ctk.CTkFont(size=11),
                         text_color="gray60", anchor="w", justify="left",
                         wraplength=390).pack(fill="x", pady=(2, 4))
            ctk.CTkLabel(quick_inner,                          text=tr("license.registration_hint"),
                         font=ctk.CTkFont(size=11), text_color="gray60", anchor="w",
                         justify="left", wraplength=390).pack(fill="x", pady=(0, 10))

            # Mobile
            ctk.CTkLabel(quick_inner, text="Mobile Number *", anchor="w",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x")
            mobile_entry = ctk.CTkEntry(quick_inner, placeholder_text="10-digit mobile",
                                        font=ctk.CTkFont(size=12), height=32)
            mobile_entry.pack(fill="x", pady=(2, 8))

            # State + District (dependent dropdowns)
            loc_row = ctk.CTkFrame(quick_inner, fg_color="transparent")
            loc_row.pack(fill="x", pady=(0, 8))
            loc_row.grid_columnconfigure(0, weight=1, uniform="loc")
            loc_row.grid_columnconfigure(1, weight=1, uniform="loc")

            ctk.CTkLabel(loc_row, text="State *", anchor="w",
                         font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 6))
            state_var = tkinter.StringVar(value="Select a State")
            state_menu = ctk.CTkOptionMenu(loc_row, values=["Select a State"] + sorted(STATE_DISTRICT_MAP.keys()),
                                           variable=state_var, height=32, font=ctk.CTkFont(size=12))
            state_menu.grid(row=1, column=0, sticky="ew", padx=(0, 6))

            ctk.CTkLabel(loc_row, text="District *", anchor="w",
                         font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, sticky="w")
            dist_var = tkinter.StringVar(value="Select State First")
            dist_menu = ctk.CTkOptionMenu(loc_row, values=["Select State First"],
                                          variable=dist_var, height=32,
                                          font=ctk.CTkFont(size=12), state="disabled")
            dist_menu.grid(row=1, column=1, sticky="ew")

            def _on_state(s: str) -> None:
                dists = STATE_DISTRICT_MAP.get(s, [])
                if dists:
                    dist_menu.configure(values=dists, state="normal")
                    if dist_var.get() not in dists:
                        dist_var.set("Select District")
                else:
                    dist_menu.configure(state="disabled")
                    dist_var.set("Select State First")
            state_var.trace_add("write", lambda *a: _on_state(state_var.get()))

            # Block
            ctk.CTkLabel(quick_inner, text="Block *", anchor="w",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x")
            block_entry = ctk.CTkEntry(quick_inner, placeholder_text="Block name",
                                       font=ctk.CTkFont(size=12), height=32)
            block_entry.pack(fill="x", pady=(2, 8))

            # Referral (optional)
            ctk.CTkLabel(quick_inner, text="Referral Code (Optional)", anchor="w",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x")
            referral_entry = ctk.CTkEntry(quick_inner, placeholder_text="Ask your friend for a code",
                                          font=ctk.CTkFont(size=12), height=32)
            referral_entry.pack(fill="x", pady=(2, 10))

            pf_status = ctk.CTkLabel(quick_inner, text="", font=ctk.CTkFont(size=11),
                                     anchor="w", wraplength=390, justify="left")
            pf_status.pack(fill="x", pady=(0, 6))

            def _submit_profile() -> None:
                mobile = mobile_entry.get().strip()
                state = state_var.get()
                district = dist_var.get()
                block = block_entry.get().strip()
                missing = []
                if len(mobile) < 10 or not mobile.isdigit():
                    missing.append("Mobile Number")
                if not state or state == "Select a State":
                    missing.append("State")
                if not district or district in ("Select State First", "Select District"):
                    missing.append("District")
                if not block:
                    missing.append("Block")
                if missing:
                    self.play_sound("error")
                    pf_status.configure(text=f"⚠️  Please fill: {', '.join(missing)}",
                                        text_color=("#DC2626", "#EF4444"))
                    return

                submit_btn.configure(state="disabled", text="⏳ Registering...")
                pf_status.configure(text=tr("license.registration_in_progress"),
                                    text_color=("#2563EB", "#60A5FA"))

                def _thread():
                    try:
                        payload = {
                            "request_id": rid,
                            "mobile": mobile,
                            "state": state,
                            "district": district,
                            "block": block,
                            "referral_code": referral_entry.get().strip(),
                        }
                        resp = self.app_state.http_session.post(
                            f"{config.LICENSE_SERVER_URL}/api/oauth/complete-profile",
                            json=payload, timeout=20)
                        data = resp.json()
                        if resp.status_code == 200 and "key" in data:
                            self.after(0, lambda: _activate_from_oauth(data))
                        else:
                            reason = data.get("reason", "Registration failed.")
                            self.after(0, lambda r=reason: (
                                self.play_sound("error"),
                                pf_status.configure(text=f"❌  {r}",
                                                    text_color=("#DC2626", "#EF4444")),
                                submit_btn.configure(state="normal", text="Register"),
                            ))
                    except Exception as e:
                        self.after(0, lambda: (
                            self.play_sound("error"),
                            pf_status.configure(text=f"❌  {e}",
                                                text_color=("#DC2626", "#EF4444")),
                            submit_btn.configure(state="normal", text="Register"),
                        ))

                threading.Thread(target=_thread, daemon=True).start()

            submit_btn = ctk.CTkButton(
                quick_inner, text="Register", command=_submit_profile,
                fg_color=("#059669", "#10B981"), hover_color=("#047857", "#059669"),
                height=38, corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"))
            submit_btn.pack(fill="x", pady=(2, 4))

            back_lbl = ctk.CTkLabel(quick_inner, text="←  Back", cursor="hand2",
                                    text_color=("#2563EB", "#60A5FA"),
                                    font=ctk.CTkFont(size=12))
            back_lbl.pack(pady=(6, 0))
            # Reset the handshake state first so a fresh OAuth flow can start
            back_lbl.bind("<Button-1>",
                          lambda e: [_cancel_oauth(), _build_quick_login_tab()])

        def _fetch_oauth_config() -> None:
            """Disable providers the server has not enabled (e.g. Google)."""
            def _thread():
                try:
                    resp = self.app_state.http_session.get(
                        f"{config.LICENSE_SERVER_URL}/api/oauth/config", timeout=8)
                    data = resp.json()
                    ok = data.get("status") == "success"
                except Exception:
                    ok = False
                    data = {}

                def _apply():
                    if not win.winfo_exists():
                        return
                    g = _quick_ui.get("google")
                    if g is not None:
                        if not ok or not data.get("google_enabled"):
                            g.configure(state="disabled",
                                        text="Google login unavailable")
                self.after(0, _apply)
            threading.Thread(target=_thread, daemon=True).start()

        _build_quick_login_tab()
        _fetch_oauth_config()

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

        # SECURITY: license key kabhi browser URL mein nahi aata. Server se
        # signed opaque buy-link lete hain (key sirf Authorization header mein
        # jata hai, TLS ke andar). Server verify karke user ko prefill karta hai.
        try:
            headers = {'Authorization': f"Bearer {self.app_state.license_info['key']}"}
            resp = self.app_state.http_session.post(
                f"{config.LICENSE_SERVER_URL}/api/get-buy-link",
                headers=headers, timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get('status') == 'success' and data.get('url'):
                webbrowser.open_new_tab(data['url'])
                return
        except Exception:
            logger.warning("get-buy-link failed — falling back to plain /buy page", exc_info=True)

        # Fallback: bina key ke buy page kholo — user wahan email dal ke
        # register/renew kar sakta hai (raw key URL mein expose nahi hoti).
        webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/buy")

    # Secure web-portal deep links (My Account / Files / Upgrade Storage).
    # License key is password-equivalent — it must never appear in a browser
    # URL. We fetch a short-lived signed token from the server (key travels
    # only in the Authorization header over TLS) and open
    # /authenticate-from-app/<token>?next=<dest>, which logs the user in and
    # lands them on the requested page — no manual login needed.
    _WEB_PORTAL_DESTS = {
        'account': '/account',
        'files': '/files',
        'storage': '/upgrade-storage',
    }

    def open_web_page(self, dest: str = 'account') -> None:
        """Open a web portal page logged in as the current user (no login needed)."""
        if not self.app_state.license_info.get('key'):
            self.play_sound("error")
            messagebox.showerror("Error", "License key not found.")
            return
        try:
            headers = {'Authorization': f"Bearer {self.app_state.license_info['key']}"}
            resp = self.app_state.http_session.post(
                f"{config.LICENSE_SERVER_URL}/api/get-auth-token",
                headers=headers, timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get('status') == 'success' and data.get('token'):
                url = (f"{config.LICENSE_SERVER_URL}/authenticate-from-app/"
                       f"{data['token']}?next={dest}")
                webbrowser.open_new_tab(url)
                return
        except Exception:
            logger.warning("get-auth-token failed — opening plain page instead", exc_info=True)

        # Fallback: bina key ke destination page kholo — server login par
        # redirect karega agar session nahi hai. Raw key kabhi URL nahi jati.
        fallback = self._WEB_PORTAL_DESTS.get(dest, '/account')
        webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}{fallback}")

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
                self.after(3000, self._maybe_show_storage_full_alert)
        finally: self.app_state.is_validating_license = False

    def _maybe_show_storage_full_alert(self) -> None:
        """Show a one-time alert (per session) when cloud storage is full/nearly full.

        The alert's button opens the upgrade-storage page, where the user can
        either buy more space or clear old data (date-wise folders) to free
        space — so they can act without hunting for the page.
        """
        if getattr(self, '_storage_alert_shown', False):
            return
        try:
            lic = self.app_state.license_info or {}
            try:
                usage = int(lic.get('total_usage') or 0)
                limit = int(lic.get('max_storage') or 0)
            except (TypeError, ValueError):
                return
            if limit <= 0:
                return
            pct = (usage / limit) * 100
            if pct < 90:
                return

            self._storage_alert_shown = True
            self.play_sound("error")
            if pct >= 100:
                title, msg = (
                    "⚠️ Cloud Storage Full",
                    f"Aapka cloud storage {pct:.0f}% bhar chuka hai\n"
                    f"({format_bytes(usage)} of {format_bytes(limit)}).\n\n"
                    "Ab nayi files save nahi ho payengi. Aap ya to:\n"
                    "  • Purana data clear karein (1 month se purana) — free space\n"
                    "  • Ya storage upgrade karein\n\n"
                    "Dono options ek hi page par hain — kholen?",
                )
            else:
                title, msg = (
                    "⚠️ Cloud Storage Almost Full",
                    f"Aapka cloud storage {pct:.0f}% bhar chuka hai\n"
                    f"({format_bytes(usage)} of {format_bytes(limit)}).\n\n"
                    "Purana data clear karke ya upgrade karke space free kar sakte hain.\n\n"
                    "Page kholen?",
                )
            if messagebox.askyesno(title, msg, parent=self):
                try:
                    self.open_web_page('storage')
                except Exception:
                    logger.warning("Could not open storage page", exc_info=True)
        except Exception:
            logger.warning("Storage alert check failed", exc_info=True)

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

                # 1b. Heartbeat — update licenses.last_seen on the server so the
                # admin panel can show which users are currently online.
                try:
                    lic = getattr(self.app_state, 'license_info', {}) or {}
                    hb_key = (lic.get('key') or '').strip()
                    if hb_key:
                        # user_level (GP/PO) bhi bheja jata hai taaki web admin
                        # panel dikha sake ki user kis level ka hai.
                        self.app_state.http_session.post(
                            f"{config.LICENSE_SERVER_URL}/api/heartbeat",
                            json={'key': hb_key,
                                  'app_version': config.APP_VERSION,
                                  'user_level': (lic.get('user_level') or '').strip().upper()},
                            timeout=5,
                        )
                        _cookie_req_count += 1
                except Exception:
                    pass  # Heartbeat failure is non-fatal — try again next cycle

                # 2. Fetch App Config (Every 120s -> 6 loops of 20s)
                if ping_counter % 6 == 0:
                    try:
                        url = f"{config.LICENSE_SERVER_URL}/api/app-config"
                        resp = self.app_state.http_session.get(url, timeout=10)
                        _cookie_req_count += 1
                        if resp.status_code == 200:
                            data = resp.json()
                            # Server-driven state registry (admin /portal-states)
                            # — naye states release ke bina add ho sakte hain.
                            # Registry built-in STATE_* dicts par override hota
                            # hai; koi bhi invalid payload silently ignore hota
                            # hai (update_state_registry sanitize karta hai).
                            try:
                                config.update_state_registry(data.get("states"))
                            except Exception:
                                pass
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

                            # One-time popup announcement (admin → user)
                            popup = data.get("announcement_popup") or None
                            if popup and isinstance(popup, dict) and popup.get("active"):
                                try:
                                    self.after(0, lambda p=popup: self._maybe_show_announcement_popup(p))
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

    # ------------------------------------------------------------------
    # ONE-TIME ANNOUNCEMENT POPUP (admin → user, with go-to-tab button)
    # ------------------------------------------------------------------

    def _maybe_show_announcement_popup(self, popup: Dict[str, Any]) -> None:
        """Show the admin's one-time popup announcement (once per popup id).

        - Each announcement has a unique `id` from the server.
        - The user can tick "Don't show again" — the id is then saved to
          config.json and the popup never reappears for that id.
        - If the popup has a `target_tab`, a button is shown that navigates
          the user straight to that tab (e.g. a newly added automation).
        """
        try:
            popup_id = str(popup.get('id') or '').strip()
            message = (popup.get('message') or '').strip()
            if not message:
                return

            # Without an id there is no way to remember dismissal — treat the
            # message itself as the id so it still only shows once per session.
            if not popup_id:
                popup_id = "msg:" + message[:64]

            # Respect the user's "don't show again" choice
            dismissed = get_config('dismissed_announcements') or []
            if popup_id and popup_id in dismissed:
                return

            # Only show once per app session even without a persisted choice
            if getattr(self, '_shown_popup_ids', None) is None:
                self._shown_popup_ids = set()
            if popup_id and popup_id in self._shown_popup_ids:
                return
            if popup_id:
                self._shown_popup_ids.add(popup_id)

            button_text = (popup.get('button_text') or 'OK').strip() or 'OK'
            target_tab = (popup.get('target_tab') or '').strip()

            win = ctk.CTkToplevel(self)
            win.title(f"{config.APP_SHORT_NAME} - Announcement")
            win.update_idletasks()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h = min(460, sw - 40), min(420, sh - 40)
            win.geometry(f'{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}')
            win.resizable(False, False)
            win.transient(self)
            win.grab_set()

            outer = ctk.CTkFrame(win, fg_color="transparent")
            outer.pack(expand=True, fill="both", padx=20, pady=18)

            # Header
            head = ctk.CTkFrame(outer, fg_color="transparent")
            head.pack(fill="x", pady=(0, 10))
            try:
                icon = ctk.CTkImage(Image.open(resource_path("assets/logo.png")), size=(34, 34))
                ctk.CTkLabel(head, image=icon, text="").pack(side="left", padx=(0, 10))
            except Exception:
                ctk.CTkLabel(head, text="📢", font=ctk.CTkFont(size=24)).pack(side="left", padx=(0, 10))
            ctk.CTkLabel(head, text="Announcement",
                         font=ctk.CTkFont(size=16, weight="bold"), anchor="w").pack(fill="x")

            # Message
            msg_frame = ctk.CTkFrame(outer, fg_color=("gray95", "gray25"), corner_radius=10)
            msg_frame.pack(fill="both", expand=True, pady=(0, 12))
            msg_lbl = ctk.CTkLabel(
                msg_frame, text=message, justify="left", anchor="w",
                font=ctk.CTkFont(size=13), wraplength=w - 70,
                text_color=("gray20", "gray90"),
            )
            msg_lbl.pack(fill="both", expand=True, padx=16, pady=14)

            # Don't-show-again checkbox
            dont_show_var = tkinter.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(outer, text="Don't show this again",
                                 variable=dont_show_var, font=ctk.CTkFont(size=12))
            cb.pack(anchor="w", pady=(0, 10))

            def _mark_dismissed():
                if popup_id and dont_show_var.get():
                    dismissed = list(get_config('dismissed_announcements') or [])
                    if popup_id not in dismissed:
                        dismissed.append(popup_id)
                        save_config('dismissed_announcements', dismissed)

            def _open_tab():
                _mark_dismissed()
                win.destroy()
                try:
                    self.show_frame(target_tab)
                except Exception:
                    logger.warning("Announcement target tab not found: %s", target_tab, exc_info=True)

            def _close():
                _mark_dismissed()
                win.destroy()

            btn_row = ctk.CTkFrame(outer, fg_color="transparent")
            btn_row.pack(fill="x", pady=(2, 0))
            btn_row.grid_columnconfigure(0, weight=1)

            if target_tab:
                go_btn = ctk.CTkButton(btn_row, text=button_text,
                                       command=_open_tab,
                                       fg_color=("#2563EB", "#3B82F6"),
                                       hover_color=("#1D4ED8", "#2563EB"),
                                       height=38, corner_radius=8,
                                       font=ctk.CTkFont(size=13, weight="bold"))
                go_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
                close_btn = ctk.CTkButton(btn_row, text="Close", command=_close,
                                          fg_color="gray", width=100, height=38,
                                          font=ctk.CTkFont(size=12))
                close_btn.grid(row=0, column=1, padx=(6, 0))
            else:
                ok_btn = ctk.CTkButton(btn_row, text=button_text, command=_close,
                                       fg_color=("#2563EB", "#3B82F6"),
                                       hover_color=("#1D4ED8", "#2563EB"),
                                       height=38, corner_radius=8,
                                       font=ctk.CTkFont(size=13, weight="bold"))
                ok_btn.grid(row=0, column=0, columnspan=2, sticky="ew")

            self.play_sound("notification")
        except Exception as e:
            logger.error("Failed to show announcement popup: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # USER DATA CLOUD BACKUP (Settings → Cloud Backup)
    # ------------------------------------------------------------------

    def _collect_user_data(self) -> Dict[str, Any]:
        """Gather all syncable user data for the cloud backup.

        Includes: autocomplete suggestions (covers location data),
        per-tab saved inputs, staff/mate mappings, and app config
        (theme, browser, toggles). Activity log / usage stats are NOT
        included (they sync separately / are not needed on a new PC).
        """
        hm = self.history_manager
        data: Dict[str, Any] = {}

        suggestions = hm.export_all_suggestions()
        if suggestions:
            data['suggestions'] = suggestions

        tab_inputs = hm.export_tab_inputs()
        if tab_inputs:
            data['tab_inputs'] = tab_inputs

        # Staff / mate mappings (JSON files)
        maps: Dict[str, Any] = {}
        for fname in ("mr_panchayat_staff_map.json", "mb_panchayat_mate_map.json"):
            fp = get_data_path(fname)
            if os.path.exists(fp):
                try:
                    with open(fp, "r") as f:
                        maps[fname] = json.load(f)
                except Exception:
                    maps[fname] = {}
        if maps:
            data['staff_maps'] = maps

        # App config (theme / browser / toggles) — whitelist only
        cfg_keys = ["theme", "last_used_browser", "sound_enabled",
                    "minimize_on_start", "whatsapp_automation_notify",
                    "whatsapp_excel_send"]
        cfg = {}
        for k in cfg_keys:
            try:
                v = get_config(k)
                if v is not None:
                    cfg[k] = v
            except Exception:
                continue
        if cfg:
            data['config'] = cfg

        # ── DPDP: Aadhaar number server par kabhi store NAHI hota. Backup
        # payload me bhi 12-digit Aadhaar patterns mask hote hain (user ne
        # suggestions/inputs me Aadhaar type kiya ho sakta hai). Sirf Aadhaar
        # pattern (exact 12-digit / 4-4-4) mask hota hai — baaki data (mobile,
        # name, staff maps) user ka apna consented backup hai, restore feature
        # ke liye intact rehta hai. Local data kabhi mutate nahi hota.
        try:
            from src.utils import mask_aadhaar_text as _mask_a

            def _mask_recursive(obj):
                if isinstance(obj, dict):
                    return {k: _mask_recursive(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_mask_recursive(v) for v in obj]
                if isinstance(obj, str):
                    return _mask_a(obj)
                return obj

            data = _mask_recursive(data)
        except Exception:
            pass  # Backup flow kabhi crash nahi hota — unmasked hi chala jayega

        return data

    def push_user_data_backup(self) -> bool:
        """Upload the current local user data snapshot to the server."""
        key = self.app_state.license_info.get('key')
        if not key:
            return False
        data = self._collect_user_data()
        if not data:
            return False
        try:
            headers = {'Authorization': f'Bearer {key}'}
            resp = self.app_state.http_session.post(
                f"{config.LICENSE_SERVER_URL}/api/user-data/backup",
                json={'data': data}, headers=headers, timeout=15)
            return resp.status_code == 200
        except Exception as e:
            logger.error("User data backup upload failed: %s", e)
            return False

    def pull_user_data_backup(self) -> bool:
        """Fetch the server backup and merge it into the local DB.

        Returns True if a backup existed and was applied. Used on a new PC
        (first activation) and after a factory reset (re-sync).
        """
        key = self.app_state.license_info.get('key')
        if not key:
            return False
        try:
            headers = {'Authorization': f'Bearer {key}'}
            resp = self.app_state.http_session.get(
                f"{config.LICENSE_SERVER_URL}/api/user-data/backup",
                headers=headers, timeout=15)
            if resp.status_code != 200:
                return False
            res = resp.json()
            data = res.get('data') or {}
            if not data:
                return False

            hm = self.history_manager
            added = 0
            if data.get('suggestions'):
                added += hm.import_all_suggestions(data['suggestions'])
            if data.get('tab_inputs'):
                added += hm.import_tab_inputs(data['tab_inputs'])

            # Staff / mate mappings
            for fname, payload in (data.get('staff_maps') or {}).items():
                if not isinstance(payload, dict):
                    continue
                fp = get_data_path(fname)
                try:
                    with open(fp, "w") as f:
                        json.dump(payload, f, indent=4)
                except Exception:
                    continue

            # App config
            for k, v in (data.get('config') or {}).items():
                try:
                    save_config(k, v)
                except Exception:
                    continue

            logger.info("User data restored from cloud backup (%s suggestions/inputs).", added)
            return True
        except Exception as e:
            logger.error("User data backup restore failed: %s", e)
            return False

    def clear_server_user_data(self) -> bool:
        """Delete the server-side backup (web account page also does this)."""
        key = self.app_state.license_info.get('key')
        if not key:
            return False
        try:
            headers = {'Authorization': f'Bearer {key}'}
            resp = self.app_state.http_session.delete(
                f"{config.LICENSE_SERVER_URL}/api/user-data/backup",
                headers=headers, timeout=15)
            return resp.status_code == 200
        except Exception as e:
            logger.error("User data backup clear failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # LOCATION FIX (Settings → Fix Location)
    # ------------------------------------------------------------------

    def fix_location_on_server(self, state: str, district: str, block: str = "") -> bool:
        """Push corrected state/district/block to the server license record."""
        key = self.app_state.license_info.get('key')
        if not key:
            return False
        try:
            headers = {'Authorization': f'Bearer {key}'}
            payload = {}
            if state:
                payload['state'] = state
            if district:
                payload['district'] = district
            if block:
                payload['block'] = block
            # user level (GP/PO) bhi server par bheja jata hai — admin panel
            # ko batane ke liye user kis level ka hai. (Heartbeat me bhi same
            # key naam use hota hai: 'user_level'.)
            level = (self.app_state.license_info.get('user_level') or '').strip().upper()
            if level in ('GP', 'PO'):
                payload['user_level'] = level
            if not payload:
                return False
            resp = self.app_state.http_session.post(
                f"{config.LICENSE_SERVER_URL}/api/update-location",
                json=payload, headers=headers, timeout=15)
            ok = resp.status_code == 200
            if ok:
                # Refresh local license_info so future syncs use the fixed values
                if state:
                    self.app_state.license_info['user_state'] = state.upper()
                if district:
                    self.app_state.license_info['user_district'] = district.upper()
                if block:
                    self.app_state.license_info['user_block'] = block.upper()
            return ok
        except Exception as e:
            logger.error("Fix location on server failed: %s", e)
            return False

    def set_user_level(self, level: str) -> None:
        """Detected portal login level ko persist karta hai.

        Two type ke users hote hain:
          • 'GP' — Panchayat (Gram Panchayat) level: portal par panchayat ka
            dropdown NAHI hota (naam text me), user sirf villages select karta hai.
          • 'PO' — Block level / Program Officer: portal par panchayat ka
            dropdown hota hai.

        Level tab ki automation ya Settings scrape se detect hota hai aur
        yahan save hota hai taaki:
          - app me (Settings > Server Synced Data) dikh sake, aur
          - heartbeat/update-location payload me server tak jaye jisse web
            ADMIN PANEL user ka type (GP/PO) dikha sake.
        """
        level = (level or '').strip().upper()
        if level not in ('GP', 'PO'):
            return
        lic = self.app_state.license_info
        if str(lic.get('user_level', '')).strip().upper() == level:
            return  # already stored — no repeated disk writes
        lic['user_level'] = level
        try:
            from src.utils import get_data_path
            with open(get_data_path('license.dat'), 'w') as f:
                json.dump(lic, f)
        except Exception:
            logger.debug("Failed to persist user_level", exc_info=True)

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

        # Home page cards ko bhi naye feature flags ke saath sync karo —
        # blocked/premium tabs wahan se bhi access na ho payen.
        try:
            home_tab = self.app_state.tab_instances.get("Home")
            if home_tab is not None and hasattr(home_tab, 'refresh_feature_states'):
                home_tab.refresh_feature_states()
        except Exception:
            pass

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
                # When an update is available the button must become an
                # install action — previously it stayed as "Check for Updates",
                # so users could only check, never install, from the About tab.
                # Only wire the download command if a URL is present (a missing
                # URL would crash the downloader).
                if info.get('url'):
                    about_tab.update_button.configure(
                        state="normal",
                        text=f"Download & Install v{info['version']}",
                        command=lambda: about_tab.download_and_install_update(
                            info.get('url', ''), info.get('version', '')
                        )
                    )
                else:
                    about_tab.update_button.configure(
                        state="normal", text="Check for Updates",
                        command=about_tab.check_for_updates
                    )
                try:
                    about_tab.show_new_version_changelog(info.get('changelog', []))
                except Exception:
                    pass
            elif info.get('status') == 'updated':
                about_tab.latest_version_label.configure(text="Latest Version: Up to date")
                about_tab.update_button.configure(
                    state="normal", text="Check for Updates",
                    command=about_tab.check_for_updates
                )
                try:
                    about_tab.hide_new_version_changelog()
                except Exception:
                    pass
            elif info.get('status') == 'error':
                about_tab.latest_version_label.configure(text="Latest Version: Check failed")
                about_tab.update_button.configure(
                    state="normal", text="Retry Check",
                    command=about_tab.check_for_updates
                )

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
        # Tab context goes into the structured automation_key column (admin
        # panel 'Task' column), so the plain message is logged — no redundant
        # '[tab]' prefix.
        active_tab = getattr(self.app_state, 'current_active_tab', '') or 'app'
        extra_info = self._get_active_tab_context()

        log_msg = message
        if extra_info:
            log_msg += f" ({extra_info})"

        self.history_manager.log_activity("SUCCESS", log_msg, automation_key=active_tab)

        if len(message) < 60 or "success" in message.lower() or "complete" in message.lower() or "finished" in message.lower():
            self.show_toast(message, kind="success")
            return "ok"
        else:
            self.play_sound("success")
            return self.app_state._original_showinfo(title, message, **options)

    def _custom_showwarning(self, title, message, **options):
        active_tab = getattr(self.app_state, 'current_active_tab', '') or 'app'
        extra_info = self._get_active_tab_context()

        log_msg = message
        if extra_info:
            log_msg += f" ({extra_info})"

        self.history_manager.log_activity("WARNING", log_msg, automation_key=active_tab)

        if len(message) < 50:
            self.show_toast(message, kind="warning")
            return "ok"

        self.play_sound("error")
        return self.app_state._original_showwarning(title, message, **options)

    def _custom_showerror(self, title, message, **options):
        active_tab = getattr(self.app_state, 'current_active_tab', '') or 'app'
        extra_info = self._get_active_tab_context()

        log_msg = f"Error: {message}"
        if extra_info:
            log_msg += f" ({extra_info})"

        self.history_manager.log_activity("ERROR", log_msg, automation_key=active_tab)

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
