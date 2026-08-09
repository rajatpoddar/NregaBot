# Temp validation — deleted after run.
import py_compile
import sys

for f in ["nrega-server/app/routes/api/activity_log.py",
          "nrega-server/app/routes/api/automation_results.py"]:
    py_compile.compile(f, doraise=True)
    print("COMPILE-OK:", f)

sys.path.insert(0, "nrega-server")
from app.routes.api.activity_log import _sanitize_entries, _looks_like_timestamp

# Timestamp strict check
assert _looks_like_timestamp("2026-08-09 12:00:00")
assert not _looks_like_timestamp("2026-08-09" + "A" * 54)  # prefix-valid garbage must fail
assert not _looks_like_timestamp("not-a-date")
print("T1 strict timestamp OK")

# Prefix-valid garbage timestamp -> replaced with now (not left to break DB)
clean, dropped = _sanitize_entries([{"status": "success", "timestamp": "2026-08-09" + "A" * 54}])
assert len(clean) == 1 and dropped == 0
assert _looks_like_timestamp(clean[0]["timestamp"]), clean[0]["timestamp"][:20]
print("T2 garbage-timestamp fallback OK")

# Huge local_id clamped to INTEGER range
clean, dropped = _sanitize_entries([{"status": "success", "local_id": 99999999999999999999}])
assert clean[0]["local_id"] == 2147483647, clean[0]["local_id"]
print("T3 local_id clamp OK")

# Negative local_id -> 0
clean, _ = _sanitize_entries([{"status": "success", "local_id": -5}])
assert clean[0]["local_id"] == 0
print("T4 negative local_id OK")

# Normal flow still fine
clean, dropped = _sanitize_entries([{"status": "success", "local_id": 42, "timestamp": "2026-08-09 12:00:00"}])
assert clean[0]["local_id"] == 42 and clean[0]["status"] == "success" and dropped == 0
print("T5 clean entry OK")

# Bad status still dropped
clean, dropped = _sanitize_entries([{"status": "hacked"}])
assert clean == [] and dropped == 1
print("T6 bad-status dropped OK")

print("ALL-REVALIDATION-PASSED")
