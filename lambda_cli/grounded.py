"""One owner-trained model with learned search routing and evidence adapters."""
import numpy as np
import math
from time import perf_counter
from .pointer import PointerEngine,softmax
from .transformer import GROUNDED_FORMAT,norm
from .intent import IntentRouter

class GroundedEngine(PointerEngine):
    supported_format=GROUNDED_FORMAT

    def search_decision(self,question):
        w=self.weights
        features=IntentRouter.features(question,len(w['search_w']))
        probabilities=softmax(features@w['search_w']+w['search_b'])
        return dict(search=bool(probabilities[1]>=.5),probability=float(probabilities[1]))

    def evidence_view(self):
        # A read-only view of the same model's conditional weights. Never mutate
        # the base arrays or switch to external weights or answer code.
        weights={k:v for k,v in self.weights.items() if not k.startswith(('evidence_','search_'))}
        for key in list(weights):
            name='evidence_'+key
            if name+'_a' in self.weights:
                value=weights[key]+self.weights[name+'_a']@self.weights[name+'_b']
                value.flags.writeable=False;weights[key]=value
        bias=weights['pointer_gate_b']+self.weights['evidence_gate_bias'];bias.flags.writeable=False
        weights['pointer_gate_b']=bias
        view=object.__new__(PointerEngine);view.__dict__=dict(self.__dict__);view.weights=weights
        return view

    def generate(self,prompt,settings=None,on_text=None,cancel=None,*,evidence=False,evidence_range=None):
        engine=self.evidence_view() if evidence else self
        if evidence and self.metadata.get('span_reader'):
            return self.read_answer(engine,prompt,settings,on_text,cancel,evidence_range)
        return PointerEngine.generate(engine,prompt,settings,on_text,cancel)

    def read_answer(self,engine,prompt,settings,on_text,cancel,bounds):
        """Decode a span predicted by neural heads, never a keyword answer lookup."""
        from .engine import Settings,Result,GeneratedToken
        from .byte_tokenizer import END
        settings=settings or Settings();settings.validate();prompt=list(prompt);started=perf_counter()
        if not bounds or len(bounds)!=2 or not all(type(i) is int for i in bounds) or not 0<=bounds[0]<bounds[1]<len(prompt):
            raise ValueError('Invalid evidence token bounds.')
        if cancel is not None and cancel.is_set():return Result('',prompt,[],0.,len(prompt),0,'cancelled')
        h,_=engine.hidden_states(prompt)
        w=engine.weights;e=norm(w['token'][prompt],w['pointer_norm_w'],w['pointer_norm_b']);features=np.concatenate((h,e),axis=-1)
        answerability=softmax(h[-1]@self.weights['span_answerable_w']+self.weights['span_answerable_b'])
        if answerability[1]<.5:
            return PointerEngine.generate(engine,prompt,settings,on_text,cancel)
        start=(features[-1]@w['pointer_q'])@(features@w['pointer_k']).T/math.sqrt(w['pointer_q'].shape[-1])
        end=(features[-1]@self.weights['span_end_q'])@(features@self.weights['span_end_k']).T/math.sqrt(self.weights['span_end_q'].shape[-1])
        lo,hi=bounds;s=np.arange(lo,hi)[:,None];t=np.arange(lo+1,hi+1)[None,:]
        joint=start[lo:hi,None]+end[None,lo+1:hi+1]
        joint=np.where((t>s)&(t-s<=64),joint,-np.inf);a,b=np.unravel_index(int(np.argmax(joint)),joint.shape)
        output=prompt[lo+a:lo+1+b];reason='stop'
        if len(output)>=settings.max_tokens:output=output[:settings.max_tokens];reason='limit'
        if cancel is not None and cancel.is_set():return Result('',prompt,[],perf_counter()-started,len(prompt),0,'cancelled')
        generated=[GeneratedToken(i,self.tokenizer.tokens[i]) for i in output]
        if reason=='stop':generated.append(GeneratedToken(END,self.tokenizer.tokens[END]))
        text=self.tokenizer.decode(output).strip()
        if on_text:on_text(text,len(generated))
        return Result(text,prompt,generated,perf_counter()-started,len(prompt),0,reason)

    def info(self):
        result=super().info();result['architecture']+=' · learned search + evidence adapters'
        result['router_parameters']=self.weights['search_w'].size+2
        result['generator_parameters']=self.parameter_count-result['router_parameters']
        result['automatic_search']=self.metadata.get('model_id')=='lambda-2.5.1'
        return result
