# -*- coding: utf-8 -*-
"""
Wizard to manually fetch E-Dönüşüm documents for a specific date range
supporting Nilvera, Paraşüt, and Uyumsoft.
"""

import base64
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..tools.ubl_tr_parser import UBLTRParser
from ..tools.ubl_tax_resolver import UBLTaxResolver

logger = logging.getLogger("fetch_invoices_wizard")

class FetchInvoicesWizard(models.TransientModel):
    _name = 'fetch.invoices.wizard'
    _description = 'E-Dönüşüm Fatura Çekme Sihirbazı'

    company_id = fields.Many2one(
        'res.company',
        string="Şirket",
        required=True,
        default=lambda self: self.env.company
    )
    date_start = fields.Date(
        string="Başlangıç Tarihi",
        required=True,
        default=lambda self: fields.Date.today()
    )
    date_end = fields.Date(
        string="Bitiş Tarihi",
        required=True,
        default=lambda self: fields.Date.today()
    )
    doc_type = fields.Selection(
        [
            ('inbound_invoice', 'Gelen e-Fatura'),
            ('earchive', 'e-Arşiv Faturalar'),
            ('esmm', 'e-SMM Makbuzları')
        ],
        string="Belge Türü",
        default='inbound_invoice',
        required=True
    )

    def action_fetch_invoices(self):
        """Executes document fetch from configured integrator."""
        self.ensure_one()
        integrator = self.company_id.get_integrator()
        start_str = str(self.date_start)
        end_str = str(self.date_end)

        created_count = 0
        updated_count = 0

        try:
            page = 1
            while True:
                res = integrator.get_inbound_invoices(start_date=start_str, end_date=end_str, page=page, page_size=50)
                items = res.get('items', [])
                if not items:
                    break

                for item in items:
                    uuid = item.get('UUID')
                    doc_id = item.get('ID') or uuid
                    if not uuid and not doc_id:
                        continue

                    # Check if already exists in Odoo
                    domain = [('company_id', '=', self.company_id.id)]
                    if uuid:
                        domain.append('|')
                        domain.append(('x_edonusum_uuid', '=', uuid))
                        domain.append(('x_parasut_uuid', '=', uuid))
                    else:
                        domain.append(('x_parasut_einvoice_id', '=', str(doc_id)))

                    existing = self.env['account.move'].search(domain, limit=1)

                    if existing:
                        st = item.get('Status')
                        if st:
                            existing.action_gib_update_status()
                        updated_count += 1
                        continue

                    # Fetch signed XML and parse
                    xml_bytes = integrator.get_inbound_invoice_xml(doc_id)
                    parser = UBLTRParser(xml_bytes)
                    data = parser.parse()

                    # Match or create partner
                    partner = self._find_or_create_partner(data['supplier'])

                    # Resolve taxes
                    tax_resolver = UBLTaxResolver(self.env)

                    # Create draft move
                    move_vals = {
                        'move_type': 'in_invoice' if data['doc_type'] == 'invoice' else 'in_refund',
                        'company_id': self.company_id.id,
                        'partner_id': partner.id,
                        'ref': data['invoice_number'],
                        'invoice_date': data['issue_date'],
                        'x_edonusum_uuid': data.get('uuid') or uuid,
                        'x_parasut_einvoice_id': str(doc_id) if item.get('ID') else False,
                        'x_edonusum_profile': data['profile_id'],
                        'x_edonusum_type_code': data['invoice_type_code'],
                        'x_edonusum_status': 'waiting' if 'TICARI' in data['profile_id'] else 'accepted',
                        'invoice_line_ids': []
                    }

                    # Find currency
                    curr_name = data['currency_code']
                    curr = self.env['res.currency'].search([('name', '=', curr_name)], limit=1)
                    if curr:
                        move_vals['currency_id'] = curr.id

                    # Line items
                    for line in data['line_items']:
                        tax_ids = tax_resolver.resolve_line_taxes(
                            line_tax_nodes=line['taxes'],
                            line_withholding=line.get('withholding'),
                            company_id=self.company_id.id,
                            is_purchase=True
                        )
                        move_vals['invoice_line_ids'].append((0, 0, {
                            'name': line['name'] or line['description'] or 'Hizmet/Ürün',
                            'quantity': line['quantity'],
                            'price_unit': line['price_unit'],
                            'tax_ids': [(6, 0, tax_ids)],
                            'x_seller_item_code': line['seller_item_code'],
                            'x_discount_amount': line['discount_amount'],
                            'x_charge_amount': line['charge_amount']
                        }))

                    # Allowances & Charges
                    for ac in data.get('allowances_and_charges', []):
                        amt = ac.get('amount', 0.0)
                        if amt > 0:
                            is_charge = ac.get('is_charge', True)
                            move_vals['invoice_line_ids'].append((0, 0, {
                                'name': 'Toplam Artırım (Yuvarlama Farkı)' if is_charge else 'Fatura Altı İskonto',
                                'quantity': 1.0,
                                'price_unit': amt if is_charge else -amt,
                                'tax_ids': [(6, 0, [])]
                            }))

                    new_move = self.env['account.move'].create(move_vals)

                    # Attach XML
                    self.env['ir.attachment'].create({
                        'name': f"{data['invoice_number']}.xml",
                        'type': 'binary',
                        'datas': base64.b64encode(xml_bytes),
                        'res_model': 'account.move',
                        'res_id': new_move.id,
                        'mimetype': 'application/xml'
                    })

                    # Attach PDF
                    try:
                        pdf_bytes = integrator.get_inbound_invoice_pdf(doc_id)
                        self.env['ir.attachment'].create({
                            'name': f"{data['invoice_number']}.pdf",
                            'type': 'binary',
                            'datas': base64.b64encode(pdf_bytes),
                            'res_model': 'account.move',
                            'res_id': new_move.id,
                            'mimetype': 'application/pdf'
                        })
                    except Exception:
                        pass

                    created_count += 1

                page += 1

            provider_title = self.company_id.edonusum_provider.capitalize()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("%s Fatura Çekme Tamamlandı") % provider_title,
                    'message': _("%d yeni fatura oluşturuldu, %d fatura güncellendi.") % (created_count, updated_count),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            raise UserError(_("Fatura çekme sırasında hata oluştu: %s") % str(e))

    def _find_or_create_partner(self, supplier_info: dict):
        vat = supplier_info.get('vat', '').strip()
        name = supplier_info.get('name', '').strip()
        if vat:
            partner = self.env['res.partner'].search([
                ('vat', '=', vat),
                '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
            ], limit=1)
            if partner:
                return partner

        vals = {
            'name': name or f"Tedarikçi {vat}",
            'vat': vat,
            'is_company': len(vat) == 10,
            'company_id': False,
            'x_is_einvoice_user': True
        }
        addr = supplier_info.get('address', {})
        if addr:
            vals.update({
                'street': addr.get('street', ''),
                'city': addr.get('city', ''),
                'zip': addr.get('postal_zone', '')
            })
        return self.env['res.partner'].create(vals)
