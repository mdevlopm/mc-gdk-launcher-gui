"""
mc_launcher/proton.py — GDK-Proton bul, indir ve kur
"""

import os
import glob
import json
import tarfile
import threading
import urllib.request
from typing import Callable, Optional

from mc_launcher.config import SCRIPT_DIR, GDK_API


def find_proton() -> Optional[str]:
    """Script dizininde GDK-Proton binary'sini arar, bulursa yolunu döner."""
    hits = glob.glob(os.path.join(SCRIPT_DIR, "GDK-Proton*", "proton"))
    return sorted(hits)[-1] if hits else None


def _do_extract(tar_path: str, on_status: Callable, remove_after: bool = False):
    """Tar arşivini SCRIPT_DIR altına aç. on_status(msg, style) callback'i ile ilerlemeyi bildir."""
    try:
        on_status("Arşiv açılıyor...", "running")
        with tarfile.open(tar_path, "r:gz") as t:
            members = t.getmembers()
            total = len(members)
            for i, m in enumerate(members, 1):
                try:
                    try:
                        t.extract(m, SCRIPT_DIR, filter="tar")
                    except TypeError:
                        t.extract(m, SCRIPT_DIR)
                except Exception as me:
                    print(f"[SKIP] {m.name}: {me}")
                if i % 100 == 0 or i == total:
                    on_status(f"Açılıyor... {int(i * 100 / total)}%", "running")
        if remove_after and os.path.exists(tar_path):
            os.remove(tar_path)
        p = find_proton()
        if p:
            os.chmod(p, 0o755)
            on_status(f"GDK-Proton hazır: {os.path.basename(os.path.dirname(p))}", "ok")
            return True
        else:
            on_status("'proton' binary bulunamadı.", "error")
            return False
    except Exception as e:
        on_status(f"Hata: {e}", "error")
        return False


def download_proton(on_status: Callable, on_done: Callable):
    """
    GitHub API'den GDK-Proton'un son sürümünü indirir ve kurar.
    on_status(msg, style), on_done(success: bool) background thread'den çağrılır.
    """
    def worker():
        try:
            on_status("GitHub sorgulanıyor...", "running")
            req = urllib.request.Request(GDK_API, headers={"User-Agent": "mc-gdk-launcher"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            asset = next(
                (a for a in data.get("assets", []) if a["name"].endswith(".tar.gz")), None
            )
            if not asset:
                raise RuntimeError("tar.gz bulunamadı.")
            tar_path = os.path.join(SCRIPT_DIR, asset["name"])

            def hook(b, bs, total):
                if total > 0:
                    on_status(f"İndiriliyor... {min(100, int(b * bs * 100 / total))}%", "running")

            on_status(f"İndiriliyor: {asset['name']}", "running")
            urllib.request.urlretrieve(asset["browser_download_url"], tar_path, reporthook=hook)
            ok = _do_extract(tar_path, on_status, remove_after=True)
            on_done(ok)
        except Exception as e:
            on_status(f"İndirme hatası: {e}", "error")
            on_done(False)

    threading.Thread(target=worker, daemon=True).start()


def install_from_file(tar_path: str, on_status: Callable, on_done: Callable):
    """Kullanıcının seçtiği .tar.gz dosyasından GDK-Proton'u kurar."""
    def worker():
        ok = _do_extract(tar_path, on_status, remove_after=False)
        on_done(ok)

    threading.Thread(target=worker, daemon=True).start()
