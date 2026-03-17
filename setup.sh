#!/bin/bash

# Minecraft GDK Launcher Setup Script
# This script creates a desktop shortcut for the launcher.

set -e

# Get the absolute path of the directory where this script is located
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ICON_PNG="$PROJECT_DIR/assets/icon.png"
ICON_SVG="$PROJECT_DIR/assets/icon.svg"
MAIN_PY="$PROJECT_DIR/main.py"

# Use sudo only when needed/available
if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  echo "ERROR: This script requires root privileges to install system packages."
  echo "Please run as root or install 'sudo'."
  exit 1
fi

# Local share directories
APP_DIR="$HOME/.local/share/applications"
ICON_DEST_DIR="$HOME/.local/share/icons"

echo "------------------------------------------"
echo "Minecraft GDK Launcher Installation Starting..."
echo "------------------------------------------"

detect_pm() {
  if command -v apt-get >/dev/null 2>&1; then echo "apt"; return; fi
  if command -v dnf >/dev/null 2>&1; then echo "dnf"; return; fi
  if command -v pacman >/dev/null 2>&1; then echo "pacman"; return; fi
  if command -v zypper >/dev/null 2>&1; then echo "zypper"; return; fi
  echo "unknown"
}

install_deps() {
  local pm="$1"

  # System packages for GI/GTK4/Libadwaita are distro-managed; pip is not reliable here.
  case "$pm" in
    apt)
      $SUDO apt-get update
      $SUDO apt-get install -y \
        python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 xdg-utils ;;
    dnf)
      $SUDO dnf install -y python3 python3-gobject gtk4 libadwaita xdg-utils ;;
    pacman)
      $SUDO pacman -Sy --noconfirm python python-gobject gtk4 libadwaita xdg-utils ;;
    zypper)
      # openSUSE paket adları distroya göre değişebildiği için typeliblere de özellikle istekte bulunuyoruz.
      $SUDO zypper --non-interactive in \
        python3 python3-gobject gtk4 xdg-utils \
        libadwaita-1-0 typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0 \
        || $SUDO zypper --non-interactive in python3 python3-gobject gtk4 libadwaita xdg-utils ;;
    *)
      echo "WARNING: Package manager not found. Please install the dependencies manually from the README."
      return 0 ;;
  esac
}

PM="$(detect_pm)"
install_deps "$PM"

# Sanity checks
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found."
  exit 1
fi

# GI smoke-test: Gtk/Adw typelibs gerçekten yüklenmiş mi?
if ! python3 - <<'PY'
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw  # noqa: F401
print("GI OK")
PY
then
  echo "ERROR: GTK4/Libadwaita Python GI dependencies not found."
  echo "Note: These packages are not installed with pip, they must be installed with the system package manager."
  exit 1
fi

# Ensure directories exist
mkdir -p "$APP_DIR"
mkdir -p "$ICON_DEST_DIR"

# Copy Icon (prefer PNG, fallback SVG, else continue without custom icon)
echo "[1/3] İkon kurulumu..."
ICON_NAME="mc_gdk_launcher"
if [ -f "$ICON_PNG" ]; then
    cp "$ICON_PNG" "$ICON_DEST_DIR/${ICON_NAME}.png"
elif [ -f "$ICON_SVG" ]; then
    cp "$ICON_SVG" "$ICON_DEST_DIR/${ICON_NAME}.svg"
else
    echo "WARNING: assets/icon.png or assets/icon.svg not found. Continuing without custom icon."
    ICON_NAME="application-x-executable"
fi

# Create Desktop Entry
echo "[2/3] Creating desktop shortcut..."
DESKTOP_FILE="$APP_DIR/com.mc.gdk.launcher.desktop"

cat > "$DESKTOP_FILE" <<EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=Minecraft GDK Launcher
Comment=Minecraft GDK için modern başlatıcı
Exec=python3 "$MAIN_PY"
Icon=$ICON_NAME
Path=$PROJECT_DIR
Terminal=false
Categories=Game;
Keywords=minecraft;gdk;launcher;
StartupWMClass=com.mc.gdk.launcher
EOL

# Make main.py executable (optional but recommended)
chmod +x "$MAIN_PY"

echo "[3/3] Setting permissions..."
chmod +x "$DESKTOP_FILE"

echo "------------------------------------------"
echo "İnstall complated successfully"
echo "Now you can see 'Minecraft GDK Launcher' icon in your application menu."
echo "------------------------------------------"
