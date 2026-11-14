import contextlib
import io
import unittest
from unittest.mock import patch

from lambda_cli.cli import main
from lambda_cli.desktop_links import DESKTOP_URL


class DesktopLinkTests(unittest.TestCase):
    def test_download_link_does_not_load_or_download_a_model(self):
        output=io.StringIO()
        with patch('lambda_cli.engine.Engine',side_effect=AssertionError('No engine needed')),contextlib.redirect_stdout(output):
            self.assertEqual(main(['desktop']),0)
        text=output.getvalue()
        self.assertIn(DESKTOP_URL,text)
        self.assertIn('macOS, Windows and Linux',text)


if __name__=='__main__':unittest.main()
