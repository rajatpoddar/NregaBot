#!/usr/bin/env python3
"""
P6.1 — Replace `self.app.stop_events[self.automation_key].is_set()`
with `self.is_stopped()` in all tab files.

Run:  python3 scripts/migrate_is_stopped.py
"""

import os
import re

TABS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "tabs")

# Pattern: self.app.stop_events[self.automation_key].is_set()
# This could also be:
#   self.app.stop_events[self.automation_key].is_set()
#   self.app.stop_events[self.automation_key].is_set() :
#   not self.app.stop_events[self.automation_key].is_set()
OLD_PATTERN = "self.app.stop_events[self.automation_key].is_set()"
NEW_PATTERN = "self.is_stopped()"

# For the negated version: not self.app.stop_events[self.automation_key].is_set()
OLD_NEGATED = "not self.app.stop_events[self.automation_key].is_set()"
NEW_NEGATED = "not self.is_stopped()"


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    count = content.count(OLD_PATTERN)
    if count == 0:
        return 0

    # Replace negated first (longer match) so we don't double-replace
    content = content.replace(OLD_NEGATED, NEW_NEGATED)
    content = content.replace(OLD_PATTERN, NEW_PATTERN)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return count


def main():
    print("=" * 60)
    print("P6.1 — is_stopped() Migration")
    print("=" * 60)

    total_replaced = 0
    file_count = 0

    for filename in sorted(os.listdir(TABS_DIR)):
        if not filename.endswith('.py'):
            continue

        filepath = os.path.join(TABS_DIR, filename)
        count = process_file(filepath)

        if count > 0:
            print(f"  ✅ {filename}: {count} replacement(s)")
            file_count += 1
            total_replaced += count

    print("-" * 60)
    print(f"Files modified: {file_count}")
    print(f"Total replacements: {total_replaced}")
    print("=" * 60)


if __name__ == '__main__':
    main()
