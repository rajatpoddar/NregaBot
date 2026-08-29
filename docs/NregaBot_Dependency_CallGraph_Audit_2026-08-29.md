I have the complete picture. The marker-keeper is a **second daemon thread** spawned per automation — important for thread analysis. Time to deliver the report.

---

# 🔍 NregaBot — Dependency & Call-Graph Analysis

> **Scope:** Four focused subsystems, with caller/callee graphs derived from the live knowledge graph (2,509 nodes, 15,228 edges). All file paths and line numbers verified against the source on disk. **No files were modified.**

> **Conventions used below:**
> - `qn = qualified_name` (e.g. `NregaBot.src.app.app_automation.AutomationMixin.start_automation_thread`)
> - `(in=N, out=M)` after a symbol means N callers, M callees in the graph
> - `[tk]` = Tk main thread, `[Wn]` = automation worker (daemon) thread, `[Mn]` = marker-keeper daemon thread, `[Mn+]` = marker-keeper spawned by multiple `start_automation_thread` calls, `[σn]` = arbitrary tab code, `[β]` = background (e.g. `threading.Thread(daemon=True)` from any non-Tk place)

---

## 1. NregaBotApp / mixin coupling

### Important classes/functions

| Symbol | qn | in/out | Thread | Owned by |
|---|---|---|---|---|
| `NregaBotApp` | `NregaBot.main_app.NregaBotApp` | 1/4 | [tk] | `main_app.py:97` |
| `NregaBotLiteApp` | `NregaBot.lite_app.NregaBotLiteApp` | 0/8 | [tk] | `lite_app.py:104` |
| `LicenseMixin` | `NregaBot.src.app.app_license.LicenseMixin` | 2/0 | [tk] | `src/app/app_license.py:58` |
| `NavMixin` | `NregaBot.src.app.app_navigation.NavMixin` | 1/0 | [tk] | `src/app/app_navigation.py:24` |
| `AutomationMixin` | `NregaBot.src.app.app_automation.AutomationMixin` | 1/0 | mixed | `src/app/app_automation.py:140` |
| `UIMixin` | `NregaBot.src.app.app_ui.UIMixin` | 1/0 | [tk] | `src/app/app_ui.py:26` |
| `AppState` (dataclass) | `NregaBot.src.state.AppState` | (field) | (shared) | `src/state.py:15` |
| `FakeApp` (test) | `NregaBot._smoke_test_tabs.FakeApp` | 0/0 | [tk] | `_smoke_test_tabs.py:53` |

MRO for `NregaBotApp` is: `ctk.CTk → LicenseMixin → NavMixin → AutomationMixin → UIMixin` (`main_app.py:97`).
`NregaBotLiteApp` uses only `LicenseMixin` (`lite_app.py:54`).

### Callers and callees

```
NregaBotApp (main_app.py:97)
  ├─ constructed by:  python main_app.py (top-level, implicit)
  ├─ delegated to:
  │     LicenseMixin.   perform_license_check_flow, _preload_and_update_about_tab,
  │                     show_activation_window, _ping_server_in_background
  │     NavMixin.       _create_nav_buttons, show_frame, _create_content_frames,
  │                     _on_nav_search_change, _shortcut_start/_retry/_stop
  │     AutomationMixin.start_automation_thread, on_automation_finished,
  │                     _emergency_stop_all, get_driver, launch_*_detached
  │     UIMixin.        _create_header, _create_footer, set_status, play_sound,
  │                     _cycle_theme, _gc_collection_loop
  └─ reaches into (direct attribute access):
        self.browser_manager, self.services, self.history_manager,
        self.sound_manager, self.workflows, self.icon_images, self.app_state
```

**Inheritance-only vs. self-proxy:** Every mixin method takes `self` and the mixin class never declares `__init__`. MRO means `self` is a `NregaBotApp` instance and **all mixins share the same `__dict__`** — the `host class` comment at `app_automation.py:143-153` is the *only* contract document for which attributes mixins depend on. The list is informal:

```
browser_manager, driver, active_browser, stop_events, history_manager,
automation_threads, active_automations, minimize_var, services
```

### Shared mutable state (the actual coupling surface)

`NregaBotApp.__init__` (`main_app.py:97-174`) constructs in this order — every attribute below is reachable by every mixin:

| Attribute | Type | Owner (mixin) | Mutable from | Documented in |
|---|---|---|---|---|
| `self.app_state` | `AppState` (dataclass) | NregaBotApp | all mixins + workers | `src/state.py:15-200` |
| `self.app_state.driver` | `Any` (selenium) | AutomationMixin + BrowserManager | both directions | `app_automation.py:162-163` sets it; `browser_manager.py:208-209` sets it |
| `self.app_state.active_browser` | `Optional[str]` | AutomationMixin + BrowserManager | both | same lines |
| `self.app_state.automation_threads` | `Dict[str, Thread]` | AutomationMixin only | set in `start_automation_thread` | `state.py:70-71` |
| `self.app_state.active_automations` | `Set[str]` | AutomationMixin + WorkflowManager | concurrent | `app_automation.py:184`, `workflow_manager.py:42,56` |
| `self.app_state.stop_events` | `Dict[str, Event]` | AutomationMixin + WorkflowManager | concurrent | `app_automation.py:185`, `workflow_manager.py:57` |
| `self.app_state.automation_progress` | `Dict[str, float]` | AutomationMixin only | worker writes | `state.py:76-79` |
| `self.history_manager` | `HistoryManager` | AutomationMixin + LicenseMixin + tabs | many | `tabs/history_manager.py` |
| `self.workflows` | `WorkflowManager` | AutomationMixin calls into it; tabs call into AutomationMixin | concurrent | `managers/workflow_manager.py:9` |
| `self.icon_images` | `LazyIconManager` | NavMixin + UIMixin | only at init | `managers/icon_manager.py` |
| `self.tab_instances` | `Dict[str, Frame]` | NavMixin writes; WorkflowManager reads | main thread only | `state.py:110-111` |
| `self.license_info` | `Dict` | LicenseMixin writes; many tabs read | mixed | `app_license.py` |

The dataclass comment at `state.py:22-25` says **UI widget refs are intentionally NOT in `AppState`** — they live as direct attrs on `NregaBotApp` because they're "tightly coupled to the GUI lifecycle." This is a deliberate escape hatch, not a slip.

### Cross-module dependencies (the import graph)

```
main_app.py
  ├─ src.config
  ├─ src.ui_components        (CollapsibleFrame, SkeletonLoader, ToastNotification, …)
  ├─ src.managers.browser_manager
  ├─ src.managers.services
  ├─ src.tab_config           (get_tabs_definition)
  ├─ src.managers.icon_manager
  ├─ src.managers.sound_manager
  ├─ src.app.app_license       (LicenseMixin)
  ├─ src.app.app_navigation    (NavMixin)
  ├─ src.app.app_automation    (AutomationMixin)
  ├─ src.app.app_ui            (UIMixin)
  ├─ src.managers.workflow_manager
  ├─ src.location_data         (STATE_DISTRICT_MAP)
  ├─ src.tabs.history_manager
  ├─ src.tabs.macro_manager_tab  ← EAGER import (only place a tab is imported at top level)
  └─ src.state                 (AppState)
```

The **single eager tab import** is `MacroManagerTab` (`main_app.py:60`). Every other tab is lazy (per `_lazy_import` in `tab_config.py:23-48`). The graph evidence: `MacroManagerTab` is the only class inside `src/tabs/` imported at module load time in `main_app.py`.

### Thread boundaries

| Mixin | Hot path is | Concurrency hazard |
|---|---|---|
| `LicenseMixin` | [tk] | none — all background calls use `self.after(0, ...)` |
| `NavMixin` | [tk] | none — `show_frame` is called from main thread only |
| `AutomationMixin` | **mixed** | `start_automation_thread` is called from [tk] but spawns [Wn] for `wrapper()` and [Mn] for the marker-keeper. See §2. |
| `UIMixin` | [tk] | none |

### Implicit contracts (convention only)

1. **Mixins never override each other's methods.** There is no `__init_subclass__` guard, no `@final` decorator. A new mixin that defines `set_status` would silently break `UIMixin`.
2. **All host-class attributes documented at `app_automation.py:143-153` are assumed to exist when `start_automation_thread` runs.** If `NregaBotApp.__init__` is bypassed (e.g. a test instantiates `AutomationMixin()` directly), `AttributeError` is the first symptom.
3. **Mixins communicate via `self.app_state.<attr>` reads/writes**, not via method calls. There is no observer pattern — the only "subscribers" are `show_frame` and `set_status` callbacks wired in by the host.
4. **`_automation_key_to_tab_name` reverse lookup** (`app_automation.py`, in/out: 2/2) is the only place AutomationMixin learns which tab owns an `automation_key`. Tabs register their `automation_key` in their constructor (`BaseAutomationTab.__init__` at `base_tab.py:46-49`).

### Potential race conditions

| # | Race | Where | Severity | Likelihood |
|---|---|---|---|---|
| 1 | `self.history_manager.increment_usage(key)` (called from [tk] in `start_automation_thread` line 182) and the worker thread reading/writing the same SQLite connection | `app_automation.py:182` | medium | low — `_get_connection` is serialized internally |
| 2 | `self.app_state.active_automations.add(key)` (line 184) and the workflow polling `key in self.app.active_automations` (`workflow_manager.py:42,56`) | cross-mixin | low | low — `set` membership is atomic in CPython |
| 3 | `self.app_state.automation_progress[key]` — written by worker, read by `UIMixin._update_running_automation_indicator` from [tk] | cross-thread | low | low — assignment of immutable float is atomic, but the dict slot itself is GIL-protected only |
| 4 | The **docstring at `app_automation.py:294-296`** explicitly says the closure is "race-condition-free because each thread's closure captures the correct tab instance — unlike a shared dict where a new tab could overwrite the old driver reference." This is the one race the author was conscious of and solved. |

### Safe refactoring boundaries

| Boundary | Why safe |
|---|---|
| `UIMixin` ↔ other mixins | UIMixin only exposes its methods; it doesn't read any `app_state` field that other mixins write. The only cross-talk is `set_status` (called by all mixins, owned by UIMixin). |
| `LicenseMixin` ↔ `AutomationMixin` | `LicenseMixin` reads `app_state.license_info` (set inside LicenseMixin itself, see `app_license.py`). No cross-write. |
| `NavMixin` ↔ `AutomationMixin` | The only edge is `NavMixin.show_frame` is called from `AutomationMixin.on_automation_finished` (depth-3 trace evidence: `app_navigation.NavMixin.show_frame: 3` inbound from `on_automation_finished`). `show_frame` is [tk]-safe. |
| `FakeApp` (`_smoke_test_tabs.py:53`) | Only used for the smoke test, never imported by production code. |

### Existing tests that protect this behavior

| Test | Protects |
|---|---|
| `_smoke_test_tabs.py` | All 48 tab classes construct successfully (catches `pack/grid` TclErrors and missing-attr errors at `__init__` time). Uses `FakeApp` to bypass the full `NregaBotApp`. |
| `tests/test_utils_pure.py::TestParseVersion` | Version tuple compare — but unrelated to mixin behavior. |
| `tests/test_update_rollback.py` | Boot-counter / `core_prev.zip` rollback. Unrelated to mixin behavior. |
| `tests/test_location_merge.py` | Location-pool merge invariant. Unrelated to mixin behavior. |

**Coverage gap:** zero direct tests for `NregaBotApp.__init__`, `AppState`, any mixin, or the `self.app_state.driver` double-write. The smoke test is the only guard.

---

## 2. AutomationMixin.start_automation_thread() and wrapper()

### Important symbols

| Symbol | qn | in/out | Where |
|---|---|---|---|
| `start_automation_thread` | `…AutomationMixin.start_automation_thread` | 46/17 | `app_automation.py:175-379` |
| Inner closure `wrapper` | (closure, not a graph node) | 0/0 (inlined) | `app_automation.py:216-307` |
| Inner closure `_marker_keeper` | (closure, not a graph node) | 0/0 (inlined) | `app_automation.py:318-379` |
| `on_automation_finished` | `…AutomationMixin.on_automation_finished` | 1/20 | `app_automation.py:467-557` |
| `_emergency_stop_all` | `…AutomationMixin._emergency_stop_all` | 1/17 | `app_automation.py:729-779` |
| `_extract_error_context` | `…app_automation._extract_error_context` (function) | 0/0 | `app_automation.py:86-137` |
| `AUTOMATION_DISPLAY_NAMES` | `…app_automation.AUTOMATION_DISPLAY_NAMES` | 0/0 | `app_automation.py:34-77` |
| `get_driver` (mixin) | `…AutomationMixin.get_driver` | 2/3 | `app_automation.py:159-164` |
| `_automation_key_to_tab_name` | `…AutomationMixin._automation_key_to_tab_name` | 2/2 | `app_automation.py` |

### Callers (inbound, 46 total)

The graph's `start_automation_thread` caller list is large because every tab's `start_automation` method is a 1-hop caller (the 48 tab → `start_automation` → `start_automation_thread` chain is in the depth-3 path).

**Direct callers (in=1, hop 1):**
- `WorkflowManager._run_generic_task` (`workflow_manager.py:183`) — `self.app.after(3000, lambda: tab.start_automation())`
- `WorkflowManager.process_global_queue` (`workflow_manager.py:236-237` and `:319-325`) — for `'Add to Queue'` and generic macro items
- `NavMixin._shortcut_start` — global Ctrl+Enter shortcut
- `NavMixin._shortcut_retry` — global Ctrl+R
- `NavMixin._create_nav_buttons` (depth 3) — wires button commands
- `AutomationMixin._maybe_auto_start_queue` — auto-restart queued items
- `MacroManagerTab.start_macro` — fires the macro itself
- `BaseAutomationTab.retry_failed_automation`, `BaseAutomationTab.retry_logic_handler` (depth 3) — retry path
- `WorkAllocationTab.run_automation_from_demand`
- `MrTrackingTab.start_automation`, `IssuedMrReportTab.start_abps_automation`, `FtoGenerationTab.start_delete_automation` (all depth 2)

**Transitive callers (in=46, hops 2-3):** the 40+ tab `start_automation` methods (e.g. `MrFillTab.start_automation`, `DemandTab.start_automation`, `MusterrollGenTab.start_automation`).

### Callees (outbound, 17)

From the graph (depth ≤ 3):
- **self.app_state writes:** `app_state.active_automations.add`, `app_state.stop_events[key] = …`, `app_state.automation_progress.pop` (lines 184-187).
- **Other mixin calls:** `self.prevent_sleep`, `self._minimize_active_browser`, `self._update_emergency_stop_btn`, `self._update_running_automation_indicator`, `self._refresh_all_tab_buttons`, `self._open_running_tab`, `self._clear_running_chips` (all the 17 outbound from `start_automation_thread`).
- **UIMixin calls:** `self.play_sound`, `self.set_status`, `self.show_toast` (depth 1 — called from `start_automation_thread` line 177/181 and from the `wrapper` closure).
- **Manager calls:** `self.history_manager.increment_usage`, `self.history_manager.log_automation_start`, `self.browser_manager.clear_thread_choice` (called twice: line 224 inside `wrapper`, line 278 in `finally`).
- **Tab methods via `target.__self__`:** `_refresh_activity_data` (line 205) is called from [tk] **before** spawning the worker — relies on the bound method's `__self__` extraction at line 198.

### The wrapper closure — full anatomy (`app_automation.py:216-307`)

```
def wrapper():                                   [Wn]  (worker thread, daemon)
    [line 224] self.browser_manager.clear_thread_choice()    (clears _thread_browser_choice)
    [line 228] target(*args)                                  ← THE automation runs here
    except Exception as e:
        [line 233] _extract_error_context(e)                 → (error_type, error_msg, error_source, error_traceback)
        [line 240-254] opt-in screenshot (save_error_screenshots)
        [line 257-273] browser-closed detector + logger.error
    finally:                                                   ← GUARANTEED to run
        [line 277-280] self.browser_manager.clear_thread_choice()  (clears for next run)
        [line 282-303] compute duration; quit tab_instance.driver if any; tab_instance.driver = None
        [line 304-307] self.after(0, self.on_automation_finished, ...)   ← SCHEDULE on [tk]

t = threading.Thread(target=wrapper, daemon=True)
self.app_state.automation_threads[key] = t
t.start()                                                      [Wn] alive

def _marker_keeper(worker_thread):                [Mn]  (second daemon thread, started at line 379)
    while worker_thread.is_alive() and key in self.app_state.active_automations:
        if marker_session is None:
            marker_session, owns_session = self.browser_manager.connect_driver_no_dialog()
        if marker_session is not None:
            [anchored once]  marker_session.switch_to.window(target)   ← STEALS FOCUS once
            [every tick]     self.browser_manager.apply_automation_marker(marker_session)
            [every tick]     self.browser_manager.keep_tab_active(marker_session)  ← CDP override
    if owns_session and marker_session is not None:
        try: marker_session.quit()
        except: pass
threading.Thread(target=_marker_keeper, args=(t,), daemon=True).start()
```

**Three threads per `start_automation_thread` call:**
1. The caller (typically [tk]).
2. [Wn] — the `wrapper` thread running the tab's `target(*args)`.
3. [Mn] — the `_marker_keeper` thread that re-paints the red-dot + forces tab active every tick.

### Shared mutable state touched by `start_automation_thread` (cross-class)

| Field | Written by | Read by | Thread safety |
|---|---|---|---|
| `app_state.active_automations` (Set[str]) | `start_automation_thread:184` (add), `_emergency_stop_all:770` (clear), `on_automation_finished` (remove) | `_wait_for_automation_finish` (workflow), `_marker_keeper` (while-cond), `_update_running_automation_indicator` | CPython GIL on set ops, but iteration is racy if mutated concurrently |
| `app_state.stop_events[key]` (Event) | `start_automation_thread:185` (new Event), `_emergency_stop_all:739` (.set()) | `wrapper` via target code (must check), `_wait_for_automation_finish:57` | `Event` is thread-safe by design |
| `app_state.automation_threads[key]` (Thread) | `start_automation_thread:310` (assign) | `start_automation_thread:176` (`is_alive()` check) | assignment is atomic; the *check-then-act* on line 176 is a TOCTOU race (see below) |
| `app_state.automation_progress` (Dict[str,float]) | wrapper (worker writes) | `_update_running_automation_indicator` ([tk] reads) | dict slot assignment is GIL-protected |
| `app_state.driver`, `app_state.active_browser` | `get_driver:162-163` ([tk]), `BrowserManager.launch_firefox_managed:208-209` ([tk]), `_emergency_stop_all:751-752` ([tk]), `wrapper:300` ([Wn] sets `tab_instance.driver = None`) | everywhere | **THIS IS A RACE** — see below |
| `browser_manager._thread_browser_choice` (Dict[int,str]) | `wrapper:224` ([Wn]), `wrapper:278` ([Wn]), `BrowserManager.get_driver:502` ([Wn] or [tk] depending on caller) | `BrowserManager.get_driver:502` | `_thread_browser_choice.pop` and `.get` are dict ops — atomic |
| `browser_manager._automation_tab_handle` (Optional[str]) | `BrowserManager.resolve_automation_tab:366/371` (CDP session, can be [Wn] or [tk]) | `BrowserManager.resolve_automation_tab:352` (same) | only one browser session at a time, so serial in practice |
| `browser_manager.driver` (Any) | `launch_chrome_detached`, `launch_firefox_managed:208`, `_prepare_driver_tab:415` ([Wn] or [tk]) | many readers | **RACE** — see below |
| `tab_instance.driver` (per-tab) | tab's `run_automation_logic` ([Wn]), `wrapper:300` ([Wn]) | tab's code | per-tab field, no cross-tab concern |
| `tab_instance.activity_start_time` | `start_automation_thread:202` ([tk]) | `wrapper:286-287` ([Wn] reads) | **WRITER BEFORE THREAD START** — no race |
| `tab_instance.activity_panchayat/_village/_details` | `start_automation_thread:207-208` ([tk] reads widget), `wrapper:289-290` ([Wn] calls `_refresh_activity_data`) | `on_automation_finished:495-497` ([tk]) | **TWO WRITERS to the same per-tab fields** — see below |
| `self.history_manager.log_automation_start(...)` (SQLite) | `start_automation_thread:209` ([tk]) | later finish | `_get_connection` is serialized internally |

### Cross-module dependencies

```
start_automation_thread
  → AutomationMixin._automation_key_to_tab_name (app_automation.py)
  → AutomationMixin.prevent_sleep
       → ServiceManager.prevent_sleep (services.py)  [creates subprocess]
  → AutomationMixin._minimize_active_browser
       → subprocess / osascript / Win32 EnumWindows
  → AutomationMixin._update_emergency_stop_btn, _update_running_automation_indicator
  → NavMixin.show_frame (the "open the running tab" jump)
  → BaseAutomationTab._refresh_activity_data
  → BaseAutomationTab._extract_activity_panchayat, _extract_activity_village
  → HistoryManager.increment_usage, log_automation_start
  → BrowserManager.clear_thread_choice
  → tkinter.messagebox (the "Busy" / "Browser Closed" dialogs)
  → SoundManager.play (start sound, error sound)
  → src.utils.get_config  (save_error_screenshots flag)

on_automation_finished (called via self.after(0, ...) from [Wn])
  → HistoryManager.log_automation_finish
  → HistoryManager.sync_activity_log_to_server
  → HistoryManager.sync_usage_stats_to_server
  → _sync_automation_results_to_cloud (cloud-reports dedupe cache)
  → BaseAutomationTab.show_automation_notification (per-tab hook)
  → NavMixin.show_frame (jump to running tab)
  → UIMixin.set_status, play_sound
```

### Thread boundaries

- **Caller of `start_automation_thread`**: always [tk] (every UI button, every shortcut, every macro). 1 inbound from [β] in `WorkflowManager._run_generic_task` which itself runs on a thread, but `_run_generic_task` only calls `self.app.after(3000, lambda: tab.start_automation())` — the actual call hops back to [tk].
- **Inside `start_automation_thread`**: [tk] executes lines 175-200 (state setup, `_refresh_activity_data` is called HERE on [tk], line 205), then spawns [Wn] for `wrapper`.
- **`wrapper` body**: [Wn] for `target(*args)` (line 228) and the screenshot + error reporting (lines 240-273). The `finally:` cleanup (lines 274-307) is **also [Wn]**. Critically: line 300 `tab_instance.driver.quit()` runs on [Wn].
- **`on_automation_finished`**: scheduled via `self.after(0, ...)` (line 304) — runs on [tk]. The actual method body (lines 467-557) calls `history_manager.log_automation_finish` (SQLite from [tk]), `tab_instance.show_automation_notification` (UI from [tk]), and three cloud-sync methods (each in its own `try` block; they may be background-fired internally).
- **`_marker_keeper`**: [Mn], second daemon, started at line 379 right after `t.start()`. Holds a *separate* CDP session for Chrome/Edge (via `connect_driver_no_dialog`), so it never touches the worker thread's driver.

### Implicit contracts (convention only)

1. **The `target` argument is a bound method whose `__self__` is the tab instance.** Line 198 does `getattr(target, '__self__', None)` — if a caller passes a lambda or a plain function, the entire `tab_instance.*` block (lines 200-214, 283-307) is silently skipped, including the activity log, the error log, the screenshot, and the `on_automation_finished` arguments. The wrapper still runs but logs nothing.
2. **`tab_instance.driver` is the per-tab Selenium driver**, *not* the shared `browser_manager.driver`. The contract documented at `app_automation.py:292-303` (and re-stated in the docstring) is: "each thread's closure captures the correct tab instance — unlike a shared dict where a new tab could overwrite the old driver reference." The `wrapper` is the *only* place this is enforced.
3. **`target()` is expected to honor `app_state.stop_events[key].is_set()`** (cooperative cancellation). If a tab author forgets to check, `_emergency_stop_all` still wins (it `driver.quit()`s and sets all events) but the worker's `target` may keep trying Selenium calls against a dead driver — handled by the browser-closed detector at lines 257-273.
4. **`stop_events.pop(key)`** at `app_automation.py:285-291` is *not* in this method (it lives in `on_automation_finished`). The wrapper itself never touches `stop_events`.
5. **`_marker_keeper` runs on a separate session for Chrome/Edge** (`connect_driver_no_dialog` returns `(driver, owns_session=True)`), and a *shared* session for Firefox (`owns_session=False`, line 430-432). It will NOT `quit()` the shared Firefox driver (the worker still needs it). This is the only place the codebase distinguishes "owns vs shares" the driver.

### Potential race conditions

| # | Race | Where | Severity | Mitigation |
|---|---|---|---|---|
| R1 | `start_automation_thread` re-entry check (line 176): `if self.app_state.automation_threads.get(key) and self.app_state.automation_threads[key].is_alive(): return`. Between `get` and `is_alive()`, the previous thread could die. Two parallel calls would both pass and both spawn workers for the same `key`. | `app_automation.py:176` | medium | None — TOCTOU. The first `target(*args)` would race the second on the same shared `BrowserManager.driver`. |
| R2 | `wrapper` writes `tab_instance.driver = None` (line 303) and `tab_instance.driver.quit()` (line 300) **on [Wn]**. Meanwhile `on_automation_finished` runs on [tk] and may call `tab.show_automation_notification` which (in some tabs like `pending_bills_tab`) reads `tab.driver`. | `app_automation.py:300-303` vs `467-557` | medium | `_is_alive()` (52 callers) is a guard but does NOT re-fetch `driver`. Some tabs can read a None `driver` and crash; comment in code says "tab is destroyed" path. |
| R3 | `self.app_state.driver` is written by `get_driver:162-163` ([tk]) and by `wrapper:300` via `tab_instance.driver = None` ([Wn]). The `app_state.driver` field is **read by `_emergency_stop_all:743` ([tk])** to decide whether to `driver.quit()`. If [Wn] is in the middle of `quit()` when [tk] checks, the `try/except` swallows the error. | `app_automation.py:162-163, 300, 743-754` | low | try/except around the quit; `_emergency_stop_all` also clears the field on line 751 |
| R4 | `_marker_keeper` (line 318-379) holds a *separate* Chrome/Edge CDP session via `connect_driver_no_dialog`. Two parallel automations on Chrome would each open a *second* CDP connection to the same Chrome process on port 9222 — Chrome only allows one CDP control client at a time. The second one will throw on `execute_cdp_cmd`. | `app_automation.py:326` + `browser_manager.py:418-433` | medium | No mitigation. Comment at `browser_manager.py:63-66` says "pinned on the first run" — but `_automation_tab_handle` is for *which tab*, not *which session*. |
| R5 | The `_thread_browser_choice` dict (line 60 of browser_manager) is keyed by `threading.get_ident()`. Daemon threads are short-lived; if a worker exits without `clear_thread_choice` being called, the choice stays cached. The `finally:` block (line 277) does call it — but a worker killed via `sys.exit` or hard crash wouldn't reach `finally`. | `app_automation.py:277-280` | low | bounded by `_CANCELLED_CHOICE` sentinel |
| R6 | `app_state.automation_progress[key] = float` (worker writes) and `_update_running_automation_indicator` ([tk] reads, depth-2 in graph). CPython dict slot assignment is GIL-protected, so torn writes are impossible for `float` — but the dict `__setitem__` itself is atomic at the GIL level. **Read of a stale value is fine; the design is event-driven by `after(0, ...)`.** | `state.py:76-79` | low | Acceptable by design |
| R7 | `wrapper` (line 289) calls `tab_instance._refresh_activity_data()` *after* `target(*args)` returns but *before* `on_automation_finished`. The tab's `_refresh_activity_data` typically reads its own widgets via `self.after(0, ...)` — but if the tab author made it a direct read, this runs on [Wn] and touches Tk. | `app_automation.py:289` | low | Convention; no enforcement |
| R8 | `on_automation_finished` (line 467) is called via `self.after(0, ...)` from the worker's `finally:`. If the app is shutting down, `after(0, ...)` may not fire — the finish is lost. | `app_automation.py:304-307` + `main_app.py:553-600` (`on_closing`) | low | `install_crash_reporter` catches uncaught exceptions; the activity log is best-effort |

### Safe refactoring boundaries

| Boundary | Why safe |
|---|---|
| `wrapper` closure (lines 216-307) | No external code references the inner function. It is a local closure. All callers go through `start_automation_thread`. Refactor to a module-level `def _run_automation_wrapper(app, key, target, args)` is safe as long as the closure's three captured variables (`self`, `key`, `target`) are explicit. |
| `AUTOMATION_DISPLAY_NAMES` (lines 34-77) | A plain module-level dict, used only by `_automation_display_name` (line 80). Imports of this symbol outside the file: `lite_app.py:64` imports it for the Lite footer. Adding a new key here is safe and doesn't require any other change. |
| `_extract_error_context` (lines 86-137) | A pure function, only called from `wrapper` (line 233). No external callers. Refactor to a separate module is trivial. |
| The screenshot branch (lines 240-254) | Pure opt-in, behind `save_error_screenshots` config. Can be deleted without affecting other behavior. |

### Existing tests that protect this behavior

| Test | Protects |
|---|---|
| `_smoke_test_tabs.py::FakeApp.start_automation_thread` (`_smoke_test_tabs.py:81`) | Just a `pass` stub. **Does not exercise the real `wrapper` body or any thread boundaries.** |
| `_smoke_test_tabs.py` overall | Only catches `__init__`-time errors, not runtime races. |
| `tests/test_update_rollback.py` | Boot counter (unrelated). |
| `tests/test_utils_pure.py` | PII mask (the wrapper's `error_msg` flows through it via `_extract_error_context` line 106 — *transitively* tested). |
| `tests/test_location_merge.py` | Unrelated. |

**Critical coverage gap:** the `wrapper` body (90 lines, the most important method in the app) has **zero direct tests**. The most-load-bearing invariants — `finally:` cleanup, `_extract_error_context` caps, browser-closed detection, `tab_instance.driver` lifecycle, the `on_automation_finished` handoff — are all unprotected by automated tests.

---

## 3. BrowserManager.driver lifecycle and concurrent automation risks

### Important symbols

| Symbol | qn | in/out | Where |
|---|---|---|---|
| `BrowserManager` (class) | `NregaBot.src.managers.browser_manager.BrowserManager` | (cl) | `browser_manager.py:51` |
| `__init__` | `…BrowserManager.__init__` | 0/0 | `browser_manager.py:52-70` |
| `get_driver` | `…BrowserManager.get_driver` | 47/8 | `browser_manager.py:457-565` |
| `launch_chrome_detached` | `…BrowserManager.launch_chrome_detached` | 2/6 | `browser_manager.py:72-123` |
| `launch_firefox_managed` | `…BrowserManager.launch_firefox_managed` | 0/6 | `browser_manager.py:165-215` |
| `launch_old_firefox` | `…BrowserManager.launch_old_firefox` | (low) | `browser_manager.py:217-251` |
| `_connect_external` | `…BrowserManager._connect_external` | 1/1 | `browser_manager.py:253-279` |
| `apply_automation_marker` | `…BrowserManager.apply_automation_marker` | 2/0 | `browser_manager.py:281-287` |
| `keep_tab_active` | `…BrowserManager.keep_tab_active` | 2/0 | `browser_manager.py:289-319` |
| `_inject_persistent_marker` | `…BrowserManager._inject_persistent_marker` | 2/0 | `browser_manager.py:321-337` |
| `resolve_automation_tab` | `…BrowserManager.resolve_automation_tab` | 2/0 | `browser_manager.py:339-374` |
| `_prepare_driver_tab` | `…BrowserManager._prepare_driver_tab` | 1/0 | `browser_manager.py:376-416` |
| `connect_driver_no_dialog` | `…BrowserManager.connect_driver_no_dialog` | 1/0 | `browser_manager.py:418-433` |
| `_create_driver_service` | `…BrowserManager._create_driver_service` | 2/0 | `browser_manager.py:435-455` |
| `clear_thread_choice` | `…BrowserManager.clear_thread_choice` | 1/1 | `browser_manager.py:671-677` |
| `AUTOMATION_MARKER_JS` (module const) | `…browser_manager.AUTOMATION_MARKER_JS` | 0/0 | `browser_manager.py:27-45` |

### Callers (inbound, 47 for `get_driver`)

`get_driver` is the **single hottest Selenium entry point** in the app — 47 distinct callers in the graph. The call sites break down:

- **44 tab `run_automation_logic` / `run_*_automation` methods** (one per automation tab). E.g. `MrFillTab.run_automation_logic:1`, `DemandTab._process_demand:1`, `MusterrollGenTab.run_automation_logic:1`, `EmbVerifyTab.run_automation_logic:1`.
- **`OnboardingGuide._check_login_thread`** (depth 1, [β] thread).
- **2 Lite-app shims** (`NregaBotLiteApp.get_driver:0/3`, which delegates to `self.browser_manager.get_driver`).

The *call* to `get_driver` is a 1-hop. Looking at where the *return value* (the Selenium driver) goes: each tab stores it in a per-tab `self.driver` (line 244 of `app_automation.py` shows `getattr(_inst, 'driver', None)` — confirming the per-tab contract) and uses it for the lifetime of its `target(*args)` call.

### Callees (outbound from `get_driver`, 8)

```
get_driver (browser_manager.py:457-565)
  ├─ self.driver / self.driver.window_handles  (own state)
  ├─ socket.create_connection(("127.0.0.1", 9222/9223), timeout=0.2)  ← CDP port probe
  ├─ threading.get_ident()                     ← thread-scoped cache key
  ├─ self._thread_browser_choice.get(...)      ← per-thread cache
  ├─ self.preferred_browser                    ← session-wide preferred
  ├─ self._ask_browser_selection               ← if multiple browsers, modal dialog
  └─ self._connect_external(browser, port)     ← actual Selenium WebDriver(...) construction
        └─ self._create_driver_service         ← webdriver_manager or Selenium Manager
```

The function is **108 lines** (457-565) and the graph captures only the *direct* callees. The dialog (`_ask_browser_selection`, ~150 lines) is a modal `CTkToplevel` that calls `self.app.wait_window(dialog)` (line 668) — a **blocking call** that **must be on [tk]**.

### Driver lifecycle — state machine

```
                    ┌────────────────────────────────────────┐
                    │ BrowserManager (singleton per app)     │
                    │   self.driver = None                   │
                    │   self.active_browser = None           │
                    │   self._automation_tab_handle = None  │
                    │   self._thread_browser_choice = {}     │
                    │   self.preferred_browser = None        │
                    └────────────────────────────────────────┘
                                    │
        launch_chrome_detached() ───┤  ← [tk] (UIMixin/button)
        launch_edge_detached()   ───┤  ← [tk]
        launch_firefox_managed() ───┤  ← [tk]
                                    ▼
                    self.driver = WebDriver(...)
                    self.active_browser = "chrome"|"edge"|"firefox"
                    self.app.driver = self.driver         ← ALSO written to NregaBotApp
                    self.app.active_browser = "..."
                                    │
        get_driver()  ──────────────┤  ← [Wn] (per-tab run_automation_logic)
                                    ▼
                    if self.driver: probe window_handles
                    probe 9222 (chrome), 9223 (edge)
                    if multiple browsers available:
                        show modal dialog (BLOCKING [tk] call)
                    return self._connect_external(...)
                    self.app_state.driver = self.driver    ← written to AppState
                    self.app_state.active_browser = ...
                                    │
        _prepare_driver_tab()  ─────┤  ← internal
                                    ▼
                    resolve_automation_tab() → pinned handle
                    driver.switch_to.window(target)         ← STEALS FOCUS
                    keep_tab_active(driver)                 ← CDP Page.setWebLifecycleState
                    _inject_persistent_marker(driver)       ← CDP addScriptToEvaluateOnNewDocument
                    apply_automation_marker(driver)          ← execute_script
                                    │
        _emergency_stop_all()  ──────┤  ← [tk] (stop button)
                                    ▼
                    self.app_state.driver.quit()            ← killed
                    self.app_state.driver = None
                    self.app_state.active_browser = None
                    self.app_state.active_automations.clear()
                                    │
        wrapper finally: ────────────┤  ← [Wn]
                                    ▼
                    tab_instance.driver.quit()              ← per-tab quit
                    tab_instance.driver = None
                                    │
        _marker_keeper exit: ────────┤  ← [Mn]
                                    ▼
                    if owns_session: marker_session.quit()  ← separate CDP session
```

### Shared mutable state — the driver triple-write problem

There are **three places** that hold the driver (or its mirror):

| Field | Class | Set by | Read by |
|---|---|---|---|
| `self.driver` | `BrowserManager` | `launch_firefox_managed:208`, `launch_chrome_detached` (via WebDriver), `_prepare_driver_tab:415` (sets to None on failure), `_emergency_stop_all` (via `app_state.driver.quit()` — but `BrowserManager.driver` is not reset!) | `get_driver:462-471` |
| `self.app_state.driver` | `NregaBotApp.app_state` | `AutomationMixin.get_driver:162`, `_emergency_stop_all:751` (None) | `AutomationMixin._minimize_active_browser:395`, `_emergency_stop_all:743`, every consumer that does `app.driver` |
| `self.app.driver` | `NregaBotApp` (legacy alias) | `BrowserManager.launch_firefox_managed:208-209` | anything using the legacy alias |

The **three-way sync is convention only** — there is no `property` enforcing equivalence. `launch_firefox_managed` updates `self.app.driver` (line 208) but `launch_chrome_detached` does NOT (it only updates `BrowserManager.driver` indirectly via the subprocess). `AutomationMixin.get_driver` updates `self.app_state.driver` but `BrowserManager.get_driver` (called next) does not. The comment in `app_automation.py:159-164` says: "Mirror into app_state for backward-compat" — so the convention is `app_state.driver` is the new home, but `app.driver` and `BrowserManager.driver` are still authoritative in places.

### The "pinned tab" invariant (a hidden state machine)

`BrowserManager._automation_tab_handle` (line 67) is the single non-obvious field. Lifecycle:
- `None` initially.
- Set to the resolved handle inside `resolve_automation_tab` (line 366 or 371) — but only on first resolve per session.
- Survives the entire app lifetime (line 352: "if still open, reuse it").
- Cleared by `resolve_automation_tab:356` if the user closed the pinned tab.
- **Never cleared explicitly otherwise** — even after `_emergency_stop_all` quits the driver (the next `get_driver` will probe `window_handles` and re-pin).

The "marker" is `AUTOMATION_MARKER_JS` (line 27-45) — a 20-line JS that:
- Prefixes `document.title` with "🤖 NREGA-BOT ⚙ Running".
- Injects a red-dot favicon as `<link rel="icon" type="image/svg+xml" id="nregabot-icon">`.
- Uses a `setInterval(apply, 1000)` to self-heal against `document.title` rewrites by the portal.

The CDP `Page.addScriptToEvaluateOnNewDocument` (line 333) makes the marker re-run on every navigation. The marker-keeper thread (line 358) re-paints via `execute_script` every ~2s tick.

### `keep_tab_active` — the focus-stealing escape hatch

`browser_manager.py:289-319` uses three CDP commands to prevent Chrome/Edge from throttling the hidden tab:

| CDP call | What it does | Persistence |
|---|---|---|
| `Page.setWebLifecycleState {"state": "active"}` | Keep timers/rendering alive | resets on navigation → marker-keeper re-applies every 2s |
| `Emulation.setFocusEmulationEnabled {"enabled": true}` | `document.hasFocus()` stays true | persists per session, does NOT affect user's actual focused tab |
| `Emulation.setCPUThrottlingRate {"rate": 1}` | No CPU throttling | persists |

The docstring at line 291-307 says: **"Firefox has no execute_cdp_cmd, so this is a safe no-op there."** All three calls are wrapped in `try/except: pass` — no errors propagate.

### Cross-module dependencies

```
BrowserManager
  ├─ src.config (OS_SYSTEM, DEFAULT_LAUNCH_URLS, MAIN_WEBSITE_URL, COLORS)
  ├─ src.utils.resource_path (asset paths)
  ├─ self.app (NregaBotApp) ← reaches back for: play_sound, show_toast, after, winfo, icon_images
  ├─ selenium.webdriver.{chrome,firefox,edge}
  ├─ webdriver_manager.{chrome,microsoft,firefox}
  └─ CTk widgets (CTkToplevel, CTkButton, CTkCheckBox, CTkLabel)  ← only inside _ask_browser_selection
```

The manager **does not import any other manager** — it reaches into `self.app` for cross-concern calls (sound, toast). This is the "god proxy" pattern in action.

### Thread boundaries

| Method | Thread | Notes |
|---|---|---|
| `__init__` | [tk] | Sets `os.environ['WDM_LOG'] = '0'` — a global side-effect |
| `launch_chrome_detached` | [tk] | `subprocess.Popen` (fire-and-forget) |
| `launch_firefox_managed` | [tk] | Constructs `WebDriver(...)` directly |
| `get_driver` | **MUST BE [tk]** for the modal dialog path | `self.app.wait_window(dialog)` (line 668) is a blocking call; on [Wn] it deadlocks. The 44 callers from tab `run_automation_logic` all run on [Wn] — but the modal-dialog branch only fires when `available_browsers` has > 1 and the user hasn't picked yet. The 0.2s socket timeouts make the probe safe to call from any thread. |
| `_connect_external` | any | Pure WebDriver construction, no UI |
| `apply_automation_marker` / `keep_tab_active` / `_inject_persistent_marker` | any (the [Mn] keeper calls all three) | `try/except: pass` everywhere |
| `resolve_automation_tab` | any | `driver.switch_to.window(h)` is unsafe from [Wn] if the driver is shared (which Firefox's is) |
| `_prepare_driver_tab` | any | Calls `self.app.after(0, lambda: messagebox.showwarning(...))` to bounce the dialog onto [tk] — proof that the method CAN run on [Wn] |
| `connect_driver_no_dialog` | any | Returns `(driver, owns_session)` tuple — called by `_marker_keeper` [Mn] |
| `clear_thread_choice` | any | Pure dict mutation |

### Implicit contracts (convention only)

1. **`get_driver()` is not safe to call concurrently from multiple threads.** The 44 `run_automation_logic` callers each run on their own [Wn] — but the AutomationMixin's `start_automation_thread` enforces "one automation key alive at a time" (line 176 guard). So in practice, [Wn] is at most one per key, but **two different keys running on the same browser CAN both call `get_driver()` simultaneously**. The race is on `_thread_browser_choice` (dict) and on `self.driver` (assigned without a lock).
2. **`self.driver` is *the* in-app Firefox driver** when `active_browser == "firefox"` — every tab's `run_automation_logic` shares it. For Chrome/Edge, `get_driver` returns a *new* `webdriver.Chrome(options=opts, ...)` per call (via `_connect_external`). So Firefox: 1 driver, N tabs. Chrome/Edge: N drivers, N tabs. **The behavior is fundamentally different and the call site cannot tell.**
3. **The pinned tab handle is for the FIRST successful resolve.** `resolve_automation_tab` returns the cached handle if still valid (line 352), else re-resolves. This is the **only mechanism** that keeps automation on the same tab across runs. If a tab author manually does `driver.get(some_url)` outside of automation, they may unintentionally change the "main tab" — but the cached handle stays put, so subsequent runs will `switch_to.window(handle)` back.
4. **`_automation_tab_handle` is stored in CDP-handle format**, which is a different ID space than the `window_handles` from the *automation* session. The comment at `browser_manager.py:347-349` says: "Window handles are browser-level target IDs, stable across CDP sessions" — that's the invariant that lets the marker-keeper's separate CDP session share the same `target`.
5. **`launch_chrome_detached` and `launch_edge_detached` write to `BrowserManager.driver = None` if the subprocess fails**, but `app_state.driver` is not touched. Subsequent `get_driver` calls will return `None` from `BrowserManager.driver` but may still find Chrome via the port probe. State desync.

### Potential race conditions

| # | Race | Where | Severity | Notes |
|---|---|---|---|---|
| **D1** | **Two `start_automation_thread` calls with different keys both call `get_driver()` from [Wn]**. For Chrome/Edge, both construct a new `WebDriver(debuggerAddress="127.0.0.1:9222", ...)`. Chrome allows only one CDP *control* client; the second connection's `execute_cdp_cmd` will fail. | `browser_manager.py:253-279` + 47 callers | **HIGH** | The `_marker_keeper` is one of the second clients. Marker will silently fail (`keep_tab_active` is try/except:pass). |
| **D2** | **`get_driver()` is called from [Wn] but blocks on the modal dialog `wait_window`** when the user has never picked. This deadlocks the worker thread (and the UI). | `browser_manager.py:668` | **HIGH** | The `0.2s` socket timeouts are short, so the dialog only appears for > 0.4s total. Real-world trigger: first run after launch, multiple browsers open. |
| **D3** | **`self.app_state.driver = None` in `_emergency_stop_all` (line 751, [tk])** races with `wrapper`'s `tab_instance.driver.quit()` (line 300, [Wn]). The `try/except` in `_emergency_stop_all:746-749` swallows the error, but if [Wn] is mid-`quit()` when [tk] does `self.app_state.driver = None`, the worker thread's `finally:` will hit a dead `driver.quit()` and silently fail. | `app_automation.py:300` vs `app_automation.py:743-754` | medium | Try/except hides it; no observable symptom |
| **D4** | **`_automation_tab_handle` is set on the *marker-keeper*'s CDP session** (via `resolve_automation_tab:366`), then the *worker's* driver calls `resolve_automation_tab` again and gets a *different* handle (because `driver.window_handles` is session-scoped). The comment at line 347-349 says handles are "stable across CDP sessions" — but the comment at line 365 reads `driver.execute_script("return location.href")` which uses *that session's* tab list, not the worker's. | `browser_manager.py:339-374` | medium | This is the exact bug fixed in past — see the docstring at line 63-67 |
| **D5** | **`launch_chrome_detached` `subprocess.Popen` and a subsequent `get_driver` socket probe (line 478)** — Chrome takes ~1-2s to start listening on 9222. The probe's 0.2s timeout means the first probe right after launch will fail with `ConnectionRefusedError`, which is *caught* and treated as "Chrome not running." | `browser_manager.py:72-123` + `:478-481` | low | The user has to click "Launch Chrome" then click "Start" — enough delay in practice |
| **D6** | **Firefox `dom.min_background_timeout_value=10` and `dom.timeout.background_throttling_max_budget=-1` are preferences** (line 187-190). If the user has already launched Firefox with a different profile, these are ignored. | `browser_manager.py:187-190` | low | Docstring says "when the Firefox window is minimized/occluded" — but the prefs are persistent, not per-session |
| **D7** | **`connect_driver_no_dialog` (line 418) returns `(self.driver, False)` for Firefox** — i.e. it shares the same driver. The marker-keeper's `apply_automation_marker` and `keep_tab_active` then call `execute_cdp_cmd` and `execute_script` on a driver that the *worker* is actively using. | `browser_manager.py:425-433` + `app_automation.py:358-366` | low | `_marker_keeper` only runs `apply_automation_marker` and `keep_tab_active` (Firefox no-ops the latter), so the impact is the title re-prefix and a favicon change. Worker's `switch_to.window` calls are NOT done by the keeper for Firefox. |
| **D8** | **`AutomationMixin.get_driver` (line 159-164) writes to `app_state.driver` and `app_state.active_browser`** but does **not** write to `BrowserManager.driver` (which was already updated by `_connect_external`). The mirror is one-way here. If `BrowserManager` is later asked by something else, it has the correct driver but `app_state.driver` is what the workers use. | `app_automation.py:159-164` | low | Convention, no enforcement |
| **D9** | **`window_handles[0]` is *not* stable across CDP sessions** — the comment at `browser_manager.py:64-66` says exactly this and the `_automation_tab_handle` pinning is the fix. But `launch_chrome_detached` does `subprocess.Popen` and *then nothing* — there's no `resolve_automation_tab` call. So the *first* run after launch may pin to a tab the user didn't intend (the second `DEFAULT_LAUNCH_URLS` tab, not the first). | `browser_manager.py:72-123` | low | Affects first-run UX only |

### Safe refactoring boundaries

| Boundary | Why safe |
|---|---|
| `AUTOMATION_MARKER_JS` (lines 27-45) | Module-level string constant, only injected via `execute_script` (line 285) and CDP `addScriptToEvaluateOnNewDocument` (line 333). Edit in isolation. |
| `keep_tab_active` (lines 289-319) | Three independent CDP calls each in their own try/except. Refactor to a list-of-calls is trivial. |
| `connect_driver_no_dialog` (line 418) | Pure, no UI, no state mutation. Returns a tuple. Easy to test in isolation (but no test exists). |
| `clear_thread_choice` (line 671) | Single-line dict pop. |
| `_thread_browser_choice` (line 60) | Only accessed by `get_driver` and `clear_thread_choice`. Adding a per-process lock here would fix D1 cleanly. |

### Existing tests that protect this behavior

**None.** `BrowserManager` has zero direct tests. The closest is `_smoke_test_tabs.py::FakeApp.get_driver` (`_smoke_test_tabs.py:108-109`) which is a `return None` stub.

**Coverage gap (entire surface):** `BrowserManager.__init__`, `get_driver`, `launch_*`, `resolve_automation_tab`, `keep_tab_active`, `apply_automation_marker`, `connect_driver_no_dialog`, `clear_thread_choice` — 0/9 of the public surface is tested. The marker-keeper thread coordination is also untested.

---

## 4. WorkflowManager Macro Queue interaction with the automation engine

### Important symbols

| Symbol | qn | in/out | Where |
|---|---|---|---|
| `WorkflowManager` (class) | `NregaBot.src.managers.workflow_manager.WorkflowManager` | (cl) | `workflow_manager.py:9` |
| `__init__` | `…WorkflowManager.__init__` | 0/0 | `workflow_manager.py:10-17` |
| `_log` | `…WorkflowManager._log` | 0/0 | `workflow_manager.py:20-23` |
| `_wait_and_execute` | `…WorkflowManager._wait_and_execute` | 0/0 | `workflow_manager.py:26-30` |
| `_wait_for_automation_finish` | `…WorkflowManager._wait_for_automation_finish` | 3/8 | `workflow_manager.py:32-67` |
| `_ensure_automation_stopped` | `…WorkflowManager._ensure_automation_stopped` | 2/4 | `workflow_manager.py:69-75` |
| `_scrape_workcodes_from_active_tab` | `…WorkflowManager._scrape_workcodes_from_active_tab` | 1/0 | `workflow_manager.py:78-100` |
| `_set_target_on_tab` | `…WorkflowManager._set_target_on_tab` | 2/0 | `workflow_manager.py:103-151` |
| `_run_generic_task` | `…WorkflowManager._run_generic_task` | 1/11 | `workflow_manager.py:153-185` |
| `_macro_call` | `…WorkflowManager._macro_call` | 1/0 | `workflow_manager.py:188-197` |
| `_update_item_status` | `…WorkflowManager._update_item_status` | 1/0 | `workflow_manager.py:199-207` |
| `process_global_queue` | `…WorkflowManager.process_global_queue` | 2/21 | `workflow_manager.py:210-349` |
| `switch_to_msr_tab_with_data` | `…WorkflowManager.switch_to_msr_tab_with_data` | 1/0 | `workflow_manager.py:352-360` |
| `switch_to_emb_entry_with_data` | `…WorkflowManager.switch_to_emb_entry_with_data` | 1/0 | `workflow_manager.py` |
| `switch_to_zero_mr_tab_with_data` | `…WorkflowManager.switch_to_zero_mr_tab_with_data` | 1/0 | `workflow_manager.py` |
| `run_bulk_demand_sequence` | `…WorkflowManager.run_bulk_demand_sequence` | 1/0 | `workflow_manager.py` |

### Callers (inbound, 2 for `process_global_queue`)

- `MacroManagerTab.start_macro` (via the tab's UI button) — fires the queue from the [tk] side.
- `AutomationMixin._maybe_auto_start_queue` — auto-restart of pending items.

The queue runs **on a thread** (`threading.Thread(target=process_global_queue, daemon=True)` somewhere in `MacroManagerTab.start_macro` — not in the graph as a literal, but the function body uses `time.sleep(...)` heavily, so it must not be on [tk]). Let me confirm via the polling loop: `process_global_queue` calls `time.sleep(3)` between items (line 341) and `time.sleep(1.5)` inside `_run_generic_task` (line 158). The `time.sleep` is the giveaway — this is a [β] thread, not [tk].

### Callees (outbound, 21 for `process_global_queue`)

```
process_global_queue
  ├─ self.app.stop_events["macro"].is_set()           ← THE macro cancel flag
  ├─ self._update_item_status(id, status, msg, macro_tab)
  ├─ self._log(macro_tab, msg, level)
  ├─ self._run_generic_task(tab_name, target, automation_key, macro_tab=macro_tab)
  │     ├─ self.app.after(0, self.app.show_frame, tab_name)
  │     ├─ time.sleep(1.5)
  │     ├─ self._ensure_automation_stopped(automation_key)
  │     ├─ self._set_target_on_tab(tab, target, entry_attr)
  │     ├─ [optional] self.app.after(500, tab._auto_fill_staff)  ← Muster Roll Gen staff pre-fill
  │     ├─ self.app.after(3000, tab.start_automation)            ← 3-SECOND DELAY
  │     └─ self._wait_for_automation_finish(automation_key, macro_tab=macro_tab)
  ├─ self._scrape_workcodes_from_active_tab(tab_name)  ← for "MR Tracking" items
  ├─ self.switch_to_msr_tab_with_data / switch_to_emb_entry_with_data / switch_to_zero_mr_tab_with_data
  │     └─ self.app.show_frame(...)
  │     └─ self.app.after(3000, tab.start_automation)  ← SAME 3-SECOND DELAY
  ├─ self.run_bulk_demand_sequence(item, macro_tab)
  ├─ AutomationMixin.start_automation_thread  ← direct call (depth 3)
  ├─ self.app.after(0, lambda: self._macro_call(m, "set_ui_state", True/False))  ← disable Macro tab UI
  ├─ self.app.play_sound("macro_start") / "macro_finish"
  └─ self.app.after(0, messagebox.showerror, "Macro Error", str(e))  ← error path
```

### The queue processing loop (verbatim, lines 215-347)

```python
try:
    for item in self.queue_items:                                    # iterate list
        if self.app.stop_events["macro"].is_set(): break            # [1] macro cancel
        if item['status'] == 'Success': continue                    # [2] skip done
        self._update_item_status(item['id'], "Running", ...)
        success = False
        msg = "Finished"
        try:
            task_type = item['type']
            target = item.get('target', '')
            if item.get('tab_name') and item.get('automation_key'):  # [A] Add-to-Queue
                success = self._run_generic_task(
                    item['tab_name'], target, item['automation_key'], macro_tab=macro_tab)
            elif "Wagelist Gen" in task_type or task_type == 'wagelist_gen_send':
                # ...two-step "gen + auto-send" with 3s sleep between
            elif "MR Tracking" in task_type or "mr_track" in task_type:
                # ...scrape workcodes, then hand off to MSR/ZeroMR/EMB tab
            elif "Verify Job Card" in task_type or ...:
                success = self._run_generic_task(...)
            # ... ~6 more branches (bulk_demand, etc.)
        except Exception as e:
            msg = str(e); self._log(...); success = False
        self._update_item_status(item['id'], "Success" if success else "Failed", msg, macro_tab)
        self._log(macro_tab, f"Task finished: {msg}", "success" if success else "error")
        self.app.after(0, self.app.set_status, f"Macro: {task_type} - {msg}")
        time.sleep(3)                                                # [3] 3s settle between items
except Exception as e:
    self.app.after(0, messagebox.showerror, "Macro Error", str(e))
finally:
    self.app.after(0, lambda m=macro_tab: self._macro_call(m, "set_ui_state", False))
    self.app.after(0, self.app.set_status, "Macro Queue Finished")
    self.app.play_sound("macro_finish")
    self._log(macro_tab, ">>> Macro Queue Execution Finished.")
```

### The polling waiter — `_wait_for_automation_finish` (lines 32-67)

This is the **synchronization primitive** between the macro thread and the automation engine:

```python
def _wait_for_automation_finish(self, key, timeout=900, macro_tab=None):
    start = time.time()
    self._log(macro_tab, f"Waiting for '{key}' automation to start...")
    automation_started = False
    # ── Phase 1: Wait for automation to APPEAR in active_automations (≤ 30s) ──
    for _ in range(30):
        if key in self.app.active_automations:                      # [P1]
            automation_started = True
            break
        time.sleep(1)
    if not automation_started:
        running_keys = list(self.app.active_automations)
        self._log(macro_tab, f"Error: Automation '{key}' did not start. Running: {running_keys}", "error")
        return False
    # ── Phase 2: Wait for automation to DISAPPEAR (≤ timeout) ──
    while key in self.app.active_automations:                       # [P2]
        if self.app.stop_events.get("macro") and self.app.stop_events["macro"].is_set():
            self._log(macro_tab, "Macro stopped by user.", "warning")
            return False
        if time.time() - start > timeout:
            self._log(macro_tab, f"Timeout: Automation '{key}' took too long.", "error")
            return False
        time.sleep(1)
    self._log(macro_tab, f"Automation '{key}' finished.")
    return True
```

This is a **busy-wait on `app.active_automations` membership** — 1-second polling, with two distinct phases. The graph's depth-3 trace shows no other waiter does the same thing. This is the unique coupling surface between `WorkflowManager` and `AutomationMixin`.

### Shared mutable state

| Field | Written by `WorkflowManager` | Read by `WorkflowManager` | Written by `AutomationMixin` |
|---|---|---|---|
| `self.app.stop_events["macro"]` | (UI button sets it — not in `WorkflowManager`) | line 57 (Phase 2 cancel) | `start_automation_thread:185` creates per-key events, NOT `"macro"` — special-cased |
| `self.app.active_automations` (Set[str]) | **read only** at lines 42, 56 | lines 42, 56 | add (line 184), `discard` (in `on_automation_finish`), `clear` (`_emergency_stop_all:770`) |
| `self.app.tab_instances` (Dict) | read at line 27, 160, 355, plus via `self.app.tab_instances.get(...)` | read | not written (NavMixin only) |
| `self.queue_items` (List[dict]) | append (UI button side), iterate (line 215), mutate status (line 204) | mutate (line 204), iterate (line 215) | not touched |
| `self.pipeline_queue` | (declared at line 12, **never used elsewhere** — dead field) | never | not touched |
| `self.is_pipeline_running` | (declared at line 13, **never used elsewhere** — dead field) | never | not touched |
| `self.app.driver`, `self.app_state.driver` | (transitively via the worker's `target` which calls `get_driver`) | (transitively) | `AutomationMixin.get_driver:162` |

The **single load-bearing shared state is `app.active_automations`** (Set). Everything else is either one-way reads or per-instance state.

### Cross-module dependencies

```
WorkflowManager
  ├─ src.utils.get_logger
  ├─ self.app (NregaBotApp)  ← tab_instances, active_automations, stop_events, show_frame, after, set_status, play_sound, log_message
  ├─ tab attributes (loose duck-typed: tab.log_display, tab.results_tree, tab.get_clean_workcodes, tab.panchayat_var, tab.agency_entry, tab.panchayat_entry, tab.agency_var, tab._auto_fill_staff, tab.start_automation)
  └─ tkinter.messagebox (the error dialog)
```

Notably, `WorkflowManager` does NOT import `AutomationMixin` or `BrowserManager` — it reaches them through `self.app.start_automation_thread` and `self.app.after(0, ...)`. The macro-to-automation hand-off is a method call, not an import.

### Thread boundaries

| Code path | Thread |
|---|---|
| `MacroManagerTab.start_macro` (the entry point) | [tk] — sets `app_state.stop_events["macro"]` and starts the worker thread |
| `process_global_queue` body | [β] — the macro worker thread |
| `_run_generic_task` body | [β] — same thread, synchronous |
| `_wait_for_automation_finish` busy-wait | [β] — `time.sleep(1)` poll |
| `app.show_frame(tab_name)` (line 157) | [β] → bounced to [tk] via `app.after(0, ...)` |
| `tab.start_automation()` (line 183) | [β] → bounced to [tk] via `app.after(3000, ...)` |
| `tab._auto_fill_staff()` (line 175) | [β] → bounced to [tk] via `app.after(500, ...)` |
| `tab.start_automation` body | [tk] (the `after` fires) → [Wn] (it calls `start_automation_thread` which spawns the worker) |
| The actual automation | [Wn] — owned by `AutomationMixin.start_automation_thread` |
| The marker-keeper | [Mn] — owned by `AutomationMixin.start_automation_thread` |
| `self._log(macro_tab, ...)` | [β] — but it eventually calls `app.log_message(macro_tab.log_display, ...)` which is the chokepoint for `safe_after` |

**The thread choreography is: [tk] (button click) → [β] (macro worker) → [tk] (via after(0,…) / after(500,…) / after(3000,…)) → [Wn] (wrapper) → [tk] (after(0, on_automation_finished)) → [Mn] (marker keeper).** Five distinct threads for one macro item.

### The 3-second delay magic number

Three places have the `3000` constant (the "3-second delay before start_automation"):
- `workflow_manager.py:183` — `self.app.after(3000, lambda: tab.start_automation())`
- `workflow_manager.py:359` — `self.app.after(3000, lambda: tab.start_automation())` (in `switch_to_msr_tab_with_data`)
- Plus `time.sleep(3)` between macro items (line 341)
- Plus `time.sleep(1.5)` after `show_frame` (line 158)

The comment at `workflow_manager.py:179-182` explains: "Removed unnecessary `update_idletasks` — the 3s delay before `start_automation` gives the event loop plenty of time to flush pending UI updates naturally." This is a heuristic that **assumes a 3-second event-loop flush is sufficient** — a slow machine could miss the deadline, a fast machine wastes 3s per item.

### `_set_target_on_tab` — the duck-typed panchayat setter

This function (lines 103-151) reflects the **heterogeneity of tab widgets**:

```python
def _set_target_on_tab(self, tab, target, entry_attr="panchayat_entry", sync=False):
    entry_widget = getattr(tab, entry_attr, None)               # try "panchayat_entry"
    if not entry_widget and hasattr(tab, "agency_entry"):
        entry_widget = tab.agency_entry                          # fallback
    if entry_widget is not None:
        # CTkEntry-style: delete + insert
        if sync: entry_widget.delete(0, "end"); entry_widget.insert(0, target)
        else: self.app.after(0, ...); self.app.after(100, ...)
    # Fallback: a matching StringVar / option menu
    setter_var = None
    var_attr = entry_attr.replace("_entry", "_var")              # "panchayat_entry" → "panchayat_var"
    menu_attr = entry_attr.replace("_entry", "_menu")            # → "panchayat_menu"
    for attr_name in (var_attr, menu_attr, "panchayat_var", "agency_var"):
        candidate = getattr(tab, attr_name, None)
        if candidate is not None and hasattr(candidate, "set"):
            setter_var = candidate; break
    # CTkOptionMenu-style: set() the var, with case-insensitive option matching
```

This is **runtime duck-typing** across tabs that have *inconsistent* attribute names. There is no interface/protocol; the function tries 6 different attribute names and 2 widget types. Adding a new tab requires `getattr(tab, ..., None)` to return one of the known names.

### `_macro_call` — the safe-Macro-tab UI bridge (lines 188-197)

```python
def _macro_call(self, macro_tab, method, *args):
    try:
        if macro_tab is not None and hasattr(macro_tab, method):
            alive = getattr(macro_tab, '_is_alive', lambda: True)
            if alive():
                getattr(macro_tab, method)(*args)
    except Exception:
        pass
```

The docstring at lines 189-191 says: "macro_tab par safe UI call — jab queue background me chale (Macro Manager tab loaded nahi / destroy ho chuka) to silently skip karo." This is the **only check** that the Macro Manager tab still exists when the queue is running. It catches everything with `except Exception: pass` — silent failures are intentional.

### Implicit contracts (convention only)

1. **`self.app.stop_events["macro"]` exists at queue start time.** The macro *must* be started from a [tk] context that creates this event. `_emergency_stop_all` (line 729-779) iterates `app_state.active_automations` and sets each event, but **does NOT set `stop_events["macro"]`**. So emergency-stop kills all per-key automations but the macro thread itself keeps polling `app.active_automations` (which is now empty after `_emergency_stop_all:770` clear) and exits naturally on the next loop iteration.
2. **`self.queue_items` items have specific shapes** (lines 215-237). Adding a new task type means editing `process_global_queue`'s big if/elif chain. The "Add to Queue" path (line 235) is the only generic one — every other branch is a string match on `item['type']`.
3. **`_wait_for_automation_finish` is a 1-second polling loop with a 30-second start window and a 900-second finish window.** If the automation takes > 30s to appear in `active_automations` (e.g. due to a slow `get_driver` blocking on a dialog), the macro gives up — even though the automation eventually started.
4. **The macro worker thread is *not* a daemon thread with cancellation tokens beyond `stop_events["macro"]`.** If the macro thread is in a long `time.sleep(3)` (line 341), the user's "Stop" click takes up to 3 seconds to take effect.
5. **Tabs are expected to expose `panchayat_entry` / `agency_entry` / `panchayat_var` / `agency_var` / `panchayat_menu` / `_auto_fill_staff`** for the macro to drive them. No base class or protocol enforces this. (This is the same duck-typed contract as `BaseAutomationTab._is_alive()`.)

### Potential race conditions

| # | Race | Where | Severity | Notes |
|---|---|---|---|---|
| W1 | **`process_global_queue` iterates `self.queue_items` while UI buttons may be mutating it** (e.g. user adds more items while a macro is running). Python `for item in list` over a list is safe; the `process_global_queue` uses `for item in self.queue_items:` (line 215) — **NOT a snapshot**. If the list is mutated mid-iteration, `RuntimeError: list changed size during iteration`. | `workflow_manager.py:215` | medium | The UI side is supposed to not mutate during a run, but nothing enforces it. `runtime_queue` items *can* be added mid-run via Add to Queue, depending on the tab's `start_automation_thread` paths. |
| W2 | **`_wait_for_automation_finish` busy-waits on `app.active_automations` (Set)**. A race exists where the *previous* `start_automation_thread` for the same `key` has just added to the set (line 184), but the worker hasn't run yet, so the set has the key. `_wait_for_automation_finish:42` sees it and declares "started" — but the *previous* worker is still finishing. The macro then waits on Phase 2 and may exit prematurely when the *previous* run finishes (before the *new* run's `target` even starts). | `workflow_manager.py:42, 56` | **HIGH** | The 3-second `after(3000, tab.start_automation)` delay (line 183) plus the 3s `time.sleep` (line 341) mitigate this in practice — but for fast machines or short items, it's a real race. |
| W3 | **`_set_target_on_tab` reads `setter_var.cget("values")`** (line 141) to do case-insensitive matching. If the user is typing into the panchayat entry *while* the macro runs, `cget("values")` may return a list being mutated. The `list(...)` wrapper at line 141 takes a snapshot, but the list itself is shared. | `workflow_manager.py:141` | low | `for v in list(setter_var.cget("values"))` is iterated; mutation during the for-loop is safe. |
| W4 | **`_wait_for_automation_finish` checks `app.stop_events["macro"]` only inside the Phase 2 loop** (line 57), not in Phase 1. If the user clicks Stop *between* Phase 1 and Phase 2 (i.e. after the automation started but before it finished), the macro honors the cancel. But if the user clicks Stop during Phase 1, the macro ignores it. | `workflow_manager.py:32-67` | low | 30s max for Phase 1; not user-visible |
| W5 | **`_update_item_status` mutates `self.queue_items` in place** (line 203-206), then calls `_macro_call(macro_tab, "update_item_status", ...)` which checks `_is_alive()`. The Macro Manager tab's `update_item_status` is called on [β] (the macro thread), but it does UI work — which violates the "never touch Tk from a worker thread" rule. The `_is_alive` check is the only guard, and it's `lambda: True` for tabs that don't override it. | `workflow_manager.py:188-197` | low | Comment in base_tab.py:521-527 (`safe_after`) is the chokepoint |
| W6 | **Two macro queues cannot run concurrently** — `MacroManagerTab.start_macro` is supposed to be disabled when `is_pipeline_running` (a dead field, line 13) is True. But the field is never set, so two clicks could spawn two `[β]` threads racing on the same `self.queue_items`. | `workflow_manager.py:12-13` | medium | The field is unused — bug or vestigial? |
| W7 | **The macro thread calls `app.after(0, messagebox.showerror, "Macro Error", str(e))`** (line 344) inside the catch-all `except`. This runs on [tk] correctly. But if the user closes the app while the macro is running, the `after` callback fires into a destroyed root — TclError. | `workflow_manager.py:344` | low | `install_crash_reporter` catches; app exits cleanly |
| W8 | **`_run_generic_task` is synchronous within the macro thread** but the **3-second `after(3000, ...)` is the only synchronization**. If the user's machine is so slow that the event loop doesn't flush the `tab.start_automation` callback within 3s, the macro's `_wait_for_automation_finish` will time out. | `workflow_manager.py:158, 183` | low | Comment at line 180-182 explains the heuristic |
| W9 | **`process_global_queue` does `time.sleep(3)` between items** (line 341) — *synchronous* on the macro thread. If the macro is stopped during this sleep, the cancel takes up to 3s to take effect. | `workflow_manager.py:341` | low | 3s is acceptable |
| W10 | **Phase 1 of `_wait_for_automation_finish` (lines 41-45) has 30 iterations × 1s = 30s**. This is **hardcoded** and doesn't use the `timeout` parameter (which is for Phase 2). So a "30-second start window" is invariant. | `workflow_manager.py:41-45` | low | Magic number; documented intent but not configurable |

### Safe refactoring boundaries

| Boundary | Why safe |
|---|---|
| `_log`, `_macro_call` (lines 20-23, 188-197) | Pure helpers, no external state beyond `self.app` and `macro_tab`. Easy to extract. |
| `_wait_for_automation_finish` (lines 32-67) | The bus is on `self.app.active_automations` and `self.app.stop_events["macro"]` only. Adding a per-key Event (already exists) and replacing the poll with `event.wait()` would be a clean refactor. |
| `_ensure_automation_stopped` (lines 69-75) | Standalone, no callbacks, just a poll. |
| `_set_target_on_tab` (lines 103-151) | Duck-typed over tab widgets; the only way to make it safe to refactor is to introduce a protocol or base class (out of scope for a "no rewrites" task). |
| The `if/elif` chain in `process_global_queue` (lines 235-333) | Each branch is a self-contained block. Adding a new branch is a contained change. |
| The dead `pipeline_queue` and `is_pipeline_running` fields (lines 12-13) | **Delete safely** — no callers in the graph. But do confirm via `git grep` before deletion (the graph may not see dynamic access). |

### Existing tests that protect this behavior

**None.** `WorkflowManager` has zero direct tests. The closest is `tests/test_location_merge.py` which tests `apply_server_data` (a `location_sync` function), not the macro queue.

**Coverage gap:** `WorkflowManager.__init__`, `_wait_for_automation_finish` (the bus-wait), `process_global_queue` (the main loop), `_set_target_on_tab` (the duck-typed setter), and the three `switch_to_*_tab_with_data` handoff methods — all 0/N untested.

---

# Dependency Graph (text form)

> Box types: `[File]` = module, `[Class]`, `[Method]`, `[Function]`, `{State}` = shared mutable field, `<Thread>` = thread boundary.
> Edge types: `--calls-->` (direct), `--writes-->` / `--reads-->` (state), `--spawns-->` (thread creation), `--mirrors-->` (state alias).

## 1. NregaBotApp / mixin coupling

```
                [main_app.py]
                    │
                    │ imports + instantiates
                    ▼
              [NregaBotApp] (class, 1/4 in/out)
        ┌──────────┬──────────┬──────────┬──────────┐
        │          │          │          │          │
   [LicenseMixin] [NavMixin] [AutomationMixin] [UIMixin]    all in src/app/
   (in=2, out=0)  (in=1, out=0) (in=1, out=0)  (in=1, out=0)
        │          │          │          │          │
        │   depends on host-attr (documented in        │
        │   app_automation.py:143-153):                │
        │   browser_manager, driver, active_browser,   │
        │   stop_events, history_manager,              │
        │   automation_threads, active_automations,    │
        │   minimize_var, services                      │
        └──────────┴──────────┴──────────┴──────────┘
                              │
                              │ all read/write
                              ▼
                    {self.app_state (AppState)}
                    src/state.py — 60+ fields, dataclass
                              │
                              │   e.g. driver, active_browser
                              │   mirrored to/from:
                              ▼
                    {self.app_state.driver}
                    {self.app_state.active_browser}
                    {self.app_state.active_automations}  ←── Set[str]
                    {self.app_state.stop_events}         ←── Dict[str, Event]
                    {self.app_state.automation_threads}   ←── Dict[str, Thread]
                    {self.app_state.automation_progress} ←── Dict[str, float]

        [src/ui_components]  [src/managers/*]  [src/tabs/*]
              │                    │                 │
              │   LazyIconManager, SoundManager,     │
              │   BrowserManager, ServiceManager,    │
              │   WorkflowManager, HistoryManager    │
              │   (all reach back to self.app)       │
              └────────────────────┴─────────────────┘
```

## 2. AutomationMixin.start_automation_thread and wrapper

```
            any tab's start_automation [tk]
                      │
                      │ calls
                      ▼
   [AutomationMixin.start_automation_thread]   <tk> (caller)
            src/app/app_automation.py:175-379
                      │
        ┌─────────────┼──────────────┬──────────────┐
        │             │              │              │
   [history.        [browser.     [self.       [self.after(0,...)
    increment_       clear_thread_  play_sound,    ┐
    usage, log_      choice]        set_status,   │ self-references for
    automation_                    show_toast]   │ the marker-keeper
    start]                                       │
        │                                          │
        │   then spawns                           │
        ▼                                          │
   <Wn: wrapper closure>    src/app/app_automation.py:216-307
        │                                          │
        ├─ target(*args)             [Wn]  ◄── THE AUTOMATION RUNS HERE
        │   (the tab's run_automation_logic)
        │     ├─ calls get_driver (BrowserManager)        ◄── §3
        │     ├─ uses app_state.driver
        │     ├─ writes tab_instance.driver
        │     └─ checks app_state.stop_events[key].is_set()
        │
        ├─ except: _extract_error_context(e)
        │           ├─ mask_pii_text (utils)   [DPDP compliance]
        │           ├─ traceback.extract_tb (capped 600/4000)
        │           └─ (error_type, error_msg, error_source, error_traceback)
        │     └─ opt-in screenshot if save_error_screenshots
        │           (LOCAL only — never uploaded)
        │
        └─ finally:                       [GUARANTEED to run]
              ├─ browser_manager.clear_thread_choice()
              ├─ compute duration from tab.activity_start_time
              ├─ if tab_instance.driver: tab_instance.driver.quit() ◄── RACE with _emergency_stop_all
              ├─ tab_instance.driver = None
              └─ self.after(0, self.on_automation_finished, ...)   ◄── hop to [tk]
                      │
                      ▼
        <Wn dies>  →  <tk: on_automation_finished>  src/app/app_automation.py:467-557
                                          │
                       ┌──────────────────┼──────────────────┐
                       │                  │                  │
                  history.            tab.             _sync_automation_
                  log_automation_     show_automation_ results_to_cloud
                  finish              notification     (in try/except)
                  (SQLite from [tk])
                       │
                       └─ self.after(0, ...) for cloud sync (try blocks)

   PARALLEL THREAD (also spawned at line 379):
   <Mn: _marker_keeper closure>    src/app/app_automation.py:318-379
        │   [Mn] runs for the entire automation duration
        ├─ connect_driver_no_dialog (BrowserManager) → SEPARATE CDP session
        │   (own session for Chrome/Edge; shared for Firefox)
        ├─ while worker_thread.is_alive() and key in active_automations:
        │     ├─ resolve_automation_tab (one switch_to.window — STEALS FOCUS once)
        │     ├─ apply_automation_marker (execute_script — no focus steal)
        │     └─ keep_tab_active (CDP: Page.setWebLifecycleState, etc.)
        └─ if owns_session: marker_session.quit()
```

## 3. BrowserManager.driver lifecycle and concurrent automation risks

```
   [BrowserManager] (singleton, src/managers/browser_manager.py:51)
        │   __init__ [tk]:  self.driver=None, self.active_browser=None,
        │                   self._automation_tab_handle=None,
        │                   self._thread_browser_choice={},
        │                   os.environ['WDM_LOG']='0'
        │
        ├─ launch_chrome_detached [tk] ─── subprocess.Popen(chrome --remote-debugging-port=9222)
        │                                writes: self.driver (only if subsequent WebDriver())
        │
        ├─ launch_firefox_managed [tk] ── WebDriver.Firefox(options)
        │                                writes: self.driver, self.active_browser="firefox",
        │                                       self.app.driver, self.app.active_browser
        │
        └─ get_driver [tk OR Wn]  ◄── CALLED BY 44 tab run_automation_logic
                │
                │   probe (socket.create_connection, timeout=0.2):
                │     127.0.0.1:9222 → chrome available?
                │     127.0.0.1:9223 → edge available?
                │
                │   priority: thread_cache → preferred_browser → only-1 → modal dialog
                │   ▸ if 2+ browsers + no prior pick:
                │       self.app.wait_window(dialog)   ◄── BLOCKING [tk] CALL — DEADLOCKS [Wn]
                │
                ├─ returns self._connect_external(browser, port)
                │     ├─ webdriver.Chrome(options=opts, debuggerAddress="127.0.0.1:9222")
                │     ├─ webdriver.Edge(options=opts, debuggerAddress="127.0.0.1:9223")
                │     └─ self._create_driver_service (webdriver_manager OR Selenium Manager)
                │
                │   AutomationMixin.get_driver:162-163 (in start_automation_thread chain)
                │   writes mirror: self.app_state.driver, self.app_state.active_browser
                │
                ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │  TRIPLE-WRITE PROBLEM (no locking, no property):                  │
   │  self.driver                  (BrowserManager)                    │
   │  self.app_state.driver        (AppState via AutomationMixin)      │
   │  self.app.driver              (NregaBotApp via launch_firefox)     │
   │  All three are read by different consumers; sync is convention.   │
   └────────────────────────────────────────────────────────────────────┘

   _prepare_driver_tab [Wn or Mn]  (internal)
        ├─ resolve_automation_tab ◄── PIN: self._automation_tab_handle
        │     1) cached handle still in window_handles? use it
        │     2) tab on MAIN_WEBSITE_URL? pin + use
        │     3) handles[0] fallback (DOC: "unstable across CDP sessions")
        ├─ driver.switch_to.window(target)  ◄── STEALS FOCUS once
        ├─ keep_tab_active (CDP: Page.setWebLifecycleState=active,
        │                    Emulation.setFocusEmulationEnabled=true,
        │                    Emulation.setCPUThrottlingRate=1)
        └─ _inject_persistent_marker (CDP: Page.addScriptToEvaluateOnNewDocument)
              + apply_automation_marker (execute_script for favicon + title)

   _emergency_stop_all [tk]  (Stop button)
        ├─ for key in active_automations: stop_events[key].set()
        ├─ self.app_state.driver.quit()  ◄── RACE with wrapper's tab_instance.driver.quit()
        ├─ self.app_state.driver = None; self.app_state.active_browser = None
        ├─ history.log_automation_finish(status="stopped") for all
        └─ self.app_state.active_automations.clear()

   CONCURRENT-AUTOMATION HAZARDS:
     D1: Two automations both call get_driver → two WebDriver instances
         to same Chrome CDP port 9222 → second's execute_cdp_cmd fails
     D2: get_driver on [Wn] with modal-dialog branch → DEADLOCK on wait_window
     D3: _emergency_stop_all.driver.quit() races wrapper.driver.quit() [Wn]
     D5: launch_chrome then immediate get_driver → 0.2s probe fails
         (Chrome needs ~1-2s to bind 9222)
     D7: Firefox shared driver + _marker_keeper execute_script → cross-thread
         driver mutation (mostly safe for read-only JS)
```

## 4. WorkflowManager Macro Queue

```
   [MacroManagerTab.start_macro]   <tk>  (UI button)
        │   creates app_state.stop_events["macro"] = threading.Event()
        │   threading.Thread(target=workflows.process_global_queue, daemon=True).start()
        │
        ▼
   <β: process_global_queue>   src/managers/workflow_manager.py:210-349
        │
        │  iterate self.queue_items  ◄── [W1: not a snapshot — list-mutation race]
        │  for each item:
        │    if app_state.stop_events["macro"].is_set(): break
        │    if item['status'] == 'Success': continue
        │    _update_item_status(id, "Running", ...)
        │    _log(macro_tab, msg, level)
        │    │
        │    dispatch by item['type'] (big if/elif):
        │    │
        │    ├─ A) 'tab_name' + 'automation_key' present  (Add-to-Queue)
        │    │     → self._run_generic_task(tab_name, target, key)
        │    │
        │    ├─ B) "Wagelist Gen" / "wagelist_gen_send"
        │    │     → _run_generic_task("Gen Wagelist", target, "gen", ...)
        │    │     → 3s settle, then _wait_for_automation_finish("send", 1200)
        │    │
        │    ├─ C) "MR Tracking" / "mr_track"
        │    │     → _scrape_workcodes_from_active_tab(tab_name)
        │    │     → switch_to_{msr,emb_entry,zero_mr}_tab_with_data(codes)
        │    │     → _wait_for_automation_finish(wait_key, 1200)
        │    │
        │    ├─ D) "Verify Job Card" / "jobcard_verify"
        │    │     → _run_generic_task("Job Card Verify", p_name, "jobcard_verify")
        │    │
        │    └─ E) "bulk_demand"
        │          → self.run_bulk_demand_sequence(item, macro_tab)
        │
        │    _update_item_status(id, "Success"/"Failed", msg)
        │    time.sleep(3)   ◄── 3s settle between items
        │
        └─ finally:
             app.after(0, set_ui_state(False))
             app.after(0, set_status("Macro Queue Finished"))
             app.play_sound("macro_finish")


   _run_generic_task(tab_name, target, key)   [β] (synchronous within macro thread)
        │
        ├─ app.after(0, self.app.set_status, ...)
        ├─ app.after(0, self.app.show_frame, tab_name)  ◄── hop to [tk]
        ├─ time.sleep(1.5)   ◄── heuristic flush
        ├─ self._ensure_automation_stopped(key)   ◄── up to 10s poll
        ├─ self._set_target_on_tab(tab, target, entry_attr)
        │     ├─ tries tab.<entry_attr>                (CTkEntry — delete+insert)
        │     ├─ tries tab.agency_entry                (CTkEntry — delete+insert)
        │     ├─ tries tab.<entry_attr>_var            (StringVar)
        │     ├─ tries tab.<entry_attr>_menu           (CTkOptionMenu var)
        │     ├─ tries tab.panchayat_var / agency_var  (case-insensitive match)
        │     └─ all via getattr(tab, ..., None) — duck-typed
        ├─ [if key=="muster"] app.after(500, tab._auto_fill_staff)
        ├─ app.after(3000, tab.start_automation)  ◄── the 3-SECOND MAGIC DELAY
        └─ self._wait_for_automation_finish(key, timeout=900, macro_tab=macro_tab)


   _wait_for_automation_finish(key, timeout=900)   [β]
        │
        │  PHASE 1: WAIT FOR START (≤ 30s, hardcoded)
        │    for _ in range(30):
        │      if key in app.active_automations: break  ◄── [W2 race: previous run!]
        │      time.sleep(1)
        │    if not started: return False
        │
        │  PHASE 2: WAIT FOR FINISH (≤ timeout)
        │    while key in app.active_automations:
        │      if app_state.stop_events["macro"].is_set(): return False
        │      if time.time() - start > timeout: return False
        │      time.sleep(1)
        │    return True
        │
        └─ The single synchronization primitive between
           [β: macro thread]  ↔  [Wn: wrapper thread]
           is membership in  {app.active_automations}  (a Set[str]).


   SHARED STATE COUPLING (only one load-bearing field):
   ┌──────────────────────────────────────────────────────┐
   │  {app.active_automations}     Set[str]               │
   │  ─ written by: AutomationMixin.start_automation_     │
   │                 thread:184 (add)                     │
   │                 on_automation_finished (remove)      │
   │                 _emergency_stop_all:770 (clear)      │
   │  ─ read by:    WorkflowManager._wait_for_           │
   │                 automation_finish:42, 56              │
   │                 WorkflowManager.process_global_      │
   │                 queue (item['key'] reference)        │
   │                 AutomationMixin._marker_keeper       │
   │                 (while-condition at line 324)        │
   │  ─ no locking; CPython GIL on set ops + iteration   │
   └──────────────────────────────────────────────────────┘
```

## Summary of test coverage gaps (the four areas)

| Area | Existing tests | Coverage |
|---|---|---|
| 1. NregaBotApp / mixin coupling | `_smoke_test_tabs.py` (FakeApp, instantiation only) | ⚠️ only catches `__init__` errors; not behavior |
| 2. `start_automation_thread` + `wrapper` | none (smoke-test stub is a `pass`) | ❌ the 90-line `wrapper` body is fully untested |
| 3. `BrowserManager` driver lifecycle | none | ❌ 0/9 of the public surface is tested |
| 4. `WorkflowManager` macro queue | none | ❌ `_wait_for_automation_finish` (the load-bearing sync primitive) and the dispatch chain are untested |

**The single most important refactor opportunity *that is also testable in isolation*** (no rewrites, just additions):

- **`_wait_for_automation_finish` (`workflow_manager.py:32-67`)** is a pure function (modulo `self.app`) that could be unit-tested with a fake `app` exposing `active_automations` and `stop_events` dicts. This is the macro-to-automation synchronization primitive and the only place `WorkflowManager` and `AutomationMixin` share state.

- **`_extract_error_context` (`app_automation.py:86-137`)** is a pure function — could be unit-tested today with no mocking. It's the data backend for the admin Error Logs page.

- **`get_driver`'s 4 browser-priority branches** (`browser_manager.py:495-525`) are testable by injecting a fake `BrowserManager` with controlled state — but the current `get_driver` is 108 lines and would need to be split.

**Areas where refactoring is genuinely hard** (because the implicit contract is wide and the test surface is too narrow):
- The triple-write driver state (`self.driver` / `app_state.driver` / `app.driver`).
- The duck-typed `_set_target_on_tab` attribute-name convention.
- The "pinned tab handle" state machine (`_automation_tab_handle`).
- The 3-second `after(3000, ...)` heuristic.

These are documented *here* in the implicit-contracts section; if you ever need to change them, the safe path is "preserve the contract in tests first" before refactoring.