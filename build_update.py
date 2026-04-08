import zipfile
import os
import platform
# Config se version import karein
try:
    from config import APP_VERSION
except ImportError:
    print("⚠️ Warning: config.py not found or APP_VERSION missing. Using 0.0.0")
    APP_VERSION = "0.0.0"

# --- CONFIGURATION ---
# OS detect karke tag set karein (mac/win)
sys_plat = platform.system()
if sys_plat == "Darwin":
    PLAT_TAG = "mac"
elif sys_plat == "Windows":
    PLAT_TAG = "win"
else:
    PLAT_TAG = "linux"

# Output folder aur filename define karein
DIST_DIR = "dist"
OUTPUT_FILENAME = f"core_{PLAT_TAG}_v{APP_VERSION}.zip"
OUTPUT_PATH = os.path.join(DIST_DIR, OUTPUT_FILENAME)

def create_source_zip():
    # 1. Dist folder banayein agar nahi hai
    if not os.path.exists(DIST_DIR):
        os.makedirs(DIST_DIR)
    
    # Purani file hatayein agar exist karti hai
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    print(f"📦 Creating Update Package: {OUTPUT_PATH}")
    
    with zipfile.ZipFile(OUTPUT_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            # In folders ko ignore karein (In-place modification taaki os.walk inke andar na jaye)
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', 'venv', 'env', 'dist', 'build', 'user_uploads', 
                '.idea', '.vscode', 'Update_Output'
            ]]

            for file in files:
                # Sirf ye extensions allow karein
                if file.endswith(('.py', '.json', '.txt', '.html', '.css', '.js', '.bat', '.sh', '.md', '.env')):
                    
                    # Khud script, loader, aur dusre zips ko ignore karein
                    if file == os.path.basename(__file__) or file == "loader.py" or file.endswith(".zip") or file.endswith(".dmg"):
                        continue
                    
                    # Full path aur Archive name
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, ".")
                    
                    print(f"  + Adding: {arcname}")
                    zipf.write(file_path, arcname)
    
    print(f"\n✅ Success! Update file ready: {OUTPUT_PATH}")
    print(f"👉 Upload this file to your server for v{APP_VERSION} ({PLAT_TAG}) update.")

if __name__ == "__main__":
    create_source_zip()