# -*- coding: utf-8 -*-
"""
Odoo Online (SaaS) Server Action: 🔄 Nilvera / GİB Durumunu Güncelle
Model: account.move
Action Type: Execute Python Code (SafeEval)
Queries live status from Nilvera API and synchronizes with Odoo.
"""

import json
import requests

for record in records:
    uuid = record.x_parasut_uuid or getattr(record, 'x_edonusum_uuid', False)
    if not uuid:
        continue

    comp_id = record.company_id.id
    api_key = record.company_id.sudo().nilvera_api_key if hasattr(record.company_id, 'nilvera_api_key') else None
    if not api_key:
        api_key = env['ir.config_parameter'].sudo().get_param(f'nilvera_api_key_{comp_id}')
    if not api_key:
        api_key = env['ir.config_parameter'].sudo().get_param('nilvera_api_key')
    if not api_key:
        raise UserError("Nilvera API Anahtarı bulunamadı!")

    url = f"https://api.nilvera.com/einvoice/Purchase/{uuid}/Status"
    headers = {
        "Authorization": "Bearer " + api_key.strip(),
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
    except Exception as e:
        raise UserError("Nilvera Bağlantı Hatası: " + str(e))

    if r.status_code == 200:
        data = r.json()
        ans_status = (data.get('AnswerStatus') or '').upper()
        status_text = (data.get('Status') or data.get('InvoiceStatus') or '').upper()
        ans_note = data.get('AnswerNote') or ''

        vals = {}
        if ans_status == 'KABUL' or 'KABUL' in status_text or 'ONAY' in status_text:
            vals['x_parasut_status'] = 'accepted'
        elif ans_status == 'RED' or 'RED' in status_text:
            vals['x_parasut_status'] = 'rejected'
        elif 'IPTAL' in status_text:
            vals['x_parasut_status'] = 'cancelled'

        if ans_note:
            vals['x_parasut_answer_note'] = ans_note

        if vals:
            record.sudo().write(vals)
            record.message_post(body=f"🔄 <b>Nilvera Durumu Güncellendi:</b> {status_text} | Yanıt: {ans_status or 'Bekliyor'}")
    else:
        raise UserError(f"Nilvera Durum Sorgulama Hatası [{r.status_code}]: {r.text}")
