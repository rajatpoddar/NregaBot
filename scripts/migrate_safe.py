#!/usr/bin/env python3
"""
Bulletproof log helper migration script v2.

Uses a bracket-counter to find matching ')' for log_message(..., handling
nested parens inside f-strings (e.g., f"({count})") correctly.
"""

import os
import ast
import sys

TABS_DIR = "src/tabs"

TARGET_FILES = [
    'abps_verify_tab.py',
    'add_activity_tab.py',
    'del_demand_tab.py',
    'duplicate_mr_tab.py',
    'ekyc_report_tab.py',
    'if_edit_tab.py',
    'jobcard_verify_tab.py',
    'material_entry_tab.py',
    'mis_reports_tab.py',
    'mr_tracking_tab.py',
    'pdf_merger_tab.py',
    'physical_complete_tab.py',
    'resend_rejected_wg_tab.py',
    'sarkar_aapke_dwar_tab.py',
    'update_estimate_tab.py',
    'wc_gen_tab.py',
]


def find_matching_paren(text, start):
    """
    Find the index of the ')' matching the '(' at text[start].
    Properly handles nested parens and ignores parens inside string literals.
    """
    depth = 0
    in_single = False
    in_double = False
    in_fstring_brace = 0  # depth of {} inside f-strings
    
    i = start
    while i < len(text):
        ch = text[i]
        prev_ch = text[i-1] if i > start else ''
        
        # Track string literals
        if ch == "'" and not in_double:
            if i > 0 and text[i-1] == '\\':
                pass  # escaped
            else:
                in_single = not in_single
        elif ch == '"' and not in_single:
            if i > 0 and text[i-1] == '\\':
                pass  # escaped
            else:
                in_double = not in_double
        
        # Track f-string braces { } inside strings
        if (in_single or in_double) and ch == '{':
            in_fstring_brace += 1
        elif (in_single or in_double) and ch == '}':
            in_fstring_brace -= 1
        
        if i == start:
            # The character at 'start' is the opening '('
            depth = 1
            i += 1
            continue
        
        if not in_single and not in_double:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return i
        
        i += 1
    
    return -1  # Not found


def is_safe_line(line):
    """Check if this line is safe for a simple single-line replacement."""
    s = line.strip()
    if not s or s.startswith('#'):
        return False
    
    # Must contain the old-style call
    marker = 'self.app.log_message(self.log_display,'
    if marker not in s:
        return False
    
    # Skip compound statements with semicolons (outside strings)
    in_single = False
    in_double = False
    for ch in s:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ';' and not in_single and not in_double:
            return False
        elif ch == '#' and not in_single and not in_double:
            # Comment - trim to just the code part
            break
    
    # Skip lambda
    if 'lambda ' in s or 'lambda:' in s:
        return False
    
    # Skip self.app.after(
    if 'self.app.after(' in s:
        return False
    
    # Must contain exactly one log_message call
    count = s.count(marker)
    if count != 1:
        return False
    
    return True


def extract_full_call(line):
    """
    Extract the entire 'self.app.log_message(...)' call from a line.
    Uses bracket-counter to handle nested parens correctly.
    Returns (full_call, start_pos, end_pos) or None.
    """
    marker = 'self.app.log_message('
    pos = line.find(marker)
    if pos < 0:
        return None
    
    # The opening ( is at pos + len(marker) - 1
    open_paren_pos = pos + len(marker) - 1
    close_paren_pos = find_matching_paren(line, open_paren_pos)
    
    if close_paren_pos < 0:
        return None
    
    return (line[pos:close_paren_pos+1], pos, close_paren_pos + 1)


def extract_args(full_call):
    """Extract the arguments from the call, handling parens."""
    # Strip 'self.app.log_message(' prefix and trailing ')'
    inner = full_call[len('self.app.log_message('):-1]
    return inner


def determine_level_and_message(inner_args):
    """
    Parse the inner arguments to determine the level and message.
    Returns (level, message_expr).
    """
    inner = inner_args.strip()
    
    # Check if the last argument is a level string
    # We need to find the last comma at depth 0 (not inside parens/braces/strings)
    # Simple heuristic: split by last comma, check if last part is a level string
    
    # Find the last comma at depth 0
    depth = 0
    in_single = False
    in_double = False
    last_comma = -1
    
    i = len(inner) - 1
    while i >= 0:
        ch = inner[i]
        
        # Track string literals (going backwards, but good enough)
        if ch == "'": in_single = not in_single  # approximate
        elif ch == '"': in_double = not in_double  # approximate
        
        if not in_single and not in_double:
            if ch == ')': depth += 1
            elif ch == '(': depth -= 1
            elif ch == ',' and depth == 0:
                last_comma = i
                break
        i -= 1
    
    if last_comma >= 0:
        last_arg = inner[last_comma+1:].strip()
        # Check if last_arg is a string literal
        if last_arg.startswith('"') or last_arg.startswith("'"):
            level_str = last_arg.strip('"\'')
            if level_str in ('success', 'error', 'warning'):
                message_expr = inner[:last_comma].strip()
                # Also strip 'self.log_display, ' prefix
                if message_expr.startswith('self.log_display,'):
                    message_expr = message_expr[len('self.log_display,'):].strip()
                return level_str, message_expr
    
    # No level found - it's an info call
    # Strip 'self.log_display, ' prefix
    message_expr = inner
    if message_expr.startswith('self.log_display,'):
        message_expr = message_expr[len('self.log_display,'):].strip()
    return 'info', message_expr


def migrate_file(fpath):
    """Migrate a single file. Returns (success, replacements, skipped)."""
    with open(fpath, 'r') as f:
        lines = f.readlines()
    
    replacements = 0
    skipped = []
    
    for i, line in enumerate(lines):
        if 'self.app.log_message(' not in line:
            continue
        
        if not is_safe_line(line):
            skipped.append(f"  ⚠️  Line {i+1}: SKIPPED (compound/complex)")
            continue
        
        result = extract_full_call(line)
        if not result:
            skipped.append(f"  ⚠️  Line {i+1}: SKIPPED (could not parse parens)")
            continue
        
        full_call, start, end = result
        inner_args = extract_args(full_call)
        level, message_expr = determine_level_and_message(inner_args)
        
        helper_name = f"log_{level}"
        new_call = f"self.{helper_name}({message_expr})"
        
        new_line = line[:start] + new_call + line[end:]
        
        if new_line != line:
            lines[i] = new_line
            replacements += 1
    
    if replacements == 0:
        return (True, 0, skipped)
    
    new_content = ''.join(lines)
    
    # Validate syntax
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return (False, replacements, [f"❌ SyntaxError at line {e.lineno}: {e.msg}"])
    
    with open(fpath, 'w') as f:
        f.write(new_content)
    
    return (True, replacements, skipped)


def main():
    total_repl = 0
    total_ok = 0
    total_fail = 0
    
    for fn in TARGET_FILES:
        fpath = os.path.join(TABS_DIR, fn)
        if not os.path.exists(fpath):
            print(f"  ⚠️  {fn}: NOT FOUND")
            continue
        
        # First verify original file is valid
        try:
            ast.parse(open(fpath).read())
        except SyntaxError as e:
            print(f"  ❌ {fn}: BROKEN BEFORE MIGRATION - line {e.lineno}: {e.msg}")
            total_fail += 1
            continue
        
        success, count, msgs = migrate_file(fpath)
        
        if success:
            status = '✅' if count > 0 else '➖'
            print(f"  {status} {fn}: {count} replacements")
            for m in msgs[:3]:  # show max 3 skipped
                print(f"     {m}")
            if len(msgs) > 3:
                print(f"     ... and {len(msgs)-3} more skipped")
            total_ok += 1
            total_repl += count
        else:
            print(f"  ❌ {fn}: FAILED")
            for m in msgs:
                print(f"     {m}")
            total_fail += 1
    
    print(f"\n📊 Summary: {total_ok} files ✅, {total_repl} replacements, {total_fail} failures")


if __name__ == '__main__':
    main()
