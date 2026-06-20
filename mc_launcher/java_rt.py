"""
mc_launcher/java_rt.py — Gömülü Adoptium Java runtime yönetimi
"""

import os
import tarfile
import urllib.request
from typing import Optional

from mc_launcher.config import RUNTIME_DIR

# Adoptium Temurin JRE (Linux x64, GA, Java 25)
# ProxyPass, class file version 69.0 (Java 25) ile derlenmiş olduğundan
# burada 25 kullanıyoruz. Bunu güncellemek gerekirse hem URL'yi
# hem de klasör adını değiştirmek yeterli.
JAVA_URL = (
    "https://api.adoptium.net/v3/binary/latest/25/ga/linux/x64/"
    "jre/hotspot/normal/eclipse"
)


def _java_dir() -> str:
    # Versiyon değişikliklerinde eski runtime'ı bozmayalım diye
    # klasör adına ana sürümü ekliyoruz.
    return os.path.join(RUNTIME_DIR, "java-25")


def find_java() -> Optional[str]:
    """İndirilen Java runtime içindeki java binary'sini bulur."""
    base = _java_dir()
    if not os.path.isdir(base):
        return None
    for root, dirs, files in os.walk(base):
        if "java" in files:
            return os.path.join(root, "java")
    return None


def _safe_extract_tar(t: tarfile.TarFile, dest_dir: str) -> None:
    """
    Tar arşivini path traversal'a karşı korumalı şekilde aç.
    Python 3.12+'da filter='tar' kullan; daha eski sürümlerde manuel doğrula.
    """
    dest_real = os.path.realpath(dest_dir)
    try:
        # Python 3.12+: built-in güvenlik filtresi
        t.extractall(dest_dir, filter="tar")
        return
    except TypeError:
        # Python < 3.12
        pass

    members = t.getmembers()
    for m in members:
        member_path = os.path.realpath(os.path.join(dest_dir, m.name))
        if not (member_path == dest_real or member_path.startswith(dest_real + os.sep)):
            raise RuntimeError(f"Güvensiz arşiv yolu: {m.name}")
    t.extractall(dest_dir)


def ensure_java(on_status) -> Optional[str]:
    """
    Gerekirse Adoptium Java JRE indirip açar, java binary yolunu döner.
    Zaten varsa indirmez.
    """
    java_bin = find_java()
    if java_bin:
        return java_bin

    os.makedirs(_java_dir(), exist_ok=True)
    tar_path = os.path.join(_java_dir(), "jre.tar.gz")

    try:
        from mc_launcher.i18n import _t
        on_status(_t("progress_download_java"), "running")
        req = urllib.request.Request(
            JAVA_URL, headers={"User-Agent": "mc-gdk-launcher"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp, open(
            tar_path, "wb"
        ) as out_f:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                out_f.write(chunk)
                done += len(chunk)
                if total > 0:
                    percent = min(100, int(done * 100 / total))
                    done_mb = done / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    on_status(f"{_t('progress_download_java')} {done_mb:.2f} MB / {total_mb:.2f} MB ({percent}%)", "running")
                else:
                    on_status(f"{_t('progress_download_java')} ({done // 1024} KB)", "running")

        on_status(_t("java_extracting"), "running")
        with tarfile.open(tar_path, "r:gz") as t:
            _safe_extract_tar(t, _java_dir())

        if os.path.exists(tar_path):
            os.remove(tar_path)

        java_bin = find_java()
        if java_bin:
            os.chmod(java_bin, 0o755)
            on_status(_t("toast_java_download_ok"), "ok")
            return java_bin

        on_status(_t("java_err_binary"), "error")
        return None
    except Exception as e:
        on_status(f"{_t('err_title')}: {e}", "error")
        return None

def remove_java() -> bool:
    """Java runtime klasörünü siler."""
    import shutil
    base = _java_dir()
    if os.path.isdir(base):
        try:
            shutil.rmtree(base)
            return True
        except OSError:
            pass
    return False
