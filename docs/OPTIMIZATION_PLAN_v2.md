# Optimization Plan: Dropdown Unification + Input Persistence

## Overview

Two major changes across the entire NregaBot application:

1. **[P1] Dropdown Unification** — Make all dropdowns use the same widget type (CTkOptionMenu) for consistent look & feel. The "Output Action" style from `duplicate_mr_tab.py` is the reference design.

2. **[P2] Universal Input Persistence** — Every input field across every tab should save to SQLite DB when the user fills it, and auto-load when they revisit the tab.

---

## Part 1: Dropdown Unification

### Current Widget Types

| Type | Widget Class | Used For | Look |
|---|---|---|---|
| **A** | `AutocompleteEntry` (custom `DropdownSelect`) | Location fields (panchayat, district, block, state, village) + some fixed-option fields | Frame-based popup, history suggestions, "Set in Settings" option |
| **B** | `ctk.CTkOptionMenu` (built-in) | Export format, export filter, work category, financial year + duplicate_mr's output_action | Native dropdown, StringVar binding, fixed values |
| **C** | `ctk.CTkComboBox` (built-in) | wc_gen_tab's dynamic dropdowns | Editable combobox |

### Decision

- **Location fields** (Panchayat, District, Block, State, Village) → Keep `AutocompleteEntry` (NEEDS history/suggestions + Settings integration)
- **Fixed-option fields** (output action, filter, year, scheme type, status, etc.) → Convert ALL to `CTkOptionMenu`
- **Output Action** → Make ALL 3 tabs use the SAME widget (CTkOptionMenu with StringVar, consistent with duplicate_mr_tab)

### Exact Changes: Fixed-Option AutocompleteEntry → CTkOptionMenu

#### Group A: Output Action (must be consistent)

| # | File | Current Code | Change To |
|---|---|---|---|
| 1 | `src/tabs/mate_mr_gen_tab.py` (line 114) | `self.output_action_combobox = AutocompleteEntry(..., suggestions_list=["Save as PDF", "Print"])` | `self.output_action_var = ctk.StringVar(value="Save as PDF"); self.output_action_menu = ctk.CTkOptionMenu(..., variable=self.output_action_var, values=["Save as PDF", "Print"])` |
| 2 | `src/tabs/musterroll_gen_tab.py` (line 90) | `self.output_action_combobox = AutocompleteEntry(..., suggestions_list=["Save as PDF", "Print"])` | Same as above |

**Note:** `duplicate_mr_tab.py` (line 83) already uses CTkOptionMenu — NO CHANGE needed.

#### Group B: Other Fixed-Option Dropdowns

| # | File | Line | Widget Name | Current | Change To | Values |
|---|---|---|---|---|---|---|
| 3 | `src/tabs/ekyc_report_tab.py` | 89 | filter_cb | AutocompleteEntry | CTkOptionMenu | ["All", "Verified (Yes)", "Not Verified (No)"] |
| 4 | `src/tabs/sad_update_tab.py` | 69 | action_combobox | AutocompleteEntry | CTkOptionMenu | ["Dispose", "Reject", "In Progress", "Pending"] |
| 5 | `src/tabs/SA_report_tab.py` | 49 | year_entry | AutocompleteEntry | CTkOptionMenu | Years list |
| 6 | `src/tabs/SA_report_tab.py` | 54 | status_entry | AutocompleteEntry | CTkOptionMenu | Status options |
| 7 | `src/tabs/sarkar_aapke_dwar_tab.py` | 112 | scheme_type_combobox | AutocompleteEntry | CTkOptionMenu | Scheme types |
| 8 | `src/tabs/sarkar_aapke_dwar_tab.py` | 134 | service_combobox | AutocompleteEntry | CTkOptionMenu | Service options |
| 9 | `src/tabs/if_edit_tab.py` | 74 | automation_mode_combo | AutocompleteEntry | CTkOptionMenu | Mode options |
| 10 | `src/tabs/wagelist_send_tab.py` | 47 | fin_year_combobox | AutocompleteEntry | CTkOptionMenu | Year options |
| 11 | `src/tabs/resend_rejected_wg_tab.py` | 46 | fin_year_combobox | AutocompleteEntry | CTkOptionMenu | Year options |
| 12 | `src/tabs/dashboard_report_tab.py` | 125 | delay_column_entry | AutocompleteEntry | CTkOptionMenu | Delay column options |

#### Group C: Keep AutocompleteEntry (Location/History fields — NO CHANGE)

All panchayat, district, block, state, village entries across ~30 tabs. These MUST keep AutocompleteEntry because:
- They need dynamic suggestions from `history_manager`
- Settings tab's "Location Data" manages their values
- Empty-state "Set in Settings" redirect is essential

#### Group D: Already CTkOptionMenu — NO CHANGE

All export_format_menu, export_filter_menu, work_category_menu, fin_year_menu across ~20 tabs.

---

## Part 2: Universal Input Persistence

### Current State

- **17 tabs** already have `save_inputs()` / `load_inputs()` using `history_manager.save_tab_inputs_batch()` / `get_tab_inputs()`
- **17 tabs** do NOT have any save/load

### Tabs Needing Save/Load Added

#### Must-Have (have input fields users fill):

| # | File | Needs |
|---|---|---|
| 1 | `src/tabs/duplicate_mr_tab.py` | Save: panchayat, output_action, orientation, scale |
| 2 | `src/tabs/abps_verify_tab.py` | Save: panchayat, village |
| 3 | `src/tabs/del_demand_tab.py` | Save: panchayat, village |
| 4 | `src/tabs/del_work_alloc_tab.py` | Save: panchayat |
| 5 | `src/tabs/delete_applicant_tab.py` | Save: reason, reg_reason, export_filter |
| 6 | `src/tabs/emb_verify_tab.py` | Save: panchayat, export_format |
| 7 | `src/tabs/if_edit_tab.py` | Save: mode, profile, dynamic fields |
| 8 | `src/tabs/jobcard_verify_tab.py` | Save: panchayat, village |
| 9 | `src/tabs/login_automation_tab.py` | Save: district, block |
| 10 | `src/tabs/material_entry_tab.py` | Save: panchayat, work_category, profile |
| 11 | `src/tabs/msr_tab.py` | Save: panchayat |
| 12 | `src/tabs/resend_rejected_wg_tab.py` | Save: fin_year, panchayat |
| 13 | `src/tabs/SA_report_tab.py` | Save: panchayat, year, status |
| 14 | `src/tabs/wagelist_gen_tab.py` | Save: agency/panchayat |
| 15 | `src/tabs/wc_gen_tab.py` | Save: profile, panchayat, dynamic fields |
| 16 | `src/tabs/sarkar_aapke_dwar_tab.py` | Already has save_inputs — VERIFY it includes ALL fields |

#### Low Priority (minimal input fields):

| # | File | Notes |
|---|---|---|
| 17 | `src/tabs/fto_generation_tab.py` | Only browser path, maybe skip |
| 18 | `src/tabs/pdf_merger_tab.py` | File selection, no input fields |
| 19 | `src/tabs/file_management_tab.py` | File browser, no input fields |
| 20 | `src/tabs/macro_manager_tab.py` | Dynamic fields, complex |
| 21 | `src/tabs/update_estimate_tab.py` | Already has config file save |
| 22 | `src/tabs/add_activity_tab.py` | Already has JSON config save |
| 23 | `src/tabs/wagelist_send_tab.py` | Only fin_year, minimal |
| 24 | `src/tabs/dashboard_report_tab.py` | Already has save — also save new fields |

### Implementation Pattern

Every tab should follow this pattern:

```python
def save_inputs(self, data):
    """Save all tab input values to DB."""
    try:
        self.app.history_manager.save_tab_inputs_batch("tab_key", data)
    except Exception as e:
        logger.debug("save_inputs failed: %s", e)

def load_inputs(self):
    """Load saved input values from DB."""
    data = self.app.history_manager.get_tab_inputs("tab_key")
    if data:
        # Set each widget's value from data dict
        self.panchayat_entry.set(data.get("panchayat", ""))
        self.some_var.set(data.get("some_field", ""))
```

Call `load_inputs()` at end of `__init__()` or `_create_widgets()`.
Call `save_inputs()` in `start_automation()` or whenever user changes a value.

---

## Part 3: Settings Integration (Keep As-Is)

Settings tab currently has:

1. **Location Data tab** — Add/delete State, District, Block, Panchayat, Village names
2. **Staff Mapping tab** — Map staff/mate names to panchayats
3. **Default Values tab** — Set default ₹ values for MB entry, verification, etc.
4. **Factory Reset tab** — Clear all saved data

All of these work with `AutocompleteEntry` (Location Data uses it for parent selection; Staff Mapping uses it for panchayat selection). **No changes needed here.**

The "Set in Settings" feature in `DropdownSelect` redirects users to the Settings tab when a dropdown has no suggestions — this continues to work.

---

## Risk Assessment

| Change | Risk | Mitigation |
|---|---|---|
| AutocompleteEntry → CTkOptionMenu (fixed options) | **Low** — values are hardcoded, no history needed | StringVar binding works same way; test get() calls in automation logic |
| Save/load additions | **Low** — follows existing pattern used by 17 tabs | Copy pattern from `mate_mr_gen_tab.py` or `dashboard_report_tab.py` |
| Output action reference changes | **Medium** — need to update all `.get()` and `.set()` calls from AutocompleteEntry API to CTkOptionMenu API | `AutocompleteEntry.get()` → `StringVar.get()`, `AutocompleteEntry.insert()` → `StringVar.set()`, `AutocompleteEntry.set()` → `StringVar.set()` |
| wc_gen_tab skew fields | **Low** — uses CTkComboBox, not AutocompleteEntry | Keep as-is |

---

## Execution Status — Completed ✅

### Phase 1 — Dropdown Unification (All Complete ✅)
| # | File | Change | Status |
|---|---|---|---|
| 1 | `mate_mr_gen_tab.py` | output_action → CTkOptionMenu | ✅ |
| 2 | `musterroll_gen_tab.py` | output_action + designation → CTkOptionMenu | ✅ |
| 3 | `ekyc_report_tab.py` | filter_cb → CTkOptionMenu + trace_add | ✅ |
| 4 | `sad_update_tab.py` | action_combobox → CTkOptionMenu | ✅ |
| 5 | `SA_report_tab.py` | year + status → CTkOptionMenu + default year | ✅ |
| 6 | `sarkar_aapke_dwar_tab.py` | scheme_type + service → CTkOptionMenu | ✅ |
| 7 | `if_edit_tab.py` | automation_mode → CTkOptionMenu + StringVar fix | ✅ |
| 8 | `wagelist_send_tab.py` | fin_year → CTkOptionMenu + default year | ✅ |
| 9 | `resend_rejected_wg_tab.py` | fin_year → CTkOptionMenu + default year | ✅ |
| 10 | `dashboard_report_tab.py` | delay_column → CTkOptionMenu | ✅ |

### Phase 2 — Save/Load Additions (Partial ✅)
| # | File | Status |
|---|---|---|
| 1 | `duplicate_mr_tab.py` | ✅ _save_inputs + _load_inputs added |
| 2+ | Remaining ~13 tabs | ⏳ Pending (user can request) |

### Phase 3 — Testing ✅
- All 11 modified files pass Python syntax check (`py_compile`)
- Code review completed with fixes applied
```
