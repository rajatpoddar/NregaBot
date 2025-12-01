# main_app.py
import tkinter
from tkinter import messagebox, filedialog
import customtkinter as ctk
import threading, time, subprocess, os, webbrowser, sys, requests, json, uuid, logging, socket, shutil
import re
from urllib.parse import urlencode
from PIL import Image
from packaging.version import parse as parse_version
from getmac import get_mac_address
from datetime import datetime
from dotenv import load_dotenv

# Note: Heavy libraries (Selenium, Pygame, Sentry) are imported inside functions 
# to speed up startup time.

from location_data import STATE_DISTRICT_MAP
from tabs.history_manager import HistoryManager
import config

from utils import resource_path, get_data_path, get_user_downloads_path, get_config, save_config

if config.OS_SYSTEM == "Windows":
    import ctypes

load_dotenv()
config.create_default_config_if_not_exists()

# Store original messagebox functions
_original_showinfo = messagebox.showinfo
_original_showwarning = messagebox.showwarning
_original_showerror = messagebox.showerror

ctk.set_default_color_theme(resource_path("theme.json"))
ctk.set_appearance_mode("System")


class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title=""):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.title = title

        self.header_label = ctk.CTkLabel(
            self, text=self.title.upper(),
            anchor="w", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray10", "gray80")
        )
        self.header_label.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="ew", padx=(5, 0))

    def add_widget(self, widget, **pack_options):
        widget.pack(in_=self.content_frame, **pack_options)
        return widget
    
class OnboardingStep(ctk.CTkFrame):
    def __init__(self, parent, title, description, icon):
        super().__init__(parent, fg_color="transparent")
        self.pack(expand=True, fill="both", padx=20, pady=(10, 0))

        if icon:
            icon_label = ctk.CTkLabel(self, image=icon, text="")
            icon_label.pack(pady=(10, 15))

        title_label = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(0, 10))

        desc_label = ctk.CTkLabel(self, text=description, wraplength=380, justify="center")
        desc_label.pack(pady=(0, 20))

class SkeletonLoader(ctk.CTkFrame):
    def __init__(self, parent, rows=5, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.pack(fill="both", expand=True, padx=20, pady=20)
        self.placeholders = []
        for _ in range(rows):
            row_frame = ctk.CTkFrame(self, fg_color="transparent")
            row_frame.pack(fill="x", pady=10)
            icon_ph = ctk.CTkFrame(row_frame, width=40, height=40, corner_radius=20, fg_color=("gray85", "gray25"))
            icon_ph.pack(side="left", padx=(0, 15))
            text_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            text_frame.pack(side="left", fill="x", expand=True)
            line1 = ctk.CTkFrame(text_frame, height=15, width=200, fg_color=("gray85", "gray25"))
            line1.pack(anchor="w", pady=(0, 5))
            line2 = ctk.CTkFrame(text_frame, height=12, width=120, fg_color=("gray90", "gray30"))
            line2.pack(anchor="w")
            self.placeholders.extend([icon_ph, line1, line2])
        self.animate_step = 0
        self.animating = True
        self._animate()

    def _animate(self):
        # FIX: Check if widget exists
        if not self.animating or not self.winfo_exists(): return
        
        l1, l2 = "gray85", "gray90" 
        d1, d2 = "gray25", "gray30"
        
        if self.animate_step == 0:
            color_set = (l2, d2) 
            self.animate_step = 1
        else:
            color_set = (l1, d1) 
            self.animate_step = 0
            
        for p in self.placeholders:
            try:
                # Double safety check
                if p.winfo_exists():
                    p.configure(fg_color=color_set)
            except: pass
            
        self.after(800, self._animate)

    def stop(self):
        self.animating = False
        self.destroy()

class MarqueeLabel(ctk.CTkFrame):
    def __init__(self, parent, text, speed=1, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.speed = speed
        self.raw_text = text
        self.safe_bg = ("white", "#1D1E1E")
        
        self.canvas = tkinter.Canvas(
            self, 
            bg=self._apply_appearance_mode(self.safe_bg), 
            bd=0, 
            highlightthickness=0, 
            height=30,
            cursor="arrow" 
        )
        self.canvas.pack(fill="both", expand=True)
        
        self.items = [] 
        self.total_width = 0
        self.canvas_width = 1
        self.is_running = True  # Animation control flag
        
        self.bind("<Configure>", self._on_resize)
        self.bind("<Destroy>", self._on_destroy) # Event for cleanup
        self.update_text(text) 
        self._animate()

    def _on_destroy(self, event):
        """Called when widget is destroyed."""
        self.is_running = False

    def _on_resize(self, event):
        self.canvas_width = event.width
        self.update_colors()

    def update_colors(self):
        try:
            if not self.winfo_exists(): return
            mode = ctk.get_appearance_mode()
            bg_color = self._apply_appearance_mode(self.safe_bg)
            self.canvas.configure(bg=bg_color)
            default_color = "gray90" if mode == "Dark" else "gray40"
            for item in self.items:
                if not item.get('is_link'):
                    self.canvas.itemconfig(item['id'], fill=default_color)
        except Exception: pass

    def _parse_html(self, text):
        pattern = re.compile(r'(<a\s+href="([^"]+)">(.+?)</a>|<b>(.+?)</b>|<i>(.+?)</i>)')
        parts = []
        last_pos = 0
        for match in pattern.finditer(text):
            if match.start() > last_pos:
                parts.append({'text': text[last_pos:match.start()], 'type': 'normal'})
            full_match = match.group(0)
            if full_match.startswith('<a'):
                parts.append({'text': match.group(3), 'type': 'link', 'url': match.group(2)})
            elif full_match.startswith('<b>'):
                parts.append({'text': match.group(4), 'type': 'bold'})
            elif full_match.startswith('<i>'):
                parts.append({'text': match.group(5), 'type': 'italic'})
            last_pos = match.end()
        if last_pos < len(text):
            parts.append({'text': text[last_pos:], 'type': 'normal'})
        return parts if parts else [{'text': text, 'type': 'normal'}]

    def update_text(self, new_text):
        if not self.winfo_exists(): return
        self.raw_text = new_text
        self.canvas.delete("all")
        self.items = []
        self.total_width = 0
        
        mode = ctk.get_appearance_mode()
        default_color = "gray90" if mode == "Dark" else "gray40"
        link_color = "#3B82F6"
        base_font_family = "Segoe UI" if os.name == "nt" else "Arial"
        
        parsed_segments = self._parse_html(new_text)
        current_x = 10 
        y_pos = 15
        
        for seg in parsed_segments:
            text_content = seg['text']
            font_spec = (base_font_family, 13)
            fill_color = default_color
            is_link = False
            
            if seg['type'] == 'bold': font_spec = (base_font_family, 13, "bold")
            elif seg['type'] == 'italic': font_spec = (base_font_family, 13, "italic")
            elif seg['type'] == 'link':
                font_spec = (base_font_family, 13, "underline")
                fill_color = link_color
                is_link = True
            
            text_id = self.canvas.create_text(current_x, y_pos, text=text_content, anchor="w", fill=fill_color, font=font_spec)
            bbox = self.canvas.bbox(text_id)
            width = bbox[2] - bbox[0] if bbox else 0
            
            item_data = {'id': text_id, 'width': width, 'is_link': is_link, 'url': seg.get('url')}
            self.items.append(item_data)
            
            if is_link:
                self.canvas.tag_bind(text_id, "<Button-1>", lambda e, url=seg['url']: webbrowser.open(url))
                self.canvas.tag_bind(text_id, "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(text_id, "<Leave>", lambda e: self.canvas.configure(cursor="arrow"))
            
            current_x += width
        self.total_width = current_x

    def _animate(self):
        # 1. First Check: Is the flag set to stop?
        if not self.is_running: return

        # 2. Second Check: Does the widget actually exist?
        try:
            if not self.winfo_exists():
                self.is_running = False
                return
        except Exception:
            self.is_running = False
            return

        if not self.items:
            self.after(100, self._animate)
            return

        try:
            first_item = self.items[0]
            # 3. Third Check: Does the canvas item exist?
            try:
                self.canvas.bbox(first_item['id'])
            except:
                return # Canvas items gone

            last_item = self.items[-1]
            last_coords = self.canvas.coords(last_item['id'])
            
            if not last_coords: 
                self.after(20, self._animate)
                return

            if last_coords[0] + last_item['width'] < 0:
                offset = self.canvas_width + 20
                current_x_reset = offset
                for item in self.items:
                    self.canvas.coords(item['id'], current_x_reset, 15)
                    current_x_reset += item['width']
            else:
                for item in self.items:
                    self.canvas.move(item['id'], -self.speed, 0)

            self.after(20, self._animate)
        except Exception:
            # Silent fail to avoid terminal spam
            self.is_running = False

class ToastNotification(ctk.CTkToplevel):
    def __init__(self, parent, message, kind="success", duration=3000):
        super().__init__(parent)
        self.parent = parent
        
        # Colors definition
        colors = {
            "success": "#2E8B57", # Sea Green
            "error": "#C53030",   # Red
            "info": "#2B6CB0",    # Blue
            "warning": "#C05621"  # Orange
        }
        
        icons = {
            "success": "✅",
            "error": "❌",
            "info": "ℹ️",
            "warning": "⚠️"
        }
        
        bg_color = colors.get(kind, "#333333")
        icon_text = icons.get(kind, "ℹ️")

        # Window Setup (Borderless & Topmost)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0) # Start invisible for fade-in

        # --- NO TRANSPARENCY NEEDED (Square Look) ---
        # Hum background color wahi rakhenge jo notification ka hai
        self.configure(fg_color=bg_color)
        
        # Main Frame (Square Shape - No Corner Radius)
        self.frame = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=0, border_width=0)
        self.frame.pack(fill="both", expand=True)
        
        # Content Layout
        self.content = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.content.pack(padx=20, pady=12)
        
        # Icon
        self.icon_label = ctk.CTkLabel(self.content, text=icon_text, font=("Arial", 18), text_color="white")
        self.icon_label.pack(side="left", padx=(0, 10))
        
        # Message
        self.msg_label = ctk.CTkLabel(self.content, text=message, font=("Segoe UI", 14, "bold"), text_color="white")
        self.msg_label.pack(side="left")
        
        # Position set karein
        self.update_idletasks()
        self._position_window()
        
        # Animation Start
        self._animate_in()
        
        # Auto Destroy Timer
        self.after(duration, self._animate_out)
        
        # Click to dismiss
        self.bind("<Button-1>", lambda e: self._animate_out())
        self.frame.bind("<Button-1>", lambda e: self._animate_out())
        self.msg_label.bind("<Button-1>", lambda e: self._animate_out())
        self.icon_label.bind("<Button-1>", lambda e: self._animate_out())

    def _position_window(self):
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()
            
            my_w = self.winfo_reqwidth()
            my_h = self.winfo_reqheight()
            
            # Bottom Center Position
            pos_x = parent_x + (parent_w // 2) - (my_w // 2)
            pos_y = parent_y + parent_h - my_h - 60 
            
            self.geometry(f"+{pos_x}+{pos_y}")
        except:
            pass

    def _animate_in(self, step=0):
        if step <= 10:
            alpha = step / 10
            self.attributes("-alpha", alpha)
            self.after(20, lambda: self._animate_in(step+1))
            
    def _animate_out(self, step=10):
        if step >= 0:
            alpha = step / 10
            self.attributes("-alpha", alpha)
            self.after(20, lambda: self._animate_out(step-1))
        else:
            self.destroy()
class OnboardingGuide(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.current_step = 0

        self.title("Welcome to NREGA Bot!")
        w, h = 450, 350
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.grab_set()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scrollable_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.steps_data = [
            {"title": "Step 1: Launch a Browser", "desc": "First, click one of the 'Chrome' buttons in the main app to open a special browser. We recommend Chrome.", "icon": self.parent.icon_images.get("onboarding_launch")},
            {"title": "Step 2: Log In to the Portal", "desc": "In the new browser window, log in to the NREGA portal with your official credentials.", "icon": self.parent.icon_images.get("onboarding_login")},
            {"title": "Step 3: Choose Your Task", "desc": "Once logged in, return to this app and select your desired automation task from the navigation menu on the left.", "icon": self.parent.icon_images.get("onboarding_select")},
            {"title": "You're All Set!", "desc": "Fill in the required details for your chosen task and click 'Start Automation'. For more help, visit our website from the link in the footer.", "icon": self.parent.icon_images.get("onboarding_start")}
        ]

        self.step_frames = []
        for i, step_info in enumerate(self.steps_data):
            frame = OnboardingStep(self.scrollable_container, step_info["title"], step_info["desc"], step_info["icon"])
            self.step_frames.append(frame)


        self.footer = ctk.CTkFrame(self)
        self.footer.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 20))
        self.footer.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self.footer, height=10)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 15))

        self.next_button = ctk.CTkButton(self.footer, text="Next", command=self.show_next_step, width=100)
        self.next_button.grid(row=0, column=1)

        self.show_step(0)
        self.focus_force()

    def show_step(self, step_index):
        for i, frame in enumerate(self.step_frames):
            if i == step_index:
                frame.pack(expand=True, fill="both")
                frame.tkraise()
            else:
                frame.pack_forget()

        progress_value = (step_index + 1) / len(self.steps_data)
        self.progress_bar.set(progress_value)

        if step_index == len(self.steps_data) - 1:
            self.next_button.configure(text="Finish", command=self.destroy)
        else:
            self.next_button.configure(text="Next")

    def show_next_step(self):
        self.current_step += 1
        if self.current_step < len(self.steps_data):
            self.show_step(self.current_step)

class ComingSoonTab(ctk.CTkFrame):
    def __init__(self, parent, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.pack(expand=True, fill="both")
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Use a relevant icon if available
        try:
            icon_image = app_instance.icon_images.get("onboarding_launch") 
            if icon_image:
                 ctk.CTkLabel(container, text="", image=icon_image).pack(pady=(0, 20))
        except: pass

        ctk.CTkLabel(container, text="Coming Soon", font=ctk.CTkFont(size=28, weight="bold")).pack()
        ctk.CTkLabel(container, text="Sarkar Aapke Dwar Automation is under development.", 
                     font=ctk.CTkFont(size=14), text_color="gray60").pack(pady=(10, 0))


class NregaBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw() # Hide initially for smooth splash transition
        self.global_disabled_features = []
        self.trial_restricted_features = []
        # --- FAST STARTUP CONFIG ---
        self.initial_width = 1100
        self.initial_height = 800
        self.title(f"{config.APP_NAME}")
        self.minsize(1000, 700)

        # Initialize basics
        self.history_manager = HistoryManager(self.get_data_path)
        self.is_licensed = False; self.license_info = {}; self.machine_id = self._get_machine_id()
        self.update_info = {"status": "Checking...", "version": None, "url": None}
        self.driver = None; self.active_browser = None; self.open_on_about_tab = False
        self.sleep_prevention_process = None; self.is_validating_license = False
        self.active_automations = set(); self.icon_images = {}; self.automation_threads = {}
        self.stop_events = {}; self.nav_buttons = {}; self.content_frames = {}; self.tab_instances = {}
        self.button_to_category_frame = {}
        self.category_frames = {}
        self.last_selected_category = get_config('last_selected_category', 'All Automations')
        
        # --- VARIABLES INITIALIZATION (Fixed) ---
        self.sound_switch_var = tkinter.BooleanVar(value=get_config('sound_enabled', True))
        self.minimize_var = tkinter.BooleanVar(value=True) # <--- YE MISSING THA, AB ADD HO GAYA
        # ----------------------------------------

        self.status_label = None
        self.server_status_indicator = None
        self.loading_animation_label = None
        self.is_animating = False
        self.splash = None

        self.splash = self._create_splash_screen()
        self.splash.update() 

        # --- FIX 1: LOAD ICONS ON MAIN THREAD ---
        # MUST be done here, NOT in a thread, or the app will crash on launch
        self._load_all_icons() 

        # Now start the background thread for non-GUI tasks
        threading.Thread(target=self._background_initialization, daemon=True).start()

        # Define cleanup protocol to fix the "Hang" issue
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _background_initialization(self):
        """Loads heavy libraries and assets in background to keep UI responsive"""
        
        # 1. Initialize Pygame (Audio)
        try:
            import pygame
            pygame.mixer.init()
        except Exception as e:
            print(f"Warning: Could not initialize audio mixer: {e}")

        # 2. Initialize Sentry (Network)
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

        # # 3. Load Icons (Disk I/O)
        # self._load_all_icons()

        # 4. Apply patches
        messagebox.showinfo = self._custom_showinfo
        messagebox.showwarning = self._custom_showwarning
        messagebox.showerror = self._custom_showerror

        # 5. Trigger UI Setup on Main Thread
        self.after(10, self._finish_startup)

    def _finish_startup(self):
        """Called after background loading is done"""
        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<FocusIn>", self._on_window_focus)
        
        # Build UI
        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(0, weight=1)
        self._create_header(); self._create_footer()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._create_main_layout(for_activation=True)
        self.set_status("Initializing...")

        # License check
        self.perform_license_check_flow()

        # Transition Splash
        self.after(500, self._transition_from_splash)

    def _transition_from_splash(self):
        if self.splash: self._fade_out_splash(self.splash, step=0)

    def _fade_out_splash(self, splash, step):
        # Faster fade out (Kam steps, kam delay)
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
        
        # Animation hata di gayi hai - Seedha visible karein
        self.attributes("-alpha", 1.0) 
        self.deiconify()
        self.lift() # Window ko sabse upar layein
        self.focus_force() # Focus force karein taaki clicks register ho

    def _load_all_icons(self):
        """Loads all icons."""
        # Browsers
        self._load_icon("chrome", "assets/icons/chrome.png")
        self._load_icon("edge", "assets/icons/edge.png")
        self._load_icon("firefox", "assets/icons/firefox.png")
        
        # App Branding & Tools
        self._load_icon("nrega", "assets/icons/nrega.png")
        self._load_icon("whatsapp", "assets/icons/whatsapp.png")
        self._load_icon("feedback", "assets/icons/feedback.png")
        
        # --- FIX: Extractor Icon Explicit Load ---
        # Ensure 'extractor.png' exists in assets/icons folder!
        self._load_icon("extractor_icon", "assets/icons/extractor.png", size=(20, 20))
        
        # Settings Toggles
        self._load_icon("sound_on", "assets/icons/sound.png", size=(18, 18)) 
        self._load_icon("minimize", "assets/icons/minimize.png", size=(18, 18))
        
        # Theme Icons
        self._load_icon("theme_system", "assets/icons/theme_auto.png", size=(18, 18))
        self._load_icon("theme_light", "assets/icons/theme_sun.png", size=(18, 18))
        self._load_icon("theme_dark", "assets/icons/theme_moon.png", size=(18, 18))

        # Other Icons (Keep existing ones...)
        self._load_icon("wc_extractor", "assets/icons/extractor.png") # Keep old key just in case
        self._load_icon("disclaimer_warning", "assets/icons/emojis/warning.png", size=(16,16))
        self._load_icon("disclaimer_thunder", "assets/icons/emojis/thunder.png", size=(16,16))
        self._load_icon("disclaimer_tools", "assets/icons/emojis/tools.png", size=(16,16))
        self._load_icon("onboarding_launch", "assets/icons/emojis/thunder.png", size=(48, 48))
        self._load_icon("onboarding_login", "assets/icons/emojis/verify_jobcard.png", size=(48, 48))
        self._load_icon("onboarding_select", "assets/icons/emojis/wc_gen.png", size=(48, 48))
        self._load_icon("onboarding_start", "assets/icons/emojis/fto_gen.png", size=(48, 48))

        # --- NEW: Device Management Icons ---
        self._load_icon("device_edit", "assets/icons/edit.png", size=(20, 20))
        self._load_icon("device_reset", "assets/icons/reset.png", size=(20, 20))
        
        # Menu Icons
        self._load_icon("emoji_mr_gen", "assets/icons/emojis/mr_gen.png", size=(16,16))
        self._load_icon("emoji_mr_payment", "assets/icons/emojis/mr_payment.png", size=(16,16))
        self._load_icon("emoji_gen_wagelist", "assets/icons/emojis/gen_wagelist.png", size=(16,16))
        self._load_icon("emoji_send_wagelist", "assets/icons/emojis/send_wagelist.png", size=(16,16))
        self._load_icon("emoji_fto_gen", "assets/icons/emojis/fto_gen.png", size=(16,16))
        self._load_icon("emoji_emb_entry", "assets/icons/emojis/warning.png", size=(16,16))
        self._load_icon("emoji_emb_verify", "assets/icons/emojis/emb_verify.png", size=(16,16))
        self._load_icon("emoji_scheme_closing", "assets/icons/emojis/scheme_closing.png", size=(16,16))
        self._load_icon("emoji_del_work_alloc", "assets/icons/emojis/del_work_alloc.png", size=(16,16))
        self._load_icon("emoji_duplicate_mr", "assets/icons/emojis/duplicate_mr.png", size=(16,16))
        self._load_icon("emoji_wc_gen", "assets/icons/emojis/wc_gen.png", size=(16,16))
        self._load_icon("emoji_if_editor", "assets/icons/emojis/if_editor.png", size=(16,16))
        self._load_icon("emoji_add_activity", "assets/icons/emojis/add_activity.png", size=(16,16))
        self._load_icon("emoji_verify_jobcard", "assets/icons/emojis/verify_jobcard.png", size=(16,16))
        self._load_icon("emoji_verify_abps", "assets/icons/emojis/verify_abps.png", size=(16,16))
        self._load_icon("emoji_wc_extractor", "assets/icons/emojis/wc_extractor.png", size=(16,16))
        self._load_icon("emoji_resend_wg", "assets/icons/emojis/resend_wg.png", size=(16,16))
        self._load_icon("emoji_update_outcome", "assets/icons/emojis/update_outcome.png", size=(16,16))
        self._load_icon("emoji_file_manager", "assets/icons/emojis/file_manager.png", size=(16,16))
        self._load_icon("emoji_feedback", "assets/icons/emojis/feedback.png", size=(16,16))
        self._load_icon("emoji_about", "assets/icons/emojis/about.png", size=(16,16))
        self._load_icon("emoji_social_audit", "assets/icons/emojis/social_audit.png", size=(16,16))
        self._load_icon("emoji_mis_reports", "assets/icons/emojis/mis_reports.png", size=(16,16))
        self._load_icon("emoji_demand", "assets/icons/emojis/demand.png", size=(16,16))
        self._load_icon("emoji_mr_tracking", "assets/icons/emojis/mr_tracking.png", size=(16,16))
        self._load_icon("emoji_dashboard_report", "assets/icons/emojis/dashboard_report.png", size=(16,16))
        self._load_icon("emoji_mr_fill", "assets/icons/emojis/mr_fill.png", size=(16,16))
        self._load_icon("emoji_pdf_merger", "assets/icons/emojis/pdf_merger.png", size=(16,16))
        self._load_icon("emoji_issued_mr_report", "assets/icons/emojis/issued_mr_report.png", size=(16,16))
        self._load_icon("emoji_zero_mr", "assets/icons/emojis/zero_mr.png", size=(16,16))
        self._load_icon("emoji_work_alloc", "assets/icons/emojis/work_allocation.png", size=(16,16))
        self._load_icon("emoji_sad_auto", "assets/icons/emojis/thunder.png", size=(16,16))
        self._load_icon("emoji_sad_status", "assets/icons/emojis/sad_status.png", size=(16,16))


    def run_onboarding_if_needed(self):
        flag_path = get_data_path('.first_run_complete')
        if not os.path.exists(flag_path):
            OnboardingGuide(self)
            try:
                with open(flag_path, 'w') as f: f.write(datetime.now().isoformat())
            except Exception as e: print(f"Could not write first run flag: {e}")

    def _create_splash_screen(self):
        splash = ctk.CTkToplevel(self); splash.overrideredirect(True)
        w, h = 300, 200; sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        x, y = (sw/2) - (w/2), (sh/2) - (h/2)
        splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        try:
            logo = ctk.CTkImage(Image.open(resource_path("logo.png")), size=(80, 80))
            ctk.CTkLabel(splash, image=logo, text="").pack(pady=(20, 10))
        except Exception: pass
        ctk.CTkLabel(splash, text=f"{config.APP_NAME}\nLoading...", font=("SF Pro Display", 14)).pack()
        splash.lift(); splash.attributes("-topmost", True)
        return splash
    
    def perform_license_check_flow(self):
        self.is_licensed = self.check_license()
        self.after(0, self._setup_licensed_ui if self.is_licensed else self._setup_unlicensed_ui)

    def _preload_and_update_about_tab(self):
        if "About" not in self.tab_instances: self.show_frame("About", raise_frame=False)
        self._update_about_tab_info(); self.update_idletasks()

    def _setup_licensed_ui(self):
        # Yahan layout destroy/recreate karne ki bajaye, bas UNLOCK karein
        self._unlock_app()
        
        # --- NEW LOGIC: Offline Lock Support with Fallback ---
        try:
            # 1. Global restrictions load karein
            self.global_disabled_features = self.license_info.get('global_disabled_features', [])
            
            # 2. Trial restrictions load karein
            key_type = str(self.license_info.get('key_type', '')).lower()
            
            if key_type == 'trial':
                # Check karein ki kya 'trial_restricted_features' key license info mein मौजूद hai?
                if 'trial_restricted_features' in self.license_info:
                    # Agar key hai (matlab nayi file hai), to uski value use karein
                    self.trial_restricted_features = self.license_info['trial_restricted_features']
                else:
                    # FAIL-SAFE: Agar key missing hai (purani file hai) aur server offline hai, 
                    # to RISK mat lo. Default PREMIUM features ko lock kar do.
                    # Aap chahein to yahan saare features ke naam daal sakte hain.
                    self.trial_restricted_features = [
                        "Sarkar Aapke Dwar", "SAD Update Status", "FTO Generation", 
                        "MR Gen", "MR Fill", "MR Payment", "Gen Wagelist", 
                        "Send Wagelist", "Demand", "Allocation", "Work Allocation",
                        "eMB Entry", "eMB Verify", "WC Gen", "IF Editor"
                    ]
            else:
                self.trial_restricted_features = []
                
            # 3. Turant lock apply karein
            self._apply_feature_flags()
            
        except Exception as e:
            print(f"Error applying local restrictions: {e}")
        # ---------------------------------------
        
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
        self._preload_and_update_about_tab()
        self.set_status("Activation Required")
        if self.show_activation_window():
            self.is_licensed = True
            self._setup_licensed_ui()
        else:
            self.on_closing(force=True)

    def _ping_server_in_background(self):
        """
        Checks server status in a dedicated background thread loop.
        This prevents UI freezing because requests never run on the main thread.
        """
        def ping_loop():
            while True: # Infinite loop inside the background thread
                is_connected = False
                try:
                    # Timeout check kar rahe hain
                    requests.get(config.LICENSE_SERVER_URL, timeout=5)
                    is_connected = True
                except requests.exceptions.RequestException:
                    is_connected = False
                
                # UI update ko main thread par bhejna zaroori hai
                try:
                    if self.winfo_exists(): # Check agar app abhi bhi khula hai
                        self.after(0, self.set_server_status, is_connected)
                    else:
                        break # Agar app band ho gaya to loop roko
                except:
                    break

                # Thread ko 20 second ke liye sula dein (UI freeze nahi hoga)
                time.sleep(20)

        # Thread start karein
        threading.Thread(target=ping_loop, daemon=True).start()

    def _on_window_focus(self, event=None):
        if self.is_licensed and not self.is_validating_license:
            self.after(500, lambda: threading.Thread(target=self._validate_in_background, daemon=True).start())

    def _on_sound_toggle_click(self):
        # Toggle Value
        new_val = not self.sound_switch_var.get()
        self.sound_switch_var.set(new_val)
        save_config('sound_enabled', new_val)
        
        # Update Visuals
        self._update_settings_btn_visuals(self.sound_btn, new_val)
        if new_val: self.play_sound("success")

    def _on_minimize_toggle_click(self):
        # Toggle Value
        new_val = not self.minimize_var.get()
        self.minimize_var.set(new_val)
        
        # Update Visuals
        self._update_settings_btn_visuals(self.minimize_btn, new_val)
        
        state = "Enabled" if new_val else "Disabled"
        self.show_toast(f"Auto-Minimize {state}", "info")

    def _update_settings_btn_visuals(self, btn, is_active):
        if is_active:
            btn.configure(fg_color=("gray85", "gray30")) # Active State (Pressed)
        else:
            btn.configure(fg_color="transparent") # Inactive State

    def _on_global_click(self, event):
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

    def play_sound(self, sound_name: str):
        if not self.sound_switch_var.get(): return
        
        sound_file = resource_path(f"assets/sounds/{sound_name}.wav")
        if not os.path.exists(sound_file):
            return

        try:
            if config.OS_SYSTEM == "Darwin":
                # CRITICAL FIX: Add stdout/stderr=subprocess.DEVNULL
                subprocess.Popen(
                    ["afplay", sound_file], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
            else:
                import pygame
                pygame.mixer.Sound(sound_file).play()
        except Exception as e:
            print(f"Error playing sound '{sound_name}': {e}")

    def _custom_showinfo(self, title, message, **options):
        # Sirf "Success" wale messages ko Toast banayenge
        # Taki Error aane par user ko OK dabana hi pade (Safety ke liye)
        
        # Agar message chhota hai, toh Toast dikhao
        if len(message) < 60 or "success" in message.lower() or "complete" in message.lower() or "finished" in message.lower():
            self.show_toast(message, kind="success")
            return "ok" # Fake return taaki code ruk na jaye
        else:
            # Agar message bada hai ya complex hai, toh purana popup hi dikhao
            self.play_sound("success")
            return _original_showinfo(title, message, **options)

    def _custom_showwarning(self, title, message, **options):
        # Warnings ko bhi Toast bana sakte hain agar chhota ho
        if len(message) < 50:
             self.show_toast(message, kind="warning")
             return "ok"
        
        self.play_sound("error")
        return _original_showwarning(title, message, **options)

    def _custom_showerror(self, title, message, **options):
        # Errors ko humesha POPUP rakhna chahiye taaki user ignore na kare
        self.play_sound("error")
        return _original_showerror(title, message, **options)

    def bring_to_front(self):
        self.lift()

    def show_toast(self, message, kind="success"):
        try:
            # Agar koi purana toast hai toh use hata do (Overlapping roko)
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

    def check_license(self):
        lic_file = get_data_path('license.dat')
        if not os.path.exists(lic_file): return False
        try:
            with open(lic_file, 'r', encoding='utf-8') as f: self.license_info = json.load(f)
            if 'key' not in self.license_info or 'expires_at' not in self.license_info: return False
            expires_dt = datetime.fromisoformat(self.license_info['expires_at'].split('T')[0])
            if datetime.now() > expires_dt: return False
            threading.Thread(target=self.validate_on_server, args=(self.license_info['key'], True), daemon=True).start()
            return True
        except Exception: return False

    def show_trial_lock_alert(self, feature_name):
        self.play_sound("error")
        if messagebox.askyesno("Premium Feature", f"'{feature_name}' is a premium feature available in paid plans.\n\nUpgrade to a full license to unlock unlimited access.\n\nWould you like to upgrade now?"):
            self.show_purchase_window()

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

    def _load_icon(self, name, path, size=(20, 20)):
        try: self.icon_images[name] = ctk.CTkImage(Image.open(resource_path(path)), size=size)
        except Exception as e: print(f"Warning: Could not load icon '{name}': {e}")

    def launch_chrome_detached(self):
        port, p_dir = "9222", os.path.join(os.path.expanduser("~"), "ChromeProfileForNREGABot")
        os.makedirs(p_dir, exist_ok=True)
        paths = {"Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"], "Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]}
        b_path = next((p for p in paths.get(config.OS_SYSTEM, []) if os.path.exists(p)), None)
        if not b_path: 
            self.play_sound("error")
            messagebox.showerror("Error", "Google Chrome not found."); return
        try:
            cmd = [
                b_path, 
                f"--remote-debugging-port={port}", 
                f"--user-data-dir={p_dir}",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--log-level=3",
                "--silent",
                config.MAIN_WEBSITE_URL, 
                "https://bookmark.nregabot.com/"
            ]
            
            flags = 0x00000008 if config.OS_SYSTEM == "Windows" else 0
            # CRITICAL FIX: stdout aur stderr ko DEVNULL kiya gaya
            subprocess.Popen(
                cmd, 
                creationflags=flags, 
                start_new_session=(config.OS_SYSTEM != "Windows"),
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            self.play_sound("success")
            messagebox.showinfo("Chrome Launched", "Chrome is starting. Please log in to the NREGA website.")
        except Exception as e: 
            self.play_sound("error")
            messagebox.showerror("Error", f"Failed to launch Chrome:\n{e}")

    def launch_edge_detached(self):
        port, p_dir = "9223", os.path.join(os.path.expanduser("~"), "EdgeProfileForNREGABot")
        os.makedirs(p_dir, exist_ok=True)
        paths = {"Darwin": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"], "Windows": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]}
        b_path = next((p for p in paths.get(config.OS_SYSTEM, []) if os.path.exists(p)), None)
        if not b_path: 
            self.play_sound("error")
            messagebox.showerror("Error", "Microsoft Edge not found."); return
        try:
            cmd = [
                b_path, 
                f"--remote-debugging-port={port}", 
                f"--user-data-dir={p_dir}",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                config.MAIN_WEBSITE_URL, 
                "https://bookmark.nregabot.com/"
            ]

            flags = 0x00000008 if config.OS_SYSTEM == "Windows" else 0
            # CRITICAL FIX: stdout aur stderr ko DEVNULL kiya gaya
            subprocess.Popen(
                cmd, 
                creationflags=flags, 
                start_new_session=(config.OS_SYSTEM != "Windows"),
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            self.play_sound("success")
            messagebox.showinfo("Edge Launched", "Edge is starting. Please log in to the NREGA website.")
        except Exception as e: 
            self.play_sound("error")
            messagebox.showerror("Error", f"Failed to launch Edge:\n{e}")

    def launch_firefox_managed(self):
        # Lazy load selenium
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager

        if self.driver and messagebox.askyesno("Browser Running", "Close existing Firefox and start new?"): self.driver.quit(); self.driver = None
        elif self.driver: return
        try:
            p_dir = os.path.join(os.path.expanduser("~"), "FirefoxProfileForNREGABot"); os.makedirs(p_dir, exist_ok=True)
            opts = FirefoxOptions(); opts.add_argument("-profile"); opts.add_argument(p_dir)
            self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=opts)
            self.active_browser = "firefox"; self.play_sound("success")
            self.driver.get(config.MAIN_WEBSITE_URL); self.driver.execute_script("window.open(arguments[0], '_blank');", "https://bookmark.nregabot.com/")
            self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception as e: 
            self.play_sound("error")
            messagebox.showerror("Error", f"Failed to launch Firefox:\n{e}"); self.driver = None; self.active_browser = None

    def get_driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.common.exceptions import WebDriverException

        available_browsers = []
        if self.driver:
            try:
                if not self.driver.window_handles: raise WebDriverException("No active windows")
                try: _ = self.driver.current_url
                except WebDriverException: self.driver.switch_to.window(self.driver.window_handles[0])
                available_browsers.append("firefox")
            except Exception: self.driver = None

        try:
            with socket.create_connection(("127.0.0.1", 9222), timeout=0.2): available_browsers.append("chrome")
        except (socket.timeout, ConnectionRefusedError): pass
        try:
            with socket.create_connection(("127.0.0.1", 9223), timeout=0.2): available_browsers.append("edge")
        except (socket.timeout, ConnectionRefusedError): pass

        if not available_browsers:
            self.play_sound("error")
            messagebox.showerror("Connection Failed", "No browser is running. Please launch one first.")
            return None

        selected_browser = available_browsers[0] if len(available_browsers) == 1 else self._ask_browser_selection(available_browsers)
        if not selected_browser: return None

        if selected_browser == "firefox":
            if not self.driver:
                self.play_sound("error")
                messagebox.showerror("Error", "Firefox session was lost. Please relaunch Firefox.")
                return None
            self.active_browser = "firefox"
            return self.driver
        elif selected_browser == "chrome":
            try:
                opts = ChromeOptions(); opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                driver = webdriver.Chrome(options=opts); self.active_browser = 'chrome'; return driver
            except Exception as e:
                self.play_sound("error"); messagebox.showerror("Connection Failed", f"Could not connect to Chrome.\nError: {e}"); return None
        elif selected_browser == "edge":
            try:
                opts = EdgeOptions(); opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
                driver = webdriver.Edge(options=opts); self.active_browser = 'edge'; return driver
            except Exception as e:
                self.play_sound("error"); messagebox.showerror("Connection Failed", f"Could not connect to Edge.\nError: {e}"); return None
        return None

    def _ask_browser_selection(self, options):
        selection_var = tkinter.StringVar(value="")
        dialog = ctk.CTkToplevel(self); dialog.title("Select Browser"); dialog.geometry("300x250"); dialog.resizable(False, False)
        dialog.transient(self); dialog.grab_set()
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (300 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (250 // 2)
        dialog.geometry(f"+{x}+{y}")
        ctk.CTkLabel(dialog, text="Multiple browsers detected.", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(dialog, text="Which one do you want to use?").pack(pady=(0, 20))
        def select(choice): selection_var.set(choice); dialog.destroy()
        for opt in options:
            ctk.CTkButton(dialog, text=f"Use {opt.capitalize()}", image=self.icon_images.get(opt, None), command=lambda o=opt: select(o)).pack(pady=5, padx=20, fill="x")
        self.wait_window(dialog); return selection_var.get()

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
        try: return get_mac_address() or "unknown-" + str(uuid.getnode())
        except Exception: return "error-mac"

    # --- REPLACE THIS FUNCTION in main_app.py ---

    def _create_header(self):
        # Main Header Container
        header = ctk.CTkFrame(self, corner_radius=15, fg_color=("white", "#1D1E1E")) 
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        header.grid_columnconfigure(1, weight=1)

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

        # Store in self so we can update it
        self.announcement_label = MarqueeLabel(announcement_frame, text="Connecting to server...", width=300)
        self.announcement_label.pack(fill="both", expand=True, pady=5)
        
        self.after(1000, self._fetch_app_config)

        # --- RIGHT: Toolbar ---
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.grid(row=0, column=2, sticky="e", padx=15, pady=8)

        # 1. Extractor
        self.extractor_btn = ctk.CTkButton(
            controls_frame, text="", image=self.icon_images.get("extractor_icon"), 
            width=35, height=35, corner_radius=8,
            fg_color=("gray95", "gray25"), hover_color=("gray85", "gray35"),
            command=lambda: self.show_frame("Workcode Extractor")
        )
        self.extractor_btn.pack(side="left", padx=(0, 10))

        # Separator
        ctk.CTkFrame(controls_frame, width=2, height=20, fg_color=("gray90", "gray30")).pack(side="left", padx=(0, 10))

        # 2. Browsers (Grouped) - CRITICAL FIX: Assigning to self variables
        browser_group = ctk.CTkFrame(controls_frame, fg_color="transparent")
        browser_group.pack(side="left", padx=(0, 10))
        
        self.launch_chrome_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("chrome"), 
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_chrome_detached
        )
        self.launch_chrome_btn.pack(side="left", padx=2)

        self.launch_edge_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("edge"), 
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_edge_detached
        )
        self.launch_edge_btn.pack(side="left", padx=2)

        self.launch_firefox_btn = ctk.CTkButton(
            browser_group, text="", image=self.icon_images.get("firefox"), 
            width=35, height=35, corner_radius=8,
            fg_color="transparent", hover_color=("gray90", "gray30"),
            command=self.launch_firefox_managed
        )
        self.launch_firefox_btn.pack(side="left", padx=2)

        # Separator
        ctk.CTkFrame(controls_frame, width=2, height=20, fg_color=("gray90", "gray30")).pack(side="left", padx=(0, 10))

        # 3. Settings
        settings_group = ctk.CTkFrame(controls_frame, fg_color=("gray95", "gray25"), corner_radius=20)
        settings_group.pack(side="left")

        # Theme Button
        self.current_theme_mode = get_config("theme_mode", "System")
        self.theme_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("theme_system"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._cycle_theme
        )
        self.theme_btn.pack(side="left", padx=(5, 2), pady=4)
        self._update_theme_icon()

        # Sound Button
        self.sound_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("sound_on"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_sound_toggle_click
        )
        self.sound_btn.pack(side="left", padx=2, pady=4)
        self._update_settings_btn_visuals(self.sound_btn, self.sound_switch_var.get())

        # Minimize Button
        self.minimize_btn = ctk.CTkButton(
            settings_group, text="", image=self.icon_images.get("minimize"),
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=("gray85", "gray30"),
            command=self._on_minimize_toggle_click
        )
        self.minimize_btn.pack(side="left", padx=(2, 5), pady=4)
        self._update_settings_btn_visuals(self.minimize_btn, self.minimize_var.get())
        
        # Dummy variable for compatibility if needed
        self.theme_combo = ctk.CTkOptionMenu(self, width=0, height=0)

    def _fetch_app_config(self):
        """Fetches global configuration (Announcement + Features)."""
        def _worker():
            try:
                url = f"{config.LICENSE_SERVER_URL}/api/app-config"
                resp = requests.get(url, timeout=20)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    msg = data.get("global_announcement", "")
                    if msg:
                        self.after(0, lambda: self.announcement_label.update_text(msg))
                    
                    # Alag-alag lists update karein
                    self.global_disabled_features = data.get("disabled_features", [])
                    
                    # Trial list sirf tab update karein agar user trial par hai
                    # --- FIX: Case-insensitive check (.lower()) ---
                    if (self.license_info.get('key_type') or '').lower() == 'trial':
                        self.trial_restricted_features = data.get("trial_restricted_features", [])
                    else:
                        self.trial_restricted_features = [] # Paid user ke liye empty
                        
                    self.after(0, self._apply_feature_flags)
                    
            except Exception as e:
                print(f"Config Fetch Error: {e}")
            finally:
                self.after(120000, self._fetch_app_config)
        
        threading.Thread(target=_worker, daemon=True).start()

    def _apply_feature_flags(self):
        """Applies visual locks or maintenance modes based on server config."""
        if not hasattr(self, 'nav_buttons'): return
        
        # Parse current app version
        current_ver = parse_version(config.APP_VERSION)

        for name, btn in self.nav_buttons.items():
            # Clean old labels
            current_text = btn.cget("text")
            clean_text = current_text.replace(" ⚠️", "").replace(" 🔒", "").replace(" (Update)", "").replace(" (Maintenance)", "")
            
            # Reset to default first
            btn.configure(state="normal", fg_color="transparent", text=clean_text, command=lambda n=name: self.show_frame(n))

            # --- Priority 1: Global Kill Switch (Smart Logic) ---
            # Now self.global_disabled_features is expected to be a Dict
            # But handle List case for backward compatibility
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
                    # Case A: Update Available
                    btn.configure(
                        state="normal", # Keep clickable
                        fg_color=("orange", "#D97706"), # Orange warning color
                        text=f"{clean_text} ⚠️ (Update)",
                        command=lambda n=name, v=fix_version_str: self.show_feature_update_alert(n, v)
                    )
                else:
                    # Case B: Maintenance (No fix yet OR user already has the fix)
                    # If user has the fix (current >= fix), we should strictly enable it.
                    # But if it's in the disabled list, it implies it's broken for *everyone* unless filtered by version.
                    # Simple Logic: If it's in the list, it's broken.
                    
                    btn.configure(
                        state="normal", # Keep clickable for message
                        fg_color=("red", "#991B1B"), # Red error color
                        text=f"{clean_text} ⚠️ (Maintenance)",
                        command=lambda n=name: self.show_feature_maintenance_alert(n)
                    )
            
            # Priority 2: Trial Restriction (Unchanged)
            elif name in self.trial_restricted_features:
                btn.configure(
                    state="normal",
                    fg_color=("gray95", "gray25"),
                    text=f"{clean_text} 🔒",
                    command=lambda n=name: self.show_trial_lock_alert(n)
                )

    def show_feature_update_alert(self, feature_name, fix_version):
        """Shows alert when a feature is disabled but a fix is available."""
        self.play_sound("error")
        if messagebox.askyesno(
            "Update Required", 
            f"The '{feature_name}' feature has been updated in version {fix_version}.\n\n"
            f"Please update NREGA Bot to the latest version to use this automation.\n\n"
            "Would you like to check for updates now?"
        ):
            # Switch to About tab and check for updates
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

    def _cycle_theme(self):
        modes = ["System", "Light", "Dark"]
        try:
            current_idx = modes.index(self.current_theme_mode)
        except ValueError:
            current_idx = 0
            
        next_idx = (current_idx + 1) % len(modes)
        self.current_theme_mode = modes[next_idx]
        
        # Apply Theme
        ctk.set_appearance_mode(self.current_theme_mode)
        save_config("theme_mode", self.current_theme_mode)
        
        # Visual Updates
        self._update_theme_icon()
        self.play_sound("click")
        
        # --- FIX: Force Announcement Color Update ---
        if hasattr(self, 'announcement_label'):
            self.announcement_label.update_colors()
        # --------------------------------------------
            
        self.after(100, self.restyle_all_treeviews)

    def _update_theme_icon(self):
        icon_key = f"theme_{self.current_theme_mode.lower()}" # theme_system, theme_light, theme_dark
        new_icon = self.icon_images.get(icon_key, self.icon_images.get("theme_system"))
        self.theme_btn.configure(image=new_icon)
        
        # Tooltip/Toast feel (Optional)
        # self.show_toast(f"Theme: {self.current_theme_mode}", "info")

    def _update_settings_btn_visuals(self, btn, is_active):
        if is_active:
            # GREEN SHADE (Light Green bg, Dark Green border/text feel)
            # Light mode: #E0F2F1 (Pale Teal), Dark mode: #1B5E20 (Dark Green)
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

    def _create_main_layout(self, for_activation=False):
        # Purana frame destroy karein
        if hasattr(self, 'main_layout_frame') and self.main_layout_frame.winfo_exists():
            self.main_layout_frame.destroy()
            # CRITICAL FIX: Screen refresh karein taaki purana frame visually gayab ho jaye
            self.update_idletasks() 

        self.main_layout_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_layout_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10,0))
        self.main_layout_frame.grid_rowconfigure(0, weight=1)
        self.main_layout_frame.grid_columnconfigure(1, weight=1)
        
        nav_scroll_frame = ctk.CTkScrollableFrame(self.main_layout_frame, width=200, label_text="", fg_color="transparent")
        nav_scroll_frame.grid(row=0, column=0, sticky="nsw", padx=(0,5))
        self._create_nav_buttons(nav_scroll_frame)
        
        self.content_area = ctk.CTkFrame(self.main_layout_frame)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)
        
        self._create_content_frames()
        
        if for_activation: 
            self._lock_app_to_about_tab()

    def _create_nav_buttons(self, parent):
        self.nav_buttons.clear()
        self.button_to_category_frame.clear()
        self.category_frames.clear()

        # --- 1. DISTINCT COLOR PALETTE ---
        CATEGORY_COLORS = {
            "Core NREGA Tasks":     ("#E3F2FD", "#0D2538"), # Soft Blue
            "JE & AE Automation":   ("#E8F5E9", "#0F2E16"), # Soft Green
            "Records & Workcode":   ("#FFF3E0", "#3E2723"), # Soft Orange/Brown
            "Utilities & Verification": ("#F3E5F5", "#2A0F36"), # Soft Purple
            "Reporting":            ("#FFEBEE", "#381115"), # Soft Red
            "Application":          ("#F5F5F5", "#212121"), # Soft Grey
        }
        
        ctk.CTkLabel(parent, text="Category Filter:", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", padx=10, pady=(10, 2))
        
        categories = ["All Automations"] + list(self.get_tabs_definition().keys())
        self.category_filter_menu = ctk.CTkOptionMenu(
            parent, 
            values=categories, 
            command=self._on_category_filter_change,
            fg_color=("gray80", "gray25"),
            button_color=("gray70", "gray30"),
            text_color=("black", "white")
        )
        self.category_filter_menu.set(self.last_selected_category)
        self.category_filter_menu.pack(fill="x", padx=10, pady=(0, 15))

        for cat, tabs in self.get_tabs_definition().items():
            cat_color = CATEGORY_COLORS.get(cat, ("#F5F5F5", "#2b2b2b"))
            
            cat_frame = CollapsibleFrame(parent, title=cat)
            cat_frame.configure(fg_color=cat_color, corner_radius=10)
            
            # --- FIX: grid_configure use kiya (pack_configure galat tha) ---
            try:
                cat_frame.content_frame.grid_configure(pady=(0, 5), padx=5)
            except Exception:
                pass 
            
            self.category_frames[cat] = cat_frame
            
            for name, data in tabs.items():
                btn = ctk.CTkButton(
                    cat_frame.content_frame, 
                    text=f" {name}", 
                    image=data.get("icon"), 
                    compound="left", 
                    command=lambda n=name: self.show_frame(n), 
                    anchor="w", 
                    font=ctk.CTkFont(size=13), 
                    height=35, 
                    corner_radius=8, 
                    fg_color="transparent", 
                    text_color=("gray10", "gray90"), 
                    hover_color=("gray100", "gray20")
                )
                btn.pack(fill="x", padx=8, pady=3)
                
                self.nav_buttons[name] = btn
                self.button_to_category_frame[name] = cat_frame

                # Check immediately if disabled (agar config pehle hi load ho chuka hai)
                if name in self.global_disabled_features:
                    btn.configure(state="disabled", text=f"{name} ⚠️ (Maintenance)")
                
        self._filter_nav_menu(self.last_selected_category)

    def _on_category_filter_change(self, selected_category: str):
        self.play_sound("select"); save_config('last_selected_category', selected_category); self._filter_nav_menu(selected_category)

    def _filter_nav_menu(self, selected_category: str):
        # 1. Pehle sabko hatao (Unpack)
        for frame in self.category_frames.values():
            frame.pack_forget()
        
        # 2. UI Engine ko saans lene do (Smoothness Hack)
        self.update_idletasks()
        
        # 3. Jo select hua hai use wapas lagao
        if selected_category == "All Automations":
            for cat, frame in self.category_frames.items():
                # Margin add karein taaki cards alag-alag dikhein
                frame.pack(fill="x", pady=8, padx=5) 
        else:
            if selected_category in self.category_frames:
                self.category_frames[selected_category].pack(fill="x", pady=5, padx=5)

    def _create_content_frames(self):
        self.content_frames.clear(); self.tab_instances.clear(); self.show_frame("About", raise_frame=False)

    def get_tabs_definition(self):
        # --- LAZY LOAD IMPORTS ---
        from tabs.msr_tab import MsrTab
        from tabs.wagelist_gen_tab import WagelistGenTab
        from tabs.wagelist_send_tab import WagelistSendTab
        from tabs.wc_gen_tab import WcGenTab
        from tabs.mb_entry_tab import MbEntryTab
        from tabs.if_edit_tab import IfEditTab
        from tabs.musterroll_gen_tab import MusterrollGenTab
        from tabs.about_tab import AboutTab
        from tabs.jobcard_verify_tab import JobcardVerifyTab
        from tabs.fto_generation_tab import FtoGenerationTab
        from tabs.workcode_extractor_tab import WorkcodeExtractorTab
        from tabs.add_activity_tab import AddActivityTab
        from tabs.abps_verify_tab import AbpsVerifyTab
        from tabs.del_work_alloc_tab import DelWorkAllocTab
        from tabs.update_estimate_tab import UpdateEstimateTab
        from tabs.duplicate_mr_tab import DuplicateMrTab
        from tabs.feedback_tab import FeedbackTab
        from tabs.file_management_tab import FileManagementTab
        from tabs.scheme_closing_tab import SchemeClosingTab
        from tabs.emb_verify_tab import EmbVerifyTab
        from tabs.resend_rejected_wg_tab import ResendRejectedWgTab
        from tabs.SA_report_tab import SAReportTab
        from tabs.mis_reports_tab import MisReportsTab
        from tabs.demand_tab import DemandTab
        from tabs.mr_tracking_tab import MrTrackingTab
        from tabs.dashboard_report_tab import DashboardReportTab
        from tabs.mr_fill_tab import MrFillTab
        from tabs.pdf_merger_tab import PdfMergerTab
        from tabs.issued_mr_report_tab import IssuedMrReportTab
        from tabs.zero_mr_tab import ZeroMrTab
        from tabs.work_allocation_tab import WorkAllocationTab
        from tabs.sarkar_aapke_dwar_tab import SarkarAapkeDwarTab
        from tabs.sad_update_tab import SADUpdateStatusTab

        return {
            "Core NREGA Tasks": {
                "MR Gen": {"creation_func": MusterrollGenTab, "icon": self.icon_images.get("emoji_mr_gen"), "key": "muster"},
                "MR Fill": {"creation_func": MrFillTab, "icon": self.icon_images.get("emoji_mr_fill"), "key": "mr_fill"},
                "MR Payment": {"creation_func": MsrTab, "icon": self.icon_images.get("emoji_mr_payment"), "key": "msr"},
                "Gen Wagelist": {"creation_func": WagelistGenTab, "icon": self.icon_images.get("emoji_gen_wagelist"), "key": "gen"},
                "Send Wagelist": {"creation_func": WagelistSendTab, "icon": self.icon_images.get("emoji_send_wagelist"), "key": "send"},
                "FTO Generation": {"creation_func": FtoGenerationTab, "icon": self.icon_images.get("emoji_fto_gen"), "key": "fto_gen"},
                "Scheme Closing": {"creation_func": SchemeClosingTab, "icon": self.icon_images.get("emoji_scheme_closing"), "key": "scheme_close"},
                "Del Work Alloc": {"creation_func": DelWorkAllocTab, "icon": self.icon_images.get("emoji_del_work_alloc"), "key": "del_work_alloc"},
                "Duplicate MR Print": {"creation_func": DuplicateMrTab, "icon": self.icon_images.get("emoji_duplicate_mr"), "key": "dup_mr"},
                "Demand": {"creation_func": DemandTab, "icon": self.icon_images.get("emoji_demand"), "key": "demand"},
                "Allocation": {"creation_func": WorkAllocationTab, "icon": self.icon_images.get("emoji_work_alloc"), "key": "allocation"},
            },
            "JE & AE Automation": {
                "eMB Entry": {"creation_func": MbEntryTab, "icon": self.icon_images.get("emoji_emb_entry"), "key": "mb_entry"},
                "eMB Verify": {"creation_func": EmbVerifyTab, "icon": self.icon_images.get("emoji_emb_verify"), "key": "emb_verify"},
            },
            "Records & Workcode": {
                "WC Gen": {"creation_func": WcGenTab, "icon": self.icon_images.get("emoji_wc_gen"), "key": "wc_gen"},
                "IF Editor": {"creation_func": IfEditTab, "icon": self.icon_images.get("emoji_if_editor"), "key": "if_edit"},
                "Add Activity": {"creation_func": AddActivityTab, "icon": self.icon_images.get("emoji_add_activity"), "key": "add_activity"},
                "Update Estimate": {"creation_func": UpdateEstimateTab, "icon": self.icon_images.get("emoji_update_outcome"), "key": "update_outcome"},
            },
            "Utilities & Verification": {
                "Verify Jobcard": {"creation_func": JobcardVerifyTab, "icon": self.icon_images.get("emoji_verify_jobcard"), "key": "jc_verify"},
                "Verify ABPS": {"creation_func": AbpsVerifyTab, "icon": self.icon_images.get("emoji_verify_abps"), "key": "abps_verify"},
                "Workcode Extractor": {"creation_func": WorkcodeExtractorTab, "icon": self.icon_images.get("emoji_wc_extractor"), "key": "wc_extract"},
                "Resend Rejected WG": {"creation_func": ResendRejectedWgTab, "icon": self.icon_images.get("emoji_resend_wg"), "key": "resend_wg"},
                "PDF Merger": {"creation_func": PdfMergerTab, "icon": self.icon_images.get("emoji_pdf_merger"), "key": "pdf_merger"},
                "Zero Mr": {"creation_func": ZeroMrTab, "icon": self.icon_images.get("emoji_zero_mr"), "key": "zero_mr"},
                "File Manager": {"creation_func": FileManagementTab, "icon": self.icon_images.get("emoji_file_manager"), "key": "file_manager"},
            },
            "AYASAD": {
                "Sarkar Aapke Dwar": {"creation_func": SarkarAapkeDwarTab, "icon": self.icon_images.get("emoji_sad_auto"), "key": "sad_auto"},
                "SAD Update Status": {"creation_func": SADUpdateStatusTab, "icon": self.icon_images.get("emoji_sad_status"), "key": "sad_status"},
            },
            "Reporting": {
                "Social Audit Report": {"creation_func": SAReportTab, "icon": self.icon_images.get("emoji_social_audit"), "key": "social_audit_respond"},
                "MIS Reports": {"creation_func": MisReportsTab, "icon": self.icon_images.get("emoji_mis_reports"), "key": "mis_reports"},
                "MR Tracking": {"creation_func": MrTrackingTab, "icon": self.icon_images.get("emoji_mr_tracking"), "key": "mr_tracking"},
                "Issued MR Details": {"creation_func": IssuedMrReportTab, "icon": self.icon_images.get("emoji_issued_mr_report"), "key": "issued_mr_report"},
                "Dashboard Report": {"creation_func": DashboardReportTab, "icon": self.icon_images.get("emoji_dashboard_report"), "key": "dashboard_report"},
            },
            "Application": {
                 "Feedback": {"creation_func": FeedbackTab, "icon": self.icon_images.get("emoji_feedback")},
                 "About": {"creation_func": AboutTab, "icon": self.icon_images.get("emoji_about")},
            }
        }

    def show_frame(self, page_name, raise_frame=True):
        # Step 1: Agar tab pehle se loaded hai, turant dikha do
        if page_name in self.tab_instances:
            if raise_frame:
                self.content_frames[page_name].tkraise()
                self._update_nav_button_color(page_name)
            return

        # Step 2: Agar tab loaded nahi hai, toh pehle SKELETON dikhao
        # Ek temporary frame banao
        loading_frame = ctk.CTkFrame(self.content_area)
        loading_frame.grid(row=0, column=0, sticky="nsew")
        
        # Skeleton start karo
        skeleton = SkeletonLoader(loading_frame, rows=4)
        loading_frame.tkraise()
        self.update_idletasks() # Screen par skeleton force karo draw hone ke liye
        
        # Step 3: Thoda sa delay dekar asli data load karo (taaki UI freeze na ho)
        def load_actual_tab():
            try:
                tabs = self.get_tabs_definition()
                for cat, tab_items in tabs.items():
                    if page_name in tab_items:
                        # Asli frame create karo
                        frame = ctk.CTkFrame(self.content_area)
                        frame.grid(row=0, column=0, sticky="nsew")
                        self.content_frames[page_name] = frame
                        
                        # Asli content initialize karo (Yeh time leta hai)
                        instance = tab_items[page_name]["creation_func"](frame, self)
                        instance.pack(expand=True, fill="both")
                        self.tab_instances[page_name] = instance
                        
                        # Skeleton hatao aur asli frame dikhao
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

        # 50ms baad load function chalao (UI ko saans lene do)
        self.after(50, load_actual_tab)

    def _update_nav_button_color(self, page_name):
        for name, btn in self.nav_buttons.items(): 
            btn.configure(fg_color=("gray90", "gray28") if name == page_name else "transparent")

    def open_web_file_manager(self):
        if self.license_info.get('key'): webbrowser.open_new_tab(f"{config.LICENSE_SERVER_URL}/authenticate-from-app/{self.license_info['key']}?next=files")
        else: self.play_sound("error"); messagebox.showerror("Error", "License key not found.")

    # --- FIXED: Added wait loop to ensure Tab is loaded before sending data ---

    def switch_to_if_edit_with_data(self, data):
        self.show_frame("IF Editor")
        
        def _wait_for_tab():
            if "IF Editor" in self.tab_instances:
                self.tab_instances["IF Editor"].load_data_from_wc_gen(data)
                self.play_sound("success")
                messagebox.showinfo("Data Transferred", f"{len(data)} items transferred.")
            else:
                self.after(100, _wait_for_tab) # Retry after 100ms
        
        _wait_for_tab()
    
    def run_work_allocation_from_demand(self, panchayat_name: str, work_key: str):
        self.show_frame("Allocation")
        
        def _wait_for_tab():
            if "Allocation" in self.tab_instances:
                alloc = self.tab_instances["Allocation"]
                # Thoda extra delay allocation tab ke liye taaki UI settle ho jaye
                self.after(200, lambda: alloc.run_automation_from_demand(panchayat_name, work_key))
                self.play_sound("success")
                messagebox.showinfo("Handoff", "Starting Work Allocation...")
            else:
                self.after(100, _wait_for_tab)
                
        _wait_for_tab()

    def switch_to_msr_tab_with_data(self, workcodes: str, panchayat_name: str):
        self.show_frame("MR Payment")
        
        def _wait_for_tab():
            if "MR Payment" in self.tab_instances:
                self.tab_instances["MR Payment"].load_data_from_mr_tracking(workcodes, panchayat_name)
                self.play_sound("success")
                messagebox.showinfo("Data Transferred", "Data sent to MR Payment.")
            else:
                self.after(100, _wait_for_tab)
        
        _wait_for_tab()

    def switch_to_emb_entry_with_data(self, workcodes: str, panchayat_name: str):
        self.show_frame("eMB Entry")
        
        def _wait_for_tab():
            if "eMB Entry" in self.tab_instances:
                self.tab_instances["eMB Entry"].load_data_from_mr_tracking(workcodes, panchayat_name)
                self.play_sound("success")
                messagebox.showinfo("Data Transferred", "Data sent to eMB Entry.")
            else:
                self.after(100, _wait_for_tab)
                
        _wait_for_tab()

    def switch_to_mr_fill_with_data(self, workcodes: str, panchayat_name: str):
        self.show_frame("MR Fill")
        
        def _wait_for_tab():
            if "MR Fill" in self.tab_instances:
                self.tab_instances["MR Fill"].load_data_from_dashboard(workcodes, panchayat_name)
                self.play_sound("success")
                messagebox.showinfo("Data Transferred", "Data sent to MR Fill.")
            else:
                self.after(100, _wait_for_tab)
        
        _wait_for_tab()

    def switch_to_mr_tracking_for_abps(self):
        self.show_frame("MR Tracking")
        
        def _wait_for_tab():
            if "MR Tracking" in self.tab_instances:
                self.tab_instances["MR Tracking"].set_for_abps_check()
                self.play_sound("success")
                messagebox.showinfo("Action Required", "Fill details to check ABPS Labour")
            else:
                self.after(100, _wait_for_tab)
        
        _wait_for_tab()

    def switch_to_duplicate_mr_with_data(self, workcodes: str, panchayat_name: str):
        self.show_frame("Duplicate MR Print")
        
        def _wait_for_tab():
            if "Duplicate MR Print" in self.tab_instances:
                self.tab_instances["Duplicate MR Print"].load_data_from_report(workcodes, panchayat_name)
                self.play_sound("success")
                messagebox.showinfo("Data Transferred", "Data sent to Duplicate MR.")
            else:
                self.after(100, _wait_for_tab)
        
        _wait_for_tab()

    def switch_to_zero_mr_tab_with_data(self, data_list: list):
        self.show_frame("Zero Mr")
        
        def _wait_for_tab():
            if "Zero Mr" in self.tab_instances:
                self.tab_instances["Zero Mr"].load_data_from_mr_tracking(data_list)
                self.play_sound("success")
                messagebox.showinfo("Data Transferred", "Data sent to Zero MR.")
            else:
                self.after(100, _wait_for_tab)
        
        _wait_for_tab()

    def send_wagelist_data_and_switch_tab(self, start, end):
        self.show_frame("Send Wagelist")
        
        def _wait_for_tab():
            if "Send Wagelist" in self.tab_instances:
                # Populate data once tab is ready
                self.tab_instances["Send Wagelist"].populate_wagelist_data(start, end)
            else:
                # Keep checking every 100ms
                self.after(100, _wait_for_tab)
        
        _wait_for_tab()
    
    def _create_footer(self):
        footer = ctk.CTkFrame(self, height=40, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 15))
        footer.grid_columnconfigure((0, 1, 3), weight=0); footer.grid_columnconfigure(2, weight=1)
        left_frame = ctk.CTkFrame(footer, fg_color="transparent"); left_frame.grid(row=0, column=0, sticky="w", padx=15)
        ctk.CTkLabel(left_frame, text="© 2025 NREGA Bot", text_color="gray50").pack(side="left")
        status_frame = ctk.CTkFrame(footer, fg_color="transparent"); status_frame.grid(row=0, column=1, columnspan=2, sticky="ew", padx=20)
        self.loading_animation_label = ctk.CTkLabel(status_frame, text="", width=20, font=ctk.CTkFont(size=14)); self.loading_animation_label.pack(side="left")
        self.status_label = ctk.CTkLabel(status_frame, text="Status: Ready", text_color="gray50", anchor="w"); self.status_label.pack(side="left")
        btn_container = ctk.CTkFrame(footer, fg_color="transparent"); btn_container.grid(row=0, column=3, sticky="e", padx=15)
        ctk.CTkButton(btn_container, text="File Manager", image=self.icon_images.get("emoji_file_manager"), command=self.open_web_file_manager, fg_color="transparent", hover=False, text_color=("gray10", "gray80")).pack(side="left")
        ctk.CTkButton(btn_container, text="Community", image=self.icon_images.get("whatsapp"), command=lambda: webbrowser.open_new_tab("https://chat.whatsapp.com/Bup3hDCH3wn2shbUryv8wn"), fg_color="transparent", hover=False, text_color=("gray10", "gray80")).pack(side="left", padx=(10, 0))
        ctk.CTkButton(btn_container, text="Contact Support", image=self.icon_images.get("feedback"), command=lambda: self.show_frame("Feedback"), fg_color="transparent", hover=False, text_color=("gray10", "gray80")).pack(side="left", padx=(10, 0))
        self.server_status_indicator = ctk.CTkFrame(btn_container, width=12, height=12, corner_radius=6, fg_color="gray"); self.server_status_indicator.pack(side="left", padx=(10, 5))
        ctk.CTkLabel(btn_container, text="Server").pack(side="left")
        self.set_status("Ready")

    def save_demo_csv(self, file_type: str):
        try:
            src = resource_path(f"assets/demo_{file_type}.csv")
            if not os.path.exists(src): self.play_sound("error"); messagebox.showerror("Error", "Demo file not found"); return
            save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=f"{file_type}_data.csv")
            if save_path: shutil.copyfile(src, save_path); self.play_sound("success"); messagebox.showinfo("Success", f"Demo file saved to:\n{save_path}")
        except Exception as e: self.play_sound("error"); messagebox.showerror("Error", str(e))

    def on_theme_change(self, new_theme: str): ctk.set_appearance_mode(new_theme); self.after(100, self.restyle_all_treeviews)
    def restyle_all_treeviews(self):
        for tab in self.tab_instances.values():
            if hasattr(tab, 'style_treeview'):
                if hasattr(tab, 'results_tree'): tab.style_treeview(tab.results_tree)
                if hasattr(tab, 'files_tree'): tab.style_treeview(tab.files_tree)

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

    def validate_on_server(self, key, is_startup_check=False):
        try:
            payload = {
                "key": key, 
                "machine_id": self.machine_id,
                "app_version": config.APP_VERSION 
            }
            resp = requests.post(f"{config.LICENSE_SERVER_URL}/api/validate", json=payload, timeout=10)
            
            self.after(0, self.set_server_status, True)
            data = resp.json()
            if resp.status_code == 200 and data.get("status") == "valid":
                self.license_info = {**data, 'key': key}
                
                # --- UPDATE START ---
                # Update lists from validation response
                if 'global_disabled_features' in data:
                    self.global_disabled_features = data['global_disabled_features']
                
                if 'trial_restricted_features' in data:
                    self.trial_restricted_features = data['trial_restricted_features']
                
                self.after(0, self._apply_feature_flags)
                # --- UPDATE END ---

                with open(get_data_path('license.dat'), 'w') as f: json.dump(self.license_info, f)
                if not is_startup_check: self.play_sound("success"); messagebox.showinfo("License Valid", "Activation successful!")
                return True
            else:
                if os.path.exists(get_data_path('license.dat')): os.remove(get_data_path('license.dat'))
                if not is_startup_check: self.play_sound("error"); messagebox.showerror("Validation Failed", data.get('reason', 'Unknown error'))
                return False
        except Exception: 
            self.after(0, self.set_server_status, False)
            if not is_startup_check: self.play_sound("error"); messagebox.showerror("Error", "Connection Error")
            return True

    def send_wagelist_data_and_switch_tab(self, start, end):
        self.show_frame("Send Wagelist")
        send_tab = self.tab_instances.get("Send Wagelist")
        if send_tab: self.after(100, lambda: send_tab.populate_wagelist_data(start, end))

    def show_activation_window(self):
        win = ctk.CTkToplevel(self); win.title("Activate Product")
        win.update_idletasks()
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        
        # --- FIX: Increased Height from 420 to 700 to fit QR Code ---
        w, h = min(450, sw-40), min(580, sh-40) 
        
        win.geometry(f'{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}')
        win.resizable(False, False); win.transient(self); win.grab_set()
        
        # --- FIX: Changed 'main' to ScrollableFrame so content never cuts off ---
        main = ctk.CTkScrollableFrame(win, fg_color="transparent")
        main.pack(expand=True, fill="both", padx=20, pady=20)
        
        ctk.CTkLabel(main, text="Product Activation", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10))
        
        activated = tkinter.BooleanVar(value=False)
        
        def on_trial():
            win.withdraw()
            if self.show_trial_registration_window(): activated.set(True); win.destroy()
            else: win.deiconify()

        # --- Helper to show Deactivation UI inside the modal ---
        # (YEH BLOCK AAPKA PURANA WALA HI HAI, SAME TO SAME)
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
        # --- End of Helper ---

        ctk.CTkButton(main, text="Start 30-Day Free Trial", command=on_trial).pack(pady=(20, 5), ipady=4, fill='x', padx=10)
        ctk.CTkLabel(main, text="— OR —").pack(pady=10)
        
        entry = ctk.CTkEntry(main, width=300, placeholder_text="Enter License Key or Email"); entry.pack(pady=5, padx=10, fill='x')
        if get_config('last_used_email'): entry.insert(0, get_config('last_used_email'))
        
        # --- NEW: OTP UI for Login ---
        otp_entry = ctk.CTkEntry(main, width=300, placeholder_text="Enter OTP (Only for Email Login)")
        otp_entry.pack(pady=5, padx=10, fill='x')
        
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
        # -----------------------------

        def on_unified_activate():
            input_val = entry.get().strip()
            otp_val = otp_entry.get().strip() # OTP value uthao
            
            if not input_val: 
                self.play_sound("error")
                messagebox.showwarning("Input Required", "Please enter a key or email", parent=win)
                return
            
            activate_btn.configure(state="disabled", text="Activating...")
            
            if "@" in input_val and "." in input_val: # Email Logic
                # OTP check
                if not otp_val:
                    self.play_sound("error")
                    messagebox.showwarning("OTP Required", "Please enter OTP for email login.", parent=win)
                    activate_btn.configure(state="normal", text="Login & Activate")
                    return

                try:
                    # Payload mein app_version aur otp bhejo
                    resp = requests.post(
                        f"{config.LICENSE_SERVER_URL}/api/login-for-activation", 
                        json={
                            "email": input_val, 
                            "machine_id": self.machine_id, 
                            "otp": otp_val,
                            "app_version": config.APP_VERSION  # <-- YEH LINE UPDATE HUI HAI
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
                        # Agar server update karne ko bole (redirect action)
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
            
            else: # License Key Logic (No OTP needed)
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
        win = ctk.CTkToplevel(self); win.title("Trial Registration")
        win.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        
        # Height thodi badha di taaki OTP field fit ho jaye
        w, h = min(540, sw-40), min(650, sh-40) 
        
        win.geometry(f'{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}')
        win.resizable(False, False); win.transient(self); win.grab_set()
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent"); scroll.pack(expand=True, fill="both", padx=10, pady=10)
        ctk.CTkLabel(scroll, text="Start Your Free Trial", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 5))
        entries = {}
        
        def add_field(p, label, key): 
            ctk.CTkLabel(p, text=label, anchor="w").pack(fill="x")
            e=ctk.CTkEntry(p); e.pack(fill="x", pady=(0,10)) 
            entries[key]=e
            
        add_field(scroll, "Full Name", "full_name")
        add_field(scroll, "Email", "email")

        # --- NEW: OTP Section Start ---
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
                # 30 seconds cooldown
                win.after(30000, lambda: send_otp_btn.configure(state="normal", text="Resend OTP"))

        send_otp_btn = ctk.CTkButton(otp_frame, text="Send OTP", width=100, command=send_otp_action)
        send_otp_btn.pack(side="right")
        # --- NEW: OTP Section End ---

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
            # OTP check add kiya
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

        # --- AUTO MINIMIZE LOGIC (Mac Chrome Fix Added) ---
        if self.minimize_var.get() and self.driver:
            try:
                # Standard Minimize (Windows/Firefox ke liye)
                self.driver.minimize_window()
                self.show_toast("Running in Background (Minimized)", "info")

                # --- MAC CHROME SPECIFIC FIX ---
                # Agar Mac hai aur Chrome hai, to AppleScript se force minimize karein
                if config.OS_SYSTEM == "Darwin" and self.active_browser == "chrome":
                    try:
                        subprocess.run([
                            "osascript", "-e", 
                            'tell application "Google Chrome" to set minimized of windows to true'
                        ])
                    except Exception:
                        pass
                # -------------------------------

            except Exception:
                pass
        # --------------------------------------------------

        def wrapper():
            try:
                target(*args)
            finally:
                self.after(0, self.on_automation_finished, key)
        
        t = threading.Thread(target=wrapper, daemon=True)
        self.automation_threads[key] = t
        t.start()

    def log_message(self, log, msg, level="info"): 
        log.configure(state="normal"); log.insert(tkinter.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"); log.configure(state="disabled"); log.see(tkinter.END)
    
    def clear_log(self, log): log.configure(state="normal"); log.delete("1.0", tkinter.END); log.configure(state="disabled")

    def on_closing(self, force=False):
        # FIX: Ensure prompt appears on top using parent=self
        if force or messagebox.askokcancel("Quit", "Quit application?", parent=self):
            
            # 1. Visual Feedback (Turant Hide karein)
            try:
                # Sound trigger karo (ab ye block nahi karega Update 3 ki wajah se)
                self.play_sound("shutdown")
                self.attributes("-alpha", 0.0) # Window Gayab
                
                # CRITICAL REMOVAL: self.update() aur time.sleep() hata diya
                # Ye dono functions band hoti hui window par HANG karte hain.
            except: pass
            
            # 2. Nuclear Option: Force Kill Process Immediately
            import os
            os._exit(0)

    def prevent_sleep(self):
        if not self.active_automations:
            if config.OS_SYSTEM == "Windows": ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
            elif config.OS_SYSTEM == "Darwin" and not self.sleep_prevention_process: self.sleep_prevention_process = subprocess.Popen(["caffeinate", "-d"])

    def allow_sleep(self):
        if not self.active_automations:
            if config.OS_SYSTEM == "Windows": ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            elif config.OS_SYSTEM == "Darwin" and self.sleep_prevention_process: self.sleep_prevention_process.terminate(); self.sleep_prevention_process = None

    def on_automation_finished(self, key):
        if key in self.active_automations: self.active_automations.remove(key)
        self.set_status("Finished"); self.after(5000, lambda: self.set_status("Ready"))
        if not self.active_automations: self.allow_sleep()

    def check_for_updates_background(self):
        def _check():
            try:
                # Timeout badha diya taaki slow connection pe fail na ho
                resp = requests.get(f"{config.MAIN_WEBSITE_URL}/version.json", timeout=15)
                data = resp.json()
                lat = data.get("latest_version")
                
                # Current version se comparison
                if lat and parse_version(lat) > parse_version(config.APP_VERSION):
                    
                    # --- SMART UPDATE LOGIC START ---
                    core_upd = data.get("core_update", {})
                    is_smart = False
                    download_url = data.get("download_url_windows") # Default to EXE
                    
                    # Check agar Smart Update available hai aur Full Reinstall required nahi hai
                    if core_upd and not core_upd.get("force_full_reinstall", False):
                        download_url = core_upd.get("url")
                        is_smart = True
                    # --- SMART UPDATE LOGIC END ---

                    self.update_info = {
                        "status": "available", 
                        "version": lat, 
                        "url": download_url, 
                        "is_smart_update": is_smart, # UI ko batane ke liye flag
                        "changelog": data.get("changelog", {}).get(lat, [])
                    }
                    self.after(0, self.show_update_prompt, lat)
                else:
                    self.update_info = {"status": "updated", "version": lat}
            except Exception as e: 
                print(f"Update Check Error: {e}")
                self.update_info['status'] = 'error'
            finally: 
                self.after(0, self._update_about_tab_info)
        
        threading.Thread(target=_check, daemon=True).start()

    def show_update_prompt(self, version):
        self.play_sound("update")
        if messagebox.askyesno("Update", f"Version {version} available. View?"):
            self.show_frame("About"); self.tab_instances.get("About").tab_view.set("Updates")

    def update_history(self, key, val): self.history_manager.save_entry(key, val)
    def remove_history(self, key, val): self.history_manager.remove_entry(key, val)

    def download_and_install_update(self, url, version):
        about = self.tab_instances.get("About")
        if not about: return
        
        # UI Update
        about.update_button.configure(state="disabled", text="Downloading...")
        about.update_progress.grid(row=4, column=0, pady=10, padx=20, sticky='ew')
        
        is_smart = self.update_info.get("is_smart_update", False)
        
        def _worker():
            try:
                # File name decide karein (EXE ya ZIP)
                filename = url.split('/')[-1]
                dl_path = os.path.join(self.get_user_downloads_path(), filename)
                
                # Download Logic
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    dl = 0
                    with open(dl_path, 'wb') as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                            dl += len(chunk)
                            if total > 0:
                                self.after(0, about.update_progress.set, dl/total)

                self.after(0, lambda: self.set_status("Installing update..."))

                # --- INSTALLATION LOGIC ---
                if is_smart and url.endswith(".zip"):
                    # Agar ZIP hai to Smart Update function call karein
                    self.after(0, lambda: self._apply_smart_update(dl_path))
                else:
                    # Agar EXE hai to purana logic (Full Installer)
                    if sys.platform == "win32":
                        os.startfile(dl_path)
                        self.after(1000, os._exit, 0) # Thoda time diya installer load hone ke liye
                    else:
                        subprocess.call(["open", dl_path])
                        
            except Exception as e:
                self.after(0, messagebox.showerror, "Update Failed", str(e))
                self.after(0, lambda: about.update_button.configure(state="normal", text="Retry Update"))

        threading.Thread(target=_worker, daemon=True).start()

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
            
            # Dev mode check (Safety)
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

            # --- MACOS LOGIC (CRITICAL FIX) ---
            elif sys.platform == "darwin":
                shell_script_path = os.path.join(self.get_data_path(), "updater.sh")
                
                # FIX: Added 'xattr -cr' to remove quarantine and 'chmod +x' for permission
                script_content = f"""#!/bin/bash
echo "Updating NREGA Bot..."
sleep 2

echo "Copying files..."
cp -R "{extract_dir}/"* "{app_dir}/"

echo "Fixing Permissions & Security..."
# 1. Remove Quarantine Attribute (Crash Fix)
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

def initialize_webdriver_manager():
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service as ChromeService
        ChromeService(ChromeDriverManager().install())
    except: pass
    try:
        from webdriver_manager.firefox import GeckoDriverManager
        from selenium.webdriver.firefox.service import Service as FirefoxService
        FirefoxService(GeckoDriverManager().install())
    except: pass

# --- NEW FUNCTION FOR LOADER ---
def run_application():
    """
    Ye function loader.py call karega jab naya update ready hoga.
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
    
    # Webdriver Manager Background Thread
    threading.Thread(target=initialize_webdriver_manager, daemon=True).start()
    
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

# Ye block tabhi chalega jab aap testing ke liye directly main_app.py run karenge
if __name__ == '__main__':
    run_application()