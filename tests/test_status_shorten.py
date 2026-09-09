"""Footer status text ka bound (STOP ALL button gayab ho jata tha).

Bug (user report, 9 Sep 2026): eMB Entry chalte waqt footer ka status itna
lamba ho jata tha ki poora footer kha leta tha aur "STOP ALL" button dikhna
hi band ho jata tha.

    Status: 3404003001/IF/7080902209903$(IF-Plantatin/Baghchatta/Yorel
    Kerketta ka Aam Bagwani 0.91 Decimil/4/22-23): period 1/2 (03/08/2026...)

Asli footer par naapa gaya (1160px footer):
    chhota status → status_frame 257px,  dock_frame mapped=True
    lamba status  → status_frame 1101px, dock_frame mapped=False   <- STOP ALL gayab

`set_status()` message ko bina kisi limit ke label me daal deta tha. Footer me
status_frame (side="left") dock_frame (side="right") se PEHLE pack hota hai,
aur Tk ka packer pehle pack hue slave ko cavity pehle deta hai — to lamba text
dock ko bhookha maar deta tha.

Fix do hisson me:
  1. `shorten_status()` — message par bound (beech me ellipsis).
  2. footer me dock_frame ko status_frame se PEHLE pack karo, taaki right side
     apni jagah hamesha reserve kar le.
"""

from __future__ import annotations

import pytest

from src.utils import STATUS_MAX_CHARS, shorten_status

LONG = ("3404003001/IF/7080902209903$(IF-Plantatin/Baghchatta/Yorel Kerketta ka "
        "Aam Bagwani 0.91 Decimil/4/22-23): period 1/2 (03/08/2026~~~~17/08/2026)")


# ── Chhote message chhede nahi jate ────────────────────────────────────────

@pytest.mark.parametrize("msg", ["Ready", "Running eMB Entry...", "Automation Finished"])
def test_short_messages_pass_through(msg):
    assert shorten_status(msg) == msg


def test_exactly_at_limit_untouched():
    msg = "x" * STATUS_MAX_CHARS
    assert shorten_status(msg) == msg


@pytest.mark.parametrize("empty", ["", None, "   "])
def test_empty_becomes_empty_string(empty):
    assert shorten_status(empty) == ""


# ── Lamba message bound me aata hai ────────────────────────────────────────

def test_long_message_is_capped():
    out = shorten_status(LONG)
    assert len(LONG) > STATUS_MAX_CHARS
    assert len(out) == STATUS_MAX_CHARS


def test_long_message_keeps_head_and_tail():
    """Dono kinare kaam ke hain — workcode shuru me, period ant me."""
    out = shorten_status(LONG)
    assert "…" in out
    assert out.startswith("3404003001/IF/")
    assert out.endswith("17/08/2026)")


def test_whitespace_and_newlines_collapsed():
    """Newline footer label ki ek line ko tod deta hai."""
    assert shorten_status("Saving\n  work\t\tnow") == "Saving work now"


# ── Bound configurable + degenerate values par crash nahi ──────────────────

def test_custom_limit_respected():
    out = shorten_status(LONG, limit=20)
    assert len(out) == 20
    assert "…" in out


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_tiny_limits_do_not_crash(limit):
    out = shorten_status(LONG, limit=limit)
    assert len(out) <= limit


def test_non_string_input():
    assert shorten_status(12345) == "12345"
