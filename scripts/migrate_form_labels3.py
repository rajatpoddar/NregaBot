"""migrate_form_labels3.py — batch 3: migrate in-tab form strings in
emb_verify_tab, add_activity_tab, scheme_closing_tab, physical_complete_tab,
jobcard_verify_tab to tr() and add locale entries.

Shares common.* keys with earlier batches (only NEW per-tab keys are defined
here; the merge script applies the full combined map).

Usage:  python3 scripts/migrate_form_labels3.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

MAP = {
    # ── emb_verify_tab ──
    "Verify Amount (₹):": ("form.emb_verify.verify_amount", "राशि सत्यापित करें (₹):"),
    "Enter Work Codes (one per line). Leave blank to process all.": ("form.emb_verify.work_codes_hint", "वर्क कोड दर्ज करें (प्रति पंक्ति एक)। सभी संसाधित करने के लिए खाली छोड़ें।"),

    # ── add_activity_tab ──
    "Unit Price (₹):": ("form.add_activity.unit_price", "इकाई मूल्य (₹):"),
    "Quantity:": ("form.add_activity.quantity", "मात्रा:"),

    # ── scheme_closing_tab ──
    "Actual Benefited Area:": ("form.scheme_closing.actual_area", "वास्तविक लाभान्वित क्षेत्र:"),
    "Measured by (Designation):": ("form.scheme_closing.measured_by_designation", "मापकर्ता (पद):"),
    "Measured by (Name):": ("form.scheme_closing.measured_by_name", "मापकर्ता (नाम):"),
    "Completion Cert. Start No:": ("form.scheme_closing.cert_start_no", "पूर्णता प्रमाणपत्र आरंभ संख्या:"),
    "Completion Date:": ("form.scheme_closing.completion_date", "पूर्णता तिथि:"),
    "Skip final confirmation": ("form.scheme_closing.skip_confirmation", "अंतिम पुष्टि छोड़ें"),
    "e.g., 1": ("form.scheme_closing.eg_1", "जैसे, 1"),
    "e.g., 54 (will auto-increment for each work code)": ("form.scheme_closing.eg_54", "जैसे, 54 (हर वर्क कोड के लिए स्वतः बढ़ेगा)"),

    # ── physical_complete_tab ──
    "Auto-Forward to Scheme Closing after success": ("form.physical_complete.auto_forward", "सफलता के बाद स्वतः योजना समापन पर भेजें"),
    "Forward to Scheme Closing ➡": ("form.physical_complete.forward_btn", "योजना समापन पर भेजें ➡"),

    # ── jobcard_verify_tab ──
    "Village Name:": ("form.jobcard_verify.village_name", "गांव का नाम:"),
    "Process all villages in this Panchayat": ("form.jobcard_verify.all_villages", "इस पंचायत के सभी गांवों की प्रक्रिया करें"),
    "Verify only with Account Number": ("form.jobcard_verify.account_only", "केवल खाता संख्या से सत्यापन करें"),
    "Select Photo Folder...": ("form.jobcard_verify.select_photo_folder", "फोटो फोल्डर चुनें..."),
    "Select Folder Containing Photos": ("form.jobcard_verify.select_photo_folder_title", "फोटो वाला फोल्डर चुनें"),
}

TARGET_FILES = [
    "src/tabs/emb_verify_tab.py",
    "src/tabs/add_activity_tab.py",
    "src/tabs/scheme_closing_tab.py",
    "src/tabs/physical_complete_tab.py",
    "src/tabs/jobcard_verify_tab.py",
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
