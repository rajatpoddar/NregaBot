# Regional Language Support — Plan & Progress Report

> **Project:** NregaBot Desktop App + Web Server — multi-language (state-wise) support
> **Status:** 🟢 Desktop app COMPLETE (Phase 1–4). Web server planned (Phase 5).
> **Last updated:** 2026-08-10 (Session 15)

---

## 1. Goal

1. **First:** Fix all user-facing text to **simple, clean English** — remove Hinglish and unnecessary verbose details that confuse users or create trust issues.
2. **Then:** Add **regional language support** (state-wise) so users from every state can use the app in their own language.
3. Everything planned, executed, and reported **step by step** in this document.

## 2. User Decisions (confirmed)

| Decision | Choice |
|---|---|
| Initial languages | **English + Hindi** first (framework ready for all 22 scheduled languages) |
| Language selection | **Settings dropdown + auto-suggest from saved state** (e.g. Maharashtra → Marathi) |
| Logs | **Technical logs stay in English** — only UI text is translated |

## 3. Architecture

```
src/i18n.py                  ← Translation engine (tr(), language manager, state→lang map)
src/locales/en.json          ← Base language (clean English — the SOURCE OF TRUTH)
src/locales/hi.json          ← Hindi translation
src/locales/<xx>.json        ← More languages (Marathi, Tamil, ... added later)
```

- `tr("key")` → returns translated string for the current language.
- `tr("key", var=123)` → supports `{var}` placeholders.
- **Fallback chain:** selected language → English → key name (never crashes, never shows blank).
- Language stored in `config.json` (`app_language`).
- **State auto-suggest:** when the user's State is known, the Settings page suggests the matching language; user can override.

## 4. Phase Plan & Progress

### ✅ Phase 1 — Text Cleanup (Hinglish → clean English)

Goal: every user-facing string in the app is simple, professional, concise English.
No more "Aap X login ho... server tak bhi jaati hai" style verbose/trust-eroding text.

**Examples of the fix:**

| Before (Hinglish / verbose) | After (clean English) |
|---|---|
| `👤 Aap PO — Block Level (Program Officer) login ho. Ye info Settings me save ho gayi hai aur server (admin panel) tak bhi jaati hai.` | `You are logged in as PO — Block Level (Program Officer).` |
| `Aapke saare automations ka record — kab, kaunsa, kya result aaya` | `History of your automations — what ran, when, and the result` |
| `Kya aap saari activity history delete karna chahte hain?` | `Delete all activity history?` |

**Per-file audit (Hinglish density → status):**

| File | Hinglish hits | Status |
|---|---|---|
| `src/tabs/settings_tab.py` | 111 | ✅ Cleaned + migrated to i18n |
| `src/utils.py` (error translations) | 77 | ✅ English rewrite |
| `src/tabs/base_tab.py` | 73 | ✅ Shared dialogs cleaned + migrated |
| `src/app/app_automation.py` | 40 | 🔄 Code comments only (not user-facing) |
| `src/app/app_license.py` | 38 | ✅ Cleaned + migrated |
| `src/tabs/demand_tab.py` | 26 | ✅ Cleaned + migrated |
| `src/tabs/file_management_tab.py` | 18 | ✅ Cleaned + migrated |
| `src/tabs/mr_tracking_tab.py` | 16 | ✅ Cleaned + migrated |
| `src/tabs/history_manager.py` | 12 | ✅ Comments only |
| `src/tabs/ekyc_report_tab.py` | 9 | ✅ Cleaned + migrated |
| `src/tabs/home_tab.py` | 8 | ✅ Cleaned + migrated |
| `src/tabs/activity_log_tab.py` | 3 | ✅ Cleaned + migrated |
| `src/tabs/login_automation_tab.py` | 5 | ✅ Cleaned + migrated |
| `src/app/app_ui.py` | 1 | ✅ Cleaned + migrated |
| `src/app/app_navigation.py` | — | ✅ Cleaned + migrated |
| Other tab files | 1–6 each | ✅ Cleaned (bulk pass) |

> Note: "Hinglish hits" = rough grep count of Hinglish words (kya/hai/nahi/karo/...). Many hits are internal code comments (not user-facing) — those are cleaned opportunistically but don't block users. Final audit result: **0 user-facing Hinglish strings + 0 Hinglish log messages remain** in `src/`.

### ✅ Phase 2 — i18n Framework (Desktop App)

| Task | Status |
|---|---|
| Create `src/i18n.py` (tr engine, language manager, state→language map) | ✅ |
| Create `src/locales/en.json` (clean English base) | ✅ |
| Create `src/locales/hi.json` (Hindi) | ✅ |
| Language settings UI (dropdown + state auto-suggest) in Settings → Default Values | ✅ |
| Migrate Settings tab strings to `tr()` | ✅ |
| Migrate shared dialogs in `base_tab.py` to `tr()` | ✅ |
| Migrate Home / sidebar / header-footer to `tr()` | ✅ |
| Migrate Login Automation, Activity Log, File Manager, About | ✅ |

### ✅ Phase 3 — Hindi Translation (first regional language)

- `hi.json` ships with clean Hindi translations for all migrated keys.
- Framework supports adding Marathi, Tamil, Telugu, Bengali, Gujarati, Punjabi, Odia, etc. — just add a `src/locales/<code>.json` file.
- Fonts: NotoSansDevanagari already bundled (used in PDFs); system fonts render Devanagari on Windows/macOS. More script fonts will be added per language as needed.

### ✅ Phase 4 — Bulk Mechanical Pass (all remaining tab files)

- Bulk pass completed on all remaining tab files: `from src.i18n import tr` added where needed + remaining hardcoded strings migrated.
- Remaining Hinglish **log messages** fixed to English (logs stay English per user decision).
- Final audit: **0 user-facing Hinglish strings, 0 Hinglish log messages** across `src/`.
- Full-project safety check: `python3 -m compileall src/` → clean, zero errors.

### ⏳ Phase 5 — Web Server (Admin Panel)

- Same i18n approach with locale JSONs + Hindi/English UI.
- State-wise language default on both platforms.

## 5. Design Rules (coding conventions)

1. **UI text** → always `tr("key")`; never hardcode user-visible strings.
2. **Keys are dot-namespaced:** `settings.location.info_banner`, `base.error.title`.
3. **English is the base file.** Other languages translate `en.json`.
4. **Logs stay English** (per user decision) — `tr()` is for UI only.
5. **Keep messages short & simple.** One clear sentence. No "info saved + sent to server" style extras unless relevant.
6. **Emojis allowed but minimal** — status indicators only, not in every sentence.
7. `tr()` never raises: unknown key → falls back to English → returns key name.

## 6. Progress Log (changelog of work done)

### 2026-08-10 — Session 1+2+3 (Completed)
- ✅ Full audit across `src/` (~47K lines, 55+ files).
- ✅ `src/i18n.py` + `src/locales/en.json` + `src/locales/hi.json`.
- ✅ Fixed flagged trust-issue message in `settings_tab.py`.
- ✅ **Language selector** in Settings → Default Values (dropdown + state auto-suggest).
- ✅ **15 Python files migrated** to `tr()` with clean English:
  - settings_tab, base_tab, home_tab, app_navigation, utils (error translations)
  - login_automation_tab, activity_log_tab, file_management_tab, about_tab
  - demand_tab, mr_tracking_tab, issued_mr_report_tab, physical_complete_tab
  - app_license
- ✅ 350+ clean English strings in `en.json` + Hindi in `hi.json`.
- ✅ All 17 files + 2 locale files pass syntax validation.

### 2026-08-10 — Session 4 (Bulk Mechanical Pass — COMPLETED)
- ✅ Built `scripts/audit_hinglish.py` + `scripts/audit_logs.py` + `scripts/audit_logs_detail.py` (reusable audit tools).
- ✅ Fixed remaining user-facing Hinglish strings → clean English across:
  - `app_license.py` (3 UI strings: browser login hint, server unreachable, session expired)
- ✅ Fixed remaining Hinglish **log messages** → English (logs stay English per user decision):
  - musterroll_gen_tab, mate_mr_gen_tab, work_allocation_tab, material_entry_tab,
    ekyc_report_tab, delete_applicant_tab, del_demand_tab
- ✅ Fixed 3 merge-corrupted lines (two statements on one line) in musterroll_gen_tab, mate_mr_gen_tab, work_allocation_tab.
- ✅ **Final audit: 0 Hinglish user-facing strings, 0 Hinglish log messages remain in `src/`.**
- ✅ **Locale completeness check: 157 keys used in code → 0 missing in `en.json`, 0 missing in `hi.json`.**
- ✅ `tr()` engine runtime-tested (English + Hindi).

### 2026-08-10 — Session 9 (Batch 2 Tabs — COMPLETED)
- ✅ **47 more in-tab form strings migrated** across 6 tabs: mis_reports, msr, zero_mr, duplicate_mr, mb_entry, pending_bills.
- ✅ `duplicate_mr_tab` was initially skipped by the batch-2 map — fixed via merged-map script (`scripts/migrate_form_labels_merge.py` reusing batch-1 `common.*` keys) → 10 strings wrapped.
- ✅ Shared strings (State:, Clear, 📥 Export to Excel, Output Action:, Merge PDFs...) now wrapped in ALL 14 migrated tab files via the merged map.
- ✅ `ws.title` reverted (openpyxl worksheet name is a data artifact, not UI).
- ✅ Internal values correctly left untouched: Landscape/Portrait (orientation), Work Codes (notebook tab), Auto from Workcode (config), JHARKHAND (state default).
- ✅ **Locale completeness: 422 keys used → 0 missing en/hi, 0 unused keys.**

### 2026-08-10 — Session 8 (In-Tab Form Labels — COMPLETED)
- ✅ **204 in-tab form strings migrated** in 8 most-used tabs: demand, wc_gen, musterroll_gen, mate_mr_gen, material_entry, mr_tracking, if_edit, sarkar_aapke_dwar.
- ✅ Covers: form labels (State:/Panchayat:), buttons (Upload Report, Load Categories), placeholders (search, work key), section headers (Step 1/2/3), file-dialog titles, info hints.
- ✅ **149 new locale keys** (`common.*` shared + `form.<slug>.*` per-tab) with Hindi translations via `scripts/migrate_form_labels.py`.
- ✅ **Hinglish placeholder fixed** — demand_tab work-key hint now clean English in en.json (was: "demand ke baad selected workers is par allocate honge").
- ✅ **Safety fixes from code review:** reverted 3 `.set(tr(...))` wraps on internal-key StringVars (notebook tab name, automation-mode, scheme-type); removed 3 dead locale keys; fixed activity_log panchayat-filter comparison to use translated value.
- ✅ **Locale completeness: 400 keys used → 0 missing in en.json, 0 missing in hi.json; 0 unused keys.**
- ⚠️ **Known limitation (documented):** OptionMenu `values=[...]` that double as internal config keys (output action, orientation, automation mode, scheme type) stay English until a value/display mapping layer is added — naive translation would break config save/load.

### 2026-08-10 — Session 7 (Full UI Hindi Coverage — COMPLETED)
- ✅ **Root cause fixed:** Sidebar (44 tab names + 8 categories), header/footer and tab-page headers were all hardcoded English.
- ✅ **Display-layer translation** (internal English keys preserved — navigation/config/history unaffected):
  - `app_navigation.py`: tab buttons, category titles, Home button, category-filter dropdown (translated display + reverse-map to English keys).
  - `app_ui.py`: Ready / STOP ALL / welcome banner / all 12 header tooltips / running indicator.
  - `app_automation.py`: "▶ Running:" prefix + automation chip names.
  - `home_tab.py`: automation card names + category headers on the Home page.
  - `lite_app.py`: Lite app sidebar tabs + categories.
  - `base_tab.py`: ▶ Start / ■ Stop / ↺ Reset buttons (visible on EVERY tab).
  - **39 tab files**: header titles + subtitles migrated to `tr("tab.<slug>.title/subtitle")` via `scripts/migrate_tab_headers.py`.
- ✅ **`tr()` upgraded** with `default=` fallback param (safe for dynamic names — never shows raw key).
- ✅ **Locale coverage: 254 keys used in code → 0 missing in en.json, 0 missing in hi.json.**
- ✅ **Language switch now applies immediately** (sidebar + home + header refresh) — restart optional for full effect.
- ✅ 148 new Hindi translations written (sidebar, header, all 39 tab headers).
- ✅ New dev tools: `scripts/migrate_tab_headers.py`, `scripts/add_missing_keys.py`, `scripts/translate_hi.py`, `scripts/check_missing_keys.py`.
- ✅ Full `compileall src/` + lite_app/main_app syntax + runtime Hindi spot-checks pass.

### 2026-08-10 — Session 6 (PyInstaller Build Bundling — COMPLETED)
- ✅ Added explicit `--add-data="src/locales:src/locales"` to ALL build paths (previously only implicit via `src:src`):
  - `scripts/build_windows.bat` (MAIN + LITE)
  - `scripts/build_macos.sh` (MAIN + LITE)
  - `scripts/build_beta_portable.bat` (onefile + folder modes)
  - `.github/workflows/release.yml` (CI build)
  - `NREGABot.spec` + `NREGABot Lite.spec` (datas list)
- ✅ Verified bundled load path: `_locales_dir()` resolves to `_MEIPASS/src/locales` ↔ matches `--add-data` destination.
- ✅ Verified `scripts/build_update.py` smart-update zip already includes `src/locales/*.json` (`.json` whitelisted, `locales` not skipped).
- ✅ Cleaned stray `src/locales/__pycache__`.

### 2026-08-10 — Session 5 (Code Review + Final Validation — COMPLETED)
- ✅ Code review by AI reviewer — 2 findings, both resolved:
  1. Verified `from src.i18n import tr` (sed-inserted) is at module **top-level scope** in `mr_tracking_tab.py` and `app_license.py` (not inside docstring/comments).
  2. Full-project `python3 -m compileall src/` → clean, zero errors (catches any latent line-merges in earlier edits).
- ✅ Added `base.retry_failed_confirm` to `en.json` + `hi.json` (completeness — docstring example key).
- ✅ Final completeness re-check: **157 keys used in code → 0 missing in en.json, 0 missing in hi.json**.
- ✅ `tr()` runtime-tested in English + Hindi (verified `settings.language.title` → "Language"/"भाषा").

### 2026-08-10 — Session 10 (Batch 3 Tabs — COMPLETED)
- ✅ **19 in-tab form strings migrated** across 5 tabs: emb_verify, add_activity, scheme_closing, physical_complete, jobcard_verify (via `scripts/migrate_form_labels3.py` + merged common.* map).
- ✅ **38 dialog arguments wrapped** in `scripts/migrate_dialogs3.py` (messagebox titles/messages → `dialogs.*` keys).
- ✅ **Remaining unwrapped English dialogs fixed** (found by code review): scheme_closing + physical_complete "No Data"/"Success" PDF-saved dialogs → reuse `errors.no_data` + `status.success` + `export.pdf_saved`; jobcard_verify "Automation Error" → `base.automation_error.title` + new `errors.an_error_occurred`; scheme_closing confirm dialog → `dialogs.confirm_scheme_closing` + new `dialogs.scheme_closing_confirm_msg` (dynamic f-string → `{scheme}` placeholder).
- ✅ 3 phantom keys (never existed in code/locales) cleaned; 5 dead `errors.*` keys removed from en+hi.
- ✅ Internal values correctly left untouched: `Junior Engineer(BP)` designation dropdown values (config save/load comparisons).
- ✅ **Locale completeness: 468 keys used → 0 missing en/hi, 0 unused keys; full compileall passes; runtime Hindi spot-checks pass.**

### 2026-08-10 — Session 11 (Batch 4 Tabs + Automation-Safety — COMPLETED)
- ✅ **78 in-tab form strings + dialogs migrated** across 4 tabs: work_allocation, wagelist_gen, fto_generation, update_estimate (via `scripts/migrate_batch4.py`).
- ✅ **Automation-safe migration** — verified NOTHING that matches the live website was translated:
  - `By.ID`/`By.TAG_NAME`/`By.CSS_SELECTOR` element locators (self.CATEGORY_ID, self.SEARCH_KEY_ID, ...) — untouched
  - `select_by_visible_text(inputs['work_category'])` — value comes from config, not translated
  - `send_keys(work_key)` — data values, untouched
  - `on`/`off` checkbox StringVar values (wagelist save_pdf_var) — untouched
  - notebook tab names (`Work Key List`, `Results`, `Settings`) — internal identifiers, NOT translated
- ✅ **Notes translated** (user request — "jo bhi likha hua hai wo bhi english aur hindi me translate"): fto_generation long instruction note → `form.fto.instructions`; wagelist panchayat-selector hint → `form.wagelist.panchayat_hint`.
- ✅ **Remaining Hinglish fixed**: work_alloc export dialog "Isse Demand tab me 'Upload Report' se load karo — work key khud set ho jayega" → clean English `dialogs.export_csv_saved`; "Koi allocated labourer nahi mila..." → `dialogs.no_allocated_labourers`.
- ✅ **Reviewer gaps closed**: variable-message dialog titles (Input Error:347, Critical Error:353, Browser Error:177, Export Error:955), `\n`-containing messages manually wrapped, 3 dead `confirm.yes/no/cancel` + 8 dead `base.*` keys removed.
- ✅ **Locale completeness: 528 keys used → 0 missing en/hi; full compileall passes; runtime Hindi spot-checks pass.**
- ⚠️ Note: 152 statically-“unused” keys are false positives — they are accessed dynamically (`tr(f"nav.tab.{slug}")`, `settings.*`, `export.*`, `status.*`) and must NOT be removed.

### 2026-08-10 — Session 12 (Batch 5 Tabs — COMPLETED)
- ✅ **55 in-tab form strings + dialogs migrated** across 4 tabs: wagelist_send, del_work_alloc, sad_update, abps_verify (via `scripts/migrate_batch5.py` + 8 manual fixes).
- ✅ **Automation-safe migration** — verified NOTHING that matches the live website was translated:
  - sad_update action dropdown `["Dispose", "Reject", "In Progress", "Pending"]` + `action_map` (→ website values 0/1/2/3) — UNTOUCHED (known limitation documented)
  - `By.ID "ctl00_*"` locators + `select_by_value(fin_year)` — UNTOUCHED
  - checkbox on/off StringVar values — UNTOUCHED
- ✅ **Notes translated**: sad_update bot-scan hint → `form.sad.bot_scan_hint`; wagelist_send f-string note → `form.wagelist_send.will_send` ({count}); wagelist_send dropdown-not-found dialog.
- ✅ **Reviewer gaps closed**: `\n`-message partial wrap fixed (retry_wagelists), sad_update:461 "Error" variable-message title wrapped, 1 dead key (`no_wagelists_fy_retry`) removed — FSTRING entry never matched actual source.
- ✅ **Locale completeness: 566 keys used → 0 missing en/hi; full compileall passes; runtime Hindi spot-checks pass; 0 partial messagebox wraps remain.**

### 2026-08-10 — Session 13 (Batch 6 Tabs — COMPLETED)
- ✅ **60 in-tab form strings + dialogs migrated** across 3 tabs: mr_fill, pdf_merger, workcode_extractor (via `scripts/migrate_batch6.py` + manual fixes).
- ✅ **professional_pdf.py intentionally skipped** — zero user-facing UI strings (pure PDF-generation utility).
- ✅ **Automation-safe migration** — verified NOTHING that matches the live website was translated:
  - mr_fill `By.XPATH //*[contains(text(), 'No Future Dates Plz')]` website text match — UNTOUCHED
  - 12 `By.ID` locators (ddlWorkCode, txtSearch, ImgbtnSearch, lblmsg, ddlMsrNo, btnsave...) — UNTOUCHED
  - pdf_merger filedialog titles — wrapped (user-facing)
- ✅ **workcode_extractor 3-part note** (💡 Note: Go to the [MR Tracking Page], copy the entire table...) — split into prefix/link/suffix keys; link label is display-only (webbrowser bind) → safe.
- ✅ **Key collisions fixed** (reviewer finding): `dialogs.reset_confirm_results` (batch-3), `dialogs.could_not_create_dir` (batch-5), `common.merge_pdfs` (batch-2) were re-used with different texts → split into `dialogs.reset_confirm_all`, `dialogs.could_not_create_out_dir`, `form.pdf_merger.merge_btn`; en/hi values restored to consistent originals.
- ✅ **Locale completeness: 617 keys used → 0 missing en/hi; full compileall passes; runtime Hindi spot-checks pass; 0 unwrapped messageboxes remain.**

### 2026-08-10 — Session 14 (Batch 7 Tabs — COMPLETED)
- ✅ **67 in-tab form strings + dialogs migrated** across 4 tabs: nmms_attendance, issued_mr_report, resend_rejected_wg, macro_manager (via `scripts/migrate_batch7.py` + manual fixes).
- ✅ **Automation-safe migration** — verified NOTHING that matches the live website was translated:
  - macro_manager task-type dropdown values ("Bulk Demand (CSV)", "Wagelist Gen + Auto Send", ...) — INTERNAL DISPATCH KEYS compared via `if choice == "Bulk Demand (CSV)"` + passed to `_update_input_fields` — UNTOUCHED
  - nmms 23 `By.XPATH`/`By.TAG_NAME` class-attribute locators — UNTOUCHED
  - macro_manager notebook tab names ("Execution Queue", "Logs & Status") — internal identifiers — UNTOUCHED
- ✅ **Hinglish docstring fixed** — macro_manager `_update_input_fields` docstring ("Dropdown change hone par inputs ko badalta hai") → clean English.
- ✅ **Reviewer gaps closed**: `status.copied` bang-collision reconciled (consistent EN/HI), 1 dead key (`form.macro.logs_status`) removed, multiline messageboxes (nmms Browser Not Connected + No Table Found) wrapped with `{preview}` placeholder.
- ✅ **Locale completeness: 668 keys used → 0 missing en/hi; full compileall passes; runtime Hindi spot-checks pass.**

### 2026-08-10 — Session 15 (Final Repo-Wide Dialog Sweep — COMPLETED)
- ✅ **79 remaining unwrapped messageboxes migrated** across 11 files: demand (19), musterroll_gen (19), wc_gen (15), settings (7), msr (6), file_management (5), base (4), if_edit (3), sad_update (1), mis_reports (1), ekyc_report (1).
- ✅ **Settings-tab Hinglish dialogs rewritten to clean English** — Backup/Restore/Clear Server Data, Scrape Failed, Reset Defaults, Factory Reset, "Dono fields bharo" fix.
- ✅ **~25 Hinglish code comments + docstrings converted to clean English** across 15 files (mr_tracking, home_tab, about_tab, file_management, mb_entry, material_entry, issued_mr, ekyc, work_allocation, etc.).
- ✅ **Automation-safe verified** — settings placeholder sentinels ("Select a State", "Select District") are INTERNAL comparison values (`if state == "Select a State"`) → left English (documented); all By.ID/By.XPATH/select_by_visible_text locators untouched.
- ✅ **~72 new `dialogs.*`/`settings.*`/`file_manager.*` keys added** (en + hi), reusing existing keys wherever text matched.
- ✅ **Reviewer fixes applied**: mb_entry info-card label fully wrapped (was half-English), indirect `messagebox` callback forms (`self.app.after(0, messagebox.showinfo, ...)` in file_management) wrapped, dead `form.mb_entry.workcode_hint` merged into a single combined key.
- ✅ **Locale completeness: 885 keys used → 0 missing en/hi; compileall passes; 0 unwrapped messageboxes (direct + indirect); 0 Hinglish anywhere in src/.**
  - Note: `nav.*`/`settings.*` keys flagged as "dead" by static scan are actually used dynamically via `tr(f"nav.tab.{name}")` / `tr(f"nav.cat.{cat}")` — intentionally kept.

### 2026-08-11 — Session 16 (Kannada + Bengali Locales — COMPLETED)
- **User-base research (Rajasthan / Karnataka / West Bengal)**: Rajasthan → Hindi already covered ✅; Karnataka → **Kannada** (66.5% mother tongue); West Bengal → **Bengali** (85.9% mother tongue).
- ✅ **`src/locales/kn.json` created** — complete 1039-key Kannada translation (Kannada script).
- ✅ **`src/locales/bn.json` created** — complete 1039-key Bengali translation (Bengali script).
- ✅ Both registered automatically — `LANGUAGES` + `STATE_LANGUAGE_MAP` in `src/i18n.py` already mapped `KARNATAKA → kn`, `WEST BENGAL → bn` (framework was ready, only files were missing).
- ✅ **Translation workflow**: `scripts/translations_{kn,bn}_1..5.py` (namespace-by-namespace) + `scripts/build_locales.py` builds `<code>.json` from the part files, reporting missing/unused per language (1039/1039, 0 missing, 0 unused).
- ✅ **Validation**: JSON valid, key parity 0 missing in all 4 locales, **0 placeholder mismatches** ({name}, {count}, {error}, ...) in kn/bn, 0 non-str values, runtime smoke tests pass (welcome/nav/dialog/form/settings/status strings render in Kannada & Bengali).
- ✅ **Packaging**: no build changes needed — `.spec` files (`('src/locales', 'src/locales')`) and `--add-data="src/locales:src/locales"` bundle the whole directory, so kn.json/bn.json ship automatically.
- ✅ **`scripts/check_missing_keys.py` upgraded** — now checks ALL locale files (en/hi/kn/bn) instead of just en/hi.
- ✅ **Reviewer fixes applied**: `build_locales.py` hardened (fail-fast exit on missing/unused keys + stricter sorted-list placeholder parity check + "generated artifact" header warning); doc section 7 rewritten to document the part-files + `build_locales.py` workflow; CI got a `validate-locales` job (check_missing_keys + rebuild kn/bn + `git diff --exit-code` drift check) that gates all build jobs in `release.yml`.

### 🎯 Overall status: DESKTOP APP CLEANUP + i18n MIGRATION COMPLETE ✅
- All user-facing text in `src/` is now clean English (base) + translatable via `tr()`.
- **885 `tr()` keys** used; **4 locales live** (`en`, `hi`, `kn`, `bn`) — 0 missing in all four.
- **Final audits: 0 user-facing Hinglish strings, 0 Hinglish log messages, 0 Hinglish comments** in `src/`.
- **Full `compileall src/` passes clean; 0 unwrapped messageboxes repo-wide.**

### ⏳ Remaining (non-blocking)
- ✅ **DONE: PyInstaller build config now bundles `src/locales/*.json` explicitly** (Session 6) — all 4 build scripts + 2 spec files + CI. New locale files (kn/bn) ship automatically via directory bundling.
- Add more languages (Marathi, Tamil, Telugu, etc.) — see section 7; Kannada/Bengali serve the current Rajasthan/Karnataka/West Bengal user base.
- Phase 5: web server language support (separate plan).

## 7. How to Add a New Language

**Recommended — parity-checked workflow (used for `kn`/`bn`):**

1. Create `scripts/translations_<code>_1..5.py` with namespace part dicts (`KN1`-style), following the existing `translations_kn_*.py` pattern (nav/tab/common…, dialogs, form, settings).
2. Import the parts in `scripts/build_locales.py` and add `<code>` to its build loop.
3. Run `python3 scripts/build_locales.py` — it builds `<code>.json`, reports **missing keys / unused entries / placeholder mismatches**, and exits non-zero on any issue (fail-fast).
4. Add the language to `LANGUAGES` in `src/i18n.py` and add a state mapping in `STATE_LANGUAGE_MAP` (e.g. `"MAHARASHTRA": "mr"`).
5. Run `python3 scripts/check_missing_keys.py` — confirms 0 missing across **all** locale files.
6. Ship — the Settings dropdown picks it up automatically; PyInstaller bundles the whole `src/locales/` dir.

> ⚠️ `kn.json` / `bn.json` (and any file built by `build_locales.py`) are **GENERATED artifacts** — edit the part files, never the `.json` directly, or your edits get overwritten on the next build.

**Quick path (no build script):** copy `en.json` → `<code>.json` and translate in place. Works, but skips the parity/placeholder validation.

**CI:** the release workflow runs `validate-locales` (check_missing_keys + rebuild kn/bn + git-diff drift check) before any build job.
