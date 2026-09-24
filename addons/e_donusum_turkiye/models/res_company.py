# -*- coding: utf-8 -*-
"""
res.company extension for Multi-Integrator E-Dönüşüm Türkiye (Nilvera, Paraşüt, Uyumsoft).
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..tools.integrators import get_integrator, BaseIntegrator

class ResCompany(models.Model):
    _inherit = 'res.company'

    edonusum_provider = fields.Selection(
        [
            ('nilvera', 'Nilvera'),
            ('parasut', 'Paraşüt'),
            ('uyumsoft', 'Uyumsoft')
        ],
        string="E-Dönüşüm Entegratörü",
        default='nilvera',
        required=True,
        help="GİB E-Fatura ve E-Arşiv işlemlerinde kullanılacak entegratör."
    )

    # 1. Nilvera Ayarları
    nilvera_api_key = fields.Char(
        string="Nilvera API Anahtarı (Bearer)",
        help="Nilvera Geliştirici Portalından alınan API Anahtarı",
        copy=False
    )
    nilvera_environment = fields.Selection(
        [('production', 'Canlı (api.nilvera.com)'), ('test', 'Test / Sandbox (testapi.nilvera.com)')],
        string="Nilvera Ortamı",
        default='production'
    )

    # 2. Paraşüt Ayarları
    parasut_client_id = fields.Char(string="Paraşüt Client ID", copy=False)
    parasut_client_secret = fields.Char(string="Paraşüt Client Secret", copy=False)
    parasut_username = fields.Char(string="Paraşüt Kullanıcı Adı (E-posta)", copy=False)
    parasut_password = fields.Char(string="Paraşüt Şifre", copy=False)
    parasut_company_id = fields.Char(string="Paraşüt Firma ID", copy=False)

    # 3. Uyumsoft Ayarları
    uyumsoft_username = fields.Char(string="Uyumsoft Web Servis Kullanıcı Adı", copy=False)
    uyumsoft_password = fields.Char(string="Uyumsoft Web Servis Şifresi", copy=False)
    uyumsoft_environment = fields.Selection(
        [('prod', 'Canlı'), ('test', 'Test / Sandbox')],
        string="Uyumsoft Ortamı",
        default='prod'
    )

    # Ortak Otomasyon & Yasal Ayarlar
    edonusum_auto_sync = fields.Boolean(
        string="Otomatik Saatlik Senkronizasyon",
        default=True,
        help="Yeni gelen faturaları ve GİB durumlarını saatlik olarak otomatik çeker."
    )
    nilvera_auto_sync = fields.Boolean(
        related='edonusum_auto_sync',
        string="Otomatik Senkronizasyon (Uyumluluk)",
        readonly=False
    )
    edonusum_auto_accept_days = fields.Integer(
        string="Yasal Otomatik Kabul Süresi (Gün)",
        default=7,
        help="TTK m.21/2 uyarınca ticari faturaların otomatik onaylanacağı süre."
    )
    nilvera_auto_accept_days = fields.Integer(
        related='edonusum_auto_accept_days',
        string="Yasal Kabul Süresi (Uyumluluk)",
        readonly=False
    )
    edonusum_last_sync_date = fields.Datetime(
        string="Son Senkronizasyon Zamanı",
        readonly=True
    )
    nilvera_last_sync_date = fields.Datetime(
        related='edonusum_last_sync_date',
        string="Son Senkronizasyon (Uyumluluk)",
        readonly=True
    )

    def get_integrator(self) -> BaseIntegrator:
        """Returns initialized BaseIntegrator adapter for the company's chosen provider."""
        self.ensure_one()
        return get_integrator(self)

    def action_test_integrator_connection(self):
        """Tests connection with the selected integrator."""
        self.ensure_one()
        integrator = self.get_integrator()
        try:
            res = integrator.test_connection()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Bağlantı Başarılı"),
                    'message': _("%s Entegratör bağlantısı başarıyla doğrulandı: %s") % (self.edonusum_provider.capitalize(), res.get('message', '')),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("%s Bağlantı Hatası: %s") % (self.edonusum_provider.capitalize(), str(e)))

    # Backwards compatibility alias
    def action_test_nilvera_connection(self):
        return self.action_test_integrator_connection()

    def get_nilvera_client(self):
        integrator = self.get_integrator()
        if hasattr(integrator, 'client'):
            return integrator.client
        from ..tools.nilvera_client import NilveraClient
        return NilveraClient(api_key=self.nilvera_api_key or '', environment=self.nilvera_environment or 'production')
