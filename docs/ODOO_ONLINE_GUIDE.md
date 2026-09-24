# Odoo Online (SaaS) Kurulum ve Kullanım Kılavuzu

Odoo Online (SaaS) ortamında sunucuya Python dosyası yüklenemez. Bu kılavuz, `odoo_online_bridge` araçlarını kullanarak Odoo Online üzerinde Nilvera E-Dönüşüm özelliklerinin nasıl kurulacağını ve çalıştırılacağını açıklar.

---

## 1. Hızlı Otomatik Kurulum (Tek Komutla Provisioning)

`odoo_online_bridge/scripts/deploy_to_odoo_online.py` betiği, Odoo Online veri tabanınıza XML-RPC ile bağlanır ve gerekli tüm özel alanları, Server Action'ları ve otomatik zamanlanmış görevleri (ir.cron) oluşturur:

```bash
python odoo_online_bridge/scripts/deploy_to_odoo_online.py \
    --url https://sirketiniz.odoo.com \
    --db sirketiniz \
    --user admin@sirketiniz.com \
    --key odoo_api_anahtariniz
```

Bu işlem:
1. `account.move` modelinde `x_parasut_uuid`, `x_parasut_profile`, `x_parasut_status`, `x_tl_*` alanlarını açar.
2. `⚡ e-Fatura: Kabul Et (GİB)`, `❌ e-Fatura: Reddet (GİB)` ve `🔄 Nilvera: Fatura Durumunu Güncelle` Server Action'larını tanımlar.
3. Saatlik otomatik senkronizasyon ve 7 günlük yasal onay takibi cron'unu kurar.

---

## 2. Nilvera API Anahtarının Tanımlanması

Odoo Online arayüzünde:
1. **Ayarlar > Teknik > Parametreler > Sistem Parametreleri** menüsüne gidin.
2. Yeni parametre ekleyin:
   * **Anahtar (Key):** `nilvera_api_key` (veya çoklu şirkette `nilvera_api_key_1`, `nilvera_api_key_2`)
   * **Değer (Value):** Nilvera API Anahtarınız

---

## 3. Harici Senkronizasyon Servisi (Sync Daemon)

Faturaları Nilvera'dan düzenli çekmek, UBL XML ve PDF'lerini eklemek için hafif `odoo_online_sync_daemon.py` betiğini herhangi bir bilgisayarda, sunucuda veya Docker container içinde çalıştırabilirsiniz:

```bash
python odoo_online_bridge/scripts/odoo_online_sync_daemon.py
```
Bu servis Odoo Online veri tabanınıza arka planda bağlanarak faturayı, satırları, döviz kurlarını ve PDF eklerini otomatik olarak içe aktarır.

---

## 4. Kullanım

Odoo Online web arayüzünde herhangi bir faturayı açtığınızda üst barda şu butonlar yer alır:
* **⚡ e-Fatura: Kabul Et (GİB):** Doğrudan Odoo arayüzünden Nilvera API'ye `POST /einvoice/Purchase/SendAnswer` çağrısı yaparak GİB kabulü gönderir ve faturayı 'Kabul Edildi' yapar.
* **❌ e-Fatura: Reddet (GİB):** Nilvera API'ye ret gönderir ve faturayı 'Reddedildi' yapar.
* **🔄 GİB / Nilvera Durumunu Güncelle:** Nilvera portalından faturanın anlık yanıt durumunu çeker.
