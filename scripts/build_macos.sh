#!/bin/bash

# --- 1. Clean previous builds ---
echo "Cleaning up previous builds..."
rm -rf build
rm -rf dist/*.app
rm -rf dist/*.dmg

# --- 2. Define app details ---
APP_NAME="NREGABot"
ICON_FILE="assets/app_icon.icns"

# Check Icon
if [ ! -f "$ICON_FILE" ]; then
    echo "⚠️ Warning: Icon file not found at $ICON_FILE. Using default."
fi

# --- 3. Get Version ---
if [ ! -f "src/config.py" ]; then
    echo "!!!!!! ERROR: config.py not found in src/ !!!!!!"
    exit 1
fi
APP_VERSION=$(grep "APP_VERSION =" src/config.py | sed 's/.*"\(.*\)".*/\1/')
echo "Found version: $APP_VERSION"

OUTPUT_DMG_NAME="dist/${APP_NAME}-v${APP_VERSION}-macOS.dmg"

# --- 4. Generate Core Update Zip ---
echo "Generating core update package..."
if [ -f "scripts/build_update.py" ]; then
    python3 scripts/build_update.py
else
    echo "⚠️ build_update.py not found in scripts/! Skipping."
fi

# --- 5. Generate Hidden Imports (CRITICAL FIX) ---
# Ye loop tabs folder ke andar saari files ko dhoond kar hidden-import me add karega
echo "Generating hidden imports for tabs..."
HIDDEN_IMPORTS=""
for file in src/tabs/*.py; do
    filename=$(basename "$file" .py)
    if [ "$filename" != "__init__" ]; then
        HIDDEN_IMPORTS="$HIDDEN_IMPORTS --hidden-import=src.tabs.$filename"
    fi
done

# --- 6. Build Loader with PyInstaller ---
echo "Building Application..."

pyinstaller --noconfirm --clean --windowed --name "${APP_NAME}" \
--icon="$ICON_FILE" \
--add-data="assets:assets" \
--add-data="config:config" \
--add-data="src:src" \
--add-data="web:web" \
--add-data=".env:." \
--collect-all customtkinter \
--collect-data fpdf \
--hidden-import=selenium \
--hidden-import=webdriver_manager \
--hidden-import=webdriver_manager.chrome \
--hidden-import=webdriver_manager.firefox \
--hidden-import=webdriver_manager.microsoft \
--collect-submodules=webdriver_manager \
--hidden-import=pandas \
--hidden-import=PIL \
--hidden-import=requests \
--hidden-import=fpdf \
--hidden-import=babel.numbers \
--hidden-import=tkcalendar \
--hidden-import=getmac \
--hidden-import=packaging \
--hidden-import=main_app \
--collect-submodules=src.tabs \
$HIDDEN_IMPORTS \
loader.py

# --- 7. Ad-Hoc Signing (Gatekeeper Fix) ---
echo "Signing app to prevent 'Damaged' error..."
codesign --force --deep --sign - "dist/${APP_NAME}.app"

# --- 8. Create DMG ---
echo "Creating DMG..."
if command -v create-dmg &> /dev/null; then
    [ -f "$OUTPUT_DMG_NAME" ] && rm "$OUTPUT_DMG_NAME"
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
else
    echo "⚠️ create-dmg not found. Skipping DMG creation."
fi

echo "✅ Build Complete!"