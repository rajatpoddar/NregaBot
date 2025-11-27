import compileall
import zipfile
import os
import sys
import shutil

# Output Filename (OS ke hisab se naam rakhein)
if sys.platform == "win32":
    OUTPUT_FILENAME = "core_win_v2.8.3.zip"
else:
    OUTPUT_FILENAME = "core_mac_v2.8.3.zip"

BUILD_DIR = "build_temp_secure"

def create_compiled_zip():
    print(f"Preparing Secure Compiled Update for {sys.platform}...")

    # 1. Clean previous build temp
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    
    # 2. Copy Source files to Temp Dir (taki original kharab na ho)
    # Ignore folders jo nahi chahiye
    def ignore_patterns(path, names):
        return [n for n in names if n in ['venv', '.git', '__pycache__', 'dist', 'build', 'user_uploads']]

    shutil.copytree(".", BUILD_DIR, ignore=ignore_patterns)

    # 3. Compile everything in Temp Dir
    print("Compiling code to .pyc...")
    # legacy=True hatakar modern tarika use karenge fir rename karenge
    compileall.compile_dir(BUILD_DIR, force=True, legacy=True) 

    # 4. Create ZIP with ONLY .pyc files (renamed to structure app)
    print(f"Creating {OUTPUT_FILENAME}...")
    with zipfile.ZipFile(OUTPUT_FILENAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(BUILD_DIR):
            for file in files:
                # Sirf .pyc uthao, aur assets (.json, .png etc)
                # .py file ko CHHOD DO (Security)
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, BUILD_DIR)

                if file.endswith(".pyc"):
                    # Add to zip
                    print(f"Adding Compiled: {rel_path}")
                    zipf.write(file_path, rel_path)
                
                elif file.endswith(('.json', '.txt', '.png', '.ico', '.html', '.css', '.js')):
                    # Resources add karo
                    if "version.json" in file: continue # Version file alag se jati hai usually
                    print(f"Adding Resource: {rel_path}")
                    zipf.write(file_path, rel_path)

    # 5. Cleanup
    shutil.rmtree(BUILD_DIR)
    print(f"\nSuccess! Secure {OUTPUT_FILENAME} ready.")
    print(f"Python Version Used: {sys.version.split()[0]}")

if __name__ == "__main__":
    create_compiled_zip()