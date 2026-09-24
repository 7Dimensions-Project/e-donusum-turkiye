# E-Dönüşüm Türkiye (Nilvera, Paraşüt & Uyumsoft Entegrasyonu)

[![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20%7C%2018.0%20%7C%2019.0-purple.svg)](https://www.odoo.com)
[![Platform](https://img.shields.io/badge/Platform-Odoo.sh%20%7C%20On--Premise%20%7C%20Odoo%20Online%20(SaaS)-blue.svg)]()
[![Integrators](https://img.shields.io/badge/Entegratörler-Nilvera%20%7C%20Paraşüt%20%7C%20Uyumsoft-success.svg)]()
[![Standard](https://img.shields.io/badge/Standart-GİB%20UBL--TR%202.1-red.svg)](https://ebelge.gib.gov.tr)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL%20v3-yellow.svg)](https://www.gnu.org/licenses/lgpl-3.0)

**E-Dönüşüm Türkiye**, Gelir İdaresi Başkanlığı (GİB) E-Dönüşüm ekosistemini (e-Fatura, e-Arşiv, e-SMM, e-İrsaliye) **Çoklu Entegratör (Multi-Integrator Engine: Nilvera, Paraşüt, Uyumsoft)** altyapısıyla hem **Odoo.sh / On-Premise** hem de **Odoo Online (SaaS)** sistemlerine entegre eden modern ve modüler kurumsal Odoo çözümüdür.

---

## 🌟 Desteklenen Entegratörler

| Entegratör | Protokol / API | Desteklenen Belgeler & İşlemler |
|---|---|---|
| **Nilvera** | REST API (Bearer Token) | e-Fatura, e-Arşiv, e-SMM, KABUL/RED, Mükellef Sorgulama, PDF/XML Arşivleme |
| **Paraşüt** | REST API v4 (OAuth2) | e-Fatura, e-Arşiv, KABUL/RED (`e_invoice_responses`), Mükellef Sorgulama, PDF/XML |
| **Uyumsoft** | SOAP / WCF Web Servisleri | e-Fatura, e-Arşiv, Ticari Yanıt (Kabul/Red), Mükellef Sorgulama, İrsaliye, PDF/XML |

*Şirket ayarlarından dilediğiniz entegratörü tek tıkla seçebilirsiniz. Modül, seçilen entegratöre göre arka plandaki tüm protokolleri dinamik olarak devreye alır.*

---

## 🚀 Temel Özellikler

* **Çift Platform Desteği (Dual-Engine):**
  * **Odoo.sh & On-Premise:** Tam yerel Odoo modülü (`addons/e_donusum_turkiye`).
  * **Odoo Online (SaaS):** Sunucuya kod yüklemeye gerek duymayan Server Action'lar ve senkronizasyon köprüsü (`odoo_online_bridge`).
* **İki Yönlü Uygulama Yanıtları (GİB KABUL / RED):**
  * Ticari e-faturalar için fatura üst barından tek tıkla doğrudan entegratör üzerinden GİB'e **KABUL** veya **RED** gönderme.
  * Portal üzerinden kabul/reddedilmiş faturaların durumlarını anlık çekme.
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
* **Resmi Ekler:** İmzalı UBL XML ve GİB görsel PDF'lerinin otomatik indirilip faturanın eklerine ve chatter'a iliştirilmesi.

---

## 📁 Proje Dizin Yapısı

```
e-donusum-turkiye/
├── addons/
│   └── e_donusum_turkiye/                 # Odoo.sh & On-Premise Yerel Modülü
│       ├── models/                        # ORM Modelleri (account.move, res.company, res.partner)
│       ├── tools/
│       │   ├── integrators/               # Çoklu Entegratör Motoru (Nilvera, Paraşüt, Uyumsoft)
│       │   │   ├── base_integrator.py     # Ortak Soyut Entegratör Sınıfı
│       │   │   ├── nilvera_adapter.py     # Nilvera REST API Adaptörü
│       │   │   ├── parasut_adapter.py     # Paraşüt v4 OAuth2 Adaptörü
│       │   │   └── uyumsoft_adapter.py    # Uyumsoft SOAP WCF Adaptörü
│       │   ├── ubl_tr_parser.py           # GİB UBL-TR 2.1 XML Ayrıştırıcı
│       │   ├── ubl_tr_generator.py        # GİB UBL-TR 2.1 XML Üretici
│       │   └── ubl_tax_resolver.py        # Türkiye Vergi & Tevkifat Çözücü
│       ├── views/                         # Form & Liste Görünümleri, Butonlar, Menüler
│       ├── wizard/                        # Tarih Aralıklı Fatura Çekme Sihirbazı
│       ├── data/                          # Saatlik Senkronizasyon & Yasal İtiraz Cron'ları, Vergi Grupları
│       └── security/                      # Yetki Grupları & ACL
├── odoo_online_bridge/                     # Odoo Online (SaaS) Köprüsü
│   ├── server_actions/                    # SaaS Server Action Python Kodları (Kabul, Red, Durum Güncelle)
│   ├── scripts/
│   │   ├── deploy_to_odoo_online.py       # Tek Komutla SaaS'a Alan & Buton Kuran CLI
│   │   └── odoo_online_sync_daemon.py     # Arka Plan Fatura Senkronizasyon Servisi
│   └── views/                             # Studio XML Yama Şablonları
├── docs/                                  # Detaylı Dokümantasyon
│   ├── ARCHITECTURE.md                    # Sistem Mimarisi & Çalışma Prensipleri
│   ├── ODOO_SH_INSTALLATION.md            # Odoo.sh & On-Premise Kurulum Rehberi
│   ├── ODOO_ONLINE_GUIDE.md               # Odoo Online (SaaS) Kullanım Rehberi
│   └── GIB_TAX_STANDARDS.md               # Türkiye Vergi Kodları & Muhasebe Standartları
├── tests/                                 # Unit & Entegrasyon Testleri
│   ├── test_multi_integrator.py           # Entegratör Fabrika & Adaptör Testleri
│   ├── test_ubl_parser.py                 # UBL 2.1 Ayrıştırma Testi
│   └── test_nilvera_api.py                # Nilvera API İstemci Testi
└── README.md
```

---

## ⚙️ Yapılandırma

Odoo arayüzünde **Ayarlar > Şirketler > E-Dönüşüm Türkiye** sekmesine gidin:
1. **Entegratör Seçin:** `Nilvera`, `Paraşüt` veya `Uyumsoft`.
2. Seçtiğiniz entegratörün kimlik bilgilerini girin:
   * **Nilvera:** API Anahtarı (Bearer token) ve Ortam (`Canlı` / `Test`).
   * **Paraşüt:** Client ID, Client Secret, Kullanıcı Adı, Şifre, Firma ID.
   * **Uyumsoft:** Web Servis Kullanıcı Adı, Şifre ve Ortam (`Canlı` / `Test`).
3. **"Seçili Entegratör Bağlantısını Test Et"** butonuna basarak bağlantıyı doğrulayın.

---

## 🧪 Testleri Çalıştırma

```bash
python -m unittest discover -s tests
```

---

## 📄 Lisans

Bu proje **LGPL-3** lisansı ile lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakınız.

Geliştirici: **7Dimensions & Hasan Can ÖZDEMİR**
