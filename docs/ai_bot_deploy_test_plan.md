# 🚀 AI Bot — Deploy & Live Test Plan

> **Kya deploy hoga:** WhatsApp AI Support Bot + in-app AI chat (desktop app WhatsApp Chat tab).
> **Files changed (nrega-server repo):**
> - `app/ai_utils.py` (naya) — Ollama client
> - `app/ai_bot.py` (naya) — bot logic (user lookup, commands, MANUAL handover, rate limit, shared `handle_message`)
> - `app/routes/api/ai.py` (naya) — `POST /api/ai/chat`
> - `app/routes/api/whatsapp_chat.py` — webhook → AI bot + `whatsapp-chat/send` background AI
> - `app/routes/api/__init__.py` — ai module register
> - `.env.example`, `docs/` (3 AI docs)
> - App repo: `src/tabs/whatsapp_chat_tab.py` (typing indicator — next app release)
>
> **Server info:** NAS `192.168.29.101` · repo path `/volume1/docker/Projects/Nrega-Bot` · compose dir `license-server/` · service `nrega-server-new` · health `localhost:4991/api/health` · public domain `nregabot.com`

---

## Phase 0 — Pre-flight (Local)

```bash
# 1. Confirm saare changes committed hain (server repo)
cd nrega-server
git status --short          # expect: ai_bot.py, ai_utils.py, routes/api/ai.py,
                            # whatsapp_chat.py, __init__.py, .env.example, docs/
# 2. Syntax check (optional, already done)
python3 -m py_compile app/ai_bot.py app/ai_utils.py app/routes/api/ai.py \
        app/routes/api/whatsapp_chat.py app/routes/api/__init__.py && echo OK
```

---

## Phase 1 — NAS: Environment Variables

```bash
ssh rajat@192.168.29.101
cd /volume1/docker/Projects/Nrega-Bot/license-server

# .env me ye add/edit karo (nano .env)
cat >> .env <<'EOF'

# --- AI Bot (Ollama) ---
OLLAMA_BASE_URL=http://192.168.29.101:11434
OLLAMA_MODEL=llama3.2:1b
OLLAMA_FALLBACK_MODEL=qwen2.5:7b-instruct
AI_BOT_ENABLED=true
AI_BOT_MAX_REPLIES_PER_HOUR=15
EOF

# 3. Verify: server container se Ollama reachable hai?
docker exec $(docker ps -qf name=nrega-server-new) \
  curl -s --max-time 5 http://192.168.29.101:11434/api/tags | head -c 300
# EXPECT: {"models":[{"name":"llama3.2:1b", ... "name":"nomic-embed-text" ...}]}
```

> ⚠️ Agar container se curl fail ho (network) to `OLLAMA_BASE_URL` ko container ke
> liye reachable address par point karo (e.g. host-gateway). Fail-safe me bot
> "busy" fallback + admin forward karega — server crash nahi hoga.

---

## Phase 2 — Deploy (Push + Build + Restart)

```bash
# 4. Local se server repo push karo
cd nrega-server
git add -A && git commit -m "feat: WhatsApp AI support bot + in-app AI chat" && git push

# 5. NAS par pull + deploy
ssh rajat@192.168.29.101
cd /volume1/docker/Projects/Nrega-Bot/license-server
git pull

# 6. Full deploy (build nrega-server-new + celery + webdav, restart, health check)
./deploy.sh
# EXPECT (last lines):
#   ✓ All containers started
#   ✓ Server is healthy (HTTP 200)
```

**Manual alternative** (agar sirf server service chahiye):
```bash
docker-compose build nrega-server-new && docker-compose up -d nrega-server-new
```

---

## Phase 3 — Server-side Verify (Logs + Status)

```bash
# 7. Logs me koi import/startup error nahi hona chahiye
docker-compose logs nrega-server-new --tail=100 | grep -iE "error|traceback|ai bot|webhook|queue" | tail -20
# EXPECT: "WhatsApp send queue started", "Evolution API webhook configured" ...
#         Koi "ImportError"/"Traceback" NAHI

# 8. Webhook configured hai? (incoming messages isi par aate hain)
curl -s https://nregabot.com/api/admin/whatsapp-chat-webhook-status
# EXPECT: {"webhook_configured": true, "instance_state": "open", ...}
# ⚠️ IMPORTANT: webhook_url "http://192.168.29.101:4991/api/whatsapp-chat/webhook"
#    hona chahiye (NAS LAN IP + mapped port 4991). Pehle galat
#    "192.168.29.209:8000" set tha → EVO log me "error: -113" (host unreachable)
#    → messages kabhi server tak nahi pahunchte the. Fix: run.py ab env-driven
#    WEBHOOK_HOST/WEBHOOK_PORT se URL banata hai (default .101:4991).

# 9. AI bot + Ollama status
curl -s https://nregabot.com/api/admin/ai-bot-status
# EXPECT: {"bot": {"enabled": true,
#                  "ollama": {"status": "ok", "configured_model": "llama3.2:1b",
#                             "model_available": true, ...},
#                  "manual_numbers": []}}

# 10. Knowledge base file load hui? (container me /app/docs/... hona chahiye)
docker exec $(docker ps -qf name=nrega-server-new) ls /app/docs/
# EXPECT: ai_bot_knowledge_base.md  ai_features_scope.md  ai_bot_system_prompt.md
# Logs me "AI KB file load failed" NAHI aana chahiye
```

---

## Phase 4 — API Test (`POST /api/ai/chat`)

```bash
# License key: admin panel se kisi apne/registered user ka key lo
KEY="YOUR_LICENSE_KEY"

# 11. Normal AI sawal
curl -s -X POST https://nregabot.com/api/ai/chat \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"message": "Demand kaise karein?"}'
# EXPECT: {"status":"success","reply":"Namaste ...","delivery_status":"answered"}
# NOTE: pehli call slow hogi (model cold load ~5-10s), phir warm (<3s)

# 12. Command
curl -s -X POST https://nregabot.com/api/ai/chat \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"message": "/pricing"}'
# EXPECT: reply me "₹99 ... ₹999"

# 13. MANUAL handover
curl -s -X POST https://nregabot.com/api/ai/chat \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"message": "MANUAL"}'
# EXPECT: "delivery_status":"escalated" + reply "support team se baat"

# 14. Galat token → 401/403 (security check)
curl -s -X POST https://nregabot.com/api/ai/chat \
  -H "Authorization: Bearer WRONG_KEY" -H "Content-Type: application/json" \
  -d '{"message": "hi"}'
# EXPECT: unauthorized error
```

---

## Phase 5 — Desktop App Chat Test (Channel B)

> ⚠️ Server-side AI chat **bina app update ke** chal jata hai (polling reply uthata hai).
> Typing indicator + header subtitle next app release me.

1. App kholo → **WhatsApp Chat** tab
2. Type: `MR gen kaise karein?` → Enter
3. **EXPECT:**
   - Tab me "🤖 AI soch raha hai..." indicator (app update wale builds me)
   - ~5-30s me AI ka reply Support bubble me (polling 3s)
   - Reply ka end: `🤖 *Ye auto-reply hai...*` footer
4. Type: `/status` → aapka naam, location, expiry, storage dikhe
5. Type: `MANUAL` → "support team se baat" reply + **admin ke WhatsApp par forward** (917033703380)
6. Admin panel → WhatsApp Chat viewer → conversation dikhna chahiye (user + AI reply dono)

---

## Phase 6 — WhatsApp Webhook Test (Channel A)

> **Zaroori:** testing us number se karo jo `licenses.user_mobile` me registered ho.

1. Apne registered phone se **NREGA Bot WhatsApp number** par message karo:
   - `Demand kaise karein?` → AI reply (~5-30s, pehli baar slow)
   - `/status` → account status
   - `manual entry kaise karein` → **AI reply** (handover NAHI — exact match test) ✅
   - `MANUAL` → "support team" confirm + admin ko forward
2. **Unknown number** se message → koi reply nahi (log me "unknown number ... ignored")
3. Server logs check karo:
```bash
docker-compose logs nrega-server-new --tail=50 | grep -iE "webhook|ai bot|queue"
# EXPECT: "📩 Webhook: event=messages.upsert, jid=91XXXXXXXXXX@..., fromMe=False"
#         "✅ Evolution text sent to 91XXXXXXXXXX" (reply)
```

---

## Phase 7 — Rollback (Agar Kuch Galat Ho)

| Situation | Action |
|-----------|--------|
| **Bot bekaar reply de raha / galat behave** | `.env` me `AI_BOT_ENABLED=false` → `docker-compose up -d nrega-server-new` → server restart. Ab messages seedha admin ko forward (purana support flow). |
| **Ollama down / server me issue** | Bot automatic fallback: "busy" reply + admin forward. Kabhi crash nahi. |
| **Poora revert chahiye** | `git log` → purana commit → `git revert` → redeploy. |

---

## Quick Troubleshooting

| Symptom | Check |
|---------|-------|
| AI reply nahi aa raha | `GET /api/admin/ai-bot-status` → `ollama.status` + `model_available`; logs me "generate failed" |
| Model not found | `docker exec ollama ollama pull llama3.2:1b` (NAS par) |
| Webhook se kuch nahi aata | `GET /api/admin/whatsapp-chat-webhook-status` → `webhook_url` = `http://192.168.29.101:4991/...` hona chahiye (galat IP/port = EVO me `error -113`). Evolution me WhatsApp Web session connected hona chahiye (`instance_state: open`) |
| Container se Ollama unreachable | `docker exec ... curl -s --max-time 5 http://192.168.29.101:11434/api/tags`; `OLLAMA_BASE_URL` fix karo |
| Reply slow (10-30s) | Normal for 1B model cold start + NAS; `keep_alive` warm hone ke baad <5s. Heavy use par `qwen2.5:7b` se quality+speed balance |
| Server 500 on /api/ai/chat | Logs me traceback; `whatsapp_chat` table me insert issue? `AI_KB_PATH` file load? |

---

## Success Checklist (sab ✅ = live!)

- [ ] `/api/admin/ai-bot-status` → `ollama.status: ok`, `model_available: true`
- [ ] `/api/admin/whatsapp-chat-webhook-status` → `webhook_configured: true`
- [ ] `/api/ai/chat` → AI answer + command + MANUAL escalation + bad-token reject
- [ ] App chat me message → AI reply bubble (bina app update)
- [ ] WhatsApp registered number → AI reply; unknown → ignored
- [ ] `MANUAL` → admin ko WhatsApp forward (dono channels)
- [ ] Logs me koi traceback nahi
