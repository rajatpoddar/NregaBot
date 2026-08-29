# 📣 Notification System Redesign Plan — "Message Center"

> **Goal:** WhatsApp + Email messaging ko ek simple, effective, scalable system banao —
> admin panel ka confusion khatam, message failures ki asli wajah dikhe, aur users ko
> sahi time par sahi message (spam nahi) mile.
> **Status:** ✅ Phase 0 DONE — Phase 1 core DONE — hub delivery overview LIVE
> **Date:** 12 Aug 2026
> **Scope:** `nrega-server/` (Flask backend + admin panel)

---

## 📌 Status & Progress (12 Aug 2026)

| Phase | Status | Kya hua |
|---|---|---|
| **Phase 0 — Quick wins** | ✅ **COMPLETE** | Failure categorization, false-timeout fix, mailing tracking, number cleanup, SMTP health, Message Center hub |
| **Phase 1 — One pipeline** | 🔄 **PARTIAL** (core + dedup done) | `message_logs` table + `notify_service.py` (send_event) + automator/version_notify migrated. **Message Center hub ab `message_logs` se delivery overview dikhata hai**. **Welcome/Renewal dual-send dedup done** (6 call sites → ek `send_welcome()`). **Baki:** `message_templates` merge + broadcast/mailing migration |
| **Phase 2 — Receipts + hub UI** | ⏳ Planned | Webhook delivery receipts (sabse high-value) + Message Center full tabs |
| **Phase 3 — Journeys + scale** | ⏳ Optional | Lifecycle journeys, partitions, failover |

> 🔎 Detailed changelog of Phase 0 implementation: **Section 4.1** below.

## 0. Executive Summary (Business View)

Aaj system me **4 alag messaging pages**, **5 alag template storage**, **3 alag send
paths** hain — isliye confusion hai. Bade companies (Stripe, Swiggy, CRED) ye sab ek
**"Notification/Message Center"** me rakhti hain: ek pipeline, ek template library, ek
delivery log, aur channels (WhatsApp/Email) sirf adapter hain.

**Kya banana hai — ek hi cheez:**

```
                    ┌─────────────────────────────────────┐
                    │        MESSAGE CENTER (admin)       │
                    │  1. Health & Delivery  (kya fail?)  │
                    │  2. Automations       (kya auto?)   │
                    │  3. Campaigns         (manual send) │
                    │  4. Template Library  (ek jagah)    │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │      notify_service (core engine)   │
                    │  event → template → personalize →   │
                    │  channels → queue → deliver → log   │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      WhatsApp (Evolution)    Email (SMTP)         In-app (future)
      ─ 1 queue + pacing      ─ Celery tasks       ─ app banner
      ─ webhook receipts      ─ delivery log       ─ popup
```

**Results:** 1 admin page se sab control; har failure ki reason dikhegi; templates ek
jagah; automation sab kuch khud (AI) likhega — admin ko bar-bar edit nahi karna padega.

---

## 1. Current State Analysis (Aaj kya hai)

### 1.1 Admin panel — 4 overlapping messaging pages

| Page | Route | Lines | Kya karta hai | Overlap |
|---|---|---|---|---|
| **WhatsApp Automation** | `/admin/whatsapp-automation` | 353 | 7 events ke toggles + template edit + version notify + renewal reminders | Templates (overlap with #4), stats |
| **Evolution Broadcast** | `/admin/evolution-broadcast` | 735 | Manual bulk/single WhatsApp + history + per-user details | Manual send (overlap with #3) |
| **Mailing Center** | `/admin/mailing` | 200 | Manual bulk Email **ya** WhatsApp (Celery) + target groups | Manual send (overlap with #2) |
| **Mailing Templates** | `/admin/mailing/templates` | 93 | Email templates CRUD | Template storage (overlap with #1) |
| *(AI Command Center)* | `/admin/ai-command-center` | 428 | AI auto-pilot on/off + AI template generation | Automation (overlap with #1) |
| *(Promo Popup)* | `/admin/promo` | — | Website popup | Alag (website) — theek hai |

### 1.2 5 alag template storage

| # | Where | Channel | Notes |
|---|---|---|---|
| 1 | `whatsapp_templates` (DB) | WhatsApp | 7 events (welcome, expiry_reminder, expired, renewal, inactive, app_update_required, factory_reset_advice) |
| 2 | `email_templates` (DB) | Email | Admin-created custom templates |
| 3 | `EMAIL_TEMPLATES` (code dict, `routes/admin/__init__.py`) | Email | 4 hardcoded (Send Key, Renewal Reminder, New Quarterly, New Half-Yearly) |
| 4 | `ai_auto_template_<event>` (app_settings, JSON) | WhatsApp | AI auto-pilot ke generated templates (24h cache) |
| 5 | `email/welcome_email.html` (Jinja file) | Email | Welcome/renewal branded email |

**Problem:** naya message banane ke liye 5 jagah dekhna padta hai. AI template
override karta hai manual ko (auto-pilot ON par) — admin ko pata nahi hota kaunsa
template actually gaya.

### 1.3 3 alag send paths (sab WhatsApp par jaa rahe hain)

| Path | Caller | Execution | Tracking |
|---|---|---|---|
| `broadcast.py::_send_whatsapp` | Broadcast + automator | Thread → `wa_queue` | `broadcast_logs` + `broadcast_log_details` |
| `tasks.py::send_bulk_message_async` | Mailing Center | Celery → `send_whatsapp_message` → `wa_queue` | ❌ koi log nahi |
| `whatsapp_utils.send_text` | queue worker | direct | log file only |

**Problem:** Mailing Center se bheje WhatsApp ka koi per-recipient record nahi banta —
fail ho to pata hi nahi chalta. Broadcast ke pass history hai, mailing ke paas nahi.

### 1.4 Kaunse messages kahan se trigger hote hain (message inventory)

**A. AUTOMATED (system khud bhejta hai — user action par trigger):**

| Event | Trigger | Channel | Files |
|---|---|---|---|
| Welcome (trial/purchase) | Signup/payment route | WhatsApp + Email | `payments.py`, `auth.py`, `oauth.py`, `pages.py` → `send_welcome_whatsapp` + `send_welcome_email` |
| Renewal confirmation | Payment success | WhatsApp + Email | `payments.py` → `send_renewal_whatsapp` + `send_welcome_email(is_renewal=True)` |
| Expiry reminders (7/3/1d) | Scheduler 8 AM IST | WhatsApp | `whatsapp_automator.check_expiry_reminders` (+ early-bird offer) |
| Expired alert | Scheduler 8 AM | WhatsApp | `check_expired_licenses` |
| Inactive re-engagement (30d) | Scheduler 8 AM | WhatsApp | `check_inactive_users` |
| App update required | `/api/validate` heartbeat | WhatsApp | `version_notify_service` |
| Factory reset advice | `/api/validate` (very old) | WhatsApp | `version_notify_service` (appended) |
| Daily automation report | Scheduler 6 AM (opt-in) | WhatsApp (Excel doc) | `send_daily_whatsapp_report` |
| OTP verification | Login/signup | WhatsApp + Email | `tasks.send_otp_email_async` |

**B. MANUAL (admin khud bhejta hai):**

| Tool | Target | Channel | Tracking |
|---|---|---|---|
| Broadcast | all / active / expired / specific user | WhatsApp | ✅ full history |
| Mailing Center | all / active / expiring_soon / expired / trial / specific | Email **ya** WhatsApp | ❌ none |
| Send Key Manually (email template) | specific | Email | ❌ none |
| Admin ad-hoc `send_custom_email` | specific (licenses, users, auth, reseller routes) | Email | ❌ none |

**C. DUPLICATE-SEND PROBLEM (bade wala):**
Welcome aur Renewal ke liye `send_welcome_email` + `send_welcome_whatsapp` **alag-alag
calls** har payment/signup route me hain (5 jagah copy-paste). Ek jagah fail ho, doosri
chalti hai; timing bhi sync nahi.

---

## 2. Root-Cause Analysis — "Message fail kyun ho rahe hain?"

### 2.1 WhatsApp failure reasons (Evolution API se milta hai, par dikhta nahi)

| Error (code) | Asli reason | Aaj kya hota hai |
|---|---|---|
| `HTTP 400: invalid number` | Number WhatsApp par nahi / galat format (10 digit ya 91 prefix nahi) | Broadcast details me dikhta hai (raw), automator me sirf "failed" |
| `HTTP 400: group/chat not found` | Number deactivated / user ne WhatsApp chhod diya | Same — raw string, koi categorization nahi |
| `HTTP 429` | Evolution rate-limit | 1 retry (2s backoff), phir fail |
| `HTTP 500/502/503/504` | Evolution down / container restart | 1 retry, phir fail |
| `Connection error: timed out` | Evolution reachable nahi — **delivery uncertain** (deliver bhi ho sakta hai!) | Fail count hone ke bawajood message pahunch gaya ho sakta hai |
| `Timed out waiting for send slot` | Queue backlog (500 users × 3s = 25 min; wait_timeout khatam) | Broadcast thread "timeout" bolta hai, par worker ne baad me send kar diya — **false failure!** |
| `MAIL CONFIG MISSING` (email) | SMTP env set nahi | Log me error, user ko kuch nahi |

### 2.2 Structural problems (failures ka source)

1. **Wait-timeout false failures:** `broadcast.py` `wait_timeout=120` par bulk me pehle
   wale users timeout ho sakte hain jabki worker ne baad me send kar diya. Status galat.
2. **No delivery receipts:** Evolution webhook `SEND_MESSAGE` events **configured hain**
   (chat ke liye), par **delivered/failed status kabhi message_logs me nahi likha jaata**.
   Broadcast history sirf "send attempt" dikhata hai, "asli delivery" nahi.
3. **Email ka koi log nahi:** `send_custom_email` return bool karta hai; bulk Celery
   tasks error ko sirf log file me daalte hain. Per-recipient fail/success kahin record
   nahi hota. Admin ko email fail hota hua dikh hi nahi sakta.
4. **No retry policy:** Email me zero retry. WhatsApp me sirf transient (429/5xx) par 1
   retry. No backoff chain, no dead-letter.
5. **Number quality:** `licenses.user_mobile` me koi validation nahi — 10-digit bina 91,
   `+91` prefix, spaces, 0-prefix — sab mix. Evolution ko raw bheja jata hai.
6. **No per-recipient unsubscribe/opt-out** — WhatsApp blocked karne wale users ko bar-bar
   message jaata hai (is_blocked sirf license-level hai).

---

## 3. Target Architecture — Big-Company Strategy

### 3.1 Principles (kya follow karein)

| Principle | Kya matlab |
|---|---|
| **1 pipeline, N channels** | Har message ek `notify_service.send(event, user)` se — channel decide karta hai system (default WhatsApp, email fallback), admin ko channel se matlab nahi |
| **Event-first, template-second** | Templates event se bind hote hain (welcome = welcome template), ad-hoc free-text nahi |
| **One log of truth** | `message_logs` table — har send (auto + manual + email + WA) ka status, error code, error reason |
| **Deliverability > Sending** | "Send ho gaya" nahi, "deliver hua" matter karta hai — webhook receipts se track |
| **Frequency capping** | Har user ko max N marketing messages/week — spam se bachao (WhatsApp ban bhi toot-ta hai) |
| **Self-healing defaults** | Templates khud AI likhega (existing auto-pilot) — admin sirf exceptions par edit kare |
| **Zero-config ops** | Health card: Evolution/SMTP/queue status + failure reasons — pehli nazar me sab pata |

### 3.2 New core: `notify_service.py`

```
notify_service.send_event(event_type, user_data, extra_context=None)
    │
    ├─ 1. TEMPLATE: resolve template (DB → AI override → built-in fallback)
    ├─ 2. PERSONALIZE: whatsapp_placeholders.build_context + render
    ├─ 3. CHANNELS: channel_policy(event) → ["whatsapp"] / ["email"] / ["both"]
    ├─ 4. FREQUENCY CAP: user ke is week ke marketing msgs < limit?
    ├─ 5. QUEUE: wa_queue (WA) / celery (email) — dono async
    └─ 6. LOG: message_logs me row (queued) → status updates (sent/delivered/failed)
```

**Key decision — ek hi `message_logs` table:**

```sql
CREATE TABLE message_logs (
    id             BIGSERIAL PRIMARY KEY,
    license_key    VARCHAR(255),              -- index
    event_type     VARCHAR(50),               -- welcome, expiry_reminder, broadcast, campaign...
    channel        VARCHAR(10),               -- whatsapp | email
    template_id    INTEGER,                   -- message_templates.id
    template_ver   INTEGER,
    status         VARCHAR(20),               -- queued | sent | delivered | failed | skipped
    error_code     VARCHAR(50),               -- invalid_number, provider_down, timeout, smtp_auth...
    error_reason   TEXT,                      -- raw detail (masked)
    provider_msg_id VARCHAR(100),             -- Evolution message id (receipt match ke liye)
    recipient_masked VARCHAR(30),             -- DPDP: 9X******X0
    sent_at        TIMESTAMP,
    delivered_at   TIMESTAMP,
    created_at     TIMESTAMP DEFAULT NOW()
);
-- Partitioning: monthly (RANGE on created_at) — 10k users scale par bhi query fast
```

### 3.3 Unified template store: `message_templates`

```sql
CREATE TABLE message_templates (
    id          SERIAL PRIMARY KEY,
    event_type  VARCHAR(50) NOT NULL,          -- welcome / expiry_reminder / campaign_*
    channel     VARCHAR(10) NOT NULL DEFAULT 'whatsapp',
    name        VARCHAR(200),
    body        TEXT NOT NULL,                 -- {user_name} placeholders
    subject     TEXT,                          -- email ke liye
    is_active   BOOLEAN DEFAULT TRUE,
    is_ai_generated BOOLEAN DEFAULT FALSE,
    version     INTEGER DEFAULT 1,
    updated_at  TIMESTAMP DEFAULT NOW()
);
```

- **Migration plan:** `whatsapp_templates` + `email_templates` + `EMAIL_TEMPLATES` dict →
  `message_templates` me merge (event_type + channel). AI templates `app_settings` se
  `is_ai_generated` rows me chale jaate hain.
- **Fallback chain:** DB template → built-in default (code) — template delete/empty hone
  par kabhi blank message nahi jayega.

### 3.4 Admin panel redesign — "Messaging" section

```
Messaging (sidebar me ek hi section — 4 pages → 1 hub + 2 standalone)

├─ 1. Message Center        (NEW — dashboard)
│      ├─ Health Card:  Evolution ✅/❌ | SMTP ✅/❌ | Queue depth | Last 24h
│      │               delivered / failed / top-5 failure reasons (pie)
│      ├─ Automations tab: 7 events × toggle × template preview (AI badge)
│      │       └─ "Edit" → Template Library (same page, modal)
│      ├─ Campaigns tab:   composer = channel(auto) × audience(segment) ×
│      │       message(template ya custom) → Send / Schedule
│      │       └─ History: per-recipient status + failure reason + retry button
│      └─ Deliverability tab: failed logs, error_code grouping, retry action,
│              invalid numbers list → "Fix numbers" (normalize job)
│
├─ 2. WhatsApp Chat         (STANDALONE — support inbox, alag kaam)
└─ 3. Promo Popup           (STANDALONE — website popup, alag kaam)
```

- `evolution-broadcast` page → **Campaigns tab** (history+details UI reuse)
- `mailing` page → **Campaigns tab** (channel picker = WhatsApp/Email/Both)
- `mailing/templates` → **Template Library** (merged, filter by channel/event)
- `whatsapp-automation` → **Automations tab** (AI auto-pilot toggle + AI Command Center
  messaging-part yahan merge)
- AI Command Center (full page) messaging/automation part ko yahan le aao; AI bot
  (support bot) wahan rehta hai

### 3.5 Journeys (user lifecycle — big-company pattern)

Har user ek lifecycle me hai → har stage ka sahi message:

```
TRIAL ──► WELCOME (WA+Email, day 0)
   │          ├─ Onboarding tip (day 2, if inactive)      [NEW - optional]
   │          └─ 5-days-left trial reminder (day 25)      [NEW - optional]
PAID  ──► RENEWAL CONFIRM (WA+Email)
   │          ├─ Feature highlight (day 15)               [NEW - optional]
   │          └─ Inactive re-engage (30d no use)
EXPIRE ──► 7d / 3d / 1d reminders (early-bird offer)
   │          └─ Expired alert (day 0) + win-back (day 7) [NEW - optional]
```

Journeys config = `automation_settings` me intervals (already hai), templates =
`message_templates`. Naya stage add karna = ek row, no code.

---

## 4. Implementation Phases

### Phase 0 — Quick wins (1-2 din, no schema change) — ✅ DONE 12 Aug 2026

| Task | Status | Detail |
|---|---|---|
| 1. Failure categorization in broadcast details | ✅ | `categorize_error()` → `error_code` (invalid_number / timeout / provider_down / rate_limited / queue_backlog / smtp_*) — history details me `[code] reason` format |
| 2. Fix false "timeout" failures | ✅ | `BroadcastQueuedError` — queue me safely pahunchne par "queued (delivery pending)" amber badge, fail count me nahi |
| 3. Mailing Center ko log do | ✅ | Campaign → `broadcast_logs` row (`campaign_email`/`campaign_whatsapp`) + har recipient `broadcast_log_details` me (PII masked); Celery task send ke baad status update |
| 4. Mobile number normalization job | ✅ | `normalize_mobile()` (10-digit→91, spaces/`+`/`-`/`()`/0-prefix/091+10-digit cleanup) + admin **Fix Numbers** button (broadcast page) |
| 5. SMTP health card | ✅ | `check_smtp_health()` shared helper → Mailing page green/red card + Message Center health; config-missing/auth/connect sab visible |
| 6. Sidebar + Message Center hub | ✅ | Naya **Message Center** page (`/admin/message-center`) — health cards, queue depth, last-24h stats, **top failure reasons grouped**, tool quick-links |

#### 4.1 Phase 0 — Implementation Changelog (what changed)

| File | Change |
|---|---|
| `app/whatsapp_utils.py` | `categorize_error()` (8 failure codes, order-aware patterns), `normalize_mobile()` public wrapper, `_normalize_mobile()` ab spaces/dashes/`()`/0-prefix bhi clean karta hai (send path par bhi apply — Evolution ko E.164 jaata hai) |
| `app/routes/admin/broadcast.py` | `BroadcastQueuedError` exception; `_send_whatsapp` wait-timeout ko raise karta hai (fail nahi); `_insert_broadcast_detail` error ko `[code] reason` store karta hai; bulk path me `queued` counter + status logic (sab-fail→failed, baaki→completed with note); naya `POST /api/fix-mobile-numbers` |
| `app/routes/admin/mailing.py` | POST par campaign log + per-recipient detail rows (PII masked) + `broadcast_id`/`detail_id` Celery task ko; naya `GET /api/smtp-status` (shared helper se) |
| `app/tasks.py` | `send_bulk_message_async` ab `broadcast_id`/`detail_id` accept karta hai; naya `_update_mailing_tracking()` — detail status update + counts recompute (row-lock serialized, READ COMMITTED) + meaningful status CASE (running/failed/completed) |
| `app/whatsapp_automator.py` | `_send_automated_whatsapp` ab `BroadcastQueuedError` catch karta hai → `queued` status (automated sends me bhi false-failure fix) |
| `app/utils.py` | `check_smtp_health()` shared helper (config missing / invalid port / auth fail / connect fail — kabhi raise nahi) |
| `app/routes/admin/message_center.py` + `app/templates/admin/admin_message_center.html` | **NEW** — Message Center hub + `/api/messaging-health` (Evolution + SMTP + queue depth + last-24h stats + top failure reasons) |
| `app/templates/admin/admin_base.html` | Sidebar Messaging section me **Message Center** top entry |
| `app/templates/admin/admin_evolution_broadcast.html` | **Fix Numbers** button + JS; `queued` status badge (history table + details table); auto-refresh me queued bhi active count |
| `app/templates/admin/admin_mailing.html` | SMTP health card + `checkSmtpHealth()` JS (60s auto-refresh) |

**Verified:** sab Python files syntax-checked + import-smoke-tested; `categorize_error`/`normalize_mobile` unit-tested (7 formats); code-reviewer ke findings fix kiye (dead SQL CASE, automator false-fail, unused import, SMTP DRY, history badge).

**Still OPEN from Phase 0 scope:** Mailing Templates page abhi `message_templates` merge hone se pehle `email_templates` hi use karta hai (Phase 1 me merge hoga). Admin ad-hoc `send_custom_email` (licenses/users/auth routes) abhi bhi untracked — Phase 1 me `notify_service` par migrate hoga.

### Phase 1 — One pipeline (3-4 din) — 🔄 core DONE 12 Aug 2026

| Task | Status | Detail |
|---|---|---|
| 1. `message_logs` table + migration | ✅ | `migrations/026_message_logs.sql` — status/error_code/error_reason/provider_msg_id/recipient_masked + indexes |
| 2. `notify_service.py` core | ✅ | `send_event()` = enabled check → template resolve (DB + AI override) → personalize → channel policy → wa_queue/SMTP → `message_logs` + legacy `broadcast_logs`; `body_override` support (version_notify); public helpers `is_event_enabled`/`get_schedule_days`/`get_template_active` |
| 3. `whatsapp_automator` → `notify_service` | ✅ | 5 event functions delegate to `send_event`; expiry dedup, early-bird, inactive weekly-gate preserved; string-expiry `expiry_date` handling preserved |
| 4. `version_notify_service` → `notify_service` | ✅ | `_compose` + `body_override` path; cooldown logic unchanged; `key` ab SELECT me (message_logs.license_key NULL nahi) |
| 5. `message_templates` table + data migration | ⏭️ NEXT | `whatsapp_templates`/`email_templates`/`EMAIL_TEMPLATES` merge (dry-run + old tables read-only 1 release) |
| 6. Welcome/Renewal dual-send dedup (WA+Email ek call) | ✅ | `notify_service.send_welcome()` — WhatsApp pipeline + branded email (synchronous, message_logs me queued→sent/failed) — 6 call sites migrated (see 4.3) |
| 7. Mailing/broadcast → `notify_service` | ⏭️ NEXT | Manual paths bhi same pipeline |
| 8. **Hub delivery overview from `message_logs`** | ✅ | Message Center ab per-channel + per-event + error-code stats live dikhata hai (see 4.2) |

**Phase 1 core changelog:** `migrations/026_message_logs.sql` (new), `app/notify_service.py` (new), `whatsapp_queue.py` (BroadcastQueuedError yahan move), `whatsapp_automator.py` (refactor), `version_notify_service.py`, `tasks.py` (`_update_message_log_status`), `broadcast.py` (re-export). Verified: syntax + imports + no circular imports + unit checks.

#### 4.2 Phase 1.5 — Message Center hub → message_logs delivery overview (12 Aug 2026)

| File | Change |
|---|---|
| `app/routes/admin/message_center.py` | `_stats_from_message_logs()` — last-24h stats ab pipeline log se: **per-channel** (WhatsApp/Email sent/failed/queued), **per-event** (top 8, `total = sent + failed + queued` — numbers hamesha reconcile), **failure reasons** ab `error_code` column se (structured, raw parsing nahi). `_stats_from_broadcast_logs()` legacy fallback (FILTER-clause SQL + `[code]` prefix parse) — migration abhi na chali ho / table khali ho to bhi hub kabhi blank nahi. Smart merge: message_logs khali → legacy data + `log_source` flag |
| `app/templates/admin/admin_message_center.html` | 2 naye sections: **Delivery by Channel** + **Delivery by Event** (stacked mini-bars green=sent/red=fail, amber=queued count, friendly labels, empty-states). **Log-source badge** (`📊 message_logs live` vs `🕰 legacy`). Reviewer fixes: `esc()` XSS helper for fallback labels, complete `EVENT_LABELS` map (campaign_email/app_update_required/admin_notify...), queued count events me bhi |

**Verified:** Python + Jinja + JS syntax; unit test bucket math (5 sent/1 fail/2 queued → totals reconcile); code-reviewer findings fix kiye. **Note:** `message_logs` abhi khali hai jab tak migration 026 server restart par apply nahi hoti — tab tak hub legacy broadcast data + empty-states dikhayega.

#### 4.3 Phase 1.6 — Welcome/Renewal dual-send dedup (12 Aug 2026)

| File | Change |
|---|---|
| `app/notify_service.py` | Naya `send_welcome(user_data, license_key, is_trial, is_renewal, channels)` — **EK call = WhatsApp + Email dono**: WhatsApp `send_event('welcome'|'renewal')` pipeline se (toggle+template gate, message_logs), email branded `welcome_email.html` synchronous + `message_logs` queued→sent/failed (SMTP fail par `smtp_send_failed` code — Message Center me ab email failures bhi dikhte hain). `_build_url` yahan move (automator se dedup). **Email leg best-effort log** — DB down ho to bhi email hamesha jata hai (purana zero-DB-dependency preserve). Email intentionally ungated (purana behavior) |
| `app/whatsapp_automator.py` | `_build_url` ab notify_service se import; `send_welcome_whatsapp`/`send_renewal_whatsapp` DEPRECATED wrappers (backward-compat, same pipeline) |
| `api/auth.py` (request-trial), `api/payments.py` (verify-payment + verify-subscription-payment), `api/oauth.py` (google trial), `frontend/pages.py` (web trial), `frontend/oauth.py` (web google trial) | 6 jagah ke alag-alag `send_welcome_email` + `send_welcome_whatsapp`/`send_renewal_whatsapp` calls → ek `send_welcome(...)`; unused imports cleaned. **Bonus:** web google trial users ko ab WhatsApp welcome bhi jaata hai (pehle sirf email tha — gap fix) |

**Verified:** syntax + imports + no circular (notify_service → utils function-level); unit test dispatch (welcome/renewal event-type, key normalization, channels override, legacy email-data shape); code-reviewer fixes (DB-down email-block edge case, dead-wrapper deprecation notes). **Note:** `send_welcome_email` util ab sirf notify_service se call hota hai (single entry).

### Phase 2 — Delivery receipts + admin hub (3-4 din)

| Task | Files |
|---|---|
| 1. Evolution webhook → `message_logs.status = delivered/failed` (SEND_MESSAGE + MESSAGES_UPDATE events) | `routes/api/whatsapp_chat.py` (ya naya `routes/api/webhook.py`), `notify_service.py` |
| 2. Email delivery: SMTP send result log + (optional) SES/Resend webhook bounce | `utils.py`, `tasks.py` |
| 3. **Message Center hub page** (health + automations + campaigns + deliverability) | `routes/admin/message_center.py` + `admin_message_center.html` — **delivery-overview part already LIVE** (health + last-24h + channels/events/error-codes, §4.2); baaki tabs (automations/campaigns/templates/deliverability) isi page par merge honge |
| 4. Campaign composer (audience segments, template picker, preview, schedule) | above + `segments.py` helper |
| 5. Template Library UI (filter, AI-generate, version) | `routes/admin/templates.py` + html |
| 6. Frequency cap per user/week (marketing events) | `notify_service.py` + `message_logs` query |
| 7. Retry action (failed rows → requeue) | Message Center Deliverability tab |

### Phase 3 — Journeys + scale (2-3 din, optional)

| Task | Detail |
|---|---|
| 1. Journey stages (day-2 onboarding, trial reminder, win-back) | templates + settings rows, no code |
| 2. Per-user channel preference (`licenses.notify_channel = both|wa|email`) | migration + settings tab (user-facing, later) |
| 3. `message_logs` monthly partition + archive policy | scale (10k users) |
| 4. Provider failover (second Evolution instance) | `evolution_config` env — config-only, no new infra |
| 5. Error-spike alert on message failures (already have pattern `error_spike_monitor`) | monitor for `message_logs.failed` |

---

## 5. "No Cluster" Scaling Strategy (10k users par bhi)

- **Ek hi server + gunicorn workers** rehta hai (monolith — ops simple).
- WhatsApp throughput: 1 queue + Redis pacing (already) = ~1 msg/3s = ~28k/day. **Enough.**
- Scale levers (infra nahi, config):
  1. `WHATSAPP_SEND_INTERVAL` 2-6s clamp — sirf safty band
  2. Provider failover = 2nd Evolution instance env (API calls alternate)
  3. `message_logs` monthly partitions + indexes → query fast
  4. Celery worker count badao (email side) — same queue, more workers
- Kabhi bhi per-tenant cluster nahi chahiye — ye single-tenant SaaS hai, data model simple
  rehta hai (licenses hi tenant hai).

---

## 6. Success Metrics (kaise pata chalega kaam hua)

| Metric | Aaj | Target (90 din) |
|---|---|---|
| Admin messaging pages | 4 pages + 3 storage | 1 hub + 2 standalone |
| Message failure visibility | Raw strings, email zero | error_code + reason, per-recipient, email included |
| False failures (timeout but delivered) | Common (bulk) | ~0 (queued-status fix) |
| Welcome/Renewal send calls | 5 copy-paste places | 1 call |
| Template sources | 5 | 1 (`message_templates`) |
| User complaints "message nahi aaya" | unknown | ↓50% (delivery receipts) |
| WhatsApp block risk | unknown | ↓ (frequency cap + invalid-number cleanup) |

---

## 7. Risks & Notes

- **Migration risk:** `whatsapp_templates`/`email_templates` merge me koi template chhut
  na jaye — data migration script + dry-run. Old tables read-only rehti hain 1 release.
- **Webhook receipts:** Evolution `SEND_MESSAGE` event me message id aati hai — queue
  response me bhi. Match karke status update (message_logs.provider_msg_id).
- **DPDP:** PII masking pehle se hai (`mask_pii_text`, `mask_email`) — `message_logs`
  me bhi masked recipients hi store karo.
- **Admin ad-hoc emails** (licenses/users/auth routes ke `send_custom_email`) — Phase 1
  me `notify_service` par migrate (event_type=`admin_notify`), taki woh bhi logged hon.

---

## 8. Phase 0 — Checklist (✅ sab complete — 12 Aug 2026)

- [x] `broadcast.py`: error → `error_code` mapping (invalid_number/timeout/provider_down/rate_limited/queue_backlog)
- [x] `broadcast.py`: wait-timeout → "queued/pending" status (false failure fix) — broadcast + automator dono
- [x] `mailing.py`: Celery sends → `broadcast_logs` + per-recipient `broadcast_log_details` (PII masked)
- [x] Mobile normalization job + admin "Fix Numbers" button
- [x] SMTP health check card (Mailing page + Message Center hub)
- [x] Message Center hub page (`/admin/message-center`) + sidebar entry

## 9. Next Steps — Phase 1 remaining + Phase 2

Phase 0 ne **visibility** di, Phase 1 core ne **pipeline** di (ab automated sends
`message_logs` me logged hote hain), aur hub ab usi log se **live delivery stats**
dikhata hai. Baaki kaam:

### 9.1 Remaining Phase 1 (priority order)

| # | Task | Kyon |
|---|---|---|
| 1 | **`message_templates` table + data migration** (5-storage merge, dry-run) | Template confusion ka root fix — ek jagah sab templates |
| 2 | **Broadcast + Mailing → `notify_service`** | Manual paths bhi same pipeline — tracking uniform |
| 3 | **Admin ad-hoc emails** (`send_custom_email` in licenses/users/auth/reseller routes) → `send_event('admin_notify')` | Woh bhi logged ho jayenge |

### 9.2 Ready-made building blocks (Phase 0 + 1 se)

- `categorize_error()` → `message_logs.error_code` me already fill hota hai
- `send_event()` → welcome/renewal email+whatsapp dono leg handle karta hai
- `message_logs` + `recipient_masked` + indexes → Phase 2 webhook receipts ka base
- `wa_queue` + Celery (`message_log_id` kwarg) → channel adapters ready

### 9.3 Phase 2 (uske baad — priority order)

1. **Webhook delivery receipts** ⭐ (sabse high-value) — Evolution
   `SEND_MESSAGE`/`MESSAGES_UPDATE` → `message_logs.status = delivered/failed`
   (`provider_msg_id` match). Iske bina hub sirf "send attempt" dikhata hai, "asli
   delivery" nahi — `provider_msg_id` column aur webhook dono pehle se ready hain.
2. **Message Center full tabs** — Automations / Campaigns / Templates / Deliverability
   (routes abhi scattered pages par hain — hub me merge; delivery overview ka
   foundation already live hai).
3. **Frequency cap** per user/week (marketing events).

### 9.4 Dhyan dene wale points

1. **Migration safety:** `whatsapp_templates`/`email_templates`/`EMAIL_TEMPLATES` merge
   me koi template na chhute — data migration script + dry-run; purani tables 1 release
   read-only rehti hain.
2. **Existing Celery queue:** `send_bulk_message_async` signature me kwargs append hote
   hain (defaults) — broker me purane tasks crash nahi karte.
3. **DPDP:** `message_logs.recipient_masked` hi store hota hai (masking built-in).
4. **Email leg personalization:** email_body JINJA syntax me likhna hoga (`{{ user_name }}`)
   — single-brace `{user_name}` (whatsapp convention) literal reh jata hai (notify_service
   me documented).
5. **Hub empty-state expect karo:** jab tak migration 026 server restart par apply nahi
   hoti, `message_logs` khali hai → hub legacy broadcast data + empty-states dikhayega
   (by design, crash nahi). Live numbers dekhne ke liye pehle deploy + restart zaroori.
