---
name: nregabot-tab-builder
description: Use when creating a new automation tab or updating an existing automation tab in NregaBot. Enforces the complete 8-point checklist: BaseAutomationTab inheritance, lazy imports, icon registration across all 4 registries, Panchayat dropdown/ASP.NET navigation handling, thread-safe notification with activity details, dedicated report directories, and executive-grade multi-sheet openpyxl Excel reporting.
---

# NregaBot Tab Builder Skill

Standard blueprint and 8-point checklist for building or updating automation tabs in NregaBot.
Whenever a new portal automation or report tab is requested, follow this exact workflow to prevent regressions, runtime errors, missing UI icons, or unprofessional report exports.

---

## 1. Non-Negotiable Architecture Rules

1. **`RULE-SRC-001` (Lazy Imports inside Methods)**:
   - Module top-level must NOT import `selenium`, `pandas`, `requests`, `openpyxl`, or `bs4`.
   - Always import these heavy libraries inside the worker thread function or export method.
   - *Exception*: `base_tab.py` owns the base selenium types.

2. **`RULE-UI-002` (Tk Thread Safety)**:
   - Worker automation threads must NEVER directly touch Tk widgets.
   - Always wrap UI mutations inside `self.app.after(0, callable)` or `_safe_ui()`.

3. **`RULE-UI-003` (Driver Lifecycle)**:
   - Tabs must NOT call `driver.quit()` in `destroy()`.
   - Driver cleanup is owned by `start_automation_thread()` wrapper closure.

4. **`RULE-REL-001` (Core Zip Whitelist)**:
   - Code ships in `core_{win,mac}_vX.zip`. Do not create random root-level scratch files. All changes belong strictly in `src/`, `config/`, `assets/`, `docs/`, or `tests/`.

---

## 2. The 8-Point Automation Checklist

### Point 1: Base Automation Class & Skeleton
Every automation tab must inherit from `BaseAutomationTab`:
```python
from .base_tab import BaseAutomationTab

class MyNewAutomationTab(BaseAutomationTab):
    def __init__(self, parent, app, **kwargs):
        super().__init__(
            parent=parent,
            app=app,
            tab_title="My New Tab",
            automation_key="my_new_tab",
            **kwargs
        )
```

### Point 2: Complete 4-Point Icon Registration
For an icon to appear in all places (Sidebar Menu, Tab Header, Dashboard Card, OS Fallbacks), it MUST be registered in all 4 places:
1. **Asset File**: Place a 32x32 / 64x64 PNG in `assets/icons/emojis/<name>.png`.
2. **`src/managers/icon_manager.py`**:
   ```python
   mgr._add("emoji_<name>", "assets/icons/emojis/<name>.png", size=(16, 16))
   ```
3. **`src/tab_config.py`**:
   ```python
   "My New Tab": {
       "creation_func": _lazy_import("MyNewAutomationTab", "src.tabs.my_new_tab"),
       "icon": app.icon_images.get("emoji_<name>"),
       "key": "my_new_tab"
   }
   ```
4. **`src/app/app_navigation.py` (`_ICON_KEYS`)**:
   ```python
   # Inside _ICON_KEYS dictionary:
   "My New Tab": "emoji_<name>",
   ```
5. **`src/config.py` (`TAB_ICONS`)**:
   ```python
   "My New Tab": "📌",  # Fallback unicode emoji
   ```

### Point 3: Locales & Display Names
- Add to `src/app/app_automation.py` & `src/tabs/base_tab.py` `AUTOMATION_DISPLAY_NAMES`:
  ```python
  "my_new_tab": "My New Tab",
  ```
- Add test case in `tests/test_automation_display_names.py`.
- Add translations in `src/locales/en.json`, `src/locales/hi.json`, and run `venv/bin/python scripts/build_locales.py`.

### Point 4: Robust Panchayat Dropdown & Navigation
Gov portal (VB-G-RAM-G / MGNREGA) dropdowns use ASP.NET `__doPostBack`. Standard dropdown handling:
1. Strip agency prefixes:
   ```python
   panchayat_val = self._clean_panchayat_value(self.panchayat_var.get())
   ```
2. Check for "All" or "My Saved":
   ```python
   if self._is_panchayat_label(panchayat_val) and not self._is_my_saved_panchayat(panchayat_val):
       # Process all panchayats in dropdown
   ```
3. Postback & staleness handling:
   ```python
   # Trigger JavaScript change event
   driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", dropdown_elem)
   try:
       WebDriverWait(driver, 10).until(EC.staleness_of(dropdown_elem))
   except Exception:
       pass
   time.sleep(1.5)
   ```
4. GP login mode detection: If user is logged in at GP level, the dropdown may not exist or be fixed. Guard with fallback.

### Point 5: Thread-Safe Notification & Activity Stats
Do NOT use non-existent methods like `notify_automation_complete()`. Always use:
```python
self.activity_details = {
    "total": total_count,
    "success": success_count,
    "failed": failed_count,
    "time_taken": elapsed_time_str
}
self.show_automation_notification("success")
```

### Point 6: Dedicated Report Directory
Never dump reports into root or an unrelated folder (like MB Entry). Always use the standard category path:
```python
# In base_tab.py, register in _REPORT_CATEGORY_NAMES
# Then fetch report dir:
reports_dir = self.app.get_report_path(self._report_category())
os.makedirs(reports_dir, exist_ok=True)
```

### Point 7: Executive-Grade Excel Reporting Standard
Raw unstyled pandas `.to_excel()` is strictly forbidden. Excel reports must be executive-ready:
1. **Primary Header Banner**: Merged Row 1, Navy Fill (`#1F4E79`), White Bold 14pt text, height 36.
2. **Subtitle Branding Bar**: Merged Row 2, Fill (`#F1F5F9`), Dark Slate Italic 9pt text:
   `Generated via NregaBot (https://nregabot.com) | Date: DD-Mon-YYYY HH:MM AM/PM`
3. **KPI Metric Summary Cards**: Rows 4–5 with colored thematic boxes:
   - Total count: Steel blue (`#DCE6F1`)
   - Success / Seeded: Mint green (`#DCFCE7`, text `#166534`)
   - Pending / Failed: Warm red (`#FEE2E2`, text `#991B1B`)
   - Completion %: Cyan (`#CFFAFE`, text `#155E75`)
4. **Table Headers**: Row 7, Navy Fill (`#1F4E79`), White Bold 11pt, centered, height 26.
5. **Data Rows**:
   - Zebra striping (`#FFFFFF` and `#F8FAFC`).
   - Conditional colored status pill cells (`✅ Seeded` / `✅ Success` green, `⏳ Pending` / `❌ Failed` red).
   - Thin cell borders (`#CBD5E1`).
   - Centered alignment for IDs, Numbers, Status, Dates; Left alignment for Names & Addresses.
6. **Multi-Sheet Structure**:
   - Sheet 1: Detailed Records
   - Sheet 2: Panchayat Summary breakdown with Grand Total accounting double bottom border (`Side(style='double', color='1F4E79')`).
7. **Freeze Panes & Gridlines**:
   - `ws.freeze_panes = "A8"`
   - `ws.views.sheetView[0].showGridLines = True`
8. **Auto Column Widths**: Dynamic width based on cell contents with sensible min/max bounds.
9. **Office-Ready Print Setup**: Call `self._apply_print_setup(ws, header_row)`.
10. **Auto-Launch**: Automatically open the generated workbook using `os.startfile` (Win) or `open` (macOS).

### Point 8: Pre-flight Verification
Before marking complete, execute:
```bash
python3 -m pytest tests/test_<tab_name>.py -v
venv/bin/python _smoke_test_tabs.py
venv/bin/python scripts/_verify_whitelist_dryrun.py
```
