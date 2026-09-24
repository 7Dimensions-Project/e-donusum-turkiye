# e_donusum_turkiye — kullanımdan kaldırıldı

Bu modül **kurulamaz** (`installable: False`) ve geliştirilmiyor. Yerini
[`addons/sd_edonusum_tr`](../sd_edonusum_tr/README.md) aldı.

## Neden

Odoo 19 çekirdeği Türkiye e-fatura altyapısını zaten içeriyor: `l10n_tr_nilvera`,
`l10n_tr_nilvera_einvoice`, `l10n_tr_nilvera_einvoice_extended`,
`l10n_tr_nilvera_edispatch`, `l10n_tr_nilvera_base_vat`. Bunlar UBL-TR builder'ı,
e-Fatura/e-Arşiv gönderme-alma akışını, PDF indirmeyi, beş cron'u, 270 satırlık
vergi şablonunu, 27 tevkifat ve 8 istisna kodunu, vergi dairesi kataloğunu ve
VKN/TCKN doğrulamasını sağlıyor. Bu modül aynı işi paralel olarak, daha eksik
biçimde yapıyordu.

## Bu modül Odoo 19'da zaten kurulmuyordu

Gerçek kurulum denemesinin çıktısı:

```
ValueError: Invalid field 'category_id' in 'res.groups'
ParseError: while parsing .../e_donusum_turkiye/security/security.xml:9
```

`res.groups.category_id` 19'da kaldırıldı (yerine `privilege_id`). Bunun dışında
statik denetim 22 bulgu veriyor (`python tools/check_odoo19.py addons/e_donusum_turkiye`):
manifest sürümü `1.0.0` (19.0.x.y.z olmalı), üç action'da `view_mode="tree"`,
eksik `web_icon` dosyası, sessiz `except Exception: pass`, 12 yerde `_("..%s") % x`.

## Bilinen riskler (neden yeniden canlandırılmamalı)

- `tools/ubl_tax_resolver.py` vergileri **isim metniyle** arar ve hiçbiri eşleşmezse
  `%20 KDV` varsayar — yanlış muhasebe üretir.
- `tools/ubl_tr_generator.py` hiçbir yerden çağrılmıyordu; giden fatura gönderimi yoktu.
- `odoo_online_bridge/` içindeki server action'lar `getattr`/`hasattr` kullanıyor;
  bunlar Odoo `safe_eval` beyaz listesinde yok, çalışmaları mümkün değil.
- `x_tl_*` alanlarına hiçbir yerde değer yazılmıyordu.

## Geçiş

Bu modül hiçbir müşteri veritabanında kurulu değil, dolayısıyla veri taşıma
gerekmiyor. Yeni kurulumlar için:

```bash
odoo -d <db> -i sd_edonusum_tr --stop-after-init
```

İleride bu modülün kurulu olduğu bir veritabanı bulunursa, `x_edonusum_uuid`
alanını çekirdeğin `l10n_tr_nilvera_uuid` alanına taşıyan bir `pre-migrate`
script'i yazılmalıdır.

## Kod neden silinmedi

Nilvera istemcisi, UBL ayrıştırıcısı ve senaryo alanları referans olarak duruyor;
`sd_edonusum_tr` geliştirilirken karşılaştırma için işe yarayabilir. Kurulamaz
olduğu için kimseye zarar vermez.
