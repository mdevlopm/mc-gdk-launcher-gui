#!/usr/bin/env sh
# Flatpak içinde /app altına pip ile kurulu Python paketlerini (cryptography vb.)
# hem sistem site-packages'ı hem de uygulama kütüphanesi ile birlikte yükler.
PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
export PYTHONPATH="/app/lib/python${PYVER}/site-packages:/app/lib/mc-gdk-launcher:${PYTHONPATH:-}"
exec python3 /app/lib/mc-gdk-launcher/main.py "$@"
