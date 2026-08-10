"""migrate_form_labels_merge.py — apply the COMBINED batch-1 + batch-2 string
maps to all migrated tab files. Reuses existing common.* keys so shared strings
(State:, Clear, 📥 Export to Excel, Output Action:, ...) finally get wrapped in
files that were skipped before (notably duplicate_mr_tab).

Usage:  python3 scripts/migrate_form_labels_merge.py
"""
import json
import re
import sys

sys.path.insert(0, "scripts")

from migrate_form_labels import MAP as MAP1  # noqa: E402
from migrate_form_labels2 import MAP as MAP2  # noqa: E402
from migrate_form_labels3 import MAP as MAP3  # noqa: E402

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# Union of all maps (later batches win on any collision)
MAP = dict(MAP1)
MAP.update(MAP2)
MAP.update(MAP3)

TARGET_FILES = [
    "src/tabs/mis_reports_tab.py",
    "src/tabs/msr_tab.py",
    "src/tabs/zero_mr_tab.py",
    "src/tabs/duplicate_mr_tab.py",
    "src/tabs/mb_entry_tab.py",
    "src/tabs/pending_bills_tab.py",
    "src/tabs/demand_tab.py",
    "src/tabs/wc_gen_tab.py",
    "src/tabs/musterroll_gen_tab.py",
    "src/tabs/mate_mr_gen_tab.py",
    "src/tabs/material_entry_tab.py",
    "src/tabs/mr_tracking_tab.py",
    "src/tabs/if_edit_tab.py",
    "src/tabs/sarkar_aapke_dwar_tab.py",
    "src/tabs/emb_verify_tab.py",
    "src/tabs/add_activity_tab.py",
    "src/tabs/scheme_closing_tab.py",
    "src/tabs/physical_complete_tab.py",
    "src/tabs/jobcard_verify_tab.py",
]

ATTR_PATTERNS = [
    re.compile(r'''(\b(?:text|placeholder_text|title)\s*=\s*)"([^"]*)"'''),
]


def main() -> None:
    en = json.load(open(EN_PATH, encoding="utf-8"))
    hi = json.load(open(HI_PATH, encoding="utf-8"))

    total = 0
    for path in TARGET_FILES:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        orig = src
        count = 0

        def wrap(m: re.Match) -> str:
            nonlocal count
            value = m.group(2)
            if value in MAP:
                key, _ = MAP[value]
                count += 1
                return f'{m.group(1)}tr("{key}")'
            return m.group(0)

        for pat in ATTR_PATTERNS:
            src = pat.sub(wrap, src)
        if src != orig:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            print(f"  {path}: {count} wrapped")
        total += count

    # Ensure every key from both maps exists in en.json (values from en map)
    added = 0
    for value, (key, hindi) in MAP.items():
        if key not in en:
            en[key] = value
            added += 1
        hi[key] = hindi

    json.dump(en, open(EN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nTotal wrapped this pass: {total}; new en.json keys: {added}")
    print(f"en.json: {len(en)} keys, hi.json: {len(hi)} keys")


if __name__ == "__main__":
    main()
