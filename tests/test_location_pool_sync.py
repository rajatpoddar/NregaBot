"""Scrape kiya hua panchayat data server pool tak pahunchta hai ya nahi.

Bug (user report, 10 Sep 2026): "add panchayat karta hoon par server pe 5 hi
panchayat dikhte hain."

`_scrape_success()` pool sync ko ek DAEMON thread me shuru karta tha aur agli
hi line par `_restart_application()` call karta tha — jo `restart_application()`
ke through `os._exit(0)` maarta hai. `os._exit` process ko turant khatam kar
deta hai, daemon threads ka intezaar kiye bina; to 15-second timeout wali HTTP
POST kabhi complete hi nahi hoti thi.

Fix: sync ka `blocking=True` mode, aur restart tabhi jab sync khatam ho jaye.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from src import location_sync


class FakeResp:
    def __init__(self, status=200):
        self.status_code = status
        self.text = "{}"

    def json(self):
        return {"added": 3, "updated": 0}


@pytest.fixture
def fake_requests(monkeypatch):
    """`requests` module ko intercept karo — koi asli network nahi."""
    calls = []

    class _Req:
        @staticmethod
        def post(url, json=None, timeout=None):
            calls.append({"url": url, "json": json, "timeout": timeout})
            return FakeResp()

    import sys
    monkeypatch.setitem(sys.modules, "requests", _Req)
    monkeypatch.setattr(location_sync, "_last_sync_at", 0.0, raising=False)
    return calls


@pytest.fixture
def app_with_block(monkeypatch):
    monkeypatch.setattr(location_sync, "get_user_location",
                        lambda app: ("JHARKHAND", "SIMDEGA", "THETHAITANGAR"))
    monkeypatch.setattr(location_sync, "build_block_payload",
                        lambda s, d, b, app=None: {
                            "state": s, "district": d, "block": b,
                            "panchayats": [{"name": "GP-A", "villages": ["V1"]}]})
    import src.config as cfg
    monkeypatch.setattr(cfg, "LICENSE_SERVER_URL", "https://example.invalid", raising=False)
    return SimpleNamespace(license_info={"key": "TEST-KEY"})


# ── blocking mode ──────────────────────────────────────────────────────────

def test_blocking_sync_posts_before_returning(fake_requests, app_with_block):
    """Return hone tak POST ho chuka hona chahiye — warna os._exit use kha jayega."""
    ok = location_sync.sync_block_to_server(app_with_block, force=True, blocking=True)

    assert ok is True
    assert len(fake_requests) == 1
    assert fake_requests[0]["url"].endswith("/api/location-data/sync")
    assert fake_requests[0]["json"]["block"] == "THETHAITANGAR"
    assert fake_requests[0]["json"]["license_key"] == "TEST-KEY"


def test_blocking_sync_survives_server_error(fake_requests, app_with_block, monkeypatch):
    import sys

    class _Boom:
        @staticmethod
        def post(*a, **k):
            raise RuntimeError("network down")

    monkeypatch.setitem(sys.modules, "requests", _Boom)
    # Raise nahi hona chahiye — caller (restart) ko rukna nahi chahiye
    location_sync.sync_block_to_server(app_with_block, force=True, blocking=True)


def test_non_blocking_still_uses_a_background_thread(app_with_block, monkeypatch):
    started = []

    class _FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target
        def start(self):
            started.append(self.target)

    monkeypatch.setattr(location_sync.threading, "Thread", _FakeThread)
    ok = location_sync.sync_block_to_server(app_with_block, force=True, blocking=False)
    assert ok is True
    assert len(started) == 1, "non-blocking mode background thread hi use kare"


def test_sync_current_location_passes_blocking_through(monkeypatch):
    seen = {}
    monkeypatch.setattr(location_sync, "sync_block_to_server",
                        lambda app, license_key="", force=False, blocking=False:
                            seen.update(force=force, blocking=blocking) or True)
    location_sync.sync_current_location(object(), force=True, blocking=True)
    assert seen == {"force": True, "blocking": True}


# ── _scrape_success ordering: restart sirf sync ke BAAD ────────────────────

@pytest.fixture
def scrape_tab(monkeypatch):
    from src.tabs import settings_tab

    events = []

    class FakeWidget:
        def configure(self, **kw):
            if "text" in kw:
                events.append(("status", kw["text"]))

    class Tab:
        _scrape_success = settings_tab.SettingsTab._scrape_success

        def __init__(self):
            self._scrape_status = FakeWidget()
            self._scrape_btn = FakeWidget()
            self.app = SimpleNamespace(after=lambda ms, cb, *a: cb(*a))

        def _refresh_loc_list(self):
            pass

        def after(self, ms, cb=None, *a):
            return None

        def winfo_toplevel(self):
            return None

        def _restart_application(self):
            events.append(("restart", None))

    monkeypatch.setattr(settings_tab.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(settings_tab, "logger", SimpleNamespace(debug=lambda *a, **k: None))
    return Tab(), events, settings_tab


def test_restart_happens_only_after_sync_completes(scrape_tab, monkeypatch):
    tab, events, settings_tab = scrape_tab
    threads = []

    def _sync(app, force=False, blocking=False):
        assert blocking is True, "scrape ke baad sync BLOCKING hona chahiye"
        events.append(("sync", None))
        return True

    monkeypatch.setattr(settings_tab.location_sync, "sync_current_location", _sync)
    monkeypatch.setattr(threading, "Thread",
                        lambda target=None, daemon=None: SimpleNamespace(
                            start=lambda: (threads.append(target), target())[0]))

    tab._scrape_success(5, 40, {"GP-A": ["V1"]}, gp_mode=False)

    order = [e[0] for e in events if e[0] in ("sync", "restart")]
    assert order == ["sync", "restart"], f"sync pehle, restart baad me — mila: {order}"


def test_restart_still_happens_when_sync_fails(scrape_tab, monkeypatch):
    tab, events, settings_tab = scrape_tab

    def _boom(app, force=False, blocking=False):
        events.append(("sync", None))
        raise RuntimeError("server down")

    monkeypatch.setattr(settings_tab.location_sync, "sync_current_location", _boom)
    monkeypatch.setattr(threading, "Thread",
                        lambda target=None, daemon=None: SimpleNamespace(
                            start=lambda: target()))

    tab._scrape_success(5, 40, {"GP-A": ["V1"]}, gp_mode=False)
    assert ("restart", None) in events, "sync fail ho to bhi app restart hona chahiye"


def test_no_sync_and_no_restart_when_nothing_scraped(scrape_tab, monkeypatch):
    tab, events, settings_tab = scrape_tab
    monkeypatch.setattr(settings_tab.location_sync, "sync_current_location",
                        lambda *a, **k: events.append(("sync", None)))

    tab._scrape_success(0, 0, {}, gp_mode=False)
    assert [e[0] for e in events if e[0] in ("sync", "restart")] == []


# ══════════════════════════════════════════════════════════════════════════
# build_block_payload: stale hierarchy upload ko cap nahi karni chahiye
# ══════════════════════════════════════════════════════════════════════════
#
# `Block→Panchayat` hierarchy sirf pool DOWNLOAD bharta hai; scrape nahi.
# Pehle payload us hierarchy ko hi source maanta tha, to ek baar
# '🌐 Block Data Download' dabane ke baad user ka upload usi purane set par
# lock ho jata tha — 25 locally hone par bhi sirf 5 sync hote the.

class _Hier:
    def __init__(self, block_children, villages=("V1",)):
        self.block_children = list(block_children)
        self.villages = list(villages)

    def get_children(self, ptype, pname, ctype):
        if ptype == "Block":
            return list(self.block_children)
        return list(self.villages)


class _HM:
    def __init__(self, suggestions):
        self.suggestions = list(suggestions)

    def get_suggestions(self, key):
        return list(self.suggestions) if key == "location_panchayat" else []


def _payload(monkeypatch, block_children, suggestions):
    import src.location_hierarchy as lh
    monkeypatch.setattr(lh, "get_hierarchy", lambda: _Hier(block_children))
    app = SimpleNamespace(history_manager=_HM(suggestions))
    return location_sync.build_block_payload("JHARKHAND", "SIMDEGA", "THETHAITANGAR",
                                             app=app)


def test_payload_includes_panchayats_missing_from_hierarchy(monkeypatch):
    """User ka poora local set jana chahiye, hierarchy ka purana subset nahi."""
    five = [f"GP-{i}" for i in range(1, 6)]
    twentyfive = [f"GP-{i}" for i in range(1, 26)]
    p = _payload(monkeypatch, block_children=five, suggestions=twentyfive)
    assert len(p["panchayats"]) == 25


def test_payload_keeps_hierarchy_only_entries(monkeypatch):
    """Hierarchy me hai par suggestions me nahi — wo bhi chhoote nahi."""
    p = _payload(monkeypatch, block_children=["GP-X"], suggestions=["GP-Y"])
    assert {x["name"] for x in p["panchayats"]} == {"GP-X", "GP-Y"}


def test_payload_dedupes_and_normalises(monkeypatch):
    p = _payload(monkeypatch, block_children=["GP-A"], suggestions=["gp-a", "  GP-A  ", "GP-B"])
    names = [x["name"] for x in p["panchayats"]]
    assert names == sorted(set(names))
    assert set(names) == {"GP-A", "GP-B"}


def test_payload_still_works_with_empty_hierarchy(monkeypatch):
    p = _payload(monkeypatch, block_children=[], suggestions=["GP-A", "GP-B"])
    assert {x["name"] for x in p["panchayats"]} == {"GP-A", "GP-B"}


def test_payload_none_when_nothing_local(monkeypatch):
    assert _payload(monkeypatch, block_children=[], suggestions=[]) is None


# ══════════════════════════════════════════════════════════════════════════
# Settings se delete → Block→Panchayat link bhi hatna chahiye
# ══════════════════════════════════════════════════════════════════════════
#
# Warna deleted panchayat (a) filtered dropdowns me dikhta rehta hai aur
# (b) union payload ke through server par dobara upload ho jata hai.

def test_delete_removes_block_panchayat_link(monkeypatch):
    from src.tabs import settings_tab

    removed = []

    class Hier:
        def get_children(self, ptype, pname, ctype):
            return ["V1"] if ptype == "Panchayat" else []
        def remove_all_children_of(self, ptype, pname):
            pass
        def remove_child(self, ptype, pname, ctype, cname):
            removed.append((ptype, pname, ctype, cname))

    class HM:
        def get_suggestions(self, k):
            return ["MOHANPUR"] if k == "location_block" else []
        def remove_entry(self, k, v):
            pass

    class Listbox:
        def curselection(self): return (0,)
        def get(self, i): return "🏘️ GP-B  (1 village)"

    class Tab:
        _delete_selected_loc = settings_tab.SettingsTab._delete_selected_loc
        _get_panchayat_keys = settings_tab.SettingsTab._get_panchayat_keys
        _get_village_keys = settings_tab.SettingsTab._get_village_keys

        def __init__(self):
            self.loc_listbox = Listbox()
            self.app = SimpleNamespace(history_manager=HM(), license_info={})

        def _refresh_loc_list(self): pass
        def winfo_toplevel(self): return None

    monkeypatch.setattr(settings_tab, "get_hierarchy", lambda: Hier())
    monkeypatch.setattr(settings_tab.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(settings_tab.messagebox, "showinfo", lambda *a, **k: None)

    Tab()._delete_selected_loc()

    assert ("Block", "MOHANPUR", "Panchayat", "GP-B") in removed, \
        f"Block→Panchayat link hatna chahiye tha, mila: {removed}"


@pytest.mark.parametrize("label,expected", [
    ("🏘️ GP-B  (1 village)", "GP-B"),      # SINGULAR — pehle toot jata tha
    ("🏘️ GP-B  (12 villages)", "GP-B"),
    ("🏘️ GP-B", "GP-B"),
    ("🏘️ NEW GP (WEST)  (3 villages)", "NEW GP (WEST)"),
])
def test_listbox_label_parses_back_to_panchayat_name(label, expected):
    """Delete list ka label parse ho kar asli naam dena chahiye."""
    import re
    m = re.match(r'🏘️\s*(.+?)(?:\s*\(\d+\s+villages?\))?$', label)
    assert m and m.group(1).strip() == expected
