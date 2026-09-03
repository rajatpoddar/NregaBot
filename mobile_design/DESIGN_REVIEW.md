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
5. 🆕 Mobile session token — `POST /api/mobile/send-otp` (reuse email OTP) + `verify-otp` + `refresh` → short-lived signed token; license key kabhi phone par store nahi (OTP mode)
6. 🆕 app-config: android version/checksum + storage tier list
7. 🆕 rename/move endpoints (flag-gated)
8. 🆕 Stable device-id fingerprint rule on heartbeat
9. 🆕 `app-telemetry` sink
10. ✅/⚠️ confirm Range 206 on download route
11. Admin: FCM test-send UI + blocked-version screen reuse

## 6. Next steps

1. ✅ H1/H2/H6a/H6b decided (see §4). H6c deferred.
2. **Backend wire-up in `nrega-server`** (this repo, deployed by user on NAS):
   - Batch 1 (v0.1 blockers, nothing blocks beta): FCM plumbing (`register-fcm-token` + send), notifications feed, activity paging, `client_msg_id` idempotency
   - Batch 2: mobile session token (`verify-otp`/`refresh`) per H1, app-config android fields + storage tier list, stable device-id rule, telemetry sink, Range-206 test
3. **Android skeleton** (separate `android-app/` repo): Gradle + M3 theme (design §4 tokens), CI debug APK = M0; then M1: splash → key login → validate → device slot claim.
4. H6c (WhatsApp number policy) — user checks WhatsApp Business account rules before v1.0.
