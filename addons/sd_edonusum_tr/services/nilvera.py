"""Nilvera sağlayıcısı.

HTTP istemcisini **yeniden yazmaz**: Odoo çekirdeğindeki
``odoo.addons.l10n_tr_nilvera.lib.nilvera_client._get_nilvera_client`` kullanılır.
Böylece taban adres (canlı/test), oturum yönetimi, zaman aşımı, loglama ve hata
biçimi çekirdekle aynı kalır; Odoo bunları güncellediğinde biz de güncelleniriz.

API anahtarı da çekirdeğin ``res.company.l10n_tr_nilvera_api_key`` alanından
okunur — aynı sırrı ikinci bir yerde saklamayız.
"""

import logging

from odoo.addons.l10n_tr_nilvera.lib.nilvera_client import _get_nilvera_client

from .base import EDonusumError, EDonusumProvider, EDonusumRetryableError, InboundDocument, register

_logger = logging.getLogger(__name__)


@register
class NilveraProvider(EDonusumProvider):
    name = "nilvera"

    def _client(self):
        company = self.company.sudo()  # sudo: API anahtarı yalnız muhasebe yöneticisinde okunabilir
        if not company.l10n_tr_nilvera_api_key:
            raise EDonusumError(
                f"'{self.company.name}' şirketi için Nilvera API anahtarı tanımlı değil "
                "(Muhasebe → Ayarlar → Türkiye - Nilvera)."
            )
        return _get_nilvera_client(company, timeout_limit=self.timeout)

    def test_connection(self) -> str:
        with self._client() as client:
            response = client.request("GET", "/einvoice/Purchase", params={"Page": 1, "PageSize": 1},
                                      handle_response=False)
        if response.status_code in (401, 403):
            raise EDonusumError("Nilvera API anahtarı reddedildi (yetki yok).", response.status_code)
        if response.status_code >= 500:
            raise EDonusumRetryableError("Nilvera sunucu hatası.", response.status_code)
        if response.status_code >= 400:
            raise EDonusumError(f"Nilvera bağlantı hatası [{response.status_code}].", response.status_code,
                                response.text[:500])
        env = "test" if self.company.sudo().l10n_tr_nilvera_use_test_env else "canlı"
        return f"Nilvera ({env}) bağlantısı doğrulandı."

    def list_inbound(self, date_start, date_end, page=1, page_size=50):
        with self._client() as client:
            data = client.request("GET", "/einvoice/Purchase", params={
                "StartDate": date_start,
                "EndDate": date_end,
                "Page": page,
                "PageSize": page_size,
                "SortColumn": "CreationDateTime",
                "SortType": "ASC",
            })
        items = data.get("Content") or data.get("Items") or []
        documents = []
        for item in items:
            doc_uuid = item.get("UUID") or item.get("Uuid")
            if not doc_uuid:
                continue
            documents.append(InboundDocument(
                uuid=doc_uuid,
                number=item.get("InvoiceNumber") or item.get("Number") or "",
                issue_date=(item.get("IssueDate") or "")[:10],
                supplier_vkn=item.get("SenderTaxNumber") or item.get("TaxNumber") or "",
                profile=(item.get("ProfileID") or item.get("Profile") or "").upper(),
                status=(item.get("StatusCode") or item.get("Status") or ""),
                answer_status=(item.get("AnswerStatus") or item.get("Answer") or ""),
                raw=item,
            ))
        return documents

    def get_status(self, doc_uuid):
        with self._client() as client:
            data = client.request("GET", f"/einvoice/Purchase/{doc_uuid}/Status")
        status = data.get("InvoiceStatus", {}) if isinstance(data.get("InvoiceStatus"), dict) else {}
        return {
            "status": str(status.get("Code") or data.get("StatusCode") or data.get("Status") or ""),
            "answer_status": str(data.get("AnswerStatus") or data.get("Answer") or ""),
            "answer_note": str(data.get("AnswerNote") or status.get("Description") or ""),
        }

    def send_answer(self, doc_uuid, answer, reason=""):
        answer = self.normalize_answer(answer)
        payload = {"UUID": doc_uuid, "Status": answer}
        if reason:
            payload["Reason"] = reason
        with self._client() as client:
            response = client.request("POST", "/einvoice/Purchase/SendAnswer", json=payload, handle_response=False)
        if response.status_code == 409:
            _logger.info("Nilvera: %s zaten yanıtlanmış.", doc_uuid)
            return {"already_answered": True, "detail": response.text[:500]}
        if response.status_code >= 500:
            raise EDonusumRetryableError("Nilvera sunucu hatası, yanıt iletilemedi.", response.status_code)
        if response.status_code >= 400:
            raise EDonusumError(f"Nilvera uygulama yanıtı reddedildi [{response.status_code}].",
                                response.status_code, response.text[:500])
        return {"already_answered": False}

    def get_document_xml(self, doc_uuid):
        with self._client() as client:
            response = client.request("GET", f"/einvoice/Purchase/{doc_uuid}/xml", handle_response=False)
        if response.status_code != 200:
            raise EDonusumError(f"Nilvera XML indirilemedi [{response.status_code}].", response.status_code)
        return response.content

    def get_document_pdf(self, doc_uuid):
        with self._client() as client:
            response = client.request("GET", f"/einvoice/Purchase/{doc_uuid}/pdf", handle_response=False)
        if response.status_code != 200:
            raise EDonusumError(f"Nilvera PDF indirilemedi [{response.status_code}].", response.status_code)
        return response.content
