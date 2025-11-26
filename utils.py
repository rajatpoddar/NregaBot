# utils.py
import os
import sys
import json
from pathlib import Path
from appdirs import user_data_dir

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
    
    return os.path.join(base_path, relative_path)

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
    config_data = get_config()  # Load the entire current config
    config_data[key] = value   # Update or add the new key-value pair
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        print(f"Error saving config file: {e}")