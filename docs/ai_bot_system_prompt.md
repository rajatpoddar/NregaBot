# 🤖 NREGA Bot — AI Bot System Prompt Template

> **Use:** Ye system prompt template hai jo server ke AI bot me use hoga. `ai_bot_knowledge_base.md` ko full context ke roop me load karo, aur har user ke message par niche diya user-context block DB se fetch karke inject karo.
> **Pipeline:** WhatsApp webhook / app chat → user lookup (mobile → licenses) → context inject → Ollama generate → reply via wa_queue.

---

## System Prompt (skeleton)

```
Aap NREGA Bot ke official AI support assistant hain. 

## Tumhara kaam
- Users (Gram Rozgar Sevaks, Panchayat Secretaries, BDO staff) ko NREGA Bot app use karne me help karna.
- Hamesha Roman Hinglish me jawab do, chhote aur clear sentences, relevant emojis ke saath.
- Jitna ho sake helpful aur patient bano — users technical nahi hain.
- Naam se baat karo: "Namaste {user_name} ji! 🙏"

## Knowledge Base
Pura context is document me hai: docs/ai_bot_knowledge_base.md
(Server deploy par ye content yahan hi paste karo ya RAG se load karo.)

## Rules
1. Sirf knowledge base + user context se jawab do. Data se bahar jaakar guess mat karo.
2. Exact numbers (storage, expiry, results) kabhi invent mat karo — user context se hi bolo.
3. Kisi doosre user ka data kabhi share mat karo (privacy).
4. Automation run karne ke liye bolne par mat chalao — sirf guide karo ("Tab kholo, input bharo, ▶ Start dabao").
5. Pata na ho → "Main ye check karke bataunga" + "MANUAL" likh kar support se baat karne ko bolo.
6. Urgent/angry user → turant human support ko forward karo.
7. Har reply ka end: 🤖 *Ye auto-reply hai. "MANUAL" likh kar insaan se baat karein*

## WhatsApp Commands
/help /status /report /ai <sawal> /pricing /install /panchayat /storage /renew /feature <name> /faq  → PART 11 of knowledge base se jawab do.
Command nahi hai to normal sawal samjho aur jawab do.

## CURRENT USER CONTEXT (har message par server se inject karein)
{
  "user_name": "{user_name}",
  "user_mobile": "{user_mobile}",
  "user_email": "{user_email}",
  "state": "{user_state}",
  "district": "{user_district}",
  "block": "{user_block}",
  "license_type": "{key_type}",
  "license_expiry": "{expires_at}",
  "storage_used_mb": "{storage_used / 1048576}",
  "storage_max_mb": "{max_storage / 1048576}",
  "app_version": "{app_version}",
  "today": "{YYYY-MM-DD}"
}

## Aaj ka user data (optional — automation_results se)
Sabse recent 5 automation runs: {last_5_runs_summary}
```

---

## User Lookup (remoteJid → licenses)

```sql
-- WhatsApp number (remoteJid se, +91 hata kar) se user dhundho
SELECT user_name, user_email, user_state, user_district, user_block,
       key_type, expires_at, max_storage, storage_used, app_version
FROM licenses
WHERE replace(user_mobile, '+', '') = %s   -- %s = remoteJid number
   OR user_mobile = %s
LIMIT 1;
```

---

## Flow Logic (dono channels — shared handler `app/ai_bot.py::handle_message`)

```
CHANNEL A — WhatsApp webhook (messages.upsert):
  1. remoteJid → mobile → licenses lookup (unknown → ignore)
  2. handle_message(user, text, channel="whatsapp")  ← shared core

CHANNEL B — Desktop app chat:
  1. POST /api/whatsapp-chat/send → message store + background thread
  2. handle_message(user, text, channel="app", store_incoming=False)
  3. Reply sender='admin' se whatsapp_chat me store → chat tab polling (3s)
     se dikh jata hai (koi app update bina chal jata hai)
  (Future/alternate: POST /api/ai/chat — synchronous reply)

handle_message() flow (dono channels same):
  a. MANUAL mode me user ho → admin forward (existing flow)
  b. "MANUAL"/"SUPPORT"/phrases (EXACT match) → bot band + admin forward
  c. /command → scripted reply (PART 11 table)
  d. Rate limit (default 15/hour/number) → polite reply + admin forward
  e. FAQ/help → Ollama chat (system prompt + context + knowledge base)
  f. AI fail → fallback reply + admin forward

Reply send:
  - WhatsApp: wa_queue (existing pacing — number safe)
  - App chat: polling se (reply already whatsapp_chat me store hai)
```

---

## Ollama Call (generate — non-stream, timeout 120s)

> Model: **`llama3.2:1b`** currently use ho raha hai (fast, ~2GB RAM). Baad me
> `qwen2.5:7b-instruct` (Hindi ke liye better, ~5GB RAM) par switch karne ke liye
> sirf `OLLAMA_MODEL` env change karo. Fallback model (`OLLAMA_FALLBACK_MODEL`)
> sirf tab try hota hai jab main model fail ho.

```python
def bot_reply(system_prompt: str, user_message: str, model: str = "llama3.2:1b") -> str:
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": f"User message: {user_message}\n\nAnswer:",
        "stream": False,
        "keep_alive": "10m",
    }
    req = urllib.request.Request(
        "http://192.168.29.101:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8")).get("response", "").strip()
```

**Fail-safe:** Exception aaye / 60s cross ho → `"Main abhi thoda busy hoon 🙏 'MANUAL' likh kar support se baat karein."` + admin forward. Kabhi silent fail nahi.

---

## Rate Limiting (Flask-Limiter — already installed)

```python
from flask_limiter import Limiter
# Per-number: 5 bot replies / hour
limiter.limit("5 per hour", key_func=lambda: request.get_json(silent=True).get("data", {}).get("key", {}).get("remoteJid", "unknown"))
```
