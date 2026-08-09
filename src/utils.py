# utils.py
import os
import sys
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, List, Optional
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


# ── Error translation (user-friendly Hinglish) ───────────────────
# India-level UX: raw Selenium/exception messages ko aam users nahi
# samajhte. translate_error() generic errors ka friendly Hinglish deta hai.
# NOTE: Developer/admin ke liye ORIGINAL message hamesha log hota rehta
# hai — ye translation sirf user-facing text/dialog me use hota hai.
_ERROR_TRANSLATIONS = [
    # (pattern, translated) — lowercase substring match, first hit wins.
    # Exception class names (bina space) pehle rakhe hain — Selenium ke
    # class names me spaces nahi hote.
    ("staleelementreferenceexception",
     "Page refresh hone ki wajah se element milne me problem hui. Retry karein."),
    ("nosuchwindowexception",
     "Browser tab/window band ho gaya — automation ruk gaya. Browser dobara kholkar run karein."),
    ("nosuchelementexception",
     "Page par required field nahi mila. Page sahi se khula hai confirm karke Retry karein."),
    ("elementclickinterceptedexception",
     "Element click block hua — koi popup/overlay chalu tha. Retry karein."),
    ("elementnotinteractableexception",
     "Element click/type nahi ho paya — page abhi load ho raha tha. Retry karein."),
    ("elementnotvisibleexception",
     "Element dikh nahi raha — page abhi load ho raha tha. Retry karein."),
    ("invalidselectorexception",
     "Element selector galat mila — page layout badla ho sakta hai. Retry karein."),
    ("webdriverexception",
     "Browser me technical problem aayi. Browser restart karke Retry karein."),
    ("no such window",
     "Browser tab/window band ho gaya — automation ruk gaya. Browser dobara kholkar run karein."),
    ("target window already closed",
     "Browser tab band ho gaya tha — automation ruk gaya. Browser dobara kholkar run karein."),
    ("web view not found",
     "Browser window nahi mili — browser restart karke dobara try karein."),
    ("invalid session id",
     "Browser session lost ho gaya — browser restart karke dobara try karein."),
    ("element is no longer attached to the dom",
     "Page reload hone ki wajah se purana element hat gaya. Retry karein."),
    ("stale element",
     "Page refresh hone ki wajah se element milne me problem hui. Retry karein."),
    ("element click intercepted",
     "Element click block hua — koi popup/overlay chalu tha. Retry karein."),
    ("element not interactable",
     "Element click/type nahi ho paya — page abhi load ho raha tha. Retry karein."),
    ("unable to locate element",
     "Page par required field nahi mila. Page sahi se khula hai confirm karke Retry karein."),
    ("no such element",
     "Page par required field nahi mila. Page sahi se khula hai confirm karke Retry karein."),
    ("timed out",
     "Page load me time lag gaya (slow network ya portal busy). Retry karein."),
    ("timeout",
     "Page load me time lag gaya (slow network ya portal busy). Retry karein."),
    ("connection refused",
     "Portal se connect nahi ho paya — network/internet check karke Retry karein."),
    ("max retries exceeded",
     "Internet/portal connection me problem — network check karke Retry karein."),
    ("failed to establish a new connection",
     "Internet/portal connection me problem — network check karke Retry karein."),
    ("no route to host",
     "Network route nahi mila — internet ya portal down ho sakta hai. Baad me try karein."),
    ("file not found",
     "File nahi mili — sahi file select karke dobara try karein."),
    ("permission denied",
     "File/folder access me permission problem — file khuli to nahi hai? Check karke Retry karein."),
    ("not enough values to unpack",
     "Data format sahi nahi mila — file ka format check karke Retry karein."),
    ("list index out of range",
     "Data me kuch missing hai (empty row ho sakti hai). File check karke Retry karein."),
    ("attributeerror",
     "Internal issue aaya (AttributeError). App ko latest version me update karke Retry karein."),
    ("typeerror",
     "Internal issue aaya (TypeError). App ko latest version me update karke Retry karein."),
    ("valueerror",
     "Diyi gayi value galat hai — inputs check karke Retry karein."),
]


# ── Crash reporter (uncaught exceptions → crash files) ───────────
_CRASH_REPORTER_INSTALLED: bool = False

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
            try:
                log_path = get_log_path()
                if os.path.exists(log_path):
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        tail = f.readlines()[-30:]
                    lines.append("--- Last log lines ---")
                    lines.extend(mask_pii_text(line.rstrip("\n")) for line in tail)
            except Exception:
                pass

            crash_dir = get_nregabot_path("Temp/crashes")
            path = os.path.join(crash_dir, f"crash_{now.strftime('%Y%m%d_%H%M%S')}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            get_logger().error("🚨 App crash recorded: %s (%s)", path, exc_type.__name__)
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
    Raw exception message → user-friendly Hinglish.

    - Match hone par friendly message return hota hai
    - Match NAHI hone par original message wapas (koi data loss nahi)
    - Kabhi raise nahi karta — UI thread ke liye 100% safe

    Args:
        error: exception ya message string
        error_type: optional exception class name (message me nahi hai to prefix)
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
    # No pattern match — original message wapas (error_type prefix ke saath)
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
