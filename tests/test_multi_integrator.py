# -*- coding: utf-8 -*-
"""
Unit tests for Multi-Integrator Factory and Adapters.
"""

import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'addons', 'e_donusum_turkiye')))
from tools.integrators import get_integrator, NilveraIntegrator, ParasutIntegrator, UyumsoftIntegrator

class DummyCompany:
    def __init__(self, provider, **kwargs):
        self.edonusum_provider = provider
        for k, v in kwargs.items():
            setattr(self, k, v)

class TestMultiIntegrator(unittest.TestCase):
    def test_factory_nilvera(self):
        comp = DummyCompany('nilvera', nilvera_api_key='nil_key_123', nilvera_environment='production')
        adapter = get_integrator(comp)
        self.assertIsInstance(adapter, NilveraIntegrator)
        self.assertEqual(adapter.provider_name, "nilvera")
        self.assertEqual(adapter.client.api_key, "nil_key_123")

    def test_factory_parasut(self):
        comp = DummyCompany(
            'parasut',
            parasut_client_id='cid_1',
            parasut_client_secret='csec_1',
            parasut_username='user@test.com',
            parasut_password='pass',
            parasut_company_id='12345'
        )
        adapter = get_integrator(comp)
        self.assertIsInstance(adapter, ParasutIntegrator)
        self.assertEqual(adapter.provider_name, "parasut")
        self.assertEqual(adapter.parasut_company_id, "12345")
        self.assertEqual(adapter.base_url, "https://api.parasut.com/v4/12345")

    def test_factory_uyumsoft(self):
        comp = DummyCompany(
            'uyumsoft',
            uyumsoft_username='uyum_user',
            uyumsoft_password='uyum_pass',
            uyumsoft_environment='test'
        )
        adapter = get_integrator(comp)
        self.assertIsInstance(adapter, UyumsoftIntegrator)
        self.assertEqual(adapter.provider_name, "uyumsoft")
        self.assertEqual(adapter.environment, "test")
        self.assertTrue("test" in adapter.ws_url)

if __name__ == '__main__':
    unittest.main()
