"""
mc_launcher/ui/dialogs.py
  - DestinationDialog : ProxyPass hedef sunucu ayarları
  - OptionsWindow     : Minecraft options.txt GUI editörü
"""

import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from mc_launcher.config import SERVER_LIST, load_cfg, save_cfg
from mc_launcher.proxypass import read_destination, write_destination
from mc_launcher.i18n import _t


# ──────────────────────────────────────────────────────────────────────────────
class DestinationDialog(Adw.Window):
    """ProxyPass config.yml hedef sunucu ayarları penceresi."""

    def __init__(self, parent, exe_path: str, on_saved=None):
        super().__init__(title=_t("title_dest_settings"))
        self.set_transient_for(parent)
        self.set_modal(True)
        # Biraz daha geniş ve yüksek, ferah bir pencere.
        self.set_default_size(520, 420)
        self.set_resizable(True)
        self.exe_path = exe_path
        self.on_saved = on_saved

        # Konfigürasyondan kullanıcı sunucularını yükle
        self._cfg = load_cfg()
        self._user_servers = list(self._cfg.get("servers", []))
        # Tüm sunucu listesi: varsayılanlar + kullanıcı ekledikleri
        self._all_servers = SERVER_LIST + self._user_servers

        host, port = read_destination(exe_path)
        self._custom_host = host
        self._custom_port = port or "19132"

        # ── Layout ──
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_margin_top(24); box.set_margin_bottom(24)
        box.set_margin_start(24); box.set_margin_end(24)
        toolbar_view.set_content(box)

        # ── Kayıtlı Sunucular grubu ──
        saved_group = Adw.PreferencesGroup(title=_t("label_server_profiles"))
        box.append(saved_group)

        self.server_combo = Adw.ComboRow(title=_t("label_server_list"))
        self._server_items = Gtk.StringList()
        self._rebuild_servers_model()

        # Mevcut host/port bir kayıtta varsa onu seç
        selected_idx = 0
        for i, srv in enumerate(self._all_servers, start=1):
            if srv["host"] == host and srv["port"] == port:
                selected_idx = i
                break
        self.server_combo.set_selected(selected_idx)
        self.server_combo.connect("notify::selected", self._on_server_selected)
        saved_group.add(self.server_combo)

        # Sunucu ekleme / düzenleme / silme satırı
        action_row = Adw.ActionRow(title=_t("label_server_profiles"))
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_btn.set_tooltip_text(_t("tt_add_profile"))
        add_btn.add_css_class("pill")
        add_btn.set_valign(Gtk.Align.CENTER)
        action_row.add_suffix(add_btn)

        edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        edit_btn.set_tooltip_text(_t("tt_edit_profile"))
        edit_btn.add_css_class("pill")
        edit_btn.set_valign(Gtk.Align.CENTER)
        action_row.add_suffix(edit_btn)

        del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        del_btn.set_tooltip_text(_t("tt_del_profile"))
        del_btn.add_css_class("pill")
        del_btn.set_valign(Gtk.Align.CENTER)
        action_row.add_suffix(del_btn)

        saved_group.add(action_row)

        add_btn.connect("clicked", self._on_add_server_clicked)
        edit_btn.connect("clicked", self._on_edit_server_clicked)
        del_btn.connect("clicked", self._on_delete_server_clicked)
        self._delete_btn = del_btn
        self._edit_btn = edit_btn

        # ── Butonlar ──
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        cancel = Gtk.Button(label=_t("btn_cancel"))
        cancel.connect("clicked", lambda _: self.close())
        btn_row.append(cancel)

        apply_btn = Gtk.Button(label=_t("btn_apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply)
        btn_row.append(apply_btn)

        # Başlangıçta buton durumlarını ayarla
        self._sync_action_buttons()

    def _on_apply(self, _):
        idx = self.server_combo.get_selected()
        if idx > 0:
            srv = self._all_servers[idx - 1]
            host, port = srv["host"], srv["port"]
        else:
            host, port = (self._custom_host or "").strip(), (self._custom_port or "").strip()
        if not host or not port:
            return
        ok = write_destination(self.exe_path, host, port)
        if self.on_saved:
            self.on_saved(host, port, ok)
        self.close()

    def _on_server_selected(self, combo, _param):
        self._sync_action_buttons()

    def _sync_action_buttons(self):
        idx = self.server_combo.get_selected()
        # Silme butonu sadece kullanıcı sunucuları için aktif olsun
        if hasattr(self, "_delete_btn"):
            self._delete_btn.set_sensitive(idx > len(SERVER_LIST))
        # Düzenleme: "Özel" dahil her zaman mümkün (özelde sadece hedefi düzenler)
        if hasattr(self, "_edit_btn"):
            self._edit_btn.set_sensitive(True)

    def _on_add_server_clicked(self, _btn):
        def _added(srv):
            self._add_user_server(srv)
        EditServerDialog(self, mode="add", on_done=_added).present()

    def _add_user_server(self, srv: dict):
        # Kullanıcı sunucu listesini güncelle ve kaydet
        servers = list(self._cfg.get("servers", []))
        updated = False
        for i, s in enumerate(servers):
            if s.get("host") == srv["host"] and s.get("port") == srv["port"]:
                servers[i] = srv
                updated = True
                break
        if not updated:
            servers.append(srv)
        self._cfg["servers"] = servers
        save_cfg(self._cfg)

        self._user_servers = servers
        self._all_servers = SERVER_LIST + self._user_servers

        # Modeli baştan oluştur ve yeni kaydı seç
        self._rebuild_servers_model()
        new_index = len(self._all_servers)  # 0 özel, 1..n sunucular
        self.server_combo.set_selected(new_index)
        self._sync_action_buttons()

    def _on_edit_server_clicked(self, _btn):
        idx = self.server_combo.get_selected()
        # 0: Özel — sadece hedefi düzenle
        if idx <= 0:
            def _done(srv):
                self._custom_host = srv["host"]
                self._custom_port = srv["port"]
            EditServerDialog(
                self,
                mode="custom",
                initial={"host": self._custom_host, "port": self._custom_port},
                on_done=_done,
            ).present()
            return

        # Varsayılanlar düzenlenemez; sadece kullanıcı sunucularını düzenle
        if idx <= len(SERVER_LIST):
            return
        user_idx = idx - len(SERVER_LIST) - 1
        if not (0 <= user_idx < len(self._user_servers)):
            return
        current = dict(self._user_servers[user_idx])

        def _done(srv):
            self._user_servers[user_idx] = srv
            self._cfg["servers"] = self._user_servers
            save_cfg(self._cfg)
            self._all_servers = SERVER_LIST + self._user_servers
            self._rebuild_servers_model()
            self.server_combo.set_selected(len(SERVER_LIST) + user_idx + 1)
            self._sync_action_buttons()

        EditServerDialog(self, mode="edit", initial=current, on_done=_done).present()

    def _on_delete_server_clicked(self, _btn):
        idx = self.server_combo.get_selected()
        # Varsayılanları (Localhost, Hive) koru; sadece kullanıcı sunucularını sil
        if idx <= len(SERVER_LIST) or idx <= 0:
            return
        user_idx = idx - len(SERVER_LIST) - 1  # _user_servers içindeki index
        if 0 <= user_idx < len(self._user_servers):
            del self._user_servers[user_idx]
        self._cfg["servers"] = self._user_servers
        save_cfg(self._cfg)
        self._all_servers = SERVER_LIST + self._user_servers
        self._rebuild_servers_model()
        self.server_combo.set_selected(0)
        if hasattr(self, "_delete_btn"):
            self._delete_btn.set_sensitive(False)
        self._sync_action_buttons()

    def _rebuild_servers_model(self):
        # 0. eleman özel (manuel)
        self._server_items.splice(0, self._server_items.get_n_items())
        self._server_items.append("— " + _t("title_custom_server") + " (" + _t("ph_search") +") —")
        for srv in self._all_servers:
            self._server_items.append(f"{srv['name']} ({srv['host']}:{srv['port']})")
        self.server_combo.set_model(self._server_items)


class EditServerDialog(Adw.Window):
    """Sunucu ekleme/düzenleme için küçük dialog."""

    def __init__(self, parent, mode: str, initial: dict | None = None, on_done=None):
        # mode: "add" | "edit" | "custom"
        title = _t("title_new_server") if mode == "add" else (_t("title_edit_server") if mode == "edit" else _t("title_custom_server"))
        super().__init__(title=title)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(360, -1)
        self.set_resizable(False)
        self._mode = mode
        self._on_done = on_done
        initial = initial or {}

        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(16); box.set_margin_end(16)
        toolbar_view.set_content(box)

        self.name_row = None
        if mode in ("add", "edit"):
            self.name_row = Adw.EntryRow(title=_t("label_server_name"))
            self.name_row.set_text(initial.get("name", ""))
            box.append(self.name_row)

        self.host_row = Adw.EntryRow(title=_t("label_server_addr"))
        self.host_row.set_text(initial.get("host", ""))
        box.append(self.host_row)

        self.port_row = Adw.EntryRow(title=_t("label_port"))
        self.port_row.set_text(initial.get("port", "") or "19132")
        box.append(self.port_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        cancel = Gtk.Button(label=_t("btn_cancel"))
        cancel.connect("clicked", lambda _: self.close())
        btn_row.append(cancel)

        ok_btn = Gtk.Button(label=_t("btn_save") if mode != "add" else _t("btn_add"))
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", self._on_ok)
        btn_row.append(ok_btn)

    def _on_ok(self, _):
        name = ""
        if self.name_row is not None:
            name = self.name_row.get_text().strip()
        host = self.host_row.get_text().strip()
        port = self.port_row.get_text().strip() or "19132"
        if (self._mode in ("add", "edit") and not name) or not host:
            return
        srv = {"host": host, "port": port}
        if self._mode in ("add", "edit"):
            srv["name"] = name
        if self._on_done:
            self._on_done(srv)
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
class OptionsWindow(Adw.Window):
    """Minecraft options.txt satırlarını GUI üzerinden düzenler."""

    def __init__(self, parent, options_path: str):
        super().__init__(title=_t("title_options"))
        self.set_default_size(520, 640)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.options_path = options_path
        self.entries: dict = {}
        self._rows: list[tuple[str, Adw.PreferencesRow]] = []

        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        toolbar_view.add_top_bar(header)

        # Üstte arama kutusu + altta scrollable PreferencesPage
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer_box.set_margin_top(6)
        outer_box.set_margin_bottom(6)
        outer_box.set_margin_start(6)
        outer_box.set_margin_end(6)
        toolbar_view.set_content(outer_box)

        # Libadwaita sürüm uyumluluğu: Adw.EntryRow bazı sürümlerde placeholder API'si yok.
        # Bu yüzden Gtk.SearchEntry kullanıyoruz.
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer_box.append(search_box)

        search_entry = Gtk.SearchEntry()
        search_entry.set_hexpand(True)
        search_entry.set_placeholder_text(_t("ph_search"))
        search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry = search_entry
        search_box.append(search_entry)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        outer_box.append(scroll)

        self.prefs_page = Adw.PreferencesPage()
        scroll.set_child(self.prefs_page)

        # Kaydet butonu HeaderBar'da
        save_btn = Gtk.Button(label=_t("btn_save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        self._load_options()

    def _load_options(self):
        if not os.path.exists(self.options_path):
            grp = Adw.PreferencesGroup()
            lbl = Gtk.Label(label=_t("err_options_not_found"))
            lbl.set_margin_top(20); lbl.set_margin_bottom(20)
            grp.add(lbl)
            self.prefs_page.add(grp)
            return

        try:
            with open(self.options_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            grp = Adw.PreferencesGroup(title="Minecraft " + _t("page_settings"))
            self.prefs_page.add(grp)

            for line in lines:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                key, val = line.split(":", 1)

                if val in ["0", "1"]:
                    row = Adw.SwitchRow(title=key)
                    row.set_active(val == "1")
                    self.entries[key] = row
                else:
                    row = Adw.EntryRow(title=key)
                    row.set_text(val)
                    self.entries[key] = row

                grp.add(row)
                self._rows.append((key, row))
        except Exception as e:
            grp = Adw.PreferencesGroup()
            grp.add(Gtk.Label(label=f"{_t('err_title')}: {e}"))
            self.prefs_page.add(grp)

    def _on_save(self, _):
        try:
            new_lines = []
            for key, widget in self.entries.items():
                if isinstance(widget, Adw.SwitchRow):
                    val = "1" if widget.get_active() else "0"
                else:
                    val = widget.get_text().strip()
                new_lines.append(f"{key}:{val}\n")
            with open(self.options_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            self.close()
        except Exception as e:
            dlg = Adw.AlertDialog(heading=_t("err_save_title"), body=str(e))
            dlg.add_response("ok", _t("btn_close"))
            dlg.present(self)

    def _on_search_changed(self, entry, *_args):
        text = entry.get_text().strip().lower()
        for key, row in self._rows:
            # Başlık veya mevcut değer içinde arama
            visible = True
            if text:
                value = ""
                if isinstance(row, Adw.EntryRow):
                    value = row.get_text().strip().lower()
                elif isinstance(row, Adw.SwitchRow):
                    value = "1" if row.get_active() else "0"
                visible = (text in key.lower()) or (text in value)
            row.set_visible(visible)
