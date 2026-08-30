# NREGA Bot - Architecture (Current)

> **Source of truth for current technical architecture.** Product intent lives in [`docs/PRD.md`](PRD.md); engineering rules in [`docs/RULES.md`](RULES.md); development phase in [`docs/PHASES.md`](PHASES.md).
>
> **Audience:** Engineers extending or refactoring NREGA Bot. AI assistants must verify claims against the current repository before publishing.
>
> **Status:** Verified against the current repository on **30 Aug 2026** at version **3.2.7**.
>
> **Preserved audits (historical evidence, not current architecture):**
> - `docs/NregaBot_Architecture_Audit_2026-08-29.md` - full architecture report (knowledge-graph driven, 2,509 nodes / 15,228 edges)
> - `docs/NregaBot_Dependency_CallGraph_Audit_2026-08-29.md` - call-graph + threading analysis (race conditions, implicit contracts)
> - `docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md` - production audit (Phase 1 fixes applied per `docs/AUDIT_FIX_PROGRESS_25Aug2026.md`)
>
> These audit files are **not deleted**; they are evidence of how the architecture was discovered and what was true at audit time. This document describes **verified current behavior**.

---

## 1. System overview

NREGA Bot is a Python desktop application using **CustomTkinter** for the GUI and **Selenium** for browser automation. It drives the **Indian government's MGNREGA / VB-G-RAM-G portal** through the user's own browser (Chrome, Edge, or Firefox). Architecture is a strict two-stage delivery:

```
loader.py (PyInstaller bundle)
   |-- splash + download SHA-256-verified core_{win,mac}_vX.zip
   |-- extract to app_live/
   +-- subprocess.Popen main_app.py  (Full SKU, port 60123)
                  or lite_app.py      (Lite SKU, port 60124)
                          |
                          v
                    NregaBotApp / NregaBotLiteApp
                          |
                          v
                       src/   (shared)
                          |
                          +-- managers/  (browser, services, workflows, sound, icon)
                          +-- app/       (mixins: license, nav, automation, ui)
                          +-- tabs/      (48 *_tab.py modules, lazy-loaded)
                          +-- locales/   (en, hi, kn, bn, hinglish)
                          +-- state.py   (AppState dataclass - shared mutable state)
                          +-- utils.py   (choke-points: save_license_dat, get_data_path, ...)
```

### 1.1 High-level components

| Layer | Files | Responsibility |
|---|---|---|
| **Loader** | `loader.py`, `lite_loader.py` | Splash + update verification + extraction + spawn inner app |
| **App root** | `main_app.py` (1131 lines), `lite_app.py` (~1800 lines) | `NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)` |
| **State** | `src/state.py` (200+ lines) | `AppState` dataclass; backward-compat properties on `NregaBotApp` |
| **App mixins** | `src/app/app_license.py` (2530), `app_navigation.py` (925), `app_automation.py` (1097), `app_ui.py` (729) | Five concerns split across five files |
| **Managers** | `src/managers/browser_manager.py`, `services.py`, `workflow_manager.py`, `sound_manager.py`, `icon_manager.py` | Engine for browser, update checks, macro queue, sound effects, icons |
| **Tabs** | `src/tabs/*_tab.py` (48 files) | Each tab = one portal automation; inherits `BaseAutomationTab` |
| **Utils** | `src/utils.py`, `src/error_context.py`, `src/location_sync.py`, `src/portal_login.py` | Pure helpers, choke-points, location pool |
| **Config** | `src/config.py`, `src/lite_config.py`, `src/tab_config.py`, `src/lite_tab_config.py` | URLs, colors (`COLORS`), registry, tab list |
| **i18n** | `src/i18n.py`, `src/locales/*.json`, `scripts/translations_{kn,bn,hing}_{1..5}.py` | 5 locales; generated via `scripts/build_locales.py` |
| **UI helpers** | `src/ui_components.py`, `src/tabs/autocomplete_widget.py`, `src/tabs/date_picker_popup.py` | Reusable widgets |

---

## 2. Full vs Lite architecture

Both SKUs share the same `src/` tree but have different entry points, MRO, and chrome.

| Aspect | Full (`main_app.py`) | Lite (`lite_app.py`) |
|---|---|---|
| Class | `NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)` | `NregaBotLiteApp(ctk.CTk, LicenseMixin)` |
| Tabs | 48 across 7 categories | ~17 subset |
| Window | 60123 | 60124 |
| Icons | PNG images via `LazyIconManager` | Unicode emoji |
| Splash | Animated `ModernSplashScreen` | None, simplified header |
| Autocomplete | `AutocompleteEntry` (type-ahead) | `LiteDropdown` (read-only dropdown, monkey-patched at `lite_app.py:67-72`) |
| `automation_threads` / `app_state` | Full | Minimal subset (Lite-specific config) |

**Key insight:** Lite replaces only the dropdown widget at startup (`_acw.AutocompleteEntry = _acw.LiteDropdown`). All 48 tab files work unchanged in Lite; the dropped entries simply aren't registered in `lite_tab_config.py`.

---

## 3. Loader -> core.zip -> application flow

The PyInstaller bundle is a **two-stage delivery** verified at runtime (`loader.py`):

1. **`loader.py` is the only entry bundled.** It shows its own splash, downloads the SHA-256-verified `core_{win,mac}_vX.zip` from `https://nregabot.com/version.json`, extracts to `app_live/`, then `subprocess.Popen`s the live app.
2. **`main_app.py` / `lite_app.py` are the inner stage.** They never know they're a "build" - `resource_path()` (`src/utils.py:102-117`) uses `sys._MEIPASS` for frozen and `os.path.abspath(".")` for dev.

`main_app.py` startup sequence (line numbers verified):
- **L76-85** - `setup_logging()` -> `install_crash_reporter()` -> `load_dotenv()` -> `create_default_config_if_not_exists()` -> `validate_config()`. PII masking baked into log formatter (`src/utils.py:289-322`).
- **L93-94** - `ctk.set_default_color_theme(resource_path("config/theme.json"))` + `set_appearance_mode("System")`.
- **L97** - `class NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)` - five MRO slots (see section 4).
- **L125-153** - Init order: `app_state = AppState()` -> `history_manager`, `browser_manager`, `services`, `sound_manager`, `workflows` -> `http_session = requests.Session()` (singleton) -> `gc.set_threshold(700,10,5); gc.freeze()` (memory-fragmentation guard for long-running GUI).
- **L158-159** - Show splash (own `CTkToplevel`, not the loader's).
- **L162-165** - Lazy icon manager; `preload_essential()` for the always-visible icons only.
- **L168** - `threading.Thread(target=self._background_initialization, daemon=True).start()` - heavy work goes off the UI thread.
- **L171-174** - Bind `WM_DELETE_WINDOW -> on_closing`; schedule first periodic GC at 5 min.

`lite_app.py` startup (L44-104) - same skeleton, then **monkey-patches** `AutocompleteEntry -> LiteDropdown` at L72.

---

## 4. NregaBotApp and mixin structure

`NregaBotApp` uses **Python's cooperative mixin pattern** - five classes, each owning a strict concern boundary, all mixed at the same level in the MRO:

```
ctk.CTk
  +-- LicenseMixin        # src/app/app_license.py        (~2530 lines)
  +-- NavMixin            # src/app/app_navigation.py     (~925 lines)
  +-- AutomationMixin     # src/app/app_automation.py     (~1097 lines)
  +-- UIMixin             # src/app/app_ui.py             (~729 lines)
```

MRO order matters: License first (initial heartbeat before UI), Nav (sidebar built before tabs), Automation (depends on driver), UI last.

### 4.1 Mixin concerns

| Mixin | Responsibility | Notable methods |
|---|---|---|
| **LicenseMixin** | License activation, validation, expiry, feature flags | `perform_license_check_flow`, `_preload_and_update_about_tab`, `show_activation_window`, `_ping_server_in_background` |
| **NavMixin** | Sidebar, category filter, lazy tab loading, search, shortcuts | `_create_nav_buttons`, `show_frame`, `_create_content_frames`, `_on_nav_search_change`, `_shortcut_start/_retry/_stop` |
| **AutomationMixin** | Browser launch, automation thread dispatch, finished callback | `start_automation_thread`, `on_automation_finished`, `_emergency_stop_all`, `get_driver`, `launch_*_detached` |
| **UIMixin** | Header, footer, status label, theme cycling, GC loop | `_create_header`, `_create_footer`, `set_status`, `play_sound`, `_cycle_theme`, `_gc_collection_loop` |

### 4.2 Shared mutable state (`src/state.py`)

`AppState` is a single dataclass holding all shared mutable state. UI widgets are **deliberately NOT** in `AppState` (see `state.py:22-25`) - they live as direct attrs on `NregaBotApp` because they're "tightly coupled to the GUI lifecycle." This is a deliberate escape hatch, not a slip.

Key state buckets:
- **License & auth** (LicenseMixin): `is_licensed`, `license_info`, `machine_id`, `expiry_alert_message`
- **Automation & browser** (AutomationMixin): `driver`, `active_browser`, `active_automations`, `automation_threads`, `stop_events`, `automation_progress`
- **UI navigation** (NavMixin): `tab_instances`, `category_frames`, `last_selected_category`, `current_active_tab`
- **Network/session**: `http_session`, `update_info`, `current_toast`
- **Lifecycle**: `_layout_ready`, `_gc_timer_id`, `_focus_validation_timer`, `_cached_style`

Backward-compat: `self.app.<attr>` on `NregaBotApp` delegates to `app_state.<attr>` so existing tab code works unchanged.

---

## 5. Managers

| Manager | File | Role |
|---|---|---|
| **BrowserManager** | `src/managers/browser_manager.py` | Chrome/Edge/Firefox lifecycle, `_automation_tab_handle` pinning, marker JS injection, `_thread_browser_choice` cache |
| **ServicesManager** | `src/managers/services.py` | License check `/api/validate`, update check, machine-id, prevent-sleep; has `_is_dev_mode()` subtlety |
| **WorkflowManager** | `src/managers/workflow_manager.py` | Macro queue - `queue_items`, `_wait_for_automation_finish`, `_ensure_automation_stopped` (DEC-002 parameterized), `process_global_queue` |
| **SoundManager** | `src/managers/sound_manager.py` | Play start/error/success sounds |
| **IconManager** | `src/managers/icon_manager.py` | Lazy PNG icon loading (`preload_essential` vs full set) |

**Single-sanctioned automation entry:** `start_automation_thread()` (in `AutomationMixin`) is the only way to run user work. Its `wrapper()` closure's `finally:` block guarantees cleanup (driver quit, `stop_events` clear, `active_automations` remove) and structured error reporting. The structured error model is the data backend for the admin's "Error Logs" page.

---

## 6. Tabs and lazy loading

48 `*_tab.py` modules live under `src/tabs/`. Every automation tab inherits from `BaseAutomationTab` (`src/tabs/base_tab.py`), which enforces the tab-author contract:

- `_is_alive()` - graceful shutdown detection
- `safe_after()` - thread-safe `after()` scheduling (always schedule UI updates on the Tk thread)
- `log_info()` / `log_warning()` / `log_error()` - structured log emission
- `_extract_activity_panchayat()` - for activity history
- `export_treeview_to_excel()` / `_csv()` / `_png()` - tabular export
- `_has_automated` flag - prevents `show_frame()` from destroying a tab that ran automation (loses logs/results otherwise)

Registration happens in `src/tab_config.py` (Full) and `src/lite_tab_config.py` (Lite) via `_lazy_import(class, module)`. The factory is thread-safe (lock discipline documented and tested in `tests/test_automation_thread_lifecycle.py`).

**Lazy-import rule (per `base_tab.py`):** selenium is module-level in `base_tab.py` deliberately (base owns WebDriver interaction); tabs themselves must **not** import selenium/pandas at module top-level or startup regresses.

### 6.1 Tab-author contract

When writing a new tab:

1. Subclass `BaseAutomationTab`.
2. Use function-level imports for heavy deps.
3. Set a unique `automation_key` string.
4. Add the key to `AUTOMATION_DISPLAY_NAMES` (`src/app/app_automation.py:35`) for a friendly footer name.
5. Register in `src/tab_config.py` with `_lazy_import`.
6. All UI updates must use `safe_after(0, ...)` from worker threads.

---

## 7. Automation/threading lifecycle

Three thread boundaries in the app, plus a per-tab marker-keeper daemon (added since the original audit):

| Thread | Spawned by | Work |
|---|---|---|
| **Tk main thread** | ctk | UI creation, event loop, all `after()` callbacks |
| **Automation worker [Wn]** | `start_automation_thread()` | The tab's `run_automation_logic` function |
| **Marker keeper [Mn]** | `_marker_keeper()` (per automation start) | Keeps the automation tab marked + injects `AUTATION_MARKER_JS` after navigation |
| **Background [B]** | Various (`threading.Thread(daemon=True)`) | License heartbeat, location sync, crash reporter, periodic GC |

### 7.1 Lifecycle of a single automation run

1. Tab calls `self.app.start_automation_thread(key, target, args)`.
2. `start_automation_thread` (line 122 of `app_automation.py`) plays start sound, increments usage, prevents sleep, registers in `active_automations`, creates `stop_events[key] = threading.Event()`, sets `_has_automated = True` on the tab.
3. A `daemon=True` worker thread runs the `wrapper()` closure.
4. `wrapper()` clears any leftover browser choice (`clear_thread_choice()`), calls `target(*args)`.
5. On exception: `_extract_error_context(e)` produces structured `(error_type, error_msg, error_source, error_traceback)` (see `src/error_context.py`, refactored in DEC-001). Optional screenshot saved locally (opt-in via `save_error_screenshots` setting).
6. `finally:` block: driver quit, history finish log, progress clear, `stop_events.pop(key, None)`, `active_automations.discard(key)`, `_update_running_automation_indicator()`, `_emergency_stop_btn` refresh, `restore_sleep_prevention()`.
7. `on_automation_finished()` (Tk thread via `after(0, ...)`) emits toast/sound, syncs activity log to server, syncs usage_stats to server.

### 7.2 Stop signaling

The user clicks STOP (or presses Ctrl+S). `stop_events[key].set()` is called. The tab's `run_automation_logic` is expected to check `self.app.stop_events[key].is_set()` at sensible yield points and return early.

For Macro Manager specifically: `_wait_for_automation_finish` checks `stop_events["macro"]` (the macro-specific event), NOT the individual automation's event. This is the deferred issue tracked in PHASES.md (see `docs/PHASES.md` Phase 2 deferred items).

---

## 8. Browser lifecycle

`BrowserManager` (`src/managers/browser_manager.py`) handles three browser models:

| Browser | Driver model | Per-tab driver? |
|---|---|---|
| **Chrome / Edge** | Detached subprocess with `--remote-debugging-port=9222`, CDP-attached | New `webdriver.Chrome(options=opts, debuggerAddress=...)` per `get_driver()` call |
| **Firefox** | Selenium-managed Geckodriver | ONE driver shared across all tabs (assigned to `self.driver` without lock) |

Key invariants (preserved from `docs/NregaBot_Dependency_CallGraph_Audit_2026-08-29.md`):

1. **`get_driver()` is not safe to call concurrently from multiple threads.** The 48 `run_automation_logic` callers each run on their own worker thread - but `start_automation_thread` enforces "one automation key alive at a time" (line 176 guard). So in practice, [Wn] is at most one per key, but **two different keys running on the same browser CAN both call `get_driver()` simultaneously**. The race is on `_thread_browser_choice` (dict) and on `self.driver` (assigned without a lock).
2. **`self.driver` is the in-app Firefox driver** when `active_browser == "firefox"` - every tab's `run_automation_logic` shares it. For Chrome/Edge, `get_driver` returns a *new* `webdriver.Chrome(options=opts, ...)` per call. So Firefox: 1 driver, N tabs. Chrome/Edge: N drivers, N tabs. The behavior is fundamentally different and the call site cannot tell.
3. **The pinned tab handle is for the FIRST successful resolve.** `resolve_automation_tab` returns the cached handle if still valid (line 352), else re-resolves. This is the **only mechanism** that keeps automation on the same tab across runs.
4. **`_automation_tab_handle` is stored in CDP-handle format**, which is a different ID space than the `window_handles` from the automation session. The comment at `browser_manager.py:347-349` says: "Window handles are browser-level target IDs, stable across CDP sessions" - that's the invariant that lets the marker-keeper's separate CDP session share the same `target`.

### 8.1 Browser-tab marker

`AUTOMATION_MARKER_JS` (`browser_manager.py:27-45`) prefixes the tab title with the bot emoji + red dot favicon and self-heals every 1s via `setInterval`. The marker keeper (`_marker_keeper`, see `test_marker_keeper_lifecycle.py`) is a separate CDP session that re-applies the marker after navigation. If the user closes the marked tab, automation halts (closes browser sub-tree).

### 8.2 Reported race conditions (HIGH severity, unfixed)

- **D1** - Two `start_automation_thread` calls with different keys both call `get_driver()` from [Wn]. For Chrome/Edge, both construct a new `WebDriver(debuggerAddress="127.0.0.1:9222", ...)`. Chrome allows only one CDP *control* client; the second connection's `execute_cdp_cmd` will fail. (Mitigated by try/except:pass in marker-keeper - marker silently fails.)
- **D2** - `get_driver()` is called from [Wn] but blocks on the modal dialog `wait_window` when the user has never picked. The 0.2s socket timeouts make it short; first run after launch is the only realistic trigger.

---

## 9. Workflow / Macro engine

`WorkflowManager` (`src/managers/workflow_manager.py`) is the **only** way to chain multiple automations across tabs. It owns the macro queue and orchestrates sequential execution.

Key API surface:
- `add_to_queue(tab_key, panchayat, **kwargs)` - any tab calls this to enqueue
- `process_global_queue()` - the loop that drains `queue_items`
- `_wait_for_automation_finish(key, timeout=900, macro_tab=None)` - polls `active_automations` until key clears; checks `stop_events["macro"]` for user-stop
- `_ensure_automation_stopped(key, *, max_polls=10)` - parameterized wait (DEC-002) before starting the next queued automation
- `_set_target_on_tab(tab_name, panchayat)` - duck-typed panchayat setter across heterogeneous tabs
- `_macro_call(macro_tab, fn, ...)` - safe bridge to run Macro-tab UI updates

**Three-second delay magic number:** the queue loop has a hardcoded `time.sleep(3)` between actions (audit calls this out). It is documented as "lets the previous automation clean up." PLANNED to be replaced with an event-based wait.

---

## 10. Client/server boundary

The desktop app and `nrega-server/` are **separate git repos** (see `docs/RULES.md` RULE-CI-001). The desktop app communicates with the server via:

| Endpoint | Purpose | Rate limit |
|---|---|---|
| `/api/validate` | License check (parameterized SQL, `SELECT...FOR UPDATE`) | 30/min per key |
| `/api/app-config` | State registry + maintenance/rollback/force-update flags | 30/min per IP |
| `/api/heartbeat` | `last_seen` + `app_version` + storage SUM | 120/min per IP |
| `/api/usage-stats/sync` | Feature telemetry (PII-free) | 60/hr per key, 600/hr per IP |
| `/api/location-data/sync` / `/get` | Block-wise panchayat/village sharing (sha256-hashed key) | per-key + per-IP |
| `/api/storage/...` | Cloud file manager (purchase/upgrade/list) | session-required |
| `/api/activity-log/sync` | Activity history (post-run) | per-key |
| `/api/crash-report` | Local crashes (PII-masked client + server) | per-key |
| `/webdav/` | WebDAV file access from phone/PC | session-required |

**DPDP boundary:** License keys are sha256-hashed client-side before any sync. Aadhaar/mobile/IFSC are masked in the logger *and* the network payload *and* server-side (defense-in-depth). Server never stores raw license key - it stores `sha256(license_key)` as the source token in `location_data_pool` and similar.

---

## 11. Internationalization (i18n)

`src/i18n.py` provides `tr(key, default)` (357 call sites). Five locales ship in `src/locales/`:

- `en.json` - source of truth (manually edited)
- `hi.json` - manually edited
- `kn.json`, `bn.json`, `hinglish.json` - **GENERATED** from part files

### 11.1 Locale generation pipeline

The generated locales are produced by `scripts/build_locales.py` from these source files:

- `scripts/translations_kn_{1..5}.py`
- `scripts/translations_bn_{1..5}.py`
- `scripts/translations_hing_{1..5}.py`

CI runs `build_locales.py` and **exits non-zero** if any key is missing/unused/placeholder-mismatched. Adding a new i18n key:

1. Add to `en.json` AND `hi.json` (manually edited).
2. Add to the **last** part file of each generated locale (`translations_kn_5.py`, `translations_bn_5.py`, `translations_hing_5.py`).
3. Run `venv/bin/python scripts/build_locales.py` - exit 0.
4. `{placeholder}` tokens must be identical across all languages (CI check).

`{placeholder}` placeholders use double-curly braces for Jinja-style formatting (e.g., `{count}`, `{date}`).

### 11.2 Font support

- DejaVu - default
- NotoSansDevanagari - Hindi PDF reports
- Regional scripts (Kannada, Bengali) ship in `assets/fonts/`

---

## 12. Configuration

| File | Role |
|---|---|
| `src/config.py` | `APP_VERSION`, `COLORS` palette (`(light, dark)` tuples), `STATE_PORTAL_HOSTS`, `STATE_DEMAND_CONFIG`, `STATE_JOB_CARD_PREFIXES`, `AUTOMATION_DISPLAY_NAMES` proxy, per-automation config dicts (URLs, defaults) |
| `src/lite_config.py` | Lite SKU overrides |
| `src/tab_config.py` | Full tab list (registered via `_lazy_import`) |
| `src/lite_tab_config.py` | Lite tab list |
| `config/version.json` | **Source of truth** for `latest_version`, download URLs, `core_update` block (version, urls, hashes) |
| `config/theme.json` | CustomTkinter theme (corner radii, colors, fonts) |
| `config/__init__.py` | Beta marker may be bundled here |
| `~/.env` (user) | Runtime secrets (`LICENSE_SERVER_URL`, etc.) - **never** bundled |

### 12.1 Color system

The central palette is `COLORS: Dict[str, ColorValue]` in `src/config.py:78`. Values support `(light, dark)` tuples for theme-aware rendering. **Hard-coding colors is forbidden** (see `docs/RULES.md` RULE-UI-001).

Categories include:
- Text colors (`text_dark`, etc.)
- Log tag colors (info/warning/error/success)
- Button colors (primary, hover, disabled)
- Nav button colors (active, inactive, hover)
- Footer status colors
- Header / controls colors
- Dropdown / combobox colors
- Skeleton colors (loading)
- About tab colors
- Device / activation colors

---

## 13. Update / release architecture

### 13.1 Two-stage delivery

1. **PyInstaller bundle = `loader.py` only.** (Or `lite_loader.py` for the Lite SKU.)
2. **Core update = `core_{win,mac}_vX.zip`** downloaded by the loader, SHA-256 verified, extracted to `app_live/`, then spawned.

### 13.2 Whitelist (CRITICAL - see `docs/RULES.md` RULE-REL-001)

`scripts/build_update.py` produces `core_{win,mac}_vX.zip` containing **only**:

- `main_app.py`, `lite_app.py`, `lite_loader.py`
- `requirements.txt`
- `src/`
- `config/`
- `assets/`
- `docs/changelog.json`, `docs/license.txt`

This whitelist is **mirrored** in `.github/workflows/release.yml` for the Windows build step (was previously a blacklist - changed in F1 of `docs/AUDIT_FIX_PROGRESS_25Aug2026.md`). The whitelist excludes:

- `AGENTS.md` (internal NAS IP, SSH topology)
- All tests, smoke-test scripts
- `nrega-server/` (service-account JSON files)
- `.env`, `*.pyc`, logs, `.DS_Store`

### 13.3 Hotfix and rollback

- **Hotfix:** same `latest_version`, different `core_update.hash` = re-download.
- **Rollback:** boot counter in `src/utils.py::get_boot_count()` increments on each launch. After N failed boots, `install_crash_reporter()`-based rollback restores the last known-good core zip.
- **Blocked versions / maintenance mode / force rollback:** server-driven via `/api/app-config`. Desktop honors these flags on heartbeat.

### 13.4 Version bump protocol (CRITICAL - see `docs/RULES.md` RULE-REL-002)

When releasing:

1. Patch-level bump only (3.2.6 -> 3.2.7).
2. Update `APP_VERSION` in `src/config.py`.
3. Update `latest_version` + URLs + changelog entry in `config/version.json`.
4. **Set all three hashes (`hash`, `hash_windows`, `hash_macos`) to empty strings `""`.**
5. User runs `scripts/deploy_version.sh` which auto-fills `hash_windows` from GitHub release, then `build_macos.sh` produces `hash_macos`.

**The agent NEVER fills hashes.** The agent NEVER runs `build_update.py` or `build_macos.sh`. These are deploy-only steps.

---

## 14. Important architectural risks

The following risks are documented in `docs/NregaBot_Dependency_CallGraph_Audit_2026-08-29.md` and `docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md`. Phase-1 audit items have been fixed (per `docs/AUDIT_FIX_PROGRESS_25Aug2026.md`); the rest are PLANNED.

### 14.1 Threading / race conditions

| ID | Risk | Severity | Where | Status |
|---|---|---|---|---|
| D1 | Two `start_automation_thread` calls with different keys both call `get_driver()` from worker threads; second CDP client fails | HIGH | `browser_manager.py:253-279` | Mitigated by try/except in marker; PLANNED proper fix |
| D2 | `get_driver()` blocks on `wait_window` modal if user has never picked | HIGH | `browser_manager.py:668` | 0.2s socket timeout makes it brief |

### 14.2 Security / release pipeline

| ID | Risk | Severity | Status |
|---|---|---|---|
| S1 | Windows core zip ships internal docs/dev files | P0 | **FIXED** in audit batch (F1); whitelist now strict |
| S2 | Hard-coded `EVO_*` API fallbacks (LAN IP + API key) | P1 | **FIXED** in audit batch (F4) |
| S3 | Unsigned core zips (no ed25519 signing) | P1 | PLANNED (not implemented) - audit Phase 2 #8 |
| S4 | HTTP update URLs (vs HTTPS) | P1 | Fixed in F3; HTTPS enforced |
| S5 | Raw license key as bearer token | P3 | PLANNED (HMAC-signed tokens) |
| S7 | License key in crash payloads | P3 | FIXED - PII masking at logger + payload |

### 14.3 Reliability

| ID | Risk | Severity | Status |
|---|---|---|---|
| U1 | Loader will downgrade users or accept empty hash | P1 | **FIXED** in F2 (downgrade refusal + empty-hash fail-safe) |
| A1 | MR Fill wrong workcode on retry | P1 | **FIXED** in F9 |
| A2 | Sleep sites should be wait conditions | P2 | PLANNED |
| A3 | Alert-probe session-death differentiation | P2 | PLANNED |

---

## 15. Current known technical debt

This section captures debt that is acknowledged but intentionally NOT fixed in the current Phase 2 scope (see `docs/PHASES.md`):

| Item | Source | Status |
|---|---|---|
| 3-second `time.sleep(3)` between macro queue actions | Audit | PLANNED - event-based wait |
| `_wait_for_automation_finish` always polls `stop_events["macro"]` instead of the per-key event | PHASES.md Phase 2 deferred | KNOWN DEFERRED |
| `license.dat` chmod 600 across 7 sites | AUDIT_FIX_PROGRESS F10 | DEFERRED |
| `lite_app.py` and `main_app.py` share update logic but diverge (Lite is currently safer than Main) | Audit U1 follow-up | PLANNED - unify in one module |
| bare-`except:` sweep was 44 sites, code quality target ongoing | Batch-6 / T2 | Mostly complete; CI gate prevents new occurrences (F821,E722) |
| `_automation_tab_handle` race with manual `driver.get(url)` outside automation | Audit | Documented; pinned-handle cache self-heals |
| `PENDING_BILLS_CONFIG` not yet integrated with State Registry | PHASES | Manual edit for new states |

---

## 16. Appendix - diagnostic fingerprints

Quick facts an AI or engineer can re-derive to confirm they're looking at the current repo:

| Fact | How to verify |
|---|---|
| Version | `grep APP_VERSION src/config.py` |
| Tab count | `find src/tabs -maxdepth 1 -name '*_tab.py' \| wc -l` |
| Test count | `python3 -m pytest -q` |
| Whitelist contents | `head -100 scripts/build_update.py` |
| Mixin MRO | `grep -nE 'class NregaBotApp' main_app.py` |
| `AUTOMATION_DISPLAY_NAMES` proxy | `head -90 src/app/app_automation.py` |
| Browser tab marker | `sed -n '27,45p' src/managers/browser_manager.py` |
| Locale generation | `ls scripts/translations_*.py` |
| Two-repo warning | `cat AGENTS.md \| head -40` (line ~26-39) |

---

*Last verified: 30 Aug 2026 against `main @ 1eb4e07`. If you find a contradiction between this doc and the source code, the source code wins - and please update this doc.*
