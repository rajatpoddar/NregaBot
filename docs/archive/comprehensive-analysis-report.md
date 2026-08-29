# NREGA Bot — Comprehensive Application Analysis Report

> **Date:** July 27, 2026
> **Author:** Buffy (AI Assistant)
> **Scope:** Full-stack analysis — Desktop App (`src/`), Server (`nrega-server/`), Web Frontend (`web/`)

---

## 📋 Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Desktop Application Analysis (src/)](#2-desktop-application-analysis-src)
3. [Server Application Analysis (nrega-server/)](#3-server-application-analysis-nrega-server)
4. [Web Frontend Analysis (web/)](#4-web-frontend-analysis-web)
5. [Database Schema & Migrations](#5-database-schema--migrations)
6. [Feature Gap Analysis](#6-feature-gap-analysis)
7. [UX & UI Improvements](#7-ux--ui-improvements)
8. [Centralization Opportunities](#8-centralization-opportunities)
9. [Analytics & Telemetry Gaps](#9-analytics--telemetry-gaps)
10. [Security Audit](#10-security-audit)
11. [Performance Optimization](#11-performance-optimization)
12. [Priority Implementation Roadmap](#12-priority-implementation-roadmap)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DESKTOP APPLICATION (src/)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Tabs (44)│  │  Managers│  │  App     │  │ Config/State   │  │
│  │ - MR/Wage│  │ - Browser│  │ - UI     │  │ - config.py    │  │
│  │ - Schemes│  │ - Sound  │  │ - Nav    │  │ - state.py     │  │
│  │ - Reports│  │ - Workflo│  │ - License│  │ - tab_config   │  │
│  │ - Tools  │  │ - Icon   │  │ - Auto   │  │                │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP (REST API)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SERVER (nrega-server/)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Flask    │  │ Routes   │  │ Services │  │ DB (Postgres)  │  │
│  │ - CORS   │  │ - API    │  │ - License│  │ - Licenses     │  │
│  │ - Limiter│  │ - Admin  │  │ - Payment│  │ - Payments     │  │
│  │ - Celery │  │ - Front  │  │ - Device │  │ - Feedback     │  │
│  │ - Redis  │  │ - File   │  │ - Trial  │  │ - Chat         │  │
│  └──────────┘  └──────────┘  └──────────┘  │ - User Files   │  │
│                                              └────────────────┘  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌──────────────────┐    ┌──────────────────────────┐
│ Static Web       │    │ Admin Panel (Server)      │
│ (web/ - Nregabot │    │ - Dashboard, Users,       │
│  marketing site) │    │ - Payments, Feedback,     │
│ - index.html     │    │ - Chat, Coupons, Reseller │
│ - contact.html   │    │ - Mailing, Audit Logs    │
│ - how-to-use     │    └──────────────────────────┘
│   etc.           │
└──────────────────┘
```

### Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| **Desktop UI** | Python + CustomTkinter + Tkinter |
| **Desktop Browser Automation** | Selenium WebDriver (Chrome/Edge/Firefox) |
| **Server Framework** | Flask (Python) |
| **Database** | PostgreSQL (with connection pooling) |
| **Cache/Queue** | Redis |
| **Async Tasks** | Celery |
| **Payments** | Razorpay (one-time + subscriptions) |
| **Analytics/Monitoring** | Prometheus metrics |
| **Admin Dashboard** | Server-rendered HTML + Tailwind CSS + Chart.js |
| **Web Frontend** | Static HTML (separate from server) |

---

## 2. Desktop Application Analysis (src/)

### 2.1 What's Present ✅

- **44+ Automation Tabs** organized in 7 categories:
  - **MR & Wage Management** (11 tabs): Demand, Work Allocation, Muster Roll Gen, Mate/Mistri MR, MR Fill, MR Payment, Gen Wagelist, Send Wagelist, FTO Generation, Duplicate MR Print, Material Entry
  - **JE & AE Approval** (2 tabs): eMB Entry, eMB Verify
  - **Schemes Related** (6 tabs): Work Code Gen, IF Editor, Update Estimate, Physical Complete, Scheme Closing, Add Activity
  - **Verification & Utility** (9 tabs): Job Card Verify, Verify ABPS, Del Work Alloc, Delete Demand, Delete Applicant, Zero MR, Resend Rejected WG, Sarkar Aapke Dwar, SAD Update Status
  - **Reports & Tracking** (7 tabs): MR Tracking, Dashboard Report, MIS Reports, Issued MR Details, eKYC Report, Social Audit Report, NMMS Attendance
  - **Smart Tools** (5 tabs): Macro Manager, Login Automation, PDF Merger, Workcode Extractor, File Manager
  - **About & Help** (3 tabs): About, Settings, Feedback
- **Lazy Loading** — tabs are imported only when first accessed (performance optimization)
- **State Management** — Centralized `AppState` dataclass
- **Sound Effects** — Click, success, error, macro sounds
- **Theme System** — Light/Dark/System with smooth fade transitions
- **Resize Smoothing** — Overlay to hide flickering during window resize
- **Activity Log** — History window with stats, search, treeview
- **Cloud File Manager** — Upload/download files to server
- **Server Status Indicator** — Footer shows connection health
- **Emergency Stop** — Stops all running automations

### 2.2 What's Missing / Can Improve ❌

| # | Issue | Severity |
|---|-------|----------|
| 1 | **No offline mode** — App requires constant internet connection | Medium |
| 2 | **No usage telemetry** — Don't know which features users use most | High |
| 3 | **No onboarding tour** — New users don't get guided walkthrough | Medium |
| 4 | **Feedback tab uses old API** — Uses `/api/feedback/send_message` instead of the new `/api/send-chat-message` | Medium |
| 5 | **No keyboard shortcuts** — Power users would benefit from shortcuts | Low |
| 6 | **No batch queue system** — Can't queue multiple tasks to run sequentially | Medium |
| 7 | **No auto-update in app** — Updates are manual download | High |
| 8 | **No crash reporting** — App crashes silently, no telemetry | High |
| 9 | **Dark mode in some tabs** — Some legacy tabs may not render properly in dark mode | Low |
| 10 | **No tab search** — With 44+ tabs, searching by name would help | Low |

### 2.3 Desktop-Specific Feature Suggestions 💡

1. **Task Queue System** — Let users queue multiple automations (e.g., "Run Demand → MR Gen → Wagelist Gen" in sequence)
2. **Dashboard Widgets** — Customizable home page with pinned shortcuts, recent activity, server status
3. **Bulk Operations** — Select multiple blocks/districts and run operations on all at once
4. **Export Center** — Single place to export all generated files (reports, PDFs, CSVs)
5. **Local Cache** — Cache frequently accessed data (MR lists, work codes) locally to reduce server calls
6. **Progressive Web App mode** — Lite version could run as a PWA
7. **Smart suggestions** — Based on past usage, suggest next actions

---

## 3. Server Application Analysis (nrega-server/)

### 3.1 What's Present ✅

- **License Management** — Full CRUD, validation, device binding, expiry
- **Payment Processing** — Razorpay integration (one-time + subscriptions)
- **Trial Registration** — 30-day free trial with OTP verification
- **Live Chat** — PostgreSQL-based chat system (migrated from Firebase)
- **Feedback System** — Submit feedback with admin reply threads
- **Cloud File Storage** — Per-user file upload (500MB default), shared collections
- **Coupon System** — Discount codes with usage limits
- **Reseller Panel** — Resellers can manage users in their district
- **Admin Dashboard** — Stats, charts, user management, transaction history
- **Mailing System** — SMTP email, WhatsApp messages, templates
- **Celery Async Tasks** — Email sending, bulk messaging
- **Redis Caching** — Admin dashboard data, rate limiting
- **Prometheus Metrics** — HTTP requests, DB pool, uptime
- **Structured Logging** — JSON log format with request context
- **Rate Limiting** — Flask-Limiter with Redis backend
- **Security Headers** — CSP, X-Frame-Options, X-Content-Type-Options
- **DB Migration System** — Versioned SQL migrations
- **Audit Logging** — Admin actions logged for compliance

### 3.2 What's Missing / Can Improve ❌

| # | Issue | Severity |
|---|-------|----------|
| 1 | **No user analytics/telemetry API** — No endpoint to track user behavior | Critical |
| 2 | **No push notifications** — Users don't get notified about license expiry, replies | High |
| 3 | **Chat not connected to desktop** — Desktop app still uses old feedback API | High |
| 4 | **No API documentation** — External devs can't integrate | Medium |
| 5 | **No automated backups** — No backup strategy for PostgreSQL | High |
| 6 | **No user activity log** — Can't see what users do in desktop app | High |
| 7 | **No webhook system** — Can't trigger external actions on events | Medium |
| 8 | **No rate limiting on web frontend** — Public pages not protected | Medium |
| 9 | **No email verification** — Users can register with any email without verifying | Medium |
| 10 | **No GDPR/Privacy compliance** — No data export/deletion flow | Medium |

### 3.3 Server-Specific Feature Suggestions 💡

1. **Usage Analytics API** — `/api/analytics/event` to record feature usage, `/api/analytics/dashboard` for aggregated stats
2. **Push Notification System** — Email + WhatsApp notifications for key events (expiry, replies, new features)
3. **Automated Backup Scheduler** — Regular PostgreSQL dumps to cloud storage
4. **User Activity Dashboard** — Admin panel showing per-user activity (last seen, features used, files uploaded)
5. **Webhook System** — Configure webhooks for license events (created, expired, blocked)
6. **API Key System** — Allow 3rd-party integrations with API keys
7. **File Versioning** — Track file versions in cloud storage
8. **Multi-language Support** — Hindi + English for admin panel

---

## 4. Web Frontend Analysis (web/)

### 4.1 What's Present ✅

- Static HTML pages: `index.html`, `about.html`, `contact.html`, `terms.html`, `refund.html`, `versions.html`, `privacy.html`, `how-to-use.html`
- `sitemap.xml`, `robots.txt` for SEO
- `update_nregabot.py` — Update check script

### 4.2 What's Missing ❌

| # | Issue | Severity |
|---|-------|----------|
| 1 | **Web frontend is completely static** — Not connected to Flask server | Critical |
| 2 | **No user login/dashboard on web** — Users can't see their account or usage | High |
| 3 | **No analytics dashboard for end users** — Can't see usage stats | High |
| 4 | **Contact form not connected** — Contact page has no backend integration | Medium |
| 5 | **No live chat widget** — Static contact page instead of live chat | High |
| 6 | **No download tracking** — Can't track which versions users download | Medium |
| 7 | **No blog/news section** — No way to announce updates and features | Low |
| 8 | **No user testimonials** — No social proof on landing page | Low |

### 4.3 Web Frontend Suggestions 💡

1. **Integrate web frontend with Flask server** — Serve from Flask instead of static files
2. **User Dashboard** — `/dashboard` showing license info, usage stats, recent activity, cloud files
3. **Analytics Dashboard** — Charts showing feature usage, task completion rates, time saved
4. **Live Chat Widget** — Add floating chat widget to all marketing pages
5. **Dynamic Pricing Page** — Real-time pricing, coupon application
6. **Download Statistics** — Track and display download counts per version
7. **Interactive Feature Showcase** — Animated demo of key features
8. **Blog/Changelog** — Dynamic changelog from `changelog.json`

---

## 5. Database Schema & Migrations

### 5.1 Current Tables

| Table | Purpose | Has Migrations? |
|-------|---------|-----------------|
| `licenses` | License keys, user info, device binding | ✅ |
| `payments` | Payment transactions | ✅ |
| `otp_store` | One-time passwords for registration | ✅ |
| `feedback` | User feedback submissions | ✅ |
| `feedback_replies` | Admin replies to feedback | ✅ |
| `chat_messages` | Live chat messages (new) | ✅ (migration 003) |
| `user_files` | Cloud file storage metadata | ✅ |
| `shared_items` | Shared file tokens | ✅ |
| `shared_collections` | Shared file collections | ✅ |
| `coupons` | Discount coupon codes | ✅ |
| `email_templates` | Reusable email templates | ✅ |
| `reseller_requests` | Reseller block/unblock requests | ✅ |
| `app_settings` | Key-value app configuration | ✅ |
| `admin_audit_logs` | Admin action audit trail | ✅ |
| `deactivation_requests` | Device deactivation requests | ✅ |

### 5.2 Missing Tables

| Table Needed | Purpose |
|-------------|---------|
| `user_activity_log` | Track desktop app feature usage |
| `user_analytics_events` | Store telemetry events from desktop |
| `analytics_daily_stats` | Daily aggregated statistics |
| `user_sessions` | Track login sessions and duration |
| `notifications` | Store push notifications for users |
| `feature_flags` | Toggle features on/off per user |
| `api_keys` | 3rd party API key management |
| `backup_logs` | Automated backup records |

---

## 6. Feature Gap Analysis

### 6.1 Misaligned / Duplicate Features

| Feature | Desktop | Server API | Admin Panel | Web Frontend | Notes |
|---------|---------|------------|-------------|--------------|-------|
| **Feedback** | ✅ (old API) | ✅ (dual: feedback + chat) | ✅ | ❌ | Desktop uses old feedback API, not chat API |
| **Live Chat** | ❌ | ✅ (chat_messages) | ✅ | ✅ (chat.html) | Desktop doesn't have live chat, only feedback |
| **File Manager** | ✅ | ✅ | ✅ | ❌ | Cloud files only accessible via desktop |
| **User Dashboard** | ❌ | ❌ | ✅ (admin) | ❌ | Users have no web dashboard |
| **Analytics** | ❌ | ❌ | ⚠️ (basic) | ❌ | Only server-level Prometheus metrics |
| **Announcements** | ✅ (marquee) | ✅ (app_settings) | ✅ | ❌ | Works via polling, no push |

### 6.2 Key Issues

1. **Desktop Feedback vs Live Chat** — The desktop app has a `FeedbackTab` that uses `/api/feedback/send_message` API, but the server also has a newer `/api/send-chat-message` endpoint (migrated from Firebase). These are **two separate systems** — a user could be chatting on the web and the desktop support person wouldn't see it, and vice versa.

2. **Web vs Server Separation** — The web frontend (`web/`) is a completely separate static site, while the Flask server has its own templates (`nrega-server/app/templates/public/`). The marketing pages (index, about, contact) are in the static site, but the buy/trial/chat pages are in the Flask server. This is confusing and fragmented.

3. **No Cross-Platform Data Flow** — Data from the desktop app (usage patterns, feature popularity, error rates) never reaches the admin dashboard. The admin can see who has a license but not how they're using the software.

---

## 7. UX & UI Improvements

### 7.1 Desktop App UX

| Area | Current State | Proposed Improvement |
|------|--------------|---------------------|
| **Home Dashboard** | Basic shortcut grid | Personalized widgets, recent activity, server status |
| **Navigation** | Category collapsible sidebar | Add search/filter at top, pin favorites |
| **Tab Loading** | Skeleton loader | Add progress indicator for automation steps |
| **Form Inputs** | Basic CTkEntry | Add autocomplete, validation, smart defaults |
| **Error Messages** | messagebox.showerror | Inline toast notifications, error details panel |
| **Feedback Tab** | Basic chat UI | Modern chat interface with typing indicators |
| **Settings** | Basic toggle switches | Organized settings with search, categories |
| **Onboarding** | None | Step-by-step tour for first-time users |
| **Empty States** | None | Helpful messages when no data, with action buttons |

### 7.2 Server Web UX (Admin Panel)

| Area | Current State | Proposed Improvement |
|------|--------------|---------------------|
| **Dashboard** | Basic stats cards | Interactive charts, real-time updates |
| **User List** | Paginated table | Advanced filtering, bulk actions, inline edit |
| **Feedback Inbox** | List view | Kanban board, priority sorting, auto-categorization |
| **Chat** | Basic message view | Rich text, file sharing, typing indicators |
| **Mobile Responsive** | Partial | Full responsive design for all admin pages |

### 7.3 Marketing Site UX (web/)

| Area | Current State | Proposed Improvement |
|------|--------------|---------------------|
| **Landing Page** | Static HTML | Dynamic hero, feature carousel, live demo |
| **Download Flow** | Manual link | Smart download (auto-detect OS), version comparison |
| **Contact** | Static form | Live chat widget, FAQ section |
| **Pricing** | Not on marketing site | Integrated pricing with dynamic plans |

---

## 8. Centralization Opportunities

### 8.1 Communication Hub (Current: Fragmented)

```
CURRENT STATE:
Desktop Feedback Tab ──→ /api/feedback/send_message ──→ feedback + feedback_replies tables
Web Chat Page ─────────→ /api/send-chat-message ──────→ chat_messages table
Contact Form (web/) ───→ No backend ──────────────────→ Nothing

PROPOSED: Unified Communication Hub
All communication ─────→ /api/chat/messages ───────────→ chat_messages table
                          └── type: 'feedback' | 'chat' | 'contact'
```

### 8.2 Analytics Hub (Current: Missing)

```
Desktop App ──→ /api/analytics/event ──→ user_analytics_events table
Web Pages ────→ /api/analytics/pageview ──→ user_page_views table
Server ───────→ Prometheus + Structured Logs
Admin ────────→ Aggregated Analytics Dashboard
```

### 8.3 Notification Hub (Current: Missing)

```
License Expiry ──────────┐
Admin Reply to Feedback ─┼──→ /api/notifications/send ──→ Email / WhatsApp / In-App
New Feature Release ─────┘
```

---

## 9. Analytics & Telemetry Gaps

### 9.1 What Currently Exists

| Analytics Type | Where | Status |
|---------------|-------|--------|
| Server HTTP metrics | Prometheus (`/api/metrics`) | ✅ Basic |
| DB connection pool | Prometheus Gauge | ✅ Basic |
| Server uptime | Prometheus Gauge | ✅ Basic |
| Admin dashboard stats | SQL queries on payments/users | ✅ Basic |
| App version distribution | Admin dashboard chart | ✅ Basic |
| Structured request logs | JSON log files | ✅ Good |

### 9.2 What's Missing

| Analytics Type | Impact | Priority |
|---------------|--------|----------|
| **Desktop feature usage** (which tabs users open, how often) | Understand popular features | 🔴 Critical |
| **Automation success rate** (how many tasks complete vs fail) | Identify buggy features | 🔴 Critical |
| **User workflow patterns** (which sequence of tasks users follow) | Optimize workflows | 🟡 High |
| **Error tracking** (what errors users encounter, stack traces) | Fix critical bugs | 🔴 Critical |
| **Time saved** (manual vs automated time) | Marketing data | 🟡 High |
| **Conversion funnel** (trial → paid conversion rate) | Business metrics | 🟡 High |
| **User retention** (how many users come back daily/weekly) | Product health | 🟡 High |
| **Feature adoption** (which features users try after onboarding) | Feature prioritization | 🟢 Medium |
| **Page analytics** (which web pages users visit) | Marketing optimization | 🟢 Medium |

### 9.3 Proposed Analytics Implementation

```sql
-- New table: user_activity_log
CREATE TABLE user_activity_log (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(255) REFERENCES licenses(key),
    machine_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,   -- 'tab_open', 'automation_start', 'automation_complete', 'automation_error'
    event_name VARCHAR(255),            -- 'Demand', 'MR Gen', 'FTO Gen'
    event_data JSONB,                   -- { duration_ms: 12345, rows_processed: 100, error: null }
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- New table: analytics_daily_stats (materialized for dashboard)
CREATE TABLE analytics_daily_stats (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    total_active_users INTEGER DEFAULT 0,
    total_automations_run INTEGER DEFAULT 0,
    automation_success_count INTEGER DEFAULT 0,
    automation_error_count INTEGER DEFAULT 0,
    top_features JSONB,                 -- [{"name": "Demand", "count": 50}, ...]
    error_summary JSONB,                -- [{"error_type": "Timeout", "count": 5}, ...]
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stat_date)
);
```

---

## 10. Security Audit

### 10.1 What's Good ✅

- CSP headers on all HTML responses
- X-Frame-Options: DENY
- Rate limiting on API endpoints
- Session cookies with SameSite/Secure
- SQL injection protection via parameterized queries
- Admin routes require authentication
- Token-based API authentication
- Input validation schemas
- XSS sanitization filter

### 10.2 What Can Be Improved ❌

| # | Issue | Severity |
|---|-------|----------|
| 1 | **No 2FA for admin** — Admin panel only requires password | 🔴 High |
| 2 | **API tokens are license keys** — License keys exposed in every API call | 🔴 High |
| 3 | **No HTTPS enforcement** — App works on HTTP in some configurations | 🔴 High |
| 4 | **No CSRF protection** — Forms vulnerable to CSRF attacks | 🟡 Medium |
| 5 | **No API request logging** — Can't audit API usage | 🟡 Medium |
| 6 | **No file upload validation** — Uploaded files not scanned for malware | 🟡 Medium |
| 7 | **Session lifetime too long** — 30 day permanent session | 🟢 Low |
| 8 | **No password strength policy** — Users can set weak passwords | 🟢 Low |

---

## 11. Performance Optimization

### 11.1 Desktop App

| Optimization | Status | Impact |
|-------------|--------|--------|
| Lazy tab loading | ✅ Done | High |
| Icon lazy loading | ✅ Done | Medium |
| Resize smoothing overlay | ✅ Done | Medium |
| Config value caching | ✅ Done | Low |
| GC optimization | ✅ Done | Low |
| Lite mode config | ✅ Done | High |
| Startup timing telemetry | ✅ Done | Low |
| Remove module-level imports from tabs | ❌ Not done | Medium |
| Skeleton loading on tab switch | ❌ Not done | Medium |
| Reduce CTkScrollableFrame usage | ❌ Not done | Medium |

### 11.2 Server

| Optimization | Status | Impact |
|-------------|--------|--------|
| DB connection pooling | ✅ Done | High |
| Redis caching for dashboard | ✅ Done | Medium |
| Celery for async tasks | ✅ Done | Medium |
| Statement timeout (30s) | ✅ Done | Low |
| N+1 query optimization | ❌ Not done | Medium |
| Database query pagination | ✅ Done | High |
| Static file caching | ❌ Not done | Medium |
| API response compression | ❌ Not done | Low |

---

## 12. Priority Implementation Roadmap

### Phase 1: Foundation (Week 1-2) 🔴 Critical

| Task | Area | Effort |
|------|------|--------|
| Create `user_activity_log` table + API endpoint | Server | 2 days |
| Add usage telemetry to desktop app (tab opens, automation runs) | Desktop | 3 days |
| Create analytics dashboard page for admin | Admin | 3 days |
| Unify feedback + chat into one system | Server + Desktop | 2 days |

### Phase 2: User Experience (Week 3-4) 🟡 High

| Task | Area | Effort |
|------|------|--------|
| Integrate web frontend with Flask server | Web + Server | 3 days |
| Add user web dashboard (license info, usage stats) | Server | 3 days |
| Add live chat widget to marketing pages | Web | 2 days |
| Implement push notifications (expiry, replies) | Server | 2 days |
| Add in-app auto-update mechanism | Desktop | 3 days |

### Phase 3: Advanced Features (Week 5-6) 🟢 Medium

| Task | Area | Effort |
|------|------|--------|
| Task queue system (batch automations) | Desktop | 4 days |
| Crash reporting and error telemetry | Desktop + Server | 2 days |
| Automated DB backup scheduler | Server | 1 day |
| User onboarding tour | Desktop | 3 days |
| API documentation | Server | 2 days |

### Phase 4: Polish (Week 7-8) 🔵 Low

| Task | Area | Effort |
|------|------|--------|
| Keyboard shortcuts | Desktop | 2 days |
| 2FA for admin panel | Server | 2 days |
| CSRF protection | Server | 1 day |
| Mobile responsive admin pages | Admin | 2 days |
| Multi-language support (Hindi) | Desktop + Web | 3 days |

---

## Appendix A: File Inventory

### Desktop Application (`src/`)

```
src/
├── main_app.py              # Main application entry (deleted/refactored)
├── lite_app.py              # Lite version entry
├── config.py                # Centralized configuration (444 lines)
├── state.py                 # AppState dataclass
├── tab_config.py            # Lazy tab loading definitions (44 tabs)
├── lite_config.py           # Lite version overrides
├── utils.py                 # Utilities (logging, paths, config)
├── ui_components.py         # Reusable UI widgets
├── location_data.py         # State/district/block data
├── app/
│   ├── app_ui.py            # UI Construction & Theme Mixin
│   ├── app_navigation.py    # Navigation & Tab Management Mixin
│   ├── app_automation.py    # Browser automation logic
│   ├── app_license.py       # License validation
│   └── __init__.py
├── managers/
│   ├── browser_manager.py   # Chrome/Edge/Firefox management
│   ├── sound_manager.py     # Sound effects
│   ├── icon_manager.py      # Icon loading & caching
│   ├── workflow_manager.py  # Workflow orchestration
│   └── services.py          # Service layer
└── tabs/                    # 44 automation tab modules
    ├── base_tab.py          # Base automation tab class
    ├── home_tab.py          # Dashboard/Home
    ├── feedback_tab.py      # Support chat
    ├── about_tab.py         # License info
    ├── settings_tab.py      # App settings
    └── ... (39 more tabs)
```

### Server Application (`nrega-server/`)

```
nrega-server/
├── run.py                   # Entry point
├── Dockerfile               # Docker build
├── docker-compose.yml       # Multi-container setup
├── requirements.txt         # Python dependencies
├── migrations/              # SQL migration files
│   ├── 001_initial_schema.sql
│   ├── 002_feedback_optimization.sql
│   └── 003_chat_messages.sql
├── app/
│   ├── __init__.py          # create_app() — Flask app factory
│   ├── models.py            # Database models & connection pool
│   ├── extensions.py        # Flask extensions (Limiter)
│   ├── cache.py             # Redis cache wrapper
│   ├── celery_app.py        # Celery configuration
│   ├── tasks.py             # Async tasks (email, bulk messaging)
│   ├── metrics.py           # Prometheus metrics
│   ├── logging_config.py    # Structured JSON logging
│   ├── utils.py             # Shared utilities, auth decorators
│   ├── http_utils.py        # HTTP response helpers
│   ├── validation.py        # Request validation schemas
│   ├── sanitize.py          # XSS sanitization
│   ├── migrations.py        # Migration runner
│   ├── backup_scheduler.py  # Automated DB backup
│   ├── repositories/        # Data access layer
│   │   ├── license_repo.py
│   │   ├── payment_repo.py
│   │   ├── feedback_repo.py
│   │   ├── coupon_repo.py
│   │   └── base.py
│   ├── services/            # Business logic layer
│   │   ├── license_service.py
│   │   ├── payment_service.py
│   │   ├── device_service.py
│   │   └── trial_service.py
│   ├── routes/
│   │   ├── api/             # REST API endpoints
│   │   │   ├── auth.py, feedback.py, payments.py
│   │   │   ├── storage.py, reseller.py
│   │   │   ├── chat.py, health.py
│   │   │   └── __init__.py
│   │   ├── admin/           # Admin panel routes
│   │   │   ├── dashboard.py, users.py, feedback.py
│   │   │   ├── transactions.py, mailing.py
│   │   │   └── __init__.py
│   │   ├── frontend/        # User-facing web routes
│   │   │   ├── auth.py, pages.py
│   │   │   └── __init__.py
│   │   ├── file/            # File management
│   │   ├── admin_routes.py
│   │   ├── file_routes.py
│   │   └── frontend_routes.py
│   ├── templates/
│   │   ├── admin/           # Admin panel templates
│   │   ├── public/          # User-facing page templates
│   │   ├── email/           # Email templates
│   │   └── auth/            # Authentication templates
│   └── static/              # Static assets (manifest, sw.js)
└── config/
    └── version.json         # Version information
```

### Web Frontend (`web/`)

```
web/
├── index.html               # Landing page
├── about.html               # About page
├── contact.html             # Contact form
├── how-to-use.html          # Usage guide
├── terms.html               # Terms of service
├── refund.html              # Refund policy
├── privacy.html             # Privacy policy
├── versions.html            # Version history
├── sitemap.xml              # SEO sitemap
├── robots.txt               # Crawler instructions
├── Readme.txt               # Web directory info
└── update_nregabot.py       # Update check script
```

---

## Appendix B: Current API Endpoints

### Public API (`/api/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/validate` | License key validation |
| POST | `/api/send-otp` | Send OTP for registration |
| POST | `/api/request-trial` | Request trial license |
| POST | `/api/login-for-activation` | Login for app activation |
| POST | `/api/request-deactivation` | Request device deactivation |
| POST | `/api/feedback` | Submit feedback |
| GET | `/api/feedback/thread` | Get feedback conversation thread |
| POST | `/api/feedback/send_message` | Send message in feedback thread |
| POST | `/api/create-order` | Create Razorpay order |
| POST | `/api/verify-payment` | Verify payment |
| POST | `/api/check-renewal-status` | Check if user qualifies for renewal |
| POST | `/api/validate-coupon` | Validate coupon code |
| POST | `/api/send-chat-message` | Send live chat message |
| GET | `/api/get-chat-messages` | Get chat history |
| POST | `/api/create-subscription-checkout` | Create subscription checkout |
| POST | `/api/verify-subscription-payment` | Verify subscription payment |
| GET | `/api/health` | Server health check |
| GET | `/api/metrics` | Prometheus metrics |

### Admin API (`/admin/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/admin/` | Dashboard |
| GET | `/admin/api/search-licenses` | Search licenses (AJAX) |
| GET | `/admin/api/dashboard-table` | Dashboard table (AJAX) |
| GET | `/admin/api/dashboard-sidebar` | Dashboard panels (AJAX) |
| POST | `/admin/update-user` | Update user details |
| POST | `/admin/update-devices` | Update max devices |
| POST | `/admin/remove-device` | Remove activated device |
| POST | `/admin/generate-key` | Generate license key |
| POST | `/admin/update-announcement` | Update global announcement |
| POST | `/admin/admin-action` | Block/unblock/delete/extend |
| POST | `/admin/import-keys` | Import CSV keys |
| GET | `/admin/export-users` | Export users CSV |
| GET | `/admin/export-keys` | Export keys CSV |

---

*This report was generated on July 27, 2026 after comprehensive analysis of the NREGA Bot codebase.*
