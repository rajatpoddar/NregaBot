# 📱 WhatsApp Notification Optimization Plan

> **Goal:** Prevent WhatsApp spam without losing useful notifications
> **Status:** Planning Phase
> **Date:** July 29, 2026

---

## 1. Current Behavior Summary

### Flow Diagram

```
User runs Automation (e.g., Demand, MR Gen, etc.)
        │
        ▼
on_automation_finished(key, duration, tab_instance)
        │
        ├──► show_automation_notification()  [in-app toast]
        │
        └──► _send_whatsapp_notification_if_enabled()
                │
                ├── Skip if status ≠ "success" / "failed"
                ├── Skip if whatsapp_automation_notify = OFF
                ├── Skip if no mobile number in license
                └── Send WhatsApp via server API
```

### Problem

| Issue | Example | Severity |
|-------|---------|----------|
| **No cooldown** | Ek ke baad ek 5 automations chalane par 5 messages seconds me | 🔴 High |
| **No per-automation control** | PDF Merger aur eKYC Report ke bhi notify — user ko sirf Demand/MR Gen chahiye | 🔴 High |
| **No daily limit** | Ek session me 20+ messages bhej sakta hai | 🟡 Medium |
| **No batch grouping** | Macro Manager se chain chalane par har item ka alag message | 🟡 Medium |

### Automation Count: ~28 Tabs

| Group | Automations | Notify Worthy? |
|-------|-------------|----------------|
| **Core NREGA** | Demand, WC Gen, MR Gen, MR Fill, Wagelist Gen, Wagelist Send, MB Entry | ✅ Yes |
| **Verification** | eMB Verify, ABPS Verify, Jobcard Verify, eKYC Report | ✅ Yes |
| **Utilities** | PDF Merger, Duplicate MR, Zero MR, MSR, Mate MR | ⚠️ Optional |
| **Admin** | MIS Reports, Dashboard Report, Activity Log | ⚠️ Optional |
| **Special** | SAD Update, Sarkar Aapke Dwar, Physical Complete, Delete Demand | ❌ Probably not |
| **Background** | Login Automation, Macro Manager, Scrape Data | ❌ No |

---

## 2. Implementation Plan — 3 Phases

### Phase 1: Cooldown Timer (Low Effort ≈ 15 min)

**File:** `src/app/app_automation.py`

**Logic:**
```python
# Class-level: track last notification time per automation
_last_notif_time: Dict[str, float] = {}

def _send_whatsapp_notification_if_enabled(self, key, panchayat, status, duration, details):
    # ── Existing checks ──
    if status not in ("success", "failed"):
        return
    whatsapp_enabled = get_config("whatsapp_automation_notify", False)
    if not whatsapp_enabled:
        return
    
    # ── NEW: Cooldown check ──
    COOLDOWN_SECONDS = 120  # 2 minutes between same automation type
    now = time.time()
    last_time = getattr(self, '_last_notif_times', {}).get(key, 0)
    if now - last_time < COOLDOWN_SECONDS:
        logger.info(f"⏱ Cooldown active for {key}, skipping notification")
        return
    
    # ── Store time ──
    if not hasattr(self, '_last_notif_times'):
        self._last_notif_times = {}
    self._last_notif_times[key] = now
    
    # ── Existing send logic ──
    ...
```

**Config Option:**
```python
# src/config.py or settings UI
"whatsapp_notif_cooldown_secs": 120  # User configurable: 60, 120, 300, 600
```

**File:** `src/tabs/settings_tab.py`
- Add cooldown slider/option in Default Values tab (or alongside WhatsApp toggle)

---

### Phase 2: Per-Automation Toggles (Medium Effort ≈ 45 min)

#### 2a. Config Storage

**File:** `src/config.py`

```python
# In create_default_config_if_not_exists():
DEFAULT_NOTIFY_AUTOMATIONS = {
    "demand": True,
    "wc_gen": True,
    "muster": True,        # MR Gen
    "mr_fill": True,
    "wagelist_gen": True,
    "send": True,           # Wagelist Send
    "mb_entry": True,
    "emb_verify": True,
    "abps_verify": True,
    "jc_verify": True,
    "ekyc": True,
    "msr": False,
    "mate_mr": False,
    "zero_mr": False,
    "duplicate_mr": False,
    "pdf_merger": False,
    "mis_reports": False,
    "dashboard_report": False,
    "sad_auto": False,
    "physical_complete": False,
    "delete_demand": False,
    "delete_applicant": False,
    "issued_mr_report": False,
    "nmms_attendance": False,
    "macro": False,
    # non-automation keys not needed
}
```

**Get/Set helper:**
```python
def get_notify_automations() -> dict:
    return get_config("whatsapp_notify_automations", DEFAULT_NOTIFY_AUTOMATIONS.copy())

def set_notify_automation(key: str, enabled: bool) -> None:
    config = get_notify_automations()
    config[key] = enabled
    save_config("whatsapp_notify_automations", config)
```

#### 2b. Update Send Logic

**File:** `src/app/app_automation.py` → `_send_whatsapp_notification_if_enabled()`

```python
# NEW: Check per-automation toggle (Phase 2)
if not get_notify_automations().get(key, True):
    logger.info(f"⏸ WhatsApp notify disabled for {key} in settings")
    return
```

#### 2c. Settings UI

**File:** `src/tabs/settings_tab.py` → New section in Default Values tab (or a dedicated tab)

**UI Suggestion:**
```
📱 WhatsApp Notification Settings
────────────────────────────────────────
  [✅ ON]  Enable WhatsApp notifications
  [120s]  Cooldown between messages
  
  ── Automations to Notify ──
  🟢 Demand          🟢 WC Gen
  🟢 MR Gen          🟢 MR Fill
  🟢 Wagelist Gen    🟢 Wagelist Send
  🟢 MB Entry        🟢 eMB Verify
  🟢 ABPS Verify     🟢 Jobcard Verify
  ⚪ eKYC Report     ⚪ MSR
  ⚪ Mate MR         ⚪ Zero MR
  🔴 Duplicate MR    🔴 PDF Merger
  🔴 MIS Reports     🔴 Dashboard Report
  ...

  [💾 Save Settings]
```

Color coding:
- 🟢 Green = High priority (ON by default)
- ⚪ Gray = Medium priority (OFF by default)
- 🔴 Red = Low priority (OFF by default)

---

### Phase 3: Smart Batch Grouping (Medium-High Effort ≈ 1 hr)

**Idea:** Jab multiple automations 3 minutes ke andar complete hoti hain, unhe 1 message mein merge karein.

#### 3a. Batch Queue

**File:** `src/app/app_automation.py`

```python
import threading

# Class-level batch state
_batch_accumulator: Dict[str, list] = {}  # {panchayat: [(key, status, duration, details)]}
_batch_timer: Optional[threading.Timer] = None
_BATCH_WINDOW = 180  # 3 seconds to accumulate more completions

def _accumulate_notification(self, key, panchayat, status, duration, details):
    """Instead of sending immediately, accumulate in batch."""
    p = panchayat or "_global"
    
    if p not in self._batch_accumulator:
        self._batch_accumulator[p] = []
    self._batch_accumulator[p].append({
        "key": key, "status": status, 
        "duration": duration, "details": details
    })
    
    # Reset timer — will send after BATCH_WINDOW seconds of inactivity
    if self._batch_timer and self._batch_timer.is_alive():
        self._batch_timer.cancel()
    
    self._batch_timer = threading.Timer(self._BATCH_WINDOW, self._flush_batch, args=[p])
    self._batch_timer.daemon = True
    self._batch_timer.start()

def _flush_batch(self, panchayat: str):
    """Send accumulated notifications as one message."""
    items = self._batch_accumulator.pop(panchayat, [])
    if not items:
        return
    
    if len(items) == 1:
        # Single item — send normal message
        item = items[0]
        self._actually_send_whatsapp(item["key"], panchayat, item["status"], item["duration"], item["details"])
    else:
        # Multiple items — send batch summary
        self._send_batch_whatsapp(panchayat, items)
```

#### 3b. Batch Message Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   🤖 NREGA Bot — Batch Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Matiyara — 3 tasks completed (2:15 PM — 2:18 PM)

✅ Demand                    (45s)
✅ WC Gen                    (1m 20s)
✅ MR Gen                    (2m 05s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Quick Links:
🔗 Manage Account: {url}
💬 Reply for support
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 3. Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `src/app/app_automation.py` | P1, P2, P3 | Cooldown logic, per-auto check, batch queue |
| `src/tabs/settings_tab.py` | P1, P2 | Cooldown slider + per-auto toggle UI |
| `src/config.py` | P1, P2 | Default config keys |
| `src/utils.py` | P2 | `get_notify_automations()` / `set_notify_automation()` helpers |
| `src/tab_config.py` | P2 | Automation key → display name mapping for UI |

---

## 4. Migration Strategy

| Step | What | Notes |
|------|------|-------|
| 1 | P1 — Cooldown Timer | Existing users ko kuch nahi karna, seamless upgrade |
| 2 | P2 — Per-Auto Toggle | New settings tab section added — defaults: important=ON, others=OFF |
| 3 | P3 — Batch Grouping | Configuration option — user toggle ON/OFF, default OFF initially |

---

## 5. Edge Cases

| Edge Case | Handling |
|-----------|----------|
| User manually runs same automation twice in 10s | Cooldown skip kar dega (2nd message nahi bhejega) |
| User changes settings while automation running | Next notification ke time naye settings apply honge |
| Macro manager chains 10+ automations | Batch grouping unhe 1-2 messages me merge karega |
| User switches OFF notifications mid-session | Agli notification nahi bhejega |
| Batch timer fires but accumulator has stale items | `_flush_batch()` cleanly handles empty/missing entries |
| Server down / Evolution API down | Already handled — request timeout + logger error |

---

## 6. Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| Messages per full workflow | 6-8 | 1-2 (batch) or 3-4 (cooldown) |
| Messages per macro session | 10-15 | 2-3 |
| User control over notifications | ON/OFF only | Per-automation selection + cooldown |
| Daily average messages | 20+ | 3-8 |
| User satisfaction | 😤 Spam | 😊 Relevant updates |
