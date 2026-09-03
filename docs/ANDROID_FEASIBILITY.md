# NREGA Bot — Android App Feasibility & Plan

> **Status:** RESEARCH / PLANNING doc — koi code change nahi. 3 Sep 2026, verified against desktop **v3.2.7** and the current `nrega-server/` tree.
> **Owner decision input:** Rajat chose **native Android (Kotlin)** as the target stack; this doc evaluates what is possible, what the server already offers, and what must be built.
> **Product intent:** [`docs/PRD.md`](PRD.md) · Desktop architecture: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) · Rules: [`docs/RULES.md`](RULES.md)

---

## 1. Executive summary (30 seconds)

- **NREGA Bot ka core = desktop Selenium automation jo user ke apne browser + apne MGNREGA portal login se chalti hai** (PRD §1: "not a SaaS web app, not a server-side scraper"). Ye constraint Android ko inheritance me milta hai.
- **"48 tabs ka bot phone par chalana" realistic nahi hai.** Mobile Chrome par Selenium ko USB-debugging chahiye (field users ke liye impossible), portal desktop-oriented hai, aur login-session model (user ka apna browser) Android par exist nahi karta.
- **Jo REALISTIC hai:** ek **native Android companion app** jo existing `nrega-server/` API surface ko use kare — license/expiry, renewal purchase, cloud files (view/download/WhatsApp-share), activity log, in-app WhatsApp support chat, notifications. Server ka ~80% infra **pehle se ready hai** (evidence section 3).
- **Second realistic phase:** field data collection (GPS/photo) + **remote-run queue** — Android se job enqueue → desktop (jo server ko har ~2 min poll karta hai) pull karke automation chalaaye → result wapas server.
- **Kotlin-native me kya NEW banana hoga (server side + app side):** app session-token flow, FCM push (Firebase service account file hai, code nahi), job-queue API, aur mobile-friendly auth UX (email+OTP ya license-key entry).

---

## 2. Why "bot on phone" is ruled out (with evidence)

| Barrier | Detail |
|---|---|
| **Selenium host model** | `BrowserManager` (`src/managers/browser_manager.py`) launches Chrome/Edge detached with `--remote-debugging-port=9222` + CDP, or Selenium-managed Firefox. This is a desktop-browser pattern; Android Chrome needs ADB/USB debugging for CDP — not deployable to GRS users. Appium automates *apps*, not the operator's own portal session. |
| **Login session** | Bot uses the user's existing portal login in a persistent profile (`~/ChromeProfileForNREGABot/`). Phone par koi "user ka apna desktop browser session" nahi hai; credentials store karna DPDP + portal-policy risk. |
| **Product identity** | PRD §1 explicitly: bot "always runs on the operator's own desktop, with their own browser, using their own login credentials". Server-side Selenium (NAS/VPS) isi ko todta hai aur shared-IP/portal-block risk deta hai. |
| **48-tab DOM automation** | Portal DOM parsing/selectors (`src/tabs/*_tab.py`) desktop DOM ke against likhe hain; mobile portal layouts alag hain. Port = full rewrite + continuous maintenance, phone performance irrelevant. |

**Conclusion:** Android = **client of the ecosystem**, not a second execution engine (unless someday portal provides official APIs — out of scope).

---

## 3. What the server already offers (evidence inventory)

Gathered from `nrega-server/app/routes/` + desktop call sites in `src/`. Two auth models exist (verified `nrega-server/app/utils.py:112-140`):

1. **License-key bearer token** — `Authorization: Bearer <license_key>` → `token_required` decorator (DB check: exists, not expired, not blocked). Desktop calls use this everywhere (verified e.g. `src/tabs/file_management_tab.py:403`).
2. **Web session** — `session['license_key']` set by frontend email+OTP login → `session_required`. Browser users (web dashboard) use this.

### 3.1 Endpoints a mobile companion app can consume TODAY (no server change)

| Area | Endpoints | Auth | Desktop evidence |
|---|---|---|---|
| **License status/expiry** | `POST /api/validate`, `POST /api/heartbeat` | bearer / body key | `src/managers/services.py:85` |
| **State registry / app flags** | `GET /api/app-config` | — | heartbeat loop (~2 min poll, `app_license.py:1806`) |
| **Cloud files** | `/files/api/list`, `/files/api/list/<id>`, `/files/api/upload`, `/files/api/create-folder`, `/files/api/download/<id>`, `/files/api/delete/<id>`, `/files/api/whatsapp-send` | bearer (`token_required`) | `src/tabs/file_management_tab.py` |
| **File sharing (no auth)** | `/public/shared/<token>`, `/public/shared-collection/<token>` | share token | file manager UI |
| **Activity history** | `GET /api/activity-log`, `/api/activity-log/stats` | session (web) | web dashboard |
| **Support chat** | `/api/whatsapp-chat/send`, `/api/whatsapp-chat/messages?since_id=` | bearer | `src/tabs/whatsapp_chat_tab.py` |
| **Renewal / payments** | `/api/check-renewal-status`, `/api/validate-coupon`, `/api/get-buy-link`, `/api/create-subscription-checkout`, `/api/verify-subscription-payment`, `/api/razorpay-webhook` | session/bearer mix | `app_license.py:1611-1645` |
| **Device mgmt** | `/api/request-deactivation`, `/api/set-device-name` | bearer | `app_license.py:276`, `about_tab.py:879` |
| **Notify preferences** | `/api/notify-settings` | bearer | `src/tabs/settings_tab.py:1478` |
| **User data** | `/api/user-data/backup`, `/api/update-location` | bearer | `app_license.py:2149+` |
| **Location pool** | `/api/location-data/sync`, `/api/location-data/get` | sha256-key body | `src/location_sync.py` |
| **OTP auth (account-level)** | `/api/send-otp`, `/api/login-for-activation`, `/api/oauth/begin|status|config|complete-profile`, `/api/get-auth-token` | — | `app_license.py:570-1097` |

### 3.2 PWA seed already on server (verified)

`nrega-server/app/static/` contains **`manifest.webmanifest` + `sw.js`**; `templates/public/base.html` links the manifest. Meaning the web dashboard is already PWA-*capable* with minor work — relevant if you ever want an installable web fallback (scaling plan Phase 4 #21: "Mobile companion — PWA first").

### 3.3 Notification pipeline (already built, WhatsApp/email only)

`notify_service.py` = unified pipeline (`send_event()` → template → channel → queue → `message_logs`). Event types include welcome, renewal reminders (`whatsapp_automator.py::check_expiry_reminders`), version updates, expiry offers. **No FCM/push channel exists** — `firebase-service-account.json` + `FIREBASE_CLIENT_CONFIG` env exist in the server repo (Firebase Admin is wired for **OAuth sign-in**), but no FCM send code was found in `app/`. In-app push = genuinely new server work.

### 3.4 Rate limiting (must respect from mobile)

Flask-Limiter + Redis; budgets per-license-key and per-IP, centralized in `nrega-server/app/rate_limit_config.py` (env-overridable). Examples: license validate 30/min/key, activity-log sync 180/hr/key, app-config 30/min/IP, heartbeat 120/min/IP. A native app **must not** poll harder than the desktop does.

### 3.5 Multi-device facts

- `licenses.activated_machines` — per-license device count; `machine_id` = MAC-derived (`src/managers/services.py::_get_machine_id`).
- `/api/set-device-name` exists → a per-license **device registry** is partially present, which the remote-run feature (option C) would build on.

---

## 4. Option analysis (native Kotlin)

### Option A — Companion app (RECOMMENDED first target)

**What the phone shows:** license status + days-to-expiry, renewal purchase (Razorpay), cloud file manager (view/download/open-in/WhatsApp share via `/files/api/whatsapp-send`), activity log + run history, in-app WhatsApp support chat (endpoint exists), notification preferences.

**Why it wins:** sabse zyada existing API reuse; directly attacks churn (35% per scaling plan — expiry reminders on phone); field GRS ko "report phone par" deta hai bina PC ke.

**Server work needed:** small.
1. **Mobile session-token endpoint** — web session cookies are awkward for native; add e.g. `POST /api/mobile/login` (email+OTP) → signed short-lived token (server already has signed-token patterns for magic links, `auth.py:778-794`). Reuse `send-otp`/OTP store.
2. **FCM push** — device-token registration (`POST /api/mobile/device-token`) + `notify_service` FCM channel for renewal/expiry/version events.
3. (optional) **App-version / Play-Store update endpoint** — mirror `version.json` pattern.

**App work needed (Kotlin):** full app — login, home, files, activity, chat, settings screens; Razorpay Android SDK checkout; offline caching of files list; WorkManager sync. Est. **6–10 weeks part-time** (1 dev), new repo `nrega-android/`.

### Option B — Field data collector (feeds desktop automation)

**What it does:** GRS phone par panchayat/village/worker data, GPS + photos (scaling plan's "NMMS attendance GPS-photo sync" idea). Upload → server → desktop operator downloads ready inputs (location pool / files API already fit).

**Server work:** new schema + upload endpoint(s) for structured records; mostly new. **App work:** forms engine + camera/GPS + offline queue (rural internet). Est. 8–12 weeks. Best after Option A ships.

### Option C — Remote-run queue (Android triggers desktop job)

**What it does:** Android me "ye panchayat ka Zero MR abhi desktop pe chala do" → server queue → desktop `heartbeat`/`app-config` poll (~2 min, existing) picks it up → automation runs → result syncs (`/api/activity-log/sync`, `/api/automation-results/sync` exist) → user sees it in app.

**Server work:** job-queue table + enqueue/dequeue/ack API + `app-config` me pending-job flag. **Desktop work:** poll job, validate inputs, refuse if a machine is off/unspecified, mark done. **Design risk:** desktop must be ON and licensed on the target machine; "kis machine par chale" needs the device registry (§3.5) + confirmation UX. Est. 6–10 weeks after A. This is the *closest thing to "phone se bot chalaya"* that is safe.

### Option D — Server-side Selenium / bot-on-phone — RULED OUT (see §2)

---

## 5. Recommended roadmap

| Phase | Scope | Est. | Gate |
|---|---|---|---|
| **0** | PWA polish (installable web companion) as interim value + live test of §3 APIs | 1–2 wk | — |
| **1** | Server: mobile token login + FCM channel + device-token API | 1–2 wk | deploy on NAS |
| **2** | **Kotlin app — Companion (Option A)** — private beta via APK/side-load | 6–10 wk | 5 field users |
| **3** | Remote-run queue (Option C) | +6–10 wk | post-A feedback |
| **4** | Field data collector (Option B) | +8–12 wk | demand check |

**Rollout note:** Play Store vs APK — current users already install Windows/macOS installers manually; an APK (GitHub release / direct link) matches the existing distribution style and avoids Play billing/policy overhead (Razorpay in-app for subscriptions). Play later for legitimacy, not day one.

---

## 6. Constraints & risks to respect

- **DPDP / PII:** Aadhaar/mobile/IFSC must stay masked (server masks; app must NOT log/store raw). License key storage on phone → Android Keystore. (See `docs/RULES.md` RULE-SEC-001.)
- **Rate limits:** mobile polls must mirror desktop cadence (heartbeat ~30 min; app-config ~2 min; no tighter).
- **Two-repo hygiene:** Android app = **third repo** (`nrega-android/`); server changes = `nrega-server` repo + its own deploy (user-only per RULE-CI-002). Never mix.
- **No NAS/remote execution by agent** (RULE-CI-002) — all server deploys stay user-run.
- **Portal policy:** never store portal credentials anywhere; automation remains desktop-only (Option C runs *on the user's machine*, not on the server).

---

## 7. Open questions for Rajat

1. **Target user of the Android app** — end GRS (expiry + files + chat) ya office/BDO (supervision: multi-operator activity view)? Shapes screens + permissions.
2. **License model on phone** — login with license key (token as-is) ya email+OTP account login (reuses web account; better UX; needs §4.A.1 token endpoint)? OTP path is recommended.
3. **Push channel** — FCM confirm karna hai? (service account file exists; env config exists; no code yet).
4. **Play Store** day one ya APK-only first?

---

## 8. Appendix — how this was verified (3 Sep 2026)

- Desktop: `config/version.json` / `src/config.py::APP_VERSION` = 3.2.7; PRD/ARCHITECTURE docs read.
- Auth decorators: `nrega-server/app/utils.py` (`admin_required`/`session_required`/`token_required`).
- Desktop API calls: grep `/api/` across `src/` → endpoint list in §3.1; bearer header confirmed (`src/tabs/file_management_tab.py:403` etc.).
- PWA seed: `ls nrega-server/app/static/` → `manifest.webmanifest`, `sw.js`; manifest linked in `templates/public/base.html`.
- FCM: grep `firebase|FCM|push` in `nrega-server/app` → no send-code (OAuth only); service account + env keys present.
- Scaling plan §2.3 lists "Mobile companion app / PWA" as missing; Phase 4 #21 "PWA first".

*Living document — update as decisions land. Source code wins over this doc on any contradiction.*
