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
import gc
from datetime import datetime
from urllib.parse import urlencode

# --- Third Party UI & System ---
import tkinter
from tkinter import messagebox, filedialog, ttk
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
    ToastNotification, OnboardingGuide, ComingSoonTab, PerformanceMonitor
)
from browser_manager import BrowserManager
from services import ServiceManager
from tab_config import get_tabs_definition
from icon_manager import create_icon_manager
from sound_manager import SoundManager
from workflow_manager import WorkflowManager
from location_data import STATE_DISTRICT_MAP
from tabs.history_manager import HistoryManager
from tabs.macro_manager_tab import MacroManagerTab
from utils import (
    resource_path, get_data_path, get_user_downloads_path, 
    get_config, save_config
)

# Note: Heavy libraries (Selenium) are imported inside 
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
        self.http_session = requests.Session() # Optimized network session
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
        self.expiry_alert_message = None

        # --- GC Tuning: Reduce memory fragmentation for long-running GUI app ---
        gc.set_threshold(700, 10, 5)
        gc.freeze()

        # --- STARTUP SEQUENCE ---
        
        # 1. Show Splash Screen
        self.splash = self._create_splash_screen()
        self.splash.update() 

        # 2. Initialize Lazy Icon Manager (definitions only, no image loading yet)
        self.icon_images = create_icon_manager()
        # Preload essential icons (browser, settings, dock) into cache
        # so UI creation doesn't trigger on-demand disk I/O on main thread
        self.icon_images.preload_essential()

        # 3. Start Background Initialization (Heavy Tasks)
        threading.Thread(target=self._background_initialization, daemon=True).start()

        # 4. Set Cleanup Protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_splash_screen(self):
        """Creates a clean, modern splash screen with high readability on both themes."""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)
        w, h = 380, 260
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        x, y = (sw // 2) - (w // 2), (sh // 2) - (h // 2)
        splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        # Base window color blends seamlessly with outer frame (no border needed)
        splash.configure(fg_color=("#FFFFFF", "#2B2B2B"))

        # Outer frame - seamless card, no awkward border
        outer = ctk.CTkFrame(
            splash, fg_color=("#FFFFFF", "#2B2B2B"), corner_radius=16,
            border_width=0
        )
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=30, pady=22)

        try:
            logo = ctk.CTkImage(Image.open(resource_path("logo.png")), size=(64, 64))
            ctk.CTkLabel(inner, image=logo, text="").pack(pady=(5, 10))
        except Exception:
            pass

        # App Name - Large, bold, high contrast on both themes
        ctk.CTkLabel(
            inner, text=f"{config.APP_NAME}",
            font=ctk.CTkFont(family="Helvetica Neue", size=24, weight="bold"),
            text_color=("#111827", "#F3F4F6")
        ).pack()

        # Portal tag - bright blue for both themes with enough contrast
        ctk.CTkLabel(
            inner, text="VB-G-RAM-G Portal Support",
            font=ctk.CTkFont(family="Helvetica Neue", size=12, weight="bold"),
            text_color=("#2563EB", "#60A5FA")
        ).pack(pady=(2, 18))

        # Animated dots - medium gray, crisp & readable
        self._splash_dots = 0
        splash.dots_label = ctk.CTkLabel(
            inner, text="Initializing",
            font=ctk.CTkFont(family="Helvetica Neue", size=12),
            text_color=("#6B7280", "#9CA3AF")
        )
        splash.dots_label.pack(pady=(0, 0))

        # Animate dots
        def _splash_animate():
            try:
                if splash.winfo_exists():
                    self._splash_dots += 1
                    d = "." * (self._splash_dots % 4)
                    splash.dots_label.configure(text=f"Loading{d}")
                    splash.after(120, _splash_animate)
            except Exception:
                pass
        _splash_animate()

        # Version - Larger and bold for better visibility
        ctk.CTkLabel(
            inner, text=f"v{config.APP_VERSION}",
            font=ctk.CTkFont(family="Helvetica Neue", size=13, weight="bold"),
            text_color=("#6B7280", "#9CA3AF")
        ).pack(side="bottom", pady=(0, 5))

        splash.lift()
        splash.attributes("-topmost", True)
        return splash

    def _background_initialization(self):
        """Loads heavy libraries and assets in background to keep UI responsive."""
        # 1. Apply Patches to Messagebox
        messagebox.showinfo = self._custom_showinfo
        messagebox.showwarning = self._custom_showwarning
        messagebox.showerror = self._custom_showerror

        # 2. Trigger UI Setup on Main Thread
        self.after(10, self._finish_startup)

    def _finish_startup(self):
        """Called on main thread after background loading is done.
        Progressively renders UI sections so low-end devices see smooth,
        staged appearance instead of a long freeze followed by partial widgets.
        """
        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<FocusIn>", self._on_window_focus)

        self.style_treeview()
        
        # Build Grid Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Stage 1: Header ---
        self._create_header()
        self.update_idletasks()  # Let tkinter render header before moving on

        # --- Stage 2: Footer ---
        self._create_footer()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_idletasks()  # Render footer before heavy layout
        
        # Mac OS Specific Delay fix
        if config.OS_SYSTEM == "Darwin":
            self.update() 
            time.sleep(0.1)

        # --- Stage 3: Main Layout (sidebar + content area) ---
        self._create_main_layout(for_activation=True)
        self._layout_ready = True  # Signal that critical UI structure is built
        self.update_idletasks()

        self.set_status("Initializing...")

        # License Check Flow
        self.perform_license_check_flow()

        # Transition Splash — Smart wait:
        # Minimum 600ms to avoid flash on fast devices, but also waits for
        # _layout_ready in case device is slow and UI isn't built yet.
        self.after(600, self._check_splash_ready)

    def _check_splash_ready(self, retries=0):
        """Waits for both minimum time AND layout readiness before fading splash.
        On low-end devices _layout_ready may not be True by the 600ms mark
        because widget creation takes longer — this loop keeps checking.
        
        Args:
            retries: Internal counter to prevent infinite loop (~5s max wait).
        """
        if getattr(self, '_layout_ready', False) and self.splash:
            self._transition_from_splash()
        elif self.splash and retries < 50:
            # Keep checking every 100ms (50 retries = ~5s total safety net)
            # After that, force transition regardless of layout state
            self.after(100, lambda: self._check_splash_ready(retries + 1))
        elif self.splash:
            # Safety net: force transition after ~5s even if layout isn't ready
            self._transition_from_splash()
        # If splash is already gone (e.g. error case), do nothing

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
                    self.after(30, lambda: self._fade_out_splash(splash, step + 1))
                else:
                    self._fade_in_main_window()
            except Exception:
                self._fade_in_main_window()
        else:
            if splash.winfo_exists():
                splash.destroy()
            self.splash = None
            self.after(0, self._fade_in_main_window)

    def style_treeview(self, treeview_widget=None):
        style = ttk.Style()
        style.theme_use("clam")

        # 1. Theme Detection
        mode = ctk.get_appearance_mode()

        if mode == "Dark":
            bg_color = "#2b2b2b"
            text_color = "#e5e7eb"
            row_hover = "#3f3f46"
            selected_bg = "#3B82F6"
            header_bg = "#1f2937"
            header_fg = "#ffffff"
            header_hover = "#374151"
        else:
            bg_color = "#ffffff"
            text_color = "#374151"
            row_hover = "#f3f4f6"
            selected_bg = "#3B82F6"
            header_bg = "#f9fafb"
            header_fg = "#111827"
            header_hover = "#e5e7eb"

        style.configure("Treeview",
                        background=bg_color,
                        foreground=text_color,
                        fieldbackground=bg_color,
                        rowheight=35,
                        font=("Segoe UI", 11),
                        borderwidth=0)

        style.map("Treeview",
                  background=[('selected', selected_bg), ('active', row_hover)],
                  foreground=[('selected', 'white'), ('active', text_color)])

        style.configure("Treeview.Heading",
                        background=header_bg,
                        foreground=header_fg,
                        relief="flat",
                        font=("Segoe UI", 12, "bold"))

        style.map("Treeview.Heading",
                  background=[('active', header_hover)])

        if treeview_widget:
            treeview_widget.configure(style="Treeview")

    def _fade_in_main_window(self):
        """Positions and shows the main application window fully rendered.
        
        On low-end devices tkinter's deiconify() can show the window before
        all widgets are painted, causing a "part by part" appearance.
        
        Fix: show at alpha=0 (invisible), force a full paint cycle with
        self.update(), then set alpha=1. The user sees the COMPLETE window
        in one frame — no progressive rendering.
        """
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

        # Step 1: Make visible but fully transparent
        self.attributes("-alpha", 0.0)
        self.deiconify()

        # Step 2: Force tkinter to paint everything NOW while still invisible
        # Multiple passes (3x) ensure layout calculation AND pixel composition
        # complete before the window becomes visible — critical on low-end GPUs
        # that may skip composition for fully transparent windows.
        for _ in range(3):
            self.update()
            self.update_idletasks()

        # Step 3: Now show the fully-rendered window (all widgets painted in one frame)
        self.attributes("-alpha", 1.0)
        self.lift()
        self.focus_force()

        if getattr(self, 'expiry_alert_message', None):
            def _show_delayed():
                self.play_sound("error")
                self.show_toast(self.expiry_alert_message, kind="warning", duration=6000)
                self.expiry_alert_message = None
            
            self.after(1500, _show_delayed)

    def run_onboarding_if_needed(self):
        """Runs the onboarding tour for first-time users."""
        flag_path = get_data_path('.first_run_complete')
        if not os.path.exists(flag_path):
            OnboardingGuide(self)
            try:
                with open(flag_path, 'w') as f: f.write(datetime.now().isoformat())
            except Exception as e: print(f"Could not write first run flag: {e}")

    def on_closing(self, force=False):
        """Handles application shutdown gracefully and cleans up browsers."""
        if force or messagebox.askokcancel("Quit", "Quit application?", parent=self):
            # Stop performance monitor updates
            try:
                if hasattr(self, 'performance_monitor'):
                    self.performance_monitor.stop()
            except: pass
            
            try:
                self.play_sound("shutdown")
                self.attributes("-alpha", 0.0) # Hide window immediately
            except: pass
            
            # Force garbage collection before exit
            gc.collect()
            
            # Cleanup zombie browser process
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.driver.quit()
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
            self.global_disabled_features = self.license_info.get('global_disabled_features', [])
            key_type = str(self.license_info.get('key_type', '')).lower()
            
            if key_type == 'trial':
                if 'trial_restricted_features' in self.license_info:
                    self.trial_restricted_features = self.license_info['trial_restricted_features']
                else:
                    self.trial_restricted_features = [
                        "Sarkar Aapke Dwar", "SAD Update Status", "FTO Generation", 
                        "MR Gen", "MR Fill", "MR Payment", "Gen Wagelist", 
                        "Send Wagelist", "Demand", "Allocation", "Work Allocation",
                        "eMB Entry", "eMB Verify", "WC Gen", "IF Editor"
                    ]
            else:
                self.trial_restricted_features = []
                
            self._apply_feature_flags()
            
        except Exception as e:
            print(f"Error applying local restrictions: {e}")
        
        is_expiring = self.check_expiry_and_notify()
        self._preload_and_update_about_tab()
        
        # Using unified sync function
        self._ping_server_in_background()
        
        # Show Home dashboard by default instead of the first automation tab
        try:
            self.show_frame("Home" if not is_expiring else "About")
        except Exception:
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
                                resp = self.http_session.post(
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
                resp = self.http_session.post(f"{config.LICENSE_SERVER_URL}/api/send-otp", json={"identifier": email_val}, timeout=10)
                if resp.status_code == 200:
                    messagebox.showinfo("OTP Sent", "Check your email for OTP", parent=win)
                else:
                    try:
                        reason = resp.json().get("reason", "Failed")
                    except Exception:
                        reason = f"Server returned status {resp.status_code}"
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
                    resp = self.http_session.post(
                        f"{config.LICENSE_SERVER_URL}/api/login-for-activation", 
                        json={
                            "email": input_val, 
                            "machine_id": self.machine_id, 
                            "otp": otp_val,
                            "app_version": config.APP_VERSION 
                        }, 
                        timeout=15
                    )
                    try:
                        data = resp.json()
                    except Exception:
                        raise Exception(f"Server returned an unexpected response (status {resp.status_code}). Please try again.")
                    
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
            
            else: 
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
                resp = self.http_session.post(f"{config.LICENSE_SERVER_URL}/api/send-otp", json={"identifier": email_val}, timeout=10)
                if resp.status_code == 200:
                    messagebox.showinfo("OTP Sent", "Check your email for OTP", parent=win)
                else:
                    try:
                        reason = resp.json().get("reason", "Failed")
                    except Exception:
                        reason = f"Server returned status {resp.status_code}"
                    messagebox.showerror("Error", reason, parent=win)
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
                resp = self.http_session.post(f"{config.LICENSE_SERVER_URL}/api/request-trial", json=data, timeout=15)
                try:
                    res = resp.json()
                except Exception:
                    raise Exception(f"Server returned an unexpected response (status {resp.status_code}). Please try again.")
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
                self.expiry_alert_message = f"License expires in {days} days."
                self.open_on_about_tab = True
                return True
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
        header = ctk.CTkFrame(self, corner_radius=15, fg_color=("white", "#1D1E1E")) 
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        header.grid_columnconfigure(1, weight=1)

        def add_status_hover(btn, message):
            def on_enter(e):
                if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                    self.status_label.configure(text=message, text_color=("#3B82F6", "#60A5FA"))
            def on_leave(e):
                if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                    self.status_label.configure(text="Ready", text_color="gray60")
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

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

        announcement_frame = ctk.CTkFrame(header, fg_color="transparent", height=30)
        announcement_frame.grid(row=0, column=1, sticky="ew", padx=20)
        announcement_frame.grid_propagate(False) 

        self.announcement_label = MarqueeLabel(announcement_frame, text="Connecting to server...", width=300)
        self.announcement_label.pack(fill="both", expand=True, pady=5)
        
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.grid(row=0, column=2, sticky="e", padx=15, pady=8)

        self.extractor_btn = ctk.CTkButton(
            controls_frame, text="", image=self.icon_images.get("extractor_icon"), 
            width=35, height=35, corner_radius=8,
            fg_color=("gray95", "gray25"), hover_color=("gray85", "gray35"),
            command=lambda: self.show_frame("Workcode Extractor")
        )
        self.extractor_btn.pack(side="left", padx=(0, 10))
        add_status_hover(self.extractor_btn, "Open Workcode Extractor")

        self.quick_login_btn = ctk.CTkButton(
            controls_frame, text="", image=self.icon_images.get("emoji_login_automation"), 
            width=35, height=35, corner_radius=8,
            fg_color=("gray95", "gray25"), hover_color=("gray85", "gray35"),
            command=self._quick_login_automation
        )
        self.quick_login_btn.pack(side="left", padx=(0, 10))
        add_status_hover(self.quick_login_btn, "Auto Login to NREGA")

        ctk.CTkFrame(controls_frame, width=2, height=20, fg_color=("gray90", "gray30")).pack(side="left", padx=(0, 10))

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

        ctk.CTkFrame(controls_frame, width=2, height=20, fg_color=("gray90", "gray30")).pack(side="left", padx=(0, 10))

        settings_group = ctk.CTkFrame(controls_frame, fg_color=("gray95", "gray25"), corner_radius=20)
        settings_group.pack(side="left")

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

        self.sound_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("sound_on"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_sound_toggle_click
        )
        self.sound_btn.pack(side="left", padx=2, pady=4)
        add_status_hover(self.sound_btn, "Toggle Sound Effects")
        self._update_settings_btn_visuals(self.sound_btn, self.sound_switch_var.get())

        self.minimize_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("minimize"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_minimize_toggle_click
        )
        self.minimize_btn.pack(side="left", padx=(2, 5), pady=4)
        add_status_hover(self.minimize_btn, "Auto-Minimize on Start")
        self._update_settings_btn_visuals(self.minimize_btn, self.minimize_var.get())
        
        self.theme_combo = ctk.CTkOptionMenu(self, width=0, height=0)

    def _create_main_layout(self, for_activation=False):
        if hasattr(self, 'main_layout_frame') and self.main_layout_frame.winfo_exists():
            self.main_layout_frame.destroy()
            self.update_idletasks() 

        self.main_layout_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_layout_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 10))
        self.main_layout_frame.grid_rowconfigure(0, weight=1)
        self.main_layout_frame.grid_columnconfigure(1, weight=1)
        
        self.sidebar_container = ctk.CTkFrame(self.main_layout_frame, width=220, corner_radius=0, fg_color="transparent")
        self.sidebar_container.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.sidebar_container.grid_rowconfigure(1, weight=1)
        self.sidebar_container.grid_columnconfigure(0, weight=1)

        self.sidebar_header = ctk.CTkFrame(self.sidebar_container, fg_color="transparent")
        self.sidebar_header.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))

        self.nav_scroll_frame = ctk.CTkScrollableFrame(
            self.sidebar_container, 
            label_text="", 
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=("gray80", "gray30"),
            scrollbar_button_hover_color=("gray70", "gray20")
        )
        self.nav_scroll_frame.grid(row=1, column=0, sticky="nsew")
        
        # Performance Monitor at bottom of sidebar
        self.performance_monitor = PerformanceMonitor(self.sidebar_container, self)
        self.performance_monitor.grid(row=2, column=0, sticky="ew", padx=2, pady=(4, 2))

        self._create_nav_buttons(self.sidebar_header, self.nav_scroll_frame)
        
        self.content_area = ctk.CTkFrame(self.main_layout_frame)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)
        
        self._create_content_frames()
        
        if for_activation: 
            self._lock_app_to_about_tab()

    def _create_nav_buttons(self, header_parent, content_parent):
        self.nav_buttons.clear()
        self.button_to_category_frame.clear()
        self.category_frames.clear()
        self.tab_icon_map = {} 

        for widget in header_parent.winfo_children(): widget.destroy()

        # --- Pinned Home button (always visible, above everything) ---
        # Load home icon directly to avoid lazy-manager caching issues
        _home_icon = None
        try:
            _home_icon = ctk.CTkImage(Image.open(resource_path("assets/icons/home.png")), size=(18, 18))
        except Exception:
            pass
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
        self.nav_buttons["Home"] = self.home_nav_btn
        # Keep icon reference so _update_nav_button_color doesn't wipe it
        self.tab_icon_map["Home"] = _home_icon

        # Thin separator
        ctk.CTkFrame(header_parent, height=1, fg_color=("gray85", "gray35")).pack(fill="x", padx=15, pady=(2, 5))

        # --- Category Filter (without Dashboard) — clean, modern look ---
        all_cats = list(self.get_tabs_definition().keys())
        filtered_cats = [c for c in all_cats if c != "Dashboard"]
        categories = ["All Automations"] + filtered_cats
        # Guard: if saved category no longer exists (e.g. old "Dashboard"), reset
        if self.last_selected_category not in categories:
            self.last_selected_category = "All Automations"
        
        self.category_filter_menu = ctk.CTkOptionMenu(
            header_parent, 
            values=categories, 
            command=self._on_category_filter_change,
            height=26, 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="normal"),
            fg_color=("#F3F4F6", "#333333"),
            button_color=("#E5E7EB", "#4B5563"),
            button_hover_color=("#D1D5DB", "#6B7280"),
            text_color=("#374151", "#D1D5DB"),
            dropdown_fg_color=("#FFFFFF", "#2B2B2B"),
            dropdown_text_color=("#374151", "#D1D5DB"),
            dropdown_hover_color=("#F3F4F6", "#374151"),
            anchor="w",
            corner_radius=8
        )
        self.category_filter_menu.set(self.last_selected_category)
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
                    font=ctk.CTkFont(family="Segoe UI", size=12, weight="normal"), 
                    height=32,           
                    corner_radius=6,    
                    fg_color="transparent", 
                    text_color=("gray30", "gray80"), 
                    hover_color=("gray90", "gray25"),
                    border_spacing=8     
                )
                btn.pack(fill="x", padx=5, pady=1) 
                
                self.nav_buttons[name] = btn
                self.button_to_category_frame[name] = cat_frame

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
        footer = ctk.CTkFrame(self, height=50, corner_radius=25, fg_color=("white", "#2B2B2B"))
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(6, weight=1)

        status_frame = ctk.CTkFrame(footer, fg_color="transparent")
        status_frame.pack(side="left", padx=20, fill="y")
        
        ctk.CTkLabel(
            status_frame, 
            text="© 2025 NREGA Bot", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            text_color=("gray50", "gray60")
        ).pack(side="left", padx=(0, 15))

        ctk.CTkFrame(status_frame, width=2, height=14, fg_color=("gray80", "gray40")).pack(side="left", padx=(0, 10))
        
        self.loading_animation_label = ctk.CTkLabel(status_frame, text="", width=20, font=ctk.CTkFont(size=14))
        self.loading_animation_label.pack(side="left")
        
        self.status_label = ctk.CTkLabel(status_frame, text="Ready", text_color="gray60", font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=(5, 0))

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

        ctk.CTkFrame(dock_frame, width=2, height=20, fg_color=("gray80", "gray40")).pack(side="left", padx=10)

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
        return get_tabs_definition(self)

    def _create_content_frames(self):
        self.content_frames.clear()
        self.tab_instances.clear()
        self.show_frame("About", raise_frame=False)
    
    def show_frame(self, page_name, raise_frame=True):
        self.current_active_tab = page_name
        
        if page_name in self.tab_instances:
            if raise_frame:
                self.content_frames[page_name].tkraise()
                self._update_nav_button_color(page_name)
            # Track usage and refresh Home page's Most Used when navigating back
            self._track_tab_usage(page_name)
            if page_name == "Home":
                # Brief delay so the frame renders before the widget rebuild
                self.after(80, self._refresh_home_most_used)
            return

        loading_frame = ctk.CTkFrame(self.content_area)
        loading_frame.grid(row=0, column=0, sticky="nsew")
        skeleton = SkeletonLoader(loading_frame, rows=10)
        loading_frame.tkraise()
        self.update_idletasks()
        
        def load_actual_tab():
            try:
                tabs = self.get_tabs_definition()
                for cat, tab_items in tabs.items():
                    if page_name in tab_items:
                        frame = ctk.CTkFrame(self.content_area)
                        frame.grid(row=0, column=0, sticky="nsew")
                        self.content_frames[page_name] = frame
                        
                        instance = tab_items[page_name]["creation_func"](frame, self)
                        instance.pack(expand=True, fill="both")
                        self.tab_instances[page_name] = instance
                        
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
                print(f"Error loading tab {page_name}: {e}")
                skeleton.stop()
                loading_frame.destroy()

        self.after(1, load_actual_tab)

    def _refresh_home_most_used(self):
        """Refresh the Home tab's Most Used section if the tab is loaded."""
        home = self.tab_instances.get("Home")
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
        for name, btn in self.nav_buttons.items():
            current_text = btn.cget("text")
            
            if "⚠️" in current_text or "🔒" in current_text:
                continue

            btn_image = self.tab_icon_map.get(name)

            if name == page_name:
                btn.configure(
                    fg_color=("#E3F2FD", "#374151"),  
                    text_color=("#1565C0", "#60A5FA"), 
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    image=btn_image
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("gray30", "gray80"),
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"),
                    image=btn_image
                )


    def _on_category_filter_change(self, selected_category: str):
        self.play_sound("select")
        save_config('last_selected_category', selected_category)
        self._filter_nav_menu(selected_category)

    def _filter_nav_menu(self, selected_category: str):
        if selected_category == "All Automations":
            for cat, frame in self.category_frames.items():
                if frame.winfo_exists() and frame.winfo_manager() != "pack":
                    frame.pack(fill="x", pady=5, padx=2)
        else:
            for cat, frame in self.category_frames.items():
                if not frame.winfo_exists():
                    continue
                if cat == selected_category:
                    if frame.winfo_manager() != "pack":
                        frame.pack(fill="x", pady=5, padx=2)
                else:
                    if frame.winfo_manager() == "pack":
                        frame.pack_forget()
        
        self.nav_scroll_frame.update_idletasks()



    def show_history_window(self):
        """Modern Activity Log window with stats, search, and filtered treeview."""
        # --- FIX: Single instance guard ---
        if hasattr(self, '_history_window') and self._history_window and self._history_window.winfo_exists():
            self._history_window.lift()
            self._history_window.focus_force()
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
            except:
                pass

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (900 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (650 // 2)
        win.geometry(f"+{x}+{y}")

        # --- FIX: Track this window globally ---
        self._history_window = win
        def on_close():
            self._history_window = None
            try:
                win.destroy()
            except:
                pass
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
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text File", "*.txt"), ("CSV File", "*.csv")],
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

    def switch_to_mr_tracking_for_abps(self, location_data=None):
        self.workflows.switch_to_mr_tracking_for_abps(location_data)

    def switch_to_duplicate_mr_with_data(self, wc, p_name):
        self.workflows.switch_to_duplicate_mr_with_data(wc, p_name)

    def switch_to_zero_mr_tab_with_data(self, data_list):
        self.workflows.switch_to_zero_mr_tab_with_data(data_list)

    def send_wagelist_data_and_switch_tab(self, start, end, auto_start=False):
        self.workflows.send_wagelist_data_and_switch_tab(start, end, auto_start=auto_start)

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
        if self.automation_threads.get(key) and self.automation_threads[key].is_alive():
            self.play_sound("error")
            messagebox.showwarning("Busy", "Task running")
            return
        
        self.play_sound("start")
        self.history_manager.increment_usage(key)
        self.prevent_sleep()
        self.active_automations.add(key)
        self.stop_events[key] = threading.Event()

        if self.minimize_var.get() and self.driver:
            try:
                self.driver.minimize_window()
                self.show_toast("Running in Background (Minimized)", "info")
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

            creds_path = self.get_data_path('user_location_pref.json')
            has_creds = False
            if os.path.exists(creds_path):
                try:
                    with open(creds_path, 'r') as f:
                        data = json.load(f)
                        if data.get("district") and data.get("block"):
                            has_creds = True
                except: pass

            should_switch = not has_creds
            self.after(0, lambda: self.show_frame("Login Automation", raise_frame=should_switch))

            def _trigger(retries=0):
                if "Login Automation" in self.tab_instances:
                    self.tab_instances["Login Automation"].run_login_thread()
                elif retries < 50: # Optimised: max retry limits to avoid infinite loop
                    self.after(100, lambda: _trigger(retries + 1))
                else:
                    print("Timeout: Login Automation tab failed to load.")
            
            self.after(500, lambda: _trigger(0))

        threading.Thread(target=_runner, daemon=True).start()

    # ============================================================================
    # 7. SERVER SYNC & UPDATES
    # ============================================================================

    def _ping_server_in_background(self):
        """Optimized unified background sync using requests.Session()"""
        def sync_worker():
            ping_counter = 0
            while True:
                # 1. Ping Server
                try:
                    self.http_session.get(config.LICENSE_SERVER_URL, timeout=5)
                    if self.winfo_exists():
                        self.after(0, self.set_server_status, True)
                except requests.exceptions.RequestException:
                    if self.winfo_exists():
                        self.after(0, self.set_server_status, False)

                # 2. Fetch App Config (Every 120s -> 6 loops of 20s)
                # Note: ping_counter starts at 0, so 0%6==0 fetches config on the VERY FIRST run!
                if ping_counter % 6 == 0:
                    try:
                        url = f"{config.LICENSE_SERVER_URL}/api/app-config"
                        resp = self.http_session.get(url, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            msg = data.get("global_announcement", "")
                            if self.winfo_exists():
                                # Agar admin ne koi message nahi diya hai, to default welcome message dikhao
                                final_msg = msg if msg else "Welcome to NREGA Bot! Ready to automate."
                                self.after(0, lambda: self.announcement_label.update_text(final_msg))
                            
                            self.global_disabled_features = data.get("disabled_features", [])
                            if (self.license_info.get('key_type') or '').lower() == 'trial':
                                self.trial_restricted_features = data.get("trial_restricted_features", [])
                            else:
                                self.trial_restricted_features = []
                            
                            if self.winfo_exists():
                                self.after(0, self._apply_feature_flags)
                    except Exception as e:
                        print(f"Config Fetch Error: {e}")
                    ping_counter = 0

                ping_counter += 1
                time.sleep(20)

        threading.Thread(target=sync_worker, daemon=True).start()

    def _fetch_app_config(self):
        # Deprecated: Now merged into _ping_server_in_background sync_worker
        pass

    def _apply_feature_flags(self):
        if not hasattr(self, 'nav_buttons'): return
        
        current_ver = parse_version(config.APP_VERSION)

        for name, btn in self.nav_buttons.items():
            current_text = btn.cget("text")
            clean_text = current_text.replace(" ⚠️", "").replace(" 🔒", "").replace(" (Update)", "").replace(" (Maintenance)", "")
            
            new_state = "normal"
            new_fg = "transparent"
            new_text = clean_text
            new_cmd = lambda n=name: self.show_frame(n)

            disabled_data = None
            if isinstance(self.global_disabled_features, list):
                if name in self.global_disabled_features: disabled_data = {"fix_version": None}
            elif isinstance(self.global_disabled_features, dict):
                disabled_data = self.global_disabled_features.get(name)

            if disabled_data:
                fix_version_str = disabled_data.get('fix_version')
                is_update_available = False
                try:
                    if fix_version_str and parse_version(fix_version_str) > current_ver:
                        is_update_available = True
                except: pass

                if is_update_available:
                    new_fg = ("orange", "#D97706")
                    new_text = f"{clean_text} ⚠️ (Update)"
                    new_cmd = lambda n=name, v=fix_version_str: self.show_feature_update_alert(n, v)
                else:
                    new_fg = ("red", "#991B1B")
                    new_text = f"{clean_text} ⚠️ (Maintenance)"
                    new_cmd = lambda n=name: self.show_feature_maintenance_alert(n)
            
            elif name in self.trial_restricted_features:
                new_fg = ("gray95", "gray25")
                new_text = f"{clean_text} 🔒"
                new_cmd = lambda n=name: self.show_trial_lock_alert(n)

            if btn.cget("text") != new_text or btn.cget("fg_color") != new_fg:
                btn.configure(state=new_state, fg_color=new_fg, text=new_text, command=new_cmd)

    def check_for_updates_background(self):
        self.services.check_for_updates_background()

    def show_update_prompt(self, version):
        self.play_sound("update")
        if messagebox.askyesno("Update", f"Version {version} available. View?"):
            self.show_frame("About"); self.tab_instances.get("About").tab_view.set("Updates")

    def download_and_install_update(self, url, version):
        self.services.download_and_install_update(url, version)

    def _apply_smart_update(self, zip_path):
        import shutil
        import zipfile
        
        if sys.platform == "darwin":
            try:
                from appdirs import user_data_dir
                
                local_dir = user_data_dir("NREGABot", "PoddarSolutions")
                core_zip_path = os.path.join(local_dir, "core.zip")
                version_file = os.path.join(local_dir, "core_version.json")
                
                self.play_sound("update")
                
                if os.path.exists(core_zip_path):
                    os.remove(core_zip_path)
                
                shutil.copy2(zip_path, core_zip_path)
                
                try:
                    new_ver = self.update_info.get('version', '0.0.0')
                    with open(version_file, 'w') as f:
                        json.dump({"version": new_ver}, f)
                except: pass

                try: os.remove(zip_path)
                except: pass
                
                messagebox.showinfo("Update Ready", "Update applied successfully.\nThe application will now restart.")
                
                self.on_closing(force=True)
                subprocess.Popen([sys.executable])
                sys.exit(0)

            except Exception as e:
                messagebox.showerror("Update Error", f"Failed to apply update:\n{e}")
                return

        extract_dir = os.path.join(self.get_data_path(), "update_temp")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            current_exe = sys.executable
            app_dir = os.path.dirname(current_exe)
            
            if not getattr(sys, 'frozen', False):
                messagebox.showinfo("Dev Mode", "Update extracted to 'update_temp'. Cannot auto-restart in dev mode.")
                return

            self.play_sound("update")
            messagebox.showinfo("Update Ready", "Application will restart to apply changes.")

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
            
            self.on_closing(force=True)
            sys.exit(0)

        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to apply smart update:\n{e}")

    # ============================================================================
    # 8. EVENTS & INTERACTIONS
    # ============================================================================

    def _on_window_focus(self, event=None):
        if not self.is_licensed:
            return

        if self.is_validating_license:
            return

        if hasattr(self, '_focus_validation_timer') and self._focus_validation_timer:
            try:
                self.after_cancel(self._focus_validation_timer)
            except: pass
        
        self._focus_validation_timer = self.after(2000, self._start_validation_thread)

    def _start_validation_thread(self):
        if not self.is_validating_license:
            threading.Thread(target=self._validate_in_background, daemon=True).start()

    def _on_global_click(self, event):
        """Global click listener optimized to prevent CPU usage loop lags."""
        try:
            widget = event.widget
            w_class = widget.winfo_class().lower()
            w_name = str(widget).lower()
            
            # Fast exit
            if "scrollbar" in w_class or "trough" in w_name or "canvas" in w_class or "slider" in w_class:
                return
                
            depth = 0
            while widget and depth < 4:
                if isinstance(widget, (ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkSwitch, ctk.CTkCheckBox, ctk.CTkRadioButton)):
                    btn_text = ""
                    try: 
                        btn_text = widget.cget("text").lower()
                    except: pass
                    
                    if "stop" in btn_text or "start automation" in btn_text: return
                    self.play_sound("click")
                    return
                widget = widget.master
                depth += 1
        except Exception:
            pass

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

    def show_toast(self, message, kind="success", duration=3000):
        try:
            if not self.winfo_exists():
                return

            if hasattr(self, 'current_toast') and self.current_toast:
                try:
                    if self.current_toast.winfo_exists():
                        self.current_toast.destroy()
                except: pass
            
            self.play_sound("complete" if kind == "success" else "error")
            
            try:
                self.current_toast = ToastNotification(self, message, kind, duration=duration)
            except Exception:
                pass 

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
        # Optimized animation speed
        self.after(200, self._animate_loading_icon, (frame_index + 1) % len(frames))

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
        self.play_sound("error")
        messagebox.showwarning(
            "Under Maintenance", 
            f"The '{feature_name}' automation is currently down due to changes in the VB-G-RAM-G portal.\n\n"
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
                    if hasattr(var_obj, 'get'):
                        try: val = var_obj.get()
                        except: pass
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
    logging.basicConfig(level=logging.INFO)
    
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
        
        app.mainloop()
        
    except Exception as e:
        messagebox.showerror("Fatal Error", str(e))
    finally: 
        s.close()

if __name__ == '__main__':
    run_application()