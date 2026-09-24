# -*- coding: utf-8 -*-
"""
UBL-TR 2.1 XML Generator for Odoo E-Dönüşüm Türkiye.
Builds compliant GİB UBL 2.1 e-Fatura and e-Arşiv XML documents from Odoo account.move.
"""

import uuid
import logging
from xml.etree import ElementTree as ET
from datetime import datetime

logger = logging.getLogger("ubl_tr_generator")

NS_MAP = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": "http://uri.etsi.org/01903/v1.3.2#"
}

class UBLTRGenerator:
    """Generates standard GİB UBL-TR 2.1 XML files."""

    def __init__(self, invoice):
        self.inv = invoice
        self.company = invoice.company_id
        self.partner = invoice.partner_id

    def generate_xml(self) -> bytes:
        """Generates full UBL-TR 2.1 XML bytes."""
        for prefix, uri in NS_MAP.items():
            ET.register_namespace("" if prefix is None else prefix, uri)

        root = ET.Element("Invoice")
        root.set("xmlns", NS_MAP[None])
        for p, u in NS_MAP.items():
            if p:
                root.set(f"xmlns:{p}", u)

        # UBLExtensions (placeholder for GİB digital signature)
        ubl_exts = ET.SubElement(root, "ext:UBLExtensions")
        ext = ET.SubElement(ubl_exts, "ext:UBLExtension")
        ET.SubElement(ext, "ext:ExtensionContent")

        # Header components
        ET.SubElement(root, "cbc:UBLVersionID").text = "2.1"
        ET.SubElement(root, "cbc:CustomizationID").text = "TR1.2"
        profile_id = getattr(self.inv, 'x_edonusum_profile', False) or getattr(self.inv, 'x_parasut_profile', 'TICARIFATURA')
        ET.SubElement(root, "cbc:ProfileID").text = profile_id.upper()
        ET.SubElement(root, "cbc:ID").text = self.inv.name or "GIB" + datetime.now().strftime("%Y%m%d%H%M%S")
        ET.SubElement(root, "cbc:CopyIndicator").text = "false"
        
        doc_uuid = getattr(self.inv, 'x_edonusum_uuid', False) or getattr(self.inv, 'x_parasut_uuid', False) or str(uuid.uuid4())
        ET.SubElement(root, "cbc:UUID").text = doc_uuid

        issue_date = str(self.inv.invoice_date or datetime.now().date())
        ET.SubElement(root, "cbc:IssueDate").text = issue_date
        ET.SubElement(root, "cbc:IssueTime").text = datetime.now().strftime("%H:%M:%S")

        inv_type = getattr(self.inv, 'x_edonusum_type_code', 'SATIS') or 'SATIS'
        ET.SubElement(root, "cbc:InvoiceTypeCode").text = inv_type

        # Notes
        ET.SubElement(root, "cbc:Note").text = f"Fatura Ref: {self.inv.name or ''}"
        if self.inv.narration:
            ET.SubElement(root, "cbc:Note").text = self.inv.narration

        currency = self.inv.currency_id.name or "TRY"
        ET.SubElement(root, "cbc:DocumentCurrencyCode").text = currency

        # AccountingSupplierParty
        self._build_supplier(root)

        # AccountingCustomerParty
        self._build_customer(root)

        # TaxTotal
        self._build_tax_totals(root, currency)

        # LegalMonetaryTotal
        self._build_legal_monetary_total(root, currency)

        # InvoiceLines
        self._build_invoice_lines(root, currency)

        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def _build_party(self, parent_elem, partner, is_supplier: bool):
        party_party = ET.SubElement(parent_elem, "cac:Party")
        vkn = "".join(filter(str.isdigit, str(partner.vat or ''))) or "11111111111"
        scheme = "TCKN" if len(vkn) == 11 else "VKN"

        party_id = ET.SubElement(party_party, "cac:PartyIdentification")
        id_elem = ET.SubElement(party_id, "cbc:ID")
        id_elem.set("schemeID", scheme)
        id_elem.text = vkn

        party_name = ET.SubElement(party_party, "cac:PartyName")
        ET.SubElement(party_name, "cbc:Name").text = partner.name or ""

        addr = ET.SubElement(party_party, "cac:PostalAddress")
        ET.SubElement(addr, "cbc:StreetName").text = partner.street or partner.street2 or "Merkez"
        ET.SubElement(addr, "cbc:CitySubdivisionName").text = partner.city or ""
        ET.SubElement(addr, "cbc:CityName").text = partner.state_id.name if partner.state_id else (partner.city or "İstanbul")
        ET.SubElement(addr, "cbc:PostalZone").text = partner.zip or "34000"
        country = ET.SubElement(addr, "cac:Country")
        ET.SubElement(country, "cbc:Name").text = partner.country_id.name if partner.country_id else "Türkiye"

        tax_scheme = ET.SubElement(party_party, "cac:PartyTaxScheme")
        scheme_node = ET.SubElement(tax_scheme, "cac:TaxScheme")
        ET.SubElement(scheme_node, "cbc:Name").text = getattr(partner, 'x_tax_office', False) or "Vergi Dairesi"

    def _build_supplier(self, root):
        supp_party = ET.SubElement(root, "cac:AccountingSupplierParty")
        self._build_party(supp_party, self.company.partner_id, is_supplier=True)

    def _build_customer(self, root):
        cust_party = ET.SubElement(root, "cac:AccountingCustomerParty")
        self._build_party(cust_party, self.partner, is_supplier=False)

    def _build_tax_totals(self, root, currency: str):
        tax_total = ET.SubElement(root, "cac:TaxTotal")
        amt = ET.SubElement(tax_total, "cbc:TaxAmount")
        amt.set("currencyID", currency)
        amt.text = f"{self.inv.amount_tax:.2f}"

        # Subtotals per tax group
        for group in self.inv.tax_totals.get('subtotals', [{}])[0].get('tax_groups', []):
            st = ET.SubElement(tax_total, "cac:TaxSubtotal")
            t_amt = ET.SubElement(st, "cbc:TaxAmount")
            t_amt.set("currencyID", currency)
            t_amt.text = f"{group.get('tax_amount', 0.0):.2f}"

            t_base = ET.SubElement(st, "cbc:TaxableAmount")
            t_base.set("currencyID", currency)
            t_base.text = f"{group.get('base_amount', 0.0):.2f}"

            t_cat = ET.SubElement(st, "cac:TaxCategory")
            t_scheme = ET.SubElement(t_cat, "cac:TaxScheme")
            ET.SubElement(t_scheme, "cbc:Name").text = "KDV"
            ET.SubElement(t_scheme, "cbc:TaxTypeCode").text = "0015"

    def _build_legal_monetary_total(self, root, currency: str):
        lmt = ET.SubElement(root, "cac:LegalMonetaryTotal")

        lea = ET.SubElement(lmt, "cbc:LineExtensionAmount")
        lea.set("currencyID", currency)
        lea.text = f"{self.inv.amount_untaxed:.2f}"

        tea = ET.SubElement(lmt, "cbc:TaxExclusiveAmount")
        tea.set("currencyID", currency)
        tea.text = f"{self.inv.amount_untaxed:.2f}"

        tia = ET.SubElement(lmt, "cbc:TaxInclusiveAmount")
        tia.set("currencyID", currency)
        tia.text = f"{self.inv.amount_total:.2f}"

        pa = ET.SubElement(lmt, "cbc:PayableAmount")
        pa.set("currencyID", currency)
        pa.text = f"{self.inv.amount_total:.2f}"

    def _build_invoice_lines(self, root, currency: str):
        for idx, line in enumerate(self.inv.invoice_line_ids.filtered(lambda l: not l.display_type), 1):
            line_elem = ET.SubElement(root, "cac:InvoiceLine")
            ET.SubElement(line_elem, "cbc:ID").text = str(idx)

            qty_elem = ET.SubElement(line_elem, "cbc:InvoicedQuantity")
            qty_elem.set("unitCode", "NIU")
            qty_elem.text = f"{line.quantity:.2f}"

            ext_amt = ET.SubElement(line_elem, "cbc:LineExtensionAmount")
            ext_amt.set("currencyID", currency)
            ext_amt.text = f"{line.price_subtotal:.2f}"

            # TaxTotal
            tt = ET.SubElement(line_elem, "cac:TaxTotal")
            t_amt = ET.SubElement(tt, "cbc:TaxAmount")
            t_amt.set("currencyID", currency)
            tax_diff = line.price_total - line.price_subtotal
            t_amt.text = f"{tax_diff:.2f}"

            # Item
            item = ET.SubElement(line_elem, "cac:Item")
            ET.SubElement(item, "cbc:Name").text = line.name or "Hizmet/Ürün"

            # Price
            price = ET.SubElement(line_elem, "cac:Price")
            p_amt = ET.SubElement(price, "cbc:PriceAmount")
            p_amt.set("currencyID", currency)
            p_amt.text = f"{line.price_unit:.2f}"
