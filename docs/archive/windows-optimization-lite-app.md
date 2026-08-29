# Windows Optimization — NREGA Bot Lite App

> **Date:** July 2026  
> **Scope:** `lite_app.py` and `src/tabs/autocomplete_widget.py`  
> **Status:** ✅ All fixes implemented

---

## Issue 1: Application Launch Not Smooth (Render Flicker)

### Problem
On Windows, the lite app window appeared incomplete during startup:
- Window was shown immediately in `__init__()` via `deiconify()` + `update()`
- Splash frame used `pack()` while subsequent `_build_ui()` used `grid()` — layout manager switch caused visual flicker
- macOS was unaffected because its window compositor handles partial renders differently

### Fix Applied ✅
- **Platform detection:** `self._on_windows = config.OS_SYSTEM == "Windows"`  
- **Windows path:** Main window stays `withdraw()`-n during UI build. A separate `CTkToplevel` splash window provides visual feedback.
- **macOS path:** Kept original in-window splash approach (to avoid macOS Tk `withdraw`/`deiconify` mouse-event bug)
- **UI revealed only when fully built:** `_show_window()` sets final geometry, calls `deiconify()`, then runs two paint cycles (`update_idletasks()` + `update()`) before showing

#### Files changed: `lite_app.py`
- `__init__()` — Restructured startup with OS-conditional path
- `_create_splash_toplevel()` — New method for Windows Toplevel splash
- `_build_ui_on_main_thread()` — Unified splash cleanup
- `_show_window()` — OS-conditional reveal with double paint cycle

---

## Issue 2: Dropdown Not Closing After Selection (AutocompleteEntry)

### Problem
On Windows, `AutocompleteEntry` dropdown (suggestion popup) didn't close reliably after selecting an item:
- `FocusOut` event fires **before** the mouse click registers on the popup toplevel
- The 250ms delay in `_on_focus_out` was insufficient on Windows
- No mouse-over tracking meant the dropdown could close while the user was moving to click

### Fix Applied ✅
- **Mouse-over tracking:** Added `_mouse_over_popup` flag, bound `<Enter>`/`<Leave>` events on the suggestion toplevel
- **Smarter focus-out handler:** `_on_focus_out` now checks `_mouse_over_popup`. If mouse is over the popup, defers hide for another 100ms to let the click complete
- **Increased delay:** From 250ms to 300ms for more reliable Windows behavior

#### Files changed: `src/tabs/autocomplete_widget.py`
- `__init__()` — Added `_mouse_over_popup` flag
- `_init_popup()` — Bound `<Enter>`/`<Leave>` events on the toplevel
- `_on_focus_out()` — Refactored with mouse-over check and longer delay

---

## Issue 3: Tab / Automation Switching Feels Laggy

### Problem
On Windows, switching between tabs had visible lag because:
1. `_update_nav_highlight()` iterated **all** nav buttons on every switch — O(n) layout recalculation
2. No `update_idletasks()` call before raising frames — Windows showed partial renders
3. `_tab_container` allowed grid propagation, causing expensive recalculations on every child add/remove

### Fix Applied ✅
- **Optimized nav highlight:** `_update_nav_highlight()` now only updates the previously-active button (1 config) and the newly-active button (1 config) — O(2) instead of O(n)
- **Layout flush before raise:** `show_frame()` calls `_tab_container.update_idletasks()` before and after `tkraise()` to ensure layout is fully calculated
- **Grid propagation disabled:** `_tab_container.grid_propagate(False)` prevents expensive child-triggered recalculations

#### Files changed: `lite_app.py`
- `__init__()` — Added `_last_active_nav` tracking field
- `_build_ui()` — Added `grid_propagate(False)` on `_tab_container`
- `show_frame()` — Added `update_idletasks()` before/after `tkraise()`
- `_update_nav_highlight()` — Changed from full iteration to incremental update

---

## Summary of Changes

| File | Change | Impact |
|---|---|---|
| `lite_app.py` | OS-conditional startup (withdraw on Windows, in-window splash on macOS) | ✅ Smooth launch |
| `lite_app.py` | Added `_create_splash_toplevel()` for Windows | ✅ Professional splash |
| `lite_app.py` | Double paint cycle in `_show_window()` for Windows | ✅ No flicker |
| `lite_app.py` | `grid_propagate(False)` on `_tab_container` | ✅ Faster tab switching |
| `lite_app.py` | `update_idletasks()` in `show_frame()` | ✅ No partial renders |
| `lite_app.py` | Incremental `_update_nav_highlight()` | ✅ Snappier nav |
| `src/tabs/autocomplete_widget.py` | Mouse-over tracking on popup | ✅ Dropdown stays open |
| `src/tabs/autocomplete_widget.py` | Smarter `_on_focus_out` with deferral | ✅ Dropdown closes properly |

---

## Testing Notes

To verify these fixes on Windows:
1. **Launch:** Run `python lite_app.py` — the window should appear fully rendered with no flicker
2. **Dropdown:** Click any `AutocompleteEntry` field, then click a suggestion — dropdown should close and value should be inserted
3. **Tab switch:** Click different nav buttons — tab content should appear smoothly without visible lag
4. **macOS:** The app should still launch and work correctly (no regression)

## Future Optimizations (Not Yet Done)

- [ ] **Tab preloading:** Preload the "Home" tab during splash phase to make first switch instant
- [ ] **Lazy widget creation:** Create only visible widgets in complex tabs, defer the rest
- [ ] **Threaded tab loading:** For very heavy tabs, show a loading skeleton while the tab initializes in a thread
- [ ] **Windows DPI scaling:** Fine-tune DPI awareness to `PerMonitorV2` for multi-monitor setups
