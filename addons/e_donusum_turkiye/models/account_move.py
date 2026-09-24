# -*- coding: utf-8 -*-
"""
account.move extension for Multi-Integrator E-Dönüşüm Türkiye (Nilvera, Paraşüt, Uyumsoft).
"""

import base64
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..tools.integrators import BaseIntegrator

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
    x_parasut_einvoice_id = fields.Char(
        string="Paraşüt e-Fatura ID",
        copy=False,
        help="Paraşüt API e_invoices tekil ID'si"
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
    x_parasut_answer_note = fields.Text(
        related='x_edonusum_answer_note',
        string="Uygulama Yanıtı Notu (Uyumluluk)",
        readonly=False
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

    def _get_target_doc_identifier(self):
        """Returns the appropriate document ID or UUID based on integrator."""
        provider = self.company_id.edonusum_provider
        if provider == 'parasut' and self.x_parasut_einvoice_id:
            return self.x_parasut_einvoice_id
        return self.x_edonusum_uuid or self.x_parasut_uuid

    # -------------------------------------------------------------------------
    # Actions: KABUL, RED, GİB Durumu Güncelle
    # -------------------------------------------------------------------------

    def action_gib_accept(self):
        """Sends KABUL application response to GİB via configured integrator."""
        self.ensure_one()
        doc_id = self._get_target_doc_identifier()
        if not doc_id:
            raise UserError(_("Bu faturanın E-Dönüşüm Belge / UUID değeri bulunamadı."))

        # Check scenario
        profile = (self.x_edonusum_profile or self.x_parasut_profile or '').upper()
        if 'TEMEL' in profile:
            raise UserError(_("Temel Faturalar için GİB mevzuatı gereği KABUL/RED yanıtı gönderilemez."))

        integrator = self.company_id.get_integrator()
        try:
            res = integrator.send_answer(doc_uuid_or_id=doc_id, status='KABUL')
            self.write({
                'x_edonusum_status': 'accepted',
                'x_edonusum_answer_note': 'GİB üzerinden kabul edildi.'
            })
            provider_title = self.company_id.edonusum_provider.capitalize()
            self.message_post(body=_("⚡ <b>GİB Uygulama Yanıtı:</b> Fatura %s/GİB üzerinden başarıyla KABUL edildi.") % provider_title)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Fatura Kabul Edildi"),
                    'message': _("KABUL yanıtı %s üzerinden GİB'e iletildi.") % provider_title,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("%s Kabul Hatası: %s") % (self.company_id.edonusum_provider.capitalize(), str(e)))

    def action_gib_reject(self):
        """Sends RED application response to GİB via configured integrator."""
        self.ensure_one()
        doc_id = self._get_target_doc_identifier()
        if not doc_id:
            raise UserError(_("Bu faturanın E-Dönüşüm Belge / UUID değeri bulunamadı."))

        profile = (self.x_edonusum_profile or self.x_parasut_profile or '').upper()
        if 'TEMEL' in profile:
            raise UserError(_("Temel Faturalar için GİB mevzuatı gereği KABUL/RED yanıtı gönderilemez."))

        integrator = self.company_id.get_integrator()
        try:
            res = integrator.send_answer(doc_uuid_or_id=doc_id, status='RED', reason='Ticari anlaşmazlık / Hatalı fatura')
            self.write({
                'x_edonusum_status': 'rejected',
                'x_edonusum_answer_note': 'GİB üzerinden reddedildi.'
            })
            provider_title = self.company_id.edonusum_provider.capitalize()
            self.message_post(body=_("❌ <b>GİB Uygulama Yanıtı:</b> Fatura %s/GİB üzerinden REDDEDİLDİ.") % provider_title)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Fatura Reddedildi"),
                    'message': _("RED yanıtı %s üzerinden GİB'e iletildi.") % provider_title,
                    'type': 'warning',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("%s Red Hatası: %s") % (self.company_id.edonusum_provider.capitalize(), str(e)))

    def action_gib_update_status(self):
        """Queries current status from integrator API and synchronizes with Odoo."""
        self.ensure_one()
        doc_id = self._get_target_doc_identifier()
        if not doc_id:
            raise UserError(_("Bu faturanın E-Dönüşüm Belge / UUID değeri bulunamadı."))

        integrator = self.company_id.get_integrator()
        try:
            data = integrator.get_inbound_invoice_status(doc_id)
            status_text = (data.get('Status') or '').upper()
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
                provider_title = self.company_id.edonusum_provider.capitalize()
                self.message_post(body=_(
                    "🔄 <b>%s Durumu Güncellendi:</b> %s | Uygulama Yanıtı: %s"
                ) % (provider_title, status_text, answer_status or "Bekliyor"))

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

    def action_download_official_pdf(self):
        """Downloads official PDF visual and attaches to the record."""
        self.ensure_one()
        doc_id = self._get_target_doc_identifier()
        if not doc_id:
            raise UserError(_("Fatura Belge / UUID değeri bulunamadı."))

        integrator = self.company_id.get_integrator()
        pdf_bytes = integrator.get_inbound_invoice_pdf(doc_id)
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name or doc_id}.pdf",
            'type': 'binary',
            'datas': base64.b64encode(pdf_bytes),
            'res_model': 'account.move',
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        self.message_post(body=_("📄 Resmi e-Fatura görseli PDF olarak eklendi."), attachment_ids=[attachment.id])
        return True

    def action_download_official_xml(self):
        """Downloads signed UBL-TR XML and attaches to the record."""
        self.ensure_one()
        doc_id = self._get_target_doc_identifier()
        if not doc_id:
            raise UserError(_("Fatura Belge / UUID değeri bulunamadı."))

        integrator = self.company_id.get_integrator()
        xml_bytes = integrator.get_inbound_invoice_xml(doc_id)
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name or doc_id}.xml",
            'type': 'binary',
            'datas': base64.b64encode(xml_bytes),
            'res_model': 'account.move',
            'res_id': self.id,
            'mimetype': 'application/xml'
        })
        self.message_post(body=_("📦 İmzalı UBL-TR XML dosyası eklendi."), attachment_ids=[attachment.id])
        return True

    # Backwards compatibility methods
    def action_download_nilvera_pdf(self):
        return self.action_download_official_pdf()

    def action_download_nilvera_xml(self):
        return self.action_download_official_xml()

    # -------------------------------------------------------------------------
    # Cron Jobs
    # -------------------------------------------------------------------------

    @api.model
    def cron_sync_all_edonusum_invoices(self):
        """Scheduled action: Polls new inbound invoices for all active companies."""
        companies = self.env['res.company'].search([
            ('edonusum_auto_sync', '=', True)
        ])
        for comp in companies:
            try:
                wizard = self.env['fetch.invoices.wizard'].with_company(comp).create({
                    'company_id': comp.id,
                    'date_start': fields.Date.today() - timedelta(days=2),
                    'date_end': fields.Date.today()
                })
                wizard.action_fetch_invoices()
            except Exception as e:
                logger.error("Error syncing E-Donusum for company %s: %s", comp.name, e)

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
