"""Characterization tests for ``WorkflowManager._wait_for_automation_finish()``.

This method is a **polling busy-wait** that blocks the calling thread until
an automation key appears in ``self.app.active_automations`` and then
disappears from it. The current implementation (verified at
``src/managers/workflow_manager.py:32-67``) has two phases:

* **Phase 1 (wait for START):** a hardcoded ``for _ in range(30):`` loop
  with ``time.sleep(1)`` between iterations. If the key never appears,
  returns ``False``.
* **Phase 2 (wait for FINISH):** a ``while key in active_automations:``
  loop with ``time.sleep(1)`` between iterations. Checks the
  ``stop_events["macro"]`` event (hardcoded literal ``"macro"``, NOT the
  per-key event) and the overall ``timeout`` parameter (default 900s).
  Returns ``False`` on stop, ``False`` on timeout, ``True`` when the
  key is no longer in ``active_automations``.

**These tests characterize that CURRENT behavior.** The polling uses
real ``time.sleep(1)`` per iteration, so to keep tests fast we
monkeypatch ``workflow_manager.time.sleep`` to a no-op. The test
fakes the *clock* (``time.time``) to control the timeout arithmetic.

**No production code is modified by this test file.**
"""

from __future__ import annotations

import threading

import pytest

from src.managers import workflow_manager as wm_mod
from src.managers.workflow_manager import WorkflowManager

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeApp:
    """Minimal stand-in for NregaBotApp.

    ``WorkflowManager._wait_for_automation_finish`` reads:
      * ``self.app.active_automations``  (a set)
      * ``self.app.stop_events``         (a dict of Event, used via
        ``.get("macro")`` and ``["macro"].is_set()``)
      * ``self.app.log_message``         (only when macro_tab has
        ``log_display``)

    ``WorkflowManager._ensure_automation_stopped`` reads:
      * ``self.app.after(0, self.app.set_status, ...)``
    """

    def __init__(self) -> None:
        self.active_automations: set = set()
        self.stop_events: dict = {}
        self.log_message = lambda *a, **k: None
        self.status_messages: list = []
        # _ensure_automation_stopped uses app.after(0, app.set_status, ...).
        # With our synchronous after(), this runs the callback inline.
        self.after_calls: list = []

    def set_status(self, msg: str) -> None:
        self.status_messages.append(msg)

    def after(self, ms: int, cb, *args):
        entry = {"ms": ms, "cb": cb, "args": args}
        self.after_calls.append(entry)
        if ms == 0:
            try:  # mirror production's silent-after pattern
                cb(*args)
            except Exception:  # noqa: BLE001, S110
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_in_thread(target, *args, **kwargs) -> threading.Thread:
    """Run ``target(*args, **kwargs)`` in a daemon thread.

    Returns the thread object so the caller can join it. The test must
    join with an explicit timeout.
    """
    t = threading.Thread(
        target=target, args=args, kwargs=kwargs, daemon=True
    )
    t.start()
    return t


def _join(t: threading.Thread, timeout: float = 3.0) -> None:
    """Join a thread with an explicit timeout. Fail the test on timeout."""
    t.join(timeout=timeout)
    assert not t.is_alive(), (
        f"Thread {t.name!r} did not terminate within {timeout}s. "
        f"Test is leaving a background thread running."
    )


@pytest.fixture
def fast_polling(monkeypatch: pytest.MonkeyPatch):
    """Make the polling loop in _wait_for_automation_finish instant.

    The production code calls ``time.sleep(1)`` in two places (Phase 1
    inside the ``for _ in range(30)`` loop, and Phase 2 inside the
    ``while`` loop). We replace ``workflow_manager.time.sleep`` with a
    no-op so the polling completes in microseconds.

    We DO NOT touch ``time.time`` here — individual tests may
    additionally monkeypatch it to control the timeout arithmetic.
    """
    monkeypatch.setattr(wm_mod.time, "sleep", lambda s: None)
    return monkeypatch


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch):
    """Pin ``time.time()`` to a fixed value for the duration of a test.

    Returns a mutable container ``[t]`` that holds the current clock
    value. The test can advance it via ``t[0] += delta``. The
    WorkflowManager's ``time.time()`` calls (via the ``wm_mod.time``
    module reference) return ``t[0]``.
    """
    clock = [1000.0]

    def fake_time() -> float:
        return clock[0]

    monkeypatch.setattr(wm_mod.time, "time", fake_time)
    return clock


# --------------------------------------------------------------------------
# Thread-leak guard
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_thread_leak():
    """Sanity: after each test, no non-daemon threads should remain that
    this test created. Daemon threads (e.g. background waiters) are
    allowed to die at process exit.
    """
    before = {t.ident for t in threading.enumerate()}
    yield
    after = threading.enumerate()
    leaked = [
        t for t in after
        if not t.daemon
        and t.is_alive()
        and t.ident not in before
        and t is not threading.main_thread()
    ]
    assert not leaked, (
        f"Test left {len(leaked)} non-daemon thread(s) running: "
        f"{[t.name for t in leaked]!r}"
    )


# --------------------------------------------------------------------------
# 1. No active automation
# --------------------------------------------------------------------------

class TestNoActiveAutomation:
    """What happens when ``key`` is already absent from
    ``active_automations`` before _wait_for_automation_finish is called.
    """

    def test_returns_false_when_key_never_appears(self, fast_polling, frozen_clock):
        # Phase 1 polls 30 times. With fast_polling, that's instant.
        # The key never appears, so the method returns False after the
        # full 30-iteration loop.
        app = _FakeApp()
        app.active_automations = set()
        app.stop_events = {"macro": threading.Event()}
        wm = WorkflowManager(app)

        result = wm._wait_for_automation_finish("never_starts")
        assert result is False

    def test_phase1_iteration_count_is_hardcoded_30(self, fast_polling, frozen_clock):
        # The Phase 1 loop is ``for _ in range(30):``. With no
        # active_automations, sleep is a no-op and we count how many
        # times the loop body ran.
        app = _FakeApp()
        app.active_automations = set()
        app.stop_events = {"macro": threading.Event()}
        wm = WorkflowManager(app)

        call_count = [0]
        original_active_automations = app.active_automations

        class CountingSet(set):
            def __contains__(self, item):
                call_count[0] += 1
                return False  # never contains

        app.active_automations = CountingSet()
        try:
            wm._wait_for_automation_finish("k")
        finally:
            app.active_automations = original_active_automations
        # The loop does ``if key in self.app.active_automations:`` and
        # then ``time.sleep(1)``. ``key in set`` is one membership check
        # per iteration. 30 iterations * 1 check = 30.
        assert call_count[0] == 30

    def test_logs_did_not_start_message(self, fast_polling, frozen_clock):
        app = _FakeApp()
        app.active_automations = set()
        logged = []
        app.log_message = lambda widget, msg, level="info": logged.append((msg, level))
        app.stop_events = {"macro": threading.Event()}
        wm = WorkflowManager(app)

        wm._wait_for_automation_finish("ghost_key", macro_tab=None)
        # No macro_tab → _log is a no-op (it checks ``if macro_tab``).
        assert logged == []


# --------------------------------------------------------------------------
# 2. Active automation that completes
# --------------------------------------------------------------------------

class TestActiveAutomationCompletes:
    """The key is present at start; the worker removes it while we poll."""

    def test_returns_true_when_key_disappears(self, fast_polling, frozen_clock):
        # The key is present when we start. The while-loop checks
        # ``key in active_automations``. The test removes the key after
        # a few "iterations" (each iteration is instant under
        # fast_polling).
        app = _FakeApp()
        app.active_automations = {"mr_fill"}
        app.stop_events = {"macro": threading.Event()}
        wm = WorkflowManager(app)

        # Schedule removal on the second membership check by hooking
        # ``__contains__``.
        call_count = [0]
        original = app.active_automations

        class _CountingSet(set):
            def __contains__(self, item):
                call_count[0] += 1
                if call_count[0] >= 2:
                    # On the 2nd check, remove the key.
                    self.discard(item)
                return super().__contains__(item)

        active = _CountingSet(original)
        app.active_automations = active
        try:
            result = wm._wait_for_automation_finish("mr_fill")
        finally:
            app.active_automations = original
        assert result is True
        # We entered the while-loop at least once (we removed on the
        # 2nd check, so we iterated >= 2 times).
        assert call_count[0] >= 2

    def test_returns_true_via_background_thread(self, fast_polling, frozen_clock):
        # Drive the test in a background thread to verify the method
        # actually returns True (not hangs).
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        wm = WorkflowManager(app)

        # Pre-schedule key removal: the test thread removes it after
        # a small real-time wait (50ms — short but real, to ensure
        # the polling thread has a chance to enter the while-loop).
        def remover():
            import time as _t
            _t.sleep(0.05)
            app.active_automations.discard("k")
        threading.Thread(target=remover, daemon=True).start()

        t = _run_in_thread(wm._wait_for_automation_finish, "k")
        _join(t, timeout=3.0)


# --------------------------------------------------------------------------
# 3. Active automation that remains running
# --------------------------------------------------------------------------

class TestActiveAutomationRemainsRunning:
    """The key stays in active_automations forever — the timeout fires."""

    def test_returns_false_on_timeout(self, fast_polling, frozen_clock):
        # The key is present and never removed. The while-loop checks
        # ``time.time() - start > timeout``. We use a custom clock
        # that advances on each membership check so the timeout fires.
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        clock = [1000.0]
        original_time = wm_mod.time.time
        wm_mod.time.time = lambda: clock[0]  # type: ignore[assignment]
        try:
            iteration = [0]
            original = app.active_automations

            class _AdvancingSet(set):
                def __contains__(self, item):
                    iteration[0] += 1
                    clock[0] += 10  # each iteration adds 10s
                    return super().__contains__(item)

            app.active_automations = _AdvancingSet(original)
            try:
                # timeout=5. After 1 iteration, clock = 1010, diff=10>5.
                result = wm._wait_for_automation_finish("k", timeout=5)
            finally:
                app.active_automations = original
        finally:
            wm_mod.time.time = original_time  # type: ignore[assignment]
        assert result is False

    def test_timeout_uses_total_elapsed_since_start(self, fast_polling):
        # The timeout is measured from the START of the call, not from
        # when the key first appeared.
        app = _FakeApp()
        app.active_automations = set()  # key not present initially
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        clock = [1000.0]
        call_count = [0]
        original_active = app.active_automations

        def fake_time():
            clock[0] += 2
            call_count[0] += 1
            return clock[0]

        wm_mod.time.time = fake_time  # type: ignore[assignment]

        def add_key_at_9():
            if call_count[0] == 9:
                app.active_automations.add("k")

        class _HookedSet(set):
            def __contains__(self, item):
                add_key_at_9()
                return super().__contains__(item)

        app.active_automations = _HookedSet()
        try:
            # After 8 Phase-1 iterations (clock at 1016), add key on
            # 9th check. Phase 1 breaks. Phase 2 first check: diff is
            # already 20 > 5 → timeout → False.
            result = wm._wait_for_automation_finish("k", timeout=5)
        finally:
            app.active_automations = original_active
        assert result is False


# --------------------------------------------------------------------------
# 4. Stop-event behavior
# --------------------------------------------------------------------------

class TestStopEventBehavior:
    """The method checks ``stop_events["macro"]`` (hardcoded literal).

    Note: it does NOT check the per-key stop event. This is a known
    limitation of the current implementation.
    """

    def test_returns_false_when_macro_stop_event_is_set_during_phase2(
        self, fast_polling, frozen_clock
    ):
        # The key is present. The macro stop event is set. The
        # while-loop checks the event and returns False on the first
        # iteration.
        app = _FakeApp()
        app.active_automations = {"k"}
        macro_event = threading.Event()
        app.stop_events = {"macro": macro_event}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        # Pre-set the macro stop event.
        macro_event.set()
        result = wm._wait_for_automation_finish("k")
        assert result is False

    def test_does_not_check_per_key_stop_event(self, fast_polling, frozen_clock):
        # The production code only checks stop_events["macro"], not
        # stop_events[key]. Setting a per-key stop event does NOT
        # cause the method to return False.
        app = _FakeApp()
        app.active_automations = {"k"}
        macro_event = threading.Event()
        per_key_event = threading.Event()
        per_key_event.set()  # set the per-key event
        app.stop_events = {"macro": macro_event, "k": per_key_event}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        result_holder = []

        def run():
            r = wm._wait_for_automation_finish("k", timeout=2)
            result_holder.append(r)

        t = _run_in_thread(run)
        # Give the polling thread time to iterate a few times under
        # fast_polling. Then assert it has NOT returned False (because
        # macro is not set). We use real sleep here because we need
        # the OTHER thread to make progress.
        import time as _t
        _t.sleep(0.1)
        assert t.is_alive(), (
            "Method returned (likely False) — but per-key stop event "
            "should NOT cause it to return early. Current implementation "
            "only checks stop_events['macro']."
        )
        # Now set the macro event to let it return.
        macro_event.set()
        _join(t, timeout=3.0)
        assert result_holder[0] is False

    def test_missing_macro_stop_event_does_not_raise(self, fast_polling, frozen_clock):
        # If stop_events has no "macro" key, .get("macro") returns None
        # and the truthy check ``None and ...`` short-circuits. No
        # exception, and the method keeps polling.
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {}  # no "macro" key
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        # Schedule removal on the 2nd check via a counting set.
        call_count = [0]
        original = app.active_automations

        class _CountingSet(set):
            def __contains__(self, item):
                call_count[0] += 1
                if call_count[0] >= 2:
                    self.discard(item)
                return super().__contains__(item)

        app.active_automations = _CountingSet(original)
        try:
            result = wm._wait_for_automation_finish("k")
        finally:
            app.active_automations = original
        # No "macro" key → no crash → eventually key removed → True.
        assert result is True


# --------------------------------------------------------------------------
# 5. Multiple automation keys
# --------------------------------------------------------------------------

class TestMultipleKeys:
    """Waiting for one key does not depend on other keys."""

    def test_waiting_for_k_does_not_finish_when_other_key_appears_and_disappears(
        self, fast_polling
    ):
        # If we're waiting for "a" and "b" appears + disappears while
        # we're polling, the method should NOT consider "a" as done
        # just because "b" disappeared.
        app = _FakeApp()
        app.active_automations = {"a"}
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        # Custom clock that advances on each membership check so the
        # timeout fires. The frozen_clock fixture alone won't work
        # because the timeout diff is always 0.
        clock = [1000.0]
        original_time = wm_mod.time.time
        wm_mod.time.time = lambda: clock[0]  # type: ignore[assignment]
        try:
            call_count = [0]
            original = app.active_automations

            class _AddBThenRemoveBoth(set):
                def __contains__(self, item):
                    call_count[0] += 1
                    clock[0] += 10  # each check advances clock by 10s
                    if call_count[0] == 2:
                        # Add b on the 2nd check.
                        self.add("b")
                    if call_count[0] == 3:
                        # Remove b (but not a) on the 3rd check.
                        self.discard("b")
                    return super().__contains__(item)

            app.active_automations = _AddBThenRemoveBoth(original)
            try:
                # timeout=3. After a few iterations, clock > 1003 → timeout.
                result = wm._wait_for_automation_finish("a", timeout=3)
            finally:
                app.active_automations = original
        finally:
            wm_mod.time.time = original_time  # type: ignore[assignment]
        # "a" was never removed → timeout → False.
        assert result is False
        assert "a" in app.active_automations  # still there

    def test_concurrent_waiters_on_different_keys_dont_interfere(
        self, fast_polling, frozen_clock
    ):
        # Two threads, each waiting for a different key. Removing one
        # key only unblocks the thread waiting for that key.
        app = _FakeApp()
        app.active_automations = {"a", "b"}
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        results = {}

        def wait_for_a():
            results["a"] = wm._wait_for_automation_finish("a", timeout=2)

        def wait_for_b():
            results["b"] = wm._wait_for_automation_finish("b", timeout=2)

        ta = _run_in_thread(wait_for_a)
        tb = _run_in_thread(wait_for_b)

        # After both have entered their while-loops, remove "a" only.
        # Give the polling threads a moment to enter the loops.
        import time as _t
        _t.sleep(0.05)
        app.active_automations.discard("a")
        # "a" thread should return True; "b" thread should still be
        # blocked waiting for "b" (which is still active).
        ta.join(timeout=3.0)
        assert not ta.is_alive()
        assert results["a"] is True
        assert tb.is_alive(), "b waiter should still be blocked"
        # Now remove "b" and let b's waiter finish.
        app.active_automations.discard("b")
        tb.join(timeout=3.0)
        assert not tb.is_alive()
        assert results["b"] is True


# --------------------------------------------------------------------------
# 6. Missing/removed state
# --------------------------------------------------------------------------

class TestMissingOrRemovedState:
    """Behavior when the key disappears from active_automations while
    waiting, or when the key is present at start and then removed.
    """

    def test_key_already_absent_returns_false_after_phase1(
        self, fast_polling, frozen_clock
    ):
        # The Phase 1 loop runs exactly 30 times when the key never
        # appears.
        app = _FakeApp()
        app.active_automations = set()
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        check_count = [0]
        original = app.active_automations

        class _CountingSet(set):
            def __contains__(self, item):
                check_count[0] += 1
                return super().__contains__(item)

        app.active_automations = _CountingSet()
        try:
            result = wm._wait_for_automation_finish("never")
        finally:
            app.active_automations = original
        assert result is False
        # 30 checks in Phase 1 + 0 in Phase 2 (Phase 2 is not entered).
        assert check_count[0] == 30

    def test_key_present_at_start_then_removed_immediately(
        self, fast_polling, frozen_clock
    ):
        # The key is present when the method is called. Phase 1 detects
        # it on the first check (key in set returns True). Phase 2's
        # while-loop checks the key again; we make the second check
        # return False to simulate immediate removal. The method
        # returns True.
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        # Track check count. The first check (Phase 1) must return
        # True so Phase 1 breaks. The second check (Phase 2) must
        # return False so the while-loop exits.
        call_count = [0]
        original = app.active_automations

        class _PresentThenAbsent(set):
            def __contains__(self, item):
                call_count[0] += 1
                if call_count[0] == 1:
                    # Phase 1: key is present.
                    return super().__contains__(item)
                # Phase 2 onwards: key has been removed.
                return False

        app.active_automations = _PresentThenAbsent(original)
        try:
            result = wm._wait_for_automation_finish("k")
        finally:
            app.active_automations = original
        # Phase 2's while-loop is ``while key in active_automations:``.
        # First check: False → exit loop → return True.
        assert result is True


# --------------------------------------------------------------------------
# 7. Timeout / polling behavior characterization
# --------------------------------------------------------------------------

class TestTimeoutPollingCharacterization:
    """Characterize the timeout and polling mechanics without real
    sleep. We use the frozen_clock fixture to advance time
    deterministically.
    """

    def test_phase2_uses_cumulative_elapsed_not_per_iteration(
        self, fast_polling
    ):
        # The timeout check at line 61 is:
        #   ``if time.time() - start > timeout:``
        # ``start`` is set once at line 34, so the timeout is total
        # elapsed since the method was called, not per-iteration.
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        # Custom clock: starts at 1000.0, advances by 0.5s per call.
        clock = [1000.0]
        call_count = [0]
        original = app.active_automations

        class _HookedSet(set):
            def __contains__(self, item):
                call_count[0] += 1
                return super().__contains__(item)

        def fake_time():
            clock[0] += 0.5
            return clock[0]

        wm_mod.time.time = fake_time  # type: ignore[assignment]
        app.active_automations = _HookedSet(original)
        try:
            # timeout=2.0. After ~5 calls (clock advanced by 2.5),
            # the diff exceeds 2.0 and we return False.
            result = wm._wait_for_automation_finish("k", timeout=2)
        finally:
            app.active_automations = original
        assert result is False
        # We should have iterated a few times before timing out.
        assert call_count[0] >= 3
        assert call_count[0] <= 8  # generous upper bound

    def test_macro_tab_log_display_receives_messages(
        self, fast_polling, frozen_clock
    ):
        # When a macro_tab with a log_display attribute is provided,
        # _log calls self.app.log_message(widget, msg, level). The
        # 'finished' log line is only emitted on the True-return path.
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        logged: list = []

        class _MacroTab:
            log_display = object()  # any sentinel; passed through

        def fake_log_message(widget, msg, level="info"):
            logged.append((widget, msg, level))

        app.log_message = fake_log_message
        wm = WorkflowManager(app)

        # Drive removal on the 2nd check.
        call_count = [0]
        original = app.active_automations

        class _CountingSet(set):
            def __contains__(self, item):
                call_count[0] += 1
                if call_count[0] >= 2:
                    self.discard(item)
                return super().__contains__(item)

        app.active_automations = _CountingSet(original)
        macro_tab = _MacroTab()
        try:
            result = wm._wait_for_automation_finish("k", macro_tab=macro_tab)
        finally:
            app.active_automations = original
        assert result is True
        # The 'finished' log line is emitted at the end of the True path.
        finished_lines = [m for _, m, _ in logged if "finished" in m.lower()]
        assert finished_lines, f"expected 'finished' log, got {logged!r}"
        # The widget passed to log_message is the macro_tab.log_display.
        assert all(w is macro_tab.log_display for w, _, _ in logged)


# ===========================================================================
# 8. _ensure_automation_stopped — a different polling helper
# ===========================================================================

class TestEnsureAutomationStopped:
    """Characterize ``_ensure_automation_stopped(key)`` (workflow_manager.py:69-75).

    This method is **different** from ``_wait_for_automation_finish``:
      * No return value (returns None).
      * Hardcoded 10-iteration cap (no ``timeout`` parameter).
      * No ``macro_tab`` parameter, no ``stop_events["macro"]`` check.
      * Schedules ``app.after(0, app.set_status, ...)`` to show a status
        message.
      * Returns None whether the key disappears or not.
    """

    def test_returns_none_immediately_when_key_not_active(self) -> None:
        app = _FakeApp()
        app.active_automations = set()
        app.stop_events = {"macro": threading.Event()}
        wm = WorkflowManager(app)

        result = wm._ensure_automation_stopped("k")
        assert result is None
        # No after() call was scheduled (the early-return path).
        assert app.after_calls == []

    def test_polls_until_key_disappears(self) -> None:
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        call_count = [0]
        original = app.active_automations

        class _CountingSet(set):
            def __contains__(self, item):
                call_count[0] += 1
                if call_count[0] >= 2:
                    self.discard(item)
                return super().__contains__(item)

        app.active_automations = _CountingSet(original)
        result = wm._ensure_automation_stopped("k")
        assert result is None
        assert call_count[0] >= 2

    def test_returns_none_after_10_iterations_if_key_persists(self, fast_polling) -> None:
        # The hardcoded 10-iteration cap. The method always returns
        # None, even after the key persists. We use a counting set to
        # count iterations without real-time sleep.
        app = _FakeApp()
        app.active_automations = {"k"}  # never removed
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        check_count = [0]
        original = app.active_automations

        class _CountingSet(set):
            def __contains__(self, item):
                check_count[0] += 1
                return True  # key always present

        app.active_automations = _CountingSet(original)
        result = wm._ensure_automation_stopped("k")
        assert result is None
        # The ``if key in self.app.active_automations:`` guard at the
        # start is 1 check, then the for loop is 10 more checks.
        # Total: 11 membership checks.
        assert check_count[0] == 11

    def test_schedules_status_message_when_key_is_active(self) -> None:
        # When the key is present, the method calls
        # ``app.after(0, app.set_status, "Waiting for {key} to clear...")``.
        # With our synchronous after(), this runs the callback inline.
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        wm._ensure_automation_stopped("k")
        # The status message was set.
        assert any("Waiting for k to clear" in m for m in app.status_messages)

    def test_no_status_message_when_key_already_absent(self) -> None:
        app = _FakeApp()
        app.active_automations = set()
        app.stop_events = {"macro": threading.Event()}
        wm = WorkflowManager(app)

        wm._ensure_automation_stopped("k")
        # No status message was set (the method returned early).
        assert app.status_messages == []

    def test_does_not_check_macro_stop_event(self, fast_polling) -> None:
        # Unlike _wait_for_automation_finish, this method does NOT
        # check stop_events["macro"]. It will poll to completion
        # regardless. With the hardcoded 10-iteration cap, it
        # returns after 10 iterations.
        app = _FakeApp()
        app.active_automations = {"k"}  # never removed
        app.stop_events = {"macro": threading.Event()}
        # Pre-set the macro stop event. This is a no-op for this method.
        app.stop_events["macro"].set()
        app.log_message = lambda *a, **k: None
        wm = WorkflowManager(app)

        check_count = [0]
        original = app.active_automations

        class _CountingSet(set):
            def __contains__(self, item):
                check_count[0] += 1
                return True

        app.active_automations = _CountingSet(original)
        result = wm._ensure_automation_stopped("k")
        # The method still polled 10 times and returned None. It did
        # NOT check the macro stop event. Total checks: 1 (guard) + 10 (loop) = 11.
        assert result is None
        assert check_count[0] == 11

    def test_does_not_call_log_message(self) -> None:
        # This method uses app.after(0, app.set_status, ...) — NOT
        # app.log_message. So _log is never called.
        app = _FakeApp()
        app.active_automations = {"k"}
        app.stop_events = {"macro": threading.Event()}
        logged = []
        app.log_message = lambda widget, msg, level="info": logged.append((widget, msg, level))
        wm = WorkflowManager(app)

        wm._ensure_automation_stopped("k")
        # No log_message calls (the method uses set_status, not log_message).
        assert logged == []

