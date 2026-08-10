@echo off
REM =======================================================
REM  NREGA Bot - BETA Portable Build Script
REM  Builds a portable EXE that does NOT auto-update from
REM  version.json (loader skipped, in-app update check gated
REM  by the bundled config/beta.json marker).
REM
REM  Usage:
REM    scripts\build_beta_portable.bat              (onefile, v3.1.0-beta)
REM    scripts\build_beta_portable.bat folder       (folder+zip mode)
REM    scripts\build_beta_portable.bat onefile 3.1.0-beta
REM =======================================================

SET MODE=%1
IF "%MODE%"=="" SET MODE=onefile
SET BETA_VERSION=%2
IF "%BETA_VERSION%"=="" SET BETA_VERSION=3.1.0-beta

SET APP_NAME="NREGA Bot Beta"
SET MARKER=config\beta.json

ECHO ======================================================
ECHO  Building BETA v%BETA_VERSION%  (%MODE%)
ECHO  Auto-update from version.json: DISABLED
ECHO ======================================================
ECHO.

REM --- Defensive: remove any leftover marker from a previous interrupted run.
REM (Otherwise a stray config/beta.json would make ALL dev runs / normal builds beta.) ---
IF EXIST %MARKER% DEL /Q %MARKER%

REM --- Step 1: Create beta marker (bundled into EXE via --add-data="config:config") ---
IF NOT EXIST config MKDIR config
ECHO {"beta": true, "version": "%BETA_VERSION%"} > %MARKER%
ECHO [OK] Beta marker created: %MARKER%

REM --- Optional .env only if it exists (PyInstaller fails on missing source) ---
SET ENV_ARG=
IF EXIST .env SET ENV_ARG=--add-data=".env:."

REM --- Step 2: Build with PyInstaller (entry = main_app.py, loader is NOT used) ---
IF /I "%MODE%"=="folder" GOTO FolderMode

:OneFileMode
ECHO [BUILD] Single-file EXE mode...
pyinstaller --noconfirm --windowed --onefile ^
--name %APP_NAME% ^
--icon="assets/app_icon.ico" ^
--add-data="assets:assets" ^
--add-data="config:config" ^
--add-data="docs/changelog.json:docs/" ^
--add-data="docs/license.txt:docs/" ^
--add-data="src:src" ^
--add-data="src/locales:src/locales" ^
%ENV_ARG% ^
--collect-all customtkinter ^
--collect-data fpdf ^
--collect-all selenium ^
--collect-all webdriver_manager ^
--hidden-import=pandas ^
--hidden-import=PIL ^
--hidden-import=requests ^
--hidden-import=fpdf ^
--hidden-import=babel.numbers ^
--hidden-import=tkcalendar ^
--hidden-import=getmac ^
--hidden-import=packaging ^
--hidden-import=humanize ^
--hidden-import=openpyxl ^
--hidden-import=main_app ^
--collect-submodules=src.tabs ^
main_app.py
IF ERRORLEVEL 1 GOTO BuildFailed
IF EXIST "dist\NREGA Bot Beta.exe" (
    REN "dist\NREGA Bot Beta.exe" "NREGA_Bot_Beta_v%BETA_VERSION%_portable.exe"
)
ECHO.
ECHO [DONE] Output: dist\NREGA_Bot_Beta_v%BETA_VERSION%_portable.exe
ECHO         Share this single EXE with beta testers.
GOTO Cleanup

:FolderMode
ECHO [BUILD] Folder + ZIP mode...
pyinstaller --noconfirm --windowed --onedir ^
--name %APP_NAME% ^
--icon="assets/app_icon.ico" ^
--add-data="assets:assets" ^
--add-data="config:config" ^
--add-data="docs/changelog.json:docs/" ^
--add-data="docs/license.txt:docs/" ^
--add-data="src:src" ^
--add-data="src/locales:src/locales" ^
%ENV_ARG% ^
--collect-all customtkinter ^
--collect-data fpdf ^
--collect-all selenium ^
--collect-all webdriver_manager ^
--hidden-import=pandas ^
--hidden-import=PIL ^
--hidden-import=requests ^
--hidden-import=fpdf ^
--hidden-import=babel.numbers ^
--hidden-import=tkcalendar ^
--hidden-import=getmac ^
--hidden-import=packaging ^
--hidden-import=humanize ^
--hidden-import=openpyxl ^
--hidden-import=main_app ^
--collect-submodules=src.tabs ^
main_app.py
IF ERRORLEVEL 1 GOTO BuildFailed
powershell -Command "Compress-Archive -Path 'dist\NREGA Bot Beta' -DestinationPath 'dist\NREGA_Bot_Beta_v%BETA_VERSION%_portable.zip' -Force"
ECHO.
ECHO [DONE] Output: dist\NREGA_Bot_Beta_v%BETA_VERSION%_portable.zip
ECHO         Extract the ZIP and run "NREGA Bot Beta.exe".
GOTO Cleanup

:BuildFailed
ECHO.
ECHO [FAILED] PyInstaller build failed!
ECHO.

:Cleanup
REM --- Step 3: Remove beta marker so normal builds stay clean ---
IF EXIST %MARKER% DEL /Q %MARKER%
ECHO [OK] Beta marker removed (repo is clean).
IF NOT DEFINED CI pause
