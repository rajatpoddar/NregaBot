#!/bin/bash
# =============================================================================
#  deploy_version.sh — FULL release deployer (ek command me sab kuch)
#
#  Ye script poora release deploy kar deta hai:
#    1. Mac core zip + DMG  → local dist/ se NAS website/updates/ me upload
#    2. Windows core zip + Setup.exe + Linux tar.gz
#       → GitHub Release se AUTO-DOWNLOAD + NAS par upload
#    3. hash_windows ko GitHub ke core_win_vX.sha256 se AUTO-FILL
#       (config/version.json me — pehle ye copy-paste manually karna padta tha)
#    4. version.json → NAS config/ (sabse LAST, taaki server kabhi missing
#       file ko refer na kare)
#    5. docker-compose mount check (purana file-mount → ek baar refresh)
#    6. Live server verify
#
#  EXPECTED FLOW (pehle ye do kaam khud karo):
#    1. ./build_macos.sh            → dist/core_mac_vX.zip + DMG + hash_macos
#    2. git push                    → GitHub Actions Windows+Linux build karta
#       hai, GitHub Release publish hota hai (core_win_vX.zip + .sha256)
#    3. ./deploy_version.sh         → is script se bas ek command, done!
#
#  Usage:
#    ./deploy_version.sh                     # default NAS settings
#    NAS_HOST=192.168.1.50 ./deploy_version.sh
#
#  Required: ssh + scp access to NAS (password or key), internet (GitHub API).
# =============================================================================
set -e

# ── Config (env vars se override kar sakte ho) ──────────────────────────────
NAS_USER="${NAS_USER:-rajat}"
NAS_HOST="${NAS_HOST:-192.168.29.101}"
NAS_BASE="${NAS_BASE:-/volume1/docker/Projects/Nrega-Bot}"
COMPOSE_DIR="${NAS_BASE}/license-server"
NAS_UPDATES="${NAS_BASE}/website/updates"          # container me /updates mount
GITHUB_REPO="rajatpoddar/NregaBot"                 # public repo — bina token chalega

# ── SSH single-connection options (password sirf 1 baar) ───────────────────
SSH_CTL="/tmp/deploy_version_${NAS_USER}@${NAS_HOST}.sock"
SSH_COMMON=(-o ControlMaster=auto -o ControlPath="$SSH_CTL" -o ControlPersist=300 -o ConnectTimeout=10)

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_VERSION_JSON="$PROJECT_ROOT/config/version.json"
DIST_DIR="$PROJECT_ROOT/dist"

echo "┌──────────────────────────────────────────────────────────┐"
echo "│  NREGA Bot — FULL Release Deployer                       │"
echo "└──────────────────────────────────────────────────────────┘"

# ── 1. Validate + version nikaalo ──────────────────────────────────────────
if [ ! -f "$LOCAL_VERSION_JSON" ]; then
    echo "❌ Local version.json nahi mila: $LOCAL_VERSION_JSON"
    exit 1
fi
VER=$(python3 -c "import json,sys; d=json.load(open('$LOCAL_VERSION_JSON')); print(d['latest_version'])")
echo "📦 Version: v$VER"
GH_TAG="v$VER"

# ── 2. Local Mac build files check ─────────────────────────────────────────
CORE_MAC="$DIST_DIR/core_mac_v${VER}.zip"
DMG="$DIST_DIR/NREGABot-v${VER}-macOS.dmg"
if [ ! -f "$CORE_MAC" ]; then
    echo "❌ Mac core zip nahi mila: $CORE_MAC"
    echo "   Pehle build karo:  cd scripts && ./build_macos.sh"
    exit 1
fi
if [ ! -f "$DMG" ]; then
    echo "⚠️  DMG nahi mila ($DMG) — sirf core zip upload hoga, manual install ke liye DMG chahiye hoga."
fi

# ── 3. GitHub Release check (Windows/Linux assets) ─────────────────────────
echo "🔍 GitHub Release check karo ($GITHUB_REPO @ $GH_TAG)..."
GH_JSON=$(curl -s --max-time 20 "https://api.github.com/repos/$GITHUB_REPO/releases/tags/$GH_TAG")
if echo "$GH_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('tag_name') else 1)" 2>/dev/null; then
    echo "✅ GitHub Release $GH_TAG mila — Windows/Linux assets download honge."
else
    echo "❌ GitHub Release $GH_TAG nahi mila."
    echo ""
    echo "   Pehle ye do kaam karo:"
    echo "     1. ./build_macos.sh                        # Mac build (hash_macos auto)"
    echo "     2. git add -A && git commit -m 'v$VER' && git push"
    echo "      # GitHub Actions ~15-20 min me Windows + Linux build karke"
    echo "      # Release publish karta hai. Phir ye script dobara chalao."
    exit 1
fi

# ── 4. Download Windows + Linux assets from GitHub Release ─────────────────
CORE_WIN="$DIST_DIR/core_win_v${VER}.zip"
SETUP_WIN="$DIST_DIR/NREGABot-v${VER}-Setup.exe"
LINUX_TGZ="$DIST_DIR/NREGABot-v${VER}-Linux.tar.gz"
GH_BASE="https://github.com/$GITHUB_REPO/releases/download/$GH_TAG"

echo "⬇️  GitHub se assets download ho rahe hain..."
[ -f "$CORE_WIN" ]   || curl -sL --max-time 300 -o "$CORE_WIN"   "$GH_BASE/core_win_v${VER}.zip"
[ -f "$SETUP_WIN" ]  || curl -sL --max-time 600 -o "$SETUP_WIN"  "$GH_BASE/NREGABot-v${VER}-Setup.exe"
[ -f "$LINUX_TGZ" ]  || curl -sL --max-time 300 -o "$LINUX_TGZ"  "$GH_BASE/NREGABot-v${VER}-Linux.tar.gz"

# ── 5. Windows hash GitHub ke .sha256 se auto-fill ─────────────────────────
#    (pehle manually copy-paste karna padta tha — ab automate hai)
GH_WIN_HASH=$(curl -sL --max-time 60 "$GH_BASE/core_win_v${VER}.sha256" | tr -d '[:space:]')
if [ -z "$GH_WIN_HASH" ] || [ ${#GH_WIN_HASH} -ne 64 ]; then
    echo "⚠️  GitHub se core_win_v${VER}.sha256 nahi mila — hash_windows update skip."
else
    # Verify: downloaded zip ka hash match karna chahiye
    LOCAL_WIN_HASH=$(shasum -a 256 "$CORE_WIN" | awk '{print $1}')
    if [ "$GH_WIN_HASH" = "$LOCAL_WIN_HASH" ]; then
        python3 -c "
import json
p = '$LOCAL_VERSION_JSON'
d = json.load(open(p))
d['core_update']['hash_windows'] = '$GH_WIN_HASH'
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)
print('✅ hash_windows auto-updated:', '$GH_WIN_HASH')
"
    else
        echo "⚠️  Windows zip hash mismatch (GitHub=$GH_WIN_HASH vs local=$LOCAL_WIN_HASH) — version.json update skip."
    fi
fi

# ── 6. NAS connectivity (master connection yahin banta hai) ────────────────
echo "🔌 NAS check karo ($NAS_USER@$NAS_HOST)..."
if ! ssh "${SSH_COMMON[@]}" "$NAS_USER@$NAS_HOST" "test -d '$NAS_UPDATES'" 2>/dev/null; then
    echo "❌ NAS updates folder nahi mila: $NAS_UPDATES"
    echo "   NAS_USER/NAS_HOST check karo: NAS_USER=Rajat NAS_HOST=192.168.1.50 ./deploy_version.sh"
    exit 1
fi

# ── 7. Upload sab files NAS par ────────────────────────────────────────────
echo "📤 Upload NAS updates folder me ho raha hai..."
UPLOADS=()
[ -f "$CORE_MAC" ]  && UPLOADS+=("$CORE_MAC")
[ -f "$DMG" ]       && UPLOADS+=("$DMG")
[ -f "$CORE_WIN" ]  && UPLOADS+=("$CORE_WIN")
[ -f "$SETUP_WIN" ] && UPLOADS+=("$SETUP_WIN")
[ -f "$LINUX_TGZ" ] && UPLOADS+=("$LINUX_TGZ")

for f in "${UPLOADS[@]}"; do
    echo "   → $(basename "$f")"
    scp "${SSH_COMMON[@]}" "$f" "$NAS_USER@$NAS_HOST:$NAS_UPDATES/"
done

# ── 8. version.json upload (SABSE LAST — server kabhi missing file na dekhe) ─
echo "📄 version.json upload ho raha hai (last step)..."
scp "${SSH_COMMON[@]}" "$LOCAL_VERSION_JSON" "$NAS_USER@$NAS_HOST:$NAS_BASE/config/version.json"

# ── 9. docker-compose mount check — file mount ho to container refresh ─────
echo "🔍 docker-compose mount check..."
MOUNT_LINE=$(ssh "${SSH_COMMON[@]}" "$NAS_USER@$NAS_HOST" "grep -n 'config/version.json' '$COMPOSE_DIR/docker-compose.yml' 2>/dev/null || true")
if [ -n "$MOUNT_LINE" ]; then
    echo "⚠️  Purana file-level mount mila — container refresh ho raha hai (ek baar)..."
    ssh -t "${SSH_COMMON[@]}" "$NAS_USER@$NAS_HOST" "cd '$COMPOSE_DIR' && sudo bash -lc 'docker-compose up -d nrega-server-new'"
    echo "✅ Container refreshed. NOTE: NAS par docker-compose.yml bhi update karo"
    echo "   (directory mount) taaki future me restart kabhi na lage."
else
    echo "✅ Directory mount active hai — restart ki zaroorat NAHI, live serve hoga."
fi

# ── 10. Verify live server ─────────────────────────────────────────────────
echo "⏳ Server verify ho raha hai..."
sleep 3
LIVE_VER=$(curl -s --max-time 20 https://nregabot.com/version.json \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['latest_version'])" 2>/dev/null || echo "ERR")

if [ "$LIVE_VER" = "$VER" ]; then
    echo ""
    echo "✅ DONE — Server ab v$VER serve kar raha hai!"
    curl -s --max-time 20 https://nregabot.com/version.json \
        | python3 -c "
import sys,json
d=json.load(sys.stdin); cu=d['core_update']
print('   latest_version:', d['latest_version'])
print('   hash_macos  :', cu['hash_macos'])
print('   hash_windows:', cu['hash_windows'])
print('   url_macos   :', cu['url_macos'])
print('   url_windows :', cu['url_windows'])
"
    echo ""
    echo "📡 Smart update ab users ko auto milega — kuch aur karne ki zaroorat nahi!"
else
    echo ""
    echo "⚠️  Mismatch: local v$VER vs live v$LIVE_VER"
    echo "   Cloudflare cache ho sakta hai — 1 min wait karke dobara check karo:"
    echo "   curl -s https://nregabot.com/version.json | python3 -m json.tool | grep latest_version"
fi
