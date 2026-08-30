# NREGA Bot - Decisions Log

> **Intentional architectural, product, and engineering decisions.** Each entry has explicit evidence (commit hash, audit reference, or AGENTS.md statement). Do NOT infer a decision solely from existing code structure.
>
> **Audience:** Engineers and AI assistants making future changes. Cite a `DEC-*` ID when proposing work that touches the same area.
>
> **Status:** Verified against the current repository on **30 Aug 2026** at version **3.2.7**.
>
> **Format:** Each entry is `DEC-XXX - Title` with sections: Status, Decision, Date, Commit, Rationale, Alternatives, Consequences, Related files.

---

## DEC-001 - Extract `_extract_error_context` into `src/error_context.py`

**Status:** Implemented and shipped (`main`)
**Date:** 30 Aug 2026
**Commit:** `ff2d0d6` (refactor: extract error context helper)

**Decision:** Move the `_extract_error_context(e: Exception) -> Tuple[str, str, str, str]` function from `src/app/app_automation.py` to a new dedicated module `src/error_context.py`.

**Rationale:**

- `app_automation.py` was a mixin module importing tkinter, customtkinter, requests, subprocess, socket, json. It was hard to unit-test any pure function without dragging in heavy GUI/networking deps.
- The error-context helper is pure (depends only on stdlib + `src.utils.mask_pii_text`).
- Extraction enables `tests/test_error_context.py` to lock in the behavior contract.
- No circular-import risk: `src/utils.py` imports only stdlib + `appdirs`, NOT `src/app/*`.

**Alternatives considered:**

- Inline test of `_extract_error_context` inside `app_automation.py` with heavy mocking - rejected (mock maintenance burden, fragile).
- Move the helper into `src/utils.py` - rejected (utils.py is broader-purpose; this helper is specifically about automation errors).

**Consequences:**

- `app_automation.py` shrunk by 55 lines (function + deps removed).
- `src/error_context.py` added (86 lines, well-documented behavior contract).
- `tests/test_error_context.py` updated to import the extracted function from `src.error_context` instead of from `src.app.app_automation` (import-path change; the test set itself was not materially expanded by this commit).
- New code may import from `src.error_context` without cycle risk.

**Related files:**

- `src/app/app_automation.py` (function removed)
- `src/error_context.py` (new module)
- `tests/test_error_context.py` (test updated)
- `docs/PHASES.md` Phase 2A

---

## DEC-002 - Parameterize `_ensure_automation_stopped` with `max_polls`

**Status:** Implemented and shipped (`main`)
**Date:** 30 Aug 2026
**Commit:** `1eb4e07` (refactor: parameterize automation stop polling)

**Decision:** Change `_ensure_automation_stopped(key)` signature to `_ensure_automation_stopped(key, *, max_polls: int = 10)`.

**Rationale:**

- Before: hard-coded `range(10)` polling loop. Callers could not tune this for slower automations without editing the function.
- After: exposes the iteration cap as a keyword-only parameter. Default behavior preserved exactly (10 polls == 1 poll/sec for ~10 seconds).
- Allows future callers (e.g., Macro Manager sub-actions) to use a larger poll count for long-running chained automations.
- `ValueError` enforced at the boundary for `max_polls < 1` - bad inputs fail fast.

**Alternatives considered:**

- Add a separate `_ensure_stopped_with_timeout()` function - rejected (duplicate logic, two ways to do the same thing).
- Replace polling with an `Event.wait()`-based mechanism - rejected for this PR scope; flagged in `docs/PHASES.md` Phase 2 deferred as future work.

**Consequences:**

- `src/managers/workflow_manager.py` grew by 23 lines (signature + docstring).
- `tests/test_workflow_automation_sync.py` grew by 53 lines (4 characterization tests).
- 306-test baseline preserved.
- `_ensure_automation_stopped` now has a documented contract: returns `None`, wall-clock time may exceed `max_polls` seconds, polling-iteration cap only.

**Related files:**

- `src/managers/workflow_manager.py`
- `tests/test_workflow_automation_sync.py`
- `docs/PHASES.md` Phase 2B

---

## DEC-003 - Whitelist packaging for `core_{win,mac}_vX.zip`

**Status:** Implemented and shipped
**Date:** 25 Aug 2026
**Commit:** (audit Batch-1 / F1) - referenced in `docs/AUDIT_FIX_PROGRESS_25Aug2026.md`

**Decision:** Replace the previous blacklist packaging of `core_win_vX.zip` with a strict whitelist. The whitelist is the same one used by `scripts/build_update.py` for macOS.

**Rationale:**

- Old blacklist approach was one repo-topology change away from leaking `nrega-server/` service-account JSON files.
- `AGENTS.md`, `tests/`, dev scripts were all shipping to every Windows user.
- A unified whitelist ensures Win + Mac packaging contracts are identical.
- Smaller core zip = faster updates + stable hashes (only real code changes change the hash).

**Whitelist contents:**

- `main_app.py`, `lite_app.py`, `lite_loader.py`
- `requirements.txt`
- `src/`
- `config/`
- `assets/`
- `docs/changelog.json`, `docs/license.txt`

**Alternatives considered:**

- Extend the blacklist - rejected (fragile; needs to enumerate every new internal file).
- Two separate lists - rejected (drift risk; Win + Mac must match).

**Consequences:**

- `.github/workflows/release.yml` "Create Core Zip (Windows)" step rewritten.
- `scripts/_verify_whitelist_dryrun.py` added as a pre-release leak-check.
- 184 files ship; LEAK CHECK CLEAN; all must-have runtime files present.

**Related files:**

- `scripts/build_update.py` (macOS - existing)
- `.github/workflows/release.yml` (Windows - updated)
- `scripts/_verify_whitelist_dryrun.py`
- `docs/AUDIT_FIX_PROGRESS_25Aug2026.md` F1

---

## DEC-004 - Server-driven state registry (no desktop release for new states)

**Status:** Implemented and shipped
**Date:** 12 Aug 2026
**Commit:** (server-side; migration 024 - `nrega-server/migrations/024_state_registry.sql`)

**Decision:** Move per-state config (portal host, job card prefix, demand base URL, village code logic) from hard-coded desktop constants to a server-managed `portal_states` table with admin CRUD at `/admin/portal-states`.

**Rationale:**

- Bihar was a release-blocker (needed desktop release to add a state).
- 10x user growth target (200 -> 10,000) means many more state additions.
- Server-driven config keeps desktop simple; complex state lives in `nrega-server/`.

**Mechanism:**

- Admin adds a state entry via `/admin/portal-states`.
- Desktop fetches `states[]` from `/api/app-config` on heartbeat (~2 min).
- `src/config.py::update_state_registry()` applies the registry payload.
- Built-in `STATE_PORTAL_HOSTS` / `STATE_DEMAND_CONFIG` / `STATE_JOB_CARD_PREFIXES` are **fallbacks** - registry overrides them.

**Alternatives considered:**

- Add states via `src/config.py` edit + desktop release - rejected (every state addition is a release, slow).
- Separate JSON file per state in repo - rejected (same problem at scale).

**Consequences:**

- New state = admin entry, no desktop release.
- Registry payloads are sanitized (strings only); invalid payloads never crash desktop.
- `get_state_portal_url()` re-hosts only `vbgramgde\d+` / `nregade\d+.dord.gov.in` hosts; report/MIS (vbgramgrep) and public (mnregaweb) hosts untouched.
- `PENDING_BILLS_CONFIG` (`src/config.py`) not yet integrated; planned.

**Related files:**

- `nrega-server/migrations/024_state_registry.sql`
- `nrega-server/app/routes/admin/states.py`
- `nrega-server/app/templates/admin/admin_portal_states.html`
- `src/config.py::update_state_registry`, `get_state_portal_url`
- `src/app/app_license.py::_ping_server_in_background`
- `docs/MEMORY.md` MEM-006

---

## DEC-005 - Use `sha256(license_key)` as server-side source token (DPDP)

**Status:** Implemented and shipped
**Date:** ~Aug 2026 (initial); reinforced 16 Aug 2026 (data-deletion/warning events)
**Commit:** (server-side; migration 028)

**Decision:** Server never stores the raw license key. It uses `sha256(license_key)` as the source token in tables like `location_data_pool.source_keys`. Desktop sha256-hashes the key before any sync.

**Rationale:**

- DPDP compliance: minimal personal data on server.
- Defense-in-depth: even if a DB is breached, raw license keys aren't there.
- Web login (frontend/auth.py) now uses signed tokens (raw key NOT in URL).

**Consequences:**

- License-key table reads/writes go through `hash_license_key()` helper.
- Server-side rate limits are keyed on the hash.
- `/api/validate` returns the same response shape regardless; client treats the response the same way.

**Related files:**

- `src/utils.py::hash_license_key`
- `nrega-server/app/repositories/location_data_repo.py`
- `nrega-server/migrations/027_location_data_pool.sql`, `028_account_notifications.sql`

---

## DEC-006 - `get_price_table(cur, table)` is the only sanctioned price read

**Status:** Implemented and shipped
**Date:** 16 Aug 2026
**Commit:** (server-side; admin Pricing page `/admin/pricing`)

**Decision:** Plan prices (first_time / renewal / storage) live in `app_settings` JSON. Always read via `get_price_table(cur, table)`. Module constants like `FIRST_TIME_PRICES` in `license_service.py` are **defaults only**.

**Rationale:**

- Admin needs to change prices without a code deploy.
- Direct use of constants would silently ignore admin changes.

**Consequences:**

- Buy page, order amount, revenue/MRR, storage API all read via the helper.
- Storage order amount is server-side authoritative; client `amount` is ignored (security fix).
- Reset button -> JSON rows deleted, defaults restored.

**Related files:**

- `nrega-server/app/services/license_service.py::get_price_table`
- `nrega-server/app/routes/admin/pricing.py`
- `nrega-server/app/routes/frontend/pages.py::buy_page`
- `docs/MEMORY.md` MEM-008

---

## DEC-007 - Refactor within user-approved scope only (Phase 2 protocol)

**Status:** Active protocol
**Date:** Aug 2026 onwards
**Commit:** (protocol, not a single commit)

**Decision:** All Phase 2 refactors follow strict protocol:

1. Characterization test locks current behavior BEFORE the refactor.
2. Single atomic commit with a clear message.
3. Recorded as a `DEC-*` entry in `docs/DECISIONS.md`.
4. Preserves the 306-test baseline.
5. Does NOT expand scope without explicit user approval.

**Rationale:**

- Audit Phase-1 fixes (Batch-1/F1..F9) were applied successfully because each was a single, scoped change.
- Phase-2 refactors (2A, 2B) followed the same pattern.

**Alternatives considered:**

- Big-bang refactor - rejected (high risk; observed in past incidents).
- Test-only-no-refactor - rejected (test suite rots without behavior changes).

**Consequences:**

- 306-test baseline is the contract; CI must pass before merge.
- Each refactor is small enough to review quickly.
- Decisions are explicit, not inferred from code.

**Related files:**

- `docs/PHASES.md`
- `docs/RULES.md` RULE-SRC-007
- `docs/RULES.md` RULE-TST-003

---

*Last updated: 30 Aug 2026 against `main @ 1eb4e07`. Add new DEC entries as future intentional decisions are made.*

---

## DEC-008 - Split AGENTS.md into 8 canonical documents

**Status:** Active (applied 30 Aug 2026)
**Date:** 30 Aug 2026
**Commit:** (no dedicated commit - this is a documentation/governance decision applied via direct file edits during the 30 Aug 2026 documentation pass; the next documentation commit should reference this DEC entry)

**Decision:** Restructure the documentation of the NREGA Bot desktop repository into 8 canonical documents with clear ownership:

- `AGENTS.md` - concise AI operating manual (visible safety reminders + workflow + doc routing)
- `docs/PRD.md` - product requirements and product intent
- `docs/ARCHITECTURE.md` - verified current technical architecture
- `docs/RULES.md` - non-negotiable engineering rules (with stable `RULE-*` IDs)
- `docs/PHASES.md` - development phases and current engineering roadmap
- `docs/DESIGN.md` - design system conventions (explicit rule vs observed convention)
- `docs/MEMORY.md` - institutional memory (with `MEM-*` IDs)
- `docs/DECISIONS.md` - intentional decisions (with `DEC-*` IDs)

**Rationale:**

- The previous single 380-line `AGENTS.md` mixed operating-manual content with deep technical detail, audit pointers, and a complete rule catalog. Critical safety reminders were easy to overlook in the wall of text.
- AI assistants and human contributors need different views: short reminders with deep-dive links (operator) vs full text with rationale (engineer).
- 8 documents with non-overlapping ownership prevents the same fact being written in 3 different places and drifting.
- Stable IDs (`RULE-*`, `MEM-*`, `DEC-*`) make citations persistent across documents and across PRs.

**Alternatives considered:**

- Keep one large `AGENTS.md` - rejected (visibility problem; safety rules get buried).
- Split into 2 docs (manual + reference) - rejected (still mixed concerns; rule catalog and memory entries need separation).
- 12+ ultra-fine-grained documents - rejected (overhead; ownership boundaries get fuzzy).

**Consequences:**

- `AGENTS.md` shrunk from ~380 lines to ~248 lines, with all critical safety rules still visible as short reminders.
- 7 new canonical docs created in `docs/`; existing audit files preserved.
- Cross-linking between documents uses stable `RULE-*` / `MEM-*` / `DEC-*` IDs.
- Any new documentation work must respect the ownership boundaries (see `docs/RULES.md` RULE-CM-002).

**Related files:**

- `AGENTS.md`
- `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/RULES.md`, `docs/PHASES.md`, `docs/DESIGN.md`, `docs/MEMORY.md`, `docs/DECISIONS.md`
- `docs/RULES.md` RULE-CM-002 (documentation ownership boundaries)
- `docs/MEMORY.md` MEM-015 (the version-drift evidence that surfaced during this same audit pass)

