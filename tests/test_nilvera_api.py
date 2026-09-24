# -*- coding: utf-8 -*-
"""
Unit tests for NilveraClient initialization and headers.
"""

import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'addons', 'e_donusum_turkiye')))
from tools.nilvera_client import NilveraClient

class TestNilveraClient(unittest.TestCase):
    def test_client_init_production(self):
        client = NilveraClient(api_key="test_api_key_123", environment="production")
        self.assertEqual(client.base_url, "https://api.nilvera.com")
        headers = client._get_headers()
        self.assertEqual(headers["Authorization"], "Bearer test_api_key_123")
        self.assertEqual(headers["Accept"], "application/json")

    def test_client_init_test(self):
        client = NilveraClient(api_key="test_api_key_456", environment="test")
        self.assertEqual(client.base_url, "https://testapi.nilvera.com")

if __name__ == '__main__':
    unittest.main()
