"""eMB Entry ka measurement-period loop.

Do cheezein cover karta hai:
  A. stale element reference par loop toot jata tha (fix: options ko strings
     me snapshot karo)
  B. "No Muster Roll Available" ko error ki tarah report kiya jata tha
     (fix: Skipped, kyunki eMB pehle ho chuka hai ya MR abhi login me
     aaya nahi — dono error nahi hain)

--- A ---

Bug (user log, 9 Sep 2026):

    [13:56:19]    Found 2 measurement period(s) for 3404003001/IF/...
    [13:56:19]    [1/2] Processing period: 03/08/2026~~~~17/08/2026
    [13:56:22]       Period '...': 0 persondays / eMB already booked — skipping.
    [13:56:22] ❌ Error on 3404003001/IF/...: stale element reference

`[2/2] Processing period` line kabhi nahi chhapi — matlab exception loop
body ke pehle statement par hi aayi.

`_process_all_measurement_periods` period dropdown ke <option> **WebElement**
references ek baar list me rakh leta tha:

    period_options = [o for o in period_select.options if o.get_attribute("value")]
    for idx, period_option in enumerate(period_options, 1):
        period_value = period_option.get_attribute("value")   # <- iteration 2 par stale

Pehle period ka selection ASP.NET full postback karta hai — page reload hote
hi wo saare option references detach ho jate hain. Iteration 2 par unhe padhna
StaleElementReferenceException deta hai, jo inner try se BAHAR hai, isliye poora
work "Failed" ho jata tha.

Fix: options ko strings me snapshot karo (wahi pattern jo isi file ke
`_process_all_works_from_dropdown` me pehle se hai), WebElement mat pakdo.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from selenium.common.exceptions import StaleElementReferenceException

from src.tabs import mb_entry_tab
from src.tabs.mb_entry_tab import MbEntryTab

PERIOD_ID = "ctl00_ContentPlaceHolder1_ddlSelMPeriod"
PERSONDAYS_ID = "ctl00_ContentPlaceHolder1_lbl_person_days"
MSR_ID = "ctl00_ContentPlaceHolder1_lbl_msr"

PERIODS = [("v1", "03/08/2026~~~~17/08/2026"),
           ("v2", "22/08/2026~~~~31/08/2026")]


# ── Fakes: postback par purane references stale ho jate hain ────────────────

class Page:
    """Generation counter — har postback purani sabhi references ko stale karta hai."""

    def __init__(self, periods, persondays="0", msr_text="MR-123"):
        self.generation = 0
        self.periods = list(periods)
        self.persondays = persondays
        self.msr_text = msr_text
        self.selected_value = None
        self.selects = []

    def postback(self):
        self.generation += 1


class FakeEl:
    def __init__(self, page, text=""):
        self.page = page
        self.born = page.generation
        self._text = text
        self.tag_name = "select"

    def _check(self):
        if self.born != self.page.generation:
            raise StaleElementReferenceException(
                "stale element reference: stale element not found")

    def is_enabled(self):
        self._check()
        return True

    def is_displayed(self):
        self._check()
        return True

    @property
    def text(self):
        self._check()
        return self._text

    def get_attribute(self, name):
        self._check()
        if name == "value":
            return self._text
        return None


class FakeOption(FakeEl):
    def __init__(self, page, value, text):
        super().__init__(page, text)
        self.value = value

    def get_attribute(self, name):
        self._check()
        return self.value if name == "value" else None


class FakeSelect:
    """Selenium Select ka stand-in — select karne par postback hota hai."""

    def __init__(self, element):
        element._check()          # asli Select bhi stale element par phatta hai
        self.page = element.page

    @property
    def options(self):
        page = self.page
        return [FakeOption(page, "", "-----Select-----")] + [
            FakeOption(page, v, t) for v, t in page.periods]

    @property
    def first_selected_option(self):
        opts = self.options
        for o in opts:
            if o.value == self.page.selected_value:
                return o
        return opts[0]

    def select_by_index(self, idx):
        opt = self.options[idx]
        self.page.selected_value = opt.value
        self.page.postback()      # full postback → sab purane refs stale


class FakeDriver:
    def __init__(self, page):
        self.page = page
        self.switch_to = SimpleNamespace(
            alert=property(lambda self: (_ for _ in ()).throw(Exception("no alert"))))

    def find_element(self, by, value):
        if value == PERSONDAYS_ID:
            return FakeEl(self.page, self.page.persondays)
        if value == MSR_ID:
            return FakeEl(self.page, self.page.msr_text)
        return FakeEl(self.page)


class FakeWait:
    def __init__(self, driver, timeout=25):
        self.driver = driver

    def until(self, method, message=""):
        for _ in range(50):
            try:
                value = method(self.driver)
                if value:
                    return value
            except StaleElementReferenceException:
                pass
        raise mb_entry_tab.TimeoutException(message)


class TabUnderTest:
    _process_all_measurement_periods = MbEntryTab._process_all_measurement_periods
    PERSONDAYS_WAIT_TIMEOUT = MbEntryTab.PERSONDAYS_WAIT_TIMEOUT

    def __init__(self):
        self.logs: list[str] = []
        self.results: list[tuple] = []
        self.app = SimpleNamespace(after=lambda *a, **k: None,
                                   set_status=lambda *a, **k: None)

    def is_stopped(self):
        return False

    def log_info(self, m):
        self.logs.append(m)

    def log_warning(self, m):
        self.logs.append(m)

    def log_error(self, m):
        self.logs.append(m)

    def update_status(self, *a, **k):
        pass

    def _log_result(self, cfg, work_code, status, details,
                    work_name="-", mr_no="-", mr_period="-"):
        self.results.append((status, details, mr_period))


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(mb_entry_tab, "Select", FakeSelect)
    monkeypatch.setattr(mb_entry_tab, "WebDriverWait", FakeWait)
    monkeypatch.setattr(mb_entry_tab.time, "sleep", lambda s: None)


def run(page):
    tab = TabUnderTest()
    driver = FakeDriver(page)
    tab._process_all_measurement_periods(
        driver, FakeWait(driver), {"unit_cost": "300", "default_pit_count": "1"},
        "3404003001/IF/7080902209903", "Aam Bagwani", ["MATE"])
    return tab


# ── Regression ─────────────────────────────────────────────────────────────

def test_every_period_visited_after_first_postback():
    """Pehle period ka postback baaki options ko stale kar deta hai."""
    tab = run(Page(PERIODS))

    processed = [m for m in tab.logs if "Processing period" in m]
    assert len(processed) == 2, f"dono period process hone chahiye, mila: {processed}"
    assert "03/08/2026~~~~17/08/2026" in processed[0]
    assert "22/08/2026~~~~31/08/2026" in processed[1]


def test_zero_persondays_skips_both_periods_without_error():
    """User ka exact scenario: dono period 0 persondays."""
    tab = run(Page(PERIODS, persondays="0"))

    assert [r[0] for r in tab.results] == ["Skipped", "Skipped"]
    assert [r[2] for r in tab.results] == [p[1] for p in PERIODS]
    assert not [m for m in tab.logs if "stale element" in m.lower()]


def test_single_period_still_works():
    tab = run(Page(PERIODS[:1]))
    assert len([m for m in tab.logs if "Processing period" in m]) == 1


def test_no_periods_logs_failure():
    tab = run(Page([]))
    assert tab.results == [("Failed", "No measurement period found", "-")]


# ══════════════════════════════════════════════════════════════════════════
# B. "No Muster Roll Available" — error nahi, Skip
# ══════════════════════════════════════════════════════════════════════════
#
# Portal (docs/htm/Measurement Book.htm) us period par ye markup deta hai:
#
#   <span id="ctl00_ContentPlaceHolder1_lbl_msr" ...>No Muster Roll Available</span>
#   <input id="ctl00_ContentPlaceHolder1_lbl_person_days" value="0" ...>
#
# Matlab: ya to eMB pehle ho chuka hai, ya MR abhi tak us login me aaya nahi.
# Dono me se koi bhi FAILURE nahi hai — warna admin panel me error spike
# dikhta hai.

NO_MR = "No Muster Roll Available"


def test_no_muster_roll_is_skipped_not_failed():
    tab = run(Page(PERIODS, persondays="0", msr_text=NO_MR))

    assert [r[0] for r in tab.results] == ["Skipped", "Skipped"]
    assert all("muster roll" in r[1].lower() for r in tab.results), tab.results


def test_no_muster_roll_reason_is_distinct_from_zero_persondays():
    """Dono skip hain par wajah alag — admin/user ko pata chalna chahiye."""
    no_mr = run(Page(PERIODS[:1], persondays="0", msr_text=NO_MR)).results[0][1]
    zero_pd = run(Page(PERIODS[:1], persondays="0", msr_text="MR-123")).results[0][1]

    assert no_mr != zero_pd
    assert "muster roll" in no_mr.lower()
    assert "personday" in zero_pd.lower()


def test_no_muster_roll_logs_no_error_line():
    tab = run(Page(PERIODS, persondays="0", msr_text=NO_MR))
    assert not [m for m in tab.logs if "Script Error" in m or "Error on" in m]


def test_blank_persondays_is_skipped_not_script_error():
    """Value kabhi bhari hi na ho — 25s timeout ke baad 'Script Error' nahi."""
    tab = run(Page(PERIODS[:1], persondays="", msr_text=NO_MR))

    assert [r[0] for r in tab.results] == ["Skipped"]
    assert not [m for m in tab.logs if "Script Error" in m]


def test_real_muster_roll_is_not_skipped_as_no_mr():
    """Asli MR number ko galti se 'no muster roll' na samjhe."""
    tab = run(Page(PERIODS[:1], persondays="0", msr_text="3404003001/MR/123456"))
    assert "muster roll" not in tab.results[0][1].lower()


# ── _is_no_muster_roll helper ──────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "No Muster Roll Available",
    "no muster roll available",
    "  No   Muster  Roll   Available  ",
    "NO MUSTEROLL AVAILABLE",
])
def test_no_muster_roll_detected(text):
    assert mb_entry_tab._is_no_muster_roll(text) is True


@pytest.mark.parametrize("text", ["", None, "-", "3404003001/MR/123456", "MR-123"])
def test_real_values_not_flagged(text):
    assert mb_entry_tab._is_no_muster_roll(text) is False


# ══════════════════════════════════════════════════════════════════════════
# C. Result row tagging — Skipped ko 'failed' tag nahi milna chahiye
# ══════════════════════════════════════════════════════════════════════════

class TagCapturingTab:
    _log_result = MbEntryTab._log_result

    def __init__(self):
        self.rows = []

    def safe_tree_insert(self, values, tags=()):
        self.rows.append((values, tags))


@pytest.mark.parametrize("status,expected", [
    ("Success", ("success",)),
    ("success", ("success",)),
    ("Skipped", ("skipped",)),
    ("skipped", ("skipped",)),
    ("Failed", ("failed",)),
    ("Script Error", ("failed",)),
])
def test_result_row_tags(status, expected):
    tab = TagCapturingTab()
    tab._log_result({"location_panchayat": "BAGHCHATTA"}, "WC/1", status, "details")
    assert tab.rows[0][1] == expected
