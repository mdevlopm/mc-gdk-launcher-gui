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

from mc_launcher.config import SCRIPT_DIR, DATA_DIR, PROTON_DIR, GDK_API


def _proton_search_dirs():
    """Önce geliştirme/bundled dizin, sonra kullanıcı veri dizini ve Steam/Flatpak Steam dizinleri."""
    seen = set()
    search_paths = [
        SCRIPT_DIR,
        PROTON_DIR,
        os.path.expanduser("~/.steam/steam/compatibilitytools.d"),
        os.path.expanduser("~/.steam/root/compatibilitytools.d"),
        os.path.expanduser("~/.local/share/Steam/compatibilitytools.d"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/steam/compatibilitytools.d"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d")
    ]
    for d in search_paths:
        if os.path.isdir(d):
            real = os.path.realpath(d)
            if real not in seen:
                seen.add(real)
                yield real


def _install_dir() -> str:
    """İndirme ve kurulum hedefi (Flatpak/sandbox uyumlu yazılabilir dizin)."""
    os.makedirs(PROTON_DIR, exist_ok=True)
    return PROTON_DIR


def _version_key(path: str):
    import re
    parts = re.findall(r'\d+', os.path.basename(os.path.dirname(path)))
    return [int(p) for p in parts]


def find_proton(login_method: str = "proxypass") -> Optional[str]:
    """GDK-Proton binary'sini arar, bulursa yolunu döner."""
    hits = []
    for base in _proton_search_dirs():
        for path in glob.glob(os.path.join(base, "GDK-Proton*", "proton")):
            hits.append(path)
            
    if not hits:
        return None

    xuser_hits = [p for p in hits if "xuser" in os.path.basename(os.path.dirname(p)).lower()]
    non_xuser_hits = [p for p in hits if p not in xuser_hits]

    if login_method == "ingame":
        if xuser_hits:
            return sorted(set(xuser_hits), key=_version_key)[-1]
    else: # proxypass
        if non_xuser_hits:
            return sorted(set(non_xuser_hits), key=_version_key)[-1]
        
    return None


def _do_extract(tar_path: str, on_status: Callable, remove_after: bool = False, login_method: str = "proxypass"):
    """Tar arşivini kurulum dizinine aç."""
    from mc_launcher.i18n import _t
    dest_dir = _install_dir()
    try:
        on_status(_t("progress_extract_archive"), "running")
        with tarfile.open(tar_path, "r:gz") as t:
            members = t.getmembers()
            total = len(members)
            dest_real = os.path.realpath(dest_dir)
            for i, m in enumerate(members, 1):
                try:
                    try:
                        t.extract(m, dest_dir, filter="tar")
                    except TypeError:
                        member_path = os.path.realpath(os.path.join(dest_dir, m.name))
                        if not (member_path == dest_real or member_path.startswith(dest_real + os.sep)):
                            raise RuntimeError(f"Güvensiz arşiv yolu: {m.name}")
                        
                        if m.issym() or m.islnk():
                            target_path = os.path.join(os.path.dirname(member_path), m.linkname)
                            target_real = os.path.realpath(target_path)
                            if not (target_real == dest_real or target_real.startswith(dest_real + os.sep)):
                                raise RuntimeError(f"Güvensiz link hedefi: {m.linkname}")
                                
                        t.extract(m, dest_dir)
                except Exception as me:
                    print(f"[SKIP] {m.name}: {me}")
                if i % 100 == 0 or i == total:
                    on_status(f"{_t('progress_extracting')} {int(i * 100 / total)}%", "running")
        if remove_after and os.path.exists(tar_path):
            os.remove(tar_path)
        p = find_proton(login_method)
        if p:
            os.chmod(p, 0o755)
            on_status(_t("status_proton_ready", name=os.path.basename(os.path.dirname(p))), "ok")
            return True
        on_status(_t("err_proton_binary_not_found"), "error")
        return False
    except Exception as e:
        on_status(f"Hata: {e}", "error")
        return False


def download_proton(on_status: Callable, on_done: Callable, login_method: str = "proxypass"):
    """
    GitHub API'den GDK-Proton'un son sürümünü indirir ve kurar.
    on_status(msg, style), on_done(success: bool) background thread'den çağrılır.
    """
    from mc_launcher.i18n import _t
    use_xuser = (login_method == "ingame")

    def worker():
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            on_status(_t("progress_query_github"), "running")
            if use_xuser:
                api_url = "https://api.github.com/repos/Wyze3306/BedrockOnLinux/releases"
            else:
                api_url = GDK_API
            req = urllib.request.Request(api_url, headers={"User-Agent": "mc-gdk-launcher"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            
            asset = None
            if use_xuser:
                if isinstance(data, list):
                    for release in data:
                        asset = next(
                            (a for a in release.get("assets", []) if a["name"].endswith(".tar.gz") and "xuser" in a["name"].lower()), None
                        )
                        if asset:
                            break
            else:
                if isinstance(data, list):
                    for release in data:
                        asset = next(
                            (a for a in release.get("assets", []) if a["name"].endswith(".tar.gz") and "xuser" not in a["name"].lower()), None
                        )
                        if asset:
                            break
                else:
                    asset = next(
                        (a for a in data.get("assets", []) if a["name"].endswith(".tar.gz") and "xuser" not in a["name"].lower()), None
                    )

            if not asset:
                raise RuntimeError("tar.gz bulunamadı.")
            tar_path = os.path.join(_install_dir(), asset["name"])

            on_status(f"{_t('progress_download_proton')} ({asset['name']})", "running")
            url = asset["browser_download_url"]
            req2 = urllib.request.Request(url, headers={"User-Agent": "mc-gdk-launcher"})
            with urllib.request.urlopen(req2, timeout=120) as resp, open(tar_path, "wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total > 0:
                        percent = min(100, int(done * 100 / total))
                        done_mb = done / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        on_status(f"{_t('progress_download_proton')} {done_mb:.1f} MB / {total_mb:.1f} MB ({percent}%)", "running")
            ok = _do_extract(tar_path, on_status, remove_after=True, login_method=login_method)
            if ok:
                ensure_umu(on_status)
            on_done(ok)
        except urllib.error.HTTPError as he:
            if he.code == 403:
                on_status("GitHub API limit exceeded. Please try again later or install GDK-Proton manually.", "error")
            else:
                on_status(f"HTTP Error: {he.code}", "error")
            on_done(False)
        except Exception as e:
            on_status(f"İndirme hatası: {e}", "error")
            on_done(False)

    threading.Thread(target=worker, daemon=True).start()


def _do_extract_zip(zip_path: str, on_status: Callable, login_method: str = "proxypass"):
    """Zip arşivini kurulum dizinine aç."""
    import zipfile
    from mc_launcher.i18n import _t
    dest_dir = _install_dir()
    try:
        on_status(_t("proton_extracting_zip"), "running")
        with zipfile.ZipFile(zip_path, 'r') as z:
            members = z.infolist()
            total = len(members)
            dest_real = os.path.realpath(dest_dir)
            for i, m in enumerate(members, 1):
                try:
                    member_path = os.path.realpath(os.path.join(dest_dir, m.filename))
                    if not (member_path == dest_real or member_path.startswith(dest_real + os.sep)):
                        raise RuntimeError(f"Güvensiz arşiv yolu: {m.filename}")
                    z.extract(m, dest_dir)
                except Exception as me:
                    print(f"[SKIP] {m.filename}: {me}")
                if i % 100 == 0 or i == total:
                    on_status(_t("proton_extracting_percent", percent=int(i * 100 / total)), "running")
        p = find_proton(login_method)
        if p:
            os.chmod(p, 0o755)
            on_status(_t("proton_ready_named", name=os.path.basename(os.path.dirname(p))), "ok")
            return True
        on_status(_t("proton_err_binary"), "error")
        return False
    except Exception as e:
        on_status(f"{_t('err_title')}: {e}", "error")
        return False


def install_from_file(tar_path: str, on_status: Callable, on_done: Callable, login_method: str = "proxypass"):
    """Kullanıcının seçtiği .tar.gz veya .zip dosyasından GDK-Proton'u kurar."""
    def worker():
        if tar_path.endswith(".zip"):
            ok = _do_extract_zip(tar_path, on_status, login_method=login_method)
        else:
            ok = _do_extract(tar_path, on_status, remove_after=False, login_method=login_method)
        if ok:
            ensure_umu(on_status)
        on_done(ok)

    threading.Thread(target=worker, daemon=True).start()


def install_from_folder(src_dir: str, on_status: Callable, on_done: Callable, login_method: str = "proxypass"):
    """Kullanıcının seçtiği unpacked klasörden GDK-Proton'u kurar."""
    def worker():
        import shutil
        from mc_launcher.i18n import _t
        dest_base = _install_dir()
        try:
            on_status(_t("proton_copying_folder"), "running")
            proton_bin = os.path.join(src_dir, "proton")
            if not os.path.isfile(proton_bin):
                on_status(_t("proton_err_folder_binary"), "error")
                on_done(False)
                return

            folder_name = os.path.basename(os.path.normpath(src_dir))
            dest_dir = os.path.join(dest_base, folder_name)

            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)

            shutil.copytree(src_dir, dest_dir)

            p = find_proton(login_method)
            if p:
                os.chmod(p, 0o755)
                ensure_umu(on_status)
                on_status(_t("proton_ready_named", name=os.path.basename(os.path.dirname(p))), "ok")
                on_done(True)
                return
            on_status(_t("proton_err_binary"), "error")
            on_done(False)
        except Exception as e:
            on_status(f"{_t('err_title')}: {e}", "error")
            on_done(False)

    threading.Thread(target=worker, daemon=True).start()


def ensure_umu(on_status: Callable) -> Optional[str]:
    """
    Sistemde veya yerel dizinde umu-run dosyası olup olmadığını kontrol eder.
    Bulamazsa GitHub API üzerinden Open-Wine-Components/umu-launcher reposundan zipapp paketini indirip kurar.
    """
    import shutil
    import tarfile
    from mc_launcher.i18n import _t

    # 1. Check if already available in PATH, cache or common runners (lutris, heroic, etc)
    for path in [
        shutil.which("umu-run"),
        os.path.expanduser("~/.local/share/mc-gdk-linux-launcher/umu/umu-run"),
        os.path.expanduser("~/.local/share/lutris/runtime/umu/umu-run"),
        os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic/tools/runtimes/umu/umu-run"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/steam/compatibilitytools.d/umu-launcher/umu-run"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d/umu-launcher/umu-run"),
    ]:
        if path and os.path.isfile(path):
            print(f"[UMU] Found existing umu-run at: {path}")
            return path

    dest_dir = os.path.join(DATA_DIR, "umu")
    os.makedirs(dest_dir, exist_ok=True)
    bin_path = os.path.join(dest_dir, "umu-run")
    if os.path.isfile(bin_path):
        return bin_path

    try:
        on_status(_t("umu_querying"), "running")
        api_url = "https://api.github.com/repos/Open-Wine-Components/umu-launcher/releases/latest"
        req = urllib.request.Request(api_url, headers={"User-Agent": "mc-gdk-launcher"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())

        asset = next((a for a in data.get("assets", []) if a["name"].endswith("zipapp.tar")), None)
        if not asset:
            # Fallback
            asset = next((a for a in data.get("assets", []) if "umu-run" in a["name"]), None)

        if not asset:
            on_status(_t("umu_err_asset"), "error")
            return None

        tar_path = os.path.join(dest_dir, asset["name"])
        on_status(_t("umu_downloading", name=asset['name']), "running")

        url = asset["browser_download_url"]
        req2 = urllib.request.Request(url, headers={"User-Agent": "mc-gdk-launcher"})
        with urllib.request.urlopen(req2, timeout=90) as resp, open(tar_path, "wb") as out:
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
                    on_status(f"{_t('umu_downloading', name=asset['name'])} ({percent}%)", "running")

        on_status(_t("umu_installing"), "running")
        dest_real = os.path.realpath(dest_dir)
        with tarfile.open(tar_path, "r") as t:
            try:
                t.extractall(dest_dir, filter="tar")
            except TypeError:
                for m in t.getmembers():
                    member_path = os.path.realpath(os.path.join(dest_dir, m.name))
                    if not (member_path == dest_real or member_path.startswith(dest_real + os.sep)):
                        raise RuntimeError(f"Güvensiz arşiv yolu: {m.name}")
                    
                    if m.issym() or m.islnk():
                        target_path = os.path.join(os.path.dirname(member_path), m.linkname)
                        target_real = os.path.realpath(target_path)
                        if not (target_real == dest_real or target_real.startswith(dest_real + os.sep)):
                            raise RuntimeError(f"Güvensiz link hedefi: {m.linkname}")
                            
                    t.extract(m, dest_dir)

        # Look for umu-run recursively in dest_dir
        found_bin = None
        for r, d, files in os.walk(dest_dir):
            if "umu-run" in files:
                found_bin = os.path.join(r, "umu-run")
                break

        if found_bin:
            shutil.copy2(found_bin, bin_path)
            os.chmod(bin_path, 0o755)
            if os.path.exists(tar_path):
                os.remove(tar_path)
            on_status(_t("umu_ready"), "ok")
            return bin_path

        on_status(_t("umu_err_no_run"), "error")
        return None
    except urllib.error.HTTPError as he:
        if he.code == 403:
            on_status("GitHub API limit exceeded. Please try again later or install umu-launcher manually.", "error")
        else:
            on_status(f"HTTP Error: {he.code}", "error")
        return None
    except Exception as e:
        on_status(f"{_t('err_title')}: {e}", "error")
        return None


class PE:
    def __init__(self, path):
        from pathlib import Path
        self.path = Path(path)
        d = self.data = self.path.read_bytes()
        if d[:2] != b"MZ":
            raise ValueError("not a PE")
        import struct
        e = struct.unpack_from("<I", d, 0x3C)[0]
        if d[e:e + 4] != b"PE\0\0":
            raise ValueError("bad PE signature")
        coff = e + 4
        nsec = struct.unpack_from("<H", d, coff + 2)[0]
        opt = coff + 20
        if struct.unpack_from("<H", d, opt)[0] != 0x20B:
            raise ValueError("not PE32+")
        self.exp_rva = struct.unpack_from("<I", d, opt + 112)[0]
        sect = opt + struct.unpack_from("<H", d, coff + 16)[0]
        self.secs = []
        for i in range(nsec):
            b = sect + i * 40
            vsz, va, rsz, raw = struct.unpack_from("<IIII", d, b + 8)
            self.secs.append((va, vsz, raw, rsz))

    def rva2off(self, rva):
        for va, vsz, raw, rsz in self.secs:
            if va <= rva < va + max(vsz, rsz):
                return raw + (rva - va)
        return None

    def off2rva(self, off):
        for va, vsz, raw, rsz in self.secs:
            if raw <= off < raw + rsz:
                return va + (off - raw)
        return None

    def export_rva(self, name):
        import struct
        d = self.data
        eo = self.rva2off(self.exp_rva)
        if eo is None:
            return None
        nn = struct.unpack_from("<I", d, eo + 24)[0]
        af = self.rva2off(struct.unpack_from("<I", d, eo + 28)[0])
        an = self.rva2off(struct.unpack_from("<I", d, eo + 32)[0])
        ao = self.rva2off(struct.unpack_from("<I", d, eo + 36)[0])
        t = name.encode()
        for i in range(nn):
            no = self.rva2off(struct.unpack_from("<I", d, an + 4 * i)[0])
            if d[no:d.index(b"\0", no)] == t:
                od = struct.unpack_from("<H", d, ao + 2 * i)[0]
                return struct.unpack_from("<I", d, af + 4 * od)[0]
        return None

    def export_off(self, name):
        r = self.export_rva(name)
        return self.rva2off(r) if r is not None else None


def _backup_once(path):
    import shutil
    bk = path.with_suffix(path.suffix + ".bol-orig")
    if not bk.exists():
        shutil.copy2(path, bk)


def apply_patch(path, off, expect, new, what, strict=True, relax=False):
    from pathlib import Path
    path = Path(path)
    raw = bytearray(path.read_bytes())
    if bytes(raw[off:off + len(new)]) == new:
        print(f"[PATCH] {what}: already patched")
        return False
    if bytes(raw[off:off + len(expect)]) != expect:
        got = bytes(raw[off:off + len(expect)]).hex()
        if not relax:
            msg = f"[PATCH] {what}: unexpected bytes at 0x{off:x} — patch skipped."
            if strict:
                raise RuntimeError(msg)
            print(msg)
            return False
        print(f"[PATCH] {what}: prologue {got} at 0x{off:x} differs — stubbing anyway.")
    _backup_once(path)
    raw[off:off + len(new)] = new
    path.write_bytes(raw)
    print(f"[PATCH] {what}: patched")
    return True


def patch_proton(proton_bin_path: str, strict=False):
    """Two binary patches that let Bedrock GDK 1.26 run under Wine.
    Idempotent; offsets found structurally; backups as *.bol-orig."""
    from pathlib import Path
    import struct
    
    root = Path(os.path.dirname(proton_bin_path))
    def fail(m):
        if strict:
            raise RuntimeError(m)
        print(f"[PATCH] {m} (continuing)")

    wine = root / "files/lib/wine/x86_64-windows"
    if not wine.exists():
        wine = root / "files/lib64/wine/x86_64-windows"
    
    combase, ntdll = wine / "combase.dll", wine / "ntdll.dll"
    if not combase.exists() or not ntdll.exists():
        return fail(f"Wine DLLs missing in {wine}")

    try:
        pe_combase = PE(combase)
        off = pe_combase.export_off("RoOriginateErrorW")
        if off is None:
            return fail("RoOriginateErrorW not found in combase.dll")
        apply_patch(combase, off, bytes.fromhex("4883ec28"),
                    bytes.fromhex("31c0c3") + b"\x90" * 21,
                    "combase.RoOriginateErrorW", strict=strict, relax=True)
    except Exception as e:
        fail(f"combase patch failed: {e}")

    try:
        pe_ntdll = PE(ntdll)
        rre = pe_ntdll.export_rva("RtlRaiseException")
        if rre is None:
            return fail("RtlRaiseException not resolved in ntdll.dll")
        d = pe_ntdll.data
        sig = bytes.fromhex("55534881ecc8000000488dac24c0000000")
        new = bytes.fromhex("b8020000c0c3") + b"\x90\x90"
        funnels, i = [], d.find(sig)
        while i >= 0:
            j = d.find(bytes.fromhex("4889d9e8"), i, i + 0x90)
            if j >= 0:
                cf = j + 3
                rel = struct.unpack_from("<i", d, cf + 1)[0]
                if pe_ntdll.off2rva(cf) + 5 + rel == rre and d[cf + 5:cf + 7] == b"\xeb\xf6":
                    funnels.append(i)
            i = d.find(sig, i + 1)
        if funnels:
            raw = bytearray(d)
            for o in funnels:
                raw[o:o + len(new)] = new
            _backup_once(ntdll)
            ntdll.write_bytes(bytes(raw))
            print(f"[PATCH] ntdll: {len(funnels)} stub(s) neutralised")
        elif d.count(new + bytes.fromhex("00488dac24c0000000")):
            print("[PATCH] ntdll: already patched")
        else:
            fail("ntdll: no stub found — Proton layout changed.")
    except Exception as e:
        fail(f"ntdll patch failed: {e}")
