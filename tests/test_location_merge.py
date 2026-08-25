"""AUDIT Batch-6: location_sync merge behavior tests (missing-only merge).

Pool ka CORE promise: server data sirf MISSING entries bharta hai — user ki
local edits kabhi overwrite nahi hoti. Ye tests usi invariant ko pin karte
hain (fake hierarchy + fake history ke saath — koi real file touch nahi).

Run: venv/bin/python -m pytest tests/test_location_sync_merge.py -v
"""
from types import SimpleNamespace

import pytest

import src.location_hierarchy as lh_mod
import src.location_sync as LS


class FakeHierarchy:
    """get_children/add_child ka minimal in-memory stand-in."""

    def __init__(self):
        self.children = {}   # (child_type, parent_name) -> [names]
        self.calls = []      # add_child audit

    def get_children(self, _ptype, pname, ctype):
        return list(self.children.get((ctype, pname), []))

    def add_child(self, ptype, pname, ctype, name):
        self.calls.append((ptype, pname, ctype, name))
        bucket = self.children.setdefault((ctype, pname), [])
        if name not in bucket:
            bucket.append(name)


class FakeHistory:
    def __init__(self):
        self.saved = []

    def get_suggestions(self, key):
        return []

    def save_entry(self, key, value):
        self.saved.append((key, value))


@pytest.fixture
def env(monkeypatch):
    hier = FakeHierarchy()
    monkeypatch.setattr(lh_mod, "get_hierarchy", lambda: hier)
    app = SimpleNamespace(history_manager=FakeHistory())
    return hier, app


# ---------------------------------------------------------------------------
# _norm — UPPER + whitespace collapse (merge-dedup isi par depend karta hai)
# ---------------------------------------------------------------------------

def test_norm_upper_and_collapse():
    assert LS._norm("  rampur   block ") == "RAMPUR BLOCK"


# ---------------------------------------------------------------------------
# apply_server_data — missing-only merge invariant
# ---------------------------------------------------------------------------

def test_apply_empty_returns_zero(env):
    hier, app = env
    assert LS.apply_server_data("BLOCK", [], app=app) == (0, 0)


def test_apply_new_block_adds_all(env):
    hier, app = env
    payload = [{"name": "Panch One", "villages": ["V1", "V2"]}]
    added = LS.apply_server_data("BLOCK", payload, app=app)
    assert added == (1, 2)
    # Hierarchy me panchayat + dono villages gaye
    assert ("Block", "BLOCK", "Panchayat", "PANCH ONE") in hier.calls
    assert ("Panchayat", "PANCH ONE", "Village", "V1") in hier.calls
    assert ("Panchayat", "PANCH ONE", "Village", "V2") in hier.calls


def test_apply_is_idempotent(env):
    """Dobara same data bhejne par kuch naya add NAHI hona chahiye."""
    hier, app = env
    payload = [{"name": "Panch One", "villages": ["V1", "V2"]}]
    assert LS.apply_server_data("BLOCK", payload, app=app) == (1, 2)
    assert LS.apply_server_data("BLOCK", payload, app=app) == (0, 0)


def test_apply_merges_only_missing_villages(env):
    """Panchayat pehle se hai → skip; sirf NAYI villages add hon."""
    hier, app = env
    hier.add_child("Block", "BLOCK", "Panchayat", "PANCH ONE")
    hier.add_child("Panchayat", "PANCH ONE", "Village", "V1")

    payload = [{"name": "Panch One", "villages": ["V1", "V2", "V3"]}]
    added = LS.apply_server_data("BLOCK", payload, app=app)
    assert added == (0, 2)  # panchayat skip, V2+V3 naye


def test_apply_case_insensitive_dedup(env):
    """'rampur' vs 'RAMPUR' — normalization ke baad same entry, duplicate nahi."""
    hier, app = env
    first = LS.apply_server_data(
        "BLOCK", [{"name": "Rampur", "villages": ["V1"]}], app=app)
    second = LS.apply_server_data(
        "BLOCK", [{"name": "rampur", "villages": ["v1"]}], app=app)
    assert first == (1, 1)
    assert second == (0, 0)


# ---------------------------------------------------------------------------
# DemandTab._get_village_code — state-specific job-card parsing
# ---------------------------------------------------------------------------

def test_village_code_jh():
    """JH: '/' se PEHLA segment lo, uska last '-' hissa village-code hai."""
    from src.tabs.demand_tab import DemandTab
    stub = SimpleNamespace(log_info=lambda *a, **k: None)
    assert DemandTab._get_village_code(stub, "DUMKA-GP-3456/2025", "jh") == "3456"


def test_village_code_rj_last_three():
    from src.tabs.demand_tab import DemandTab
    stub = SimpleNamespace(log_info=lambda *a, **k: None)
    assert DemandTab._get_village_code(stub, "BR1223344", "rj") == "344"
