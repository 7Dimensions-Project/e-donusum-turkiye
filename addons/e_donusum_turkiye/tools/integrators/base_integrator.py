# -*- coding: utf-8 -*-
"""
Base Abstract Integrator for Turkish E-Dönüşüm providers.
Defines the standard contract that all integrators (Nilvera, Paraşüt, Uyumsoft, etc.) must fulfill.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseIntegrator(ABC):
    """Abstract Base Class for GİB E-Dönüşüm Integrators."""

    def __init__(self, company):
        self.company = company
        self.provider_name = "base"

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Tests API / Web Service credentials and returns status dict."""
        pass

    @abstractmethod
    def get_inbound_invoices(self, start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """
        Fetches list of inbound e-invoices.
        Returns dict containing list of items with standard keys:
        [{'UUID': str, 'InvoiceNumber': str, 'IssueDate': str, 'SupplierVKN': str, 'Status': str, 'Raw': dict}]
        """
        pass

    @abstractmethod
    def get_inbound_invoice_status(self, doc_uuid_or_id: str) -> Dict[str, Any]:
        """
        Queries status of an invoice.
        Returns dict with standard keys:
        {'Status': str, 'AnswerStatus': str ('KABUL'|'RED'|'BEKLIYOR'), 'AnswerNote': str}
        """
        pass

    @abstractmethod
    def get_inbound_invoice_xml(self, doc_uuid_or_id: str) -> bytes:
        """Downloads signed UBL-TR 2.1 XML bytes."""
        pass

    @abstractmethod
    def get_inbound_invoice_pdf(self, doc_uuid_or_id: str) -> bytes:
        """Downloads official rendered PDF bytes."""
        pass

    @abstractmethod
    def send_answer(self, doc_uuid_or_id: str, status: str = 'KABUL', reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends official GİB Application Response (Uygulama Yanıtı).
        status: 'KABUL' or 'RED'
        reason: Optional rejection reason
        """
        pass

    @abstractmethod
    def check_taxpayer(self, vkn_tckn: str) -> Dict[str, Any]:
        """
        Queries whether the given VKN/TCKN is registered in GİB E-Invoice directory.
        Returns {'IsTaxPayer': bool, 'Alias': str, 'Title': str}
        """
        pass
