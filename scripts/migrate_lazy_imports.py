#!/usr/bin/env python3
"""
Migration script: P5.1 — Remove lazy import blocks from automation tab files.

For each .py file in src/tabs/ (except _imports.py, base_tab.py and __init__.py):
  1. Add  from ._imports import *  at module level (right after the last
     module-level non-lazy import).
  2. Remove ALL method-body lazy import blocks:
       - Indented lines matching  from selenium...  or  import openpyxl
         or  from openpyxl...   — these are inside method bodies.
       - Preceding comment lines like  '# ---- Lazy imports ----'
         or  '# Lazy imports'

Run from the project root:  python scripts/migrate_lazy_imports.py
"""

import re
import os
import sys

TABS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "tabs")
IMPORT_LINE = "from ._imports import *  # noqa: F403,F401\n"

# Patterns for lazy imports (indented — method-body level)
LAZY_PATTERNS = [
    re.compile(r'^(\s+)from selenium\b'),
    re.compile(r'^\s+import openpyxl\b'),
    re.compile(r'^(\s+)from openpyxl\b'),
]

# Comment lines that introduce lazy import blocks
COMMENT_PATTERNS = [
    re.compile(r'^\s*#.*[Ll]azy.*[Ii]mport'),
    re.compile(r'^\s*# ----.*----'),
]

FILES_TO_SKIP = {
    "_imports.py",   # our new module
    "base_tab.py",   # already has module-level selenium imports
    "__init__.py",   # empty
    "home_tab.py",   # no lazy imports expected
    "macro_manager_tab.py",
    "workcode_extractor_tab.py",
    "file_management_tab.py",
    "about_tab.py",
    "settings_tab.py",
    "whatsapp_chat_tab.py",
    "date_picker_popup.py",
    "professional_pdf.py",
    "autocomplete_widget.py",
    "history_manager.py",
    "config.py",
    "lite_config.py",
    "state.py",
    "utils.py",
}


def has_module_level_import(lines):
    """Check if  from ._imports import *  already exists."""
    return any('from ._imports import *' in line for line in lines)


def find_insertion_point(lines):
    """Find the best line to insert the shared import.
    
    Insert after the last module-level import or after the 'from .base_tab'
    or 'from src' import block.
    """
    last_import_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match module-level imports (not indented)
        if stripped.startswith(('import ', 'from ')) and not stripped.startswith(('from ',)) or True:
            # Only count non-indented imports (module level)
            if line[0] != ' ' and line[0] != '\t':
                if any(stripped.startswith(p) for p in ('import ', 'from ')):
                    last_import_idx = i
    
    # If no import found, insert after the module docstring or first lines
    if last_import_idx < 0:
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#'):
                return i
        return 1  # default
    
    return last_import_idx + 1


def is_lazy_import_line(line):
    """Check if a line is a method-body lazy import (indented selenium/openpyxl import)."""
    stripped = line.strip()
    if not stripped:
        return False
    if not (line[0] in (' ', '\t')):
        return False  # not indented => module level, keep it
    
    for pattern in LAZY_PATTERNS:
        if pattern.match(line):
            return True
    return False


def is_comment_line(line):
    """Check if line is a lazy-import comment prefix."""
    return any(p.match(line) for p in COMMENT_PATTERNS)


def process_file(filepath):
    """Process a single tab file: remove lazy imports, add shared import."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if not lines:
        return 0, 0
    
    if has_module_level_import(lines):
        print(f"  ⏭️  SKIP (already has _imports import): {os.path.basename(filepath)}")
        return 0, 0
    
    # Step 1: Add shared import at module level
    insert_at = find_insertion_point(lines)
    
    # Only add the import line if the file has any lazy imports to remove
    # Check if file has lazy imports before adding
    has_lazy = any(is_lazy_import_line(line) for line in lines)
    if has_lazy:
        # Add a blank line before the import if needed
        if insert_at > 0 and lines[insert_at - 1].strip():
            lines.insert(insert_at, '\n')
            insert_at += 1
        lines.insert(insert_at, IMPORT_LINE)
    
    # Step 2: Remove lazy import lines
    removed = 0
    new_lines = []
    skip_comment = False  # flag to skip upcoming comment lines
    
    for line in lines:
        stripped = line.strip()
        
        # Skip lazy-import comment blocks
        if is_comment_line(line):
            removed += 1
            continue
        
        if is_lazy_import_line(line):
            removed += 1
            continue
        
        new_lines.append(line)
    
    # Write result
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    return 1, removed


def main():
    print("=" * 60)
    print("P5.1 — Lazy Import Block Migration")
    print("=" * 60)
    
    total_processed = 0
    total_removed = 0
    
    for filename in sorted(os.listdir(TABS_DIR)):
        if not filename.endswith('.py'):
            continue
        if filename in FILES_TO_SKIP:
            continue
        
        filepath = os.path.join(TABS_DIR, filename)
        processed, removed = process_file(filepath)
        
        if processed:
            print(f"  ✅ {filename}: removed {removed} lazy import lines")
        total_processed += processed
        total_removed += removed
    
    print("-" * 60)
    print(f"Processed: {total_processed} files")
    print(f"Removed:   {total_removed} lazy import lines")
    print("=" * 60)


if __name__ == '__main__':
    main()
