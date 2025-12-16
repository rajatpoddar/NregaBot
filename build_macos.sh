#!/bin/bash

# --- 1. Clean previous builds ---
echo "Cleaning up previous builds..."
rm -rf build
rm -rf dist/*.app
rm -rf dist/*.dmg

# --- 2. Define app details ---
APP_NAME="NREGABot"
ICON_FILE="assets/app_icon.icns"

# Check if icon exists (Prevent PyInstaller default icon)
if [ ! -f "$ICON_FILE" ]; then
    echo "⚠️ Warning: Icon file not found at $ICON_FILE. Using default."
fi

# --- 3. Automatic Version Detection ---
echo "Reading application version from config.py..."
# Ensure config.py exists
if [ ! -f "config.py" ]; then
    echo "!!!!!! ERROR: config.py not found !!!!!!"
    exit 1
fi
APP_VERSION=$(grep "APP_VERSION =" config.py | sed 's/.*"\(.*\)".*/\1/')

if [ -z "$APP_VERSION" ]; then
    echo "!!!!!! ERROR: FAILED to read version from config.py !!!!!!"
    exit 1
fi
echo "Found version: $APP_VERSION"

# DMG Name
OUTPUT_DMG_NAME="dist/${APP_NAME}-v${APP_VERSION}-macOS.dmg"

# --- 4. Core Update Zip Generation ---
echo "--------------------------------------------------"
echo "Generating core update package locally..."
echo "--------------------------------------------------"

if [ -f "build_update.py" ]; then
    python3 build_update.py
    if ls dist/core_mac_v*.zip 1> /dev/null 2>&1; then
        echo "✅ Core update package verified in dist/ folder."
    else
        echo "⚠️ Warning: build_update.py ran but zip file not found."
    fi
else
    echo "⚠️ Warning: build_update.py not found! Skipping core zip generation."
fi

# --- 5. Generate Hidden Imports for Tabs (FIX FOR LAZY LOADING) ---
# Automatically find all python files in tabs/ folder and format as --hidden-import=tabs.filename
echo "Generating hidden imports for tabs..."
HIDDEN_IMPORTS=""
for file in tabs/*.py; do
    # Get filename without extension (e.g., tabs/msr_tab.py -> msr_tab)
    filename=$(basename "$file" .py)
    # Skip __init__
    if [ "$filename" != "__init__" ]; then
        HIDDEN_IMPORTS="$HIDDEN_IMPORTS --hidden-import=tabs.$filename"
    fi
done

# --- 6. Run PyInstaller ---
echo "Building the Loader application with PyInstaller..."

# Note: Added --clean, --noconsole (same as -w), and dynamic HIDDEN_IMPORTS
pyinstaller --noconfirm --clean --windowed --name "${APP_NAME}" \
--icon="$ICON_FILE" \
--add-data="logo.png:." \
--add-data="theme.json:." \
--add-data="assets:assets" \
--add-data=".env:." \
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
--hidden-import=tab_config \
--hidden-import=ui_components \
--hidden-import=workflow_manager \
--hidden-import=services \
--hidden-import=browser_manager \
--hidden-import=icon_manager \
--hidden-import=sound_manager \
$HIDDEN_IMPORTS \
loader.py

# --- 7. Ad-Hoc Code Signing (IMPORTANT FOR MACOS) ---
# Bina iske app "Damaged" bolkar open nahi hoga
echo "Applying Ad-Hoc Signature to .app bundle..."
codesign --force --deep --sign - "dist/${APP_NAME}.app"

# --- 8. Create the DMG ---
echo "Creating DMG package..."

if ! command -v create-dmg &> /dev/null; then
    echo "create-dmg could not be found. Please install it (brew install create-dmg)."
    exit 1
fi

# Remove old DMG if exists
if [ -f "$OUTPUT_DMG_NAME" ]; then
    rm "$OUTPUT_DMG_NAME"
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

echo "--------------------------------------------------"
echo "✅ Build complete!"
echo "📂 DMG File: ${OUTPUT_DMG_NAME}"
LATEST_CORE=$(ls dist/core_mac_v*.zip 2>/dev/null | head -n 1)
echo "📦 Core Update File: ${LATEST_CORE}"
echo "--------------------------------------------------"