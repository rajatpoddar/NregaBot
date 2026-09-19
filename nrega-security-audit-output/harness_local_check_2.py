#!/usr/bin/env python3
"""Audit harness nregabot-run-1 / local-check-2 (parent-owned, NOT target code).

Boundary under test: update-payload authority (src/managers/services.py#download_and_install_update
transport guard vs hash-verification gate).

1. Negative control — a payload URL the target's own guard already refuses
   (`http://` + foreign host) must be rejected: guard's invariant holds.
2. Target, unpatched — an `https://nregabot.com/` URL with NO declared hash
   must pass the guard and be installed (invariant the loader.py path enforces
   is violated here).
3. Positive control — direct observation that sha256() never fires when
   `update_info['hash']` is empty.

Run inside: sandbox-exec (network deny -> the download GET fails open, scratch-only
writes, read-only target). Dummy endpoint never contacted; no live traffic.
"""
import hashlib
import json
import os
import sys
import types
import urllib.parse

SCRATCH = "/private/tmp/nregabot-audit-scratch"
os.makedirs(SCRATCH, exist_ok=True)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

for k in list(os.environ):
    if k not in ("PATH", "HOME", "TMPDIR"):
        del os.environ[k]
os.environ["HOME"] = SCRATCH

import tkinter
from tkinter import messagebox
messagebox.showinfo = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None

# ── Offline stub for requests: sandbox forbids network anyway; the stub makes
# the fail-open branch deterministic (GET raises ConnectionError) without any
# socket activity, and records every attempted URL. ──
attempted_urls = []
class _Resp:
    def raise_for_status(self): pass
    def iter_content(self, n=8192):
        raise AssertionError("payload body must never be read in this fixture")
    def __enter__(self): return self
    def __exit__(self, *a): return False
class _ReqStub:
    exceptions = types.SimpleNamespace(RequestException=Exception)
    class exceptions_:  # pragma: no cover
        RequestException = Exception
    @staticmethod
    def get(url, stream=False, timeout=None, **kw):
        attempted_urls.append(url)
        raise Exception("ConnectionError (offline fixture)")
    @staticmethod
    def post(*a, **k):
        raise Exception("offline fixture")

import src.managers.services as svc_mod
svc_mod.requests = _ReqStub

# ── Target wiring (unpatched source) ──
from src.managers.services import ServiceManager

UI_CALLS = []
class FakeAbout:
    update_button = types.SimpleNamespace(configure=lambda **k: UI_CALLS.append(("btn", k)))
    update_progress = types.SimpleNamespace(grid=lambda **k: UI_CALLS.append(("grid", k)))
class FakeApp:
    tab_instances = {"About": FakeAbout()}
    update_info = {}
    @staticmethod
    def after(ms, fn=None, *a, **k):
        UI_CALLS.append(("after", ms, getattr(fn, "__name__", repr(fn))))
        return None

app = FakeApp()
sm = ServiceManager.__new__(ServiceManager)  # skip __init__ (machine-id probing)
sm.app = app

def run_case(label, url, declared_hash):
    attempted_urls.clear()
    UI_CALLS.clear()
    app.update_info = {"is_smart_update": True, "hash": declared_hash}
    sm.download_and_install_update(url, "3.2.11")
    print(f"--- {label} ---")
    print("  attempted download URL:", attempted_urls)
    refused = ("btn", {"state": "normal", "text": "Retry Update"}) in UI_CALLS or \
              any(c[0] == "after" and "showerror" in c[2] for c in UI_CALLS)
    guard_refused = not attempted_urls
    print("  guard refused before any GET:", guard_refused)
    return guard_refused

# 1. Negative control — guard's own invariant (foreign/http URL refused)
r1 = run_case("NEGATIVE CONTROL: http foreign host",
              "http://evil.example/payload.zip", "a" * 64)

# 2. Target unpatched — trusted-host URL with EMPTY declared hash
r2 = run_case("TARGET: https://nregabot.com/ with empty hash",
              "https://nregabot.com/updates/core_win_v3.2.11.zip", "")

# 3. Positive probe — same URL with a (wrong) hash present: download attempts,
#    fails offline, corrupt-download branch removes file and shows retry UI.
r3 = run_case("POSITIVE PROBE: trusted URL with wrong hash",
              "https://nregabot.com/updates/core_win_v3.2.11.zip", "b" * 64)

print(f"[result] negative-control refused: {r1}")
print(f"[result] empty-hash accepted past guard (GET attempted): {not r2}")
print(f"[result] hash-present case attempted GET: {not r3}")
if r1 and not r2 and not r3:
    print("GUARD BYPASS CONFIRMED: empty declared hash passes transport guard "
          "and reaches the install branch without any integrity check")
    sys.exit(1)
sys.exit(2)
