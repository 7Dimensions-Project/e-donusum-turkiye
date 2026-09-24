# -*- coding: utf-8 -*-
"""
UBL-TR 2.1 Parser for Odoo E-Dönüşüm Türkiye.
Extracts comprehensive invoice metadata, header information, partner details,
line items, complex multi-taxes (KDV, Tevkifat, Konaklama, ÖTV, ÖİV), allowances,
charges (yuvarlama farkı), exchange rates, order/dispatch references, and bank IBANs.
"""

import base64
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("ubl_tr_parser")

NS = {
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#'
}

class UBLTRParser:
    """Parser for Turkish E-Invoice / E-Archive / E-CreditNote UBL 2.1 XML documents."""

    def __init__(self, xml_content: Union[str, bytes]):
        if isinstance(xml_content, str):
            xml_bytes = xml_content.encode('utf-8')
        else:
            xml_bytes = xml_content

        try:
            self.root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            logger.error("XML parse error in UBLTRParser: %s", e)
            raise ValueError(f"Geçersiz XML formatı: {e}")

    def _findtext(self, node: ET.Element, xpath: str, default: str = "") -> str:
        if node is None:
            return default
        found = node.findtext(xpath, namespaces=NS)
        return found.strip() if found else default

    def _findfloat(self, node: ET.Element, xpath: str, default: float = 0.0) -> float:
        text = self._findtext(node, xpath, "")
        if not text:
            return default
        try:
            return float(text.replace(',', '.'))
        except ValueError:
            return default

    def parse(self) -> Dict[str, Any]:
        """Parses the entire UBL 2.1 document and returns a structured dictionary."""
        tag = self.root.tag.split('}')[-1]
        is_credit_note = (tag == 'CreditNote')

        res = {
            'doc_type': 'credit_note' if is_credit_note else 'invoice',
            'uuid': self._findtext(self.root, 'cbc:UUID'),
            'invoice_number': self._findtext(self.root, 'cbc:ID'),
            'issue_date': self._findtext(self.root, 'cbc:IssueDate'),
            'issue_time': self._findtext(self.root, 'cbc:IssueTime'),
            'profile_id': self._findtext(self.root, 'cbc:ProfileID', 'TEMELFATURA').upper(),
            'invoice_type_code': self._findtext(self.root, 'cbc:InvoiceTypeCode', 'SATIS').upper(),
            'currency_code': self._findtext(self.root, 'cbc:DocumentCurrencyCode', 'TRY').upper(),
            'notes': [],
            'supplier': self._parse_supplier(),
            'customer': self._parse_customer(),
            'order_reference': self._parse_order_reference(),
            'despatch_references': self._parse_despatch_references(),
            'pricing_exchange_rate': self._parse_exchange_rate(),
            'payment_means': self._parse_payment_means(),
            'taxes': self._parse_tax_totals(),
            'allowances_and_charges': self._parse_allowance_charges(self.root),
            'monetary_totals': self._parse_monetary_totals(),
            'line_items': self._parse_line_items(is_credit_note),
            'embedded_pdf': self._parse_embedded_pdf()
        }

        # Notes
        for note_node in self.root.findall('cbc:Note', namespaces=NS):
            if note_node.text:
                res['notes'].append(note_node.text.strip())

        return res

    def _parse_party(self, party_node: Optional[ET.Element]) -> Dict[str, Any]:
        if party_node is None:
            return {}

        name = self._findtext(party_node, 'cac:PartyName/cbc:Name')
        if not name:
            name = self._findtext(party_node, 'cac:PartyLegalEntity/cbc:RegistrationName')

        vkn_tckn = ""
        for party_id in party_node.findall('cac:PartyIdentification/cbc:ID', namespaces=NS):
            val = (party_id.text or '').strip()
            scheme = (party_id.get('schemeID') or '').upper()
            if scheme in ('VKN', 'TCKN') or len(val) in (10, 11):
                vkn_tckn = val
                break
        if not vkn_tckn:
            vkn_tckn = self._findtext(party_node, 'cac:PartyLegalEntity/cbc:CompanyID')

        addr_node = party_node.find('cac:PostalAddress', namespaces=NS)
        address = {
            'street': self._findtext(addr_node, 'cbc:StreetName'),
            'building_number': self._findtext(addr_node, 'cbc:BuildingNumber'),
            'district': self._findtext(addr_node, 'cbc:CitySubdivisionName'),
            'city': self._findtext(addr_node, 'cbc:CityName'),
            'postal_zone': self._findtext(addr_node, 'cbc:PostalZone'),
            'country': self._findtext(addr_node, 'cac:Country/cbc:Name', 'Türkiye')
        }

        contact_node = party_node.find('cac:Contact', namespaces=NS)
        contact = {
            'phone': self._findtext(contact_node, 'cbc:Telephone'),
            'email': self._findtext(contact_node, 'cbc:ElectronicMail'),
            'website': self._findtext(party_node, 'cbc:WebsiteURI')
        }

        tax_office = self._findtext(party_node, 'cac:PartyTaxScheme/cac:TaxScheme/cbc:Name')

        return {
            'name': name,
            'vat': vkn_tckn,
            'tax_office': tax_office,
            'address': address,
            'contact': contact
        }

    def _parse_supplier(self) -> Dict[str, Any]:
        node = self.root.find('cac:AccountingSupplierParty/cac:Party', namespaces=NS)
        return self._parse_party(node)

    def _parse_customer(self) -> Dict[str, Any]:
        node = self.root.find('cac:AccountingCustomerParty/cac:Party', namespaces=NS)
        return self._parse_party(node)

    def _parse_order_reference(self) -> Dict[str, Any]:
        node = self.root.find('cac:OrderReference', namespaces=NS)
        if node is not None:
            return {
                'id': self._findtext(node, 'cbc:ID'),
                'issue_date': self._findtext(node, 'cbc:IssueDate')
            }
        return {}

    def _parse_despatch_references(self) -> List[Dict[str, Any]]:
        refs = []
        for node in self.root.findall('cac:DespatchDocumentReference', namespaces=NS):
            refs.append({
                'id': self._findtext(node, 'cbc:ID'),
                'issue_date': self._findtext(node, 'cbc:IssueDate')
            })
        return refs

    def _parse_exchange_rate(self) -> Dict[str, Any]:
        node = self.root.find('cac:PricingExchangeRate', namespaces=NS)
        if node is not None:
            return {
                'source_currency': self._findtext(node, 'cbc:SourceCurrencyCode'),
                'target_currency': self._findtext(node, 'cbc:TargetCurrencyCode'),
                'rate': self._findfloat(node, 'cbc:CalculationRate', 1.0)
            }
        return {'rate': 1.0}

    def _parse_payment_means(self) -> List[Dict[str, Any]]:
        means = []
        for node in self.root.findall('cac:PaymentMeans', namespaces=NS):
            iban = self._findtext(node, 'cac:PayeeFinancialAccount/cbc:ID')
            bank_name = self._findtext(node, 'cac:PayeeFinancialAccount/cac:FinancialInstitutionBranch/cac:FinancialInstitution/cbc:Name')
            swift = self._findtext(node, 'cac:PayeeFinancialAccount/cac:FinancialInstitutionBranch/cbc:ID')
            means.append({
                'payment_code': self._findtext(node, 'cbc:PaymentMeansCode'),
                'payment_due_date': self._findtext(node, 'cbc:PaymentDueDate'),
                'iban': iban,
                'bank_name': bank_name,
                'swift': swift
            })
        return means

    def _parse_allowance_charges(self, parent_node: ET.Element) -> List[Dict[str, Any]]:
        items = []
        for node in parent_node.findall('cac:AllowanceCharge', namespaces=NS):
            is_charge = (self._findtext(node, 'cbc:ChargeIndicator').lower() == 'true')
            items.append({
                'is_charge': is_charge,  # True = Charge (Artırım / Yuvarlama), False = Allowance (İskonto)
                'amount': self._findfloat(node, 'cbc:Amount', 0.0),
                'multiplier_factor': self._findfloat(node, 'cbc:MultiplierFactorNumeric', 0.0),
                'reason': self._findtext(node, 'cbc:AllowanceChargeReason')
            })
        return items

    def _parse_tax_totals(self) -> Dict[str, Any]:
        taxes = {
            'total_tax_amount': 0.0,
            'subtotals': []
        }
        for node in self.root.findall('cac:TaxTotal', namespaces=NS):
            total_amt = self._findfloat(node, 'cbc:TaxAmount', 0.0)
            taxes['total_tax_amount'] += total_amt
            for st in node.findall('cac:TaxSubtotal', namespaces=NS):
                code = self._findtext(st, 'cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode')
                name = self._findtext(st, 'cac:TaxCategory/cac:TaxScheme/cbc:Name')
                taxes['subtotals'].append({
                    'taxable_amount': self._findfloat(st, 'cbc:TaxableAmount', 0.0),
                    'tax_amount': self._findfloat(st, 'cbc:TaxAmount', 0.0),
                    'percent': self._findfloat(st, 'cbc:Percent', 0.0),
                    'tax_code': code,
                    'tax_name': name
                })
        return taxes

    def _parse_monetary_totals(self) -> Dict[str, float]:
        node = self.root.find('cac:LegalMonetaryTotal', namespaces=NS)
        if node is None:
            return {}
        return {
            'line_extension_amount': self._findfloat(node, 'cbc:LineExtensionAmount', 0.0),
            'tax_exclusive_amount': self._findfloat(node, 'cbc:TaxExclusiveAmount', 0.0),
            'tax_inclusive_amount': self._findfloat(node, 'cbc:TaxInclusiveAmount', 0.0),
            'allowance_total_amount': self._findfloat(node, 'cbc:AllowanceTotalAmount', 0.0),
            'charge_total_amount': self._findfloat(node, 'cbc:ChargeTotalAmount', 0.0),
            'payable_amount': self._findfloat(node, 'cbc:PayableAmount', 0.0)
        }

    def _parse_line_items(self, is_credit_note: bool) -> List[Dict[str, Any]]:
        line_tag = 'cac:CreditNoteLine' if is_credit_note else 'cac:InvoiceLine'
        lines = []

        for line_node in self.root.findall(line_tag, namespaces=NS):
            item_node = line_node.find('cac:Item', namespaces=NS)
            price_node = line_node.find('cac:Price', namespaces=NS)

            name = self._findtext(item_node, 'cbc:Name')
            desc = self._findtext(item_node, 'cbc:Description', name)
            seller_code = self._findtext(item_node, 'cac:SellersItemIdentification/cbc:ID')
            buyer_code = self._findtext(item_node, 'cac:BuyersItemIdentification/cbc:ID')
            barcode = self._findtext(item_node, 'cac:StandardItemIdentification/cbc:ID')

            qty_node = line_node.find('cbc:InvoicedQuantity' if not is_credit_note else 'cbc:CreditedQuantity', namespaces=NS)
            qty = float(qty_node.text.replace(',', '.')) if (qty_node is not None and qty_node.text) else 1.0
            uom = qty_node.get('unitCode', 'NIU') if qty_node is not None else 'NIU'

            price_unit = self._findfloat(price_node, 'cbc:PriceAmount', 0.0)
            line_ext_amount = self._findfloat(line_node, 'cbc:LineExtensionAmount', 0.0)

            # Line taxes
            line_taxes = []
            for tt in line_node.findall('cac:TaxTotal', namespaces=NS):
                for st in tt.findall('cac:TaxSubtotal', namespaces=NS):
                    code = self._findtext(st, 'cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode')
                    tname = self._findtext(st, 'cac:TaxCategory/cac:TaxScheme/cbc:Name')
                    pct = self._findfloat(st, 'cbc:Percent', 0.0)
                    t_amt = self._findfloat(st, 'cbc:TaxAmount', 0.0)
                    taxable_amt = self._findfloat(st, 'cbc:TaxableAmount', 0.0)
                    line_taxes.append({
                        'code': code,
                        'name': tname,
                        'percent': pct,
                        'amount': t_amt,
                        'taxable_amount': taxable_amt
                    })

            # Line Withholding
            wh_node = line_node.find('cac:WithholdingTaxTotal', namespaces=NS)
            wh_tax = None
            if wh_node is not None:
                wh_st = wh_node.find('cac:TaxSubtotal', namespaces=NS)
                if wh_st is not None:
                    wh_tax = {
                        'percent': self._findfloat(wh_st, 'cbc:Percent', 0.0),
                        'amount': self._findfloat(wh_st, 'cbc:TaxAmount', 0.0),
                        'taxable_amount': self._findfloat(wh_st, 'cbc:TaxableAmount', 0.0)
                    }

            # Line allowances / charges (discounts)
            allowances = self._parse_allowance_charges(line_node)
            discount_amount = sum(a['amount'] for a in allowances if not a['is_charge'])
            charge_amount = sum(a['amount'] for a in allowances if a['is_charge'])

            lines.append({
                'line_id': self._findtext(line_node, 'cbc:ID'),
                'name': name,
                'description': desc,
                'quantity': qty,
                'uom_code': uom,
                'price_unit': price_unit,
                'line_extension_amount': line_ext_amount,
                'seller_item_code': seller_code,
                'buyer_item_code': buyer_code,
                'barcode': barcode,
                'taxes': line_taxes,
                'withholding': wh_tax,
                'discount_amount': discount_amount,
                'charge_amount': charge_amount
            })

        return lines

    def _parse_embedded_pdf(self) -> Optional[bytes]:
        """Extracts base64 encoded PDF from AdditionalDocumentReference if present."""
        for doc_ref in self.root.findall('cac:AdditionalDocumentReference', namespaces=NS):
            doc_type = self._findtext(doc_ref, 'cbc:DocumentType', '').lower()
            att = doc_ref.find('cac:Attachment/cbc:EmbeddedDocumentBinaryObject', namespaces=NS)
            if att is not None and att.text:
                mime = (att.get('mimeCode') or '').lower()
                if 'pdf' in mime or 'pdf' in doc_type:
                    try:
                        return base64.b64decode(att.text.strip())
                    except Exception as e:
                        logger.warning("Could not decode embedded PDF: %s", e)
        return None
