# tabs/pdf_merger_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os
from pypdf import PdfWriter
from datetime import datetime  # <-- ADD THIS IMPORT

from .base_tab import BaseAutomationTab

class PDFMergerTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, automation_key="pdf_merger")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1) # <-- UPDATED: Make log area (now at row 4) expand
        
        self.selected_files = [] # To store the list of PDF paths

        self._create_widgets()

    def _apply_appearance_mode(self, color):
        """Helper to get correct color from theme."""
        if isinstance(color, (list, tuple)):
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        return color

    def _create_widgets(self):
        # --- Controls Frame ---
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))
        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_rowconfigure(1, weight=1) # Make listbox expand

        # --- File Selection Button ---
        select_button_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        select_button_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        
        self.select_files_button = ctk.CTkButton(select_button_frame, text="Select PDF Files...", command=self.select_files)
        self.select_files_button.pack(side="left")
        
        ctk.CTkLabel(select_button_frame, text="Select multiple PDFs. The order below is the merge order.").pack(side="left", padx=10)

        # --- File List & Reordering ---
        list_frame = ctk.CTkFrame(controls_frame) 
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.file_listbox = tkinter.Listbox(list_frame, height=15, selectmode=tkinter.SINGLE, exportselection=False)
        
        # Apply styling to match the app theme
        bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkTextbox"]["fg_color"])
        text_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        select_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
        select_fg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["text_color"])

        self.file_listbox.configure(
            bg=bg_color, fg=text_color, 
            selectbackground=select_bg, 
            selectforeground=select_fg,
            borderwidth=0, relief="flat",
            highlightthickness=0
        )
        self.file_listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ctk.CTkScrollbar(list_frame, command=self.file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_listbox.configure(yscrollcommand=scrollbar.set)

        # --- Reordering Buttons ---
        reorder_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        reorder_frame.grid(row=1, column=1, sticky="ns", padx=(5, 10), pady=5)
        
        self.move_up_button = ctk.CTkButton(reorder_frame, text="Move Up", command=self.move_up, width=100)
        self.move_up_button.pack(pady=5)
        
        self.move_down_button = ctk.CTkButton(reorder_frame, text="Move Down", command=self.move_down, width=100)
        self.move_down_button.pack(pady=5)
        
        self.remove_button = ctk.CTkButton(reorder_frame, text="Remove", command=self.remove_selected, fg_color="red", hover_color="#C70000", width=100)
        self.remove_button.pack(pady=5)
        
        # --- NEW: Output File Name ---
        output_name_frame = ctk.CTkFrame(self)
        output_name_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(10, 0))
        output_name_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(output_name_frame, text="Output File Name:").grid(row=0, column=0, sticky="w", padx=15, pady=10)
        self.file_name_entry = ctk.CTkEntry(output_name_frame, placeholder_text="e.g., Kasraydih")
        self.file_name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 15), pady=10)
        # --- END NEW ---

        # --- Action Buttons ---
        action_frame = self._create_action_buttons(parent_frame=self)
        action_frame.grid(row=3, column=0, sticky="ew", pady=10, padx=10) # <-- UPDATED: row=3
        
        self.start_button.configure(text="Merge Selected PDFs")
        self.reset_button.configure(text="Clear List")
        
        # --- Logs ---
        notebook = ctk.CTkTabview(self)
        notebook.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10)) # <-- UPDATED: row=4
        self._create_log_and_status_area(parent_notebook=notebook)
        # We don't need the progress bar for this fast task
        self.progress_bar.pack_forget()

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        # Use the base class method to handle Start, Stop, Reset
        self.set_common_ui_state(running)
        
        state = "disabled" if running else "normal"
        self.select_files_button.configure(state=state)
        self.move_up_button.configure(state=state)
        self.move_down_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.file_listbox.configure(state=state)
        self.file_name_entry.configure(state=state) # <-- ADD THIS

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Select PDF files to merge",
            filetypes=[("PDF files", "*.pdf")]
        )
        if files:
            new_files_count = 0
            for f in files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
                    new_files_count += 1
            self.update_listbox()
            self.app.log_message(self.log_display, f"Added {new_files_count} new PDF file(s). Total: {len(self.selected_files)}")
    
    def update_listbox(self):
        self.file_listbox.delete(0, tkinter.END)
        for i, f in enumerate(self.selected_files):
            self.file_listbox.insert(tkinter.END, f"{i+1}. {os.path.basename(f)}")
            
    def move_up(self):
        try:
            idx = self.file_listbox.curselection()[0]
            if idx > 0:
                self.selected_files[idx], self.selected_files[idx-1] = self.selected_files[idx-1], self.selected_files[idx]
                self.update_listbox()
                self.file_listbox.selection_set(idx - 1)
        except IndexError:
            pass # No selection

    def move_down(self):
        try:
            idx = self.file_listbox.curselection()[0]
            if idx < len(self.selected_files) - 1:
                self.selected_files[idx], self.selected_files[idx+1] = self.selected_files[idx+1], self.selected_files[idx]
                self.update_listbox()
                self.file_listbox.selection_set(idx + 1)
        except IndexError:
            pass # No selection
            
    def remove_selected(self):
        try:
            idx = self.file_listbox.curselection()[0]
            removed_file = self.selected_files.pop(idx)
            self.update_listbox()
            self.app.log_message(self.log_display, f"Removed: {os.path.basename(removed_file)}")
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a file from the list to remove.", parent=self)

    def reset_ui(self):
        if not self.selected_files and not self.file_name_entry.get(): 
            return
        if messagebox.askokcancel("Clear Form?", "Are you sure you want to clear all selected files and the file name?"):
            self.selected_files.clear()
            self.update_listbox()
            self.file_name_entry.delete(0, tkinter.END) # <-- ADD THIS
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.app.log_message(self.log_display, "File list and name cleared.")
            self.app.after(0, self.app.set_status, "Ready")
            
    # --- NEW HELPER METHOD ---
    def _get_output_path(self, base_name):
        """Generates a unique output path in the user's downloads folder."""
        try:
            downloads_dir = self.app.get_user_downloads_path()
            output_dir = os.path.join(downloads_dir, "NregaBot", "Merged_Pdf_Output")
            
            # Create the directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            date_str = datetime.now().strftime("%d-%b-%Y") # e.g., 01-Nov-2025
            
            # Initial file name
            file_name = f"{base_name}_{date_str}.pdf"
            output_path = os.path.join(output_dir, file_name)
            
            # Handle conflicts
            count = 1
            while os.path.exists(output_path):
                file_name = f"{base_name}_{date_str}({count}).pdf"
                output_path = os.path.join(output_dir, file_name)
                count += 1
                
            return output_path
        except Exception as e:
            self.app.log_message(self.log_display, f"Error creating output path: {e}", "error")
            messagebox.showerror("Path Error", f"Could not create output directory: {e}", parent=self)
            return None
            
    def start_automation(self):
        if len(self.selected_files) < 2:
            messagebox.showwarning("Not Enough Files", "Please select at least two PDF files to merge.", parent=self)
            return

        # --- UPDATED: Get base name from entry ---
        base_name = self.file_name_entry.get().strip()
        if not base_name:
            messagebox.showwarning("Input Required", "Please enter an output file name (e.g., Kasraydih).", parent=self)
            return

        # --- UPDATED: Generate path automatically ---
        output_path = self._get_output_path(base_name)
        
        if not output_path:
            return # Error already shown by _get_output_path

        # Pass a copy of the list to the thread
        self.app.start_automation_thread(
            self.automation_key, 
            self.run_automation_logic, 
            args=(self.selected_files.copy(), output_path)
        )
        
    def run_automation_logic(self, file_list, output_path):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        self.app.log_message(self.log_display, f"Starting merge of {len(file_list)} files...")
        self.app.after(0, self.app.set_status, "Merging PDFs...")

        try:
            merger = PdfWriter()
            
            for i, pdf_path in enumerate(file_list):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "Merge cancelled.", "warning")
                    merger.close()
                    return

                self.app.log_message(self.log_display, f"Adding file {i+1}/{len(file_list)}: {os.path.basename(pdf_path)}")
                self.app.after(0, self.update_status, f"Adding file {i+1}/{len(file_list)}")
                merger.append(pdf_path)
            
            if self.app.stop_events[self.automation_key].is_set(): return

            self.app.log_message(self.log_display, f"Writing to output file: {output_path}")
            with open(output_path, "wb") as f_out:
                merger.write(f_out)
            
            merger.close()
            
            self.app.log_message(self.log_display, "Merge complete!", "success")
            messagebox.showinfo("Success", f"Successfully merged {len(file_list)} files into:\n{output_path}", parent=self)
            
            if messagebox.askyesno("Open Location?", "Do you want to open the folder containing the merged file?", parent=self):
                self.app.open_folder(os.path.dirname(output_path))

        except Exception as e:
            self.app.log_message(self.log_display, f"A critical error occurred: {e}", "error")
            messagebox.showerror("Merge Error", f"An error occurred during merging:\n\n{e}", parent=self)
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.app.set_status, "Ready")