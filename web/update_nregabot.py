import os
import requests
import shutil

# --- CONFIGURATION (Ise Apne Hisab Se Change Karein) ---
GITHUB_REPO = "rajatpoddar/nrega_automation"
GITHUB_BRANCH = "main"  # Ya wo branch jahan aap code push karte hain

# 1. Website Root Folder (Jahan index.html rahega)
NAS_WEBSITE_ROOT = "/volume1/docker/Projects/Nrega-Bot/website"

# 2. Updates Folder (Jahan core.zip aur exe jayenge)
NAS_UPDATE_FOLDER = os.path.join(NAS_WEBSITE_ROOT, "updates")

# Agar Repo Private hai to Token dalein, warna None rakhein
# (Website files fetch karne ke liye Token zaroori ho sakta hai agar API limit aaye)
GITHUB_TOKEN = None  # e.g., "ghp_xxxxxxxxxxxx" 

# --- HEADERS ---
HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

def download_file(url, dest_path):
    """File download helper function"""
    print(f"Downloading: {dest_path}")
    try:
        # Stream download handling
        with requests.get(url, headers=HEADERS, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        # Agar file version.json hai to permissions fix karein
        if dest_path.endswith("version.json"):
             os.chmod(dest_path, 0o644)
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def sync_release_assets():
    """Task 1: GitHub Release Assets (updates) download karna"""
    print("\n--- Checking for Application Updates (Release Assets) ---")
    
    if not os.path.exists(NAS_UPDATE_FOLDER):
        os.makedirs(NAS_UPDATE_FOLDER)

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    
    try:
        resp = requests.get(api_url, headers=HEADERS)
        resp.raise_for_status()
        release_data = resp.json()
        print(f"Latest Release: {release_data.get('tag_name')}")

        for asset in release_data.get('assets', []):
            filename = asset['name']
            download_url = asset['browser_download_url']
            dest_file = os.path.join(NAS_UPDATE_FOLDER, filename)

            # Filter relevant files
            allowed_extensions = ('.zip', '.exe', '.json', '.dmg', '.tar.gz')
            if not filename.endswith(allowed_extensions):
                continue

            # Check size to skip existing files
            if os.path.exists(dest_file):
                if os.path.getsize(dest_file) == asset['size']:
                    print(f"Skipping {filename} (Up to date)")
                    continue
            
            download_file(download_url, dest_file)
            
    except Exception as e:
        print(f"Failed to check releases: {e}")

def sync_website_folder(repo_path="web", local_path=NAS_WEBSITE_ROOT):
    """Task 2: GitHub Repo ke 'web' folder ko NAS par sync karna"""
    print(f"\n--- Syncing Website Files from '{repo_path}' ---")
    
    if not os.path.exists(local_path):
        os.makedirs(local_path)

    # GitHub Contents API call
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}?ref={GITHUB_BRANCH}"
    
    try:
        resp = requests.get(api_url, headers=HEADERS)
        resp.raise_for_status()
        items = resp.json()

        if isinstance(items, dict): # Agar single file hai (Error case mostly)
            items = [items]

        for item in items:
            name = item['name']
            item_type = item['type']
            download_url = item['download_url']
            
            local_file_path = os.path.join(local_path, name)

            if item_type == 'file':
                # File download karein
                # SHA hash check kar sakte hain, par abhi simple overwrite logic rakhte hain
                # ya size check kar sakte hain. API size return karta hai.
                
                remote_size = item['size']
                should_download = True
                
                if os.path.exists(local_file_path):
                    local_size = os.path.getsize(local_file_path)
                    if local_size == remote_size:
                        # Size same hai to skip (Basic check)
                        print(f"Skipping {name} (Size match)")
                        should_download = False
                
                if should_download and download_url:
                    download_file(download_url, local_file_path)

            elif item_type == 'dir':
                # Agar folder hai (jaise css/js/images), to recursion use karein
                new_local_folder = os.path.join(local_path, name)
                sync_website_folder(item['path'], new_local_folder)

    except Exception as e:
        print(f"Failed to sync website folder: {e}")

def main():
    # 1. Pehle Website Files Update karein (HTML/CSS)
    sync_website_folder()
    
    # 2. Fir App Updates Download karein (ZIP/EXE)
    sync_release_assets()
    
    print("\nAll Tasks Completed.")

if __name__ == "__main__":
    main()