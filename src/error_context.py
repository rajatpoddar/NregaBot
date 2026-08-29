"""
src/error_context.py

Pure helper for extracting structured diagnostics from an uncaught automation
exception. Extracted from ``src/app/app_automation.py`` (which previously
imported tkinter, customtkinter, requests, subprocess, socket, json) so that
this function can be unit-tested without pulling in the heavy GUI /
networking dependencies of the mixin module.

Public API:
    _extract_error_context(e: Exception) -> Tuple[str, str, str, str]

Dependencies (all stdlib or already-present in src/utils.py):
    * os.path.basename  (stdlib)
    * traceback         (stdlib, imported locally inside the function)
    * src.utils.mask_pii_text  (already imported as a local fallback)
    * src.utils.mask_aadhaar_text  (transitively via mask_pii_text)

No circular-import risk:
    * src/utils.py imports only stdlib + ``appdirs`` — verified at
      src/utils.py:1-13. It does NOT import src/app/*.

Behavior contract (preserved verbatim from app_automation.py:86-137):
    * ``error_msg``     — ``f"{error_type}: {str(e)}"`` PII-masked, [:600].
    * ``error_source``  — chain of the last 2 user-code frames (skipping
                          ``site-packages`` and ``<...>`` frames),
                          formatted as ``"file.py:line:fn -> file.py:line:fn"``.
    * ``error_traceback`` — full traceback text PII-masked, [:4000].
"""

import os
from typing import Tuple


def _extract_error_context(e: Exception) -> Tuple[str, str, str, str]:
    """
    Extract structured diagnostics from an uncaught automation exception.

    Returns (error_type, error_message, error_source, error_traceback):
      - error_type:      exception class name, e.g. 'StaleElementReferenceException'
      - error_message:   'Type: message' (capped at 600 chars for DB)
      - error_source:    'file:line:function' chain (last 2 user-code frames)
                         — admin Error Logs me exactly pata chalta hai ki
                         automation ke kis function se error aaya.
      - error_traceback: full traceback text (capped at 4000 chars) — admin
                         ko poora stack milta hai (kaunsa frame kis line se
                         call hua), sirf summary chain nahi.
    """
    error_type = type(e).__name__
    # ── DPDP: exception message me Aadhaar/account/mobile numbers leak ho
    #    sakte hain (e.g. "element with value 123412341234 not found") —
    #    log/store hone se pehle PII mask karo.
    try:
        from src.utils import mask_pii_text
        error_msg = mask_pii_text(f"{error_type}: {str(e)}")[:600]
    except Exception:
        error_msg = f"{error_type}: {str(e)}"[:600]
    error_source = ""
    error_traceback = ""
    try:
        import traceback
        frames = traceback.extract_tb(e.__traceback__)
        # Skip framework internals (selenium/site-packages) — keep the last 2
        # user-code frames so the chain reads like 'demand_tab.py:1234:_process_village'.
        user_frames = [f for f in frames
                       if 'site-packages' not in f.filename
                       and not f.filename.startswith('<')]
        if not user_frames:
            user_frames = frames
        parts = [f"{os.path.basename(f.filename)}:{f.lineno}:{f.name}"
                 for f in user_frames[-2:]]
        error_source = " -> ".join(parts)
        # Full stack — formatting karte time exception bhi append hota hai.
        # Traceback me bhi PII values ho sakti hain (locals/args) — mask karo.
        try:
            from src.utils import mask_pii_text as _m
            error_traceback = _m(''.join(
                traceback.format_exception(type(e), e, e.__traceback__)
            ))[:4000]
        except Exception:
            error_traceback = ''.join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )[:4000]
    except Exception:
        pass
    return error_type, error_msg, error_source, error_traceback
