# -*- coding: utf-8 -*-
"""
res.partner extension for E-Dönüşüm Türkiye.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_is_einvoice_user = fields.Boolean(
        string="e-Fatura Mükellefi",
        default=False,
        help="Bu carinin GİB e-Fatura sistemine kayıtlı olup olmadığını belirtir."
    )
    x_tax_office = fields.Char(
        string="Vergi Dairesi"
    )
    x_einvoice_alias = fields.Char(
        string="Posta Kutusu / Gönderici Birim Etiketi (Alias)",
        help="GİB Posta Kutusu Etiketi (Örn: defaultpk, urn:mail:defaultgb)"
    )

    def action_check_einvoice_taxpayer(self):
        """Checks partner's taxpayer status via Nilvera API."""
        self.ensure_one()
        vkn = "".join(filter(str.isdigit, str(self.vat or '')))
        if not vkn or len(vkn) not in (10, 11):
            raise UserError(_("Lütfen carinin 10 haneli VKN veya 11 haneli TCKN numarasını girin."))

        company = self.env.company
        client = company.get_nilvera_client()
        try:
            res = client.check_taxpayer(vkn)
            is_user = bool(res and (res.get('IsTaxPayer') or res.get('Status')))
            self.write({
                'x_is_einvoice_user': is_user,
                'x_einvoice_alias': res.get('Alias') or self.x_einvoice_alias or ''
            })
            msg = _("Mükellef Durumu: %s") % (_("e-Fatura Kayıtlı") if is_user else _("e-Fatura Kayıtlı Değil (e-Arşiv)"))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("GİB Mükellef Sorgulama"),
                    'message': msg,
                    'type': 'success' if is_user else 'info',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("GİB Sorgulama Hatası: %s") % str(e))
