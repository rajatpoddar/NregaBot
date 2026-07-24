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

    # ------------------------------------------------------------------
    # ACTIVATION WINDOW
    # ------------------------------------------------------------------

    def show_activation_window(self) -> bool:
        win = ctk.CTkToplevel(self); win.title("Activate Product")
        win.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(450, sw-40), min(580, sh-40)
        win.geometry(f'{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}')
        win.resizable(False, False); win.transient(self); win.grab_set()

        main = ctk.CTkScrollableFrame(win, fg_color="transparent")
        main.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(main, text="Product Activation", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10))
        activated = tkinter.BooleanVar(value=False)

        def on_trial():
            win.withdraw()
            if self.show_trial_registration_window(): activated.set(True); win.destroy()
            else: win.deiconify()

        def show_slots_full_ui(data):
            for widget in main.winfo_children(): widget.pack_forget()
            ctk.CTkLabel(main, text="All Device Slots Full", font=ctk.CTkFont(size=18, weight="bold"), text_color=config.COLORS["red_expired"]).pack(pady=(0, 5))
            ctk.CTkLabel(main, text="Deactivate an old device to use this one.", font=ctk.CTkFont(size=12)).pack(pady=(0, 10))
            device_frame = ctk.CTkFrame(main, fg_color="transparent")
            device_frame.pack(fill="x", pady=5)
            temp_key = data.get('license_key')
            devices = data.get('devices', [])
            for dev in devices:
                row = ctk.CTkFrame(device_frame, fg_color=(config.COLORS["gray90"], config.COLORS["gray30"]))
                row.pack(fill="x", pady=3, padx=5)
                info_frame = ctk.CTkFrame(row, fg_color="transparent")
                info_frame.pack(side="left", padx=10, pady=5)
                ctk.CTkLabel(info_frame, text=dev['name'], font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                if dev['name'] != dev['id']:
                    ctk.CTkLabel(info_frame, text=dev['id'], font=ctk.CTkFont(size=10), text_color="gray60").pack(anchor="w")
                if dev.get('is_pending'):
                    ctk.CTkLabel(row, text="Pending Approval ⏳", text_color=config.COLORS["device_pending_text"], font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=15)
                else:
                    def request_remove(mid=dev['id'], btn_ref=None):
                        if not messagebox.askyesno("Confirm", f"Request removal of {mid}?", parent=win): return
                        if btn_ref: btn_ref.configure(state="disabled", text="Sending...")
                        def _req_thread():
                            try:
                                headers = {'Authorization': f'Bearer {temp_key}'}
                                resp = self.app_state.http_session.post(f"{config.LICENSE_SERVER_URL}/api/request-deactivation", json={'machine_id': mid}, headers=headers, timeout=10)
                                res = resp.json()
                                if resp.status_code == 200 and res.get("status") == "success":
                                    self.after(0, lambda: messagebox.showinfo("Success", "Request Sent! Admin will review it.", parent=win))
                                    self.after(0, win.destroy)
                                else:
                                    self.after(0, lambda: messagebox.showerror("Error", res.get("reason", "Failed"), parent=win))
                                    if btn_ref: self.after(0, lambda: btn_ref.configure(state="normal", text="Request Removal"))
                            except Exception as e:
                                self.after(0, lambda: messagebox.showerror("Error", str(e), parent=win))
                                if btn_ref: self.after(0, lambda: btn_ref.configure(state="normal", text="Request Removal"))
                        threading.Thread(target=_req_thread, daemon=True).start()
                    btn = ctk.CTkButton(row, text="Request Removal", width=110, height=28, fg_color=config.COLORS["btn_stop"], hover_color=config.COLORS["btn_stop_hover"])
                    btn.configure(command=lambda m=dev['id'], b=btn: request_remove(m, b))
                    btn.pack(side="right", padx=10)
            footer_frame = ctk.CTkFrame(main, fg_color="transparent")
            footer_frame.pack(fill="x", pady=(20, 0))
            ctk.CTkLabel(footer_frame, text="Please contact:", font=ctk.CTkFont(size=12, weight="bold")).pack()
            email_label = ctk.CTkLabel(footer_frame, text="nregabot@gmail.com", text_color=(config.COLORS["blue"], config.COLORS["blue_light"]), cursor="hand2")
            email_label.pack()
            email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:nregabot@gmail.com"))
            ctk.CTkLabel(footer_frame, text="- OR -", text_color="gray60", font=ctk.CTkFont(size=10)).pack(pady=5)
            wa_link = ctk.CTkLabel(footer_frame, text="Join WhatsApp Community", text_color=config.COLORS["whatsapp_green"], font=ctk.CTkFont(weight="bold"), cursor="hand2")
            wa_link.pack()
            wa_link.bind("<Button-1>", lambda e: webbrowser.open("https://chat.whatsapp.com/Bup3hDCH3wn2shbUryv8wn"))
            try:
                qr_path = resource_path(os.path.join("assets", "whatsapp_qr.png"))
                if os.path.exists(qr_path):
                    pil_img = Image.open(qr_path)
                    qr_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(160, 160))
                    qr_label = ctk.CTkLabel(footer_frame, text="", image=qr_image)
                    qr_label.pack(pady=(10, 0))
                    qr_label.image = qr_image
                else: logger.warning("QR Image file not found at: %s", qr_path)
            except Exception as e: logger.error("QR Load Error: %s", e)
            ctk.CTkButton(main, text="Back to Login", command=lambda: [win.destroy(), self.show_activation_window()], fg_color="gray", width=150).pack(pady=20)

        ctk.CTkButton(main, text="Start 30-Day Free Trial", command=on_trial).pack(pady=(20, 5), ipady=4, fill='x', padx=10)
        ctk.CTkLabel(main, text="— OR —").pack(pady=10)
        entry = ctk.CTkEntry(main, width=300, placeholder_text="Enter License Key or Email"); entry.pack(pady=5, padx=10, fill='x')
        if get_config('last_used_email'): entry.insert(0, get_config('last_used_email'))
        otp_entry = ctk.CTkEntry(main, width=300, placeholder_text="Enter OTP (Only for Email Login)")
        otp_entry.pack(pady=5, padx=10, fill='x')

        def send_otp_login():
            email_val = entry.get().strip()
            if "@" not in email_val:
                messagebox.showwarning("Invalid", "Enter a valid email to send OTP.", parent=win)
                return
            send_otp_btn.configure(state="disabled", text="Sending...")
            try:
                resp = self.app_state.http_session.post(f"{config.LICENSE_SERVER_URL}/api/send-otp", json={"identifier": email_val}, timeout=10)
                if resp.status_code == 200:
                    messagebox.showinfo("OTP Sent", "Check your email for OTP", parent=win)
                else:
                    try: reason = resp.json().get("reason", "Failed")
                    except Exception: reason = f"Server returned status {resp.status_code}"
                    messagebox.showerror("Error", reason, parent=win)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)
            finally:
                win.after(30000, lambda: send_otp_btn.configure(state="normal", text="Send OTP"))

        send_otp_btn = ctk.CTkButton(main, text="Send OTP", command=send_otp_login, fg_color="gray")
        send_otp_btn.pack(pady=5, fill='x', padx=10)

        def on_unified_activate():
            input_val = entry.get().strip()
            otp_val = otp_entry.get().strip()
            if not input_val:
                self.play_sound("error")
                messagebox.showwarning("Input Required", "Please enter a key or email", parent=win)
                return
            activate_btn.configure(state="disabled", text="Activating...")
            if "@" in input_val and "." in input_val:
                if not otp_val:
                    self.play_sound("error")
                    messagebox.showwarning("OTP Required", "Please enter OTP for email login.", parent=win)
                    activate_btn.configure(state="normal", text="Login & Activate")
                    return
                try:
                    resp = self.app_state.http_session.post(f"{config.LICENSE_SERVER_URL}/api/login-for-activation", json={"email": input_val, "machine_id": self.app_state.machine_id, "otp": otp_val, "app_version": config.APP_VERSION}, timeout=15)
                    try: data = resp.json()
                    except Exception: raise Exception(f"Server returned an unexpected response (status {resp.status_code}). Please try again.")
                    if resp.status_code == 200 and data.get("status") == "success":
                        save_config('last_used_email', input_val)
                        self.app_state.license_info = data
                        with open(get_data_path('license.dat'), 'w') as f: json.dump(self.app_state.license_info, f)
                        self.play_sound("success")
                        messagebox.showinfo("Success", "Activated!", parent=win)
                        activated.set(True); win.destroy()
                    elif resp.status_code == 403 and data.get("status") == "slots_full":
                        self.play_sound("error"); show_slots_full_ui(data)
                    else:
                        self.play_sound("error")
                        if data.get("action") == "redirect":
                            if messagebox.askyesno("Action Required", data.get("reason") + "\n\nOpen website?"): webbrowser.open(data.get("url"))
                        else: messagebox.showerror("Failed", data.get("reason", "Error"), parent=win)
                except Exception as e:
                    self.play_sound("error")
                    messagebox.showerror("Error", str(e), parent=win)
                finally:
                    if activate_btn.winfo_exists(): activate_btn.configure(state="normal", text="Login & Activate")
            else:
                if self.validate_on_server(input_val):
                    activated.set(True); win.destroy()
                else:
                    if activate_btn.winfo_exists(): activate_btn.configure(state="normal", text="Login & Activate")

        activate_btn = ctk.CTkButton(main, text="Login & Activate", command=on_unified_activate); activate_btn.pack(pady=10, ipady=4, fill='x', padx=10)
        buy_link = ctk.CTkLabel(main, text="Purchase a License Key", text_color=("blue", "cyan"), cursor="hand2"); buy_link.pack(pady=(15,0))
        buy_link.bind("<Button-1>", lambda e: webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/buy"))
        self.wait_window(win); return activated.get()

    # ------------------------------------------------------------------
    # TRIAL REGISTRATION
    # ------------------------------------------------------------------

    def show_trial_registration_window(self) -> bool:
        win = ctk.CTkToplevel(self); win.title("Trial Registration")
        win.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(540, sw-40), min(650, sh-40)
        win.geometry(f'{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}')
        win.resizable(False, False); win.transient(self); win.grab_set()
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(expand=True, fill="both", padx=10, pady=10)
        ctk.CTkLabel(scroll, text="Start Your Free Trial", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 5))
        entries = {}
        def add_field(p, label, key):
            ctk.CTkLabel(p, text=label, anchor="w").pack(fill="x")
            e=ctk.CTkEntry(p); e.pack(fill="x", pady=(0,10)); entries[key]=e
        add_field(scroll, "Full Name", "full_name")
        add_field(scroll, "Email", "email")
        otp_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        otp_frame.pack(fill="x", pady=(0, 10))
        entries['otp'] = ctk.CTkEntry(otp_frame, placeholder_text="Enter OTP from Email")
        entries['otp'].pack(side="left", fill="x", expand=True, padx=(0, 5))

        def send_otp_action():
            email_val = entries['email'].get().strip()
            if not email_val or "@" not in email_val:
                messagebox.showerror("Error", "Enter valid email first", parent=win); return
            send_otp_btn.configure(state="disabled", text="Sending...")
            try:
                resp = self.app_state.http_session.post(f"{config.LICENSE_SERVER_URL}/api/send-otp", json={"identifier": email_val}, timeout=10)
                if resp.status_code == 200: messagebox.showinfo("OTP Sent", "Check your email for OTP", parent=win)
                else:
                    try: reason = resp.json().get("reason", "Failed")
                    except Exception: reason = f"Server returned status {resp.status_code}"
                    messagebox.showerror("Error", reason, parent=win)
            except Exception as e: messagebox.showerror("Error", str(e), parent=win)
            finally: win.after(30000, lambda: send_otp_btn.configure(state="normal", text="Resend OTP"))

        send_otp_btn = ctk.CTkButton(otp_frame, text="Send OTP", width=100, command=send_otp_action)
        send_otp_btn.pack(side="right")
        add_field(scroll, "Mobile", "mobile"); add_field(scroll, "Block", "block"); add_field(scroll, "Pincode", "pincode")
        ctk.CTkLabel(scroll, text="State", anchor="w").pack(fill="x")
        state_var = tkinter.StringVar(value="Select a State"); state_menu = ctk.CTkOptionMenu(scroll, values=sorted(list(STATE_DISTRICT_MAP.keys())), variable=state_var); state_menu.pack(fill="x", pady=(0,10)); entries['state']=state_var
        ctk.CTkLabel(scroll, text="District", anchor="w").pack(fill="x")
        dist_var = tkinter.StringVar(value="Select State First"); dist_menu = ctk.CTkOptionMenu(scroll, values=["Select State First"], variable=dist_var, state="disabled"); dist_menu.pack(fill="x", pady=(0,10)); entries['district']=dist_var
        def on_state(s):
            dists = STATE_DISTRICT_MAP.get(s, [])
            if dists: dist_menu.configure(values=dists, state="normal"); dist_var.set("Select District")
            else: dist_menu.configure(state="disabled")
        state_var.trace_add("write", lambda *args: on_state(state_var.get()))
        add_field(scroll, "Referral Code (Optional)", "referral_code")
        successful = tkinter.BooleanVar(value=False)

        def submit():
            data = {k: v.get().strip() for k, v in entries.items()}
            if not all(data.get(f) for f in ["full_name", "email", "mobile", "state", "otp"]):
                self.play_sound("error"); messagebox.showwarning("Error", "Missing fields or OTP", parent=win); return
            data["name"] = data.pop("full_name");            data["machine_id"] = self.app_state.machine_id
            submit_btn.configure(state="disabled", text="Requesting...")
            try:
                resp = self.app_state.http_session.post(f"{config.LICENSE_SERVER_URL}/api/request-trial", json=data, timeout=15)
                try: res = resp.json()
                except Exception: raise Exception(f"Server returned an unexpected response (status {resp.status_code}). Please try again.")
                if resp.status_code == 200 and res.get("status") == "success":
                    save_config('last_used_email', data['email'])
                    self.app_state.license_info = {'key': res.get("key"), 'expires_at': res.get('expires_at'), 'user_name': data['name'], 'key_type': 'trial'}
                    with open(get_data_path('license.dat'), 'w') as f: json.dump(self.app_state.license_info, f)
                    self.play_sound("success"); messagebox.showinfo("Success", "Trial Started!", parent=win); successful.set(True); win.destroy()
                else: self.play_sound("error"); messagebox.showerror("Error", res.get("reason", "Error"), parent=win)
            except Exception as e: self.play_sound("error"); messagebox.showerror("Error", str(e), parent=win)
            finally:
                if submit_btn.winfo_exists(): submit_btn.configure(state="normal", text="Start Trial")

        submit_btn = ctk.CTkButton(scroll, text="Start Trial", command=submit); submit_btn.pack(pady=20, fill='x')
        self.wait_window(win); return successful.get()

    # ------------------------------------------------------------------
    # PURCHASE, EXPIRY, LOCK/UNLOCK
    # ------------------------------------------------------------------

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
            if info['status'] == 'available':
                about_tab.latest_version_label.configure(text=f"Latest Version: {info['version']}")

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
