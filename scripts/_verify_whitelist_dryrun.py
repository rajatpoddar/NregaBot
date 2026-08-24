"""One-off dry-run of the release.yml Windows core-zip WHITELIST logic.
Verifies: total file count, zero leaks, all must-have runtime files present."""
import os

ALLOWED_TOP_LEVEL = {"main_app.py", "lite_app.py", "lite_loader.py",
                     "requirements.txt", "src", "config", "assets", "docs"}
ALLOWED_DOCS = {"changelog.json", "license.txt"}
ALLOWED_EXT = (".py", ".json", ".txt", ".html", ".css", ".js", ".bat", ".sh",
               ".md", ".png", ".ico", ".icns", ".wav", ".ttf", ".bmp",
               ".jpeg", ".jpg", ".csv")
SKIP_DIRS = {"__pycache__", ".git", "venv", "env", ".venv", "dist", "build",
             "user_uploads", ".idea", ".vscode", "Update_Output", "backups",
             "screenshots"}
SENSITIVE_FILES = {".env", ".env.example", ".env.dev", ".env.production",
                   "firebase-service-account.json", "hooks.json", "deploy.sh",
                   "docker-compose.yml", "Dockerfile", ".dockerignore", ".gitignore"}


def is_allowed(p):
    norm = p.replace("\\", "/")
    first = norm.split("/")[0]
    if first not in ALLOWED_TOP_LEVEL:
        return False
    if first == "docs":
        return norm in {f"docs/{f}" for f in ALLOWED_DOCS}
    if "/" not in norm:
        return norm in ALLOWED_TOP_LEVEL
    if os.path.basename(norm) in SENSITIVE_FILES:
        return False
    return norm.endswith(ALLOWED_EXT)


files = []
for top in sorted(ALLOWED_TOP_LEVEL):
    if not os.path.exists(top):
        continue
    if os.path.isfile(top):
        if is_allowed(top):
            files.append(top)
        continue
    for root, dirs, fs in os.walk(top):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fs:
            arc = os.path.relpath(os.path.join(root, f)).replace("\\", "/")
            if is_allowed(arc):
                files.append(arc)

print(f"TOTAL files that would ship: {len(files)}")
leak_kw = ("AGENTS", "IMPROVEMENT", "last_conversat", "nrega-server", ".env",
           "service-account", "hooks.json", "_smoke_test", "_audit_tab",
           "run_server", "start_server", "server_loop", "jc_verify_prefs",
           "import_check_results")
leaks = [f for f in files if any(k in f for k in leak_kw)]
print("LEAK CHECK (must be []):", leaks or "CLEAN ✅")
must = ["main_app.py", "lite_app.py", "src/config.py", "src/locales/en.json",
        "config/version.json", "docs/changelog.json", "docs/license.txt"]
missing = {m: (m in files) for m in must}
print("MUST-HAVE check:", "ALL PRESENT ✅" if all(missing.values()) else missing)
