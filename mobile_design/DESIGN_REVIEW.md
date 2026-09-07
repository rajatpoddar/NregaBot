# Design Review — NREGA Companion App (Phase 1)

> Status: **Design received & verified against backend code (3 Sep 2026)**
> Design source: `mobile_design/NREGA Companion App Design.html` (Claude bundled export)
> Readable text: `mobile_design/design_spec.md` · Raw doc: `mobile_design/design_doc.html`
> Server code verified: `nrega-server/app/routes/**` (separate repo, self-hosted NAS)

---

## 1. What was delivered

Full design contract per the brief (sections A–H), single self-contained HTML:
11 screens with **28 documented states**, cover + A–H written sections:

| Section | Present | Notes |
|---|---|---|
| A. Product spec | ✅ | v0.1 must-have / v1.0 should-have / later |
| B. IA & navigation | ✅ | 4 thumb destinations, rest 1 tap deep |
| C. Screens C1–C11 + states | ✅ | 28 states: splash, login (key+OTP+offline), home (4 license states), files, renew, storage, devices, activity, support, notifications, settings |
| D. User flows D1–D8 | ✅ | Each with the failing path |
| E. Screen → API mapping | ✅ | Verified below |
| F. Android blueprint | ✅ | Compose M3, pinned stack, modules, networking, i18n, security |
| G. Build plan | ✅ | M0–M9, ~19–20 wk solo / ~13 wk two engineers; backend items list |
| H. Open decisions H1–H6 | ✅ | See §4 |

Design system: **Material 3 / Jetpack Compose**, brand tokens from desktop theme
(primary `#3B8ED0`/`#1F6AA5`, surfaces `#F9F9FA`/`#2B2B2B`), flat mood, light+dark.
Languages: en/hi/kn/bn/hinglish all designed for.

---

## 2. API mapping verified against server code (section E)

Auth model claim (`Authorization: Bearer <license_key>`) matches the desktop code.
Legend: ✅ = exists on server today · ⚠️ = exists but needs change · 🆕 = genuinely new (design marked it NEW — confirmed)

| Design says | Server route (verified) | Verdict |
|---|---|---|
| `GET /api/app-config` | `app/routes/api/auth.py:629` | ✅ exists — but desktop-only fields; **no android version/checksum** → 🆕 add `min_android_version`, `latest`, `apk_url`, `sha256` |
| `POST /api/validate` | `auth.py` | ✅ |
| `POST /api/heartbeat` | `auth.py` | ✅ (device slots live here — device-id contract needs a stable-fingerprint rule → 🆕 rule) |
| `POST /api/send-otp` | ✅ (web email-OTP) | ✅ reuse |
| `POST /api/mobile/verify-otp` | — | 🆕 (design NEW — correct; also `/refresh`) |
| `GET /files/api/storage-breakdown` | `routes/file/api.py:78` | ✅ |
| `GET /files/api/list`, `.../list/<folder_id>` | `file/api.py:27-28` | ✅ |
| `GET /files/api/download/<file_id>` | `file/api.py:270` | ✅ — Werkzeug `send_file` handles Range → resumable likely OK; confirm 206 with a test |
| `POST /files/api/whatsapp-send` | `file/api.py:599` | ✅ |
| `POST /files/merge-for-share` | `file/api.py:425` | ✅ |
| `GET /files/view/<file_id>` (share link) | `file/web.py` `/view/<id>` | ✅ |
| `DELETE /files/api/delete/<item_id>` | `file/api.py:292` | ✅ |
| `POST /files/api/create-folder` | `file/api.py:330` | ✅ |
| `POST /files/api/upload` | `file/api.py:168` | ✅ |
| `POST /files/api/rename`, `/move` | — | 🆕 (design NEW — confirmed absent; hide behind config flag until shipped ✅) |
| Renew: `check-renewal-status`, `validate-coupon`, `create-order`, `verify-payment`, `activate-subscription`, `verify-subscription-payment`, `get-buy-link` | all in `routes/api/` | ✅ all exist (designer used the real names from the brief) |
| Storage upgrade: `create-storage-order`, `verify-storage-payment`, `update-storage` | ✅ all exist (+ `upgrade-storage`, device-upgrade variants) | ✅ — tier list still needs a home in `app-config` → 🆕 |
| Devices: `set-device-name`, `remove-device`, `request-deactivation` | ✅ all exist | ✅ |
| `GET /activity-log`, `GET /activity-log/stats` | ✅ both exist | ⚠️ add `?from&to&type&cursor` paging → 🆕 params (design NEW — correct) |
| Support: `GET|POST /whatsapp-chat/messages` | ✅ | ⚠️ add `client_msg_id` idempotency → 🆕 field |
| `GET /api/notifications` | — | 🆕 |
| `POST /api/register-fcm-token` | — | 🆕 (Firebase env config exists on server but no FCM send code) |
| `POST /api/app-telemetry` | — | 🆕 (F7; design marks NEW) |

**Bottom line:** out of ~30 claims, every single one marked ✅ exists at exactly the
path the design used; every one marked NEW in the design is genuinely absent.
The design is grounded — nothing to rewrite, only to build.

---

## 3. Review notes (small corrections / things to watch)

1. **Home → storage breakdown quota check**: `storage-breakdown` response shape should be
   re-read during wire-up (design assumes quota + per-folder breakdown fields).
2. **Download Range**: route uses Flask `send_from_directory` — Werkzeug's `send_file`
   supports `Range`/206 natively. Add one integration test before relying on it for
   resumable 4G downloads.
3. **`/api/validate` payload**: design shows `{license_key}` in body for key-login, but
   auth everywhere else is `Authorization: Bearer`. Confirm which the server accepts
   (likely header-only) during wire-up — one interceptor, not two.
4. **WhatsApp arbitrary numbers (H6c)**: the send sheet allows typing any number. Server
   `whatsapp-send` accepts it today — but this is a WhatsApp Business policy question
   (designer flagged it; decision in §4).
5. **Maintenance / blocked-version screens** (C1b/C1c) map to existing
   `maintenance_mode` + `blocked_versions` in app-config — good; only version fields
   missing for Android (see §2).
6. **Stable device id**: reinstall must not burn a device slot — needs a server-side
   fingerprint/dedupe rule on `heartbeat`. Design asks for the contract; this is a
   backend decision to make before M1.
7. **Storage tiers/prices**: don't hardcode in the app; server needs a tier list (design
   NEW — correct). `create-storage-order` expects `tier_id`.

---

## 4. Open decisions the design hands back (H1–H6)

### DECIDED (user, 3 Sep 2026)

| # | Decision | Consequence |
|---|---|---|
| H1 | **License key + email OTP, dono** | `verify-otp`/`refresh` session endpoints ARE in scope (backend item 5 → required now) |
| H2 | **Native Razorpay SDK** (hosted buy-link sirf fallback) | add Razorpay Android SDK; keep buy-link path |
| H3 | **APK-first** (matches desktop distribution) | FCM needs Play Services on device; local expiry reminders already designed |
| H4 | Keep "NREGA Bot" name; साथी ऐप subtitle; shield-check icon (designer rec accepted) | cosmetic, time-boxed |
| H5 | **API 26** floor, revisit at 200 installs (designer rec accepted) | QA bands 8/10/12/13+ |
| H6a | **Files readable after expiry** (designer rec accepted) | no design change |
| H6b | **Storage one-time, valid till license expiry** (designer rec accepted) | no design change |
| H6c | WhatsApp arbitrary-number send — **OPEN** (defer; needs WhatsApp Business policy answer) | keep typed-number path for v0.1 |

Deferred defaults taken as designer recommendations unless user objects.

Designer's original framing (for reference): license key in v0.1 + email OTP later,
native Razorpay with buy-link fallback, APK-first, "NREGA Bot" + साथी ऐप, API 26.

## 5. Backend work implied (from design G2 + this review)

Hard blockers for v1.0 → do first (nothing blocks the v0.1 beta):
1. ✅ FCM plumbing — `register-fcm-token` + server send (Firebase env already configured) — **DONE 3 Sep** (`fcm_repo`, `fcm_service`, `/api/register-fcm-token`, migration 029)
2. ✅ Notifications feed — `GET /api/notifications` — **DONE 3 Sep** (`notification_repo`, `notification_service.push()` = inbox row + push pair, migration 030)
3. ✅ Activity-log paging params — **DONE 3 Sep** (`GET /api/activity-log?cursor&from&to&type`, now Bearer-auth too — migration none needed; repo `get_feed`)
4. ✅ `client_msg_id` idempotency on chat + whatsapp-send — **DONE 3 Sep** (migration 031: partial unique on `whatsapp_chat` + `file_whatsapp_sends` marker table)

Then (needed before v1.0, H1 = key + OTP decided):
5. ✅ Mobile session token — **DONE in code (Batch 2, 4 Sep)** — `POST /api/mobile/send-otp` (reuse email OTP) + `verify-otp` + `refresh` + `logout` → short-lived signed session token (30 min, itsdangerous) + 30-day DB-backed rotating refresh token (hash-only, migration 032). License key kabhi phone par store nahi (OTP mode): verify-otp payload me raw `key` omit hai; har existing Bearer endpoint par session token chalta hai (`token_required` fallback, utils.py). Files: `app/routes/api/mobile.py`, `app/services/mobile_auth_service.py`, `app/repositories/mobile_session_repo.py`, `migrations/032_mobile_sessions.sql` + tests `tests/test_mobile_auth_service.py` (16).** Deploy NAS par user khud karega (RULE-CI-002) — code committed nahi, review ke liye ready.
6. ✅ app-config: android version/checksum + storage tier list — **DONE in code (Batch 2, 4 Sep)** — `/api/app-config` response ab `android` release gate bhejta hai (`latest_version[_code]`, `min_version_code`, `blocked_version_codes`, `apk_url`, `sha256`, `size_bytes` — design C1c) + `storage_tiers` list (design C6b: price admin pricing se, bytes single-source `STORAGE_ADDON_BYTES`; `tier_id` = `create-storage-order` ka `{plan}`). Admin `/admin/app-control` par "Android App Release" card se set/clear hota hai. Storage verify route ka local bytes-map bhi shared constant par shift (drift fix). Files: `auth.py`, `routes/admin/app_control.py` + template, `services/license_service.py`, `routes/api/storage.py` + tests `tests/test_storage_tiers.py` (14).
7. ✅ rename/move endpoints (flag-gated) — **DONE in code (Batch 2, 4 Sep)** — `POST /files/api/rename` `{item_id, new_name}` + `POST /files/api/move` `{item_id, target_folder_id}` (null = root). Folder rename/move disk + DB subtree filepaths dono rewrite karta hai (`rewrite_filepath_prefix` pure rule — component-boundary safe). Guards: sibling collision 409, folder-into-itself/descendant cycle 400, feature gate 403 (`disabled_features` me `file_rename_move`; admin `/admin/features` par "Rename / Move Files" checkbox). Files: `routes/file/api.py`, `routes/file/__init__.py`, `routes/admin/features.py` + tests `tests/test_rename_move.py` (17 — incl. disk↔DB consistency integration tests).
8. ✅ Stable device-id fingerprint rule on heartbeat — **DONE in code (Batch 2, 4 Sep)** — contract: mobile device_id = 16-hex ANDROID_ID (signing-key-scoped, reinstall par same); random/dashed/uuid4-hex ids REJECT (mobile verify-otp, reason `unstable_device_id`). Activation membership case-insensitive + canonical (format drift se double-claim impossible). Heartbeat optional `device_id`/`platform` accept karta hai — presence record (`licenses.device_presence`, migration 033, bounded map) par slot claim KABHI nahi. C7 device list ko per-device `last_seen` deta hai (`build_device_list`). Files: `services/device_service.py`, `repositories/license_repo.py`, `auth.py`, `mobile.py`, `migrations/033_device_presence.sql` + tests `tests/test_device_fingerprint.py` (16).
9. ✅ `app-telemetry` sink — **DONE in code (Batch 2, 4 Sep)** — `POST /api/app-telemetry` `{device_id, app_version, events: [...]}` (flat single-event sketch bhi accept). Design F7 ke 6 events allowlist par hain: `login_result`, `renewal_funnel`, `payment_outcome`, `transfer_failure`, `offline_queue`, `crash`. Auth required NAHI (crash login se pehle bhi hota hai) — abuse control: per-device+per-IP rate limits, batch ≤50, allowlist, row prune 90 din (migration 034). Raw events store (sink aggregation nahi karta — query-time). `stack_hash` = sha256 (raw stack kabhi nahi), `license_key` optional (invalid → NULL, fail nahi). Files: `routes/api/app_telemetry.py`, `repositories/app_telemetry_repo.py`, `migrations/034_app_telemetry.sql` + tests `tests/test_app_telemetry.py` (12).
10. ✅ Range/206 download — **CONFIRMED + tested (Batch 2, 4 Sep)** — `tests/test_download_range.py` (8): route ka exact `send_from_directory(as_attachment=True, download_name=…)` call Flask test client se — 206 + Content-Range + sahi bytes prefix/mid/open/suffix, 416 `bytes */size`, resume-after-interrupt. Werkzeug 3.1: plain-200 par `Accept-Ranges` nahi aata (206 par aata hai) — client hamesha Range header bhejta hai, ye contract test me documented.
11. Admin: FCM test-send UI + blocked-version screen reuse — dono **DONE in code (Batch 2, 4 Sep)** — Android blocked-version (C1c) App Control "Android App Release" card me (item 6); FCM test-send UI `GET/POST /admin/fcm-test` par (identifier = key|email|mobile; **Full pipeline** = `notification_service.push()` inbox+FCM, default — **Raw FCM** = sirf firebase; Firebase unconfigured / zero devices → send block; har send `FCM_TEST_SEND` audit log + `source=admin_fcm_test` data marker; sidebar Messaging → Push Test). Files: `app/routes/admin/fcm_test.py`, `templates/admin/admin_fcm_test.html` + `tests/test_fcm_test_ui.py` (18).

## 6. Next steps

1. ✅ H1/H2/H6a/H6b decided (see §4). H6c deferred.
2. ✅ Backend Batch 2 **COMPLETE** (4 Sep): mobile session token flow (5) + app-config Android gate/tier list (6) + rename/move endpoints (7) + stable device-id fingerprint rule (8) + telemetry sink (9) + Range/206 test (10) + admin FCM test-send UI (11) — sab code-ready in `nrega-server` (tests 177/177) — user deploy + DB integration-test NAS par baaki (RULE-CI-002).
3. **Android app — M0+M1+M2 DONE, M3 BUILT (4 Sep)** in `android-app/` (new nested repo, ignored by desktop repo like `nrega-server/`). **M0:** Gradle 8.11.1 + AGP 8.7.3 + Kotlin 2.1.0 + Compose BOM 2024.12.01, minSdk 26 / compileSdk 35 / targetSdk 34, M3 theme with design tokens, adaptive shield-check icon (H4), CI `build.yml`; `assembleDebug` green (9.4 MB) — **installed on user's real phone, renders fine (user-verified)**. **M1 (built, same day):** OkHttp client (F3 timeouts), kotlinx-serialization DTOs (real server contracts), EncryptedSharedPreferences (F6), 16-hex ANDROID_ID device provider (server fingerprint rule), splash → app-config gate (C1b maintenance / C1c blocked+min-version, `android` release fields) → key login `POST /api/validate {key, machine_id, app_version}` (slot claim server-side; `slots_full`/invalid/expired reasons surfaced) → Home placeholder (paid/trial chip, expiry countdown, device slots, storage line, offline cached profile) + heartbeat presence ping. Auth note resolved: /validate takes key in **body**; Bearer header for other endpoints (M2+). **Deploy-fix round (user-verified):** app screens got a root theme background + system-bar insets (dark-mode white-window fix), cold start is now instant (cache-first, background refresh, 30-min app-config TTL); server `/api/validate` accepts `platform` — Android key-login records PRESENCE only (never a device slot, per user ruling) and never triggers the desktop version-notify WhatsApp; unstable fingerprints rejected 403. **M2 (built, phone-verified):** Room cache (license/app-config/storage rows, F3 offline-first), Bearer auth interceptor (F3 one-interceptor rule), storage gauge via `/files/api/storage-breakdown` (shape verified: `{total_usage, storage_limit, date_folders}`), C3 home dashboard with the four license-state countdown card (blue/amber/red + trial), quick-action tiles (M3–M6 placeholders), 2-min heartbeat loop. **M3 (built, versionCode 3 / `0.1.0-M3`):** bottom-nav scaffold (Home·Files·Activity·Account, IA B — Activity/Account M6 placeholders; heartbeat loop moved to the shell so any tab stays online); C4 Files screen — breadcrumb (root→folder chain, no back-stack), folders-above-files (server order), size+date rows, client-side search, refresh; Room v1→v2 migration adds `file_listing` (one row per folder, root=0 — offline opens show stale listing + amber "no internet" bar) + `downloaded` (persistent C4a chip); download `GET /files/api/download/<id>` streamed to `filesDir/downloads/` with live progress + tap-to-retry (server Range/206 confirmed — resume hardening scheduled with M8); view/share via FileProvider (manifest + `res/xml/file_paths.xml`); WhatsApp send (C4c) — long-press PDF → multi-select → 10-digit number dialog → `POST /files/api/whatsapp-send {item_ids, mobile, caption, clean_pages, client_msg_id}` (fresh UUID per attempt = idempotent; server merges + sends via Evolution API — principle 4, WhatsApp never opens on the phone); single-PDF send via row overflow; WA entry points hidden when license expired (capability table). Shared `AppContainer` (data/AppContainer.kt) — one OkHttp client / store / cache across both ViewModels (F3). `assembleDebug` green (11.5 MB). **M3-fix round (phone feedback, 4 Sep):** folder tap now navigates in (was falling into the download branch → "download failed"); `download()` guards `isFolder`; DownloadedChip is a fixed-height pill (CircleShape on a wide surface stretched the check icon into a smear); launcher icon = the real brand logo `assets/logo.png` (adaptive foreground at safe-zone size, deep-green `#105010` background sampled from the art, legacy density PNGs; shield vectors removed); **critical wire bug:** kotlinx `encodeDefaults` defaults to false, so `platform = "android"` (a default value) was silently omitted from `/validate` + `/heartbeat` bodies — server saw `desktop`, ran the desktop version-notify WhatsApp nudge (the recurring "update" messages, doubled by login + re-validate) and could claim slots. `ApiJson` now sets `encodeDefaults = true`. Server-side guard (`platform` skip for android, commit 51eade0) is ready but needs NAS deploy (user-only, RULE-CI-002).**
4. H6c (WhatsApp number policy) — user checks WhatsApp Business account rules before v1.0.
5. **Android app — M3 second fix round (phone feedback, 4 Sep, interrupted session resumed):** (a) **Downloaded tick inline with filename** — the pill chip in the subtitle row ate the row's space; now a small check icon sits right after the file name. (b) **WhatsApp send — no number prompt** — sends directly to the user's OWN registered mobile (`user_mobile` from `/validate`, same number the web file manager uses); if the account has no mobile on file the app says so instead of asking. Removed the `WhatsAppNumberDialog` + dialog strings + `waDialog` state from `FilesViewModel`. (c) **Header logo** — Home header + splash now render the real brand logo (`ic_logo.png` cropped from the adaptive foreground) on the deep-green `#105010` circle, matching the launcher icon; old shield gone from header/splash (gate screens keep it — lock semantics). `assembleDebug` green.
6. **Android app — M4 (v0.1 beta prep, 4 Sep):** `values-hi/strings.xml` — full 77-key Hindi translation (design F4, microcopy sheet + desktop register: नवीनीकरण करें / दिन बाकी / क्लाउड जगह / WhatsApp पर भेजें), system-locale following, Latin digits already enforced (dates `Locale.ENGLISH`, bytes `Locale.ROOT`). Locale-parity CI gate added to `build.yml` (fails on missing/extra keys). Version `0.1.0-M4` (versionCode 4), `assembleDebug` green. Remaining: Hindi-locale phone check + 5-user pilot (user).
7. **Android app — M5 (renewal + storage upgrade, 4 Sep):** **Razorpay native SDK (H2)** — `com.razorpay:checkout:1.6.41`; auto-update build me `RazorpayCheckout` class nahi — `com.razorpay.Checkout` + host **Activity implements `PaymentResultWithDataListener`** (`RazorpayBridge` forward). **Renewal (C5a/b/c):** server-quoted `POST /api/create-order` (`registration_data` me email/plan_type/max_devices/coupon_code/**existing_key** → paise + key_id), yearly/monthly toggle, coupon (`/api/validate-coupon`), old→new expiry estimate (server rule: renewal extends from current expiry); checkout par sirf `order_id` — amount server order par hai; phir `/api/verify-payment` + `/api/validate` force-refresh polling (5 s × 12) — success/pending/failure states + "refresh license status" escape hatch. **Storage upgrade (C6b):** tiers app-config `storage_tiers` cache se (server-priced, app sirf tier_id), sheet gauge/90%/100% banner se; `create-storage-order` → Razorpay → `verify-storage-payment` → gauge refresh. Home Renew button ab LIVE (in-card expiring/expired, outlined valid). **Server change:** `create-storage-order` response me `key_id` add (SDK ke liye) — `storage.py` ek line, NAS deploy ke saath jayega. Version `0.1.0-M5` (versionCode 5), `assembleDebug` green. Remaining: deploy (user) + phone test — ₹1 test order, coupon, pending/failure states.
