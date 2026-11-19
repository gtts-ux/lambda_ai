"""Owner-defined image allowance pricing, independent of chat tokenization."""
import re
import unicodedata

SIZES=(256,512,1024)
MAX_IMAGES=8

def image_price(prompt,size=256,count=1):
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=500:
        raise ValueError('Use an image description of 1–500 characters.')
    if type(size) is not int or size not in SIZES:raise ValueError('Choose 256, 512 or 1024 pixels.')
    if type(count) is not int or not 1<=count<=MAX_IMAGES:raise ValueError('Choose between 1 and 8 images.')
    words=len(re.findall(r"\w+(?:['’\-]\w+)*",unicodedata.normalize('NFKC',prompt)))
    if not words:raise ValueError('Describe your image using at least one word.')
    multiplier=size//256;per_image=words*1000*multiplier
    return dict(words=words,size=size,count=count,multiplier=multiplier,perImage=per_image,total=per_image*count)
