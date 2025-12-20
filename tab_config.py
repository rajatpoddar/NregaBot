# tab_config.py

def get_tabs_definition(app):
    """
    Returns the dictionary of all tabs, their icons, and classes.
    Lazy imports are used to keep application startup fast.
    """
    # --- LAZY LOAD IMPORTS (Taaki app turant khule) ---
    from tabs.msr_tab import MsrTab
    from tabs.wagelist_gen_tab import WagelistGenTab
    from tabs.wagelist_send_tab import WagelistSendTab
    from tabs.wc_gen_tab import WcGenTab
    from tabs.mb_entry_tab import MbEntryTab
    from tabs.if_edit_tab import IfEditTab
    from tabs.musterroll_gen_tab import MusterrollGenTab
    from tabs.about_tab import AboutTab
    from tabs.jobcard_verify_tab import JobcardVerifyTab
    from tabs.fto_generation_tab import FtoGenerationTab
    from tabs.workcode_extractor_tab import WorkcodeExtractorTab
    from tabs.add_activity_tab import AddActivityTab
    from tabs.abps_verify_tab import AbpsVerifyTab
    from tabs.del_work_alloc_tab import DelWorkAllocTab
    from tabs.update_estimate_tab import UpdateEstimateTab
    from tabs.duplicate_mr_tab import DuplicateMrTab
    from tabs.feedback_tab import FeedbackTab
    from tabs.file_management_tab import FileManagementTab
    from tabs.scheme_closing_tab import SchemeClosingTab
    from tabs.emb_verify_tab import EmbVerifyTab
    from tabs.resend_rejected_wg_tab import ResendRejectedWgTab
    from tabs.SA_report_tab import SAReportTab
    from tabs.mis_reports_tab import MisReportsTab
    from tabs.demand_tab import DemandTab
    from tabs.mr_tracking_tab import MrTrackingTab
    from tabs.dashboard_report_tab import DashboardReportTab
    from tabs.mr_fill_tab import MrFillTab
    from tabs.pdf_merger_tab import PdfMergerTab
    from tabs.issued_mr_report_tab import IssuedMrReportTab
    from tabs.zero_mr_tab import ZeroMrTab
    from tabs.work_allocation_tab import WorkAllocationTab
    from tabs.sarkar_aapke_dwar_tab import SarkarAapkeDwarTab
    from tabs.sad_update_tab import SADUpdateStatusTab
    from tabs.login_automation_tab import LoginAutomationTab
    from tabs.ekyc_report_tab import EKycReportTab

    # --- DEFINITIONS ---
    return {
        "Core NREGA Tasks": {
            "MR Gen": {"creation_func": MusterrollGenTab, "icon": app.icon_images.get("emoji_mr_gen"), "key": "muster"},
            "MR Fill": {"creation_func": MrFillTab, "icon": app.icon_images.get("emoji_mr_fill"), "key": "mr_fill"},
            "MR Payment": {"creation_func": MsrTab, "icon": app.icon_images.get("emoji_mr_payment"), "key": "msr"},
            "Gen Wagelist": {"creation_func": WagelistGenTab, "icon": app.icon_images.get("emoji_gen_wagelist"), "key": "gen"},
            "Send Wagelist": {"creation_func": WagelistSendTab, "icon": app.icon_images.get("emoji_send_wagelist"), "key": "send"},
            "FTO Generation": {"creation_func": FtoGenerationTab, "icon": app.icon_images.get("emoji_fto_gen"), "key": "fto_gen"},
            "Scheme Closing": {"creation_func": SchemeClosingTab, "icon": app.icon_images.get("emoji_scheme_closing"), "key": "scheme_close"},
            "Del Work Alloc": {"creation_func": DelWorkAllocTab, "icon": app.icon_images.get("emoji_del_work_alloc"), "key": "del_work_alloc"},
            "Duplicate MR Print": {"creation_func": DuplicateMrTab, "icon": app.icon_images.get("emoji_duplicate_mr"), "key": "dup_mr"},
            "Demand": {"creation_func": DemandTab, "icon": app.icon_images.get("emoji_demand"), "key": "demand"},
            "Allocation": {"creation_func": WorkAllocationTab, "icon": app.icon_images.get("emoji_work_alloc"), "key": "allocation"},
        },
        "JE & AE Automation": {
            "eMB Entry": {"creation_func": MbEntryTab, "icon": app.icon_images.get("emoji_emb_entry"), "key": "mb_entry"},
            "eMB Verify": {"creation_func": EmbVerifyTab, "icon": app.icon_images.get("emoji_emb_verify"), "key": "emb_verify"},
        },
        "Records & Workcode": {
            "WC Gen": {"creation_func": WcGenTab, "icon": app.icon_images.get("emoji_wc_gen"), "key": "wc_gen"},
            "IF Editor": {"creation_func": IfEditTab, "icon": app.icon_images.get("emoji_if_editor"), "key": "if_edit"},
            "Add Activity": {"creation_func": AddActivityTab, "icon": app.icon_images.get("emoji_add_activity"), "key": "add_activity"},
            "Update Estimate": {"creation_func": UpdateEstimateTab, "icon": app.icon_images.get("emoji_update_outcome"), "key": "update_outcome"},
        },
        "Utilities & Verification": {
            "Verify Jobcard": {"creation_func": JobcardVerifyTab, "icon": app.icon_images.get("emoji_verify_jobcard"), "key": "jc_verify"},
            "Verify ABPS": {"creation_func": AbpsVerifyTab, "icon": app.icon_images.get("emoji_verify_abps"), "key": "abps_verify"},
            "Workcode Extractor": {"creation_func": WorkcodeExtractorTab, "icon": app.icon_images.get("emoji_wc_extractor"), "key": "wc_extract"},
            "Resend Rejected WG": {"creation_func": ResendRejectedWgTab, "icon": app.icon_images.get("emoji_resend_wg"), "key": "resend_wg"},
            "PDF Merger": {"creation_func": PdfMergerTab, "icon": app.icon_images.get("emoji_pdf_merger"), "key": "pdf_merger"},
            "Zero Mr": {"creation_func": ZeroMrTab, "icon": app.icon_images.get("emoji_zero_mr"), "key": "zero_mr"},
            "File Manager": {"creation_func": FileManagementTab, "icon": app.icon_images.get("emoji_file_manager"), "key": "file_manager"},
        },
        "AYASAD": {
            "Sarkar Aapke Dwar": {"creation_func": SarkarAapkeDwarTab, "icon": app.icon_images.get("emoji_sad_auto"), "key": "sad_auto"},
            "SAD Update Status": {"creation_func": SADUpdateStatusTab, "icon": app.icon_images.get("emoji_sad_status"), "key": "sad_status"},
        },
        "Reporting": {
            "Social Audit Report": {"creation_func": SAReportTab, "icon": app.icon_images.get("emoji_social_audit"), "key": "social_audit_respond"},
            "MIS Reports": {"creation_func": MisReportsTab, "icon": app.icon_images.get("emoji_mis_reports"), "key": "mis_reports"},
            "MR Tracking": {"creation_func": MrTrackingTab, "icon": app.icon_images.get("emoji_mr_tracking"), "key": "mr_tracking"},
            "Issued MR Details": {"creation_func": IssuedMrReportTab, "icon": app.icon_images.get("emoji_issued_mr_report"), "key": "issued_mr_report"},
            "Dashboard Report": {"creation_func": DashboardReportTab, "icon": app.icon_images.get("emoji_dashboard_report"), "key": "dashboard_report"},
            "eKYC Report": {"creation_func": EKycReportTab, "icon": app.icon_images.get("emoji_ekyc_report"), "key": "ekyc_report"},
        },
        "Application": {
             "Feedback": {"creation_func": FeedbackTab, "icon": app.icon_images.get("emoji_feedback")},
             "About": {"creation_func": AboutTab, "icon": app.icon_images.get("emoji_about")},
             "Login Automation": {"creation_func": LoginAutomationTab, "icon": app.icon_images.get("emoji_login_automation")},
        }
    }