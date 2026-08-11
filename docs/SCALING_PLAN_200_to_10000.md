# 🚀 NREGA Bot — 200 → 10,000 Users Scaling & Expansion Plan

> **Purpose:** Aaj 200 users (Jharkhand) → kal 10,000 users (all India). Yeh document batata hai:
> kya-kya sectors missing hain, kya rewrite karna hai, 10k users ke liye kaunsi "bonus" cheezein
> chahiye, admin panel me kya-kya dikhna chahiye, UX ko friendly kaise banayein, kaunsa data
> collect karein, business model kaise expand karein, aur maintenance ko smooth kaise rakhein.
>
> **Date:** August 2026 · **Current version:** 3.2.3 · **Audience:** Product owner (Rajat) + future team

> ## 📌 PROGRESS UPDATE — 11 Aug 2026: PHASE 1 COMPLETE ✅
>
> **"Multi-State + Visibility" phase ke saare core items ship ho chuke hain** (server-side built,
> deploy backlog baki — section 13 dekho):
>
> - ✅ **State Registry (DB-driven)** — `portal_states` table (migration 024) + admin page
>   (`/admin/portal-states`) + desktop heartbeat refresh. Naya state = **admin se add, koi release nahi**.
> - ✅ **Revenue Dashboard** (`/admin/revenue`) — MRR ₹2081/4378, churn 35%, LTV, expiry forecast 7/30/60/90 + CSV
> - ✅ **State Analytics** (`/admin/state-analytics`) — per-state users/activity/fail-rate/revenue/MRR,
>   registry-aware (unregistered states amber banner)
> - ✅ **Error-Spike Alerts** — per-automation fail >10% → admin WhatsApp (cooldown + test button)
> - ✅ **Feature Popularity** (usage_stats sync → server) · ✅ **Tab search + keyboard shortcuts**
> - ⏸️ **Bihar portal config** — defer kiya tha; ab registry ke through admin se hi add ho sakta hai (release ki zaroorat nahi)
>
> **➡️ Abhi ka sabse logical next step:** (1) Deploy backlog ship karo, (2) **churn prevention —
> WhatsApp renewal reminders** (revenue dashboard ne churn 35% + 30 din me ~15 licenses expiring dikhaya
> — ye sabse bada business leak hai). Phase 2 infra (CDN/canary/managed PG) tab tak wait kare jab users
> ~1000-2000 cross karein.
>
> ---

## 📋 Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current System Snapshot (kya pehle se hai)](#2-current-system-snapshot)
3. [Sector Gap Analysis — kya-kya missing hai](#3-sector-gap-analysis)
4. [What Needs Rewrite / Refactor](#4-what-needs-rewrite--refactor)
5. [Scaling to 10,000 Users — Architecture](#5-scaling-to-10000-users--architecture)
6. [Admin Panel — Everything You Should See](#6-admin-panel--everything-you-should-see)
7. [UX & User-Friendliness Functions](#7-ux--user-friendliness-functions)
8. [Data to Collect (UX + Business ke liye)](#8-data-to-collect)
9. [Business Model Expansion](#9-business-model-expansion)
10. [Maintenance & Operations](#10-maintenance--operations)
11. [Prioritized Roadmap (Phase-wise)](#11-prioritized-roadmap)
12. [Metrics to Track (KPIs)](#12-metrics-to-track)

---

## 1. Executive Summary

| Dimension | Aaj (200 users) | Target (10,000 users) |
|---|---|---|
| **States supported** | Jharkhand, Rajasthan, Karnataka (config me) — Bihar users aa rahe hain | 25+ states, per-state portal configs DB-driven |
| **Users** | ~200 (license-based) | 10,000+ concurrent users |
| **Support model** | WhatsApp + admin panel | Self-serve diagnostics, automated triage, state-wise support desk |
| **Error visibility** | Admin Error Logs + Crashes tab ✅ | Real-time monitoring + auto-categorization + auto-fix deployment |
| **Server infra** | Single NAS docker-compose (Flask + PG + Redis) | Multi-node / managed DB, CDN, auto-scaling, high availability |
| **Revenue** | Monthly/Quarterly/Yearly plans + reseller | Tiered plans, team licenses, distributor model, services |
| **Data security** | DPDP PII masking ✅ | Full DPDP consent flow + breach notification + audit |
| **Reliability** | Best-effort | SLAs, uptime monitoring, canary updates, auto-rollback |

**Sabse important principle:** Scale karne se pehle **visibility** chahiye. Jab tak aapko pata nahi
ki 10,000 users me se kis state me kaunsa tab fail ho raha hai, koun upgrade nahi kar raha, kis
ka license 3 din me expire hone wala hai — tab tak scale karna andha hona hai.

---

## 2. Current System Snapshot

> ✅ Jo pehle se hai, use dobara mat banao. Yeh inventory hai — roadmap iske **aage** ka kaam hai.

### 2.1 Desktop App (jo hai)

| Area | Status | Notes |
|---|---|---|
| 55 automation tabs (MR, eMB, Schemes, Verify, Reports, Tools) | ✅ | `src/tab_config.py` lazy-loaded |
| 5 languages (EN, HI, KN, BN, Hinglish) | ✅ | `src/locales/*.json`, CI-verified |
| Loader + core-zip SHA-256 verified updates | ✅ | `loader.py`, `config/version.json` |
| Activity log → server sync | ✅ | SQLite → `/api/activity-log/sync` (batched 50) |
| Crash reporter + server upload | ✅ | `install_crash_reporter()`, `/api/crash-report`, admin Crashes tab |
| Screenshot on failure | ✅ | Local `Temp/error_screenshots/` (server upload baki) |
| Error traceback + last-30-log-lines | ✅ | `error_traceback` column, admin collapsible |
| Heartbeat (`licenses.last_seen`) | ✅ | `/api/heartbeat` — active user tracking |
| User level detection (GP/PO) | ✅ | `set_user_level()` → heartbeat → admin |
| Cloud backup/restore of user data | ✅ | `/api/user-data/backup` |
| Macro manager (sequential queue) | ✅ | `workflow_manager.py` |
| WhatsApp notifications + daily report | ✅ | Evolution API + 6 AM daily report |
| Onboarding tour, factory reset, theme | ✅ | v3.2.2+ |
| Per-state portal configs | ✅ | `portal_states` DB registry (migration 024) + admin page — naya state bina release ke |
| Feature usage stats | ✅ | `usage_stats` sync → server + Feature Popularity admin page |

### 2.2 Server (jo hai)

| Area | Status | Notes |
|---|---|---|
| Flask + PostgreSQL + Redis + Celery + Gunicorn | ✅ | Docker Compose on NAS |
| License validation, trials, payments (Razorpay) | ✅ | Subscriptions + one-time |
| Admin panel (25+ sections) | ✅ | Dashboard, users, transactions, activity, crashes, rate-limits, uptime, ops, features, broadcast, coupons, chat, files, audit, bulk-extend, resellers, referrals, promo, mailing, locations, cleanup, AI control center, WhatsApp automation |
| **Ops Overview page** | ✅ | Live runs, success rate, active users (15m/24h/7d), error rate by version, top failing automations, crash trend, update adoption |
| Crash reports + admin Crashes tab | ✅ | Version/OS/type/traceback/last-log, filters, export |
| Rate limiting (per-key + per-IP) + admin page | ✅ | Flask-Limiter + Redis |
| Uptime watchdog + WhatsApp alerts | ✅ | `/healthz` + internal monitor (DB/Redis/Evo/WebDAV) |
| Activity log retention (180 days) | ✅ | Migration 016, archive + purge |
| DPDP PII masking | ✅ | Client + server (`pii_mask.py`), migration 019 backfill |
| Versioned migrations (022) | ✅ | Checksum-protected, auto-apply on boot |
| Daily DB backups (30 days retention) | ✅ | `backup-new` service |
| Web frontend + user dashboard | ✅ | `/account`, `/activity`, buy page, reseller panel, OAuth/Passkey |
| AI bot + command center | ✅ | `ai_bot.py`, admin AI control center, autopilot |
| Release sync (auto-pull GitHub releases) | ✅ | `release_sync.py` → `/updates` folder |

### 2.3 Kya abhi bhi missing hai (one-glance)

| Missing | Severity |
|---|---|
| Missing | Severity | Status |
|---|---|---|
| **Multi-state expansion** (Bihar/UP/MP/other states ke portal configs) | 🔴 Critical | ✅ DONE — `portal_states` registry, admin se add |
| **Feature telemetry to server** (`usage_stats`) | 🔴 High | ✅ DONE — sync + Feature Popularity page |
| **Revenue/MRR analytics** in admin | 🔴 High | ✅ DONE — `/admin/revenue` |
| **State-wise breakdown** in admin | 🟠 High | ✅ DONE — `/admin/state-analytics` |
| **Error-spike alerts** (auto → WhatsApp) | 🟠 High | ✅ DONE — `error_spike_monitor.py` |
| **Tab search + keyboard shortcuts** | 🟡 Medium | ✅ DONE |
| **Retention / cohort / funnel analytics** (trial→paid) | 🟠 High | ✅ DONE (12 Aug 2026 — `/admin/funnel`, cohorts + drop-off) |
| **WhatsApp renewal reminders + expiry offers** | 🔴 High | ⬜ **NEXT BEST** — churn 35% se direct fight |
| **Offline-first + queue + auto-resume** (rural internet) | 🟠 High | ⬜ |
| **Scheduled automations** (roz ka task bina user ke chale) | 🟡 Medium | ⬜ |
| **In-app notification center** | 🟡 Medium | ⬜ |
| **Canary updates + auto-rollback** | 🟡 Medium | ⬜ (Phase 2, ~1000 users par) |
| **Push notifications** (license expiry, replies, new features) | 🟡 Medium | ⬜ (renewal reminders ke saath) |
| **API documentation** (public) | 🟢 Low | ⬜ |
| **Mobile companion app / PWA** | 🟢 Low | ⬜ |
| **Team/collaborator mode** | 🟢 Low | ⬜ |

---

## 3. Sector Gap Analysis

### 3.1 Naya State Add Karna ✅ DONE (DB-driven State Registry)

> **11 Aug 2026:** Solution implement ho chuka hai — `portal_states` table (migration 024) + admin
> page `/admin/portal-states` + desktop `update_state_registry()` (heartbeat se ~2 min me refresh).
> Bihar/UP/MP add karna ab = admin panel se ek form — **koi code change, koi release nahi**.
> `src/config.py` ke built-in dicts sirf fallback hain (server unreachable par app chalti hai).

**Problem (history):** `src/config.py` me sirf 3 states hardcoded hain:

```python
STATE_PORTAL_HOSTS = {
    "Jharkhand": "vbgramgde2.dord.gov.in",
    "Rajasthan": "vbgramgde3.dord.gov.in",
    "Karnataka": "vbgramgde2.dord.gov.in",
}
STATE_JOB_CARD_PREFIXES = {"JH-": "Jharkhand", "RJ-": "Rajasthan", "KA-": "Karnataka"}
```

Bihar (and upcoming states) ke liye har naya state add karna = code change + naya release.
**10,000 users ke liye ye kabhi nahi chalega** — states slow roll out honge aur har state ke
portal ke alag host/page-overrides/APIs honge.

**Solution (P0): State Registry — DB-driven ✅**
- `portal_states` DB table (migration 024) — state_key, portal_host, job_card_prefix,
  demand_base_url, village_code_logic, is_active, sort_order.
- Admin page `/admin/portal-states` — add/edit (UPSERT), activate/deactivate, delete.
- Desktop `/api/app-config` se registry fetch (heartbeat ~2 min) → `update_state_registry()` →
  `get_state_portal_host()/get_state_portal_url()/get_state_demand_config()` registry-aware.
- **Naya state = admin se add, koi app release nahi chahiye** ✅ (tested end-to-end).

### 3.2 Missing Automation Sectors (features jo nahi hain)

| Sector | Feature Idea | Why | Priority |
|---|---|---|---|
| **Payment Tracking** | Wagelist/FTO payment status tracker (paid/pending/rejected per FTO) — portal se scrape karke office-ready report | Payment follow-up roz ka kaam hai | 🔴 |
| **Aadhaar & DBT** | Aadhaar seeding verification + DBT registration status (per worker) | ABPS ke saath combo | 🟠 |
| **Job Card Bulk Operations** | Bulk job card correction (name/relation/DOB correction requests) | Data quality drive | 🟠 |
| **Attendance** | NMMS attendance ko **auto-schedule** karo (roz fixed time) + GPS-photo sync | Scheduled feature ke saath | 🟡 |
| **Social Audit** | Social Audit report scrape + **issue-vise response auto-fill** (abhi sirf report hai) | Compliance | 🟡 |
| **Asset/Geo-tagging** | Work site geo-tag + asset photo management | MGNREGA geo-tagging mandate | 🟡 |
| **MIS Analytics Module** | Portal MIS ko Excel me nahi, **comparative dashboard** me (block-wise progress) | Reporting upgrade | 🟢 |
| **Offline Queue** | Automation inputs ko queue karo; internet aate hi auto-resume | Rural internet | 🟠 |
| **Scheduled Runs** | "Har Monday 10 AM ko Zero MR submit ho jaye" | Power feature | 🟡 |

### 3.3 Missing Business Sectors (revenue ke liye)

| Sector | Description | Priority |
|---|---|---|
| **Team/Office Licenses** | Ek block office — 3-5 operator ek license (sub-accounts, per-operator limits) | 🔴 |
| **Distributor/State-Partner Model** | State-level distributor ko reseller API + dashboard (bada state le sakta hai) | 🔴 |
| **Training & Onboarding Services** | Paid 1:1 onboarding / workshop (state govt offices ko) | 🟠 |
| **Priority Support Tier** | "Pro support" plan — faster response, WhatsApp direct line | 🟡 |
| **API Access for Offices** | Office MIS integration ke liye licensed API | 🟢 |
| **Lite-Bundle Upsell** | Lite users ko main app upgrade funnel (in-app) | 🟡 |

---

## 4. What Needs Rewrite / Refactor

### 4.1 🔴 Rewrite karo (high value)

| # | File / System | Problem | Solution |
|---|---|---|---|
| 1 | **State configs in `src/config.py`** | Hardcoded 3 states; naya state = new release | DB/JSON-driven state registry (§3.1) |
| 2 | **Giant tab files** (some 1700+ lines) | Maintainability risk; team badhe par collision | Har tab ko 2-3 modules me tod do: `_ui.py`, `_logic.py`, `_parsers.py` (base_tab me common helpers) |
| 3 | **Selector/URL fragmentation** | Har tab apne selectors hardcode karta hai; state change par sab jagah fix | Central `portal_map.py` — per-state per-page selector+URL registry, tabs usse hi read karein |
| 4 | **Admin panel monolith templates** | `admin_*.html` bade hain, mobile-responsive nahi | Component-based templates + Chart.js 3.x upgrade + mobile responsive pass |
| 5 | **Server single-NAS deployment** | Single point of failure; NAS par bandwidth/storage limits | Managed Postgres (or replica), CDN for updates, 2nd app node (see §5) |

### 4.2 🟠 Refactor karo (medium)

| # | File / System | Problem | Solution |
|---|---|---|---|
| 1 | `base_tab.py` (2200+ lines) | Do kaam ek file me: UI + automation | UI helpers (`ui_components.py`) aur automation helpers (`automation_utils.py`) me split |
| 2 | `app_license.py` (2300+ lines) | License + backup + heartbeat + notifications sab ek me | LicenseMixin ko 3 focused mixins me tod do |
| 3 | **Old feedback vs chat dual system** | Desktop feedback tab purana API use karta hai, web chat naya — dono alag | Sab kuch unified `whatsapp_chat`/chat system par le ao (server pe already unified hai) |
| 4 | **`web/` static site vs Flask templates** | Marketing site alag, buy/trial alag | Web frontend ko Flask se serve karo (ya at least shared nav/design system) |
| 5 | **EVO secrets fallback defaults** | `config.py` me `NregaBotSecretKey123` fallback | Production me fallback remove karo; env-only; key rotate karo |

### 4.3 🟢 Keep as-is (touch mat karo)

- Loader + core-zip update architecture ✅ (production-grade)
- Migrations system ✅ (checksum-protected)
- PII masking pipeline ✅ (DPDP)
- WhatsApp queue pacing ✅ (anti-ban)
- Activity log sync ✅ (batched, retried)
- Rate limiting ✅

---

## 5. Scaling to 10,000 Users — Architecture

### 5.1 Load Expectations (10k users)

| Metric | 10k users | Load/day |
|---|---|---|
| Heartbeats (30 min cycle) | ~333 req/min avg | ~480k/day |
| Activity-log sync (50/batch) | ~5-20 syncs/user/day | ~100k/day |
| Automation results | ~1-5/user/day | ~50k/day |
| Update checks | ~1-2/user/day | ~20k/day |
| WhatsApp sends | ~3-5/user/day | ~50k/day |
| File uploads/downloads | ~1-2/user/day | ~20k/day |

**Server capacity (current):** Gunicorn 3-5 workers, PG pool 30 conns, NAS Docker.
10k users par **load balancer + 2 app nodes + managed DB** chahiye. Realistically NAS pe
~2-3k users tak OK hai; uske baad cloud migration plan banao.

### 5.2 Infrastructure Upgrades (priority order)

| # | Upgrade | Kya karein | Impact |
|---|---|---|---|
| 1 | **CDN for core zips + installers** | `config/version.json` URLs → Cloudflare R2 (already in use for files!) + CDN. NAS bandwidth me update downloads na aaye | 🔴 Critical |
| 2 | **Managed PostgreSQL / replica** | NAS PG → managed (e.g. Cloudflare D1 nahi — RDS/Supabase/Timescale) ya at least read-replica for admin dashboards | 🔴 Critical |
| 3 | **Redis upgrade** | Redis 7 → Redis Cloud/managed ya NAS me aage memory + persistence (AOF) | 🟠 |
| 4 | **2nd app node + LB** | 2nd VPS par Flask; nginx LB; sticky sessions off (stateless API) | 🟠 |
| 5 | **Auto-scaling Gunicorn** | Workers = f(load): `gunicorn --workers 8 --threads 4 --max-requests 1000`; horizontal = 2 nodes | 🟠 |
| 6 | **Object storage for user_uploads** | `user_uploads/` NAS local → R2 primary (abhi R2 pe bhi jaata hai — primary banao) | 🟠 |
| 7 | **Alerting + APM** | Error-spike alerts ✅ done; baki: Sentry (server) + uptime external probe (UptimeRobot guide already hai) | 🟠 |

### 5.3 Desktop App Scale-Safety (10k clients)

| # | Feature | Kya | Priority |
|---|---|---|---|
| 1 | **Canary updates** | `core_update` me `canary_percent` field — pehle 5% users ko update, crash-spike dikhe to auto-hold | 🔴 |
| 2 | **Auto-rollback** | Agar naya version crash rate > threshold (e.g. 3%) → server banner "known issue" + loader auto-downgrade | 🔴 |
| 3 | **Update bandwidth control** | Core zip ko compress (zopfli/brotli) + incremental patches (bsdiff) — KB-size hotfix ka promise hai, har baar full zip nahi | 🟠 |
| 4 | **Staggered sync** | Heartbeat/sync me random jitter (±5 min) — sab clients ek saath server pe na giren | 🟠 |
| 5 | **Offline queue** | Sync fail → local queue (already hai) → exponential backoff + retry (already retry hai, backoff add karo) | 🟠 |
| 6 | **Client-side feature flags** | Server `feature_flags` endpoint → naya feature server se on/off (admin Features page pe already hai — client ko poll karna baki) | 🟠 |
| 7 | **Low-end PC mode** | Lite build pehle se hai ✅; images-disabled Selenium mode + memory profiling | 🟢 |

### 5.4 "Bonus" Cheezein (sudden spike ke liye)

1. **Circuit breakers** — WhatsApp/email/R2 fail ho to queue karo, server 503 de na ki 500 spam.
2. **Graceful degradation** — Update server down → app "update check failed" me silently continue (already hai ✅).
3. **Bulk endpoints** — Automation results/activity sync already batched ✅; aur batch size tune karo.
4. **DB connection pool monitoring** — `metrics.py` already pool gauges ✅; alert jab pool exhaust ho.
5. **Load test script** — `locustfile.py` server repo me (10k virtual users ka smoke test).
6. **Rate limit tuning UI** — Admin rate-limits page already hai ✅; per-endpoint budgets set karo.
7. **Storage quotas enforcement** — 10k users × 500MB = 5TB; R2 lifecycle rules + quota alerts.

---

## 6. Admin Panel — Everything You Should See

> Abhi admin me 25+ sections hain ✅ — ye list uske **upar** ka hai: jo data abhi collect hota
> hai par dikhta nahi, ya jo collect karna chahiye.

### 6.1 🔴 Must-add (pehle 2 months) — ✅ 4/6 DONE

| # | Admin Section | Data Source | Kya dikhe | Status |
|---|---|---|---|---|
| 1 | **📈 Revenue Dashboard** | `payments` + `licenses` tables | MRR, new/renewed/churned licenses, LTV estimate, plan breakdown, payment failures, refunds, subscription churn rate, revenue forecast (next 30/60/90 days) | ✅ `/admin/revenue` |
| 2 | **🗺️ State-Wise Analytics** | `licenses.user_state` + `activity_logs` | Per-state: users, active (24h/7d), error rate, top automations, top failing automation — ek click me | ✅ `/admin/state-analytics` |
| 3 | **🔥 Feature Popularity** | `usage_stats` sync from desktop (§8) | Kaunsa tab kitni baar start hua, success rate per tab, top 10 features, least-used (delete/improve) | ✅ `/admin/feature-popularity` |
| 4 | **🔄 Funnel / Retention** | `licenses.created_at` + `payments` + heartbeats | Trial→paid conversion %, daily/weekly active, cohort retention (30/60/90 day), churn alerts | ⬜ NEXT (renewal reminders ke saath) |
| 5 | **⏳ License Expiry Forecast** | `licenses.expires_at` | Next 7/30/60 days me kitne licenses expire honge, renewal-reminder queue, expiring-soon CSV export | ✅ forecast part; ⬜ **auto reminder queue** (churn prevention) |
| 6 | **🚨 Error Spike Alerts** | `activity_logs` | Per-automation error rate threshold (e.g. >10%) → WhatsApp/email alert to admin — **automatic**, page dekhne ka wait nahi | ✅ `error_spike_monitor.py` |

### 6.2 🟠 Should-add (3-6 months)

| # | Section | Kya dikhe |
|---|---|---|
| 7 | **💬 Support SLA** | Feedback/chat first-response time, open ticket count by age, support load per day |
| 8 | **📦 Storage & Bandwidth** | Per-user storage used, R2 cost estimate, top 10 heavy users, cleanup suggestions |
| 9 | **📱 Device Fleet** | OS breakdown, app version distribution (already in ops ✅), low-end PC share, Lite vs Main |
| 10 | **🤖 AI Triage Inbox** | AI bot se auto-summarized new error patterns + suggested fixes (AI infra already hai — `ai_bot.py`) |
| 11 | **🎯 NPS / CSAT** | In-app survey results (1-10 rating after automation) |
| 12 | **🛡️ Security Center** | Failed logins, rate-limit hits, blocked IPs, admin audit log (exists ✅) + 2FA for admin |

### 6.3 Data Flow (jo implement karna hai)

```
Desktop (SQLite usage_stats) ──▶ /api/usage-stats/sync (batched, PII-free) ──▶ usage_stats table
Desktop (activity_log)        ──▶ /api/activity-log/sync (already ✅)       ──▶ activity_logs
Heartbeat (last_seen)         ──▶ /api/heartbeat (already ✅)               ──▶ licenses.last_seen
Admin Dashboard               ◀── aggregated queries + Redis cache (pattern already hai ✅)
```

---

## 7. UX & User-Friendliness Functions

### 7.1 🔴 High-impact (user retention ke liye)

| # | Feature | Kya | Effort |
|---|---|---|---|
| 1 | **🔍 Tab Search + Favorites** | Sidebar me search box (55 tabs!) + pin favorite tabs top pe | Small — `app_navigation.py` |
| 2 | **⌨️ Keyboard Shortcuts** | Ctrl+K search, Ctrl+Enter start, Ctrl+S stop, Ctrl+R retry, Alt+number tab switch | Medium |
| 3 | **📅 Scheduled Automation** | "Roz subah 10 baje Zero MR" — macro queue + scheduler (Windows Task Scheduler / macOS launchd / in-app timer) | Medium |
| 4 | **🛜 Offline Mode** | Bina internet bhi app kholo; inputs prep karo; internet aate hi sync+run | Medium |
| 5 | **🔔 Notification Center** | In-app bell: license expiry (30/7/1 din pehle), admin announcements, new features, replies | Small |
| 6 | **💡 Smart Suggestions** | Pichle runs se: "Aapne aaj 3 baar Zero MR chalaaya — schedule karna chahenge?" | Medium |
| 7 | **❓ In-app Help / Tutorials** | Har tab par "?" → YouTube/guide video + demo CSV download (demo CSVs already assets me ✅) | Small |

### 7.2 🟠 Medium-impact (polish)

| # | Feature | Notes |
|---|---|---|
| 8 | **Error messages "Fix karein" button** | Error dialog me already translation hai ✅ — "How to fix" + auto-open Settings/support add karo |
| 9 | **Dark mode complete coverage** | Legacy tabs check — `COLORS` central hai ✅, kuch tabs me hardcoded colors scan karo |
| 10 | **Progressive Web App (web)** | Web dashboard ko PWA banao — phone par "install" ho jaye |
| 11 | **Voice input (Hinglish/Hindi)** | Regional users ke liye — OS-level speech-to-text integrate karo (may be heavy; P2) |
| 12 | **WhatsApp-first UX** | Har automation ke baad WhatsApp par result bhejna already hai ✅ — "Reply to run again" add karo (WhatsApp chat automation already server pe hai!) |
| 13 | **Multi-PC sync improvements** | Cloud backup already ✅ — auto-sync on exit + conflict resolution banao |

### 7.3 🟢 Quick wins (aaj hi kar sakte hain)

- Tab search (sidebar filter) — 1 din
- Keyboard shortcuts — 2 din
- Notification center — 3 din
- Per-tab "?" help links — 2 din
- Scheduled automation (basic, Windows task via subprocess) — 4 din

---

## 8. Data to Collect

> ⚠️ **DPDP-compliant design:** Aadhaar/mobile PII **kabhi server pe nahi** — sirf anonymized
> aggregate + masked data. Opt-in consent screen with clear privacy notice (v3.2.1 docs already ✅).

### 8.1 Automation Telemetry (feature-level, PII-free)

| Event | Fields | Use |
|---|---|---|
| `automation_start` | tab_key, state, panchayat_count, input_type | Feature popularity |
| `automation_finish` | tab_key, success/failed, duration_seconds, rows_processed, error_type | Success rate per tab, per state |
| `automation_stop` | tab_key, reason (user/manual) | Abandonment analysis |
| `tab_open` | tab_key, session_id | Which tabs users explore |
| `sync_health` | last_sync_ok, pending_entries | Offline experience quality |

### 8.2 Device & Environment (masked)

| Field | Use |
|---|---|
| OS + version, app version (already in activity log ✅) | Update adoption, platform targeting |
| RAM/CPU tier (lite vs full) | Performance optimization, Lite upsell |
| Screen size | UI layout decisions |
| Browser type (Chrome/Edge/Firefox) | Support prioritization |

### 8.3 Business Funnel Data

| Funnel step | Metric |
|---|---|
| Web visit → trial registered | Conversion % |
| Trial → activated in app | Activation % |
| Activated → first automation run | Onboarding success |
| Trial → paid | **Conversion %** (most important) |
| Paid → renewed | Retention % |
| Paid → churned | Churn % + reason (exit survey) |

### 8.4 UX Feedback Loops

| Tool | Kya |
|---|---|
| **In-app NPS** | Automation ke baad: "Is feature ko rate karein (1-10)" — 1/month |
| **Exit survey** | License expire hone par: "Kyun renew nahi kiya?" (2-3 options) |
| **Error feedback** | Error dialog me "Ye galat hai" button → auto-sends error context (already crash/error pipeline ✅) |
| **Feature requests** | In-app "Request feature" → admin inbox (web pe already hai ✅) |

---

## 9. Business Model Expansion

### 9.1 Pricing Tiers (current: Monthly/Quarterly/Half-Yearly/Yearly)

| Tier | Price idea | Includes | Target |
|---|---|---|---|
| **Starter** (current monthly) | existing | 1 device, core features | Individual GRS |
| **Pro** | 2× monthly | 2 devices, scheduled automation, priority support | Serious operators |
| **Office/Team** | 3-5× (per 3 seats) | 3-5 sub-accounts, shared panchayat pool, admin for office | Block/Panchayat office |
| **Distributor/Reseller** | custom | API + dashboard + margin | State partners |
| **Enterprise/Institution** | yearly contract | Training, SLA, dedicated support, custom reports | BDO offices, NGOs, govt projects |

### 9.2 Revenue Streams (naye)

1. **Team licenses** (biggest near-term upside — office ek license 3-5 operators me share karta hai aaj, ise legalize + monetize karo)
2. **Distributor program** — har state me 2-3 active resellers (reseller panel already ✅)
3. **Training/onboarding service** — ₹500-2000/user onboarding session
4. **Priority support subscription** — ₹X/month, WhatsApp direct line
5. **Premium reports/analytics** — office-ready comparative dashboards (tier-gated)
6. **API license** — office MIS integration
7. **Renewal reminders with offers** — 7-din pehle WhatsApp reminder + early-bird discount (reduces churn, increases renewals)

### 9.3 Growth Levers (10k tak)

| Lever | Kya |
|---|---|
| **Referral program** | Already hai ✅ (15 days) — state-wise leaderboard banao |
| **State launches** | Har state ke WhatsApp community + local reseller + district-level demo |
| **Churn prevention** | Expiry alerts, exit surveys, annual plans discount |
| **Viral loop** | WhatsApp report forwarding (har report me "Made with NREGA Bot" footer) |
| **Content/SEO** | How-to videos (Hinglish/Hindi), state-specific guides on website |

---

## 10. Maintenance & Operations

### 10.1 Release Process (already strong — maintain it)

- Version bump (patch-only) → `config/version.json` (hashes empty) → push → CI builds ✅
- User runs `deploy_version.sh` → hashes filled + NAS upload ✅
- **Add:** Changelog template (English) + canary field in `core_update`

### 10.2 Server Deploy (already strong)

- Git push → webhook → `deploy.sh` (full) / `deploy_quick.sh` (app-only) ✅
- **Add:** Staging environment (same compose, port 4992, test DB) — deploy se pehle smoke test
- **Add:** Automated tests in CI (`pytest` server tests dir already hai ✅ — CI me run karo)
- **Add:** Rollback runbook — agar naya server version fail ho: `git checkout <prev>` + `deploy_quick.sh`

### 10.3 Monitoring & Alerting (critical for 10k)

| Check | Tool | Alert to |
|---|---|---|
| Server up | `/healthz` + UptimeRobot (guide already ✅) | WhatsApp |
| DB/Redis/Evo/WebDAV | `uptime_monitor.py` (already ✅) | WhatsApp |
| Error rate spike | ✅ DONE — `error_spike_monitor.py` (per-automation fail >10% → WhatsApp) | WhatsApp |
| Crash spike per version | NEW: canary monitor | WhatsApp |
| Disk space NAS | `df` cron + alert | WhatsApp |
| R2/bandwidth cost | R2 metrics + monthly review | Email |
| DB backup success | `backup-new` + daily email (already ✅) | Email |

### 10.4 Disaster Recovery (DR drill)

1. **Monthly restore test** — latest backup ko staging DB me restore karke verify karo (7 din me 1 baar kaafi)
2. **Point-in-time recovery** — PG WAL archiving enable karo
3. **Geo-redundant backup** — daily dump → R2 (off-NAS) bhejo (abhi NAS-local hi hai)
4. **Runbook** — `docs/RUNBOOK.md`: "server down" / "DB full" / "WhatsApp banned" / "core zip corrupt" — har scenario me 5 steps

### 10.5 Documentation

- `AGENTS.md` — already excellent ✅ (update as code changes)
- `docs/SCALING_PLAN_200_to_10000.md` — this file (living document, update every quarter)
- `docs/RUNBOOK.md` — NEW (ops scenarios)
- API docs — generate from route decorators (simple script)

---

## 11. Prioritized Roadmap

### Phase 1 — "Multi-State + Visibility" 🔴 → ✅ **COMPLETE (11 Aug 2026)**

| # | Task | Where | Status |
|---|---|---|---|
| 1 | **Bihar portal config** (host/page-overrides/demand URLs/jobcard prefix `BR-`) | registry (admin se add) | ⏸️ Deferred — ab admin se hi add hota hai, release nahi |
| 2 | **State registry (DB-driven)** — migration 024 + admin page + desktop refresh | `portal_states`, `src/config.py` | ✅ DONE (plan se better: DB, release-free) |
| 3 | **Revenue Dashboard** (MRR, churn, forecast) | `nrega-server/app/routes/admin/revenue.py` | ✅ DONE |
| 4 | **State-wise analytics** in admin | `admin/state_analytics.py` + `admin_state_analytics.html` | ✅ DONE |
| 5 | **`usage_stats` sync** + Feature Popularity admin page | desktop + `admin/usage_stats.py` | ✅ DONE |
| 6 | **Error-spike alerts** (per-automation threshold → WhatsApp) | `error_spike_monitor.py` + Uptime page | ✅ DONE |
| 7 | **Tab search + keyboard shortcuts** | `app_navigation.py` | ✅ DONE |

> **Phase 1 done. Abhi ka next step:** Deploy backlog ship karo (section 13) → **churn prevention
> (WhatsApp renewal reminders)** — sabse bada business leak (churn 35%, 30d me ~15 licenses expiring).

### Phase 2 — "Scale Infrastructure" 🟠 (tab shuru karo jab users ~1000-2000 cross karein)

> Abhi (234 users) infra upgrades premature hain — NAS ~2-3k users tak chalega. Pehle business
> retention (Phase 1.5) pakdo. **Phase 2 ka sabse pehla item CDN nahi, CANARY ho sakta hai** —
> kyunki har release ab 234+ users ko risk deta hai, canary crash-spike par auto-hold karta hai.

| # | Task | Trigger |
|---|---|---|
| 8 | CDN for core zips/installers (R2 + Cloudflare CDN) | ~1000 users |
| 9 | Canary updates + auto-rollback (loader + version.json) | aaj bhi kar sakte ho (release risk kam) |
| 10 | Managed Postgres migration plan (or replica for dashboards) | ~2000 users |
| 11 | 2nd app node + load balancer (VPS) | ~2000 users |
| 12 | Locust load test (target 10k) + Gunicorn tuning | ~1500 users |
| 13 | Offline queue + backoff (desktop) | rural users feedback |
| 14 | In-app notification center + expiry reminders | Phase 1.5 churn ke saath (desktop release) |

### Phase 3 — "Business & Retention" (Month 4-6) 🟡

| # | Task |
|---|---|
| 15 | Team/Office license tier + sub-accounts |
| 16 | Distributor program rollout (state partners) |
| 17 | Funnel/retention analytics + exit surveys |
| 18 | Scheduled automations |
| 19 | Support SLA dashboard + priority support tier |
| 20 | R2 primary storage + lifecycle rules |

### Phase 4 — "Ecosystem" (Month 7-12) 🟢

| # | Task |
|---|---|
| 21 | Mobile companion (PWA first) |
| 22 | API marketplace / office integrations |
| 23 | AI triage inbox (auto-summarized errors) |
| 24 | NPS + in-app surveys |
| 25 | Team collaboration mode (shared panchayat pool) |

---

## 12. Metrics to Track

| Metric | Definition | Target |
|---|---|---|
| **Active users (DAU/WAU)** | unique heartbeats 24h/7d | track + grow 20%/month |
| **Error rate** | failed runs / total runs | < 5% |
| **Crash-free sessions** | sessions without crash | > 99% |
| **Update adoption** | % on latest version (2 weeks) | > 90% |
| **Trial → paid conversion** | paid / trials | > 15% |
| **Churn rate (monthly)** | expired & not renewed | < 8% |
| **Renewal rate** | renewed / due | > 70% |
| **Support first-response** | time to first reply | < 4 hours |
| **Time-to-fix (P0 error)** | first seen → release | < 48 hours |
| **Per-automation success** | success per automation_key | >= 90% |
| **MRR** | monthly recurring revenue | track weekly |
| **LTV:CAC** | lifetime value / acquisition cost | > 3x |

---

## Appendix: Key File Map (iskay mutabiq kaam karo)

| Task | Files |
|---|---|
| Naya state add | `src/config.py` (STATE_PORTAL_HOSTS, STATE_DEMAND_CONFIG, STATE_JOB_CARD_PREFIXES) → migrate to registry |
| Tab search/shortcuts | `src/app/app_navigation.py`, `src/app/app_ui.py` |
| Feature telemetry | `src/tabs/history_manager.py` (usage_stats sync), `nrega-server/app/routes/api/activity_log.py` |
| Revenue dashboard | `nrega-server/app/routes/admin/dashboard.py` + `transactions.py` + templates |
| Canary updates | `config/version.json` (core_update.canary_percent), `loader.py`, `src/managers/services.py` |
| Error spike alerts | `nrega-server/app/routes/admin/ops.py`, `uptime_monitor.py` |
| Scheduled automation | `src/managers/workflow_manager.py`, new `scheduler_manager.py` |
| Notification center | `src/app/app_ui.py` (bell), server `app_settings` announcements |
| CDN/updates | `scripts/build_update.py`, `config/version.json`, `release_sync.py` |
| Team licenses | `nrega-server/app/routes/admin/licenses.py`, `services/license_service.py`, `src/app/app_license.py` |

---

## 13. 📌 Progress Log (update har implementation ke baad)

### 11 Aug 2026 — Phase 1 COMPLETE

**Ship ho gaya (server, deploy backlog baki):**

| Item | Files | Deploy note |
|---|---|---|
| State Registry (DB + admin) | `migrations/024_state_registry.sql`, `app/routes/admin/states.py`, `admin_portal_states.html`, `src/config.py` (client), `app_license.py` (heartbeat) | Server push + desktop release |
| Revenue Dashboard | `app/routes/admin/revenue.py`, `admin_revenue.html` | Server-only |
| State Analytics | `app/routes/admin/state_analytics.py`, `admin_state_analytics.html` | Server-only |
| Error-Spike Alerts | `app/error_spike_monitor.py`, `run.py`, `admin/uptime.py`, `admin_uptime.html` | Server-only (env: `ERROR_SPIKE_ALERT_WHATSAPP`) |
| Feature Popularity | (pehle se ship) | — |

**Validation done:** migration 024 applied ✅ · revenue dashboard real-DB build ✅ · state analytics
real-DB build (Jharkhand 229 users) ✅ · error-spike synthetic spike 87.5% detect ✅ · sab render
200 + auth 302 + CSV export ✅ · code reviews ×3 ✅

**Deploy checklist (baaki kaam):**
1. `git -C nrega-server push` → NAS deploy (server-only items turant live)
2. Desktop changes next release ke saath (registry client code) — version bump patch-level, hashes `""`
3. `.env` par: `ERROR_SPIKE_ALERT_WHATSAPP` (ya `UPTIME_ALERT_WHATSAPP`) — Uptime page se test button

**Next implement (recommended):**
1. ✅ **Churn prevention — WhatsApp renewal reminders DONE** (below entry dekho)
2. ✅ Funnel/retention analytics (trial→paid) — DONE 12 Aug 2026 (`/admin/funnel`: stages 172→164→61, cohorts, drop-off). Baaki: daily/weekly active + cohort retention (30/60/90d) charts.
3. 🟠 Scheduled automations (Phase 3 #18) ya Canary (Phase 2 #9).

### 11 Aug 2026 (2) — Churn prevention: WhatsApp renewal reminders ✅

`whatsapp_automator.py::check_expiry_reminders()` ab production-ready (migration 025):

| Feature | Kya |
|---|---|
| 7/3/1 din reminders | Pehle se tha (`send_before_days`); ab hardened |
| **Dedup** | `renewal_reminders` table (PK license_key+stage) — scheduler multiple runs par bhi ek baar |
| **Already-renewed skip** | Window me payment ho to reminder nahi (window = max stage + 1 din) |
| **Early-bird offer** | `{early_bird_line}` placeholder — env `RENEWAL_EARLY_BIRD_PCT` (10) + `RENEWAL_EARLY_BIRD_COUPON` |
| **Coupon validity** | Invalid/expired coupon → code omit (kabhi checkout par reject nahi) |
| **Admin visibility** | WhatsApp Automation page — Renewal Reminders card (upcoming 7/3/1d + sent today/total) |

**Validation:** migration 025 applied ✅ · 7d fires ✅ · dedup (2nd run 0 sends) ✅ · renewed-skip ✅ ·
3d stage ✅ · invalid-coupon omit ✅ · stats API + page render 200 ✅ · code review ×1 ✅

**Deploy:** server-only — `git -C nrega-server push` (migration 025 auto-applies). `.env` par
`RENEWAL_EARLY_BIRD_COUPON` tab tak mat dalo jab tak Coupons page par code create na ho.

### 11 Aug 2026 (3) — Admin panel cleanup + server push ✅

- Sidebar 29 → 24 links, 5 clean sections (Overview / User Management / Messaging / Finance &
  Sales / Database & Ops).
- Merges: Broadcast→WhatsApp Automation hub, Email Templates→Mailing, Reseller Requests→Resellers,
  Rate Limits→Uptime, Find Duplicates→DB Maintenance (true merge, `cleanup.py`).
- Dead template `nrega-license-server-new.html` deleted. Saare 28 admin pages render 200 verified.
- **Server pushed** — is session ke saare changes (registry, revenue, state-analytics, error-spike,
  renewal reminders, admin cleanup) NAS deploy ho gaye (migrations 024+025 auto-apply).

---

*Ye document living hai — har implementation ke baad section 13 update karo. 200 → 10,000 tak ka
rasta visibility (✅ done), state support (✅ done), retention (abhi), aur revenue model se hokar
jaata hai. Phase 1 complete — ab churn prevention + deploy backlog pakdo.*
