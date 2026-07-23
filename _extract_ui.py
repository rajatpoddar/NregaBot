#!/usr/bin/env python3
"""Extract UI methods from main_app.py into app_ui.py as UIMixin."""
import re

SOURCE = "main_app.py"
OUTPUT = "app_ui.py"

# Methods to extract (in order they appear in source)
UI_METHODS = [
    "_on_window_resize_detect",
    "_show_resize_overlay",
    "_hide_resize_overlay",
    "_on_window_resize_end",
    "_create_header",
    "_create_main_layout",
    "_create_footer",
    "_on_sound_toggle_click",
    "_on_minimize_toggle_click",
    "_cycle_theme",
    "_fade_in_after_theme",
    "_update_theme_icon",
    "_update_settings_btn_visuals",
    "_update_header_welcome_message",
]

HEADER_TEXT = '''# app_ui.py — UI Construction & Theme Mixin
#
# A1: Extracted from main_app.py to reduce file size.
# Contains methods for building the app layout (header, footer, sidebar),
# resize smoothing, theme switching, and UI event handlers.
#
# Uses mixin pattern: inheriting class (NregaBotApp) provides
# all instance variables via self.

import customtkinter as ctk
import tkinter
from tkinter import messagebox
import os
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

import config
from utils import resource_path, get_logger, get_config, save_config
from ui_components import MarqueeLabel, PerformanceMonitor

logger = get_logger()


class UIMixin:
    """Mixin: UI construction, resize smoothing, theme cycling, UI events."""
'''


def find_method_ranges(lines, method_names):
    """Find (name, start, end) for each method in the file."""
    results = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped.startswith("def ") and line[0] == ' ':
            name = stripped.split("(")[0].replace("def ", "").strip()
            if name in method_names:
                start = i
                indent = len(line) - len(line.lstrip())
                i += 1
                while i < len(lines):
                    l = lines[i]
                    ls = l.lstrip()
                    # Stop at next def/class or section header at same or less indent
                    if l.strip() and len(l) - len(l.lstrip()) <= indent:
                        if ls.startswith("def ") or l.strip().startswith("# ==="):
                            break
                    i += 1
                end = i
                results.append((name, start, end))
        else:
            i += 1
    return results


def main():
    with open(SOURCE, 'r') as f:
        lines = f.readlines()

    # Find all methods
    methods = find_method_ranges(lines, set(UI_METHODS))
    methods_sorted = sorted(methods, key=lambda x: x[1])  # Sort by line number

    print(f"Found {len(methods_sorted)} methods to extract:")
    for name, start, end in methods_sorted:
        print(f"  {name}: lines {start+1}-{end} ({end-start} lines)")

    # Build UIMixin content
    mixin_lines = [HEADER_TEXT]
    for name, start, end in methods_sorted:
        method_code = lines[start:end]
        # Re-indent from 4 spaces to 4 spaces (same indent level in mixin)
        for line in method_code:
            mixin_lines.append('    ' + line if line.strip() else '\n')

    # Write app_ui.py
    with open(OUTPUT, 'w') as f:
        f.writelines(mixin_lines)
    print(f"\nCreated {OUTPUT}: {len(mixin_lines)} lines")

    # Remove methods from main_app.py (reverse order)
    methods_rev = sorted(methods_sorted, key=lambda x: x[1], reverse=True)
    for name, start, end in methods_rev:
        # Also remove blank lines before the method
        while start > 0 and lines[start - 1].strip() == '':
            start -= 1
        del lines[start:end]

    # Remove section headers for completely extracted sections
    result = []
    skip_resize_section = False
    skip_ui_section = False
    # Also remove _update_header_welcome_message from helpers (it was in LicenseMixin too)
    for line in lines:
        if "# RESIZE SMOOTHING" in line:
            skip_resize_section = True
            continue
        if "# UI CONSTRUCTION" in line:
            skip_ui_section = True
            continue
        if "# 3. DATA HANDOFF" in line and skip_resize_section:
            skip_resize_section = False
            result.append(line)
            continue
        if "# 3. DATA HANDOFF" in line and skip_ui_section:
            skip_ui_section = False
            result.append(line)
            continue
        if not skip_resize_section and not skip_ui_section:
            result.append(line)

    content = ''.join(result)

    # Add UIMixin import
    content = content.replace(
        "from app_automation import AutomationMixin",
        "from app_automation import AutomationMixin\nfrom app_ui import UIMixin"
    )

    # Update class inheritance
    content = content.replace(
        "class NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin):",
        "class NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin):"
    )

    with open(SOURCE, 'w') as f:
        f.write(content)

    final_lines = len(content.split('\n'))
    print(f"Updated {SOURCE}: {final_lines} lines (removed {len(methods_sorted)} methods)")


if __name__ == "__main__":
    main()
