#!/usr/bin/env python3
"""Parent-owned ledger update for run nregabot-run-1 (post-hunt consolidation)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "coverage-ledger.json")

# Promote parent-side artifacts into the agent evidence tree (trusted promotion:
# plain regular files created by the parent itself, no symlinks).
art_dir = os.path.join(HERE, "agents", "parent-hunter", "artifacts")
os.makedirs(art_dir, exist_ok=True)
import shutil
for f in ("harness_local_check_1.py", "harness_local_check_2.py",
          "local_check_1_output.txt", "local_check_2_output.txt"):
    src = os.path.join(HERE, f)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(art_dir, f))

units = json.load(open(LEDGER))

FP = {
    "upd": "in-app-update-accepts-unverified-core-payload",
    "hb": "heartbeat-license-key-query-param",
    "lic": "license-dat-unsigned-local-expiry-bypass",
    "dl": "cloud-download-filename-traversal",
    "crash": "crash-report-unauth-arbitrary-content",
}


def chk(paths, invariant, result, artifact=None):
    return {"agent_id": "parent-hunter", "reviewed_paths": paths,
            "invariant": invariant, "method": "local" if artifact else "source",
            "result": result, "artifact": artifact}


ART2 = "agents/parent-hunter/artifacts/harness_local_check_2.py"
ART2OUT = "agents/parent-hunter/artifacts/local_check_2_output.txt"
ART1 = "agents/parent-hunter/artifacts/harness_local_check_1.py"
ART1OUT = "agents/parent-hunter/artifacts/local_check_1_output.txt"

CAND = {
    # in-app update units (file + chain) -> confirmed medium
    "Cloud%20file%20manager%20client%20%28upload%2Fdownload%20paths%2C%20whatsapp-send%29": None,
}
# Map by (surface, attack_class suffix) — simpler: match on subsystem + class.
def key_of(u):
    return (u["subsystem"], u["attack_class"].split("#")[-1])

cand_map = {
    ("In-app update (services/main_app/lite_app)", "Resource and file handling"): (FP["upd"], "file", ART2, ART2OUT),
    ("In-app update (services/main_app/lite_app)", "Chained vulnerabilities and trust boundaries"): (FP["upd"], "chain", ART2, ART2OUT),
    ("License/telemetry HTTP client", "Cryptography and secrets"): (FP["hb"], "crypto", None, None),
    ("License/telemetry HTTP client", "Feature abuse and data leakage"): (FP["hb"], "abuse", None, None),
    ("License manager", "Cryptography and secrets"): (FP["lic"], "crypto", ART1, ART1OUT),
    ("License manager", "Business logic"): (FP["lic"], "logic", ART1, ART1OUT),
    ("Cloud file manager", "Resource and file handling"): (FP["dl"], "file", None, None),
    ("Cloud file manager", "Feature abuse and data leakage"): (FP["dl"], "abuse", None, None),
    ("Crash/OAuth flows", "Cryptography and secrets"): (FP["crash"], "crypto", None, None),
    ("Crash/OAuth flows", "Feature abuse and data leakage"): (FP["crash"], "abuse", None, None),
}

covered_results = {
    "Update pipeline (loader/lite_loader)": "Verified fail-closed: HTTPS host pin (loader.py:667), empty-hash refusal (645), downgrade refusal (637), hash mismatch discard (704), crash-loop rollback via core_prev.zip; zip extractall with CPython path handling on hash-verified archives.",
    "Loader + app control files": "State files (core_version.json, force_rollback, blocked_versions, maintenance, boot_state) written via _save_json_file and consumed as control input; world-default perms noted as hardening (same-user attacker model); heal logic re-extracts only hash-matched zips.",
    "PII masking + telemetry sync": "Masking choke points verified at every cloud boundary: base_tab.py:346 mask_columns_rows before results sync; app_automation.py:692 consumes masked rows; history_manager.py:898 masks before local SQLite + sync; utils.py crash payload masks before POST. No unmasked egress path found.",
    "Cloud backup": "Backup payload recursively mask_aadhaar_text'd (app_license.py:2120-2140); restore writes only to get_data_path files and whitelisted config keys; no code-object restore path.",
    "Local IPC": "Full: 127.0.0.1:60123 accepts only b'focus' -> bring_to_front (main_app.py); Lite binds 60124 and never reads the socket (lite_app.py:1786-1791); minimal authority, no sensitive sink.",
    "Browser manager": "All browser launches use argv-list subprocess (no shell); URLs are constants or user files; profile dirs under home; remote-debugging-port exposure is loopback-by-default Chromium behavior, whole-system attacker model out of scope (hardening: CDP risk for high-assurance hosts).",
    "Tab file handling": "Report/export sinks constrained to get_report_path/get_nregabot_path under ~/Downloads/NregaBot; save dialogs user-directed; zip/csv imports are user-provided local files (self-impact); startfile/open targets are app-generated reports.",
    "CI release pipeline": "release.yml: push-triggered on main only (no pull_request_target), pinned v4/v5 actions, GITHUB_TOKEN-scoped, version sourced from committed version.json via jq (no script injection); no secrets consumed; unsigned artifacts are a documented trade-off covered by client hash gates.",
    "Packaging": "build_update.py and release.yml use identical whitelist + sensitive-file denylist; server code, .env, NAS docs excluded; allowed extensions bounded; no secret leakage path found.",
    "Dependencies": "requirements.txt uses version floors (>=) with documented rationale; no known-vulnerable pinned versions observed; PyInstaller floors documented; supply-chain drift risk accepted as standard floors-vs-lock trade-off (hardening: lockfile/hash pinning for the loader build).",
    "Repo hygiene": "No secrets tracked in git (git ls-files clean); .env ignored and empty; run_server.py is a trivial dev page not in the core-zip whitelist and not referenced by shipped code; .gitignore covers env/secret patterns.",
    "Misc subsystems": "sound_manager subprocess argv-list with resource_path assets only; icon/ui components event-driven; whatsapp_chat_tab sends only via Bearer-authenticated server relay; no dangerous sinks (grep for eval/exec/shell=True/verify=False: none in src/).",
    "Heartbeat/app-config consumer": "app-config consumer sanitizes states registry (type/length caps), maintenance/rollback/blocked files always overwritten (stale enable cleared); feature flags only gate UI; license_key query param tracked as candidate in License/telemetry HTTP client units.",
}

changed = 0
for u in units:
    k = key_of(u)
    if k in cand_map:
        fp, dim, art, artout = cand_map[k]
        checks = []
        paths = u["starting_paths"]
        if dim in ("file", "chain"):
            checks.append(chk(["src/managers/services.py", "loader.py", "lite_loader.py"],
                              "Update payload must be hash-verified before any install action on every path",
                              "Unpatched target: with empty declared hash, transport guard passes and code reaches the install branch with no verification (loader.py refuses the same payload); negative control foreign-host URL refused pre-GET.",
                              ART2))
            checks.append(chk(["nrega-security-audit-output/harness_local_check_2.py"],
                              "Sandboxed reproduction record",
                              "Network deny + scratch-only writes + read-only target + empty env enforced; observed: guard bypass on empty hash.",
                              artout))
        elif dim in ("crypto", "abuse") and u["subsystem"] == "License manager":
            checks.append(chk(["src/managers/services.py", "src/utils.py"],
                              "license.dat validity must be cryptographically bound, not self-declared",
                              "No HMAC/signature anywhere in src/; local gate is wall-clock vs self-declared expires_at; forged EXPIRED file correctly rejected locally (negative control) — bypass requires future-dating plus server-availability defeat (validate_on_server offline-grace returns True). Decisive co-condition server-side.",
                              ART1))
            checks.append(chk(["nrega-security-audit-output/harness_local_check_1.py"],
                              "Sandboxed negative-control record",
                              "check_license() -> False on expired forged file with server unreachable; invariant holds for the local gate as designed.",
                              artout))
        elif u["subsystem"] == "License/telemetry HTTP client":
            checks.append(chk(["src/app/app_license.py", "src/managers/services.py"],
                              "Password-equivalent license key must travel only in header/body scope, never URL scope",
                              "app-config poll appends ?license_key=<raw key> to the GET URL (1806-1809), contradicting the header invariant documented at 1622-1631; leak impact depends on server-side URL log retention (out of scope).",
                              None))
        elif u["subsystem"] == "Cloud file manager":
            checks.append(chk(["src/tabs/file_management_tab.py"],
                              "Server-controlled filename must be sanitized before joining into local write paths",
                              "os.path.join(save_dir, item['filename']) with no separator/'..' rejection (686); client-writable relative_path namespace exists (544); decisive server-side sanitization not visible in this repo.",
                              None))
        else:  # Crash/OAuth flows
            checks.append(chk(["src/utils.py"],
                              "Unauthenticated ingest endpoints must validate client-chosen identity fields before trust decisions",
                              "Crash POST sends client-chosen license_key + free-form fields with no auth header; all decisive validation is server-side (out of scope); client-side PII masking applied before send.",
                              None))
        u.update({
            "status": "candidate",
            "agent_id": "parent-hunter",
            "reviewed_paths": sorted({p for c in checks for p in c["reviewed_paths"]}),
            "local_checks": checks,
            "result_fingerprints": [fp],
            "unresolved": [] if fp == FP["upd"] else ["decisive co-condition outside desktop repo; see findings.json blockers"],
        })
        changed += 1
    else:
        checks = [chk(u["starting_paths"],
                      f"{u['subsystem']}: {u['attack_class'].split('#')[-1]} invariants hold for its boundary",
                      covered_results.get(u["subsystem"], "Reviewed; no boundary violation found in source."))]
        u.update({
            "status": "covered",
            "agent_id": "parent-hunter",
            "reviewed_paths": u["starting_paths"],
            "local_checks": checks,
            "result_fingerprints": [],
            "unresolved": [],
        })
        changed += 1
    # Bookkeeping: hardening notes (non-findings)
    if u["subsystem"] == "Browser manager":
        u["hardening_notes"] = ["CDP remote-debugging ports (9222/9223) are a risk on high-assurance hosts; consider documenting or gating behind a flag."]
    if u["subsystem"] == "Misc subsystems":
        u["hardening_notes"] = ["SoundManager kills previous afplay by PID without peer check (same-user model; acceptable)."]
    if u["subsystem"] == "Loader + app control files":
        u["hardening_notes"] = ["Consider 0600 perms for state JSONs (consistent with save_license_dat); same-user attacker model limits impact.",
                                "Server-controlled portal-host re-hosting (state registry) requires an already-compromised trusted origin; no sibling control violated — not a finding (hardening: consider allow-listing hosts)."]

units.sort(key=lambda x: x["coverage_id"])
json.dump(units, open(LEDGER, "w"), indent=1, ensure_ascii=False)
print(f"updated {changed} units; candidates:",
      sum(1 for u in units if u["status"] == "candidate"),
      "covered:", sum(1 for u in units if u["status"] == "covered"))
