"""Characterization tests for the tab-driver cleanup in the
``AutomationMixin.start_automation_thread()`` wrapper's ``finally:`` block.

The production code at ``src/app/app_automation.py:297-303``:

```python
if tab_instance is not None and hasattr(tab_instance, 'driver'):
    try:
        if tab_instance.driver is not None:
            tab_instance.driver.quit()
    except Exception:
        pass
    tab_instance.driver = None
```

No production code is modified by this test file.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from src.state import AppState

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeDriver:
    """Minimal Selenium-like driver stand-in."""

    def __init__(self) -> None:
        self.quit_count: int = 0
        self.quit_exc: Exception | None = None

    def quit(self) -> None:
        self.quit_count += 1
        if self.quit_exc is not None:
            raise self.quit_exc


class _FakeTab:
    """Minimal tab with a ``driver`` attribute."""

    def __init__(self, driver=None) -> None:
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
    """Records every history call. No I/O, no SQLite."""

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


def _join_threads(threads, timeout=3.0) -> None:
    for t in threads:
        t.join(timeout=timeout)
        assert not t.is_alive(), (
            f"Thread {t.name!r} did not terminate within {timeout}s."
        )


@pytest.fixture(autouse=True)
def _no_thread_leak():
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


# ===========================================================================
# Tab-driver cleanup in wrapper's finally: block
# ===========================================================================

class TestTabDriverCleanup:
    """Characterize ``tab_instance.driver.quit()`` and
    ``tab_instance.driver = None`` in the wrapper's finally: block
    (app_automation.py:297-303)."""

    def test_driver_quit_called_when_driver_exists_on_success(self) -> None:
        # Capture the driver BEFORE the wrapper clears it, so we can
        # verify that quit() was called.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        driver = _FakeDriver()
        tab = _FakeTab(driver=driver)
        # Stash a reference to the driver for later assertion.
        captured_driver = driver
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        # The wrapper called quit() on the original driver.
        assert captured_driver.quit_count == 1
        # The wrapper set tab.driver to None.
        assert tab.driver is None

    def test_driver_set_to_none_after_cleanup_on_success(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        driver = _FakeDriver()
        tab = _FakeTab(driver=driver)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert tab.driver is None

    def test_driver_quit_called_when_target_raises(self) -> None:
        # Target raises. The finally: block should STILL call driver.quit()
        # and set driver = None.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        driver = _FakeDriver()

        class _RaisingTab(_FakeTab):
            def run(inner_self) -> None:
                raise RuntimeError("boom")

        tab = _RaisingTab(driver=driver)
        captured_driver = driver
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        # The wrapper called quit() on the original driver.
        assert captured_driver.quit_count == 1
        # The wrapper set tab.driver to None.
        assert tab.driver is None

    def test_driver_set_to_none_after_cleanup_on_exception(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)

        class _RaisingTab(_FakeTab):
            def run(inner_self) -> None:
                raise RuntimeError("boom")

        tab = _RaisingTab(driver=_FakeDriver())
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert tab.driver is None

    def test_driver_quit_swallows_exception(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        bad_driver = _FakeDriver()
        bad_driver.quit_exc = RuntimeError("quit failed")
        tab = _FakeTab(driver=bad_driver)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert bad_driver.quit_count == 1
        assert tab.driver is None

    def test_no_quit_when_driver_is_none(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        tab = _FakeTab(driver=None)
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert tab.driver is None

    def test_no_quit_when_target_is_lambda(self) -> None:
        # If target is a plain function (not a bound method), there is
        # no tab_instance and the whole cleanup block is skipped.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        mixin.start_automation_thread("k", lambda: None, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "k" not in app.app_state.active_automations
        assert app.history_manager.finishes == []

    def test_no_crash_when_tab_has_no_driver_attribute(self) -> None:
        # If tab_instance exists but has no 'driver' attribute, the
        # whole block is skipped. No AttributeError.
        app = _FakeApp()
        mixin = _make_automation_mixin(app)

        class _NoDriverTab:
            def __init__(inner_self) -> None:
                self._has_automated = False
                self.activity_start_time = None
                self.activity_panchayat = ""
                self.activity_village = ""
                self.activity_details = ""
            def _refresh_activity_data(inner_self) -> None:
                pass
            def show_automation_notification(inner_self, status) -> None:
                pass
            def run(inner_self) -> None:
                pass

        tab = _NoDriverTab()  # no 'driver' attribute
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert "k" not in app.app_state.active_automations

    def test_history_finish_logged_with_status_success(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)
        tab = _FakeTab(driver=_FakeDriver())
        mixin.start_automation_thread("mr_fill", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert len(app.history_manager.finishes) == 1
        finish = app.history_manager.finishes[0]
        assert finish["automation_key"] == "mr_fill"
        assert finish["status"] == "success"
        assert finish["error_type"] == ""
        assert tab.driver is None

    def test_history_finish_logged_with_status_failed_on_exception(self) -> None:
        app = _FakeApp()
        mixin = _make_automation_mixin(app)

        class _RaisingTab(_FakeTab):
            def run(inner_self) -> None:
                raise ValueError("specific error message")

        tab = _RaisingTab(driver=_FakeDriver())
        mixin.start_automation_thread("k", tab.run, ())
        _join_threads(list(app.app_state.automation_threads.values()), timeout=3.0)
        assert len(app.history_manager.finishes) == 1
        finish = app.history_manager.finishes[0]
        assert finish["status"] == "failed"
        assert finish["error_type"] == "ValueError"
        assert "specific error message" in finish["details"]
        assert tab.driver is None
