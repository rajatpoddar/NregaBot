# 🖥️ nrega-server — Read-Only Audit Report (25 Aug 2026)

> **⚠️ RULES FOLLOWED:** Ye **READ-ONLY** audit hai — `nrega-server/` me **ek bhi code
> change NAHI kiya**, NAS par koi command nahi chalaya, koi push nahi kiya (AGENTS.md
> §1.5 golden rule #11). Server 200 live clients ko serve kar raha hai — isliye sab
> fixes sirf RECOMMENDATIONS hain; implementation alag planned change ke roop me hogi
> (aap ke confirm karne par).
>
> Desktop-side sibling doc: [`AUDIT_FIX_PROGRESS_25Aug2026.md`](AUDIT_FIX_PROGRESS_25Aug2026.md)

---

## ✅ JO SAHI MILA (verified-good)

| Area | Evidence |
|---|---|
| `/api/validate` hot path | Parameterized SQL, `SELECT…FOR UPDATE` row-lock, blocked/expiry checks, schema validation decorator, 30/min limit, slots_full par signed magic-link (raw key URL me nahi) — `routes/api/auth.py:209–347` |
| Device binding | Server-side enforce (`device_service.try_activate_device`) — client sirf display |
| Location data pool | DB license check, sha256(key) source tokens (raw key store/return nahi), per-key + per-IP limits, length-capped sanitization — `routes/api/location_data.py` |
| Crash reports | Fake-key reject, truncation caps, server-side PII masking (defense-in-depth), rate limits — `routes/api/crash_report.py` |
| File manager | Har route `@session_required`, har query `license_key` scoped + ownership check → IDOR-safe pattern — `routes/file/web.py` |
| API auth | `token_required` DB round-trip: expiry + `is_blocked` turant enforce — `app/utils.py:120–136` |
| Ops | Uptime/error-spike monitors, backup scheduler, release-sync — lock-guarded; Celery worker me skip (`run.py:15`); AI warmup Redis-lock |

## 🔎 FINDINGS

### SRV1 · P1 — Committed secrets: ROTATION abhi bhi pending
`.env`, `.env.dev`, `firebase-service-account.json`,
`google-sheets-service-account.json`, `hooks.json` aaj bhi **git-tracked** hain
(`git ls-files` confirmed). CODE_REVIEW_REPORT isse "private LAN = accepted risk"
bolta hai — untrack-revert ka reason valid hai. **Par rotation abhi tak nahi hui**,
aur Evolution key desktop side se already public thi.

**Action (USER karega):** DB password, SMTP, Razorpay, Firebase/Sheets keys, Evolution
key — sab rotate. Naye values sirf actual `.env` me; repo me sirf `.env.example`.

### SRV2 · P2 — Internal LAN defaults hardcoded code me
`run.py:76–78`: webhook default `http://192.168.29.101:4991`. Env-override hai,
par default hardcoded — wahi class jo desktop config se hatayi thi.
**Fix:** default empty + missing par warn-log (fail-soft skip as-is).

### SRV3 · P2 — location_data 500s client ko `str(e)` leak karte hain
`location_data.py:177,224`: `"reason": f"Sync failed: {str(e)}"` — internal detail
(PG messages/table names) client tak. `validate_key()` ise SAHI karta hai (generic
message, detail sirf log). **Fix:** generic message dono jagah; detail logger me.

### SRV4 · P2 — VERIFY: per-IP rate limits behind tunnel/proxy
`/heartbeat` 120/min, `/app-config` 30/min — per-IP keyed. Agar ProxyFix/
X-Forwarded-For configured NAHI, to tunnel ke peeche sab users ek IP se aakar
collectively throttle hote (200 × app-config/120s ≈ 100/min > 30). Production
chalta hai isliye shayad set hai — **ek baar confirm karo**, warna real-IP keying
lagao.

### SRV5 · P3 — validate() har call par write
`last_seen`/`app_version` UPDATE + storage SUM har validate par (200 users ka
heartbeat load). Kaam karta hai, par read-cache (30–60s) ya batching se DB load
kaafi girega — prior plan ka M5 item, ab bhi relevant.

### SRV6 · P3 — Raw license key hi bearer token hai
`token_required` = key-in-header, no scopes/rotation. v1 ke liye theek (DB-backed,
instant revoke), par HMAC-signed short-lived tokens ka upgrade path note kar lo.

### SRV7 · P3 — Admin panel sprawl: 36 route modules / 39 templates
Tumhara "messy / repeated data" observation sahi hai. Pattern jo mila:
* KPI counts (users/licenses/revenue) kai pages apne-apne queries se compute karte
  hain → ek shared `admin_stats_service` banna chahiye.
* Kuch helpers (`_pct`, plan-price tables) already revenue.py se reuse hote hain ✅ —
  wahi pattern baaki pages me bhi lagana hai.
* Sidebar consolidation (§4.9, 11 Aug) ho chuka ✅; ab PAGE-level duplication bachi hai.
**Proposed order (jab karein):** (1) shared stats service, (2) template partials for
tables/cards, (3) dead/duplicate cards audit per page.

### SRV8 · P3 — run.py dev-mode `app.run(host=0.0.0.0)`
Sirf `__main__` dev path hai, prod gunicorn hai — par `DEBUG=true` + 0.0.0.0 combo
par hard-fail guard daal dena chahiye (FLASK_SECRET_KEY guard jaisa).

---

## 📌 SUMMARY

Server ka core (license validation, device binding, file ownership, crash pipeline)
**solid production-grade** hai — sabse bada REAL risk sirf **SRV1 (secret rotation)**
hai jo pure USER-action hai. Baaki P2/P3 items chhote, isolated changes hain jo kabhi
bhi planned deploy me ho sakte hain. Admin-panel cleanup (SRV7) tumhare "baad me"
ke liye cataloged hai.

*Koi server file modify nahi hui. Ye doc desktop repo ke `docs/` me rakha gaya hai
taaki baaki audit documentation ke saath rahe.*

