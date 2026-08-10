"""translate_hi.py — write real Hindi translations into hi.json for the new
app.* / tab.* / nav.* keys added by add_missing_keys.py.

Usage:  python3 scripts/translate_hi.py
"""
import json

HI_PATH = "src/locales/hi.json"

# ── app.* — header / footer / status ──
APP_HI = {
    "app.status_ready": "तैयार",
    "app.status_finished": "पूर्ण हुआ",
    "app.stop_all": "सब रोकें",
    "app.running_prefix": "▶ चल रहा है: ",
    "app.emergency_stop_hint": "आपातकालीन रोक — सभी ऑटोमेशन रोकने के लिए क्लिक करें",
    "app.welcome_loading": "एनआरईजीए बॉट में आपका स्वागत है! लोड हो रहा है...",
    "app.welcome_prefix": "स्वागत है,",
    "app.welcome_login_prompt": "लॉगिन करें, फिर कोई कार्य चुनें।",
    "app.tooltip.workcode_extractor": "वर्क कोड एक्सट्रैक्टर खोलें",
    "app.tooltip.auto_login": "एनआरईजीए में ऑटो लॉगिन",
    "app.tooltip.launch_chrome": "गूगल क्रोम खोलें",
    "app.tooltip.launch_edge": "माइक्रोसॉफ्ट एज खोलें",
    "app.tooltip.launch_firefox": "मोज़िला फायरफॉक्स खोलें",
    "app.tooltip.switch_theme": "थीम बदलें (लाइट/डार्क)",
    "app.tooltip.toggle_sound": "ध्वनि चालू/बंद करें",
    "app.tooltip.auto_minimize": "स्टार्ट पर ऑटो-मिनिमाइज़",
    "app.tooltip.activity_log": "एक्टिविटी लॉग देखें (सेटिंग्स → एक्टिविटी लॉग)",
    "app.tooltip.cloud_files": "क्लाउड फाइलें खोलें",
    "app.tooltip.join_community": "कम्युनिटी से जुड़ें",
    "app.tooltip.open_settings": "सेटिंग्स खोलें",
    "app.tooltip.server_status": "सर्वर कनेक्शन स्थिति",
}

# ── tab.* — page headers (title + subtitle) ──
TAB_HI = {
    "tab.abps_verify.title": "एबीपीएस सत्यापन",
    "tab.abps_verify.subtitle": "जॉबकार्ड धारकों के एबीपीएस (यूआईडी-लिंक्ड) खाते बैच में सत्यापित करें।",
    "tab.add_activity.title": "गतिविधि जोड़ें",
    "tab.add_activity.subtitle": "हर लंबित वर्क की के लिए नई गतिविधि (इकाई मूल्य + मात्रा) जोड़ें।",
    "tab.dashboard_report.title": "डैशबोर्ड रिपोर्ट",
    "tab.dashboard_report.subtitle": "पंचायत के लंबित ई-एमआर के लिए विलंब-निगरानी डैशबोर्ड से डेटा लें।",
    "tab.del_demand.title": "डिमांड हटाएं",
    "tab.del_demand.subtitle": "पोर्टल पर एक गांव या पंचायत के सभी गांवों की डिमांड हटाएं।",
    "tab.del_work_alloc.title": "कार्य आवंटन हटाएं",
    "tab.del_work_alloc.subtitle": "पंचायत के कार्य आवंटन हटाएं, वैकल्पिक रूप से तारीख के अनुसार फ़िल्टर करें।",
    "tab.delete_applicant.title": "आवेदक हटाएं",
    "tab.delete_applicant.subtitle": "एक्सेल सूची से ई-केवाईसी आवेदक हटाएं — ऑटो-मैच, चयन और हटाएं।",
    "tab.demand.title": "डिमांड",
    "tab.demand.subtitle": "ई-केवाईसी व एबीपीएस रिपोर्ट अपलोड करें, जॉबकार्ड चुनें और पोर्टल पर कार्य डिमांड बनाएं।",
    "tab.duplicate_mr.title": "डुप्लिकेट एमआर प्रिंट",
    "tab.duplicate_mr.subtitle": "चयनित पंचायत के डुप्लिकेट मस्टर रोल प्रिंट या सेव करें।",
    "tab.ekyc_report.title": "ई-केवाईसी रिपोर्ट",
    "tab.ekyc_report.subtitle": "जॉबकार्ड धारकों की ई-केवाईसी व एबीपीएस स्थिति स्कैन करें — पंचायत-वार सारांश।",
    "tab.emb_verify.title": "ईएमबी सत्यापन",
    "tab.emb_verify.subtitle": "चयनित पंचायत के स्वीकृत राशि के अनुसार ईएमबी प्रविष्टियां सत्यापित करें।",
    "tab.fto_generation.title": "एफटीओ निर्माण",
    "tab.fto_generation.subtitle": "डीएससी-हस्ताक्षरित पुराने फायरफॉक्स सत्र से लंबित एफटीओ पर हस्ताक्षर करें, या हटाएं।",
    "tab.if_edit.title": "आईएफ संपादक",
    "tab.if_edit.subtitle": "सीएसवी या वर्क कोड जनरेशन से वर्क कोड के लिए पोर्टल पर आईएफ विवरण संपादित करें।",
    "tab.issued_mr_report.title": "जारी एमआर रिपोर्ट",
    "tab.issued_mr_report.subtitle": "वर्ककोड, परिणाम और एबीपीएस डेटा के साथ जारी मस्टर-रोल रिपोर्ट प्राप्त करें।",
    "tab.jobcard_verify.title": "जॉबकार्ड सत्यापन",
    "tab.jobcard_verify.subtitle": "फोटो अपलोड और खाता-संख्या जांच के साथ बैच में जॉबकार्ड सत्यापित करें।",
    "tab.login_automation.title": "लॉगिन और नेविगेशन ऑटोमेशन",
    "tab.login_automation.subtitle": "वित्तीय वर्ष, जिला व ब्लॉक स्वतः चुनें — आपको केवल यूजर आईडी व पासवर्ड दर्ज करना है।",
    "tab.macro_manager.title": "मैक्रो मैनेजर",
    "tab.macro_manager.subtitle": "कई ऑटोमेशन को एक कतार में जोड़ें और लगातार चलाएं।",
    "tab.mate_mr_gen.title": "मेट / मिस्त्री एमआर निर्माण",
    "tab.mate_mr_gen.subtitle": "खाली मेट/मिस्त्री (कुशल/अर्ध-कुशल) मस्टर रोल तैयार करें।",
    "tab.material_entry.title": "सामग्री प्रविष्टि",
    "tab.material_entry.subtitle": "कई वर्क की व बिल संख्या के लिए सामग्री विवरण (दर, मात्रा, जीएसटी) दर्ज करें।",
    "tab.mb_entry.title": "ईएमबी प्रविष्टि",
    "tab.mb_entry.subtitle": "मस्टर रोल की माप सीधे ईएमबी पोर्टल पर दर्ज करें।",
    "tab.mis_reports.title": "एमआईएस रिपोर्ट",
    "tab.mis_reports.subtitle": "कई एनआरईजीए एमआईएस रिपोर्ट एक स्वरूपित एक्सेल फाइल में डाउनलोड करें।",
    "tab.mr_fill.title": "एमआर भरें",
    "tab.mr_fill.subtitle": "छुट्टी कॉलम चिह्नित करें और चयनित पंचायत के लिए मस्टर रोल उपस्थिति भरें।",
    "tab.mr_tracking.title": "एमआर ट्रैकिंग",
    "tab.mr_tracking.subtitle": "मस्टर-रोल स्थिति, लंबितता और एबीपीएस ट्रैक करें — वन-क्लिक क्रियाओं के साथ।",
    "tab.msr.title": "एमआर भुगतान (एमएसआर)",
    "tab.msr.subtitle": "स्वीकृत मजदूरी राशि के अनुसार मस्टर रोल भुगतान प्रक्रिया करें और सत्यापित करें।",
    "tab.musterroll_gen.title": "मस्टर रोल निर्माण",
    "tab.musterroll_gen.subtitle": "चयनित तारीखों के बीच मजदूरों के लिए मस्टर रोल तैयार करें।",
    "tab.nmms_attendance.title": "एनएमएमएस उपस्थिति",
    "tab.nmms_attendance.subtitle": "तारीख, समूह फोटो और जियो-निर्देशांक के साथ एनएमएमएस उपस्थिति दर्ज करें।",
    "tab.pdf_merger.title": "पीडीएफ विलय",
    "tab.pdf_merger.subtitle": "कई पीडीएफ क्रम से जोड़ें, नाम दें और एक फाइल के रूप में सहेजें।",
    "tab.physical_complete.title": "भौतिक पूर्णता",
    "tab.physical_complete.subtitle": "चयनित पंचायत के लिए पोर्टल पर कार्यों को भौतिक रूप से पूर्ण चिह्नित करें।",
    "tab.resend_rejected_wg.title": "अस्वीकृत वेजलिस्ट पुनः भेजें",
    "tab.resend_rejected_wg.subtitle": "चयनित वर्ष के लिए पोर्टल द्वारा अस्वीकृत वेजलिस्ट पुनः भेजें।",
    "tab.sad_update.title": "एसएडी स्थिति अपडेट",
    "tab.sad_update.subtitle": "सरकार आपके द्वार आवेदनों को बैच में अपडेट/निपटान करें।",
    "tab.sarkar_aapke_dwar.title": "सरकार आपके द्वार",
    "tab.sarkar_aapke_dwar.subtitle": "सरकार आपके द्वार आवेदन बैच या मॉनिटर मोड में भरें और जमा करें।",
    "tab.scheme_closing.title": "योजना समापन",
    "tab.scheme_closing.subtitle": "चयनित पंचायत के लिए पूर्णता विवरण भरकर योजनाएं बंद करें।",
    "tab.update_estimate.title": "अनुमान अपडेट",
    "tab.update_estimate.subtitle": "कई वर्क कोड के लिए अनुमानित परिणाम एक साथ अपडेट करें।",
    "tab.wagelist_gen.title": "वेजलिस्ट निर्माण",
    "tab.wagelist_gen.subtitle": "लंबित वर्क कोड के लिए वेजलिस्ट तैयार करें और वैकल्पिक रूप से स्वतः भेजें।",
    "tab.wagelist_send.title": "वेजलिस्ट भेजें",
    "tab.wagelist_send.subtitle": "ईएफएमएस पोर्टल के माध्यम से तैयार (या सभी लंबित) वेजलिस्ट भेजें।",
    "tab.wc_gen.title": "वर्क कोड निर्माण",
    "tab.wc_gen.subtitle": "सीएसवी फाइल से एनआरईजीए पोर्टल पर वर्क कोड तैयार करें।",
    "tab.work_allocation.title": "कार्य आवंटन",
    "tab.work_allocation.subtitle": "चयनित वर्क की को पोर्टल पर जॉबकार्ड में आवंटित करें।",
    "tab.zero_mr.title": "शून्य एमआर",
    "tab.zero_mr.subtitle": "बिना भुगतान वाले कार्यों के लिए शून्य-मूल्य मस्टर रोल तैयार करें।",
}

# ── nav.tab.* — sidebar tab names ──
NAV_TAB_HI = {
    "nav.tab.Home": "होम",
    "nav.tab.Demand": "डिमांड",
    "nav.tab.Work Allocation": "कार्य आवंटन",
    "nav.tab.Muster Roll Gen": "मस्टर रोल जनरेशन",
    "nav.tab.Mate/Mistri MR": "मेट/मिस्त्री एमआर",
    "nav.tab.MR Fill": "एमआर भरें",
    "nav.tab.MR Payment": "एमआर भुगतान",
    "nav.tab.Gen Wagelist": "वेजलिस्ट बनाएं",
    "nav.tab.Send Wagelist": "वेजलिस्ट भेजें",
    "nav.tab.FTO Generation": "एफटीओ निर्माण",
    "nav.tab.Duplicate MR Print": "डुप्लिकेट एमआर प्रिंट",
    "nav.tab.Material Entry": "सामग्री प्रविष्टि",
    "nav.tab.eMB Entry": "ईएमबी प्रविष्टि",
    "nav.tab.eMB Verify": "ईएमबी सत्यापन",
    "nav.tab.Work Code Gen": "वर्क कोड जनरेशन",
    "nav.tab.IF Editor": "आईएफ संपादक",
    "nav.tab.Update Estimate": "अनुमान अपडेट",
    "nav.tab.Physical Complete": "भौतिक पूर्णता",
    "nav.tab.Scheme Closing": "योजना समापन",
    "nav.tab.Add Activity": "गतिविधि जोड़ें",
    "nav.tab.Job Card Verify": "जॉबकार्ड सत्यापन",
    "nav.tab.Verify ABPS": "एबीपीएस सत्यापन",
    "nav.tab.Del Work Alloc": "कार्य आवंटन हटाएं",
    "nav.tab.Delete Demand": "डिमांड हटाएं",
    "nav.tab.Delete Applicant": "आवेदक हटाएं",
    "nav.tab.Zero MR": "शून्य एमआर",
    "nav.tab.Resend Rejected WG": "अस्वीकृत वेजलिस्ट पुनः भेजें",
    "nav.tab.Sarkar Aapke Dwar": "सरकार आपके द्वार",
    "nav.tab.SAD Update Status": "एसएडी स्थिति अपडेट",
    "nav.tab.MR Tracking": "एमआर ट्रैकिंग",
    "nav.tab.Dashboard Report": "डैशबोर्ड रिपोर्ट",
    "nav.tab.MIS Reports": "एमआईएस रिपोर्ट",
    "nav.tab.Issued MR Details": "जारी एमआर विवरण",
    "nav.tab.eKYC Report": "ई-केवाईसी रिपोर्ट",
    "nav.tab.Social Audit Report": "सामाजिक लेखापरीक्षा रिपोर्ट",
    "nav.tab.NMMS Attendance": "एनएमएमएस उपस्थिति",
    "nav.tab.Pending Bills": "लंबित बिल",
    "nav.tab.Macro Manager": "मैक्रो मैनेजर",
    "nav.tab.PDF Merger": "पीडीएफ विलय",
    "nav.tab.Workcode Extractor": "वर्ककोड एक्सट्रैक्टर",
    "nav.tab.File Manager": "फाइल मैनेजर",
    "nav.tab.About": "जानकारी",
    "nav.tab.Settings": "सेटिंग्स",
    "nav.tab.WhatsApp Chat": "व्हाट्सएप चैट",
}

# ── nav.cat.* — sidebar category names ──
NAV_CAT_HI = {
    "nav.cat.Dashboard": "डैशबोर्ड",
    "nav.cat.MR & Wage Management": "एमआर और मजदूरी प्रबंधन",
    "nav.cat.JE & AE Approval": "जेई और एई स्वीकृति",
    "nav.cat.Schemes Related": "योजनाएं संबंधित",
    "nav.cat.Verification & Utility": "सत्यापन और उपयोगिता",
    "nav.cat.Reports & Tracking": "रिपोर्ट और ट्रैकिंग",
    "nav.cat.Smart Tools": "स्मार्ट टूल्स",
    "nav.cat.About & Help": "जानकारी और सहायता",
    "nav.cat.All Automations": "सभी ऑटोमेशन",
}


def main() -> None:
    hi = json.load(open(HI_PATH, encoding="utf-8"))
    updates = {}
    updates.update(APP_HI)
    updates.update(TAB_HI)
    updates.update(NAV_TAB_HI)
    updates.update(NAV_CAT_HI)

    translated = 0
    for k, v in updates.items():
        hi[k] = v
        translated += 1

    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Translated {translated} keys in hi.json.")


if __name__ == "__main__":
    main()
