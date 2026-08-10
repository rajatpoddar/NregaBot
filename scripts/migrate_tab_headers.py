"""migrate_tab_headers.py — wrap every `_create_header_card(..., "Title", "Subtitle")`
call in `src/tabs/*.py` with tr("tab.<slug>.title") / tr("tab.<slug>.subtitle").

The slug is derived from the FILE stem (e.g. `demand_tab.py` → `demand`), so keys
are stable regardless of title wording. After editing the code it prints the full
(key → English) map so en.json/hi.json entries can be added.

Usage:  python3 scripts/migrate_tab_headers.py
"""
import re
import glob
import os
import json

PATTERN = re.compile(
    r'(_create_header_card\(\s*[^,]+,\s*"[^"]*",\s*)"([^"]*)"\s*,\s*"([^"]*)"'
)


def slug_for(path: str) -> str:
    base = os.path.basename(path).replace(".py", "")
    base = base.replace("_tab", "")
    # Keep a readable, stable slug
    return base


def main() -> None:
    results = {}  # slug -> (title, subtitle)
    changed = 0
    for f in sorted(glob.glob("src/tabs/*.py")):
        with open(f, encoding="utf-8") as fh:
            src = fh.read()
        slug = slug_for(f)

        def repl(m: re.Match) -> str:
            prefix, title, subtitle = m.group(1), m.group(2), m.group(3)
            results[slug] = (title, subtitle)
            return (f'{prefix}tr("tab.{slug}.title"), '
                    f'tr("tab.{slug}.subtitle")')

        new_src, n = PATTERN.subn(repl, src)
        if n:
            # Ensure tr import exists
            if "from src.i18n import tr" not in new_src:
                # Insert after the last `from src...` import line
                lines = new_src.split("\n")
                idx = -1
                for i, line in enumerate(lines):
                    if line.startswith("from src"):
                        idx = i
                if idx >= 0:
                    lines.insert(idx + 1, "from src.i18n import tr")
                else:
                    # Fallback: after first non-comment line
                    for i, line in enumerate(lines):
                        if line.strip() and not line.strip().startswith("#"):
                            lines.insert(i, "from src.i18n import tr")
                            break
                new_src = "\n".join(lines)
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(new_src)
            changed += 1
            print(f"  migrated {os.path.basename(f)} ({n} call(s))")

    print(f"\n== {changed} files changed, {len(results)} header cards ==")
    print("\n== en.json additions (paste into the locales file) ==")
    for slug in sorted(results):
        title, subtitle = results[slug]
        print(f'  "tab.{slug}.title": "{title}",')
        print(f'  "tab.{slug}.subtitle": "{subtitle}",')


if __name__ == "__main__":
    main()
