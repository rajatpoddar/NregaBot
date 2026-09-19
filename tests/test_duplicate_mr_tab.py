# tests/test_duplicate_mr_tab.py
from unittest.mock import MagicMock
import pytest


def test_duplicate_mr_show_completion_dialog_counts():
    """Verify _show_completion_dialog correctly counts 'Saved as PDF' at index 4 (Status)."""
    from src.tabs.duplicate_mr_tab import DuplicateMrTab

    tab = DuplicateMrTab.__new__(DuplicateMrTab)
    tab.app = MagicMock()
    tab.results_tree = MagicMock()
    tab.log_info = MagicMock()
    tab.activity_details = ""
    tab.show_automation_notification = MagicMock()
    tab.output_dir = None

    # Columns: ("Timestamp", "Panchayat", "Work Code", "MSR No", "Status")
    # Item 1: Saved as PDF (success)
    # Item 2: PDF Save Failed (failure)
    # Item 3: Timeout (failure)
    tab.results_tree.get_children.return_value = ["item1", "item2", "item3"]
    tab.results_tree.item.side_effect = lambda item: {
        "item1": {"values": ["15:00:00", "KASRAYDIH", "475432", "5771", "Saved as PDF"]},
        "item2": {"values": ["15:01:00", "KASRAYDIH", "475433", "5772", "PDF Save Failed"]},
        "item3": {"values": ["15:02:00", "KASRAYDIH", "475434", "5773", "Timeout"]},
    }[item]

    tab._show_completion_dialog()

    # Verify log_info called with 1 saved, 2 failed
    tab.log_info.assert_any_call("📊 Duplicate MR Complete: ✅ 1 saved, ❌ 2 failed (of 3 total)")
    assert "1 saved, 2 failed" in tab.activity_details
    tab.show_automation_notification.assert_called_with("info")


def test_duplicate_mr_all_saved_notification():
    """Verify all saved triggers 'success' notification."""
    from src.tabs.duplicate_mr_tab import DuplicateMrTab

    tab = DuplicateMrTab.__new__(DuplicateMrTab)
    tab.app = MagicMock()
    tab.results_tree = MagicMock()
    tab.log_info = MagicMock()
    tab.activity_details = ""
    tab.show_automation_notification = MagicMock()
    tab.output_dir = None

    tab.results_tree.get_children.return_value = ["item1"]
    tab.results_tree.item.return_value = {
        "values": ["15:00:00", "KASRAYDIH", "475432", "5771", "Saved as PDF"]
    }

    tab._show_completion_dialog()

    tab.log_info.assert_any_call("📊 Duplicate MR Complete: ✅ 1 saved, ❌ 0 failed (of 1 total)")
    assert "1 saved, 0 failed" in tab.activity_details
    tab.show_automation_notification.assert_called_with("success")


def test_emb_verify_show_summary():
    """Verify emb_verify_tab correctly counts status at index 2."""
    from src.tabs.emb_verify_tab import EmbVerifyTab

    tab = EmbVerifyTab.__new__(EmbVerifyTab)
    tab._is_alive = MagicMock(return_value=True)
    tab.results_tree = MagicMock()
    tab.update_status = MagicMock()
    tab.log_info = MagicMock()

    # Columns: ("Panchayat", "Work Code", "Status", "Details", "Timestamp")
    tab.results_tree.get_children.return_value = ["item1", "item2"]
    tab.results_tree.item.side_effect = lambda item: {
        "item1": {"values": ["KASRAYDIH", "475432", "Success", "Verified", "15:00:00"]},
        "item2": {"values": ["KASRAYDIH", "475433", "Failed", "Error", "15:01:00"]},
    }[item]

    tab._show_emb_summary(total_work=2)

    tab.update_status.assert_called_with("✅ 1/2 verified", 1.0)
