"""Wagelist Gen ab workcode-filtered mode support karta hai.

User request (13 Sep 2026): "Generate Wagelist" baaki automations jaisa kaam
kare — user workcodes de aur SIRF wahi wagelist bane. Ek bhi workcode na diya
to purana behaviour (pending list ka sab kuch) hi chale.

Fixture `tests/fixtures/wagelist_pending.html` asli portal page se banaya gaya
hai (work names anonymised; workcodes asli, kyunki suffix matching unhi par
tiki hai). Pending table ``ctl00_ContentPlaceHolder1_wagelist_msr`` ka layout:

    Sno. | Panchayat | Work Code | Work Name | Select(checkbox)

yaani workcode hamesha ``tds[2]`` me hai, aur aakhri row blank spacer hoti hai.
Yahan ke teeno helper pure hain (koi Tk/Selenium nahi), isliye fixture se rows
nikaal kar seedha test kiye jaate hain.
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser

import pytest

from src.tabs.wagelist_gen_tab import (
    _parse_workcode_input,
    _pick_next_row_index,
    _wc_match_keys,
)

HTM_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "wagelist_pending.html")

# fixture ke teen pending workcodes
WC_1 = "3422003019/IF/7080902694979"
WC_2 = "3422003019/IF/7080902718672"
WC_3 = "3422003019/IF/7080903414194"


class _WagelistTableParser(HTMLParser):
    """``wagelist_msr`` table ki har <tr> ke <td> texts collect karta hai."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_table = False
        self._depth = 0
        self._cells: list[str] | None = None
        self._buf: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if a.get("id") == "ctl00_ContentPlaceHolder1_wagelist_msr":
                self._in_table = True
                self._depth = 1
            elif self._in_table:
                self._depth += 1
        elif self._in_table and tag == "tr":
            self._cells = []
        elif self._in_table and tag == "td" and self._cells is not None:
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "table" and self._in_table:
            self._depth -= 1
            if self._depth == 0:
                self._in_table = False
        elif self._in_table and tag == "td" and self._buf is not None:
            self._cells.append(" ".join("".join(self._buf).split()))
            self._buf = None
        elif self._in_table and tag == "tr" and self._cells is not None:
            if self._cells:
                self.rows.append(self._cells)
            self._cells = None

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)


@pytest.fixture(scope="module")
def page_work_codes() -> list[str]:
    """Fixture ki pending table se workcode column (tds[2]) — blank row bhi."""
    with open(HTM_PATH, encoding="utf-8", errors="replace") as fh:
        parser = _WagelistTableParser()
        parser.feed(fh.read())
    return [r[2] if len(r) > 2 else "" for r in parser.rows]


# ── Fixture khud sahi hai? ────────────────────────────────────────────────

def test_fixture_has_three_pending_workcodes_plus_blank_row(page_work_codes):
    assert page_work_codes == [WC_1, WC_2, WC_3, ""]


# ── _parse_workcode_input: textbox ka raw text → clean list ───────────────

def test_parse_input_splits_lines_and_drops_blanks():
    raw = f"  {WC_1}  \n\n{WC_2}\n   \n"
    assert _parse_workcode_input(raw) == [WC_1, WC_2]


def test_parse_input_splits_comma_separated_codes():
    assert _parse_workcode_input(f"{WC_1}, {WC_2}") == [WC_1, WC_2]


def test_parse_input_dedupes_keeping_order():
    assert _parse_workcode_input(f"{WC_2}\n{WC_1}\n{WC_2}") == [WC_2, WC_1]


def test_parse_input_of_blank_text_is_empty_list():
    assert _parse_workcode_input("   \n\t  ") == []
    assert _parse_workcode_input(None) == []


# ── _wc_match_keys: teeno paste format match hone chahiye ────────────────

def test_full_portal_workcode_matches_itself(page_work_codes):
    assert _wc_match_keys(page_work_codes[0]) & _wc_match_keys(WC_1)


def test_partial_workcode_paste_matches_full_page_code():
    # user ne panchayat-prefix ke bina paste kiya
    assert _wc_match_keys(WC_1) & _wc_match_keys("IF/7080902694979")


def test_truncated_last6_matches_full_page_code():
    # app ke Results tree / Excel export me workcode isi tarah dikhta hai
    assert _wc_match_keys(WC_1) & _wc_match_keys("694979")


def test_lowercase_and_whitespace_paste_still_matches():
    assert _wc_match_keys(WC_1) & _wc_match_keys("  3422003019/if/7080902694979 ")


def test_different_workcodes_do_not_match():
    assert not (_wc_match_keys(WC_1) & _wc_match_keys(WC_2))


def test_blank_code_has_no_keys_and_never_matches():
    assert _wc_match_keys("") == frozenset()
    assert not (_wc_match_keys(WC_1) & _wc_match_keys("   "))


# ── _pick_next_row_index: ALL mode (koi workcode nahi diya) ───────────────

def test_all_mode_picks_first_row(page_work_codes):
    assert _pick_next_row_index(page_work_codes, None, set()) == 0


def test_all_mode_skips_a_row_that_already_failed(page_work_codes):
    failed = set(_wc_match_keys(WC_1))
    assert _pick_next_row_index(page_work_codes, None, failed) == 1


def test_all_mode_returns_none_when_every_row_failed(page_work_codes):
    failed = set().union(*(_wc_match_keys(c) for c in (WC_1, WC_2, WC_3)))
    assert _pick_next_row_index(page_work_codes, None, failed) is None


def test_all_mode_ignores_the_blank_spacer_row():
    assert _pick_next_row_index(["", "  "], None, set()) is None


# ── _pick_next_row_index: filtered mode (user ne workcodes diye) ──────────

def test_filtered_mode_picks_only_the_requested_row(page_work_codes):
    wanted = [_wc_match_keys(WC_3)]
    assert _pick_next_row_index(page_work_codes, wanted, set()) == 2


def test_filtered_mode_picks_requested_row_via_truncated_code(page_work_codes):
    wanted = [_wc_match_keys("718672")]  # WC_2 ke last 6 digits
    assert _pick_next_row_index(page_work_codes, wanted, set()) == 1


def test_filtered_mode_returns_none_when_no_row_matches(page_work_codes):
    wanted = [_wc_match_keys("3422003019/IF/7080900000000")]
    assert _pick_next_row_index(page_work_codes, wanted, set()) is None


def test_filtered_mode_skips_a_requested_row_that_already_failed(page_work_codes):
    wanted = [_wc_match_keys(WC_1), _wc_match_keys(WC_2)]
    failed = set(_wc_match_keys(WC_1))
    assert _pick_next_row_index(page_work_codes, wanted, failed) == 1


def test_filtered_mode_keeps_page_order_not_input_order(page_work_codes):
    # user ne ulta order me diya — phir bhi table ki pehli matching row pehle
    wanted = [_wc_match_keys(WC_3), _wc_match_keys(WC_1)]
    assert _pick_next_row_index(page_work_codes, wanted, set()) == 0


def test_empty_wanted_list_is_treated_as_all_mode(page_work_codes):
    # khaali textbox → _parse_workcode_input [] deta hai → sab generate ho
    assert _pick_next_row_index(page_work_codes, [], set()) == 0


# ── _extract_row_work_codes: table ki saari rows ka Work Code column ──────
#
# Page se workcode nikalna ab har iteration me poori table ke liye hota hai
# (pehle sirf ek row ke liye hota tha), isliye fast path ek JS call hai. Agar
# wo kisi bhi wajah se galat/naakaam ho to per-row Selenium fallback chalna
# chahiye — warna rows aur codes ki alignment tooti to galat row generate ho
# jayegi.


class _FakeCell:
    def __init__(self, text):
        self._text = text

    def get_attribute(self, name):
        assert name == "innerText"
        return self._text


class _FakeRow:
    def __init__(self, cells):
        self._cells = [_FakeCell(c) for c in cells]

    def find_elements(self, by, value):
        return list(self._cells)


class _FakeDriver:
    """execute_script ka behaviour test ke hisaab se badalta hai."""

    def __init__(self, script_result=None, raises=False):
        self._script_result = script_result
        self._raises = raises
        self.script_calls = 0

    def execute_script(self, script, *args):
        self.script_calls += 1
        if self._raises:
            raise RuntimeError("javascript disabled")
        return self._script_result


def _extract(driver, rows):
    from src.tabs.wagelist_gen_tab import WagelistGenTab
    # unbound call — Tk widget banaye bina sirf logic test karni hai
    return WagelistGenTab._extract_row_work_codes(object(), driver, object(), rows)


def test_extract_uses_js_result_when_it_lines_up_with_rows():
    driver = _FakeDriver(script_result=[WC_1, WC_2, ""])
    rows = [_FakeRow(["1", "Matiyara", "IGNORED"])] * 3
    assert _extract(driver, rows) == [WC_1, WC_2, ""]
    assert driver.script_calls == 1


def test_extract_falls_back_per_row_when_js_throws():
    driver = _FakeDriver(raises=True)
    rows = [
        _FakeRow(["1", "Matiyara", f"  {WC_1}  ", "name", ""]),
        _FakeRow(["2", "Matiyara", WC_2, "name", ""]),
    ]
    assert _extract(driver, rows) == [WC_1, WC_2]


def test_extract_falls_back_per_row_when_js_count_mismatches_rows():
    # misalignment = galat row generate ho jayegi, isliye JS result reject ho
    driver = _FakeDriver(script_result=[WC_1])
    rows = [
        _FakeRow(["1", "Matiyara", WC_1, "name", ""]),
        _FakeRow(["2", "Matiyara", WC_2, "name", ""]),
    ]
    assert _extract(driver, rows) == [WC_1, WC_2]


def test_extract_fallback_gives_blank_for_a_row_without_a_third_cell():
    driver = _FakeDriver(raises=True)
    rows = [_FakeRow(["&nbsp;", "&nbsp;"]), _FakeRow(["1", "Matiyara", WC_3, "n", ""])]
    assert _extract(driver, rows) == ["", WC_3]


# ── _report_missing_work_codes: jo maanga tha par mila nahi ──────────────
#
# Filtered mode ka sabse zaroori feedback: user ne 5 code diye, 3 bane — baaki
# 2 ka kya hua? Har missing code ki ek 'Not Found' row banni chahiye taaki
# Excel export me bhi dikhe.


class _RecordingTab:
    """Sirf wahi methods jo _report_missing_work_codes chhuta hai."""

    def __init__(self):
        self.warnings = []
        self.results = []

    def log_warning(self, msg):
        self.warnings.append(msg)

    def _log_result(self, panchayat, work_code, status, wagelist_no, job_card, name):
        self.results.append((panchayat, work_code, status, wagelist_no))


def _report(wanted, handled):
    from src.tabs.wagelist_gen_tab import WagelistGenTab
    tab = _RecordingTab()
    WagelistGenTab._report_missing_work_codes(tab, wanted, handled)
    return tab


def test_missing_codes_get_a_not_found_result_row():
    tab = _report([WC_1, WC_2, WC_3], {WC_2})
    assert [(r[1], r[2]) for r in tab.results] == [
        (WC_1, "Not Found"),
        (WC_3, "Not Found"),
    ]


def test_nothing_is_reported_when_every_requested_code_was_handled():
    tab = _report([WC_1, WC_2], {WC_1, WC_2})
    assert tab.results == []
    assert tab.warnings == []


def test_missing_codes_are_also_logged_as_warnings():
    tab = _report([WC_1, WC_2], {WC_1})
    assert any("1" in w for w in tab.warnings)          # summary line
    assert any(WC_2 in w for w in tab.warnings)         # the code itself


# ── Partial-suffix paste (bug, 13 Sep 2026) ──────────────────────────────
#
# User ne "18672" / "14194" diye — ye 7080902718672 / 7080903414194 ke last
# FIVE digits hain. Matcher sirf full / last-segment / last-SIX jaanta tha, to
# ek bhi row match nahi hui aur log me "No more requested work codes pending"
# aa gaya. Ab page ki row apne numeric tail ke har suffix se match karti hai.
#
# Suffix expansion SIRF page side par hota hai. Dono taraf karte to do alag
# works jinke tail ka aakhri hissa same hai (…694979 aur …124979) aapas me
# galat match kar jate.

WC_TAIL_TWIN_A = "3422003019/IF/7080902694979"   # WC_1 jaisa hi tail-end: 4979
WC_TAIL_TWIN_B = "3422003019/IF/7080902124979"   # alag work, same last 4


def test_last5_fragment_paste_matches_the_page_row(page_work_codes):
    # exactly the user's report
    wanted = [_wc_match_keys("18672")]
    assert _pick_next_row_index(page_work_codes, wanted, set()) == 1


def test_both_reported_fragments_match_their_rows(page_work_codes):
    assert _pick_next_row_index(page_work_codes, [_wc_match_keys("14194")], set()) == 2


def test_last4_fragment_paste_matches_the_page_row(page_work_codes):
    assert _pick_next_row_index(page_work_codes, [_wc_match_keys("4194")], set()) == 2


def test_fragment_shorter_than_four_digits_is_ignored(page_work_codes):
    # "194" har doosre workcode se takra sakta hai — itna dhila match mat karo
    assert _pick_next_row_index(page_work_codes, [_wc_match_keys("194")], set()) is None


def test_fragment_still_does_not_match_an_unrelated_row(page_work_codes):
    assert _pick_next_row_index(page_work_codes, [_wc_match_keys("18672")], set()) != 0


def test_two_works_with_the_same_tail_end_are_not_confused():
    rows = [WC_TAIL_TWIN_A, WC_TAIL_TWIN_B]
    # poora code dene par sirf apni hi row mile
    assert _pick_next_row_index(rows, [_wc_match_keys(WC_TAIL_TWIN_B)], set()) == 1


def test_a_failed_row_does_not_skip_a_different_row_sharing_its_tail_end():
    # failed-tracking identity keys par hona chahiye, suffix keys par nahi —
    # warna …694979 fail hote hi …124979 bhi chup-chaap skip ho jayegi
    rows = [WC_TAIL_TWIN_A, WC_TAIL_TWIN_B]
    failed = set(_wc_match_keys(WC_TAIL_TWIN_A))
    assert _pick_next_row_index(rows, None, failed) == 1


# ── _wanted_codes_satisfied_by: 'Not Found' report sahi rahe ─────────────
#
# Row match karne ke baad ye tay karta hai ki user ke kaun-kaun se diye gaye
# code us row se poore ho gaye. Agar ye bhi identity keys par chalta to
# fragment ("18672") se wagelist ban jaane ke BAAD bhi wo code 'Not Found'
# report hota — filtered mode ka sabse bharosa-todne wala bug.

def _satisfied(page_code, wanted):
    from src.tabs.wagelist_gen_tab import _wanted_codes_satisfied_by
    return _wanted_codes_satisfied_by(page_code, [(c, _wc_match_keys(c)) for c in wanted])


def test_a_fragment_is_marked_satisfied_by_the_row_it_generated():
    assert _satisfied(WC_2, ["18672"]) == {"18672"}


def test_a_full_code_is_marked_satisfied_by_its_row():
    assert _satisfied(WC_2, [WC_2]) == {WC_2}


def test_several_spellings_of_the_same_work_are_all_satisfied_at_once():
    # user ne galti se ek hi work teen tarah se daal diya
    assert _satisfied(WC_2, [WC_2, "718672", "18672"]) == {WC_2, "718672", "18672"}


def test_codes_for_other_works_stay_unsatisfied():
    assert _satisfied(WC_2, [WC_1, "14194"]) == set()


def test_nothing_is_satisfied_when_no_codes_were_requested():
    assert _satisfied(WC_2, []) == set()
