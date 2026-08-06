# NREGA Bot — Comprehensive Project Analysis

> **Version:** 3.0.6  
> **Last Updated:** July 24, 2026  
> **Author:** Rajat Poddar  
> **Status:** Production

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Architecture](#3-architecture)
4. [File Inventory](#4-file-inventory)
5. [Build System](#5-build-system)
6. [Update Mechanism](#6-update-mechanism)
7. [Dependencies](#7-dependencies)
8. [Recent Changes](#8-recent-changes)
9. [How to Push a New Version](#9-how-to-push-a-new-version)

---

## 1. Project Overview

NREGA Bot is a Python-based desktop application for automating tasks on the VB-G-RAM-G government portal (MGNREGA). It helps block-level officers (PO) automate repetitive tasks like demand generation, muster roll printing, wage list processing, FTO generation, and more.

**Key Technologies:**
- **GUI:** CustomTkinter 5.x (tkinter wrapper)
- **Automation:** Selenium 4.x (Firefox managed, Chrome/Edge via DevTools Protocol)
- **Packaging:** PyInstaller (loader + core zip system)
- **Installer:** Inno Setup (Windows only)
- **PDF:** fpdf2, wkhtmltoimage
- **Excel:** openpyxl
- **Networking:** requests (Session reuse), socket (browser detection)
- **Licensing:** Custom REST API with OTP auth
- **Updates:** Smart update via ZIP + PyInstaller (loader-based)

---

## 2. Directory Structure

```
📁 Project Root/
├── 📄 main_app.py              ← Main application entry point (after loader)
├── 📄 loader.py                ← Splash screen + update checker + launcher
├── 📄 requirements.txt         ← Python dependencies
├── 📄 README.md                ← Project readme
├── 📄 .gitignore               ← Git ignore rules
├── 📄 .env                     ← Environment variables (gitignored)
│
├── 📁 src/                     ← ★ All source code
│   ├── 📁 app/                 ← Application mixin classes
│   │   ├── app_automation.py   ←   AutomationMixin (browser, threads)
│   │   ├── app_license.py      ←   LicenseMixin (activation, validation)
│   │   ├── app_navigation.py   ←   NavMixin (tab switching, buttons)
│   │   └── app_ui.py           ←   UIMixin (header, footer, sidebar)
│   │
│   ├── 📁 managers/            ← Service manager classes
│   │   ├── browser_manager.py  ←   Browser lifecycle (Chrome/Edge/Firefox)
│   │   ├── icon_manager.py     ←   Lazy icon loading/caching
│   │   ├── services.py         ←   License validation, updates, sleep
│   │   ├── sound_manager.py    ←   Sound playback (winsound/afplay)
│   │   └── workflow_manager.py ←   Macro/pipeline automation queue
│   │
│   ├── 📁 tabs/                ← ★ 46+ automation tab implementations
│   │   ├── base_tab.py         ←   BaseAutomationTab (shared scaffold)
│   │   ├── home_tab.py         ←   Home dashboard
│   │   ├── about_tab.py        ←   About / Licensing / Updates
│   │   ├── demand_tab.py       ←   Demand automation
│   │   ├── wagelist_gen_tab.py ←   Generate Wagelist
│   │   ├── wagelist_send_tab.py←   Send Wagelist
│   │   ├── mr_fill_tab.py      ←   MR Fill (Attendance)
│   │   ├── musterroll_gen_tab.py ← MR Generation
│   │   ├── fto_generation_tab.py ← FTO Generation
│   │   ├── dashboard_report_tab.py ← Dashboard Report
│   │   ├── mis_reports_tab.py  ←   MIS Reports
│   │   ├── ekyc_report_tab.py  ←   eKYC Report
│   │   ├── ... (40+ more tabs)
│   │   ├── history_manager.py  ←   Usage history tracking
│   │   ├── macro_manager_tab.py←   Macro Manager
│   │   ├── autocomplete_widget.py ← Autocomplete entry widget
│   │   ├── date_entry_widget.py   ← Date entry helper
│   │   ├── date_picker_popup.py   ← Calendar popup widget
│   │   └── professional_pdf.py    ← Professional PDF export
│   │
│   ├── 📄 config.py            ← Centralized settings, colors, automation configs
│   ├── 📄 state.py             ← AppState dataclass (45+ typed fields)
│   ├── 📄 tab_config.py        ← Tab definitions + icon mappings
│   ├── 📄 ui_components.py     ← Reusable widgets (SkeletonLoader, Toast, etc.)
│   ├── 📄 utils.py             ← Helper functions (paths, logging, config)
│   └── 📄 location_data.py     ← State → District mapping (1000+ entries)
│
├── 📁 assets/                  ← Static resources
│   ├── 📁 icons/               ←   PNG icons, emoji sets
│   ├── 📁 sounds/              ←   WAV files (click, success, error, etc.)
│   ├── 📁 fonts/               ←   TTF fonts (DejaVu Sans, Noto Sans Devanagari)
│   ├── 📁 demo/                ←   Sample CSV data files
│   ├── 📄 logo.png             ←   App logo (64×64, 80×80)
│   ├── 📄 app_icon.ico         ←   Windows app icon
│   ├── 📄 app_icon.icns        ←   macOS app icon
│   ├── 📄 jobcard.jpeg         ←   Sample jobcard photo
│   ├── 📄 wizard_image.bmp     ←   Inno Setup wizard image
│   └── 📄 wizard_small_image.bmp ← Inno Setup small wizard image
│
├── 📁 config/                  ← Runtime configuration files
│   ├── 📄 version.json         ←   Version info + changelog (read by GitHub Actions)
│   └── 📄 theme.json           ←   CustomTkinter theme definition
│
├── 📁 docs/                    ← Documentation & legal
│   ├── 📄 ARCHITECTURE_ANALYSIS.md  ← Architecture docs
│   ├── 📄 PERFORMANCE_ANALYSIS.md   ← Performance analysis
│   ├── 📄 PROJECT_ANALYSIS.md       ← ★ THIS FILE
│   ├── 📄 changelog.json            ← Historical changelog (deprecated — now in version.json)
│   ├── 📄 license.txt               ← EULA / License terms
│   ├── 📄 disclaimer.txt            ← Software disclaimer
│   ├── 📄 infobefore.txt            ← Pre-install info for Inno Setup
│   ├── 📄 Guide.txt                 ← Deployment guide
│   ├── 📄 last_conversatation.txt   ← Previous Freebuff conversation log
│   └── 📄 import_check_results.txt  ← Import verification results
│
├── 📁 scripts/                 ← Build & utility scripts
│   ├── 📄 build_windows.bat    ←   Windows build (PyInstaller + Inno Setup)
│   ├── 📄 build_macos.sh       ←   macOS build (PyInstaller + DMG)
│   ├── 📄 build_update.py      ←   Core update zip creator
│   ├── 📄 installer.iss        ←   Inno Setup installer script
│   ├── 📄 check_imports.py     ←   Import verification scanner
│   ├── 📄 extract_changelog.py ←   Changelog extraction utility
│   ├── 📄 migrate_source.py    ←   Source file migration script
│   ├── 📄 migrate_tabs.py      ←   Tab file migration script
│   └── 📄 _extract_ui.py       ←   UI extraction utility
│
├── 📁 web/                     ← Project website files (nregabot.com)
│   ├── 📄 index.html           ←   Website homepage
│   ├── 📄 about.html           ←   About page
│   ├── 📄 contact.html         ←   Contact page
│   ├── 📄 privacy.html         ←   Privacy policy
│   ├── 📄 terms.html           ←   Terms of service
│   ├── 📄 refund.html          ←   Refund policy
│   ├── 📄 how-to-use.html      ←   User guide
│   ├── 📄 versions.html        ←   Version history page
│   ├── 📄 update_nregabot.py   ←   Server-side release deployment script
│   ├── 📄 robots.txt           ←   SEO
│   └── 📄 sitemap.xml          ←   SEO
│
├── 📁 backups/                 ← Legacy backups (optional: move to docs/backups/)
│   └── 📁 tabs_backup_c7/      ←   Pre-refactoring tab backup (47 files)
│
├── 📁 .github/workflows/       ← CI/CD
│   └── 📄 release.yml          ←   Release workflow (auto-build + publish)
│
└── 📁 venv/                    ← Python virtual environment (gitignored)
```

---

## 3. Architecture

### 3.1 Application Class Hierarchy

```
NregaBotApp(ctk.CTk, LicenseMixin, NavMixin, AutomationMixin, UIMixin)
│
├── LicenseMixin (src/app/app_license.py)
│   ├── License validation + activation
│   ├── Trial registration
│   ├── Feature flag management
│   ├── Server sync (ping every 20s)
│   └── Messagebox overrides (logging)
│
├── NavMixin (src/app/app_navigation.py)
│   ├── Navigation button creation
│   ├── Tab switching (show_frame)
│   ├── Error boundary UI (tab crash recovery)
│   └── Category filtering
│
├── AutomationMixin (src/app/app_automation.py)
│   ├── Browser management delegation
│   ├── Thread dispatch (start_automation_thread)
│   └── Quick login automation
│
└── UIMixin (src/app/app_ui.py)
    ├── Header (logo, welcome, browser buttons)
    ├── Footer (status bar, performance monitor)
    └── Sidebar + content area layout
```

### 3.2 Initialization Flow

```
loader.py (splash)
  → check_for_updates()
  → extract core zip → launch main_app
  
main_app.py (NregaBotApp.__init__)
  → splash screen
  → icon manager init
  → background init thread
  → _finish_startup()
    → _create_header()
    → _create_footer()
    → _create_main_layout()
    → perform_license_check_flow()
      → check_license() → _setup_licensed_ui() OR show_activation_window()
    → fade splash → show Home
```

### 3.3 Data Flow

```
User Click → show_frame() → SkeletonLoader → load_actual_tab()
  → Tab Instance → Cached in tab_instances

Start Automation → start_automation_thread()
  → Mark tab _has_automated=True → Set stop_event → Spawn Thread
  → wrapper() runs target → finally: quit tab's driver → on_automation_finished()

Navigation (Tab A → B → A):
  → show_frame("TabA"):
    has_automated? True → DON'T destroy → tkraise()
    has_automated? False → destroy → create new
```

---

## 4. File Inventory

### 4.1 Core Source Files (src/)

| File | Lines | Purpose |
|------|-------|---------|
| `src/config.py` | ~600 | Centralized settings, COLORS dict (200+ entries), automation configs |
| `src/state.py` | ~195 | AppState dataclass with 45+ typed fields |
| `src/tab_config.py` | ~130 | Tab definitions, categories, icon mappings |
| `src/ui_components.py` | ~900 | Reusable widgets + AfterTracker + PerformanceMonitor |
| `src/utils.py` | ~160 | resource_path, config get/save, logging, parse_version |
| `src/location_data.py` | ~1000+ | State → District mapping data |
| `src/app/app_automation.py` | ~264 | AutomationMixin |
| `src/app/app_license.py` | ~640 | LicenseMixin |
| `src/app/app_navigation.py` | ~875 | NavMixin |
| `src/app/app_ui.py` | ~480 | UIMixin |
| `src/managers/browser_manager.py` | ~310 | Browser lifecycle |
| `src/managers/icon_manager.py` | ~160 | Lazy icon loading |
| `src/managers/services.py` | ~180 | License, updates, sleep |
| `src/managers/sound_manager.py` | ~80 | Sound playback |
| `src/managers/workflow_manager.py` | ~300 | Macro/pipeline queue |

### 4.2 Tab Files (src/tabs/)

46+ tab files totaling ~31,000 lines. Largest:
- `demand_tab.py` (~2,285 lines)
- `mr_tracking_tab.py` (~1,697 lines)
- `nmms_attendance_tab.py` (~1,344 lines)

### 4.3 Entry Points

| File | Purpose | When Used |
|------|---------|-----------|
| `loader.py` | Splash + update check | First launch (PyInstaller builds this) |
| `main_app.py` | Main application | Launched by loader.py after updates |

---

## 5. Build System

### 5.1 GitHub Workflow (`.github/workflows/release.yml`)

Triggers on every push to `main` + manual dispatch.

**Jobs:**
1. **get-release-info** — Reads version + changelog from `config/version.json`
2. **build-windows** — Creates Loader EXE + Core ZIP
   - `scripts\build_windows.bat` → PyInstaller (loader.py) → Inno Setup (installer.iss)
   - Core Zip: copies repo → compile .pyc → zip (skips .py, .exe, .bat, etc.)
3. **build-linux** — Creates portable tar.gz via PyInstaller
4. **publish-release** — Uploads artifacts + `config/version.json` to GitHub Release

### 5.2 Build Artifacts

| Artifact | Platform | Created By |
|----------|----------|------------|
| `NREGABot-vX.X.X-Setup.exe` | Windows | Inno Setup (via `scripts/installer.iss`) |
| `core_win_vX.X.X.zip` | Windows (update) | Python script in release.yml |
| `NREGABot-vX.X.X-Linux.tar.gz` | Linux | PyInstaller `--onefile` |

### 5.3 Key Build Parameters

**PyInstaller `--add-data` flags:**
```
--add-data="assets:assets"       ← Icons, sounds, fonts
--add-data="config:config"       ← theme.json
--add-data="src:src"             ← All source code
--add-data="web:web"             ← Website files (Linux build only)
--add-data="docs/changelog.json:docs/"  ← Changelog
--add-data=".env:."              ← Environment (SENTRY_DSN)
```

**PyInstaller `--hidden-import` / `--collect-submodules`:**
```
--hidden-import=main_app
--collect-submodules=src.tabs    ← All 46+ tab modules
--collect-all customtkinter
--collect-data fpdf
--hidden-import=selenium, webdriver_manager, pandas, PIL, requests, fpdf, ...
```

---

## 6. Update Mechanism

### 6.1 Update Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        LOADER FLOW                               │
│                                                                  │
│  loader.exe starts → checks nregabot.com/version.json            │
│       ↓                                                          │
│  New version? → Download core_win_vX.zip from URL                │
│       ↓                                                          │
│  Extract to app_live/ → sys.path.insert(0, app_live/)            │
│       ↓                                                          │
│  import main_app → main_app.run_application()                    │
│       ↓                                                          │
│  main_app.py does: from src import config → finds src/ package   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    IN-APP SMART UPDATE                            │
│                                                                  │
│  Running app → services.py checks {website}/version.json         │
│       ↓                                                          │
│  New version? → Download core_win_vX.zip                         │
│       ↓                                                          │
│  _apply_smart_update() → extract → xcopy over old files          │
│       ↓                                                          │
│  New main_app.py + new src/ directory copied                     │
│  Old root files (config.py, etc.) remain but unused              │
│       ↓                                                          │
│  App restarts → new code runs from new structure                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Update Server

- **URL:** `https://nregabot.com/version.json`
- **Checked by:** `loader.py` (startup) and `services.py` (in-app)
- **Format:** Contains `latest_version`, `download_url_windows/macos`, `core_update` object
- **Deployment:** `web/update_nregabot.py` script syncs GitHub release assets to NAS

### 6.3 Core Zip Contents

The core zip (`core_win_vX.X.X.zip`) contains only runtime files:
- Compiled `.pyc` files (source `.py` files excluded for security)
- All `src/` modules
- `assets/` (icons, sounds, fonts)
- `config/` (theme.json)
- `main_app.pyc`, `loader.pyc`

**Excluded:**
- `web/`, `docs/`, `scripts/` — not needed at runtime
- `.py` files — replaced by compiled `.pyc`
- `.exe`, `.bat`, `.sh`, `.iss` — build artifacts

---

## 7. Dependencies

### 7.1 Python Packages (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| `customtkinter` | Modern UI framework (tkinter wrapper) |
| `PIL/Pillow` | Image loading for icons |
| `selenium` | Browser automation |
| `webdriver_manager` | Auto-download Chrome/Edge/Firefox drivers |
| `requests` | HTTP client for licensing + updates |
| `openpyxl` | Excel file creation/reading |
| `fpdf2` | PDF generation |
| `python-dotenv` | `.env` file loading |
| `getmac` | Machine ID for licensing |
| `babel` | Number formatting |
| `tkcalendar` | Date picker widget |
| `packaging` | Version comparison |
| `appdirs` | User data directory resolution |

### 7.2 System Dependencies

| Tool | Platform | Purpose |
|------|----------|---------|
| Inno Setup 6 | Windows | Installer creation |
| create-dmg | macOS | DMG creation |
| Chrome/Edge/Firefox | All | Browser automation targets |

---

## 8. Recent Changes

### 8.1 File Reorganization

All source files moved from root-level to `src/` subdirectories:

| Old Location | New Location |
|-------------|-------------|
| `app_automation.py`, `app_license.py`, etc. | `src/app/` |
| `browser_manager.py`, `services.py`, etc. | `src/managers/` |
| `tabs/*.py` | `src/tabs/` |
| `config.py`, `state.py`, `utils.py`, etc. | `src/` root |
| `logo.png`, `jobcard.jpeg`, `wizard_*.bmp` | `assets/` |
| `theme.json`, `version.json` | `config/` |
| `license.txt`, `changelog.json`, etc. | `docs/` |
| `build_windows.bat`, `installer.iss`, etc. | `scripts/` |

### 8.2 Import Updates

All imports updated to use `src.` prefix:
```python
# Before:
from config import COLORS
from ui_components import SkeletonLoader
from tabs.demand_tab import DemandTab

# After:
from src import config
from src.ui_components import SkeletonLoader
from src.tabs.demand_tab import DemandTab
```

### 8.3 Build Script Fixes

| File | Fix |
|------|-----|
| `.github/workflows/release.yml` | Paths to `config/version.json`, `scripts\build_windows.bat`, PyInstaller flags |
| `scripts/build_windows.bat` | `--add-data` paths, installer.iss path |
| `scripts/build_macos.sh` | src/config.py, tabs loop, hidden imports |
| `scripts/installer.iss` | Wizard images → assets/, license → docs/ |
| `.gitignore` | Removed `scripts/` entry |

---

## 9. How to Push a New Version

### Step 1: Update Version

Edit `config/version.json`:
```json
{
  "latest_version": "3.0.7",
  "core_update": { "version": "3.0.7", ... },
  "changelog": { "3.0.7": [ "🚀 Your changes here" ] }
}
```

### Step 2: Update Source Version

Edit `src/config.py`:
```python
APP_VERSION: str = "3.0.7"
```

### Step 3: Update Installer Fallback

Edit `scripts/installer.iss`:
```ini
#define AppVersion "3.0.7"
```

### Step 4: Commit & Push

```bash
git add .
git commit -m "Release v3.0.7"
git push origin main
```

GitHub Actions will automatically:
1. Read version from `config/version.json`
2. Build Windows Loader EXE + Core ZIP
3. Build Linux portable tar.gz
4. Create GitHub Release with all artifacts + version.json

### Step 5: Deploy to Update Server

Run `web/update_nregabot.py` to sync release assets to the NAS, or manually:
1. Download `core_win_v3.0.7.zip` from GitHub Release
2. Upload to your update server
3. Update `version.json` on `nregabot.com` with new download URLs

---

## Appendix: Key URLs

| URL | Purpose |
|-----|---------|
| `https://nregabot.com` | Main website + `version.json` |
| `https://nregabot.com` | License validation API |
| `https://github.com/your-org/nregabot` | Source code + Releases |

## Appendix: Security Notes

- `.env` contains `SENTRY_DSN` for error tracking (gitignored)
- License keys are validated server-side
- Core zip excludes `.py` source files (compiled to `.pyc` for obfuscation)
- No hardcoded credentials in source code
