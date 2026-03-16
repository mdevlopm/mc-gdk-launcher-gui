#!/bin/bash

# Minecraft GDK Launcher Setup Script
# This script creates a desktop shortcut for the launcher.

set -e

# Get the absolute path of the directory where this script is located
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ICON_PATH="$PROJECT_DIR/assets/icon.png"
MAIN_PY="$PROJECT_DIR/main.py"

# Local share directories
APP_DIR="$HOME/.local/share/applications"
ICON_DEST_DIR="$HOME/.local/share/icons"

echo "------------------------------------------"
echo "Minecraft GDK Launcher Kurulumu Başlıyor..."
echo "------------------------------------------"

# Ensure directories exist
mkdir -p "$APP_DIR"
mkdir -p "$ICON_DEST_DIR"

# Copy Icon
if [ -f "$ICON_PATH" ]; then
    echo "[1/3] İkon kopyalanıyor..."
    cp "$ICON_PATH" "$ICON_DEST_DIR/mc_gdk_launcher.png"
else
    echo "HATA: assets/icon.png bulunamadı!"
    exit 1
fi

# Create Desktop Entry
echo "[2/3] Masaüstü kısayolu oluşturuluyor..."
DESKTOP_FILE="$APP_DIR/com.mc.gdk.launcher.desktop"

cat > "$DESKTOP_FILE" <<EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=Minecraft GDK Launcher
Comment=Minecraft GDK için modern başlatıcı
Exec=python3 "$MAIN_PY"
Icon=mc_gdk_launcher
Path=$PROJECT_DIR
Terminal=false
Categories=Game;
Keywords=minecraft;gdk;launcher;
StartupWMClass=com.mc.gdk.launcher
EOL

# Make main.py executable (optional but recommended)
chmod +x "$MAIN_PY"

echo "[3/3] İzinler ayarlanıyor..."
chmod +x "$DESKTOP_FILE"

echo "------------------------------------------"
echo "KURULUM TAMAMLANDI!"
echo "Artık uygulama menünüzde 'Minecraft GDK Launcher' ikonunu görebilirsiniz."
echo "------------------------------------------"
