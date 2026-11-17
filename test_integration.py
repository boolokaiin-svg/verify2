"""Adapter contract tests; no AI calls or real documents leave this process."""
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class IntegrationTest(unittest.TestCase):
    def test_backend_contract(self):
        with tempfile.TemporaryDirectory() as storage:
            fake = types.ModuleType('verify_service')
            fake.PropertyVerificationAgent = object

            def verify(document, **kwargs):
                self.assertEqual(document, b'fixture')
                Path('output/ec.pdf').write_bytes(b'%PDF-fixture')
                return {'success': True, 'verdict': 'WARNING', 'data': {'confidence': 75},
                        'downloaded_files': {'ec': 'output/ec.pdf'}}

            fake.verify_property_document = verify
            with patch.dict(os.environ, VERIFICATION_SERVICE_TOKEN='test-secret',
                            OPENROUTER_API_KEY='fixture', VERIFICATION_STORAGE_DIR=storage), \
                    patch.dict(sys.modules, verify_service=fake):
                spec = importlib.util.spec_from_file_location('adapter_test', Path(__file__).with_name('app.py'))
                adapter = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(adapter)
                client = TestClient(adapter.app)
                self.assertEqual(client.get('/health').status_code, 200)
                self.assertEqual(client.get('/api/internal/readiness').status_code, 401)
                headers = {'Authorization': 'Bearer test-secret', 'X-Boolok-User-Id': 'a' * 24}
                self.assertTrue(client.get('/api/internal/readiness', headers=headers).json()['ready'])
                response = client.post('/api/verify', headers=headers,
                                       files={'document': ('deed.pdf', b'fixture', 'application/pdf')})
                self.assertEqual(response.status_code, 200, response.text)
                filename = response.json()['downloaded_files']['ec']
                url = '/api/download-ec/' + filename
                self.assertEqual(client.get(url, headers=headers).content, b'%PDF-fixture')
                other = dict(headers, **{'X-Boolok-User-Id': 'b' * 24})
                self.assertEqual(client.get(url, headers=other).status_code, 404)
                self.assertTrue(client.post('/api/internal/delete-account/' + 'a' * 24,
                                            headers=headers).json()['success'])
                self.assertEqual(client.get(url, headers=headers).status_code, 404)


if __name__ == '__main__':
    unittest.main()
