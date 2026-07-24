import os
import sys
import subprocess
import socket
from tkinter import messagebox
import tkinter
from typing import Any, Dict, List, Optional, Tuple
import customtkinter as ctk
from src import config
from src.utils import resource_path, get_logger

logger = get_logger()

# Selenium Imports (Lazy loading handled inside methods where possible to speed up start)


class BrowserManager:
    def __init__(self, app: object) -> None:
        self.app = app  # Main App ka reference taaki hum sound/toast use kar sakein
        self.driver: Any = None
        self.active_browser: Optional[str] = None
        
        # Suppress verbose WDM (WebDriver Manager) INFO logs from terminal
        os.environ['WDM_LOG'] = '0'

    def launch_chrome_detached(self, target_urls: Optional[List[str]] = None) -> None:
        """Launches Chrome with debugging port enabled."""
        port, p_dir = "9222", os.path.join(os.path.expanduser("~"), "ChromeProfileForNREGABot")
        os.makedirs(p_dir, exist_ok=True)
        
        paths: Dict[str, List[str]] = {
            "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"], 
            "Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
        }
        b_path: Optional[str] = next((p for p in paths.get(config.OS_SYSTEM, []) if os.path.exists(p)), None)
        
        if not b_path: 
            self.app.play_sound("error")
            messagebox.showerror("Error", "Google Chrome not found.")
            return
            
        if target_urls:
            urls_to_open: List[str] = target_urls
        else:
            urls_to_open = [config.MAIN_WEBSITE_URL, "https://bookmark.nregabot.com/"]
            
        try:
            cmd: List[str] = [
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
            
            flags: int = 0x00000008 if config.OS_SYSTEM == "Windows" else 0
            
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

    def launch_edge_detached(self) -> None:
        port, p_dir = "9223", os.path.join(os.path.expanduser("~"), "EdgeProfileForNREGABot")
        os.makedirs(p_dir, exist_ok=True)
        paths: Dict[str, List[str]] = {
            "Darwin": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
            "Windows": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
        }
        b_path: Optional[str] = next((p for p in paths.get(config.OS_SYSTEM, []) if os.path.exists(p)), None)
        
        if not b_path: 
            self.app.play_sound("error")
            messagebox.showerror("Error", "Microsoft Edge not found.")
            return
            
        try:
            cmd: List[str] = [
                b_path, 
                f"--remote-debugging-port={port}", 
                f"--user-data-dir={p_dir}",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                config.MAIN_WEBSITE_URL, 
                "https://bookmark.nregabot.com/"
            ]

            flags: int = 0x00000008 if config.OS_SYSTEM == "Windows" else 0
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

    def launch_firefox_managed(self) -> None:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options as FirefoxOptions

        if self.driver and messagebox.askyesno("Browser Running", "Close existing Firefox and start new?"): 
            try: self.driver.quit()
            except Exception as e: logger.debug("Failed to quit Firefox driver: %s", e)
            self.driver = None
        elif self.driver:
            return
        
        try:
            p_dir = os.path.join(os.path.expanduser("~"), "FirefoxProfileForNREGABot")
            os.makedirs(p_dir, exist_ok=True)
            opts = FirefoxOptions()
            opts.add_argument("-profile")
            opts.add_argument(p_dir)
            
            service = self._create_driver_service("firefox")
            if service:
                self.driver = webdriver.Firefox(options=opts, service=service)
            else:
                # Fallback: let Selenium Manager handle geckodriver
                self.driver = webdriver.Firefox(options=opts)
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
            
    def launch_old_firefox(self, binary_path: str, target_url: Optional[str] = None) -> Tuple[bool, str]:
        """Launches a specific old version of Firefox for FTO DSC processing."""
        try:
            from selenium import webdriver
            from selenium.webdriver.firefox.options import Options
            from selenium.webdriver.firefox.service import Service
            from src.utils import resource_path

            if not os.path.exists(binary_path):
                raise Exception(f"Firefox not found at: {binary_path}")

            options = Options()
            options.binary_location = binary_path
            
            # Note: Old Firefox ke liye purana geckodriver chahiye hota hai.
            # Aapko 'assets/drivers/geckodriver_old.exe' rakhna padega.
            driver_path: str = resource_path("assets/drivers/geckodriver_old.exe")
            
            if os.path.exists(driver_path):
                service = Service(executable_path=driver_path)
                driver = webdriver.Firefox(service=service, options=options)
            else:
                # Agar driver file nahi milti to default launch try karega
                driver = webdriver.Firefox(options=options)

            self.driver = driver
            self.active_browser = "firefox_old"
            
            if target_url:
                driver.get(target_url)
                
            return True, "Old Firefox launched successfully!"
        except Exception as e:
            return False, f"Failed to launch Old Firefox: {e}"

    def _create_driver_service(self, browser_type: str) -> Any:
        """Returns a Service object for the given browser type, or None.
        Uses webdriver_manager to download the driver if needed, with
        a fallback to Selenium's built-in manager.
        """
        try:
            if browser_type == "chrome":
                from selenium.webdriver.chrome.service import Service as ChromeService
                from webdriver_manager.chrome import ChromeDriverManager
                return ChromeService(ChromeDriverManager().install())
            elif browser_type == "edge":
                from selenium.webdriver.edge.service import Service as EdgeService
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                return EdgeService(EdgeChromiumDriverManager().install())
            elif browser_type == "firefox":
                from selenium.webdriver.firefox.service import Service as FirefoxService
                from webdriver_manager.firefox import GeckoDriverManager
                return FirefoxService(GeckoDriverManager().install())
        except Exception:
            pass
        return None

    def get_driver(self) -> Any:
        """Connects to an existing browser session."""
        available_browsers: List[str] = []
        
        # Check Firefox (Internal)
        if self.driver:
            try:
                if not self.driver.window_handles:
                    from selenium.common.exceptions import WebDriverException
                    raise WebDriverException("No active windows")
                try:
                    _ = self.driver.current_url
                except Exception as e:
                    from selenium.common.exceptions import WebDriverException
                    self.driver.switch_to.window(self.driver.window_handles[0])
                available_browsers.append("firefox")
            except Exception:
                self.driver = None

        # Check Chrome (External Port 9222)
        try:
            with socket.create_connection(("127.0.0.1", 9222), timeout=0.2):
                available_browsers.append("chrome")
        except (socket.timeout, ConnectionRefusedError):
            pass
        
        # Check Edge (External Port 9223)
        try:
            with socket.create_connection(("127.0.0.1", 9223), timeout=0.2):
                available_browsers.append("edge")
        except (socket.timeout, ConnectionRefusedError):
            pass

        if not available_browsers:
            self.app.play_sound("error")
            messagebox.showerror("Connection Failed", "No browser is running. Please launch one first.")
            return None

        selected_browser: str = available_browsers[0] if len(available_browsers) == 1 else self._ask_browser_selection(available_browsers)
        if not selected_browser:
            return None

        if selected_browser == "firefox":
            if not self.driver:
                self.app.play_sound("error")
                messagebox.showerror("Error", "Firefox session was lost. Please relaunch Firefox.")
                return None
            self.active_browser = "firefox"
            self.app.active_browser = "firefox"
            return self.driver
            
        elif selected_browser == "chrome":
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            try:
                opts = ChromeOptions()
                opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                service = self._create_driver_service("chrome")
                if service:
                    driver = webdriver.Chrome(options=opts, service=service)
                else:
                    # Fallback: let Selenium Manager handle driver
                    driver = webdriver.Chrome(options=opts)
                self.active_browser = 'chrome'
                self.app.active_browser = 'chrome'
                return driver
            except Exception as e:
                self.app.play_sound("error")
                messagebox.showerror("Connection Failed", f"Could not connect to Chrome.\nError: {e}")
                return None
                
        elif selected_browser == "edge":
            from selenium import webdriver
            from selenium.webdriver.edge.options import Options as EdgeOptions
            try:
                opts = EdgeOptions()
                opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
                service = self._create_driver_service("edge")
                if service:
                    driver = webdriver.Edge(options=opts, service=service)
                else:
                    # Fallback: let Selenium Manager handle driver
                    driver = webdriver.Edge(options=opts)
                self.active_browser = 'edge'
                self.app.active_browser = 'edge'
                return driver
            except Exception as e:
                self.app.play_sound("error")
                messagebox.showerror("Connection Failed", f"Could not connect to Edge.\nError: {e}")
                return None
        return None

    def _ask_browser_selection(self, options: List[str]) -> str:
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
        except Exception as e:
            logger.debug("Failed to center browser selection dialog: %s", e)
        
        ctk.CTkLabel(dialog, text="Multiple browsers detected.", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(dialog, text="Which one do you want to use?").pack(pady=(0, 20))
        
        def select(choice: str) -> None: 
            selection_var.set(choice)
            dialog.destroy()
            
        for opt in options:
            ctk.CTkButton(dialog, text=f"Use {opt.capitalize()}", 
                          image=self.app.icon_images.get(opt, None), 
                          command=lambda o=opt: select(o)).pack(pady=5, padx=20, fill="x")
        
        self.app.wait_window(dialog)
        return selection_var.get()
