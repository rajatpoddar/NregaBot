I have a comprehensive picture. The full architecture report is below.

---

# 🏗️ NregaBot — Practical Architecture Report

> **Scope:** Desktop app at `/Users/rajatpoddar/Documents/Projects/NregaBOT-Latest/NregaBot` (the `nrega-server/` Flask backend is a separate git repo and was not indexed — out of scope here).
> **Index stats:** 2,509 nodes / 15,228 edges, 0 parse-partial, 0 skipped. 100 Python source files, 2 YAML/JSON, 1 release workflow.
> **Mode:** Read-only. No files were modified.

---

## 1. Application entry points and startup flow

The project has **two parallel entry points** for two product SKUs that share `src/`:

| Entry | SKU | Window | Tabs | Icons | Splash |
|---|---|---|---|---|---|
| `main_app.py` (1131 lines) | **NREGABot** (full) | 60123 | 48 (across 7 categories) | PNG images (LazyIconManager) | Animated `ModernSplashScreen` |
| `lite_app.py` (~1800 lines) | **NREGABot Lite** | 60124 | ~17 (subset) | Unicode emoji | None, simplified header |
| `loader.py` / `lite_loader.py` | Wrapper | — | — | — | Own `ModernSplashScreen`; downloads & verifies `core.zip` |

**The PyInstaller bundle is a 2-stage delivery** — verified at runtime from the loader module (`loader.py:46-52`, `loader.py:75-81`):
1. `loader.py` is the only entry bundled. It shows its own splash, downloads the SHA-256-verified `core_{win,mac}_vX.zip` from `https://nregabot.com/version.json`, extracts to `app_live/`, then `subprocess.Popen`s the live app.
2. `main_app.py` / `lite_app.py` are the inner stage. They never know they're a "build" — `resource_path()` (`src/utils.py:102-117`, `loader.py:75-81`) uses `sys._MEIPASS` for frozen and `os.path.abspath(".")` for dev.

**`main_app.py` startup sequence** (line numbers verified):
- **L76-85** — `setup_logging()` → `install_crash_reporter()` → `load_dotenv()` → `create_default_config_if_not_exists()` → `validate_config()`. PII masking is baked into the log formatter (`src/utils.py:289-322`).
- **L93-94** — `ctk.set_default_color_theme(resource_path("config/theme.json"))` + `set_appearance_mode("System")`.
- **L97** — `class NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)` — five MRO slots, see §2.
- **L125-153** — Init order: `app_state = AppState()` → `history_manager`, `browser_manager`, `services`, `sound_manager`, `workflows` → `http_session = requests.Session()` (singleton) → `gc.set_threshold(700,10,5); gc.freeze()` (memory-fragmentation guard for long-running GUI).
- **L158-159** — Show splash (own `CTkToplevel`, not the loader's).
- **L162-165** — Lazy icon manager; `preload_essential()` for the always-visible icons only.
- **L168** — `threading.Thread(target=self._background_initialization, daemon=True).start()` — heavy work goes off the UI thread.
- **L171-174** — Bind `WM_DELETE_WINDOW → on_closing`; schedule first periodic GC at 5 min.

**`lite_app.py` startup** (L44-104) — same skeleton, then **monkey-patches** `AutocompleteEntry → LiteDropdown` at L72 (so all 48 tab files work unchanged in Lite, but typing/autocomplete is replaced with a read-only dropdown — `lite_app.py:67-72`).

> **Why this matters:** the `loader.py` → `core.zip` → `main_app.py` chain is the single biggest architectural concept. If you ever doubt what runs where, look at the loader's `MODULES_TO_CHECK` and the verified hash in `config/version.json`.

---

## 2. NregaBotApp class hierarchy and major responsibilities

`NregaBotApp` (main_app.py:97) uses **Python's cooperative mixin pattern** — five classes, each owning a strict concern boundary, all mixed at the same level in the MRO:

```
ctk.CTk
  ├── LicenseMixin        # src/app/app_license.py        (2,530 lines — biggest mixin)
  ├── NavMixin            # src/app/app_navigation.py     (924 lines)
  ├── AutomationMixin     # src/app/app_automation.py    (1,150 lines)
  └── UIMixin             # src/app/app_ui.py             (729 lines)
```

| Mixin | Owns | Key public surface |
|---|---|---|
| **LicenseMixin** | License validation/activation, expiry alerts, activation window, Google/Passkey quick-login, `_ping_server_in_background` (state registry fetch), feature flags, About tab data | `perform_license_check_flow()`, `check_license()`, `show_activation_window()`, `_preload_and_update_about_tab()` |
| **NavMixin** | Sidebar category filter, tab search, **`show_frame()`** (the lazy tab loader), `get_tabs_definition()` proxy, Ctrl+K / Ctrl+Enter / Ctrl+S / Ctrl+R global shortcuts, Macro Manager dropdown | `_create_nav_buttons()`, `show_frame(name)`, `_filter_nav_menu()`, `_on_nav_search_change()` |
| **AutomationMixin** | `start_automation_thread()` (the dispatcher), `wrapper()` (the error-and-finish harness), `_emergency_stop_all()`, `on_automation_finished()`, WhatsApp notify on finish, `AUTOMATION_DISPLAY_NAMES` dict (44 friendly names) | `start_automation_thread(key, target, args)`, `on_automation_finished()` |
| **UIMixin** | Header, footer, status label, "▶ Running: …" indicator, theme cycle, sound toggle, resize smoothing (debounce + overlay), macOS titlebar sync | `_create_header()`, `_create_footer()`, `_cycle_theme()`, `set_status()` |

**Why mixins, not subclasses:** Mixins let each concern live in its own file (~700-2,500 lines) while sharing `self.app_state` (the dataclass) and `self.app.<attr>` backward-compat properties. The whole app is **one Tk root** (single-instance enforced by socket port 60123) — there is no "controller" and "view" split. The tradeoff is **tight coupling to the `app` proxy** (see §11).

**`AppState` (`src/state.py`)** is the centralized dataclass backing everything. UI widget refs are *not* in it (per the comment at L22-24) — they live as direct attrs on `NregaBotApp`. Sections include: LICENSE & AUTH, AUTOMATION & BROWSER, UI STATE, NETWORK/SESSION, INTERNAL/LIFECYCLE.

> **Sanity check on graph:** `NregaBotApp` has 4 inbound (called by main) and 4 outbound (calls into `app_state`, mixins, etc.) — a single hot hub. The four mixin classes each have 1-2 inbound and 0 outbound. That fan-in asymmetry is exactly the "god object" pattern that mixins preserve intentionally.

---

## 3. Tab/module architecture and lazy loading

**48 tab classes** live in `src/tabs/*.py`, plus 7 shared widget/helper modules:
- `base_tab.py` — `BaseAutomationTab(ctk.CTkFrame)` — the parent for **all 44 automation tabs** (the 4 non-automation tabs are `HomeTab`, `AboutTab`, `SettingsTab`, `FileManagementTab`, `ActivityLogTab`, `MacroManagerTab`, `LoginAutomationTab`, `WhatsAppChatTab`).
- `autocomplete_widget.py` — `AutocompleteEntry` (replaced with `LiteDropdown` in Lite via monkey-patch at `lite_app.py:72`).
- `date_entry_widget.py` — date picker used across reports.
- `date_picker_popup.py` — pop-up calendar.
- `history_manager.py` — SQLite-backed activity log + cloud sync.
- `professional_pdf.py` — PDF generation for exports.
- `_imports.py` — shared import hub that tabs reach for (heavy libs cached here).

**The lazy loader is the most important performance feature.** The `tab_config.py` system (`src/tab_config.py:23-48`) is a textbook double-checked-locking factory:

```python
_TAB_MODULE_IMPORT_LOCK = threading.Lock()   # module-level

def _lazy_import(class_name, module_path):
    _cache = {}
    def factory(parent, app):
        nonlocal _cache
        if class_name not in _cache:
            with _TAB_MODULE_IMPORT_LOCK:           # serializes heavy imports
                if class_name not in _cache:        # double-checked
                    mod = importlib.import_module(module_path)
                    _cache[class_name] = getattr(mod, class_name)
        return _cache[class_name](parent, app)
    return factory
```

`get_tabs_definition(app)` returns a `{category: {tab_name: {"creation_func": factory, "icon": ..., "key": ...}}}` dict — **no tab class is loaded at startup** (AGENTS.md §4: ~40-60% startup reduction). The first call to `show_frame(name)` (`src/app/app_navigation.py:274`) instantiates the tab via the factory.

**Two parallel tab configs:**
- `src/tab_config.py` — full set (48 tabs, 7 categories: Dashboard / MR & Wage Management / EMB Approvals / Schemes / Smart Tools / Verification & Utility / Reports & Tracking / Tools & Settings).
- `src/lite_tab_config.py` — **imports `_lazy_import` from `tab_config` and reuses it**; only declares a subset (~17 tabs), uses Unicode emoji instead of PNG icons.

**Important invariant (enforced by `_TAB_MODULE_IMPORT_LOCK`):** if a tab module's top-level imports triggered another `_lazy_import`, the lock would deadlock. The comment at `src/tab_config.py:34-37` explicitly forbids this — none of today's 48 tabs do it.

> **Where to find what each tab does:** `AUTOMATION_DISPLAY_NAMES` in `src/app/app_automation.py:34-77` is the **single source of truth** for "what does this automation key mean" (the footer "▶ Running: …" reads from it). When adding a tab, register in both `tab_config.py` and this dict (AGENTS.md §4.7).

---

## 4. Automation / threading architecture

This is the **most intricate part** of the codebase and the highest-risk area (see §11).

**`AutomationMixin.start_automation_thread(key, target, args=())` — `src/app/app_automation.py:175-379`** is the only sanctioned way to run an automation. Verbatim contract:

1. **L176-179** — Guard: if `automation_threads[key].is_alive()` → play "error" sound + `messagebox.showwarning("Busy", "Task running")` and return. No queueing; **second click is rejected**.
2. **L181-185** — Play "start" sound → `history_manager.increment_usage(key)` → `prevent_sleep()` (Windows-only via `services.py` `subprocess.Popen`) → add key to `app_state.active_automations` → create fresh `threading.Event` in `app_state.stop_events[key]` → clear stale progress.
3. **L188-191** — `_update_emergency_stop_btn()` + `_update_running_automation_indicator()` + `_refresh_all_tab_buttons()` (queue-aware Start/Add-to-Queue).
4. **L193-195** — If `minimize_var` is on and a driver exists, minimize the active browser + toast.
5. **L198-214** — `getattr(target, '__self__', None)` extracts the bound tab instance. Mark `_has_automated = True`, record `activity_start_time`, call `_refresh_activity_data()`, and `history_manager.log_automation_start(...)` with panchayat/village snapshot.
6. **L216-557 — `wrapper()` daemon thread** (the actual worker). This is the error-and-finish harness:
   - `target(*args)` runs in the worker.
   - On exception: `_extract_error_context(e)` → `(error_type, error_msg, error_source, error_traceback)` (L86-136, structured: "file:line:function" chain capped at 600 chars, full traceback capped at 4000).
   - **Opt-in failure screenshot** (L240-254): only if `get_config("save_error_screenshots", False)` is on, **saved locally only** to `~/Downloads/NregaBot/Temp/error_screenshots/`, **never uploaded** (DPDP).
   - **Browser-closed detector** (L258-268): catches "no such window" / "target window already closed" / "web view not found" / "invalid session id" and shows a friendly toast + `messagebox.showwarning`.
   - **`finally:` cleanup (L274-557)** — the *only* place automation finish is handled:
     - L277-280 — clear per-run browser choice
     - L281-282 — compute duration
     - **L486-527** — `log_automation_finish(...)` with `status` ∈ `{success, failed, stopped}` (driven by `error_msg` + `stop_event.is_set()`)
     - L529-534 — `tab.show_automation_notification(status=...)` (per-tab hook)
     - **L536-557 — Triple cloud sync**, each in its own try block:
       - `_sync_automation_results_to_cloud(key, ...)` — raw results → server.
       - `history_manager.sync_activity_log_to_server(license_key=...)` — Phase 2 log.
       - `history_manager.sync_usage_stats_to_server(license_key=...)` — feature telemetry (per AGENTS.md §6.5: usage_stats table).
   - L285-291 — `stop_events.pop(key)`, mark thread dead, refresh UI.

**`_emergency_stop_all()` (`src/app/app_automation.py:729-779`)** iterates every `stop_event` and sets it. Workers cooperatively check `stop_event.is_set()` (the convention).

**`WorkflowManager.process_global_queue()` (`src/managers/workflow_manager.py:210-349`)** is the **Macro Manager** — a *separate* execution engine that runs queued items **one at a time** across multiple tabs:
- Items live in `self.queue_items` (central store, survives `MacroManagerTab` being destroyed — comment at L14-17).
- For each item: `app.show_frame(tab_name)` → `time.sleep(1.5)` → `_set_target_on_tab()` → `tab.start_automation()` → `_wait_for_automation_finish(key, timeout=900, macro_tab=None)` (a polling loop checking `key in app.active_automations`).
- The macro **itself** has a `stop_events["macro"]` so a user can stop the whole queue independently of individual automations.

**Browser automation is stateful and shared.** `BrowserManager` (`src/managers/browser_manager.py:51-67`) holds a single `self.driver` + `self.active_browser`. The `_automation_tab_handle` is **pinned** (line 67) — first automation run grabs a CDP tab handle and reuses it for *every* later run, because `window_handles[0]` is not stable across CDP sessions. WDM noise is silenced with `os.environ['WDM_LOG'] = '0'` at L70.

**`AUTOMATION_MARKER_JS`** (`browser_manager.py:27-45`) is the red-dot favicon + "🤖 NREGA-BOT ⚙ Running" tab title injected via CDP `Page.addScriptToEvaluateOnNewDocument` — survives navigation via a self-healing `setInterval` and a CDP on-load hook, so the user can always see which tab is being driven.

> **The two-thread invariant** every tab author must respect: **(a) never touch Tk widgets from a worker thread — use `self.app.after(0, ...)`; (b) never call `driver.quit()` in `destroy()` — the wrapper in `start_automation_thread` owns cleanup.** AGENTS.md §4.3 rules 2 and 3.

---

## 5. Managers, mixins, utilities — how they interact

The seven managers (`src/managers/`) each have a single concern and a `self.app` reference back to the host:

| Manager | File | Lines | Concern | Touches |
|---|---|---|---|---|
| `BrowserManager` | `browser_manager.py` | ~700 | Launch Chrome/Edge (detached, debug port 9222/9223), Firefox (managed), driver lifecycle, automation-tab pinning, marker JS | `self.app.play_sound`, `self.app.show_toast` (calls back into mixins) |
| `ServiceManager` | `services.py` | ~600 | License check (`/api/validate`), update check (`version.json` polling), machine-id (MAC), sleep-prevention subprocess, **dev-mode detector** (`_is_dev_mode()`, L19-40) | `self.app.license_info`, `self.app.update_info`, `self.app.after(0, ...)` |
| `WorkflowManager` | `workflow_manager.py` | ~400 | Macro/queue execution, cross-tab state snapshotting (`_scrape_workcodes_from_active_tab`), panchayat setter across heterogeneous widgets | `self.app.tab_instances`, `self.app.show_frame`, `self.app.stop_events["macro"]` |
| `SoundManager` | `sound_manager.py` | ~150 | Pure-stdlib audio (afplay / winsound / aplay→paplay→ffplay), single-instance macOS, path cache | `self.app.sound_switch_var` |
| `IconManager` | `icon_manager.py` | (lazy) | Lazy PNG load + cache, `preload_essential()` | None (pure data) |

The managers collectively **delegate to the app, don't own it** — `BrowserManager` calls `self.app.play_sound()` rather than `SoundManager` directly. This creates a small "everything goes through the app" coupling (see §11 risk).

**Utility hub — `src/utils.py` (~900 lines) is the highest-fan-in file in the codebase (boundaries: 15 inbound calls).** Key functions:
- `resource_path()` (used by PyInstaller `_MEIPASS` resolution — has 23 call sites).
- `get_data_path()` (44 call sites — every file write goes through here, so `user_data_dir("NREGABot", "PoddarSolutions")` is the only data location).
- `get_nregabot_path()` / `get_report_path()` (16 call sites — the only way to reach `~/Downloads/NregaBot/...`).
- `get_logger()` (42 call sites — every module gets a logger from the same root, with PII-masking formatter).
- `get_config()` / `save_config()` / `validate_config()` (12+9+1 call sites — single chokepoint for `config.json` I/O; corrupted config is auto-backed up and reset, `src/utils.py:665-695`).
- `save_license_dat()` (4 call sites — **THE only writer of `license.dat`**, enforces utf-8 + `chmod 0o600`, AGENTS.md §4 rule 12).
- **`install_crash_reporter()` (L478-567)** — global `sys.excepthook` + `ThreadingException` hook, saves uncaught exceptions to `~/Downloads/NregaBot/Temp/crashes/`, **uploads to `/api/crash-report` in a daemon thread** (server-side also masks PII).
- `record_boot_attempt()` / `mark_clean_boot()` / `should_rollback_boot()` / `remember_bad_version()` — the **boot-counter rollback system** (AGENTS.md §7) shared between `loader.py`, `lite_loader.py`, `services.py`, `main_app.py`, `lite_app.py`. Counter resets only on a fully-rendered main window; ≥3 crash-loop within 10 min triggers auto-restore of `core_prev.zip`.
- `mask_pii_text()` / `_AADHAAR_SPACED_RE` / `_MOBILE_RE` / `_IFSC_RE` (L237-286) — **DPDP Act 2023 compliance** (Aadhaar/mobile/IFSC regex, with the explicit note that the patterns are **kept in sync with `nrega-server/app/pii_mask.py`** — drift would silently desync masking).
- `translate_error()` (L380-437) — user-friendly mapping for 20+ Selenium/network error strings.

**i18n hub — `src/i18n.py`** is the 357th most-called function in the graph (`tr()` is used 357 times). It loads JSON locale files from `src/locales/{en,hi,...}.json`, falls back to English → caller `default` → key name, **never raises**. `STATE_LANGUAGE_MAP` (L50-89) auto-suggests a language from the user's state. Locale JSONs are **CI-generated** from `scripts/translations_{lang}_5.py` (AGENTS.md §4 rule 9 — never edit `kn.json`/`bn.json`/`hinglish.json` by hand).

> **The interaction triangle:** `tab → app_state → manager`. Tabs never import managers directly; they go through the app proxy. Managers never touch each other; they go through the app. The app is the universal mediator. This is what makes lazy tab loading work — the tab can be imported without dragging in Selenium until it's actually instantiated.

---

## 6. Configuration and environment handling

**Three layers of configuration** (deliberately split):

| Layer | Source | Read via | Notes |
|---|---|---|---|
| **Module constants** | `src/config.py` (~1,400 lines) | direct import `from src import config` | `APP_VERSION = "3.2.7"`, `APP_VERSION_WIRE = "3.2.7"`, `LICENSE_SERVER_URL` (env-overridable, L14), `OS_SYSTEM`, `COLORS` (the **central palette — 100+ entries**, `(light, dark)` tuples), state portal hosts/demand configs, automation display names |
| **JSON config** | `~/AppData/.../user_data_dir/config.json` | `get_config(key, default)` / `save_config(key, value)` | User prefs: `theme_mode`, `sound_enabled`, `last_selected_category`, `app_language`, `save_error_screenshots` |
| **License state** | `license.dat` (utf-8, `chmod 0o600`) | `save_license_dat()` only | Raw key, expires_at, user info — PII-sensitive, single-writer policy |

**Env vars** (only 6 in the whole graph, intentionally minimal):
- `LICENSE_SERVER_URL` — defaults to `https://nregabot.com` (`src/config.py:14`).
- `EVO_BASE_URL`, `EVO_INSTANCE`, `EVO_API_KEY` — **default to empty** since the 25 Aug 2026 audit removed hard-coded fallbacks (the server, not the client, owns WhatsApp).
- `LITE_LOADER_ACTIVE` — flag.
- `WDM_LOG=0` — silenced in `BrowserManager.__init__` (`browser_manager.py:70`).

**State registry (server-driven config)** — `src/config.py:597-731`:
- `STATE_PORTAL_HOSTS`, `STATE_DEMAND_CONFIG`, `STATE_JOB_CARD_PREFIXES` are **fallback** dicts.
- `update_state_registry(states)` is called from `LicenseMixin._ping_server_in_background` (per AGENTS.md §4.5) every ~2 min — server's `/api/app-config` pushes overrides; client sanitizes strings only (invalid payload never crashes).
- Consumers: `get_state_portal_host()`, `get_state_demand_config()`, `get_state_job_card_prefixes()`, `get_state_portal_url()` (re-hosts only `vbgramgde\d+` / `nregade\d+.dord.gov.in`; report/MIS and public hosts untouched).

**Beta build support** (`src/config.py:25-44`): `scripts/build_beta_portable.bat` ships a `config/beta.json` marker; `_detect_beta_build()` reads it and overrides `APP_VERSION` to e.g. `3.0.8-beta`. Normal builds never have the marker → `BETA_BUILD = False`.

**Version bumping protocol (AGENTS.md §4 rule 10)**: patch-level only (e.g. `3.2.6 → 3.2.7`); update `src/config.py::APP_VERSION` + `config/version.json::latest_version` + `core_update.version` + changelog; **set the three hashes to `""`**; agent never fills hashes (user runs `scripts/deploy_version.sh`).

**Config validation self-heal** (`src/utils.py:665-695`): if `config.json` is corrupted, it's backed up as `config.json.corrupted` and a fresh default is created — startup never crashes on bad config.

---

## 7. Data flow through the application

Three end-to-end flows you can trace:

### Flow A — User runs a single automation
```
User clicks Start in MrFillTab
  → MrFillTab.start_automation()  (calls base_tab's start_automation_thread)
    → AutomationMixin.start_automation_thread(key="mr_fill", target=run_logic, args=())
      ├─→ history_manager.increment_usage("mr_fill")  [local SQLite]
      ├─→ prevent_sleep()  [Windows subprocess]
      ├─→ app_state.active_automations.add("mr_fill")
      ├─→ app_state.stop_events["mr_fill"] = threading.Event()
      ├─→ browser_manager.get_driver()  [pinned automation tab handle]
      ├─→ threading.Thread(target=wrapper, daemon=True).start()
      │     └─→ target(*args)  ← the actual Selenium code in MrFillTab
      │           ├─ webdriver calls (selenium)
      │           ├─ log_info()  → safe_after()  → Tk Text widget (main thread)
      │           └─ writes results_tree (main thread via after())
      └─→ on_automation_finished()  (on the SAME worker thread)
            ├─ history_manager.log_automation_finish(...)
            ├─ tab.show_automation_notification(...)
            ├─ _sync_automation_results_to_cloud()  [background HTTP]
            ├─ history_manager.sync_activity_log_to_server()  [background HTTP]
            └─ history_manager.sync_usage_stats_to_server()  [background HTTP]
```

### Flow B — App startup (full)
```
loader.py  (PyInstaller entry)
  ├─ ModernSplashScreen (CTk root, own borderless window)
  ├─ GET https://nregabot.com/version.json
  ├─ platform-specific hash compare (hash_windows / hash_macos)
  ├─ download + SHA-256 verify core.zip
  ├─ extract to app_live/
  ├─ subprocess.Popen([sys.executable, "main_app.py"])
  └─ main_app.py
       ├─ setup_logging()  install_crash_reporter()  validate_config()
       ├─ NregaBotApp.__init__
       │    ├─ AppState()  (defaults from dataclass)
       │    ├─ HistoryManager / BrowserManager / ServiceManager / SoundManager / WorkflowManager
       │    ├─ http_session = requests.Session()
       │    ├─ show splash
       │    ├─ icon manager preload_essential()
       │    └─ threading.Thread(_background_initialization, daemon).start()
       │         └─ license check (servers) + update check (servers)
       ├─ _create_header / _create_nav_buttons / _create_content_frames (main thread)
       │     └─ NavMixin._create_nav_buttons: build sidebar with NO tab instances yet
       ├─ show_frame("About", raise_frame=False)  ← first real tab load (lazy)
       │     └─ _lazy_import("AboutTab", "src.tabs.about_tab")  ← FIRST module import
       ├─ LicenseMixin.perform_license_check_flow()  (on main thread via after())
       │     └─ licensed → _setup_licensed_ui() / unlicensed → _setup_unlicensed_ui()
       └─ on_closing  (registered)
```

### Flow C — Location pool sync (silent background)
```
any tab finishes automation
  → on_automation_finished → _sync_automation_results_to_cloud (or settings_tab._scrape_success)
    → location_sync.sync_current_location(app)  [10-min throttle, daemon thread]
      ├─ reads history_manager for (state, district, block)
      ├─ location_hierarchy.get_children("Block", block, "Panchayat")
      ├─ POST /api/location-data/sync  (license_key = sha256 hash, never raw)
      └─ on settings: fetch_block_from_server() → apply_server_data()
            (missing-only merge — user local edits NEVER overwritten)
```

---

## 8. External API / service integrations

The desktop app talks to **one server** (`config.LICENSE_SERVER_URL`, default `https://nregabot.com`) and **one local browser**. All HTTP calls live in just **6 files** (per `search_code` for `requests.*`):

| File | Endpoints called |
|---|---|
| `src/managers/services.py` | `POST /api/validate` (license), `GET /version.json` (update), `GET /api/app-config` (state registry — via `LicenseMixin`) |
| `src/app/app_automation.py` | `POST /api/cloud-reports/sync` (raw results — 30-day web storage) |
| `src/location_sync.py` | `POST /api/location-data/sync`, `GET /api/location-data/get` (block data pool) |
| `src/tabs/history_manager.py` | `POST /api/activity-log/sync`, `POST /api/usage-stats/sync` (per AGENTS.md §6.5) |
| `src/utils.py` | `POST /api/crash-report` (in `_upload_crash_report`, daemon thread, L457-476) |
| `src/tabs/file_management_tab.py` | cloud file sync |
| `src/tabs/whatsapp_chat_tab.py` | legacy direct Evolution API (EVO_BASE_URL — empty by default after audit) |
| `src/tabs/about_tab.py` | update info refresh |
| `src/tabs/pending_bills_tab.py` | its own sync |
| `src/tabs/settings_tab.py` | (one) |

**Browser automation is the dominant "external" surface**, not HTTP. The portal is `https://vbgramg.nregabot.com/` (and other state-specific hosts from `STATE_PORTAL_HOSTS`). `BrowserManager.launch_firefox_managed()` (L165-220) configures Firefox to **disable background-tab throttling** (`dom.min_background_timeout_value=10`, `dom.timeout.background_throttling_max_budget=-1`) — without this, background JS controls (radios, dropdown postbacks) get rate-limited and automation breaks.

**`AUTOMATION_MARKER_JS`** is also "external" in spirit — it injects into the portal page via CDP to identify the automation tab visually.

**WhatsApp is server-mediated.** Desktop app never speaks to Evolution API directly anymore (after the 25 Aug 2026 audit removed the hard-coded fallback). All WhatsApp notifications go through `/api/notify` server-side; the client's role is limited to (a) showing a toast and (b) supplying `license_key` for context.

---

## 9. Error handling and logging

**Logging is centralized** in `src/utils.py:23-64`:
- Root logger name: `"nregabot"`.
- File handler: `RotatingFileHandler` (5 MB × 2 backups) at `nregabot.log` in the data dir.
- Console handler: `WARNING+` only to stderr.
- **`_PiiMaskingFormatter`** (L289-322) wraps *both* the message and the `exc_info` traceback through `mask_pii_text()` — Aadhaar, mobile, IFSC, sensitive column names (`aadhaar/aadhar/uid/account/bank/ifsc/mobile/phone/voter/pan/jobcard/name/...`) are masked before they reach the file. **Server side does the same in `nrega-server/app/pii_mask.py`** — comment at L248-250 explicitly warns to keep both in sync.

**`get_logger()` returns the same singleton** — 42 call sites, all in the form `logger = get_logger()` at module top.

**`install_crash_reporter()` (L478-567)** catches:
- `sys.excepthook` — main thread uncaught exceptions.
- `threading.excepthook` — thread exceptions (Python 3.8+).
- Saves full traceback + PII-masked context to `~/Downloads/NregaBot/Temp/crashes/`.
- Best-effort `POST /api/crash-report` in a daemon thread (server-side rate-limited + PII masked too — defense in depth).
- **Never raises** (the crash path must not crash).

**Per-automation error handling** lives in `AutomationMixin.start_automation_thread.wrapper()` (L216-557, see §4):
- `_extract_error_context()` (L86-136) returns structured `(error_type, error_msg, error_source, error_traceback)`.
- Browser-closed detector catches the 4 "user closed the tab mid-run" patterns and shows a friendly warning instead of a traceback.
- `finally:` block guarantees `on_automation_finish` is always called — even if the user kills the thread.

**`BaseAutomationTab` error surface** (`src/tabs/base_tab.py`):
- `log_info()` (200 call sites), `log_error()` (105), `log_warning()` (103) — thin wrappers around `self.app.log_message()` + `_safe_after()` so that even if the tab is destroyed, the callback is no-op'd (`AfterTracker` pattern, `src/ui_components.py`).
- `_is_alive()` (52 call sites) — checked before every UI mutation to prevent TclError on dead widgets.
- `safe_after()` — same idea for `after()` callbacks.
- `translate_error()` (utils) — user-friendly mapping for 20+ Selenium/network error patterns (`utils.py:380-437`).

**`NavMixin.show_frame()` (L274-365)** wraps every tab load in try/except — on failure it pops a graceful "Error" frame in the content area (not a Tk crash) with **Retry** and **Go Home** buttons and an expandable traceback panel. This is one of the strongest UX features in the codebase.

**`tab_config._lazy_import` race protection** — `_TAB_MODULE_IMPORT_LOCK` ensures two concurrent `show_frame()` calls cannot import the same tab module twice and crash with "partially initialized module pandas" (comment at `tab_config.py:14-20` documents the incident).

**`_is_dev_mode()`** (`src/managers/services.py:19-40`) — update check is suppressed in dev runs to avoid the "false bug-fix update popup on every launch" failure mode (no `core_version.json` in source checkout).

**WhatsApp-on-error**: tab-level `show_automation_notification(status)` is called on finish; tabs like `pending_bills_tab` extend it to send a WhatsApp summary.

---

## 10. Test architecture and current test coverage

**3 test files** (`tests/`), all pure pytest:

| File | Target | Pattern |
|---|---|---|
| `tests/test_utils_pure.py` | `src/utils.py` pure helpers | `parse_version`, `current_financial_year` (April boundary!), `truncate_workcode`, `mask_pii_text` (DPDP) |
| `tests/test_update_rollback.py` | `src/utils.py` boot-counter + `loader.py::_rollback_to_previous` + `lite_loader.py` | Real `tmp_path` fixture, monkeypatches `get_data_path` — never touches real user data |
| `tests/test_location_merge.py` | `src/location_sync.py::apply_server_data`, `src/tabs/demand_tab.py::_get_village_code` | Fake `FakeHierarchy` + `FakeHistory` — missing-only merge invariant, idempotency, case-insensitive dedup |

**`pytest.ini`** is two lines: `testpaths = tests`. Tests are run manually: `venv/bin/python -m pytest tests/ -v` (or per-file).

**`_smoke_test_tabs.py` is not pytest** — it's a manual `python _smoke_test_tabs.py` script that builds a `FakeApp` + `FakeHistory` + `FakeWorkflows` + a withdrawn Tk root, then **instantiates every tab in `tab_config.get_tabs_definition()`** to catch `pack/grid` TclErrors and other construction-time crashes (the same crash class as "cannot use geometry manager pack inside ... grid"). Per AGENTS.md §3: run after every tab change.

**Coverage gaps (be honest):**
- **Zero direct tests for `main_app.py` / `lite_app.py` / `app_*.py` mixins / `state.py` / `i18n.py` / `managers/` / `tab_config.py`** — the entire UI orchestration and threading is uncovered.
- **Zero tests for any of the 48 tab classes** — only one tab (`DemandTab._get_village_code`) is indirectly covered via `test_location_merge.py`.
- **Zero HTTP/network tests** — `services.py` license check, `app_automation.py` cloud sync, `location_sync.py`, `crash reporter` upload path are all untested.
- **The "happy path" of `start_automation_thread` is untested** — only the boot-counter, PII mask, version-parse, and merge logic are.

This matches the **AGENTS.md §6.5 / §7 pattern**: tests are pragmatic ("test the things that broke in past incidents" — boot counter, PII mask, locale build, workcode privacy) rather than aiming for coverage %. The smoke test is the "catch-all" for tab construction.

---

## 11. Major architectural risks / tightly coupled areas

### 🔴 High

1. **`NregaBotApp` is a god object** (1,131 lines + 4 mixins totaling 5,300+ lines). Every concern lives on it. Tabs reach in via `self.app.<attr>` or `self.app_state.<attr>` (backward-compat properties). The boundary between mixins is informal — `AutomationMixin` calls `self.app.show_toast` (UIMixin), `LicenseMixin` calls `self.app.stop_events` (AutomationMixin). If you wanted to instantiate a `NregaBotApp` in a unit test you'd need a near-full FakeApp (see `_smoke_test_tabs.py::FakeApp` — it's 110 lines for a reason).
2. **Single global `BrowserManager.driver`** — only one Selenium session at a time. `get_driver()` mutates `app_state.driver` and `app_state.active_browser` (L162-163). Two parallel automations of different kinds will fight over the same browser. WorkflowManager's macro queue serializes for this reason, but the contract is *implicit* — nothing prevents two direct `start_automation_thread` calls from racing.
3. **`AutomationMixin.wrapper()` is the single most important and least tested method** (204 lines, 1 inbound, 17 outbound calls). Every try/except in it is load-bearing. A refactor here is high-risk; the structured `_extract_error_context` and the screen-shot opt-in + the cloud-sync triple + the `finally:` cleanup all hang together.
4. **The `loader.py` ↔ `src/utils.py` ↔ `main_app.py` boot-counter contract** is split across **5 files** (`loader.py`, `lite_loader.py`, `services.py`, `main_app.py`, `lite_app.py`). `mark_clean_boot` is only called once the main window is "fully rendered" — but "fully rendered" is a fuzzy signal. A tab that crashes *after* `mark_clean_boot` runs will still leave a corrupt boot counter on next run. Tests cover the counter logic but not the "when to call mark_clean_boot" coordination.
5. **`tab_config._lazy_import` lock is held across the import** (the comment at L34-37 explicitly documents this). If any tab author adds a top-level `from src.tab_config import _lazy_import` and calls it during their own module-level import, the whole app deadlocks. The rule is enforced by documentation only.

### 🟡 Medium

6. **PII masking is regex-based and there are 2 implementations** (client `src/utils.py:251-286` + server `nrega-server/app/pii_mask.py`). The comment at L248-250 says "drift ho to dono ek saath update karo" — a regex change on one side will desync masking. No shared test enforces this.
7. **`AUTOMATION_DISPLAY_NAMES` is a flat dict** (`src/app/app_automation.py:34-77`, 44 entries). Adding a new tab requires editing **3 files**: `tab_config.py` (or `lite_tab_config.py`), this dict, and the new tab file. There's no schema validation that the three are in sync.
8. **`workflow_manager.py::_run_generic_task` does `time.sleep(1.5)`** (L158) and `self.app.after(3000, ...)` (L183) before triggering — magic numbers tuned empirically. If a user has a slow machine, automation can race the macro scheduler.
9. **`save_config` is not thread-safe** (`src/utils.py:713-724`): it does read-modify-write without a lock. If two background threads save config at the same time, one write wins. Low probability in practice but the data flow (settings_tab + automation background) does allow it.
10. **`HomeTab`/`SettingsTab` and other "always-loaded" tabs** are eagerly instantiated on first `show_frame("Home"/"Settings")` — but their imports still trigger the full module load (selenium, pandas, openpyxl). The 40-60% startup reduction is real but not as good as it could be if you mark some tabs as "lite-only" or "low-memory".
11. **`AUTH/Activation window` is a 2,530-line mixin** (`src/app/app_license.py`). It mixes license check, activation, settings, About-tab management, and the Google quick-login UI. If you need to refactor licensing, expect a large surface.

### 🟢 Low / acceptable

12. The `loader.py` and `lite_loader.py` are **near-duplicates** (~500 lines each, with subtle differences — the Lite version has fewer features). AGENTS.md doesn't call this out, but you have a *very* familiar maintenance pattern (one change in `loader.py` often needs a parallel change in `lite_loader.py`).
13. **48 tab files use `from src.tabs._imports import ...`** for shared heavy imports — that file is a "god import hub" and any circular import there cascades.
14. **No type checking in CI** — files are `# type: ignore`-free but there's no mypy/pyright config visible. Type hints are present on most public functions but not enforced.

---

## 12. Top 10 files/modules to understand first

> **Read order if you're new to the codebase.** Each entry tells you what you learn from it and what it connects to.

| # | File | Why it's first | You'll learn |
|---|---|---|---|
| 1 | **`main_app.py`** (1131 lines) | The single entry point. Every other file imports or is imported from here. The `__init__` is a guided tour of the whole architecture. | The startup sequence, manager wiring, mixin MRO, `_background_initialization`, `on_closing`. |
| 2 | **`loader.py`** (~700 lines) | Half the "how does this run on a user's machine" question. Without it you won't understand `resource_path` or the update flow. | The 2-stage delivery model, SHA-256 verification, `core_prev.zip` rollback, the **boot-counter** state machine. |
| 3 | **`src/state.py`** (~200 lines) | Every mixin reads/writes `self.app_state`; understanding the dataclass is the fastest way to understand the app's mental model. | All 60+ state fields, organized by owner (License / Automation / UI / Network / Lifecycle). |
| 4 | **`src/app/app_automation.py`** (1150 lines) | The **most important** file in the app — `start_automation_thread` is the only sanctioned entry point for any user-initiated work. The `wrapper()` is the cleanup/error harness for the entire app. | The threading contract, the structured error model (`_extract_error_context`), the cloud-sync triple, the `AUTOMATION_DISPLAY_NAMES` registry. |
| 5 | **`src/app/app_license.py`** (2530 lines) | The biggest mixin and arguably the most user-facing flow. License check, activation window, expiry alerts, Google quick-login, About-tab data, app-config (state registry) fetch. | The full auth flow, the `/api/validate` contract, the state registry's `update_state_registry` driver, the feature-flag pattern. |
| 6 | **`src/tab_config.py`** | Shows the lazy tab factory pattern. Read this once and you'll understand how 48 tabs coexist with sub-second startup. | `_lazy_import`, `_TAB_MODULE_IMPORT_LOCK`, the category structure, the icon/key metadata. |
| 7 | **`src/managers/browser_manager.py`** | The "external" boundary — talks to Chrome/Edge/Firefox via Selenium/CDP. The `_automation_tab_handle` pinning is a non-obvious gotcha you'll need to know. | Browser launch (detached vs managed), CDP marker JS, the per-thread browser choice cache, Firefox throttling overrides. |
| 8 | **`src/utils.py`** (~900 lines) | The "library" the whole app shares — `resource_path`, `get_data_path`, `get_logger`, `get_config`/`save_config`, **`save_license_dat`** (the only writer), `install_crash_reporter`, the **boot-counter**, PII masking, `translate_error`. | The choke-point discipline, the DPDP compliance, the rollback mechanism, the locale/version utility functions. |
| 9 | **`src/managers/workflow_manager.py`** | The Macro Manager — the *only* way to chain multiple automations across tabs. Central to power users. | The `queue_items` lifecycle, `_wait_for_automation_finish` polling, the macro `stop_events["macro"]`, the cross-tab panchayat setter. |
| 10 | **`src/tabs/base_tab.py`** (~2700 lines, but start at L1-160 then skim) | The parent class for all 44 automation tabs. Defines the contract every tab must honor (`_is_alive`, `safe_after`, `log_info`, `_extract_activity_panchayat`, `export_treeview_to_excel`, etc.). | The tab-author contract, the AfterTracker pattern, the activity-tracking fields, the Treeview → Excel/CSV/PNG export pipeline. |

**Honorable mentions** (read in week 2):
- `src/managers/services.py` — license check + update check, has the `_is_dev_mode()` subtlety.
- `src/i18n.py` — locale loader; small but central (357 call sites for `tr()`).
- `src/location_sync.py` — server-driven data pool; the "missing-only merge" invariant is non-obvious.
- `lite_app.py` — the Lite SKU; mostly parallel to main but with `LiteDropdown` monkey-patch and a slimmer `LicenseMixin`-only MRO.
- `AGENTS.md` — the human-written operating manual, has the gold rules (lazy imports, version bumping protocol, NAS rules, `save_license_dat` choke-point, etc.).

---

## Summary — what makes this architecture work

1. **Two-stage delivery** (`loader.py` + `core.zip` + `main_app.py`) — update via SHA-256-verified hotfix, rollback via boot-counter, single entry bundle.
2. **Mixin pattern on a single Tk root** — 5 concerns, 5 files, no controllers, no DI container, but the `app` proxy is a god object.
3. **Lazy tab loading with thread-safe factory** — 48 tabs with sub-second startup. Lock discipline is documented and tested.
4. **Single-sanctioned automation entry** — `start_automation_thread` is the only way to run user work; `wrapper()`'s `finally:` guarantees cleanup and triple cloud-sync. The structured error model is the data backend for the admin's "Error Logs" page.
5. **Centralized utils with choke-points** — `save_license_dat`, `get_data_path`, `get_logger`, `install_crash_reporter` are all one-writer, never-raise, PII-masked, version-agnostic.
6. **Server-driven config** — state registry, app-config heartbeat, license validation, cloud sync all flow through `LICENSE_SERVER_URL`. Desktop stays simple; complex state lives in `nrega-server/`.
7. **DPDP compliance at the formatter** — Aadhaar/mobile/IFSC are masked in the logger *and* in the network payload *and* server-side (defense in depth).
8. **Pragmatic test coverage** — `test_utils_pure`, `test_update_rollback`, `test_location_merge`, plus the `_smoke_test_tabs` catch-all. No mocking-heavy test pyramid; tests are the things-that-broke test set.

**The biggest single thing to internalize**: every important constraint in this codebase is **enforced at a single chokepoint** (save_license_dat, get_data_path, get_logger, _lazy_import, start_automation_thread, install_crash_reporter, _PiiMaskingFormatter, get_state_portal_url). Find the chokepoint, and the constraint is documented in its docstring + AGENTS.md. That's the operating principle — read those chokepoints first, and the rest of the code reads like a well-indexed book.

---

**Generated from:** NregaBot knowledge graph (2,509 nodes, 15,228 edges, fresh full index, 0 parse errors). All file paths and line numbers verified against the current source on disk.