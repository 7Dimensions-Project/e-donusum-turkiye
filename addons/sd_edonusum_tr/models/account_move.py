"""Gelen e-faturalar için GİB uygulama yanıtı ve TTK m.21/2 takibi.

Odoo çekirdeği (``l10n_tr_nilvera_einvoice``) belgeleri indirir ve gönderim
durumunu (``l10n_tr_nilvera_send_status``) izler, ancak **uygulama yanıtı**
(KABUL / RED) göndermez. Ticari faturalarda bu yanıt yasal bir yükümlülüktür:
TTK m.21/2 uyarınca faturaya sekiz gün içinde itiraz edilmezse fatura içeriği
kabul edilmiş sayılır. Uygulamada GİB e-Fatura tarafında bu süre sekiz günlük
yasal itiraz süresi olarak işletilir ve süre şirket bazında ayarlanabilir.

Bu modül çekirdeğin alanlarını yeniden tanımlamaz; yalnızca yanıt durumunu ve
süre takibini ekler.
"""

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import ANSWER_ACCEPT, ANSWER_REJECT, EDonusumError, EDonusumRetryableError

_logger = logging.getLogger(__name__)

#: Uygulama yanıtı yalnızca ticari senaryoda verilir; temel faturada verilemez.
COMMERCIAL_PROFILES = ("TICARIFATURA", "TICARI", "COMMERCIAL")


class AccountMove(models.Model):
    _inherit = "account.move"

    sd_gib_profile = fields.Char(
        string="GİB Senaryosu (gelen)", readonly=True, copy=False, index="btree_not_null",
        help="Entegratörden gelen belgenin ProfileID değeri (TICARIFATURA / TEMELFATURA ...).",
    )
    sd_answer_status = fields.Selection(
        [
            ("not_applicable", "Uygulanamaz"),
            ("pending", "Yanıt Bekliyor"),
            ("accepted", "Kabul Edildi"),
            ("rejected", "Reddedildi"),
            ("auto_accepted", "Yasal Kabul (süre doldu)"),
            ("cancelled", "İptal"),
        ],
        string="Uygulama Yanıtı", default="not_applicable", copy=False, index=True, readonly=True, tracking=True,
    )
    sd_answer_note = fields.Text(string="Yanıt Notu", readonly=True, copy=False)
    sd_answer_date = fields.Datetime(string="Yanıt Tarihi", readonly=True, copy=False)
    sd_answer_deadline = fields.Date(
        string="İtiraz Son Tarihi", compute="_compute_sd_answer_deadline", store=True, copy=False,
        help="Fatura tarihine şirket ayarındaki yasal süre eklenerek hesaplanır.",
    )
    sd_answer_days_left = fields.Integer(
        string="Kalan Gün", compute="_compute_sd_answer_days_left",
    )
    sd_can_answer = fields.Boolean(compute="_compute_sd_can_answer")

    # -- Hesaplamalar -----------------------------------------------------

    @api.depends("invoice_date", "sd_answer_status", "company_id")
    def _compute_sd_answer_deadline(self):
        days_by_company = self._sd_auto_accept_days_by_company()
        for move in self:
            if move.sd_answer_status in ("not_applicable", False) or not move.invoice_date:
                move.sd_answer_deadline = False
            else:
                move.sd_answer_deadline = move.invoice_date + relativedelta(
                    days=days_by_company.get(move.company_id.id, 7)
                )

    @api.depends("sd_answer_deadline")
    def _compute_sd_answer_days_left(self):
        today = fields.Date.context_today(self)
        for move in self:
            move.sd_answer_days_left = (move.sd_answer_deadline - today).days if move.sd_answer_deadline else 0

    @api.depends("move_type", "sd_answer_status", "sd_gib_profile", "l10n_tr_nilvera_uuid")
    def _compute_sd_can_answer(self):
        for move in self:
            move.sd_can_answer = bool(
                move.move_type in ("in_invoice", "in_refund")
                and move.l10n_tr_nilvera_uuid
                and move.sd_answer_status == "pending"
                and move._sd_is_commercial()
            )

    def _sd_is_commercial(self):
        self.ensure_one()
        profile = (self.sd_gib_profile or "").upper()
        return any(token in profile for token in COMMERCIAL_PROFILES)

    @api.model
    def _sd_auto_accept_days_by_company(self):
        backends = self.env["sd.edonusum.backend"].sudo().search([("active", "=", True)])
        # sudo: süre ayarı yalnız yöneticide yazılır, okuması her kullanıcı için gerekli
        return {b.company_id.id: b.auto_accept_days for b in backends}

    def _sd_backend(self):
        """Faturanın şirketi için etkin entegratör; yoksa UserError."""
        self.ensure_one()
        backend = self.env["sd.edonusum.backend"]._get_for_company(self.company_id)
        if not backend:
            raise UserError(_(
                "'%(company)s' şirketi için etkin bir E-Dönüşüm entegratörü tanımlı değil.",
                company=self.company_id.name,
            ))
        return backend

    # -- Kullanıcı aksiyonları -------------------------------------------

    def action_sd_answer_accept(self):
        self.ensure_one()
        return self._sd_send_answer(ANSWER_ACCEPT)

    def action_sd_answer_reject(self):
        """Red sebebi zorunlu olduğu için sihirbaz açar."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Faturayı Reddet (GİB)"),
            "res_model": "sd.edonusum.answer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _sd_send_answer(self, answer, reason=""):
        """Entegratöre uygulama yanıtı gönderir ve sonucu faturaya işler."""
        self.ensure_one()
        if not self.l10n_tr_nilvera_uuid:
            raise UserError(_("Faturanın GİB belge numarası (UUID) yok; yanıt gönderilemez."))
        if not self._sd_is_commercial():
            raise UserError(_(
                "Bu belge ticari fatura senaryosunda değil (%(profile)s). "
                "Temel faturalara GİB uygulama yanıtı verilemez; itiraz harici yollarla yapılır.",
                profile=self.sd_gib_profile or _("bilinmiyor"),
            ))
        if self.sd_answer_status in ("accepted", "rejected", "auto_accepted"):
            raise UserError(_("Bu fatura için yanıt zaten verilmiş (%s).", self.sd_answer_status))

        backend = self._sd_backend()
        Log = self.env["sd.edonusum.sync.log"]
        try:
            result = backend.get_provider().send_answer(self.l10n_tr_nilvera_uuid, answer, reason)
        except EDonusumError as exc:
            # independent: UserError isteği geri alır, günlük kaydı da silinirdi
            Log._record(backend, "send_answer", "error", str(exc), move=self,
                        document_uuid=self.l10n_tr_nilvera_uuid, payload=exc.payload or "",
                        independent=True)
            raise UserError(_("Uygulama yanıtı gönderilemedi: %s", exc)) from exc

        status = "accepted" if answer == ANSWER_ACCEPT else "rejected"
        note = reason or (_("GİB üzerinden kabul edildi.") if answer == ANSWER_ACCEPT
                          else _("GİB üzerinden reddedildi."))
        self.write({
            "sd_answer_status": status,
            "sd_answer_note": note,
            "sd_answer_date": fields.Datetime.now(),
        })
        Log._record(backend, "send_answer", "success",
                    _("Zaten yanıtlanmıştı.") if result.get("already_answered") else answer,
                    move=self, document_uuid=self.l10n_tr_nilvera_uuid)
        self.message_post(body=_(
            "GİB uygulama yanıtı gönderildi: %(answer)s%(reason)s",
            answer=answer,
            reason=_(" — Gerekçe: %s", reason) if reason else "",
        ))
        return True

    # -- Entegratörden gelen belgeleri işaretleme -------------------------

    @api.model
    def _sd_mark_inbound_documents(self, backend, documents):
        """Entegratörden gelen belge listesini mevcut faturalarla eşleştirir.

        Çekirdek belgeleri kendi cron'uyla indirir; burada yalnızca yanıt
        durumu ve senaryo bilgisi zenginleştirilir. Tek sorguda eşleşme yapılır.
        """
        by_uuid = {doc.uuid: doc for doc in documents if doc.uuid}
        if not by_uuid:
            return self.browse()
        moves = self.search([
            ("company_id", "=", backend.company_id.id),
            ("l10n_tr_nilvera_uuid", "in", list(by_uuid)),
        ])
        for move in moves:
            doc = by_uuid.get(move.l10n_tr_nilvera_uuid)
            values = {}
            if doc.profile and move.sd_gib_profile != doc.profile:
                values["sd_gib_profile"] = doc.profile
            if move.sd_answer_status == "not_applicable":
                is_commercial = any(token in (doc.profile or "").upper() for token in COMMERCIAL_PROFILES)
                if is_commercial and move.move_type in ("in_invoice", "in_refund"):
                    values["sd_answer_status"] = "pending"
            if values:
                move.write(values)
        return moves

    # -- Zamanlanmış görevler ---------------------------------------------

    @api.model
    def _cron_sd_sync_answer_status(self, limit=200):
        """Yanıt bekleyen faturaların durumunu entegratörden günceller."""
        Log = self.env["sd.edonusum.sync.log"]
        backends = self.env["sd.edonusum.backend"].sudo().search([("active", "=", True)])
        for backend in backends:
            moves = self.search([
                ("company_id", "=", backend.company_id.id),
                ("sd_answer_status", "=", "pending"),
                ("l10n_tr_nilvera_uuid", "!=", False),
            ], limit=limit)
            if not moves:
                continue
            provider = backend.get_provider()
            for move in moves:
                try:
                    with self.env.cr.savepoint():
                        data = provider.get_status(move.l10n_tr_nilvera_uuid)
                        state = provider.classify_answer(data.get("status", ""), data.get("answer_status", ""))
                        if state:
                            move.write({
                                "sd_answer_status": state,
                                "sd_answer_note": data.get("answer_note") or move.sd_answer_note,
                                "sd_answer_date": fields.Datetime.now(),
                            })
                            move.message_post(body=_(
                                "Entegratör durumu güncellendi: %(status)s", status=state,
                            ))
                except EDonusumRetryableError as exc:
                    Log._record(backend, "get_status", "retry", str(exc), move=move,
                                document_uuid=move.l10n_tr_nilvera_uuid)
                    break  # geçici hata: bu şirket için turu bitir, sonraki cron'da devam
                except EDonusumError as exc:
                    Log._record(backend, "get_status", "error", str(exc), move=move,
                                document_uuid=move.l10n_tr_nilvera_uuid)
            backend.sudo().last_sync = fields.Datetime.now()

    @api.model
    def _cron_sd_auto_accept_expired(self, limit=500):
        """TTK m.21/2: itiraz süresi dolan ticari faturaları yasal kabul sayar."""
        Log = self.env["sd.edonusum.sync.log"]
        today = fields.Date.context_today(self)
        backends = self.env["sd.edonusum.backend"].sudo().search([("active", "=", True)])
        for backend in backends:
            moves = self.search([
                ("company_id", "=", backend.company_id.id),
                ("sd_answer_status", "=", "pending"),
                ("sd_answer_deadline", "<", today),
                ("move_type", "in", ("in_invoice", "in_refund")),
            ], limit=limit)
            if not moves:
                continue
            provider = backend.get_provider() if backend.auto_accept_enabled else None
            for move in moves:
                try:
                    with self.env.cr.savepoint():
                        if provider is not None:
                            provider.send_answer(move.l10n_tr_nilvera_uuid, ANSWER_ACCEPT,
                                                 _("TTK m.21/2 – yasal süre içinde itiraz edilmedi."))
                        move.write({
                            "sd_answer_status": "auto_accepted",
                            "sd_answer_note": _(
                                "TTK m.21/2 uyarınca yasal itiraz süresi (%(days)s gün) içinde itiraz "
                                "edilmediğinden kabul edilmiş sayıldı.", days=backend.auto_accept_days,
                            ),
                            "sd_answer_date": fields.Datetime.now(),
                        })
                        move.message_post(body=_("Yasal kabul: itiraz süresi doldu."))
                        Log._record(backend, "auto_accept", "success", move=move,
                                    document_uuid=move.l10n_tr_nilvera_uuid)
                except EDonusumRetryableError as exc:
                    Log._record(backend, "auto_accept", "retry", str(exc), move=move,
                                document_uuid=move.l10n_tr_nilvera_uuid)
                    break
                except EDonusumError as exc:
                    Log._record(backend, "auto_accept", "error", str(exc), move=move,
                                document_uuid=move.l10n_tr_nilvera_uuid)
