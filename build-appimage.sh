#!/usr/bin/env bash
# Minecraft GDK Launcher — AppImage packaging script
# Creates an AppImage of the launcher using host python3 and GTK4.

set -euo pipefail

APP_ID="com.mc.gdk.launcher"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
APPDIR="${PROJECT_DIR}/build-appimage/AppDir"
OUT_DIR="${PROJECT_DIR}/build-appimage"

echo "=========================================="
echo " Minecraft GDK Launcher — AppImage Build"
echo "=========================================="

# 1. Prepare clean directories
echo "[1/4] Preparing directories..."
rm -rf "$OUT_DIR"
mkdir -p "$APPDIR"

# 2. Copy application source files
echo "[2/4] Copying source files..."
cp -a "$PROJECT_DIR/main.py" "$APPDIR/main.py"
cp -a "$PROJECT_DIR/mc_launcher" "$APPDIR/mc_launcher"
cp -a "$PROJECT_DIR/assets" "$APPDIR/assets"

# Clean caches or temporary files in the copy
find "$APPDIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$APPDIR" -name "*.pyc" -delete 2>/dev/null || true

# 3. Create desktop file, icon and AppRun wrapper
echo "[3/4] Structuring AppDir metadata..."
# Copy desktop file
cp "$PROJECT_DIR/flatpak/com.mc.gdk.launcher.desktop" "$APPDIR/com.mc.gdk.launcher.desktop"

# Set up icons
ICON_SRC=""
if [[ -f "$PROJECT_DIR/assets/minecraft_gdk_launcher_logo.svg" ]]; then
  ICON_SRC="$PROJECT_DIR/assets/minecraft_gdk_launcher_logo.svg"
elif [[ -f "$PROJECT_DIR/assets/icon.svg" ]]; then
  ICON_SRC="$PROJECT_DIR/assets/icon.svg"
fi

if [[ -n "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$APPDIR/com.mc.gdk.launcher.svg"
  ln -sf "com.mc.gdk.launcher.svg" "$APPDIR/.DirIcon"
else
  echo "WARNING: No logo icon found!"
fi

# Create AppRun entrypoint
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PYTHONPATH="${HERE}${PYTHONPATH:+:$PYTHONPATH}"

# Check for GTK4 and PyGObject dependencies on the host
if ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' 2>/dev/null; then
    echo "ERROR: Missing PyGObject, GTK4 or Libadwaita dependencies."
    echo "Please install them via your package manager first."
    exit 1
fi

exec python3 "${HERE}/main.py" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# 4. Download appimagetool and compile AppImage
echo "[4/4] Generating AppImage..."
APPIMAGE_TOOL="${OUT_DIR}/appimagetool"
if [[ ! -f "$APPIMAGE_TOOL" ]]; then
  echo "Downloading appimagetool..."
  APPIMAGETOOL_VERSION="continuous"
  curl -Lo "$APPIMAGE_TOOL" "https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"
  chmod +x "$APPIMAGE_TOOL"
fi

# Set ARCH environmental variable required by appimagetool
export ARCH=x86_64

# Package the AppDir into an AppImage
# Pass --appimage-extract-and-run to make sure it doesn't fail if FUSE is not installed/enabled
echo "Running appimagetool..."
"$APPIMAGE_TOOL" --appimage-extract-and-run "$APPDIR" "${PROJECT_DIR}/Minecraft_GDK_Launcher-v3.1-x86_64.AppImage"

echo
echo "=========================================="
echo " AppImage build complete!"
echo " Output path: ${PROJECT_DIR}/Minecraft_GDK_Launcher-v3.1-x86_64.AppImage"
echo "=========================================="
