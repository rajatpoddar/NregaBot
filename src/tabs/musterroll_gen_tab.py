# tabs/musterroll_gen_tab.py
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os, json, time, base64, sys, subprocess, requests, threading
from datetime import datetime
# pypdf may be missing on installs that predate v3.0.0 (smart code-only
# updates cannot add new Python deps). Fall back to PyPDF2, and if neither
# is available the merge/PDF features will show a clear message instead of
# crashing the whole tab.
try:
    from pypdf import PdfWriter, PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfWriter, PdfReader
    except ImportError:
        PdfWriter = PdfReader = None
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException, 
    UnexpectedAlertPresentException
)
from src import config
from src.i18n import tr
from .base_tab import BaseAutomationTab

from typing import Any, Callable, Dict, List, Optional, Tuple
from ._imports import By, Select, WebDriverWait, EC, NoSuchElementException, StaleElementReferenceException, TimeoutException  # noqa: F401


class MusterrollGenTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="muster")
        self.config_file = self.app.get_data_path("muster_roll_inputs.json")
        
        self.mapping_file = self.app.get_data_path("mr_panchayat_staff_map.json")
        self.mapping_data = {} 
        
        self.success_count = 0
        self.skipped_count = 0
        self.output_dir = ""
        self.current_session_files = []
        
        self._load_mapping_data()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_widgets()
        self.load_inputs()
    def _create_widgets(self) -> None:
        # --- Header / intro card (P7.2: pending-bills style) ---
        self._create_header_card(self, "📄", tr("tab.musterroll_gen.title"), tr("tab.musterroll_gen.subtitle"),
                                 icon_key="emoji_mr_gen")

        # --- Main Notebook (Settings | Work Search Keys | Results | Logs) ---
        data_notebook = ctk.CTkTabview(self)
        data_notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        settings_tab = data_notebook.add("Settings")
        work_codes_tab = data_notebook.add("Work Search Keys (or auto)")
        results_tab = data_notebook.add("Results")
        self._create_log_and_status_area(parent_notebook=data_notebook)

        # ════════════════ SETTINGS TAB ════════════════
        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(0, weight=1)

        # This frame holds all the user input fields (bordered card)
        controls_frame = ctk.CTkFrame(settings_tab, corner_radius=12, border_width=1,
                                      border_color=("gray85", "gray30"))
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        controls_frame.grid_columnconfigure((1,3), weight=1)
        
        ctk.CTkLabel(controls_frame, text=tr("common.panchayat_name_label")).grid(row=0, column=0, sticky='w', padx=15, pady=(15,0))
        p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
        self.panchayat_var = ctk.StringVar(value=config.ALL_PANCHAYATS_LABEL)
        self.panchayat_var.trace_add("write", lambda *_: self._on_panchayat_selected())
        self.panchayat_menu = ctk.CTkOptionMenu(controls_frame, variable=self.panchayat_var,
                                                values=self._all_panchayat_values(p_vals))
        self.panchayat_menu.grid(row=0, column=1, columnspan=3, sticky='ew', padx=15, pady=(15,0))
        ctk.CTkLabel(controls_frame, text="💡 Select '🌐 All Panchayats' for every panchayat of the block, or '⭐ My Saved Panchayats' for only your saved panchayats.",
                     text_color="gray50", font=ctk.CTkFont(size=11)).grid(row=1, column=1, columnspan=3, sticky='w', padx=15, pady=(2, 0))
        
        # --- Start Date ---
        ctk.CTkLabel(controls_frame, text=tr("form.mr_gen.date_from")).grid(row=2, column=0, sticky='w', padx=15, pady=5)
        start_date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        start_date_frame.grid(row=2, column=1, sticky='ew', padx=(15,5), pady=5)
        self.start_date_entry = ctk.CTkEntry(start_date_frame, placeholder_text=tr("common.date_format"))
        self.start_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(start_date_frame, text="📅", width=30, fg_color=("gray85", "gray25"), text_color=("black", "white"),
                    command=lambda: self.open_date_picker(lambda d: [self.start_date_entry.delete(0, "end"), self.start_date_entry.insert(0, d)])).pack(side="right", padx=(5,0))

        # --- End Date ---
        ctk.CTkLabel(controls_frame, text=tr("form.mr_gen.date_to")).grid(row=2, column=2, sticky='w', padx=10, pady=5)
        end_date_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        end_date_frame.grid(row=2, column=3, sticky='ew', padx=(5,15), pady=5)
        self.end_date_entry = ctk.CTkEntry(end_date_frame, placeholder_text=tr("common.date_format"))
        self.end_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(end_date_frame, text="📅", width=30, fg_color=("gray85", "gray25"), text_color=("black", "white"),
                    command=lambda: self.open_date_picker(lambda d: [self.end_date_entry.delete(0, "end"), self.end_date_entry.insert(0, d)])).pack(side="right", padx=(5,0))
        
        ctk.CTkLabel(controls_frame, text=tr("form.mr_gen.select_designation")).grid(row=3, column=0, sticky='w', padx=15, pady=5)
        designation_options = ["Junior Engineer--BP", "Assistant Engineer--BP", "Technical Assistant--BP", "Acrited Engineer(AE)--GP", "Junior Engineer--GP", "Technical Assistant--GP"]
        self.designation_var = ctk.StringVar()
        self.designation_menu = ctk.CTkOptionMenu(controls_frame, variable=self.designation_var, values=designation_options)
        self.designation_menu.grid(row=3, column=1, sticky='ew', padx=(15,5), pady=5)
        
        ctk.CTkLabel(controls_frame, text=tr("form.mr_gen.select_staff")).grid(row=3, column=2, sticky='w', padx=10, pady=5)
        s_vals = self.app.history_manager.get_suggestions("staff_name") or [""]
        self.staff_var = ctk.StringVar()
        self.staff_menu = ctk.CTkOptionMenu(controls_frame, variable=self.staff_var, values=s_vals)
        self.staff_menu.grid(row=3, column=3, sticky='ew', padx=(5,15), pady=5)
        
        ctk.CTkLabel(controls_frame, text=tr("common.output_action")).grid(row=4, column=0, sticky='w', padx=15, pady=5)
        self.output_action_var = ctk.StringVar(value="Save as PDF")
        self.output_action_menu = ctk.CTkOptionMenu(controls_frame, variable=self.output_action_var, values=["Save as PDF", "Print"])
        self.output_action_menu.grid(row=4, column=1, sticky='ew', padx=(15,5), pady=5)
        
        self.save_to_cloud_var = tkinter.BooleanVar(value=True) 
        self.save_to_cloud_checkbox = ctk.CTkCheckBox(
            controls_frame, 
            text=tr("form.mr_gen.save_pdf_cloud"), 
            variable=self.save_to_cloud_var
        )
        self.save_to_cloud_checkbox.grid(row=4, column=2, columnspan=2, sticky='w', padx=15, pady=5)

        ctk.CTkLabel(controls_frame, text=tr("common.orientation")).grid(row=5, column=0, sticky='w', padx=15, pady=5)
        self.orientation_var = ctk.StringVar(value="Landscape")
        self.orientation_segmented_button = ctk.CTkSegmentedButton(controls_frame, variable=self.orientation_var, values=["Landscape", "Portrait"])
        self.orientation_segmented_button.grid(row=5, column=1, sticky='ew', padx=(15,5), pady=5)

        ctk.CTkLabel(controls_frame, text=tr("common.pdf_scale")).grid(row=5, column=2, sticky='w', padx=10, pady=5)
        scale_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        scale_frame.grid(row=5, column=3, sticky="ew", padx=(5,15), pady=5)
        scale_frame.grid_columnconfigure(0, weight=1)
        self.scale_slider = ctk.CTkSlider(scale_frame, from_=50, to=100, number_of_steps=50, command=self._update_scale_label)
        self.scale_slider.set(75)
        self.scale_slider.grid(row=0, column=0, sticky="ew")
        self.scale_label = ctk.CTkLabel(scale_frame, text="75%", width=40)
        self.scale_label.grid(row=0, column=1, padx=(10, 0))
        ctk.CTkLabel(controls_frame, text=tr("form.mr_gen.output_hint"), text_color="gray50").grid(row=6, column=2, columnspan=2, sticky='e', padx=15, pady=(10,15))
        
        # Action Buttons (Start, Stop, Reset) — outside the card
        action_frame = self._create_action_buttons(parent_frame=settings_tab)
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 15))
        
        work_codes_tab.grid_columnconfigure(0, weight=1)
        work_codes_tab.grid_rowconfigure(1, weight=1)
        wc_controls = ctk.CTkFrame(work_codes_tab, fg_color="transparent")
        wc_controls.grid(row=0, column=0, sticky='ew')
        clear_button = ctk.CTkButton(wc_controls, text=tr("common.clear"), width=80, command=lambda: self.work_codes_text.delete("1.0", tkinter.END))
        clear_button.pack(side='right', pady=(5,0), padx=(0,5))
        
        extract_button = ctk.CTkButton(wc_controls, text=tr("common.extract_from_text"), width=120,
                                       command=lambda: self._extract_and_update_workcodes(self.work_codes_text))
        extract_button.pack(side='right', pady=(5,0), padx=(0, 5))
        
        self.work_codes_text = ctk.CTkTextbox(work_codes_tab, height=100)
        self.work_codes_text.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        
        results_tab.grid_columnconfigure(0, weight=1); results_tab.grid_rowconfigure(2, weight=1)
        
        results_action_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        results_action_frame.grid(row=0, column=0, sticky="ew", pady=(5,10), padx=5)
        
        self.merge_pdfs_button = ctk.CTkButton(results_action_frame, text=tr("common.merge_saved_pdfs"), command=self.merge_saved_pdfs)
        self.merge_pdfs_button.pack(side='left', padx=(0, 10))

        export_controls_frame = ctk.CTkFrame(results_action_frame, fg_color="transparent")
        export_controls_frame.pack(side='right', padx=(10, 0))
        self.export_button = ctk.CTkButton(export_controls_frame, text=tr("common.export_excel"), command=self.export_report)
        self.export_button.pack(side='left')
        
        summary_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        summary_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        summary_frame.grid_columnconfigure((0, 1), weight=1)
        self.success_label = ctk.CTkLabel(summary_frame, text=tr("common.success_default"), text_color="#2E8B57", font=ctk.CTkFont(weight="bold")); self.success_label.grid(row=0, column=0, sticky='w')
        self.skipped_label = ctk.CTkLabel(summary_frame, text=tr("common.skipped_failed_default"), text_color="#DAA520", font=ctk.CTkFont(weight="bold")); self.skipped_label.grid(row=0, column=1, sticky='w')
        
        cols = ("Timestamp", "Panchayat", "Work Code/Key", "Status", "Details"); self.results_tree = ttk.Treeview(results_tab, columns=cols, show='headings')
        for col in cols: self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=80, anchor='center'); self.results_tree.column("Work Code/Key", width=250); self.results_tree.column("Status", width=100, anchor='center'); self.results_tree.column("Details", width=400)
        self.results_tree.grid(row=2, column=0, sticky='nsew')
        scrollbar = ctk.CTkScrollbar(results_tab, command=self.results_tree.yview); self.results_tree.configure(yscroll=scrollbar.set); scrollbar.grid(row=2, column=1, sticky='ns')
        self.style_treeview(self.results_tree)
        self._setup_treeview_sorting(self.results_tree)



    def _update_scale_label(self, value):
        self.scale_label.configure(text=f"{int(value)}%")

    def set_ui_state(self, running: bool):
        if not self._is_alive():
            return
        self.set_common_ui_state(running)
        state = "disabled" if running else "normal"
        self.panchayat_menu.configure(state=state)
        self.start_date_entry.configure(state=state)
        self.end_date_entry.configure(state=state)
        self.staff_menu.configure(state=state)
        self.designation_menu.configure(state=state)
        self.orientation_segmented_button.configure(state=state)
        self.scale_slider.configure(state=state)
        self.output_action_menu.configure(state=state)
        self.work_codes_text.configure(state=state)
        self.save_to_cloud_checkbox.configure(state=state)
        
        self.export_button.configure(state=state)
        for menu_name in ("export_format_menu", "export_filter_menu"):
            menu = getattr(self, menu_name, None)
            if menu is not None:
                try:
                    menu.configure(state=state)
                except Exception:
                    pass
        self.merge_pdfs_button.configure(state=state)
        if (state == "normal" and hasattr(self, "_on_format_change")
                and getattr(self, "export_format_menu", None) is not None):
            try:
                self._on_format_change(self.export_format_menu.get())
            except Exception:
                pass

    def _load_mapping_data(self):
        """Load panchayat→staff mapping from JSON, normalizing keys to lowercase for case-insensitive lookup."""
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, 'r') as f:
                    raw = json.load(f)
                self.mapping_data = {k.strip().lower(): v for k, v in raw.items()}
            except Exception:
                self.mapping_data = {}

    def _save_mapping_pair(self, panchayat, staff):
        if not panchayat or not staff: return
        key = panchayat.strip().lower()
        self.mapping_data[key] = staff.strip()
        try:
            with open(self.mapping_file, 'w') as f:
                json.dump(self.mapping_data, f, indent=4)
        except Exception as e:
            print(f"Error saving mapping: {e}")

    def _on_panchayat_selected(self, *args):
        """Called when panchayat is selected from dropdown — auto-fills staff from mapping."""
        self._auto_fill_staff()

    def _auto_fill_staff(self):
        current_panchayat = self.panchayat_var.get().strip().lower()
        if current_panchayat in self.mapping_data:
            saved_staff = self.mapping_data[current_panchayat]
            if self.staff_var.get().strip() != saved_staff:
                # Ensure the mapped staff name appears in the dropdown options,
                # otherwise the value can't be re-selected by the user.
                vals = list(self.staff_menu.cget("values"))
                if saved_staff not in vals:
                    vals = [v for v in vals if v != ""] + [saved_staff]
                    self.staff_menu.configure(values=vals)
                self.staff_var.set(saved_staff)
    def _validate_date_not_too_old(self, date_str: str) -> bool:
        """Check if the start date is not more than 2 days before current date.
        Returns True if valid, False if too old."""
        try:
            start_date = datetime.strptime(date_str, "%d/%m/%Y")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            days_diff = (today - start_date).days
            if days_diff > 2:
                messagebox.showwarning(
                    "Date Too Old",
                    f"Start date ({date_str}) is {days_diff} days before today.\n\n"
                    f"Automation cannot start with a date this old.\n"
                    f"Please update the start date to within the last 2 days."
                )
                return False
            return True
        except ValueError:
            messagebox.showwarning(
                "Invalid Date",
                f"Start date '{date_str}' is not valid. Please use DD/MM/YYYY format."
            )
            return False

    def start_automation(self) -> None:
        for item in self.results_tree.get_children(): self.results_tree.delete(item)
        self.success_count, self.skipped_count = 0, 0
        self.current_session_files = [] 
        self.success_label.configure(text=tr("common.success_default"))
        self.skipped_label.configure(text=tr("common.skipped_failed_default"))
        
        start_date = self.start_date_entry.get().strip()
        
        # Validate start date is not too old
        if not self._validate_date_not_too_old(start_date):
            return
        
        inputs = {
            'panchayat': self.panchayat_var.get().strip(), 
            'start_date': start_date, 
            'end_date': self.end_date_entry.get().strip(), 
            'designation': self.designation_var.get(), 
            'staff': self.staff_var.get().strip(), 
            'orientation': self.orientation_var.get(),
            'scale': self.scale_slider.get(),
            'output_action': self.output_action_var.get(), 
            'work_codes_raw': self.work_codes_text.get("1.0", tkinter.END).strip(),
            'save_to_cloud': self.save_to_cloud_var.get()
        }

        if not all(inputs[k] for k in ['panchayat', 'start_date', 'end_date', 'designation', 'staff']):
            messagebox.showwarning(tr("errors.input_error"), tr("dialogs.all_fields_required"))
            return
        if inputs['panchayat'] not in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL):
            self._save_mapping_pair(inputs['panchayat'], inputs['staff'])
        inputs['work_codes'] = [line.strip() for line in inputs['work_codes_raw'].split('\n') if line.strip()]
        inputs['auto_mode'] = not bool(inputs['work_codes'])
        self.save_inputs(inputs)
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))
    def retry_logic_handler(self) -> None:
        failed_items = []
        for item_id in self.results_tree.get_children():
            values = self.results_tree.item(item_id)['values']
            work_code = str(values[2])
            status = str(values[3]).lower()
            if "success" not in status:
                failed_items.append(work_code)
        
        if not failed_items:
            messagebox.showinfo(tr("base.error_tab.retry_btn"), tr("dialogs.no_failed_to_retry"))
            return

        if not messagebox.askyesno(tr("base.retry_confirm_title"), tr("dialogs.retry_failed_skipped", count=len(failed_items))):
            return

        self.work_codes_text.configure(state="normal")
        self.work_codes_text.delete("1.0", tkinter.END)
        self.work_codes_text.insert("1.0", "\n".join(failed_items))
        self.work_codes_text.configure(state="disabled")

        self.safe_tree_clear()
            
        self.success_count = 0
        self.skipped_count = 0
        self.update_status("Retrying failed items...", 0.0)
        self.start_automation()
    def reset_ui(self) -> None:
        if messagebox.askokcancel(tr("dialogs.reset_form"), tr("dialogs.reset_confirm_logs")):
            self.panchayat_var.set("")
            self.start_date_entry.clear(); self.end_date_entry.clear()
            self.staff_var.set("")
            self.designation_var.set('')
            self.orientation_var.set('Landscape')
            self.scale_slider.set(75); self.scale_label.configure(text="75%")
            self.output_action_var.set('Save as PDF')
            self.work_codes_text.delete('1.0', tkinter.END)
            for item in self.results_tree.get_children(): self.results_tree.delete(item)
            self.app.clear_log(self.log_display)
            self.update_status("Ready", 0.0)
            self.success_label.configure(text=tr("common.success_default")); self.skipped_label.configure(text=tr("common.skipped_failed_default"))
            self.log_info("Form has been reset.")
            self.app.after(0, self.app.set_status, "Ready")
            
    def save_inputs(self, inputs):
        try:
            inputs_to_save = inputs.copy()
            inputs_to_save.pop('work_codes_raw', None)
            inputs_to_save.pop('work_codes', None)
            inputs_to_save.pop('auto_mode', None)
            self.app.history_manager.save_tab_inputs_batch("muster", inputs_to_save)
        except Exception as e: print(f"Error saving inputs: {e}")
        
    def load_inputs(self):
        data = self.app.history_manager.get_tab_inputs("muster")
        if data:
            self.panchayat_var.set(data.get('panchayat', ''))
            self.start_date_entry.delete(0, "end"); self.start_date_entry.insert(0, data.get('start_date', ''))
            self.end_date_entry.delete(0, "end"); self.end_date_entry.insert(0, data.get('end_date', ''))
            self.designation_var.set(data.get('designation', ''))
            self.staff_var.set(data.get('staff', ''))
            self.orientation_var.set(data.get('orientation', 'Landscape'))
            self.scale_slider.set(float(data.get('scale', 75))); self._update_scale_label(self.scale_slider.get())
            self.output_action_var.set(data.get('output_action', 'Save as PDF'))
            # Coerce to a real bool: saved data may hold "", "True", "False", "1", etc.
            self.save_to_cloud_var.set(str(data.get('save_to_cloud', True)).strip().lower() in ("1", "true", "yes", "on"))

    def _print_file(self, file_path):
        try:
            if not os.path.exists(file_path):
                self.log_error(f"Print Error: File not found at {file_path}")
                return
            if sys.platform == "win32": os.startfile(file_path, "print")
            else: subprocess.run(["lpr", file_path], check=True)
            self.log_info(f"Sent {os.path.basename(file_path)} to printer.")
            time.sleep(2)
        except Exception as e:
            error_msg = f"An unexpected error occurred while printing: {e}"
            self.log_error(error_msg)
            self.app.after(0, lambda: messagebox.showwarning(tr("dialogs.print_error"), error_msg))

    def _get_output_dir(self, location_panchayat):
        try:
            safe_location_panchayat = "".join(c for c in location_panchayat if c.isalnum() or c in (' ', '_')).rstrip()
            if not safe_location_panchayat: safe_location_panchayat = "Unknown_Panchayat"
            date_str = datetime.now().strftime('%Y-%m-%d')
            output_dir = os.path.join(self.app.get_nregabot_path("PDF_Output/MR_Output"), safe_location_panchayat, date_str)
            os.makedirs(output_dir, exist_ok=True)
            return output_dir
        except Exception as e:
            self.log_error(f"Error creating output directory: {e}")
            messagebox.showerror(tr("dialogs.directory_error"), tr("dialogs.could_not_create_output_dir", error=e))
            return None

    def run_automation_logic(self, inputs):
        self.app.after(0, self.set_ui_state, True)
        self.app.clear_log(self.log_display)
        panchayat_target = inputs.get('panchayat', '')
        all_mode = panchayat_target in (config.ALL_PANCHAYATS_LABEL, config.MY_PANCHAYATS_LABEL)
        saved_mode = panchayat_target == config.MY_PANCHAYATS_LABEL
        self.log_info(f"Starting MR generation for: {panchayat_target}")
        self.app.after(0, self.app.set_status, "Running MR Generation...")
        
        try:
            driver = self.app.get_driver()
            if not driver: 
                self.app.after(0, self.set_ui_state, False)
                return
            wait = WebDriverWait(driver, 20)

            # Tabs are created once and cached, so the mapping loaded in
            # __init__ can be stale if the user added/edited panchayat→staff
            # mappings in Settings during this session. Re-read it fresh.
            self._load_mapping_data()

            # Determine which panchayats to process
            panchayats_to_process = []
            if all_mode:
                self.log_info("🌐 Fetching all panchayats from the website...")
                driver.get(config.MUSTER_ROLL_CONFIG["base_url"])
                agency_select = Select(wait.until(EC.presence_of_element_located((By.ID, "exe_agency"))))
                prefix = config.AGENCY_PREFIX
                for t in self._get_select_option_texts(agency_select):
                    if t.startswith(prefix):
                        t = t[len(prefix):]
                    panchayats_to_process.append(t.strip())
                if saved_mode:
                    panchayats_to_process = self._filter_panchayats_to_saved(panchayats_to_process)
                    self.log_info(f"⭐ My Saved Panchayats mode: {len(panchayats_to_process)} saved panchayat(s) will be processed.")
                else:
                    self.log_info(f"Found {len(panchayats_to_process)} panchayats to process.")
                if self._abort_if_no_saved_panchayats(panchayats_to_process):
                    return
            else:
                panchayats_to_process = [panchayat_target]

            total_panchayats = len(panchayats_to_process)
            for p_idx, p_name in enumerate(panchayats_to_process):
                if self.is_stopped(): 
                    self.log_warning("Stop signal received.")
                    break
                self.log_info(f"=== Panchayat {p_idx+1}/{total_panchayats}: {p_name} ===")
                self.app.after(0, self.update_status, f"{p_name}: fetching items...", p_idx / total_panchayats)
                inputs['panchayat'] = p_name
                # 'All Panchayats' / 'My Saved Panchayats' runs process MANY
                # panchayats but the form holds only ONE fixed staff value.
                # Use the saved panchayat→staff mapping (Settings > Staff
                # Mapping / previously-run pairs) per panchayat so the correct
                # technical staff is selected for each. Unmapped panchayats
                # keep the manually-selected staff.
                if all_mode:
                    mapped_staff = self.mapping_data.get(p_name.strip().lower())
                    if mapped_staff:
                        self.log_info(f"   → Staff mapped for {p_name}: {mapped_staff}")
                        inputs['staff'] = mapped_staff
                    else:
                        self.log_info(f"   → No staff mapping for {p_name} — using '{inputs.get('staff', '')}'")
                self.output_dir = self._get_output_dir(p_name)
                if not self.output_dir:
                    self.log_warning(f"Skipping {p_name}: could not create output directory.")
                    continue
                if not self._validate_panchayat(driver, wait, p_name, silent=all_mode):
                    continue

                self.app.update_history("location_panchayat", p_name)
                self.app.update_history("staff_name", inputs['staff'])

                items_to_process = self._get_items_to_process(driver, wait, inputs)
                session_skip_list = set()
                total_items = len(items_to_process)

                for index, item in enumerate(items_to_process):
                    if self.is_stopped(): 
                        self.log_warning("Stop signal received.")
                        break
                    self.log_info(f"--- Processing item ({index+1}/{total_items}): {item} ---")
                    self.app.after(0, self.update_status, f"{p_name}: {item}", (p_idx + (index + 1) / max(total_items, 1)) / max(total_panchayats, 1))
                    
                    self._process_single_item(driver, wait, inputs, item, self.output_dir, session_skip_list)

        except Exception as e:
            self.log_error(f"A critical error occurred: {e}")
            if "in str" not in str(e):
                messagebox.showerror(tr("dialogs.critical_error"), tr("dialogs.unexpected_error_stopped", error=e))
        
        finally:
            self.app.after(0, self.set_ui_state, False)
            self.app.after(0, self.update_status, "Automation Finished.", 1.0)
            self.app.after(100, self._show_completion_dialog, self.output_dir)
            self.app.after(0, self.app.set_status, "Automation Finished")

    def _show_completion_dialog(self, output_dir):
        summary = f"Automation complete.\nSuccess: {self.success_count}\nSkipped/Failed: {self.skipped_count}"
        if "macro" in self.app.active_automations:
            self.log_info(f"Batch Finished. Output saved to: {output_dir}")
            return

        if self.success_count > 0 and output_dir and os.path.exists(output_dir):
            if messagebox.askyesno(tr("dialogs.task_finished"), tr("dialogs.open_output_after", summary=summary)):
                self.app.open_folder(output_dir)
        else:
            self.log_info(f"📊 {summary}")
    def _validate_panchayat(self, driver, wait, location_panchayat, silent=False):
        """Validate that the panchayat exists on the website. In silent mode
        (All Panchayats / Macro) failures are logged instead of blocking on a
        messagebox."""
        try:
            self.log_info("Validating Panchayat name...")
            driver.get(config.MUSTER_ROLL_CONFIG["base_url"])
            # Central helper — GP login has no agency/panchayat dropdown;
            # skip validation and return True (continue).
            status, _ = self._select_panchayat_or_skip(
                driver, wait, config.AGENCY_PREFIX + location_panchayat,
                ["exe_agency"])
            if status == "gp":
                self.log_info("GP login detected — no panchayat dropdown, validation skipped.")
                return True
            if status != "selected":
                error_msg = f"Panchayat name '{location_panchayat}' not found on the website. Please check spelling."
                if "macro" in self.app.active_automations or silent:
                    self.log_error(f"Skipping: {error_msg}")
                    return False
                messagebox.showerror(tr("dialogs.validation_error"), error_msg)
                return False
            self.log_success("Panchayat name is valid.")
            return True
        except Exception as e:
            self.log_error(f"Validation failed: Error: {e}")
            return False

    def _get_items_to_process(self, driver, wait, inputs):
        if inputs['auto_mode']:
            self.log_info("Auto Mode: Fetching available work codes...")
            try:
                agency_select = Select(driver.find_element(By.ID, "exe_agency"))
                self._select_by_text_case_insensitive(agency_select, config.AGENCY_PREFIX + inputs['panchayat'])
                wait.until(lambda d: len(Select(d.find_element(By.ID, "ddlWorkCode")).options) > 1)
                items = [opt.text for opt in Select(driver.find_element(By.ID, "ddlWorkCode")).options if opt.get_attribute("value")]
                self.log_info(f"Found {len(items)} available work codes.")
                return items
            except Exception as e:
                self.log_error(f"Could not fetch work codes automatically. Error: {e}")
                return []
        else:
            self.log_info(f"Processing {len(inputs['work_codes'])} provided work keys.")
            return inputs['work_codes']

    def _process_single_item(self, driver, wait, inputs, item, output_dir, session_skip_list):
        full_work_code_text = ""
        try:
            self.log_info("   - Navigating to MR page...")
            driver.get(config.MUSTER_ROLL_CONFIG["base_url"])
            
            self.log_info("   - Selecting Panchayat...")
            status, _ = self._select_panchayat_or_skip(
                driver, wait, config.AGENCY_PREFIX + inputs['panchayat'],
                ["exe_agency"])
            if status == "gp":                 self.log_info("   - GP login — no panchayat dropdown, selection skipped.")
            
            self.log_info(f"   - Selecting work code for '{item}'...")
            full_work_code_text = self._select_work_code(driver, wait, item, inputs['auto_mode'])
            
            if full_work_code_text in session_skip_list:
                self._log_result(inputs['panchayat'], item, "Skipped", "Already processed in this session.")
                return

            self.log_info("   - Entering dates and staff details...")
            driver.execute_script(f"document.getElementById('txtDateFrom').value = '{inputs['start_date']}';")
            driver.execute_script(f"document.getElementById('txtDateTo').value = '{inputs['end_date']}';")
            
            designation_dropdown = wait.until(EC.presence_of_element_located((By.ID, "ddldesg")))
            Select(designation_dropdown).select_by_visible_text(inputs['designation'])

            self.log_info("   - Waiting for Technical Staff list to populate...")
            wait.until(EC.presence_of_element_located((By.XPATH, "//select[@id='ddlstaff']/option[position()>1]")))
            
            staff_dropdown = Select(driver.find_element(By.ID, "ddlstaff"))
            staff_found = False
            for opt in staff_dropdown.options:
                if inputs['staff'].lower() == opt.text.lower():
                    staff_dropdown.select_by_visible_text(opt.text)
                    staff_found = True
                    break
            
            if not staff_found:
                raise ValueError(f"Staff name '{inputs['staff']}' not found. Check spelling.")
            
            self.log_info("   - Submitting form...")
            body_element = driver.find_element(By.TAG_NAME, 'body')
            btn_proceed = wait.until(EC.presence_of_element_located((By.ID, "btnProceed")))
            driver.execute_script("arguments[0].click();", btn_proceed)
            
            try:
                WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert_text = alert.text
                alert.accept()
                self._log_result(inputs['panchayat'], item, "Failed", f"Server Alert: {alert_text}")
                return
            except TimeoutException: pass
            
            wait.until(EC.staleness_of(body_element))
            
            error_reason = self._check_for_page_errors(driver)
            if error_reason:
                self._log_result(inputs['panchayat'], item, "Skipped", error_reason)
                session_skip_list.add(full_work_code_text)
                return
            self.log_info("   - Muster Roll is valid. Generating output...")
            pdf_path = self._save_mr_as_pdf(driver, full_work_code_text, output_dir, inputs['orientation'], inputs['scale'])
            
            log_detail = f"Saved as {os.path.basename(pdf_path)}" if pdf_path else "PDF Save Failed"
            
            if pdf_path:
                self.current_session_files.append(pdf_path)
                if inputs.get('save_to_cloud'):
                    self.log_info("   - Uploading to cloud...")
                    if self._upload_to_cloud(pdf_path, inputs['panchayat']):
                        log_detail += " & Cloud Uploaded"
                    else:
                        log_detail += " (Cloud Failed)"

            if inputs['output_action'] == "Print" and pdf_path:
                self._print_file(pdf_path)

            self._log_result(inputs['panchayat'], item, "Success" if pdf_path else "Failed", log_detail)
            session_skip_list.add(full_work_code_text)

        except TimeoutException:
            self.log_error(f"Error on '{item}': Timeout (Slow Network)")
            self._log_result(inputs['panchayat'], item, "Failed", "Timeout - Slow Network")
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "Unknown Error"
            self.log_error(f"Error on '{item}': {error_msg}")
            self._log_result(inputs['panchayat'], item, "Failed", error_msg)

    def _save_mr_as_pdf(self, driver, full_work_code, output_dir, orientation, scale):
        try:
            safe_work_code = full_work_code.split('/')[-1][-6:]
            base_filename = safe_work_code
            extension = ".pdf"
            counter = 1
            pdf_filename = f"{base_filename}{extension}"
            save_path = os.path.join(output_dir, pdf_filename)

            while os.path.exists(save_path):
                pdf_filename = f"{base_filename} ({counter}){extension}"
                save_path = os.path.join(output_dir, pdf_filename)
                counter += 1

            is_landscape = (orientation == "Landscape")
            pdf_scale = scale / 100.0
            pdf_data_base64 = None

            # --- CSS for Orientation ---
            if is_landscape:
                self.log_info("   - Injecting CSS for landscape orientation...")
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
            self.log_info("   - Removing blank page elements...")
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

                self.log_info("   - Using Firefox's print command...")
                self.log_warning("   - Note: PDF Scale setting is ignored for Firefox.")
                pdf_data_base64 = driver.print_page()

            elif self.app.active_browser == 'chrome':
                self.log_info("   - Using Chrome's advanced print command (CDP)...")
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
                result = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                pdf_data_base64 = result['data']

            if pdf_data_base64:
                pdf_data = base64.b64decode(pdf_data_base64)
                with open(save_path, 'wb') as f:
                    f.write(pdf_data)
                return save_path
            else:
                self.log_error("Error: PDF data was not generated by the browser.")
                return None

        except Exception as e:
            self.log_error(f"Error saving PDF: {e}")
            return None

    def _select_work_code(self, driver, wait, item, is_auto_mode):
        """
        Selects the work code with Retry Logic to handle StaleElementExceptions.
        """
        work_code_dropdown_locator = (By.ID, "ddlWorkCode")
        
        for attempt in range(3): # Try 3 times
            try:
                if is_auto_mode:
                    # Auto Mode: Wait for options
                    wait.until(EC.presence_of_element_located(work_code_dropdown_locator))
                    wait.until(lambda d: len(Select(d.find_element(*work_code_dropdown_locator)).options) > 1)
                    
                    work_code_dropdown = Select(driver.find_element(*work_code_dropdown_locator))
                    
                    # Iterate to find matching text
                    found_option = next((opt for opt in work_code_dropdown.options if opt.text == item and opt.get_attribute("value")), None)

                    if found_option:
                        full_work_code_text = found_option.text
                        work_code_dropdown.select_by_visible_text(full_work_code_text)
                        self.log_info(f"   - Found and selected: {full_work_code_text}")
                        return full_work_code_text
                    else:
                        raise NoSuchElementException(f"Could not find a matching work for auto item '{item}'.")
                
                else:
                    # Manual Mode: Search box
                    search_key = item
                    search_box = wait.until(EC.presence_of_element_located((By.ID, "txtWork")))
                    driver.execute_script("arguments[0].value = arguments[1];", search_box, search_key)
                    
                    # Capture old dropdown to detect refresh
                    old_dropdown = driver.find_element(*work_code_dropdown_locator)
                    
                    search_btn = driver.find_element(By.ID, "imgButtonSearch")
                    driver.execute_script("arguments[0].click();", search_btn)
                    
                    # Wait for refresh
                    try: wait.until(EC.staleness_of(old_dropdown))
                    except TimeoutException: pass
                    
                    wait.until(EC.presence_of_element_located(work_code_dropdown_locator))
                    wait.until(lambda d: len(Select(d.find_element(*work_code_dropdown_locator)).options) > 1)
                    
                    work_code_dropdown = Select(driver.find_element(*work_code_dropdown_locator))
                    
                    found_option = next((opt for opt in work_code_dropdown.options if search_key in opt.text and opt.get_attribute("value")), None)
                    if found_option:
                        full_work_code_text = found_option.text
                        work_code_dropdown.select_by_visible_text(full_work_code_text)
                        self.log_info(f"   - Found and selected: {full_work_code_text}")
                        return full_work_code_text
                    else:
                        raise NoSuchElementException(f"Could not find a matching work for search key '{item}'.")
                        
            except StaleElementReferenceException:
                if attempt < 2:
                    self.log_warning("   - Stale element detected, retrying selection...")
                    time.sleep(2)
                    continue
                else:
                    raise
            except Exception as e:
                raise e

    def _check_for_page_errors(self, driver) -> str | None:
        """Checks for known error messages on the page. Returns the error string if found, else None."""
        page_source = driver.page_source.lower()
        if "geotag is not received" in page_source:
            return "Skipped: Geotag not received"
        if "greater than allowed limit" in page_source:
            return "Skipped: Greater than allowed limit"
        if "no worker available" in page_source:
            return "Skipped: No worker available"
        if "no muster roll available" in page_source:
            return "Skipped: No Muster Roll available"
        if "overlap that period" in page_source:
            return "Skipped: Date period overlaps with existing MR"
        return None

    def _log_result(self, panchayat, item_key, status, details):
        timestamp = datetime.now().strftime("%H:%M:%S")
        values = (timestamp, panchayat, item_key, status, details)
        
        # --- FIX: Explicit Success Tag ---
        # Previously only 'failed' was checked; now 'success' is also checked
        tags = ()
        if 'success' in status.lower():
            tags = ('success',)
        else:
            tags = ('failed',)

        if status == "Success":
            self.success_count += 1
            self.app.after(0, lambda: self.success_label.configure(text=f"Success: {self.success_count}"))
        else:
            self.skipped_count += 1
            self.app.after(0, lambda: self.skipped_label.configure(text=f"Skipped/Failed: {self.skipped_count}"))
        
        self.safe_tree_insert(values, tags)

    def _upload_to_cloud(self, file_path, location_panchayat):
        """Uploads a given file to the user's cloud storage via the API."""
        if not self.app.license_info.get('key'):
            self.log_warning("   - Cloud Upload Skipped: No license key found.")
            return False
            
        headers = {'Authorization': f"Bearer {self.app.license_info['key']}"}
        url = f"{config.LICENSE_SERVER_URL}/files/api/upload"
        filename = os.path.basename(file_path)

        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'application/pdf')}
                
                date_folder = datetime.now().strftime('%Y-%m-%d')
                safe_location_panchayat = "".join(c for c in location_panchayat if c.isalnum() or c in (' ', '_')).rstrip()
                
                relative_path = f'Muster_Rolls/{date_folder}/{safe_location_panchayat}/{filename}'
                
                data = {
                    'parent_id': '', 
                    'relative_path': relative_path
                }
                
                response = self.app.http_session.post(url, headers=headers, files=files, data=data, timeout=120)

            if response.status_code == 201:
                return True
            else:
                self.log_error(f"   - Cloud upload failed with status {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_error(f"   - A connection error occurred during cloud upload: {e}")
            return False
        except Exception as e:
            self.log_error(f"   - An unexpected error occurred during cloud upload: {e}")
            return False

    def export_report(self):
        self.export_treeview_to_excel(
            tree=self.results_tree,
            default_filename="muster_roll_gen_results.xlsx",
            filter_mode="Export All",
            title_prefix="Muster Roll Generation Report"
        )

    def _get_filtered_data_and_filepath(self, export_format):
        if not self.results_tree.get_children(): messagebox.showinfo(tr("dialogs.no_data"), tr("dialogs.no_results_to_export")); return None, None
        location_panchayat = self.panchayat_entry.get().strip()
        if not location_panchayat: messagebox.showwarning(tr("dialogs.input_needed"), tr("dialogs.panchayat_name_for_title")); return None, None
        
        filter_option = self.export_filter_menu.get()
        data_to_export = []
        for item_id in self.results_tree.get_children():
            row_values = self.results_tree.item(item_id)['values']
            status = row_values[3].upper() 
            if filter_option == "Export All": data_to_export.append(row_values)
            elif filter_option == "Success Only" and "SUCCESS" in status: data_to_export.append(row_values)
            elif filter_option == "Failed Only" and "SUCCESS" not in status: data_to_export.append(row_values)
        if not data_to_export: messagebox.showinfo(tr("dialogs.no_data"), tr("dialogs.no_records_for_filter", filter=filter_option)); return None, None

        safe_name = "".join(c for c in location_panchayat if c.isalnum() or c in (' ', '_')).rstrip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        details = {"Image (.jpg)": { "ext": ".jpg", "types": [("JPEG Image", "*.jpg")]}, "PDF (.pdf)": { "ext": ".pdf", "types": [("PDF Document", "*.pdf")]}}[export_format]
        filename = f"MR_Gen_Report_{safe_name}_{timestamp}{details['ext']}"
        file_path = filedialog.asksaveasfilename(defaultextension=details['ext'], filetypes=details['types'], initialdir=self.app.get_report_path("Muster Roll"), initialfile=filename, title=tr("common.save_report"))
        return (data_to_export, file_path) if file_path else (None, None)
    
    def _handle_pdf_export(self, data, headers, col_widths, file_path):
        title = f"Muster Roll Generation Report: {self.panchayat_entry.get().strip()}"
        report_date = datetime.now().strftime('%d %b %Y')
        success = self.generate_report_pdf(data, headers, col_widths, title, report_date, file_path)
        if success and messagebox.askyesno(tr("dialogs.success"), tr("dialogs.pdf_report_saved_open", path=file_path)):
            if sys.platform == "win32": os.startfile(file_path)
            else: subprocess.call(['open', file_path])

    # --- NEW MERGE PDFS METHOD ---
    def merge_saved_pdfs(self):
        self.log_info("Starting PDF merge...")        
        # Use ONLY the files generated in the current session
        pdf_files = self.current_session_files
        
        if not pdf_files:
            self.log_warning("No PDFs generated in this session to merge.")
            messagebox.showinfo(tr("dialogs.no_files"), tr("dialogs.no_mrs_generated_cycle"), parent=self)
            return
            
        self.log_info(f"Merging {len(pdf_files)} files generated in this session.")
        # Get output file name from user
        dialog = ctk.CTkInputDialog(text=tr("common.merge_base_name"), title=tr("common.merge_pdfs"))
        base_name = dialog.get_input()
        
        if not base_name:
            self.log_info("Merge cancelled by user.")
            return

        # Get unique output path
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

        # Run merge in a separate thread
        self.app.start_automation_thread(
            "pdf_merger_mr", 
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