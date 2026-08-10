"""migrate_batch7.py — migrate SAFE UI strings in batch-7 tab files to tr().

⚠️ SAFETY: macro_manager task-type dropdown values ("Bulk Demand (CSV)",
"Wagelist Gen + Auto Send", ...) are INTERNAL DISPATCH KEYS — compared with
`if choice == "Bulk Demand (CSV)"` and passed to _update_input_fields — they
must NOT be translated. All website matching uses By.XPATH/By.TAG_NAME with
class-attribute locators (no text matching) — untouched by these patterns.

Wraps:
  - text=/placeholder_text=/title= attributes (UI labels, buttons, hints)
  - messagebox.show*/ask* positional args (both args literal strings)
  - f-string + multiline messagebox dialogs via exact string replacements

Usage:  python3 scripts/migrate_batch7.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# string → (key, hindi). ONLY user-facing UI strings.
MAP = {
    # ── nmms_attendance_tab ──
    "Attendance Date:": ("form.nmms.attendance_date", "उपस्थिति दिनांक:"),
    "📅 Set Date & Scrape": ("form.nmms.set_date_scrape", "📅 दिनांक सेट करें और स्क्रेप करें"),
    "Download Group Photos": ("form.nmms.download_photos", "ग्रुप फोटो डाउनलोड करें"),
    "Select Panchayats:": ("form.nmms.select_panchayats", "पंचायत चुनें:"),
    "Select All": ("common.select_all", "सभी चुनें"),
    "Clear All": ("common.clear_all", "सभी साफ़ करें"),
    "💡 How to Use": ("form.nmms.how_to_use", "💡 उपयोग कैसे करें"),
    "📊 Export Excel Report": ("form.nmms.export_report", "📊 एक्सेल रिपोर्ट निर्यात करें"),
    "Clear Results": ("form.nmms.clear_results", "परिणाम साफ़ करें"),
    "📥 Export Workers Excel": ("form.nmms.export_workers", "📥 मज़दूर एक्सेल निर्यात करें"),
    "Scraping...": ("form.nmms.scraping", "स्क्रेप हो रहा है..."),
    "🔍 Scrape Current Page": ("form.nmms.scrape_current", "🔍 वर्तमान पेज स्क्रेप करें"),
    "No panchayats found. Make sure panchayat list is visible in browser.": ("dialogs.nmms_no_panchayats", "कोई पंचायत नहीं मिली। सुनिश्चित करें कि ब्राउज़र में पंचायत सूची दिख रही है।"),
    "Save NMMS Attendance Report": ("form.nmms.save_report", "NMMS उपस्थिति रिपोर्ट सहेजें"),

    # ── issued_mr_report_tab ──
    "State:": ("common.state_label", "राज्य:"),
    "District:": ("common.district_label", "जिला:"),
    "Block:": ("common.block_label", "ब्लॉक:"),
    "Panchayat:": ("common.panchayat_label", "पंचायत:"),
    "Pending demand labour for abps": ("form.issued_mr.pending_labour", "ABPS के लिए लंबित डिमांड मज़दूर"),
    "Copy Workcodes": ("form.issued_mr.copy_workcodes", "वर्ककोड कॉपी करें"),
    "Run Duplicate MR Print": ("form.issued_mr.run_dup_mr", "डुप्लीकेट MR प्रिंट चलाएं"),
    "📥 Export to Excel": ("common.export_excel", "📥 एक्सेल में निर्यात करें"),
    "Export ABPS Data": ("form.issued_mr.export_abps", "ABPS डेटा निर्यात करें"),

    # ── resend_rejected_wg_tab ──
    "Financial Year:": ("common.financial_year", "वित्तीय वर्ष:"),
    "Panchayat (optional):": ("form.resend_wg.panchayat_optional", "पंचायत (वैकल्पिक):"),
    "Process for ALL available Panchayats": ("form.resend_wg.process_all", "सभी उपलब्ध पंचायतों के लिए प्रक्रिया करें"),

    # ── macro_manager_tab ──
    "+ Add to Queue": ("form.macro.add_to_queue", "+ क्यू में जोड़ें"),
    "Select Task Type:": ("form.macro.select_task", "कार्य प्रकार चुनें:"),
    "Tip: Ensure 'State/Block' are selected.": ("form.macro.state_block_tip", "टिप: सुनिश्चित करें कि 'State/Block' चयनित हैं।"),
    "▶ Run Macro Queue": ("form.macro.run_queue", "▶ मैक्रो क्यू चलाएं"),
    "⏹ Stop": ("form.macro.stop", "⏹ रोकें"),
    "Panchayat Name:": ("common.panchayat_name_label", "पंचायत का नाम:"),
    "Select CSV File:": ("form.macro.select_csv", "CSV फ़ाइल चुनें:"),
    "Browse": ("common.browse", "ब्राउज़ करें"),
    "Target Panchayat(s):": ("form.macro.target_panchayats", "लक्षित पंचायतें:"),
    "Clear Queue": ("form.macro.clear_queue", "क्यू साफ़ करें"),
    "Logs & Status": ("form.macro.logs_status", "लॉग और स्थिति"),

    # ── shared dialogs ──
    "Reset Form?": ("dialogs.reset_form", "फ़ॉर्म रीसेट करें?"),
    "Input Error": ("errors.input_error", "इनपुट त्रुटि"),
    "All fields are required.": ("errors.input_required", "सभी फ़ील्ड आवश्यक हैं।"),
    "Confirm": ("dialogs.confirm", "पुष्टि करें"),
    "This will process ALL panchayats in the block. Continue?": ("dialogs.process_all_panchayats", "यह ब्लॉक के सभी पंचायतों को प्रोसेस करेगा। जारी रखें?"),
    "No Data": ("errors.no_data", "कोई डेटा नहीं"),
    "There are no results to export.": ("errors.no_results_export", "निर्यात करने के लिए कोई परिणाम नहीं।"),
    "Copied": ("status.copied", "कॉपी हो गया"),
    "Empty": ("dialogs.empty", "खाली"),
    "There are no workcodes to copy.": ("dialogs.no_workcodes_copy", "कॉपी करने के लिए कोई वर्ककोड नहीं है।"),
    "There are no workcodes to send.": ("dialogs.no_workcodes_send", "भेजने के लिए कोई वर्ककोड नहीं है।"),
    "Panchayat name is missing.": ("dialogs.panchayat_missing", "पंचायत का नाम गायब है।"),
    "There are no ABPS results to export.": ("dialogs.no_abps_results", "निर्यात करने के लिए कोई ABPS परिणाम नहीं।"),
    "No Selection": ("dialogs.no_selection", "कोई चयन नहीं"),
    "Please select at least one panchayat.": ("dialogs.select_one_panchayat", "कृपया कम से कम एक पंचायत चुनें।"),
    "Browser Not Connected": ("dialogs.browser_not_connected", "ब्राउज़र कनेक्ट नहीं है"),
    "No Table Found": ("dialogs.no_table_found", "कोई टेबल नहीं मिली"),
    "Scrape Error": ("dialogs.scrape_error", "स्क्रेप त्रुटि"),
    "Exported": ("status.exported", "निर्यात हो गया"),
    "Export Error": ("dialogs.export_error", "निर्यात त्रुटि"),
    "State, District and Block are required.": ("dialogs.state_district_block_required", "राज्य, जिला और ब्लॉक आवश्यक हैं।"),
}

# Exact source→replacement for f-string + multiline messagebox dialogs
FSTRING_REPLACEMENTS = [
    # nmms: Scrape Error
    ('messagebox.showerror("Scrape Error", f"Could not read the page:\\n{err}")',
     'messagebox.showerror(tr("dialogs.scrape_error"), tr("dialogs.could_not_read_page", error=err))'),
    # nmms: Error scraping failed
    ('messagebox.showerror("Error", f"Scraping failed:\\n{err}")',
     'messagebox.showerror(tr("dialogs.error"), tr("dialogs.scraping_failed", error=err))'),
    # nmms: Exported report saved
    ('messagebox.showinfo("Exported", f"Report saved!\\n\\n{file_path}")',
     'messagebox.showinfo(tr("status.exported"), tr("dialogs.report_saved", path=file_path))'),
    # nmms: Export Error could not save
    ('messagebox.showerror("Export Error", f"Could not save report:\\n{e}")',
     'messagebox.showerror(tr("dialogs.export_error"), tr("dialogs.could_not_save_report", error=e))'),
    # nmms multiline: Browser Not Connected
    ('messagebox.showwarning(\n                "Browser Not Connected",\n                "No browser found.\\n\\nPlease launch Chrome/Edge from the app and log in to NREGA portal first.")',
     'messagebox.showwarning(\n                tr("dialogs.browser_not_connected"),\n                tr("dialogs.no_browser_found"))'),
    # nmms multiline: No Table Found (with page preview t)
    ('messagebox.showwarning(\n                    "No Table Found",\n                    "No data table found on the current browser page.\\n\\n"\n                    "Please navigate to the panchayat list in your browser first,\\n"\n                    "then click \'Scrape Current Page\' again.\\n\\n"\n                    f"Page preview:\\n{t}")',
     'messagebox.showwarning(\n                    tr("dialogs.no_table_found"),\n                    tr("dialogs.no_table_found_msg", preview=t))'),
    # issued_mr: workcodes copied
    ('messagebox.showinfo("Copied", f"{len(text.splitlines())} workcodes copied to clipboard.", parent=self)',
     'messagebox.showinfo(tr("status.copied"), tr("dialogs.workcodes_copied", count=len(text.splitlines())), parent=self)'),
]

# macro_manager docstring Hinglish → clean English
DOCSTRING_FIX = (
    '        """\n        Dropdown change hone par inputs ko badalta hai.\n        """',
    '        """Update the input fields when the task-type dropdown changes."""',
)

# messagebox positional args: messagebox.showXXX("Title", "Message") — both literal
MB_PATTERN = re.compile(r'''(messagebox\.\w+\(\s*)"([^"]+)"\s*,\s*"([^"]+)"''')

# text=/placeholder_text=/title= attrs with literal string values (skip f-strings)
ATTR_PATTERN = re.compile(r'''(?<!f)(\b(?:text|placeholder_text|title)\s*=\s*)"([^"]+)"''')

FILES = [
    "src/tabs/nmms_attendance_tab.py",
    "src/tabs/issued_mr_report_tab.py",
    "src/tabs/resend_rejected_wg_tab.py",
    "src/tabs/macro_manager_tab.py",
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

        # f-string + multiline dialogs
        for old, new in FSTRING_REPLACEMENTS:
            if old in src:
                src = src.replace(old, new)
                count += 1

        # docstring fix
        if DOCSTRING_FIX[0] in src:
            src = src.replace(DOCSTRING_FIX[0], DOCSTRING_FIX[1])
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
        "dialogs.could_not_read_page": (
            "Could not read the page:\n{error}",
            "पेज पढ़ा नहीं जा सका:\n{error}",
        ),
        "dialogs.scraping_failed": (
            "Scraping failed:\n{error}",
            "स्क्रेपिंग विफल:\n{error}",
        ),
        "dialogs.report_saved": (
            "Report saved!\n\n{path}",
            "रिपोर्ट सेव हुई!\n\n{path}",
        ),
        "dialogs.could_not_save_report": (
            "Could not save report:\n{error}",
            "रिपोर्ट सेव नहीं हो सकी:\n{error}",
        ),
        "dialogs.no_browser_found": (
            "No browser found.\n\nPlease launch Chrome/Edge from the app and log in to NREGA portal first.",
            "कोई ब्राउज़र नहीं मिला।\n\nकृपया ऐप से Chrome/Edge लॉन्च करें और पहले NREGA पोर्टल में लॉगिन करें।",
        ),
        "dialogs.no_table_found_msg": (
            "No data table found on the current browser page.\n\nPlease navigate to the panchayat list in your browser first,\nthen click 'Scrape Current Page' again.\n\nPage preview:\n{preview}",
            "वर्तमान ब्राउज़र पेज पर कोई डेटा टेबल नहीं मिली।\n\nकृपया पहले ब्राउज़र में पंचायत सूची पर जाएं,\nफिर 'Scrape Current Page' फिर से क्लिक करें।\n\nपेज पूर्वावलोकन:\n{preview}",
        ),
        "dialogs.workcodes_copied": (
            "{count} workcodes copied to clipboard.",
            "{count} वर्ककोड क्लिपबोर्ड पर कॉपी हो गए।",
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
