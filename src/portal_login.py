"""Portal login-level detection — shared helper (Session Expired trick).

VB-G-RAM-G portal par login status detect karne ki strategy:

  • Logged-out hone par demand page sirf 'Session Expired!' text dikhata
    hai — koi complex DOM parsing nahi chahiye.
  • Logged-in hone par:
      - panchayat dropdown (DDL_panchayat) mile  → PO (Block / Program
        Officer) login.
      - sirf village dropdown (DDL_Village) mile → GP (Panchayat level)
        login.

Is helper ko onboarding wizard, settings scrape aur koi bhi automation use
kar sakta hai taaki detection logic ek hi jagah ho. Selenium imports
function-level rakhe gaye hain (startup slow na ho).
"""

# Demand page ke dropdown element IDs — GP vs PO detection ke liye
PANCHAYAT_DROPDOWN_ID = "ctl00_ContentPlaceHolder1_DDL_panchayat"
VILLAGE_DROPDOWN_ID = "ctl00_ContentPlaceHolder1_DDL_Village"


def detect_portal_login(driver, demand_url=None, wait_seconds=15):
    """Demand page par login status detect karo.

    Args:
        driver: Selenium driver (browser already connected).
        demand_url: Demand page URL. Diya jaye to pehle us par navigate
            karta hai (ye navigation khud session ko bhi fresh karti hai).
        wait_seconds: Page settle hone ka max wait (default 15s).

    Returns:
        (status, level):
          status:
            'not_logged_in' — 'Session Expired!' ya login-page redirect.
            'po'            — logged in, panchayat dropdown present
                              (Block / Program Officer).
            'gp'            — logged in, sirf village dropdown
                              (Panchayat level).
            'unknown'       — kuch bhi match nahi hua.
          level: 'PO' | 'GP' | None (sirf logged-in par set hota hai).
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    if demand_url:
        driver.get(demand_url)
        try:
            WebDriverWait(driver, wait_seconds).until(lambda d: (
                "session expired" in (d.page_source or "").lower()
                or "login" in (d.current_url or "").lower()
                or d.find_elements(By.ID, PANCHAYAT_DROPDOWN_ID)
                or d.find_elements(By.ID, VILLAGE_DROPDOWN_ID)
            ))
        except Exception:
            pass
    cur = (driver.current_url or "").lower()
    body = (driver.page_source or "").lower()
    if "session expired" in body or "login" in cur:
        return "not_logged_in", None
    if driver.find_elements(By.ID, PANCHAYAT_DROPDOWN_ID):
        return "po", "PO"
    if driver.find_elements(By.ID, VILLAGE_DROPDOWN_ID):
        return "gp", "GP"
    return "unknown", None
