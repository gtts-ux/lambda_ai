"""Own learned Terra image-tool head. No keyword-based routing decisions."""
import hashlib
import re
import unicodedata
from pathlib import Path
import numpy as np

ASSET=Path(__file__).resolve().parent/'assets/image_intent.npz'

def features(text,size=8192):
    text=unicodedata.normalize('NFKD',text.casefold().replace('ł','l'))
    text=''.join(c for c in text if not unicodedata.combining(c))
    words=re.findall(r"[\w']+|[^\w\s]",text,flags=re.UNICODE)
    signals=['w:'+w for w in words]+['b:'+a+' '+b for a,b in zip(words,words[1:])]
    signals+=['t:'+a+' '+b+' '+c for a,b,c in zip(words,words[1:],words[2:])]
    compact=' '.join(words)
    for width in (3,4,5):signals += [f'c{width}:'+compact[i:i+width] for i in range(max(0,len(compact)-width+1))]
    vector=np.zeros(size,dtype=np.float32)
    for token in signals:
        number=int.from_bytes(hashlib.blake2b(token.encode(),digest_size=8).digest(),'little')
        vector[number%size]+=1 if number&(1<<63) else -1
    return vector/max(float(np.linalg.norm(vector)),1e-8)

class ImageIntent:
    def __init__(self,path=ASSET):
        with np.load(path,allow_pickle=False) as data:
            self.w1=data['w1'].copy();self.b1=data['b1'].copy();self.w2=data['w2'].copy();self.b2=data['b2'].copy()
            self.threshold=float(data['threshold'])
        if self.w1.shape!=(8192,24) or self.b1.shape!=(24,) or self.w2.shape!=(24,2) or self.b2.shape!=(2,):
            raise ValueError('Invalid image intent head')
        if not all(np.isfinite(x).all() for x in [self.w1,self.b1,self.w2,self.b2]) or not .5<=self.threshold<1:
            raise ValueError('Invalid image intent values')
    def predict(self,text):
        hidden=np.tanh(features(text)@self.w1+self.b1)
        logits=hidden@self.w2+self.b2;p=np.exp(logits-logits.max());p/=p.sum()
        probability=float(p[1])
        return dict(image=probability>=self.threshold,probability=probability,threshold=self.threshold)
