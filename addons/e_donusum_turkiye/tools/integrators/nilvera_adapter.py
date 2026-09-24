# -*- coding: utf-8 -*-
"""
Nilvera Integrator Adapter for E-Dönüşüm Türkiye.
Wraps Nilvera REST API into the standard BaseIntegrator interface.
"""

from typing import Dict, Any, Optional
from .base_integrator import BaseIntegrator
from ..nilvera_client import NilveraClient, NilveraAPIError

class NilveraIntegrator(BaseIntegrator):
    def __init__(self, company):
        super().__init__(company)
        self.provider_name = "nilvera"
        api_key = getattr(company, 'nilvera_api_key', '') or ''
        env_mode = getattr(company, 'nilvera_environment', 'production') or 'production'
        self.client = NilveraClient(api_key=api_key, environment=env_mode)

    def test_connection(self) -> Dict[str, Any]:
        res = self.client.get_inbound_invoices(page=1, page_size=1)
        return {"status": "success", "message": f"Nilvera API ({self.client.environment}) bağlantısı başarılı."}

    def get_inbound_invoices(self, start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        raw = self.client.get_inbound_invoices(start_date=start_date, end_date=end_date, page=page, page_size=page_size)
        items = raw.get('Content', []) or raw.get('Items', [])
        normalized = []
        for it in items:
            normalized.append({
                'UUID': it.get('UUID'),
                'InvoiceNumber': it.get('InvoiceNumber'),
                'IssueDate': it.get('IssueDate'),
                'SupplierVKN': it.get('TaxNumber') or it.get('SupplierVKN'),
                'SupplierName': it.get('TaxPayerTitle') or it.get('SupplierName'),
                'ProfileID': it.get('ProfileID') or it.get('InvoiceProfile'),
                'Status': it.get('Status') or it.get('InvoiceStatus'),
                'AnswerStatus': it.get('AnswerStatus'),
                'Raw': it
            })
        return {'items': normalized, 'raw': raw}

    def get_inbound_invoice_status(self, doc_uuid_or_id: str) -> Dict[str, Any]:
        raw = self.client.get_inbound_invoice_status(doc_uuid_or_id)
        status_text = (raw.get('Status') or raw.get('InvoiceStatus') or '').upper()
        ans_status = (raw.get('AnswerStatus') or '').upper()
        ans_note = raw.get('AnswerNote') or ''
        return {
            'Status': status_text,
            'AnswerStatus': ans_status,
            'AnswerNote': ans_note,
            'Raw': raw
        }

    def get_inbound_invoice_xml(self, doc_uuid_or_id: str) -> bytes:
        return self.client.get_inbound_invoice_xml(doc_uuid_or_id)

    def get_inbound_invoice_pdf(self, doc_uuid_or_id: str) -> bytes:
        return self.client.get_inbound_invoice_pdf(doc_uuid_or_id)

    def send_answer(self, doc_uuid_or_id: str, status: str = 'KABUL', reason: Optional[str] = None) -> Dict[str, Any]:
        return self.client.send_answer(doc_uuid_or_id, status=status, reason=reason)

    def check_taxpayer(self, vkn_tckn: str) -> Dict[str, Any]:
        res = self.client.check_taxpayer(vkn_tckn)
        is_tp = bool(res and (res.get('IsTaxPayer') or res.get('Status')))
        return {
            'IsTaxPayer': is_tp,
            'Alias': res.get('Alias') or '',
            'Title': res.get('Title') or ''
        }
