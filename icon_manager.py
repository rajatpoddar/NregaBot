import customtkinter as ctk
from PIL import Image
from utils import resource_path

def load_icons():
    """
    Loads all application icons and returns a dictionary.
    """
    icons = {}
    
    def _add(name, path, size=(20, 20)):
        try:
            # Resource path se full path nikalo
            full_path = resource_path(path)
            # Image load karke CTkImage banao
            icons[name] = ctk.CTkImage(Image.open(full_path), size=size)
        except Exception as e:
            print(f"Warning: Could not load icon '{name}': {e}")

    # --- BROWSERS ---
    _add("chrome", "assets/icons/chrome.png")
    _add("edge", "assets/icons/edge.png")
    _add("firefox", "assets/icons/firefox.png")
    
    # --- APP BRANDING ---
    _add("nrega", "assets/icons/nrega.png")
    _add("whatsapp", "assets/icons/whatsapp.png")
    _add("feedback", "assets/icons/feedback.png")
    _add("history", "assets/icons/history.png")
    
    # --- TOOLS ---
    _add("extractor_icon", "assets/icons/extractor.png", size=(20, 20))
    _add("wc_extractor", "assets/icons/extractor.png") # Legacy key
    
    # --- SETTINGS TOGGLES ---
    _add("sound_on", "assets/icons/sound.png", size=(18, 18))
    _add("minimize", "assets/icons/minimize.png", size=(18, 18))
    
    # --- THEME ICONS ---
    _add("theme_system", "assets/icons/theme_auto.png", size=(18, 18))
    _add("theme_light", "assets/icons/theme_sun.png", size=(18, 18))
    _add("theme_dark", "assets/icons/theme_moon.png", size=(18, 18))

    # --- DEVICE MANAGER ---
    _add("device_edit", "assets/icons/edit.png", size=(20, 20))
    _add("device_reset", "assets/icons/reset.png", size=(20, 20))

    # --- ONBOARDING (Large Icons) ---
    _add("onboarding_launch", "assets/icons/emojis/thunder.png", size=(48, 48))
    _add("onboarding_login", "assets/icons/emojis/verify_jobcard.png", size=(48, 48))
    _add("onboarding_select", "assets/icons/emojis/wc_gen.png", size=(48, 48))
    _add("onboarding_start", "assets/icons/emojis/fto_gen.png", size=(48, 48))

    # --- DISCLAIMER ICONS ---
    _add("disclaimer_warning", "assets/icons/emojis/warning.png", size=(16, 16))
    _add("disclaimer_thunder", "assets/icons/emojis/thunder.png", size=(16, 16))
    _add("disclaimer_tools", "assets/icons/emojis/tools.png", size=(16, 16))

    # --- MENU ICONS (Small 16x16) ---
    # Core
    _add("emoji_mr_gen", "assets/icons/emojis/mr_gen.png", size=(16, 16))
    _add("emoji_mr_fill", "assets/icons/emojis/mr_fill.png", size=(16, 16))
    _add("emoji_mr_payment", "assets/icons/emojis/mr_payment.png", size=(16, 16))
    _add("emoji_gen_wagelist", "assets/icons/emojis/gen_wagelist.png", size=(16, 16))
    _add("emoji_send_wagelist", "assets/icons/emojis/send_wagelist.png", size=(16, 16))
    _add("emoji_fto_gen", "assets/icons/emojis/fto_gen.png", size=(16, 16))
    _add("emoji_scheme_closing", "assets/icons/emojis/scheme_closing.png", size=(16, 16))
    _add("emoji_del_work_alloc", "assets/icons/emojis/del_work_alloc.png", size=(16, 16))
    _add("emoji_duplicate_mr", "assets/icons/emojis/duplicate_mr.png", size=(16, 16))
    _add("emoji_demand", "assets/icons/emojis/demand.png", size=(16, 16))
    _add("emoji_work_alloc", "assets/icons/emojis/work_allocation.png", size=(16, 16))
    
    # JE/AE
    _add("emoji_emb_entry", "assets/icons/emojis/warning.png", size=(16, 16))
    _add("emoji_emb_verify", "assets/icons/emojis/emb_verify.png", size=(16, 16))
    
    # Records
    _add("emoji_wc_gen", "assets/icons/emojis/wc_gen.png", size=(16, 16))
    _add("emoji_if_editor", "assets/icons/emojis/if_editor.png", size=(16, 16))
    _add("emoji_add_activity", "assets/icons/emojis/add_activity.png", size=(16, 16))
    _add("emoji_update_outcome", "assets/icons/emojis/update_outcome.png", size=(16, 16))
    
    # Utilities
    _add("emoji_verify_jobcard", "assets/icons/emojis/verify_jobcard.png", size=(16, 16))
    _add("emoji_verify_abps", "assets/icons/emojis/verify_abps.png", size=(16, 16))
    _add("emoji_wc_extractor", "assets/icons/emojis/wc_extractor.png", size=(16, 16))
    _add("emoji_resend_wg", "assets/icons/emojis/resend_wg.png", size=(16, 16))
    _add("emoji_pdf_merger", "assets/icons/emojis/pdf_merger.png", size=(16, 16))
    _add("emoji_zero_mr", "assets/icons/emojis/zero_mr.png", size=(16, 16))
    _add("emoji_file_manager", "assets/icons/emojis/file_manager.png", size=(16, 16))
    
    # Reports
    _add("emoji_social_audit", "assets/icons/emojis/social_audit.png", size=(16, 16))
    _add("emoji_mis_reports", "assets/icons/emojis/mis_reports.png", size=(16, 16))
    _add("emoji_mr_tracking", "assets/icons/emojis/mr_tracking.png", size=(16, 16))
    _add("emoji_issued_mr_report", "assets/icons/emojis/issued_mr_report.png", size=(16, 16))
    _add("emoji_dashboard_report", "assets/icons/emojis/dashboard_report.png", size=(16, 16))
    
    # Others
    _add("emoji_sad_auto", "assets/icons/emojis/thunder.png", size=(16, 16))
    _add("emoji_sad_status", "assets/icons/emojis/sad_status.png", size=(16, 16))
    _add("emoji_login_automation", "assets/icons/emojis/login_automation.png", size=(16, 16))
    _add("emoji_feedback", "assets/icons/emojis/feedback.png", size=(16, 16))
    _add("emoji_about", "assets/icons/emojis/about.png", size=(16, 16))

    return icons