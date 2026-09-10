"""Tests for ``build_automation_push_payload`` in ``src.app.app_automation``.

Automation finish par desktop companion app ko push bhejta hai
(POST /api/push/automation-complete). Payload yahin banta hai — server par
nahi — kyunki notification ka text user ki bhasha me chahiye aur bhasha
sirf desktop ko pata hai (src/i18n.py, 5 locales).

Function pure hai: dict in / dict out, koi network nahi. `None` ka matlab
"kuch mat bhejo".
"""

from __future__ import annotations

from src.app.app_automation import build_automation_push_payload


class TestWhichRunsNotify:
    def test_stopped_run_sends_nothing(self):
        """User ne khud roka — usse batane ka matlab nahi."""
        assert build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="Rampur",
            status="stopped", duration=12.0, details="Total: 3",
        ) is None

    def test_success_builds_a_payload(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="Rampur",
            status="success", duration=12.0, details="Total: 3",
        )
        assert payload is not None
        assert payload["status"] == "success"
        assert payload["license_key"] == "NB-1"
        assert payload["automation_key"] == "demand"

    def test_failed_builds_a_payload(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="Rampur",
            status="failed", duration=12.0, details="",
        )
        assert payload is not None
        assert payload["status"] == "failed"

    def test_no_license_key_sends_nothing(self):
        """Bina license ke server 401 dega — call hi mat karo."""
        assert build_automation_push_payload(
            license_key="", key="demand", panchayat="Rampur",
            status="success", duration=1.0, details="Total: 3",
        ) is None


class TestNotificationText:
    def test_title_names_the_automation(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="mr_tracking", panchayat="Rampur",
            status="success", duration=5.0, details="",
        )
        assert "MR Tracking" in payload["title"]

    def test_success_and_failure_titles_differ(self):
        ok = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="R",
            status="success", duration=5.0, details="")
        bad = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="R",
            status="failed", duration=5.0, details="")
        assert ok["title"] != bad["title"]

    def test_body_carries_panchayat_and_details(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="Rampur",
            status="success", duration=5.0,
            details="Total: 15 | Success: 12 | Failed: 3",
        )
        assert "Rampur" in payload["body"]
        assert "Total: 15 | Success: 12 | Failed: 3" in payload["body"]

    def test_body_survives_missing_panchayat_and_details(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="",
            status="success", duration=5.0, details="",
        )
        assert isinstance(payload["body"], str)
        assert payload["body"].strip() != ""


class TestDuration:
    def test_seconds_under_a_minute(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="R",
            status="success", duration=42.0, details="")
        assert "42s" in payload["body"]

    def test_minutes_over_a_minute(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="R",
            status="success", duration=150.0, details="")
        assert "2.5m" in payload["body"]

    def test_duration_is_sent_as_a_number(self):
        payload = build_automation_push_payload(
            license_key="NB-1", key="demand", panchayat="R",
            status="success", duration=150.0, details="")
        assert payload["duration_seconds"] == 150.0


class TestSenderGuards:
    """``_push_automation_complete`` — kya asal me network par jata hai.

    Method sirf guard + thread-spawn hai; asli POST daemon thread me hota
    hai. Yahan ye check hota hai ki thread bane hi na jab bhejne ko kuch
    nahi hai (warna har stopped run par ek bekaar thread khulta)."""

    def _fake_app(self, monkeypatch, license_key="NB-1"):
        from types import SimpleNamespace
        from src.app import app_automation

        spawned = []

        class FakeThread:
            def __init__(self, *a, **kw):
                spawned.append(kw.get("target"))

            def start(self):
                pass

        monkeypatch.setattr(app_automation.threading, "Thread", FakeThread)

        app = SimpleNamespace(
            app_state=SimpleNamespace(license_info={"key": license_key}),
        )
        app._push_automation_complete = (
            app_automation.AutomationMixin._push_automation_complete.__get__(app)
        )
        return app, spawned

    def test_stopped_run_spawns_no_thread(self, monkeypatch):
        app, spawned = self._fake_app(monkeypatch)
        app._push_automation_complete("demand", "Rampur", "stopped", 5.0, "")
        assert spawned == []

    def test_missing_license_spawns_no_thread(self, monkeypatch):
        app, spawned = self._fake_app(monkeypatch, license_key="")
        app._push_automation_complete("demand", "Rampur", "success", 5.0, "")
        assert spawned == []

    def test_successful_run_spawns_one_thread(self, monkeypatch):
        app, spawned = self._fake_app(monkeypatch)
        app._push_automation_complete("demand", "Rampur", "success", 5.0, "Total: 3")
        assert len(spawned) == 1
