# src/i18n.py
"""
Lightweight i18n engine for NregaBot desktop app.

Usage:
    from src.i18n import tr, set_language, get_language, suggest_language_for_state

    label = ctk.CTkLabel(frame, text=tr("settings.title"))
    msg = tr("base.automation_complete.title")

Placeholders: tr("dialogs.extracted_count", count=len(results))

Fallback chain: selected language → English → key name (never crashes).
"""

import json
import os
from typing import Any, Dict, List, Optional

from src.utils import resource_path, get_config, save_config

# ── All 22 scheduled languages + English (framework ready) ─────────
LANGUAGES: Dict[str, str] = {
    "en": "English",
    "hi": "हिन्दी (Hindi)",
    "mr": "मराठी (Marathi)",
    "ta": "தமிழ் (Tamil)",
    "te": "తెలుగు (Telugu)",
    "kn": "ಕನ್ನಡ (Kannada)",
    "ml": "മലയാളം (Malayalam)",
    "bn": "বাংলা (Bengali)",
    "gu": "ગુજરાતી (Gujarati)",
    "pa": "ਪੰਜਾਬੀ (Punjabi)",
    "or": "ଓଡ଼ିଆ (Odia)",
    "as": "অসমীয়া (Assamese)",
    "ur": "اردو (Urdu)",
    "ne": "नेपाली (Nepali)",
    "sa": "संस्कृतम् (Sanskrit)",
    "ks": "कॉशुर (Kashmiri)",
    "sd": "سنڌي (Sindhi)",
    "doi": "डोगरी (Dogri)",
    "mai": "मैथिली (Maithili)",
    "sat": "ᱥᱟᱱᱛᱟᱲᱤ (Santali)",
    "mni": "মৈতৈলোন্ (Manipuri)",
    "bodo": "बर'/बड़ो (Bodo)",
}

# ── State → suggested language (auto-suggest in Settings) ─────────
STATE_LANGUAGE_MAP: Dict[str, str] = {
    "MAHARASHTRA": "mr",
    "TAMIL NADU": "ta",
    "TAMILNADU": "ta",
    "ANDHRA PRADESH": "te",
    "TELANGANA": "te",
    "KARNATAKA": "kn",
    "KERALA": "ml",
    "WEST BENGAL": "bn",
    "GUJARAT": "gu",
    "PUNJAB": "pa",
    "ODISHA": "or",
    "ORISSA": "or",
    "ASSAM": "as",
    "BIHAR": "hi",
    "UTTAR PRADESH": "hi",
    "MADHYA PRADESH": "hi",
    "RAJASTHAN": "hi",
    "HARYANA": "hi",
    "HIMACHAL PRADESH": "hi",
    "UTTARAKHAND": "hi",
    "JHARKHAND": "hi",
    "CHHATTISGARH": "hi",
    "DELHI": "hi",
    "GOA": "mr",
    "JAMMU AND KASHMIR": "ur",
    "LADAKH": "ur",
    "TRIPURA": "bn",
    "MANIPUR": "mni",
    "SIKKIM": "ne",
    "ARUNACHAL PRADESH": "hi",
    "MEGHALAYA": "en",
    "MIZORAM": "en",
    "NAGALAND": "en",
    "ANDAMAN AND NICOBAR ISLANDS": "hi",
    "CHANDIGARH": "hi",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "gu",
    "LAKSHADWEEP": "ml",
    "PUDUCHERRY": "ta",
}

CONFIG_KEY = "app_language"
DEFAULT_LANG = "en"

# Cache: lang_code -> {key: translated_string}
_TABLES: Dict[str, Dict[str, str]] = {}


def _locales_dir() -> str:
    """Path to locale JSON files (src/locales/)."""
    # Prefer path relative to this module (works in dev and when bundled with source)
    here = os.path.dirname(__file__)
    candidate = os.path.join(here, "locales")
    if os.path.isdir(candidate):
        return candidate
    # Fallback: resource_path (PyInstaller builds with --add-data)
    return os.path.join(resource_path("src"), "locales")


def _load_table(lang: str) -> Dict[str, str]:
    """Load a locale JSON into cache. Never raises — returns {} on failure."""
    if lang not in _TABLES:
        path = os.path.join(_locales_dir(), f"{lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _TABLES[lang] = data if isinstance(data, dict) else {}
        except Exception:
            _TABLES[lang] = {}
    return _TABLES[lang]


def get_language() -> str:
    """Return the current language code (e.g. 'en', 'hi')."""
    lang = get_config(CONFIG_KEY, DEFAULT_LANG) or DEFAULT_LANG
    if lang not in LANGUAGES:
        return DEFAULT_LANG
    return lang


def set_language(lang: str) -> None:
    """Save language preference to config.json."""
    if lang not in LANGUAGES:
        lang = DEFAULT_LANG
    save_config(CONFIG_KEY, lang)
    # Clear cached table so next tr() call reloads
    _TABLES.pop(lang, None)
    _TABLES.pop(DEFAULT_LANG, None)


def get_available_languages() -> List[str]:
    """Return language codes that have a locale file on disk."""
    try:
        d = _locales_dir()
        codes = []
        for f in os.listdir(d):
            if f.endswith(".json") and f[:-5] in LANGUAGES:
                codes.append(f[:-5])
        # English is always available (base)
        if "en" not in codes:
            codes.append("en")
        return sorted(set(codes))
    except Exception:
        return ["en"]


def tr(key: str, default: Optional[str] = None, **kwargs: Any) -> str:
    """Translate a UI string key for the current language.

    Fallback chain: current language → English → `default` (if given) → key name.
    Supports {placeholder} via keyword arguments.
    Never raises — returns key on total failure.

    `default` is the caller-provided English text shown when the key is
    missing from the locale files. This keeps dynamic UI (e.g. sidebar tab
    names) safe even before a translation is added.
    """
    lang = get_language()
    table = _load_table(lang)
    text = table.get(key)

    # Fallback to English
    if text is None and lang != DEFAULT_LANG:
        text = _load_table(DEFAULT_LANG).get(key)

    # Last-resort fallback: caller-provided default, else the key itself
    if text is None:
        text = default if default is not None else key

    # Format placeholders
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text

    return text


def suggest_language_for_state(state: str) -> str:
    """Return the suggested language code for a given state.

    Falls back to 'hi' (Hindi) for states whose language is not yet available.
    """
    s = (state or "").strip().upper()
    return STATE_LANGUAGE_MAP.get(s, "hi")
