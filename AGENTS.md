# AGENTS.md - NREGA Bot (READ THIS FIRST)

> **AI operating manual.** Jab bhi naya session/chat start ho, ye file **PEHLE** padho.
> Detailed explanations live in [`docs/`](docs/) - is file ka kaam hai:
> 1. Project identity in 30 seconds
> 2. Two-repo warning (CRITICAL)
> 3. Non-negotiable safety rules (visible reminders)
> 4. Workflow pointers (with links to canonical docs)
>
> **Status:** Verified 30 Aug 2026 against version **3.2.7** (see `config/version.json`).

---

## 1. Project identity (30 seconds)

NREGA Bot is a **Python desktop automation tool** (CustomTkinter + Selenium) that drives the Indian government's **MGNREGA / VB-G-RAM-G portal** through the user's own browser (Chrome, Edge, or Firefox). It eliminates repetitive data entry for Gram Rozgar Sevaks, Panchayat Secretaries, and BDO offices.

- **48 tabs** in `src/tabs/` (each tab = one portal automation task)
- **5 locales:** English, Hindi, Kannada, Bengali, Hinglish
- **Delivery model:** PyInstaller builds only `loader.py`; app code ships as `core_{win,mac}_vX.zip` with SHA-256 verification
- **Full SKU:** `main_app.py` (port 60123); **Lite SKU:** `lite_app.py` (port 60124)

Deep dive: [`docs/PRD.md`](docs/PRD.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 2. TWO SEPARATE GIT REPOS - HARD RULE

Ye project **do alag git repos** hai. Galti se galat repo me commit/deploy karna = bada nuksan. Har git command se pehle **cwd check karo**:

| Repo | Folder | Remote | Branch |
|---|---|---|---|
| **Desktop app** | `.` (root) | `https://github.com/rajatpoddar/NregaBot.git` | `main` |
| **Server (Flask)** | `nrega-server/` | `ssh://rajat@192.168.29.101:/volume1/docker/nrega-server.git` (self-hosted NAS) | `master` |

- **Nested repo, submodule NAHI:** `nrega-server/` ka apna `.git` hai; main repo use ignore karta hai (`.gitignore` line ~43). `git status` root me = sirf desktop app ka status.
- Server commands hamesha `git -C nrega-server <cmd>` ya `cd nrega-server && git <cmd>` use karo.
- Server credentials `nrega-server/` me hain - kabhi main repo / GitHub par mat bhejo.
- **Deploy:** desktop = GitHub Actions (release.yml); server = NAS par `deploy.sh` / `deploy_quick.sh` (docker-compose).

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-CI-001.

---

## 3. Non-negotiable safety rules (CRITICAL REMINDERS)

These are duplicated here as visible reminders. Full text + rationale in [`docs/RULES.md`](docs/RULES.md).

### 3.1 NAS commands and server pushes are USER-ONLY

**Agent MUST NOT execute commands on the NAS.** Not via SSH, not via `ssh -t`, not via any wrapper. **Agent MUST NOT push to `nrega-server` remote**, even if SSH works.

**Rationale:** 11 Aug 2026 incident - agent's SSH attempts triggered DSM Auto Block on the user's Mac IP, blocking deploys.

**What the agent does instead:** Provides copy-paste commands; waits for user confirmation.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-CI-002.

### 3.2 Agent NEVER fills release hashes / NEVER runs `build_update.py` / `build_macos.sh`

`config/version.json` ke teeno hashes (`hash`, `hash_windows`, `hash_macos`) ko empty `""` rakhna hai. User runs `scripts/deploy_version.sh` which auto-fills.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-REL-002.

### 3.3 Core zip = whitelist only

`core_{win,mac}_vX.zip` contains ONLY: `main_app.py`, `lite_app.py`, `lite_loader.py`, `requirements.txt`, `src/`, `config/`, `assets/`, `docs/changelog.json`, `docs/license.txt`. **No** AGENTS.md, no tests, no `nrega-server/`, no `.env`.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-REL-001.

---

### 3.4 Tk thread safety

Worker threads MUST NOT touch Tk widgets. Use `self.app.after(0, callable)` or `safe_after(0, callable)`.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-UI-002.

### 3.5 Driver cleanup is owned by `start_automation_thread()` wrapper

Tabs MUST NOT call `driver.quit()` in `destroy()`. Cleanup happens in the `finally:` block of the wrapper closure.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-UI-003.

### 3.6 Lazy imports inside tabs

Tab files MUST NOT import selenium/pandas/requests at module top-level. Use function-level imports.

Exception: `base_tab.py` may import selenium module-level (it owns WebDriver interaction).

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-SRC-001.

### 3.7 Generated locale JSON is CI-controlled

`src/locales/kn.json`, `bn.json`, `hinglish.json` are build artifacts. **Never edit directly.** Edit `en.json` + `hi.json` + `translations_{kn,bn,hing}_5.py` (last part files) + run `build_locales.py`.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-LOC-001 / RULE-LOC-002.

### 3.8 `license.dat` writes only via `save_license_dat()`

`src/utils.py::save_license_dat()` is the choke point that enforces UTF-8 + chmod 600.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-SRC-006.

### 3.9 PII is masked in 3 layers (logger + payload + server)

Aadhaar / mobile / IFSC must go through `mask_pii_text()` from `src/utils.py`.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-SEC-001.

### 3.10 Refactor within user-approved scope (Phase 2 protocol)

Characterization test -> atomic commit -> DEC-* entry -> preserves 306-test baseline. Do NOT expand scope without explicit user approval.

Full rule: [`docs/RULES.md`](docs/RULES.md) RULE-SRC-007 / RULE-TST-003.

---

## 4. Mandatory coding workflow

1. **Read context first** - this file + the relevant section of [`docs/RULES.md`](docs/RULES.md) + the relevant `MEM-*` / `DEC-*` entries.
2. **Verify version** - `config/version.json::latest_version` + `src/config.py::APP_VERSION` are the source of truth.
3. **For non-trivial changes** - query Codebase Memory first (see section 5 below).
4. **For new tabs** - subclass `BaseAutomationTab`; use function-level imports; register via `_lazy_import` in `src/tab_config.py`; add key to `AUTOMATION_DISPLAY_NAMES`.
5. **For refactors** - write characterization test FIRST, then change, then verify.
6. **Run pre-flight checks**:
   ```bash
   python3 -m pytest -q                                   # 306 passing
   venv/bin/python _smoke_test_tabs.py                   # all tabs instantiate
   venv/bin/python scripts/check_imports.py              # imports + compile
   venv/bin/python scripts/_verify_whitelist_dryrun.py   # core zip leak check
   ```
7. **Never commit `nrega-server/`** from the desktop repo (it's ignored; nothing happens).

---

## 5. Codebase Memory workflow

For non-trivial work (refactor, new module, complex bug fix), query the codebase-memory-mcp graph:

1. `search_graph` - find related symbols.
2. `trace_path` - map callers / callees.
3. `get_code_snippet` - read exact source.
4. `check_index_coverage` - validate candidate paths.
5. `query_graph` - complex multi-hop patterns.
6. `get_architecture` - project summary.

**Why:** The graph has 2,509 nodes / 15,228 edges (per audit 29 Aug 2026). Grep misses implicit contracts.

Full workflow: [`docs/MEMORY.md`](docs/MEMORY.md) MEM-002.

---

## 6. Documentation routing

| Question | Document |
|---|---|
| What is this product? Who's it for? | [`docs/PRD.md`](docs/PRD.md) |
| How is it built? Where do I start? | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| What are the hard rules? | [`docs/RULES.md`](docs/RULES.md) |
| What's the current phase? What's done / deferred? | [`docs/PHASES.md`](docs/PHASES.md) |
| How does the design system work? | [`docs/DESIGN.md`](docs/DESIGN.md) |
| Historical gotchas, lessons, incidents | [`docs/MEMORY.md`](docs/MEMORY.md) |
| Intentional decisions with evidence | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Past audits / plans / analysis | [`docs/NregaBot_Architecture_Audit_2026-08-29.md`](docs/NregaBot_Architecture_Audit_2026-08-29.md), [`docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md`](docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md), [`docs/archive/`](docs/archive/) |
| Scaling roadmap (200 -> 10,000) | [`docs/SCALING_PLAN_200_to_10000.md`](docs/SCALING_PLAN_200_to_10000.md) |
| Server deploy on Synology NAS | [`docs/Guide.txt`](docs/Guide.txt) |
| EULA | [`docs/license.txt`](docs/license.txt) |
| User-facing changelog | [`docs/changelog.json`](docs/changelog.json) |

---

## 7. Essential commands

### 7.1 Run locally

```bash
source venv/bin/activate
python main_app.py                # Full SKU
python lite_app.py                # Lite SKU
```

### 7.2 Test

```bash
python3 -m pytest -q              # 306 tests passing
venv/bin/python _smoke_test_tabs.py
venv/bin/python scripts/check_imports.py
venv/bin/python scripts/_verify_whitelist_dryrun.py
```

### 7.3 Build (USER ONLY)

```bash
# User runs these; agent never does:
scripts/build_macos.sh            # macOS .dmg + core zip
scripts/build_update.py           # macOS core zip only
.git push origin main             # triggers Windows + Linux CI builds
scripts/deploy_version.sh         # auto-fills Windows hash, uploads to NAS
```

### 7.4 Git safety

```bash
pwd                              # ALWAYS - confirm cwd before git
git status                       # desktop repo (root only)
git -C nrega-server status        # server repo
# NEVER: ssh ... 192.168.29.101    # RULE-CI-002
# NEVER: git push ... nrega-server.git
```

### 7.5 Locale / i18n

```bash
venv/bin/python scripts/build_locales.py   # exit 0 required
```

---

## 8. Version truth

| File | Field | Current |
|---|---|---|
| `config/version.json` | `latest_version` | **3.2.7** |
| `src/config.py` | `APP_VERSION` | **3.2.7** |
| `README.md` | Version badge | **v3.2.7** |

If any document disagrees with the first two, **the source-of-truth files win**. Always verify before publishing claims.

---

## 9. Reference

- **Repo layout:**
  - `.` = desktop app (this repo)
  - `nrega-server/` = Flask backend (separate repo)
  - `tests/` = 12 test modules, 306 tests
  - `scripts/` = build, deploy, dev utilities (USER-ONLY for build/deploy)
  - `assets/` = icons, fonts, sounds
  - `config/` = `version.json` (source of truth), `theme.json`, `__init__.py`

- **Tabs:** `src/tabs/*_tab.py` - 48 modules, all lazy-loaded.

- **Mixins (MRO):** `ctk.CTk -> LicenseMixin -> NavMixin -> AutomationMixin -> UIMixin`.

- **Last verified:** 30 Aug 2026 against `main @ 1eb4e07`.

- **If you find a contradiction** between this file and the source code, the source code wins. Update the docs to match.
