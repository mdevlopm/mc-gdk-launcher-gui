# 🎮 Minecraft Bedrock Linux (GDK) Launcher

[![Platform Linux](https://img.shields.io/badge/platform-Linux-blue.svg)](https://www.linux.org)
[![GTK4 Libadwaita](https://img.shields.io/badge/UI-GTK4%20%2F%20Libadwaita-orange.svg)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Linux üzerinde **Minecraft Bedrock (GDK)** sürümünü oynamak için tasarlanmış, **GTK4 ve Libadwaita** teknolojileriyle geliştirilmiş premium ve modern arayüze sahip bağımsız bir başlatıcı (launcher).

Bu başlatıcı, oyunun Microsoft GDK uyumluluk katmanını Linux üzerinde çalıştırmak için **GDK-Proton** araçlarını ve gelişmiş kimlik doğrulama mekanizmalarını yönetir.

---

## ✨ Öne Çıkan Özellikler

- **Modern & Premium Tasarım:** Tamamen GNOME tasarım kılavuzlarına ve Libadwaita standartlarına uygun, sistem temasıyla uyumlu koyu mod ve cam (glassmorphic) kart tasarımları.
- **Dinamik Çift Giriş Modu:**
  - 🌐 **ProxyPass Yöntemi:** Microsoft kimlik doğrulama trafiğini yönlendirmek için yerel bir ara sunucu kullanır. Bu mod seçildiğinde başlatıcı otomatik olarak oyun dosyalarını vanilla (temiz) durumuna getirir, fazlalık DLL yamalarını temizler ve Wine MSA kayıt defteri girdilerini sıfırlar. Standart GDK-Proton sürümünü kullanır.
  - 🎮 **Oyun İçi (In-Game) Giriş Yöntemi:** Oyun içi girişin çalışabilmesi için özel yama içeren `xuser` GDK-Proton sürümünü ve özel DLL kancalarını (`XCurl.dll`, `libHttpClient.GDK.dll`) otomatik olarak kurar ve entegre eder.
- **Otomatik Bağımlılık Yönetimi:**
  - Uyumlu GDK-Proton sürümlerini doğrudan başlatıcı içerisinden indirip kurma.
  - ProxyPass için gerekli olan Java Runtime (çalışma zamanı) ortamını otomatik algılama ve indirme.
- **Entegre Mağaza (Store):** Özel brarchive kaynak paketlerini, modları ve dış görünümleri (skin) tek tıkla indirip oyuna yükleme.
- **options.txt Editörü:** Oyun içi ayarları başlatıcıyı kapatmadan veya dosya yöneticisiyle uğraşmadan doğrudan arayüz üzerinden arayıp değiştirebilme.
- **Dahili Hata Çözücü:** Donma veya siyah ekran sorunlarını otomatik çözen yama tetikleyicileri.

---

## 🛠️ Sistem Gereksinimleri

Bu uygulama sistem kütüphanelerine ve Python PyGObject bağlayıcılarına ihtiyaç duyar:

- **Python** 3.9 veya daha yeni bir sürüm
- **GTK** 4.0 ve üzeri
- **Libadwaita** 1.0 ve üzeri
- **PyGObject** (`python3-gi`)
- `xdg-utils`

### Paket Kurulumu (Debian / Ubuntu / Pop!_OS)
```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 xdg-utils
```

---

## 📦 Kurulum ve Çalıştırma Yöntemleri

Projeyi sisteminize kurmak, paketlemek veya test etmek için 3 farklı yöntem sunulmaktadır:

### 1. Sistem Kurulumu (`setup.sh`)
Bu betik, uygulamayı kullanıcınızın yerel dizinine (`~/.local/share/applications`) yükler, gerekli bağımlılıkları kontrol eder ve uygulama menünüze kısayol ekler.

```bash
chmod +x setup.sh
./setup.sh
```
- **Terminalden Çalıştırma:** `mc-gdk-launcher`
- **Masaüstü Dosyası:** `~/.local/share/applications/com.mc.gdk.launcher.desktop`

### 2. Standalone AppImage Oluşturma
Bağımsız, taşınabilir bir AppImage paketi oluşturmak için:

```bash
chmod +x build-appimage.sh
./build-appimage.sh
```
- **Çıktı:** `Minecraft_GDK_Launcher-x86_64.AppImage`
- Uygulamayı hiçbir yere kurmadan doğrudan bu dosyaya çift tıklayarak çalıştırabilirsiniz.

### 3. Flatpak Sandboxed Kurulumu
Uygulamayı izole edilmiş bir Flatpak kapsayıcısında çalıştırmak istiyorsanız:

```bash
chmod +x flatpak/install-local.sh
./flatpak/install-local.sh
```
- **Çalıştırma Komutu:** `flatpak run com.mc.gdk.launcher`
- Bağımlılıkları sandbox içerisine flathub aracılığıyla otomatik kurar.

---

## 🚀 Geliştirici ve Test Modu (Kurulumsuz)

Kodlar üzerinde değişiklik yapıp doğrudan test etmek için aşağıdaki komut yeterlidir:

```bash
python3 main.py
```

---

## ⚠️ Önemli Notlar

- Bu proje **Minecraft oyun dosyalarını içermez**. GDK sürümüne ait oyun dosyalarını sizin temin etmeniz ve ayarlardan oyunun `.exe` yolunu seçmeniz gerekir.
- ProxyPass ve In-Game geçişlerinde başlatıcı otomatik olarak dosya doğrulaması yapar. Dosyalarınızın yedeğini almak isteyebilirsiniz.

---

## 👤 Yapımcı
- **@mercimekcik**
- GitHub: [Mercimekcik Profil Sayfası](https://github.com/Mercimekcik?tab=repositories)
