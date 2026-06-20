#!/usr/bin/env bash
# Flatpak paketini derler ve yerel bir repo oluşturur.
# Gereksinim: flatpak, flatpak-builder, flathub remote

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)"
SRC_DIR="$PROJECT_DIR/.flatpak-src"
BUILD_DIR="$SCRIPT_DIR/build"
REPO_DIR="$SCRIPT_DIR/repo"
MANIFEST="$SCRIPT_DIR/com.mc.gdk.launcher.yml"

echo "=========================================="
echo " Minecraft GDK Launcher — Flatpak Derleme"
echo "=========================================="

if ! command -v flatpak >/dev/null 2>&1; then
  echo "HATA: flatpak kurulu değil."
  echo "Fedora: sudo dnf install flatpak flatpak-builder"
  exit 1
fi

if ! command -v flatpak-builder >/dev/null 2>&1; then
  echo "HATA: flatpak-builder kurulu değil."
  echo "Fedora: sudo dnf install flatpak-builder"
  exit 1
fi

if ! flatpak remote-list | grep -q flathub; then
  echo "Flathub remote ekleniyor..."
  flatpak remote-add --if-not-exists flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo
fi

echo "[1/3] Kaynak dosyalar hazırlanıyor..."
rm -rf "$SRC_DIR"
mkdir -p "$SRC_DIR"

rsync -a \
  --exclude '.git/' \
  --exclude 'GDK-Proton10-32/' \
  --exclude '.flatpak-src/' \
  --exclude 'flatpak/build/' \
  --exclude 'flatpak/repo/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$PROJECT_DIR/" "$SRC_DIR/"

echo "[2/3] Flatpak derleniyor (bu işlem birkaç dakika sürebilir)..."
mkdir -p "$BUILD_DIR" "$REPO_DIR"

flatpak-builder \
  --force-clean \
  --install-deps-from=flathub \
  --repo="$REPO_DIR" \
  "$BUILD_DIR" \
  "$MANIFEST"

echo "[3/3] Derleme tamamlandı."
echo
echo "Yerel repo: $REPO_DIR"
echo
echo "Kurulum için:"
echo "  flatpak --user remote-add --no-gpg-verify --if-not-exists mc-gdk-launcher file://$REPO_DIR"
echo "  flatpak --user install -y mc-gdk-launcher com.mc.gdk.launcher"
echo
echo "Veya tek komut:"
echo "  $SCRIPT_DIR/install-local.sh"
