"""Headless smoke test: instantiates EVERY tab in tab_config.py to catch
pack/grid TclErrors and other construction-time crashes.

Run: venv/bin/python _smoke_test_tabs.py
Creates a real (withdrawn) Tk root so geometry-manager conflicts surface,
exactly like the user's "cannot use geometry manager pack inside ... grid" crash.
"""
import sys
import traceback

import customtkinter as ctk
from tkinter import messagebox

# Silence messageboxes during construction (e.g. missing files / warnings)
messagebox.showwarning = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None
messagebox.showinfo = lambda *a, **k: None
messagebox.askyesno = lambda *a, **k: False
messagebox.askokcancel = lambda *a, **k: False


class FakeHistory:
    def get_suggestions(self, key):
        return ["Test Panchayat"]
    def get_tab_inputs(self, key):
        return {}
    def save_tab_inputs_batch(self, *a, **k):
        pass
    def get_total_suggestions_count(self):
        return 0
    def get_usage_stats_count(self):
        return 0
    def get_usage_stats(self):
        return {}
    def get_suggestions_count_by_key(self):
        return {}
    def get_most_used_keys(self, limit=None):
        return []
    def clear_all_suggestions(self):
        return 0
    def save_suggestion(self, *a, **k):
        pass


class _FakeWorkflows:
    """Minimal stand-in so tabs can reference app.workflows.queue_items."""
    def __init__(self):
        self.queue_items = []
        self.pipeline_queue = []
        self.is_pipeline_running = False


class FakeApp:
    def __init__(self):
        self.history_manager = FakeHistory()
        self.stop_events = {}
        self.active_automations = set()
        self.active_browser = 'chrome'
        self._cached_style = None
        self.icon_images = {}
        self.clipboard = ""
        self.license_info = {}  # File Manager reads license_info
        self.current_user = {"name": "Test"}
        self.tab_instances = {}
        self.workflows = _FakeWorkflows()

    def _missing(self, *a, **k):
        return "/tmp"
    get_report_path = _missing
    get_nregabot_path = _missing
    get_data_path = _missing

    def set_status(self, msg):
        pass
    def get_driver(self):
        return None
    def update_history(self, *a, **k):
        pass
    def clear_log(self, *a):
        pass
    def start_automation_thread(self, *a, **k):
        pass
    def show_toast(self, **k):
        pass
    def after(self, ms, cb, *a, **k):
        return None
    def clipboard_clear(self):
        self.clipboard = ""
    def clipboard_append(self, text):
        self.clipboard = text
    def log_message(self, *a, **k):
        pass
    def get_tabs_definition(self):
        from src.tab_config import get_tabs_definition
        return get_tabs_definition(self)
    def show_frame(self, *a, **k):
        pass
    def get_driver_or_launch(self, *a, **k):
        return None
    def open_external_url(self, *a, **k):
        pass
    def launch_chrome_detached(self, *a, **k):
        return None
    def set_status(self, msg):
        pass
    def open_link_in_browser(self, *a, **k):
        pass
    def get_driver(self):
        return None
    def _quick_login_automation(self, *a, **k):
        return None


def main():
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()

    from src.tab_config import get_tabs_definition
    definitions = get_tabs_definition(FakeApp())

    # Flatten: (category, tab_name, creation_func, key)
    all_tabs = []
    for category, tabs in definitions.items():
        for name, info in tabs.items():
            all_tabs.append((category, name, info["creation_func"], info.get("key")))

    print(f"Total tabs found: {len(all_tabs)}\n")

    failed = []
    for category, name, creation_func, key in all_tabs:
        try:
            app = FakeApp()
            tab = creation_func(root, app)
            root.update()  # force layout -> TclError fires here if pack/grid mix
            tab.destroy()
            print(f"  OK  [{category}] {name}")
        except Exception as e:
            failed.append((category, name, e))
            print(f"  FAIL [{category}] {name}: {e}")
            traceback.print_exc()

    root.destroy()
    if failed:
        print(f"\nSMOKE TEST FAILED: {len(failed)} tab(s) failed")
        for cat, name, e in failed:
            print(f"  - [{cat}] {name}: {e}")
        sys.exit(1)
    print("\nSMOKE TEST PASSED: all tabs instantiate without TclError")


if __name__ == "__main__":
    main()
