"""Build kn.json / bn.json / hinglish.json from translation part files. Reports coverage.

NOTE: src/locales/kn.json, bn.json and hinglish.json are GENERATED artifacts.
Never edit the .json files directly — edit the part files below
(scripts/translations_{kn,bn,hing}_1..5.py) and re-run this script.

Exit codes: 0 = all good (full coverage, placeholders intact);
            1 = missing keys, unused entries, or placeholder mismatches.
"""
import json
import os
import re
import sys

# Allow running from repo root or scripts/ dir
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from translations_kn_1 import KN1
from translations_kn_2 import KN2
from translations_kn_3 import KN3
from translations_kn_4 import KN4
from translations_kn_5 import KN5
from translations_bn_1 import BN1
from translations_bn_2 import BN2
from translations_bn_3 import BN3
from translations_bn_4 import BN4
from translations_bn_5 import BN5
from translations_hing_1 import HING1
from translations_hing_2 import HING2
from translations_hing_3 import HING3
from translations_hing_4 import HING4
from translations_hing_5 import HING5

en = json.load(open("src/locales/en.json", encoding="utf-8"))

KN = {}
for part in (KN1, KN2, KN3, KN4, KN5):
    KN.update(part)

BN = {}
for part in (BN1, BN2, BN3, BN4, BN5):
    BN.update(part)

HING = {}
for part in (HING1, HING2, HING3, HING4, HING5):
    HING.update(part)


def _placeholders(text: str) -> list:
    """Sorted list of {token}s — stricter than set comparison (catches dupes)."""
    return sorted(re.findall(r"\{([a-z_]+)\}", text, re.I))


failures = False
for code, table in (("kn", KN), ("bn", BN), ("hinglish", HING)):
    missing = [k for k in en if k not in table]
    unused = [k for k in table if k not in en]
    bad_ph = [
        (k, en[k], table.get(k))
        for k in en
        if isinstance(en[k], str)
        and _placeholders(en[k]) != _placeholders(str(table.get(k, "")))
    ]
    print(f"{code}: en keys {len(en)} | provided {len(table)} | missing {len(missing)} | unused {len(unused)} | placeholder mismatches {len(bad_ph)}")
    if missing:
        failures = True
        print("  MISSING:", ", ".join(missing[:15]))
    if unused:
        failures = True
        print("  UNUSED:", ", ".join(unused[:15]))
    for k, src, dst in bad_ph[:5]:
        failures = True
        print(f"  PLACEHOLDER MISMATCH {k}: en={src!r} vs {code}={dst!r}")
    out = {k: table.get(k, en[k]) for k in en}
    with open(f"src/locales/{code}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  {code}.json written: {len(out)} keys")

sys.exit(1 if failures else 0)
