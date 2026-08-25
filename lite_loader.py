# lite_loader.py
# Lightweight loader for NREGA Bot Lite — compact splash + auto-update.
#
# Acts exactly like the main app's loader.py but:
#   - 30% smaller splash (380x250 vs 520x360)
#   - No PIL/Pillow dependency (uses emoji instead of logo PNG)
#   - Simpler update path (no appdirs, extracts directly to install dir)
#   - Launches lite_app.py after splash
#
# Build with PyInstaller:
#   pyinstaller --name="NREGABotLite" --windowed lite_loader.py

import sys
import os
import json
import time
import hashlib
import threading
import shutil
import zipfile
import traceback
from typing import Optional

from src import config
from appdirs import user_data_dir
import requests
import customtkinter as ctk

# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

APP_NAME = "NREGA Bot Lite"
SPLASH_W, SPLASH_H = 380, 250
UPDATE_URL = "https://nregabot.com/version.json"
VERSION_FILE = "version.json"
LITE_APP_MODULE = "lite_app"
LITE_APP_ENTRY = "run_lite_application"


def parse_version(v: str) -> tuple:
    """Parse a semver string like '3.0.7' or '3.0.7-LITE' into a sortable tuple."""
    try:
        return tuple(int(x) for x in v.replace("-LITE", "").replace("-lite", "").split("."))
    except Exception:
        return (0, 0, 0)


def sha256_file(path: str) -> str:
    """Return lowercase hex SHA-256 of a file (streaming — safe for big zips)."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


# ═══════════════════════════════════════════════════════════════════════
# UPDATE ROLLBACK — boot-counter crash detection (mirrors loader.py)
# ═══════════════════════════════════════════════════════════════════════
# State files live in install_dir (user_data_dir("NREGA Bot Lite", ...)).
# The loader records a boot attempt before launching lite_app.py; lite_app
# deletes boot_state.json once its window is rendered. If MAX_BOOT_ATTEMPTS
# launches crash in a row, the previous update zip is re-applied instead of
# looping on a broken version.

MAX_BOOT_ATTEMPTS = 3
BOOT_CRASH_WINDOW_SECONDS = 600  # 10 min — a stale crash from days ago doesn't count


def _lite_read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _lite_write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _lite_boot_state_path(install_dir):
    return os.path.join(install_dir, "boot_state.json")


def _lite_bad_versions_path(install_dir):
    return os.path.join(install_dir, "bad_versions.json")


def _lite_should_rollback(install_dir):
    state = _lite_read_json(_lite_boot_state_path(install_dir), {}) or {}
    if int(state.get("attempts") or 0) < MAX_BOOT_ATTEMPTS:
        return False
    ts = state.get("ts")
    if ts:
        try:
            if time.time() - float(ts) > BOOT_CRASH_WINDOW_SECONDS:
                return False
        except Exception:
            return False
    return True


def _lite_record_boot_attempt(install_dir, version=""):
    state = _lite_read_json(_lite_boot_state_path(install_dir), {}) or {}
    attempts = 0
    ts = state.get("ts")
    if ts:
        try:
            if time.time() - float(ts) <= BOOT_CRASH_WINDOW_SECONDS:
                attempts = int(state.get("attempts") or 0)
        except Exception:
            attempts = 0
    _lite_write_json(_lite_boot_state_path(install_dir),
                     {"attempts": attempts + 1, "version": version or "", "ts": time.time()})


def _lite_reset_boot_state(install_dir, version=""):
    _lite_write_json(_lite_boot_state_path(install_dir),
                     {"attempts": 0, "version": version or "", "ts": time.time()})


def _lite_is_bad_version(install_dir, version):
    if not version:
        return False
    data = _lite_read_json(_lite_bad_versions_path(install_dir), {}) or {}
    max_bad = data.get("max_bad") or ""
    if not max_bad:
        return False
    try:
        return parse_version(version) <= parse_version(max_bad)
    except Exception:
        return False


def _lite_remember_bad_version(install_dir, version):
    if not version:
        return
    try:
        path = _lite_bad_versions_path(install_dir)
        data = _lite_read_json(path, {}) or {}
        cur = data.get("max_bad") or ""
        if not cur or parse_version(version) > parse_version(cur):
            data["max_bad"] = version
            _lite_write_json(path, data)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# COMPACT SPLASH
# ═══════════════════════════════════════════════════════════════════════

class LiteLoaderSplash(ctk.CTk):
    """Splash screen matching main app's loader design — compact size."""

    def __init__(self) -> None:
        super().__init__()

        self.is_destroyed = False
        self._dot_index = 0
        # Boot-counter flag: True in production (record a boot attempt before
        # launching lite_app.py so a crash-looping update can be rolled back),
        # False in dev mode. install_dir is where the state files live.
        self._track_boot = False
        self._install_dir = ""

        ctk.set_appearance_mode("System")

        # ── Borderless centered window ──
        self.overrideredirect(True)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - (SPLASH_W // 2)
        y = (sh // 2) - (SPLASH_H // 2)
        self.geometry(f"{SPLASH_W}x{SPLASH_H}+{x}+{y}")

        self.configure(fg_color=("#F8FAFC", "#1A1A2E"))

        # ── Outer card (matching main loader: corner_radius=20, border_width=2) ──
        card = ctk.CTkFrame(self, corner_radius=20,
                            fg_color=("#FFFFFF", "#2B2B2B"),
                            border_width=2,
                            border_color=("#E2E8F0", "#404040"))
        card.pack(fill="both", expand=True, padx=4, pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=24, pady=18)

        # Logo emoji (same as main loader — just emoji instead of PIL logo)
        ctk.CTkLabel(inner, text="🏛️", font=ctk.CTkFont(size=28)).pack(pady=(4, 2))

        # App title — exactly like main loader: "NREGA Bot"
        ctk.CTkLabel(inner, text="NREGA Bot",
                     font=ctk.CTkFont(family="Helvetica Neue", size=22, weight="bold"),
                     text_color=("#1E293B", "#F1F5F9")
                     ).pack(pady=(2, 1))

        # Tagline — exactly like main loader: "VB-G-RAM-G Portal Support"
        ctk.CTkLabel(inner, text="VB-G-RAM-G Portal Support",
                     font=ctk.CTkFont(family="Helvetica Neue", size=11),
                     text_color=("#3B82F6", "#60A5FA")
                     ).pack(pady=(0, 14))

        # Animated dots (matching main loader style)
        self.dots_lbl = ctk.CTkLabel(inner, text="Loading",
                                     font=ctk.CTkFont(family="Helvetica Neue", size=11),
                                     text_color=("#64748B", "#94A3B8"))
        self.dots_lbl.pack()

        # Status text
        self.status_lbl = ctk.CTkLabel(inner, text="",
                                       font=ctk.CTkFont(family="Helvetica Neue", size=10),
                                       text_color=("#94A3B8", "#64748B"))
        self.status_lbl.pack(pady=(2, 0))

        # Version footer — matching main loader style
        ctk.CTkLabel(inner, text=f"v{config.APP_VERSION.replace('-LITE','')} \u00b7 NregaBot.com",
                     font=ctk.CTkFont(family="Helvetica Neue", size=9),
                     text_color=("#CBD5E1", "#475569")
                     ).pack(side="bottom", pady=(0, 2))

        # ── Animations ──
        self._anim_after_id: Optional[str] = None
        self._animate_dots()

        # ── Background update check ──
        threading.Thread(target=self._run_update_process, daemon=True).start()

    # ────────────────────────────────────────────────────────────────
    # UI helpers
    # ────────────────────────────────────────────────────────────────

    def _animate_dots(self) -> None:
        if self.is_destroyed:
            return
        dots = "." * (self._dot_index % 4)
        self._dot_index += 1
        try:
            self.dots_lbl.configure(text=f"Loading{dots}")
            self._anim_after_id = self.after(400, self._animate_dots)
        except Exception:
            pass

    def _set_status(self, text: str) -> None:
        """Thread-safe status update."""
        if self.is_destroyed:
            return
        try:
            self.after(0, lambda: self.status_lbl.configure(text=text))
        except Exception:
            pass

    def _cancel_after_callbacks(self) -> None:
        """Cancel all pending after() timers to prevent stale callbacks on destroyed window."""
        if self._anim_after_id:
            try:
                self.after_cancel(self._anim_after_id)
            except Exception:
                pass
            self._anim_after_id = None

    # ────────────────────────────────────────────────────────────────
    # UPDATE LOGIC — same approach as main app's loader.py
    # ────────────────────────────────────────────────────────────────

    def _get_app_dirs(self) -> tuple:
        """
        Detect the app's runtime directories.

        In PyInstaller --onedir builds:
          sys._MEIPASS points to the _internal/ directory where Python
          source files live. Works on both Windows (alongside EXE) and
          macOS (.app bundle contents).

        In dev mode (source):
          sys._MEIPASS doesn't exist — use current working directory.

        Returns:
          (content_dir, install_dir)
          - content_dir: where source files live (sys._MEIPASS or cwd)
          - install_dir: where version.json should be stored
        """
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller built — sys._MEIPASS IS the _internal/ directory
            content_dir = sys._MEIPASS
            # For version.json: use a user-level persistent directory
            # (inside .app bundle on macOS is fragile; user_data_dir is safe)
            install_dir = user_data_dir(APP_NAME, "PoddarSolutions")
        else:
            # Dev mode — running from source
            content_dir = os.path.abspath(".")
            install_dir = content_dir
        return content_dir, install_dir

    def _run_update_process(self) -> None:
        try:
            time.sleep(0.3)

            content_dir, install_dir = self._get_app_dirs()

            # Dev mode — skip update check when running from source
            if not hasattr(sys, '_MEIPASS'):
                self._set_status("Dev Mode · Ready")
                time.sleep(0.4)
                self._launch_lite_app()
                return

            # Prod mode — record boot attempts so a crash-looping update can
            # be rolled back (see the rollback helpers at the top of this file).
            self._track_boot = True
            self._install_dir = install_dir

            # Ensure install_dir exists for version.json
            os.makedirs(install_dir, exist_ok=True)

            # ── Maintenance Mode ──
            maintenance_msg = None
            try:
                resp = requests.get(f"{UPDATE_URL}/api/app-config", timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    mm = data.get('maintenance_mode')
                    if isinstance(mm, dict) and mm.get('enabled'):
                        maintenance_msg = mm.get('message', 'App is under maintenance.')
            except Exception:
                pass
            if not maintenance_msg:
                try:
                    mm_path = os.path.join(install_dir, "maintenance_mode.json")
                    if os.path.exists(mm_path):
                        with open(mm_path, 'r') as f:
                            mm = json.load(f)
                        if isinstance(mm, dict) and mm.get('enabled'):
                            maintenance_msg = mm.get('message', 'App is under maintenance.')
                except Exception:
                    pass
            if maintenance_msg:
                self._set_status(f"🔧 {maintenance_msg}")
                time.sleep(5)
                self.destroy()
                return

            # ── Server-triggered Rollback ──
            try:
                rb_path = os.path.join(install_dir, "force_rollback.json")
                if os.path.exists(rb_path):
                    with open(rb_path, 'r') as f:
                        rb = json.load(f)
                    target_ver = rb.get('target_version', '') if isinstance(rb, dict) else ''
                    if target_ver:
                        msg = rb.get('message', '') or f"Rolling back to v{target_ver}..."
                        self._set_status(f"🔄 {msg}")
                        self._lite_restore_previous(install_dir, content_dir, target_ver)
                    # Clear after acting on it
                    try:
                        os.remove(rb_path)
                    except Exception:
                        pass
            except Exception:
                pass

            # ── Crash-loop rollback ──
            # Consecutive failed boots → re-apply the previous update zip
            # BEFORE the update check, so a broken version is never re-applied.
            if _lite_should_rollback(install_dir):
                state = _lite_read_json(_lite_boot_state_path(install_dir), {}) or {}
                crashed_version = str(state.get("version") or "")
                self._set_status("Repeated startup failure — restoring previous version...")
                if self._lite_restore_previous(install_dir, content_dir, crashed_version):
                    print(f"Rollback: restored previous Lite version (was v{crashed_version})")
                else:
                    print("Rollback: no previous version available for Lite")
                    _lite_reset_boot_state(install_dir, crashed_version)

            # ── Check for updates ──
            self._set_status("Checking for updates...")

            try:
                # Timeout 20s — Cloudflare + Zero-Trust tunnel latency can push
                # the version.json response past 5s; a too-tight timeout made the
                # update check silently fail (looked like "no update available").
                resp = requests.get(UPDATE_URL, timeout=20)
                data = resp.json()
            except Exception as e:
                print(f"Update check failed: {e}")
                self._set_status("Ready (offline)")
                time.sleep(0.5)
                self._launch_lite_app()
                return

            lat = data.get("latest_version", "")
            if not lat:
                self._set_status("Ready")
                time.sleep(0.3)
                self._launch_lite_app()
                return

            # ── Known-bad version skip (rollback guard) ──
            # A version that crash-looped and was rolled back must not be
            # re-offered; only a strictly NEWER release clears it.
            if _lite_is_bad_version(install_dir, lat):
                print(f"Rollback: skipping update to v{lat} (known bad)")
                self._set_status("Ready")
                time.sleep(0.3)
                self._launch_lite_app()
                return

            # ── Admin-blocked version skip ──
            try:
                bv_path = os.path.join(install_dir, "blocked_versions.json")
                if os.path.exists(bv_path):
                    with open(bv_path, 'r') as f:
                        bv = json.load(f)
                    versions = bv.get('versions', []) if isinstance(bv, dict) else []
                    if lat in versions:
                        print(f"Blocked: skipping update to v{lat} (admin blocked)")
                        self._set_status("Ready")
                        time.sleep(0.3)
                        self._launch_lite_app()
                        return
            except Exception:
                pass

            # Read current version + applied zip hash from persistent location
            current_ver = "0.0.0"
            current_hash = ""
            ver_path = os.path.join(install_dir, VERSION_FILE)
            if os.path.exists(ver_path):
                try:
                    with open(ver_path) as f:
                        _vdata = json.load(f)
                        current_ver = _vdata.get("version", "0.0.0")
                        current_hash = _vdata.get("hash", "") or ""
                except Exception:
                    pass

            # ── Update available — find download URL ──
            core_data = data.get("core_update", {})
            # Lite always downloads the generic core_vX.zip, so it uses the
            # generic hash field (not the platform-specific ones). Note: the
            # generic hash is normally empty (build_update.py only writes it on
            # Linux), so Lite hotfix detection is usually version-only — that's
            # expected, not a bug.
            server_hash = core_data.get("hash", "") or ""
            dl_url = (core_data.get("url")
                      or data.get("download_url_windows")
                      or data.get("download_url"))

            if not dl_url:
                self._set_status("Update info missing")
                time.sleep(0.5)
                self._launch_lite_app()
                return

            # Update if version is newer OR the core zip content changed
            # (same-version hotfix: same version number, new hash → re-download).
            hash_changed = bool(server_hash) and server_hash != current_hash
            if parse_version(lat) <= parse_version(current_ver) and not hash_changed:
                self._set_status("App is up to date")
                time.sleep(0.4)
                self._launch_lite_app()
                return

            # ── Keep the currently-installed update zip as the rollback target ──
            # _lite_update.zip holds the zip of the version that is CURRENTLY
            # installed (kept after every successful apply). Copy it aside with
            # its version/hash BEFORE the download below overwrites it, so a
            # crash-looping update can be rolled back.
            zip_path = os.path.join(install_dir, "_lite_update.zip")
            try:
                if os.path.exists(zip_path) and zipfile.is_zipfile(zip_path):
                    shutil.copy2(zip_path, os.path.join(install_dir, "_lite_prev_update.zip"))
                    _lite_write_json(os.path.join(install_dir, "_lite_prev_meta.json"),
                                     {"version": current_ver, "hash": current_hash})
            except Exception as e:
                print(f"Rollback: could not keep previous Lite zip: {e}")

            # ── Download update ZIP to install_dir (persistent) ──
            # AUDIT FIX (25 Aug 2026): transport guard — payload must be HTTPS
            # from our own host (mirrors the loader.py fix). NOTE: unlike the
            # main loader, an EMPTY server_hash is NOT refused here because the
            # generic hash field is normally empty for Lite (version-only
            # updates are the documented Lite flow); verification still runs
            # whenever a hash IS present.
            if not isinstance(dl_url, str) or not dl_url.startswith("https://nregabot.com/"):
                print(f"Update skipped: unsafe download URL '{str(dl_url)[:80]}'.")
                self._set_status("App is up to date")
                time.sleep(0.5)
                self._launch_lite_app()
                return

            self._set_status(f"Downloading v{lat}...")

            try:
                r = requests.get(dl_url, stream=True, timeout=60)
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
            except Exception as e:
                print(f"Download failed: {e}")
                self._set_status("Download failed")
                time.sleep(1)
                self._cleanup_file(zip_path)
                self._launch_lite_app()
                return

            # Integrity check: verify hash before extracting (same-version hotfix
            # + corrupt-download protection).
            if server_hash:
                actual_hash = sha256_file(zip_path)
                if not actual_hash or actual_hash != server_hash:
                    print(f"Hash mismatch: expected {server_hash}, got {actual_hash}. Keeping old version.")
                    self._set_status("Download corrupt — will retry next launch")
                    time.sleep(1)
                    self._cleanup_file(zip_path)
                    self._launch_lite_app()
                    return

            # Apply (keeps zip_path on success so it becomes the 'installed
            # version' zip used for the next rollback).
            self._apply_update_zip(install_dir, content_dir, zip_path, lat, server_hash)

        except Exception as e:
            print(f"Loader error: {e}")
            traceback.print_exc()

        self._launch_lite_app()

    # ────────────────────────────────────────────────────────────────
    # APPLY / ROLLBACK
    # ────────────────────────────────────────────────────────────────

    def _apply_update_zip(self, install_dir, content_dir, zip_path, version, hash_val):
        """Extract an update zip into content_dir and record its version.

        Keeps zip_path on success — it becomes the 'installed version' zip used
        as the rollback target for the NEXT update. Deletes it on failure so a
        corrupt zip is never treated as installed. Returns True on success.
        """
        tmp_dir = os.path.join(install_dir, "_lite_update_tmp")
        ver_path = os.path.join(install_dir, VERSION_FILE)
        try:
            self._set_status("Extracting update...")
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            os.makedirs(tmp_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmp_dir)

            # Merge extracted files into content_dir (= _internal/)
            for item in os.listdir(tmp_dir):
                src = os.path.join(tmp_dir, item)
                dst = os.path.join(content_dir, item)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)

            # Save updated version + zip hash in persistent location
            if version:
                with open(ver_path, "w") as f:
                    json.dump({"version": version, "hash": hash_val}, f)

            self._set_status("Update applied! ✓")
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"Extraction failed: {e}")
            self._set_status("Extraction failed")
            time.sleep(1)
            self._cleanup_file(zip_path)  # never treat a corrupt zip as installed
            return False
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _lite_restore_previous(self, install_dir, content_dir, crashed_version=""):
        """Re-apply the previously-installed update zip (saved at promote time)
        and restore version.json from its meta. Returns True on success.
        """
        prev_zip = os.path.join(install_dir, "_lite_prev_update.zip")
        prev_meta = _lite_read_json(os.path.join(install_dir, "_lite_prev_meta.json"), {}) or {}
        if not os.path.exists(prev_zip) or not zipfile.is_zipfile(prev_zip):
            return False
        prev_ver = str(prev_meta.get("version") or "")
        prev_hash = str(prev_meta.get("hash") or "")

        # Stage the previous zip as the current update zip and apply it.
        dst = os.path.join(install_dir, "_lite_update.zip")
        try:
            shutil.copy2(prev_zip, dst)
        except Exception as e:
            print(f"Rollback: could not stage previous zip: {e}")
            return False

        if not self._apply_update_zip(install_dir, content_dir, dst, prev_ver, prev_hash):
            return False

        if crashed_version:
            _lite_remember_bad_version(install_dir, crashed_version)
            print(f"Rollback: marked v{crashed_version} as bad — updates to it will be skipped")
        _lite_reset_boot_state(install_dir, prev_ver)
        return True

    # ────────────────────────────────────────────────────────────────
    # LAUNCH
    # ────────────────────────────────────────────────────────────────

    def _launch_lite_app(self) -> None:
        """Cleanly close splash and transition to lite_app.py.
        Uses withdraw() instead of destroy() to keep the Tk interpreter alive
        so lite_app.py can create its own CTk window afterwards.
        """
        # ── Boot-counter: record this launch attempt BEFORE the app starts. ──
        # lite_app.py deletes boot_state.json once its window is rendered; a
        # crash before that leaves the counter to accumulate → the next launch
        # may roll back to the previous version. Production only.
        if getattr(self, "_track_boot", False):
            try:
                ver = "0.0.0"
                try:
                    with open(os.path.join(self._install_dir, VERSION_FILE), encoding="utf-8") as f:
                        ver = (json.load(f).get("version") or "0.0.0")
                except Exception:
                    pass
                _lite_record_boot_attempt(self._install_dir, ver)
            except Exception:
                pass

        self.is_destroyed = True
        self._cancel_after_callbacks()
        self.withdraw()
        self.quit()

    @staticmethod
    def _cleanup_file(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = LiteLoaderSplash()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.destroy()
        sys.exit(0)
    except Exception:
        pass

    try:
        app.destroy()
    except Exception:
        pass

    # ── Signal lite_app to skip its own splash + redundant update check ──
    os.environ['LITE_LOADER_ACTIVE'] = '1'

    # ── Clean modules that might conflict ──
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("lite_loader"):
            del sys.modules[mod_name]

    # CRITICAL: purge the cached src package (imported at the top for the
    # splash footer). If it stays cached, lite_app's `from src import config`
    # gets the OLD bundled config even after a successful update — the app
    # reports the old version and keeps prompting for updates forever.
    for _m in [m for m in list(sys.modules)
               if m == 'src' or m.startswith('src.')]:
        del sys.modules[_m]

    # ── Import and run lite_app ──
    try:
        import lite_app
        lite_app.run_lite_application()
    except Exception as e:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Launch Error",
            f"Failed to start NREGA Bot Lite.\n\n{e}\n\n{traceback.format_exc()}"
        )
        sys.exit(1)
