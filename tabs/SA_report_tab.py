# tabs/SA_report_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time, os, sys, re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from fpdf import FPDF
from utils import resource_path
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry

class SAReportTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="social_audit_respond")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_widgets()

    def _create_widgets(self):
        # Frame for all user input controls
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="new", padx=10, pady=10)
        controls_frame.grid_columnconfigure(1, weight=1)

        # --- Input Fields for the NEW page ---
        ctk.CTkLabel(controls_frame, text="Panchayat:").grid(row=0, column=0, sticky='w', padx=15, pady=(15, 5))
        self.panchayat_entry = AutocompleteEntry(controls_frame, suggestions_list=self.app.history_manager.get_suggestions("audit_panchayat_respond"))
        self.panchayat_entry.grid(row=0, column=1, sticky='ew', padx=15, pady=(15, 5))
        ctk.CTkLabel(controls_frame, text="On PO LOGIN, go to D23 > Social Audit View, then start the automation. Stay on that page.", text_color="gray50").grid(row=1, column=1, sticky='w', padx=15, pady=(0,10))


        ctk.CTkLabel(controls_frame, text="Audit Conducted in:").grid(row=2, column=0, sticky='w', padx=15, pady=5)
        current_year = datetime.now().year
        years = [f"{year}-{year+1}" for year in range(current_year, current_year - 8, -1)]
        self.year_entry = ctk.CTkComboBox(controls_frame, values=years)
        self.year_entry.grid(row=2, column=1, sticky='ew', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text="Issue Status:").grid(row=3, column=0, sticky='w', padx=15, pady=5)
        status_options = ["Pending", "Closed"]
        self.status_entry = ctk.CTkComboBox(controls_frame, values=status_options)
        self.status_entry.grid(row=3, column=1, sticky='ew', padx=15, pady=5)

        action_frame = self._create_action_buttons(parent_frame=controls_frame)
        action_frame.grid(row=4, column=0, columnspan=2, pady=10)

        notebook = ctk.CTkTabview(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        results_tab = notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=notebook)

        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)
        
        export_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        export_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.export_button = ctk.CTkButton(export_frame, text="Export Report", command=self.export_report)
        self.export_button.pack(side="left")
        
        # --- UPDATE: Added PNG Export ---
        self.export_format_menu = ctk.CTkOptionMenu(export_frame, values=["PDF (.pdf)", "PNG (.png)", "CSV (.csv)"])
        # --- END UPDATE ---
        
        self.export_format_menu.pack(side="left", padx=5)

        cols = ("SR#", "District", "Block", "Panchayat", "Issue Number", "Issue Type", "Forwarded To", "Status", "Issue Description")
        self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        
        self.results_tree.column("SR#", width=40, anchor='center'); self.results_tree.column("District", width=100); self.results_tree.column("Block", width=100); self.results_tree.column("Panchayat", width=100); self.results_tree.column("Issue Number", width=120); self.results_tree.column("Issue Type", width=150); self.results_tree.column("Forwarded To", width=80); self.results_tree.column("Status", width=80); self.results_tree.column("Issue Description", width=350)

        self.results_tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=1, column=1, sticky='ns')
        self.style_treeview(self.results_tree)

    def set_ui_state(self, running: bool):
        self.set_common_ui_state(running); state = "disabled" if running else "normal"; self.panchayat_entry.configure(state=state); self.year_entry.configure(state=state); self.status_entry.configure(state=state)

    def reset_ui(self):
        """Resets inputs to default."""
        super().reset_ui() # Call base to clear logs/status
        
        # Clear Panchayat
        self.panchayat_entry.delete(0, tkinter.END)
        
        # Reset Dropdowns (Select first option if available)
        try:
            current_year = datetime.now().year
            default_year = f"{current_year}-{current_year+1}"
            self.year_entry.set(default_year)
            self.status_entry.set("Pending")
        except: pass
        
        # Clear Treeview
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

    def start_automation(self):
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        inputs = {'panchayat': self.panchayat_entry.get().strip(), 'year': self.year_entry.get().strip(), 'status': self.status_entry.get().strip()}
        if not all(inputs.values()): messagebox.showwarning("Input Error", "All fields are required."); return
        
        self.app.update_history("audit_panchayat_respond", inputs['panchayat'])
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True); self.app.clear_log(self.log_display); self.app.log_message(self.log_display, "Starting SA View/Respond Issue automation...")
        try:
            driver = self.app.get_driver();
            if not driver: return
            wait = WebDriverWait(driver, 20); url = "https://mnregaweb2.nic.in/netnrega/SocialAuditFindings/SA-ViewRespond-Issue.aspx"; driver.get(url)
            PANCHAYAT_ID, YEAR_ID, STATUS_ID, GET_DETAILS_BTN_ID, RESULTS_TABLE_ID, SPINNER_ID = ("ContentPlaceHolder1_ddlPanchayat", "ContentPlaceHolder1_ddlAuditConduct", "ContentPlaceHolder1_ddlStatus", "ContentPlaceHolder1_btnFilterData", "ContentPlaceHolder1_grd_IssueDetails", "ContentPlaceHolder1_UpdateProgress1")

            self.app.log_message(self.log_display, f"Selecting Panchayat: {inputs['panchayat']}"); Select(wait.until(EC.element_to_be_clickable((By.ID, PANCHAYAT_ID)))).select_by_visible_text(inputs['panchayat']); wait.until(EC.invisibility_of_element_located((By.ID, SPINNER_ID)))
            self.app.log_message(self.log_display, f"Selecting Year: {inputs['year']}"); Select(wait.until(EC.element_to_be_clickable((By.ID, YEAR_ID)))).select_by_visible_text(inputs['year']); wait.until(EC.invisibility_of_element_located((By.ID, SPINNER_ID)))
            self.app.log_message(self.log_display, f"Selecting Status: {inputs['status']}"); Select(wait.until(EC.element_to_be_clickable((By.ID, STATUS_ID)))).select_by_visible_text(inputs['status'])
            self.app.log_message(self.log_display, "Fetching details...");
            try: old_first_row = driver.find_element(By.XPATH, f"//table[@id='{RESULTS_TABLE_ID}']//tr[2]")
            except NoSuchElementException: old_first_row = None
            driver.find_element(By.ID, GET_DETAILS_BTN_ID).click(); wait.until(EC.invisibility_of_element_located((By.ID, SPINNER_ID)))
            if old_first_row:
                try: wait.until(EC.staleness_of(old_first_row))
                except TimeoutException: self.app.log_message(self.log_display, "Staleness check timed out, proceeding...", "warning")

            table = wait.until(EC.presence_of_element_located((By.ID, RESULTS_TABLE_ID))); total_rows = len(table.find_elements(By.XPATH, ".//tr[position()>1]")); self.app.log_message(self.log_display, f"Found {total_rows} records.")
            for i in range(total_rows):
                if self.app.stop_events[self.automation_key].is_set(): self.app.log_message(self.log_display, "Stop signal received.", "warning"); break
                
                # --- UPDATE: Better Status ---
                status_msg = f"Processing row {i+1}/{total_rows}"
                self.app.after(0, self.app.set_status, status_msg)
                self.app.after(0, self.update_status, status_msg, (i+1)/total_rows)
                # --- END UPDATE ---
                
                row = wait.until(EC.presence_of_element_located((By.XPATH, f"//table[@id='{RESULTS_TABLE_ID}']//tr[{i+2}]"))); cells = row.find_elements(By.TAG_NAME, "td")
                
                sr_no, district, block, panchayat, issue_no, issue_type, forwarded_to, status = (cells[0].text.strip(), cells[1].text.strip(), cells[2].text.strip(), cells[3].text.strip(), cells[4].text.strip(), cells[5].text.strip(), cells[6].text.strip(), cells[7].text.strip())
                self.app.log_message(self.log_display, f"({sr_no}/{total_rows}) Clicking 'View' for Issue: {issue_no}"); view_button = cells[9].find_element(By.TAG_NAME, "input"); driver.execute_script("arguments[0].click();", view_button)
                modal_wait = WebDriverWait(driver, 10); issue_description = modal_wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_lblIssueDesc"))).text.strip()
                modal_wait.until(EC.element_to_be_clickable((By.ID, "btnCloseModel"))).click(); modal_wait.until(EC.invisibility_of_element_located((By.ID, "successModal")))
                try: modal_wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))
                except TimeoutException: self.app.log_message(self.log_display, "Modal backdrop did not disappear normally. Proceeding...", "warning")
                
                result_data = (sr_no, district, block, panchayat, issue_no, issue_type, forwarded_to, status, issue_description)
                self.app.after(0, lambda data=result_data: self.results_tree.insert("", "end", values=data))
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e: error_msg = f"A browser error occurred: {str(e).splitlines()[0]}"; self.app.log_message(self.log_display, error_msg, "error"); messagebox.showerror("Automation Error", error_msg)
        except Exception as e: self.app.log_message(self.log_display, f"An unexpected error occurred: {e}", "error"); messagebox.showerror("Critical Error", f"An unexpected error occurred: {e}")
        finally:
            self.app.after(0, self.set_ui_state, False); self.app.after(0, self.update_status, "Automation Finished", 1.0); self.app.after(0, self.app.set_status, "Automation Finished")
            if not self.app.stop_events[self.automation_key].is_set():
                self.app.after(100, lambda: messagebox.showinfo("Complete", "Social Audit Report generation has finished."))
            
            # Reset status after 5 seconds
            self.app.after(5000, lambda: self.app.set_status("Ready"))
            self.app.after(5000, lambda: self.update_status("Ready", 0.0))

    def export_report(self):
        if not self.results_tree.get_children():
            messagebox.showinfo("No Data", "There are no results to export.")
            return
            
        first_item = self.results_tree.get_children()[0]
        values = self.results_tree.item(first_item, 'values')
        district, block, panchayat = values[1], values[2], values[3]
        
        # --- NEW: Folder and Filename Logic ---
        financial_year = self.year_entry.get()
        current_year = datetime.now().strftime("%Y")
        current_date_str = datetime.now().strftime("%d-%b-%Y") # e.g., 30-Oct-2025
        safe_panchayat = re.sub(r'[\\/*?:"<>|]', '_', panchayat) 

        try:
            downloads_path = self.app.get_user_downloads_path()
            target_dir = os.path.join(downloads_path, f"Reports {current_year}", "Social Audit Report", financial_year)
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Folder Error", f"Could not create directory:\n{e}\nSaving to Downloads instead.")
            target_dir = self.app.get_user_downloads_path()
        # --- END NEW ---

        export_format = self.export_format_menu.get()
        headers = self.results_tree['columns']
        data = [self.results_tree.item(item, 'values') for item in self.results_tree.get_children()]
        
        title = f"Social Audit Status Report: {panchayat}, {block}, {district}"
        date_str = f"Date - {datetime.now().strftime('%d-%m-%Y')}"

        if "CSV" in export_format:
            default_filename = f"Social_Audit_Report_{safe_panchayat}-{current_date_str}.csv"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv", filetypes=[("CSV files", "*.csv")], 
                initialdir=target_dir, initialfile=default_filename, title="Save CSV Report")
            if not file_path: return
            self.export_treeview_to_csv(self.results_tree, file_path) # Pass full path to base method
            return
        
        elif "PNG" in export_format:
            default_filename = f"Social_Audit_Report_{safe_panchayat}-{current_date_str}.png"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png", filetypes=[("PNG Image", "*.png")], 
                initialdir=target_dir, initialfile=default_filename, title="Save PNG Report")
            if not file_path: return
            
            # Use the base class method to generate the PNG
            success = self.generate_report_image(data, headers, title, date_str, file_path)
            if success:
                messagebox.showinfo("Success", f"PNG report saved successfully to:\n{file_path}")

        elif "PDF" in export_format:
            default_filename = f"Social_Audit_Report_{safe_panchayat}-{current_date_str}.pdf"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF Document", "*.pdf")], 
                initialdir=target_dir, initialfile=default_filename, title="Save PDF Report")
            if not file_path: return

            # Column widths for PDF (9 columns)
            # ("SR#", "District", "Block", "Panchayat", "Issue Number", "Issue Type", "Forwarded To", "Status", "Issue Description")
            col_widths = [10, 25, 25, 25, 30, 35, 20, 20, 87] # Tuned manually
            total_width_ratio = sum(col_widths)
            effective_page_width = 297 - 20 # A4 Landscape width minus margins
            actual_col_widths = [(w / total_width_ratio) * effective_page_width for w in col_widths]
            
            success = self.generate_report_pdf(data, headers, actual_col_widths, title, date_str, file_path)
            if success:
                messagebox.showinfo("Success", f"PDF report saved successfully to:\n{file_path}")
        
    def generate_report_pdf(self, data, headers, col_widths, title, date_str, file_path):
        """
        Overrides base method to use Unicode font, add footer, adjust formatting, 
        and correctly handle row wrapping and page breaks.
        """
        
        class PDFWithFooter(FPDF):
            def footer(self):
                self.set_y(-15) 
                try:
                    self.set_font(font_name, '', 8) 
                except NameError: 
                    self.set_font('Helvetica', '', 8) 
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
                self.set_xy(self.l_margin, -15)
                self.cell(0, 10, 'Report Generated by NregaBot.com', 0, 0, 'L')

        try:
            pdf = PDFWithFooter(orientation="L", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            try:
                font_path_regular = resource_path("assets/fonts/NotoSansDevanagari-Regular.ttf")
                font_path_bold = resource_path("assets/fonts/NotoSansDevanagari-Bold.ttf")
                pdf.add_font("NotoSansDevanagari", "", font_path_regular, uni=True)
                pdf.add_font("NotoSansDevanagari", "B", font_path_bold, uni=True)
                font_name = "NotoSansDevanagari"
            except RuntimeError:
                font_name = "Helvetica" 

            # --- Title ---
            pdf.set_font(font_name, "B", 14) 
            pdf.cell(0, 10, title, 0, 1, "C")
            pdf.set_font(font_name, "", 10) 
            pdf.cell(0, 8, date_str, 0, 1, "R") 
            pdf.ln(4) 

            # --- Headers ---
            pdf.set_font(font_name, "B", 7) 
            pdf.set_fill_color(200, 220, 255)
            header_height = 8 
            
            if len(col_widths) != len(headers):
                self.app.log_message(self.log_display, "PDF Export Warning: Column width count mismatch.", "warning")
                col_widths = [(pdf.w - 2 * pdf.l_margin) / len(headers)] * len(headers)

            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], header_height, header, 1, 0, "C", fill=True) 
            pdf.ln()

            # --- Data Rows ---
            pdf.set_font(font_name, "", 6) 
            line_height = 4 # Define line height
            
            for row_data in data:
                if len(row_data) != len(headers):
                    continue

                # --- Calculate row height based on content wrapping ---
                max_lines = 1
                for i, cell_text in enumerate(row_data):
                    lines = pdf.multi_cell(col_widths[i], line_height, str(cell_text), border=0, align='L', split_only=True)
                    current_lines = len(lines) if lines else 1 
                    if current_lines > max_lines: max_lines = current_lines
                
                row_height = line_height * max_lines
                
                # --- Check for page break BEFORE drawing the row ---
                if pdf.get_y() + row_height > pdf.page_break_trigger:
                    pdf.add_page()
                    # Redraw headers on new page
                    pdf.set_font(font_name, "B", 7)
                    for i, header in enumerate(headers):
                         pdf.cell(col_widths[i], header_height, header, 1, 0, "C", fill=True)
                    pdf.ln()
                    pdf.set_font(font_name, "", 6) # Reset data font

                # --- Draw the row using multi_cell for wrapping ---
                y_start = pdf.get_y()
                x_start = pdf.l_margin 
                
                for i, cell_text in enumerate(row_data):
                    col_width = col_widths[i]
                    x_current = x_start + sum(col_widths[:i]) 
                    pdf.set_xy(x_current, y_start) 
                    pdf.multi_cell(col_width, line_height, str(cell_text), border=1, align='L', max_line_height=line_height) 
                
                pdf.set_y(y_start + row_height) 

            pdf.output(file_path)
            return True
        except Exception as e:
            messagebox.showerror("PDF Export Error", f"Could not generate PDF report.\nError: {e}", parent=self)
            return False