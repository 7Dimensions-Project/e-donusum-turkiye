"""Uyumsoft sağlayıcısı (SOAP / WS-Security UsernameToken).

Uyumsoft e-Fatura servisi SOAP 1.1 konuşur. Ek bağımlılık getirmemek için
(Odoo.sh yalnız saf-Python paketleri kurar) ``zeep`` yerine elle SOAP zarfı
kurulur ve yanıt ``lxml`` ile ayrıştırılır — ikisi de Odoo'da hazırdır.

Not: Uyumsoft'un uç nokta adresleri ve işlem adları sözleşmeye göre değişebildiği
için ``sd.edonusum.backend.uyumsoft_endpoint`` ile geçersiz kılınabilir.
"""

import logging

import requests
from lxml import etree

from .base import EDonusumError, EDonusumProvider, EDonusumRetryableError, InboundDocument, register

_logger = logging.getLogger(__name__)

PROD_ENDPOINT = "https://efatura.uyumsoft.com.tr/Services/Integration"
TEST_ENDPOINT = "https://efatura-test.uyumsoft.com.tr/Services/Integration"
NS = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "u": "http://tempuri.org/",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
}


@register
class UyumsoftProvider(EDonusumProvider):
    name = "uyumsoft"

    def __init__(self, backend):
        super().__init__(backend)
        self.endpoint = backend.uyumsoft_endpoint or (
            TEST_ENDPOINT if backend.use_test_env else PROD_ENDPOINT
        )

    # -- SOAP altyapısı ---------------------------------------------------

    def _envelope(self, operation: str, body_xml: str) -> bytes:
        backend = self.backend.sudo()  # sudo: servis parolası yalnız sistem yöneticisinde okunabilir
        if not backend.uyumsoft_username or not backend.uyumsoft_password:
            raise EDonusumError("Uyumsoft web servis kullanıcı adı/şifresi tanımlı değil.")
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" xmlns:u="http://tempuri.org/">'
            "<s:Header>"
            '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/'
            'oasis-200401-wss-wssecurity-secext-1.0.xsd">'
            "<wsse:UsernameToken>"
            f"<wsse:Username>{_escape(backend.uyumsoft_username)}</wsse:Username>"
            f"<wsse:Password>{_escape(backend.uyumsoft_password)}</wsse:Password>"
            "</wsse:UsernameToken></wsse:Security></s:Header>"
            f"<s:Body><u:{operation}>{body_xml}</u:{operation}></s:Body></s:Envelope>"
        ).encode()

    def _call(self, operation: str, body_xml: str = ""):
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"http://tempuri.org/IIntegration/{operation}",
        }
        try:
            response = requests.post(self.endpoint, data=self._envelope(operation, body_xml),
                                     headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EDonusumRetryableError(f"Uyumsoft bağlantı hatası: {exc}") from exc

        _logger.info('"POST %s" %s %s', operation, response.status_code, len(response.content))
        if response.status_code >= 500 and b"Fault" not in response.content:
            raise EDonusumRetryableError("Uyumsoft servisi yanıt vermiyor.", response.status_code)

        try:
            tree = etree.fromstring(response.content)
        except etree.XMLSyntaxError as exc:
            raise EDonusumError(f"Uyumsoft yanıtı ayrıştırılamadı: {exc}") from exc

        fault = tree.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            detail = "".join(fault.itertext()).strip()
            raise EDonusumError(f"Uyumsoft SOAP hatası: {detail[:400]}", response.status_code)
        return tree

    @staticmethod
    def _text(node, tag: str, default: str = "") -> str:
        found = node.find(f".//{{*}}{tag}")
        return (found.text or default).strip() if found is not None and found.text else default

    # -- Sözleşme ---------------------------------------------------------

    def test_connection(self) -> str:
        self._call("IsEInvoiceUser", "<vknTckn>0000000000</vknTckn>")
        return "Uyumsoft web servisi bağlantısı doğrulandı."

    def list_inbound(self, date_start, date_end, page=1, page_size=50):
        body = (
            f"<query><StartDate>{date_start}</StartDate><EndDate>{date_end}</EndDate>"
            f"<PageIndex>{page - 1}</PageIndex><PageSize>{page_size}</PageSize></query>"
        )
        tree = self._call("GetInboxInvoiceList", body)
        documents = []
        for node in tree.iterfind(".//{*}InvoiceInfo"):
            doc_uuid = self._text(node, "Ettn") or self._text(node, "Id")
            if not doc_uuid:
                continue
            documents.append(InboundDocument(
                uuid=doc_uuid,
                number=self._text(node, "InvoiceId") or self._text(node, "DocumentId"),
                issue_date=self._text(node, "IssueDate")[:10],
                supplier_vkn=self._text(node, "SenderVknTckn") or self._text(node, "TargetTaxNumber"),
                profile=self._text(node, "Profile").upper(),
                status=self._text(node, "Status"),
                answer_status=self._text(node, "ResponseStatus"),
                raw={"ettn": doc_uuid},
            ))
        return documents

    def get_status(self, doc_uuid):
        tree = self._call("GetInvoiceStatus", f"<ettn>{doc_uuid}</ettn>")
        return {
            "status": self._text(tree, "Status"),
            "answer_status": self._text(tree, "ResponseStatus") or self._text(tree, "AnswerType"),
            "answer_note": self._text(tree, "Description") or self._text(tree, "ResponseNote"),
        }

    def send_answer(self, doc_uuid, answer, reason=""):
        answer = self.normalize_answer(answer)
        body = (
            f"<ettn>{doc_uuid}</ettn>"
            f"<isAccepted>{'true' if answer == 'KABUL' else 'false'}</isAccepted>"
            f"<note>{_escape(reason)}</note>"
        )
        tree = self._call("SetInvoiceResponse", body)
        result = (self._text(tree, "IsSucceded") or self._text(tree, "Result") or "true").lower()
        if result in ("false", "0"):
            message = self._text(tree, "Message") or self._text(tree, "Description")
            if "already" in message.lower() or "daha önce" in message.lower():
                return {"already_answered": True, "detail": message}
            raise EDonusumError(f"Uyumsoft uygulama yanıtı reddedildi: {message[:300]}")
        return {"already_answered": False}

    def get_document_xml(self, doc_uuid):
        tree = self._call("GetInvoice", f"<ettn>{doc_uuid}</ettn><isHtml>false</isHtml>")
        payload = self._text(tree, "Data") or self._text(tree, "Content")
        if not payload:
            raise EDonusumError("Uyumsoft XML içeriği boş döndü.")
        import base64
        return base64.b64decode(payload)


def _escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
