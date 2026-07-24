# lite_tab_config.py
# Lightweight tab configuration for NREGA Bot Lite.
#
# Only the most essential tabs are included — removes heavy/uncommon tabs
# like Macro Manager, File Manager, Feedback, Sarkar Aapke Dwar, etc.
#
# Uses the same lazy-loading pattern as tab_config.py but with fewer tabs,
# resulting in faster startup and lower memory usage.

from typing import Any, Dict


from src.tab_config import _lazy_import


def get_tabs_definition_lite(app: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns a MINIMAL set of tabs for the Lite version.
    Only the most commonly used tabs are included.
    """
    return {
        # 0. Dashboard (Home) — Always first!
        "Dashboard": {
            "Home": {
                "creation_func": _lazy_import("HomeTab", "src.tabs.home_tab"),
                "icon": app.icon_images.get("nrega")
            },
        },

        # 1. MR & Wage Management (essential MR operations)
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

        # 2. JE & AE Approval (essential)
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

        # 3. Schemes (essential)
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

        # 4. Reports & Tracking (simplified)
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
        },

        # 5. Smart Tools (essential only)
        "Smart Tools": {
            "Login Automation": {
                "creation_func": _lazy_import("LoginAutomationTab", "src.tabs.login_automation_tab"),
                "icon": app.icon_images.get("emoji_login_automation"),
                "key": "login_automation"
            },
        },

        # 6. About (simplified)
        "About": {
            "About": {
                "creation_func": _lazy_import("AboutTab", "src.tabs.about_tab"),
                "icon": app.icon_images.get("emoji_about")
            },
        }
    }
