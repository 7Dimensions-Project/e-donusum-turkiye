from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Nilvera API anahtarı çekirdekte (l10n_tr_nilvera) zaten var; burada tekrarlanmaz.
    sd_edonusum_backend_id = fields.Many2one(
        "sd.edonusum.backend", string="E-Dönüşüm Entegratörü",
        compute="_compute_sd_edonusum_backend_id", store=False,
        help="Şirket için etkin entegratör bağlantısı.",
    )

    def _compute_sd_edonusum_backend_id(self):
        backends = self.env["sd.edonusum.backend"].search([
            ("company_id", "in", self.ids), ("active", "=", True),
        ])
        by_company = {}
        for backend in backends:
            by_company.setdefault(backend.company_id.id, backend)
        for company in self:
            company.sd_edonusum_backend_id = by_company.get(company.id, False)
