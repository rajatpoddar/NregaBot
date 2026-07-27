# utils.py
import os
import sys
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Optional
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
        fh.setFormatter(logging.Formatter(
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
    ch.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
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
