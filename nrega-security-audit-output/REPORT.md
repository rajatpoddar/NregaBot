# Security Audit Report — NregaBot Desktop (`nregabot-run-1`)

## 1. Run profile, scope, and execution statement

| Field | Value |
|---|---|
| Profile | **standard** (coverage ledger, hunter waves, post-wave critic, independent verification) |
| Scope | Desktop app repo only: `main_app.py`, `lite_app.py`, `lite_loader.py`, `loader.py`, `src/`, `scripts/` (build), `.github/workflows/`, `config/version.json` |
| Out of scope | `nrega-server/` (separate repo, per audit request), `venv/`, `build/`, `dist/`, `assets/` (static), `android-app/`, `mobile_design/` |
| Source ref | `df034c7d584d26865d705abdeff499f2b5499821` (worktree dirty: `config/version.json` only) |
| Budget | none set |
| Prior runs | none existed; no ledger carried |
| Execution | **sandboxed source-and-local-only.** All evidence is source review plus two sandboxed harness runs (macOS seatbelt: `deny network*`, scratch-only writes, read-only target, empty environment at target import). No live endpoints were contacted; no production data touched. |
| Platform adaptation | This environment exposes no sub-agent/Task mechanism. The hunter, coverage-critic, Phase-3 verifier, and Phase-5 verifier roles were executed as **separate passes by the parent agent**, preserving the structured per-unit evidence contracts and the fresh-eyes re-verification of every record. Independence is pass-level, not agent-level — disclosed as a run limitation. |
| Run status | **complete** — all 33 ledger units dispositioned; every retained record passed verification; both validators pass. |

This is a scoped run (server repo excluded by request); it makes no claim about `nrega-server/`.

## 2. Security posture summary

The desktop app is unusually well-hardened for its class. The loader update pipeline enforces the full fail-closed set (HTTPS host pin, per-platform SHA-256, empty-hash refusal, downgrade refusal, crash-loop rollback). PII masking is applied through choke points at **every** cloud boundary (results sync, backups, logs, crash reports, activity telemetry) — consistent with the project's DPDP Act 2023 posture. No secrets are tracked in git; no `eval`/`exec`/shell-string/`verify=False` sinks exist; the CI workflow has no injection surface and consumes no secrets.

One real defect was confirmed: the **in-app updater** (the sibling of the hardened loader path) installs trusted-host payloads with **no** integrity check when the declared hash is empty — violating the codebase's own invariant. Three leads require owner observation of the server side before they can be graded.

## 3. Confirmed findings

| Severity | Title | Boundary | Observed result |
|---|---|---|---|
| **medium** | In-app updater installs trusted-host payloads without integrity verification | Update-payload authority (`src/managers/services.py` vs `loader.py` gate) | With an empty declared hash, the payload passes the only pre-install gate (transport guard) and reaches `os.startfile`/`open` with zero verification; `loader.py` refuses the identical payload |

### Confirmed-1: `in-app-update-accepts-unverified-core-payload` (medium)

- **Location:** `src/managers/services.py:223-288`; sibling control `loader.py:690`.
- **Lower-trust principal / entry:** the `version.json` writer's payload choice (publisher mistake or origin compromise — TLS blocks on-path attackers), consumed by the About-tab update flow with a user click.
- **Reproduction (bounded, sandboxed):** `sandbox-exec -f /tmp/net-deny.sb python3 nrega-security-audit-output/harness_local_check_2.py` — drives the unpatched `ServiceManager.download_and_install_update` with (a) a foreign-host URL → refused pre-GET (negative control), (b) a trusted-host URL with `hash: ""` → **guard passes, install branch reached, no verification exists**.
- **Conditions:** version.json must carry a trusted-host payload with an empty platform hash; user accepts the in-app prompt. The live feed currently publishes hashes for both platforms, so reachability is owner-controlled — the client defect is the *absent fail-closed invariant* exactly where the loader keeps one.
- **Impact if reached:** payload becomes executed code on the worker's machine (Windows: `os.startfile` + `os._exit`; macOS: opened, and for `.zip`, copied to `core.zip` as next-boot code). Overall severity capped at medium because likelihood requires a publisher-side mistake/compromise.
- **Priority rationale:** same authority boundary as the loader (code execution), one-line divergence from an invariant the codebase itself defines; trivial to close.
- **Smallest fix:** in `services.py::_download_and_install_update`, refuse when `expected_hash` is empty (mirror `loader.py:690`), then verify before install; publish the generic hash in `version.json` so no client path sees an empty field.

## 4. NEEDS VALIDATION

| Lead | Trace (repo-relative) | Exact blocker | Bounded local next step | Owner-observed deployment check |
|---|---|---|---|---|
| `heartbeat-license-key-query-param` | `app_license.py:1785 → 1808 → 1810` | Whether key-bearing URLs are persisted in server/CDN/WAF access logs (deployment fact; server repo out of scope) | Confirm request-line carries the key (loopback fixture; already source-visible at 1808) | Grep access logs for `license_key=`, review CDN/WAF query retention; if logged → rotate keys, switch to Authorization header |
| `license-dat-unsigned-local-expiry-bypass` | `services.py:56 → 67 → 68 → 73 → 133` | Whether online rejection actually deactivates the app, and the vendor's accepted abuse model (anti-tamper vs hard control) | Sandbox fixture: future-dated forged `license.dat` + blocked egress → app enters licensed state (client half) | Observe re-validation behavior with forged key online: lockout vs transient error; state intended offline-grace policy |
| `cloud-download-filename-traversal` | `file_management_tab.py:683 → 686 → 688` | Whether nrega-server sanitizes `filename`/`relative_path` at store/list time; tenancy of the files namespace | Loopback stub of `/files/api/download` returning `../../pwned.txt` → drive the unmodified worker against a scratch dir | Inspect upload handler validation + list serialization + cross-user namespace isolation; if sanitized, close as rejected |
| `crash-report-unauth-arbitrary-content` | `utils.py:573 → 503 → server handler` | Entirely server-side: key ownership validation, field sanitization, admin-view escaping | (Client half already established: no auth header, client-chosen key) | Inspect `/api/crash-report` handler + admin rendering; if all validated/escaped, close as rejected |

These are **not** confirmed vulnerabilities; each has a decisive fact outside the desktop repository.

## 5. Hardening notes and positive patterns

**Positive patterns (worth keeping):**
- Loader fail-closed update gate (`loader.py:637-706`): host pin + platform hash + empty-hash refusal + downgrade refusal + rollback — a model sibling to diff against.
- PII masking choke points at every egress: `base_tab.py:346` (cloud rows), `utils.py:303/544-578` (logs + crash), `history_manager.py:898` (SQLite + sync), `app_license.py:2120` (backup).
- `save_license_dat()` single choke point with `chmod 600` (`src/utils.py:690`).
- Whitelist core-zip packaging in both `scripts/build_update.py` and CI, with a sensitive-file denylist.
- CI: push-to-main only, pinned actions, no secrets, no script injection surface; `ruff F821/E722` gate.

**Hardening notes (non-findings):**
- Chrome/Edge CDP remote-debugging ports (9222/9223) are loopback-only by default but let any same-user process drive the logged-in portal session; consider documenting or gating on high-assurance hosts.
- App-control state JSONs (`core_version.json`, `maintenance_mode.json`, …) use default perms, unlike `license.dat`'s 0600; same-user attacker model limits impact.
- Server-controlled portal-host re-hosting (state registry → `get_state_portal_url`) is sanitized-shape but not scheme-allow-listed; requires an already-compromised trusted origin to matter (not a finding).
- `requirements.txt` uses floors, not a lockfile; a lock/hash-pinned set for the loader build would tighten supply-chain drift.
- `run_server.py` (port-8099 dev page) is unreferenced by shipped code and excluded from the core-zip whitelist; consider deleting.

## 6. Coverage summary (from `coverage-ledger.json`)

- **33/33 units dispositioned**: 23 `covered`, 10 `candidate` (5 unique fingerprints), 0 `blocked`, 0 `deferred`, 0 `out_of_scope`.
- Hunter waves: 3 (update/licensing/transport; PII/cloud; CI/packaging/wildcard), followed by a coverage-critic pass — no accepted `missing_units`, no legitimate `reassign_ids`; one candidate demoted to a hardening note (state-registry re-hosting) under the anti-pattern rules.
- Candidate validation: 5 fingerprints → 1 confirmed, 4 needs_validation (each with a decisive out-of-scope fact). Rejected during validation: none.
- Every assigned unit carries per-check evidence (`reviewed_paths`, `invariant`, `method`, `result`, promoted artifacts under `agents/parent-hunter/artifacts/`).
- Scope exclusions: `nrega-server/` (all server-side handlers referenced above), packaging metadata dirs, static assets. A future server-repo audit is the natural complement to this run.
