from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services import ANSWER_REJECT


class SdEdonusumAnswerWizard(models.TransientModel):
    _name = "sd.edonusum.answer.wizard"
    _description = "GİB Uygulama Yanıtı (Red) Sihirbazı"

    move_id = fields.Many2one("account.move", string="Fatura", required=True, ondelete="cascade")
    reason = fields.Text(
        string="Red Gerekçesi", required=True,
        help="GİB'e iletilen uygulama yanıtında yer alır ve faturaya not olarak kaydedilir.",
    )

    def action_confirm_reject(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(_("Red gerekçesi zorunludur."))
        self.move_id._sd_send_answer(ANSWER_REJECT, self.reason.strip())
        return {"type": "ir.actions.act_window_close"}
