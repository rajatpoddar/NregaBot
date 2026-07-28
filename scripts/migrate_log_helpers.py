#!/usr/bin/env python3
"""
Safe bulk migration: Replace self.app.log_message(self.log_display, ...) calls
with self.log_success/log_error/log_warning/log_info helpers.

SAFETY GUARANTEES:
  - Only replaces when log_message call is the ONLY statement on the line
    (i.e., closing paren is last non-whitespace char before end-of-line)
  - Skips lines with self.app.after(), lambda:, or semicolons after the call
  - Skips f-strings with nested parentheses (too risky)
  - Validates syntax after each file
"""
import os
import re
import ast
import glob
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABS_DIR = os.path.join(PROJECT_ROOT, "src", "tabs")

ALREADY_MIGRATED = {
    "del_work_alloc_tab.py",
    "zero_mr_tab.py",
    "SA_report_tab.py",
    "emb_verify_tab.py",
}


def get_tab_files():
    files = glob.glob(os.path.join(TABS_DIR, "*.py"))
    return sorted(
        f for f in files
        if os.path.basename(f) not in ALREADY_MIGRATED
        and os.path.basename(f) != "base_tab.py"
    )


def is_single_statement(line, match_end):
    """
    Check that the log_message(...) call is the ONLY statement on this line.
    match_end is the position where the closing paren of log_message ends.
    Everything after that must be whitespace only.
    """
    after = line[match_end:]
    return after.strip() == ""


# Safely compile regex patterns.
# IMPORTANT: Do NOT include trailing \s*$ — that would consume the line-ending \n
# and concatenate the next line into this one.  is_single_statement() already
# validates that nothing follows the closing paren on this line.
def build_pattern(level=None):
    """Build regex pattern. level can be 'success', 'error', 'warning', 'info', or None (no level)."""
    if level:
        return re.compile(
            r"self\.app\.log_message\(self\.log_display,\s*(.*?),\s*\""
            + level
            + r"\"\s*\)"
        )
    else:
        return re.compile(
            r"self\.app\.log_message\(self\.log_display,\s*(.*?)\)"
        )


LEVEL_PATTERNS = [
    ("success", "log_success"),
    ("error", "log_error"),
    ("warning", "log_warning"),
    ("info", "log_info"),
]

NOLEVEL_PATTERN = ("nolevel", "log_info")


def should_skip_line(line):
    s = line.strip()
    # Skip blank/comment lines
    if not s or s.startswith("#"):
        return True
    # Skip after() scheduling
    if "self.app.after(" in s:
        return True
    # Skip lambda patterns
    if "lambda:" in s or "lambda " in s:
        return True
    # Skip lines already using the new helpers
    for m in ("self.log_success(", "self.log_error(", "self.log_warning(", "self.log_info("):
        if m in s:
            return True
    return False


def replace_line(line):
    """Try to replace a single line. Returns (new_line, changed_bool)."""
    if "self.app.log_message(self.log_display," not in line:
        return line, False
    if should_skip_line(line):
        return line, False

    # Try with explicit level first
    for level, method in LEVEL_PATTERNS:
        pat = build_pattern(level)
        m = pat.search(line)
        if m:
            msg = m.group(1)
            # Safety check: no nested unclosed parens in msg
            if msg.count("(") != msg.count(")") and "f\"" in msg:
                # Risky f-string - skip
                continue
            if not is_single_statement(line, m.end()):
                continue
            replacement = f"self.{method}({msg})"
            new_line = pat.sub(replacement, line)
            return new_line, True

    # Try without level
    pat = build_pattern()
    m = pat.search(line)
    if m:
        msg = m.group(1)
        if msg.count("(") != msg.count(")") and "f\"" in msg:
            return line, False
        if not is_single_statement(line, m.end()):
            return line, False
        replacement = f"self.log_info({msg})"
        new_line = pat.sub(replacement, line)
        return new_line, True

    return line, False


def replace_in_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines(keepends=True)

    modified_lines = []
    changes = 0

    for line in lines:
        new_line, changed = replace_line(line)
        modified_lines.append(new_line)
        if changed:
            changes += 1

    if changes > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(modified_lines)

    return changes


def validate_syntax(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        return True
    except SyntaxError:
        return False


def main():
    files = get_tab_files()
    total_changes = 0
    success_count = 0
    error_files = []
    skipped = 0

    print(f"Found {len(files)} tab files to process...\n")

    for filepath in files:
        basename = os.path.basename(filepath)
        changes = replace_in_file(filepath)

        if changes > 0:
            if validate_syntax(filepath):
                print(f"  ✅ {basename}: {changes} replacements")
                success_count += 1
            else:
                print(f"  ❌ {basename}: {changes} replacements BUT SYNTAX ERROR - REVERTING!")
                # Revert via git
                os.system(f"git checkout -- '{filepath}'")
                error_files.append(basename)
        else:
            print(f"  ➖ {basename}: no changes needed")
            skipped += 1

        total_changes += changes

    print(f"\n{'='*60}")
    print(f"Total: {total_changes} replacements across {success_count} files")
    if error_files:
        print(f"⚠️  Reverted {len(error_files)} files with errors: {', '.join(error_files)}")
        return 1
    else:
        print("✅ All files passed syntax validation!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
