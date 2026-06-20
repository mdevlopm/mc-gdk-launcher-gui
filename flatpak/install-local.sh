#!/usr/bin/env bash
# Flatpak paketini derler ve kullanıcı hesabına kurar.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_DIR="$SCRIPT_DIR/repo"
REMOTE_NAME="mc-gdk-launcher-local"
APP_ID="com.mc.gdk.launcher"

echo "=========================================="
echo " Minecraft GDK Launcher — Flatpak Kurulum"
echo "=========================================="

"$SCRIPT_DIR/build.sh"

echo
echo "Flatpak remote ekleniyor / güncelleniyor..."
flatpak remote-add --user --no-gpg-verify --if-not-exists \
  "$REMOTE_NAME" "file://$REPO_DIR" 2>/dev/null || \
flatpak remote-modify --user "$REMOTE_NAME" "file://$REPO_DIR"

echo "Paket kuruluyor..."
flatpak --user install -y "$REMOTE_NAME" "$APP_ID"

echo
echo "=========================================="
echo " Kurulum tamamlandı!"
echo "=========================================="
echo "Başlatmak için:"
echo "  flatpak run $APP_ID"
echo
echo "Uygulama menüsünde 'Minecraft GDK Launcher' olarak görünür."
echo "=========================================="
