from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open  # noqa: F401  (ileride örnek dosya okumak için)

UBL_WITH_CODES = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UUID>11111111-2222-3333-4444-555555555555</cbc:UUID>
  <cac:WithholdingTaxTotal>
    <cbc:TaxAmount currencyID="TRY">1000.00</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxAmount currencyID="TRY">1000.00</cbc:TaxAmount>
      <cac:TaxCategory>
        <cac:TaxScheme>
          <cbc:Name>KDV Tevkifatı</cbc:Name>
          <cbc:TaxTypeCode>627</cbc:TaxTypeCode>
        </cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:WithholdingTaxTotal>
  <cac:TaxTotal>
    <cac:TaxSubtotal>
      <cac:TaxCategory>
        <cbc:TaxExemptionReasonCode>301</cbc:TaxExemptionReasonCode>
        <cac:TaxScheme>
          <cbc:TaxTypeCode>0015</cbc:TaxTypeCode>
        </cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
</Invoice>
"""

UBL_PLAIN = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UUID>99999999-8888-7777-6666-555555555555</cbc:UUID>
  <cac:TaxTotal>
    <cac:TaxSubtotal>
      <cac:TaxCategory>
        <cac:TaxScheme><cbc:TaxTypeCode>0015</cbc:TaxTypeCode></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
</Invoice>
"""


@tagged("post_install", "-at_install")
class TestUblTaxCodes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.builder = cls.env["account.edi.xml.ubl.tr"]
        cls.tree = etree.fromstring(UBL_WITH_CODES.encode())
        cls.plain_tree = etree.fromstring(UBL_PLAIN.encode())

    def _skip_without_catalogue(self):
        """TR hesap planı yüklü değilse kod kataloğu boştur; o testler anlamsızdır."""
        model = self.builder._sd_tax_code_model()
        if model is None or not model.search_count([]):
            self.skipTest("GİB kod kataloğu bu veritabanında yüklü değil (TR hesap planı yok)")

    # 1) mutlu yol: kodlar belgeden okunuyor
    def test_withholding_code_is_read_from_document(self):
        self.assertEqual(self.builder._sd_extract_withholding_codes(self.tree), ["627"])

    def test_exemption_code_is_read_from_document(self):
        self.assertEqual(self.builder._sd_extract_exemption_codes(self.tree), ["301"])

    # 2) 9015 vergi türü kodudur, tevkifat sebep kodu değildir — karıştırılmamalı
    def test_tax_type_code_9015_is_not_a_reason_code(self):
        xml = UBL_WITH_CODES.replace("<cbc:TaxTypeCode>627</cbc:TaxTypeCode>",
                                     "<cbc:TaxTypeCode>9015</cbc:TaxTypeCode>")
        tree = etree.fromstring(xml.encode())
        self.assertEqual(self.builder._sd_extract_withholding_codes(tree), [])

    # 3) kodsuz belge sessizce geçmeli
    def test_plain_document_yields_nothing(self):
        self.assertEqual(self.builder._sd_extract_withholding_codes(self.plain_tree), [])
        self.assertEqual(self.builder._sd_extract_exemption_codes(self.plain_tree), [])

    # 4) GİB kodu çekirdeğin kataloğundaki kayda çevriliyor
    def test_code_lookup_maps_to_catalogue(self):
        self._skip_without_catalogue()
        record = self.builder._sd_find_tax_code("627", ["withholding"])
        self.assertTrue(record, "627 kodu kod kataloğunda bulunamadı")
        self.assertEqual(record.code, 627)

    def test_code_lookup_rejects_wrong_type(self):
        self._skip_without_catalogue()
        self.assertFalse(self.builder._sd_find_tax_code("627", ["exception"]))

    def test_code_lookup_handles_garbage(self):
        self._skip_without_catalogue()
        self.assertFalse(self.builder._sd_find_tax_code("ABC", ["withholding"]))
        self.assertFalse(self.builder._sd_find_tax_code(False, ["withholding"]))

    # 5) uyuşmazlık raporlanıyor, vergi seçimi değiştirilmiyor
    def test_mismatch_is_reported(self):
        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.env["res.partner"].create({"name": "Tedarikçi"}).id,
            "invoice_line_ids": [(0, 0, {"name": "Demir", "quantity": 1, "price_unit": 100.0})],
        })
        messages = self.builder._sd_check_withholding_codes(move, ["627"])
        self.assertTrue(any("627" in m for m in messages),
                        "belgedeki kod faturada yokken uyarı üretilmeli")
        self.assertFalse(move.invoice_line_ids.tax_ids.l10n_tr_tax_withholding_code_id,
                         "vergi seçimi değiştirilmemeli")

    def test_unknown_code_is_reported(self):
        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.env["res.partner"].create({"name": "Tedarikçi 2"}).id,
            "invoice_line_ids": [(0, 0, {"name": "Hizmet", "quantity": 1, "price_unit": 50.0})],
        })
        messages = self.builder._sd_check_withholding_codes(move, ["999"])
        self.assertTrue(any("999" in m for m in messages))
