"""Regression tests for in-app update integrity verification (Confirmed-1).

Verifies that ServiceManager.download_and_install_update:
1. Rejects non-HTTPS or non-nregabot.com URLs before any GET.
2. Fails closed when expected_hash is empty or missing (no GET performed).
3. Detects hash mismatch post-download, removes corrupt file, and alerts user.
4. Accepts and applies updates when SHA-256 hash matches.
"""
import hashlib
import os
import types
import pytest

from src.managers.services import ServiceManager


class DummyButton:
    def __init__(self):
        self.state = "normal"
        self.text = ""

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]
        if "text" in kwargs:
            self.text = kwargs["text"]


class DummyProgress:
    def __init__(self):
        self.val = 0.0

    def grid(self, **kwargs):
        pass

    def set(self, val):
        self.val = val


class DummyAboutTab:
    def __init__(self):
        self.update_button = DummyButton()
        self.update_progress = DummyProgress()


class DummyApp:
    def __init__(self):
        self.tab_instances = {"About": DummyAboutTab()}
        self.update_info = {}
        self.status = ""
        self.smart_update_applied = None
        self.scheduled_calls = []

    def after(self, ms, fn, *args, **kwargs):
        # Execute synchronously for deterministic testing
        self.scheduled_calls.append((ms, fn, args, kwargs))
        if callable(fn):
            return fn(*args, **kwargs)
        return None

    def set_status(self, msg):
        self.status = msg

    def _apply_smart_update(self, path):
        self.smart_update_applied = path


@pytest.fixture
def mock_env(tmp_path, monkeypatch):
    """Isolate downloads path and mock UI messagebox."""
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    monkeypatch.setattr("src.managers.services.get_user_downloads_path", lambda: str(downloads_dir))
    
    shown_errors = []
    monkeypatch.setattr("src.managers.services.messagebox.showerror", lambda title, msg: shown_errors.append((title, msg)))
    
    # Run worker thread synchronously instead of spawning threading.Thread
    def sync_thread(target, daemon=True):
        t = types.SimpleNamespace()
        t.start = lambda: target()
        return t
    monkeypatch.setattr("threading.Thread", sync_thread)
    
    return types.SimpleNamespace(downloads_dir=downloads_dir, shown_errors=shown_errors)


def test_inapp_update_rejects_unsafe_url(mock_env):
    app = DummyApp()
    sm = ServiceManager.__new__(ServiceManager)
    sm.app = app
    app.update_info = {"is_smart_update": True, "hash": "a" * 64}

    # HTTP URL
    sm.download_and_install_update("http://nregabot.com/updates/core.zip", "3.2.12")
    assert len(mock_env.shown_errors) == 1
    assert "Refusing unsafe update URL" in mock_env.shown_errors[0][1]

    # Foreign host
    sm.download_and_install_update("https://evil.example.com/updates/core.zip", "3.2.12")
    assert len(mock_env.shown_errors) == 2
    assert "Refusing unsafe update URL" in mock_env.shown_errors[1][1]


def test_inapp_update_fails_closed_on_empty_hash(mock_env, monkeypatch):
    app = DummyApp()
    sm = ServiceManager.__new__(ServiceManager)
    sm.app = app

    get_called = []
    class MockRequests:
        @staticmethod
        def get(*args, **kwargs):
            get_called.append(args)
            raise AssertionError("requests.get must NOT be called when hash is empty")

    monkeypatch.setattr("src.managers.services.requests", MockRequests)

    # Empty hash in update_info
    app.update_info = {"is_smart_update": True, "hash": ""}
    sm.download_and_install_update("https://nregabot.com/updates/core_win_v3.2.12.zip", "3.2.12")

    assert len(get_called) == 0, "Download was attempted despite empty integrity hash!"
    assert len(mock_env.shown_errors) == 1
    assert "server did not provide an integrity hash" in mock_env.shown_errors[0][1]
    assert app.tab_instances["About"].update_button.text == "Retry Update"


def test_inapp_update_fails_on_hash_mismatch(mock_env, monkeypatch):
    app = DummyApp()
    sm = ServiceManager.__new__(ServiceManager)
    sm.app = app

    content = b"corrupted payload data"
    actual_hash = hashlib.sha256(content).hexdigest()
    expected_hash = "f" * 64

    class MockResponse:
        headers = {"content-length": str(len(content))}
        def raise_for_status(self):
            pass
        def iter_content(self, chunk_size):
            yield content
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    class MockRequests:
        @staticmethod
        def get(url, stream=True):
            return MockResponse()

    monkeypatch.setattr("src.managers.services.requests", MockRequests)

    app.update_info = {"is_smart_update": True, "hash": expected_hash}
    sm.download_and_install_update("https://nregabot.com/updates/core_win_v3.2.12.zip", "3.2.12")

    # Mismatch detected -> dl_path removed, error shown
    assert len(mock_env.shown_errors) == 1
    assert "Download is corrupt or hash mismatch" in mock_env.shown_errors[0][1]
    assert not os.path.exists(mock_env.downloads_dir / "core_win_v3.2.12.zip")
    assert app.smart_update_applied is None


def test_inapp_update_succeeds_when_hash_matches(mock_env, monkeypatch):
    app = DummyApp()
    sm = ServiceManager.__new__(ServiceManager)
    sm.app = app

    content = b"valid core zip payload bytes"
    expected_hash = hashlib.sha256(content).hexdigest()

    class MockResponse:
        headers = {"content-length": str(len(content))}
        def raise_for_status(self):
            pass
        def iter_content(self, chunk_size):
            yield content
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    class MockRequests:
        @staticmethod
        def get(url, stream=True):
            return MockResponse()

    monkeypatch.setattr("src.managers.services.requests", MockRequests)

    app.update_info = {"is_smart_update": True, "hash": expected_hash}
    sm.download_and_install_update("https://nregabot.com/updates/core_win_v3.2.12.zip", "3.2.12")

    assert len(mock_env.shown_errors) == 0
    expected_file = str(mock_env.downloads_dir / "core_win_v3.2.12.zip")
    assert app.smart_update_applied == expected_file
