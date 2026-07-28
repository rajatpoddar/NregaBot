#!/usr/bin/env python3
"""
P5.1 extension — Remove lazy `import pandas as pd` and
`from webdriver_manager.chrome import ChromeDriverManager`
from method bodies. Add them at module level.

Run:  python3 scripts/migrate_pandas_wdm.py
"""

import os
import re

TABS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "tabs")

# Only clean these 3 files
TARGET_FILES = {
    "mr_tracking_tab.py",
    "issued_mr_report_tab.py",
    "nmms_attendance_tab.py",
}


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    lines = content.splitlines(keepends=True)

    # ── Detect which module-level imports are needed ──
    needs_pandas = 'import pandas as pd' in content
    needs_wdm = 'ChromeDriverManager' in content

    # ── Remove lazy imports from method bodies ──
    new_lines = []
    removed_pandas = 0
    removed_wdm = 0

    for line in lines:
        stripped = line.strip()
        # Match indented (method-body) imports
        if line[0] in (' ', '\t'):
            if stripped == 'import pandas as pd':
                removed_pandas += 1
                continue
            if stripped == 'from webdriver_manager.chrome import ChromeDriverManager':
                removed_wdm += 1
                continue
        new_lines.append(line)

    content = ''.join(new_lines)

    # ── Add module-level imports (if not already present & if used) ──
    has_module_pandas = any(
        l.strip() == 'import pandas as pd' and l[0] not in (' ', '\t')
        for l in new_lines
    )
    has_module_wdm = any(
        l.strip() == 'from webdriver_manager.chrome import ChromeDriverManager' and l[0] not in (' ', '\t')
        for l in new_lines
    )

    insert_lines = []
    if needs_pandas and not has_module_pandas and removed_pandas > 0:
        insert_lines.append('import pandas as pd\n')
    if needs_wdm and not has_module_wdm and removed_wdm > 0:
        insert_lines.append('from webdriver_manager.chrome import ChromeDriverManager\n')

    if insert_lines:
        # Find insertion point: after last module-level import block
        last_import_idx = -1
        for i, line in enumerate(new_lines):
            s = line.strip()
            if s.startswith(('import ', 'from ')) and line[0] not in (' ', '\t'):
                last_import_idx = i
        # Insert after the last module-level import
        insert_at = last_import_idx + 1
        # Add blank line before if needed
        if insert_at < len(new_lines) and new_lines[insert_at - 1].strip():
            insert_lines.insert(0, '\n')
        for il in reversed(insert_lines):
            new_lines.insert(insert_at, il)
        content = ''.join(new_lines)

    total = removed_pandas + removed_wdm
    if total == 0:
        return 0, 0, 0

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return total, removed_pandas, removed_wdm


def main():
    print("=" * 60)
    print("Pandas & webdriver_manager Lazy Import Cleanup")
    print("=" * 60)

    total_p = 0
    total_w = 0
    files_modified = 0

    for filename in sorted(os.listdir(TABS_DIR)):
        if filename not in TARGET_FILES:
            continue
        filepath = os.path.join(TABS_DIR, filename)
        total, p, w = process_file(filepath)
        if total > 0:
            details = []
            if p: details.append(f'{p}x import pandas as pd')
            if w: details.append(f'{w}x from webdriver_manager.chrome import ChromeDriverManager')
            print(f"  ✅ {filename}: {', '.join(details)}")
            files_modified += 1
            total_p += p
            total_w += w

    print("-" * 60)
    print(f"Files modified: {files_modified}")
    print(f"import pandas as pd: {total_p} removed")
    print(f"from webdriver_manager: {total_w} removed")
    print(f"Total: {total_p + total_w} lazy import lines cleaned")
    print("=" * 60)


if __name__ == '__main__':
    main()
