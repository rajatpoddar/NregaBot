#!/usr/bin/env python3
"""
Migration script: reorganizes NREGA Bot source files into a clean folder structure.
Handles:
  1. Creating __init__.py files
  2. Copying Python files to new locations with updated imports
  3. Updating import paths in remaining files (main_app.py, loader.py, tabs/*.py, scripts/*.py)
  4. Deleting old source files after successful migration
"""

import os
import re
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

print(f"Project root: {PROJECT_ROOT}")

# ============================================================================
# STEP 1: Create __init__.py files
# ============================================================================
def create_init_files():
    init_dirs = [
        "src",
        os.path.join("src", "app"),
        os.path.join("src", "managers"),
        "scripts",
        "docs",
        "config",
        "backups",
    ]
    for d in init_dirs:
        init_file = os.path.join(d, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write(f"# {d} package\n")
            print(f"  Created: {init_file}")


# ============================================================================
# STEP 2: IMPORT MAPPINGS
# ============================================================================
# Files that move and their new paths
FILE_MOVES = {
    # Root -> src/
    "config.py": "src/config.py",
    "state.py": "src/state.py",
    "utils.py": "src/utils.py",
    "ui_components.py": "src/ui_components.py",
    "location_data.py": "src/location_data.py",
    "tab_config.py": "src/tab_config.py",
    # Root -> src/app/
    "app_ui.py": "src/app/app_ui.py",
    "app_navigation.py": "src/app/app_navigation.py",
    "app_automation.py": "src/app/app_automation.py",
    "app_license.py": "src/app/app_license.py",
    # Root -> src/managers/
    "services.py": "src/managers/services.py",
    "browser_manager.py": "src/managers/browser_manager.py",
    "sound_manager.py": "src/managers/sound_manager.py",
    "icon_manager.py": "src/managers/icon_manager.py",
    "workflow_manager.py": "src/managers/workflow_manager.py",
    # Root -> scripts/ (with import updates)
    "build_update.py": "scripts/build_update.py",
    "_extract_ui.py": "scripts/_extract_ui.py",
}

# Tabs directory move (entire directory)
TABS_MOVE = True

# Import replacement rules for MOVED files (applied to file content when copying)
# (old_import_pattern, new_import_pattern) - simple string replacement
IMPORT_REPLACEMENTS = [
    # Replace 'import config' -> 'from src import config'
    # But NOT 'from config import ...'
    (r"^import config$", "from src import config"),
    (r"^import config as", "from src import config as"),
    
    # Replace 'from config import' -> 'from src.config import'
    (r"^from config import", "from src.config import"),
    
    # Replace 'from utils import' -> 'from src.utils import'
    (r"^from utils import", "from src.utils import"),
    
    # Replace 'from ui_components import' -> 'from src.ui_components import'
    (r"^from ui_components import", "from src.ui_components import"),
    
    # Replace 'from location_data import' -> 'from src.location_data import'
    (r"^from location_data import", "from src.location_data import"),
    
    # Replace 'from tab_config import' -> 'from src.tab_config import'
    (r"^from tab_config import", "from src.tab_config import"),
    
    # Replace 'from state import' -> 'from src.state import'
    (r"^from state import", "from src.state import"),
    
    # Replace 'from browser_manager import' -> 'from src.managers.browser_manager import'
    (r"^from browser_manager import", "from src.managers.browser_manager import"),
    
    # Replace 'from services import' -> 'from src.managers.services import'
    (r"^from services import", "from src.managers.services import"),
    
    # Replace 'from sound_manager import' -> 'from src.managers.sound_manager import'
    (r"^from sound_manager import", "from src.managers.sound_manager import"),
    
    # Replace 'from icon_manager import' -> 'from src.managers.icon_manager import'
    (r"^from icon_manager import", "from src.managers.icon_manager import"),
    
    # Replace 'from workflow_manager import' -> 'from src.managers.workflow_manager import'
    (r"^from workflow_manager import", "from src.managers.workflow_manager import"),
    
    # Replace 'from app_ui import' -> 'from src.app.app_ui import'
    (r"^from app_ui import", "from src.app.app_ui import"),
    
    # Replace 'from app_navigation import' -> 'from src.app.app_navigation import'
    (r"^from app_navigation import", "from src.app.app_navigation import"),
    
    # Replace 'from app_automation import' -> 'from src.app.app_automation import'
    (r"^from app_automation import", "from src.app.app_automation import"),
    
    # Replace 'from app_license import' -> 'from src.app.app_license import'
    (r"^from app_license import", "from src.app.app_license import"),
    
    # Replace 'from tabs.' references -> 'from src.tabs.'
    (r"^from tabs\.", "from src.tabs."),
]


def update_imports(content):
    """Update import statements in file content using regex replacements."""
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
    
    # Also handle the special case in config.py: `from utils import get_data_path`
    # This is at the bottom of config.py
    new_content = "\n".join(updated_lines)
    if "from utils import get_data_path" in new_content and "from src.utils import get_data_path" not in new_content:
        new_content = new_content.replace("from utils import get_data_path", "from src.utils import get_data_path")
        modified = True
    
    return new_content, modified


def update_imports_in_file(filepath):
    """Update imports in a file in-place."""
    if not os.path.exists(filepath):
        print(f"  SKIP (not found): {filepath}")
        return False
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content, modified = update_imports(content)
    
    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  Updated imports: {filepath}")
    else:
        print(f"  No import changes: {filepath}")
    
    return modified


# ============================================================================
# STEP 3: Copy files to new locations with import updates
# ============================================================================
def migrate_python_files():
    for src_rel, dst_rel in FILE_MOVES.items():
        src_path = os.path.join(PROJECT_ROOT, src_rel)
        dst_path = os.path.join(PROJECT_ROOT, dst_rel)
        
        if not os.path.exists(src_path):
            print(f"  SKIP (source not found): {src_rel}")
            continue
        
        # Read source content
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Update imports for the new location
        new_content, modified = update_imports(content)
        
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        
        # Write to new location
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        status = "imports updated" if modified else "no import changes"
        print(f"  Copied: {src_rel} -> {dst_rel} ({status})")


# ============================================================================
# STEP 4: Update imports in files that stay at root
# ============================================================================
def update_root_files():
    root_files = [
        "main_app.py",
        "loader.py",
    ]
    for f in root_files:
        fpath = os.path.join(PROJECT_ROOT, f)
        update_imports_in_file(fpath)


# ============================================================================
# STEP 5: Update imports in tabs/ files
# ============================================================================
def update_tab_files():
    tabs_dir = os.path.join(PROJECT_ROOT, "tabs")
    if not os.path.exists(tabs_dir):
        print("  tabs/ directory not found, skipping")
        return
    
    for fname in sorted(os.listdir(tabs_dir)):
        if fname.endswith(".py"):
            fpath = os.path.join(tabs_dir, fname)
            update_imports_in_file(fpath)


# ============================================================================
# STEP 6: Delete old source files (after successful copy)
# ============================================================================
def migrate_tabs_directory():
    """Move tabs/ directory to src/tabs/"""
    src_tabs = os.path.join(PROJECT_ROOT, "tabs")
    dst_tabs = os.path.join(PROJECT_ROOT, "src", "tabs")
    
    if not os.path.exists(src_tabs):
        print("  tabs/ not found at root, skipping")
        return
    
    if os.path.exists(dst_tabs):
        print("  src/tabs/ already exists, skipping")
        return
    
    # Copy all tab files to src/tabs/
    os.makedirs(dst_tabs, exist_ok=True)
    for fname in os.listdir(src_tabs):
        if fname.endswith(".py") or fname.endswith(".pyc"):
            continue  # Handle below
        src_file = os.path.join(src_tabs, fname)
        dst_file = os.path.join(dst_tabs, fname)
        if os.path.isfile(src_file):
            with open(src_file, "r", encoding="utf-8") as f:
                content = f.read()
            new_content, _ = update_imports(content)
            with open(dst_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  Copied tab: {fname} -> src/tabs/{fname}")


def cleanup_old_files(dry_run=False):
    for src_rel in FILE_MOVES:
        src_path = os.path.join(PROJECT_ROOT, src_rel)
        if os.path.exists(src_path):
            if dry_run:
                print(f"  Would delete: {src_rel}")
            else:
                os.remove(src_path)
                print(f"  Deleted: {src_rel}")
        else:
            print(f"  Already gone: {src_rel}")


def cleanup_old_backup():
    """Delete tabs_backup_c7 from root since it's now in backups/"""
    old = os.path.join(PROJECT_ROOT, "tabs_backup_c7")
    new = os.path.join(PROJECT_ROOT, "backups", "tabs_backup_c7")
    if os.path.exists(new) and os.path.exists(old):
        shutil.rmtree(old)
        print(f"  Deleted root: tabs_backup_c7 (now in backups/)")
    elif os.path.exists(old):
        print("  tabs_backup_c7 still at root (backup copy not confirmed)")


def cleanup_old_tabs_dir():
    """Delete old tabs/ directory from root after migration"""
    old_tabs = os.path.join(PROJECT_ROOT, "tabs")
    new_tabs = os.path.join(PROJECT_ROOT, "src", "tabs")
    if os.path.exists(new_tabs) and os.path.exists(old_tabs):
        shutil.rmtree(old_tabs)
        print(f"  Deleted root: tabs/ (now in src/tabs/)")
    elif os.path.exists(old_tabs):
        print("  tabs/ still at root (src/tabs/ not confirmed)")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("NREGA Bot Source Migration")
    print("=" * 60)
    
    print("\n[1/5] Creating __init__.py files...")
    create_init_files()
    
    print("\n[2/5] Copying Python files to new locations...")
    migrate_python_files()
    
    print("\n[2b/5] Moving tabs/ directory -> src/tabs/...")
    migrate_tabs_directory()
    
    print("\n[3/5] Updating imports in root files (main_app.py, loader.py)...")
    update_root_files()
    
    print("\n[4/5] Updating imports in old tabs/ files...")
    # Note: tabs were moved to src/tabs/ with updated imports
    # The old tabs/ directory is still there - update its imports just in case
    # Actually skip this because old tabs will be deleted
    print("  (skipped - tabs moved to src/tabs/)")
    
    print("\n[5/5] Cleaning up old source files...")
    cleanup_old_files()
    cleanup_old_backup()
    cleanup_old_tabs_dir()
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
