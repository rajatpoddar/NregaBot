# NregaBot Optimization Plan
## Production-Grade Performance Enhancement for Low-End Devices

**Date:** July 24, 2026  
**Current Version:** 3.0.6  
**Total Codebase:** ~36,848 lines (Python)  
**Target:** Low-end devices (2-4 GB RAM, slower CPUs, HDD storage)

---

## 📊 Current Application Analysis

### Application Overview

| Metric | Value |
|--------|-------|
| Total Python files | 50+ |
| Largest file | `demand_tab.py` (2,283 lines) |
| `src/tabs/` total | 31,163 lines across 44 tab files |
| Heavy dependencies | PIL, openpyxl, reportlab, selenium, pandas |
| Startup imports (tab_config.py) | 44 tab classes imported at once |
| `time.sleep()` occurrences | 30+ (main thread blocking) |
| UI framework | customtkinter + tkinter |

### Performance Bottlenecks Identified

#### 🔴 Critical (High Impact)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| P1 | **Excessive `time.sleep()` blocking main thread** | Across 15+ tab files | UI freezes during automation |
| P2 | **All 44 tab classes imported at startup** | `tab_config.py` line 12-55 | ~1-2s startup delay on HDD |
| P3 | **Heavy libraries loaded at module level** | `base_tab.py`, `about_tab.py`, 20+ tabs | RAM waste if tab never opened |
| P4 | **`reportlab` & `openpyxl` imported eagerly** | 15+ tab files import at top | Each import adds 100-200ms |
| P5 | **2,283-line `demand_tab.py`** | `src/tabs/demand_tab.py` | Slow parsing, high memory |
| P6 | **1,697-line `mr_tracking_tab.py`** | `src/tabs/mr_tracking_tab.py` | Same issue |

#### 🟡 Medium Impact

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| M1 | **Redundant `self.update_idletasks()` calls** | `app_navigation.py`, `app_ui.py` | Extra CPU cycles |
| M2 | **Icon cache not cleared on theme change** | `icon_manager.py` | Memory leak edge case |
| M3 | **Thread objects held in dict after completion** | `app_state.py` line 52 | Memory leak over hours |
| M4 | **Canvas-based animations running constantly** | `ui_components.py` | Unnecessary GPU/CPU usage |
| M5 | **80+ PNG icons loaded as CTkImage** | `icon_manager.py` (50+ definitions) | Memory: ~5-10 MB for icons |

#### 🟢 Minor

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| N1 | **Empty `__init__.py` files** | Several packages | Minor import overhead |
| N2 | **Config too large** | `config.py` (100+ color values) | Marginal parse time |
| N3 | **Font files loaded repeatedly** | 6+ tabs load fonts independently | Redundant disk I/O |

---

## 🎯 Optimization Roadmap

### Phase 1: Quick Wins (Safe, No Breaking Changes)
*Estimated effort: 2-3 hours • Risk: Low*

#### ✅ [1.1] Replace `time.sleep()` with `WebDriverWait` + `after()`
- **Files affected:** All tab files with `time.sleep()`
- **Current:** `time.sleep(2)` blocks entire UI
- **Fix:** Use Selenium's `WebDriverWait` for browser waits, `self.after()` for UI delays
- **Impact:** No UI freezing during automation waits
- **Risk:** None — fully backward compatible

#### ✅ [1.2] Lazy-load heavy tab imports
- **Files affected:** `tab_config.py`
- **Current:** All 44 tabs imported when `get_tabs_definition()` is called
- **Fix:** Import only when tab is first accessed via lazy loading wrapper
- **Impact:** Startup time reduced by 40-60%
- **Risk:** Very low

#### ✅ [1.3] Cache frequently-accessed config values
- **Files affected:** `src/config.py`, `main_app.py`
- **Current:** `config.COLORS["blue_hover"]` accessed repeatedly
- **Fix:** Add config value cache with dict access
- **Impact:** Marginal CPU improvement
- **Risk:** None

### Phase 2: Structural Improvements (Medium Effort)
*Estimated effort: 4-6 hours • Risk: Low-Medium*

#### ✅ [2.1] Split `demand_tab.py` into modules
- **Current:** 2,283-line monolithic file
- **Proposed:** Split into:
  - `demand_tab.py` (UI + orchestration ~500 lines)
  - `demand_automation.py` (automation logic ~800 lines)
  - `demand_utils.py` (helpers ~400 lines)
- **Impact:** Faster parsing, easier maintenance, lower memory

#### ✅ [2.2] Split `mr_tracking_tab.py` into modules
- **Current:** 1,697-line monolithic file
- **Proposed:** Split into tracking logic + reporting + UI
- **Impact:** Same as above

#### ✅ [2.3] Centralize font loading
- **Files affected:** 6+ tabs loading NotoSansDevanagari fonts
- **Current:** Each tab loads fonts independently (disk I/O + memory)
- **Fix:** Centralized `FontManager` singleton in `src/managers/font_manager.py`
- **Impact:** Reduces font loading from 6+ redundant loads to 1

#### ✅ [2.4] Optimize `LazyIconManager` cache strategy
- **Files affected:** `src/managers/icon_manager.py`
- **Current:** Preloads 15 icons at startup, caches all
- **Proposed:** Add LRU eviction, reduce preload to 8 essential icons
- **Impact:** ~2-3 MB memory savings on low-end

### Phase 3: Advanced Optimizations (Higher Effort)
*Estimated effort: 8-12 hours • Risk: Medium*

#### ⏳ [3.1] Create Lite Mode Toggle
- **New feature:** Settings → "Low-End Device Mode"
- **When enabled:**
  - Disable animations and transitions
  - Reduce update frequency
  - Use simpler UI components (tkinter native instead of CTk)
  - Disable sound effects
  - Set GC collection interval to 2min (from 5min)
- **Impact:** Significant CPU/memory reduction

#### ⏳ [3.2] Convert heavy PDF/XLSX generation to background threads
- **Files affected:** All tabs using reportlab/openpyxl
- **Current:** PDF/Excel generation blocks UI thread
- **Fix:** Move all document generation to `threading.Thread` with progress callback
- **Impact:** UI stays responsive during exports

#### ⏳ [3.3] Implement widget pooling / recycling
- **Files affected:** Tabs with large Treeview widgets
- **Current:** Fresh widgets created each time
- **Fix:** Reuse existing widgets, just swap data
- **Impact:** Reduced widget creation overhead

### Phase 4: Lite Version (Standalone)
*Estimated effort: 16-20 hours • Risk: Medium-High*

#### 📦 [4.1] Create `nregabot_lite.py` — Stripped-down variant
- Remove non-essential tabs (feedback, about animations, onboarding)
- Remove sound system entirely
- Replace customtkinter with tkinter.ttk where possible
- Remove performance monitor
- Single-threaded automation (sequential, no parallel workflows)
- Pre-compiled (.pyc) distribution to reduce startup parsing

**Tabs to KEEP in Lite:**
1. Home (simplified)
2. Demand / Work Allocation
3. MR Gen / MR Fill / MR Tracking / MR Payment
4. eMB Entry / eMB Verify
5. WC Gen / IF Editor
6. Wage List Gen / Send
7. FTO Generation
8. Muster Roll Gen
9. Basic Reports (MIS, Dashboard)
10. Login Automation

**Tabs to REMOVE in Lite:**
- Macros & Workflows
- File Manager (web-dependent)
- About (animations, changelog)
- Onboarding Guide
- Performance Monitor
- Advanced animations & transitions

---

## 📋 Step-by-Step Implementation Tasks

### Task Status Legend
- ✅ **Pending** — Not started
- 🔄 **In Progress** — Currently being implemented
- ⏳ **Completed** — Finished and verified

### Startup Optimization

- [ ] **T1.1** Move all tab imports from `tab_config.py` to lazy-loading pattern
  - Files: `src/tab_config.py`
  - Method: Create `LazyTabLoader` class that imports on first access
  - Expected gain: 40-60% faster startup

- [ ] **T1.2** Reduce icon preload from 15 to 8 essential icons
  - Files: `src/managers/icon_manager.py`
  - Keep only: chrome, firefox, home_icon, sound_on, theme icons, nrega
  - Defer: onboarding icons, menu emoji icons (loaded when tab opens)

- [ ] **T1.3** Defer non-critical UI construction to idle time
  - Files: `main_app.py`, `src/app/app_ui.py`
  - Move footer, theme toggle, status bar to `self.after_idle()`

### Runtime Performance

- [ ] **T2.1** Replace `time.sleep()` with `WebDriverWait` in automation tabs
  - Files: `mb_entry_tab.py`, `material_entry_tab.py`, `sarkar_aapke_dwar_tab.py`, `mr_fill_tab.py`, `nmms_attendance_tab.py`, `mis_reports_tab.py`, `wagelist_send_tab.py`
  - Pattern: Replace `time.sleep(N)` with `WebDriverWait(driver, N).until(...)`
  - Expected gain: UI stays responsive, automation speed increases

- [ ] **T2.2** Lazy-load `openpyxl` and `reportlab` in all tab files
  - Files: 20+ tabs that import these at module level
  - Fix: Move imports inside methods that actually use them
  - Expected gain: ~100-200ms per tab load, ~5-10MB RAM

- [ ] **T2.3** Optimize `self.after()` timer chains
  - Files: All tabs using self.after() for periodic tasks
  - Reduce redundant after() calls, coalesce timers where possible

- [ ] **T2.4** Prune dead threads from `automation_threads` dict
  - Already partially implemented (P6 in main_app.py)
  - Ensure all tabs clean up thread references in destroy()

### Memory Optimization

- [ ] **T3.1** Add `MemoryMonitor` to detect leaks during long sessions
  - New file: `src/managers/memory_monitor.py`
  - Logs memory usage every 10 minutes, warns if >200MB growth

- [ ] **T3.2** Centralize font loading into `FontManager`
  - New file: `src/managers/font_manager.py`
  - Singleton pattern: load NotoSansDevanagari fonts once, reuse everywhere

- [ ] **T3.3** Clear icon cache on theme change
  - Files: `src/managers/icon_manager.py` (method exists, ensure it's called)
  - Verify: `LazyIconManager.clear_cache()` is called on theme switch

### UI Responsiveness

- [ ] **T4.1** Remove redundant `self.update_idletasks()` calls
  - Files: `app_navigation.py`, `app_ui.py`, `app_license.py`, `ui_components.py`
  - Keep only: one `self.update_idletasks()` after major UI construction

- [ ] **T4.2** Add `after_idle()` for low-priority UI updates
  - Replace `self.after(0, callback)` with `self.after_idle(callback)` where order doesn't matter

- [ ] **T4.3** Reduce animation frame rate on low-end detection
  - Files: `main_app.py` (loading animation), `ui_components.py`
  - Detect: if startup takes >3s, halve animation framerate

### Code Splitting

- [ ] **T5.1** Refactor `demand_tab.py` (2,283 lines)
  - Extract: `demand_automation.py` — Selenium logic
  - Extract: `demand_utils.py` — CSV parsing, data helpers
  - Keep: `demand_tab.py` — UI only (~500 lines)
  - Risk: Medium — careful dependency management needed

- [ ] **T5.2** Refactor `mr_tracking_tab.py` (1,697 lines)
  - Same pattern as T5.1
  - Extract reporting/PDF logic, automation logic

- [ ] **T5.3** Refactor `nmms_attendance_tab.py` (1,344 lines)
  - Same pattern as above

### Lite Version Creation

- [ ] **T6.1** Create `src/lite_config.py` — Lite version configuration
  - Reduced feature set, simplified UI
  - Override `config.py` values for Lite mode

- [ ] **T6.2** Create `src/app/app_lite.py` — Simplified app class
  - Extends `NregaBotApp` or standalone
  - Disables: animations, sounds, onboarding, performance monitor

- [ ] **T6.3** Build scripts for Lite distribution
  - `scripts/build_lite_windows.bat`
  - `scripts/build_lite_macos.sh`
  - Smaller executable, fewer dependencies

---

## 🔧 Technical Implementation Details

### Lazy Tab Loading Pattern

```python
# Current (eager):
from src.tabs.demand_tab import DemandTab

# Proposed (lazy):
class LazyTabLoader:
    _tab_cache = {}
    
    def get_tab(self, name, parent, app):
        if name not in self._tab_cache:
            if name == "Demand":
                from src.tabs.demand_tab import DemandTab
                self._tab_cache[name] = DemandTab(parent, app)
        return self._tab_cache[name]
```

### WebDriverWait Pattern (Replace time.sleep)

```python
# Current (blocking):
time.sleep(2)
element.click()

# Proposed (non-blocking):
wait = WebDriverWait(driver, 10)
element = wait.until(EC.element_to_be_clickable((By.ID, "submit-btn")))
element.click()
```

### Centralized Font Manager

```python
class FontManager:
    _instance = None
    _fonts_loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_font_paths(self):
        if not self._fonts_loaded:
            # Load fonts once
            self.regular = resource_path("assets/fonts/NotoSansDevanagari-Regular.ttf")
            self.bold = resource_path("assets/fonts/NotoSansDevanagari-Bold.ttf")
            self._fonts_loaded = True
        return self.regular, self.bold
```

---

## 📊 Expected Performance Gains

| Metric | Before | After (Optimized) | After (Lite) |
|--------|--------|-------------------|--------------|
| Startup Time (HDD) | 4-6 seconds | 2-3 seconds | 1-2 seconds |
| Startup Time (SSD) | 2-3 seconds | 1-1.5 seconds | <1 second |
| RAM Usage (idle) | 120-150 MB | 80-100 MB | 50-70 MB |
| RAM Usage (automation) | 250-350 MB | 200-250 MB | 150-200 MB |
| Tab Switching | 300-800ms | 100-300ms | 50-150ms |
| UI Freeze During Wait | 2-3 seconds | 0 seconds | 0 seconds |
| Executable Size | ~80 MB | ~60 MB | ~40 MB |

---

## ⚠️ Risk Mitigation

1. **Always create backups** before refactoring large files
2. **Test each change in isolation** on a low-end VM (2GB RAM)
3. **Maintain backward compatibility** — Lite version should be able to load full configs
4. **Feature flags** — Use `config.FEATURE_FLAGS` dict to toggle optimizations
5. **Rollback plan** — Keep original files as `.backup.py` during refactoring

---

## 📝 Progress Log

| Date | Task | Status | Notes |
|------|------|--------|-------|
| 2026-07-24 | Initial analysis completed | ✅ Done | Codebase analyzed, bottlenecks identified |
| 2026-07-24 | **Phase 1.2**: Lazy tab loading in `tab_config.py` | ✅ Done | All 44 tabs now lazily imported via `_lazy_import()` pattern |
| 2026-07-24 | **Phase 1.3**: Config value cache in `config.py` | ✅ Done | `COLORS.cache` added with `_ConfigCache` class |
| 2026-07-24 | **Phase 4**: `lite_app.py` entry point created | ✅ Done | Simplified app with essential tabs only |
| 2026-07-24 | **Phase 4**: `lite_tab_config.py` created | ✅ Done | 30 essential tabs, removed heavy/uncommon ones |
| 2026-07-24 | **Phase 4**: `lite_config.py` created | ✅ Done | Config overrides for low-end devices |
| 2026-07-24 | Code review & bug fixes | ✅ Done | Fixed MacroManagerTab lazy import bug, removed dup code |
| | T1.1 - Replace time.sleep | ⏳ **Next up** | Requires per-tab analysis |
| | T3.2 - Font Manager | ⏳ Pending | |
| | T5.1 - Split demand_tab.py | ⏳ Pending | |
| | Build Lite executable | ⏳ Pending | PyInstaller for `lite_app.py` |

---

> **Next Steps:** Review this plan, prioritize tasks, and start with Phase 1 (Quick Wins) for immediate impact with minimal risk.
