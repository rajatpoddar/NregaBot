import threading
import time
from datetime import datetime
from tkinter import messagebox
import customtkinter as ctk
from src import config
from .base_tab import BaseAutomationTab

from src.utils import get_logger
from typing import Any, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, StaleElementReferenceException, TimeoutException  # noqa: F401


logger = get_logger()

class LoginAutomationTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, "login_automation")
        
        # --- Main Layout ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # ── Header card (pack-managed wrapper — this tab uses pack layout) ──
        header_wrap = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_wrap.pack(fill="x", padx=0, pady=(0, 12))
        self._create_header_card(header_wrap, "🔐", "Login & Navigation Automation",
                                 "Auto-select Financial Year, District & Block — you only enter User ID & Password.",
                                 icon_key="emoji_login_automation")
        
        # --- Financial Year (Auto-set, read-only display) ---
        self.current_financial_year = self._get_current_financial_year()
        
        # --- Auto-Detected Location Info Card ---
        self._auto_detect_location()

        # --- Info Section ---
        info_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray95", "gray25"), corner_radius=10,
                                  border_width=1, border_color=("gray85", "gray30"))
        info_frame.pack(fill='x', padx=10, pady=(0, 5))
        
        ctk.CTkLabel(info_frame,
            text="💡  Bot automatically detects your District & Block from saved settings.\n"
                 "Pehle Settings > Location Data > 'Scrape Now' se data sync karein.\n"
                 "Browser launch hone ke baad aapko User ID & Password manual enter karna hoga.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray80"),
            wraplength=650, justify="left",
        ).pack(padx=15, pady=10)

        # --- Launch Button ---
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(pady=20)

        self.login_btn = ctk.CTkButton(
            btn_frame, text="🚀 Launch & Navigate",
            command=self.run_login_thread,
            fg_color=config.COLORS["btn_start"],
            hover_color=config.COLORS["btn_start_hover"],
            font=ctk.CTkFont(weight="bold", size=14),
            height=40, width=200,
        )
        self.login_btn.pack()

        # Status
        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready to automate", text_color="gray", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=5)

    @staticmethod
    def _get_current_financial_year():
        """Returns current Indian financial year as 'YYYY-YYYY' (e.g. '2026-2027').
        Indian FY runs from April to March."""
        now = datetime.now()
        year = now.year
        if now.month < 4:
            return f"{year - 1}-{year}"
        else:
            return f"{year}-{year + 1}"

    def _auto_detect_location(self):
        """Auto-detect District and Block from history_manager (server-synced data)."""
        hm = self.app.history_manager

        # Get from history suggestions
        dist_suggestions = hm.get_suggestions("location_district")
        block_suggestions = hm.get_suggestions("location_block")

        # Also check license_info (server-synced) as fallback
        lic = self.app.license_info if hasattr(self.app, 'license_info') else {}
        server_dist = (lic.get('user_district') or '').strip().upper()
        server_block = (lic.get('user_block') or '').strip().upper()

        # Use first suggestion as default, fallback to server data
        self.district = dist_suggestions[0] if dist_suggestions else (server_dist or "")
        self.block = block_suggestions[0] if block_suggestions else (server_block or "")

        # Ensure they're saved in history as well (sync from server if needed)
        if server_dist and server_dist not in dist_suggestions:
            hm.save_entry("location_district", server_dist)
            if not self.district:
                self.district = server_dist
        if server_block and server_block not in block_suggestions:
            hm.save_entry("location_block", server_block)
            if not self.block:
                self.block = server_block

        # Build info card showing detected values
        loc_frame = ctk.CTkFrame(self.main_frame, fg_color=("#F0FDF4", "#0F2A1D"), corner_radius=10,
                                 border_width=1, border_color=("#BBF7D0", "#166534"))
        loc_frame.pack(fill='x', padx=10, pady=(0, 5))

        inner = ctk.CTkFrame(loc_frame, fg_color="transparent")
        inner.pack(padx=15, pady=10)

        ctk.CTkLabel(inner, text="✅  Auto-Detected Location",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=("#166534", "#4ADE80")).pack(anchor="w")

        # FY row
        fy_row = ctk.CTkFrame(inner, fg_color="transparent")
        fy_row.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(fy_row, text=f"🗓️  Financial Year:  ",
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray60")).pack(side="left")
        ctk.CTkLabel(fy_row, text=self.current_financial_year,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#166534", "#86EFAC")).pack(side="left")

        # District row
        dist_row = ctk.CTkFrame(inner, fg_color="transparent")
        dist_row.pack(fill="x", pady=2)
        ctk.CTkLabel(dist_row, text=f"📍  District:  ",
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray60")).pack(side="left")
        if self.district:
            ctk.CTkLabel(dist_row, text=self.district,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=("#166534", "#86EFAC")).pack(side="left")
        else:
            ctk.CTkLabel(dist_row, text="Not set — scrape data first",
                         font=ctk.CTkFont(size=12),
                         text_color=("#DC2626", "#F87171")).pack(side="left")

        # Block row
        block_row = ctk.CTkFrame(inner, fg_color="transparent")
        block_row.pack(fill="x", pady=2)
        ctk.CTkLabel(block_row, text=f"📦  Block:  ",
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray60")).pack(side="left")
        if self.block:
            ctk.CTkLabel(block_row, text=self.block,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=("#166534", "#86EFAC")).pack(side="left")
        else:
            ctk.CTkLabel(block_row, text="Not set — scrape data first",
                         font=ctk.CTkFont(size=12),
                         text_color=("#DC2626", "#F87171")).pack(side="left")

        # Note
        if not self.district or not self.block:
            ctk.CTkLabel(loc_frame,
                text="⚠️  Location data nahi mila. Pehle Settings > Location Data > 'Scrape from Website' se data sync karein.",
                font=ctk.CTkFont(size=11),
                text_color=("#DC2626", "#F87171"),
                wraplength=600, justify="left",
            ).pack(padx=15, pady=(0, 8), anchor="w")

    def run_login_thread(self):
        t = threading.Thread(target=self.run_login_automation)
        t.start()

    def run_login_automation(self):

        fin_year = self.current_financial_year

        # Re-read from history_manager on each run (in case user scraped data after opening this tab)
        hm = self.app.history_manager
        dist_suggestions = hm.get_suggestions("location_district")
        block_suggestions = hm.get_suggestions("location_block")
        lic = self.app.license_info if hasattr(self.app, 'license_info') else {}
        server_dist = (lic.get('user_district') or '').strip().upper()
        server_block = (lic.get('user_block') or '').strip().upper()

        district = dist_suggestions[0] if dist_suggestions else (server_dist or "")
        block = block_suggestions[0] if block_suggestions else (server_block or "")

        if not (district and block):
            messagebox.showwarning("Missing Data",
                "District ya Block data nahi mila.\n\n"
                "Pehle Settings > Location Data > 'Scrape from Website' se data sync karein,\n"
                "ya Settings > Location Data mein manually add karein.")
            return

        try:
            self.update_status("Status: Launching Browser...")
            driver = self.app.get_driver()
            if not driver:
                self.update_status("Status: No Browser Found"); return

            url = "https://vbgramgde2.dord.gov.in/VBGRAMG/Login.aspx?&level=HomePO&state_code=34"
            driver.get(url)
            wait = WebDriverWait(driver, 25)

            # --- 1. Select Dropdowns ---
            self.update_status(f"Status: Selecting Financial Year ({fin_year})...")
            self._safe_select(wait, "//select[contains(@id, 'ddl_FinYr')]", fin_year)

            self.update_status(f"Status: Finding District '{district}'...")
            self._safe_select(wait, "//select[contains(@id, 'ddl_District')]", district, wait_for_options=True)

            self.update_status(f"Status: Finding Block '{block}'...")
            self._safe_select(wait, "//select[contains(@id, 'ddl_Block')]", block, wait_for_options=True)

            # --- Wait for Page Refresh ---
            self.update_status("Status: Waiting for page refresh...")
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                pass

            self.update_status("Status: Ready for Login — enter User ID & Password manually")

        except Exception as e:
            self.update_status("Status: Error occurred")
            messagebox.showerror("Automation Error", f"Error: {str(e)}")

    def _safe_select(self, wait, xpath, text, wait_for_options=False):
        for _ in range(3):
            try:
                elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                sel = Select(elem)
                if wait_for_options:
                    WebDriverWait(self.app.get_driver(), 5).until(lambda d: len(Select(d.find_element(By.XPATH, xpath)).options) > 1)
                    sel = Select(self.app.get_driver().find_element(By.XPATH, xpath))
                try: sel.select_by_visible_text(text)
                except:
                    found = False
                    for opt in sel.options:
                        if opt.text.strip().lower() == text.lower():
                            sel.select_by_visible_text(opt.text); found = True; break
                    if not found: raise Exception(f"Option '{text}' not found")
                return
            except StaleElementReferenceException:
                time.sleep(1)
        raise Exception(f"Failed to select '{text}' after retries")

    def update_status(self, text):
        """Update status label. Safe to call after tab destroyed."""
        if not self._is_alive():
            return
        try:
            self.status_label.configure(text=text)
        except Exception:
            pass
        try:
            clean_text = text.replace("Status: ", "")
            self.app.set_status(clean_text)
        except Exception as e: logger.debug("LoginAutomation: Could not update status: %s", e)
