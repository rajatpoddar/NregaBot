# tabs/print_wagelist_tab.py
"""
Print Wagelist — View & Save Wagelist as PDF.

Extract wagelist numbers from any pasted text (like Workcode Extractor),
then visit each on the portal and save as PDF.

Flow:
  1. Paste any text containing wagelist numbers
  2. Click "Extract" → regex finds all digits+WL+digits patterns, deduplicates
  3. Click Start → for each wagelist:
     a. Navigate to view_wagelist.aspx?flag=UNSK
     b. Select Financial Year
     c. Search wagelist number
     d. Select from dropdown
     e. Save page as PDF
"""

import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import re
import time
import os
import base64
from datetime import datetime
from src import config
from src.i18n import tr
from .base_tab import BaseAutomationTab
from typing import Any
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException  # noqa: F401

from src.utils import get_logger

logger = get_logger()

# view_wagelist.aspx base URL (flag=UNSK for PO login)
VIEW_WAGELIST_URL = "https://vbgramgde2.dord.gov.in/vbgramg/view_wagelist.aspx?flag=UNSK"

# Regex: matches wagelist IDs like 3422003WL000023, 3422003WL031552
_WAGELIST_PATTERN = re.compile(r'\b\d+WL\d+\b', re.IGNORECASE)


class PrintWagelistTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="print_wagelist")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._extracted_wagelists: list = []
        self._create_widgets()

    def _create_widgets(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Main Notebook ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        settings_tab = notebook.add("Settings")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)

        # ================== SETTINGS TAB ==================
        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(2, weight=1)

        # --- Header Card ---
        self._create_header_card(
            settings_tab, "🖨️",
            "Print Wagelist",
            "Paste any text containing wagelist numbers → Extract → Save as PDF.",
            icon_key="emoji_send_wagelist"
        )

        # --- Top Controls: FY + Save PDF option ---
        controls_frame = ctk.CTkFrame(
            settings_tab, corner_radius=12, border_width=1,
            border_color=("gray85", "gray30")
        )
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        controls_frame.grid_columnconfigure(1, weight=1)

        # Financial Year
        ctk.CTkLabel(controls_frame, text="Financial Year:").grid(
            row=0, column=0, sticky="w", padx=15, pady=10
        )
        current_year = datetime.now().year
        year_options = [
            f"{y}-{y+1}" for y in range(current_year + 1, current_year - 10, -1)
        ]
        default_year = (
            f"{current_year}-{current_year+1}"
            if datetime.now().month >= 4
            else f"{current_year-1}-{current_year}"
        )
        self.fin_year_var = ctk.StringVar(value=default_year)
        self.fin_year_menu = ctk.CTkOptionMenu(
            controls_frame, variable=self.fin_year_var, values=year_options
        )
        self.fin_year_menu.grid(row=0, column=1, sticky="ew", padx=15, pady=10)

        # Save PDF checkbox
        self.save_pdf_var = ctk.StringVar(value="on")
        self.save_pdf_checkbox = ctk.CTkCheckBox(
            controls_frame, text="Save as PDF",
            variable=self.save_pdf_var, onvalue="on", offvalue="off"
        )
        self.save_pdf_checkbox.grid(row=0, column=2, padx=15, pady=10)

        # --- Extract Section (Workcode Extractor style) ---
        extract_frame = ctk.CTkFrame(
            settings_tab, corner_radius=12, border_width=1,
            border_color=("gray85", "gray30")
        )
        extract_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        extract_frame.grid_columnconfigure(0, weight=1)
        extract_frame.grid_columnconfigure(1, weight=1)
        extract_frame.grid_rowconfigure(3, weight=1)

        # Row 0: Label + Extract button + options
        top_row = ctk.CTkFrame(extract_frame, fg_color="transparent")
        top_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))
        top_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top_row, text="📋 Paste Text & Extract Wagelists:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(5, 10), pady=5, sticky="w")

        self.extract_btn = ctk.CTkButton(
            top_row, text="🔍 Extract Wagelists", width=160,
            command=self._extract_wagelists,
            fg_color=config.COLORS["btn_start"],
            hover_color=config.COLORS["btn_start_hover"]
        )
        self.extract_btn.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.remove_dups_var = ctk.StringVar(value="on")
        self.remove_dups_checkbox = ctk.CTkCheckBox(
            top_row, text="Remove duplicates",
            variable=self.remove_dups_var, onvalue="on", offvalue="off"
        )
        self.remove_dups_checkbox.grid(row=0, column=2, padx=10, pady=5)

        self.clear_btn = ctk.CTkButton(
            top_row, text="Clear", width=70,
            command=self._clear_extract, fg_color="transparent",
            border_width=2, text_color=("gray10", "#DCE4EE")
        )
        self.clear_btn.grid(row=0, column=3, padx=(5, 0), pady=5)

        # Row 1: Hint
        ctk.CTkLabel(
            extract_frame,
            text="Paste wagelist numbers, reports, messages — anything containing patterns like 3422003WL000023",
            text_color="gray60", font=ctk.CTkFont(size=11)
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(2, 5))

        # Row 2: Input / Output side by side
        # Left: Input textbox
        self.input_text = ctk.CTkTextbox(extract_frame, wrap=tkinter.WORD, font=("Consolas", 12))
        self.input_text.grid(row=2, column=0, sticky="nsew", padx=(10, 5), pady=(0, 5))

        # Right: Output textbox (extracted wagelists)
        output_frame = ctk.CTkFrame(extract_frame, fg_color="transparent")
        output_frame.grid(row=2, column=1, sticky="nsew", padx=(5, 10), pady=(0, 5))
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(1, weight=1)

        output_header = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_header.grid(row=0, column=0, sticky="ew")
        output_header.grid_columnconfigure(1, weight=1)

        self.output_label = ctk.CTkLabel(
            output_header, text="Extracted (0):",
            font=ctk.CTkFont(weight="bold")
        )
        self.output_label.grid(row=0, column=0, sticky="w")

        self.copy_btn = ctk.CTkButton(
            output_header, text="Copy", width=60,
            command=self._copy_results
        )
        self.copy_btn.grid(row=0, column=1, sticky="e", padx=(5, 0))

        self.output_text = ctk.CTkTextbox(
            output_frame, wrap=tkinter.NONE, state="disabled",
            font=("Consolas", 12)
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", pady=(3, 0))

        # Row 3: Output folder hint
        self.output_folder_label = ctk.CTkLabel(
            extract_frame, text="", text_color="gray50",
            font=ctk.CTkFont(size=11), wraplength=600, justify="left"
        )
        self.output_folder_label.grid(
            row=3, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8)
        )

        # Action Buttons (Start / Stop / Retry / Reset)
        action_frame = self._create_action_buttons(parent_frame=settings_tab)
        action_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        # ================== RESULTS TAB ==================
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10), padx=5)

        self.export_button = ctk.CTkButton(
            results_action_frame, text=tr("common.export_excel"),
            command=self._export_results
        )
        self.export_button.pack(side="left")

        cols = ("Wagelist No.", "Status", "Timestamp", "PDF Path")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show="headings")
        for col in cols:
            self.results_tree.heading(col, text=col)
        self.results_tree.column("Wagelist No.", width=180)
        self.results_tree.column("Status", width=100)
        self.results_tree.column("Timestamp", width=80, anchor="center")
        self.results_tree.column("PDF Path", width=300)
        self.results_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=5)
        self.style_treeview(self.results_tree)

    # ------------------------------------------------------------------
    # Extract Logic (like Workcode Extractor)
    # ------------------------------------------------------------------
    def _extract_wagelists(self):
        """Extract wagelist numbers from the input textbox using regex."""
        input_content = self.input_text.get("1.0", tkinter.END)
        if not input_content.strip():
            messagebox.showinfo("No Input", "Please paste some text containing wagelist numbers first.")
            return

        matches = _WAGELIST_PATTERN.findall(input_content)
        # Normalize to uppercase
        found = [m.upper() for m in matches]

        # Deduplicate while preserving order
        if self.remove_dups_var.get() == "on":
            seen = set()
            unique = []
            for w in found:
                if w not in seen:
                    seen.add(w)
                    unique.append(w)
            found = unique

        self._extracted_wagelists = found

        # Update output display
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tkinter.END)
        if found:
            self.output_text.insert("1.0", "\n".join(found))
        else:
            self.output_text.insert("1.0", "No wagelist numbers found (pattern: digits+WL+digits)")
        self.output_text.configure(state="disabled")

        self.output_label.configure(text=f"Extracted ({len(found)}):")

        if found:
            self.log_info(f"🔍 Extracted {len(found)} unique wagelist(s): {', '.join(found[:5])}" +
                         (f"... +{len(found)-5} more" if len(found) > 5 else ""))
        else:
            self.log_info("🔍 No wagelist numbers found in the input text.")

    def _copy_results(self):
        """Copy extracted wagelists to clipboard."""
        results = self.output_text.get("1.0", tkinter.END).strip()
        if results and "No wagelist" not in results:
            self.app.clipboard_clear()
            self.app.clipboard_append(results)
            self.copy_btn.configure(text="✓ Copied")
            self.app.after(2000, lambda: self.copy_btn.configure(text="Copy"))

    def _clear_extract(self):
        """Clear input, output, and extracted list."""
        self.input_text.delete("1.0", tkinter.END)
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tkinter.END)
        self.output_text.configure(state="disabled")
        self.output_label.configure(text="Extracted (0):")
        self._extracted_wagelists = []

    # ------------------------------------------------------------------
    # UI State
    # ------------------------------------------------------------------
    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.fin_year_menu.configure(state=state)
        self.save_pdf_checkbox.configure(state=state)
        self.extract_btn.configure(state=state)
        self.remove_dups_checkbox.configure(state=state)
        self.clear_btn.configure(state=state)
        self.input_text.configure(state=state)
        self.export_button.configure(state=state)

    def reset_ui(self) -> None:
        if messagebox.askokcancel(tr("dialogs.reset_form"), tr("confirm.are_you_sure")):
            self._clear_extract()
            self.save_pdf_var.set("on")
            self.output_folder_label.configure(text="")
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")

    def start_automation(self) -> None:
        wagelist_list = self._extracted_wagelists

        if not wagelist_list:
            # Try extracting first if input has text
            input_content = self.input_text.get("1.0", tkinter.END).strip()
            if input_content:
                self._extract_wagelists()
                wagelist_list = self._extracted_wagelists

            if not wagelist_list:
                messagebox.showwarning(
                    "No Wagelists",
                    "No wagelist numbers found.\n\n"
                    "Paste text containing wagelist numbers (e.g. 3422003WL000023)\n"
                    "and click 'Extract Wagelists' first."
                )
                return

        fin_year = self.fin_year_var.get()
        save_pdf = self.save_pdf_var.get() == "on"

        self.app.start_automation_thread(
            self.automation_key,
            self.run_automation_logic,
            args=(fin_year, wagelist_list, save_pdf)
        )

    def retry_logic_handler(self) -> None:
        if messagebox.askyesno("Retry", "Retry the last wagelist batch?"):
            self.start_automation()

    # ------------------------------------------------------------------
    # Automation Logic
    # ------------------------------------------------------------------
    def run_automation_logic(self, fin_year: str, wagelist_list: list, save_pdf: bool):
        self.app.after(0, self.set_ui_state, True)
        self.safe_tree_clear()
        self.app.clear_log(self.log_display)
        self.log_info("Starting Print Wagelist automation...")
        self.app.after(0, self.app.set_status, "Running Print Wagelist...")
        self.app.after(0, self.update_status, "Initializing...", 0.0)

        # Prepare output directory
        output_dir = None
        if save_pdf:
            try:
                output_dir = os.path.join(
                    self.app.get_nregabot_path("PDF_Output/Wagelist"),
                    "Print",
                    datetime.now().strftime("%Y-%m-%d")
                )
                os.makedirs(output_dir, exist_ok=True)
                self.log_info(f"PDFs will be saved to: {output_dir}")
                self.app.after(0, lambda: self.output_folder_label.configure(
                    text=f"📁 {output_dir}"
                ))
            except Exception:
                output_dir = None

        total = len(wagelist_list)
        success_count = 0
        fail_count = 0

        try:
            driver = self.app.get_driver()
            if not driver:
                return
            wait = WebDriverWait(driver, 30)

            for idx, wagelist_no in enumerate(wagelist_list, 1):
                if self.is_stopped():
                    self.log_warning("⏹️ Automation stopped by user.")
                    break

                pct = idx / total
                self.log_info(f"=== [{idx}/{total}] Processing: {wagelist_no} ===")
                self.app.after(0, self.update_status, f"{wagelist_no} ({idx}/{total})", pct)
                self.app.after(0, self.app.set_status, f"Print WL: {wagelist_no}")

                try:
                    result = self._process_single_wagelist(
                        driver, wait, wagelist_no, fin_year, save_pdf, output_dir
                    )
                    if result:
                        success_count += 1
                        pdf_info = f" ({result})" if result and result not in ("No PDF", "Viewed") else ""
                        self.log_success(f"✅ {wagelist_no} saved{pdf_info}")
                        self._log_result(wagelist_no, "Success", pdf_info)
                    else:
                        fail_count += 1
                        self.log_error(f"❌ {wagelist_no} failed")
                        self._log_result(wagelist_no, "Failed", "")
                except Exception as e:
                    fail_count += 1
                    self.log_error(f"❌ {wagelist_no} error: {e}")
                    self._log_result(wagelist_no, f"Error: {type(e).__name__}", "")

                time.sleep(1)

        except Exception as e:
            self.log_error(f"Critical error: {e}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Finished", 1.0)
            self.app.after(0, self.app.set_status, "Finished")
            self.log_info(f"{'='*50}")
            self.log_info(f"📊 Done: ✅ {success_count} success, ❌ {fail_count} failed (of {total})")
            self.log_info(f"{'='*50}")
            self.app.after(5000, lambda: self.app.set_status("Ready"))
            self.app.after(5000, lambda: self.update_status("Ready", 0.0))

    def _process_single_wagelist(
        self, driver, wait, wagelist_no: str, fin_year: str,
        save_pdf: bool, output_dir: str
    ) -> str:
        """
        Process a single wagelist:
        1. Navigate to view_wagelist.aspx?flag=UNSK
        2. Select FY (if not already)
        3. Search wagelist number
        4. Select from dropdown
        5. Save as PDF

        Returns: PDF file path if saved, empty string if failed.
        """
        for attempt in range(2):
            if self.is_stopped():
                return ""
            try:
                # A. Load page
                self.log_info(f"   Loading view_wagelist page...")
                loaded = False
                for _ in range(3):
                    try:
                        driver.get(self.resolve_portal_url(VIEW_WAGELIST_URL))
                        loaded = True
                        break
                    except Exception:
                        time.sleep(2)
                if not loaded:
                    self.log_error(f"   Failed to load page for {wagelist_no}")
                    return ""

                # Wait for page to be ready
                self._wait_for_ready(driver, 15)

                # B. Select Financial Year
                self.log_info(f"   Selecting FY: {fin_year}")
                fy_select = wait.until(
                    EC.presence_of_element_located((By.ID, "ddlFinYr"))
                )
                # Check if FY is already selected
                current_fy = Select(fy_select).first_selected_option.get_attribute("value")
                if current_fy != fin_year:
                    Select(fy_select).select_by_visible_text(fin_year)
                    # FY change triggers ASP.NET postback — wait for it
                    self.log_info(f"   FY postback in progress...")
                    self._wait_for_postback(driver, 15)
                else:
                    self.log_info(f"   FY already set to {fin_year}")

                # Check for error message after FY select
                if self._check_error_message(driver):
                    self.log_error(f"   Error after FY select — page may not be logged in")
                    return ""

                # C. Search for wagelist number
                self.log_info(f"   Searching: {wagelist_no}")
                search_box = wait.until(
                    EC.presence_of_element_located((By.ID, "txt_search"))
                )
                search_box.clear()
                time.sleep(0.3)
                search_box.send_keys(wagelist_no)
                time.sleep(0.5)

                # Click search button (input type=image — use JS click)
                search_btn = wait.until(
                    EC.element_to_be_clickable((By.ID, "ImgbtnSearch"))
                )
                driver.execute_script("arguments[0].click();", search_btn)
                self.log_info(f"   Search triggered, waiting for results...")

                # Wait for postback to complete
                self._wait_for_postback(driver, 15)

                # Check for error after search
                if self._check_error_message(driver):
                    self.log_error(f"   Search error for {wagelist_no}")
                    return ""

                # D. Select wagelist from dropdown
                self.log_info(f"   Checking dropdown...")
                wl_dropdown = wait.until(
                    EC.presence_of_element_located((By.ID, "ddl_sel"))
                )
                wl_select = Select(wl_dropdown)

                # Log available options for debugging
                available = [opt.get_attribute("value") for opt in wl_select.options]
                self.log_info(f"   Dropdown has {len(available)} option(s): {available[:5]}")

                # Try to find and select the wagelist
                found = False
                for opt in wl_select.options:
                    val = opt.get_attribute("value")
                    text = opt.text.strip()
                    if not val or val == "select":
                        continue
                    if val.lower() == wagelist_no.lower():
                        wl_select.select_by_value(val)
                        found = True
                        self.log_info(f"   Exact match selected: {val}")
                        break
                    elif wagelist_no.lower() in val.lower():
                        wl_select.select_by_value(val)
                        found = True
                        self.log_info(f"   Partial match selected: {val}")
                        break
                    elif wagelist_no.lower() in text.lower():
                        wl_select.select_by_visible_text(text)
                        found = True
                        self.log_info(f"   Text match selected: {text}")
                        break

                if not found:
                    # Try prefix match (e.g. 3422003WL matches 3422003WL000023)
                    for opt in wl_select.options:
                        val = opt.get_attribute("value")
                        if val and val != "select" and wagelist_no[:10] in val:
                            wl_select.select_by_value(val)
                            found = True
                            self.log_info(f"   Prefix match selected: {val}")
                            break

                if not found:
                    self.log_error(f"   Wagelist '{wagelist_no}' not found in dropdown. Available: {available}")
                    return ""

                # Wait for table to load after dropdown selection (postback)
                self.log_info(f"   Wagelist selected, waiting for table...")
                self._wait_for_postback(driver, 15)

                # Verify the wagelist table loaded
                table_loaded = False
                try:
                    driver.find_element(By.ID, "GridView1")
                    table_loaded = True
                except NoSuchElementException:
                    pass

                if not table_loaded:
                    # Check dvshow div for content
                    try:
                        dvshow = driver.find_element(By.ID, "dvshow")
                        if dvshow.text.strip() and len(dvshow.text.strip()) > 10:
                            table_loaded = True
                    except NoSuchElementException:
                        pass

                if not table_loaded:
                    self.log_error(f"   No wagelist data loaded for {wagelist_no}")
                    return ""

                self.log_info(f"   Wagelist table loaded successfully")

                # E. Save as PDF
                if save_pdf and output_dir:
                    pdf_path = self._save_page_as_pdf(driver, wagelist_no, output_dir)
                    if pdf_path:
                        return pdf_path
                    return ""
                else:
                    self.log_info(f"   Wagelist loaded (PDF save disabled)")
                    return "Viewed"

            except Exception as e:
                self.log_warning(f"   Attempt {attempt+1} failed: {type(e).__name__}: {e}")
                if attempt == 0:
                    time.sleep(2)

        self.log_error(f"   Failed after retries: {wagelist_no}")
        return ""

    def _wait_for_ready(self, driver, timeout: int = 10):
        """Wait for document.readyState == 'complete'."""
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass

    def _wait_for_postback(self, driver, timeout: int = 10):
        """Wait for ASP.NET postback to complete."""
        self._wait_for_ready(driver, timeout)
        time.sleep(1)
        self._wait_for_ready(driver, 5)

    def _check_error_message(self, driver) -> bool:
        """Check if the page shows an error message. Returns True if error found."""
        try:
            lbl = driver.find_element(By.ID, "lblmsg")
            msg = lbl.text.strip()
            if msg:
                self.log_warning(f"   Portal message: {msg}")
                return True
        except NoSuchElementException:
            pass
        return False

    def _save_page_as_pdf(self, driver, wagelist_no: str, output_dir: str) -> str:
        """Save the current page as a PDF using browser print-to-PDF."""
        try:
            safe_name = wagelist_no.replace("/", "-").replace("\\", "-")
            base_filename = f"WL_{safe_name}"
            extension = ".pdf"
            counter = 1
            pdf_filename = f"{base_filename}{extension}"
            save_path = os.path.join(output_dir, pdf_filename)

            while os.path.exists(save_path):
                pdf_filename = f"{base_filename} ({counter}){extension}"
                save_path = os.path.join(output_dir, pdf_filename)
                counter += 1

            pdf_data_base64 = None

            if self.app.active_browser == "firefox":
                self.log_info("   Saving PDF via Firefox print...")
                from selenium.webdriver.common.print_page_options import PrintOptions
                print_options = PrintOptions()
                print_options.orientation = "landscape"
                print_options.scale = 0.7
                pdf_data_base64 = driver.print_page(print_options)

            elif self.app.active_browser == "chrome":
                self.log_info("   Saving PDF via Chrome CDP...")
                print_options = {
                    "landscape": True,
                    "displayHeaderFooter": False,
                    "printBackground": True,
                    "scale": 0.7,
                    "marginTop": 0.4, "marginBottom": 0.4,
                    "marginLeft": 0.4, "marginRight": 0.4,
                    "paperWidth": 8.27,   # A4
                    "paperHeight": 11.69,
                }
                result = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                pdf_data_base64 = result["data"]

            if pdf_data_base64:
                pdf_data = base64.b64decode(pdf_data_base64)
                with open(save_path, "wb") as f:
                    f.write(pdf_data)
                return save_path
            else:
                self.log_error(f"   PDF data not generated for {wagelist_no}")
                return ""

        except Exception as e:
            self.log_error(f"   PDF save error for {wagelist_no}: {e}")
            return ""

    def _log_result(self, wagelist_no: str, status: str, detail: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        tags = ("success",) if "success" in status.lower() else ("failed",)
        self.safe_tree_insert(
            (wagelist_no, status, timestamp, detail), tags
        )

    def _export_results(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="print_wagelist_results.xlsx",
            filter_mode="Export All",
            title_prefix="Print Wagelist Report"
        )
