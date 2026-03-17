#!/usr/bin/env python3
"""
Minecraft GDK Launcher — Modüler / Libadwaita Sürüm
Giriş noktası
"""

import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw

from mc_launcher.ui.main_window import LauncherWindow

class LauncherApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.mc.gdk.launcher")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LauncherWindow(self)
        win.present()

if __name__ == "__main__":
    app = LauncherApp()
    sys.exit(app.run(sys.argv))
