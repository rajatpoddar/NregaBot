# config.py
# This file contains centralized configuration settings for the NREGA Bot.
from typing import Any, Dict, List, Tuple, Union

# --- Application & Brand Info ---
APP_NAME: str = "NREGA Bot"
APP_SHORT_NAME: str = "NREGA Bot"
APP_TAGLINE: str = "Your NREGA Task Management Companion"
APP_DESCRIPTION: str = "A comprehensive tool for managing NREGA tasks efficiently."
APP_AUTHOR: str = "Rajat Poddar"
APP_AUTHOR_EMAIL: str = "Rajatpoddar@outlook.com"
APP_VERSION: str = "3.1.5"
import os
LICENSE_SERVER_URL: str = os.environ.get('LICENSE_SERVER_URL', 'https://license.nregabot.com')

# --- Beta build support ---
# scripts/build_beta_portable.bat bundles a config/beta.json marker into the
# portable EXE. When present, the app runs as a "beta" build:
#   * APP_VERSION is overridden to the beta version (e.g. 3.0.8-beta)
#   * All update checks from version.json are disabled
# Normal (installer) builds never contain this marker -> BETA_BUILD = False
BETA_BUILD: bool = False


def _detect_beta_build() -> bool:
    """Detect the bundled config/beta.json marker and apply beta overrides."""
    global APP_VERSION
    try:
        import json as _json
        from src.utils import resource_path
        marker = resource_path(os.path.join("config", "beta.json"))
        if os.path.exists(marker):
            with open(marker, "r", encoding="utf-8") as f:
                _data = _json.load(f)
            _ver = _data.get("version")
            if _ver:
                APP_VERSION = str(_ver)
            return True
    except Exception:
        pass
    return False


BETA_BUILD = _detect_beta_build()
# Clean numeric version sent to the license server on the wire. The server
# may not understand pre-release suffixes like "-beta" (client-side
# parse_version strips them, but the server is out of our control).
APP_VERSION_WIRE: str = APP_VERSION.split('-')[0]
MAIN_WEBSITE_URL: str = "https://nregabot.com"
# Websites opened by default when the user launches a managed browser
# (Chrome / Edge / Firefox) from the app. First entry opens in the main
# tab, the rest open as additional tabs.
DEFAULT_LAUNCH_URLS: List[str] = [
    MAIN_WEBSITE_URL,
    "https://bookmark.nregabot.com/",
    "https://vbgramg.nregabot.com/",
]
SUPPORT_EMAIL: str = "nregabot@gmail.com"

# --- Evolution API Configuration (for WhatsApp messaging) ---
EVO_BASE_URL: str = "http://192.168.29.101:8087"
EVO_INSTANCE: str = "NregaBot"
EVO_API_KEY: str = "NregaBotSecretKey123"

# --- Platform & UI Configuration ---
import platform
OS_SYSTEM: str = platform.system()

# ============================================================================
# CENTRALIZED COLOR PALETTE
# All UI colors should be defined here and referenced via config.COLORS.
# ============================================================================
ColorValue = Union[str, Tuple[str, str]]
COLORS: Dict[str, ColorValue] = {
    # === SURFACE / BACKGROUND ===
    "bg_dark": "#2B2B2B",           # Dark mode main bg (footer, splash, header)
    "bg_darker": "#1D1E1E",         # Dark mode container bg (header, cards)
    "bg_medium": "#333333",         # Medium dark bg (overlay, options)
    "bg_light": "#FFFFFF",           # Light mode main bg (splash, cards, header)
    "bg_light_alt": "#F3F4F6",      # Light alt bg (overlay, splash outer, hover)
    "bg_loader": "#212325",         # Loader outer bg (dark)
    "bg_loader_inner": ("#F3F4F6", "#212325"),  # Loader fg_color tuple

    # === TEXT COLORS ===
    "text_dark": "#111827",          # Near-black (headings, primary text light)
    "text_dark_alt": "#374151",      # Dark gray (body text light)
    "text_medium": "#6B7280",        # Medium gray (secondary text)
    "text_light": "#9CA3AF",         # Light gray (tertiary text)
    "text_border": "#D1D5DB",        # Gray border
    "text_border_dark": "#565B5E",  # Dark border
    "text_hover": "#E5E7EB",         # Light hover bg
    "text_hover_dark": "#374151",   # Dark hover bg
    "text_bright": "#DCE4EE",        # Bright text on dark (headings)
    "text_muted_dark": "#767676",    # Muted dark text
    "text_muted_light": "#9D9D9D",   # Muted light text
    "text_white": "#F3F4F6",         # Near-white text on dark
    "text_skeleton_light": "#E0E0E0", # Skeleton placeholder light
    "text_skeleton_dark_1": "#2D3748", # Skeleton placeholder dark
    "text_skeleton_dark_2": "#4A5568", # Skeleton placeholder dark alt
    "text_skeleton_light_alt": "#EEEEEE", # Skeleton placeholder light alt

    # === BLUE / PRIMARY ACCENT ===
    "blue": "#3B82F6",               # Primary blue
    "blue_hover": "#2563EB",         # Blue hover
    "blue_light": "#60A5FA",         # Blue light accent
    "blue_dark": "#1565C0",          # Blue dark
    "blue_border": "#BFDBFE",        # Blue light border
    "blue_bg": "#DBEAFE",            # Blue very light bg
    "blue_bg_alt": "#EFF6FF",        # Blue extra light bg
    "blue_bg_nav": "#E3F2FD",        # Blue nav active bg
    "blue_hover_nav": "#BBDEFB",     # Blue nav hover
    "blue_bg_dark": "#1E3A5F",       # Blue dark bg
    "blue_tab_active": "#1D4ED8",    # Blue active tab
    "blue_tab_hover": "#1E40AF",     # Blue tab hover
    "blue_link": "#0EA5E9",          # Link blue/cyan mix
    "blue_link_hover": "#0284C7",    # Link hover

    # === GREEN / SUCCESS ===
    "green": "#16A34A",              # Green accent
    "green_light": "#4ADE80",         # Green light accent
    "green_button": "#2E8B57",       # Green start button
    "green_button_hover": "#1F5E39", # Green start button hover
    "green_status": "#38A169",        # Green status active
    "green_export": "#107C10",        # Green export button
    "green_launch": "#108842",        # Green Firefox launch
    "green_file": "#22C55E",          # Green file status
    "green_del_app": "#10B981",       # Green delete-app count
    "green_dark_bg": "#14532D",      # Dark green bg
    "green_light_bg": "#BBF7D0",      # Light green bg
    "green_bg": "#F0FDF4",            # Very light green bg
    "green_success_bg": "#DCFCE7",    # Success bg light
    "green_success_fg": "#166534",    # Success fg dark
    "green_bg_btn": "#C8E6C9",        # Green button bg light
    "green_dark_btn": "#2E7D32",      # Green button bg dark (softer)
    "green_very_light": "#E8F5E9",   # Green very light
    "green_dashboard": "#4A55A2",      # Dashboard report button
    "green_dashboard_hover": "#5E69B8", # Dashboard report hover
    "green_whatsapp": "#25D366",       # WhatsApp green

    # === RED / ERROR ===
    "red": "#DC2626",                 # Red accent
    "red_light": "#F87171",           # Red light accent
    "red_button": "#C53030",          # Red stop button
    "red_button_hover": "#9B2C2C",   # Red stop button hover
    "red_delete": "#D32F2F",          # Red delete button
    "red_delete_hover": "#B71C1C",    # Red delete hover
    "red_error": "#EF4444",           # Red error status
    "red_expired": "#E53E3E",         # Red expired/error
    "red_dark_hover": "#7F1D1D",      # Red dark hover
    "red_text": "#D32F2F",            # Red text (softer)
    "red_text_light": "#FFCCCC",      # Red light text
    "red_bg": "#FEE2E2",              # Red light bg
    "red_border": "#FECACA",          # Red light border
    "red_bg_alt": "#FEF2F2",          # Red very light bg
    "red_dark_bg": "#450A0A",         # Red dark bg
    "red_very_light": "#FFEBEE",      # Red very light bg
    "red_dark": "#B71C1C",            # Red dark (softer)
    "red_dark_bg_alt": "#5c1e1e",     # Fail bg dark
    "red_text_dark": "#991B1B",       # Red dark text

    # === ORANGE / WARNING ===
    "orange": "#D97706",              # Orange accent
    "orange_light": "#FBBF24",        # Orange light accent
    "orange_hover": "#B45309",        # Orange hover
    "orange_dark_hover": "#92400E",   # Orange dark hover
    "orange_expires": "#DD6B20",      # Orange expires-soon
    "orange_warning": "#C05621",      # Orange warning
    "orange_accent": "#F97316",       # Orange accent
    "orange_accent_light": "#FB923C", # Orange light accent
    "orange_border": "#FED7AA",       # Orange light border
    "orange_bg": "#FFF7ED",           # Orange very light bg
    "orange_dark_bg": "#431407",      # Orange dark bg
    "orange_pending": "#FFA500",      # Orange pending approval
    "orange_file": "#f59e0b",         # Yellow-orange file status
    "orange_report": "#D35400",       # Orange report button
    "orange_report_hover": "#E67E22", # Orange report hover
    "oranges": "#EA580C",             # Orange shade

    # === YELLOW / GOLD ===
    "yellow": "#EAB308",              # Yellow accent
    "yellow_light": "#FACC15",        # Yellow light accent
    "yellow_border": "#FDE68A",        # Yellow light border
    "yellow_bg": "#FEFCE8",           # Yellow very light bg
    "yellow_dark_bg": "#422006",       # Yellow dark bg
    "yellow_skip_bg": "#fef9c3",      # Skip bg light
    "yellow_skip_fg": "#854d0e",      # Skip fg
    "yellow_skip_bg_dark": "#5c4e1e",  # Skip bg dark
    "gold": "#FFD700",                # Gold
    "gold4": "gold4",                 # Gold named color
    "dark_goldenrod": "#B8860B",      # Dark goldenrod

    # === PURPLE ===
    "purple": "#7C3AED",              # Purple
    "purple_light": "#A78BFA",        # Purple light accent
    "purple_accent": "#8B5CF6",       # Purple accent
    "purple_border": "#DDD6FE",       # Purple light border
    "purple_bg": "#F5F3FF",           # Purple very light bg
    "purple_dark_bg": "#2E1065",      # Purple dark bg
    "purple_report": "#8E24AA",       # Purple report button
    "purple_report_hover": "#7B1FA2", # Purple report hover

    # === TEAL / CYAN ===
    "teal": "#0EA5E9",                # Cyan accent
    "teal_light": "#38BDF8",          # Cyan light accent
    "teal_dark": "#0284C7",           # Cyan dark
    "teal_border": "#BAE6FD",         # Cyan light border
    "teal_bg": "#F0F9FF",             # Cyan very light bg
    "teal_dark_bg": "#0C4A6E",        # Cyan dark bg
    "teal_named": "teal",             # Tkinter named teal
    "teal_hover": "#00695C",          # Teal hover
    "teal_green_hover": "#1A994C",    # Green hover (Firefox)

    # === NEUTRAL GRAYS ===
    "gray10": "gray10",               # Tkinter named gray
    "gray30": "gray30",
    "gray50": "gray50",
    "gray60": "gray60",
    "gray70": "gray70",
    "gray75": "gray75",
    "gray80": "gray80",
    "gray85": "gray85",
    "gray90": "gray90",
    "gray95": "gray95",
    "gray20": "gray20",
    "gray25": "gray25",
    "gray30_tk": "gray30",
    "gray35": "gray35",
    "gray40": "gray40",

    # === TREEVIEW ===
    "tv_bg_dark": "#2b2b2b",
    "tv_fg_dark": "#e5e7eb",
    "tv_hover_dark": "#3f3f46",
    "tv_sel": "#3B82F6",
    "tv_header_bg_dark": "#1f2937",
    "tv_header_fg_dark": "#ffffff",
    "tv_header_hover_dark": "#374151",
    "tv_bg_light": "#ffffff",
    "tv_fg_light": "#374151",
    "tv_hover_light": "#f3f4f6",
    "tv_header_bg_light": "#f9fafb",
    "tv_header_fg_light": "#111827",
    "tv_header_hover_light": "#e5e7eb",

    # === CATEGORY COLORS (Home Tab + Sidebar) ===
    # Format: (light_bg, dark_bg), (light_border, dark_border), (light_accent, dark_accent)
    "cat_mr_wage": {
        "bg": ("#EFF6FF", "#1E3A5F"),
        "border": ("#BFDBFE", "#3B82F6"),
        "accent": ("#3B82F6", "#60A5FA"),
    },
    "cat_je_ae": {
        "bg": ("#F0FDF4", "#14532D"),
        "border": ("#BBF7D0", "#22C55E"),
        "accent": ("#16A34A", "#4ADE80"),
    },
    "cat_schemes": {
        "bg": ("#FFF7ED", "#431407"),
        "border": ("#FED7AA", "#F97316"),
        "accent": ("#EA580C", "#FB923C"),
    },
    "cat_verify": {
        "bg": ("#F5F3FF", "#2E1065"),
        "border": ("#DDD6FE", "#8B5CF6"),
        "accent": ("#7C3AED", "#A78BFA"),
    },
    "cat_reports": {
        "bg": ("#FEF2F2", "#450A0A"),
        "border": ("#FECACA", "#EF4444"),
        "accent": ("#DC2626", "#F87171"),
    },
    "cat_tools": {
        "bg": ("#FEFCE8", "#422006"),
        "border": ("#FDE68A", "#EAB308"),
        "accent": ("#CA8A04", "#FACC15"),
    },
    "cat_about": {
        "bg": ("#F0F9FF", "#0C4A6E"),
        "border": ("#BAE6FD", "#0EA5E9"),
        "accent": ("#0284C7", "#38BDF8"),
    },

    # === LOG TAG COLORS ===
    "log_success": ("#16A34A", "#4ADE80"),
    "log_warning": ("#D97706", "#FBBF24"),
    "log_error": ("#DC2626", "#F87171"),

    # === BUTTON COLORS ===
    "btn_start": "#2E8B57",
    "btn_start_hover": "#1F5E39",
    "btn_stop": "#C53030",
    "btn_stop_hover": "#9B2C2C",
    "btn_retry": "#D97706",
    "btn_retry_hover": "#B45309",
    "btn_reset_light": ("gray70", "#4A4A4A"),
    "btn_reset_hover_light": ("gray60", "#3A3A3A"),

    # === NAV BUTTON COLORS ===
    "nav_active_bg": ("#E3F2FD", "#374151"),
    "nav_active_text": ("#1565C0", "#60A5FA"),
    "nav_inactive_text": ("gray30", "gray80"),

    # === FOOTER STATUS COLORS ===
    "status_ready": ("#3B82F6", "#60A5FA"),
    "status_error_light": ("orange", "#D97706"),
    "status_error_dark": ("red", "#991B1B"),

    # === HEADER / CONTROLS COLORS ===
    "header_ctrl_bg": ("gray95", "gray25"),
    "header_ctrl_hover": ("gray85", "gray35"),
    "header_separator": ("gray90", "gray30"),
    "header_browser_bg": "transparent",
    "header_browser_hover": ("gray90", "gray30"),

    # === DROPDOWN / COMBOBOX COLORS ===
    "dd_fg": ("#F3F4F6", "#333333"),
    "dd_button": ("#E5E7EB", "#4B5563"),
    "dd_button_hover": ("#D1D5DB", "#6B7280"),
    "dd_text": ("#374151", "#D1D5DB"),
    "dd_dropdown_fg": ("#FFFFFF", "#2B2B2B"),
    "dd_dropdown_text": ("#374151", "#D1D5DB"),
    "dd_dropdown_hover": ("#F3F4F6", "#374151"),

    # === SKELETON COLORS ===
    "skel_light": "#E0E0E0",
    "skel_dark_1": "#2D3748",
    "skel_dark_2": "#4A5568",
    "skel_light_alt": "#EEEEEE",

    # === ANNOUNCEMENT / BADGE ===
    "badge_success": ("#2563EB", "#60A5FA"),
    "badge_info": ("#059669", "#34D399"),
    "badge_warning": ("#D97706", "#FBBF24"),
    "badge_error": ("#C53030", "#F87171"),

    # === SCROLLBAR === 
    "scrollbar_light": "#E0E0E0",
    "scrollbar_dark": "#333333",

    "blue_loader_tag": "#1F6AA5",
    "gray40_": "#4A4A4A",
    "gray35_": "#3A3A3A",

    # === MISC / ONE-OFF ===
    "orange_abps": "#B45309",
    "orange_abps_hover": "#92400E",
    "blue_btn": "#3B82F6",
    "blue_btn_hover": "#2563EB",
    "blue_border_card": "#3B82F6",
    "green_export_btn": "#107C10",
    "green_del_app_count": "#10B981",
    "red_error_status": "#EF4444",
    "red_about_border": "#E53E3E",
    "orange_about_border": "#DD6B20",
    "blue_link_text": ("#3B82F6", "#60A5FA"),
    "blue_link_dark": ("#2563EB", "#60A5FA"),
    "blue_info": "#2B6CB0",
    "blue_link_about": ("#3B82F6", "#60A5FA"),
    "whatsapp_green": "#25D366",
    "gray_555": "#555555",
    "gray_4B5563": "#4B5563",
    "gray_2D2D2D": "#2D2D2D",
    "gray_444": "#444444",
    "gray_btn_bg": "gray50",
    "gray_btn_hover": "gray60",
    "gray_btn_border": ("gray10", "#DCE4EE"),
    "gray_btn_reset_light": ("gray70", "#4A4A4A"),
    "gray_btn_reset_hover": ("gray60", "#3A3A3A"),
    "chat_bubble_user": ("#d1e7ff", "#2a3b4d"),
    "chat_bubble_admin": ("#e2e3e5", "#373739"),
    "gray_card_bg": ("gray90", "gray20"),
    "fw_label_color": ("#2563EB", "#60A5FA"),
    "profile_btn_border": ("gray10", "#DCE4EE"),

    # === ABOUT TAB COLORS ===
    "about_active": "#38A169",
    "about_expired": "#E53E3E",
    "about_expires_soon": "#DD6B20",
    "about_gold_name": ("gold4", "#FFD700"),

    # === DEVICE / ACTIVATION COLORS ===
    "device_frame_bg": ("gray90", "gray30"),
    "device_entry_bg": ("gray85", "gray20"),
    "device_btn_bg": "transparent",
    "device_btn_hover": ("gray75", "gray25"),
    "device_pending_text": ("orange", "#FFA500"),
}

# --- Centralized Style and Icon Configuration fix---
ICONS: Dict[str, object] = {
    # MR & Wage Management
    "Demand": "📝", "Work Allocation": "📋", "Muster Roll Gen": "📄",
    "Mate/Mistri MR": "👥", "MR Fill": "✍️", "MR Payment": "💳",
    "Gen Wagelist": "📋", "Send Wagelist": "➡️", "FTO Generation": "📤",
    "Duplicate MR Print": "📠", "Material Entry": "🧱",
    # JE & AE Approval
    "eMB Entry": "✏️", "eMB Verify": "🔍",
    # Schemes Related
    "Work Code Gen": "🏗️", "IF Editor": "🔧", "Update Estimate": "📊",
    "Physical Complete": "✅", "Scheme Closing": "🏁", "Add Activity": "🪄",
    # Verification & Utility
    "Job Card Verify": "✅", "Verify ABPS": "💳", "Del Work Alloc": "🗑️",
    "Delete Demand": "📝", "Delete Applicant": "🗑️", "Zero MR": "0️⃣",
    "Resend Rejected WG": "🔁", "Sarkar Aapke Dwar": "⛺", "SAD Update Status": "📊",
    # Reports & Tracking
    "MR Tracking": "🕵️", "Dashboard Report": "📈", "MIS Reports": "📊",
    "Issued MR Details": "📋", "eKYC Report": "🆔", "Social Audit Report": "📝",
    "NMMS Attendance": "📋", "Pending Bills": "💸",
    # Smart Tools
    "Macro Manager": "⚙️", "Login Automation": "🤖", "PDF Merger": "📑",
    "Workcode Extractor": "✂️", "File Manager": "📁",
    # About & Help
    "Feedback": "💬", "About": "ℹ️",
    # Theme
    "Theme": {"light": "🌙", "dark": "☀️"}
}

# --- Automation Configurations --- 
# Shared value for Panchayat prefix
AGENCY_PREFIX: str = "Gram Panchayat -"

# Dropdown label used when the user wants to process ALL panchayats of the block.
# Tabs that support this feature prepend it to their Panchayat dropdown options.
ALL_PANCHAYATS_LABEL: str = "🌐 All Panchayats"

MUSTER_ROLL_CONFIG: Dict[str, object] = {
    "base_url": "https://vbgramgde2.dord.gov.in/vbgramg/preprintmsr.aspx",
    "output_folder_name": "NREGABot_MR_Output",
    "pdf_options": {
        'landscape': True, 'displayHeaderFooter': False, 'printBackground': False,
        'preferCSSPageSize': False, 'paperWidth': 11.69, 'paperHeight': 8.27,
        'marginTop': 0.4, 'marginBottom': 0.4, 'marginLeft': 0.4, 'marginRight': 0.4,
        'scale': 0.8
    },
    "pdf_options_portrait": {
        'landscape': False, 'displayHeaderFooter': False, 'printBackground': False,
        'preferCSSPageSize': False, 'paperWidth': 8.27, 'paperHeight': 11.69,
        'marginTop': 0.4, 'marginBottom': 0.4, 'marginLeft': 0.4, 'marginRight': 0.4,
        'scale': 0.8
    }
}

# Mate/Mistri (Skilled/Semi-Skilled) MR generation uses the same base URL
# but selects the Skilled worker category checkbox and fills workers_per_mr.
MATE_MR_CONFIG: Dict[str, str] = {
    "base_url": "https://vbgramgde2.dord.gov.in/vbgramg/preprintmsr.aspx",
    "output_folder_name": "NREGABot_MateMR_Output",
}

MSR_CONFIG: Dict[str, object] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/msrpayment.aspx",
    "work_code_index": 1, "muster_roll_index": 1, "min_delay": 2, "max_delay": 6
}

WAGELIST_GEN_CONFIG: Dict[str, str] = {
    "base_url": 'https://vbgramgde2.dord.gov.in/vbgramg/SendMSRtoPO.aspx',
}

WAGELIST_SEND_CONFIG: Dict[str, object] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/sendforpay.aspx",
    "defaults": {
        "start_row": "3",
        "end_row": "19"
    }
}

MB_ENTRY_CONFIG: Dict[str, object] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/mbbook.aspx",
    "defaults": {
        "measurement_book_no": "", "page_no": "", "unit_cost": "300",
        "mate_name": "", "default_pit_count": "112", "je_name": "", "je_designation": "JE"
    }
}


IF_EDIT_CONFIG: Dict[str, object] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/IFEdit.aspx",
    "page1": {
        "estimated_pd": "0.090", "beneficiaries_count": "1",
        "convergence_scheme_type": "State", "convergence_scheme_name": "ABUA AWAS YOJNA"
    },
    "page2": {
        "sanction_no": "1-06/{year}", "sanction_date": "20/06/{year}", "est_time_completion": "1",
        "avg_labour_per_day": "10", "expected_mandays": "0.090", "tech_sanction_amount": "0.25380",
        "unskilled_labour_cost": "0.17266",
        "mgnrega_material_cost": "0.07235",
        "skilled_labour_cost": "0",
        "semi_skilled_labour_cost": "0",
        "scheme1_cost": "0",
        "fin_sanction_no": "01-06/{year}",
        "fin_sanction_date": "20/06/{year}", "fin_sanction_amount": "0.25380", "fin_scheme_input": "0"
    },
    "page3": {} # Page 3 now controlled by CSV
}

WC_GEN_CONFIG: Dict[str, object] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/work_entry.aspx",
    "defaults": {
        "master_category": "B", "work_category": "Construction of house", "beneficiary_type": "Individual",
        "activity_type": "Construction/Plantation/Development/Reclamation", "work_type": "Construction of PMAY /State House",
        "pro_status": "Constr of State scheme House for Individuals", "district_distance": "36", "financial_year": "2025-2026",
        "ridge_type": "L", "proposal_date": "15/06/{year}", "start_date": "15/06/{year}",
        "est_labour_cost": "0.25380", "est_material_cost": "0.0", "executing_agency": "3"
    }
}

FTO_GEN_CONFIG: Dict[str, str] = {
    "login_url": "https://vbgramgde2.dord.gov.in/vbgramg/FTO/Login.aspx?&level=HomeACGP&state_code=34",
    "aadhaar_fto_url": "https://vbgramgde2.dord.gov.in/vbgramg/FTO/ftoverify_aadhar.aspx",
    "top_up_fto_url": "https://vbgramgde2.dord.gov.in/vbgramg/FTO/ftoverify_aadhar.aspx?wg_topup=S",
    # --- NEW DELETION URLS ---
    # Note: Removed 'Digest' as it is session specific.
    "delete_url_1": "https://mnregaweb3.nic.in/netnrega/FTO/Fto_ds_po.aspx?cate=Z", 
    "delete_url_2": "https://mnregaweb3.nic.in/netnrega/FTO/Fto_ds_po.aspx"
}

JOBCARD_VERIFY_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/VerificationJCatPO.aspx",
    "default_photo": "assets/jobcard.jpeg"
}
# --- Add Activity Configuration ---
ADD_ACTIVITY_CONFIG: Dict[str, object] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/IAY_Act_Mat.aspx",
    "defaults": {
        "activity_code": "ACT105",
        "unit_price": "300",
        "quantity": "90"
    }
}
# --- ABPS Verification Configuration ---
ABPS_VERIFY_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/UID/VUID_NPCI.aspx"
}

DEL_WORK_ALLOC_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/delWrkAlloc.aspx"
}

# --- Update Estimate Configuration ---
UPDATE_ESTIMATE_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/Update_proposedstatus.aspx"
}

# --- ADD THIS NEW DICTIONARY ---
# Config for state-specific demand URLs and logic
STATE_DEMAND_CONFIG: Dict[str, Dict[str, str]] = {
    "Jharkhand": {
        "base_url": "https://vbgramgde2.dord.gov.in/vbgramg/demand_new.aspx",
        # Logic to parse village code from 'JH-01-001-001-001/123' -> '001'
        "village_code_logic": "jh"
    },
    "Rajasthan": {
        "base_url": "https://nregade2.dord.gov.in/netnrega/demand_new.aspx",
        # Logic to parse village code from 'RJ-270200209000394400/00022652' -> '400'
        "village_code_logic": "rj"
    },
    "Karnataka": {
        "base_url": "https://vbgramgde2.dord.gov.in/vbgramg/demand_new.aspx",
        "village_code_logic": "ka"
    }
    # Add more states here
    # You can add more states here
}


# --- Duplicate MR Print Configuration ---
DUPLICATE_MR_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/reprintmsr.aspx"
}

# --- NEW: eMB Verify Configuration ---
EMB_VERIFY_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/mbookverify.aspx"
}
REJECTED_WL_CONFIG: Dict[str, str] = {
    "RESEND_REJECTED_WG": "https://vbgramgde2.dord.gov.in/vbgramg/view_wagelist_rejected.aspx"
}

# --- MR Tracking Configuration  ---
MR_TRACKING_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgrep.dord.gov.in/VBGRAMG/dynamic_muster_track.aspx?lflag=eng&state_code=34&fin_year=2026-2027&state_name=JHARKHAND&Digest=J5TMmiE35cAOwcsR6vvJIA"
}

# --- NMMS Daily Attendance Configuration ---
NMMS_ATTENDANCE_CONFIG: Dict[str, str] = {
    "base_url": "https://vbgramgrep.dord.gov.in/vbgramg/NMMS_DailyAttendance.aspx"
}

# --- MIS Reports Configuration ---
MIS_REPORTS_CONFIG: Dict[str, str] = {
    "base_url": "https://vbgramgrep.dord.gov.in/VBGRAMG/MISreport.aspx"
}

# --- NEW: MR Fill (Attendance) Configuration ---
MR_FILL_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/mustrollattend.aspx"
}

# --- NEW: Zero MR Configuration ---
ZERO_MR_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/musteraszero.aspx"
}

# ---NEW: Work Allocation Configuration ---
WORK_ALLOCATION_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/workalloc.aspx"
}

DEL_DEMAND_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/deletedemand.aspx"
}

# --- Pending Bills (Unpaid MR/Bill) Scraper Configuration ---
# This automation scrapes the public "Liability & Expenditure Report" (Pending Bills)
# page from the MGNREGA website and prepares an Excel sheet of unpaid muster rolls
# and bills for the selected district → block → panchayat.
#
# The MGNREGA liability report pages require a per-query "Digest" parameter (they
# reject URL tampering). Digests are embedded in the links of every report page, so
# the automation only needs ONE valid *seed* digest for the state page (page=S) of
# the seed financial year — all deeper digests (district → block → panchayat) are
# read from the page links at runtime, and other financial years are reached through
# the ASP.NET financial-year dropdown postback.
#
# seed_digest: a valid Digest for page=S of seed_fin_year. If the site regenerates
#              digests and scraping starts failing with "URL TEMPERED", refresh this
#              value by opening the liability report in a browser and copying the
#              Digest from the address bar.
#
# To add another state: add an entry with its state_code, the liability report URL,
# the state_out data base URL and a fresh seed digest.
PENDING_BILLS_CONFIG: Dict[str, Dict[str, str]] = {
    "JHARKHAND": {
        "state_code": "34",
        "report_url": "https://mnregaweb2.dord.gov.in/netnrega/liability_exp_report.aspx",
        "data_base_url": "https://mnregaweb2.dord.gov.in/Netnrega/writereaddata/state_out/",
        "seed_fin_year": "2026-2027",
        "seed_digest": "9OGth4UYNHlos5R4NI/k3A",
    },
    # Add more states here, e.g.:
    # "BIHAR": {"state_code": "10", "report_url": "...", "data_base_url": "...",
    #           "seed_fin_year": "2026-2027", "seed_digest": "..."},
}

MATERIAL_ENTRY_CONFIG: Dict[str, str] = {
    # Replace with the exact base url used for material entry from your PO login
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/billdetail.aspx" 
}

# --- Delete Applicant Configuration ---
DELETE_APPLICANT_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/DelApp.aspx"
}

# --- Delete Registration Configuration ---
DEL_REG_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/DelReg.aspx"
}

# --- eKYC Report Configuration ---
EKYC_REPORT_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/UID/AppABPSRpt.aspx"
}

# --- Physical Complete Configuration ---
PHYSICAL_COMPLETE_CONFIG: Dict[str, str] = {
    "url": "https://vbgramgde2.dord.gov.in/vbgramg/phycomp_work.aspx"
}

# ============================================================================
# P1.3: Config Value Cache — avoids repeated dict lookups and color string
# parsing for frequently-accessed values. The cache is populated lazily.
# ============================================================================

import json
from typing import Any, Optional
from src.utils import get_data_path

class _ConfigCache:
    """
    Lightweight cache for frequently-accessed config values.
    
    - get(key): returns cached value or computes from COLORS dict
    - clear(): resets cache (used on theme change)
    
    Usage::
        COLORS.cache.get("blue")  # 1st call: dict lookup; 2nd+: cache hit
    """
    def __init__(self, colors_dict):
        self._colors = colors_dict
        self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._cache:
            return self._cache[key]
        val = self._colors.get(key, default)
        self._cache[key] = val
        return val

    def clear(self) -> None:
        self._cache.clear()


# Create a module-level cache so it can be accessed via config.COLORS_CACHE.get("key")
# NOTE: We cannot set COLORS.cache = ... because Python dict instances don't
# support arbitrary attribute assignment (AttributeError). Instead, a separate
# COLORS_CACHE variable is used.
COLORS_CACHE = _ConfigCache(COLORS)


def create_default_config_if_not_exists() -> None:
    """
    Creates a default config.json in the app data directory if it doesn't exist.
    """
    config_file_path = get_data_path('config.json')

    if not os.path.exists(config_file_path):
        # Define the default settings that should be in the config.json
        DEFAULT_USER_CONFIG: Dict[str, object] = {
            "theme": "System",
            "last_used_browser": "chrome",
            "onboarding_complete": False
        }
        try:
            with open(config_file_path, 'w') as f:
                json.dump(DEFAULT_USER_CONFIG, f, indent=4)
        except IOError as e:
            print(f"Error creating default config file: {e}")
