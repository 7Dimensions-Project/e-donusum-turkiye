"""Gelen UBL-TR faturasındaki GİB vergi kodlarını okur.

Odoo çekirdeği (`l10n_tr_nilvera_einvoice`) bir e-faturayı içeri alırken UBL'den
yalnızca UUID'yi okur; **tevkifat sebep kodu** ve **KDV istisna kodu** ayrıştırılmaz.
Oysa bu kodlar belgenin kendisinde yazılıdır:

* tevkifat: ``cac:WithholdingTaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode``
  (satır düzeyinde de gelebilir) — GİB kodu 601, 602, … 627
* istisna: ``cac:TaxCategory/cbc:TaxExemptionReasonCode`` — 301, 308, 350, …

Kodu belgeden okumak yerine satır açıklamasından ya da vergi adından tahmin etmek
yanlış tevkifat türü bildirilmesine yol açar. Bu sınıf kodları okur, faturaya işler
ve seçilen Odoo vergisiyle uyuşmuyorsa sohbete uyarı bırakır — sessizce düzeltmez,
çünkü doğru vergi seçimi mali bir karardır.
"""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)

#: GİB'de KDV tevkifatının vergi türü kodu
WITHHOLDING_TAX_TYPE_CODE = "9015"


class AccountEdiXmlUblTr(models.AbstractModel):
    _inherit = "account.edi.xml.ubl.tr"

    # -- Ayrıştırma -------------------------------------------------------

    def _sd_extract_withholding_codes(self, tree):
        """Belgedeki tevkifat sebep kodlarını döner (sırayı korur, tekrarsız)."""
        codes = []
        for node in tree.iterfind(".//{*}WithholdingTaxTotal"):
            for subtotal in node.iterfind(".//{*}TaxSubtotal"):
                category = subtotal.find(".//{*}TaxCategory")
                if category is None:
                    continue
                # Tevkifat sebep kodu TaxTypeCode alanında taşınır; 9015 vergi
                # türünün kendisidir, sebep kodu değildir.
                for code_node in category.iterfind(".//{*}TaxTypeCode"):
                    value = (code_node.text or "").strip()
                    if value and value != WITHHOLDING_TAX_TYPE_CODE and value not in codes:
                        codes.append(value)
        return codes

    def _sd_extract_exemption_codes(self, tree):
        """Belgedeki KDV istisna sebep kodlarını döner (tekrarsız)."""
        codes = []
        for node in tree.iterfind(".//{*}TaxExemptionReasonCode"):
            value = (node.text or "").strip()
            if value and value not in codes:
                codes.append(value)
        return codes

    # -- Odoo kayıtlarıyla eşleme ----------------------------------------

    def _sd_tax_code_model(self):
        """GİB kod kataloğu modeli.

        Odoo 19.0'da bu katalog ``l10n_tr_nilvera_einvoice_extended`` modülünden,
        saas~19.3'te ise doğrudan ``l10n_tr_nilvera_einvoice``'dan gelir ve model
        adı buna göre değişir. Hangisi kuruluysa o kullanılır.
        """
        for name in ("l10n_tr_nilvera_einvoice.account.tax.code",
                     "l10n_tr_nilvera_einvoice_extended.account.tax.code"):
            if name in self.env:
                return self.env[name]
        return None

    def _sd_find_tax_code(self, code, code_types):
        """GİB kodunu kod kataloğundaki kayda çevirir; bulunamazsa boş recordset."""
        model = self._sd_tax_code_model()
        if model is None:
            return None
        if not code:
            return model.browse()
        try:
            numeric = int(str(code).strip())
        except (TypeError, ValueError):
            return model.browse()
        return model.search([("code", "=", numeric), ("code_type", "in", code_types)], limit=1)

    def _sd_apply_exemption_code(self, invoice, codes):
        """İlk istisna kodunu faturaya işler; zaten doluysa dokunmaz."""
        if not codes or invoice.l10n_tr_exemption_code_id:
            return None
        record = self._sd_find_tax_code(codes[0], ["exception", "export_exception", "export_registration"])
        if record:
            invoice.l10n_tr_exemption_code_id = record.id
            return record
        return None

    def _sd_check_withholding_codes(self, invoice, codes):
        """Belgedeki tevkifat kodlarıyla satırlardaki vergilerin kodlarını karşılaştırır.

        Uyuşmazlığı ve eksikliği rapor eder; vergi seçimini değiştirmez.
        """
        if not codes:
            return []

        model = self._sd_tax_code_model()
        if model is None:
            return [_("GİB kod kataloğu kurulu değil; belgedeki tevkifat kodu doğrulanamadı: %(codes)s",
                      codes=", ".join(codes))]
        document_records = model.browse()
        unknown = []
        for code in codes:
            record = self._sd_find_tax_code(code, ["withholding"])
            if record:
                document_records |= record
            else:
                unknown.append(code)

        selected = invoice.invoice_line_ids.tax_ids.l10n_tr_tax_withholding_code_id
        messages = []
        if unknown:
            messages.append(_(
                "Belgedeki tevkifat kodu tanınmadı: %(codes)s", codes=", ".join(unknown),
            ))
        missing = document_records - selected
        if missing:
            messages.append(_(
                "Belgede bildirilen tevkifat kodu faturadaki vergilerde yok: %(codes)s",
                codes=", ".join(f"{r.code} – {r.name}" for r in missing),
            ))
        extra = selected - document_records
        if extra:
            messages.append(_(
                "Faturadaki vergilerde belgede geçmeyen tevkifat kodu var: %(codes)s",
                codes=", ".join(f"{r.code} – {r.name}" for r in extra),
            ))
        return messages

    # -- Çekirdek akışa bağlanma ------------------------------------------

    def _import_fill_invoice(self, invoice, tree, qty_factor):
        # EXTENDS l10n_tr_nilvera_einvoice
        logs = super()._import_fill_invoice(invoice, tree, qty_factor)

        exemption_codes = self._sd_extract_exemption_codes(tree)
        withholding_codes = self._sd_extract_withholding_codes(tree)
        if not exemption_codes and not withholding_codes:
            return logs

        notes = []
        applied = self._sd_apply_exemption_code(invoice, exemption_codes)
        if applied:
            notes.append(_(
                "KDV istisna kodu belgeden okundu: %(code)s – %(name)s",
                code=applied.code, name=applied.name,
            ))
        elif exemption_codes and not invoice.l10n_tr_exemption_code_id:
            notes.append(_(
                "Belgedeki KDV istisna kodu tanınmadı: %(codes)s", codes=", ".join(exemption_codes),
            ))

        if withholding_codes:
            notes.append(_("Belgede bildirilen tevkifat kodu: %(codes)s", codes=", ".join(withholding_codes)))
            notes.extend(self._sd_check_withholding_codes(invoice, withholding_codes))

        if notes:
            invoice.message_post(body="<br/>".join(notes))
            _logger.info("UBL-TR vergi kodları okundu (%s): %s", invoice.name or invoice.id, notes)

        return logs
