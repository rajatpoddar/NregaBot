# tabs/ekyc_report_tab.py
import time
import threading
import json
import os
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

# Excel Imports
from src import config
from .base_tab import BaseAutomationTab
from src.utils import get_logger
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException  # noqa: F401


logger = get_logger()

# Dropdown labels used when the user wants to process ALL panchayats / ALL villages
ALL_PANCHAYATS_LABEL = "🌐 All Panchayats"
ALL_VILLAGES_LABEL = "🌐 All Villages"

class EKycReportTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, "ekyc_report")
        
        if self.automation_key not in self.app.stop_events:
            self.app.stop_events[self.automation_key] = threading.Event()
        
        self.all_scraped_data = []
        self.scraped_keys = set() # To track duplicates
        self._setup_ui()
        self.load_inputs()

    def _setup_ui(self):

        # ── Header card (pack-managed wrapper — tab uses pack layout) ──
        header_wrap = ctk.CTkFrame(self, fg_color="transparent")
        header_wrap.pack(fill="x", padx=0, pady=0)
        self._create_header_card(header_wrap, "📇", "eKYC Report",
                                 "Scan eKYC & ABPS status for jobcard holders — panchayat-wise summary.",
                                 icon_key="emoji_ekyc_report")

        # ── Main tab view at the top: Settings / Results / Logs & Status ──
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=(6, 5))

        settings_tab = self.tab_view.add("Settings")
        results_tab = self.tab_view.add("Results")
        self._create_log_and_status_area(self.tab_view)

        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(2, weight=1)
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        # --- Settings: Input Section ---
        input_frame = ctk.CTkFrame(settings_tab, corner_radius=12, border_width=1,
                                   border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        input_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        input_frame.grid_columnconfigure(1, weight=1)
        input_frame.grid_columnconfigure(3, weight=1)
        input_frame.grid_columnconfigure(5, weight=1)

        # Panchayat Input (Autocomplete Linked to Global History)
        ctk.CTkLabel(input_frame, text="Panchayat:").grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=ALL_PANCHAYATS_LABEL)
        self.panchayat_menu = ctk.CTkOptionMenu(input_frame, variable=self.panchayat_var,
                                                values=[ALL_PANCHAYATS_LABEL] + [v for v in p_vals if v], width=140)
        self.panchayat_menu.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        # Village Input (Autocomplete Linked to Global History)
        ctk.CTkLabel(input_frame, text="Village:").grid(row=0, column=2, padx=(10, 5), pady=10, sticky="w")
        v_vals = self.app.history_manager.get_suggestions("location_village") or [""]
        self.village_var = ctk.StringVar(value=ALL_VILLAGES_LABEL)
        self.village_menu = ctk.CTkOptionMenu(input_frame, variable=self.village_var,
                                              values=[ALL_VILLAGES_LABEL] + [v for v in v_vals if v], width=140)
        self.village_menu.grid(row=0, column=3, padx=5, pady=10, sticky="ew")

        # Filter villages when panchayat changes
        def _on_panchayat_change(*_):
            pan = self.panchayat_var.get()
            if pan and pan != ALL_PANCHAYATS_LABEL:
                vals = self.app.history_manager.get_filtered_suggestions("location_village", "location_panchayat", pan) or []
            else:
                vals = self.app.history_manager.get_suggestions("location_village") or []
            self.village_var.set(ALL_VILLAGES_LABEL)
            self.village_menu.configure(values=[ALL_VILLAGES_LABEL] + [v for v in vals if v])
        self.panchayat_var.trace_add("write", _on_panchayat_change)

        # Filter Dropdown
        ctk.CTkLabel(input_frame, text="Filter:").grid(row=0, column=4, padx=(10, 5), pady=10, sticky="w")
        self.filter_var = ctk.StringVar(value="All")
        self.filter_var.trace_add("write", lambda *_: self.apply_filter_visuals())
        self.filter_menu = ctk.CTkOptionMenu(input_frame, variable=self.filter_var, values=["All", "Verified (Yes)", "Not Verified (No)"], width=130)
        self.filter_menu.grid(row=0, column=5, padx=5, pady=10, sticky="ew")

        note_label = ctk.CTkLabel(settings_tab, text="💡 Note: Select '🌐 All Panchayats' to scan all panchayats.",
                                  text_color=("gray40", "gray70"), font=("Arial", 11, "italic"))
        note_label.grid(row=1, column=0, sticky="w", padx=20, pady=(6, 4))

        # --- Settings: Stats Frame (per-panchayat summary) ---
        self.stats_frame = ctk.CTkFrame(settings_tab, corner_radius=12, border_width=1,
                                        border_color=("gray85", "gray30"), fg_color=("gray97", "gray18"))
        self.stats_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 5))
        self.stats_frame.grid_columnconfigure(0, weight=1)
        self.stats_label_header = ctk.CTkLabel(self.stats_frame, text="📊 Panchayat-wise Summary:", font=("Arial", 11, "bold"))
        self.stats_label_header.pack(anchor="w", padx=10, pady=(5, 2))
        self.stats_text = ctk.CTkLabel(self.stats_frame, text="(No data yet)", font=("Arial", 10), justify="left", wraplength=900)
        self.stats_text.pack(anchor="w", padx=15, pady=(0, 5))

        # --- Settings: Action Buttons (outside any card) ---
        self._create_action_buttons(parent_frame=settings_tab).grid(row=3, column=0, pady=(8, 4))

        # --- Results Tab: Export button on top (so it's right next to the
        #     data after the run finishes — no hunting in Settings) ---
        export_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))
        self.export_btn = ctk.CTkButton(export_frame, text="📥 Export to Excel", command=self.export_professional_report, 
                                        state="disabled", fg_color=config.COLORS["green_export"])
        self.export_btn.pack(side="left")

        # --- Results Table ---
        result_frame = results_tab
        columns = ("sno", "panchayat", "village", "jobcard", "name", "abps_status", "ekyc_status")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("sno", text="S.No")
        self.tree.heading("panchayat", text="Panchayat")
        self.tree.heading("village", text="Village")
        self.tree.heading("jobcard", text="Job Card No")
        self.tree.heading("name", text="Applicant Name")
        self.tree.heading("abps_status", text="ABPS Enabled?")
        self.tree.heading("ekyc_status", text="eKYC Done?")
        
        self.tree.column("sno", width=50, anchor="center")
        self.tree.column("panchayat", width=130)
        self.tree.column("village", width=120)
        self.tree.column("jobcard", width=180)
        self.tree.column("name", width=200)
        self.tree.column("abps_status", width=100, anchor="center")
        self.tree.column("ekyc_status", width=100, anchor="center")

        self.style_treeview(self.tree)

        sb = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        sb.grid(row=1, column=1, sticky="ns")

        # ── results_tree alias ──
        # Base class helpers (WhatsApp summary + Excel report, cloud sync)
        # `results_tree` attribute use karte hain — same table ko alias kar do
        # taaki eKYC report bhi WhatsApp par summary + sheet bhej sake.
        self.results_tree = self.tree

    def _safe_update_status(self, text, progress=None):
        """Safe version of update_status — only runs on main thread via after(0, ...)."""
        if not self._is_alive():
            return
        try:
            self.status_label.configure(text=f"Status: {text}")
        except Exception:
            pass
        if progress is not None:
            try:
                self.progress_bar.set(progress)
            except Exception:
                pass
            # Footer '%' display — app ko progress report karo
            try:
                if hasattr(self.app, 'report_automation_progress'):
                    self.app.report_automation_progress(self.automation_key, progress)
            except Exception:
                pass
        try:
            self.app.set_status(f"eKYC Bot: {text}")
        except Exception:
            pass

    def update_status(self, text, progress=None):
        """Update UI status. Always use from main thread via app.after(0, ...)."""
        self.app.after(0, self._safe_update_status, text, progress)
    def start_automation(self) -> None:
        self.save_inputs()
        self.set_common_ui_state(running=True)
        self.export_btn.configure(state="disabled")
        
        self.all_scraped_data = []
        self.scraped_keys = set()
        for item in self.tree.get_children(): self.tree.delete(item)
        self.stats_text.configure(text="(Processing...)")

        # Start automation thread — uses app.start_automation_thread so
        # wrapper() handles driver cleanup and safe UI dispatch
        self.app.start_automation_thread(
            self.automation_key,
            self._run_process_safe,
            args=()
        )

    def _run_process_safe(self):
        """Wrapper that maintains backward compatibility.
        
        Called via start_automation_thread so driver cleanup and
        on_automation_finished are handled automatically.
        run_process references self.driver (which may be None for this tab
        since it uses app.browser_manager.get_driver() instead).
        """
        self.run_process()

    def _update_stats_display(self):
        """Scraped data se panchayat-wise stats calculate karke display karo"""
        if not self.all_scraped_data:
            self.stats_text.configure(text="(No data yet)")
            return
        
        from collections import defaultdict
        panchayat_stats = defaultdict(lambda: {"total": 0, "done": 0, "abps_pending": 0})
        
        for r in self.all_scraped_data:
            p = r.get("panchayat", "Unknown")
            panchayat_stats[p]["total"] += 1
            if "yes" in r["ekyc"].lower():
                panchayat_stats[p]["done"] += 1
            if "no" in r["abps"].lower():
                panchayat_stats[p]["abps_pending"] += 1
        
        grand_total = len(self.all_scraped_data)
        grand_done = sum(1 for r in self.all_scraped_data if "yes" in r["ekyc"].lower())
        grand_abps = sum(1 for r in self.all_scraped_data if "no" in r["abps"].lower())
        
        lines = []
        for p_name, s in sorted(panchayat_stats.items()):
            pending = s["total"] - s["done"]
            lines.append(
                f"📌 {p_name}:  Total={s['total']}  |  eKYC Done={s['done']}  |  Pending={pending}  |  ABPS Pending={s['abps_pending']}"
            )
        
        if len(panchayat_stats) > 1:
            lines.append(
                f"\n🔢 GRAND TOTAL:  Total={grand_total}  |  eKYC Done={grand_done}  |  Pending={grand_total - grand_done}  |  ABPS Pending={grand_abps}"
            )
        
        self.stats_text.configure(text="\n".join(lines))

    def _extract_activity_details(self) -> str:
        """eKYC-specific result summary: eKYC Done / Pending / ABPS Pending.

        Base heuristic Status column dhunde hai, par eKYC table me Yes/No
        columns hain — isliye accurate counts yahan se aate hain.
        """
        try:
            items = self.tree.get_children() if getattr(self, 'tree', None) is not None else []
            if not items:
                # Khali tree → purani run ke counts leak na karein ("success + no data → skip" bhi sahi ho)
                return ""
            total = len(items)
            done = 0
            abps_pending = 0
            for iid in items:
                vals = self.tree.item(iid, 'values') or []
                if len(vals) > 6 and 'yes' in str(vals[6]).lower():
                    done += 1
                if len(vals) > 5 and 'no' in str(vals[5]).lower():
                    abps_pending += 1
            pending = total - done
            parts = [f"📊 Total: {total}", f"✅ eKYC Done: {done}"]
            if pending > 0:
                parts.append(f"⏳ Pending: {pending}")
            if abps_pending > 0:
                parts.append(f"ABPS Pending: {abps_pending}")
            return " | ".join(parts)
        except Exception:
            return self.activity_details

    def run_process(self):
        try:
            panchayat_target = self.panchayat_var.get().strip()
            village_target = self.village_var.get().strip()
            # Map the "All" dropdown labels back to empty (process everything)
            if panchayat_target == ALL_PANCHAYATS_LABEL:
                panchayat_target = ""
            if village_target == ALL_VILLAGES_LABEL:
                village_target = ""

            # (Logs tab is auto-shown via set_common_ui_state(True) hook.)
            driver = self.app.browser_manager.get_driver()
            wait = WebDriverWait(driver, 20)
            
            self.update_status("Opening Website...")
            driver.get(config.EKYC_REPORT_CONFIG["url"])

            # 1. Uncheck Pending — simple checkbox toggle, no postback on this page
            try:
                chk_locator = (By.ID, "ctl00_ContentPlaceHolder1_chbx_freshCase")
                chk = wait.until(EC.presence_of_element_located(chk_locator))
                is_checked = driver.execute_script("return arguments[0].checked;", chk)
                
                if is_checked:
                    self.log_info("Unchecking 'Pending case' checkbox...")
                    driver.execute_script("arguments[0].click();", chk)
                    # No postback on checkbox toggle — just proceed
            except Exception as e:
                self.log_warning(f"Warning in Uncheck Pending: {e}")
            # 2. Determine Panchayats to Process
            panchayats_to_process = []
            
            if panchayat_target:
                panchayats_to_process.append(panchayat_target)
                self.app.update_history("location_panchayat", panchayat_target)
            else:
                self.update_status("Fetching panchayat list...")
                try:
                    panchayat_dd_elem = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDL_panchayat")))
                    options = Select(panchayat_dd_elem).options
                    
                    for opt in options:
                        val = opt.get_attribute("value")
                        txt = opt.text.strip()
                        if val not in ["00", "99"] and txt != "---Select---" and "All" not in txt:
                            panchayats_to_process.append(txt)
                    
                    self.log_info(f"Found {len(panchayats_to_process)} panchayats to scan.")
                except Exception as e:
                    raise Exception(f"Could not fetch panchayat list: {e}")

            # 3. Iterate over Panchayats
            total_panchayats = len(panchayats_to_process)
            
            for p_idx, p_name in enumerate(panchayats_to_process, 1):
                if self.is_stopped(): break
                
                self.update_status(f"Processing Panchayat {p_idx}/{total_panchayats}: {p_name}")
                self.log_info(f"{'='*50}\nSelecting Panchayat: {p_name}\n{'='*50}")
                # Select Panchayat (case-insensitive)
                try:
                    panchayat_elem = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_DDL_panchayat")))
                    panchayat_dd = Select(panchayat_elem)
                    
                    if not self._select_by_text_case_insensitive(panchayat_dd, p_name):
                        # Log available options for debugging
                        options_text = [opt.text.strip() for opt in panchayat_dd.options if opt.text.strip() not in ("---Select---", "")]
                        self.log_error(f"Failed to select panchayat '{p_name}'. Available: {options_text}")
                        continue
                    
                    # Wait for village dropdown to populate after panchayat postback
                    try:
                        wait.until(lambda d: len(Select(d.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")).options) > 1)
                        self.log_success(f"Selected panchayat: '{p_name}' (village list loaded)")
                    except:
                        time.sleep(1.5)  # fallback wait
                    
                except Exception as e:
                    self.log_error(f"Failed to select {p_name}: {e}")
                    continue

                # 4. Determine Villages to Process for this Panchayat
                villages_to_process = []
                
                if village_target and ("All Village" in village_target or village_target == "99"):
                    village_target = ""

                if village_target:
                    villages_to_process.append(village_target)
                    self.app.update_history("location_village", village_target)
                else:
                    self.update_status(f"Fetching village list for {p_name}...")
                    try:
                        village_dd_elem = None
                        for _ in range(3):
                            try:
                                village_dd_elem = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")
                                break
                            except: time.sleep(1)
                        
                        if not village_dd_elem: raise Exception("Village Dropdown not found")

                        options = Select(village_dd_elem).options
                        for opt in options:
                            val = opt.get_attribute("value")
                            txt = opt.text.strip()
                            if val not in ["00", "99"] and txt != "---Select---" and txt != "--All Villages--":
                                villages_to_process.append(txt)
                        
                        self.log_info(f"Found {len(villages_to_process)} villages in {p_name}.")
                    except Exception as e:
                        self.log_error(f"Could not fetch village list for {p_name}: {e}")
                        continue

                # 5. Process Villages in this Panchayat
                total_villages = len(villages_to_process)
                
                for v_idx, v_name in enumerate(villages_to_process, 1):
                    if self.is_stopped(): break
                    
                    self.update_status(f"[{p_name}] Village {v_idx}/{total_villages}: {v_name}")
                    self.log_info(f"  Selecting Village: {v_name}")                    
                    # Select Village (case-insensitive, with retry)
                    selection_success = False
                    for attempt in range(1, 4):
                        try:
                            v_dd_elem = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_DDL_Village")))
                            v_dd = Select(v_dd_elem)
                            
                            if self._select_by_text_case_insensitive(v_dd, v_name):
                                # Wait for postback after village selection
                                time.sleep(0.5)
                                selection_success = True
                                break
                            else:
                                # Log available options on first attempt only
                                if attempt == 1:
                                    v_options = [opt.text.strip() for opt in v_dd.options if opt.text.strip() not in ("---Select---", "")]
                                    self.log_warning(f"    Village '{v_name}' not found. Available: {v_options}")
                        except Exception as e:
                            pass
                        self.log_warning(f"    Retry {attempt} for {v_name}...")
                        time.sleep(1.5)
                    
                    if not selection_success:
                        self.log_error(f"    Skipping {v_name} (Selection Failed after 3 attempts)")
                        continue

                    self.scrape_current_table(driver, p_name, v_name)

            self.update_status("Completed")
            self.app.after(0, self._update_stats_display)
            self.app.after(0, lambda: self.export_btn.configure(state="normal"))
            self.app.after(0, messagebox.showinfo, "Success", f"Scan Complete.\nRecords Found: {len(self.all_scraped_data)}")

        except Exception as e:
            self.app.after(0, self.handle_error, e)
        finally:
            # Log completion summary
            total = len(self.all_scraped_data)
            done = sum(1 for r in self.all_scraped_data if 'yes' in r['ekyc'].lower()) if self.all_scraped_data else 0
            pending = total - done
            self.log_info(f"📊 eKYC Scan Complete: 📝 {total} records, ✅ {done} eKYC done, ❌ {pending} pending")
            self.app.after(0, self.set_common_ui_state, False)
            self.app.after(0, self._safe_update_status, "Ready")

    def scrape_current_table(self, driver, location_panchayat, location_village):
        current_page_num = 1
        
        # Reset to Page 1
        try:
            page_one_link = driver.find_elements(By.XPATH, "//a[text()='1']")
            if page_one_link:
                self.log_info(f"Resetting to Page 1 for {location_village}...")
                old_table = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_gvData")
                driver.execute_script("arguments[0].click();", page_one_link[0])
                try: WebDriverWait(driver, 10).until(EC.staleness_of(old_table))
                except Exception: time.sleep(2)
        except Exception as e:
            logger.debug("Failed to wait for table staleness: %s", e)

        while True:
            if self.is_stopped(): return

            if "No Record Found" in driver.page_source:
                self.log_warning(f"No records in {location_village}.")
                break

            try:
                table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_gvData")))
                rows = table.find_elements(By.TAG_NAME, "tr")
            except:
                self.log_error("Table not found.")
                break

            count_on_page = 0
            if len(rows) > 1:
                for row in rows[1:]:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 5: continue 

                    try:
                        jc = cols[1].text.strip()
                        if "Job Card" in jc: continue 
                        
                        # --- FIX: GARBAGE/PAGINATION ROW FILTER ---
                        # "1", "2" jaise page numbers ko filter karne ke liye length check
                        if len(jc) < 5: continue 

                        name = cols[3].text.strip()
                        abps = cols[-2].text.strip()
                        ekyc = cols[-1].text.strip()
                        
                        # --- STRICT DUPLICATE CHECK ---
                        # Spaces hata kar aur lowercase karke check karenge
                        clean_jc = "".join(jc.split()).lower()
                        clean_name = "".join(name.split()).lower()
                        
                        unique_key = f"{location_panchayat}|{location_village}|{clean_jc}|{clean_name}"
                        
                        if unique_key in self.scraped_keys: continue
                        self.scraped_keys.add(unique_key)

                        record = {
                            "panchayat": location_panchayat,
                            "village": location_village,
                            "jobcard": jc, "name": name, "abps": abps, "ekyc": ekyc
                        }
                        self.all_scraped_data.append(record)
                        self.check_and_insert_to_tree(record)
                        count_on_page += 1
                    except: continue

            self.log_info(f"  > Page {current_page_num}: {count_on_page} new records.")
            next_page_num = current_page_num + 1
            try:
                next_link = driver.find_element(By.XPATH, f"//a[contains(@href, 'Page${next_page_num}')]")
                self.update_status(f"Loading {location_village} - Page {next_page_num}...")
                old_table = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_gvData")
                
                driver.execute_script("arguments[0].click();", next_link)
                
                try: WebDriverWait(driver, 10).until(EC.staleness_of(old_table))
                except: time.sleep(3)
                current_page_num += 1
            except NoSuchElementException:
                break
            except Exception as e:
                self.log_warning(f"Pagination error: {e}")
                break

    def _should_show_record(self, record):
        """Filter logic based on eKYC status only"""
        filter_mode = self.filter_var.get()
        ekyc_yes = "yes" in record['ekyc'].lower()

        if filter_mode == "All": 
            return True
        elif filter_mode == "Verified (Yes)" and ekyc_yes: 
            return True
        elif filter_mode == "Not Verified (No)" and not ekyc_yes: 
            return True
        return False

    def check_and_insert_to_tree(self, record):
        if self._should_show_record(record):
            sno = len(self.tree.get_children()) + 1
            self.tree.insert("", "end", values=(sno, record['panchayat'], record['village'], record['jobcard'], record['name'], record['abps'], record['ekyc']))
            if sno % 10 == 0: self.tree.yview_moveto(1)

    def apply_filter_visuals(self):
        """Re-apply filter to tree based on current filter_var."""
        for item in self.tree.get_children(): self.tree.delete(item)
        for r in self.all_scraped_data: self.check_and_insert_to_tree(r)

    def export_professional_report(self):
        """Export using the base class professional Excel method."""
        if not self.tree.get_children():
            messagebox.showinfo("No Data", "No records to export. Run automation first.")
            return
        self.export_treeview_to_excel(
            tree=self.tree,
            default_filename="ekyc_report.xlsx",
            filter_mode="Export All",
            title_prefix="eKYC & ABPS Report"
        )

    def save_inputs(self):
        panchayat = self.panchayat_var.get().strip()
        village = self.village_var.get().strip()
        if panchayat == ALL_PANCHAYATS_LABEL:
            panchayat = ""  # Save as empty = all panchayats
        if village == ALL_VILLAGES_LABEL:
            village = ""  # Save as empty = all villages
        data = {
            "panchayat": panchayat,
            "village": village,
            "filter": self.filter_var.get(),
        }
        try:
            self.app.history_manager.save_tab_inputs_batch("ekyc_report", data)
        except Exception as e:
            logger.warning("Failed to save eKYC inputs: %s", e)

    def load_inputs(self):
        data = self.app.history_manager.get_tab_inputs("ekyc_report")
        if data:
            self.panchayat_var.set(data.get("panchayat") or ALL_PANCHAYATS_LABEL)
            self.village_var.set(data.get("village") or ALL_VILLAGES_LABEL)
            saved_filter = data.get("filter", "All")
            self.filter_var.set(saved_filter)