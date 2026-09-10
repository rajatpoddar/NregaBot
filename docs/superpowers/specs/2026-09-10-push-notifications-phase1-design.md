# Push Notifications — Phase 1: automation-complete push

**Date:** 2026-09-10
**Status:** approved design, ready for implementation plan
**Repos touched:** `NregaBot` (desktop), `nrega-server`, `android-app`

## Why

Per-automation WhatsApp notifications were shipped once and then removed: users
found them irritating and could not tell which message was whose. The value of
"your automation finished" is real — it is what lets someone walk away from the
machine — so it moves to the phone, where a notification is cheap to glance at
and easy to switch off.

Phase 1 also does something no phase before it has done: **it puts the first
real push on a real device.** M7 built the entire pipeline and left it in stub
mode. Everything below is small; the value is in closing the last gap.

## What already exists

Server:

| Piece | Where | State |
|---|---|---|
| FCM send + invalid-token cleanup | `app/services/fcm_service.py` | Works. `firebase-service-account.json` present (project `nrega-bot-live-chat`). |
| Inbox row + push, one choke point | `app/services/notification_service.py::push()` | Works. Categories: `license · desktop · support · announcement`. |
| Token register/unregister | `app/routes/api/fcm.py` | Works. |
| Inbox read/mark-read | `app/routes/api/notifications.py` | Works. |
| Admin single-license test send | `app/routes/admin/fcm_test.py` | Works. |

Android: `FcmManager`, `NregaMessagingService`, `NregaNotificationChannels`
(6 channels incl. `nregabot_desktop`), notification inbox screen, Room v4
`notification` table — all built, all in stub mode.

Desktop: `on_automation_finished()` at `src/app/app_automation.py:414` is the
single point every automation passes through on completion. It already holds
`key`, `panchayat`, `village`, `status`, `duration`, `details`, and already
fires three background cloud syncs from that block.

**The gap:** `notification_service.push()` is called from nowhere in
production — only from the admin test page. The plumbing is complete and dry.

## Two defects found while designing

1. **`category` never reaches the device.** `notification_service.push()` puts
   `notification_id` and `deeplink` into the FCM `data` block but not
   `category`. `NregaMessagingService.kt:65` reads `data["category"]` and falls
   back to `"announcement"`, so *every* push lands in the announcement channel.
   A user who mutes announcements would silently mute automation alerts too.
2. **`deeplink` is written but never read.** `NregaMessagingService.kt:90` puts
   it in the launch Intent; nothing in `MainActivity` consumes it. Tapping a
   notification opens the app on its default screen.

Both are Phase 1 work — the feature is not honestly done without them.

## Decisions

| Question | Decision |
|---|---|
| Which finishes push | `success` and `failed`. Not `stopped` — the user stopped it themselves. |
| WhatsApp | Untouched. Per-automation WhatsApp is already gone; the 6 AM daily report stays exactly as it is. |
| User control | A toggle in the app's Account screen, stored server-side so it survives a reinstall or a new phone. |
| Transport | FCM. It is the only path that survives Doze and OEM battery managers, it is free, and the plumbing is already built. |
| Who writes the text | The desktop app. It already knows the user's language (`src/i18n.py`, 5 locales); the server would have to guess. |

## Design

### Flow

```
Desktop: on_automation_finished(status in {success, failed})
    │  background thread, fire-and-forget
    ▼
POST /api/push/automation-complete
    { license_key, automation_key, status, panchayat, duration_seconds,
      details, title, body }
    │
    ├─ license exists?            no → 401
    ├─ push_automation_notify ON? no → 200 {"status": "skipped"}
    ├─ any FCM token for license? no → 200 {"status": "no_devices"}
    ▼
notification_service.push(category='desktop', title, body,
                          deeplink='activity', data={automation_key, status})
    │
    ├─ inbox row (source of truth)
    └─ FCM → every registered device for that license
              data: {notification_id, deeplink, category, automation_key, status}
    ▼
Android: NregaMessagingService → channel nregabot_desktop → system notification
    tap → MainActivity reads deeplink extra → Activity screen
```

### Server

**New endpoint** `POST /api/push/automation-complete` in a new
`app/routes/api/push.py`.

Auth follows the established desktop-background-thread pattern
(`activity_log.py`, `automation_notify.py`, `crash_report.py`): `license_key`
in the body, no session or bearer token, with a license-existence check so
forged keys get 401. Rate limited through `rate_limit_config.ENDPOINTS` with a
new `push_automation` entry — `200 per hour` per key, `600 per hour` per IP,
matching `automation_results`.

Validation, all server-side because the client is not trusted: `status` must be
`success` or `failed` (anything else, including `stopped`, is a 400 — the
desktop should never send it, and if an old build does we reject rather than
push); `title` truncated to 200; `body` to 500; `automation_key` to 100;
`panchayat` to 255.

**Toggle storage.** Migration `035_push_automation_notify.sql`:

```sql
ALTER TABLE licenses
  ADD COLUMN IF NOT EXISTS push_automation_notify BOOLEAN NOT NULL DEFAULT TRUE;
```

Default TRUE: a user who installs the app opted into notifications by
installing it, and the switch is one tap away.

**Toggle read** rides on `/api/validate`, which already returns
`whatsapp_daily_report` the same way (`app/routes/api/auth.py:917`) — the app
reads its profile from there, so no extra round trip.

**Toggle write:** `POST /api/push-settings`, Bearer auth (`token_required`),
body `{"push_automation_notify": bool}`.

**Bug fix** in `notification_service.push()`: add `category` to `push_data`
alongside `notification_id` and `deeplink`. One line; it fixes channel routing
for every existing and future push, not just this one.

### Desktop

In `on_automation_finished()`, inside the existing `# ── Cloud Sync ──` block,
a fourth call: `self._push_automation_complete(key, panchayat, status, duration, details)`.

It follows the shape of `_sync_automation_results_to_cloud()` directly above it
— guard clauses first, `requests.post` on a daemon thread, every exception
swallowed to `logger.debug`. A notification failing must never disturb an
automation that succeeded.

Text is composed here, through `tr()`, so it arrives in the user's language:

- title — `✅ MR Payment poori hui` / `⚠️ MR Payment adhoori rahi`
- body — panchayat, the `details` line the tab already builds
  (`Total: 15 | Success: 12 | Failed: 3`), and duration

New locale keys in all five locale files (`en`, `hi`, `hinglish`, `bn`, `kn`).

### Android

1. **Toggle** — a switch row in `SettingsRows` in `AccountScreen.kt`, next to
   the existing notifications and support rows. Reads from the profile
   (`LicenseDto`), writes through a new `AccountViewModel` call. Optimistic
   flip with a revert and a snackbar if the call fails, matching how device
   rename already behaves.
2. **Deeplink handling** — `MainActivity` reads the `deeplink` extra on
   `onCreate` and `onNewIntent` and routes it: `activity` → Activity screen,
   `renewal` → Renewal (already emitted by `ExpiryReminderWorker.kt:93`),
   `notifications` → inbox. Unknown value → default screen, never a crash.
3. **Strings** — new keys in `values/` and `values-hi/`. CI's locale parity
   gate fails the build if they drift, which is the intended safety net.

## Error handling

| Case | Behaviour |
|---|---|
| Server unreachable from desktop | Swallowed, `logger.debug`. Automation is unaffected. No retry queue — a stale "finished" notification an hour later is worse than none. |
| Toggle OFF | 200 `{"status": "skipped"}`. No inbox row either — the user asked not to be told. |
| No device registered | 200 `{"status": "no_devices"}`, no inbox row. Nobody is going to read it. |
| Firebase unconfigured | `push()` already returns `ok` with `sent: 0`; the inbox row still exists so the app shows it on next open. |
| Token stale / app uninstalled | `send_to_license()` already removes it on `UnregisteredError`. |
| Unknown deeplink | Default screen. |

## Testing

**Server** (`pytest`, following `tests/test_notification_service.py`):
validation rejects bad `status`, truncation caps hold, toggle OFF skips before
any DB write, no-token path skips, `category` is present in the built payload.

**Desktop:** the payload builder is a pure function taking status/details and
returning the dict — tested directly. `stopped` produces no call at all.

**Android:** locale parity gate in CI; deeplink routing over the three known
values plus an unknown one.

**The acceptance test is a phone.** Run an automation on the desktop, watch the
notification arrive, tap it, land on Activity. Then switch the toggle off and
confirm the next run is silent. Nothing below that counts as done — this path
has never once been exercised end to end.

## Prerequisite (blocks everything)

`google-services.json` for `com.nregabot.companion` from Firebase project
**`nrega-bot-live-chat`** — the same project the server's
`firebase-service-account.json` belongs to. Until it is in `android-app/app/`,
the app stays in stub mode and no push can arrive. It is gitignored, like the
keystore.

## Out of scope

Phase 2 (admin push broadcast: specific user / all app users, promotional
sends, fan-out with progress log) and Phase 3 (`push` as a third channel in
`notify_service.EVENT_DEFAULT_CHANNELS`, giving expiry/renewal/welcome/storage
events push delivery for free). Also deliberately excluded from Phase 1: quiet
hours, per-automation notification preferences, and push for `stopped` runs.
