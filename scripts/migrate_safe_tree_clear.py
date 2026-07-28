#!/usr/bin/env python3
"""
migrate_safe_tree_clear.py — P5.3

Replaces two patterns with self.safe_tree_clear():

Pattern 1 — thread-safe wrapper (9 files):
    self.app.after(0, lambda: [self.results_tree.delete(item)
        for item in self.results_tree.get_children()])

Pattern 2 — direct for loop (23 files):
    for item in self.results_tree.get_children():
        self.results_tree.delete(item)
"""

import os
import re

TABS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "tabs")


def migrate_file(filepath: str) -> int:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    count = 0

    # Pattern 1: self.app.after(0, lambda: [self.results_tree.delete(item) for item in self.results_tree.get_children()])
    # This is a single-line pattern
    pattern1 = re.compile(
        r"self\.app\.after\(0,\s*lambda:\s*\[self\.results_tree\.delete\(item\)\s+for\s+item\s+in\s+self\.results_tree\.get_children\(\)\]\)"
    )
    new_content, n = pattern1.subn("self.safe_tree_clear()", content)
    if n > 0:
        count += n
        content = new_content

    # Pattern 2: for item in self.results_tree.get_children():\n    self.results_tree.delete(item)
    # This spans two lines
    pattern2 = re.compile(
        r"for\s+item\s+in\s+self\.results_tree\.get_children\(\):\s*\n\s+self\.results_tree\.delete\(item\)"
    )
    new_content, n = pattern2.subn("self.safe_tree_clear()", content)
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
    print("P5.3 Migration: → self.safe_tree_clear()")
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
