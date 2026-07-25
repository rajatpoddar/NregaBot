# tabs/material_entry_tab.py
import json
import os
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import time
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    UnexpectedAlertPresentException, StaleElementReferenceException,
    ElementNotInteractableException, WebDriverException
)

from src import config
from .base_tab import BaseAutomationTab
from .autocomplete_widget import AutocompleteEntry
from typing import Any, Callable, Dict, List, Optional, Tuple

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "..", "assets", "material_profiles.json")
MAX_MATERIAL_ROWS = 15
DEFAULT_MATERIAL_ROWS = 2


class MaterialEntryTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="material_entry")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.materials_ui = []
        self._profiles = self._load_profiles()
        self.lbl_total_amount = None
        self.lbl_total_gst = None
        self.lbl_grand_total = None
        self._create_widgets()

    # =========================================================================
    # PROFILE MANAGEMENT
    # =========================================================================

    def _load_profiles(self):
        try:
            if os.path.exists(PROFILES_FILE):
                with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_profiles(self):
        try:
            os.makedirs(os.path.dirname(PROFILES_FILE), exist_ok=True)
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Profile Error", f"Could not save profiles:\n{e}", parent=self)

    def _get_profile_names(self):
        return list(self._profiles.keys()) if self._profiles else []

    def _save_current_as_profile(self):
        name = self.profile_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Profile Name", "Please enter a profile name.", parent=self)
            return
        materials = []
        for mat in self.materials_ui:
            n = mat["name"].get().strip()
            if n:
                materials.append({
                    "name": n,
                    "rate": mat["rate"].get().strip(),
                    "qty": mat["qty"].get().strip(),
                    "gst": mat["gst"].get()
                })
        if not materials:
            messagebox.showwarning("No Data", "Fill at least one material row before saving.", parent=self)
            return
        self._profiles[name] = materials
        self._save_profiles()
        self._refresh_profile_menu()
        self.profile_var.set(name)
        messagebox.showinfo("Saved", f"Profile '{name}' saved successfully.", parent=self)

    def _load_selected_profile(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import UnexpectedAlertPresentException
        from selenium.common.exceptions import ElementNotInteractableException
        from selenium.common.exceptions import WebDriverException
        from selenium import webdriver
        name = self.profile_var.get()
        if not name or name not in self._profiles:
            messagebox.showwarning("No Profile", "Select a valid profile to load.", parent=self)
            return
        materials = self._profiles[name]
        # Ensure enough rows exist
        needed = len(materials)
        while len(self.materials_ui) < needed:
            self._add_material_row()
        # Fill rows
        for i, mat in enumerate(materials):
            self.materials_ui[i]["name"].delete(0, "end")
            self.materials_ui[i]["name"].insert(0, mat.get("name", ""))
            self.materials_ui[i]["rate"].delete(0, "end")
            self.materials_ui[i]["rate"].insert(0, mat.get("rate", ""))
            self.materials_ui[i]["qty"].delete(0, "end")
            self.materials_ui[i]["qty"].insert(0, mat.get("qty", ""))
            self.materials_ui[i]["gst"].set(mat.get("gst", "0"))
        # Clear extra rows beyond profile
        for i in range(needed, len(self.materials_ui)):
            self.materials_ui[i]["name"].delete(0, "end")
            self.materials_ui[i]["rate"].delete(0, "end")
            self.materials_ui[i]["qty"].delete(0, "end")
            self.materials_ui[i]["gst"].set("0")

    def _delete_selected_profile(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import UnexpectedAlertPresentException
        from selenium.common.exceptions import ElementNotInteractableException
        from selenium.common.exceptions import WebDriverException
        from selenium import webdriver
        name = self.profile_var.get()
        if not name or name not in self._profiles:
            messagebox.showwarning("No Profile", "Select a valid profile to delete.", parent=self)
            return
        if messagebox.askyesno("Delete Profile", f"Delete profile '{name}'?", parent=self):
            del self._profiles[name]
            self._save_profiles()
            self._refresh_profile_menu()
            self.profile_var.set("")

    def _refresh_profile_menu(self):
        names = self._get_profile_names()
        self.profile_menu.configure(values=names if names else [""])


    # =========================================================================
    # UI CREATION
    # =========================================================================
    def _create_widgets(self) -> None:
        # Outer scrollable container
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import UnexpectedAlertPresentException
        from selenium.common.exceptions import ElementNotInteractableException
        from selenium.common.exceptions import WebDriverException
        from selenium import webdriver
        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        outer.grid_columnconfigure(0, weight=1)

        # --- General Details ---
        input_frame = ctk.CTkFrame(outer)
        input_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        input_frame.grid_columnconfigure(1, weight=1)
        input_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(input_frame, text="Panchayat (For Block Login):").grid(row=0, column=0, padx=15, pady=5, sticky="w")
        self.panchayat_entry = AutocompleteEntry(
            input_frame,
            placeholder_text="Leave blank for GP Login",
            suggestions_list=self.app.history_manager.get_suggestions("panchayat_name"),
            app_instance=self.app,
            history_key="panchayat_name"
        )
        self.panchayat_entry.grid(row=0, column=1, columnspan=3, padx=15, pady=5, sticky="ew")

        ctk.CTkLabel(input_frame, text="Work Category:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        work_category_options = [
            "Anganwadi/Other Rural Infrastructure", "Coastal Areas", "Drought Proofing", "Rural Drinking Water",
            "Food Grain", "Flood Control and Protection", "Fisheries", "Micro Irrigation Works",
            "Provision of Irrigation facility to Land Owned by SC/ST/LR or IAY Beneficiaries/Small or Marginal Farmers",
            "Land Development", "Other Works", "Play Ground", "Rural Connectivity", "Rural Sanitation",
            "Bharat Nirman Sewa Kendra", "Water Conservation and Water Harvesting", "Renovation of traditional water bodies"
        ]
        self.work_category_var = ctk.StringVar(value=work_category_options[8])
        self.work_category_menu = ctk.CTkOptionMenu(input_frame, variable=self.work_category_var, values=work_category_options, dynamic_resizing=False)
        self.work_category_menu.grid(row=1, column=1, columnspan=3, padx=15, pady=5, sticky="ew")

        ctk.CTkLabel(input_frame, text="Vendor Code:").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.vendor_code_entry = ctk.CTkEntry(input_frame, placeholder_text="e.g., 6430")
        self.vendor_code_entry.grid(row=2, column=1, padx=15, pady=5, sticky="ew")

        ctk.CTkLabel(input_frame, text="Bill Date (DD/MM/YYYY):").grid(row=2, column=2, padx=15, pady=5, sticky="w")
        date_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        date_frame.grid(row=2, column=3, sticky="ew", padx=15, pady=5)
        self.bill_date_entry = ctk.CTkEntry(date_frame, placeholder_text="DD/MM/YYYY")
        self.bill_date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(date_frame, text="📅", width=35, fg_color=("gray85", "gray25"), text_color=("black", "white"),
                      command=lambda: self.open_date_picker(lambda d: [self.bill_date_entry.delete(0, "end"), self.bill_date_entry.insert(0, d)])).pack(side="right", padx=(5, 0))

        # --- Profile System ---
        profile_frame = ctk.CTkFrame(outer)
        profile_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        profile_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(profile_frame, text="Material Profiles:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=8, sticky="w")

        self.profile_var = ctk.StringVar(value="")
        profile_names = self._get_profile_names()
        self.profile_menu = ctk.CTkOptionMenu(profile_frame, variable=self.profile_var,
                                               values=profile_names if profile_names else [""],
                                               dynamic_resizing=False, width=200)
        self.profile_menu.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        ctk.CTkButton(profile_frame, text="Load Profile", width=110,
                      fg_color="#2563EB", hover_color="#1D4ED8",
                      command=self._load_selected_profile).grid(row=0, column=2, padx=5, pady=8)

        ctk.CTkLabel(profile_frame, text="Save As:").grid(row=0, column=3, padx=(15, 5), pady=8, sticky="w")
        self.profile_name_entry = ctk.CTkEntry(profile_frame, placeholder_text="Profile name", width=140)
        self.profile_name_entry.grid(row=0, column=4, padx=5, pady=8)

        ctk.CTkButton(profile_frame, text="💾 Save Profile", width=110,
                      fg_color="#059669", hover_color="#047857",
                      command=self._save_current_as_profile).grid(row=0, column=5, padx=5, pady=8)

        ctk.CTkButton(profile_frame, text="🗑 Delete", width=80,
                      fg_color="#DC2626", hover_color="#B91C1C",
                      command=self._delete_selected_profile).grid(row=0, column=6, padx=5, pady=8)

        # --- Material Details ---
        mat_outer = ctk.CTkFrame(outer)
        mat_outer.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        mat_outer.grid_columnconfigure(0, weight=1)

        mat_header = ctk.CTkFrame(mat_outer, fg_color="transparent")
        mat_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkLabel(mat_header, text="Material Details", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.row_count_label = ctk.CTkLabel(mat_header, text=f"(Rows: {DEFAULT_MATERIAL_ROWS} / {MAX_MATERIAL_ROWS})", text_color="gray60")
        self.row_count_label.pack(side="left", padx=8)
        ctk.CTkButton(mat_header, text="+ Add Row", width=90, height=28,
                      fg_color="#059669", hover_color="#047857",
                      command=self._add_material_row).pack(side="right", padx=5)
        ctk.CTkButton(mat_header, text="- Remove Row", width=100, height=28,
                      fg_color="#DC2626", hover_color="#B91C1C",
                      command=self._remove_material_row).pack(side="right", padx=5)

        # Column headers
        col_header_frame = ctk.CTkFrame(mat_outer, fg_color="transparent")
        col_header_frame.grid(row=1, column=0, sticky="ew", padx=10)
        for col_idx, (text, w) in enumerate([("Material Name (from Site)", 200), ("Unit Price", 110), ("Quantity", 110), ("GST Slab (%)", 100)]):
            ctk.CTkLabel(col_header_frame, text=text, text_color="gray60", width=w, anchor="w").grid(row=0, column=col_idx, padx=5, pady=2, sticky="w")

        # Scrollable rows container
        self.mat_scroll_frame = ctk.CTkScrollableFrame(mat_outer, height=180, fg_color="transparent")
        self.mat_scroll_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.mat_scroll_frame.grid_columnconfigure(0, weight=1)

        # Add default rows
        for _ in range(DEFAULT_MATERIAL_ROWS):
            self._add_material_row()

        # --- Totals Summary ---
        totals_frame = ctk.CTkFrame(mat_outer, fg_color=("gray90", "gray20"))
        totals_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 8))

        self.lbl_total_amount = ctk.CTkLabel(totals_frame, text="Amount: ₹0.00", anchor="center")
        self.lbl_total_amount.pack(side="left", expand=True, padx=10, pady=6)

        ctk.CTkFrame(totals_frame, width=1, height=20, fg_color="gray50").pack(side="left", pady=6)

        self.lbl_total_gst = ctk.CTkLabel(totals_frame, text="GST: ₹0.00", anchor="center")
        self.lbl_total_gst.pack(side="left", expand=True, padx=10, pady=6)

        ctk.CTkFrame(totals_frame, width=1, height=20, fg_color="gray50").pack(side="left", pady=6)

        self.lbl_grand_total = ctk.CTkLabel(totals_frame, text="Grand Total: ₹0.00",
                                             font=ctk.CTkFont(weight="bold"), anchor="center")
        self.lbl_grand_total.pack(side="left", expand=True, padx=10, pady=6)

        # --- Action Buttons ---
        action_frame = self._create_action_buttons(outer)
        action_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)

        # --- Notebook ---
        notebook = ctk.CTkTabview(outer)
        notebook.grid(row=4, column=0, sticky="nsew", padx=5, pady=5)
        outer.grid_rowconfigure(4, weight=1)

        # Work Key Input Tab
        batch_tab = notebook.add("Input: Work Key & Bill No")
        batch_tab.grid_columnconfigure(0, weight=1)
        batch_tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(batch_tab, text="Format: WorkSearchKey, BillNumber (One per line)\nExample: 25554, 855").grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))
        # Textbox with scrollbar
        wk_frame = ctk.CTkFrame(batch_tab, fg_color="transparent")
        wk_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        wk_frame.grid_columnconfigure(0, weight=1)
        wk_frame.grid_rowconfigure(0, weight=1)
        self.batch_textbox = ctk.CTkTextbox(wk_frame, height=120, wrap="none")
        self.batch_textbox.grid(row=0, column=0, sticky="nsew")
        wk_scroll_y = ctk.CTkScrollbar(wk_frame, command=self.batch_textbox.yview)
        wk_scroll_y.grid(row=0, column=1, sticky="ns")
        wk_scroll_x = ctk.CTkScrollbar(wk_frame, orientation="horizontal", command=self.batch_textbox.xview)
        wk_scroll_x.grid(row=1, column=0, sticky="ew")
        self.batch_textbox.configure(yscrollcommand=wk_scroll_y.set, xscrollcommand=wk_scroll_x.set)

        # Results Tab
        results_tab = notebook.add("Results")
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(0, weight=1)

        res_btn_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        res_btn_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        ctk.CTkButton(res_btn_frame, text="📤 Export CSV", width=110,
                      fg_color="#7C3AED", hover_color="#6D28D9",
                      command=lambda: self.export_treeview_to_csv(self.results_tree, "material_entry_results.csv")
                      ).pack(side="right")
        ctk.CTkButton(res_btn_frame, text="🗑 Clear", width=80,
                      fg_color=("gray70", "gray30"),
                      command=lambda: [self.results_tree.delete(i) for i in self.results_tree.get_children()]
                      ).pack(side="right", padx=5)

        res_tree_frame = ctk.CTkFrame(results_tab, fg_color="transparent")
        res_tree_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        results_tab.grid_rowconfigure(1, weight=1)
        res_tree_frame.grid_columnconfigure(0, weight=1)
        res_tree_frame.grid_rowconfigure(0, weight=1)

        cols = ("Timestamp", "Work Key", "Bill No", "Status", "Details")
        self.results_tree = ttk.Treeview(res_tree_frame, columns=cols, show='headings')
        for col in cols:
            self.results_tree.heading(col, text=col)
        self.results_tree.column("Timestamp", width=80, anchor="center")
        self.results_tree.column("Work Key", width=120)
        self.results_tree.column("Bill No", width=80)
        self.results_tree.column("Status", width=100, anchor="center")
        self.results_tree.column("Details", width=300)
        self.results_tree.grid(row=0, column=0, sticky="nsew")

        res_scroll_y = ctk.CTkScrollbar(res_tree_frame, command=self.results_tree.yview)
        res_scroll_y.grid(row=0, column=1, sticky="ns")
        res_scroll_x = ctk.CTkScrollbar(res_tree_frame, orientation="horizontal", command=self.results_tree.xview)
        res_scroll_x.grid(row=1, column=0, sticky="ew")
        self.results_tree.configure(yscrollcommand=res_scroll_y.set, xscrollcommand=res_scroll_x.set)
        self.style_treeview(self.results_tree)

        # Logs & Status Tab
        self._create_log_and_status_area(notebook)


    # =========================================================================
    # DYNAMIC MATERIAL ROWS
    # =========================================================================

    def _add_material_row(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import UnexpectedAlertPresentException
        from selenium.common.exceptions import ElementNotInteractableException
        from selenium.common.exceptions import WebDriverException
        from selenium import webdriver
        if len(self.materials_ui) >= MAX_MATERIAL_ROWS:
            messagebox.showwarning("Limit Reached", f"Maximum {MAX_MATERIAL_ROWS} rows allowed.", parent=self)
            return

        row_idx = len(self.materials_ui)
        row_frame = ctk.CTkFrame(self.mat_scroll_frame, fg_color="transparent")
        row_frame.grid(row=row_idx, column=0, sticky="ew", pady=2)
        row_frame.grid_columnconfigure(0, weight=1)

        name_ent = ctk.CTkEntry(row_frame, width=200, placeholder_text=f"Material {row_idx + 1}", height=30)
        name_ent.grid(row=0, column=0, padx=5, sticky="ew")

        rate_ent = ctk.CTkEntry(row_frame, width=110, placeholder_text="Rate", height=30)
        rate_ent.grid(row=0, column=1, padx=5)

        qty_ent = ctk.CTkEntry(row_frame, width=110, placeholder_text="Qty", height=30)
        qty_ent.grid(row=0, column=2, padx=5)

        gst_var = ctk.StringVar(value="0")
        gst_menu = ctk.CTkOptionMenu(row_frame, variable=gst_var, values=["0", "5", "6", "12", "18", "28"],
                                     width=100, height=30, command=lambda _: self._recalculate_totals())
        gst_menu.grid(row=0, column=3, padx=5)

        # Trace rate and qty for live total updates
        rate_ent.bind("<KeyRelease>", lambda e: self._recalculate_totals())
        qty_ent.bind("<KeyRelease>", lambda e: self._recalculate_totals())

        self.materials_ui.append({"name": name_ent, "rate": rate_ent, "qty": qty_ent, "gst": gst_var, "frame": row_frame})
        self._update_row_count_label()
        self._recalculate_totals()

    def _remove_material_row(self):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import UnexpectedAlertPresentException
        from selenium.common.exceptions import ElementNotInteractableException
        from selenium.common.exceptions import WebDriverException
        from selenium import webdriver
        if len(self.materials_ui) <= 1:
            messagebox.showwarning("Cannot Remove", "At least one material row must remain.", parent=self)
            return
        last = self.materials_ui.pop()
        last["frame"].destroy()
        self._update_row_count_label()
        self._recalculate_totals()

    def _recalculate_totals(self):
        if self.lbl_total_amount is None:
            return
        total_amount = 0.0
        total_gst = 0.0
        for mat in self.materials_ui:
            try:
                rate = float(mat["rate"].get().strip() or 0)
                qty = float(mat["qty"].get().strip() or 0)
                gst_pct = float(mat["gst"].get() or 0)
                base = rate * qty
                gst_amt = base * gst_pct / 100
                total_amount += base
                total_gst += gst_amt
            except ValueError:
                pass
        grand_total = total_amount + total_gst
        self.lbl_total_amount.configure(text=f"Amount: ₹{total_amount:,.2f}")
        self.lbl_total_gst.configure(text=f"GST: ₹{total_gst:,.2f}")
        self.lbl_grand_total.configure(text=f"Grand Total: ₹{grand_total:,.2f}")

    def _update_row_count_label(self):
        self.row_count_label.configure(text=f"(Rows: {len(self.materials_ui)} / {MAX_MATERIAL_ROWS})")

    # =========================================================================
    # AUTOMATION LOGIC
    # =========================================================================

    def _get_inputs(self):
        materials = []
        for mat in self.materials_ui:
            name = mat["name"].get().strip()
            if name:
                materials.append({
                    "name": name,
                    "rate": mat["rate"].get().strip(),
                    "qty": mat["qty"].get().strip(),
                    "gst": mat["gst"].get()
                })

        raw_batch = self.batch_textbox.get("1.0", "end").strip().splitlines()
        tasks = []
        for line in raw_batch:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                tasks.append({"work_key": parts[0], "bill_no": parts[1]})

        return {
            "panchayat": self.panchayat_entry.get().strip(),
            "work_category": self.work_category_var.get(),
            "vendor_code": self.vendor_code_entry.get().strip(),
            "bill_date": self.bill_date_entry.get().strip(),
            "materials": materials,
            "tasks": tasks
        }
    def start_automation(self) -> None:
        inputs = self._get_inputs()
        if not inputs["vendor_code"] or not inputs["bill_date"] or not inputs["tasks"]:
            messagebox.showwarning("Missing Input", "Vendor Code, Bill Date, and at least one Work Key/Bill No pair are required.", parent=self)
            return
        if not inputs["materials"]:
            messagebox.showwarning("Missing Material", "Please fill at least one material row.", parent=self)
            return
        self.app.start_automation_thread(self.automation_key, self.run_automation_logic, args=(inputs,))

    def run_automation_logic(self, inputs):
        # ---- Lazy imports ----
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
        from selenium.webdriver.common.keys import Keys
        from selenium.common.exceptions import UnexpectedAlertPresentException
        from selenium.common.exceptions import ElementNotInteractableException
        from selenium.common.exceptions import WebDriverException
        from selenium import webdriver
        self.app.after(0, self.set_common_ui_state, True)
        self.app.clear_log(self.log_display)

        driver = self.app.get_driver()
        if not driver:
            self.app.after(0, self.set_common_ui_state, False)
            return

        wait = WebDriverWait(driver, 15)
        total_tasks = len(inputs["tasks"])
        success_count = 0
        fail_count = 0

        try:
            for i, task in enumerate(inputs["tasks"]):
                if self.app.stop_events[self.automation_key].is_set():
                    self.app.log_message(self.log_display, "\n⚠ Automation stopped by user.", "warning")
                    break

                work_key = task['work_key']
                bill_no = task['bill_no']
                self.update_status(f"Processing {work_key} (Bill {bill_no})", (i + 1) / total_tasks)
                self.app.log_message(self.log_display, f"\n{'=' * 60}\n▶ Processing Work Key: {work_key} | Bill: {bill_no}\n{'=' * 60}")

                try:
                    driver.get(config.MATERIAL_ENTRY_CONFIG["url"])
                    # Wait for page to fully load before interacting
                    wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlworkcategory")))
                    time.sleep(1.5)  # Brief wait for postback to begin

                    # 1. Panchayat (Block Login)
                    if inputs['panchayat']:
                        try:
                            panchayat_dd = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlpanchayat_code")))
                            Select(panchayat_dd).select_by_visible_text(inputs['panchayat'])
                            self.app.log_message(self.log_display, f"✓ Panchayat selected: {inputs['panchayat']}")
                            time.sleep(1.5)  # Brief wait for postback to begin
                        except TimeoutException:
                            self.app.log_message(self.log_display, "ℹ Panchayat dropdown not found (GP login assumed)")

                    # 2. Work Category — re-fetch after panchayat postback to avoid stale
                    self.app.log_message(self.log_display, "▶ Selecting Work Category...")
                    for attempt in range(3):
                        try:
                            cat_dd_el = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlworkcategory")))
                            wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_ddlworkcategory")))
                            Select(cat_dd_el).select_by_visible_text(inputs['work_category'])
                            self.app.log_message(self.log_display, f"✓ Category: {inputs['work_category']}")
                            break
                        except StaleElementReferenceException:
                            if attempt == 2:
                                raise
                            time.sleep(1.5)  # Brief wait for postback to begin
                    time.sleep(1.5)  # Brief wait for postback to begin

                    # 3. Work Code Search
                    self.app.log_message(self.log_display, f"▶ Searching Work Key: {work_key}...")
                    for attempt in range(3):
                        try:
                            search_wk = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtwrksearchkey")))
                            search_wk.clear()
                            search_wk.send_keys(work_key)
                            search_wk.send_keys(Keys.TAB)
                            break
                        except StaleElementReferenceException:
                            if attempt == 2:
                                raise
                            time.sleep(1.5)  # Brief wait for postback to begin
                    time.sleep(1.5)  # Brief wait for postback to begin

                    # Re-fetch dropdown fresh after postback
                    found_wc = False
                    for attempt in range(3):
                        try:
                            wc_dd_el = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlWork_code")))
                            wc_dd = Select(wc_dd_el)
                            for opt in wc_dd.options:
                                if work_key in opt.text:
                                    wc_dd.select_by_visible_text(opt.text)
                                    self.app.log_message(self.log_display, f"✓ Work code selected: {opt.text}")
                                    found_wc = True
                                    break
                            break
                        except StaleElementReferenceException:
                            if attempt == 2:
                                raise
                            time.sleep(1)

                    if not found_wc:
                        self._log_result(work_key, bill_no, "Failed", "Work code not found in dropdown")
                        fail_count += 1
                        continue
                    time.sleep(1.5)  # Brief wait for postback to begin

                    # 4. Vendor Code
                    self.app.log_message(self.log_display, f"▶ Searching Vendor: {inputs['vendor_code']}...")
                    for attempt in range(3):
                        try:
                            vendor_txt = wait.until(EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txttinsearch")))
                            vendor_txt.clear()
                            vendor_txt.send_keys(inputs['vendor_code'])
                            vendor_txt.send_keys(Keys.TAB)
                            break
                        except StaleElementReferenceException:
                            if attempt == 2:
                                raise
                            time.sleep(1.5)  # Brief wait for postback to begin
                    time.sleep(1.5)  # Brief wait for postback to begin

                    vendor_found = False
                    for attempt in range(3):
                        try:
                            vendor_dd = Select(wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlVendor"))))
                            if len(vendor_dd.options) > 1:
                                vendor_dd.select_by_index(1)
                                self.app.log_message(self.log_display, f"✓ Vendor selected: {vendor_dd.first_selected_option.text}")
                                vendor_found = True
                            break
                        except StaleElementReferenceException:
                            if attempt == 2:
                                raise
                            time.sleep(1.5)  # Brief wait for postback to begin
                    if not vendor_found:
                        self._log_result(work_key, bill_no, "Failed", "Vendor not found after search")
                        fail_count += 1
                        continue
                    time.sleep(1.5)  # Brief wait for postback to begin

                    # 5. Bill Details
                    self.app.log_message(self.log_display, "▶ Entering Bill Details...")
                    bill_input = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtBill_no")
                    bill_input.clear()
                    bill_input.send_keys(bill_no)

                    date_input = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtBilldate")
                    date_input.clear()
                    date_input.send_keys(inputs['bill_date'])
                    date_input.send_keys(Keys.TAB)
                    self.app.log_message(self.log_display, f"✓ Bill No: {bill_no}, Date: {inputs['bill_date']}")
                    time.sleep(1.5)  # Brief wait for postback to begin

                    # 6. Fill Materials
                    self.app.log_message(self.log_display, "▶ Filling Materials...")
                    filled_count = 0
                    for mat in inputs['materials']:
                        try:
                            xpath = f"//table[@id='ctl00_ContentPlaceHolder1_gvData']//tr[.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{mat['name'].lower()}')]]"
                            mat_row = driver.find_element(By.XPATH, xpath)

                            rate_input = mat_row.find_element(By.XPATH, ".//input[contains(@id, '_Rate')]")
                            rate_input.clear()
                            rate_input.send_keys(mat['rate'])
                            rate_input.send_keys(Keys.TAB)

                            qty_input = mat_row.find_element(By.XPATH, ".//input[contains(@id, '_Quantity')]")
                            qty_input.clear()
                            qty_input.send_keys(mat['qty'])
                            qty_input.send_keys(Keys.TAB)

                            gst_dd = Select(mat_row.find_element(By.XPATH, ".//select[contains(@id, '_gst_slab')]"))
                            gst_dd.select_by_visible_text(mat['gst'])

                            self.app.log_message(self.log_display, f"  ✓ {mat['name']}: Rate={mat['rate']}, Qty={mat['qty']}, GST={mat['gst']}%")
                            filled_count += 1
                        except NoSuchElementException:
                            self.app.log_message(self.log_display, f"  ⚠ Material '{mat['name']}' not found in table", "warning")
                        except (StaleElementReferenceException, ElementNotInteractableException) as e:
                            self.app.log_message(self.log_display, f"  ⚠ Error filling '{mat['name']}': {str(e)}", "warning")

                    if filled_count == 0:
                        self._log_result(work_key, bill_no, "Failed", "No materials could be filled")
                        fail_count += 1
                        continue

                    time.sleep(1.5)  # Brief wait for postback to begin

                    # 7. Checkbox & Submit
                    self.app.log_message(self.log_display, "▶ Confirming and Saving...")
                    checkbox = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_CheckBox1")
                    if not checkbox.is_selected():
                        driver.execute_script("arguments[0].click();", checkbox)

                    submit_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_cmdProceed")
                    driver.execute_script("arguments[0].click();", submit_btn)
                    time.sleep(2.0)  # Short wait after click

                    # 8. Handle Alerts
                    try:
                        alert = WebDriverWait(driver, 3).until(EC.alert_is_present())
                        alert_text = alert.text
                        alert.accept()
                        self.app.log_message(self.log_display, f"ℹ Alert: {alert_text}", "warning")
                    except TimeoutException:
                        pass

                    # 9. Check Success
                    try:
                        success_msg = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_lblMsg"))).text
                        if "successfully" in success_msg.lower() or "saved" in success_msg.lower():
                            self.app.log_message(self.log_display, f"✅ SUCCESS: {success_msg}")
                            self._log_result(work_key, bill_no, "Success", success_msg)
                            success_count += 1
                        else:
                            self.app.log_message(self.log_display, f"⚠ Unexpected message: {success_msg}", "warning")
                            self._log_result(work_key, bill_no, "Warning", success_msg)
                    except TimeoutException:
                        self.app.log_message(self.log_display, "⚠ Could not verify success message", "warning")
                        self._log_result(work_key, bill_no, "Unknown", "No confirmation message found")

                except TimeoutException as e:
                    error_msg = f"Timeout: Element not found - {str(e)}"
                    self.app.log_message(self.log_display, f"❌ {error_msg}", "error")
                    self._log_result(work_key, bill_no, "Failed", error_msg)
                    fail_count += 1
                except NoSuchElementException as e:
                    error_msg = f"Element not found: {str(e)}"
                    self.app.log_message(self.log_display, f"❌ {error_msg}", "error")
                    self._log_result(work_key, bill_no, "Failed", error_msg)
                    fail_count += 1
                except WebDriverException as e:
                    error_msg = f"WebDriver error: {str(e)}"
                    self.app.log_message(self.log_display, f"❌ {error_msg}", "error")
                    self._log_result(work_key, bill_no, "Failed", error_msg)
                    fail_count += 1
                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    self.app.log_message(self.log_display, f"❌ {error_msg}", "error")
                    self._log_result(work_key, bill_no, "Failed", error_msg)
                    fail_count += 1

        except Exception as e:
            self.handle_error(e)

        finally:
            self.app.after(0, self.set_common_ui_state, False)
            self.update_status("Task Finished", 1.0)
            summary = f"Material Entry Automation Complete!\n\n✅ Success: {success_count}\n❌ Failed: {fail_count}\n📊 Total: {total_tasks}"
            self.app.log_message(self.log_display, f"\n{'=' * 60}\n{summary}\n{'=' * 60}")
            messagebox.showinfo("Complete", summary, parent=self)

    def _log_result(self, work_key, bill_no, status, details):
        ts = datetime.now().strftime("%H:%M:%S")
        tags = ('success',) if 'success' in status.lower() else ('failed',) if 'failed' in status.lower() else ()
        self.app.after(0, lambda: self.results_tree.insert("", "end", values=(ts, work_key, bill_no, status, details), tags=tags))
    def reset_ui(self) -> None:
        super().reset_ui()
        self.vendor_code_entry.delete(0, "end")
        self.bill_date_entry.delete(0, "end")
        self.batch_textbox.delete("1.0", "end")
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        for mat in self.materials_ui:
            mat["name"].delete(0, "end")
            mat["rate"].delete(0, "end")
            mat["qty"].delete(0, "end")
            mat["gst"].set("0")
