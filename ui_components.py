import customtkinter as ctk
import tkinter
import webbrowser
import os
import re
from PIL import Image
from utils import resource_path

# --- 1. COLLAPSIBLE FRAME (Sidebar Categories) ---
class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title=""):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.title = title

        # IMPROVED: Added a separator line and better spacing for the header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(15, 5))
        
        self.header_label = ctk.CTkLabel(
            self.header_frame, 
            text=self.title.upper(),
            anchor="w", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("gray40", "gray60")
        )
        self.header_label.pack(side="left", fill="x")

        # Optional: Subtle separator line next to text
        self.separator = ctk.CTkFrame(self.header_frame, height=2, fg_color=("gray90", "gray25"))
        self.separator.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=8)

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="ew", padx=(5, 0))

    def add_widget(self, widget, **pack_options):
        widget.pack(in_=self.content_frame, **pack_options)
        return widget

# --- 2. ONBOARDING STEP (Guide UI) ---
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

# --- 3. SKELETON LOADER (Loading Effect) ---
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
                if p.winfo_exists():
                    p.configure(fg_color=color_set)
            except: pass
            
        self.after(800, self._animate)

    def stop(self):
        self.animating = False
        self.destroy()

# --- 4. MARQUEE LABEL (Running Text) ---
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
        self.is_running = True 
        
        self.bind("<Configure>", self._on_resize)
        self.bind("<Destroy>", self._on_destroy)
        self.update_text(text) 
        self._animate()

    def _on_destroy(self, event):
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
        if not self.is_running: return
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
            try: self.canvas.bbox(first_item['id'])
            except: return 

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
            self.is_running = False

# --- 5. TOAST NOTIFICATION (Popup) ---
class ToastNotification(ctk.CTkToplevel):
    def __init__(self, parent, message, kind="success", duration=3000):
        super().__init__(parent)
        self.parent = parent
        
        colors = {"success": "#2E8B57", "error": "#C53030", "info": "#2B6CB0", "warning": "#C05621"}
        icons = {"success": "✅", "error": "❌", "info": "ℹ️", "warning": "⚠️"}
        
        bg_color = colors.get(kind, "#333333")
        icon_text = icons.get(kind, "ℹ️")

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0) 
        self.configure(fg_color=bg_color)
        
        self.frame = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=0, border_width=0)
        self.frame.pack(fill="both", expand=True)
        
        self.content = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.content.pack(padx=20, pady=12)
        
        self.icon_label = ctk.CTkLabel(self.content, text=icon_text, font=("Arial", 18), text_color="white")
        self.icon_label.pack(side="left", padx=(0, 10))
        
        self.msg_label = ctk.CTkLabel(self.content, text=message, font=("Segoe UI", 14, "bold"), text_color="white")
        self.msg_label.pack(side="left")
        
        self.update_idletasks()
        self._position_window()
        self._animate_in()
        self.after(duration, self._animate_out)
        
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
            
            pos_x = parent_x + (parent_w // 2) - (my_w // 2)
            pos_y = parent_y + parent_h - my_h - 60 
            
            self.geometry(f"+{pos_x}+{pos_y}")
        except: pass

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

# --- 6. ONBOARDING GUIDE ---
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

# --- 7. COMING SOON TAB ---
class ComingSoonTab(ctk.CTkFrame):
    def __init__(self, parent, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.pack(expand=True, fill="both")
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        try:
            icon_image = app_instance.icon_images.get("onboarding_launch") 
            if icon_image:
                 ctk.CTkLabel(container, text="", image=icon_image).pack(pady=(0, 20))
        except: pass

        ctk.CTkLabel(container, text="Coming Soon", font=ctk.CTkFont(size=28, weight="bold")).pack()
        ctk.CTkLabel(container, text="Sarkar Aapke Dwar Automation is under development.", 
                     font=ctk.CTkFont(size=14), text_color="gray60").pack(pady=(10, 0))