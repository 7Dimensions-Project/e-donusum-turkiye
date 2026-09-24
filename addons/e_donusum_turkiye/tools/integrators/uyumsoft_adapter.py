# -*- coding: utf-8 -*-
"""
Uyumsoft Integrator Adapter for E-Dönüşüm Türkiye.
Implements BaseIntegrator using Uyumsoft SOAP WCF Web Services.
"""

import io
import base64
import zipfile
import logging
import requests
from typing import Dict, Any, Optional
from .base_integrator import BaseIntegrator

logger = logging.getLogger("uyumsoft_adapter")

try:
    import zeep
    from zeep.transports import Transport
    from zeep.wsse.username import UsernameToken
    ZEEP_AVAILABLE = True
except ImportError:
    ZEEP_AVAILABLE = False

class UyumsoftAPIError(Exception):
    pass

class UyumsoftIntegrator(BaseIntegrator):
    def __init__(self, company):
        super().__init__(company)
        self.provider_name = "uyumsoft"
        self.username = (getattr(company, 'uyumsoft_username', '') or '').strip()
        self.password = (getattr(company, 'uyumsoft_password', '') or '').strip()
        self.environment = getattr(company, 'uyumsoft_environment', 'prod') or 'prod'
        
        if self.environment == 'test':
            self.ws_url = "https://efatura-test.uyumsoft.com.tr/Services/Integration?wsdl"
        else:
            self.ws_url = "https://efatura.uyum.com.tr/Services/Integration?wsdl"
            
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._init_client()
        return self._client

    def _init_client(self):
        if not ZEEP_AVAILABLE:
            raise UyumsoftAPIError("Zeep kütüphanesi yüklü değil! Lütfen 'pip install zeep' komutunu çalıştırın.")
        if not self.username or not self.password:
            raise UyumsoftAPIError("Uyumsoft kullanıcı adı veya şifresi tanımlanmamış!")

        session = requests.Session()
        transport = Transport(session=session, timeout=40, operation_timeout=40)
        wsse = UsernameToken(self.username, self.password)
        try:
            self._client = zeep.Client(wsdl=self.ws_url, wsse=wsse, transport=transport)
        except Exception as e:
            raise UyumsoftAPIError(f"Uyumsoft WSDL bağlantı hatası: {str(e)}")

    def test_connection(self) -> Dict[str, Any]:
        try:
            cl = self.client
            # Call WhoAmI or simple test
            res = cl.service.WhoAmI()
            return {"status": "success", "message": f"Uyumsoft ({self.environment}) bağlantısı başarılı: {res}"}
        except Exception as e:
            raise UyumsoftAPIError(f"Uyumsoft bağlantı testi başarısız: {str(e)}")

    def get_inbound_invoices(self, start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        cl = self.client
        query = {
            'PageIndex': page - 1,
            'PageSize': page_size,
            'ExecutionStartDate': start_date,
            'ExecutionEndDate': end_date
        }
        try:
            res = cl.service.GetInboxInvoices(query=query)
            items = []
            if res and hasattr(res, 'Value') and res.Value:
                for inv in getattr(res.Value, 'InboxInvoice', []):
                    items.append({
                        'UUID': inv.InvoiceId,
                        'InvoiceNumber': inv.InvoiceNumber,
                        'IssueDate': str(inv.ExecutionDate),
                        'SupplierVKN': inv.SourceVkn,
                        'SupplierName': inv.SourceTitle,
                        'ProfileID': inv.Scenario,
                        'Status': inv.Status,
                        'AnswerStatus': 'KABUL' if 'KABUL' in str(inv.Status).upper() else ('RED' if 'RED' in str(inv.Status).upper() else 'BEKLIYOR'),
                        'Raw': inv
                    })
            return {'items': items, 'raw': res}
        except Exception as e:
            raise UyumsoftAPIError(f"Uyumsoft gelen faturalar alınamadı: {str(e)}")

    def get_inbound_invoice_status(self, doc_uuid_or_id: str) -> Dict[str, Any]:
        cl = self.client
        try:
            res = cl.service.GetInboxInvoiceStatus(invoiceId=doc_uuid_or_id)
            status_text = str(getattr(res, 'Status', ''))
            ans_status = 'BEKLIYOR'
            if 'KABUL' in status_text.upper():
                ans_status = 'KABUL'
            elif 'RED' in status_text.upper():
                ans_status = 'RED'
            return {
                'Status': status_text,
                'AnswerStatus': ans_status,
                'AnswerNote': getattr(res, 'Message', ''),
                'Raw': res
            }
        except Exception as e:
            raise UyumsoftAPIError(f"Uyumsoft durum sorgulama hatası: {str(e)}")

    def get_inbound_invoice_xml(self, doc_uuid_or_id: str) -> bytes:
        cl = self.client
        try:
            res = cl.service.GetInboxInvoiceData(invoiceId=doc_uuid_or_id)
            raw_data = getattr(res, 'Value', None) or res
            return self._extract_xml(raw_data)
        except Exception as e:
            raise UyumsoftAPIError(f"Uyumsoft XML indirme hatası: {str(e)}")

    def get_inbound_invoice_pdf(self, doc_uuid_or_id: str) -> bytes:
        cl = self.client
        try:
            res = cl.service.GetInboxInvoicePdf(invoiceId=doc_uuid_or_id)
            if hasattr(res, 'Value') and res.Value:
                return base64.b64decode(res.Value) if isinstance(res.Value, str) else res.Value
            raise UyumsoftAPIError("PDF verisi boş döndü.")
        except Exception as e:
            raise UyumsoftAPIError(f"Uyumsoft PDF indirme hatası: {str(e)}")

    def send_answer(self, doc_uuid_or_id: str, status: str = 'KABUL', reason: Optional[str] = None) -> Dict[str, Any]:
        cl = self.client
        response_status = 1 if status.upper() == 'KABUL' else 2
        try:
            req = {
                'InvoiceId': doc_uuid_or_id,
                'Status': response_status,
                'Reason': reason or ('Kabul edildi' if status.upper() == 'KABUL' else 'Hatalı fatura')
            }
            res = cl.service.SendInvoiceResponse(response=req)
            return {"status": "success", "message": f"Uyumsoft {status} yanıtı iletildi.", "raw": res}
        except Exception as e:
            raise UyumsoftAPIError(f"Uyumsoft uygulama yanıtı gönderilemedi: {str(e)}")

    def check_taxpayer(self, vkn_tckn: str) -> Dict[str, Any]:
        cl = self.client
        try:
            res = cl.service.IsEInvoiceUser(vkn=vkn_tckn)
            is_user = bool(getattr(res, 'Value', False))
            return {'IsTaxPayer': is_user, 'Alias': '', 'Title': ''}
        except Exception as e:
            return {'IsTaxPayer': False, 'Alias': '', 'Title': ''}

    def _extract_xml(self, data) -> bytes:
        if isinstance(data, str):
            try:
                data = base64.b64decode(data)
            except Exception:
                data = data.encode('utf-8')
        if isinstance(data, (bytes, bytearray)):
            if data.startswith(b'PK\x03\x04'):
                with zipfile.ZipFile(io.BytesIO(data), 'r') as z:
                    for name in z.namelist():
                        if name.endswith('.xml'):
                            return z.read(name)
            return bytes(data)
        return b''
