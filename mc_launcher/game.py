"""
mc_launcher/game.py — Oyun başlatma, durdurma ve disk tarama mantığı
"""

import os
import signal
import sys
import subprocess
import threading
import time
import traceback
from typing import Callable, List, Optional

from mc_launcher.config import SCRIPT_DIR, COMPAT_DATA, DATA_DIR
from mc_launcher.proxypass import find_proxypass, ensure_proxypass
from mc_launcher.java_rt import ensure_java
from mc_launcher.proton import ensure_umu, patch_proton
from mc_launcher.gameinput import install_gameinput
from mc_launcher.i18n import _t
from pathlib import Path


def build_env(mangohud_on: bool = False) -> dict:
    """Proton çalıştırması için gerekli ortam değişkenlerini hazırlar."""
    steam_root = os.path.expanduser("~/.steam/root")
    if not os.path.isdir(steam_root):
        flatpak_steam = os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/steam")
        if os.path.isdir(flatpak_steam):
            steam_root = flatpak_steam
        else:
            flatpak_steam_alt = os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam")
            if os.path.isdir(flatpak_steam_alt):
                steam_root = flatpak_steam_alt
            else:
                steam_root = SCRIPT_DIR

    env = os.environ.copy()

    # Wayland + NVIDIA EGL sorunlarını aşmak için WAYLAND_DISPLAY değişkenini gizleyip
    # oyunun XWayland (X11) modunda başlamasını sağlıyoruz. Ayrıca fare algılama sorunları için SDL'i X11'e zorluyoruz.
    env.pop("WAYLAND_DISPLAY", None)
    env["SDL_VIDEODRIVER"] = "x11"
    env["GDK_BACKEND"] = "x11"

    # Minecraft Bedrock VR başlıklarını ararken (OpenVR, OpenXR) çökmeleri önlemek için
    # VR DLL kütüphanelerini devre dışı bırakıyoruz.
    dll_overrides = "d3d12=n;dxgi=n;vrclient=;vrclient_x64=;openvr_api=;wineopenxr=;winedbg.exe=d;winedbg=d"

    env.update({
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": steam_root,
        "STEAM_COMPAT_DATA_PATH"          : COMPAT_DATA,
        "PROTON_NO_ESYNC"                 : "0",
        "PROTON_NO_FSYNC"                 : "0",
        "WINEDLLOVERRIDES"                : dll_overrides,
        "WINE_FULLSCREEN_INTEGER_SCALING" : "0",
        "PROTON_USE_WINED3D"              : "0",
        "VKD3D_CONFIG"                    : "force_raw_va_cbv",
        "SDL_MOUSEDRIVER"                 : "x11",
        "SDL_VIDEO_X11_DGAMOUSE"          : "0",
        "SteamAppId"                      : "4000",
        "SteamGameId"                     : "4000",
        "PROTON_LOG"                      : "1",
    })
    if mangohud_on:
        env["MANGOHUD"]        = "1"
        env["MANGOHUD_CONFIG"] = "fps,frame_timing,gpu_stats,cpu_stats,vram,ram"
    return env


def _list_child_pids(pid: int) -> List[int]:
    """/proc üzerinden alt süreç PID'lerini toplar."""
    pids: List[int] = []
    try:
        with open(f"/proc/{pid}/task/{pid}/children", encoding="utf-8") as f:
            for part in f.read().split():
                if part.isdigit():
                    cpid = int(part)
                    pids.append(cpid)
                    pids.extend(_list_child_pids(cpid))
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        pass
    return pids


def _signal_pids(pids: List[int], sig: int) -> None:
    for pid in pids:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _kill_wineserver(proton: Optional[str] = None) -> None:
    """Prefix'e bağlı wineserver sürecini sonlandırır."""
    env = build_env()
    pfx = os.path.join(COMPAT_DATA, "pfx")
    if os.path.isdir(pfx):
        env["WINEPREFIX"] = pfx

    cmds = []
    if proton and os.path.isfile(proton):
        real_proton = os.path.realpath(proton)
        wineserver_bin = os.path.join(os.path.dirname(real_proton), "files", "bin", "wineserver")
        if os.path.isfile(wineserver_bin):
            cmds.append([wineserver_bin, "-k"])
        cmds.append([proton, "run", "wineserver", "-k"])
    cmds.append(["wineserver", "-k"])

    from mc_launcher.flatpak import wrap_flatpak_cmd
    for cmd in cmds:
        cmd = wrap_flatpak_cmd(cmd, env)
        try:
            res = subprocess.run(
                cmd,
                env=env,
                timeout=8,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue


def stop_game(proc_or_result, proton: Optional[str] = None, proxy_proc=None) -> None:
    """
    Oyunu ve ilişkili süreçleri sonlandırır.
    Proton/Wine alt süreç ağacını ve wineserver'ı hedef alır.
    """
    if isinstance(proc_or_result, dict):
        proc_or_result["cancelled"] = True
        proc = proc_or_result.get("game")
        if not proxy_proc:
            proxy_proc = proc_or_result.get("proxy")
    else:
        proc = proc_or_result

    if proxy_proc and proxy_proc.poll() is None:
        try:
            proxy_proc.terminate()
            proxy_proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            try:
                proxy_proc.kill()
            except OSError:
                pass

    # Direct process kill by name (most robust fallback for detached Wine/Proton games)
    # Use exact name matching (-x) instead of substring (-f) to avoid killing unrelated processes (e.g., text editors, file managers)
    try:
        subprocess.run(["pkill", "-9", "-x", "Minecraft.Windows.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-9", "-x", "Minecraft.Windows"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    if not proc or proc.poll() is not None:
        _kill_wineserver(proton)
        return

    root_pid = proc.pid
    tree = _list_child_pids(root_pid)

    for sig, pause in ((signal.SIGTERM, 0.6), (signal.SIGKILL, 0.3)):
        try:
            pgid = os.getpgid(root_pid)
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

        _signal_pids(tree, sig)
        try:
            os.kill(root_pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

        time.sleep(pause)
        if proc.poll() is not None:
            break

    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass

    _kill_wineserver(proton)


def launch_game(
    proton: str,
    exe: str,
    mangohud_on: bool,
    on_status: Callable,
    on_proxy_line: Optional[Callable] = None,
    on_finished: Optional[Callable] = None,
    on_started: Optional[Callable] = None,
    login_method: str = "proxypass",
):
    """
    ProxyPass + oyunu ayrı thread'de başlatır.
    on_status(msg, style)  — durum güncellemeleri
    on_proxy_line(line)    — proxy log satırı (isteğe bağlı)
    on_started(game, proxy) — süreçler başlatıldığında (isteğe bağlı)
    on_finished()          — oyun proc kapanınca çağrılır (isteğe bağlı)
    Döndürür: {"game": proc|None, "proxy": proc|None} paylaşılan sözlük
    """
    env = build_env(mangohud_on)
    jar = None
    java_bin = None
    if login_method == "proxypass":
        jar = find_proxypass(exe) or ensure_proxypass(on_status)
        java_bin = ensure_java(on_status)

    result = {"game": None, "proxy": None, "cancelled": False}

    def runner():
        proxy_proc = None
        relay = None
        try:
            if result.get("cancelled"):
                return
            # Kill leftover wineserver or game processes to prevent registry locks
            try:
                # Use exact name matching (-x) for game processes, and specific pattern for java-proxypass
                subprocess.run(["pkill", "-9", "-x", "Minecraft.Windows.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["pkill", "-9", "-x", "Minecraft.Windows"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["pkill", "-9", "-f", "java.*ProxyPass\\.jar"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                _kill_wineserver(proton)
                time.sleep(1)
            except Exception as e:
                print(f"[LAUNCH] Leftover cleanup error: {e}")

            if result.get("cancelled"):
                return

            # Proton binary dosyalarını GDK uyumluluğu için yama yapıyoruz (combase.dll, ntdll.dll stubs)
            try:
                patch_proton(proton)
            except Exception as pe:
                print(f"[LAUNCH] Proton yamalama hatası: {pe}")
            if login_method == "proxypass":
                # ============================================================
                # YENİ ProxyPass STRATEJİSİ: xuser Proton + DLL yamaları
                # ============================================================
                #
                # ESKİ davranış (sorunlu):
                #   - restore_vanilla_state() çağrılır → DLL yamaları kaldırılır
                #   - Normal (xuser olmayan) Proton kullanılır
                #   - Sonuç: XUser implementasyonu eksik → oyun çöker
                #
                # YENİ davranış (düzeltilmiş):
                #   - xuser Proton kullanılır (find_proton artık xuser tercih eder)
                #   - DLL yamaları KURULUR (xuser Proton bunlara ihtiyaç duyar)
                #   - restore_vanilla_state ÇAĞRILMAZ (yamaları korumak için)
                #   - ProxyPass.jar auth'u Bedrock protokol katmanında halleder
                #   - Registry preauth UYGULANMAZ (ProxyPass auth sağlar)
                #   - UMU launcher ile başlatılır (GPU sürücü izolasyonu)
                #
                # Bu sayede xuser Proton + DLL yamaları + ProxyPass birlikte
                # sorunsuz çalışır.
                # ============================================================
                on_status(_t("status_preparing_proxypass_xuser"), "running")
                try:
                    from mc_launcher.config import DATA_DIR
                    from mc_launcher.preauth import (
                        wine_disable_winegdk_preauth, hide_signin_button,
                        install_gdk_xbox_dlls, patch_gui_signin_gate
                    )
                    pfx = os.path.join(COMPAT_DATA, "pfx")
                    os.makedirs(pfx, exist_ok=True)

                    # --- Adım 1: Stale ingame registry token'larını temizle ---
                    # Önceki ingame modundan kalma ForceMsaFacet ve RefreshToken
                    # değerlerini sil. ProxyPass auth'u ağ katmanında halleder,
                    # bu registry değerlerine ihtiyaç duymaz.
                    wine_disable_winegdk_preauth(proton, pfx, env)

                    # --- Adım 2: GDK Xbox DLL yamalarını kur ---
                    # xuser Proton'un XUser yamaları, oyunun HTTP trafiğinin
                    # OpenSSL üzerinden gitmesi için bu DLL'lere ihtiyaç duyar:
                    #   - XCurl.dll → OpenSSL XCurl shim (GnuTLS bypass)
                    #   - libHttpClient.GDK.dll → XCurl provider'a zorla (binary patch)
                    #   - cacert.pem → sertifika paketi
                    #   - cryptbase.dll → Wine prefix system32 (RNG stub)
                    # Yamalar .bol-orig backup ile idempotent'tir — tekrar
                    # kurulduğunda zarar vermez.
                    on_status("GDK Xbox DLL yamaları yükleniyor (xuser Proton için)...", "running")
                    install_gdk_xbox_dlls(
                        os.path.dirname(exe), DATA_DIR, pfx, on_status
                    )

                    # --- Adım 3: GnuTLS TLS 1.3 sorununu önle ---
                    # Wine'ın kendi GnuTLS kullanımı için TLS 1.3'ü devre dışı bırak.
                    # (DLL yamaları oyunun HTTP'ini OpenSSL'e yönlendirir, ama
                    # Wine'ın kendisi GnuTLS kullanmaya devam eder — bu da JA3
                    # fingerprint sorununa takılabilir.)
                    etc_dir = os.path.join(DATA_DIR, "etc")
                    os.makedirs(etc_dir, exist_ok=True)
                    prio_file = os.path.join(etc_dir, "gnutls-no-tls13.cfg")
                    if not os.path.exists(prio_file):
                        try:
                            with open(prio_file, "w") as f:
                                f.write("[priorities]\nSYSTEM = NORMAL:-VERS-TLS1.3:%COMPAT\n")
                        except Exception as e:
                            print(f"[LAUNCH] GnuTLS öncelik dosyası yazma hatası: {e}")
                    env["GNUTLS_SYSTEM_PRIORITY_FILE"] = prio_file
                    env["GNUTLS_SYSTEM_PRIORITY_FAIL_ON_INVALID"] = "0"

                    # --- Adım 4: HBUI sign-in gate'i yamala ---
                    # ProxyPass auth sağlasa bile, oyun UI'ı XUser üzerinden
                    # giriş yapılmış olarak görünmeyebilir. Bu yama, multiplayer
                    # ve sunucu menülerinin açılmasını garanti eder.
                    # (Idempotent — .bak backup sadece ilk sefer oluşturulur)
                    try:
                        patch_gui_signin_gate(os.path.dirname(exe))
                    except Exception as e:
                        print(f"[LAUNCH] GUI yamalama hatası: {e}")

                    # --- Adım 5: Sign-in butonunu gizle (kosmetik) ---
                    # ProxyPass modunda in-game sign-in butonu çalışmaz,
                    # gizlemek kullanıcı deneyimini iyileştirir.
                    hide_signin_button(os.path.dirname(exe))

                    # ============================================================
                    # YAPILMAYAN işlemler (ve nedenleri):
                    # ============================================================
                    # restore_vanilla_state: ÇAĞRILMAZ
                    #   Sebep: xuser Proton DLL yamalarına ihtiyaç duyar.
                    #   restore_vanilla_state yamaları kaldırırsa oyun çöker.
                    #
                    # wine_apply_winegdk_prereqs: ÇAĞRILMAZ
                    #   Sebep: ProxyPass auth'u ağ katmanında halleder.
                    #   ForceMsaFacet ve RefreshToken gerekmez.
                    #
                    # run_xbl_preauth: ÇAĞRILMAZ
                    #   Sebep: device.json gerekmez, ProxyPass auth sağlar.
                    #
                    # WINEGDK_PREAUTH_DEVICE: SET EDİLMEZ
                    #   Sebep: device.json yok, ProxyPass auth sağlar.
                    # ============================================================
                except Exception as e:
                    print(f"[LAUNCH] Hata (ProxyPass hazırlık): {e}")
                    on_status(f"ProxyPass hazırlama hatası: {e}", "error")

                if jar and java_bin:
                    print(f"[PROXY] Başlatılıyor: {jar}")
                    proxy_proc = subprocess.Popen(
                        [
                            java_bin,
                            "-Djava.net.preferIPv4Stack=true",
                            "-XX:+IgnoreUnrecognizedVMOptions",
                            "--add-opens", "java.base/jdk.internal.misc=ALL-UNNAMED",
                            "--add-opens", "java.base/java.nio=ALL-UNNAMED",
                            "--add-opens", "java.base/java.lang=ALL-UNNAMED",
                            "--add-opens", "java.base/java.lang.reflect=ALL-UNNAMED",
                            "-Dio.netty.tryReflectionSetAccessible=true",
                            "-jar", jar
                        ],
                        cwd=os.path.dirname(jar),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        start_new_session=True,
                    )

                    result["proxy"] = proxy_proc
                    if result.get("cancelled"):
                        try:
                            proxy_proc.terminate()
                        except OSError:
                            pass
                        return

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
                    time.sleep(2)
                else:
                    missing = []
                    if not jar:
                        missing.append("ProxyPass.jar")
                    if not java_bin:
                        missing.append("Java Runtime")
                    print(f"[PROXY] Atlanıyor (eksik bileşenler: {', '.join(missing)})")

            if result.get("cancelled"):
                return
            if login_method == "ingame":
                import json
                from mc_launcher.config import DATA_DIR
                from mc_launcher.preauth import (
                    msa_refresh, run_xbl_preauth, wine_apply_winegdk_prereqs,
                    wine_reg_set_refresh_token, patch_gui_signin_gate,
                    install_gdk_xbox_dlls, hide_signin_button
                )
                
                on_status(_t("status_updating_session"), "running")
                
                # 1. Read token
                token_file = os.path.join(DATA_DIR, "msa", "token.json")
                tok = None
                if os.path.isfile(token_file):
                    try:
                        with open(token_file) as f:
                            tok_data = json.load(f)
                        tok = tok_data.get("refresh_token")
                    except Exception as e:
                        print(f"[LAUNCH] Token dosyası okuma hatası: {e}")
                
                fresh = None
                if tok:
                    try:
                        fresh = msa_refresh(tok)
                        if fresh and "error" in fresh:
                            print(f"[LAUNCH] Token refresh error: {fresh}")
                    except Exception as e:
                        print(f"[LAUNCH] Token yenileme hatası: {e}")
                
                if fresh and fresh.get("refresh_token"):
                    tok = fresh["refresh_token"]
                    try:
                        os.path.dirname(token_file) and os.makedirs(os.path.dirname(token_file), exist_ok=True)
                        with open(token_file, "w") as f:
                            json.dump({"refresh_token": tok, "obtained": int(time.time())}, f, indent=2)
                        print("[LAUNCH] Token başarıyla yenilendi ve kaydedildi.")
                    except Exception as e:
                        print(f"[LAUNCH] Yenilenen token kaydedilemedi: {e}")
                
                # 2. Registry prereqs
                pfx = os.path.join(COMPAT_DATA, "pfx")
                os.makedirs(pfx, exist_ok=True)
                wine_apply_winegdk_prereqs(proton, pfx, env)
                
                if tok:
                    wine_reg_set_refresh_token(proton, pfx, env, tok)
                
                # 3. Host-side pre-auth device.json generation
                access_token = (fresh or {}).get("access_token", "") if fresh else ""
                run_xbl_preauth(access_token, DATA_DIR)

                # Update auth.json with real gamertag from device.json so the launcher UI shows the correct name
                preauth_file = os.path.join(DATA_DIR, "winegdk-preauth", "device.json")
                if os.path.isfile(preauth_file):
                    try:
                        with open(preauth_file) as f:
                            dev_data = json.load(f)
                        gtg = dev_data.get("xbl_gamertag")
                        if gtg:
                            from mc_launcher.proxypass import auth_json_path
                            auth_path = auth_json_path(exe)
                            os.makedirs(os.path.dirname(auth_path), exist_ok=True)
                            with open(auth_path, "w", encoding="utf-8") as f:
                                json.dump({"gamertag": gtg}, f)
                            print(f"[LAUNCH] Updated auth.json with real gamertag: {gtg}")
                    except Exception as e:
                        print(f"[LAUNCH] Error updating auth.json with gamertag: {e}")
                
                # 4. Environment overrides for GnuTLS and pre-auth device path
                if os.path.isfile(preauth_file):
                    env["WINEGDK_PREAUTH_DEVICE"] = "Z:" + str(preauth_file).replace("/", "\\")
                    print(f"[LAUNCH] Preauth device mapped: {env['WINEGDK_PREAUTH_DEVICE']}")
                
                etc_dir = os.path.join(DATA_DIR, "etc")
                os.makedirs(etc_dir, exist_ok=True)
                prio_file = os.path.join(etc_dir, "gnutls-no-tls13.cfg")
                if not os.path.exists(prio_file):
                    try:
                        with open(prio_file, "w") as f:
                            f.write("[priorities]\nSYSTEM = NORMAL:-VERS-TLS1.3:%COMPAT\n")
                    except Exception as e:
                        print(f"[LAUNCH] GnuTLS öncelik dosyası yazma hatası: {e}")
                
                env["GNUTLS_SYSTEM_PRIORITY_FILE"] = prio_file
                env["GNUTLS_SYSTEM_PRIORITY_FAIL_ON_INVALID"] = "0"

                # 4.5. Install GDK/OSS DLLs and OpenSSL XCurl dependencies
                try:
                    install_gdk_xbox_dlls(os.path.dirname(exe), DATA_DIR, os.path.join(COMPAT_DATA, "pfx"), on_status)
                    hide_signin_button(os.path.dirname(exe))
                except Exception as e:
                    print(f"[LAUNCH] GDK/OpenSSL kurulum hatası: {e}")
 
                # 5. Patch HBUI sign-in gate to enable adding servers
                try:
                    patch_gui_signin_gate(os.path.dirname(exe))
                except Exception as e:
                    print(f"[LAUNCH] GUI yamalama hatası: {e}")

            # GDK multiplayer/LAN ve ekran kartı sürücülerinin izole çalışması için oyunu umu-launcher (Steam Linux Runtime) aracılığıyla başlatıyoruz.
            # UMU, steamrt3 (pressure-vessel) ile hem X11 hem Wayland bağlantılarını container içine alır.
            #
            # ÖNEMLİ: Artık her iki modda (proxypass + ingame) da UMU launcher kullanılıyor.
            # Sebep: xuser Proton, pressure-vessel (steamrt3) container'ı içinde
            # GPU sürücülerini (özellikle NVIDIA) doğru şekilde mount etmek için
            # UMU'ya ihtiyaç duyar. UMU olmadan xuser Proton GPU erişiminde
            # sorunlar yaşayabilir.
            umu_run = ensure_umu(on_status)
            if umu_run:
                # steamrt3 runtime'ının yüklü olup olmadığını kontrol edip, eksikse otomatik indirmeyi aktif ediyoruz.
                xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
                umu_shim = os.path.join(xdg_data, "umu", "steamrt3", "umu-shim")
                if not os.path.exists(umu_shim):
                    on_status(_t("status_downloading_steamrt3"), "running")
                    runtime_update = "1"
                else:
                    runtime_update = "0"

                # GDK-Proton'un Wayland altında düzgün çalışması ve pressure-vessel'in
                # ekran kartı sürücülerini (özellikle NVIDIA) container içine doğru şekilde mount edebilmesi için
                # WAYLAND_DISPLAY değişkenini ve X11 bağlantı yetkilerini geri yüklüyoruz.
                if "WAYLAND_DISPLAY" in os.environ:
                    env["WAYLAND_DISPLAY"] = os.environ["WAYLAND_DISPLAY"]
                
                disp = os.environ.get("DISPLAY")
                if disp:
                    env["DISPLAY"] = disp
                    import glob
                    mutter_cands = glob.glob(f"/run/user/{os.getuid()}/.mutter-Xwaylandauth.*")
                    candidates = [os.environ.get("XAUTHORITY"), os.path.expanduser("~/.Xauthority")] + mutter_cands
                    for cand in candidates:
                        if cand and os.path.exists(cand):
                            env["XAUTHORITY"] = cand
                            break
                    
                    import shutil
                    if shutil.which("xhost"):
                        user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
                        for arg in (f"+SI:localuser:{user}", "+local:"):
                            try:
                                from mc_launcher.flatpak import wrap_flatpak_cmd
                                xcmd = wrap_flatpak_cmd(["xhost", arg], env)
                                subprocess.run(xcmd, env=env, timeout=2,
                                               stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL)
                            except Exception:
                                pass

                cmd = [umu_run, exe]
                env.update({
                    "GAMEID": "0",
                    "PROTONPATH": os.path.dirname(proton),
                    "PROTON_VERB": "run",
                    "WINEPREFIX": os.path.join(COMPAT_DATA, "pfx"),
                    "STEAM_COMPAT_CLIENT_INSTALL_PATH": os.path.expanduser("~/.steam/steam"),
                    "UMU_RUNTIME_UPDATE": runtime_update,
                    # Hata ayıklama logları için:
                    "PROTON_LOG": "1",
                    "PROTON_LOG_DIR": os.path.dirname(COMPAT_DATA),
                    # WindowsAppRuntime hata pencerelerini ve çökmeleri engellemek için gerekli değişkenler:
                    "MICROSOFT_WINDOWSAPPRUNTIME_BOOTSTRAP_INITIALIZE_SHOWUI": "0",
                    "MICROSOFT_WINDOWSAPPRUNTIME_BOOTSTRAP_INITIALIZE_FAILFAST": "0",
                    "MICROSOFT_WINDOWSAPPRUNTIME_DEPLOYMENT_INITIALIZE_ONERRORSHOWUI": "0",
                })
            else:
                if mangohud_on:
                    cmd = ["mangohud", "--dlsym", proton, "run", exe]
                else:
                    cmd = [proton, "run", exe]

            if result.get("cancelled"):
                if proxy_proc and proxy_proc.poll() is None:
                    try:
                        proxy_proc.terminate()
                        proxy_proc.wait(timeout=2)
                    except Exception:
                        try:
                            proxy_proc.kill()
                        except Exception:
                            pass
                return

            prefix_dir = Path(os.path.join(COMPAT_DATA, "pfx"))
            game_dir = Path(os.path.dirname(exe))
            try:
                install_gameinput(prefix_dir, game_dir)
            except Exception as e:
                print(f"[LAUNCH] GameInput yükleme hatası: {e}")

            from mc_launcher.flatpak import wrap_flatpak_cmd
            cmd = wrap_flatpak_cmd(cmd, env, cwd=os.path.dirname(exe))
            print(f"[LAUNCH] {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(exe),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            result["game"] = proc
            if result.get("cancelled"):
                try:
                    proc.terminate()
                except OSError:
                    pass
                if proxy_proc and proxy_proc.poll() is None:
                    try:
                        proxy_proc.terminate()
                    except OSError:
                        pass
                return
            if on_started:
                on_started(proc, proxy_proc)

            def _rd(pipe, tag):
                try:
                    for raw in iter(pipe.readline, b""):
                        print(f"[{tag}] {raw.decode(errors='replace').rstrip()}")
                finally:
                    pipe.close()

            t1 = threading.Thread(target=_rd, args=(proc.stdout, "OUT"), daemon=True)
            t2 = threading.Thread(target=_rd, args=(proc.stderr, "ERR"), daemon=True)
            t1.start()
            t2.start()

            on_status(_t("status_game_running"), "running")
            ret = proc.wait()
            t1.join(timeout=3)
            t2.join(timeout=3)
            on_status(_t("status_game_exited", ret=ret), "ok" if ret == 0 else "error")
        except Exception as e:
            print(f"[HATA]\n{traceback.format_exc()}")
            on_status(_t("status_game_error", error=str(e)), "error")
        finally:
            if relay:
                try:
                    relay.stop()
                except Exception as e:
                    print(f"[PROXY] Error stopping relay: {e}")
            if proxy_proc and proxy_proc.poll() is None:
                try:
                    proxy_proc.terminate()
                    proxy_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proxy_proc.kill()
                except OSError:
                    pass
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
                    if target in files:
                        found.append(os.path.join(cur, target))
            except Exception as e:
                print(f"Tarama hatası ({root_dir}): {e}")

        from gi.repository import GLib
        GLib.idle_add(on_done, found)

    on_status(_t("status_scanning_disks"), "running")
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
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
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
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            os.replace(tmp_path, path)
            return True
        except OSError as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise
    except OSError as e:
        print(f"[LAUNCH] options.txt patch error: {e}")
        return False
