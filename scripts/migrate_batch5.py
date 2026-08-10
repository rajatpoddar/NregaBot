"""migrate_batch5.py — migrate SAFE UI strings in batch-5 tab files to tr().

⚠️ SAFETY: strings matched against the LIVE WEBSITE (By.ID / select_by_value /
LINK_TEXT), config save/load values, and dropdown options that act as internal
keys are INTENTIONALLY EXCLUDED. Notably sad_update's action dropdown options
("Dispose"/"Reject"/"In Progress"/"Pending") map to website values via
action_map and must NOT be translated.

Wraps:
  - text=/placeholder_text=/title= attributes (UI labels, buttons, hints)
  - messagebox.show*/ask* positional args (both args literal strings)
  - f-string messagebox dialogs via exact string replacements
  - sad_update bot-scan hint note (multi-line-ish user note)

Usage:  python3 scripts/migrate_batch5.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# string → (key, hindi). ONLY user-facing UI strings.
MAP = {
    # ── wagelist_send_tab ──
    "Financial Year:": ("common.financial_year", "वित्तीय वर्ष:"),
    "📥 Export to Excel": ("common.export_excel", "📥 एक्सेल में निर्यात करें"),

    # ── del_work_alloc_tab ──
    "Panchayat Name:": ("common.panchayat_name_label", "पंचायत का नाम:"),
    "From Date(s):": ("common.from_dates", "दिनांक से:"),
    "Clear": ("common.clear", "साफ़ करें"),
    "DD/MM/YYYY, DD/MM/YYYY": ("form.del_work_alloc.date_placeholder", "DD/MM/YYYY, DD/MM/YYYY"),

    # ── sad_update_tab ──
    "💡 Select Action:": ("form.sad.select_action", "💡 कार्रवाई चुनें:"),
    "Enter Acknowledgement Numbers (One per line):": ("form.sad.ack_label", "स्वीकृति संख्याएं दर्ज करें (प्रति पंक्ति एक):"),
    "Select Excel/CSV File:": ("form.sad.select_file", "एक्सेल/CSV फ़ाइल चुनें:"),
    "Browse": ("common.browse", "ब्राउज़ करें"),
    "💡 Bot will scan all columns for pattern X/Y/Z/A automatically.": ("form.sad.bot_scan_hint", "💡 बॉट X/Y/Z/A पैटर्न के लिए सभी कॉलम स्वचालित रूप से स्कैन करेगा।"),
    "Ack Number": ("form.sad.col_ack", "स्वीकृति संख्या"),
    "Status": ("form.sad.col_status", "स्थिति"),
    "Message": ("form.sad.col_message", "संदेश"),
    "🗑 Clear Logs": ("common.clear_logs", "🗑 लॉग साफ़ करें"),
    "📋 Copy Logs": ("common.copy_logs", "📋 लॉग कॉपी करें"),
    "Select .xlsx or .csv file": ("form.sad.select_excel_csv", ".xlsx या .csv फ़ाइल चुनें"),
    "Results": ("common.results", "परिणाम"),

    # ── abps_verify_tab ──
    "Panchayat:": ("form.abps.panchayat_label", "पंचायत:"),
    "Village:": ("form.abps.village_label", "गांव:"),
    "Export to PDF": ("common.export_pdf", "PDF में निर्यात करें"),
    "Save PDF Report": ("common.save_report", "PDF रिपोर्ट सहेजें"),

    # ── shared dialog strings ──
    "Reset Form?": ("dialogs.reset_form", "फ़ॉर्म रीसेट करें?"),
    "Are you sure?": ("confirm.are_you_sure", "क्या आप सुनिश्चित हैं?"),
    "Input Error": ("errors.input_error", "इनपुट त्रुटि"),
    "Retry": ("base.error_tab.retry_btn", "पुनः प्रयास"),
    "Copied": ("status.copied", "कॉपी हो गया"),
    "Input Needed": ("errors.input_needed", "इनपुट आवश्यक"),
    "No Data": ("errors.no_data", "कोई डेटा नहीं"),
    "Input Required": ("errors.input_required", "इनपुट आवश्यक"),
    "Confirm": ("dialogs.confirm", "पुष्टि करें"),
    "File Error": ("dialogs.file_error", "फ़ाइल त्रुटि"),
    "Automation Error": ("base.automation_error.title", "ऑटोमेशन त्रुटि"),

    # ── wagelist_send dialogs ──
    "Please select a Financial Year.": ("dialogs.select_fin_year", "कृपया वित्तीय वर्ष चुनें।"),
    "Retrying will process the remaining wagelists.\nContinue?": ("dialogs.retry_wagelists", "पुनः प्रयास शेष वेजलिस्टों को प्रोसेस करेगा।\nजारी रखें?"),

    # ── del_work_alloc dialogs ──
    "Panchayat Name is required.": ("dialogs.panchayat_name_required", "पंचायत का नाम आवश्यक है।"),
    "This will process ALL panchayats in the block. Continue?": ("dialogs.process_all_panchayats", "यह ब्लॉक के सभी पंचायतों को प्रोसेस करेगा। जारी रखें?"),
    "Clear all inputs and logs?": ("dialogs.reset_confirm_logs", "सभी इनपुट और लॉग साफ़ करें?"),

    # ── sad_update dialogs ──
    "Logs copied to clipboard!": ("dialogs.logs_copied", "लॉग क्लिपबोर्ड पर कॉपी हो गए!"),
    "Please go to 'Paste Text' or 'Upload File' tab and provide input.": ("dialogs.sad_provide_input", "कृपया 'Paste Text' या 'Upload File' टैब पर जाकर इनपुट दें।"),
    "Text area is empty.": ("dialogs.text_area_empty", "टेक्स्ट क्षेत्र खाली है।"),
    "Invalid file path.": ("dialogs.invalid_file_path", "अमान्य फ़ाइल पथ।"),
    "No valid patterns found in file.": ("dialogs.no_patterns_found", "फ़ाइल में कोई मान्य पैटर्न नहीं मिला।"),
    "No valid items found to process.": ("dialogs.no_valid_items", "प्रोसेस करने के लिए कोई मान्य आइटम नहीं मिला।"),

    # ── abps_verify dialogs ──
    "Please enter a Panchayat name.": ("dialogs.abps_panchayat_required", "कृपया पंचायत का नाम दर्ज करें।"),
}

# Exact source→replacement for f-string messagebox dialogs
FSTRING_REPLACEMENTS = [
    # wagelist_send: No wagelists for fin year
    ('messagebox.showwarning("No Wagelists", f"No wagelists were found for the financial year {fin_year}.")',
     'messagebox.showwarning(tr("dialogs.no_wagelists"), tr("dialogs.no_wagelists_fy", year=fin_year))'),
    # wagelist_send line 179 (multiline f-string) — check exact below
    ('messagebox.showwarning("No Wagelists",\n                                   f"No wagelists were found for the financial year {fin_year}.\\nPlease verify the financial year and try again.")',
     'messagebox.showwarning(tr("dialogs.no_wagelists"), tr("dialogs.no_wagelists_fy_retry", year=fin_year))'),
    # wagelist_send: Automation Error
    ('messagebox.showerror("Automation Error", f"An error occurred: {e}")',
     'messagebox.showerror(tr("base.automation_error.title"), tr("dialogs.an_error_occurred", error=e))'),
    # sad_update: Failed to copy
    ('messagebox.showerror("Error", f"Failed to copy: {e}")',
     'messagebox.showerror(tr("dialogs.error"), tr("dialogs.failed_copy", error=e))'),
]

# sad_update bot-scan hint is already in MAP (text= pattern). Nothing extra needed.

# messagebox positional args: messagebox.showXXX("Title", "Message") — both literal
MB_PATTERN = re.compile(r'''(messagebox\.\w+\(\s*)"([^"]+)"\s*,\s*"([^"]+)"''')

# text=/placeholder_text=/title= attrs with literal string values (skip f-strings)
ATTR_PATTERN = re.compile(r'''(?<!f)(\b(?:text|placeholder_text|title)\s*=\s*)"([^"]+)"''')

FILES = [
    "src/tabs/wagelist_send_tab.py",
    "src/tabs/del_work_alloc_tab.py",
    "src/tabs/sad_update_tab.py",
    "src/tabs/abps_verify_tab.py",
]


def main() -> None:
    en = json.load(open(EN_PATH, encoding="utf-8"))
    hi = json.load(open(HI_PATH, encoding="utf-8"))

    total = 0
    for path in FILES:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        orig = src
        count = 0

        def wrap_attr(m: re.Match) -> str:
            nonlocal count
            value = m.group(2)
            if value in MAP:
                key, _ = MAP[value]
                count += 1
                return f'{m.group(1)}tr("{key}")'
            return m.group(0)

        def wrap_mb(m: re.Match) -> str:
            nonlocal count
            prefix, title, msg = m.group(1), m.group(2), m.group(3)
            t_key = MAP.get(title)
            m_key = MAP.get(msg)
            if not t_key and not m_key:
                return m.group(0)
            new = prefix
            if t_key:
                new += f'tr("{t_key[0]}")'
                count += 1
            else:
                new += f'"{title}"'
            new += ", "
            if m_key:
                new += f'tr("{m_key[0]}")'
                count += 1
            else:
                new += f'"{msg}"'
            return new

        src = ATTR_PATTERN.sub(wrap_attr, src)
        src = MB_PATTERN.sub(wrap_mb, src)

        # f-string dialogs via exact replacement
        for old, new in FSTRING_REPLACEMENTS:
            if old in src:
                src = src.replace(old, new)
                count += 1

        if src != orig:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            print(f"  {path}: {count} wrapped")
        else:
            print(f"  {path}: 0 wrapped (no matches)")
        total += count

    # Add locale entries from MAP
    added = 0
    for value, (key, hindi) in MAP.items():
        if key not in en:
            en[key] = value
            added += 1
        hi[key] = hindi

    # Extra keys not in MAP (f-string dialog texts, dynamic)
    extra = {
        "dialogs.no_wagelists": ("No Wagelists", "कोई वेजलिस्ट नहीं"),
        "dialogs.no_wagelists_fy": (
            "No wagelists were found for the financial year {year}.",
            "वित्तीय वर्ष {year} के लिए कोई वेजलिस्ट नहीं मिली।",
        ),
        "dialogs.no_wagelists_fy_retry": (
            "No wagelists were found for the financial year {year}.\nPlease verify the financial year and try again.",
            "वित्तीय वर्ष {year} के लिए कोई वेजलिस्ट नहीं मिली।\nकृपया वित्तीय वर्ष जांचें और पुनः प्रयास करें।",
        ),
        "dialogs.an_error_occurred": (
            "An error occurred: {error}",
            "एक त्रुटि हुई: {error}",
        ),
        "dialogs.failed_copy": (
            "Failed to copy: {error}",
            "कॉपी विफल: {error}",
        ),
        "dialogs.error": ("Error", "त्रुटि"),
    }
    for key, (val, hind) in extra.items():
        if key not in en:
            en[key] = val
            added += 1
        hi[key] = hind

    json.dump(en, open(EN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nTotal wrapped: {total}; new en.json keys: {added}")
    print(f"en.json: {len(en)} keys, hi.json: {len(hi)} keys")


if __name__ == "__main__":
    main()
