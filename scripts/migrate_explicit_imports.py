#!/usr/bin/env python3
"""
migrate_explicit_imports.py
P7.1 — Replace `from ._imports import *` wildcard imports with explicit
named imports from the shared import hub, based on AST usage analysis.

Why:
  - Wildcard imports (`import *`) hide which names a module actually uses.
  - Every tab imported pandas/openpyxl/selenium *even when unused* just by
    importing `_imports` (pandas is only truly needed by 2 tabs).
  - Explicit imports make dependencies visible and reduce import cost per tab.

How it works:
  1. Reads the `__all__` list from `src/tabs/_imports.py`.
  2. Parses every tab file with `ast`, collects every Name node actually used.
  3. Replaces the wildcard line with `from ._imports import <used names>`.

Safety:
  - Only rewrites files that currently contain the wildcard import.
  - Keeps `_imports.py` as the single import hub (source module unchanged).
  - After running, run `python -m py_compile` + an import smoke test on all tabs.

Run:  python scripts/migrate_explicit_imports.py
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABS_DIR = ROOT / "src" / "tabs"
IMPORTS_FILE = TABS_DIR / "_imports.py"

# Matches:  from ._imports import *   (with optional comment)
WILDCARD_RE = re.compile(
    r"^\s*from\s+\._imports\s+import\s+\*\s*(?:#.*)?$",
    re.MULTILINE,
)


def get_all_names() -> list:
    """Extract the `__all__` list from _imports.py."""
    tree = ast.parse(IMPORTS_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id == "__all__":
                return [
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
    return []


def collect_used_names(source: str) -> set:
    """Return the set of all identifier names referenced in the file."""
    tree = ast.parse(source)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
    return used


def main() -> int:
    all_names = get_all_names()
    if not all_names:
        print("ERROR: could not read __all__ from _imports.py", file=sys.stderr)
        return 1

    changed = 0
    skipped = 0
    for path in sorted(TABS_DIR.glob("*.py")):
        src = path.read_text(encoding="utf-8")
        if not WILDCARD_RE.search(src):
            continue

        used = collect_used_names(src)
        needed = [name for name in all_names if name in used]

        if not needed:
            print(f"SKIP (no _imports names used): {path.name}")
            skipped += 1
            continue

        line = "from ._imports import " + ", ".join(needed) + "  # noqa: F401\n"
        new_src, n = WILDCARD_RE.subn(line, src, count=1)
        if n != 1:
            print(f"WARN: could not rewrite {path.name}", file=sys.stderr)
            continue

        path.write_text(new_src, encoding="utf-8")
        print(f"OK   {path.name}: {len(needed)} names -> {', '.join(needed)}")
        changed += 1

    print(f"\nDone. {changed} file(s) migrated, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
