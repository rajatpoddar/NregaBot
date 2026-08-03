# NREGA Bot — Codebase Guide

> **Purpose:** This file is the single reference for understanding the NREGA Bot codebase
> quickly. Read this FIRST before exploring the code, so you don't waste time re-mapping
> the architecture on every session. Keep it updated when the architecture changes.

NREGA Bot is a **Python desktop automation tool** (CustomTkinter GUI) that automates
data-entry tasks on the Indian government's **VB-G-RAM-G / MGNREGA portal**. It drives a
Selenium browser (Chrome/Edge/Firefox) to fill forms, scrape reports, and generate
Excel/PDF reports for a user's district → block → panchayat.

---

## 1. High-Level Architecture

```
PyInstaller EXE (loader) ──downloads──▶ core_win_vX.zip (source code) ──extracts──▶ runs main_app.py
      │                                                                                    │
      └── splash screen + update check (loader.py / lite_loader.py)                        │
                                                                                           ▼
                                                            NregaBotApp (main_app.py)
                                                            ┌──────────────┬──────────────────┐
                                                            │ Header/footer│ Sidebar nav      │
                                                            │ (UIMixin)    │ (NavMixin)       │
                                                            ├──────────────┼──────────────────┤
                                                            │ License      │ Automation       │
                                                            │ (LicenseMixin)│ (AutomationMixin)│
                                                            └──────────────┴──────────────────┘
                                                                        │
                                                      ~44 lazy-loaded tabs in src/tabs/
```

### Key concept: the "loader + core zip" delivery model

- The **PyInstaller build only bundles `loader.py` (or `lite_loader.py`)** plus third-party
  pip packages. The actual application code (`main_app.py`, `src/`) ships as a **source zip**
  (`core_win_vX.zip` / `core_mac_vX.zip`) built by `scripts/build_update.py`.
- On launch, the loader checks `https://nregabot.com/version.json` (see `config/version.json`
  for the local mirror), downloads the core zip if newer **or same-version-but-different-hash**
  (SHA-256 verified), extracts it, and runs `main_app.py` / `lite_app.py` from disk.
- **Implication for pip deps:** any third-party package the app code needs (e.g. `humanize`)
  MUST be declared as `--hidden-import=...` in the build scripts — otherwise PyInstaller never
  sees it because the loader itself doesn't import it. (This caused the "humanize module
  missing" bug — see build scripts section.)

---

## 2. Entry Points

| File | Role |
|---|---|
| `loader.py` | **Main app loader.** Splash screen, checks/ downloads/ extracts core zip, then `import main_app; main_app.run_application()`. |
| `lite_loader.py` | **Lite app loader.** Compact splash, simpler update path (extracts into `_internal/`), then `lite_app.run_lite_application()`. |
| `main_app.py` | **Full app.** Defines `NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)` and `run_application()` (single-instance socket on port 60123). |
| `lite_app.py` | **Lite app.** `NregaBotLiteApp` — fewer tabs, no sounds/animations/onboarding, emoji icons. Port 60124. |
| `_smoke_test_tabs.py` | Headless test: instantiates EVERY tab to catch pack/grid TclErrors. Run: `venv/bin/python _smoke_test_tabs.py`. |
| `scripts/check_imports.py` | Compiles + imports every `.py` file; writes results to `docs/import_check_results.txt`. |

---

## 3. App State & Mixins

### `src/state.py` — `AppState` dataclass
Centralized typed state: license info, `active_automations: Set[str]`, `automation_threads`,
`stop_events`, tab instances, nav buttons, update info, theme mode, etc.
`NregaBotApp` exposes **backward-compatible properties** (bottom of `main_app.py`) that
delegate `self.app.xxx` → `self.app_state.xxx`, so the 40+ tab files can keep using
`self.app.<attr>` unchanged.

### Mixin files (`src/app/`)
| File | Mixin | Responsibility |
|---|---|---|
| `app_ui.py` | `UIMixin` | Header, footer (status + running-automation indicator), sidebar layout, resize smoothing, theme cycling, sound/minimize toggles, `set_status()`-adjacent widgets. |
| `app_navigation.py` | `NavMixin` | Sidebar buttons, category filter, lazy tab loading via `show_frame()`, tab caching (`_has_automated` keeps tabs alive after a run), error UI for failed tab loads, workflow delegation to `self.workflows`. |
| `app_automation.py` | `AutomationMixin` | `start_automation_thread(key, target, args)`, `on_automation_finished()`, emergency stop, `AUTOMATION_DISPLAY_NAMES` map + `_update_running_automation_indicator()`, WhatsApp notification helpers, browser launch delegation, `_quick_login_automation`. |
| `app_license.py` | `LicenseMixin` | License validation flow, activation window, expiry handling, feature flags (`global_disabled_features`, `trial_restricted_features`). |

---

## 4. Managers (`src/managers/`)

| File | Class | Responsibility |
|---|---|---|
| `services.py` | `ServiceManager` | License check/validate (`/api/validate`), update check & install, machine-id via MAC, prevent-sleep (Windows `SetThreadExecutionState` / macOS `caffeinate`). |
| `browser_manager.py` | `BrowserManager` | Launch Chrome (debug port 9222)/Edge/Firefox, manage Selenium driver, per-thread browser choice. |
| `workflow_manager.py` | `WorkflowManager` | **Macro queue engine**: runs a sequence of tab automations (e.g. MR Tracking → eMB Entry), waits for keys in `app.active_automations`, hands off scraped workcodes between tabs. |
| `icon_manager.py` | `LazyIconManager` | Lazy icon loading with cache (`get("key")`, `get_sized()`, `preload_essential()`). |
| `sound_manager.py` | `SoundManager` | Plays wav assets from `assets/sounds/`. |

---

## 5. Tab System (`src/tabs/`)

- **~44 tabs**, each a `ctk.CTkFrame`. Config lives in `src/tab_config.py`
  (`get_tabs_definition()`) and `src/lite_tab_config.py` (`get_tabs_definition_lite()`).
- **Lazy loading:** `_lazy_import(class_name, module_path)` in `tab_config.py` imports the
  module only on first tab open (importlib) and caches the class. This keeps startup fast
  (no selenium/pandas at boot).
- **Base class:** `src/tabs/base_tab.py` → `BaseAutomationTab(parent, app, automation_key)`.
  Provides: log area + status bar, Start/Stop/Retry/Reset buttons, `start_automation()`,
  `stop_automation()`, `update_status()`, `set_common_ui_state()`, treeview styling/export
  (CSV/Excel with openpyxl styling), PNG report generation (`generate_report_image`),
  `_REPORT_CATEGORY_NAMES` (automation_key → report folder name), activity tracking
  (`activity_panchayat/village/details`), `safe_after()` tracked callbacks, `_is_alive()` guards.
- **Automation flow:** tab's `start_automation()` → `self.app.start_automation_thread(
  self.automation_key, self.run_automation_logic, args=...)` → runs on a daemon thread →
  `on_automation_finished()` cleans up, logs, toasts, WhatsApp notify, removes key from
  `active_automations`.

### Automation keys (`automation_key` on each tab)
`demand, work_allocation, muster, mate_mr, mr_fill, msr, gen, send, fto_gen, duplicate_mr,
material_entry, mb_entry, emb_verify, wc_gen, if_edit, update_estimate, physical_complete,
scheme_closing, add_activity, jc_verify, abps_verify, del_work_alloc, del_demand,
delete_applicant, zero_mr, resend_wg, sad_auto, sad_update_status, mr_tracking,
dashboard_report, mis_reports, issued_mr_report, ekyc_report, social_audit_respond,
nmms_attendance, pending_bills, macro, pdf_merger, wc_extractor`.

**Friendly display names** for these live in `AUTOMATION_DISPLAY_NAMES` in
`src/app/app_automation.py` (used by the footer "▶ Running: …" indicator).

---

## 6. Footer & Running-Automation Indicator

Built in `UIMixin._create_footer()` (`src/app/app_ui.py`) and `lite_app.py`.

- **Left side:** © copyright, loading spinner, then the **`running_automation_label`**
  showing e.g. `▶ Running: MB Entry, Demand` (bold blue). Updated by
  `AutomationMixin._update_running_automation_indicator()`.
- **Right side (`dock_frame`):** **`status_label`** (`Status: Ready`), then STOP ALL
  emergency-stop dot+label, icon buttons (history, cloud files, WhatsApp, settings), server
  status dot.
- `_update_running_automation_indicator()` is called on start / finish / emergency stop and
  is safe before the footer exists (`winfo_exists()` guard).
- `set_status()` (in `main_app.py`) colors the status label by message keywords
  (running → blue + spinner, ready → green + success sound, error → red + error sound).

---

## 7. Configuration (`src/config.py`)

- `APP_VERSION` (3.1.2), `LICENSE_SERVER_URL` (env or default), `MAIN_WEBSITE_URL`,
  `SUPPORT_EMAIL`, `BETA_BUILD` (detected via `config/beta.json` marker).
- `COLORS` — the **central color palette** (all UI must use `config.COLORS["key"]`, supports
  `(light, dark)` tuples). `COLORS_CACHE` for fast access.
- Per-automation config dicts: `MUSTER_ROLL_CONFIG`, `MSR_CONFIG`, `WAGELIST_GEN_CONFIG`,
  `MB_ENTRY_CONFIG`, `IF_EDIT_CONFIG`, `WC_GEN_CONFIG`, `FTO_GEN_CONFIG`, `PENDING_BILLS_CONFIG`
  (per-state seed digests), `STATE_DEMAND_CONFIG`, etc. — URLs + form defaults per portal page.
- `DEFAULT_LAUNCH_URLS` — sites opened when launching managed browsers.
- User config (`config.json`) is read/written via `src/utils.py` `get_config()` / `save_config()`
  in the app data dir (`user_data_dir("NREGABot", "PoddarSolutions")`).

---

## 8. Utility Layer (`src/utils.py`)

| Function | Purpose |
|---|---|
| `resource_path()` | Path for bundled assets (works in PyInstaller `_MEIPASS` and dev). |
| `get_data_path()` / `get_user_downloads_path()` / `get_nregabot_path()` / `get_report_path()` | Standard dirs: app data, `~/Downloads`, `~/Downloads/NregaBot/`, `~/Downloads/NregaBot/Report {FY}/…`. |
| `setup_logging()` / `get_logger()` | Centralized rotating file logger (app data `nregabot.log`) + stderr warnings. |
| `get_config()` / `save_config()` / `validate_config()` | User config.json helpers (`create_default_config_if_not_exists()` lives in `src/config.py`). |
| `parse_version()` | Semver compare (replaces `packaging`). |
| `format_bytes()` | Byte-size formatting — uses `humanize` if installed, **built-in fallback otherwise** (so the app never crashes if `humanize` is missing from the bundle). |
| `truncate_workcode()` | Last-6-digits privacy truncation of NREGA workcodes. |
| `_suppress_overscroll()` | macOS trackpad bounce suppression for scroll frames. |

---

## 9. Build & Release System

### Build scripts
| Script | Purpose |
|---|---|
| `scripts/build_windows.bat` | Main loader (onedir) + Lite loader (onedir) + portable zip + Inno Setup installers. **Has `--hidden-import=humanize` + `--hidden-import=src.app.app_automation`.** |
| `scripts/build_macos.sh` | Same for macOS + codesign + DMG. |
| `scripts/build_beta_portable.bat` | Beta onefile portable build (adds `config/beta.json` marker → `BETA_BUILD=True`). |
| `scripts/build_update.py` | Builds `dist/core_{mac,win}_v{version}.zip` from a **whitelist** of top-level entries (never ships `.env`, server code, secrets) and writes SHA-256 into `config/version.json`. |
| `scripts/installer.iss` / `installer_lite.iss` | Inno Setup scripts. |

### CI (`.github/workflows/release.yml`)
On push to `main`: builds Windows (loader + core win zip + Lite portable), Beta portable,
Linux loader, then publishes a GitHub release. `config/version.json` is the source of truth
for `latest_version`, changelog, and `core_update` hashes (`hash_windows`/`hash_macos`).

### Update mechanism (SHA-256 hotfix support)
- `version.json → core_update`: `version`, `url(_windows/_macos)`, `force_full_reinstall`,
  `hash_windows`, `hash_macos`, generic `hash`.
- Loader (`loader.py`) / `ServiceManager.check_for_updates_background()` compare **their own
  platform's hash** only; same-version + changed-hash = hotfix re-download. Corrupt download
  (hash mismatch) keeps the old version.
- After `build_update.py`, copy the printed SHA-256 into `config/version.json` before release.

---

## 10. Data & Assets

| Path | Content |
|---|---|
| `assets/` | `logo.png`, icons (`assets/icons/`), sounds (`assets/sounds/*.wav`), fonts (DejaVu + NotoSansDevanagari for Hindi PDFs), demo CSVs, `material_profiles.json`. |
| `config/` | `version.json`, `theme.json`, `__init__.py` (beta marker may be bundled here). |
| `docs/` | `changelog.json` (About → Changelog tab), `license.txt`, guides. |
| User data dir | `config.json`, `license.dat`, `nregabot.log`, `core_version.json`, `core.zip`, `app_live/` (extracted code). |

---

## 11. Conventions & Gotchas (IMPORTANT)

- **Never hard-code colors** — use `config.COLORS[...]`. Supports `(light, dark)` tuples.
- **Never call Tk widgets from worker threads** — always `self.app.after(0, ...)`.
- **Never `driver.quit()` in a tab's `destroy()`** — the automation thread may be using it;
  cleanup happens in `start_automation_thread()`'s wrapper `finally`.
- **Keep tabs alive after automation** — `_has_automated` flag stops `show_frame()` from
  destroying a tab that ran automation (loses logs/results otherwise).
- **Any new pip package MUST be added as `--hidden-import=` in BOTH `build_windows.bat` and
  `build_macos.sh`** (and release.yml Linux build), because the loader is the PyInstaller
  entry and app code ships as source. Forgetting this = "ModuleNotFoundError" in release
  (see the `humanize` incident). Also add a source-level fallback where feasible.
- **New tabs:** add to `src/tab_config.py` with a `creation_func` via `_lazy_import`, give the
  tab a unique `automation_key`, and add the key to `AUTOMATION_DISPLAY_NAMES` if you want a
  friendly footer name. Lite tabs go in `src/lite_tab_config.py`.
- **Lazy loading is core** — don't import selenium/pandas/etc. at module top-level in tabs
  or the startup time regresses; use function-level imports (selenium already module-level
  in `base_tab.py` deliberately).
- **Report paths** go through `get_report_path(category, fin_year)` →
  `~/Downloads/NregaBot/Report 2026-2027/<Category>/`.
- **Logging:** use `get_logger()` (never bare `print` for user-facing logs; `print` only for
  debug).
- **Testing:** run `venv/bin/python _smoke_test_tabs.py` after tab changes and
  `venv/bin/python scripts/check_imports.py` before release.

---

## 12. Common Task Recipes (where to edit)

| Task | File(s) |
|---|---|
| Change footer / status / running indicator | `src/app/app_ui.py`, `src/app/app_automation.py`, `lite_app.py` |
| Add/modify a portal automation tab | `src/tabs/<tab>_tab.py` + `src/tab_config.py` (+ `src/config.py` for URLs) |
| Add a sidebar category or tab | `src/app/app_navigation.py` (`_ICON_KEYS`), `src/tab_config.py` |
| Fix license/activation | `src/app/app_license.py`, `src/managers/services.py` |
| Change update flow | `loader.py`, `lite_loader.py`, `src/managers/services.py`, `scripts/build_update.py`, `config/version.json` |
| Macro queue / multi-tab workflows | `src/managers/workflow_manager.py` |
| Colors/theme | `src/config.py` (`COLORS`), `config/theme.json` |
| Release a new version | bump `APP_VERSION` (config.py) + `config/version.json` → run `build_update.py` → copy hash → push (CI builds) |
