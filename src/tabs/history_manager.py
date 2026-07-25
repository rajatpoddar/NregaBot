# tabs/history_manager.py
import sqlite3
import json
import os
import threading
from datetime import datetime  # <-- Time save karne ke liye ye zaroori hai
from src import config  # For APP_VERSION — auto-reset usage stats on version change
from src.utils import get_logger
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = get_logger()

class HistoryManager:
    def __init__(self, data_path_func):
        self.db_file = data_path_func('nrega_local_db.sqlite')
        self.old_json_file = data_path_func('autocomplete_history.json')
        self.lock = threading.Lock()
        self._conn = None  # Persistent connection (lazy init)
        
        self._init_db()
        self._migrate_from_json_if_needed()
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
        """Tables create karta hai."""
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

                # --- NEW TABLE: Activity Log (Ye naya hai) ---
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        activity_type TEXT,
                        description TEXT
                    )
                ''')
                
                # Table 3: App Meta for version tracking
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS app_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                
                conn.commit()
            except Exception as e:
                logger.error("Database Init Error: %s", e)

    def _check_version_reset(self):
        """
        On every app launch, check if the app version has changed.
        If so, reset usage_stats so that the 'Most Used' section starts
        fresh for the new version. This prevents stale historical data
        from previous versions dominating the top-used list.
        """
        current_ver = config.APP_VERSION
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM app_meta WHERE key = 'app_version'")
                row = cursor.fetchone()
                stored_ver = row[0] if row else None
                
                if stored_ver != current_ver:
                    # Version changed (or first launch) — reset usage stats
                    cursor.execute("DELETE FROM usage_stats")
                    cursor.execute(
                        "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('app_version', ?)",
                        (current_ver,)
                    )
                    conn.commit()
            except Exception as e:
                logger.debug("Version reset check failed: %s", e)

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

    def save_entry(self, field_key: str, value: str):
        if not value or not field_key: return 
        # Auto-uppercase panchayat, state, district, block keys for consistent display
        uppercase_keys = {
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

    # --- NEW: Logging Functions ---
    def log_activity(self, activity_type: str, description: str):
        """Current time ke saath activity save karta hai."""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO activity_log (timestamp, activity_type, description) VALUES (?, ?, ?)", 
                               (now, activity_type, description))
                
                # Auto-Cleanup: Sirf last 1000 records rakho taaki DB heavy na ho
                cursor.execute("DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 1000)")
                
                conn.commit()
            except Exception as e:
                print(f"Log Error: {e}")

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