"""Inference for the learned chat/calculation classifier; no arithmetic evaluator."""
from dataclasses import dataclass
import hashlib
import re

import numpy as np


@dataclass(frozen=True)
class Intent:
    name: str
    index: int
    math_probability: float

    def to_dict(self):
        return {"intent":self.name,"math_probability":self.math_probability}


class IntentRouter:
    def __init__(self, weights, bias, threshold=0.65):
        self.weights=np.asarray(weights,dtype=np.float32)
        self.bias=np.asarray(bias,dtype=np.float32)
        if self.weights.ndim!=2 or self.weights.shape[0]<1 or self.weights.shape[1]!=2 or self.bias.shape!=(2,):
            raise ValueError('Invalid intent classifier dimensions.')
        if not np.isfinite(self.weights).all() or not np.isfinite(self.bias).all():
            raise ValueError('Invalid intent classifier weights.')
        if not 0<threshold<1:
            raise ValueError('Invalid intent threshold.')
        self.threshold=threshold
        self.weights.flags.writeable=False
        self.bias.flags.writeable=False

    @staticmethod
    def features(text, size):
        # Numbers are abstracted for generalization; the learned weights decide
        # whether the surrounding request calls for calculation or conversation.
        text=re.sub(r'\d+(?:\.\d+)?','#',text.lower().replace('’',"'"))
        words=re.findall(r"[a-z]+(?:'[a-z]+)?|#|[+*/=×÷-]",text)
        signals=['w:'+w for w in words]
        signals += ['b:'+a+' '+b for a,b in zip(words,words[1:])]
        compact=' '.join(words)
        for width in (3,4):
            signals += [f'c{width}:'+compact[i:i+width] for i in range(max(0,len(compact)-width+1))]
        vector=np.zeros(size,dtype=np.float32)
        for signal in signals:
            digest=hashlib.blake2b(signal.encode('utf-8'),digest_size=8).digest()
            number=int.from_bytes(digest,'little')
            vector[number%size] += 1.0 if number&(1<<63) else -1.0
        norm=float(np.linalg.norm(vector))
        if norm:
            vector/=norm
        return vector

    def predict(self, text):
        logits=self.features(text,len(self.weights))@self.weights+self.bias
        probabilities=np.exp(logits-logits.max())
        probabilities/=probabilities.sum()
        p=float(probabilities[1])
        index=int(p>=self.threshold)
        return Intent('math' if index else 'chat',index,p)
