# tabs/duplicate_mr_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os
import base64
import json
import time
import threading
from datetime import datetime
from pypdf import PdfWriter, PdfReader # <-- IMPORT ADD KIYA GAYA

from src import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry
from typing import Any, Callable, Dict, List, Optional, Tuple

class DuplicateMrTab(BaseAutomationTab):
    """
    A tab for automating the process of re-printing Muster Rolls (MRs) for multiple work codes.
    """
    def __init__(self, parent: Any, app_instance: Any) -> None:
        # Lazy imports
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
        super().__init__(parent, app_instance, automation_key="duplicate_mr")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._create_widgets()
        self._load_history()
        self.current_panchayat = ""
        self.output_dir = "" # <-- ADDED
    def _create_widgets(self) -> None:
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)

        input_frame = ctk.CTkFrame(main_container)
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="Panchayat Name:").grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.panchayat_entry = AutocompleteEntry(input_frame,
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app, 
            history_key="panchayat_name")
        self.panchayat_entry.grid(row=0, column=1, padx=15, pady=10, sticky="ew")

        ctk.CTkLabel(input_frame, text="Output Action:").grid(row=1, column=0, padx=15, pady=10, sticky="w")
        self.output_action_var = ctk.StringVar(value="Save as PDF Only")
        self.output_action_menu = ctk.CTkOptionMenu(input_frame, variable=self.output_action_var, values=["Save as PDF Only", "Print and Save PDF"])
        self.output_action_menu.grid(row=1, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(input_frame, text="Orientation:").grid(row=2, column=0, padx=15, pady=10, sticky="w")
        self.orientation_var = ctk.StringVar(value="Landscape")
        self.orientation_segmented_button = ctk.CTkSegmentedButton(input_frame, variable=self.orientation_var, values=["Landscape", "Portrait"])
        self.orientation_segmented_button.grid(row=2, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(input_frame, text="PDF Scale:").grid(row=3, column=0, padx=15, pady=10, sticky="w")
        scale_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        scale_frame.grid(row=3, column=1, padx=15, pady=10, sticky="ew")
        scale_frame.grid_columnconfigure(0, weight=1)

        self.scale_slider = ctk.CTkSlider(scale_frame, from_=50, to=100, number_of_steps=50, command=self._update_scale_label)
        self.scale_slider.set(75)
        self.scale_slider.grid(row=0, column=0, sticky="ew")

        self.scale_label = ctk.CTkLabel(scale_frame, text="75%", width=40)
        self.scale_label.grid(row=0, column=1, padx=(10, 0))
        
        # --- NEW INFO LABEL ---
        ctk.CTkLabel(input_frame, text="ℹ️ Generated PDFs saved in 'Downloads/NregaBot/DuplicateMR_Output/{panchayat}/{date}'.", text_color="gray50").grid(row=4, column=1, sticky='w', padx=15, pady=(0,5))
        
        action_frame = self._create_action_buttons(input_frame)
        action_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=15, pady=(10, 15)) # <-- Row changed to 5

        notebook = ctk.CTkTabview(main_container)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        work_codes_tab = notebook.add("Work Codes")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(notebook)
        
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1) 
        
        wc_controls = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_controls.grid(row=0, column=0, sticky='ew', padx=5, pady=(5,0))
        
        clear_button = ctk.CTkButton(wc_controls, text="Clear", width=80, command=lambda: self.work_codes_textbox.delete("1.0", tkinter.END))
        clear_button.pack(side='right', padx=(0, 5))
        
        extract_button = ctk.CTkButton(wc_controls, text="Extract from Text", width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_codes_textbox))
        extract_button.pack(side='right', padx=(0, 5))

        self.work_codes_textbox = ctk.CTkTextbox(work_codes_tab, height=150)
        self.work_codes_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5) 

        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10), padx=5)
        
        # --- MERGE BUTTON ADDED ---
        self.merge_pdfs_button = ctk.CTkButton(results_action_frame, text="Merge Saved PDFs", command=self.merge_saved_pdfs)
        self.merge_pdfs_button.pack(side='left', padx=(0, 10))
        # --- END ---

        self.export_csv_button = ctk.CTkButton(results_action_frame, text="Export to CSV", command=lambda: self.export_treeview_to_csv(self.results_tree, "duplicate_mr_results.csv"))
        self.export_csv_button.pack(side="left") # Changed to left

        cols = ("Timestamp", "Work Code", "MSR No", "Status")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=100, anchor="center")
        self.results_tree.column("Work Code", width=250)
        self.results_tree.column("MSR No", width=100, anchor="center")
        self.style_treeview(self.results_tree)

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')
        
    def _update_scale_label(self, value):
        self.scale_label.configure(text=f"{int(value)}%")

    def _load_history(self):
        panchayat_history = self.app.history_manager.get_suggestions("panchayat_name")
        if not hasattr(self.panchayat_entry, 'suggestions'):
             self.panchayat_entry.suggestions = []
        self.panchayat_entry.suggestions.extend(panchayat_history)


    def _log_result(self, work_code, msr_no, status):
        timestamp = time.strftime("%H:%M:%S")
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(timestamp, work_code, msr_no, status)))
    def start_automation(self) -> None:
        panchayat = self.panchayat_entry.get().strip()
        work_codes_raw = self.work_codes_textbox.get("1.0", "end").strip()
        action = self.output_action_var.get()
        orientation = self.orientation_var.get()
        scale = self.scale_slider.get()

        if not panchayat or not work_codes_raw:
            messagebox.showwarning("Input Required", "Panchayat Name and Work Codes are required.")
            return
            
        work_codes = [line.strip() for line in work_codes_raw.splitlines() if line.strip()]
        self.app.history_manager.save_entry("panchayat_name", panchayat)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(panchayat, work_codes, action, orientation, scale))

    # --- NEW HELPER METHOD ---
    def _get_output_dir(self, panchayat_name):
        """Creates and returns the structured output directory."""
        try:
            # Sanitize panchayat name
            safe_panchayat_name = "".join(c for c in panchayat_name if c.isalnum() or c in (' ', '_')).rstrip()
            if not safe_panchayat_name:
                safe_panchayat_name = "Unknown_Panchayat"
                
            # Get date for folder name
            date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Create the full path
            # NregaBot > Duplicate_MR_Output > Panchayat Name > Date
            output_dir = os.path.join(
                self.app.get_nregabot_path("DuplicateMR_Output"),
                safe_panchayat_name,
                date_str
            )
            os.makedirs(output_dir, exist_ok=True)
            return output_dir
        except Exception as e:
            self.app.log_message(self.log_display, f"Error creating output directory: {e}", "error")
            messagebox.showerror("Directory Error", f"Could not create output directory: {e}")
            return None
        
    def load_data_from_report(self, workcodes: str, panchayat_name: str):
        """Loads data from a report tab (like Issued MR Details)."""
        # Clear existing data
        self.panchayat_entry.delete(0, "end")
        self.work_codes_textbox.configure(state="normal")
        self.work_codes_textbox.delete("1.0", "end")
        
        # Insert new data
        self.panchayat_entry.insert(0, panchayat_name)
        self.work_codes_textbox.insert("1.0", workcodes)
        self.work_codes_textbox.configure(state="disabled")
        
        # Update history
        self.app.history_manager.save_entry("panchayat_name", panchayat_name)
        
        # Switch to the work codes tab
        for tab_name in self.master.children:
            try:
                # This is a bit of a hack to find the notebook
                if isinstance(self.master.nametowin(tab_name), ctk.CTkTabview):
                    self.master.nametowin(tab_name).set("Work Codes")
                    break
            except Exception:
                pass

    def run_automation_logic(self, panchayat, work_codes, action, orientation, scale):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)

        self.app.log_message(self.log_display, "--- Starting Duplicate MR Printing ---")
        self.app.after(0, self.app.set_status, "Running Duplicate MR Print...")
        self.current_panchayat = panchayat
        
        # --- SETTING self.output_dir ---
        self.output_dir = self._get_output_dir(panchayat)
        if not self.output_dir:
            self.app.log_message(self.log_display, "Failed to create output directory. Aborting.", "error")
            self.app.after(0, self.set_ui_state, False)
            return
        self.app.log_message(self.log_display, f"Output will be in: {self.output_dir}", "info")
        # --- END ---

        driver = self.app.get_driver()
        if not driver:
            messagebox.showerror(
                "Browser Not Found",
                "No active browser session was found.\n\nPlease use the 'Launch Chrome' or 'Launch Firefox' buttons at the top-right to start a browser before running the automation."
            )
            self.app.after(0, self.set_ui_state, False)
            return

        try:
            for work_code in work_codes:
                if self.app.stop_events[self.automation_key].is_set():
                    break
                self.app.log_message(self.log_display, f"\n--- Processing Work Code: {work_code} ---")
                self._process_single_work_code(driver, work_code, action, panchayat, orientation, scale)
        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {str(e).splitlines()[0]}", "error")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.log_message(self.log_display, "\n--- Automation Finished ---")
            self.app.after(100, self._show_completion_dialog)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _show_completion_dialog(self):
        final_message = "Duplicate MR process has finished."
        # --- UPDATED PATH CHECK ---
        if self.output_dir and os.path.exists(self.output_dir) and any(os.scandir(self.output_dir)):
            if messagebox.askyesno("Complete", f"{final_message}\n\nDo you want to open the output folder?"):
                self.app.open_folder(self.output_dir)
        else:
            messagebox.showinfo("Complete", final_message)
        # --- END ---

    def _process_single_work_code(self, driver, work_code, action, panchayat, orientation, scale):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver
        wait = WebDriverWait(driver, 40)
        url = config.DUPLICATE_MR_CONFIG["url"]
        try:
            msr_options = self._get_msr_list(driver, wait, work_code, panchayat, url)
            if not msr_options: return

            for i, msr_no in enumerate(msr_options):
                if self.app.stop_events[self.automation_key].is_set(): break
                
                self.app.log_message(self.log_display, f"--- Processing MSR {i+1}/{len(msr_options)}: {msr_no} ---")
                
                driver.get(url)
                
                # --- Background Safe: Select Panchayat ---
                panchayat_dd_element = wait.until(EC.presence_of_element_located((By.ID, "ddlPanchayat")))
                self._select_by_text_case_insensitive(Select(panchayat_dd_element), panchayat)
                
                # --- Background Safe: Fill Work Code ---
                wc_input = wait.until(EC.presence_of_element_located((By.ID, "txtWork")))
                driver.execute_script("arguments[0].value = arguments[1];", wc_input, work_code)
                
                # --- Background Safe: Click Search ---
                search_btn = driver.find_element(By.ID, "imgButtonSearch")
                driver.execute_script("arguments[0].click();", search_btn)
                time.sleep(2.0)  # Short wait after click

                wait.until(lambda d: len(Select(d.find_element(By.ID, "ddlworkcode")).options) > 1)
                Select(driver.find_element(By.ID, "ddlworkcode")).select_by_index(1)
                
                wait.until(lambda d: len(Select(d.find_element(By.ID, "ddlmsrno")).options) > 1)

                current_msr_dd = Select(driver.find_element(By.ID, "ddlmsrno"))
                current_msr_dd.select_by_value(msr_no)
                
                # --- Background Safe: Click Proceed ---
                proceed_btn = driver.find_element(By.ID, "btnproceed")
                driver.execute_script("arguments[0].click();", proceed_btn)
                
                self.app.log_message(self.log_display, "   - Loading print page content...")
                
                try:
                    iframe_wait = WebDriverWait(driver, 5)
                    iframe_wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, 'iframe')))
                    self.app.log_message(self.log_display, "   - Switched to content iframe.")
                except TimeoutException:
                    self.app.log_message(self.log_display, "   - No iframe detected, proceeding in main document.")

                self.app.log_message(self.log_display, "   - Waiting for 'Print' link to become available...")
                # Presence check for print link
                wait.until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Print")))
                self.app.log_message(self.log_display, "   - Print page is ready.")
                
                pdf_path = self._save_mr_as_pdf(driver, work_code, msr_no, orientation, scale, self.output_dir)
                
                if pdf_path: self._log_result(work_code, msr_no, "Saved as PDF")
                else: self._log_result(work_code, msr_no, "PDF Save Failed")

                if "Print and Save" in action and pdf_path:
                    driver.execute_script("window.print();")
                    time.sleep(5)
                
                driver.switch_to.default_content()
        
        except TimeoutException:
            self.app.log_message(self.log_display, f"Timeout: Page element not found for work code {work_code}", "error")
            self._log_result(work_code, "N/A", "Timeout")
        except NoSuchElementException:
            self.app.log_message(self.log_display, f"Element not found for work code {work_code}", "error")
            self._log_result(work_code, "N/A", "Element not found")
        except Exception as e:
            self.app.log_message(self.log_display, f"Error processing {work_code}: {str(e).splitlines()[0]}", "error")
            self._log_result(work_code, "N/A", "Unexpected Error")

    def _get_msr_list(self, driver, wait, work_code, panchayat, url):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver
        """Helper to get list of MSRs (Background Safe)."""
        self.app.log_message(self.log_display, f"Getting MSR list for Work Code: {work_code}")
        try:
            driver.get(url)
            
            panchayat_dd_element = wait.until(EC.presence_of_element_located((By.ID, "ddlPanchayat")))
            self._select_by_text_case_insensitive(Select(panchayat_dd_element), panchayat)
            
            wc_input = wait.until(EC.presence_of_element_located((By.ID, "txtWork")))
            driver.execute_script("arguments[0].value = arguments[1];", wc_input, work_code)
            
            search_btn = driver.find_element(By.ID, "imgButtonSearch")
            driver.execute_script("arguments[0].click();", search_btn)
            time.sleep(2.0)  # Short wait after click
            
            wait.until(lambda d: len(Select(d.find_element(By.ID, "ddlworkcode")).options) > 1)
            Select(driver.find_element(By.ID, "ddlworkcode")).select_by_index(1)
            
            wait.until(lambda d: len(Select(d.find_element(By.ID, "ddlmsrno")).options) > 1)
            msr_dd_element = driver.find_element(By.ID, "ddlmsrno")
            msr_options = [opt.get_attribute('value') for opt in Select(msr_dd_element).options if '--' not in opt.text]
            
            if not msr_options:
                self.app.log_message(self.log_display, "No MSR numbers found.", "warning")
                self._log_result(work_code, "N/A", "No MSRs found")
                return []
            
            self.app.log_message(self.log_display, f"Found {len(msr_options)} MSRs: {', '.join(msr_options)}")
            return msr_options
        except TimeoutException:
            self.app.log_message(self.log_display, f"Timeout getting MSR list for {work_code}: page elements not loading", "error")
            return []
        except Exception as e:
            self.app.log_message(self.log_display, f"Error getting MSR list for {work_code}: {str(e).splitlines()[0]}", "error")
            return []

    # --- FUNCTION SIGNATURE UPDATED ---
    def _save_mr_as_pdf(self, driver, work_code, msr_no, orientation, scale, output_dir):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver
        try:
            safe_work_code = work_code.split('/')[-1][-6:]
            filename = f"MR_{safe_work_code}_{msr_no}.pdf"
            filepath = os.path.join(output_dir, filename)

            is_landscape = (orientation == "Landscape")
            pdf_scale = scale / 100.0
            pdf_data_base64 = None

            # --- CSS for Orientation ---
            if is_landscape:
                driver.execute_script(
                    "var css = '@page { size: landscape; }';"
                    "var head = document.head || document.getElementsByTagName('head')[0];"
                    "var style = document.createElement('style');"
                    "style.type = 'text/css'; style.media = 'print';"
                    "if (style.styleSheet){ style.styleSheet.cssText = css; }"
                    "else { style.appendChild(document.createTextNode(css)); }"
                    "head.appendChild(style);"
                )

            # --- Fix: Remove blank page caused by website update ---
            driver.execute_script("""
                // 1. Inject print CSS to suppress all known blank-page causes
                var styleTag = document.createElement('style');
                styleTag.innerHTML = `
                    @media print {
                        * { page-break-after: auto !important; page-break-before: auto !important; break-after: auto !important; break-before: auto !important; }
                        body::after { display: none !important; content: none !important; }
                    }
                `;
                document.head.appendChild(styleTag);

                // 2. Remove trailing empty block elements from body
                var bodyChildren = Array.from(document.body.children);
                for (var i = bodyChildren.length - 1; i >= 0; i--) {
                    var el = bodyChildren[i];
                    if (el.innerText.trim() === '' && el.querySelectorAll('img, input, table, iframe, canvas, video').length === 0) {
                        el.parentNode.removeChild(el);
                    } else {
                        break; // stop at first non-empty element from the end
                    }
                }

                // 3. Force remove page-break-after on ALL elements
                var allEls = document.querySelectorAll('*');
                allEls.forEach(function(el) {
                    el.style.pageBreakAfter = 'auto';
                    el.style.pageBreakBefore = 'auto';
                    el.style.breakAfter = 'auto';
                    el.style.breakBefore = 'auto';
                });
            """)

            if self.app.active_browser == 'firefox':
                # Firefox: Inject a fixed div using JavaScript
                footer_js = """
                var footer = document.createElement('div');
                footer.innerText = 'NregaBot.com';
                footer.style.position = 'fixed';
                footer.style.bottom = '0';
                footer.style.right = '0';
                footer.style.padding = '10px';
                footer.style.fontSize = '10px';
                footer.style.color = '#cccccc';  // Light Gray
                footer.style.fontFamily = 'Arial, sans-serif';
                footer.style.zIndex = '9999';
                document.body.appendChild(footer);
                """
                driver.execute_script(footer_js)
                
                self.app.log_message(self.log_display, "   - Note: PDF Scale setting is not supported for Firefox and will be ignored.", "warning")
                pdf_data_base64 = driver.print_page()
            
            elif self.app.active_browser == 'chrome':
                # Inject footer as a fixed-position element (avoids CDP footer causing extra blank page)
                driver.execute_script("""
                    var existing = document.getElementById('nregabot-footer');
                    if (!existing) {
                        var footer = document.createElement('div');
                        footer.id = 'nregabot-footer';
                        footer.innerText = 'NregaBot.com';
                        footer.style.position = 'fixed';
                        footer.style.bottom = '6px';
                        footer.style.right = '10px';
                        footer.style.fontSize = '9px';
                        footer.style.color = '#d3d3d3';
                        footer.style.fontFamily = 'Helvetica, sans-serif';
                        footer.style.zIndex = '9999';
                        document.body.appendChild(footer);
                    }
                """)

                print_options = {
                    "landscape": is_landscape,
                    "displayHeaderFooter": False,      # Disabled - footer injected via JS instead
                    "printBackground": False,
                    "scale": pdf_scale,
                    "marginTop": 0.4,
                    "marginBottom": 0.4,
                    "marginLeft": 0.4, "marginRight": 0.4
                }
                result = driver.execute_cdp_cmd('Page.printToPDF', print_options)
                pdf_data_base64 = result['data']

            if pdf_data_base64:
                pdf_data = base64.b64decode(pdf_data_base64)
                with open(filepath, 'wb') as f:
                    f.write(pdf_data)
                return filepath
            else:
                return None
        except Exception as e:
            self.app.log_message(self.log_display, f"Error saving PDF: {e}", "error")
            return None

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_entry.configure(state=state)
        self.work_codes_textbox.configure(state=state)
        self.output_action_menu.configure(state=state)
        self.orientation_segmented_button.configure(state=state)
        self.scale_slider.configure(state=state)
        self.merge_pdfs_button.configure(state=state) # <-- ADDED
        self.export_csv_button.configure(state=state) # <-- ADDED
    def reset_ui(self) -> None:
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver
        if messagebox.askokcancel("Reset Form?", "Are you sure?"):
            self.panchayat_entry.delete(0, "end")
            self.work_codes_textbox.delete("1.0", "end")
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.orientation_var.set("Landscape")
            self.scale_slider.set(75)
            self.scale_label.configure(text="75%")
            self.app.after(0, self.app.set_status, "Ready")

    # --- NEW MERGE PDFS METHOD ---
    def merge_saved_pdfs(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver
        self.app.log_message(self.log_display, "Starting PDF merge...")
        
        # 1. Get current output directory
        panchayat = self.panchayat_entry.get().strip()
        if not panchayat:
            messagebox.showwarning("Input Required", "Please enter a Panchayat name to find the correct folder.", parent=self)
            return
            
        # Get the directory for *today's* saved files for this panchayat
        output_dir = self._get_output_dir(panchayat)
        if not os.path.exists(output_dir):
            self.app.log_message(self.log_display, f"No output folder found for today: {output_dir}", "warning")
            messagebox.showinfo("No Files", f"No saved PDFs found for '{panchayat}' from today.", parent=self)
            return

        # 2. Find all PDF files in that directory
        pdf_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            self.app.log_message(self.log_display, "No PDF files found in the directory.", "warning")
            messagebox.showinfo("No Files", f"No PDFs found in:\n{output_dir}", parent=self)
            return
            
        pdf_files.sort() # Sort files alphabetically
        self.app.log_message(self.log_display, f"Found {len(pdf_files)} PDF files to merge.")

        # 3. Get output file name from user
        dialog = ctk.CTkInputDialog(text="Enter a base name for the merged file:", title="Merge PDFs")
        base_name = dialog.get_input()
        
        if not base_name:
            self.app.log_message(self.log_display, "Merge cancelled by user.", "info")
            return

        # 4. Get unique output path in the Merged_Pdf_Output folder
        try:
            merge_output_dir = self.app.get_nregabot_path("Merged_PDF")
            os.makedirs(merge_output_dir, exist_ok=True)
            
            date_str = datetime.now().strftime("%d-%b-%Y")
            file_name = f"{base_name}_{date_str}.pdf"
            output_path = os.path.join(merge_output_dir, file_name)
            
            count = 1
            while os.path.exists(output_path):
                file_name = f"{base_name}_{date_str}({count}).pdf"
                output_path = os.path.join(merge_output_dir, file_name)
                count += 1
        except Exception as e:
            messagebox.showerror("Path Error", f"Could not create merge output path: {e}", parent=self)
            return

        # 5. Run merge in a separate thread to keep UI responsive
        self.app.start_automation_thread(
            "pdf_merger_dup_mr", # Use a temporary key
            self._run_merge_logic, 
            args=(pdf_files, output_path)
        )

    def _run_merge_logic(self, file_list, output_path):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium import webdriver
        """The actual PDF merging logic that runs in a thread."""
        self.app.after(0, self.set_ui_state, True)
        self.app.log_message(self.log_display, f"Merging {len(file_list)} files...")
        self.app.after(0, self.app.set_status, "Merging PDFs...")
        
        # Note: duplicate_mr_tab uses "pdf_merger_dup_mr" event key, 
        # while musterroll_gen_tab uses "pdf_merger_mr". 
        # Getting the key dynamically based on current file/tab:
        stop_event_key = "pdf_merger_dup_mr" if "duplicate" in self.automation_key else "pdf_merger_mr"

        try:
            merger = PdfWriter()
            for i, pdf_path in enumerate(file_list):
                if self.app.stop_events.get(stop_event_key, threading.Event()).is_set():
                    self.app.log_message(self.log_display, "Merge cancelled.", "warning")
                    merger.close()
                    return
                
                self.app.log_message(self.log_display, f"Processing file {i+1}/{len(file_list)}: {os.path.basename(pdf_path)}")
                
                # Smart blank page filtering logic
                reader = PdfReader(pdf_path)
                num_pages = len(reader.pages)

                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    
                    if page_num == num_pages - 1:
                        text = page.extract_text()
                        if text is None or len(text.strip()) < 250:
                            self.app.log_message(self.log_display, f"  -> Skipped footer-only last page in {os.path.basename(pdf_path)}")
                            continue 

                    merger.add_page(page)
            
            with open(output_path, "wb") as f_out:
                merger.write(f_out)
            merger.close()
            
            self.app.log_message(self.log_display, "Merge complete!", "success")
            messagebox.showinfo("Success", f"Successfully merged {len(file_list)} files into:\n{output_path}", parent=self)
            if messagebox.askyesno("Open Location?", "Open the Merged PDFs folder?", parent=self):
                self.app.open_folder(os.path.dirname(output_path))
                
        except Exception as e:
            self.app.log_message(self.log_display, f"Error during merge: {e}", "error")
            messagebox.showerror("Merge Error", f"An error occurred: {e}", parent=self)
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")