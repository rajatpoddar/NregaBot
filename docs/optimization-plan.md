# 🚀 NREGA Bot Lite — Performance Optimization Plan

> **Goal:** Make the Lite application launch instantly, run buttery-smooth on low-end PCs (1GB RAM, old CPUs), and never flicker during startup, tab switching, or window resize.

---

## 📋 Table of Contents

1. [Phase 1: Startup & Splash (0–500ms)](#phase-1-startup--splash-0500ms)
2. [Phase 2: UI Construction & Layout (500ms–2s)](#phase-2-ui-construction--layout-500ms2s)
3. [Phase 3: Tab Loading & Navigation (2s+)](#phase-3-tab-loading--navigation-2s)
4. [Phase 4: Runtime Performance](#phase-4-runtime-performance)
5. [Phase 5: Memory & GC](#phase-5-memory--gc)
6. [Phase 6: Import & Dependency Optimization](#phase-6-import--dependency-optimization)
7. [Phase 7: Window & Resize Smoothing](#phase-7-window--resize-smoothing)
8. [Phase 8: Monitoring & Metrics](#phase-8-monitoring--metrics)

---

## Phase 1: Startup & Splash (0–500ms)

### 1.1 Zero-Flicker Splash → Main Window Transition ✅ *(Already Done)*

**Current state:** Splash fades out (10-step alpha), then main window uses `alpha=0 → paint → alpha=1` trick.

**Already optimized:**
- `_fade_in_main_window()` renders the full window while invisible (alpha=0.0)
- Two `update()` / `update_idletasks()` cycles ensure complete pixel composition before showing
- No flicker during the transition

**Remaining optimizations:**

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 1.1a | **Reduce splash window size** — current 300×200 → 280×160. Smaller toplevel = faster create/render. | Low | 1 min |
| 1.1b | **Remove splash fade-out animation** (10 steps × 15ms = 150ms). Just destroy instantly. Splash is already behind alpha=0 window; no one sees it disappear. | Medium | 2 min |
| 1.1c | **Reduce minimum splash display time** — current 500ms → 200ms. On fast devices there's no reason to wait. | Medium | 1 min |
| 1.1d | **Eliminate `_check_splash_ready` retry loop** — if layout is ready by 200ms, just transition. The 30-retry × 100ms = 3s worst case wastes cycles. | Low | 2 min |

### 1.2 Deferred Initialization

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 1.2a | **Move HTTP session creation** (`requests.Session()`) out of `__init__` → create lazily on first network call. | Low | 3 min |
| 1.2b | **Defer `BrowserManager` init** — it imports selenium, webdriver, etc. Only create when user clicks a browser button. | **High** | 5 min |
| 1.2c | **Defer `WorkflowManager` init** — rarely used in Lite. Create on first access. | Medium | 3 min |
| 1.2d | **Defer `HistoryManager` init** — file I/O for history DB. Create when user opens history window. | Medium | 3 min |

### 1.3 Threading Model

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 1.3a | **Replace `threading.Thread` for background init** with `self.after(0, ...)` chain. Threading adds overhead on single-core low-end CPUs. The lite UI build is fast enough to run on main thread. | Medium | 2 min |
| 1.3b | **Ensure no `time.sleep()` on main thread** — audit all startup methods. Use `self.after()` instead. | Low | 5 min |

---

## Phase 2: UI Construction & Layout (500ms–2s)

### 2.1 Widget Count Reduction

**Problem:** Each `CTkFrame`, `CTkButton`, `CTkLabel` creates a tkinter Canvas internally — expensive on old GPUs/drivers.

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 2.1a | **Remove redundant wrapper frames** — e.g., `branding` frame in header has `CTkFrame` + 3 labels. Flatten to just labels with side-by-side pack. | Medium | 5 min |
| 2.1b | **Replace `CTkScrollableFrame`** (heavy canvas-based) with plain `tk.Canvas` + `tk.Frame` for sidebar nav scroll. Or use `tkinter.ttk.Treeview` as nav (lightweight). | **High** | 20 min |
| 2.1c | **Minimize nav button count** — Lite already has fewer tabs (24 vs 40+ in full). Consider grouping less-used tabs into a "More..." dropdown. | Medium | 10 min |
| 2.1d | **Replace header action buttons** with smaller text-only buttons (remove PNG/emoji icons from buttons). | Low | 3 min |

### 2.2 Canvas Redraw Optimization

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 2.2a | **Set `corner_radius=0` on ALL structural frames** (header, sidebar container, content area, footer). Corner rounding creates canvas arcs that are expensive to redraw on resize. ✅ *(partially done — some already have 0)* | **High** | 3 min |
| 2.2b | **Avoid `grid_propagate(False)`** on frames that don't need it — it forces tkinter to negate geometry calculations. | Medium | 5 min |
| 2.2c | **Use `pack(fill=..., expand=...)` instead of `grid()`** for simpler layouts — less geometry management overhead. | Medium | 10 min |
| 2.2d | **Batch UI updates** — when building many widgets, call `win.update_idletasks()` only once at the end, not per-widget. | Low | 2 min |

### 2.3 Theme & Color

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 2.3a | **Simplify COLORS dict** — Lite doesn't need all 150+ color entries from `config.py`. Create a `LITE_COLORS` subset. | Low | 10 min |
| 2.3b | **Pre-resolve color tuples** — `(light, dark)` tuples force CTk to check appearance mode each render. Use static resolved colors for widgets that don't theme-switch. | Medium | 5 min |
| 2.3c | **Use `COLORS_CACHE`** (already exists in config.py) for frequently-accessed colors. | Low | 3 min |

---

## Phase 3: Tab Loading & Navigation (2s+)

### 3.1 Super-Lazy Tab Loading

**Current state:** Tabs are loaded lazily via `show_frame()` — first click creates the frame and instance.

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 3.1a | **Add tab preloading queue** — After Home is shown, preload next-likely tabs (e.g., Demand, Work Allocation) in background with 200ms gaps. | Medium | 10 min |
| 3.1b | **Cache tab frame creation** — `ctk.CTkFrame(self.content_area)` creates a canvas. Reuse a single "tab container frame" and just swap child widgets. | **High** | 15 min |
| 3.1c | **Tab destruction on memory pressure** — if >5 tabs are loaded and RAM < threshold, destroy the least-recently-used tab instance. | Low | 10 min |
| 3.1d | **Avoid `frame.tkraise()`** — instead, hide/unhide frames with `pack_forget()`/`pack()` or `grid_remove()`/`grid()`. `tkraise()` triggers full stacking order recalculation. | Medium | 5 min |

### 3.2 Navigation Responsiveness

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 3.2a | **Show skeleton/placeholder** immediately when tab is clicked, load actual content in background. | **High** (UX) | 15 min |
| 3.2b | **Instantly highlight nav button** before tab content loads — gives immediate tactile feedback. ✅ *(Already done)* | - | - |
| 3.2c | **Debounce rapid nav clicks** — if user clicks 3 tabs in 100ms, only process the last one. | Low | 3 min |

---

## Phase 4: Runtime Performance

### 4.1 Event Loop Health

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 4.1a | **Move all network I/O to threads** — every `requests.get()` blocks the GUI. Audit all tabs for blocking calls. | **High** | 20 min |
| 4.1b | **Use `self.after(10, ...)` instead of `threading.Thread`** for short background tasks — avoids GIL contention on single-core CPUs. | Medium | 10 min |
| 4.1c | **Limit `after()` callbacks** — too many pending timers slows tkinter's event loop. Consolidate where possible. | Low | 5 min |

### 4.2 String & Config Optimization

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 4.2a | **Cache `get_tabs_definition_lite()` result** — it's called on every `show_frame()` and every nav creation. The dict is static per session. | Medium | 2 min |
| 4.2b | **Replace f-string heavy code** with `.format()` or pre-compiled templates in hot paths (tab switching, status updates). | Low | 5 min |
| 4.2c | **Avoid `hasattr()` in hot paths** — use `getattr(..., None)` with a sentinel. | Low | 3 min |

---

## Phase 5: Memory & GC

### 5.1 Garbage Collection

**Current state:** `gc.set_threshold(500, 5, 3)`, `gc.freeze()` at startup.

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 5.1a | **Add periodic GC collection** (every 3 minutes) — like `main_app.py`'s `_gc_collection_loop()`. Prevents memory fragmentation in long sessions. | Medium | 5 min |
| 5.1b | **Increase generation-0 threshold** — 500 is very aggressive. Try `(700, 10, 5)` to reduce collection frequency on low-end CPUs. | Medium | 2 min |
| 5.1c | **Explicitly delete large objects** after use (e.g., temp dataframes, large lists) with `del` + `gc.collect()`. | Medium | 10 min |

### 5.2 Object Lifecycle

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 5.2a | **Clear `tab_instances` cache** for tabs that are no longer visible (keep max 3-5). | Medium | 8 min |
| 5.2b | **Destroy Selenium driver** aggressively on automation finish — it's a memory hog (~200-500MB). ✅ *(Already partially done)* | - | - |
| 5.2c | **Release `http_session` connection pools** periodically with `session.close()`. | Low | 2 min |

---

## Phase 6: Import & Dependency Optimization

### 6.1 Startup Imports

**Problem:** `lite_app.py` imports 15+ modules at module level, loading thousands of lines of code before the splash even shows.

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 6.1a | **Move imports into methods** — `from src.managers.browser_manager import BrowserManager` → import inside the method that creates it. | **High** | 10 min |
| 6.1b | **Lazy-import heavy modules** — `requests`, `ctypes`, `webbrowser`, `socket` — import only when needed. | Medium | 5 min |
| 6.1c | **Use `importlib.import_module()`** for tab imports (already done via `_lazy_import` in `lite_tab_config.py`). ✅ | - | - |
| 6.1d | **Remove unused imports** — `from tkinter import ttk`, `from datetime import datetime`, `Set`, `Tuple` from typing. | Low | 2 min |

### 6.2 Module Size

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 6.2a | **Create `lite_state.py`** — a simplified AppState with only Lite-relevant fields (no `_resize_overlay`, `performance_monitor`, etc.) | Medium | 15 min |
| 6.2b | **Strip unused configs** — Lite doesn't need `MATE_MR_CONFIG`, `ZERO_MR_CONFIG`, `JOBCARD_VERIFY_CONFIG`, etc. | Low | 5 min |

---

## Phase 7: Window & Resize Smoothing

### 7.1 Window Show Animation

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 7.1a | **Remove `focus_force()`** — forces window manager attention, can cause jank on Linux/X11. Use `lift()` only. | Low | 1 min |
| 7.1b | **Pre-calculate geometry** before `deiconify()` — avoid geometry manager pass after showing. ✅ *(Already done)* | - | - |
| 7.1c | **Set min size constraints on content area** to prevent layout recalculations during initial pack. | Low | 2 min |

### 7.2 Resize Debounce

**Current state:** No resize handling in lite_app.py (unlike full app which has `_on_window_resize_detect`).

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 7.2a | **Add resize overlay** (single flat CTkFrame) that covers content during resize — prevents canvas redraw flicker on Windows. | **High** | 10 min |
| 7.2b | **Bind `<Configure>` event** with 100ms debounce to avoid rapid recalculations. | Medium | 5 min |
| 7.2c | **Use `grid_propagate(False)`** on main content area to prevent child-driven layout shifts during resize. | Low | 2 min |

---

## Phase 8: Monitoring & Metrics

### 8.1 Performance Telemetry (Optional)

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 8.1a | **Log startup timestamps** — measure `__init__ start`, `_build_ui end`, `_fade_in_main_window end`, `show_frame("Home") end`. Useful for regression testing. | Low | 5 min |
| 8.1b | **Track tab load times** — log how long each `show_frame()` takes. Identifies slow tabs. | Low | 3 min |
| 8.1c | **Memory usage snapshot** — log `gc.get_objects()` count and `psutil.Process().memory_info()` after startup and after each tab load. | Low | 5 min |

---

## ⚡ Prioritized Action Plan

### 🥇 Immediate (High Impact, Low Effort) — Do First

| Priority | Task | Phase | Est. Time |
|----------|------|-------|-----------|
| P1 | Defer `BrowserManager` init (lazy import + lazy create) | 1.2b | 5 min |
| P2 | Remove splash fade-out animation | 1.1b | 2 min |
| P3 | Reduce minimum splash time 500ms → 200ms | 1.1c | 1 min |
| P4 | Set `corner_radius=0` on all structural frames | 2.2a | 3 min |
| P5 | Cache `get_tabs_definition_lite()` result | 4.2a | 2 min |
| P6 | Add resize overlay to prevent flicker | 7.2a | 10 min |
| P7 | Add periodic GC collection loop | 5.1a | 5 min |
| **Total** | | | **~28 min** |

### 🥈 Short-term (High Impact, Medium Effort) — Next Sprint

| Priority | Task | Phase | Est. Time |
|----------|------|-------|-----------|
| P8 | Reuse single tab container frame instead of creating new CTkFrame per tab | 3.1b | 15 min |
| P9 | Replace `CTkScrollableFrame` with lightweight alternative | 2.1b | 20 min |
| P10 | Move network I/O off main thread (audit tabs) | 4.1a | 20 min |
| P11 | Redundant wrapper frame removal | 2.1a | 5 min |
| P12 | Add startup timing telemetry | 8.1a | 5 min |
| **Total** | | | **~65 min** |

### 🥉 Long-term (Medium/High Impact, Higher Effort) — Future

| Priority | Task | Phase | Est. Time |
|----------|------|-------|-----------|
| P13 | Show skeleton/placeholder on tab click | 3.2a | 15 min |
| P14 | Tab destruction on memory pressure | 3.1c | 10 min |
| P15 | Simplify COLORS dict for Lite | 2.3a | 10 min |
| P16 | Create `lite_state.py` | 6.2a | 15 min |
| P17 | Move all module-level imports into methods | 6.1a | 10 min |
| **Total** | | | **~60 min** |

---

## 📊 Success Metrics

| Metric | Current (approx.) | Target |
|--------|-------------------|--------|
| Cold startup → Home visible | ~800ms–1.5s | **<500ms** |
| Splash → main window flicker | Visible on some devices | **Zero flicker** |
| Tab switch responsiveness | ~50–200ms | **<30ms (instant highlight)** |
| Memory after startup | ~80–120MB | **<60MB** |
| Import time | ~150–300ms | **<100ms** |
| Resize smoothness | Minor flicker on Windows | **No visible artifacts** |

---

## 🔄 Continuous Improvement

- **Profile before/after** each change using Python's `time.perf_counter()` and `tracemalloc`
- **Test on actual low-end hardware** (Windows 7, 2GB RAM, Intel Atom/Celeron)
- **Add a `--benchmark` CLI flag** that starts the app, measures all phases, prints results, and exits

---

*Last updated: July 2026*
*Author: AI Optimization Assistant*
