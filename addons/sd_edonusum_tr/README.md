# sd_edonusum_tr — E-Dönüşüm TR: Uygulama Yanıtı ve Çoklu Entegratör

Odoo 19'un **yerleşik** Türkiye e-fatura altyapısının üzerine oturur ve yalnızca orada
olmayanı ekler.

## Çekirdek neyi zaten yapıyor (bu modül tekrar etmez)

`l10n_tr_nilvera*` modülleri Odoo 19 ile birlikte gelir:

| Konu | Çekirdek modül |
|---|---|
| UBL-TR 2.1 üretimi/ayrıştırması | `l10n_tr_nilvera_einvoice` (`account_edi_xml_ubl_tr`) |
| e-Fatura / e-Arşiv gönderme, alma, PDF | `l10n_tr_nilvera_einvoice` (5 cron) |
| GİB senaryo ve fatura tipleri, **27 tevkifat kodu**, **8 istisna kodu**, ihraç kayıtlı | `l10n_tr_nilvera_einvoice_extended` |
| 270 satırlık TR vergi şablonu, vergi dairesi kataloğu | `l10n_tr_nilvera_einvoice_extended` |
| e-İrsaliye | `l10n_tr_nilvera_edispatch` |
| VKN/TCKN doğrulama, mükellef sorgulama, alias | `l10n_tr_nilvera`, `l10n_tr_nilvera_base_vat` |

## Bu modül ne ekliyor

1. **GİB uygulama yanıtı (KABUL / RED)** — çekirdekte yok. Gelen ticari faturada fatura
   üst barından tek tıkla; red için gerekçe sihirbazı zorunlu.
2. **TTK m.21/2 yasal itiraz takibi** — itiraz son tarihi hesaplanır, son 3 günde fatura
   formunda uyarı çıkar, süre dolunca günlük cron faturayı *yasal kabul* olarak işaretler.
   `auto_accept_enabled` açıksa entegratöre de KABUL yanıtı gönderilir (varsayılan kapalı:
   önce yalnız Odoo içi işaretleme).
3. **Çoklu entegratör** — Nilvera (çekirdeğin istemcisi yeniden kullanılır), **Paraşüt**
   (OAuth2, jeton backend'de önbelleklenir) ve **Uyumsoft** (SOAP/WS-Security, ek bağımlılık
   yok: `requests` + `lxml`). Yeni sağlayıcı eklemek = `services/` altına bir dosya.
4. **İşlem günlüğü** — her dış çağrı `sd.edonusum.sync.log` kaydına yazılır; hatalar sessizce
   yutulmaz, geçici hatalar (`retry`) bir sonraki cron turunda devam eder.

## Kurulum

```bash
# Odoo.sh / on-premise: addons yolunda bu modül olmalı
odoo -d <db> -i sd_edonusum_tr --stop-after-init
```

Sonra **Muhasebe → E-Dönüşüm TR → Entegratör Bağlantıları** altında şirket başına bir kayıt
açın. Nilvera seçilirse API anahtarı çekirdeğin kendi ayarından (Muhasebe → Ayarlar →
Türkiye - Nilvera) okunur; Paraşüt/Uyumsoft kimlik bilgileri backend kaydında saklanır ve
yalnızca sistem yöneticisi (`base.group_system`) okuyabilir.

## Yetkiler

| Grup | Yapabildiği |
|---|---|
| Uygulama Yanıtı Verebilir | Faturaya KABUL/RED gönderir, günlüğü okur |
| Entegratör Yöneticisi | Bağlantıları tanımlar, süre ayarını değiştirir |

Kimlik bilgisi alanları `groups="base.group_system"` ile korunur — muhasebe kullanıcısı
RPC ile dahi okuyamaz.

## Test

```bash
odoo -d <db> -u sd_edonusum_tr --test-enable --test-tags /sd_edonusum_tr --stop-after-init
```

Testler ağa çıkmaz; sağlayıcı çağrıları `unittest.mock` ile taklit edilir.

## Bilinçli sınırlar

- **Giden fatura üretimi ve gönderimi çekirdeğe bırakılmıştır.** Paraşüt/Uyumsoft üzerinden
  *giden* e-fatura göndermek isterseniz, çekirdeğin `_l10n_tr_nilvera_submit_document`
  akışının sağlayıcı seçimine göre dallanması gerekir; bu modül bugün yalnız gelen belge
  yanıtlarını çoklu sağlayıcıya açar.
- Paraşüt ve Uyumsoft uç noktaları sözleşmeye göre değişebildiğinden alan adları
  `services/*.py` içinde tek noktada toplanmıştır; canlı hesapla ilk bağlantıda
  doğrulanmalıdır.
