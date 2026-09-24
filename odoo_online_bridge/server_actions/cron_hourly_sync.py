# -*- coding: utf-8 -*-
"""
Odoo Online (SaaS) Scheduled Action: Nilvera Hourly Sync & Status Polling
Model: account.move
Action Type: Execute Python Code (SafeEval)
Runs every hour in Odoo Online SaaS to check portal answers and legal 7-day acceptance.
"""

import datetime
import requests

# 1. Bekleyen Ticari Faturaların Nilvera Portal Durumunu Sorgula
waiting_moves = env['account.move'].search([
    ('move_type', '=', 'in_invoice'),
    ('x_parasut_status', '=', 'waiting'),
    ('x_parasut_uuid', '!=', False)
], limit=30)

for move in waiting_moves:
    try:
        comp_id = move.company_id.id
        api_key = env['ir.config_parameter'].sudo().get_param(f'nilvera_api_key_{comp_id}')
        if not api_key:
            api_key = env['ir.config_parameter'].sudo().get_param('nilvera_api_key')
        if not api_key:
            continue

        url = f"https://api.nilvera.com/einvoice/Purchase/{move.x_parasut_uuid}/Status"
        headers = {"Authorization": "Bearer " + api_key.strip(), "Accept": "application/json"}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            d = r.json()
            ans = (d.get('AnswerStatus') or '').upper()
            st = (d.get('Status') or d.get('InvoiceStatus') or '').upper()
            if ans == 'KABUL' or 'KABUL' in st or 'ONAY' in st:
                move.sudo().write({'x_parasut_status': 'accepted'})
                move.message_post(body="🔄 <b>Nilvera Senkronizasyonu:</b> Faturanın portal üzerinden KABUL edildiği algılandı.")
            elif ans == 'RED' or 'RED' in st:
                move.sudo().write({'x_parasut_status': 'rejected'})
                move.message_post(body="❌ <b>Nilvera Senkronizasyonu:</b> Faturanın portal üzerinden REDDEDİLDİĞİ algılandı.")
    except Exception as e:
        pass

# 2. 7 Günlük Yasal İtiraz Süresi Kontrolü (TTK m.21/2)
cutoff = datetime.date.today() - datetime.timedelta(days=7)
expired_moves = env['account.move'].search([
    ('move_type', '=', 'in_invoice'),
    ('x_parasut_status', '=', 'waiting'),
    ('invoice_date', '<=', cutoff)
])

for move in expired_moves:
    move.sudo().write({
        'x_parasut_status': 'auto_accepted',
        'x_parasut_answer_note': 'TTK m.21/2 uyarınca 7 gün içinde itiraz edilmediği için kanunen onaylandı.'
    })
    move.message_post(body="⚖️ <b>Yasal Kabul:</b> Fatura 7 günlük yasal itiraz süresi dolduğu için kanunen onaylandı.")
