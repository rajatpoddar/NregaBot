# lite_tab_config.py
# Lightweight tab configuration for NREGA Bot Lite.
#
# Only the most essential automation tabs are included — as specified:
#   Muster Roll Generate, Mate / Mistri MR, MR Fill, MSR Process,
#   Gen Wagelist, Send Wagelist, Duplicate MR, EMB Entry, EMB Verify,
#   Physical Complete, Scheme Closing, Delete Work Allocation,
#   Delete Demand, Workcode Extractor, EKYC Report, Login Automation
#
# Uses Unicode emoji characters instead of PNG image files for icons,
# resulting in faster startup and lower memory usage.

from typing import Any, Dict


from src.tab_config import _lazy_import


def get_tabs_definition_lite(app: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns a MINIMAL set of tabs for the Lite version.
    Only the most commonly used automation tabs are included.
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
            "Muster Roll Gen": {
                "creation_func": _lazy_import("MusterrollGenTab", "src.tabs.musterroll_gen_tab"),
                "icon": "📄",
                "key": "mr_gen"
            },
            "Mate / Mistri MR": {
                "creation_func": _lazy_import("MateMrGenTab", "src.tabs.mate_mr_gen_tab"),
                "icon": "🛠️",
                "key": "mate_mr"
            },
            "MR Fill": {
                "creation_func": _lazy_import("MrFillTab", "src.tabs.mr_fill_tab"),
                "icon": "✏️",
                "key": "mr_fill"
            },
            "MSR Process": {
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
            "Duplicate MR": {
                "creation_func": _lazy_import("DuplicateMrTab", "src.tabs.duplicate_mr_tab"),
                "icon": "🖨️",
                "key": "duplicate_mr"
            },
        },

        # 2. EMB Approvals
        "EMB Approvals": {
            "EMB Entry": {
                "creation_func": _lazy_import("MbEntryTab", "src.tabs.mb_entry_tab"),
                "icon": "📝",
                "key": "mb_entry"
            },
            "EMB Verify": {
                "creation_func": _lazy_import("EmbVerifyTab", "src.tabs.emb_verify_tab"),
                "icon": "✅",
                "key": "emb_verify"
            },
        },

        # 3. Schemes
        "Schemes": {
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
            "Delete Work Allocation": {
                "creation_func": _lazy_import("DelWorkAllocTab", "src.tabs.del_work_alloc_tab"),
                "icon": "🗑️",
                "key": "del_work_alloc"
            },
            "Delete Demand": {
                "creation_func": _lazy_import("DelDemandTab", "src.tabs.del_demand_tab"),
                "icon": "🗑️",
                "key": "del_demand"
            },
        },

        # 4. Smart Tools
        "Smart Tools": {
            "Login Automation": {
                "creation_func": _lazy_import("LoginAutomationTab", "src.tabs.login_automation_tab"),
                "icon": "🤖",
                "key": "login_automation"
            },
            "MR Tracking": {
                "creation_func": _lazy_import("MrTrackingTab", "src.tabs.mr_tracking_tab"),
                "icon": "📍",
                "key": "mr_tracking"
            },
            "Workcode Extractor": {
                "creation_func": _lazy_import("WorkcodeExtractorTab", "src.tabs.workcode_extractor_tab"),
                "icon": "🔧",
                "key": "wc_extractor"
            },
            "EKYC Report": {
                "creation_func": _lazy_import("EKycReportTab", "src.tabs.ekyc_report_tab"),
                "icon": "📇",
                "key": "ekyc_report"
            },
        },

        # 5. About (simplified)
        "About": {
            "About": {
                "creation_func": _lazy_import("AboutTab", "src.tabs.about_tab"),
                "icon": "ℹ️"
            },
        }
    }
