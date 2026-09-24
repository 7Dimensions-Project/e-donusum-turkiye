# -*- coding: utf-8 -*-
"""
Nilvera REST API Client for Odoo E-Dönüşüm Türkiye.
Handles authentication, e-Fatura (inbound/outbound), e-Arşiv, e-SMM,
GİB Application Responses (KABUL / RED), and status inquiries.
"""

import json
import logging
import requests
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger("nilvera_client")

class NilveraAPIError(Exception):
    """Custom exception for Nilvera API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class NilveraClient:
    """Robust client for Nilvera E-Dönüşüm REST API."""

    PROD_URL = "https://api.nilvera.com"
    TEST_URL = "https://testapi.nilvera.com"

    def __init__(self, api_key: str, environment: str = "production", timeout: int = 30):
        self.api_key = (api_key or "").strip()
        self.environment = environment.lower() if environment else "production"
        self.base_url = self.TEST_URL if self.environment in ("test", "sandbox") else self.PROD_URL
        self.timeout = timeout
        self.session = requests.Session()

    def _get_headers(self, content_type: str = "application/json") -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                 data: Optional[Any] = None, json_data: Optional[Any] = None,
                 headers_override: Optional[Dict] = None, raw_response: bool = False) -> Any:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = headers_override or self._get_headers()

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=headers,
                timeout=self.timeout
            )
        except requests.RequestException as e:
            logger.error("Nilvera network error (%s %s): %s", method, url, e)
            raise NilveraAPIError(f"Nilvera bağlantı hatası: {str(e)}")

        if raw_response:
            return response

        if response.status_code not in (200, 201, 202, 204):
            err_msg = f"Nilvera API Hatası [{response.status_code}] ({method} {endpoint}): {response.text}"
            logger.warning(err_msg)
            raise NilveraAPIError(err_msg, status_code=response.status_code, response_text=response.text)

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except Exception:
            return response.text

    # -------------------------------------------------------------------------
    # 1. Gelen e-Faturalar (Inbound / Purchase)
    # -------------------------------------------------------------------------

    def get_inbound_invoices(self, start_date: Optional[str] = None, end_date: Optional[str] = None,
                             page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """Fetch list of inbound e-invoices."""
        params = {
            "Page": page,
            "PageSize": page_size
        }
        if start_date:
            params["StartDate"] = start_date
        if end_date:
            params["EndDate"] = end_date
        return self._request("GET", "/einvoice/Purchase", params=params)

    def get_inbound_invoice_status(self, uuid: str) -> Dict[str, Any]:
        """Fetch GİB status, answer notes and details for an inbound invoice."""
        return self._request("GET", f"/einvoice/Purchase/{uuid}/Status")

    def get_inbound_invoice_pdf(self, uuid: str) -> bytes:
        """Download official visual PDF for an inbound invoice."""
        resp = self._request("GET", f"/einvoice/Purchase/{uuid}/pdf", raw_response=True)
        if resp.status_code == 200:
            return resp.content
        raise NilveraAPIError(f"PDF indirilemedi [{resp.status_code}]: {resp.text}", status_code=resp.status_code)

    def get_inbound_invoice_xml(self, uuid: str) -> bytes:
        """Download signed UBL-TR 2.1 XML for an inbound invoice."""
        resp = self._request("GET", f"/einvoice/Purchase/{uuid}/xml", raw_response=True)
        if resp.status_code == 200:
            return resp.content
        raise NilveraAPIError(f"XML indirilemedi [{resp.status_code}]: {resp.text}", status_code=resp.status_code)

    def send_answer(self, uuid: str, status: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Send Application Response (Uygulama Yanıtı) to GİB via Nilvera.
        status: 'KABUL' or 'RED'
        """
        st = status.strip().upper()
        if st not in ("KABUL", "RED"):
            raise ValueError("Status must be either 'KABUL' or 'RED'")

        payload = {
            "UUID": uuid,
            "Status": st
        }
        if reason:
            payload["Reason"] = reason

        try:
            return self._request("POST", "/einvoice/Purchase/SendAnswer", json_data=payload)
        except NilveraAPIError as ne:
            # 409 Conflict typically indicates already answered
            if ne.status_code == 409:
                logger.info("Invoice %s was already answered: %s", uuid, ne.response_text)
                return {"status": "already_answered", "detail": ne.response_text}
            raise

    # -------------------------------------------------------------------------
    # 2. Giden e-Faturalar (Outbound / Sales)
    # -------------------------------------------------------------------------

    def send_outbound_invoice(self, ubl_xml_content: Union[str, bytes]) -> Dict[str, Any]:
        """Upload and send an outbound e-invoice UBL XML to GİB."""
        headers = self._get_headers(content_type="application/xml")
        return self._request("POST", "/einvoice/Sales/Send", data=ubl_xml_content, headers_override=headers)

    def get_outbound_invoice_status(self, uuid: str) -> Dict[str, Any]:
        """Fetch GİB status of an outbound e-invoice."""
        return self._request("GET", f"/einvoice/Sales/{uuid}/Status")

    def get_outbound_invoice_pdf(self, uuid: str) -> bytes:
        """Download PDF of outbound sales invoice."""
        resp = self._request("GET", f"/einvoice/Sales/{uuid}/pdf", raw_response=True)
        if resp.status_code == 200:
            return resp.content
        raise NilveraAPIError(f"PDF indirilemedi [{resp.status_code}]", status_code=resp.status_code)

    # -------------------------------------------------------------------------
    # 3. e-Arşiv Fatura
    # -------------------------------------------------------------------------

    def send_earchive_invoice(self, ubl_xml_content: Union[str, bytes]) -> Dict[str, Any]:
        """Send e-Arşiv invoice."""
        headers = self._get_headers(content_type="application/xml")
        return self._request("POST", "/earchive/Invoices/Send", data=ubl_xml_content, headers_override=headers)

    def get_earchive_status(self, uuid: str) -> Dict[str, Any]:
        """Get e-Arşiv status."""
        return self._request("GET", f"/earchive/Invoices/{uuid}/Status")

    def get_earchive_pdf(self, uuid: str) -> bytes:
        """Download e-Arşiv PDF."""
        resp = self._request("GET", f"/earchive/Invoices/{uuid}/pdf", raw_response=True)
        if resp.status_code == 200:
            return resp.content
        raise NilveraAPIError(f"e-Arşiv PDF indirilemedi [{resp.status_code}]", status_code=resp.status_code)

    # -------------------------------------------------------------------------
    # 4. e-SMM (Serbest Meslek Makbuzu)
    # -------------------------------------------------------------------------

    def get_esmm_documents(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Fetch e-SMM receipts."""
        params = {}
        if start_date:
            params["StartDate"] = start_date
        if end_date:
            params["EndDate"] = end_date
        return self._request("GET", "/esmm/Invoices", params=params)

    # -------------------------------------------------------------------------
    # 5. GİB Mükellef Sorgulama (Taxpayer Lookup)
    # -------------------------------------------------------------------------

    def check_taxpayer(self, vkn_or_tckn: str) -> Dict[str, Any]:
        """Check whether a partner VKN/TCKN is an e-Invoice registered taxpayer."""
        clean_vkn = "".join(filter(str.isdigit, str(vkn_or_tckn)))
        return self._request("GET", f"/general/TaxPayer/{clean_vkn}")
