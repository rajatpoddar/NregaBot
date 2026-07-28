import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os
import threading
import time
from datetime import datetime
from .base_tab import BaseAutomationTab
from typing import Any, Callable, Dict, List, Optional, Tuple

class MacroManagerTab(BaseAutomationTab):
    def __init__(self, parent: Any, app_instance: Any) -> None:
        super().__init__(parent, app_instance, automation_key="macro")
        self.queue_items = [] 
        # Stores specific inputs for bulk demand
        self.bulk_inputs = {} 
        self._create_widgets()
    def _create_widgets(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- 1. Control Panel ---
        control_frame = ctk.CTkFrame(self)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        control_frame.grid_columnconfigure(1, weight=1)

        # Task Selector
        ctk.CTkLabel(control_frame, text="Select Task Type:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.task_type_menu = ctk.CTkOptionMenu(
            control_frame, 
            values=[
                "Bulk Demand (CSV)",  # <--- New Option
                "Wagelist Gen + Auto Send",
                "MR Tracking -> MR Payment",
                "MR Tracking -> eMB Entry",
                "MR Tracking -> Zero MR",
                "Verify Job Card",
                "Verify ABPS",
                "Generate MR"
            ],
            command=self._update_input_fields, # Calls the dynamic updater
            width=280
        )
        self.task_type_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # --- Dynamic Input Area ---
        # Ye frame alag alag inputs dikhayega based on selection
        self.input_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        self.input_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=0, pady=0)
        
        # Initialize with default inputs
        self._update_input_fields("Bulk Demand (CSV)")

        # Instructions Label (Static)
        self.instruction_label = ctk.CTkLabel(control_frame, text="Tip: Ensure 'State/Block' are selected.", text_color="gray60", font=ctk.CTkFont(size=11))
        self.instruction_label.grid(row=2, column=1, sticky="w", padx=10, pady=(0,10))

        # --- 2. Action Buttons ---
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.start_btn = ctk.CTkButton(action_frame, text="▶ Run Macro Queue", fg_color="#2E7D32", hover_color="#1B5E20", height=40, font=ctk.CTkFont(size=14, weight="bold"), command=self.start_macro)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=5)
        
        self.stop_btn = ctk.CTkButton(action_frame, text="⏹ Stop", fg_color="#C62828", hover_color="#B91C1C", height=40, state="disabled", command=self.stop_automation)
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=5)

        # --- 3. Queue & Logs Notebook ---
        self.notebook = ctk.CTkTabview(self)
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        queue_tab = self.notebook.add("Execution Queue")
        self._create_log_and_status_area(parent_notebook=self.notebook)
        
        # --- Queue UI Setup ---
        queue_tab.grid_columnconfigure(0, weight=1)
        queue_tab.grid_rowconfigure(0, weight=1)

        cols = ("ID", "Task Type", "Target", "Status", "Message")
        self.queue_tree = ttk.Treeview(queue_tab, columns=cols, show='headings', selectmode="browse")
        
        self.queue_tree.column("ID", width=40, anchor="center")
        self.queue_tree.column("Task Type", width=220)
        self.queue_tree.column("Target", width=150)
        self.queue_tree.column("Status", width=100, anchor="center")
        self.queue_tree.column("Message", width=300)
        
        for col in cols: self.queue_tree.heading(col, text=col)

        self.queue_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        sb = ctk.CTkScrollbar(queue_tab, command=self.queue_tree.yview)
        sb.grid(row=0, column=1, sticky="ns", pady=5)
        self.queue_tree.configure(yscroll=sb.set)
        
        self.style_treeview(self.queue_tree)
        self.queue_tree.tag_configure('Pending', font=('Segoe UI', 10)) 
        self.queue_tree.tag_configure('Running', background='#E3F2FD', foreground='#0D47A1')
        self.queue_tree.tag_configure('Success', background='#E8F5E9', foreground='#1B5E20')
        self.queue_tree.tag_configure('Failed', background='#FFEBEE', foreground='#B71C1C')

    def _update_input_fields(self, choice):
        """
        Dropdown change hone par inputs ko badalta hai.
        """
        # Clear existing widgets in input_frame
        for widget in self.input_frame.winfo_children():
            widget.destroy()

        self.bulk_inputs = {} # Clear refs
        self.target_entry = None # Reset standard entry ref

        if choice == "Bulk Demand (CSV)":
            # --- UI For Bulk Demand ---
            ctk.CTkLabel(self.input_frame, text="Panchayat Name:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
            
            p_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
            p_var = ctk.StringVar()
            p_entry = ctk.CTkOptionMenu(self.input_frame, variable=p_var, values=p_vals, width=200)
            p_entry.grid(row=0, column=1, padx=10, pady=5, sticky="w")
            self.bulk_inputs['panchayat'] = p_entry
            self.bulk_inputs['panchayat_var'] = p_var

            ctk.CTkLabel(self.input_frame, text="Select CSV File:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
            
            f_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
            f_frame.grid(row=1, column=1, padx=10, pady=5, sticky="w")
            
            f_entry = ctk.CTkEntry(f_frame, width=150)
            f_entry.pack(side="left")
            self.bulk_inputs['filepath'] = f_entry

            def browse_file():
                path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
                if path:
                    f_entry.delete(0, "end")
                    f_entry.insert(0, path)

            ctk.CTkButton(f_frame, text="Browse", width=50, command=browse_file).pack(side="left", padx=5)
            
            # Add Button specifically for Bulk
            ctk.CTkButton(self.input_frame, text="+ Add to Queue", width=120, command=self.add_to_queue).grid(row=2, column=1, padx=10, pady=10, sticky="w")

        else:
            # --- UI For Standard Tasks (Wagelist, MR, etc.) ---
            ctk.CTkLabel(self.input_frame, text="Target Panchayat(s):").grid(row=0, column=0, padx=10, pady=5, sticky="nw")
            
            # Re-create the standard target entry
            t_vals = self.app.history_manager.get_suggestions("location_panchayat") or [""]
            self.target_var = ctk.StringVar()
            self.target_entry = ctk.CTkOptionMenu(self.input_frame, variable=self.target_var, values=t_vals, width=200)
            self.target_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
            
            btn_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
            btn_frame.grid(row=1, column=1, sticky="w", padx=10)
            
            ctk.CTkButton(btn_frame, text="+ Add to Queue", width=100, command=self.add_to_queue).pack(side="left")
            ctk.CTkButton(btn_frame, text="Clear Queue", width=100, fg_color="#C62828", hover_color="#B91C1C", command=self.clear_queue).pack(side="left", padx=10)

    def add_to_queue(self):
        task = self.task_type_menu.get()
        
        # --- Logic for Bulk Demand ---
        if task == "Bulk Demand (CSV)":
            p_name = self.bulk_inputs['panchayat_var'].get().strip()
            f_path = self.bulk_inputs['filepath'].get().strip()
            
            if not p_name or not f_path:
                messagebox.showwarning("Input Error", "Please enter Panchayat Name AND select a CSV file.")
                return
            
            if not os.path.exists(f_path):
                messagebox.showerror("File Error", "Selected file does not exist.")
                return

            item_id = len(self.queue_items) + 1
            # Note: We use 'panchayat' and 'filepath' keys for the workflow manager
            item = {
                'id': item_id, 
                'type': 'bulk_demand',  # Internal key
                'target': p_name,       # For display
                'panchayat': p_name,    # For logic
                'filepath': f_path,     # For logic
                'status': 'Pending', 
                'msg': f"File: {os.path.basename(f_path)}"
            }
            self.queue_items.append(item)
            self.queue_tree.insert("", "end", iid=str(item_id), values=(item_id, "Bulk Demand", p_name, "Pending", item['msg']), tags=('Pending',))
            
            # Clear inputs
            self.bulk_inputs['panchayat_var'].set("")
            self.bulk_inputs['filepath'].delete(0, "end")
            
        # --- Logic for Standard Tasks ---
        else:
            if not self.target_entry: return
            target = self.target_var.get().strip()
            
            if not target:
                messagebox.showwarning("Input", "Please enter a Panchayat Name.")
                return

            targets = [t.strip() for t in target.split(',') if t.strip()]
            
            for t in targets:
                item_id = len(self.queue_items) + 1
                item = {'id': item_id, 'type': task, 'target': t, 'status': 'Pending', 'msg': 'Waiting...'}
                self.queue_items.append(item)
                self.queue_tree.insert("", "end", iid=str(item_id), values=(item_id, task, t, "Pending", "Waiting..."), tags=('Pending',))
            
            self.target_var.set("")
            
        self.log_info("Task added to queue.")
    def clear_queue(self):
        self.queue_items.clear()
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        self.log_info("Queue cleared.")
    def update_item_status(self, item_id, status, msg=""):
        try:
            for item in self.queue_items:
                if str(item['id']) == str(item_id):
                    item['status'] = status
                    item['msg'] = msg
                    break
            
            if self.queue_tree.exists(str(item_id)):
                current_vals = self.queue_tree.item(str(item_id))['values']
                new_vals = (current_vals[0], current_vals[1], current_vals[2], status, msg)
                self.queue_tree.item(str(item_id), values=new_vals, tags=(status,))
                self.queue_tree.see(str(item_id))
        except Exception as e:
            print(f"Error updating status: {e}")

    def start_macro(self):
        if not self.queue_items:
            messagebox.showwarning("Empty", "Queue is empty.")
            return
            
        pending = [i for i in self.queue_items if i['status'] in ['Pending', 'Failed']]
        if not pending:
            if messagebox.askyesno("Reset", "All tasks finished. Reset statuses to run again?"):
                for i in self.queue_items: 
                    self.update_item_status(i['id'], "Pending", "Waiting...")
            else: return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        self.log_info(">>> Starting Macro Queue Execution...")
        self.notebook.set("Logs & Status")
        
        self.app.start_automation_thread(self.automation_key, self.app.workflows.process_global_queue, args=(self,))

    def set_ui_state(self, running: bool) -> None:
        if not self._is_alive():
            return
        state = "disabled" if running else "normal"
        self.start_btn.configure(state=state)
        self.stop_btn.configure(state="normal" if running else "disabled")
        
        # Safely configure inputs depending on what's visible
        if self.target_entry:
            self.target_entry.configure(state=state)
        
        if self.bulk_inputs:
            self.bulk_inputs['panchayat'].configure(state=state)
            self.bulk_inputs['filepath'].configure(state=state)