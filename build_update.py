import zipfile
import os

# Output file name (version.json se match hona chahiye)
OUTPUT_FILENAME = "core_v2.8.3.zip"

def create_source_zip():
    print(f"Creating {OUTPUT_FILENAME} with source files only...")
    
    with zipfile.ZipFile(OUTPUT_FILENAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            # In folders ko ignore karein
            if '__pycache__' in dirs: dirs.remove('__pycache__')
            if '.git' in dirs: dirs.remove('.git')
            if 'venv' in dirs: dirs.remove('venv')
            if 'dist' in dirs: dirs.remove('dist')
            if 'build' in dirs: dirs.remove('build')
            if 'user_uploads' in dirs: dirs.remove('user_uploads')

            for file in files:
                # Sirf ye extensions allow karein
                if file.endswith(('.py', '.json', '.txt', '.html', '.css', '.js')):
                    
                    # Khud script aur purane zip ko na add karein
                    if file == OUTPUT_FILENAME or file == "build_update.py" or file == "loader.py":
                        continue
                    
                    # Full path aur Archive name banayein
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, ".")
                    
                    print(f"Adding: {arcname}")
                    zipf.write(file_path, arcname)
    
    print(f"\nSuccess! '{OUTPUT_FILENAME}' is ready.")
    print("Now upload this file to: https://nregabot.com/updates/")

if __name__ == "__main__":
    # Purana zip delete karein agar hai
    if os.path.exists(OUTPUT_FILENAME):
        os.remove(OUTPUT_FILENAME)
    create_source_zip()