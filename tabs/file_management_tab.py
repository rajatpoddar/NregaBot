# tabs/file_management_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog, simpledialog
import customtkinter as ctk
import requests
import os
import threading
from datetime import datetime
import humanize
from pathlib import Path
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
import webbrowser

import config

class FileManagementTab(ctk.CTkFrame):
    def __init__(self, parent, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.current_folder_id = None
        self.item_map = {}

        self.history = []
        self.history_index = -1

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._create_widgets()
        self.refresh_files()

    def _create_widgets(self):
        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Cloud File Manager", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        storage_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        storage_frame.grid(row=0, column=1, padx=15, pady=10, sticky="e")
        self.storage_label = ctk.CTkLabel(storage_frame, text="Storage: Calculating...")
        self.storage_label.pack(anchor="e")
        self.storage_progress = ctk.CTkProgressBar(storage_frame, width=150)
        self.storage_progress.set(0)
        self.storage_progress.pack(anchor="e", pady=(5,0))

        self.upgrade_storage_button = ctk.CTkButton(storage_frame, text="Upgrade Storage", height=24, command=self.open_upgrade_page)
        self.upgrade_storage_button.pack(anchor="e", pady=(5,0))


        nav_frame = ctk.CTkFrame(self)
        nav_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        nav_frame.grid_columnconfigure(1, weight=1)

        controls_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self.back_button = ctk.CTkButton(controls_frame, text="⬅", width=30, command=self.go_back, state="disabled")
        self.back_button.pack(side="left", padx=(0, 5))
        self.forward_button = ctk.CTkButton(controls_frame, text="➡", width=30, command=self.go_forward, state="disabled")
        self.forward_button.pack(side="left", padx=(0, 10))

        self.upload_file_button = ctk.CTkButton(controls_frame, text="Upload File(s)", width=120, command=self.upload_files)
        self.upload_file_button.pack(side="left", padx=(0, 5))

        self.upload_folder_button = ctk.CTkButton(controls_frame, text="Upload Folder", width=120, command=self.upload_folder)
        self.upload_folder_button.pack(side="left", padx=5)

        self.new_folder_button = ctk.CTkButton(controls_frame, text="New Folder", width=110, command=self.create_new_folder)
        self.new_folder_button.pack(side="left", padx=5)

        self.refresh_button = ctk.CTkButton(controls_frame, text="Refresh", width=90, command=lambda: self.refresh_files(self.current_folder_id, add_to_history=False))
        self.refresh_button.pack(side="left", padx=5)

        progress_breadcrumb_frame = ctk.CTkFrame(self)
        progress_breadcrumb_frame.grid(row=2, column=0, padx=10, pady=0, sticky="ew")
        progress_breadcrumb_frame.grid_columnconfigure(0, weight=1)

        self.breadcrumb_frame = ctk.CTkFrame(progress_breadcrumb_frame, fg_color="transparent")
        self.breadcrumb_frame.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.op_progress_label = ctk.CTkLabel(progress_breadcrumb_frame, text="", text_color="gray50")
        self.op_progress_label.grid(row=1, column=0, padx=10, pady=(0,5), sticky="w")
        self.op_progress = ctk.CTkProgressBar(progress_breadcrumb_frame)
        self.op_progress.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.op_progress.set(0)
        self.op_progress.grid_remove()
        self.op_progress_label.grid_remove()

        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=3, column=0, padx=10, pady=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        cols = ("Name", "Size", "Date Modified")
        self.files_tree = ttk.Treeview(main_frame, columns=cols, show='headings')
        for col in cols: self.files_tree.heading(col, text=col)
        self.files_tree.column("Name", width=400, anchor="w")
        self.files_tree.column("Size", width=100, anchor="e")
        self.files_tree.column("Date Modified", width=150, anchor="center")
        self.files_tree.grid(row=0, column=0, sticky='nsew')

        scrollbar = ctk.CTkScrollbar(main_frame, command=self.files_tree.yview)
        self.files_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')

        self.style_treeview(self.files_tree)
        self.files_tree.bind("<<TreeviewSelect>>", self.on_item_select)
        self.files_tree.bind("<Double-1>", self.on_item_double_click)

        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        self.download_button = ctk.CTkButton(action_bar, text="Download", command=self.download_selected_item, state="disabled")
        self.download_button.pack(side="left", padx=(0, 5))
        self.share_button = ctk.CTkButton(action_bar, text="Share", command=self.share_selected_item, state="disabled")
        self.share_button.pack(side="left", padx=5)
        self.delete_button = ctk.CTkButton(action_bar, text="Delete", command=self.delete_selected_item, state="disabled", fg_color="#D32F2F", hover_color="#B71C1C")
        self.delete_button.pack(side="left", padx=5)

    def style_treeview(self, treeview_widget=None):
        # Agar argument nahi diya (main_app me), toh ye function global style set karega
        style = ttk.Style()
        style.theme_use("clam")

        # 1. Theme Detection
        mode = ctk.get_appearance_mode()

        if mode == "Dark":
            # --- DARK MODE COLORS ---
            bg_color = "#2b2b2b"        # Table Background
            text_color = "#e5e7eb"      # Text (Light Gray)
            row_hover = "#3f3f46"       # Row Hover Color (Thoda sa light dark)
            selected_bg = "#3B82F6"     # Selection (Blue)
            
            header_bg = "#1f2937"       # Header Background (Dark Slate)
            header_fg = "#ffffff"       # Header Text
            header_hover = "#374151"    # Header Hover
        else:
            # --- LIGHT MODE COLORS ---
            bg_color = "#ffffff"        # Table Background
            text_color = "#374151"      # Text (Dark Gray)
            row_hover = "#f3f4f6"       # Row Hover Color (Very Light Gray)
            selected_bg = "#3B82F6"     # Selection (Blue)
            
            header_bg = "#f9fafb"       # Header Background (Off-white)
            header_fg = "#111827"       # Header Text (Almost Black)
            header_hover = "#e5e7eb"    # Header Hover

        # 2. Configure Treeview Body
        style.configure("Treeview",
                        background=bg_color,
                        foreground=text_color,
                        fieldbackground=bg_color,
                        rowheight=35,             # Rows thodi spacious
                        font=("Segoe UI", 11),
                        borderwidth=0)

        # 3. Configure Rows (Hover & Selection)
        # Note: 'selected' pehle check hota hai, isliye hover selected row ka color kharab nahi karega
        style.map("Treeview",
                  background=[('selected', selected_bg), ('active', row_hover)],
                  foreground=[('selected', 'white'), ('active', text_color)])

        # 4. Configure Heading
        style.configure("Treeview.Heading",
                        background=header_bg,
                        foreground=header_fg,
                        relief="flat",
                        font=("Segoe UI", 12, "bold"))

        style.map("Treeview.Heading",
                  background=[('active', header_hover)])

        # 5. Fix for file_management_tab (jahan widget pass hota hai)
        if treeview_widget:
            treeview_widget.configure(style="Treeview")

    def on_item_select(self, event=None):
        selected_items = self.files_tree.selection()
        is_selected = bool(selected_items)
        state = "normal" if is_selected else "disabled"
        self.download_button.configure(state=state)
        self.delete_button.configure(state=state)

        # Share button logic
        if len(selected_items) == 1:
            item_data = self.item_map.get(int(selected_items[0]))
            if item_data and item_data['is_folder']:
                self.share_button.configure(state="normal")
            else:
                self.share_button.configure(state="disabled")
        else:
            self.share_button.configure(state="disabled")

    def on_item_double_click(self, event=None):
        selected_iid = self.files_tree.focus()
        if not selected_iid: return

        item_data = self.item_map.get(int(selected_iid))
        if item_data and item_data['is_folder']:
            self.refresh_files(folder_id=item_data['id'])

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
        if not headers: return

        self.current_folder_id = folder_id
        url = f"{config.LICENSE_SERVER_URL}/files/api/list"
        if folder_id:
            url += f"/{folder_id}"

        def _fetch():
            try:
                response = requests.get(url, headers=headers, timeout=15)
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
        # This method now only updates the file list and breadcrumbs for this tab
        self.update_file_list(data.get('files', []))
        self.update_breadcrumbs(data.get('path', []))

        # We also use the usage data from this API call to keep the progress bar accurate
        # The storage LIMIT is now set by the main_app, not this function
        current_limit = self.app.license_info.get('max_storage')
        self.update_storage_info(data.get('total_usage', 0), current_limit)

    def update_file_list(self, files):
        self.files_tree.delete(*self.files_tree.get_children())
        self.item_map.clear()
        
        for item in files:
            self.item_map[item['id']] = item
            try:
                date_obj = datetime.fromisoformat(item['uploaded_at'].replace('Z', '+00:00'))
                formatted_date = date_obj.strftime('%Y-%m-%d %I:%M %p')
            except (ValueError, TypeError):
                formatted_date = item['uploaded_at']

            icon = "📁" if item['is_folder'] else "📄"
            name = f"{icon} {item['filename']}"
            size = humanize.naturalsize(item['filesize']) if not item['is_folder'] else "—"

            self.files_tree.insert("", "end", iid=item['id'], values=(name, size, formatted_date))

    def update_storage_info(self, total_usage, storage_limit):
        try:
            numeric_usage = int(total_usage)
            numeric_limit = int(storage_limit) if storage_limit else 1

            # Use humanize for both values for consistent formatting
            self.storage_label.configure(text=f"Storage: {humanize.naturalsize(numeric_usage)} / {humanize.naturalsize(numeric_limit)}")

            usage_percent = numeric_usage / numeric_limit if numeric_limit > 0 else 0
            self.storage_progress.set(usage_percent)

            if usage_percent < 0.3:
                color = "#22c55e" # Green
            elif 0.3 <= usage_percent < 0.6:
                color = "#3b82f6" # Blue
            elif 0.6 <= usage_percent < 0.8:
                color = "#f59e0b" # Yellow
            else:
                color = "#ef4444" # Red

            self.storage_progress.configure(progress_color=color)
            self.upgrade_storage_button.configure(fg_color=color, hover_color=color)

        except (ValueError, TypeError):
            self.storage_label.configure(text="Storage: Error")
            self.storage_progress.set(0)


    def update_breadcrumbs(self, path):
        for widget in self.breadcrumb_frame.winfo_children():
            widget.destroy()

        home_btn = ctk.CTkButton(self.breadcrumb_frame, text="Home", command=lambda: self.refresh_files(None), width=50, height=24)
        home_btn.pack(side="left")

        for folder in path:
            ctk.CTkLabel(self.breadcrumb_frame, text="/").pack(side="left", padx=2)
            btn = ctk.CTkButton(self.breadcrumb_frame, text=folder['filename'], command=lambda f_id=folder['id']: self.refresh_files(f_id), height=24)
            btn.pack(side="left")

    def upload_files(self):
        filepaths = filedialog.askopenfilenames(title="Select File(s) to Upload")
        if not filepaths: return
        self._start_upload_session(filepaths, is_folder=False)

    def upload_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder to Upload")
        if not folder_path: return

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
        if not headers: return

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
                        self.app.after(0, self.op_progress_label.configure, {"text": f"Uploading ({i+1}/{total_items}): {filename} ({int(progress*100)}%)"})
                    return callback

                success = self._perform_upload(local_path, relative_path, headers, create_callback)
                if not success:
                    if not messagebox.askyesno("Upload Failed", f"Failed to upload {filename}. Continue with remaining files?"):
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

            response = requests.post(
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
        if not headers: return

        data = {'folder_name': folder_name.strip(), 'parent_id': self.current_folder_id or ''}

        def _create():
            try:
                # --- FIX: Corrected the API endpoint URL ---
                response = requests.post(f"{config.LICENSE_SERVER_URL}/files/api/create-folder", headers=headers, json=data, timeout=30)
                if response.status_code == 201:
                    self.app.after(0, lambda: self.refresh_files(self.current_folder_id, add_to_history=False))
                else:
                    try:
                        # Try to get a specific reason from the server's JSON response
                        reason = response.json().get('reason', 'An unknown server error occurred.')
                    except requests.exceptions.JSONDecodeError:
                        # If the response isn't JSON, show the raw text (e.g., "404 Not Found")
                        reason = f"Server returned a non-JSON response (Status: {response.status_code})."
                    self.app.after(0, messagebox.showerror, "Creation Failed", reason)
            except requests.exceptions.RequestException as e:
                self.app.after(0, messagebox.showerror, "Connection Error", str(e))

        threading.Thread(target=_create, daemon=True).start()

    # tabs/file_management_tab.py

    def share_selected_item(self):
        selected_iid = self.files_tree.selection()
        if not selected_iid: return

        item_data = self.item_map.get(int(selected_iid[0]))
        if not item_data or not item_data['is_folder']:
            messagebox.showwarning("Invalid Selection", "Please select a folder to share.")
            return

        headers = self.get_auth_headers()
        if not headers: return

        self.share_button.configure(state="disabled", text="Sharing...")

        def _share():
            try:
                response = requests.post(f"{config.LICENSE_SERVER_URL}/files/api/share-folder/{item_data['id']}", headers=headers, timeout=15)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        share_link = data.get('share_link')
                        self.app.clipboard_clear()
                        self.app.clipboard_append(share_link)
                        self.app.after(0, messagebox.showinfo, "Share Link Created", f"The share link for '{item_data['filename']}' has been copied to your clipboard.")
                    except ValueError:
                        self.app.after(0, messagebox.showerror, "Share Failed", "Received an invalid response from the server.")
                else:
                    try:
                        reason = response.json().get('reason', f"Server returned status code {response.status_code}")
                        self.app.after(0, messagebox.showerror, "Share Failed", reason)
                    except ValueError:
                        self.app.after(0, messagebox.showerror, "Share Failed", "Received an invalid error response from the server.")

            except requests.exceptions.RequestException as e:
                self.app.after(0, messagebox.showerror, "Share Failed", str(e))
            finally:
                # FIX: This ensures the button is always reset
                if self.share_button.winfo_exists():
                    self.app.after(0, self.share_button.configure, {"state": "normal", "text": "Share"})

        threading.Thread(target=_share, daemon=True).start()

    def download_selected_item(self):
        selected_iid = self.files_tree.selection()
        if not selected_iid: return

        item_data = self.item_map.get(int(selected_iid[0]))
        if not item_data: return

        if item_data['is_folder']:
            self.download_folder(item_data)
        else:
            self.download_file(item_data)

    def download_file(self, item_data):
        save_path = filedialog.asksaveasfilename(initialfile=item_data['filename'], title="Save File As")
        if not save_path: return

        headers = self.get_auth_headers()
        if not headers: return

        self.op_progress.grid()
        self.op_progress_label.grid()

        def _download():
            try:
                with requests.get(f"{config.LICENSE_SERVER_URL}/files/api/download/{item_data['id']}", headers=headers, stream=True, timeout=300) as r:
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
                                self.app.after(0, self.op_progress_label.configure, {"text": f"Downloading: {item_data['filename']} ({int(progress*100)}%)"})

                self.app.after(0, messagebox.showinfo, "Download Complete", f"Successfully downloaded '{item_data['filename']}'")
            except requests.exceptions.RequestException as e:
                self.app.after(0, messagebox.showerror, "Download Failed", str(e))
            finally:
                self.app.after(0, lambda: self.op_progress.grid_remove())
                self.app.after(0, lambda: self.op_progress_label.grid_remove())

        threading.Thread(target=_download, daemon=True).start()


    def download_folder(self, folder_data):
        save_location = filedialog.askdirectory(title=f"Select where to save the '{folder_data['filename']}' folder")
        if not save_location: return

        headers = self.get_auth_headers()
        if not headers: return

        self.op_progress.grid()
        self.op_progress_label.grid()

        def _download_worker():
            files_to_download = []

            def get_all_files(folder_id, current_path):
                url = f"{config.LICENSE_SERVER_URL}/files/api/list/{folder_id}"
                try:
                    response = requests.get(url, headers=headers, timeout=15)
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
                self.app.after(0, self.op_progress.set, (i / total_files))
                self.app.after(0, self.op_progress_label.configure, {"text": f"Downloading ({i+1}/{total_files}): {os.path.basename(file_info['path'])}"})

                local_path = os.path.join(save_location, file_info['path'])
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                try:
                    with requests.get(f"{config.LICENSE_SERVER_URL}/files/api/download/{file_info['id']}", headers=headers, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                except requests.exceptions.RequestException:
                    if not messagebox.askyesno("Download Failed", f"Failed to download {os.path.basename(file_info['path'])}. Continue?"):
                        break

            self.app.after(0, self.op_progress.set, 1.0)
            self.app.after(0, messagebox.showinfo, "Download Complete", f"Finished downloading folder '{folder_data['filename']}'.")
            self.app.after(5000, lambda: self.op_progress.grid_remove())
            self.app.after(5000, lambda: self.op_progress_label.grid_remove())

        threading.Thread(target=_download_worker, daemon=True).start()

    def delete_selected_item(self):
        selected_iid = self.files_tree.selection()
        if not selected_iid: return

        item_data = self.item_map.get(int(selected_iid[0]))
        if not item_data: return

        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to permanently delete '{item_data['filename']}'? This cannot be undone."):
            return

        headers = self.get_auth_headers()
        if not headers: return

        def _delete():
            try:
                response = requests.delete(f"{config.LICENSE_SERVER_URL}/files/api/delete/{item_data['id']}", headers=headers, timeout=30)
                if response.status_code == 200:
                    self.app.after(0, lambda: self.refresh_files(self.current_folder_id, add_to_history=False))
                else:
                    self.app.after(0, messagebox.showerror, "Deletion Failed", response.json().get('reason', 'Server error'))
            except requests.exceptions.RequestException as e:
                self.app.after(0, messagebox.showerror, "Deletion Failed", str(e))

        threading.Thread(target=_delete, daemon=True).start()

    def open_upgrade_page(self):
        if not self.app.license_info.get('key'):
            messagebox.showerror("Error", "No license key found to authenticate.")
            return

        auth_url = f"{config.LICENSE_SERVER_URL}/authenticate-from-app/{self.app.license_info['key']}"
        webbrowser.open_new_tab(auth_url)