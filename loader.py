import sys
import os
import time
import requests
import zipfile
import json
import shutil
import threading
import subprocess
import traceback
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
EXTRACTED_DIR = os.path.join(LOCAL_DIR, "app_live") # New extraction folder
VERSION_FILE = os.path.join(LOCAL_DIR, "core_version.json")
LOG_FILE = os.path.join(LOCAL_DIR, "loader_log.txt")

# Ensure Local Dir Exists
os.makedirs(LOCAL_DIR, exist_ok=True)

def log_error(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
    except: pass

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

    def extract_zip(self):
        """Safe extraction of core.zip to EXTRACTED_DIR"""
        try:
            self.update_status("Extracting files...", -1)
            
            # 1. Clean old folder if exists
            if os.path.exists(EXTRACTED_DIR):
                try:
                    shutil.rmtree(EXTRACTED_DIR)
                except Exception as e:
                    print(f"Cleanup Error: {e}")
                    # Try renaming if delete fails (file lock issue)
                    try:
                        os.rename(EXTRACTED_DIR, f"{EXTRACTED_DIR}_old_{int(time.time())}")
                    except: pass

            # 2. Extract
            os.makedirs(EXTRACTED_DIR, exist_ok=True)
            with zipfile.ZipFile(CORE_ZIP_PATH, 'r') as zip_ref:
                zip_ref.extractall(EXTRACTED_DIR)
                
            return True
        except Exception as e:
            log_error(f"Extraction Failed: {e}")
            self.update_status(f"Extraction Error: {str(e)}", 0)
            time.sleep(2)
            return False

    def run_update_process(self):
        try:
            time.sleep(0.5) 
            
            # --- DEV MODE CHECK ---
            # अगर हम Local Dev environment में हैं, तो अपडेट चेक स्किप करें
            if os.path.exists(os.path.join(os.path.abspath("."), "main_app.py")):
                self.update_status("Dev Mode: Skipping Updates", 1.0)
                time.sleep(0.5)
                self.after(0, self.launch_main_app)
                return

            # --- PROD MODE: Check Updates ---
            
            # Initial Check: Do we need to extract existing zip?
            if os.path.exists(CORE_ZIP_PATH) and not os.path.exists(EXTRACTED_DIR):
                 self.extract_zip()

            # Check for new updates
            update_found = self.check_for_updates()
            
            if update_found:
                self.extract_zip()

            self.update_status("Launching application...", 1.0)
            time.sleep(0.5)
            self.after(0, self.launch_main_app)
            
        except Exception as e:
            log_error(f"Update Process Error: {e}")
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
                resp = requests.get(UPDATE_URL, headers=headers, timeout=5) # Short timeout
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
                
                # Update version file
                with open(VERSION_FILE, 'w') as f:
                    json.dump({"version": server_ver}, f)
                    
                return True # Update was performed
            else:
                self.update_status("App is up to date.", 1.0)
                time.sleep(0.5)
                return False
        except Exception as e:
            print(f"Update check error: {e}")
            return False

    def launch_main_app(self):
        """Cleanly closes splash and transitions to main app."""
        self.is_destroyed = True 
        
        # --- COMPLETE CLEANUP ---
        self.withdraw()
        self.quit() # Breaks the mainloop
        
# --- Entry Point ---
if __name__ == "__main__":
    if HAS_UI_LIBS:
        app = ModernSplashScreen()
        try:
            app.mainloop() 
        except KeyboardInterrupt:
            app.destroy()
            sys.exit(0)
            
        # --- TRANSITION LOGIC ---
        try:
            app.destroy()
        except:
            pass
            
        # 1. Determine Launch Path
        # Priority: Current Dir (Dev) -> Extracted Folder -> Zip (Fallback)
        cwd = os.path.abspath(".")
        launch_path = cwd # Default to current dir (Dev mode)
        
        # Check if we are running locally (Dev Mode)
        if os.path.exists(os.path.join(cwd, "main_app.py")):
            print(f"Dev Mode Detected: Running from {cwd}")
            launch_path = cwd
        # Else try Extracted Directory
        elif os.path.exists(EXTRACTED_DIR) and os.path.exists(os.path.join(EXTRACTED_DIR, "main_app.py")):
            launch_path = EXTRACTED_DIR
        elif os.path.exists(EXTRACTED_DIR) and os.path.exists(os.path.join(EXTRACTED_DIR, "main_app.pyc")):
            launch_path = EXTRACTED_DIR
        
        # 2. Setup Environment
        sys.path.insert(0, launch_path)
        try:
            os.chdir(launch_path) # CRITICAL: Sets working dir for assets/themes
        except Exception as e:
            print(f"Failed to change directory: {e}")

        # 3. Clean imports to force reload from new location
        modules_to_clean = ['main_app', 'ui_components', 'services', 'config', 'utils']
        for m in modules_to_clean:
            if m in sys.modules:
                del sys.modules[m]

        # 4. Launch
        try:
            import main_app 
            main_app.run_application()
        except Exception as e:
            # --- CRITICAL ERROR HANDLER ---
            # If app fails to launch, show the FULL error to the user
            log_error(f"Launch Crash: {e}\n{traceback.format_exc()}")
            
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            
            error_msg = traceback.format_exc()
            messagebox.showerror(
                "Critical Error", 
                f"Failed to launch application.\n\nPath: {launch_path}\n\nError:\n{error_msg}"
            )
            sys.exit(1)
            
    else:
        # HEADLESS MODE (No Splash)
        print("Launching NREGA Bot (Headless Mode)...")
        launch_path = os.path.abspath(".")
        if os.path.exists(EXTRACTED_DIR):
            launch_path = EXTRACTED_DIR
            
        sys.path.insert(0, launch_path)
        try:
            os.chdir(launch_path)
            import main_app
            main_app.run_application()
        except ImportError as e:
            print(f"Critical Error: {e}")