# -*- coding: utf-8 -*-
"""
One-Click Provisioner for Odoo Online (SaaS).
Automatically creates required custom fields, server actions, views, and crons
in any standard Odoo Online database via XML-RPC.
"""

import sys
import argparse
import xmlrpc.client

def main():
    parser = argparse.ArgumentParser(description="Deploy E-Dönüşüm Türkiye to Odoo Online (SaaS)")
    parser.add_argument("--url", required=True, help="Odoo Online URL (e.g. https://mycompany.odoo.com)")
    parser.add_argument("--db", required=True, help="Odoo Database Name")
    parser.add_argument("--user", required=True, help="Admin User Email/Login")
    parser.add_argument("--key", required=True, help="Odoo API Key or Password")
    args = parser.parse_args()

    print(f"Connecting to Odoo Online at {args.url}...")
    common = xmlrpc.client.ServerProxy(f"{args.url.rstrip('/')}/xmlrpc/2/common")
    uid = common.authenticate(args.db, args.user, args.key, {})
    if not uid:
        print("Error: Authentication failed! Please check credentials.")
        sys.exit(1)
    print(f"Authenticated successfully as UID: {uid}")

    models = xmlrpc.client.ServerProxy(f"{args.url.rstrip('/')}/xmlrpc/2/object")
    kw = (args.db, uid, args.key)

    # 1. Custom Fields on account.move
    print("\n1. Checking and creating custom fields on account.move...")
    fields_to_ensure = [
        {'name': 'x_parasut_uuid', 'field_description': 'E-Fatura UUID', 'ttype': 'char', 'index': True},
        {'name': 'x_parasut_profile', 'field_description': 'GİB Senaryosu', 'ttype': 'char'},
        {'name': 'x_parasut_status', 'field_description': 'E-Dönüşüm Durumu', 'ttype': 'selection',
         'selection': "[('draft','Taslak'),('waiting','GİB Onay Bekliyor'),('accepted','Kabul Edildi'),('rejected','Reddedildi'),('cancelled','İptal Edildi'),('auto_accepted','Yasal Olarak Onaylandı (7 Gün)')]"},
        {'name': 'x_parasut_answer_note', 'field_description': 'Uygulama Yanıtı Notu', 'ttype': 'text'},
        {'name': 'x_tl_untaxed', 'field_description': 'TL Matrah', 'ttype': 'monetary'},
        {'name': 'x_tl_tax', 'field_description': 'TL Vergi', 'ttype': 'monetary'},
        {'name': 'x_tl_total', 'field_description': 'TL Toplam', 'ttype': 'monetary'},
        {'name': 'x_tl_rate', 'field_description': 'Döviz Kuru', 'ttype': 'float'},
        {'name': 'x_tl_rate_text', 'field_description': 'Kur Bilgisi', 'ttype': 'char'},
    ]

    move_model = models.execute_kw(*kw, 'ir.model', 'search_read', [[('model', '=', 'account.move')]], {'fields': ['id']})
    model_id = move_model[0]['id']

    for f in fields_to_ensure:
        exists = models.execute_kw(*kw, 'ir.model.fields', 'search', [[('model_id', '=', model_id), ('name', '=', f['name'])]])
        if not exists:
            f['model_id'] = model_id
            models.execute_kw(*kw, 'ir.model.fields', 'create', [f])
            print(f"Created field: {f['name']}")
        else:
            print(f"Field already exists: {f['name']}")

    # 2. Server Actions
    print("\n2. Deploying Server Actions...")
    actions = [
        {
            'name': '⚡ e-Fatura: Kabul Et (GİB)',
            'code': open(r'odoo_online_bridge/server_actions/action_gib_accept.py', encoding='utf-8').read()
        },
        {
            'name': '❌ e-Fatura: Reddet (GİB)',
            'code': open(r'odoo_online_bridge/server_actions/action_gib_reject.py', encoding='utf-8').read()
        },
        {
            'name': '🔄 Nilvera: Fatura Durumunu Güncelle',
            'code': open(r'odoo_online_bridge/server_actions/action_gib_sync_status.py', encoding='utf-8').read()
        }
    ]

    for act in actions:
        found = models.execute_kw(*kw, 'ir.actions.server', 'search', [[('model_id', '=', model_id), ('name', '=', act['name'])]])
        vals = {
            'name': act['name'],
            'model_id': model_id,
            'state': 'code',
            'code': act['code']
        }
        if found:
            models.execute_kw(*kw, 'ir.actions.server', 'write', [found, vals])
            print(f"Updated server action: {act['name']}")
        else:
            models.execute_kw(*kw, 'ir.actions.server', 'create', [vals])
            print(f"Created server action: {act['name']}")

    # 3. Scheduled Action (Cron)
    print("\n3. Setting up Scheduled Action (ir.cron)...")
    cron_name = "Nilvera E-Dönüşüm: Saatlik Senkronizasyon & 7 Günlük Yasal Onay"
    cron_code = open(r'odoo_online_bridge/server_actions/cron_hourly_sync.py', encoding='utf-8').read()
    cron_found = models.execute_kw(*kw, 'ir.cron', 'search', [[('name', '=', cron_name)]])
    cron_vals = {
        'name': cron_name,
        'model_id': model_id,
        'state': 'code',
        'code': cron_code,
        'interval_number': 1,
        'interval_type': 'hours',
        'numbercall': -1,
        'active': True
    }
    if cron_found:
        models.execute_kw(*kw, 'ir.cron', 'write', [cron_found, cron_vals])
        print("Updated scheduled action.")
    else:
        models.execute_kw(*kw, 'ir.cron', 'create', [cron_vals])
        print("Created scheduled action.")

    print("\n=== Deployment to Odoo Online Complete! ===")

if __name__ == "__main__":
    main()
