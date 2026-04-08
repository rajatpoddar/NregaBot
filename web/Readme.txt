## Commands for build the app

# For Windows

pyinstaller --noconfirm --windowed --name "NREGA-Dashboard" --icon="app_icon.ico" --add-data="logo.png;." --add-data="payment_qr.png;." --add-data="theme.json;." --add-data="assets;assets" --add-data=".env;." --add-data="jobcard.jpeg;." --collect-data fpdf main_app.py


# For MacOS

# Add the new --add-data flag for the default photo
pyinstaller --noconfirm --onefile --windowed --name "NREGA-Dashboard" --icon="app_icon.icns" --add-data="logo.png:." --add-data="payment_qr.png:." --add-data="jobcard.jpeg:." main_app.py


## Convert .app to .dmg Commands

create-dmg \
  --volname "NREGA Dashboard Installer" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 120 \
  --icon "NREGA-Dashboard.app" 175 190 \
  --app-drop-link 425 190 \
  "NREGA-Dashboard-v2.4.0.dmg" \
  "path/to/your/NREGA-Dashboard.app"

  