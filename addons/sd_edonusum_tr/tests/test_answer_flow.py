from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.sd_edonusum_tr.services.base import EDonusumError

SEND_ANSWER = "odoo.addons.sd_edonusum_tr.services.nilvera.NilveraProvider.send_answer"
GET_STATUS = "odoo.addons.sd_edonusum_tr.services.nilvera.NilveraProvider.get_status"


@tagged("post_install", "-at_install")
class TestAnswerFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.sudo().l10n_tr_nilvera_api_key = "test-key"
        cls.backend = cls.env["sd.edonusum.backend"].create({
            "company_id": cls.company.id,
            "provider": "nilvera",
            "auto_accept_days": 7,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Tedarikçi A.Ş.", "vat": "1234567890"})
        cls.user = cls.env["res.users"].create({
            "name": "E-Dönüşüm Kullanıcı", "login": "sd_edonusum_user",
            "group_ids": [(6, 0, [cls.env.ref("sd_edonusum_tr.group_sd_edonusum_user").id])],
        })

    def _make_inbound(self, profile="TICARIFATURA", invoice_date=None, uuid="uuid-1"):
        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "invoice_date": invoice_date or fields.Date.context_today(self.env.user),
            "invoice_line_ids": [(0, 0, {"name": "Hizmet", "quantity": 1, "price_unit": 100.0})],
        })
        move.write({"sd_gib_profile": profile, "l10n_tr_nilvera_uuid": uuid, "sd_answer_status": "pending"})
        return move

    # 1) mutlu yol: kabul
    def test_accept_sets_status_and_logs(self):
        move = self._make_inbound()
        with patch(SEND_ANSWER, return_value={"already_answered": False}) as mocked:
            move.action_sd_answer_accept()
        mocked.assert_called_once()
        self.assertEqual(move.sd_answer_status, "accepted")
        self.assertTrue(move.sd_answer_date)
        log = self.env["sd.edonusum.sync.log"].search([("move_id", "=", move.id)], limit=1)
        self.assertEqual((log.operation, log.state), ("send_answer", "success"))

    # 1b) red sihirbazı gerekçeyi taşır
    def test_reject_via_wizard(self):
        move = self._make_inbound(uuid="uuid-2")
        wizard = self.env["sd.edonusum.answer.wizard"].create({"move_id": move.id, "reason": "Hatalı tutar"})
        with patch(SEND_ANSWER, return_value={"already_answered": False}) as mocked:
            wizard.action_confirm_reject()
        self.assertEqual(mocked.call_args.args[1], "RED")
        self.assertEqual(move.sd_answer_status, "rejected")
        self.assertIn("Hatalı tutar", move.sd_answer_note)

    # 2) hata yolu: temel faturaya yanıt verilemez
    def test_basic_invoice_cannot_be_answered(self):
        move = self._make_inbound(profile="TEMELFATURA", uuid="uuid-3")
        self.assertFalse(move.sd_can_answer)
        with self.assertRaises(UserError):
            move.action_sd_answer_accept()

    def test_second_answer_refused(self):
        move = self._make_inbound(uuid="uuid-4")
        with patch(SEND_ANSWER, return_value={"already_answered": False}):
            move.action_sd_answer_accept()
        with self.assertRaises(UserError):
            move._sd_send_answer("RED", "tekrar")

    def test_provider_error_is_logged_and_raised(self):
        """Hata kullanıcıya yansır ve günlüğe bağımsız imleçle yazılır.

        Bağımsız imleçte yazılan kayıt bu testin imlecinden görünmez; bu yüzden
        kaydın kendisi değil, doğru argümanlarla yazıldığı doğrulanır.
        """
        move = self._make_inbound(uuid="uuid-5")
        log_model = self.env["sd.edonusum.sync.log"].__class__
        with patch(SEND_ANSWER, side_effect=EDonusumError("403 reddedildi", 403)), \
             patch.object(log_model, "_record") as record:
            with self.assertRaises(UserError):
                move.action_sd_answer_accept()
        self.assertEqual(move.sd_answer_status, "pending")
        record.assert_called_once()
        self.assertEqual(record.call_args.args[2], "error")
        self.assertTrue(record.call_args.kwargs["independent"])

    # 3) erişim: yetkisiz kullanıcı entegratör ayarını değiştiremez
    def test_backend_write_requires_manager(self):
        with self.assertRaises(AccessError):
            self.backend.with_user(self.user).write({"auto_accept_days": 30})

    def test_secret_fields_hidden_from_plain_user(self):
        backend = self.backend.with_user(self.user)
        self.assertNotIn("parasut_client_secret", backend.fields_get())

    # 4) TTK m.21/2 — süre ve otomatik kabul
    def test_deadline_follows_company_setting(self):
        self.backend.auto_accept_days = 8
        move = self._make_inbound(invoice_date="2026-03-01", uuid="uuid-6")
        move.invalidate_recordset(["sd_answer_deadline"])
        self.assertEqual(str(move.sd_answer_deadline), "2026-03-09")

    def test_cron_auto_accepts_expired_without_calling_provider(self):
        self.backend.auto_accept_enabled = False
        move = self._make_inbound(invoice_date="2020-01-01", uuid="uuid-7")
        with patch(SEND_ANSWER) as mocked:
            self.env["account.move"]._cron_sd_auto_accept_expired()
        mocked.assert_not_called()
        self.assertEqual(move.sd_answer_status, "auto_accepted")
        self.assertIn("TTK", move.sd_answer_note)

    def test_cron_auto_accept_sends_when_enabled(self):
        self.backend.auto_accept_enabled = True
        move = self._make_inbound(invoice_date="2020-01-01", uuid="uuid-8")
        with patch(SEND_ANSWER, return_value={"already_answered": False}) as mocked:
            self.env["account.move"]._cron_sd_auto_accept_expired()
        mocked.assert_called_once()
        self.assertEqual(move.sd_answer_status, "auto_accepted")

    def test_cron_status_sync_updates_from_provider(self):
        move = self._make_inbound(uuid="uuid-9")
        with patch(GET_STATUS, return_value={"status": "KABUL", "answer_status": "KABUL", "answer_note": "portal"}):
            self.env["account.move"]._cron_sd_sync_answer_status()
        self.assertEqual(move.sd_answer_status, "accepted")
        self.assertEqual(move.sd_answer_note, "portal")

    # 5) çekirdek akış bozulmadı: fatura normal şekilde onaylanabiliyor
    def test_core_posting_still_works(self):
        move = self._make_inbound(uuid="uuid-10")
        move.action_post()
        self.assertEqual(move.state, "posted")
