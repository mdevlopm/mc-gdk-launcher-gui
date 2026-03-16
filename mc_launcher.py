#!/usr/bin/env python3
"""
Minecraft GDK Launcher  –  Weather-OS/GDK-Proton
GNOME/Adwaita tasarımı · ProxyPass · Destination ayarları
"""

import os, sys, json, glob, subprocess, threading, tarfile, traceback, re
import urllib.request

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "mc_launcher_config.json")
COMPAT_DATA = os.path.join(os.path.expanduser("~"), ".mc_gdk_prefix")
GDK_API     = "https://api.github.com/repos/Weather-OS/GDK-Proton/releases/latest"

# ── Config ───────────────────────────────────────────────────────────────────
def load_cfg():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {"exe_path": ""}

def save_cfg(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ── GDK-Proton ───────────────────────────────────────────────────────────────
def find_proton():
    hits = glob.glob(os.path.join(SCRIPT_DIR, "GDK-Proton*", "proton"))
    return sorted(hits)[-1] if hits else None

# ── ProxyPass yardımcıları ───────────────────────────────────────────────────
def find_proxypass(exe_path=""):
    if exe_path:
        parent = os.path.dirname(os.path.dirname(exe_path))
        for p in [os.path.join(parent, "ProxyPass.jar"),
                  os.path.join(os.path.dirname(exe_path), "ProxyPass.jar")]:
            if os.path.isfile(p):
                return p
    return None

def auth_json_exists(exe_path=""):
    if exe_path:
        parent = os.path.dirname(os.path.dirname(exe_path))
        return os.path.isfile(os.path.join(parent, "auth.json"))
    return False

def config_yml_path(exe_path=""):
    if exe_path:
        return os.path.join(os.path.dirname(os.path.dirname(exe_path)), "config.yml")
    return None

def read_destination(exe_path):
    """config.yml'den host ve port oku."""
    path = config_yml_path(exe_path)
    if not path or not os.path.isfile(path):
        return "", ""
    with open(path) as f:
        txt = f.read()
    host = re.search(r"destination:\s*\n\s*host:\s*(.+)", txt)
    port = re.search(r"destination:\s*\n\s*host:\s*.+\n\s*port:\s*(\d+)", txt)
    return (host.group(1).strip() if host else ""), (port.group(1).strip() if port else "")

def write_destination(exe_path, host, port):
    """config.yml'deki destination host/port'u güncelle."""
    path = config_yml_path(exe_path)
    if not path or not os.path.isfile(path):
        return False
    with open(path) as f:
        txt = f.read()
    txt = re.sub(
        r"(destination:\s*\n\s*host:\s*)(.+)",
        lambda m: m.group(1) + host,
        txt
    )
    txt = re.sub(
        r"(destination:\s*\n\s*host:\s*.+\n\s*port:\s*)(\d+)",
        lambda m: m.group(1) + port,
        txt
    )
    with open(path, "w") as f:
        f.write(txt)
    return True

# ════════════════════════════════════════════════════════════════════════════
# Yardımcı: Adwaita-benzeri grup kutusu
# ════════════════════════════════════════════════════════════════════════════
def make_group(title):
    """Başlıklı yuvarlak köşeli grup frame'i döndürür."""
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    lbl = Gtk.Label(label=title)
    lbl.add_css_class("group-title")
    lbl.set_halign(Gtk.Align.START)
    lbl.set_margin_bottom(6)
    outer.append(lbl)

    frame = Gtk.Frame()
    frame.add_css_class("group-frame")
    outer.append(frame)

    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    inner.add_css_class("group-inner")
    frame.set_child(inner)

    return outer, inner

def make_row(label_text, widget, last=False):
    """Solda etiket, sağda widget içeren tek satır."""
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.add_css_class("pref-row")
    if not last:
        row.add_css_class("pref-row-sep")

    lbl = Gtk.Label(label=label_text)
    lbl.add_css_class("row-label")
    lbl.set_halign(Gtk.Align.START)
    lbl.set_hexpand(True)
    row.append(lbl)
    row.append(widget)
    return row

# ════════════════════════════════════════════════════════════════════════════
# ProxyPass Canlı Log Penceresi (oyun çalışırken)
# ════════════════════════════════════════════════════════════════════════════
class ProxyLogWindow(Gtk.Window):
    """Oyunla birlikte çalışan ProxyPass'in canlı loglarını gösterir."""
    REFRESH_MS = 500   # kaç ms'de bir güncelle

    def __init__(self, proxy_proc, parent=None):
        super().__init__(title="ProxyPass — Canlı Log")
        self.set_default_size(580, 360)
        self.set_resizable(True)
        if parent:
            self.set_transient_for(parent)
        self._proc      = proxy_proc
        self._parent_win = parent
        self._last_len   = 0
        self._timer_id   = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)
        self.set_child(box)

        hdr = Gtk.Label(label="ProxyPass çıktısı (canlı)")
        hdr.add_css_class("group-title")
        hdr.set_halign(Gtk.Align.START)
        box.append(hdr)

        frame = Gtk.Frame()
        frame.add_css_class("group-frame")
        frame.set_vexpand(True)
        box.append(frame)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        frame.set_child(scroll)

        self.tv = Gtk.TextView()
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.add_css_class("term-view")
        self.buf = self.tv.get_buffer()
        scroll.set_child(self.tv)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        clear_btn = Gtk.Button(label="Temizle")
        clear_btn.connect("clicked", lambda _: self.buf.set_text(""))
        btn_row.append(clear_btn)

        close_btn = Gtk.Button(label="Kapat")
        close_btn.connect("clicked", lambda _: self.close())
        btn_row.append(close_btn)

        self.connect("close-request", self._on_close)

        # Mevcut log tamponunu hemen yaz, sonra periyodik güncelle
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
        """Periyodik olarak yeni log satırlarını ekle."""
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
        # Proc bittiyse dur
        if self._proc and self._proc.poll() is not None:
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _on_close(self, _):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        return False


# ════════════════════════════════════════════════════════════════════════════
# ProxyPass Terminal Penceresi
# ════════════════════════════════════════════════════════════════════════════
class ProxyTermWindow(Gtk.Window):
    def __init__(self, jar_path, cwd, on_done=None):
        super().__init__(title="ProxyPass — Microsoft Girişi")
        self.set_default_size(500, 280)
        self.set_resizable(True)
        self.jar_path = jar_path
        self.cwd      = cwd
        self.on_done  = on_done
        self.proc     = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)
        self.set_child(box)

        hdr = Gtk.Label(label="ProxyPass çıktısı")
        hdr.add_css_class("group-title")
        hdr.set_halign(Gtk.Align.START)
        box.append(hdr)

        frame = Gtk.Frame()
        frame.add_css_class("group-frame")
        frame.set_vexpand(True)
        box.append(frame)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        frame.set_child(scroll)

        self.tv = Gtk.TextView()
        self.tv.set_editable(False)
        self.tv.set_cursor_visible(False)
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.add_css_class("term-view")
        self.buf = self.tv.get_buffer()
        scroll.set_child(self.tv)

        close_btn = Gtk.Button(label="Kapat")
        close_btn.set_halign(Gtk.Align.END)
        close_btn.connect("clicked", lambda _: self._kill_and_close())
        box.append(close_btn)

        self.connect("close-request", self._on_close_req)
        threading.Thread(target=self._run, daemon=True).start()

    def _append(self, text):
        def _do():
            self.buf.insert(self.buf.get_end_iter(), text)
            self.tv.scroll_to_iter(self.buf.get_end_iter(), 0, False, 0, 0)
            return False
        GLib.idle_add(_do)

    def _run(self):
        try:
            self.proc = subprocess.Popen(
                ["java", "-jar", self.jar_path],
                cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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

# ════════════════════════════════════════════════════════════════════════════
# Destination Ayarları Penceresi
# ════════════════════════════════════════════════════════════════════════════
class DestinationDialog(Gtk.Window):
    def __init__(self, parent, exe_path, on_saved=None):
        super().__init__(title="Sunucu Ayarları")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(380, -1)
        self.set_resizable(False)
        self.exe_path = exe_path
        self.on_saved = on_saved

        host, port = read_destination(exe_path)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20); box.set_margin_bottom(20)
        box.set_margin_start(20); box.set_margin_end(20)
        self.set_child(box)

        grp_outer, grp_inner = make_group("Hedef Sunucu (config.yml)")
        box.append(grp_outer)

        self.host_entry = Gtk.Entry()
        self.host_entry.set_text(host)
        self.host_entry.set_size_request(200, -1)
        grp_inner.append(make_row("Sunucu Adresi", self.host_entry))

        self.port_entry = Gtk.Entry()
        self.port_entry.set_text(port)
        self.port_entry.set_size_request(80, -1)
        grp_inner.append(make_row("Port", self.port_entry, last=True))

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        cancel = Gtk.Button(label="İptal")
        cancel.connect("clicked", lambda _: self.close())
        btn_row.append(cancel)

        save = Gtk.Button(label="Kaydet")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._on_save)
        btn_row.append(save)

    def _on_save(self, _):
        host = self.host_entry.get_text().strip()
        port = self.port_entry.get_text().strip()
        if not host or not port:
            return
        ok = write_destination(self.exe_path, host, port)
        if self.on_saved:
            self.on_saved(host, port, ok)
        self.close()

# ════════════════════════════════════════════════════════════════════════════
# Ana Pencere
# ════════════════════════════════════════════════════════════════════════════
CSS = """
/* ── Genel ── */
window {
    background-color: @window_bg_color;
}

/* ── Grup başlığı ── */
.group-title {
    font-size: 11px;
    font-weight: bold;
    color: @headerbar_fg_color;
    opacity: 0.55;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Grup frame ── */
.group-frame {
    border-radius: 12px;
    border: 1px solid alpha(@window_fg_color, 0.08);
    background-color: @card_bg_color;
}

/* ── Satır ── */
.pref-row {
    padding: 10px 14px;
    min-height: 36px;
}
.pref-row-sep {
    border-bottom: 1px solid alpha(@window_fg_color, 0.07);
}
.row-label {
    font-size: 13px;
    color: @window_fg_color;
}
.row-value {
    font-size: 13px;
    color: alpha(@window_fg_color, 0.55);
}
.row-value.ok    { color: #26a269; }
.row-value.warn  { color: #cd9309; }
.row-value.error { color: #c01c28; }

/* ── Terminal ── */
.term-view,
.term-view text {
    font-family: monospace;
    font-size: 11px;
    background-color: #1e1e1e;
    color: #d4d4d4;
    border-radius: 8px;
    padding: 8px;
}

/* ── Büyük başlat butonu ── */
.launch-btn {
    font-size: 13px;
    font-weight: bold;
    padding: 12px 0px;
    border-radius: 8px;
}

/* ── Araçlar popover ── */
.tools-btn {
    padding: 4px 8px;
    min-height: 0;
    min-width: 0;
}
popover contents {
    padding: 6px;
}
.tool-row {
    padding: 4px 8px;
    border-radius: 6px;
    min-height: 32px;
}
.tool-row:hover {
    background-color: alpha(@window_fg_color, 0.08);
}
.tool-row-label {
    font-size: 13px;
}
.tool-sep {
    margin-top: 4px;
    margin-bottom: 4px;
}

/* ── Durum çubuğu ── */
.status-bar {
    font-size: 11px;
    color: alpha(@window_fg_color, 0.45);
}
.status-bar.running { color: #1c71d8; }
.status-bar.ok      { color: #26a269; }
.status-bar.error   { color: #c01c28; }

/* ── İç group padding ── */
.group-inner {
    border-radius: 12px;
}
"""

class LauncherWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Minecraft GDK Launcher")
        self.set_default_size(480, -1)
        self.set_resizable(False)
        self.cfg         = load_cfg()
        self._proxy_proc     = None
        self._game_proc      = None
        self._mangohud_on    = False
        self._proxy_log_buf  = []
        self._proxy_log_lock = threading.Lock()

        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # ── Headerbar ────────────────────────────────────────────────────────
        hb = Gtk.HeaderBar()
        hb.set_show_title_buttons(True)
        self.set_titlebar(hb)

        title_lbl = Gtk.Label(label="Minecraft GDK Launcher")
        title_lbl.add_css_class("title")
        hb.set_title_widget(title_lbl)

        # HeaderBar — tek Araçlar butonu + popover
        tools_btn = Gtk.MenuButton()
        tools_btn.set_icon_name("open-menu-symbolic")
        tools_btn.set_tooltip_text("Araçlar")
        tools_btn.add_css_class("flat")

        popover = Gtk.Popover()
        popover.set_has_arrow(False)
        tools_btn.set_popover(popover)

        pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        pop_box.set_margin_top(4); pop_box.set_margin_bottom(4)
        pop_box.set_margin_start(4); pop_box.set_margin_end(4)
        popover.set_child(pop_box)

        def _pop_row(icon, label, callback, tooltip=""):
            row_btn = Gtk.Button()
            row_btn.add_css_class("flat")
            row_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row_inner.add_css_class("tool-row")
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(16)
            row_inner.append(img)
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("tool-row-label")
            lbl.set_halign(Gtk.Align.START)
            row_inner.append(lbl)
            row_btn.set_child(row_inner)
            if tooltip:
                row_btn.set_tooltip_text(tooltip)
            def _cb(_btn):
                popover.popdown()
                callback(None)
            row_btn.connect("clicked", _cb)
            return row_btn

        pop_box.append(_pop_row(
            "folder-open-symbolic",
            "Wine Prefix Klasörünü Aç",
            self._on_open_prefix,
            "Ctrl+W"
        ))
        pop_box.append(_pop_row(
            "preferences-system-symbolic",
            "winecfg",
            self._on_winecfg
        ))
        pop_box.append(Gtk.Separator())
        pop_box.append(_pop_row(
            "emblem-important-symbolic",
            "Yükleme Donmasını Düzelt",
            self._on_fix_loading_freeze
        ))
        pop_box.append(_pop_row(
            "display-symbolic",
            "VSync Kapat",
            self._on_disable_vsync
        ))

        hb.pack_end(tools_btn)

        # ── Ana kutu ─────────────────────────────────────────────────────────
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_top(16); root.set_margin_bottom(16)
        root.set_margin_start(16); root.set_margin_end(16)
        self.set_child(root)

        # ── MangoHud switch satırı ──────────────────────────────────────────
        import shutil as _shutil
        mango_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mango_row.set_margin_bottom(4)
        root.append(mango_row)

        mango_icon = Gtk.Image.new_from_icon_name("utilities-system-monitor-symbolic")
        mango_icon.set_pixel_size(16)
        mango_row.append(mango_icon)

        mango_lbl = Gtk.Label(label="MangoHud FPS Sayacı")
        mango_lbl.add_css_class("row-label")
        mango_lbl.set_halign(Gtk.Align.START)
        mango_lbl.set_hexpand(True)
        mango_row.append(mango_lbl)

        self.mango_sub = Gtk.Label()
        self.mango_sub.add_css_class("row-value")
        mango_row.append(self.mango_sub)

        self.mangohud_btn = Gtk.Switch()
        self.mangohud_btn.set_valign(Gtk.Align.CENTER)
        self.mangohud_btn.connect("notify::active", self._on_mangohud_toggle)
        if not _shutil.which("mangohud"):
            self.mangohud_btn.set_sensitive(False)
            self.mango_sub.set_text("Kurulu değil")
            self.mango_sub.add_css_class("error")
        else:
            self.mango_sub.set_text("Kapalı")
        mango_row.append(self.mangohud_btn)

        # ── GDK-Proton grubu ─────────────────────────────────────────────────
        grp1, inner1 = make_group("GDK-Proton")
        root.append(grp1)

        self.proton_val = Gtk.Label()
        self.proton_val.add_css_class("row-value")
        self.proton_val.set_halign(Gtk.Align.END)
        inner1.append(make_row("Sürüm", self.proton_val))

        btn_box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box1.set_halign(Gtk.Align.END)

        self.dl_btn = Gtk.Button(label="İndir")
        self.dl_btn.add_css_class("suggested-action")
        self.dl_btn.connect("clicked", self._on_auto_download)
        btn_box1.append(self.dl_btn)

        self.manual_btn = Gtk.Button(label="Dosyadan Kur")
        self.manual_btn.connect("clicked", self._on_manual_install)
        btn_box1.append(self.manual_btn)

        inner1.append(make_row("Kurulum", btn_box1, last=True))
        self._refresh_proton_label()

        # ── Oyun dosyası grubu ───────────────────────────────────────────────
        grp2, inner2 = make_group("Oyun")
        root.append(grp2)

        exe_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.exe_entry = Gtk.Entry()
        self.exe_entry.set_text(self.cfg.get("exe_path", ""))
        self.exe_entry.set_hexpand(True)
        self.exe_entry.set_placeholder_text("Minecraft.Windows.exe yolu...")
        self.exe_entry.connect("changed", self._on_exe_changed)
        exe_box.append(self.exe_entry)
        browse_btn = Gtk.Button(label="Seç")
        browse_btn.connect("clicked", self._on_browse_exe)
        exe_box.append(browse_btn)
        inner2.append(make_row("Çalıştırılabilir", exe_box, last=True))

        # ── ProxyPass grubu ──────────────────────────────────────────────────
        grp3, inner3 = make_group("ProxyPass")
        root.append(grp3)

        self.auth_val = Gtk.Label()
        self.auth_val.add_css_class("row-value")
        self.auth_val.set_halign(Gtk.Align.END)
        inner3.append(make_row("Giriş Durumu", self.auth_val))

        self.dest_val = Gtk.Label()
        self.dest_val.add_css_class("row-value")
        self.dest_val.set_halign(Gtk.Align.END)
        inner3.append(make_row("Hedef Sunucu", self.dest_val))

        proxy_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        proxy_btn_box.set_halign(Gtk.Align.END)

        self.login_btn = Gtk.Button(label="Microsoft Girişi")
        self.login_btn.connect("clicked", self._on_proxy_login)
        proxy_btn_box.append(self.login_btn)

        self.logout_btn = Gtk.Button(label="Oturumu Kapat")
        self.logout_btn.add_css_class("destructive-action")
        self.logout_btn.connect("clicked", self._on_proxy_logout)
        proxy_btn_box.append(self.logout_btn)

        self.proxylog_btn = Gtk.Button(label="Logları Gör")
        self.proxylog_btn.connect("clicked", self._on_proxy_logs)
        proxy_btn_box.append(self.proxylog_btn)

        self.dest_btn = Gtk.Button(label="Sunucu Ayarla")
        self.dest_btn.connect("clicked", self._on_dest_settings)
        proxy_btn_box.append(self.dest_btn)

        inner3.append(make_row("İşlemler", proxy_btn_box, last=True))
        self._refresh_proxy_labels()

        # ── Başlat butonu ────────────────────────────────────────────────────
        self.launch_btn = Gtk.Button(label="Oyunu Başlat")
        self.launch_btn.add_css_class("suggested-action")
        self.launch_btn.add_css_class("launch-btn")
        self.launch_btn.set_hexpand(True)
        self.launch_btn.connect("clicked", self._on_launch_or_stop)
        root.append(self.launch_btn)

        # ── Durum çubuğu ─────────────────────────────────────────────────────
        self.status_lbl = Gtk.Label(label="Hazır.")
        self.status_lbl.add_css_class("status-bar")
        self.status_lbl.set_margin_bottom(4)
        root.append(self.status_lbl)

        self.connect("close-request", self._on_close)

        # Ctrl+W → prefix klasörü aç
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>w"),
            Gtk.CallbackAction.new(lambda *_: self._on_open_prefix(None) or True)
        )
        ctrl.add_shortcut(shortcut)

        shortcut_m = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>m"),
            Gtk.CallbackAction.new(lambda *_: self.mangohud_btn.set_active(
                not self.mangohud_btn.get_active()) or True
                if self.mangohud_btn.get_sensitive() else True)
        )
        ctrl.add_shortcut(shortcut_m)

        shortcut_f = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>f"),
            Gtk.CallbackAction.new(lambda *_: self._on_fix_loading_freeze(None) or True)
        )
        ctrl.add_shortcut(shortcut_f)
        self.add_controller(ctrl)

    # ── Yardımcılar ──────────────────────────────────────────────────────────
    def _set_status(self, msg, style=None):
        def _u():
            self.status_lbl.set_text(msg)
            for c in ["running", "ok", "error"]:
                self.status_lbl.remove_css_class(c)
            if style:
                self.status_lbl.add_css_class(style)
            return False
        GLib.idle_add(_u)

    def _refresh_proton_label(self):
        p = find_proton()
        if p:
            self.proton_val.set_text(os.path.basename(os.path.dirname(p)))
            self.proton_val.remove_css_class("error")
            self.proton_val.add_css_class("ok")
        else:
            self.proton_val.set_text("Kurulu değil")
            self.proton_val.remove_css_class("ok")
            self.proton_val.add_css_class("error")

    def _refresh_proxy_labels(self):
        exe = self.exe_entry.get_text().strip()
        jar = find_proxypass(exe)

        # auth durumu
        has_jar  = bool(jar)
        has_auth = auth_json_exists(exe)
        is_running = (self._proxy_proc is not None and self._proxy_proc.poll() is None)

        if not has_jar:
            self.auth_val.set_text("ProxyPass.jar bulunamadı")
            for c in ["ok","warn","error"]: self.auth_val.remove_css_class(c)
            self.auth_val.add_css_class("error")
            self.login_btn.set_visible(True)
            self.login_btn.set_sensitive(False)
            self.logout_btn.set_visible(False)
            self.proxylog_btn.set_sensitive(False)
        elif has_auth:
            self.auth_val.set_text("Giriş yapıldı ✓")
            for c in ["warn","error"]: self.auth_val.remove_css_class(c)
            self.auth_val.add_css_class("ok")
            self.login_btn.set_visible(False)
            self.logout_btn.set_visible(True)
            self.proxylog_btn.set_sensitive(is_running)
        else:
            self.auth_val.set_text("Giriş yapılmadı")
            for c in ["ok","error"]: self.auth_val.remove_css_class(c)
            self.auth_val.add_css_class("warn")
            self.login_btn.set_visible(True)
            self.login_btn.set_sensitive(True)
            self.logout_btn.set_visible(False)
            self.proxylog_btn.set_sensitive(False)

        # destination
        if exe:
            host, port = read_destination(exe)
            if host:
                self.dest_val.set_text(f"{host}:{port}")
                for c in ["warn","error"]: self.dest_val.remove_css_class(c)
                self.dest_val.add_css_class("ok")
                self.dest_btn.set_sensitive(True)
            else:
                self.dest_val.set_text("config.yml bulunamadı")
                for c in ["ok"]: self.dest_val.remove_css_class(c)
                self.dest_val.add_css_class("error")
                self.dest_btn.set_sensitive(False)
        else:
            self.dest_val.set_text("—")
            self.dest_btn.set_sensitive(False)

    def _on_exe_changed(self, _):
        self._refresh_proxy_labels()

    def _show_error(self, title, msg):
        def _s():
            d = Gtk.AlertDialog()
            d.set_message(title); d.set_detail(msg); d.show(self)
            return False
        GLib.idle_add(_s)

    def _set_install_btns(self, s):
        GLib.idle_add(lambda: self.dl_btn.set_sensitive(s) or False)
        GLib.idle_add(lambda: self.manual_btn.set_sensitive(s) or False)

    def _on_close(self, _):
        self._kill_proxy()
        return False

    def _on_mangohud_toggle(self, switch, _param=None):
        self._mangohud_on = switch.get_active()
        if self._mangohud_on:
            GLib.idle_add(lambda: self.mango_sub.set_text("Aktif") or
                          self.mango_sub.remove_css_class("error") or
                          self.mango_sub.add_css_class("ok") or False)
            self._set_status("MangoHud aktif — oyun FPS sayacıyla başlayacak.", "ok")
        else:
            GLib.idle_add(lambda: self.mango_sub.set_text("Kapalı") or
                          self.mango_sub.remove_css_class("ok") or False)
            self._set_status("MangoHud devre dışı.", None)

    def _on_open_prefix(self, _):
        """Wine prefix klasörünü dosya yöneticisinde aç."""
        path = COMPAT_DATA
        os.makedirs(path, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", path])
            self._set_status(f"Klasör açıldı: {path}", "ok")
        except Exception as e:
            self._show_error("Hata", f"Klasör açılamadı:\n{e}")

    def _options_txt_path(self):
        return os.path.join(
            COMPAT_DATA, "pfx", "drive_c", "users", "steamuser",
            "AppData", "Roaming", "Minecraft Bedrock",
            "Users", "Shared", "games", "com.mojang",
            "minecraftpe", "options.txt"
        )

    def _patch_options(self, key, value):
        """options.txt içinde key:value satırını yaz, yoksa ekle. True/hata mesajı döner."""
        path = self._options_txt_path()
        if not os.path.isfile(path):
            return None  # dosya yok
        with open(path) as f:
            lines = f.readlines()
        found = False
        new_lines = []
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

    def _on_disable_vsync(self, _):
        """gfx_vsync:0 — VSync'i kapat."""
        if not os.path.isfile(self._options_txt_path()):
            self._show_error(
                "options.txt bulunamadı",
                "Oyunu en az bir kez başlatıp kapattıktan sonra tekrar deneyin."
            )
            return
        try:
            self._patch_options("gfx_vsync", "0")
            self._set_status("VSync kapatıldı ✓", "ok")
        except Exception as e:
            self._set_status(f"Hata: {e}", "error")
            self._show_error("Yazma Hatası", str(e))

    def _on_fix_loading_freeze(self, _):
        """do_not_show_multiplayer_online_safety_warning:1 — yükleme donmasını düzelt."""
        if not os.path.isfile(self._options_txt_path()):
            self._show_error(
                "options.txt bulunamadı",
                "Oyunu en az bir kez başlatıp kapattıktan sonra tekrar deneyin."
            )
            return
        try:
            self._patch_options("do_not_show_multiplayer_online_safety_warning", "1")
            self._set_status("Yükleme donması düzeltildi ✓", "ok")
        except Exception as e:
            self._set_status(f"Hata: {e}", "error")
            self._show_error("Yazma Hatası", str(e))

    def _on_winecfg(self, _):
        """winecfg'yi GDK-Proton prefix'i üzerinden çalıştır."""
        proton = find_proton()
        if not proton:
            self._show_error("GDK-Proton yok", "Önce GDK-Proton'u indirin.")
            return
        os.makedirs(COMPAT_DATA, exist_ok=True)
        steam_root = os.path.expanduser("~/.steam/root")
        if not os.path.isdir(steam_root):
            steam_root = SCRIPT_DIR
        env = os.environ.copy()
        env.update({
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": steam_root,
            "STEAM_COMPAT_DATA_PATH"          : COMPAT_DATA,
        })
        def runner():
            try:
                self._set_status("winecfg açılıyor...", "running")
                proc = subprocess.Popen(
                    [proton, "run", "winecfg"],
                    env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                proc.wait()
                self._set_status("winecfg kapandı.", "ok")
            except Exception as e:
                self._set_status(f"winecfg hatası: {e}", "error")
        threading.Thread(target=runner, daemon=True).start()

    def _kill_proxy(self):
        if self._proxy_proc and self._proxy_proc.poll() is None:
            self._proxy_proc.terminate()
            self._proxy_proc = None

    # ── Destination ayarları ─────────────────────────────────────────────────
    def _on_dest_settings(self, _):
        exe = self.exe_entry.get_text().strip()
        def on_saved(host, port, ok):
            if ok:
                GLib.idle_add(self._refresh_proxy_labels)
                self._set_status(f"Sunucu güncellendi: {host}:{port}", "ok")
            else:
                self._set_status("config.yml yazılamadı.", "error")
        dlg = DestinationDialog(self, exe, on_saved=on_saved)
        dlg.present()

    # ── ProxyPass girişi ─────────────────────────────────────────────────────
    def _on_proxy_login(self, _):
        exe = self.exe_entry.get_text().strip()
        jar = find_proxypass(exe)
        if not jar:
            self._show_error("ProxyPass bulunamadı",
                             "Minecraft.exe seçili ve ProxyPass.jar aynı klasörde olmalı.")
            return
        def after_login():
            GLib.idle_add(self._refresh_proxy_labels)
        win = ProxyTermWindow(jar, os.path.dirname(jar), on_done=after_login)
        win.set_transient_for(self)
        win.present()

    # ── ProxyPass oturumu kapat ─────────────────────────────────────────────
    def _on_proxy_logout(self, _):
        exe = self.exe_entry.get_text().strip()
        if not exe:
            return
        auth_path = os.path.join(os.path.dirname(os.path.dirname(exe)), "auth.json")
        if not os.path.isfile(auth_path):
            self._set_status("auth.json zaten yok.", None)
            return

        def confirm_delete():
            dlg = Gtk.AlertDialog()
            dlg.set_message("Oturumu kapat")
            dlg.set_detail("auth.json silinecek ve mevcut ProxyPass bağlantısı kesilecek.\n\n" + auth_path)
            dlg.set_buttons(["İptal", "Sil"])
            dlg.set_default_button(0)
            dlg.set_cancel_button(0)
            dlg.choose(self, None, self._on_logout_confirm)
            return False
        GLib.idle_add(confirm_delete)

    def _on_logout_confirm(self, dlg, result):
        try:
            idx = dlg.choose_finish(result)
        except Exception:
            return
        if idx != 1:
            return
        exe = self.exe_entry.get_text().strip()
        auth_path = os.path.join(os.path.dirname(os.path.dirname(exe)), "auth.json")
        # Önce çalışan ProxyPass'i durdur
        self._kill_proxy()
        try:
            os.remove(auth_path)
            self._set_status("Oturum kapatıldı, auth.json silindi.", "ok")
        except Exception as e:
            self._set_status(f"Silinemedi: {e}", "error")
        GLib.idle_add(self._refresh_proxy_labels)

    # ── ProxyPass log penceresi ──────────────────────────────────────────────
    def _on_proxy_logs(self, _):
        if not self._proxy_proc or self._proxy_proc.poll() is not None:
            self._set_status("ProxyPass şu an çalışmıyor.", "error")
            GLib.idle_add(self._refresh_proxy_labels)
            return
        win = ProxyLogWindow(self._proxy_proc, parent=self)
        win.present()

    # ── GDK-Proton indir ─────────────────────────────────────────────────────
    def _do_extract(self, tar_path, remove_after=False):
        try:
            self._set_status("Arşiv açılıyor...", "running")
            with tarfile.open(tar_path, "r:gz") as t:
                members = t.getmembers()
                total   = len(members)
                for i, m in enumerate(members, 1):
                    try:
                        try:    t.extract(m, SCRIPT_DIR, filter="tar")
                        except TypeError: t.extract(m, SCRIPT_DIR)
                    except Exception as me:
                        print(f"[SKIP] {m.name}: {me}")
                    if i % 100 == 0 or i == total:
                        self._set_status(f"Açılıyor... {int(i*100/total)}%", "running")
            if remove_after and os.path.exists(tar_path):
                os.remove(tar_path)
            p = find_proton()
            if p:
                os.chmod(p, 0o755)
                GLib.idle_add(self._refresh_proton_label)
                self._set_status(f"GDK-Proton hazır: {os.path.basename(os.path.dirname(p))}", "ok")
            else:
                self._set_status("'proton' binary bulunamadı.", "error")
        except Exception as e:
            self._set_status(f"Hata: {e}", "error")
            self._show_error("Extract Hatası", str(e))
        finally:
            self._set_install_btns(True)

    def _on_auto_download(self, _):
        self._set_install_btns(False)
        def worker():
            try:
                self._set_status("GitHub sorgulanıyor...", "running")
                req = urllib.request.Request(GDK_API, headers={"User-Agent": "mc-gdk-launcher"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read())
                asset = next((a for a in data.get("assets", []) if a["name"].endswith(".tar.gz")), None)
                if not asset:
                    raise RuntimeError("tar.gz bulunamadı.")
                tar_path = os.path.join(SCRIPT_DIR, asset["name"])
                def hook(b, bs, total):
                    if total > 0:
                        self._set_status(f"İndiriliyor... {min(100,int(b*bs*100/total))}%", "running")
                self._set_status(f"İndiriliyor: {asset['name']}", "running")
                urllib.request.urlretrieve(asset["browser_download_url"], tar_path, reporthook=hook)
                self._do_extract(tar_path, remove_after=True)
            except Exception as e:
                self._set_status(f"İndirme hatası: {e}", "error")
                self._set_install_btns(True)
        threading.Thread(target=worker, daemon=True).start()

    def _on_manual_install(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title("GDK-Proton .tar.gz seç")
        dlg.open(self, None, self._on_manual_chosen)

    def _on_manual_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if path:
            self._set_install_btns(False)
            threading.Thread(target=self._do_extract, args=(path, False), daemon=True).start()

    # ── EXE seç ──────────────────────────────────────────────────────────────
    def _on_browse_exe(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title("Minecraft.Windows.exe seç")
        dlg.open(self, None, self._on_exe_chosen)

    def _on_exe_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if path:
            self.exe_entry.set_text(path)
            self.cfg["exe_path"] = path
            save_cfg(self.cfg)

    # ── Oyunu başlat / durdur ────────────────────────────────────────────────
    def _on_launch_or_stop(self, _):
        if self._game_proc and self._game_proc.poll() is None:
            # Oyun çalışıyor → durdur
            self._game_proc.terminate()
            self._set_status("Oyun durduruluyor...", "running")
        else:
            self._on_launch(None)

    def _on_launch(self, _):
        exe    = self.exe_entry.get_text().strip()
        proton = find_proton()

        if not exe or not os.path.isfile(exe):
            self._show_error("Hata", "Minecraft.Windows.exe seçilmedi veya bulunamadı.")
            return
        if not proton:
            self._show_error("GDK-Proton yok", "Önce GDK-Proton'u indirin.")
            return

        self.cfg["exe_path"] = exe
        save_cfg(self.cfg)
        os.makedirs(COMPAT_DATA, exist_ok=True)

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
            "SDL_MOUSEDRIVER"                 : "x11",
            "WINE_FULLSCREEN_INTEGER_SCALING" : "0",
            "PROTON_USE_WINED3D"              : "0",
            "SDL_VIDEO_X11_DGAMOUSE"          : "0",
        })

        # MangoHud etkinse env'e ekle
        if self._mangohud_on:
            env["MANGOHUD"]        = "1"
            env["MANGOHUD_CONFIG"] = "fps,frame_timing,gpu_stats,cpu_stats,vram,ram"

        self._set_status("Başlatılıyor...", "running")
        GLib.idle_add(lambda: (
            self.launch_btn.set_label("Oyunu Durdur") or
            self.launch_btn.remove_css_class("suggested-action") or
            self.launch_btn.add_css_class("destructive-action") or
            False
        ))

        jar = find_proxypass(exe)

        def runner():
            proxy_proc = None
            try:
                if jar:
                    print(f"[PROXY] Başlatılıyor: {jar}")
                    proxy_proc = subprocess.Popen(
                        ["java", "-jar", jar],
                        cwd=os.path.dirname(jar),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                    )
                    self._proxy_proc     = proxy_proc
                    self._proxy_log_buf  = []   # log satırları
                    self._proxy_log_lock = threading.Lock()

                    def _read_proxy_log(proc):
                        for raw in iter(proc.stdout.readline, b""):
                            line = raw.decode(errors="replace")
                            with self._proxy_log_lock:
                                self._proxy_log_buf.append(line)
                                if len(self._proxy_log_buf) > 2000:
                                    self._proxy_log_buf.pop(0)
                        proc.stdout.close()

                    threading.Thread(target=_read_proxy_log,
                                     args=(proxy_proc,), daemon=True).start()
                    import time; time.sleep(2)
                    # Loglar okunmaya başladıktan sonra butonu güncelle
                    GLib.idle_add(self._refresh_proxy_labels)

                if self._mangohud_on:
                    cmd = ["mangohud", "--dlsym", proton, "run", exe]
                else:
                    cmd = [proton, "run", exe]
                print(f"[LAUNCH] {' '.join(cmd)}")
                proc = subprocess.Popen(
                    cmd,
                    cwd=os.path.dirname(exe), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self._game_proc = proc
                self._set_status("Oyun çalışıyor...", "running")

                def rd(pipe, tag):
                    for raw in iter(pipe.readline, b""):
                        print(f"[{tag}] {raw.decode(errors='replace').rstrip()}")
                    pipe.close()

                t1 = threading.Thread(target=rd, args=(proc.stdout, "OUT"), daemon=True)
                t2 = threading.Thread(target=rd, args=(proc.stderr, "ERR"), daemon=True)
                t1.start(); t2.start()
                ret = proc.wait()
                t1.join(timeout=3); t2.join(timeout=3)

                self._set_status(f"Oyun kapandı  (exit: {ret})",
                                  "ok" if ret == 0 else "error")
            except Exception as e:
                print(f"[HATA]\n{traceback.format_exc()}")
                self._set_status(f"Hata: {e}", "error")
                self._show_error("Başlatma Hatası", str(e))
            finally:
                if proxy_proc and proxy_proc.poll() is None:
                    proxy_proc.terminate()
                self._proxy_proc = None
                self._game_proc  = None
                GLib.idle_add(lambda: (
                    self.launch_btn.set_label("Oyunu Başlat") or
                    self.launch_btn.remove_css_class("destructive-action") or
                    self.launch_btn.add_css_class("suggested-action") or
                    False
                ))
                GLib.idle_add(self._refresh_proxy_labels)

        threading.Thread(target=runner, daemon=True).start()


# ── Uygulama ─────────────────────────────────────────────────────────────────
class LauncherApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.mc.gdk.launcher")

    def do_activate(self):
        LauncherWindow(self).present()


if __name__ == "__main__":
    sys.exit(LauncherApp().run(sys.argv))
