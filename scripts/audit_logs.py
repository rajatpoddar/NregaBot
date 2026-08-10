#!/usr/bin/env python3
"""Count Hinglish inside log_*() calls across src/ — these show in the
Logs panel, so per the 'logs stay English' decision they should be English.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

HINGLISH = re.compile(
    r"(kya|hai|nahi|karo|karein|kare |aapka|aapke|jaati|gayi|hain|hoga|hogi"
    r"|Kripya|kripya|dobara|pahle|pehle|kholkar|khol ke|bhej|dabayein|daba"
    r"|lagta|mila|mili|mile|ho paya|ho gaya|ho gayi|nhi|krna|karna|kren)",
    re.IGNORECASE,
)

LOG_CALL = re.compile(r"\.log_(info|warning|error|success)\(")

SKIP = {
    "settings_tab.py", "base_tab.py", "home_tab.py", "login_automation_tab.py",
    "activity_log_tab.py", "file_management_tab.py", "about_tab.py",
    "demand_tab.py", "mr_tracking_tab.py", "issued_mr_report_tab.py",
    "physical_complete_tab.py", "utils.py",
}


def main():
    total = 0
    per_file = []
    for dirpath, _dirs, files in os.walk(SRC):
        for fn in sorted(files):
            if not fn.endswith(".py") or fn in SKIP:
                continue
            path = os.path.join(dirpath, fn)
            count = 0
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if LOG_CALL.search(line) and HINGLISH.search(line):
                        count += 1
            if count:
                rel = os.path.relpath(path, ROOT)
                per_file.append((count, rel))
                total += count
    per_file.sort(reverse=True)
    for count, rel in per_file:
        print(f"  {count:3d}  {rel}")
    print(f"\nTotal Hinglish log messages remaining: {total}")


if __name__ == "__main__":
    main()
