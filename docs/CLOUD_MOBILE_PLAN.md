# NregaBot Cloud + Mobile Dashboard — Project Plan

> **Last Updated:** 20 August 2026
> **Status:** 🟢 Phase 1 In Progress — MR Tracking cloud automation built
> **Target:** Mobile se reports + daily tasks access karna bina desktop app ke

---

## 📌 Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Current State Analysis](#2-current-state-analysis)
3. [Solution Overview](#3-solution-overview)
4. [Technology Choices](#4-technology-choices)
5. [Architecture](#5-architecture)
6. [Phase 1: Cloud Reports Dashboard (Mobile-First)](#6-phase-1-cloud-reports-dashboard)
7. [Phase 2: Simple Automations via Cloud](#7-phase-2-simple-automations-via-cloud)
8. [Phase 3: Full Mobile Experience](#8-phase-3-full-mobile-experience)
9. [Database Schema Changes](#9-database-schema-changes)
10. [API Endpoints](#10-api-endpoints)
11. [Security Considerations](#11-security-considerations)
12. [Deployment Strategy](#12-deployment-strategy)
13. [Milestones & Timeline](#13-milestones--timeline)
14. [Risk Assessment](#14-risk-assessment)
15. [Progress Tracker](#15-progress-tracker)

---

## 1. Problem Statement

### Current Limitation
NregaBot desktop app **55 Selenium-based automation tabs** offer karta hai MGNREGA portal ke liye. Lekin:
- **Desktop zaroori hai** — har automation ke liye local Chrome/Edge launch hota hai
- **Mobile se kuch nahi kar sakte** — users ko laptop/PC access chahiye
- **Reporting dekhne ke liye bhi desktop chahiye** — even though reports sirf scrape+read hain
- **~200+ users** across Jharkhand, Rajasthan, Karnataka, Bihar — bahut se users ke paas consistent desktop access nahi hai

### User Need
> "Mobile se reports scrape kar payein aur kuch daily work wala task mobile se kar payein cloud browser ke sahare"

---

## 2. Current State Analysis

### Desktop App Architecture
```
loader.py → main_app.py (NregaBotApp) → src/
                                          ├── tabs/ (55 tabs)
                                          │   ├── base_tab.py (BaseAutomationTab)
                                          │   ├── demand_tab.py
                                          │   ├── mr_fill_tab.py
                                          │   ├── ... (53 more)
                                          ├── app/
                                          │   ├── app_automation.py (threading, cloud sync)
                                          │   ├── app_ui.py
                                          │   └── app_navigation.py
                                          ├── managers/
                                          │   └── browser_manager.py (Chrome/Edge/Firefox)
                                          └── config.py (URLs, COLORS, state configs)
```

### Existing Cloud Infrastructure (nrega-server)
```
nrega-server/
├── app/
│   ├── routes/
│   │   ├── api/
│   │   │   ├── auth.py (license validation, /api/app-config)
│   │   │   ├── storage.py
│   │   │   ├── usage_stats.py
│   │   │   └── location_data.py
│   │   ├── admin/ (revenue, pricing, state analytics, etc.)
│   │   └── frontend/ (buy page, login, etc.)
│   ├── repositories/
│   └── services/
├── migrations/ (001-028)
└── run.py
```

### Already-Built Pieces We Can Reuse
| Component | File | What It Does |
|---|---|---|
| Cloud Reports Sync | `src/app/app_automation.py` → `_sync_automation_results_to_cloud()` | Automation finish par results tree → server API POST |
| Activity Logging | `src/tabs/history_manager.py` | `log_automation_start/finish()`, `sync_activity_log_to_server()` |
| Feature Telemetry | `src/tabs/history_manager.py` | `sync_usage_stats_to_server()` |
| WhatsApp Notifier | `nrega-server/app/whatsapp_automator.py` | Daily reports, expiry reminders, renewal alerts |
| License System | `src/app/app_license.py` + `nrega-server/app/services/license_service.py` | Full license validation, feature flags |
| Report Path Utils | `src/utils.py` → `get_report_path()` | `~/Downloads/NregaBot/Report {FY}/<Category>/` |
| PII Masking | `src/utils.py` → `mask_columns_rows()` | Server sync boundary par Aadhaar/bank data mask |

### Key Limitation: Desktop Automation Flow
```python
# Current flow (per tab):
def start_automation(self):
    driver = self.app.get_driver()  # Launches Chrome/Edge/Firefox LOCALLY
    driver.get(url)                 # Navigates to MGNREGA portal
    # ... fill forms, scrape data ...
    self._tree_insert(self.results_tree, values)  # Show in UI
    # After finish:
    self.app.start_automation_thread(key, run_automation_logic, args)
```

**Problem:** `get_driver()` launches a LOCAL browser — cannot work from mobile/cloud.

---

## 3. Solution Overview

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                     │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Mobile Web Portal │  │ WhatsApp Bot     │            │
│  │ (Flask + Jinja2)  │  │ (Evolution API)  │            │
│  │ Responsive HTML5   │  │ Quick commands   │            │
│  │ - View reports     │  │ - /report daily  │            │
│  │ - Trigger tasks    │  │ - /track MR      │            │
│  │ - Download Excel   │  │ - Status updates │            │
│  └──────────────────┘  └──────────────────┘            │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS / WSS
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    SERVICE LAYER (Flask)                  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Report API    │  │ Task Queue   │  │ Auth/License  │  │
│  │ /api/reports  │  │ /api/tasks   │  │ (existing)    │  │
│  │ GET + filter  │  │ POST + status│  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘  │
│         │                  │                              │
│         ▼                  ▼                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Browser Worker Pool                     │   │
│  │                                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐               │   │
│  │  │ Obscura #1   │  │ Obscura #2   │  ...         │   │
│  │  │ (Docker)     │  │ (Docker)     │               │   │
│  │  │ CDP :9222    │  │ CDP :9223    │               │   │
│  │  │ 30 MB RAM    │  │ 30 MB RAM    │               │   │
│  │  └─────────────┘  └─────────────┘               │   │
│  └──────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    DATA LAYER                            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ PostgreSQL    │  │ Redis        │  │ File Storage  │  │
│  │ (existing DB) │  │ (task queue) │  │ (Excel/PDF)   │  │
│  │ + new tables  │  │              │  │               │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Technology Choices

### Why Obscura over Headless Chrome?

| Metric | Obscura | Headless Chrome |
|---|---|---|
| Memory per instance | **30 MB** | 200+ MB |
| Binary size | **70 MB** | 300+ MB |
| Page load speed | **85 ms** | ~500 ms |
| Startup time | **Instant** | ~2 seconds |
| Anti-detect | **Built-in** | None (easily blocked) |
| CDP Compatible | ✅ | ✅ |
| Docker Image | **~57 MB** | ~400 MB |
| License | Apache-2.0 (free) | Free |

**Impact on NAS:** Agar NAS par 8 GB RAM hai to:
- Chrome: 8 GB / 200 MB = ~40 concurrent sessions max
- Obscura: 8 GB / 30 MB = **~260 concurrent sessions** (6.5x better)

**Anti-detect benefit:** MGNREGA portal sometimes blocks automated requests. Obscura's stealth mode (fingerprint randomization, `navigator.webdriver = undefined`) solves this without proxy dependencies.

### Backend Stack (Existing + New)

| Component | Choice | Why |
|---|---|---|
| Web Framework | **Flask** (existing) | Already have nrega-server, no new dependency |
| Template Engine | **Jinja2** (Flask built-in) | Mobile-responsive HTML5 pages |
| CSS Framework | **Tailwind CSS CDN** | Zero install, mobile-first responsive |
| Task Queue | **SQLite + Threading** (Phase 1) → **Redis** (Phase 2) | Start simple, scale later |
| Browser Engine | **Obscura** (Docker) | Lightweight, anti-detect, CDP compatible |
| Browser Client | **Playwright** (Python) | CDP client for Obscura, familiar API |
| Real-time Updates | **Server-Sent Events (SSE)** | Simpler than WebSocket, works through proxies |
| WhatsApp | **Evolution API** (existing) | Already integrated |

---

## 5. Architecture

### 5.1 Component Interaction Flow

```
User Phone Browser
    │
    │ GET /cloud/dashboard
    ▼
┌─────────────────────────────────┐
│  Flask: cloud_routes.py          │
│  - Check license (existing)      │
│  - Query cloud_reports table     │
│  - Render mobile-responsive HTML │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Mobile Dashboard Page           │
│  ┌─────────────────────────┐    │
│  │ 📊 Today's Reports      │    │
│  │ ┌───────┐ ┌───────┐    │    │
│  │ │Demand │ │MR Track│    │    │
│  │ │ 12 ✅ │ │  5 ✅  │    │    │
│  │ └───────┘ └───────┘    │    │
│  │ ┌───────┐ ┌───────┐    │    │
│  │ │Pending│ │eKYC   │    │    │
│  │ │Bills  │ │Report │    │    │
│  │ │  8 ✅ │ │  3 ✅  │    │    │
│  │ └───────┘ └───────┘    │    │
│  │                         │    │
│  │ [📥 Download Excel]     │    │
│  │ [🔄 Refresh Reports]    │    │
│  └─────────────────────────┘    │
└─────────────────────────────────┘
```

### 5.2 Task Execution Flow (Phase 2)

```
User taps "Start Demand Entry" on mobile
    │
    │ POST /api/tasks/create
    │ {automation_key: "demand", params: {district, block, panchayat}}
    ▼
┌─────────────────────────────────┐
│  Flask: task_api.py              │
│  - Validate license              │
│  - Create task_records row       │
│  - Enqueue to task queue         │
│  - Return task_id                │
└──────────────┬──────────────────┘
               │
               │ Background worker picks up
               ▼
┌─────────────────────────────────┐
│  Task Worker (Python thread)     │
│  - Connect to Obscura CDP        │
│  - Execute automation logic      │
│  - Store results in cloud_reports│
│  - Update task_records status    │
│  - Send WhatsApp notification    │
└─────────────────────────────────┘
               │
               │ SSE push to mobile
               ▼
┌─────────────────────────────────┐
│  Mobile Dashboard auto-updates   │
│  - Progress bar fills            │
│  - "✅ Complete" badge appears   │
│  - Download button activates     │
└─────────────────────────────────┘
```

---

## 6. Phase 1: Cloud Reports Dashboard

### 🎯 Goal
Users apne mobile browser se login karke **sirf reports dekh aur download** kar sakein — bina koi automation run kiye. Reports desktop app ke cloud sync se aati hain (existing flow).

### 📋 Status: 🟢 In Progress

### 6.1 What Changed

| File | Action | Description |
|---|---|---|
| `nrega-server/app/routes/cloud/__init__.py` | ✅ **DONE** | Cloud blueprint (prefix `/cloud`) |
| `nrega-server/app/routes/cloud/dashboard.py` | ✅ **DONE** | Dashboard route — recent reports |
| `nrega-server/app/routes/cloud/mr_tracking.py` | ✅ **DONE** | MR Tracking automation via Playwright + Obscura |
| `nrega-server/app/templates/cloud/base.html` | ✅ **DONE** | Mobile-responsive base template (Tailwind CSS) |
| `nrega-server/app/templates/cloud/dashboard.html` | ✅ **DONE** | Dashboard with automation cards + form + results |
| `nrega-server/migrations/029_cloud_reports.sql` | ✅ **DONE** | cloud_reports table |
| `nrega-server/app/routes/__init__.py` | ✅ **DONE** | Register cloud_bp |
| `nrega-server/app/__init__.py` | ✅ **DONE** | Register cloud_bp |
| `nrega-server/web/index.html` | ✅ **DONE** | Added "Cloud" link to navbar (desktop + mobile) |

### 6.2 New Pages (Mobile-Responsive)

| Page | URL | Description |
|---|---|---|
| Login | `/cloud/login` | License key se login (existing auth) |
| Dashboard | `/cloud/dashboard` | Today/yesterday/all reports overview |
| Report Detail | `/cloud/report/<id>` | Single report ka detail + download |
| Download | `/cloud/download/<id>` | Excel/PDF file download |

### 6.3 UI Design (Mobile-First)

```
┌─────────────────────────┐
│ 🏠 NregaBot Cloud       │ ← Sticky header
│ ─────────────────────── │
│                         │
│ 📅 Today — 20 Aug 2026  │ ← Date filter
│                         │
│ ┌─────────────────────┐ │
│ │ 📊 Demand Entry     │ │ ← Report card
│ │ JH > Block > GP     │ │
│ │ ✅ 12 rows • 2 min  │ │
│ │ [📥 Excel] [👁 View]│ │ ← Action buttons
│ └─────────────────────┘ │
│                         │
│ ┌─────────────────────┐ │
│ │ 📍 MR Tracking      │ │
│ │ 5 MRs tracked       │ │
│ │ ✅ 5 rows • 45 sec  │ │
│ │ [📥 Excel] [👁 View]│ │
│ └─────────────────────┘ │
│                         │
│ ┌─────────────────────┐ │
│ │ 💸 Pending Bills    │ │
│ │ 8 unpaid bills       │ │
│ │ ✅ 8 rows • 1 min   │ │
│ │ [📥 Excel] [👁 View]│ │
│ └─────────────────────┘ │
│                         │
│ ─────────────────────── │
│ ⚙️ Settings  📞 Support │ ← Footer nav
└─────────────────────────┘
```

### 6.4 Implementation Steps

- [x] **6.4.1** Create `nrega-server/app/routes/cloud/__init__.py`
- [x] **6.4.2** Create `nrega-server/app/routes/cloud/dashboard.py` — Flask Blueprint for `/cloud/*`
- [x] **6.4.3** Create mobile-responsive base template (`base.html`) with Tailwind CSS
- [x] **6.4.4** Create dashboard page (`cloud/dashboard.html`) — automation cards + MR tracking form
- [x] **6.4.5** Create `nrega-server/app/routes/cloud/mr_tracking.py` — MR Tracking automation via Obscura/Playwright
- [x] **6.4.6** Create `nrega-server/migrations/029_cloud_reports.sql` — cloud_reports table
- [x] **6.4.7** Register cloud_bp in `routes/__init__.py` + `app/__init__.py`
- [x] **6.4.8** Add "NregaBot Cloud" link to public website navbar (desktop + mobile menu)
- [ ] **6.4.9** Add Obscura Docker container to `docker-compose.yml`
- [ ] **6.4.10** Add `playwright` to requirements.txt
- [ ] **6.4.11** Test on mobile browsers (Chrome, Safari, Samsung Internet)
- [ ] **6.4.12** Create report detail page (`/cloud/report/<id>`) for past reports

### 6.5 Estimated Effort
- **Backend (Flask routes + DB):** 3-4 days
- **Frontend (Mobile templates):** 2-3 days
- **Testing + Polish:** 1-2 days
- **Total: ~1 week**

---

## 7. Phase 2: Simple Automations via Cloud

### 🎯 Goal
Users mobile se **read-only automations** trigger kar sakein — cloud browser (Obscura) unke behalf par MGNREGA portal scrape kare, results store kare, user ko notify kare.

### 📋 Status: 🔴 Not Started

### 7.1 Which Automations Are Cloud-Ready?

| Tab | automation_key | Login Required? | Complexity | Cloud-Ready? |
|---|---|---|---|---|
| Dashboard Report | `dashboard_report` | ❌ No (public) | Low | ✅ **Easy** |
| MIS Reports | `mis_reports` | ❌ No (public) | Low | ✅ **Easy** |
| MR Tracking | `mr_tracking` | ❌ No (public) | Low | ✅ **Easy** |
| Pending Bills | `pending_bills` | ❌ No (public) | Medium | ✅ **Easy** |
| eKYC Report | `ekyc_report` | ✅ Yes (PO login) | Low | ⚠️ **Medium** |
| Issued MR Details | `issued_mr_report` | ✅ Yes | Low | ⚠️ **Medium** |
| NMMS Attendance | `nmms_attendance` | ✅ Yes | Medium | ⚠️ **Medium** |
| Social Audit Report | `social_audit_respond` | ✅ Yes | Medium | ⚠️ **Medium** |
| Demand Entry | `demand` | ✅ Yes (PO login) | High | ❌ **Hard** |
| MR Fill | `mr_fill` | ✅ Yes | High | ❌ **Hard** |
| Work Allocation | `work_allocation` | ✅ Yes | High | ❌ **Hard** |
| Muster Roll Gen | `muster` | ✅ Yes | Medium | ❌ **Hard** |

**Strategy:** Start with public report tabs (no login needed), then add login-required ones with encrypted credential storage.

### 7.2 What Changes

| File | Action | Description |
|---|---|---|
| `nrega-server/app/routes/cloud/task_api.py` | **NEW** | Task creation + status API |
| `nrega-server/app/routes/cloud/worker.py` | **NEW** | Background task worker |
| `nrega-server/app/services/obscura_client.py` | **NEW** | Obscura CDP client wrapper |
| `nrega-server/app/repositories/task_records_repo.py` | **NEW** | Task queue DB operations |
| `nrega-server/migrations/030_task_queue.sql` | **NEW** | Task queue tables |
| `docker-compose.yml` | **NEW/MODIFY** | Add Obscura container |
| `nrega-server/app/templates/cloud/task_trigger.html` | **NEW** | Task creation UI |
| `nrega-server/app/templates/cloud/task_progress.html` | **NEW** | Live progress view |

### 7.3 Obscura Docker Setup

```yaml
# docker-compose.yml addition
services:
  obscura:
    image: h4ckf0r0day/obscura
    ports:
      - "127.0.0.1:9222:9222"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
    environment:
      - OBSCURA_NETWORK_BODY_BUFFER_BYTES=4194304  # 4MB for large pages

  # Optional: second worker for parallel tasks
  obscura-worker:
    image: h4ckf0r0day/obscura
    ports:
      - "127.0.0.1:9223:9222"
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
```

### 7.4 Task Execution Architecture

```python
# nrega-server/app/services/obscura_client.py

from playwright.sync_api import sync_playwright

class ObscuraClient:
    """Wrapper for Obscura CDP browser — replaces local Selenium."""
    
    CDP_ENDPOINT = "ws://localhost:9222"
    
    def __init__(self):
        self._pw = None
        self._browser = None
    
    def connect(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.connect_over_cdp(self.CDP_ENDPOINT)
    
    def new_page(self):
        return self._browser.new_page()
    
    def close(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()


# Example: Cloud report scraping
def scrape_dashboard_report(params: dict) -> dict:
    """Scrape MGNREGA dashboard report via Obscura."""
    client = ObscuraClient()
    try:
        client.connect()
        page = client.new_page()
        
        # Navigate to public report (no login needed)
        url = "https://vbgramgrep.dord.gov.in/VBGRAMG/..."
        page.goto(url, wait_until="networkidle")
        
        # Select district/block from dropdowns
        page.select_option("#ddl_District", params["district"])
        page.select_option("#ddl_Block", params["block"])
        
        # Wait for table to load
        page.wait_for_selector("table.report-table")
        
        # Extract data
        results = page.evaluate("""() => {
            const rows = document.querySelectorAll('table.report-table tr');
            return Array.from(rows).map(row => 
                Array.from(row.cells).map(cell => cell.textContent.trim())
            );
        }""")
        
        return {"columns": results[0], "rows": results[1:], "status": "success"}
    finally:
        client.close()
```

### 7.5 Task Queue Design (Phase 2.1 — SQLite-based)

```sql
-- migrations/030_task_queue.sql

CREATE TABLE IF NOT EXISTS task_records (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(255) NOT NULL,
    automation_key VARCHAR(100) NOT NULL,
    params JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending',  -- pending/running/completed/failed
    result_summary TEXT,
    result_rows JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds FLOAT
);

CREATE INDEX idx_task_records_license ON task_records(license_key);
CREATE INDEX idx_task_records_status ON task_records(status);
CREATE INDEX idx_task_records_created ON task_records(created_at DESC);
```

### 7.6 Implementation Steps

- [ ] **7.6.1** Add Obscura Docker container to `docker-compose.yml`
- [ ] **7.6.2** Create `nrega-server/app/services/obscura_client.py` — CDP client wrapper
- [ ] **7.6.3** Create `nrega-server/migrations/030_task_queue.sql` — task_records table
- [ ] **7.6.4** Create `nrega-server/app/repositories/task_records_repo.py` — CRUD operations
- [ ] **7.6.5** Create `nrega-server/app/routes/cloud/task_api.py` — REST API for tasks
- [ ] **7.6.6** Create `nrega-server/app/routes/cloud/worker.py` — background task processor
- [ ] **7.6.7** Implement `dashboard_report` cloud automation (simplest, no login)
- [ ] **7.6.8** Implement `mr_tracking` cloud automation (no login)
- [ ] **7.6.9** Implement `pending_bills` cloud automation (no login)
- [ ] **7.6.10** Implement `mis_reports` cloud automation (no login)
- [ ] **7.6.11** Create task trigger UI (`cloud/tasks.html`)
- [ ] **7.6.12** Create live progress view with SSE (`/cloud/progress/<task_id>`)
- [ ] **7.6.13** Add WhatsApp notification on task completion
- [ ] **7.6.14** Test all 4 public report automations via mobile
- [ ] **7.6.15** Add rate limiting per license key (max concurrent tasks)

### 7.7 Estimated Effort
- **Obscura setup + client:** 1-2 days
- **Task queue + API:** 2-3 days
- **4 public report automations:** 3-4 days
- **UI (trigger + progress):** 2-3 days
- **Testing + WhatsApp notify:** 1-2 days
- **Total: ~2 weeks**

---

## 8. Phase 3: Full Mobile Experience

### 🎯 Goal
Login-required automations (form filling, data entry) bhi mobile se trigger ho sakein. Full push notifications, offline support, voice commands.

### 📋 Status: 🔴 Not Started

### 8.1 Features

| Feature | Description | Complexity |
|---|---|---|
| Encrypted Credential Store | User ke portal credentials server par encrypted (AES-256) store ho | Medium |
| Login-Required Automations | Demand, MR Fill, Work Allocation via cloud browser | High |
| Push Notifications | FCM/APNs for automation complete/fail alerts | Medium |
| Offline Results Cache | PWA service worker — previously fetched reports offline dikhein | Low |
| Voice Commands (Hindi) | "Report dikhao" / "MR fill karo" — Web Speech API | Medium |
| Photo Upload | Jobcard verification ke liye mobile se photo upload | Low |
| Scheduled Automations | User schedule kare — " roz raat 10 baje dashboard report bhejo" | Medium |
| Multi-User Dashboard | BDO office — ek license se multiple workers dekh sakein | High |

### 8.2 Encrypted Credential Storage

```sql
-- migrations/031_portal_credentials.sql

CREATE TABLE IF NOT EXISTS portal_credentials (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(255) NOT NULL,
    portal_type VARCHAR(50) NOT NULL,  -- 'po_login', 'gp_login'
    username_encrypted BYTEA NOT NULL,  -- AES-256 encrypted
    password_encrypted BYTEA NOT NULL,  -- AES-256 encrypted
    state VARCHAR(100),
    district VARCHAR(200),
    block VARCHAR(200),
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(license_key, portal_type, state, district, block)
);
```

### 8.3 Implementation Steps

- [ ] **8.3.1** Design encrypted credential storage (AES-256, key from license)
- [ ] **8.3.2** Create portal_credentials migration + repository
- [ ] **8.3.3** Create credential management API (add/edit/delete via mobile)
- [ ] **8.3.4** Implement `demand` cloud automation (with login flow)
- [ ] **8.3.5** Implement `mr_fill` cloud automation
- [ ] **8.3.6** Implement `work_allocation` cloud automation
- [ ] **8.3.7** Implement `muster_roll_gen` cloud automation
- [ ] **8.3.8** Add PWA manifest + service worker for offline support
- [ ] **8.3.9** Add push notification via FCM (or WhatsApp as fallback)
- [ ] **8.3.10** Implement scheduled automations (cron-like)
- [ ] **8.3.11** Add voice command support (Web Speech API)
- [ ] **8.3.12** Multi-user dashboard for BDO offices

### 8.4 Estimated Effort
- **Credential storage + security:** 3-4 days
- **4 login-required automations:** 5-7 days
- **Push notifications + PWA:** 2-3 days
- **Voice commands + scheduling:** 3-4 days
- **Total: ~3-4 weeks**

---

## 9. Database Schema Changes

### Migration 029: Cloud Reports (Phase 1)

```sql
-- Already partially exists (cloud_reports from desktop sync)
-- Enhancement: add more metadata columns

ALTER TABLE cloud_reports
    ADD COLUMN IF NOT EXISTS report_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS file_path TEXT,
    ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,
    ADD COLUMN IF NOT EXISTS viewed_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS downloaded_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_cloud_reports_type 
    ON cloud_reports(license_key, report_type, created_at DESC);
```

### Migration 030: Task Queue (Phase 2)

```sql
-- See section 7.5 above
```

### Migration 031: Portal Credentials (Phase 3)

```sql
-- See section 8.2 above
```

---

## 10. API Endpoints

### Phase 1: Reports API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/cloud/reports` | License key | List reports (filterable) |
| `GET` | `/api/cloud/reports/<id>` | License key | Single report detail |
| `GET` | `/api/cloud/reports/<id>/download` | License key | Download Excel/PDF |
| `GET` | `/api/cloud/reports/stats` | License key | Report counts by type/date |

### Phase 2: Task API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/cloud/tasks` | License key | Create new task |
| `GET` | `/api/cloud/tasks` | License key | List user's tasks |
| `GET` | `/api/cloud/tasks/<id>` | License key | Task detail + progress |
| `DELETE` | `/api/cloud/tasks/<id>` | License key | Cancel running task |
| `GET` | `/api/cloud/tasks/<id>/stream` | License key | SSE progress stream |

### Phase 3: Credentials API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/cloud/credentials` | License key | Add portal credentials |
| `GET` | `/api/cloud/credentials` | License key | List saved credentials |
| `PUT` | `/api/cloud/credentials/<id>` | License key | Update credentials |
| `DELETE` | `/api/cloud/credentials/<id>` | License key | Delete credentials |

---

## 11. Security Considerations

### 11.1 DPDP Compliance (Data Protection)

| Risk | Mitigation |
|---|---|
| Portal credentials in transit | TLS 1.3 enforced on all `/api/cloud/*` |
| Portal credentials at rest | AES-256 encryption, key derived from license_key |
| Report data (Aadhaar, bank) | Already masked via `mask_columns_rows()` before server sync |
| Server-side browser session | Sessions destroyed after task completion, no persistent cookies |
| Rate limiting | Per-license: max 3 concurrent tasks, max 50 tasks/day |

### 11.2 Authentication Flow

```
Mobile Browser → GET /cloud/login
    │
    │ User enters license key
    ▼
POST /cloud/login {license_key: "NREGABOT-XXXX"}
    │
    │ Validate against licenses table
    │ Check expiry, device count, feature flags
    ▼
Set session cookie (httponly, secure, same_site=strict)
    │
    │ Redirect to /cloud/dashboard
    ▼
All subsequent requests: session cookie + license key header
```

### 11.3 Obscura Security

- Obscura container runs on `127.0.0.1:9222` only — not exposed to internet
- Each task gets a fresh browser context (no cookie leakage between users)
- Stealth mode enabled — prevents portal from detecting automation
- Container memory limit: 256 MB — prevents resource exhaustion

---

## 12. Deployment Strategy

### 12.1 NAS Deployment (Existing)

```bash
# nrega-server already deploys on NAS via docker-compose
# Add Obscura to the existing stack

# On NAS:
cd /volume1/docker/nrega-server/
git pull origin master
docker-compose up -d --build
```

### 12.2 Resource Requirements

| Component | RAM | Disk | CPU |
|---|---|---|---|
| Flask server (existing) | 256 MB | 1 GB | 0.5 core |
| PostgreSQL (existing) | 512 MB | 5 GB | 0.5 core |
| Obscura (Phase 1: 1 worker) | 256 MB | 70 MB | 0.25 core |
| Obscura (Phase 2: 3 workers) | 768 MB | 210 MB | 0.75 core |
| **Total (Phase 2)** | **~1.8 GB** | **~7 GB** | **~2 cores** |

**NAS impact:** Most NAS devices (Synology, QNAP) have 4-8 GB RAM. This adds ~1.8 GB — manageable.

### 12.3 Rollout Plan

| Step | Action | Risk |
|---|---|---|
| 1 | Deploy Phase 1 (reports dashboard) to NAS | Low — read-only, no automation |
| 2 | Test with 5 beta users on mobile | Low — feedback collection |
| 3 | Deploy Phase 2 (cloud automations) to NAS | Medium — new browser engine |
| 4 | Gradual rollout (10% → 50% → 100% users) | Medium — monitor error rates |
| 5 | Phase 3 features as they're ready | Medium — encrypted credentials |

---

## 13. Milestones & Timeline

| Milestone | Target Date | Status | Description |
|---|---|---|---|
| **M1: Plan Review** | Aug 2026 | 🟡 In Review | This document reviewed and approved |
| **M2: Phase 1 Prototype** | Sep Week 1 | 🔴 Not Started | Mobile reports dashboard (view only) |
| **M3: Phase 1 Complete** | Sep Week 2 | 🔴 Not Started | All existing reports viewable on mobile |
| **M4: Obscura Integration** | Sep Week 3 | 🔴 Not Started | Docker setup + CDP client |
| **M5: Phase 2 First Automation** | Sep Week 4 | 🔴 Not Started | Dashboard Report via cloud |
| **M6: Phase 2 Complete** | Oct Week 2 | 🔴 Not Started | All 4 public automations via cloud |
| **M7: Beta Launch** | Oct Week 3 | 🔴 Not Started | 5 users testing on mobile |
| **M8: Production Launch** | Nov Week 1 | 🔴 Not Started | All users get mobile access |

---

## 14. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| MGNREGA portal blocks Obscura | Low | High | Stealth mode + fingerprint randomization |
| NAS resource exhaustion | Low | Medium | Memory limits + task queue throttling |
| Portal session timeout during automation | Medium | Medium | Auto-retry + session refresh logic |
| Mobile browser compatibility issues | Low | Low | Tailwind CSS (cross-browser tested) |
| Credential security breach | Low | Critical | AES-256 encryption + no plaintext storage |
| Obscura project abandoned | Low | Low | Can fall back to headless Chrome |
| Network latency from NAS | Medium | Low | Results cached, background processing |

---

## 15. Progress Tracker

> **Instructions:** Jab kaam shuru ho, yahan checkboxes tick karte jaana.
> Format: `- [x]` for done, `- [ ]` for pending, `- [~]` for in-progress

### Phase 1: Cloud Reports Dashboard

- [x] Create Flask Blueprint for `/cloud/*` routes
- [x] Create mobile-responsive base template (Tailwind CSS)
- [x] Create dashboard page (automation cards + MR tracking form)
- [x] Create MR Tracking cloud automation (Playwright + Obscura CDP)
- [x] Create cloud_reports table migration (029)
- [x] Register cloud_bp in app
- [x] Add "NregaBot Cloud" link to public website navbar
- [ ] Add Obscura Docker container to docker-compose.yml
- [ ] Add playwright to requirements.txt
- [ ] Test on mobile browsers
- [ ] Create report detail page (/cloud/report/<id>)
- [ ] **Phase 1 Complete** ✅

### Phase 2: Simple Automations via Cloud

- [ ] Add Obscura Docker container to `docker-compose.yml`
- [ ] Create `obscura_client.py` (CDP wrapper)
- [ ] Create `task_records` migration
- [ ] Create task repository
- [ ] Create task API (`/api/cloud/tasks`)
- [ ] Create background task worker
- [ ] Implement `dashboard_report` cloud automation
- [ ] Implement `mr_tracking` cloud automation
- [ ] Implement `pending_bills` cloud automation
- [ ] Implement `mis_reports` cloud automation
- [ ] Create task trigger UI
- [ ] Create live progress view (SSE)
- [ ] Add WhatsApp notification on completion
- [ ] Rate limiting per license key
- [ ] **Phase 2 Complete** ✅

### Phase 3: Full Mobile Experience

- [ ] Design encrypted credential storage (AES-256)
- [ ] Create `portal_credentials` migration
- [ ] Create credential management API
- [ ] Implement `demand` cloud automation (with login)
- [ ] Implement `mr_fill` cloud automation
- [ ] Implement `work_allocation` cloud automation
- [ ] Implement `muster_roll_gen` cloud automation
- [ ] Add PWA manifest + service worker
- [ ] Add push notifications (FCM or WhatsApp)
- [ ] Implement scheduled automations
- [ ] Add voice commands (Hindi)
- [ ] Multi-user dashboard for BDO offices
- [ ] **Phase 3 Complete** ✅

### Overall Status

| Phase | Status | Progress |
|---|---|---|
| Phase 1: Cloud Reports Dashboard | 🟢 In Progress | 60% |
| Phase 2: Simple Automations | 🟢 MR Tracking Done | 15% |
| Phase 3: Full Mobile Experience | 🔴 Not Started | 0% |
| **Overall Project** | 🟢 Active Development | 25% |

---

## 📎 Appendix

### A. Obscura Quick Reference

```bash
# Install on NAS (Linux x86_64)
curl -LO https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-x86_64-linux.tar.gz
tar xzf obscura-x86_64-linux.tar.gz

# Run CDP server
./obscura serve --port 9222

# Run with stealth mode (anti-detect)
./obscura serve --port 9222 --stealth

# Docker
docker run -d --name obscura -p 127.0.0.1:9222:9222 h4ckf0r0day/obscura

# Quick test (fetch page)
./obscura fetch https://example.com --eval "document.title"
```

### B. Useful Links

| Resource | URL |
|---|---|
| Obscura GitHub | https://github.com/h4ckf0r0day/obscura |
| Obscura Releases | https://github.com/h4ckf0r0day/obscura/releases |
| Playwright Python Docs | https://playwright.dev/python/ |
| Tailwind CSS | https://tailwindcss.com/ |
| MGNREGA Portal | https://nregastrep.nic.in/ |
| VB-G-RAM-G Portal | https://vbgramgde2.dord.gov.in/ |

### C. File Structure (New Files)

```
nrega-server/
├── app/
│   ├── routes/
│   │   └── cloud/                    # ✅ Created
│   │       ├── __init__.py           # ✅ Cloud blueprint
│   │       ├── dashboard.py          # ✅ Dashboard route
│   │       ├── mr_tracking.py        # ✅ MR Tracking automation
│   │       ├── task_api.py           # Phase 2
│   │       └── worker.py             # Phase 2
│   ├── repositories/
│   │   └── cloud_reports_repo.py     # Phase 1 (future)
│   │   └── task_records_repo.py      # Phase 2
│   ├── services/
│   │   └── obscura_client.py         # Phase 2
│   └── templates/
│       └── cloud/                    # ✅ Created
│           ├── base.html             # ✅ Mobile-responsive base
│           ├── dashboard.html        # ✅ Dashboard + MR tracking form
│           ├── report_detail.html    # Phase 1 (future)
│           ├── tasks.html            # Phase 2
│           └── task_progress.html    # Phase 2
├── migrations/
│   ├── 029_cloud_reports.sql         # ✅ cloud_reports table
│   ├── 030_task_queue.sql           # Phase 2
│   └── 031_portal_credentials.sql   # Phase 3
└── docker-compose.yml                # Modify (add Obscura)
```

---

> **Ye document living hai — jaise kaam progress kare, waise update karte jaana.
> Har phase complete hone par status aur dates update karo.**
