{
    "name": "E-Dönüşüm TR: Uygulama Yanıtı ve Çoklu Entegratör",
    "summary": "Odoo'nun yerleşik Nilvera e-fatura altyapısına GİB uygulama yanıtı (KABUL/RED), "
               "TTK m.21/2 otomatik kabul ve Paraşüt / Uyumsoft entegratör desteği ekler.",
    "description": """
E-Dönüşüm TR: Uygulama Yanıtı ve Çoklu Entegratör
==================================================

Odoo 19 ile gelen l10n_tr_nilvera* modüllerinin üzerine oturur ve yalnızca
çekirdekte bulunmayanı ekler:

* GİB uygulama yanıtı (KABUL / RED) ve red gerekçesi sihirbazı.
* TTK m.21/2 yasal itiraz süresi takibi ve süre dolunca otomatik kabul.
* Paraşüt (OAuth2) ve Uyumsoft (SOAP) entegratör desteği; Nilvera için
  çekirdeğin istemcisi ve API anahtarı yeniden kullanılır.
* Her dış çağrının kaydedildiği işlem günlüğü.
""",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/EDI",
    "author": "7Dimensions",
    "website": "https://github.com/7Dimensions-Project/e-donusum-turkiye",
    "license": "LGPL-3",
    "countries": ["tr"],
    # Core zaten şunları sağlıyor: UBL-TR builder, e-Fatura/e-Arşiv gönderme-alma,
    # PDF akışı, cron'lar, 270 satırlık TR vergi şablonu, 38 GİB kodu (tevkifat/istisna),
    # mükellef sorgulama, alias yönetimi, VKN/TCKN doğrulama.
    # Bu modül SADECE core'da olmayanı ekler.
    "depends": [
        "l10n_tr_nilvera_einvoice_extended",
    ],
    "data": [
        "security/sd_edonusum_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/sd_edonusum_backend_views.xml",
        "views/sd_edonusum_sync_log_views.xml",
        "views/account_move_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
