"""
mc_launcher/ui/proxy_windows.py
  - ProxyTermWindow  : Microsoft girişi için ProxyPass terminal penceresi
  - ProxyLogWindow   : Oyun sırasında canlı log görüntüleyici
"""

import os
import subprocess
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from mc_launcher.i18n import _t


# ──────────────────────────────────────────────────────────────────────────────
class ProxyTermWindow(Adw.Window):
    """
    ProxyPass JAR'ı çalıştırıp çıktısını terminal görünümünde gösterir.
    Microsoft hesabına giriş için kullanılır.
    """
    def __init__(self, jar_path: str, cwd: str, parent=None, on_done=None):
        super().__init__(title=_t("title_proxy_login"))
        self.set_default_size(540, 320)
        self.set_resizable(True)
        if parent:
            self.set_transient_for(parent)
            self.set_modal(True)

        self.jar_path = jar_path
        self.cwd      = cwd
        self.on_done  = on_done
        self.proc     = None

        # ── İçerik ──
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(16); box.set_margin_end(16)
        toolbar_view.set_content(box)

        lbl = Gtk.Label(label=_t("label_proxy_output"))
        lbl.add_css_class("heading")
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.append(scroll)

        self.tv = Gtk.TextView()
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.add_css_class("monospace")
        self.buf = self.tv.get_buffer()
        scroll.set_child(self.tv)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        close_btn = Gtk.Button(label=_t("btn_close"))
        close_btn.connect("clicked", lambda _: self._kill_and_close())
        btn_row.append(close_btn)

        self.connect("close-request", self._on_close_req)
        threading.Thread(target=self._run, daemon=True).start()

    # ── İç ──

    def _append(self, text: str):
        def _do():
            self.buf.insert(self.buf.get_end_iter(), text)
            self.tv.scroll_to_iter(self.buf.get_end_iter(), 0, False, 0, 0)
            return False
        GLib.idle_add(_do)

    def _run(self):
        try:
            # Oyunla aynı gömülü Java runtime'ını kullan.
            from mc_launcher.java_rt import ensure_java

            # Basit status bildirimi: pencere başlığını kullanamayız, bu yüzden
            # stdout'a log basmakla yetiniyoruz.
            def _status(msg, _style=None):
                print(f"[ProxyTerm] {msg}")

            java_bin = ensure_java(_status)
            cmd = [java_bin or "java", "-jar", self.jar_path]

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

    def _on_finish(self):
        if self.on_done:
            self.on_done()
        self.close()
        return False

    def _kill_and_close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.close()

    def _on_close_req(self, _):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        return False


# ──────────────────────────────────────────────────────────────────────────────
class ProxyLogWindow(Adw.Window):
    """
    Oyun çalışırken ProxyPass çıktısını canlı gösterir.
    Ebeveyn penceredeki _proxy_log_buf / _proxy_log_lock'u kullanır.
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

        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(16); box.set_margin_end(16)
        toolbar_view.set_content(box)

        lbl = Gtk.Label(label=_t("label_proxy_live"))
        lbl.add_css_class("heading")
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.append(scroll)

        self.tv = Gtk.TextView()
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.add_css_class("monospace")
        self.buf = self.tv.get_buffer()
        scroll.set_child(self.tv)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        clear_btn = Gtk.Button(label=_t("btn_clear"))
        clear_btn.connect("clicked", lambda _: self.buf.set_text(""))
        btn_row.append(clear_btn)

        close_btn = Gtk.Button(label=_t("btn_close"))
        close_btn.connect("clicked", lambda _: self.close())
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
