# lite_config.py
# Lite version configuration overrides for low-end devices.
#
# Usage: In lite_app.py, import this AFTER main config:
#   from src import config
#   from src import lite_config
#   lite_config.apply_overrides()
#
# This module overrides specific values in config.py to reduce
# memory usage, disable animations, and simplify UI.

from src import config


# --- Override dictionary with Lite-specific values ---
_LITE_OVERRIDES = {
    # Lite App Name
    "APP_NAME": "NREGA Bot (Lite)",
    "APP_SHORT_NAME": "NREGA Bot Lite",
    "APP_TAGLINE": "Lightweight NREGA Automation",

    # Disable features for performance
    "ENABLE_ANIMATIONS": False,
    "ENABLE_SOUNDS": False,
    "ENABLE_ONBOARDING": False,
    "ENABLE_PERFORMANCE_MONITOR": False,
    "ENABLE_MACROS": False,
    "ENABLE_FILE_MANAGER": False,
    "ENABLE_FEEDBACK": False,
    "ENABLE_AUTO_UPDATE_CHECK": False,

    # Simplified splash screen
    "ENABLE_SPLASH_ANIMATION": False,

    # Reduce splash display time (instant transition)
    "SPLASH_MIN_DISPLAY_MS": 100,

    # GC settings tuned for low-end
    "GC_THRESHOLD": (500, 5, 3),  # More aggressive collection
    "GC_INTERVAL_MS": 180000,  # Collect every 3 min instead of 5
}


def apply_overrides() -> None:
    """Apply Lite overrides to the config module's namespace."""
    for key, value in _LITE_OVERRIDES.items():
        setattr(config, key, value)

    # Override APP_VERSION to differentiate from full version
    if hasattr(config, 'APP_VERSION'):
        config.APP_VERSION = f"{config.APP_VERSION}-LITE"

    # Lite uses default window size (config values always exist)
    # Reduce from default 1100x800 to 950x700 for low-end displays
    config.INITIAL_WIDTH = getattr(config, 'INITIAL_WIDTH', 1100)
    config.INITIAL_HEIGHT = getattr(config, 'INITIAL_HEIGHT', 800)
    # These are set only for Lite - original config.py doesn't define them
    config.LITE_INITIAL_WIDTH = 950
    config.LITE_INITIAL_HEIGHT = 700
    config.LITE_MIN_WIDTH = 800
    config.LITE_MIN_HEIGHT = 550
