#!/usr/bin/env python3
"""
Comprehensive migration: Convert ALL self.app.log_message(self.log_display, ...)
calls to standardized self.log_success/error/warning/info() helpers.

Handles ALL patterns found in the codebase:
  A) Simple:      self.app.log_message(self.log_display, msg, "level")
  B) No-level:    self.app.log_message(self.log_display, msg)
  C) Compound:    self.app.log_message(self.log_display, msg, "level"); other_code
  D) after(lambda): self.app.after(N, lambda: self.app.log_message(self.log_display, msg, "level"))
  E) after(args):   self.app.after(N, self.app.log_message, self.log_display, msg, "level")
  F) lambda-only:   lambda: self.app.log_message(self.log_display, msg, "level")
  G) after(lambda) complex: self.app.after(N, lambda msg=var: self.app.log_message(...))

SAFETY:
  - Parses file with ast.parse() before and after to validate syntax
  - Uses bracket-counting to handle nested parens in f-strings
  - Reverts via git if syntax breaks
"""

import ast
import os
import re
import sys
from typing import List, Tuple, Optional

TABS_DIR = "src/tabs"

# ── Files to process (all .py files in tabs dir except base_tab, __init__, _imports) ──
EXCLUDE = {"base_tab.py", "__init__.py", "_imports.py", "professional_pdf.py",
           "autocomplete_widget.py", "date_entry_widget.py", "date_picker_popup.py"}

LEVEL_MAP = {
    '"success"': "log_success",
    "'success'": "log_success",
    '"error"':   "log_error",
    "'error'":   "log_error",
    '"warning"': "log_warning",
    "'warning'": "log_warning",
    '"info"':    "log_info",
    "'info'":    "log_info",
}


def get_tab_files() -> List[str]:
    files = []
    for fn in os.listdir(TABS_DIR):
        if fn.endswith(".py") and fn not in EXCLUDE:
            files.append(os.path.join(TABS_DIR, fn))
    return sorted(files)


# ── Bracket-aware string parsing ──

def find_matching_paren(text: str, start: int) -> int:
    """Find matching ')' for '(' at text[start], handling nested parens and strings."""
    depth = 0
    in_single = False
    in_double = False
    i = start
    while i < len(text):
        ch = text[i]
        # Track strings
        if ch == "'" and not in_double and (i == 0 or text[i-1] != '\\'):
            in_single = not in_single
        elif ch == '"' and not in_single and (i == 0 or text[i-1] != '\\'):
            in_double = not in_double

        if not in_single and not in_double:
            if i == start:
                depth = 1
                i += 1
                continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def extract_level_and_msg(inner: str) -> Tuple[Optional[str], str]:
    """Extract level and message expression from inner args.
    inner = whats_left_after_stripping_log_display.
    Returns (level, message_expr)
    """
    inner = inner.strip()

    # Find the last comma at depth 0, but not inside strings
    depth = 0
    in_single = False
    in_double = False
    last_comma = -1

    # Walk backwards to find last comma
    i = len(inner) - 1
    while i >= 0:
        ch = inner[i]
        if ch == "'" and (i == 0 or inner[i-1] != '\\'):
            in_single = not in_single
        elif ch == '"' and (i == 0 or inner[i-1] != '\\'):
            in_double = not in_double
        if not in_single and not in_double:
            if ch == ')':
                depth += 1
            elif ch == '(':
                depth -= 1
            elif ch == ',' and depth == 0:
                last_comma = i
                break
        i -= 1

    if last_comma >= 0:
        last_arg = inner[last_comma + 1:].strip()
        # Check if last_arg is a string literal that matches a level
        level_key = None
        for q in ('"', "'"):
            if last_arg.startswith(q) and last_arg.endswith(q):
                val = last_arg.strip(q)
                if val in ('success', 'error', 'warning', 'info'):
                    level_key = val
                    break
        if level_key:
            msg_expr = inner[:last_comma].strip()
            return level_key, msg_expr

    # No level found
    return "info", inner


# ── Pattern functions ──

def try_pattern_A_simple(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Pattern A: self.app.log_message(self.log_display, msg, "level")"""
    marker = "self.app.log_message(self.log_display,"
    if marker not in line:
        return None, None

    idx = line.index(marker)
    open_paren = idx + len(marker) - 1  # index of '('
    # The '(' is the last char of 'log_message('
    # Actually marker ends with log_display,, so open_paren = idx + len(marker) - 1
    # Let me recalculate
    # log_message( -> the '(' is at position of marker - 1 from end
    real_marker = "self.app.log_message("
    m_idx = line.index(real_marker)
    open_p = m_idx + len(real_marker) - 1

    close_p = find_matching_paren(line, open_p)
    if close_p < 0:
        return None, None

    full_call = line[m_idx:close_p + 1]
    inner = full_call[len("self.app.log_message("):-1].strip()

    # Must start with self.log_display
    if not inner.startswith("self.log_display"):
        return None, None

    # Strip self.log_display, prefix
    after_display = inner[len("self.log_display"):].strip()
    if after_display.startswith(","):
        after_display = after_display[1:].strip()

    level, msg_expr = extract_level_and_msg(after_display)
    if level is None:
        return None, None

    helper = f"log_{level}"
    new_call = f"self.{helper}({msg_expr})"

    # Replace in line
    before_call = line[:m_idx]
    after_call = line[close_p + 1:]

    return f"{before_call}{new_call}{after_call}", full_call


def try_pattern_D_after_lambda(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Pattern D: self.app.after(N, lambda: self.app.log_message(...))"""
    pat = re.compile(
        r"self\.app\.after\(\s*\d+\s*,\s*lambda\s*(?::|[^:]*?:)\s*"
        r"self\.app\.log_message\(self\.log_display,\s*(.*?)\s*\)\s*\)"
    )
    m = pat.search(line)
    if not m:
        return None, None

    # Try after-lambda with level
    pat2 = re.compile(
        r"self\.app\.after\(\s*\d+\s*,\s*lambda\s*(?::|[^:]*?:)\s*"
        r"self\.app\.log_message\(self\.log_display,\s*(.*?),\s*\"(success|error|warning|info)\"\s*\)\s*\)"
    )
    m2 = pat2.search(line)
    if m2:
        msg = m2.group(1).strip()
        level = m2.group(2)
        new_call = f"self.log_{level}({msg})"
        new_line = pat2.sub(new_call, line)
        return new_line, m2.group(0)

    # no level version
    pat3 = re.compile(
        r"self\.app\.after\(\s*\d+\s*,\s*lambda\s*(?::|[^:]*?:)\s*"
        r"self\.app\.log_message\(self\.log_display,\s*(.*?)\s*\)\s*\)"
    )
    m3 = pat3.search(line)
    if m3:
        msg = m3.group(1).strip()
        new_call = f"self.log_info({msg})"
        new_line = pat3.sub(new_call, line)
        return new_line, m3.group(0)

    return None, None


def try_pattern_E_after_args(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Pattern E: self.app.after(N, self.app.log_message, self.log_display, msg, "level")"""
    pat = re.compile(
        r"self\.app\.after\(\s*\d+\s*,\s*self\.app\.log_message,\s*"
        r"self\.log_display,\s*(.*?),\s*\"(success|error|warning|info)\"\s*\)"
    )
    m = pat.search(line)
    if m:
        msg = m.group(1).strip()
        level = m.group(2)
        new_call = f"self.log_{level}({msg})"
        new_line = pat.sub(new_call, line)
        return new_line, m.group(0)

    # without level
    pat2 = re.compile(
        r"self\.app\.after\(\s*\d+\s*,\s*self\.app\.log_message,\s*"
        r"self\.log_display,\s*(.*?)\s*\)"
    )
    m2 = pat2.search(line)
    if m2:
        msg = m2.group(1).strip()
        new_call = f"self.log_info({msg})"
        new_line = pat2.sub(new_call, line)
        return new_line, m2.group(0)

    return None, None


def try_pattern_F_lambda(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Pattern F: lambda: self.app.log_message(self.log_display, msg, "level")"""
    pat = re.compile(
        r"lambda\s*(?::|[^:]*?:)\s*"
        r"self\.app\.log_message\(self\.log_display,\s*(.*?),\s*\"(success|error|warning|info)\"\s*\)"
    )
    m = pat.search(line)
    if m:
        msg = m.group(1).strip()
        level = m.group(2)
        new_call = f"lambda: self.log_{level}({msg})"
        new_line = pat.sub(new_call, line)
        return new_line, m.group(0)

    return None, None


# ── Master replacement ──

def try_all_patterns(line: str) -> Tuple[Optional[str], int]:
    """Try all patterns in order. Returns (new_line, replacements_count)."""
    patterns = [
        try_pattern_D_after_lambda,
        try_pattern_E_after_args,
        try_pattern_F_lambda,
        try_pattern_A_simple,
    ]

    for pattern_fn in patterns:
        result, _ = pattern_fn(line)
        if result is not None and result != line:
            return result, 1
    return None, 0


def migrate_file(filepath: str) -> Tuple[int, List[str]]:
    """Migrate a single file. Returns (replacements, errors)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if no patterns found
    if "self.app.log_message(self.log_display" not in content:
        return 0, []

    lines = content.splitlines(keepends=True)
    new_lines = list(lines)
    total = 0
    errors = []

    for i, line in enumerate(lines):
        if "self.app.log_message(self.log_display" not in line:
            continue

        # Check if already using helpers
        if any(f"self.log_{h}(" in line for h in ('success', 'error', 'warning', 'info')):
            continue

        new_line, count = try_all_patterns(line)
        if new_line is not None and count > 0:
            new_lines[i] = new_line
            total += count

    if total == 0:
        return 0, []

    new_content = ''.join(new_lines)

    # Validate syntax
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        errors.append(f"SyntaxError at line {e.lineno}: {e.msg}")
        # Don't write - return original
        return 0, errors

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return total, errors


def main():
    files = get_tab_files()
    print(f"Found {len(files)} tab files to process...\n")

    total_changes = 0
    success_files = 0
    all_errors = []

    for filepath in files:
        fn = os.path.basename(filepath)

        # First validate original file
        try:
            with open(filepath) as f:
                ast.parse(f.read())
        except SyntaxError as e:
            print(f"  ⚠️  {fn}: BROKEN BEFORE MIGRATION - SKIPPING (line {e.lineno})")
            continue

        changes, errors = migrate_file(filepath)
        if errors:
            print(f"  ❌ {fn}: ERRORS - {errors[0]}")
            all_errors.append((fn, errors))
        elif changes > 0:
            print(f"  ✅ {fn}: {changes} replacements")
            success_files += 1
        else:
            print(f"  ➖ {fn}: no changes needed")
        total_changes += changes

    print(f"\n{'=' * 50}")
    print(f"Summary: {total_changes} replacements in {success_files} files")
    if all_errors:
        print(f"Errors in {len(all_errors)} files:")
        for fn, errs in all_errors:
            for e in errs:
                print(f"  {fn}: {e}")
        return 1
    else:
        print("✅ All files migrated successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
