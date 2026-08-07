# tabs/physical_complete_tab.py
import subprocess
import sys
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os
import json
import time
import re
from datetime import datetime

from src import config
from src.utils import truncate_workcode
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Keys, Select, WebDriverWait, EC, NoAlertPresentException, NoSuchElementException, TimeoutException  # noqa: F401


class PhysicalCompleteTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="physical_complete")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.auto_forward_var = tkinter.BooleanVar(value=True)
        self.last_successful_panchayat = ""
        self.last_successful_codes = []
        
        self._create_widgets()
        self._load_saved_inputs()
    def _create_widgets(self) -> None:

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(3, weight=1)

        # ── Header card ──
        self._create_header_card(main_container, "✅", "Physical Complete",
                                 "Mark works as physically complete on the portal for the selected Panchayat.",
                                 icon_key="emoji_physical_complete")

        # --- Input Frame (bordered card) ---
        input_frame = ctk.CTkFrame(main_container, corner_radius=12, border_width=1,
                                   border_color=("gray85", "gray30"))
        input_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        input_frame.grid_columnconfigure(1, weight=1)

        # Row 0: Panchayat
        ctk.CTkLabel(input_frame, text="Panchayat Name:").grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar()
        self.panchayat_menu = ctk.CTkOptionMenu(input_frame, variable=self.panchayat_var, values=p_vals)
        self.panchayat_menu.grid(row=0, column=1, columnspan=3, padx=15, pady=(15, 5), sticky="ew")

        # Row 1: Work Category
        ctk.CTkLabel(input_frame, text="Work Category:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        work_category_options = [
            "Anganwadi/Other Rural Infrastructure", "Coastal Areas", "Drought Proofing", "Rural Drinking Water",
            "Food Grain", "Flood Control and Protection", "Fisheries", "Micro Irrigation Works",
            "Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers",
            "Land Development", "Other Works", "Play Ground", "Rural Connectivity", "Rural Sanitation",
            "Bharat Nirman Sewa Kendra", "Water Conservation and Water Harvesting", "Renovation of traditional water bodies"
        ]
        self.work_category_var = ctk.StringVar(value=work_category_options[8])
        self.work_category_menu = ctk.CTkOptionMenu(input_frame, variable=self.work_category_var, values=work_category_options)
        self.work_category_menu.grid(row=1, column=1, columnspan=3, padx=15, pady=5, sticky="ew")

        # Row 2: Auto Forward Checkbox
        self.auto_forward_checkbox = ctk.CTkCheckBox(
            input_frame, 
            text="Auto-Forward to Scheme Closing after success", 
            variable=self.auto_forward_var
        )
        self.auto_forward_checkbox.grid(row=2, column=1, columnspan=3, padx=15, pady=(5, 15), sticky="w")

        # Action Buttons (OUTSIDE the card)
        action_frame = self._create_action_buttons(parent_frame=main_container)
        action_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=6)

        # Data Notebook
        notebook = ctk.CTkTabview(main_container)
        notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=10)
        
        work_codes_tab = notebook.add("Work Codes to Complete")
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(notebook)
        
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1)

        wc_header_frame = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        clear_wc_button = ctk.CTkButton(wc_header_frame, text="Clear", width=80, command=lambda: self.work_codes_textbox.delete("1.0", "end"))
        clear_wc_button.pack(side="right", padx=5)

        extract_button = ctk.CTkButton(wc_header_frame, text="Extract from Text", width=120, command=self._extract_work_codes_local)
        extract_button.pack(side='right', padx=(0, 5))
        
        self.work_codes_textbox = ctk.CTkTextbox(work_codes_tab, height=150)
        self.work_codes_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10), padx=5)
        
        # Forward Button
        self.forward_btn = ctk.CTkButton(
            results_action_frame, 
            text="Forward to Scheme Closing ➡", 
            command=self.manual_forward,
            fg_color="#2b7a0b", hover_color="#1e5c06"
        )
        self.forward_btn.pack(side='left', padx=(5, 10))

        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text="📥 Export to Excel", command=self.export_report)
        self.export_button.pack(side='left')

        cols = ("Timestamp", "Panchayat", "Work Code", "Status", "Details")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=100, anchor="center")
        self.results_tree.column("Work Code", width=250)
        self.results_tree.column("Status", width=100, anchor="center")
        self.results_tree.column("Details", width=350)
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree) 

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')

    def _extract_work_codes_local(self):
        input_content = self.work_codes_textbox.get("1.0", tkinter.END)
        if not input_content.strip(): return
        FULL_WC_REGEX = re.compile(r'\b(34\d{8}(?:/\w+)+/\d+)\b')
        found_work_codes = FULL_WC_REGEX.findall(input_content)
        self.work_codes_textbox.configure(state="normal")
        self.work_codes_textbox.delete("1.0", tkinter.END)
        if found_work_codes:
            self.work_codes_textbox.insert("1.0", "\n".join(found_work_codes))
        else:
            self.work_codes_textbox.insert("1.0", "No matching full work codes found.")
        self.work_codes_textbox.configure(state="disabled")



    def _get_inputs(self):
        inputs = {
            "panchayat": self.panchayat_var.get().strip(),
            "work_category": self.work_category_var.get(),
            "work_codes_raw": self.work_codes_textbox.get("1.0", "end").strip()
        }
        inputs["work_codes"] = [line.strip() for line in inputs["work_codes_raw"].splitlines() if line.strip()]
        return inputs

    def _save_inputs(self, inputs):
        save_data = {k: v for k, v in inputs.items() if k not in ["work_codes_raw", "work_codes"]}
        try:
            self.app.history_manager.save_tab_inputs_batch("physical_complete", save_data)
        except Exception as e:
            print(f"Error saving inputs: {e}")

    def _load_saved_inputs(self):
        """Load previously saved inputs from DB."""
        data = self.app.history_manager.get_tab_inputs("physical_complete")
        if data:
            self.panchayat_var.set(data.get("panchayat", ""))
            self.work_category_var.set(data.get("work_category", "Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers"))
    def start_automation(self) -> None:
        inputs = self._get_inputs()
        if not inputs["panchayat"] or not inputs["work_category"] or not inputs["work_codes"]:
            messagebox.showwarning("Input Required", "Panchayat, Work Category, and at least one Work Code are required.")
            return

        self._save_inputs(inputs)
        self.app.update_history("location_panchayat", inputs["panchayat"])
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        
        # Reset tracking variables for this run
        self.last_successful_panchayat = inputs["panchayat"]
        self.last_successful_codes = []
        
        self.app.after(0, self.app.set_status, "Running Physical Complete Work...")
        self.log_info("--- Starting Physical Complete Automation ---")        
        driver = self.app.get_driver()
        if not driver:
            messagebox.showerror("Browser Not Found", "Please launch a browser first.")
            self.app.after(0, self.set_ui_state, False)
            return

        try:
            total_codes = len(inputs["work_codes"])
            success_count, fail_count = 0, 0

            for i, work_code in enumerate(inputs["work_codes"]):
                if self.is_stopped():
                    self.log_warning("⏹️ Automation stopped by user.")
                    break
                
                pct = (i + 1) / total_codes * 100
                status_msg = f"[{i+1}/{total_codes}] {truncate_workcode(work_code)} ({pct:.0f}%)"
                self.app.after(0, self.app.set_status, f"Physical Complete: {status_msg}")
                self.app.after(0, self.update_status, f"Processing {i+1}/{total_codes}", (i+1)/total_codes)
                self.log_info(f"  🔄 [{i+1}/{total_codes}] Completing: {truncate_workcode(work_code)}")                
                status, details = self._process_single_work_code(driver, inputs, work_code)
                self._log_result(inputs['panchayat'], work_code, status, details)
                
                if status == "Success": 
                    success_count += 1
                    self.last_successful_codes.append(work_code)
                    self.log_success(f"    ✅ {truncate_workcode(work_code)}: Marked complete")
                else: 
                    fail_count += 1
                    self.log_error(f"    ❌ {truncate_workcode(work_code)}: {details}")
            self.log_info(f"{'='*50}")
            self.log_info(f"📊 Physical Complete: ✅ {success_count} done, ❌ {fail_count} failed (of {total_codes} total)")
            self.log_info(f"{'='*50}")
            # Auto-forward Logic
            if self.auto_forward_var.get() and self.last_successful_codes:
                self.log_info("--- Auto-Forwarding to Scheme Closing ---")
                self.app.after(500, lambda: self.forward_to_scheme_closing(self.last_successful_panchayat, self.last_successful_codes, auto_start=True))

        except Exception as e:
            self.log_error(f"A critical error occurred: {str(e).splitlines()[0]}")
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.update_status("Automation Finished", 1.0)
            self.log_info("--- Automation Finished ---")
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _log_result(self, panchayat, work_code, status, details):
        timestamp = time.strftime("%H:%M:%S")
        tags = ('failed',) if 'success' not in status.lower() else ()
        self.safe_tree_insert((timestamp, panchayat, truncate_workcode(work_code), status, details), tags)

    def _process_single_work_code(self, driver, inputs, work_code):
        wait = WebDriverWait(driver, 20)
        url = config.PHYSICAL_COMPLETE_CONFIG["url"]
        
        try:
            driver.get(url)
            self.log_info("   - Selecting Panchayat...")
            panchayat_select = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlPanchayat")))
            self._select_by_text_case_insensitive(Select(panchayat_select), inputs["panchayat"])
            wait.until(EC.staleness_of(panchayat_select))

            self.log_info("   - Selecting Work Category...")
            category_select = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlWorkCategroy")))
            Select(category_select).select_by_visible_text(inputs["work_category"])
            wait.until(EC.staleness_of(category_select))

            self.log_info("   - Searching for Work Code...")
            wc_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txt_search_wrk")))
            time.sleep(1.5)  # Brief wait for postback to begin
            wc_input.send_keys(work_code)
            wc_input.send_keys(Keys.TAB)
            wait.until(EC.staleness_of(wc_input))

            work_dropdown_element = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlworkcode")))
            work_dropdown = Select(work_dropdown_element)
            option_found = False
            for option in work_dropdown.options:
                if work_code in option.get_attribute("value"):
                    work_dropdown.select_by_value(option.get_attribute("value"))
                    option_found = True
                    break
            if not option_found: return "Failed", f"Work code {work_code} not found."
            wait.until(EC.staleness_of(work_dropdown_element))
            
            self.log_info("   - Verifying Details and Checking Box...")            
            # Postback Handle
            checkbox = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_checkdisc")))
            if not checkbox.is_selected():
                checkbox.click()
                wait.until(EC.staleness_of(checkbox))

            self.log_info("   - Clicking NEXT and handling alert...")
            next_btn = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_BtnNext")))
            next_btn.click()

            try:
                alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert_text = alert.text
                if "remaining to fill" in alert_text or "remaining to payment" in alert_text:
                    alert.accept()
                    return "Failed", alert_text
                alert.accept()
            except TimeoutException:
                pass 
            
            self.log_info("   - Page 2: Waiting for Asset Details form...")            
            asset_name_input = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_grdData_ctl02_txtAsset_Name")))
            asset_desc_input = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_grdData_ctl02_txtAsset_Description")
            
            asset_name_input.clear()
            asset_name_input.send_keys("Completed")
            asset_desc_input.clear()
            asset_desc_input.send_keys("Completed")
            
            self.log_info("   - Saving Physical Completion...")
            self._find(driver, By.ID, "ctl00_ContentPlaceHolder1_btSave").click()
            
            try:
                alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert_text = alert.text
                alert.accept()
                return "Success", f"Operation completed: {alert_text}"
            except TimeoutException:
                if "Work has been Completed Successfully" in driver.page_source:
                    return "Success", "Work completed successfully (page)."
                return "Success", "Saved successfully but no confirmation alert found."

        except (TimeoutException, NoSuchElementException, NoAlertPresentException) as e:
            error_message = str(e).splitlines()[0] if str(e) else "No error message"
            self.log_error(f"   - Error: {error_message}")
            return "Failed", f"Error on page: {error_message}"
        except Exception as e:
            error_message = str(e).splitlines()[0] if str(e) else "No error message"
            self.log_error(f"   - Unexpected error: {error_message}")
            return "Failed", f"Unexpected error: {error_message}"

    def manual_forward(self):
        """Button click handler for forwarding to Scheme Closing"""
        if not self.last_successful_codes:
            messagebox.showinfo("No Data", "Koi successful work code nahi hai forward karne ke liye. Pehle automation run karein.")
            return
        self.forward_to_scheme_closing(self.last_successful_panchayat, self.last_successful_codes, auto_start=False)

    def forward_to_scheme_closing(self, panchayat, work_codes, auto_start=False):
        scheme_tab = None
        
        # NregaBot me tabs 'tab_instances' dictionary me display name ke sath store hote hain
        if hasattr(self.app, 'tab_instances') and "Scheme Closing" in self.app.tab_instances:
            scheme_tab = self.app.tab_instances["Scheme Closing"]
        elif hasattr(self.app, 'tabs') and "scheme_closing" in self.app.tabs:
            scheme_tab = self.app.tabs["scheme_closing"]
            
        if not scheme_tab:
            messagebox.showerror("Error", "Scheme Closing tab application mein load nahi hua hai. Kripya pehle us tab par ek baar click karein.")
            return
            
        try:
            # Tab ko visually switch karne ke liye
            if hasattr(self.app, 'notebook'):
                for tab_id in self.app.notebook._name_list:
                    if "Scheme Closing" in tab_id or "scheme" in tab_id.lower():
                        self.app.notebook.set(tab_id)
                        break
        except Exception as e:
            print(f"Switching tab failed: {e}")
            
        # Update the Panchayat Field
        scheme_tab.panchayat_var.set(panchayat)
        
        # Update the Work Codes
        scheme_tab.work_codes_textbox.configure(state="normal")
        scheme_tab.work_codes_textbox.delete("1.0", "end")
        scheme_tab.work_codes_textbox.insert("1.0", "\n".join(work_codes))
        
        if auto_start:
            # Chhota sa delay taaki UI update ho sake aur uske baad Scheme Closing start ho jaye
            self.app.after(500, scheme_tab.start_automation)
        else:
            messagebox.showinfo("Forwarded Successfully", f"{len(work_codes)} successful work codes 'Scheme Closing' tab mein bhej diye gaye hain.")
    def reset_ui(self) -> None:
        if messagebox.askokcancel("Reset Form?", "Are you sure? This will clear all inputs."):
            self.panchayat_var.set("")
            self.work_codes_textbox.delete("1.0", "end")
            self.safe_tree_clear()
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0)
            self.app.after(0, self.app.set_status, "Ready")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.work_category_menu.configure(state=state)
        self.work_codes_textbox.configure(state=state)
        self.auto_forward_checkbox.configure(state=state)
        self.forward_btn.configure(state=state)
        self.export_button.configure(state=state)

    def export_report(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="physical_complete_results.xlsx",
            filter_mode="Export All",
            title_prefix="Physical Complete Report"
        )

    def _get_filtered_data_and_filepath(self, export_format):
        if not self.results_tree.get_children(): 
            messagebox.showinfo("No Data", "No results to export."); return None, None
        location_panchayat = self.panchayat_entry.get().strip()
        if not location_panchayat: 
            messagebox.showwarning("Input Needed", "Panchayat Name is required for report title."); return None, None
        
        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in self.results_tree.get_children():
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[3].upper()
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status: data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status: data_to_export.append(row_values)
            
        if not data_to_export: 
            messagebox.showinfo("No Data", f"No records found for filter '{filter_option}'."); return None, None

        safe_name = "".join(c for c in location_panchayat if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        details = {"Image (.jpg)": { "ext": ".jpg", "types": [("JPEG Image", "*.jpg")]}, "PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")]}}[export_format]
        filename = f"Physical_Complete_Report_{safe_name}_{timestamp}{details['ext']}"
        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_report_path("Physical Complete"), initialfile=filename, title="Save Report")
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, headers, col_widths, file_path):
        title = f"Physical Complete Report: {self.panchayat_entry.get().strip()}"
        report_date = datetime.now().strftime('%d %b %Y')
        success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
        if success and messagebox.askyesno("Success", f"PDF Report saved to:\n{file_path}\n\nDo you want to open it?"):
            if sys.platform == "win32": os.startfile(file_path)
            else: subprocess.call(['open', file_path])