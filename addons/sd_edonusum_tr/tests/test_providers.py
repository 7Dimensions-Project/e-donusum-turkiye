from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.sd_edonusum_tr.services import get_provider
from odoo.addons.sd_edonusum_tr.services.base import EDonusumError, EDonusumProvider, EDonusumRetryableError


@tagged("post_install", "-at_install")
class TestProviders(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def _backend(self, provider, **values):
        return self.env["sd.edonusum.backend"].create({
            "company_id": self.company.id, "provider": provider, **values,
        })

    def test_factory_returns_matching_provider(self):
        for provider in ("nilvera", "parasut", "uyumsoft"):
            backend = self._backend(provider, parasut_company_id="123")
            self.assertEqual(get_provider(backend).name, provider)
            backend.unlink()

    def test_answer_normalisation(self):
        self.assertEqual(EDonusumProvider.normalize_answer(" kabul "), "KABUL")
        with self.assertRaises(EDonusumError):
            EDonusumProvider.normalize_answer("belki")

    def test_answer_classification(self):
        classify = EDonusumProvider.classify_answer
        self.assertEqual(classify("KABUL EDILDI", ""), "accepted")
        self.assertEqual(classify("", "RED"), "rejected")
        self.assertEqual(classify("IPTAL", ""), "cancelled")
        self.assertEqual(classify("BEKLIYOR", ""), "")

    def test_parasut_requires_company_id(self):
        backend = self._backend("parasut")
        with self.assertRaises(EDonusumError):
            get_provider(backend)

    def test_parasut_caches_token_on_backend(self):
        backend = self._backend("parasut", parasut_company_id="9", parasut_client_id="id",
                                parasut_client_secret="secret", parasut_username="u", parasut_password="p")
        provider = get_provider(backend)
        token_response = MagicMock(status_code=200)
        token_response.json.return_value = {"access_token": "tok", "refresh_token": "ref", "expires_in": 7200}
        with patch("odoo.addons.sd_edonusum_tr.services.parasut.requests.post", return_value=token_response) as post:
            self.assertEqual(provider._token(), "tok")
            self.assertEqual(provider._token(), "tok")  # ikinci çağrı önbellekten
        post.assert_called_once()
        self.assertEqual(backend.sudo().parasut_refresh_token, "ref")

    def test_parasut_server_error_is_retryable(self):
        backend = self._backend("parasut", parasut_company_id="9", parasut_client_id="id",
                                parasut_client_secret="secret", parasut_username="u", parasut_password="p")
        provider = get_provider(backend)
        with patch("odoo.addons.sd_edonusum_tr.services.parasut.requests.post",
                   return_value=MagicMock(status_code=503, text="down")):
            with self.assertRaises(EDonusumRetryableError):
                provider._token()

    def test_uyumsoft_envelope_escapes_credentials(self):
        backend = self._backend("uyumsoft", uyumsoft_username="a&b", uyumsoft_password="p<w")
        envelope = get_provider(backend)._envelope("IsEInvoiceUser", "<vknTckn>1</vknTckn>").decode()
        self.assertIn("a&amp;b", envelope)
        self.assertIn("p&lt;w", envelope)
        self.assertNotIn("<Username>a&b<", envelope)

    def test_uyumsoft_soap_fault_raises(self):
        backend = self._backend("uyumsoft", uyumsoft_username="u", uyumsoft_password="p")
        fault = (
            '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body><s:Fault><faultstring>Yetkisiz</faultstring></s:Fault></s:Body></s:Envelope>"
        ).encode()
        with patch("odoo.addons.sd_edonusum_tr.services.uyumsoft.requests.post",
                   return_value=MagicMock(status_code=200, content=fault)):
            with self.assertRaises(EDonusumError):
                get_provider(backend).test_connection()

    def test_nilvera_without_api_key_raises(self):
        self.company.sudo().l10n_tr_nilvera_api_key = False
        backend = self._backend("nilvera")
        with self.assertRaises(EDonusumError):
            get_provider(backend).test_connection()
