import sys
import os
import time
import requests
import zipfile
import json
import shutil
import threading
import subprocess
from appdirs import user_data_dir

# --- Try importing CustomTkinter for Modern UI ---
try:
    import customtkinter as ctk
    from PIL import Image
    HAS_UI_LIBS = True
except ImportError:
    HAS_UI_LIBS = False
    print("Warning: CustomTkinter or PIL not found. Running in headless mode.")

# --- App Configuration ---
APP_NAME = "NREGABot"
UPDATE_URL = "https://nregabot.com/version.json" 

LOCAL_DIR = user_data_dir(APP_NAME, "PoddarSolutions")
CORE_ZIP_PATH = os.path.join(LOCAL_DIR, "core.zip")
VERSION_FILE = os.path.join(LOCAL_DIR, "core_version.json")

# Ensure Local Dir Exists
os.makedirs(LOCAL_DIR, exist_ok=True)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ModernSplashScreen(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.is_destroyed = False  # Flag to prevent zombie updates

        # Window Setup
        self.overrideredirect(True) # Borderless
        width, height = 400, 250
        
        # Center the window
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Theme
        ctk.set_appearance_mode("Dark")
        self.configure(fg_color="#1a1a1a")

        # Layout Frame
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # 1. Logo
        try:
            logo_path = resource_path("logo.png") 
            if os.path.exists(logo_path):
                pil_img = Image.open(logo_path)
                self.logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(60, 60))
                self.logo_label = ctk.CTkLabel(self.main_frame, image=self.logo_img, text="")
                self.logo_label.pack(pady=(10, 5))
        except Exception:
            pass 

        # 2. App Name
        self.title_label = ctk.CTkLabel(
            self.main_frame, 
            text="NREGA Bot", 
            font=("Roboto", 24, "bold"), 
            text_color="white"
        )
        self.title_label.pack(pady=(5, 20))

        # 3. Status Text
        self.status_label = ctk.CTkLabel(
            self.main_frame, 
            text="Initializing...", 
            font=("Roboto", 12), 
            text_color="#a0a0a0"
        )
        self.status_label.pack(pady=(0, 10))

        # 4. Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            self.main_frame, 
            width=300, 
            height=8, 
            corner_radius=4,
            progress_color="#3B82F6"
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 20))
        
        # Start the update process
        threading.Thread(target=self.run_update_process, daemon=True).start()

    def update_status(self, text, progress=None):
        """Updates UI safely. Checks if window exists to prevent TclError."""
        if self.is_destroyed: return
        try:
            self.after(0, lambda: self._update_ui(text, progress))
        except Exception: pass

    def _update_ui(self, text, progress):
        if self.is_destroyed: return
        try:
            self.status_label.configure(text=text)
            if progress is not None:
                if progress == -1: 
                    self.progress_bar.configure(mode="indeterminate")
                    self.progress_bar.start()
                else:
                    self.progress_bar.configure(mode="determinate")
                    self.progress_bar.stop()
                    self.progress_bar.set(progress)
        except Exception: pass

    def run_update_process(self):
        try:
            time.sleep(0.5) 
            self.check_for_updates()
            self.update_status("Launching application...", 1.0)
            time.sleep(0.5)
            self.after(0, self.launch_main_app)
        except Exception as e:
            self.update_status(f"Error: {str(e)}", 0)
            time.sleep(2)
            self.after(0, self.launch_main_app)

    def check_for_updates(self):
        try:
            self.update_status("Checking for updates...", -1)
            
            # 1. Local Version
            current_ver = "0.0.0"
            if os.path.exists(VERSION_FILE):
                try:
                    with open(VERSION_FILE, 'r') as f:
                        current_ver = json.load(f).get('version', "0.0.0")
                except: pass

            # 2. Server Check
            headers = {'User-Agent': 'NREGABot-Loader/1.0', 'Cache-Control': 'no-cache'}
            try:
                resp = requests.get(UPDATE_URL, headers=headers, timeout=10)
                data = resp.json()
            except Exception as e:
                print(f"Update check failed: {e}")
                return False
            
            # 3. OS Specific URL
            core_data = data.get('core_update', {})
            server_ver = core_data.get('version')
            
            download_url = None
            if sys.platform == "win32":
                download_url = core_data.get('url_windows')
            elif sys.platform == "darwin": 
                download_url = core_data.get('url_macos')
                
            if not download_url:
                download_url = core_data.get('url')

            if not server_ver or not download_url:
                return False

            if server_ver != current_ver:
                self.update_status(f"New version found: v{server_ver}", 0)
                time.sleep(0.5)
                self.update_status("Downloading update...", 0)
                
                r = requests.get(download_url, headers=headers, stream=True)
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                
                with open(CORE_ZIP_PATH, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = downloaded / total_size
                                self.update_status(f"Downloading... {int(percent*100)}%", percent)
                
                self.update_status("Installing update...", -1)
                with open(VERSION_FILE, 'w') as f:
                    json.dump({"version": server_ver}, f)
                time.sleep(0.5)
                return True
            else:
                self.update_status("App is up to date.", 1.0)
                time.sleep(0.5)
        except Exception as e:
            print(f"Update check error: {e}")
        return False

    def launch_main_app(self):
        """Cleanly closes splash and transitions to main app."""
        self.is_destroyed = True # Stop UI updates
        
        # --- FIX FOR macOS SEGMENTATION FAULT ---
        # CustomTkinter crashes on macOS if initialized twice in the same process.
        # If running as a script (not frozen EXE) on Mac, we launch main_app as a subprocess.
        if sys.platform == "darwin" and not getattr(sys, 'frozen', False):
            try:
                self.destroy() # Close window visually
                
                # Prepare environment to include core.zip in imports
                env = os.environ.copy()
                if os.path.exists(CORE_ZIP_PATH):
                    python_path = env.get("PYTHONPATH", "")
                    env["PYTHONPATH"] = f"{CORE_ZIP_PATH}{os.pathsep}{python_path}"
                
                # Launch Main App cleanly
                subprocess.Popen([sys.executable, "main_app.py"], env=env)
                sys.exit(0) # Exit Loader process completely
            except Exception as e:
                print(f"Failed to subprocess launch: {e}")
        # ----------------------------------------

        self.destroy()
        
        if os.path.exists(CORE_ZIP_PATH):
            sys.path.insert(0, CORE_ZIP_PATH)
        
        try:
            import main_app 
            main_app.run_application()
        except ImportError as e:
            # Fallback GUI
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Critical Error", f"Failed to launch application:\n{e}")
            sys.exit(1)

# --- Entry Point ---
if __name__ == "__main__":
    if HAS_UI_LIBS:
        app = ModernSplashScreen()
        try:
            app.mainloop()
        except KeyboardInterrupt:
            app.destroy()
    else:
        print("Launching NREGA Bot (Headless Mode)...")
        if os.path.exists(CORE_ZIP_PATH):
            sys.path.insert(0, CORE_ZIP_PATH)
        try:
            import main_app
            main_app.run_application()
        except ImportError as e:
            print(f"Critical Error: {e}")