# 🎮 Minecraft Bedrock Linux (GDK) Launcher

A standalone launcher designed to run the Minecraft Bedrock (GDK) edition on Linux, built with GTK4 and Libadwaita for a premium, modern interface.
This launcher manages GDK-Proton tooling and advanced authentication mechanisms required to run the game's Microsoft GDK compatibility layer on Linux.

## ✨ Key Features

- **Modern & Premium Design:** Fully compliant with GNOME design guidelines and Libadwaita standards, featuring system-theme-aware dark mode and glassmorphic card design.
- **Dynamic Dual Login Mode:**
  - 🌐 **ProxyPass Method:** Uses a local proxy server to route Microsoft authentication traffic. When this mode is selected, the launcher automatically restores game files to vanilla state, cleans up extra DLL patches, and resets Wine MSA registry entries. Uses the standard GDK-Proton build.
  - 🎮 **In-Game Login Method:** Automatically installs and integrates the patched `xuser` GDK-Proton build and the custom DLL hooks (`XCurl.dll`, `libHttpClient.GDK.dll`) required for in-game authentication to work.
- **Automatic Dependency Management:**
  - Download and install compatible GDK-Proton versions directly from within the launcher.
  - Automatically detect and download the Java Runtime required for ProxyPass.
- **Integrated Store:** Download and install custom archive resource packs, mods, and skins to the game with a single click.
- **options.txt Editor:** Search and edit in-game settings directly from the UI, without closing the launcher or using a file manager.
- **Built-in Crash Resolver:** Automatic patch triggers to fix freezing or black-screen issues.

## 🛠️ System Requirements

This application requires system libraries and Python PyGObject bindings:

- Python 3.9 or newer
- GTK 4.0 or newer
- Libadwaita 1.0 or newer
- PyGObject (`python3-gi`)
- `xdg-utils`

### Package Installation (Debian / Ubuntu / Pop!_OS)

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 xdg-utils
```

## 📦 Installation & Run Methods

Three different methods are provided to install, package, or test the project on your system:

### 1. System Installation (`setup.sh`)

This script installs the application into your user's local directory (`~/.local/share/applications`), checks for required dependencies, and adds a shortcut to your application menu.

```bash
chmod +x setup.sh
./setup.sh
```

- **Run from terminal:** `mc-gdk-launcher`
- **Desktop file:** `~/.local/share/applications/com.mc.gdk.launcher.desktop`

### 2. Build a Standalone AppImage

To build a portable, standalone AppImage package:

```bash
chmod +x build-appimage.sh
./build-appimage.sh
```

- **Output:** `Minecraft_GDK_Launcher-x86_64.AppImage`
- You can run the app directly by double-clicking this file, with no installation required.

### 3. Flatpak Sandboxed Installation

If you want to run the application in an isolated Flatpak container:

```bash
chmod +x flatpak/install-local.sh
./flatpak/install-local.sh
```

- **Run command:** `flatpak run com.mc.gdk.launcher`
- Dependencies are automatically installed into the sandbox via Flathub.

## 🚀 Developer / Test Mode (No Installation)

To make changes to the code and test them directly:

```bash
python3 main.py
```

## ⚠️ Important Notes

- This project does **not** include Minecraft game files. You must provide the GDK edition's game files yourself and select the game's `.exe` path in the settings.
- The launcher automatically performs file verification when switching between ProxyPass and In-Game modes. You may want to back up your files beforehand.

## 👤 Author

- @mercimekcik
- GitHub: [Mercimekcik Profile](https://github.com/Mercimekcik?tab=repositories)
