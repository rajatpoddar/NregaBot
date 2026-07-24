# tab_config.py

def get_tabs_definition(app):
    """
    Returns the dictionary of all tabs, their icons, and classes.
    Reorganized into 7 specific categories with CORRECTED ICON KEYS.
    """
    # --- LAZY LOAD IMPORTS ---
    from src.tabs.home_tab import HomeTab
    from src.tabs.msr_tab import MsrTab
    from src.tabs.wagelist_gen_tab import WagelistGenTab
    from src.tabs.wagelist_send_tab import WagelistSendTab
    from src.tabs.wc_gen_tab import WcGenTab
    from src.tabs.mb_entry_tab import MbEntryTab
    from src.tabs.if_edit_tab import IfEditTab
    from src.tabs.musterroll_gen_tab import MusterrollGenTab
    from src.tabs.about_tab import AboutTab
    from src.tabs.jobcard_verify_tab import JobcardVerifyTab
    from src.tabs.fto_generation_tab import FtoGenerationTab
    from src.tabs.workcode_extractor_tab import WorkcodeExtractorTab
    from src.tabs.add_activity_tab import AddActivityTab
    from src.tabs.abps_verify_tab import AbpsVerifyTab
    from src.tabs.del_work_alloc_tab import DelWorkAllocTab
    from src.tabs.update_estimate_tab import UpdateEstimateTab
    from src.tabs.duplicate_mr_tab import DuplicateMrTab
    from src.tabs.feedback_tab import FeedbackTab
    from src.tabs.file_management_tab import FileManagementTab
    from src.tabs.scheme_closing_tab import SchemeClosingTab
    from src.tabs.emb_verify_tab import EmbVerifyTab
    from src.tabs.resend_rejected_wg_tab import ResendRejectedWgTab
    from src.tabs.sarkar_aapke_dwar_tab import SarkarAapkeDwarTab
    from src.tabs.sad_update_tab import SadUpdateTab
    from src.tabs.mr_fill_tab import MrFillTab
    from src.tabs.mr_tracking_tab import MrTrackingTab
    from src.tabs.zero_mr_tab import ZeroMrTab
    from src.tabs.demand_tab import DemandTab
    from src.tabs.work_allocation_tab import WorkAllocationTab
    from src.tabs.mis_reports_tab import MisReportsTab
    from src.tabs.issued_mr_report_tab import IssuedMrReportTab
    from src.tabs.login_automation_tab import LoginAutomationTab
    from src.tabs.pdf_merger_tab import PDFMergerTab
    from src.tabs.dashboard_report_tab import DashboardReportTab
    from src.tabs.ekyc_report_tab import EKycReportTab
    from src.tabs.SA_report_tab import SAReportTab
    from src.tabs.macro_manager_tab import MacroManagerTab
    from src.tabs.del_demand_tab import DelDemandTab
    from src.tabs.material_entry_tab import MaterialEntryTab
    from src.tabs.delete_applicant_tab import DeleteApplicantTab
    from src.tabs.physical_complete_tab import PhysicalCompleteTab
    from src.tabs.mate_mr_gen_tab import MateMrGenTab
    from src.tabs.nmms_attendance_tab import NmmsAttendanceTab

    return {
        # 0. Dashboard (Home) — Always first!
        "Dashboard": {
            "Home": {"creation_func": lambda p, a: HomeTab(p, a), "icon": app.icon_images.get("nrega")},
        },

        # 1. MR Related
        "MR & Wage Management": {
            "Demand": {"creation_func": DemandTab, "icon": app.icon_images.get("emoji_demand"), "key": "demand"},
            # Ensure 'work_allocation.png' exists in assets/icons/emojis/
            "Work Allocation": {"creation_func": WorkAllocationTab, "icon": app.icon_images.get("emoji_work_allocation"), "key": "work_allocation"},
            "Muster Roll Gen": {"creation_func": MusterrollGenTab, "icon": app.icon_images.get("emoji_mr_gen"), "key": "mr_gen"},
            "Mate/Mistri MR": {"creation_func": MateMrGenTab, "icon": app.icon_images.get("emoji_mr_gen"), "key": "mate_mr"},
            "MR Fill": {"creation_func": MrFillTab, "icon": app.icon_images.get("emoji_mr_fill"), "key": "mr_fill"},
            "MR Payment": {"creation_func": MsrTab, "icon": app.icon_images.get("emoji_mr_payment"), "key": "msr_payment"},
            "Gen Wagelist": {"creation_func": WagelistGenTab, "icon": app.icon_images.get("emoji_gen_wagelist"), "key": "wagelist_gen"},
            "Send Wagelist": {"creation_func": WagelistSendTab, "icon": app.icon_images.get("emoji_send_wagelist"), "key": "wagelist_send"},
            "FTO Generation": {"creation_func": FtoGenerationTab, "icon": app.icon_images.get("emoji_fto_gen"), "key": "fto_gen"},
            "Duplicate MR Print": {"creation_func": DuplicateMrTab, "icon": app.icon_images.get("emoji_duplicate_mr"), "key": "duplicate_mr"},
            "Material Entry": {"creation_func": MaterialEntryTab, "icon": app.icon_images.get("emoji_material_entry"), "key": "material_entry"},
        },

        # 2. JE and AE Approval
        "JE & AE Approval": {
            # Ensure 'mb_entry.png' exists in assets/icons/emojis/
            "eMB Entry": {"creation_func": MbEntryTab, "icon": app.icon_images.get("emoji_mb_entry"), "key": "mb_entry"},
            "eMB Verify": {"creation_func": EmbVerifyTab, "icon": app.icon_images.get("emoji_emb_verify"), "key": "emb_verify"},
        },

        # 3. Schemes Related
        "Schemes Related": {
            "Work Code Gen": {"creation_func": WcGenTab, "icon": app.icon_images.get("emoji_wc_gen"), "key": "wc_gen"},
            "IF Editor": {"creation_func": IfEditTab, "icon": app.icon_images.get("emoji_if_editor"), "key": "if_editor"},
            # Renamed key to match new file: update_estimate.png
            "Update Estimate": {"creation_func": UpdateEstimateTab, "icon": app.icon_images.get("emoji_update_estimate"), "key": "update_estimate"},
            "Physical Complete": {"creation_func": PhysicalCompleteTab, "icon": app.icon_images.get("emoji_physical_complete"), "key": "physical_complete"},
            "Scheme Closing": {"creation_func": SchemeClosingTab, "icon": app.icon_images.get("emoji_scheme_closing"), "key": "scheme_closing"},
            "Add Activity": {"creation_func": AddActivityTab, "icon": app.icon_images.get("emoji_add_activity"), "key": "add_activity"},
        },

        # 4. Verification & Utility
        "Verification & Utility": {
            "Job Card Verify": {"creation_func": JobcardVerifyTab, "icon": app.icon_images.get("emoji_verify_jobcard"), "key": "jobcard_verify"},
            "Verify ABPS": {"creation_func": AbpsVerifyTab, "icon": app.icon_images.get("emoji_verify_abps"), "key": "verify_abps"},
            "Del Work Alloc": {"creation_func": DelWorkAllocTab, "icon": app.icon_images.get("emoji_del_work_alloc"), "key": "del_work_alloc"},
            "Delete Demand": {"creation_func": DelDemandTab, "icon": app.icon_images.get("emoji_del_demand"), "key": "del_demand"},
            "Delete Applicant": {"creation_func": DeleteApplicantTab, "icon": app.icon_images.get("emoji_delete_applicant"), "key": "delete_applicant"},
            "Zero MR": {"creation_func": ZeroMrTab, "icon": app.icon_images.get("emoji_zero_mr"), "key": "zero_mr"},
            "Resend Rejected WG": {"creation_func": ResendRejectedWgTab, "icon": app.icon_images.get("emoji_resend_wg"), "key": "resend_rejected_wg"},
            "Sarkar Aapke Dwar": {"creation_func": SarkarAapkeDwarTab, "icon": app.icon_images.get("emoji_sad_status"), "key": "sarkar_aapke_dwar"},
            "SAD Update Status": {"creation_func": SadUpdateTab, "icon": app.icon_images.get("emoji_update_outcome"), "key": "sad_update_status"},
        },

        # 5. Reports Tool
        "Reports & Tracking": {
            "MR Tracking": {"creation_func": MrTrackingTab, "icon": app.icon_images.get("emoji_mr_tracking"), "key": "mr_tracking"},
            "Dashboard Report": {"creation_func": DashboardReportTab, "icon": app.icon_images.get("emoji_dashboard_report"), "key": "dashboard_report"},
            "MIS Reports": {"creation_func": MisReportsTab, "icon": app.icon_images.get("emoji_mis_reports"), "key": "mis_reports"},
            "Issued MR Details": {"creation_func": IssuedMrReportTab, "icon": app.icon_images.get("emoji_issued_mr_report"), "key": "issued_mr_report"},
            "eKYC Report": {"creation_func": EKycReportTab, "icon": app.icon_images.get("emoji_ekyc_report"), "key": "ekyc_report"},
            "Social Audit Report": {"creation_func": SAReportTab, "icon": app.icon_images.get("emoji_social_audit"), "key": "social_audit_respond"},
            "NMMS Attendance": {"creation_func": NmmsAttendanceTab, "icon": app.icon_images.get("emoji_nmms_attendance"), "key": "nmms_attendance"},
        },

        # 6. Smart Tool
        "Smart Tools": {
            # Changed 'tools' to 'emoji_tools' to match file
            "Macro Manager": {"creation_func": lambda p, a: MacroManagerTab(p, a), "icon": app.icon_images.get("emoji_tools")},
            "Login Automation": {"creation_func": LoginAutomationTab, "icon": app.icon_images.get("emoji_login_automation"), "key": "login_automation"},
            "PDF Merger": {"creation_func": PDFMergerTab, "icon": app.icon_images.get("emoji_pdf_merger"), "key": "pdf_merger"},
            "Workcode Extractor": {"creation_func": WorkcodeExtractorTab, "icon": app.icon_images.get("emoji_wc_extractor"), "key": "wc_extractor"},
            "File Manager": {"creation_func": FileManagementTab, "icon": app.icon_images.get("emoji_file_manager")},
        },

        # 7. About & Help
        "About & Help": {
             "About": {"creation_func": AboutTab, "icon": app.icon_images.get("emoji_about")},
             "Feedback": {"creation_func": FeedbackTab, "icon": app.icon_images.get("emoji_feedback")},
        }
    }