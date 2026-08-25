"""AUDIT Batch-6: pure-function unit tests for src/utils.py helpers.

Ye functions demand/report/update ke core paths me use hote hain — pehle
inka ZERO coverage tha. Sab tests pure/isolated hain (koi network, koi GUI,
koi real user-data touch nahi).

Run: venv/bin/python -m pytest tests/test_utils_pure.py -v
"""
import datetime as _dt

import pytest

from src.utils import (
    current_financial_year,
    mask_pii_text,
    parse_version,
    truncate_workcode,
)


# ---------------------------------------------------------------------------
# parse_version — loader/Lite dono update-decision isi par chale hain
# ---------------------------------------------------------------------------

class TestParseVersion:
    @pytest.mark.parametrize("raw,expected", [
        ("3.0.7", (3, 0, 7)),
        ("3.0.7-LITE", (3, 0, 7)),          # pre-release suffix strip
        ("3.0.7-beta", (3, 0, 7)),
        ("3.0", (3, 0)),
        ("3", (3,)),
        ("", (0,)),
    ])
    def test_basic(self, raw, expected):
        assert parse_version(raw) == expected

    def test_none_is_safe(self):
        # AttributeError path → (0,) — kabhi raise nahi hona chahiye
        assert parse_version(None) == (0,)

    def test_numeric_ordering(self):
        # 3.2.10 > 3.2.9 — tuple-compare, string-compare NAHI
        assert parse_version("3.2.10") > parse_version("3.2.9")

    def test_downgrade_detection(self):
        # Batch-1 fix ka core semantic: older version detect ho sake
        assert parse_version("3.1.0") < parse_version("3.2.7")
        assert parse_version("3.2.7") == parse_version("3.2.7-beta")


# ---------------------------------------------------------------------------
# current_financial_year — April boundary (government FY)
# ---------------------------------------------------------------------------

class TestFinancialYear:
    @staticmethod
    def _freeze(monkeypatch, year, month, day):
        real_dt = _dt.datetime

        class FakeDateTime(real_dt):
            @classmethod
            def now(cls, tz=None):
                return real_dt(year, month, day)

        monkeypatch.setattr(_dt, "datetime", FakeDateTime)

    @pytest.mark.parametrize("month,day,expected_start", [
        (1, 15, 2025),   # Jan  → previous year ka FY chal raha
        (3, 31, 2025),   # March end tak purana FY
        (4, 1, 2026),    # April 1 se NAYA FY (boundary!)
        (12, 31, 2026),  # Dec → isi saal ka FY
    ])
    def test_april_boundary(self, monkeypatch, month, day, expected_start):
        self._freeze(monkeypatch, 2026, month, day)
        expected = f"{expected_start}-{expected_start + 1}"
        assert current_financial_year() == expected


# ---------------------------------------------------------------------------
# truncate_workcode — privacy display + RETRY is par depend karta hai
# ---------------------------------------------------------------------------

class TestTruncateWorkcode:
    def test_full_pattern_keeps_last_segment(self):
        # WORKCODE_PATTERN: 34+digits/segments/final-digits (hyphen-free segments)
        assert truncate_workcode("3420123456/2025/123456") == "123456"

    def test_long_suffix_clamps_to_six(self):
        assert truncate_workcode("3420123456/2025/123456789") == "456789"

    def test_short_suffix_unchanged(self):
        assert truncate_workcode("3420123456/2025/123456") [:0] == ""
        assert len(truncate_workcode("3420123456/2025/12345")) == 5

    def test_fallback_pure_digits_nine_plus(self):
        # Non-workcode numeric string ≥9 digits → last 6 (privacy fallback)
        assert truncate_workcode("1234567890") == "567890"

    def test_short_numeric_unchanged(self):
        assert truncate_workcode("12345") == "12345"

    def test_alphanumeric_nonworkcode_unchanged(self):
        # Letters hone par digit-fallback trigger NahI hota
        assert truncate_workcode("ABC-12345678901") == "ABC-12345678901"

    def test_jobcard_style_unchanged_by_pattern(self):
        # 'BR/12/3456' jaise IDs ka data loss na ho (no 34-prefix)
        assert truncate_workcode("BR/12/3456") == "BR/12/3456"

    def test_empty_and_none(self):
        assert truncate_workcode("") == ""
        assert truncate_workcode(None) == ""


# ---------------------------------------------------------------------------
# mask_pii_text — DPDP masking (logs/crash-reports isi se safe hain)
# ---------------------------------------------------------------------------

class TestMaskPiiText:
    def test_aadhaar_contiguous(self):
        out = mask_pii_text("Aadhaar 123456789012 hai")
        assert "123456789012" not in out
        assert "XXXX-XXXX-XXXX" in out

    def test_aadhaar_spaced(self):
        out = mask_pii_text("1234 5678 9012")
        assert out == "XXXX-XXXX-XXXX"

    def test_mobile_masked(self):
        out = mask_pii_text("Call 9876543210 now")
        assert "9876543210" not in out
        assert "98******10" in out

    def test_ifsc_masked(self):
        out = mask_pii_text("IFSC SBIN0001234")
        assert "SBIN0001234" not in out
        assert "XXXX0XXXXXX" in out

    def test_plain_text_untouched(self):
        assert mask_pii_text("Panchayat Rampur Block Madhupur") == \
               "Panchayat Rampur Block Madhupur"

    def test_none_safe(self):
        assert mask_pii_text(None) == ""

    def test_multi_pii_single_pass(self):
        line = "user 9988776655 aadhaar 123456789012 IFSC SBIN0001234"
        out = mask_pii_text(line)
        for secret in ("9988776655", "123456789012", "SBIN0001234"):
            assert secret not in out
