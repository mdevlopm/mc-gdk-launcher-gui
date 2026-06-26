"""
mc_launcher/store.py — Microsoft Store API sorgulama, indirme ve kurma mantığı
"""

import os
import re
import urllib.request
import urllib.parse
import zipfile
from typing import Callable, Optional, List
from mc_launcher.i18n import _t


def find_all_mojang_dirs() -> List[str]:
    """Wine prefix içindeki com.mojang klasörlerinin yollarını döner."""
    import os
    from mc_launcher.config import COMPAT_DATA
    drive_c = os.path.join(COMPAT_DATA, "pfx", "drive_c")
    if not os.path.isdir(drive_c):
        return []
    
    paths = []
    import getpass
    try:
        user_name = getpass.getuser()
    except Exception:
        user_name = os.environ.get("USER", "steamuser")
        
    common_subpaths = [
        "users/steamuser/AppData/Roaming/Minecraft Bedrock/Users/Shared/games/com.mojang",
    ]
    if user_name and user_name != "steamuser":
        common_subpaths.append(f"users/{user_name}/AppData/Roaming/Minecraft Bedrock/Users/Shared/games/com.mojang")

    for sp in common_subpaths:
        p = os.path.join(drive_c, sp)
        if os.path.isdir(p) and p not in paths:
            paths.append(p)
            
    # Tüm drive_c/users dizinini tarayarak com.mojang klasörlerini bul (XUID özel klasörleri dahil)
    users_dir = os.path.join(drive_c, "users")
    if os.path.isdir(users_dir):
        for root, dirs, _files in os.walk(users_dir):
            if root.endswith("games") and "com.mojang" in dirs:
                p = os.path.join(root, "com.mojang")
                if p not in paths:
                    paths.append(p)
    return paths


def detect_zip_type(file_path: str) -> str:
    """Zip dosyasının içeriğine bakarak .mcworld, .mcaddon veya .mcpack olduğunu algılar."""
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            names = z.namelist()
            if any(name.endswith("level.dat") for name in names):
                return ".mcworld"
            if any(name.lower().endswith(".mcpack") for name in names):
                return ".mcaddon"
    except Exception as e:
        print(f"[Store] Error detecting zip type for {file_path}: {e}")
    return ".mcpack"


def install_bedrock_content(
    file_path: str,
    on_progress: Callable[[str], None],
    detected_ext: Optional[str] = None
) -> bool:
    """
    İndirilen .mcpack, .mcworld veya .mcaddon dosyasını bulunan tüm com.mojang dizinlerine kurar.
    """
    mojang_dirs = find_all_mojang_dirs()
    if not mojang_dirs:
        on_progress(_t("store_err_mojang"))
        return False
        
    on_progress(_t("store_analyzing"))
    ext = detected_ext or os.path.splitext(file_path)[1].lower()
    if ext not in [".mcpack", ".mcworld", ".mcaddon", ".zip"]:
        ext = detect_zip_type(file_path)
    
    def is_world_zip(zip_ref):
        names = zip_ref.namelist()
        return any(name.endswith("level.dat") for name in names)

    def get_pack_type(zip_ref):
        names = zip_ref.namelist()
        manifest_name = next((n for n in names if n.endswith("manifest.json") or n.endswith("pack_manifest.json")), None)
        if manifest_name:
            try:
                import json
                with zip_ref.open(manifest_name) as f:
                    data = json.loads(f.read().decode('utf-8', errors='replace'))
                modules = data.get("modules", [])
                if modules:
                    m_type = modules[0].get("type", "resources")
                    if m_type == "data":
                        return "behavior_packs"
                    elif m_type == "resources":
                        return "resource_packs"
                    elif m_type == "skin_pack":
                        return "skin_packs"
            except Exception:
                pass
        
        for n in names:
            if "entities/" in n or "loot_tables/" in n or "recipes/" in n or "scripts/" in n:
                return "behavior_packs"
        return "resource_packs"

    def extract_zip_to(zip_ref, target_dir):
        target_dir = os.path.abspath(target_dir)
        dest_real = os.path.realpath(target_dir)
        
        for member in zip_ref.infolist():
            clean_name = os.path.normpath(member.filename)
            if clean_name.startswith("..") or os.path.isabs(clean_name):
                continue
                
            member_path = os.path.abspath(os.path.join(target_dir, clean_name))
            if not member_path.startswith(dest_real + os.sep) and member_path != dest_real:
                continue
                
            if member.is_dir():
                os.makedirs(member_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(member_path), exist_ok=True)
                with zip_ref.open(member) as source, open(member_path, "wb") as dest:
                    import shutil
                    shutil.copyfileobj(source, dest)

    try:
        if ext == ".mcworld":
            world_name = os.path.splitext(os.path.basename(file_path))[0]
            world_dir_name = re.sub(r'[^a-zA-Z0-9_-]', '_', world_name)
            
            on_progress(_t("store_installing_world", name=world_name))
            with zipfile.ZipFile(file_path, 'r') as z:
                for mojang_dir in mojang_dirs:
                    target_dir = os.path.join(mojang_dir, "minecraftWorlds", world_dir_name)
                    extract_zip_to(z, target_dir)
            on_progress(_t("store_world_ok"))
            return True
            
        elif ext == ".mcpack" or ext == ".zip":
            pack_name = os.path.splitext(os.path.basename(file_path))[0]
            pack_dir_name = re.sub(r'[^a-zA-Z0-9_-]', '_', pack_name)
            
            with zipfile.ZipFile(file_path, 'r') as z:
                if ext == ".zip" and is_world_zip(z):
                    on_progress(_t("store_installing_world", name=pack_name))
                    for mojang_dir in mojang_dirs:
                        target_dir = os.path.join(mojang_dir, "minecraftWorlds", pack_dir_name)
                        extract_zip_to(z, target_dir)
                    on_progress(_t("store_world_ok"))
                    return True
                
                pack_type = get_pack_type(z)
                on_progress(_t("store_installing_pack", type=pack_type, name=pack_name))
                for mojang_dir in mojang_dirs:
                    target_dir = os.path.join(mojang_dir, pack_type, pack_dir_name)
                    extract_zip_to(z, target_dir)
            on_progress(_t("store_pack_ok", type=pack_type))
            return True
            
        elif ext == ".mcaddon":
            on_progress(_t("store_extracting_addon"))
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(file_path, 'r') as z:
                    extract_zip_to(z, tmpdir)
                
                packs = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.lower().endswith(".mcpack")]
                if not packs:
                    pack_name = os.path.splitext(os.path.basename(file_path))[0]
                    pack_dir_name = re.sub(r'[^a-zA-Z0-9_-]', '_', pack_name)
                    with zipfile.ZipFile(file_path, 'r') as z:
                        for mojang_dir in mojang_dirs:
                            target_dir = os.path.join(mojang_dir, "resource_packs", pack_dir_name)
                            extract_zip_to(z, target_dir)
                    on_progress(_t("store_pack_ok", type="resource_packs"))
                    return True
                    
                for pack_path in packs:
                    install_bedrock_content(pack_path, on_progress)
            on_progress(_t("store_addon_ok"))
            return True
        else:
            on_progress(_t("store_err_ext", ext=ext))
            return False
            
    except Exception as e:
        on_progress(_t("store_err_install", error=e))
        return False


def download_and_install_content(
    url: str,
    on_progress: Callable[[str], None]
) -> tuple[bool, str]:
    """
    Verilen URL'deki içeriği indirip otomatik olarak kurar.
    """
    import urllib.error
    import socket
    import ssl
    
    temp_path = None
    try:
        on_progress(_t("store_connecting"))
        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path)
        
        # Local file bypass
        if url.startswith("file://") or os.path.isfile(url):
            local_path = path if url.startswith("file://") else url
            if not os.path.isfile(local_path):
                return False, "File not found"
            ext = os.path.splitext(local_path)[1].lower()
            install_errs = []
            def log_progress(msg):
                on_progress(msg)
                if any(x in msg.lower() for x in ["hata", "error", "failed", "başarısız"]):
                    install_errs.append(msg)
            success = install_bedrock_content(local_path, log_progress, detected_ext=ext)
            if success:
                return True, ""
            else:
                return False, install_errs[-1] if install_errs else _t("toast_install_failed")
        
        # 1. URL path'inden varsayılan uzantıyı bul
        ext = os.path.splitext(path)[1].lower()
        
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        on_progress(_t("store_downloading", percent=0))
        
        # Geçici dosyaya kaydet
        import tempfile
        temp_fd, temp_path = tempfile.mkstemp(suffix=".tmp")
        os.close(temp_fd)
        
        # SSL Verification
        ssl_context = ssl.create_default_context()
        try:
            resp = urllib.request.urlopen(req, timeout=120, context=ssl_context)
        except urllib.error.URLError as url_err:
            reason_str = str(url_err.reason).lower()
            if "cert" in reason_str or "ssl" in reason_str or "verify" in reason_str:
                on_progress(_t("store_connecting") + " (SSL Error: Connection refused)")
            raise url_err
        
        with resp:
            # 2. Content-Disposition başlığından uzantı tespiti
            cd = resp.headers.get("Content-Disposition", "")
            m = re.search(r'filename=["\']?([^"\';\n]+)["\']?', cd)
            if m:
                detected_name = m.group(1)
                detected_ext = os.path.splitext(detected_name)[1].lower()
                if detected_ext in [".mcpack", ".mcworld", ".mcaddon", ".zip"]:
                    ext = detected_ext
            
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(temp_path, "wb") as out_f:
                while True:
                    chunk = resp.read(1024 * 64)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    done += len(chunk)
                    if total > 0:
                        percent = int(done * 100 / total)
                        done_mb = done / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        base_msg = _t("store_downloading", percent=percent)
                        on_progress(f"{base_msg} ({done_mb:.2f} MB / {total_mb:.2f} MB)")
                    else:
                        done_kb = done // 1024
                        on_progress(_t("store_downloading_kb", kb=done_kb))
        
        # 3. Dosya uzantısı tespiti hâlâ belirsiz veya .zip ise, dosya içeriğini tara
        if not ext or ext not in [".mcpack", ".mcworld", ".mcaddon", ".zip"]:
            ext = detect_zip_type(temp_path)
            
        install_errs = []
        def log_progress(msg):
            on_progress(msg)
            if any(x in msg.lower() for x in ["hata", "error", "failed", "başarısız"]):
                install_errs.append(msg)
                
        success = install_bedrock_content(temp_path, log_progress, detected_ext=ext)
        
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
            
        if success:
            return True, ""
        else:
            err_detail = install_errs[-1] if install_errs else _t("toast_install_failed")
            return False, err_detail
            
    except urllib.error.HTTPError as http_err:
        err_msg = f"HTTP Error {http_err.code}: {http_err.reason}"
        on_progress(_t("store_err_install", error=err_msg))
        return False, err_msg
    except urllib.error.URLError as url_err:
        reason_str = str(url_err.reason)
        if "timed out" in reason_str.lower() or isinstance(url_err.reason, socket.timeout):
            err_msg = f"Connection Timed Out (120s limit reached): {reason_str}"
        elif "cert" in reason_str.lower() or "ssl" in reason_str.lower():
            err_msg = f"SSL Certificate Verification Failed: {reason_str}"
        else:
            err_msg = f"Network Connection Failed: {reason_str}"
        on_progress(_t("store_err_install", error=err_msg))
        return False, err_msg
    except socket.timeout:
        err_msg = "Connection Timed Out (120s limit reached)"
        on_progress(_t("store_err_install", error=err_msg))
        return False, err_msg
    except zipfile.BadZipFile:
        err_msg = "Invalid pack file (Not a ZIP archive)"
        on_progress(_t("store_err_install", error=err_msg))
        return False, err_msg
    except Exception as e:
        err_msg = str(e)
        on_progress(_t("store_err_install", error=err_msg))
        return False, err_msg


def get_world_name(world_dir: str) -> str:
    levelname_path = os.path.join(world_dir, "levelname.txt")
    if os.path.isfile(levelname_path):
        try:
            with open(levelname_path, "r", encoding="utf-8", errors="ignore") as f:
                name = f.readline().strip()
                if name:
                    return name
        except Exception:
            pass
    return os.path.basename(world_dir)


def get_pack_name(pack_dir: str) -> str:
    for filename in ["manifest.json", "pack_manifest.json"]:
        manifest_path = os.path.join(pack_dir, filename)
        if os.path.isfile(manifest_path):
            try:
                import json
                with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                header = data.get("header", {})
                name = header.get("name")
                if name:
                    return name
            except Exception:
                pass
    return os.path.basename(pack_dir)


def list_installed_content() -> List[dict]:
    """
    Mojang dizinlerindeki kurulu dünyaları ve paketleri tarayıp döner.
    """
    mojang_dirs = find_all_mojang_dirs()
    installed = []
    
    types_mapping = {
        "minecraftWorlds": "world",
        "resource_packs": "resource_pack",
        "behavior_packs": "behavior_pack",
        "skin_packs": "skin_pack"
    }
    
    for mojang_dir in mojang_dirs:
        for subfolder_name, content_type in types_mapping.items():
            dir_path = os.path.join(mojang_dir, subfolder_name)
            if not os.path.isdir(dir_path):
                continue
            
            try:
                for item_name in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item_name)
                    if not os.path.isdir(item_path):
                        continue
                        
                    if content_type == "world":
                        real_name = get_world_name(item_path)
                    else:
                        real_name = get_pack_name(item_path)
                        
                    installed.append({
                        "name": real_name,
                        "folder_name": item_name,
                        "type": content_type,
                        "path": item_path,
                        "mojang_dir": mojang_dir
                    })
            except Exception:
                pass
                
    return installed


def delete_installed_content(path: str) -> bool:
    """Kurulu içeriği (klasörü) güvenli şekilde siler."""
    import shutil
    try:
        abs_path = os.path.abspath(path)
        mojang_dirs = [os.path.abspath(d) for d in find_all_mojang_dirs()]
        
        is_safe = False
        allowed_subfolders = ["minecraftWorlds", "resource_packs", "behavior_packs", "skin_packs"]
        
        for base_dir in mojang_dirs:
            for sub in allowed_subfolders:
                allowed_prefix = os.path.join(base_dir, sub) + os.sep
                if abs_path.startswith(allowed_prefix):
                    is_safe = True
                    break
            if is_safe:
                break
                
        if not is_safe:
            print(f"[Store] Refusing to delete unsafe path: {path}")
            return False
            
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
            return True
    except Exception as e:
        print(f"[Store] Error deleting content: {e}")
    return False
