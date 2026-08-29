"""Characterization tests for ``src.app.app_automation._extract_error_context``.

The function (app_automation.py:86-137) takes an Exception and returns a
4-tuple ``(error_type, error_msg, error_source, error_traceback)`` with
specific caps:
  * ``error_msg`` is capped at 600 chars and PII-masked.
  * ``error_traceback`` is capped at 4000 chars and PII-masked.
  * ``error_source`` is the chain of the last 2 user-code frames
    (site-packages frames are skipped).

These tests exercise the real function on real exceptions. No mocking
of the function itself; only ``src.utils.mask_pii_text`` is called by the
real function and we let it run.
"""

from __future__ import annotations

from src.app.app_automation import _extract_error_context


def _raise_and_capture(exc: BaseException) -> tuple:
    """Raise ``exc`` inside a try/except and return the
    ``_extract_error_context`` result for it. Single-frame stack — used
    by tests that don't care about the call chain.
    """
    try:
        raise exc
    except BaseException as caught:  # noqa: BLE001  # intentional: match production _extract_error_context
        return _extract_error_context(caught)


class TestErrorContextBasicShape:
    """The 4-tuple contract: (error_type, error_msg, error_source, error_traceback)."""

    def test_returns_four_tuple(self) -> None:
        result = _raise_and_capture(ValueError("hello"))
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_error_type_is_exception_class_name(self) -> None:
        et, _, _, _ = _raise_and_capture(ValueError("hello"))
        assert et == "ValueError"

    def test_error_type_for_builtin_subclass(self) -> None:
        et, _, _, _ = _raise_and_capture(RuntimeError("x"))
        assert et == "RuntimeError"

    def test_error_type_for_custom_exception(self) -> None:
        class MyCustomError(Exception):
            pass
        et, _, _, _ = _raise_and_capture(MyCustomError("x"))
        assert et == "MyCustomError"

    def test_error_msg_contains_exception_message(self) -> None:
        _, em, _, _ = _raise_and_capture(ValueError("the field is missing"))
        assert "the field is missing" in em

    def test_error_msg_includes_type_prefix(self) -> None:
        # The function formats as f"{error_type}: {str(e)}" (line 106).
        _, em, _, _ = _raise_and_capture(ValueError("hello"))
        assert "ValueError" in em
        assert "hello" in em

    def test_error_source_is_non_empty_for_python_raised_exception(self) -> None:
        # _raise_and_capture uses a real raise so the traceback has user frames
        _, _, src, _ = _raise_and_capture(ValueError("x"))
        assert src  # non-empty
        # Each frame is "file:line:function". With 1 frame, no " -> " separator.
        # With >=2 frames, frames are joined by " -> ".
        assert ".py" in src
        # If multiple frames are present, the chain uses " -> " between them.
        # A single frame is just "<file>.py:<line>:<fn>". Both are valid.
        if " -> " in src:
            # Multi-frame case: every segment must be a file:line:fn
            for frame in src.split(" -> "):
                assert ":" in frame


class TestErrorContextMessageCap:
    """``error_msg`` is sliced to [:600] (app_automation.py:106)."""

    def test_message_capped_at_600_chars(self) -> None:
        big = "x" * 5000
        _, em, _, _ = _raise_and_capture(RuntimeError(big))
        assert len(em) <= 600

    def test_message_under_600_passes_through_intact(self) -> None:
        # A short message is not truncated.
        small = "short error"
        _, em, _, _ = _raise_and_capture(ValueError(small))
        # PII masking may add a prefix but the original text must survive
        # and total length must be < 600.
        assert small in em
        assert len(em) < 600

    def test_message_cap_is_inclusive_of_type_prefix(self) -> None:
        # The slicing is on the final string, not on the message body
        # alone. The 600 budget includes "ValueError: " etc.
        msg = "x" * 650  # 650 > 600
        _, em, _, _ = _raise_and_capture(ValueError(msg))
        assert len(em) <= 600


class TestErrorContextTracebackCap:
    """``error_traceback`` is sliced to [:4000] (app_automation.py:128)."""

    def test_traceback_capped_at_4000_chars(self) -> None:
        # Build a deep call stack so the formatted traceback is large.
        def deep(n: int) -> None:
            if n == 0:
                raise RuntimeError("boom")
            deep(n - 1)
        try:
            deep(200)
        except RuntimeError as e:
            _, _, _, tb = _extract_error_context(e)
        assert len(tb) <= 4000

    def test_traceback_is_non_empty_for_real_exception(self) -> None:
        _, _, _, tb = _raise_and_capture(RuntimeError("x"))
        assert tb  # non-empty

    def test_traceback_contains_exception_type_name(self) -> None:
        # traceback.format_exception includes the type name.
        _, _, _, tb = _raise_and_capture(RuntimeError("x"))
        assert "RuntimeError" in tb

    def test_traceback_contains_exception_message(self) -> None:
        _, _, _, tb = _raise_and_capture(RuntimeError("the message"))
        assert "the message" in tb


class TestErrorContextPIIMasking:
    """``mask_pii_text`` is called on both ``error_msg`` and
    ``error_traceback``. Verify the masking actually fires.

    The patterns (per src/utils.py:251-253):
      * Aadhaar: 12 contiguous digits, or 4-4-4 spaced → ``XXXX-XXXX-XXXX``
      * Mobile:  10-digit, starting 6-9 → ``9X******X0`` (first 2 + last 2)
      * IFSC:    4 letters + 0 + 6 alnum → ``XXXX0XXXXXX``
    """

    def test_aadhaar_12_digits_is_masked_in_error_msg(self) -> None:
        # A 12-digit Aadhaar embedded in a ValueError.
        _, em, _, _ = _raise_and_capture(
            ValueError("user 123456789012 not found")
        )
        assert "123456789012" not in em
        assert "XXXX-XXXX-XXXX" in em

    def test_aadhaar_4_4_4_spaced_is_masked_in_error_msg(self) -> None:
        _, em, _, _ = _raise_and_capture(
            ValueError("user 1234 5678 9012 not found")
        )
        assert "1234 5678 9012" not in em
        # mask_pii_text normalizes the spaced form to the masked placeholder
        assert "XXXX-XXXX-XXXX" in em

    def test_mobile_10_digits_is_masked_in_error_msg(self) -> None:
        _, em, _, _ = _raise_and_capture(
            ValueError("phone 9876543210 invalid")
        )
        assert "9876543210" not in em
        # The mask pattern keeps first 2 + 6 asterisks + last 2
        assert "98******10" in em

    def test_pii_is_also_masked_in_traceback(self) -> None:
        # Aadhaar inside the message propagates into the formatted traceback.
        _, _, _, tb = _raise_and_capture(
            ValueError("user 123456789012 not found")
        )
        assert "123456789012" not in tb
        assert "XXXX-XXXX-XXXX" in tb

    def test_plain_text_passes_through_unmasked(self) -> None:
        # No digits, no patterns → no masking.
        _, em, _, _ = _raise_and_capture(
            ValueError("Panchayat Rampur Block Madhupur")
        )
        assert "Panchayat Rampur Block Madhupur" in em

    def test_short_number_is_not_masked(self) -> None:
        # 6-digit numbers are not Aadhaar (must be 12) and not mobile
        # (must be 10) → no masking.
        _, em, _, _ = _raise_and_capture(ValueError("code 123456"))
        assert "123456" in em


class TestErrorContextSourceChain:
    """``error_source`` is the chain of the last 2 user-code frames.

    The function (app_automation.py:113-122) filters out frames whose
    filename contains "site-packages" or starts with "<", then joins the
    last 2 remaining frames as "file:line:fn -> file:line:fn".

    The test functions themselves run in pytest, so their frames have a
    path that does NOT contain "site-packages" — they are user frames.
    """

    def test_error_source_format_is_file_line_function(self) -> None:
        _, _, src, _ = _raise_and_capture(RuntimeError("x"))
        # Each frame is "<filename>:<lineno>:<function_name>"
        # The chain has at least one such frame, joined by " -> "
        frames = src.split(" -> ")
        assert len(frames) >= 1
        for frame in frames:
            assert ":" in frame

    def test_error_source_does_not_contain_site_packages(self) -> None:
        _, _, src, _ = _raise_and_capture(RuntimeError("x"))
        assert "site-packages" not in src

    def test_error_source_preserves_inner_function_name(self) -> None:
        # The deepest user-code frame is _raise_and_capture (a helper).
        # The chain's last segment references the function that raised.
        _, _, src, _ = _raise_and_capture(RuntimeError("x"))
        # The most recent frame is the line inside _raise_and_capture's
        # ``raise exc`` line. Its function name is "_raise_and_capture".
        assert "_raise_and_capture" in src

    def test_error_source_includes_this_test_file(self) -> None:
        # The traceback originated in this file (test_error_context.py).
        # The source chain should reference this file by its basename.
        _, _, src, _ = _raise_and_capture(RuntimeError("x"))
        assert "test_error_context.py" in src

    def test_error_source_caps_at_two_frames(self) -> None:
        # Per the implementation: ``user_frames[-2:]`` (line 122).
        # Even with many frames in the stack, only the last 2 user frames
        # appear in error_source.
        def level_3() -> None:
            raise RuntimeError("x")
        def level_2() -> None:
            level_3()
        def level_1() -> None:
            level_2()
        try:
            level_1()
        except RuntimeError as e:
            _, _, src, _ = _extract_error_context(e)
        # At most 2 " -> "-separated segments
        assert len(src.split(" -> ")) <= 2


class TestErrorContextEdgeCases:
    """Behavior at the edges of the input domain."""

    def test_exception_with_no_message(self) -> None:
        # Some exceptions have no message. error_type is still set; the
        # message is "" and em is just "ValueError: ".
        et, em, _, _ = _raise_and_capture(ValueError(""))
        assert et == "ValueError"
        # The em is exactly the "ValueError: " prefix (the message part
        # is empty). PII masking doesn't change "" so the result is
        # predictable.
        assert "ValueError" in em

    def test_exception_with_none_message_is_safe(self) -> None:
        # ``raise ValueError(None)`` produces a ValueError whose str() is "None".
        et, em, _, _ = _raise_and_capture(ValueError(None))
        assert et == "ValueError"
        # The em is "ValueError: None" — verify the function doesn't crash.
        assert "ValueError" in em

    def test_non_str_message_is_handled(self) -> None:
        # Some real-world exceptions have non-str messages (rare but
        # possible). The function calls str(e) which handles this.
        et, em, _, _ = _raise_and_capture(ValueError(42))
        assert et == "ValueError"
        # The "42" is stringified by str() inside the function.
        assert "42" in em

    def test_chained_exception_uses_outermost(self) -> None:
        # ``raise X from Y`` — the function uses the outer (X) exception
        # because that's what ``type(e).__name__`` and ``str(e)`` refer to.
        try:
            try:
                raise ValueError("inner")
            except ValueError as inner:
                raise RuntimeError("outer") from inner
        except RuntimeError as e:
            et, em, _, _ = _extract_error_context(e)
        assert et == "RuntimeError"
        assert "outer" in em

    def test_returned_tuple_elements_are_strings(self) -> None:
        # All four elements should be strings (not None, not exceptions).
        et, em, src, tb = _raise_and_capture(RuntimeError("x"))
        assert isinstance(et, str)
        assert isinstance(em, str)
        assert isinstance(src, str)
        assert isinstance(tb, str)