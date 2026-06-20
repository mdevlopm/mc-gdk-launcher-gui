#!/usr/bin/env bash
# Minecraft GDK Launcher — kurulum betiği
# Bağımlılıkları kurar, uygulamayı ~/.local/share altına kopyalar,
# masaüstü kısayolu ve komut satırı başlatıcısı oluşturur.

set -euo pipefail

APP_ID="com.mc.gdk.launcher"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/${APP_ID}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DEST_DIR_SVG="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
ICON_DEST_DIR_PNG="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

WRAPPER="${BIN_DIR}/mc-gdk-launcher"
DESKTOP_FILE="${APP_DIR}/${APP_ID}.desktop"

echo "=========================================="
echo " Minecraft GDK Launcher — Kurulum"
echo "=========================================="
echo "Kaynak : $PROJECT_DIR"
echo "Hedef  : $INSTALL_DIR"
echo

# sudo yalnızca sistem paketleri için
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

detect_pm() {
  if command -v apt-get >/dev/null 2>&1; then echo "apt"; return; fi
  if command -v dnf >/dev/null 2>&1; then echo "dnf"; return; fi
  if command -v pacman >/dev/null 2>&1; then echo "pacman"; return; fi
  if command -v zypper >/dev/null 2>&1; then echo "zypper"; return; fi
  echo "unknown"
}

install_deps() {
  local pm="$1"
  case "$pm" in
    apt)
      if [[ -n "$SUDO" ]]; then
        $SUDO apt-get update
        $SUDO apt-get install -y \
          python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
          xdg-utils python3-cairo gir1.2-rsvg-2.0
      fi
      ;;
    dnf)
      if [[ -n "$SUDO" ]]; then
        $SUDO dnf install -y \
          python3 python3-gobject gtk4 libadwaita xdg-utils \
          python3-cairo rsvg2
      fi
      ;;
    pacman)
      if [[ -n "$SUDO" ]]; then
        $SUDO pacman -Sy --noconfirm \
          python python-gobject gtk4 libadwaita xdg-utils \
          python-cairo rsvg
      fi
      ;;
    zypper)
      if [[ -n "$SUDO" ]]; then
        $SUDO zypper --non-interactive in \
          python3 python3-gobject gtk4 libadwaita xdg-utils \
          python3-cairo typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0 \
          librsvg-2-2 || $SUDO zypper --non-interactive in \
          python3 python3-gobject gtk4 libadwaita xdg-utils
      fi
      ;;
    *)
      echo "UYARI: Paket yöneticisi bulunamadı. Bağımlılıkları README'den manuel kurun."
      ;;
  esac
}

PM="$(detect_pm)"
echo "[1/5] Bağımlılıklar kontrol ediliyor ($PM)..."
install_deps "$PM"

if ! command -v python3 >/dev/null 2>&1; then
  echo "HATA: python3 bulunamadı."
  exit 1
fi

if ! python3 - <<'PY'
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw  # noqa: F401
print("GI OK")
PY
then
  echo "HATA: GTK4 / Libadwaita Python bağımlılıkları eksik."
  echo "Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
  exit 1
fi

echo "[2/5] Uygulama dosyaları kopyalanıyor..."
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$APP_DIR"

rsync -a --delete \
  --exclude '.git/' \
  --exclude 'GDK-Proton10-32/' \
  --exclude 'flatpak/build/' \
  --exclude 'flatpak/repo/' \
  --exclude 'flatpak/.build-src/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$PROJECT_DIR/main.py" \
  "$PROJECT_DIR/mc_launcher" \
  "$PROJECT_DIR/assets" \
  "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR/main.py"

echo "[3/5] İkon kuruluyor..."
mkdir -p "$ICON_DEST_DIR_SVG" "$ICON_DEST_DIR_PNG"

ICON_SRC=""
if [[ -f "$PROJECT_DIR/assets/minecraft_gdk_launcher_logo.svg" ]]; then
  ICON_SRC="$PROJECT_DIR/assets/minecraft_gdk_launcher_logo.svg"
elif [[ -f "$PROJECT_DIR/assets/icon.svg" ]]; then
  ICON_SRC="$PROJECT_DIR/assets/icon.svg"
fi

if [[ -n "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$ICON_DEST_DIR_SVG/${APP_ID}.svg"
  if python3 "$PROJECT_DIR/render_icon.py" "$ICON_SRC" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/" 2>/dev/null; then
    echo "  PNG ikonlar oluşturuldu."
  else
    echo "  UYARI: PNG ikon oluşturulamadı (cairo/rsvg eksik olabilir)."
  fi
else
  echo "  UYARI: SVG ikon bulunamadı."
fi

echo "[4/5] Komut satırı başlatıcısı oluşturuluyor..."
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/main.py" "\$@"
EOF
chmod +x "$WRAPPER"

echo "[5/5] Masaüstü kısayolu oluşturuluyor..."
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Minecraft GDK Launcher
GenericName=Game Launcher
Comment=Minecraft Bedrock (GDK) için Linux başlatıcısı
Exec=${WRAPPER}
TryExec=${WRAPPER}
Icon=${APP_ID}
Path=${INSTALL_DIR}
Terminal=false
Categories=Game;
Keywords=minecraft;bedrock;gdk;launcher;proton;
StartupNotify=true
StartupWMClass=com.mc.gdk.launcher
EOF
chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

echo
echo "=========================================="
echo " Kurulum tamamlandı!"
echo "=========================================="
echo "Uygulama menüsünden veya şu komutla başlatın:"
echo "  mc-gdk-launcher"
echo
echo "Flatpak ile kurmak için:"
echo "  ./flatpak/install-local.sh"
echo "=========================================="
