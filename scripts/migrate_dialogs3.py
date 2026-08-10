"""migrate_dialogs3.py — wrap messagebox.show*/ask* positional title+message
arguments in batch-3 tab files with tr() keys and add locale entries.

The regex-based form migration can't see messagebox positional args, so these
are handled here with a dedicated string→key map.

Usage:  python3 scripts/migrate_dialogs3.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

MAP = {
    "Reset Form?": ("dialogs.reset_form", "फॉर्म रीसेट करें?"),
    "This will clear all inputs and results. Continue?": ("dialogs.reset_confirm_results", "यह सभी इनपुट और परिणाम साफ़ कर देगा। जारी रखें?"),
    "Input Error": ("errors.input_error", "इनपुट त्रुटि"),
    "Panchayat Name and Verify Amount are required.": ("dialogs.emb_verify_required", "पंचायत का नाम और सत्यापन राशि आवश्यक है।"),
    "Input Required": ("errors.input_required", "इनपुट आवश्यक"),
    "Please provide at least one work key.": ("dialogs.add_activity_need_key", "कृपया कम से कम एक वर्क की प्रदान करें।"),
    "Please enter a Unit Price and Quantity.": ("dialogs.add_activity_need_price", "कृपया इकाई मूल्य और मात्रा दर्ज करें।"),
    "Clear all inputs and logs?": ("dialogs.reset_confirm_logs", "सभी इनपुट और लॉग साफ़ करें?"),
    "Are you sure? This will clear all inputs.": ("dialogs.reset_confirm_inputs", "क्या आप सुनिश्चित हैं? यह सभी इनपुट साफ़ कर देगा।"),
    "All fields and at least one work code are required.": ("dialogs.scheme_closing_required", "सभी फ़ील्ड और कम से कम एक वर्क कोड आवश्यक है।"),
    "Completion Certificate Start No must be a number.": ("dialogs.cert_start_must_be_number", "पूर्णता प्रमाणपत्र आरंभ संख्या संख्या होनी चाहिए।"),
    "Browser Not Found": ("errors.browser_not_found", "ब्राउज़र नहीं मिला"),
    "Please launch a browser first.": ("errors.browser_required", "कृपया पहले ब्राउज़र लॉन्च करें।"),
    "Confirm Scheme Closing": ("dialogs.confirm_scheme_closing", "योजना समापन की पुष्टि करें"),
    "No Data": ("errors.no_data", "कोई डेटा नहीं"),
    "No results to export.": ("errors.no_results_export", "निर्यात करने के लिए कोई परिणाम नहीं।"),
    "Input Needed": ("errors.input_needed", "इनपुट आवश्यक"),
    "Panchayat Name is required for report title.": ("dialogs.panchayat_for_report", "रिपोर्ट शीर्षक के लिए पंचायत का नाम आवश्यक है।"),
    "Panchayat name is required.": ("dialogs.panchayat_required", "पंचायत का नाम आवश्यक है।"),
    "Panchayat, Work Category, and at least one Work Code are required.": ("dialogs.physical_complete_required", "पंचायत, कार्य श्रेणी और कम से कम एक वर्क कोड आवश्यक है।"),
    "Please enter a Village name or check 'Process all villages'.": ("dialogs.jobcard_village_required", "कृपया गांव का नाम दर्ज करें या 'सभी गांवों की प्रक्रिया करें' चुनें।"),
    "Success": ("status.success", "सफल"),
    "Are you sure?": ("confirm.are_you_sure", "क्या आप सुनिश्चित हैं?"),
}

# positional messagebox patterns: messagebox.showXXX("Title", "Message")
PATTERNS = [
    re.compile(r'''(messagebox\.\w+\(\s*)"([^"]+)"\s*,\s*"([^"]+)"'''),
]


def main() -> None:
    en = json.load(open(EN_PATH, encoding="utf-8"))
    hi = json.load(open(HI_PATH, encoding="utf-8"))

    files = [
        "src/tabs/emb_verify_tab.py",
        "src/tabs/add_activity_tab.py",
        "src/tabs/scheme_closing_tab.py",
        "src/tabs/physical_complete_tab.py",
        "src/tabs/jobcard_verify_tab.py",
    ]

    total = 0
    for path in files:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        orig = src
        count = 0

        def wrap(m: re.Match) -> str:
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

        for pat in PATTERNS:
            src = pat.sub(wrap, src)
        if src != orig:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            print(f"  {path}: {count} args wrapped")
        total += count

    added = 0
    for value, (key, hindi) in MAP.items():
        if key not in en:
            en[key] = value
            added += 1
        hi[key] = hindi

    json.dump(en, open(EN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nTotal args wrapped: {total}; new en.json keys: {added}")


if __name__ == "__main__":
    main()
