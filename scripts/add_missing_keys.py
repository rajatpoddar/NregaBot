"""add_missing_keys.py — add the missing en.json entries for the new nav/app/tab
keys used by the sidebar, header and tab-header migration.

Run BEFORE writing Hindi translations so hi.json can copy from en.json.

Usage:  python3 scripts/add_missing_keys.py
"""
import json

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# app.* — English values match what the code passed to tr() as `default`
APP_EN = {
    "app.status_ready": "Ready",
    "app.status_finished": "Finished",
    "app.stop_all": "STOP ALL",
    "app.running_prefix": "▶ Running: ",
    "app.emergency_stop_hint": "Emergency Stop — Click to halt all automations",
    "app.welcome_loading": "Welcome to NREGA Bot! Loading...",
    "app.welcome_prefix": "Welcome,",
    "app.welcome_login_prompt": "Log in, then select a task.",
    "app.tooltip.workcode_extractor": "Open Workcode Extractor",
    "app.tooltip.auto_login": "Auto Login to NREGA",
    "app.tooltip.launch_chrome": "Launch Google Chrome",
    "app.tooltip.launch_edge": "Launch Microsoft Edge",
    "app.tooltip.launch_firefox": "Launch Mozilla Firefox",
    "app.tooltip.switch_theme": "Switch Theme (Light/Dark)",
    "app.tooltip.toggle_sound": "Toggle Sound Effects",
    "app.tooltip.auto_minimize": "Auto-Minimize on Start",
    "app.tooltip.activity_log": "View Activity Log (Settings → Activity Log)",
    "app.tooltip.cloud_files": "Open Cloud Files",
    "app.tooltip.join_community": "Join Community",
    "app.tooltip.open_settings": "Open Settings",
    "app.tooltip.server_status": "Server Connection Status",
}

# tab.* — English values are the exact header titles/subtitles from the code
TAB_EN = {
    "tab.abps_verify.title": "Verify ABPS",
    "tab.abps_verify.subtitle": "Verify ABPS (UID-linked) accounts for jobcard holders in bulk.",
    "tab.add_activity.title": "Add Activity",
    "tab.add_activity.subtitle": "Add a new activity (unit price + quantity) for each pending work key.",
    "tab.dashboard_report.title": "Dashboard Report",
    "tab.dashboard_report.subtitle": "Scrape the delay-monitoring dashboard for pending E-MRs of a panchayat.",
    "tab.del_demand.title": "Delete Demand",
    "tab.del_demand.subtitle": "Delete demands for one village, or all villages in a Panchayat, on the portal.",
    "tab.del_work_alloc.title": "Delete Work Allocation",
    "tab.del_work_alloc.subtitle": "Delete work allocations for a Panchayat, optionally filtered by date(s).",
    "tab.delete_applicant.title": "Delete Applicant",
    "tab.delete_applicant.subtitle": "Delete eKYC applicants from an Excel list — auto-match, select, and delete.",
    "tab.demand.title": "Demand",
    "tab.demand.subtitle": "Upload the eKYC & ABPS report, select job cards and create work demands on the portal.",
    "tab.duplicate_mr.title": "Duplicate MR Print",
    "tab.duplicate_mr.subtitle": "Print or save duplicate Muster Rolls for the selected Panchayat.",
    "tab.ekyc_report.title": "eKYC Report",
    "tab.ekyc_report.subtitle": "Scan eKYC & ABPS status for jobcard holders — panchayat-wise summary.",
    "tab.emb_verify.title": "eMB Verify",
    "tab.emb_verify.subtitle": "Verify eMB entries against the sanctioned amount for the selected Panchayat.",
    "tab.fto_generation.title": "FTO Generation",
    "tab.fto_generation.subtitle": "Sign pending FTOs using the DSC-signed Old Firefox session, or delete them.",
    "tab.if_edit.title": "IF Editor",
    "tab.if_edit.subtitle": "Edit IF details on the portal for work codes from a CSV or WC Gen.",
    "tab.issued_mr_report.title": "Issued MR Report",
    "tab.issued_mr_report.subtitle": "Pull issued muster-roll reports with workcodes, results and ABPS data.",
    "tab.jobcard_verify.title": "Verify Jobcard",
    "tab.jobcard_verify.subtitle": "Verify jobcards with photo upload and account-number checks in bulk.",
    "tab.login_automation.title": "Login & Navigation Automation",
    "tab.login_automation.subtitle": "Auto-select Financial Year, District & Block — you only enter User ID & Password.",
    "tab.macro_manager.title": "Macro Manager",
    "tab.macro_manager.subtitle": "Chain multiple automations into one queue and run them back-to-back.",
    "tab.mate_mr_gen.title": "Mate / Mistri MR Generation",
    "tab.mate_mr_gen.subtitle": "Generate blank Mate/Mistri (Skilled/Semi-Skilled) Muster Rolls.",
    "tab.material_entry.title": "Material Entry",
    "tab.material_entry.subtitle": "Enter material details (rate, quantity, GST) for multiple work keys and bill numbers.",
    "tab.mb_entry.title": "eMB Entry",
    "tab.mb_entry.subtitle": "Enter measurements for Muster Rolls directly into the eMB portal.",
    "tab.mis_reports.title": "MIS Reports",
    "tab.mis_reports.subtitle": "Download multiple NREGA MIS reports into a single formatted Excel file.",
    "tab.mr_fill.title": "MR Fill",
    "tab.mr_fill.subtitle": "Mark holiday columns and fill Muster Roll attendance for the selected Panchayat.",
    "tab.mr_tracking.title": "MR Tracking",
    "tab.mr_tracking.subtitle": "Track muster-roll status, pendency and ABPS — with one-click actions.",
    "tab.msr.title": "MR Payment (MSR)",
    "tab.msr.subtitle": "Process & verify Muster Roll payments against the sanctioned wage amount.",
    "tab.musterroll_gen.title": "Muster Roll Generation",
    "tab.musterroll_gen.subtitle": "Generate Muster Rolls for workers between the selected dates.",
    "tab.nmms_attendance.title": "NMMS Attendance",
    "tab.nmms_attendance.subtitle": "Record NMMS attendance with date, group photos and geo-coordinates.",
    "tab.pdf_merger.title": "PDF Merger",
    "tab.pdf_merger.subtitle": "Merge multiple PDFs in order, name the output and save as one file.",
    "tab.physical_complete.title": "Physical Complete",
    "tab.physical_complete.subtitle": "Mark works as physically complete on the portal for the selected Panchayat.",
    "tab.resend_rejected_wg.title": "Resend Rejected Wagelist",
    "tab.resend_rejected_wg.subtitle": "Resend wagelists that were rejected by the portal, for the selected year.",
    "tab.sad_update.title": "SAD Update Status",
    "tab.sad_update.subtitle": "Update / dispose Sarkar Aapke Dwar applications in bulk.",
    "tab.sarkar_aapke_dwar.title": "Sarkar Aapke Dwar",
    "tab.sarkar_aapke_dwar.subtitle": "Fill and submit Sarkar Aapke Dwar applications in bulk or monitor mode.",
    "tab.scheme_closing.title": "Scheme Closing",
    "tab.scheme_closing.subtitle": "Close schemes by filling completion details for the selected Panchayat.",
    "tab.update_estimate.title": "Update Estimate",
    "tab.update_estimate.subtitle": "Update the estimated outcome for multiple work codes in one go.",
    "tab.wagelist_gen.title": "Wagelist Generation",
    "tab.wagelist_gen.subtitle": "Generate wagelists for pending work codes and optionally auto-send them.",
    "tab.wagelist_send.title": "Send Wagelist",
    "tab.wagelist_send.subtitle": "Send generated (or all) pending wagelists via the EFMS portal.",
    "tab.wc_gen.title": "Work Code Generation",
    "tab.wc_gen.subtitle": "Generate work codes on the NREGA portal from a CSV file.",
    "tab.work_allocation.title": "Work Allocation",
    "tab.work_allocation.subtitle": "Allocate selected work keys to job cards on the portal.",
    "tab.zero_mr.title": "Zero MR",
    "tab.zero_mr.subtitle": "Generate a zero-value Muster Roll for works with no payments.",
}

# nav.tab.* — sidebar tab display names (keys are English names with spaces)
NAV_TAB_EN = {
    "Home": "Home",
    "Demand": "Demand",
    "Work Allocation": "Work Allocation",
    "Muster Roll Gen": "Muster Roll Gen",
    "Mate/Mistri MR": "Mate/Mistri MR",
    "MR Fill": "MR Fill",
    "MR Payment": "MR Payment",
    "Gen Wagelist": "Gen Wagelist",
    "Send Wagelist": "Send Wagelist",
    "FTO Generation": "FTO Generation",
    "Duplicate MR Print": "Duplicate MR Print",
    "Material Entry": "Material Entry",
    "eMB Entry": "eMB Entry",
    "eMB Verify": "eMB Verify",
    "Work Code Gen": "Work Code Gen",
    "IF Editor": "IF Editor",
    "Update Estimate": "Update Estimate",
    "Physical Complete": "Physical Complete",
    "Scheme Closing": "Scheme Closing",
    "Add Activity": "Add Activity",
    "Job Card Verify": "Job Card Verify",
    "Verify ABPS": "Verify ABPS",
    "Del Work Alloc": "Del Work Alloc",
    "Delete Demand": "Delete Demand",
    "Delete Applicant": "Delete Applicant",
    "Zero MR": "Zero MR",
    "Resend Rejected WG": "Resend Rejected WG",
    "Sarkar Aapke Dwar": "Sarkar Aapke Dwar",
    "SAD Update Status": "SAD Update Status",
    "MR Tracking": "MR Tracking",
    "Dashboard Report": "Dashboard Report",
    "MIS Reports": "MIS Reports",
    "Issued MR Details": "Issued MR Details",
    "eKYC Report": "eKYC Report",
    "Social Audit Report": "Social Audit Report",
    "NMMS Attendance": "NMMS Attendance",
    "Pending Bills": "Pending Bills",
    "Macro Manager": "Macro Manager",
    "PDF Merger": "PDF Merger",
    "Workcode Extractor": "Workcode Extractor",
    "File Manager": "File Manager",
    "About": "About",
    "Settings": "Settings",
    "WhatsApp Chat": "WhatsApp Chat",
}

NAV_CAT_EN = {
    "Dashboard": "Dashboard",
    "MR & Wage Management": "MR & Wage Management",
    "JE & AE Approval": "JE & AE Approval",
    "Schemes Related": "Schemes Related",
    "Verification & Utility": "Verification & Utility",
    "Reports & Tracking": "Reports & Tracking",
    "Smart Tools": "Smart Tools",
    "About & Help": "About & Help",
    "All Automations": "All Automations",
}


def main() -> None:
    en = json.load(open(EN_PATH, encoding="utf-8"))
    hi = json.load(open(HI_PATH, encoding="utf-8"))

    # Build nav keys (English value = the name itself)
    nav_en = {f"nav.tab.{k}": v for k, v in NAV_TAB_EN.items()}
    nav_en.update({f"nav.cat.{k}": v for k, v in NAV_CAT_EN.items()})

    additions = {}
    additions.update(APP_EN)
    additions.update(TAB_EN)
    additions.update(nav_en)

    added = 0
    for k, v in additions.items():
        if k not in en:
            en[k] = v
            added += 1
        # hi.json: copy English for now — real Hindi translation is added by hand later
        if k not in hi:
            hi[k] = v

    json.dump(en, open(EN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Added {added} new keys to en.json; hi.json synced (English placeholders).")
    print(f"en.json now has {len(en)} keys; hi.json has {len(hi)} keys.")


if __name__ == "__main__":
    main()
