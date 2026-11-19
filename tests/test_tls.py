import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from lambda_cli.tls import https_context
from lambda_cli.image_generation import References

class PortableTLSTests(unittest.TestCase):
    def test_trusted_roots_survive_missing_build_machine_certificate_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ,SSL_CERT_FILE=str(Path(directory)/'missing.pem'),SSL_CERT_DIR=directory):
                https_context.cache_clear();context=https_context()
                self.assertGreater(len(context.get_ca_certs()),100)
                self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
                self.assertTrue(context.check_hostname)
        https_context.cache_clear()

    def test_certificate_failure_is_not_reported_as_an_unknown_subject(self):
        def fetch(*args):raise URLError(ssl.SSLCertVerificationError('missing trusted certificate'))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'secure connection'):
                References(directory,fetch).search('human','subject',None)

if __name__=='__main__':unittest.main()
