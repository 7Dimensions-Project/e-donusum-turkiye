# -*- coding: utf-8 -*-
"""
Unit tests for UBLTRParser.
"""

import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'addons', 'e_donusum_turkiye')))
from tools.ubl_tr_parser import UBLTRParser

SAMPLE_UBL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>TR1.2</cbc:CustomizationID>
    <cbc:ProfileID>TICARIFATURA</cbc:ProfileID>
    <cbc:ID>TEST202600000001</cbc:ID>
    <cbc:UUID>11111111-2222-3333-4444-555555555555</cbc:UUID>
    <cbc:IssueDate>2026-09-24</cbc:IssueDate>
    <cbc:InvoiceTypeCode>SATIS</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>TRY</cbc:DocumentCurrencyCode>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="VKN">1234567890</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>Örnek Tedarikçi A.Ş.</cbc:Name>
            </cac:PartyName>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="VKN">9876543210</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>Örnek Alıcı Ltd. Şti.</cbc:Name>
            </cac:PartyName>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:AllowanceCharge>
        <cbc:ChargeIndicator>true</cbc:ChargeIndicator>
        <cbc:Amount currencyID="TRY">0.25</cbc:Amount>
        <cbc:AllowanceChargeReason>Yuvarlama Farkı</cbc:AllowanceChargeReason>
    </cac:AllowanceCharge>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="TRY">1000.00</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount currencyID="TRY">1000.25</cbc:TaxExclusiveAmount>
        <cbc:TaxInclusiveAmount currencyID="TRY">1200.25</cbc:TaxInclusiveAmount>
        <cbc:PayableAmount currencyID="TRY">1200.25</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
    <cac:InvoiceLine>
        <cbc:ID>1</cbc:ID>
        <cbc:InvoicedQuantity unitCode="NIU">1</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="TRY">1000.00</cbc:LineExtensionAmount>
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="TRY">200.00</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount currencyID="TRY">1000.00</cbc:TaxableAmount>
                <cbc:TaxAmount currencyID="TRY">200.00</cbc:TaxAmount>
                <cbc:Percent>20</cbc:Percent>
                <cac:TaxCategory>
                    <cac:TaxScheme>
                        <cbc:Name>KDV</cbc:Name>
                        <cbc:TaxTypeCode>0015</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Name>Danışmanlık Hizmeti</cbc:Name>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount currencyID="TRY">1000.00</cbc:PriceAmount>
        </cac:Price>
    </cac:InvoiceLine>
</Invoice>
"""

class TestUBLParser(unittest.TestCase):
    def test_parse_sample_ubl(self):
        parser = UBLTRParser(SAMPLE_UBL_XML)
        res = parser.parse()

        self.assertEqual(res['uuid'], "11111111-2222-3333-4444-555555555555")
        self.assertEqual(res['invoice_number'], "TEST202600000001")
        self.assertEqual(res['profile_id'], "TICARIFATURA")
        self.assertEqual(res['supplier']['vat'], "1234567890")
        self.assertEqual(res['supplier']['name'], "Örnek Tedarikçi A.Ş.")
        self.assertEqual(len(res['line_items']), 1)
        self.assertEqual(res['line_items'][0]['price_unit'], 1000.00)
        self.assertEqual(len(res['allowances_and_charges']), 1)
        self.assertEqual(res['allowances_and_charges'][0]['amount'], 0.25)
        self.assertTrue(res['allowances_and_charges'][0]['is_charge'])

if __name__ == '__main__':
    unittest.main()
