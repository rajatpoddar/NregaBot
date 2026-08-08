# 🤖 NREGA Bot — AI Features Scope & Roadmap

> **Purpose:** NregaBot app + nrega-server me AI features ka complete scope, best user experience design, aur WhatsApp AI interaction plan.
> **Date:** August 8, 2026
> **Status:** Planning / Scope Analysis

---

## 1. 📊 Current Setup (Verified Facts)

| Layer | Tech | Details |
|-------|------|---------|
| **Desktop App** | Python + CustomTkinter | 33+ automation tabs (Demand, MR Gen, Wagelist, FTO, eKYC, MIS Reports...) |
| **Server** | Flask 3.1 + PostgreSQL | License auth, admin panel, cloud files, webhooks — Synology NAS par Docker |
| **WhatsApp** | Evolution API (`192.168.29.101:8087`) | Text + document send, incoming webhook, global queue (2–6s pacing) |
| **Chat Support** | `whatsapp_chat` table | App ↔ Server ↔ Admin WhatsApp (webhook abhi **log-only** hai) |
| **Data Sync** | `automation_results` table | Har automation ka raw result (columns + rows JSONB) server par 30 din |
| **Daily Report** | 6 AM task | Previous day ka multi-sheet Excel WhatsApp par |
| **Ollama** ✅ | `192.168.29.101:11434` | **`llama3.2:1b`** (1.2B, tools ✓, 131K context) + **`nomic-embed-text`** (embeddings ✓) — same NAS par, cost ₹0 |

### Why this setup is AI-ready (bahut lucky ho)

- **Ollama server ke saath hi hai** → local AI, koi cloud API cost nahi, data NAS ke bahar nahi jata.
- **`automation_results` me raw data already sync hota hai** → AI ko analysis ke liye structured data mil raha hai, kuch bhi naya scrape nahi karna.
- **WhatsApp webhook already configured hai** (`MESSAGES_UPSERT`) → bas endpoint me AI logic daal do, bot ready.
- **`nomic-embed-text` already installed** → RAG (docs Q&A) ka foundation ready hai.

---

## 2. 🏗️ AI Integration Architecture

```
┌─────────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
│   DESKTOP APP       │   │   NREGA-SERVER       │   │   OLLAMA (NAS)      │
│  (users ke PC)      │   │  (Flask + PG)        │   │  192.168.29.101     │
│                     │   │                      │   │                     │
│  AI Assistant Tab   │──►│  /api/ai/chat        │──►│  /api/generate      │
│  Automation results │──►│  automation_results  │   │  llama3.2:1b        │
│  (columns+rows)     │   │                      │   │  nomic-embed-text   │
└─────────────────────┘   │  /api/ai/summarize   │   └─────────────────────┘
                          │  /api/ai/analyze     │
                          │  /api/ai/embed       │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │  EVOLUTION API       │
                          │  192.168.29.101:8087 │◄── webhook (incoming msgs)
                          └──────────┬───────────┘
                                     ▼
                             User ka WhatsApp
```

**Key design decisions:**
- **AI server-side rakho, app me nahi** → ek baar server par AI banaya to har user ko bina update ke feature milega. App sirf chat UI dikhayega.
- **App ka AI call bhi server se hoke** → license token auth already hai (`token_required`), rate limiting (Flask-Limiter already installed) — abuse control free me.
- **Streaming support** (`stream: true`) → users ko typing feel milegi, 10s wait me bhi bot "zinda" lagega.
- **`keep_alive`** → model ko warm rakho (first prompt par 7.6s load hota hai — cold start slow hai, warm hone par <1s).

---

## 3. 🎯 AI Feature Scope — 3 Phases

### 🟢 Phase 1 — Quick Wins (1–2 hafte)

#### 1.1 AI Automation Report Summary 🔥 (sabse high value)
**Abhi:** Automation finish → template message ("Task: Demand | Panchayat: MATIYARA | Result: Total: 118 | Success: 115 | Failed: 3").

**AI ke saath:** Server `automation_notify.py` me AI layer — details + results rows ko model ko do, aur professional **Hinglish summary + insight + suggestion** banao:

> ✅ *MATIYARA ka Demand complete — 4 min me.*
> 📊 118 job cards me se 115 pass, 3 fail.
> ⚠️ Fail reason: 2 job cards ka no. wrong tha, 1 par server alert.
> 💡 Suggestion: fail list check karke "Resend Rejected" tab se retry karein.

**Files:** `nrega-server/app/routes/api/automation_notify.py` (modify) + `nrega-server/app/ai_utils.py` (new)
**Effort:** ~4–6 hrs. **Impact:** Har user ko roz dikhta hai — sabse zyada visibility.

#### 1.2 WhatsApp AI Support Bot 💬
**Abhi:** Webhook log-only hai — user message admin ke WhatsApp par jata hai, admin manually reply karta hai.

**AI ke saath:** Webhook me pehle AI try kare:
- **FAQ / how-to questions** → RAG se turant jawab (docs + Guide.txt + changelog se)
- **Commands** (`/help`, `/status`, `/report`) → predefined responses
- **Complex / issue reporting** → existing flow se admin ko forward + AI draft reply bhi bhej do (admin bas edit karke send kare)
- **Handover line:** "*Ye common question tha isliye maine jawab diya. Aur help chahiye to type karein 'MANUAL'*"

**Files:** `nrega-server/app/routes/api/whatsapp_chat.py` (webhook modify) + `nrega-server/app/ai_utils.py`
**Effort:** ~1 hafta. **Impact:** Rajat ka support load 60–70% kam.

#### 1.3 In-App AI Assistant Tab 🤖
**Abhi:** Users ko koi assistant nahi — help ke liye WhatsApp/email.

**AI ke saath:** Naya tab `src/tabs/ai_assistant_tab.py`:
- Hinglish chat — "MR gen kaise karein?", "wagelist me error aa raha hai"
- RAG over: README, Guide.txt, docs, tab-specific help text
- Quick action chips: *"💡 Demand kaise karein"* *"❌ Error fix"* *"📊 Mera aaj ka summary"*
- Typing indicator + streaming response

**Files:** `src/tabs/ai_assistant_tab.py` (new) + `src/tab_config.py` (register) + server `/api/ai/chat`
**Effort:** ~1 hafta. **Impact:** Support se pehle self-service.

#### 1.4 Smart Error Analysis 🛠️
**Abhi:** Automation fail hone par sirf error text dikhta hai, user confuse.

**AI ke saath:** Activity log errors ko AI se diagnose karo:
- "URL TEMPERED" → *Digest expire ho gaya, pending_bills_tab me seed_digest refresh karein*
- "Element not found" → *Page layout badla ho sakta hai, screenshot bhej kar support ko batao*
- Pehle 10 baar ka error pattern match — repeat ho raha hai to batana

**Files:** Server `app/routes/api/ai.py` + app error logging me hook
**Effort:** ~3–4 din. **Impact:** Fail hone par user ko next step pata ho.

---

### 🟡 Phase 2 — Data Intelligence (3–5 hafte)

#### 2.1 RAG Knowledge Base 📚
Guide.txt, README, changelog, FAQ, aur admin responses ko `nomic-embed-text` se embed karke vector store (pgvector ya local SQLite FTS + embeddings). Sab AI features ka foundation.

#### 2.2 Results Data Insights — "Mini MIS Analyst" 📈
**Gold mine:** `automation_results` me har run ka raw `columns + rows` pda hai.

- Har results table par **"🤖 AI Summary"** button → AI data ko padh kar batao: totals, anomalies, missing values, duplicates, out-of-range amounts
- Chat with your data: *"is demand me kitne job cards 10 din se zyada ke hain?"*
- **Excel/CSV upload + AI analysis** — village code mismatch, date format issues, amount errors detect karo

#### 2.3 Daily AI Digest (6 AM) 🌅
Abhi ka 6 AM report sirf Excel hai. AI se:
- Narrative summary: *"Kal 12 automations chali — 11 success, 1 fail. Sabse zyada activity MATIYARA me. Aapke 3 MR payment pending hain."*
- Excel ke saath **AI highlights message** bhi bhejo

#### 2.4 Document Q&A 📄
Cloud files (PDF/Excel) par sawal: *"is muster roll me total attendance kya hai?"*, *"MATIYARA ke pending bills ka total amount?"* — embeddings + chunking se.

---

### 🔴 Phase 3 — Intelligent Automation & Admin Copilot (5–8 hafte)

#### 3.1 Natural Language Commands 🗣️
*"MATIYARA ka demand chalao"* → AI intent detect karke demand tab kholo + panchayat select karo (user ko confirm karwao — automation destructive hai, **confirm step mandatory**).

#### 3.2 Data Cleaning & Validation Assistant 🧹
CSV/Excel import me:
- Village codes format check
- Aadhaar number validation
- Date format normalize
- Amount/wage rate mismatch detect
- Duplicate entries flag

#### 3.3 Template Generator ✍️
Official memos, payment notices, panchayat letters — 30 sec me draft (Hinglish + formal Hindi dono).

#### 3.4 Admin Copilot (Rajat ke liye) 🧠
- **Support ticket summaries** — chat history ka 1-line summary har ticket par
- **Repeated-failure detection** — "User X ke 8 runs fail hue is hafte — pattern: element not found"
- **Revenue/license insights** — expiring licenses, inactive users, AI-drafted renewal message
- **AI-drafted admin replies** — support me quick-reply suggestions

---

## 4. 💬 WhatsApp AI Interaction Design (Detailed)

### 4.1 Flow

```
User WhatsApp message
        │
        ▼
Evolution API → webhook → /api/whatsapp-chat/webhook
        │
        ├── 1. Identity: remoteJid → user_mobile → licenses table lookup
        ├── 2. Unknown number? → ignore/log (spam safety)
        │
        ├── 3. Command?  (/help, /status, /report) → instant scripted reply
        │
        ├── 4. FAQ match? → Ollama RAG auto-reply (2–5s)
        │
        ├── 5. Complex / emotion / escalation? → admin ko forward (existing)
        │        └── AI draft reply admin ke liye (Edit & Send)
        │
        └── 6. Log everything in whatsapp_chat (existing)
```

### 4.2 Design Rules (spam-proof & user-friendly)

| Rule | Detail |
|------|--------|
| **Cooldown** | Har number se max 5 bot-replies/hour (Flask-Limiter) |
| **Bot signature** | Har AI reply me 🤖 footer — *"Ye auto-reply hai. 'MANUAL' likh kar insaan se baat karein"* |
| **Human handover** | "MANUAL" / "SUPPORT" / profanity → turant admin ko forward |
| **Admin override** | Admin ka reply hamesha bot se priority — bot kabhi admin ke baad na bole |
| **Queue safety** | AI replies bhi existing `wa_queue` se (pacing already hai) |
| **Offline fallback** | Ollama down → "Currently on manual mode" + forward to admin (no crash) |
| **Hindi + Hinglish** | Model output Roman Hinglish (jaisa users bolte hain) |

### 4.3 Suggested WhatsApp Commands
```
/help     — feature list + bot guide
/status   — mera license, expiry, current panchayat
/report   — aaj ka automation summary (server se automation_results)
/ai <q>   — direct AI sawal, e.g. "/ai wagelist send kaise karein"
MANUAL    — human support se connect
```

---

## 5. 🎨 Best User Experience (UX) — AI kaise feel hona chahiye

1. **Hinglish-first** — users Roman Hinglish me bolte hain, AI bhi wahi bole. Koi "assistant" robot feel nahi.
2. **AI everywhere, lekin optional** — har results table par ek small "🤖 Summary" button. Zaroori nahi, available ho.
3. **Typing indicator + streaming** — 1B model slow hai, par streaming se reply type hote dikhega → wait bearable.
4. **Quick action chips** — empty state me: *"Mujhe MR gen nahi aata"* *"Error fix"* *"Aaj ka summary"* — user ko sochna na pade.
5. **Zero blocking** — AI call hamesha background thread me; UI kabhi freeze nahi. Timeout 60s, uske baad friendly message.
6. **Fallback chain** — Ollama down → simple rule-based FAQ → "try later" + support forward. Kabhi crash nahi.
7. **Privacy badge** — About/Settings me: *"🔒 AI aapke apne server par chalta hai — data kisi cloud provider ko nahi jata."* (Sale point bhi!)
8. **Beta labeling** — "🤖 AI Assistant (Beta)" — expectations set, feedback prompt.
9. **Feedback loop** — har AI reply ke saath 👍/👎 — model prompts ko improve karte raho.
10. **Latency budget** — 1B model: summary tasks <8s, chat <15s. Isse zyada ho to batching/streaming/caching use karo.

---

## 6. 🧠 Model Recommendations (Important!)

| Model | Size | Use For | Verdict |
|-------|------|---------|---------|
| **llama3.2:1b** (installed) | 1.2B | Intent detection, classification, structured JSON extraction, short summaries | ✅ Already there — fast, tools ✓ |
| **nomic-embed-text** (installed) | 137M | RAG embeddings | ✅ Perfect |
| **qwen2.5:7b-instruct** ⭐ | 7B | Chat, Hinglish Q&A, insights | 🎯 **Recommended** — Hindi quality bahut achhi, 1b se 10x better |
| **llama3.1:8b** | 8B | Chat, analysis | ✅ Good alternative |

> **⚠️ NOTE:** `llama3.2:1b` quality Hindi/analysis ke liye kaafi weak hai (English me bhi limited). **Phase 1 ke complex features (1.1, 1.3) ke liye 7–8B model chahiye.** NAS RAM check karo (`free -h`): 16GB+ RAM ho to `qwen2.5:7b-instruct` (Q4_K_M ~4.7GB) smoothly chalega. 1B ko fast/intent tasks ke liye rakho.
>
> **Performance tips:** `keep_alive` set karo (model warm), `stream: true`, aur heavy analysis ko Celery background task me (server me Celery already hai!).

---

## 7. 🛠️ Implementation Blueprint

### Server side (nrega-server/)

| File | Action | Contents |
|------|--------|----------|
| `app/ai_utils.py` | **NEW** | Ollama client: `generate()`, `stream_generate()`, `embed()`, `chat_with_context()`, health check, timeouts, retries |
| `app/routes/api/ai.py` | **NEW** | Blueprint: `/api/ai/chat`, `/api/ai/summarize`, `/api/ai/analyze`, `/api/ai/embed`, `/api/ai/health` — sab `token_required` + rate-limited |
| `app/routes/api/whatsapp_chat.py` | **MODIFY** | Webhook me AI layer (section 4.1 flow) |
| `app/routes/api/automation_notify.py` | **MODIFY** | AI summary in WhatsApp notification |
| `app/tasks.py` | **MODIFY** | Daily 6 AM report me AI narrative |
| `app/repositories/ai_chat_repo.py` | **NEW** | Chat history + feedback storage (optional) |
| `app/models.py` | **MODIFY** | `ai_chat_logs` table registration |
| `.env` | **MODIFY** | `OLLAMA_BASE_URL=http://192.168.29.101:11434`, `OLLAMA_MODEL=qwen2.5:7b-instruct`, `OLLAMA_EMBED=nomic-embed-text` |
| `requirements.txt` | **MODIFY** | (Optional: `pgvector` for embeddings — ya local JSON store se shuru karo) |

### Desktop app (src/)

| File | Action | Contents |
|------|--------|----------|
| `src/managers/ai_manager.py` | **NEW** | Server AI API client, streaming callback, background threads |
| `src/tabs/ai_assistant_tab.py` | **NEW** | Chat UI (existing `whatsapp_chat_tab.py` style reuse — bubbles, typing indicator) |
| `src/tab_config.py` | **MODIFY** | "AI Assistant" tab register (icon: 🤖) |
| `src/tabs/base_tab.py` | **MODIFY** | Results tree me "🤖 AI Summary" button |
| `src/app/app_automation.py` | **MODIFY** | Failure par AI error-diagnosis chip |
| `src/config.py` | **MODIFY** | `OLLAMA_BASE_URL` (server se hi ata hai, hardcode nahi) |

---

## 8. ⚡ Priority Matrix & Roadmap

| # | Feature | Impact | Effort | Phase |
|---|---------|--------|--------|-------|
| 1 | AI Automation Report Summary | 🔥🔥🔥 | 4–6 hrs | P1 |
| 2 | WhatsApp AI Support Bot | 🔥🔥🔥 | 1 hafta | P1 |
| 3 | In-App AI Assistant (RAG) | 🔥🔥🔥 | 1 hafta | P1 |
| 4 | Smart Error Analysis | 🔥🔥 | 3–4 din | P1 |
| 5 | RAG Knowledge Base | 🔥🔥🔥 | 3–5 din | P2 (foundation) |
| 6 | Results Data Insights | 🔥🔥🔥 | 1–2 hafte | P2 |
| 7 | Daily AI Digest | 🔥🔥 | 3–4 din | P2 |
| 8 | Document Q&A | 🔥🔥 | 2 hafte | P2 |
| 9 | NL Commands | 🔥 | 2–3 hafte | P3 |
| 10 | Data Cleaning AI | 🔥🔥 | 1–2 hafte | P3 |
| 11 | Template Generator | 🔥 | 3–4 din | P3 |
| 12 | Admin Copilot | 🔥🔥 | 2–3 hafte | P3 |

**Suggested start order:** `qwen2.5:7b` install → `ai_utils.py` → Feature #1 (summary) → #2 (WhatsApp bot) → #3 (assistant tab) → #6 (insights). Har feature 1 release me shamil karo (changelog me AI badges).

---

## 9. ⚠️ Risks & Considerations

| Risk | Mitigation |
|------|-----------|
| **NAS CPU/RAM limit** | 7B model NAS ko load karega — Celery background tasks me heavy AI, WhatsApp send path se AI ko alag rakho (send kabhi block na ho) |
| **1B model quality** | Complex tasks ke liye 7B; 1B sirf intent/classification |
| **WhatsApp spam/abuse** | Flask-Limiter + per-number cooldown + "MANUAL" handover |
| **Ollama down** | Fallback chain (rules → forward to admin), health endpoint + status dot |
| **Hallucination (galat data bolna)** | RAG answers me source reference, analysis me exact numbers sirf data se (no guessing); model prompts me "data se bahar mat jao" |
| **Privacy** | Sab local — koi data NAS se bahar nahi. Isko feature banao (marketing point) |
| **Latency** | keep_alive + streaming + async (Celery) |

---

## 10. 🚀 First Concrete Step

```bash
# 1. NAS par achha model install karo (qwen2.5:7b — Hindi ke liye best free option)
ssh Rajat@192.168.29.101 "docker exec ollama ollama pull qwen2.5:7b-instruct"

# 2. Verify
curl http://192.168.29.101:11434/api/tags
```

```python
# 3. Server par ai_utils.py (rough sketch)
import urllib.request, json

OLLAMA_URL = "http://192.168.29.101:11434"

def generate(prompt: str, model: str = "qwen2.5:7b-instruct",
             system: str = "Aap NREGA Bot ke support assistant hain. Hinglish me jawab do.",
             stream: bool = False, timeout: int = 60):
    payload = {
        "model": model, "prompt": prompt, "stream": stream,
        "system": system, "keep_alive": "10m",
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")).get("response", "")
```

**Phase 1 ka pehla milestone:** Feature #1 (AI Automation Report Summary) live — uske baad har update me AI features grow karte jao.

---

*End of scope document. Har feature ke details/implementation notes alag se request kar sakte ho.*
