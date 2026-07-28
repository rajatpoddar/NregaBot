# src/tabs/_imports.py
#
# Shared imports for all automation tabs.
# Tabs do:  from ._imports import *
# at module level instead of repeating lazy imports in every method body.
#
# ⚠️ These imports are resolved when the tab module is first loaded.
# Since tab_config.py lazy-imports tab modules via _lazy_import(), this
# happens only when the user first opens that tab — not at app startup.

# --- selenium.webdriver.common ---
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.print_page_options import PrintOptions

# --- selenium.webdriver.support ---
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- selenium.common.exceptions ---
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    NoSuchWindowException,
    StaleElementReferenceException,
    TimeoutException,
    UnexpectedAlertPresentException,
    WebDriverException,
)

# --- selenium itself (for driver creation) ---
from selenium import webdriver

# --- Chrome options (used by mr_tracking and some others) ---
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

# --- openpyxl ---
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

# --- pandas ---
import pandas as pd

# ────────────────────────────────────────────────────────────────
#  __all__  —  explicit list of names exported via import *
# ────────────────────────────────────────────────────────────────
__all__ = [
    # selenium.webdriver.common
    "By",
    "Keys",
    "PrintOptions",
    # selenium.webdriver.support
    "Select",
    "WebDriverWait",
    "EC",
    # selenium.common.exceptions
    "NoAlertPresentException",
    "NoSuchElementException",
    "NoSuchWindowException",
    "StaleElementReferenceException",
    "TimeoutException",
    "UnexpectedAlertPresentException",
    "WebDriverException",
    # selenium
    "webdriver",
    # Chrome options
    "ChromeOptions",
    "ChromeService",
    # openpyxl
    "openpyxl",
    "XLImage",
    "Alignment",
    "Border",
    "Font",
    "PatternFill",
    "Side",
    "get_column_letter",
    "PageMargins",
    # pandas
    "pd",
]
