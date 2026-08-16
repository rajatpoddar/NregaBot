# NREGA Bot — Architectural & Engineering Audit + Improvement Plan

**Audit date:** 16 Aug 2026 · **Scope:** entire desktop app (root repo) + Flask server (`nrega-server/`)
**Method:** read-only inspection of the full codebase — source, config, migrations, Docker files, build scripts, CI, docs, and git state. Every finding below was verified from code; nothing is assumed.

> ⚠️ **Audit-phase only.** No source file was modified. The only file created is this one.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview (verified architecture)](#2-system-overview)
3. [The 30 Analysis Areas](#3-the-30-analysis-areas)
4. [Issue Register (severity → evidence → fix)](#4-issue-register)
5. [Prioritized Roadmap (Phase 0–6)](#5-prioritized-roadmap)
6. [Quick Wins / Medium / Architectural / High-Risk / Do-Not-Change](#6-change-classification)
7. [What Should Be Preserved](#7-what-should-be-preserved)
8. [Verification Notes](#8-verification-notes)

---

## 1. Executive Summary

NREGA Bot is a **production, revenue-generating** desktop automation product (~200+ active users, Jharkhand core + expanding states) paired with a Flask-based license/WhatsApp/analytics backend. The codebase is large: **~62,000 LOC desktop (Python)** (37,154 in `src/tabs/` alone, 55 tabs) and **~29,000 LOC server**, evolved rapidly over ~123 (desktop) + ~296 (server) commits.

**Overall assessment: the system is pragmatic, feature-complete, and has several genuinely well-engineered areas** (SHA-256-verified update pipeline, lazy tab loading, DPDP PII masking, server-driven state registry, signed tokens, error-spike monitoring). It is NOT an architecture that needs rewriting.

**The three most urgent issues are operational/security, not architectural:**

1. **CRITICAL — Real production secrets are committed to the `nrega-server` git repo** (`.env`, `.env.dev`, both service-account JSONs, `hooks.json`). The ignore rules exist but were added *after* the files were committed, so git keeps tracking them.
2. **HIGH — No rollback path for the self-update pipeline.** A bad release boots users into a crash loop with no "last-known-good" fallback (`extract_zip()` deletes the previous `app_live` before extracting).
3. **HIGH — Near-zero automated test coverage.** The desktop app has *zero* unit/integration tests; the server has 6 small unit tests. CI validates locales + imports only. For a product that ships weekly and mutates government financial data, this is the biggest silent risk.

Secondary themes: unpinned desktop dependencies (non-reproducible builds), duplicated Selenium/alert boilerplate across 55 tabs, fragile multi-worker scheduler pattern on the server, license-key-as-bearer-token with no rotation, MAC-address device binding, and a single-NAS single-point-of-failure deployment.

The roadmap in [§5](#5-prioritized-roadmap) is ordered so that **Phase 0 items are doable in days, not months**, and nothing in it requires a rewrite.

---

## 2. System Overview

### 2.1 Repository layout (two independent git repos!)

| | Desktop app | Server |
|---|---|---|
| Root | `.` (GitHub `rajatpoddar/NregaBot`, branch `main`) | `nrega-server/` (NAS git, branch `master`) |
| Entry | `loader.py` → `main_app.py` (`run_application()`); Lite: `lite_loader.py` → `lite_app.py` | `run.py` (gunicorn `run:app`, 3 workers × 4 threads default) |
| Stack | Python 3.11, CustomTkinter/Tk, Selenium (Chrome CDP :9222 / Edge :9223 / Firefox), SQLite (WAL) | Flask 3.1, gunicorn, PostgreSQL 14, Redis, Celery, Evolution API (WhatsApp), WebDAV |
| Deploy | PyInstaller loader EXE + signed `core_{win,mac}_vX.zip` | `docker-compose` on NAS `192.168.29.101` (6 services + webhook) |

### 2.2 Desktop startup & execution flow (verified)

```
loader.py (splash + update check + SHA-256 verify + extract to app_live)
  └─ main_app.run_application()
       ├─ single-instance guard (bind 127.0.0.1:60123, 'focus' signal)
       ├─ NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)
       │    ├─ AppState dataclass (src/state.py) — all state centralized;
       │    │   ~20 delegation properties on NregaBotApp keep old self.app.<attr> working
       │    ├─ _background_initialization() thread → staged UI build (_finish_startup)
       │    ├─ perform_license_check_flow() → check_license() (license.dat) →
       │    │   background validate_on_server() + _ping_server_in_background() (20s loop)
       │    └─ lazy tab loading: tab_config._lazy_import() (thread-locked),
       │        tabs import selenium/pandas only when first opened
       └─ automation: start_automation_thread(key, target, args) → daemon thread →
            wrapper() → finally → on_automation_finished() → activity log + cloud sync +
            usage-stats sync + WhatsApp notify
```

### 2.3 Desktop ↔ server communication (verified)

- HTTPS REST, JSON. **Bearer token = the raw license key** (`Authorization: Bearer <key>`), verified by `token_required` (`nrega-server/app/utils.py`) with a DB lookup on every call.
- Endpoints (~60 total): `/api/validate`, `/api/heartbeat` (~20s), `/api/app-config` (~120s), `/api/activity-log/sync`, `/api/usage-stats/sync`, `/api/automation-results/sync`, `/api/location-data/sync|get`, `/api/crash-report`, `/api/notify-settings`, payments (`/api/create-order`, `/verify-payment`, Razorpay webhook), OTP/trial/login, deactivation, storage.
- Web: Flask sessions (30-day permanent), signed one-time tokens for buy/auth links (`itsdangerous`), WebAuthn passkeys, Google OAuth.
- No WebSocket/push: desktop polls; WhatsApp notifications flow server → Evolution API → user phone.

### 2.4 Database (verified)

- **Server:** PostgreSQL 14. 29 SQL migrations (`nrega-server/migrations/`) applied at container start under `pg_try_advisory_lock(42)` to avoid multi-worker DDL races. Tables: licenses, otp_store, payments, user_files, activity_logs (+ archive), usage_stats, portal_states, location_data_pool, renewal_reminders, storage_warnings, data_deletion_warnings, message_logs, whatsapp_chat, admin_audit_logs, etc. `models.py` uses a small pool (`get_db_conn`/`release_db_conn`).
- **Desktop:** SQLite WAL (`nrega_local_db.sqlite`) — suggestions, usage_stats, activity_log (trimmed to last 2000 rows), tab_inputs. `history_manager.py` is the single owner (thread-locked).
- **Backup:** separate `postgres:14` container `pg_dump`s nightly to `backups_new/` (30-day retention). DB-only — user files are on the NAS volume / R2.

### 2.5 NREGA business domain (verified surface)

Tabs map to MGNREGA / VB-G-RAM-G portal operations: Demand, Work Allocation, Muster Roll Gen, MR Fill, MR Payment (MSR), Wagelist Gen/Send, FTO Generation, eMB Entry/Verify, Work Code Gen, IF Editor, Update Estimate, Physical Complete, Scheme Closing, Job Card / ABPS / eKYC verify, MR Tracking, MIS/Dashboard Reports, Pending Bills, SAD (Sarkar Aapke Dwar), plus utilities (PDF Merger, Macro Manager, WhatsApp Chat, File Manager). Business logic is embedded in tab files (Selenium flows), config dicts (`src/config.py` per-automation URLs/form defaults), and the server-driven `portal_states` registry.

---

## 3. The 30 Analysis Areas

Legend: ✅ good · ⚠️ watch · ❌ problem

### 3.1 Complete repository structure
✅ Clear separation: `src/` (app), `src/tabs/` (55 tabs), `src/app/` (mixins), `src/managers/`, `scripts/` (60+ build/migration scripts), `docs/` (deep documentation), `nrega-server/` (independent repo with `app/routes/{api,admin,frontend,file}`, `app/services`, `app/repositories`, `app/templates`, `migrations/`, `tests/`, `web/`).
❌ **Stray/dev artifacts in the root repo:** `server_loop.py` is **tracked in git**; `server.log`, `server_0.log`, `server_direct.log`, `single_server.log`, `direct_server.log`, `background_server.log`, `persistent_server.log`, `persistent_server2.py` sit untracked in the working tree. Three of the four "login page" server scripts are byte-identical duplicates.

### 3.2 Desktop Tkinter architecture
✅ Mixin decomposition (License/Nav/Automation/UI), centralized `AppState` dataclass with typed fields, delegation properties for backward compat, lazy tab loading with import lock, staged UI build with splash fade, single-instance socket guard.
✅ Guard rails are real: `safe_after()`/`AfterTracker`, `_is_alive()`, `winfo_exists()` checks everywhere, thread→UI via `after(0, ...)`.
❌ `on_closing()` ends with `os._exit(0)` — deliberately skips all teardown (see 3.25).
❌ `lite_app.py` (1,786 lines) duplicates large parts of `main_app.py` instead of parameterizing the full app (Lite config override pattern exists but the app class is still copy-pasted).

### 3.3 Flask server architecture
✅ Blueprint-per-area (`api`/`admin`/`frontend`/`file`/`website`), repository layer for newer features, services layer, validation schemas (`validation.py`), rate-limit registry, CORS restricted to 2 origins, security headers (CSP, nosniff, frame-deny), structured JSON logging, Prometheus metrics.
❌ Route files are very large (`api/auth.py` 844 lines, `api/payments.py` 764, `frontend/pages.py` 725, `admin/activity.py` 688, `api/automation_results.py` 663) — most logic is in routes, not services (services layer exists but is thin for older features).
❌ Schedulers/monitors start in **every gunicorn worker** (`run.py`); single-winner is enforced with `fcntl` locks (backup_scheduler, uptime_monitor) or Redis locks (AI warmup) — mitigated but fragile (see 3.14).

### 3.4 Desktop ↔ server communication
✅ Reasonable API surface; client uses one `requests.Session`; heartbeat + app-config polling; sync endpoints are PII-masked at the boundary and rate-limited per-key + per-IP.
❌ `GET /api/app-config?license_key=<key>` puts the **license key in a query string** (server access-log/proxy exposure) — inconsistent with the project's own "key kabhi URL mein nahi" policy adopted for buy/auth links.
❌ Client sends the raw key as a bearer token on every sync; a leaked key = full account takeover (see 3.9).

### 3.5 Application startup & execution flow
✅ Loader: dev-mode skip, `core.zip` SHA-256 verification per platform, write-version-after-extract (fixed a real stuck-update bug), heal logic, version read from `.pyc` on Windows.
✅ App startup: background init thread, staged UI, license flow, updates in background.
❌ **No rollback to last-known-good.** `extract_zip()` does `shutil.rmtree(EXTRACTED_DIR)` then extracts. If the new build crashes on launch (import error, broken migration of local DB), the user is stuck in a boot loop with only an error dialog; the loader has no "N launches crashed → revert to previous core.zip" mechanism (there is no previous core.zip kept).

### 3.6 NREGA business logic
✅ Domain knowledge is deep and tab-scoped; state registry makes new states addable without a release; demand auto-detection, workcode truncation (privacy), FY-aware report folders.
❌ Business logic is embedded in UI files with little separation — a portal layout change requires editing UI-heavy tab code (the `mr_fill_tab.py` Chrome-150 alert fix in the working tree is a recent example of portal-change fragility).
❌ Per-state config is duplicated between `src/config.py` fallbacks, `PENDING_BILLS_CONFIG`, and the server registry (acknowledged in AGENTS.md §4.5 as pending work).

### 3.7 Selenium/browser automation
✅ Three-browser support (Chrome/Edge via CDP debug port, Firefox managed), tab-marker JS + CDP `Page.setWebLifecycleState` to keep hidden tabs "active", per-run browser-choice cache, driver cleanup in the wrapper's `finally` (not in tab `destroy()` — correct).
❌ **Massive duplication of low-level Selenium boilerplate:** 55 tabs each re-implement waits/alerts/selects. `WebDriverWait` appears 10× in `demand_tab.py`, 9× in `issued_mr_report_tab.py`; alert handling appears 35× in `wagelist_send_tab.py`, 24× in `delete_applicant_tab.py`; `time.sleep` fixed-wait polling: 21× in `issued_mr_report_tab.py`, 20× in `dashboard_report_tab.py`, 16× in `mis_reports_tab.py`. The Chrome-150 "No dialog is showing" change had to be patched tab-by-tab.
❌ Fixed sleeps make runs slow and flaky; a shared "portal interaction" helper layer (wait, select, alert accept with retry, screenshot-on-fail) would cut both bugs and runtime.

### 3.8 Database & data flow
✅ Server: advisory-locked migrations, sane indexes, archive table for activity logs, repos for newer modules. Desktop: single SQLite owner with WAL + busy timeout.
❌ `SELECT * FROM licenses WHERE key = %s FOR UPDATE` on **every `/api/validate`** (and validate fires on window focus) — row lock + write (`last_seen`) per call; fine at 200 users, a scaling risk at 10k (validate should be read-mostly with a separate write path).
❌ Desktop `activity_log` is trimmed to 2000 rows and sync is only attempted at automation finish — if the app is closed for days, offline entries accumulate and a single batch of 50 syncs per run means slow catch-up (acceptable, but worth a startup catch-up sync).

### 3.9 Authentication & authorization
✅ OTP flow (10-min expiry, per-identifier, rate-limited 3/min), trial creation, device-slot model with pending deactivation, admin session auth, passkeys (WebAuthn), Google OAuth, signed one-time buy/auth tokens (raw key never in URLs — good), 30-day permanent web sessions.
❌ **License key = password-equivalent credential, used directly as a bearer token, stored in plaintext `license.dat`, and included in:** crash-report payloads (`src/utils.py _read_license_key`), admin deactivation notification emails (full key in body, `api/auth.py request_deactivation`), welcome emails. No key rotation, no per-request signature, no expiry enforcement client-side beyond local clock (`services.check_license` compares `datetime.now()` against `expires_at` — **client clock can be rolled back**; the server re-validates, so impact is limited to offline grace).
❌ **Machine ID = MAC address** (`get_mac_address()`), spoofable and unstable across VPN/adapters; device-slot binding is the weakest link of the licensing model.
❌ `FLASK_SECRET_KEY` falls back to `'a-very-secret-key'` (`app/__init__.py`) with only a warning — combined with 3.1's committed `.env`, the real key is already in repo history anyway.

### 3.10 API architecture
✅ Consistent `{status, reason}` JSON envelope, `APIError` handler, global 404/405/429/500 handlers, validation schemas, rate limits (Flask-Limiter, per-key + per-IP registry in `rate_limit_config.py`), health endpoints, prometheus metrics.
❌ `/api/validate` does business logic (device activation, version notify, storage calc) inline — 844-line route; webhook (`/razorpay-webhook`, `/whatsapp-chat/webhook`) signature verification should be double-checked for Razorpay (payment_service exists — verify webhook secret enforced in tests; currently no test covers it).

### 3.11 Error handling
✅ Desktop: `translate_error()` maps raw Selenium errors to friendly Hinglish, structured `error_type/error_source/error_traceback` for admins, failure screenshots (opt-in, local-only), crash reporter (file + masked server upload), `handle_error()` scheduled on main thread.
✅ Server: global handlers, error-spike monitor (per-automation fail-rate → admin WhatsApp), uptime monitor.
❌ **40 bare `except:` in tabs** + pervasive `except Exception: pass` swallow failures silently — combined with `print()` (28 uses in tabs/managers instead of the logger), real bugs hide. The Chrome-150 alert issue shipped because the failure mode was swallowed as "no alert".

### 3.12 Logging
✅ Desktop: centralized `setup_logging()`, rotating file (5 MB × 2), PII-masking **formatter** (covers tracebacks), crash log tail. Server: structured JSON logging, prometheus.
❌ Inconsistent: `print()` still used in tabs and `services.py`; several `logger.error(f"...")` calls with inline f-strings (fine, but style drift); loader writes its own `loader_log.txt` outside the app logger (acceptable, but unrotated).

### 3.13 Configuration & secrets
❌ **CRITICAL:** `nrega-server` git tracks `.env`, `.env.dev`, `google-sheets-service-account.json`, `firebase-service-account.json`, `hooks.json` (verified via `git ls-files`; `.env` touched in 24 commits, added in the initial commit). The `.gitignore` rules that would exclude them were added later — **tracked files are not retroactively ignored**. The NAS repo is private, but if it is ever cloned/pushed to GitHub, backed up off-NAS, or the NAS is compromised, all credentials (Postgres, Razorpay, Twilio, SMTP, R2, Google OAuth, Evolution API, Google/Firebase service-account private keys) are exposed.
✅ `.env.example` is a good documented template. Root `.env` is empty and ignored.
⚠️ Desktop `src/config.py` still carries a **hardcoded default** `EVO_API_KEY = 'NregaBotSecretKey123'` and `EVO_BASE_URL = 'http://192.168.29.101:8087'` (LAN IP in shipped client) — overridable via env, but the fallback is a known secret.

### 3.14 Threading / process management
✅ Desktop: daemon threads for everything network/automation, `stop_events` per automation, emergency stop-all, sleep prevention (caffeinate/SetThreadExecutionState), GC tuning, thread-pruning in the GC loop, `_marker_keeper` session cleanup in `finally`.
✅ Server: fcntl single-winner locks for schedulers, Redis lock for AI warmup.
❌ Gunicorn default **3 workers × 4 threads**: `start_scheduler`, `start_uptime_monitor`, `start_error_spike_monitor`, `start_release_sync`, webhook setup, AI warmup all execute in every worker process (locked, but lock-file semantics on shared NAS volumes are easy to get wrong — e.g. lock file on NFS/SMB).
❌ Desktop: every automation run spawns an extra CDP session (`_marker_keeper`) + a sync thread + a WhatsApp thread — acceptable, but worth noting that a single tab can hold 3–4 auxiliary threads alive for the run duration.

### 3.15 Network failure handling
✅ Desktop: offline-grace on license (startup validation failure → allowed), silent retry syncs, dedupe-cache commits only after successful sync (no data loss), update downloads verified + corrupt file deleted for retry.
⚠️ Offline mode: `validate_on_server` returns `True` on network error during startup check — deliberate, but it means an **expired license keeps working indefinitely while offline** (client clock check only). For a paid product, consider a bounded offline grace period.

### 3.16 Performance bottlenecks
✅ Startup: lazy tabs, thread-safe pandas lazy import, `ttk.Style` singleton, icon preload, `gc.freeze()`.
❌ Runtime: fixed `time.sleep` polling in report tabs (adds minutes to runs); `_extract_activity_details()` walks all treeview rows before+after every run (O(rows) × strings — fine for small runs, quadratic feel for large ones); `generate_report_image()` builds a 2400px-wide PIL image that grows in ~20-row chunks (large reports = transient multi-hundred-MB memory spikes on low-end machines — ironic for the "low-end device" target); `SELECT ... FOR UPDATE` on validate.
❌ Server: `heartbeat` writes `last_seen` on every ping from every user (~200 users × 1/20s = 10 writes/s at present scale, ×50 at 10k users); `app_config` does 6+ queries per poll.

### 3.17 Memory / CPU risks
❌ PIL report rendering (above) on low-RAM machines (Lite app targets these).
⚠️ Long automations + `_marker_keeper` every 2s CDP calls — CPU modest but constant.
✅ Periodic `gc.collect()` + thread pruning mitigates fragmentation; `gc.freeze()` at startup.
⚠️ Server: AI model warmup (qwen2.5:3b) on a NAS — documented OOM risk with 7B+ models, already constrained in `.env.example`.

### 3.18 Security vulnerabilities (see also 3.9, 3.13)
1. **CRITICAL:** secrets in server git history (3.13).
2. **HIGH:** license key as bearer token + plaintext storage + inclusion in crash payloads/emails (3.9). Crash-report payload contains `license_key` — the crash upload endpoint stores it; PII masking exists but the key itself is not masked anywhere by design.
3. **HIGH:** known `FLASK_SECRET_KEY` default fallback (3.9).
4. **MEDIUM:** `GET /api/app-config?license_key=` query-string exposure (3.4).
5. **MEDIUM:** `EVO_API_KEY` hardcoded default shipped to every client (3.13).
6. **MEDIUM:** no brute-force lockout on `/api/validate` (rate limit 30/min per IP is the only guard; a single leaked key can be validated repeatedly; low impact).
7. **MEDIUM:** WebDAV server (`webdav_server.py`) on port 8080 — needs auth review (not inspected in depth; flag for audit).
8. **LOW:** `server_loop.py` (tracked) is a toy HTTP server — harmless but signals dev-artifact hygiene issues.
9. **GOOD:** CSP, nosniff, frame-deny, CORS allowlist, signed tokens, server-side PII masking, admin audit log.

### 3.19 Dependency problems
❌ **Desktop `requirements.txt` is entirely unpinned** (Pillow, selenium, pandas, etc.). PyInstaller builds are non-reproducible; a transitive bump can break a release (the documented "humanize incident" — AGENTS.md rule #5 exists because of it). Hidden-import lists are hand-maintained in *two* build scripts + the .spec file — easy to drift.
✅ Server `requirements.txt` is pinned exactly; Dockerfile + docker-compose are reproducible.
⚠️ `webdriver-manager` (WDM) in desktop reqs — the browser_manager builds driver services manually (`_create_driver_service`) but WDM is still a dependency; mixed driver-management approaches.

### 3.20 Code duplication
- `lite_app.py` ≈ big copy of `main_app.py` (1,786 vs 1,145 lines) with a `lite_config` override layer — the override pattern exists; the class duplication doesn't need to.
- 4 near-identical local HTTP "login page" server scripts (3 tracked/untracked in root).
- Selenium wait/alert/select boilerplate across 55 tabs (3.7).
- License-key fetch pattern duplicated in tabs (`self.app.license_info.get('key')` + `Authorization` header) — small, but a `self.app.auth_headers()` helper would remove ~10 copies.
- `parse_version` exists in both `src/utils.py` and `history_manager.py` (near-identical).
- Error-translation/alert-accept logic varies per tab (the Chrome-150 fix added `_wait_for_submit_alert` to mr_fill; `wagelist_send_tab` has its own helper).

### 3.21 Architectural inconsistencies
- License state: mostly centralized in `AppState` via properties, but `about_tab.py` keeps its own `self.license_info` copy; `services.py` and mixins both mutate the same underlying dict through properties — works, but the two access styles (`self.app.x` vs `self.app_state.x`) coexist across the codebase.
- `src/config.py` holds *both* static constants and **runtime-mutated state** (`update_state_registry()` mutates module dicts at runtime from a heartbeat thread) — works, but makes config module stateful/global; a data race is possible if a tab reads while the registry is being replaced (dict swap is atomic in CPython, so low risk).
- Server: some features use repositories (newer), most use direct SQL in routes (older) — two idioms.
- `PENDING_BILLS_CONFIG` vs `portal_states` registry — acknowledged duplication (AGENTS.md §4.5).

### 3.22 Technical debt
- 60+ one-off `scripts/migrate_*.py` codemods committed (they did their job; they are historical artifacts — prune or move to `scripts/archive/`).
- `docs/` contains many overlapping analysis docs (`ARCHITECTURE_ANALYSIS.md`, `OPTIMIZATION_PLAN*.md`, `PROJECT_ANALYSIS.md`, `comprehensive-analysis-report.md`, etc.) — analysis sprawl; this audit should be the single living doc going forward.
- `base_tab.py` is 2,422 lines (UI helpers + report rendering + error handling + serial helpers) — a god-module candidate.
- `generate_report_pdf` uses `str(cell).encode('latin-1', 'replace')` — **silently destroys non-Latin (Hindi) text in PDFs**; the PNG path handles Devanagari fonts correctly. Real bug for Hindi users.

### 3.23 Testing & missing coverage
❌ Desktop: **zero unit tests**; the only checks are `_smoke_test_tabs.py` (manual, instantiates tabs) and `scripts/check_imports.py` (import compile) — both manual, not in CI.
❌ Server: 6 unit tests (placeholders, broadcast personalization, queue pacing, usage-stats wiring, fmt_ist, audit resolve) — no tests for auth/validate/payments/webhook/OTP/license logic/rate limits, no integration tests against Postgres.
✅ CI (`release.yml`) does validate locale parity (nice) + import check, and builds Windows/macOS artifacts.
❌ No CI test job at all; no coverage tracking; no test for the critical update/heal logic in the loader.

### 3.24 Deployment & production-readiness
✅ Docker-compose with healthchecks, restart policies, env-file, separate backup container, `deploy.sh`/`deploy_quick.sh`, GitHub Actions builds Windows/macOS, version.json + hashes flow.
❌ **Single NAS = single point of failure** (app + DB + Redis + WhatsApp + backups + WebDAV all on one box). No off-site backup of `backups_new/` (Google Sheets push exists for licenses snapshot — good partial mitigation). No restore drill evidence.
❌ Windows smart update uses `updater.bat` (xcopy over a running exe, `os._exit(0)` immediately) — no checksum on the installer zip at apply time (the zip hash is checked at download; the .bat copies blindly). If the .bat fails, the user has a half-updated install with no automatic recovery.
⚠️ `hooks.json` deploy paths + `docker.sock` mount in the webhook container = container escape surface if the webhook image is compromised.

### 3.25 Backup & data-loss risks
- **Server DB:** nightly pg_dump to the same NAS, 30-day retention. Single-machine — a NAS disk failure loses DB *and* backups together. Google Sheets daily snapshot is the only off-box copy (licenses only).
- **User files:** `user_uploads/` on the NAS volume; R2 (Cloudflare) referenced in env — file storage location should be confirmed; `MAX_STORAGE` 500 MB default per user, 2 MB per file.
- **Desktop:** user data in `~/Downloads/NregaBot/` (reports) + `user_data_dir` (config, license, SQLite). Cloud backup exists for suggestions/tab-inputs (`/api/user-data/backup`). Local DB has no backup of its own; `os._exit(0)` on quit can leave the SQLite WAL uncheckpointed (WAL is crash-safe, so risk is low, but a periodic `PRAGMA wal_checkpoint` on clean close is trivial).

### 3.26 Reliability & recovery mechanisms
✅ Desktop: SHA-256-verified updates, heal logic, corrupt-download retry, silent retry syncs, dedupe-after-success, error screenshots, crash reporter, emergency stop, driver cleanup in `finally`.
✅ Server: restart policies, healthchecks, uptime + error-spike monitors, rate limiting, activity-log archiving.
❌ No last-known-good rollback on desktop updates (3.5). No automated canary — a bad release hits all users at once (mitigated by the same-version hotfix mechanism, which at least allows quick re-release).

### 3.27 UI/UX problems
✅ Polished: theme-aware colors centralized, splash fade, toasts, onboarding, tab search (Ctrl+K), keyboard shortcuts (Ctrl+Enter/S/R), running-automation chips with progress %, treeview auto-switch to Results on finish.
❌ 55 tabs in a sidebar = discovery problem (partially solved by search + categories).
❌ Hardcoded English strings remain in tabs (e.g., `base_tab._create_action_buttons` hardcodes `"↻ Retry Failed"`; `mr_fill_tab` logs "Manual Mode: Paused") while 1,097 keys × 5 locales exist — translation drift.
❌ PDF export corrupts Hindi text (3.22) — a UX bug for the primary audience.
⚠️ `messagebox`-based flows (activation, updates) are modal and blocking; toasts mitigate but several critical paths still use modal dialogs on the main thread.

### 3.28 Maintainability
✅ Excellent documentation (AGENTS.md is genuinely the best part of this repo), consistent naming, centralized colors/logging/state, migration discipline, changelog in version.json.
❌ Tab count + per-tab boilerplate = high maintenance surface per portal change; god-module `base_tab.py`; two state-access idioms; analysis-doc sprawl; unpinned deps make "works on my machine" a real failure mode.

### 3.29 Scalability
- Current: 200 users on a NAS. Server is single-instance (3 workers); Postgres on the same box; Redis single node; Celery single worker.
- 10k users will require: managed Postgres (or at least off-NAS DB), CDN for the update zips (Cloudflare already fronts the domain), worker/queue separation (already Celery-shaped), validate-path read optimization (remove `FOR UPDATE`), heartbeat batching, app-config caching. The project's own `docs/SCALING_PLAN_200_to_10000.md` covers this correctly — the plan is sound; the gap is execution backlog (deploy backlog acknowledged in the doc).
- Desktop: 55 tabs with lazy loading scale fine; the per-tab Selenium boilerplate is the bottleneck for *feature velocity*, not runtime scale.

### 3.30 What should be preserved (don't rewrite)
1. **Loader/update pipeline** (SHA-256, platform hashes, heal, .pyc version read, write-after-extract) — genuinely careful; add rollback, don't replace.
2. **AppState centralization + delegation properties** — clean seam for future refactors.
3. **Lazy tab loading + thread-safe import locks** — startup is fast because of this.
4. **DPDP PII masking architecture** (formatter-level masking, boundary masking, workcode truncation) — hard-won compliance; extend, don't redo.
5. **Server-driven config** (state registry, app-config, feature flags, admin pricing) — this is the right pattern; expand it.
6. **Signed-token URL policy** (no raw keys in URLs) — keep and extend to the remaining query-string case.
7. **Rate-limit registry + validation schemas + repositories (newer modules)** — the target idiom; backfill old routes to it incrementally.
8. **Monitoring stack** (uptime, error-spike, prometheus) — small and effective.
9. **The two-repo split + migration discipline + advisory-locked DDL** — correct for this deployment.

---

## 4. Issue Register

For each issue: **Severity · Evidence · Why it matters · Recommended fix · Complexity · Risk of changing · Expected benefit.**

### CRITICAL

#### C1. Production secrets committed to the server git repo
- **Evidence:** `git -C nrega-server ls-files` → `.env`, `.env.dev`, `google-sheets-service-account.json`, `firebase-service-account.json`, `hooks.json` are tracked (`.env` in 24 commits; added in initial commit `9d4cb9e`). `.gitignore` rules exist but don't un-track files.
- **Why:** Full credential compromise (Postgres, Razorpay, Twilio, SMTP, R2, Google OAuth, service-account private keys) the moment the repo leaves the NAS or the NAS is breached. Also blocks safe onboarding of a second developer.
- **Fix:** (a) rotate all secrets now; (b) `git rm --cached` the files + commit; (c) purge history with `git filter-repo` (create a fresh repo mirror on the NAS); (d) verify no secret strings remain with a scan; (e) document that `.env*`, `*-service-account.json`, `hooks.json` are never `git add`ed.
- **Complexity:** Medium (rotation is the slow part; history purge is scripted).
- **Risk of changing:** Medium — must be done carefully on the NAS repo with a full backup first; the app/server keep working during it.
- **Benefit:** Eliminates the single most dangerous exposure in the product.

#### C2. No rollback for the desktop self-update pipeline
- **Evidence:** `loader.py extract_zip()` does `shutil.rmtree(EXTRACTED_DIR)` before extracting; `core.zip` is overwritten at download time; the only heal logic fixes version-file mismatch, not a crash-looping new build.
- **Why:** One bad release (import error, broken locale, bad local-DB migration) permanently breaks every user's app until a manual reinstall or a *new* release. For a tool that government clerks depend on daily, that's a support fire.
- **Fix:** Keep `core_prev.zip` + a "boot counter" file: if the app crashes within N seconds of launch M times in a row (detected in the loader before `main_app` import), extract `core_prev.zip` and offer the error to the server. Ship a "Roll back to previous version" button in the loader error dialog.
- **Complexity:** Medium. **Risk:** Low–Medium (additive; must not break the existing verified flow). **Benefit:** Turns every future bad release from a fire into a no-op.

### HIGH

#### H1. Near-zero automated test coverage
- **Evidence:** root repo: no `test_*` files; `_smoke_test_tabs.py` + `check_imports.py` are manual. Server: 6 unit tests only; no CI test job.
- **Why:** Weekly releases mutate financial data; regressions (like the Chrome-150 alert regression visible in the working tree) ship to production. No safety net for refactors the roadmap proposes.
- **Fix:** Phase 5 — start with (a) pytest for `src/utils.py` (masking, parse_version, truncate_workcode, translate_error) — pure functions, zero GUI; (b) pytest for server validation/schemas, `security.py` tokens, OTP logic, `token_required` (mock DB); (c) loader update/heal logic unit tests (mock requests + zipfile); (d) CI job `pytest` + coverage gate.
- **Complexity:** Low start → Medium. **Risk:** Low. **Benefit:** Highest leverage change in the whole plan.

#### H2. License key = bearer token, plaintext on disk, embedded in crash payloads/emails
- **Evidence:** `nrega-server/app/utils.py token_required` (DB lookup by raw key); `src/managers/services.py` `check_license()` reads plaintext `license.dat`; `src/utils.py _read_license_key()` puts key in crash payload; `api/auth.py request_deactivation` emails full key to admin; `send_welcome_email` embeds key in user emails.
- **Why:** Key theft = account takeover (no rotation, no MFA on the desktop flow). Key in emails is industry-standard for license keys, but combined with plaintext disk + crash uploads the blast radius is wide.
- **Fix (in order of value):** (a) rotate-key capability in admin panel + `/api/rotate-key`; (b) stop sending the raw key in crash payloads (send machine-id + license hash); (c) mask key in admin emails (show last 4); (d) keep `license.dat` but add OS-level protection on Windows (DPAPI) / macOS (Keychain) — or at least document the tradeoff.
- **Complexity:** Medium. **Risk:** Medium (auth changes touch every client call). **Benefit:** Reduces account-takeover blast radius dramatically.

#### H3. Known-default `FLASK_SECRET_KEY`
- **Evidence:** `app/__init__.py` — `os.environ.get('FLASK_SECRET_KEY', 'a-very-secret-key')`, warning only.
- **Why:** Forgeable session cookies + signed tokens if env is missing in any deployment (staging, dev boxes, a future cloud deploy). C1 makes the *real* key public to repo readers anyway.
- **Fix:** Fail hard at startup when unset in production (`if os.environ.get('FLASK_ENV') == 'production' and SECRET_KEY == default: raise`), plus rotate (part of C1).
- **Complexity:** Low. **Risk:** Low. **Benefit:** Removes a silent-weakness class.

#### H4. PDF export corrupts Hindi/Devanagari text
- **Evidence:** `base_tab.generate_report_pdf()` → `str(cell).encode('latin-1', 'replace').decode('latin-1')`.
- **Why:** Primary users are Hindi speakers; exported PDFs silently show `?`/garbage. The PNG path already handles Devanagari — inconsistent and embarrassing for a "professional report" feature.
- **Fix:** Use `fpdf2` with a Unicode font (the repo already bundles NotoSansDevanagari for PNG) or route PDF export through reportlab with the Devanagari TTF.
- **Complexity:** Low–Medium. **Risk:** Low. **Benefit:** Correct output for the core audience.

#### H5. Machine-ID = MAC address
- **Evidence:** `src/managers/services.py _get_machine_id()` → `get_mac_address() or uuid.getnode()`.
- **Why:** Spoofable, changes with VPN/adapters → support calls "my license stopped working", and easy to bypass for a determined pirate (they'd just spoof; note the device-slot model's purpose is *limits*, not piracy — but unstable IDs create real user pain).
- **Fix:** Composite ID (MAC + motherboard/volume serial on Windows via `wmic`/registry, `ioreg` on macOS) hashed with a salt; keep backward compatibility by accepting legacy IDs.
- **Complexity:** Medium. **Risk:** Medium (device re-activation churn on upgrade — ship a migration window where old and new IDs both validate). **Benefit:** Fewer support tickets; stronger slots.

### MEDIUM

#### M1. Desktop dependencies unpinned / hand-maintained hidden imports
- **Evidence:** `requirements.txt` (no versions); `build_windows.bat`, `build_macos.sh`, `NREGABot.spec` each list hidden-imports; the "humanize incident" documented in AGENTS.md rule #5.
- **Fix:** Pin versions in `requirements.txt` (or `requirements-lock.txt` for build), add a CI check that `.spec`/build scripts' hidden-import lists match `src/tabs/` modules (a small script), and auto-generate the tab list (build_macos.sh already loops `src/tabs/` — replicate for Windows).
- **Complexity:** Low–Medium. **Risk:** Low. **Benefit:** Reproducible builds; fewer release-time surprises.

#### M2. Selenium boilerplate duplication across 55 tabs
- **Evidence:** counts in §3.7 (`time.sleep` 21× in one tab, alert handling 35× in another; the Chrome-150 patch had to be applied per-tab).
- **Fix:** Add a `PortalDriver`/`portal_utils` helper module: `wait_and_click`, `select_safe` (already in AutomationMixin), `accept_alert_retry` (exists in 2 tabs — promote), `safe_sleep` that polls stop_event, screenshot-on-fail, unified exception translation. Migrate tabs incrementally (top-10 by alert/sleep count first).
- **Complexity:** Medium. **Risk:** Medium (touches every tab; do it tab-by-tab with the smoke test + a portal session). **Benefit:** Faster portal-change fixes, less flakiness, shorter runs (replace sleeps with wait conditions).

#### M3. `GET /api/app-config?license_key=` query-string exposure
- **Evidence:** `api/auth.py app_config()` reads `request.args.get('license_key')`.
- **Fix:** Move to `Authorization: Bearer` (client already has the header pattern) — the endpoint is called from the heartbeat loop with the key available.
- **Complexity:** Low. **Risk:** Low (coordinated client+server release). **Benefit:** Removes the last raw-key-in-URL case.

#### M4. Multi-worker scheduler pattern (server)
- **Evidence:** `run.py` starts schedulers in every process; `backup_scheduler.py`/`uptime_monitor.py` use fcntl single-winner; gunicorn defaults 3 workers.
- **Fix:** Move schedulers/monitors into the Celery worker (single process) or a dedicated `scheduler` container; keep fcntl as belt-and-suspenders.
- **Complexity:** Medium. **Risk:** Medium (timing changes for backups/reminders). **Benefit:** Removes a whole class of duplicate-message/duplicate-email bugs.

#### M5. `/api/validate` write path on every call
- **Evidence:** `SELECT ... FOR UPDATE`, then `UPDATE last_seen`, storage SUM, version-notify check, device activation — all in one route called on focus + startup.
- **Fix:** Split: read-only validate (cache valid/invalid for 60s), separate heartbeat write path (already exists), device activation only on change. Add an index check on `licenses(last_seen)`.
- **Complexity:** Medium. **Risk:** Medium (auth logic). **Benefit:** Scales to 10k without DB contention; faster focus-time UX.

#### M6. Root-repo hygiene: tracked `server_loop.py` + log files + duplicated dev servers
- **Fix:** `git rm server_loop.py`, delete the `server*.log`/`persistent_server*.py` working-tree files (confirm with user first), archive the 60+ one-off `scripts/migrate_*.py` into `scripts/archive/`, and consolidate `docs/` analyses into this plan + AGENTS.md.
- **Complexity:** Low. **Risk:** Low. **Benefit:** Onboarding clarity; smaller clone.

#### M7. `EVO_API_KEY` hardcoded default in shipped client
- **Evidence:** `src/config.py` — `EVO_API_KEY = os.environ.get('EVO_API_KEY', 'NregaBotSecretKey123')`.
- **Fix:** Remove the fallback (fail with a clear message if unset) — the value is already public; anyone can call the local Evolution API if they reach the LAN.
- **Complexity:** Low. **Risk:** Low. **Benefit:** Removes a known-secret from every client install.

#### M8. Hardcoded UI strings alongside the i18n system
- **Evidence:** `base_tab.py` "↻ Retry Failed", `mr_fill_tab.py` "Manual Mode: Paused", etc., while 1,097-key × 5-locale files exist and CI enforces parity.
- **Fix:** Sweep hardcoded strings into `en.json`/`hi.json` + part files (the CI-validated workflow exists). Add a CI lint that fails on `CTkButton(text="..."` with non-placeholder strings.
- **Complexity:** Low–Medium. **Risk:** Low. **Benefit:** Consistent 5-language UX.

#### M9. `os._exit(0)` on quit / uncheckpointed SQLite
- **Evidence:** `main_app.py on_closing()` → `os._exit(0)`.
- **Fix:** On clean close, call `history_manager.close()` (exists), `PRAGMA wal_checkpoint(TRUNCATE)`, then `sys.exit`. Keep `os._exit` only as the force path.
- **Complexity:** Low. **Risk:** Low–Medium (shutdown ordering). **Benefit:** Cleaner data durability; closes SQLite cleanly.

#### M10. Single-NAS deployment = single point of failure
- **Evidence:** docker-compose runs everything on `192.168.29.101`; `backups_new/` is on the same disk.
- **Fix:** (a) nightly `pg_dump` → R2/backblaze (off-box); (b) at minimum, copy `backups_new/` off-NAS weekly; (c) document a restore drill. Google Sheets licenses snapshot is a good start — extend it to a full DB dump.
- **Complexity:** Low–Medium. **Risk:** Low. **Benefit:** Survives NAS disk failure.

### LOW

- **L1:** `lite_app.py` class duplication → parameterize the full app with the `lite_config` overrides instead of a parallel class. (Architectural, later.)
- **L2:** Analysis-doc sprawl in `docs/` → consolidate (tie to M6).
- **L3:** `SELECT * FROM licenses` in backup CSV / `expired_days_ago` filter duplicated per-template → small shared helpers.
- **L4:** `parse_version` duplicated (`utils.py` + `history_manager.py`) → single source.
- **L5:** WebDAV auth review (port 8080, `webdav_server.py`) — confirm it authenticates against the same user store.
- **L6:** `PREFERRED_URL_SCHEME` default `'http'` — assert `https` in production config.

---

## 5. Prioritized Roadmap

### PHASE 0 — Critical security / data-loss / reliability (do first, ~1–2 weeks)
| # | Item | Ref |
|---|---|---|
| 0.1 | Rotate ALL server secrets; remove `.env*`, service accounts, `hooks.json` from git tracking; purge history (`git filter-repo` on a NAS-repo mirror); add pre-commit secret scan | C1 |
| 0.2 | `FLASK_SECRET_KEY` hard fail in production + verify `.env` completeness at deploy (`deploy.sh` check) | H3 |
| 0.3 | Stop shipping the raw license key in crash-report payloads (hash it); mask keys in admin emails | H2 |
| 0.4 | Remove `EVO_API_KEY` known-default from client; move `/api/app-config` key from query string to header | M7, M3 |
| 0.5 | Off-NAS backup copy of `backups_new/` (R2/Backblaze) + document restore drill | M10 |
| 0.6 | Desktop update rollback: `core_prev.zip` + boot-counter crash detection | C2 |

### PHASE 1 — Stability
- 1.1 Fix PDF Hindi corruption (H4).
- 1.2 Replace top-10 worst fixed-`time.sleep` tabs with stop-aware wait conditions (M2 subset).
- 1.3 Graceful quit: checkpoint SQLite WAL, close history manager (M9).
- 1.4 `updater.bat`: verify installer hash before copy + write a "last known good" marker before applying (H-safety for updates).
- 1.5 Add index on `licenses(last_seen)` + cache `/validate` read path (M5 subset, low risk).

### PHASE 2 — Architecture & maintainability
- 2.1 Promote shared `portal_utils` (alert accept, select, click, screenshot) and migrate tabs incrementally (M2 full).
- 2.2 Split `base_tab.py` god-module (UI helpers / report rendering / serial helpers / error handling).
- 2.3 Move server schedulers into Celery/scheduler container (M4).
- 2.4 Consolidate root-repo dev artifacts + archive one-off scripts (M6).
- 2.5 Single-source `parse_version`, auth-header helper, alert helpers (L4, M2).

### PHASE 3 — Performance
- 3.1 `/api/validate` read/write split + 60s cache (M5).
- 3.2 Chunked/streamed PIL report rendering or hand off to a background thread with a size cap (memory spikes).
- 3.3 Heartbeat batching (server-side accept + async write).
- 3.4 Desktop: avoid full treeview re-scan in `_extract_activity_details` on every run start/finish (cache counts incrementally).

### PHASE 4 — UI/UX
- 4.1 i18n string sweep + CI lint for hardcoded strings (M8).
- 4.2 Fix PDF/PNG export consistency (fonts, Devanagari everywhere) (H4 follow-up).
- 4.3 Convert remaining modal `messagebox` flows on the main thread to non-blocking toasts where safe (activation, update prompts).

### PHASE 5 — Testing & observability
- 5.1 pytest for pure functions: `src/utils.py`, `history_manager` (SQLite in-memory), loader update/heal logic (mocked HTTP) (H1).
- 5.2 Server pytest: `validation.py` schemas, `security.py` tokens, `token_required`, OTP verify, trial dedupe; add Postgres test fixture for repo tests.
- 5.3 Wire `_smoke_test_tabs.py` + `check_imports.py` into CI (today they're manual).
- 5.4 Add Sentry or keep crash-report pipeline but add alerting on crash-rate spikes (client-side counterpart of the server error-spike monitor).
- 5.5 Coverage gate (start 40% on new code, ratchet up).

### PHASE 6 — Scalability & future
- 6.1 Execute the existing `docs/SCALING_PLAN_200_to_10000.md` backlog: managed Postgres, CDN for update zips, worker separation.
- 6.2 License-key rotation API + composite machine-ID (H2/H5).
- 6.3 Parameterize `lite_app.py` into the main app class (L1).
- 6.4 WebDAV auth hardening + file-storage audit (R2 vs NAS volume) (L5).
- 6.5 Consider canary: ship to 5% of users first (version.json already supports per-platform URLs; add a `rollout_pct`).

---

## 6. Change Classification

### ⚡ Quick wins (hours–days, low risk)
- C1 partial: `git rm --cached` secrets + commit + scan (rotation is the slow part).
- H3: fail-fast secret key. H4: PDF font fix. M3: app-config header. M7: remove EVO fallback.
- M9: clean SQLite shutdown. M10: off-NAS backup copy + restore drill doc.
- L4: dedupe `parse_version`. M6 partial: remove `server_loop.py` + log files from the repo.

### 🔧 Medium-sized improvements (days–weeks)
- H2: key rotation API + crash-payload key hashing.
- M1: pin desktop deps + auto-generated hidden-import CI check.
- M2 phase 1: shared `portal_utils` for the 10 worst tabs.
- M5: validate read/write split. M8: i18n sweep + lint.
- H1 phase 1: pytest for pure functions + CI job.

### 🏗️ Architectural changes (weeks–months, staged)
- M4: schedulers → Celery/scheduler container.
- M2 phase 2: migrate all tabs to `portal_utils`; split `base_tab.py`.
- H5: composite machine-ID with migration window.
- L1: unify full/Lite apps.
- 6.x: scaling plan execution.

### ⚠️ High-risk changes (require care, staging, or coordination)
- C1 history purge (`git filter-repo` on the NAS repo — back it up first).
- H2 full bearer-token redesign (if taken beyond rotation) — touches every client call; coordinate a client+server release.
- H5 machine-ID change — device-slot migration window required or users get re-activation failures.
- 3.2/3.3 validate/heartbeat rework — auth-adjacent; test against a staging DB.

### 🚫 Things that should NOT be changed
- The loader's verified-update architecture (SHA-256, platform hashes, heal, write-after-extract) — add rollback, keep the rest.
- `AppState` + delegation-property pattern.
- Lazy tab loading + import locks (including the pandas lock).
- DPDP PII masking design (formatter-level, boundary masking, workcode truncation).
- The two-repo split and the NAS-based deployment (until the scaling plan says otherwise).
- Server-driven config (state registry / app-config / admin pricing) — extend, don't replace.
- Signed-token URL policy.
- SQLite as the desktop local store (correct choice for this workload).
- CustomTkinter as the UI framework (rewriting the GUI would be the single highest-risk, lowest-return change possible here).

---

## 7. What Should Be Preserved

Beyond the "do not change" list, preserve the *culture* that produced the good parts: the AGENTS.md discipline (the best project documentation I've audited), the migration + changelog discipline, the PII-first thinking (DPDP), the incremental feature-telemetry approach, and the pragmatic "ship server-driven config, not releases" strategy. These are worth more than any single refactor.

---

## 8. Verification Notes

- **Repo state at audit time:** working tree had `AGENTS.md`, `config/version.json`, `src/tabs/mr_fill_tab.py` modified (uncommitted); no source file was touched by this audit.
- **Commands used (all read-only):** `git ls-files`, `git log`, `git check-ignore`, `wc -l`, `grep`/`rg` pattern counts, `find`, `cat` of config files (values redacted in this document).
- **Secret check:** this document contains no actual secret values; `.env` contents were redacted during inspection.
- **Known gaps (not inspected in depth):** `workflow_manager.py` internals, WebDAV auth, `web/` marketing-site code, Razorpay webhook signature verification path, `ai_bot.py` internals, and the `nrega-server/docs/` content. These are flagged as follow-up audit targets, not silently assumed safe.
