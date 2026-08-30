# NREGA Bot - Engineering Rules

> **Non-negotiable engineering rules.** These are extracted from `AGENTS.md` and validated against the current repository. Violations will break production for users - be conservative.
>
> **Audience:** Every AI assistant, contributor, or contractor touching the codebase.
>
> **Status:** Verified against the current repository on **30 Aug 2026** at version **3.2.7**.
>
> **Stable IDs:** Each rule has a `RULE-<category>-<number>` ID. Cite it in PRs and discussions; do not renumber.

Categories:
- `RULE-UI-*` - UI / Tk rules
- `RULE-SRC-*` - source-code architecture rules
- `RULE-LOC-*` - localization rules
- `RULE-REL-*` - release / update pipeline rules
- `RULE-SEC-*` - security / credential rules
- `RULE-CI-*` - two-repo / CI rules
- `RULE-OPS-*` - operational rules
- `RULE-TST-*` - testing rules
- `RULE-CM-*` - Codebase Memory rules

---

## RULE-UI-001 - Never hard-code colors

Colors must come from `config.COLORS[...]` only. The palette supports `(light, dark)` tuples for theme-aware rendering.

**Rationale:** Theme switching, dark/light mode, and rebrand all depend on a single source of truth. Hard-coded colors break immediately when the palette changes.

**Where:** Anywhere a `fg_color`, `text_color`, `border_color`, or `button_color` is set.

**Violation example:** `my_btn.configure(fg_color="#1F6AA5")` -> **WRONG**. Correct: `my_btn.configure(fg_color=config.COLORS["primary"])`.

---

## RULE-UI-002 - Never touch Tk widgets from worker threads

Worker threads (anywhere outside the Tk main loop) must NOT call methods on Tk/CustomTkinter widgets. All UI updates must be scheduled via `self.app.after(0, callable)` or `safe_after(0, callable)`.

**Rationale:** Tk is not thread-safe. A widget call from a worker thread will either silently fail, raise `TclError`, or corrupt internal state.

**Where:** Inside `run_automation_logic`, callback closures, retry helpers, background threads.

**Violation example:** `self.log_display.insert(...)` from inside a `try/except` in `run_automation_logic` -> **WRONG**. Correct: `self.safe_after(0, lambda: self.log_display.insert(...))`.

---

## RULE-UI-003 - Never `driver.quit()` in a tab's `destroy()`

The Selenium driver is owned by `BrowserManager` and may be shared across tabs (Firefox case especially). Cleanup happens in `start_automation_thread()`'s wrapper `finally:` block, NOT in `destroy()`.

**Rationale:** A tab can be destroyed by `show_frame()` while another tab is still using the shared driver. Quitting in `destroy()` would kill the active automation.

**Where:** Any `destroy()` override in a tab, any Tk `Widget.__del__` shim.

---

## RULE-UI-004 - Use `_has_automated` flag to keep tabs alive

Every automation tab sets `tab_instance._has_automated = True` when it starts (handled by `start_automation_thread`). `show_frame()` must NOT destroy a tab whose `_has_automated` is True (otherwise log/results vanish on tab switch).

**Where:** `NavMixin.show_frame()` and any tab that subclasses `BaseAutomationTab`.

---

## RULE-UI-005 - Reuse UI components before inventing new ones

Before creating a new widget, check:

- `src/ui_components.py` - toasts, badges, loading skeletons, etc.
- `src/tabs/autocomplete_widget.py` - `AutocompleteEntry` / `LiteDropdown`
- `src/tabs/date_picker_popup.py` - date selection
- `src/tabs/_imports.py` - shared tab imports

**Where:** All new UI work.

---

## RULE-SRC-001 - Lazy imports inside tabs

Tab files (`src/tabs/*_tab.py`) must NOT import selenium, pandas, requests, or other heavy deps at module top-level. Use function-level imports inside `run_automation_logic` or specific methods.

**Exception:** `base_tab.py` may import selenium module-level (it owns WebDriver interaction by design).

**Rationale:** Loading 48 tabs with heavy imports at startup takes seconds. Lazy imports keep startup under 1s.

---

**Violation example:**
```python
# In src/tabs/demand_tab.py
import pandas as pd          # WRONG
from selenium import webdriver  # WRONG
```

**Correct:**
```python
# In src/tabs/demand_tab.py
def run_automation_logic(self, ...):
    import pandas as pd
    from selenium.webdriver.common.by import By
    ...
```

---

## RULE-SRC-002 - Tabs register via `tab_config.py` and unique `automation_key`

Every tab has a unique `automation_key` string. Registration:

1. `src/tab_config.py` (Full SKU) - via `_lazy_import(ClassName, "module.path")`.
2. `src/lite_tab_config.py` (Lite SKU) - if also in Lite.
3. `AUTOMATION_DISPLAY_NAMES` in `src/app/app_automation.py:35` - friendly name shown in footer.

**Where:** All new tabs.

**Rationale:** Lazy imports via the factory keep startup fast; `AUTOMATION_DISPLAY_NAMES` ensures the "Running: ..." indicator is human-readable.

---

## RULE-SRC-003 - Use `get_logger()` for user-facing logs

All user-facing logs go through `get_logger()` from `src/utils.py`. Never `print()` for user-visible output; `print()` is debug-only.

**Where:** Any log message shown to the user in the tab's log area or toast.

---

## RULE-SRC-004 - Report paths via `get_report_path()`

Reports go through `src.utils.get_report_path(category, fin_year)` -> `~/Downloads/NregaBot/Report {FY}/<Category>/`. Do NOT hard-code user paths.

**Rationale:** Cross-platform (Windows / macOS / Linux), respects user's home directory, audit-friendly.

---

## RULE-SRC-005 - New pip dependency must update BOTH build scripts

The loader (`loader.py`) is the PyInstaller entry; app code ships as source. Any new pip dependency must be added as `--hidden-import=` in:

- `scripts/build_windows.bat`
- `scripts/build_macos.sh`
- `.github/workflows/release.yml` (Linux build)

Forgetting this = `ModuleNotFoundError` in production (see "humanize incident" in README Developer Guide).

Where feasible, add a source-level fallback so the app degrades gracefully if the dep is missing.

**Where:** Adding any pip dependency to `requirements.txt`.

---

## RULE-SRC-006 - `license.dat` writes go through `save_license_dat()` only

`src/utils.py::save_license_dat(data: dict)` is the **only** sanctioned writer for `license.dat`. It enforces:

- UTF-8 encoding
- Owner-only file permissions (chmod 600)

Never write `license.dat` directly via `open(get_data_path("license.dat"), "w")` from app code.

**Rationale:** Audit Batch-2/D4 - license.dat is the security boundary; scattered writes risk permission drift.

---

## RULE-SRC-007 - Refactor within scope only (Phase 2 protocol)

During Phase 2 (Safe Refactoring), all changes follow the user-approved scope:

- **Phase 2A:** Pure-function test foundation, bare-except sweep, repo hygiene (Batch-6 scope).
- **Phase 2B:** Parameterize automation-stop polling (DEC-002).

**Never expand scope without explicit user approval.** Each refactor must:

1. Have a characterization test (test the current behavior before changing).
2. Land as a single commit with a clear message.
3. Be recorded as a DEC-* entry in `docs/DECISIONS.md`.
4. Preserve the 306-test baseline.

---

## RULE-LOC-001 - Generated locale JSON is CI-controlled

`src/locales/kn.json`, `bn.json`, `hinglish.json` are **build artifacts** generated by `scripts/build_locales.py` from `scripts/translations_{kn,bn,hing}_{1..5}.py`.

**Never edit these JSON files directly** - CI runs `build_locales.py` and exits non-zero on missing/unused/placeholder-mismatch keys (release blocker).

`src/locales/en.json` and `hi.json` ARE manually edited - they are the source of truth.

---

## RULE-LOC-002 - New i18n key workflow

To add a new key:

1. Add to `en.json` AND `hi.json` (manually edited).
2. Add to the **last** part file of each generated locale:
   - `scripts/translations_kn_5.py`
   - `scripts/translations_bn_5.py`
   - `scripts/translations_hing_5.py`
3. Run `venv/bin/python scripts/build_locales.py` - exit 0 required.
4. `{placeholder}` tokens must be **identical** across all languages (CI check).

**Rationale:** This 3.2.3 release had 6 missing keys that failed CI; the workflow above prevents that class of bug.

---

## RULE-LOC-003 - User-facing text goes through `tr()`

User-visible strings must use `tr("key", default)` from `src/i18n.py` (357 call sites). Never hard-code English in UI labels.

`tr()` falls back to the default if the key is missing, so partial locale coverage doesn't crash.

---

## RULE-LOC-004 - Placeholder tokens are Jinja-style

Placeholders use `{name}` (single curly braces). All language variants must keep the same placeholder set; CI rejects mismatches.

Example: `{count}`, `{date}`, `{user_name}`.

---

## RULE-REL-001 - Core zip = whitelist only

`scripts/build_update.py` produces `core_{win,mac}_vX.zip` containing **only**:

- `main_app.py`, `lite_app.py`, `lite_loader.py`
- `requirements.txt`
- `src/`
- `config/`
- `assets/`
- `docs/changelog.json`, `docs/license.txt`

This whitelist is mirrored in `.github/workflows/release.yml` for the Windows build step.

**Excluded:**

- `AGENTS.md` (internal NAS IP, SSH topology)
- All tests, smoke-test scripts
- `nrega-server/` (service-account JSON files)
- `.env`, `*.pyc`, logs, `.DS_Store`

Pre-release leak-check: `venv/bin/python scripts/_verify_whitelist_dryrun.py` must be CLEAN + must-have files present.

**History:** Audit Batch-1/F1 fixed this. The previous blacklist approach leaked internal docs and was one CI step away from leaking `nrega-server/` service-account JSON files.

---

## RULE-REL-002 - Version bump protocol (agent does NOT fill hashes)

When releasing a new version:

1. **Patch-level bump only** (e.g., 3.2.6 -> 3.2.7). Feature bumps must be a separate plan.
2. Update `APP_VERSION` in `src/config.py`.
3. Update `latest_version`, URLs, and changelog entry in `config/version.json`.
4. **Set all three hashes (`hash`, `hash_windows`, `hash_macos`) to empty strings `""`.**
5. User runs `scripts/deploy_version.sh` which:
   - Triggers CI Windows/Linux build
   - Auto-fills `hash_windows` from GitHub release
   - Runs `build_macos.sh` to produce `hash_macos`
   - Uploads core zips to NAS

**The agent NEVER fills hashes.** The agent NEVER runs `build_update.py` or `build_macos.sh`. These are deploy-only steps performed by the user.

---

## RULE-REL-003 - Hotfix re-download mechanism

Same `latest_version` + different `core_update.hash` triggers re-download. Used for emergency patches without bumping the user-visible version.

---

## RULE-REL-004 - Boot-counter rollback

The `get_boot_count()` helper in `src/utils.py` increments on each launch. After N failed boots, `install_crash_reporter()`-based rollback restores the last known-good core zip. The agent MUST NOT disable this mechanism.

---

## RULE-SEC-001 - PII is masked in three layers

Defense-in-depth for Aadhaar/mobile/IFSC/account numbers:

1. **Logger formatter** (`src/utils.py::_PiiMaskingFormatter`) masks before write.
2. **Network payload** masks before sending to server.
3. **Server-side** masks again before storage.

Any new logging path that touches user data MUST go through `mask_pii_text()` from `src/utils.py`.

---

## RULE-SEC-002 - License keys hashed client-side

License keys are sha256-hashed before any sync (`src/utils.py::hash_license_key` or equivalent). Server stores only the hash as the source token (e.g., `location_data_pool.source_keys`). Raw key must NEVER be persisted server-side.

---

## RULE-SEC-003 - No secrets in repo

`.env`, `.env.dev`, `firebase-service-account.json`, `google-sheets-service-account.json` are git-ignored at the desktop root. `nrega-server/` keeps its own `.env` and service-account JSON - **never** commit them.

The `EVO_*` API fallbacks were REMOVED in audit F4 - hard-coded API key fallbacks are forbidden.

---

## RULE-SEC-004 - Update URLs must be HTTPS

The loader enforces HTTPS for update URLs (audit F3). Plain HTTP update URLs are rejected.

---

## RULE-CI-001 - Two separate git repos (HARD RULE)

NREGA Bot has **two separate git repos**:

| Repo | Folder | Remote | Branch |
|---|---|---|---|
| **Desktop app** | `.` (root) | `https://github.com/rajatpoddar/NregaBot.git` | `main` |
| **Server (Flask)** | `nrega-server/` | `ssh://rajat@192.168.29.101:/volume1/docker/nrega-server.git` (self-hosted NAS) | `master` |

`nrega-server/` has its own `.git`; the desktop repo's `.gitignore` excludes it (line ~43). They are NOT submodules.

**Rules:**

- Always check `pwd` before any `git` command. `git status` at root = desktop repo only.
- Server commands use `git -C nrega-server <cmd>` or `cd nrega-server && git <cmd>`.
- Never `git add nrega-server/...` from root (it's ignored; nothing happens).
- Never push to the server remote unless explicitly told.
- Server credentials live in `nrega-server/` - never send them to the desktop repo or GitHub.

---

## RULE-CI-002 - NAS commands are USER-ONLY (HARD RULE)

The agent MUST NOT execute commands on the NAS (`192.168.29.101`) - not via SSH, not via `ssh -t`, not via any wrapper.

The agent MUST NOT push to the `nrega-server` remote, even if SSH works.

**Rationale:** Incident 11 Aug 2026 - agent's SSH attempts triggered DSM Auto Block on the user's Mac IP, blocking deploys.

**What the agent does instead:** Provides copy-paste commands and waits for the user's confirmation.

**If SSH state is broken:** the agent tells the user; the user fixes NAS home perms (`chmod 755 ~`) - the agent does NOT touch NAS files.

---

## RULE-OPS-001 - `.vscode/tasks.json` is manual only

`runOn: folderOpen` was REMOVED from `.vscode/tasks.json` (per user demand). Folder open does NOT auto-start any terminal. **Never re-add** folder-open task automation.

---

## RULE-OPS-002 - Manual broadcast / templates live in admin panel

WhatsApp Broadcast, Email Templates, Reseller Requests, Rate Limits, and Find Duplicates were merged into parent pages during the 11 Aug 2026 admin cleanup (sidebar 29 -> 24 links). When adding new admin features, place links in the existing 5 sections (Overview / User Management / Messaging / Finance & Sales / Database & Ops).

---

## RULE-TST-001 - Preserve the current verified test baseline

Every PR MUST preserve the current verified test baseline. New tests are encouraged; regressions (test count decreasing) are not.

The current baseline (306 passing tests) was verified on 30 Aug 2026 against commit `1eb4e07`. The exact number is recorded in `docs/PHASES.md` (Phase 2B-baseline). The rule is "do not decrease the test count" - not "the number must stay 306 forever."

```bash
python3 -m pytest -q  # baseline 306 as of 30 Aug 2026; new tests should grow this number, never shrink it
```

---

## RULE-TST-002 - Run smoke + import checks before release

Before any release:

```bash
venv/bin/python _smoke_test_tabs.py                       # instantiate ALL tabs
venv/bin/python scripts/check_imports.py                  # compile + import everything
venv/bin/python scripts/_verify_whitelist_dryrun.py       # core zip leak check
```

All three must exit 0.

---

## RULE-TST-003 - Characterization tests for refactors

Every refactor that changes observable behavior must first have a characterization test that locks in the current behavior. The test must pass BEFORE the refactor; the refactor must keep it passing.

Reference examples: `tests/test_workflow_automation_sync.py` (DEC-002), `tests/test_wrapper_tab_driver_cleanup.py` (audit), `tests/test_automation_thread_lifecycle.py`.

---

## RULE-CM-001 - Codebase Memory for non-trivial changes

Before any non-trivial code change (refactor, new module, complex bug fix), query the Codebase Memory MCP graph:

1. `search_graph` - find related functions/classes/routes
2. `trace_path` - map caller/callee relationships
3. `get_code_snippet` - read exact source
4. `check_index_coverage` - verify candidate paths
5. `query_graph` - complex multi-hop patterns

See `docs/MEMORY.md` MEM-001 for full workflow.

---

## RULE-CM-002 - Documentation ownership

- `AGENTS.md` - AI operating manual ONLY (concise, with links)
- `docs/PRD.md` - product requirements
- `docs/ARCHITECTURE.md` - current technical architecture
- `docs/RULES.md` - this file
- `docs/PHASES.md` - current dev phase + history
- `docs/DESIGN.md` - design system conventions
- `docs/MEMORY.md` - institutional memory
- `docs/DECISIONS.md` - intentional decisions
- `docs/audits/` - historical audit reports (read-only)

Do NOT duplicate large sections across files. Do NOT turn AGENTS.md into another engineering manual.

---

## Summary table

| ID | One-line rule |
|---|---|
| RULE-UI-001 | Colors only from `COLORS[...]` |
| RULE-UI-002 | Tk widgets only from Tk thread (use `safe_after`) |
| RULE-UI-003 | Never `driver.quit()` in tab `destroy()` |
| RULE-UI-004 | Use `_has_automated` flag to keep tabs alive |
| RULE-UI-005 | Reuse UI components; check `ui_components.py` first |
| RULE-SRC-001 | Lazy imports inside tabs (selenium is base-level exception) |
| RULE-SRC-002 | Tabs register via `tab_config.py` with unique `automation_key` |
| RULE-SRC-003 | User logs via `get_logger()` (no `print`) |
| RULE-SRC-004 | Reports via `get_report_path()` |
| RULE-SRC-005 | New pip dep -> update both `build_windows.bat` + `build_macos.sh` + release.yml |
| RULE-SRC-006 | `license.dat` writes only via `save_license_dat()` |
| RULE-SRC-007 | Refactor within Phase 2 scope; test before changing |
| RULE-LOC-001 | Generated locale JSON is CI-controlled (never edit directly) |
| RULE-LOC-002 | New i18n key: en+hi json + last part files + `build_locales.py` exit 0 |
| RULE-LOC-003 | User-facing text via `tr()` |
| RULE-LOC-004 | Placeholders `{name}` identical across languages |
| RULE-REL-001 | Core zip = whitelist only |
| RULE-REL-002 | Version bump: patch only; hashes stay empty until user deploy |
| RULE-REL-003 | Same version + new hash = hotfix re-download |
| RULE-REL-004 | Boot-counter rollback: never disable |
| RULE-SEC-001 | PII masked in 3 layers (formatter, payload, server) |
| RULE-SEC-002 | License keys sha256-hashed before sync |
| RULE-SEC-003 | No secrets in repo |
| RULE-SEC-004 | Update URLs must be HTTPS |
| RULE-CI-001 | Two repos; always `pwd` before `git` |
| RULE-CI-002 | NAS commands and server pushes are USER-ONLY |
| RULE-OPS-001 | `.vscode/tasks.json` manual only (no folder-open) |
| RULE-OPS-002 | Admin sidebar links live in 5 sections |
| RULE-TST-001 | Preserve current verified test baseline (306 as of 30 Aug 2026) |
| RULE-TST-002 | Smoke + import checks before release |
| RULE-TST-003 | Characterization tests for refactors |
| RULE-CM-001 | Codebase Memory for non-trivial changes |
| RULE-CM-002 | Documentation ownership boundaries |
