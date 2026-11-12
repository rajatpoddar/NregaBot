# tabs/pending_bills_tab.py
"""
Pending Material Bills Automation Tab

Scrapes pending material bills awaiting approval from the MGNREGA / Netnrega portal:
URL: https://nregade4.dord.gov.in/Netnrega/Bill_Approval_NRG.aspx

Features:
- Browser-based Selenium automation (user logs into MGNREGA portal).
- Supports iterating through:
  • "All Available Financial Years" (or a specific financial year).
  • "🌐 All Panchayats", "⭐ My Saved Panchayats", or a single Panchayat.
- Captures live pending bills from table #gvbillpaid1 into the results treeview.
- Executive-grade multi-sheet Excel export (Detailed Pending Bills + Panchayat Summary)
  with KPI cards, styling, number formatting, and auto-launch.
"""
import os
import re
import sys
import time
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

import customtkinter as ctk

from .base_tab import BaseAutomationTab
from src import config
from src.utils import get_logger
from src.i18n import tr

logger = get_logger()

# Dropdown label constants
ALL_FY_LABEL = "🗓 All Available Financial Years"
ALL_PANCHAYATS_LABEL = "🌐 All Panchayats"


class PendingBillsTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="pending_bills")
        self.collected_rows: List[Dict[str, Any]] = []

        self.fy_var = ctk.StringVar(value=ALL_FY_LABEL)
        self.panchayat_var = ctk.StringVar(value=ALL_PANCHAYATS_LABEL)

        self.config_vars = {
            "pending_bills_fy": self.fy_var,
            "pending_bills_panchayat": self.panchayat_var,
        }

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_widgets()
        self.load_inputs()

    # ────────────────────────────────────────────────────────────────────────
    # UI BUILDERS
    # ────────────────────────────────────────────────────────────────────────
    def _create_widgets(self) -> None:
        self.notebook = ctk.CTkTabview(self)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        settings_tab = self.notebook.add("Settings")
        results_tab = self.notebook.add("Results")
        self._create_log_and_status_area(self.notebook)  # adds "Logs & Status"

        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(2, weight=1)
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        # ════════════════════ SETTINGS TAB ════════════════════
        # ── Header / intro card ──
        header = ctk.CTkFrame(settings_tab, fg_color=("gray95", "gray20"), corner_radius=12)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ctk.CTkLabel(
            header, text=tr("form.pending_bills.scraper_title"),
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=(config.COLORS["blue_dark"], config.COLORS["blue_light"])
        ).pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            header,
            text="MGNREGA portal me pehle se login hona chahiye. Bot Bill Approval page se pending bills capture karega.",
            font=ctk.CTkFont(size=12),
            text_color=(config.COLORS["text_dark_alt"], config.COLORS["text_light"])
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # ── Inputs card ──
        inputs_card = ctk.CTkFrame(settings_tab, corner_radius=12, border_width=1,
                                   border_color=("gray85", "gray30"))
        inputs_card.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        inputs_card.grid_columnconfigure(1, weight=1)

        # Financial Year
        ctk.CTkLabel(inputs_card, text=tr("form.pending_bills.financial_year"),
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(16, 10), pady=(14, 8))
        self.fy_menu = ctk.CTkOptionMenu(inputs_card, variable=self.fy_var,
                                         values=self._fy_values(), width=280)
        self.fy_menu.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(14, 8))

        # Panchayat
        ctk.CTkLabel(inputs_card, text=tr("common.panchayat_col"),
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=1, column=0, sticky="w", padx=(16, 10), pady=(8, 14))
        self.panchayat_menu = ctk.CTkOptionMenu(inputs_card, variable=self.panchayat_var,
                                                values=self._panchayat_values(), width=280)
        self.panchayat_menu.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=(8, 14))

        # ── Info / instructions card ──
        info = ctk.CTkFrame(settings_tab, corner_radius=12, border_width=1,
                            border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        info.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        info.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            info, text=tr("common.how_it_works"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=(config.COLORS["blue_dark"], config.COLORS["blue_light"])
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        rules_text = (
            "• Automation run karne ke liye browser me MGNREGA portal pehle se LOGIN hona chahiye.\n"
            "• URL: https://nregade4.dord.gov.in/Netnrega/Bill_Approval_NRG.aspx\n"
            "• Financial Year: 'All Available Financial Years' ya koi specific financial year select karein.\n"
            "• Panchayat: '🌐 All Panchayats', '⭐ My Saved Panchayats', ya specific Panchayat chunein.\n"
            "• Bot ek-ek karke selected financial years aur panchayats ke pending bills scrape karega.\n"
            "• Task complete hone par executive-grade multi-sheet Excel report generate hogi."
        )
        ctk.CTkLabel(
            info, text=rules_text, justify="left", anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=(config.COLORS["text_dark_alt"], config.COLORS["text_light"])
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        # ── Action buttons ──
        action_frame = self._create_action_buttons(parent_frame=settings_tab)
        action_frame.grid(row=3, column=0, pady=10)

        # ════════════════════ RESULTS TAB ════════════════════
        res_btn_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        res_btn_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        self.export_button = ctk.CTkButton(
            res_btn_frame, text=tr("common.export_excel"), width=160, height=32,
            fg_color=config.COLORS["green_export"], hover_color="#0B5E0B",
            command=self.export_report, font=ctk.CTkFont(size=12, weight="bold"))
        self.export_button.pack(side="right")
        self.res_count_label = ctk.CTkLabel(
            res_btn_frame, text="0 bills captured", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=(config.COLORS["text_medium"], config.COLORS["text_light"]))
        self.res_count_label.pack(side="left", padx=5)

        cols = ("FY", "Panchayat", "Work Code", "Work Name", "Bill No.", "Bill Date",
                "Vendor Name", "Bill Amount (₹)", "Balance (₹)")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show="headings")
        widths = {
            "FY": 95, "Panchayat": 130, "Work Code": 170, "Work Name": 220,
            "Bill No.": 80, "Bill Date": 90, "Vendor Name": 160,
            "Bill Amount (₹)": 110, "Balance (₹)": 110
        }
        for col in cols:
            self.results_tree.heading(col, text=col)
            align = "w" if col in ("Panchayat", "Work Name", "Vendor Name") else "center"
            if "Amount" in col or "Balance" in col:
                align = "e"
            self.results_tree.column(col, width=widths[col], minwidth=70, anchor=align)
        self.results_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)

    # ────────────────────────────────────────────────────────────────────────
    # INPUT PERSISTENCE
    # ────────────────────────────────────────────────────────────────────────
    def load_inputs(self) -> None:
        try:
            data = self.app.history_manager.get_tab_inputs("pending_bills")
            if not data:
                return
            saved_fy = data.get("pending_bills_fy", "")
            if saved_fy and hasattr(self, "fy_menu") and saved_fy in self.fy_menu.cget("values"):
                self.fy_var.set(saved_fy)
            saved_panch = data.get("pending_bills_panchayat", "")
            if saved_panch and hasattr(self, "panchayat_var"):
                self.panchayat_var.set(saved_panch)
        except Exception:
            pass

    def save_inputs(self, inputs: Optional[Dict[str, Any]] = None) -> None:
        try:
            save_data = inputs or {
                "pending_bills_fy": self.fy_var.get(),
                "pending_bills_panchayat": self.panchayat_var.get(),
            }
            self.app.history_manager.save_tab_inputs_batch("pending_bills", save_data)
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────────────
    # DROPDOWN VALUES
    # ────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _last_n_financial_years(n: int = 6) -> List[str]:
        now = datetime.now()
        cur_start = now.year if now.month >= 4 else now.year - 1
        return [f"{cur_start - i}-{cur_start - i + 1}" for i in range(n)]

    @staticmethod
    def _current_financial_year() -> str:
        now = datetime.now()
        start = now.year if now.month >= 4 else now.year - 1
        return f"{start}-{start + 1}"

    def _fy_values(self) -> List[str]:
        return [ALL_FY_LABEL] + self._last_n_financial_years(6)

    def _panchayat_values(self) -> List[str]:
        saved = self._get_saved_panchayats()
        vals = [ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL]
        if saved:
            vals.extend(saved)
        return vals

    # ────────────────────────────────────────────────────────────────────────
    # UI STATE
    # ────────────────────────────────────────────────────────────────────────
    def set_ui_state(self, running: bool) -> None:
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        for w in (self.fy_menu, self.panchayat_menu):
            try:
                w.configure(state=state)
            except Exception:
                pass
        if hasattr(self, "export_button"):
            try:
                self.export_button.configure(state=state)
            except Exception:
                pass

    def safe_tree_insert(self, row: Dict[str, Any]) -> None:
        def _add():
            if not self._is_alive() or not hasattr(self, "results_tree"):
                return
            vals = (
                row.get("fy", ""),
                row.get("panchayat", ""),
                row.get("work_code", ""),
                row.get("work_name", ""),
                row.get("bill_no", ""),
                row.get("bill_date", ""),
                row.get("vendor_name", ""),
                f"₹ {float(row.get('bill_amount', 0) or 0):,.2f}",
                f"₹ {float(row.get('balance_to_paid', 0) or 0):,.2f}"
            )
            self.results_tree.insert("", "end", values=vals)
            if hasattr(self, "res_count_label"):
                self.res_count_label.configure(text=f"{len(self.collected_rows)} bills captured")
        self.app.after(0, _add)

    # ────────────────────────────────────────────────────────────────────────
    # PARSING ENGINE (Static, Testable)
    # ────────────────────────────────────────────────────────────────────────
    @staticmethod
    def parse_bills_table(html_content: str, fy: str = "", panchayat: str = "") -> List[Dict[str, Any]]:
        """Parses pending bills table #gvbillpaid1 from HTML string.
        Extracts all columns cleanly into dictionary records.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find("table", id="gvbillpaid1")
        if not table:
            return []

        rows: List[Dict[str, Any]] = []
        tbody = table.find("tbody")
        tr_elements = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for tr_elem in tr_elements:
            tds = tr_elem.find_all("td")
            if not tds:
                continue

            # Check for empty table indicator row
            if len(tds) == 1 or "no data available" in tr_elem.get_text().lower():
                continue

            def _clean(val: Any) -> str:
                return (val.get_text(strip=True) if val else "").strip()

            s_no = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblsno")))
            work_code = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblworkcode")))
            work_name = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblworkname")))
            total_sanction = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lbltfinsanction")))
            mat_sanction = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblsancformat")))
            total_mat_booked = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lbltmatbook")))
            total_paid = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblTotalPaid")))
            balance_to_paid = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblBalancedtoPaid")))
            work_status = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblworkstatus")))
            bill_no = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblbillNo")))
            bill_date = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblbilldate")))
            vendor_name = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblvendername")))
            vendor_tin = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lbltinno")))
            bill_amount = _clean(tr_elem.find(class_="billAmount") or tr_elem.find(id=lambda x: x and x.endswith("_amt")))
            tax_amount = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lbltaxamount")))
            material_list_no = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblmateriallstno")))
            fto_no = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblftono")))
            is_rejected = _clean(tr_elem.find(id=lambda x: x and x.endswith("_lblisrejected")))

            # Positional fallback if specific ID spans are missing
            if not work_code and len(tds) >= 17:
                s_no = s_no or _clean(tds[0])
                work_code = _clean(tds[1])
                work_name = _clean(tds[2])
                total_sanction = total_sanction or _clean(tds[3])
                mat_sanction = mat_sanction or _clean(tds[4])
                total_mat_booked = total_mat_booked or _clean(tds[5])
                total_paid = total_paid or _clean(tds[6])
                balance_to_paid = balance_to_paid or _clean(tds[7])
                work_status = work_status or _clean(tds[8])
                bill_no = bill_no or _clean(tds[9])
                bill_date = bill_date or _clean(tds[10])
                vendor_name = vendor_name or _clean(tds[11])
                bill_amount = bill_amount or _clean(tds[12])
                tax_amount = tax_amount or _clean(tds[13])
                material_list_no = material_list_no or _clean(tds[14])
                fto_no = fto_no or _clean(tds[15])
                is_rejected = is_rejected or _clean(tds[16])

            if not work_code and not bill_no:
                continue

            row_data: Dict[str, Any] = {
                "s_no": s_no,
                "fy": fy,
                "panchayat": panchayat,
                "work_code": work_code,
                "work_name": work_name,
                "total_sanction": total_sanction,
                "mat_sanction": mat_sanction,
                "total_mat_booked": total_mat_booked,
                "total_paid": total_paid,
                "balance_to_paid": balance_to_paid,
                "work_status": work_status,
                "bill_no": bill_no,
                "bill_date": bill_date,
                "vendor_name": vendor_name,
                "vendor_tin": vendor_tin,
                "bill_amount": bill_amount,
                "tax_amount": tax_amount,
                "material_list_no": material_list_no,
                "fto_no": fto_no,
                "is_rejected": is_rejected or "N",
            }
            rows.append(row_data)

        return rows

    def _scrape_table_all_pages(self, driver: Any, current_fy: str, cleaned_p: str) -> List[Dict[str, Any]]:
        """Scrapes all rows from table #gvbillpaid1.
        1. Attempts to select 'All' (-1) in DataTables length dropdown and trigger draw.
        2. Scrapes the table.
        3. If multiple pages remain, traverses them via the Next button (#gvbillpaid1_next).
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select

        # Attempt to set DataTables page length to All (-1)
        try:
            len_dropdowns = driver.find_elements(By.NAME, "gvbillpaid1_length")
            if len_dropdowns:
                len_sel = Select(len_dropdowns[0])
                for opt in len_sel.options:
                    if opt.get_attribute("value") == "-1" or "all" in opt.text.lower():
                        len_sel.select_by_value("-1")
                        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", len_dropdowns[0])
                        time.sleep(1.0)
                        break
        except Exception:
            pass

        try:
            driver.execute_script("""
                if (window.jQuery && $.fn.DataTable && $.fn.DataTable.isDataTable('#gvbillpaid1')) {
                    $('#gvbillpaid1').DataTable().page.len(-1).draw();
                }
            """)
            time.sleep(0.8)
        except Exception:
            pass

        collected_rows: List[Dict[str, Any]] = []
        seen_keys = set()
        max_pages = 50

        for page in range(1, max_pages + 1):
            tables = driver.find_elements(By.ID, "gvbillpaid1")
            if not tables:
                break

            table_html = tables[0].get_attribute("outerHTML")
            page_rows = self.parse_bills_table(table_html, fy=current_fy, panchayat=cleaned_p)
            for r in page_rows:
                key = (r.get("work_code"), r.get("bill_no"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    collected_rows.append(r)

            # Check if there is an active (not disabled) Next button
            next_btns = driver.find_elements(By.ID, "gvbillpaid1_next")
            if not next_btns:
                next_btns = driver.find_elements(By.CSS_SELECTOR, ".paginate_button.next")

            if not next_btns:
                break

            classes = next_btns[0].get_attribute("class") or ""
            if "disabled" in classes.lower():
                break  # Reached the last page

            # Click next page to fetch remaining 10 rows
            try:
                driver.execute_script("arguments[0].click();", next_btns[0])
                time.sleep(1.0)
            except Exception:
                break

        return collected_rows

    # ────────────────────────────────────────────────────────────────────────
    # START / AUTOMATION DISPATCH
    # ────────────────────────────────────────────────────────────────────────
    def start_automation(self) -> None:
        self.safe_tree_clear()
        self.collected_rows = []
        if hasattr(self, "res_count_label"):
            self.res_count_label.configure(text="0 bills captured")

        target_fy = self.fy_var.get().strip()
        target_panchayat = self.panchayat_var.get().strip()

        inputs = {
            "pending_bills_fy": target_fy,
            "pending_bills_panchayat": target_panchayat,
        }
        self.save_inputs(inputs)

        self.app.start_automation_thread(
            self.automation_key, self.run_automation_logic,
            args=(target_fy, target_panchayat))

    # ────────────────────────────────────────────────────────────────────────
    # AUTOMATION WORKER (Runs in background thread)
    # ────────────────────────────────────────────────────────────────────────
    def run_automation_logic(self, target_fy: str, target_panchayat: str) -> None:
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, lambda: self.app.clear_log(self.log_display))
        self.log_info("🚀 Starting Pending Material Bills extraction...")

        start_time = time.time()
        driver = self.app.get_driver()
        if not driver:
            self.log_error("❌ Browser driver not available.")
            self.app.after(0, self.set_ui_state, False)
            return

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.support import expected_conditions as EC

        wait = WebDriverWait(driver, 15)
        raw_url = getattr(config, "PENDING_BILLS_URL", "https://nregade4.dord.gov.in/Netnrega/Bill_Approval_NRG.aspx")
        target_url = self.resolve_portal_url(raw_url)

        self.log_info(f"🌐 Navigating to Bill Approval page: {target_url}")
        driver.get(target_url)

        # ── Verify page presence (user must be logged in) ──
        try:
            wait.until(lambda d: d.find_elements(By.ID, "ctl00_ContentPlaceHolder1_DDLFY") or
                                 d.find_elements(By.ID, "ctl00_ContentPlaceHolder1_ddlpnch"))
        except Exception:
            self.log_error("❌ Portal par Bill Approval page nahi mila.")
            self.log_error("👉 Sunishchit karein ki aap browser me MGNREGA portal par LOGGED IN hain aur session active hai.")
            self.app.after(0, self.set_ui_state, False)
            return

        # ── Step 1: Determine Financial Years to process ──
        fys_to_process: List[str] = []
        try:
            fy_elem = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDLFY")
            fy_select = Select(fy_elem)
            available_fys = [opt.text.strip() for opt in fy_select.options
                             if opt.text.strip() and "--SELECT" not in opt.text.strip().upper()]
        except Exception as e:
            self.log_warning(f"Could not read Financial Year options: {e}")
            available_fys = []

        if not target_fy or target_fy == ALL_FY_LABEL:
            fys_to_process = available_fys or [self._current_financial_year()]
            self.log_info(f"🗓 Mode: All Available Financial Years ({len(fys_to_process)} years found: {', '.join(fys_to_process)})")
        else:
            fys_to_process = [target_fy]
            self.log_info(f"🗓 Mode: Single Financial Year ({target_fy})")

        total_fys = len(fys_to_process)

        # ── Loop over Financial Years ──
        for fy_idx, current_fy in enumerate(fys_to_process):
            if self.is_stopped():
                self.log_warning("⏹️ Automation stopped by user.")
                break

            self.log_info(f"\n{'='*20} Financial Year [{fy_idx+1}/{total_fys}]: {current_fy} {'='*20}")

            # Select FY with postback wait
            try:
                fy_elem = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDLFY"))
                )
                curr_sel = Select(fy_elem).first_selected_option.text.strip()
                if curr_sel != current_fy:
                    self.log_info(f"Selecting FY: {current_fy}...")
                    old_fy_ref = fy_elem
                    Select(fy_elem).select_by_visible_text(current_fy)
                    self._wait_for_postback(driver, old_fy_ref, timeout=12)
                    time.sleep(1.5)
            except Exception as e:
                self.log_warning(f"Failed to select FY {current_fy}: {e}")

            # ── Step 2: Determine Panchayats for this FY ──
            panch_elem = self._find_panchayat_dropdown(driver, wait, ["ctl00_ContentPlaceHolder1_ddlpnch"], timeout=6)
            is_gp_login = panch_elem is None

            panchayats_to_process: List[str] = []
            if not is_gp_login:
                all_options: List[str] = []
                for _ in range(3):
                    try:
                        p_elem_fresh = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlpnch")
                        p_select = Select(p_elem_fresh)
                        all_options = [opt.text.strip() for opt in p_select.options
                                       if opt.text.strip() and "--SELECT" not in opt.text.strip().upper()
                                       and not (opt.get_attribute("value") or "").startswith("00")]
                        if all_options:
                            break
                    except Exception:
                        time.sleep(1.0)

                if self._is_my_saved_panchayat(target_panchayat):
                    panchayats_to_process = self._filter_panchayats_to_saved(all_options)
                    self.log_info(f"⭐ My Saved Panchayats mode: {len(panchayats_to_process)} panchayat(s) will be processed.")
                elif self._is_panchayat_label(target_panchayat):
                    panchayats_to_process = all_options
                    self.log_info(f"🌐 All Panchayats mode: {len(panchayats_to_process)} panchayats found.")
                else:
                    # Single target panchayat
                    panchayats_to_process = [target_panchayat]
            else:
                gp_name = self._read_gp_panchayat(driver, ["ctl00_ContentPlaceHolder1_lblBlocktxt", "ctl00_ContentPlaceHolder1_lblStatetxt"]) or "Panchayat"
                panchayats_to_process = [gp_name]
                self.log_info(f"Panchayat dropdown not found — GP Login mode detected for {gp_name}.")

            if not panchayats_to_process:
                self.log_warning(f"No panchayats to process for FY {current_fy}.")
                continue

            # ── Loop over Panchayats ──
            tot_p = len(panchayats_to_process)
            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped():
                    self.log_warning("⏹️ Automation stopped by user.")
                    break

                cleaned_p = self._clean_panchayat_value(p_name)
                self.log_info(f"--- [{fy_idx+1}/{total_fys}] Panchayat [{p_idx+1}/{tot_p}]: {cleaned_p} ({current_fy}) ---")
                self.app.after(0, self.update_status, f"{cleaned_p} ({current_fy})...", (p_idx + 1) / tot_p)

                if not is_gp_login:
                    selected_ok = False
                    for attempt in range(3):
                        try:
                            p_elem_live = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpnch"))
                            )
                            p_sel = Select(p_elem_live)
                            matched_text = None
                            target_lower = cleaned_p.lower()
                            for opt in p_sel.options:
                                opt_txt = opt.text.strip()
                                if target_lower == opt_txt.lower() or target_lower in opt_txt.lower():
                                    matched_text = opt_txt
                                    break

                            if not matched_text:
                                self.log_warning(f"Panchayat '{cleaned_p}' not found in dropdown. Skipping.")
                                break

                            curr_sel_text = p_sel.first_selected_option.text.strip()
                            if curr_sel_text == matched_text:
                                selected_ok = True
                                break

                            self.log_info(f"Selecting Panchayat: '{matched_text}'...")
                            old_p_ref = p_elem_live
                            p_sel.select_by_visible_text(matched_text)
                            self._wait_for_postback(driver, old_p_ref, timeout=12)
                            time.sleep(1.5)
                            selected_ok = True
                            break
                        except Exception as e:
                            time.sleep(1.0)

                    if not selected_ok and not is_gp_login:
                        continue

                # ── Step 3: Wait for table #gvbillpaid1 or message ──
                try:
                    WebDriverWait(driver, 8).until(
                        lambda d: d.find_elements(By.ID, "gvbillpaid1") or
                                 d.find_elements(By.ID, "ctl00_ContentPlaceHolder1_lblmsg")
                    )
                except Exception:
                    pass
                time.sleep(0.5)

                # Scrape table (with All length select and Next page traversal)
                try:
                    parsed_rows = self._scrape_table_all_pages(driver, current_fy, cleaned_p)
                    if parsed_rows:
                        self.collected_rows.extend(parsed_rows)
                        for r in parsed_rows:
                            self.safe_tree_insert(r)
                        self.log_info(f"✅ Found {len(parsed_rows)} pending bill(s) for {cleaned_p}.")
                    else:
                        self.log_info(f"ℹ️ 0 pending bills for {cleaned_p}.")
                except Exception as e:
                    self.log_warning(f"Error scraping table for {cleaned_p}: {e}")

        elapsed_time = round(time.time() - start_time, 1)
        mins, secs = divmod(int(elapsed_time), 60)
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"

        self.log_info(f"\n🎉 Extraction Complete! Captured {len(self.collected_rows)} bills in {time_str}.")

        # Thread-safe notification per Point 5 of nregabot-tab-builder
        self.activity_details = {
            "total": len(self.collected_rows),
            "success": len(self.collected_rows),
            "failed": 0,
            "time_taken": time_str
        }
        self.app.after(0, self.set_ui_state, False)
        self.show_automation_notification("success")

        # Switch to Results tab
        self.app.after(0, lambda: self.notebook.set("Results"))

        # Prompt export if rows were captured
        if self.collected_rows:
            self.app.after(500, self.export_report)

    # ────────────────────────────────────────────────────────────────────────
    # EXECUTIVE-GRADE EXCEL EXPORT (OpenPyXL)
    # ────────────────────────────────────────────────────────────────────────
    def export_report(self) -> None:
        if not self.collected_rows:
            messagebox.showinfo(tr("dialogs.no_data"),
                                "No pending bills captured to export.",
                                parent=self)
            return

        sel_fy = self.fy_var.get().strip()
        fin_year = sel_fy if (sel_fy and sel_fy != ALL_FY_LABEL) else ""
        reports_dir = self.app.get_report_path(self._report_category(), fin_year)
        os.makedirs(reports_dir, exist_ok=True)

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialdir=reports_dir,
            initialfile=f"Pending_Bills_{datetime.now().strftime('%d-%m-%Y_%H%M')}.xlsx",
            title=tr("form.pending_bills.save_report"))
        if not file_path:
            return

        try:
            self.write_excel_report(self.collected_rows, file_path)
            messagebox.showinfo(tr("dialogs.success"),
                                tr("dialogs.report_saved_success", path=file_path), parent=self)
            # Auto-open per Point 7
            try:
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.call(["open", file_path])
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror(tr("dialogs.export_error"), f"Failed to export Excel report: {e}", parent=self)

    @staticmethod
    def write_excel_report(rows: List[Dict[str, Any]], file_path: str) -> None:
        """Writes executive-grade multi-sheet Excel report per Point 7 of
        nregabot-tab-builder skill.
        Sheet 1: Pending Bills Details with KPI Cards & Navy headers
        Sheet 2: Panchayat Summary with Grand Total double border
        """
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()

        # Styles
        navy_header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        subtitle_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        zebra_gray_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        grand_total_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")

        # KPI Fills & Fonts
        kpi_total_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
        kpi_amount_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        kpi_amount_font = Font(name="Calibri", size=15, bold=True, color="166534")
        kpi_balance_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        kpi_balance_font = Font(name="Calibri", size=15, bold=True, color="991B1B")
        kpi_panch_fill = PatternFill(start_color="CFFAFE", end_color="CFFAFE", fill_type="solid")
        kpi_panch_font = Font(name="Calibri", size=15, bold=True, color="155E75")

        title_font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        subtitle_font = Font(name="Calibri", size=9, italic=True, color="475569")
        kpi_label_font = Font(name="Calibri", size=9, bold=True, color="475569")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        regular_font = Font(name="Calibri", size=10)
        bold_font = Font(name="Calibri", size=10, bold=True)

        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        right_align = Alignment(horizontal="right", vertical="center", wrap_text=False)

        thin_side = Side(style="thin", color="CBD5E1")
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        double_bottom = Border(left=thin_side, right=thin_side, top=thin_side,
                               bottom=Side(style="double", color="1F4E79"))

        # Calculations for KPIs
        total_bills = len(rows)
        total_amount = sum(float(r.get("bill_amount", 0) or 0) for r in rows)
        total_balance = sum(float(r.get("balance_to_paid", 0) or 0) for r in rows)
        unique_panchayats = len(set(r.get("panchayat", "") for r in rows if r.get("panchayat")))

        # ════════════════════ SHEET 1: DETAILS ════════════════════
        ws1 = wb.active
        ws1.title = "Pending Bills Details"
        ws1.views.sheetView[0].showGridLines = True

        headers1 = [
            "S.No", "Financial Year", "Panchayat", "Work Code", "Work Name",
            "Bill No.", "Bill Date", "Vendor Name", "Vendor TIN/GSTIN",
            "Bill Amount (₹)", "Tax Amount (₹)", "Balance to be Paid (₹)",
            "Total Financial Sanction (₹)", "Sanction for Material (₹)",
            "Total Material Booked (₹)", "Total Paid (₹)", "Work Status",
            "Material List No.", "FTO No.", "Rejected"
        ]
        num_cols1 = len(headers1)

        # Row 1: Header Banner
        ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols1)
        ws1.row_dimensions[1].height = 36
        banner1 = ws1.cell(row=1, column=1, value="MGNREGA - PENDING MATERIAL BILLS REPORT")
        banner1.font = title_font
        banner1.fill = navy_header_fill
        banner1.alignment = center_align

        # Row 2: Subtitle Branding Bar
        ws1.merge_cells(start_row=2, start_column=1, end_row=2, end_column=num_cols1)
        ws1.row_dimensions[2].height = 18
        sub1 = ws1.cell(row=2, column=1,
                        value=f"Generated via NregaBot (https://nregabot.com) | Date: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}")
        sub1.font = subtitle_font
        sub1.fill = subtitle_fill
        sub1.alignment = center_align

        # Row 4-5: KPI Summary Cards
        ws1.row_dimensions[4].height = 18
        ws1.row_dimensions[5].height = 28

        # Card 1: Total Bills (Cols A:C)
        ws1.merge_cells("A4:C4")
        ws1.merge_cells("A5:C5")
        ws1["A4"] = "TOTAL PENDING BILLS"
        ws1["A4"].font = kpi_label_font
        ws1["A4"].fill = kpi_total_fill
        ws1["A4"].alignment = center_align
        ws1["A5"] = total_bills
        ws1["A5"].font = Font(name="Calibri", size=15, bold=True, color="1F4E79")
        ws1["A5"].fill = kpi_total_fill
        ws1["A5"].alignment = center_align

        # Card 2: Total Amount (Cols D:F)
        ws1.merge_cells("D4:F4")
        ws1.merge_cells("D5:F5")
        ws1["D4"] = "TOTAL BILL AMOUNT (₹)"
        ws1["D4"].font = kpi_label_font
        ws1["D4"].fill = kpi_amount_fill
        ws1["D4"].alignment = center_align
        ws1["D5"] = total_amount
        ws1["D5"].font = kpi_amount_font
        ws1["D5"].fill = kpi_amount_fill
        ws1["D5"].alignment = center_align
        ws1["D5"].number_format = "₹ #,##0.00"

        # Card 3: Total Balance to be Paid (Cols G:I)
        ws1.merge_cells("G4:I4")
        ws1.merge_cells("G5:I5")
        ws1["G4"] = "TOTAL BALANCE TO BE PAID (₹)"
        ws1["G4"].font = kpi_label_font
        ws1["G4"].fill = kpi_balance_fill
        ws1["G4"].alignment = center_align
        ws1["G5"] = total_balance
        ws1["G5"].font = kpi_balance_font
        ws1["G5"].fill = kpi_balance_fill
        ws1["G5"].alignment = center_align
        ws1["G5"].number_format = "₹ #,##0.00"

        # Card 4: Panchayats (Cols J:L)
        ws1.merge_cells("J4:L4")
        ws1.merge_cells("J5:L5")
        ws1["J4"] = "PANCHAYATS COVERED"
        ws1["J4"].font = kpi_label_font
        ws1["J4"].fill = kpi_panch_fill
        ws1["J4"].alignment = center_align
        ws1["J5"] = unique_panchayats
        ws1["J5"].font = kpi_panch_font
        ws1["J5"].fill = kpi_panch_fill
        ws1["J5"].alignment = center_align

        # Apply borders to KPI blocks
        for r_kpi in (4, 5):
            for col_idx in range(1, 13):
                ws1.cell(row=r_kpi, column=col_idx).border = thin_border

        # Row 7: Table Headers
        ws1.row_dimensions[7].height = 26
        for col_idx, h in enumerate(headers1, 1):
            c = ws1.cell(row=7, column=col_idx, value=h)
            c.font = header_font
            c.fill = navy_header_fill
            c.alignment = center_align
            c.border = thin_border

        # Data Rows
        numeric_cols1 = {10, 11, 12, 13, 14, 15, 16}
        for r_idx, row in enumerate(rows, start=1):
            row_num = 7 + r_idx
            ws1.row_dimensions[row_num].height = 20
            fill = zebra_gray_fill if (r_idx % 2 == 0) else white_fill

            vals = [
                r_idx,
                row.get("fy", ""),
                row.get("panchayat", ""),
                row.get("work_code", ""),
                row.get("work_name", ""),
                row.get("bill_no", ""),
                row.get("bill_date", ""),
                row.get("vendor_name", ""),
                row.get("vendor_tin", ""),
                float(row.get("bill_amount", 0) or 0),
                float(row.get("tax_amount", 0) or 0),
                float(row.get("balance_to_paid", 0) or 0),
                float(row.get("total_sanction", 0) or 0),
                float(row.get("mat_sanction", 0) or 0),
                float(row.get("total_mat_booked", 0) or 0),
                float(row.get("total_paid", 0) or 0),
                row.get("work_status", ""),
                row.get("material_list_no", ""),
                row.get("fto_no", ""),
                row.get("is_rejected", "N")
            ]

            for c_idx, val in enumerate(vals, 1):
                cell = ws1.cell(row=row_num, column=c_idx, value=val)
                cell.font = regular_font
                cell.fill = fill
                cell.border = thin_border

                if c_idx in numeric_cols1:
                    cell.alignment = right_align
                    cell.number_format = "#,##0.00"
                elif c_idx in (3, 5, 8):  # Panchayat, Work Name, Vendor Name
                    cell.alignment = left_align
                else:
                    cell.alignment = center_align

        ws1.freeze_panes = "A8"

        # Auto-fit column widths for Sheet 1
        for col in ws1.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col[6:]:  # Start measuring from header row
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws1.column_dimensions[col_letter].width = min(max(max_len + 3, 11), 50)

        # ════════════════════ SHEET 2: SUMMARY ════════════════════
        ws2 = wb.create_sheet(title="Panchayat Summary")
        ws2.views.sheetView[0].showGridLines = True

        headers2 = [
            "S.No", "Financial Year", "Panchayat", "Pending Bills Count",
            "Total Bill Amount (₹)", "Total Balance to be Paid (₹)"
        ]
        num_cols2 = len(headers2)

        # Row 1: Header Banner
        ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols2)
        ws2.row_dimensions[1].height = 36
        banner2 = ws2.cell(row=1, column=1, value="PENDING MATERIAL BILLS - PANCHAYAT SUMMARY")
        banner2.font = title_font
        banner2.fill = navy_header_fill
        banner2.alignment = center_align

        # Row 2: Subtitle
        ws2.merge_cells(start_row=2, start_column=1, end_row=2, end_column=num_cols2)
        ws2.row_dimensions[2].height = 18
        sub2 = ws2.cell(row=2, column=1,
                        value=f"Generated via NregaBot (https://nregabot.com) | Date: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}")
        sub2.font = subtitle_font
        sub2.fill = subtitle_fill
        sub2.alignment = center_align

        # Row 4: Headers
        ws2.row_dimensions[4].height = 26
        for col_idx, h in enumerate(headers2, 1):
            c = ws2.cell(row=4, column=col_idx, value=h)
            c.font = header_font
            c.fill = navy_header_fill
            c.alignment = center_align
            c.border = thin_border

        # Aggregate summary by (FY, Panchayat)
        summary_dict: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for r in rows:
            key = (r.get("fy", ""), r.get("panchayat", ""))
            s = summary_dict.setdefault(key, {"count": 0, "amount": 0.0, "balance": 0.0})
            s["count"] += 1
            s["amount"] += float(r.get("bill_amount", 0) or 0)
            s["balance"] += float(r.get("balance_to_paid", 0) or 0)

        # Sort summary by amount descending
        sorted_summary = sorted(summary_dict.items(), key=lambda kv: kv[1]["amount"], reverse=True)

        for s_idx, ((fy_val, p_val), stats) in enumerate(sorted_summary, start=1):
            s_row = 4 + s_idx
            ws2.row_dimensions[s_row].height = 20
            fill = zebra_gray_fill if (s_idx % 2 == 0) else white_fill

            vals2 = [
                s_idx, fy_val, p_val, stats["count"], stats["amount"], stats["balance"]
            ]
            for c_idx, val in enumerate(vals2, 1):
                cell = ws2.cell(row=s_row, column=c_idx, value=val)
                cell.font = regular_font
                cell.fill = fill
                cell.border = thin_border
                if c_idx in (5, 6):
                    cell.alignment = right_align
                    cell.number_format = "₹ #,##0.00"
                elif c_idx == 3:
                    cell.alignment = left_align
                else:
                    cell.alignment = center_align

        # Grand Total Row
        gt_row = 5 + len(sorted_summary)
        ws2.row_dimensions[gt_row].height = 22
        gt_vals = ["", "GRAND TOTAL", "", total_bills, total_amount, total_balance]
        for c_idx, val in enumerate(gt_vals, 1):
            cell = ws2.cell(row=gt_row, column=c_idx, value=val)
            cell.font = bold_font
            cell.fill = grand_total_fill
            cell.border = double_bottom
            if c_idx in (5, 6):
                cell.alignment = right_align
                cell.number_format = "₹ #,##0.00"
            else:
                cell.alignment = center_align

        ws2.freeze_panes = "A5"

        # Auto-fit column widths for Sheet 2
        for col in ws2.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col[3:]:
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws2.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)

        wb.save(file_path)
