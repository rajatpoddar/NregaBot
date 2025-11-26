# config.py
# This file contains centralized configuration settings for the NREGA Bot.

# --- Application & Brand Info ---
APP_NAME = "NREGA Bot"
APP_SHORT_NAME = "NREGA Bot"
APP_TAGLINE = "Your NREGA Task Management Companion"
APP_DESCRIPTION = "A comprehensive tool for managing NREGA tasks efficiently."
APP_AUTHOR = "Rajat Poddar"
APP_AUTHOR_EMAIL = "Rajatpoddar@outlook.com"
APP_VERSION = "2.8.3"
LICENSE_SERVER_URL = "https://license.nregabot.com"
MAIN_WEBSITE_URL = "https://nregabot.com"
SUPPORT_EMAIL = "nregabot@gmail.com"

# --- Platform & UI Configuration ---
import platform
OS_SYSTEM = platform.system()

# --- Centralized Style and Icon Configuration fix---
ICONS = {
    "MR Gen": "📄", "MR Payment": "💳", "FTO Generation": "📤",
    "Gen Wagelist": "📋", "Send Wagelist": "➡️", "Verify Jobcard": "✅",
    "eMB Entry": "✏️", "eMB Verify": "🔍", "WC Gen (Abua)": "🏗️", "IF Editor (Abua)": "🔧",
    "Add Activity": "🪄","Verify ABPS": "💳",  "Workcode Extractor": "✂️", "Scheme Closing": "🏁",
    "Update Outcome": "📊", "Duplicate MR Print": "📠", "Feedback": "💬","File Manager": "📁", "Resend Rejected WG": "🔁", "Demand": "📝", "Sarkar Aapke Dwar": "⛺",# <-- ADD THIS LINE
    "About": "ℹ️", "Theme": {"light": "🌙", "dark": "☀️"}
}

# --- Automation Configurations --- 
# Shared value for Panchayat prefix
AGENCY_PREFIX = "Gram Panchayat -"

MUSTER_ROLL_CONFIG = {
    "base_url": "https://nregade4.nic.in/Netnrega/preprintmsr.aspx",
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

MSR_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/msrpayment.aspx",
    "work_code_index": 1, "muster_roll_index": 1, "min_delay": 2, "max_delay": 6
}

WAGELIST_GEN_CONFIG = {
    "base_url": 'https://nregade4.nic.in/Netnrega/SendMSRtoPO.aspx',
}

WAGELIST_SEND_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/sendforpay.aspx",
    "defaults": {
        "start_row": "3",
        "end_row": "19"
    }
}

MB_ENTRY_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/mbbook.aspx",
    "defaults": {
        "measurement_book_no": "", "page_no": "", "unit_cost": "282",
        "mate_name": "", "default_pit_count": "112", "je_name": "", "je_designation": "JE"
    }
}


IF_EDIT_CONFIG = {
    "url": "https://nregade4.nic.in/netnrega/IFEdit.aspx",
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

WC_GEN_CONFIG = {
    "url": "https://mnregaweb2.nic.in/netnrega/work_entry.aspx",
    "defaults": {
        "master_category": "B", "work_category": "Construction of house", "beneficiary_type": "Individual",
        "activity_type": "Construction/Plantation/Development/Reclamation", "work_type": "Construction of PMAY /State House",
        "pro_status": "Constr of State scheme House for Individuals", "district_distance": "36", "financial_year": "2025-2026",
        "ridge_type": "L", "proposal_date": "15/06/{year}", "start_date": "15/06/{year}",
        "est_labour_cost": "0.25380", "est_material_cost": "0.0", "executing_agency": "3"
    }
}

FTO_GEN_CONFIG = {
    "login_url": "https://mnregaweb3.nic.in/Netnrega/FTO/Login.aspx?&level=HomeACGP&state_code=34",
    "aadhaar_fto_url": "https://mnregaweb3.nic.in/netnrega/FTO/ftoverify_aadhar.aspx",
    "top_up_fto_url": "https://mnregaweb3.nic.in/netnrega/FTO/ftoverify_aadhar.aspx?wg_topup=S"
}

JOBCARD_VERIFY_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/VerificationJCatPO.aspx",
    "default_photo": "jobcard.jpeg"
}
# --- Add Activity Configuration ---
ADD_ACTIVITY_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/IAY_Act_Mat.aspx",
    "defaults": {
        "activity_code": "ACT105",
        "unit_price": "282",
        "quantity": "90"
    }
}
# --- ABPS Verification Configuration ---
ABPS_VERIFY_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/UID/VUID_NPCI.aspx"
}

DEL_WORK_ALLOC_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/delWrkAlloc.aspx"
}

# --- Update Estimate Configuration ---
UPDATE_ESTIMATE_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/Update_proposedstatus.aspx"
}

# --- ADD THIS NEW DICTIONARY ---
# Config for state-specific demand URLs and logic
STATE_DEMAND_CONFIG = {
    "Jharkhand": {
        "base_url": "https://nregade4.nic.in/netnrega/demand_new.aspx",
        # Logic to parse village code from 'JH-01-001-001-001/123' -> '001'
        "village_code_logic": "jh"
    },
    "Rajasthan": {
        "base_url": "https://nregade2.nic.in/netnrega/demand_new.aspx",
        # Logic to parse village code from 'RJ-270200209000394400/00022652' -> '400'
        "village_code_logic": "rj"
    }
    # You can add more states here
}


# --- Duplicate MR Print Configuration ---
DUPLICATE_MR_CONFIG = {
    "url": "https://nregade4.nic.in/netnrega/reprintmsr.aspx"
}

# --- NEW: eMB Verify Configuration ---
EMB_VERIFY_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/mbookverify.aspx"
}
REJECTED_WL_CONFIG = {
    "RESEND_REJECTED_WG": "https://nregade4.nic.in/Netnrega/view_wagelist_rejected.aspx"
}

# --- MR Tracking Configuration  ---
MR_TRACKING_CONFIG = {
    "url": "https://nregastrep.nic.in/netnrega/dynamic_muster_track.aspx?lflag=eng&state_code=34&fin_year=2025-2026&state_name=JHARKHAND&Digest=FjAL4jfLQiHS1NU1KnbRZg"
}

# --- MIS Reports Configuration ---
MIS_REPORTS_CONFIG = {
    "base_url": "https://nreganarep.nic.in/netnrega/MISreport4.aspx"
}

# --- NEW: MR Fill (Attendance) Configuration ---
MR_FILL_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/mustrollattend.aspx"
}

# --- NEW: Zero MR Configuration ---
ZERO_MR_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/musteraszero.aspx"
}

# ---NEW: Work Allocation Configuration ---
WORK_ALLOCATION_CONFIG = {
    "url": "https://nregade4.nic.in/Netnrega/workalloc.aspx"
}

import os
import json
from utils import get_data_path

def create_default_config_if_not_exists():
    """
    Creates a default config.json in the app data directory if it doesn't exist.
    """
    config_file_path = get_data_path('config.json')

    if not os.path.exists(config_file_path):
        # Define the default settings that should be in the config.json
        DEFAULT_USER_CONFIG = {
            "theme": "System",
            "last_used_browser": "chrome",
            "onboarding_complete": False
        }
        try:
            with open(config_file_path, 'w') as f:
                json.dump(DEFAULT_USER_CONFIG, f, indent=4)
        except IOError as e:
            print(f"Error creating default config file: {e}")