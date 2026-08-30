# NREGA Bot - Product Requirements

> **Source of truth for product intent.** Technical architecture lives in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md); engineering rules in [`docs/RULES.md`](RULES.md); current development phase in [`docs/PHASES.md`](PHASES.md).
>
> **Audience:** Product owner (Rajat), future team members, AI assistants aligning on scope.
>
> **Status:** Living document. Verified against the current repository on **30 Aug 2026** at version **3.2.7** (see `config/version.json` and `src/config.py::APP_VERSION`).

---

## 1. Product purpose

NREGA Bot is a **desktop automation tool for India's MGNREGA / VB-G-RAM-G portal**. It drives a real browser (Chrome, Edge, or Firefox) on the user's own computer to:

1. **Eliminate repetitive data entry** for Gram Rozgar Sevaks, Panchayat Secretaries, and BDO offices.
2. **Read and fill portal forms precisely** - no fat-finger mistakes in job cards, muster rolls, demands, wagelists.
3. **Generate professional reports** (Excel + PDF, A4 landscape, serial + page numbers).
4. **Keep automations running in the background** while the user works on other things - the browser stays minimized.
5. **Self-heal across portal changes** via SHA-256-verified hotfix updates that ship without a full re-install.

The product is **not** a SaaS web app and is **not** a server-side scraper. It always runs on the operator's own desktop, with their own browser, using their own login credentials.

---

## 2. Target users

| Persona | What they do today | What the bot does for them |
|---|---|---|
| **Gram Rozgar Sevak (GRS)** | Manually fill jobcard / MR / wagelist forms as part of routine NREGA work | One-click Demand, MR Fill, Wagelist Generate/Send, Jobcard Verify |
| **Panchayat Secretary** | Maintain records, generate reports for blocks | MR Tracking, eKYC/ABPS reports, Jobcard verification |
| **BDO / Block-level operator** | Aggregate data, verify compliance | Macro/Multi-tab workflows, Activity log, WhatsApp reports |
| **State admin** (Jharkhand, Rajasthan, Karnataka actively registered; other states pending) | Not the direct user - benefits from operational uplift | Indirect - operators finish more work in less time |

> **Note:** State list is server-driven. New states are added without a desktop release via the **State Registry** admin page (`/admin/portal-states`). Current active states: Jharkhand, Rajasthan, Karnataka (per `src/config.py::STATE_PORTAL_HOSTS`). Additional states (e.g., Bihar) are pending admin entry - see `docs/SCALING_PLAN_200_to_10000.md` (the "Phase 1 complete" / state-registry progress section).

---

## 3. Core problems solved

1. **Form entry volume** - The portal requires repetitive multi-field entry across many panchayats. Bot-driven automation substantially reduces the manual time operators spend on a single multi-panchayat cycle.
2. **Typing errors** - Bot reads the portal DOM directly and types with 100% fidelity; no human transcription.
3. **Multi-step workflows** - A single Macro can chain Demand -> Work Allocation -> MR Generate -> MR Send without the user babysitting the browser.
4. **Report generation** - Pulls live data from the portal and exports print-ready Excel/PDF with proper formatting.
5. **Updates that don't break** - SHA-256-verified hotfix zips (KB-sized) patch the running app in seconds; on boot failure, automatic rollback to last known-good core.
6. **Cross-device continuity** - License-key-driven activation; settings sync via the cloud server; data pool shares location hierarchies block-wise (see section 4).
7. **State onboarding without releases** - Operators in new states download the same desktop app; the State Registry pulls the right portal URL/config on heartbeat.


---

## 4. Core workflows and capabilities

### 4.1 MR & Wage management

- Demand (CSV-driven, 100-day limit adjustment)
- Delete Demand (single/multiple villages; auto-recovers portal bugs)
- Work Allocation (multi-date)
- Muster Roll Generator (PDFs + Merge PDFs)
- MR Fill (eKYC + ABPS verification immediately after generation)
- MR Payment (MSR)
- Mate MR / Material Entry / FTO Generation / FTO Delete / Pending Bills
- Zero MR / Duplicate MR / Scheme Closing
- Wagelist Generate / Send / Resend Rejected / Print / Merge
- ABPS Verify / eMB Verify / eKYC Report / Dashboard Report
- Jobcard Verification (with photo upload, "All Villages" support)

### 4.2 Macro Manager

The **only** way to chain multiple automations across tabs (`src/managers/workflow_manager.py`). Used by power users to queue dozens of panchayats times tabs without manual intervention. Also exposes "Add to Queue" from any individual tab.

### 4.3 Reports and exports

- Excel (openpyxl) - A4 landscape, serial numbers, page numbers, colored status highlights
- PDF - Print-ready, Hindi/regional script support (NotoSansDevanagari font)
- WhatsApp delivery - Activity summary to admin/operator's configured number
- Local CSV - every treeview exportable per-tab

### 4.4 Location data pool (3.2.5+)

Operators without PO/GP login previously couldn't select panchayat/village. Now: users sync their saved block data (`location_hierarchy.json`) to the server; same-block peers fetch it for ready-made dropdowns - no scraping needed. **Server stores `sha256(license_key)` only (DPDP), names are UPPER-normalized, merge is missing-only** (local edits never overwritten). See `src/location_sync.py`.

### 4.5 Search and shortcuts (3.2.3+)

- **Sidebar search** (Ctrl+K focus) - case-insensitive across all tabs and categories
- **Ctrl+Enter** -> start current tab automation
- **Ctrl+S** -> stop current tab
- **Ctrl+R** -> retry failed

---

## 5. Full vs Lite product

| Aspect | **NREGABot** (Full) | **NREGABot Lite** |
|---|---|---|
| Entry | `main_app.py` | `lite_app.py` |
| Window | 60123 | 60124 |
| Tabs | **48** across 7 categories | ~17 subset |
| Icons | PNG (`assets/icons/`) | Unicode emoji |
| Splash | Animated `ModernSplashScreen` | None, simplified header |
| Autocomplete | `AutocompleteEntry` (type-ahead) | `LiteDropdown` (read-only dropdown) |
| Use case | Operators who use 40+ tabs | Operators who only need a few core automations |

Both share the same `src/` tree; Lite monkey-patches the dropdown widget at startup so tab files are reused unchanged. See `lite_app.py:67-72` (the patch) and `lite_app.py:104` (`class NregaBotLiteApp(ctk.CTk, LicenseMixin)`).

---

## 6. Supported portal/browser model

| Browser | Mode | Notes |
|---|---|---|
| **Chrome** | Detached (debug port 9222) | Default; CDP-attached so automation can run while minimized |
| **Edge** | Detached (debug port 9222) | Same CDP mechanism as Chrome |
| **Firefox** | Managed (selenium-managed Geckodriver) | 1 driver shared across all tabs (different from Chrome/Edge model) |
| Older Firefox | Supported in FTO Generation (2.9.7+) | Per changelog entry |

The bot **launches its own browser instance** in a persistent user profile (`~/ChromeProfileForNREGABot/`) so login sessions survive across runs. Browser tab is marked with "robot NREGA-BOT gear Running" + a red favicon dot via `AUTOMATION_MARKER_JS` (`browser_manager.py:27-45`) so the user doesn't accidentally close it.

---

## 7. Cloud/server role

The `nrega-server/` (Flask on Synology NAS) handles:

1. **License validation** - `/api/validate` (parameterized SQL, `SELECT...FOR UPDATE`, blocked/expiry checks, schema validation, 30/min limit, signed magic-link for `slots_full` cases).
2. **State registry** - `/api/app-config` returns active `states[]` -> desktop applies via `update_state_registry()` (`src/config.py`) on heartbeat.
3. **Cloud sync** - settings, files, location pool, activity logs.
4. **Crash/error pipeline** - `error_logs` (auto-categorization), `crash_reports` (PII-masked both client and server).
5. **Payments + pricing** - Razorpay integration, plan prices editable via `/admin/pricing` (DB-override of constants).
6. **Admin panel** - license management, revenue dashboard, state analytics, churn prevention (renewal reminders), error-spike alerts, trial funnel analytics.
7. **Auto-update delivery** - `release_sync` downloads new GitHub releases into NAS `website/updates/`.

The desktop app **never trusts server data blindly** - registry payloads are sanitized (strings only); license keys are sha256-hashed before sending; PII (Aadhaar/mobile/IFSC) is masked in the logger *and* the network payload *and* server-side (defense-in-depth).

---

## 8. Update / delivery model

Two-stage delivery (`loader.py` -> `core.zip` -> `main_app.py`):

1. **PyInstaller bundle = `loader.py` only.** Splash shown by the loader; downloads SHA-256-verified `core_{win,mac}_vX.zip`; extracts to `app_live/`; spawns `main_app.py`/`lite_app.py`.
2. **`core_{win,mac}_vX.zip` is built via a strict whitelist** (`scripts/build_update.py` + mirror in `.github/workflows/release.yml` for Windows): only `main_app.py`, `lite_app.py`, `lite_loader.py`, `requirements.txt`, `src/`, `config/`, `assets/`, `docs/changelog.json`, `docs/license.txt`. **No** AGENTS.md, no tests, no nrega-server, no .env.
3. **Hotfix mechanism** - same `latest_version`, different `core_update.hash` = re-download.
4. **Rollback** - boot counter (`get_boot_count` in `src/utils.py`) increments on each launch; failed boots trigger `install_crash_reporter`-based rollback to last known-good core.


---

## 9. Important product constraints

| Constraint | Why |
|---|---|
| **Live government portal** | The bot reads/clears portal state. It cannot roll back a wrong submission. (Per `docs/license.txt` disclaimer.) |
| **DPDP / PII compliance** | License keys hashed client-side before any sync. Aadhaar/mobile/IFSC masked in logger + payload + server. |
| **User's own browser** | We use the user's existing login session; no credential ever leaves the user's machine. |
| **Single-instance** | Full app uses port 60123; Lite uses 60124 - second launches focus the existing window. |
| **Windows / macOS / Linux** | All three supported via PyInstaller. Build scripts: `scripts/build_windows.bat`, `scripts/build_macos.sh`, GitHub Actions release workflow (Linux). |

---

## 10. Current product status

| Metric | Value | Source |
|---|---|---|
| **Version** | 3.2.7 | `config/version.json`, `src/config.py::APP_VERSION` |
| **Active users** | ~200+ (Jharkhand base + growing in Rajasthan, Karnataka, Bihar) | `docs/SCALING_PLAN_200_to_10000.md` |
| **Tabs** | 48 (Full) / ~17 (Lite) | `find src/tabs -name '*_tab.py'` |
| **Locales** | English, Hindi, Kannada, Bengali, Hinglish | `src/locales/{en,hi,kn,bn,hinglish}.json` |
| **Test count** | 306 passing | `pytest -q` |
| **Server** | Live (Flask + Postgres + Redis + Celery + WebDAV on Synology NAS via docker-compose) | `docs/Guide.txt` |
| **Production** | Yes | (per AGENTS.md section 6 - production status confirmed) |

---

## 11. Explicit future direction

The following items are **already supported** by existing project documentation/audits and are listed here as planned/PLANNED only:

| Item | Source | Status |
|---|---|---|
| **WhatsApp renewal reminders (churn prevention)** | `docs/SCALING_PLAN_200_to_10000.md` 11 Aug 2026 entry | Done server-side (migration 025) - `nrega-server/app/whatsapp_automator.py::check_expiry_reminders()` |
| **Trial funnel analytics** | `docs/SCALING_PLAN_200_to_10000.md` 11 Aug 2026 entry | Done (`/admin/funnel` page, 12 Aug 2026) |
| **ed25519-signed core zips** | `docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md` Phase 2 #8 | PLANNED (not implemented) |
| **Per-tab retry classification docs** | `docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md` Phase 2 #13 | PLANNED |
| **CDN / managed Postgres / canary** | `docs/SCALING_PLAN_200_to_10000.md` section 5 | PLANNED - deferred until user count crosses ~1000-2000 |
| **MR Fill date-error vs already-filled disambiguation** | `docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md` Phase 2 #9 | PLANNED |
| **`_wait_for_automation_finish` always checks `stop_events["macro"]`** | PHASES.md / DEC-002 follow-up | KNOWN DEFERRED - see `docs/PHASES.md` |
| **`license.dat` chmod 600 across 7 sites** | `docs/AUDIT_FIX_PROGRESS_25Aug2026.md` F10 | DEFERRED |

> **What is intentionally NOT in scope here:** revenue projections, marketing KPIs, partner/reseller expansion plans beyond the published scaling doc. Those are in `docs/SCALING_PLAN_200_to_10000.md` (the living roadmap) and are intentionally separate from product requirements.

---

## 12. Fact vs assumption

**Facts (verified from current repo on 30 Aug 2026):**
- Version 3.2.7, 48 tabs, 5 locales, 306 tests passing
- Two repos (desktop + server), two-stage loader delivery, SHA-256-verified hotfixes
- Live production with ~200+ users

**Assumptions (explicit):**
- Bihar state is "pending admin entry" - taken from the scaling plan's "Phase 1 progress" section; no in-repo registry row was inspected here.
- "Production" status of the server is taken from `docs/Guide.txt` and AGENTS.md section 6 - not re-verified by querying the live NAS.
