# -*- coding: utf-8 -*-
"""
Paraşüt Integrator Adapter for E-Dönüşüm Türkiye.
Implements BaseIntegrator using Paraşüt API v4 (OAuth2 REST API).
"""

import time
import requests
from typing import Dict, Any, Optional
from .base_integrator import BaseIntegrator

class ParasutAPIError(Exception):
    pass

class ParasutIntegrator(BaseIntegrator):
    def __init__(self, company):
        super().__init__(company)
        self.provider_name = "parasut"
        self.client_id = (getattr(company, 'parasut_client_id', '') or '').strip()
        self.client_secret = (getattr(company, 'parasut_client_secret', '') or '').strip()
        self.username = (getattr(company, 'parasut_username', '') or '').strip()
        self.password = (getattr(company, 'parasut_password', '') or '').strip()
        self.parasut_company_id = str(getattr(company, 'parasut_company_id', '') or '').strip()
        
        self.token_url = "https://api.parasut.com/oauth/token"
        self.base_url = f"https://api.parasut.com/v4/{self.parasut_company_id}"
        self.access_token = None
        self.token_expires_at = 0

    def _authenticate(self):
        if not all([self.client_id, self.client_secret, self.username, self.password, self.parasut_company_id]):
            raise ParasutAPIError("Paraşüt API kimlik bilgileri (Client ID, Secret, Kullanıcı Adı, Şifre, Şirket ID) eksik!")

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
        }
        res = requests.post(self.token_url, data=payload, timeout=25)
        if res.status_code != 200:
            raise ParasutAPIError(f"Paraşüt yetkilendirme hatası [{res.status_code}]: {res.text}")

        data = res.json()
        self.access_token = data.get("access_token")
        expires_in = data.get("expires_in", 7200)
        self.token_expires_at = time.time() + expires_in - 120

    def _get_headers(self, content_type="application/vnd.api+json"):
        if not self.access_token or time.time() >= self.token_expires_at:
            self._authenticate()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.api+json",
            "Content-Type": content_type
        }

    def test_connection(self) -> Dict[str, Any]:
        self._authenticate()
        url = f"{self.base_url}/me"
        res = requests.get(url, headers=self._get_headers(), timeout=15)
        if res.status_code in (200, 204):
            return {"status": "success", "message": "Paraşüt API v4 bağlantısı ve yetkilendirmesi başarılı."}
        # Fallback to test getting contacts
        url = f"{self.base_url}/contacts?page[size]=1"
        res = requests.get(url, headers=self._get_headers(), timeout=15)
        if res.status_code == 200:
            return {"status": "success", "message": "Paraşüt API v4 bağlantısı başarılı."}
        raise ParasutAPIError(f"Paraşüt bağlantı testi başarısız [{res.status_code}]: {res.text}")

    def get_inbound_invoices(self, start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        url = f"{self.base_url}/e_invoices"
        params = {
            "page[number]": page,
            "page[size]": page_size,
            "filter[direction]": "inbound"
        }
        if start_date:
            params["filter[issue_date]"] = f"{start_date}..."
        
        res = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
        if res.status_code != 200:
            raise ParasutAPIError(f"Paraşüt gelen faturalar alınamadı [{res.status_code}]: {res.text}")

        data = res.json()
        items = data.get("data", [])
        normalized = []
        for it in items:
            attrs = it.get("attributes", {})
            normalized.append({
                'UUID': attrs.get('uuid'),
                'ID': it.get('id'),
                'InvoiceNumber': attrs.get('invoice_no'),
                'IssueDate': attrs.get('issue_date'),
                'SupplierVKN': attrs.get('vkn'),
                'SupplierName': attrs.get('sender_name') or attrs.get('contact_name'),
                'ProfileID': attrs.get('scenario') or 'TICARIFATURA',
                'Status': attrs.get('status'),
                'AnswerStatus': 'KABUL' if attrs.get('response_status') == 'accepted' else ('RED' if attrs.get('response_status') == 'rejected' else 'BEKLIYOR'),
                'Raw': it
            })
        return {'items': normalized, 'raw': data}

    def get_inbound_invoice_status(self, doc_uuid_or_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/e_invoices/{doc_uuid_or_id}"
        res = requests.get(url, headers=self._get_headers(), timeout=20)
        if res.status_code != 200:
            raise ParasutAPIError(f"Paraşüt fatura durumu alınamadı [{res.status_code}]: {res.text}")

        attrs = res.json().get("data", {}).get("attributes", {})
        resp_status = (attrs.get("response_status") or "").upper()
        gib_status = (attrs.get("status") or "").upper()
        
        answer_status = "BEKLIYOR"
        if resp_status in ("ACCEPTED", "KABUL") or "KABUL" in gib_status:
            answer_status = "KABUL"
        elif resp_status in ("REJECTED", "RED") or "RED" in gib_status:
            answer_status = "RED"

        return {
            'Status': gib_status,
            'AnswerStatus': answer_status,
            'AnswerNote': attrs.get("response_reason") or "",
            'Raw': attrs
        }

    def get_inbound_invoice_xml(self, doc_uuid_or_id: str) -> bytes:
        # Check if xml link or direct endpoint exists
        url = f"{self.base_url}/e_invoices/{doc_uuid_or_id}/xml"
        res = requests.get(url, headers=self._get_headers(content_type="application/xml"), timeout=30)
        if res.status_code == 200:
            return res.content
        raise ParasutAPIError(f"Paraşüt XML indirilemedi [{res.status_code}]: {res.text}")

    def get_inbound_invoice_pdf(self, doc_uuid_or_id: str) -> bytes:
        url = f"{self.base_url}/e_invoices/{doc_uuid_or_id}/pdf"
        res = requests.get(url, headers=self._get_headers(content_type="application/pdf"), timeout=30)
        if res.status_code == 200:
            return res.content
        raise ParasutAPIError(f"Paraşüt PDF indirilemedi [{res.status_code}]: {res.text}")

    def send_answer(self, doc_uuid_or_id: str, status: str = 'KABUL', reason: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/e_invoices/{doc_uuid_or_id}/responses"
        resp_type = "accept" if status.upper() == "KABUL" else "reject"
        payload = {
            "data": {
                "type": "e_invoice_responses",
                "attributes": {
                    "response_type": resp_type
                }
            }
        }
        if reason:
            payload["data"]["attributes"]["reason"] = reason.strip()
        elif resp_type == "reject":
            payload["data"]["attributes"]["reason"] = "Ticari uyuşmazlık nedeniyle reddedilmiştir."

        res = requests.post(url, json=payload, headers=self._get_headers(), timeout=25)
        if res.status_code in (200, 201, 202, 204):
            return {"status": "success", "message": f"Paraşüt e-Fatura {resp_type} yanıtı iletildi.", "raw": res.text}
        raise ParasutAPIError(f"Paraşüt uygulama yanıtı gönderilemedi [{res.status_code}]: {res.text}")

    def check_taxpayer(self, vkn_tckn: str) -> Dict[str, Any]:
        url = f"{self.base_url}/e_invoice_inboxes"
        params = {"filter[vkn]": vkn_tckn}
        res = requests.get(url, headers=self._get_headers(), params=params, timeout=20)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data:
                attrs = data[0].get("attributes", {})
                return {
                    'IsTaxPayer': True,
                    'Alias': attrs.get('identifier') or attrs.get('alias') or '',
                    'Title': attrs.get('name') or attrs.get('title') or ''
                }
        return {'IsTaxPayer': False, 'Alias': '', 'Title': ''}
