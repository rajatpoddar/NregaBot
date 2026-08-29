"""Characterization tests for ``src.managers.browser_manager.BrowserManager``.

We exercise only the GUI-free surface:
  * ``__init__`` — initial state and the WDM_LOG env-var side effect.
  * ``clear_thread_choice()`` — per-thread cache eviction.
  * ``_thread_browser_choice`` — thread isolation of the dict.
  * ``connect_driver_no_dialog()`` — for chrome / edge / firefox / no-browser.
  * ``resolve_automation_tab()`` — pinned-handle reuse + fallback.
  * ``apply_automation_marker``, ``keep_tab_active``,
    ``_inject_persistent_marker`` — must swallow driver exceptions.

We do NOT test ``get_driver()`` because it contains a Tk modal dialog
(``self.app.wait_window(dialog)``) that would block a headless test.

The tests use a local ``FakeDriver`` class (defined at the top of this
file) rather than importing from ``conftest.py`` to keep the
characterization self-contained and to avoid test-order coupling.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from src.managers.browser_manager import _CANCELLED_CHOICE, BrowserManager

# ---------------------------------------------------------------------------
# Test-local FakeDriver. Mirrors only the surface the tested methods use:
#   * window_handles (property)
#   * switch_to.window(handle) — returns self
#   * execute_script(js) — for "return location.href" returns the href
#     mapped to the handle that was last switched to (stored in _last_handle)
#   * execute_cdp_cmd(cmd, payload) — records the call
# ---------------------------------------------------------------------------

class _FakeDriver:
    """Minimal stand-in for a Selenium WebDriver used by these tests."""

    def __init__(
        self,
        window_handles: list[str] | None = None,
        current_window_handle: str = "h0",
        location_hrefs: dict[str, str] | None = None,
    ) -> None:
        self._window_handles: list[str] = (
            list(window_handles) if window_handles is not None else []
        )
        self._last_handle: str = current_window_handle
        self._location_hrefs: dict[str, str] = location_hrefs or {}
        self.scripts: list[str] = []
        self.cdp_calls: list[tuple[str, dict[str, Any]]] = []
        self.switches: list[str] = []

    @property
    def window_handles(self) -> list[str]:
        return list(self._window_handles)

    def switch_to(self) -> _FakeDriver:
        return self

    def window(self, handle: str) -> _FakeDriver:
        self.switches.append(handle)
        self._last_handle = handle
        return self

    def execute_script(self, js: str) -> str:
        self.scripts.append(js)
        if "location.href" in js:
            return self._location_hrefs.get(self._last_handle, "")
        return ""

    def execute_cdp_cmd(self, cmd: str, payload: dict[str, Any]) -> None:
        self.cdp_calls.append((cmd, payload))


class _RaisingDriver:
    """A driver whose every method raises. Used to verify the marker hooks
    swallow exceptions."""

    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc or RuntimeError("driver unavailable")
        self.calls: list[str] = []

    def execute_script(self, js: str) -> None:
        self.calls.append("execute_script")
        raise self._exc

    def execute_cdp_cmd(self, cmd: str, payload: dict[str, Any]) -> None:
        self.calls.append(f"execute_cdp_cmd:{cmd}")
        raise self._exc

    def switch_to(self) -> _RaisingDriver:
        return self

    def window(self, handle: str) -> _RaisingDriver:
        self.calls.append(f"window:{handle}")
        raise self._exc

    @property
    def window_handles(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager() -> BrowserManager:
    return BrowserManager(None)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestBrowserManagerInit:
    """``BrowserManager.__init__`` (browser_manager.py:52-70)."""

    def test_initial_driver_is_none(self) -> None:
        bm = _make_manager()
        assert bm.driver is None

    def test_initial_active_browser_is_none(self) -> None:
        bm = _make_manager()
        assert bm.active_browser is None

    def test_initial_thread_browser_choice_is_empty_dict(self) -> None:
        bm = _make_manager()
        assert bm._thread_browser_choice == {}
        assert isinstance(bm._thread_browser_choice, dict)

    def test_initial_preferred_browser_is_none(self) -> None:
        bm = _make_manager()
        assert bm.preferred_browser is None

    def test_initial_automation_tab_handle_is_none(self) -> None:
        bm = _make_manager()
        assert bm._automation_tab_handle is None

    def test_init_sets_wdm_log_env_to_zero(self) -> None:
        # Per browser_manager.py:70: ``os.environ['WDM_LOG'] = '0'``.
        # The autouse ``_isolate_wdm_log`` fixture (in conftest.py)
        # deletes the var before this test.
        _make_manager()
        assert os.environ.get("WDM_LOG") == "0"

    def test_init_stores_app_reference(self) -> None:
        bm = _make_manager()
        assert bm.app is None

    def test_init_creates_independent_dict_per_instance(self) -> None:
        bm1 = _make_manager()
        bm2 = _make_manager()
        bm1._thread_browser_choice[12345] = "chrome"
        assert 12345 not in bm2._thread_browser_choice


# ---------------------------------------------------------------------------
# clear_thread_choice — per-thread eviction
# ---------------------------------------------------------------------------

class TestClearThreadChoice:
    """``clear_thread_choice()`` (browser_manager.py:671-677)."""

    def test_clears_current_thread_entry(self) -> None:
        bm = _make_manager()
        my_tid = threading.get_ident()
        bm._thread_browser_choice[my_tid] = "chrome"
        bm.clear_thread_choice()
        assert my_tid not in bm._thread_browser_choice

    def test_preserves_other_thread_entries(self) -> None:
        bm = _make_manager()
        my_tid = threading.get_ident()
        other_tid = my_tid + 1 if my_tid != 2**63 else my_tid - 1
        bm._thread_browser_choice[my_tid] = "chrome"
        bm._thread_browser_choice[other_tid] = "firefox"
        bm.clear_thread_choice()
        assert my_tid not in bm._thread_browser_choice
        assert bm._thread_browser_choice[other_tid] == "firefox"

    def test_no_op_when_current_thread_not_in_dict(self) -> None:
        bm = _make_manager()
        bm.clear_thread_choice()
        assert bm._thread_browser_choice == {}

    def test_clears_cancelled_choice_sentinel(self) -> None:
        bm = _make_manager()
        my_tid = threading.get_ident()
        bm._thread_browser_choice[my_tid] = _CANCELLED_CHOICE
        bm.clear_thread_choice()
        assert my_tid not in bm._thread_browser_choice

    def test_call_from_one_thread_does_not_affect_another(self) -> None:
        bm = _make_manager()
        results = {}
        ready_a = threading.Event()
        ready_b = threading.Event()

        def thread_a() -> None:
            my_tid = threading.get_ident()
            bm._thread_browser_choice[my_tid] = "chrome"
            ready_a.set()
            ready_b.wait(timeout=1.0)
            bm.clear_thread_choice()
            results["a_after_clear"] = my_tid in bm._thread_browser_choice

        def thread_b() -> None:
            my_tid = threading.get_ident()
            ready_a.wait(timeout=1.0)
            bm._thread_browser_choice[my_tid] = "edge"
            ready_b.set()
            threading.Event().wait(0.05)
            results["b_preserved"] = my_tid in bm._thread_browser_choice

        ta = threading.Thread(target=thread_a)
        tb = threading.Thread(target=thread_b)
        ta.start(); tb.start()
        ta.join(timeout=2.0); tb.join(timeout=2.0)
        assert results["a_after_clear"] is False
        assert results["b_preserved"] is True


# ---------------------------------------------------------------------------
# _thread_browser_choice — basic properties of the dict
# ---------------------------------------------------------------------------

class TestThreadBrowserChoiceDict:
    """The dict ``_thread_browser_choice`` itself."""

    def test_dict_supports_per_thread_keys(self) -> None:
        bm = _make_manager()
        bm._thread_browser_choice[1] = "chrome"
        bm._thread_browser_choice[2] = "edge"
        bm._thread_browser_choice[3] = "firefox"
        assert bm._thread_browser_choice[1] == "chrome"
        assert bm._thread_browser_choice[2] == "edge"
        assert bm._thread_browser_choice[3] == "firefox"

    def test_dict_keyed_by_get_ident_is_an_int(self) -> None:
        bm = _make_manager()
        tid = threading.get_ident()
        assert isinstance(tid, int)
        bm._thread_browser_choice[tid] = "chrome"
        assert threading.get_ident() in bm._thread_browser_choice


# ---------------------------------------------------------------------------
# connect_driver_no_dialog
# ---------------------------------------------------------------------------

class TestConnectDriverNoDialog:
    """``connect_driver_no_dialog()`` (browser_manager.py:418-433)."""

    def test_chrome_returns_driver_and_owns_session_true(self) -> None:
        bm = _make_manager()
        bm.active_browser = "chrome"
        sentinel_driver = object()
        bm._connect_external = lambda browser, port: sentinel_driver  # type: ignore[method-assign]
        d, owns = bm.connect_driver_no_dialog()
        assert d is sentinel_driver
        assert owns is True

    def test_edge_returns_driver_and_owns_session_true(self) -> None:
        bm = _make_manager()
        bm.active_browser = "edge"
        sentinel_driver = object()
        bm._connect_external = lambda browser, port: sentinel_driver  # type: ignore[method-assign]
        d, owns = bm.connect_driver_no_dialog()
        assert d is sentinel_driver
        assert owns is True

    def test_firefox_with_driver_returns_driver_and_owns_session_false(self) -> None:
        bm = _make_manager()
        sentinel_driver = object()
        bm.driver = sentinel_driver
        bm.active_browser = "firefox"
        d, owns = bm.connect_driver_no_dialog()
        assert d is sentinel_driver
        assert owns is False

    def test_firefox_with_none_driver_returns_none(self) -> None:
        bm = _make_manager()
        bm.driver = None
        bm.active_browser = "firefox"
        called = []
        bm._connect_external = lambda b, p: called.append((b, p))  # type: ignore[method-assign]
        d, owns = bm.connect_driver_no_dialog()
        assert d is None
        assert owns is False
        assert called == []

    def test_no_active_browser_returns_none(self) -> None:
        bm = _make_manager()
        d, owns = bm.connect_driver_no_dialog()
        assert d is None
        assert owns is False

    def test_unknown_active_browser_returns_none(self) -> None:
        bm = _make_manager()
        bm.active_browser = "firefox_old"
        d, owns = bm.connect_driver_no_dialog()
        assert d is None
        assert owns is False

    def test_chrome_uses_port_9222(self) -> None:
        bm = _make_manager()
        bm.active_browser = "chrome"
        seen: dict[str, Any] = {}
        def fake_connect(browser: str, port: int) -> object:
            seen["browser"] = browser
            seen["port"] = port
            return object()
        bm._connect_external = fake_connect  # type: ignore[method-assign]
        bm.connect_driver_no_dialog()
        assert seen == {"browser": "chrome", "port": 9222}

    def test_edge_uses_port_9223(self) -> None:
        bm = _make_manager()
        bm.active_browser = "edge"
        seen: dict[str, Any] = {}
        def fake_connect(browser: str, port: int) -> object:
            seen["browser"] = browser
            seen["port"] = port
            return object()
        bm._connect_external = fake_connect  # type: ignore[method-assign]
        bm.connect_driver_no_dialog()
        assert seen == {"browser": "edge", "port": 9223}


# ---------------------------------------------------------------------------
# resolve_automation_tab
# ---------------------------------------------------------------------------

class TestResolveAutomationTab:
    """``resolve_automation_tab(driver)`` (browser_manager.py:339-374).

    These tests use a simpler FakeDriver that records the sequence of
    driver calls. The exact ordering of the main-URL probe loop has been
    observed to be flaky under pytest (see commit history); these tests
    characterize the *observable* outputs of the method, not the internal
    call sequence.
    """

    def test_returns_pinned_handle_when_still_open(self) -> None:
        bm = _make_manager()
        bm._automation_tab_handle = "h0"
        d = _FakeDriver(window_handles=["h0", "h1"])
        result = bm.resolve_automation_tab(d)
        assert result == "h0"
        assert bm._automation_tab_handle == "h0"

    def test_returns_none_when_no_tabs(self) -> None:
        bm = _make_manager()
        d = _FakeDriver(window_handles=[])
        result = bm.resolve_automation_tab(d)
        assert result is None

    def test_returns_none_when_pinned_handle_is_none_and_no_tabs(self) -> None:
        bm = _make_manager()
        bm._automation_tab_handle = None
        d = _FakeDriver(window_handles=[])
        assert bm.resolve_automation_tab(d) is None

    def test_falls_back_to_first_handle_when_no_main_url_match(self) -> None:
        # By default FakeDriver returns "" for the location.href query,
        # which does NOT start with MAIN_WEBSITE_URL. So no handle matches
        # and the method falls through to handles[0].
        bm = _make_manager()
        d = _FakeDriver(window_handles=["h0", "h1"])
        result = bm.resolve_automation_tab(d)
        assert result == "h0"
        assert bm._automation_tab_handle == "h0"

    def test_re_pins_when_pinned_handle_is_stale(self) -> None:
        # The user closed the pinned tab → handle is no longer in
        # window_handles. The method should fall through to step (2) or
        # step (3) and update the cached pinned handle.
        bm = _make_manager()
        bm._automation_tab_handle = "stale_handle_not_in_handles"
        d = _FakeDriver(window_handles=["h0", "h1"])
        result = bm.resolve_automation_tab(d)
        assert result == "h0"
        assert bm._automation_tab_handle == "h0"

    def test_does_not_call_execute_script_when_pinned_handle_valid(self) -> None:
        # If step (1) returns, the main-URL probe is skipped. Verify by
        # recording the script calls (which the main-URL probe uses).
        bm = _make_manager()
        bm._automation_tab_handle = "h0"
        d = _FakeDriver(window_handles=["h0", "h1"])
        bm.resolve_automation_tab(d)
        # Step (1) returns early before any switch_to.window / execute_script
        # for the main-URL probe.
        assert d.scripts == [], f"expected no scripts, got {d.scripts}"
        assert d.switches == [], f"expected no switches, got {d.switches}"


# ---------------------------------------------------------------------------
# Marker hooks — must swallow driver exceptions
# ---------------------------------------------------------------------------

class TestMarkerHooksSwallowExceptions:
    """``apply_automation_marker``, ``keep_tab_active``,
    ``_inject_persistent_marker`` are declared "Never raises." Each wraps
    a driver call in ``try/except: pass``.
    """

    def test_apply_automation_marker_swallows_exceptions(self) -> None:
        bm = _make_manager()
        d = _RaisingDriver()
        bm.apply_automation_marker(d)
        assert "execute_script" in d.calls

    def test_keep_tab_active_swallows_exceptions(self) -> None:
        bm = _make_manager()
        d = _RaisingDriver()
        bm.keep_tab_active(d)
        assert any("execute_cdp_cmd" in c for c in d.calls)

    def test_inject_persistent_marker_swallows_exceptions(self) -> None:
        bm = _make_manager()
        d = _RaisingDriver()
        bm._inject_persistent_marker(d)
        assert any("execute_cdp_cmd" in c for c in d.calls)

    def test_apply_automation_marker_with_real_driver_runs_script(self) -> None:
        bm = _make_manager()
        d = _FakeDriver()
        bm.apply_automation_marker(d)
        assert len(d.scripts) == 1
        assert "document.title" in d.scripts[0]

    def test_keep_tab_active_makes_three_cdp_calls(self) -> None:
        bm = _make_manager()
        d = _FakeDriver()
        bm.keep_tab_active(d)
        cdp_cmds = [c[0] for c in d.cdp_calls]
        assert "Page.setWebLifecycleState" in cdp_cmds
        assert "Emulation.setFocusEmulationEnabled" in cdp_cmds
        assert "Emulation.setCPUThrottlingRate" in cdp_cmds

    def test_inject_persistent_marker_uses_add_script_to_evaluate_on_new_document(self) -> None:
        bm = _make_manager()
        d = _FakeDriver()
        bm._inject_persistent_marker(d)
        assert len(d.cdp_calls) == 1
        cmd, payload = d.cdp_calls[0]
        assert cmd == "Page.addScriptToEvaluateOnNewDocument"
        assert "source" in payload
        from src.managers import browser_manager as bm_mod
        assert payload["source"] == bm_mod.AUTOMATION_MARKER_JS




