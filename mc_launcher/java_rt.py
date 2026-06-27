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
            candidate = os.path.join(root, "java")
            if os.path.isfile(candidate) and "bin" in root.split(os.sep):
                return candidate
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
        
        # Verify link targets if it is a symlink/hardlink to prevent symlink traversal
        if m.issym() or m.islnk():
            target_path = os.path.join(os.path.dirname(member_path), m.linkname)
            target_real = os.path.realpath(target_path)
            if not (target_real == dest_real or target_real.startswith(dest_real + os.sep)):
                raise RuntimeError(f"Güvensiz link hedefi: {m.linkname}")
    t.extractall(dest_dir)


def ensure_java(on_status) -> Optional[str]:
    """
    Gerekirse Adoptium Java JRE indirip açar, java binary yolunu döner.
    Zaten varsa indirmez.
    """
    java_bin = find_java()
    if java_bin:
        return java_bin

    tar_path = os.path.join(RUNTIME_DIR, "jre.tar.gz")
    tmp_tar_path = tar_path + ".tmp"
    temp_dir = _java_dir() + ".tmp"

    try:
        from mc_launcher.i18n import _t
        on_status(_t("progress_download_java"), "running")
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        req = urllib.request.Request(
            JAVA_URL, headers={"User-Agent": "mc-gdk-launcher"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp, open(
            tmp_tar_path, "wb"
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

        if os.path.exists(tmp_tar_path):
            os.replace(tmp_tar_path, tar_path)

        on_status(_t("java_extracting"), "running")
        
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        with tarfile.open(tar_path, "r:gz") as t:
            _safe_extract_tar(t, temp_dir)

        # Atomic directory swap
        if os.path.exists(_java_dir()):
            shutil.rmtree(_java_dir(), ignore_errors=True)
        os.rename(temp_dir, _java_dir())

        if os.path.exists(tar_path):
            try:
                os.remove(tar_path)
            except OSError:
                pass

        java_bin = find_java()
        if java_bin:
            os.chmod(java_bin, 0o755)
            import subprocess
            try:
                subprocess.run([java_bin, "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except PermissionError:
                on_status("Hata: Java çalıştırılamadı. Kurulum dizini 'noexec' ile bağlanmış olabilir (örn. /tmp).", "error")
                return None
            except Exception as e:
                print(f"[Java] Test execution failed: {e}")
                
            on_status(_t("toast_java_download_ok"), "ok")
            return java_bin

        on_status(_t("java_err_binary"), "error")
        return None
    except Exception as e:
        on_status(f"{_t('err_title')}: {e}", "error")
        return None
    finally:
        if os.path.exists(tmp_tar_path):
            try:
                os.remove(tmp_tar_path)
            except OSError:
                pass
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


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

