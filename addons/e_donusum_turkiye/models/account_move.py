# -*- coding: utf-8 -*-
"""
account.move extension for E-Dönüşüm Türkiye (Nilvera & GİB).
"""

import base64
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..tools.nilvera_client import NilveraClient, NilveraAPIError
from ..tools.ubl_tr_parser import UBLTRParser
from ..tools.ubl_tax_resolver import UBLTaxResolver

logger = logging.getLogger("e_donusum.account_move")

class AccountMove(models.Model):
    _inherit = 'account.move'

    x_edonusum_uuid = fields.Char(
        string="E-Fatura / E-Arşiv UUID",
        copy=False,
        index=True,
        help="GİB Evrensel Benzersiz Tanımlayıcısı (UUID)"
    )
    # Backward compatibility with existing fields
    x_parasut_uuid = fields.Char(
        related='x_edonusum_uuid',
        string="UUID (Uyumluluk)",
        store=True,
        readonly=False
    )
    x_edonusum_profile = fields.Selection(
        [
            ('TICARIFATURA', 'Ticari Fatura'),
            ('TEMELFATURA', 'Temel Fatura'),
            ('EARSIVFATURA', 'e-Arşiv Fatura'),
            ('IHRACAT', 'İhracat Faturası'),
            ('YOLCUBERABERFATURA', 'Yolcu Beraber Fatura'),
            ('KAMU', 'Kamu Faturası')
        ],
        string="GİB Senaryosu",
        default='TICARIFATURA',
        help="GİB Fatura Senaryosu"
    )
    x_parasut_profile = fields.Char(
        string="Senaryo (Uyumluluk)",
        help="Senaryo metin alanı"
    )
    x_edonusum_type_code = fields.Selection(
        [
            ('SATIS', 'Satış'),
            ('IADE', 'İade'),
            ('TEVKIFAT', 'Tevkifat'),
            ('ISTISNA', 'İstisna'),
            ('OZELMATRAH', 'Özel Matrah'),
            ('IHRACKAYITLI', 'İhraç Kayıtlı')
        ],
        string="GİB Fatura Tipi",
        default='SATIS'
    )
    x_edonusum_status = fields.Selection(
        [
            ('draft', 'Taslak'),
            ('waiting', 'GİB Onay Bekliyor'),
            ('accepted', 'Kabul Edildi'),
            ('rejected', 'Reddedildi'),
            ('cancelled', 'İptal Edildi'),
            ('auto_accepted', 'Yasal Olarak Onaylandı (7 Gün)')
        ],
        string="E-Dönüşüm Durumu",
        default='draft',
        copy=False,
        index=True
    )
    x_parasut_status = fields.Selection(
        [
            ('draft', 'Taslak'),
            ('waiting', 'GİB Onay Bekliyor'),
            ('accepted', 'Kabul Edildi'),
            ('rejected', 'Reddedildi'),
            ('cancelled', 'İptal Edildi'),
            ('auto_accepted', 'Yasal Olarak Onaylandı (7 Gün)')
        ],
        related='x_edonusum_status',
        string="Durum (Uyumluluk)",
        store=True,
        readonly=False
    )
    x_edonusum_gib_date = fields.Date(
        string="GİB Gönderim Tarihi",
        readonly=True
    )
    x_edonusum_answer_note = fields.Text(
        string="Uygulama Yanıtı Notu",
        readonly=True
    )
    x_edonusum_answer_status = fields.Char(
        string="GİB Son Durum Kodu",
        readonly=True
    )

    # Multi-currency (FX) side-by-side TL totals
    x_tl_untaxed = fields.Monetary(
        string="TL Matrah",
        currency_field='company_currency_id',
        readonly=True
    )
    x_tl_tax = fields.Monetary(
        string="TL Vergi",
        currency_field='company_currency_id',
        readonly=True
    )
    x_tl_total = fields.Monetary(
        string="TL Toplam",
        currency_field='company_currency_id',
        readonly=True
    )
    x_tl_rate = fields.Float(
        string="Fatura Kuru (TCMB)",
        digits=(12, 4),
        readonly=True
    )
    x_tl_rate_text = fields.Char(
        string="Döviz & Kur Bilgisi",
        readonly=True
    )

    is_foreign_currency = fields.Boolean(
        string="Dövizli Fatura mı?",
        compute='_compute_is_foreign_currency'
    )

    @api.depends('currency_id', 'company_id.currency_id')
    def _compute_is_foreign_currency(self):
        for move in self:
            move.is_foreign_currency = (
                move.currency_id and
                move.company_id and
                move.currency_id.id != move.company_id.currency_id.id
            )

    # -------------------------------------------------------------------------
    # Actions: KABUL, RED, GİB Durumu Güncelle
    # -------------------------------------------------------------------------

    def action_gib_accept(self):
        """Sends KABUL application response to GİB via Nilvera."""
        self.ensure_one()
        uuid = self.x_edonusum_uuid or self.x_parasut_uuid
        if not uuid:
            raise UserError(_("Bu faturanın E-Dönüşüm UUID değeri bulunamadı."))

        # Check scenario
        profile = (self.x_edonusum_profile or self.x_parasut_profile or '').upper()
        if 'TEMEL' in profile:
            raise UserError(_("Temel Faturalar için GİB mevzuatı gereği KABUL/RED yanıtı gönderilemez."))

        client = self.company_id.get_nilvera_client()
        try:
            res = client.send_answer(uuid=uuid, status='KABUL')
            self.write({
                'x_edonusum_status': 'accepted',
                'x_edonusum_answer_note': 'GİB üzerinden kabul edildi.'
            })
            self.message_post(body=_("⚡ <b>GİB Uygulama Yanıtı:</b> Fatura Nilvera/GİB üzerinden KABUL edildi."))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Fatura Kabul Edildi"),
                    'message': _("KABUL yanıtı başarıyla GİB'e iletildi."),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except NilveraAPIError as ne:
            raise UserError(_("Nilvera Kabul Hatası: %s") % str(ne))

    def action_gib_reject(self):
        """Sends RED application response to GİB via Nilvera."""
        self.ensure_one()
        uuid = self.x_edonusum_uuid or self.x_parasut_uuid
        if not uuid:
            raise UserError(_("Bu faturanın E-Dönüşüm UUID değeri bulunamadı."))

        profile = (self.x_edonusum_profile or self.x_parasut_profile or '').upper()
        if 'TEMEL' in profile:
            raise UserError(_("Temel Faturalar için GİB mevzuatı gereği KABUL/RED yanıtı gönderilemez."))

        client = self.company_id.get_nilvera_client()
        try:
            res = client.send_answer(uuid=uuid, status='RED', reason='Ticari anlaşmazlık / Hatalı fatura')
            self.write({
                'x_edonusum_status': 'rejected',
                'x_edonusum_answer_note': 'GİB üzerinden reddedildi.'
            })
            self.message_post(body=_("❌ <b>GİB Uygulama Yanıtı:</b> Fatura Nilvera/GİB üzerinden REDDEDİLDİ."))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Fatura Reddedildi"),
                    'message': _("RED yanıtı başarıyla GİB'e iletildi."),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        except NilveraAPIError as ne:
            raise UserError(_("Nilvera Red Hatası: %s") % str(ne))

    def action_gib_update_status(self):
        """Queries current status from Nilvera API and synchronizes with Odoo."""
        self.ensure_one()
        uuid = self.x_edonusum_uuid or self.x_parasut_uuid
        if not uuid:
            raise UserError(_("Bu faturanın E-Dönüşüm UUID değeri bulunamadı."))

        client = self.company_id.get_nilvera_client()
        try:
            data = client.get_inbound_invoice_status(uuid)
            status_text = (data.get('Status') or data.get('InvoiceStatus') or '').upper()
            answer_status = (data.get('AnswerStatus') or '').upper()
            answer_note = data.get('AnswerNote') or ''

            vals = {}
            if answer_status == 'KABUL' or 'KABUL' in status_text or 'ONAY' in status_text:
                vals['x_edonusum_status'] = 'accepted'
            elif answer_status == 'RED' or 'RED' in status_text:
                vals['x_edonusum_status'] = 'rejected'
            elif 'IPTAL' in status_text:
                vals['x_edonusum_status'] = 'cancelled'

            if answer_note:
                vals['x_edonusum_answer_note'] = answer_note
            if status_text:
                vals['x_edonusum_answer_status'] = status_text

            if vals:
                self.write(vals)
                self.message_post(body=_(
                    "🔄 <b>Nilvera Durumu Güncellendi:</b> %s | Uygulama Yanıtı: %s"
                ) % (status_text, answer_status or "Bekliyor"))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("GİB Durumu Güncellendi"),
                    'message': _("Durum: %s | Yanıt: %s") % (status_text, answer_status or "Belirtilmemiş"),
                    'type': 'info',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("Durum sorgulama hatası: %s") % str(e))

    def action_download_nilvera_pdf(self):
        """Downloads official PDF visual and attaches to the record."""
        self.ensure_one()
        uuid = self.x_edonusum_uuid or self.x_parasut_uuid
        if not uuid:
            raise UserError(_("Fatura UUID değeri bulunamadı."))

        client = self.company_id.get_nilvera_client()
        pdf_bytes = client.get_inbound_invoice_pdf(uuid)
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name or uuid}.pdf",
            'type': 'binary',
            'datas': base64.b64encode(pdf_bytes),
            'res_model': 'account.move',
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        self.message_post(body=_("📄 Resmi e-Fatura görseli PDF olarak eklendi."), attachment_ids=[attachment.id])
        return True

    def action_download_nilvera_xml(self):
        """Downloads signed UBL-TR XML and attaches to the record."""
        self.ensure_one()
        uuid = self.x_edonusum_uuid or self.x_parasut_uuid
        if not uuid:
            raise UserError(_("Fatura UUID değeri bulunamadı."))

        client = self.company_id.get_nilvera_client()
        xml_bytes = client.get_inbound_invoice_xml(uuid)
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name or uuid}.xml",
            'type': 'binary',
            'datas': base64.b64encode(xml_bytes),
            'res_model': 'account.move',
            'res_id': self.id,
            'mimetype': 'application/xml'
        })
        self.message_post(body=_("📦 İmzalı UBL-TR XML dosyası eklendi."), attachment_ids=[attachment.id])
        return True

    # -------------------------------------------------------------------------
    # Cron Jobs
    # -------------------------------------------------------------------------

    @api.model
    def cron_sync_all_nilvera_invoices(self):
        """Scheduled action: Polls new inbound invoices for all active companies."""
        companies = self.env['res.company'].search([
            ('nilvera_api_key', '!=', False),
            ('nilvera_auto_sync', '=', True)
        ])
        for comp in companies:
            try:
                comp.with_user(1)._sync_company_nilvera_invoices()
            except Exception as e:
                logger.error("Error syncing Nilvera for company %s: %s", comp.name, e)

    @api.model
    def cron_check_7day_legal_acceptance(self):
        """
        TTK m.21/2: Invoices waiting for commercial answer older than 7 days
        are legally accepted by default.
        """
        cutoff_date = fields.Date.today() - timedelta(days=7)
        invoices = self.search([
            ('move_type', '=', 'in_invoice'),
            ('x_edonusum_status', '=', 'waiting'),
            ('invoice_date', '<=', cutoff_date)
        ])
        for inv in invoices:
            inv.write({
                'x_edonusum_status': 'auto_accepted',
                'x_edonusum_answer_note': 'TTK m.21/2 uyarınca 7 gün içinde itiraz edilmediği için kanunen onaylandı.'
            })
            inv.message_post(body=_("⚖️ <b>Yasal Kabul:</b> Fatura 7 günlük yasal itiraz süresi dolduğu için onaylanmıştır."))
