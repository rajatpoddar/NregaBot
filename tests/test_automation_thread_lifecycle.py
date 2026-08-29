"""Characterization tests for ``AutomationMixin.start_automation_thread()``.

These tests exercise the **dispatcher and lifecycle** of the method, not
the full Selenium loop. They use a ``_FakeApp`` that:

* Stores all real state in a real ``AppState`` instance.
* Makes ``after(0, cb, *args)`` run the callback **synchronously** so
  the ``on_automation_finished`` handoff is observable within the test.
* Replaces all UI-touching methods with no-op stubs that just record
  the call. This is safe because the production code wraps each of
  these in ``try/except: pass``.

**Threading model under test** (verified against current source at
src/app/app_automation.py:175-379):

* [tk] (caller) executes the dispatcher synchronously up to the point
  where it spawns two daemon threads, then returns.
* [Wn] worker: the ``wrapper`` closure. Runs ``target(*args)``, then
  the ``finally:`` block (L274-307) which schedules
  ``on_automation_finished`` via ``self.after(0, ...)``.
* [Mn] marker-keeper: the ``_marker_keeper`` closure. Loops every 2s
  while the worker is alive OR the key is in ``active_automations``.

**No production code is modified by this test file.**
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

from src.state import AppState

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeHistory:
    """Records every history call. No I/O, no SQLite."""

    def __init__(self) -> None:
        self.starts: list[dict[str, Any]] = []
        self.finishes: list[dict[str, Any]] = []
        self.usages: list[tuple[str, ...]] = []
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
    """BrowserManager stand-in. No Selenium, no network."""

    def __init__(self) -> None:
        self.driver: Any = None
        self.active_browser: str | None = None
        self.clear_thread_choice_calls: int = 0
        self.connect_driver_calls: int = 0

    def clear_thread_choice(self) -> None:
        self.clear_thread_choice_calls += 1

    def connect_driver_no_dialog(self) -> tuple[Any, bool]:
        self.connect_driver_calls += 1
        return (None, False)

    def apply_automation_marker(self, driver: Any) -> None:
        pass

    def keep_tab_active(self, driver: Any) -> None:
        pass


class _FakeServices:
    def prevent_sleep(self) -> None:
        pass

    def allow_sleep(self) -> None:
        pass


class _FakeWorkflows:
    def __init__(self) -> None:
        self.queue_items: list[dict[str, Any]] = []


class _FakeTab:
    """A minimal tab with the attributes the dispatcher reads."""

    def __init__(self) -> None:
        self._has_automated = False
        self.activity_start_time: float | None = None
        self.activity_panchayat: str = ""
        self.activity_village: str = ""
        self.activity_details: str = ""
        self.driver: Any = None
        self.refresh_calls: int = 0
        self.notification_calls: list[str] = []
        # If set, tab.run() raises this exception instead of returning.
        # Used by TestAutomationException to trigger the error path
        # while still providing a real tab_instance to the dispatcher.
        self.run_raises: Exception | None = None

    def _refresh_activity_data(self) -> None:
        self.refresh_calls += 1

    def show_automation_notification(self, status: str) -> None:
        self.notification_calls.append(status)

    def run(self) -> None:
        if self.run_raises is not None:
            raise self.run_raises


class _FakeApp:
    """A minimal stand-in for NregaBotApp."""

    def __init__(self) -> None:
        self.app_state = AppState()
        # The dispatcher reads minimize_var from app_state (line 193).
        self.app_state.minimize_var = SimpleNamespace(
            get=lambda: False, set=lambda v: None
        )
        # Also keep a host-level reference.
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

    def show_toast(self, msg: str, kind: str = "info", duration: int = 3000) -> None:
        self.toast_messages.append((msg, kind))

    def log_message(self, *args: Any, **kwargs: Any) -> None:
        pass

    def after(self, ms: int, cb: Any, *args: Any) -> str | None:
        entry = {"ms": ms, "cb": cb, "args": args, "fired": False}
        self.after_calls.append(entry)
        if ms == 0:
            try:
                entry["fired"] = True
                cb(*args)
            except Exception:  # noqa: BLE001, S110  # mirror production's silent-after pattern
                pass
        return None

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


def _make_automation_mixin(app: _FakeApp):
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
    mixin.app = app  # type: ignore[attr-defined]
    return mixin


def _join_threads(threads, timeout: float = 3.0) -> None:
    """Join each thread with an explicit timeout."""
    for t in threads:
        t.join(timeout=timeout)
        assert not t.is_alive(), (
            f"Thread {t.name!r} did not terminate within {timeout}s. "
            f"Test is leaving a background thread running."
        )


# ===========================================================================
# 1. Dispatcher registration
# ===========================================================================

class TestDispatcherRegistration:
    """``start_automation_thread`` registers state in AppState before
    the worker runs. Verify each registration."""

    def test_adds_key_to_active_automations_during_run(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("mr_fill", target, ())
        assert started.wait(timeout=2.0)
        assert "mr_fill" in app.app_state.active_automations
        proceed.set()
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)

    def test_creates_fresh_stop_event_in_stop_events(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        stale = threading.Event()
        stale.set()
        app.app_state.stop_events["mr_fill"] = stale
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        ev = app.app_state.stop_events["mr_fill"]
        assert ev is not stale
        assert ev.is_set() is False

    def test_creates_no_stop_event_for_other_keys(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "other_key" not in app.app_state.stop_events

    def test_clears_stale_automation_progress(self) -> None:
        app = _FakeApp()
        app.app_state.automation_progress["mr_fill"] = 0.42
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "mr_fill" not in app.app_state.automation_progress

    def test_preserves_progress_for_other_keys(self) -> None:
        app = _FakeApp()
        app.app_state.automation_progress["other_key"] = 0.5
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app.app_state.automation_progress["other_key"] == 0.5

    def test_calls_history_manager_increment_usage(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert ("mr_fill",) in app.history_manager.usages

    def test_calls_services_prevent_sleep(self) -> None:
        app = _FakeApp()
        called = {"n": 0}
        original = app.services.prevent_sleep
        def wrapper() -> None:
            called["n"] += 1
            original()
        app.services.prevent_sleep = wrapper  # type: ignore[method-assign]
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert called["n"] == 1

    def test_plays_start_sound(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "start" in app.sound_calls

    def test_calls_update_emergency_stop_btn(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app._emergency_stop_btn_calls >= 1

    def test_calls_update_running_automation_indicator(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app._running_indicator_calls >= 1

    def test_calls_refresh_all_tab_buttons(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        # Dispatcher (L191) + on_automation_finished (L472) = 2.
        assert app._refresh_all_tab_buttons_calls == 2


# ===========================================================================
# 2. Thread creation
# ===========================================================================

class TestThreadCreation:
    """The dispatcher must create exactly one worker thread and start it."""

    def test_registers_worker_thread_in_automation_threads(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", lambda: None, ())
        assert "mr_fill" in app.app_state.automation_threads
        t = app.app_state.automation_threads["mr_fill"]
        assert isinstance(t, threading.Thread)
        assert t.daemon, "worker thread must be a daemon"

    def test_worker_thread_starts_running(self) -> None:
        app = _FakeApp()
        started = threading.Event()
        proceed = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        t = app.app_state.automation_threads["k"]
        assert t.is_alive()
        proceed.set()
        _join_threads([t], timeout=3.0)

    def test_target_receives_args(self) -> None:
        app = _FakeApp()
        received: list = []
        started = threading.Event()
        def target(a, b, c="default"):
            received.append((a, b, c))
            started.set()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", target, ("x", 42))
        assert started.wait(timeout=2.0)
        t = app.app_state.automation_threads["k"]
        _join_threads([t], timeout=3.0)
        assert received == [("x", 42, "default")]

    def test_target_does_not_receive_key_as_arg(self) -> None:
        # The key is stored in app_state, NOT passed to the target.
        app = _FakeApp()
        received: list = []
        started = threading.Event()
        def target(*args):
            received.append(args)
            started.set()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("some_key", target, ())
        assert started.wait(timeout=2.0)
        t = app.app_state.automation_threads["some_key"]
        _join_threads([t], timeout=3.0)
        assert received == [()]

    def test_re_entry_is_rejected_while_thread_alive(self) -> None:
        app = _FakeApp()
        proceed = threading.Event()
        started = threading.Event()
        def target() -> None:
            started.set()
            proceed.wait(timeout=3.0)
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", target, ())
        assert started.wait(timeout=2.0)
        mixin.start_automation_thread("k", lambda: None, ())
        assert "error" in app.sound_calls
        assert "k" in app.app_state.active_automations
        proceed.set()
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)

    def test_re_entry_succeeds_after_thread_finishes(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        app2 = _FakeApp()
        mixin2 = _make_automation_mixin(app2)
        mixin2.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app2.app_state.automation_threads.values()), timeout=3.0)
        assert len(app.history_manager.usages) >= 1
        assert len(app2.history_manager.usages) >= 1


# ===========================================================================
# 3. Successful completion
# ===========================================================================

class TestSuccessfulCompletion:
    """What happens when ``target(*args)`` returns normally."""

    def test_on_automation_finished_is_scheduled_via_after_zero(self) -> None:
        # Use a bound method so tab_instance is non-None and
        # on_automation_finished reaches the history.log_automation_finish
        # call (L514). With a plain lambda, tab_instance is None and
        # the history call is skipped (L493).
        app = _FakeApp()
        tab = _FakeTab()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        # The synchronous after(0) has fired and the history record exists.
        assert len(app.history_manager.finishes) == 1
        after_zero = [e for e in app.after_calls if e["ms"] == 0]
        assert after_zero

    def test_active_automations_is_empty_after_completion(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "k" not in app.app_state.active_automations

    def test_automation_progress_is_popped_after_completion(self) -> None:
        app = _FakeApp()
        def target() -> None:
            app.app_state.automation_progress["k"] = 0.7
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", target, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "k" not in app.app_state.automation_progress

    def test_status_message_finished_is_shown(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        finished = [m for m in app.status_messages if "finished" in m.lower()]
        assert finished

    def test_history_log_automation_finish_called_with_status_success(self) -> None:
        # Use a bound method (tab.run) so tab_instance is not None
        # and on_automation_finished reaches the history call.
        app = _FakeApp()
        tab = _FakeTab()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert len(app.history_manager.finishes) == 1
        finish = app.history_manager.finishes[0]
        assert finish["automation_key"] == "mr_fill"
        assert finish["status"] == "success"
        assert finish["error_type"] == ""  # on success, error_type is empty string

    def test_history_log_automation_start_called_with_key(self) -> None:
        # log_automation_start is called only when target is a bound
        # method (so tab_instance is not None).
        app = _FakeApp()
        tab = _FakeTab()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("mr_fill", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert len(app.history_manager.starts) == 1
        assert app.history_manager.starts[0]["automation_key"] == "mr_fill"

    def test_allow_sleep_called_when_last_automation_finishes(self) -> None:
        app = _FakeApp()
        called = {"n": 0}
        original = app.services.allow_sleep
        def wrapper() -> None:
            called["n"] += 1
            original()
        app.services.allow_sleep = wrapper  # type: ignore[method-assign]
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert called["n"] == 1


# ===========================================================================
# 4. Automation exception
# ===========================================================================

class TestAutomationException:
    """What happens when ``target(*args)`` raises."""

    def test_target_exception_does_not_propagate_to_caller(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        def target() -> None:
            raise ValueError("simulated failure")
        # Must not raise.
        mixin.start_automation_thread("k", target, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "k" not in app.app_state.active_automations

    def test_status_is_failed_on_exception(self) -> None:
        app = _FakeApp()
        tab = _FakeTab()
        tab.run_raises = RuntimeError("boom")
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert len(app.history_manager.finishes) == 1
        assert app.history_manager.finishes[0]["status"] == "failed"

    def test_error_msg_is_captured_in_finish_log(self) -> None:
        app = _FakeApp()
        tab = _FakeTab()
        tab.run_raises = RuntimeError("the thing failed")
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        finish = app.history_manager.finishes[0]
        # The error_msg is folded into the `details` field with an
        # "ERROR: " prefix (production line 511).
        assert "the thing failed" in finish["details"]
        assert finish["details"].startswith("ERROR: ")

    def test_error_type_is_exception_class_name(self) -> None:
        app = _FakeApp()
        tab = _FakeTab()
        tab.run_raises = ValueError("v")
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        finish = app.history_manager.finishes[0]
        assert finish["error_type"] == "ValueError"

    def test_finally_cleanup_runs_on_exception(self) -> None:
        app = _FakeApp()
        tab = _FakeTab()
        tab.run_raises = RuntimeError("x")
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "k" not in app.app_state.active_automations
        assert "k" not in app.app_state.automation_progress
        assert len(app.history_manager.finishes) == 1

    def test_progress_cleared_even_on_exception(self) -> None:
        app = _FakeApp()
        tab = _FakeTab()
        def before_raise() -> None:
            app.app_state.automation_progress["k"] = 0.3
        # Set up a tab that sets progress and then raises.
        class ProgressThenError(_FakeTab):
            def run(self) -> None:
                before_raise()
                raise RuntimeError("fail after progress set")
        tab = ProgressThenError()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "k" not in app.app_state.automation_progress

    def test_browser_closed_exception_triggers_friendly_toast(self) -> None:
        # The wrapper (line 257-268) checks for known "browser closed"
        # error patterns and shows a friendly toast via
        # self.after(0, lambda: (self.show_toast(...), messagebox...)).
        app = _FakeApp()
        tab = _FakeTab()
        tab.run_raises = RuntimeError("no such window: target window already closed")
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        toasts = [m for m in app.toast_messages if "browser" in m[0].lower()]
        assert toasts, f"expected a browser-closed toast, got {app.toast_messages!r}"

    def test_non_browser_exception_does_not_trigger_friendly_toast(self) -> None:
        app = _FakeApp()
        tab = _FakeTab()
        tab.run_raises = ValueError("not a browser error")
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        toasts = [m for m in app.toast_messages if "browser" in m[0].lower()]
        assert not toasts, f"unexpected browser-closed toast: {toasts!r}"


# ===========================================================================
# 5. Stop event
# ===========================================================================

class TestStopEvent:
    """Characterize what the dispatcher does (and does NOT do) with the
    stop event. The current behavior is: a fresh Event is created on
    every start; the WORKER does not check it; on_automation_finished
    uses it to determine status="stopped" if it was .set().
    """

    def test_dispatcher_creates_a_fresh_event(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        old = threading.Event()
        old.set()
        app.app_state.stop_events["k"] = old
        mixin.start_automation_thread("k", lambda: None, ())
        ev = app.app_state.stop_events["k"]
        assert ev is not old
        assert ev.is_set() is False

    def test_dispatcher_does_not_check_event_in_worker(self) -> None:
        # The wrapper body does NOT consult stop_events[key]. The
        # "stop" is cooperative: target() must check the event itself.
        app = _FakeApp()
        ran_to_completion = threading.Event()
        def target() -> None:
            ran_to_completion.set()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", target, ())
        app.app_state.stop_events["k"].set()
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        # The target ran to completion -- the dispatcher did not
        # interrupt it.
        assert ran_to_completion.is_set()
        assert "k" not in app.app_state.active_automations

    def test_status_is_stopped_when_event_set_and_no_exception(self) -> None:
        # The wrapper itself never raises, but on_automation_finished
        # uses the event to mark "stopped" (line 504). Use a bound
        # method so tab_instance is not None.
        #
        # To avoid a race between the worker finishing and the test
        # setting the event, we use a proceed event that the test
        # controls. The worker blocks on proceed until the test sets
        # the stop event first, then releases proceed.
        app = _FakeApp()
        _FakeTab()
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started = threading.Event()
        def blocking_run() -> None:
            started.set()
            proceed.wait(timeout=2.0)
        # Use a wrapper that mimics tab.run but blocks first.
        class BlockingTab(_FakeTab):
            def run(self) -> None:
                started.set()
                proceed.wait(timeout=2.0)
        blocking_tab = BlockingTab()
        mixin.start_automation_thread("k", blocking_tab.run, ())
        assert started.wait(timeout=2.0)
        # NOW the worker is definitely blocked. Set the stop event.
        app.app_state.stop_events["k"].set()
        # Release the worker.
        proceed.set()
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app.history_manager.finishes[0]["status"] == "stopped"

    def test_status_is_success_when_event_not_set(self) -> None:
        app = _FakeApp()
        tab = _FakeTab()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app.history_manager.finishes[0]["status"] == "success"

    def test_clear_thread_choice_is_called_twice_per_run(self) -> None:
        # Per the wrapper (line 224 and line 278), clear_thread_choice
        # is called both at the start and at the end of the wrapper.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app.browser_manager.clear_thread_choice_calls == 2


# ===========================================================================
# 6. Multiple automation keys
# ===========================================================================

class TestMultipleKeys:
    """Verify that independent keys do not accidentally overwrite each
    other's bookkeeping. Use deterministic fakes and synchronization."""

    def test_two_keys_have_independent_active_automations(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        proceed_a = threading.Event()
        proceed_b = threading.Event()
        started_a = threading.Event()
        started_b = threading.Event()
        def target_a() -> None:
            started_a.set()
            proceed_a.wait(timeout=3.0)
        def target_b() -> None:
            started_b.set()
            proceed_b.wait(timeout=3.0)
        mixin.start_automation_thread("a", target_a, ())
        mixin.start_automation_thread("b", target_b, ())
        assert started_a.wait(timeout=2.0)
        assert started_b.wait(timeout=2.0)
        assert "a" in app.app_state.active_automations
        assert "b" in app.app_state.active_automations
        assert "a" in app.app_state.automation_threads
        assert "b" in app.app_state.automation_threads
        assert app.app_state.automation_threads["a"] is not app.app_state.automation_threads["b"]
        assert "a" in app.app_state.stop_events
        assert "b" in app.app_state.stop_events
        assert app.app_state.stop_events["a"] is not app.app_state.stop_events["b"]
        proceed_a.set()
        proceed_b.set()
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)

    def test_finishing_one_key_does_not_remove_other(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        proceed_b = threading.Event()
        started_b = threading.Event()
        tab_a = _FakeTab()
        def target_b() -> None:
            started_b.set()
            proceed_b.wait(timeout=3.0)
        mixin.start_automation_thread("a", tab_a.run, ())
        mixin.start_automation_thread("b", target_b, ())
        assert started_b.wait(timeout=2.0)
        # Wait for "a" to finish.
        a_thread = app.app_state.automation_threads["a"]
        a_thread.join(timeout=2.0)
        assert not a_thread.is_alive()
        assert "a" not in app.app_state.active_automations
        assert "b" in app.app_state.active_automations
        a_finishes = [f for f in app.history_manager.finishes if f["automation_key"] == "a"]
        assert len(a_finishes) == 1
        b_finishes = [f for f in app.history_manager.finishes if f["automation_key"] == "b"]
        assert len(b_finishes) == 0
        proceed_b.set()
        _join_threads([app.app_state.automation_threads["b"]], timeout=3.0)

    def test_clearing_progress_for_one_key_does_not_clear_others(self) -> None:
        app = _FakeApp()
        app.app_state.automation_progress["other"] = 0.5
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app.app_state.automation_progress["other"] == 0.5
        assert "k" not in app.app_state.automation_progress

    def test_stale_stop_event_for_other_key_is_preserved(self) -> None:
        # The dispatcher creates a fresh event for the new key, but
        # does NOT touch other keys' events.
        app = _FakeApp()
        old = threading.Event()
        old.set()
        app.app_state.stop_events["other"] = old
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert app.app_state.stop_events["other"] is old
        assert app.app_state.stop_events["other"].is_set()

    def test_each_key_has_its_own_thread(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        proceed = threading.Event()
        started_a = threading.Event()
        started_b = threading.Event()
        def target_a() -> None:
            started_a.set()
            proceed.wait(timeout=3.0)
        def target_b() -> None:
            started_b.set()
            proceed.wait(timeout=3.0)
        mixin.start_automation_thread("a", target_a, ())
        mixin.start_automation_thread("b", target_b, ())
        assert started_a.wait(timeout=2.0)
        assert started_b.wait(timeout=2.0)
        ta = app.app_state.automation_threads["a"]
        tb = app.app_state.automation_threads["b"]
        assert ta is not tb
        assert ta.is_alive() and tb.is_alive()
        proceed.set()
        _join_threads([ta, tb], timeout=3.0)

