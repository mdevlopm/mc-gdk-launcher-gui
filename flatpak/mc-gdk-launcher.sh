#!/usr/bin/env sh
export PYTHONPATH="/app/lib/mc-gdk-launcher:${PYTHONPATH:-}"
exec python3 /app/lib/mc-gdk-launcher/main.py "$@"
