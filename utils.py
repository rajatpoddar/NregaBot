# utils.py
import os
import sys
import json
import logging
from pathlib import Path
from appdirs import user_data_dir

# --- C8: Centralized Logging Setup ---

_LOGGER_SETUP_DONE = False

def get_log_path():
    """Returns the path to the application log file."""
    return os.path.join(get_data_path(), "nregabot.log")

def setup_logging(level=logging.INFO):
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

def get_logger():
    """Get the application's root logger. Call setup_logging() first."""
    return logging.getLogger("nregabot")


def resource_path(relative_path):
    """ 
    Get absolute path to resource.
    Priority:
    1. PyInstaller Temp Folder (sys._MEIPASS) - Jb exe ban kar chalega
    2. Local Directory - Jb aap development kar rahe honge
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    # Normalize path separators for cross-platform compatibility (fixes Windows backslash issues)
    normalized = os.path.normpath(relative_path)
    return os.path.join(base_path, normalized)

def get_data_path(filename=""):
    """Get the path to the application's data directory."""
    app_name = "NREGABot"
    app_author = "PoddarSolutions"
    # Use user_data_dir to find the appropriate platform-specific data directory
    data_dir = user_data_dir(app_name, app_author)
    os.makedirs(data_dir, exist_ok=True)
    # Return the full path to the file or just the directory if no filename is given
    return os.path.join(data_dir, filename)

def get_user_downloads_path():
    """Returns the default downloads path for the user."""
    return str(Path.home() / "Downloads")

# --- UPDATED CONFIG FUNCTIONS ---

CONFIG_FILE = get_data_path('config.json')

def validate_config():
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
            import shutil
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

def get_config(key=None, default=None):
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

def save_config(key, value):
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