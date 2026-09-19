# NEEDS-VALIDATION — `nregabot-run-1`

Prioritized leads. Each is source-grounded in the **desktop repo** but has a decisive fact
outside it (server-side behavior or deployment configuration). **These are not confirmed
vulnerabilities and carry no severity.** Do not run live probes against nregabot.com —
each plan is bounded-local or owner-observed.

---

## 1. `heartbeat-license-key-query-param` — credential-transport hygiene

- **Trace:** `src/app/app_license.py:1785` (`hb_key = lic.get('key')`) → `:1808`
  (`url += f"?license_key={hb_key}"`) → `:1810` (`http_session.get(url)`).
- **Verified evidence:** the app-config poll carries the password-equivalent key in the URL
  query string every ~20 s, while every sibling endpoint uses the Authorization header —
  the codebase's own documented invariant (`app_license.py:1625`: the key "must never
  appear in a browser URL"). TLS protects the wire, not downstream URL-scoped logging.
- **Affected boundary:** license key leaves header-scoped transport and enters URL-scoped
  surfaces (access logs, CDN/WAF retention, any URL reconstruction).
- **Exact blocker:** whether key-bearing URLs are actually *persisted* at nregabot.com's
  TLS termination (Flask/nginx access logs, Cloudflare tunnel/WAF settings) is a deployment
  fact; `nrega-server/` is out of scope for this run.
- **Bounded local next step:** loopback fixture server + one heartbeat iteration; record
  the request line to demonstrate the key on the wire in the URL (already source-visible
  at 1808 — this step only re-confirms the client half).
- **Owner-observed deployment check:** grep recent access logs for `license_key=`;
  review CDN/proxy/WAF full-URL retention and any third-party log shipping. **If logged:**
  rotate license keys, purge log archives containing keys, and switch the endpoint to the
  Authorization header (delete the query-param branch — the server already accepts the
  key from `/api/heartbeat`'s JSON body pattern).

## 2. `license-dat-unsigned-local-expiry-bypass` — licensing control strength

- **Trace:** `src/managers/services.py:56` (load plaintext JSON) → `:67` (parse
  self-declared `expires_at`) → `:68` (wall-clock comparison — the only local gate) →
  `:73` (grant access, server check is a daemon thread) → `:133` (`validate_on_server`
  exception path returns True — offline grace).
- **Verified evidence:** no HMAC/signature exists anywhere in `src/` (repo-wide search);
  `save_license_dat` (`src/utils.py:690`) writes plaintext JSON. Sandboxed negative
  control (`harness_local_check_1.py`): forged **expired** file + server unreachable →
  `check_license() -> False` — the local gate behaves as designed, so the bypass requires
  future-dating the file (trivial for its owner) **plus** the offline-grace path.
- **Affected boundary:** license validity enforcement is server-availability-dependent;
  a holder who edits one JSON field and blocks egress operates indefinitely offline.
- **Exact blocker:** (a) whether online rejection deactivates the app (deletes
  `license.dat`, locks UI) or merely shows a transient error; (b) the vendor's accepted
  abuse model — anti-tamper/revenue control vs. hard security boundary.
- **Bounded local next step:** sandbox fixture with a **future-dated** forged file and
  blocked egress; record that the app enters the licensed state (client-half proof).
- **Owner-observed deployment check:** with a deliberately expired/forged key and the
  server reachable, observe whether the app locks or continues; state the intended
  offline-grace policy. If a hard boundary is intended, add an HMAC (key derived at
  activation) over `{key, expires_at, machine_id}` and verify before any local grant.

## 3. `cloud-download-filename-traversal` — write-path trust of server metadata

- **Trace:** `src/tabs/file_management_tab.py:683` (GET `/files/api/download/{id}`) →
  `:686` (`local_path = os.path.join(save_dir, item['filename'])`, no sanitization) →
  `:688` (streamed `open(local_path,'wb')`).
- **Verified evidence:** the client joins server-controlled `filename` into a
  user-chosen directory with no rejection of separators, `..`, absolute paths, or (on
  Windows) drive/UNC forms; the upload side sends client-chosen `relative_path`
  (`file_management_tab.py:544`), so the filename namespace is client-writable data
  stored server-side and handed back verbatim to downloaders.
- **Affected boundary:** bytes written outside the user-selected directory if the server
  ever returns a traversal-shaped filename (malicious/compromised server, or
  cross-tenant filename influence if the server permits).
- **Exact blocker:** whether nrega-server validates `filename`/`relative_path` at
  store/list time, and whether two licensed users can share a file namespace — not
  observable in the desktop repo.
- **Bounded local next step:** loopback stub of `/files/api/download` returning
  `../../pwned.txt` with dummy bytes; drive the unmodified `_download_multiple_files`
  worker against a scratch `save_dir`; observe the write landing outside it (client-side
  path proof; no vendor server contacted).
- **Owner-observed deployment check:** inspect the upload handler's filename validation,
  the list endpoint's serialization, and tenancy isolation of `/files`. **If sanitization
  exists at store time and tenancy is enforced, close this record as rejected** with that
  evidence; otherwise fix server-side *and* add client-side `os.path.basename` +
  component rejection (defense in depth on the write sink).

## 4. `crash-report-unauth-arbitrary-content` — server ingest trust decision

- **Trace:** `src/utils.py:573` (payload: client-chosen `license_key` from local file,
  free-form `error_message`/`error_traceback`/`last_log_lines`) → `:503`
  (`POST /api/crash-report`, **no Authorization header**) → server handler (out of scope).
- **Verified evidence:** the client-side contribution is limited and by design
  (fire-and-forget crash reporting; PII-masked before send, `utils.py:577`). The comment
  at `utils.py:492` asserts server-side masking + rate limiting — an owner assertion,
  not a client-verifiable control. Any process on any machine can POST the same shape.
- **Affected boundary:** entirely server-side — whether unauthenticated, client-chosen
  `license_key` + free-form text yields log poisoning, a stored-XSS path into the admin
  panel, or PII cross-attribution.
- **Exact blocker:** the `/api/crash-report` handler, its storage, and the admin view's
  rendering context all live in `nrega-server/` (out of scope for this run).
- **Bounded local next step:** none beyond what source already establishes (no auth
  header, client-chosen key); the open question is server-only.
- **Owner-observed deployment check:** confirm (1) license_key ownership validation
  before storage, (2) field length caps/sanitization at store time, (3) auto-escaping in
  the admin crash-report view. **If all three hold, close as rejected.** If any fails,
  the finding belongs to the nrega-server audit; rate-limit + bind reports to the
  authenticated license at the server.
