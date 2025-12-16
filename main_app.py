# main_app.py

# ============================================================================
# IMPORTS
# ============================================================================

# --- Standard Library ---
import threading
import time
import subprocess
import os
import webbrowser
import sys
import json
import logging
import socket
import shutil
import re
from datetime import datetime
from urllib.parse import urlencode

# --- Third Party UI & System ---
import tkinter
from tkinter import messagebox, filedialog
import customtkinter as ctk
import requests
from PIL import Image
from dotenv import load_dotenv
from packaging.version import parse as parse_version

# --- Windows Specific ---
import config
if config.OS_SYSTEM == "Windows":
    import ctypes

# --- Local Modules / UI Components ---
from ui_components import (
    CollapsibleFrame, OnboardingStep, SkeletonLoader, MarqueeLabel, 
    ToastNotification, OnboardingGuide, ComingSoonTab
)
from browser_manager import BrowserManager
from services import ServiceManager
from tab_config import get_tabs_definition
from icon_manager import load_icons
from sound_manager import SoundManager
from workflow_manager import WorkflowManager
from location_data import STATE_DISTRICT_MAP
from tabs.history_manager import HistoryManager
from utils import (
    resource_path, get_data_path, get_user_downloads_path, 
    get_config, save_config
)

# Note: Heavy libraries (Selenium, Pygame, Sentry) are imported inside 
# functions to speed up startup time.

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================

load_dotenv()
config.create_default_config_if_not_exists()

# Store original messagebox functions to override them later
_original_showinfo = messagebox.showinfo
_original_showwarning = messagebox.showwarning
_original_showerror = messagebox.showerror

# Theme Setup
ctk.set_default_color_theme(resource_path("theme.json"))
ctk.set_appearance_mode("System")


class NregaBotApp(ctk.CTk):
    """
    Main Application Class for NREGA Bot.
    Handles UI orchestration, navigation, license management, and automation dispatching.
    """

    # ============================================================================
    # 1. INITIALIZATION & LIFECYCLE
    # ============================================================================

    def __init__(self):
        super().__init__()
        
        # Initial Window State
        self.withdraw()  # Hide initially for smooth splash transition
        self.title(f"{config.APP_NAME}")
        
        # Dimensions & Constraints
        self.initial_width = 1100
        self.initial_height = 800
        self.minsize(1000, 700)

        # --- Feature Flags & Restrictions ---
        self.global_disabled_features = []
        self.trial_restricted_features = []

        # --- Service Managers ---
        self.history_manager = HistoryManager(self.get_data_path)
        self.browser_manager = BrowserManager(self)
        self.services = ServiceManager(self)
        self.sound_manager = SoundManager(self)
        self.workflows = WorkflowManager(self)
        
        # --- State Variables ---
        self.machine_id = self.services.machine_id
        self.is_licensed = False
        self.license_info = {}
        self.machine_id = self._get_machine_id()
        self.update_info = {"status": "Checking...", "version": None, "url": None}
        
        self.driver = None
        self.active_browser = None
        self.open_on_about_tab = False
        self.sleep_prevention_process = None
        self.is_validating_license = False
        
        # --- Automation & Threading Tracking ---
        self.active_automations = set()
        self.icon_images = {}
        self.automation_threads = {}
        self.stop_events = {}
        
        # --- UI Element Containers ---
        self.nav_buttons = {}
        self.content_frames = {}
        self.tab_instances = {}
        self.button_to_category_frame = {}
        self.category_frames = {}
        self.last_selected_category = get_config('last_selected_category', 'All Automations')
        
        # --- User Preferences (Reactive Variables) ---
        self.sound_switch_var = tkinter.BooleanVar(value=get_config('sound_enabled', True))
        self.minimize_var = tkinter.BooleanVar(value=True) 

        # --- UI Placeholders ---
        self.status_label = None
        self.server_status_indicator = None
        self.loading_animation_label = None
        self.is_animating = False
        self.splash = None

        # --- STARTUP SEQUENCE ---
        
        # 1. Show Splash Screen
        self.splash = self._create_splash_screen()
        self.splash.update() 

        # 2. Load Icons (Must be on Main Thread)
        self.icon_images = load_icons() 

        # 3. Start Background Initialization (Heavy Tasks)
        threading.Thread(target=self._background_initialization, daemon=True).start()

        # 4. Set Cleanup Protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_splash_screen(self):
        """Creates a borderless splash window centered on screen."""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)
        w, h = 300, 200
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        x, y = (sw/2) - (w/2), (sh/2) - (h/2)
        splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        
        try:
            logo = ctk.CTkImage(Image.open(resource_path("logo.png")), size=(80, 80))
            ctk.CTkLabel(splash, image=logo, text="").pack(pady=(20, 10))
        except Exception: 
            pass
        
        ctk.CTkLabel(splash, text=f"{config.APP_NAME}\nLoading...", font=("SF Pro Display", 14)).pack()
        splash.lift()
        splash.attributes("-topmost", True)
        return splash

    def _background_initialization(self):
        """Loads heavy libraries and assets in background to keep UI responsive."""
        # 1. Initialize Pygame (Audio)
        try:
            import pygame
            pygame.mixer.init()
        except Exception as e:
            print(f"Warning: Could not initialize audio mixer: {e}")

        # 2. Initialize Sentry (Network Monitoring)
        try:
            SENTRY_DSN = os.getenv("SENTRY_DSN")
            if SENTRY_DSN:
                import sentry_sdk
                sentry_sdk.init(
                    dsn=SENTRY_DSN,
                    release=f"{config.APP_NAME}@{config.APP_VERSION}",
                    traces_sample_rate=1.0,
                )
                sentry_sdk.set_user({"id": self.machine_id})
                sentry_sdk.set_tag("os.name", config.OS_SYSTEM)
        except Exception: 
            pass

        # 3. Apply Patches to Messagebox
        messagebox.showinfo = self._custom_showinfo
        messagebox.showwarning = self._custom_showwarning
        messagebox.showerror = self._custom_showerror

        # 4. Trigger UI Setup on Main Thread
        self.after(10, self._finish_startup)

    def _finish_startup(self):
        """Called on main thread after background loading is done."""
        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<FocusIn>", self._on_window_focus)
        
        # Build Grid Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self._create_header()
        self._create_footer()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Mac OS Specific Delay fix
        if config.OS_SYSTEM == "Darwin":
            self.update() 
            time.sleep(0.1)

        self._create_main_layout(for_activation=True)
        self.set_status("Initializing...")

        # License Check Flow
        self.perform_license_check_flow()

        # Transition Splash
        self.after(500, self._transition_from_splash)

    def _transition_from_splash(self):
        """Initiates splash fade out."""
        if self.splash: 
            self._fade_out_splash(self.splash, step=0)

    def _fade_out_splash(self, splash, step):
        """Recursively fades out the splash screen."""
        if step <= 5:
            try:
                if splash.winfo_exists():
                    splash.attributes("-alpha", 1.0 - (step / 5))
                    self.after(20, lambda: self._fade_out_splash(splash, step + 1))
                else:
                    self._fade_in_main_window()
            except Exception:
                self._fade_in_main_window()
        else:
            if splash.winfo_exists():
                splash.destroy()
            self.splash = None
            self.after(0, self._fade_in_main_window)

    def _fade_in_main_window(self):
        """Positions and shows the main application window."""
        self.update_idletasks()
        work_x, work_y, work_width, work_height = self._get_work_area()
        min_w, min_h = 1000, 700 
        app_height = min(self.initial_height, work_height - 40 if work_height > min_h else work_height)
        app_width = min(self.initial_width, work_width - 40 if work_width > min_w else work_width)
        app_height = max(app_height, min_h)
        app_width = max(app_width, min_w)
        
        x = work_x + (work_width // 2) - (app_width // 2)
        y = work_y + (work_height // 2) - (app_height // 2)
        
        self.geometry(f'{app_width}x{app_height}+{x}+{y}')
        
        self.attributes("-alpha", 1.0) 
        self.deiconify()
        self.lift() 
        self.focus_force() 

    def run_onboarding_if_needed(self):
        """Runs the onboarding tour for first-time users."""
        flag_path = get_data_path('.first_run_complete')
        if not os.path.exists(flag_path):
            OnboardingGuide(self)
            try:
                with open(flag_path, 'w') as f: f.write(datetime.now().isoformat())
            except Exception as e: print(f"Could not write first run flag: {e}")

    def on_closing(self, force=False):
        """Handles application shutdown."""
        if force or messagebox.askokcancel("Quit", "Quit application?", parent=self):
            try:
                self.play_sound("shutdown")
                self.attributes("-alpha", 0.0) # Hide window immediately
            except: pass
            
            # Force Kill Process
            import os
            os._exit(0)

    # ============================================================================
    # 2. LICENSE & AUTHENTICATION
    # ============================================================================

    def perform_license_check_flow(self):
        """Initial license validation flow."""
        self.is_licensed = self.check_license()
        self.after(0, self._setup_licensed_ui if self.is_licensed else self._setup_unlicensed_ui)
        
    def _preload_and_update_about_tab(self):
        """Ensures About tab is loaded so we can update version/license text."""
        if "About" not in self.tab_instances: 
            self.show_frame("About", raise_frame=False)
        self._update_about_tab_info()
        self.update_idletasks()

    def check_license(self):
        return self.services.check_license()

    def validate_on_server(self, key, is_startup_check=False):
        return self.services.validate_on_server(key, is_startup_check)

    def _setup_licensed_ui(self):
        """Unlocks the UI for valid license holders."""
        self._unlock_app()
        
        # --- Offline Lock Support with Fallback ---
        try:
            # 1. Load global restrictions
            self.global_disabled_features = self.license_info.get('global_disabled_features', [])
            
            # 2. Load trial restrictions
            key_type = str(self.license_info.get('key_type', '')).lower()
            
            if key_type == 'trial':
                if 'trial_restricted_features' in self.license_info:
                    self.trial_restricted_features = self.license_info['trial_restricted_features']
                else:
                    # FAIL-SAFE: Default PREMIUM features lock
                    self.trial_restricted_features = [
                        "Sarkar Aapke Dwar", "SAD Update Status", "FTO Generation", 
                        "MR Gen", "MR Fill", "MR Payment", "Gen Wagelist", 
                        "Send Wagelist", "Demand", "Allocation", "Work Allocation",
                        "eMB Entry", "eMB Verify", "WC Gen", "IF Editor"
                    ]
            else:
                self.trial_restricted_features = []
                
            # 3. Apply locks
            self._apply_feature_flags()
            
        except Exception as e:
            print(f"Error applying local restrictions: {e}")
        
        is_expiring = self.check_expiry_and_notify()
        self._preload_and_update_about_tab()
        self._ping_server_in_background()
        
        try:
            first_tab = list(list(self.get_tabs_definition().values())[0].keys())[0]
            self.show_frame("About" if is_expiring else first_tab)
        except:
            self.show_frame("About")
        
        self.check_for_updates_background()
        self.set_status("Ready")
        self.after(500, self.run_onboarding_if_needed)

    def _setup_unlicensed_ui(self):
        """Locks UI and prompts for activation."""
        self._preload_and_update_about_tab()
        self.set_status("Activation Required")
        if self.show_activation_window():
            self.is_licensed = True
            self._setup_licensed_ui()
        else:
            self.on_closing(force=True)

    def show_activation_window(self):
        """Displays the Activation / Login Modal."""
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

        # Helper: Slot Management UI
        def show_slots_full_ui(data):
            for widget in main.winfo_children(): widget.pack_forget()
            ctk.CTkLabel(main, text="All Device Slots Full", font=ctk.CTkFont(size=18, weight="bold"), text_color="#E53E3E").pack(pady=(0, 5))
            ctk.CTkLabel(main, text="Deactivate an old device to use this one.", font=ctk.CTkFont(size=12)).pack(pady=(0, 10))
            device_frame = ctk.CTkFrame(main, fg_color="transparent")
            device_frame.pack(fill="x", pady=5)
            temp_key = data.get('license_key')
            devices = data.get('devices', [])
            for dev in devices:
                row = ctk.CTkFrame(device_frame, fg_color=("gray90", "gray30"))
                row.pack(fill="x", pady=3, padx=5)
                info_frame = ctk.CTkFrame(row, fg_color="transparent")
                info_frame.pack(side="left", padx=10, pady=5)
                ctk.CTkLabel(info_frame, text=dev['name'], font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                if dev['name'] != dev['id']:
                    ctk.CTkLabel(info_frame, text=dev['id'], font=ctk.CTkFont(size=10), text_color="gray60").pack(anchor="w")
                if dev.get('is_pending'):
                    status_lbl = ctk.CTkLabel(row, text="Pending Approval ⏳", text_color=("orange", "#FFA500"), font=ctk.CTkFont(size=12, weight="bold"))
                    status_lbl.pack(side="right", padx=15)
                else:
                    def request_remove(mid=dev['id'], btn_ref=None):
                        if not messagebox.askyesno("Confirm", f"Request removal of {mid}?", parent=win): return
                        if btn_ref: btn_ref.configure(state="disabled", text="Sending...")
                        def _req_thread():
                            try:
                                headers = {'Authorization': f'Bearer {temp_key}'}
                                resp = requests.post(
                                    f"{config.LICENSE_SERVER_URL}/api/request-deactivation",
                                    json={'machine_id': mid}, headers=headers, timeout=10
                                )
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
                    btn = ctk.CTkButton(row, text="Request Removal", width=110, height=28, fg_color="#C53030", hover_color="#9B2C2C")
                    btn.configure(command=lambda m=dev['id'], b=btn: request_remove(m, b))
                    btn.pack(side="right", padx=10)
            footer_frame = ctk.CTkFrame(main, fg_color="transparent")
            footer_frame.pack(fill="x", pady=(20, 0))
            ctk.CTkLabel(footer_frame, text="Please contact:", font=ctk.CTkFont(size=12, weight="bold")).pack()
            email_label = ctk.CTkLabel(footer_frame, text="nregabot@gmail.com", text_color=("#3B82F6", "#60A5FA"), cursor="hand2")
            email_label.pack()
            email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:nregabot@gmail.com"))
            ctk.CTkLabel(footer_frame, text="- OR -", text_color="gray60", font=ctk.CTkFont(size=10)).pack(pady=5)
            wa_link = ctk.CTkLabel(footer_frame, text="Join WhatsApp Community", text_color="#25D366", font=ctk.CTkFont(weight="bold"), cursor="hand2")
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
                else: print("QR Image file not found at:", qr_path)
            except Exception as e: print(f"QR Load Error: {e}")
            ctk.CTkButton(main, text="Back to Login", command=lambda: [win.destroy(), self.show_activation_window()], fg_color="gray", width=150).pack(pady=20)
        
        # Trial Button
        ctk.CTkButton(main, text="Start 30-Day Free Trial", command=on_trial).pack(pady=(20, 5), ipady=4, fill='x', padx=10)
        ctk.CTkLabel(main, text="— OR —").pack(pady=10)
        
        # Inputs
        entry = ctk.CTkEntry(main, width=300, placeholder_text="Enter License Key or Email"); entry.pack(pady=5, padx=10, fill='x')
        if get_config('last_used_email'): entry.insert(0, get_config('last_used_email'))
        
        otp_entry = ctk.CTkEntry(main, width=300, placeholder_text="Enter OTP (Only for Email Login)")
        otp_entry.pack(pady=5, padx=10, fill='x')
        
        # OTP Logic
        def send_otp_login():
            email_val = entry.get().strip()
            if "@" not in email_val:
                messagebox.showwarning("Invalid", "Enter a valid email to send OTP.", parent=win)
                return
            
            send_otp_btn.configure(state="disabled", text="Sending...")
            try:
                resp = requests.post(f"{config.LICENSE_SERVER_URL}/api/send-otp", json={"identifier": email_val}, timeout=10)
                if resp.status_code == 200:
                    messagebox.showinfo("OTP Sent", "Check your email for OTP", parent=win)
                else:
                    messagebox.showerror("Error", resp.json().get("reason", "Failed"), parent=win)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)
            finally:
                win.after(30000, lambda: send_otp_btn.configure(state="normal", text="Send OTP"))

        send_otp_btn = ctk.CTkButton(main, text="Send OTP", command=send_otp_login, fg_color="gray")
        send_otp_btn.pack(pady=5, fill='x', padx=10)

        # Activation Logic
        def on_unified_activate():
            input_val = entry.get().strip()
            otp_val = otp_entry.get().strip()
            
            if not input_val: 
                self.play_sound("error")
                messagebox.showwarning("Input Required", "Please enter a key or email", parent=win)
                return
            
            activate_btn.configure(state="disabled", text="Activating...")
            
            if "@" in input_val and "." in input_val: # Email Logic
                if not otp_val:
                    self.play_sound("error")
                    messagebox.showwarning("OTP Required", "Please enter OTP for email login.", parent=win)
                    activate_btn.configure(state="normal", text="Login & Activate")
                    return

                try:
                    resp = requests.post(
                        f"{config.LICENSE_SERVER_URL}/api/login-for-activation", 
                        json={
                            "email": input_val, 
                            "machine_id": self.machine_id, 
                            "otp": otp_val,
                            "app_version": config.APP_VERSION 
                        }, 
                        timeout=15
                    )
                    data = resp.json()
                    
                    if resp.status_code == 200 and data.get("status") == "success":
                        save_config('last_used_email', input_val)
                        self.license_info = data
                        with open(get_data_path('license.dat'), 'w') as f: json.dump(self.license_info, f)
                        self.play_sound("success")
                        messagebox.showinfo("Success", "Activated!", parent=win)
                        activated.set(True)
                        win.destroy()
                    
                    elif resp.status_code == 403 and data.get("status") == "slots_full":
                        self.play_sound("error")
                        show_slots_full_ui(data)

                    else: 
                        self.play_sound("error")
                        if data.get("action") == "redirect":
                            if messagebox.askyesno("Action Required", data.get("reason") + "\n\nOpen website?"): 
                                webbrowser.open(data.get("url"))
                        else: 
                            messagebox.showerror("Failed", data.get("reason", "Error"), parent=win)
                except Exception as e: 
                    self.play_sound("error")
                    messagebox.showerror("Error", str(e), parent=win)
                finally: 
                    if activate_btn.winfo_exists(): 
                        activate_btn.configure(state="normal", text="Login & Activate")
            
            else: # Key Logic
                if self.validate_on_server(input_val): 
                    activated.set(True)
                    win.destroy()
                else: 
                    if activate_btn.winfo_exists(): 
                        activate_btn.configure(state="normal", text="Login & Activate")

        activate_btn = ctk.CTkButton(main, text="Login & Activate", command=on_unified_activate); activate_btn.pack(pady=10, ipady=4, fill='x', padx=10)
        buy_link = ctk.CTkLabel(main, text="Purchase a License Key", text_color=("blue", "cyan"), cursor="hand2"); buy_link.pack(pady=(15,0))
        buy_link.bind("<Button-1>", lambda e: webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/buy"))
        
        self.wait_window(win); return activated.get()

    def show_trial_registration_window(self):
        """Displays the Trial Registration Modal."""
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
            e=ctk.CTkEntry(p); e.pack(fill="x", pady=(0,10)) 
            entries[key]=e
            
        add_field(scroll, "Full Name", "full_name")
        add_field(scroll, "Email", "email")

        # OTP Section
        otp_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        otp_frame.pack(fill="x", pady=(0, 10))
        entries['otp'] = ctk.CTkEntry(otp_frame, placeholder_text="Enter OTP from Email")
        entries['otp'].pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        def send_otp_action():
            email_val = entries['email'].get().strip()
            if not email_val or "@" not in email_val:
                messagebox.showerror("Error", "Enter valid email first", parent=win)
                return
            
            send_otp_btn.configure(state="disabled", text="Sending...")
            try:
                resp = requests.post(f"{config.LICENSE_SERVER_URL}/api/send-otp", json={"identifier": email_val}, timeout=10)
                if resp.status_code == 200:
                    messagebox.showinfo("OTP Sent", "Check your email for OTP", parent=win)
                else:
                    messagebox.showerror("Error", resp.json().get("reason", "Failed"), parent=win)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)
            finally:
                win.after(30000, lambda: send_otp_btn.configure(state="normal", text="Resend OTP"))

        send_otp_btn = ctk.CTkButton(otp_frame, text="Send OTP", width=100, command=send_otp_action)
        send_otp_btn.pack(side="right")

        add_field(scroll, "Mobile", "mobile")
        add_field(scroll, "Block", "block")
        add_field(scroll, "Pincode", "pincode")
        
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
            
            data["name"] = data.pop("full_name"); data["machine_id"] = self.machine_id
            submit_btn.configure(state="disabled", text="Requesting...")
            try:
                resp = requests.post(f"{config.LICENSE_SERVER_URL}/api/request-trial", json=data, timeout=15)
                res = resp.json()
                if resp.status_code == 200 and res.get("status") == "success":
                    save_config('last_used_email', data['email'])
                    self.license_info = {'key': res.get("key"), 'expires_at': res.get('expires_at'), 'user_name': data['name'], 'key_type': 'trial'}
                    with open(get_data_path('license.dat'), 'w') as f: json.dump(self.license_info, f)
                    self.play_sound("success"); messagebox.showinfo("Success", "Trial Started!", parent=win); successful.set(True); win.destroy()
                else: self.play_sound("error"); messagebox.showerror("Error", res.get("reason", "Error"), parent=win)
            except Exception as e: self.play_sound("error"); messagebox.showerror("Error", str(e), parent=win)
            finally: 
                if submit_btn.winfo_exists(): submit_btn.configure(state="normal", text="Start Trial")
        
        submit_btn = ctk.CTkButton(scroll, text="Start Trial", command=submit); submit_btn.pack(pady=20, fill='x')
        self.wait_window(win); return successful.get()

    def show_purchase_window(self, context='upgrade'):
        if not self.license_info.get('key'): self.play_sound("error"); messagebox.showerror("Error", "License key missing"); return
        webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/buy?existing_key={self.license_info['key']}")

    def check_expiry_and_notify(self):
        exp = self.license_info.get('expires_at')
        if not exp: return False
        try:
            days = (datetime.fromisoformat(exp.split('T')[0]).date() - datetime.now().date()).days
            if 0 <= days < 7:
                self.play_sound("error"); messagebox.showwarning("Expiring", f"License expires in {days} days."); self.open_on_about_tab = True; return True
        except Exception: pass
        return False

    def _lock_app_to_about_tab(self):
        self.show_frame("About")
        for name, btn in self.nav_buttons.items():
            if name != "About": btn.configure(state="disabled")
        if hasattr(self, 'launch_chrome_btn'):
            self.launch_chrome_btn.configure(state="disabled")
            self.launch_edge_btn.configure(state="disabled")
            self.launch_firefox_btn.configure(state="disabled")
            self.theme_combo.configure(state="disabled")
            if hasattr(self, 'sound_switch'): self.sound_switch.configure(state="disabled")

    def _unlock_app(self):
        for btn in self.nav_buttons.values(): btn.configure(state="normal")
        self.launch_chrome_btn.configure(state="normal"); self.launch_edge_btn.configure(state="normal"); self.launch_firefox_btn.configure(state="normal")
        self.theme_combo.configure(state="normal")
        if hasattr(self, 'sound_switch'): self.sound_switch.configure(state="normal")
    
    def _validate_in_background(self):
        try:
            self.is_validating_license = True
            if self.validate_on_server(self.license_info.get('key'), is_startup_check=True):
                self.after(0, self._update_about_tab_info)
                fm_tab = self.tab_instances.get("File Manager")
                if fm_tab:
                    self.after(0, lambda: fm_tab.update_storage_info(self.license_info.get('total_usage'), self.license_info.get('max_storage')))
                    self.after(0, lambda: fm_tab.refresh_files(fm_tab.current_folder_id, add_to_history=False))
        finally: self.is_validating_license = False

    # ============================================================================
    # 3. UI CONSTRUCTION
    # ============================================================================

    def _create_header(self):
        """Constructs the top header with logo, announcement, and toolbar."""
        header = ctk.CTkFrame(self, corner_radius=15, fg_color=("white", "#1D1E1E")) 
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        header.grid_columnconfigure(1, weight=1)

        # Helper: Hover Effects
        def add_status_hover(btn, message):
            def on_enter(e):
                if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                    self.status_label.configure(text=message, text_color=("#3B82F6", "#60A5FA"))
            def on_leave(e):
                if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                    self.status_label.configure(text="Ready", text_color="gray60")
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

        # --- LEFT: Branding ---
        branding_frame = ctk.CTkFrame(header, fg_color="transparent")
        branding_frame.grid(row=0, column=0, sticky="w", padx=15, pady=8)
        
        try:
            logo = ctk.CTkImage(Image.open(resource_path("logo.png")), size=(38, 38))
            ctk.CTkLabel(branding_frame, image=logo, text="").pack(side="left", padx=(0, 12))
        except Exception: pass

        text_box = ctk.CTkFrame(branding_frame, fg_color="transparent")
        text_box.pack(side="left")
        
        ctk.CTkLabel(text_box, text=config.APP_NAME, font=ctk.CTkFont(size=18, weight="bold"), anchor="w", height=20).pack(anchor="w")
        
        welcome_sub_frame = ctk.CTkFrame(text_box, fg_color="transparent", height=15)
        welcome_sub_frame.pack(anchor="w")
        self.header_welcome_prefix_label = ctk.CTkLabel(welcome_sub_frame, text=f"v{config.APP_VERSION}", font=ctk.CTkFont(size=11), text_color="gray60")
        self.header_welcome_prefix_label.pack(side="left")
        self.header_welcome_name_label = ctk.CTkLabel(welcome_sub_frame, text="", font=ctk.CTkFont(size=11, weight="bold"))
        self.header_welcome_name_label.pack(side="left")
        self.header_welcome_suffix_label = ctk.CTkLabel(welcome_sub_frame, text="", font=ctk.CTkFont(size=11))
        self.header_welcome_suffix_label.pack(side="left")

        # --- MIDDLE: Announcement ---
        announcement_frame = ctk.CTkFrame(header, fg_color="transparent", height=30)
        announcement_frame.grid(row=0, column=1, sticky="ew", padx=20)
        announcement_frame.grid_propagate(False) 

        self.announcement_label = MarqueeLabel(announcement_frame, text="Connecting to server...", width=300)
        self.announcement_label.pack(fill="both", expand=True, pady=5)
        
        self.after(1000, self._fetch_app_config)

        # --- RIGHT: Toolbar ---
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.grid(row=0, column=2, sticky="e", padx=15, pady=8)

        # Extractor
        self.extractor_btn = ctk.CTkButton(
            controls_frame, text="", image=self.icon_images.get("extractor_icon"), 
            width=35, height=35, corner_radius=8,
            fg_color=("gray95", "gray25"), hover_color=("gray85", "gray35"),
            command=lambda: self.show_frame("Workcode Extractor")
        )
        self.extractor_btn.pack(side="left", padx=(0, 10))
        add_status_hover(self.extractor_btn, "Open Workcode Extractor")

        # Login Automation
        self.quick_login_btn = ctk.CTkButton(
            controls_frame, text="", image=self.icon_images.get("emoji_login_automation"), 
            width=35, height=35, corner_radius=8,
            fg_color=("gray95", "gray25"), hover_color=("gray85", "gray35"),
            command=self._quick_login_automation
        )
        self.quick_login_btn.pack(side="left", padx=(0, 10))
        add_status_hover(self.quick_login_btn, "Auto Login to NREGA")

        # Separator
        ctk.CTkFrame(controls_frame, width=2, height=20, fg_color=("gray90", "gray30")).pack(side="left", padx=(0, 10))

        # Browsers
        browser_group = ctk.CTkFrame(controls_frame, fg_color="transparent")
        browser_group.pack(side="left", padx=(0, 10))
        
        self.launch_chrome_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("chrome"), 
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_chrome_detached
        )
        self.launch_chrome_btn.pack(side="left", padx=2)
        add_status_hover(self.launch_chrome_btn, "Launch Google Chrome")

        self.launch_edge_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("edge"), 
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_edge_detached
        )
        self.launch_edge_btn.pack(side="left", padx=2)
        add_status_hover(self.launch_edge_btn, "Launch Microsoft Edge")

        self.launch_firefox_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("firefox"), 
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_firefox_managed
        )
        self.launch_firefox_btn.pack(side="left", padx=2)
        add_status_hover(self.launch_firefox_btn, "Launch Mozilla Firefox")

        # Separator
        ctk.CTkFrame(controls_frame, width=2, height=20, fg_color=("gray90", "gray30")).pack(side="left", padx=(0, 10))

        # Settings
        settings_group = ctk.CTkFrame(controls_frame, fg_color=("gray95", "gray25"), corner_radius=20)
        settings_group.pack(side="left")

        # Theme
        self.current_theme_mode = get_config("theme_mode", "System")
        self.theme_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("theme_system"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._cycle_theme
        )
        self.theme_btn.pack(side="left", padx=(5, 2), pady=4)
        add_status_hover(self.theme_btn, "Switch Theme (Light/Dark)")
        self._update_theme_icon()

        # Sound
        self.sound_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("sound_on"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_sound_toggle_click
        )
        self.sound_btn.pack(side="left", padx=2, pady=4)
        add_status_hover(self.sound_btn, "Toggle Sound Effects")
        self._update_settings_btn_visuals(self.sound_btn, self.sound_switch_var.get())

        # Minimize
        self.minimize_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("minimize"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_minimize_toggle_click
        )
        self.minimize_btn.pack(side="left", padx=(2, 5), pady=4)
        add_status_hover(self.minimize_btn, "Auto-Minimize on Start")
        self._update_settings_btn_visuals(self.minimize_btn, self.minimize_var.get())
        
        # Compatibility dummy
        self.theme_combo = ctk.CTkOptionMenu(self, width=0, height=0)

    def _create_main_layout(self, for_activation=False):
        """Constructs the sidebar and content area with a FIXED header."""
        # Clean old frame
        if hasattr(self, 'main_layout_frame') and self.main_layout_frame.winfo_exists():
            self.main_layout_frame.destroy()
            self.update_idletasks() 

        self.main_layout_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_layout_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 10))
        self.main_layout_frame.grid_rowconfigure(0, weight=1)
        self.main_layout_frame.grid_columnconfigure(1, weight=1)
        
        # --- LEFT SIDEBAR CONTAINER ---
        self.sidebar_container = ctk.CTkFrame(self.main_layout_frame, width=220, corner_radius=0, fg_color="transparent")
        self.sidebar_container.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.sidebar_container.grid_rowconfigure(1, weight=1)
        self.sidebar_container.grid_columnconfigure(0, weight=1)

        # 1. FIXED HEADER (Dropdown yahan aayega)
        self.sidebar_header = ctk.CTkFrame(self.sidebar_container, height=50, fg_color="transparent")
        self.sidebar_header.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
        self.sidebar_header.grid_propagate(False) # Height fix rakhne ke liye

        # 2. SCROLLABLE CONTENT (Buttons yahan aayenge)
        self.nav_scroll_frame = ctk.CTkScrollableFrame(self.sidebar_container, label_text="", fg_color="transparent")
        self.nav_scroll_frame.grid(row=1, column=0, sticky="nsew")
        
        # Populate Sidebar
        self._create_nav_buttons(self.sidebar_header, self.nav_scroll_frame)
        
        # --- RIGHT CONTENT AREA ---
        self.content_area = ctk.CTkFrame(self.main_layout_frame)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)
        
        self._create_content_frames()
        
        if for_activation: 
            self._lock_app_to_about_tab()

    def _create_nav_buttons(self, header_parent, content_parent):
        """Populates the navigation sidebar using tab config."""
        self.nav_buttons.clear()
        self.button_to_category_frame.clear()
        self.category_frames.clear()
        self.tab_icon_map = {} 

        # --- 1. Filter Dropdown (Fixed Header me) ---
        # Clear old widgets in header if any
        for widget in header_parent.winfo_children(): widget.destroy()

        categories = ["All Automations"] + list(self.get_tabs_definition().keys())
        
        self.category_filter_menu = ctk.CTkOptionMenu(
            header_parent, 
            values=categories, 
            command=self._on_category_filter_change,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=("white", "#2B2B2B"),
            button_color=("gray85", "gray35"),
            button_hover_color=("gray75", "gray45"),
            text_color=("gray10", "gray90"),
            dropdown_fg_color=("white", "#2B2B2B"),
            dropdown_text_color=("gray10", "gray90"),
            dropdown_hover_color=("gray90", "gray35"),
            anchor="w",
            corner_radius=8
        )
        self.category_filter_menu.set(self.last_selected_category)
        self.category_filter_menu.pack(fill="x", pady=10, padx=5)

        # --- 2. Categories & Buttons (Scrollable Area me) ---
        for cat, tabs in self.get_tabs_definition().items():
            
            # Category Frame
            cat_frame = CollapsibleFrame(content_parent, title=cat)
            self.category_frames[cat] = cat_frame
            
            for name, data in tabs.items():
                self.tab_icon_map[name] = data.get("icon")

                btn = ctk.CTkButton(
                    cat_frame.content_frame, 
                    text=f"{name}", 
                    image=data.get("icon"), 
                    compound="left", 
                    command=lambda n=name: self.show_frame(n), 
                    anchor="w", 
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"), 
                    height=40,          
                    corner_radius=8,    
                    fg_color="transparent", 
                    text_color=("gray30", "gray80"), 
                    hover_color=("gray90", "gray25"),
                    border_spacing=12    
                )
                btn.pack(fill="x", padx=8, pady=2) 
                
                self.nav_buttons[name] = btn
                self.button_to_category_frame[name] = cat_frame

                # Restricted/Maintenance Logic
                is_disabled = False
                if isinstance(self.global_disabled_features, list):
                    if name in self.global_disabled_features: is_disabled = True
                elif isinstance(self.global_disabled_features, dict):
                    if name in self.global_disabled_features: is_disabled = True
                
                if is_disabled:
                    btn.configure(
                        state="normal", 
                        text=f"{name} ⚠️",
                        fg_color=("#FEF2F2", "#450A0A"), 
                        text_color=("#DC2626", "#F87171"), 
                        hover_color=("#FEE2E2", "#7F1D1D") 
                    )

        self._filter_nav_menu(self.last_selected_category)

    def _create_footer(self):
        """Constructs the floating footer with status bar and quick links."""
        footer = ctk.CTkFrame(self, height=50, corner_radius=25, fg_color=("white", "#2B2B2B"))
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(6, weight=1)

        # LEFT SIDE: Status Bar
        status_frame = ctk.CTkFrame(footer, fg_color="transparent")
        status_frame.pack(side="left", padx=20, fill="y")
        
        # --- NEW: Copyright Label ---
        ctk.CTkLabel(
            status_frame, 
            text="© 2025 NREGA Bot", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            text_color=("gray50", "gray60")
        ).pack(side="left", padx=(0, 15))

        # Visual Separator
        ctk.CTkFrame(status_frame, width=2, height=14, fg_color=("gray80", "gray40")).pack(side="left", padx=(0, 10))
        # ----------------------------

        self.loading_animation_label = ctk.CTkLabel(status_frame, text="", width=20, font=ctk.CTkFont(size=14))
        self.loading_animation_label.pack(side="left")
        
        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color="gray60", font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=(5, 0))

        # RIGHT SIDE: Icon Dock
        dock_frame = ctk.CTkFrame(footer, fg_color="transparent")
        dock_frame.pack(side="right", padx=15, pady=5)

        def create_icon_btn(parent, icon_name, command, tooltip_text):
            icon = self.icon_images.get(icon_name)
            btn = ctk.CTkButton(
                parent, text="", image=icon, width=40, height=40, corner_radius=20,
                fg_color="transparent", hover_color=("gray90", "gray35"),
                command=command
            )
            btn.pack(side="left", padx=4)
            
            def on_enter(e):
                self.status_label.configure(text=tooltip_text, text_color=("#3B82F6", "#60A5FA")) 
            def on_leave(e):
                self.status_label.configure(text="Ready", text_color="gray60") 
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            return btn

        create_icon_btn(dock_frame, "history", self.show_history_window, "View Activity Log")
        create_icon_btn(dock_frame, "emoji_file_manager", self.open_web_file_manager, "Open Cloud Files")
        create_icon_btn(dock_frame, "whatsapp", lambda: webbrowser.open("https://chat.whatsapp.com/Bup3hDCH3wn2shbUryv8wn"), "Join Community")
        create_icon_btn(dock_frame, "feedback", lambda: self.show_frame("Feedback"), "Contact Support")

        # Separator Line
        ctk.CTkFrame(dock_frame, width=2, height=20, fg_color=("gray80", "gray40")).pack(side="left", padx=10)

        # Server Status Dot
        self.server_status_indicator = ctk.CTkFrame(dock_frame, width=12, height=12, corner_radius=6, fg_color="gray")
        self.server_status_indicator.pack(side="left", padx=(0, 5))
        
        def on_server_hover(e): self.status_label.configure(text="Server Connection Status")
        def on_server_leave(e): self.status_label.configure(text="Ready")
        self.server_status_indicator.bind("<Enter>", on_server_hover)
        self.server_status_indicator.bind("<Leave>", on_server_leave)

        self.set_status("Ready")

    # ============================================================================
    # 4. NAVIGATION & FRAME MANAGEMENT
    # ============================================================================

    def get_tabs_definition(self):
        """Loads tab definitions from config."""
        return get_tabs_definition(self)

    def _create_content_frames(self):
        """Prepares the container for tabs."""
        self.content_frames.clear()
        self.tab_instances.clear()
        self.show_frame("About", raise_frame=False)
    
    def show_frame(self, page_name, raise_frame=True):
        """Lazy loads and displays a specific tab."""
        self.current_active_tab = page_name
        
        # 1. Already Loaded
        if page_name in self.tab_instances:
            if raise_frame:
                self.content_frames[page_name].tkraise()
                self._update_nav_button_color(page_name)
            return

        # 2. Not Loaded: Show Skeleton
        loading_frame = ctk.CTkFrame(self.content_area)
        loading_frame.grid(row=0, column=0, sticky="nsew")
        skeleton = SkeletonLoader(loading_frame, rows=4)
        loading_frame.tkraise()
        self.update_idletasks()
        
        # 3. Load actual content (with delay to prevent UI freeze)
        def load_actual_tab():
            try:
                tabs = self.get_tabs_definition()
                for cat, tab_items in tabs.items():
                    if page_name in tab_items:
                        # Create actual frame
                        frame = ctk.CTkFrame(self.content_area)
                        frame.grid(row=0, column=0, sticky="nsew")
                        self.content_frames[page_name] = frame
                        
                        # Initialize content
                        instance = tab_items[page_name]["creation_func"](frame, self)
                        instance.pack(expand=True, fill="both")
                        self.tab_instances[page_name] = instance
                        
                        # Swap Skeleton
                        skeleton.stop()
                        loading_frame.destroy()
                        
                        if raise_frame:
                            frame.tkraise()
                            self._update_nav_button_color(page_name)
                        break
            except Exception as e:
                print(f"Error loading tab {page_name}: {e}")
                skeleton.stop()
                loading_frame.destroy()

        self.after(50, load_actual_tab)

    def _update_nav_button_color(self, page_name):
        """Highlights the active tab with high contrast in both modes."""
        for name, btn in self.nav_buttons.items():
            current_text = btn.cget("text")
            
            # Skip coloring for disabled/locked items to keep their warning colors
            if "⚠️" in current_text or "🔒" in current_text:
                continue 

            if name == page_name:
                # SELECTED STATE
                btn.configure(
                    fg_color=("#E3F2FD", "#374151"),   # Light: Pale Blue, Dark: Dark Grey (Visible!)
                    text_color=("#1565C0", "#60A5FA"), # Light: Deep Blue, Dark: Neon Blue
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    image=self.tab_icon_map.get(name)  # Ensure icon stays
                )
            else:
                # UNSELECTED STATE
                btn.configure(
                    fg_color="transparent",
                    text_color=("gray30", "gray80"),
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"),
                    image=self.tab_icon_map.get(name)
                )

    def _on_category_filter_change(self, selected_category: str):
        self.play_sound("select")
        save_config('last_selected_category', selected_category)
        self._filter_nav_menu(selected_category)

    def _filter_nav_menu(self, selected_category: str):
        # Unpack all
        for frame in self.category_frames.values():
            frame.pack_forget()
        
        # FIX: Removed self.update_idletasks() to prevent flickering/glitch
        
        # Repack selected
        if selected_category == "All Automations":
            for cat, frame in self.category_frames.items():
                frame.pack(fill="x", pady=8, padx=5) 
        else:
            if selected_category in self.category_frames:
                self.category_frames[selected_category].pack(fill="x", pady=5, padx=5)

    def show_history_window(self):
        """Displays the recent activity log in a popup."""
        win = ctk.CTkToplevel(self)
        win.title("Activity Log - Recent Tasks")
        win.geometry("700x500")
        
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (700 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (500 // 2)
        win.geometry(f"+{x}+{y}")

        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(win, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        ctk.CTkLabel(header, text="Recent Activity Log (Last 50 Items)", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Refresh", width=80, height=25, command=lambda: [win.destroy(), self.show_history_window()]).pack(side="right")

        # Text Area
        log_box = ctk.CTkTextbox(win, font=("Consolas", 12))
        log_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        logs = self.history_manager.get_recent_activity(50)
        
        if not logs:
            log_box.insert("0.0", "No recent activity found. Start working to see logs here!")
        else:
            for timestamp, type_, desc in logs:
                icon = "✅" if type_ == "SUCCESS" else "⚠️" if type_ == "WARNING" else "❌"
                line = f"{timestamp} | {icon} {desc}\n"
                log_box.insert("end", line)
                log_box.insert("end", "-"*80 + "\n")
        
        log_box.configure(state="disabled")

    # ============================================================================
    # 5. DATA HANDOFF METHODS (INTER-TAB COMMUNICATION)
    # ============================================================================

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

    def switch_to_mr_tracking_for_abps(self):
        self.workflows.switch_to_mr_tracking_for_abps()

    def switch_to_duplicate_mr_with_data(self, wc, p_name):
        self.workflows.switch_to_duplicate_mr_with_data(wc, p_name)

    def switch_to_zero_mr_tab_with_data(self, data_list):
        self.workflows.switch_to_zero_mr_tab_with_data(data_list)

    def send_wagelist_data_and_switch_tab(self, start, end):
        self.workflows.send_wagelist_data_and_switch_tab(start, end)

    # ============================================================================
    # 6. BROWSER & AUTOMATION MANAGER
    # ============================================================================

    def get_driver(self):
        driver = self.browser_manager.get_driver()
        if driver:
            self.driver = self.browser_manager.driver
            self.active_browser = self.browser_manager.active_browser
        return driver
    
    def launch_chrome_detached(self, target_urls=None):
        self.browser_manager.launch_chrome_detached(target_urls)
        
    def launch_edge_detached(self):
        self.browser_manager.launch_edge_detached()
        
    def launch_firefox_managed(self):
        self.browser_manager.launch_firefox_managed()

    def start_automation_thread(self, key, target, args=()):
        """
        Runs an automation task in a background thread with sleep prevention.
        Handles window minimization on start.
        """
        if self.automation_threads.get(key) and self.automation_threads[key].is_alive():
            self.play_sound("error")
            messagebox.showwarning("Busy", "Task running")
            return
        
        self.play_sound("start")
        self.history_manager.increment_usage(key)
        self.prevent_sleep()
        self.active_automations.add(key)
        self.stop_events[key] = threading.Event()

        # Auto Minimize
        if self.minimize_var.get() and self.driver:
            try:
                self.driver.minimize_window()
                self.show_toast("Running in Background (Minimized)", "info")

                # Mac Chrome Fix
                if config.OS_SYSTEM == "Darwin" and self.active_browser == "chrome":
                    try:
                        subprocess.run([
                            "osascript", "-e", 
                            'tell application "Google Chrome" to set minimized of windows to true'
                        ])
                    except Exception:
                        pass
            except Exception:
                pass

        def wrapper():
            try:
                target(*args)
            finally:
                self.after(0, self.on_automation_finished, key)
        
        t = threading.Thread(target=wrapper, daemon=True)
        self.automation_threads[key] = t
        t.start()

    def on_automation_finished(self, key):
        if key in self.active_automations: self.active_automations.remove(key)
        self.set_status("Finished")
        self.after(5000, lambda: self.set_status("Ready"))
        if not self.active_automations: self.allow_sleep()

    def _quick_login_automation(self):
        """Auto Login Logic: Checks browser state and credentials."""
        def _runner():
            # 1. Check Browser
            chrome_running = False
            try:
                with socket.create_connection(("127.0.0.1", 9222), timeout=0.2):
                    chrome_running = True
            except:
                pass

            if not chrome_running:
                login_url = "https://nregade4.nic.in/netnrega/Login.aspx?&level=HomePO&state_code=34"
                self.after(0, lambda: self.launch_chrome_detached(target_urls=[login_url]))
                time.sleep(4)

            # 2. Check Saved Credentials
            creds_path = self.get_data_path('user_location_pref.json')
            has_creds = False
            if os.path.exists(creds_path):
                try:
                    with open(creds_path, 'r') as f:
                        data = json.load(f)
                        if data.get("district") and data.get("block"):
                            has_creds = True
                except: pass

            # 3. Load Tab
            should_switch = not has_creds
            self.after(0, lambda: self.show_frame("Login Automation", raise_frame=should_switch))

            # 4. Trigger Automation
            def _trigger():
                if "Login Automation" in self.tab_instances:
                    self.tab_instances["Login Automation"].run_login_thread()
                else:
                    self.after(100, _trigger)
            
            self.after(500, _trigger)

        threading.Thread(target=_runner, daemon=True).start()

    # ============================================================================
    # 7. SERVER SYNC & UPDATES
    # ============================================================================

    def _ping_server_in_background(self):
        """Periodically checks connectivity to license server."""
        def ping_loop():
            while True: 
                is_connected = False
                try:
                    requests.get(config.LICENSE_SERVER_URL, timeout=5)
                    is_connected = True
                except requests.exceptions.RequestException:
                    is_connected = False
                
                try:
                    if self.winfo_exists():
                        self.after(0, self.set_server_status, is_connected)
                    else:
                        break 
                except:
                    break
                time.sleep(20)

        threading.Thread(target=ping_loop, daemon=True).start()

    def _fetch_app_config(self):
        """Fetches global configuration (Announcement + Features) from server."""
        def _worker():
            try:
                url = f"{config.LICENSE_SERVER_URL}/api/app-config"
                resp = requests.get(url, timeout=20)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    msg = data.get("global_announcement", "")
                    if msg:
                        self.after(0, lambda: self.announcement_label.update_text(msg))
                    
                    self.global_disabled_features = data.get("disabled_features", [])
                    
                    if (self.license_info.get('key_type') or '').lower() == 'trial':
                        self.trial_restricted_features = data.get("trial_restricted_features", [])
                    else:
                        self.trial_restricted_features = []
                        
                    self.after(0, self._apply_feature_flags)
                    
            except Exception as e:
                print(f"Config Fetch Error: {e}")
            finally:
                self.after(120000, self._fetch_app_config)
        
        threading.Thread(target=_worker, daemon=True).start()

    def _apply_feature_flags(self):
        """Applies visual locks or maintenance modes based on server config."""
        if not hasattr(self, 'nav_buttons'): return
        
        current_ver = parse_version(config.APP_VERSION)

        for name, btn in self.nav_buttons.items():
            # Reset
            current_text = btn.cget("text")
            clean_text = current_text.replace(" ⚠️", "").replace(" 🔒", "").replace(" (Update)", "").replace(" (Maintenance)", "")
            
            btn.configure(state="normal", fg_color="transparent", text=clean_text, command=lambda n=name: self.show_frame(n))

            # 1. Global Kill Switch
            disabled_data = None
            if isinstance(self.global_disabled_features, list):
                if name in self.global_disabled_features:
                    disabled_data = {"fix_version": None}
            elif isinstance(self.global_disabled_features, dict):
                disabled_data = self.global_disabled_features.get(name)

            if disabled_data:
                fix_version_str = disabled_data.get('fix_version')
                is_update_available = False
                
                if fix_version_str:
                    try:
                        if parse_version(fix_version_str) > current_ver:
                            is_update_available = True
                    except: pass

                if is_update_available:
                    btn.configure(
                        state="normal",
                        fg_color=("orange", "#D97706"), 
                        text=f"{clean_text} ⚠️ (Update)",
                        command=lambda n=name, v=fix_version_str: self.show_feature_update_alert(n, v)
                    )
                else:
                    btn.configure(
                        state="normal", 
                        fg_color=("red", "#991B1B"), 
                        text=f"{clean_text} ⚠️ (Maintenance)",
                        command=lambda n=name: self.show_feature_maintenance_alert(n)
                    )
            
            # 2. Trial Restriction
            elif name in self.trial_restricted_features:
                btn.configure(
                    state="normal",
                    fg_color=("gray95", "gray25"),
                    text=f"{clean_text} 🔒",
                    command=lambda n=name: self.show_trial_lock_alert(n)
                )

    def check_for_updates_background(self):
        self.services.check_for_updates_background()

    def show_update_prompt(self, version):
        self.play_sound("update")
        if messagebox.askyesno("Update", f"Version {version} available. View?"):
            self.show_frame("About"); self.tab_instances.get("About").tab_view.set("Updates")

    def download_and_install_update(self, url, version):
        self.services.download_and_install_update(url, version)

    def _apply_smart_update(self, zip_path):
        """
        Smart Update Logic (Windows & macOS):
        1. Extract ZIP to temp folder.
        2. Create a script (.bat for Win, .sh for Mac) to swap files.
        3. Run script and close app.
        """
        import zipfile
        import stat

        try:
            # 1. Temp folder setup
            extract_dir = os.path.join(self.get_data_path(), "update_temp")
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            os.makedirs(extract_dir)

            # 2. Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 3. Get Application Paths
            current_exe = sys.executable
            app_dir = os.path.dirname(current_exe)
            
            # Dev mode check
            if not getattr(sys, 'frozen', False):
                messagebox.showinfo("Dev Mode", "Update extracted to 'update_temp'. Cannot auto-restart in dev mode.")
                return

            self.play_sound("update")
            messagebox.showinfo("Update Ready", "Application will restart to apply changes.")

            # --- WINDOWS LOGIC ---
            if sys.platform == "win32":
                batch_script_path = os.path.join(self.get_data_path(), "updater.bat")
                script_content = f"""
@echo off
title Updating NREGA Bot...
echo Waiting for application to close...
timeout /t 2 /nobreak > NUL

echo Installing updates...
xcopy /s /y "{extract_dir}\\*" "{app_dir}\\"

echo Cleaning up...
rmdir /s /q "{extract_dir}"
del "{zip_path}"

echo Restarting Application...
start "" "{current_exe}"

echo Done.
del "%~f0" & exit
"""
                with open(batch_script_path, "w") as bat:
                    bat.write(script_content)
                os.startfile(batch_script_path)

            # --- MACOS LOGIC ---
            elif sys.platform == "darwin":
                shell_script_path = os.path.join(self.get_data_path(), "updater.sh")
                script_content = f"""#!/bin/bash
echo "Updating NREGA Bot..."
sleep 2

echo "Copying files..."
cp -R "{extract_dir}/"* "{app_dir}/"

echo "Fixing Permissions & Security..."
# 1. Remove Quarantine Attribute
xattr -cr "{app_dir}"
# 2. Ensure Executable Permission
chmod +x "{current_exe}"

echo "Cleaning up..."
rm -rf "{extract_dir}"
rm "{zip_path}"

echo "Restarting..."
"{current_exe}" &

rm "$0"
"""
                with open(shell_script_path, "w") as sh:
                    sh.write(script_content)

                # Make script executable
                st = os.stat(shell_script_path)
                os.chmod(shell_script_path, st.st_mode | stat.S_IEXEC)

                # Run Shell script
                subprocess.Popen(["/bin/bash", shell_script_path])

            # 4. Force Close App
            self.on_closing(force=True)
            sys.exit(0)

        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to apply smart update:\n{e}")

    # ============================================================================
    # 8. EVENTS & INTERACTIONS
    # ============================================================================

    def _on_window_focus(self, event=None):
        if self.is_licensed and not self.is_validating_license:
            self.after(500, lambda: threading.Thread(target=self._validate_in_background, daemon=True).start())

    def _on_global_click(self, event):
        """Global click listener for sound effects."""
        widget = event.widget
        while widget:
            try:
                if isinstance(widget, (ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkSwitch, ctk.CTkCheckBox)):
                    button_text = ""
                    if hasattr(widget, 'cget'):
                        try: button_text = widget.cget("text").lower()
                        except (AttributeError, tkinter.TclError): pass
                    if "stop" in button_text or "start automation" in button_text: return
                    self.play_sound("click")
                    return
                widget = widget.master
            except Exception: return

    def _on_sound_toggle_click(self):
        new_val = not self.sound_switch_var.get()
        self.sound_switch_var.set(new_val)
        save_config('sound_enabled', new_val)
        
        self._update_settings_btn_visuals(self.sound_btn, new_val)
        if new_val: self.play_sound("success")

    def _on_minimize_toggle_click(self):
        new_val = not self.minimize_var.get()
        self.minimize_var.set(new_val)
        
        self._update_settings_btn_visuals(self.minimize_btn, new_val)
        
        state = "Enabled" if new_val else "Disabled"
        self.show_toast(f"Auto-Minimize {state}", "info")

    def _cycle_theme(self):
        modes = ["System", "Light", "Dark"]
        try:
            current_idx = modes.index(self.current_theme_mode)
        except ValueError:
            current_idx = 0
            
        next_idx = (current_idx + 1) % len(modes)
        self.current_theme_mode = modes[next_idx]
        
        ctk.set_appearance_mode(self.current_theme_mode)
        save_config("theme_mode", self.current_theme_mode)
        
        self._update_theme_icon()
        self.play_sound("click")
        
        if hasattr(self, 'announcement_label'):
            self.announcement_label.update_colors()
            
        self.after(100, self.restyle_all_treeviews)

    def _update_theme_icon(self):
        icon_key = f"theme_{self.current_theme_mode.lower()}" 
        new_icon = self.icon_images.get(icon_key, self.icon_images.get("theme_system"))
        self.theme_btn.configure(image=new_icon)

    def _update_settings_btn_visuals(self, btn, is_active):
        if is_active:
            btn.configure(fg_color=("#C8E6C9", "#1B5E20")) 
        else:
            btn.configure(fg_color="transparent")

    def _update_header_welcome_message(self):
        if not self.header_welcome_prefix_label: return
        user_name, key_type = self.license_info.get('user_name'), self.license_info.get('key_type')
        if user_name:
            self.header_welcome_prefix_label.configure(text=f"v{config.APP_VERSION} | Welcome, ")
            self.header_welcome_name_label.configure(text=user_name)
            self.header_welcome_suffix_label.configure(text="!")
            if key_type != 'trial': self.header_welcome_name_label.configure(text_color=("gold4", "#FFD700"), font=ctk.CTkFont(size=13, weight="bold"))
            else: self.header_welcome_name_label.configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"], font=ctk.CTkFont(size=13, weight="normal"))
        else:
            self.header_welcome_prefix_label.configure(text=f"v{config.APP_VERSION} | Log in, then select a task.")
            self.header_welcome_name_label.configure(text=""); self.header_welcome_suffix_label.configure(text="")

    def _update_about_tab_info(self):
        self._update_header_welcome_message()
        about_tab = self.tab_instances.get("About")
        if about_tab:
            about_tab.update_subscription_details(self.license_info)
            info = self.update_info
            if info['status'] == 'available':
                about_tab.latest_version_label.configure(text=f"Latest Version: {info['version']}")
                about_tab.update_button.configure(text=f"Download & Install v{info['version']}", state="normal", command=lambda: about_tab.download_and_install_update(info['url'], info['version']))
                about_tab.show_new_version_changelog(info.get('changelog', []))
            elif info['status'] == 'updated':
                about_tab.latest_version_label.configure(text=f"Latest Version: {config.APP_VERSION}")
                about_tab.update_button.configure(text="You are up to date", state="disabled")
                about_tab.hide_new_version_changelog()
            else:
                about_tab.latest_version_label.configure(text=f"Latest Version: {info['status'].capitalize()}"); about_tab.update_button.configure(text="Check for Updates", state="normal")
                about_tab.hide_new_version_changelog()

    # ============================================================================
    # 9. HELPERS & UTILITIES
    # ============================================================================

    def get_data_path(self, filename): return get_data_path(filename)
    def get_user_downloads_path(self): return get_user_downloads_path()
    
    def open_folder(self, path):
        try:
            if os.path.exists(path):
                if sys.platform == "win32": os.startfile(path)
                else: subprocess.call(["open" if sys.platform == "darwin" else "xdg-open", path])
        except Exception as e: 
            self.play_sound("error")
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def open_web_file_manager(self):
        if self.license_info.get('key'): webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/authenticate-from-app/{self.license_info['key']}?next=files")
        else: self.play_sound("error"); messagebox.showerror("Error", "License key not found.")

    def save_demo_csv(self, file_type: str):
        try:
            src = resource_path(f"assets/demo_{file_type}.csv")
            if not os.path.exists(src): self.play_sound("error"); messagebox.showerror("Error", "Demo file not found"); return
            save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=f"{file_type}_data.csv")
            if save_path: shutil.copyfile(src, save_path); self.play_sound("success"); messagebox.showinfo("Success", f"Demo file saved to:\n{save_path}")
        except Exception as e: self.play_sound("error"); messagebox.showerror("Error", str(e))

    def play_sound(self, sound_name: str):
        self.sound_manager.play(sound_name)

    def show_toast(self, message, kind="success"):
        try:
            if hasattr(self, 'current_toast') and self.current_toast and self.current_toast.winfo_exists():
                self.current_toast.destroy()
            
            self.play_sound("complete" if kind == "success" else "error")
            self.current_toast = ToastNotification(self, message, kind)
        except Exception as e:
            print(f"Toast Error: {e}")

    def set_status(self, message, color=None):
        if self.status_label:
            message_lower = message.lower()
            final_color = color 
            should_animate = False
            if final_color is None:
                if any(x in message_lower for x in ["running", "starting", "navigating", "processing", "loading"]):
                    final_color = "#3B82F6"; should_animate = True
                elif "finished" in message_lower: final_color = "#E53E3E"
                elif "ready" in message_lower:
                    final_color = "#38A169"
                    if message == "Ready": self.play_sound("success")
                elif "error" in message_lower or "failed" in message_lower:
                    final_color = "#E53E3E"
                    if not "session expired" in message_lower: self.play_sound("error")
                else: final_color = "gray50"

            if should_animate and not self.is_animating:
                self.is_animating = True; self._animate_loading_icon()
            elif not should_animate: self.is_animating = False

            self.status_label.configure(text=f"Status: {message}", text_color=final_color)
            if not self.is_animating and self.loading_animation_label: self.loading_animation_label.configure(text="")

    def _animate_loading_icon(self, frame_index=0):
        if not self.is_animating:
            if self.loading_animation_label: self.loading_animation_label.configure(text="")
            return
        frames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
        if self.loading_animation_label: self.loading_animation_label.configure(text=frames[frame_index])
        self.after(80, self._animate_loading_icon, (frame_index + 1) % len(frames))

    def set_server_status(self, is_connected: bool):
        if self.server_status_indicator: self.server_status_indicator.configure(fg_color="green" if is_connected else "red")

    def prevent_sleep(self):
        self.services.prevent_sleep()

    def allow_sleep(self):
        self.services.allow_sleep()

    def bring_to_front(self):
        self.lift()

    def _get_work_area(self):
        if config.OS_SYSTEM == "Windows":
            try:
                SPI_GETWORKAREA = 0x0030
                rect = (ctypes.c_long * 4)()
                ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
                return (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
            except Exception: pass
        return (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())

    def _get_machine_id(self):
        return self.services.machine_id

    def show_trial_lock_alert(self, feature_name):
        self.play_sound("error")
        if messagebox.askyesno("Premium Feature", f"'{feature_name}' is a premium feature available in paid plans.\n\nUpgrade to a full license to unlock unlimited access.\n\nWould you like to upgrade now?"):
            self.show_purchase_window()

    def show_feature_update_alert(self, feature_name, fix_version):
        """Shows alert when a feature is disabled but a fix is available."""
        self.play_sound("error")
        if messagebox.askyesno(
            "Update Required", 
            f"The '{feature_name}' feature has been updated in version {fix_version}.\n\n"
            f"Please update NREGA Bot to the latest version to use this automation.\n\n"
            "Would you like to check for updates now?"
        ):
            self.show_frame("About")
            self.tab_instances.get("About").tab_view.set("Updates")
            self.check_for_updates_background()

    def show_feature_maintenance_alert(self, feature_name):
        """Shows alert when a feature is disabled for maintenance."""
        self.play_sound("error")
        messagebox.showwarning(
            "Under Maintenance", 
            f"The '{feature_name}' automation is currently down due to changes in the NREGA website.\n\n"
            "Our team is working on a fix. Please wait for a new update.\n"
            "We will notify you soon."
        )

    def log_message(self, log, msg, level="info"): 
        log.configure(state="normal")
        log.insert(tkinter.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        log.configure(state="disabled")
        log.see(tkinter.END)
    
    def clear_log(self, log): 
        log.configure(state="normal")
        log.delete("1.0", tkinter.END)
        log.configure(state="disabled")

    def update_history(self, key, val): self.history_manager.save_entry(key, val)
    def remove_history(self, key, val): self.history_manager.remove_entry(key, val)
    
    def on_theme_change(self, new_theme: str): ctk.set_appearance_mode(new_theme); self.after(100, self.restyle_all_treeviews)
    def restyle_all_treeviews(self):
        for tab in self.tab_instances.values():
            if hasattr(tab, 'style_treeview'):
                if hasattr(tab, 'results_tree'): tab.style_treeview(tab.results_tree)
                if hasattr(tab, 'files_tree'): tab.style_treeview(tab.files_tree)

    def _get_active_tab_context(self):
        """Scans active tab for context (Panchayat/Block/Agency names)."""
        try:
            if not hasattr(self, 'current_active_tab') or not self.current_active_tab:
                return ""

            tab = self.tab_instances.get(self.current_active_tab)
            if not tab: return ""

            found_values = []
            target_keywords = ['panchayat', 'gp', 'block', 'mandal', 'village', 'selected', 'agency']
            
            for var_name, var_obj in vars(tab).items():
                name_lower = var_name.lower()
                
                if any(k in name_lower for k in target_keywords):
                    val = ""
                    # Case 1: Tkinter Variable
                    if hasattr(var_obj, 'get'):
                        try: val = var_obj.get()
                        except: pass
                    # Case 2: Widget
                    elif hasattr(var_obj, 'winfo_exists') and hasattr(var_obj, 'get'):
                        try: val = var_obj.get()
                        except: pass
                        
                    if val and isinstance(val, str) and len(val) > 2:
                        if "select" not in val.lower() and "choose" not in val.lower():
                            found_values.append(val)

            if found_values:
                return " | ".join(sorted(list(set(found_values))))
            
            return ""
        except Exception as e:
            print(f"Context Error: {e}")
            return ""

    # ============================================================================
    # 10. CUSTOM MESSAGE BOX OVERRIDES
    # ============================================================================

    def _custom_showinfo(self, title, message, **options):
        active_tab = getattr(self, 'current_active_tab', 'System')
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
            return _original_showinfo(title, message, **options)

    def _custom_showwarning(self, title, message, **options):
        active_tab = getattr(self, 'current_active_tab', 'System')
        extra_info = self._get_active_tab_context()
        
        log_msg = f"[{active_tab}] {message}"
        if extra_info: log_msg += f" ({extra_info})"
            
        self.history_manager.log_activity("WARNING", log_msg)
        
        if len(message) < 50:
             self.show_toast(message, kind="warning")
             return "ok"
        
        self.play_sound("error")
        return _original_showwarning(title, message, **options)

    def _custom_showerror(self, title, message, **options):
        active_tab = getattr(self, 'current_active_tab', 'System')
        extra_info = self._get_active_tab_context()
        
        log_msg = f"[{active_tab}] Error: {message}"
        if extra_info: log_msg += f" ({extra_info})"

        self.history_manager.log_activity("ERROR", log_msg)

        self.play_sound("error")
        return _original_showerror(title, message, **options)


# ============================================================================
# MAIN EXECUTION ENTRY POINT
# ============================================================================

def run_application():
    """
    Called by loader.py. Handles Single Instance check via Sockets.
    """
    logging.basicConfig(level=logging.INFO)
    
    # Socket Logic for Single Instance
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try: 
        s.bind(("127.0.0.1", 60123))
    except:
        try: 
            s.connect(("127.0.0.1", 60123))
            s.sendall(b'focus')
            s.close()
        except: pass
        sys.exit(0)
    
    try:
        app = NregaBotApp()
        
        # Socket Listener Thread
        def listen():
            s.listen(1)
            while True:
                try:
                    c, a = s.accept()
                    d = c.recv(1024)
                    if d == b'focus': 
                        app.after(0, app.bring_to_front)
                    c.close()
                except (OSError, ValueError):
                    break
        threading.Thread(target=listen, daemon=True).start()
        
        # Start App
        app.mainloop()
        
    except Exception as e:
        messagebox.showerror("Fatal Error", str(e))
    finally: 
        s.close()

if __name__ == '__main__':
    run_application()