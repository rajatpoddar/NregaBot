import customtkinter as ctk
from PIL import Image
from typing import Any, Dict, List, Optional, Tuple
from src.utils import resource_path


class LazyIconManager:
    """
    Lazily loads icons only when first accessed via get().
    No images are decoded or stored in memory until first requested.
    Acts as a drop-in replacement for a dict of icons — supports .get().
    """
    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._definitions: List[Tuple[str, str, Tuple[int, int]]] = []  # (name, path, size) tuples — no loading yet

    def _add(self, name: str, path: str, size: Tuple[int, int] = (20, 20)) -> None:
        """Register an icon definition. Does NOT load the image."""
        self._definitions.append((name, path, size))

    def get(self, name: str, default: Any = None) -> Any:
        """Get an icon by name. Loads and caches it on first access."""
        # Return from cache if already loaded
        if name in self._cache:
            return self._cache[name]

        # Find the definition and load it
        for n, path, size in self._definitions:
            if n == name:
                try:
                    full_path = resource_path(path)
                    img = ctk.CTkImage(Image.open(full_path), size=size)
                    self._cache[name] = img
                    return img
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Icon load failed '{name}' from {path}: {e}")
                    self._cache[name] = default
                    return default
        return default

    def get_sized(self, name: str, size: Tuple[int, int], default: Any = None) -> Any:
        """Load an icon at a custom size (fresh decode, not the definition size).

        Unlike get(), this always re-decodes the image at the requested size
        instead of returning the cached definition-size icon. Used when the
        same icon needs a larger rendition (e.g. tab header cards at 20x20
        while the sidebar uses 16x16).
        """
        for n, path, _ in self._definitions:
            if n == name:
                try:
                    full_path = resource_path(path)
                    return ctk.CTkImage(Image.open(full_path), size=size)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Icon load failed '{name}' from {path}: {e}")
                    return default
        return default

    def clear_cache(self) -> None:
        """M2: Clear all cached CTkImage objects.
        
        Call this after a theme switch to force icons to be recreated with
        the new appearance mode. CTkImage objects internally cache a PhotoImage
        that is tied to the current theme — flushing the cache ensures fresh,
        correctly-themed images are loaded on next access.
        """
        self._cache.clear()

    def preload_essential(self) -> None:
        """Preload only the most critical icons (browser, toolbar, settings)."""
        essential: List[str] = [
            "chrome", "edge", "firefox", "extractor_icon", "emoji_login_automation",
            "sound_on", "minimize", "theme_system", "theme_light", "theme_dark",
            "history", "emoji_file_manager", "feedback", "nrega", "home_icon",
        ]
        for name in essential:
            self.get(name)


def create_icon_manager() -> LazyIconManager:
    """
    Factory: creates a LazyIconManager with all icon definitions registered.
    No images are decoded — just path/size tuples stored.
    """
    mgr = LazyIconManager()

    # --- BROWSERS ---
    mgr._add("chrome",  "assets/icons/chrome.png")
    mgr._add("edge",    "assets/icons/edge.png")
    mgr._add("firefox", "assets/icons/firefox.png")

    # --- APP BRANDING ---
    mgr._add("nrega",     "assets/icons/nrega.png")
    mgr._add("home_icon", "assets/icons/home.png", size=(18, 18))
    mgr._add("whatsapp",  "assets/icons/whatsapp.png")
    mgr._add("feedback",  "assets/icons/feedback.png")
    mgr._add("history",   "assets/icons/history.png")

    # --- TOOLS ---
    mgr._add("extractor_icon", "assets/icons/extractor.png", size=(20, 20))
    mgr._add("wc_extractor",   "assets/icons/extractor.png")      # legacy alias

    # --- SETTINGS TOGGLES ---
    mgr._add("sound_on",  "assets/icons/sound.png",   size=(18, 18))
    mgr._add("minimize",  "assets/icons/minimize.png", size=(18, 18))

    # --- THEME ---
    mgr._add("theme_system", "assets/icons/theme_auto.png", size=(18, 18))
    mgr._add("theme_light",  "assets/icons/theme_sun.png",  size=(18, 18))
    mgr._add("theme_dark",   "assets/icons/theme_moon.png", size=(18, 18))

    # --- DEVICE MANAGER ---
    mgr._add("device_edit",  "assets/icons/edit.png",  size=(20, 20))
    mgr._add("device_reset", "assets/icons/reset.png", size=(20, 20))

    # --- ONBOARDING (Large) ---
    mgr._add("onboarding_launch", "assets/icons/emojis/thunder.png",       size=(48, 48))
    mgr._add("onboarding_login",  "assets/icons/emojis/verify_jobcard.png",size=(48, 48))
    mgr._add("onboarding_select", "assets/icons/emojis/wc_gen.png",        size=(48, 48))
    mgr._add("onboarding_start",  "assets/icons/emojis/fto_gen.png",       size=(48, 48))

    # --- DISCLAIMER ---
    mgr._add("disclaimer_warning", "assets/icons/emojis/warning.png", size=(16, 16))
    mgr._add("disclaimer_thunder", "assets/icons/emojis/thunder.png", size=(16, 16))
    mgr._add("disclaimer_tools",   "assets/icons/emojis/tools.png",   size=(16, 16))

    # --- MENU ICONS (16×16) ---
    # 1. MR & Wage Management
    mgr._add("emoji_demand",           "assets/icons/emojis/demand.png",            size=(16, 16))
    mgr._add("emoji_work_allocation",  "assets/icons/emojis/work_allocation.png",   size=(16, 16))
    mgr._add("emoji_mr_gen",           "assets/icons/emojis/mr_gen.png",            size=(16, 16))
    mgr._add("emoji_mr_fill",          "assets/icons/emojis/mr_fill.png",           size=(16, 16))
    mgr._add("emoji_mr_payment",       "assets/icons/emojis/mr_payment.png",        size=(16, 16))
    mgr._add("emoji_gen_wagelist",     "assets/icons/emojis/gen_wagelist.png",      size=(16, 16))
    mgr._add("emoji_send_wagelist",    "assets/icons/emojis/send_wagelist.png",     size=(16, 16))
    mgr._add("emoji_fto_gen",          "assets/icons/emojis/fto_gen.png",           size=(16, 16))
    mgr._add("emoji_duplicate_mr",     "assets/icons/emojis/duplicate_mr.png",      size=(16, 16))
    mgr._add("emoji_material_entry",   "assets/icons/emojis/material_entry.png",    size=(16, 16))

    # 2. JE & AE Approval
    mgr._add("emoji_mb_entry",   "assets/icons/emojis/mb_entry.png",   size=(16, 16))
    mgr._add("emoji_emb_verify", "assets/icons/emojis/emb_verify.png", size=(16, 16))

    # 3. Schemes
    mgr._add("emoji_wc_gen",             "assets/icons/emojis/wc_gen.png",             size=(16, 16))
    mgr._add("emoji_if_editor",          "assets/icons/emojis/if_editor.png",           size=(16, 16))
    mgr._add("emoji_update_estimate",    "assets/icons/emojis/update_estimate.png",     size=(16, 16))
    mgr._add("emoji_physical_complete",  "assets/icons/emojis/physical_complete.png",   size=(16, 16))
    mgr._add("emoji_scheme_closing",     "assets/icons/emojis/scheme_closing.png",      size=(16, 16))
    mgr._add("emoji_add_activity",       "assets/icons/emojis/add_activity.png",        size=(16, 16))

    # 4. Verification & Utility
    mgr._add("emoji_verify_jobcard",  "assets/icons/emojis/verify_jobcard.png", size=(16, 16))
    mgr._add("emoji_verify_abps",     "assets/icons/emojis/verify_abps.png",     size=(16, 16))
    mgr._add("emoji_del_work_alloc",  "assets/icons/emojis/del_work_alloc.png",  size=(16, 16))
    mgr._add("emoji_del_demand",      "assets/icons/emojis/del_demand.png",      size=(16, 16))
    mgr._add("emoji_delete_applicant","assets/icons/emojis/del_applicant.png",    size=(16, 16))
    mgr._add("emoji_zero_mr",         "assets/icons/emojis/zero_mr.png",          size=(16, 16))
    mgr._add("emoji_resend_wg",       "assets/icons/emojis/resend_wg.png",        size=(16, 16))
    mgr._add("emoji_sad_status",      "assets/icons/emojis/sad_status.png",       size=(16, 16))
    mgr._add("emoji_update_outcome",  "assets/icons/emojis/update_outcome.png",   size=(16, 16))

    # 5. Reports & Tracking
    mgr._add("emoji_mr_tracking",       "assets/icons/emojis/mr_tracking.png",        size=(16, 16))
    mgr._add("emoji_dashboard_report",  "assets/icons/emojis/dashboard_report.png",   size=(16, 16))
    mgr._add("emoji_mis_reports",       "assets/icons/emojis/mis_reports.png",        size=(16, 16))
    mgr._add("emoji_issued_mr_report",  "assets/icons/emojis/issued_mr_report.png",   size=(16, 16))
    mgr._add("emoji_ekyc_report",       "assets/icons/emojis/ekyc_report.png",        size=(16, 16))
    mgr._add("emoji_social_audit",      "assets/icons/emojis/social_audit.png",       size=(16, 16))
    mgr._add("emoji_nmms_attendance",   "assets/icons/emojis/mis_reports.png",        size=(16, 16))
    mgr._add("emoji_pending_bills",      "assets/icons/emojis/demand.png",              size=(16, 16))

    # 6. Smart Tools
    mgr._add("emoji_tools",             "assets/icons/emojis/emoji_tools.png",        size=(16, 16))
    mgr._add("emoji_login_automation",  "assets/icons/emojis/login_automation.png",   size=(16, 16))
    mgr._add("emoji_pdf_merger",        "assets/icons/emojis/pdf_merger.png",         size=(16, 16))
    mgr._add("emoji_wc_extractor",      "assets/icons/emojis/wc_extractor.png",       size=(16, 16))
    mgr._add("emoji_file_manager",      "assets/icons/emojis/file_manager.png",       size=(16, 16))

    # 7. Other
    mgr._add("emoji_sad_auto",  "assets/icons/emojis/thunder.png",    size=(16, 16))
    mgr._add("emoji_feedback",  "assets/icons/emojis/feedback.png",   size=(16, 16))
    mgr._add("emoji_about",     "assets/icons/emojis/about.png",      size=(16, 16))

    # --- SETTINGS ICON ---
    mgr._add("settings", "assets/icons/settings.png", size=(20, 20))

    # --- CLOCK ICON (Home Tab Date/Time) ---
    mgr._add("emoji_clock", "assets/icons/emojis/clock.png", size=(16, 16))

    # --- SIDEBAR ---
    mgr._add("performance_thunder", "assets/icons/emojis/thunder.png", size=(14, 14))

    return mgr
