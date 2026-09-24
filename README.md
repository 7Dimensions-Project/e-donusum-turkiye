# E-Dönüşüm Türkiye (Nilvera & GİB Entegrasyonu)

[![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20%7C%2018.0%20%7C%2019.0-purple.svg)](https://www.odoo.com)
[![Platform](https://img.shields.io/badge/Platform-Odoo.sh%20%7C%20On--Premise%20%7C%20Odoo%20Online%20(SaaS)-blue.svg)]()
[![Integration](https://img.shields.io/badge/Entegratör-Nilvera%20REST%20API-success.svg)](https://nilvera.com)
[![Standard](https://img.shields.io/badge/Standart-GİB%20UBL--TR%202.1-red.svg)](https://ebelge.gib.gov.tr)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL%20v3-yellow.svg)](https://www.gnu.org/licenses/lgpl-3.0)

**E-Dönüşüm Türkiye**, Gelir İdaresi Başkanlığı (GİB) E-Dönüşüm ekosistemini (e-Fatura, e-Arşiv, e-SMM, e-İrsaliye) **Nilvera REST API** üzerinden hem **Odoo.sh / On-Premise** hem de **Odoo Online (SaaS)** sistemlerine kusursuz entegre eden modern ve tam kapsamlı kurumsal Odoo çözümüdür.

---

## 🌟 Temel Özellikler

* **Çift Platform Desteği (Dual-Engine):**
  * **Odoo.sh & On-Premise:** Tam yerel Odoo modülü (`addons/e_donusum_turkiye`).
  * **Odoo Online (SaaS):** Sunucuya kod yüklemeye gerek duymayan Server Action'lar ve otomatik senkronizasyon köprüsü (`odoo_online_bridge`).
* **İki Yönlü Uygulama Yanıtları (GİB KABUL / RED):**
  * Ticari e-faturalar için fatura üst barından tek tıkla doğrudan `POST /einvoice/Purchase/SendAnswer` ile GİB yanıtı iletme.
  * Portal üzerinden kabul/reddedilmiş faturaların durumlarını anlık çekme (`GET /einvoice/Purchase/{UUID}/Status`).
  * 7 günlük yasal itiraz süresi dolan ticari faturaların otomatik onayı (**TTK m.21/2**).
* **Gelişmiş Türkiye Vergi Motoru (UBL-TR 2.1):**
  * **KDV (0015):** %20, %10, %1, %0 ve İstisna kodları.
  * **Tevkifat (9015):** 2/10, 3/10, 4/10, 5/10, 7/10, 9/10, 10/10 tevkifat oranlarının otomatik tespiti ve eşlenmesi.
  * **Konaklama Vergisi (0059):** Alıcı için indirim konusu yapılamayan konaklama vergisinin otomatik olarak **770 Genel Yönetim Gideri**'ne ayrıştırılması.
  * **ÖİV (4080), ÖTV (0071-77), Damga (0040), BSMV (0021).**
  * **AllowanceCharge Dengelemesi:** Fatura altı 0.25 TL gibi yuvarlama/artırım veya iskonto farklarının kuruşu kuruşuna dengelenmesi.
* **Çoklu Para Birimi (FX - EUR, USD, GBP):**
  * Dövizli faturaların TCMB kuru ile muhasebeleştirilmesi ve arayüzde yan yana TL Vergi/Matrah/Genel Toplam kutusu.
* **Otomatik Cari ve Ürün Eşleme:**
  * VKN / TCKN ile cari tespiti, otomatik cari kartı açma ve e-fatura mükellefiyet sorgusu.
  * Tedarikçi ürün kodu ve barkod eşlemesi.
* **Resmi Ekler:** İmzalı UBL XML ve GİB görsel PDF'lerinin otomatik indirilip faturanın eklerine ve chatter'a iliştirilmesi.

---

## 📁 Proje Dizin Yapısı

```
e-donusum-turkiye/
├── addons/
│   └── e_donusum_turkiye/                 # Odoo.sh & On-Premise Yerel Modülü
│       ├── models/                        # ORM Modelleri (account.move, res.company, res.partner)
│       ├── tools/                         # Nilvera API İstemcisi, UBL-TR Parser & Generator, Vergi Çözücü
│       ├── views/                         # Form & Liste Görünümleri, Durum Rozetleri, Butonlar
│       ├── wizard/                        # Tarih Aralıklı Fatura Çekme Sihirbazı
│       ├── data/                          # Saatlik Senkronizasyon & Yasal İtiraz Cron'ları, Vergi Grupları
│       └── security/                      # Kullanıcı Yetki Grupları & ACL
├── odoo_online_bridge/                     # Odoo Online (SaaS) Entegrasyon Paketi
│   ├── server_actions/                    # SaaS Server Action Python Kodları (Kabul, Red, Durum Güncelle)
│   ├── scripts/
│   │   ├── deploy_to_odoo_online.py       # Tek Komutla SaaS'a Alan & Buton Kuran CLI
│   │   └── odoo_online_sync_daemon.py     # SaaS için Arka Planda Çalışan Fatura Senkronizasyon Servisi
│   └── views/                             # Studio XML Yama Şablonları
├── docs/                                  # Detaylı Dokümantasyon
│   ├── ARCHITECTURE.md                    # Sistem Mimarisi & Çalışma Prensipleri
│   ├── ODOO_SH_INSTALLATION.md            # Odoo.sh & On-Premise Kurulum Rehberi
│   ├── ODOO_ONLINE_GUIDE.md               # Odoo Online (SaaS) Kullanım Rehberi
│   └── GIB_TAX_STANDARDS.md               # Türkiye Vergi Kodları & Muhasebe Standartları
├── tests/                                 # Unit & Entegrasyon Testleri
│   ├── test_ubl_parser.py
│   └── test_nilvera_api.py
└── README.md
```

---

## 🚀 Hızlı Başlangıç

### Odoo.sh & On-Premise İçin:
Detaylar için [Odoo.sh Kurulum Kılavuzu](docs/ODOO_SH_INSTALLATION.md) belgesini inceleyin:
1. Depoyu Odoo `addons` yolunuza ekleyin.
2. Uygulama listesini güncelleyip `Türkiye E-Dönüşüm` modülünü yükleyin.
3. **Ayarlar > Şirketler > E-Dönüşüm** sekmesinden Nilvera API Anahtarınızı girip bağlantıyı test edin.

### Odoo Online (SaaS) İçin:
Detaylar için [Odoo Online Kullanım Kılavuzu](docs/ODOO_ONLINE_GUIDE.md) belgesini inceleyin:
```bash
python odoo_online_bridge/scripts/deploy_to_odoo_online.py \
    --url https://sirketiniz.odoo.com \
    --db sirketiniz \
    --user admin@sirketiniz.com \
    --key api_anahtariniz
```

---

## 🧪 Testleri Çalıştırma

```bash
python -m unittest discover -s tests
```

---

## 📄 Lisans

Bu proje **LGPL-3** lisansı ile lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakınız.

Geliştirici: **7Dimensions & Hasan Can ÖZDEMİR**
