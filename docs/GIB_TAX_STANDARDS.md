# Türkiye E-Dönüşüm Vergi Standartları ve Muhasebeleştirme Kılavuzu

Bu belge, Gelir İdaresi Başkanlığı (GİB) E-Fatura UBL-TR 2.1 standardında yer alan vergi kodlarının, oranlarının ve muhasebe karşılıklarının teknik ve mevzuatsal dökümüdür.

---

## 1. Vergi Kodları Tablosu

| Vergi Kodu | Vergi Adı | Standart Oranlar | Odoo Muhasebe Hesabı (Alış) | Odoo Muhasebe Hesabı (Satış) |
|---|---|---|---|---|
| **0015** | Gerçek Usulde KDV | %20, %10, %1, %0 | 191 İndirilecek KDV | 391 Hesaplanan KDV |
| **9015** | KDV Tevkifatı | 2/10 .. 10/10 | 191 İndirilecek KDV / Tevkifat | 391 Hesaplanan KDV / 360 |
| **0059** | Konaklama Vergisi | %1, %2 | **770 Genel Yönetim Giderleri** | 360 Ödenecek Konaklama Vergisi |
| **4080** | Özel İletişim Vergisi (ÖİV) | %10 | **770 Genel Yönetim Giderleri** | 360 Ödenecek ÖİV |
| **0003** | Gelir Vergisi Stopajı | %20, %10 | 770 Gider / 360 Stopaj | - |
| **0071-77**| Özel Tüketim Vergisi (ÖTV) | Değişken | Maliyet / 153 / 770 | 360 Ödenecek ÖTV |
| **0040** | Damga Vergisi | Binde 9,48 | 770 Genel Yönetim Giderleri | 360 Ödenecek Damga Vergisi |
| **0021** | BSMV | %5 | 770 Finansman Gideri | 360 Ödenecek BSMV |

---

## 2. Kritik Muhasebesel Kurallar

### 2.1 Konaklama Vergisi (0059)
* **Kural:** Konaklama Vergisi KDV matrahına dahil edilmez.
* **Alıcı Açısından:** Konaklama vergisi alıcı (müşteri) tarafından indirilecek KDV (191) konusu yapılamaz. Doğrudan **770 Genel Yönetim Gideri** veya ilgili gider hesabına gider/maliyet olarak kaydedilir.
* **Odoo Çözümü:** Vergi tanımındaki repartition line hesabı 191 değil, 770 seçilir.

### 2.2 KDV Tevkifatı (9015)
* Tevkifat, satıcının faturada tahakkuk ettirdiği KDV'nin bir kısmını alıcının doğrudan devlete (2 No'lu KDV beyannamesiyle) ödemesidir.
* Oranlar: `2/10`, `3/10`, `4/10`, `5/10`, `7/10`, `9/10`, `10/10`.
* Modülümüz satırdaki withholding oranını kesirli oranla eşleyip Odoo'daki ilgili Tevkifat vergisini otomatik seçer.

### 2.3 Toplam Artırım ve Yuvarlama (AllowanceCharge)
* e-Faturalarda `cac:AllowanceCharge` etiketi altındaki `cbc:ChargeIndicator=true` alanları **Artırım / Yuvarlama Farkı**'dır (`ChargeIndicator=false` ise İskonto'dur).
* Kuruş yuvarlama farkları faturanın genel toplamını (PayableAmount) birebir eşitlemek için `%0 KDV` ile doğrudan gider/yuvarlama satırı olarak eklenir.

### 2.4 Çoklu Para Birimi (FX) ve TCMB Kuru
* Yabancı para birimli (EUR, USD vb.) faturalarda UBL içindeki `cac:PricingExchangeRate` kuru esas alınır.
* Faturanın Odoo yevmiye kaydı resmi kur üzerinden TL'ye dönüştürülür ve arayüzde hem orijinal döviz hem de TL Vergi/Matrah/Toplam yan yana gösterilir.
