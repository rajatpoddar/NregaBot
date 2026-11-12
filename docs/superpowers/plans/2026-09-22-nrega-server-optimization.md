# NREGA Server Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize `nrega-server` for production throughput, database connection safety, query efficiency, and caching with zero downtime and zero API contract breaks.

**Architecture:** 
1. Database pool tuning (options statement timeout, maxconn sizing for Gunicorn multi-worker model).
2. Multi-row bulk insertion (`execute_values`) for high-volume activity logs.
3. PostgreSQL index additions and sargable timestamp range queries.
4. Redis caching for hot paths (`/api/validate`, admin aggregations, and marketing homepage).
5. Static asset HTTP cache-control headers and lightweight healthcheck ping.

**Tech Stack:** Python 3.12, Flask 3.1, PostgreSQL 14 (psycopg2-binary), Redis 5.2, Gunicorn 23.0.

**Spec:** Current codebase at `nrega-server/` with verified 246 passing test baseline.

## Global Constraints
- Production Safety: Zero breaking changes to any desktop app API payload or response contracts (`/validate`, `/heartbeat`, `/activity-log/sync`, `/app-config`).
- Two-Repo Rule: Desktop app is in root `.`; server is in `nrega-server/`. All server git operations must use `git -C nrega-server <cmd>`.
- NAS Safety: Agent MUST NOT execute commands on NAS or push to NAS remotes (`RULE-CI-002`).
- 246-test baseline in `nrega-server/tests/` must remain 100% passing at every step.

---

### Task 1: Database Connection Pool & Statement Timeout Optimization

**Files:**
- Modify: `nrega-server/app/models.py:21-77`
- Test: `nrega-server/tests/test_fmt_ist.py` (and test suite)

**Interfaces:**
- Consumes: `psycopg2.pool.ThreadedConnectionPool`
- Produces: `get_db_conn(for_schema=False)` without per-checkout SQL query

- [ ] **Step 1: Check existing DB connection behavior in `models.py`**
Inspect lines 21-77 of `nrega-server/app/models.py`. Currently `db_pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=30, ...)` and `get_db_conn()` runs `cur.execute("SET statement_timeout = '30s'")` on every single checkout.

- [ ] **Step 2: Update `models.py` connection pool and `get_db_conn`**
In `init_db_pool()`:
Set `maxconn=10` (since Gunicorn has 3 workers × 4 threads = 12 threads total; 10 conns per worker pool = 30 max connections, leaving 70 for Celery, WebDAV, and backups).
Add `options='-c statement_timeout=30s'` to the connection parameters:
```python
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dbname=os.environ.get('POSTGRES_DB'),
            user=os.environ.get('POSTGRES_USER'),
            password=os.environ.get('POSTGRES_PASSWORD'),
            host=os.environ.get('DATABASE_HOST'),
            port=os.environ.get('DATABASE_PORT', '5432'),
            options='-c statement_timeout=30s',
        )
```
In `get_db_conn(for_schema=False)`:
Remove the checkout query `cur.execute("SET statement_timeout = '30s'")`.
If `for_schema=True`, reset timeout to 0 for schema migrations:
```python
def get_db_conn(for_schema=False):
    global db_pool
    if db_pool is None:
        init_db_pool()
    try:
        conn = db_pool.getconn()
        if for_schema:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '0'")
        _update_db_metrics()
        return conn
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise
```

- [ ] **Step 3: Run existing tests to verify pool functionality**
Run: `python3 -m unittest discover -s tests -p "test_*.py"` inside `nrega-server/`.
Expected: All 246 tests PASS.

- [ ] **Step 4: Commit Task 1**
```bash
git -C nrega-server add app/models.py
git -C nrega-server commit -m "perf(db): set statement timeout via connect options and tune pool maxconn"
```

---

### Task 2: High-Speed Batch INSERT in Activity Log Sync

**Files:**
- Modify: `nrega-server/app/repositories/activity_log_repo.py:28-84`
- Test: `nrega-server/tests/test_activity_sync_batch.py` (create new test)

**Interfaces:**
- Consumes: `psycopg2.extras.execute_values`, `mask_pii_text`
- Produces: `ActivityLogRepository.sync_batch(...) -> int` (returns number of inserted rows in single roundtrip)

- [ ] **Step 1: Write test for `sync_batch`**
Create `nrega-server/tests/test_activity_sync_batch.py`:
Test that `sync_batch` processes entries, handles empty entries gracefully, applies PII masking, and calls execute_values with the expected tuple format.

- [ ] **Step 2: Run test to verify it fails or needs implementation**
Run: `python3 -m unittest tests/test_activity_sync_batch.py` inside `nrega-server/`.

- [ ] **Step 3: Implement `execute_values` in `activity_log_repo.py`**
Replace individual `cur.execute` in loop with `from psycopg2.extras import execute_values`:
```python
        if not entries:
            return 0

        sql = """INSERT INTO activity_logs
                    (license_key, local_id, timestamp, activity_type, description,
                     automation_key, panchayat, village, status, duration_seconds, details,
                     app_version, os_platform, error_type, error_source, error_traceback,
                     created_at)
                  VALUES %s"""

        rows = []
        now_ts = datetime.utcnow()
        for entry in entries:
            description = mask_pii_text(entry.get('description', ''))
            details = mask_pii_text(entry.get('details', ''))
            error_type = mask_pii_text(entry.get('error_type') or '')
            error_source = mask_pii_text(entry.get('error_source') or '')
            error_traceback = mask_pii_text(entry.get('error_traceback') or '')[:4000]

            rows.append((
                license_key,
                entry.get('local_id', 0),
                entry.get('timestamp', now_ts.isoformat()),
                entry.get('activity_type', ''),
                description,
                entry.get('automation_key', ''),
                entry.get('panchayat', ''),
                entry.get('village', ''),
                entry.get('status', ''),
                float(entry.get('duration_seconds', 0) or 0),
                details,
                entry.get('app_version') or payload_app_version or '',
                entry.get('os_platform') or '',
                error_type,
                error_source,
                error_traceback,
                now_ts,
            ))

        with self._cursor(commit=True) as cur:
            execute_values(cur, sql, rows)
            return len(rows)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests/test_activity_sync_batch.py` inside `nrega-server/`.
Expected: PASS.

- [ ] **Step 5: Commit Task 2**
```bash
git -C nrega-server add app/repositories/activity_log_repo.py tests/test_activity_sync_batch.py
git -C nrega-server commit -m "perf(activity-log): use execute_values for single-roundtrip batch insert"
```

---

### Task 3: Missing Database Indexes Migration & Sargable Date Range Queries

**Files:**
- Create: `nrega-server/migrations/037_performance_indexes.sql`
- Modify: `nrega-server/app/repositories/activity_log_repo.py:109-125`
- Modify: `nrega-server/app/repositories/automation_results_repo.py:123-130`
- Test: `nrega-server/tests/test_migration_037.py`

**Interfaces:**
- Consumes: PostgreSQL schema migrations
- Produces: B-tree indexes for `licenses(last_seen)`, `licenses(key_type)`, `activity_logs(status, created_at)`, `activity_logs(automation_key, created_at)`

- [ ] **Step 1: Write SQL migration file `037_performance_indexes.sql`**
```sql
-- Migration 037: Performance Indexes for Dashboard & Activity Queries
-- Idempotent index creation to accelerate frequent filtering and sorting.

CREATE INDEX IF NOT EXISTS idx_licenses_last_seen
    ON licenses (last_seen DESC);

CREATE INDEX IF NOT EXISTS idx_licenses_key_type
    ON licenses (key_type);

CREATE INDEX IF NOT EXISTS idx_al_status_created
    ON activity_logs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_al_auto_created
    ON activity_logs (automation_key, created_at DESC);
```

- [ ] **Step 2: Update Date Filters in Repositories to be Sargable**
In `activity_log_repo.py` and `automation_results_repo.py`:
Change `DATE(created_at) >= %s` to `created_at >= %s::timestamp` and `DATE(created_at) <= %s` to `created_at <= (%s::date + INTERVAL '1 day')` or append `' 00:00:00'` / `' 23:59:59'`. This enables PostgreSQL to use the b-tree index on `created_at`.

- [ ] **Step 3: Write test verifying migration 037 exists and is valid**
Verify migration runner recognizes `037_performance_indexes.sql`.

- [ ] **Step 4: Run server test suite**
Run: `python3 -m unittest discover -s tests -p "test_*.py"` inside `nrega-server/`.
Expected: PASS.

- [ ] **Step 5: Commit Task 3**
```bash
git -C nrega-server add migrations/037_performance_indexes.sql app/repositories/activity_log_repo.py app/repositories/automation_results_repo.py tests/test_migration_037.py
git -C nrega-server commit -m "perf(db): add 037 performance indexes and sargable date queries"
```

---

### Task 4: Caching for Hot `/api/validate` and Admin Activity Dashboard

**Files:**
- Modify: `nrega-server/app/routes/api/auth.py:372-385`
- Modify: `nrega-server/app/routes/admin/features.py:70-95`
- Modify: `nrega-server/app/routes/admin/activity.py:218-265`
- Test: `nrega-server/tests/test_hot_path_caching.py`

**Interfaces:**
- Consumes: `app.cache.cache`
- Produces: Cached `disabled_features` and admin activity stats

- [ ] **Step 1: Write test for cached features and stats**
Create `nrega-server/tests/test_hot_path_caching.py` testing cache get/set and invalidation.

- [ ] **Step 2: Cache `disabled_features` in `/api/validate`**
In `app/routes/api/auth.py`:
```python
disabled_features = cache.get('app:settings:disabled_features')
if disabled_features is None:
    cur.execute("SELECT value FROM app_settings WHERE key = 'disabled_features'")
    row = cur.fetchone()
    disabled_features = row[0] if row and row[0] else ''
    cache.set('app:settings:disabled_features', disabled_features, ttl=300)
```
In `app/routes/admin/features.py`:
When admin updates disabled features, call:
```python
cache.delete('app:settings:disabled_features')
```

- [ ] **Step 3: Optimize and cache Admin Activity Logs aggregations**
In `app/routes/admin/activity.py::activity_logs_api()`:
1. Cache `stats = cache.get('admin:activity:stats')` (TTL 60s). If missing, query DB and `cache.set('admin:activity:stats', stats, ttl=60)`.
2. Cache `top_automations = cache.get('admin:activity:top_automations')` (TTL 300s).
3. In `count_sql`:
If `search_query` is empty, use `SELECT COUNT(al.id) FROM activity_logs al {where_sql}` without joining `licenses l`.

- [ ] **Step 4: Run test suite**
Run: `python3 -m unittest discover -s tests -p "test_*.py"` inside `nrega-server/`.
Expected: PASS.

- [ ] **Step 5: Commit Task 4**
```bash
git -C nrega-server add app/routes/api/auth.py app/routes/admin/features.py app/routes/admin/activity.py tests/test_hot_path_caching.py
git -C nrega-server commit -m "perf(cache): cache disabled_features on /validate and activity stats in admin"
```

---

### Task 5: Marketing Website & Static Asset Caching & Headers

**Files:**
- Modify: `nrega-server/app/routes/website.py:63-95, 174-211`
- Modify: `nrega-server/app/routes/admin/pricing.py:80-115`
- Test: `nrega-server/tests/test_website_caching.py`

**Interfaces:**
- Consumes: `app.cache.cache`, `send_from_directory(..., max_age=...)`
- Produces: Sub-millisecond homepage rendering and 24-hour browser caching for static assets

- [ ] **Step 1: Write test for website caching & static headers**
Create `nrega-server/tests/test_website_caching.py`.

- [ ] **Step 2: Implement homepage HTML caching in `website.py`**
In `render_index_html()`:
Check `cache.get('website:index_html')`. If found, return `Response(cached_html, mimetype='text/html')`.
Otherwise, build it, set `cache.set('website:index_html', html, ttl=300)`, and return.
In `app/routes/admin/pricing.py`:
When admin saves pricing updates, call `cache.delete('website:index_html')`.

- [ ] **Step 3: Add `max_age` to static asset responses in `website.py`**
In `website_file()`:
Set `max_age=86400` (24 hours) for images, stylesheets, scripts, and favicon:
```python
return send_from_directory(dir_path, filename, max_age=86400)
```
For `version.json` and updates, ensure `max_age=0` (or leave default no-cache) so update checks are always immediate.

- [ ] **Step 4: Run tests**
Run: `python3 -m unittest tests/test_website_caching.py` inside `nrega-server/`.
Expected: PASS.

- [ ] **Step 5: Commit Task 5**
```bash
git -C nrega-server add app/routes/website.py app/routes/admin/pricing.py tests/test_website_caching.py
git -C nrega-server commit -m "perf(web): cache rendered homepage and set 24h static asset cache headers"
```

---

### Task 6: Lightweight Health Check Ping & Webhook Lock Verification

**Files:**
- Modify: `nrega-server/app/routes/api/health.py:68-80`
- Modify: `nrega-server/run.py:65-84`
- Test: `nrega-server/tests/test_health_ping.py`

**Interfaces:**
- Consumes: `redis_client.ping()`
- Produces: Zero-write health checks and single-worker webhook registration

- [ ] **Step 1: Optimize Redis health check in `health.py`**
Replace `cache.set('__health_check__', 1)` / `cache.get` / `cache.delete` with:
```python
    try:
        from ...cache import _get_client
        r_client = _get_client()
        if r_client and r_client.ping():
            checks['redis'] = 'ok'
        else:
            checks['redis'] = 'error'
            all_ok = False
    except Exception as e:
        logger.warning(f"Health check — redis failed: {e}")
        checks['redis'] = 'not_configured'
```

- [ ] **Step 2: Guard Evolution webhook thread in `run.py` with file lock**
Add non-blocking file lock `/tmp/nrega_webhook_setup.lock` so only the first Gunicorn worker sets up the webhook on boot, eliminating 3 concurrent identical webhook calls.

- [ ] **Step 3: Run full server test suite**
Run: `python3 -m unittest discover -s tests -p "test_*.py"` inside `nrega-server/`.
Expected: All tests PASS.

- [ ] **Step 4: Commit Task 6**
```bash
git -C nrega-server add app/routes/api/health.py run.py tests/test_health_ping.py
git -C nrega-server commit -m "perf(ops): use direct redis ping in healthcheck and lock webhook setup"
```
