# Odoo.sh ve On-Premise Kurulum Kılavuzu

Bu kılavuz, `e_donusum_turkiye` modülünün **Odoo.sh** veya **On-Premise (Kendi Sunucunuz)** ortamlarında nasıl kurulacağını ve yapılandırılacağını açıklar.

---

## 1. Modülü Eklemek

### Odoo.sh Ortamı
1. Odoo.sh projenizin GitHub deposunda bu depoyu bir submodule olarak veya `addons` klasörünüzün içine ekleyin:
   ```bash
   git submodule add https://github.com/7Dimensions-Project/e-donusum-turkiye.git addons/e-donusum-turkiye
   ```
2. Odoo.sh yapılandırmasında `addons_path` listesine `addons/e-donusum-turkiye/addons` yolunu ekleyin.

### On-Premise / Docker Ortamı
Modül klasörünü Odoo `addons` yolunuza kopyalayın veya bağlayın:
```bash
cp -r repos/e-donusum-turkiye/addons/e_donusum_turkiye /opt/odoo/custom_addons/
```
`odoo.conf` dosyanızda:
```ini
addons_path = /opt/odoo/odoo/addons,/opt/odoo/custom_addons
```

---

## 2. Modülü Yüklemek

1. Odoo'ya yönetici olarak giriş yapın.
2. **Geliştirici Modunu (Developer Mode)** etkinleştirin.
3. **Uygulamalar** menüsüne gidin ve **Uygulama Listesini Güncelle** butonuna tıklayın.
4. Arama çubuğuna `e_donusum_turkiye` veya `Türkiye E-Dönüşüm` yazın ve **Yükle** butonuna tıklayın.

---

## 3. Şirket Ayarlarını Yapılandırmak

1. **Ayarlar > Şirketler** menüsünden şirketinizi açın.
2. **E-Dönüşüm (Nilvera)** sekmesine gelin:
   * **Nilvera API Anahtarı:** Nilvera portalından aldığınız API Key'i girin.
   * **Nilvera Ortamı:** `Canlı` veya `Test` seçin.
   * **Bağlantıyı Test Et:** Butona basarak API anahtarının doğruluğunu onaylayın.
   * **Otomatik Senkronizasyon:** Açık bırakın (Her saat başı yeni faturaları ve GİB yanıtlarını çeker).
   * **Yasal Otomatik Kabul Süresi:** Varsayılan 7 gün.

---

## 4. Kullanım

* **Faturaları Çekmek:** **E-Dönüşüm > İşlemler > Nilvera'dan Fatura Çek** sihirbazı ile dilediğiniz tarih aralığındaki faturaları tek tıkla çekebilirsiniz.
* **Kabul / Red Yanıtı:** Gelen bir ticari faturayı açıp üst bardaki **⚡ e-Fatura: Kabul Et (GİB)** veya **❌ e-Fatura: Reddet (GİB)** butonuna basarak doğrudan GİB yanıtı iletebilirsiniz.
