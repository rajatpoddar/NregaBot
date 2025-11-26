#!/bin/bash

# --- Define app details here ---
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

OUTPUT_DMG_NAME="dist/${APP_NAME}-v${APP_VERSION}-macOS.dmg"

# --- Step 1: Run PyInstaller on LOADER.PY ---
echo "Building the Loader application with PyInstaller..."

# Note: Separator ':' use kiya hai (Mac format)
# aur hidden imports add kiye hain.

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

# Agar create-dmg install nahi hai to error handle karein
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

echo "Build complete! DMG is located at: ${OUTPUT_DMG_NAME}"