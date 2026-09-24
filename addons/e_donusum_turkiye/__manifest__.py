# -*- coding: utf-8 -*-
# Part of Odoo E-Dönüşüm Türkiye. See LICENSE file for full copyright and licensing details.

{
    'name': 'Türkiye E-Dönüşüm (Nilvera & GİB Entegrasyonu)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Nilvera REST API ile GİB e-Fatura, e-Arşiv, e-SMM, Tevkifat ve İki Yönlü Uygulama Yanıtı Entegrasyonu',
    'description': """
Odoo E-Dönüşüm Türkiye (Nilvera & GİB Tam Entegrasyonu)
======================================================
Bu modül, Odoo.sh ve On-Premise ortamlarında Nilvera REST API üzerinden Gelir İdaresi Başkanlığı (GİB)
E-Dönüşüm ekosistemini (e-Fatura, e-Arşiv, e-SMM) eksiksiz ve otomatik olarak yönetir.

Temel Yetenekler:
-----------------
* **Gelen ve Giden e-Faturalar:** Ticari ve Temel e-Fatura alma, gönderme, UBL-TR 2.1 tam ayrıştırma.
* **İki Yönlü Uygulama Yanıtları (KABUL / RED):**
  - Ticari faturalar için doğrudan arayüzden Nilvera API'ye `POST /einvoice/Purchase/SendAnswer` ile GİB yanıtı iletme.
  - Portal üzerinden verilen yanıtları ve GİB durum kodlarını saatlik senkronizasyon ile Odoo'ya aktarma (`GET /einvoice/Purchase/{UUID}/Status`).
  - 7 günlük yasal itiraz süresini (TTK m.21/2) otomatik hesaplama ve yasal süre dolduğunda otomatik onaylama.
* **Gelişmiş Türkiye Vergi Motoru:**
  - Gerçek usulde KDV (%20, %10, %1, %0 ve İstisna Kodları).
  - 9015 Tevkifat Kodları ve Tevkifat Oranları (2/10, 3/10, 4/10, 5/10, 7/10, 9/10, 10/10).
  - Konaklama Vergisi (%1, %2) 770 Genel Yönetim Giderleri ayrıştırması.
  - ÖİV (%10), ÖTV, Stopaj, Damga Vergisi ve BSMV otomatik hesaplama ve eşleme.
  - Fatura altı kuruş yuvarlama farkları ve artırım (AllowanceCharge) satır dengelemesi.
* **Çoklu Para Birimi (FX - EUR, USD, GBP):**
  - Dövizli faturalarda TCMB kuru ile muhasebeleştirme ve form üzerinde yan yana TL Vergi/Matrah/Genel Toplam kutusu.
* **Otomatik Cari ve Ürün Eşleme:**
  - VKN / TCKN üzerinden sistemdeki partner'ı bulma, yoksa otomatik oluşturma ve e-fatura mükellefiyetini işaretleme.
  - Tedarikçi ürün kodu (SellerItemIdentification) veya barkod ile ürün eşleme.
* **Resmi Ekler ve Önizleme:**
  - Orijinal imzalı UBL XML ve GİB PDF'lerini doğrudan faturanın eklerine ve chatter alanına kaydetme.
* **Çoklu Şirket (Multi-Company):**
  - Şirket bazlı ayrı API anahtarları, Test / Canlı ortam geçişi ve bağımsız senkronizasyon ayarları.
    """,
    'author': '7Dimensions & Hasan Can ÖZDEMİR',
    'website': 'https://github.com/7Dimensions-Project/e-donusum-turkiye',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/tax_data.xml',
        'data/cron_data.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/menu_views.xml',
        'wizard/fetch_invoices_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
