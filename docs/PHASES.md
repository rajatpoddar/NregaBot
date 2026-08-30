# NREGA Bot - Development Phases

> **Source of truth for the current engineering roadmap.** Architecture lives in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md); rules in [`docs/RULES.md`](RULES.md); decisions in [`docs/DECISIONS.md`](DECISIONS.md); institutional memory in [`docs/MEMORY.md`](MEMORY.md).
>
> **Audience:** Engineer + AI assistant continuing work. Each phase has explicit scope, what changed, and what was deferred.
>
> **Status:** Verified against the current repository on **30 Aug 2026** at version **3.2.7** on commit `1eb4e07`.

---

## Phase 1 - Characterization

The first phase built a test foundation that locks in current behavior BEFORE any refactoring. It is split into sub-phases.

### Phase 1A - Pure-function test foundation (Batch-6 / T1)

**Date:** Aug 2026 (CI hygiene batch).
**Commit range:** Batch-6 follow-ups; the test files themselves landed around `ceb3f66` (feat: Enhance CI checks and code hygiene).

**Scope:**

- 36 new unit tests in `tests/test_utils_pure.py` + `tests/test_location_merge.py`.
- Coverage of pure functions in `src/utils.py`: `parse_version`, `current_financial_year`, `truncate_workcode`, `mask_pii_text`.
- Coverage of `src/location_sync.py::apply_server_data`: missing-only merge invariant, idempotency, partial-village merge, case-insensitive dedup.
- Coverage of `src/tabs/demand_tab.py::_get_village_code`: JH slash-first semantics + RJ last-3.

**Result:** 56/56 passing (after Batch-6).

---

### Phase 1B-A - AppState dataclass + backward-compat properties

**Date:** Aug 2026 (before Batch-6).
**Scope:** Centralized application state into a single `AppState` dataclass (`src/state.py`). Backward-compatible properties on `NregaBotApp` delegate to `app_state` so existing `self.app.<attr>` tab code works unchanged.

UI widget references were deliberately kept as direct attributes on `NregaBotApp` (per `state.py:22-25`).

---

### Phase 1B-B - Bare-except sweep (Batch-6 / T2)

**Date:** Aug 2026.
**Scope:** 44 bare-`except:` -> `except Exception:` across 40 tabs + loader x2 + main_app + ui_components. Bare except swallowed `KeyboardInterrupt`/`SystemExit`; specific handling now lets signals through.

**Verified:** grep count -> 0 bare-excepts in tabs; `py_compile` 13 files OK.

---

### Phase 1B-C - CI gate expand (Batch-6 / T3)

**Date:** Aug 2026.
**Commit:** `ceb3f66` (feat: Enhance CI checks and code hygiene).

**Scope:** CI ruff gate expanded from `F821` to `F821,E722`. `requirements-dev.txt` pins `ruff==0.16.4`; CI uses the same version. Baseline verified-clean before gate expansion.

---

### Phase 1B-D - Repo hygiene (Batch-6 / H1-H2)

**Date:** Aug 2026.
**Scope:**

- `docs/import_check_results.txt` untracked (was in `.gitignore` but tracked - phantom "M" status fixed).
- 0-byte `persistent_server2.py` deleted.
- `_audit_tab_layout.py` moved to `scripts/dev/` (git mv - history preserved).
- 6 empty root logs deleted.

---

### 303-test milestone

**Date:** 25 Aug 2026.
**Commit:** `d686262` (feat: Implement audit fixes for security and packaging improvements).

**Scope:** Cumulative test count after audit Batch-1 fixes (F1-F9 applied per `docs/AUDIT_FIX_PROGRESS_25Aug2026.md`). Audit fix-related tests plus pre-existing tests brought total to ~303.

**Audit Phase-1 fixes applied (per `docs/AUDIT_FIX_PROGRESS_25Aug2026.md`):**

| Fix | Severity | Status |
|---|---|---|
| F1 - Windows core zip -> whitelist | P0 | Applied |
| F2 - Loader: downgrade refusal + empty-hash fail-safe + HTTPS | P1 | Applied |
| F3 - About-tab updater HTTPS URL guard | P1 | Applied |
| F4 - Hard-coded `EVO_*` fallbacks removed | P1 | Applied |
| F5 - `.env` bundling removed from build scripts | P2 | Applied |
| F6 - CI `.env` creation steps removed | P2 | Applied |
| F7 - Demand tab `'e' in locals()` bug fixed | P1 | Applied |
| F8 - Usage-stats sync undefined-variable crash | P3 | Applied |
| F9 - MR Fill wrong-workcode protection | P1 | Applied |
| F10 - `license.dat` chmod 600 | P2 | **Deferred** (see Phase 2 deferred items) |

---

## Phase 2 - Safe Refactoring

The current active phase. **All changes preserve the 306-test baseline.** Each refactor ships with:

1. A characterization test (locks current behavior).
2. A single atomic commit.
3. A `DEC-*` entry in `docs/DECISIONS.md`.

### 2A - Extract error context helper

**Commit:** `ff2d0d6` (refactor: extract error context helper)
**Author:** Rajat Poddar, 30 Aug 2026
**Files touched:**

- `src/app/app_automation.py` -55 lines (function removed)
- `src/error_context.py` +86 lines (new module)
- `tests/test_error_context.py` adjusted

**Scope:** Extracted `_extract_error_context(e)` from `src/app/app_automation.py` (which previously imported tkinter, customtkinter, requests, subprocess, socket, json) into a pure helper `src/error_context.py`. This enables unit-testing without pulling in heavy GUI/networking deps.

**Behavior contract preserved verbatim from `app_automation.py:86-137`:**

- `error_type` - exception class name.
- `error_msg` - `f"{error_type}: {str(e)}"` PII-masked, [:600].
- `error_source` - last 2 user-code frames, formatted `file.py:line:fn -> file.py:line:fn`.
- `error_traceback` - full traceback PII-masked, [:4000].

**No circular-import risk:** `src/utils.py` imports only stdlib + `appdirs`; does NOT import `src/app/*`.

**See:** [`docs/DECISIONS.md`](DECISIONS.md) DEC-001.

---

### 2B - Parameterize automation stop polling

**Commit:** `1eb4e07` (refactor: parameterize automation stop polling)
**Author:** Rajat Poddar, 30 Aug 2026
**Files touched:**

- `src/managers/workflow_manager.py` (max_polls keyword arg added to `_ensure_automation_stopped`)
- `tests/test_workflow_automation_sync.py` +53 lines (characterization tests)

**Before:** `_ensure_automation_stopped(key)` had a hard-coded `range(10)` polling loop. Callers could not tune this for slower automations without editing the function.

**After:** `_ensure_automation_stopped(key, *, max_polls: int = 10)` exposes the iteration cap as a keyword-only parameter. Default behavior preserved exactly (10 polls == 1 poll/sec for ~10 seconds).

**Behavior contract:**

- `max_polls < 1` raises `ValueError` (contract enforced at the boundary).
- Function returns `None` regardless of whether the key disappears (caller proceeds either way).
- Wall-clock time may exceed `max_polls` seconds on a slow host; the docstring calls this out: "This is **not** a strict wall-clock timeout - it is a polling-iteration cap."

**Characterization tests added (`test_workflow_automation_sync.py`):**

- Default `max_polls=10` preserves prior behavior.
- Custom `max_polls` values change the loop bound.
- `ValueError` for `max_polls < 1`.
- Key not in `active_automations` short-circuits.

**See:** [`docs/DECISIONS.md`](DECISIONS.md) DEC-002.

---

### 2B-baseline - 306-test baseline

**Current test baseline (verified 30 Aug 2026 on commit `1eb4e07`):**

```
python3 -m pytest -q
306 passed in ~27s
```

**Test files (12 modules):** see `docs/ARCHITECTURE.md` section 16 for the table.

---

## Phase 2 deferred items (KNOWN DEFERRED, not fixed)

These items are intentionally NOT fixed in the current Phase 2 scope. They are tracked here for future planning.

### `_wait_for_automation_finish` always checks `stop_events["macro"]`

**Status:** **KNOWN DEFERRED - DO NOT MARK FIXED.**

**Where:** `src/managers/workflow_manager.py:57` (and any other reference).

**Issue:** `_wait_for_automation_finish(key)` checks `self.app.stop_events.get("macro")` for user-stop, but this is the **macro-specific** event, NOT the per-automation event. In practice this works for Macro Manager because the macro owns the per-automation lifecycle, but it is a latent footgun if any other caller uses `_wait_for_automation_finish`.

**Current tests:** `tests/test_workflow_automation_sync.py` characterization tests document the existing behavior.

**Why deferred:** The Macro Manager is the only caller and changing this affects Macro behavior in subtle ways. Needs a behavioral decision (per-key vs macro-global) before refactor.

**Future fix sketch:**

- Rename `_wait_for_automation_finish(key, ..., stop_event=...)` to accept an explicit stop event.
- Macro Manager passes `stop_events["macro"]`; individual tabs could pass their own event.
- Add a regression test for the new boundary.

---

### Other deferred items (from audit + MEMORY.md)

| Item | Source | Why deferred |
|---|---|---|
| `license.dat` chmod 600 across 7 sites | AUDIT_FIX_PROGRESS F10 | Touches 3 files; needs user-only deploy coordination |
| 3-second `time.sleep(3)` between macro actions | Audit | Needs event-based replacement; design TBD |
| ed25519-signed core zips | Audit Phase 2 #8 | Larger infra change; needs CI signing key |
| MR Fill date-error vs already-filled disambiguation | Audit Phase 2 #9 | Tab-level behavior change |
| Per-tab retry classification docs | Audit Phase 2 #13 | Documentation work, not refactor |
| Unify Lite/Main update logic in one module | Audit Phase 4 #19 | Larger architecture work |

---

## Future phases (PLANNED only)

The following are explicitly listed as PLANNED in `docs/PRD.md` / `docs/SCALING_PLAN_200_to_10000.md`. **Do NOT start work without an explicit user decision.**

| Phase | Source | Status |
|---|---|---|
| Churn prevention (renewal reminders) | SCALING_PLAN section 11 Aug 2026 | Done server-side (migration 025) |
| Trial funnel analytics | SCALING_PLAN section 11 Aug 2026 | Done (`/admin/funnel` page) |
| CDN / managed Postgres / canary | SCALING_PLAN section 5 | Deferred until users cross ~1000-2000 |
| Scheduled automations | SCALING_PLAN Phase 3 #18 | PLANNED |
| State-registry integration for `PENDING_BILLS_CONFIG` | PHASES | PLANNED (currently manual edit) |
| Adapter to expose per-key stop event in `_wait_for_automation_finish` (currently hardcoded to `stop_events["macro"]`) | PHASES | PLANNED (see deferred items) |

---

## Summary

- **Phase 1 (Characterization):** Test foundation + bare-except sweep + CI gate + repo hygiene + 303-test milestone after audit Batch-1 fixes.
- **Phase 2A (Current):** `ff2d0d6` - extract error context helper.
- **Phase 2B (Current):** `1eb4e07` - parameterize automation stop polling.
- **Baseline:** 306 tests passing.
- **Deferred:** `_wait_for_automation_finish` stop_event semantics; license.dat chmod 600 across 7 sites; 3-second sleep between macro actions.
