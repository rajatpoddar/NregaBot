# tabs/history_manager.py
import sqlite3
import json
import os
import threading
from datetime import datetime  # <-- Time save karne ke liye ye zaroori hai
from src import config  # For APP_VERSION — auto-reset usage stats on version change
from src.utils import get_logger
from typing import Any, Dict, List, Optional, Tuple

logger = get_logger()

class HistoryManager:
    # ── Per-tab input JSON files (form values like panchayat, village, etc.) ──
    # These are NOT config/default files — they store last-used form inputs.
    # Clear All Suggestions should also clear these.
    TAB_INPUT_FILES = [
        "ekyc_inputs.json",
        "mr_tracking_inputs.json",
        "issued_mr_report_inputs.json",
        "work_alloc_inputs.json",
        "zero_mr_inputs.json",
        "mis_reports_inputs.json",
        "sad_update_inputs.json",
        "sad_inputs.json",
        "scheme_closing_inputs.json",
        "mate_mr_inputs.json",
        "muster_roll_inputs.json",
        "demand_inputs.json",
        "dashboard_report_inputs.json",
        "nmms_inputs.json",
        "mr_fill_inputs.json",
        "physical_complete_inputs.json",
    ]

    def __init__(self, data_path_func):
        self.data_path_func = data_path_func  # Store for later use (clearing tab inputs)
        self.db_file = data_path_func('nrega_local_db.sqlite')
        self.old_json_file = data_path_func('autocomplete_history.json')
        self.lock = threading.Lock()
        self._conn = None  # Persistent connection (lazy init)
        
        self._init_db()
        self._migrate_from_json_if_needed()
        self._import_tab_inputs_from_json()  # Migrate legacy JSON files to DB
        self._check_version_reset()  # Auto-reset usage stats on new version

    def _get_connection(self):
        """Returns the persistent connection, creating it on first call with WAL mode."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read/write
            self._conn.execute("PRAGMA busy_timeout=5000")  # Wait up to 5s if locked
        return self._conn

    def close(self):
        """Closes the persistent database connection."""
        with self.lock:
            try:
                if self._conn:
                    self._conn.close()
                    self._conn = None
            except Exception as e:
                logger.debug("HistoryManager.close failed: %s", e)

    def _init_db(self):
        """Create the tables."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Table 1: Autocomplete
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS suggestions (
                        field_key TEXT,
                        value TEXT,
                        UNIQUE(field_key, value)
                    )
                ''')
                
                # Table 2: Usage Stats
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS usage_stats (
                        automation_key TEXT PRIMARY KEY,
                        count INTEGER DEFAULT 0
                    )
                ''')

                # --- NEW TABLE: Activity Log (enhanced columns) ---
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        activity_type TEXT,
                        description TEXT,
                        automation_key TEXT DEFAULT '',
                        panchayat TEXT DEFAULT '',
                        village TEXT DEFAULT '',
                        status TEXT DEFAULT '',
                        duration_seconds REAL DEFAULT 0,
                        details TEXT DEFAULT '',
                        app_version TEXT DEFAULT '',
                        os_platform TEXT DEFAULT '',
                        error_type TEXT DEFAULT '',
                        error_source TEXT DEFAULT '',
                        error_traceback TEXT DEFAULT ''
                    )
                ''')
                
                # Migrate old table if needed: add new columns
                self._migrate_activity_log_columns(cursor)
                
                # Table 3: App Meta for version tracking
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS app_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')

                # Table 4: Per-tab form input values (replaces JSON files)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tab_inputs (
                        tab_key TEXT,
                        field_key TEXT,
                        value TEXT,
                        UNIQUE(tab_key, field_key)
                    )
                ''')
                
                conn.commit()
            except Exception as e:
                logger.error("Database Init Error: %s", e)

    def _check_version_reset(self):
        """
        On every app launch, check if the base app version has changed.
        
        Only resets usage_stats when the MAJOR or MINOR version number changes
        (e.g. 2.x → 3.x, or 3.0 → 3.1). Patch version bumps (3.0.6 → 3.0.7)
        and -LITE suffix differences are ignored so usage history persists
        across both main & lite apps and small updates.
        
        This prevents:
        1. Main app ↔ Lite app switching from resetting each other's stats
           (since Lite app appends '-LITE' to APP_VERSION)
        2. Daily patch updates from wiping user's 'Most Used' history
        """
        # Strip -LITE suffix and use only base version for comparison
        current_ver = config.APP_VERSION.split('-')[0]
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM app_meta WHERE key = 'base_version'")
                row = cursor.fetchone()
                stored_ver = row[0] if row else None
                
                # Parse versions to compare at major.minor level
                current_parts = self._parse_version_parts(current_ver)
                stored_parts = self._parse_version_parts(stored_ver) if stored_ver else (0,)
                
                # Reset only when major or minor version changes
                should_reset = (
                    stored_ver is None  # First launch
                    or current_parts[0] != stored_parts[0]  # Major version change
                    or (len(current_parts) > 1 and len(stored_parts) > 1
                        and current_parts[0] == stored_parts[0]
                        and current_parts[1] != stored_parts[1])  # Minor version change
                )
                
                if should_reset:
                    # Reset usage stats for a fresh start on new version
                    cursor.execute("DELETE FROM usage_stats")
                
                # Always update stored base_version
                cursor.execute(
                    "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('base_version', ?)",
                    (current_ver,)
                )
                conn.commit()
            except Exception as e:
                logger.debug("Version reset check failed: %s", e)

    @staticmethod
    def _parse_version_parts(version_str: str) -> tuple:
        """Parse a version string like '3.0.7' into a tuple of ints (3, 0, 7)."""
        try:
            return tuple(int(p) if p.isdigit() else 0 for p in version_str.strip().split('.'))
        except (ValueError, AttributeError):
            return (0,)

    # ────────────────────────────────────────────────────────────────
    # TAB INPUTS — Per-tab form input values (replaces JSON files)
    # ────────────────────────────────────────────────────────────────

    def save_tab_input(self, tab_key: str, field_key: str, value: str):
        """Save a single tab input field to DB."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO tab_inputs (tab_key, field_key, value) VALUES (?, ?, ?)",
                    (tab_key, field_key, str(value) if value else "")
                )
                conn.commit()
            except Exception as e:
                logger.debug("save_tab_input failed: %s", e)

    def save_tab_inputs_batch(self, tab_key: str, data: dict):
        """Save multiple tab inputs at once."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                for k, v in data.items():
                    cursor.execute(
                        "INSERT OR REPLACE INTO tab_inputs (tab_key, field_key, value) VALUES (?, ?, ?)",
                        (tab_key, k, str(v) if v else "")
                    )
                conn.commit()
            except Exception as e:
                logger.debug("save_tab_inputs_batch failed: %s", e)

    def get_tab_inputs(self, tab_key: str) -> dict:
        """Get all saved inputs for a tab as a dict."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT field_key, value FROM tab_inputs WHERE tab_key = ?", (tab_key,))
                return dict(cursor.fetchall())
            except:
                return {}

    def get_tab_input(self, tab_key: str, field_key: str, default: str = "") -> str:
        """Get a single tab input value."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM tab_inputs WHERE tab_key = ? AND field_key = ?", (tab_key, field_key))
                row = cursor.fetchone()
                return row[0] if row else default
            except:
                return default

    def clear_tab_inputs(self, tab_key: str = None):
        """Clear inputs for a specific tab, or ALL if tab_key is None.
        
        Note: This method acquires self.lock. When calling from a method
        that already holds self.lock (e.g. clear_all_suggestions), use
        _clear_tab_inputs instead to avoid reentrant deadlock.
        """
        with self.lock:
            self._clear_tab_inputs(tab_key)

    def _clear_tab_inputs(self, tab_key: str = None):
        """Internal version — does NOT acquire lock (caller must hold it)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            if tab_key:
                cursor.execute("DELETE FROM tab_inputs WHERE tab_key = ?", (tab_key,))
            else:
                cursor.execute("DELETE FROM tab_inputs")
            conn.commit()
        except Exception as e:
            logger.debug("_clear_tab_inputs failed: %s", e)

    def get_tab_inputs_count(self, tab_key: str = None) -> int:
        """Count tab inputs (for a specific tab, or ALL)."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                if tab_key:
                    cursor.execute("SELECT COUNT(*) FROM tab_inputs WHERE tab_key = ?", (tab_key,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM tab_inputs")
                row = cursor.fetchone()
                return row[0] if row else 0
            except:
                return 0

    # ── Import legacy JSON files into tab_inputs table ──
    _TAB_INPUT_JSON_FILES = {
        "ekyc_report": "ekyc_inputs.json",
        "mr_tracking": "mr_tracking_inputs.json",
        "issued_mr_report": "issued_mr_report_inputs.json",
        "work_alloc": "work_alloc_inputs.json",
        "zero_mr": "zero_mr_inputs.json",
        "mis_reports": "mis_reports_inputs.json",
        "sad_update": "sad_update_inputs.json",
        "sad_auto": "sad_inputs.json",
        "scheme_closing": "scheme_closing_inputs.json",
        "mate_mr": "mate_mr_inputs.json",
        "muster": "muster_roll_inputs.json",
        "demand": "demand_inputs.json",
        "dashboard_report": "dashboard_report_inputs.json",
        "nmms": "nmms_inputs.json",
        "mr_fill": "mr_fill_inputs.json",
        "physical_complete": "physical_complete_inputs.json",
    }

    def _import_tab_inputs_from_json(self):
        """On first run with empty tab_inputs table, import existing JSON files."""
        if self.get_tab_inputs_count() > 0:
            return  # Already have data, skip import
        for tab_key, filename in self._TAB_INPUT_JSON_FILES.items():
            try:
                fp = self.data_path_func(filename)
                if not os.path.exists(fp):
                    continue
                with open(fp, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.save_tab_inputs_batch(tab_key, data)
                # Delete legacy JSON file — all tabs now use DB
                try:
                    if os.path.exists(fp):
                        os.remove(fp)
                        logger.debug("Deleted legacy JSON: %s", filename)
                except Exception as ex:
                    logger.debug("Could not delete legacy %s: %s", filename, ex)
            except Exception as e:
                logger.debug("Failed to import legacy %s: %s", filename, e)

    # --- Migration aur Suggestions ke purane functions (Same as before) ---
    def _migrate_activity_log_columns(self, cursor):
        """Add new columns to activity_log if they don't exist (SQLite migration)."""
        try:
            cursor.execute("PRAGMA table_info(activity_log)")
            existing = {row[1] for row in cursor.fetchall()}
            new_cols = {
                "automation_key": "TEXT DEFAULT ''",
                "panchayat": "TEXT DEFAULT ''",
                "village": "TEXT DEFAULT ''",
                "status": "TEXT DEFAULT ''",
                "duration_seconds": "REAL DEFAULT 0",
                "details": "TEXT DEFAULT ''",
                "synced": "INTEGER DEFAULT 0",   # 0=not synced, 1=synced to server
                # ── Error-diagnostics columns (admin Error Logs ke liye) ──
                # Inse pata chalta hai: kaunsa app version, kaunsa OS,
                # kaunsa error type, aur kis file:line:function me error aaya.
                "app_version": "TEXT DEFAULT ''",
                "os_platform": "TEXT DEFAULT ''",
                "error_type": "TEXT DEFAULT ''",
                "error_source": "TEXT DEFAULT ''",
                "error_traceback": "TEXT DEFAULT ''",
            }
            for col_name, col_type in new_cols.items():
                if col_name not in existing:
                    cursor.execute(f"ALTER TABLE activity_log ADD COLUMN {col_name} {col_type}")
        except Exception as e:
            logger.debug("Activity log column migration failed: %s", e)

    # --- Migration aur Suggestions ke purane functions (Same as before) ---
    def _migrate_from_json_if_needed(self):
        if os.path.exists(self.old_json_file):
            with self.lock:
                try:
                    conn = self._get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT count(*) FROM suggestions")
                    if cursor.fetchone()[0] == 0:
                        with open(self.old_json_file, 'r') as f: data = json.load(f)
                        for k, v in data.items():
                            if k == "_usage_stats": continue
                            if isinstance(v, list):
                                for val in v: cursor.execute("INSERT OR IGNORE INTO suggestions VALUES (?, ?)", (k, val))
                        if "_usage_stats" in data:
                            for k, v in data["_usage_stats"].items():
                                cursor.execute("INSERT OR IGNORE INTO usage_stats VALUES (?, ?)", (k, v))
                        conn.commit()
                        # ✅ Migration done — delete old JSON so it never re-populates
                        try:
                            os.remove(self.old_json_file)
                            logger.info("Purana autocomplete_history.json delete kar diya migration ke baad.")
                        except Exception as e:
                            logger.debug("Old JSON delete failed: %s", e)
                except Exception as e:
                    logger.debug("Migration from JSON failed: %s", e)

    def get_suggestions(self, field_key: str) -> list:
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM suggestions WHERE field_key = ? ORDER BY value ASC", (field_key,))
                rows = cursor.fetchall()
                return [row[0] for row in rows]
            except: return []

    def get_filtered_suggestions(self, field_key: str, parent_key: str, parent_value: str) -> list:
        """Get suggestions filtered by parent-child hierarchy.
        
        If hierarchy data exists for the given parent, returns only children
        that belong to that parent. Falls back to all suggestions if no
        hierarchy data is found.
        """
        if not parent_value:
            return self.get_suggestions(field_key)
        try:
            from src.location_hierarchy import get_hierarchy, HIERARCHY_TYPES, TYPE_TO_PREFIX
            # Determine parent type and child type from keys
            # field_key = "location_district", parent_key = "location_state"
            child_prefix = field_key.replace("location_", "").replace("mr_track_", "").replace("dashboard_", "").replace("mis_", "").replace("issued_mr_", "")
            parent_prefix = parent_key.replace("location_", "").replace("mr_track_", "").replace("dashboard_", "").replace("mis_", "").replace("issued_mr_", "")
            # Map prefixes to type names
            prefix_to_type = {v.lower(): k for k, v in TYPE_TO_PREFIX.items()}
            child_type = prefix_to_type.get(child_prefix, "")
            parent_type = prefix_to_type.get(parent_prefix, "")
            if child_type and parent_type:
                hier = get_hierarchy()
                children = hier.get_children(parent_type, parent_value, child_type)
                if children:
                    return children
        except Exception:
            pass
        return self.get_suggestions(field_key)

    def save_entry(self, field_key: str, value: str):
        if not value or not field_key: return 
        # Auto-uppercase panchayat, state, district, block keys for consistent display
        uppercase_keys = {
            # Shared location keys
            "location_panchayat", "location_state", "location_district", "location_block",
            "location_village",
            # Panchayat keys
            "panchayat_name", "panchayat", "dashboard_panchayat",
            "mr_track_panchayat", "issued_mr_panchayat", "audit_panchayat_respond",
            # State keys
            "mr_track_state", "issued_mr_state", "mis_state", "dashboard_state",
            # District keys
            "mr_track_district", "issued_mr_district", "mis_district", "dashboard_district",
            # Block keys
            "mr_track_block", "issued_mr_block", "mis_block", "dashboard_block",
        }
        if field_key in uppercase_keys:
            value = value.upper()
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO suggestions VALUES (?, ?)", (field_key, value))
                conn.commit()
            except Exception as e:
                logger.debug("History save_entry failed: %s", e)

    def remove_entry(self, field_key: str, value: str):
        if not value: return
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM suggestions WHERE field_key = ? AND value = ?", (field_key, value))
                conn.commit()
            except Exception as e:
                logger.debug("History remove_entry failed: %s", e)

    def increment_usage(self, automation_key: str):
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO usage_stats (automation_key, count) VALUES (?, 1) ON CONFLICT(automation_key) DO UPDATE SET count = count + 1", (automation_key,))
                conn.commit()
            except Exception as e:
                logger.debug("History increment_usage failed: %s", e)

    def get_most_used_keys(self, count: int = 5) -> list:
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT automation_key FROM usage_stats ORDER BY count DESC LIMIT ?", (count,))
                rows = cursor.fetchall()
                return [row[0] for row in rows]
            except:
                return []

    # ────────────────────────────────────────────────────────────────
    # STATISTICS & BULK CLEAR — for Settings "Clear History" tab
    # ────────────────────────────────────────────────────────────────
    def get_suggestions_count_by_key(self) -> Dict[str, int]:
        """Returns dict of field_key -> count of saved suggestions."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT field_key, COUNT(*) FROM suggestions GROUP BY field_key ORDER BY field_key")
                return dict(cursor.fetchall())
            except:
                return {}

    def get_total_suggestions_count(self) -> int:
        """Returns total number of saved suggestion entries."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM suggestions")
                row = cursor.fetchone()
                return row[0] if row else 0
            except:
                return 0

    def get_usage_stats_count(self) -> int:
        """Returns number of tracked usage stats entries."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM usage_stats")
                row = cursor.fetchone()
                return row[0] if row else 0
            except:
                return 0

    def get_usage_stats_all(self) -> Dict[str, int]:
        """Return ALL usage stats as {automation_key: count}.

        Used by the server telemetry sync (/api/usage-stats/sync) — the
        admin panel's Feature Popularity page ke liye. PII-free: sirf
        automation_key + count bheje jaate hain.
        """
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT automation_key, count FROM usage_stats")
                return {r[0]: r[1] for r in cursor.fetchall()}
            except Exception:
                return {}

    # ────────────────────────────────────────────────────────────────
    # SERVER SYNC — Feature popularity telemetry (usage_stats)
    # ────────────────────────────────────────────────────────────────

    def sync_usage_stats_to_server(self, license_key: str = "") -> int:
        """
        Local usage_stats (automation_key -> count) ko server par bhejo.

        Admin panel ki 'Feature Popularity' page isi se dikhti hai — kaunsa
        tab kitni baar use hua, kis state me, kis version me. Yeh sirf
        aggregated counts bhejta hai (PII-free) — koi panchayat/village/
        worker data nahi.

        Safe-by-design:
          - License key required (nahi to skip)
          - Background daemon thread me — UI kabhi block nahi
          - Server unreachable / 4xx-5xx → silent skip, next cycle retry
          - Kabhi raise nahi karta

        Returns number of features queued for sync (0 = nothing to sync).
        """
        if not license_key:
            return 0
        stats = self.get_usage_stats_all()
        if not stats:
            return 0

        from src.config import LICENSE_SERVER_URL
        server_url = LICENSE_SERVER_URL
        if not server_url:
            return 0

        def _do_sync():
            try:
                import requests as req_lib
                payload = {
                    "license_key": license_key,
                    "app_version": getattr(config, 'APP_VERSION', ''),
                    "stats": stats,
                }
                resp = req_lib.post(
                    f"{server_url}/api/usage-stats/sync",
                    json=payload,
                    timeout=15,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    logger.info("✅ Usage stats sync: %s features synced to server.",
                                result.get('synced_features', len(stats)))
                else:
                    logger.debug("⚠️ Usage stats sync: HTTP %s (%s)",
                                 resp.status_code, resp.text[:200])
            except Exception as e:
                logger.debug("⚠️ Usage stats sync failed (retry next cycle): %s", e)

        threading.Thread(target=_do_sync, daemon=True).start()
        return len(stats)

    def _delete_file_if_exists(self, filepath: str):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug("Deleted old file: %s", filepath)
        except Exception as e:
            logger.debug("Could not delete file %s: %s", filepath, e)


    def clear_suggestions_for_key(self, field_key: str) -> bool:
        """Delete suggestions for a specific field_key."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM suggestions WHERE field_key = ?", (field_key,))
                conn.commit()
                return True
            except Exception as e:
                logger.debug("clear_suggestions_for_key failed: %s", e)
                return False

    def clear_usage_stats(self) -> bool:
        """Delete all usage stats (resets 'Most Used' section)."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM usage_stats")
                conn.commit()
                return True
            except Exception as e:
                logger.debug("clear_usage_stats failed: %s", e)
                return False

    def clear_all_history(self) -> bool:
        """Delete ALL data: suggestions + usage stats + tab inputs."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM suggestions")
                cursor.execute("DELETE FROM usage_stats")
                conn.commit()
                # Clear tab inputs + delete legacy JSON files (caller holds lock, use _clear_tab_inputs)
                self._clear_tab_inputs()
                for filename in self._TAB_INPUT_JSON_FILES.values():
                    try:
                        fp = self.data_path_func(filename)
                        if os.path.exists(fp):
                            os.remove(fp)
                    except Exception:
                        pass
                self._delete_file_if_exists(self.old_json_file)
                return True
            except Exception as e:
                logger.debug("clear_all_history failed: %s", e)
                return False

    def get_db_file_path(self) -> str:
        return self.db_file

    # ────────────────────────────────────────────────────────────────
    # CLOUD BACKUP — export / import suggestions (user data sync)
    # ────────────────────────────────────────────────────────────────
    def export_all_suggestions(self) -> Dict[str, list]:
        """Return ALL suggestions grouped by field_key: {field_key: [values]}.

        Used by the cloud backup feature — this covers location data
        (state/district/block/panchayat/village) + autocomplete suggestions
        for every field. Usage stats / activity log are intentionally
        excluded (server sync already handles activity log separately).
        """
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT field_key, value FROM suggestions ORDER BY field_key, value")
                rows = cursor.fetchall()
                result: Dict[str, list] = {}
                for field_key, value in rows:
                    result.setdefault(field_key, []).append(value)
                return result
            except Exception as e:
                logger.error("export_all_suggestions failed: %s", e)
                return {}

    def import_all_suggestions(self, suggestions: Dict[str, list]) -> int:
        """Merge suggestions from a cloud backup into the local DB.

        Existing values are kept (INSERT OR IGNORE) so a restore never wipes
        newer local data. Returns the number of entries added.
        """
        if not suggestions or not isinstance(suggestions, dict):
            return 0
        added = 0
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                for field_key, values in suggestions.items():
                    if not isinstance(values, list):
                        continue
                    for value in values:
                        if not value:
                            continue
                        # Reuse save_entry logic (uppercase for location keys)
                        try:
                            cursor.execute("INSERT OR IGNORE INTO suggestions VALUES (?, ?)", (field_key, str(value)))
                            added += cursor.rowcount
                        except Exception:
                            continue
                conn.commit()
                return added
            except Exception as e:
                logger.error("import_all_suggestions failed: %s", e)
                return 0

    def export_tab_inputs(self) -> Dict[str, Dict[str, str]]:
        """Return all per-tab saved form inputs: {tab_key: {field_key: value}}."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT tab_key, field_key, value FROM tab_inputs ORDER BY tab_key, field_key")
                rows = cursor.fetchall()
                result: Dict[str, Dict[str, str]] = {}
                for tab_key, field_key, value in rows:
                    result.setdefault(tab_key, {})[field_key] = value
                return result
            except Exception as e:
                logger.error("export_tab_inputs failed: %s", e)
                return {}

    def import_tab_inputs(self, tab_inputs: Dict[str, Dict[str, str]]) -> int:
        """Merge per-tab form inputs from a cloud backup."""
        if not tab_inputs or not isinstance(tab_inputs, dict):
            return 0
        added = 0
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                for tab_key, fields in tab_inputs.items():
                    if not isinstance(fields, dict):
                        continue
                    for field_key, value in fields.items():
                        try:
                            cursor.execute(
                                "INSERT OR REPLACE INTO tab_inputs (tab_key, field_key, value) VALUES (?, ?, ?)",
                                (tab_key, field_key, str(value) if value else "")
                            )
                            added += 1
                        except Exception:
                            continue
                conn.commit()
                return added
            except Exception as e:
                logger.error("import_tab_inputs failed: %s", e)
                return 0

    def clear_all_suggestions(self) -> bool:
        """Delete all autocomplete suggestion entries + per-tab saved inputs."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM suggestions")
                conn.commit()
                # Clear tab inputs from DB (caller holds lock, use _clear_tab_inputs)
                self._clear_tab_inputs()
                # Delete legacy JSON files so they don't re-import on restart
                for filename in self._TAB_INPUT_JSON_FILES.values():
                    try:
                        fp = self.data_path_func(filename)
                        if os.path.exists(fp):
                            os.remove(fp)
                    except Exception:
                        pass
                # Delete old JSON to prevent re-population on restart
                self._delete_file_if_exists(self.old_json_file)
                return True
            except Exception as e:
                logger.debug("clear_all_suggestions failed: %s", e)
                return False

    def factory_reset(self) -> bool:
        """
        Full factory reset: clears ALL user data from the database
        (suggestions, usage_stats, tab_inputs, activity_log, app_meta)
        and deletes all legacy JSON files.
        
        Keeps the DB file itself (so tables/indices remain) but wipes
        all rows. This makes the app fresh like a new installation while
        preserving license.dat (activation) outside this method.
        """
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                # Clear all data tables
                cursor.execute("DELETE FROM suggestions")
                cursor.execute("DELETE FROM usage_stats")
                cursor.execute("DELETE FROM tab_inputs")
                cursor.execute("DELETE FROM activity_log")
                cursor.execute("DELETE FROM app_meta")
                conn.commit()
                
                # Delete legacy JSON input files
                for filename in self._TAB_INPUT_JSON_FILES.values():
                    try:
                        fp = self.data_path_func(filename)
                        if os.path.exists(fp):
                            os.remove(fp)
                            logger.debug("Factory reset deleted: %s", filename)
                    except Exception as e:
                        logger.debug("Could not delete %s: %s", filename, e)
                
                # Delete old autocomplete_history.json
                self._delete_file_if_exists(self.old_json_file)
                
                return True
            except Exception as e:
                logger.error("factory_reset failed: %s", e)
                return False

    # --- NEW: Logging Functions ---
    def log_activity(self, activity_type: str, description: str, automation_key: str = "app",
                     panchayat: str = "", village: str = "", details: str = ""):
        """Backward-compatible activity logger — routes through the structured
        logger so the admin panel / Activity Log never shows blank columns.

        The status is derived from the type (SUCCESS→success, WARNING→warning,
        ERROR→error) and the description is mirrored into the details column
        when no explicit details are given.
        """
        self.log_activity_structured(
            activity_type=activity_type,
            description=description,
            automation_key=automation_key or "app",
            panchayat=panchayat,
            village=village,
            status=activity_type.lower(),
            details=details or description,
        )

    def log_activity_structured(self, activity_type: str, description: str,
                                 automation_key: str = "", panchayat: str = "",
                                 village: str = "", status: str = "",
                                 duration_seconds: float = 0, details: str = "",
                                 error_type: str = "", error_source: str = "",
                                 error_traceback: str = ""):
        """
        Enhanced activity logging with structured fields.
        
        Args:
            activity_type: Type of activity (SUCCESS, ERROR, START, FINISH, etc.)
            description: Human-readable description
            automation_key: Which automation ran (e.g., 'demand', 'mb_entry')
            panchayat: Panchayat name (uppercase)
            village: Village name (uppercase)
            status: Status of the activity (running, success, failed, stopped)
            duration_seconds: How long the automation took
            details: Additional JSON-like details (work codes, counts, etc.)
            error_type: Exception type name (e.g. 'StaleElementReferenceException')
            error_source: 'file:line:function' chain where the error was raised
                — admin Error Logs me exactly pata chalta hai kis function se
                error aaya (debugging ke liye sabse useful field).
            error_traceback: Full exception traceback (capped ~4000 chars) —
                admin ko stack ka pura chain milta hai (conceptually 'file:line'
                se bhi aage jaakar saare frames).
        
        app_version aur os_platform apne aap fill hote hain (config se) taaki
        har entry bataye kaunsa app version / OS use ho raha tha.
        """
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # ── DPDP: log/store hone se pehle PII mask ──
                # Description/details/error strings me Aadhaar (12-digit),
                # mobile, IFSC numbers leak ho sakte hain (tabs jobcard/name
                # ke saath log karte hain). mask_pii_text inhe redact karta
                # hai — local SQLite bhi safe, server sync bhi safe.
                try:
                    from src.utils import mask_pii_text as _m
                    description = _m(description)
                    details = _m(details)
                    error_type = _m(error_type)
                    error_source = _m(error_source)
                    error_traceback = _m(error_traceback)
                except Exception:
                    pass

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                    INSERT INTO activity_log 
                        (timestamp, activity_type, description, automation_key,
                         panchayat, village, status, duration_seconds, details,
                         app_version, os_platform, error_type, error_source,
                         error_traceback)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (now, activity_type, description, automation_key,
                      panchayat, village, status, duration_seconds, details,
                      getattr(config, 'APP_VERSION', ''),
                      getattr(config, 'OS_SYSTEM', ''),
                      (error_type or '')[:255],
                      (error_source or '')[:500],
                      (error_traceback or '')[:4000]))
                
                # Auto-Cleanup: Keep last 2000 records
                cursor.execute("DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 2000)")
                
                conn.commit()
            except Exception as e:
                print(f"Log Error: {e}")

    def log_automation_start(self, automation_key: str, panchayat: str = "",
                              village: str = "", details: str = ""):
        """Log when an automation starts."""
        loc = " | ".join(x for x in (panchayat, village) if x)
        self.log_activity_structured(
            activity_type="START",
            description=f"Started {automation_key}{(' for ' + loc) if loc else ''}",
            automation_key=automation_key,
            panchayat=panchayat,
            village=village,
            status="running",
            duration_seconds=0,
            details=details
        )

    def log_automation_finish(self, automation_key: str, panchayat: str = "",
                               village: str = "", status: str = "success",
                               duration_seconds: float = 0, details: str = "",
                               error_type: str = "", error_source: str = "",
                               error_traceback: str = ""):
        """Log when an automation finishes.

        error_type / error_source sirf failed runs me bheje jaate hain —
        admin Error Logs ko batate hain ki exact exception kya tha aur
        kis file:line:function se aaya.
        """
        loc = " | ".join(x for x in (panchayat, village) if x)
        dur = f" ({duration_seconds:.0f}s)" if duration_seconds > 0 else ""
        self.log_activity_structured(
            activity_type="FINISH",
            description=f"{status.upper()}: {automation_key}{(' for ' + loc) if loc else ''}{dur}",
            automation_key=automation_key,
            panchayat=panchayat,
            village=village,
            status=status,
            duration_seconds=duration_seconds,
            details=details,
            error_type=error_type,
            error_source=error_source,
            error_traceback=error_traceback
        )

    def get_recent_activity(self, limit: int = 50) -> list:
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT timestamp, activity_type, description FROM activity_log ORDER BY id DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return rows
            except:
                return []

    def get_recent_activity_structured(self, limit: int = 50) -> list:
        """Get recent activity with all structured fields."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, timestamp, activity_type, description,
                           automation_key, panchayat, village, status,
                           duration_seconds, details
                    FROM activity_log
                    ORDER BY id DESC LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    result.append({
                        "id": row[0],
                        "timestamp": row[1],
                        "activity_type": row[2],
                        "description": row[3],
                        "automation_key": row[4] or "",
                        "panchayat": row[5] or "",
                        "village": row[6] or "",
                        "status": row[7] or "",
                        "duration_seconds": float(row[8] or 0),
                        "details": row[9] or "",
                    })
                return result
            except:
                return []

    def get_activity_summary_for_today(self) -> list:
        """Get today's automation activities as a summary list.
        Used for WhatsApp notification.
        """
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                today = datetime.now().strftime("%Y-%m-%d")
                cursor.execute('''
                    SELECT automation_key, panchayat, status, COUNT(*) as times,
                           ROUND(AVG(duration_seconds), 0) as avg_duration
                    FROM activity_log
                    WHERE timestamp LIKE ? AND activity_type = 'FINISH'
                    GROUP BY automation_key, panchayat, status
                    ORDER BY timestamp DESC
                ''', (f"{today}%",))
                rows = cursor.fetchall()
                return [{
                    "automation_key": r[0] or "",
                    "panchayat": r[1] or "",
                    "status": r[2] or "",
                    "count": r[3],
                    "avg_duration": float(r[4] or 0),
                } for r in rows]
            except:
                return []

    # ────────────────────────────────────────────────────────────────
    # SERVER SYNC — Phase 2: Send activity log to server
    # ────────────────────────────────────────────────────────────────

    def get_unsynced_entries(self, batch_size: int = 50) -> list:
        """Get entries that haven't been synced to the server yet."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, timestamp, activity_type, description,
                           automation_key, panchayat, village, status,
                           duration_seconds, details,
                           app_version, os_platform, error_type, error_source,
                           error_traceback
                    FROM activity_log
                    WHERE synced = 0
                    ORDER BY id ASC
                    LIMIT ?
                ''', (batch_size,))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    result.append({
                        "local_id": row[0],
                        "timestamp": row[1],
                        "activity_type": row[2],
                        "description": row[3],
                        # Backfill fallbacks so legacy rows (written before the
                        # structured columns existed) never sync as blank.
                        "automation_key": row[4] or "app",
                        "panchayat": row[5] or "",
                        "village": row[6] or "",
                        "status": row[7] or (row[2] or "").lower(),
                        "duration_seconds": float(row[8] or 0),
                        "details": row[9] or row[3] or "",
                        # Error-diagnostics — empty ho to legacy fallback
                        "app_version": row[10] or getattr(config, 'APP_VERSION', ''),
                        "os_platform": row[11] or getattr(config, 'OS_SYSTEM', ''),
                        "error_type": row[12] or "",
                        "error_source": row[13] or "",
                        "error_traceback": row[14] or "",
                    })
                return result
            except Exception as e:
                logger.debug("get_unsynced_entries failed: %s", e)
                return []

    def mark_entries_as_synced(self, local_ids: list) -> None:
        """Mark entries as synced after successful server upload."""
        if not local_ids:
            return
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(local_ids))
                cursor.execute(
                    f"UPDATE activity_log SET synced = 1 WHERE id IN ({placeholders})",
                    local_ids
                )
                conn.commit()
            except Exception as e:
                logger.debug("mark_entries_as_synced failed: %s", e)

    def sync_activity_log_to_server(self, license_key: str = "") -> int:
        """
        Sends unsynced activity log entries to the server.

        Args:
            license_key: User's license key (needed for server-side lookup).
                         Pass from app_automation.py where self.app_state.license_info is available.

        Returns the number of entries queued for sync (0 if nothing to sync
        or if sync is disabled).

        This method is safe to call from any thread — runs HTTP in a background
        daemon thread. Failed syncs are silently retried on next automation finish.
        """
        if not license_key:
            logger.debug("Activity log sync: No license key provided.")
            return 0

        from src.config import LICENSE_SERVER_URL
        server_url = LICENSE_SERVER_URL
        if not server_url:
            logger.debug("Activity log sync: No LICENSE_SERVER_URL configured.")
            return 0

        # Get unsynced entries
        entries = self.get_unsynced_entries(batch_size=50)
        if not entries:
            logger.debug("Activity log sync: No unsynced entries found.")
            return 0

        logger.info(f"Activity log sync: Attempting to sync {len(entries)} entries to {server_url}...")

        import threading
        def _do_sync():
            try:
                import requests as req_lib

                payload = {
                    "license_key": license_key,
                    "app_version": config.APP_VERSION,
                    "entries": entries,
                }

                resp = req_lib.post(
                    f"{server_url}/api/activity-log/sync",
                    json=payload,
                    timeout=15,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    synced_count = result.get('synced_count', 0)
                    if synced_count > 0:
                        local_ids = [e['local_id'] for e in entries[:synced_count]]
                        self.mark_entries_as_synced(local_ids)
                        logger.info(f"✅ Activity log sync: {synced_count} entries synced successfully to server.")
                    else:
                        logger.warning(f"⚠️ Activity log sync: Server returned synced_count=0 for {len(entries)} entries.")
                else:
                    logger.warning(f"⚠️ Activity log sync: Server returned HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"⚠️ Activity log sync failed (will retry on next automation finish): {e}")

        threading.Thread(target=_do_sync, daemon=True).start()
        return len(entries)