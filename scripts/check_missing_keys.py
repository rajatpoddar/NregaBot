"""check_missing_keys.py — find every tr("...") key used in src/ and report
which keys are missing from each locale file (en / hi / kn / bn / ...).
Also lists ALL used keys grouped by prefix so new keys can be reviewed
before adding translations.

Usage:  python3 scripts/check_missing_keys.py
"""
import re
import glob
import json
from collections import Counter
import os

LOCALES_DIR = "src/locales"


def scan_used_keys() -> set:
    used = set()
    pattern = re.compile(r"""tr\(\s*(['"])([a-z_][a-z0-9_.]*)\1""")
    for f in glob.glob("src/**/*.py", recursive=True):
        if "locales" in f or f.endswith("/i18n.py"):
            continue
        try:
            src = open(f, encoding="utf-8").read()
        except Exception:
            continue
        used |= set(m.group(2) for m in pattern.finditer(src))
    return used


def main() -> None:
    used = scan_used_keys()
    locale_files = sorted(
        f for f in os.listdir(LOCALES_DIR) if f.endswith(".json")
    )
    locales = {}
    for f in locale_files:
        locales[f] = json.load(open(os.path.join(LOCALES_DIR, f), encoding="utf-8"))

    print(f"Keys used in code: {len(used)}")
    total_missing = 0
    for f in locale_files:
        missing = sorted(k for k in used if k not in locales[f])
        total_missing += len(missing)
        print(f"Missing in {f}: {len(missing)}")
        for k in missing:
            print(f"  {k}")
    print(f"TOTAL missing across locales: {total_missing}")

    # Group all used keys by prefix for review
    prefixes = Counter(k.split(".")[0] for k in used)
    print("\n=== Used keys by prefix ===")
    for p in sorted(prefixes):
        print(f"  {p}: {prefixes[p]}")


if __name__ == "__main__":
    main()
