import threading
import json
import os
import time
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from .base_tab import BaseAutomationTab

class LoginAutomationTab(BaseAutomationTab):
    def __init__(self, parent, app_instance):
        super().__init__(parent, app_instance, "login_automation")
        
        # --- Main Layout ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title = ctk.CTkLabel(self.main_frame, text="NREGA Navigation Automation", font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(pady=(0, 20))
        
        # --- Location Form Section ---
        form_frame = ctk.CTkFrame(self.main_frame)
        form_frame.pack(fill='x', padx=10, pady=10)
        form_frame.columnconfigure(1, weight=1)
        
        # 1. Financial Year
        ctk.CTkLabel(form_frame, text="Financial Year:", font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky='w', padx=15, pady=10)
        self.fin_year_var = tk.StringVar()
        self.fin_year_input = ctk.CTkComboBox(form_frame, variable=self.fin_year_var, width=250)
        current_year = 2025
        years = [f"{i}-{i+1}" for i in range(current_year + 1, 2010, -1)]
        self.fin_year_input.configure(values=years)
        if years: self.fin_year_input.set(years[1])
        self.fin_year_input.grid(row=0, column=1, padx=15, pady=10, sticky='w')
        
        # 2. District
        ctk.CTkLabel(form_frame, text="District Name:", font=ctk.CTkFont(size=13)).grid(row=1, column=0, sticky='w', padx=15, pady=10)
        self.district_input = ctk.CTkEntry(form_frame, width=250, placeholder_text="e.g. GAYA")
        self.district_input.grid(row=1, column=1, padx=15, pady=10, sticky='w')
        
        # 3. Block
        ctk.CTkLabel(form_frame, text="Block Name:", font=ctk.CTkFont(size=13)).grid(row=2, column=0, sticky='w', padx=15, pady=10)
        self.block_input = ctk.CTkEntry(form_frame, width=250, placeholder_text="e.g. MANPUR")
        self.block_input.grid(row=2, column=1, padx=15, pady=10, sticky='w')
        
        # --- Buttons ---
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        self.save_btn = ctk.CTkButton(btn_frame, text="💾 Save Location", command=self.save_credentials, fg_color="gray", font=ctk.CTkFont(weight="bold"))
        self.save_btn.pack(side='left', padx=10)
        
        self.login_btn = ctk.CTkButton(btn_frame, text="🚀 Launch & Navigate", command=self.run_login_thread, fg_color="#2E8B57", hover_color="#1F5E39", font=ctk.CTkFont(weight="bold"))
        self.login_btn.pack(side='left', padx=10)
        
        # Info Note
        note_label = ctk.CTkLabel(self.main_frame, text="Note: This will select District & Block automatically.\nYou must enter User ID & Password manually.", text_color="orange", font=ctk.CTkFont(size=12))
        note_label.pack(pady=10)

        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready to automate", text_color="gray")
        self.status_label.pack(pady=5)
        
        self.load_credentials()

    def get_creds_path(self):
        if hasattr(self.app, 'get_data_path'): return self.app.get_data_path('user_location_pref.json')
        return 'user_location_pref.json'

    def save_credentials(self):
        data = {
            "fin_year": self.fin_year_input.get(),
            "district": self.district_input.get().strip(),
            "block": self.block_input.get().strip()
        }
        try:
            with open(self.get_creds_path(), 'w') as f: json.dump(data, f)
            messagebox.showinfo("Success", "Location Preferences Saved!")
        except Exception as e: messagebox.showerror("Error", f"Could not save: {str(e)}")

    def load_credentials(self):
        path = self.get_creds_path()
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.fin_year_input.set(data.get("fin_year", ""))
                    self.district_input.delete(0, tk.END); self.district_input.insert(0, data.get("district", ""))
                    self.block_input.delete(0, tk.END); self.block_input.insert(0, data.get("block", ""))
            except: pass

    def run_login_thread(self):
        t = threading.Thread(target=self.run_login_automation)
        t.start()

    def run_login_automation(self):
        fin_year = self.fin_year_input.get()
        district = self.district_input.get().strip()
        block = self.block_input.get().strip()
        
        if not (district and block):
            messagebox.showwarning("Missing Info", "Please enter District and Block name")
            return

        try:
            self.update_status("Status: Launching Browser...")
            driver = self.app.get_driver()
            if not driver:
                self.update_status("Status: No Browser Found"); return

            url = "https://nregade4.nic.in/netnrega/Login.aspx?&level=HomePO&state_code=34"
            driver.get(url)
            wait = WebDriverWait(driver, 25)
            
            # --- 1. Select Dropdowns ---
            self.update_status("Status: Selecting Financial Year...")
            self._safe_select(wait, "//select[contains(@id, 'ddl_FinYr')]", fin_year)
            
            self.update_status(f"Status: Finding District '{district}'...")
            self._safe_select(wait, "//select[contains(@id, 'ddl_District')]", district, wait_for_options=True)

            self.update_status(f"Status: Finding Block '{block}'...")
            self._safe_select(wait, "//select[contains(@id, 'ddl_Block')]", block, wait_for_options=True)

            # --- Wait for Page Refresh ---
            self.update_status("Status: Waiting for page refresh...")
            # Block select karne ke baad page reload hota hai, uska wait karein
            time.sleep(3) 

            # --- Process Complete ---
            # Yahan se Maine Toast Notifications hata diye hain taaki koi crash na ho.
            # Sirf text status update hoga.
            self.update_status("Status: Ready for Login")
            
        except Exception as e:
            self.update_status("Status: Error occurred")
            messagebox.showerror("Automation Error", f"Error: {str(e)}")

    def _safe_select(self, wait, xpath, text, wait_for_options=False):
        for _ in range(3):
            try:
                elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                sel = Select(elem)
                if wait_for_options:
                    WebDriverWait(self.app.get_driver(), 5).until(lambda d: len(Select(d.find_element(By.XPATH, xpath)).options) > 1)
                    sel = Select(self.app.get_driver().find_element(By.XPATH, xpath))
                try: sel.select_by_visible_text(text)
                except:
                    found = False
                    for opt in sel.options:
                        if opt.text.strip().lower() == text.lower():
                            sel.select_by_visible_text(opt.text); found = True; break
                    if not found: raise Exception(f"Option '{text}' not found")
                return
            except StaleElementReferenceException:
                time.sleep(1)
        raise Exception(f"Failed to select '{text}' after retries")

    def update_status(self, text):
        # 1. Update Local Label
        self.status_label.configure(text=text)
        
        # 2. Update Global App Footer
        try:
            clean_text = text.replace("Status: ", "")
            self.app.set_status(clean_text)
        except: pass