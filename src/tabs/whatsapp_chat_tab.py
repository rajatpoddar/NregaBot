# tabs/whatsapp_chat_tab.py
"""
WhatsApp Chat Tab — Modern Chat UI.

Users send messages that are forwarded to admin's WhatsApp via OpenWA.
Admin replies from WhatsApp, replies come back via webhook.

Uses config.LICENSE_SERVER_URL which can be overridden via env variable:
    LICENSE_SERVER_URL=http://localhost:8000 python main_app.py
"""
import tkinter
from tkinter import messagebox
import customtkinter as ctk
import requests
from src import config
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ──
WHATSAPP_GREEN = "#25D366"
WHATSAPP_DARK = "#075E54"
WHATSAPP_DARK_ALT = "#004D4A"
# (light_bg, dark_bg) tuples for theme-aware coloring
BUBBLE_USER_COLOR = ("#DCF8C6", "#054D44")
BUBBLE_ADMIN_COLOR = ("#FFFFFF", "#2B2B2B")
BUBBLE_BG = ("#ECE5DD", "#111B21")


class WhatsAppChatTab(ctk.CTkFrame):
    """WhatsApp-style chat tab with support."""

    POLL_INTERVAL_MS = 3000

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.poll_after_id = None
        self.last_message_id = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Outer card ──
        self.card = ctk.CTkFrame(self, corner_radius=12)
        self.card.grid(row=0, column=0, padx=20, pady=15, sticky="nsew")
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_rowconfigure(1, weight=1)

        # ── Header ──
        self._build_header()

        # Track whether empty state is showing
        self._showing_empty = False

        # ── Chat area ──
        self.chat_frame = ctk.CTkScrollableFrame(
            self.card, corner_radius=0,
            fg_color=BUBBLE_BG,
        )
        self.chat_frame.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # ── Input area ──
        self._build_input()

        # Start polling
        self.after(500, self.load_messages)

    # ── Build Header ──────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self.card, fg_color=WHATSAPP_DARK, height=64)
        header.grid(row=0, column=0, padx=0, pady=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        # Avatar circle
        avatar_canvas = tkinter.Canvas(
            header, width=42, height=42, highlightthickness=0,
            bg=WHATSAPP_DARK, bd=0
        )
        avatar_canvas.grid(row=0, column=0, padx=(14, 10), pady=11)
        avatar_canvas.create_oval(2, 2, 40, 40, fill="#34B7F1", outline="")
        avatar_canvas.create_text(21, 22, text="S", fill="white",
                                  font=("Segoe UI", 18, "bold"))

        # Title
        ctk.CTkLabel(
            header, text="Support Chat",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white"
        ).grid(row=0, column=1, sticky="w")

        self.status_label = ctk.CTkLabel(
            header, text="🟢 Online",
            font=ctk.CTkFont(size=10),
            text_color="#A8D8EA"
        )
        self.status_label.grid(row=0, column=2, padx=(0, 14), sticky="e")

    # ── Build Input ───────────────────────────────────────────
    def _build_input(self):
        input_bg = ctk.CTkFrame(self.card, fg_color=("#F0F0F0", "#1F2C33"),
                                 height=60)
        input_bg.grid(row=2, column=0, padx=0, pady=0, sticky="ew")
        input_bg.grid_columnconfigure(0, weight=1)
        input_bg.grid_propagate(False)

        self.message_entry = ctk.CTkEntry(
            input_bg,
            placeholder_text="Type a message",
            height=40,
            corner_radius=20,
            border_width=0,
            fg_color=("#FFFFFF", "#2A3942"),
            text_color=("#111111", "#E9EDEF"),
            placeholder_text_color=("#8696A0", "#8696A0")
        )
        self.message_entry.grid(row=0, column=0, padx=(12, 8), pady=10, sticky="ew")
        self.message_entry.bind("<Return>", self.send_message)
        self.message_entry.bind("<KeyRelease>", self._on_typing)

        self.send_button = ctk.CTkButton(
            input_bg,
            text="➤",
            width=44,
            height=40,
            corner_radius=22,
            fg_color=WHATSAPP_GREEN,
            hover_color="#20BD5E",
            text_color="white",
            font=ctk.CTkFont(size=18),
            command=self.send_message
        )
        self.send_button.grid(row=0, column=1, padx=(0, 12), pady=10)

        # Sound toggle indicator
        self.sound_indicator = ctk.CTkLabel(
            input_bg, text="🔔", font=ctk.CTkFont(size=9),
            text_color=("#8696A0", "#8696A0")
        )
        self.sound_indicator.grid(row=1, column=0, padx=(16, 0), pady=(0, 2), sticky="w")

    def _on_typing(self, event=None):
        txt = self.message_entry.get().strip()
        if txt:
            self.sound_indicator.configure(text="Press Enter to send")
        else:
            self.sound_indicator.configure(text="🔔 Notification on reply")

    # ── Send Message ──────────────────────────────────────────
    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if not message:
            return

        original_text = message
        self.message_entry.delete(0, "end")
        self.sound_indicator.configure(text="")

        self.send_button.configure(state="disabled", text="⏳")
        self.message_entry.configure(state="disabled")

        threading.Thread(
            target=self._send_worker,
            args=(message, original_text),
            daemon=True
        ).start()

    def _send_worker(self, message: str, original_text: str):
        success = False
        error_reason = "An unknown error occurred."
        try:
            headers = {'Authorization': f'Bearer {self.app.license_info.get("key")}'}
            response = self.app.http_session.post(
                f"{config.LICENSE_SERVER_URL}/api/whatsapp-chat/send",
                json={"message": message},
                headers=headers,
                timeout=15
            )
            if response.status_code in (200, 201):
                success = True
            else:
                try:
                    data = response.json()
                    error_reason = data.get('reason', 'Failed to send message.')
                except Exception:
                    error_reason = f"Server error ({response.status_code})"
        except requests.exceptions.ConnectionError:
            error_reason = "Cannot connect to server. Check your internet."
        except requests.exceptions.Timeout:
            error_reason = "Server is not responding. Try again."
        except Exception as e:
            error_reason = str(e)

        self.app.after(0, self._on_send_complete, success, error_reason, original_text)

    def _on_send_complete(self, success: bool, reason: str, original_text: str):
        self.message_entry.configure(state="normal")
        self.send_button.configure(state="normal", text="➤")

        if success:
            self.status_label.configure(text="🟢 Online")
            self.load_messages()
        else:
            self.status_label.configure(text="🔴 Error")
            messagebox.showerror(
                "Send Failed",
                f"Could not send message.\n\nReason: {reason}\n\n"
                f"💡 Tip: For local testing, run:\n"
                f"LICENSE_SERVER_URL=http://localhost:8000 python main_app.py"
            )
            self.message_entry.insert(0, original_text)

    # ── Load Messages ─────────────────────────────────────────
    def load_messages(self):
        if self.poll_after_id:
            self.app.after_cancel(self.poll_after_id)
            self.poll_after_id = None

        if not self.chat_frame.winfo_children():
            self._show_empty_state()

        threading.Thread(target=self._load_worker, daemon=True).start()

    def _show_empty_state(self):
        self._showing_empty = True
        for w in self.chat_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.chat_frame,
            text="💬 No messages yet",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("#667781", "#8696A0")
        ).pack(pady=(60, 5))
        ctk.CTkLabel(
            self.chat_frame,
            text="Send a message to start the conversation!",
            font=ctk.CTkFont(size=12),
            text_color=("#8696A0", "#8696A0")
        ).pack(pady=(0, 5))

    def _load_worker(self):
        try:
            headers = {'Authorization': f'Bearer {self.app.license_info.get("key")}'}
            response = self.app.http_session.get(
                f"{config.LICENSE_SERVER_URL}/api/whatsapp-chat/messages?since_id={self.last_message_id}",
                headers=headers,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    msgs = data.get("messages", [])
                    if msgs:
                        self.app.after(0, self._display_messages, msgs)
            elif response.status_code == 404:
                self.app.after(0, self._show_migration_needed)
        except requests.exceptions.ConnectionError:
            self.app.after(0, self._show_offline)
        except Exception:
            pass
        finally:
            self.poll_after_id = self.app.after(self.POLL_INTERVAL_MS, self.load_messages)

    def _show_migration_needed(self):
        for w in self.chat_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.chat_frame,
            text="🚧 Server update needed",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=("#E74C3C", "#E74C3C")
        ).pack(pady=(60, 5))
        ctk.CTkLabel(
            self.chat_frame,
            text="The server needs to be updated with the new chat system.\n"
                 "Please restart the server or deploy the latest code.",
            font=ctk.CTkFont(size=12),
            text_color=("#8696A0", "#8696A0"),
            justify="center"
        ).pack(pady=(0, 5))

    def _show_offline(self):
        if not self.chat_frame.winfo_children():
            self._show_empty_state()

    # ── Display Messages ──────────────────────────────────────
    def _display_messages(self, messages: List[Dict]):
        # Clear empty state if it's showing
        if self._showing_empty:
            self._showing_empty = False
            for w in self.chat_frame.winfo_children():
                w.destroy()

        has_new_admin_msg = False
        for msg in messages:
            self._append_message(msg)
            if msg.get('sender') == 'admin':
                has_new_admin_msg = True

        # Play notification sound when a new admin reply arrives
        if has_new_admin_msg:
            try:
                if hasattr(self.app, 'sound_manager') and self.app.sound_manager:
                    self.app.sound_manager.play("notification")
            except Exception:
                pass

        # Auto-scroll to bottom
        self.after(100, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        try:
            canvas = self.chat_frame._parent_canvas
            canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _append_message(self, msg: Dict):
        msg_id = msg.get('id', 0)
        sender = msg.get('sender', 'user')
        text = msg.get('message', '')
        created = msg.get('created_at', '')

        if msg_id > self.last_message_id:
            self.last_message_id = msg_id

        is_admin = sender == 'admin'

        # Container for this message
        row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(2, 0))
        row.grid_columnconfigure(0, weight=1)

        if is_admin:
            # ── Admin / Support bubble (left) ──
            label_frame = ctk.CTkFrame(
                row, fg_color=BUBBLE_ADMIN_COLOR,
                corner_radius=8
            )
            # Round corners: top-left, top-right, bottom-right = 8; bottom-left = 2
            label_frame.pack(anchor="w", padx=(4, 60), pady=3)

            ctk.CTkLabel(
                label_frame,
                text="👨‍💼 Support",
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color=("#075E54", "#25D366")
            ).pack(anchor="w", padx=10, pady=(6, 0))

            ctk.CTkLabel(
                label_frame,
                text=text,
                wraplength=380,
                justify="left",
                font=ctk.CTkFont(size=13),
                text_color=("#303030", "#E9EDEF")
            ).pack(anchor="w", padx=10, pady=(1, 2))

            if created:
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    time_str = dt.strftime("%I:%M %p")
                except Exception:
                    time_str = ""
                ctk.CTkLabel(
                    label_frame,
                    text=time_str,
                    font=ctk.CTkFont(size=9),
                    text_color=("#8696A0", "#8696A0")
                ).pack(anchor="w", padx=10, pady=(0, 6))

        else:
            # ── User bubble (right, WhatsApp green) ──
            label_frame = ctk.CTkFrame(
                row, fg_color=BUBBLE_USER_COLOR,
                corner_radius=8
            )
            label_frame.pack(anchor="e", padx=(60, 4), pady=3)

            ctk.CTkLabel(
                label_frame,
                text="👤 You",
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color=("#1B5E20", "#4ADE80")
            ).pack(anchor="e", padx=10, pady=(6, 0))

            ctk.CTkLabel(
                label_frame,
                text=text,
                wraplength=380,
                justify="left",
                font=ctk.CTkFont(size=13),
                text_color=("#303030", "#E9EDEF")
            ).pack(anchor="e", padx=10, pady=(1, 2))

            if created:
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    time_str = dt.strftime("%I:%M %p")
                except Exception:
                    time_str = ""
                ctk.CTkLabel(
                    label_frame,
                    text=time_str + " ✓✓",
                    font=ctk.CTkFont(size=9),
                    text_color=("#8696A0", "#4ADE80")
                ).pack(anchor="e", padx=10, pady=(0, 6))

    # ── Cleanup ───────────────────────────────────────────────
    def destroy(self):
        if self.poll_after_id:
            self.app.after_cancel(self.poll_after_id)
        super().destroy()
