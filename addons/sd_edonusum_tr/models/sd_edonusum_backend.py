from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import EDonusumError, get_provider


class SdEdonusumBackend(models.Model):
    _name = "sd.edonusum.backend"
    _description = "E-Dönüşüm Entegratör Bağlantısı"
    _order = "company_id, provider"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", string="Şirket", required=True, index=True,
        default=lambda self: self.env.company, ondelete="cascade",
    )
    provider = fields.Selection(
        [("nilvera", "Nilvera"), ("parasut", "Paraşüt"), ("uyumsoft", "Uyumsoft")],
        string="Entegratör", required=True, default="nilvera",
    )
    active = fields.Boolean(default=True)
    use_test_env = fields.Boolean(
        string="Test Ortamı",
        help="Nilvera'da bu ayar çekirdeğin şirket ayarından okunur; Paraşüt ve Uyumsoft için burası geçerlidir.",
    )
    timeout = fields.Integer(string="Zaman Aşımı (sn)", default=30, required=True)
    state = fields.Selection(
        [("draft", "Taslak"), ("ok", "Bağlandı"), ("error", "Hata")],
        default="draft", readonly=True, copy=False,
    )
    state_message = fields.Char(readonly=True, copy=False)
    last_sync = fields.Datetime(string="Son Senkronizasyon", readonly=True, copy=False)

    # -- Uygulama yanıtı politikası ---------------------------------------
    auto_accept_days = fields.Integer(
        string="Yasal Kabul Süresi (gün)", default=7, required=True,
        help="TTK m.21/2: ticari faturaya bu süre içinde itiraz edilmezse kabul edilmiş sayılır. "
             "Süre fatura tarihinden itibaren işler.",
    )
    auto_accept_enabled = fields.Boolean(
        string="Süre Dolunca Otomatik Kabul Gönder", default=False,
        help="İşaretliyse süre dolan ticari faturalar için entegratöre KABUL yanıtı gönderilir. "
             "Kapalıysa yalnızca Odoo'da 'yasal kabul' olarak işaretlenir, GİB'e yanıt gönderilmez.",
    )

    # -- Paraşüt ----------------------------------------------------------
    parasut_company_id = fields.Char(string="Paraşüt Firma ID", groups="base.group_system")
    parasut_client_id = fields.Char(string="Paraşüt Client ID", groups="base.group_system")
    parasut_client_secret = fields.Char(string="Paraşüt Client Secret", groups="base.group_system")
    parasut_username = fields.Char(string="Paraşüt Kullanıcı Adı", groups="base.group_system")
    parasut_password = fields.Char(string="Paraşüt Şifre", groups="base.group_system")
    parasut_access_token = fields.Char(groups="base.group_system", copy=False)
    parasut_refresh_token = fields.Char(groups="base.group_system", copy=False)
    parasut_token_expiry = fields.Float(groups="base.group_system", copy=False)

    # -- Uyumsoft ---------------------------------------------------------
    uyumsoft_username = fields.Char(string="Uyumsoft Kullanıcı Adı", groups="base.group_system")
    uyumsoft_password = fields.Char(string="Uyumsoft Şifre", groups="base.group_system")
    uyumsoft_endpoint = fields.Char(
        string="Uyumsoft Uç Noktası", groups="base.group_system",
        help="Boş bırakılırsa ortam ayarına göre varsayılan adres kullanılır.",
    )

    _company_provider_uniq = models.Constraint(
        "UNIQUE(company_id, provider)",
        "Her şirket için bir entegratör yalnızca bir kez tanımlanabilir.",
    )
    _timeout_positive = models.Constraint(
        "CHECK(timeout > 0 AND timeout <= 300)",
        "Zaman aşımı 1-300 saniye arasında olmalıdır.",
    )

    @api.depends("provider", "company_id")
    def _compute_name(self):
        labels = dict(self._fields["provider"].selection)
        for backend in self:
            backend.name = f"{labels.get(backend.provider, backend.provider)} · {backend.company_id.name or ''}".strip(" ·")

    @api.constrains("auto_accept_days")
    def _check_auto_accept_days(self):
        for backend in self:
            if not 1 <= backend.auto_accept_days <= 60:
                raise ValidationError(_("Yasal kabul süresi 1 ile 60 gün arasında olmalıdır."))

    # -- API --------------------------------------------------------------

    @api.model
    def _get_for_company(self, company):
        """Şirketin etkin entegratörünü döner; yoksa boş recordset."""
        return self.search([("company_id", "=", company.id), ("active", "=", True)], limit=1)

    def get_provider(self):
        """Bu backend için sağlayıcı adaptörünü döner."""
        self.ensure_one()
        return get_provider(self)

    def action_test_connection(self):
        self.ensure_one()
        try:
            message = self.get_provider().test_connection()
        except EDonusumError as exc:
            self.write({"state": "error", "state_message": str(exc)[:200]})
            raise UserError(_("Bağlantı hatası: %s", exc)) from exc
        self.write({"state": "ok", "state_message": message[:200]})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Bağlantı Başarılı"), "message": message, "type": "success", "sticky": False},
        }
