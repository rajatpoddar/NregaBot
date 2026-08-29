"""Characterization tests for ``src.state.AppState``.

AppState is a ``@dataclass`` (src/state.py) with ``field(default_factory=...)``
for every mutable container. These tests characterize the *defaults* and
verify that mutable containers are independent per instance (the classic
"mutable default argument" bug — which the dataclass correctly avoids via
``default_factory``).

All tests construct the real AppState and read its real attributes. There
is no mocking and no production-code modification.
"""

from __future__ import annotations

import dataclasses
import threading

from src.state import AppState


class TestAppStateLicenseDefaults:
    """The LICENSE & AUTH block (src/state.py:27-55)."""

    def test_is_licensed_default_is_false(self) -> None:
        assert AppState().is_licensed is False

    def test_license_info_default_is_empty_dict(self) -> None:
        assert AppState().license_info == {}

    def test_is_validating_license_default_is_false(self) -> None:
        assert AppState().is_validating_license is False

    def test_global_disabled_features_default_is_empty_list(self) -> None:
        # Per the dataclass declaration: Union[List[str], Dict[str, Any]]
        # default_factory=list.
        assert AppState().global_disabled_features == []

    def test_trial_restricted_features_default_is_empty_list(self) -> None:
        assert AppState().trial_restricted_features == []

    def test_expiry_alert_message_default_is_none(self) -> None:
        assert AppState().expiry_alert_message is None

    def test_open_on_about_tab_default_is_false(self) -> None:
        assert AppState().open_on_about_tab is False

    def test_machine_id_default_is_empty_string(self) -> None:
        assert AppState().machine_id == ""


class TestAppStateAutomationDefaults:
    """The AUTOMATION & BROWSER block (src/state.py:57-83).

    The four mutable containers — ``active_automations`` (set),
    ``automation_threads`` (dict), ``stop_events`` (dict), and
    ``automation_progress`` (dict) — are the load-bearing shared state that
    AutomationMixin, WorkflowManager, and the marker-keeper thread all
    read and write. This block verifies they start empty and are independent
    per instance.
    """

    def test_driver_default_is_none(self) -> None:
        assert AppState().driver is None

    def test_active_browser_default_is_none(self) -> None:
        assert AppState().active_browser is None

    def test_active_automations_default_is_empty_set(self) -> None:
        assert AppState().active_automations == set()
        assert isinstance(AppState().active_automations, set)

    def test_automation_threads_default_is_empty_dict(self) -> None:
        assert AppState().automation_threads == {}

    def test_stop_events_default_is_empty_dict(self) -> None:
        assert AppState().stop_events == {}

    def test_automation_progress_default_is_empty_dict(self) -> None:
        assert AppState().automation_progress == {}

    def test_sleep_prevention_process_default_is_none(self) -> None:
        assert AppState().sleep_prevention_process is None


class TestAppStateUINavigationDefaults:
    """The UI / NAVIGATION block (src/state.py:86-138)."""

    def test_tab_instances_default_is_empty_dict(self) -> None:
        assert AppState().tab_instances == {}

    def test_button_to_category_frame_default_is_empty_dict(self) -> None:
        assert AppState().button_to_category_frame == {}

    def test_category_frames_default_is_empty_dict(self) -> None:
        assert AppState().category_frames == {}

    def test_last_selected_category_default(self) -> None:
        # The default value is documented in the field's docstring as
        # "All Automations" — verify the literal value.
        assert AppState().last_selected_category == "All Automations"

    def test_category_icons_loaded_default_is_empty_set(self) -> None:
        assert AppState()._category_icons_loaded == set()
        assert isinstance(AppState()._category_icons_loaded, set)

    def test_tab_icon_keys_default_is_empty_dict(self) -> None:
        assert AppState()._tab_icon_keys == {}

    def test_tab_icon_map_default_is_empty_dict(self) -> None:
        assert AppState().tab_icon_map == {}

    def test_last_active_nav_default_is_none(self) -> None:
        assert AppState()._last_active_nav is None

    def test_current_active_tab_default_is_none(self) -> None:
        assert AppState().current_active_tab is None

    def test_history_window_default_is_none(self) -> None:
        assert AppState()._history_window is None


class TestAppStateNetworkDefaults:
    """The NETWORK / SESSION block (src/state.py:140-157)."""

    def test_http_session_default_is_none(self) -> None:
        # NregaBotApp.__init__ sets this to a real requests.Session AFTER
        # construction. The dataclass default is None.
        assert AppState().http_session is None

    def test_update_info_default_shape(self) -> None:
        # Per the field's default_factory: {"status": "Checking...",
        # "version": None, "url": None}.
        info = AppState().update_info
        assert info == {
            "status": "Checking...", "version": None, "url": None
        }

    def test_current_toast_default_is_none(self) -> None:
        assert AppState().current_toast is None


class TestAppStateLifecycleDefaults:
    """The INTERNAL / LIFECYCLE block (src/state.py:159-200)."""

    def test_layout_ready_default_is_false(self) -> None:
        assert AppState()._layout_ready is False

    def test_is_resizing_default_is_false(self) -> None:
        assert AppState()._is_resizing is False

    def test_is_theme_transitioning_default_is_false(self) -> None:
        assert AppState()._is_theme_transitioning is False

    def test_resize_timer_default_is_none(self) -> None:
        assert AppState()._resize_timer is None

    def test_resize_overlay_default_is_none(self) -> None:
        assert AppState()._resize_overlay is None

    def test_last_resize_dimensions_default_is_none(self) -> None:
        s = AppState()
        assert s._last_resize_w is None
        assert s._last_resize_h is None

    def test_cached_style_default_is_none(self) -> None:
        assert AppState()._cached_style is None

    def test_gc_timer_id_default_is_none(self) -> None:
        assert AppState()._gc_timer_id is None

    def test_focus_validation_timer_default_is_none(self) -> None:
        assert AppState()._focus_validation_timer is None

    def test_original_messagebox_refs_default_is_none(self) -> None:
        # These three fields store the original tkinter.messagebox methods
        # before any UI override. Default to None.
        s = AppState()
        assert s._original_showinfo is None
        assert s._original_showwarning is None
        assert s._original_showerror is None


class TestAppStateMutableContainersAreIndependent:
    """The most important guarantee: mutable defaults are NOT shared
    between instances.

    The classic Python bug is ``def f(items=[]): items.append(...); ...``
    which leaks state across calls. AppState uses
    ``field(default_factory=set)`` / ``dict`` / ``list`` to avoid that.
    These tests verify the protection works.
    """

    def test_two_instances_have_independent_active_automations_sets(self) -> None:
        s1 = AppState()
        s2 = AppState()
        s1.active_automations.add("mr_fill")
        assert "mr_fill" not in s2.active_automations
        assert s2.active_automations == set()

    def test_two_instances_have_independent_stop_events_dicts(self) -> None:
        s1 = AppState()
        s2 = AppState()
        s1.stop_events["k"] = threading.Event()
        assert "k" not in s2.stop_events
        assert s2.stop_events == {}

    def test_two_instances_have_independent_automation_threads_dicts(self) -> None:
        s1 = AppState()
        s2 = AppState()
        t = threading.Thread(target=lambda: None)
        s1.automation_threads["k"] = t
        assert "k" not in s2.automation_threads
        assert s2.automation_threads == {}

    def test_two_instances_have_independent_automation_progress_dicts(self) -> None:
        s1 = AppState()
        s2 = AppState()
        s1.automation_progress["k"] = 0.42
        assert "k" not in s2.automation_progress
        assert s2.automation_progress == {}

    def test_two_instances_have_independent_license_info_dicts(self) -> None:
        s1 = AppState()
        s2 = AppState()
        s1.license_info["user_name"] = "alice"
        assert "user_name" not in s2.license_info
        assert s2.license_info == {}

    def test_two_instances_have_independent_global_disabled_features(self) -> None:
        # The field type is Union[List[str], Dict[str, Any]] with
        # default_factory=list — so each instance gets its own list.
        s1 = AppState()
        s2 = AppState()
        s1.global_disabled_features.append("Some Tab")
        assert s2.global_disabled_features == []
        assert s2.global_disabled_features is not s1.global_disabled_features

    def test_two_instances_have_independent_update_info_dicts(self) -> None:
        s1 = AppState()
        s2 = AppState()
        s1.update_info["version"] = "3.2.7"
        assert s2.update_info == {
            "status": "Checking...", "version": None, "url": None
        }
        assert s2.update_info is not s1.update_info


class TestAppStateDataclassStructure:
    """Sanity checks on the dataclass itself.

    Not behavior, but a characterization of the *type* so a future field
    rename/remove is caught. A regression here would invalidate every
    mixin that depends on these names.
    """

    def test_appstate_is_a_dataclass(self) -> None:
        assert dataclasses.is_dataclass(AppState)

    def test_field_count(self) -> None:
        # Lock the field count at 47 — a regression guard for accidental
        # field adds/removes during refactors.
        assert len(dataclasses.fields(AppState)) == 47

    def test_specific_fields_exist(self) -> None:
        # Sample of high-traffic fields whose presence is required by
        # AutomationMixin / WorkflowManager / NavMixin.
        names = {f.name for f in dataclasses.fields(AppState)}
        for required in (
            "is_licensed", "license_info",
            "driver", "active_browser", "active_automations",
            "automation_threads", "stop_events", "automation_progress",
            "tab_instances", "last_selected_category",
            "http_session",
        ):
            assert required in names, f"AppState missing field {required!r}"
