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
ECHO [STEP 1b/3] Building LITE app with PyInstaller...
ECHO.

pyinstaller --noconfirm --windowed --onedir ^
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
lite_loader.py

REM Check if PyInstaller failed
if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! LITE app PyInstaller build FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO LITE app PyInstaller build successful.
ECHO.

REM --- Step 1c: Create LITE app portable ZIP ---
ECHO [STEP 1c/3] Creating LITE app portable ZIP...
ECHO.

REM Strip quotes from version for filename
SET ZIP_VERSION=%APP_VERSION:"=%

REM Create portable ZIP of the onedir directory
powershell -Command "Compress-Archive -Path 'dist\NREGA Bot Lite' -DestinationPath 'dist\NREGA_Bot_Lite_v%ZIP_VERSION%_portable.zip' -Force"

if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! LITE app ZIP creation FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO LITE app portable ZIP created successfully.
ECHO.

REM --- Step 2a: Create MAIN app installer with Inno Setup ---
ECHO [STEP 2a/3] Creating the MAIN installer with Inno Setup...
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
    ECHO !!!!!!! MAIN Inno Setup compilation FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO MAIN installer created successfully.
ECHO.

REM --- Step 2b: Create LITE app installer with Inno Setup ---
ECHO [STEP 2b/3] Creating the LITE installer with Inno Setup...
ECHO.

ISCC /dAppVersion=%APP_VERSION% "scripts\installer_lite.iss"

if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! LITE Inno Setup compilation FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO LITE installer created successfully.
ECHO.
ECHO =======================================================
ECHO.
ECHO  Build successful!
ECHO  - MAIN installer: dist\installer\NREGABot-v%APP_VERSION:"=%-Setup.exe
ECHO  - LITE installer: dist\installer\NREGABot-Lite-v%APP_VERSION:"=%-Setup.exe
ECHO  - LITE portable:  dist\NREGA_Bot_Lite_v%ZIP_VERSION%_portable.zip
ECHO.
ECHO =======================================================

:End
REM CI environment me pause mat karo (GitHub Actions hang ho jayega)
if not defined CI pause
