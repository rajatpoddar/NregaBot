"""Wagelist Gen ke checkbox settings app restart ke baad yaad rehne chahiye.

User report (13 Sep 2026): "Save PDF" tick karke app band karo, dobara kholo —
tick gayab. Baaki tabs (duplicate_mr, mr_tracking, pending_bills, ...) pehle se
`history_manager.save_tab_inputs_batch()` / `get_tab_inputs()` use karte hain;
Wagelist Gen me wo wiring thi hi nahi.

DB me value hamesha string banti hai (`save_tab_inputs_batch` khud `str(v)`
karta hai), isliye load side ko string se CTk ke "on"/"off" tak le jaana hai —
purani/kharaab value par bhi bina crash ke sensible default.
"""

from __future__ import annotations

import pytest

from src.tabs.wagelist_gen_tab import WagelistGenTab, _checkbox_state


# ── _checkbox_state: stored string → "on" / "off" ────────────────────────

@pytest.mark.parametrize("raw", ["on", "On", " ON ", "1", "true", "True", "yes"])
def test_truthy_stored_values_read_as_on(raw):
    assert _checkbox_state(raw, "off") == "on"


@pytest.mark.parametrize("raw", ["off", "Off", " OFF ", "0", "false", "no"])
def test_falsy_stored_values_read_as_off(raw):
    assert _checkbox_state(raw, "on") == "off"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_missing_value_falls_back_to_the_default(raw):
    assert _checkbox_state(raw, "on") == "on"
    assert _checkbox_state(raw, "off") == "off"


def test_unrecognised_value_falls_back_to_the_default():
    assert _checkbox_state("banana", "on") == "on"


# ── _load_inputs / _save_inputs: asli var par asar ──────────────────────

class _FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeHistoryManager:
    def __init__(self, stored=None):
        self.stored = stored
        self.saved = None

    def get_tab_inputs(self, tab_key):
        assert tab_key == "wagelist_gen"
        return self.stored

    def save_tab_inputs_batch(self, tab_key, data):
        assert tab_key == "wagelist_gen"
        self.saved = dict(data)


class _FakeTab:
    """Sirf wahi cheezein jo _load_inputs / _save_inputs chhute hain."""

    def __init__(self, stored=None):
        self.history_manager = _FakeHistoryManager(stored)
        self.app = self
        self.save_pdf_var = _FakeVar("off")
        self.send_to_sender_var = _FakeVar("on")


def _load(stored):
    tab = _FakeTab(stored)
    WagelistGenTab._load_inputs(tab)
    return tab


def test_a_ticked_save_pdf_box_comes_back_ticked():
    tab = _load({"save_pdf": "on"})
    assert tab.save_pdf_var.get() == "on"


def test_an_unticked_auto_send_box_comes_back_unticked():
    tab = _load({"send_to_sender": "off"})
    assert tab.send_to_sender_var.get() == "off"


def test_first_ever_run_keeps_the_shipped_defaults():
    tab = _load({})
    assert tab.save_pdf_var.get() == "off"
    assert tab.send_to_sender_var.get() == "on"


def test_a_broken_history_manager_does_not_crash_the_tab():
    class _Exploding:
        def get_tab_inputs(self, tab_key):
            raise RuntimeError("db locked")

    tab = _FakeTab()
    tab.history_manager = _Exploding()
    WagelistGenTab._load_inputs(tab)          # must not raise
    assert tab.save_pdf_var.get() == "off"


def test_saving_writes_both_checkbox_states():
    tab = _FakeTab()
    tab.save_pdf_var.set("on")
    tab.send_to_sender_var.set("off")
    WagelistGenTab._save_inputs(tab)
    assert tab.history_manager.saved == {"save_pdf": "on", "send_to_sender": "off"}


def test_saving_survives_a_broken_history_manager():
    class _Exploding:
        def save_tab_inputs_batch(self, tab_key, data):
            raise RuntimeError("disk full")

    tab = _FakeTab()
    tab.history_manager = _Exploding()
    WagelistGenTab._save_inputs(tab)          # must not raise


def test_a_saved_state_survives_a_round_trip():
    tab = _FakeTab()
    tab.save_pdf_var.set("on")
    WagelistGenTab._save_inputs(tab)

    reopened = _load(tab.history_manager.saved)
    assert reopened.save_pdf_var.get() == "on"


# ── Work Codes textbox persist NAHI hona chahiye ────────────────────────

def test_work_codes_are_never_persisted():
    """Per-run data hai — agli baar chupchaap filter lag gaya to user phasega."""
    tab = _FakeTab()
    WagelistGenTab._save_inputs(tab)
    assert "work_codes" not in tab.history_manager.saved
