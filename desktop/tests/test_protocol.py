"""The desktop JSON wire format must not depend on the host's code page."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ProtocolTests(unittest.TestCase):
    def test_utf8_requests_and_responses_with_legacy_pipe_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, LAMBDA_DATA_HOME=folder,
                       PYTHONUTF8='1', PYTHONIOENCODING='cp1252')
            request = dict(id=1, method='preferences', params=dict(
                values=dict(displayName='Łukasz 東京')))
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1]/'backend.py')],
                input=(json.dumps(request, ensure_ascii=False)+'\n').encode('utf-8'),
                capture_output=True, env=env, timeout=30, check=True)
            messages = [json.loads(line) for line in result.stdout.decode('utf-8').splitlines()]
            response = next(row for row in messages if row.get('id') == 1)
            self.assertNotIn('error', response)
            self.assertEqual(response['result']['preferences']['displayName'], 'Łukasz 東京')
