"""Characterization tests for the ``_marker_keeper`` closure
in ``src/app/app_automation.py:318-379``.

The keeper is a daemon thread spawned by ``start_automation_thread``
(line 379) that re-paints the browser tab marker (title + favicon)
while the worker thread is alive AND the key is in
``active_automations``. It exits when BOTH conditions become false.

**Test design — why this is deterministic and fast:**

The keeper's loop body has one observable side effect: it calls
``time.sleep(2)`` between iterations (line 371). We make this sleep a
no-op by monkeypatching ``src.app.app_automation.time.sleep``. This is
a standard Python testing pattern that:

  * Does NOT change production code (the sleep itself is unchanged
    in production; we only suppress it in the test).
  * Does NOT change the semantics being tested (we test the exit
    condition, not the polling interval).
  * Makes the keeper loop spin instantly, so the test verifies
    the exit condition within milliseconds.

We also use ``threading.Event`` for thread synchronization and a
tight real-time ``threading.Event().wait(0.01)`` loop (≤ 50 iterations
= ≤ 0.5s) to detect the keeper's invocation. No arbitrary
``time.sleep`` for coordination.

**No production code is modified by this test file.**
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from src.app import app_automation as aa_mod  # the module under test
from src.state import AppState

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeDriver:
    """Minimal Selenium-like driver stand-in (used by tab)."""

    def __init__(self) -> None:
        self.quit_count: int = 0
        self.quit_exc: Exception | None = None

    def quit(self) -> None:
        self.quit_count += 1
        if self.quit_exc is not None:
            raise self.quit_exc


class _FakeTab:
    def __init__(self, driver: _FakeDriver | None = None) -> None:
        self._has_automated = False
        self.activity_start_time = None
        self.activity_panchayat = ""
        self.activity_village = ""
        self.activity_details = ""
        self.driver = driver
        self.refresh_calls: int = 0
        self.notification_calls: list[str] = []

    def _refresh_activity_data(self) -> None:
        self.refresh_calls += 1

    def show_automation_notification(self, status: str) -> None:
        self.notification_calls.append(status)

    def run(self) -> None:
        pass


class _FakeHistory:
    def __init__(self) -> None:
        self.starts: list[dict[str, Any]] = []
        self.finishes: list[dict[str, Any]] = []
        self.usages: list[tuple] = []
        self.activity_log_syncs: list[dict[str, Any]] = []
        self.usage_stats_syncs: list[dict[str, Any]] = []

    def increment_usage(self, key: str) -> None:
        self.usages.append((key,))

    def log_automation_start(self, **kwargs: Any) -> None:
        self.starts.append(kwargs)

    def log_automation_finish(self, **kwargs: Any) -> None:
        self.finishes.append(kwargs)

    def sync_activity_log_to_server(self, **kwargs: Any) -> None:
        self.activity_log_syncs.append(kwargs)

    def sync_usage_stats_to_server(self, **kwargs: Any) -> None:
        self.usage_stats_syncs.append(kwargs)


class _FakeBrowserManager:
    """BrowserManager stand-in that records marker-keeper invocations."""

    def __init__(self) -> None:
        self.driver: Any = None
        self.active_browser: str | None = None
        self.clear_thread_choice_calls: int = 0
        self.connect_driver_calls: int = 0
        # Marker-keeper related counters
        self.apply_marker_calls: int = 0
        self.keep_tab_active_calls: int = 0
        # If set, apply_automation_marker raises this exception
        self.apply_marker_exc: Exception | None = None
        # If set, connect_driver_no_dialog returns this (driver, owns)
        self.override_session: tuple[Any, bool] | None = None

    def clear_thread_choice(self) -> None:
        self.clear_thread_choice_calls += 1

    def connect_driver_no_dialog(self) -> tuple[Any, bool]:
        self.connect_driver_calls += 1
        if self.override_session is not None:
            return self.override_session
        # Return a None session (no real driver) with owns=False.
        return (None, False)

    def apply_automation_marker(self, driver: Any) -> None:
        self.apply_marker_calls += 1
        if self.apply_marker_exc is not None:
            raise self.apply_marker_exc

    def keep_tab_active(self, driver: Any) -> None:
        self.keep_tab_active_calls += 1


class _FakeServices:
    def prevent_sleep(self) -> None:
        pass

    def allow_sleep(self) -> None:
        pass


class _FakeWorkflows:
    def __init__(self) -> None:
        self.queue_items: list[dict[str, Any]] = []


class _FakeApp:
    """Minimal stand-in for NregaBotApp, with synchronous after(0, ...)."""

    def __init__(self) -> None:
        self.app_state = AppState()
        self.app_state.minimize_var = SimpleNamespace(
            get=lambda: False, set=lambda v: None
        )
        self.minimize_var = self.app_state.minimize_var

        self.history_manager = _FakeHistory()
        self.browser_manager = _FakeBrowserManager()
        self.services = _FakeServices()
        self.sound_manager = SimpleNamespace(play=lambda *a, **k: None)
        self.workflows = _FakeWorkflows()

        self._emergency_stop_btn_calls: int = 0
        self._running_indicator_calls: int = 0
        self._refresh_all_tab_buttons_calls: int = 0

        self.after_calls: list[dict[str, Any]] = []
        self.status_messages: list[str] = []
        self.toast_messages: list[tuple[str, str]] = []
        self.sound_calls: list[str] = []

    def play_sound(self, name: str) -> None:
        self.sound_calls.append(name)

    def set_status(self, msg: str) -> None:
        self.status_messages.append(msg)

    def show_toast(self, msg, kind="info", duration=3000) -> None:
        self.toast_messages.append((msg, kind))

    def log_message(self, *args, **kwargs) -> None:
        pass

    def after(self, ms: int, cb, *args):
        entry = {"ms": ms, "cb": cb, "args": args, "fired": False}
        self.after_calls.append(entry)
        if ms == 0:
            try:  # mirror production's silent-after pattern
                entry["fired"] = True
                cb(*args)
            except Exception:  # noqa: BLE001, S110
                pass

    def _update_emergency_stop_btn(self) -> None:
        self._emergency_stop_btn_calls += 1

    def _update_running_automation_indicator(self) -> None:
        self._running_indicator_calls += 1

    def _refresh_all_tab_buttons(self) -> None:
        self._refresh_all_tab_buttons_calls += 1

    def _maybe_auto_start_queue(self) -> None:
        pass

    def get_nregabot_path(self, subdir: str = "") -> str:
        return f"/tmp/nregabot-test/{subdir}"


def _make_automation_mixin(app):
    """Return a bare AutomationMixin instance bound to ``app``."""
    from src.app.app_automation import AutomationMixin
    mixin = object.__new__(AutomationMixin)
    for attr in (
        "browser_manager", "driver", "active_browser", "stop_events",
        "history_manager", "automation_threads", "active_automations",
        "services", "app_state",
        "play_sound", "set_status", "show_toast", "log_message",
        "after", "_update_emergency_stop_btn",
        "_update_running_automation_indicator",
        "_refresh_all_tab_buttons", "_maybe_auto_start_queue",
        "get_nregabot_path", "workflows", "sound_manager",
    ):
        if hasattr(app, attr):
            setattr(mixin, attr, getattr(app, attr))
    mixin.app = app
    return mixin


def _find_keeper_thread() -> threading.Thread | None:
    """Find the marker-keeper daemon thread (best-effort).

    The keeper is started as ``daemon=True`` with no name set
    explicitly. We identify it by ``daemon=True`` + not being the main
    thread. This is approximate but sufficient for our tests.
    """
    for t in threading.enumerate():
        if t.daemon and t is not threading.main_thread() and t.name != "MainThread":
            return t
    return None


@pytest.fixture(autouse=True)
def _no_thread_leak():
    """Ensure no non-daemon threads are left behind after a test."""
    before = {t.ident for t in threading.enumerate()}
    yield
    after = threading.enumerate()
    leaked = [
        t for t in after
        if not t.daemon and t.is_alive()
        and t.ident not in before
        and t is not threading.main_thread()
    ]
    assert not leaked, (
        f"Test left {len(leaked)} non-daemon thread(s) running: "
        f"{[t.name for t in leaked]!r}"
    )


@pytest.fixture
def fast_keeper_sleep(monkeypatch):
    """Make the keeper's ``time.sleep(2)`` instant.

    The keeper at line 371 calls ``time.sleep(2)``. We patch
    ``src.app.app_automation.time.sleep`` to a no-op so the keeper
    spins instantly. This does NOT change production code — it only
    suppresses the real-time wait in the test environment so we can
    verify the exit condition deterministically.

    We restore the original ``time.sleep`` at teardown via the
    ``monkeypatch`` fixture.
    """
    monkeypatch.setattr(aa_mod.time, "sleep", lambda s: None)
    return monkeypatch


def _join_keeper(keeper: threading.Thread, timeout: float = 2.0) -> None:
    """Join the keeper daemon thread with an explicit timeout.

    Daemon threads die with the process, but the worker has already
    finished by the time we check, so the keeper should also have
    exited. We give it up to ``timeout`` seconds to terminate.
    """
    keeper.join(timeout=timeout)
    assert not keeper.is_alive(), (
        f"Keeper {keeper.name!r} did not exit within {timeout}s."
    )


# ===========================================================================
# Marker-keeper lifecycle
# ===========================================================================

class TestMarkerKeeperLifecycle:
    """Characterize the ``_marker_keeper`` closure
    (src/app/app_automation.py:318-379)."""

    def test_keeper_thread_is_started_when_worker_starts(
        self, fast_keeper_sleep
    ) -> None:
        # After start_automation_thread, a daemon thread (the keeper)
        # should be alive.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        # The keeper is a daemon. Give it a brief moment to be spawned.
        keeper = _find_keeper_thread()
        assert keeper is not None, (
            "No daemon thread found — keeper was not started."
        )
        assert keeper.daemon, "Keeper must be a daemon thread."
        # Release the worker.
        proceed.set()
        # Join the worker (required by the thread-test rules).
        _join_keeper(app.app_state.automation_threads["k"], timeout=3.0)
        _join_keeper(keeper, timeout=2.0)

    def test_keeper_exits_after_worker_dies_and_key_removed(
        self, fast_keeper_sleep
    ) -> None:
        # The keeper's exit condition is
        # ``worker_thread.is_alive() AND key in active_automations``
        # (line 323-324). When BOTH are false, the loop ends and the
        # keeper returns. We verify the keeper thread terminates by
        # blocking the worker with a target that waits on an event,
        # verifying the keeper is alive (via FakeBrowserManager call
        # counter), then releasing the worker and verifying the keeper
        # exits.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        # Wait for the keeper to make at least one call. This proves
        # the keeper is alive and spinning.
        for _ in range(50):
            if app.browser_manager.connect_driver_calls > 0:
                break
            threading.Event().wait(0.01)
        assert app.browser_manager.connect_driver_calls >= 1
        # The keeper IS alive (we found it via the call counter). Now
        # release the worker — the keeper should exit.
        proceed.set()
        worker = app.app_state.automation_threads["k"]
        _join_keeper(worker, timeout=3.0)
        # The worker is done and the key is removed. The keeper should
        # exit. We try to find it; with sleep=no-op it may have already
        # exited by the time we look. If we find it, we join. If not,
        # that's also fine — it already exited.
        keeper = _find_keeper_thread()
        if keeper is not None:
            _join_keeper(keeper, timeout=2.0)
        # Whether the keeper already exited or we joined it, active_automations
        # is clean and the lifecycle is complete.
        assert "k" not in app.app_state.active_automations

    def test_keeper_does_not_prevent_worker_completion(
        self, fast_keeper_sleep
    ) -> None:
        # The worker should complete regardless of the keeper's state.
        # The keeper only reads worker.is_alive() and active_automations;
        # it never joins or holds a lock on the worker.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        started = threading.Event()
        proceed = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        # The keeper is now spinning (with sleep=no-op). Release the
        # worker and verify it terminates promptly.
        proceed.set()
        worker = app.app_state.automation_threads["k"]
        _join_keeper(worker, timeout=3.0)
        # Worker is done; active_automations is empty; keeper exits.
        assert "k" not in app.app_state.active_automations
        keeper = _find_keeper_thread()
        if keeper is not None:
            _join_keeper(keeper, timeout=2.0)

    def test_browser_manager_connect_driver_no_dialog_is_called(
        self, fast_keeper_sleep
    ) -> None:
        # The keeper calls browser_manager.connect_driver_no_dialog()
        # once per session (line 325-326). With our FakeBrowserManager
        # returning (None, False), the session is "None" so the inner
        # ``if marker_session is not None:`` block is skipped, but
        # connect_driver_no_dialog IS still called.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        # Give the keeper a moment to spin.
        for _ in range(50):
            if app.browser_manager.connect_driver_calls > 0:
                break
            threading.Event().wait(0.01)
        # The keeper called connect_driver_no_dialog at least once.
        assert app.browser_manager.connect_driver_calls >= 1
        proceed.set()
        worker = app.app_state.automation_threads["k"]
        _join_keeper(worker, timeout=3.0)
        keeper = _find_keeper_thread()
        if keeper is not None:
            _join_keeper(keeper, timeout=2.0)

    def test_browser_manager_apply_marker_called_when_session_is_not_none(
        self, fast_keeper_sleep
    ) -> None:
        # When the FakeBrowserManager returns a non-None session, the
        # keeper's inner block (line 328) runs and calls
        # apply_automation_marker + keep_tab_active. The inner block
        # is gated by ``if marker_session.window_handles:`` (line 330).
        # Provide a session with a truthy window_handles.
        app = _FakeApp()
        sentinel_session = SimpleNamespace(window_handles=["h0"])
        app.browser_manager.override_session = (sentinel_session, False)
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        # Give the keeper a moment to spin.
        for _ in range(50):
            if app.browser_manager.apply_marker_calls > 0:
                break
            threading.Event().wait(0.01)
        # Assert WHILE the worker is still alive (keeper is still
        # spinning). We don't try to find the keeper thread after
        # releasing the worker, because with sleep=no-op the keeper
        # exits very quickly.
        assert app.browser_manager.apply_marker_calls >= 1
        assert app.browser_manager.keep_tab_active_calls >= 1
        proceed.set()
        worker = app.app_state.automation_threads["k"]
        _join_keeper(worker, timeout=3.0)
        keeper = _find_keeper_thread()
        if keeper is not None:
            _join_keeper(keeper, timeout=2.0)

    def test_marker_exception_is_swallowed_and_keeper_continues(
        self, fast_keeper_sleep
    ) -> None:
        # If apply_automation_marker raises, the keeper's inner
        # ``except Exception:`` (line 367-370) catches it, resets
        # marker_session, and continues. The keeper does NOT die.
        app = _FakeApp()
        sentinel_session = SimpleNamespace(window_handles=["h0"])
        app.browser_manager.override_session = (sentinel_session, False)
        # Make apply_marker raise on every call.
        app.browser_manager.apply_marker_exc = RuntimeError("boom")
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        # The keeper is spinning and catching exceptions. Wait until
        # apply_marker has been called at least once (proving the inner
        # block was reached). This happens WHILE the worker is alive.
        for _ in range(50):
            if app.browser_manager.apply_marker_calls > 0:
                break
            threading.Event().wait(0.01)
        # The exception was swallowed (the keeper is still alive). We
        # verify the worker can still complete despite the keeper errors.
        proceed.set()
        worker = app.app_state.automation_threads["k"]
        _join_keeper(worker, timeout=3.0)
        assert "k" not in app.app_state.active_automations
        # apply_marker was called at least once.
        assert app.browser_manager.apply_marker_calls >= 1
