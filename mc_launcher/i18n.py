"""
mc_launcher/i18n.py — Merkezi dil yönetimi
"""

from mc_launcher.config import load_cfg

# Dil sözlüğü
_STRINGS = {
    "tr": {
        # Yan Menü / Sayfalar
        "page_play": "Oyna",
        "page_proxy": "ProxyPass",
        "page_proton": "GDK-Proton",
        "page_tools": "Araçlar",
        "page_about": "Hakkında",
        "page_settings": "Ayarlar",

        # Gruplar
        "group_play": "Oyun Çalıştırılabilir Dosyası",
        "group_perf": "Performans",
        "group_tools_fast": "Hızlı Araçlar",
        "group_proxy": "ProxyPass",
        "group_components": "Bileşenler",
        "group_logs": "ProxyPass Logları",
        "group_proton": "GDK-Proton",
        "group_proton_tools": "Araçlar",
        "group_dll": "DLL Injector",

        # Butonlar / Etiketler
        "btn_select": "Seç",
        "btn_auto_find": "Otomatik Bul",
        "btn_start_game": "Oyunu Başlat",
        "btn_stop_game": "Oyunu Durdur",
        "btn_login": "Microsoft Girişi",
        "btn_logout": "Oturumu Kapat",
        "btn_set_dest": "Sunucu Ayarla",
        "btn_download": "İndir",
        "btn_install_file": "Dosyadan Kur",
        "btn_apply": "Uygula",
        "btn_save": "Kaydet",
        "btn_cancel": "İptal",
        "btn_open_folder": "Klasörü Aç",
        "btn_open": "Aç",
        "btn_clear": "Temizle",
        "btn_close": "Kapat",
        "btn_add": "Ekle",

        # Placeholderlar
        "ph_game_exe": "Minecraft.Windows.exe yolu...",
        "ph_injector_exe": "DLL injector çalıştırılabilir dosya yolu...",
        "ph_search": "Anahtar veya değer ara...",

        # Durumlar
        "status_ready": "Hazır.",
        "status_mangohud_on": "MangoHud aktif — oyun FPS sayacıyla başlayacak.",
        "status_mangohud_off": "MangoHud devre dışı.",
        "status_prefix_opened": "Klasör açıldı: {path}",
        "status_vsync_on": "VSync açıldı ✓",
        "status_vsync_off": "VSync kapatıldı ✓",
        "status_fix_loading": "Yükleme donması düzeltildi ✓",
        "status_installed": "Kurulu",
        "status_not_installed": "Kurulu değil",
        "status_auth_done": "Giriş yapıldı ✓",
        "status_auth_none": "Giriş yapılmadı",
        "status_jar_not_found": "ProxyPass.jar bulunamadı",
        "status_config_not_found": "config.yml bulunamadı",

        # Dialoglar / Pencereler
        "title_dest_settings": "Sunucu Ayarları",
        "title_options": "Oyun Seçenekleri (options.txt)",
        "title_proxy_login": "ProxyPass — Microsoft Girişi",
        "title_proxy_log": "ProxyPass — Canlı Log",
        "title_edit_server": "Sunucuyu Düzenle",
        "title_new_server": "Yeni Sunucu",
        "title_custom_server": "Özel Sunucu",
        "label_proxy_output": "ProxyPass çıktısı",
        "label_proxy_live": "ProxyPass çıktısı (canlı)",
        "label_server_list": "Sunucu Listesi",
        "label_server_profiles": "Sunucu Profilleri",
        "label_server_name": "Sunucu Adı",
        "label_server_addr": "Sunucu Adresi",
        "label_port": "Port",
        "label_auth_status": "Giriş Durumu",
        "label_dest_server": "Hedef Sunucu",
        "label_actions": "İşlemler",
        "label_version": "Sürüm",
        "label_install": "Kurulum",
        "label_wine_prefix": "Wine Prefix",
        "label_vsync": "VSync",
        "label_mangohud": "MangoHud FPS Sayacı",
        "label_loading_fix": "Yükleme Donmasını Düzelt",

        # Tooltipler
        "tt_auto_find": "Diskleri tarayarak oyunu otomatik bulur",
        "tt_browse_injector": "DLL injector EXE dosyasını seç",
        "tt_injector_switch": "Açıksa oyunla beraber çalıştırılır",
        "tt_add_profile": "Yeni sunucu profili ekle",
        "tt_edit_profile": "Seçili sunucuyu düzenle",
        "tt_del_profile": "Seçili kullanıcı sunucusunu sil",

        # Hatalar / Mesajlar
        "err_title": "Hata",
        "err_save_title": "Kaydetme Hatası",
        "err_options_not_found": "options.txt bulunamadı",
        "err_options_msg": "Oyunu en az bir kez başlatıp kapattıktan sonra tekrar deneyin.",
        "err_proton_none": "GDK-Proton yok",
        "err_proton_msg": "Önce GDK-Proton'u indirin.",
        "msg_about": (
            "Bu launcher, Minecraft Bedrock'u GDK-Proton ile Linux üzerinde çalıştırmayı "
            "kolaylaştırmak için tasarlanmış modüler bir arayüz sağlar.\n\n"
            "Özellikler:\n"
            "- Oyun dosyası seçme ve otomatik tarama\n"
            "- GDK-Proton indir/kur ve Wine araçları\n"
            "- ProxyPass ile Microsoft girişi ve hedef sunucu ayarları\n"
            "- options.txt için pratik araçlar"
        ),
        "about_title": "Minecraft GDK Launcher",
        "about_tagline": "Linux • GTK4 • Libadwaita",
        "about_links": "Bağlantılar",
        "about_info": "Bilgi",
        "about_github": "GitHub",
        "about_discord": "Discord",
        "about_version": "Sürüm",

        # Diller
        "lang_tr": "Türkçe",
        "lang_en": "English",
        "lang_de": "Deutsch",
        "menu_language": "Dil",
        "menu_settings": "Ayarlar",
    },
    "en": {
        "page_play": "Play",
        "page_proxy": "ProxyPass",
        "page_proton": "GDK-Proton",
        "page_tools": "Tools",
        "page_about": "About",
        "page_settings": "Settings",

        "group_play": "Game Executable",
        "group_perf": "Performance",
        "group_tools_fast": "Quick Tools",
        "group_proxy": "ProxyPass",
        "group_components": "Components",
        "group_logs": "ProxyPass Logs",
        "group_proton": "GDK-Proton",
        "group_proton_tools": "Tools",
        "group_dll": "DLL Injector",

        "btn_select": "Browse",
        "btn_auto_find": "Auto Find",
        "btn_start_game": "Launch Game",
        "btn_stop_game": "Stop Game",
        "btn_login": "Microsoft Login",
        "btn_logout": "Logout",
        "btn_set_dest": "Set Server",
        "btn_download": "Download",
        "btn_install_file": "Install from File",
        "btn_apply": "Apply",
        "btn_save": "Save",
        "btn_cancel": "Cancel",
        "btn_open_folder": "Open Folder",
        "btn_open": "Open",
        "btn_clear": "Clear",
        "btn_close": "Close",
        "btn_add": "Add",

        "ph_game_exe": "Path to Minecraft.Windows.exe...",
        "ph_injector_exe": "Path to DLL injector executable...",
        "ph_search": "Search key or value...",

        "status_ready": "Ready.",
        "status_mangohud_on": "MangoHud enabled — game will start with FPS counter.",
        "status_mangohud_off": "MangoHud disabled.",
        "status_prefix_opened": "Folder opened: {path}",
        "status_vsync_on": "VSync enabled ✓",
        "status_vsync_off": "VSync disabled ✓",
        "status_fix_loading": "Loading freeze fixed ✓",
        "status_installed": "Installed",
        "status_not_installed": "Not installed",
        "status_auth_done": "Logged in ✓",
        "status_auth_none": "Not logged in",
        "status_jar_not_found": "ProxyPass.jar not found",
        "status_config_not_found": "config.yml not found",

        "title_dest_settings": "Server Settings",
        "title_options": "Game Options (options.txt)",
        "title_proxy_login": "ProxyPass — Microsoft Login",
        "title_proxy_log": "ProxyPass — Live Log",
        "title_edit_server": "Edit Server",
        "title_new_server": "New Server",
        "title_custom_server": "Custom Server",
        "label_proxy_output": "ProxyPass output",
        "label_proxy_live": "ProxyPass output (live)",
        "label_server_list": "Server List",
        "label_server_profiles": "Server Profiles",
        "label_server_name": "Server Name",
        "label_server_addr": "Server Address",
        "label_port": "Port",
        "label_auth_status": "Auth Status",
        "label_dest_server": "Destination Server",
        "label_actions": "Actions",
        "label_version": "Version",
        "label_install": "Installation",
        "label_wine_prefix": "Wine Prefix",
        "label_vsync": "VSync",
        "label_mangohud": "MangoHud FPS Counter",
        "label_loading_fix": "Fix Loading Freeze",

        "tt_auto_find": "Scans disks to automatically find the game",
        "tt_browse_injector": "Select DLL injector EXE file",
        "tt_injector_switch": "If enabled, runs with the game",
        "tt_add_profile": "Add new server profile",
        "tt_edit_profile": "Edit selected server",
        "tt_del_profile": "Delete selected user server",

        "err_title": "Error",
        "err_save_title": "Save Error",
        "err_options_not_found": "options.txt not found",
        "err_options_msg": "Try again after launching and closing the game at least once.",
        "err_proton_none": "GDK-Proton missing",
        "err_proton_msg": "Download GDK-Proton first.",
        "msg_about": (
            "This launcher provides a modular interface designed to facilitate "
            "running Minecraft Bedrock on Linux with GDK-Proton.\n\n"
            "Features:\n"
            "- Game file selection and automatic scanning\n"
            "- GDK-Proton download/install and Wine tools\n"
            "- Microsoft login and destination server settings with ProxyPass\n"
            "- Handy tools for options.txt"
        ),
        "about_title": "Minecraft GDK Launcher",
        "about_tagline": "Linux • GTK4 • Libadwaita",
        "about_links": "Links",
        "about_info": "Info",
        "about_github": "GitHub",
        "about_discord": "Discord",
        "about_version": "Version",

        "lang_tr": "Türkçe",
        "lang_en": "English",
        "lang_de": "Deutsch",
        "menu_language": "Language",
        "menu_settings": "Settings",
    },
    "de": {
        "page_play": "Spielen",
        "page_proxy": "ProxyPass",
        "page_proton": "GDK-Proton",
        "page_tools": "Werkzeuge",
        "page_about": "Über",
        "page_settings": "Einstellungen",

        "group_play": "Spielbare Datei",
        "group_perf": "Leistung",
        "group_tools_fast": "Schnelle Werkzeuge",
        "group_proxy": "ProxyPass",
        "group_components": "Komponenten",
        "group_logs": "ProxyPass-Protokolle",
        "group_proton": "GDK-Proton",
        "group_proton_tools": "Werkzeuge",
        "group_dll": "DLL-Injector",

        "btn_select": "Auswählen",
        "btn_auto_find": "Automatisch finden",
        "btn_start_game": "Spiel starten",
        "btn_stop_game": "Spiel beenden",
        "btn_login": "Microsoft-Anmeldung",
        "btn_logout": "Abmelden",
        "btn_set_dest": "Server einstellen",
        "btn_download": "Herunterladen",
        "btn_install_file": "Aus Datei installieren",
        "btn_apply": "Anwenden",
        "btn_save": "Speichern",
        "btn_cancel": "Abbrechen",
        "btn_open_folder": "Ordner öffnen",
        "btn_open": "Öffnen",
        "btn_clear": "Löschen",
        "btn_close": "Schließen",
        "btn_add": "Hinzufügen",

        "ph_game_exe": "Pfad zu Minecraft.Windows.exe...",
        "ph_injector_exe": "Pfad zur DLL-Injector-Bestandteil...",
        "ph_search": "Schlüssel veya Wert suchen...",

        "status_ready": "Bereit.",
        "status_mangohud_on": "MangoHud aktiviert — Spiel startet mit FPS-Zähler.",
        "status_mangohud_off": "MangoHud deaktiviert.",
        "status_prefix_opened": "Ordner geöffnet: {path}",
        "status_vsync_on": "VSync aktiviert ✓",
        "status_vsync_off": "VSync deaktiviert ✓",
        "status_fix_loading": "Ladefehler behoben ✓",
        "status_installed": "Installiert",
        "status_not_installed": "Nicht installiert",
        "status_auth_done": "Angemeldet ✓",
        "status_auth_none": "Nicht angemeldet",
        "status_jar_not_found": "ProxyPass.jar nicht gefunden",
        "status_config_not_found": "config.yml nicht gefunden",

        "title_dest_settings": "Server-Einstellungen",
        "title_options": "Spieloptionen (options.txt)",
        "title_proxy_login": "ProxyPass — Microsoft-Anmeldung",
        "title_proxy_log": "ProxyPass — Live-Protokoll",
        "title_edit_server": "Server bearbeiten",
        "title_new_server": "Neuer Server",
        "title_custom_server": "Benutzerdefinierter Server",
        "label_proxy_output": "ProxyPass-Ausgabe",
        "label_proxy_live": "ProxyPass-Ausgabe (live)",
        "label_server_list": "Serverliste",
        "label_server_profiles": "Serverprofile",
        "label_server_name": "Servername",
        "label_server_addr": "Serveradresse",
        "label_port": "Port",
        "label_auth_status": "Anmeldestatus",
        "label_dest_server": "Zielserver",
        "label_actions": "Aktionen",
        "label_version": "Version",
        "label_install": "Installation",
        "label_wine_prefix": "Wine-Prefix",
        "label_vsync": "VSync",
        "label_mangohud": "MangoHud FPS-Zähler",
        "label_loading_fix": "Ladefehler beheben",

        "tt_auto_find": "Durchsucht Festplatten, um das Spiel automatisch zu finden",
        "tt_browse_injector": "DLL-Injector-EXE auswählen",
        "tt_injector_switch": "Falls aktiviert, wird es mit dem Spiel gestartet",
        "tt_add_profile": "Neues Serverprofil hinzufügen",
        "tt_edit_profile": "Ausgewählten Server bearbeiten",
        "tt_del_profile": "Ausgewählten Benutzerserver löschen",

        "err_title": "Fehler",
        "err_save_title": "Speicherfehler",
        "err_options_not_found": "options.txt nicht gefunden",
        "err_options_msg": "Versuchen Sie es erneut, nachdem Sie das Spiel mindestens einmal gestartet und geschlossen haben.",
        "err_proton_none": "GDK-Proton fehlt",
        "err_proton_msg": "Laden Sie zuerst GDK-Proton herunter.",
        "msg_about": (
            "Dieser Launcher bietet eine modularer Oberfläche, die das Ausführen von "
            "Minecraft Bedrock auf Linux mit GDK-Proton erleichtert.\n\n"
            "Funktionen:\n"
            "- Spielseitenauswahl und automatischer Scan\n"
            "- GDK-Proton Download/Installation und Wine-Werkzeuge\n"
            "- Microsoft-Anmeldung und Zielservereinstellungen mit ProxyPass\n"
            "- Praktische Werkzeuge für options.txt"
        ),
        "about_title": "Minecraft GDK Launcher",
        "about_tagline": "Linux • GTK4 • Libadwaita",
        "about_links": "Links",
        "about_info": "Info",
        "about_github": "GitHub",
        "about_discord": "Discord",
        "about_version": "Version",

        "lang_tr": "Türkçe",
        "lang_en": "English",
        "lang_de": "Deutsch",
        "menu_language": "Sprache",
        "menu_settings": "Einstellungen",
    }
}

_current_lang = "tr"

def init_i18n():
    global _current_lang
    cfg = load_cfg()
    _current_lang = cfg.get("language", "tr")

def get_current_lang():
    return _current_lang

def set_current_lang(code):
    global _current_lang
    if code in _STRINGS:
        _current_lang = code

def _t(key, **kwargs):
    """
    Belirtilen anahtar için çeviriyi döner.
    Eğer anahtar belirtilen dilde yoksa Türkçe'ye, o da yoksa anahtarın kendisine döner.
    """
    lang = _current_lang
    text = _STRINGS.get(lang, {}).get(key)
    if text is None:
        text = _STRINGS.get("tr", {}).get(key, key)
    
    if kwargs:
        return text.format(**kwargs)
    return text
