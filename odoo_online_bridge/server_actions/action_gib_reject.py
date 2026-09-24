# -*- coding: utf-8 -*-
"""
Odoo Online (SaaS) Server Action: ❌ e-Fatura: Reddet (GİB)
Model: account.move
Action Type: Execute Python Code (SafeEval)
Directly callable via header button in Odoo Online without custom addons!
"""

import json
import requests

for record in records:
    # 1. UUID & Nilvera API Key Kontrolü
    uuid = record.x_parasut_uuid or getattr(record, 'x_edonusum_uuid', False)
    if not uuid:
        raise UserError("Bu faturanın E-Dönüşüm / Nilvera UUID değeri bulunamadı!")

    # 2. Senaryo Kontrolü
    profile = (record.x_parasut_profile or getattr(record, 'x_edonusum_profile', '') or '').upper()
    if 'TEMEL' in profile:
        raise UserError("Temel Faturalar için GİB mevzuatı gereği KABUL veya RED uygulama yanıtı verilemez!")

    # 3. Şirket API Key Kontrolü
    comp_id = record.company_id.id
    api_key = record.company_id.sudo().nilvera_api_key if hasattr(record.company_id, 'nilvera_api_key') else None
    if not api_key:
        api_key = env['ir.config_parameter'].sudo().get_param(f'nilvera_api_key_{comp_id}')
    if not api_key:
        api_key = env['ir.config_parameter'].sudo().get_param('nilvera_api_key')
    if not api_key:
        raise UserError("Nilvera API Anahtarı bulunamadı! Lütfen şirket ayarlarından veya Sistem Parametrelerinden API anahtarını tanımlayın.")

    # 4. Nilvera SendAnswer API Çağrısı (RED)
    url = "https://api.nilvera.com/einvoice/Purchase/SendAnswer"
    headers = {
        "Authorization": "Bearer " + api_key.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "UUID": uuid,
        "Status": "RED",
        "Reason": "Fatura içeriğindeki tutar/hizmet uyuşmazlığı nedeniyle reddedilmiştir."
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
    except Exception as e:
        raise UserError("Nilvera API Bağlantı Hatası: " + str(e))

    if r.status_code in (200, 201, 202, 204):
        record.sudo().write({
            'x_parasut_status': 'rejected',
            'x_parasut_answer_note': 'GİB üzerinden reddedildi.'
        })
        record.message_post(body="❌ <b>GİB Uygulama Yanıtı:</b> Fatura Nilvera/GİB üzerinden başarıyla <b>REDDEDİLDİ</b>.")
    elif r.status_code == 409:
        record.sudo().write({
            'x_parasut_status': 'rejected'
        })
        record.message_post(body="ℹ️ <b>GİB Durumu:</b> Fatura Nilvera portalında zaten reddedilmiş görünüyor. Odoo durumu güncellendi.")
    else:
        err_msg = "Nilvera Hata Yanıtı [" + str(r.status_code) + "]: " + r.text
        raise UserError("GİB Red Yanıtı Gönderilemedi!\n\n" + err_msg)
