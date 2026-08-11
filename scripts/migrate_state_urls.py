#!/usr/bin/env python3
"""migrate_state_urls.py — state-aware portal URLs.

Wraps every portal URL config reference across the tabs —
    config.X_CONFIG["url"] / config.X_CONFIG["base_url"]
with
    self.resolve_portal_url(config.X_CONFIG["url"])
so vbgramg transaction URLs get re-hosted to the user's state host
(e.g. Rajasthan → vbgramgde3.dord.gov.in) at runtime.

Run from the project root:  venv/bin/python scripts/migrate_state_urls.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABS_DIR = ROOT / "src" / "tabs"

# config.MUSTER_ROLL_CONFIG["base_url"]  /  config.MR_FILL_CONFIG["url"]
PATTERN = re.compile(r'config\.([A-Z_]+)_CONFIG\["(url|base_url)"\]')

changed = []
for path in sorted(TABS_DIR.glob("*.py")):
    text = path.read_text(encoding="utf-8")

    def _wrap(match: "re.Match") -> str:
        return f'self.resolve_portal_url(config.{match.group(1)}_CONFIG["{match.group(2)}"])'

    new_text = PATTERN.sub(_wrap, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        changed.append(path.name)

print(f"Updated {len(changed)} tab(s): {', '.join(changed) if changed else 'none'}")
