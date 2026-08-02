"""build_update.py — creates the code-only "core" update zip.

Only the files the desktop app needs at runtime are packaged. Server code
(nrega-server/), the marketing site (web/), dotenv files and other secrets are
deliberately EXCLUDED so they can never leak through the update channel.
"""
import zipfile
import os
import sys
import platform

# Make sure the project root is on sys.path so `from src.config import
# APP_VERSION` works even when invoked as `python3 scripts/build_update.py`.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.config import APP_VERSION
except ImportError:
    print("⚠️ Warning: config.py not found or APP_VERSION missing. Using 0.0.0")
    APP_VERSION = "0.0.0"

# --- CONFIGURATION ---
sys_plat = platform.system()
if sys_plat == "Darwin":
    PLAT_TAG = "mac"
elif sys_plat == "Windows":
    PLAT_TAG = "win"
else:
    PLAT_TAG = "linux"

DIST_DIR = "dist"
OUTPUT_FILENAME = f"core_{PLAT_TAG}_v{APP_VERSION}.zip"
OUTPUT_PATH = os.path.join(PROJECT_ROOT, DIST_DIR, OUTPUT_FILENAME)

# ---------------------------------------------------------------------------
# WHITELIST — only these top-level entries are packaged.
# Anything not listed here (nrega-server/, web/, scripts/, .github/, docs/
# beyond the changelog, .env, hooks.json, firebase-service-account.json, ...)
# is EXCLUDED.
# ---------------------------------------------------------------------------
ALLOWED_TOP_LEVEL = {
    "main_app.py", "lite_app.py", "lite_loader.py", "requirements.txt",
    "src", "config", "assets", "docs",
}
ALLOWED_DOCS = {"changelog.json"}   # only this file from docs/
ALLOWED_EXT = (".py", ".json", ".txt", ".html", ".css", ".js", ".bat", ".sh",
               ".md", ".png", ".ico", ".icns", ".wav", ".ttf", ".bmp",
               ".jpeg", ".jpg", ".csv")

SKIP_DIRS = {"__pycache__", ".git", "venv", "env", ".venv", "dist", "build",
             "user_uploads", ".idea", ".vscode", "Update_Output", "backups",
             "screenshots"}

# Extra safety net: even inside an allowed dir, never ship these files.
SENSITIVE_FILES = {".env", ".env.example", ".env.dev", ".env.production",
                   "firebase-service-account.json", "hooks.json",
                   "deploy.sh", "docker-compose.yml", "Dockerfile",
                   ".dockerignore", ".gitignore"}


def _is_allowed(rel_path: str) -> bool:
    """Return True if rel_path (POSIX, relative to project root) is safe to ship."""
    norm = rel_path.replace("\\", "/")
    first = norm.split("/")[0]
    if first not in ALLOWED_TOP_LEVEL:
        return False
    # docs/ -> only changelog.json
    if first == "docs":
        return norm == "docs/changelog.json"
    # Root-level files -> only the explicitly allowed ones
    if "/" not in norm:
        return norm in ALLOWED_TOP_LEVEL
    # Inside src/ config/ assets/ -> extension check + sensitive-file check
    if os.path.basename(norm) in SENSITIVE_FILES:
        return False
    return norm.endswith(ALLOWED_EXT)


def create_source_zip():
    """Package only the whitelisted app files into the update zip."""
    if not os.path.exists(DIST_DIR):
        os.makedirs(DIST_DIR)

    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    print(f"📦 Creating Update Package: {OUTPUT_PATH}")
    count = 0
    with zipfile.ZipFile(OUTPUT_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for top in sorted(ALLOWED_TOP_LEVEL):
            full = os.path.join(PROJECT_ROOT, top)
            if not os.path.exists(full):
                continue
            if os.path.isfile(full):
                if _is_allowed(top):
                    print(f"  + Adding: {top}")
                    zipf.write(full, top)
                    count += 1
                continue
            # top is a directory -> walk only it (never the whole repo)
            for root, dirs, files in os.walk(full):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, PROJECT_ROOT).replace("\\", "/")
                    if _is_allowed(arcname):
                        print(f"  + Adding: {arcname}")
                        zipf.write(file_path, arcname)
                        count += 1

    print(f"\n✅ Success! Update file ready: {OUTPUT_PATH} ({count} files)")
    print(f"👉 Upload this file to your server for v{APP_VERSION} ({PLAT_TAG}) update.")


if __name__ == "__main__":
    create_source_zip()
