#!/usr/bin/env python3
"""
P6.2+P6.3 — Migrate to select_dropdown() and _find() helpers.

Patterns migrated:
  1) self._select_by_text_case_insensitive(Select(wait.until(...)), value)
     → self.select_dropdown(driver, element_id, value)

  2) driver.find_element(By.ID, "...")
     → self._find(driver, By.ID, "...")

  3) driver.find_element(By.XPATH, "...")
     → self._find(driver, By.XPATH, "...")

Run:  python3 scripts/migrate_select_dropdown.py
"""

import os
import re

TABS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "tabs")


def find_driver_var(lines, line_idx):
    """Scan backwards from line_idx to find the 'driver = ...' assignment."""
    for i in range(line_idx - 1, max(line_idx - 30, 0), -1):
        m = re.match(r'^(\s+)(\w+)\s*=\s*(?:self\.app\.get_driver\(\)|driver)', lines[i])
        if m:
            return m.group(2)
    return 'driver'


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    lines = content.splitlines(keepends=True)

    # ── Pattern 1: select_dropdown ──
    # Match: self._select_by_text_case_insensitive(Select(wait.until(EC.element_to_be_clickable((By.ID, X)))), Y)
    pat1 = re.compile(
        r'self\._select_by_text_case_insensitive\('
        r'Select\('
        r'wait\.until\(EC\.element_to_be_clickable\(\(By\.ID,\s*([^)]+)\)\)\)'
        r'\),\s*([^)]+)\)'
    )

    replacements_1 = 0
    new_lines = []
    for i, line in enumerate(lines):
        new_line = line
        for m in pat1.finditer(line):
            element_id = m.group(1).strip()
            value = m.group(2).strip()
            dv = find_driver_var(lines, i)
            new_call = f'self.select_dropdown({dv}, {element_id}, {value})'
            new_line = new_line.replace(m.group(0), new_call)
            replacements_1 += 1
        new_lines.append(new_line)
    lines = new_lines
    content = ''.join(lines)

    # ── Pattern 2: driver.find_element(By.ID, "...") → self._find(...) ──
    # Only match inside method bodies (indented lines)
    pat2 = re.compile(
        r'^(\s+)driver\.find_element\(By\.ID,\s*\"([^\"]+)\"\)',
        re.MULTILINE
    )
    replacements_2 = len(pat2.findall(content))
    content = pat2.sub(
        r'\1self._find(driver, By.ID, "\2")',
        content
    )

    # ── Pattern 3: driver.find_element(By.XPATH, "...") → self._find(...) ──
    pat3 = re.compile(
        r'^(\s+)driver\.find_element\(By\.XPATH,\s*\"([^\"]+)\"\)',
        re.MULTILINE
    )
    replacements_3 = len(pat3.findall(content))
    content = pat3.sub(
        r'\1self._find(driver, By.XPATH, "\2")',
        content
    )

    total = replacements_1 + replacements_2 + replacements_3
    if total == 0:
        return 0

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    details = []
    if replacements_1: details.append(f'{replacements_1} select_dropdown')
    if replacements_2: details.append(f'{replacements_2} _find(By.ID)')
    if replacements_3: details.append(f'{replacements_3} _find(By.XPATH)')
    return f'{", ".join(details)}'


def main():
    print("=" * 60)
    print("P6.2+P6.3 — select_dropdown() & _find() Migration")
    print("=" * 60)

    total_reports = []

    for filename in sorted(os.listdir(TABS_DIR)):
        if not filename.endswith('.py'):
            continue

        filepath = os.path.join(TABS_DIR, filename)
        try:
            result = process_file(filepath)
            if result:
                print(f"  ✅ {filename}: {result}")
                total_reports.append((filename, result))
        except Exception as e:
            print(f"  ❌ {filename}: ERROR - {e}")

    print("-" * 60)
    if total_reports:
        for fname, desc in total_reports:
            print(f"  ✅ {fname}: {desc}")
    print(f"Total files modified: {len(total_reports)}")
    print("=" * 60)


if __name__ == '__main__':
    main()
