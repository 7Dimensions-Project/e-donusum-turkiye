# -*- coding: utf-8 -*-
{
    'name': 'E-Dönüşüm Türkiye (KULLANIMDAN KALDIRILDI — bkz. sd_edonusum_tr)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'GİB UBL-TR 2.1 E-Fatura, E-Arşiv, E-SMM Entegrasyonu (Nilvera, Paraşüt, Uyumsoft). Odoo.sh, On-Premise ve Odoo Online uyumlu.',
    'description': """
E-Dönüşüm Türkiye
=================
Gelir İdaresi Başkanlığı (GİB) E-Dönüşüm standartlarına tam uyumlu kurumsal e-Fatura, e-Arşiv, e-SMM ve e-İrsaliye çözümü.

Desteklenen Entegratörler:
--------------------------
* **Nilvera:** REST API (Bearer Token)
* **Paraşüt:** REST API v4 (OAuth2)
* **Uyumsoft:** SOAP / WCF Web Servisleri (UsernameToken)

Öne Çıkan Özellikler:
--------------------
* Çift Katmanlı Mimari (Odoo.sh & On-Premise yerel modül, Odoo Online SaaS server action köprüsü).
* İki Yönlü Uygulama Yanıtları (GİB KABUL / RED).
* 7 Günlük Ticari Fatura Yasal İtiraz Takibi ve Otomatik Onay (TTK m.21/2).
* Çoklu Vergi Motoru (KDV %20/%10/%1/%0, Tevkifat 9015 2/10..10/10, Konaklama Vergisi 0059 -> 770 Genel Yönetim Gideri, ÖİV 4080, ÖTV, Damga, BSMV).
* Kuruş Yuvarlama ve Artırım Dengelemesi (AllowanceCharge / ChargeIndicator).
* Çoklu Para Birimi (FX - EUR, USD, GBP) ve TCMB Kuru ile Yan Yana TL Tutarları.
* İmzalı UBL-TR 2.1 XML ve Resmi Görsel PDF Arşivleme.
    """,
    'author': '7Dimensions & Hasan Can ÖZDEMİR',
    'website': 'https://github.com/7Dimensions-Project/e-donusum-turkiye',
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'data/tax_data.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'wizard/fetch_invoices_wizard_views.xml',
        'views/menu_views.xml',
    ],
    # Bu modül Odoo 19'da kurulmuyor ve yerini addons/sd_edonusum_tr aldı.
    # Ayrıntı ve geçiş notları: addons/e_donusum_turkiye/DEPRECATED.md
    'installable': False,
    'application': False,
    'auto_install': False,
}
