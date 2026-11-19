"""Online reference photos, own local neural pixels. No hosted image AI or Torch."""
import hashlib
import html
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode,urlparse
from urllib.request import Request,urlopen
import numpy as np
from PIL import Image,ImageOps
from .models import atomic_json
from .image_network import OrionNetwork,prompt_ids,resize

HOSTS={'images-api.nasa.gov','images-assets.nasa.gov','commons.wikimedia.org','upload.wikimedia.org','thumb.wikimedia.org'}
BAD=['mockup','mock-up','assembly','production','factory','manufacturing','museum','exhibit','training',
     'conference','portrait','diagram','logo','patch','insignia','blueprint','drawing','painting','tour',
     'projected','projection','monument','illustration','chart','cutaway','montage','close-up','engine',
     'first stage','second stage','instrument unit','welding','ceremony','wreath','gala','audience','speaker']

def cancelled(cancel):
    if cancel is not None and cancel.is_set():raise ValueError('Image generation cancelled.')

def plan(prompt):
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=500:raise ValueError('Use an image description of 1–500 characters.')
    position='left' if re.search(r'\b(?:on|to|at) (?:the )?left\b',prompt,re.I) else 'right' if re.search(r'\b(?:on|to|at) (?:the )?right\b',prompt,re.I) else 'center'
    text=re.sub(r',?\s*(?:on|to|at) (?:the )?(?:left|right)\b','',prompt,flags=re.I).strip().rstrip('.!?')
    text=re.sub(r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:generate|create|make|draw|render|produce)\s+(?:me\s+)?(?:(?:a|an)\s+)?(?:(?:photo|photograph|picture|image|illustration|artwork)\s*(?:of|showing|featuring)?\s*[, :]?\s*)?','',text,flags=re.I)
    text=re.sub(r'^(?:prosze\s+)?(?:wygeneruj|narysuj|stworz|zrob)\s+(?:mi\s+)?(?:(?:obraz|zdjecie|zdjęcie|ilustracje)\s*)?[:, ]*','',text,flags=re.I)
    pieces=re.split(r'\s+(?:in|against|with|above|on|beside)\s+(?:a\s+|an\s+|the\s+)?',text,maxsplit=2,flags=re.I)
    queries=[re.sub(r'^(?:a|an|the)\s+','',p.strip(),flags=re.I) for p in pieces]
    if not all(queries) or len(queries)>2:raise ValueError('Start with one subject and one background, such as “a cat in a forest”.')
    return dict(prompt=prompt,queries=queries,position=position,
        search_queries=[('star field' if i and q.lower() in {'space','outer space'} else q) for i,q in enumerate(queries)])

class References:
    def __init__(self,directory,fetcher=None):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.fetcher=fetcher or self.fetch
    @staticmethod
    def fetch(url,cancel=None):
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
            raise ValueError('Unsupported image reference host')
        cancelled(cancel)
        request=Request(url,headers={'User-Agent':'LambdaAI/0.9.0 (local image playground)'})
        with urlopen(request,timeout=15) as response:
            final=urlparse(response.geturl())
            if final.scheme!='https' or final.hostname not in HOSTS:raise ValueError('Unsupported reference redirect')
            chunks=[];total=0
            while True:
                cancelled(cancel);part=response.read(65536)
                if not part:break
                total+=len(part)
                if total>8_000_000:raise ValueError('Image reference is too large')
                chunks.append(part)
        return b''.join(chunks)
    def json(self,url,cancel):
        key=hashlib.sha256(url.encode()).hexdigest();path=self.directory/(key+'.json')
        if path.exists():return json.loads(path.read_text())
        value=json.loads(self.fetcher(url,cancel));atomic_json(path,value);return value
    @staticmethod
    def relevance(row,query,role):
        title=row.get('title','').lower();description=row.get('description','').lower();text=title+' '+description
        words=re.findall('[a-z0-9]+',query.lower())
        if not words or not all(re.search(r'\b'+re.escape(w)+r'\b',text) for w in words):return -1000
        score=8*int(query.lower() in title)+sum(3*bool(re.search(r'\b'+re.escape(w)+r'\b',title)) for w in words)
        bad=[w for w in BAD if w not in query.lower()]
        score-=sum(14 for w in bad if w in title)+sum(3 for w in bad if w in description)
        if role=='background':score+=sum(4 for w in ['star field','nebula','galaxy','stars','star cluster','deep space'] if w in title)
        else:
            score+=sum(2 for w in ['liftoff','lift-off','launch','flight','full view','standing','orbit'] if w in title)
            score+=sum(3 for w in ['liftoff','lift-off','launch pad','launchpad','in flight','rocket launch','test flight'] if w in description)
        return score
    def search(self,query,role,cancel):
        rows=[];errors=[];deadline=time.monotonic()+60
        try:
            # Title search avoids a page full of unrelated events whose long
            # descriptions mention the requested subject in passing.
            raw=self.json('https://images-api.nasa.gov/search?'+urlencode(dict(title=query,media_type='image',page_size=100)),cancel)
            if not raw.get('collection',{}).get('items'):
                raw=self.json('https://images-api.nasa.gov/search?'+urlencode(dict(q=query,media_type='image',page_size=100)),cancel)
            for item in raw.get('collection',{}).get('items',[]):
                meta=(item.get('data') or [{}])[0]
                links=[x for x in item.get('links',[]) if x.get('render')=='image' and urlparse(x.get('href','')).hostname=='images-assets.nasa.gov']
                if not links or not meta.get('nasa_id'):continue
                link=min(links,key=lambda x:abs((x.get('width') or 640)-640))
                rows.append(dict(id='nasa:'+meta['nasa_id'],title=meta.get('title',''),description=meta.get('description','')[:3000],
                    image_url=link['href'],source_url='https://images.nasa.gov/details/'+meta['nasa_id'],
                    credit=meta.get('photographer') or meta.get('center','NASA'),provider='NASA'))
        except (OSError,ValueError) as exc:errors.append(str(exc))
        ranked=[dict(r,relevance=self.relevance(r,query,role)) for r in rows]
        ranked=[r for r in ranked if r['relevance']>-5]
        if len(ranked)<5:
            try:
                raw=self.json('https://commons.wikimedia.org/w/api.php?'+urlencode(dict(action='query',format='json',generator='search',gsrnamespace=6,gsrsearch=query,gsrlimit=20,prop='imageinfo',iiprop='url|extmetadata',iiurlwidth=512)),cancel)
                for page in raw.get('query',{}).get('pages',{}).values():
                    info=(page.get('imageinfo') or [{}])[0];meta=info.get('extmetadata',{});url=info.get('thumburl',info.get('url',''))
                    if urlparse(url).hostname not in HOSTS or not re.search(r'\.(jpg|jpeg|png)(?:$|\?)',url,re.I):continue
                    clean=lambda name:html.unescape(re.sub('<[^>]+>','',meta.get(name,{}).get('value','')))
                    row=dict(id='commons:'+str(page['pageid']),title=page['title'].removeprefix('File:'),description=clean('ImageDescription')[:3000],
                        image_url=url,source_url=info.get('descriptionurl'),credit=clean('Artist'),license=clean('LicenseShortName'),provider='Wikimedia Commons')
                    row['relevance']=self.relevance(row,query,role)
                    if row['relevance']>-5:ranked.append(row)
            except (OSError,ValueError) as exc:errors.append(str(exc))
        ranked.sort(key=lambda r:r['relevance'],reverse=True)
        result=[];seen=set()
        for row in ranked[:30]:
            cancelled(cancel)
            if time.monotonic()>deadline:break
            key=hashlib.sha256(row['id'].encode()).hexdigest();path=self.directory/(key+'.png')
            try:
                if not path.exists():
                    with Image.open(io.BytesIO(self.fetcher(row['image_url'],cancel))) as original:
                        if original.width*original.height>16_000_000 or min(original.size)<64:continue
                        im=ImageOps.exif_transpose(original).convert('RGB');im.thumbnail((512,512));im.save(path)
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                if digest in seen:continue
                result.append(dict(row,path=str(path),sha256=digest));seen.add(digest)
            except (OSError,ValueError) as exc:errors.append(str(exc))
            if len(result)>=10:break
        if not result:
            cancelled(cancel)
            raise ValueError(f'No usable reference photos for “{query}”. Try a shorter English subject or background, or check your connection.')
        return result

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
        return pixels,dict(model='orion-image-1',modelName='orion image 1',width=256,height=256,
            references=[public(row) for group in groups for row in group],selectedReferences=[public(subject)]+([public(background)] if background else []))
