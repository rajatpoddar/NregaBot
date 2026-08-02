import sys
import os
import time
import hashlib
import requests
import zipfile
import json
import shutil
import threading
import subprocess
import traceback
from appdirs import user_data_dir
# Add import config for COLORS
from src import config

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
EXTRACTED_DIR = os.path.join(LOCAL_DIR, "app_live")
VERSION_FILE = os.path.join(LOCAL_DIR, "core_version.json")
LOG_FILE = os.path.join(LOCAL_DIR, "loader_log.txt")

os.makedirs(LOCAL_DIR, exist_ok=True)

def log_error(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
    except Exception as e:
        print(f"log_error failed: {e}")

def sha256_file(path: str) -> str:
    """Return lowercase hex SHA-256 of a file (streaming — safe for big zips)."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
    except Exception as e:
        log_error(f"sha256_file failed for {path}: {e}")
        return ""
    return h.hexdigest()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ModernSplashScreen(ctk.CTk):
    """Professional animated splash screen with gradient design."""

    def __init__(self):
        super().__init__()

        self.is_destroyed = False
        self._dot_index = 0
        self._glow_direction = 1
        self._glow_step = 0

        # Window Setup — borderless, centered, larger
        self.overrideredirect(True)
        width, height = 520, 360

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - (width // 2)
        y = (sh // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        ctk.set_appearance_mode("System")

        # ---------- BACKGROUND (adapts to light/dark system theme) ----------
        self.configure(fg_color=(config.COLORS["bg_light_alt"], config.COLORS["bg_loader"]))

        # Outer frame with subtle border
        self._outer = ctk.CTkFrame(
            self, fg_color=((config.COLORS["bg_light"], config.COLORS["bg_dark"])), corner_radius=20,
            border_width=2, border_color=((config.COLORS["text_border"], config.COLORS["text_border_dark"]))
        )
        self._outer.pack(fill="both", expand=True, padx=4, pady=4)

        # Inner content container
        container = ctk.CTkFrame(self._outer, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=30, pady=25)

        # ---------- 1. LOGO (80x80) ----------
        self.logo_container = ctk.CTkFrame(container, fg_color="transparent", height=90)
        self.logo_container.pack(pady=(5, 5))
        self.logo_container.pack_propagate(False)

        self.logo_img_ctk = None
        try:
            logo_path = resource_path("assets/logo.png")
            if os.path.exists(logo_path):
                pil_img = Image.open(logo_path)
                self.logo_img_ctk = ctk.CTkImage(
                    light_image=pil_img, dark_image=pil_img, size=(80, 80)
                )
                self.logo_label = ctk.CTkLabel(
                    self.logo_container, image=self.logo_img_ctk, text=""
                )
                self.logo_label.pack(expand=True)
        except Exception:
            pass

        # ---------- 2. APP TITLE ----------
        ctk.CTkLabel(
            container,
            text="NREGA Bot",
            font=ctk.CTkFont(family="Helvetica Neue", size=28, weight="bold"),
            text_color=(config.COLORS["text_dark"], config.COLORS["text_bright"])
        ).pack(pady=(3, 2))

        # ---------- 3. TAGLINE ----------
        ctk.CTkLabel(
            container,
            text="VB-G-RAM-G Portal Support",
            font=ctk.CTkFont(family="Helvetica Neue", size=13),
            text_color=(config.COLORS["blue_hover"], config.COLORS["blue_loader_tag"])
        ).pack(pady=(0, 22))

        # ---------- 4. ANIMATED DOTS ----------
        self.dots_label = ctk.CTkLabel(
            container,
            text="Loading",
            font=ctk.CTkFont(family="Helvetica Neue", size=13),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_muted_light"])
        )
        self.dots_label.pack(pady=(0, 4))

        # ---------- 5. STATUS TEXT ----------
        self.status_label = ctk.CTkLabel(
            container,
            text="",
            font=ctk.CTkFont(family="Helvetica Neue", size=11),
            text_color=(config.COLORS["text_light"], config.COLORS["text_muted_dark"])
        )
        self.status_label.pack(pady=(2, 0))

        # ---------- 8. VERSION FOOTER ----------
        # Dynamic version from config — matches the app's actual build version
        # (lite_loader.py uses the same pattern).
        ctk.CTkLabel(
            container,
            text=f"v{config.APP_VERSION} \u00b7 NregaBot.com",
            font=ctk.CTkFont(family="Helvetica Neue", size=10),
            text_color=(config.COLORS["text_border"], config.COLORS["text_border_dark"])
        ).pack(side="bottom", pady=(0, 5))

        # ---------- START ANIMATIONS ----------
        self._anim_after_id = None
        self._animate_dots()

        # ---------- BACKGROUND UPDATE THREAD ----------
        threading.Thread(target=self.run_update_process, daemon=True).start()

    # ------------------------------------------------------------------
    #  ANIMATIONS
    # ------------------------------------------------------------------

    def _animate_dots(self):
        if self.is_destroyed:
            return
        dots = "." * (self._dot_index % 4)
        self._dot_index += 1
        try:
            self.dots_label.configure(text=f"Loading{dots}")
            self._anim_after_id = self.after(450, self._animate_dots)
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  UI UPDATE HELPERS
    # ------------------------------------------------------------------

    def update_status(self, text, progress=None):
        """Thread-safe UI update."""
        if self.is_destroyed:
            return
        try:
            self.after(0, lambda: self._update_ui(text, progress))
        except Exception:
            pass

    def _update_ui(self, text, progress=None):
        if self.is_destroyed:
            return
        try:
            self.status_label.configure(text=text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  BUSINESS LOGIC (unchanged from original)
    # ------------------------------------------------------------------

    def extract_zip(self):
        """Safe extraction of core.zip to EXTRACTED_DIR"""
        try:
            self.update_status("Extracting files...", -1)

            if os.path.exists(EXTRACTED_DIR):
                try:
                    shutil.rmtree(EXTRACTED_DIR)
                except Exception as e:
                    print(f"Cleanup Error: {e}")
                    try:
                        os.rename(EXTRACTED_DIR, f"{EXTRACTED_DIR}_old_{int(time.time())}")
                    except:
                        pass

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
            if os.path.exists(os.path.join(os.path.abspath("."), "main_app.py")):
                self.update_status("Dev Mode: Skipping Updates", 1.0)
                time.sleep(0.5)
                self.after(0, self.launch_main_app)
                return

            # --- PROD MODE ---
            if os.path.exists(CORE_ZIP_PATH) and not os.path.exists(EXTRACTED_DIR):
                self.extract_zip()

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

            current_ver = "0.0.0"
            current_hash = ""
            if os.path.exists(VERSION_FILE):
                try:
                    with open(VERSION_FILE, 'r') as f:
                        _vdata = json.load(f)
                        current_ver = _vdata.get('version', "0.0.0")
                        current_hash = _vdata.get('hash', "") or ""
                except:
                    pass

            headers = {'User-Agent': 'NREGABot-Loader/1.0', 'Cache-Control': 'no-cache'}
            try:
                resp = requests.get(UPDATE_URL, headers=headers, timeout=5)
                data = resp.json()
            except Exception as e:
                print(f"Update check failed: {e}")
                return False

            core_data = data.get('core_update', {})
            server_ver = core_data.get('version')
            # Platform-specific hash: Windows and macOS core zips differ, so each
            # platform verifies against ITS OWN hash only. Never fall back to the
            # generic hash here — a generic hash describes the generic zip, not
            # this platform's zip, and a mismatch would block updates.
            if sys.platform == "win32":
                server_hash = core_data.get('hash_windows', '') or ''
            elif sys.platform == "darwin":
                server_hash = core_data.get('hash_macos', '') or ''
            else:
                server_hash = core_data.get('hash', '') or ''

            download_url = None
            if sys.platform == "win32":
                download_url = core_data.get('url_windows')
            elif sys.platform == "darwin":
                download_url = core_data.get('url_macos')

            if not download_url:
                download_url = core_data.get('url')

            if not server_ver or not download_url:
                return False

            # Update if the version changed OR the core zip content changed
            # (same-version hotfix: same version number, new hash → re-download).
            needs_update = (server_ver != current_ver) or (server_hash and server_hash != current_hash)

            if needs_update:
                self.update_status(f"New update found: v{server_ver}", 0)
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

                # Integrity check: if the server declared a hash, verify it before
                # applying. A mismatch means a corrupt/partial download — keep the
                # old version and retry on the next launch.
                if server_hash:
                    actual_hash = sha256_file(CORE_ZIP_PATH)
                    if not actual_hash or actual_hash != server_hash:
                        log_error(f"Hash mismatch: expected {server_hash}, got {actual_hash}. Keeping old version.")
                        self.update_status("Download corrupt — will retry next launch.", 0)
                        try:
                            os.remove(CORE_ZIP_PATH)
                        except Exception:
                            pass
                        time.sleep(1)
                        return False

                with open(VERSION_FILE, 'w') as f:
                    json.dump({"version": server_ver, "hash": server_hash}, f)

                return True
            else:
                self.update_status("App is up to date.", 1.0)
                time.sleep(0.5)
                return False
        except Exception as e:
            print(f"Update check error: {e}")
            return False

    def launch_main_app(self):
        """Cleanly closes splash and transitions to main app.
        Uses withdraw() instead of destroy() to keep the Tk interpreter alive
        so main_app.py can create its own CTk window afterwards.
        """
        self.is_destroyed = True
        if self._anim_after_id:
            try:
                self.after_cancel(self._anim_after_id)
            except Exception:
                pass
            self._anim_after_id = None
        self.withdraw()
        self.quit()


# --- ENTRY POINT ---
if __name__ == "__main__":
    if HAS_UI_LIBS:
        app = ModernSplashScreen()
        try:
            app.mainloop()
        except KeyboardInterrupt:
            app.destroy()
            sys.exit(0)

        try:
            app.destroy()
        except:
            pass

        # 1. Determine Launch Path
        cwd = os.path.abspath(".")
        launch_path = cwd

        if os.path.exists(os.path.join(cwd, "main_app.py")):
            print(f"Dev Mode Detected: Running from {cwd}")
            launch_path = cwd
        elif os.path.exists(EXTRACTED_DIR) and os.path.exists(os.path.join(EXTRACTED_DIR, "main_app.py")):
            launch_path = EXTRACTED_DIR
        elif os.path.exists(EXTRACTED_DIR) and os.path.exists(os.path.join(EXTRACTED_DIR, "main_app.pyc")):
            launch_path = EXTRACTED_DIR

        sys.path.insert(0, launch_path)
        try:
            os.chdir(launch_path)
        except Exception as e:
            print(f"Failed to change directory: {e}")

        modules_to_clean = ['main_app', 'ui_components', 'services', 'config', 'utils']
        for m in modules_to_clean:
            if m in sys.modules:
                del sys.modules[m]

        try:
            import main_app
            main_app.run_application()
        except Exception as e:
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
        # HEADLESS MODE
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
