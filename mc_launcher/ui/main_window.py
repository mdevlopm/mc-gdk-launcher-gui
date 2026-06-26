"""
mc_launcher/ui/main_window.py — Simplified premium dark launcher with onboarding wizard
"""

import os
import threading
import subprocess
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, Pango

from mc_launcher.i18n import _t, init_i18n, set_current_lang, get_current_lang
from mc_launcher.config import COMPAT_DATA, load_cfg, save_cfg
from mc_launcher.backgrounds import list_background_ids, resolve_background
from mc_launcher.proton import find_proton, download_proton, install_from_file, install_from_folder
from mc_launcher.proxypass import find_proxypass, auth_json_exists, auth_json_path, read_destination, ensure_proxypass, read_proxypass_config, write_proxypass_config
from mc_launcher.game import launch_game, scan_for_exe, options_txt_path, patch_options, stop_game
from mc_launcher.java_rt import find_java, ensure_java
from mc_launcher.ui.proxy_windows import ProxyTermWindow
from mc_launcher.ui.dialogs import DestinationDialog
from mc_launcher.store import download_and_install_content, list_installed_content, delete_installed_content

# CSS Styling to wow the user (Lunar Client inspired, glassmorphism dark theme)
CSS_DATA = """
window {
    background-color: var(--window-bg);
    color: #e2e8f0;
    font-family: Cantarell, "Segoe UI", system-ui, sans-serif;
    font-size: 14px;
}

.sidebar-box {
    background-color: var(--sidebar-bg);
    border-right: 1px solid var(--border-color);
    padding: 16px 8px;
}

.sidebar-btn {
    border-radius: 10px;
    padding: 10px;
    margin-bottom: 6px;
    color: #94a3b8;
    background: transparent;
    border: none;
    transition: background-color 0.25s ease, color 0.25s ease, transform 0.2s ease, box-shadow 0.25s ease;
}

.sidebar-btn:hover {
    background-color: var(--border-color);
    color: #f1f5f9;
    transform: translateX(3px);
}

.sidebar-btn.active {
    background-color: var(--sidebar-active-bg);
    color: #ffffff;
    box-shadow: 0 4px 16px var(--sidebar-active-shadow);
    transform: translateX(4px);
}

.sidebar-logo {
    margin-bottom: 24px;
}

.play-panel {
    border-radius: 0;
    padding: 0;
}

.play-content-box {
    background: linear-gradient(to top, rgba(8,10,20,0.92) 30%, rgba(8,10,20,0.55) 70%, rgba(8,10,20,0.3) 100%);
    border-radius: 0;
    padding: 32px;
    transition: opacity 0.35s ease, transform 0.35s ease;
}

.play-bg {
    transition: opacity 0.4s ease;
    opacity: 1;
}

.play-bg-fade {
    opacity: 0.25;
}

.page-content {
    animation: page-enter 0.45s cubic-bezier(0.22, 1, 0.36, 1) backwards;
}

@keyframes page-enter {
    from {
        opacity: 0;
        transform: translateY(16px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes soft-pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.4); }
    50% { box-shadow: 0 0 32px rgba(52, 211, 153, 0.55); }
}

.sidebar-collapsed {
    min-width: 0;
}

.sidebar-toggle-btn {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
    color: #64748b;
    margin-top: 4px;
    margin-bottom: 4px;
    transition: all 0.2s ease;
}

.sidebar-toggle-btn:hover {
    background-color: var(--border-color);
    color: #f1f5f9;
}

.custom-headerbar {
    background-color: var(--headerbar-bg);
    border-bottom: 1px solid var(--border-color);
    padding: 6px 12px;
    min-height: 40px;
}

.headerbar-title {
    font-size: 11px;
    font-weight: 700;
    color: #475569;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

.wm-controls {
    padding: 0;
    margin: 0;
}

.wm-btn {
    border: none;
    border-radius: 0;
    min-width: 46px;
    min-height: 36px;
    padding: 0;
    background: transparent;
    color: #cbd5e1;
    transition: background-color 0.15s ease, color 0.15s ease;
}

.wm-btn image {
    opacity: 1;
    -gtk-icon-size: 16px;
    color: inherit;
}

.wm-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #f8fafc;
}

.wm-btn-close:hover {
    background-color: #dc2626;
    color: #ffffff;
}

.game-title {
    font-size: 36px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 2px;
}

.game-subtitle {
    font-size: 14px;
    color: var(--primary-color);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.play-btn-glowing {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: #ffffff;
    font-size: 17px;
    font-weight: bold;
    border-radius: 12px;
    padding: 14px 48px;
    border: none;
    box-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
    transition: transform 0.2s ease, box-shadow 0.25s ease, background 0.25s ease;
    animation: soft-pulse 3s ease-in-out infinite;
}

.play-btn-glowing:hover {
    background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
    box-shadow: 0 0 30px rgba(52, 211, 153, 0.6);
}

.play-btn-glowing:active {
    transform: scale(0.98);
}

.stop-btn-glowing {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: #ffffff;
    font-size: 17px;
    font-weight: bold;
    border-radius: 12px;
    padding: 14px 48px;
    border: none;
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
    transition: all 0.2s ease-in-out;
}

.stop-btn-glowing:hover {
    background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
    box-shadow: 0 0 30px rgba(248, 113, 113, 0.6);
}

.glass-card {
    background-color: var(--glass-card-bg);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 16px;
    transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}

.glass-card:hover {
    transform: translateY(-2px);
    border-color: var(--primary-color);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
}

button.pill {
    transition: transform 0.18s ease, opacity 0.18s ease;
}

button.pill:hover {
    transform: translateY(-1px);
}

button.pill:active {
    transform: scale(0.97);
}

.glass-card-title {
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
}

.page-title {
    font-size: 22px;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 4px;
}

.settings-row {
    padding: 6px 0;
}

.component-row {
    padding: 4px 0;
}

.component-name {
    min-width: 140px;
    color: #94a3b8;
    font-size: 13px;
}

.wizard-box {
    background-color: var(--sidebar-bg);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    padding: 40px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
    animation: page-enter 0.5s cubic-bezier(0.22, 1, 0.36, 1) backwards;
}

.wizard-title {
    font-size: 26px;
    font-weight: bold;
    color: #ffffff;
}

.wizard-desc {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.6;
}

.wizard-step-label {
    font-size: 11px;
    font-weight: bold;
    color: var(--primary-color);
    text-transform: uppercase;
    letter-spacing: 2px;
}

.status-label-ok {
    color: #10b981;
    font-weight: bold;
}

.status-label-warn {
    color: #f59e0b;
    font-weight: bold;
}

.status-label-error {
    color: #ef4444;
    font-weight: bold;
}

.store-card {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.25s ease;
}

.store-card:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: var(--primary-color);
    transform: translateY(-2px);
}

.store-card-title {
    font-weight: bold;
    font-size: 16px;
    color: #ffffff;
    margin-top: 8px;
}

.store-card-desc {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
    line-height: 1.4;
}

.badge {
    border-radius: 12px;
    padding: 2px 8px;
    margin-left: 8px;
}

.badge-text {
    font-size: 10px;
    font-weight: bold;
}

.badge-world {
    background-color: rgba(16, 185, 129, 0.15);
    color: #10b981;
}

.badge-resource {
    background-color: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
}

.badge-behavior {
    background-color: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
}

dropdown {
    background-color: var(--glass-card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: #e2e8f0;
}

dropdown:hover {
    border-color: var(--primary-color);
}

dropdown button {
    background: transparent;
    border: none;
    box-shadow: none;
    color: inherit;
    padding: 6px 12px;
}

dropdown popover {
    background-color: var(--sidebar-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

dropdown popover listview {
    background-color: transparent;
}

dropdown popover listitem {
    padding: 8px 12px;
    color: #cbd5e1;
}

dropdown popover listitem:hover {
    background-color: var(--border-color);
    color: #ffffff;
}

dropdown popover listitem:selected {
    background-color: var(--sidebar-active-bg);
    color: #ffffff;
}
"""


class LauncherWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Minecraft GDK Linux Launcher")
        self.set_default_size(1024, 720)
        self.set_resizable(True)
        self.set_decorated(False)
        self.maximize()

        init_i18n()
        self.cfg = load_cfg()
        self._language = get_current_lang()
        self._proxy_proc = None
        self._game_proc = None
        self._game_procs = {}
        self._game_stopping = False
        self._launch_proton = None
        self._mangohud_on = False
        self._bg_ids = list_background_ids()
        self._login_methods = ["proxypass", "ingame"]
        self._proxy_log_buf = []
        self._proxy_log_lock = threading.Lock()
        self._ui_initialized = False
        self._updating_lang_dropdown = False
        self._updating_bg_dropdown = False
        self._updating_login_dropdowns = False

        # Load Custom CSS Style Provider
        self._load_css()

        # Setup Toast Overlay
        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        # Main Window Stack (Wizard or Launcher View)
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.main_stack.set_transition_duration(300)
        self._toast_overlay.set_child(self.main_stack)

        # Build UI Screens
        self._build_wizard_ui()
        self._build_launcher_ui()

        # Initialize and show correct screen
        self._apply_language()
        self._ui_initialized = True
        self._refresh_all_states()

        # If setup is not completed, run Wizard; otherwise, run Launcher
        if not self.cfg.get("setup_completed", False):
            self.main_stack.set_visible_child_name("wizard")
        else:
            self.main_stack.set_visible_child_name("launcher")

        self.connect("close-request", self._on_close)
        self.connect("destroy", self._on_destroy)

        # Keep maximize button icon in sync with window state
        self.connect("notify::maximized", lambda *_: self._update_wm_max_icon())

    def _load_css(self):
        self._css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        bg = self.cfg.get("play_background", "default")
        self._apply_theme(bg)

    def _apply_theme(self, bg_id):
        themes = {
            "default": {
                "window-bg": "#0c0d12",
                "sidebar-bg": "#0f1118",
                "sidebar-active-bg": "#2563eb",
                "sidebar-active-shadow": "rgba(37, 99, 235, 0.35)",
                "glass-card-bg": "rgba(22, 28, 45, 0.6)",
                "headerbar-bg": "#080a10",
                "primary-color": "#3b82f6",
                "border-color": "#1e2230",
            },
            "forest": {
                "window-bg": "#061f12",
                "sidebar-bg": "#082918",
                "sidebar-active-bg": "#10b981",
                "sidebar-active-shadow": "rgba(16, 185, 129, 0.35)",
                "glass-card-bg": "rgba(16, 45, 28, 0.6)",
                "headerbar-bg": "#04170d",
                "primary-color": "#10b981",
                "border-color": "#14462a",
            },
            "nether": {
                "window-bg": "#1c0808",
                "sidebar-bg": "#240a0a",
                "sidebar-active-bg": "#ef4444",
                "sidebar-active-shadow": "rgba(239, 68, 68, 0.35)",
                "glass-card-bg": "rgba(45, 16, 16, 0.6)",
                "headerbar-bg": "#130404",
                "primary-color": "#f87171",
                "border-color": "#451010",
            },
            "ocean": {
                "window-bg": "#031e24",
                "sidebar-bg": "#042930",
                "sidebar-active-bg": "#06b6d4",
                "sidebar-active-shadow": "rgba(6, 182, 212, 0.35)",
                "glass-card-bg": "rgba(12, 45, 52, 0.6)",
                "headerbar-bg": "#021418",
                "primary-color": "#22d3ee",
                "border-color": "#0c4a54",
            },
            "end": {
                "window-bg": "#170524",
                "sidebar-bg": "#1f0830",
                "sidebar-active-bg": "#a855f7",
                "sidebar-active-shadow": "rgba(168, 85, 247, 0.35)",
                "glass-card-bg": "rgba(36, 12, 52, 0.6)",
                "headerbar-bg": "#100318",
                "primary-color": "#c084fc",
                "border-color": "#440d54",
            },
            "mountains": {
                "window-bg": "#0f172a",
                "sidebar-bg": "#1e293b",
                "sidebar-active-bg": "#6366f1",
                "sidebar-active-shadow": "rgba(99, 102, 241, 0.35)",
                "glass-card-bg": "rgba(30, 41, 59, 0.6)",
                "headerbar-bg": "#020617",
                "primary-color": "#818cf8",
                "border-color": "#334155",
            },
            "custom": {
                "window-bg": "#0c0d12",
                "sidebar-bg": "#0f1118",
                "sidebar-active-bg": "#2563eb",
                "sidebar-active-shadow": "rgba(37, 99, 235, 0.35)",
                "glass-card-bg": "rgba(22, 28, 45, 0.6)",
                "headerbar-bg": "#080a10",
                "primary-color": "#3b82f6",
                "border-color": "#1e2230",
            }
        }
        vars_dict = themes.get(bg_id, themes["default"])
        var_lines = []
        for k, v in vars_dict.items():
            var_lines.append(f"    --{k}: {v};")
        vars_block = "window {\n" + "\n".join(var_lines) + "\n}\n"
        css_text = vars_block + CSS_DATA
        if hasattr(self._css_provider, 'load_from_string'):
            self._css_provider.load_from_string(css_text)
        else:
            self._css_provider.load_from_data(css_text.encode('utf-8'))

    # ── ONBOARDING WIZARD UI ───────────────────────────────────────────────────
    def _build_wizard_ui(self):
        wizard_clamp = Adw.Clamp()
        wizard_clamp.set_maximum_size(680)
        wizard_clamp.set_valign(Gtk.Align.CENTER)

        wizard_main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        wizard_main_box.add_css_class("wizard-box")
        wizard_clamp.set_child(wizard_main_box)

        # Title Block
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_halign(Gtk.Align.CENTER)
        
        self.wiz_step_indicator = Gtk.Label()
        self.wiz_step_indicator.add_css_class("wizard-step-label")
        title_box.append(self.wiz_step_indicator)

        self.wiz_title_lbl = Gtk.Label()
        self.wiz_title_lbl.add_css_class("wizard-title")
        title_box.append(self.wiz_title_lbl)

        wizard_main_box.append(title_box)

        # Sub-stack for Wizard pages
        self.wizard_stack = Gtk.Stack()
        self.wizard_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.wizard_stack.set_transition_duration(250)
        wizard_main_box.append(self.wizard_stack)

        # Page 1: Select Game EXE
        p1_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.wiz_p1_desc = Gtk.Label(label=_t("wizard_step1_desc"))
        self.wiz_p1_desc.add_css_class("wizard-desc")
        self.wiz_p1_desc.set_wrap(True)
        self.wiz_p1_desc.set_xalign(0.0)
        p1_box.append(self.wiz_p1_desc)

        exe_select_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.wiz_exe_entry = Gtk.Entry()
        self.wiz_exe_entry.set_hexpand(True)
        self.wiz_exe_entry.set_text(self.cfg.get("exe_path", ""))
        self.wiz_exe_entry.connect("changed", self._on_wiz_exe_changed)
        exe_select_box.append(self.wiz_exe_entry)

        wiz_browse_btn = Gtk.Button(label=_t("btn_select"))
        wiz_browse_btn.add_css_class("pill")
        wiz_browse_btn.set_valign(Gtk.Align.CENTER)
        wiz_browse_btn.connect("clicked", self._on_wiz_browse_exe)
        exe_select_box.append(wiz_browse_btn)

        wiz_find_btn = Gtk.Button(label=_t("btn_auto_find"))
        wiz_find_btn.add_css_class("pill")
        wiz_find_btn.set_valign(Gtk.Align.CENTER)
        wiz_find_btn.connect("clicked", self._on_wiz_scan_exe)
        exe_select_box.append(wiz_find_btn)
        p1_box.append(exe_select_box)

        # Login Method Row
        self.wiz_login_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.wiz_login_box.set_margin_top(8)
        self.wiz_login_lbl = Gtk.Label(label=_t("lbl_login_method") + ":")
        self.wiz_login_lbl.add_css_class("dim-label")
        self.wiz_login_lbl.set_halign(Gtk.Align.START)
        self.wiz_login_box.append(self.wiz_login_lbl)

        login_labels = Gtk.StringList.new([_t(f"opt_login_{l}") for l in self._login_methods])
        self.wiz_login_dropdown = Gtk.DropDown(model=login_labels)
        self.wiz_login_dropdown.set_valign(Gtk.Align.CENTER)
        self.wiz_login_dropdown.connect("notify::selected", self._on_wiz_login_method_selected)
        self.wiz_login_box.append(self.wiz_login_dropdown)
        p1_box.append(self.wiz_login_box)

        curr_method = self.cfg.get("login_method", "proxypass")
        if curr_method in self._login_methods:
            self.wiz_login_dropdown.set_selected(self._login_methods.index(curr_method))

        # Download info box
        download_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        download_info_box.set_margin_top(8)

        self.wiz_ms_download_btn = Gtk.Button(label=_t("btn_download_where"))
        self.wiz_ms_download_btn.add_css_class("suggested-action")
        self.wiz_ms_download_btn.add_css_class("pill")
        self.wiz_ms_download_btn.set_halign(Gtk.Align.START)
        self.wiz_ms_download_btn.connect("clicked", lambda _: self._open_uri("https://github.com/bubbles-wow/mcbe-gdk-unpack-archive/releases/tag/1.26.30.5"))
        download_info_box.append(self.wiz_ms_download_btn)

        self.wiz_ms_disclaimer_lbl = Gtk.Label(label=_t("lbl_disclaimer"))
        self.wiz_ms_disclaimer_lbl.add_css_class("dim-label")
        self.wiz_ms_disclaimer_lbl.set_xalign(0.0)
        download_info_box.append(self.wiz_ms_disclaimer_lbl)
        p1_box.append(download_info_box)
        
        self.wizard_stack.add_named(p1_box, "step_exe")

        # Page 2: ProxyPass Setup
        p2_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.wiz_p2_desc = Gtk.Label(label=_t("wizard_step2_desc"))
        self.wiz_p2_desc.add_css_class("wizard-desc")
        self.wiz_p2_desc.set_wrap(True)
        self.wiz_p2_desc.set_xalign(0.0)
        p2_box.append(self.wiz_p2_desc)

        # ProxyPass Status Row
        pp_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        pp_row.set_margin_start(8)
        pp_row.append(Gtk.Label(label=_t("label_proxypass_jar") + " :"))
        self.wiz_pp_status_lbl = Gtk.Label(label=_t("status_not_installed"))
        self.wiz_pp_status_lbl.set_hexpand(True)
        self.wiz_pp_status_lbl.set_xalign(0.0)
        pp_row.append(self.wiz_pp_status_lbl)
        self.wiz_pp_dl_btn = Gtk.Button(label=_t("btn_download"))
        self.wiz_pp_dl_btn.add_css_class("pill")
        self.wiz_pp_dl_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_pp_dl_btn.connect("clicked", self._on_wiz_download_proxypass)
        pp_row.append(self.wiz_pp_dl_btn)
        
        self.wiz_pp_del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        self.wiz_pp_del_btn.add_css_class("destructive-action")
        self.wiz_pp_del_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_pp_del_btn.connect("clicked", self._on_delete_proxypass)
        pp_row.append(self.wiz_pp_del_btn)
        p2_box.append(pp_row)

        # Java JRE Status Row
        java_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        java_row.set_margin_start(8)
        java_row.append(Gtk.Label(label=_t("label_adoptium_jre") + " :"))
        self.wiz_java_status_lbl = Gtk.Label(label=_t("status_not_installed"))
        self.wiz_java_status_lbl.set_hexpand(True)
        self.wiz_java_status_lbl.set_xalign(0.0)
        java_row.append(self.wiz_java_status_lbl)
        self.wiz_java_dl_btn = Gtk.Button(label=_t("btn_download"))
        self.wiz_java_dl_btn.add_css_class("pill")
        self.wiz_java_dl_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_java_dl_btn.connect("clicked", self._on_wiz_download_java)
        java_row.append(self.wiz_java_dl_btn)
        
        self.wiz_java_del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        self.wiz_java_del_btn.add_css_class("destructive-action")
        self.wiz_java_del_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_java_del_btn.connect("clicked", self._on_delete_java)
        java_row.append(self.wiz_java_del_btn)
        p2_box.append(java_row)

        self.wiz_proxy_progress_lbl = Gtk.Label(label="")
        self.wiz_proxy_progress_lbl.add_css_class("dim-label")
        self.wiz_proxy_progress_lbl.set_xalign(0.0)
        p2_box.append(self.wiz_proxy_progress_lbl)

        self.wiz_proxy_progress_bar = Gtk.ProgressBar()
        self.wiz_proxy_progress_bar.set_visible(False)
        self.wiz_proxy_progress_bar.set_margin_top(4)
        p2_box.append(self.wiz_proxy_progress_bar)

        self.wizard_stack.add_named(p2_box, "step_proxy")

        # Page 3: GDK-Proton Setup
        p3_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.wiz_p3_desc = Gtk.Label(label=_t("wizard_step3_desc"))
        self.wiz_p3_desc.add_css_class("wizard-desc")
        self.wiz_p3_desc.set_wrap(True)
        self.wiz_p3_desc.set_xalign(0.0)
        p3_box.append(self.wiz_p3_desc)

        proton_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        proton_row.set_margin_start(8)
        proton_row.append(Gtk.Label(label=_t("label_gdk_proton") + " :"))
        self.wiz_proton_status_lbl = Gtk.Label(label=_t("status_not_installed"))
        self.wiz_proton_status_lbl.set_hexpand(True)
        self.wiz_proton_status_lbl.set_xalign(0.0)
        proton_row.append(self.wiz_proton_status_lbl)

        self.wiz_proton_dl_btn = Gtk.Button(label=_t("btn_download"))
        self.wiz_proton_dl_btn.add_css_class("pill")
        self.wiz_proton_dl_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_proton_dl_btn.connect("clicked", self._on_wiz_download_proton)
        proton_row.append(self.wiz_proton_dl_btn)

        self.wiz_proton_file_btn = Gtk.Button(label=_t("btn_install_file"))
        self.wiz_proton_file_btn.add_css_class("pill")
        self.wiz_proton_file_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_proton_file_btn.connect("clicked", self._on_wiz_manual_proton)
        proton_row.append(self.wiz_proton_file_btn)

        self.wiz_proton_folder_btn = Gtk.Button(label=_t("btn_install_folder"))
        self.wiz_proton_folder_btn.add_css_class("pill")
        self.wiz_proton_folder_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_proton_folder_btn.connect("clicked", self._on_wiz_manual_folder)
        proton_row.append(self.wiz_proton_folder_btn)
        p3_box.append(proton_row)

        self.wiz_proton_progress_lbl = Gtk.Label(label="")
        self.wiz_proton_progress_lbl.add_css_class("dim-label")
        self.wiz_proton_progress_lbl.set_xalign(0.0)
        p3_box.append(self.wiz_proton_progress_lbl)

        self.wiz_proton_progress_bar = Gtk.ProgressBar()
        self.wiz_proton_progress_bar.set_visible(False)
        self.wiz_proton_progress_bar.set_margin_top(4)
        p3_box.append(self.wiz_proton_progress_bar)

        self.wizard_stack.add_named(p3_box, "step_proton")

        # Wizard Navigation Buttons (Strict Aspect Ratio & Centered Alignment)
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        nav_box.set_margin_top(16)
        
        self.wiz_back_btn = Gtk.Button()
        self.wiz_back_btn.set_size_request(120, 38)
        self.wiz_back_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_back_btn.set_halign(Gtk.Align.CENTER)
        self.wiz_back_btn.add_css_class("pill")
        self.wiz_back_btn.connect("clicked", self._on_wiz_back)
        nav_box.append(self.wiz_back_btn)

        self.wiz_skip_btn = Gtk.Button()
        self.wiz_skip_btn.set_size_request(120, 38)
        self.wiz_skip_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_skip_btn.set_halign(Gtk.Align.CENTER)
        self.wiz_skip_btn.add_css_class("pill")
        self.wiz_skip_btn.add_css_class("flat")
        self.wiz_skip_btn.connect("clicked", self._on_wiz_skip)
        nav_box.append(self.wiz_skip_btn)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        nav_box.append(spacer)

        self.wiz_next_btn = Gtk.Button()
        self.wiz_next_btn.set_size_request(120, 38)
        self.wiz_next_btn.set_valign(Gtk.Align.CENTER)
        self.wiz_next_btn.set_halign(Gtk.Align.CENTER)
        self.wiz_next_btn.connect("clicked", self._on_wiz_next)
        self.wiz_next_btn.add_css_class("suggested-action")
        self.wiz_next_btn.add_css_class("pill")
        nav_box.append(self.wiz_next_btn)

        wizard_main_box.append(nav_box)

        # Set default step
        self.wizard_step = 1
        self._update_wizard_view()

        self.main_stack.add_named(wizard_clamp, "wizard")

    def _update_wizard_view(self):
        login_method = self.cfg.get("login_method", "proxypass")
        if login_method == "ingame":
            if self.wizard_step > 2:
                self.wizard_step = 2
            self.wiz_step_indicator.set_text(_t("wizard_step", current=self.wizard_step, total=2))
            if self.wizard_step == 1:
                self.wiz_title_lbl.set_text(_t("wizard_step1_title"))
                self.wizard_stack.set_visible_child_name("step_exe")
                self.wiz_back_btn.set_sensitive(False)
                self.wiz_back_btn.set_label(_t("btn_back"))
                self.wiz_next_btn.set_label(_t("wizard_next"))
                self.wiz_skip_btn.set_visible(True)
                self.wiz_skip_btn.set_label(_t("wizard_skip"))
            elif self.wizard_step == 2:
                self.wiz_title_lbl.set_text(_t("wizard_step3_title"))
                self.wizard_stack.set_visible_child_name("step_proton")
                self.wiz_back_btn.set_sensitive(True)
                self.wiz_back_btn.set_label(_t("btn_back"))
                self.wiz_next_btn.set_label(_t("wizard_finish"))
                self.wiz_skip_btn.set_visible(True)
                self.wiz_skip_btn.set_label(_t("wizard_skip"))
        else:
            self.wiz_step_indicator.set_text(_t("wizard_step", current=self.wizard_step, total=3))
            if self.wizard_step == 1:
                self.wiz_title_lbl.set_text(_t("wizard_step1_title"))
                self.wizard_stack.set_visible_child_name("step_exe")
                self.wiz_back_btn.set_sensitive(False)
                self.wiz_back_btn.set_label(_t("btn_back"))
                self.wiz_next_btn.set_label(_t("wizard_next"))
                self.wiz_skip_btn.set_visible(True)
                self.wiz_skip_btn.set_label(_t("wizard_skip"))
            elif self.wizard_step == 2:
                self.wiz_title_lbl.set_text(_t("wizard_step2_title"))
                self.wizard_stack.set_visible_child_name("step_proxy")
                self.wiz_back_btn.set_sensitive(True)
                self.wiz_back_btn.set_label(_t("btn_back"))
                self.wiz_next_btn.set_label(_t("wizard_next"))
                self.wiz_skip_btn.set_visible(True)
                self.wiz_skip_btn.set_label(_t("wizard_skip"))
            elif self.wizard_step == 3:
                self.wiz_title_lbl.set_text(_t("wizard_step3_title"))
                self.wizard_stack.set_visible_child_name("step_proton")
                self.wiz_back_btn.set_sensitive(True)
                self.wiz_back_btn.set_label(_t("btn_back"))
                self.wiz_next_btn.set_label(_t("wizard_finish"))
                self.wiz_skip_btn.set_visible(True)
                self.wiz_skip_btn.set_label(_t("wizard_skip"))

    def _on_wiz_back(self, _):
        if self.wizard_step > 1:
            self.wizard_step -= 1
            self._update_wizard_view()

    def _on_wiz_skip(self, _):
        login_method = self.cfg.get("login_method", "proxypass")
        max_step = 2 if login_method == "ingame" else 3
        if self.wizard_step < max_step:
            self.wizard_step += 1
            self._update_wizard_view()
        else:
            self._finish_wizard()

    def _on_wiz_next(self, _):
        login_method = self.cfg.get("login_method", "proxypass")
        max_step = 2 if login_method == "ingame" else 3
        if self.wizard_step < max_step:
            self.wizard_step += 1
            self._update_wizard_view()
        else:
            self._finish_wizard()

    def _on_wiz_login_method_selected(self, dropdown, _pspec):
        if not getattr(self, "_ui_initialized", False):
            return
        if getattr(self, "_updating_login_dropdowns", False):
            return
        if not getattr(self, "_ui_initialized", False):
            return
        idx = dropdown.get_selected()
        if 0 <= idx < len(self._login_methods):
            method = self._login_methods[idx]
            if self.cfg.get("login_method") != method:
                self._handle_login_method_change(method)
            self.cfg["login_method"] = method
            save_cfg(self.cfg)
            self._update_wizard_view()
            self._refresh_all_states()
            if hasattr(self, "settings_login_dropdown"):
                self._updating_login_dropdowns = True
                try:
                    self.settings_login_dropdown.set_selected(idx)
                finally:
                    self._updating_login_dropdowns = False

    def _on_settings_login_method_selected(self, dropdown, _pspec):
        if getattr(self, "_updating_login_dropdowns", False):
            return
        if not getattr(self, "_ui_initialized", False):
            return
        idx = dropdown.get_selected()
        if 0 <= idx < len(self._login_methods):
            method = self._login_methods[idx]
            if self.cfg.get("login_method") != method:
                self._handle_login_method_change(method)
            self.cfg["login_method"] = method
            save_cfg(self.cfg)
            self._update_wizard_view()
            self._refresh_all_states()
            if hasattr(self, "wiz_login_dropdown"):
                self._updating_login_dropdowns = True
                try:
                    self.wiz_login_dropdown.set_selected(idx)
                finally:
                    self._updating_login_dropdowns = False

    def _handle_login_method_change(self, method):
        # Delete auth.json in all possible directories to prevent conflicts between proxypass and ingame
        exe = self.cfg.get("exe_path", "").strip()
        
        # Reset launch proton cache so it is re-evaluated immediately
        self._launch_proton = None

        paths_to_delete = []
        if exe:
            paths_to_delete.append(auth_json_path(exe))
            paths_to_delete.append(os.path.join(os.path.dirname(exe), "auth.json"))
            paths_to_delete.append(os.path.join(os.path.dirname(os.path.dirname(exe)), "auth.json"))
        paths_to_delete.append(auth_json_path(""))
        
        from mc_launcher.config import PROXYPASS_DIR
        paths_to_delete.append(os.path.join(PROXYPASS_DIR, "auth.json"))
        
        jar = find_proxypass(exe)
        if jar:
            paths_to_delete.append(os.path.join(os.path.dirname(jar), "auth.json"))
            
        for path in set(paths_to_delete):
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    print(f"[Launcher] Deleted old auth file at {path} due to login method change.")
                except Exception as e:
                    print(f"[Launcher] Error deleting old auth file {path}: {e}")
                
        # If switching to proxypass, also clear the registry RefreshToken so it doesn't conflict
        if method == "proxypass":
            from mc_launcher.config import DATA_DIR
            token_file = os.path.join(DATA_DIR, "msa", "token.json")
            if os.path.isfile(token_file):
                try:
                    os.remove(token_file)
                    print(f"[Launcher] Deleted host-side token file at {token_file}")
                except Exception as e:
                    print(f"[Launcher] Error deleting host-side token: {e}")

            def clear_registry():
                proton = find_proton("ingame")
                if not proton:
                    proton = find_proton("proxypass")
                if proton:
                    from mc_launcher.game import build_env
                    env = build_env()
                    pfx = os.path.join(COMPAT_DATA, "pfx")
                    env["WINEPREFIX"] = pfx
                    for root in ["HKLM", "HKCU"]:
                        cmd = [
                            proton, "run", "reg", "delete",
                            f"{root}\\Software\\Wine\\WineGDK",
                            "/v", "RefreshToken",
                            "/f"
                        ]
                        try:
                            from mc_launcher.flatpak import wrap_flatpak_cmd
                            cmd = wrap_flatpak_cmd(cmd, env)
                            subprocess.run(cmd, env=env, capture_output=True, timeout=10)
                            print(f"[Launcher] Cleared {root} WineGDK RefreshToken registry key for proxypass mode.")
                        except Exception as e:
                            print(f"[Launcher] Registry {root} silme hatası: {e}")

            threading.Thread(target=clear_registry, daemon=True).start()

    def _refresh_login_dropdowns(self):
        if not hasattr(self, "_login_methods"):
            self._login_methods = ["proxypass", "ingame"]
        self._updating_login_dropdowns = True
        try:
            if hasattr(self, "wiz_login_dropdown"):
                selected = self.wiz_login_dropdown.get_selected()
                labels = Gtk.StringList.new([_t(f"opt_login_{l}") for l in self._login_methods])
                self.wiz_login_dropdown.set_model(labels)
                self.wiz_login_dropdown.set_selected(selected)
            if hasattr(self, "settings_login_dropdown"):
                selected = self.settings_login_dropdown.get_selected()
                labels = Gtk.StringList.new([_t(f"opt_login_{l}") for l in self._login_methods])
                self.settings_login_dropdown.set_model(labels)
                self.settings_login_dropdown.set_selected(selected)
        finally:
            self._updating_login_dropdowns = False

    def _finish_wizard(self):
        self.cfg["setup_completed"] = True
        save_cfg(self.cfg)
        self._refresh_all_states()
        self.main_stack.set_visible_child_name("launcher")
        self._toast(_t("status_ready"))

    # Wizard step actions
    def _on_wiz_exe_changed(self, entry):
        path = entry.get_text().strip()
        self.cfg["exe_path"] = path
        save_cfg(self.cfg)
        self.settings_exe_entry.set_text(path)

    def _on_wiz_browse_exe(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_exe"))
        dlg.open(self, None, self._on_wiz_exe_chosen)

    def _on_wiz_exe_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if path:
            self.wiz_exe_entry.set_text(path)
            self.cfg["exe_path"] = path
            save_cfg(self.cfg)
            self.settings_exe_entry.set_text(path)
            self._toast(_t("toast_exe_selected"))

    def _on_wiz_scan_exe(self, btn):
        btn.set_sensitive(False)
        def on_done(found):
            btn.set_sensitive(True)
            if not found:
                self._show_error(_t("err_scan_title"), _t("err_scan_not_found"))
                return
            best = found[0]
            for exe in found:
                if find_proxypass(exe):
                    best = exe
                    break
            self.wiz_exe_entry.set_text(best)
            self.cfg["exe_path"] = best
            save_cfg(self.cfg)
            self.settings_exe_entry.set_text(best)
            self._toast(_t("toast_game_found"))
            self._refresh_all_states()
        scan_for_exe(on_done=on_done, on_status=lambda msg, *_: self._toast(msg))

    def _on_wiz_download_proxypass(self, btn):
        btn.set_sensitive(False)
        self._update_progress_helper(self.wiz_proxy_progress_lbl, self.wiz_proxy_progress_bar, _t("progress_download_proxypass"))
        def worker():
            jar = ensure_proxypass(lambda msg, *_: GLib.idle_add(self._update_progress_helper, self.wiz_proxy_progress_lbl, self.wiz_proxy_progress_bar, msg))
            def done():
                btn.set_sensitive(True)
                self._update_progress_helper(self.wiz_proxy_progress_lbl, self.wiz_proxy_progress_bar, "")
                self._refresh_all_states()
                if jar:
                    self._toast(_t("toast_proxypass_installed"))
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    def _on_wiz_download_java(self, btn):
        btn.set_sensitive(False)
        self._update_progress_helper(self.wiz_proxy_progress_lbl, self.wiz_proxy_progress_bar, _t("progress_download_java"))
        def worker():
            java = ensure_java(lambda msg, *_: GLib.idle_add(self._update_progress_helper, self.wiz_proxy_progress_lbl, self.wiz_proxy_progress_bar, msg))
            def done():
                btn.set_sensitive(True)
                self._update_progress_helper(self.wiz_proxy_progress_lbl, self.wiz_proxy_progress_bar, "")
                self._refresh_all_states()
                if java:
                    self._toast(_t("toast_java_installed"))
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    def _on_wiz_download_proton(self, btn):
        btn.set_sensitive(False)
        self._update_progress_helper(self.wiz_proton_progress_lbl, self.wiz_proton_progress_bar, _t("progress_download_proton"))
        def on_status(msg, *_):
            GLib.idle_add(self._update_progress_helper, self.wiz_proton_progress_lbl, self.wiz_proton_progress_bar, msg)
        def on_done(ok):
            def complete():
                btn.set_sensitive(True)
                self._update_progress_helper(self.wiz_proton_progress_lbl, self.wiz_proton_progress_bar, "")
                self._refresh_all_states()
                if ok:
                    self._toast(_t("toast_proton_downloaded"))
            GLib.idle_add(complete)
        download_proton(on_status=on_status, on_done=on_done, login_method=self.cfg.get("login_method", "proxypass"))

    def _on_wiz_manual_proton(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_proton"))
        dlg.open(self, None, self._on_wiz_manual_proton_chosen)

    def _on_wiz_manual_proton_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if path:
            self.wiz_proton_file_btn.set_sensitive(False)
            self.wiz_proton_folder_btn.set_sensitive(False)
            self.wiz_proton_dl_btn.set_sensitive(False)
            def on_status(msg, *_):
                GLib.idle_add(self._update_progress_helper, self.wiz_proton_progress_lbl, self.wiz_proton_progress_bar, msg)
            def on_done(ok):
                def complete():
                    self.wiz_proton_file_btn.set_sensitive(True)
                    self.wiz_proton_folder_btn.set_sensitive(True)
                    self.wiz_proton_dl_btn.set_sensitive(True)
                    self._update_progress_helper(self.wiz_proton_progress_lbl, self.wiz_proton_progress_bar, "")
                    self._refresh_all_states()
                    if ok:
                        self._toast(_t("toast_proton_installed"))
                GLib.idle_add(complete)
            install_from_file(path, on_status=on_status, on_done=on_done, login_method=self.cfg.get("login_method", "proxypass"))

    def _on_wiz_manual_folder(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_proton"))
        dlg.select_folder(self, None, self._on_wiz_manual_folder_chosen)

    def _on_wiz_manual_folder_chosen(self, dlg, result):
        try:
            path = dlg.select_folder_finish(result).get_path()
        except Exception:
            return
        if path:
            self.wiz_proton_file_btn.set_sensitive(False)
            self.wiz_proton_folder_btn.set_sensitive(False)
            self.wiz_proton_dl_btn.set_sensitive(False)
            def on_status(msg, *_):
                GLib.idle_add(self._update_progress_helper, self.wiz_proton_progress_lbl, self.wiz_proton_progress_bar, msg)
            def on_done(ok):
                def complete():
                    self.wiz_proton_file_btn.set_sensitive(True)
                    self.wiz_proton_folder_btn.set_sensitive(True)
                    self.wiz_proton_dl_btn.set_sensitive(True)
                    self._update_progress_helper(self.wiz_proton_progress_lbl, self.wiz_proton_progress_bar, "")
                    self._refresh_all_states()
                    if ok:
                        self._toast(_t("toast_proton_installed"))
                GLib.idle_add(complete)
            install_from_folder(path, on_status=on_status, on_done=on_done, login_method=self.cfg.get("login_method", "proxypass"))

    def _on_delete_proxypass(self, _):
        from mc_launcher.proxypass import remove_proxypass
        if remove_proxypass():
            self._toast("ProxyPass silindi.")
        self._refresh_all_states()

    def _on_delete_java(self, _):
        from mc_launcher.java_rt import remove_java
        if remove_java():
            self._toast("Java Runtime silindi.")
        self._refresh_all_states()

    # ── MAIN LAUNCHER UI (LUNAR CLIENT STYLE) ──────────────────────────────────
    def _build_launcher_ui(self):
        launcher_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._sidebar_expanded = True

        # ── Sidebar ──
        self._sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._sidebar.add_css_class("sidebar-box")
        self._sidebar.set_size_request(240, -1)
        launcher_box.append(self._sidebar)

        # ── Sidebar Toggle Button (top of sidebar) ──
        toggle_btn = Gtk.Button()
        toggle_btn.add_css_class("sidebar-toggle-btn")
        self._sidebar_toggle_icon = Gtk.Image.new_from_icon_name("go-previous-symbolic")
        toggle_btn.set_child(self._sidebar_toggle_icon)
        toggle_btn.set_halign(Gtk.Align.END)
        toggle_btn.set_tooltip_text(_t("tt_sidebar_toggle"))
        toggle_btn.connect("clicked", self._on_sidebar_toggle)
        self._sidebar.append(toggle_btn)

        # App Logo Label
        self._logo_label = Gtk.Label(label="GDK CLIENT")
        self._logo_label.add_css_class("sidebar-logo")
        self._logo_label.add_css_class("title-1")
        self._logo_label.set_halign(Gtk.Align.CENTER)
        self._sidebar.append(self._logo_label)

        # Stack to hold right-side content pages
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.content_stack.set_transition_duration(320)
        self.content_stack.set_hexpand(True)
        self.content_stack.set_vexpand(True)

        # Helper to add sidebar buttons
        self._sidebar_buttons = {}
        self._sidebar_labels = {}
        self._sidebar_icon_widgets = {}
        def _add_sidebar_item(name: str, icon_name: str, label_text: str):
            btn = Gtk.Button()
            btn.add_css_class("sidebar-btn")

            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            lbl = Gtk.Label(label=label_text)
            lbl.set_halign(Gtk.Align.START)

            btn_box.append(icon)
            btn_box.append(lbl)
            btn.set_child(btn_box)

            btn.connect("clicked", lambda _btn, n=name: self._switch_content_page(n))
            self._sidebar.append(btn)
            self._sidebar_buttons[name] = btn
            self._sidebar_labels[name] = lbl
            self._sidebar_icon_widgets[name] = icon

        _add_sidebar_item("play", "media-playback-start-symbolic", _t("page_play"))
        _add_sidebar_item("proxy", "network-workgroup-symbolic", _t("page_proxy"))
        _add_sidebar_item("store", "starred-symbolic", _t("page_store"))
        _add_sidebar_item("settings", "emblem-system-symbolic", _t("page_settings"))
        _add_sidebar_item("about", "help-about-symbolic", _t("page_about"))
        _add_sidebar_item("wizard", "system-software-install-symbolic", _t("wizard_title"))

        # Separator
        self._sidebar.append(Gtk.Separator())

        # Bottom area in Sidebar: Language Dropdown
        self._lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._lang_box.set_margin_top(16)
        self._lang_box.set_margin_bottom(8)
        self._lang_box.set_halign(Gtk.Align.CENTER)

        self._lang_lbl_widget = Gtk.Label(label=_t("menu_language") + ": ")
        self._lang_lbl_widget.add_css_class("dim-label")
        self._lang_box.append(self._lang_lbl_widget)

        self.lang_btn = Gtk.MenuButton()
        self.lang_btn.add_css_class("flat")
        self._lang_box.append(self.lang_btn)
        self._sidebar.append(self._lang_box)

        # Content stack wrap
        content_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_wrap.set_hexpand(True)
        content_wrap.set_vexpand(True)
        content_wrap.append(self.content_stack)

        launcher_box.append(content_wrap)

        # ── Thin Custom HeaderBar ──
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        header_box.add_css_class("custom-headerbar")
        header_box.set_hexpand(True)

        # App title (left)
        hb_title = Gtk.Label(label="GDK CLIENT")
        hb_title.add_css_class("headerbar-title")
        hb_title.set_halign(Gtk.Align.START)
        hb_title.set_hexpand(True)
        hb_title.set_margin_start(4)
        header_box.append(hb_title)

        # Window control buttons (standard Linux: min — max — close)
        wm_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        wm_box.add_css_class("wm-controls")
        wm_box.set_halign(Gtk.Align.END)
        wm_box.set_valign(Gtk.Align.CENTER)

        def _make_wm_btn(css_extra, tooltip, icon_name, callback):
            btn = Gtk.Button()
            btn.add_css_class("wm-btn")
            if css_extra:
                btn.add_css_class(css_extra)
            btn.set_tooltip_text(tooltip)
            btn.set_halign(Gtk.Align.CENTER)
            btn.set_valign(Gtk.Align.CENTER)

            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(16)
            btn.set_child(icon)
            btn.connect("clicked", callback)
            return btn

        self._wm_btn_min = _make_wm_btn(
            None, _t("tt_minimize"), "window-minimize-symbolic", lambda _: self.minimize()
        )
        self._wm_btn_max = _make_wm_btn(
            None,
            _t("tt_maximize"),
            "window-maximize-symbolic",
            self._on_wm_maximize,
        )
        self._wm_btn_close = _make_wm_btn(
            "wm-btn-close", _t("tt_close"), "window-close-symbolic", lambda _: self.close()
        )

        wm_box.append(self._wm_btn_min)
        wm_box.append(self._wm_btn_max)
        wm_box.append(self._wm_btn_close)

        header_box.append(wm_box)

        # Wrap header_box inside Gtk.WindowHandle for window dragging
        headerbar = Gtk.WindowHandle()
        headerbar.set_child(header_box)

        # Wrap everything: headerbar on top, sidebar+content below
        root_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root_vbox.append(headerbar)
        root_vbox.append(launcher_box)

        self.main_stack.add_named(root_vbox, "launcher")

        # ── 1. PLAY PAGE — Background image + overlay content ──
        # Overlay: bg image behind, content box on top
        play_overlay = Gtk.Overlay()
        play_overlay.set_hexpand(True)
        play_overlay.set_vexpand(True)

        # Background image
        self._play_bg_picture = Gtk.Picture()
        self._play_bg_picture.add_css_class("play-bg")
        self._play_bg_picture.set_content_fit(Gtk.ContentFit.COVER)
        self._play_bg_picture.set_can_shrink(True)
        self._play_bg_picture.set_hexpand(True)
        self._play_bg_picture.set_vexpand(True)
        play_overlay.set_child(self._play_bg_picture)
        self._apply_play_background(animate=False)

        # Content clamp centered on top of image
        play_clamp = Adw.Clamp()
        play_clamp.set_maximum_size(700)
        play_clamp.set_valign(Gtk.Align.CENTER)
        play_clamp.set_halign(Gtk.Align.CENTER)
        play_clamp.set_hexpand(True)
        play_clamp.set_vexpand(True)

        play_panel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        play_panel_box.add_css_class("play-panel")
        play_panel_box.add_css_class("play-content-box")
        play_panel_box.set_valign(Gtk.Align.END)
        play_panel_box.set_vexpand(True)
        play_clamp.add_css_class("page-content")
        play_clamp.set_child(play_panel_box)
        play_overlay.add_overlay(play_clamp)

        # Game Title
        game_logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        game_logo_box.set_halign(Gtk.Align.CENTER)

        sub_lbl = Gtk.Label(label="MINECRAFT BEDROCK EDITION")
        sub_lbl.add_css_class("game-subtitle")
        game_logo_box.append(sub_lbl)

        title_lbl = Gtk.Label(label="GDK CLIENT")
        title_lbl.add_css_class("game-title")
        game_logo_box.append(title_lbl)

        play_panel_box.append(game_logo_box)

        # Play Button
        self.play_btn = Gtk.Button(label=_t("btn_start_game"))
        self.play_btn.add_css_class("play-btn-glowing")
        self.play_btn.set_halign(Gtk.Align.CENTER)
        self.play_btn.connect("clicked", self._on_launch_or_stop)
        play_panel_box.append(self.play_btn)

        # Launch Status Label
        self.launch_status_lbl = Gtk.Label(label=_t("status_ready"))
        self.launch_status_lbl.set_halign(Gtk.Align.CENTER)
        play_panel_box.append(self.launch_status_lbl)

        self.launch_progress_bar = Gtk.ProgressBar()
        self.launch_progress_bar.set_visible(False)
        self.launch_progress_bar.set_halign(Gtk.Align.CENTER)
        self.launch_progress_bar.set_size_request(200, -1)
        self.launch_progress_bar.set_margin_top(4)
        play_panel_box.append(self.launch_progress_bar)

        self.play_proxy_log_btn = Gtk.Button(label=_t("title_proxy_log"))
        self.play_proxy_log_btn.add_css_class("pill")
        self.play_proxy_log_btn.set_halign(Gtk.Align.CENTER)
        self.play_proxy_log_btn.connect("clicked", self._on_show_proxy_log)
        self.play_proxy_log_btn.set_visible(False)
        play_panel_box.append(self.play_proxy_log_btn)

        # Clean Account & Server Summary Card
        summary_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        summary_card.add_css_class("glass-card")
        summary_card.set_halign(Gtk.Align.FILL)
        play_panel_box.append(summary_card)

        # Destination Server Summary Row
        self.play_server_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.play_server_lbl = Gtk.Label(label=_t("label_dest_server") + ":")
        self.play_server_lbl.set_halign(Gtk.Align.START)
        self.play_server_box.append(self.play_server_lbl)

        self.play_server_val = Gtk.Label(label="—")
        self.play_server_val.add_css_class("dim-label")
        self.play_server_val.set_hexpand(True)
        self.play_server_val.set_xalign(0.0)
        self.play_server_box.append(self.play_server_val)

        self.play_server_btn = Gtk.Button(label=_t("btn_set_dest"))
        self.play_server_btn.add_css_class("pill")
        self.play_server_btn.connect("clicked", self._on_dest_settings)
        self.play_server_box.append(self.play_server_btn)
        summary_card.append(self.play_server_box)

        # Active Login/Gamertag Summary Row
        account_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.play_account_lbl = Gtk.Label(label=_t("label_active_account") + ":")
        self.play_account_lbl.set_halign(Gtk.Align.START)
        account_box.append(self.play_account_lbl)

        self.play_account_val = Gtk.Label(label="—")
        self.play_account_val.add_css_class("dim-label")
        self.play_account_val.set_hexpand(True)
        self.play_account_val.set_xalign(0.0)
        account_box.append(self.play_account_val)

        # In-game login buttons directly on the Play page
        self.play_login_btn = Gtk.Button(label=_t("btn_login"))
        self.play_login_btn.add_css_class("pill")
        self.play_login_btn.connect("clicked", self._on_proxy_login)
        account_box.append(self.play_login_btn)

        self.play_logout_btn = Gtk.Button(label=_t("btn_logout"))
        self.play_logout_btn.add_css_class("destructive-action")
        self.play_logout_btn.add_css_class("pill")
        self.play_logout_btn.connect("clicked", self._on_proxy_logout)
        account_box.append(self.play_logout_btn)

        summary_card.append(account_box)

        self.content_stack.add_named(play_overlay, "play")


        # ── 2. PROXYPASS & ACCOUNTS PAGE ──
        proxy_clamp = Adw.Clamp()
        proxy_clamp.set_maximum_size(900)
        proxy_clamp.set_hexpand(True)
        proxy_clamp.set_vexpand(True)
        proxy_clamp.add_css_class("page-content")

        proxy_scroll = Gtk.ScrolledWindow()
        proxy_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        proxy_scroll.set_hexpand(True)
        proxy_scroll.set_vexpand(True)
        proxy_clamp.set_child(proxy_scroll)

        proxy_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        proxy_box.set_margin_top(24)
        proxy_box.set_margin_bottom(24)
        proxy_box.set_margin_start(24)
        proxy_box.set_margin_end(24)
        proxy_scroll.set_child(proxy_box)

        self.proxy_page_title = Gtk.Label()
        self.proxy_page_title.add_css_class("page-title")
        self.proxy_page_title.set_halign(Gtk.Align.START)
        proxy_box.append(self.proxy_page_title)

        # Status cards
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        status_box.set_halign(Gtk.Align.FILL)
        
        # Login card
        login_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        login_card.add_css_class("glass-card")
        login_card.set_hexpand(True)
        self.proxy_auth_lbl = Gtk.Label()
        self.proxy_auth_lbl.add_css_class("glass-card-title")
        self.proxy_auth_lbl.set_halign(Gtk.Align.START)
        login_card.append(self.proxy_auth_lbl)
        self.proxy_auth_val = Gtk.Label(label=_t("status_auth_none"))
        self.proxy_auth_val.set_halign(Gtk.Align.START)
        login_card.append(self.proxy_auth_val)
        
        login_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        login_actions.set_halign(Gtk.Align.START)
        login_actions.set_margin_top(4)
        self.proxy_login_btn = Gtk.Button(label=_t("btn_login"))
        self.proxy_login_btn.add_css_class("pill")
        self.proxy_login_btn.connect("clicked", self._on_proxy_login)
        login_actions.append(self.proxy_login_btn)
        
        self.proxy_logout_btn = Gtk.Button(label=_t("btn_logout"))
        self.proxy_logout_btn.add_css_class("destructive-action")
        self.proxy_logout_btn.add_css_class("pill")
        self.proxy_logout_btn.connect("clicked", self._on_proxy_logout)
        login_actions.append(self.proxy_logout_btn)

        self.proxy_log_btn = Gtk.Button(label=_t("title_proxy_log"))
        self.proxy_log_btn.add_css_class("pill")
        self.proxy_log_btn.connect("clicked", self._on_show_proxy_log)
        login_actions.append(self.proxy_log_btn)

        self.proxy_reset_btn = Gtk.Button(label=_t("btn_reset_proxy"))
        self.proxy_reset_btn.add_css_class("pill")
        self.proxy_reset_btn.connect("clicked", self._on_proxy_reset)
        login_actions.append(self.proxy_reset_btn)

        login_card.append(login_actions)
        status_box.append(login_card)

        # Component installation card
        comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        comp_card.add_css_class("glass-card")
        comp_card.set_hexpand(True)
        self.proxy_comp_lbl = Gtk.Label()
        self.proxy_comp_lbl.add_css_class("glass-card-title")
        self.proxy_comp_lbl.set_halign(Gtk.Align.START)
        comp_card.append(self.proxy_comp_lbl)
        
        pp_status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        pp_status_box.add_css_class("component-row")
        self.proxy_pp_name_lbl = Gtk.Label()
        self.proxy_pp_name_lbl.add_css_class("component-name")
        self.proxy_pp_name_lbl.set_halign(Gtk.Align.START)
        pp_status_box.append(self.proxy_pp_name_lbl)
        self.proxy_pp_status = Gtk.Label(label="")
        self.proxy_pp_status.set_hexpand(True)
        self.proxy_pp_status.set_xalign(0.0)
        pp_status_box.append(self.proxy_pp_status)
        self.proxy_pp_btn = Gtk.Button(label=_t("btn_download"))
        self.proxy_pp_btn.connect("clicked", self._on_download_proxypass)
        self.proxy_pp_btn.add_css_class("pill")
        self.proxy_pp_btn.set_valign(Gtk.Align.CENTER)
        pp_status_box.append(self.proxy_pp_btn)
        
        self.proxy_pp_del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        self.proxy_pp_del_btn.add_css_class("destructive-action")
        self.proxy_pp_del_btn.set_valign(Gtk.Align.CENTER)
        self.proxy_pp_del_btn.connect("clicked", self._on_delete_proxypass)
        pp_status_box.append(self.proxy_pp_del_btn)
        comp_card.append(pp_status_box)

        self.proxy_pp_progress_bar = Gtk.ProgressBar()
        self.proxy_pp_progress_bar.set_visible(False)
        self.proxy_pp_progress_bar.set_margin_bottom(8)
        comp_card.append(self.proxy_pp_progress_bar)

        java_status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        java_status_box.add_css_class("component-row")
        self.proxy_java_name_lbl = Gtk.Label()
        self.proxy_java_name_lbl.add_css_class("component-name")
        self.proxy_java_name_lbl.set_halign(Gtk.Align.START)
        java_status_box.append(self.proxy_java_name_lbl)
        self.proxy_java_status = Gtk.Label(label="")
        self.proxy_java_status.set_hexpand(True)
        self.proxy_java_status.set_xalign(0.0)
        java_status_box.append(self.proxy_java_status)
        self.proxy_java_btn = Gtk.Button(label=_t("btn_download"))
        self.proxy_java_btn.connect("clicked", self._on_download_java)
        self.proxy_java_btn.add_css_class("pill")
        self.proxy_java_btn.set_valign(Gtk.Align.CENTER)
        java_status_box.append(self.proxy_java_btn)
        
        self.proxy_java_del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        self.proxy_java_del_btn.add_css_class("destructive-action")
        self.proxy_java_del_btn.set_valign(Gtk.Align.CENTER)
        self.proxy_java_del_btn.connect("clicked", self._on_delete_java)
        java_status_box.append(self.proxy_java_del_btn)
        comp_card.append(java_status_box)

        self.proxy_java_progress_bar = Gtk.ProgressBar()
        self.proxy_java_progress_bar.set_visible(False)
        self.proxy_java_progress_bar.set_margin_bottom(8)
        comp_card.append(self.proxy_java_progress_bar)

        status_box.append(comp_card)
        proxy_box.append(status_box)

        # ── ProxyPass Advanced Settings Card ──
        pp_settings_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        pp_settings_card.add_css_class("glass-card")
        pp_settings_card.set_margin_top(12)
        
        self.proxy_settings_title_lbl = Gtk.Label()
        self.proxy_settings_title_lbl.add_css_class("glass-card-title")
        self.proxy_settings_title_lbl.set_halign(Gtk.Align.START)
        pp_settings_card.append(self.proxy_settings_title_lbl)
        
        # Grid of settings
        settings_grid = Gtk.Grid()
        settings_grid.set_row_spacing(12)
        settings_grid.set_column_spacing(16)
        pp_settings_card.append(settings_grid)
        
        # Proxy Bind Host & Port
        self.proxy_bind_host_lbl = Gtk.Label()
        self.proxy_bind_host_lbl.set_halign(Gtk.Align.START)
        settings_grid.attach(self.proxy_bind_host_lbl, 0, 0, 1, 1)
        
        self.proxy_bind_host_entry = Gtk.Entry()
        self.proxy_bind_host_entry.set_hexpand(True)
        settings_grid.attach(self.proxy_bind_host_entry, 1, 0, 1, 1)
        
        self.proxy_bind_port_lbl = Gtk.Label()
        self.proxy_bind_port_lbl.set_halign(Gtk.Align.START)
        settings_grid.attach(self.proxy_bind_port_lbl, 2, 0, 1, 1)
        
        self.proxy_bind_port_entry = Gtk.Entry()
        self.proxy_bind_port_entry.set_hexpand(True)
        settings_grid.attach(self.proxy_bind_port_entry, 3, 0, 1, 1)
        
        # Dest Host & Port
        self.proxy_dest_host_lbl = Gtk.Label()
        self.proxy_dest_host_lbl.set_halign(Gtk.Align.START)
        settings_grid.attach(self.proxy_dest_host_lbl, 0, 1, 1, 1)
        
        self.proxy_dest_host_entry = Gtk.Entry()
        self.proxy_dest_host_entry.set_hexpand(True)
        settings_grid.attach(self.proxy_dest_host_entry, 1, 1, 1, 1)
        
        self.proxy_dest_port_lbl = Gtk.Label()
        self.proxy_dest_port_lbl.set_halign(Gtk.Align.START)
        settings_grid.attach(self.proxy_dest_port_lbl, 2, 1, 1, 1)
        
        self.proxy_dest_port_entry = Gtk.Entry()
        self.proxy_dest_port_entry.set_hexpand(True)
        settings_grid.attach(self.proxy_dest_port_entry, 3, 1, 1, 1)

        # Switches box
        switches_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        switches_box.set_margin_top(8)
        pp_settings_card.append(switches_box)
        
        # Online Mode switch
        online_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.proxy_online_mode_lbl = Gtk.Label()
        self.proxy_online_mode_lbl.set_hexpand(True)
        self.proxy_online_mode_lbl.set_xalign(0.0)
        self.proxy_online_mode_switch = Gtk.Switch()
        self.proxy_online_mode_switch.set_valign(Gtk.Align.CENTER)
        online_box.append(self.proxy_online_mode_lbl)
        online_box.append(self.proxy_online_mode_switch)
        switches_box.append(online_box)
        
        # Save Auth Details switch
        save_auth_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.proxy_save_auth_lbl = Gtk.Label()
        self.proxy_save_auth_lbl.set_hexpand(True)
        self.proxy_save_auth_lbl.set_xalign(0.0)
        self.proxy_save_auth_switch = Gtk.Switch()
        self.proxy_save_auth_switch.set_valign(Gtk.Align.CENTER)
        save_auth_box.append(self.proxy_save_auth_lbl)
        save_auth_box.append(self.proxy_save_auth_switch)
        switches_box.append(save_auth_box)
        
        # Broadcast Session switch
        broadcast_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.proxy_broadcast_lbl = Gtk.Label()
        self.proxy_broadcast_lbl.set_hexpand(True)
        self.proxy_broadcast_lbl.set_xalign(0.0)
        self.proxy_broadcast_switch = Gtk.Switch()
        self.proxy_broadcast_switch.set_valign(Gtk.Align.CENTER)
        broadcast_box.append(self.proxy_broadcast_lbl)
        broadcast_box.append(self.proxy_broadcast_switch)
        switches_box.append(broadcast_box)
        
        # Max Clients entry
        max_clients_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.proxy_max_clients_lbl = Gtk.Label()
        self.proxy_max_clients_lbl.set_hexpand(True)
        self.proxy_max_clients_lbl.set_xalign(0.0)
        self.proxy_max_clients_entry = Gtk.Entry()
        self.proxy_max_clients_entry.set_width_chars(8)
        self.proxy_max_clients_entry.set_valign(Gtk.Align.CENTER)
        max_clients_box.append(self.proxy_max_clients_lbl)
        max_clients_box.append(self.proxy_max_clients_entry)
        switches_box.append(max_clients_box)
        
        # Action Buttons
        settings_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        settings_actions.set_halign(Gtk.Align.END)
        settings_actions.set_margin_top(12)
        
        self.proxy_save_settings_btn = Gtk.Button()
        self.proxy_save_settings_btn.add_css_class("suggested-action")
        self.proxy_save_settings_btn.add_css_class("pill")
        self.proxy_save_settings_btn.connect("clicked", self._on_save_proxy_settings)
        settings_actions.append(self.proxy_save_settings_btn)
        
        pp_settings_card.append(settings_actions)
        proxy_box.append(pp_settings_card)

        self.content_stack.add_named(proxy_clamp, "proxy")


        # ── 3. UNIFIED SETTINGS & TOOLS PAGE ──
        settings_clamp = Adw.Clamp()
        settings_clamp.set_maximum_size(840)
        settings_clamp.add_css_class("page-content")

        settings_scroll = Gtk.ScrolledWindow()
        settings_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        settings_scroll.set_hexpand(True)
        settings_scroll.set_vexpand(True)
        settings_clamp.set_child(settings_scroll)

        settings_main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        settings_main_box.set_margin_top(24)
        settings_main_box.set_margin_bottom(24)
        settings_main_box.set_margin_start(24)
        settings_main_box.set_margin_end(24)
        settings_scroll.set_child(settings_main_box)

        # Settings Title
        self.settings_title = Gtk.Label()
        self.settings_title.add_css_class("page-title")
        self.settings_title.set_halign(Gtk.Align.START)
        settings_main_box.append(self.settings_title)

        # ── Category 1: Game Executable Path ──
        path_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        path_card.add_css_class("glass-card")
        self.settings_play_title = Gtk.Label()
        self.settings_play_title.add_css_class("glass-card-title")
        self.settings_play_title.set_halign(Gtk.Align.START)
        path_card.append(self.settings_play_title)

        path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.settings_exe_lbl = Gtk.Label()
        self.settings_exe_lbl.add_css_class("dim-label")
        self.settings_exe_lbl.set_halign(Gtk.Align.START)
        path_box.append(self.settings_exe_lbl)
        
        self.settings_exe_entry = Gtk.Entry()
        self.settings_exe_entry.set_hexpand(True)
        self.settings_exe_entry.set_placeholder_text(_t("ph_game_exe"))
        self.settings_exe_entry.set_text(self.cfg.get("exe_path", ""))
        self.settings_exe_entry.connect("changed", self._on_settings_exe_changed)
        path_box.append(self.settings_exe_entry)

        self.settings_exe_browse_btn = Gtk.Button(label=_t("btn_select"))
        self.settings_exe_browse_btn.add_css_class("pill")
        self.settings_exe_browse_btn.set_valign(Gtk.Align.CENTER)
        self.settings_exe_browse_btn.connect("clicked", self._on_wiz_browse_exe)
        path_box.append(self.settings_exe_browse_btn)

        self.settings_exe_find_btn = Gtk.Button(label=_t("btn_auto_find"))
        self.settings_exe_find_btn.add_css_class("pill")
        self.settings_exe_find_btn.set_valign(Gtk.Align.CENTER)
        self.settings_exe_find_btn.connect("clicked", self._on_wiz_scan_exe)
        path_box.append(self.settings_exe_find_btn)
        path_card.append(path_box)

        # Login Method Row in settings path_card
        settings_login_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        settings_login_row.add_css_class("settings-row")
        settings_login_row.set_margin_top(8)
        self.settings_login_lbl = Gtk.Label(label=_t("lbl_login_method") + ":")
        self.settings_login_lbl.add_css_class("dim-label")
        self.settings_login_lbl.set_halign(Gtk.Align.START)
        self.settings_login_lbl.set_hexpand(True)
        settings_login_row.append(self.settings_login_lbl)

        settings_login_labels = Gtk.StringList.new([_t(f"opt_login_{l}") for l in self._login_methods])
        self.settings_login_dropdown = Gtk.DropDown(model=settings_login_labels)
        self.settings_login_dropdown.set_valign(Gtk.Align.CENTER)
        self.settings_login_dropdown.connect("notify::selected", self._on_settings_login_method_selected)
        settings_login_row.append(self.settings_login_dropdown)
        path_card.append(settings_login_row)

        curr_method = self.cfg.get("login_method", "proxypass")
        if curr_method in self._login_methods:
            self.settings_login_dropdown.set_selected(self._login_methods.index(curr_method))

        # Add Download info box to settings path_card
        settings_ms_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        settings_ms_box.set_margin_top(4)

        self.settings_ms_download_btn = Gtk.Button(label=_t("btn_download_where"))
        self.settings_ms_download_btn.add_css_class("suggested-action")
        self.settings_ms_download_btn.add_css_class("pill")
        self.settings_ms_download_btn.set_halign(Gtk.Align.START)
        self.settings_ms_download_btn.connect("clicked", lambda _: self._open_uri("https://github.com/bubbles-wow/mcbe-gdk-unpack-archive/releases/tag/1.26.30.5"))
        settings_ms_box.append(self.settings_ms_download_btn)

        self.settings_ms_disclaimer_lbl = Gtk.Label(label=_t("lbl_disclaimer"))
        self.settings_ms_disclaimer_lbl.add_css_class("dim-label")
        self.settings_ms_disclaimer_lbl.set_xalign(0.0)
        settings_ms_box.append(self.settings_ms_disclaimer_lbl)
        path_card.append(settings_ms_box)

        settings_main_box.append(path_card)

        # ── Category 2: Performance & Safety Fixes ──
        perf_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        perf_card.add_css_class("glass-card")
        self.settings_perf_title = Gtk.Label()
        self.settings_perf_title.add_css_class("glass-card-title")
        self.settings_perf_title.set_halign(Gtk.Align.START)
        perf_card.append(self.settings_perf_title)

        perf_grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        
        # MangoHud Switch
        mango_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        mango_box.add_css_class("settings-row")
        self.settings_mango_lbl = Gtk.Label(label=_t("label_mangohud"))
        self.settings_mango_lbl.set_hexpand(True)
        self.settings_mango_lbl.set_halign(Gtk.Align.START)
        mango_box.append(self.settings_mango_lbl)
        self.settings_mango_switch = Gtk.Switch()
        self.settings_mango_switch.set_valign(Gtk.Align.CENTER)
        self.settings_mango_switch.connect("notify::active", self._on_mangohud_toggle)
        mango_box.append(self.settings_mango_switch)
        perf_grid.append(mango_box)

        # VSync Switch
        vsync_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vsync_box.add_css_class("settings-row")
        self.settings_vsync_lbl = Gtk.Label(label=_t("label_vsync"))
        self.settings_vsync_lbl.set_hexpand(True)
        self.settings_vsync_lbl.set_halign(Gtk.Align.START)
        vsync_box.append(self.settings_vsync_lbl)
        self.settings_vsync_switch = Gtk.Switch()
        self.settings_vsync_switch.set_valign(Gtk.Align.CENTER)
        self.settings_vsync_switch.connect("notify::active", self._on_vsync_toggle)
        vsync_box.append(self.settings_vsync_switch)
        perf_grid.append(vsync_box)

        # Safety loading freeze fix button
        fix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        fix_box.add_css_class("settings-row")
        fix_sp = Gtk.Box()
        fix_sp.set_hexpand(True)
        fix_box.append(fix_sp)
        self.settings_fix_btn = Gtk.Button()
        self.settings_fix_btn.add_css_class("pill")
        self.settings_fix_btn.connect("clicked", self._on_fix_loading_freeze)
        fix_box.append(self.settings_fix_btn)
        perf_grid.append(fix_box)

        perf_card.append(perf_grid)
        settings_main_box.append(perf_card)

        # ── Category 2b: Appearance ──
        appearance_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        appearance_card.add_css_class("glass-card")
        self.settings_appearance_title = Gtk.Label()
        self.settings_appearance_title.add_css_class("glass-card-title")
        self.settings_appearance_title.set_halign(Gtk.Align.START)
        appearance_card.append(self.settings_appearance_title)

        bg_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bg_row.add_css_class("settings-row")
        self.settings_bg_lbl = Gtk.Label()
        self.settings_bg_lbl.set_halign(Gtk.Align.START)
        self.settings_bg_lbl.set_hexpand(True)
        bg_row.append(self.settings_bg_lbl)

        bg_labels = Gtk.StringList.new([_t(f"bg_{bid}") for bid in self._bg_ids])
        self.bg_dropdown = Gtk.DropDown(model=bg_labels)
        self.bg_dropdown.set_valign(Gtk.Align.CENTER)
        self.bg_dropdown.connect("notify::selected", self._on_background_selected)
        bg_row.append(self.bg_dropdown)
        appearance_card.append(bg_row)

        # Language Dropdown Row in Settings
        lang_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lang_row.add_css_class("settings-row")
        self.settings_lang_lbl = Gtk.Label(label=_t("menu_language"))
        self.settings_lang_lbl.set_halign(Gtk.Align.START)
        self.settings_lang_lbl.set_hexpand(True)
        lang_row.append(self.settings_lang_lbl)

        self._lang_ids = ["tr", "en", "de", "zh"]
        lang_labels = Gtk.StringList.new([_t(f"lang_{lid}") for lid in self._lang_ids])
        self.settings_lang_dropdown = Gtk.DropDown(model=lang_labels)
        self.settings_lang_dropdown.set_valign(Gtk.Align.CENTER)
        current_lang_code = self._language if self._language in self._lang_ids else "en"
        self._updating_lang_dropdown = True
        try:
            self.settings_lang_dropdown.set_selected(self._lang_ids.index(current_lang_code))
        finally:
            self._updating_lang_dropdown = False
        self.settings_lang_dropdown.connect("notify::selected", self._on_settings_lang_selected)
        lang_row.append(self.settings_lang_dropdown)
        appearance_card.append(lang_row)

        self.bg_custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.bg_custom_box.add_css_class("settings-row")
        self.bg_custom_entry = Gtk.Entry()
        self.bg_custom_entry.set_hexpand(True)
        self.bg_custom_entry.set_placeholder_text(_t("ph_background_custom"))
        self.bg_custom_entry.set_text(self.cfg.get("play_background_custom", ""))
        self.bg_custom_entry.connect("changed", self._on_background_custom_changed)
        self.bg_custom_box.append(self.bg_custom_entry)

        self.bg_custom_browse_btn = Gtk.Button(label=_t("btn_select"))
        self.bg_custom_browse_btn.add_css_class("pill")
        self.bg_custom_browse_btn.set_valign(Gtk.Align.CENTER)
        self.bg_custom_browse_btn.connect("clicked", self._on_browse_background)
        self.bg_custom_box.append(self.bg_custom_browse_btn)
        appearance_card.append(self.bg_custom_box)

        current_bg = self.cfg.get("play_background", "default")
        if current_bg not in self._bg_ids:
            current_bg = "default"
        self.bg_dropdown.set_selected(self._bg_ids.index(current_bg))
        self.bg_custom_box.set_visible(current_bg == "custom")
        settings_main_box.append(appearance_card)

        # ── Category 3: DLL Injector settings ──
        dll_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        dll_card.add_css_class("glass-card")
        self.settings_dll_title = Gtk.Label()
        self.settings_dll_title.add_css_class("glass-card-title")
        self.settings_dll_title.set_halign(Gtk.Align.START)
        dll_card.append(self.settings_dll_title)

        dll_inputs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dll_path_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.settings_dll_lbl = Gtk.Label()
        self.settings_dll_lbl.add_css_class("dim-label")
        self.settings_dll_lbl.set_halign(Gtk.Align.START)
        dll_path_row.append(self.settings_dll_lbl)

        self.settings_dll_entry = Gtk.Entry()
        self.settings_dll_entry.set_hexpand(True)
        self.settings_dll_entry.set_placeholder_text(_t("ph_injector_exe"))
        self.settings_dll_entry.set_text(self.cfg.get("injector_path", ""))
        self.settings_dll_entry.connect("changed", self._on_dll_entry_changed)
        dll_path_row.append(self.settings_dll_entry)

        self.settings_dll_browse_btn = Gtk.Button(label=_t("btn_select"))
        self.settings_dll_browse_btn.add_css_class("pill")
        self.settings_dll_browse_btn.set_valign(Gtk.Align.CENTER)
        self.settings_dll_browse_btn.connect("clicked", self._on_browse_injector)
        dll_path_row.append(self.settings_dll_browse_btn)
        dll_inputs.append(dll_path_row)

        dll_toggle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        dll_toggle_row.add_css_class("settings-row")
        self.settings_dll_toggle_lbl = Gtk.Label(label=_t("tt_injector_switch"))
        self.settings_dll_toggle_lbl.set_hexpand(True)
        self.settings_dll_toggle_lbl.set_halign(Gtk.Align.START)
        self.settings_dll_toggle_lbl.set_wrap(True)
        self.settings_dll_toggle_lbl.set_xalign(0.0)
        dll_toggle_row.append(self.settings_dll_toggle_lbl)
        self.settings_dll_switch = Gtk.Switch()
        self.settings_dll_switch.set_active(bool(self.cfg.get("injector_autorun", False)))
        self.settings_dll_switch.set_valign(Gtk.Align.CENTER)
        self.settings_dll_switch.connect("notify::active", self._on_dll_toggle)
        dll_toggle_row.append(self.settings_dll_switch)
        dll_inputs.append(dll_toggle_row)
        dll_card.append(dll_inputs)
        settings_main_box.append(dll_card)

        # ── Category 4: Wine & Proton Management ──
        wine_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        wine_card.add_css_class("glass-card")
        self.settings_wine_title = Gtk.Label(label=_t("group_wine_proton"))
        self.settings_wine_title.add_css_class("glass-card-title")
        self.settings_wine_title.set_halign(Gtk.Align.START)
        wine_card.append(self.settings_wine_title)

        ver_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.settings_proton_ver_lbl = Gtk.Label()
        ver_box.append(self.settings_proton_ver_lbl)
        self.proton_ver_lbl = Gtk.Label()
        self.proton_ver_lbl.add_css_class("dim-label")
        ver_box.append(self.proton_ver_lbl)
        wine_card.append(ver_box)

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.settings_proton_dl_btn = Gtk.Button(label=_t("btn_download"))
        self.settings_proton_dl_btn.add_css_class("pill")
        self.settings_proton_dl_btn.connect("clicked", self._on_auto_download)
        action_box.append(self.settings_proton_dl_btn)

        self.settings_proton_file_btn = Gtk.Button(label=_t("btn_install_file"))
        self.settings_proton_file_btn.add_css_class("pill")
        self.settings_proton_file_btn.connect("clicked", self._on_manual_install)
        action_box.append(self.settings_proton_file_btn)

        self.settings_proton_folder_btn = Gtk.Button(label=_t("btn_install_folder"))
        self.settings_proton_folder_btn.add_css_class("pill")
        self.settings_proton_folder_btn.connect("clicked", self._on_manual_install_folder)
        action_box.append(self.settings_proton_folder_btn)
        wine_card.append(action_box)

        self.settings_proton_status_lbl = Gtk.Label(label="")
        self.settings_proton_status_lbl.add_css_class("dim-label")
        self.settings_proton_status_lbl.set_halign(Gtk.Align.START)
        wine_card.append(self.settings_proton_status_lbl)

        self.settings_proton_progress_bar = Gtk.ProgressBar()
        self.settings_proton_progress_bar.set_visible(False)
        self.settings_proton_progress_bar.set_margin_top(4)
        wine_card.append(self.settings_proton_progress_bar)

        prefix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.settings_prefix_lbl = Gtk.Label()
        prefix_box.append(self.settings_prefix_lbl)
        p_sp = Gtk.Box()
        p_sp.set_hexpand(True)
        prefix_box.append(p_sp)
        self.settings_prefix_btn = Gtk.Button(label=_t("btn_open_folder"))
        self.settings_prefix_btn.add_css_class("pill")
        self.settings_prefix_btn.connect("clicked", self._on_open_prefix)
        prefix_box.append(self.settings_prefix_btn)
        wine_card.append(prefix_box)

        winecfg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        winecfg_box.add_css_class("settings-row")
        self.settings_winecfg_lbl = Gtk.Label(label=_t("label_winecfg"))
        winecfg_box.append(self.settings_winecfg_lbl)
        w_sp = Gtk.Box()
        w_sp.set_hexpand(True)
        winecfg_box.append(w_sp)
        self.settings_winecfg_btn = Gtk.Button(label=_t("btn_open"))
        self.settings_winecfg_btn.add_css_class("pill")
        self.settings_winecfg_btn.connect("clicked", self._on_winecfg)
        winecfg_box.append(self.settings_winecfg_btn)
        wine_card.append(winecfg_box)

        settings_main_box.append(wine_card)

        # ── Category 5: Embedded options.txt Editor ──
        options_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        options_card.add_css_class("glass-card")
        self.settings_options_title = Gtk.Label()
        self.settings_options_title.add_css_class("glass-card-title")
        self.settings_options_title.set_halign(Gtk.Align.START)
        options_card.append(self.settings_options_title)

        editor_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.options_search_entry = Gtk.SearchEntry()
        self.options_search_entry.set_hexpand(True)
        self.options_search_entry.connect("search-changed", self._on_options_search_changed)
        editor_top.append(self.options_search_entry)

        self.save_options_btn = Gtk.Button(label=_t("btn_save"))
        self.save_options_btn.add_css_class("suggested-action")
        self.save_options_btn.add_css_class("pill")
        self.save_options_btn.connect("clicked", self._on_save_options)
        editor_top.append(self.save_options_btn)
        options_card.append(editor_top)

        # Scrollable Options Area (Fixed Height inside Settings to fit well)
        options_scroll = Gtk.ScrolledWindow()
        options_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        options_scroll.set_min_content_height(260)
        options_scroll.set_vexpand(False)
        self.options_list_box = Gtk.ListBox()
        self.options_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        options_scroll.set_child(self.options_list_box)
        options_card.append(options_scroll)

        settings_main_box.append(options_card)

        self.content_stack.add_named(settings_clamp, "settings")


        # ── 4. ABOUT PAGE ──
        about_clamp = Adw.Clamp()
        about_clamp.set_maximum_size(840)
        about_clamp.add_css_class("page-content")

        about_scroll = Gtk.ScrolledWindow()
        about_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        about_scroll.set_hexpand(True)
        about_scroll.set_vexpand(True)
        about_clamp.set_child(about_scroll)

        about_page_widget = Adw.PreferencesPage()
        about_scroll.set_child(about_page_widget)

        # ── Hakkında sayfası ────────────────────────────────────────────────
        about_group = Adw.PreferencesGroup()
        about_page_widget.add(about_group)

        # Hero satırı: ikon + başlık + açıklama (GNOME/Libadwaita tarzı)
        hero_row = Adw.PreferencesRow()
        hero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero_box.set_margin_top(18)
        hero_box.set_margin_bottom(10)
        hero_box.set_margin_start(6)
        hero_box.set_margin_end(6)
        hero_row.set_child(hero_box)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        head.set_halign(Gtk.Align.START)
        hero_box.append(head)

        # İkon: önce assets içinden, yoksa tema ikonu
        import os as _os
        from mc_launcher.config import SCRIPT_DIR as _SD
        icon_path = None
        for name in ("minecraft_gdk_launcher_logo.svg", "icon.svg", "icon.png"):
            path = _os.path.join(_SD, "assets", name)
            if _os.path.isfile(path):
                icon_path = path
                break
        
        if icon_path:
            img = Gtk.Image.new_from_file(icon_path)
        else:
            img = Gtk.Image.new_from_icon_name("help-about-symbolic")
        img.set_pixel_size(64)
        img.set_valign(Gtk.Align.START)
        head.append(img)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_valign(Gtk.Align.START)
        head.append(title_box)

        about_title = Gtk.Label(label=_t("about_title"))
        about_title.add_css_class("title-1")
        about_title.set_halign(Gtk.Align.START)
        about_title.set_xalign(0.0)
        title_box.append(about_title)
        self.about_title_lbl = about_title

        about_sub = Gtk.Label(label=_t("about_tagline"))
        about_sub.add_css_class("dim-label")
        about_sub.set_halign(Gtk.Align.START)
        about_sub.set_xalign(0.0)
        title_box.append(about_sub)
        self.about_tagline_lbl = about_sub

        about_lbl = Gtk.Label(label=_t("msg_about"))
        self.about_desc_lbl = about_lbl
        about_lbl.set_halign(Gtk.Align.START)
        about_lbl.set_xalign(0.0)
        about_lbl.set_wrap(True)
        about_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        about_lbl.set_selectable(True)
        hero_box.append(about_lbl)

        about_group.add(hero_row)

        links_group = Adw.PreferencesGroup(title=_t("about_links"))
        about_page_widget.add(links_group)
        self.about_links_group = links_group

        # GitHub
        gh_row = Adw.ActionRow(title=_t("about_github"))
        self.about_gh_btn = Gtk.Button(label=_t("btn_open"))
        self.about_gh_btn.add_css_class("pill")
        self.about_gh_btn.connect("clicked", lambda *_: self._open_uri("https://discord.gg/VzYZVWBjs"))
        gh_row.add_suffix(self.about_gh_btn)
        links_group.add(gh_row)
        self.about_gh_row = gh_row

        # Discord / iletişim
        dc_row = Adw.ActionRow(title=_t("about_discord"))
        self.about_dc_btn = Gtk.Button(label=_t("btn_open"))
        self.about_dc_btn.add_css_class("pill")
        self.about_dc_btn.connect("clicked", lambda *_: self._open_uri("https://discord.com/"))
        dc_row.add_suffix(self.about_dc_btn)
        links_group.add(dc_row)
        self.about_dc_row = dc_row

        info_group = Adw.PreferencesGroup(title=_t("about_info"))
        about_page_widget.add(info_group)
        self.about_info_group = info_group

        ver_row = Adw.ActionRow(title=_t("about_version"), subtitle="3.0")
        info_group.add(ver_row)
        self.about_ver_row = ver_row

        self.content_stack.add_named(about_clamp, "about")

        # Create Store page
        self._create_store_page()

        # Set default content page
        self._switch_content_page("play")

        # Build settings menu
        self._build_settings_menu()

    def _on_sidebar_toggle(self, _):
        self._sidebar_expanded = not self._sidebar_expanded
        if self._sidebar_expanded:
            # Expand
            self._sidebar.set_size_request(240, -1)
            self._logo_label.set_visible(True)
            self._lang_box.set_visible(True)
            for lbl in self._sidebar_labels.values():
                lbl.set_visible(True)
            self._sidebar_toggle_icon.set_from_icon_name("go-previous-symbolic")
        else:
            # Collapse
            self._sidebar.set_size_request(56, -1)
            self._logo_label.set_visible(False)
            self._lang_box.set_visible(False)
            for lbl in self._sidebar_labels.values():
                lbl.set_visible(False)
            self._sidebar_toggle_icon.set_from_icon_name("go-next-symbolic")

    def _on_wm_maximize(self, _):
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()
        self._update_wm_max_icon()

    def _update_wm_max_icon(self):
        if not hasattr(self, "_wm_btn_max"):
            return
        icon = self._wm_btn_max.get_child()
        if not icon:
            return
        if self.is_maximized():
            icon.set_from_icon_name("window-restore-symbolic")
            self._wm_btn_max.set_tooltip_text(_t("tt_unmaximize"))
        else:
            icon.set_from_icon_name("window-maximize-symbolic")
            self._wm_btn_max.set_tooltip_text(_t("tt_maximize"))

    def _apply_play_background(self, animate=True):
        if not hasattr(self, "_play_bg_picture"):
            return
        bg_id = self.cfg.get("play_background", "default")
        path = resolve_background(
            bg_id,
            self.cfg.get("play_background_custom", ""),
        )

        def _set_image():
            if path:
                self._play_bg_picture.set_filename(path)
            self._play_bg_picture.remove_css_class("play-bg-fade")
            return False

        if animate:
            self._play_bg_picture.add_css_class("play-bg-fade")
            GLib.timeout_add(180, _set_image)
        else:
            _set_image()

        self._apply_theme(bg_id)

    def _refresh_background_dropdown(self):
        if not hasattr(self, "bg_dropdown"):
            return
        self._updating_bg_dropdown = True
        try:
            selected = self.bg_dropdown.get_selected()
            bg_id = self._bg_ids[selected] if 0 <= selected < len(self._bg_ids) else "default"
            labels = Gtk.StringList.new([_t(f"bg_{bid}") for bid in self._bg_ids])
            self.bg_dropdown.set_model(labels)
            idx = self._bg_ids.index(bg_id) if bg_id in self._bg_ids else 0
            self.bg_dropdown.set_selected(idx)
        finally:
            self._updating_bg_dropdown = False

    def _on_background_selected(self, dropdown, _pspec):
        if getattr(self, "_updating_bg_dropdown", False):
            return
        idx = dropdown.get_selected()
        if idx < 0 or idx >= len(self._bg_ids):
            return
        bg_id = self._bg_ids[idx]
        if self.cfg.get("play_background") == bg_id:
            return
        self.cfg["play_background"] = bg_id
        save_cfg(self.cfg)
        self.bg_custom_box.set_visible(bg_id == "custom")
        self._apply_play_background()
        self._toast(_t("toast_background_changed"))

    def _on_background_custom_changed(self, entry):
        path = entry.get_text().strip()
        self.cfg["play_background_custom"] = path
        save_cfg(self.cfg)
        if self.cfg.get("play_background") == "custom" and path:
            self._apply_play_background()

    def _on_browse_background(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_background"))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        for pattern in ("image/*",):
            f = Gtk.FileFilter()
            f.add_mime_type(pattern)
            filters.append(f)
        dlg.set_filters(filters)
        dlg.open(self, None, self._on_background_chosen)

    def _on_background_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if not path:
            return
        self.cfg["play_background"] = "custom"
        self.cfg["play_background_custom"] = path
        save_cfg(self.cfg)
        self.bg_custom_entry.set_text(path)
        self.bg_custom_box.set_visible(True)
        if "custom" in self._bg_ids:
            self.bg_dropdown.set_selected(self._bg_ids.index("custom"))
        self._apply_play_background()
        self._toast(_t("toast_background_changed"))

    def _switch_content_page(self, name: str):
        if name == "wizard":
            self.wizard_step = 1
            self._update_wizard_view()
            self.main_stack.set_visible_child_name("wizard")
            return
        
        self.content_stack.set_visible_child_name(name)
        
        # Update sidebar active states
        for k, btn in self._sidebar_buttons.items():
            if k == name:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

        # Refresh state labels
        self._refresh_all_states()

        # Load options dynamically if switched to settings page (since it contains editor now)
        if name == "settings":
            self._build_options_editor()

    # ── OPTIONS EDITOR LOGIC ───────────────────────────────────────────────────
    def _build_options_editor(self):
        # Clear existing rows
        while True:
            row = self.options_list_box.get_row_at_index(0)
            if not row:
                break
            self.options_list_box.remove(row)

        self.options_entries = {}
        self.options_row_widgets = []

        path = options_txt_path()
        if not os.path.isfile(path):
            lbl = Gtk.Label(label=_t("err_options_not_found") + "\n" + _t("err_options_msg"))
            lbl.set_margin_top(40)
            lbl.set_margin_bottom(40)
            lbl.set_halign(Gtk.Align.CENTER)
            self.options_list_box.append(lbl)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                key, val = line.split(":", 1)

                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row_box.set_margin_top(8)
                row_box.set_margin_bottom(8)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)

                lbl = Gtk.Label(label=key)
                lbl.set_hexpand(True)
                lbl.set_xalign(0.0)
                row_box.append(lbl)

                if val in ["0", "1"]:
                    switch = Gtk.Switch()
                    switch.set_active(val == "1")
                    switch.set_valign(Gtk.Align.CENTER)
                    row_box.append(switch)
                    self.options_entries[key] = switch
                else:
                    entry = Gtk.Entry()
                    entry.set_text(val)
                    entry.set_valign(Gtk.Align.CENTER)
                    row_box.append(entry)
                    self.options_entries[key] = entry

                row = Gtk.ListBoxRow()
                row.set_child(row_box)
                self.options_list_box.append(row)
                self.options_row_widgets.append((key, row))

        except Exception as e:
            self._show_error(_t("err_title"), _t("err_options_read", error=e))

    def _on_options_search_changed(self, entry):
        text = entry.get_text().strip().lower()
        for key, row in self.options_row_widgets:
            visible = True
            if text:
                visible = text in key.lower()
            row.set_visible(visible)

    def _on_save_options(self, _):
        path = options_txt_path()
        if not os.path.isfile(path):
            return
        try:
            new_lines = []
            for key, widget in self.options_entries.items():
                if isinstance(widget, Gtk.Switch):
                    val = "1" if widget.get_active() else "0"
                else:
                    val = widget.get_text().strip()
                new_lines.append(f"{key}:{val}\n")
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            self._toast(_t("toast_options_saved"))
        except Exception as e:
            self._show_error(_t("err_save_title"), str(e))

    # ── LOGIC REFRESHES & STATES ───────────────────────────────────────────────
    def _refresh_all_states(self):
        if not getattr(self, "_ui_initialized", False):
            return
        exe = self.cfg.get("exe_path", "").strip()
        
        # Update summaries on Play tab
        self.play_account_val.set_text(self._get_auth_username())

        # Server destination
        if exe:
            host, port = read_destination(exe)
            if host:
                self.play_server_val.set_text(f"{host}:{port}")
            else:
                self.play_server_val.set_text(_t("status_config_not_found"))
        else:
            self.play_server_val.set_text("—")

        # Update Settings tab configurations
        self.settings_dll_entry.set_text(self.cfg.get("injector_path", ""))
        self.settings_dll_switch.set_active(bool(self.cfg.get("injector_autorun", False)))
        self.settings_mango_switch.set_active(self._mangohud_on)

        # VSync switch state from options.txt
        vsync_val = "0"
        if os.path.isfile(options_txt_path()):
            try:
                with open(options_txt_path(), "r") as f:
                    for line in f:
                        if line.startswith("gfx_vsync:"):
                            vsync_val = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass
        self.settings_vsync_switch.set_active(vsync_val == "1")

        # 2. Update ProxyPass components & status
        pp_exists = bool(find_proxypass(exe))
        java_exists = bool(find_java())
        auth_exists = auth_json_exists(exe)

        # Onboarding states
        if pp_exists:
            self.wiz_pp_status_lbl.set_text(_t("status_installed_ok"))
            self.wiz_pp_status_lbl.set_css_classes(["status-label-ok"])
        else:
            self.wiz_pp_status_lbl.set_text(_t("status_not_installed"))
            self.wiz_pp_status_lbl.set_css_classes(["status-label-error"])

        if java_exists:
            self.wiz_java_status_lbl.set_text(_t("status_installed_ok"))
            self.wiz_java_status_lbl.set_css_classes(["status-label-ok"])
        else:
            self.wiz_java_status_lbl.set_text(_t("status_not_installed"))
            self.wiz_java_status_lbl.set_css_classes(["status-label-error"])

        # Main launcher page states
        self.proxy_pp_status.set_text(_t("status_installed_ok") if pp_exists else _t("status_not_installed"))
        self.proxy_pp_status.set_css_classes(["status-label-ok"] if pp_exists else ["status-label-error"])
        
        self.proxy_pp_btn.set_sensitive(not pp_exists)
        self.proxy_pp_del_btn.set_sensitive(pp_exists)
        self.wiz_pp_dl_btn.set_sensitive(not pp_exists)
        self.wiz_pp_del_btn.set_sensitive(pp_exists)
        
        self.proxy_java_status.set_text(_t("status_installed_ok") if java_exists else _t("status_not_installed"))
        self.proxy_java_status.set_css_classes(["status-label-ok"] if java_exists else ["status-label-error"])
        
        self.proxy_java_btn.set_sensitive(not java_exists)
        self.proxy_java_del_btn.set_sensitive(java_exists)
        self.wiz_java_dl_btn.set_sensitive(not java_exists)
        self.wiz_java_del_btn.set_sensitive(java_exists)

        if auth_exists:
            self.proxy_auth_val.set_text(_t("status_auth_done"))
            self.proxy_auth_val.set_css_classes(["status-label-ok"])
            self.proxy_login_btn.set_visible(False)
            self.proxy_logout_btn.set_visible(True)
        else:
            self.proxy_auth_val.set_text(_t("status_auth_none"))
            self.proxy_auth_val.set_css_classes(["status-label-warn"])
            self.proxy_login_btn.set_visible(True)
            self.proxy_logout_btn.set_visible(False)

        # Toggle visibility of ProxyPass-related settings/pages and direct login/logout buttons
        login_method = self.cfg.get("login_method", "proxypass")
        if login_method == "ingame":
            self.play_login_btn.set_visible(not auth_exists)
            self.play_logout_btn.set_visible(auth_exists)
            self.play_server_box.set_visible(False)
        else:
            self.play_login_btn.set_visible(False)
            self.play_logout_btn.set_visible(False)
            self.play_server_box.set_visible(True)

        if "proxy" in self._sidebar_buttons:
            self._sidebar_buttons["proxy"].set_visible(login_method == "proxypass")
            if login_method == "ingame" and self.content_stack.get_visible_child_name() == "proxy":
                self._switch_content_page("play")

        # Ensure self._proxy_proc is synced with self._game_procs
        proxy = self._game_procs.get("proxy") if hasattr(self, "_game_procs") else None
        if proxy is not None:
            self._proxy_proc = proxy

        # Update visibility of the proxy log buttons
        has_proxy_logs = False
        with self._proxy_log_lock:
            has_proxy_logs = len(self._proxy_log_buf) > 0

        is_proxy_running = bool(self._proxy_proc and self._proxy_proc.poll() is None)
        show_log_btn = is_proxy_running or has_proxy_logs
        self.proxy_log_btn.set_visible(show_log_btn)
        if hasattr(self, "play_proxy_log_btn"):
            self.play_proxy_log_btn.set_visible(show_log_btn)

        # 3. Update Proton states
        p = find_proton(self.cfg.get("login_method", "proxypass"))
        if p:
            proton_name = os.path.basename(os.path.dirname(p))
            self.wiz_proton_status_lbl.set_text(_t("status_installed_named", name=proton_name))
            self.wiz_proton_status_lbl.set_css_classes(["status-label-ok"])
            self.proton_ver_lbl.set_text(proton_name)
        else:
            self.wiz_proton_status_lbl.set_text(_t("status_not_installed"))
            self.wiz_proton_status_lbl.set_css_classes(["status-label-error"])
            self.proton_ver_lbl.set_text(_t("status_not_installed"))

        # Refresh advanced ProxyPass settings fields if present
        if hasattr(self, "proxy_bind_host_entry") and exe:
            try:
                pp_cfg = read_proxypass_config(exe)
                self.proxy_bind_host_entry.set_text(pp_cfg.get("proxy_host", "0.0.0.0"))
                self.proxy_bind_port_entry.set_text(pp_cfg.get("proxy_port", "19132"))
                self.proxy_dest_host_entry.set_text(pp_cfg.get("dest_host", "127.0.0.1"))
                self.proxy_dest_port_entry.set_text(pp_cfg.get("dest_port", "19132"))
                self.proxy_online_mode_switch.set_active(pp_cfg.get("online_mode", True))
                self.proxy_save_auth_switch.set_active(pp_cfg.get("save_auth_details", True))
                self.proxy_broadcast_switch.set_active(pp_cfg.get("broadcast_session", False))
                self.proxy_max_clients_entry.set_text(str(pp_cfg.get("max_clients", 0)))
            except Exception as e:
                print(f"Error loading ProxyPass config on refresh: {e}")

    def _get_auth_username(self) -> str:
        exe = self.cfg.get("exe_path", "").strip()
        auth_path = auth_json_path(exe)
        if not os.path.isfile(auth_path):
            return _t("status_auth_none")
        try:
            import json
            with open(auth_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in ("name", "Name", "gamertag", "Gamertag", "username", "Username"):
                if key in data and data[key]:
                    return str(data[key])
        except Exception:
            pass
        return _t("status_auth_done")

    def _toast(self, msg: str):
        GLib.idle_add(lambda: self._toast_overlay.add_toast(Adw.Toast(title=msg)) or False)

    def _open_uri(self, uri: str):
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except Exception:
            pass

    def _show_error(self, title: str, msg: str):
        def _s():
            dlg = Adw.AlertDialog(heading=title, body=msg)
            dlg.add_response("ok", _t("btn_close"))
            dlg.present(self)
            return False
        GLib.idle_add(_s)

    def _apply_language(self):
        # Update sidebar labels
        if "play" in self._sidebar_labels: self._sidebar_labels["play"].set_label(_t("page_play"))
        if "proxy" in self._sidebar_labels: self._sidebar_labels["proxy"].set_label(_t("page_proxy"))
        if "store" in self._sidebar_labels: self._sidebar_labels["store"].set_label(_t("page_store"))
        if "settings" in self._sidebar_labels: self._sidebar_labels["settings"].set_label(_t("page_settings"))
        if "about" in self._sidebar_labels: self._sidebar_labels["about"].set_label(_t("page_about"))
        if "wizard" in self._sidebar_labels: self._sidebar_labels["wizard"].set_label(_t("wizard_title"))

        # Update language dropdown button label
        self._build_settings_menu()
        self.lang_btn.set_tooltip_text(_t("menu_language"))
        self._lang_lbl_widget.set_text(_t("menu_language") + ": ")

        # Window controls
        if hasattr(self, "_wm_btn_close"):
            self._wm_btn_close.set_tooltip_text(_t("tt_close"))
            self._wm_btn_min.set_tooltip_text(_t("tt_minimize"))
            self._update_wm_max_icon()

        # Update wizard views
        self._update_wizard_view()
        self.wiz_p1_desc.set_text(_t("wizard_step1_desc"))
        self.wiz_p2_desc.set_text(_t("wizard_step2_desc"))
        self.wiz_p3_desc.set_text(_t("wizard_step3_desc"))

        # Update Play view labels
        is_running = self._is_game_running()
        self.play_btn.set_label(_t("btn_stop_game" if is_running else "btn_start_game"))
        self.play_server_lbl.set_text(_t("label_dest_server") + ":")
        self.play_account_lbl.set_text(_t("label_active_account") + ":")
        self.play_server_btn.set_label(_t("btn_set_dest"))

        # Update Settings view labels
        self.settings_title.set_text(_t("page_settings"))
        self.settings_play_title.set_text(_t("group_play"))
        self.settings_perf_title.set_text(_t("group_perf"))
        self.settings_appearance_title.set_text(_t("group_appearance"))
        self.settings_bg_lbl.set_text(_t("label_play_background"))
        if hasattr(self, "settings_lang_lbl"):
            self.settings_lang_lbl.set_text(_t("menu_language"))
        self._refresh_background_dropdown()
        self._refresh_lang_dropdown()
        self.bg_custom_entry.set_placeholder_text(_t("ph_background_custom"))
        self.bg_custom_browse_btn.set_label(_t("btn_select"))
        self.bg_custom_box.set_visible(self.cfg.get("play_background", "default") == "custom")
        self.settings_dll_title.set_text(_t("group_dll"))
        self.settings_wine_title.set_text(_t("group_wine_proton"))
        self.settings_options_title.set_text(_t("title_options"))

        self.settings_exe_lbl.set_text(_t("ph_game_exe"))
        self.settings_exe_entry.set_placeholder_text(_t("ph_game_exe"))
        self.settings_exe_find_btn.set_label(_t("btn_auto_find"))
        self.settings_exe_browse_btn.set_label(_t("btn_select"))
        self.settings_ms_download_btn.set_label(_t("btn_download_where"))
        self.wiz_ms_download_btn.set_label(_t("btn_download_where"))
        self.wiz_ms_disclaimer_lbl.set_text(_t("lbl_disclaimer"))
        self.settings_ms_disclaimer_lbl.set_text(_t("lbl_disclaimer"))

        if hasattr(self, "wiz_login_lbl"):
            self.wiz_login_lbl.set_text(_t("lbl_login_method") + ":")
        if hasattr(self, "settings_login_lbl"):
            self.settings_login_lbl.set_text(_t("lbl_login_method") + ":")
        self._refresh_login_dropdowns()

        self.settings_mango_lbl.set_text(_t("label_mangohud"))
        self.settings_vsync_lbl.set_text(_t("label_vsync"))
        self.settings_fix_btn.set_label(_t("label_loading_fix"))

        self.settings_dll_lbl.set_text(_t("ph_injector_exe"))
        self.settings_dll_entry.set_placeholder_text(_t("ph_injector_exe"))
        self.settings_dll_toggle_lbl.set_text(_t("tt_injector_switch"))
        self.settings_dll_browse_btn.set_label(_t("btn_select"))
        self.settings_winecfg_lbl.set_text(_t("label_winecfg"))

        self.settings_proton_ver_lbl.set_text(_t("label_version") + ":")
        self.settings_proton_dl_btn.set_label(_t("btn_download"))
        self.settings_proton_file_btn.set_label(_t("btn_install_file"))
        self.settings_proton_folder_btn.set_label(_t("btn_install_folder"))
        self.wiz_proton_file_btn.set_label(_t("btn_install_file"))
        self.wiz_proton_folder_btn.set_label(_t("btn_install_folder"))
        self.settings_prefix_lbl.set_text(_t("label_wine_prefix"))
        self.settings_prefix_btn.set_label(_t("btn_open_folder"))
        self.settings_winecfg_btn.set_label(_t("btn_open"))

        self.options_search_entry.set_placeholder_text(_t("ph_search"))
        self.save_options_btn.set_label(_t("btn_save"))

        # Update Proxy view labels
        self.proxy_page_title.set_text(_t("page_proxy"))
        self.proxy_auth_lbl.set_text(_t("label_auth_status"))
        self.proxy_comp_lbl.set_text(_t("group_components"))
        self.proxy_pp_name_lbl.set_text(_t("label_proxypass") + ":")
        self.proxy_java_name_lbl.set_text(_t("label_adoptium_jre") + ":")
        self.proxy_logout_btn.set_label(_t("btn_logout"))
        self.proxy_login_btn.set_label(_t("btn_login"))
        self.proxy_log_btn.set_label(_t("title_proxy_log"))
        if hasattr(self, "play_proxy_log_btn"):
            self.play_proxy_log_btn.set_label(_t("title_proxy_log"))
        self.proxy_pp_btn.set_label(_t("btn_download"))
        self.proxy_java_btn.set_label(_t("btn_download"))

        # Advanced ProxyPass settings translation
        if hasattr(self, "proxy_settings_title_lbl"):
            self.proxy_settings_title_lbl.set_text(_t("group_proxypass_settings"))
            self.proxy_bind_host_lbl.set_text(_t("label_proxy_host") + ":")
            self.proxy_bind_port_lbl.set_text(_t("label_proxy_port") + ":")
            self.proxy_dest_host_lbl.set_text(_t("label_dest_host") + ":")
            self.proxy_dest_port_lbl.set_text(_t("label_dest_port") + ":")
            self.proxy_online_mode_lbl.set_text(_t("label_online_mode"))
            self.proxy_save_auth_lbl.set_text(_t("label_save_auth_details"))
            self.proxy_broadcast_lbl.set_text(_t("label_broadcast_session"))
            self.proxy_max_clients_lbl.set_text(_t("label_max_clients"))
            self.proxy_save_settings_btn.set_label(_t("btn_save"))

        # Update Store view labels
        if hasattr(self, "store_page_title"):
            self.store_page_title.set_text(_t("page_store"))
            self.store_page_desc.set_text(_t("label_store_desc"))
            self.store_curated_title.set_text(_t("group_store"))
            self.store_custom_title.set_text(_t("label_custom_url"))
            self.store_custom_entry.set_placeholder_text(_t("ph_custom_url"))
            self.store_custom_btn.set_label(_t("btn_install_mod"))
            if hasattr(self, "store_library_title"):
                self.store_library_title.set_text(_t("store_library_title"))
                self._refresh_store_library()
            self._populate_curated_store()

        # Update About view labels
        if hasattr(self, "about_title_lbl"):
            self.about_title_lbl.set_text(_t("about_title"))
        if hasattr(self, "about_tagline_lbl"):
            self.about_tagline_lbl.set_text(_t("about_tagline"))
        if hasattr(self, "about_desc_lbl"):
            self.about_desc_lbl.set_text(_t("msg_about"))
        if hasattr(self, "about_links_group"):
            self.about_links_group.set_title(_t("about_links"))
        if hasattr(self, "about_info_group"):
            self.about_info_group.set_title(_t("about_info"))
        if hasattr(self, "about_gh_row"):
            self.about_gh_row.set_title(_t("about_github"))
        if hasattr(self, "about_dc_row"):
            self.about_dc_row.set_title(_t("about_discord"))
        if hasattr(self, "about_gh_btn"):
            self.about_gh_btn.set_label(_t("btn_open"))
        if hasattr(self, "about_dc_btn"):
            self.about_dc_btn.set_label(_t("btn_open"))
        if hasattr(self, "about_ver_row"):
            self.about_ver_row.set_title(_t("about_version"))

    def _build_settings_menu(self):
        root = Gio.Menu()
        lang_menu = Gio.Menu()
        for c in ("tr", "en", "de", "zh"):
            item = Gio.MenuItem.new(_t(f"lang_{c}"), None)
            item.set_action_and_target_value("win.language", GLib.Variant("s", c))
            lang_menu.append_item(item)

        root.append_submenu(_t("menu_language"), lang_menu)
        self.lang_btn.set_menu_model(root)

        # Create simple menu trigger action
        if not hasattr(self, "_lang_action_connected"):
            code = self._language if self._language in ("tr", "en", "de", "zh") else "en"
            self._lang_action = Gio.SimpleAction.new_stateful(
                "language",
                GLib.VariantType.new("s"),
                GLib.Variant("s", code),
            )
            self._lang_action.connect("change-state", self._on_language_action)
            self.add_action(self._lang_action)
            self._lang_action_connected = True

        # Set active language label on button
        self.lang_btn.set_label(_t(f"lang_{self._language}"))

    def _on_language_action(self, action, value):
        code = value.get_string() if value is not None else "tr"
        if self._language == code:
            return
        set_current_lang(code)
        action.set_state(GLib.Variant("s", code))
        self._language = code
        self.cfg["language"] = code
        save_cfg(self.cfg)
        if hasattr(self, "settings_lang_dropdown"):
            self._updating_lang_dropdown = True
            try:
                idx = self._lang_ids.index(code) if code in self._lang_ids else 0
                self.settings_lang_dropdown.set_selected(idx)
            finally:
                self._updating_lang_dropdown = False
        self._apply_language()

    def _on_settings_lang_selected(self, dropdown, _pspec):
        if getattr(self, "_updating_lang_dropdown", False):
            return
        idx = dropdown.get_selected()
        if idx < 0 or idx >= len(self._lang_ids):
            return
        code = self._lang_ids[idx]
        if self._language == code:
            return
        set_current_lang(code)
        self._language = code
        self.cfg["language"] = code
        save_cfg(self.cfg)
        if hasattr(self, "_lang_action"):
            self._lang_action.set_state(GLib.Variant("s", code))
        self._apply_language()

    def _refresh_lang_dropdown(self):
        if not hasattr(self, "settings_lang_dropdown"):
            return
        self._updating_lang_dropdown = True
        try:
            selected = self.settings_lang_dropdown.get_selected()
            lang_id = self._lang_ids[selected] if 0 <= selected < len(self._lang_ids) else "en"
            labels = Gtk.StringList.new([_t(f"lang_{lid}") for lid in self._lang_ids])
            self.settings_lang_dropdown.set_model(labels)
            idx = self._lang_ids.index(lang_id) if lang_id in self._lang_ids else 0
            self.settings_lang_dropdown.set_selected(idx)
        finally:
            self._updating_lang_dropdown = False

    def _update_progress_helper(self, label, progress_bar, msg):
        if not label:
            return
        label.set_text(msg)
        if not progress_bar:
            return
            
        import re
        # Check if there is a percentage (e.g. 50% or %50)
        m = re.search(r'(\d+)\s*%', msg) or re.search(r'%\s*(\d+)', msg)
        if m:
            pct = float(m.group(1))
            progress_bar.set_fraction(pct / 100.0)
            progress_bar.set_visible(True)
        elif any(x in msg.lower() for x in ["açılıyor", "extracting", "kuruluyor", "ayıklanıyor", "entpacken", "entpackt"]):
            m2 = re.search(r'(\d+)', msg)
            if m2:
                pct = float(m2.group(1))
                progress_bar.set_fraction(pct / 100.0)
                progress_bar.set_visible(True)
            else:
                progress_bar.pulse()
                progress_bar.set_visible(True)
        elif any(x in msg.lower() for x in ["ok", "hazır", "başarıyla", "ready", "error", "hata", "başarısız", "failed", "seçilmedi", "bereit", "erfolgreich", "fehler", "fehlgeschlagen"]) or not msg:
            progress_bar.set_fraction(0.0)
            progress_bar.set_visible(False)
        else:
            if any(x in msg.lower() for x in ["indir", "downlo", "bağlantı", "query", "arşiv", "herunter", "verbindung"]):
                progress_bar.pulse()
                progress_bar.set_visible(True)
            else:
                progress_bar.set_fraction(0.0)
                progress_bar.set_visible(False)

    def _set_status(self, msg: str, _style=None):
        GLib.idle_add(self._update_progress_helper, self.launch_status_lbl, self.launch_progress_bar, msg)
        if hasattr(self, "settings_proton_status_lbl") and hasattr(self, "settings_proton_progress_bar"):
            GLib.idle_add(self._update_progress_helper, self.settings_proton_status_lbl, self.settings_proton_progress_bar, msg)

    def _reset_play_button(self):
        self.play_btn.set_label(_t("btn_start_game"))
        self.play_btn.remove_css_class("stop-btn-glowing")
        self.play_btn.add_css_class("play-btn-glowing")
        self._game_stopping = False

    def _is_game_running(self) -> bool:
        game = self._game_procs.get("game")
        return bool(game and game.poll() is None)

    # ── GAME LAUNCH OR STOP ────────────────────────────────────────────────────
    def _on_launch_or_stop(self, _):
        if self._is_game_running():
            self._stop_running_game()
            return
        if self._game_stopping:
            return
        self._start_game()

    def _stop_running_game(self):
        game = self._game_procs.get("game")
        proxy = self._game_procs.get("proxy")
        proton = self._launch_proton or find_proton(self.cfg.get("login_method", "proxypass"))

        self._game_stopping = True
        self.play_btn.set_sensitive(False)
        self._set_status(_t("status_stopping"))

        def worker():
            stop_game(self._game_procs, proton=proton, proxy_proc=proxy)

            def done():
                self._game_procs = {}
                self._proxy_proc = None
                self._launch_proton = None
                self._reset_play_button()
                self.play_btn.set_sensitive(True)
                self._set_status(_t("status_ready"))
                self._refresh_all_states()
                return False

            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    def _start_game(self):
        exe = self.cfg.get("exe_path", "").strip()
        proton = find_proton(self.cfg.get("login_method", "proxypass"))

        if not exe or not os.path.isfile(exe):
            self._show_error(_t("err_title"), _t("err_game_not_found"))
            return
        if not proton:
            self._show_error(_t("err_proton_none"), _t("err_proton_msg"))
            return

        login_method = self.cfg.get("login_method", "proxypass")
        if login_method == "proxypass" and not auth_json_exists(exe):
            self._show_error(_t("err_title"), _t("label_auth_required", "Please sign in first!"))
            self._on_proxy_login(None)
            return

        os.makedirs(COMPAT_DATA, exist_ok=True)
        self._launch_proton = proton
        self._game_stopping = False
        self._game_procs = {"game": None, "proxy": None}

        with self._proxy_log_lock:
            self._proxy_log_buf.clear()

        GLib.idle_add(lambda: (
            self.play_btn.set_label(_t("btn_stop_game")) or
            self.play_btn.remove_css_class("play-btn-glowing") or
            self.play_btn.add_css_class("stop-btn-glowing") or
            False
        ))
        self._set_status(_t("status_launching"), "running")

        def on_proxy_line(line):
            with self._proxy_log_lock:
                self._proxy_log_buf.append(line)

        def on_started(game_proc, proxy_proc):
            def update():
                self._game_procs["game"] = game_proc
                self._game_procs["proxy"] = proxy_proc
                self._proxy_proc = proxy_proc
                self._refresh_all_states()
                return False
            GLib.idle_add(update)

        def on_finished():
            if self._game_stopping:
                return
            def update():
                self._game_procs = {}
                self._proxy_proc = None
                self._launch_proton = None
                self._reset_play_button()
                self._refresh_all_states()
                return False
            GLib.idle_add(update)

        self._game_procs = launch_game(
            proton=proton,
            exe=exe,
            mangohud_on=self._mangohud_on,
            on_status=self._set_status,
            on_proxy_line=on_proxy_line,
            on_started=on_started,
            on_finished=on_finished,
            login_method=self.cfg.get("login_method", "proxypass"),
        )
        GLib.timeout_add(2500, lambda: self._refresh_all_states() or False)

        # Injector autorun
        injector_path = (self.cfg.get("injector_path") or "").strip()
        autorun = bool(self.cfg.get("injector_autorun", False))
        if autorun and injector_path and os.path.isfile(injector_path):
            try:
                import subprocess
                subprocess.Popen([injector_path], cwd=os.path.dirname(injector_path))
            except Exception as e:
                self._set_status(_t("err_injector_start", error=e), "error")

    # ── WINE ACTIONS ───────────────────────────────────────────────────────────
    def _on_open_prefix(self, _):
        os.makedirs(COMPAT_DATA, exist_ok=True)
        try:
            import subprocess
            subprocess.Popen(["xdg-open", COMPAT_DATA])
            self._toast(_t("toast_prefix_opened"))
        except Exception as e:
            self._show_error(_t("err_title"), _t("err_folder_open", error=e))

    def _on_winecfg(self, _):
        import subprocess, os as _os
        from mc_launcher.config import SCRIPT_DIR as _SD
        proton = find_proton(self.cfg.get("login_method", "proxypass"))
        if not proton:
            self._show_error(_t("err_proton_none"), _t("err_proton_msg"))
            return
        _os.makedirs(COMPAT_DATA, exist_ok=True)
        steam_root = _os.path.expanduser("~/.steam/root")
        if not _os.path.isdir(steam_root):
            flatpak_steam = _os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/steam")
            if _os.path.isdir(flatpak_steam):
                steam_root = flatpak_steam
            else:
                flatpak_steam_alt = _os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam")
                if _os.path.isdir(flatpak_steam_alt):
                    steam_root = flatpak_steam_alt
                else:
                    steam_root = _SD
        env = _os.environ.copy()
        env.update({
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": steam_root,
            "STEAM_COMPAT_DATA_PATH": COMPAT_DATA,
        })
        def runner():
            try:
                GLib.idle_add(self._toast, _t("toast_winecfg_opening"))
                from mc_launcher.flatpak import wrap_flatpak_cmd
                cmd = wrap_flatpak_cmd([proton, "run", "winecfg"], env)
                proc = subprocess.Popen(cmd, env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait()
                GLib.idle_add(self._toast, _t("toast_winecfg_closed"))
            except Exception as e:
                self._show_error(_t("err_title"), _t("err_winecfg", error=e))
        threading.Thread(target=runner, daemon=True).start()

    def _on_auto_download(self, btn):
        btn.set_sensitive(False)
        self.settings_proton_file_btn.set_sensitive(False)
        self.settings_proton_folder_btn.set_sensitive(False)
        self._toast(_t("toast_proton_download_start"))
        def on_done(ok):
            GLib.idle_add(btn.set_sensitive, True)
            GLib.idle_add(self.settings_proton_file_btn.set_sensitive, True)
            GLib.idle_add(self.settings_proton_folder_btn.set_sensitive, True)
            GLib.idle_add(lambda: self._update_progress_helper(self.settings_proton_status_lbl, self.settings_proton_progress_bar, "") if hasattr(self, "settings_proton_status_lbl") else None)
            GLib.idle_add(self._refresh_all_states)
            if ok:
                self._toast(_t("toast_proton_download_ok"))
        download_proton(on_status=self._set_status, on_done=on_done, login_method=self.cfg.get("login_method", "proxypass"))

    def _on_manual_install(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_proton"))
        dlg.open(self, None, self._on_manual_chosen)

    def _on_manual_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if path:
            self.settings_proton_file_btn.set_sensitive(False)
            self.settings_proton_folder_btn.set_sensitive(False)
            self.settings_proton_dl_btn.set_sensitive(False)
            def on_done(ok):
                GLib.idle_add(self.settings_proton_file_btn.set_sensitive, True)
                GLib.idle_add(self.settings_proton_folder_btn.set_sensitive, True)
                GLib.idle_add(self.settings_proton_dl_btn.set_sensitive, True)
                GLib.idle_add(lambda: self._update_progress_helper(self.settings_proton_status_lbl, self.settings_proton_progress_bar, "") if hasattr(self, "settings_proton_status_lbl") else None)
                GLib.idle_add(self._refresh_all_states)
                if ok:
                    self._toast(_t("toast_proton_file_ok"))
            install_from_file(path, on_status=self._set_status, on_done=on_done, login_method=self.cfg.get("login_method", "proxypass"))

    def _on_manual_install_folder(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_proton"))
        dlg.select_folder(self, None, self._on_manual_folder_chosen)

    def _on_manual_folder_chosen(self, dlg, result):
        try:
            path = dlg.select_folder_finish(result).get_path()
        except Exception:
            return
        if path:
            self.settings_proton_file_btn.set_sensitive(False)
            self.settings_proton_folder_btn.set_sensitive(False)
            self.settings_proton_dl_btn.set_sensitive(False)
            def on_done(ok):
                GLib.idle_add(self.settings_proton_file_btn.set_sensitive, True)
                GLib.idle_add(self.settings_proton_folder_btn.set_sensitive, True)
                GLib.idle_add(self.settings_proton_dl_btn.set_sensitive, True)
                GLib.idle_add(lambda: self._update_progress_helper(self.settings_proton_status_lbl, self.settings_proton_progress_bar, "") if hasattr(self, "settings_proton_status_lbl") else None)
                GLib.idle_add(self._refresh_all_states)
                if ok:
                    self._toast(_t("toast_proton_file_ok"))
            install_from_folder(path, on_status=self._set_status, on_done=on_done, login_method=self.cfg.get("login_method", "proxypass"))

    # ── SETTINGS AND TOGGLES ───────────────────────────────────────────────────
    def _on_settings_exe_changed(self, entry):
        path = entry.get_text().strip()
        self.cfg["exe_path"] = path
        save_cfg(self.cfg)

    def _on_mangohud_toggle(self, switch, _):
        self._mangohud_on = switch.get_active()
        self._toast(_t("toast_mangohud_on") if self._mangohud_on else _t("toast_mangohud_off"))

    def _on_vsync_toggle(self, switch, _):
        if not os.path.isfile(options_txt_path()):
            self._show_error(_t("err_options_not_found"), _t("err_options_msg"))
            return
        val = "1" if switch.get_active() else "0"
        try:
            patch_options("gfx_vsync", val)
            self._toast(_t("toast_vsync_on") if val == "1" else _t("toast_vsync_off"))
        except Exception as e:
            self._show_error(_t("err_save_title"), str(e))

    def _on_fix_loading_freeze(self, _):
        if not os.path.isfile(options_txt_path()):
            self._show_error(_t("err_options_not_found"), _t("err_options_msg"))
            return
        try:
            patch_options("do_not_show_multiplayer_online_safety_warning", "1")
            self._toast(_t("status_fix_loading"))
        except Exception as e:
            self._show_error(_t("err_save_title"), str(e))

    # DLL Settings
    def _on_dll_entry_changed(self, entry):
        self.cfg["injector_path"] = entry.get_text().strip()
        save_cfg(self.cfg)

    def _on_browse_injector(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_injector"))
        dlg.open(self, None, self._on_injector_chosen)

    def _on_injector_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if path:
            self.settings_dll_entry.set_text(path)
            self.cfg["injector_path"] = path
            save_cfg(self.cfg)
            self._toast(_t("toast_injector_selected"))

    def _on_dll_toggle(self, switch, _):
        self.cfg["injector_autorun"] = switch.get_active()
        save_cfg(self.cfg)

    # ── SERVER DESTINATION DIALOG ──────────────────────────────────────────────
    def _on_dest_settings(self, _):
        exe = self.cfg.get("exe_path", "").strip()
        if not exe:
            self._show_error(_t("err_title"), _t("err_select_exe_first"))
            return
        def on_saved(host, port, ok):
            if ok:
                GLib.idle_add(self._refresh_all_states)
                self._toast(_t("toast_server_set", host=host, port=port))
        DestinationDialog(self, exe, on_saved=on_saved).present()

    # ── PROXYPASS ACTIONS ──────────────────────────────────────────────────────
    def _on_proxy_login(self, _):
        exe = self.cfg.get("exe_path", "").strip()
        login_method = self.cfg.get("login_method", "proxypass")
        if login_method == "ingame":
            ProxyTermWindow("", "", exe_path=exe, parent=self, on_done=self._refresh_all_states, login_method="ingame").present()
            return

        jar = find_proxypass(exe)
        if jar:
            ProxyTermWindow(jar, os.path.dirname(jar), exe_path=exe, parent=self, on_done=self._refresh_all_states).present()
        else:
            def worker():
                def thread_status(msg, style="running"):
                    GLib.idle_add(self._set_status, msg, style)
                GLib.idle_add(self.proxy_login_btn.set_sensitive, False)
                try:
                    downloaded_jar = ensure_proxypass(thread_status)
                    if downloaded_jar:
                        def launch_win():
                            ProxyTermWindow(downloaded_jar, os.path.dirname(downloaded_jar), exe_path=exe, parent=self, on_done=self._refresh_all_states).present()
                            self.proxy_login_btn.set_sensitive(True)
                        GLib.idle_add(launch_win)
                    else:
                        def show_err():
                            self._show_error(_t("err_title"), _t("status_jar_not_found"))
                            self.proxy_login_btn.set_sensitive(True)
                        GLib.idle_add(show_err)
                except Exception as e:
                    def handle_exc():
                        self._show_error(_t("err_title"), f"Error downloading ProxyPass: {e}")
                        self.proxy_login_btn.set_sensitive(True)
                    GLib.idle_add(handle_exc)
            threading.Thread(target=worker, daemon=True).start()

    def _on_show_proxy_log(self, _):
        from mc_launcher.ui.proxy_windows import ProxyLogWindow
        ProxyLogWindow(self._proxy_proc, parent=self).present()

    def _on_proxy_logout(self, _):
        exe = self.cfg.get("exe_path", "").strip()
        auth_path = auth_json_path(exe)
        if not os.path.isfile(auth_path):
            self._toast(_t("toast_session_already_closed"))
            return
        
        def confirm():
            dlg = Adw.AlertDialog(
                heading=_t("btn_logout"),
                body=_t("msg_logout_confirm", path=auth_path),
            )
            dlg.add_response("cancel", _t("btn_cancel"))
            dlg.add_response("delete", _t("btn_logout"))
            dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
            dlg.set_default_response("cancel")
            dlg.set_close_response("cancel")
            dlg.connect("response", self._on_logout_response)
            dlg.present(self)
            return False
        GLib.idle_add(confirm)

    def _on_logout_response(self, dlg, response_id):
        if response_id != "delete":
            return
        exe = self.cfg.get("exe_path", "").strip()
        auth_path = auth_json_path(exe)
        if self._proxy_proc and self._proxy_proc.poll() is None:
            self._proxy_proc.terminate()
            self._proxy_proc = None
        try:
            if os.path.isfile(auth_path):
                os.remove(auth_path)
            
            # Also clean up from proxypass directory if it was created there
            from mc_launcher.config import PROXYPASS_DIR
            proxypass_auth = os.path.join(PROXYPASS_DIR, "auth.json")
            if os.path.isfile(proxypass_auth):
                os.remove(proxypass_auth)
                
            self._toast(_t("toast_session_closed"))
        except Exception as e:
            self._show_error(_t("err_title"), _t("err_delete_failed", error=e))

        def clear_registry():
            proton = find_proton("ingame")
            if not proton:
                proton = find_proton("proxypass")
            if proton:
                from mc_launcher.game import build_env
                env = build_env()
                pfx = os.path.join(COMPAT_DATA, "pfx")
                env["WINEPREFIX"] = pfx
                cmd = [
                    proton, "run", "reg", "delete",
                    "HKCU\\Software\\Wine\\WineGDK",
                    "/v", "RefreshToken",
                    "/f"
                ]
                try:
                    from mc_launcher.flatpak import wrap_flatpak_cmd
                    cmd = wrap_flatpak_cmd(cmd, env)
                    subprocess.run(cmd, env=env, capture_output=True, timeout=10)
                except Exception as e:
                    print(f"[LOGOUT] Registry silme hatası: {e}")

        threading.Thread(target=clear_registry, daemon=True).start()
        GLib.idle_add(self._refresh_all_states)

    def _on_proxy_reset(self, _):
        # 1. Kill the current proxy process
        if self._proxy_proc:
            try:
                self._proxy_proc.kill()
            except Exception:
                pass
            self._proxy_proc = None

        # 2. Kill any orphaned ProxyPass.jar processes
        try:
            import subprocess
            from mc_launcher.flatpak import wrap_flatpak_cmd
            subprocess.run(wrap_flatpak_cmd(["pkill", "-9", "-f", "java.*mc-gdk-linux-launcher.*ProxyPass\\.jar"]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Launcher] Error killing ProxyPass: {e}")

        # 3. If the game is currently running, restart ProxyPass in the background
        is_game_running = bool(self._game_procs.get("game") and self._game_procs["game"].poll() is None)
        if is_game_running:
            self._set_status("ProxyPass yeniden başlatılıyor...", "running")
            
            def restart_worker():
                try:
                    import time
                    time.sleep(1) # wait a moment for the ports to free up
                    
                    exe = self.cfg.get("exe_path", "").strip()
                    from mc_launcher.proxypass import find_proxypass, ensure_proxypass
                    from mc_launcher.java_rt import ensure_java
                    
                    jar = find_proxypass(exe) or ensure_proxypass(self._set_status)
                    java_bin = ensure_java(self._set_status)
                    
                    if jar and java_bin:
                        print(f"[PROXY] Yeniden Başlatılıyor: {jar}")
                        # Ensure ProxyPass binds on 0.0.0.0:19132 (direct mode)
                        try:
                            from mc_launcher.proxypass import read_proxypass_config, write_proxypass_config
                            pp_settings = read_proxypass_config(exe)
                            changed = False
                            if pp_settings.get("proxy_host") != "0.0.0.0":
                                pp_settings["proxy_host"] = "0.0.0.0"
                                changed = True
                            if pp_settings.get("proxy_port") != "19132":
                                pp_settings["proxy_port"] = "19132"
                                changed = True
                            if changed:
                                write_proxypass_config(exe, pp_settings)
                                print("[PROXY] Config updated: proxy binding set to 0.0.0.0:19132")
                        except Exception as e:
                            print(f"[PROXY] Config rewrite error: {e}")

                        proxy_cmd = [
                            java_bin,
                            "-Djava.net.preferIPv4Stack=true",
                            "-XX:+IgnoreUnrecognizedVMOptions",
                            "--add-opens", "java.base/jdk.internal.misc=ALL-UNNAMED",
                            "--add-opens", "java.base/java.nio=ALL-UNNAMED",
                            "--add-opens", "java.base/java.lang=ALL-UNNAMED",
                            "--add-opens", "java.base/java.lang.reflect=ALL-UNNAMED",
                            "-Dio.netty.tryReflectionSetAccessible=true",
                            "-jar", jar
                        ]
                        from mc_launcher.flatpak import wrap_flatpak_cmd
                        proxy_cmd = wrap_flatpak_cmd(proxy_cmd, cwd=os.path.dirname(jar))
                        proxy_proc = subprocess.Popen(
                            proxy_cmd,
                            cwd=os.path.dirname(jar),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            start_new_session=True,
                        )
                        self._proxy_proc = proxy_proc
                        self._game_procs["proxy"] = proxy_proc
                        
                        def _read_proxy(proc):
                            try:
                                for raw in iter(proc.stdout.readline, b""):
                                    line = raw.decode(errors="replace")
                                    with self._proxy_log_lock:
                                        self._proxy_log_buf.append(line)
                            except Exception as e:
                                print(f"[PROXY] Log okuma hatası: {e}")
                            finally:
                                if proc.stdout:
                                    proc.stdout.close()

                        threading.Thread(target=_read_proxy, args=(proxy_proc,), daemon=True).start()
                        time.sleep(2)
                        
                        GLib.idle_add(self._toast, "ProxyPass başarıyla yeniden başlatıldı!")
                        GLib.idle_add(self._set_status, "Oyun çalışıyor...", "running")
                    else:
                        GLib.idle_add(self._toast, "ProxyPass yeniden başlatılamadı (Eksik bileşenler).")
                except Exception as ex:
                    print(f"[PROXY] Restart error: {ex}")
                    GLib.idle_add(self._toast, f"Yeniden başlatma hatası: {ex}")
            
            threading.Thread(target=restart_worker, daemon=True).start()
        else:
            self._toast("ProxyPass süreçleri temizlendi.")
        
        self._refresh_all_states()

    def _on_download_proxypass(self, btn):
        btn.set_sensitive(False)
        self._update_progress_helper(self.proxy_pp_status, self.proxy_pp_progress_bar, _t("progress_download_proxypass"))
        def worker():
            jar = ensure_proxypass(lambda msg, *_: GLib.idle_add(self._update_progress_helper, self.proxy_pp_status, self.proxy_pp_progress_bar, msg))
            def done():
                btn.set_sensitive(True)
                self._update_progress_helper(self.proxy_pp_status, self.proxy_pp_progress_bar, "")
                self._refresh_all_states()
                if jar:
                    self._toast(_t("toast_proxypass_download_ok"))
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    def _on_download_java(self, btn):
        btn.set_sensitive(False)
        self._update_progress_helper(self.proxy_java_status, self.proxy_java_progress_bar, _t("progress_download_java"))
        def worker():
            java = ensure_java(lambda msg, *_: GLib.idle_add(self._update_progress_helper, self.proxy_java_status, self.proxy_java_progress_bar, msg))
            def done():
                btn.set_sensitive(True)
                self._update_progress_helper(self.proxy_java_status, self.proxy_java_progress_bar, "")
                self._refresh_all_states()
                if java:
                    self._toast(_t("toast_java_download_ok"))
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    # ── ADVANCED PROXYPASS SETTINGS ACTIONS ────────────────────────────────────
    def _on_save_proxy_settings(self, _):
        exe = self.cfg.get("exe_path", "").strip()
        if not exe:
            self._show_error(_t("err_title"), _t("err_select_exe_first"))
            return
            
        try:
            max_c = int(self.proxy_max_clients_entry.get_text().strip() or "0")
        except ValueError:
            max_c = 0
            
        settings = {
            "proxy_host": self.proxy_bind_host_entry.get_text().strip() or "0.0.0.0",
            "proxy_port": self.proxy_bind_port_entry.get_text().strip() or "19132",
            "dest_host": self.proxy_dest_host_entry.get_text().strip() or "127.0.0.1",
            "dest_port": self.proxy_dest_port_entry.get_text().strip() or "19132",
            "online_mode": self.proxy_online_mode_switch.get_active(),
            "save_auth_details": self.proxy_save_auth_switch.get_active(),
            "broadcast_session": self.proxy_broadcast_switch.get_active(),
            "max_clients": max_c
        }
        
        ok = write_proxypass_config(exe, settings)
        if ok:
            self._toast(_t("toast_options_saved"))
            self._refresh_all_states()
        else:
            self._show_error(_t("err_title"), _t("status_config_not_found"))

    # ── ADDON & MAP STORE LOGIC ──────────────────────────────────────────────
    def _create_store_page(self):
        # ── 4. ADDON & MAP STORE PAGE ──
        store_clamp = Adw.Clamp()
        store_clamp.set_maximum_size(900)
        store_clamp.set_hexpand(True)
        store_clamp.set_vexpand(True)
        store_clamp.add_css_class("page-content")

        store_scroll = Gtk.ScrolledWindow()
        store_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        store_scroll.set_hexpand(True)
        store_scroll.set_vexpand(True)
        store_clamp.set_child(store_scroll)

        store_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        store_box.set_margin_top(24)
        store_box.set_margin_bottom(24)
        store_box.set_margin_start(24)
        store_box.set_margin_end(24)
        store_scroll.set_child(store_box)

        # Title & Subtitle
        self.store_page_title = Gtk.Label()
        self.store_page_title.add_css_class("page-title")
        self.store_page_title.set_halign(Gtk.Align.START)
        store_box.append(self.store_page_title)

        self.store_page_desc = Gtk.Label()
        self.store_page_desc.add_css_class("dim-label")
        self.store_page_desc.set_halign(Gtk.Align.START)
        self.store_page_desc.set_xalign(0.0)
        store_box.append(self.store_page_desc)

        # Installer Progress / Status bar at the top
        self.store_progress_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.store_progress_card.add_css_class("glass-card")
        self.store_progress_card.set_visible(False)
        self.store_progress_card.set_margin_top(12)
        self.store_progress_card.set_margin_bottom(4)
        
        self.store_progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        self.store_spinner = Gtk.Spinner()
        self.store_spinner.set_visible(False)
        self.store_progress_box.append(self.store_spinner)
        
        self.store_progress_lbl = Gtk.Label()
        self.store_progress_lbl.add_css_class("dim-label")
        self.store_progress_lbl.set_hexpand(True)
        self.store_progress_lbl.set_xalign(0.0)
        self.store_progress_box.append(self.store_progress_lbl)
        
        self.store_progress_card.append(self.store_progress_box)
        
        self.store_progress_bar = Gtk.ProgressBar()
        self.store_progress_bar.set_visible(False)
        self.store_progress_bar.set_margin_top(4)
        self.store_progress_card.append(self.store_progress_bar)
        
        store_box.append(self.store_progress_card)

        # Curated items preferences group (or glass-card)
        curated_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        curated_group.add_css_class("glass-card")
        
        self.store_curated_title = Gtk.Label()
        self.store_curated_title.add_css_class("glass-card-title")
        self.store_curated_title.set_halign(Gtk.Align.START)
        curated_group.append(self.store_curated_title)

        # Gtk.FlowBox for Grid of Items
        self.store_flowbox = Gtk.FlowBox()
        self.store_flowbox.set_valign(Gtk.Align.START)
        self.store_flowbox.set_max_children_per_line(3)
        self.store_flowbox.set_min_children_per_line(1)
        self.store_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.store_flowbox.set_column_spacing(16)
        self.store_flowbox.set_row_spacing(16)
        curated_group.append(self.store_flowbox)
        store_box.append(curated_group)

        # Custom Direct URL installer card
        custom_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        custom_card.add_css_class("glass-card")
        custom_card.set_margin_top(12)
        
        self.store_custom_title = Gtk.Label()
        self.store_custom_title.add_css_class("glass-card-title")
        self.store_custom_title.set_halign(Gtk.Align.START)
        custom_card.append(self.store_custom_title)
        
        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.store_custom_entry = Gtk.Entry()
        self.store_custom_entry.set_hexpand(True)
        self.store_custom_entry.connect("activate", self._on_custom_install_clicked)
        custom_box.append(self.store_custom_entry)
        
        self.store_browse_btn = Gtk.Button()
        self.store_browse_btn.set_icon_name("document-open-symbolic")
        self.store_browse_btn.set_tooltip_text(_t("btn_browse"))
        self.store_browse_btn.add_css_class("flat")
        self.store_browse_btn.connect("clicked", self._on_store_browse_clicked)
        custom_box.append(self.store_browse_btn)
        
        self.store_custom_btn = Gtk.Button()
        self.store_custom_btn.add_css_class("suggested-action")
        self.store_custom_btn.add_css_class("pill")
        self.store_custom_btn.connect("clicked", self._on_custom_install_clicked)
        custom_box.append(self.store_custom_btn)
        
        custom_card.append(custom_box)
        store_box.append(custom_card)

        # Library card for managing installed content
        library_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        library_card.add_css_class("glass-card")
        library_card.set_margin_top(12)
        
        library_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        self.store_library_title = Gtk.Label(label=_t("store_library_title"))
        self.store_library_title.add_css_class("glass-card-title")
        self.store_library_title.set_hexpand(True)
        self.store_library_title.set_halign(Gtk.Align.START)
        library_header.append(self.store_library_title)
        
        # Refresh button
        library_refresh_btn = Gtk.Button()
        library_refresh_btn.set_icon_name("view-refresh-symbolic")
        library_refresh_btn.add_css_class("flat")
        library_refresh_btn.connect("clicked", lambda _: self._refresh_store_library())
        library_header.append(library_refresh_btn)
        
        library_card.append(library_header)
        
        # Scroll area / ListBox for items
        self.store_library_listbox = Gtk.ListBox()
        self.store_library_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.store_library_listbox.add_css_class("boxed-list")
        
        library_card.append(self.store_library_listbox)
        store_box.append(library_card)

        # Add to stack
        self.content_stack.add_named(store_clamp, "store")
        
        # Populate the curated list
        self._populate_curated_store()
        # Populate the library list
        self._refresh_store_library()

    def _populate_curated_store(self):
        # Clear existing flowbox children
        while True:
            child = self.store_flowbox.get_child_at_index(0)
            if not child:
                break
            self.store_flowbox.remove(child)
            
        curated_items = [
            {
                "name": "SkyBlock Bedrock Map",
                "type": "world",
                "desc_key": "store_desc_skyblock",
                "url": "https://github.com/kirbycope/SkyBlock-Bedrock/raw/main/SkyBlock-Bedrock.mcworld",
                "icon": "input-gaming-symbolic"
            },
            {
                "name": "Attachables Resource Pack",
                "type": "resource_pack",
                "desc_key": "store_desc_attachables",
                "url": "https://github.com/Bedrock-OSS/bedrock-examples/releases/download/download/attachable-example.mcpack",
                "icon": "image-missing-symbolic"
            },
            {
                "name": "Server Teleport Helper",
                "type": "resource_pack",
                "desc_key": "store_desc_teleport",
                "url": "https://github.com/lZiMUl/MineCraft-Server-Teleport/releases/download/1.4.1/MineCraft.Server.Teleport.mcpack",
                "icon": "network-transmit-receive-symbolic"
            },
            {
                "name": "No Fog Resource Pack",
                "type": "resource_pack",
                "desc_key": "store_desc_nofog",
                "url": "https://github.com/Minecraft-Bedrock-Packs/no-fog-resource-pack/releases/download/v1.0.0/nofog.mcpack",
                "icon": "weather-clear-symbolic"
            },
            {
                "name": "Bedrock Technical Resource Pack",
                "type": "resource_pack",
                "desc_key": "store_desc_technical",
                "url": "https://github.com/RavinMaddHatter/Bedrock-Technical-Resource-Pack/releases/latest/download/Bedrock-Technical-Resource-Pack.mcpack",
                "icon": "applications-engineering-symbolic"
            },
            {
                "name": "One Chunk Bedrock",
                "type": "world",
                "desc_key": "store_desc_onechunk",
                "url": "https://github.com/kirbycope/one-chunk-bedrock/raw/main/one-chunk-bedrock.mcworld",
                "icon": "applications-games-symbolic"
            },
            {
                "name": "Void World Behavior Pack",
                "type": "behavior_pack",
                "desc_key": "store_desc_void",
                "url": "https://github.com/Minecraft-Bedrock-Packs/void-world-behavior-pack/releases/download/v1.0.0/void.mcpack",
                "icon": "weather-clear-night-symbolic"
            },
            {
                "name": "PvP Texture Pack",
                "type": "resource_pack",
                "desc_key": "store_desc_pvp",
                "url": "https://github.com/WaddleDeveloper7/PvPTexturePack/releases/latest/download/PvPTexturePack.mcpack",
                "icon": "applications-games-symbolic"
            },
            {
                "name": "HD PBR Resource Pack",
                "type": "resource_pack",
                "desc_key": "store_desc_hdpbr",
                "url": "https://github.com/jasonjgardner/jg-rtx/releases/latest/download/jg-rtx.mcpack",
                "icon": "applications-multimedia-symbolic"
            }
        ]
        
        for item in curated_items:
            # Build item card
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.add_css_class("store-card")
            card.set_size_request(240, 240)
            
            # Header box with Icon & Badge
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            icon = Gtk.Image.new_from_icon_name(item["icon"])
            icon.set_pixel_size(24)
            header.append(icon)
            
            badge_box = Gtk.Box()
            badge_box.add_css_class("badge")
            # Style badge based on type
            btype = item["type"]
            if btype == "world":
                badge_box.add_css_class("badge-world")
                badge_key = "store_badge_world"
            elif btype == "resource_pack":
                badge_box.add_css_class("badge-resource")
                badge_key = "store_badge_resource"
            else:
                badge_box.add_css_class("badge-behavior")
                badge_key = "store_badge_behavior"
                
            badge_lbl = Gtk.Label(label=_t(badge_key))
            badge_lbl.add_css_class("badge-text")
            badge_box.append(badge_lbl)
            header.append(badge_box)
            card.append(header)
            
            # Title
            title = Gtk.Label(label=item["name"])
            title.add_css_class("store-card-title")
            title.set_halign(Gtk.Align.START)
            title.set_wrap(True)
            card.append(title)
            
            # Description
            desc = Gtk.Label(label=_t(item["desc_key"]))
            desc.add_css_class("store-card-desc")
            desc.set_halign(Gtk.Align.START)
            desc.set_wrap(True)
            desc.set_vexpand(True)
            card.append(desc)
            
            # Install Button
            btn = Gtk.Button(label=_t("btn_install_mod"))
            btn.add_css_class("pill")
            btn.connect("clicked", lambda _btn, url=item["url"]: self._install_store_content(url))
            card.append(btn)
            
            self.store_flowbox.append(card)

    def _install_store_content(self, url: str):
        if getattr(self, "_store_installing", False):
            return
            
        self._store_installing = True
        self.store_progress_card.set_visible(True)
        self.store_spinner.set_visible(True)
        self.store_spinner.start()
        self.store_progress_box.set_visible(True)
        self.store_progress_bar.set_visible(True)
        self.store_progress_bar.set_fraction(0.0)
        self.store_progress_lbl.set_text(_t("status_installing_content"))
        
        def worker():
            success = False
            err_msg = ""
            try:
                def update_progress(msg):
                    GLib.idle_add(self._update_progress_helper, self.store_progress_lbl, self.store_progress_bar, msg)
                    
                success, err_msg = download_and_install_content(url, update_progress)
            except Exception as worker_exc:
                success = False
                err_msg = str(worker_exc)
            
            def done():
                self._store_installing = False
                self.store_spinner.stop()
                self.store_spinner.set_visible(False)
                self.store_progress_bar.set_visible(False)
                if success:
                    self._toast(_t("toast_install_ok"))
                    self.store_progress_lbl.set_text(_t("toast_install_ok"))
                    self._refresh_store_library()
                    GLib.timeout_add_seconds(5, lambda: (self.store_progress_card.set_visible(False)) or False)
                else:
                    self._show_error(_t("err_title"), f"{_t('toast_install_failed')}\n\nDetail: {err_msg}")
                    self.store_progress_lbl.set_text(f"{_t('toast_install_failed')}: {err_msg}")
            GLib.idle_add(done)
            
        threading.Thread(target=worker, daemon=True).start()

    def _on_custom_install_clicked(self, _):
        url = self.store_custom_entry.get_text().strip()
        if not url:
            return
        self.store_custom_entry.set_text("")
        self._install_store_content(url)

    def _on_store_browse_clicked(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title(_t("dlg_select_background"))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        
        f_mc = Gtk.FileFilter()
        f_mc.set_name("Minecraft Content (*.mcworld, *.mcpack, *.mcaddon, *.zip)")
        f_mc.add_pattern("*.mcworld")
        f_mc.add_pattern("*.mcpack")
        f_mc.add_pattern("*.mcaddon")
        f_mc.add_pattern("*.zip")
        filters.append(f_mc)
        
        dlg.set_filters(filters)
        dlg.open(self, None, self._on_store_file_chosen)

    def _on_store_file_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if not path:
            return
        
        # Dosya yolunu file:// URI olarak belirleyip doğrudan kuralım
        self.store_custom_entry.set_text("")
        self._install_store_content(f"file://{path}")

    def _refresh_store_library(self):
        # Clear existing items
        while True:
            row = self.store_library_listbox.get_row_at_index(0)
            if not row:
                break
            self.store_library_listbox.remove(row)
            
        items = list_installed_content()
        if not items:
            empty_lbl = Gtk.Label(label=_t("store_library_empty"))
            empty_lbl.add_css_class("dim-label")
            empty_lbl.set_margin_top(12)
            empty_lbl.set_margin_bottom(12)
            
            row = Gtk.ListBoxRow()
            row.set_child(empty_lbl)
            row.set_selectable(False)
            self.store_library_listbox.append(row)
            return
            
        for item in items:
            row = Gtk.ListBoxRow()
            row.set_selectable(False)
            
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(12)
            box.set_margin_end(12)
            
            # Icon based on type
            icon_name = "applications-games-symbolic"
            if item["type"] == "resource_pack":
                icon_name = "image-missing-symbolic"
            elif item["type"] == "behavior_pack":
                icon_name = "weather-clear-night-symbolic"
            elif item["type"] == "skin_pack":
                icon_name = "avatar-default-symbolic"
                
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(20)
            box.append(icon)
            
            # Text block (Name & Details)
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_box.set_hexpand(True)
            
            name_lbl = Gtk.Label(label=item["name"])
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.add_css_class("heading")
            text_box.append(name_lbl)
            
            # Badge text
            badge_key = f"store_badge_{item['type']}"
            badge_text = _t(badge_key)
            
            prefix_info = ""
            if "prefix" in item["path"]:
                prefix_info = " (Prefix)"
            elif "Steam" in item["path"]:
                prefix_info = " (Steam)"
                
            details_lbl = Gtk.Label(label=f"{badge_text}{prefix_info} • {item['folder_name']}")
            details_lbl.set_halign(Gtk.Align.START)
            details_lbl.add_css_class("dim-label")
            text_box.append(details_lbl)
            
            box.append(text_box)
            
            # Delete button
            del_btn = Gtk.Button()
            del_btn.set_icon_name("user-trash-symbolic")
            del_btn.add_css_class("destructive-action")
            del_btn.add_css_class("flat")
            del_btn.connect("clicked", lambda _btn, name=item["name"], path=item["path"]: self._delete_store_content_clicked(name, path))
            
            box.append(del_btn)
            row.set_child(box)
            self.store_library_listbox.append(row)

    def _delete_store_content_clicked(self, name: str, path: str):
        def on_response(dlg, response):
            if response == "yes":
                success = delete_installed_content(path)
                if success:
                    self._toast(_t("store_delete_ok"))
                    self._refresh_store_library()
                else:
                    self._show_error(_t("err_title"), _t("store_delete_failed", error="Access Denied"))
                    
        dlg = Adw.AlertDialog(
            heading=_t("store_delete_confirm_title"),
            body=_t("store_delete_confirm_msg", name=name)
        )
        dlg.add_response("no", _t("btn_cancel"))
        dlg.add_response("yes", _t("store_delete_confirm_title"))
        dlg.set_response_appearance("yes", Adw.ResponseAppearance.DESTRUCTIVE)
        
        dlg.connect("response", on_response)
        dlg.present(self)

    # Window close handler
    def _on_close(self, _):
        save_cfg(self.cfg)
        if self._is_game_running():
            game = self._game_procs.get("game")
            proxy = self._game_procs.get("proxy")
            
            def _stop_and_destroy():
                try:
                    stop_game(
                        self._game_procs,
                        proton=self._launch_proton or find_proton(self.cfg.get("login_method", "proxypass")),
                        proxy_proc=proxy
                    )
                except Exception as e:
                    print(f"[Launcher] stop_game error during close: {e}")
                finally:
                    GLib.idle_add(self.destroy)
            
            threading.Thread(target=_stop_and_destroy, daemon=True).start()
            return True  # Prevent default close, we will call destroy when done
            
        elif self._proxy_proc and self._proxy_proc.poll() is None:
            self._proxy_proc.terminate()
            
        return False

    def _on_destroy(self, _):
        if hasattr(self, "_css_provider"):
            try:
                Gtk.StyleContext.remove_provider_for_display(
                    Gdk.Display.get_default(),
                    self._css_provider
                )
            except Exception as e:
                print(f"[Launcher] CSS provider removal error: {e}")
