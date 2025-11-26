@echo off
REM =======================================================
REM  Windows Build Script for NREGA Bot (Smart Loader)
REM =======================================================

REM --- Configuration ---
REM GitHub Actions se APP_VERSION set hoga, nahi to default use karega
IF "%APP_VERSION%"=="" SET APP_VERSION="0.0.0"

SET APP_NAME="NREGA Bot"
SET INNO_SETUP_COMPILER="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

ECHO ######################################################
ECHO.
ECHO  Building %APP_NAME% v%APP_VERSION% (Loader System)...
ECHO.
ECHO ######################################################
ECHO.

REM --- Step 1: Run PyInstaller on LOADER.PY ---
ECHO [STEP 1/2] Building the application with PyInstaller...
ECHO.

REM Hum loader.py ko build kar rahe hain, lekin main_app ki libraries
REM ko zabardasti pack kar rahe hain (hidden-import) taaki wo andar मौजूद rahein.

pyinstaller --noconfirm --windowed --onefile ^
--name %APP_NAME% ^
--icon="assets/app_icon.ico" ^
--add-data="logo.png;." ^
--add-data="theme.json;." ^
--add-data="changelog.json;." ^
--add-data="assets;assets" ^
--add-data=".env;." ^
--add-data="jobcard.jpeg;." ^
--add-data="tabs;tabs" ^
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
loader.py

REM Check if PyInstaller failed
if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! PyInstaller build FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO PyInstaller build successful.
ECHO.

REM --- Step 2: Run Inno Setup Compiler ---
ECHO [STEP 2/2] Creating the installer with Inno Setup...
ECHO.

REM Check if the Inno Setup compiler exists (Local Machine Check)
if not exist %INNO_SETUP_COMPILER% (
    REM GitHub Actions environment me path alag ho sakta hai, ye local check hai
    ECHO Warning: Inno Setup default path not found. Assuming configured in PATH or GitHub Action.
)

REM Agar GitHub Action me hain, to ISCC command path me hota hai
ISCC /dAppVersion=%APP_VERSION% "installer.iss"

if errorlevel 1 (
    ECHO.
    ECHO !!!!!!! Inno Setup compilation FAILED. !!!!!!!
    goto End
)

ECHO.
ECHO =======================================================
ECHO.
ECHO  Build successful!
ECHO  Find your installer in the 'dist\installer' sub-folder.
ECHO.
ECHO =======================================================

:End
pause