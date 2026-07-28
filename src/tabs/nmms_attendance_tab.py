# tabs/nmms_attendance_tab.py
# NMMS Daily Attendance Viewer & Report Generator
# New approach: "Scrape Current Page" workflow — reads whatever is already visible in browser

import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, os, re, json, requests, threading
from datetime import datetime



from .base_tab import BaseAutomationTab
from src.utils import get_logger
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._imports import *  # noqa: F403,F401

import pandas as pd

logger = get_logger()

NMMS_BASE_URL = "https://vbgramgrep.dord.gov.in/vbgramg/NMMS_DailyAttendance.aspx"  # kept for photo URL resolution


class NmmsAttendanceTab(BaseAutomationTab):
    """
    NMMS Daily Attendance scraper.
    Flow:
      1. User manually opens NMMS portal in browser, selects State/Date/Block → panchayat list appears
      2. 'Scrape Current Page' → reads the panchayat table already on screen
      3. User selects panchayats → Start
      4. For each panchayat: click MR link → scrape MR list → click each MR link → scrape detail
      5. Export professional Excel report
    """

    SUMMARY_HEADERS = [
        "S No.", "Panchayat", "Work Code", "Msr No.", "Work Name",
        "No. of Workers", "Taken By", "Designation",
        "Photo-1 Taken", "Photo-1 Uploaded", "Geo Coordinates (P1)",
        "Photo-2 Taken", "Photo-2 Uploaded", "Geo Coordinates (P2)",
        "Photo-1 Saved", "Photo-2 Saved",
    ]
    WORKER_HEADERS = [
        "S No.", "Panchayat", "Work Code", "Msr No.",
        "Job Card No.", "Worker Name", "Gender", "Attendance Date", "Status",
    ]
    PAN_OVERVIEW_HEADERS = [
        "S No.", "Panchayat", "No. of Works", "No. of Muster Rolls", "Persondays Generated",
    ]

    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="nmms_attendance")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)   # full tab is the scrollable area
        self._panchayat_data: list = []
        self._config_file = self.app.get_data_path("nmms_inputs.json")
        self._photo_paths_map: dict = {}  # row_index → (photo1_path, photo2_path)
        self._create_widgets()
        self._load_inputs()

    # UI
    def _create_widgets(self) -> None:

        # ── Outer scrollable wrapper so the entire tab scrolls ──────────────
        outer_scroll = ctk.CTkScrollableFrame(self)
        outer_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        outer_scroll.grid_columnconfigure(0, weight=1)
        # Make rows expand so the notebook fills remaining space
        outer_scroll.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(outer_scroll)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top.grid_columnconfigure(0, weight=1)

        # Instructions
        instr = (
            "STEPS:  1. In browser: manually open the NMMS portal, select State, "
            "Attendance Date, Block and click Go.  "
            "2. Come back here and click 'Scrape Current Page'.  "
            "3. Select panchayats and click ▶ Start."
        )
        ctk.CTkLabel(top, text=instr, justify="left", wraplength=950,
                     fg_color=("gray90", "#2A2A2A"), corner_radius=8,
                     padx=10, pady=8).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        # Button row
        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        self._scrape_btn = ctk.CTkButton(
            btn_row, text="🔍 Scrape Current Page", width=190,
            fg_color="#2E7D32", hover_color="#1B5E20", command=self._scrape_current_page_thread)
        self._scrape_btn.pack(side="left", padx=(0, 16))

        self._save_photos_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(btn_row, text="Download Group Photos",
                        variable=self._save_photos_var).pack(side="left")

        # Panchayat selection
        pan_outer = ctk.CTkFrame(top, fg_color="transparent")
        pan_outer.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 2))
        pan_outer.grid_columnconfigure(0, weight=1)

        pan_hdr = ctk.CTkFrame(pan_outer, fg_color="transparent")
        pan_hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(pan_hdr, text="Select Panchayats:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(pan_hdr, text="Select All", width=100,
                      fg_color="#1565C0", hover_color="#0D47A1",
                      command=self._select_all).pack(side="right", padx=(4, 0))
        ctk.CTkButton(pan_hdr, text="Clear All", width=90, command=self._clear_all).pack(side="right")

        self._pan_scroll = ctk.CTkScrollableFrame(pan_outer, height=120)
        self._pan_scroll.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self._pan_checkboxes: dict = {}

        self._pan_info_lbl = ctk.CTkLabel(
            pan_outer, text_color="gray50", justify="left", wraplength=950,
            text="No panchayats loaded. Navigate to panchayat list in browser, then click 'Scrape Current Page'.")
        self._pan_info_lbl.grid(row=2, column=0, sticky="w", pady=(2, 2))

        # Start / Stop / Retry / Reset buttons
        self._create_action_buttons(parent_frame=top).grid(row=3, column=0, pady=(8, 10))

        # Bottom notebook — placed inside the scrollable wrapper
        nb = ctk.CTkTabview(outer_scroll)
        nb.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._build_summary_tab(nb.add("MR Summary"))
        self._build_workers_tab(nb.add("Workers Detail"))
        self._create_log_and_status_area(parent_notebook=nb)

    def _build_summary_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="📊 Export Excel Report",
                      fg_color="#2E7D32", hover_color="#1B5E20",
                      command=self._export_excel).pack(side="left", padx=(0, 8))
        ctk.CTkButton(toolbar, text="Clear Results", width=100,
                      fg_color=("gray70", "#4A4A4A"), text_color="white",
                      command=self._clear_results).pack(side="left")

        self.results_tree = ttk.Treeview(tab, columns=self.SUMMARY_HEADERS, show="headings")
        _w = {"S No.": 45, "Panchayat": 100, "Work Code": 195, "Msr No.": 55,
              "Work Name": 190, "No. of Workers": 80, "Taken By": 130, "Designation": 100,
              "Photo-1 Taken": 140, "Photo-1 Uploaded": 140, "Geo Coordinates (P1)": 150,
              "Photo-2 Taken": 140, "Photo-2 Uploaded": 140, "Geo Coordinates (P2)": 150,
              "Photo-1 Saved": 85, "Photo-2 Saved": 85}
        for col in self.SUMMARY_HEADERS:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=_w.get(col, 100), minwidth=40)

        self.results_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        vsb = ctk.CTkScrollbar(tab, command=self.results_tree.yview)
        hsb = ctk.CTkScrollbar(tab, orientation="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")
        self.style_treeview(self.results_tree)

    def _build_workers_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="📋 Export Workers CSV",
                      command=lambda: self.export_treeview_to_csv(
                          self.workers_tree, "NMMS_Workers_Detail.csv")).pack(side="left")

        self.workers_tree = ttk.Treeview(tab, columns=self.WORKER_HEADERS, show="headings")
        _ww = {"S No.": 45, "Panchayat": 100, "Work Code": 180, "Msr No.": 55,
               "Job Card No.": 160, "Worker Name": 180, "Gender": 55,
               "Attendance Date": 100, "Status": 70}
        for col in self.WORKER_HEADERS:
            self.workers_tree.heading(col, text=col)
            self.workers_tree.column(col, width=_ww.get(col, 100), minwidth=30)

        self.workers_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        vsb2 = ctk.CTkScrollbar(tab, command=self.workers_tree.yview)
        self.workers_tree.configure(yscroll=vsb2.set)
        vsb2.grid(row=1, column=1, sticky="ns")
        self.style_treeview(self.workers_tree)

    # CONFIG / HELPERS
    def _save_inputs(self):
        try:
            self.app.history_manager.save_tab_input("nmms", "save_photos", str(self._save_photos_var.get()))
        except Exception:
            pass

    def _load_inputs(self):
        try:
            val = self.app.history_manager.get_tab_input("nmms", "save_photos", "True")
            self._save_photos_var.set(val.lower() == "true")
        except Exception:
            pass

    def _select_all(self):
        for v in self._pan_checkboxes.values(): v.set(True)

    def _clear_all(self):
        for v in self._pan_checkboxes.values(): v.set(False)

    def _clear_results(self):
        for i in self.results_tree.get_children(): self.results_tree.delete(i)
        for i in self.workers_tree.get_children(): self.workers_tree.delete(i)
        self._photo_paths_map.clear()
        self.update_status("Cleared.", 0)

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        s = "disabled" if running else "normal"
        self._scrape_btn.configure(state=s)
    def reset_ui(self) -> None:
        self._clear_results()
        self.update_status("Ready", 0)
        self.log_info("Reset complete.")
    def _get_driver(self):
        driver = self.app.get_driver()
        if not driver:
            messagebox.showwarning(
                "Browser Not Connected",
                "No browser found.\n\nPlease launch Chrome/Edge from the app and log in to NREGA portal first.")
        return driver

    # PHASE 2 — SCRAPE CURRENT PAGE
    def _scrape_current_page_thread(self):
        driver = self._get_driver()
        if not driver:
            return
        self._scrape_btn.configure(state="disabled", text="Scraping...")
        threading.Thread(target=self._scrape_current_page_logic, args=(driver,), daemon=True).start()

    def _scrape_current_page_logic(self, driver):
        try:
            self.log_info("Reading panchayat table from current browser page...")
            self.log_info(f"  Current URL: {driver.current_url}")
            try:
                WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.XPATH, "//table//tr[td]")))
            except TimeoutException:
                body = driver.find_element(By.TAG_NAME, "body").text[:400]
                self.app.after(0, lambda t=body: messagebox.showwarning(
                    "No Table Found",
                    "No data table found on the current browser page.\n\n"
                    "Please navigate to the panchayat list in your browser first,\n"
                    "then click 'Scrape Current Page' again.\n\n"
                    f"Page preview:\n{t}"))
                return

            rows = driver.find_elements(By.XPATH, "//table//tr")
            data = []
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 4:
                    continue
                try:
                    sno = cells[0].text.strip()
                    if not sno.isdigit():
                        continue
                    pan = cells[1].text.strip()
                    # Skip if panchayat cell is empty, "total", or is just a number (column-number header row)
                    if not pan or pan.lower() == "total" or pan.isdigit():
                        continue
                    no_works   = cells[2].text.strip() if len(cells) > 2 else ""
                    no_mr      = cells[3].text.strip() if len(cells) > 3 else ""
                    persondays = cells[4].text.strip() if len(cells) > 4 else ""
                    mr_href = ""
                    try:
                        mr_href = cells[3].find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                    except NoSuchElementException:
                        pass
                    data.append({"sno": sno, "name": pan, "no_works": no_works,
                                 "no_mr": no_mr, "persondays": persondays, "mr_href": mr_href})
                    self.app.log_message(self.log_display,
                        f"  Found: {pan} | MRs: {no_mr} | href: {(mr_href[:70] + '...') if len(mr_href) > 70 else mr_href}")
                except Exception:
                    continue

            self.app.after(0, lambda d=data: self._populate_panchayat_checkboxes(d))
        except Exception as e:
            self.log_error(f"Scrape error: {e}")
            self.app.after(0, lambda err=str(e): messagebox.showerror("Scrape Error", f"Could not read the page:\n{err}"))
        finally:
            self.app.after(0, lambda: self._scrape_btn.configure(state="normal", text="🔍 Scrape Current Page"))

    def _populate_panchayat_checkboxes(self, data: list):
        for w in self._pan_scroll.winfo_children(): w.destroy()
        self._pan_checkboxes.clear()
        self._panchayat_data = data

        if not data:
            self._pan_info_lbl.configure(text="No panchayats found. Make sure panchayat list is visible in browser.")
            self.log_warning("No panchayats found on page.")
            return

        self._pan_scroll.grid_columnconfigure(0, weight=1)
        for i, item in enumerate(data):
            var = ctk.BooleanVar(value=True)
            label = f"{item['name']}  (Works: {item['no_works']} | MRs: {item['no_mr']} | Persondays: {item['persondays']})"
            ctk.CTkCheckBox(self._pan_scroll, text=label, variable=var).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            self._pan_checkboxes[item["name"]] = var

        self._pan_info_lbl.configure(text=f"✅ {len(data)} panchayat(s) loaded. Select desired ones and click ▶ Start.")
        self.log_success(f"Scraped {len(data)} panchayats.")
    # PHASE 3 — START AUTOMATION
    def start_automation(self) -> None:
        selected = [n for n, v in self._pan_checkboxes.items() if v.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one panchayat.")
            return
        self._save_inputs()
        self.log_info(f"Starting for {len(selected)} panchayat(s)...")
        self.app.start_automation_thread(self.automation_key, self._run_scrape_logic, args=(selected,))

    def _run_scrape_logic(self, selected_panchayats: list):
        self.app.after(0, self.set_ui_state, True)
        self.app.after(0, self.update_status, "Initializing...", 0.0)

        driver = self._get_driver()
        if not driver:
            self.app.after(0, self.set_ui_state, False)
            return

        date_safe = datetime.now().strftime("%d-%m-%Y")
        photos_dir = os.path.join(self.app.get_user_downloads_path(), "NregaBot", "NMMS_Attendance", date_safe, "Photos")
        os.makedirs(photos_dir, exist_ok=True)

        page1_url = driver.current_url
        summary_sno = len(self.results_tree.get_children())
        worker_sno  = len(self.workers_tree.get_children())
        total = len(selected_panchayats)
        # photo_paths_map: maps treeview item iid → (photo1_path, photo2_path)
        if not hasattr(self, "_photo_paths_map"):
            self._photo_paths_map: dict = {}
        # Don't clear existing entries — append so re-runs accumulate

        try:
            for p_idx, pan_name in enumerate(selected_panchayats):
                if self.is_stopped():
                    self.log_warning("Stop signal received.")
                    break

                self.app.after(0, self.update_status, f"Panchayat {p_idx+1}/{total}: {pan_name}", p_idx / total)
                self.log_info(f"▶ {pan_name}")
                pan_info = next((d for d in self._panchayat_data if d["name"] == pan_name), None)
                if not pan_info:
                    self.log_warning(f"  ⚠ No data for '{pan_name}'")
                    continue

                mr_rows = self._click_and_scrape_mr_list(pan_info, driver, pan_name)
                if not mr_rows:
                    self.log_warning(f"  No MRs found for {pan_name}.")
                    # Go back to panchayat list if we navigated away
                    if driver.current_url != page1_url:
                        driver.back()
                        time.sleep(2)
                    continue

                self.log_info(f"  {len(mr_rows)} MR(s) found.")
                # At this point driver is on MR list page for this panchayat
                mr_list_url = driver.current_url

                for mr_info in mr_rows:
                    if self.is_stopped():
                        break
                    summary_sno += 1
                    # Ensure we're on MR list page before clicking MR detail
                    if driver.current_url != mr_list_url:
                        driver.get(mr_list_url)
                        time.sleep(2)
                    detail = self._scrape_mr_detail(mr_info, driver, pan_name, photos_dir)
                    # _scrape_mr_detail does driver.back() → returns to MR list page

                    srow = (summary_sno, pan_name,
                            mr_info.get("work_code",""), mr_info.get("msr_no",""),
                            detail.get("work_name",""), detail.get("worker_count","0"),
                            detail.get("taken_by",""), detail.get("designation",""),
                            detail.get("photo1_taken",""), detail.get("photo1_uploaded",""),
                            detail.get("photo1_geo",""),
                            detail.get("photo2_taken",""), detail.get("photo2_uploaded",""),
                            detail.get("photo2_geo",""),
                            detail.get("photo1_saved","N/A"), detail.get("photo2_saved","N/A"))
                    self.app.after(0, lambda r=srow: self.results_tree.insert("", "end", values=r))

                    # Store photo paths for Excel embedding (keyed by sequential index)
                    row_key = summary_sno  # int key at time of insertion
                    p1_path = detail.get("photo1_path", "")
                    p2_path = detail.get("photo2_path", "")
                    if p1_path or p2_path:
                        self._photo_paths_map[row_key] = (p1_path, p2_path)

                    for w in detail.get("workers", []):
                        worker_sno += 1
                        wrow = (worker_sno, pan_name,
                                mr_info.get("work_code",""), mr_info.get("msr_no",""),
                                w.get("jobcard",""), w.get("name",""),
                                w.get("gender",""), w.get("date",""), w.get("status",""))
                        self.app.after(0, lambda r=wrow: self.workers_tree.insert("", "end", values=r))

                # After all MRs for this panchayat: go back to panchayat list
                if driver.current_url != page1_url:
                    driver.back()
                    time.sleep(2)

            self.app.after(0, self.update_status, "Completed!", 1.0)
            self.log_success(f"Done! {summary_sno} MR(s) scraped.")
            cnt = summary_sno
            total_workers = len(self.workers_tree.get_children()) if hasattr(self, 'workers_tree') else 0
            self.app.after(200, lambda: self.app.log_message(self.log_display, f"📊 NMMS Attendance Complete: {cnt} MRs scraped, {total_workers} workers found. Photos: {photos_dir}"))

        except Exception as e:
            self.log_error(f"Critical error: {e}")
            self.app.after(0, lambda err=str(e): messagebox.showerror("Error", f"Scraping failed:\n{err}"))
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")

    # SCRAPING HELPERS
    def _click_and_scrape_mr_list(self, pan_info: dict, driver, pan_name: str) -> list:
        """Navigate to MR list page by clicking the link (not via URL), then scrape MR rows."""
        mr_rows = []
        try:
            # Always click the link on the current page — never use driver.get(href)
            self.log_info(f"  Clicking MR link for '{pan_name}'...")
            try:
                link = driver.find_element(
                    By.XPATH,
                    f"//tr[td[normalize-space()='{pan_name}']]//td[4]//a"
                )
                link.click()
            except NoSuchElementException:
                # Fallback: find any link in a row containing pan_name
                try:
                    link = driver.find_element(
                        By.XPATH,
                        f"//tr[td[contains(normalize-space(),'{pan_name}')]]//a"
                    )
                    link.click()
                except NoSuchElementException:
                    self.log_warning(f"  ⚠ MR link not found for '{pan_name}'.")
                    return []

            time.sleep(2)

            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//table//tr[td]")))
            except TimeoutException:
                self.log_warning("  ⚠ Timeout on MR list page.")
                return []

            for row in driver.find_elements(By.XPATH, "//table//tr"):
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 6:
                    continue
                try:
                    sno_text = cells[0].text.strip()
                    if not sno_text.isdigit():
                        continue
                    work_code  = cells[4].text.strip()
                    msr_cell   = cells[5]
                    msr_no     = msr_cell.text.strip()
                    # Skip column-number header rows (work_code is a plain digit like "5")
                    if work_code.isdigit() and not msr_no or msr_no.isdigit() and len(msr_no) <= 2:
                        continue
                    # Skip if work_code looks like a column number (single digit, no slash)
                    if work_code.isdigit() and "/" not in work_code:
                        continue
                    persondays = cells[6].text.strip() if len(cells) > 6 else ""
                    detail_href = ""
                    try:
                        detail_href = msr_cell.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                    except NoSuchElementException:
                        pass
                    mr_rows.append({"work_code": work_code, "msr_no": msr_no,
                                    "persondays": persondays, "detail_href": detail_href})
                except Exception:
                    continue
        except Exception as e:
            self.log_error(f"  MR list error: {e}")
            return mr_rows

    def _scrape_mr_detail(self, mr_info: dict, driver, pan_name: str, photos_dir: str) -> dict:
        """Navigate to MR detail page by clicking the link, scrape photo info + worker table."""
        detail = {
            "work_name": "",
            "photo1_taken": "", "photo1_uploaded": "", "photo1_geo": "",
            "photo2_taken": "", "photo2_uploaded": "", "photo2_geo": "",
            "taken_by": "", "designation": "",
            "worker_count": "0", "workers": [],
            "photo1_saved": "No", "photo2_saved": "No",
            "photo1_path": "", "photo2_path": "",  # actual file paths for Excel embedding
        }
        msr_no = mr_info.get("msr_no", "")
        if not msr_no:
            self.log_warning("    ⚠ No MSR no for this row.")
            return detail

        try:
            self.app.log_message(self.log_display,
                f"    MR {msr_no} | {mr_info.get('work_code','')}")
            # Click the link instead of navigating via URL
            try:
                link = driver.find_element(
                    By.XPATH,
                    f"//a[normalize-space()='{msr_no}']"
                )
                link.click()
            except NoSuchElementException:
                # Fallback: find link in row containing this msr_no
                try:
                    link = driver.find_element(
                        By.XPATH,
                        f"//tr[td[normalize-space()='{msr_no}']]//a"
                    )
                    link.click()
                except NoSuchElementException:
                    self.app.log_message(self.log_display,
                        f"    ⚠ Could not find clickable link for MR {msr_no}.", "warning")
                    return detail
            time.sleep(2)
            page_src = driver.page_source

            # Work Name — from the page heading area
            try:
                # The page shows "Work Name : <name>" in a dedicated paragraph/td
                wn_el = driver.find_element(
                    By.XPATH,
                    "//p[contains(.,'Work Name')] | //td[contains(.,'Work Name') and not(contains(.,'Work Code'))]"
                )
                wn_text = wn_el.text
                detail["work_name"] = self._extract_field(wn_text, ["Work Name"])
            except NoSuchElementException:
                detail["work_name"] = self._extract_field(page_src, ["Work Name"])

            if not detail["work_name"]:
                # Try regex directly on page source
                m = re.search(
                    r'Work\s+Name\s*:?\s*<[^>]*>\s*([^<\r\n]{5,})',
                    page_src, re.IGNORECASE
                )
                if m:
                    detail["work_name"] = m.group(1).strip()

            # Photo info blocks
            self._extract_photo_info(driver, page_src, 1, detail)
            self._extract_photo_info(driver, page_src, 2, detail)
            
            # Log photo info extraction status
            p1_ok = bool(detail.get("photo1_taken") or detail.get("photo1_uploaded"))
            p2_ok = bool(detail.get("photo2_taken") or detail.get("photo2_uploaded"))
            if p1_ok:
                self.app.log_message(self.log_display, 
                    f"      Photo-1: {detail.get('photo1_taken','')} | By: {detail.get('taken_by','')}")
            else:
                self.log_warning("      ⚠ Photo-1 info not found")
                if p2_ok:
                    self.app.log_message(self.log_display, f"      Photo-2: {detail.get('photo2_taken','')}")

            # Photos download
            if self._save_photos_var.get():
                detail["photo1_saved"], detail["photo1_path"] = self._download_photo(1, pan_name, mr_info, photos_dir, driver)
                detail["photo2_saved"], detail["photo2_path"] = self._download_photo(2, pan_name, mr_info, photos_dir, driver)

            # Worker table — HTML uses <th> headers: S.No, Job Card No, Worker Name(Gender), Attendance Date, Present/Absent
            workers = []
            w_rows = driver.find_elements(By.XPATH,
                "//table[.//th[contains(normalize-space(),'Job Card')]]//tr[td]")
            if not w_rows:
                # Fallback: any table row with 5+ tds and first cell is a number
                w_rows = driver.find_elements(By.XPATH, "//table//tr[count(td)>=5]")

            for wr in w_rows:
                wc = wr.find_elements(By.TAG_NAME, "td")
                if len(wc) < 5 or not wc[0].text.strip().isdigit():
                    continue
                try:
                    raw  = wc[2].text.strip()
                    gm   = re.search(r"\(([MFmf])\)", raw)
                    workers.append({
                        "jobcard": wc[1].text.strip(),
                        "name":    re.sub(r"\s*\([MFmf]\)\s*", "", raw).strip(),
                        "gender":  gm.group(1).upper() if gm else "",
                        "date":    wc[3].text.strip(),
                        "status":  wc[4].text.strip(),
                    })
                except Exception:
                    continue

            detail["workers"]      = workers
            detail["worker_count"] = str(len(workers))
            
            if workers:
                self.log_info(f"      Workers: {len(workers)}")
            else:
                self.log_warning("      ⚠ No workers found!")
            # Go back to MR list page via browser back button
            driver.back()
            time.sleep(1.5)

        except Exception as e:
            self.log_error(f"    Detail error: {e}")
            try:
                driver.back()
                time.sleep(1.5)
            except Exception:
                pass
        return detail

    def _extract_photo_info(self, driver, page_src: str, photo_no: int, detail: dict):
        """
        Extract timestamp / geo / taken-by for a photo block.

        Priority order:
          1. Read span elements by their known ContentPlaceHolder IDs directly.
          2. Find the td that contains "Timestamp for Photo-N" and parse its text.
          3. Sibling <tr> approach.
          4. Regex carve-out from raw HTML source.
        """
        pkey = f"photo{photo_no}_"

        # ── Strategy 0: read known span IDs directly (most reliable) ─────────
        # The page has spans like:
        #   ContentPlaceHolder1_lbl_Taken_by / lbl_SecondTaken_by (not present; same span for both)
        #   ContentPlaceHolder1_lbl_PhotoUploadTime  (photo 1 upload timestamp)
        #   ContentPlaceHolder1_lbl_SecondPhotoUploadTime (photo 2)
        #   ContentPlaceHolder1_lbl_cordinates       (photo 1 geo)
        #   ContentPlaceHolder1_lbl_SecondCordinates (photo 2 geo)
        #   ContentPlaceHolder1_lbl_Designation
        # NOTE: "Taken" timestamp (when photo was captured) may only appear as upload time;
        #       treat PhotoUploadTime as "Uploaded" and look for a separate taken span if present.
        def _span(span_id: str) -> str:
            """Return innerText of a span by its ID, empty string if not found."""
            try:
                el = driver.find_element(By.ID, span_id)
                return (el.get_attribute("innerText") or el.text or "").strip()
            except NoSuchElementException:
                return ""

        if photo_no == 1:
            # Photo-1 spans
            taken_val    = _span("ContentPlaceHolder1_lbl_PhotoTakenTime")   # may not exist on all portals
            uploaded_val = _span("ContentPlaceHolder1_lbl_PhotoUploadTime")
            geo_val      = _span("ContentPlaceHolder1_lbl_cordinates")
            taken_by_val = _span("ContentPlaceHolder1_lbl_Taken_by")
            desig_val    = _span("ContentPlaceHolder1_lbl_Designation")

            # If no separate "taken" span, fall back to upload time for "Taken" column too
            if not taken_val:
                taken_val = uploaded_val

            if uploaded_val:
                detail[f"{pkey}taken"]    = taken_val
                detail[f"{pkey}uploaded"] = uploaded_val
                detail[f"{pkey}geo"]      = geo_val
            if taken_by_val:
                detail["taken_by"]    = taken_by_val
            if desig_val:
                detail["designation"] = desig_val

        else:  # photo_no == 2
            taken_val    = _span("ContentPlaceHolder1_lbl_SecondPhotoTakenTime")
            uploaded_val = _span("ContentPlaceHolder1_lbl_SecondPhotoUploadTime")
            geo_val      = _span("ContentPlaceHolder1_lbl_SecondCordinates")

            if not taken_val:
                taken_val = uploaded_val

            if uploaded_val:
                detail[f"{pkey}taken"]    = taken_val
                detail[f"{pkey}uploaded"] = uploaded_val
                detail[f"{pkey}geo"]      = geo_val

        # If span-based extraction succeeded, return early
        if detail.get(f"{pkey}uploaded"):
            return

        # ── Strategy 1: find the timestamp block container ──────────────────
        block_text = ""
        try:
            ts_td = driver.find_element(
                By.XPATH,
                f"//td[.//text()[contains(normalize-space(.), 'Timestamp for Photo-{photo_no}')]]"
            )
            block_text = ts_td.get_attribute("innerText") or ts_td.text
        except NoSuchElementException:
            pass

        # ── Strategy 2: try individual label cells (when each row is a <tr>) ─
        if not block_text:
            try:
                rows = driver.find_elements(
                    By.XPATH,
                    f"//tr[.//td[contains(normalize-space(.), 'Timestamp for Photo-{photo_no}')]]"
                    f"/following-sibling::tr[position()<=6]"
                )
                parts = []
                for r in rows:
                    parts.append(r.text)
                if parts:
                    block_text = "\n".join(parts)
            except Exception:
                pass

        # ── Strategy 3: regex carve-out from raw HTML ───────────────────────
        if not block_text:
            m = re.search(
                rf"Timestamp for Photo-{photo_no}(.{{0,1500}}?)"
                rf"(?:Timestamp for Photo-\d|S\.No|Job Card|Last Updated|$)",
                page_src, re.IGNORECASE | re.DOTALL
            )
            if m:
                block_text = re.sub(r'<[^>]+>', ' ', m.group(0))
                block_text = re.sub(r'&nbsp;', ' ', block_text)
                block_text = re.sub(r'\s{2,}', ' ', block_text)

        if not block_text:
            if photo_no == 2:
                detail["photo2_taken"]    = "Not Uploaded"
                detail["photo2_uploaded"] = "Not Uploaded"
                detail["photo2_geo"]      = ""
            return

        # ── Parse collected text block ───────────────────────────────────────
        fields = self._parse_label_value_block(block_text)

        detail[f"{pkey}taken"]    = fields.get("taken", "")
        detail[f"{pkey}uploaded"] = fields.get("uploaded", "")
        detail[f"{pkey}geo"]      = (fields.get("geo co-ordinates")
                                     or fields.get("geo coordinates")
                                     or fields.get("geo", ""))
        if photo_no == 1:
            detail["taken_by"]    = fields.get("taken by", "")
            detail["designation"] = fields.get("designation", "")

        # If still nothing, do a direct line scan
        if not any([detail[f"{pkey}taken"], detail[f"{pkey}uploaded"], detail[f"{pkey}geo"]]):
            self._extract_photo_info_direct(block_text, photo_no, detail)

    def _extract_photo_info_direct(self, block_text: str, photo_no: int, detail: dict):
        """
        Fallback direct-scan parser: searches each known pattern directly with regex.
        Used when _parse_label_value_block returns nothing useful.
        """
        pkey = f"photo{photo_no}_"
        text = block_text

        # Taken timestamp: "Taken : 07 Jul 2026 05:32:34:000"
        m = re.search(r'Taken\s*:\s*([^\n\r]+)', text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Avoid matching "Taken by"
            if not re.match(r'by', val, re.IGNORECASE):
                detail[f"{pkey}taken"] = val

        # Uploaded timestamp
        m = re.search(r'Uploaded\s*:\s*([^\n\r]+)', text, re.IGNORECASE)
        if m:
            detail[f"{pkey}uploaded"] = m.group(1).strip()

        # Geo Coordinates
        m = re.search(r'Geo[\s\w-]*:\s*([-\d.,\s]+)', text, re.IGNORECASE)
        if m:
            detail[f"{pkey}geo"] = m.group(1).strip().rstrip(",")

        if photo_no == 1:
            # Taken by
            m = re.search(r'Taken\s+[Bb]y\s*:\s*([^\n\r]+)', text, re.IGNORECASE)
            if m:
                detail["taken_by"] = m.group(1).strip()
            # Designation
            m = re.search(r'Designation\s*:\s*([^\n\r]+)', text, re.IGNORECASE)
            if m:
                detail["designation"] = m.group(1).strip()

    def _parse_label_value_block(self, text: str) -> dict:
        """
        Parse a block of text with 'Label : value' or 'Label :\nvalue' patterns.
        Returns a dict of {lowercased_label: value}.

        Uses a whitelist of known labels to avoid misinterpreting timestamp colons
        (e.g., '09:00:47:000') as label-value separators.

        IMPORTANT: More-specific labels (e.g. 'taken by') must come before
        less-specific ones ('taken') so the longer match wins.
        """
        KNOWN_LABELS = [
            'timestamp for photo-1', 'timestamp for photo-2',
            'taken by',      # ← must come BEFORE 'taken'
            'taken',
            'uploaded',
            'geo co-ordinates', 'geo coordinates', 'geo',
            'designation', 'work name', 'work code', 'msr no',
        ]

        def is_label_line(line):
            """Return the matched label or None."""
            line_lower = line.lower().strip()
            for lbl in KNOWN_LABELS:
                if re.match(rf'^{re.escape(lbl)}\s*:?\s*', line_lower):
                    return lbl
            return None

        result = {}
        lines = [ln.strip() for ln in text.replace('\t', ' ').splitlines()]
        lines = [ln for ln in lines if ln]  # remove empty

        i = 0
        while i < len(lines):
            line = lines[i]
            lbl = is_label_line(line)
            if lbl is not None:
                # Extract value from same line after colon
                m = re.match(rf'^{re.escape(lbl)}\s*:+\s*(.*)', line, re.IGNORECASE)
                value = m.group(1).strip() if m else ''

                # If value empty, check next line
                if not value and i + 1 < len(lines):
                    next_lbl = is_label_line(lines[i + 1])
                    if next_lbl is None:  # next line is value, not label
                        value = lines[i + 1].strip()
                        i += 1  # consume the value line

                if value:
                    result[lbl] = value
            i += 1

        return result

    def _extract_field(self, text: str, labels: list) -> str:
        """Simple regex field extractor — used for Work Name and other single fields."""
        for label in labels:
            escaped = re.escape(label.rstrip(": "))
            # Same line: "Label : value" or "Label: value"
            m = re.search(rf"{escaped}\s*:+\s*(.+)", text, re.IGNORECASE)
            if m:
                val = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                val = re.sub(r'\s+', ' ', val)
                if val:
                    return val
            # Next line: "Label :\nvalue"
            m = re.search(rf"{escaped}\s*:+\s*[\r\n]+\s*(.+)", text, re.IGNORECASE)
            if m:
                val = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                val = re.sub(r'\s+', ' ', val)
                if val:
                    return val
        return ""

    def _re(self, html: str, pattern: str) -> str:
        m = re.search(pattern, html, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _download_photo(self, photo_no: int, pan_name: str,
                        mr_info: dict, photos_dir: str, driver) -> tuple:
        """
        Download a group photo via the 'Click here for large image' link.
        HTML structure: <a href="ShowImage.aspx?...">Click here for large image</a>
        This link is inside "Uploaded Group Photo-{N}" section.
        
        Returns: (status_str, file_path) where status is "Yes"/"No"/"Not Uploaded"/"Error"
        """
        try:
            photo_src = ""

            # Find all "Click here for large image" anchors on the page
            anchors = driver.find_elements(
                By.XPATH,
                "//a[contains(normalize-space(.),'large image') or contains(normalize-space(.),'Large Image') or contains(normalize-space(.),'large Image')]"
            )
            if len(anchors) >= photo_no:
                href = anchors[photo_no - 1].get_attribute("href") or ""
                if href and not href.startswith("javascript"):
                    photo_src = href

            # Fallback: any anchor whose href contains ShowImage or photo keyword
            if not photo_src:
                all_anchors = driver.find_elements(By.TAG_NAME, "a")
                photo_anchors = [
                    a for a in all_anchors
                    if any(k in (a.get_attribute("href") or "").lower()
                           for k in ("showimage", "photo", "grpphoto", "nmmsphoto"))
                ]
                if len(photo_anchors) >= photo_no:
                    photo_src = photo_anchors[photo_no - 1].get_attribute("href") or ""

            if not photo_src:
                return ("Not Uploaded", "")

            # Resolve relative URLs
            if photo_src.startswith("//"):
                photo_src = "https:" + photo_src
            elif not photo_src.startswith("http"):
                base = NMMS_BASE_URL.rsplit("/", 1)[0]
                photo_src = base + "/" + photo_src.lstrip("/")

            # Build filename and download
            safe_pan = re.sub(r'[\\/*?:"<>|]', "_", pan_name)
            safe_wc  = re.sub(r'[\\/*?:"<>|/]', "_", mr_info.get("work_code", "WC"))
            ext      = os.path.splitext(photo_src.split("?")[0])[-1]
            if not ext or len(ext) > 5:
                ext = ".jpg"
            fname = f"{safe_pan}_MR{mr_info.get('msr_no','0')}_{safe_wc}_Photo{photo_no}{ext}"
            path  = os.path.join(photos_dir, fname)

            cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
            resp    = self.app.http_session.get(
                photo_src,
                headers={"User-Agent": "Mozilla/5.0",
                         "Referer": driver.current_url},
                cookies=cookies, timeout=30)

            if resp.status_code == 200 and len(resp.content) > 500:
                with open(path, "wb") as f:
                    f.write(resp.content)
                self.log_info(f"    📷 Photo {photo_no}: {fname}")
                return ("Yes", path)

            self.app.log_message(self.log_display,
                f"    Photo {photo_no}: HTTP {resp.status_code} ({len(resp.content)} bytes)", "warning")
            return ("No", "")

        except Exception as e:
            self.log_warning(f"    Photo {photo_no} failed: {e}")
            return ("Error", "")

    # EXCEL EXPORT
    def _export_excel(self):
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "No results to export. Run the scrape first.")
            return

        date_safe = datetime.now().strftime("%d-%m-%Y")
        target_dir = os.path.join(self.app.get_user_downloads_path(), "NregaBot", "NMMS_Attendance", date_safe)
        os.makedirs(target_dir, exist_ok=True)

        file_path = filedialog.asksaveasfilename(
            initialdir=target_dir,
            initialfile=f"NMMS_Attendance_Report_{date_safe}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")],
            title="Save NMMS Attendance Report")
        if not file_path:
            return

        try:
            self._write_excel(file_path, date_safe)
            messagebox.showinfo("Exported", f"Report saved!\n\n{file_path}")
            if os.name == "nt":
                try: os.startfile(file_path)
                except Exception as e_open:
                    logger.debug("NMMS: Could not open file: %s", e_open)
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save report:\n{e}")

    def _write_excel(self, path: str, date_str: str):
        summary_data = [self.results_tree.item(i, "values") for i in self.results_tree.get_children()]
        worker_data  = [self.workers_tree.item(i, "values")  for i in self.workers_tree.get_children()]

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            # Sheet 1 — MR Summary
            pd.DataFrame(summary_data, columns=self.SUMMARY_HEADERS).to_excel(
                writer, sheet_name="MR Summary", index=False, startrow=4)
            ws_summary = writer.sheets["MR Summary"]
            self._style_sheet(ws_summary,
                len(summary_data), self.SUMMARY_HEADERS,
                f"NMMS Daily Attendance — MR Summary",
                f"Date: {date_str}  |  Generated by NregaBot", "1565C0")

            # Embed photos into Photo-1 Saved / Photo-2 Saved columns
            self._embed_photos_in_sheet(ws_summary, summary_data)

            # Sheet 2 — Workers Detail
            pd.DataFrame(worker_data, columns=self.WORKER_HEADERS).to_excel(
                writer, sheet_name="Workers Detail", index=False, startrow=4)
            self._style_sheet(writer.sheets["Workers Detail"],
                len(worker_data), self.WORKER_HEADERS,
                "NMMS Daily Attendance — Workers Detail",
                f"Date: {date_str}  |  Generated by NregaBot", "2E7D32")

            # Sheet 3 — Block Overview
            if self._panchayat_data:
                pan_rows = [[d["sno"], d["name"], d["no_works"], d["no_mr"], d["persondays"]]
                            for d in self._panchayat_data]
                pd.DataFrame(pan_rows, columns=self.PAN_OVERVIEW_HEADERS).to_excel(
                    writer, sheet_name="Block Overview", index=False, startrow=4)
                self._style_sheet(writer.sheets["Block Overview"],
                    len(pan_rows), self.PAN_OVERVIEW_HEADERS,
                    "NMMS Block Overview — Panchayat Summary",
                    f"Date: {date_str}  |  Generated by NregaBot", "6A1B9A")

    def _embed_photos_in_sheet(self, ws, summary_data: list):
        """
        For each data row that has a saved photo, embed the image in the
        'Photo-1 Saved' and/or 'Photo-2 Saved' cell and clear the text label.

        Photo paths are stored in self._photo_paths_map keyed by 1-based row index
        (matching summary_sno order used during scraping).
        """
        # Column indices (1-based) for the saved-photo columns
        try:
            p1_col = self.SUMMARY_HEADERS.index("Photo-1 Saved") + 1
            p2_col = self.SUMMARY_HEADERS.index("Photo-2 Saved") + 1
        except ValueError:
            return  # headers changed — skip silently

        # Photo display size in the cell (pixels at 96 dpi)
        IMG_W, IMG_H = 120, 90

        # Data starts at Excel row 6 (rows 1-3 header/subtitle/generated-by, row 4 blank, row 5 col headers)
        DATA_START_ROW = 6

        # Build a sorted list of (row_key, paths) so we can walk in order
        # row_key is summary_sno which starts at whatever was in the treeview before this run.
        # The simplest mapping: use the order of self._photo_paths_map entries.
        # But we stored them by summary_sno (1-based cumulative).
        # Map them to the order of summary_data rows by matching S No. in column 0.
        sno_to_paths: dict = {}
        for k, v in self._photo_paths_map.items():
            sno_to_paths[k] = v  # k is summary_sno int

        for row_idx, row_vals in enumerate(summary_data):
            excel_row = DATA_START_ROW + row_idx
            try:
                sno_val = int(row_vals[0])
            except (ValueError, IndexError):
                continue

            paths = sno_to_paths.get(sno_val)
            if not paths:
                continue

            p1_path, p2_path = paths

            for col_idx, img_path in [(p1_col, p1_path), (p2_col, p2_path)]:
                if not img_path or not os.path.isfile(img_path):
                    continue
                try:
                    img = XLImage(img_path)
                    img.width  = IMG_W
                    img.height = IMG_H

                    # Anchor the image to the target cell
                    cell_addr = f"{get_column_letter(col_idx)}{excel_row}"
                    img.anchor = cell_addr

                    # Clear text in that cell and size the row/col to fit the image
                    ws[cell_addr].value = ""
                    ws.row_dimensions[excel_row].height = IMG_H * 0.75  # pt ≈ px * 0.75
                    ws.column_dimensions[get_column_letter(col_idx)].width = IMG_W / 7  # approx chars

                    ws.add_image(img)
                except Exception:
                    pass  # leave text value as-is if image fails

    def _style_sheet(self, ws, n_data_rows: int, headers: list,
                     title: str, subtitle: str, hdr_color: str):
        """Apply title, subtitle, generated-by, header styling, and zebra striping."""
        n = len(headers)
        WHITE = "FFFFFF"
        thin  = Side(style="thin", color="BDBDBD")
        bdr   = Border(left=thin, right=thin, top=thin, bottom=thin)
        ctr   = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Row 1 — Title
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
        c1 = ws.cell(row=1, column=1, value=title)
        c1.font      = Font(size=14, bold=True, color=WHITE)
        c1.fill      = PatternFill(start_color=hdr_color, end_color=hdr_color, fill_type="solid")
        c1.alignment = ctr
        ws.row_dimensions[1].height = 26

        # Row 2 — Subtitle
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
        c2 = ws.cell(row=2, column=1, value=subtitle)
        c2.font = Font(italic=True, size=9); c2.alignment = ctr

        # Row 3 — Generated by
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=n)
        c3 = ws.cell(row=3, column=1,
                     value=f"Generated by NregaBot  |  {datetime.now().strftime('%d-%m-%Y %I:%M %p')}")
        c3.font = Font(italic=True, size=8, color="808080"); c3.alignment = ctr

        # Row 5 — Column headers (pandas wrote them at row 5 due to startrow=4)
        hdr_fill = PatternFill(start_color="E8EAF6", end_color="E8EAF6", fill_type="solid")
        for cell in ws[5]:
            cell.font = Font(bold=True, size=10)
            cell.fill = hdr_fill
            cell.alignment = ctr
            cell.border = bdr

        # Rows 6+ — Data with zebra striping
        EVEN = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
        ODD  = PatternFill(start_color=WHITE, end_color=WHITE, fill_type="solid")
        for r_idx, row_cells in enumerate(
                ws.iter_rows(min_row=6, max_row=5 + n_data_rows, min_col=1, max_col=n)):
            fill = EVEN if r_idx % 2 == 0 else ODD
            for cell in row_cells:
                cell.fill   = fill
                cell.border = bdr
                cell.alignment = Alignment(vertical="center")

        # Auto-size columns
        for col_idx, col_name in enumerate(headers, start=1):
            letter = get_column_letter(col_idx)
            best = min(max(len(str(col_name)) + 3, 12), 55)
            ws.column_dimensions[letter].width = best
