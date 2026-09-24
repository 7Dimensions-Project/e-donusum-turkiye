"""E-Dönüşüm entegratörleri için ortak arayüz.

Odoo çekirdeği (``l10n_tr_nilvera_einvoice``) yalnızca Nilvera ile konuşur ve GİB
uygulama yanıtı (KABUL / RED) göndermez. Bu paket, çekirdeğin akışını bozmadan
entegratörden bağımsız bir yüzey sunar: her sağlayıcı aynı sözleşmeyi uygular,
çağıran taraf (``account.move``, cron'lar) sağlayıcıyı bilmez.

Sağlayıcılar Odoo ORM'ine bağımlı değildir; yalnızca ``backend`` kaydından okunan
saf değerlerle çalışırlar, böylece ağ katmanı testlerde kolayca mock'lanır.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class EDonusumError(Exception):
    """Entegratör çağrılarında oluşan, kullanıcıya gösterilebilir hata."""

    def __init__(self, message: str, status_code: int | None = None, payload: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class EDonusumRetryableError(EDonusumError):
    """Geçici hata (ağ, 429, 5xx) — cron bir sonraki turda yeniden dener."""


@dataclass
class InboundDocument:
    """Entegratörden bağımsız gelen belge özeti."""

    uuid: str
    number: str = ""
    issue_date: str = ""
    supplier_vkn: str = ""
    profile: str = ""
    status: str = ""
    answer_status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


ANSWER_ACCEPT = "KABUL"
ANSWER_REJECT = "RED"


class EDonusumProvider(ABC):
    """Tüm entegratörlerin uyduğu sözleşme.

    Uygulayan sınıflar ``name`` sınıf niteliğini doldurur ve yalnızca
    ``__init__(self, backend)`` imzasını kullanır; ``backend`` bir
    ``sd.edonusum.backend`` kaydıdır (tek kayıt).
    """

    name = "base"
    #: Bu sağlayıcı GİB uygulama yanıtı gönderebiliyor mu?
    supports_answer = True

    def __init__(self, backend):
        backend.ensure_one()
        self.backend = backend
        self.company = backend.company_id
        self.timeout = backend.timeout or 30

    # -- Sözleşme ---------------------------------------------------------

    @abstractmethod
    def test_connection(self) -> str:
        """Kimlik bilgilerini doğrular; kullanıcıya gösterilecek kısa mesaj döner."""

    @abstractmethod
    def list_inbound(self, date_start: str, date_end: str, page: int = 1, page_size: int = 50) -> list[InboundDocument]:
        """Verilen aralıktaki gelen belgeleri döner. Sayfa boşsa boş liste."""

    @abstractmethod
    def get_status(self, doc_uuid: str) -> dict[str, str]:
        """``{'status': ..., 'answer_status': 'KABUL'|'RED'|'', 'answer_note': ...}``"""

    @abstractmethod
    def send_answer(self, doc_uuid: str, answer: str, reason: str = "") -> dict[str, Any]:
        """GİB uygulama yanıtı gönderir. ``answer`` = ``KABUL`` | ``RED``.

        Zaten yanıtlanmış belgelerde istisna fırlatmaz; ``{'already_answered': True}`` döner.
        """

    # -- İsteğe bağlı -----------------------------------------------------

    def get_document_xml(self, doc_uuid: str) -> bytes:
        raise EDonusumError(f"{self.name}: XML indirme desteklenmiyor.")

    def get_document_pdf(self, doc_uuid: str) -> bytes:
        raise EDonusumError(f"{self.name}: PDF indirme desteklenmiyor.")

    # -- Yardımcılar ------------------------------------------------------

    @staticmethod
    def normalize_answer(answer: str) -> str:
        value = (answer or "").strip().upper()
        if value not in (ANSWER_ACCEPT, ANSWER_REJECT):
            raise EDonusumError(f"Geçersiz uygulama yanıtı: {answer!r} (KABUL veya RED olmalı)")
        return value

    @staticmethod
    def classify_answer(status_text: str, answer_text: str) -> str:
        """Entegratörden gelen serbest metni ortak duruma indirger."""
        blob = f"{status_text or ''} {answer_text or ''}".upper()
        if "RED" in blob or "REJECT" in blob:
            return "rejected"
        if "KABUL" in blob or "ONAY" in blob or "ACCEPT" in blob or "APPROVE" in blob:
            return "accepted"
        if "IPTAL" in blob or "İPTAL" in blob or "CANCEL" in blob:
            return "cancelled"
        return ""


_PROVIDERS: dict[str, type[EDonusumProvider]] = {}


def register(cls: type[EDonusumProvider]) -> type[EDonusumProvider]:
    """Sağlayıcı sınıfını kayıt defterine ekler (modül import edilirken çalışır)."""
    _PROVIDERS[cls.name] = cls
    return cls


def get_provider(backend) -> EDonusumProvider:
    """``backend.provider`` değerine karşılık gelen sağlayıcıyı örnekler."""
    provider_cls = _PROVIDERS.get(backend.provider)
    if provider_cls is None:
        raise EDonusumError(f"Tanımsız entegratör: {backend.provider}")
    return provider_cls(backend)


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)
