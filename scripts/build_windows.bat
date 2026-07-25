@echo off
REM =======================================================
REM  Windows Build Script for NREGA Bot (Smart Loader)
REM =======================================================

REM --- Configuration ---
REM GitHub Actions se APP_VERSION set hoga, nahi to default use karega
IF "%APP_VERSION%"=="" SET APP_VERSION="0.0.0"

SET APP_NAME="NREGA Bot"
SET LITE_APP_NAME="NREGA Bot Lite"
REM Chocolatey installs Inno Setup to %%ProgramFiles%% (C:\Program Files), NOT to (x86)
SET INNO_SETUP_COMPILER="%ProgramFiles%\Inno Setup 6\ISCC.exe"
SET INNO_SETUP_COMPILER_X86="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

ECHO ######################################################
ECHO.
ECHO  Building %APP_NAME% v%APP_VERSION% (Loader System)...
ECHO.
ECHO ######################################################
ECHO.

REM --- Clean previous builds ---
ECHO [STEP 0/3] Cleaning old builds...
if exist "dist\%APP_NAME%" rmdir /s /q "dist\%APP_NAME%"
if exist "dist\%LITE_APP_NAME%" rmdir /s /q "dist\%LITE_APP_NAME%"
if exist "dist\installer" rmdir /s /q "dist\installer"
if exist "build" rmdir /s /q "build"
ECHO Old builds cleaned.
ECHO.

REM ==============================================================
REM !!! IMPORTANT: PyInstaller 6.x+ uses : as separator on ALL  !!!
REM !!! platforms, including Windows. Old ; separator no longer !!!
REM !!! works. Use forward slashes in paths for consistency.    !!!
REM ==============================================================

REM --- Step 1a: Build MAIN App (Loader) ---
ECHO [STEP 1a/3] Building MAIN app with PyInstaller...
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
ECHO [STEP 1b/3] Building LITE app with PyInstaller...
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

REM --- Step 2: Run Inno Setup Compiler (MAIN app installer only) ---
ECHO [STEP 2/3] Creating the MAIN installer with Inno Setup...
ECHO.

REM Try primary path (%%ProgramFiles%% - chocolatey default)
if exist %INNO_SETUP_COMPILER% (
    ECHO Found Inno Setup at: %INNO_SETUP_COMPILER%
    %INNO_SETUP_COMPILER% /dAppVersion=%APP_VERSION% "scripts/installer.iss"
) else (
    REM Try fallback path (%%ProgramFiles(x86)%% - manual install)
    ECHO Not found at primary path. Trying fallback...
    if exist %INNO_SETUP_COMPILER_X86% (
        ECHO Found Inno Setup at: %INNO_SETUP_COMPILER_X86%
        %INNO_SETUP_COMPILER_X86% /dAppVersion=%APP_VERSION% "scripts/installer.iss"
    ) else (
        ECHO Inno Setup not found at either path. Skipping installer creation.
        ECHO Main app portable build is in dist\%APP_NAME%\
        goto End
    )
)

if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! Inno Setup compilation FAILED. !!!!!!!
    ECHO Main app installer not created, but portable build is in dist\%APP_NAME%\
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