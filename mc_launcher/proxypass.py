"""
mc_launcher/proxypass.py — ProxyPass yardımcı fonksiyonları
"""

import os
import re
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


def auth_json_exists(exe_path: str = "") -> bool:
    """Minecraft'ın üst dizininde auth.json var mı kontrol eder."""
    if not exe_path:
        return False
    parent = os.path.dirname(os.path.dirname(exe_path))
    return os.path.isfile(os.path.join(parent, "auth.json"))


def config_yml_path(exe_path: str = "") -> Optional[str]:
    """ProxyPass config.yml dosyasının yolunu döner."""
    if not exe_path:
        return None
    return os.path.join(os.path.dirname(os.path.dirname(exe_path)), "config.yml")


def read_destination(exe_path: str) -> Tuple[str, str]:
    """config.yml'den hedef host ve port'u okur. Bulamazsa ('', '') döner."""
    path = config_yml_path(exe_path)
    if not path or not os.path.isfile(path):
        return "", ""
    with open(path) as f:
        txt = f.read()
    # destination: bloğundan sonraki host ve port'u yakala.
    # re.DOTALL ile satır sonlarını atlayabiliriz.
    host = re.search(r"destination:.*?host:\s*([^\s#\n]+)", txt, re.DOTALL)
    port = re.search(r"destination:.*?port:\s*(\d+)", txt, re.DOTALL)
    return (
        host.group(1).strip() if host else "",
        port.group(1).strip() if port else "",
    )


def write_destination(exe_path: str, host: str, port: str) -> bool:
    """config.yml'deki destination host/port'u günceller. Başarılıysa True döner."""
    path = config_yml_path(exe_path)
    if not path or not os.path.isfile(path):
        return False
    with open(path) as f:
        txt = f.read()
    # destination: bloğunu bul ve içindeki host/port alanlarını seçici şekilde değiştir.
    # Önce bloğu bulalım (basit olması için tüm dosyada host/port arıyoruz ama
    # destination altında olduklarından emin olmak için daha spesifik olabiliriz).
    # Ancak ProxyPass config.yml yapısı basit olduğu için genel re.sub yeterli olabilir.
    # Daha güvenli olması için bloğu yakalayıp sadece orada işlem yapıyoruz:
    def repl_host(m):
        return re.sub(r"(host:\s*)(.+)", r"\g<1>" + host, m.group(0))
    def repl_port(m):
        return re.sub(r"(port:\s*)(\d+)", r"\g<1>" + port, m.group(0))

    txt = re.sub(r"destination:.*?host:\s*[^\s#\n]+", repl_host, txt, flags=re.DOTALL)
    txt = re.sub(r"destination:.*?port:\s*\d+", repl_port, txt, flags=re.DOTALL)
    with open(path, "w") as f:
        f.write(txt)
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
        on_status("ProxyPass indiriliyor...", "running")
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
        urllib.request.urlretrieve(url, jar_path)
        on_status("ProxyPass indirildi ✓", "ok")
        return jar_path
    except Exception as e:
        on_status(f"ProxyPass indirme hatası: {e}", "error")
        return None
