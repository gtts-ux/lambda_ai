import unittest
import numpy as np

from lambda_cli.models import validate_catalog
from lambda_cli.transformer import POINTER_FORMAT, weight_shapes


class LargeModelLimitsTests(unittest.TestCase):
    def test_35m_pointer_architecture_fits_bounded_runtime(self):
        c=dict(format=POINTER_FORMAT,width=384,layers=19,heads=6,vocabulary=2048,context=512,pointer_width=256)
        self.assertEqual(sum(int(np.prod(s)) for s in weight_shapes(c).values()),35028097)
        with self.assertRaises(ValueError):weight_shapes(dict(c,layers=25))
        with self.assertRaises(ValueError):weight_shapes(dict(c,width=768,layers=19,heads=12))

    def test_large_download_is_supported_but_still_bounded(self):
        item=dict(id='lambda-terra-4.1',name='lambda terra 4.1',revision=2,
            sha256='a'*64,bytes=140112388,min_app_version='0.8.6',
            url='https://raw.githubusercontent.com/gtts-ux/lambda_ai/main/models/fixture.npz')
        self.assertEqual(validate_catalog(dict(schema=1,models=[item]))['models'][0]['bytes'],140112388)
        with self.assertRaises(ValueError):validate_catalog(dict(schema=1,models=[dict(item,bytes=160*1024*1024+1)]))


if __name__=='__main__':unittest.main()
