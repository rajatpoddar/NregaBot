# tabs/file_management_tab.py
"""
Cloud File Manager — simplified.

Layout (top → bottom):
    Header      : Title + storage meter + Upgrade button
    Toolbar     : ⬅ ➡ | Upload ▾ (File(s)/Folder) | New Folder | Refresh
    Breadcrumb  : navigation + operation progress
    File tree   : multi-select, right-click menu, empty-state hint
    Action bar  : Download | Send via WhatsApp | Delete

WhatsApp fast-path: PDFs select karo → "Send via WhatsApp" → server PDFs ko
merge karke (footer/blank pages remove) Evolution API se **aapke apne
registered WhatsApp number par** bhej deta hai. Koi mobile input nahi —
number hamesha license se aata hai. Koi manual WhatsApp Web attach nahi.
"""
import tkinter
from tkinter import ttk, messagebox, filedialog, simpledialog
import customtkinter as ctk
import requests
import os
import threading
from datetime import datetime
from pathlib import Path
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

from src import config
from src.utils import format_bytes
from typing import Any, Callable, Dict, List, Optional, Tuple

WHATSAPP_GREEN = "#25D366"
WHATSAPP_GREEN_HOVER = "#1EBE5D"


class WhatsAppSendDialog(ctk.CTkToplevel):
    """Small dialog: caption + blank-page cleanup option. Hamesha user ke apne number par."""

    def __init__(self, tab: "FileManagementTab", file_count: int) -> None:
        super().__init__(tab)
        self.tab = tab
        self.file_count = file_count

        self.title("📤 Send PDF via WhatsApp")
        self.resizable(False, False)
        self.transient(tab)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.grid_columnconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, corner_radius=12, fg_color="transparent")
        frame.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        summary = (f"{file_count} PDF select kiye hain — merge hoke ek clean PDF "
                   f"bheji jayegi.") if file_count > 1 else "1 PDF select ki hai."
        ctk.CTkLabel(
            frame, text=summary,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=WHATSAPP_GREEN
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Document aapke apne WhatsApp number par jayegi — koi number input nahi
        self.user_mobile = self._get_user_mobile()
        if self.user_mobile:
            ctk.CTkLabel(
                frame, text=f"📱 Aapke number par bheji jayegi: {self.user_mobile}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("#1D4ED8", "#60A5FA")
            ).grid(row=1, column=0, sticky="w", pady=(0, 10))
        else:
            ctk.CTkLabel(
                frame, text="⚠️ Aapka WhatsApp number account me registered nahi hai",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="orange"
            ).grid(row=1, column=0, sticky="w", pady=(0, 10))

        ctk.CTkLabel(frame, text="Caption (optional):").grid(row=2, column=0, sticky="w")
        self.caption_entry = ctk.CTkEntry(frame, placeholder_text="e.g., Muster Roll — Kasraydih", height=38)
        self.caption_entry.grid(row=3, column=0, sticky="ew", pady=(4, 10))

        self.clean_var = tkinter.BooleanVar(value=True)
        ctk.CTkCheckBox(
            frame, text="Remove trailing blank/footer pages",
            variable=self.clean_var
        ).grid(row=4, column=0, sticky="w")
        ctk.CTkLabel(
            frame, text="(Wahi filter jo PDF Merger use karta hai)",
            font=ctk.CTkFont(size=11), text_color="gray50"
        ).grid(row=5, column=0, sticky="w", padx=(22, 0), pady=(0, 6))

        self.status_label = ctk.CTkLabel(frame, text="", text_color=WHATSAPP_GREEN, font=ctk.CTkFont(size=12))
        self.status_label.grid(row=6, column=0, sticky="w", pady=(2, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        self.cancel_button = ctk.CTkButton(btn_frame, text="Cancel", width=100, command=self._cancel)
        self.cancel_button.pack(side="right", padx=(8, 0))
        self.send_button = ctk.CTkButton(
            btn_frame, text="Send", width=130,
            fg_color=WHATSAPP_GREEN, hover_color=WHATSAPP_GREEN_HOVER,
            text_color="white", command=self._submit
        )
        self.send_button.pack(side="right")
        if not self.user_mobile:
            self.send_button.configure(state="disabled")

        self.after(120, self.caption_entry.focus_set)

    def _get_user_mobile(self) -> str:
        """User ka registered mobile number (license_info se)."""
        try:
            lic = getattr(self.tab.app, 'license_info', {}) or {}
            mobile = (lic or {}).get('user_mobile', '') or ''
            digits = "".join(ch for ch in str(mobile) if ch.isdigit())
            return digits if len(digits) >= 10 else ''
        except Exception:
            return ''

    def _submit(self):
        # Mobile number input nahi hai — hamesha user ke apne number par jata hai
        digits = self._get_user_mobile()
        if len(digits) < 10:
            self.status_label.configure(
                text="⚠️ Aapka WhatsApp number account me registered nahi hai",
                text_color="orange")
            return

        caption = self.caption_entry.get().strip()
        clean = self.clean_var.get()

        self.send_button.configure(state="disabled", text="⏳ Sending...")
        self.status_label.configure(text="", text_color=WHATSAPP_GREEN)
        self.tab._start_whatsapp_send(digits, caption, clean, self)

    def _finish(self, success: bool, message: str):
        """Called from the tab after the server responds."""
        try:
            if success:
                self.destroy()
            else:
                self.send_button.configure(state="normal", text="Send")
                self.status_label.configure(text=f"❌ {message}", text_color="red")
        except Exception:
            pass

    def _cancel(self):
        self.destroy()


class FileManagementTab(ctk.CTkFrame):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.current_folder_id = None
        self.item_map = {}
        self._wa_dialog = None

        self.history = []
        self.history_index = -1

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._create_widgets()
        self.refresh_files()

    # ════════════════════════════════════════════════════════════
    # UI BUILD
    # ════════════════════════════════════════════════════════════
    def _create_widgets(self) -> None:
        # ── Header: title + storage meter ──
        header_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                    border_color=("gray85", "gray30"), fg_color=("gray95", "gray20"))
        header_frame.grid(row=0, column=0, padx=10, pady=(10, 6), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        fm_icon = None
        try:
            fm_icon = self.app.icon_images.get_sized("emoji_file_manager", (20, 20))
        except Exception:
            fm_icon = None

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        ctk.CTkLabel(
            title_frame, text=" Cloud File Manager" if fm_icon is not None else "📁 Cloud File Manager",
            image=fm_icon, compound="left",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#1D4ED8", "#60A5FA")
        ).pack(side="left")
        ctk.CTkLabel(
            title_frame, text="Upload karo, client ko WhatsApp par bhejo",
            font=ctk.CTkFont(size=11),
            text_color=("#475569", "#94A3B8")
        ).pack(side="left", padx=(10, 0))

        storage_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        storage_frame.grid(row=0, column=1, padx=15, pady=10, sticky="e")
        self.storage_label = ctk.CTkLabel(storage_frame, text="Storage: Calculating...")
        self.storage_label.pack(anchor="e")
        self.storage_progress = ctk.CTkProgressBar(storage_frame, width=150)
        self.storage_progress.set(0)
        self.storage_progress.pack(anchor="e", pady=(5, 0))
        self.upgrade_storage_button = ctk.CTkButton(storage_frame, text="Upgrade Storage", height=24, command=self.open_upgrade_page)
        self.upgrade_storage_button.pack(anchor="e", pady=(5, 0))

        # ── Toolbar: navigation + single Upload menu ──
        nav_frame = ctk.CTkFrame(self, corner_radius=12, border_width=1,
                                 border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        nav_frame.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="ew")
        nav_frame.grid_columnconfigure(1, weight=1)

        controls_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.back_button = ctk.CTkButton(controls_frame, text="⬅", width=30, command=self.go_back, state="disabled")
        self.back_button.pack(side="left", padx=(0, 5))
        self.forward_button = ctk.CTkButton(controls_frame, text="➡", width=30, command=self.go_forward, state="disabled")
        self.forward_button.pack(side="left", padx=(0, 10))

        self.upload_button = ctk.CTkButton(controls_frame, text="⬆ Upload ▾", width=110, command=self._show_upload_menu)
        self.upload_button.pack(side="left", padx=(0, 5))
        self.new_folder_button = ctk.CTkButton(controls_frame, text="New Folder", width=110, command=self.create_new_folder)
        self.new_folder_button.pack(side="left", padx=5)
        self.refresh_button = ctk.CTkButton(controls_frame, text="⟳ Refresh", width=90,
                                            command=lambda: self.refresh_files(self.current_folder_id, add_to_history=False))
        self.refresh_button.pack(side="left", padx=5)

        # ── Breadcrumb + operation progress ──
        progress_breadcrumb_frame = ctk.CTkFrame(self)
        progress_breadcrumb_frame.grid(row=2, column=0, padx=10, pady=0, sticky="ew")
        progress_breadcrumb_frame.grid_columnconfigure(0, weight=1)

        self.breadcrumb_frame = ctk.CTkFrame(progress_breadcrumb_frame, fg_color="transparent")
        self.breadcrumb_frame.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.op_progress_label = ctk.CTkLabel(progress_breadcrumb_frame, text="", text_color="gray50")
        self.op_progress_label.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="w")
        self.op_progress = ctk.CTkProgressBar(progress_breadcrumb_frame)
        self.op_progress.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.op_progress.set(0)
        self.op_progress.grid_remove()
        self.op_progress_label.grid_remove()

        # ── File tree ──
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=3, column=0, padx=10, pady=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        cols = ("Name", "Size", "Date Modified")
        self.files_tree = ttk.Treeview(main_frame, columns=cols, show='headings', selectmode='extended')
        for col in cols:
            self.files_tree.heading(col, text=col)
        self.files_tree.column("Name", width=400, anchor="w")
        self.files_tree.column("Size", width=100, anchor="e")
        self.files_tree.column("Date Modified", width=150, anchor="center")
        self.files_tree.grid(row=0, column=0, sticky='nsew')

        scrollbar = ctk.CTkScrollbar(main_frame, command=self.files_tree.yview)
        self.files_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')

        self.empty_label = ctk.CTkLabel(
            main_frame, text="📂 Folder empty hai\n\n'Upload ▾' se files add karein",
            font=ctk.CTkFont(size=14), text_color="gray50"
        )

        self.style_treeview(self.files_tree)
        self.files_tree.bind("<<TreeviewSelect>>", self.on_item_select)
        self.files_tree.bind("<Double-1>", self.on_item_double_click)
        self.files_tree.bind("<Button-3>", self._on_tree_right_click)
        self.files_tree.bind("<Delete>", lambda e: self.delete_selected_item())

        # ── Action bar ──
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        action_bar.grid_columnconfigure(3, weight=1)

        self.sel_label = ctk.CTkLabel(action_bar, text="", text_color="gray50", font=ctk.CTkFont(size=12))
        self.sel_label.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.download_button = ctk.CTkButton(action_bar, text="Download", command=self.download_selected_item, state="disabled")
        self.download_button.grid(row=0, column=1, padx=(0, 5))
        self.whatsapp_button = ctk.CTkButton(
            action_bar, text="🟢 Send via WhatsApp", command=self.send_whatsapp_selected,
            state="disabled", fg_color=WHATSAPP_GREEN, hover_color=WHATSAPP_GREEN_HOVER,
            text_color="white"
        )
        self.whatsapp_button.grid(row=0, column=2, padx=5)
        self.delete_button = ctk.CTkButton(
            action_bar, text="Delete", command=self.delete_selected_item, state="disabled",
            fg_color=config.COLORS["red_delete"], hover_color=config.COLORS["red_delete_hover"]
        )
        self.delete_button.grid(row=0, column=3, padx=5, sticky="w")

    def style_treeview(self, treeview_widget=None):
        if hasattr(self.app, '_cached_style') and self.app._cached_style is not None:
            style = self.app._cached_style
        else:
            style = ttk.Style()
            style.theme_use("clam")
            self.app._cached_style = style

        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            bg_color = "#2b2b2b"; text_color = "#e5e7eb"; row_hover = "#3f3f46"
            selected_bg = "#3B82F6"; header_bg = "#1f2937"; header_fg = "#ffffff"; header_hover = "#374151"
        else:
            bg_color = "#ffffff"; text_color = "#374151"; row_hover = "#f3f4f6"
            selected_bg = "#3B82F6"; header_bg = "#f9fafb"; header_fg = "#111827"; header_hover = "#e5e7eb"

        style.configure("Treeview", background=bg_color, foreground=text_color,
                        fieldbackground=bg_color, rowheight=35,
                        font=("Segoe UI", 11), borderwidth=0)
        style.map("Treeview", background=[('selected', selected_bg), ('active', row_hover)],
                  foreground=[('selected', 'white'), ('active', text_color)])
        style.configure("Treeview.Heading", background=header_bg, foreground=header_fg,
                        relief="flat", font=("Segoe UI", 12, "bold"))
        style.map("Treeview.Heading", background=[('active', header_hover)])
        if treeview_widget:
            treeview_widget.configure(style="Treeview")

    # ════════════════════════════════════════════════════════════
    # SELECTION HELPERS
    # ════════════════════════════════════════════════════════════
    def _get_selected_items(self) -> List[Dict]:
        items = []
        for iid in self.files_tree.selection():
            item = self.item_map.get(int(iid))
            if item:
                items.append(item)
        return items

    def _selected_pdf_files(self) -> List[Dict]:
        return [it for it in self._get_selected_items()
                if not it['is_folder'] and it['filename'].lower().endswith('.pdf')]

    def on_item_select(self, event=None):
        selected = self._get_selected_items()
        n = len(selected)
        pdf_files = self._selected_pdf_files()

        state = "normal" if n else "disabled"
        self.download_button.configure(state=state)
        self.delete_button.configure(state=state)
        self.whatsapp_button.configure(state="normal" if pdf_files else "disabled")

        if n:
            if pdf_files and n > len(pdf_files):
                self.sel_label.configure(text=f"{n} selected ({len(pdf_files)} PDF)")
            else:
                self.sel_label.configure(text=f"{n} selected")
        else:
            self.sel_label.configure(text="")

    def on_item_double_click(self, event=None):
        selected = self._get_selected_items()
        if not selected:
            return
        item = selected[0]
        if item['is_folder']:
            self.refresh_files(folder_id=item['id'])
        else:
            self.download_file(item)

    def _on_tree_right_click(self, event):
        iid = self.files_tree.identify_row(event.y)
        if not iid:
            return
        if iid not in self.files_tree.selection():
            self.files_tree.selection_set(iid)
        self.on_item_select()

        menu = tkinter.Menu(self, tearoff=0)
        selected = self._get_selected_items()
        pdf_files = self._selected_pdf_files()

        menu.add_command(label="⬇ Download", command=self.download_selected_item,
                         state="normal" if selected else "disabled")
        menu.add_command(label="🟢 Send via WhatsApp", command=self.send_whatsapp_selected,
                         state="normal" if pdf_files else "disabled")
        menu.add_separator()
        menu.add_command(label="🗑 Delete", command=self.delete_selected_item,
                         state="normal" if selected else "disabled")
        menu.add_command(label="⟳ Refresh", command=lambda: self.refresh_files(self.current_folder_id, add_to_history=False))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ════════════════════════════════════════════════════════════
    # AUTH + NAVIGATION + LISTING
    # ════════════════════════════════════════════════════════════
    def get_auth_headers(self):
        if not self.app.license_info.get('key'):
            messagebox.showerror("Authentication Error", "No active license key found.")
            return None
        return {'Authorization': f"Bearer {self.app.license_info['key']}"}

    def refresh_files(self, folder_id=None, add_to_history=True):
        self.files_tree.delete(*self.files_tree.get_children())
        self.on_item_select()

        if add_to_history:
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            if not self.history or self.history[-1] != folder_id:
                self.history.append(folder_id)
            self.history_index = len(self.history) - 1

        self.update_nav_buttons()

        headers = self.get_auth_headers()
        if not headers:
            return

        self.current_folder_id = folder_id
        url = f"{config.LICENSE_SERVER_URL}/files/api/list"
        if folder_id:
            url += f"/{folder_id}"

        def _fetch():
            try:
                response = self.app.http_session.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    self.app.after(0, self.update_ui_with_data, data)
                else:
                    reason = response.json().get('reason', 'Unknown error')
                    self.app.after(0, messagebox.showerror, "Error", f"Failed to fetch file list: {reason}")
            except requests.exceptions.RequestException as e:
                self.app.after(0, messagebox.showerror, "Connection Error", f"Could not connect to the server: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.refresh_files(self.history[self.history_index], add_to_history=False)

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.refresh_files(self.history[self.history_index], add_to_history=False)

    def update_nav_buttons(self):
        self.back_button.configure(state="normal" if self.history_index > 0 else "disabled")
        self.forward_button.configure(state="normal" if self.history_index < len(self.history) - 1 else "disabled")

    def update_ui_with_data(self, data):
        self.update_file_list(data.get('files', []))
        self.update_breadcrumbs(data.get('path', []))
        current_limit = self.app.license_info.get('max_storage')
        self.update_storage_info(data.get('total_usage', 0), current_limit)

    def update_file_list(self, files):
        self.files_tree.delete(*self.files_tree.get_children())
        self.item_map.clear()

        if not files:
            self.files_tree.grid_remove()
            self.empty_label.grid(row=0, column=0, sticky="nsew")
        else:
            self.empty_label.grid_remove()
            self.files_tree.grid()

        for item in files:
            self.item_map[item['id']] = item
            try:
                date_obj = datetime.fromisoformat(item['uploaded_at'].replace('Z', '+00:00'))
                formatted_date = date_obj.strftime('%Y-%m-%d %I:%M %p')
            except (ValueError, TypeError):
                formatted_date = item['uploaded_at']

            icon = "📁" if item['is_folder'] else "📄"
            name = f"{icon} {item['filename']}"
            size = format_bytes(item['filesize']) if not item['is_folder'] else "—"
            self.files_tree.insert("", "end", iid=item['id'], values=(name, size, formatted_date))

    def update_storage_info(self, total_usage, storage_limit):
        try:
            numeric_usage = int(total_usage)
            numeric_limit = int(storage_limit) if storage_limit else 1
            self.storage_label.configure(text=f"Storage: {format_bytes(numeric_usage)} / {format_bytes(numeric_limit)}")
            usage_percent = numeric_usage / numeric_limit if numeric_limit > 0 else 0
            self.storage_progress.set(usage_percent)
            if usage_percent < 0.3:
                color = config.COLORS["green_file"]
            elif usage_percent < 0.6:
                color = config.COLORS["blue"]
            elif usage_percent < 0.8:
                color = config.COLORS["orange_file"]
            else:
                color = config.COLORS["red_error"]
            self.storage_progress.configure(progress_color=color)
            self.upgrade_storage_button.configure(fg_color=color, hover_color=color)
        except (ValueError, TypeError):
            self.storage_label.configure(text="Storage: Error")
            self.storage_progress.set(0)

    def update_breadcrumbs(self, path):
        for widget in self.breadcrumb_frame.winfo_children():
            widget.destroy()
        home_btn = ctk.CTkButton(self.breadcrumb_frame, text="Home",
                                 command=lambda: self.refresh_files(None), width=50, height=24)
        home_btn.pack(side="left")
        for folder in path:
            ctk.CTkLabel(self.breadcrumb_frame, text="/").pack(side="left", padx=2)
            btn = ctk.CTkButton(self.breadcrumb_frame, text=folder['filename'],
                                command=lambda f_id=folder['id']: self.refresh_files(f_id), height=24)
            btn.pack(side="left")

    # ════════════════════════════════════════════════════════════
    # UPLOAD
    # ════════════════════════════════════════════════════════════
    def _show_upload_menu(self):
        menu = tkinter.Menu(self, tearoff=0)
        menu.add_command(label="📄 Upload File(s)...", command=self.upload_files)
        menu.add_command(label="📁 Upload Folder...", command=self.upload_folder)
        try:
            x = self.upload_button.winfo_rootx()
            y = self.upload_button.winfo_rooty() + self.upload_button.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def upload_files(self):
        filepaths = filedialog.askopenfilenames(title="Select File(s) to Upload")
        if not filepaths:
            return
        self._start_upload_session(filepaths, is_folder=False)

    def upload_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder to Upload")
        if not folder_path:
            return
        files_to_upload = []
        base_folder_name = os.path.basename(folder_path)
        for root, _, files in os.walk(folder_path):
            for filename in files:
                local_path = os.path.join(root, filename)
                relative_path = os.path.join(base_folder_name, os.path.relpath(local_path, folder_path))
                files_to_upload.append({'local_path': local_path, 'relative_path': str(Path(relative_path))})
        if not files_to_upload:
            messagebox.showinfo("Empty Folder", "The selected folder is empty.")
            return
        self._start_upload_session(files_to_upload, is_folder=True)

    def _start_upload_session(self, items, is_folder):
        headers = self.get_auth_headers()
        if not headers:
            return

        self.op_progress.grid()
        self.op_progress_label.grid()
        self.op_progress.set(0)

        def _upload_worker():
            total_items = len(items)
            for i, item in enumerate(items):
                local_path = item['local_path'] if is_folder else item
                relative_path = item['relative_path'] if is_folder else ''
                filename = os.path.basename(local_path)

                def create_callback(encoder):
                    total_size = encoder.len
                    def callback(monitor):
                        progress = (i + (monitor.bytes_read / total_size)) / total_items
                        self.app.after(0, self.op_progress.set, progress)
                        self.app.after(0, self.op_progress_label.configure,
                                       {"text": f"Uploading ({i+1}/{total_items}): {filename} ({int(progress*100)}%)"})
                    return callback

                success = self._perform_upload(local_path, relative_path, headers, create_callback)
                if not success:
                    if not messagebox.askyesno("Upload Failed",
                                               f"Failed to upload {filename}. Continue with remaining files?"):
                        break

            self.app.after(0, self.op_progress_label.configure, {"text": "Upload Complete!"})
            self.app.after(5000, lambda: self.op_progress.grid_remove())
            self.app.after(5000, lambda: self.op_progress_label.grid_remove())
            self.app.after(100, lambda: self.refresh_files(self.current_folder_id, add_to_history=False))

        threading.Thread(target=_upload_worker, daemon=True).start()

    def _perform_upload(self, filepath, relative_path, headers, create_callback):
        try:
            fields = {
                'parent_id': str(self.current_folder_id or ''),
                'relative_path': relative_path,
                'file': (os.path.basename(filepath), open(filepath, 'rb'), 'application/octet-stream')
            }
            encoder = MultipartEncoder(fields=fields)
            monitor = MultipartEncoderMonitor(encoder, create_callback(encoder))

            response = self.app.http_session.post(
                f"{config.LICENSE_SERVER_URL}/files/api/upload",
                headers={**headers, 'Content-Type': monitor.content_type},
                data=monitor,
                timeout=300
            )
            return response.status_code == 201
        except requests.exceptions.RequestException as e:
            print(f"Upload error: {e}")
            return False
        except Exception as e:
            print(f"Generic upload error: {e}")
            return False

    def create_new_folder(self):
        folder_name = simpledialog.askstring("New Folder", "Enter a name for the new folder:", parent=self)
        if not folder_name or not folder_name.strip():
            return
        headers = self.get_auth_headers()
        if not headers:
            return
        data = {'folder_name': folder_name.strip(), 'parent_id': self.current_folder_id or ''}

        def _create():
            try:
                response = self.app.http_session.post(
                    f"{config.LICENSE_SERVER_URL}/files/api/create-folder", headers=headers, json=data, timeout=30)
                if response.status_code == 201:
                    self.app.after(0, lambda: self.refresh_files(self.current_folder_id, add_to_history=False))
                else:
                    try:
                        reason = response.json().get('reason', 'An unknown server error occurred.')
                    except requests.exceptions.JSONDecodeError:
                        reason = f"Server returned a non-JSON response (Status: {response.status_code})."
                    self.app.after(0, messagebox.showerror, "Creation Failed", reason)
            except requests.exceptions.RequestException as e:
                self.app.after(0, messagebox.showerror, "Connection Error", str(e))

        threading.Thread(target=_create, daemon=True).start()

    # ════════════════════════════════════════════════════════════
    # DOWNLOAD
    # ════════════════════════════════════════════════════════════
    def download_selected_item(self):
        items = self._get_selected_items()
        if not items:
            return

        if len(items) == 1:
            item = items[0]
            if item['is_folder']:
                self.download_folder(item)
            else:
                self.download_file(item)
            return

        if any(it['is_folder'] for it in items):
            messagebox.showinfo("Folders Selected",
                                "Folders ko individually download karein (double-click se khol kar).")
            return

        save_dir = filedialog.askdirectory(title="Select folder to save the downloaded files")
        if not save_dir:
            return
        self._download_multiple_files(items, save_dir)

    def _download_multiple_files(self, items, save_dir):
        headers = self.get_auth_headers()
        if not headers:
            return
        self.op_progress.grid()
        self.op_progress_label.grid()
        total = len(items)

        def _worker():
            for i, item in enumerate(items):
                self.app.after(0, self.op_progress.set, i / total)
                self.app.after(0, self.op_progress_label.configure,
                               {"text": f"Downloading ({i+1}/{total}): {item['filename']}"})
                try:
                    with self.app.http_session.get(
                        f"{config.LICENSE_SERVER_URL}/files/api/download/{item['id']}",
                        headers=headers, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        local_path = os.path.join(save_dir, item['filename'])
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                except requests.exceptions.RequestException:
                    if not messagebox.askyesno("Download Failed",
                                               f"Failed to download {item['filename']}. Continue?"):
                        break
            self.app.after(0, self.op_progress.set, 1.0)
            self.app.after(0, self.op_progress_label.configure, {"text": "Download Complete!"})
            self.app.after(5000, lambda: self.op_progress.grid_remove())
            self.app.after(5000, lambda: self.op_progress_label.grid_remove())

        threading.Thread(target=_worker, daemon=True).start()

    def download_file(self, item_data):
        save_path = filedialog.asksaveasfilename(initialfile=item_data['filename'], title="Save File As")
        if not save_path:
            return
        headers = self.get_auth_headers()
        if not headers:
            return
        self.op_progress.grid()
        self.op_progress_label.grid()

        def _download():
            try:
                with self.app.http_session.get(
                    f"{config.LICENSE_SERVER_URL}/files/api/download/{item_data['id']}",
                    headers=headers, stream=True, timeout=300) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    bytes_downloaded = 0
                    with open(save_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            if total_size > 0:
                                progress = bytes_downloaded / total_size
                                self.app.after(0, self.op_progress.set, progress)
                                self.app.after(0, self.op_progress_label.configure,
                                               {"text": f"Downloading: {item_data['filename']} ({int(progress*100)}%)"})
                self.app.after(0, messagebox.showinfo, "Download Complete",
                               f"Successfully downloaded '{item_data['filename']}'")
            except requests.exceptions.RequestException as e:
                self.app.after(0, messagebox.showerror, "Download Failed", str(e))
            finally:
                self.app.after(0, lambda: self.op_progress.grid_remove())
                self.app.after(0, lambda: self.op_progress_label.grid_remove())

        threading.Thread(target=_download, daemon=True).start()

    def download_folder(self, folder_data):
        save_location = filedialog.askdirectory(title=f"Select where to save the '{folder_data['filename']}' folder")
        if not save_location:
            return
        headers = self.get_auth_headers()
        if not headers:
            return
        self.op_progress.grid()
        self.op_progress_label.grid()

        def _download_worker():
            files_to_download = []

            def get_all_files(folder_id, current_path):
                url = f"{config.LICENSE_SERVER_URL}/files/api/list/{folder_id}"
                try:
                    response = self.app.http_session.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    items = response.json().get('files', [])
                    for item in items:
                        new_path = os.path.join(current_path, item['filename'])
                        if item['is_folder']:
                            get_all_files(item['id'], new_path)
                        else:
                            files_to_download.append({'id': item['id'], 'path': new_path, 'size': item['filesize']})
                except requests.exceptions.RequestException:
                    self.app.after(0, messagebox.showerror, "Error", "Could not fetch folder contents.")
                    return

            get_all_files(folder_data['id'], folder_data['filename'])

            total_files = len(files_to_download)
            if total_files == 0:
                os.makedirs(os.path.join(save_location, folder_data['filename']), exist_ok=True)
                self.app.after(0, messagebox.showinfo, "Complete", "Downloaded empty folder structure.")
                return

            for i, file_info in enumerate(files_to_download):
                self.app.after(0, self.op_progress.set, i / total_files)
                self.app.after(0, self.op_progress_label.configure,
                               {"text": f"Downloading ({i+1}/{total_files}): {os.path.basename(file_info['path'])}"})
                local_path = os.path.join(save_location, file_info['path'])
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                try:
                    with self.app.http_session.get(
                        f"{config.LICENSE_SERVER_URL}/files/api/download/{file_info['id']}",
                        headers=headers, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                except requests.exceptions.RequestException:
                    if not messagebox.askyesno("Download Failed",
                                               f"Failed to download {os.path.basename(file_info['path'])}. Continue?"):
                        break

            self.app.after(0, self.op_progress.set, 1.0)
            self.app.after(0, messagebox.showinfo, "Download Complete",
                           f"Finished downloading folder '{folder_data['filename']}'.")
            self.app.after(5000, lambda: self.op_progress.grid_remove())
            self.app.after(5000, lambda: self.op_progress_label.grid_remove())

        threading.Thread(target=_download_worker, daemon=True).start()

    # ════════════════════════════════════════════════════════════
    # DELETE
    # ════════════════════════════════════════════════════════════
    def delete_selected_item(self):
        items = self._get_selected_items()
        if not items:
            return
        if len(items) == 1:
            names = f"'{items[0]['filename']}'"
        else:
            names = f"{len(items)} items"
        if not messagebox.askyesno("Confirm Deletion",
                                   f"Are you sure you want to permanently delete {names}? This cannot be undone."):
            return
        headers = self.get_auth_headers()
        if not headers:
            return

        def _delete():
            failed = []
            for item in items:
                try:
                    response = self.app.http_session.delete(
                        f"{config.LICENSE_SERVER_URL}/files/api/delete/{item['id']}", headers=headers, timeout=30)
                    if response.status_code != 200:
                        failed.append(item['filename'])
                except requests.exceptions.RequestException:
                    failed.append(item['filename'])
            if failed:
                self.app.after(0, messagebox.showerror, "Deletion Failed",
                               f"Could not delete: {', '.join(failed)}")
            self.app.after(0, lambda: self.refresh_files(self.current_folder_id, add_to_history=False))

        threading.Thread(target=_delete, daemon=True).start()

    # ════════════════════════════════════════════════════════════
    # WHATSAPP FAST-PATH
    # ════════════════════════════════════════════════════════════
    def send_whatsapp_selected(self):
        pdf_files = self._selected_pdf_files()
        if not pdf_files:
            messagebox.showinfo("Select PDFs", "WhatsApp par bhejne ke liye ek ya zyada PDF files select karein.")
            return
        self._wa_dialog = WhatsAppSendDialog(self, len(pdf_files))

    def _start_whatsapp_send(self, mobile: str, caption: str, clean_pages: bool, dialog: WhatsAppSendDialog):
        pdf_files = self._selected_pdf_files()
        headers = self.get_auth_headers()
        if not headers:
            dialog._finish(False, "No active license key found.")
            return

        item_ids = [it['id'] for it in pdf_files]
        payload = {
            "item_ids": item_ids,
            "mobile": mobile,
            "caption": caption,
            "clean_pages": clean_pages,
        }

        def _send():
            try:
                response = self.app.http_session.post(
                    f"{config.LICENSE_SERVER_URL}/files/api/whatsapp-send",
                    json=payload, headers=headers, timeout=120)
                if response.status_code in (200, 201, 202):
                    self.app.after(0, lambda: self._on_whatsapp_done(True, ""))
                else:
                    try:
                        reason = response.json().get('reason', f"Server error ({response.status_code})")
                    except Exception:
                        reason = f"Server error ({response.status_code})"
                    self.app.after(0, lambda: self._on_whatsapp_done(False, reason))
            except requests.exceptions.RequestException as e:
                self.app.after(0, lambda: self._on_whatsapp_done(False, f"Connection error: {e}"))

        threading.Thread(target=_send, daemon=True).start()

    def _on_whatsapp_done(self, success: bool, message: str):
        dialog = self._wa_dialog
        self._wa_dialog = None
        if dialog is not None and dialog.winfo_exists():
            dialog._finish(success, message)
        if success:
            try:
                if hasattr(self.app, 'show_toast'):
                    self.app.show_toast("📤 PDF WhatsApp par bhej diya!", "success")
            except Exception:
                pass
            messagebox.showinfo("WhatsApp Send", "PDF WhatsApp par bhej di gayi!\n\n"
                                                 "Document aapke WhatsApp par kuch seconds me aa jayega.")

    def open_upgrade_page(self):
        # Secure path: signed token fetch → browser (raw key kabhi URL mein nahi)
        self.app.open_web_page('storage')
