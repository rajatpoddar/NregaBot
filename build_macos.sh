#!/bin/bash

# --- Clean previous builds ---
echo "Cleaning up previous builds..."
rm -rf build
rm -rf dist/*.app
rm -rf dist/*.dmg
# Note: Hum dist folder delete nahi kar rahe, bas purane artifacts hata rahe hain

# --- Define app details ---
APP_NAME="NREGABot"
ICON_FILE="assets/app_icon.icns"

# --- Automatic Version Detection ---
echo "Reading application version from config.py..."
APP_VERSION=$(grep "APP_VERSION =" config.py | sed 's/.*"\(.*\)".*/\1/')

if [ -z "$APP_VERSION" ]; then
    echo "!!!!!! ERROR: FAILED to read version from config.py !!!!!!"
    exit 1
fi
echo "Found version: $APP_VERSION"

# DMG Name
OUTPUT_DMG_NAME="dist/${APP_NAME}-v${APP_VERSION}-macOS.dmg"

# ========================================================
# STEP 0: GENERATE CORE UPDATE ZIP (Correctly named & placed)
# ========================================================
echo "--------------------------------------------------"
echo "Generating core update package locally..."
echo "--------------------------------------------------"

if [ -f "build_update.py" ]; then
    python3 build_update.py
    
    # Check if ANY zip file was created in dist matching the pattern
    if ls dist/core_mac_v*.zip 1> /dev/null 2>&1; then
        echo "✅ Core update package verified in dist/ folder."
    else
        echo "⚠️ Warning: build_update.py ran but the expected zip file was not found in 'dist/'."
    fi
else
    echo "⚠️ Warning: build_update.py not found! Skipping core zip generation."
fi

echo "--------------------------------------------------"

# --- Step 1: Run PyInstaller on LOADER.PY ---
echo "Building the Loader application with PyInstaller..."

pyinstaller --noconfirm --windowed --name "${APP_NAME}" \
--icon="$ICON_FILE" \
--add-data="logo.png:." \
--add-data="theme.json:." \
--add-data="changelog.json:." \
--add-data="assets:assets" \
--add-data=".env:." \
--add-data="jobcard.jpeg:." \
--add-data="tabs:tabs" \
--collect-all customtkinter \
--collect-data fpdf \
--hidden-import=selenium \
--hidden-import=webdriver_manager \
--hidden-import=pandas \
--hidden-import=PIL \
--hidden-import=requests \
--hidden-import=fpdf \
--hidden-import=babel.numbers \
--hidden-import=tkcalendar \
--hidden-import=getmac \
--hidden-import=packaging \
--hidden-import=main_app \
loader.py

# --- Step 2: Create the DMG ---
echo "Creating DMG package..."

if ! command -v create-dmg &> /dev/null; then
    echo "create-dmg could not be found. Please install it (brew install create-dmg)."
    exit 1
fi

create-dmg \
  --volname "${APP_NAME} Installer" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 175 180 \
  --hide-extension "${APP_NAME}.app" \
  --app-drop-link 425 180 \
  "$OUTPUT_DMG_NAME" \
  "dist/${APP_NAME}.app"

echo "✅ Build complete!"
echo "📂 DMG File: ${OUTPUT_DMG_NAME}"
# Latest core file dhoond ke print karo
LATEST_CORE=$(ls dist/core_mac_v*.zip | head -n 1)
echo "📦 Core Update File: ${LATEST_CORE}"