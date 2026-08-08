# 🤖 AI Command Center — Admin Control Panel (AI Business Model)

NREGA Bot ka naya business model: **AI sab kuch handle karta hai — aap sirf
control karo.** Ye document admin panel ke naye AI features ka scope + usage
guide hai.

---

## 🎯 Vision

Pehle: admin ko har message khud likhna padta tha (boring templates), har
reply khud dekhna padta tha, aur koi overview nahi tha ki kya chal raha hai.

Ab: **Ollama (aapka NAS) sab messages likhta hai** — broadcast, automation
events, support replies. Aap decide karte ho:
- AI bot **ON/OFF**
- Kaun sa **model**
- **Rate limit**
- Auto-pilot **ON/OFF** (kab kya jayega)

Sab ek jagah — **AI Command Center** page (`/admin/ai-command-center`).

---

## 🧩 Components

| File | Kya karta hai |
|---|---|
| `app/ai_settings.py` | DB-backed settings (`app_settings` table) — bot on/off, model, rate limit, autopilot. Env se higher priority. TTL cache (5s) |
| `app/ai_writer.py` | AI Message Writer — intent → ready WhatsApp message. Placeholders handle karta hai |
| `app/ai_autopilot.py` | Full auto-pilot — har enabled event ke liye AI template generate/refresh (24h cache), phir existing checks bhejte hain |
| `app/routes/admin/ai_control_center.py` | Command Center page + overview API + writer API + autopilot run API |
| `app/templates/admin/admin_ai_control_center.html` | Command Center UI — status cards, controls, live overview |
| `app/routes/admin/broadcast.py` | Broadcast me **per-user personalization** (`{user_name}`, `{days_left}`...) + AI writer support |
| `app/whatsapp_automator.py` | `_get_template` ab auto-pilot ON + AI template ho to AI template use karta hai |
| `app/backup_scheduler.py` | 8 AM IST hook ab `run_ai_autopilot()` call karta hai (auto-pilot aware) |
| `app/ai_bot.py` | Support bot ab DB settings use karta hai (admin panel se control) |

---

## 📋 Settings (app_settings table — DB, env se priority)

| Key | Default | Control karta hai |
|---|---|---|
| `ai_bot_enabled` | env `AI_BOT_ENABLED` / true | WhatsApp + App chat ke AI replies |
| `ai_bot_model` | env `OLLAMA_MODEL` / llama3.2:1b | Reply model |
| `ai_bot_max_replies_per_hour` | env / 15 | Rate limit (1 hour, per number) |
| `ai_autopilot_enabled` | false | Full auto-pilot master switch |
| `ai_autopilot_model` | (reply model) | Auto-pilot template generation model |
| `ai_auto_template_<event>` | — | AI-generated template cache (body + generated_at JSON) |

> **Koi migration nahi chahiye** — `app_settings` table pehle se hai, keys
> runtime par INSERT ... ON CONFLICT se save hote hain.

---

## 🖥 AI Command Center page (`/admin/ai-command-center`)

### Status cards (live, 30s auto-refresh)
1. **AI Bot** — ON/OFF + current model
2. **Ollama (NAS)** — UP/DOWN + model installed ya nahi
3. **Evolution API** — connected/disconnected + version
4. **Rate Limit** — current max/hour
5. **Auto-pilot** — ON/OFF
6. **Escalations (24h)** — kitne users ne support manga (ATTENTION badge)

### Controls
- **AI Bot Controls**: ON/OFF toggle, model dropdown, max replies/hour → Save
- **Full Auto-pilot**: master toggle, generation model, events list (kaunse
  events enabled + AI template ready hai ya manual) → Save + link to
  WhatsApp Automation page

### Live overview (kya chal raha hai)
- **Recent Chats** — last 10 messages (AI reply vs user) + aaj ke stats
- **Recent Broadcasts** — last 6 broadcast_logs (status, progress)
- **Automation Today** — aaj bheje gaye auto messages (delivered/failed)

### Buttons
- **Run Auto-pilot Now** — background me AI templates generate karke due
  users ko bhejta hai (8 AM ka wait nahi)

---

## ✨ AI Message Writer

Ab har jagah static textarea boring nahi — AI se message banao:

### Broadcast page (`/admin/evolution-broadcast`)
- **"✨ Write with AI"** button — intent likho (e.g. *"renewal reminder,
  friendly Hinglish me, user ke naam ke saath"*) → AI ready message banata
  hai → "Use this message" → edit karke send
- **Placeholders hint**: `{user_name}` `{days_left}` `{expiry_date}` `{plan_type}`
- **"Personalize per user" checkbox** — ON karo to har user ko uske naam/
  days-left/plan ke saath alag message jayega (send time par replace)

### Automation page (`/admin/whatsapp-automation`)
- Har event card me **"Rewrite with AI"** button — us event ke context me
  fresh template banata hai → Save Template

### Command Center / API
- `POST /admin/api/ai/write-message` — `{intent, audience, placeholders}` → `{ok, message}`

---

## 🚀 Full Auto-pilot (business model)

```
8 AM IST (scheduler) ──┐
"Run Auto-pilot Now" ──┴─> run_ai_autopilot()
                              │
                              ├─ auto-pilot ON? ── NO ──> existing template checks (backward compatible)
                              │        │
                              │       YES
                              │        │
                              │        ▼
                              │  Har ENABLED event ke liye:
                              │    AI template generate/refresh (24h cache)
                              │    → app_settings.ai_auto_template_<event>
                              │        │
                              │        ▼
                              │  Existing checks (expiry/expired/inactive/welcome/renewal)
                              │    ab AI templates use karte hain
                              │    → placeholders har user ke liye personalize
                              ▼
                        Done ✅
```

**Kaunsi events AI handle karta hai:**
| Event | Kab | AI kya likhta hai |
|---|---|---|
| welcome | trial/pehli purchase | activation + features + support CTA |
| expiry_reminder | 7/3/1 din pehle | friendly reminder + renewal CTA |
| expired | expire hone par | renewal CTA (bina guilt ke) |
| renewal | payment ke baad | confirmation + plan + dhanyawad |
| inactive | 30+ din (configurable) | re-engagement + naye features |

> Per-event ON/OFF abhi bhi **WhatsApp Automation** page se hota hai —
> Command Center sirf master switch + template source dikhata hai.

---

## 🧠 AI Bot DB-first settings

`ai_bot.py` ab env nahi, **DB settings** use karta hai:
- `AI_BOT_ENABLED` → `ai_bot_enabled` (admin panel se ON/OFF)
- `OLLAMA_MODEL` → `ai_bot_model` (admin panel se model switch)
- `AI_BOT_MAX_REPLIES_PER_HOUR` → `ai_bot_max_replies_per_hour`

Env sirf **default** hai — DB me set kar diya to wo jeet ta hai. Bot ka
`bot_status()` ab pura settings snapshot return karta hai (debugging easy).

---

## 🧪 Deploy & Test

```bash
# 1. Push + deploy (usual flow)
cd nrega-server && git add -A && git commit -m "feat: AI Command Center + auto-pilot + AI writer" && git push
# NAS par: git pull && ./deploy.sh

# 2. Verify
#   GET /admin/ai-command-center  → page render + status cards
#   GET /admin/api/ai/overview    → JSON (bot, ollama, evolution, chats, broadcasts)
#   POST /admin/api/ai/write-message  {"intent": "renewal reminder friendly"} → message
#   POST /admin/api/ai/autopilot/run  → background run

# 3. Broadcast me AI writer + personalization test
#   - "Write with AI" → intent → message aaya? Use this message → personalize ON → send
#   - Broadcast history me har user ka alag preview nahi dikhega (log template
#     hi hota hai), par WhatsApp par naam replace hoga

# 4. Auto-pilot test
#   - Command Center → Auto-pilot ON → Save → "Run Auto-pilot Now"
#   - 10-20s baad /admin/api/ai/overview → automation_today me entries
#   - WhatsApp Automation stats card me delivered counts
```

---

## ⚠️ Notes & Limits

1. **llama3.2:1b** se AI writer ke messages short/simple honge. Better Hindi
   chahiye to `qwen2.5:7b-instruct` pull karke Command Center me select karo
   (~5-6GB RAM).
2. Auto-pilot templates **24h cache** — har din fresh. Template galat lagti
   ho to WhatsApp Automation page se edit karo (save template override karega
   — autopilot agli baar 24h baad hi regenerate karega).
3. Auto-pilot OFF karne par **purana behaviour 100% restore** hota hai.
4. `personalize` checkbox + AI writer dono optional hain — bina kisi bhi
   naye feature ke broadcast purana jaisa hi kaam karta hai.
5. Escalation count heuristic hai (`MANUAL/SUPPORT/human` wale user
   messages 24h me) — exact support requests ka accurate log nahi.
