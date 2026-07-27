# tabs/base_tab.py
import csv
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, sys, platform, re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont 

from src import config
from src.utils import resource_path, get_logger

logger = get_logger()

# Module-level imports for selenium and openpyxl (P4: moved from lazy imports in method bodies)
from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException

# A2: Import extracted components from their own modules
from .date_picker_popup import DatePickerPopup
from .professional_pdf import ProfessionalPDF

class BaseAutomationTab(ctk.CTkFrame):
    def __init__(self, parent: Any, app_instance: Any, automation_key: str) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.automation_key = automation_key
        self.retry_btn = None # Placeholder for retry button
        self._tab_destroyed = False  # Flag: set True in destroy() to prevent UI updates on dead widgets
        
        # --- AfterTracker for safe callback cleanup on tab destroy ---
        from src.ui_components import AfterTracker
        self._safe_after = AfterTracker(self)
        
    def destroy(self) -> None:
        """
        Override destroy() to set a flag that prevents background threads
        from updating widgets on a destroyed tab.
        
        DO NOT call driver.quit() here — the automation thread may be using
        the same driver concurrently, causing a GIL fatal crash. The driver
        is cleaned up in start_automation_thread()'s wrapper() after the
        target() function returns.
        
        DO NOT set stop_event here — the new tab instance shares the same
        automation_key, which would replace the Event in stop_events[key],
        causing the old thread to read the new (unset) Event.
        """
        self._tab_destroyed = True
        super().destroy()
        
    def _is_alive(self) -> bool:
        """Returns True if the tab's widgets still exist and can be updated.
        
        Background threads call set_common_ui_state() / log_message() via
        self.app.after(0, ...). If the user navigated away before the callback
        fires, all widgets are destroyed and winfo_exists() returns False.
        This guard prevents TclError: invalid command name.
        """
        if self._tab_destroyed:
            return False
        try:
            return bool(self.winfo_exists())
        except Exception:
            return False
        
    def safe_after(self, ms: int, callback: Callable, *args: Any) -> str:
        """
        Tracked version of after() that auto-cancels when tab is destroyed.
        Prevents ghost callbacks from firing after tab is gone.
        Use this instead of self.after() for recurring callbacks.
        """
        return self._safe_after.after(ms, callback, *args)
        
    def open_date_picker(self, callback: Callable[[str], None]) -> None:
        """Opens the reusable DatePickerPopup."""
        DatePickerPopup(self, callback)

    def handle_error(self, e: Exception) -> None:
        """Centralized error handler."""
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

    def _get_wkhtml_path(self) -> str:
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
        
    def generate_report_image(self, data: List[List[str]], headers: List[str], title: str, date_str: str, output_path: str) -> bool:
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

    def _wrap_text(self, text: str, font: Any, max_width: float) -> List[str]:
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

    def generate_report_pdf(self, data: List[List[str]], headers: List[str], col_widths: List[float], title: str, date_str: str, file_path: str) -> bool:
        try:
            pdf = ProfessionalPDF(title, date_str, orientation='L', unit='mm', format='A4')
            pdf.alias_nb_pages()
            pdf.add_page()
            
            line_height = 8
            font_size = 9
            pdf.set_font("Arial", size=font_size)
            
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", 'B', 10)
            
            for i, h in enumerate(headers):
                width = col_widths[i] if i < len(col_widths) else 40
                pdf.cell(width, 10, str(h), 1, 0, 'C', True)
            pdf.ln()

            pdf.set_font("Arial", size=font_size)
            pdf.set_text_color(0, 0, 0)
            
            fill = False
            
            for row in data:
                max_lines = 1
                for i, cell_data in enumerate(row):
                    text = str(cell_data).encode('latin-1', 'replace').decode('latin-1')
                    width = col_widths[i] if i < len(col_widths) else 40
                    if text:
                        text_width = pdf.get_string_width(text)
                        if text_width > width - 2:
                            lines = int(text_width / (width - 2)) + 1
                            if lines > max_lines: max_lines = lines
                            
                row_height = max_lines * 5
                if row_height < 8: row_height = 8
                
                if pdf.get_y() + row_height > 190:
                    pdf.add_page()
                    pdf.set_fill_color(44, 62, 80)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Arial", 'B', 10)
                    for i, h in enumerate(headers):
                        width = col_widths[i] if i < len(col_widths) else 40
                        pdf.cell(width, 10, str(h), 1, 0, 'C', True)
                    pdf.ln()
                    pdf.set_font("Arial", size=font_size)
                    pdf.set_text_color(0, 0, 0)
                
                pdf.set_fill_color(240, 240, 240) if fill else pdf.set_fill_color(255, 255, 255)
                
                current_x = pdf.get_x()
                current_y = pdf.get_y()
                
                for i, cell_data in enumerate(row):
                    width = col_widths[i] if i < len(col_widths) else 40
                    text = str(cell_data).encode('latin-1', 'replace').decode('latin-1')
                    
                    if i == 1:
                        if "SUCCESS" in text.upper(): pdf.set_text_color(0, 100, 0)
                        elif "FAIL" in text.upper(): pdf.set_text_color(180, 0, 0)
                        else: pdf.set_text_color(0, 0, 0)
                    else:
                        pdf.set_text_color(0, 0, 0)

                    pdf.rect(current_x, current_y, width, row_height, 'DF' if fill else 'D')
                    pdf.multi_cell(width, 5, text, border=0, align='L')
                    
                    current_x += width
                    pdf.set_xy(current_x, current_y)
                    
                pdf.ln(row_height)
                fill = not fill

            pdf.output(file_path)
            return True
            
        except Exception as e:
            print(f"PDF Gen Error: {e}")
            messagebox.showerror("PDF Export Error", f"Could not generate PDF.\nError: {e}", parent=self.app)
            return False

    def _create_action_buttons(self, parent_frame: Any) -> ctk.CTkFrame:
        """Creates Start, Stop, Reset AND Retry buttons."""
        outer_wrapper = ctk.CTkFrame(parent_frame, fg_color="transparent")
        inner_container = ctk.CTkFrame(outer_wrapper, fg_color="transparent")
        inner_container.pack(expand=True, anchor="center")
        
        self.start_button = ctk.CTkButton(inner_container, text="▶ Start", command=self.start_automation, width=110, height=32, corner_radius=8, fg_color=config.COLORS["btn_start"], hover_color=config.COLORS["btn_start_hover"], font=ctk.CTkFont(size=13, weight="bold"))
        self.start_button.pack(side="left", padx=(0, 8))

        self.stop_button = ctk.CTkButton(inner_container, text="■ Stop", command=self.stop_automation, state="disabled", width=90, height=32, corner_radius=8, fg_color=config.COLORS["btn_stop"], hover_color=config.COLORS["btn_stop_hover"], font=ctk.CTkFont(size=13, weight="bold"))
        self.stop_button.pack(side="left", padx=(0, 8))
        
        # --- NEW RETRY BUTTON ---
        self.retry_btn = ctk.CTkButton(inner_container, text="↻ Retry Failed", command=self.retry_logic_handler, width=110, height=32, corner_radius=8, fg_color=config.COLORS["orange"], hover_color=config.COLORS["orange_hover"], font=ctk.CTkFont(size=13, weight="bold"))
        self.retry_btn.pack(side="left", padx=(0, 8))
        self.retry_btn.configure(state="disabled") # Initially disabled

        self.reset_button = ctk.CTkButton(inner_container, text="↺ Reset", command=self.reset_ui, width=90, height=32, corner_radius=8, fg_color=(config.COLORS["gray70"], config.COLORS["gray40_"]), hover_color=(config.COLORS["gray60"], config.COLORS["gray35_"]), text_color="white", font=ctk.CTkFont(size=13))
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
    
    def set_common_ui_state(self, running: bool) -> None:
        """Updates Start/Stop/Reset/Retry buttons based on running state.
        
        Safe to call after tab has been destroyed — checks _is_alive()
        and wraps each configure() in try/except to prevent TclError.
        """
        if not self._is_alive():
            return
        try:
            self.start_button.configure(state="disabled" if running else "normal", text="Running..." if running else "▶ Start")
        except Exception:
            pass
        try:
            self.stop_button.configure(state="normal" if running else "disabled")
        except Exception:
            pass
        try:
            self.reset_button.configure(state="disabled" if running else "normal")
        except Exception:
            pass
        if self.retry_btn:
            try:
                self.retry_btn.configure(state="disabled" if running else "normal")
            except Exception:
                pass

    def reset_ui(self) -> None:
        self.update_status("Ready", 0)
        self.app.set_status("Ready")
        self.log_display.configure(state="normal")
        self.log_display.delete("1.0", tkinter.END)
        self.log_display.configure(state="disabled")

    def stop_automation(self) -> None:
        self.app.stop_events[self.automation_key].set()
        self.app.log_message(self.log_display, "Stop signal sent. Finishing current task...", "warning")

    def update_status(self, message: str, progress: Optional[float] = None) -> None:
        """Update status label and progress bar.
        
        Safe to call after tab has been destroyed — checks _is_alive()
        and wraps configure() in try/except.
        """
        if not self._is_alive():
            return
        try:
            self.status_label.configure(text=f"Status: {message}")
        except Exception:
            pass
        if progress is not None:
            try:
                self.progress_bar.set(float(progress))
            except Exception:
                pass
        # --- FIXED: Update Global App Status ---
        if hasattr(self.app, 'set_status'):
            self.app.set_status(message)

    def retry_logic_handler(self) -> None:
        """Override this in child tabs if specific logic is needed, otherwise uses default."""
        # Child tab should define 'self.input_text_widget' (the textbox with codes/jobcards)
        if hasattr(self, 'work_codes_text'):
            self.retry_failed_automation(self.work_codes_text)
        elif hasattr(self, 'jobcards_text'): # For Demand Tab support
            self.retry_failed_automation(self.jobcards_text)
        else:
            messagebox.showinfo("Info", "Retry logic not configured for this tab.")

    def retry_failed_automation(self, input_widget: Any) -> None:
        """
        Generic Logic:
        1. Reads 'Failed' items from Treeview.
        2. Updates the input box with ONLY failed items.
        3. Clears the Treeview.
        4. Auto-starts automation.
        """
        failed_items = []
        all_items = self.results_tree.get_children()
        
        if not all_items:
            messagebox.showinfo("Retry", "No results found to retry.")
            return

        for item_id in all_items:
            values = self.results_tree.item(item_id)['values']
            # Assuming Column 0 is ID (Workcode/Jobcard) and Column 1 is Status
            code = str(values[0])
            status = str(values[1]).lower()
            
            if "success" not in status:
                failed_items.append(code)
        
        if not failed_items:
            messagebox.showinfo("Great!", "No failed items found.")
            return

        # Confirm before action
        if not messagebox.askyesno("Retry Failed", f"Found {len(failed_items)} failed items.\nDo you want to retry them now?"):
            return

        # 1. Update Input Widget
        input_widget.configure(state="normal")
        input_widget.delete("1.0", tkinter.END)
        input_widget.insert("1.0", "\n".join(failed_items))
        input_widget.configure(state="disabled")

        # 2. Clear Previous Results (Optional, but cleaner for retry run)
        for item in all_items:
            self.results_tree.delete(item)

        # 3. Auto Start
        self.app.log_message(self.log_display, f"Retrying {len(failed_items)} failed items...", "info")
        self.start_automation()

    def _get_style(self) -> ttk.Style:
        """Return a cached ttk.Style singleton to avoid recreation overhead."""
        if not hasattr(self.app, '_cached_style') or self.app._cached_style is None:
            style = ttk.Style()
            style.theme_use("clam")
            self.app._cached_style = style
        return self.app._cached_style

    def style_treeview(self, treeview_widget: Optional[Any] = None) -> None:
        style = self._get_style()

        mode = ctk.get_appearance_mode()

        if mode == "Dark":
            # --- DARK MODE COLORS ---
            bg_color = "#333333"
            text_color = "#e5e7eb"
            row_hover = "#404040"
            selected_bg = "#3B82F6"
            
            header_bg = "#1f2937"       
            header_fg = "#ffffff"       
            header_hover = "#374151"
            
            # Tags Colors (Dark Mode)
            fail_bg = "#5c1e1e"   # Dark Red
            fail_fg = "#ffffff"
            skip_bg = "#5c4e1e"   # Dark Yellow/Brown
            skip_fg = "#ffffff"
            success_bg = "#14532d" # Dark Green
            success_fg = "#ffffff"
            
        else:
            # --- LIGHT MODE COLORS ---
            bg_color = "#ffffff"        
            text_color = "#111827"
            row_hover = "#f3f4f6"       
            selected_bg = "#3B82F6"     
            
            header_bg = "#f9fafb"       
            header_fg = "#111827"       
            header_hover = "#e5e7eb"
            
            # Tags Colors (Light Mode)
            fail_bg = "#fee2e2"   # Light Red
            fail_fg = "#991b1b"
            skip_bg = "#fef9c3"   # Light Yellow
            skip_fg = "#854d0e"
            success_bg = "#dcfce7" # Light Green
            success_fg = "#166534" # Dark Green Text

        # Configure Treeview
        style.configure("Treeview",
                        background=bg_color,
                        foreground=text_color,
                        fieldbackground=bg_color,
                        rowheight=35,             
                        font=("Segoe UI", 11),
                        borderwidth=0)

        style.map("Treeview",
                  background=[('selected', selected_bg), ('active', row_hover)],
                  foreground=[('selected', 'white'), ('active', text_color)])

        style.configure("Treeview.Heading",
                        background=header_bg,
                        foreground=header_fg,
                        relief="flat",
                        font=("Segoe UI", 12, "bold"))

        style.map("Treeview.Heading",
                  background=[('active', header_hover)])

        # Apply Tags
        if treeview_widget:
            treeview_widget.configure(style="Treeview")
            treeview_widget.tag_configure('failed', background=fail_bg, foreground=fail_fg)
            treeview_widget.tag_configure('skipped', background=skip_bg, foreground=skip_fg)
            treeview_widget.tag_configure('success', background=success_bg, foreground=success_fg)
            treeview_widget.tag_configure('warning', background=skip_bg, foreground=skip_fg)

    def _setup_treeview_sorting(self, tree: Any) -> None:
        for col in tree["columns"]:
            tree.heading(col, text=col, command=lambda _col=col: self._treeview_sort_column(tree, _col, False))

    def _treeview_sort_column(self, tv: Any, col: str, reverse: bool) -> None:
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        try: l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError: l.sort(reverse=reverse)
        for index, (val, k) in enumerate(l): tv.move(k, '', index)
        tv.heading(col, command=lambda: self._treeview_sort_column(tv, col, not reverse))
        
    def export_treeview_to_csv(self, tree: Any, default_filename: str) -> None:
        """Export treeview contents to CSV inside ~/Downloads/NregaBot/Reports/."""
        reports_dir = self.app.get_nregabot_path("Reports")
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialdir=reports_dir, initialfile=default_filename, title="Save CSV Report")
        if not file_path: return
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(tree["columns"])
                for item_id in tree.get_children(): writer.writerow(tree.item(item_id)['values'])
            messagebox.showinfo("Success", f"Report successfully exported to\n{file_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while saving the CSV file:\n{e}", parent=self)

    def _extract_and_update_workcodes(self, textbox_widget: Any) -> None:
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
            final_results = results 

            if final_results:
                textbox_widget.configure(state="normal")
                textbox_widget.delete("1.0", tkinter.END)
                textbox_widget.insert("1.0", "\n".join(final_results))
                messagebox.showinfo("Extraction Complete", f"Found and extracted {len(final_results)} items.", parent=self)
            else:
                messagebox.showinfo("No Codes Found", "Could not find any matching work codes or wagelist IDs in the text.", parent=self)
        
        except Exception as e:
            messagebox.showerror("Extraction Error", f"An error occurred during extraction: {e}", parent=self)

    # ────────────────────────────────────────────────────────────────
    # CASE-INSENSITIVE DROPDOWN SELECTION HELPER
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _select_by_text_case_insensitive(select_element: Any, target_text: str) -> bool:
        """
        Case-insensitive version of Selenium's select_by_visible_text().
        
        Website par panchayat kabhi "PALOJORI" (UPPERCASE), kabhi "Palojori" (Title Case)
        dikhta hai. User ne jaisa bhi save kiya ho, automation kaam karna chahiye.
        
        Args:
            select_element: A selenium.webdriver.support.ui.Select instance
            target_text: The text to match (case-insensitive)
            
        Returns:
            True if a match was found and selected, False otherwise
        """
        target_lower = target_text.strip().lower()
        for option in select_element.options:
            if option.text.strip().lower() == target_lower:
                select_element.select_by_visible_text(option.text)
                return True
        return False
    
    # ────────────────────────────────────────────────────────────────
    # LOCATION HIERARCHY HELPERS
    # ────────────────────────────────────────────────────────────────

    # Mapping: location_key → (parent_key, [child_keys_to_clear])
    _HIERARCHY_CLEAR = {
        "location_state":    (None, ["location_district", "location_block", "location_panchayat"]),
        "location_district": ("location_state", ["location_block", "location_panchayat"]),
        "location_block":    ("location_district", ["location_panchayat"]),
        "location_panchayat":("location_block", []),
        "location_village":  ("location_panchayat", []),
    }

    def _make_filter_func(self, child_key: str, parent_key: str, parent_entry: Any):
        """
        Create a filter function for a child dropdown that filters by parent value.
        Usage: filter_func=self._make_filter_func("location_district", "location_state", self.state_entry)
        """
        def _filter():
            parent_val = parent_entry.get().strip() if parent_entry else ""
            return self.app.history_manager.get_filtered_suggestions(
                child_key, parent_key, parent_val
            )
        return _filter

    def _make_parent_callback(self, my_key: str, child_entries: list):
        """
        Create a command callback for when a location value is selected.
        Clears child entries when parent changes so old child values don't
        appear orphaned.
        
        child_entries: list of (entry_widget, child_key) tuples to clear
        
        Note: Hierarchy relationships (parent→child) are built via the
        Settings tab — automation tabs are consumers only.
        """
        def _on_parent_selected(value):
            # Clear all dependent child entries
            for entry, _ in child_entries:
                try:
                    entry.delete(0, 'end')
                except Exception:
                    pass
        return _on_parent_selected

    def _apply_appearance_mode(self, theme_color_tuple: Any) -> str:
        if isinstance(theme_color_tuple, (tuple, list)):
            if ctk.get_appearance_mode().lower() == "light": return theme_color_tuple[0]
            else: return theme_color_tuple[1]
        return theme_color_tuple