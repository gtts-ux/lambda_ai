"""Online reference photos, own local neural pixels. No hosted image AI or Torch."""
import re
import numpy as np
from PIL import Image,ImageOps
from .image_references import References
from .image_network import OrionNetwork,prompt_ids,resize


def cancelled(cancel):
    if cancel is not None and cancel.is_set():raise ValueError('Image generation cancelled.')

def plan(prompt):
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=500:raise ValueError('Use an image description of 1–500 characters.')
    position='left' if re.search(r'\b(?:on|to|at) (?:the )?left\b',prompt,re.I) else 'right' if re.search(r'\b(?:on|to|at) (?:the )?right\b',prompt,re.I) else 'center'
    text=re.sub(r',?\s*(?:on|to|at) (?:the )?(?:left|right)\b','',prompt,flags=re.I).strip().rstrip('.!?')
    text=re.sub(r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:generate|create|make|draw|render|produce)\s+(?:me\s+)?(?:(?:a|an)\s+)?(?:(?:photo|photograph|picture|image|illustration|artwork)\s*(?:of|showing|featuring)?\s*[, :]?\s*)?','',text,flags=re.I)
    text=re.sub(r'^(?:prosze\s+)?(?:wygeneruj|narysuj|stworz|zrob)\s+(?:mi\s+)?(?:(?:obraz|zdjecie|zdjęcie|ilustracje)\s*)?[:, ]*','',text,flags=re.I)
    pieces=re.split(r'\s+(?:in|against|with|above|on|beside)\s+(?:a\s+|an\s+|the\s+)?',text,maxsplit=1,flags=re.I)
    queries=[re.sub(r'^(?:a|an|the)\s+','',p.strip(),flags=re.I) for p in pieces]
    if not all(queries):raise ValueError('Describe a subject and an optional setting.')
    return dict(prompt=prompt,queries=queries,position=position,
        search_queries=[('star field' if i and q.lower() in {'space','outer space'} else q) for i,q in enumerate(queries)])


def tensor(path):
    with Image.open(path) as im:im=ImageOps.pad(im.convert('RGB'),(256,256),method=Image.Resampling.LANCZOS,color=(128,128,128))
    return np.asarray(im,dtype=np.float32).transpose(2,0,1)/np.float32(127.5)-1

class ImageGenerator:
    def __init__(self,model_path,cache,fetcher=None):
        self.model=OrionNetwork(model_path);self.references=References(cache,fetcher)
    def generate(self,prompt,seed=42,progress=lambda phase,percent:None,cancel=None):
        request=plan(prompt);groups=[]
        for i,query in enumerate(request['search_queries']):
            role='subject' if not i else 'background';progress('Searching '+role+' references',5+i*5)
            groups.append(self.references.search(query,role,cancel))
        cancelled(cancel);progress('Selecting references',15);ranked=[]
        for row in groups[0]:
            cancelled(cancel);im=tensor(row['path'])[None]
            logits=self.model.mask(im,prompt_ids([request['queries'][0]]));matte=1/(1+np.exp(np.clip(-logits,-80,80)))
            area=float((matte>.5).mean());certainty=float(np.abs(matte-.5).mean())
            border=float(np.concatenate([matte[:,:,0,:],matte[:,:,-1,:],matte[:,:,:,0],matte[:,:,:,-1]],-1).mean())
            score=row['relevance']+2*certainty-8*border-10*float(area<.03 or area>.9)
            ranked.append((score,row,im,matte))
        _,subject,im,matte=max(ranked,key=lambda item:item[0]);ys,xs=np.where(matte[0,0]>.5)
        if len(xs)>20:
            x0,x1=max(0,int(xs.min())-12),min(256,int(xs.max())+13);y0,y1=max(0,int(ys.min())-12),min(256,int(ys.max())+13)
            crop=im[:,:,y0:y1,x0:x1];side=max(crop.shape[-2:]);dy=side-crop.shape[-2];dx=side-crop.shape[-1]
            im=resize(np.pad(crop,((0,0),(0,0),(dy//2,dy-dy//2),(dx//2,dx-dx//2))),256)
            logits=self.model.mask(im,prompt_ids([request['queries'][0]]));matte=1/(1+np.exp(np.clip(-logits,-80,80)))
        background=groups[1][0] if len(groups)>1 else None
        bg=tensor(background['path'])[None] if background else np.zeros_like(im)
        refs=np.stack([im,bg],1);low=resize(refs.reshape(2,3,256,256),64).reshape(1,2,3,64,64)
        caption=f"{request['queries'][0]} in {request['queries'][1] if background else 'plain background'}, {request['position']}"
        coarse=self.model.sample(low,resize(matte,64),caption,seed=seed,progress=progress,cancel=cancel)
        cancelled(cancel);progress('Rendering 256 × 256',85)
        pixels=self.model.detail(coarse,refs,matte)[0]
        cancelled(cancel);progress('Saving image',98)
        pixels=np.rint((pixels.clip(-1,1)+1)*np.float32(127.5)).astype(np.uint8).transpose(1,2,0)
        public=lambda row:{key:row.get(key) for key in ['title','source_url','credit','license','provider','sha256']}
        return pixels,dict(model='orion-image-1',modelName='orion image 1',width=256,height=256,safeSearch='strict',referenceSearch='DuckDuckGo',
            references=[public(row) for group in groups for row in group],selectedReferences=[public(subject)]+([public(background)] if background else []))
