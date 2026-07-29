# tabs/activity_log_tab.py
"""
Activity Log Tab — Shows user's automation activity history.

Displays structured activity log from history_manager.get_recent_activity_structured()
with color-coded status badges, panchayat filter, and clear functionality.
"""

from tkinter import ttk, messagebox
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import customtkinter as ctk

from src.utils import get_logger

logger = get_logger()


class ActivityLogTab(ctk.CTkFrame):
    """Activity Log viewer — embedded in Settings tab."""

    # Status colors (light, dark)
    STATUS_COLORS = {
        "success": ("#16A34A", "#4ADE80"),
        "failed":  ("#DC2626", "#F87171"),
        "stopped": ("#D97706", "#FBBF24"),
        "running": ("#3B82F6", "#60A5FA"),
        "":        ("gray50",  "gray60"),
    }

    # Mapping: status value → display text
    STATUS_LABELS = {
        "success": "✅ Success",
        "failed":  "❌ Failed",
        "stopped": "⏹️ Stopped",
        "running": "🔄 Running",
        "":        "—",
    }

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self._refresh_in_progress = False  # Prevent re-entrant calls

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_filters()
        self._build_table()
        self.after(100, self._refresh_log)  # Delay initial load to let UI settle

    # ── Header ────────────────────────────────────────────────────
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="📋", font=ctk.CTkFont(size=24)
                     ).grid(row=0, column=0, padx=(0, 10))

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(title_frame, text="Activity Log",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame,
                     text="Aapke saare automations ka record — kab, kaunsa, kya result aaya",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).pack(anchor="w")

        # Count badge
        self._count_label = ctk.CTkLabel(header, text="",
                                          font=ctk.CTkFont(size=12),
                                          text_color=("gray50", "gray60"))
        self._count_label.grid(row=0, column=2, sticky="e", padx=(10, 0))

    # ── Filters ───────────────────────────────────────────────────
    def _build_filters(self) -> None:
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        filter_frame.grid_columnconfigure(2, weight=1)

        # Automation type filter
        ctk.CTkLabel(filter_frame, text="Filter:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        self._filter_var = ctk.StringVar(value="All")
        self._filter_menu = ctk.CTkOptionMenu(
            filter_frame,
            variable=self._filter_var,
            values=["All", "Success", "Failed", "Stopped"],
            width=120, height=28,
            command=lambda _: self._refresh_log(),
        )
        self._filter_menu.grid(row=0, column=1, sticky="w", padx=(0, 15))

        # Panchayat filter
        self._panchayat_var = ctk.StringVar(value="All Panchayats")
        self._panchayat_menu = ctk.CTkOptionMenu(
            filter_frame,
            variable=self._panchayat_var,
            values=["All Panchayats"],
            width=160, height=28,
            command=lambda _: self._safe_refresh(),
        )
        self._panchayat_menu.grid(row=0, column=2, sticky="w", padx=(0, 15))

        # Action buttons
        self._refresh_btn = ctk.CTkButton(
            filter_frame, text="🔄 Refresh", width=90, height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#E2E8F0", "#334155"),
            text_color=("#1E293B", "#F1F5F9"),
            hover_color=("#CBD5E1", "#475569"),
            command=self._refresh_log,
        )
        self._refresh_btn.grid(row=0, column=3, sticky="e", padx=(5, 5))

        self._clear_btn = ctk.CTkButton(
            filter_frame, text="🗑 Clear Logs", width=110, height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#DC2626", "#EF4444"),
            text_color="white",
            hover_color=("#B91C1C", "#DC2626"),
            command=self.clear_logs,
        )
        self._clear_btn.grid(row=0, column=4, sticky="e")

    # ── Table ─────────────────────────────────────────────────────
    def _build_table(self) -> None:
        """Build the Treeview with color-coded rows."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        columns = ("time", "automation", "panchayat", "duration", "status", "details")
        self._tree = ttk.Treeview(
            container, columns=columns, show="headings",
            selectmode="browse",
        )
        self._tree.grid(row=0, column=0, sticky="nsew")

        # Column config
        col_configs = {
            "time":       ("Time",       160, "w"),
            "automation": ("Automation", 180, "w"),
            "panchayat":  ("Panchayat",  160, "w"),
            "duration":   ("Duration",   100, "center"),
            "status":     ("Status",     130, "center"),
            "details":    ("Details",    300, "w"),
        }
        for col_id, (text, width, anchor) in col_configs.items():
            self._tree.heading(col_id, text=text, anchor=anchor)
            self._tree.column(col_id, width=width, minwidth=80, anchor=anchor)

        # Scrollbar
        vs = ttk.Scrollbar(container, orient="vertical", command=self._tree.yview)
        vs.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=vs.set)

        # Tags for status coloring
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self._tree.tag_configure("success", background="#14532D", foreground="#4ADE80")
            self._tree.tag_configure("failed",  background="#450A0A", foreground="#F87171")
            self._tree.tag_configure("stopped", background="#422006", foreground="#FBBF24")
            self._tree.tag_configure("running", background="#1E3A5F", foreground="#60A5FA")
            self._tree.tag_configure("group_header", background="#1E293B", foreground="#94A3B8", font=("Segoe UI", 10, "bold"))
        else:
            self._tree.tag_configure("success", background="#DCFCE7", foreground="#166534")
            self._tree.tag_configure("failed",  background="#FEE2E2", foreground="#991B1B")
            self._tree.tag_configure("stopped", background="#FEF9C3", foreground="#854D0E")
            self._tree.tag_configure("running", background="#DBEAFE", foreground="#1E40AF")
            self._tree.tag_configure("group_header", background="#F1F5F9", foreground="#64748B", font=("Segoe UI", 10, "bold"))

        # No sort-on-click — grouped data doesn't sort well by column.
        # Default ordering: newest activities first within each date group.

    # ── Refresh ───────────────────────────────────────────────────
    def _safe_refresh(self) -> None:
        """Wrapper to prevent re-entrant calls via OptionMenu callbacks."""
        if not self._refresh_in_progress:
            self._refresh_log()

    def _refresh_log(self) -> None:
        """Load and display activity log from history_manager with date groupings."""
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        try:
            # Clear existing rows
            for item in self._tree.get_children():
                self._tree.delete(item)

            hm = self.app.history_manager
            try:
                activities = hm.get_recent_activity_structured(limit=500)
            except Exception as e:
                logger.debug("Failed to load activity log: %s", e)
                activities = []

            if not activities:
                self._count_label.configure(text="📭 No activity recorded yet")
                return

            # Get filter values
            status_filter = self._filter_var.get().lower()
            panch_filter = self._panchayat_var.get().strip()

            # Build panchayat filter options
            panchayats = set()
            for a in activities:
                p = (a.get("panchayat") or "").strip()
                if p:
                    panchayats.add(p)

            current_panch_vals = ["All Panchayats"] + sorted(panchayats)
            if self._panchayat_menu.cget("values") != current_panch_vals:
                self._panchayat_menu.configure(values=current_panch_vals)
                if self._panchayat_var.get() not in current_panch_vals:
                    self._panchayat_var.set("All Panchayats")

            # ── Date Grouping ──
            today = datetime.now().date()
            groups = {
                "today":     {"label": "📅 Today",       "rows": []},
                "yesterday": {"label": "📅 Yesterday",   "rows": []},
                "this_week": {"label": "📅 This Week",   "rows": []},
                "this_month":{"label": "📅 This Month",  "rows": []},
                "older":     {"label": "📅 Older",       "rows": []},
            }

            # Filter and group
            for a in activities:
                status = (a.get("status") or "").lower()
                if status_filter != "all" and status != status_filter:
                    continue

                panch = (a.get("panchayat") or "").strip()
                if panch_filter and panch_filter != "All Panchayats":
                    if panch != panch_filter:
                        continue

                # Determine date group
                raw_ts = a.get("timestamp") or ""
                try:
                    if "T" in raw_ts:
                        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                    elif " " in raw_ts and len(raw_ts) >= 10:
                        dt = datetime.strptime(raw_ts[:10], "%Y-%m-%d")
                    else:
                        groups["older"]["rows"].append(a)
                        continue

                    diff = (today - dt.date()).days
                    if diff == 0:
                        groups["today"]["rows"].append(a)
                    elif diff == 1:
                        groups["yesterday"]["rows"].append(a)
                    elif diff <= 7:
                        groups["this_week"]["rows"].append(a)
                    elif diff <= 30:
                        groups["this_month"]["rows"].append(a)
                    else:
                        groups["older"]["rows"].append(a)
                except Exception:
                    groups["older"]["rows"].append(a)

            # Render groups
            displayed = 0
            for group_key in ["today", "yesterday", "this_week", "this_month", "older"]:
                group = groups[group_key]
                if not group["rows"]:
                    continue

                # Insert group header (not selectable, visual only)
                group_count = len(group["rows"])
                group_count_s = sum(1 for r in group["rows"] if (r.get("status") or "").lower() == "success")
                group_count_f = sum(1 for r in group["rows"] if (r.get("status") or "").lower() == "failed")
                group_header_text = f"{group['label']}  ({group_count} activities"
                if group_count_s:
                    group_header_text += f"  ✅ {group_count_s}"
                if group_count_f:
                    group_header_text += f"  ❌ {group_count_f}"
                group_header_text += ")"

                group_item = self._tree.insert("", "end", values=(
                    "", group_header_text, "", "", "", ""
                ), tags=("group_header",))

                # Reverse rows so oldest activity appears first within each group
                for a in reversed(group["rows"]):
                    raw_ts = a.get("timestamp") or ""
                    formatted_ts = self._format_timestamp(raw_ts)

                    auto_key = a.get("automation_key") or ""
                    auto_display = auto_key.replace("_", " ").title() if auto_key else (a.get("activity_type") or "—")

                    panch_display = (a.get("panchayat") or "").strip()
                    panch_display = panch_display if panch_display else "—"

                    dur = a.get("duration_seconds") or 0
                    if dur <= 0:
                        dur_display = "—"
                    elif dur < 60:
                        dur_display = f"{dur:.0f}s"
                    elif dur < 3600:
                        dur_display = f"{dur/60:.1f}m"
                    else:
                        dur_display = f"{dur/3600:.1f}h"

                    status_val = (a.get("status") or "").lower()
                    status_label = self.STATUS_LABELS.get(status_val, status_val.title() if status_val else "—")

                    # Richer details: combine description + details
                    desc = (a.get("description") or "")
                    det = (a.get("details") or "")
                    if desc and det:
                        details = f"{desc} | {det}"
                    else:
                        details = desc or det or ""

                    # Determine tag for coloring
                    tag = status_val if status_val in ("success", "failed", "stopped", "running") else ""

                    self._tree.insert(group_item, "end", values=(
                        formatted_ts, auto_display, panch_display,
                        dur_display, status_label, details
                    ), tags=(tag,) if tag else ())
                    displayed += 1

            self._count_label.configure(text=f"📊 {displayed}/{len(activities)} activities")
        finally:
            self._refresh_in_progress = False

    # ── Clear Logs ────────────────────────────────────────────────
    def clear_logs(self) -> None:
        """
        Clear all activity log entries from the database after confirmation.
        
        Standardized name matching other tabs — replaces legacy _clear_log().
        """
        if not messagebox.askyesno(
            "Clear Activity Log",
            "Kya aap saari activity history delete karna chahte hain?\n\n"
            "Yeh action wapas nahi laaya ja sakta.",
            icon="warning",
            parent=self.winfo_toplevel()
        ):
            return

        hm = self.app.history_manager
        try:
            conn = hm._get_connection()
            with hm.lock:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM activity_log")
                conn.commit()
            self._refresh_log()
            messagebox.showinfo("Cleared", "Activity log clear ho gaya.", parent=self.winfo_toplevel())
        except Exception as e:
            logger.error("Failed to clear activity log: %s", e)
            messagebox.showerror("Error", f"Clear failed: {e}", parent=self.winfo_toplevel())

    # ── Helpers ────────────────────────────────────────────────────
    @staticmethod
    def _format_timestamp(raw: str) -> str:
        """Format ISO timestamp to readable format."""
        if not raw:
            return "—"
        try:
            if "T" in raw:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            elif " " in raw and len(raw) == 19:
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            else:
                return raw[:16]
            return dt.strftime("%d-%b %I:%M %p")
        except (ValueError, TypeError):
            return raw[:16] if len(raw) > 16 else raw
