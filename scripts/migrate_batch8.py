"""migrate_batch8.py — migrate SAFE UI strings in final-batch tab files to tr().

⚠️ SAFETY: strings matched against the LIVE WEBSITE are INTENTIONALLY EXCLUDED:
- SA_report status dropdown ["Pending", "Closed"] — matched on the website via
  select_by_visible_text(inputs['status']) — must NOT be translated.
- dashboard_report By.ID locators (ContentPlaceHolder1_*) + district text match
  (data value) — untouched.
- mate_mr_gen.py has only "75%" (progress value) — skipped entirely.

Wraps:
  - text=/placeholder_text=/title= attributes (UI labels, buttons, hints)
  - messagebox.show*/ask* positional args (both args literal strings)
  - f-string + multiline messagebox dialogs via exact string replacements
  - whatsapp Hinglish "AI soch raha hai..." → clean English + tr()

Usage:  python3 scripts/migrate_batch8.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# string → (key, hindi). ONLY user-facing UI strings.
MAP = {
    # ── dashboard_report_tab ──
    "State:": ("common.state_label", "राज्य:"),
    "District:": ("common.district_label", "जिला:"),
    "Block:": ("common.block_label", "ब्लॉक:"),
    "Panchayat:": ("common.panchayat_label", "पंचायत:"),
    "Delay Column:": ("form.dashboard.delay_column", "विलंब कॉलम:"),
    "Copy Workcodes": ("form.dashboard.copy_workcodes", "वर्ककोड कॉपी करें"),
    "Run MR Fill": ("form.dashboard.run_mr_fill", "MR फिल चलाएं"),
    "📥 Export to Excel": ("common.export_excel", "📥 एक्सेल में निर्यात करें"),

    # ── whatsapp_chat_tab ──
    "🟢 Online": ("chat.online", "🟢 ऑनलाइन"),
    "🔔 Notification on reply": ("chat.notify_reply", "🔔 उत्तर आने पर सूचना"),
    "AI": ("chat.ai", "AI"),
    "Support Chat": ("chat.support_chat", "सहायता चैट"),
    "🤖 AI Assistant • 24x7 Support": ("chat.ai_subtitle", "🤖 AI सहायक • 24x7 सहायता"),
    "Press Enter to send": ("chat.press_enter", "भेजने के लिए Enter दबाएं"),
    "🔴 Error": ("chat.error", "🔴 त्रुटि"),
    "💬 No messages yet": ("chat.no_messages", "💬 अभी कोई संदेश नहीं"),
    "Send a message to start the conversation!": ("chat.start_convo", "बातचीत शुरू करने के लिए एक संदेश भेजें!"),
    "🚧 Server update needed": ("chat.server_update", "🚧 सर्वर अपडेट आवश्यक"),
    "👨‍💼 Support": ("chat.support", "👨‍💼 सहायता"),
    "👤 You": ("chat.you", "👤 आप"),
    "Type a message": ("chat.type_message", "संदेश लिखें"),

    # ── SA_report_tab ──
    "Audit Conducted in:": ("form.sa.audit_year", "ऑडिट वर्ष:"),
    "Issue Status:": ("form.sa.issue_status", "समस्या स्थिति:"),
    "Social Audit Status Report": ("form.sa.report_title", "सामाजिक ऑडिट स्थिति रिपोर्ट"),

    # ── shared dialogs ──
    "Input Error": ("errors.input_error", "इनपुट त्रुटि"),
    "All fields are required.": ("errors.input_required", "सभी फ़ील्ड आवश्यक हैं।"),
    "Confirm": ("dialogs.confirm", "पुष्टि करें"),
    "This will process ALL panchayats in the block. Continue?": ("dialogs.process_all_panchayats", "यह ब्लॉक के सभी पंचायतों को प्रोसेस करेगा। जारी रखें?"),
    "Copied": ("status.copied", "कॉपी हो गया"),
    "Empty": ("dialogs.empty", "खाली"),
    "No workcodes.": ("dialogs.no_workcodes_short", "कोई वर्ककोड नहीं।"),
    "Error": ("dialogs.error", "त्रुटि"),
    "Missing Data.": ("dialogs.missing_data", "डेटा गायब है।"),
    "No Data": ("errors.no_data", "कोई डेटा नहीं"),
    "No results to export.": ("dialogs.no_results_export_short", "निर्यात करने के लिए कोई परिणाम नहीं।"),
    "PDF Error": ("dialogs.pdf_error", "PDF त्रुटि"),
    "Automation Error": ("base.automation_error.title", "ऑटोमेशन त्रुटि"),
    "Critical Error": ("dialogs.critical_error", "गंभीर त्रुटि"),
}

# Exact source→replacement for f-string + multiline messagebox dialogs
FSTRING_REPLACEMENTS = [
    # dashboard: Copied
    ('messagebox.showinfo("Copied", f"Copied to clipboard.")',
     'messagebox.showinfo(tr("status.copied"), tr("dialogs.copied_to_clipboard"))'),
    # SA_report: browser error
    ('messagebox.showerror("Automation Error", error_msg)',
     'messagebox.showerror(tr("base.automation_error.title"), error_msg)'),
    # SA_report: critical error f-string
    ('messagebox.showerror("Critical Error", f"An unexpected error occurred: {e}")',
     'messagebox.showerror(tr("dialogs.critical_error"), tr("dialogs.unexpected_error", error=e))'),
]

# whatsapp Hinglish → clean English + tr()
WHATSAPP_HINGLISH = [
    ('self.sound_indicator.configure(text="🤖 AI soch raha hai...")',
     'self.sound_indicator.configure(text=tr("chat.ai_thinking"))'),
    # Hinglish comments → clean English
    ('        self._awaiting_ai = False       # AI reply aane tak typing indicator\n        self._awaiting_ai_after = None  # indicator timeout (reply na aaye to reset)',
     '        self._awaiting_ai = False       # show typing indicator until the AI reply arrives\n        self._awaiting_ai_after = None  # indicator timeout (reset if no reply)'),
    ('        # Subtitle — AI assistant pehle reply karta hai, phir human support',
     '        # Subtitle — AI assistant replies first, then human support'),
]

# messagebox positional args: messagebox.showXXX("Title", "Message") — both literal
MB_PATTERN = re.compile(r'''(messagebox\.\w+\(\s*)"([^"]+)"\s*,\s*"([^"]+)"''')

# text=/placeholder_text=/title= attrs with literal string values (skip f-strings)
ATTR_PATTERN = re.compile(r'''(?<!f)(\b(?:text|placeholder_text|title)\s*=\s*)"([^"]+)"''')

FILES = [
    "src/tabs/dashboard_report_tab.py",
    "src/tabs/whatsapp_chat_tab.py",
    "src/tabs/SA_report_tab.py",
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

        for old, new in FSTRING_REPLACEMENTS:
            if old in src:
                src = src.replace(old, new)
                count += 1

        for old, new in WHATSAPP_HINGLISH:
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

    # Extra keys not in MAP (f-string / dynamic / multiline)
    extra = {
        "chat.ai_thinking": ("🤖 AI is thinking...", "🤖 AI सोच रहा है..."),
        "dialogs.copied_to_clipboard": ("Copied to clipboard.", "क्लिपबोर्ड पर कॉपी हो गया।"),
        "dialogs.unexpected_error": (
            "An unexpected error occurred: {error}",
            "एक अप्रत्याशित त्रुटि हुई: {error}",
        ),
        "dialogs.send_failed": (
            "Send Failed",
            "भेजना विफल",
        ),
        "dialogs.send_failed_msg": (
            "Could not send message.\n\nReason: {reason}\n\n💡 Tip: For local testing, run:\nLICENSE_SERVER_URL=http://localhost:8000 python main_app.py",
            "संदेश नहीं भेजा जा सका।\n\nकारण: {reason}\n\n💡 टिप: स्थानीय परीक्षण के लिए चलाएं:\nLICENSE_SERVER_URL=http://localhost:8000 python main_app.py",
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
