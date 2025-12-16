# tabs/history_manager.py
import sqlite3
import json
import os
import threading
from datetime import datetime  # <-- Time save karne ke liye ye zaroori hai

class HistoryManager:
    def __init__(self, data_path_func):
        self.db_file = data_path_func('nrega_local_db.sqlite')
        self.old_json_file = data_path_func('autocomplete_history.json')
        self.lock = threading.Lock()
        
        self._init_db()
        self._migrate_from_json_if_needed()

    def _get_connection(self):
        """Creates a database connection."""
        conn = sqlite3.connect(self.db_file, check_same_thread=False)
        return conn

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
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Database Init Error: {e}")

    # --- Migration aur Suggestions ke purane functions (Same as before) ---
    def _migrate_from_json_if_needed(self):
        if os.path.exists(self.old_json_file):
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM suggestions")
            if cursor.fetchone()[0] == 0:
                try:
                    with open(self.old_json_file, 'r') as f: data = json.load(f)
                    for k, v in data.items():
                        if k == "_usage_stats": continue
                        if isinstance(v, list):
                            for val in v: cursor.execute("INSERT OR IGNORE INTO suggestions VALUES (?, ?)", (k, val))
                    if "_usage_stats" in data:
                        for k, v in data["_usage_stats"].items():
                            cursor.execute("INSERT OR IGNORE INTO usage_stats VALUES (?, ?)", (k, v))
                    conn.commit()
                except Exception: pass
            conn.close()

    def get_suggestions(self, field_key: str) -> list:
        try:
            conn = self._get_connection(); cursor = conn.cursor()
            cursor.execute("SELECT value FROM suggestions WHERE field_key = ? ORDER BY value ASC", (field_key,))
            rows = cursor.fetchall(); conn.close()
            return [row[0] for row in rows]
        except: return []

    def save_entry(self, field_key: str, value: str):
        if not value or not field_key: return 
        with self.lock:
            try:
                conn = self._get_connection(); cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO suggestions VALUES (?, ?)", (field_key, value))
                conn.commit(); conn.close()
            except: pass

    def remove_entry(self, field_key: str, value: str):
        if not value: return
        with self.lock:
            try:
                conn = self._get_connection(); cursor = conn.cursor()
                cursor.execute("DELETE FROM suggestions WHERE field_key = ? AND value = ?", (field_key, value))
                conn.commit(); conn.close()
            except: pass

    def increment_usage(self, automation_key: str):
        with self.lock:
            try:
                conn = self._get_connection(); cursor = conn.cursor()
                cursor.execute("INSERT INTO usage_stats (automation_key, count) VALUES (?, 1) ON CONFLICT(automation_key) DO UPDATE SET count = count + 1", (automation_key,))
                conn.commit(); conn.close()
            except: pass

    def get_most_used_keys(self, count: int = 5) -> list:
        try:
            conn = self._get_connection(); cursor = conn.cursor()
            cursor.execute("SELECT automation_key FROM usage_stats ORDER BY count DESC LIMIT ?", (count,))
            rows = cursor.fetchall(); conn.close()
            return [row[0] for row in rows]
        except: return []

    # --- NEW: Logging Functions (Magic starts here) ---
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
                conn.close()
            except Exception as e:
                print(f"Log Error: {e}")

    def get_recent_activity(self, limit: int = 50) -> list:
        """UI me dikhane ke liye recent data lata hai."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, activity_type, description FROM activity_log ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except: return []