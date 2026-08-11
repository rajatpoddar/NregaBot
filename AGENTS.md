# AGENTS.md — NREGA Bot (READ THIS FIRST)

> **AI operating manual.** Jab bhi naya session/chat start ho, ye file **PEHLE** padho —
> isi se poora context 2 minute mein mil jayega. Deep dive ke liye: `README.md` →
> **🧑💻 Developer Guide** section (full architecture). Dono dev-only hain —
> `scripts/build_update.py` ke whitelist (`src/`, `config/`, `assets/`, `docs/`) mein
> nahi hain, isliye core zip mein ship nahi hote.

---

## 1. What is this? (30-second answer)

**Python desktop automation tool** (CustomTkinter GUI + Selenium) jo Indian govt.
**MGNREGA / VB-G-RAM-G portal** par data-entry automate karta hai: forms bharta hai,
reports scrape karta hai, Excel/PDF reports banata hai. Target users: Gram Rozgar
Sevaks, Panchayat Secretaries, BDO offices.

- **~55 tabs** in `src/tabs/`, har tab ek portal automation task.
- **5 languages:** English, हिन्दी, ಕನ್ನಡ, বাংলা, Hinglish (`src/locales/*.json`).
- **Delivery model:** PyInstaller build sirf `loader.py` bundle karta hai; app code
  `core_{win,mac}_vX.zip` ke roop me ships hota hai (SHA-256 verified hotfixes).

---

## 1.5. ⚠️ TWO SEPARATE GIT REPOS — DONO ALAG HAIN!

Ye project **do alag git repos** hai. Galti se galat repo me commit/deploy karna = bada nuksan. Har git command se pehle **cwd check karo**:

| Repo | Folder | Remote | Branch | Deploy |
|---|---|---|---|---|
| **Desktop app** | `.` (root) | `https://github.com/rajatpoddar/NregaBot.git` | `main` | GitHub Actions: push to `main` → release.yml builds + publishes |
| **Server (Flask)** | `nrega-server/` | `ssh://rajat@192.168.29.101:/volume1/docker/nrega-server.git` (self-hosted NAS git) | `master` | NAS par `deploy.sh` / `deploy_quick.sh` (docker-compose) |

- **Nested repo, submodule NAHI:** `nrega-server/` ka apna `.git` hai; main repo use ignore karta hai (`.gitignore` line ~43). Dono ke commits/status/branches bilkul alag hain. `git status` root me = sirf desktop app ka status.
- **Server commands:** hamesha `git -C nrega-server <cmd>` ya `cd nrega-server && git <cmd>` use karo — kabhi root se `git add nrega-server/...` mat karo (ignore hai, kuch nahi hoga).
- **Parallel development:** desktop changes → GitHub push; server changes → NAS push + deploy. Dono independently ship hote hain, ek dusre par block nahi.
- **Server local dev:** `nrega-server/run_local.sh` (Flask). Server deploy flow: `deploy.sh` / `deploy_quick.sh`.
- **Server credentials:** `nrega-server/` me service-account JSON files hain — ye kabhi main repo/GitHub par mat bhejna!

---

## 2. Architecture (10-second map)

```
loader.py ──splash + download core zip──▶ main_app.py (NregaBotApp) ──▶ src/
```

| Piece | File | Role |
|---|---|---|
| App class | `main_app.py` | `NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)`, single-instance (port 60123). Lite: `lite_app.py` (port 60124). |
| State | `src/state.py` | `AppState` dataclass. Tabs use `self.app.<attr>` — backward-compat props delegate to `app_state`. |
| Mixins | `src/app/app_ui.py` | Header, footer, status label, running-automation indicator. |
| | `src/app/app_navigation.py` | Sidebar, category filter, **lazy tab loading** (`show_frame()`). |
| | `src/app/app_automation.py` | `start_automation_thread(key, target, args)`, STOP ALL, WhatsApp notify, `AUTOMATION_DISPLAY_NAMES`. |
| | `src/app/app_license.py` | License validation/activation/expiry, feature flags. |
| Managers | `src/managers/services.py` | License check `/api/validate`, update check, machine-id, prevent-sleep. |
| | `src/managers/browser_manager.py` | Chrome (debug port 9222)/Edge/Firefox + Selenium driver. |
| | `src/managers/workflow_manager.py` | **Macro queue** — multiple tabs sequentially. |
| Tabs | `src/tabs/base_tab.py` | `BaseAutomationTab` — log area, Start/Stop/Retry, treeview export (CSV/Excel/PNG), `safe_after()`, `_is_alive()`. |
| | `src/tab_config.py` + `lite_tab_config.py` | Tab registration via `_lazy_import(class, module)`. **New tab yahan add hota hai.** |
| Config | `src/config.py` | `APP_VERSION`, `COLORS` (central palette, `(light, dark)` tuples), per-automation config dicts (URLs/form defaults). |
| Utils | `src/utils.py` | `resource_path()`, `get_report_path()` (`~/Downloads/NregaBot/Report {FY}/<Category>/`), `get_logger()`, `get_config()/save_config()`. |
| i18n | `src/i18n.py` + `src/locales/*.json` | Translations — user-facing text hard-code kabhi nahi. |
| Backend | `nrega-server/` | Flask server (license, sync, crash reports, WhatsApp API). Dev: `nrega-server/run_local.sh`. |

**Automation flow:** tab `start_automation()` → `self.app.start_automation_thread(key, run_automation_logic, args)` → daemon thread → `on_automation_finished()` cleanup.

## 3. Quick start (dev)

```bash
source venv/bin/activate && python main_app.py   # run full app
venv/bin/python _smoke_test_tabs.py              # instantiate ALL tabs (catches pack/grid Tcl errors) — tab change ke baad run karo
venv/bin/python scripts/check_imports.py         # compile + import everything (release se pehle)
```

## 4. Golden rules (NEVER break)

1. **Colors:** sirf `config.COLORS[...]` use karo — hard-code kabhi nahi.
2. **Threading:** worker threads se Tk widgets kabhi touch nahi — hamesha `self.app.after(0, ...)`.
3. **Driver:** tab `destroy()` me `driver.quit()` kabhi nahi — cleanup `start_automation_thread()` wrapper `finally` me hota hai.
4. **Lazy imports:** tabs me selenium/pandas top-level import nahi (startup slow ho jata hai) — function-level imports rakho. `base_tab.py` me selenium module-level isliye hai kyunki wahi base hai.
5. **New pip dep:** loader hi PyInstaller entry hai → har nayi dep ko `--hidden-import=` **DONO** `scripts/build_windows.bat` + `scripts/build_macos.sh` me add karo, warna release me `ModuleNotFoundError` (see "humanize incident" in README Developer Guide). Where feasible, source-level fallback bhi add karo.
6. **Logging:** `get_logger()` use karo; user-facing logs me `print` nahi (sirf debug me).
7. **New tab:** `src/tab_config.py` me register karo (unique `automation_key`) + `AUTOMATION_DISPLAY_NAMES` (`src/app/app_automation.py`) me friendly name. Lite tabs → `lite_tab_config.py`.
8. **UI reuse:** naye widget banane se pehle `src/ui_components.py`, `src/tabs/autocomplete_widget.py`, `src/tabs/date_picker_popup.py` check karo — don't re-invent.

## 5. Common tasks → where to edit

| Task | Files |
|---|---|
| Footer / status / running indicator | `src/app/app_ui.py`, `src/app/app_automation.py`, `lite_app.py` |
| Add/change a portal automation tab | `src/tabs/<tab>_tab.py` + `src/tab_config.py` (+ `src/config.py` for URLs) |
| Sidebar category or tab | `src/app/app_navigation.py`, `src/tab_config.py` |
| License / activation | `src/app/app_license.py`, `src/managers/services.py` |
| Update flow | `loader.py`, `lite_loader.py`, `src/managers/services.py`, `scripts/build_update.py`, `config/version.json` |
| Macro / multi-tab workflow | `src/managers/workflow_manager.py` |
| Theme / colors | `src/config.py` (`COLORS`), `config/theme.json` |
| Translations | `src/locales/*.json` (saare 5 files me key add karo; scripts: `check_missing_keys.py`, `add_missing_keys.py`) |
| Release a new version | bump `APP_VERSION` (config.py) + `config/version.json` → `scripts/build_update.py` → hash copy → push (CI builds) |

## 6. Project state (current)

- **Version:** 3.2.2 — `config/version.json` is source of truth; `src/config.py` me `APP_VERSION` (dono sync rakho).
- **Repo layout:** project root = desktop app; `nrega-server/` = Flask backend (alag deployable, has own Dockerfile).
- **`.vscode/tasks.json`:** tasks ab **manual** hain — `runOn: folderOpen` hata diya gaya hai (user demand). Folder kholte hi koi terminal nahi khulta; kabhi wapas mat add karna.
- **`config/theme.json`** + `assets/` fonts/sounds/icons — UI assets ka central home.

## 7. Delivery-model gotcha (release ke waqt yaad rakho)

Source-level changes users tak pahunchane ke liye `scripts/build_update.py` run karke
`config/version.json` ka `hash_windows`/`hash_macos` update karna padta hai (same version
+ different hash = hotfix re-download). Dev me seedha `python main_app.py` chalta hai.
