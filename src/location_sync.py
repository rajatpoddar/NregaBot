# location_sync.py
"""
Block-wise location data pool — server ke saath panchayat/village sharing.

Problem: kuch users ko portal par na PO (block) na GP (panchayat) login milta
hai — isliye "Add Panchayat & Village" scrape nahi ho paata aur dropdowns
khali rehte hain.

Solution: har user apne saved block data (panchayat → villages, jo
location_hierarchy.json me hai) ko server par sync karta hai; same block ke
doosre users wo data server se fetch karke turant use kar lete hain.

Design (usage_stats sync pattern — golden rule):
  - Background daemon thread me — UI kabhi block nahi
  - Server unreachable / error → silent skip, next cycle retry
  - Kabhi raise nahi karta

Data privacy: panchayat/village/block names public MGNREGA data hain (PII
nahi); server par sirf sha256(license_key) hash jata hai (source dedup ke
liye) — raw license key kabhi share nahi hota.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Server-side caps se match — oversize payloads client par hi filter karo
_MAX_PANCHAYATS_PER_SYNC = 500
_MAX_VILLAGES_PER_PANCHAYAT = 300

# Sync throttle — bar-bar same data upload na ho (server rate limit bhi save)
_MIN_SYNC_INTERVAL_SECONDS = 600  # 10 min
_last_sync_at = 0.0
_last_sync_lock = threading.Lock()


def _norm(name) -> str:
    """Name normalize: whitespace collapse + UPPER (hierarchy jaisa hi)."""
    return " ".join((name or "").split()).upper()


def get_user_location(app) -> tuple:
    """
    User ka active (state, district, block) nikaalo — history_manager ke
    saved location keys se; na mile to license se fallback.

    Returns (state, district, block) — empty strings allowed.
    """
    state = district = block = ""
    try:
        hm = app.history_manager
        state = (hm.get_suggestions("location_state") or [""])[0]
        district = (hm.get_suggestions("location_district") or [""])[0]
        block = (hm.get_suggestions("location_block") or [""])[0]
    except Exception:
        pass
    if not state or not district or not block:
        try:
            lic = getattr(app, "license_info", {}) or {}
            if not state:
                state = lic.get("user_state") or ""
            if not district:
                district = lic.get("user_district") or ""
            if not block:
                block = lic.get("user_block") or ""
        except Exception:
            pass
    return _norm(state), _norm(district), _norm(block)


def get_license_key(app) -> str:
    """App se license key (body me bhejne ke liye)."""
    try:
        lic = getattr(app, "license_info", {}) or {}
        return (lic.get("key") or "").strip()
    except Exception:
        return ""


def build_block_payload(state: str, district: str, block: str, app=None):
    """
    Hierarchy (location_hierarchy.json) se block ke panchayat → villages ka
    payload banao. Block ke panchayat nahi mile → None (sync skip).

    Panchayat naam hierarchy ke keys hain (UPPER); villages unke children.
    Hierarchy me block→panchayat relation missing ho (purana data) to saved
    suggestions (Settings > Location Data) se fallback karte hain — village
    list hierarchy se.
    """
    if not state or not district or not block:
        return None
    from src.location_hierarchy import get_hierarchy

    hier = get_hierarchy()
    try:
        panch_names = hier.get_children("Block", block, "Panchayat")
    except Exception:
        panch_names = []
    if not panch_names:
        try:
            hm = getattr(app, "history_manager", None)
            if hm is not None:
                panch_names = [p for p in hm.get_suggestions("location_panchayat") if p]
        except Exception:
            panch_names = []

    panchayats = []
    for p in panch_names[: _MAX_PANCHAYATS_PER_SYNC]:
        p = _norm(p)
        if not p:
            continue
        try:
            villages = hier.get_children("Panchayat", p, "Village")
        except Exception:
            villages = []
        panchayats.append({"name": p, "villages": villages[: _MAX_VILLAGES_PER_PANCHAYAT]})
    if not panchayats:
        return None
    return {
        "state": state,
        "district": district,
        "block": block,
        "panchayats": panchayats,
    }


def sync_block_to_server(app, license_key: str = "", force: bool = False) -> bool:
    """
    User ke block ka panchayat→village data server ko bhejo (background).

    Throttled: _MIN_SYNC_INTERVAL_SECONDS ke andar repeat call skip (force=True
    se bypass — e.g. scrape ke turant baad).
    """
    global _last_sync_at
    if not force:
        with _last_sync_lock:
            if time.time() - _last_sync_at < _MIN_SYNC_INTERVAL_SECONDS:
                return False
            _last_sync_at = time.time()

    if not license_key:
        license_key = get_license_key(app)
    if not license_key:
        return False

    state, district, block = get_user_location(app)
    payload = build_block_payload(state, district, block, app=app)
    if not payload:
        return False

    from src.config import LICENSE_SERVER_URL
    server_url = LICENSE_SERVER_URL
    if not server_url:
        return False

    def _do_sync():
        try:
            import requests as req_lib
            body = dict(payload)
            body["license_key"] = license_key
            resp = req_lib.post(
                f"{server_url}/api/location-data/sync",
                json=body,
                timeout=15,
            )
            if resp.status_code == 200:
                r = resp.json()
                logger.info("☁️ Location pool sync: +%s new / %s updated panchayat(s) "
                            "for block %s", r.get("added", 0), r.get("updated", 0), block)
            else:
                logger.debug("⚠️ Location pool sync: HTTP %s (%s)",
                             resp.status_code, resp.text[:200])
        except Exception as e:
            logger.debug("⚠️ Location pool sync failed (retry next cycle): %s", e)

    threading.Thread(target=_do_sync, daemon=True).start()
    return True


def fetch_block_from_server(license_key: str, state: str, district: str,
                            block: str, timeout: int = 10) -> list:
    """
    Server se same-block ka merged panchayat data fetch karo (BLOCKING — caller
    ko background thread me call karna chahiye).

    Returns: [{"name": ..., "villages": [...], "source_count": n}, ...] ya [].
    """
    if not license_key or not state or not district or not block:
        return []
    from src.config import LICENSE_SERVER_URL
    server_url = LICENSE_SERVER_URL
    if not server_url:
        return []
    try:
        import requests as req_lib
        resp = req_lib.get(
            f"{server_url}/api/location-data/get",
            params={
                "license_key": license_key,
                "state": state,
                "district": district,
                "block": block,
            },
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("panchayats") or []
        logger.debug("⚠️ Location pool fetch: HTTP %s (%s)",
                     resp.status_code, resp.text[:200])
    except Exception as e:
        logger.debug("⚠️ Location pool fetch failed: %s", e)
    return []


def apply_server_data(block: str, panchayats: list, app=None) -> tuple:
    """
    Server data ko local hierarchy + suggestions me merge karo (sirf missing —
    user ke local edits kabhi overwrite nahi hote).

    Returns: (panchayat_added, village_added)
    """
    if not panchayats:
        return (0, 0)
    from src.location_hierarchy import get_hierarchy

    hier = get_hierarchy()
    hm = None
    try:
        if app is not None:
            hm = app.history_manager
    except Exception:
        hm = None

    panch_added = vill_added = 0
    for p in panchayats:
        name = _norm(p.get("name") or "")
        if not name:
            continue
        # Panchayat pehle se hai? (hierarchy block relation ya suggestions me)
        already = False
        if block:
            try:
                already = name in hier.get_children("Block", block, "Panchayat")
            except Exception:
                already = False
        if not already and hm is not None:
            try:
                already = name in (hm.get_suggestions("location_panchayat") or [])
            except Exception:
                pass
        if not already:
            # Naya panchayat — block ke under + suggestions me add
            if block:
                try:
                    hier.add_child("Block", block, "Panchayat", name)
                except Exception:
                    pass
            try:
                if hm is not None:
                    hm.save_entry("location_panchayat", name)
            except Exception:
                pass
            panch_added += 1
        # Villages — sirf missing (hierarchy me)
        existing = set()
        try:
            existing = set(hier.get_children("Panchayat", name, "Village"))
        except Exception:
            pass
        for v in (p.get("villages") or []):
            vn = _norm(v)
            if not vn or vn in existing:
                continue
            try:
                hier.add_child("Panchayat", name, "Village", vn)
                if hm is not None:
                    hm.save_entry("location_village", vn)
                existing.add(vn)
                vill_added += 1
            except Exception:
                pass
    return (panch_added, vill_added)


def sync_current_location(app, force: bool = False) -> bool:
    """
    Convenience: app se license + location utha ke background sync start karo.

    Har panchayat add (scrape success, manual add, GP auto-add) ke baad call
    karo — throttled, silent, kabhi crash nahi.
    """
    try:
        return sync_block_to_server(app, license_key="", force=force)
    except Exception as e:
        logger.debug("sync_current_location error: %s", e)
        return False
