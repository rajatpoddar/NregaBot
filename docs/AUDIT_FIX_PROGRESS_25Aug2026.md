# 🔧 Audit Fixes — Progress Report (25 Aug 2026)

> **Context:** Full forensic audit isi date par complete hua tha → detailed findings:
> [`docs/NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md`](NREGA_BOT_FORENSIC_AUDIT_25Aug2026.md)
>
> Ye document us audit ke **low-effort + high-impact + safe-to-implement** fixes ka
> implementation record hai — har fix ke liye: *issue kya tha → kya change kiya →
> ab kya sahi hua*. Har code change me `AUDIT FIX (25 Aug 2026)` comment bhi laga hai.

---

## 📊 Summary

| # | Fix | Severity | File(s) | Status |
|---|---|---|---|---|
| F1 | Windows core zip → **whitelist** packaging | 🔴 P0 | `.github/workflows/release.yml` | ✅ Applied |
| F2 | Loader: **downgrade refusal** + empty-hash fail-safe + HTTPS URL guard | 🟠 P1 | `loader.py` | ✅ Applied |
| F3 | About-tab updater me HTTPS URL guard | 🟠 P1 | `src/managers/services.py` | ✅ Applied |
| F4 | Hard-coded `EVO_*` fallbacks (LAN IP + API key) removed | 🟠 P1 | `src/config.py` | ✅ Applied |
| F5 | `--add-data=".env:."` bundling removed (main + lite) | 🟡 P2 | `build_windows.bat`, `build_macos.sh` | ✅ Applied |
| F6 | CI `SENTRY_DSN .env` creation steps removed (×2 jobs) | 🟡 P2 | `.github/workflows/release.yml` | ✅ Applied |
| F7 | Demand tab `'e' in locals()` dead-code bug fixed | 🟠 P1 | `src/tabs/demand_tab.py` | ✅ Applied |
| F8 | Usage-stats sync undefined-variable crash | 🟢 P3 | `src/tabs/history_manager.py` | ✅ Applied |
| F9 | MR Fill wrong-workcode protection + full-code retry map | 🟠 P1 | `src/tabs/mr_fill_tab.py` | ✅ Applied |
| F10 | `license.dat` chmod 600 | 🟡 P2 | 7 write-sites across 3 files | ⏸️ Deferred |

---

## F1 — Windows core zip ab whitelist se banta hai 🔴 P0

**Issue kya tha:** CI ka "Create Core Zip (Windows)" step poora repo `copytree` karke
ek **blacklist** (ignore-list) se chhupata tha. Isme har Windows user ke paas ye sab
jata tha: `AGENTS.md` (internal NAS IP `192.168.29.101`, SSH paths, deploy topology!),
`NREGA_BOT_IMPROVEMENT_PLAN.md`, `tests/`, smoke-test scripts, dev server launchers,
`.DS_Store`, logs — aur sabse khatarnak: **`nrega-server/` ignore-list me nahi tha**.
Aaj hi nrega-server folder build machine par hota (local build), to
`firebase-service-account.json` + `google-sheets-service-account.json` (private keys!)
har user ke core zip me ship ho jate. macOS zip already whitelist use karta tha
(`scripts/build_update.py`) — dono platforms ka guarantee alag tha.

**Kya change kiya:** `release.yml` ke Windows core-zip step ko `build_update.py` ke
whitelist se mirror kiya — sirf `main_app.py`, `lite_app.py`, `lite_loader.py`,
`requirements.txt`, `src/`, `config/`, `assets/`, aur `docs/` me se sirf
`changelog.json` + `license.txt`. Upar se ek extra `SENSITIVE_FILES` safety-net.

**Ab kya sahi hua:**
* Koi internal doc / dev file / secret kabhi update channel se leak nahi ho sakta —
  chahe repo me kuch bhi aa jaye.
* Dono platforms (Win + Mac) ka packaging contract identical.
* Core zip size chhota → faster updates, stable hashes (sirf real code changes se
  hash badalta hai).

**Verification:** Dry-run script (`scripts/_verify_whitelist_dryrun.py`) chalaya:
**184 files ship, LEAK CHECK CLEAN ✅, saare must-have runtime files present ✅**
(`main_app.py`, `src/config.py`, `src/locales/en.json`, `config/version.json`,
`docs/changelog.json`, `docs/license.txt`). Note: `.py` source abhi bhi included hai
— loader `app_live/src/config.py` padhkar version detect karta hai, isliye ye zaroori
hai (purana pyc-only incident).

---

## F2 — Loader ab downgrade + unverified updates refuse karta hai 🟠 P1

**Issue kya tha:** `loader.py::check_for_updates()` me
`needs_update = (server_ver != effective_ver)` — pure inequality. Server koi bhi
PURANA version bhej de, users uspe "update" ho jate (downgrade attack/mistake).
Dusra problem: hash verify `if server_hash:` tha — agar server hash khaali tha
(release flow me hashes deploy ke BAAD bharte hain), to download **bina kisi
verification ke** extract ho jata. Interesting: Lite loader (`lite_loader.py:467`)
me ye logic sahi thi (`<=` comparison) — dono loaders diverge ho chuke the.

**Kya change kiya:**
1. Downgrade refusal: `parse_version(server_ver) < parse_version(effective_ver)`
   → log + skip ("App is up to date.").
2. Update sirf **strictly newer** version ya same-version hotfix (hash changed) par.
3. Empty server hash = update REFUSE (pehle blind-apply hota tha). Fail-safe:
   verify na kar sake to old version hi chalao.
4. Transport guard: `download_url` sirf `https://nregabot.com/...` hi ho sakta hai
   (tampered version.json http:// ya foreign host pe redirect nahi kar sakta;
   `requests` by default https→http redirects follow karta hai).
5. `parse_version` loader me import add kiya.

**Ab kya sahi hua:** Rogue/galat server response users ko purane version par nahi
le ja sakta; bina hash ke code kabhi execute nahi hoga; payload download ka host +
scheme enforce hota hai. Ab dono loaders ka security posture same hai.

---

## F3 — About-tab updater me bhi HTTPS guard 🟠 P1

**Issue kya tha:** `services.py::download_and_install_update()` (About tab se manual
update) URL ko bina validate kiye download karta tha — wahi https→http redirect /
foreign-host risk jo F2 me loader me fix kiya.

**Kya change kiya:** `_worker()` ke start me guard — URL `https://nregabot.com/`
se start hona hi chahiye, warna clean error ("Refusing unsafe update URL") aur
Retry button wapas enable.

**Ab kya sahi hua:** Dono update paths (loader auto-update + About manual update)
ab same transport rule follow karte hain.

---

## F4 — Hard-coded Evolution API credentials removed 🟠 P1

**Issue kya tha:** `src/config.py` me:
```python
EVO_BASE_URL = os.environ.get('EVO_BASE_URL', 'http://192.168.29.101:8087')  # internal LAN IP!
EVO_API_KEY  = os.environ.get('EVO_API_KEY', 'NregaBotSec***')               # purana REAL key
```
Ye public GitHub repo me tha aur har packaged build me ship hota tha. Desktop client
in values ko kahin use bhi nahi karta (verified — WhatsApp server-side feature hai),
to ye pure disclosure tha.

**Kya change kiya:** Defaults ab empty strings (`''`). Comment updated jo batata hai
ki legacy path tab tak disabled rahega jab tak explicitly configure na ho.

**Ab kya sahi hua:** Public repo / builds me ab na internal IP hai na API key.
⚠️ **User action pending:** Evolution API key ko SERVER side par rotate karna abhi
baki hai (purani key already public tha).

---

## F5+F6 — `.env` bundling band 🟡 P2

**Issue kya tha:** Charo PyInstaller builds (`--add-data=".env:."`) root `.env` ko
bundle me daal dete the. CI me ye file `SENTRY_DSN=<secret>` ke saath banti thi →
secret har Setup.exe / portable zip / DMG me embedded. Aur codebase me SENTRY_DSN
padhne wala EK BHI line nahi tha — pure leak, zero benefit. Bundled `.env` runtime
me load bhi nahi hota tha (load_dotenv CWD search karta hai, _MEIPASS nahi).

**Kya change kiya:** `build_windows.bat` (2 lines) + `build_macos.sh` (2 lines) se
`--add-data=".env:."` hataya; `release.yml` ke dono jobs (build-windows,
build-beta-windows) se "Create .env file" steps hataye.

**Ab kya sahi hua:** Koi CI secret artifacts me ship nahi hota; future me agar koi
`.env` me secret daal bhi de to bundle me jane ka rasta hi nahi hai. Bundle size
thoda kam.

---

## F7 — Demand tab ka `'e' in locals()` dead-code bug 🟠 P1

**Issue kya tha:** `_process_demand()` ke `finally:` block me
`elif 'e' in locals():` likha tha. Python 3 me except-block khatam hote hi `e`
name DELETE ho jata hai — maine runtime test se confirm kiya (`'e' in locals()`
→ `False`, exception aane ke BAAD bhi). Matlab: **crash hone par bhi status
"Finished" dikhta tha** aur "INTELLIGENT HANDOFF" (auto work-allocation) partial
results pe chal jata tha. Operator ko kabhi pata nahi chalta ki run fail hua tha.

**Kya change kiya:**
1. Run start pe `self._demand_error = ""` clear.
2. Fatal except-handler me `self._demand_error = type(e).__name__` set.
3. `finally:` me `elif getattr(self, '_demand_error', ''):` — ab crash par
   status sach me `Error: <Type>` dikhata hai aur handoff skip hota hai.
4. Line ~1957: `'e' not in locals()` → `not getattr(self, '_demand_error', '')`.

**Ab kya sahi hua:** Crashed demand run ab correctly "Error" report karta hai,
auto-allocation galat/partial data pe fire nahi hota, aur logs me error state
persist rehti hai. (Inner village/panchayat-level handled errors jaan-bujh kar
flag set NAHI karte — wo skips hain, fatal nahi.)

---

## F8 — Usage-stats sync crash fix 🟢 P3

**Issue kya tha:** `history_manager.py:587` pe
`result.get('synced_features', len(snapshot))` — `snapshot` naam ka variable
function me exist hi nahi karta (wahan `stats` hai). Server agar 200-response me
wo key na bheje, `NameError` hota — jo broad except me swallow ho kar galat
"sync failed" log deta.

**Kya change kiya:** `len(snapshot)` → `len(stats)`. One-word fix.

**Ab kya sahi hua:** Sync fallback count ab sahi variable se aata hai; latent
NameError khatam.

---

## F9 — MR Fill wrong-workcode protection + full-code retry 🟠 P1

**Issue kya tha (3-part chain):**
1. Work code dropdown me blind `select_by_index(1)` — search fuzzy/multi-match
   return kare to **galat work code par attendance** fill ho sakti thi.
2. Results tree privacy ke liye truncated code dikhata tha
   (`truncate_workcode` → last 6 digits).
3. "Retry Failed" wahi TRUNCATED code portal search box me wapas daalta tha —
   suffix-match + first-option-select = wrong-target probability aur badh jati.

**Kya change kiya:**
1. Naya helper `_select_option_containing(select, target_key, label)` +
   `_norm_code()` (lowercase, alnum-only tolerant matching): dropdown me PEHLA
   option select hota hai jiske normalized text me requested code contained hai.
   Match na mile to `ValueError` → item cleanly "Failed" record hota hai.
   **Fail-safe direction:** worst case = item fail (pehle se better), kabhi
   galat fill nahi.
2. `_log_result()` ab `_full_workcode_map[truncated] = full_code` maintain karta hai.
3. `retry_logic_handler()` tree value ko map se FULL code me convert karke
   retry queue me daalta hai (unmapped ho to purana behavior fallback).

⚠️ **Note:** Ye portal-interaction logic hai — agle real run me ek chhota manual
test zaroor karo (1-2 work codes MR Fill karke): normal success + ek galat code
dalke "not found" path bhi dekhna.

**Ab kya sahi hua:** Attendance galat work code par jaane ka primary rasta band;
retry ab exact original code se chalta hai.

---

## ✅ Validation Results

| Check | Result |
|---|---|
| `py_compile` (6 changed .py files) | ✅ PASS |
| `release.yml` YAML parse | ✅ PASS |
| Leftover scan: `.env` add-data / EVO key / NAS IP in config / SENTRY_DSN | ✅ ZERO matches |
| Whitelist dry-run (184 files) | ✅ CLEAN — no leaks, all runtime files present |
| pytest (update-rollback suite) | ✅ 20/20 passed |
| `_smoke_test_tabs.py` (all tabs instantiate) | ✅ PASSED |

## ⏸️ Deferred (safe the, par quick-fix scope me nahi)

* **F10 — license.dat chmod 600:** 7 write-sites (app_license.py ×5, services.py ×1,
  lite_app.py ×1) ko shared helper pe migrate karna padega — mechanical but wide;
  akele next PR me karna better. Windows-majority user base par POSIX chmod ka
  marginal value hai.
* **Evolution API key rotation** — server-side action, USER karega (agent rule).
* Audit ke Phase-2 items (ed25519-signed zips, signed license responses, pinned
  requirements, MR-fill date-error vs already-filled disambiguation) — roadmap doc
  me already listed.

## 📁 Changed Files

```
.github/workflows/release.yml      (whitelist zip + 2× .env step removal)
loader.py                          (downgrade/hash/https guards)
src/config.py                      (EVO_* defaults → '')
src/managers/services.py           (HTTPS guard)
src/tabs/history_manager.py        (NameError fix)
src/tabs/demand_tab.py             ('e' in locals() fix, 4 edits)
src/tabs/mr_fill_tab.py            (target-matching + retry map, 4 edits)
scripts/build_windows.bat          (.env bundling removed ×2)
scripts/build_macos.sh             (.env bundling removed ×2)
scripts/_verify_whitelist_dryrun.py (NEW - verification helper, reusable pre-release check)
docs/AUDIT_FIX_PROGRESS_25Aug2026.md (NEW - ye file)
```

*Kuch bhi commit nahi kiya — review ke baad user commit karega. Rollback simple hai:
sab changes uncommitted working-tree changes hain (`git diff` / `git checkout -- <file>`).*


