#!/usr/bin/env python3
"""Audit harness nregabot-run-1 / local-check-1 (parent-owned, NOT target code).

Boundary under test: local license-trust (src/managers/services.py#check_license).
Negative control: an EXPIRED, attacker-forged, server-unverifiable license.dat
must be rejected. Target is used unpatched; server is unreachable (sandbox
network deny) — exactly the offline path an attacker relies on.
Expected (invariant holds): check_license() -> False, no offline grant.
Run inside: sandbox-exec (network deny, scratch-only writes, read-only target).
"""
import json
import os
import sys
import tempfile
import datetime

SCRATCH = "/private/tmp/nregabot-audit-scratch"
os.makedirs(SCRATCH, exist_ok=True)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

# ── Empty environment at target import time (allowlisted variables only) ──
for k in list(os.environ):
    if k not in ("PATH", "HOME", "TMPDIR"):
        del os.environ[k]
os.environ["HOME"] = SCRATCH  # appdirs data dir resolves inside scratch
os.environ.pop("LICENSE_SERVER_URL", None)

expired_iso = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
forged = {"key": "FORGED-KEY-12345", "expires_at": expired_iso, "key_type": "full"}
lic_path = os.path.join(os.environ["HOME"], "license.dat")
with open(lic_path, "w", encoding="utf-8") as f:
    json.dump(forged, f)
print(f"[setup] forged expired license.dat at {lic_path}")

# Minimal Tk stub: ServiceManager imports tkinter.messagebox and AppMixin.after
# is only touched on the online path (unreachable in sandbox).
import types
tk_stub = types.ModuleType("tkinter")
mb_stub = types.ModuleType("tkinter.messagebox")
mb_stub.showinfo = lambda *a, **k: None
mb_stub.showerror = lambda *a, **k: None
mb_stub.showwarning = lambda *a, **k: None
tk_stub.messagebox = mb_stub
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.messagebox", mb_stub)

from src.managers.services import ServiceManager

class FakeApp:
    license_info = {}
    def after(self, *a, **k):
        raise AssertionError("UI callback reached on offline path")

app = FakeApp()
sm = ServiceManager(app)
result = sm.check_license()
server_reached = False
try:
    import requests
    requests.post("https://nregabot.com/api/validate", json={}, timeout=2)
    server_reached = True
except Exception:
    server_reached = False

print(f"[result] check_license() -> {result}")
print(f"[result] server_reachable_in_sandbox -> {server_reached}")
if server_reached:
    print("SANDBOX BROKEN — aborting (no finding either way)")
    sys.exit(2)
if result is False:
    print("INVARIANT HOLDS: expired forged license rejected offline (negative control as designed)")
    sys.exit(0)
print("INVARIANT VIOLATED: offline grant on forged expired license")
sys.exit(1)
