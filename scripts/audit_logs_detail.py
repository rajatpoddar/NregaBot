#!/usr/bin/env python3
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

HINGLISH = re.compile(
    r"(kya|hai|nahi|karo|karein|aapka|aapke|jaati|gayi|hain|hoga|hogi|mila|mili|mile|ho paya|ho gaya|ho gayi|nhi|karna|kren|kar de|kar do|kare)",
    re.IGNORECASE,
)
LOG_CALL = re.compile(r"\.log_(info|warning|error|success)\(")

FILES = [
    "src/tabs/musterroll_gen_tab.py",
    "src/tabs/mate_mr_gen_tab.py",
    "src/tabs/work_allocation_tab.py",
    "src/tabs/material_entry_tab.py",
    "src/tabs/ekyc_report_tab.py",
    "src/tabs/delete_applicant_tab.py",
    "src/tabs/del_demand_tab.py",
]

for rel in FILES:
    path = os.path.join(ROOT, rel)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print(f"\n=== {rel} ===")
    for i, line in enumerate(lines, 1):
        if LOG_CALL.search(line) and HINGLISH.search(line):
            print(f"  {i}: {line.rstrip()}")
