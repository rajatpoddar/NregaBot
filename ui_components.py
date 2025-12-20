import customtkinter as ctk
import tkinter
import tkinter as tk
import webbrowser
import os
import re
from PIL import Image
from utils import resource_path

# --- 1. COLLAPSIBLE FRAME (Sidebar Categories) ---
class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title=""):
        # OPTIMIZATION: corner_radius=0 for faster rendering
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.title = title

        # Header Frame
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(10, 2)) # Padding reduced
        
        self.header_label = ctk.CTkLabel(
            self.header_frame, 
            text=self.title.upper(),
            anchor="w", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("gray40", "gray60")
        )
        self.header_label.pack(side="left", fill="x", expand=True)

        # OPTIMIZATION: Removed Separator Line (Performance Boost)
        # Jo line pehle thi wo ab widget load nahi badhayegi

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_frame.grid(row=1, column=0, sticky="ew", padx=(0, 0))

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

class FormSkeleton(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # Background color aapke app theme ke hisab se set karein
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.bind("<Configure>", self.redraw)

    def redraw(self, event=None):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # Skeleton color (Light Grey)
        skel_color = "#E0E0E0" 

        # 1. Title/Header Block (Top Left)
        self.canvas.create_rectangle(20, 20, 300, 50, fill=skel_color, outline="")

        # 2. Form Fields (Rows of Label + Input)
        # Yeh loop 8 lines/rows banayega jo aapke 'data texts' ko represent karega
        start_y = 80
        gap = 60 # Har row ke beech ka gap
        
        for i in range(8): 
            y = start_y + (i * gap)
            
            # Label Skeleton (Chota box left side)
            self.canvas.create_rectangle(20, y, 150, y+20, fill=skel_color, outline="")
            
            # Input Field Skeleton (Lamba box right side)
            self.canvas.create_rectangle(170, y, w - 50, y+35, fill=skel_color, outline="")

        # 3. Action Buttons (Bottom)
        btn_y = start_y + (8 * gap) + 20
        self.canvas.create_rectangle(20, btn_y, 140, btn_y+40, fill=skel_color, outline="")
        self.canvas.create_rectangle(160, btn_y, 280, btn_y+40, fill=skel_color, outline="")
class SkeletonLoader(ctk.CTkFrame):
    def __init__(self, parent, rows=8, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.pack(fill="both", expand=True, padx=20, pady=20)
        self.placeholders = []
        
        # --- 1. Header Title ---
        title_frame = ctk.CTkFrame(self, width=250, height=35, corner_radius=8, fg_color=("gray85", "gray25"))
        title_frame.pack(anchor="w", pady=(0, 25))
        self.placeholders.append(title_frame)

        # --- 2. Top Info Cards (The "4 Circles" Area) ---
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 25))
        
        for _ in range(4): # 4 Blocks banayenge
            card = ctk.CTkFrame(stats_frame, fg_color=("white", "#2B2B2B"), corner_radius=10)
            card.pack(side="left", expand=True, fill="x", padx=6, ipady=10)
            
            # Circle (Icon Placeholder)
            circle = ctk.CTkFrame(card, width=45, height=45, corner_radius=22, fg_color=("gray85", "gray25"))
            circle.pack(side="left", padx=(15, 10))
            
            # Text Details
            text_box = ctk.CTkFrame(card, fg_color="transparent")
            text_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            
            l1 = ctk.CTkFrame(text_box, height=14, width=80, corner_radius=6, fg_color=("gray85", "gray25"))
            l1.pack(anchor="w", pady=(0, 6))
            l2 = ctk.CTkFrame(text_box, height=12, width=50, corner_radius=6, fg_color=("gray90", "gray30"))
            l2.pack(anchor="w")
            
            self.placeholders.extend([circle, l1, l2])

        # --- 3. Data List / Table (The "8 Lines" Area) ---
        table_frame = ctk.CTkFrame(self, fg_color=("white", "#2B2B2B"), corner_radius=12)
        table_frame.pack(fill="both", expand=True)
        
        # Fake Table Header
        header_row = ctk.CTkFrame(table_frame, height=40, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(15, 10))
        h1 = ctk.CTkFrame(header_row, height=20, width=100, corner_radius=5, fg_color=("gray85", "gray25"))
        h1.pack(side="left", padx=(0, 20))
        h2 = ctk.CTkFrame(header_row, height=20, width=150, corner_radius=5, fg_color=("gray85", "gray25"))
        h2.pack(side="left")
        self.placeholders.extend([h1, h2])
        
        # Fake Table Rows
        for i in range(rows):
            row = ctk.CTkFrame(table_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=8)
            
            # Row Structure (Multiple columns simulating real data)
            c1 = ctk.CTkFrame(row, height=16, width=40, corner_radius=8, fg_color=("gray90", "gray30")) # ID
            c1.pack(side="left", padx=(0, 20))
            
            w_text = 200 if i % 2 == 0 else 150
            c2 = ctk.CTkFrame(row, height=16, width=w_text, corner_radius=8, fg_color=("gray90", "gray30")) # Name
            c2.pack(side="left", padx=(0, 20))
            
            c3 = ctk.CTkFrame(row, height=16, corner_radius=8, fg_color=("gray90", "gray30")) # Details (Flexible)
            c3.pack(side="left", fill="x", expand=True)
            
            self.placeholders.extend([c1, c2, c3])
            
        self.animate_step = 0
        self.animating = True
        self._animate()

    def _animate(self):
        if not self.animating or not self.winfo_exists(): return
        
        # Thoda modern colors (Light/Dark mode compatible)
        # Pulse Effect: Light Gray <-> Slightly Darker Gray
        l1, l2 = "#E0E0E0", "#EEEEEE"  # Light Mode
        d1, d2 = "#2D3748", "#4A5568"  # Dark Mode
        
        mode = ctk.get_appearance_mode()
        
        if self.animate_step == 0:
            c_light, c_dark = l2, d2
            self.animate_step = 1
        else:
            c_light, c_dark = l1, d1
            self.animate_step = 0
            
        final_color = c_dark if mode == "Dark" else c_light
            
        for p in self.placeholders:
            try:
                if p.winfo_exists():
                    p.configure(fg_color=final_color)
            except: pass
            
        self.after(600, self._animate) # Thoda fast animation (600ms)

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