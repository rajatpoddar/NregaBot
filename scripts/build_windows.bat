@echo off
REM =======================================================
REM  Windows Build Script for NREGA Bot (Smart Loader)
REM =======================================================

REM --- Configuration ---
REM GitHub Actions se APP_VERSION set hoga, nahi to default use karega
IF "%APP_VERSION%"=="" SET APP_VERSION="0.0.0"

SET APP_NAME="NREGA Bot"
SET LITE_APP_NAME="NREGA Bot Lite"

ECHO ######################################################
ECHO.
ECHO  Building %APP_NAME% v%APP_VERSION% (Loader System) + %LITE_APP_NAME%...
ECHO.
ECHO ######################################################
ECHO.

REM --- Step 1a: Build MAIN App (Loader) ---
ECHO [STEP 1a/2] Building MAIN app with PyInstaller...
ECHO.

pyinstaller --noconfirm --windowed --onedir ^
--name %APP_NAME% ^
--icon="assets/app_icon.ico" ^
--add-data="assets:assets" ^
--add-data="config:config" ^
--add-data="docs/changelog.json:docs/" ^
--add-data="src:src" ^
--add-data="web:web" ^
--add-data=".env:." ^
--collect-all customtkinter ^
--collect-data fpdf ^
--hidden-import=selenium ^
--hidden-import=webdriver_manager ^
--hidden-import=pandas ^
--hidden-import=PIL ^
--hidden-import=requests ^
--hidden-import=fpdf ^
--hidden-import=babel.numbers ^
--hidden-import=tkcalendar ^
--hidden-import=getmac ^
--hidden-import=packaging ^
--hidden-import=main_app ^
--collect-submodules=src.tabs ^
loader.py

REM Check if PyInstaller failed
if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! MAIN app PyInstaller build FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO MAIN app PyInstaller build successful.
ECHO.

REM --- Step 1b: Build LITE App ---
ECHO [STEP 1b/2] Building LITE app with PyInstaller...
ECHO.

pyinstaller --noconfirm --windowed --onefile ^
--name %LITE_APP_NAME% ^
--icon="assets/app_icon.ico" ^
--add-data="assets:assets" ^
--add-data="config:config" ^
--add-data="src:src" ^
--add-data=".env:." ^
--collect-all customtkinter ^
--hidden-import=getmac ^
--hidden-import=packaging ^
--hidden-import=requests ^
--hidden-import=PIL ^
--collect-submodules=src.managers ^
--collect-submodules=src.tabs ^
lite_app.py

REM Check if PyInstaller failed
if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! LITE app PyInstaller build FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO LITE app PyInstaller build successful.
ECHO.

REM --- Step 2: Create installer with Inno Setup (MAIN app only) ---
ECHO [STEP 2/2] Creating the MAIN installer with Inno Setup...
ECHO.

REM Check if the Inno Setup compiler exists (Local Machine Check)
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    if not exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
        ECHO Warning: Inno Setup default path not found. Assuming configured in PATH or GitHub Action.
    )
)

REM Agar GitHub Action me hain, to ISCC command path me hota hai
ISCC /dAppVersion=%APP_VERSION% "scripts\installer.iss"

if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! Inno Setup compilation FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO =======================================================
ECHO.
ECHO  Build successful!
ECHO  - MAIN installer: dist\installer
ECHO  - LITE standalone: dist\%LITE_APP_NAME%.exe
ECHO.
ECHO =======================================================

:End
REM CI environment me pause mat karo (GitHub Actions hang ho jayega)
if not defined CI pause
