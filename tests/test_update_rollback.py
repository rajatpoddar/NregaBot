"""Unit tests for the desktop update-rollback mechanism.

Covers the boot-counter crash detection and core_prev.zip restore that the
loader (loader.py / lite_loader.py) uses to recover from a broken update:

  * src/utils.py      — boot counter, bad-version floor, prev-zip promotion
  * loader.py         — _rollback_to_previous end-to-end (restore + version
                        file + bad-version ban + counter reset)
  * lite_loader.py    — boot counter, apply/restore of the Lite update zip

Every test runs against pytest's tmp_path — real user data (user_data_dir) is
never touched (get_data_path / loader module constants are monkeypatched).

Run:  venv/bin/python -m pytest tests/test_update_rollback.py -v
"""
import json
import os
import time
import zipfile

import pytest

import src.utils as U


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Point every state file (boot_state, bad_versions, core.zip, ...) at an
    isolated temp dir so tests never modify real user data."""
    monkeypatch.setattr(U, "get_data_path", lambda f="": str(tmp_path / (f or "")))
    yield


def _write_zip(path, version):
    """Write a tiny fake core zip whose src/config.py reports APP_VERSION."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("src/config.py", f"APP_VERSION = '{version}'\n")


# ---------------------------------------------------------------------------
# Boot counter (src.utils)
# ---------------------------------------------------------------------------

class TestBootCounter:
    def test_three_consecutive_crashes_trigger_rollback(self):
        assert not U.should_rollback_boot()
        U.record_boot_attempt("3.2.5")
        U.record_boot_attempt("3.2.5")
        assert not U.should_rollback_boot(), "2 attempts < 3 → no rollback"
        U.record_boot_attempt("3.2.5")
        assert U.should_rollback_boot()

    def test_clean_boot_resets_counter(self):
        U.record_boot_attempt("3.2.5")
        U.record_boot_attempt("3.2.5")
        U.record_boot_attempt("3.2.5")
        assert U.should_rollback_boot()
        U.mark_clean_boot("3.2.5")  # app boots fine
        assert U.read_boot_state() == {}
        assert not U.should_rollback_boot()

    def test_stale_crash_does_not_trigger_rollback(self):
        U._save_json_file(U.get_boot_state_path(),
                          {"attempts": 9, "version": "3.2.5", "ts": time.time() - 7200})
        assert not U.should_rollback_boot(), "old crash (>10 min) must not count"
        U._save_json_file(U.get_boot_state_path(),
                          {"attempts": 9, "version": "3.2.5", "ts": time.time() - 60})
        assert U.should_rollback_boot(), "recent crashes must count"

    def test_boot_state_never_corrupts_other_files(self):
        # state file is JSON and resettable even if hand-edited to garbage
        U._save_json_file(U.get_boot_state_path(), "not a dict")
        U.record_boot_attempt("3.2.5")  # must not raise
        assert int(U.read_boot_state().get("attempts") or 0) == 1


# ---------------------------------------------------------------------------
# Bad-version floor (src.utils)
# ---------------------------------------------------------------------------

class TestBadVersions:
    def test_remember_and_skip(self):
        assert not U.is_bad_version("3.2.5")
        U.remember_bad_version("3.2.5")
        assert U.is_bad_version("3.2.5")
        assert U.is_bad_version("3.2.4"), "anything up to the bad version is skipped"
        assert not U.is_bad_version("3.2.6"), "a newer release is not bad"

    def test_floor_is_monotonic(self):
        U.remember_bad_version("3.2.5")
        U.remember_bad_version("3.2.4")  # older — must NOT lower the floor
        assert U.is_bad_version("3.2.5")

    def test_newer_clean_boot_clears_floor(self):
        U.remember_bad_version("3.2.5")
        U.mark_clean_boot("3.2.6")  # newer version boots fine → floor obsolete
        assert not U.is_bad_version("3.2.5")

    def test_older_clean_boot_keeps_floor(self):
        U.remember_bad_version("3.2.5")
        U.mark_clean_boot("3.2.4")  # rolled-back version — floor stays
        assert U.is_bad_version("3.2.5")


# ---------------------------------------------------------------------------
# core_prev.zip promotion (src.utils)
# ---------------------------------------------------------------------------

class TestPromote:
    def test_no_zip_no_promote(self):
        assert not U.promote_current_zip_to_prev()

    def test_promote_with_matching_hash(self):
        zip_path = U.get_core_zip_path()
        _write_zip(zip_path, "3.2.4")
        h = U._sha256_file(zip_path)
        U._save_json_file(U.get_core_version_file_path(), {"version": "3.2.4", "hash": h})
        assert U.promote_current_zip_to_prev()
        assert os.path.exists(U.get_core_prev_zip_path())
        meta = U._load_json_file(U.get_core_prev_meta_path(), {})
        assert meta.get("version") == "3.2.4"
        assert meta.get("hash") == h

    def test_promote_rejects_hash_mismatch(self):
        # a partial/corrupt download must never become the rollback target
        zip_path = U.get_core_zip_path()
        _write_zip(zip_path, "3.2.4")
        U._save_json_file(U.get_core_version_file_path(),
                          {"version": "3.2.4", "hash": "0" * 64})
        assert not U.promote_current_zip_to_prev()
        assert not os.path.exists(U.get_core_prev_zip_path())

    def test_promote_rejects_corrupt_zip(self):
        with open(U.get_core_zip_path(), "w") as f:
            f.write("not a zip")
        assert not U.promote_current_zip_to_prev()


# ---------------------------------------------------------------------------
# loader._rollback_to_previous
# ---------------------------------------------------------------------------

import loader  # noqa: E402  (heavy-ish module; kept after the utils tests)


@pytest.fixture()
def loader_env(tmp_path, monkeypatch):
    """Redirect loader's module-level paths into an isolated temp dir.

    Note: core_prev.zip / core_prev_meta.json have NO module constants — the
    rollback code reads them via src.utils getters, which the autouse
    _isolate_state fixture already redirects to the same tmp_path.
    """
    monkeypatch.setattr(loader, "LOCAL_DIR", str(tmp_path))
    monkeypatch.setattr(loader, "CORE_ZIP_PATH", str(tmp_path / "core.zip"))
    monkeypatch.setattr(loader, "EXTRACTED_DIR", str(tmp_path / "app_live"))
    monkeypatch.setattr(loader, "VERSION_FILE", str(tmp_path / "core_version.json"))
    return loader


def _make_loader_obj(loader_mod):
    """A real ModernSplashScreen would open a Tk window + start a thread — use a
    bare instance with only the attributes the rollback path touches."""
    obj = object.__new__(loader_mod.ModernSplashScreen)
    obj.is_destroyed = True
    obj._dot_index = 0
    obj._glow_direction = 1
    obj._glow_step = 0
    obj._anim_after_id = None
    obj._pending_version = None
    obj._pending_hash = ""
    obj.update_status = lambda text, progress=None: None
    return obj


class TestLoaderRollback:
    def test_rollback_restores_previous_version(self, loader_env):
        loader_mod = loader_env
        _write_zip(U.get_core_prev_zip_path(), "3.2.4")
        prev_hash = U._sha256_file(U.get_core_prev_zip_path())
        U._save_json_file(U.get_core_prev_meta_path(),
                          {"version": "3.2.4", "hash": prev_hash})
        _write_zip(loader_mod.CORE_ZIP_PATH, "3.2.5")  # broken current version
        U._save_json_file(U.get_boot_state_path(),
                          {"attempts": 3, "version": "3.2.5", "ts": time.time() - 30})

        obj = _make_loader_obj(loader_mod)
        assert loader_mod.ModernSplashScreen._rollback_to_previous(obj, "3.2.5")

        # live code is the old version again
        assert loader_mod.ModernSplashScreen._get_app_live_version(obj) == "3.2.4"
        rec_ver, rec_hash = obj._read_version_file()
        assert rec_ver == "3.2.4", f"version file must record 3.2.4, got {rec_ver!r}"
        assert rec_hash == prev_hash

        # crashed version banned (update check will skip it), counter reset
        assert U.is_bad_version("3.2.5") and not U.is_bad_version("3.2.6")
        assert int(U.read_boot_state().get("attempts") or 0) == 0

    def test_rollback_derives_version_when_meta_missing(self, loader_env):
        loader_mod = loader_env
        _write_zip(U.get_core_prev_zip_path(), "3.2.4")
        # no core_prev_meta.json — version must be derived from the code
        obj = _make_loader_obj(loader_mod)
        assert loader_mod.ModernSplashScreen._rollback_to_previous(obj, "")
        assert loader_mod.ModernSplashScreen._get_app_live_version(obj) == "3.2.4"
        rec_ver, _ = obj._read_version_file()
        assert rec_ver == "3.2.4"

    def test_rollback_without_prev_is_graceful(self, loader_env):
        loader_mod = loader_env
        obj = _make_loader_obj(loader_mod)
        assert loader_mod.ModernSplashScreen._rollback_to_previous(obj, "3.2.5") is False

    def test_rollback_with_corrupt_prev_is_graceful(self, loader_env):
        loader_mod = loader_env
        with open(U.get_core_prev_zip_path(), "w") as f:
            f.write("not a zip")
        obj = _make_loader_obj(loader_mod)
        assert loader_mod.ModernSplashScreen._rollback_to_previous(obj, "3.2.5") is False


# ---------------------------------------------------------------------------
# lite_loader (mirror of the main mechanism)
# ---------------------------------------------------------------------------

try:
    import lite_loader
except ImportError:  # e.g. customtkinter not installed in a minimal env
    lite_loader = None


@pytest.mark.skipif(lite_loader is None, reason="lite_loader not importable")
class TestLiteRollback:
    def test_boot_counter(self, tmp_path):
        install = str(tmp_path / "install")
        os.makedirs(install)
        assert not lite_loader._lite_should_rollback(install)
        for _ in range(3):
            lite_loader._lite_record_boot_attempt(install, "3.2.5")
        assert lite_loader._lite_should_rollback(install)
        # stale → no rollback
        lite_loader._lite_write_json(lite_loader._lite_boot_state_path(install),
                                     {"attempts": 9, "version": "3.2.5", "ts": time.time() - 9999})
        assert not lite_loader._lite_should_rollback(install)

    def test_bad_version_floor(self, tmp_path):
        install = str(tmp_path / "install")
        os.makedirs(install)
        lite_loader._lite_remember_bad_version(install, "3.2.5")
        assert lite_loader._lite_is_bad_version(install, "3.2.5")
        assert not lite_loader._lite_is_bad_version(install, "3.2.6")

    def test_apply_and_restore_previous(self, tmp_path):
        install = str(tmp_path / "install")
        content = str(tmp_path / "content")
        os.makedirs(install)
        os.makedirs(os.path.join(content, "src"))

        obj = object.__new__(lite_loader.LiteLoaderSplash)
        obj._track_boot = False
        obj._install_dir = install
        obj.is_destroyed = False
        obj._set_status = lambda text: None

        prev_zip = os.path.join(install, "_lite_prev_update.zip")
        _write_zip(prev_zip, "3.2.4")
        lite_loader._lite_write_json(os.path.join(install, "_lite_prev_meta.json"),
                                     {"version": "3.2.4", "hash": "abc"})
        new_zip = os.path.join(install, "_lite_update.zip")
        _write_zip(new_zip, "3.2.5")

        assert obj._apply_update_zip(install, content, new_zip, "3.2.5", "xyz")
        with open(os.path.join(content, "src", "config.py")) as f:
            assert "3.2.5" in f.read()
        vd = lite_loader._lite_read_json(os.path.join(install, "version.json"), {})
        assert vd.get("version") == "3.2.5" and vd.get("hash") == "xyz"
        assert os.path.exists(new_zip), "applied zip must be kept as rollback source"

        # crash-loop on 3.2.5 → restore 3.2.4
        lite_loader._lite_write_json(lite_loader._lite_boot_state_path(install),
                                     {"attempts": 3, "version": "3.2.5", "ts": time.time() - 30})
        assert obj._lite_restore_previous(install, content, "3.2.5")
        with open(os.path.join(content, "src", "config.py")) as f:
            assert "3.2.4" in f.read(), "content must be rolled back to 3.2.4"
        vd = lite_loader._lite_read_json(os.path.join(install, "version.json"), {})
        assert vd.get("version") == "3.2.4"
        assert lite_loader._lite_is_bad_version(install, "3.2.5")
        state = lite_loader._lite_read_json(lite_loader._lite_boot_state_path(install), {})
        assert int(state.get("attempts") or 0) == 0

    def test_restore_without_prev_is_graceful(self, tmp_path):
        install = str(tmp_path / "install")
        os.makedirs(install)
        obj = object.__new__(lite_loader.LiteLoaderSplash)
        obj._track_boot = False
        obj._install_dir = install
        obj.is_destroyed = False
        obj._set_status = lambda text: None
        assert obj._lite_restore_previous(install, str(tmp_path / "content"), "3.2.6") is False
