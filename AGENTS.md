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
- **NAS SSH state (12 Aug 2026):** SSH + **key auth WORKING** (user `rajat` → account `Rajat`, home `/var/services/homes/Rajat`, DSM case-insensitive). Mac key `~/.ssh/id_ed25519` (`rajatpoddar-macbook`) NAS ke `authorized_keys` mein hai; `~/.ssh/config` entry (`IdentityFile` + `UseKeychain`) bani hai → push bina password. **⚠️ GOTCHA:** NAS home folder world/group-writable ho to OpenSSH key auth reject karta hai (`Permission denied (publickey,password)`) — fix: NAS par `chmod 755 ~`. DSM kabhi-kabhi home perms 775/777 reset kar deta hai (SMB/reboot ke baad) — tab key auth dobara fail ho to yahi fix. Ye sab changes sirf USER karta hai — agent sirf commands batata hai.
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
9. **Translations — JSON GENERATED hai (CI build breaker ⚠️):** `src/locales/kn.json`, `bn.json`, `hinglish.json` are **build artifacts** — CI me `scripts/build_locales.py` unhe `scripts/translations_{kn,bn,hing}_{1..5}.py` se regenerate karta hai aur **missing/unused/placeholder-mismatch par exit 1** karta hai (release fail). Naye i18n key add karne ka SAHI tarika:
   1. `en.json` (+ `hi.json`) me key add karo — ye dono directly edited hain.
   2. **Teeno part files** (`translations_kn_5.py`, `translations_bn_5.py`, `translations_hing_5.py` — last part) me bhi wahi key add karo (translated).
   3. `venv/bin/python scripts/build_locales.py` run karo → **exit 0** hona chahiye. `{placeholder}` tokens sab languages me **identical** hone chahiye (CI check karta hai).
   JSON me direct key edit karke CI fail hota hai — ye 3.2.3 release me hua tha (missing 6 keys).
10. **Version bump — CHHOTA bump + hashes KHAALI (deploy user ka kaam hai):** version bump sirf patch level karo (e.g. 3.2.2 → 3.2.3), feature bump nahi. `src/config.py` + `config/version.json` (latest_version, URLs, core_update version, changelog entry English me) update karo, aur `core_update.hash` / `hash_windows` / `hash_macos` teeno ko `""` set karo. **Kabhi `scripts/build_update.py` run mat karo aur hashes mat fill karo** — ye user khud `scripts/deploy_version.sh` se karta hai (Windows hash GitHub se auto-fill, Mac hash `build_macos.sh` se).
11. **NAS commands / server push — SIRF USER (HARD RULE, see §1.5):** NAS (`192.168.29.101`) par koi command execute mat karo aur `nrega-server` remote par kabhi push mat karo — chahe SSH kaam kar raha ho ya nahi, chahe push fail ho raha ho. Sirf copy-paste commands batao aur user ke confirm karne ka wait karo. (Incident: 11 Aug 2026 — agent ke SSH attempts se DSM Auto Block ne Mac IP block kar diya, deploy ruk gaya.)

## 4.5. 🗺️ State Registry (server-driven) — naya state add karna

**Naya state (Bihar, UP, ...) ab app-release ke bina add hota hai** — admin panel
(`/admin/portal-states`) se. Desktop app har ~2 min `/api/app-config` se `states`
fetch karke built-in `STATE_*` dicts par override karta hai.

| Data flow | File |
|---|---|
| Registry table + seed | `nrega-server/migrations/024_state_registry.sql` (`portal_states`) |
| `/api/app-config` → `states` field | `nrega-server/app/routes/api/auth.py` (`app_config()`) |
| Admin manage page | `nrega-server/app/routes/admin/states.py` + `app/templates/admin/admin_portal_states.html` |
| Client registry (sanitized) | `src/config.py` — `update_state_registry()`, `get_state_portal_host()`, `get_state_demand_config()`, `get_state_job_card_prefixes()`, `get_state_portal_url()` |
| Registry fetch in heartbeat | `src/app/app_license.py` (`_ping_server_in_background`, app-config block) |
| Demand-tab consumers | `src/tabs/demand_tab.py` (`_get_state_options`, `_detect_state_from_report`, `start_automation`) |

**Per-state fields:** `state_key`, `portal_host` (VB-G-RAM-G host), `job_card_prefix`
(e.g. `BR-` — job-card auto-detect), `demand_base_url`, `village_code_logic`
(`jh`/`rj`/`ka`), `is_active`, `sort_order`.

**Rules:**
- Built-in `STATE_PORTAL_HOSTS` / `STATE_DEMAND_CONFIG` / `STATE_JOB_CARD_PREFIXES`
  **sirf fallback** hain — seed values unse match karte hain. Registry entry override
  karti hai.
- Registry tabhi use hoti hai jab entry sanitized hai (strings only) — invalid
  server payload kabhi crash nahi karta.
- `get_state_portal_url()` sirf `vbgramgde\d+`/`nregade\d+.dord.gov.in` hosts
  re-host karta hai — report/MIS (vbgramgrep) aur public (mnregaweb) untouched.
- `PENDING_BILLS_CONFIG` (src/config.py) alag hai — liability-report scraper ka
  apna state map (state_code/seed_digest). Iska registry integration baad ka
  kaam hai, abhi manual edit se add hota hai.

## 4.11. 🌐 Location Data Pool (block-wise panchayat/village sharing) — 3.2.5+

Users jinke paas portal par na PO na GP login milta hai wo panchayat/village
select nahi kar paate. Iska fix: har user apne saved block data
(`location_hierarchy.json` → panchayat→villages) ko server par sync karta hai;
same-block ke doosre users wo data directly fetch karke dropdowns ready kar
lete hain — bina scrape ke.

| Data flow | File |
|---|---|
| Pool table | `nrega-server/migrations/027_location_data_pool.sql` (`location_data_pool` — state/district/block/panchayat + villages JSONB + source_keys sha256 hashes) |
| Sync endpoint | `nrega-server/app/routes/api/location_data.py` — `POST /api/location-data/sync`, `GET /api/location-data/get` (rate limits: `rate_limit_config.py` → `location_data` / `location_data_get`) |
| Repo | `nrega-server/app/repositories/location_data_repo.py` |
| Client module | `src/location_sync.py` — `sync_current_location(app)` (silent, 10-min throttle), `fetch_block_from_server()`, `apply_server_data()` (sirf missing merge — local edits kabhi overwrite nahi) |
| Sync triggers | `settings_tab._scrape_success` (force), `base_tab._save_panchayat_villages_to_settings` (GP auto-add), automation finish |
| Download UI | `settings_tab._download_block_data` — "🌐 Block Data Download" button |
| Onboarding | `ui_components.py` `_fetch_pool_background/_apply_pool_result` — server data mile → green tick → Next (bina login ke bhi) |

**Rules:**
- Names UPPER-normalized; DPDP: server par sirf `sha256(license_key)` jata hai (raw key kabhi nahi).
- Merge sirf missing — user ke local edits kabhi overwrite nahi.
- Sab kuch silent background — kabhi crash nahi; server down ho to next cycle retry.

## 4.6. 🚨 Error-Spike Alerts (per-automation fail-rate watchdog)

`app/error_spike_monitor.py` activity_logs se har `ERROR_SPIKE_CHECK_INTERVAL`
(default 300s) par last `ERROR_SPIKE_WINDOW_MINUTES` (60) ki per-automation
fail rate nikalta hai — `>ERROR_SPIKE_THRESHOLD_PCT` (10%) aur
`>=ERROR_SPIKE_MIN_RUNS` (5) hone par admin ko WhatsApp alert (triage ke
liye top affected states ke saath). Per-automation `ERROR_SPIKE_COOLDOWN`
(3600s) spam guard; `ERROR_SPIKE_ALERT_WHATSAPP` (fallback
`UPTIME_ALERT_WHATSAPP`) unset ho to alerts skip.

| Piece | File |
|---|---|
| Monitor (fcntl lock, in-memory cooldown, bounded query) | `nrega-server/app/error_spike_monitor.py` |
| Startup registration | `nrega-server/run.py` (uptime monitor ke saath) |
| Admin config card + last-check + test button | `nrega-server/app/routes/admin/uptime.py` + `app/templates/admin/admin_uptime.html` |

**Note:** Monitor in-memory cooldown use karta hai (uptime_monitor pattern —
fcntl lock single-worker guarantee) — Redis API dependency nahi. Koi migration
nahi. Yahan alert-message template edit karo agar format badalna ho.

## 4.7. 📊 State Analytics (per-state health)

`app/routes/admin/state_analytics.py` — `/admin/state-analytics` page har state
ka health check dikhata hai (5-min cache, `admin:state-analytics`):

| Metric | Source |
|---|---|
| Users / Active Paid / Trials (30d) | `licenses.user_state` |
| Runs (30d) / Fail Rate | `activity_logs` (30d window, `success`/`failed`/`error`) |
| Revenue / Tx / Est. MRR | `payments` + plan prices (`FIRST_TIME_PRICES`) |
| Registry status (✅/⚠️) | `portal_states` — unregistered states amber banner + `State Registry` link |

**Rules:**
1. `user_state` messy hota hai (`JH`, `jharkhand`, `WEST BENGAL`) — `_STATE_ALIASES`
   casefold + abbreviation mapping se canonical name banata hai (duplicate rows nahi).
   Naya state add karte waqt alias bhi check karo.
2. `payments` table empty ho to revenue 0 dikhta hai — query sahi hai.
3. CSV export `/export-state-analytics` cached data se (5-min stale OK).
4. Reuse: `_pct`/`_PLAN_MONTHS`/`_PLAN_KEYS` revenue.py se, `_IST_TZ` dashboard.py se.

## 4.8. 🔔 Renewal Reminders (churn prevention)

`whatsapp_automator.py::check_expiry_reminders()` — expiry se 7/3/1 din pehle
(`whatsapp_templates.send_before_days`, default `[7, 3, 1]`) user ko WhatsApp
reminder + **early-bird offer** bhejta hai. Daily scheduler `ai_autopilot.py`
se chalta hai (`run_all_automation_checks`).

**Rules:**
1. **Dedup** — `renewal_reminders` table (migration 025), PK `(license_key, stage)`.
   Har stage per license sirf EK baar; send SUCCESS ke baad hi mark hota hai
   (fail → agli baar retry). Scheduler din me multiple baar chale to bhi
   duplicate nahi.
2. **Already-renewed skip** — pichhle 8 din me payment (`payments` table) aayi
   ho to reminder nahi jaata.
3. **Early-bird offer** — env: `RENEWAL_EARLY_BIRD_PCT` (default `10`),
   `RENEWAL_EARLY_BIRD_COUPON` (default empty). Placeholders `{early_bird_discount}`,
   `{early_bird_coupon}`, `{early_bird_line}` (`whatsapp_placeholders.py` se).
   Template ka offer line migration 025 se add hota hai (sirf agar `early_bird`
   pehle se template me nahi — admin custom message preserve hota hai).
4. **Admin visibility** — WhatsApp Automation page par "Renewal Reminders" card
   (upcoming 7/3/1d + sent today/total) — `automation_config.py::
   whatsapp_automation_stats_api` se.
5. Naya reminder stage add: template ke `send_before_days` se (admin editable).

## 4.9. 🧹 Admin sidebar (cleanup — 11 Aug 2026)

Admin panel ko solo-admin friendly banaya gaya: sidebar me 5 links merge/hide kiye (routes
**hatae NAHI** — sirf sidebar se hataye + cross-links daale):

| Page | Kahan gaya |
|---|---|
| WhatsApp Broadcast | WhatsApp Automation page par **Manual Broadcast** button |
| Manage Templates (email) | Mailing Center page par **Email Templates** button |
| Reseller Requests | Resellers page par **Reseller Requests** button |
| Rate Limits | Uptime page par **Rate Limits** button |
| Find Duplicates | DB Maintenance page par **Duplicate Users** section (true merge — `cleanup.py` ab duplicates bhi query karta hai) |

Dead template `nrega-license-server-new.html` delete kiya. Naya section header: Messaging /
Database & Ops / DB Maintenance. Naya page add karte waqt sidebar ke inhi sections me daalo.

## 4.10. 🔀 Trial Funnel (trial→paid conversion) — 12 Aug 2026

`app/routes/admin/funnel_analytics.py` — `/admin/funnel` page. **⚠️ CRITICAL
DATA MODEL (live-DB discovery): trial users upgrade hone par SAME key rehti
hai, sirf `key_type` badalta hai (trial → monthly/paid/...).** Isliye trial
population `key_type='trial'` se NAHI, key prefix `NREGABOT-TRIAL-%` se
define hoti hai (172 keys, 61 upgraded). Ye `revenue.py` ke trial→paid email-join
query ko bhi affect karta hai — wo query bhi cross-key conversions hi pakadti
hai (in-place upgrades miss karti hai) — funnel page iska sahi alternative hai.

| Stage | Signal |
|---|---|
| Trial Registered | `key LIKE 'NREGABOT-TRIAL-%'` (trial-origin, upgrade-proof) |
| Activated | `last_seen NOT NULL` (app launch/heartbeat) ya activity_logs |
| Converted | `key_type <> 'trial'` (in-place upgrade) ya payments par key |
| Renewed (KPI only) | 2+ payments on key — `payments` table abhi sparse (1 row) isliye 0 dikhega, future metric |

Cohort table (trial month × trials/activated/converted), drop-off analysis
(sabse bada drop + actionable msg), 5-min Redis cache (`admin:funnel-analytics`),
CSV export. Funnel stages strictly nested hain (converted counted sirf activated
keys par). Agar key generation format kabhi badle to `_TRIAL_PREFIX` update karo.

## 4.12. 🔔 Account Notifications (storage full + data-deletion warning) — 16 Aug 2026

Customer interaction upgrade: user ke account par kuch hota hai (storage full,
license expired + data baaki) to wo khud WhatsApp + Email se informed hota hai.

| Piece | File |
|---|---|
| Events + dedup tables + templates | `nrega-server/migrations/028_account_notifications.sql` (`storage_warnings`, `data_deletion_warnings`) |
| Scheduler checks | `nrega-server/app/whatsapp_automator.py` — `check_storage_full()` + `check_data_deletion_warning()` (registered in `run_all_automation_checks`) |
| Placeholders | `nrega-server/app/whatsapp_placeholders.py` — `license_key`, `storage_used`, `storage_limit`, `storage_percent` |
| Dual-channel (WhatsApp + Email) | `nrega-server/app/notify_service.py` — `EVENT_DEFAULT_CHANNELS` |
| Admin toggles/templates | `nrega-server/app/routes/admin/automation_config.py` + `admin_whatsapp_automation.html` |

**Rules:**
- `storage_full`: threshold `interval_config.threshold_pct` (default 90) — 100%
alag stage. **Re-notify:** `interval_config.re_notify_days` (default 30) — full
rehne par har N din me EK baar dobara warn (roj roj nahi — spam guard);
send ke baad `sent_at` refresh hota hai. **Upgrade/refill reset:** storage
upgrade (storage.py `verify_storage_payment`, payment_service plan upgrade,
admin files `update_storage`) par `storage_warnings` dedup rows DELETE hote
hain — usage gir ke dobara full hone par NAYA warning milta hai. Storage
usage = `user_files` SUM (validate_key jaisa); legacy `max_storage NULL` →
500 MB fallback.
- `data_deletion_warning`: expired + cloud data → warning. `grace_days` (90)
after expiry = deletion deadline; `warn_days` (30) pehle warn. **Actual data
deletion yahan NAHI hota — sirf warning** (template admin edit karta hai).
- Email body `notify_service._send_email_channel` ko `email_subject`/`email_body`
se milta hai (Jinja `{{ user_name }}` etc.) — checks dono bhejte hain.
- License key ab `build_context` me hamesha hota hai (`{license_key}`) — har
template me use kar sakte hain (migration ne existing templates me bhi append
kiya). Web login (frontend/auth.py) ab expired user ko block + buy-page redirect
karta hai (signed token — raw key URL me nahi).

## 4.13. 💲 Pricing (admin-editable plan + storage prices) — 16 Aug 2026

Application ka price change ab code change ke bina hota hai: Admin → **Pricing**
(`/admin/pricing`). Prices `app_settings` JSON me (DB override), module constants
sirf defaults hain.

| Piece | File |
|---|---|
| Read/write helpers | `nrega-server/app/services/license_service.py` — `get_price_table(cur, table)`, `save_price_table(cur, table, prices)` |
| Admin page | `nrega-server/app/routes/admin/pricing.py` + `app/templates/admin/admin_pricing.html` |
| Buy page | `nrega-server/app/routes/frontend/pages.py::buy_page` (price_tables) |
| Order amount | `license_service.calculate_order_amount()` (DB price) |
| Revenue / MRR | `revenue.py`, `state_analytics.py` (get_price_table) |
| Storage order API | `nrega-server/app/routes/api/storage.py` (server-side price — client amount trust NAHI) |

**Rules:**
- Tables: `first_time`, `renewal`, `storage`. app_settings keys: `first_time_prices`,
  `renewal_prices`, `storage_prices`. Partial override OK — missing keys defaults se.
- **Har jagah `get_price_table(cur, table)` se padho — constants (`FIRST_TIME_PRICES`
  etc.) seedha kabhi use mat karo**, warna admin change dikhega nahi.
- `calculate_order_amount` + buy page + revenue/MRR + storage API sab DB-aware hain.
- Storage order amount ab **server-side** se aata hai (client bheja `amount` ignore
  hota hai — security fix bhi). Plans: 1gb/5gb/10gb (+ legacy 25gb).
- Reset button → JSON rows delete (defaults par wapas).

## 4.14. 🔗 Login OG tags — 16 Aug 2026

`app/templates/public/base.html` me OG/Twitter meta tags add kiye (og:image →
`https://nregabot.com/assets/og-banner.webp?v=3`, 1200x633). Pehle WhatsApp me
link share karne par bada raw logo dikhta tha (koi og:image nahi tha). Blocks:
`og_title` / `og_description` / `twitter_title` / `twitter_description` — page
overwrite kar sakta hai, default marketing-site values hain.

## 5. Common tasks → where to edit

| Task | Files |
|---|---|
| Footer / status / running indicator | `src/app/app_ui.py`, `src/app/app_automation.py`, `lite_app.py` |
| Add/change a portal automation tab | `src/tabs/<tab>_tab.py` + `src/tab_config.py` (+ `src/config.py` for URLs) |
| Sidebar category or tab | `src/app/app_navigation.py`, `src/tab_config.py` |
| License / activation | `src/app/app_license.py`, `src/managers/services.py` |
| Update flow | `loader.py`, `lite_loader.py`, `src/managers/services.py`, `scripts/build_update.py`, `config/version.json` |
| Macro / multi-tab workflow | `src/managers/workflow_manager.py` |
| Add/edit a VB-G-RAM-G state (no release) | Admin → **State Registry** (`/admin/portal-states`); data flow: `024_state_registry.sql` → `auth.py app_config()` → `src/config.py` registry → heartbeat fetch |
| Revenue / MRR / churn / expiry forecast | Admin → **Revenue Dashboard** (`/admin/revenue`); `nrega-server/app/routes/admin/revenue.py` + `admin_revenue.html` |
| App plan + storage prices change (no release) | Admin → **Pricing** (`/admin/pricing`); `nrega-server/app/routes/admin/pricing.py` + `admin_pricing.html`. Prices `app_settings` JSON me (DB override), defaults `license_service.py` (`FIRST_TIME_PRICES`/`RENEWAL_PRICES`/`DEFAULT_STORAGE_PRICES`) — **hamesha `get_price_table(cur, table)` se padho, constants seedha kabhi nahi** (buy page, order amount, revenue/MRR, storage API sab isi se chalti hain) |
| Theme / colors | `src/config.py` (`COLORS`), `config/theme.json` |
| Translations | **`en.json` + `hi.json` directly edit karo; `kn.json`/`bn.json`/`hinglish.json` GENERATED hain — unhe kabhi directly edit mat karo.** Source of truth = `scripts/translations_{kn,bn,hing}_{1..5}.py` part files. Naya key add: en.json (+ hi.json) + teeno part files (last part `_5` me) me add karo → `venv/bin/python scripts/build_locales.py` run karo (CI yahi chalta hai; exit 0 chahiye) → generated JSON khud update ho jata hai. Helpers: `check_missing_keys.py` (code vs locales), `add_missing_keys.py`. |
| Release a new version | **CHHOTA bump** (patch, e.g. 3.2.2 → 3.2.3) — `APP_VERSION` (config.py) + `config/version.json` (latest_version, URLs, core_update version, changelog) → **core_update ke teeno hashes (`hash`, `hash_windows`, `hash_macos`) ko `""` KHAALI karo** → commit + push (CI builds). **Agent hashes fill/build_update.py kabhi NAHI chalaata** — user khud `scripts/deploy_version.sh` chala ke hashes + deploy karta hai (wo script Windows hash GitHub se auto-fill karti hai; Mac hash `build_macos.sh` banata hai). |
| Feature telemetry (usage_stats) | Client: `history_manager.py` (sync method) + `app_automation.py` (trigger). Server: migration → repo → `/api/usage-stats/sync` → admin page. |
| Tab search / keyboard shortcuts | `src/app/app_navigation.py` (`_on_nav_search_change`, `_shortcut_*`). |

## 6. Project state (current)

- **Version:** 3.2.5 — `config/version.json` is source of truth; `src/config.py` me `APP_VERSION` (dono sync rakho).
- **Users:** ~200+ active (Jharkhand base) — Rajasthan, Karnataka, Bihar users aa rahe hain. **Production.** Scaling roadmap: `docs/SCALING_PLAN_200_to_10000.md` (living doc — naya kaam wahi se phase-wise pick karo).

## 6.5. 📡 Feature Telemetry (Feature Popularity) — 3.2.3+ / server deploy 023

Desktop app har automation finish par apni local `usage_stats` (automation_key → count, SQLite `nrega_local_db.sqlite`) ko server par bhejta hai:

```
history_manager.sync_usage_stats_to_server()  (called from on_automation_finished)
        │  POST /api/usage-stats/sync   (PII-free: sirf key+count+app_version)
        ▼
usage_stats table (migration 023)  →  admin /admin/feature-popularity
```

- **Client:** `src/tabs/history_manager.py` → `get_usage_stats_all()` + `sync_usage_stats_to_server()`. Trigger: `src/app/app_automation.py` `on_automation_finished()` (activity-log sync ke saath). Background daemon thread, kabhi raise nahi karta, silent retry next cycle.
- **Server:** `nrega-server/migrations/023_usage_stats.sql` (table: `license_key, automation_key, count, app_version, last_synced_at`, PK = (license_key, automation_key)), `nrega-server/app/repositories/usage_stats_repo.py`, `nrega-server/app/routes/api/usage_stats.py` (rate-limited: `USAGE_STATS_SYNC_PER_KEY_RATE` default 60/hr, per-IP 600/hr — `rate_limit_config.py` me registered).
- **Admin:** `nrega-server/app/routes/admin/usage_stats.py` → `/admin/feature-popularity` (top automations, state-wise, version-wise). Sidebar: **Feature Popularity** (Database & Files section).
- **Naya telemetry type add karna ho to:** API route + migration + repo + admin page — activity_log/usage_stats pattern copy karo.

## 6.6. ⌨️ Tab Search + Keyboard Shortcuts — 3.2.3

- **Tab Search:** sidebar me search box (Ctrl+K focus) — 55 tabs me case-insensitive dhundho. Code: `src/app/app_navigation.py` `_on_nav_search_change()` / `_clear_nav_search()` / `_focus_nav_search()`. Placeholder i18n: `nav.search_placeholder` (`tr()` default fallback, locale key optional).
- **Shortcuts (global, guarded — entry/text focus me nahi chalti):**
  - `Ctrl+Enter` → current tab automation **start** (`_shortcut_start`)
  - `Ctrl+S` → current tab **stop** (`_shortcut_stop`)
  - `Ctrl+R` → current tab **retry failed** (`_shortcut_retry`)
- **Bindings `bind_all` + `add="+"` + one-time flag** (`_nav_search_shortcut_bound` / `_automation_shortcuts_bound`) — nav rebuild par duplicate bind nahi hote.
- **Repo layout:** project root = desktop app; `nrega-server/` = Flask backend (alag deployable, has own Dockerfile).
- **`.vscode/tasks.json`:** tasks ab **manual** hain — `runOn: folderOpen` hata diya gaya hai (user demand). Folder kholte hi koi terminal nahi khulta; kabhi wapas mat add karna.
- **`config/theme.json`** + `assets/` fonts/sounds/icons — UI assets ka central home.

## 7. Delivery-model gotcha (release ke waqt yaad rakho)

- **Agent hashes kabhi fill mat karo:** `config/version.json → core_update` ke `hash`,
  `hash_windows`, `hash_macos` — ye user khud bharता hai. Version bump karte waqt inhe
  `""` (empty) karo. `scripts/build_update.py` / `scripts/build_macos.sh` agent run nahi
  karta — sirf user deploy karta hai (`scripts/deploy_version.sh`).
- Deploy flow (user ke liye): `build_macos.sh` → `git push` (CI Windows/Linux builds) →
  `deploy_version.sh` (hash_windows auto-fill + NAS upload + verify).
- Same version + different hash = hotfix re-download mechanism.
- Dev me seedha `python main_app.py` chalta hai.
