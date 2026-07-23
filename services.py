import os
import sys
import json
import uuid
import requests
import threading
import subprocess
import ctypes
from datetime import datetime
from typing import Any, Dict, Optional
from getmac import get_mac_address
from tkinter import messagebox
import config
from utils import get_data_path, get_user_downloads_path, parse_version

class ServiceManager:
    def __init__(self, app: object) -> None:
        self.app = app
        self.sleep_prevention_process: Optional[subprocess.Popen] = None
        self.machine_id: str = self._get_machine_id()

    def _get_machine_id(self) -> str:
        try:
            return get_mac_address() or "unknown-" + str(uuid.getnode())
        except Exception:
            return "error-mac"

    # --- LICENSE LOGIC ---
    def check_license(self) -> bool:
        lic_file = get_data_path('license.dat')
        if not os.path.exists(lic_file):
            return False
        try:
            with open(lic_file, 'r', encoding='utf-8') as f: 
                self.app.license_info = json.load(f)
            
            if 'key' not in self.app.license_info or 'expires_at' not in self.app.license_info:
                return False
            
            expires_dt = datetime.fromisoformat(self.app.license_info['expires_at'].split('T')[0])
            if datetime.now() > expires_dt:
                return False
            
            # Background validation
            threading.Thread(target=self.validate_on_server, args=(self.app.license_info['key'], True), daemon=True).start()
            return True
        except Exception:
            return False

    def validate_on_server(self, key: str, is_startup_check: bool = False) -> bool:
        try:
            payload: Dict[str, str] = {
                "key": key, 
                "machine_id": self.machine_id,
                "app_version": config.APP_VERSION 
            }
            # Timeout check
            resp = requests.post(f"{config.LICENSE_SERVER_URL}/api/validate", json=payload, timeout=10)
            
            # UI Update (Safe Threading)
            self.app.after(0, self.app.set_server_status, True)
            
            try:
                data = resp.json()
            except Exception:
                raise Exception(f"Server returned an unexpected response (status {resp.status_code})")
            if resp.status_code == 200 and data.get("status") == "valid":
                self.app.license_info = {**data, 'key': key}
                
                # Update Feature Flags
                if 'global_disabled_features' in data:
                    self.app.global_disabled_features = data['global_disabled_features']
                if 'trial_restricted_features' in data:
                    self.app.trial_restricted_features = data['trial_restricted_features']
                
                self.app.after(0, self.app._apply_feature_flags)

                with open(get_data_path('license.dat'), 'w') as f:
                    json.dump(self.app.license_info, f)
                
                if not is_startup_check: 
                    self.app.play_sound("success")
                    messagebox.showinfo("License Valid", "Activation successful!")
                return True
            else:
                if os.path.exists(get_data_path('license.dat')):
                    os.remove(get_data_path('license.dat'))
                if not is_startup_check: 
                    self.app.play_sound("error")
                    messagebox.showerror("Validation Failed", data.get('reason', 'Unknown error'))
                return False
        except Exception: 
            self.app.after(0, self.app.set_server_status, False)
            if not is_startup_check: 
                self.app.play_sound("error")
                messagebox.showerror("Error", "Connection Error")
            return True  # Offline mode allow kar rahe hain agar startup check hai

    # --- UPDATE LOGIC ---
    def check_for_updates_background(self) -> None:
        def _check() -> None:
            try:
                resp = requests.get(f"{config.MAIN_WEBSITE_URL}/version.json", timeout=15)
                data = resp.json()
                lat = data.get("latest_version")
                
                if lat and parse_version(lat) > parse_version(config.APP_VERSION):
                    # Smart Update Check
                    core_upd = data.get("core_update", {})
                    is_smart = False
                    download_url = data.get("download_url_windows")
                    
                    if core_upd and not core_upd.get("force_full_reinstall", False):
                        download_url = core_upd.get("url")
                        is_smart = True

                    self.app.update_info = {
                        "status": "available", 
                        "version": lat, 
                        "url": download_url, 
                        "is_smart_update": is_smart,
                        "changelog": data.get("changelog", {}).get(lat, [])
                    }
                    self.app.after(0, self.app.show_update_prompt, lat)
                else:
                    self.app.update_info = {"status": "updated", "version": lat}
            except Exception as e: 
                print(f"Update Check Error: {e}")
                self.app.update_info['status'] = 'error'
            finally: 
                self.app.after(0, self.app._update_about_tab_info)
        
        threading.Thread(target=_check, daemon=True).start()

    def download_and_install_update(self, url: str, version: str) -> None:
        about = self.app.tab_instances.get("About")
        if not about:
            return
        
        about.update_button.configure(state="disabled", text="Downloading...")
        about.update_progress.grid(row=4, column=0, pady=10, padx=20, sticky='ew')
        
        is_smart = self.app.update_info.get("is_smart_update", False)
        
        def _worker() -> None:
            try:
                filename = url.split('/')[-1]
                dl_path = os.path.join(get_user_downloads_path(), filename)
                
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    dl = 0
                    with open(dl_path, 'wb') as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                            dl += len(chunk)
                            if total > 0:
                                self.app.after(0, about.update_progress.set, dl/total)

                self.app.after(0, lambda: self.app.set_status("Installing update..."))

                if is_smart and url.endswith(".zip"):
                    self.app.after(0, lambda: self.app._apply_smart_update(dl_path))
                else:
                    if sys.platform == "win32":
                        os.startfile(dl_path)
                        self.app.after(1000, os._exit, 0)
                    else:
                        subprocess.call(["open", dl_path])
                        
            except Exception as e:
                self.app.after(0, messagebox.showerror, "Update Failed", str(e))
                self.app.after(0, lambda: about.update_button.configure(state="normal", text="Retry Update"))

        threading.Thread(target=_worker, daemon=True).start()

    # --- SYSTEM POWER ---
    def prevent_sleep(self) -> None:
        if not self.app.active_automations:
            if config.OS_SYSTEM == "Windows": 
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
            elif config.OS_SYSTEM == "Darwin" and not self.sleep_prevention_process: 
                self.sleep_prevention_process = subprocess.Popen(["caffeinate", "-d"])

    def allow_sleep(self) -> None:
        if not self.app.active_automations:
            if config.OS_SYSTEM == "Windows": 
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            elif config.OS_SYSTEM == "Darwin" and self.sleep_prevention_process: 
                self.sleep_prevention_process.terminate()
                self.sleep_prevention_process = None
