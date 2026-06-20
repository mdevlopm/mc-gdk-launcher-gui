"""
mc_launcher/proxypass.py — ProxyPass yardımcı fonksiyonları
"""

import os
import json
import urllib.request
from typing import Optional, Tuple

from mc_launcher.config import PROXYPASS_DIR


def find_proxypass(exe_path: str = "") -> Optional[str]:
    """
    ProxyPass.jar konumunu bulur.
    Öncelik:
      1) Minecraft.exe'nin yanındaki / üstündeki ProxyPass.jar
      2) Launcher'ın XDG data dizinindeki (PROXYPASS_DIR/ProxyPass.jar)
    """
    # Launcher'ın indirdiği jar
    jar_local = os.path.join(PROXYPASS_DIR, "ProxyPass.jar")
    if not exe_path:
        return jar_local if os.path.isfile(jar_local) else None

    parent = os.path.dirname(os.path.dirname(exe_path))
    for p in [
        os.path.join(parent, "ProxyPass.jar"),
        os.path.join(os.path.dirname(exe_path), "ProxyPass.jar"),
        jar_local,
    ]:
        if os.path.isfile(p):
            return p
    return None


def auth_json_path(exe_path: str = "") -> str:
    """ProxyPass auth.json dosyasının yolunu döner."""
    if exe_path:
        parent = os.path.dirname(os.path.dirname(exe_path))
        return os.path.join(parent, "auth.json")
    jar = find_proxypass(exe_path)
    if jar:
        return os.path.join(os.path.dirname(jar), "auth.json")
    return os.path.join(PROXYPASS_DIR, "auth.json")


def auth_json_exists(exe_path: str = "") -> bool:
    """ProxyPass auth.json dosyası var mı kontrol eder."""
    return os.path.isfile(auth_json_path(exe_path))


def config_yml_path(exe_path: str = "") -> Optional[str]:
    """ProxyPass config.yml dosyasının yolunu döner (JAR neredeyse orada)."""
    jar = find_proxypass(exe_path)
    if not jar:
        return None
    return os.path.join(os.path.dirname(jar), "config.yml")


def read_destination(exe_path: str) -> Tuple[str, str]:
    """config.yml'den hedef host ve port'u okur. Bulamazsa ('', '') döner."""
    cfg = read_proxypass_config(exe_path)
    return cfg.get("dest_host", ""), cfg.get("dest_port", "")


def write_destination(exe_path: str, host: str, port: str) -> bool:
    """config.yml'deki destination host/port'u günceller. Başarılıysa True döner."""
    cfg = read_proxypass_config(exe_path)
    cfg["dest_host"] = host
    cfg["dest_port"] = port
    return write_proxypass_config(exe_path, cfg)


def read_proxypass_config(exe_path: str) -> dict:
    """ProxyPass config.yml dosyasındaki tüm ayarları okur."""
    defaults = {
        "proxy_host": "0.0.0.0",
        "proxy_port": "19132",
        "dest_host": "127.0.0.1",
        "dest_port": "19132",
        "online_mode": True,
        "save_auth_details": True,
        "broadcast_session": False,
        "max_clients": 0
    }
    path = config_yml_path(exe_path)
    if not path or not os.path.isfile(path):
        return defaults
    
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        
    res = dict(defaults)
    current_block = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        
        # Check blocks
        if stripped.startswith("proxy:"):
            current_block = "proxy"
            continue
        elif stripped.startswith("destination:"):
            current_block = "destination"
            continue
        elif not line.startswith(" ") and ":" in stripped:
            current_block = None
            
        # Parse fields
        if ":" in stripped:
            parts = stripped.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            # Remove inline comments
            if "#" in val:
                val = val.split("#", 1)[0].strip()
                
            if current_block == "proxy":
                if key == "host":
                    res["proxy_host"] = val
                elif key == "port":
                    res["proxy_port"] = val
            elif current_block == "destination":
                if key == "host":
                    res["dest_host"] = val
                elif key == "port":
                    res["dest_port"] = val
            else:
                if key == "online-mode":
                    res["online_mode"] = val.lower() == "true"
                elif key == "save-auth-details":
                    res["save_auth_details"] = val.lower() == "true"
                elif key == "broadcast-session":
                    res["broadcast_session"] = val.lower() == "true"
                elif key == "max-clients":
                    try:
                        res["max_clients"] = int(val)
                    except ValueError:
                        pass
    return res


def write_proxypass_config(exe_path: str, settings: dict) -> bool:
    """ProxyPass config.yml dosyasına tüm ayarları yazar."""
    path = config_yml_path(exe_path)
    if not path:
        return False
    
    # Dosya yoksa şablon oluştur
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"""# ProxyPass Configuration
proxy:
  host: {settings.get('proxy_host', '127.0.0.1')}
  port: {settings.get('proxy_port', '19122')}

destination:
  host: {settings.get('dest_host', '127.0.0.1')}
  port: {settings.get('dest_port', '19132')}

online-mode: {str(settings.get('online_mode', True)).lower()}
save-auth-details: {str(settings.get('save_auth_details', True)).lower()}
broadcast-session: {str(settings.get('broadcast_session', False)).lower()}
max-clients: {settings.get('max_clients', 0)}
""")
        return True

    # Dosya varsa satır satır güncelle
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    new_lines = []
    current_block = None
    replaced_keys = set()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if stripped.startswith("proxy:"):
            current_block = "proxy"
            new_lines.append(line)
            i += 1
            continue
        elif stripped.startswith("destination:"):
            current_block = "destination"
            new_lines.append(line)
            i += 1
            continue
        elif stripped and not line.startswith(" ") and not stripped.startswith("#") and ":" in stripped:
            current_block = None
            
        if stripped and not stripped.startswith("#") and ":" in stripped:
            parts = stripped.split(":", 1)
            key = parts[0].strip()
            # Girintiyi tespit et
            indent = line[:line.find(key)]
            
            if current_block == "proxy":
                if key == "host":
                    new_lines.append(f"{indent}host: {settings.get('proxy_host', '127.0.0.1')}\n")
                    i += 1
                    continue
                elif key == "port":
                    new_lines.append(f"{indent}port: {settings.get('proxy_port', '19122')}\n")
                    i += 1
                    continue
            elif current_block == "destination":
                if key == "host":
                    new_lines.append(f"{indent}host: {settings.get('dest_host', '127.0.0.1')}\n")
                    i += 1
                    continue
                elif key == "port":
                    new_lines.append(f"{indent}port: {settings.get('dest_port', '19132')}\n")
                    i += 1
                    continue
            else:
                if key == "online-mode":
                    new_lines.append(f"online-mode: {str(settings.get('online_mode', True)).lower()}\n")
                    replaced_keys.add("online-mode")
                    i += 1
                    continue
                elif key == "save-auth-details":
                    new_lines.append(f"save-auth-details: {str(settings.get('save_auth_details', True)).lower()}\n")
                    replaced_keys.add("save-auth-details")
                    i += 1
                    continue
                elif key == "broadcast-session":
                    new_lines.append(f"broadcast-session: {str(settings.get('broadcast_session', False)).lower()}\n")
                    replaced_keys.add("broadcast-session")
                    i += 1
                    continue
                elif key == "max-clients":
                    new_lines.append(f"max-clients: {settings.get('max_clients', 0)}\n")
                    replaced_keys.add("max-clients")
                    i += 1
                    continue
        
        new_lines.append(line)
        i += 1

    # Eksik olanları ekle
    if "online-mode" not in replaced_keys:
        new_lines.append(f"online-mode: {str(settings.get('online_mode', True)).lower()}\n")
    if "save-auth-details" not in replaced_keys:
        new_lines.append(f"save-auth-details: {str(settings.get('save_auth_details', True)).lower()}\n")
    if "broadcast-session" not in replaced_keys:
        new_lines.append(f"broadcast-session: {str(settings.get('broadcast_session', False)).lower()}\n")
    if "max-clients" not in replaced_keys:
        new_lines.append(f"max-clients: {settings.get('max_clients', 0)}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    return True


PROXYPASS_API = "https://api.github.com/repos/Kas-tle/ProxyPass/releases/latest"


def ensure_proxypass(on_status) -> Optional[str]:
    """
    PROXYPASS_DIR altına ProxyPass.jar indirir (yoksa) ve yolunu döner.
    """
    os.makedirs(PROXYPASS_DIR, exist_ok=True)
    jar_path = os.path.join(PROXYPASS_DIR, "ProxyPass.jar")
    if os.path.isfile(jar_path):
        return jar_path

    try:
        from mc_launcher.i18n import _t
        on_status(_t("progress_download_proxypass"), "running")
        req = urllib.request.Request(
            PROXYPASS_API, headers={"User-Agent": "mc-gdk-launcher"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        asset = next(
            (a for a in data.get("assets", []) if a["name"].endswith(".jar")), None
        )
        if not asset:
            raise RuntimeError("ProxyPass.jar bulunamadı.")

        url = asset["browser_download_url"]
        req2 = urllib.request.Request(url, headers={"User-Agent": "mc-gdk-launcher"})
        with urllib.request.urlopen(req2, timeout=60) as resp, open(jar_path, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total > 0:
                    percent = min(100, int(done * 100 / total))
                    done_mb = done / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    on_status(f"{_t('progress_download_proxypass')} {done_mb:.2f} MB / {total_mb:.2f} MB ({percent}%)", "running")
                else:
                    on_status(f"{_t('progress_download_proxypass')} ({done // 1024} KB)", "running")
        on_status(_t("toast_proxypass_download_ok"), "ok")
        return jar_path
    except Exception as e:
        on_status(f"ProxyPass indirme hatası: {e}", "error")
        return None

def remove_proxypass() -> bool:
    """ProxyPass.jar dosyasını (varsa) siler."""
    jar_path = os.path.join(PROXYPASS_DIR, "ProxyPass.jar")
    if os.path.isfile(jar_path):
        try:
            os.remove(jar_path)
            return True
        except OSError:
            pass
    return False
