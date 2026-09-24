import logging

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)


class SdEdonusumSyncLog(models.Model):
    _name = "sd.edonusum.sync.log"
    _description = "E-Dönüşüm İşlem Günlüğü"
    _order = "create_date desc, id desc"
    _rec_name = "operation"

    backend_id = fields.Many2one("sd.edonusum.backend", string="Entegratör", ondelete="cascade", index=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True, index=True)
    provider = fields.Selection(related="backend_id.provider", string="Sağlayıcı", store=True)
    move_id = fields.Many2one("account.move", string="Fatura", ondelete="cascade", index=True)
    document_uuid = fields.Char(string="Belge UUID", index=True)
    operation = fields.Selection(
        [
            ("send_answer", "Uygulama Yanıtı"),
            ("get_status", "Durum Sorgulama"),
            ("list_inbound", "Gelen Belge Listesi"),
            ("auto_accept", "Yasal Otomatik Kabul"),
            ("test", "Bağlantı Testi"),
        ],
        required=True,
    )
    state = fields.Selection(
        [("success", "Başarılı"), ("error", "Hata"), ("retry", "Yeniden Denenecek")],
        required=True, index=True,
    )
    message = fields.Char()
    payload = fields.Text(help="Tanı amaçlı ham yanıt özeti. Kimlik bilgisi içermez.")

    @api.model
    def _record(self, backend, operation, state, message="", move=None, document_uuid="", payload="",
                independent=False):
        """Günlük kaydı oluşturur. Çağıran akışı asla kesmez.

        ``independent=True`` verildiğinde kayıt **ayrı bir cursor'da** yazılır ve hemen
        kalıcı olur. Bu, kullanıcıya ``UserError`` gösterilecek hata yollarında şarttır:
        Odoo, kullanıcı hatasında isteğin tamamını geri alır ve aynı imleçte yazılan
        günlük kaydı da silinirdi — yani hatalar hiç görünmezdi.
        """
        values = {
            "backend_id": backend.id if backend else False,
            "move_id": move.id if move else False,
            "document_uuid": document_uuid or "",
            "operation": operation,
            "state": state,
            "message": (message or "")[:255],
            "payload": (payload or "")[:4000],
        }
        try:
            if independent:
                with self.env.registry.cursor() as cr:
                    api.Environment(cr, SUPERUSER_ID, {})["sd.edonusum.sync.log"].create(values)
                return self.browse()
            # sudo: günlük her yetkili kullanıcının işlemi için yazılabilmeli
            return self.sudo().create(values)
        except Exception:  # noqa: BLE001 - günlükleme hatası iş akışını durdurmamalı
            _logger.exception("E-Dönüşüm günlüğü yazılamadı: %s/%s", operation, state)
            return self.browse()
