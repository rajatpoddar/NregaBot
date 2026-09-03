# Mobile App Design Prompt (for Claude)

> **How to use:** Neendh se copy karo — `docs/MOBILE_APP_DESIGN_PROMPT.md` ke niche wala code block. Poora block (CODE-BLOCK-START se CODE-BLOCK-END tak) Claude ko paste karo, kuch delete mat karna. Design wapas aane ke baad wire-up/implementation yahan codebase me hoga.
>
> **Context source:** [`docs/ANDROID_FEASIBILITY.md`](ANDROID_FEASIBILITY.md) — sab backend endpoints niche verified server code se hain (status: v3.2.7, 30 Aug 2026).
>
> **Decisions already locked:** Native Android (Kotlin) · **Design system: Material 3 (Jetpack Compose)** · Companion app only — bot/automation phone pe NAHI chalegi.

---

```markdown
CODE-BLOCK-START

# ROLE
You are a senior Android product designer + mobile architect working for NREGA Bot, a
government-workflow automation startup in India. You will produce the COMPLETE design
package for our first native Android companion app. You are NOT building code today —
you are producing the product spec, UI/UX design, and technical blueprint that our
engineering team (who knows the backend intimately but has NOT built mobile yet) will
implement 1:1.

Read the full context below, then produce the deliverables in the exact structure
requested at the end. Be concrete and specific — never hand-wavy. Where you face a real
decision, DO NOT silently pick — list it in "Open decisions" with your recommendation
and the trade-offs.

---

# 1. WHAT THE PRODUCT IS (today)

NREGA Bot is a desktop Windows/macOS automation tool (Python, CustomTkinter + Selenium)
used by ~200+ Gram Rozgar Sevaks (GRS), Panchayat Secretaries, and BDO offices in India.
It drives the government MGNREGA / VB-G-RAM-G portal through the operator's OWN browser
and OWN portal login to eliminate repetitive data entry: 48 task tabs (muster rolls,
payment files, job cards, zero-MR, etc.), report generation, PDF merge, and WhatsApp
delivery of outputs.

Key architectural facts that MUST shape the app design:
- The automation runs ONLY on the operator's desktop. It is NOT a SaaS/scraper, and the
  bot will NEVER run on a phone or on our server. This is a hard product rule.
- The desktop app phones home to our Flask+Postgres server (self-hosted NAS):
  - `POST /api/heartbeat` every ~2 min with license key + device info
  - `GET /api/app-config` — remote announcements, maintenance mode, blocked versions
  - `POST /api/validate` — license validation at startup
- A desktop "account" = one LICENSE KEY owned by one user (name, email, mobile,
  district/state, subscription plan, expiry date, device slots, storage quota + usage).
- Cloud file storage is a core paid feature: generated PDFs/reports sync to the server,
  organized in folders, with storage quotas per plan (paid upgrades exist).
- Payments run on Razorpay with server-side signature verification only. Subscription
  (monthly/yearly) + one-time renewals + storage upgrades all exist.
- Users are non-technical, Hindi-first, often on low-end Android phones with weak/4G
  connectivity, and many are first-time smartphone users. Trust and simplicity are
  paramount. Some users share one desktop with a colleague.
- Existing brand/language: English UI, but end-users speak Hindi, Kannada, Bengali, and
  Hinglish. The desktop product supports 5 locales: en, hi, kn, bn, hinglish.
- Distribution today = direct installer/zip with SHA-256 checksums + license key
  activation (NOT app-store based). Assume the Android app will ALSO be distributed as a
  direct APK first (side-load), possibly Google Play later — design must not depend on
  Play-only APIs (no Play Billing! payments go through the existing Razorpay flow).

# 2. WHAT WE ARE DESIGNING (scope)

A **companion app**, not a port of the bot. Whatever the user can do inside "their
account" today — license status, subscription renewal, cloud files (view/download/
share), storage, activity history, support — must be available on the phone. The phone
app is how a GRS "stays connected" between desktop sessions and while in the field.

IN SCOPE (Phase 1 — this design):
1. **Onboarding + Login** — email+OTP (existing server flow) OR license-key entry;
   see Open decisions. Secure session storage. Logout/switch user.
2. **Home / License dashboard** — plan name, expiry countdown, days remaining
   (expiring/expired states), storage gauge, quick actions.
3. **Cloud Files** — browse folder tree, search, view PDFs/reports, download,
   share to WhatsApp (server does the WhatsApp send), public share-link creation,
   delete, create folder, upload from phone (photos/PDFs), storage-quota banner.
4. **Buy / Renew / Upgrade** — renewal when expiring, storage upgrade when full;
   MUST use the existing server-side Razorpay flow (server creates order/subscription,
   client verifies server-side; see §5.4). No Play Billing.
5. **Devices** — list devices registered on the license, rename, remove
   (device-slot limits exist server-side).
6. **Activity** — recent desktop automation activity + per-day stats (server keeps it).
7. **Support** — WhatsApp-style in-app chat (server relay), help/FAQ, "contact us".
8. **Notifications** — expiry reminders, announcements, activity/result alerts.
   IMPORTANT: no push infra exists today (desktop polls). Phase 1 = FCM push (to build)
   + in-app notification inbox as fallback.
9. **Settings** — language (5 locales), theme (light/dark), notification prefs,
   app version + update check, about.

OUT OF SCOPE (do NOT design screens/flows for these):
- Any bot/automation execution, Selenium-like features, or "run this tab" actions.
- Server/admin features, reseller features, analytics dashboards.
- Porting the desktop UI. A field-data-collection module and a remote-run job queue are
  future phases — architecture should leave room (clean feature modules) but do not
  design them now.

# 3. USERS & DESIGN CONSTRAINTS (non-negotiable)

- Primary persona: **Renu, 32, GRS** — works from a village Panchayat office and from
  the field. Hindi-first. Uses a ~₹6-9k Android phone (2-3 GB RAM, Android 8-11,
  small screen ~5"). Sometimes poor connectivity (2G/4G edge, signal drops).
- Secondary persona: **Panchayat Secretary / BDO office staff** — slightly more
  literate, English ok, wants reports fast and shareable.
- Constraints that MUST shape every screen:
  1. Large touch targets (min ~48dp), simple Hindi-first copy, numbers/dates shown
     prominently (expiry dates, file sizes).
  2. Skeleton loading states, graceful offline states (cached last-known data),
     retry affordances everywhere. Downloads must survive screen-off.
  3. Low bandwidth: lazy image/PDF handling, no heavy assets, small APK.
  4. Works on Android 8.0+ (API 26+), supports dark mode, light theme default.
  5. All UI copy in 5 locales (en, hi, kn, bn, hinglish) via proper i18n — NOT
     hardcoded strings. No RTL needed (all LTR scripts).
  6. Security: license key/session token never stored in plaintext; use Android
     Keystore-backed storage. Never log PII (Aadhaar/mobile/IFSC must be masked).

# 4. DESIGN SYSTEM (DECIDED) — Material 3 on Jetpack Compose

**The design system is Material 3 (Google's standard), implemented with Jetpack
Compose's `material3` library. Do NOT invent a parallel/custom design system, and do
NOT reopen Compose-vs-XML.** M3 gives us tested components, accessibility, dark-mode
and theming for free. We take M3's structure and re-theme it with NREGA Bot brand
tokens (below) so the app stays in the desktop product family. Mobile-specific
refinements (bottom navigation, thumb zones, one-hand reach) are welcome within M3.

## 4.1 Brand tokens → M3 role mapping

- **Primary** → brand blue: light `#3B8ED0` / dark `#1F6AA5` (M3 `primary`); hover
  `#36719F` / `#144870` → `onPrimary` white `#FFFFFF`.
- **Surfaces** → light `#F9F9FA` / dark `#2B2B2B` (M3 `surface`/`surfaceContainer`);
  window/background light `#FFFFFF` / dark `#212325`.
- **Status colors** map to M3 semantic roles: success / warning / error / info
  (license valid, expiring, expired, maintenance) → `primary` variants, `tertiary`,
  `error`, `info`-style tones.
- **Shape:** override M3 defaults toward the desktop's flat look — modest radius
  (~6-8dp: buttons ~6dp, cards ~8dp, sheets ~12dp top corners); minimize elevation
  shadows; prefer tonal/outline differentiation (flat aesthetic, `border_width=0`
  heritage).
- **Dynamic color (Material You):** optional user toggle on Android 12+ ONLY; default
  is the fixed brand palette so the app always looks on-brand.
- **Typography:** default system sans (Roboto/Noto Sans — full Devanagari, Kannada,
  Bengali coverage built in); use tabular figures for dates/countdowns/sizes;
  generous scale for primary numbers (expiry countdown).
- **Light/dark:** BOTH required, following the token pairs above.
- **Brand voice:** plain, trustworthy, government-friendly Hindi. Avoid jargon; avoid
  English abbreviations like "renewal" without explanation (or keep both: "Renewal —
  नवीनीकरण").

# 5. BACKEND REALITY (verified) — DESIGN AGAINST THESE EXACT ENDPOINTS

All endpoints below are verified in server code today. Auth header for machine/API
calls: `Authorization: Bearer <license_key>` (server splits on space and looks up the
last token as the license key; rejects if expired or blocked). Web login instead uses
email+OTP then a browser cookie session.

## 5.1 License / account
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/validate` | validate a license key (also returns plan/expiry/user) |
| POST | `/api/heartbeat` | desktop presence + device info (mobile may ping too) |
| GET | `/api/app-config` | announcements, maintenance, blocked versions |
| POST | `/api/set-device-name` | name the current device |
| POST | `/api/remove-device` | free a device slot |
| POST | `/api/check-duplicate` | duplicate-key checks |
| POST | `/api/request-deactivation` | user-initiated deactivation |

## 5.2 Email OTP + session auth (web today)
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/send-otp` | send email OTP (web login flow uses this) |
| — | `/account/*`, `/auth/*` | web session (cookies) — NOT directly usable by native apps |

> NOTE: There is NO mobile session-token endpoint yet. The app design should specify a
> clean "email+OTP → short-lived signed session token" contract as new backend work,
> and treat license-key auth (`Bearer`) as the fallback/primary alternative. Pick the
> login model in Open decisions.

## 5.3 Cloud files & storage (blueprint prefix `/files`; auth `Bearer <license_key>`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/files/api/list` | folder tree (folders + files, metadata) |
| GET | `/files/api/list/<folder_id>` | contents of one folder |
| GET | `/files/api/storage-breakdown` | storage used by category + quota |
| POST | `/files/api/upload` | upload file |
| GET | `/files/api/download/<file_id>` | download file |
| DELETE | `/files/api/delete/<item_id>` | delete file/folder |
| POST | `/files/api/create-folder` | create folder |
| POST | `/files/api/whatsapp-send` | server sends selected PDFs/files to a WhatsApp number |
| POST | `/files/merge-for-share` | merge selected PDFs into one |
| GET | `/files/download-merged-pdf/<folder_id>` | download merged PDF |
| GET | `/files/view/<file_id>` | web view/share page for a file (public share link) |
| POST | `/api/create-storage-order` | Razorpay order for storage upgrade |
| POST | `/api/verify-storage-payment` | verify storage payment server-side |
| POST | `/api/update-storage` / `/api/upgrade-storage` | quota change after payment |

## 5.4 Payments (Razorpay — server-side signature verification ONLY)
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/create-order` | create Razorpay order (one-time renewal) |
| POST | `/api/verify-payment` | verify payment signature server-side |
| POST | `/api/activate-subscription` | start Razorpay subscription |
| POST | `/api/verify-subscription-payment` | verify subscription payment |
| POST | `/razorpay-webhook` | server-side subscription lifecycle |
| POST | `/api/check-renewal-status` | whether renewal pricing applies |
| POST | `/api/validate-coupon` | coupon check |
| POST | `/api/get-buy-link` | signed one-time buy link (license key NEVER in a URL) |

SECURITY RULE for the design: the client NEVER decides price/plan and NEVER verifies
payments. Client asks server → server creates order → payment happens (native in-app
checkout via Razorpay SDK or a server-hosted web checkout page — see Open decisions) →
server verifies → client refreshes license state from `/api/validate`.

## 5.5 Activity & usage
| Method | Path | Purpose |
|---|---|---|
| POST | `/activity-log/sync` | desktop pushes activity entries |
| GET | `/activity-log` (+ `/activity-log/stats`) | user's recent activity + stats |
| POST | `/usage-stats/sync` | desktop usage counters |

## 5.6 Support chat (server relays WhatsApp-style chat)
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/whatsapp-chat/messages` | chat history / send message |
| — | `/whatsapp-chat/webhook` | inbound messages from our WhatsApp Business side |

# 6. DELIVERABLES — produce ALL of these, in this order

## A. Product spec (short)
- Persona-confirmed goal for the app in 3 sentences.
- Feature priority list (must-have / should-have / later) mapped to the IN-SCOPE list.
- The ONE metric this app should move (e.g., on-time renewals, support deflection).

## B. Information architecture + navigation
- Full IA tree. Primary navigation pattern (bottom nav vs drawer) with justification
  for THIS user (Hindi-first, low-end, one hand). Max 4-5 primary destinations.
- Every screen listed with: name, purpose, key content, primary action(s), and how the
  user reaches it.

## C. Screen designs (the bulk — go deep here)
For EVERY screen produce: a text wireframe (ASCII or structured layout description),
content hierarchy, exact states to design (loading skeleton / empty / error / offline /
no-permission / license-expired banner / storage-full), and microcopy in English + Hindi
(both — we will localize the rest). At minimum cover:
1. Splash + license/expiry pre-check
2. Login (per chosen model in §5.2) + OTP entry + retry + error states
3. Home dashboard (status card, expiry countdown, storage gauge, quick actions)
4. Files list + folder navigation + file actions sheet (view/download/WhatsApp-share/
   copy link/delete/rename if supported) + upload flow (permission states) +
   download progress + offline handling
5. Buy/Renew page (plan summary, coupon field, Razorpay checkout transition,
   success/failure/pending verification states, "already renewed?" refresh)
6. Storage-upgrade upsell flow (where it triggers: at 90%/100% quota)
7. Devices list (add via desktop?, rename, remove, slots remaining)
8. Activity feed (grouped by day, filter, empty state)
9. Support chat (thread UI, offline queue of outbox messages, attach-optional)
10. Notifications inbox + FCM permission first-run rationale
11. Settings (language switcher behavior = immediate re-render, theme, about/version)

## D. User flows (happy + failure paths) — step-by-step, including states
1. First launch → login → home
2. License expiring in 7 days → notification → renew → Razorpay → success → updated card
3. License expired → app behavior (what stays usable? files view? support? nothing?)
4. Storage 98% full → upload attempt → upsell → upgrade → retry upload
5. Share 3 PDFs to WhatsApp from the field
6. New phone / reinstall / second device slot exhausted
7. Support chat offline → queued → delivered on reconnect
8. Maintenance mode / blocked version (server `/api/app-config`)

## E. Screen → API mapping table
Every screen/action → exact endpoint(s) from §5 + payload sketch + refresh/revalidation
strategy (when to refetch, caching TTL, pull-to-refresh, optimistic UI where safe).

## F. Android technical blueprint
- Recommended stack with versions you'd pin. **Decided: Kotlin 2.x + Jetpack Compose
  (material3) + MVVM** — pick Hilt vs manual DI (recommend for this team), Retrofit/OkHttp
  + Kotlinx Serialization or Moshi, Room or DataStore for cache, WorkManager for
  background sync/downloads, FCM, EncryptedSharedPreferences/Keystore, Biometric option.
  No XML layouts unless you have a compelling reason — do not reopen this.
- Project/module structure (single module vs feature modules — recommend for Phase 1).
- Networking layer: auth header strategy, token refresh, 401 handling, retry/backoff,
  offline queue for chat + activity.
- Localization architecture for 5 locales incl. a strings workflow.
- Notification architecture: FCM + inbox fallback, when to request permission,
  expiry-reminder scheduling (local + push).
- Security checklist and a "what we will NOT do" list (no key in SharedPreferences,
  no Play Billing, no client-side price trust).
- Analytics/observability recommendation that fits a self-hosted Flask backend
  (minimal; we control everything).

## G. Build plan
- Ordered milestones with rough effort (the team is 1-2 engineers who know Python/
  backend but are new to Android — be honest about learning curve). What is the
  smallest useful v0.1 (beta to 5 friendly users)? What comes in v1.0?
- Backend work items this design implies (new session-token endpoint, FCM plumbing,
  any new payload fields) — list them explicitly so backend can start in parallel.

## H. Open decisions (each with a recommendation + trade-offs)
1. Login model: email+OTP (matches web, field users know email? many DON'T) vs
   license-key entry (they have the key from desktop) vs both.
2. Payment UX: Razorpay native SDK vs server-hosted web checkout in WebView/CCT.
3. Play Store vs APK-first distribution (affects FCM provider choice & update UX).
4. App naming/branding for the phone ("NREGA Bot" vs friendlier Hindi-friendly name)
   and app icon direction.
5. Min Android version (we said 8.0 — confirm vs 10 to cut device matrix).
6. Anything else you genuinely can't decide alone.

# 7. QUALITY BAR
- Every claim about the backend must come from §5 (nothing invented). If you need an
  endpoint that does not exist, say so and mark it "NEW".
- Write in English; microcopy in English + Hindi. Concrete over clever.
- Produce a document of substantial depth — this IS the implementation contract.

CODE-BLOCK-END
```

---

## Next steps (after Claude returns the design)

1. **Design review** — design aapke saath pass/fail karo (login model, payment flow, screen list).
2. **Backend first (parallel)** — main server me `nrega-server` repo me naye endpoints banata hoon: mobile session-token login (`/api/mobile/*`), FCM push plumbing, koi bhi missing payload field.
3. **Android skeleton** — Kotlin project structure + design tokens + networking layer design ke against.
4. **Screens wire-up** — ek-ek karke Claude ke spec ke against implement.

> ⚠️ **Repo rule yaad rahe:** `nrega-server/` alag repo hai (NAS remote). Server-side changes wahan user khud deploy karta hai — main sirf code + copy-paste commands deta hoon (docs/RULES.md RULE-CI-002).
