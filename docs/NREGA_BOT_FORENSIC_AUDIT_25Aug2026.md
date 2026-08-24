# 🔍 NREGA Bot v3.2.7 — Full Production Forensic Audit Report

> **⚡ FIX STATUS (25 Aug 2026):** Is audit ke Phase-1 me se **9 low-effort/high-impact
> fixes APPLY ho chuke hain** (F1–F9) — details, issue→change→benefit breakdown aur
> validation results ke liye dekho:
> [`docs/AUDIT_FIX_PROGRESS_25Aug2026.md`](AUDIT_FIX_PROGRESS_25Aug2026.md)
>
**Audit date:** 25 Aug 2026
> **Scope:** desktop app root repo (`main` @ `6b5d175`) + build/CI pipeline. Server (`nrega-server/`) inspected only where it intersects the desktop supply chain.
> **Method:** read-only inspection of loader/update flow, licensing, threading, Selenium automation, data parsing, i18n, CI/build scripts, tests. Static checks executed: `pytest` (20/20 pass), `scripts/build_locales.py` (exit 0), `scripts/check_imports.py`, targeted runtime verification of suspect logic. **No code was modified.**
>
> 📁 *This report lives in `docs/` deliberately — see Finding S1: root-level `.md` files (AGENTS.md, NREGA_BOT_IMPROVEMENT_PLAN.md) currently ship inside `core_win_v*.zip` to every Windows user. Don't move this file to the repo root.*

---

## EXECUTIVE SUMMARY

| Dimension | Rating | Justification |
|---|---|---|
| **Overall health** | **6 / 10** | Mature, battle-tested product with real guard rails — undermined by release-pipeline hygiene and near-zero test coverage |
| **Security** | **5 / 10** | Good DPDP masking & HTTPS discipline; but integrity-only update verification, hard-coded API-key fallbacks, internal-infrastructure disclosure in shipped artifacts |
| **Reliability** | **6.5 / 10** | Rollback/heal system is genuinely good; several confirmed logic bugs in success detection and status reporting remain |
| **Architecture** | **7 / 10** | Mixin decomposition, centralized state, lazy loading all verified real; `lite_app.py` duplication and god-modules are debt, not blockers |
| **Release engineering** | **5 / 10** | Two divergent core-zip strategies (whitelist vs blacklist), unpinned dependencies, secrets bundled via `--add-data=".env:."` |
| **Testing maturity** | **2.5 / 10** | 20 tests total, all update-rollback. Zero tests for CSV parsing, financial year, license responses, retry semantics |

The system has visibly improved since `NREGA_BOT_IMPROVEMENT_PLAN.md` (16 Aug): boot-counter rollback ✅ implemented, blocked-versions ✅, locale CI gate ✅, pytest in CI ✅, crash-report PII masking ✅. However, the plan's Phase-0 items **0.4 (EVO key removal)** and the Windows-zip content problem are **still open**, and new issues were found that the previous audit missed (downgrade asymmetry between loaders, `'e' in locals()` dead-code bug, truncated-workcode retry loop).


---

## TOP 10 MOST IMPORTANT FINDINGS

### 1. 🔴 P0 — Windows core zip ships internal docs/dev files; one misstep from shipping server secrets

* **File:** `.github/workflows/release.yml` — "Create Core Zip (Windows)" step, lines 126–133
* **Function:** inline `ignore_func` / `shutil.copytree`
* **Problem:** macOS core zips use a **whitelist** (`scripts/build_update.py:40–73` — only `src/`, `config/`, `assets/`, limited `docs/`). The Windows step uses a **blacklist**: everything not in `['venv','.git','.github','dist','build','__pycache__','user_uploads','.env','.vscode','web','docs','scripts','backups']` ships to every Windows user, including:
    * `AGENTS.md` — contains internal NAS IP `192.168.29.101`, SSH user/path topology, deploy procedures
    * `NREGA_BOT_IMPROVEMENT_PLAN.md`, README dev guide, `tests/`, `_smoke_test_tabs.py`, `_audit_tab_layout.py`, `pytest.ini`, `jc_verify_prefs.json`, dev server launchers (`run_server.py`, `start_server.py`, `server_loop.py`), `.DS_Store`, log files
    * Critically: **`nrega-server/` is NOT ignored.** Today GitHub Actions doesn't check out that folder (separate NAS repo), so secrets don't ship *in this exact pipeline run*. But any local run of this recipe, or vendoring of the server folder, silently ships `firebase-service-account.json`, `google-sheets-service-account.json`, `hooks.json`, and server source into `core_win_v*.zip` — downloaded and extracted by every client loader. Verified: those service-account JSONs are tracked files in the server repo (`git -C nrega-server ls-files`).
* **Real-world impact:** Internal infrastructure disclosure to ~200+ installs now; credential leak on first topology change. Also bloats every hotfix zip and changes its hash for non-code reasons (breaks same-version hotfix determinism).
* **Fix:** Port `build_update.py`'s whitelist into the release.yml step (or call `build_update.py --platform win` directly so there is exactly one packaging implementation).

### 2. 🟠 P1 — Main loader accepts downgrades; empty hash = no verification at all

* **File:** `loader.py:670` and `loader.py:701` · **Function:** `check_for_updates()`
* **Problem:** `needs_update = (server_ver != effective_ver) or (server_hash and server_hash != current_hash)` — a pure inequality. Any server response with an older `version` triggers a downgrade install. Compare `lite_loader.py:467`: `if parse_version(lat) <= parse_version(current_ver) and not hash_changed:` — Lite does it correctly; main doesn't. Additionally the download integrity check is `if server_hash:` — when `hash_windows`/`hash_macos` is empty (routine during the documented release flow where hashes are filled *after* push), the freshly downloaded zip is extracted **with zero verification**.
* **Realistic scenario:** compromised/erroneous tunnel response or a mis-edited version.json rolls all users back months (blocked-versions can't help); a partially-filled version.json pushes unverified code.
* **Fix:** refuse when `parse_version(server_ver) < parse_version(effective_ver)`; treat empty server_hash as "do not apply" rather than "skip check".

### 3. 🟠 P1 — MR Fill selects work code and MR by dropdown *index*, then retry feeds back truncated codes

* **Files:** `src/tabs/mr_fill_tab.py:395,404` (+ `536`), retry at `494–529`; truncation `src/utils.py:137–168`
* **Problem chain:**
    1. `_process_single_work_code()` searches the portal for `work_key`, then does `work_code_select.select_by_index(1)` and `msr_select.select_by_index(1)` **without verifying the selected option's text contains the target work code**. If search returns multiple/partial matches, attendance is filled for the wrong work code.
    2. Results tree stores the *display* code: `_log_result()` runs `work_key = truncate_workcode(work_key)` (line 536) before insert.
    3. `retry_logic_handler()` (line 508) reads `values[1]` — the truncated 6-digit suffix — writes it into the input box and re-runs. Search-by-suffix + select-first-option compounds mismatch probability whenever two work codes share a suffix within a panchayat.
* **Impact:** attendance posted against the wrong work code = wrong government data submission. Single worst data-integrity chain in the codebase.
* **Fix:** assert `selected_option.text` contains the normalized target code before proceeding; store the *full* work code in a hidden tree column (or side map keyed by item id) and have retry read from that map.

### 4. 🟠 P1 — Demand tab: crashed runs report "Finished" and still trigger auto work-allocation

* **File:** `src/tabs/demand_tab.py:1883` and `1946` · **Function:** `_process_demand()` `finally:` block
* **Problem:** `elif 'e' in locals():` is dead code. In Python 3 the exception name is deleted when the except block exits — verified at runtime (`'e' in locals()` → `False` even after a raised exception). Consequence: after the function-level `except Exception as e:` at line 1870 fires, the `finally` block falls into the **else branch** — status text says "Finished", and the "INTELLIGENT HANDOFF" auto-allocation runs off partial results instead of being skipped.
* **Impact:** operator sees "Finished" after a mid-run crash; allocation handoff may fire with incomplete success data (mitigated partly because allocation only uses names actually marked Success in the tree, but the status lie and lost error state are real).
* **Fix:** set `self._run_error = type(e).__name__` inside the except block and check that flag in `finally`.

### 5. 🟠 P1 — Hard-coded Evolution API credentials + internal IP in shipped config

* **File:** `src/config.py:63–65`

```python
EVO_BASE_URL: str = os.environ.get('EVO_BASE_URL', 'http://192.168.29.101:8087')
EVO_API_KEY: str = os.environ.get('EVO_API_KEY', 'NregaBotSec***Key123')  # redacted here
```

* **Problem:** These defaults ship in the public GitHub repo and in every packaged app/core zip. The in-code comment admits the fallback is the *previous real value*. Desktop code currently never calls them (verified — no usage outside config), but they disclose LAN topology and a likely-still-live API key for the production Evolution API (WhatsApp). Improvement-plan item 0.4 said remove these; not done.
* **Fix:** default to empty strings; fail loudly (or disable feature) when unset. Rotate the Evolution key regardless.

### 6. 🟠 P1 — SHA-256 update verification is integrity-only, not authentication

* **Files:** `loader.py:592–705`, `src/managers/services.py:153–221`
* **Answer to special check #4:** version number, download URL, *and* expected hash all arrive in the same `version.json` over TLS from `nregabot.com`. There is no signature, no pinned key, no second trust root. Anyone controlling the server/tunnel/DNS-with-valid-cert supplies both the malicious zip and its matching hash → arbitrary Python code execution inside the trusted `app_live` directory on every machine (loader executes extracted source via `import main_app`). SHA-256 protects against corruption and partial downloads (it does that well), **not** against a hostile update source.
* **Fix (proportionate):** minisign/ed25519-sign the zip at build time (private key in GitHub secret / offline), embed public key in the PyInstaller loader, verify signature before hash. ~50 LOC total.

### 7. 🟡 P2 — "No Future Dates Plz" reported as "MR Already Filled"

* **File:** `src/tabs/mr_fill_tab.py:406–417, 545–549`
* **Problem:** The portal's future-date validation error is converted to `ValueError("MR Already Filled")` and later normalized to the literal details string `"MR Already Filled"`. An operator scanning results believes the muster was already submitted when in fact **nothing was saved** (bad date range). False-negative failure presentation with direct government-data consequences.
* **Fix:** preserve the portal message; add a distinct "Date Error — not saved" category; only report "Already Filled" when an explicit portal already-filled phrase matched.

### 8. 🟡 P2 — Machine binding uses MAC address; license stored as plain JSON; startup check is local-only

* **Files:** `src/managers/services.py:48–52` (`get_mac_address()`), `services.py:55–74` (`check_license`)
* **Problems:** (a) MAC changes with VMs, VPN adapters, hardware replacement → legitimate users locked out; trivially spoofable by abusers. (b) `license.dat` is plain JSON with `key` + `expires_at`; the startup decision is purely local (`datetime.now() > expires_dt` → unlock UI), server validation is background-only. (c) Crash-report uploads include the raw license key (`utils.py:541`).
* **Answer to special check #11:** Yes — license checks can be bypassed entirely client-side by editing `license.dat` (extend `expires_at`) or patching the frozen binary; there is no signed response, no replay protection, no server-side revocation enforced before unlock. Today's cost falls entirely on honest users (MAC churn) while adding zero tamper resistance.
* **Fix:** HMAC-sign `/api/validate` responses and verify locally; switch machine-id to a stable random UUID persisted in the data dir; hash the key in crash payloads.

### 9. 🟡 P2 — `.env` is bundled into every installer/portable/DMG build

* **Files:** `scripts/build_windows.bat:33,75`; `scripts/build_macos.sh:93,123` (`--add-data=".env:."`); `scripts/installer.iss:54` (ships entire `dist/NREGA Bot/*` incl. `_internal/.env`); `release.yml:101–103` writes `SENTRY_DSN=<secret>` into `.env` before building
* **Problem:** CI's Sentry DSN is embedded in every distributed artifact (extractable from `_internal/` in seconds). Nothing in the codebase even reads `SENTRY_DSN` (grep confirms zero usage) — pure leak with no benefit. Worse, the pattern means any future real secret placed in `.env` silently ships.
* **Fix:** delete the `--add-data=".env:."` from both scripts and the CI `.env` step (nothing consumes it).

### 10. 🟡 P2 — Latent `NameError` in usage-stats sync; unpinned dependencies

* **File:** `src/tabs/history_manager.py:587` — `result.get('synced_features', len(snapshot))` references undefined `snapshot` (function defines `stats`). Any 200-response lacking that key raises NameError, swallowed by the broad handler and misreported as sync failure.
* **File:** `requirements.txt` — zero version pins across 22 deps (incl. `pandas`, `selenium`, `requests`, `PyInstaller`). Combined with missing explicit hidden-imports (e.g., `openpyxl` is bundled only as a side effect of `--collect-submodules=src.tabs` triggering module-level analysis), every CI build is a fresh dependency lottery. The "humanize incident" class remains structurally unresolved.
* **Fix:** fix the variable; pin requirements (`pip freeze` baseline) + `--hidden-import=openpyxl` etc. in both build scripts.

---

## SECURITY FINDINGS

| # | Sev | Location | Finding |
|---|---|---|---|
| S1 | P0 | `release.yml:126–133` | Blacklist-based core zip (Top-10 #1). Confirmed contents today include `AGENTS.md` (NAS IP, SSH topology), improvement plans, dev/test scripts. nrega-server secrets excluded *only* by the accident of CI checkout scope. |
| S2 | P1 | `src/config.py:63–65` | Hard-coded Evo API key fallback + internal IP (Top-10 #5). |
| S3 | P1 | Update pipeline overall | No signature/authenticity (Top-10 #6). HTTPS protects transport, not the endpoint. |
| S4 | P1 | `loader.py:642–646,685` | `download_url` comes from server JSON and is fetched without scheme/host validation; `requests` follows https→http redirects by default. A server-side mistake (or compromise) can serve `http://…` and the loader obeys. Enforce `https://nregabot.com/updates/…` prefix. |
| S5 | P2 | `services.py:60–61`, `app_license.py:850–851` | `license.dat` plaintext JSON (key + expiry + user PII per OAuth payload) written with default umask. Set `os.chmod(0o600)`. |
| S6 | P2 | `browser_manager.py:74,96,126,142` | Chrome/Edge CDP on fixed ports 9222/9223 with persistent dedicated profiles holding portal sessions. Any local process can attach to CDP and drive the authenticated session. Accepted Selenium tradeoff; consider explicit `127.0.0.1` binding / randomized pipe on Windows. |
| S7 | P2 | `utils.py:457–476,541` | Crash reports POST raw `license_key` + masked traceback to `/api/crash-report`. Masking covers Aadhaar/mobile/IFSC but the key is a bearer credential sent alongside error data. Hash it (the sha256 pattern already exists in-repo in `location_sync.py`). |
| S8 | P2 | `loader.py:296–320` | `marshal.loads` on `app_live/src/config.pyc` for version sniffing. Marshal of a hash-verified file = low risk, but marshal is not designed for untrusted input. Text-first ordering exists — keep pyc path strictly behind verification. |
| S9 | P3 | `settings_tab.py:268–278`, `ui_components.py:1856–1912` | Subprocess usage audited: list-argv everywhere, `sh -c` payloads built with `shlex.quote`, pid values are ints. **No injection found.** ✅ |
| S10 | P3 | Root `.env` | Empty, **untracked** in git (verified via `git ls-files`). No committed secrets in the desktop repo itself. ✅ |
| S11 | P3 | Zip handling | Extraction relies on CPython `zipfile.extractall` sanitization (strips `..`, absolute paths, drive letters). No custom extraction bypass found in loader/lite_loader/main_app. Acceptable; add an explicit namelist assertion when moving to whitelist packaging anyway. |

### Special security checks — direct answers

1. **Malicious server response → code execution?** YES — core zip is Python source executed by the loader; hash is server-supplied too. Requires nregabot.com/server/tunnel compromise or TLS breach.
2. **Downgrade possible?** YES on main loader (`!=`), NO on Lite loader (`<=`).
3. **Core ZIP replaceable?** Same trust root as #1 — yes given server control; attacker supplies matching hash.
4. **SHA-256 auth or integrity?** Integrity only.
5. **Packaged client secrets?** `.env` bundled into loaders (SENTRY_DSN in CI builds); EVO_API_KEY default hard-coded; AGENTS.md internal IP in core zip.
14. **Malformed Excel/CSV crash?** Cannot crash outright (encoding ladder ends in never-failing latin-1 — itself finding D4); corrupt xlsx via pandas untested.
15. **Zip escape extraction dir?** No practical path beyond CPython's built-in sanitization.
16. **Update failure permanently broken?** No — extract-before-version-write, heal logic, boot-counter rollback, `core_prev.zip`, blocked/bad versions all verified (`tests/test_update_rollback.py`, 20/20 passing).
17. **New dep passes locally, fails packaged?** YES — documented "humanize incident" class; unpinned deps + missing hidden-imports make it recurring.
18. **Artifacts contain .env/debug/internal info?** Core zip: AGENTS.md/improvement-plan/dev scripts/tests YES; `.env` excluded from core zip but bundled into loader via `--add-data`; installer ships `_internal/.env`.

---

## DATA-INTEGRITY FINDINGS

| # | Sev | Location | Finding |
|---|---|---|---|
| D1 | P1 | `mr_fill_tab.py` (Top-10 #3) | Wrong-workcode selection + truncated-retry chain. |
| D2 | P1 | `demand_tab.py:1883` (Top-10 #4) | Crashed run → "Finished" + handoff. |
| D3 | P2 | `mr_fill_tab.py:411–417` (Top-10 #7) | Date error labeled "MR Already Filled". |
| D4 | P2 | `demand_tab.py:1526–1553` (`load_csv_data`) | Encoding ladder `utf-8-sig → utf-8 → cp1252 → latin-1`; latin-1 decodes *any* byte stream, so a genuinely mis-encoded file produces mojibake labourer names that then flow into demand submission with no error. The eKYC path warns about `?` names elsewhere (`find_row_index` logs grid mismatches) but nothing blocks submission. Add a Devanagari/Kannada/Bengali script-ratio sanity check on parsed names before enabling Start. |
| D5 | P2 | `src/utils.py:163–166` | `truncate_workcode` fallback truncates ANY ≥9-digit numeric string (e.g., a bare 12-digit jobcard id) to its last 6 digits. Currently display-only, but it feeds result trees consumed by retry (see D1). Tighten fallback to require the workcode shape. |
| D6 | P3 ✅ | `src/utils.py:191–196` | `current_financial_year()` April boundary is correct (month>=4). Verified. Report folders per FY consistent. |
| D7 | P3 | `demand_tab.py:1489–1498` | Village-code fallback: `rj` takes `jc[-3:]` blindly — a job card whose serial is shorter than 3 chars yields a garbage token; guarded only by upstream village-name presence. Note for Rajasthan expansion. |
| D8 | P3 | `history_manager.py:587` | Undefined `snapshot` NameError (Top-10 #10). |

### Retry / Idempotency Classification

| Automation | Classification | Basis |
|---|---|---|
| Demand (`demand_tab`) | **RETRY WITH STATE CHECK** ✅ | Portal "already demanded" phrases detected (`ALREADY_PHRASES`, line 2226–2228); submit result collected post-click (`_collect_submit_result`). Good model. |
| MR Fill (`mr_fill_tab`) | **RETRY WITH STATE CHECK** ⚠️ | Save success detected via alert text ("Saved Successfully"/"has been saved"); timeout-after-accept marks Failed though save may have landed — re-run hits portal's own already-filled guard. Safe-ish, but see D3 mislabeling which corrupts operator judgment. |
| MB Entry / Material Entry / FTO gen / Wagelist send | **DANGEROUS TO RETRY without state confirmation** ⚠️ *(suspected — not exhaustively traced)* | Success/failure decided by alert-text heuristics and fixed sleeps (`mb_entry_tab.py:722,771,881`; `material_entry_tab.py:488–490`); no equivalent ALREADY-phrase guards found in sampled sections. A timeout after actual server-side commit → user clicks Retry Failed → duplicate entry attempt with only portal-side mercy as protection. Recommend per-tab audit adding pre-submit state probes (like demand's pattern) before marking SAFE. |

---

## AUTOMATION / SELENIUM FINDINGS

| # | Sev | Location | Finding |
|---|---|---|---|
| A1 | P1 | `mr_fill_tab.py:395,404` | Index-based dropdown selection without target-text assertion (Top-10 #3). |
| A2 | P2 | Tabs-wide (~100+ sites) | Fixed `time.sleep(1–3)` after postbacks (`mate_mr_gen_tab.py:594,780`; `jobcard_verify_tab.py:355,441`; `mis_reports_tab.py:235,251,273` …). Slow portals → premature interaction; fast portals → wasted hours per run. The demand tab shows the right pattern (`_wait_dropdown_populated`); migrate incrementally. |
| A3 | P2 | `mr_fill_tab.py:298–330` | Alert polling treats *any* exception (incl. session death) as "no alert yet", looping until timeout — a dead browser burns 15s×items instead of failing fast. Differentiate `InvalidSessionIdException`/`NoSuchWindowException` → abort. |
| A4 | P2 ✅ | `browser_manager.py:63–67,536–551` | `_automation_tab_handle` pinning solves the classic wrong-tab automation problem well — handle reuse after user closes the tab depends on `_prepare_driver_tab` recovery; guard verified present. |
| A5 | P3 ✅ | `base_tab.py:2367–2407` | Central `_select_panchayat_or_skip` correctly distinguishes GP vs PO logins and returns machine-readable status; consumers act on `"notfound"`/`"missing"` properly (verified in `demand_tab.py:1791–1806`). |
| A6 | P3 | Session expiry | No unified portal-session-expiry detector; each tab discovers login pages ad hoc. A shared "redirected to Login.aspx?" probe would cut a whole failure class. |

Portal-layout brittleness (ID/XPath coupling to `vbgramgde2.dord.gov.in`) is inherent and acknowledged in docs/disclaimer; centralization helpers reduce blast radius.

---

## THREADING / GUI FINDINGS

| # | Sev | Location | Finding |
|---|---|---|---|
| T1 ✅ | — | `app_automation.py:175–400` | `start_automation_thread` wrapper verified: duplicate-start guard, stop-event lifecycle, driver cleanup in `finally`, structured error extraction, activity+usage sync trigger. Matches AGENTS.md claims. |
| T2 ✅ | — | `base_tab.py:489–527` | `destroy()` sets `_tab_destroyed` without quitting shared driver or resetting shared stop-event (comment explains the race it avoids — correct). `_is_alive()` + `safe_after`/AfterTracker present and used. |
| T3 | P2 | `main_app.py:553–591` | `on_closing()` ends with `os._exit(0)` after best-effort driver quit. Skips SQLite WAL checkpoint and history-manager close → last-write window can lose suggestions/usage counters (WAL usually recovers; risk small but real on power-loss during shutdown). Improvement-plan M9/1.3 still open. |
| T4 | P3 | `state.py` + property delegation | Shared mutable state (`active_automations`, `stop_events`) mutated from worker + main threads without locks. GIL makes set ops atomic enough here; GC-loop pruning uses a copy-safe pattern (main_app.py:535–542). Accept; document rather than lock. |
| T5 | P3 | `workflow_manager.py:56–58` | Macro queue busy-polls `while key in self.app.active_automations`; stop honored ✅. Fine at current scale. |
| T6 ✅ | — | Worker→UI transitions | Sampled tabs consistently route through `self.app.after(0, …)` including snapshot-before-capture for location labels (`demand_tab.py:2006–2012`). |

**Answers:** #7 — worker exceptions are caught and surfaced by the wrapper (no silent thread deaths mid-run); daemon threads die unreported at `os._exit` (acceptable). #8 — destroyed frames are protected via flag/winfo_exists/safe_after trio; residual risk only where tabs call bare `self.after` (none found in sampled hot paths).

---

## LICENSE / SERVER / SYNC FINDINGS

* **L1 (P2):** Full client-bypass reality — see Top-10 #8. Per audit rules, distinguish: *normal user failure* = MAC-change lockouts (common support-ticket generator); *accidental corruption* = plain-JSON `license.dat` edits; *intentional tampering* = trivially achievable and undetected.
* **L2 (P3):** `validate_on_server` sends machine_id (MAC) + version over HTTPS ✅; response fields (`global_disabled_features`, trial restrictions) are applied client-side only — inherently advisory.
* **L3 (P3):** Sync surfaces audited — `location_sync.py` hashes the license key (sha256) ✅ and shares only public-grade panchayat/village names; `usage-stats` and `activity-log` sync send the **raw** key (as auth context over TLS — acceptable, but inconsistent with the DPDP stance stated in AGENTS.md §4.11). Merge behavior is strictly additive (missing-only) ✅ per `apply_server_data`.
* **L4 (P3):** Offline behavior: startup unlock works fully offline until background validation contradicts it — deliberate grace design; ensure the contradiction path actually locks features (recommend a manual test of revoked-key UX).
* **Special check #12 (tenant isolation):** server-side concern — out of this repo's boundary; location pool keyed by sha256(key) is reasonable.
* **Special check #13 (share links):** file-manager share links served by `nrega-server/app/routes/file/web.py` — outside this audit's scope; recommend a dedicated server-side pass (auth/expiry/enumerability).

---

## UPDATE / LOADER FINDINGS

* **U1:** Downgrade asymmetry + empty-hash skip — Top-10 #2.
* **U2:** Supply-chain authenticity — Top-10 #6.
* **U3 ✅:** Extract-then-record ordering, `_heal_install()` live-version comparison, boot-counter (3 strikes) rollback, `core_prev.zip` promotion with hash-match precondition, bad-version floor, admin blocked-list, force-rollback file — all verified in code AND covered by passing unit tests. This subsystem is the strongest part of the product.
* **U4 (P3):** `main_app._apply_smart_update` (lines 679–731) writes `core_version.json` immediately after scheduling the async `updater.bat`; if `xcopy` fails the version file lies — but loader heal compares live code version next launch, so it self-corrects. Note only.
* **U5 (P3):** Concurrent launch during update: single-instance socket (60123) + delayed relaunch shows awareness; no file lock on `core.zip` — two loaders racing prevented by single-instance except loader-vs-smart-update overlap (edge, low likelihood).

---

## BUILD / RELEASE FINDINGS

| # | Sev | Finding |
|---|---|---|
| B1 | P0 | Windows zip blacklist — Top-10 #1. |
| B2 | P2 | `.env` bundling — Top-10 #9. |
| B3 | P2 | Unpinned requirements + hidden-import fragility — Top-10 #10. |
| B4 | P3 | `publish-release` deletes existing tag/release then recreates (`release.yml:300–308`) — mutable releases break user-side pinning/audit trails. Prefer immutable tags; fail if tag exists. |
| B5 | P3 | macOS signing is ad-hoc (`codesign --sign -`, `build_macos.sh:140`) with no notarization → Gatekeeper friction trains users to override security prompts. Known cost tradeoff; track as roadmap. |
| B6 | P3 | Linux build omits hidden-imports present in Win/mac lists (e.g. `pypdf`, `release.yml:245–269`); Linux users get updates via generic hash/url only. Works today via collect flags — same fragility class as B3. |
| B7 ✅ | — | Locale CI gate verified live: `build_locales.py` exit 0, 1106 keys × 5 locales, zero placeholder drift; `git diff --exit-code src/locales/` is a solid tripwire. Special check #19: **yes, synchronized.** |
| B8 | P3 | `scripts/check_imports.py` scans `dist/` bundles (855 noise errors) and *executes* module-level servers ("Address already in use" for run_server/start_server/server_loop — import-time side effects). Fix: exclude dist/, guard entry points, exit non-zero on genuine source errors. |

---

## TESTING GAPS

Current suite: **20 tests, exclusively update-rollback** (`tests/test_update_rollback.py` — good quality, isolated tmp_path fixtures). Smoke test instantiates all tabs headlessly ✅ (real TclError catcher). Zero coverage on:

* `parse_version` edge cases, `current_financial_year`, `truncate_workcode`, `mask_pii_text` regexes
* `load_csv_data` encoding ladder; demand grouping / village-code logic
* mr_fill result classification; license response handling
* `apply_server_data` merge; retry flows

All are pure functions or mockable (requests/Selenium fakes) — none need the live portal. ROI order: (1) utils pure functions, (2) CSV/Excel parsers with crafted mojibake/malformed fixtures, (3) demand grouping, (4) loader version-decision table (would have caught U1), (5) Selenium page-object fakes for mr_fill classification. CI note: pytest job already exists in release.yml (lean deps) — extend it.

---

## PERFORMANCE FINDINGS

* Startup: lazy tab loading + deferred imports verified working as documented; splash staged init sound.
* The `time.sleep` tax (A2) is the dominant runtime cost — converting the top 10 offenders to event-driven waits is the only optimization with measurable user impact.
* Periodic GC + dead-thread pruning (`main_app.py:517–551`) addresses long-session growth ✅.
* PNG/PIL report-rendering memory spikes noted in the prior plan remain (Phase-3 candidate, not urgent).

---

## ARCHITECTURAL DEBT

1. `lite_app.py` (~77k chars) duplicates `main_app` mixin behavior — the copies already diverged (Lite has correct downgrade logic; Main doesn't — proof of the duplication cost). Parameterize rather than rewrite.
2. Per-tab Selenium boilerplate (alert accept/retry loops) duplicated despite `portal_utils`-style helpers existing in base_tab — finish the migration.
3. `docs/last_conversatation.txt` (12k+ lines) and other chat dumps inside `docs/` bloat the repo and complicate the Windows core-zip exclusion list. Archive out-of-tree.
4. The `'e' in locals()` idiom suggests no lint gate — add `ruff` (F821/dead-code class checks) to CI cheaply.

---

## DOCUMENTATION MISMATCHES

| Claim (AGENTS.md / README) | Verdict |
|---|---|
| Core zip whitelist `src/config/assets/docs` | **MISLEADING for Windows** — true for macOS (`build_update.py`), false for CI Windows zip (blacklist). |
| "SHA-256 Verified" smart updates (README badge) | **INCOMPLETE** — true as corruption check; false as security guarantee. |
| Golden rule "never `print` for logs" | **OUTDATED** — violations persist (`services.py:216`, others). |
| Version bump: agent leaves hashes empty, user fills | **CORRECT** ✅ — observed in live git diff (user-filled `hash_windows/macos`, uncommitted). |
| Threading rules / safe_after / no quit-in-destroy / lazy imports | **CORRECT** ✅ — verified in code. |
| Lite vs Main feature parity of update safety | **MISLEADING** — Lite is safer than Main (U1). |
| `nrega-server` never ships in core zip | **OUTDATED RISK STATEMENT** — holds only while CI checkout excludes it (S1). |

---

## PRIORITIZED REMEDIATION ROADMAP

### Phase 1 — Immediate (before next production release)

1. Replace Windows core-zip step with `build_update.py` whitelist (single packager) — kills S1/B1.
2. Loader: refuse downgrades (`<` comparison) + treat empty server hash as do-not-apply (U1).
3. Remove `EVO_*` fallback values; rotate the Evolution key (S2).
4. Delete `--add-data=".env:."` from both build scripts + CI `.env` step (B2).
5. MR Fill: assert selected option matches target work code; carry full codes for retry (D1/A1).
6. Demand tab: replace `'e' in locals()` with an explicit error flag (D2).
7. Fix `history_manager.py:587` undefined variable (D8).

### Phase 2 — High Priority

8. ed25519-signed core zips (sign in CI, verify in loader) (S3/U2).
9. MR Fill date-error vs already-filled disambiguation (D3); rename misleading statuses.
10. Signed license responses + stable UUID machine-id; chmod 600 `license.dat`; hash key in crash payloads (L1, S5, S7).
11. Pin requirements; add missing hidden-imports (`openpyxl`, `ttkbootstrap`) to all three build targets (B3).
12. Enforce https + host-prefix on update/download URLs (S4).
13. Pre-submit ALREADY-state probes for MB Entry / Material Entry / FTO / Wagelist-send; publish per-tab retry classification in docs.

### Phase 3 — Stability

14. Test-suite build-out in ROI order above; wire smoke + fixed check_imports into CI as blocking.
15. Convert top-10 sleep sites to wait conditions; alert-probe session-death differentiation (A2, A3).
16. Graceful shutdown: checkpoint SQLite before exit instead of bare `os._exit(0)` (T3).
17. ruff/flake8 gate catching dead-code idioms; de-noise `check_imports.py`.
18. Devanagari-script sanity check on parsed CSV names before enabling submission (D4).

### Phase 4 — Architecture (justified only)

19. Unify Lite/Main update logic in one module (duplication already caused divergent security behavior).
20. Finish portal-helper migration in remaining tabs; archive chat-log dumps out of the repo.

---

## RELEASE READINESS VERDICT

## ⚠️ READY WITH REQUIRED FIXES

The product's core engineering — update rollback/heal, thread-safe tab lifecycle, DPDP masking, locale parity gating — is genuinely production-grade, and 20/20 tests plus a live locale rebuild confirm the newest machinery works. But Phase-1 items are release blockers, not polish: the Windows core zip currently distributes internal infrastructure documents to every user and is one repository-topology change away from distributing live service-account keys; the main loader will happily downgrade users or extract a completely unverified zip whenever the hash field is empty (a state your own release flow produces routinely); and MR Fill can submit attendance against the wrong work code through the index-selection + truncated-retry chain. None of these require architectural surgery — all seven Phase-1 items are day-scale fixes — but until they land, each release extends the exposure. Ship again only after Phase 1 is merged.

---

*End of audit report. Generated 25 Aug 2026 · ox-alpha forensic audit · read-only — no source files were modified.*








