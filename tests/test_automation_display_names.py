"""Characterization tests for ``AUTOMATION_DISPLAY_NAMES`` and
``_automation_display_name`` in ``src.app.app_automation``.

The dict (app_automation.py:34-77) maps every ``automation_key`` (the
string that ``AutomationMixin.start_automation_thread`` uses) to a
human-readable label shown in the footer's "▶ Running: ..." indicator.

The lookup function (line 80-83) is a one-liner:
    ``return AUTOMATION_DISPLAY_NAMES.get(key, key.replace("_", " ").title())``

Tests use the real dict and the real lookup function. No mocking.
"""

from __future__ import annotations

import pytest

from src.app.app_automation import (
    AUTOMATION_DISPLAY_NAMES,
    _automation_display_name,
)


class TestAutomationDisplayNamesDictionary:
    """The dict itself."""

    def test_dict_is_non_empty(self) -> None:
        assert len(AUTOMATION_DISPLAY_NAMES) > 0

    def test_all_values_are_non_empty_strings(self) -> None:
        # The footer's "▶ Running: ..." chip is rendered from this string.
        # An empty value would break the UI.
        for k, v in AUTOMATION_DISPLAY_NAMES.items():
            assert isinstance(v, str), f"value for {k!r} is not str: {type(v)}"
            assert v.strip(), f"empty value for key {k!r}"

    def test_all_keys_are_non_empty_strings(self) -> None:
        # A None or empty key would never match a real automation_key, but
        # we still lock the type for future refactors.
        for k in AUTOMATION_DISPLAY_NAMES:
            assert isinstance(k, str)
            assert k.strip(), "empty key in AUTOMATION_DISPLAY_NAMES"


class TestAutomationDisplayNamesKnownKeys:
    """Specific keys currently in the dict (sourced from
    app_automation.py:34-77). Each pair is verified against the *real*
    dict — these are not invented; they are copied from the source.
    """

    @pytest.mark.parametrize("key,expected", [
        ("pending_bills", "Pending Bills"),
        ("mr_tracking", "MR Tracking"),
        ("issued_mr_report", "Issued MR"),
        ("fto_gen", "FTO Generation"),
        ("fto_gen_del", "FTO Delete"),
        ("nmms_attendance", "NMMS Attendance"),
        ("work_allocation", "Work Allocation"),
        ("gen", "Wagelist"),
        ("mr_fill", "MR Fill"),
        ("emb_verify", "eMB Verify"),
        ("material_entry", "Material Entry"),
        ("mis_reports", "MIS"),
        ("physical_complete", "Physical Complete"),
        ("sad_update_status", "SAD Update"),
        ("add_activity", "Add Activity"),
        ("del_demand", "Delete Demand"),
        ("sad_auto", "Sarkar Aapke Dwar"),
        ("mb_entry", "MB Entry"),
        ("zero_mr", "Zero MR"),
        ("delete_applicant", "Delete Applicant"),
        ("demand", "Demand"),
        ("resend_wg", "Resend Rejected Wagelist"),
        ("update_estimate", "Update Estimate"),
        ("wc_gen", "Work Code Generation"),
        ("send", "Wagelist Send"),
        ("print_wagelist", "Print Wagelist"),
        ("duplicate_mr", "Duplicate MR"),
        ("social_audit_respond", "Social Audit"),
        ("muster", "Muster Roll"),
        ("mate_mr", "Mate MR"),
        ("pdf_merger", "PDF Merger"),
        ("msr", "MR Payment"),
        ("dashboard_report", "Dashboard Report"),
        ("abps_verify", "ABPS Verify"),
        ("if_edit", "IF Edit"),
        ("jc_verify", "Jobcard Verify"),
        ("jobcard_verify", "Jobcard Verify"),
        ("verify_abps", "Verify ABPS"),
        ("del_work_alloc", "Delete Work Allocation"),
        ("macro", "Macro"),
        ("scheme_closing", "Scheme Closing"),
        ("ekyc_report", "eKYC Report"),
    ])
    def test_lookup_for_known_key(self, key: str, expected: str) -> None:
        # These are the *real* values from the dict. If the dict entry is
        # removed or renamed, this test fails — that's the point.
        assert key in AUTOMATION_DISPLAY_NAMES
        assert AUTOMATION_DISPLAY_NAMES[key] == expected

    def test_dict_size_at_least_30(self) -> None:
        # Regression guard. Currently the dict has 42 entries; lock a
        # floor of 30 so a "someone deleted half the dict" refactor is
        # caught immediately.
        assert len(AUTOMATION_DISPLAY_NAMES) >= 30


class TestAutomationDisplayNameLookup:
    """The ``_automation_display_name(key)`` function."""

    def test_known_key_returns_mapped_value(self) -> None:
        # "mr_fill" is a real key. The lookup returns its mapped value.
        assert _automation_display_name("mr_fill") == "MR Fill"

    def test_unknown_key_uses_title_case_fallback(self) -> None:
        # An unknown key falls back to ``key.replace("_", " ").title()``.
        # This is the documented behavior at line 80-83.
        assert _automation_display_name("some_unknown_key") == "Some Unknown Key"

    def test_unknown_single_word_key_uses_title_case_fallback(self) -> None:
        assert _automation_display_name("foobar") == "Foobar"

    def test_empty_string_lookup_returns_empty_string(self) -> None:
        # Edge case: "" is not in the dict. The fallback is
        # "".replace("_", " ").title() = "".title() = "". Characterize it.
        assert _automation_display_name("") == ""

    def test_key_with_consecutive_underscores_keeps_them(self) -> None:
        # The replace is single-pass: "__" stays as "  " in the fallback.
        # "a__b" → "a  b" → "A  B" (title() capitalizes the first letter
        # of each whitespace-separated word, leaves the rest lowercased).
        assert _automation_display_name("a__b") == "A  B"

    def test_known_key_returned_via_lookup_equals_dict_value(self) -> None:
        # Equivalence: the function for known keys must return the dict value.
        for k, v in AUTOMATION_DISPLAY_NAMES.items():
            assert _automation_display_name(k) == v

    def test_lookup_function_returns_a_string(self) -> None:
        # The function must never raise and must always return a string.
        for key in ["", "a", "a_b", "X", "weird key with spaces"]:
            result = _automation_display_name(key)
            assert isinstance(result, str)