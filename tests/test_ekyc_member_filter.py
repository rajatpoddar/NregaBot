"""eKYC report ka Yes/No filter member-wise hona chahiye, jobcard-wise nahi.

User report (13 Sep 2026): ek job card par kai members hote hain; filter "Yes"
par us card ke sirf Yes-wale members aane chahiye, No-wale nahi (aur ulta bhi).

Do asli bugs the:

1. RULE-UI-002 — `check_and_insert_to_tree()` scraping ke worker thread se
   SEEDHA Tk chhuta tha (`filter_var.get()`, `tree.get_children()`,
   `tree.insert()`, `tree.yview_moveto()`). docs/RULES.md:40 ke mutabik aisa
   widget call "silently fail" kar sakta hai — yaani rows chupchaap gir jaati
   hain. Ek card ke 2 me se 1 member gire to report jobcard-wise dikhti hai.

2. Filter logic Tk var par tiki thi, isliye test hi nahi ho sakti thi.

Fixtures `tests/fixtures/ekyc_grid_page{1,2}.html` asli portal pages se banaye
gaye hain — markup ki shakl asli (table id, 10 columns, span/hidden-input
wrappers, uppercase "NO", nested-table pagination row), par har naam aur job
card number FAKE hai. Page 2 me mixed job card maujood hai:
app#1 ESHWAR RANA = Yes, app#2 GOPAL SOREN = NO.
"""

from __future__ import annotations

import os
from html.parser import HTMLParser

import pytest

from src.tabs.ekyc_report_tab import EKycReportTab, _matches_filter

HTM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

MIXED_JC = "JH-99-999-999-001/36"
MIXED_YES_MEMBER = "ESHWAR RANA"         # app#1, eKyc = Yes
MIXED_NO_MEMBER = "GOPAL SOREN"          # app#2, eKyc = NO


class _GridParser(HTMLParser):
    """gvData ki har <tr> ke <td> texts — Selenium jaisa flat view."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in = False
        self._depth = 0
        self._cells: list[str] | None = None
        self._buf: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if a.get("id") == "ctl00_ContentPlaceHolder1_gvData":
                self._in, self._depth = True, 1
            elif self._in:
                self._depth += 1
        elif self._in and tag == "tr":
            self._cells = []
        elif self._in and tag == "td" and self._cells is not None:
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "table" and self._in:
            self._depth -= 1
            if self._depth == 0:
                self._in = False
        elif self._in and tag == "td" and self._buf is not None:
            self._cells.append(" ".join("".join(self._buf).split()))
            self._buf = None
        elif self._in and tag == "tr" and self._cells is not None:
            if self._cells:
                self.rows.append(self._cells)
            self._cells = None

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)


@pytest.fixture(scope="module")
def scraped_records() -> list[dict]:
    """Dono fixture pages ko scraper ke column mapping se records me badlo."""
    records = []
    for fname in ("ekyc_grid_page1.html", "ekyc_grid_page2.html"):
        with open(os.path.join(HTM_DIR, fname), encoding="utf-8", errors="replace") as fh:
            parser = _GridParser()
            parser.feed(fh.read())
        for cols in parser.rows:
            if len(cols) < 5:
                continue
            jc = cols[1].strip()
            if "Job Card" in jc or len(jc) < 5:
                continue
            records.append({
                "panchayat": "Matiyara", "village": "Amtatanr",
                "jobcard": jc, "name": cols[3].strip(),
                "abps": cols[-2].strip(), "ekyc": cols[-1].strip(),
            })
    return records


def test_the_fixture_contains_a_mixed_status_job_card(scraped_records):
    """Fixture khud sahi hai — warna neeche ke test jhoothe green ho jayenge."""
    members = {r["name"]: r["ekyc"] for r in scraped_records if r["jobcard"] == MIXED_JC}
    assert members == {MIXED_YES_MEMBER: "Yes", MIXED_NO_MEMBER: "NO"}


# ── _matches_filter: ek member ka eKYC value vs chuna hua filter ─────────

@pytest.mark.parametrize("ekyc", ["Yes", "yes", "YES", " Yes "])
def test_a_verified_member_shows_under_the_yes_filter(ekyc):
    assert _matches_filter(ekyc, "Verified (Yes)") is True
    assert _matches_filter(ekyc, "Not Verified (No)") is False


@pytest.mark.parametrize("ekyc", ["No", "no", "NO", " NO "])
def test_an_unverified_member_shows_under_the_no_filter(ekyc):
    # portal asli me uppercase "NO" bhejta hai — dekho fixture page 2
    assert _matches_filter(ekyc, "Not Verified (No)") is True
    assert _matches_filter(ekyc, "Verified (Yes)") is False


@pytest.mark.parametrize("ekyc", ["Yes", "NO", ""])
def test_the_all_filter_shows_everyone(ekyc):
    assert _matches_filter(ekyc, "All") is True


def test_a_blank_ekyc_value_counts_as_not_verified():
    assert _matches_filter("", "Not Verified (No)") is True
    assert _matches_filter(None, "Not Verified (No)") is True


# ── Asli requirement: ek job card ke members alag-alag chhante jaayein ──

def test_yes_filter_keeps_only_the_verified_member_of_a_mixed_job_card(scraped_records):
    shown = [r["name"] for r in scraped_records
             if r["jobcard"] == MIXED_JC and _matches_filter(r["ekyc"], "Verified (Yes)")]
    assert shown == [MIXED_YES_MEMBER]


def test_no_filter_keeps_only_the_unverified_member_of_a_mixed_job_card(scraped_records):
    shown = [r["name"] for r in scraped_records
             if r["jobcard"] == MIXED_JC and _matches_filter(r["ekyc"], "Not Verified (No)")]
    assert shown == [MIXED_NO_MEMBER]


def test_the_filter_never_drops_a_whole_job_card(scraped_records):
    """Jobcard-wise filtering ka ulta proof: mixed card dono filters me dikhe."""
    for mode in ("Verified (Yes)", "Not Verified (No)"):
        cards = {r["jobcard"] for r in scraped_records if _matches_filter(r["ekyc"], mode)}
        assert MIXED_JC in cards


def test_every_member_lands_in_exactly_one_of_the_two_filters(scraped_records):
    yes = [r for r in scraped_records if _matches_filter(r["ekyc"], "Verified (Yes)")]
    no = [r for r in scraped_records if _matches_filter(r["ekyc"], "Not Verified (No)")]
    assert len(yes) + len(no) == len(scraped_records)
    assert len(no) == 3          # dono fixture pages milakar 3 NO members


# ── RULE-UI-002: worker thread se Tk ko haath nahi lagana ───────────────

class _ExplodingTree:
    """Koi bhi Tk touch = test fail."""

    def __getattr__(self, name):
        raise AssertionError(
            f"RULE-UI-002 toota: worker thread se tree.{name}() call hua")


class _RecordingApp:
    def __init__(self):
        self.scheduled = []

    def after(self, ms, callback, *args):
        self.scheduled.append((ms, callback, args))


class _WorkerThreadTab:
    """Scraping thread par jo tab dikhta hai — uske sirf zaroori hisse."""

    def __init__(self):
        self.app = _RecordingApp()
        self.tree = _ExplodingTree()
        self.results_tree = self.tree
        self.filter_var = _ExplodingTree()

    def _is_alive(self):
        return True

    # Asli method — taaki test ye bhi pakde ki sahi callback schedule hua
    _insert_records = EKycReportTab._insert_records


def test_queuing_rows_from_the_worker_thread_never_touches_tk(scraped_records):
    tab = _WorkerThreadTab()
    # _ExplodingTree phatt jayega agar koi seedha Tk call hua
    EKycReportTab._flush_rows_to_tree(tab, scraped_records[:5])
    assert len(tab.app.scheduled) == 1, "rows ek hi batch me main thread par jaani chahiye"
    ms, callback, args = tab.app.scheduled[0]
    assert ms == 0
    assert callback == tab._insert_records
    assert list(args[0]) == scraped_records[:5]


def test_an_empty_batch_schedules_nothing():
    tab = _WorkerThreadTab()
    EKycReportTab._flush_rows_to_tree(tab, [])
    assert tab.app.scheduled == []


def test_the_queued_batch_is_a_copy_so_the_worker_can_reuse_its_list(scraped_records):
    """Worker apni list clear karke agla page bhar deta hai — batch bache."""
    tab = _WorkerThreadTab()
    page = list(scraped_records[:3])
    EKycReportTab._flush_rows_to_tree(tab, page)
    page.clear()
    queued = tab.app.scheduled[0][2][0]
    assert len(queued) == 3
