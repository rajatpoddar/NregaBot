# tab_config.py
#
# P1.2: Lazy Tab Loading — Tab classes are imported ONLY when the tab is
# first accessed (via creation_func). This reduces startup time by ~40-60%
# because none of the 44 heavy tab modules (each potentially importing
# selenium, openpyxl, reportlab, PIL, etc.) are loaded at app start.
#
# The get_tabs_definition() function returns dicts with "creation_func"
# lambdas that import the tab class on first call. The imports are cached
# so subsequent calls reuse the same class.

import threading
from typing import Any, Dict

# Tab-module imports are serialized through this lock. Tab modules (and their
# shared _imports hub) import heavy libraries — previously a concurrent tab
# load (e.g. user click racing a license-validation thread / workflow handoff /
# frozen-build import) could trigger the same slow import twice and crash with
# 'partially initialized module pandas' / 'cannot import name ... from _imports'.
_TAB_MODULE_IMPORT_LOCK = threading.Lock()


def _lazy_import(class_name: str, module_path: str) -> Any:
    """Helper: imports a tab class on first call, caches it for subsequent calls.

    Returns a factory function that lazily imports the module and class
    only when first invoked. The class reference is cached so subsequent
    calls just instantiate without re-importing.

    Thread-safe: the (possibly slow) importlib.import_module() call runs
    under a module-level lock, so two threads can never import tab modules
    concurrently and race on their shared heavy imports.

    NOTE: because the lock is held across import_module(), tab modules must
    NOT call another _lazy_import factory during their own module-level
    import (that would deadlock on the same lock). None do today.
    """
    _cache: Dict[str, Any] = {}
    def factory(parent: Any, app: Any) -> Any:
        nonlocal _cache
        if class_name not in _cache:
            import importlib
            with _TAB_MODULE_IMPORT_LOCK:
                if class_name not in _cache:  # double-checked locking
                    mod = importlib.import_module(module_path)
                    _cache[class_name] = getattr(mod, class_name)
        return _cache[class_name](parent, app)
    return factory


def get_tabs_definition(app: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns the dictionary of all tabs, their icons, and classes.
    Reorganized into 7 specific categories with CORRECTED ICON KEYS.

    Tabs are lazily imported ONLY when creation_func is called (i.e., when
    the user first opens that tab). No tab class is imported at startup.
    """
    # Each creation_func is a lambda that imports the tab class on first call.
    # The lambda caches the imported class so subsequent calls are instant.

    return {
        # 0. Dashboard (Home) — Always first!
        "Dashboard": {
            "Home": {
                "creation_func": _lazy_import("HomeTab", "src.tabs.home_tab"),
                "icon": app.icon_images.get("nrega")
            },
        },

        # 1. MR Related
        "MR & Wage Management": {
            "Demand": {
                "creation_func": _lazy_import("DemandTab", "src.tabs.demand_tab"),
                "icon": app.icon_images.get("emoji_demand"),
                "key": "demand"
            },
            "Work Allocation": {
                "creation_func": _lazy_import("WorkAllocationTab", "src.tabs.work_allocation_tab"),
                "icon": app.icon_images.get("emoji_work_allocation"),
                "key": "work_allocation"
            },
            "Muster Roll Gen": {
                "creation_func": _lazy_import("MusterrollGenTab", "src.tabs.musterroll_gen_tab"),
                "icon": app.icon_images.get("emoji_mr_gen"),
                "key": "mr_gen"
            },
            "Mate/Mistri MR": {
                "creation_func": _lazy_import("MateMrGenTab", "src.tabs.mate_mr_gen_tab"),
                "icon": app.icon_images.get("emoji_mr_gen"),
                "key": "mate_mr"
            },
            "MR Fill": {
                "creation_func": _lazy_import("MrFillTab", "src.tabs.mr_fill_tab"),
                "icon": app.icon_images.get("emoji_mr_fill"),
                "key": "mr_fill"
            },
            "MR Payment": {
                "creation_func": _lazy_import("MsrTab", "src.tabs.msr_tab"),
                "icon": app.icon_images.get("emoji_mr_payment"),
                "key": "msr_payment"
            },
            "Gen Wagelist": {
                "creation_func": _lazy_import("WagelistGenTab", "src.tabs.wagelist_gen_tab"),
                "icon": app.icon_images.get("emoji_gen_wagelist"),
                "key": "wagelist_gen"
            },
            "Send Wagelist": {
                "creation_func": _lazy_import("WagelistSendTab", "src.tabs.wagelist_send_tab"),
                "icon": app.icon_images.get("emoji_send_wagelist"),
                "key": "wagelist_send"
            },
            "FTO Generation": {
                "creation_func": _lazy_import("FtoGenerationTab", "src.tabs.fto_generation_tab"),
                "icon": app.icon_images.get("emoji_fto_gen"),
                "key": "fto_gen"
            },
            "Duplicate MR Print": {
                "creation_func": _lazy_import("DuplicateMrTab", "src.tabs.duplicate_mr_tab"),
                "icon": app.icon_images.get("emoji_duplicate_mr"),
                "key": "duplicate_mr"
            },
            "Material Entry": {
                "creation_func": _lazy_import("MaterialEntryTab", "src.tabs.material_entry_tab"),
                "icon": app.icon_images.get("emoji_material_entry"),
                "key": "material_entry"
            },
        },

        # 2. JE and AE Approval
        "JE & AE Approval": {
            "eMB Entry": {
                "creation_func": _lazy_import("MbEntryTab", "src.tabs.mb_entry_tab"),
                "icon": app.icon_images.get("emoji_mb_entry"),
                "key": "mb_entry"
            },
            "eMB Verify": {
                "creation_func": _lazy_import("EmbVerifyTab", "src.tabs.emb_verify_tab"),
                "icon": app.icon_images.get("emoji_emb_verify"),
                "key": "emb_verify"
            },
        },

        # 3. Schemes Related
        "Schemes Related": {
            "Work Code Gen": {
                "creation_func": _lazy_import("WcGenTab", "src.tabs.wc_gen_tab"),
                "icon": app.icon_images.get("emoji_wc_gen"),
                "key": "wc_gen"
            },
            "IF Editor": {
                "creation_func": _lazy_import("IfEditTab", "src.tabs.if_edit_tab"),
                "icon": app.icon_images.get("emoji_if_editor"),
                "key": "if_editor"
            },
            "Update Estimate": {
                "creation_func": _lazy_import("UpdateEstimateTab", "src.tabs.update_estimate_tab"),
                "icon": app.icon_images.get("emoji_update_estimate"),
                "key": "update_estimate"
            },
            "Physical Complete": {
                "creation_func": _lazy_import("PhysicalCompleteTab", "src.tabs.physical_complete_tab"),
                "icon": app.icon_images.get("emoji_physical_complete"),
                "key": "physical_complete"
            },
            "Scheme Closing": {
                "creation_func": _lazy_import("SchemeClosingTab", "src.tabs.scheme_closing_tab"),
                "icon": app.icon_images.get("emoji_scheme_closing"),
                "key": "scheme_closing"
            },
            "Add Activity": {
                "creation_func": _lazy_import("AddActivityTab", "src.tabs.add_activity_tab"),
                "icon": app.icon_images.get("emoji_add_activity"),
                "key": "add_activity"
            },
        },

        # 4. Verification & Utility
        "Verification & Utility": {
            "Job Card Verify": {
                "creation_func": _lazy_import("JobcardVerifyTab", "src.tabs.jobcard_verify_tab"),
                "icon": app.icon_images.get("emoji_verify_jobcard"),
                "key": "jobcard_verify"
            },
            "Verify ABPS": {
                "creation_func": _lazy_import("AbpsVerifyTab", "src.tabs.abps_verify_tab"),
                "icon": app.icon_images.get("emoji_verify_abps"),
                "key": "verify_abps"
            },
            "Del Work Alloc": {
                "creation_func": _lazy_import("DelWorkAllocTab", "src.tabs.del_work_alloc_tab"),
                "icon": app.icon_images.get("emoji_del_work_alloc"),
                "key": "del_work_alloc"
            },
            "Delete Demand": {
                "creation_func": _lazy_import("DelDemandTab", "src.tabs.del_demand_tab"),
                "icon": app.icon_images.get("emoji_del_demand"),
                "key": "del_demand"
            },
            "Delete Applicant": {
                "creation_func": _lazy_import("DeleteApplicantTab", "src.tabs.delete_applicant_tab"),
                "icon": app.icon_images.get("emoji_delete_applicant"),
                "key": "delete_applicant"
            },
            "Zero MR": {
                "creation_func": _lazy_import("ZeroMrTab", "src.tabs.zero_mr_tab"),
                "icon": app.icon_images.get("emoji_zero_mr"),
                "key": "zero_mr"
            },
            "Resend Rejected WG": {
                "creation_func": _lazy_import("ResendRejectedWgTab", "src.tabs.resend_rejected_wg_tab"),
                "icon": app.icon_images.get("emoji_resend_wg"),
                "key": "resend_rejected_wg"
            },
            "Sarkar Aapke Dwar": {
                "creation_func": _lazy_import("SarkarAapkeDwarTab", "src.tabs.sarkar_aapke_dwar_tab"),
                "icon": app.icon_images.get("emoji_sad_status"),
                "key": "sarkar_aapke_dwar"
            },
            "SAD Update Status": {
                "creation_func": _lazy_import("SadUpdateTab", "src.tabs.sad_update_tab"),
                "icon": app.icon_images.get("emoji_update_outcome"),
                "key": "sad_update_status"
            },
        },

        # 5. Reports Tool
        "Reports & Tracking": {
            "MR Tracking": {
                "creation_func": _lazy_import("MrTrackingTab", "src.tabs.mr_tracking_tab"),
                "icon": app.icon_images.get("emoji_mr_tracking"),
                "key": "mr_tracking"
            },
            "Dashboard Report": {
                "creation_func": _lazy_import("DashboardReportTab", "src.tabs.dashboard_report_tab"),
                "icon": app.icon_images.get("emoji_dashboard_report"),
                "key": "dashboard_report"
            },
            "MIS Reports": {
                "creation_func": _lazy_import("MisReportsTab", "src.tabs.mis_reports_tab"),
                "icon": app.icon_images.get("emoji_mis_reports"),
                "key": "mis_reports"
            },
            "Issued MR Details": {
                "creation_func": _lazy_import("IssuedMrReportTab", "src.tabs.issued_mr_report_tab"),
                "icon": app.icon_images.get("emoji_issued_mr_report"),
                "key": "issued_mr_report"
            },
            "eKYC Report": {
                "creation_func": _lazy_import("EKycReportTab", "src.tabs.ekyc_report_tab"),
                "icon": app.icon_images.get("emoji_ekyc_report"),
                "key": "ekyc_report"
            },
            "Social Audit Report": {
                "creation_func": _lazy_import("SAReportTab", "src.tabs.SA_report_tab"),
                "icon": app.icon_images.get("emoji_social_audit"),
                "key": "social_audit_respond"
            },
            "NMMS Attendance": {
                "creation_func": _lazy_import("NmmsAttendanceTab", "src.tabs.nmms_attendance_tab"),
                "icon": app.icon_images.get("emoji_nmms_attendance"),
                "key": "nmms_attendance"
            },
            "Pending Bills": {
                "creation_func": _lazy_import("PendingBillsTab", "src.tabs.pending_bills_tab"),
                "icon": app.icon_images.get("emoji_pending_bills"),
                "key": "pending_bills"
            },
        },

        # 6. Smart Tool
        "Smart Tools": {
            "Macro Manager": {
                "creation_func": _lazy_import("MacroManagerTab", "src.tabs.macro_manager_tab"),
                "icon": app.icon_images.get("emoji_tools")
            },
            "PDF Merger": {
                "creation_func": _lazy_import("PDFMergerTab", "src.tabs.pdf_merger_tab"),
                "icon": app.icon_images.get("emoji_pdf_merger"),
                "key": "pdf_merger"
            },
            "Workcode Extractor": {
                "creation_func": _lazy_import("WorkcodeExtractorTab", "src.tabs.workcode_extractor_tab"),
                "icon": app.icon_images.get("emoji_wc_extractor"),
                "key": "wc_extractor"
            },
            "File Manager": {
                "creation_func": _lazy_import("FileManagementTab", "src.tabs.file_management_tab"),
                "icon": app.icon_images.get("emoji_file_manager")
            },
        },

        # 7. About & Help
        "About & Help": {
            "About": {
                "creation_func": _lazy_import("AboutTab", "src.tabs.about_tab"),
                "icon": app.icon_images.get("emoji_about")
            },
            "Settings": {
                "creation_func": _lazy_import("SettingsTab", "src.tabs.settings_tab"),
                "icon": app.icon_images.get("settings")
            },
            "WhatsApp Chat": {
                "creation_func": _lazy_import("WhatsAppChatTab", "src.tabs.whatsapp_chat_tab"),
                "icon": app.icon_images.get("whatsapp")
            },
        }
    }
