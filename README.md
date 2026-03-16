# mc-gdk-launcher-gui
# Minecraft GDK Launcher (Linux)

Minecraft GDK için geliştirilmiş, modern ve modüler bir başlatıcıdır. Python, GTK4 ve Libadwaita kullanılarak Linux sistemler için optimize edilmiştir.


## Özellikler

- **Modern Arayüz**: Libadwaita ile temiz, adaptif ve sistem temasına uyumlu (Dark/Light mode) bir tasarım.
- **ProxyPass Desteği**: Sunucu bağlantıları için entegre ProxyPass yönetimi.
- **Proton/GDK Entegrasyonu**: GDK-Proton üzerinden yüksek performanslı oyun deneyimi.
- **Modüler Yapı**: Java Runtime, Proxy ve Oyun mantığı birbirinden bağımsız, kolay geliştirilebilir modüller.
- **Kolay Kurulum**: Tek komutla masaüstü entegrasyonu.
- **Sunucu Yönetimi**: Hazır sunucu listesi ve özel sunucu ekleme desteği.

## Gereksinimler

Uygulamayı çalıştırmak için sisteminizde aşağıdaki paketlerin yüklü olması gerekir:

- **Python 3.9+**
- **GTK4**
- **Libadwaita 1.0+**
- **PyGObject** (`python3-gi`)

Debian/Ubuntu tabanlı sistemlerde kurulum:
```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

## Kurulum

öncelikle projeyi klonlamanız gerekmektedir ardından klonladıgnız dizine girip komutları çalıştırmanız yeterlidir artık gnome arayüzünde uygulamanın iconu belirecek


```bash
chmod +x setup.sh
./setup.sh
```

Bu işlem uygulama menünüzde bir kısayol oluşturacak ve ikonu sisteme tanıtacaktır.

## Kullanım

Eğer kurulum yapmadan doğrudan çalıştırmak isterseniz:

```bash
python3 main.py
```

## Lisans

Bu proje açık kaynaklıdır. Detaylar için ilgili dosyalara göz atabilirsiniz.
oyun dosyası suanda mevcut değil discord üzerinden iletişime geçebilirsiniz 
discord ismi whtsyk
##Katkıda bulunanlar 
@mercimekcik https://github.com/Mercimekcik?tab=repositories

