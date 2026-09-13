"""MGNREGA rozgaar guarantee 100 → 125 din (user report, 13 Sep 2026).

Cap teen jagah bikhra hua tha: asli ghataav (`avail = 100 - worked`), result ka
status text ("Skipped (100 days)"), aur `_log_result` ke andar dafan tag matcher
jo literal '100 days' dhundhta tha. Teeno ko ek constant par laaya gaya hai
taaki agli baar (150?) sirf `config.MGNREGA_GUARANTEED_DAYS` badle.

Tag matcher isliye bhi test hota hai: wo `_log_result` ke andar tha, to koi
number badalne par yellow 'skipped' rows chup-chaap rang khoti — dikhta kuch
nahi, bas galat.
"""

from __future__ import annotations

import pytest

from src import config
from src.tabs.demand_tab import _allocate_days, _days_available, _status_tags


# ── Constant hi ab sach hai ──────────────────────────────────────────────

def test_guaranteed_days_is_one_twenty_five():
    assert config.MGNREGA_GUARANTEED_DAYS == 125


# ── _days_available: ghar ne kitne din aur paa sakta hai ────────────────

def test_a_household_that_has_worked_nothing_gets_the_full_entitlement():
    assert _days_available(0) == 125


def test_a_household_past_the_old_hundred_limit_still_has_days_left():
    # yahi asli bug tha — 100..124 wale galat 'Skipped' ho rahe the
    assert _days_available(100) == 25
    assert _days_available(120) == 5


def test_a_household_at_the_new_limit_has_nothing_left():
    assert _days_available(125) == 0


def test_a_household_past_the_new_limit_goes_negative_so_the_caller_skips():
    assert _days_available(130) == -5


def test_availability_tracks_the_constant_rather_than_a_hardcoded_number():
    assert _days_available(0) == config.MGNREGA_GUARANTEED_DAYS


# ── _allocate_days: ek job card ke kai labourers me din baantna ─────────

def test_everyone_gets_the_asked_days_when_the_card_has_room():
    assert _allocate_days(user_days=14, avail=125, applicant_count=5) == 14


def test_days_are_split_evenly_when_the_ask_exceeds_whats_left():
    # 30 x 5 = 150 > 125 → 125 // 5
    assert _allocate_days(user_days=30, avail=125, applicant_count=5) == 25


def test_a_lone_applicant_is_capped_at_whats_left():
    assert _allocate_days(user_days=14, avail=5, applicant_count=1) == 5


def test_split_rounds_down_to_zero_when_there_is_less_than_one_day_each():
    # caller ka niyam: adj_days 0 ho to pehle applicant ko poora avail milta hai
    assert _allocate_days(user_days=14, avail=3, applicant_count=5) == 0


def test_an_empty_applicant_list_does_not_divide_by_zero():
    assert _allocate_days(user_days=14, avail=5, applicant_count=0) == 5


def test_the_new_limit_lets_a_full_ask_through_that_the_old_one_would_have_cut():
    # 25 x 5 = 125: purane 100-cap par ye 20 ho jata, ab poora 25 milta hai
    assert _allocate_days(user_days=25, avail=_days_available(0), applicant_count=5) == 25


# ── _status_tags: result row ka rang ────────────────────────────────────

def test_the_day_limit_skip_row_is_a_warning_not_a_failure():
    assert _status_tags(f"Skipped ({config.MGNREGA_GUARANTEED_DAYS} days)") == ('warning',)


def test_the_day_limit_skip_row_stays_a_warning_if_the_number_changes_again():
    # matcher kisi number par nahi tika hona chahiye
    assert _status_tags("Skipped (150 days)") == ('warning',)
    assert _status_tags("Skipped (100 days)") == ('warning',)


@pytest.mark.parametrize("status", [
    "Failed (Grid did not refresh)",
    "Skipped (JC Not Issued)",
    "Error: aadhaar mismatch",
    "Invalid date",
])
def test_real_failures_stay_red(status):
    assert _status_tags(status) == ('failed',)


@pytest.mark.parametrize("status", ["Demand already exists", "Adjusted to 5 days"])
def test_other_warnings_stay_yellow(status):
    assert _status_tags(status) == ('warning',)


@pytest.mark.parametrize("status", ["Success", "Saved", "Done"])
def test_successes_stay_green(status):
    assert _status_tags(status) == ('success',)


def test_an_unrecognised_status_gets_no_colour():
    assert _status_tags("Processing") == ()


def test_failure_wins_over_warning_when_a_status_reads_as_both():
    # "not issued" failed-list me hai aur "skip" warning-list me — red jeete
    assert _status_tags("Skipped (JC Not Issued)") == ('failed',)
