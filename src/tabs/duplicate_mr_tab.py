# tabs/duplicate_mr_tab.py
import tkinter
from tkinter import ttk, messagebox
import customtkinter as ctk
import os
import base64
import json
import time
import threading
from datetime import datetime
try:
    from pypdf import PdfWriter, PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfWriter, PdfReader
    except ImportError:
        PdfWriter = PdfReader = None

from src import config
from .base_tab import BaseAutomationTab
from src.utils import truncate_workcode
from src.i18n import tr
from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, TimeoutException  # noqa: F401


class DuplicateMrTab(BaseAutomationTab):
    """
    A tab for automating the process of re-printing Muster Rolls (MRs) for multiple work codes.
    """
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="duplicate_mr")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._create_widgets()
        self._load_history()
        self._load_inputs()
        self.current_panchayat = ""
        self.output_dir = "" # <-- ADDED
    def _create_widgets(self) -> None:

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(3, weight=1)

        # ── Header card ──
        self._create_header_card(main_container, "🖨️", tr("tab.duplicate_mr.title"), tr("tab.duplicate_mr.subtitle"),
                                 icon_key="emoji_duplicate_mr")

        input_frame = ctk.CTkFrame(main_container, corner_radius=12, border_width=1,
                                   border_color=("gray85", "gray30"))
        input_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text=tr("common.panchayat_name_label")).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(input_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=0, column=1, padx=15, pady=10, sticky="ew")

        ctk.CTkLabel(input_frame, text=tr("common.output_action")).grid(row=1, column=0, padx=15, pady=10, sticky="w")
        self.output_action_var = ctk.StringVar(value="Save as PDF Only")
        self.output_action_menu = ctk.CTkOptionMenu(input_frame, variable=self.output_action_var, values=["Save as PDF Only", "Print and Save PDF"])
        self.output_action_menu.grid(row=1, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(input_frame, text=tr("common.orientation")).grid(row=2, column=0, padx=15, pady=10, sticky="w")
        self.orientation_var = ctk.StringVar(value="Landscape")
        self.orientation_segmented_button = ctk.CTkSegmentedButton(input_frame, variable=self.orientation_var, values=["Landscape", "Portrait"])
        self.orientation_segmented_button.grid(row=2, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(input_frame, text=tr("common.pdf_scale")).grid(row=3, column=0, padx=15, pady=10, sticky="w")
        scale_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        scale_frame.grid(row=3, column=1, padx=15, pady=10, sticky="ew")
        scale_frame.grid_columnconfigure(0, weight=1)

        self.scale_slider = ctk.CTkSlider(scale_frame, from_=50, to=100, number_of_steps=50, command=self._update_scale_label)
        self.scale_slider.set(75)
        self.scale_slider.grid(row=0, column=0, sticky="ew")

        self.scale_label = ctk.CTkLabel(scale_frame, text="75%", width=40)
        self.scale_label.grid(row=0, column=1, padx=(10, 0))
        
        # --- NEW INFO LABEL ---
        ctk.CTkLabel(input_frame, text="💡 Generated PDFs saved in 'Downloads/NregaBot/DuplicateMR_Output/{panchayat}/{date}'.", text_color="gray50").grid(row=4, column=1, sticky='w', padx=15, pady=(0,5))
        
        # ── Action buttons (OUTSIDE the card) ──
        action_frame = self._create_action_buttons(parent_frame=main_container)
        action_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=6)

        notebook = ctk.CTkTabview(main_container)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=10)
        
        work_codes_tab = notebook.add("Work Codes")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(notebook)
        
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1) 
        
        wc_controls = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_controls.grid(row=0, column=0, sticky='ew', padx=5, pady=(5,0))
        
        clear_button = ctk.CTkButton(wc_controls, text=tr("common.clear"), width=80, command=lambda: self.work_codes_textbox.delete("1.0", tkinter.END))
        clear_button.pack(side='right', padx=(0, 5))
        
        extract_button = ctk.CTkButton(wc_controls, text=tr("common.extract_from_text"), width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_codes_textbox))
        extract_button.pack(side='right', padx=(0, 5))

        self.work_codes_textbox = ctk.CTkTextbox(work_codes_tab, height=150)
        self.work_codes_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5) 

        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10), padx=5)
        
        # --- MERGE BUTTON ADDED ---
        self.merge_pdfs_button = ctk.CTkButton(results_action_frame, text=tr("common.merge_saved_pdfs"), command=self.merge_saved_pdfs)
        self.merge_pdfs_button.pack(side='left', padx=(0, 10))
        # --- END ---

        self.export_csv_button = ctk.CTkButton(results_action_frame, text=tr("common.export_excel"), command=lambda: self.export_treeview_to_excel(self.results_tree, default_filename="duplicate_mr_results.xlsx", filter_mode="Export All"))
        self.export_csv_button.pack(side="left") # Changed to left

        cols = ("Timestamp", "Panchayat", "Work Code", "MSR No", "Status")
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

    def _save_inputs(self, data):
        """Save tab inputs to DB."""
        try:
            self.app.history_manager.save_tab_inputs_batch("duplicate_mr", data)
        except Exception as e:
            pass

    def _load_inputs(self):
        """Load saved tab inputs from DB."""
        data = self.app.history_manager.get_tab_inputs("duplicate_mr")
        if data:
            if data.get('panchayat'):
                self.panchayat_var.set(data['panchayat'])
            self.output_action_var.set(data.get('output_action', 'Save as PDF Only'))
            self.orientation_var.set(data.get('orientation', 'Landscape'))
            try:
                scale = float(data.get('scale', 75))
                self.scale_slider.set(scale)
                self._update_scale_label(scale)
            except ValueError:
                pass

    def _load_history(self):
        panchayat_history = self.app.history_manager.get_suggestions("location_panchayat")
        # With CTkOptionMenu, suggestions are set at widget creation
        pass


    def _log_result(self, panchayat, work_code, msr_no, status):
        timestamp = time.strftime("%H:%M:%S")
        self.safe_tree_insert((timestamp, panchayat, truncate_workcode(work_code), msr_no, status))
    def start_automation(self) -> None:
        panchayat = self.panchayat_var.get().strip()
        work_codes_raw = self.work_codes_textbox.get("1.0", "end").strip()
        action = self.output_action_var.get()
        orientation = self.orientation_var.get()
        scale = self.scale_slider.get()

        if not panchayat or not work_codes_raw:
            messagebox.showwarning(tr("dialogs.input_required"), tr("dialogs.panchayat_workcodes_required"))
            return
            
        work_codes = [line.strip() for line in work_codes_raw.splitlines() if line.strip()]
        self._save_inputs({
            'panchayat': panchayat,
            'output_action': action,
            'orientation': orientation,
            'scale': scale,
        })
        self.app.history_manager.save_entry("location_panchayat", panchayat)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(panchayat, work_codes, action, orientation, scale))

    # --- NEW HELPER METHOD ---
    def _get_output_dir(self, location_panchayat):
        """Creates and returns the structured output directory."""
        try:
            # Sanitize panchayat name
            safe_location_panchayat = "".join(c for c in location_panchayat if c.isalnum() or c in (' ', '_')).rstrip()
            if not safe_location_panchayat:
                safe_location_panchayat = "Unknown_Panchayat"
                
            # Get date for folder name
            date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Create the full path
            # NregaBot > Duplicate_MR_Output > Panchayat Name > Date
            output_dir = os.path.join(
                self.app.get_nregabot_path("DuplicateMR_Output"),
                safe_location_panchayat,
                date_str
            )
            os.makedirs(output_dir, exist_ok=True)
            return output_dir
        except Exception as e:
            self.log_error(f"Error creating output directory: {e}")
            messagebox.showerror(tr("dialogs.directory_error"), tr("dialogs.could_not_create_output_dir", error=e))
            return None
        
    def load_data_from_report(self, workcodes: str, location_panchayat: str):
        """Loads data from a report tab (like Issued MR Details)."""
        # Clear existing data
        self.panchayat_var.set("")
        self.work_codes_textbox.configure(state="normal")
        self.work_codes_textbox.delete("1.0", "end")
        
        # Insert new data
        self.panchayat_var.set(location_panchayat)
        self.work_codes_textbox.insert("1.0", workcodes)
        self.work_codes_textbox.configure(state="disabled")
        
        # Update history
        self.app.history_manager.save_entry("location_panchayat", location_panchayat)
        
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

        self.log_info("--- Starting Duplicate MR Printing ---")
        self.app.after(0, self.app.set_status, "Running Duplicate MR Print...")
        self.current_panchayat = panchayat
        
        # --- SETTING self.output_dir ---
        self.output_dir = self._get_output_dir(panchayat)
        if not self.output_dir:
            self.log_error("Failed to create output directory. Aborting.")
            self.app.after(0, self.set_ui_state, False)
            return
        self.log_info(f"Output will be in: {self.output_dir}")
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
                if self.is_stopped():
                    break
                self.log_info(f"--- Processing Work Code: {work_code} ---")
                self._process_single_work_code(driver, work_code, action, panchayat, orientation, scale)
        except Exception as e:
            self.log_error(f"A critical error occurred: {str(e).splitlines()[0]}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.log_info("--- Automation Finished ---")
            self.app.after(100, self._show_completion_dialog)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _show_completion_dialog(self):
        # Count success/fail from results_tree
        # Status values: "Saved as PDF" (success), "PDF Save Failed", "Timeout", "No MSRs found", etc.
        success_count = sum(1 for item in self.results_tree.get_children() if 'saved' in str(self.results_tree.item(item)['values'][3]).lower())
        fail_count = sum(1 for item in self.results_tree.get_children() if 'saved' not in str(self.results_tree.item(item)['values'][3]).lower())
        total_count = success_count + fail_count
        
        # Log structured summary first
        self.log_info(f"📊 Duplicate MR Complete: ✅ {success_count} saved, ❌ {fail_count} failed (of {total_count} total)")
        
        final_message = f"Duplicate MR process has finished.\n✅ {success_count} saved, ❌ {fail_count} failed"
        # --- UPDATED PATH CHECK ---
        if self.output_dir and os.path.exists(self.output_dir) and any(os.scandir(self.output_dir)):
            if messagebox.askyesno(tr("dialogs.complete"), tr("dialogs.open_output_after", summary=final_message)):
                self.app.open_folder(self.output_dir)
        else:
            self.log_info(f"📊 {final_message}")

    def _process_single_work_code(self, driver, work_code, action, panchayat, orientation, scale):
        wait = WebDriverWait(driver, 40)
        url = config.DUPLICATE_MR_CONFIG["url"]
        try:
            msr_options = self._get_msr_list(driver, wait, work_code, panchayat, url)
            if not msr_options: return

            for i, msr_no in enumerate(msr_options):
                if self.is_stopped(): break
                
                self.log_info(f"--- Processing MSR {i+1}/{len(msr_options)}: {msr_no} ---")                
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
                
                self.log_info("   - Loading print page content...")                
                try:
                    iframe_wait = WebDriverWait(driver, 5)
                    iframe_wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, 'iframe')))
                    self.log_info("   - Switched to content iframe.")
                except TimeoutException:
                    self.log_info("   - No iframe detected, proceeding in main document.")
                self.log_info("   - Waiting for 'Print' link to become available...")
                # Presence check for print link
                wait.until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Print")))
                self.log_info("   - Print page is ready.")                
                pdf_path = self._save_mr_as_pdf(driver, work_code, msr_no, orientation, scale, self.output_dir)
                
                if pdf_path: self._log_result(panchayat, work_code, msr_no, "Saved as PDF")
                else: self._log_result(panchayat, work_code, msr_no, "PDF Save Failed")

                if "Print and Save" in action and pdf_path:
                    driver.execute_script("window.print();")
                    time.sleep(5)
                
                driver.switch_to.default_content()
        
        except TimeoutException:
            self.log_error(f"Timeout: Page element not found for work code {work_code}")
            self._log_result(panchayat, work_code, "N/A", "Timeout")
        except NoSuchElementException:
            self.log_error(f"Element not found for work code {work_code}")
            self._log_result(panchayat, work_code, "N/A", "Element not found")
        except Exception as e:
            self.log_error(f"Error processing {work_code}: {str(e).splitlines()[0]}")
            self._log_result(panchayat, work_code, "N/A", "Unexpected Error")

    def _get_msr_list(self, driver, wait, work_code, panchayat, url):
        """Helper to get list of MSRs (Background Safe)."""
        self.log_info(f"Getting MSR list for Work Code: {work_code}")
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
                self.log_warning("No MSR numbers found.")
                self._log_result(panchayat, work_code, "N/A", "No MSRs found")
                return []
            
            self.log_info(f"Found {len(msr_options)} MSRs: {', '.join(msr_options)}")
            return msr_options
        except TimeoutException:
            self.log_error(f"Timeout getting MSR list for {work_code}: page elements not loading")
            return []
        except Exception as e:
            self.log_error(f"Error getting MSR list for {work_code}: {str(e).splitlines()[0]}")
            return []

    # --- FUNCTION SIGNATURE UPDATED ---
    def _save_mr_as_pdf(self, driver, work_code, msr_no, orientation, scale, output_dir):
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
                
                self.log_warning("   - Note: PDF Scale setting is not supported for Firefox and will be ignored.")
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
            self.log_error(f"Error saving PDF: {e}")
            return None

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.work_codes_textbox.configure(state=state)
        self.output_action_menu.configure(state=state)
        self.orientation_segmented_button.configure(state=state)
        self.scale_slider.configure(state=state)
        self.merge_pdfs_button.configure(state=state) # <-- ADDED
        self.export_csv_button.configure(state=state) # <-- ADDED
    def reset_ui(self) -> None:
        if messagebox.askokcancel(tr("dialogs.reset_form"), tr("dialogs.are_you_sure")):
            self.panchayat_var.set("")
            self.work_codes_textbox.delete("1.0", "end")
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.safe_tree_clear()
            self.orientation_var.set("Landscape")
            self.scale_slider.set(75)
            self.scale_label.configure(text="75%")
            self.app.after(0, self.app.set_status, "Ready")

    # --- NEW MERGE PDFS METHOD ---
    def merge_saved_pdfs(self):
        self.log_info("Starting PDF merge...")        
        # 1. Get current output directory
        panchayat = self.panchayat_var.get().strip()
        if not panchayat:
            messagebox.showwarning(tr("dialogs.input_required"), tr("dialogs.enter_panchayat_folder"), parent=self)
            return
            
        # Get the directory for *today's* saved files for this panchayat
        output_dir = self._get_output_dir(panchayat)
        if not os.path.exists(output_dir):
            self.log_warning(f"No output folder found for today: {output_dir}")
            messagebox.showinfo(tr("dialogs.no_files"), tr("dialogs.no_pdfs_today", panchayat=panchayat), parent=self)
            return

        # 2. Find all PDF files in that directory
        pdf_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            self.log_warning("No PDF files found in the directory.")
            messagebox.showinfo(tr("dialogs.no_files"), tr("dialogs.no_pdfs_in", output_dir=output_dir), parent=self)
            return
            
        pdf_files.sort() # Sort files alphabetically
        self.log_info(f"Found {len(pdf_files)} PDF files to merge.")
        # 3. Get output file name from user
        dialog = ctk.CTkInputDialog(text=tr("common.merge_base_name"), title=tr("common.merge_pdfs"))
        base_name = dialog.get_input()
        
        if not base_name:
            self.log_info("Merge cancelled by user.")
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
            messagebox.showerror(tr("dialogs.path_error"), tr("dialogs.could_not_create_merge_output_path", error=e), parent=self)
            return

        # 5. Run merge in a separate thread to keep UI responsive
        self.app.start_automation_thread(
            "pdf_merger_dup_mr", # Use a temporary key
            self._run_merge_logic, 
            args=(pdf_files, output_path)
        )

    def _run_merge_logic(self, file_list, output_path):
        """The actual PDF merging logic that runs in a thread."""
        if PdfWriter is None:
            self.log_error("PDF library (pypdf/PyPDF2) not installed. Please reinstall the latest version from nregabot.com.")
            messagebox.showerror(tr("dialogs.pdf_lib_missing"), tr("dialogs.pdf_lib_missing_msg"), parent=self)
            return
        self.app.after(0, self.set_ui_state, True)
        self.log_info(f"Merging {len(file_list)} files...")
        self.app.after(0, self.app.set_status, "Merging PDFs...")
        
        # Note: duplicate_mr_tab uses "pdf_merger_dup_mr" event key, 
        # while musterroll_gen_tab uses "pdf_merger_mr". 
        # Getting the key dynamically based on current file/tab:
        stop_event_key = "pdf_merger_dup_mr" if "duplicate" in self.automation_key else "pdf_merger_mr"

        try:
            merger = PdfWriter()
            for i, pdf_path in enumerate(file_list):
                if self.app.stop_events.get(stop_event_key, threading.Event()).is_set():
                    self.log_warning("Merge cancelled.")
                    merger.close()
                    return
                
                self.log_info(f"Processing file {i+1}/{len(file_list)}: {os.path.basename(pdf_path)}")                
                # Smart blank page filtering logic
                reader = PdfReader(pdf_path)
                num_pages = len(reader.pages)

                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    
                    if page_num == num_pages - 1:
                        text = page.extract_text()
                        if text is None or len(text.strip()) < 250:
                            self.log_info(f"  -> Skipped footer-only last page in {os.path.basename(pdf_path)}")
                            continue 

                    merger.add_page(page)
            
            with open(output_path, "wb") as f_out:
                merger.write(f_out)
            merger.close()
            
            self.log_success("Merge complete!")
            messagebox.showinfo(tr("dialogs.success"), tr("dialogs.merged_success", count=len(file_list), path=output_path), parent=self)
            if messagebox.askyesno(tr("dialogs.open_location"), tr("dialogs.open_merged_folder"), parent=self):
                self.app.open_folder(os.path.dirname(output_path))
                
        except Exception as e:
            self.log_error(f"Error during merge: {e}")
            messagebox.showerror(tr("dialogs.merge_error"), tr("dialogs.merge_error_generic", error=e), parent=self)
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")