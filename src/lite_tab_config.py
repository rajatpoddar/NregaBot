# lite_tab_config.py
# Lightweight tab configuration for NREGA Bot Lite.
#
# Only the most essential tabs are included — removes heavy/uncommon tabs
# like Macro Manager, File Manager, Feedback, Sarkar Aapke Dwar, etc.
#
# Uses Unicode emoji characters instead of PNG image files for icons,
# resulting in faster startup and lower memory usage.

from typing import Any, Dict


from src.tab_config import _lazy_import


def get_tabs_definition_lite(app: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns a MINIMAL set of tabs for the Lite version.
    Only the most commonly used tabs are included.
    Uses Unicode emoji characters instead of PNG image icons.
    """
    return {
        # 0. Dashboard (Home) — Always first!
        "Dashboard": {
            "Home": {
                "creation_func": _lazy_import("HomeTab", "src.tabs.home_tab"),
                "icon": "🏠"
            },
        },

        # 1. MR & Wage Management (essential MR operations)
        "MR & Wage Management": {
            "Demand": {
                "creation_func": _lazy_import("DemandTab", "src.tabs.demand_tab"),
                "icon": "📋",
                "key": "demand"
            },
            "Work Allocation": {
                "creation_func": _lazy_import("WorkAllocationTab", "src.tabs.work_allocation_tab"),
                "icon": "🔄",
                "key": "work_allocation"
            },
            "Muster Roll Gen": {
                "creation_func": _lazy_import("MusterrollGenTab", "src.tabs.musterroll_gen_tab"),
                "icon": "📄",
                "key": "mr_gen"
            },
            "MR Fill": {
                "creation_func": _lazy_import("MrFillTab", "src.tabs.mr_fill_tab"),
                "icon": "✏️",
                "key": "mr_fill"
            },
            "MR Payment": {
                "creation_func": _lazy_import("MsrTab", "src.tabs.msr_tab"),
                "icon": "💰",
                "key": "msr_payment"
            },
            "Gen Wagelist": {
                "creation_func": _lazy_import("WagelistGenTab", "src.tabs.wagelist_gen_tab"),
                "icon": "📊",
                "key": "wagelist_gen"
            },
            "Send Wagelist": {
                "creation_func": _lazy_import("WagelistSendTab", "src.tabs.wagelist_send_tab"),
                "icon": "📤",
                "key": "wagelist_send"
            },
            "FTO Generation": {
                "creation_func": _lazy_import("FtoGenerationTab", "src.tabs.fto_generation_tab"),
                "icon": "💳",
                "key": "fto_gen"
            },
            "Duplicate MR Print": {
                "creation_func": _lazy_import("DuplicateMrTab", "src.tabs.duplicate_mr_tab"),
                "icon": "🖨️",
                "key": "duplicate_mr"
            },
            "Material Entry": {
                "creation_func": _lazy_import("MaterialEntryTab", "src.tabs.material_entry_tab"),
                "icon": "📦",
                "key": "material_entry"
            },
        },

        # 2. JE & AE Approval (essential)
        "JE & AE Approval": {
            "eMB Entry": {
                "creation_func": _lazy_import("MbEntryTab", "src.tabs.mb_entry_tab"),
                "icon": "📝",
                "key": "mb_entry"
            },
            "eMB Verify": {
                "creation_func": _lazy_import("EmbVerifyTab", "src.tabs.emb_verify_tab"),
                "icon": "✅",
                "key": "emb_verify"
            },
        },

        # 3. Schemes (essential)
        "Schemes Related": {
            "Work Code Gen": {
                "creation_func": _lazy_import("WcGenTab", "src.tabs.wc_gen_tab"),
                "icon": "🔢",
                "key": "wc_gen"
            },
            "IF Editor": {
                "creation_func": _lazy_import("IfEditTab", "src.tabs.if_edit_tab"),
                "icon": "📝",
                "key": "if_editor"
            },
            "Update Estimate": {
                "creation_func": _lazy_import("UpdateEstimateTab", "src.tabs.update_estimate_tab"),
                "icon": "💰",
                "key": "update_estimate"
            },
            "Physical Complete": {
                "creation_func": _lazy_import("PhysicalCompleteTab", "src.tabs.physical_complete_tab"),
                "icon": "🏗️",
                "key": "physical_complete"
            },
            "Scheme Closing": {
                "creation_func": _lazy_import("SchemeClosingTab", "src.tabs.scheme_closing_tab"),
                "icon": "🔒",
                "key": "scheme_closing"
            },
            "Add Activity": {
                "creation_func": _lazy_import("AddActivityTab", "src.tabs.add_activity_tab"),
                "icon": "➕",
                "key": "add_activity"
            },
        },

        # 4. Reports & Tracking (simplified)
        "Reports & Tracking": {
            "MR Tracking": {
                "creation_func": _lazy_import("MrTrackingTab", "src.tabs.mr_tracking_tab"),
                "icon": "🔍",
                "key": "mr_tracking"
            },
            "Dashboard Report": {
                "creation_func": _lazy_import("DashboardReportTab", "src.tabs.dashboard_report_tab"),
                "icon": "📊",
                "key": "dashboard_report"
            },
            "MIS Reports": {
                "creation_func": _lazy_import("MisReportsTab", "src.tabs.mis_reports_tab"),
                "icon": "📈",
                "key": "mis_reports"
            },
            "Issued MR Details": {
                "creation_func": _lazy_import("IssuedMrReportTab", "src.tabs.issued_mr_report_tab"),
                "icon": "📋",
                "key": "issued_mr_report"
            },
        },

        # 5. Smart Tools (essential only)
        "Smart Tools": {
            "Login Automation": {
                "creation_func": _lazy_import("LoginAutomationTab", "src.tabs.login_automation_tab"),
                "icon": "🤖",
                "key": "login_automation"
            },
            "Workcode Extractor": {
                "creation_func": _lazy_import("WorkcodeExtractorTab", "src.tabs.workcode_extractor_tab"),
                "icon": "🔧",
                "key": "wc_extractor"
            },
        },

        # 6. About (simplified)
        "About": {
            "About": {
                "creation_func": _lazy_import("AboutTab", "src.tabs.about_tab"),
                "icon": "ℹ️"
            },
        }
    }
