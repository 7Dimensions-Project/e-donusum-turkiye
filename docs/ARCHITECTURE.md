# E-Dönüşüm Türkiye: Mimari ve Tasarım Kılavuzu

## 1. Genel Bakış

**E-Dönüşüm Türkiye**, Gelir İdaresi Başkanlığı (GİB) E-Dönüşüm mevzuatına (e-Fatura, e-Arşiv, e-SMM, e-İrsaliye) tam uyumlu, Nilvera REST API altyapısını kullanan ve hem **Odoo.sh / On-Premise** hem de **Odoo Online (SaaS)** platformlarında çalışabilen hibrit bir entegrasyon çözümüdür.

---

## 2. Dual-Engine (Çift Katmanlı) Mimari

Odoo Online (SaaS) ortamları güvenlik gereği sunucuya doğrudan özel Python dosyaları (`addons`) yüklenmesine izin vermez. Buna karşılık Odoo.sh ve On-Premise ortamları tam kod erişimine sahiptir. 

Bu projenin temel tasarım felsefesi, iş mantığını ve GİB kurallarını ortamdan bağımsız kılarak her iki ekosisteme de uyarlamaktır:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        E-DÖNÜŞÜM TÜRKİYE ÇEKİRDEĞİ                      │
│   • UBL-TR 2.1 Ayrıştırıcı & Üretici (UBLTRParser / UBLTRGenerator)   │
│   • Nilvera REST API İstemcisi (OAuth / Bearer Client)                │
│   • Türkiye Vergi & Tevkifat Çözücü Motoru (UBLTaxResolver)           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     ODOO.SH & ON-PREMISE        │       │       ODOO ONLINE (SAAS)        │
│ • addons/e_donusum_turkiye      │       │ • odoo_online_bridge            │
│ • Yerel ORM Modeli              │       │ • Odoo SafeEval Server Actions  │
│ • Doğrudan UI Butonları         │       │ • Otomatik Provisioner CLI      │
│ • ir.cron Zamanlanmış Görevler  │       │ • Harici Sync Daemon / Worker   │
└─────────────────────────────────┘       └─────────────────────────────────┘
```

---

## 3. Temel Bileşenler

### 3.1 NilveraClient (`tools/nilvera_client.py`)
Nilvera REST API ile haberleşen bağımsız istemci:
* **Gelen e-Faturalar:** Listeleme, UUID bazlı tekil sorgulama, imzalı UBL XML ve görsel PDF indirme.
* **Uygulama Yanıtları:** `POST /einvoice/Purchase/SendAnswer` ile ticari faturalara GİB onaylı **KABUL** veya **RED** gönderme.
* **Durum Senkronizasyonu:** `GET /einvoice/Purchase/{UUID}/Status` ile portal yanıtlarını ve GİB durum kodlarını anlık çekme.
* **GİB Mükellef Kontrolü:** `GET /general/TaxPayer/{VKN}` ile carinin e-fatura kayıtlısı olup olmadığını sorgulama.

### 3.2 UBLTRParser (`tools/ubl_tr_parser.py`)
GİB UBL-TR 2.1 standardını tam olarak çözen motor:
* **Çoklu Vergi Ayrıştırma:** Aynı satırda KDV + Konaklama Vergisi veya KDV + ÖİV durumlarını doğru tespit etme.
* **Tevkifat Oranları:** `9015` vergi kodunu ve 2/10..10/10 tevkifat oranlarını çözümleme.
* **AllowanceCharge Dengelemesi:** Fatura altı 0.25 TL gibi yuvarlama/artırım veya iskonto farklarını yakalama.
* **Döviz & Kur Bilgileri:** Fatura kuru, döviz cinsi ve TL karşılıklarını çıkarma.

### 3.3 UBLTaxResolver (`tools/ubl_tax_resolver.py`)
UBL vergi kodlarını Odoo'nun şirkete özel `account.tax` kayıtlarıyla dinamik olarak eşleştiren motor. Çok şirketli (multi-company) mimaride her şirketin hesap planına göre çalışır.
