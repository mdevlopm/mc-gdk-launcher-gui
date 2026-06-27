#!/usr/bin/env python3
"""
Minecraft GDK Launcher — Modüler / Libadwaita Sürüm
Giriş noktası
"""

import sys

import traceback

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw
    from mc_launcher.ui.main_window import LauncherWindow
except Exception as e:
    err_msg = f"Kritik Hata: Eksik bağımlılık veya yükleme sorunu.\n\n{traceback.format_exc()}"
    sys.stderr.write(err_msg + "\n")
    
    # Terminale bakmayan kullanıcılar için temel uyarı:
    import subprocess
    import shutil
    if shutil.which("zenity"):
        subprocess.run(["zenity", "--error", "--text", err_msg])
    elif shutil.which("kdialog"):
        subprocess.run(["kdialog", "--error", err_msg])
        
    sys.exit(1)

class LauncherApp(Adw.Application):
    def __init__(self):
        from gi.repository import GLib
        GLib.set_prgname("com.mc.gdk.launcher")
        super().__init__(application_id="com.mc.gdk.launcher")

    def do_activate(self):
        # KDE ve diğer masaüstü ortamlarında Adwaita uyarısını ve görünmeyen ikon sorununu çözer
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        
        import os
        from gi.repository import Gtk
        settings = Gtk.Settings.get_default()
        if settings:
            desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
            if "gnome" not in desktop:
                settings.set_property("gtk-icon-theme-name", "Adwaita")

        win = self.props.active_window
        if not win:
            win = LauncherWindow(self)
        win.present()

if __name__ == "__main__":
    app = LauncherApp()
    sys.exit(app.run(sys.argv))
