import sys
import os
import time
import hashlib
import re
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
# Rollback helpers — boot-counter crash detection + core_prev.zip management.
# Shared with main_app.py / services.py via src/utils.py.
from src.utils import (
    record_boot_attempt,
    reset_boot_state,
    should_rollback_boot,
    promote_current_zip_to_prev,
    is_bad_version,
    remember_bad_version,
    read_boot_state,
    get_core_prev_zip_path,
    get_core_prev_meta_path,
    # App Control — server-driven emergency controls
    read_force_rollback,
    clear_force_rollback,
    read_blocked_versions,
)

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

        # Pending update version/hash — recorded into core_version.json ONLY
        # after a successful extraction (see extract_zip). The old loader wrote
        # the version file BEFORE extracting; if extraction then failed, the app
        # permanently believed it was already updated while actually running
        # old code ("stuck state" — version matches server so no re-download).
        self._pending_version = None
        self._pending_hash = ""

        # Boot-counter flag: True in production (record a boot attempt before
        # launching the app so a crash-looping update can be rolled back),
        # False in dev mode (running from source — no update/rollback logic).
        self._boot_state_enabled = False

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
    #  BUSINESS LOGIC
    # ------------------------------------------------------------------

    def _read_version_file(self):
        """Read (version, hash) from core_version.json; default ('0.0.0', '')."""
        try:
            if os.path.exists(VERSION_FILE):
                with open(VERSION_FILE, 'r') as f:
                    data = json.load(f)
                    return (data.get('version', '0.0.0'), data.get('hash', '') or '')
        except Exception:
            pass
        return ('0.0.0', '')

    def _write_version_file(self, version, hash_val):
        try:
            with open(VERSION_FILE, 'w') as f:
                json.dump({"version": version, "hash": hash_val}, f)
        except Exception as e:
            log_error(f"Failed to write version file: {e}")

    def _get_app_live_version(self) -> str:
        """Actual version baked into the extracted code (app_live/src/config.py).

        Returns '' if app_live isn't extracted yet. Used by the HEAL logic to
        detect the stuck state where core_version.json claims a version the
        extracted code doesn't actually have.

        Windows core zips (built by GitHub Actions CI) ship COMPILED .pyc
        files only — every .py source file is stripped out — so src/config.py
        does NOT exist there. In that case the version is read out of
        src/config.pyc instead (see _read_version_from_pyc). Without this
        fallback the loader could never match the server version on Windows
        and re-downloaded + re-extracted the core zip on EVERY launch.
        """
        cfg_path = os.path.join(EXTRACTED_DIR, "src", "config.py")
        pyc_path = os.path.join(EXTRACTED_DIR, "src", "config.pyc")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped.startswith("APP_VERSION:") or stripped.startswith("APP_VERSION ="):
                            val = stripped.split("=", 1)[1].split("=")[-1].strip()
                            return val.strip('"').strip("'").replace("-LITE", "").replace("-lite", "").strip()
            except Exception:
                pass
            # config.py exists but APP_VERSION couldn't be read from it — fall
            # through to the compiled config.pyc before giving up (defensive).

        # Windows: compiled-only core zip → parse the marshalled config.pyc.
        if os.path.exists(pyc_path):
            return self._read_version_from_pyc(pyc_path)
        return ""

    def _read_version_from_pyc(self, pyc_path: str) -> str:
        """Read APP_VERSION out of a compiled src/config.pyc (Windows core zip).

        Legacy .pyc files are a short header followed by the marshalled code
        object. The header is 8 bytes for Python 3.0-3.2, 12 for 3.3-3.6, and
        16 for 3.7+ (both the timestamp and hash-based forms are 16 bytes);
        CI builds with compileall(legacy=True) produce the 12-byte form. We
        try each known header size and scan the code object's constants for
        the first semver-looking string — that is APP_VERSION.
        """
        try:
            import marshal
            with open(pyc_path, 'rb') as f:
                data = f.read()
            for header_len in (12, 16, 20, 8):
                try:
                    code = marshal.loads(data[header_len:])
                except Exception:
                    continue
                for const in getattr(code, 'co_consts', ()):
                    if isinstance(const, str):
                        v = const.replace("-LITE", "").replace("-lite", "").strip()
                        if re.match(r'^\d+\.\d+\.\d+', v):
                            return v
        except Exception:
            pass
        return ""

    def _heal_install(self) -> None:
        """Repair a stuck update state.

        Old loader versions wrote core_version.json BEFORE extracting the zip.
        If extraction then failed, the version file claimed the new version
        while the app kept running old code — and because the recorded version
        matched the server, the update was never attempted again.

        Here we detect that mismatch (recorded version != actual code version
        in app_live) and re-extract from the already-downloaded, hash-verified
        core.zip. If core.zip is missing or corrupt, check_for_updates() will
        re-download it because it compares against the LIVE code version too.
        """
        try:
            recorded_ver, recorded_hash = self._read_version_file()
            if recorded_ver == "0.0.0" or not recorded_hash:
                return

            live_ver = self._get_app_live_version()
            if live_ver and live_ver == recorded_ver:
                return  # code and record agree — nothing to heal

            if not os.path.exists(CORE_ZIP_PATH):
                return  # nothing to extract from; check_for_updates re-downloads

            zip_hash = sha256_file(CORE_ZIP_PATH)
            if not zip_hash or zip_hash != recorded_hash:
                return  # zip doesn't match the recorded version — re-download instead

            self.update_status("Repairing installation...", -1)
            if self.extract_zip():
                self._write_version_file(recorded_ver, recorded_hash)
                log_error(f"Heal: re-extracted core.zip (v{recorded_ver}) after detecting version-file/code mismatch")
        except Exception as e:
            log_error(f"Heal install failed: {e}")

    def extract_zip(self):
        """Safe extraction of core.zip to EXTRACTED_DIR. Returns True on success.

        The version file is written ONLY after a successful extraction — the old
        behaviour recorded the new version before extracting, so a failed
        extraction permanently stranded users on old code (version file matched
        the server and the update was never attempted again).
        """
        try:
            self.update_status("Extracting files...", -1)

            # Validate the zip BEFORE touching the existing EXTRACTED_DIR — a
            # corrupt download ("File is not a zip file") must never destroy
            # the last working copy of the app; otherwise a failed extraction
            # would leave the user with NO runnable app at all.
            if not zipfile.is_zipfile(CORE_ZIP_PATH):
                log_error("Extraction Failed: core.zip is not a valid zip file")
                self.update_status("Extraction Error: corrupt update file", 0)
                time.sleep(2)
                return False

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

            # Only record the new version AFTER extraction succeeded.
            if self._pending_version:
                self._write_version_file(self._pending_version, self._pending_hash)
                self._pending_version = None
                self._pending_hash = ""

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
                self._boot_state_enabled = False
                self.update_status("Dev Mode: Skipping Updates", 1.0)
                time.sleep(0.5)
                self.after(0, self.launch_main_app)
                return

            # --- PROD MODE ---
            self._boot_state_enabled = True

            # ── MAINTENANCE MODE ───────────────────────────────────────
            # Server-driven kill switch: if admin enabled maintenance mode,
            # show message and exit immediately. Check server API directly
            # (fast, 3s timeout) — don't rely only on the local file which
            # may be stale.
            maintenance_msg = None
            try:
                resp = requests.get(
                    f"{config.LICENSE_SERVER_URL}/api/app-config",
                    timeout=3,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    mm = data.get("maintenance_mode")
                    if isinstance(mm, dict) and mm.get('enabled'):
                        maintenance_msg = mm.get('message', 'App is under maintenance.')
            except Exception:
                pass
            # Fallback: local file (heartbeat writes this)
            if not maintenance_msg:
                try:
                    from src.utils import get_data_path
                    mm_data_path = get_data_path("maintenance_mode.json")
                    if os.path.exists(mm_data_path):
                        with open(mm_data_path, 'r') as f:
                            mm = json.load(f)
                        if isinstance(mm, dict) and mm.get('enabled'):
                            maintenance_msg = mm.get('message', 'App is under maintenance.')
                except Exception:
                    pass
            if maintenance_msg:
                self.update_status(f"🔧 {maintenance_msg}", -1)
                log_error(f"Maintenance mode: {maintenance_msg}")
                time.sleep(5)
                self.after(0, self.destroy)
                return

            # ── SERVER-TRIGGERED ROLLBACK ──────────────────────────────
            # If the server signaled a forced rollback (admin pressed the
            # button), restore core_prev.zip BEFORE any update logic.
            try:
                rb = read_force_rollback()
                target_ver = rb.get('target_version', '')
                if target_ver:
                    msg = rb.get('message', '') or f"Rolling back to v{target_ver}..."
                    self.update_status(f"🔄 {msg}", -1)
                    log_error(f"Force rollback: {msg}")
                    if self._rollback_to_previous(target_ver):
                        log_error(f"Force rollback: restored v{target_ver}")
                    else:
                        log_error(f"Force rollback: could not restore v{target_ver}")
                    clear_force_rollback()
            except Exception:
                pass

            # ── CRASH-LOOP ROLLBACK ──────────────────────────────────────
            # If the last few launches all crashed before the app could mark a
            # clean boot (see mark_clean_boot in main_app.py), the current
            # install is broken. Restore the previous version BEFORE any update
            # logic runs, so a bad update is never re-downloaded / re-extracted
            # (that would loop forever).
            if should_rollback_boot():
                state = read_boot_state()
                crashed_version = str(state.get("version") or "")
                self.update_status("Repeated startup failure — restoring previous version...", -1)
                if self._rollback_to_previous(crashed_version):
                    log_error(f"Rollback: boot-loop detected on v{crashed_version}, restored previous version")
                else:
                    # No previous version to restore (or it failed) — don't
                    # count forever; fall through to the normal flow.
                    log_error("Rollback: boot-loop detected but no previous version could be restored")
                    reset_boot_state(crashed_version)
                    time.sleep(1)

            if os.path.exists(CORE_ZIP_PATH) and not os.path.exists(EXTRACTED_DIR):
                self.extract_zip()

            # HEAL: a previous run may have recorded a version in
            # core_version.json WITHOUT successfully extracting it (old bug:
            # the version file was written before extraction). If the recorded
            # version doesn't match the actual code in app_live, re-extract
            # from the already-downloaded core.zip so the app doesn't stay
            # stuck on old code forever.
            self._heal_install()

            update_found = self.check_for_updates()

            if update_found:
                if not self.extract_zip():
                    # Extraction of the new version failed (corrupt/partial
                    # download, disk issue) — try to restore the previous
                    # version right away instead of launching a possibly-broken
                    # app_live. The boot-counter path would catch this on the
                    # next launch anyway; doing it now avoids the crash loop.
                    log_error("Rollback: extraction of new update failed — restoring previous version")
                    self._rollback_to_previous("")

            self.update_status("Launching application...", 1.0)
            time.sleep(0.5)
            self.after(0, self.launch_main_app)

        except Exception as e:
            log_error(f"Update Process Error: {e}")
            self.update_status(f"Error: {str(e)}", 0)
            time.sleep(2)
            self.after(0, self.launch_main_app)

    def _rollback_to_previous(self, crashed_version: str = "") -> bool:
        """Restore core_prev.zip (the version installed before the crash-looping
        update) as the live app and record the crashed version as 'bad' so the
        update check skips it until a newer release ships.

        Returns True on success. Never raises.
        """
        try:
            prev_zip = get_core_prev_zip_path()
            if not os.path.exists(prev_zip):
                log_error("Rollback: no core_prev.zip available — nothing to restore")
                return False
            if not zipfile.is_zipfile(prev_zip):
                log_error("Rollback: core_prev.zip is corrupt — cannot restore")
                return False

            prev_meta = {}
            try:
                with open(get_core_prev_meta_path(), 'r', encoding='utf-8') as f:
                    prev_meta = json.load(f)
            except Exception:
                prev_meta = {}
            prev_ver = str(prev_meta.get("version") or "")
            prev_hash = str(prev_meta.get("hash") or "")
            # Only a real-looking version string may be written to
            # core_version.json; otherwise it is derived from the extracted
            # code after extraction (same approach as _heal_install).
            prev_ver_valid = bool(re.match(r'^\d+\.\d+\.\d+', prev_ver))

            # Swap the current zip back so the app_live gets the old code.
            try:
                shutil.copy2(prev_zip, CORE_ZIP_PATH)
            except Exception as e:
                log_error(f"Rollback: could not restore core.zip: {e}")
                return False

            self.update_status("Restoring previous version...", -1)
            self._pending_version = prev_ver if prev_ver_valid else None
            self._pending_hash = prev_hash
            if not self.extract_zip():
                log_error("Rollback: extraction of previous version failed")
                return False

            if not prev_ver_valid:
                live = self._get_app_live_version()
                if live:
                    self._write_version_file(live, prev_hash)

            restored_ver = prev_ver if prev_ver_valid else (self._get_app_live_version() or "")

            # Never re-offer the version that just crash-looped.
            if crashed_version:
                remember_bad_version(crashed_version)
                log_error(f"Rollback: marked v{crashed_version} as bad — updates to it will be skipped")

            reset_boot_state(restored_ver)
            log_error(f"Rollback: restored previous version {restored_ver or '(unknown)'}")
            return True
        except Exception as e:
            log_error(f"Rollback failed: {e}")
            return False

    def check_for_updates(self):
        try:
            self.update_status("Checking for updates...", -1)

            current_ver, current_hash = self._read_version_file()
            live_ver = self._get_app_live_version()
            # Compare against the ACTUAL code version in app_live, not just the
            # recorded version file. If a previous update recorded a newer
            # version without successfully extracting it, the version file alone
            # would say "up to date" while old code runs — so the live code
            # version is authoritative for deciding whether an update is needed.
            # When NO code version can be read at all (missing/partial app_live
            # after a failed extraction), treat the install as empty — never let
            # the recorded version make us think we're up to date (that is the
            # permanent-stuck trap).
            if live_ver:
                effective_ver = live_ver
            else:
                effective_ver = "0.0.0"

            headers = {'User-Agent': 'NREGABot-Loader/1.0', 'Cache-Control': 'no-cache'}
            try:
                # Timeout 20s — Cloudflare + Zero-Trust tunnel latency can push
                # the version.json response past 5s; a too-tight timeout made the
                # update check silently fail (looked like "no update available").
                resp = requests.get(UPDATE_URL, headers=headers, timeout=20)
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

            # ── Known-bad version skip (rollback guard) ──
            # A version that crash-looped and was rolled back must not be
            # re-offered; only a strictly NEWER release clears it (see
            # remember_bad_version / is_bad_version in src/utils.py).
            if is_bad_version(server_ver):
                log_error(f"Rollback: skipping update to v{server_ver} (known bad — waiting for a newer release)")
                self.update_status("App is up to date.", 1.0)
                time.sleep(0.5)
                return False

            # ── Admin-blocked version skip ──
            # Server admin blocked this version (dangerous release, etc.).
            blocked = read_blocked_versions()
            if blocked and server_ver in blocked:
                log_error(f"Blocked: skipping update to v{server_ver} (admin blocked)")
                self.update_status("App is up to date.", 1.0)
                time.sleep(0.5)
                return False

            # Update if the version changed OR the core zip content changed
            # (same-version hotfix: same version number, new hash → re-download).
            # Version is compared against the LIVE code (see effective_ver).
            needs_update = (server_ver != effective_ver) or (server_hash and server_hash != current_hash)

            if needs_update:
                # Keep the currently-installed zip as core_prev.zip BEFORE the
                # download overwrites it, so a crash-looping update can be
                # rolled back (see _rollback_to_previous).
                try:
                    promote_current_zip_to_prev()
                except Exception:
                    pass

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

                # Do NOT write the version file here — extract_zip() records it
                # only AFTER a successful extraction. Writing it before
                # extraction is the old bug that stranded users on old code.
                self._pending_version = server_ver
                self._pending_hash = server_hash

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
        # ── Boot-counter: record this launch attempt BEFORE the app starts. ──
        # main_app.py deletes boot_state.json only after a successful startup
        # (mark_clean_boot). If the app crashes first, the counter survives and
        # the NEXT launch may roll back to the previous version instead of
        # crash-looping forever. Production only — dev runs skip this.
        if self._boot_state_enabled:
            try:
                record_boot_attempt(self._get_app_live_version())
            except Exception:
                pass

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

        # CRITICAL: purge the ENTIRE src package (and every src.* submodule)
        # that this loader imported at the top for its splash screen
        # (from src import config). If left cached, main_app's own
        # `from src import config` reuses the BUNDLED src — which still has
        # the OLD APP_VERSION after a smart update — so the app reports the
        # old version and keeps showing "update available" popups forever.
        for _m in [m for m in list(sys.modules)
                   if m == 'src' or m.startswith('src.')]:
            del sys.modules[_m]

        # ── Boot-counter (headless, production only) ──
        # Same as the splash path: record the launch attempt before starting
        # the app so a crash-looping update can be rolled back on the next
        # launch. Skipped in dev mode (running from the source tree).
        try:
            from src import config as _cfg
            from src.utils import record_boot_attempt
            if not os.path.exists(os.path.join(os.path.abspath("."), "main_app.py")):
                record_boot_attempt(getattr(_cfg, "APP_VERSION", ""))
        except Exception:
            pass

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
            # Same src purge as the UI branch — otherwise main_app reuses the
            # loader's cached (bundled) src and reports the old version.
            for _m in [m for m in list(sys.modules)
                       if m == 'src' or m.startswith('src.')]:
                del sys.modules[_m]
            import main_app
            main_app.run_application()
        except ImportError as e:
            print(f"Critical Error: {e}")
