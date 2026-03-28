"""
mc_launcher/game.py — Oyun başlatma, durdurma ve disk tarama mantığı
"""

import os
import signal
import subprocess
import threading
import traceback
from typing import Callable, List, Optional

from mc_launcher.config import SCRIPT_DIR, COMPAT_DATA
from mc_launcher.proxypass import find_proxypass, ensure_proxypass
from mc_launcher.java_rt import ensure_java


def build_env(mangohud_on: bool = False) -> dict:
    """Proton çalıştırması için gerekli ortam değişkenlerini hazırlar."""
    steam_root = os.path.expanduser("~/.steam/root")
    if not os.path.isdir(steam_root):
        steam_root = SCRIPT_DIR

    env = os.environ.copy()
    env.update({
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": steam_root,
        "STEAM_COMPAT_DATA_PATH"          : COMPAT_DATA,
        "PROTON_NO_ESYNC"                 : "0",
        "PROTON_NO_FSYNC"                 : "0",
        "WINEDLLOVERRIDES"                : "d3d12=n;dxgi=n",
        "WINE_FULLSCREEN_INTEGER_SCALING" : "0",
        "PROTON_USE_WINED3D"              : "0",
    })
    # Wayland/X11 sistemlerinde kullanıcı ortamını zorlamayalım.
    # Bu iki değişken bazı ortamlarda input sorunlarına sebep olabiliyor.
    # (Gerekiyorsa kullanıcı kendi env'i ile override edebilir.)
    if mangohud_on:
        env["MANGOHUD"]        = "1"
        env["MANGOHUD_CONFIG"] = "fps,frame_timing,gpu_stats,cpu_stats,vram,ram"
    return env


def launch_game(
    proton: str,
    exe: str,
    mangohud_on: bool,
    on_status: Callable,
    on_proxy_line: Optional[Callable] = None,
    on_finished: Optional[Callable] = None,
):
    """
    ProxyPass + oyunu ayrı thread'de başlatır.
    on_status(msg, style)  — durum güncellemeleri
    on_proxy_line(line)    — proxy log satırı (isteğe bağlı)
    on_finished(proc)      — oyun proc kapanınca çağrılır (isteğe bağlı)
    Döndürür: (game_proc, proxy_proc) — çağrıcı saklayabilir
    """
    env = build_env(mangohud_on)
    # Önce yereldeki veya indirilmiş ProxyPass.jar'ı bul / indir.
    jar = find_proxypass(exe) or ensure_proxypass(on_status)
    # Adoptium Java runtime'ı hazırla.
    java_bin = ensure_java(on_status)

    result = {"game": None, "proxy": None}

    def runner():
        proxy_proc = None
        try:
            # ProxyPass başlat
            if jar and java_bin:
                print(f"[PROXY] Başlatılıyor: {jar}")
                proxy_proc = subprocess.Popen(
                    [java_bin, "-jar", jar],
                    cwd=os.path.dirname(jar),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                )
                result["proxy"] = proxy_proc

                def _read_proxy(proc):
                    try:
                        for raw in iter(proc.stdout.readline, b""):
                            line = raw.decode(errors="replace")
                            if on_proxy_line:
                                on_proxy_line(line)
                    except Exception as e:
                        print(f"[PROXY] Log okuma hatası: {e}")
                    finally:
                        if proc.stdout:
                            proc.stdout.close()

                threading.Thread(target=_read_proxy, args=(proxy_proc,), daemon=True).start()
                import time; time.sleep(2)
            else:
                missing = []
                if not jar: missing.append("ProxyPass.jar")
                if not java_bin: missing.append("Java Runtime")
                print(f"[PROXY] Atlanıyor (eksik bileşenler: {', '.join(missing)})")

            # Oyunu başlat
            if mangohud_on:
                cmd = ["mangohud", "--dlsym", proton, "run", exe]
            else:
                cmd = [proton, "run", exe]

            print(f"[LAUNCH] {' '.join(cmd)}")
            # Unix altında süreç grubu oluşturarak başlat; böylece Proton'un
            # açtığı alt süreçler de birlikte sonlandırılabilir.
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(exe),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
            result["game"] = proc

            def _rd(pipe, tag):
                try:
                    for raw in iter(pipe.readline, b""):
                        print(f"[{tag}] {raw.decode(errors='replace').rstrip()}")
                finally:
                    pipe.close()

            t1 = threading.Thread(target=_rd, args=(proc.stdout, "OUT"), daemon=True)
            t2 = threading.Thread(target=_rd, args=(proc.stderr, "ERR"), daemon=True)
            t1.start(); t2.start()

            on_status("Oyun çalışıyor...", "running")
            ret = proc.wait()
            t1.join(timeout=3); t2.join(timeout=3)
            on_status(f"Oyun kapandı (exit: {ret})", "ok" if ret == 0 else "error")
        except Exception as e:
            print(f"[HATA]\n{traceback.format_exc()}")
            on_status(f"Hata: {e}", "error")
        finally:
            if proxy_proc and proxy_proc.poll() is None:
                proxy_proc.terminate()
                try:
                    proxy_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proxy_proc.kill()
            if on_finished:
                on_finished()

    threading.Thread(target=runner, daemon=True).start()
    return result


def scan_for_exe(on_done: Callable[[List[str]], None], on_status: Callable):
    """
    Olası dizinleri tarayarak Minecraft.Windows.exe'yi arar.
    on_done(found_list) UI thread'de çağrılır (GLib.idle_add ile).
    """
    def worker():
        user = os.environ.get("USER", "")
        search_roots = [
            SCRIPT_DIR,
            os.path.expanduser("~/Games"),
            os.path.expanduser("~/.local/share"),
            f"/run/media/{user}" if user else "/run/media",
            "/mnt",
        ]
        found: List[str] = []
        # Dışarıdan `find` komutuna bağımlı kalmak her sistemde stabil değil;
        # ayrıca büyük disklerde zaman aşımı ile eksik sonuç döndürebiliyor.
        # Bu yüzden sınırlı derinlikte Python ile geziyoruz.
        target = "Minecraft.Windows.exe"
        max_depth = 6

        for root_dir in search_roots:
            if not os.path.isdir(root_dir):
                continue
            base_depth = root_dir.rstrip(os.sep).count(os.sep)
            try:
                for cur, dirs, files in os.walk(root_dir, topdown=True):
                    depth = cur.rstrip(os.sep).count(os.sep) - base_depth
                    if depth >= max_depth:
                        dirs[:] = []
                        continue
                    # Permission hatalarında os.walk bazı FS'lerde gürültü çıkarabilir; yut.
                    if target in files:
                        found.append(os.path.join(cur, target))
            except Exception as e:
                print(f"Tarama hatası ({root_dir}): {e}")

        from gi.repository import GLib
        GLib.idle_add(on_done, found)

    on_status("Diskler taranıyor... Lütfen bekleyin.", "running")
    threading.Thread(target=worker, daemon=True).start()


def options_txt_path() -> str:
    """Wine prefix içindeki Minecraft options.txt dosyasının yolunu döner."""
    return os.path.join(
        COMPAT_DATA, "pfx", "drive_c", "users", "steamuser",
        "AppData", "Roaming", "Minecraft Bedrock",
        "Users", "Shared", "games", "com.mojang",
        "minecraftpe", "options.txt",
    )


def patch_options(key: str, value: str) -> Optional[bool]:
    """options.txt içindeki key:value satırını günceller, yoksa ekler."""
    path = options_txt_path()
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        lines = f.readlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith(key + ":"):
            new_lines.append(f"{key}:{value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}:{value}\n")
    with open(path, "w") as f:
        f.writelines(new_lines)
    return True


def stop_game(proc) -> None:
    """
    Oyunu mümkün olduğunca temiz şekilde sonlandırır.
    Proton'un başlattığı alt süreçleri de öldürebilmek için
    süreç grubunu hedef almaya çalışır. Gerekirse zorla sonlandırır.
    """
    if not proc or proc.poll() is not None:
        return
    try:
        import time
        # Önce Proton süreç grubunu sonlandır (mümkünse).
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            time.sleep(0.3)
            if proc.poll() is None:
                os.killpg(pgid, signal.SIGKILL)
        except Exception:
            proc.terminate()
            time.sleep(0.3)
            if proc.poll() is None:
                proc.kill()
    except Exception:
        # Sessizce yut; burada ekrana hata basmak istemiyoruz.
        pass
