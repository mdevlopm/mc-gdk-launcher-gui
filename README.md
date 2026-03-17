# Minecraft GDK Launcher (Linux)

A clean, modern launcher built with **GTK4 / Libadwaita** to run **Minecraft Bedrock (GDK)** on Linux via **GDK-Proton**.
Includes integrated **ProxyPass** support for handling Microsoft authentication and custom server routing.

---

## 🚀 Features

* **Native GNOME-style UI** powered by Libadwaita
* **GDK-Proton management** (download and install directly inside the app)
* **ProxyPass integration**

  * Microsoft account login handling
  * Custom destination server configuration
* **Automatic Java runtime downloader** (used by ProxyPass when required)
* **Desktop integration**

  * `setup.sh` creates an application menu shortcut

---

## 📦 Requirements

This project relies on **system-level dependencies** (not pip-installed packages):

* Python **3.9+**
* GTK **4**
* Libadwaita **1.0+**
* PyGObject (`python3-gi`)
* `xdg-utils`

### Debian / Ubuntu

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 xdg-utils
```

---

## 🛠️ Installation

Clone the repository and run:

```bash
chmod +x setup.sh
./setup.sh
```

This script:

* Installs required dependencies (if available)
* Creates a desktop/application menu entry

---

## ▶️ Run Without Installation

```bash
python3 main.py
```

---

## ⚠️ Notes

* This repository **does not include game files**
* Discord integration is planned for future updates

---

## 📄 License

MIT License

---

## 👤 Credits
@mercimekcik
GitHub: https://github.com/Mercimekcik?tab=repositories
