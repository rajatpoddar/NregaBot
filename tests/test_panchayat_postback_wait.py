"""Panchayat selection ke baad ASP.NET postback ka wait (eMB Entry stall).

Bug (user log, 9 Sep 2026 — JE/Block login):

    [13:43:17] Panchayat dropdown found — Block/PO login.
    [13:43:44] 🔍 Searching for all available works...      <- 27 second gap

`mb_entry_tab` panchayat select hone ke BAAD dropdown ko dobara find karta
tha aur us naye reference ke `staleness_of` ka wait karta tha:

    dd = wait.until(EC.presence_of_element_located((By.ID, ...)))   # naya element
    wait.until(EC.staleness_of(dd))                                  # kabhi True nahi

Selenium ka find_element navigation complete hone ke baad lautta hai, to `dd`
post-postback element hota hai — wo kabhi stale nahi hoga. Isliye wait apna
poora `WebDriverWait(driver, 25)` timeout jala deta tha, har panchayat par.
GP login par status "gp" aata hai aur ye block chalta hi nahi — isliye stall
sirf Block/PO/JE login par dikhta tha.

Fix: staleness ka wait selection se PEHLE wale element reference par ho
(`_wait_for_postback`), aur uska timeout chhota + apna ho.

Ye tests virtual clock use karte hain — real me koi wait nahi hota.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException,
                                        TimeoutException)
from selenium.webdriver.support import expected_conditions as EC

from src.tabs import base_tab
from src.tabs.base_tab import BaseAutomationTab

PANCH_ID = "ctl00_ContentPlaceHolder1_ddl_panch"


# ── Selenium fakes (virtual clock — koi real sleep nahi) ────────────────────

class FakeElement:
    """WebElement stand-in jo detach (stale) ho sakta hai."""

    def __init__(self, name: str, tag: str = "select") -> None:
        self.name = name
        self.tag_name = tag
        self.stale = False

    def _check(self):
        if self.stale:
            raise StaleElementReferenceException(f"{self.name} detached")

    def is_enabled(self):
        self._check()
        return True

    def is_displayed(self):
        self._check()
        return True

    def get_dom_attribute(self, name):
        self._check()
        return None


class FakeDriver:
    """Elements ko id se rakhta hai; `_find_panchayat_dropdown` ke
    comma-joined CSS selector ("#a, #b") ko bhi id me normalize karta hai."""

    def __init__(self, elements: dict) -> None:
        self.elements = dict(elements)

    def _lookup(self, value):
        for part in str(value).split(","):
            el = self.elements.get(part.strip().lstrip("#"))
            if el is not None:
                return el
        return None

    def find_element(self, by, value):
        el = self._lookup(value)
        if el is None:
            raise NoSuchElementException(value)
        return el

    def find_elements(self, by, value):
        el = self._lookup(value)
        return [el] if el is not None else []


class FakeWait:
    """WebDriverWait jaisa, par virtual clock par — `elapsed` assert kar sakte hain."""

    clock = 0.0  # sabhi instances ek hi virtual ghadi share karte hain

    def __init__(self, driver, timeout, poll_frequency=0.5, ignored_exceptions=None):
        self.driver = driver
        self.timeout = float(timeout)
        self.poll = poll_frequency

    def until(self, method, message=""):
        deadline = FakeWait.clock + self.timeout
        while True:
            try:
                value = method(self.driver)
                if value:
                    return value
            except (NoSuchElementException, StaleElementReferenceException):
                pass
            if FakeWait.clock >= deadline:
                raise TimeoutException(message)
            FakeWait.clock += self.poll


class TabUnderTest:
    """BaseAutomationTab ke asli panchayat helpers, bina Tk ke."""

    _find_panchayat_dropdown = BaseAutomationTab._find_panchayat_dropdown
    _select_panchayat_or_skip = BaseAutomationTab._select_panchayat_or_skip
    _read_gp_panchayat = BaseAutomationTab._read_gp_panchayat
    _wait_for_dropdown_options = BaseAutomationTab._wait_for_dropdown_options
    _wait_for_postback = BaseAutomationTab._wait_for_postback
    POSTBACK_WAIT_TIMEOUT = BaseAutomationTab.POSTBACK_WAIT_TIMEOUT

    def __init__(self) -> None:
        self.logs: list[str] = []
        self.app = None
        self.selected: list[str] = []
        self.postback = True          # select par full postback hota hai?
        self.driver: FakeDriver | None = None

    def log_info(self, msg):
        self.logs.append(msg)

    def _record_user_level(self, is_gp_login):
        pass

    def _select_by_text_fuzzy(self, select_element, target_text):
        """Asli select ki jagah: postback simulate karta hai.

        Full postback = purana element detach + naya element DOM me.
        """
        self.selected.append(target_text)
        old = self.driver.elements[PANCH_ID]
        if self.postback:
            old.stale = True
            self.driver.elements[PANCH_ID] = FakeElement("panch-after")
        return True


@pytest.fixture(autouse=True)
def _virtual_clock(monkeypatch):
    FakeWait.clock = 0.0
    monkeypatch.setattr(base_tab, "WebDriverWait", FakeWait)
    monkeypatch.setattr(base_tab.time, "sleep", lambda s: None)


def make_tab(postback: bool = True):
    tab = TabUnderTest()
    tab.postback = postback
    tab.driver = FakeDriver({PANCH_ID: FakeElement("panch-before")})
    return tab


# ── Root cause: purana pattern poora timeout jalata tha ─────────────────────

def test_old_pattern_burns_the_full_caller_timeout():
    """Selection ke BAAD find kiya gaya element kabhi stale nahi hota."""
    tab = make_tab()
    caller_wait = FakeWait(tab.driver, 25)
    status, _ = tab._select_panchayat_or_skip(
        tab.driver, caller_wait, "BAGHCHATTA", [PANCH_ID])
    assert status == "selected" and tab.selected == ["BAGHCHATTA"]

    start = FakeWait.clock
    dd = caller_wait.until(EC.presence_of_element_located(("id", PANCH_ID)))
    with pytest.raises(TimeoutException):
        caller_wait.until(EC.staleness_of(dd))
    assert FakeWait.clock - start >= 25   # user ke log ka ~27s gap


# ── Fix: selection se PEHLE wale reference par wait ─────────────────────────

def test_postback_wait_returns_immediately_on_full_postback():
    tab = make_tab(postback=True)
    caller_wait = FakeWait(tab.driver, 25)
    start = FakeWait.clock

    status, used = tab._select_panchayat_or_skip(
        tab.driver, caller_wait, "BAGHCHATTA", [PANCH_ID], wait_postback=True)

    assert (status, used) == ("selected", "BAGHCHATTA")
    assert FakeWait.clock - start < 2.0, "postback wait ne timeout jala diya"


def test_postback_wait_is_bounded_when_no_full_postback():
    """Partial/AJAX postback: element stale nahi hota — par 25s nahi lagne chahiye."""
    tab = make_tab(postback=False)
    caller_wait = FakeWait(tab.driver, 25)
    start = FakeWait.clock

    status, _ = tab._select_panchayat_or_skip(
        tab.driver, caller_wait, "BAGHCHATTA", [PANCH_ID], wait_postback=True)

    spent = FakeWait.clock - start
    assert status == "selected"
    assert spent <= BaseAutomationTab.POSTBACK_WAIT_TIMEOUT + 1
    assert spent < 25, "caller ke lambe wait par fallback nahi hona chahiye"


def test_default_callers_do_not_wait_for_postback():
    """Baaki 40+ tabs ka behaviour na badle — wait opt-in hai."""
    tab = make_tab(postback=True)
    caller_wait = FakeWait(tab.driver, 25)
    start = FakeWait.clock

    status, _ = tab._select_panchayat_or_skip(
        tab.driver, caller_wait, "BAGHCHATTA", [PANCH_ID])

    assert status == "selected"
    assert FakeWait.clock - start < 1.0


def test_gp_login_never_waits_for_postback():
    """GP login: dropdown hi nahi — postback wait ka sawaal nahi."""
    tab = TabUnderTest()
    tab.driver = FakeDriver({})
    caller_wait = FakeWait(tab.driver, 25)
    start = FakeWait.clock

    status, _ = tab._select_panchayat_or_skip(
        tab.driver, caller_wait, "BAGHCHATTA", [PANCH_ID], wait_postback=True)

    assert status == "gp"
    # sirf dropdown detection ka chhota wait (timeout=3), 25s wala nahi
    assert FakeWait.clock - start <= 4


def test_notfound_skips_postback_wait():
    tab = make_tab(postback=False)
    tab._select_by_text_fuzzy = lambda sel, txt: False
    caller_wait = FakeWait(tab.driver, 25)
    start = FakeWait.clock

    status, _ = tab._select_panchayat_or_skip(
        tab.driver, caller_wait, "NAHI HAI", [PANCH_ID], wait_postback=True)

    assert status == "notfound"
    assert FakeWait.clock - start < 1.0


def test_wait_for_postback_never_raises():
    tab = make_tab()
    assert tab._wait_for_postback(tab.driver, None) is False
