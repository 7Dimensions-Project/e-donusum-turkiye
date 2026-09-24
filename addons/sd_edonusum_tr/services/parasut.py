"""Paraşüt sağlayıcısı (API v4, OAuth2).

Nilvera'dan iki temel farkı vardır:

* Kimlik doğrulama OAuth2 ``password`` akışıdır ve erişim jetonu ~2 saat geçerlidir.
  Jeton, sağlayıcı örneğinde değil **backend kaydında** saklanır
  (``sd.edonusum.backend.parasut_access_token``), böylece her cron turunda yeniden
  oturum açılmaz. Süresi dolmadan yenilenir; ``refresh_token`` varsa o kullanılır.
* Gövde biçimi JSON:API'dir (``application/vnd.api+json``): veriler
  ``data[].attributes`` altında gelir.

Paraşüt gelen e-faturalara GİB uygulama yanıtı vermeyi ``e_invoice_inboxes``
kaynağı üzerinden yapar; belgenin Paraşüt tarafındaki ``id``'si UUID ile birlikte
``raw`` içinde taşınır.
"""

import logging
import time

import requests

from .base import EDonusumError, EDonusumProvider, EDonusumRetryableError, InboundDocument, register

_logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.parasut.com/oauth/token"
API_ROOT = "https://api.parasut.com/v4"


@register
class ParasutProvider(EDonusumProvider):
    name = "parasut"

    def __init__(self, backend):
        super().__init__(backend)
        if not backend.parasut_company_id:
            raise EDonusumError("Paraşüt Firma ID tanımlı değil.")
        self.base_url = f"{API_ROOT}/{backend.parasut_company_id}"

    # -- Kimlik doğrulama -------------------------------------------------

    def _token(self) -> str:
        backend = self.backend.sudo()  # sudo: kimlik bilgileri yalnız sistem yöneticisinde okunabilir
        now = time.time()
        if backend.parasut_access_token and backend.parasut_token_expiry and backend.parasut_token_expiry > now + 60:
            return backend.parasut_access_token

        if backend.parasut_refresh_token:
            payload = {
                "client_id": backend.parasut_client_id,
                "client_secret": backend.parasut_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": backend.parasut_refresh_token,
            }
        else:
            missing = [label for label, value in (
                ("Client ID", backend.parasut_client_id),
                ("Client Secret", backend.parasut_client_secret),
                ("Kullanıcı adı", backend.parasut_username),
                ("Şifre", backend.parasut_password),
            ) if not value]
            if missing:
                raise EDonusumError("Paraşüt kimlik bilgileri eksik: " + ", ".join(missing))
            payload = {
                "client_id": backend.parasut_client_id,
                "client_secret": backend.parasut_client_secret,
                "username": backend.parasut_username,
                "password": backend.parasut_password,
                "grant_type": "password",
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            }

        try:
            response = requests.post(TOKEN_URL, data=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EDonusumRetryableError(f"Paraşüt bağlantı hatası: {exc}") from exc

        if response.status_code >= 500:
            raise EDonusumRetryableError("Paraşüt yetkilendirme servisi yanıt vermiyor.", response.status_code)
        if response.status_code != 200:
            # Yenileme jetonu geçersizse bir kez parola akışına düş.
            if backend.parasut_refresh_token:
                backend.write({"parasut_refresh_token": False, "parasut_access_token": False})
                return self._token()
            raise EDonusumError(f"Paraşüt yetkilendirme hatası [{response.status_code}].",
                                response.status_code, response.text[:500])

        data = response.json()
        backend.write({
            "parasut_access_token": data.get("access_token"),
            "parasut_refresh_token": data.get("refresh_token") or backend.parasut_refresh_token,
            "parasut_token_expiry": now + float(data.get("expires_in") or 7200),
        })
        return data["access_token"]

    def _request(self, method, endpoint, params=None, json=None):
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        }
        try:
            response = requests.request(method, f"{self.base_url}{endpoint}", headers=headers,
                                        params=params, json=json, timeout=self.timeout)
        except requests.RequestException as exc:
            raise EDonusumRetryableError(f"Paraşüt bağlantı hatası: {exc}") from exc

        _logger.info('"%s %s" %s', method, endpoint, response.status_code)
        if response.status_code in (429,) or response.status_code >= 500:
            raise EDonusumRetryableError(f"Paraşüt geçici hata [{response.status_code}].", response.status_code)
        if response.status_code >= 400:
            raise EDonusumError(f"Paraşüt API hatası [{response.status_code}].",
                                response.status_code, response.text[:500])
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # -- Sözleşme ---------------------------------------------------------

    def test_connection(self) -> str:
        self._request("GET", "/contacts", params={"page[size]": 1})
        return "Paraşüt API v4 bağlantısı doğrulandı."

    def list_inbound(self, date_start, date_end, page=1, page_size=50):
        data = self._request("GET", "/e_invoice_inboxes", params={
            "page[number]": page,
            "page[size]": page_size,
            "filter[issue_date]": f"{date_start},{date_end}",
        })
        documents = []
        for item in data.get("data", []):
            attributes = item.get("attributes", {}) or {}
            doc_uuid = attributes.get("uuid") or attributes.get("ettn") or ""
            if not doc_uuid:
                continue
            documents.append(InboundDocument(
                uuid=doc_uuid,
                number=attributes.get("invoice_number") or attributes.get("number") or "",
                issue_date=(attributes.get("issue_date") or "")[:10],
                supplier_vkn=attributes.get("vkn") or attributes.get("tax_number") or "",
                profile=(attributes.get("scenario") or attributes.get("profile") or "").upper(),
                status=attributes.get("status") or "",
                answer_status=attributes.get("response_type") or attributes.get("answer_status") or "",
                raw={"id": item.get("id"), **attributes},
            ))
        return documents

    def get_status(self, doc_uuid):
        data = self._request("GET", "/e_invoice_inboxes", params={"filter[uuid]": doc_uuid, "page[size]": 1})
        rows = data.get("data") or []
        if not rows:
            return {"status": "", "answer_status": "", "answer_note": ""}
        attributes = rows[0].get("attributes", {}) or {}
        return {
            "status": str(attributes.get("status") or ""),
            "answer_status": str(attributes.get("response_type") or attributes.get("answer_status") or ""),
            "answer_note": str(attributes.get("response_note") or attributes.get("note") or ""),
        }

    def send_answer(self, doc_uuid, answer, reason=""):
        answer = self.normalize_answer(answer)
        data = self._request("GET", "/e_invoice_inboxes", params={"filter[uuid]": doc_uuid, "page[size]": 1})
        rows = data.get("data") or []
        if not rows:
            raise EDonusumError(f"Paraşüt'te {doc_uuid} numaralı gelen belge bulunamadı.")
        inbox_id = rows[0].get("id")
        attributes = rows[0].get("attributes", {}) or {}
        if attributes.get("response_type"):
            return {"already_answered": True, "detail": attributes.get("response_type")}

        payload = {
            "data": {
                "type": "e_invoice_inboxes",
                "id": str(inbox_id),
                "attributes": {
                    "response_type": "accepted" if answer == "KABUL" else "rejected",
                    "response_note": reason or "",
                },
            }
        }
        self._request("PATCH", f"/e_invoice_inboxes/{inbox_id}", json=payload)
        return {"already_answered": False}
