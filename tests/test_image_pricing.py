import unittest
from lambda_cli.image_pricing import image_price

class ImagePricingTests(unittest.TestCase):
    def test_owner_examples_and_each_image_multiplier(self):
        prompt='cat in the green park'
        self.assertEqual(image_price(prompt,256)['total'],5000)
        self.assertEqual(image_price(prompt,512)['total'],10000)
        self.assertEqual(image_price(prompt,1024)['total'],20000)
        self.assertEqual(image_price(prompt,512,3)['total'],30000)

    def test_word_boundaries_and_unicode_are_independent_of_chat_tokenizer(self):
        self.assertEqual(image_price('person,face,human')['words'],3)
        self.assertEqual(image_price('Biały kot obok domu.')['words'],4)
        self.assertEqual(image_price("A blue-green bird's nest")['words'],4)
        for kwargs in [dict(size=4096),dict(count=0),dict(count=1.5),dict(count=True)]:
            with self.assertRaises(ValueError):image_price('cat',**kwargs)
        with self.assertRaises(ValueError):image_price('!!!')

if __name__=='__main__':unittest.main()
