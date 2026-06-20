"""
mc_launcher/ui/proxy_windows.py
  - ProxyTermWindow  : Microsoft girişi için ProxyPass terminal penceresi
  - ProxyLogWindow   : Oyun sırasında canlı log görüntüleyici
"""

import re
import subprocess
import threading
import json
import time
import urllib.request
import urllib.parse
import urllib.error

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Gio
from mc_launcher.i18n import _t
from mc_launcher.proxypass import auth_json_exists, auth_json_path


class ProxyTermWindow(Adw.Window):
    """
    ProxyPass JAR'ı çalıştırıp Microsoft giriş kodunu otomatik yakalar,
    ekranda büyükçe gösterir ve giriş tamamlandığında otomatik kapanır.
    """
    def __init__(self, jar_path: str, cwd: str, exe_path: str = "", parent=None, on_done=None, login_method="proxypass"):
        title_key = "title_direct_login" if login_method == "ingame" else "title_proxy_login"
        super().__init__(title=_t(title_key))
        self.set_default_size(580, 520)
        self.set_resizable(True)
        if parent:
            self.set_transient_for(parent)
            self.set_modal(True)

        self.jar_path = jar_path
        self.cwd      = cwd
        self.exe_path = exe_path
        self.on_done  = on_done
        self.login_method = login_method
        self.proc     = None
        self.target_url = "https://microsoft.com/link"
        self.auth_check_id = None
        self._current_code = ""
        self._stop_native = False

        # Content layout using ToolbarView
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        # HeaderBar inside window
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        # Custom title widget
        self.title_lbl = Gtk.Label(label=_t(title_key))
        self.title_lbl.add_css_class("title")
        header.set_title_widget(self.title_lbl)
        toolbar_view.add_top_bar(header)

        # Main Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        toolbar_view.set_content(main_box)

        # ── Elegant Prominent Code Display ──
        code_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        code_card.add_css_class("glass-card")
        code_card.set_halign(Gtk.Align.FILL)
        main_box.append(code_card)

        # Status & Instructions
        self.status_lbl = Gtk.Label(label=_t("status_waiting_code"))
        self.status_lbl.set_halign(Gtk.Align.CENTER)
        self.status_lbl.set_wrap(True)
        code_card.append(self.status_lbl)

        # Large code display
        self.code_val = Gtk.Label(label="— — — —")
        self.code_val.set_halign(Gtk.Align.CENTER)
        self.code_val.set_markup("<span size='32000' weight='bold' color='#3b82f6'>— — — —</span>")
        code_card.append(self.code_val)

        # Copy Code Button
        self.copy_code_btn = Gtk.Button(label="📋  " + _t("btn_copy_code"))
        self.copy_code_btn.add_css_class("pill")
        self.copy_code_btn.set_halign(Gtk.Align.CENTER)
        self.copy_code_btn.set_sensitive(False)
        self.copy_code_btn.connect("clicked", self._on_copy_code)
        code_card.append(self.copy_code_btn)

        # Expander for raw console logs
        expander = Gtk.Expander(label=_t("label_console_output"))
        expander.set_expanded(False)
        main_box.append(expander)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(160)
        expander.set_child(scroll)

        self.tv = Gtk.TextView()
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.add_css_class("monospace")
        self.buf = self.tv.get_buffer()
        scroll.set_child(self.tv)

        # Close button
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        main_box.append(btn_row)

        close_btn = Gtk.Button(label=_t("btn_close"))
        close_btn.connect("clicked", lambda _: self._kill_and_close())
        close_btn.add_css_class("pill")
        btn_row.append(close_btn)

        self.connect("close-request", self._on_close_req)

        # Start authentication process
        threading.Thread(target=self._run, daemon=True).start()

        # Check if auth.json is created periodically
        if self.exe_path:
            self.auth_check_id = GLib.timeout_add(1000, self._check_auth_completed)

    def _check_auth_completed(self):
        if not self.exe_path:
            return GLib.SOURCE_REMOVE
        
        import os
        if self.login_method == "ingame":
            if auth_json_exists(self.exe_path):
                print("[ProxyTerm] Native auth.json detected, closing login window!")
                self._kill_and_close()
                return GLib.SOURCE_REMOVE
        else:
            jar_auth = os.path.join(self.cwd, "auth.json")
            if os.path.isfile(jar_auth):
                print("[ProxyTerm] ProxyPass auth.json detected, copying to game directory and closing!")
                try:
                    import shutil
                    dest_auth = auth_json_path(self.exe_path)
                    os.makedirs(os.path.dirname(dest_auth), exist_ok=True)
                    shutil.copy2(jar_auth, dest_auth)
                except Exception as e:
                    print(f"[ProxyTerm] Error copying auth.json to game folder: {e}")
                self._kill_and_close()
                return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _on_copy_code(self, _):
        if not self._current_code:
            return
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self._current_code)
        self.copy_code_btn.set_label("✓  " + _t("status_copied"))
        GLib.timeout_add(2000, lambda: self.copy_code_btn.set_label("📋  " + _t("btn_copy_code")) or False)

    def _append(self, text: str):
        def _do():
            self.buf.insert(self.buf.get_end_iter(), text)
            self.tv.scroll_to_iter(self.buf.get_end_iter(), 0, False, 0, 0)
            
            # Detect URL and authentication Code
            # ProxyPass typically outputs:
            # "To sign in, use a web browser to open the page https://microsoft.com/link and enter the code XXXXXXXX"
            url_match = re.search(r"(https?://microsoft\.com/link)", text)
            code_match = re.search(r"\b([A-Z0-9]{8})\b", text)
            
            if code_match:
                code = code_match.group(1)
                self._current_code = code
                self.code_val.set_markup(f"<span size='32000' weight='bold' color='#10b981'>{code}</span>")
                self.status_lbl.set_text(_t("label_code_ready"))
                self.copy_code_btn.set_sensitive(True)
                if url_match:
                    self.target_url = url_match.group(1)
            return False
        GLib.idle_add(_do)

    def _run(self):
        if self.login_method == "ingame":
            self._run_native_flow()
            return

        try:
            from mc_launcher.java_rt import ensure_java

            def _status(msg, _style=None):
                print(f"[ProxyTerm] {msg}")

            java_bin = ensure_java(_status)
            cmd = [
                java_bin or "java",
                "-Djava.net.preferIPv4Stack=true",
                "-XX:+IgnoreUnrecognizedVMOptions",
                "--add-opens", "java.base/jdk.internal.misc=ALL-UNNAMED",
                "--add-opens", "java.base/java.nio=ALL-UNNAMED",
                "--add-opens", "java.base/java.lang=ALL-UNNAMED",
                "--add-opens", "java.base/java.lang.reflect=ALL-UNNAMED",
                "-Dio.netty.tryReflectionSetAccessible=true",
                "-jar", self.jar_path
            ]

            self.proc = subprocess.Popen(
                cmd,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            for raw in iter(self.proc.stdout.readline, b""):
                self._append(raw.decode(errors="replace"))
            self.proc.stdout.close()
            ret = self.proc.wait()
            self._append(f"\n[Süreç bitti, kod: {ret}]\n")
            GLib.idle_add(self._on_finish)
        except Exception as e:
            self._append(f"\n[HATA] {e}\n")

    def _run_native_flow(self):
        def http_post(url, params):
            import gzip
            data = urllib.parse.urlencode(params).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "mc-gdk-launcher",
                "Accept-Encoding": "gzip, deflate"
            })
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content_encoding = resp.headers.get("Content-Encoding", "")
                    body_bytes = resp.read()
                    if "gzip" in content_encoding:
                        body_bytes = gzip.decompress(body_bytes)
                    elif "deflate" in content_encoding:
                        import zlib
                        body_bytes = zlib.decompress(body_bytes, -zlib.MAX_WBITS)
                    return json.loads(body_bytes.decode("utf-8"))
            except urllib.error.HTTPError as e:
                try:
                    content_encoding = e.headers.get("Content-Encoding", "")
                    body_bytes = e.read()
                    if "gzip" in content_encoding:
                        body_bytes = gzip.decompress(body_bytes)
                    elif "deflate" in content_encoding:
                        import zlib
                        body_bytes = zlib.decompress(body_bytes, -zlib.MAX_WBITS)
                    body_str = body_bytes.decode("utf-8")
                    if body_str.strip():
                        return json.loads(body_str)
                    else:
                        return {"error": f"HTTP Error {e.code}: {e.reason} (Empty body)"}
                except Exception as ex:
                    return {"error": f"HTTP Error {e.code}: {e.reason} (Decode failed: {ex})"}
            except Exception as e:
                return {"error": str(e)}

        self._append("[NATIVE] Microsoft device-code akışı başlatılıyor...\n")
        
        # 1. Request device code
        client_id = "0000000048183522"
        scope = "service::user.auth.xboxlive.com::MBI_SSL"
        
        res = http_post("https://login.live.com/oauth20_connect.srf", {
            "client_id": client_id,
            "scope": scope,
            "response_type": "device_code"
        })
        
        if "device_code" not in res:
            err_msg = res.get("error_description") or res.get("error") or "Bilinmeyen hata"
            self._append(f"[HATA] Cihaz kodu alınamadı: {err_msg}\n")
            return
            
        device_code = res["device_code"]
        user_code = res["user_code"]
        verification_uri = res.get("verification_uri", "https://microsoft.com/link")
        
        self._current_code = user_code
        self.target_url = verification_uri
        
        # Update UI with the code
        def update_ui():
            self.code_val.set_markup(f"<span size='32000' weight='bold' color='#10b981'>{user_code}</span>")
            self.status_lbl.set_text(_t("label_code_ready"))
            self.copy_code_btn.set_sensitive(True)
        GLib.idle_add(update_ui)
        
        self._append(f"[NATIVE] Lütfen tarayıcınızdan {verification_uri} adresine gidin ve şu kodu yazın: {user_code}\n")
        
        # Open verification URI in default browser
        def open_browser():
            try:
                import webbrowser
                opened = webbrowser.open(verification_uri)
                if not opened:
                    Gio.AppInfo.launch_default_for_uri(verification_uri, None)
            except Exception as e:
                print(f"[NATIVE] Tarayıcı açma hatası: {e}")
                try:
                    Gio.AppInfo.launch_default_for_uri(verification_uri, None)
                except Exception as e2:
                    print(f"[NATIVE] Gio.AppInfo launch failed: {e2}")
        GLib.idle_add(open_browser)
        
        interval = max(int(res.get("interval", 5) or 5), 1)
        expires_in = int(res.get("expires_in", 900) or 900)
        deadline = time.time() + expires_in
        
        # 2. Poll for token
        while time.time() < deadline and not self._stop_native:
            time.sleep(interval)
            
            token_res = http_post("https://login.live.com/oauth20_token.srf", {
                "client_id": client_id,
                "grant_type": "device_code",
                "device_code": device_code
            })
            
            err = token_res.get("error")
            if err == "authorization_pending":
                continue
            elif err == "slow_down":
                interval += 5
                continue
            elif err:
                self._append(f"[HATA] Kimlik doğrulama başarısız: {err}\n")
                break
                
            if "refresh_token" in token_res:
                refresh_token = token_res["refresh_token"]
                access_token = token_res.get("access_token", "")
                self._append("[NATIVE] Kimlik başarıyla doğrulandı! Refresh token alındı.\n")
                self._append("[NATIVE] Token Wine kayıt defterine yazılıyor...\n")
                
                # Write to registry!
                ok = self._write_token_to_registry(refresh_token)
                if ok:
                    self._append("[NATIVE] Başarıyla Wine kayıt defterine yazıldı!\n")
                    self._append("[NATIVE] Xbox Live profili çekiliyor...\n")
                    try:
                        from mc_launcher.config import DATA_DIR
                        from mc_launcher.preauth import run_xbl_preauth
                        run_xbl_preauth(access_token, DATA_DIR)
                    except Exception as e:
                        print(f"[NATIVE] Preauth error on login: {e}")
                    
                    self._save_native_token_indicator(refresh_token)
                else:
                    self._append("[HATA] Kayıt defterine yazma başarısız oldu.\n")
                
                GLib.idle_add(self._on_finish)
                return
                
        self._append("[NATIVE] Oturum açma süresi doldu veya iptal edildi.\n")

    def _write_token_to_registry(self, token: str) -> bool:
        from mc_launcher.proton import find_proton
        from mc_launcher.game import build_env
        from mc_launcher.config import COMPAT_DATA, DATA_DIR
        from mc_launcher.preauth import wine_reg_set_refresh_token, wine_apply_winegdk_prereqs
        import os
        
        # Save host-side refresh token file
        msa_dir = os.path.join(DATA_DIR, "msa")
        os.makedirs(msa_dir, exist_ok=True)
        token_file = os.path.join(msa_dir, "token.json")
        try:
            with open(token_file, "w") as f:
                json.dump({"refresh_token": token, "obtained": int(time.time())}, f, indent=2)
            print(f"[NATIVE] Token saved to host file: {token_file}")
        except Exception as e:
            print(f"[NATIVE] Error saving token to host file: {e}")

        proton_bin = find_proton("ingame")
        if not proton_bin:
            proton_bin = find_proton("proxypass")
        if not proton_bin:
            print("[NATIVE] GDK-Proton bulunamadı, kayıt defterine yazılamıyor.")
            return False
            
        env = build_env()
        pfx = os.path.join(COMPAT_DATA, "pfx")
        os.makedirs(pfx, exist_ok=True)
        
        # Apply prereqs + write refresh token to registry
        wine_apply_winegdk_prereqs(proton_bin, pfx, env)
        wine_reg_set_refresh_token(proton_bin, pfx, env, token)
        return True

    def _save_native_token_indicator(self, token: str):
        import json
        import os
        from mc_launcher.config import DATA_DIR
        try:
            gamertag = "Direct Sign-in"
            dev_path = os.path.join(DATA_DIR, "winegdk-preauth", "device.json")
            if os.path.isfile(dev_path):
                with open(dev_path) as f:
                    dev_data = json.load(f)
                gamertag = dev_data.get("xbl_gamertag") or "Direct Sign-in"

            indicator_path = auth_json_path(self.exe_path)
            os.makedirs(os.path.dirname(indicator_path), exist_ok=True)
            with open(indicator_path, "w", encoding="utf-8") as f:
                json.dump({"gamertag": gamertag}, f)
            print(f"[NATIVE] Saved native auth indicator with gamertag: {gamertag}")
        except Exception as e:
            print(f"[NATIVE] Indicator yazma hatası: {e}")

    def _on_finish(self):
        if self.on_done:
            self.on_done()
        self.close()
        return False

    def _kill_and_close(self):
        self._stop_native = True
        if self.auth_check_id:
            GLib.source_remove(self.auth_check_id)
            self.auth_check_id = None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.close()

    def _on_close_req(self, _):
        self._stop_native = True
        if self.auth_check_id:
            GLib.source_remove(self.auth_check_id)
            self.auth_check_id = None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        if self.on_done:
            self.on_done()
        return False


# ──────────────────────────────────────────────────────────────────────────────
class ProxyLogWindow(Adw.Window):
    """
    Oyun çalışırken ProxyPass çıktısını canlı gösterir.
    """
    REFRESH_MS = 500

    def __init__(self, proxy_proc, parent=None):
        super().__init__(title=_t("title_proxy_log"))
        self.set_default_size(580, 380)
        self.set_resizable(True)
        if parent:
            self.set_transient_for(parent)

        self._proc       = proxy_proc
        self._parent_win = parent
        self._last_len   = 0
        self._timer_id   = None

        # Content layout using ToolbarView
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        toolbar_view.add_top_bar(header)

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        toolbar_view.set_content(main_box)

        lbl = Gtk.Label(label=_t("label_proxy_live"))
        lbl.add_css_class("heading")
        lbl.set_halign(Gtk.Align.START)
        main_box.append(lbl)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        main_box.append(scroll)

        self.tv = Gtk.TextView()
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.add_css_class("monospace")
        self.buf = self.tv.get_buffer()
        scroll.set_child(self.tv)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        main_box.append(btn_row)

        clear_btn = Gtk.Button(label=_t("btn_clear"))
        clear_btn.connect("clicked", lambda _: self.buf.set_text(""))
        clear_btn.add_css_class("pill")
        btn_row.append(clear_btn)

        close_btn = Gtk.Button(label=_t("btn_close"))
        close_btn.connect("clicked", lambda _: self.close())
        close_btn.add_css_class("pill")
        btn_row.append(close_btn)

        self.connect("close-request", self._on_close)
        self._flush_buf()
        self._timer_id = GLib.timeout_add(self.REFRESH_MS, self._tick)

    def _flush_buf(self):
        if not self._parent_win:
            return
        with self._parent_win._proxy_log_lock:
            lines = list(self._parent_win._proxy_log_buf)
        if lines:
            self.buf.set_text("".join(lines))
            self._last_len = len(lines)
            self.tv.scroll_to_iter(self.buf.get_end_iter(), 0, False, 0, 0)

    def _tick(self):
        if not self._parent_win:
            return GLib.SOURCE_REMOVE
        with self._parent_win._proxy_log_lock:
            buf = self._parent_win._proxy_log_buf
            new_lines = buf[self._last_len:]
            self._last_len = len(buf)
        if new_lines:
            end = self.buf.get_end_iter()
            self.buf.insert(end, "".join(new_lines))
            self.tv.scroll_to_iter(self.buf.get_end_iter(), 0, False, 0, 0)
        if self._proc and self._proc.poll() is not None:
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _on_close(self, _):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        return False
