import sys
import os
import requests
import zipfile
import importlib
import json
import shutil
from appdirs import user_data_dir

# App Config
APP_NAME = "NREGABot"
UPDATE_URL = "https://your-server.com/api/get-latest-core" # Aapka API endpoint
LOCAL_DIR = user_data_dir(APP_NAME, "PoddarSolutions")
CORE_ZIP_PATH = os.path.join(LOCAL_DIR, "core.zip")
VERSION_FILE = os.path.join(LOCAL_DIR, "core_version.json")

def check_for_updates():
    """Server se check karega ki naya python code available hai ya nahi"""
    try:
        # Current Version
        current_ver = "0.0.0"
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r') as f:
                current_ver = json.load(f).get('version', "0.0.0")

        # Server Check
        # Server response example: {"version": "1.0.1", "url": "https://.../core_v1.0.1.zip"}
        resp = requests.get(UPDATE_URL, timeout=5)
        data = resp.json()
        
        server_ver = data.get('version')
        download_url = data.get('url')

        if server_ver != current_ver:
            print(f"Updating from {current_ver} to {server_ver}...")
            # Download Zip
            r = requests.get(download_url, stream=True)
            with open(CORE_ZIP_PATH, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
            
            # Save new version
            with open(VERSION_FILE, 'w') as f:
                json.dump({"version": server_ver}, f)
            return True
    except Exception as e:
        print(f"Update check failed: {e}")
    return False

def launch_app():
    # 1. Update Check (Optional: Isse background thread me bhi daal sakte hain)
    check_for_updates()

    # 2. Add Core Zip to Sys Path
    # Python seedha ZIP file ke andar se import kar sakta hai!
    if os.path.exists(CORE_ZIP_PATH):
        sys.path.insert(0, CORE_ZIP_PATH)
    else:
        # Fallback: Agar zip nahi hai, to internal code use kare (First install case)
        # Iske liye aapko pehli baar zip ko installer ke saath bundle karna hoga
        pass

    try:
        # 3. Dynamic Import
        # Ab main_app.py ko import karo (jo ab zip ke andar hai)
        import main_app 
        main_app.run_application()
    except ImportError as e:
        print(f"Critical Error: Could not load application core. {e}")
        # Yahan ek basic Tkinter popup dikha sakte hain ki "Reinstall required"

if __name__ == "__main__":
    launch_app()