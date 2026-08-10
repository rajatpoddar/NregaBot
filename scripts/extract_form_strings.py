"""extract_form_strings.py — list unique hardcoded user-facing strings
(text="...", placeholder_text="...") in the given tab files, so a
translation mapping can be built.

Usage:  python3 scripts/extract_form_strings.py <file1> <file2> ...
"""
import re
import sys
from collections import Counter

STR_PATTERNS = [
    re.compile(r'''\btext\s*=\s*"([^"]{2,})"'''),
    re.compile(r'''\bplaceholder_text\s*=\s*"([^"]{2,})"'''),
    re.compile(r'''\btitle\s*=\s*"([^"]{2,})"'''),
    re.compile(r'''\.set\(\\?"([^"]{3,})"'''),  # StringVar .set("...")
]


def extract(path: str) -> Counter:
    counter = Counter()
    try:
        src = open(path, encoding="utf-8").read()
    except Exception as e:
        print(f"!! {path}: {e}")
        return counter
    for pat in STR_PATTERNS:
        for m in pat.finditer(src):
            s = m.group(1).strip()
            # skip pure emoji / icon / color-only strings
            if not s or s.startswith(("#", "{", "(")):
                continue
            if len(s) > 80:
                continue
            counter[s] += 1
    return counter


def main() -> None:
    for path in sys.argv[1:]:
        counter = extract(path)
        print(f"\n===== {path} ({sum(counter.values())} hits, {len(counter)} unique) =====")
        for s, n in counter.most_common():
            print(f"  x{n:<3} {s}")


if __name__ == "__main__":
    main()
