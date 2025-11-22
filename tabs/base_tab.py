# tabs/base_tab.py
import csv
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, sys, platform, re
from PIL import Image, ImageDraw, ImageFont 

from utils import resource_path

class BaseAutomationTab(ctk.CTkFrame):
    def __init__(self, parent, app_instance, automation_key):
        super().__init__(parent, fg_color="transparent")
        self.app = app_instance
        self.automation_key = automation_key

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

    def generate_report_pdf(self, data, headers, col_widths, title, date_str, file_path):
        # Implementation assumed from previous context
        return False

    # -------------------------------------------------------------------------
    # MODIFIED: _create_action_buttons (Centralized & Modern UI)
    # -------------------------------------------------------------------------
    def _create_action_buttons(self, parent_frame):
        """
        Creates Start, Stop, and Reset buttons.
        USES A WRAPPER FRAME TO FORCE CENTERING IN ALL TABS.
        """
        # 1. Outer Wrapper (The frame that child tabs will pack/grid)
        # This frame will take whatever space the child tab gives it (e.g. fill='x')
        outer_wrapper = ctk.CTkFrame(parent_frame, fg_color="transparent")
        
        # 2. Inner Container (Holds the actual buttons)
        # We pack this centered inside the outer wrapper.
        inner_container = ctk.CTkFrame(outer_wrapper, fg_color="transparent")
        inner_container.pack(expand=True, anchor="center")
        
        # 3. Add Buttons to the Inner Container
        
        # ▶ Start Button (Green, Compact)
        self.start_button = ctk.CTkButton(
            inner_container, 
            text="▶ Start", 
            command=self.start_automation, 
            width=110, 
            height=32,
            corner_radius=8,
            fg_color="#2E8B57",  # Sea Green
            hover_color="#1F5E39",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.start_button.pack(side="left", padx=(0, 8))

        # ■ Stop Button (Red, Compact)
        self.stop_button = ctk.CTkButton(
            inner_container, 
            text="■ Stop", 
            command=self.stop_automation, 
            state="disabled", 
            width=90,
            height=32,
            corner_radius=8,
            fg_color="#C53030", # Material Red
            hover_color="#9B2C2C",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.stop_button.pack(side="left", padx=(0, 8))
        
        # ↺ Reset Button (Gray, Compact)
        self.reset_button = ctk.CTkButton(
            inner_container, 
            text="↺ Reset", 
            command=self.reset_ui, 
            width=90,
            height=32,
            corner_radius=8,
            fg_color=("gray70", "#4A4A4A"), 
            hover_color=("gray60", "#3A3A3A"),
            text_color="white",
            font=ctk.CTkFont(size=13)
        )
        self.reset_button.pack(side="left")

        # 4. Return the Outer Wrapper
        # Now, no matter how the child tab packs this (fill='x', sticky='ew'),
        # the inner container will always remain floating in the center.
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
        # Update text for running state
        self.start_button.configure(
            state="disabled" if running else "normal",
            text="Running..." if running else "▶ Start"
        )
        self.stop_button.configure(state="normal" if running else "disabled")
        self.reset_button.configure(state="disabled" if running else "normal")

    def start_automation(self):
        raise NotImplementedError

    def stop_automation(self):
        self.app.stop_events[self.automation_key].set()
        self.app.log_message(self.log_display, "Stop signal sent. Finishing current task...", "warning")

    def reset_ui(self):
        raise NotImplementedError
        
    def update_status(self, message, progress=None):
        self.status_label.configure(text=f"Status: {message}")
        if progress is not None:
            self.progress_bar.set(float(progress))

    def style_treeview(self, tree):
        style = ttk.Style()
        bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        text_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        heading_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
        
        style.theme_use("default")
        style.configure("Treeview", background=bg_color, foreground=text_color, fieldbackground=bg_color, borderwidth=0)
        style.map('Treeview', background=[('selected', ctk.ThemeManager.theme["CTkButton"]["fg_color"])])
        style.configure("Treeview.Heading", background=heading_bg, foreground=text_color, relief="flat", font=('Calibri', 10,'bold'))
        style.map("Treeview.Heading", background=[('active', ctk.ThemeManager.theme["CTkButton"]["hover_color"])])

        tree.tag_configure('failed', foreground='red')

    def _setup_treeview_sorting(self, tree):
        for col in tree["columns"]:
            tree.heading(col, text=col, command=lambda _col=col: self._treeview_sort_column(tree, _col, False))

    def _treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        try:
            l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)
        tv.heading(col, command=lambda: self._treeview_sort_column(tv, col, not reverse))
        
    def export_treeview_to_csv(self, tree, default_filename):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialdir=self.app.get_user_downloads_path(),
            initialfile=default_filename,
            title="Save CSV Report"
        )
        if not file_path: return
        
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(tree["columns"])
                for item_id in tree.get_children():
                    writer.writerow(tree.item(item_id)['values'])
            messagebox.showinfo("Success", f"Report successfully exported to\n{file_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while saving the CSV file:\n{e}", parent=self)

    def _extract_and_update_workcodes(self, textbox_widget):
        """
        Extracts work codes (6-digit) and wagelist IDs.
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
            final_results = list(dict.fromkeys(results))

            if final_results:
                textbox_widget.configure(state="normal")
                textbox_widget.delete("1.0", tkinter.END)
                textbox_widget.insert("1.0", "\n".join(final_results))
                messagebox.showinfo("Extraction Complete", f"Found and extracted {len(final_results)} unique codes.", parent=self)
            else:
                messagebox.showinfo("No Codes Found", "Could not find any matching work codes or wagelist IDs in the text.", parent=self)
        
        except Exception as e:
            messagebox.showerror("Extraction Error", f"An error occurred during extraction: {e}", parent=self)

    # --- Helper for Appearance Mode ---
    def _apply_appearance_mode(self, theme_color_tuple):
        """
        Picks the correct color from a (light, dark) tuple based on current mode.
        """
        if isinstance(theme_color_tuple, (tuple, list)):
            if ctk.get_appearance_mode().lower() == "light":
                return theme_color_tuple[0]
            else:
                return theme_color_tuple[1]
        return theme_color_tuple