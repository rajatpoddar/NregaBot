# Skilled & Semi-Skilled Worker Aadhaar Report Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new automation tab (`skilled_aadhaar_report`) to the NregaBot desktop application that selects Panchayats on the portal's `SkilledBulkAadhaarUpdate.aspx` page, paginates through all grid pages, scrapes worker details, calculates a summary (total workers, male/female count, Aadhaar seeded vs pending count), and exports reports to Excel/CSV.

**Architecture:** Create `src/tabs/skilled_aadhaar_report_tab.py` subclassing `BaseAutomationTab`. Register it in `src/tab_config.py`, `src/lite_tab_config.py`, `src/app/app_automation.py`, `src/tabs/base_tab.py`, and `src/tabs/history_manager.py`. Include unit test `tests/test_skilled_aadhaar_report_tab.py` utilizing the HTML snapshot `docs/htm/SkilledBulkAadhaarUpdate.aspx.html`.

**Tech Stack:** Python 3.12, CustomTkinter, Selenium WebDriver, openpyxl, pandas/csv, pytest.

**Spec:** HTML file `docs/htm/SkilledBulkAadhaarUpdate.aspx.html`.

## Global Constraints

- **Thread Safety:** Worker threads MUST NOT touch Tk widgets directly. Use `self.app.after(0, callable)` or `safe_after(0, callable)` (RULE-UI-002).
- **Driver Cleanup:** Tab MUST NOT call `driver.quit()`. Cleanup is owned by `start_automation_thread()` wrapper (RULE-UI-003).
- **Lazy Imports:** Tab MUST NOT import selenium/pandas/requests at module top-level (RULE-SRC-001). Use function-level imports or `_imports` helper.
- **Whitelist Protection:** Core zip contains whitelisted folders only; no tests or `.env` leaked (RULE-REL-001).
- **Version Integrity:** `config/version.json` latest_version is source of truth (3.2.9).

---

### Task 1: Create unit parser tests using HTML snapshot fixture

**Files:**
- Create: `tests/test_skilled_aadhaar_report_tab.py`
- Reference: `docs/htm/SkilledBulkAadhaarUpdate.aspx.html`

**Interfaces:**
- Produces: `parse_skilled_aadhaar_table(html_content: str)` function (standalone pure parser function for unit testing and tab consumption)

- [ ] **Step 1: Write the failing unit test for table parsing**

```python
# tests/test_skilled_aadhaar_report_tab.py
import pytest
from pathlib import Path

def parse_skilled_aadhaar_table(html_content: str):
    """Parses rows from SkilledBulkAadhaarUpdate table HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", id="ctl00_ContentPlaceHolder1_Grid_debarred")
    if not table:
        return [], {"total": 0, "male": 0, "female": 0, "other": 0, "seeded": 0, "pending": 0}
    
    rows = table.find_all("tr")
    data = []
    male = female = other = seeded = pending = 0
    
    for r in rows:
        cols = r.find_all("td")
        # Data row has 7 td elements (col 0: S.No, 1: JobCard, 2: Name, 3: Gender, 4: Aadhaar, 5: Aadhaar Name, 6: Update link)
        if len(cols) == 7:
            # Check if this row is pagination nested table or data row
            sno_span = cols[0].find("span", id=lambda x: x and x.endswith("_sno"))
            if not sno_span:
                continue
            
            sno = sno_span.get_text(strip=True)
            jc_span = cols[1].find("span", id=lambda x: x and x.endswith("_lbljcno"))
            jc_no = jc_span.get_text(strip=True) if jc_span else cols[1].get_text(strip=True)
            
            name_span = cols[2].find("span", id=lambda x: x and x.endswith("_lblapp_name"))
            worker_name = name_span.get_text(strip=True) if name_span else cols[2].get_text(strip=True)
            
            gender_span = cols[3].find("span", id=lambda x: x and x.endswith("_lblgender"))
            gender = gender_span.get_text(strip=True) if gender_span else cols[3].get_text(strip=True)
            
            uid_span = cols[4].find("span", id=lambda x: x and x.endswith("_lb_UID_No"))
            uid_text = uid_span.get_text(strip=True) if uid_span else cols[4].get_text(strip=True)
            
            aadhaar_name = cols[5].get_text(strip=True)
            
            has_aadhaar = bool(uid_text)
            status = "Seeded" if has_aadhaar else "Pending"
            
            if gender.upper() == "M":
                male += 1
            elif gender.upper() == "F":
                female += 1
            else:
                other += 1
                
            if has_aadhaar:
                seeded += 1
            else:
                pending += 1
                
            data.append({
                "sno": sno,
                "job_card_no": jc_no,
                "worker_name": worker_name,
                "gender": gender,
                "aadhaar_no": uid_text,
                "name_as_per_aadhaar": aadhaar_name,
                "status": status
            })
            
    summary = {
        "total": len(data),
        "male": male,
        "female": female,
        "other": other,
        "seeded": seeded,
        "pending": pending
    }
    return data, summary


def test_parse_skilled_aadhaar_table():
    fixture_path = Path("docs/htm/SkilledBulkAadhaarUpdate.aspx.html")
    assert fixture_path.exists(), "Snapshot fixture missing"
    
    html_content = fixture_path.read_text(encoding="utf-8")
    data, summary = parse_skilled_aadhaar_table(html_content)
    
    assert summary["total"] > 0
    assert summary["total"] == summary["male"] + summary["female"] + summary["other"]
    assert summary["total"] == summary["seeded"] + summary["pending"]
    assert len(data) == summary["total"]
    
    # Check specific fields of first row
    first = data[0]
    assert "job_card_no" in first
    assert "worker_name" in first
    assert "gender" in first
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_skilled_aadhaar_report_tab.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_skilled_aadhaar_report_tab.py
git commit -m "test: add parser unit tests for skilled aadhaar report page"
```

---

### Task 2: Create `src/tabs/skilled_aadhaar_report_tab.py` module

**Files:**
- Create: `src/tabs/skilled_aadhaar_report_tab.py`

**Interfaces:**
- Consumes: `BaseAutomationTab`, `tr()` from `src.i18n`, `config`
- Produces: `SkilledAadhaarReportTab` class

- [ ] **Step 1: Write `src/tabs/skilled_aadhaar_report_tab.py`**

Implementation requirements:
- Subclass `BaseAutomationTab` with `automation_key = "skilled_aadhaar_report"`.
- Setup UI with Header Card (icon 👷‍♂️ / `emoji_skilled_report`), TabView (`Settings`, `Results`, `Logs & Status`).
- `Settings` tab:
  - Panchayat dropdown (using `_all_panchayat_values` with `ALL_PANCHAYATS_LABEL` and `MY_PANCHAYATS_LABEL`).
  - Filter dropdown (`All`, `Aadhaar Seeded`, `Aadhaar Pending`).
  - Stats frame for Panchayat-wise summary.
  - Action buttons (`_create_action_buttons`).
- `Results` tab:
  - Prominent Summary Card at top:
    - Total Workers (कुल कामगार)
    - Male (पुरुष) / Female (महिला)
    - Aadhaar Seeded (आधार चढ़ा हुआ)
    - Aadhaar Pending (आधार बाकी)
  - Export to Excel button (`export_btn`).
  - Treeview data table with columns: `Panchayat`, `S.No`, `Job Card No`, `Worker Name`, `Gender`, `Aadhaar No`, `Name as per Aadhaar`, `Aadhaar Status`.
- `run_process(driver)` method:
  - Supports single Panchayat, All Panchayats, or My Saved Panchayats.
  - Switches Panchayat via `ctl00_ContentPlaceHolder1_ddl_panch`.
  - Loops over GridView pages via pagination elements in `ctl00_ContentPlaceHolder1_Grid_debarred`.
  - Scrapes rows using Selenium or page source BeautifulSoup.
  - Aggregates stats into `all_scraped_data` and updates summary frame and Treeview using `self.app.after(0, ...)`.
  - Generates Excel/CSV export function `export_professional_report()`.

- [ ] **Step 2: Run smoke test to verify no syntax or Tk construction errors**

Run: `venv/bin/python _smoke_test_tabs.py`
Expected: PASS (if registered) or clean python syntax check via `venv/bin/python scripts/check_imports.py`

- [ ] **Step 3: Commit**

```bash
git add src/tabs/skilled_aadhaar_report_tab.py
git commit -m "feat: implement SkilledAadhaarReportTab automation tab"
```

---

### Task 3: Register `skilled_aadhaar_report` across configuration, navigation, locales, and history

**Files:**
- Modify: `src/tab_config.py`
- Modify: `src/lite_tab_config.py`
- Modify: `src/app/app_automation.py`
- Modify: `src/tabs/base_tab.py`
- Modify: `src/tabs/history_manager.py`
- Modify: `src/locales/en.json`, `hi.json`, `hinglish.json`, `kn.json`, `bn.json`

**Interfaces:**
- Consumes: `_lazy_import("SkilledAadhaarReportTab", "src.tabs.skilled_aadhaar_report_tab")`

- [ ] **Step 1: Add lazy import registration in `src/tab_config.py` and `src/lite_tab_config.py`**
  - Add `"Skilled & Semi-Skilled Report"` under `"Reports & Tracking"`:
```python
            "Skilled Worker Report": {
                "creation_func": _lazy_import("SkilledAadhaarReportTab", "src.tabs.skilled_aadhaar_report_tab"),
                "icon": app.icon_images.get("emoji_ekyc_report"),
                "key": "skilled_aadhaar_report"
            },
```

- [ ] **Step 2: Add display name mapping in `src/app/app_automation.py` and `src/tabs/base_tab.py`**
  - Add `"skilled_aadhaar_report": "Skilled & Semi-Skilled Report"` to `AUTOMATION_DISPLAY_NAMES`.

- [ ] **Step 3: Add history input filename mapping in `src/tabs/history_manager.py`**
  - Add `"skilled_aadhaar_report": "skilled_aadhaar_inputs.json"` to `TAB_INPUT_FILES`.

- [ ] **Step 4: Add i18n keys to all locale files**
  - Add `tab.skilled_aadhaar_report.title` and `tab.skilled_aadhaar_report.subtitle` to `en.json`, `hi.json`, `hinglish.json`, `kn.json`, `bn.json`.

- [ ] **Step 5: Run full pre-flight check suite**

Run:
```bash
python3 -m pytest -q
venv/bin/python _smoke_test_tabs.py
venv/bin/python scripts/check_imports.py
venv/bin/python scripts/_verify_whitelist_dryrun.py
```
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/tab_config.py src/lite_tab_config.py src/app/app_automation.py src/tabs/base_tab.py src/tabs/history_manager.py src/locales/
git commit -m "feat: register skilled_aadhaar_report tab across tab_configs, display names, history, and locales"
```

---

### Task 4: Final Verification & Smoke Test

- [ ] **Step 1: Run pytest suite**
Run: `python3 -m pytest -q` (Expect 307+ passing)

- [ ] **Step 2: Run smoke test for all 46 tabs**
Run: `venv/bin/python _smoke_test_tabs.py` (Expect Total tabs found: 46, all OK)

- [ ] **Step 3: Check import and whitelist dryrun**
Run: `venv/bin/python scripts/check_imports.py` and `venv/bin/python scripts/_verify_whitelist_dryrun.py`
