#!/usr/bin/env python3
"""Audit remaining user-facing Hinglish strings across src/ tab files.

Finds lines that contain Hinglish words AND are user-facing
(messagebox calls, text="..." labels, placeholder_text, status labels).
Skips comments (lines starting with # or inside docstrings heuristically).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

HINGLISH = re.compile(
    r"(kya|hai|nahi|karo|karein|kare |aapka|aapke|jaati|gayi|hain|hoga|hogi"
    r"|Kripya|kripya|dobara|pahle|pehle|kholkar|khol ke|bhej|dabayein|daba"
    r"|lagta|mila|mili|mile|ho paya|ho gaya|ho gayi|nhi|krna|karna|kren)",
    re.IGNORECASE,
)

USER_FACING = re.compile(
    r"(messagebox\.(showinfo|showwarning|showerror|askyesno|askokcancel|showquestion)"
    r"|text\s*=\s*[\"']|placeholder_text\s*=\s*[\"']"
    r"|\.configure\(\s*text\s*=\s*[\"']|update_status\(|set_status\(|log_warning\()"
)

SKIP_FILES = {
    # Already migrated (no need to re-audit)
    "settings_tab.py", "base_tab.py", "home_tab.py", "login_automation_tab.py",
    "activity_log_tab.py", "file_management_tab.py", "about_tab.py",
    "demand_tab.py", "mr_tracking_tab.py", "issued_mr_report_tab.py",
    "physical_complete_tab.py",
}


def is_comment(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return True
    # A line whose string content is inside a docstring region — rough skip:
    return stripped.startswith('"""') or stripped.startswith("'''")


def audit(path: str):
    hits = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        in_docstring = False
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring or is_comment(line):
                continue
            if HINGLISH.search(line) and USER_FACING.search(line):
                hits.append((lineno, line.rstrip("\n")))
    return hits


def main():
    total = 0
    for dirpath, _dirs, files in os.walk(SRC):
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            if fn in SKIP_FILES:
                continue
            path = os.path.join(dirpath, fn)
            hits = audit(path)
            if hits:
                rel = os.path.relpath(path, ROOT)
                print(f"\n=== {rel} ({len(hits)} hits) ===")
                for lineno, line in hits:
                    print(f"  {lineno}: {line[:160]}")
                total += len(hits)
    print(f"\nTotal user-facing Hinglish hits remaining: {total}")


if __name__ == "__main__":
    main()
