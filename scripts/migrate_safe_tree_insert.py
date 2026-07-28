#!/usr/bin/env python3
"""
migrate_safe_tree_insert.py — P5.2

Replaces:
    self.app.after(0, lambda: self.results_tree.insert(
        "", "end", values=VALUES, tags=TAGS))

With:
    self.safe_tree_insert(VALUES, TAGS)

Handles both:
  - inline tuples: values=(work_code, status, ...)
  - pre-built variables: values=values, tags=tags
  - missing tags: ...values=(...))
  - multi-line value tuples: values=(\n  ...\n)
"""

import os
import re
import sys

TABS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "tabs")


def _replace_after_call(content: str) -> str:
    """
    Pattern: self.app.after(0, lambda: self.results_tree.insert("", "end", values=..., tags=...))
    We want to extract 'values' and 'tags' and replace with self.safe_tree_insert(values, tags)
    """
    # Pattern 1: self.app.after(0, lambda: self.results_tree.insert("", "end", values=(...inline tuple...), tags=tags))
    # This is tricky because the values tuple might span multiple lines and contain nested parens
    
    # Let's use a simpler approach: find all occurrences and manually replace
    # Pattern: self.app.after(0, lambda: self.results_tree.insert("", "end", 
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Detect the start of a replaceable pattern
        if 'self.app.after(0, lambda: self.results_tree.insert(' in line or \
           ('self.app.after(0,' in line and 'results_tree.insert(' in line):
            
            # Collect all lines of this call
            call_lines = [line]
            # Check if the call spans multiple lines (i.e., doesn't end with )) on this line)
            # Count open/close parens - if balanced, it's single line
            combined = line
            while '(' in line and '))' not in line and not line.rstrip().endswith('))'):
                # Actually let's just count parens
                open_parens = combined.count('(') - combined.count(')')
                # Need more nuanced check: the pattern ends with ...)) 
                if combined.rstrip().endswith('))') or (combined.rstrip().endswith(')') and not combined.rstrip().endswith('))')):
                    pass  # might still be single line
                # Check if we need more lines
                if open_parens <= 0:
                    break
                i += 1
                if i >= len(lines):
                    break
                line = lines[i]
                call_lines.append(line)
                combined = ' '.join(call_lines)
            
            full_call = ' '.join(call_lines)
            
            # Now try to extract values and tags
            # Pattern: values=(...), tags=tags)
            # OR: values=(...))
            # OR: values=values, tags=tags)
            
            # Check if it's a simple pre-built variable case first
            # Pattern: ...values=values, tags=tags))
            m = re.search(r'values=values\s*,\s*tags=(\w+)\)\)', full_call)
            if m:
                tags_var = m.group(1)
                replacement = f"                self.safe_tree_insert(values, {tags_var})"
                # Preserve the original line's indentation
                indent = call_lines[0][:len(call_lines[0]) - len(call_lines[0].lstrip())]
                new_lines.append(indent + replacement)
                continue
            
            # Pattern: values=values))  (no tags)
            m = re.search(r'values=values\)\)', full_call)
            if m:
                replacement = f"                self.safe_tree_insert(values)"
                indent = call_lines[0][:len(call_lines[0]) - len(call_lines[0].lstrip())]
                new_lines.append(indent + replacement)
                continue
            
            # Pattern: values=(inline_tuple), tags=tags))
            # First, find where values=(...) starts and ends
            vals_match = re.search(r'values=\((.+?)\)\s*,\s*tags=(\w+)\)\)', full_call, re.DOTALL)
            if vals_match:
                values_content = vals_match.group(1).strip()
                tags_var = vals_match.group(2)
                # Format the replacement
                if '\n' in values_content:
                    # Clean up multi-line values
                    values_content = re.sub(r'\s+', ' ', values_content).strip()
                replacement = f"self.safe_tree_insert(({values_content}), {tags_var})"
                indent = call_lines[0][:len(call_lines[0]) - len(call_lines[0].lstrip())]
                new_lines.append(indent + replacement)
                continue
            
            # Pattern: values=(inline_tuple))  (no tags)
            vals_match = re.search(r'values=\((.+?)\)\)\)', full_call)
            if vals_match:
                values_content = vals_match.group(1).strip()
                if '\n' in values_content:
                    values_content = re.sub(r'\s+', ' ', values_content).strip()
                replacement = f"self.safe_tree_insert(({values_content}))"
                indent = call_lines[0][:len(call_lines[0]) - len(call_lines[0].lstrip())]
                new_lines.append(indent + replacement)
                continue
            
            # If none of the patterns matched, keep the original
            new_lines.extend(call_lines)
        else:
            new_lines.append(line)
        i += 1
    
    return '\n'.join(new_lines)


def migrate_file(filepath: str) -> int:
    """Returns number of replacements made."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Simple text-based replacements for the most common patterns
    replacements = [
        # Pattern: values=values (pre-built variable)
        (r"self\.app\.after\(0,\s*lambda:\s*self\.results_tree\.insert\(\"\",\s*\"end\",\s*values=values,\s*tags=(\w+)\)\)",
         r"self.safe_tree_insert(values, \1)"),
        
        # Pattern: values=values (no tags)
        (r"self\.app\.after\(0,\s*lambda:\s*self\.results_tree\.insert\(\"\",\s*\"end\",\s*values=values\)\)",
         r"self.safe_tree_insert(values)"),
        
        # Pattern: inline tuple with tags
        (r"self\.app\.after\(0,\s*lambda:\s*self\.results_tree\.insert\(\"\",\s*\"end\",\s*values=\(([^)]+)\),\s*tags=(\w+)\)\)",
         r"self.safe_tree_insert((\1), \2)"),
        
        # Pattern: inline tuple without tags
        (r"self\.app\.after\(0,\s*lambda:\s*self\.results_tree\.insert\(\"\",\s*\"end\",\s*values=\(([^)]+)\)\)\)",
         r"self.safe_tree_insert((\1))"),
    ]
    
    count = 0
    for pattern, replacement in replacements:
        new_content, n = re.subn(pattern, replacement, content)
        if n > 0:
            count += n
            content = new_content
    
    if count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ {os.path.basename(filepath)}: {count} replacement(s)")
    else:
        print(f"  ➖ {os.path.basename(filepath)}: no matches")
    
    return count


def main():
    print("=" * 60)
    print("P5.2 Migration: self.app.after(0, lambda: ...) → self.safe_tree_insert()")
    print("=" * 60)
    
    tab_files = sorted(f for f in os.listdir(TABS_DIR) 
                      if f.endswith('.py') and f != '__init__.py')
    
    total = 0
    for fname in tab_files:
        fpath = os.path.join(TABS_DIR, fname)
        total += migrate_file(fpath)
    
    print(f"\n{'='*60}")
    print(f"Total replacements: {total}")


if __name__ == '__main__':
    main()
