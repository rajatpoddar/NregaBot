#!/usr/bin/env python3
"""
Quick script to copy tabs/ to src/tabs/ with updated imports.
"""
import os
import re
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

src_tabs = os.path.join(PROJECT_ROOT, "tabs")
dst_tabs = os.path.join(PROJECT_ROOT, "src", "tabs")

if not os.path.exists(src_tabs):
    print("ERROR: tabs/ not found at root")
    exit(1)

os.makedirs(dst_tabs, exist_ok=True)

# Import replacement rules for tabs files
IMPORT_REPLACEMENTS = [
    (r"^import config$", "from src import config"),
    (r"^from config import", "from src.config import"),
    (r"^from utils import", "from src.utils import"),
    (r"^from ui_components import", "from src.ui_components import"),
    (r"^from location_data import", "from src.location_data import"),
    (r"^from tab_config import", "from src.tab_config import"),
    (r"^from state import", "from src.state import"),
    (r"^from browser_manager import", "from src.managers.browser_manager import"),
    (r"^from services import", "from src.managers.services import"),
    (r"^from sound_manager import", "from src.managers.sound_manager import"),
    (r"^from icon_manager import", "from src.managers.icon_manager import"),
    (r"^from workflow_manager import", "from src.managers.workflow_manager import"),
    (r"^from app_ui import", "from src.app.app_ui import"),
    (r"^from app_navigation import", "from src.app.app_navigation import"),
    (r"^from app_automation import", "from src.app.app_automation import"),
    (r"^from app_license import", "from src.app.app_license import"),
]

def update_imports(content):
    lines = content.split("\n")
    updated_lines = []
    modified = False
    for line in lines:
        new_line = line
        for pattern, replacement in IMPORT_REPLACEMENTS:
            if re.match(pattern, line):
                new_line = re.sub(pattern, replacement, line)
                if new_line != line:
                    modified = True
                    break
        updated_lines.append(new_line)
    return "\n".join(updated_lines), modified

copied = 0
for fname in sorted(os.listdir(src_tabs)):
    if not fname.endswith(".py"):
        continue
    src_file = os.path.join(src_tabs, fname)
    dst_file = os.path.join(dst_tabs, fname)
    
    with open(src_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    new_content, modified = update_imports(content)
    
    with open(dst_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"  {'UPDATED' if modified else 'COPIED'}: {fname}")
    copied += 1

print(f"\nDone! {copied} tab files copied to src/tabs/")

# Now delete root tabs/
shutil.rmtree(src_tabs)
print("Deleted root tabs/ directory")
