# tabs/feedback_tab.py
import tkinter
from tkinter import messagebox
import customtkinter as ctk
import requests
import config
import threading

class FeedbackTab(ctk.CTkFrame):
    """A tab for users to chat with support."""
    def __init__(self, parent, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.poll_after_id = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.main_frame, text="Support Chat", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Chat display area
        self.chat_scrollable_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="Conversation History")
        self.chat_scrollable_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.chat_scrollable_frame.grid_columnconfigure(0, weight=1)

        # Message input area
        self.input_frame = ctk.CTkFrame(self.main_frame)
        self.input_frame.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.message_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type your message here...")
        self.message_entry.grid(row=0, column=0, padx=(10, 10), pady=10, sticky="ew")
        self.message_entry.bind("<Return>", self.send_message)

        self.send_button = ctk.CTkButton(self.input_frame, text="Send", command=self.send_message, width=80)
        self.send_button.grid(row=0, column=1, padx=(0, 10), pady=10)

        self.load_conversation()

    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if not message:
            return

        # Store the original message text and clear the input field immediately
        original_message_text = self.message_entry.get()
        self.message_entry.delete(0, "end")

        # Disable UI elements to prevent further actions while sending
        self.send_button.configure(state="disabled", text="Sending...")
        self.message_entry.configure(state="disabled")

        message_data = { "message": message, "app_version": config.APP_VERSION }
        
        # Start the background task to send the message
        threading.Thread(target=self._send_message_worker, args=(message_data, original_message_text), daemon=True).start()

    def _send_message_worker(self, message_data, original_message_text):
        success = False
        error_reason = "An unknown error occurred."
        try:
            headers = {'Authorization': f'Bearer {self.app.license_info.get("key")}'}
            response = requests.post(f"{config.LICENSE_SERVER_URL}/api/feedback/send_message", json=message_data, headers=headers, timeout=15)
            
            if response.status_code == 201:
                success = True
            else:
                error_reason = response.json().get('reason', 'Failed to send message.')
        except requests.exceptions.RequestException:
            error_reason = "Connection Error. Please check your internet."
        
        # Schedule the completion handler to run on the main UI thread
        self.app.after(0, self._on_send_complete, success, error_reason, original_message_text)

    def _on_send_complete(self, success, reason, original_message):
        """This function runs on the main thread after the message-sending attempt is complete."""
        # Always re-enable the UI elements
        self.message_entry.configure(state="normal")
        self.send_button.configure(state="normal", text="Send")

        if success:
            # If the message was sent successfully, trigger a refresh of the conversation
            self.load_conversation()
        else:
            # If sending failed, show an error and restore the typed message
            messagebox.showerror("Send Failed", f"Could not send message.\n\nReason: {reason}")
            self.message_entry.insert(0, original_message)

    def load_conversation(self):
        # Cancel any pending automatic refresh to avoid conflicts
        if self.poll_after_id:
            self.app.after_cancel(self.poll_after_id)

        # Show a loading message only if the chat is currently empty
        if not self.chat_scrollable_frame.winfo_children():
            ctk.CTkLabel(self.chat_scrollable_frame, text="Loading history...").pack(pady=10)
        
        threading.Thread(target=self._load_conversation_worker, daemon=True).start()

    def _load_conversation_worker(self):
        try:
            headers = {'Authorization': f'Bearer {self.app.license_info.get("key")}'}
            response = requests.get(f"{config.LICENSE_SERVER_URL}/api/feedback/thread", headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                self.app.after(0, self._display_conversation, data.get("conversation", []))
            else:
                self.app.after(0, self._display_conversation, [])
        except requests.exceptions.RequestException:
            self.app.after(0, self._display_conversation, [])
        finally:
            # Schedule the next automatic poll
            self.poll_after_id = self.app.after(15000, self.load_conversation) 

    def _display_conversation(self, conversation):
        # This logic prevents flickering by only redrawing if the messages have actually changed
        current_messages_data = []
        for child in self.chat_scrollable_frame.winfo_children():
            if isinstance(child, ctk.CTkFrame) and hasattr(child, '_message_data'):
                current_messages_data.append(child._message_data)

        if current_messages_data == conversation:
            return # No changes, so no need to redraw

        # Clear the old messages
        for widget in self.chat_scrollable_frame.winfo_children():
            widget.destroy()

        if not conversation:
            ctk.CTkLabel(self.chat_scrollable_frame, text="No messages yet. Start the conversation!", text_color="gray").pack(pady=20)
            return

        # Draw the new messages
        for msg in conversation:
            frame = ctk.CTkFrame(self.chat_scrollable_frame, fg_color="transparent")
            frame._message_data = msg # Store the original data for comparison
            
            is_admin = msg['is_admin_reply']
            bubble = ctk.CTkLabel(
                frame, text=msg['message'], wraplength=400, justify="left",
                fg_color=("#d1e7ff", "#2a3b4d") if not is_admin else ("#e2e3e5", "#373739"),
                corner_radius=10, padx=10, pady=5
            )

            anchor_side = "e" if not is_admin else "w"
            pack_padx = (50, 5) if not is_admin else (5, 50)
            
            frame.pack(fill="x", padx=5, pady=2)
            bubble.pack(anchor=anchor_side, padx=pack_padx, pady=2)
        
        # Ensure the view is scrolled to the latest message
        self.app.after(100, self.chat_scrollable_frame._parent_canvas.yview_moveto, 1.0)