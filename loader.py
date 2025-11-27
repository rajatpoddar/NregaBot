import sys
import os
import requests
import zipfile
import json
import shutil
from appdirs import user_data_dir

# App Config
APP_NAME = "NREGABot"

# --- CHANGE 1: Correct URL (Static JSON file) ---
# Yahan 'your-server.com' ki jagah apna domain dalein jahan version.json hosted hai
UPDATE_URL = "https://nregabot.com/version.json" 

LOCAL_DIR = user_data_dir(APP_NAME, "PoddarSolutions")
CORE_ZIP_PATH = os.path.join(LOCAL_DIR, "core.zip")
VERSION_FILE = os.path.join(LOCAL_DIR, "core_version.json")

def check_for_updates():
    try:
        # 1. Local Version Check
        current_ver = "0.0.0"
        if os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, 'r') as f:
                    current_ver = json.load(f).get('version', "0.0.0")
            except: pass

        # 2. Server Check
        headers = {'User-Agent': 'NREGABot-Loader/1.0', 'Cache-Control': 'no-cache'}
        print(f"Checking updates at: {UPDATE_URL}")
        
        try:
            resp = requests.get(UPDATE_URL, headers=headers, timeout=10)
            data = resp.json()
        except Exception as e:
            print(f"Update check failed (Network/JSON): {e}")
            return False
        
        # 3. Get OS Specific URL
        core_data = data.get('core_update', {})
        server_ver = core_data.get('version')
        
        # OS Detection Logic
        download_url = None
        if sys.platform == "win32":
            download_url = core_data.get('url_windows')
        elif sys.platform == "darwin": # macOS
            download_url = core_data.get('url_macos')
            
        # Fallback to generic URL if specific not found
        if not download_url:
            download_url = core_data.get('url')

        if not server_ver or not download_url:
            print("No update URL found for this OS.")
            return False

        if server_ver != current_ver:
            print(f"Downloading update {server_ver} for {sys.platform}...")
            r = requests.get(download_url, headers=headers, stream=True)
            with open(CORE_ZIP_PATH, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
            
            with open(VERSION_FILE, 'w') as f:
                json.dump({"version": server_ver}, f)
            return True
            
    except Exception as e:
        print(f"Update check error: {e}")
    
    return False

def launch_app():
    check_for_updates()

    if os.path.exists(CORE_ZIP_PATH):
        sys.path.insert(0, CORE_ZIP_PATH)
    
    try:
        # .pyc files are automatically handled by import if in sys.path
        import main_app 
        main_app.run_application()
    except ImportError as e:
        print(f"Critical Error: {e}")
        # Agar magic number error aaye, to user ko batayein
        if "bad magic number" in str(e):
            print("\nERROR: Python Version Mismatch!")
            print("Server se jo .pyc file aayi hai wo alag Python version ki hai.")
            print(f"Current System Python: {sys.version.split()[0]}")

if __name__ == "__main__":
    launch_app()