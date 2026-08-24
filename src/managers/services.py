import os
import sys
import json
import uuid
import hashlib
import requests
import threading
import subprocess
import ctypes
from datetime import datetime
from typing import Any, Dict, Optional
from getmac import get_mac_address
from tkinter import messagebox
from src import config
from src.utils import get_data_path, get_user_downloads_path, parse_version


def _is_dev_mode() -> bool:
    """Detect running from the source tree (python main_app / python lite_app).

    Production installs run the app from the loader-managed app_live folder (or
    as a frozen bundle); dev runs execute the source directly. Update checks
    must be skipped in dev mode — the loader already skips updates for dev
    builds, and the app's same-version hotfix hash comparison is meaningless
    against a source checkout: there is no core_version.json there, so the local
    hash is '' and a non-empty server hash would trigger a false
    'bug-fix update' popup on EVERY launch.
    """
    if getattr(sys, 'frozen', False):
        return False  # packaged build (NREGABot / NREGABot Lite) — normal update flow
    try:
        from appdirs import user_data_dir
        prod_root = os.path.realpath(os.path.join(user_data_dir("NREGABot", "PoddarSolutions"), "app_live"))
    except Exception:
        prod_root = ""
    here = os.path.realpath(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return not prod_root or here != prod_root


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
                "app_version": config.APP_VERSION_WIRE 
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
        if config.BETA_BUILD:
            # Beta builds never auto-update from version.json
            self.app.update_info = {"status": "beta", "version": config.APP_VERSION}
            self.app.after(0, self.app._update_about_tab_info)
            return

        if _is_dev_mode():
            # Dev runs (python main_app) must never auto-check or prompt — the
            # loader already skips updates for dev builds, and the hotfix hash
            # comparison (server hash vs the empty local core_version.json hash)
            # would otherwise pop a false "bug-fix update" dialog every launch.
            self.app.update_info = {"status": "updated", "version": config.APP_VERSION}
            self.app.after(0, self.app._update_about_tab_info)
            return

        def _get_local_applied_hash() -> str:
            """Hash of the core zip the loader last applied (core_version.json)."""
            try:
                vf = get_data_path('core_version.json')
                if os.path.exists(vf):
                    with open(vf, 'r', encoding='utf-8') as f:
                        return json.load(f).get('hash', '') or ''
            except Exception:
                pass
            return ''

        def _check() -> None:
            try:
                resp = requests.get(f"{config.MAIN_WEBSITE_URL}/version.json", timeout=15)
                data = resp.json()
                lat = data.get("latest_version")

                # ── Known-bad version skip (rollback guard) ──
                # If a version crash-looped and the loader rolled back, the
                # About-tab check must not re-offer it — only a NEWER release
                # clears the ban (see src/utils.py is_bad_version).
                try:
                    from src.utils import is_bad_version
                    if lat and is_bad_version(lat):
                        self.app.update_info = {"status": "updated", "version": lat}
                        return  # finally below still refreshes the About tab
                except Exception:
                    pass

                core_upd = data.get("core_update", {}) or {}
                # Platform-specific hash (Windows/macOS core zips differ). Each
                # platform verifies against ITS OWN hash only — never fall back to
                # the generic hash here (it describes the generic zip, not this
                # platform's zip, and a mismatch would block updates).
                if sys.platform == "win32":
                    server_hash = core_upd.get("hash_windows", "") or ""
                elif sys.platform == "darwin":
                    server_hash = core_upd.get("hash_macos", "") or ""
                else:
                    server_hash = core_upd.get("hash", "") or ""

                # Same-version hotfix: version equal but core zip content changed.
                is_newer = bool(lat) and parse_version(lat) > parse_version(config.APP_VERSION)
                is_hotfix = bool(server_hash) and server_hash != _get_local_applied_hash()

                if is_newer or is_hotfix:
                    # Smart Update Check
                    is_smart = False
                    download_url = data.get("download_url_windows")
                    
                    if core_upd and not core_upd.get("force_full_reinstall", False):
                        # Use the platform-specific core zip (build_update.py names
                        # them core_mac_*.zip / core_win_*.zip). Fall back to the
                        # generic URL if the platform key is missing.
                        if sys.platform == "win32":
                            download_url = core_upd.get("url_windows") or core_upd.get("url")
                        elif sys.platform == "darwin":
                            download_url = core_upd.get("url_macos") or core_upd.get("url")
                        else:
                            download_url = core_upd.get("url")
                        is_smart = True

                    self.app.update_info = {
                        "status": "available", 
                        "version": lat, 
                        "url": download_url, 
                        "is_smart_update": is_smart,
                        "hash": server_hash,
                        "changelog": data.get("changelog", {}).get(lat, [])
                    }
                    self.app.after(0, self.app.show_update_prompt, lat, is_hotfix)
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
                # AUDIT FIX (25 Aug 2026) — transport guard: update payloads
                # must be HTTPS from our own host. A tampered/mis-edited
                # version.json must not point the download at http:// or a
                # foreign host (requests follows https→http redirects).
                if not isinstance(url, str) or not url.startswith("https://nregabot.com/"):
                    raise Exception(f"Refusing unsafe update URL: {str(url)[:80]}")
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

                # Integrity check before applying — a corrupt download (e.g. a
                # truncated transfer through the Cloudflare tunnel) would be
                # copied into the loader's core.zip and fail extraction on the
                # next launch, leaving the app stuck on the old version.
                expected_hash = (self.app.update_info or {}).get("hash") or ""
                if expected_hash:
                    actual_hash = hashlib.sha256()
                    with open(dl_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            actual_hash.update(chunk)
                    if actual_hash.hexdigest() != expected_hash:
                        try:
                            os.remove(dl_path)
                        except Exception:
                            pass
                        self.app.after(0, lambda: [
                            messagebox.showerror(
                                "Update Failed",
                                "Download is corrupt — it will be retried automatically next time."
                            ),
                            about.update_button.configure(state="normal", text="Retry Update")
                        ])
                        return

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
