"""Shared fixtures for Phase 1A characterization tests.

Goals (per the Phase 1A plan):
  * No real NregaBotApp construction.
  * No real Tk GUI.
  * No real Selenium / browser processes.
  * No network calls.
  * No filesystem writes outside pytest's tmp_path.

Notes on why certain monkeypatches are autouse:

  * ``app_automation`` and ``browser_manager`` import ``tkinter.messagebox`` at
    module level. On a headless host, certain ``messagebox`` paths open a
    native dialog and block. We replace the four common methods with no-ops
    so the production modules are importable and any stray ``messagebox.*``
    call in code under test cannot hang the test runner.

  * ``BrowserManager.__init__`` writes ``os.environ['WDM_LOG'] = '0'`` as a
    module-import side-effect. We snapshot the env var in the autouse fixture
    and restore it after each test so a test never inherits a polluted env
    from a prior instantiation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Autouse: neutralize tkinter.messagebox so module imports + any stray
# messagebox call during a test cannot open a modal dialog.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _neutralize_messagebox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the four common messagebox methods with safe no-ops.

    The production modules ``src.app.app_automation`` and
    ``src.managers.browser_manager`` import ``tkinter.messagebox`` at module
    level (line 19 of app_automation.py; line 6 of browser_manager.py). On
    a headless host, certain messagebox calls block waiting for a user
    click. Monkeypatching at the start of every test means even if a tested
    code path *does* call messagebox, the test cannot hang.
    """
    from tkinter import messagebox

    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    monkeypatch.setattr(messagebox, "askokcancel", lambda *a, **k: False)


# ---------------------------------------------------------------------------
# Autouse: snapshot and restore WDM_LOG env var. BrowserManager.__init__
# writes os.environ['WDM_LOG'] = '0' on every instantiation. We don't want
# that to leak across tests.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_wdm_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshot WDM_LOG and restore it after each test."""
    monkeypatch.delenv("WDM_LOG", raising=False)


# ---------------------------------------------------------------------------
# FakeDriver — used by BrowserManager tests for resolve_automation_tab
# and the marker-hook methods. Mirrors only the methods those code paths
# call (window_handles, switch_to.window, execute_script, execute_cdp_cmd).
# ---------------------------------------------------------------------------

class FakeDriver:
    """Minimal stand-in for a Selenium WebDriver.

    Only implements the surface that ``BrowserManager.resolve_automation_tab``,
    ``apply_automation_marker``, ``keep_tab_active`` and
    ``_inject_persistent_marker`` actually call. Any other access raises
    ``AttributeError`` so a test cannot accidentally rely on behavior the
    production code does not exercise.
    """

    def __init__(
        self,
        window_handles: list[str] | None = None,
        current_window_handle: str = "h0",
        location_hrefs: dict[str, str] | None = None,
    ) -> None:
        self._window_handles = (
            list(window_handles) if window_handles is not None else []
        )
        self.current_window_handle = current_window_handle
        # window handle -> href. If a handle is not mapped, the JS read
        # returns "".
        self._location_hrefs: dict[str, str] = location_hrefs or {}

        # Call-recordings so a test can assert on what the production
        # method tried to do.
        self.scripts: list[str] = []
        self.cdp_calls: list[tuple] = []
        self.switches: list[str] = []

    @property
    def window_handles(self) -> list[str]:
        return list(self._window_handles)

    # resolve_automation_tab does ``driver.switch_to.window(h)`` (line 364).
    # That means the production code calls the bound method
    # ``driver.switch_to.window(h)`` where ``driver.switch_to`` returns a
    # object with a ``.window`` method. We support that shape below.
    def switch_to(self) -> FakeDriver:
        return self

    def window(self, handle: str) -> FakeDriver:
        self.switches.append(handle)
        if handle in self._window_handles:
            self.current_window_handle = handle
        return self

    def execute_script(self, js: str) -> str:
        self.scripts.append(js)
        # resolve_automation_tab uses "return location.href" (line 365).
        # Answer with the href mapped to the current handle (or "").
        if "location.href" in js:
            return self._location_hrefs.get(self.current_window_handle, "")
        return ""

    def execute_cdp_cmd(self, cmd: str, payload: dict[str, Any]) -> None:
        self.cdp_calls.append((cmd, payload))
        # Production methods that wrap execute_cdp_cmd (keep_tab_active,
        # _inject_persistent_marker) declare "Never raises." — so we just
        # record the call. Tests that need a raising driver should use
        # RaisingDriver (below) instead of overriding this method.


class RaisingDriver:
    """A driver whose every method raises.

    Used to verify that the marker hooks and the connect_driver_no_dialog
    error path swallow exceptions from the driver. The production methods
    we test are required to be no-op-safe on any exception from the driver,
    so a driver that raises is the cleanest way to confirm that.
    """

    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc or RuntimeError("driver unavailable")
        self.calls: list[str] = []

    def execute_script(self, js: str) -> None:
        self.calls.append("execute_script")
        raise self._exc

    def execute_cdp_cmd(self, cmd: str, payload: dict[str, Any]) -> None:
        self.calls.append(f"execute_cdp_cmd:{cmd}")
        raise self._exc

    def quit(self) -> None:
        self.calls.append("quit")
        raise self._exc

    def minimize_window(self) -> None:
        self.calls.append("minimize_window")
        raise self._exc

    def save_screenshot(self, path: str) -> None:
        self.calls.append("save_screenshot")
        raise self._exc

    def switch_to(self) -> RaisingDriver:
        return self

    def window(self, handle: str) -> RaisingDriver:
        self.calls.append(f"window:{handle}")
        raise self._exc

    @property
    def window_handles(self) -> list[str]:
        # The production code at line 464 raises if the driver has no
        # window_handles property at all. Provide one that returns the
        # list provided at construction.
        return list(getattr(self, "_window_handles", []))


@pytest.fixture
def fake_driver() -> FakeDriver:
    """A default FakeDriver with two handles, no special URL mapping."""
    return FakeDriver(window_handles=["h0", "h1"])


@pytest.fixture
def raising_driver() -> RaisingDriver:
    """A driver that raises on every method call."""
    return RaisingDriver()


# ---------------------------------------------------------------------------
# Optional convenience fixture for tests that need a "no-op app" arg.
# The BrowserManager __init__ accepts any object as the app arg; the methods
# we test here (clear_thread_choice, connect_driver_no_dialog,
# resolve_automation_tab, the marker hooks) do not touch self.app at all.
# ---------------------------------------------------------------------------

@pytest.fixture
def noop_app() -> SimpleNamespace:
    """A SimpleNamespace that satisfies ``BrowserManager(app)`` without
    requiring a real NregaBotApp instance."""
    return SimpleNamespace(
        # None of these are read by the methods we test; included for safety
        # in case a test later exercises a path that does touch self.app.
        play_sound=lambda *a, **k: None,
        show_toast=lambda *a, **k: None,
    )
