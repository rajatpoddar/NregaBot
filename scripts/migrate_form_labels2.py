"""migrate_form_labels2.py — batch 2: migrate in-tab form strings in
mis_reports_tab, msr_tab, zero_mr_tab, duplicate_mr_tab, mb_entry_tab,
pending_bills_tab to tr() and add locale entries.

Reuses the same safe approach as migrate_form_labels.py (only strings present
in MAP are touched; text=/placeholder_text=/title= patterns only).

Usage:  python3 scripts/migrate_form_labels2.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

MAP = {
    # ── shared (already-existing common.* reused where possible) ──
    "Deselect All": ("common.deselect_all", "सभी अचयनित करें"),
    "Reports to Download:": ("form.mis_reports.reports_to_download", "डाउनलोड करने योग्य रिपोर्ट:"),
    "Save MIS Reports As": ("form.mis_reports.save_as", "एमआईएस रिपोर्ट इस रूप में सहेजें"),
    "Financial Year:": ("form.zero_mr.financial_year", "वित्तीय वर्ष:"),
    "Enter one item per line. Format: SearchKey,MSRNo": ("form.zero_mr.format_hint", "प्रति पंक्ति एक आइटम दर्ज करें। प्रारूप: SearchKey,MSRNo"),
    "Retry Mode (Text)": ("form.zero_mr.retry_mode", "पुनः प्रयास मोड (टेक्स्ट)"),
    "Panchayat Name": ("form.msr.panchayat_name", "पंचायत का नाम"),
    "Verify Amount (₹)": ("form.msr.verify_amount", "राशि सत्यापित करें (₹)"),
    "Reject if amount does not match this value.": ("form.msr.reject_hint", "यदि राशि इस मान से मेल नहीं खाती तो अस्वीकार करें।"),
    "MB No.": ("form.mb_entry.mb_no", "एमबी सं."),
    "Auto": ("form.mb_entry.auto", "ऑटो"),
    "💡 Usage Notes": ("form.mb_entry.usage_notes", "💡 उपयोग नोट्स"),
    "No Work Codes": ("form.mb_entry.no_work_codes", "कोई वर्क कोड नहीं"),
    "No work codes entered. This will process ALL available works from the 'Select Work' dropdown on the portal.\\n\\nContinue?": ("form.mb_entry.no_work_codes_msg", "कोई वर्क कोड दर्ज नहीं किया गया। यह पोर्टल पर 'Select Work' ड्रॉपडाउन से सभी उपलब्ध कार्यों को संसाधित करेगा।\\n\\nजारी रखें?"),
    "💸 Pending Bills Scraper": ("form.pending_bills.scraper_title", "💸 लंबित बिल स्क्रैपर"),
    "State *": ("form.pending_bills.state_required", "राज्य *"),
    "District *": ("form.pending_bills.district_required", "जिला *"),
    "Block *": ("form.pending_bills.block_required", "ब्लॉक *"),
    "Panchayat": ("common.panchayat_col", "पंचायत"),
    "Financial Year": ("form.pending_bills.financial_year", "वित्तीय वर्ष"),
    "💡 How it works": ("common.how_it_works", "💡 यह कैसे काम करता है"),
    "Summary (one row per panchayat)": ("form.pending_bills.summary_hint", "सारांश (प्रति पंचायत एक पंक्ति)"),
    "Save Pending Bills Report": ("form.pending_bills.save_report", "लंबित बिल रिपोर्ट सहेजें"),
    "Summary": ("form.pending_bills.summary_title", "सारांश"),
}

TARGET_FILES = [
    "src/tabs/mis_reports_tab.py",
    "src/tabs/msr_tab.py",
    "src/tabs/zero_mr_tab.py",
    "src/tabs/duplicate_mr_tab.py",
    "src/tabs/mb_entry_tab.py",
    "src/tabs/pending_bills_tab.py",
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

    added = 0
    for value, (key, hindi) in MAP.items():
        if key not in en:
            en[key] = value
            added += 1
        hi[key] = hindi

    json.dump(en, open(EN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nTotal wrapped: {total}; new en.json keys: {added}")
    print(f"en.json: {len(en)} keys, hi.json: {len(hi)} keys")


if __name__ == "__main__":
    main()
