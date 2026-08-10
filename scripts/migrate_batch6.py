"""migrate_batch6.py — migrate SAFE UI strings in batch-6 tab files to tr().

⚠️ SAFETY: strings matched against the LIVE WEBSITE (By.ID / By.XPATH with
contains(text(), ...) / select_by_visible_text) are INTENTIONALLY EXCLUDED —
notably mr_fill's `//*[contains(text(), 'No Future Dates Plz')]` website text
match and all By.ID "ddl*"/"txt*" locators.

professional_pdf.py is SKIPPED entirely — it has zero user-facing UI strings
(no messagebox / CTkLabel / text=), it's a PDF-generation utility.

Wraps:
  - text=/placeholder_text=/title= attributes (UI labels, buttons, hints)
  - messagebox.show*/ask* positional args (both args literal strings)
  - f-string messagebox dialogs via exact string replacements
  - workcode_extractor fragmented 3-part note (special-cased below)

Usage:  python3 scripts/migrate_batch6.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# string → (key, hindi). ONLY user-facing UI strings.
MAP = {
    # ── mr_fill_tab ──
    "Panchayat Name": ("common.panchayat_name", "पंचायत का नाम"),
    "e.g., Palojori (skip if using GP login)": ("form.mr_fill.panchayat_placeholder", "जैसे, पालोजोरी (GP लॉगिन उपयोग करने पर छोड़ें)"),
    "Mark Holiday Columns (comma-separated)": ("form.mr_fill.holiday_cols", "छुट्टी वाले कॉलम चिह्नित करें (अल्पविराम से अलग)"),
    "e.g., 7, 14 (will mark 7th and 14th columns as holiday)": ("form.mr_fill.holiday_placeholder", "जैसे, 7, 14 (7वें और 14वें कॉलम को छुट्टी के रूप में चिह्नित करेगा)"),
    "Manual Mode (Pause after marking holidays for you to mark absentees)": ("form.mr_fill.manual_mode", "मैन्युअल मोड (छुट्टी चिह्नित करने के बाद रुकें ताकि आप अनुपस्थित चिह्नित कर सकें)"),
    "Clear": ("common.clear", "साफ़ करें"),
    "Extract from Text": ("common.extract_from_text", "टेक्स्ट से निकालें"),
    "📥 Export to Excel": ("common.export_excel", "📥 एक्सेल में निर्यात करें"),

    # ── pdf_merger_tab ──
    "Select PDF Files...": ("common.select_pdf_files", "PDF फ़ाइलें चुनें..."),
    "Select multiple PDFs. The order below is the merge order.": ("form.pdf_merger.select_hint", "कई PDF चुनें। नीचे का क्रम मर्ज क्रम है।"),
    "Move Up": ("common.move_up", "ऊपर ले जाएं"),
    "Move Down": ("common.move_down", "नीचे ले जाएं"),
    "Remove": ("common.remove", "हटाएं"),
    "Output File Name:": ("common.output_file_name", "आउटपुट फ़ाइल नाम:"),
    "Merge Selected PDFs": ("form.pdf_merger.merge_btn", "चयनित PDF मर्ज करें"),
    "Clear List": ("common.clear_list", "सूची साफ़ करें"),
    "e.g., Kasraydih": ("form.pdf_merger.name_placeholder", "जैसे, कसरायडीह"),
    "Select PDF files to merge": ("form.pdf_merger.select_title", "मर्ज करने के लिए PDF फ़ाइलें चुनें"),

    # ── workcode_extractor_tab ──
    "Workcode Extractor": ("tab.workcode_extractor.title", "वर्ककोड एक्सट्रैक्टर"),
    "Paste the MR Tracking table and extract workcodes / wagelist IDs instantly.": ("form.workcode_ext.subtitle", "MR ट्रैकिंग टेबल पेस्ट करें और तुरंत वर्ककोड / वेजलिस्ट आईडी निकालें।"),
    "Paste Text Below": ("form.workcode_ext.paste_label", "नीचे टेक्स्ट पेस्ट करें"),
    "💡 Note: Go to the ": ("form.workcode_ext.note_prefix", "💡 नोट: "),
    "MR Tracking Page": ("form.workcode_ext.note_link", "MR ट्रैकिंग पेज"),
    ", copy the entire table, and paste it below.": ("form.workcode_ext.note_suffix", ", पूरी टेबल कॉपी करें, और नीचे पेस्ट करें।"),
    "Extracted Codes": ("form.workcode_ext.extracted_label", "निकाले गए कोड"),
    "▶ Extract Codes": ("form.workcode_ext.extract_btn", "▶ कोड निकालें"),
    "Remove Duplicates": ("form.workcode_ext.remove_dups", "डुप्लीकेट हटाएं"),
    "Extract Full Workcode": ("form.workcode_ext.extract_full", "पूर्ण वर्ककोड निकालें"),
    "Extract Wagelist IDs": ("form.workcode_ext.extract_wl_ids", "वेजलिस्ट आईडी निकालें"),
    "Clear All": ("common.clear_all", "सभी साफ़ करें"),
    "Copied!": ("status.copied", "कॉपी हो गया!"),
    "Filter date (DD-MM-YYYY)": ("form.workcode_ext.filter_date", "दिनांक फ़िल्टर (DD-MM-YYYY)"),
    "Copy": ("common.copy", "कॉपी करें"),

    # ── mr_fill dialogs ──
    "Reset Form?": ("dialogs.reset_form", "फ़ॉर्म रीसेट करें?"),
    "Clear all inputs, results, and logs?": ("dialogs.reset_confirm_all", "सभी इनपुट, परिणाम और लॉग साफ़ करें?"),
    "Input Error": ("errors.input_error", "इनपुट त्रुटि"),
    "No work keys (Search Key) provided.": ("dialogs.no_work_keys", "कोई वर्क की (सर्च की) प्रदान नहीं की गई।"),
    "MR Fill Error": ("dialogs.mr_fill_error", "MR फिल त्रुटि"),
    "Retry": ("base.error_tab.retry_btn", "पुनः प्रयास"),
    "No results found to retry.": ("base.retry_no_results", "पुनः प्रयास के लिए कोई परिणाम नहीं मिला।"),
    "Great!": ("dialogs.great", "बढ़िया!"),
    "No failed items found.": ("base.retry_no_fails", "कोई विफल आइटम नहीं मिला।"),
    "Retry Failed": ("base.retry_confirm_title", "पुनः प्रयास विफल"),
    "No Data": ("errors.no_data", "कोई डेटा नहीं"),
    "There are no results to export.": ("errors.no_results_export", "निर्यात करने के लिए कोई परिणाम नहीं।"),
    "Input Needed": ("errors.input_needed", "इनपुट आवश्यक"),
    "Please enter a Panchayat Name for the report title.": ("dialogs.panchayat_report_title", "रिपोर्ट शीर्षक के लिए कृपया पंचायत का नाम दर्ज करें।"),

    # ── pdf_merger dialogs ──
    "No Selection": ("dialogs.no_selection", "कोई चयन नहीं"),
    "Please select a file from the list to remove.": ("dialogs.select_file_remove", "हटाने के लिए कृपया सूची से एक फ़ाइल चुनें।"),
    "Clear Form?": ("dialogs.clear_form", "फ़ॉर्म साफ़ करें?"),
    "Are you sure you want to clear all selected files and the file name?": ("dialogs.clear_form_confirm", "क्या आप सभी चयनित फ़ाइलें और फ़ाइल नाम साफ़ करना चाहते हैं?"),
    "Path Error": ("dialogs.path_error", "पथ त्रुटि"),
    "Not Enough Files": ("dialogs.not_enough_files", "पर्याप्त फ़ाइलें नहीं"),
    "Please select at least two PDF files to merge.": ("dialogs.select_two_pdfs", "मर्ज करने के लिए कृपया कम से कम दो PDF फ़ाइलें चुनें।"),
    "Input Required": ("errors.input_required", "इनपुट आवश्यक"),
    "Please enter an output file name (e.g., Kasraydih).": ("dialogs.enter_output_name", "कृपया आउटपुट फ़ाइल नाम दर्ज करें (जैसे, कसरायडीह)।"),
    "PDF Library Missing": ("dialogs.pdf_lib_missing", "PDF लाइब्रेरी उपलब्ध नहीं"),
    "Success": ("status.success", "सफल"),
    "Open Location?": ("dialogs.open_location", "स्थान खोलें?"),
    "Do you want to open the folder containing the merged file?": ("dialogs.open_location_confirm", "क्या आप मर्ज की गई फ़ाइल वाला फ़ोल्डर खोलना चाहते हैं?"),
}

# Exact source→replacement for f-string messagebox dialogs
FSTRING_REPLACEMENTS = [
    # mr_fill: MR Fill Error
    ('messagebox.showerror("MR Fill Error", f"An error occurred: {e}")',
     'messagebox.showerror(tr("dialogs.mr_fill_error"), tr("errors.an_error_occurred", error=e))'),
    # mr_fill: Retry Failed (count)
    ('if messagebox.askyesno("Retry Failed", f"Found {len(failed_items)} failed items.\\nRetry now?"):',
     'if messagebox.askyesno(tr("base.retry_confirm_title"), tr("dialogs.retry_failed_items", count=len(failed_items))):'),
    # pdf_merger: Path Error
    ('messagebox.showerror("Path Error", f"Could not create output directory: {e}", parent=self)',
     'messagebox.showerror(tr("dialogs.path_error"), tr("dialogs.could_not_create_dir", dir="", error=e), parent=self)'),
    # pdf_merger: Success merged
    ('messagebox.showinfo("Success", f"Successfully merged {len(file_list)} files into:\\n{output_path}", parent=self)',
     'messagebox.showinfo(tr("status.success"), tr("dialogs.merged_files", count=len(file_list), path=output_path), parent=self)'),
]

# messagebox positional args: messagebox.showXXX("Title", "Message") — both literal
MB_PATTERN = re.compile(r'''(messagebox\.\w+\(\s*)"([^"]+)"\s*,\s*"([^"]+)"''')

# text=/placeholder_text=/title= attrs with literal string values (skip f-strings)
ATTR_PATTERN = re.compile(r'''(?<!f)(\b(?:text|placeholder_text|title)\s*=\s*)"([^"]+)"''')

FILES = [
    "src/tabs/mr_fill_tab.py",
    "src/tabs/pdf_merger_tab.py",
    "src/tabs/workcode_extractor_tab.py",
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

    # Extra keys not in MAP (f-string dialog texts, multi-line)
    extra = {
        "dialogs.retry_failed_items": (
            "Found {count} failed items.\nRetry now?",
            "{count} विफल आइटम मिले।\nअब पुनः प्रयास करें?",
        ),
        "dialogs.could_not_create_dir": (
            "Could not create output directory: {error}",
            "आउटपुट निर्देशिका नहीं बनाई जा सकी: {error}",
        ),
        "dialogs.merged_files": (
            "Successfully merged {count} files into:\n{path}",
            "{count} फ़ाइलें सफलतापूर्वक इसमें मर्ज हुईं:\n{path}",
        ),
        "dialogs.pdf_lib_missing_msg": (
            "PDF merge requires the 'pypdf' library.\n\nSmart updates cannot add new Python libraries — please download the latest full version from nregabot.com.",
            "PDF मर्ज के लिए 'pypdf' लाइब्रेरी आवश्यक है।\n\nस्मार्ट अपडेट नई Python लाइब्रेरी नहीं जोड़ सकते — कृपया nregabot.com से नवीनतम पूर्ण संस्करण डाउनलोड करें।",
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
