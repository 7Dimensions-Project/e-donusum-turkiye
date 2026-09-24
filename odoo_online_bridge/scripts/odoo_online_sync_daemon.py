# -*- coding: utf-8 -*-
"""
Standalone Sync Daemon for Odoo Online (SaaS).
Runs outside of Odoo (e.g. Docker, systemd, local cron), connects to Odoo Online via XML-RPC
and Nilvera REST API, and continuously syncs inbound invoices, UBL lines, taxes, and PDFs.
"""

import os
import sys
import time
import base64
import logging
import xmlrpc.client
from datetime import datetime, timedelta

# Add parent path to import tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'addons', 'e_donusum_turkiye')))
from tools.nilvera_client import NilveraClient, NilveraAPIError
from tools.ubl_tr_parser import UBLTRParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_daemon")

class OdooOnlineSyncDaemon:
    def __init__(self, odoo_url, odoo_db, odoo_user, odoo_key, nilvera_key, company_id=1):
        self.odoo_url = odoo_url.rstrip('/')
        self.odoo_db = odoo_db
        self.odoo_user = odoo_user
        self.odoo_key = odoo_key
        self.company_id = company_id
        self.nilvera = NilveraClient(api_key=nilvera_key)

        common = xmlrpc.client.ServerProxy(f"{self.odoo_url}/xmlrpc/2/common")
        self.uid = common.authenticate(odoo_db, odoo_user, odoo_key, {})
        if not self.uid:
            raise ValueError("Odoo Online authentication failed!")
        self.models = xmlrpc.client.ServerProxy(f"{self.odoo_url}/xmlrpc/2/object")
        logger.info("Connected to Odoo Online successfully as UID %d", self.uid)

    def execute(self, model, method, *args, **kwargs):
        return self.models.execute_kw(self.odoo_db, self.uid, self.odoo_key, model, method, list(args), kwargs)

    def sync_recent_invoices(self, days=7):
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        logger.info("Fetching Nilvera inbound invoices since %s...", start_date)

        page = 1
        created_count = 0
        while True:
            res = self.nilvera.get_inbound_invoices(start_date=start_date, page=page, page_size=50)
            items = res.get('Content', []) or res.get('Items', [])
            if not items:
                break

            for item in items:
                uuid = item.get('UUID')
                if not uuid:
                    continue

                existing = self.execute('account.move', 'search_read',
                    [[('company_id', '=', self.company_id), '|', ('x_parasut_uuid', '=', uuid), ('ref', '=', item.get('InvoiceNumber'))]],
                    fields=['id', 'x_parasut_status']
                )

                if existing:
                    # Sync status if changed
                    st = (item.get('Status') or item.get('InvoiceStatus') or '').upper()
                    ans = (item.get('AnswerStatus') or '').upper()
                    new_st = None
                    if ans == 'KABUL' or 'KABUL' in st or 'ONAY' in st:
                        new_st = 'accepted'
                    elif ans == 'RED' or 'RED' in st:
                        new_st = 'rejected'

                    if new_st and existing[0].get('x_parasut_status') != new_st:
                        self.execute('account.move', 'write', [[existing[0]['id']], {'x_parasut_status': new_st}])
                        logger.info("Updated invoice %s status to %s", uuid, new_st)
                    continue

                # New invoice: fetch XML and PDF
                logger.info("Importing new invoice: %s (%s)", item.get('InvoiceNumber'), uuid)
                try:
                    xml_bytes = self.nilvera.get_inbound_invoice_xml(uuid)
                    parser = UBLTRParser(xml_bytes)
                    data = parser.parse()

                    # Find or create partner
                    partner_id = self._resolve_partner(data['supplier'])

                    # Prepare lines
                    line_cmds = []
                    for line in data['line_items']:
                        line_cmds.append((0, 0, {
                            'name': line['name'] or line['description'] or 'Ürün/Hizmet',
                            'quantity': line['quantity'],
                            'price_unit': line['price_unit']
                        }))

                    # Charge / Allowance
                    for ac in data.get('allowances_and_charges', []):
                        amt = ac.get('amount', 0.0)
                        if amt > 0:
                            is_charge = ac.get('is_charge', True)
                            line_cmds.append((0, 0, {
                                'name': 'Toplam Artırım (Yuvarlama Farkı)' if is_charge else 'Fatura Altı İskonto',
                                'quantity': 1.0,
                                'price_unit': amt if is_charge else -amt
                            }))

                    move_vals = {
                        'move_type': 'in_invoice' if data['doc_type'] == 'invoice' else 'in_refund',
                        'company_id': self.company_id,
                        'partner_id': partner_id,
                        'ref': data['invoice_number'],
                        'invoice_date': data['issue_date'],
                        'x_parasut_uuid': uuid,
                        'x_parasut_profile': data['profile_id'],
                        'x_parasut_status': 'waiting' if 'TICARI' in data['profile_id'] else 'accepted',
                        'invoice_line_ids': line_cmds
                    }

                    # Set currency if foreign
                    if data['currency_code'] != 'TRY':
                        curr = self.execute('res.currency', 'search_read', [[('name', '=', data['currency_code'])]], fields=['id'])
                        if curr:
                            move_vals['currency_id'] = curr[0]['id']

                    move_id = self.execute('account.move', 'create', [move_vals])

                    # Attach XML
                    self.execute('ir.attachment', 'create', [{
                        'name': f"{data['invoice_number']}.xml",
                        'type': 'binary',
                        'datas': base64.b64encode(xml_bytes).decode('utf-8'),
                        'res_model': 'account.move',
                        'res_id': move_id,
                        'mimetype': 'application/xml'
                    }])

                    # Attach PDF
                    try:
                        pdf_bytes = self.nilvera.get_inbound_invoice_pdf(uuid)
                        self.execute('ir.attachment', 'create', [{
                            'name': f"{data['invoice_number']}.pdf",
                            'type': 'binary',
                            'datas': base64.b64encode(pdf_bytes).decode('utf-8'),
                            'res_model': 'account.move',
                            'res_id': move_id,
                            'mimetype': 'application/pdf'
                        }])
                    except Exception:
                        pass

                    created_count += 1
                except Exception as e:
                    logger.error("Failed to import invoice %s: %s", uuid, e)

            page += 1

        logger.info("Sync finished. %d new invoices imported.", created_count)

    def _resolve_partner(self, supplier_info):
        vat = supplier_info.get('vat', '').strip()
        name = supplier_info.get('name', '').strip()
        if vat:
            existing = self.execute('res.partner', 'search_read', [[('vat', '=', vat)]], fields=['id'])
            if existing:
                return existing[0]['id']

        vals = {
            'name': name or f"Tedarikçi {vat}",
            'vat': vat,
            'is_company': len(vat) == 10
        }
        return self.execute('res.partner', 'create', [vals])

if __name__ == "__main__":
    print("Odoo Online Sync Daemon loaded.")
