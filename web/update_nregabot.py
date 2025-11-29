import os
import requests
import shutil

# --- CONFIGURATION ---
GITHUB_REPO = "rajatpoddar/nrega_automation"
GITHUB_BRANCH = "main"

# 1. Website Root (Jahan index.html aur version.json hone chahiye)
NAS_WEBSITE_ROOT = "/volume1/docker/Projects/Nrega-Bot/website"

# 2. Updates Folder (Jahan zip aur exe rahenge)
NAS_UPDATE_FOLDER = os.path.join(NAS_WEBSITE_ROOT, "updates")

GITHUB_TOKEN = None  # Token optional

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

def download_file(url, dest_path):
    print(f"Downloading: {dest_path}")
    try:
        # stream=True rakhenge, lekin content decode karke likhenge
        with requests.get(url, headers=HEADERS, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                # OLD CODE (Problem yahan thi): shutil.copyfileobj(r.raw, f)
                
                # NEW CODE (Fix): iter_content use karein jo automatic decompress karega
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
        if dest_path.endswith("version.json"):
             os.chmod(dest_path, 0o644)
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def sync_release_assets():
    print("\n--- Checking for Application Updates ---")
    
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
            
            # File updates folder me jayegi
            dest_file = os.path.join(NAS_UPDATE_FOLDER, filename)

            # Allowed files
            if not filename.endswith(('.zip', '.exe', '.json', '.dmg', '.tar.gz')):
                continue

            # Check if update needed
            should_download = True
            if os.path.exists(dest_file):
                if os.path.getsize(dest_file) == asset['size']:
                    print(f"Skipping {filename} (Up to date)")
                    should_download = False
            
            if should_download:
                if download_file(download_url, dest_file):
                    
                    # ✅ NEW LOGIC: Agar file version.json hai, to use ROOT folder me copy karo
                    if filename == "version.json":
                        root_version_file = os.path.join(NAS_WEBSITE_ROOT, "version.json")
                        shutil.copy2(dest_file, root_version_file)
                        print(f"✅ Updated {root_version_file} for website access.")

    except Exception as e:
        print(f"Failed to check releases: {e}")

def sync_website_folder(repo_path="web", local_path=NAS_WEBSITE_ROOT):
    print(f"\n--- Syncing Website Files from '{repo_path}' ---")
    if not os.path.exists(local_path): os.makedirs(local_path)

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}?ref={GITHUB_BRANCH}"
    
    try:
        resp = requests.get(api_url, headers=HEADERS)
        if resp.status_code == 404:
            print(f"Folder '{repo_path}' not found in repo.")
            return
            
        items = resp.json()
        if isinstance(items, dict): items = [items]

        for item in items:
            name = item['name']
            if item['type'] == 'file':
                local_file = os.path.join(local_path, name)
                # Simple overwrite logic for web files
                download_file(item['download_url'], local_file)
            elif item['type'] == 'dir':
                sync_website_folder(item['path'], os.path.join(local_path, name))

    except Exception as e:
        print(f"Website sync error: {e}")

def main():
    sync_website_folder()  # HTML/CSS update karega
    sync_release_assets()  # App files + version.json update karega
    print("\nAll Tasks Completed.")

if __name__ == "__main__":
    main()