# tabs/base_tab.py
import csv
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, sys, platform, re
import calendar
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont 
from fpdf import FPDF  # <--- Make sure this is imported

# Import Selenium Exceptions for Error Handling
from selenium.common.exceptions import NoSuchWindowException, WebDriverException

from utils import resource_path

# --- REUSABLE DATE PICKER CLASS ---
class DatePickerPopup(ctk.CTkToplevel):
    """
    A reusable modal popup for selecting a date.
    Features:
    - Centered on the main application window.
    - Highlights Today (Blue), Mondays (Greenish), and Sundays (Reddish).
    """
    def __init__(self, parent, on_date_select):
        super().__init__(parent)
        self.on_date_select = on_date_select
        self.title("Select Date")
        
        # Dimensions
        width, height = 300, 360
        
        # Calculate Center Position relative to Parent
        try:
            parent.update_idletasks()
            x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
            y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
        except:
            # Fallback if parent coords aren't ready
            x, y = 100, 100
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.transient(parent) # Keeps it on top of the parent window
        
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
        
        # --- Header Section (Month/Year & Navigation) ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkButton(self.header_frame, text="<", width=30, command=self.prev_month, 
                      fg_color="transparent", border_width=1, text_color=("black", "white")).pack(side="left")
        
        self.lbl_month_year = ctk.CTkLabel(self.header_frame, text="", font=("Arial", 16, "bold"))
        self.lbl_month_year.pack(side="left", expand=True)
        
        ctk.CTkButton(self.header_frame, text=">", width=30, command=self.next_month, 
                      fg_color="transparent", border_width=1, text_color=("black", "white")).pack(side="right")
        
        # --- Calendar Grid Section ---
        self.cal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cal_frame.pack(expand=True, fill="both", padx=10, pady=5)
        
        self.draw_calendar()
        self.focus_force() 

    def draw_calendar(self):
        """Renders the grid of days for the current month."""
        for widget in self.cal_frame.winfo_children():
            widget.destroy()
            
        # Update Header
        month_name = calendar.month_name[self.current_month]
        self.lbl_month_year.configure(text=f"{month_name} {self.current_year}")
        
        # Weekday Headers
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            t_color = "red" if i == 6 else ("gray30", "gray70")
            ctk.CTkLabel(self.cal_frame, text=day, font=("Arial", 12, "bold"), text_color=t_color).grid(row=0, column=i, padx=2, pady=5)
            
        # Days Grid
        cal = calendar.monthcalendar(self.current_year, self.current_month)
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day != 0:
                    # Color Logic
                    btn_fg_color = "transparent"
                    hover_color = ("gray80", "gray30")
                    text_color = ("black", "white")

                    if c == 0: # Monday (Greenish)
                        btn_fg_color = ("#E8F5E9", "#1B5E20") 
                    elif c == 6: # Sunday (Reddish)
                        btn_fg_color = ("#FFEBEE", "#8B0000")
                        text_color = ("#C62828", "#FFCCCC")

                    # Highlight Today (Blue)
                    now = datetime.now()
                    if day == now.day and self.current_month == now.month and self.current_year == now.year:
                        btn_fg_color = ("#2196F3", "#1976D2")
                        text_color = "white"
                        hover_color = ("#1E88E5", "#1565C0")

                    btn = ctk.CTkButton(
                        self.cal_frame, text=str(day), width=35, height=35,
                        fg_color=btn_fg_color, 
                        hover_color=hover_color,
                        text_color=text_color,
                        command=lambda d=day: self.select_date(d)
                    )
                    btn.grid(row=r+1, column=c, padx=2, pady=2)

    def prev_month(self):
        self.current_month -= 1
        if self.current_month == 0:
            self.current_month = 12
            self.current_year -= 1
        self.draw_calendar()

    def next_month(self):
        self.current_month += 1
        if self.current_month == 13:
            self.current_month = 1
            self.current_year += 1
        self.draw_calendar()

    def select_date(self, day):
        # Return date in DD/MM/YYYY format
        selected_date = f"{day:02d}/{self.current_month:02d}/{self.current_year}"
        self.on_date_select(selected_date)
        self.destroy()

# --- CUSTOM PDF CLASS FOR PROFESSIONAL HEADER/FOOTER ---
class ProfessionalPDF(FPDF):
    def __init__(self, title_text, date_text, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = title_text
        self.report_date = date_text

    def header(self):
        # Logo (if exists)
        try:
            logo_path = resource_path("assets/logo.png")
            if os.path.exists(logo_path):
                self.image(logo_path, 10, 8, 12)
                self.set_x(25) # Move text cursor after logo
        except: pass

        # Title
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, self.report_title, 0, 1, 'L')
        
        # Date & Subtitle
        self.set_font('Arial', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f"Generated on: {self.report_date}", 0, 1, 'L')
        
        # Line break and horizontal rule
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 287, self.get_y()) # A4 Landscape width is ~297mm
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} - Generated by NregaBot.com', 0, 0, 'C')

class BaseAutomationTab(ctk.CTkFrame):
    def __init__(self, parent, app_instance, automation_key):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.automation_key = automation_key
        
    # --- ADD THIS HELPER METHOD ---
    def open_date_picker(self, callback):
        """
        Opens the reusable DatePickerPopup.
        :param callback: A function that accepts a string (the selected date).
        """
        DatePickerPopup(self, callback)

    # --- ADD THIS ERROR HANDLER ---
    def handle_error(self, e):
        """
        Centralized error handler.
        Detects manual browser closure and shows user-friendly messages.
        """
        error_msg = str(e).lower()
        
        if "no such window" in error_msg or "target window already closed" in error_msg or "web view not found" in error_msg:
            self.app.log_message(self.log_display, "Automation Stopped: Browser tab/window was closed.", "error")
            messagebox.showwarning("Browser Closed", "Automation stopped because the browser window was closed.")
        
        elif "invalid session id" in error_msg:
            self.app.log_message(self.log_display, "Error: Browser session lost.", "error")
            messagebox.showwarning("Connection Lost", "Browser session was lost. Please restart the browser.")
            
        else:
            self.app.log_message(self.log_display, f"Error: {e}", "error")
            messagebox.showerror("Automation Error", f"An error occurred:\n\n{e}")

    def _get_wkhtml_path(self):
        """Gets the correct path to the wkhtmltoimage executable based on the OS."""
        os_type = platform.system()
    
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
            if os_type == "Windows":
                return os.path.join(base_path, 'wkhtmltoimage.exe')
            elif os_type == "Darwin":
                return os.path.join(base_path, 'wkhtmltoimage')
        else:
            base_path = os.path.abspath(".")
            if os_type == "Windows":
                return os.path.join(base_path, 'bin', 'win', 'wkhtmltoimage.exe')
            elif os_type == "Darwin":
                return os.path.join(base_path, 'bin', 'mac', 'wkhtmltoimage')
                
        return 'wkhtmltoimage'
        
    def generate_report_image(self, data, headers, title, date_str, output_path):
        """
        Generates a professional-looking report as a PNG image.
        """
        try:
            try:
                font_path_regular = resource_path("assets/fonts/NotoSansDevanagari-Regular.ttf")
                font_path_bold = resource_path("assets/fonts/NotoSansDevanagari-Bold.ttf")
                font_title = ImageFont.truetype(font_path_bold, 28)
                font_date = ImageFont.truetype(font_path_regular, 18)
                font_header = ImageFont.truetype(font_path_bold, 16)
                font_body = ImageFont.truetype(font_path_regular, 14)
            except IOError:
                print("Warning: NotoSansDevanagari fonts not found. Using default PIL fonts.")
                font_title = ImageFont.load_default()
                font_date = ImageFont.load_default()
                font_header = ImageFont.load_default()
                font_body = ImageFont.load_default()

            img_width = 2400
            margin_x = 80
            margin_y = 60
            
            header_bg_color = (220, 235, 255)
            row_even_bg_color = (255, 255, 255)
            row_odd_bg_color = (245, 245, 245)
            text_color = (0, 0, 0)
            border_color = (180, 180, 180)

            num_cols = len(headers)
            col_widths_pixels = []
            if num_cols > 0:
                available_width = img_width - (2 * margin_x)
                default_width = available_width / num_cols
                col_widths_pixels = [default_width] * num_cols
                
                sno_index = -1
                if any(str(h).lower() in ["s no.", "sno.", "s.no"] for h in headers):
                    sno_index = next((i for i, h in enumerate(headers) if str(h).lower() in ["s no.", "sno.", "s.no"]), -1)
                    if sno_index != -1:
                        col_widths_pixels[sno_index] = max(80, default_width * 0.4)
                        
                non_sno_width = sum(col_widths_pixels[i] for i in range(num_cols) if i != sno_index)
                remaining_width = available_width - (col_widths_pixels[sno_index] if sno_index != -1 else 0)
                original_non_sno_total = sum(default_width for i in range(num_cols) if i != sno_index)
                
                if original_non_sno_total > 0:
                    scale_factor = remaining_width / original_non_sno_total
                    for i in range(num_cols):
                        if i != sno_index:
                            col_widths_pixels[i] *= scale_factor
            
            for i, header in enumerate(headers):
                header_width = font_header.getlength(str(header)) + 40
                if col_widths_pixels[i] < header_width:
                    col_widths_pixels[i] = header_width

            current_total_width = sum(col_widths_pixels)
            if current_total_width == 0: return False
                
            scale_factor = (img_width - 2 * margin_x) / current_total_width
            col_widths_pixels = [w * scale_factor for w in col_widths_pixels]

            initial_height = 1600
            img = Image.new("RGB", (img_width, initial_height), (255, 255, 255))
            draw = ImageDraw.Draw(img)

            current_y = margin_y
            
            title_bbox = font_title.getbbox(title)
            title_height = title_bbox[3] - title_bbox[1]
            title_text_width = font_title.getlength(title)
            title_x = (img_width - title_text_width) / 2
            draw.text((title_x, current_y), title, font=font_title, fill=text_color)
            current_y += title_height + 5

            date_bbox = font_date.getbbox(date_str)
            date_height = date_bbox[3] - date_bbox[1]
            date_text_width = font_date.getlength(date_str)
            date_x = img_width - margin_x - date_text_width
            draw.text((date_x, current_y), date_str, font=font_date, fill=text_color)
            current_y += date_height + 20

            header_y_start = current_y
            header_height = 0
            for i, header in enumerate(headers):
                wrapped_header = self._wrap_text(str(header), font_header, col_widths_pixels[i] - 10)
                line_height = (font_header.getbbox("Tg")[3] - font_header.getbbox("Tg")[1]) * 1.2
                header_height = max(header_height, len(wrapped_header) * line_height + 10)
            
            current_x = margin_x
            for i, header in enumerate(headers):
                draw.rectangle([current_x, header_y_start, current_x + col_widths_pixels[i], header_y_start + header_height], fill=header_bg_color, outline=border_color, width=1)
                
                wrapped_header = self._wrap_text(str(header), font_header, col_widths_pixels[i] - 20)
                line_height = (font_header.getbbox("Tg")[3] - font_header.getbbox("Tg")[1]) * 1.2
                total_text_height = len(wrapped_header) * line_height
                text_y = header_y_start + (header_height - total_text_height) / 2
                
                for line in wrapped_header:
                    line_width = font_header.getlength(line)
                    draw.text((current_x + (col_widths_pixels[i] - line_width) / 2, text_y), line, font=font_header, fill=text_color)
                    text_y += line_height
                current_x += col_widths_pixels[i]
            current_y += header_height

            line_height = (font_body.getbbox("Tg")[3] - font_body.getbbox("Tg")[1]) * 1.2
            for row_idx, row_data in enumerate(data):
                row_bg_color = row_even_bg_color if row_idx % 2 == 0 else row_odd_bg_color

                max_row_text_height = 0
                temp_wrapped_cells = []
                for i, cell_text in enumerate(row_data):
                    wrapped_lines = self._wrap_text(str(cell_text), font_body, col_widths_pixels[i] - 20)
                    temp_wrapped_cells.append(wrapped_lines)
                    max_row_text_height = max(max_row_text_height, len(wrapped_lines) * line_height)

                row_data_height = max_row_text_height + 10

                if current_y + row_data_height + margin_y > img.height:
                    new_height = int(img.height + (row_data_height + margin_y) * 20)
                    new_img = Image.new("RGB", (img_width, new_height), (255, 255, 255))
                    new_img.paste(img, (0, 0))
                    img = new_img
                    draw = ImageDraw.Draw(img)

                current_x = margin_x
                for i, cell_text in enumerate(row_data):
                    draw.rectangle([current_x, current_y, current_x + col_widths_pixels[i], current_y + row_data_height], fill=row_bg_color, outline=border_color, width=1)
                    
                    wrapped_lines = temp_wrapped_cells[i]
                    text_y = current_y + 5
                    for line in wrapped_lines:
                        draw.text((current_x + 10, text_y), line, font=font_body, fill=text_color)
                        text_y += line_height
                    current_x += col_widths_pixels[i]
                current_y += row_data_height

            current_y += 15
            footer_text = "Report Generated by NregaBot.com"
            footer_font = font_body
            footer_bbox = footer_font.getbbox(footer_text)
            footer_height = footer_bbox[3] - footer_bbox[1]
            footer_y_pos = current_y + 10

            if footer_y_pos + footer_height + margin_y > img.height:
                new_height = int(footer_y_pos + footer_height + margin_y)
                new_img = Image.new("RGB", (img_width, new_height), (255, 255, 255))
                new_img.paste(img, (0, 0))
                img = new_img
                draw = ImageDraw.Draw(img)
            
            draw.text((margin_x, footer_y_pos), footer_text, font=footer_font, fill=text_color)
            current_y = footer_y_pos + footer_height
            final_img = img.crop((0, 0, img_width, current_y + margin_y))
            final_img.save(output_path, "PNG", dpi=(300, 300))
            return True
        except Exception as e:
            messagebox.showerror("PNG Export Error", f"Could not generate PNG report.\nError: {e}", parent=self.app)
            return False

    def _wrap_text(self, text, font, max_width):
        """Helper to wrap text for Pillow."""
        if not text: return [""]
        text_lines = text.split('\n')
        final_lines = []
        for text_line in text_lines:
            if not text_line.strip():
                final_lines.append(""); continue
            words = text_line.split(' ')
            lines = []; current_line = []
            for word in words:
                word_too_long = False
                while font.getlength(word) > max_width:
                    word_too_long = True
                    if current_line: lines.append(' '.join(current_line)); current_line = []
                    break_found = False
                    for i in range(len(word) - 1, 0, -1):
                        if font.getlength(word[:i]) <= max_width:
                            lines.append(word[:i]); word = word[i:]; break_found = True; break
                    if not break_found: lines.append(word); word = ""; break
                if not word: continue
                if not word_too_long and font.getlength(' '.join(current_line + [word])) <= max_width:
                    current_line.append(word)
                else:
                    if current_line: lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line: lines.append(' '.join(current_line))
            final_lines.extend(lines)
        return final_lines if final_lines else [""]

    # -------------------------------------------------------------------------
    # NEW PDF GENERATOR (Fixing Silent Failures)
    # -------------------------------------------------------------------------
    def generate_report_pdf(self, data, headers, col_widths, title, date_str, file_path):
        """
        Generates a professional A4 Landscape PDF.
        """
        try:
            # Create PDF in Landscape (L), mm units, A4 format
            pdf = ProfessionalPDF(title, date_str, orientation='L', unit='mm', format='A4')
            pdf.alias_nb_pages()
            pdf.add_page()
            
            # --- Table Settings ---
            line_height = 8
            font_size = 9
            pdf.set_font("Arial", size=font_size)
            
            # --- Header Row ---
            pdf.set_fill_color(44, 62, 80) # Dark Blue
            pdf.set_text_color(255, 255, 255) # White text
            pdf.set_font("Arial", 'B', 10)
            
            # Print Headers
            for i, h in enumerate(headers):
                width = col_widths[i] if i < len(col_widths) else 40
                pdf.cell(width, 10, str(h), 1, 0, 'C', True)
            pdf.ln()

            # --- Data Rows ---
            pdf.set_font("Arial", size=font_size)
            pdf.set_text_color(0, 0, 0) # Reset text to black
            
            fill = False # For zebra striping
            
            for row in data:
                # Calculate max height needed for this row
                # We need to know how many lines the text will wrap into
                max_lines = 1
                
                # Check each cell in the row
                for i, cell_data in enumerate(row):
                    text = str(cell_data).encode('latin-1', 'replace').decode('latin-1') # Sanitize Text
                    width = col_widths[i] if i < len(col_widths) else 40
                    
                    # Calculate lines using MultiCell simulation
                    # FPDF doesn't give a direct way to measure height of MultiCell easily without drawing,
                    # so we approximate by character count or assume FPDF handling.
                    # Better approach for FPDF 1.7+:
                    
                    # Split text roughly to estimate lines (simple approximation)
                    # Note: precise method requires using GetStringWidth. 
                    # Here we use a safe approximation for robust "non-silent" fail.
                    
                    if text:
                        text_width = pdf.get_string_width(text)
                        if text_width > width - 2: # -2 for padding
                            lines = int(text_width / (width - 2)) + 1
                            if lines > max_lines: max_lines = lines
                            
                row_height = max_lines * 5 # 5mm per line of text
                if row_height < 8: row_height = 8 # Minimum row height
                
                # Check Page Break
                if pdf.get_y() + row_height > 190: # 190mm is roughly safe limit for A4 Landscape
                    pdf.add_page()
                    # Re-print Header
                    pdf.set_fill_color(44, 62, 80)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Arial", 'B', 10)
                    for i, h in enumerate(headers):
                        width = col_widths[i] if i < len(col_widths) else 40
                        pdf.cell(width, 10, str(h), 1, 0, 'C', True)
                    pdf.ln()
                    pdf.set_font("Arial", size=font_size)
                    pdf.set_text_color(0, 0, 0)
                
                # Draw Cells
                pdf.set_fill_color(240, 240, 240) if fill else pdf.set_fill_color(255, 255, 255)
                
                current_x = pdf.get_x()
                current_y = pdf.get_y()
                
                for i, cell_data in enumerate(row):
                    width = col_widths[i] if i < len(col_widths) else 40
                    text = str(cell_data).encode('latin-1', 'replace').decode('latin-1') # Sanitize
                    
                    # Color coding for "Status" column
                    if i == 1: # Assuming Status is column 1
                        if "SUCCESS" in text.upper(): pdf.set_text_color(0, 100, 0)
                        elif "FAIL" in text.upper(): pdf.set_text_color(180, 0, 0)
                        else: pdf.set_text_color(0, 0, 0)
                    else:
                        pdf.set_text_color(0, 0, 0)

                    # Draw Cell
                    pdf.rect(current_x, current_y, width, row_height, 'DF' if fill else 'D')
                    pdf.multi_cell(width, 5, text, border=0, align='L') # 5 is line height inside cell
                    
                    # Move cursor to right for next cell
                    current_x += width
                    pdf.set_xy(current_x, current_y)
                    
                pdf.ln(row_height)
                fill = not fill # Toggle color

            pdf.output(file_path)
            return True
            
        except Exception as e:
            print(f"PDF Gen Error: {e}") # Print to console for debugging
            messagebox.showerror("PDF Export Error", f"Could not generate PDF.\nError: {e}", parent=self.app)
            return False

    # -------------------------------------------------------------------------
    # MODIFIED: _create_action_buttons (Centralized & Modern UI)
    # -------------------------------------------------------------------------
    def _create_action_buttons(self, parent_frame):
        """Creates Start, Stop, and Reset buttons."""
        outer_wrapper = ctk.CTkFrame(parent_frame, fg_color="transparent")
        inner_container = ctk.CTkFrame(outer_wrapper, fg_color="transparent")
        inner_container.pack(expand=True, anchor="center")
        
        self.start_button = ctk.CTkButton(inner_container, text="▶ Start", command=self.start_automation, width=110, height=32, corner_radius=8, fg_color="#2E8B57", hover_color="#1F5E39", font=ctk.CTkFont(size=13, weight="bold"))
        self.start_button.pack(side="left", padx=(0, 8))

        self.stop_button = ctk.CTkButton(inner_container, text="■ Stop", command=self.stop_automation, state="disabled", width=90, height=32, corner_radius=8, fg_color="#C53030", hover_color="#9B2C2C", font=ctk.CTkFont(size=13, weight="bold"))
        self.stop_button.pack(side="left", padx=(0, 8))
        
        self.reset_button = ctk.CTkButton(inner_container, text="↺ Reset", command=self.reset_ui, width=90, height=32, corner_radius=8, fg_color=("gray70", "#4A4A4A"), hover_color=("gray60", "#3A3A3A"), text_color="white", font=ctk.CTkFont(size=13))
        self.reset_button.pack(side="left")
        return outer_wrapper

    def _create_log_and_status_area(self, parent_notebook):
        log_frame = parent_notebook.add("Logs & Status")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_actions_frame = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_actions_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))

        def copy_logs_to_clipboard():
            logs = self.log_display.get("1.0", tkinter.END)
            if logs.strip():
                self.app.clipboard_clear(); self.app.clipboard_append(logs)
                messagebox.showinfo("Copied", "Logs copied to clipboard.", parent=self.app)
            else:
                messagebox.showwarning("Empty", "There are no logs to copy.", parent=self.app)

        copy_button = ctk.CTkButton(log_actions_frame, text="Copy Logs", width=100, command=copy_logs_to_clipboard)
        copy_button.pack(side="right")

        self.log_display = ctk.CTkTextbox(log_frame, state="disabled")
        self.log_display.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        status_bar_frame = ctk.CTkFrame(log_frame, height=30)
        status_bar_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

        self.status_label = ctk.CTkLabel(status_bar_frame, text="Status: Ready", anchor="w")
        self.status_label.pack(side="left", padx=10)
        
        self.progress_bar = ctk.CTkProgressBar(status_bar_frame, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.pack(side="right", padx=10, fill="x", expand=True)
    
    def set_common_ui_state(self, running: bool):
        self.start_button.configure(state="disabled" if running else "normal", text="Running..." if running else "▶ Start")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.reset_button.configure(state="disabled" if running else "normal")

    def reset_ui(self):
        """
        Default reset behavior. Subclasses should override this 
        to clear specific input fields.
        """
        self.update_status("Ready", 0)
        self.app.set_status("Ready")
        # Optional: Clear logs
        self.log_display.configure(state="normal")
        self.log_display.delete("1.0", tkinter.END)
        self.log_display.configure(state="disabled")

    def stop_automation(self):
        self.app.stop_events[self.automation_key].set()
        self.app.log_message(self.log_display, "Stop signal sent. Finishing current task...", "warning")

    def update_status(self, message, progress=None):
        self.status_label.configure(text=f"Status: {message}")
        if progress is not None:
            self.progress_bar.set(float(progress))

    def style_treeview(self, treeview_widget=None):
        # Agar argument nahi diya (main_app me), toh ye function global style set karega
        style = ttk.Style()
        style.theme_use("clam")

        # 1. Theme Detection
        mode = ctk.get_appearance_mode()

        if mode == "Dark":
            # --- DARK MODE COLORS ---
            bg_color = "#2b2b2b"        # Table Background
            text_color = "#e5e7eb"      # Text (Light Gray)
            row_hover = "#3f3f46"       # Row Hover Color (Thoda sa light dark)
            selected_bg = "#3B82F6"     # Selection (Blue)
            
            header_bg = "#1f2937"       # Header Background (Dark Slate)
            header_fg = "#ffffff"       # Header Text
            header_hover = "#374151"    # Header Hover
        else:
            # --- LIGHT MODE COLORS ---
            bg_color = "#ffffff"        # Table Background
            text_color = "#374151"      # Text (Dark Gray)
            row_hover = "#f3f4f6"       # Row Hover Color (Very Light Gray)
            selected_bg = "#3B82F6"     # Selection (Blue)
            
            header_bg = "#f9fafb"       # Header Background (Off-white)
            header_fg = "#111827"       # Header Text (Almost Black)
            header_hover = "#e5e7eb"    # Header Hover

        # 2. Configure Treeview Body
        style.configure("Treeview",
                        background=bg_color,
                        foreground=text_color,
                        fieldbackground=bg_color,
                        rowheight=35,             # Rows thodi spacious
                        font=("Segoe UI", 11),
                        borderwidth=0)

        # 3. Configure Rows (Hover & Selection)
        # Note: 'selected' pehle check hota hai, isliye hover selected row ka color kharab nahi karega
        style.map("Treeview",
                  background=[('selected', selected_bg), ('active', row_hover)],
                  foreground=[('selected', 'white'), ('active', text_color)])

        # 4. Configure Heading
        style.configure("Treeview.Heading",
                        background=header_bg,
                        foreground=header_fg,
                        relief="flat",
                        font=("Segoe UI", 12, "bold"))

        style.map("Treeview.Heading",
                  background=[('active', header_hover)])

        # 5. Fix for file_management_tab (jahan widget pass hota hai)
        if treeview_widget:
            treeview_widget.configure(style="Treeview")

    def _setup_treeview_sorting(self, tree):
        for col in tree["columns"]:
            tree.heading(col, text=col, command=lambda _col=col: self._treeview_sort_column(tree, _col, False))

    def _treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        try: l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError: l.sort(reverse=reverse)
        for index, (val, k) in enumerate(l): tv.move(k, '', index)
        tv.heading(col, command=lambda: self._treeview_sort_column(tv, col, not reverse))
        
    def export_treeview_to_csv(self, tree, default_filename):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialdir=self.app.get_user_downloads_path(), initialfile=default_filename, title="Save CSV Report")
        if not file_path: return
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(tree["columns"])
                for item_id in tree.get_children(): writer.writerow(tree.item(item_id)['values'])
            messagebox.showinfo("Success", f"Report successfully exported to\n{file_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while saving the CSV file:\n{e}", parent=self)

    def _extract_and_update_workcodes(self, textbox_widget):
        """
        Extracts work codes (6-digit) and wagelist IDs.
        Updated: Allows duplicates (does not filter unique values).
        """
        try:
            input_content = textbox_widget.get("1.0", tkinter.END)
            if not input_content.strip(): return

            work_code_pattern = re.compile(r'\b(34\d{8}(?:/\w+)+/\d+)\b')
            wagelist_pattern = re.compile(r'\b\d+WL\d+\b', re.IGNORECASE)

            found_work_codes = work_code_pattern.findall(input_content)
            found_wagelists = wagelist_pattern.findall(input_content)

            processed_work_codes = []
            for code in found_work_codes:
                last_part = code.split('/')[-1]
                if len(last_part) > 7:
                    processed_work_codes.append(last_part[-6:])
                else:
                    processed_work_codes.append(last_part)
            
            results = processed_work_codes + [wl.upper() for wl in found_wagelists]
            
            # --- CHANGE MADE HERE ---
            # Previously: final_results = list(dict.fromkeys(results)) (This removed duplicates)
            # Now: We keep 'results' as is to allow duplicates.
            final_results = results 
            # ------------------------

            if final_results:
                textbox_widget.configure(state="normal")
                textbox_widget.delete("1.0", tkinter.END)
                textbox_widget.insert("1.0", "\n".join(final_results))
                # Update message to reflect total items found, including duplicates
                messagebox.showinfo("Extraction Complete", f"Found and extracted {len(final_results)} items.", parent=self)
            else:
                messagebox.showinfo("No Codes Found", "Could not find any matching work codes or wagelist IDs in the text.", parent=self)
        
        except Exception as e:
            messagebox.showerror("Extraction Error", f"An error occurred during extraction: {e}", parent=self)

    def _apply_appearance_mode(self, theme_color_tuple):
        if isinstance(theme_color_tuple, (tuple, list)):
            if ctk.get_appearance_mode().lower() == "light": return theme_color_tuple[0]
            else: return theme_color_tuple[1]
        return theme_color_tuple