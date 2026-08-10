"""migrate_batch4.py — migrate SAFE UI strings in batch-4 tab files to tr().

⚠️ SAFETY: strings matched against the LIVE WEBSITE (By.ID / LINK_TEXT /
select_by_visible_text), config save/load values, and checkbox on/off values are
INTENTIONALLY EXCLUDED from the map — translating them would break automation.

Wraps:
  - text=/placeholder_text=/title= attributes (UI labels, buttons, hints)
  - messagebox.show*/ask* positional args (both args literal strings)
  - f-string messagebox dialogs via exact string replacements (handled
    separately because regex can't safely cross f" prefixes)
  - fto_generation long instruction note

Usage:  python3 scripts/migrate_batch4.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# string → (key, hindi). ONLY user-facing UI strings.
MAP = {
    # ── work_allocation_tab ──
    "No file selected": ("common.no_file_selected", "कोई फ़ाइल चयनित नहीं"),
    "Panchayat Name:": ("common.panchayat_name_label", "पंचायत का नाम:"),
    "Work Category:": ("form.work_alloc.work_category", "कार्य श्रेणी:"),
    "Use Demand CSV:": ("form.work_alloc.use_demand_csv", "डिमांड CSV उपयोग करें:"),
    "Load Demand CSV": ("form.work_alloc.load_demand_csv", "डिमांड CSV लोड करें"),
    "Enter one Work Key (Search Key) per line.": ("form.work_alloc.work_key_hint", "प्रति पंक्ति एक वर्क की (सर्च की) दर्ज करें।"),
    "Clear": ("common.clear", "साफ़ करें"),
    "📤 Export for Demand": ("form.work_alloc.export_demand", "📤 डिमांड के लिए निर्यात करें"),
    "📥 Export to Excel": ("common.export_excel", "📥 एक्सेल में निर्यात करें"),
    "Select Demand CSV": ("form.work_alloc.select_demand_csv", "डिमांड CSV चुनें"),
    "Export for Demand": ("form.work_alloc.export_demand_title", "डिमांड के लिए निर्यात करें"),
    # Retry Mode (Text) is a DISPLAY-ONLY status label (never compared) → safe
    "Retry Mode (Text)": ("form.work_alloc.retry_mode", "रीट्राई मोड (टेक्स्ट)"),

    # ── wagelist_gen_tab ──
    "Save generated wagelist page as PDF": ("form.wagelist.save_pdf", "जनरेट की गई वेजलिस्ट पेज को PDF के रूप में सहेजें"),
    "Save Report": ("common.save_report", "रिपोर्ट सहेजें"),
    "Are you sure?": ("confirm.are_you_sure", "क्या आप सुनिश्चित हैं?"),
    "No Data": ("errors.no_data", "कोई डेटा नहीं"),
    "There are no results to export.": ("errors.no_results_export", "निर्यात करने के लिए कोई परिणाम नहीं।"),
    "Success": ("status.success", "सफल"),
    "Input Error": ("errors.input_error", "इनपुट त्रुटि"),
    "Retry": ("base.error_tab.retry_btn", "पुनः प्रयास"),
    "Input Needed": ("errors.input_needed", "इनपुट आवश्यक"),

    # ── fto_generation_tab ──
    "Launch Old Firefox": ("form.fto.launch_old_ff", "पुराना फ़ायरफ़ॉक्स लॉन्च करें"),
    "Old Firefox Path:": ("form.fto.old_ff_path", "पुराना फ़ायरफ़ॉक्स पथ:"),
    "Browse": ("common.browse", "ब्राउज़ करें"),
    "Check Install": ("form.fto.check_install", "इंस्टॉल जांचें"),
    "Check Pending ABPS Labour": ("form.fto.check_pending_abps", "लंबित ABPS मज़दूर जांचें"),
    "🗑 Delete FTOs": ("form.fto.delete_ftos", "🗑 FTO हटाएं"),
    "Launching...": ("form.fto.launching", "लॉन्च हो रहा है..."),
    "Select Old Firefox Executable": ("form.fto.select_ff_exe", "पुराना फ़ायरफ़ॉक्स एक्ज़ीक्यूटेबल चुनें"),
    "Not Found": ("dialogs.not_found", "नहीं मिला"),
    "Browser Ready": ("dialogs.browser_ready", "ब्राउज़र तैयार"),
    "Browser Error": ("dialogs.browser_error", "ब्राउज़र त्रुटि"),
    "Confirm Delete": ("dialogs.confirm_delete", "हटाने की पुष्टि करें"),
    "Finished": ("dialogs.finished", "समाप्त"),
    "Error": ("dialogs.error", "त्रुटि"),
    "Critical Error": ("dialogs.critical_error", "गंभीर त्रुटि"),

    # ── update_estimate_tab ──
    "Estimated Outcome": ("form.update_estimate.estimated_outcome", "अनुमानित परिणाम"),
    "This value will be used for all work codes processed.": ("form.update_estimate.outcome_hint", "यह मान सभी प्रोसेस किए गए वर्क कोड के लिए उपयोग होगा।"),
    "Enter one Work Code per line.": ("form.update_estimate.workcode_hint", "प्रति पंक्ति एक वर्क कोड दर्ज करें।"),
    "Extract from Text": ("common.extract_from_text", "टेक्स्ट से निकालें"),
    "Reset Form?": ("dialogs.reset_form", "फ़ॉर्म रीसेट करें?"),
    "This will clear all inputs, results, and logs. Continue?": ("dialogs.reset_confirm_full", "यह सभी इनपुट, परिणाम और लॉग साफ़ कर देगा। जारी रखें?"),
    "Estimated Outcome cannot be empty.": ("dialogs.outcome_required", "अनुमानित परिणाम खाली नहीं हो सकता।"),
    "No work codes provided.": ("dialogs.no_work_codes", "कोई वर्क कोड प्रदान नहीं किया गया।"),
    "Automation Error": ("base.automation_error.title", "ऑटोमेशन त्रुटि"),
    "Extraction Complete": ("dialogs.extraction_complete", "निष्कर्षण पूर्ण"),
    "No Codes Found": ("dialogs.no_codes_found", "कोई कोड नहीं मिला"),
    "Extraction Error": ("dialogs.extraction_error", "निष्कर्षण त्रुटि"),

    # ── work_allocation dialogs ──
    "Invalid data format received from Demand tab.": ("dialogs.invalid_demand_data", "डिमांड टैब से अमान्य डेटा प्रारूप प्राप्त हुआ।"),
    "Work Category is required.": ("dialogs.work_category_required", "कार्य श्रेणी आवश्यक है।"),
    "Please enter Work Keys or Load a CSV.": ("dialogs.enter_work_keys_or_csv", "कृपया वर्क की दर्ज करें या CSV लोड करें।"),
    "No valid items found in the Work Key List.": ("dialogs.no_valid_work_keys", "वर्क की सूची में कोई मान्य आइटम नहीं मिला।"),
    "CSV must have 'Allocation Work Code' column.": ("dialogs.csv_allocation_column", "CSV में 'Allocation Work Code' कॉलम होना चाहिए।"),
    "No results found to retry.": ("base.retry_no_results", "पुनः प्रयास के लिए कोई परिणाम नहीं मिला।"),
    "No failed items found.": ("base.retry_no_fails", "कोई विफल आइटम नहीं मिला।"),
    "Great!": ("dialogs.great", "बढ़िया!"),

    # ── wagelist_gen dialogs ──
    "Please enter an Agency/Panchayat name.": ("dialogs.agency_panchayat_required", "कृपया एजेंसी/पंचायत का नाम दर्ज करें।"),
    "Retrying will check for any remaining items in the list.\nContinue?": ("dialogs.retry_remaining", "पुनः प्रयास सूची में शेष आइटमों की जांच करेगा।\nजारी रखें?"),
    "Please enter an Agency Name for the report title.": ("dialogs.agency_name_required", "रिपोर्ट शीर्षक के लिए कृपया एजेंसी का नाम दर्ज करें।"),

    # ── fto_generation dialogs ──
    "Old Firefox not found! Please browse and select 'firefox.exe' manually.": ("dialogs.ff_not_found", "पुराना फ़ायरफ़ॉक्स नहीं मिला! कृपया ब्राउज़ करके 'firefox.exe' को मैन्युअल चुनें।"),
    "Valid Firefox path is required!": ("dialogs.valid_ff_required", "मान्य फ़ायरफ़ॉक्स पथ आवश्यक है!"),
    "This will delete the FIRST FTO in the dropdown.\n\nEnsure you want to proceed.": ("dialogs.delete_fto_confirm", "यह ड्रॉपडाउन में पहला FTO हटा देगा।\n\nसुनिश्चित करें कि आप आगे बढ़ना चाहते हैं।"),
    "FTO Deletion check complete.": ("dialogs.fto_delete_complete", "FTO विलोपन जांच पूर्ण।"),
    "Old Firefox is open.\n\n1. Login to NREGA.\n2. Go to FTO page.\n3. Return here and click 'Start'.": ("dialogs.ff_open_msg", "पुराना फ़ायरफ़ॉक्स खुला है।\n\n1. NREGA में लॉगिन करें।\n2. FTO पेज पर जाएं।\n3. यहां लौटें और 'Start' पर क्लिक करें।"),

    # ── update_estimate dialogs ──
    "Could not find any matching full work codes (e.g., 34.../.../...).": ("dialogs.no_full_codes_msg", "कोई मेल खाता पूर्ण वर्क कोड नहीं मिला (जैसे, 34.../.../...)."),
}

# Exact source→replacement for f-string messagebox dialogs (regex unsafe across f")
FSTRING_REPLACEMENTS = [
    # update_estimate line 172
    ('messagebox.showerror("Automation Error", f"An unexpected error occurred: {e}")',
     'messagebox.showerror(tr("base.automation_error.title"), tr("dialogs.unexpected_error", error=e))'),
    # update_estimate line 250 (has parent=self suffix)
    ('messagebox.showinfo("Extraction Complete", f"Found and extracted {len(final_results)} unique full work codes.", parent=self)',
     'messagebox.showinfo(tr("dialogs.extraction_complete"), tr("dialogs.extracted_count", count=len(final_results)), parent=self)'),
    # update_estimate line 255 (has parent=self suffix)
    ('messagebox.showerror("Extraction Error", f"An error occurred during extraction: {e}", parent=self)',
     'messagebox.showerror(tr("dialogs.extraction_error"), tr("dialogs.extraction_error_msg", error=e), parent=self)'),
    # work_allocation line 853
    ('messagebox.showerror("Error", f"Failed to load CSV: {e}")',
     'messagebox.showerror(tr("dialogs.error"), tr("dialogs.failed_load_csv", error=e))'),
    # wagelist_gen line 464
    ('messagebox.showinfo("No Data", f"No records found for filter \'{filter_option}\'.")',
     'messagebox.showinfo(tr("errors.no_data"), tr("dialogs.no_records_for_filter", filter=filter_option))'),
    # wagelist_gen line 492
    ('messagebox.askyesno("Success", f"PDF Report saved to:\\n{file_path}\\n\\nDo you want to open it?")',
     'messagebox.askyesno(tr("status.success"), tr("export.pdf_saved", path=file_path))'),
    # fto_generation line 153
    ('messagebox.showinfo("Success", f"Old Firefox found at:\\n{path}")',
     'messagebox.showinfo(tr("status.success"), tr("dialogs.ff_found", path=path))'),
]

# fto_generation long instruction note — plain string assigned to note_text var
FTO_NOTE_OLD = ('note_text = "💡 Instructions:\\n1. Check/Set Old Firefox Path and Click '
                "\\'Launch Old Firefox\\'.\\n2. Log in manually, insert DSC Token, go to FTO page.\\n"
                "3. Click 'Start' to sign pending FTOs or 'Delete' to remove.\"")
FTO_NOTE_NEW = 'note_text = tr("form.fto.instructions")'

# messagebox positional args: messagebox.showXXX("Title", "Message") — both literal
MB_PATTERN = re.compile(r'''(messagebox\.\w+\(\s*)"([^"]+)"\s*,\s*"([^"]+)"''')

# text=/placeholder_text=/title= attrs with literal string values (skip f-strings)
ATTR_PATTERN = re.compile(r'''(?<!f)(\b(?:text|placeholder_text|title)\s*=\s*)"([^"]+)"''')

FILES = [
    "src/tabs/work_allocation_tab.py",
    "src/tabs/wagelist_gen_tab.py",
    "src/tabs/fto_generation_tab.py",
    "src/tabs/update_estimate_tab.py",
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

        # fto instruction note
        if FTO_NOTE_OLD in src:
            src = src.replace(FTO_NOTE_OLD, FTO_NOTE_NEW)
            count += 1

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

    # Extra keys not in MAP (multi-line / dynamic / f-string dialog texts)
    extra = {
        "form.fto.instructions": (
            "💡 Instructions:\n1. Check/Set Old Firefox Path and Click 'Launch Old Firefox'.\n2. Log in manually, insert DSC Token, go to FTO page.\n3. Click 'Start' to sign pending FTOs or 'Delete' to remove.",
            "💡 निर्देश:\n1. पुराना फ़ायरफ़ॉक्स पथ जांचें/सेट करें और 'Launch Old Firefox' पर क्लिक करें।\n2. मैन्युअल लॉगिन करें, DSC टोकन डालें, FTO पेज पर जाएं।\n3. लंबित FTO पर हस्ताक्षर करने के लिए 'Start' या हटाने के लिए 'Delete' पर क्लिक करें।",
        ),
        "dialogs.extracted_count": (
            "Found and extracted {count} unique full work codes.",
            "{count} अद्वितीय पूर्ण वर्क कोड मिले और निकाले गए।",
        ),
        "dialogs.unexpected_error": (
            "An unexpected error occurred: {error}",
            "एक अप्रत्याशित त्रुटि हुई: {error}",
        ),
        "dialogs.extraction_error_msg": (
            "An error occurred during extraction: {error}",
            "निष्कर्षण के दौरान एक त्रुटि हुई: {error}",
        ),
        "dialogs.failed_load_csv": (
            "Failed to load CSV: {error}",
            "CSV लोड विफल: {error}",
        ),
        "dialogs.ff_found": (
            "Old Firefox found at:\n{path}",
            "पुराना फ़ायरफ़ॉक्स यहां मिला:\n{path}",
        ),
        "dialogs.no_records_for_filter": (
            "No records found for filter '{filter}'.",
            "फ़िल्टर '{filter}' के लिए कोई रिकॉर्ड नहीं मिला।",
        ),
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
