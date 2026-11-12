"""Own frozen conversation base plus learned coding adapters and language routing."""
import numpy as np
from .grounded import GroundedEngine
from .pointer import PointerEngine,softmax
from .transformer import CODE_FORMAT
from .intent import IntentRouter
from .byte_tokenizer import USER,END,ASSISTANT,conversation_prompt


class CodeEngine(GroundedEngine):
    supported_format=CODE_FORMAT

    def classify(self,question):
        p=softmax(IntentRouter.features(question,len(self.weights['search_w']))@self.weights['search_w']+self.weights['search_b'])
        index=int(np.argmax(p))
        return dict(intent=('chat','python','javascript')[index],language=(None,'python','javascript')[index],coding_probability=float(p[1]+p[2]),math_probability=None)

    def search_decision(self,question):
        return dict(search=False,probability=0.)

    def generate(self,prompt,settings=None,on_text=None,cancel=None,**kwargs):
        if isinstance(prompt,str):
            question=prompt[10:-9] if prompt.startswith('Question: ') and prompt.endswith('\nAnswer: ') else prompt
            prompt=conversation_prompt(self.tokenizer,[],question,self.context)
        else:
            prompt=list(prompt)
            start=max((i for i,t in enumerate(prompt) if t==USER),default=-1)+1
            end=next((i for i in range(start,len(prompt)) if prompt[i]==END),len(prompt))
            question=self.tokenizer.decode(prompt[start:end])
        decision=self.classify(question)
        engine=self if decision['intent']=='chat' else self.evidence_view()
        result=PointerEngine.generate(engine,prompt,settings,on_text,cancel)
        result.intent=decision['intent']
        return result

    def info(self):
        result=PointerEngine.info(self)
        result['architecture']+=' · learned Python / JavaScript adapters'
        result['router_parameters']=self.weights['search_w'].size+self.weights['search_b'].size
        result['generator_parameters']=self.parameter_count-result['router_parameters']
        result['automatic_search']=False
        result['coding_languages']=['python','javascript']
        return result
