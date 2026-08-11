# tabs/delete_applicant_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, os, sys, subprocess, json
from datetime import datetime


from src import config
from src.i18n import tr
from .base_tab import BaseAutomationTab
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException, openpyxl  # noqa: F401


# Excel export imports
try:
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

class DeleteApplicantTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="delete_applicant")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.selected_items = set()
        self.excel_panchayat = ""
        self._logged_keys = set()  # dedup: (jobcard_upper, name_upper, status)
        self._init_data_dir()
        self._create_widgets()

    def _init_data_dir(self):

        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            d = os.path.join(base, "data")
            self.data_dir = d if os.path.isdir(d) else os.path.expanduser("~")
        except Exception:
            self.data_dir = os.path.expanduser("~")

    # ──────────────────────────────────────────────────
    #  UI
    # ──────────────────────────────────────────────────
    def _create_widgets(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(6, weight=1)  # notebook expands

        # ── Header / intro card (pending-bills style) ──
        self._create_header_card(main, "🗑️", tr("tab.delete_applicant.title"), tr("tab.delete_applicant.subtitle"),
                                 icon_key="emoji_delete_applicant")

        # ── Row 1: Two dropdowns side by side (bordered card) ──
        dd_frame = ctk.CTkFrame(main, corner_radius=12, border_width=1,
                                border_color=("gray85", "gray30"))
        dd_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        dd_frame.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(dd_frame, text="App. Reason:",
                     font=ctk.CTkFont(size=13, weight="bold"))\
            .grid(row=0, column=0, padx=(15, 5), pady=8, sticky="w")
        app_reason_opts = ["Person Expired", "Voluntary Surrender",
                          "Person shifted to a new family", "Duplicate Applicant", "Fake Applicant"]
        self.reason_var = ctk.StringVar(value=app_reason_opts[2])
        self.reason_menu = ctk.CTkOptionMenu(dd_frame, variable=self.reason_var,
                                             values=app_reason_opts, width=220, height=32)
        self.reason_menu.grid(row=0, column=1, padx=5, pady=8, sticky="w")

        ctk.CTkLabel(dd_frame, text="Reg. Reason:",
                     font=ctk.CTkFont(size=13, weight="bold"))\
            .grid(row=0, column=2, padx=(15, 5), pady=8, sticky="w")
        reg_reason_opts = ["Non-existent in Panchayat", "Duplicate Job Card",
                          "Fake Job Card", "Voluntary Surrender"]
        self.reg_reason_var = ctk.StringVar(value=reg_reason_opts[0])
        self.reg_reason_menu = ctk.CTkOptionMenu(dd_frame, variable=self.reg_reason_var,
                                                 values=reg_reason_opts, width=220, height=32)
        self.reg_reason_menu.grid(row=0, column=3, padx=5, pady=8, sticky="w")

        # ── Row 2: Excel upload + status + select buttons (bordered card) ──
        mid_frame = ctk.CTkFrame(main, corner_radius=12, border_width=1,
                                 border_color=("gray85", "gray30"))
        mid_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
        mid_frame.grid_columnconfigure(2, weight=1)

        self.upload_btn = ctk.CTkButton(mid_frame, text="📁 Browse eKYC Excel",
                                        command=self.load_excel, width=145, height=32,
                                        fg_color=config.COLORS["blue"], hover_color=config.COLORS["blue_hover"],
                                        font=ctk.CTkFont(size=13))
        self.upload_btn.grid(row=0, column=0, padx=(15, 10), pady=6, sticky="w")

        self.excel_status_lbl = ctk.CTkLabel(mid_frame, text="No file loaded.",
                                             text_color="gray60", font=ctk.CTkFont(size=12))
        self.excel_status_lbl.grid(row=0, column=1, padx=5, pady=6, sticky="w")

        self.select_all_btn = ctk.CTkButton(mid_frame, text="☑ Select All",
            command=self.select_all, width=95,
            fg_color="transparent", border_width=1, text_color=("black", "white"),
            state="disabled", font=ctk.CTkFont(size=12))
        self.select_all_btn.grid(row=0, column=3, padx=(0, 5), pady=6, sticky="e")

        self.deselect_all_btn = ctk.CTkButton(mid_frame, text="☐ Deselect All",
            command=self.deselect_all, width=105,
            fg_color="transparent", border_width=1, text_color=("black", "white"),
            state="disabled", font=ctk.CTkFont(size=12))
        self.deselect_all_btn.grid(row=0, column=4, padx=(0, 15), pady=6, sticky="e")

        # ── Row 3: Info bar ──
        info_bar = ctk.CTkFrame(main, fg_color=("gray95", "gray20"), height=32)
        info_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))
        info_bar.grid_columnconfigure(0, weight=1)

        self.info_lbl = ctk.CTkLabel(info_bar,
            text=f"📅 Date: {datetime.now().strftime('%d/%m/%Y')}  |  🌐 Panchayat: auto-detected from Excel",
            font=ctk.CTkFont(size=12), text_color=("gray40", "gray60"), anchor="w")
        self.info_lbl.grid(row=0, column=0, sticky="w", padx=15, pady=4)

        # ── Row 4: Select count ──
        self.sel_count_lbl = ctk.CTkLabel(main,
            text="Selected: 0 / 0  —  Click any row to toggle ☐/☑",
            font=ctk.CTkFont(size=12), text_color=("gray50", "gray60"), anchor="w")
        self.sel_count_lbl.grid(row=4, column=0, sticky="w", padx=25, pady=(0, 2))

        # ── Row 5: Action Buttons ──
        self._create_action_buttons(main).grid(row=5, column=0, sticky="ew", padx=10, pady=5)

        # ── Row 6: Notebook ──
        notebook = ctk.CTkTabview(main)
        notebook.grid(row=6, column=0, sticky="nsew", padx=10, pady=5)

        # --- Tab: 📋 Loaded Data ---
        dt = notebook.add("📋 Loaded Data")
        dt.grid_columnconfigure(0, weight=1)
        dt.grid_rowconfigure(0, weight=1)

        cols = ("select", "sno", "jobcard", "name", "panchayat", "village", "abps", "ekyc")
        self.data_tree = ttk.Treeview(dt, columns=cols, show='headings', selectmode="none")
        headings = {"select":"✔","sno":"#","jobcard":"Job Card No","name":"Applicant Name",
                    "panchayat":"Panchayat","village":"Village","abps":"ABPS","ekyc":"eKYC"}
        for c in cols:
            self.data_tree.heading(c, text=headings[c])
        self.data_tree.column("select", width=50, anchor="center", minwidth=40)
        self.data_tree.column("sno", width=45, anchor="center", minwidth=35)
        self.data_tree.column("jobcard", width=180)
        self.data_tree.column("name", width=200)
        self.data_tree.column("panchayat", width=140)
        self.data_tree.column("village", width=130)
        self.data_tree.column("abps", width=70, anchor="center")
        self.data_tree.column("ekyc", width=70, anchor="center")
        self.data_tree.tag_configure('selected', background='#FFCCCC', foreground='#1E293B')
        self.data_tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.data_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        vsb = ttk.Scrollbar(dt, orient="vertical", command=self.data_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", pady=5)
        self.data_tree.configure(yscrollcommand=vsb.set)
        self.style_treeview(self.data_tree)

        # --- Tab: Results (with export button) ---
        res_tab = notebook.add("Results")
        res_tab.grid_columnconfigure(0, weight=1)
        res_tab.grid_rowconfigure(1, weight=1)

        export_bar = ctk.CTkFrame(res_tab, fg_color="transparent")
        export_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        self.export_btn = ctk.CTkButton(export_bar, text="📥 Export to Excel",
                                        command=self.export_report, fg_color=config.COLORS["green_export"],
                                        state="disabled", font=ctk.CTkFont(size=13))
        self.export_btn.pack(side="left", padx=(0, 10))

        self.export_filter = ctk.CTkOptionMenu(export_bar, width=140,
            values=["Export All", "Success Only", "Failed Only"])
        self.export_filter.pack(side="left")

        self.export_lbl = ctk.CTkLabel(export_bar, text="",
                                       font=ctk.CTkFont(size=12), text_color="gray60")
        self.export_lbl.pack(side="left", padx=10)

        cols_r = ("#", "Panchayat", "Deletion Date", "Jobcard No", "Applicant Name", "Status", "Details")
        self.results_tree = ttk.Treeview(res_tab, columns=cols_r, show='headings')
        width_map = {"#": 40, "Panchayat": 140, "Deletion Date": 100, "Jobcard No": 160,
                     "Applicant Name": 180, "Status": 90, "Details": 350}
        for c in cols_r:
            self.results_tree.heading(c, text=c)
            self.results_tree.column(c, width=width_map.get(c, 100))
        self.results_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.style_treeview(self.results_tree)

        # --- Tab: Logs & Status ---
        self._create_log_and_status_area(notebook)

    # ──────────────────────────────────────────────────
    #  Selection
    # ──────────────────────────────────────────────────

    def _on_tree_click(self, event):
        item = self.data_tree.identify_row(event.y)
        if item:
            if item in self.selected_items:
                self.selected_items.discard(item)
                self.data_tree.set(item, "select", "☐")
                self.data_tree.item(item, tags=())
            else:
                self.selected_items.add(item)
                self.data_tree.set(item, "select", "☑")
                self.data_tree.item(item, tags=('selected',))
            self._update_sel_count()

    def _update_sel_count(self):
        total = len(self.data_tree.get_children())
        sel = len(self.selected_items)
        self.sel_count_lbl.configure(
            text=f"Selected: {sel} / {total}  —  Click rows to toggle ☐/☑",
            text_color=config.COLORS["green_del_app"] if sel > 0 else ("gray50", "gray60"))

    def select_all(self):
        for item in self.data_tree.get_children():
            self.selected_items.add(item)
            self.data_tree.set(item, "select", "☑")
            self.data_tree.item(item, tags=('selected',))
        self._update_sel_count()

        for item in self.data_tree.get_children():
            self.selected_items.add(item)
            self.data_tree.set(item, "select", "☑")
        self._update_sel_count()

    def deselect_all(self):
        for item in self.data_tree.get_children():
            self.selected_items.discard(item)
            self.data_tree.set(item, "select", "☐")
            self.data_tree.item(item, tags=())
        self._update_sel_count()

        for item in self.data_tree.get_children():
            self.selected_items.discard(item)
            self.data_tree.set(item, "select", "☐")
        self._update_sel_count()

    # ──────────────────────────────────────────────────
    #  Excel Loading
    # ──────────────────────────────────────────────────

    def load_excel(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.data_dir,
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Select eKYC Report Excel File")
        if not file_path:
            return

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))

            if not all_rows or len(all_rows) < 2:
                messagebox.showerror(tr("dialogs.empty_file"), tr("dialogs.no_data_rows"), parent=self.app)
                wb.close(); return

            # ── Find header row ──
            hdr_idx = None; hdr_map = {}
            for ri, row in enumerate(all_rows):
                joined = " | ".join(str(c).lower().strip() if c else "" for c in row)
                has_jc = "job card" in joined or "jobcard" in joined
                has_name = "applicant" in joined or ("name" in joined and "scheme" not in joined and "report" not in joined)
                if has_jc and has_name:
                    hdr_idx = ri
                    for ci, h in enumerate(row):
                        ht = str(h).lower().strip() if h else ""
                        if "job card" in ht or "jobcard" in ht:       hdr_map["jobcard"] = ci
                        elif "applicant" in ht or ("name" in ht and "scheme" not in ht and "report" not in ht): hdr_map["name"] = ci
                        elif "s.no" in ht or "s no" in ht or ht == "#": hdr_map["sno"] = ci
                        elif "panchayat" in ht:
                            hdr_map["panchayat"] = ci
                        elif "village" in ht:
                            hdr_map["village"] = ci
                        elif "abps" in ht:
                            hdr_map["abps"] = ci
                        elif "ekyc" in ht:
                            hdr_map["ekyc"] = ci
                    break

            if "jobcard" not in hdr_map or "name" not in hdr_map:
                messagebox.showerror(tr("dialogs.invalid_format"), tr("dialogs.ekyc_columns_required"), parent=self.app)
                wb.close(); return

            # ── Clear ──
            for item in self.data_tree.get_children(): self.data_tree.delete(item)
            self.selected_items.clear()
            self.excel_panchayat = ""

            # ── Parse ──
            loaded = 0
            for ri in range(hdr_idx + 1, len(all_rows)):
                row = all_rows[ri]
                if not any(c is not None and str(c).strip() for c in row):
                    continue

                def v(col_key):
                    idx = hdr_map.get(col_key)
                    return str(row[idx]).strip() if idx is not None and idx < len(row) and row[idx] is not None else ""

                sno = v("sno"); jc = v("jobcard"); name = v("name")
                if not jc or not name or len(jc) < 5:
                    continue
                panch = v("panchayat")
                if not self.excel_panchayat and panch:
                    self.excel_panchayat = panch
                self.data_tree.insert("", "end",
                    values=("☐", sno, jc, name, panch, v("village"), v("abps"), v("ekyc")))
                loaded += 1

            wb.close()

            if loaded > 0:
                self.excel_status_lbl.configure(
                    text=f"✅ {loaded} applicants — {os.path.basename(file_path)}",
                    text_color=config.COLORS["green_del_app"])
                self.select_all_btn.configure(state="normal")
                self.deselect_all_btn.configure(state="normal")
                self._update_sel_count()
                if self.excel_panchayat:
                    self.info_lbl.configure(
                        text=f"📅 Date: {datetime.now().strftime('%d/%m/%Y')}  |  "
                             f"🌐 Panchayat: {self.excel_panchayat}")
                self.log_info(f"eKYC Excel loaded: {loaded} records. Panchayat: {self.excel_panchayat or 'N/A'}")
            else:
                self.excel_status_lbl.configure(text="❌ No valid records.", text_color=config.COLORS["red_error"])

        except ImportError:
            messagebox.showerror(tr("dialogs.library_missing"), tr("dialogs.openpyxl_required"), parent=self.app)
        except Exception as e:
            messagebox.showerror(tr("dialogs.error"), tr("dialogs.could_not_read_excel", error=e), parent=self.app)

    # ──────────────────────────────────────────────────
    #  Automation
    # ──────────────────────────────────────────────────
    def start_automation(self) -> None:
        if not self.selected_items:
            messagebox.showwarning(tr("dialogs.no_selection"),
                tr("dialogs.no_applicant_selected"))
            return

        # ⭐ Extract Treeview data in MAIN THREAD (thread-safe)
        # Read selected items + all their values from the Treeview
        # This avoids calling Tkinter widget methods from the background thread
        selected_data = []
        for item in self.selected_items:
            vals = self.data_tree.item(item, "values")
            if len(vals) >= 3:
                jc = str(vals[2]).strip().upper()
                name = str(vals[3]).strip().upper()
                if jc and name:
                    selected_data.append({
                        "jobcard": jc,
                        "name_upper": name,
                        "vals": list(vals),  # tuple → list for safe serialization
                    })

        if not selected_data:
            messagebox.showwarning(tr("dialogs.no_data"),
                tr("dialogs.could_not_read_applicant"))
            return

        inputs = {
            "reason": self.reason_var.get(),
            "reg_reason": self.reg_reason_var.get(),
            "panchayat": self.excel_panchayat,
            "date": datetime.now().strftime("%d/%m/%Y"),
            "selected_data": selected_data,
        }
        self.app.start_automation_thread(self.automation_key,
                                         self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_common_ui_state, True)
        self.app.clear_log(self.log_display)
        self.safe_tree_clear()
        self._logged_keys.clear()

        driver = self.app.get_driver()
        if not driver:
            self.app.after(0, self.set_common_ui_state, False)
            return

        wait = WebDriverWait(driver, 15)
        del_date = inputs["date"]
        panchayat = inputs.get("panchayat", "")
        reg_reason = inputs.get("reg_reason", "Voluntary Surrender")
        result_seq = [0]  # mutable counter for closure
        pending_reg_del = set()  # jobcards needing full registration deletion
        success_count = fail_count = skip_count = 0  # counted from tree at end

        # ── Build grouped data from pre-extracted selected_data ──
        grouped = {}
        for entry in inputs.get("selected_data", []):
            jc = entry["jobcard"]
            name = entry["name_upper"]
            vals = entry["vals"]
            grouped.setdefault(jc, []).append((name, vals))

        total_jc = len(grouped)

        def log_one(jc, app_name, status, detail):
            """Thread-safe insert with dedup."""
            key = (jc.upper(), app_name.upper(), status)
            if key in self._logged_keys:
                return
            self._logged_keys.add(key)
            result_seq[0] += 1
            seq = result_seq[0]
            self.app.after(0, lambda s=seq, j=jc, a=app_name, st=status, d=detail: \
                self.results_tree.insert("", "end",
                    values=(s, self.excel_panchayat or "-", del_date, j, a, st, d),
                    tags=('success',) if 'success' in st.lower()
                         else ('warning',) if 'skipped' in st.lower()
                         else ('failed',)))

        try:
            # ═══════════════════════════════════════════
            #  PHASE 1 — Delete Applicants
            # ═══════════════════════════════════════════
            for jc_idx, (jobcard, applicants) in enumerate(grouped.items()):
                if self.is_stopped():
                    break

                self.update_status(f"Jobcard {jc_idx+1}/{total_jc}: {jobcard}",
                                   (jc_idx + 1) / total_jc)
                self.log_info(f"Jobcard {jc_idx+1}/{total_jc}: {jobcard}")

                self.log_info("🌐 Opening Delete Applicant page...")
                driver.get(self.resolve_portal_url(config.DELETE_APPLICANT_CONFIG["url"]))

                # Track whether we found this jobcard on the portal
                # If yes but applicant processing fails → mark for reg deletion
                jobcard_found_on_portal = False

                # ── 1. Panchayat ──
                if panchayat:
                    status, _ = self._select_panchayat_or_skip(
                        driver, wait, panchayat,
                        ["ctl00_ContentPlaceHolder1_ddlpnch"])
                    if status == "gp":
                        self.log_info("📍 Panchayat dropdown not found (GP login).")
                    elif status == "selected":
                        self.log_info(f"📍 Selecting Panchayat: {panchayat}")
                        time.sleep(1.5)  # Brief wait for postback to begin
                    elif status == "notfound":                         self.log_warning(f"📍 Panchayat '{panchayat}' not found in dropdown.")
                # ── 2. Village (JS — fast) ──
                try:
                    self.log_info("🏘️  Selecting village from jobcard code...")
                    v_code = jobcard.split('/')[0].split('-')[-1]
                    v_dd = wait.until(EC.presence_of_element_located(
                        (By.ID, "ctl00_ContentPlaceHolder1_ddlvillage")))
                    found = driver.execute_script("""
                        var sel = arguments[0], suffix = arguments[1];
                        for (var i = 0; i < sel.options.length; i++) {
                            if (sel.options[i].value.endsWith(suffix)) {
                                sel.value = sel.options[i].value;
                                sel.dispatchEvent(new Event('change'));
                                return true;
                            }
                        }
                        return false;
                    """, v_dd, v_code)
                    if found:
                        self.log_info(f"     ✅ Village code {v_code} selected.")
                    else:
                        for nu, ov in applicants:
                            log_one(jobcard, ov[3], "Failed", f"Village code '{v_code}' not found.")
                        continue
                except Exception:
                    for nu, ov in applicants:
                        log_one(jobcard, ov[3], "Failed", "Invalid jobcard format.")
                    continue
                time.sleep(1.5)  # Brief wait for postback to begin

                # ── 3. Registration (JS — fast) ──
                try:
                    self.log_info("📋 Selecting Registration No (Jobcard)...")
                    reg_dd = wait.until(EC.presence_of_element_located(
                        (By.ID, "ctl00_ContentPlaceHolder1_ddlReg")))
                    found_reg = driver.execute_script("""
                        var sel = arguments[0], target = arguments[1].toUpperCase();
                        for (var i = 0; i < sel.options.length; i++) {
                            if (sel.options[i].text.toUpperCase() === target) {
                                sel.value = sel.options[i].value;
                                sel.dispatchEvent(new Event('change'));
                                return true;
                            }
                        }
                        return false;
                    """, reg_dd, jobcard)
                    if found_reg:
                        self.log_info(f"     ✅ Jobcard {jobcard} selected.")
                    else:
                        self.log_info(f"     ❌ Jobcard {jobcard} not found in registration dropdown.")
                        for nu, ov in applicants:
                            log_one(jobcard, ov[3], "Failed", "Jobcard not found in village.")
                        continue
                except Exception as e:
                    for nu, ov in applicants:
                        log_one(jobcard, ov[3], "Failed", f"Registration error: {str(e).splitlines()[0]}")
                    continue
                time.sleep(1.5)  # Brief wait for postback to begin

                # ── We found this jobcard on portal! ──
                jobcard_found_on_portal = True

                # ── 4. Process table ──
                self.log_info("📊 Scanning applicant table...")
                try:
                    table = wait.until(EC.presence_of_element_located(
                        (By.ID, "ctl00_ContentPlaceHolder1_grdData")))
                    rows = table.find_elements(By.TAG_NAME, "tr")[1:]

                    portal_names = set()
                    row_map = {}
                    for row in rows:
                        try:
                            ni = row.find_element(By.XPATH, ".//input[contains(@id, '_txtName')]")
                            # Normalize: uppercase + collapse whitespace
                            raw = ni.get_attribute("value") or ""
                            pn = " ".join(raw.strip().upper().split())
                            if pn:
                                portal_names.add(pn)
                                row_map[pn] = row
                        except NoSuchElementException:
                            continue

                    # Normalize applicant names from Excel the same way
                    normalized_applicants = []
                    for nu, ov in applicants:
                        norm_name = " ".join(nu.split())  # collapse spaces
                        normalized_applicants.append((norm_name, ov, nu))

                    self.log_info(f"Found {len(portal_names)} applicants on portal. Matching {len(normalized_applicants)} selected...")

                    filled_ok = []
                    for norm_name, ov, original_upper in normalized_applicants:
                        actual = ov[3]
                        if norm_name in portal_names:
                            try:
                                row = row_map[norm_name]
                                
                                # Use JS for checkbox — bypass "not interactable" errors
                                chk = row.find_element(By.XPATH, ".//input[contains(@id, '_chkDelete')]")
                                if not chk.is_selected():
                                    driver.execute_script("arguments[0].click();", chk)
                                
                                # Use JS for reason dropdown — find option by DISPLAY TEXT then select
                                reason_sel = row.find_element(By.XPATH, ".//select[contains(@id, '_ddlReason')]")
                                reason_val = inputs["reason"]
                                driver.execute_script("""
                                    var sel = arguments[0], txt = arguments[1];
                                    for (var i = 0; i < sel.options.length; i++) {
                                        if (sel.options[i].text.trim() === txt) {
                                            sel.value = sel.options[i].value;
                                            sel.dispatchEvent(new Event('change'));
                                            return true;
                                        }
                                    }
                                    return false;
                                """, reason_sel, reason_val)

                                # Use JS for date input — set value + dispatch input + blur (same as TAB key)
                                di = row.find_element(By.XPATH, ".//input[contains(@id, '_txtDate')]")
                                driver.execute_script("""
                                    arguments[0].value = arguments[1];
                                    arguments[0].dispatchEvent(new Event('input'));
                                    arguments[0].dispatchEvent(new Event('blur'));
                                """, di, del_date)
                                
                                self.log_info(f"     ✔ Filled: {actual}")
                                filled_ok.append((norm_name, ov))
                            except Exception as e:
                                err_msg = str(e).splitlines()[0]
                                # Translate technical Selenium errors to user-friendly messages
                                if "Element is not currently interactable" in err_msg or "interactable" in err_msg:
                                    friendly = "Could not fill form — portal field not ready yet."
                                elif "stale element" in err_msg.lower():
                                    friendly = "Page refreshed while filling — form data lost."
                                elif "timeout" in err_msg.lower():
                                    friendly = "Portal page not responding — timeout error."
                                else:
                                    friendly = err_msg[:80]
                                log_one(jobcard, actual, "Failed", friendly)
                        else:
                            log_one(jobcard, actual, "Failed",
                                    "Applicant name not found in portal table.")

                    # ⚠️  Registration deletion is ONLY triggered by the "cannot delete all" JS alert below.
                    # Other errors (head of household, stale elements, etc.) → NEVER delete registration.

                    # ── 5. Submit if any filled ──
                    if filled_ok:
                        self.log_info("📤 Submitting deletion...")
                        # Use JS click to avoid stale element errors (page may refresh via partial postback)
                        try:
                            btn = wait.until(EC.presence_of_element_located(
                                (By.ID, "ctl00_ContentPlaceHolder1_BtnDelete")))
                            driver.execute_script("arguments[0].click();", btn)
                        except Exception:
                            # Fallback: re-find and JS click (avoids stale element)
                            try:
                                btn2 = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_BtnDelete")
                                driver.execute_script("arguments[0].click();", btn2)
                            except Exception:
                                pass  # Let outer handler log the error

                        # Step A: Check for CLIENT-SIDE JS alert (before postback)
                        # This fires when trying to delete the LAST applicant in a family
                        alert_fired = False
                        alert_text = ""
                        try:
                            alert = WebDriverWait(driver, 3).until(EC.alert_is_present())
                            alert_text = alert.text
                            alert.accept()
                            alert_fired = True
                            self.log_info(f"     Alert: {alert_text}")
                        except TimeoutException:
                            pass  # No alert → postback happened normally

                        # Step B: If "cannot delete all" → schedule registration deletion, DONE with this jobcard
                        if alert_fired and "cannot delete all" in alert_text.lower():
                            pending_reg_del.add(jobcard)
                            self.log_warning(f"Cannot delete last applicant. Will delete full registration for {jobcard}.")
                            for nu, ov in filled_ok:
                                log_one(jobcard, ov[3], "Failed",
                                        "Cannot delete last applicant. Registration will be deleted.")
                            continue  # Skip lblmsg check — page didn't postback

                        # Step C: Wait for postback to complete, then read lblmsg
                        self.log_info("     Waiting for postback result...")
                        try:
                            lblmsg = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_lblmsg")))
                            msg_text = lblmsg.text.strip()
                        except TimeoutException:
                            msg_text = ""

                        if msg_text:
                            self.log_info(f"     📝 Page message: {msg_text}")
                        # Determine success: message contains "DELETED" or "has been marked"
                        if "deleted" in msg_text.lower() and "has been marked" in msg_text.lower():
                            for nu, ov in filled_ok:
                                log_one(jobcard, ov[3], "Success", msg_text)
                        elif msg_text:
                            for nu, ov in filled_ok:
                                log_one(jobcard, ov[3], "Failed", msg_text)
                        else:
                            # lblmsg not found or empty — maybe form succeeded without message
                            self.log_info("     ✅ No error message — assuming success.")
                            for nu, ov in filled_ok:
                                log_one(jobcard, ov[3], "Success", "Submitted successfully.")
                    else:
                        self.log_warning("⚠️  No applicants were filled.")
                except Exception as e:
                    self.log_error(f"Table error: {e}")
                    for nu, ov in applicants:
                        log_one(jobcard, ov[3], "Failed", f"Table error: {str(e).splitlines()[0]}")

            # ═══════════════════════════════════════════
            #  PHASE 2 — Delete Full Registration
            #  (for jobcards where last member couldn't be deleted)
            # ═══════════════════════════════════════════
            if pending_reg_del and not self.is_stopped():
                self.log_info(f"PHASE 2: Deleting {len(pending_reg_del)} full registration(s)")
                self.update_status(f"Deleting {len(pending_reg_del)} registrations...", 0.0)

                for reg_idx, jobcard in enumerate(sorted(pending_reg_del)):
                    if self.is_stopped():
                        break
                    self._process_reg_deletion(driver, wait, jobcard, panchayat,
                                               reg_reason, del_date, log_one,
                                               reg_idx, len(pending_reg_del))

            # ── Final summary (count from tree) ──
            app_done = result_seq[0]
            reg_done = len(pending_reg_del)
            success_count = 0
            fail_count = 0
            skip_count = 0
            for item_id in self.results_tree.get_children():
                vals = self.results_tree.item(item_id)['values']
                if len(vals) >= 5:
                    st = str(vals[4]).lower()
                    if 'success' in st:
                        success_count += 1
                    elif 'fail' in st or 'error' in st:
                        fail_count += 1
                    elif 'skip' in st:
                        skip_count += 1

            sep = "=" * 50
            summary = f"\n{sep}\n📊 Applicant Deletion Summary"
            summary += f"\n✅ Success: {success_count}"
            summary += f"\n❌ Failed: {fail_count}"
            summary += f"\n⏭️  Skipped: {skip_count}"
            summary += f"\n📁 Total processed: {app_done}"
            if reg_done:
                summary += f"\n🗑️  Registrations also deleted: {reg_done}"
            summary += f"\n{sep}"
            self.log_info(summary)
        except Exception as e:
            self.handle_error(e)
        finally:
            self.app.after(0, lambda: self.export_btn.configure(state="normal"))
            self.app.after(0, self.set_common_ui_state, False)
            self.update_status("Task Finished", 1.0)
            msg = f"Applicant deletion finished. ✅ {success_count}, ❌ {fail_count}, ⏭️ {skip_count}"
            if pending_reg_del:
                msg += f"\n🗑️  {len(pending_reg_del)} registration(s) also deleted."
            self.log_info(f"📊 {msg}")
    # ──────────────────────────────────────────────────
    #  Registration Deletion (Phase 2)
    # ──────────────────────────────────────────────────

    def _process_reg_deletion(self, driver, wait, jobcard, panchayat,
                               reg_reason, del_date, log_one,
                               reg_idx, total_reg):
        """
        Delete a full registration on DelReg.aspx page.
        Called when applicant deletion fails because only 1 member remains.
        """
        self.log_info(f"Reg-Deletion {reg_idx+1}/{total_reg}: {jobcard}")
        self.update_status(f"Reg-Deletion {reg_idx+1}/{total_reg}: {jobcard}",
                           (reg_idx + 1) / total_reg)

        try:
            # Navigate
            self.log_info("🌐 Opening Registration Delete page...")
            driver.get(self.resolve_portal_url(config.DEL_REG_CONFIG["url"]))

            # ── Select Panchayat ──
            if panchayat:
                try:
                    self.log_info(f"📍 Selecting Panchayat: {panchayat}")
                    panch_dd = wait.until(EC.presence_of_element_located(
                        (By.ID, "ctl00_ContentPlaceHolder1_ddlpnch")))
                    self._select_by_text_case_insensitive(Select(panch_dd), panchayat)
                    time.sleep(1.5)  # Brief wait for postback to begin
                except (TimeoutException, NoSuchElementException):
                    self.log_info("📍 Panchayat dropdown not found (GP login).")
            # ── Select Village (JS — fast) ──
            try:
                self.log_info("🏘️  Selecting village...")
                v_code = jobcard.split('/')[0].split('-')[-1]
                v_dd = wait.until(EC.presence_of_element_located(
                    (By.ID, "ctl00_ContentPlaceHolder1_ddlvillage")))
                found = driver.execute_script("""
                    var sel = arguments[0], suffix = arguments[1];
                    for (var i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].value.endsWith(suffix)) {
                            sel.value = sel.options[i].value;
                            sel.dispatchEvent(new Event('change'));
                            return true;
                        }
                    }
                    return false;
                """, v_dd, v_code)
                if not found:
                    self.log_info(f"     ❌ Village code '{v_code}' not found.")
                    log_one(jobcard, "[Registration]", "Failed",
                            f"Village code '{v_code}' not found on DelReg page.")
                    return
            except Exception:
                log_one(jobcard, "[Registration]", "Failed",
                        "Invalid jobcard format on DelReg page.")
                return
            time.sleep(1.5)  # Brief wait for postback to begin

            # ── Select Registration (JS — fast) ──
            try:
                self.log_info(f"📋 Selecting Registration: {jobcard}")
                reg_dd = wait.until(EC.presence_of_element_located(
                    (By.ID, "ctl00_ContentPlaceHolder1_ddlReg")))
                found_reg = driver.execute_script("""
                    var sel = arguments[0], target = arguments[1].toUpperCase();
                    for (var i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].text.toUpperCase() === target) {
                            sel.value = sel.options[i].value;
                            sel.dispatchEvent(new Event('change'));
                            return true;
                        }
                    }
                    return false;
                """, reg_dd, jobcard)
                if found_reg:
                    self.log_info(f"     ✅ Registration {jobcard} selected.")
                else:
                    self.log_info(f"     ❌ Jobcard {jobcard} not found on DelReg page.")
                    log_one(jobcard, "[Registration]", "Failed",
                            "Jobcard not found on DelReg page.")
                    return
            except Exception as e:
                self.log_info(f"     ❌ Registration error: {str(e).splitlines()[0]}")
                log_one(jobcard, "[Registration]", "Failed",
                        f"Reg selection error: {str(e).splitlines()[0]}")
                return
            time.sleep(1.5)  # Brief wait for postback to begin

            # ── Select Reason ──
            try:
                self.log_info(f"📝 Selecting reason: {reg_reason}")
                reason_dd = Select(wait.until(EC.presence_of_element_located(
                    (By.ID, "ctl00_ContentPlaceHolder1_ddlDelReason"))))
                reason_dd.select_by_visible_text(reg_reason)
            except Exception as e:
                # Try selecting by value if visible_text fails
                try:
                    reason_dd = Select(driver.find_element(
                        By.ID, "ctl00_ContentPlaceHolder1_ddlDelReason"))
                    reason_dd.select_by_value(reg_reason)
                except Exception:
                    log_one(jobcard, "[Registration]", "Failed",
                            f"Reason selection error: {str(e).splitlines()[0]}")
                    return

            # ── Submit ──
            self.log_info("📤 Submitting registration deletion...")
            try:
                submit_btn = wait.until(EC.element_to_be_clickable(
                    (By.ID, "ctl00_ContentPlaceHolder1_BtnSubmit")))
                driver.execute_script("arguments[0].click();", submit_btn)
            except Exception:
                try:
                    self._find(driver, By.ID, "ctl00_ContentPlaceHolder1_BtnSubmit").click()
                except Exception as e:
                    log_one(jobcard, "[Registration]", "Failed",
                            f"Submit button error: {str(e).splitlines()[0]}")
                    return

            # ── Check for JS alert (client-side validation) ──
            alert_fired = False
            alert_text = ""
            try:
                alert = WebDriverWait(driver, 3).until(EC.alert_is_present())
                alert_text = alert.text
                alert.accept()
                alert_fired = True
                self.log_info(f"     Alert: {alert_text}")
            except TimeoutException:
                pass

            # ── Check lblmsg for result (same as Phase 1) ──
            if not alert_fired:
                try:
                    lblmsg = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_lblmsg")))
                    msg_text = lblmsg.text.strip()
                    self.log_info(f"     📝 Page message: {msg_text}")
                    if "deleted" in msg_text.lower() and "has been marked" in msg_text.lower():
                        log_one(jobcard, "[Registration]", "Success", msg_text)
                    elif msg_text:
                        log_one(jobcard, "[Registration]", "Failed", msg_text)
                    else:
                        log_one(jobcard, "[Registration]", "Success",
                                "Registration deleted (no message).")
                except TimeoutException:
                    log_one(jobcard, "[Registration]", "Success",
                            "Registration deleted (no message).")
            else:
                # Alert fired — use alert text for result
                if "success" in alert_text.lower() or "deleted" in alert_text.lower():
                    log_one(jobcard, "[Registration]", "Success",
                            f"Registration deleted: {alert_text}")
                else:
                    log_one(jobcard, "[Registration]", "Failed", alert_text)

        except Exception as e:
            log_one(jobcard, "[Registration]", "Failed",
                    f"Reg deletion error: {str(e).splitlines()[0]}")

    # ──────────────────────────────────────────────────
    #  Export to Professional Excel
    # ──────────────────────────────────────────────────

    def export_report(self):
        # Use the base class professional Excel export
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename=f"delete_applicant_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            filter_mode=self.export_filter.get(),
            title_prefix="Applicant Deletion Report"
        )

    # ──────────────────────────────────────────────────
    #  Reset

    # ──────────────────────────────────────────────────
    #  Reset
    # ──────────────────────────────────────────────────
    def reset_ui(self) -> None:
        super().reset_ui()
        self.selected_items.clear()
        self._logged_keys.clear()
        self.excel_panchayat = ""
        self.excel_status_lbl.configure(text="No file loaded.", text_color="gray60")
        self.select_all_btn.configure(state="disabled")
        self.deselect_all_btn.configure(state="disabled")
        self.export_btn.configure(state="disabled")
        self.sel_count_lbl.configure(text="Selected: 0 / 0  —  Click rows to toggle ☐/☑",
                                     text_color=("gray50", "gray60"))
        self.info_lbl.configure(
            text=f"📅 Date: {datetime.now().strftime('%d/%m/%Y')}  |  🌐 Panchayat: auto-detected from Excel")
        for tree in (self.data_tree, self.results_tree):
            for item in tree.get_children():
                tree.delete(item)
