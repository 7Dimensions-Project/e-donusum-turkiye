# -*- coding: utf-8 -*-
"""
res.company extension for Nilvera E-Dönüşüm configuration.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..tools.nilvera_client import NilveraClient, NilveraAPIError

class ResCompany(models.Model):
    _inherit = 'res.company'

    nilvera_api_key = fields.Char(
        string="Nilvera API Anahtarı (Bearer)",
        help="Nilvera Geliştirici Portalından alınan API Anahtarı",
        copy=False
    )
    nilvera_environment = fields.Selection(
        [('production', 'Canlı (api.nilvera.com)'), ('test', 'Test / Sandbox (testapi.nilvera.com)')],
        string="Nilvera Ortamı",
        default='production',
        required=True
    )
    nilvera_auto_sync = fields.Boolean(
        string="Otomatik Saatlik Senkronizasyon",
        default=True,
        help="Yeni gelen faturaları ve GİB durumlarını saatlik olarak otomatik çeker."
    )
    nilvera_auto_accept_days = fields.Integer(
        string="Yasal Otomatik Kabul Süresi (Gün)",
        default=7,
        help="TTK m.21/2 uyarınca ticari faturaların otomatik onaylanacağı süre."
    )
    nilvera_last_sync_date = fields.Datetime(
        string="Son Senkronizasyon Zamanı",
        readonly=True
    )

    def get_nilvera_client(self) -> NilveraClient:
        """Returns initialized NilveraClient instance for this company."""
        self.ensure_one()
        if not self.nilvera_api_key:
            raise UserError(_("Lütfen '%s' şirketi için Nilvera API Anahtarını tanımlayın.") % self.name)
        return NilveraClient(api_key=self.nilvera_api_key, environment=self.nilvera_environment)

    def action_test_nilvera_connection(self):
        """Tests the Nilvera API connection and credentials."""
        self.ensure_one()
        client = self.get_nilvera_client()
        try:
            # Test simple call: fetch 1 inbound invoice or status
            res = client.get_inbound_invoices(page=1, page_size=1)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Bağlantı Başarılı"),
                    'message': _("Nilvera API (%s) bağlantısı başarıyla doğrulandı.") % self.nilvera_environment,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except NilveraAPIError as e:
            raise UserError(_("Nilvera Bağlantı Hatası: %s") % str(e))
        except Exception as e:
            raise UserError(_("Beklenmeyen Bağlantı Hatası: %s") % str(e))
