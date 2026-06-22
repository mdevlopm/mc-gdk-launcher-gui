"""
mc_launcher/config.py — Sabitler ve yapılandırma yönetimi
"""

import os
import json

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# XDG tabanlı dizinler
_XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
_XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
APP_ID = "mc-gdk-linux-launcher"

DATA_DIR = os.path.join(_XDG_DATA_HOME, APP_ID)
CONFIG_DIR = os.path.join(_XDG_CONFIG_HOME, APP_ID)

# Eski sürümlerle uyumluluk için: prefix dizinini XDG'ye taşıdık
COMPAT_DATA = os.path.join(DATA_DIR, "prefix")

# Runtime / bileşen dizinleri
RUNTIME_DIR = os.path.join(DATA_DIR, "runtime")
PROXYPASS_DIR = os.path.join(DATA_DIR, "proxypass")
PROTON_DIR = os.path.join(DATA_DIR, "proton")

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
GDK_API = "https://api.github.com/repos/Weather-OS/GDK-Proton/releases/latest"

# Kayıtlı sunucu listesi — varsayılanlar (sabit, silinemez).
SERVER_LIST = [
    {"name": "Localhost", "host": "127.0.0.1",              "port": "19132"},
    {"name": "Hive",      "host": "fr.hivebedrock.network", "port": "19132"},
]

DEFAULT_CFG = {
    "exe_path": "",
    "injector_path": "",
    "injector_autorun": False,
    "language": "en",
    "play_background": "default",
    "play_background_custom": "",
    "login_method": "proxypass", # "proxypass" or "ingame"
    # Kullanıcının kendi eklediği sunucular:
    # [{"name": str, "host": str, "port": str}, ...]
    "servers": [],
}


import copy

def deep_merge(dict1: dict, dict2: dict) -> dict:
    """Recursively merges dict2 into dict1."""
    for key, value in dict2.items():
        if isinstance(value, dict) and key in dict1 and isinstance(dict1[key], dict):
            deep_merge(dict1[key], value)
        else:
            dict1[key] = copy.deepcopy(value)
    return dict1


def load_cfg() -> dict:
    """Config dosyasını okur, yoksa ya da bozuksa varsayılanlarla birleştirir."""
    cfg = copy.deepcopy(DEFAULT_CFG)
    # Önce yeni XDG konumu, yoksa eski SCRIPT_DIR konumuna bak.
    paths = [CONFIG_FILE, os.path.join(SCRIPT_DIR, "mc_launcher_config.json")]
    for path in paths:
        try:
            if not os.path.isfile(path):
                continue
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                deep_merge(cfg, data)
                break
        except Exception:
            continue
    return cfg


def save_cfg(cfg: dict) -> None:
    """Config dosyasını kaydeder."""
    # Eksik anahtarlar varsa tamamla
    out = copy.deepcopy(DEFAULT_CFG)
    deep_merge(out, cfg or {})
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp_path = CONFIG_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, CONFIG_FILE)
    except OSError as e:
        print(f"[Config] save_cfg error: {e}")
