"""
mc_launcher/ui/main_window.py — LauncherWindow (Adw.ApplicationWindow)
"""

import os
import shutil
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Pango
from mc_launcher.i18n import _t, init_i18n, set_current_lang, get_current_lang

from mc_launcher.config import COMPAT_DATA, load_cfg, save_cfg
from mc_launcher.proton import find_proton, download_proton, install_from_file
from mc_launcher.proxypass import find_proxypass, auth_json_exists, read_destination, ensure_proxypass
from mc_launcher.game import launch_game, scan_for_exe, options_txt_path, patch_options, stop_game
from mc_launcher.java_rt import find_java, ensure_java
from mc_launcher.ui.proxy_windows import ProxyTermWindow
from mc_launcher.ui.dialogs import DestinationDialog, OptionsWindow


class LauncherWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Minecraft GDK Linux Launcher")
        self.set_default_size(980, 640)
        self.set_resizable(True)

        init_i18n()
        self.cfg              = load_cfg()
        self._language        = get_current_lang()
        self._proxy_proc      = None
        self._game_proc       = None
        self._game_procs      = {}          # {"game": proc, "proxy": proc}
        self._mangohud_on     = False
        self._proxy_log_buf   = []
        self._proxy_log_lock  = threading.Lock()

        # ── Toast overlay ────────────────────────────────────────────────────
        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        # ── ToolbarView ──────────────────────────────────────────────────────
        toolbar_view = Adw.ToolbarView()
        self._toast_overlay.set_child(toolbar_view)

        # ── HeaderBar ────────────────────────────────────────────────────────
        hb = Adw.HeaderBar()
        toolbar_view.add_top_bar(hb)

        # Sol üst: Ayarlar (dil seçimi)
        self.settings_btn = Gtk.MenuButton()
        self.settings_btn.set_icon_name("emblem-system-symbolic")
        self.settings_btn.set_tooltip_text(_t("menu_settings"))
        hb.pack_start(self.settings_btn)

        # Dil action'ı (win.language)
        code = self._language if self._language in ("tr", "en", "de") else "tr"
        self._lang_action = Gio.SimpleAction.new_stateful(
            "language",
            GLib.VariantType.new("s"),
            GLib.Variant("s", code),
        )
        self._lang_action.connect("change-state", self._on_language_action)
        self.add_action(self._lang_action)

        # ── Ana içerik: yatay launcher düzeni (sidebar + içerik) ─────────────
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toolbar_view.set_content(main_box)

        # Libadwaita sürüm uyumluluğu: Adw.ViewStackSidebar her sistemde yok.
        # Bu yüzden klasik Gtk.Stack + Gtk.StackSidebar kullanıyoruz.
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._stack.set_transition_duration(200)

        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(self._stack)
        sidebar.set_size_request(220, -1)
        sidebar.set_vexpand(True)
        main_box.append(sidebar)

        # Sağ taraf (sayfalar)
        stack_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        stack_wrap.set_hexpand(True)
        stack_wrap.set_vexpand(True)
        main_box.append(stack_wrap)

        stack_wrap.append(self._stack)

        self._stack_pages = {}

        def _page(title: str, icon: str):
            sc = Gtk.ScrolledWindow()
            sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sc.set_hexpand(True)
            sc.set_vexpand(True)
            clamp = Adw.Clamp()
            clamp.set_maximum_size(900)
            clamp.set_tightening_threshold(600)
            sc.set_child(clamp)
            page = Adw.PreferencesPage()
            clamp.set_child(page)
            name = title.lower().replace(" ", "_")
            stack_page = self._stack.add_titled(sc, name, title)
            # Gtk.StackPage icon desteği sürüme göre değişebilir.
            if hasattr(stack_page, "set_icon_name"):
                stack_page.set_icon_name(icon)
            self._stack_pages[name] = stack_page
            return page

        play_page = _page(_t("page_play"), "media-playback-start-symbolic")
        proxy_page = _page(_t("page_proxy"), "network-workgroup-symbolic")
        proton_page = _page(_t("page_proton"), "system-software-install-symbolic")
        tools_page = _page(_t("page_tools"), "preferences-system-symbolic")
        about_page = _page(_t("page_about"), "help-about-symbolic")

        # ── Oyna sayfası ────────────────────────────────────────────────────
        play_group = Adw.PreferencesGroup(title=_t("group_play"))
        play_page.add(play_group)
        self.play_group = play_group

        # Tam genişlik satır: Oyun EXE yolu
        exe_row = Adw.PreferencesRow()
        exe_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        exe_box.set_hexpand(True)
        exe_row.set_child(exe_box)
        self.exe_entry = Gtk.Entry()
        self.exe_entry.set_text(self.cfg.get("exe_path", ""))
        self.exe_entry.set_hexpand(True)
        self.exe_entry.set_placeholder_text(_t("ph_game_exe"))
        self.exe_entry.set_valign(Gtk.Align.CENTER)
        self.exe_entry.connect("changed", self._on_exe_changed)
        exe_box.append(self.exe_entry)

        browse_btn = Gtk.Button(label=_t("btn_select"))
        browse_btn.add_css_class("pill")
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.connect("clicked", self._on_browse_exe)
        exe_box.append(browse_btn)
        self.exe_browse_btn = browse_btn

        scan_btn = Gtk.Button(label=_t("btn_auto_find"))
        scan_btn.add_css_class("pill")
        scan_btn.set_valign(Gtk.Align.CENTER)
        scan_btn.set_tooltip_text(_t("tt_auto_find"))
        scan_btn.connect("clicked", self._on_scan_exe)
        self._scan_btn = scan_btn
        exe_box.append(scan_btn)
        play_group.add(exe_row)

        perf_group = Adw.PreferencesGroup(title=_t("group_perf"))
        play_page.add(perf_group)
        self.perf_group = perf_group
        self.mango_row = Adw.SwitchRow(
            title=_t("label_mangohud"),
            subtitle=_t("status_not_installed") if not shutil.which("mangohud") else _t("status_mangohud_off"),
        )
        if not shutil.which("mangohud"):
            self.mango_row.set_sensitive(False)
        self.mango_row.connect("notify::active", self._on_mangohud_toggle)
        perf_group.add(self.mango_row)

        # DLL injector (performans altında ayrı başlık)
        injector_group = Adw.PreferencesGroup(title=_t("group_dll"))
        play_page.add(injector_group)
        self.dll_group = injector_group

        injector_row = Adw.PreferencesRow()
        injector_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        injector_box.set_hexpand(True)
        injector_row.set_child(injector_box)
        self.injector_entry = Gtk.Entry()
        self.injector_entry.set_text(self.cfg.get("injector_path", ""))
        self.injector_entry.set_hexpand(True)
        self.injector_entry.set_placeholder_text(_t("ph_injector_exe"))
        self.injector_entry.set_valign(Gtk.Align.CENTER)
        self.injector_entry.connect("changed", self._on_injector_path_changed)
        injector_box.append(self.injector_entry)

        injector_btn = Gtk.Button(label=_t("btn_select"))
        injector_btn.add_css_class("pill")
        injector_btn.set_valign(Gtk.Align.CENTER)
        injector_btn.set_tooltip_text(_t("tt_browse_injector"))
        injector_btn.connect("clicked", self._on_browse_injector)
        injector_box.append(injector_btn)
        self.injector_browse_btn = injector_btn

        self.injector_switch = Gtk.Switch()
        self.injector_switch.set_valign(Gtk.Align.CENTER)
        self.injector_switch.set_tooltip_text(_t("tt_injector_switch"))
        self.injector_switch.set_active(bool(self.cfg.get("injector_autorun", False)))
        self._injector_switch_handler_id = self.injector_switch.connect(
            "notify::active", self._on_injector_toggle
        )
        injector_box.append(self.injector_switch)

        injector_group.add(injector_row)
        self._refresh_injector_controls()

        launch_group = Adw.PreferencesGroup()
        play_page.add(launch_group)
        self.launch_btn = Gtk.Button(label=_t("btn_start_game"))
        self.launch_btn.add_css_class("suggested-action")
        self.launch_btn.add_css_class("pill")
        self.launch_btn.set_hexpand(True)
        self.launch_btn.set_margin_top(8)
        self.launch_btn.set_margin_bottom(8)
        self.launch_btn.connect("clicked", self._on_launch_or_stop)
        launch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        launch_box.append(self.launch_btn)
        launch_group.add(launch_box)

        # ── ProxyPass sayfası ───────────────────────────────────────────────
        proxy_group = Adw.PreferencesGroup(title=_t("group_proxy"))
        proxy_page.add(proxy_group)
        self.proxy_group = proxy_group

        self.auth_row = Adw.ActionRow(title=_t("label_auth_status"))
        self.auth_val = Gtk.Label()
        self.auth_val.add_css_class("dim-label")
        self.auth_val.set_valign(Gtk.Align.CENTER)
        self.auth_row.add_suffix(self.auth_val)
        proxy_group.add(self.auth_row)

        self.dest_row = Adw.ActionRow(title=_t("label_dest_server"))
        self.dest_val = Gtk.Label()
        self.dest_val.add_css_class("dim-label")
        self.dest_val.set_valign(Gtk.Align.CENTER)
        self.dest_row.add_suffix(self.dest_val)
        proxy_group.add(self.dest_row)

        proxy_action_row = Adw.ActionRow(title=_t("label_actions"))
        proxy_btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        proxy_btns.set_valign(Gtk.Align.CENTER)

        self.login_btn = Gtk.Button(label=_t("btn_login"))
        self.login_btn.add_css_class("pill")
        self.login_btn.connect("clicked", self._on_proxy_login)
        proxy_btns.append(self.login_btn)

        self.logout_btn = Gtk.Button(label=_t("btn_logout"))
        self.logout_btn.add_css_class("destructive-action")
        self.logout_btn.add_css_class("pill")
        self.logout_btn.connect("clicked", self._on_proxy_logout)
        proxy_btns.append(self.logout_btn)

        self.dest_btn = Gtk.Button(label=_t("btn_set_dest"))
        self.dest_btn.add_css_class("pill")
        self.dest_btn.connect("clicked", self._on_dest_settings)
        proxy_btns.append(self.dest_btn)

        proxy_action_row.add_suffix(proxy_btns)
        proxy_group.add(proxy_action_row)

        # ProxyPass / Java bileşen durumu
        components_group = Adw.PreferencesGroup(title=_t("group_components"))
        proxy_page.add(components_group)
        self.components_group = components_group

        # ProxyPass satırı
        self.pp_row = Adw.ActionRow(title="ProxyPass")
        self.proxy_status_lbl = Gtk.Label()
        self.proxy_status_lbl.add_css_class("dim-label")
        self.proxy_status_lbl.set_valign(Gtk.Align.CENTER)
        self.pp_row.add_suffix(self.proxy_status_lbl)

        self.pp_btn = Gtk.Button(label=_t("btn_download"))
        self.pp_btn.add_css_class("pill")
        self.pp_btn.set_valign(Gtk.Align.CENTER)
        self.pp_btn.connect("clicked", self._on_download_proxypass)
        self.pp_row.add_suffix(self.pp_btn)
        components_group.add(self.pp_row)

        # Java satırı
        self.java_row = Adw.ActionRow(title="Java Runtime")
        self.java_status_lbl = Gtk.Label()
        self.java_status_lbl.add_css_class("dim-label")
        self.java_status_lbl.set_valign(Gtk.Align.CENTER)
        self.java_row.add_suffix(self.java_status_lbl)

        self.java_btn = Gtk.Button(label=_t("btn_download"))
        self.java_btn.add_css_class("pill")
        self.java_btn.set_valign(Gtk.Align.CENTER)
        self.java_btn.connect("clicked", self._on_download_java)
        self.java_row.add_suffix(self.java_btn)
        components_group.add(self.java_row)

        self._refresh_proxy_components()

        # Canlı ProxyPass logları
        logs_group = Adw.PreferencesGroup(title=_t("group_logs"))
        proxy_page.add(logs_group)
        self.logs_group = logs_group

        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        logs_group.add(log_box)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)
        log_scroll.set_hexpand(True)
        # Log alanını daha görünür ve rahat okunabilir yap.
        log_scroll.set_min_content_height(260)
        log_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        log_box.append(log_scroll)

        self.proxy_log_view = Gtk.TextView()
        self.proxy_log_view.set_editable(False)
        self.proxy_log_view.set_cursor_visible(False)
        self.proxy_log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.proxy_log_view.add_css_class("monospace")
        self.proxy_log_buf = self.proxy_log_view.get_buffer()
        log_scroll.set_child(self.proxy_log_view)

        self._refresh_proxy_labels()

        # ── GDK-Proton sayfası ──────────────────────────────────────────────
        proton_group = Adw.PreferencesGroup(title=_t("group_proton"))
        proton_page.add(proton_group)
        self.proton_group = proton_group

        self.proton_ver_row = Adw.ActionRow(title=_t("label_version"))
        self.proton_ver_lbl = Gtk.Label()
        self.proton_ver_lbl.add_css_class("dim-label")
        self.proton_ver_lbl.set_valign(Gtk.Align.CENTER)
        self.proton_ver_row.add_suffix(self.proton_ver_lbl)
        proton_group.add(self.proton_ver_row)

        self.install_row = Adw.ActionRow(title=_t("label_install"))
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_valign(Gtk.Align.CENTER)

        self.dl_btn = Gtk.Button(label=_t("btn_download"))
        self.dl_btn.add_css_class("suggested-action")
        self.dl_btn.add_css_class("pill")
        self.dl_btn.connect("clicked", self._on_auto_download)
        btn_box.append(self.dl_btn)

        self.manual_btn = Gtk.Button(label=_t("btn_install_file"))
        self.manual_btn.add_css_class("pill")
        self.manual_btn.connect("clicked", self._on_manual_install)
        btn_box.append(self.manual_btn)

        self.install_row.add_suffix(btn_box)
        proton_group.add(self.install_row)

        proton_tools = Adw.PreferencesGroup(title=_t("group_proton_tools"))
        proton_page.add(proton_tools)
        self.proton_tools_group = proton_tools

        self.prefix_row = Adw.ActionRow(title=_t("label_wine_prefix"))
        self.open_prefix_btn = Gtk.Button(label=_t("btn_open_folder"))
        self.open_prefix_btn.add_css_class("pill")
        self.open_prefix_btn.connect("clicked", self._on_open_prefix)
        self.prefix_row.add_suffix(self.open_prefix_btn)
        proton_tools.add(self.prefix_row)

        self.winecfg_row = Adw.ActionRow(title="winecfg")
        self.winecfg_btn = Gtk.Button(label=_t("btn_open"))
        self.winecfg_btn.add_css_class("pill")
        self.winecfg_btn.connect("clicked", self._on_winecfg)
        self.winecfg_row.add_suffix(self.winecfg_btn)
        proton_tools.add(self.winecfg_row)

        self._refresh_proton_label()

        # ── Araçlar sayfası ────────────────────────────────────────────────
        tools_group = Adw.PreferencesGroup(title=_t("group_tools_fast"))
        tools_page.add(tools_group)
        self.tools_group_fast = tools_group

        self.opt_row = Adw.ActionRow(title=_t("title_options"))
        self.opt_btn = Gtk.Button(label=_t("btn_open"))
        self.opt_btn.add_css_class("pill")
        self.opt_btn.connect("clicked", self._on_open_options_gui)
        self.opt_row.add_suffix(self.opt_btn)
        tools_group.add(self.opt_row)

        self.fix_row = Adw.ActionRow(title=_t("label_loading_fix"))
        self.fix_btn = Gtk.Button(label=_t("btn_apply"))
        self.fix_btn.add_css_class("pill")
        self.fix_btn.connect("clicked", self._on_fix_loading_freeze)
        self.fix_row.add_suffix(self.fix_btn)
        tools_group.add(self.fix_row)

        vs_row = Adw.ActionRow(title=_t("label_vsync"))
        self.vsync_switch = Gtk.Switch()
        self.vsync_switch.set_valign(Gtk.Align.CENTER)
        self._vsync_handler_id = self.vsync_switch.connect("notify::active", self._on_vsync_toggle)
        vs_row.add_suffix(self.vsync_switch)
        tools_group.add(vs_row)

        # Durum çubuğu (alt bar)
        self.status_lbl = Gtk.Label(label=_t("status_ready"))
        self.status_lbl.add_css_class("dim-label")
        self.status_lbl.set_margin_bottom(8)
        status_bar = Adw.ToolbarView()
        toolbar_view2 = Adw.ToolbarView()   # alt satır için
        bottom_bar = Adw.HeaderBar()
        bottom_bar.set_show_start_title_buttons(False)
        bottom_bar.set_show_end_title_buttons(False)
        bottom_bar.set_title_widget(self.status_lbl)
        toolbar_view.add_bottom_bar(bottom_bar)

        # ── Hakkında sayfası ────────────────────────────────────────────────
        about_group = Adw.PreferencesGroup()
        about_page.add(about_group)

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
        self.about_lbl = about_lbl
        about_lbl.set_halign(Gtk.Align.START)
        about_lbl.set_xalign(0.0)
        about_lbl.set_wrap(True)
        about_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        about_lbl.set_selectable(True)
        hero_box.append(about_lbl)

        about_group.add(hero_row)

        links_group = Adw.PreferencesGroup(title=_t("about_links"))
        about_page.add(links_group)
        self.about_links_group = links_group

        # GitHub
        gh_row = Adw.ActionRow(title=_t("about_github"))
        self.about_gh_btn = Gtk.Button(label=_t("btn_open"))
        self.about_gh_btn.add_css_class("pill")
        self.about_gh_btn.connect("clicked", lambda *_: self._open_uri("https://github.com/mdevlopm/mc-gdk-launcher-gui"))
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
        about_page.add(info_group)
        self.about_info_group = info_group

        ver_row = Adw.ActionRow(title=_t("about_version"), subtitle="1.0")
        info_group.add(ver_row)
        self.about_ver_row = ver_row

        # Klavye kısayolları
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>w"),
            Gtk.CallbackAction.new(lambda *_: self._on_open_prefix(None) or True)
        ))
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>m"),
            Gtk.CallbackAction.new(lambda *_:
                self.mango_row.set_active(not self.mango_row.get_active()) or True
                if self.mango_row.get_sensitive() else True)
        ))
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control>f"),
            Gtk.CallbackAction.new(lambda *_: self._on_fix_loading_freeze(None) or True)
        ))
        self.add_controller(ctrl)

        self.connect("close-request", self._on_close)

        # Başlangıçta seçili dile göre başlıkları güncelle
        self._build_settings_menu()
        self._apply_language()

    # ── Toast bildirimi ───────────────────────────────────────────────────────
    def _toast(self, msg: str):
        GLib.idle_add(lambda: self._toast_overlay.add_toast(Adw.Toast(title=msg)) or False)

    def _open_uri(self, uri: str):
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except Exception:
            # En kötü ihtimal: sessiz geç, UI çökmesin.
            pass

    def _apply_language(self):
        # Stack page başlıkları
        mapping = {
            "oyna": "page_play",
            "proxypass": "page_proxy",
            "gdk-proton": "page_proton",
            "araçlar": "page_tools",
            "hakkında": "page_about",
            "ayarlar": "page_settings",
        }
        for name, key in mapping.items():
            page = self._stack_pages.get(name)
            if page and hasattr(page, "set_title"):
                page.set_title(_t(key))

        # Grup başlıkları
        if hasattr(self, "play_group"):
            self.play_group.set_title(_t("group_play"))
        if hasattr(self, "perf_group"):
            self.perf_group.set_title(_t("group_perf"))
        if hasattr(self, "tools_group_fast"):
            self.tools_group_fast.set_title(_t("group_tools_fast"))
        if hasattr(self, "proxy_group"):
            self.proxy_group.set_title(_t("group_proxy"))
        if hasattr(self, "components_group"):
            self.components_group.set_title(_t("group_components"))
        if hasattr(self, "logs_group"):
            self.logs_group.set_title(_t("group_logs"))
        if hasattr(self, "proton_group"):
            self.proton_group.set_title(_t("group_proton"))
        if hasattr(self, "proton_tools_group"):
            self.proton_tools_group.set_title(_t("group_proton_tools"))
        if hasattr(self, "dll_group"):
            self.dll_group.set_title(_t("group_dll"))

        # Satır başlıkları
        if hasattr(self, "auth_row"): self.auth_row.set_title(_t("label_auth_status"))
        if hasattr(self, "dest_row"): self.dest_row.set_title(_t("label_dest_server"))
        if hasattr(self, "pp_row"):   self.pp_row.set_title("ProxyPass")
        if hasattr(self, "java_row"): self.java_row.set_title("Java Runtime")
        if hasattr(self, "proton_ver_row"): self.proton_ver_row.set_title(_t("label_version"))
        if hasattr(self, "install_row"):    self.install_row.set_title(_t("label_install"))
        if hasattr(self, "prefix_row"):     self.prefix_row.set_title(_t("label_wine_prefix"))
        if hasattr(self, "winecfg_row"):    self.winecfg_row.set_title("winecfg")
        if hasattr(self, "opt_row"):        self.opt_row.set_title(_t("title_options"))
        if hasattr(self, "fix_row"):        self.fix_row.set_title(_t("label_loading_fix"))
        
        # Switch satırları
        if hasattr(self, "mango_row"):
            self.mango_row.set_title(_t("label_mangohud"))
            sub = _t("status_not_installed") if not shutil.which("mangohud") else (_t("status_installed") if self._mangohud_on else _t("status_mangohud_off"))
            self.mango_row.set_subtitle(sub)

        # HeaderBar ayarlar menüsü
        if hasattr(self, "settings_btn"):
            self.settings_btn.set_tooltip_text(_t("menu_settings"))
            self._build_settings_menu()

        # Buton yazıları / placeholderlar
        if hasattr(self, "exe_browse_btn"):
            self.exe_browse_btn.set_label(_t("btn_select"))
        if hasattr(self, "_scan_btn") and self._scan_btn is not None:
            self._scan_btn.set_label(_t("btn_auto_find"))
            self._scan_btn.set_tooltip_text(_t("tt_auto_find"))
        if hasattr(self, "injector_browse_btn"):
            self.injector_browse_btn.set_label(_t("btn_select"))
            self.injector_browse_btn.set_tooltip_text(_t("tt_browse_injector"))
        if hasattr(self, "launch_btn"):
            is_running = bool(self._game_procs.get("game")) and self._game_procs["game"].poll() is None
            self.launch_btn.set_label(_t("btn_stop_game" if is_running else "btn_start_game"))
        if hasattr(self, "exe_entry"):
            self.exe_entry.set_placeholder_text(_t("ph_game_exe"))
        if hasattr(self, "injector_entry"):
            self.injector_entry.set_placeholder_text(_t("ph_injector_exe"))
        if hasattr(self, "login_btn"):  self.login_btn.set_label(_t("btn_login"))
        if hasattr(self, "logout_btn"): self.logout_btn.set_label(_t("btn_logout"))
        if hasattr(self, "dest_btn"):   self.dest_btn.set_label(_t("btn_set_dest"))
        if hasattr(self, "pp_btn"):     self.pp_btn.set_label(_t("btn_download"))
        if hasattr(self, "java_btn"):   self.java_btn.set_label(_t("btn_download"))
        if hasattr(self, "dl_btn"):     self.dl_btn.set_label(_t("btn_download"))
        if hasattr(self, "manual_btn"): self.manual_btn.set_label(_t("btn_install_file"))
        if hasattr(self, "open_prefix_btn"): self.open_prefix_btn.set_label(_t("btn_open_folder"))
        if hasattr(self, "winecfg_btn"):    self.winecfg_btn.set_label(_t("btn_open"))
        if hasattr(self, "opt_btn"):        self.opt_btn.set_label(_t("btn_open"))
        if hasattr(self, "fix_btn"):        self.fix_btn.set_label(_t("btn_apply"))

        # Switch tooltipler
        if hasattr(self, "injector_switch"):
            self.injector_switch.set_tooltip_text(_t("tt_injector_switch"))

        # Hakkında yazısı
        if hasattr(self, "about_lbl"):
            self.about_lbl.set_text(_t("msg_about"))
        if hasattr(self, "about_title_lbl"):
            self.about_title_lbl.set_text(_t("about_title"))
        if hasattr(self, "about_tagline_lbl"):
            self.about_tagline_lbl.set_text(_t("about_tagline"))
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

        # Diğer dinamik etiketleri de yenile
        self._refresh_proxy_labels()
        self._refresh_proton_label()
        if hasattr(self, "status_lbl"):
             self.status_lbl.set_text(_t("status_ready"))

    def _build_settings_menu(self):
        root = Gio.Menu()
        lang_menu = Gio.Menu()
        for c in ("tr", "en", "de"):
            item = Gio.MenuItem.new(_t(f"lang_{c}"), None)
            item.set_action_and_target_value("win.language", GLib.Variant("s", c))
            lang_menu.append_item(item)

        root.append_submenu(_t("menu_language"), lang_menu)
        self.settings_btn.set_menu_model(root)

    def _on_language_action(self, action, value):
        code = value.get_string() if value is not None else "tr"
        set_current_lang(code)
        action.set_state(GLib.Variant("s", code))
        self._language = code
        if isinstance(self.cfg, dict):
            self.cfg["language"] = code
            save_cfg(self.cfg)
        self._apply_language()

    # ── Durum çubuğu ─────────────────────────────────────────────────────────
    def _set_status(self, msg: str, _style=None):
        """Alttaki durum etiketini günceller."""
        def _u():
            self.status_lbl.set_text(msg)
            return False
        GLib.idle_add(_u)

    # ── Proton etiketi ────────────────────────────────────────────────────────
    def _refresh_proton_label(self):
        p = find_proton()
        if p:
            GLib.idle_add(lambda: self.proton_ver_lbl.set_text(
                os.path.basename(os.path.dirname(p))) or False)
        else:
            GLib.idle_add(lambda: self.proton_ver_lbl.set_text(_t("status_not_installed")) or False)

    # ── ProxyPass etiketleri ─────────────────────────────────────────────────
    def _refresh_proxy_labels(self):
        exe = self.exe_entry.get_text().strip()
        jar = find_proxypass(exe)
        has_auth   = auth_json_exists(exe)

        # Proxy sürecini her seferinde _game_procs'tan al; launch_game
        # arka planda bunu güncelliyor.
        proxy = self._game_procs.get("proxy")
        if proxy is not None and proxy.poll() is None:
            self._proxy_proc = proxy
            is_running = True
        else:
            is_running = False

        if not jar:
            self.auth_val.set_text(_t("status_jar_not_found"))
            self.login_btn.set_visible(True)
            self.login_btn.set_sensitive(False)
            self.logout_btn.set_visible(False)
        elif has_auth:
            self.auth_val.set_text(_t("status_auth_done"))
            self.login_btn.set_visible(False)
            self.logout_btn.set_visible(True)
        else:
            self.auth_val.set_text(_t("status_auth_none"))
            self.login_btn.set_visible(True)
            self.login_btn.set_sensitive(True)
            self.logout_btn.set_visible(False)

        if exe:
            host, port = read_destination(exe)
            if host:
                self.dest_val.set_text(f"{host}:{port}")
                self.dest_btn.set_sensitive(True)
            else:
                self.dest_val.set_text(_t("status_config_not_found"))
                self.dest_btn.set_sensitive(False)
        else:
            self.dest_val.set_text("—")
            self.dest_btn.set_sensitive(False)

        # Bileşen etiketlerini de güncelle
        self._refresh_proxy_components()

    def _refresh_proxy_components(self):
        # ProxyPass durumu
        pp_path = find_proxypass(self.exe_entry.get_text().strip())
        if pp_path:
            self.proxy_status_lbl.set_text(_t("status_installed"))
        else:
            self.proxy_status_lbl.set_text(_t("status_not_installed"))

        # Java durumu
        java_bin = find_java()
        if java_bin:
            self.java_status_lbl.set_text(_t("status_installed"))
        else:
            self.java_status_lbl.set_text(_t("status_not_installed"))

    def _on_exe_changed(self, _):
        self._refresh_proxy_labels()

    # ── Hata dialogu ─────────────────────────────────────────────────────────
    def _show_error(self, title: str, msg: str):
        def _s():
            dlg = Adw.AlertDialog(heading=title, body=msg)
            dlg.add_response("ok", _t("btn_close"))
            dlg.present(self)
            return False
        GLib.idle_add(_s)

    # ── Kurulum butonları ─────────────────────────────────────────────────────
    def _set_install_btns(self, sensitive: bool):
        GLib.idle_add(lambda: self.dl_btn.set_sensitive(sensitive) or False)
        GLib.idle_add(lambda: self.manual_btn.set_sensitive(sensitive) or False)

    # ── MangoHud ─────────────────────────────────────────────────────────────
    def _on_mangohud_toggle(self, row, _param=None):
        self._mangohud_on = row.get_active()
        subtitle = _t("status_installed") if self._mangohud_on else _t("status_mangohud_off")
        GLib.idle_add(lambda: row.set_subtitle(subtitle) or False)
        status = _t("status_mangohud_on") if self._mangohud_on else _t("status_mangohud_off")
        self._set_status(status)

    # ── Prefix aç ────────────────────────────────────────────────────────────
    def _on_open_prefix(self, _):
        os.makedirs(COMPAT_DATA, exist_ok=True)
        try:
            import subprocess
            subprocess.Popen(["xdg-open", COMPAT_DATA])
            self._set_status(_t("status_prefix_opened", path=COMPAT_DATA))
        except Exception as e:
            self._show_error(_t("err_title"), f"Klasör açılamadı:\n{e}")

    # ── Options.txt GUI ───────────────────────────────────────────────────────
    def _on_open_options_gui(self, _):
        path = options_txt_path()
        if not os.path.isfile(path):
            self._show_error(_t("err_options_not_found"), _t("err_options_msg"))
            return
        OptionsWindow(self, path).present()

    # ── VSync anahtarı ───────────────────────────────────────────────────────
    def _on_vsync_toggle(self, switch, _param=None):
        if not os.path.isfile(options_txt_path()):
            self._show_error(_t("err_options_not_found"), _t("err_options_msg"))
            # Dosya yoksa switch'i eski haline döndür (notify döngüsüne girmeden).
            handler_id = getattr(self, "_vsync_handler_id", None)
            def _revert():
                try:
                    if handler_id is not None:
                        switch.handler_block(handler_id)
                    switch.set_active(not switch.get_active())
                finally:
                    if handler_id is not None:
                        switch.handler_unblock(handler_id)
                return False
            GLib.idle_add(_revert)
            return
        val = "1" if switch.get_active() else "0"
        try:
            patch_options("gfx_vsync", val)
            state_txt = _t("status_vsync_on") if val == "1" else _t("status_vsync_off")
            self._set_status(state_txt)
            self._toast(state_txt)
        except Exception as e:
            self._show_error(_t("err_save_title"), str(e))

    # ── Yükleme donmasını düzelt ──────────────────────────────────────────────
    def _on_fix_loading_freeze(self, _):
        if not os.path.isfile(options_txt_path()):
            self._show_error(_t("err_options_not_found"), _t("err_options_msg"))
            return
        try:
            patch_options("do_not_show_multiplayer_online_safety_warning", "1")
            self._set_status(_t("status_fix_loading"))
            self._toast(_t("status_fix_loading"))
        except Exception as e:
            self._show_error(_t("err_save_title"), str(e))

    # ── winecfg ──────────────────────────────────────────────────────────────
    def _on_winecfg(self, _):
        import subprocess, os as _os
        from mc_launcher.config import SCRIPT_DIR as _SD
        proton = find_proton()
        if not proton:
            self._show_error(_t("err_proton_none"), _t("err_proton_msg"))
            return
        _os.makedirs(COMPAT_DATA, exist_ok=True)
        steam_root = _os.path.expanduser("~/.steam/root")
        if not _os.path.isdir(steam_root):
            steam_root = _SD
        env = _os.environ.copy()
        env.update({
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": steam_root,
            "STEAM_COMPAT_DATA_PATH"          : COMPAT_DATA,
        })
        def runner():
            try:
                self._set_status("winecfg açılıyor...", "running")
                proc = subprocess.Popen([proton, "run", "winecfg"], env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait()
                self._set_status("winecfg kapandı.")
            except Exception as e:
                self._set_status(f"winecfg hatası: {e}", "error")
        threading.Thread(target=runner, daemon=True).start()

    # ── ProxyPass ────────────────────────────────────────────────────────────
    def _kill_proxy(self):
        if self._proxy_proc and self._proxy_proc.poll() is None:
            self._proxy_proc.terminate()
            self._proxy_proc = None

    def _on_dest_settings(self, _):
        exe = self.exe_entry.get_text().strip()
        def on_saved(host, port, ok):
            if ok:
                GLib.idle_add(self._refresh_proxy_labels)
                self._set_status(f"Sunucu güncellendi: {host}:{port}")
                self._toast(f"Sunucu ayarlandı: {host}:{port}")
            else:
                self._set_status("config.yml yazılamadı.", "error")
        DestinationDialog(self, exe, on_saved=on_saved).present()

    def _on_proxy_login(self, _):
        exe = self.exe_entry.get_text().strip()
        # Mevcut jar'ı bul, yoksa indir.
        jar = find_proxypass(exe) or ensure_proxypass(self._set_status)
        if not jar:
            self._show_error(_t("err_title"), _t("status_jar_not_found"))
            return
        def after_login():
            GLib.idle_add(self._refresh_proxy_labels)
        ProxyTermWindow(jar, os.path.dirname(jar), parent=self, on_done=after_login).present()

    def _on_download_proxypass(self, _btn):
        def worker():
            jar = ensure_proxypass(self._set_status)
            GLib.idle_add(self._refresh_proxy_components)
            if jar:
                self._toast("ProxyPass indirildi ✓")
        threading.Thread(target=worker, daemon=True).start()

    def _on_download_java(self, _btn):
        def worker():
            java = ensure_java(self._set_status)
            GLib.idle_add(self._refresh_proxy_components)
            if java:
                self._toast("Java runtime indirildi ✓")
        threading.Thread(target=worker, daemon=True).start()

    def _on_proxy_logout(self, _):
        exe = self.exe_entry.get_text().strip()
        if not exe:
            return
        import os as _os
        auth_path = _os.path.join(_os.path.dirname(_os.path.dirname(exe)), "auth.json")
        if not _os.path.isfile(auth_path):
            self._set_status("auth.json zaten yok.")
            return
        def confirm():
            dlg = Adw.AlertDialog(
                heading=_t("btn_logout"),
                body=f"auth.json delete confirm\n\n{auth_path}",
            )
            # Re-keying body to use _t later if needed, for now just matching context
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
        exe = self.exe_entry.get_text().strip()
        import os as _os
        auth_path = _os.path.join(_os.path.dirname(_os.path.dirname(exe)), "auth.json")
        self._kill_proxy()
        try:
            _os.remove(auth_path)
            self._set_status("Oturum kapatıldı, auth.json silindi.")
            self._toast("Oturum kapatıldı ✓")
        except Exception as e:
            self._set_status(f"Silinemedi: {e}", "error")
        GLib.idle_add(self._refresh_proxy_labels)

    def _on_proxy_logs(self, _):
        if not self._proxy_proc or self._proxy_proc.poll() is not None:
            self._set_status("ProxyPass şu an çalışmıyor.", "error")
            GLib.idle_add(self._refresh_proxy_labels)
            return
        ProxyLogWindow(self._proxy_proc, parent=self).present()

    # ── GDK-Proton indir / kur ───────────────────────────────────────────────
    def _on_auto_download(self, _):
        self._set_install_btns(False)
        def on_done(ok):
            self._set_install_btns(True)
            GLib.idle_add(self._refresh_proton_label)
            if ok:
                self._toast(_t("btn_download") + " ✓")
        download_proton(on_status=self._set_status, on_done=on_done)

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
            def on_done(ok):
                self._set_install_btns(True)
                GLib.idle_add(self._refresh_proton_label)
                if ok:
                    self._toast(_t("btn_download") + " ✓")
            install_from_file(path, on_status=self._set_status, on_done=on_done)

    # ── EXE seç / tara ───────────────────────────────────────────────────────
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

    def _on_browse_injector(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_title("DLL injector çalıştırılabilir dosyayı seç")
        dlg.open(self, None, self._on_injector_chosen)

    def _on_injector_chosen(self, dlg, result):
        try:
            path = dlg.open_finish(result).get_path()
        except Exception:
            return
        if path:
            self.injector_entry.set_text(path)
            self.cfg["injector_path"] = path
            save_cfg(self.cfg)
            self._refresh_injector_controls()

    def _on_injector_toggle(self, switch, _param=None):
        # Dosya yolu geçerli değilse toggle etmeye izin verme.
        path = (self.injector_entry.get_text() or "").strip()
        if not path or not os.path.isfile(path):
            handler_id = getattr(self, "_injector_switch_handler_id", None)
            try:
                if handler_id is not None:
                    switch.handler_block(handler_id)
                switch.set_active(False)
            finally:
                if handler_id is not None:
                    switch.handler_unblock(handler_id)
            self.cfg["injector_autorun"] = False
            save_cfg(self.cfg)
            self._refresh_injector_controls()
            return

        self.cfg["injector_autorun"] = bool(switch.get_active())
        save_cfg(self.cfg)

    def _on_injector_path_changed(self, _entry):
        self.cfg["injector_path"] = self.injector_entry.get_text().strip()
        save_cfg(self.cfg)
        self._refresh_injector_controls()

    def _refresh_injector_controls(self):
        path = (self.injector_entry.get_text() or "").strip()
        ok = bool(path) and os.path.isfile(path)
        self.injector_switch.set_sensitive(ok)
        if not ok:
            # Geçersiz yol varken autorun açık kalmasın.
            handler_id = getattr(self, "_injector_switch_handler_id", None)
            try:
                if handler_id is not None:
                    self.injector_switch.handler_block(handler_id)
                self.injector_switch.set_active(False)
            finally:
                if handler_id is not None:
                    self.injector_switch.handler_unblock(handler_id)
            if self.cfg.get("injector_autorun"):
                self.cfg["injector_autorun"] = False
                save_cfg(self.cfg)

    def _on_scan_exe(self, btn):
        btn.set_sensitive(False)
        def on_done(found):
            btn.set_sensitive(True)
            if not found:
                self._show_error("Bulunamadı", "Sistemde Minecraft.Windows.exe bulunamadı.")
                self._set_status("Taramada oyun bulunamadı.")
                return
            # ProxyPass.jar içereni önceliklendir
            best = found[0]
            for exe in found:
                if find_proxypass(exe):
                    best = exe
                    break
            self.exe_entry.set_text(best)
            self.cfg["exe_path"] = best
            save_cfg(self.cfg)
            self._set_status("Oyun otomatik olarak bulundu ve kaydedildi ✓")
            self._toast("Oyun bulundu ✓")
            self._refresh_proxy_labels()
        scan_for_exe(on_done=on_done, on_status=self._set_status)

    # ── Oyunu başlat / durdur ────────────────────────────────────────────────
    def _on_launch_or_stop(self, _):
        game = self._game_procs.get("game")
        if game and game.poll() is None:
            stop_game(game)
            self._set_status("Oyun durduruluyor...")
        else:
            self._start_game()

    def _start_game(self):
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

        # Başlat butonunu değiştir
        GLib.idle_add(lambda: (
            self.launch_btn.set_label("Oyunu Durdur") or
            self.launch_btn.remove_css_class("suggested-action") or
            self.launch_btn.add_css_class("destructive-action") or
            False
        ))
        self._set_status("Başlatılıyor...", "running")

        def on_proxy_line(line):
            with self._proxy_log_lock:
                self._proxy_log_buf.append(line)
                if len(self._proxy_log_buf) > 2000:
                    self._proxy_log_buf.pop(0)
            # Canlı log görünümünü güncelle
            if hasattr(self, "proxy_log_buf") and self.proxy_log_buf is not None:
                def _u():
                    self.proxy_log_buf.set_text("".join(self._proxy_log_buf))
                    end = self.proxy_log_buf.get_end_iter()
                    self.proxy_log_view.scroll_to_iter(end, 0.0, False, 0.0, 0.0)
                    return False
                GLib.idle_add(_u)

        def on_finished():
            proxy = self._game_procs.get("proxy")
            if proxy and proxy.poll() is None:
                proxy.terminate()
            self._proxy_proc  = None
            self._game_procs  = {}
            GLib.idle_add(lambda: (
                self.launch_btn.set_label(_t("btn_start_game")) or
                self.launch_btn.remove_css_class("destructive-action") or
                self.launch_btn.add_css_class("suggested-action") or
                False
            ))
            GLib.idle_add(self._refresh_proxy_labels)

        self._proxy_log_buf  = []
        self._proxy_log_lock = threading.Lock()
        if hasattr(self, "proxy_log_buf"):
            self.proxy_log_buf.set_text("")

        result = launch_game(
            proton=proton,
            exe=exe,
            mangohud_on=self._mangohud_on,
            on_status=self._set_status,
            on_proxy_line=on_proxy_line,
            on_finished=on_finished,
        )
        self._game_procs = result
        self._proxy_proc = result.get("proxy")
        # Proxy başladıktan 2 sn sonra butonları yenile
        GLib.timeout_add(2500, lambda: self._refresh_proxy_labels() or False)

        # DLL injector'ü istenirse oyunla beraber çalıştır.
        injector_path = (self.cfg.get("injector_path") or "").strip()
        autorun = bool(self.cfg.get("injector_autorun", False))
        if autorun and injector_path and os.path.isfile(injector_path):
            try:
                import subprocess
                subprocess.Popen([injector_path], cwd=os.path.dirname(injector_path))
            except Exception as e:
                self._set_status(f"DLL injector başlatılamadı: {e}", "error")

    # ── Pencere kapat ────────────────────────────────────────────────────────
    def _on_close(self, _):
        self._kill_proxy()
        if hasattr(self, "cfg") and isinstance(self.cfg, dict):
            save_cfg(self.cfg)
        return False
