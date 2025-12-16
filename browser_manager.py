import os
import sys
import subprocess
import socket
import threading
from tkinter import messagebox
import tkinter
import customtkinter as ctk
import config
from utils import resource_path

# Selenium Imports (Lazy loading handled inside methods where possible to speed up start)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import WebDriverException
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

class BrowserManager:
    def __init__(self, app):
        self.app = app # Main App ka reference taaki hum sound/toast use kar sakein
        self.driver = None
        self.active_browser = None
        
        # Background me Webdriver Manager initialize karo
        threading.Thread(target=self._initialize_webdriver_manager, daemon=True).start()

    def _initialize_webdriver_manager(self):
        try:
            ChromeService(ChromeDriverManager().install())
        except: pass
        try:
            FirefoxService(GeckoDriverManager().install())
        except: pass

    def launch_chrome_detached(self, target_urls=None):
        """Launches Chrome with debugging port enabled."""
        port, p_dir = "9222", os.path.join(os.path.expanduser("~"), "ChromeProfileForNREGABot")
        os.makedirs(p_dir, exist_ok=True)
        
        paths = {
            "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"], 
            "Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
        }
        b_path = next((p for p in paths.get(config.OS_SYSTEM, []) if os.path.exists(p)), None)
        
        if not b_path: 
            self.app.play_sound("error")
            messagebox.showerror("Error", "Google Chrome not found.")
            return
            
        if target_urls:
            urls_to_open = target_urls
        else:
            urls_to_open = [config.MAIN_WEBSITE_URL, "https://bookmark.nregabot.com/"]
            
        try:
            cmd = [
                b_path, 
                f"--remote-debugging-port={port}", 
                f"--user-data-dir={p_dir}",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--log-level=3",
                "--silent"
            ] + urls_to_open
            
            flags = 0x00000008 if config.OS_SYSTEM == "Windows" else 0
            
            subprocess.Popen(
                cmd, 
                creationflags=flags, 
                start_new_session=(config.OS_SYSTEM != "Windows"),
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            if not target_urls:
                self.app.play_sound("success")
                self.app.show_toast("Chrome Launched successfully!", "success")
                
        except Exception as e: 
            self.app.play_sound("error")
            messagebox.showerror("Error", f"Failed to launch Chrome:\n{e}")

    def launch_edge_detached(self):
        port, p_dir = "9223", os.path.join(os.path.expanduser("~"), "EdgeProfileForNREGABot")
        os.makedirs(p_dir, exist_ok=True)
        paths = {"Darwin": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"], "Windows": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]}
        b_path = next((p for p in paths.get(config.OS_SYSTEM, []) if os.path.exists(p)), None)
        
        if not b_path: 
            self.app.play_sound("error")
            messagebox.showerror("Error", "Microsoft Edge not found.")
            return
            
        try:
            cmd = [
                b_path, 
                f"--remote-debugging-port={port}", 
                f"--user-data-dir={p_dir}",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                config.MAIN_WEBSITE_URL, 
                "https://bookmark.nregabot.com/"
            ]

            flags = 0x00000008 if config.OS_SYSTEM == "Windows" else 0
            subprocess.Popen(
                cmd, 
                creationflags=flags, 
                start_new_session=(config.OS_SYSTEM != "Windows"),
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            self.app.play_sound("success")
            self.app.show_toast("Edge Launched successfully!", "success")
        except Exception as e: 
            self.app.play_sound("error")
            messagebox.showerror("Error", f"Failed to launch Edge:\n{e}")

    def launch_firefox_managed(self):
        if self.driver and messagebox.askyesno("Browser Running", "Close existing Firefox and start new?"): 
            try: self.driver.quit()
            except: pass
            self.driver = None
        elif self.driver: return
        
        try:
            p_dir = os.path.join(os.path.expanduser("~"), "FirefoxProfileForNREGABot")
            os.makedirs(p_dir, exist_ok=True)
            opts = FirefoxOptions()
            opts.add_argument("-profile")
            opts.add_argument(p_dir)
            
            self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=opts)
            self.active_browser = "firefox"
            self.app.play_sound("success")
            
            self.driver.get(config.MAIN_WEBSITE_URL)
            self.driver.execute_script("window.open(arguments[0], '_blank');", "https://bookmark.nregabot.com/")
            self.driver.switch_to.window(self.driver.window_handles[0])
            
            # Sync with main app
            self.app.driver = self.driver
            self.app.active_browser = "firefox"
            
        except Exception as e: 
            self.app.play_sound("error")
            messagebox.showerror("Error", f"Failed to launch Firefox:\n{e}")
            self.driver = None
            self.active_browser = None

    def get_driver(self):
        """Connects to an existing browser session."""
        available_browsers = []
        
        # Check Firefox (Internal)
        if self.driver:
            try:
                if not self.driver.window_handles: raise WebDriverException("No active windows")
                try: _ = self.driver.current_url
                except WebDriverException: self.driver.switch_to.window(self.driver.window_handles[0])
                available_browsers.append("firefox")
            except Exception: self.driver = None

        # Check Chrome (External Port 9222)
        try:
            with socket.create_connection(("127.0.0.1", 9222), timeout=0.2): available_browsers.append("chrome")
        except (socket.timeout, ConnectionRefusedError): pass
        
        # Check Edge (External Port 9223)
        try:
            with socket.create_connection(("127.0.0.1", 9223), timeout=0.2): available_browsers.append("edge")
        except (socket.timeout, ConnectionRefusedError): pass

        if not available_browsers:
            self.app.play_sound("error")
            messagebox.showerror("Connection Failed", "No browser is running. Please launch one first.")
            return None

        selected_browser = available_browsers[0] if len(available_browsers) == 1 else self._ask_browser_selection(available_browsers)
        if not selected_browser: return None

        if selected_browser == "firefox":
            if not self.driver:
                self.app.play_sound("error")
                messagebox.showerror("Error", "Firefox session was lost. Please relaunch Firefox.")
                return None
            self.active_browser = "firefox"
            self.app.active_browser = "firefox"
            return self.driver
            
        elif selected_browser == "chrome":
            try:
                opts = ChromeOptions()
                opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                driver = webdriver.Chrome(options=opts)
                self.active_browser = 'chrome'
                self.app.active_browser = 'chrome'
                return driver
            except Exception as e:
                self.app.play_sound("error")
                messagebox.showerror("Connection Failed", f"Could not connect to Chrome.\nError: {e}")
                return None
                
        elif selected_browser == "edge":
            try:
                opts = EdgeOptions()
                opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
                driver = webdriver.Edge(options=opts)
                self.active_browser = 'edge'
                self.app.active_browser = 'edge'
                return driver
            except Exception as e:
                self.app.play_sound("error")
                messagebox.showerror("Connection Failed", f"Could not connect to Edge.\nError: {e}")
                return None
        return None

    def _ask_browser_selection(self, options):
        selection_var = tkinter.StringVar(value="")
        dialog = ctk.CTkToplevel(self.app)
        dialog.title("Select Browser")
        dialog.geometry("300x250")
        dialog.resizable(False, False)
        dialog.transient(self.app)
        dialog.grab_set()
        dialog.update_idletasks()
        
        # Center dialog
        try:
            x = self.app.winfo_x() + (self.app.winfo_width() // 2) - (300 // 2)
            y = self.app.winfo_y() + (self.app.winfo_height() // 2) - (250 // 2)
            dialog.geometry(f"+{x}+{y}")
        except: pass
        
        ctk.CTkLabel(dialog, text="Multiple browsers detected.", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(dialog, text="Which one do you want to use?").pack(pady=(0, 20))
        
        def select(choice): 
            selection_var.set(choice)
            dialog.destroy()
            
        for opt in options:
            ctk.CTkButton(dialog, text=f"Use {opt.capitalize()}", 
                          image=self.app.icon_images.get(opt, None), 
                          command=lambda o=opt: select(o)).pack(pady=5, padx=20, fill="x")
        
        self.app.wait_window(dialog)
        return selection_var.get()