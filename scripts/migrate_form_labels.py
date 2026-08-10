"""migrate_form_labels.py — wrap hardcoded in-tab form labels, buttons and
placeholders in tr() calls and add the keys to en.json / hi.json.

Handles text=, placeholder_text=, title= and StringVar.set("...") patterns.
Only strings present in the MAP are touched; everything else is left as-is
(safe to run repeatedly).

Usage:  python3 scripts/migrate_form_labels.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# ---------------------------------------------------------------------------
# STRING → (KEY, HINDI). Keys starting with `common.` are shared across tabs.
# ---------------------------------------------------------------------------
MAP = {
    # ── shared / common ──
    "📥 Export to Excel": ("common.export_excel", "📥 एक्सेल में निर्यात करें"),
    "Clear": ("common.clear", "साफ़ करें"),
    "🗑 Clear": ("common.clear", "साफ़ करें"),
    "Save": ("common.save", "सहेजें"),
    "Delete": ("common.delete", "हटाएं"),
    "🗑 Delete": ("common.delete", "हटाएं"),
    "Cancel": ("common.cancel", "रद्द करें"),
    "Add": ("common.add", "जोड़ें"),
    "Select": ("common.select", "चुनें"),
    "Select All": ("common.select_all", "सभी चुनें"),
    "Loading...": ("common.loading", "लोड हो रहा है..."),
    "Loading files...": ("common.loading_files", "फाइलें लोड हो रही हैं..."),
    "DD/MM/YYYY": ("common.date_format", "DD/MM/YYYY"),
    "Select PDF": ("common.select_pdf", "पीडीएफ चुनें"),
    "Download Demo CSV": ("common.download_demo_csv", "डेमो सीएसवी डाउनलोड करें"),
    "Demo CSV": ("common.demo_csv", "डेमो सीएसवी"),
    "Select from Computer": ("common.select_from_computer", "कंप्यूटर से चुनें"),
    "Select from Cloud": ("common.select_from_cloud", "क्लाउड से चुनें"),
    "Select CSV": ("common.select_csv", "सीएसवी चुनें"),
    "Select CSV File": ("common.select_csv_file", "सीएसवी फाइल चुनें"),
    "Browse": ("common.browse", "ब्राउज़ करें"),
    "Get Template": ("common.get_template", "टेम्पलेट प्राप्त करें"),
    "Save Report": ("common.save_report", "रिपोर्ट सहेजें"),
    "Merge PDFs": ("common.merge_pdfs", "पीडीएफ मर्ज करें"),
    "Merge Saved PDFs": ("common.merge_saved_pdfs", "सहेजी पीडीएफ मर्ज करें"),
    "Extract from Text": ("common.extract_from_text", "टेक्स्ट से निकालें"),
    "Enter a base name for the merged file:": ("common.merge_base_name", "मर्ज की गई फाइल के लिए नाम दर्ज करें:"),
    "Output Action:": ("common.output_action", "आउटपुट क्रिया:"),
    "Orientation:": ("common.orientation", "ओरिएंटेशन:"),
    "PDF Scale:": ("common.pdf_scale", "पीडीएफ स्केल:"),
    "Panchayat Name:": ("common.panchayat_name_label", "पंचायत का नाम:"),
    "Panchayat:": ("common.panchayat_label", "पंचायत:"),
    "State:": ("common.state_label", "राज्य:"),
    "District:": ("common.district_label", "जिला:"),
    "Block:": ("common.block_label", "ब्लॉक:"),
    "Enter new profile name to save": ("common.profile_name_placeholder", "सहेजने के लिए नई प्रोफाइल का नाम दर्ज करें"),
    "Success: 0": ("common.success_default", "सफल: 0"),
    "Skipped/Failed: 0": ("common.skipped_failed_default", "छोड़े गए/असफल: 0"),
    "Success: 0 | Failed: 0": ("common.success_failed_default", "सफल: 0 | असफल: 0"),
    "📋 Copy Logs": ("common.copy_logs", "📋 लॉग कॉपी करें"),
    "🗑 Clear Logs": ("common.clear_logs", "🗑 लॉग साफ़ करें"),
    "Applicant Name": ("common.applicant_name_col", "आवेदक का नाम"),
    "Status": ("common.status_col", "स्थिति"),
    "Time": ("common.time_col", "समय"),
    "No file loaded.": ("errors.no_file_loaded", "कोई फाइल लोड नहीं है।"),
    "No file selected": ("errors.no_file_selected", "कोई फाइल चयनित नहीं है"),
    "No data source selected": ("errors.no_data_source", "कोई डेटा स्रोत चयनित नहीं है"),
    "No file": ("errors.no_file", "कोई फाइल नहीं"),

    # ── demand_tab ──
    "< Back": ("form.demand.back", "< पीछे"),
    "Select a file or folder:": ("form.demand.select_file_or_folder", "फाइल या फोल्डर चुनें:"),
    "No .csv / .xlsx files or folders found.": ("form.demand.no_csv_xlsx", "कोई .csv / .xlsx फाइल या फोल्डर नहीं मिला।"),
    "Work Demand From:": ("form.demand.work_demand_from", "कार्य डिमांड तिथि:"),
    "Days:": ("form.demand.days", "दिन:"),
    "No. of Labour:": ("form.demand.no_of_labour", "मजदूरों की संख्या:"),
    "Work Key:": ("form.demand.work_key", "वर्क की:"),
    "📄 Upload Report": ("form.demand.upload_report", "📄 रिपोर्ट अपलोड करें"),
    "🕘 Previous": ("form.demand.previous", "🕘 पिछला"),
    "0 applicants selected": ("form.demand.applicants_selected", "0 आवेदक चयनित"),
    "Quick Select:": ("form.demand.quick_select", "त्वरित चयन:"),
    "Retry Failed Applicants": ("form.demand.retry_failed", "असफल आवेदक पुनः प्रयास करें"),
    "🕘 Previously uploaded eKYC reports": ("form.demand.previous_reports", "🕘 पहले अपलोड की गई ई-केवाईसी रिपोर्ट"),
    "No report loaded.\\nUpload the eKYC & ABPS report first.": ("form.demand.no_report", "कोई रिपोर्ट लोड नहीं है।\\nपहले ई-केवाईसी व एबीपीएस रिपोर्ट अपलोड करें।"),
    "Nothing selected yet.\\nUse Quick Select or Search →": ("form.demand.nothing_selected", "अभी कुछ चयनित नहीं है।\\nत्वरित चयन या खोज का उपयोग करें →"),
    "Panchayat": ("common.panchayat_col", "पंचायत"),
    "Village": ("common.village_col", "गांव"),
    "Job Card No": ("common.jobcard_no_col", "जॉबकार्ड सं."),
    "Count": ("common.count_col", "गिनती"),
    "Type work key (optional) — selected workers will be allocated here after the demand": ("form.demand.workkey_placeholder", "वर्क की टाइप करें (वैकल्पिक) — डिमांड के बाद चयनित मजदूर यहां आवंटित होंगे"),
    "Type JC suffixes e.g.  1/5, 12/44, 10/150  then press Enter": ("form.demand.jc_suffixes", "जेसी सफिक्स टाइप करें जैसे  1/5, 12/44, 10/150  फिर एंटर दबाएं"),
    "🔍  Search by name or JC number to find & tick individually...": ("form.demand.search_placeholder", "🔍  नाम या जेसी संख्या से खोजें और व्यक्तिगत रूप से चुनें..."),
    "Select eKYC Report (Excel/CSV)": ("form.demand.select_ekyc_report", "ई-केवाईसी रिपोर्ट चुनें (एक्सेल/सीएसवी)"),

    # ── wc_gen_tab ──
    "Load Categories from Website": ("form.wc_gen.load_categories", "वेबसाइट से श्रेणियां लोड करें"),
    "Step 1: Load Panchayat & Profile": ("form.wc_gen.step1", "चरण 1: पंचायत और प्रोफाइल लोड करें"),
    "Config Profile:": ("form.wc_gen.config_profile", "कॉन्फिग प्रोफाइल:"),
    "Auto-send successful work codes to IF Editor": ("form.wc_gen.auto_send_if", "सफल वर्क कोड स्वतः आईएफ एडिटर को भेजें"),
    "Step 2: Configure Work Details": ("form.wc_gen.step2", "चरण 2: कार्य विवरण कॉन्फ़िगर करें"),
    "Proposal Date:": ("form.wc_gen.proposal_date", "प्रस्ताव तिथि:"),
    "Work Start Date:": ("form.wc_gen.work_start_date", "कार्य आरंभ तिथि:"),
    "Undertaking PDF (Individual):": ("form.wc_gen.undertaking_pdf", "अंडरटेकिंग पीडीएफ (व्यक्तिगत):"),
    "Step 3: Select Data File": ("form.wc_gen.step3", "चरण 3: डेटा फाइल चुनें"),
    "Generate CSV Online": ("form.wc_gen.generate_csv_online", "सीएसवी ऑनलाइन बनाएं"),
    "Select Undertaking PDF": ("form.wc_gen.select_undertaking_pdf", "अंडरटेकिंग पीडीएफ चुनें"),
    "Select your CSV data file": ("form.wc_gen.select_csv", "अपनी सीएसवी डेटा फाइल चुनें"),

    # ── musterroll_gen_tab / mate_mr_gen_tab ──
    "तारीख से:": ("form.mr_gen.date_from", "तारीख से:"),
    "तारीख को:": ("form.mr_gen.date_to", "तारीख को:"),
    "Select Designation:": ("form.mr_gen.select_designation", "पद चुनें:"),
    "Select Technical Staff:": ("form.mr_gen.select_staff", "तकनीकी स्टाफ चुनें:"),
    "Save generated PDF to Cloud": ("form.mr_gen.save_pdf_cloud", "जनरेट की गई पीडीएफ क्लाउड में सहेजें"),
    "💡 Generated MRs are saved in 'Downloads/NregaBot/MR_Output'.": ("form.mr_gen.output_hint", "💡 जनरेट एमआर 'Downloads/NregaBot/MR_Output' में सहेजी जाती हैं।"),
    "No. of MRs to Print:": ("form.mate_mr.no_of_mrs", "प्रिंट करने के लिए एमआर की संख्या:"),
    "Workers per MR Form:": ("form.mate_mr.workers_per_form", "प्रति एमआर फॉर्म मजदूर:"),
    "💡 Mate/Mistri MRs saved in 'Downloads/NregaBot/MateMR_Output'.": ("form.mate_mr.output_hint", "💡 मेट/मिस्त्री एमआर 'Downloads/NregaBot/MateMR_Output' में सहेजी जाती हैं।"),
    "e.g. 5": ("form.mate_mr.eg_5", "जैसे 5"),
    "e.g. 10": ("form.mate_mr.eg_10", "जैसे 10"),

    # ── material_entry_tab ──
    "Panchayat (For Block Login):": ("form.material_entry.panchayat_block", "पंचायत (ब्लॉक लॉगिन के लिए):"),
    "Work Category:": ("form.material_entry.work_category", "कार्य श्रेणी:"),
    "Vendor Code:": ("form.material_entry.vendor_code", "विक्रेता कोड:"),
    "Bill Date (DD/MM/YYYY):": ("form.material_entry.bill_date", "बिल तिथि (DD/MM/YYYY):"),
    "Material Profiles:": ("form.material_entry.material_profiles", "सामग्री प्रोफाइल:"),
    "Load Profile": ("form.material_entry.load_profile", "प्रोफाइल लोड करें"),
    "Save As:": ("form.material_entry.save_as", "इस रूप में सहेजें:"),
    "💾 Save Profile": ("form.material_entry.save_profile", "💾 प्रोफाइल सहेजें"),
    "Material Details": ("form.material_entry.material_details", "सामग्री विवरण"),
    "+ Add Row": ("common.add_row", "+ पंक्ति जोड़ें"),
    "- Remove Row": ("common.remove_row", "- पंक्ति हटाएं"),
    "Amount: ₹0.00": ("form.material_entry.amount", "राशि: ₹0.00"),
    "GST: ₹0.00": ("form.material_entry.gst", "जीएसटी: ₹0.00"),
    "Grand Total: ₹0.00": ("form.material_entry.grand_total", "कुल योग: ₹0.00"),
    "Format: WorkSearchKey, BillNumber (One per line)\\nExample: 25554, 855": ("form.material_entry.format_hint", "प्रारूप: WorkSearchKey, BillNumber (प्रति पंक्ति एक)\\nउदाहरण: 25554, 855"),
    "e.g., 6430": ("form.material_entry.vendor_example", "जैसे, 6430"),
    "Profile name": ("form.material_entry.profile_name", "प्रोफाइल का नाम"),
    "Rate": ("form.material_entry.rate", "दर"),
    "Qty": ("form.material_entry.qty", "मात्रा"),

    # ── mr_tracking_tab ──
    "Pending for Filling": ("form.mr_tracking.pending_filling", "भरने के लिए लंबित"),
    "T+8 to T+15 (Zero MR)": ("form.mr_tracking.t8_t15", "T+8 से T+15 (शून्य एमआर)"),
    "Pending for ABPS": ("form.mr_tracking.pending_abps", "एबीपीएस के लिए लंबित"),
    "Copy Workcodes": ("form.mr_tracking.copy_workcodes", "वर्ककोड कॉपी करें"),
    "Run MR Payment": ("form.mr_tracking.run_mr_payment", "एमआर भुगतान चलाएं"),
    "Run eMB Entry": ("form.mr_tracking.run_emb_entry", "ईएमबी प्रविष्टि चलाएं"),
    "Forward to Zero MR": ("form.mr_tracking.forward_zero_mr", "शून्य एमआर में भेजें"),
    "Generate Pendency Report (T0-T8)": ("form.mr_tracking.pendency_report", "लंबितता रिपोर्ट बनाएं (T0-T8)"),
    "Export ABPS Report": ("form.mr_tracking.export_abps", "एबीपीएस रिपोर्ट निर्यात करें"),
    "Panchayat-wise Pendency Analysis": ("form.mr_tracking.pendency_analysis", "पंचायत-वार लंबितता विश्लेषण"),
    "Download Excel Report": ("common.download_excel_report", "एक्सेल रिपोर्ट डाउनलोड करें"),

    # ── if_edit_tab ──
    "Automation Mode:": ("form.if_edit.automation_mode", "ऑटोमेशन मोड:"),
    "Configuration Profile:": ("form.if_edit.config_profile", "कॉन्फ़िगरेशन प्रोफाइल:"),
    "Data Source:": ("form.if_edit.data_source", "डेटा स्रोत:"),
    "Enable Page 2 & 3 (Convergence Work)": ("form.if_edit.enable_pages", "पेज 2 और 3 सक्षम करें (कन्वर्जेंस कार्य)"),
    "--- Convergence Settings (If Enabled) ---": ("form.if_edit.convergence_section", "--- कन्वर्जेंस सेटिंग्स (यदि सक्षम) ---"),
    "--- Estimated Cost (in Lakhs) ---": ("form.if_edit.estimated_cost", "--- अनुमानित लागत (लाखों में) ---"),
    "--- Financial Sanction ---": ("form.if_edit.financial_sanction", "--- वित्तीय स्वीकृति ---"),
    "💡 Note: These values will be applied to all work codes in the CSV.": ("form.if_edit.note", "💡 नोट: ये मान सीएसवी के सभी वर्क कोड पर लागू होंगे।"),
    "--- Add Activities ---": ("form.if_edit.add_activities", "--- गतिविधियां जोड़ें ---"),
    "One activity per line. Format: Activity Code,Unit Price,Quantity": ("form.if_edit.activity_format", "प्रति पंक्ति एक गतिविधि। प्रारूप: Activity Code,Unit Price,Quantity"),
    "--- Add Materials (Optional) ---": ("form.if_edit.add_materials", "--- सामग्री जोड़ें (वैकल्पिक) ---"),
    "One material per line. Format: Material Name,Unit Price,Quantity": ("form.if_edit.material_format", "प्रति पंक्ति एक सामग्री। प्रारूप: Material Name,Unit Price,Quantity"),

    # ── sarkar_aapke_dwar_tab ──
    "Backlog Entry Mode": ("form.sad.backlog_mode", "बैकलॉग प्रविष्टि मोड"),
    "Mode 1: Bulk Entry (via Excel or CSV)": ("form.sad.mode1", "मोड 1: बल्क प्रविष्टि (एक्सेल या सीएसवी से)"),
    "Common Settings": ("form.sad.common_settings", "सामान्य सेटिंग्स"),
    "Applicant Remarks:": ("form.sad.applicant_remarks", "आवेदक टिप्पणी:"),
    "Scheme Type:": ("form.sad.scheme_type", "योजना प्रकार:"),
    "Scheme/Service:": ("form.sad.scheme_service", "योजना/सेवा:"),
    "Scheme Remarks:": ("form.sad.scheme_remarks", "योजना टिप्पणी:"),
    "Scheme Remarks": ("form.sad.scheme_remarks_col", "योजना टिप्पणी"),
    "Ack Number": ("form.sad.ack_number_col", "एक नंबर"),
    "Select .xlsx or .csv file with Applicant Details...": ("form.sad.select_file_placeholder", "आवेदक विवरण वाली .xlsx या .csv फाइल चुनें..."),
    "Default Applicant Remarks (if not in file)": ("form.sad.default_applicant_remarks", "डिफ़ॉल्ट आवेदक टिप्पणी (यदि फाइल में न हो)"),
    "Default Scheme Remarks (if not in file)": ("form.sad.default_scheme_remarks", "डिफ़ॉल्ट योजना टिप्पणी (यदि फाइल में न हो)"),
}

# Only these file stems are processed in this pass
TARGET_FILES = [
    "src/tabs/demand_tab.py",
    "src/tabs/wc_gen_tab.py",
    "src/tabs/musterroll_gen_tab.py",
    "src/tabs/mate_mr_gen_tab.py",
    "src/tabs/material_entry_tab.py",
    "src/tabs/mr_tracking_tab.py",
    "src/tabs/if_edit_tab.py",
    "src/tabs/sarkar_aapke_dwar_tab.py",
]

ATTR_PATTERNS = [
    re.compile(r'''(\b(?:text|placeholder_text|title)\s*=\s*)"([^"]*)"'''),
]
SET_PATTERN = re.compile(r'''(\bset\(\s*)"([^"]*)"\s*\)''')


def escape_for_json(s: str) -> str:
    return s


def main() -> None:
    en = json.load(open(EN_PATH, encoding="utf-8"))
    hi = json.load(open(HI_PATH, encoding="utf-8"))

    total_wrapped = 0
    for path in TARGET_FILES:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        orig = src
        wrapped_in_file = 0

        def wrap_attr(m: re.Match) -> str:
            nonlocal wrapped_in_file
            attr = m.group(1)
            value = m.group(2)
            if value in MAP:
                key, _ = MAP[value]
                wrapped_in_file += 1
                return f'{attr}tr("{key}")'
            return m.group(0)

        def wrap_set(m: re.Match) -> str:
            nonlocal wrapped_in_file
            value = m.group(2)
            if value in MAP:
                key, _ = MAP[value]
                wrapped_in_file += 1
                return f'{m.group(1)}tr("{key}"){m.group(0)[m.group(0).rfind(")"):]}'
            return m.group(0)

        for pat in ATTR_PATTERNS:
            src = pat.sub(wrap_attr, src)
        src = SET_PATTERN.sub(wrap_set, src)

        if src != orig:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            print(f"  {path}: {wrapped_in_file} strings wrapped")
        else:
            print(f"  {path}: (no change)")
        total_wrapped += wrapped_in_file

    # Add locale entries
    added = 0
    for value, (key, hindi) in MAP.items():
        if key not in en:
            en[key] = value
            added += 1
        hi[key] = hindi

    json.dump(en, open(EN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nTotal wrapped: {total_wrapped}; new en.json keys: {added}")
    print(f"en.json: {len(en)} keys, hi.json: {len(hi)} keys")


if __name__ == "__main__":
    main()
