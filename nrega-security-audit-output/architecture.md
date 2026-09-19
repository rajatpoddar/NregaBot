# NregaBot Desktop — Architecture Summary (run `nregabot-run-1`)

## Product, principals, authority, protected resources

NREGA Bot is a licensed desktop automation tool (Python 3.11, CustomTkinter + Selenium) that drives the government MGNREGA/VB-G-RAM-G web portal through the user's own Chrome/Edge/Firefox, automating repetitive data entry for Panchayat-level operators. Principals: (1) licensed end user — same person whose browser session automates the portal; (2) vendor server `nregabot.com` (license, updates, cloud storage, telemetry, WhatsApp relay); (3) local attackers (other processes/OS users on the same machine); (4) network attacker (MITM). Protected resources: the license key (password-equivalent bearer token), worker PII (Aadhaar, bank, mobile — DPDP Act 2023 scope), portal session in the managed browser, local user data, and the update pipeline (code-execution authority).

Comparable baseline: standard commercial desktop app with auto-updater + license server (Squirrel-style). The codebase mostly meets that baseline: update payloads pinned to `https://nregabot.com/`, SHA-256 verified, downgrade-refused, empty-hash-refused (loader.py). Trade-offs the baseline accepts (plaintext local license file, launcher deep-links) appear here too.

## Tech stack, deployment paths, offline limits

PyInstaller loader (`loader.py`, 881 L; `lite_loader.py`, 706 L) downloads `core_{win,mac}_vX.zip` into `user_data_dir("NREGABot")/app_live`, verifies SHA-256 from `version.json`, extracts, and launches `main_app.py` (Full) / `lite_app.py` (Lite). Flask server code lives in `nrega-server/` — OUT OF SCOPE. Tests: `pytest -q` (306). All network calls are `requests`; no sandbox manager on host → **no target code executed this run (source-only)**.

## Entry surfaces

1. **Update pipeline**: loader.py + lite_loader.py + in-app update (src/managers/services.py, main_app.py `_apply_smart_update`) — code execution authority.
2. **License server APIs**: validate/OTP/OAuth/heartbeat/app-config/user-data backup (src/app/app_license.py, src/managers/services.py).
3. **Web portal deep-links**: `open_web_page()`/`get-auth-token` → `/authenticate-from-app/<token>?next=<dest>` (app_license.py:1645-1670); buy-link (1611).
4. **Cloud file manager**: upload/download/list/delete + WhatsApp-send (`/files/api/*`, src/tabs/file_management_tab.py, src/tabs/demand_tab.py:135, musterroll_gen_tab.py:910).
5. **Telemetry/sync**: crash-report, automation-results/sync, usage-stats, activity-log, location sync (src/utils.py:492, src/app/app_automation.py:610/692, src/tabs/history_manager.py:595/1153, src/location_sync.py).
6. **Local IPC**: single-instance socket on 127.0.0.1:60123 (main_app.py run_application), 60124 (Lite).
7. **Browser control**: Chrome/Edge launched with `--remote-debugging-port=9222/9223`, dedicated profile dirs (src/managers/browser_manager.py).
8. **Local file sinks**: reports under `~/Downloads/NregaBot/`, config.json, license.dat, state JSONs; `os.startfile`/`open` on generated reports; `updater.bat` generation (main_app.py `_apply_smart_update`).

## Trust boundaries and strongest source-visible controls

- **Internet → updater**: HTTPS host-pin (`https://nregabot.com/`), platform-specific SHA-256, empty-hash refusal, downgrade refusal, rollback on crash-loop (loader.py:662-680). Weakest sibling: lite_loader.py:436 accepts version-only updates (empty generic hash OK — documented); services.py in-app path verifies only when hash present (falls back to OS "open" of the downloaded file).
- **Server ↔ client license/data**: Bearer license key over TLS in Authorization header (never in URL, by design — app_license.py:1622); heartbeat `?license_key=` query param is the exception (app_license.py:1809).
- **PII → server**: masking choke points at every cloud boundary: `mask_columns_rows` in base_tab._extract_tree_columns_rows (src/tabs/base_tab.py:346), `mask_pii_text` in logs/crash reporter (src/utils.py:303-578), `mask_aadhaar_text` recursive in user-data backup (app_license.py:2120-2140), history_manager.py:898.
- **Local attacker ↔ app state**: license.dat chmod 600 via `save_license_dat` choke point (src/utils.py); other state JSONs (config.json, core_version.json, maintenance_mode.json, force_rollback.json, blocked_versions.json, boot_state.json) written world-default-perms via `_save_json_file`, and all are **read as trusted control input by loader/app** (rollback, blocked versions, maintenance, feature flags, update metadata in core_version.json).
- **Local IPC**: port 60123 loopback; any local process can send `focus` (benign) — no auth, minimal authority.
- **Server-driven config → app behavior**: `/api/app-config` writes maintenance/rollback/blocked-versions files and feature flags; `config.update_state_registry(data["states"])`; `global_disabled_features`.

## Source-to-sink paths of note

- Update: `version.json` → hash/url extraction → download → verify → `extractall` (zip, path traversal: Python's extractall rejects absolute/`..` on CPython) → relaunch (`Popen sh -c exec sys.executable`; Windows `updater.bat` xcopy of extracted dir → `os.startfile`).
- License file: server response merged with key → `save_license_dat` → on load, expiry checked **locally only** (`check_license`, services.py:53-67); no signature verification exists in `src/` (grep: no hmac/rsa/signature verify).
- Feature flags/disabled features from server → `_apply_feature_flags` gate automations.
- Web token: key → POST /api/get-auth-token → token in URL path → webbrowser.open.
- Cloud rows: results_tree → mask → POST; reports/Excel exports stay local & unmasked by design.

## Prior coverage gaps

None — no prior runs exist for this repo.

## Companion selection summary

- **SUPPLY-CHAIN-AND-RELEASE.md** — update pipeline, PyInstaller build, CI release workflow (.github/workflows/release.yml), whitelist packaging, generated locales. Boundaries: release authority, update trust.
- **DESKTOP-MOBILE-AND-LOCAL-IPC.md** — loopback IPC, local state-file trust, deep-link handoff (`authenticate-from-app`), credential-store boundary (license.dat plaintext), remote-debugging browser launch. Boundaries: local attacker ↔ app state.
- **WEB-PROTOCOL-AND-AUTH.md** — license key as bearer credential, OTP/OAuth flows, token-in-URL, query-param key, session/token handling. Boundaries: client ↔ license server identity.
- **DATA-ISOLATION-AND-LIFECYCLE.md** — PII masking boundaries, cloud backup/restore, deletion/retention of cloud rows, local SQLite history + server sync. Boundaries: user data → vendor cloud.
- **CLOUD-AND-DEPLOYMENT.md** — CI workflow permissions/secrets, server-driven kill-switches, version.json integrity. Boundaries: release/control-plane authority.
- Excluded: MEMORY-SAFETY-AND-BINARY (no native code), AI-AND-LLM, PROTOCOLS-RPC (no custom protocol), RESOURCE-EXHAUSTION (single-user desktop; no multi-tenant shared compute in scope), CLIENT-SIDE (no webview; Selenium drives the gov portal the user operates), ATTACK-CLASSES MFA/passkey subsections (no such flows).

## Starting paths

`loader.py`, `lite_loader.py`, `main_app.py`, `lite_app.py`, `src/utils.py`, `src/config.py`, `src/managers/services.py`, `src/managers/browser_manager.py`, `src/app/app_license.py`, `src/app/app_automation.py`, `src/tabs/file_management_tab.py`, `src/tabs/history_manager.py`, `src/tabs/base_tab.py`, `src/location_sync.py`, `.github/workflows/release.yml`, `scripts/build_update.py`, `requirements.txt`, `.gitignore`.
