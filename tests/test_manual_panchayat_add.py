"""Dev-mode manual Panchayat add (Settings > Location Data).

`add_panchayat_manual()` bina portal scrape ke ek panchayat ko wahi jagah
likhta hai jahan scrape likhta hai — sabhi PANCHAYAT_KEYS (har tab ka
dropdown) + Block->Panchayat hierarchy (filtered dropdowns).

Server location pool par kuch nahi bhejta — dev/test panchayat shared pool
ko kharab na kare.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tabs import settings_tab
from src.tabs.settings_tab import PANCHAYAT_KEYS, add_panchayat_manual


class FakeHistoryManager:
    def __init__(self, seed: dict | None = None) -> None:
        self.store: dict[str, list[str]] = {k: list(v) for k, v in (seed or {}).items()}
        self.saved: list[tuple[str, str]] = []

    def get_suggestions(self, field_key: str) -> list:
        return list(self.store.get(field_key, []))

    def save_entry(self, field_key: str, value: str) -> None:
        self.saved.append((field_key, value))
        self.store.setdefault(field_key, [])
        if value not in self.store[field_key]:
            self.store[field_key].append(value)


class FakeHierarchy:
    def __init__(self) -> None:
        self.added: list[tuple[str, str, str, str]] = []

    def add_child(self, parent_type, parent_name, child_type, child_name) -> None:
        self.added.append((parent_type, parent_name, child_type, child_name))


@pytest.fixture
def hier(monkeypatch: pytest.MonkeyPatch) -> FakeHierarchy:
    fake = FakeHierarchy()
    monkeypatch.setattr(settings_tab, "get_hierarchy", lambda: fake)
    return fake


def make_app(hm: FakeHistoryManager, license_info: dict | None = None):
    return SimpleNamespace(history_manager=hm, license_info=license_info or {})


# ── Rejections ──

@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_blank_name_rejected(hier, bad):
    hm = FakeHistoryManager()
    added, msg = add_panchayat_manual(make_app(hm), bad)
    assert added is False
    assert hm.saved == []
    assert hier.added == []
    assert msg


def test_duplicate_rejected_case_and_space_insensitive(hier):
    hm = FakeHistoryManager({"location_panchayat": ["BARWADIH"]})
    added, msg = add_panchayat_manual(make_app(hm), "  barwadih ")
    assert added is False
    assert hm.saved == []
    assert hier.added == []
    assert "BARWADIH" in msg


def test_duplicate_detected_from_any_panchayat_key(hier):
    hm = FakeHistoryManager({"mr_track_panchayat": ["CHANDWA"]})
    added, _ = add_panchayat_manual(make_app(hm), "chandwa")
    assert added is False
    assert hm.saved == []


# ── Happy path ──

def test_saved_to_every_panchayat_key_uppercased(hier):
    hm = FakeHistoryManager()
    added, msg = add_panchayat_manual(make_app(hm), "  kanke   west ")
    assert added is True
    assert "KANKE WEST" in msg
    assert sorted(hm.saved) == sorted((k, "KANKE WEST") for k in PANCHAYAT_KEYS)


def test_block_hierarchy_linked_from_history_block(hier):
    hm = FakeHistoryManager({"location_block": ["MOHANPUR"]})
    added, _ = add_panchayat_manual(make_app(hm), "SAPHI")
    assert added is True
    assert hier.added == [("Block", "MOHANPUR", "Panchayat", "SAPHI")]


def test_block_hierarchy_falls_back_to_license_block(hier):
    hm = FakeHistoryManager()
    app = make_app(hm, {"user_block": "sarath"})
    added, _ = add_panchayat_manual(app, "PALOJORI")
    assert added is True
    assert hier.added == [("Block", "SARATH", "Panchayat", "PALOJORI")]


def test_no_block_known_still_saves_but_skips_hierarchy(hier):
    hm = FakeHistoryManager()
    added, _ = add_panchayat_manual(make_app(hm), "NAWADIH")
    assert added is True
    assert hier.added == []
    assert ("location_panchayat", "NAWADIH") in hm.saved


# ── Never crashes the caller ──

def test_hierarchy_failure_does_not_break_the_add(monkeypatch, hier):
    def boom():
        raise RuntimeError("hierarchy file locked")

    monkeypatch.setattr(settings_tab, "get_hierarchy", boom)
    hm = FakeHistoryManager({"location_block": ["MOHANPUR"]})
    added, _ = add_panchayat_manual(make_app(hm), "TOPCHANCHI")
    assert added is True
    assert ("location_panchayat", "TOPCHANCHI") in hm.saved


def test_history_save_failure_reported_not_raised(hier):
    class BrokenHM(FakeHistoryManager):
        def save_entry(self, field_key, value):
            raise RuntimeError("db locked")

    added, msg = add_panchayat_manual(make_app(BrokenHM()), "GIRIDIH")
    assert added is False
    assert msg


def test_does_not_touch_server_location_pool(monkeypatch, hier):
    calls = []
    monkeypatch.setattr(settings_tab.location_sync, "sync_current_location",
                        lambda *a, **k: calls.append(a))
    add_panchayat_manual(make_app(FakeHistoryManager()), "DUMRI")
    assert calls == []
