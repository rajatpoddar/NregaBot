# utils.py
import os
import sys
import json
import logging
import re
import shutil
import time
import zipfile
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from appdirs import user_data_dir

# --- C8: Centralized Logging Setup ---

_LOGGER_SETUP_DONE: bool = False

def get_log_path() -> str:
    """Returns the path to the application log file."""
    return os.path.join(get_data_path(), "nregabot.log")

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    C8: Configure centralized logging for the application.
    
    Sets up:
    - File handler: logs everything >= level to nregabot.log in data dir
    - Console handler: logs WARNING+ to stderr for crash visibility
    
    Safe to call multiple times — only configures on first call.
    """
    global _LOGGER_SETUP_DONE
    if _LOGGER_SETUP_DONE:
        return logging.getLogger("nregabot")
    
    logger = logging.getLogger("nregabot")
    logger.setLevel(level)
    logger.handlers.clear()  # Avoid duplicate handlers if re-called

    # --- File Handler (persistent log, rotated at 5MB) ---
    log_path = get_log_path()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=2, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(_PiiMaskingFormatter(
            "%(asctime)s [%(levelname)-5s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(fh)
    except Exception as e:
        # Can't log yet — print as last resort
        print(f"Warning: Could not create log file at {log_path}: {e}")

    # --- Console Handler (WARNING+ only, to avoid cluttering stdout) ---
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(_PiiMaskingFormatter("%(levelname)-8s %(message)s"))
    logger.addHandler(ch)

    _LOGGER_SETUP_DONE = True
    return logger

def _suppress_overscroll(scroll_frame) -> None:
    """Suppress macOS overscroll "bounce" on a CTkScrollableFrame.
    On macOS, trackpad momentum scrolling fires events even after
    content reaches the scroll boundary, causing 1-2s of visible
    rubber-banding/dance. This snaps the canvas back to the boundary
    on every MouseWheel event, instantly killing the bounce.
    """
    if sys.platform != "darwin":
        return
    try:
        canvas = scroll_frame._canvas
        parent_frame = scroll_frame._parent_frame

        def _fix_boundary(_event=None):
            if not canvas.winfo_exists():
                return
            yview = canvas.yview()
            if yview[0] <= 0.0:
                canvas.yview_moveto(0.0)
            if yview[1] >= 1.0:
                canvas.yview_moveto(1.0)

        # Bind AFTER CTk's handler (add="+") so we snap back after
        # any scroll that went past the boundary.
        # Only bind on parent_frame — canvas binding is redundant since
        # CTk's handler is on parent_frame and triggers the canvas scroll.
        parent_frame.bind("<MouseWheel>", _fix_boundary, add="+")
    except Exception:
        pass


def get_logger() -> logging.Logger:
    """Get the application's root logger. Call setup_logging() first."""
    return logging.getLogger("nregabot")


def resource_path(relative_path: str) -> str:
    """ 
    Get absolute path to resource.
    Priority:
    1. PyInstaller Temp Folder (sys._MEIPASS) - Jb exe ban kar chalega
    2. Local Directory - Jb aap development kar rahe honge
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path: str = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    # Normalize path separators for cross-platform compatibility (fixes Windows backslash issues)
    normalized = os.path.normpath(relative_path)
    return os.path.join(base_path, normalized)

def get_data_path(filename: str = "") -> str:
    """Get the path to the application's data directory."""
    app_name = "NREGABot"
    app_author = "PoddarSolutions"
    # Use user_data_dir to find the appropriate platform-specific data directory
    data_dir = user_data_dir(app_name, app_author)
    os.makedirs(data_dir, exist_ok=True)
    # Return the full path to the file or just the directory if no filename is given
    return os.path.join(data_dir, filename)

def get_user_downloads_path() -> str:
    """Returns the default downloads path for the user."""
    return str(Path.home() / "Downloads")


# ── Workcode pattern & truncation ─────────────────────────────────
WORKCODE_PATTERN = re.compile(r'\b(34\d{8}(?:/\w+)+/\d+)\b')

def truncate_workcode(workcode: str) -> str:
    """
    Workcode ke sirf last 6 digits return karta hai.
    
    NREGA workcodes format: 34XXXXXXXXXXXXXX/YYYY-YY/ZZZZZZ
    Sirf last 6 digits (ZZZZZZ) log/store kiya jaata hai privacy ke liye.
    
    Agar input pattern match nahi karta (jaise jobcard number, search key),
    to wapas vahi value return kar deta hai bina truncation ke.
    
    Examples:
        342012345678901/2024-25/123456  → 123456
        342012345678901/2024-25/789012  → 789012
        ABC123  → ABC123  (not a workcode, return as-is)
    """
    if not workcode or not isinstance(workcode, str):
        return workcode or ""
    
    wc = workcode.strip()
    if WORKCODE_PATTERN.match(wc):
        parts = wc.split('/')
        last_part = parts[-1]
        if len(last_part) > 6:
            return last_part[-6:]
        return last_part
    
    # Fallback: check if it looks like a numeric code with digits > 8
    digits = ''.join(c for c in wc if c.isdigit())
    if len(digits) > 8 and not any(c.isalpha() for c in wc if c.isalnum()):
        return digits[-6:]
    
    return wc


def get_nregabot_path(subdir: str = "") -> str:
    """
    Returns a path inside ~/Downloads/NregaBot/{subdir}, creating dirs as needed.
    Ensures ALL user-facing files stay within ~/Downloads/NregaBot/.
    
    Examples:
        get_nregabot_path()              -> ~/Downloads/NregaBot/
        get_nregabot_path("Reports")      -> ~/Downloads/NregaBot/Reports/
        get_nregabot_path("Imports")      -> ~/Downloads/NregaBot/Imports/
        get_nregabot_path("Reports/2026/MB_Report") -> ~/Downloads/NregaBot/Reports/2026/MB_Report/
    """
    base = os.path.join(get_user_downloads_path(), "NregaBot")
    if subdir:
        full = os.path.join(base, subdir)
        os.makedirs(full, exist_ok=True)
        return full
    os.makedirs(base, exist_ok=True)
    return base


def current_financial_year() -> str:
    """Current Indian financial year as 'YYYY-YYYY' (starts 1 April)."""
    from datetime import datetime
    now = datetime.now()
    start = now.year if now.month >= 4 else now.year - 1
    return f"{start}-{start + 1}"


def format_bytes(amount: Any, binary: bool = False) -> str:
    """
    Human-readable byte size formatter.

    Uses the `humanize` package when it is installed; otherwise falls back to
    a built-in formatter so the app NEVER crashes on screens that display
    file sizes (About tab, File Manager) even if `humanize` is missing from
    the PyInstaller bundle.

    Examples:
        format_bytes(0)          -> "0 Bytes"
        format_bytes(1536)       -> "1.5 kB"
        format_bytes(1536, True) -> "1.5 KiB"
    """
    if amount is None:
        amount = 0
    try:
        import humanize
        return humanize.naturalsize(amount, binary=binary)
    except Exception:
        pass
    # --- Fallback (no humanize installed) ---
    try:
        size = float(amount)
    except (TypeError, ValueError):
        return "0 Bytes"
    base = 1024.0 if binary else 1000.0
    units = (["Bytes", "KiB", "MiB", "GiB", "TiB"] if binary
             else ["Bytes", "kB", "MB", "GB", "TB"])
    if size < base:
        return f"{int(size)} Bytes"
    unit_idx = 0
    while size >= base and unit_idx < len(units) - 1:
        size /= base
        unit_idx += 1
    return f"{size:.1f} {units[unit_idx]}"


# ── DPDP Act 2023: PII masking helpers ──────────────────────────
# Rule: Aadhaar number kabhi bhi store/transfer NAHI hota (na local DB, na
# server, na logs, na reports). Cloud/sync boundary par sensitive fields
# (Aadhaar, bank account, IFSC, mobile, jobcard, applicant name) mask ho kar
# jaate hain — server par hamesha non-sensitive metadata hi pahunchta hai.
#
# Local results tree / exported Excel user ke apne PC par rehta hai (user ka
# apna data, office report ke liye) — SERVER ko jaane wale data me masking
# hamesha applied hoti hai.

# NOTE: `[\s-]?` optional separators ki wajah se ye pattern plain 12-digit
# numbers ko bhi match karta hai (alag `\d{12}` regex redundant hai — dono
# client `src/utils.py` aur server `nrega-server/app/pii_mask.py` me identical
# rehna chahiye, drift ho to dono ek saath update karo).
_AADHAAR_SPACED_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
_MOBILE_RE = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

# Sensitive column-name keywords (word-boundary match — "panchayat" me "pan"
# false-positive nahi hota, "filename" me "name" bhi nahi).
_SENSITIVE_COL_KEYWORDS = (
    "aadhaar", "aadhar", "uid", "account", "bank", "ifsc",
    "mobile", "phone", "voter", "pan", "jobcard", "job card",
    "job-card", "bankac", "ac no", "acno", "name",
)


def mask_aadhaar_text(text: str) -> str:
    """12-digit Aadhaar (contiguous ya 4-4-4 spaced) ko XXXX-XXXX-XXXX banao."""
    if not text:
        return text or ""
    return _AADHAAR_SPACED_RE.sub(lambda m: "XXXX-XXXX-XXXX", text)


def mask_pii_text(text: Any) -> str:
    """Kisi bhi string me PII patterns (Aadhaar, mobile, IFSC) mask karo.

    - Aadhaar (12-digit / 4-4-4) → XXXX-XXXX-XXXX
    - Mobile (10-digit, 6-9 se shuru) → 9X******X0
    - IFSC → XXXX0XXXXXX

    Kabhi raise nahi karta — logs/errors/tracebacks me bhi safe.
    """
    if text is None:
        return ""
    s = str(text)
    s = mask_aadhaar_text(s)
    s = _MOBILE_RE.sub(lambda m: m.group(0)[:2] + "******" + m.group(0)[-2:], s)
    s = _IFSC_RE.sub("XXXX0XXXXXX", s)
    return s


class _PiiMaskingFormatter(logging.Formatter):
    """DPDP: formatted output (message + exc_info traceback) me PII mask karo.

    Plain logging.Filter sirf ``record.msg`` ko dekhta hai — exception
    traceback (``exc_info``) Formatter me format hone par filter ke BAAD judta
    hai, isliye Filter usse cover nahi karta. Isliye Formatter-level masking
    FINAL formatted string par hoti hai — message + traceback dono safe
    (``logger.error(msg, exc_info=True)`` bhi). Local nregabot.log + crash
    reporter ke last-log-lines dono isi se safe rehte hain. Kabhi raise nahi
    karta — logging path 100% safe.
    """

    def format(self, record):
        out = super().format(record)
        try:
            return mask_pii_text(out)
        except Exception:
            return out


def _is_sensitive_col(name: Any) -> bool:
    """Column name sensitive hai? (aadhaar/uid/account/mobile/jobcard/name...)"""
    try:
        low = str(name or "").strip().lower()
        if not low:
            return False
        return any(re.search(r"\b" + re.escape(kw) + r"\b", low)
                   for kw in _SENSITIVE_COL_KEYWORDS)
    except Exception:
        return False


def mask_sensitive_col_value(col_name: Any, value: Any) -> str:
    """Sensitive column ka value mask karo.

    - Aadhaar/UID column → XXXX-XXXX-XXXX (full mask)
    - Baaki sensitive columns (account/jobcard/mobile/name...) → ****<last4>
    """
    low = str(col_name or "").lower()
    s = "" if value is None else str(value)
    if not s.strip():
        return s
    if any(k in low for k in ("aadhaar", "aadhar", "uid")):
        return "XXXX-XXXX-XXXX"
    digits = re.sub(r"\D", "", s)
    if digits:
        return "****" + digits[-4:]
    return "****"


def mask_columns_rows(columns: List[str], rows: List[List]) -> tuple:
    """Cloud reports ke liye columns+rows me sensitive data mask karo.

    - Sensitive columns (Aadhaar/UID/account/mobile/jobcard/name...) ke
      values mask hote hain
    - Har cell me accidental 12-digit Aadhaar/mobile pattern bhi mask hota
      hai (column-agnostic leak guard)

    Naya (columns, rows) return karta hai — original lists mutate nahi hoti.
    """
    try:
        if not columns or not rows:
            return columns, rows
        sens_idx = [i for i, c in enumerate(columns) if _is_sensitive_col(c)]
        new_rows = []
        for r in rows:
            nr = list(r)
            for i in sens_idx:
                if i < len(nr):
                    nr[i] = mask_sensitive_col_value(columns[i], nr[i])
            for i in range(len(nr)):
                nr[i] = mask_pii_text(nr[i])
            new_rows.append(nr)
        return columns, new_rows
    except Exception:
        return columns, rows


# ── Error translation (clean English) ──────────────────────────
# Raw Selenium/exception messages → user-friendly English.
# The ORIGINAL exception is always logged for developers.
# This translation is only used in user-facing dialogs.
_ERROR_TRANSLATIONS = [
    # (pattern, translated) — lowercase substring match, first hit wins.
    # Exception class names (no spaces) first — Selenium class names
    # don't have spaces.
    ("staleelementreferenceexception",
     "Could not find the element because the page refreshed. Please try again."),
    ("nosuchwindowexception",
     "Browser tab/window was closed — automation stopped. Reopen the browser and run again."),
    ("nosuchelementexception",
     "Required field not found on the page. Check that the page loaded correctly and try again."),
    ("elementclickinterceptedexception",
     "Could not click the element — a popup or overlay was in the way. Please try again."),
    ("elementnotinteractableexception",
     "Could not click or type into the element — the page was still loading. Please try again."),
    ("elementnotvisibleexception",
     "Element is not visible — the page may still be loading. Please try again."),
    ("invalidselectorexception",
     "Element selector was incorrect — the page layout may have changed. Please try again."),
    ("webdriverexception",
     "A technical error occurred in the browser. Restart the browser and try again."),
    ("no such window",
     "Browser tab/window was closed — automation stopped. Reopen the browser and run again."),
    ("target window already closed",
     "Browser tab was already closed — automation stopped. Reopen the browser and run again."),
    ("web view not found",
     "Browser window not found — restart the browser and try again."),
    ("invalid session id",
     "Browser session was lost — restart the browser and try again."),
    ("element is no longer attached to the dom",
     "The page was reloaded and the element was removed. Please try again."),
    ("stale element",
     "Could not find the element because the page refreshed. Please try again."),
    ("element click intercepted",
     "Could not click the element — a popup or overlay was in the way. Please try again."),
    ("element not interactable",
     "Could not click or type into the element — the page was still loading. Please try again."),
    ("unable to locate element",
     "Required field not found on the page. Check that the page loaded correctly and try again."),
    ("no such element",
     "Required field not found on the page. Check that the page loaded correctly and try again."),
    ("timed out",
     "Page load timed out (slow network or portal is busy). Please try again."),
    ("timeout",
     "Page load timed out (slow network or portal is busy). Please try again."),
    ("connection refused",
     "Could not connect to the portal — check your network/internet and try again."),
    ("max retries exceeded",
     "Internet or portal connection issue — check your network and try again."),
    ("failed to establish a new connection",
     "Internet or portal connection issue — check your network and try again."),
    ("no route to host",
     "Network route not found — internet or portal may be down. Please try again later."),
    ("file not found",
     "File not found — select the correct file and try again."),
    ("permission denied",
     "Permission issue accessing the file/folder — check if the file is open in another program and try again."),
    ("not enough values to unpack",
     "Data format is incorrect — check the file format and try again."),
    ("list index out of range",
     "Data is missing something (possibly an empty row). Check the file and try again."),
    ("attributeerror",
     "An internal error occurred (AttributeError). Update the app to the latest version and try again."),
    ("typeerror",
     "An internal error occurred (TypeError). Update the app to the latest version and try again."),
    ("valueerror",
     "The value provided is invalid — check your inputs and try again."),
]


# ── Crash reporter (uncaught exceptions → crash files) ───────────
_CRASH_REPORTER_INSTALLED: bool = False


def _read_license_key() -> str:
    """license.dat se license key read karo (crash upload payload ke liye).

    Kabhi raise nahi karta — crash path me bhi 100% safe.
    """
    try:
        with open(get_data_path("license.dat"), "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("key") or "").strip()
    except Exception:
        return ""


def _upload_crash_report(payload: dict) -> None:
    """Crash report server par bhejo (daemon thread me — kabhi raise nahi).

    POST /api/crash-report — server-side bhi PII masking + rate limiting hai
    (defense-in-depth). Fail hone par silently ignore — crash path me koi
    network wait ya exception UI ko nahi rok sakta.
    """
    try:
        from src import config
        server_url = (config.LICENSE_SERVER_URL or "").strip().rstrip("/")
        if not server_url.startswith("http"):
            return
        import requests
        requests.post(
            f"{server_url}/api/crash-report",
            json=payload,
            timeout=8,
        )
    except Exception:
        pass

def install_crash_reporter() -> None:
    """
    Global uncaught-exception handler — app crash hone par bhi details save.

    Har crash par ``Temp/crashes/crash_YYYYMMDD_HHMMSS.txt`` banta hai jisme:
      * App version + OS + time
      * Exception type + message
      * Full traceback
      * App log ke last 30 lines (kahan tak pahuncha tha)

    - Additive: purana sys.excepthook chain hota hai (override nahi)
    - Idempotent: do baar install hone par duplicate nahi
    - Kabhi raise nahi karta — crash path me bhi 100% safe
    """
    global _CRASH_REPORTER_INSTALLED
    if _CRASH_REPORTER_INSTALLED:
        return
    _CRASH_REPORTER_INSTALLED = True

    old_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        try:
            import traceback as _tb
            from datetime import datetime as _dt
            from src import config

            now = _dt.now()
            # DPDP: crash file me bhi raw exception message/traceback PII leak
            # nahi karta — Aadhaar/mobile/IFSC redact hoke likha jaata hai.
            lines = [
                f"Time      : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"App       : {config.APP_NAME} v{config.APP_VERSION}",
                f"OS        : {config.OS_SYSTEM}",
                f"Exception : {mask_pii_text(f'{exc_type.__name__}: {exc_value}')}",
                "--- Traceback ---",
                mask_pii_text("".join(_tb.format_exception(exc_type, exc_value, exc_tb))),
            ]

            # App log ke last ~30 lines — crash se pehle kya ho raha tha
            # (ek baar hi read karo — file-write aur server upload dono isi se)
            tail_lines: list = []
            try:
                log_path = get_log_path()
                if os.path.exists(log_path):
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        tail_lines = [mask_pii_text(line.rstrip("\n"))
                                      for line in f.readlines()[-30:]]
                    lines.append("--- Last log lines ---")
                    lines.extend(tail_lines)
            except Exception:
                pass

            crash_dir = get_nregabot_path("Temp/crashes")
            path = os.path.join(crash_dir, f"crash_{now.strftime('%Y%m%d_%H%M%S')}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            get_logger().error("🚨 App crash recorded: %s (%s)", path, exc_type.__name__)

            # ── Server upload (background daemon thread, kabhi raise nahi) ──
            try:
                import threading
                payload = {
                    "license_key": _read_license_key(),
                    "app_version": getattr(config, "APP_VERSION", ""),
                    "os_platform": getattr(config, "OS_SYSTEM", ""),
                    "error_type": getattr(exc_type, "__name__", ""),
                    "error_message": mask_pii_text(str(exc_value)),
                    "error_traceback": mask_pii_text(
                        "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
                    ),
                    "last_log_lines": "\n".join(tail_lines),
                    "crash_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                }
                threading.Thread(
                    target=_upload_crash_report, args=(payload,), daemon=True
                ).start()
            except Exception:
                pass
        except Exception:
            pass

        # Original handler ko chain karo — default stderr traceback preserve
        try:
            if old_hook is not None:
                old_hook(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _hook


def translate_error(error: Any, error_type: str = "") -> str:
    """
    Convert raw exception message → user-friendly English.

    - If a pattern matches, returns a friendly message.
    - If no pattern matches, returns the original message (no data loss).
    - Never raises — 100% safe for the UI thread.

    Args:
        error: exception object or message string
        error_type: optional exception class name (prepended if not already in message)
    """
    try:
        raw = str(error or "")
    except Exception:
        return ""
    if not raw.strip():
        return ""
    low = raw.lower()
    for pattern, translated in _ERROR_TRANSLATIONS:
        if pattern in low:
            return translated
    # No pattern match — return original message (with error_type prefix if provided)
    if error_type and not raw.strip().startswith(error_type):
        return f"{error_type}: {raw.strip()}"
    return raw.strip()


def get_report_path(category: str = "", fin_year: str = "") -> str:
    """
    Standard report directory: ~/Downloads/NregaBot/Report {fin_year}/{category}/

    All report exports (Excel/CSV/PDF/image) should use this so every report
    lands in one consistent place per financial year.

    Examples:
        get_report_path("Pending Bills")              -> ~/Downloads/NregaBot/Report 2026-2027/Pending Bills/
        get_report_path("Pending Bills", "2025-2026") -> ~/Downloads/NregaBot/Report 2025-2026/Pending Bills/
        get_report_path()                              -> ~/Downloads/NregaBot/Report 2026-2027/
    """
    fy = fin_year or current_financial_year()
    subdir = f"Report {fy}"
    if category:
        subdir = os.path.join(subdir, category)
    return get_nregabot_path(subdir)

# --- UPDATED CONFIG FUNCTIONS ---

CONFIG_FILE: str = get_data_path('config.json')

def parse_version(version_str: str) -> tuple:
    """
    A7: Parse a semver-like version string into a comparable tuple of integers.
    Strips pre-release suffixes (e.g. -LITE, -beta, -rc1) for clean comparison.
    Replaces 'packaging.version.parse' to remove the external dependency.
    
    Examples:
        '3.0.7'      -> (3, 0, 7)
        '3.0.7-LITE' -> (3, 0, 7)
        '3.0'        -> (3, 0)
        ''           -> (0,)
    
    Usage:
        if parse_version(latest) > parse_version(config.APP_VERSION):
            # newer version available
    """
    try:
        # Strip pre-release suffix (e.g. 3.0.7-LITE -> 3.0.7)
        clean = version_str.strip().split('-')[0]
        parts = clean.split('.')
        return tuple(int(p) if p.isdigit() else 0 for p in parts)
    except (ValueError, AttributeError):
        return (0,)


def save_license_dat(data: dict) -> None:
    """AUDIT FIX (25 Aug 2026): persist license.dat through ONE choke-point
    with owner-only permissions.

    Why: license.dat holds the raw license key + user PII and was written
    world-readable-per-umask from 7 different call-sites. This helper is now
    the only writer. os.chmod(0o600) is effectively a no-op on Windows
    (Python maps it to the read-only flag; the file stays writable for the
    owner) and enforces owner-only on macOS/Linux. Encoding is explicitly
    utf-8 (keys are ASCII, but explicit beats platform-default). Never
    raises — a permission hiccup must never break activation."""
    path = get_data_path("license.dat")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def validate_config() -> bool:
    """
    Validates the config.json file. If corrupted or unreadable, 
    backs up the old file and creates a fresh default.
    Returns True if valid, False if had to reset.
    """
    logger = get_logger()
    if not os.path.exists(CONFIG_FILE):
        return True  # Will be created by create_default_config_if_not_exists
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        # Basic type check: must be a dict
        if not isinstance(data, dict):
            raise ValueError("Config is not a dict")
        return True
    except (json.JSONDecodeError, IOError, ValueError) as e:
        logger.warning("Config validation failed (%s). Resetting config.", e)
        try:
            # Backup corrupted file
            backup_path = CONFIG_FILE + ".corrupted"
            shutil.copy2(CONFIG_FILE, backup_path)
            logger.info("Backed up corrupted config to %s", backup_path)
        except Exception:
            pass
        # Remove corrupted file so create_default_config_if_not_exists can recreate
        try:
            os.remove(CONFIG_FILE)
        except Exception as e:
            logger.warning("Failed to remove corrupted config file: %s", e)
        return False

def get_config(key: Optional[str] = None, default: Any = None) -> Any:
    """
    Loads the configuration from config.json.
    If a key is provided, it returns the value for that key, otherwise the entire config.
    """
    if not os.path.exists(CONFIG_FILE):
        return {} if key is None else default
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
        if key is None:
            return config_data
        return config_data.get(key, default)
    except (json.JSONDecodeError, IOError):
        return {} if key is None else default

def save_config(key: str, value: Any) -> None:
    """
    Saves a specific key-value pair to the config.json file.
    """
    logger = get_logger()
    config_data = get_config()  # Load the entire current config
    config_data[key] = value   # Update or add the new key-value pair
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        logger.error("Error saving config file: %s", e)


# ============================================================================
# UPDATE ROLLBACK — boot-counter crash detection (shared)
# ============================================================================
# Shared between loader.py / lite_loader.py (record boot attempts, decide when
# to roll back, restore core_prev.zip), services.py (skip known-bad versions in
# the in-app update check) and main_app.py / lite_app.py (mark clean boot once
# the main window is fully rendered).
#
# How it works:
#   1. Right before launching the app, the loader records a boot attempt in
#      boot_state.json: {attempts+1, version launched, timestamp}.
#   2. The app deletes boot_state.json ONLY after its main window is fully
#      rendered (mark_clean_boot). A crash during startup leaves the file.
#   3. If MAX_BOOT_ATTEMPTS consecutive launches crash within the boot window,
#      the loader restores core_prev.zip (the version installed before the
#      update) and records the crashed version in bad_versions.json so the
#      update check skips it until a NEWER version ships.
#
# All functions are defensive (never raise) — the update path must never crash.

MAX_BOOT_ATTEMPTS = 3
BOOT_CRASH_WINDOW_SECONDS = 600  # 10 min — a stale crash from days ago doesn't count


def get_core_zip_path() -> str:
    """Path of the currently-installed core.zip (same dir as core_version.json)."""
    return get_data_path("core.zip")


def get_core_prev_zip_path() -> str:
    """Path of the previous core.zip kept for rollback."""
    return get_data_path("core_prev.zip")


def get_core_prev_meta_path() -> str:
    """{version, hash} of core_prev.zip, written when it was kept."""
    return get_data_path("core_prev_meta.json")


def get_core_version_file_path() -> str:
    """Path of core_version.json (recorded version + hash of the app_live code)."""
    return get_data_path("core_version.json")


def get_boot_state_path() -> str:
    return get_data_path("boot_state.json")


def get_bad_versions_path() -> str:
    return get_data_path("bad_versions.json")


def _load_json_file(path: str, default: Any = None) -> Any:
    """Read JSON from disk; returns `default` on any failure. Never raises."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json_file(path: str, data: Any) -> None:
    """Atomically-ish write JSON to disk; never raises."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _sha256_file(path: str) -> str:
    """Streaming SHA-256 of a file — safe for large zips. '' on failure."""
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def read_boot_state() -> Dict[str, Any]:
    """boot_state.json contents ({attempts, version, ts}) or {}."""
    state = _load_json_file(get_boot_state_path(), {})
    return state if isinstance(state, dict) else {}


def record_boot_attempt(version: str = "") -> Dict[str, Any]:
    """Loader calls this right before launching the app.

    Increments the consecutive-crash counter (reset if the previous crash is
    older than BOOT_CRASH_WINDOW_SECONDS) and records the launched version.
    Returns the new state.
    """
    state = read_boot_state()
    attempts = 0
    ts = state.get("ts")
    if ts:
        try:
            if time.time() - float(ts) <= BOOT_CRASH_WINDOW_SECONDS:
                attempts = int(state.get("attempts") or 0)
        except Exception:
            attempts = 0
    new_state = {"attempts": attempts + 1, "version": version or "", "ts": time.time()}
    _save_json_file(get_boot_state_path(), new_state)
    return new_state


def reset_boot_state(version: str = "") -> None:
    """Zero the boot counter (used after a rollback / when rollback is impossible)."""
    _save_json_file(get_boot_state_path(), {"attempts": 0, "version": version or "", "ts": time.time()})


def should_rollback_boot() -> bool:
    """True when the last MAX_BOOT_ATTEMPTS launches all crashed before the app
    could mark a clean boot — i.e. the current install is crash-looping."""
    state = read_boot_state()
    if int(state.get("attempts") or 0) < MAX_BOOT_ATTEMPTS:
        return False
    ts = state.get("ts")
    if ts:
        try:
            if time.time() - float(ts) > BOOT_CRASH_WINDOW_SECONDS:
                return False  # stale — not an active crash loop
        except Exception:
            return False
    return True


def mark_clean_boot(app_version: str = "") -> None:
    """App calls this once its main window is fully rendered — the signal that
    startup succeeded. Resets the boot counter and, if a version newer than the
    last known-bad one booted cleanly, clears the bad-version floor. Safe to
    call in dev mode (no boot state exists there); never raises."""
    try:
        path = get_boot_state_path()
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    try:
        bad_path = get_bad_versions_path()
        data = _load_json_file(bad_path, {})
        max_bad = data.get("max_bad") or ""
        if max_bad and app_version and parse_version(app_version) > parse_version(max_bad):
            if os.path.exists(bad_path):
                os.remove(bad_path)
    except Exception:
        pass


def is_bad_version(version: str) -> bool:
    """True if `version` (or anything older) crash-looped and was rolled back.
    The update check must not offer it again until a newer release ships."""
    if not version:
        return False
    data = _load_json_file(get_bad_versions_path(), {})
    max_bad = data.get("max_bad") or ""
    if not max_bad:
        return False
    try:
        return parse_version(version) <= parse_version(max_bad)
    except Exception:
        return False


def remember_bad_version(version: str) -> None:
    """Record the crashed version as the new 'known bad' floor (monotonic —
    only ever raised, so a newer good release can boot past it)."""
    if not version:
        return
    try:
        path = get_bad_versions_path()
        data = _load_json_file(path, {})
        if not isinstance(data, dict):
            data = {}
        cur = data.get("max_bad") or ""
        if not cur or parse_version(version) > parse_version(cur):
            data["max_bad"] = version
            _save_json_file(path, data)
    except Exception:
        pass


def promote_current_zip_to_prev() -> bool:
    """Keep the currently-installed core.zip as core_prev.zip BEFORE a new
    download overwrites it, so a crash-looping update can be rolled back.
    Records the installed version+hash in core_prev_meta.json so the rollback
    restores core_version.json correctly. Only promotes when the current zip
    looks like the one actually installed (or hashes can't be verified).
    Returns True if a prev copy was made."""
    try:
        zip_path = get_core_zip_path()
        if not os.path.exists(zip_path):
            return False
        if not zipfile.is_zipfile(zip_path):
            return False
        recorded_ver = ""
        recorded_hash = ""
        vf = get_core_version_file_path()
        if os.path.exists(vf):
            try:
                vd = _load_json_file(vf, {})
                if isinstance(vd, dict):
                    recorded_ver = vd.get("version", "") or ""
                    recorded_hash = vd.get("hash", "") or ""
            except Exception:
                pass
        # Only keep the zip as 'previous' if it matches what we actually
        # installed (a partial download must never become the rollback target).
        if recorded_hash:
            actual = _sha256_file(zip_path)
            if actual and actual != recorded_hash:
                return False
        shutil.copy2(zip_path, get_core_prev_zip_path())
        _save_json_file(get_core_prev_meta_path(), {"version": recorded_ver, "hash": recorded_hash})
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════
#  APP CONTROL — Server-driven emergency controls
#  (Maintenance Mode, Force Rollback, Blocked Versions)
# ═══════════════════════════════════════════════════════════════════════

def get_force_rollback_path() -> str:
    """Path of force_rollback.json — set by the client heartbeat when the
    server signals a forced rollback; read by loader.py on next launch."""
    return get_data_path("force_rollback.json")


def save_force_rollback(data: dict) -> None:
    """Persist a force-rollback signal from the server."""
    _save_json_file(get_force_rollback_path(), data)


def read_force_rollback() -> dict:
    """Read the force-rollback signal; returns {} if none."""
    data = _load_json_file(get_force_rollback_path(), {})
    return data if isinstance(data, dict) else {}


def clear_force_rollback() -> None:
    """Remove the force-rollback signal after it has been acted on."""
    try:
        path = get_force_rollback_path()
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def get_blocked_versions_path() -> str:
    """Path of blocked_versions.json — synced from server, checked by loader."""
    return get_data_path("blocked_versions.json")


def save_blocked_versions(versions: list) -> None:
    """Persist the blocked-versions list from the server."""
    _save_json_file(get_blocked_versions_path(), {"versions": versions})


def read_blocked_versions() -> list:
    """Read blocked versions list; returns [] if none."""
    data = _load_json_file(get_blocked_versions_path(), {})
    versions = data.get("versions") if isinstance(data, dict) else None
    return versions if isinstance(versions, list) else []
