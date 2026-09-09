"""Result table me galat Work Code dikhta tha (eMB Entry, dropdown mode).

User report (9 Sep 2026): Work Code column me
    3404003001/IF/7080902209915$(IF-Plantatin/Baghchatta/Prabhudayal Kerketta
    ka Aam Bagwani 1.0Acre/6/22-23)
ka display "22-23)" aa raha tha — hona chahiye tha "209915" ('$' se pehle wale
asli workcode ke last 6 digits).

Do wajah, dono theek karni hain:

1. Portal ka <option> ka VALUE hi "workcode$workname" hota hai — dekho
   docs/htm/Measurement Book.htm:

       <option value="3404003001/IF/7080902209915$(IF-Plantatin/.../6/22-23)">

   mb_entry_tab wahi poora value `work_code` maan kar log/result me bhej deta
   tha. Selection ke liye poora value chahiye, par display ke liye sirf '$' se
   pehle wala hissa.

2. `truncate_workcode()` khud bhi galat tha: `WORKCODE_PATTERN.match()` sirf
   SHURUAT match karta hai, par function uske baad POORI string ko '/' se
   split karta tha. To trailing junk wali string par last part "22-23)" nikal
   aata tha. Ab matched group hi use hota hai.
"""

from __future__ import annotations

import pytest

from src.tabs.mb_entry_tab import _parse_work_option
from src.utils import truncate_workcode

# docs/htm/Measurement Book.htm ke asli options
OPT_1 = ("3404003001/IF/7080902209903$(IF-Plantatin/Baghchatta/Yorel Kerketta "
         "ka Aam Bagwani 0.91 Decimil/4/22-23)")
OPT_2 = ("3404003001/IF/7080902209915$(IF-Plantatin/Baghchatta/Prabhudayal Kerketta "
         "ka Aam Bagwani 1.0Acre/6/22-23)")


# ── truncate_workcode: trailing junk se dhokha na khaye ────────────────────

@pytest.mark.parametrize("raw,expected", [
    (OPT_1, "209903"),
    (OPT_2, "209915"),
    ("3404003001/IF/7080902209915", "209915"),
])
def test_workcode_with_trailing_name_truncates_correctly(raw, expected):
    assert truncate_workcode(raw) == expected


def test_plain_workcode_behaviour_unchanged():
    assert truncate_workcode("3420123456/2025/123456") == "123456"
    assert truncate_workcode("3420123456/2025/123456789") == "456789"


def test_non_workcode_still_returned_as_is():
    assert truncate_workcode("ABC-12345678901") == "ABC-12345678901"
    assert truncate_workcode("BR/12/3456") == "BR/12/3456"


# ── _parse_work_option: selection value vs display code ────────────────────

def test_parse_keeps_full_value_for_selection():
    value, _name, _code = _parse_work_option(OPT_2, OPT_2)
    assert value == OPT_2, "dropdown match ke liye poora value chahiye"


def test_parse_returns_clean_workcode_for_display():
    _value, _name, code = _parse_work_option(OPT_2, OPT_2)
    assert code == "3404003001/IF/7080902209915"
    assert "$" not in code


def test_parsed_code_renders_as_six_digits():
    """End-to-end: jo result row me dikhega."""
    _v, _n, code = _parse_work_option(OPT_2, OPT_2)
    assert truncate_workcode(code) == "209915"


def test_parse_extracts_work_name():
    _v, name, _c = _parse_work_option(OPT_2, OPT_2)
    assert "Prabhudayal Kerketta" in name
    assert not name.startswith("3404003001")


def test_option_without_dollar_falls_back_to_value():
    _v, _n, code = _parse_work_option("3404003001/IF/7080902209915", "Some Work")
    assert code == "3404003001/IF/7080902209915"


def test_auto_mb_no_uses_last_four_of_clean_code():
    """Auto MB No = clean workcode ke last 4 digits (galat string se nahi)."""
    _v, _n, code = _parse_work_option(OPT_2, OPT_2)
    assert code[-4:] == "9915"
