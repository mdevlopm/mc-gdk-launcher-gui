"""
mc_launcher/preauth.py — Microsoft / Xbox Live native login and pre-auth chain.
Allows bypassing GnuTLS TLS 1.3 JA3 fingerprint block by Microsoft Azure Front Door.
"""

import os
import json
import base64
import time
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import uuid as _uuid
from typing import Optional

MSA_CLIENT_ID = "0000000048183522"     # Bedrock Android (matches WineGDK XUser)
MSA_SCOPE = "service::user.auth.xboxlive.com::MBI_SSL"
MSA_TOKEN_URL = "https://login.live.com/oauth20_token.srf"


def msa_refresh(refresh_token: str) -> Optional[dict]:
    """Trade a refresh token for a fresh access token."""
    fields = {
        "client_id": MSA_CLIENT_ID,
        "scope": MSA_SCOPE,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        MSA_TOKEN_URL,
        data=data,
        method="POST",
        headers={
            "User-Agent": "mc-gdk-launcher",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
            if isinstance(res, dict) and "access_token" in res:
                return res
            return None
    except Exception as e:
        print(f"[PreAuth] MSA refresh failed: {e}")
        return None


def run_xbl_preauth(msa_access_token: str, data_dir: str) -> bool:
    """
    Run the whole Xbox Live auth chain (device + user + SISU tokens) from host's OpenSSL
    and write to device.json where xgameruntime.dll reads it instead of making blocked HTTP calls.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    except ImportError as e:
        print(f"[PreAuth] xbl_preauth: missing Python dep ({e}) — skipping")
        return False

    cache = os.path.join(data_dir, "winegdk-preauth")
    os.makedirs(cache, exist_ok=True)
    key_path = os.path.join(cache, "device-key.pem")
    out_path = os.path.join(cache, "device.json")
    device_id_path = os.path.join(cache, "device-id.txt")

    if os.path.exists(key_path) and os.path.exists(device_id_path):
        try:
            with open(key_path, "rb") as f:
                priv = serialization.load_pem_private_key(f.read(), password=None)
            with open(device_id_path, "r") as f:
                device_id = f.read().strip()
        except Exception:
            priv = None
            device_id = None
    else:
        priv = None
        device_id = None

    if priv is None:
        priv = ec.generate_private_key(ec.SECP256R1())
        device_id = "{" + str(_uuid.uuid4()) + "}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(key_path, flags, 0o600)
        try:
            with open(fd, "wb") as f:
                f.write(priv.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption()
                ))
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        with open(device_id_path, "w") as f:
            f.write(device_id)

    pub_numbers = priv.public_key().public_numbers()
    x_b64 = base64.b64encode(pub_numbers.x.to_bytes(32, "big")).decode()
    y_b64 = base64.b64encode(pub_numbers.y.to_bytes(32, "big")).decode()
    proof_key = {
        "alg": "ES256",
        "crv": "P-256",
        "kty": "EC",
        "use": "sig",
        "x": x_b64,
        "y": y_b64
    }

    def _sign_header(method, path, body_bytes):
        t_float = time.time()
        t_secs = int(t_float)
        t_frac = int((t_float - t_secs) * 10000000)
        now_ft = (t_secs + 11644473600) * 10000000 + t_frac
        ver = (1).to_bytes(4, "big")
        ts = now_ft.to_bytes(8, "big")
        hash_input = (
            ver + b"\0" + ts + b"\0"
            + method.encode() + b"\0"
            + path.encode() + b"\0"
            + b"" + b"\0"
            + body_bytes + b"\0"
        )
        sig_der = priv.sign(hash_input, ec.ECDSA(hashes.SHA256()))
        r2, s2 = decode_dss_signature(sig_der)
        sig_raw = r2.to_bytes(32, "big") + s2.to_bytes(32, "big")
        return base64.b64encode(ver + ts + sig_raw).decode()

    class _HttpResp:
        def __init__(self, status_code, raw):
            self.status_code = status_code
            self._raw = raw
            self.text = raw.decode("utf-8", "replace")
        def json(self):
            try:
                return json.loads(self._raw)
            except Exception:
                return {}

    def _xbl_post(url, body_dict):
        body_bytes = json.dumps(body_dict, separators=(",", ":")).encode()
        from urllib.parse import urlparse
        path = urlparse(url).path
        req = urllib.request.Request(
            url,
            data=body_bytes,
            method="POST",
            headers={
                "User-Agent": "XAL Xbox Live Game (Windows; SDK; 1.0.0.0)",
                "Content-Type": "application/json",
                "x-xbl-contract-version": "1",
                "Signature": _sign_header("POST", path, body_bytes),
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return _HttpResp(resp.status, resp.read())
        except urllib.error.HTTPError as e:
            return _HttpResp(e.code, e.read())

    # ---- 1. /device/authenticate ----
    try:
        r = _xbl_post("https://device.auth.xboxlive.com/device/authenticate", {
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "AuthMethod": "ProofOfPossession",
                "Id": device_id,
                "DeviceType": "Win32",
                "Version": "10.0.22631",
                "ProofKey": proof_key,
            },
        })
    except Exception as e:
        print(f"[PreAuth] device.auth POST failed: {e}")
        return False
    if r.status_code != 200:
        print(f"[PreAuth] device.auth HTTP {r.status_code} — {r.text[:200]}")
        return False
    j = r.json()
    device_token = j.get("Token")
    if not device_token:
        print(f"[PreAuth] Device authenticate response missing 'Token' key.")
        return False

    # ---- 2. /user/authenticate ----
    user_token = None
    user_token_expiry = None
    if msa_access_token:
        try:
            ru = _xbl_post("https://user.auth.xboxlive.com/user/authenticate", {
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT",
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": "t=" + msa_access_token,
                },
            })
            if ru.status_code == 200:
                uj = ru.json()
                user_token = uj["Token"]
                user_token_expiry = uj.get("NotAfter", "")
            else:
                print(f"[PreAuth] user.auth HTTP {ru.status_code} — {ru.text[:200]}")
        except Exception as e:
            print(f"[PreAuth] user.auth POST failed: {e}")

    # ---- 3. sisu helper ----
    def _sisu(rp):
        if not msa_access_token:
            return None
        try:
            r2 = _xbl_post("https://sisu.xboxlive.com/authorize", {
                "AccessToken": "t=" + msa_access_token,
                "AppId": "0000000048183522",
                "deviceToken": device_token,
                "Sandbox": "RETAIL",
                "UseModernGamertag": True,
                "SiteName": "user.auth.xboxlive.com",
                "RelyingParty": rp,
                "OfferTermsAcceptance": True,
                "AcceptOffers": True,
                "ProofKey": proof_key,
            })
            if r2.status_code != 200:
                print(f"[PreAuth] sisu({rp}) HTTP {r2.status_code} — {r2.text[:200]}")
                return None
            return r2.json()
        except Exception as ex:
            print(f"[PreAuth] sisu({rp}) failed: {ex}")
            return None

    # ---- 3a. sisu /authorize for http://xboxlive.com ----
    xbl_sisu = _sisu("http://xboxlive.com") or {}
    xbl_auth = xbl_sisu.get("AuthorizationToken", {}) if xbl_sisu else {}
    xbl_token = xbl_auth.get("Token")
    xbl_expiry = xbl_auth.get("NotAfter", "") if xbl_auth else ""
    xbl_claims = {}
    try:
        xbl_claims = xbl_auth["DisplayClaims"]["xui"][0]
    except (KeyError, IndexError, TypeError):
        pass

    # ---- 3b. sisu /authorize for PlayFab ----
    pf_sisu = _sisu("https://b980a380.minecraft.playfabapi.com/") or {}
    pf_auth = pf_sisu.get("AuthorizationToken", {}) if pf_sisu else {}
    sisu_rp = "https://b980a380.minecraft.playfabapi.com/" if pf_auth.get("Token") else None
    sisu_token = pf_auth.get("Token")
    sisu_expiry = pf_auth.get("NotAfter", "")
    sisu_uhs = None
    try:
        sisu_uhs = pf_auth["DisplayClaims"]["xui"][0].get("uhs")
    except (KeyError, IndexError, TypeError):
        pass

    # ---- 3c. sisu /authorize for multiplayer RP ----
    mp_sisu = _sisu("https://multiplayer.minecraft.net/") or {}
    mp_auth = mp_sisu.get("AuthorizationToken", {}) if mp_sisu else {}
    mp_rp = "https://multiplayer.minecraft.net/" if mp_auth.get("Token") else None
    mp_token = mp_auth.get("Token")
    mp_expiry = mp_auth.get("NotAfter", "")
    mp_uhs = None
    try:
        mp_uhs = mp_auth["DisplayClaims"]["xui"][0].get("uhs")
    except (KeyError, IndexError, TypeError):
        pass

    # ---- 3d. sisu /authorize for licensing RP ----
    lic_sisu = _sisu("http://licensing.xboxlive.com") or {}
    lic_auth = lic_sisu.get("AuthorizationToken", {}) if lic_sisu else {}
    lic_rp = "http://licensing.xboxlive.com" if lic_auth.get("Token") else None
    lic_token = lic_auth.get("Token")
    lic_expiry = lic_auth.get("NotAfter", "")
    lic_uhs = None
    try:
        lic_uhs = lic_auth["DisplayClaims"]["xui"][0].get("uhs")
    except (KeyError, IndexError, TypeError):
        pass

    priv_d = priv.private_numbers().private_value
    ecc_blob = (
        (0x32534345).to_bytes(4, "little") + (32).to_bytes(4, "little")
        + pub_numbers.x.to_bytes(32, "big")
        + pub_numbers.y.to_bytes(32, "big")
        + priv_d.to_bytes(32, "big")
    )

    out = {
        "device_id": device_id,
        "ecc_private_blob_b64": base64.b64encode(ecc_blob).decode(),
        "device_token": device_token,
        "device_token_expiry": j.get("NotAfter", ""),
        "user_token": user_token,
        "user_token_expiry": user_token_expiry,
        "xbl_token": xbl_token,
        "xbl_token_expiry": xbl_expiry,
        "xbl_xuid": xbl_claims.get("xid"),
        "xbl_gamertag": xbl_claims.get("gtg"),
        "xbl_age_group": xbl_claims.get("agg"),
        "xbl_uhs": xbl_claims.get("uhs"),
        "sisu_rp": sisu_rp,
        "sisu_token": sisu_token,
        "sisu_uhs": sisu_uhs,
        "sisu_expiry": sisu_expiry,
        "mp_rp": mp_rp,
        "mp_token": mp_token,
        "mp_uhs": mp_uhs,
        "mp_expiry": mp_expiry,
        "lic_rp": lic_rp,
        "lic_token": lic_token,
        "lic_uhs": lic_uhs,
        "lic_expiry": lic_expiry,
        "obtained": int(time.time()),
    }

    import tempfile
    fd, tmp = tempfile.mkstemp(dir=str(os.path.dirname(out_path)), prefix=".device-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(out, indent=2))
            f.flush()
            try:
                os.fsync(fd)
            except OSError:
                pass
        os.replace(tmp, out_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    print("[PreAuth] Host-side Xbox Live pre-auth completed successfully.")
    return True


def wine_apply_winegdk_prereqs(proton_bin: str, pfx_path: str, env: dict):
    """Write required keys to Wine registry to enable Xbox Live APIs and disable TLS 1.3 block."""
    env_copy = env.copy()
    env_copy["WINEPREFIX"] = pfx_path

    def _regadd(*args):
        cmd = [proton_bin, "run", "reg", "add"] + list(args) + ["/f"]
        try:
            subprocess.run(cmd, env=env_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except Exception as e:
            print(f"[PreAuth] reg add {args[0]} failed: {e}")

    # OEM ConsoleMode=8 mimics console to avoid "dev build" locking multiplayer
    _regadd(r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\OEM", "/v", "ConsoleMode", "/t", "REG_DWORD", "/d", "8")
    # Force MSA facet (unlocks multiplayer/servers menu)
    _regadd(r"HKLM\Software\Wine\WineGDK", "/v", "ForceMsaFacet", "/t", "REG_DWORD", "/d", "1")
    # Force WinHttp protocols to use TLS 1.2 (DefaultSecureProtocols = 2560)
    _regadd(r"HKLM\Software\Microsoft\Windows\CurrentVersion\Internet Settings\WinHttp", "/v", "DefaultSecureProtocols", "/t", "REG_DWORD", "/d", "2560")
    # Disable TLS 1.3 Client Schannel handshake in WinHttp
    _regadd(r"HKLM\Software\Microsoft\Schannel\Protocols\TLS 1.3\Client", "/v", "DisabledByDefault", "/t", "REG_DWORD", "/d", "1")

    # Mute app runtime UI crash errors
    for name, val in (
        ("MICROSOFT_WINDOWSAPPRUNTIME_BOOTSTRAP_INITIALIZE_SHOWUI", "0"),
        ("MICROSOFT_WINDOWSAPPRUNTIME_BOOTSTRAP_INITIALIZE_FAILFAST", "0"),
        ("MICROSOFT_WINDOWSAPPRUNTIME_DEPLOYMENT_INITIALIZE_ONERRORSHOWUI", "0"),
    ):
        _regadd(r"HKCU\Environment", "/v", name, "/t", "REG_SZ", "/d", val)


def wine_reg_set_refresh_token(proton_bin: str, pfx_path: str, env: dict, token: str):
    """Seed the MSA refresh token where WineGDK's XUser reads it."""
    env_copy = env.copy()
    env_copy["WINEPREFIX"] = pfx_path

    for root in ["HKLM", "HKCU"]:
        cmd = [
            proton_bin, "run", "reg", "add",
            f"{root}\\Software\\Wine\\WineGDK",
            "/v", "RefreshToken",
            "/t", "REG_SZ",
            "/d", token,
            "/f"
        ]
        try:
            subprocess.run(cmd, env=env_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except Exception as e:
            print(f"[PreAuth] reg add {root} RefreshToken failed: {e}")


def patch_gui_signin_gate(game_dir: str):
    """
    Patch Minecraft Bedrock HBUI JS files to bypass the 'Microsoft Account required' warning
    and allow adding and joining servers on Linux/Wine.
    """
    import glob
    import shutil
    import re
    
    js_pattern = os.path.join(game_dir, "data", "gui", "dist", "hbui", "index-*.js")
    js_files = glob.glob(js_pattern)
    for js_path in js_files:
        try:
            with open(js_path, "rb") as f:
                data = f.read()
            
            orig = data
            
            # 1. Patch l3(e) function to allow Friends/Realms/Servers tab access
            target_l3 = (
                "function l3(e){return(0,l.useFacetMap)(((t,a)=>{switch(e){"
                "case r3.FRIENDS:return!TI(a.platform)&&!xI(a.platform)&&!t.isLoggedInWithMicrosoftAccount||(TI(a.platform)||xI(a.platform))&&!t.isLoggedInWithMicrosoftAccount&&!t.isSignedInPlatformNetwork;"
                "case r3.REALMS:return(TI(a.platform)||xI(a.platform))&&!t.isSignedInPlatformNetwork||!t.isLoggedInWithMicrosoftAccount;"
                "case r3.SERVERS:case r3.TEMPLATES:default:return!t.isLoggedInWithMicrosoftAccount}}),"
                "[e],[(0,l.useSharedFacet)(FF),(0,l.useSharedFacet)(_l)])}"
            ).encode("utf-8")
            
            patched_l3 = (
                "function l3(e){return(0,l.useFacetMap)(((t,a)=>{switch(e){"
                "case r3.FRIENDS:return!1;"
                "case r3.REALMS:return!1;"
                "case r3.SERVERS:case r3.TEMPLATES:default:return!1}}),"
                "[e],[(0,l.useSharedFacet)(FF),(0,l.useSharedFacet)(_l)])}"
            ).encode("utf-8")
            
            # 2. Patch m3() function to allow multiplayer
            target_m3 = (
                "function m3(){const e=(0,l.useFacetMap)((e=>TI(e.platform)||xI(e.platform)),[],[(0,l.useSharedFacet)(_l)]);"
                "return(0,l.useFacetMap)(((e,t,a)=>!a&&(!e.isLoggedInWithMicrosoftAccount||e.userPermissions.multiplayer.denyReasons.includes(bF.XboxLive)||t&&!e.hasPremiumNetworkAccess)),"
                "[],[(0,l.useSharedFacet)(FF),e,n3()])}"
            ).encode("utf-8")
            
            patched_m3 = (
                "function m3(){const e=(0,l.useFacetMap)((e=>TI(e.platform)||xI(e.platform)),[],[(0,l.useSharedFacet)(_l)]);"
                "return(0,l.useFacetMap)(((e,t,a)=>!1),"
                "[],[(0,l.useSharedFacet)(FF),e,n3()])}"
            ).encode("utf-8")
            
            if target_l3 in data:
                data = data.replace(target_l3, patched_l3)
            if target_m3 in data:
                data = data.replace(target_m3, patched_m3)

            # 3. Add version-tolerant BedrockOnLinux patches as fallbacks/complements
            # Servers-tab "need a Microsoft account" banner: wB() -> ""
            needle = 'function wB(){return(0,l.useFacetMap)'.encode("utf-8")
            repl_needle = 'function wB(){return"";return'.encode("utf-8")
            if needle in data and b'function wB(){return"";return' not in data:
                data = data.replace(needle, repl_needle, 1)

            # Remove the broken in-game "Sign in" button.
            m = re.search(rb'(_NotLoggedInWarning_OreUI`\)\}\),\\[[^\\]]*\\]\);)'
                          rb'(return r\.createElement\\(sx,)', data)
            if m and b'return null;return r.createElement(sx,' not in data:
                data = data[:m.start()] + m.group(1) + b'return null;' + m.group(2) + data[m.end():]
                
            if data != orig:
                bak_path = js_path + ".bak"
                if not os.path.exists(bak_path):
                    try:
                        shutil.copy2(js_path, bak_path)
                    except Exception as e:
                        print(f"[PreAuth] Error creating backup of {js_path}: {e}")
                        continue
                with open(js_path, "wb") as f:
                    f.write(data)
                print(f"[PreAuth] Patched HBUI sign-in gate in {os.path.basename(js_path)}")
        except Exception as e:
            print(f"[PreAuth] Error patching {js_path}: {e}")


def apply_patch(path: str, off: int, expect: bytes, new: bytes, what: str):
    import shutil
    try:
        with open(path, "rb") as f:
            raw = bytearray(f.read())
        if bytes(raw[off:off + len(new)]) == new:
            print(f"[PreAuth] {what}: already patched")
            return True
        if bytes(raw[off:off + len(expect)]) != expect:
            print(f"[PreAuth] {what}: unexpected bytes at 0x{off:x} — patch skipped.")
            return False
        bk = path + ".bol-orig"
        if not os.path.exists(bk):
            shutil.copy2(path, bk)
        raw[off:off + len(new)] = new
        with open(path, "wb") as f:
            f.write(raw)
        print(f"[PreAuth] {what}: patched successfully")
        return True
    except Exception as e:
        print(f"[PreAuth] apply_patch failed: {e}")
        return False


def _patch_lhc_xcurl_gate(game_dir: str):
    """Force libHttpClient.GDK onto the XCurl HTTP provider."""
    import re
    dll = os.path.join(game_dir, "libHttpClient.GDK.dll")
    if not os.path.isfile(dll):
        print("[PreAuth] libHttpClient.GDK.dll not found, skipping routing patch.")
        return
    try:
        with open(dll, "rb") as f:
            data = f.read()
        # add eax,-2 ; mov edx,4 ; lea rcx,[rip+imm32] ; cmp eax,6 ; ja rel32
        m = re.search(rb"\x83\xc0\xfe\xba\x04\x00\x00\x00\x48\x8d\x0d.{4}\x83\xf8\x06"
                      rb"\x0f\x87.{4}", data, re.S)
        if not m:
            print("[PreAuth] libHttpClient provider gate not found — XCurl routing patch skipped.")
            return
        ja_off = m.start() + 18          # past add(3)+mov(5)+lea(7)+cmp(3)
        expect = data[ja_off:ja_off + 6]
        if expect[:2] != b"\x0f\x87":
            print("[PreAuth] libHttpClient gate anchor misaligned — XCurl patch skipped.")
            return
            
        apply_patch(dll, ja_off, expect, b"\x90" * 6, "libHttpClient -> force XCurl provider")
    except Exception as e:
        print(f"[PreAuth] Error patching libHttpClient: {e}")


def _install_cryptbase_in_prefix(pfx_path: str, data_dir: str):
    import shutil
    import hashlib
    openssl_set = os.path.join(data_dir, "xodus-xcurl", "openssl-set")
    src = os.path.join(openssl_set, "cryptbase.dll")
    if not os.path.isfile(src):
        print(f"[PreAuth] cryptbase stub source {src} not found!")
        return
    sys32 = os.path.join(pfx_path, "drive_c", "windows", "system32")
    if not os.path.isdir(sys32):
        print(f"[PreAuth] system32 folder not found at {sys32}")
        return
    dst = os.path.join(sys32, "cryptbase.dll")
    try:
        def sha1(p):
            with open(p, "rb") as f:
                return hashlib.sha1(f.read()).hexdigest()
        if os.path.isfile(dst) and sha1(dst) == sha1(src):
            print("[PreAuth] cryptbase RNG stub is already installed in system32.")
            return
        
        bak = os.path.join(sys32, "cryptbase.dll.bol-orig")
        if os.path.isfile(dst) and not os.path.exists(bak):
            shutil.copy2(dst, bak)
        shutil.copy2(src, dst)
        print("[PreAuth] Installed cryptbase RNG stub in system32.")
    except Exception as e:
        print(f"[PreAuth] cryptbase RNG stub installation failed: {e}")


def install_gdk_xbox_dlls(game_dir: str, data_dir: str, pfx_path: str, on_status=None):
    """
    Downloads and installs the custom OpenSSL XCurl set, the Xbox Live OSS DLLs,
    and applies binary patching and prefix RNG stubs to make in-game login work.
    """
    import shutil
    import urllib.request
    import tarfile
    import glob
    from mc_launcher.i18n import _t
    
    cache_dir = os.path.join(data_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    
    def download_with_progress(url, dest, label):
        req = urllib.request.Request(url, headers={"User-Agent": "mc-gdk-launcher"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if on_status:
                    if total > 0:
                        percent = min(100, int(done * 100 / total))
                        done_mb = done / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        on_status(f"{label}... {done_mb:.2f} MB / {total_mb:.2f} MB ({percent}%)", "running")
                    else:
                        on_status(f"{label}... ({done // 1024} KB)", "running")
    
    # 1. Download GDK deps (libHttpClient.GDK.dll, XCurl.dll)
    gdk_deps_url = "https://github.com/minecraft-linux/mcpelauncher-gdk-dependencies/releases/download/v0.0.0"
    gdk_deps_dlls = ("libHttpClient.GDK.dll", "XCurl.dll")
    
    for nm in gdk_deps_dlls:
        dst = os.path.join(game_dir, nm)
        bak = dst + ".bol-orig"
        if os.path.exists(bak):
            continue
        cached = os.path.join(cache_dir, "gdkdeps-" + nm)
        if not os.path.isfile(cached):
            print(f"[PreAuth] Downloading {nm}...")
            try:
                download_with_progress(f"{gdk_deps_url}/{nm}", cached, _t("preauth_download_xbox_live", name=nm))
            except Exception as e:
                print(f"[PreAuth] Error downloading {nm}: {e}")
                continue
        if os.path.isfile(dst) and not os.path.exists(bak):
            shutil.copy2(dst, bak)
        if os.path.isfile(cached):
            shutil.copy2(cached, dst)
            print(f"[PreAuth] Installed GDK dep {nm}")

    # 2. Download and extract OpenSSL XCurl set
    openssl_set_dir = os.path.join(data_dir, "xodus-xcurl", "openssl-set")
    marker_file = os.path.join(openssl_set_dir, ".rev")
    target_rev = "56a296acc12a" # The working published revision
    
    have_set = (
        os.path.isfile(os.path.join(openssl_set_dir, "libcurl-4.dll")) and
        os.path.isfile(os.path.join(openssl_set_dir, "xcurl-cashim.dll"))
    )
    
    rev_ok = False
    if have_set and os.path.isfile(marker_file):
        try:
            with open(marker_file) as f:
                if f.read().strip() == target_rev:
                    rev_ok = True
        except Exception:
            pass
            
    if not rev_ok:
        asset_url = f"https://github.com/Wyze3306/BedrockOnLinux/releases/download/v1.0.5/openssl-xcurl-set-{target_rev}.tar.gz"
        archive_path = os.path.join(cache_dir, f"openssl-xcurl-set-{target_rev}.tar.gz")
        if not os.path.isfile(archive_path):
            print(f"[PreAuth] Downloading OpenSSL XCurl set...")
            try:
                download_with_progress(asset_url, archive_path, _t("preauth_download_offline_deps"))
            except Exception as e:
                print(f"[PreAuth] Failed to download OpenSSL XCurl set: {e}")
                
        if os.path.isfile(archive_path):
            if on_status:
                on_status(_t("preauth_install_offline_deps"), "running")
            print(f"[PreAuth] Extracting OpenSSL XCurl set...")
            tmp_extract = os.path.join(data_dir, "xodus-xcurl", ".set-dl")
            if os.path.exists(tmp_extract):
                shutil.rmtree(tmp_extract, ignore_errors=True)
            os.makedirs(tmp_extract, exist_ok=True)
            try:
                dest_real = os.path.realpath(tmp_extract)
                with tarfile.open(archive_path) as t:
                    try:
                        t.extractall(tmp_extract, filter="tar")
                    except TypeError:
                        for m in t.getmembers():
                            member_path = os.path.realpath(os.path.join(tmp_extract, m.name))
                            if not (member_path == dest_real or member_path.startswith(dest_real + os.sep)):
                                raise RuntimeError(f"Güvensiz arşiv yolu: {m.name}")
                        t.extractall(tmp_extract)
                
                os.makedirs(openssl_set_dir, exist_ok=True)
                src_dir = tmp_extract
                subdirs = os.listdir(tmp_extract)
                if len(subdirs) == 1 and os.path.isdir(os.path.join(tmp_extract, subdirs[0])):
                    src_dir = os.path.join(tmp_extract, subdirs[0])
                    
                for item in os.listdir(src_dir):
                    item_path = os.path.join(src_dir, item)
                    if os.path.isfile(item_path):
                        shutil.copy2(item_path, os.path.join(openssl_set_dir, item))
                
                with open(marker_file, "w") as f:
                    f.write(target_rev)
                print("[PreAuth] Unpacked OpenSSL XCurl set successfully.")
            except Exception as e:
                print(f"[PreAuth] Error unpacking OpenSSL XCurl set: {e}")
            finally:
                if os.path.exists(tmp_extract):
                    shutil.rmtree(tmp_extract, ignore_errors=True)
                    
    # 3. Copy DLLs to the game Binaries directory
    libcurl = os.path.join(openssl_set_dir, "libcurl-4.dll")
    shim = os.path.join(openssl_set_dir, "xcurl-cashim.dll")
    if os.path.isfile(libcurl) and os.path.isfile(shim):
        for nm in ("XCurl.dll", "Xcurl.dll"):
            dst = os.path.join(game_dir, nm)
            bak = dst + ".bol-orig"
            if os.path.isfile(dst) and not os.path.exists(bak):
                shutil.copy2(dst, bak)
                
        # Copy dependency DLLs
        skip = {"cryptbase.dll", "xcurl-cashim.dll"}
        for dll in glob.glob(os.path.join(openssl_set_dir, "*.dll")):
            name = os.path.basename(dll)
            if name in skip or name.endswith((".bak", ".fwd-bak", ".1export-bak")):
                continue
            shutil.copy2(dll, os.path.join(game_dir, name))
            
        # Real OpenSSL libcurl
        shutil.copy2(libcurl, os.path.join(game_dir, "xcurl_real.dll"))
        
        # Shim becomes XCurl.dll
        for nm in ("XCurl.dll", "Xcurl.dll"):
            shutil.copy2(shim, os.path.join(game_dir, nm))
            
        # Download and copy cacert.pem
        cacert = os.path.join(cache_dir, "cacert.pem")
        if not os.path.isfile(cacert):
            print("[PreAuth] Downloading SSL cacert bundle...")
            try:
                download_with_progress("https://curl.se/ca/cacert.pem", cacert, _t("preauth_download_ssl"))
            except Exception as e:
                print(f"[PreAuth] Failed to download cacert: {e}")
        if os.path.isfile(cacert):
            shutil.copy2(cacert, os.path.join(game_dir, "cacert.pem"))
            for base in (game_dir, os.path.dirname(game_dir)):
                crt = os.path.join(base, "etc", "ssl", "certs", "ca-bundle.crt")
                os.makedirs(os.path.dirname(crt), exist_ok=True)
                shutil.copy2(cacert, crt)
            print("[PreAuth] SSL certificates bundle copied.")
            
        print("[PreAuth] OpenSSL XCurl (CA-injecting shim) + deps installed.")
    else:
        print("[PreAuth] OpenSSL XCurl set not found or incomplete.")
        
    # 4. Patch libHttpClient
    _patch_lhc_xcurl_gate(game_dir)
    
    # 5. Install cryptbase RNG stub in Wine prefix
    _install_cryptbase_in_prefix(pfx_path, data_dir)


def hide_signin_button(game_dir: str):
    """Hide the broken in-game title-screen 'Sign in' button (cosmetic)."""
    import re
    try:
        vanilla = os.path.join(game_dir, "data", "resource_packs", "vanilla")
        bra = os.path.join(vanilla, "__brarchive", "ui.brarchive")
        if os.path.exists(bra):
            bak = bra + ".bol-bak"
            if not os.path.exists(bak):
                os.rename(bra, bak)
        ss = os.path.join(vanilla, "ui", "start_screen.json")
        if not os.path.isfile(ss):
            return
            
        ss_bak = ss + ".bol-bak"
        if not os.path.exists(ss_bak):
            import shutil
            try:
                shutil.copy2(ss, ss_bak)
                print("[PreAuth] Created backup of start_screen.json")
            except Exception as e:
                print(f"[PreAuth] Error backing up start_screen.json: {e}")

        with open(ss, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        new, n = re.subn(
            r'("xbl_signin_button@start\.xbl_signin_button"\s*:\s*\{\}\s*\}\s*\]'
            r'\s*,\s*"bindings"\s*:\s*\[\s*\{\s*"binding_name"\s*:\s*)'
            r'"#sign_in_visible"',
            r'\g<1>"#edu_demo_only_ui_visible"', txt, count=1)
        if n:
            with open(ss, "w", encoding="utf-8") as f:
                f.write(new)
            print("[PreAuth] Hid the broken in-game Sign-in button.")
    except Exception as e:
        print(f"[PreAuth] hide_signin_button error: {e}")


def restore_vanilla_state(game_dir: str, pfx_path: str):
    """Restores the original game files and prefix settings to revert in-game hacks."""
    import shutil
    import glob
    
    print("[Restore] Restoring game files and Wine prefix to vanilla...")

    # 1. Restore DLL backups in game_dir
    for nm in ("XCurl.dll", "Xcurl.dll", "libHttpClient.GDK.dll"):
        dst = os.path.join(game_dir, nm)
        orig = dst + ".bol-orig"
        if os.path.isfile(orig):
            try:
                shutil.copy2(orig, dst)
                print(f"[Restore] Restored original {nm} from backup.")
            except Exception as e:
                print(f"[Restore] Error restoring {nm}: {e}")
                
    # Delete extra DLLs that were copied
    extra_dlls = ["libcurl-4.dll", "xcurl_real.dll", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "cacert.pem"]
    for dll in extra_dlls:
        path = os.path.join(game_dir, dll)
        if os.path.isfile(path):
            try:
                os.remove(path)
                print(f"[Restore] Removed extra file: {dll}")
            except Exception as e:
                print(f"[Restore] Error removing {dll}: {e}")
                
    # 2. Restore GUI/HBUI JS files
    js_pattern = os.path.join(game_dir, "data", "gui", "dist", "hbui", "index-*.js")
    for js_path in glob.glob(js_pattern):
        bak = js_path + ".bak"
        if os.path.isfile(bak):
            try:
                shutil.copy2(bak, js_path)
                print(f"[Restore] Restored GUI script: {os.path.basename(js_path)}")
            except Exception as e:
                print(f"[Restore] Error restoring GUI script: {e}")
                
    # 3. Restore Resource Pack start screen and brarchives
    vanilla = os.path.join(game_dir, "data", "resource_packs", "vanilla")
    bra = os.path.join(vanilla, "__brarchive", "ui.brarchive")
    bra_bak = bra + ".bol-bak"
    if os.path.isfile(bra_bak):
        try:
            if os.path.exists(bra):
                os.remove(bra)
            os.rename(bra_bak, bra)
            print("[Restore] Restored vanilla ui.brarchive resource pack.")
        except Exception as e:
            print(f"[Restore] Error restoring ui.brarchive: {e}")
            
    ss = os.path.join(vanilla, "ui", "start_screen.json")
    ss_bak = ss + ".bol-bak"
    if os.path.isfile(ss_bak):
        try:
            shutil.copy2(ss_bak, ss)
            print("[Restore] Restored vanilla start_screen.json.")
        except Exception as e:
            print(f"[Restore] Error restoring start_screen.json: {e}")
            
    # 4. Restore cryptbase.dll inside prefix
    if pfx_path:
        sys32 = os.path.join(pfx_path, "drive_c", "windows", "system32")
        crypt = os.path.join(sys32, "cryptbase.dll")
        crypt_orig = crypt + ".bol-orig"
        if os.path.isfile(crypt_orig):
            try:
                shutil.copy2(crypt_orig, crypt)
                print("[Restore] Restored prefix cryptbase.dll from backup.")
            except Exception as e:
                print(f"[Restore] Error restoring prefix cryptbase.dll: {e}")


def wine_disable_winegdk_preauth(proton_bin: str, pfx_path: str, env: dict):
    """Disable the built-in WineGDK XUser MSA authentication facet for ProxyPass mode."""
    import subprocess
    env_copy = env.copy()
    env_copy["WINEPREFIX"] = pfx_path

    def _regdelete(key, val):
        cmd = [proton_bin, "run", "reg", "delete", key, "/v", val, "/f"]
        try:
            subprocess.run(cmd, env=env_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            print(f"[Restore] Deleted registry key: {key} \\ {val}")
        except Exception as e:
            print(f"[Restore] Error deleting registry key {key} \\ {val}: {e}")

    # Delete ForceMsaFacet and RefreshToken so WineGDK falls back to network login (ProxyPass)
    for root in ("HKLM", "HKCU"):
        _regdelete(f"{root}\\Software\\Wine\\WineGDK", "ForceMsaFacet")
        _regdelete(f"{root}\\Software\\Wine\\WineGDK", "RefreshToken")
