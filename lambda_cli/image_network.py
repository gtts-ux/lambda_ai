"""Portable NumPy inference for the owner's three-part Orion image network."""
import hashlib
import json
import math
import re
import zipfile
import numpy as np

def expected_shapes():
    d={}
    def param(prefix,shape,bias=True):
        d[prefix+'.weight']=shape
        if bias:d[prefix+'.bias']=(shape[0],)
    def block(prefix,cin,cout):
        param(prefix+'.layers.0',(cout,cin,3,3));param(prefix+'.layers.1',(cout,))
        param(prefix+'.layers.3',(cout,cout,3,3));param(prefix+'.layers.4',(cout,))
    param('mask.words',(2048,32),False);param('mask.text',(96,32))
    for name,a,b in [('a',3,24),('b',24,48),('c',48,96),('d',144,48),('e',72,24)]:block('mask.'+name,a,b)
    param('mask.out',(1,24,1,1))
    param('flow.words',(2048,64),False);param('flow.condition.0',(128,129));param('flow.condition.2',(128,128))
    param('flow.input',(32,10,3,3));param('flow.down1',(64,32,4,4));param('flow.down2',(96,64,4,4))
    for name,a,b in [('enc1',32,32),('enc2',64,64),('middle1',96,96),('middle2',96,96),('dec2',160,64),('dec1',96,32)]:
        p='flow.'+name
        param(p+'.norm1',(a,));param(p+'.conv1',(b,a,3,3));param(p+'.norm2',(b,))
        param(p+'.conv2',(b,b,3,3));param(p+'.film',(b*2,128))
        if a!=b:param(p+'.skip',(b,a,1,1))
    d['flow.attention.in_proj_weight']=(288,96);d['flow.attention.in_proj_bias']=(288,)
    param('flow.attention.out_proj',(96,96));param('flow.output.0',(32,));param('flow.output.2',(3,32,3,3))
    block('detail.low',12,32);param('detail.affine',(6,32))
    param('detail.up1.0',(96,32,3,3));param('detail.up2.0',(64,24,3,3))
    param('detail.refine.0',(24,23,3,3));param('detail.refine.2',(24,1,3,3));param('detail.refine.4',(3,24,1,1))
    d['detail.coordinates']=(1,2,64,64)
    return d

def prompt_ids(prompts):
    out=[]
    for prompt in prompts:
        words=re.findall(r'[a-z0-9]+',prompt.lower())[:48]
        ids=[1+int.from_bytes(hashlib.blake2b(w.encode(),digest_size=4).digest(),'little')%2047 for w in words]
        out.append(ids+[0]*(48-len(ids)))
    return np.asarray(out,dtype=np.int64)

def silu(x):return x/(1+np.exp(np.clip(-x,-80,80)))

def resize(x,h,w=None,nearest=False):
    w=h if w is None else w;ih,iw=x.shape[-2:]
    if (ih,iw)==(h,w):return x
    if nearest:
        return x[:,:,np.minimum(np.arange(h)*ih//h,ih-1)[:,None],np.minimum(np.arange(w)*iw//w,iw-1)[None,:]]
    y=np.maximum(0,(np.arange(h,dtype=np.float32)+.5)*np.float32(ih/h)-.5)
    xx=np.maximum(0,(np.arange(w,dtype=np.float32)+.5)*np.float32(iw/w)-.5)
    y0=y.astype(int);x0=xx.astype(int);y1=np.minimum(y0+1,ih-1);x1=np.minimum(x0+1,iw-1)
    fy=(y-y0).astype(np.float32)[None,None,:,None];fx=(xx-x0).astype(np.float32)[None,None,None,:]
    a=x[:,:,y0[:,None],x0[None,:]]*(1-fx)+x[:,:,y0[:,None],x1[None,:]]*fx
    b=x[:,:,y1[:,None],x0[None,:]]*(1-fx)+x[:,:,y1[:,None],x1[None,:]]*fx
    return a*(1-fy)+b*fy

def grid_sample(x,theta):
    b,c,h,w=x.shape
    xx=(np.arange(w,dtype=np.float32)+.5)*np.float32(2/w)-1
    yy=(np.arange(h,dtype=np.float32)+.5)*np.float32(2/h)-1
    gy,gx=np.meshgrid(yy,xx,indexing='ij')
    coord=np.stack([gx,gy,np.ones_like(gx)],-1)
    grid=np.einsum('bij,hwj->bhwi',theta,coord,optimize=True)
    px=((grid[...,0]+1)*w-1)*.5;py=((grid[...,1]+1)*h-1)*.5
    x0=np.floor(px).astype(int);y0=np.floor(py).astype(int);fx=px-x0;fy=py-y0
    output=np.zeros_like(x)
    for dx,dy,weight in [(0,0,(1-fx)*(1-fy)),(1,0,fx*(1-fy)),(0,1,(1-fx)*fy),(1,1,fx*fy)]:
        ix=x0+dx;iy=y0+dy;valid=(ix>=0)&(ix<w)&(iy>=0)&(iy<h)
        for n in range(b):
            values=x[n][:,np.clip(iy[n],0,h-1),np.clip(ix[n],0,w-1)]
            output[n]+=values*(weight[n]*valid[n]).astype(np.float32)[None]
    return output

class OrionNetwork:
    def __init__(self,path):
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist())>250 or sum(x.file_size for x in archive.infolist())>20_000_000:
                raise ValueError('Invalid Orion model archive size')
        expected=expected_shapes()
        with np.load(path,allow_pickle=False) as data:
            self.metadata=json.loads(str(data['metadata']))
            modes={'orion-image-1':'object-composition','orion-1.2':'full-scene-reference'}
            identifier=self.metadata.get('model_id')
            if self.metadata.get('format')!='orion-image-v1' or identifier not in modes:
                raise ValueError('Unsupported Orion model format')
            self.generation_mode=self.metadata.get('generation_mode','object-composition')
            if self.generation_mode!=modes[identifier]:raise ValueError('Unsupported Orion generation mode')
            if set(data.files)!=set(expected)|{'metadata'}:raise ValueError('Invalid Orion tensors')
            self.p={}
            for name,shape in expected.items():
                value=data[name]
                if value.shape!=shape or value.dtype!=np.float32 or not np.isfinite(value).all():
                    raise ValueError('Invalid Orion tensor: '+name)
                self.p[name]=value.copy();self.p[name].flags.writeable=False

    def linear(self,x,p):return x@self.p[p+'.weight'].T+self.p[p+'.bias']

    def conv(self,x,p,stride=1,padding=None,groups=1):
        weight=self.p[p+'.weight'];k=weight.shape[-1]
        padding=k//2 if padding is None else padding
        if padding:x=np.pad(x,((0,0),(0,0),(padding,padding),(padding,padding)))
        windows=np.lib.stride_tricks.sliding_window_view(x,(k,k),axis=(-2,-1))[:,:,::stride,::stride]
        b,c,h,w=windows.shape[:4]
        if groups==c:
            result=np.einsum('bchwij,cij->bchw',windows,weight[:,0],optimize=True)
        else:
            matrix=np.ascontiguousarray(windows.transpose(0,2,3,1,4,5)).reshape(b*h*w,-1)
            result=(matrix@weight.reshape(weight.shape[0],-1).T).reshape(b,h,w,-1).transpose(0,3,1,2)
        return result+self.p[p+'.bias'][None,:,None,None]

    def norm(self,x,p):
        b,c,h,w=x.shape;v=x.reshape(b,8,c//8,h,w);mean=v.mean((2,3,4),keepdims=True)
        variance=((v-mean)**2).mean((2,3,4),keepdims=True)
        result=((v-mean)/np.sqrt(variance+np.float32(1e-5))).reshape(x.shape)
        return result*self.p[p+'.weight'][None,:,None,None]+self.p[p+'.bias'][None,:,None,None]

    def block(self,x,p):
        x=silu(self.norm(self.conv(x,p+'.layers.0'),p+'.layers.1'))
        return silu(self.norm(self.conv(x,p+'.layers.3'),p+'.layers.4'))

    def words(self,ids,p):
        return self.p[p+'.words.weight'][ids].sum(1)/(ids!=0).sum(1,keepdims=True).clip(1).astype(np.float32)

    def mask(self,image,ids):
        x=resize(image,96);a=self.block(x,'mask.a')
        b=self.block(a.reshape(len(a),24,48,2,48,2).mean((3,5)),'mask.b')
        c=self.block(b.reshape(len(b),48,24,2,24,2).mean((3,5)),'mask.c')
        c=c+self.linear(self.words(ids,'mask'),'mask.text')[:,:,None,None]
        d=self.block(np.concatenate([resize(c,48,nearest=True),b],1),'mask.d')
        e=self.block(np.concatenate([resize(d,96,nearest=True),a],1),'mask.e')
        return resize(self.conv(e,'mask.out',padding=0),image.shape[-2],image.shape[-1])

    def residual(self,x,condition,p):
        h=self.conv(silu(self.norm(x,p+'.norm1')),p+'.conv1')
        scale,shift=np.split(self.linear(condition,p+'.film'),2,axis=1)
        h=self.norm(h,p+'.norm2')*(1+scale[:,:,None,None])+shift[:,:,None,None]
        skip=self.conv(x,p+'.skip',padding=0) if p+'.skip.weight' in self.p else x
        return skip+self.conv(silu(h),p+'.conv2')

    def flow(self,noisy,t,refs,ids,matte):
        freq=np.exp(np.arange(32,dtype=np.float32)*np.float32(-math.log(10000)/31))
        phase=t[:,None]*freq[None,:]*1000
        condition=np.concatenate([np.sin(phase),np.cos(phase),self.words(ids,'flow'),np.ones((len(t),1),np.float32)],1)
        condition=self.linear(silu(self.linear(condition,'flow.condition.0')),'flow.condition.2')
        gated=refs.copy();gated[:,0]*=matte
        x1=self.residual(self.conv(np.concatenate([noisy,gated.reshape(len(refs),6,64,64),matte],1),'flow.input'),condition,'flow.enc1')
        x2=self.residual(self.conv(x1,'flow.down1',stride=2,padding=1),condition,'flow.enc2')
        h=self.residual(self.conv(x2,'flow.down2',stride=2,padding=1),condition,'flow.middle1')
        pooled=h.reshape(len(h),96,8,2,8,2).mean((3,5)).reshape(len(h),96,64).transpose(0,2,1)
        qkv=pooled@self.p['flow.attention.in_proj_weight'].T+self.p['flow.attention.in_proj_bias']
        q,k,v=[z.reshape(len(h),64,4,24).transpose(0,2,1,3) for z in np.split(qkv,3,axis=2)]
        scores=(q@k.transpose(0,1,3,2))*np.float32(1/math.sqrt(24))
        attention=np.exp(scores-scores.max(-1,keepdims=True));attention/=attention.sum(-1,keepdims=True)
        attended=(attention@v).transpose(0,2,1,3).reshape(len(h),64,96)
        attended=self.linear(attended,'flow.attention.out_proj').transpose(0,2,1).reshape(len(h),96,8,8)
        h=self.residual(h+resize(attended,16),condition,'flow.middle2')
        h=self.residual(np.concatenate([resize(h,32,nearest=True),x2],1),condition,'flow.dec2')
        h=self.residual(np.concatenate([resize(h,64,nearest=True),x1],1),condition,'flow.dec1')
        return self.conv(silu(self.norm(h,'flow.output.0')),'flow.output.2')

    @staticmethod
    def shuffle(x):
        b,c,h,w=x.shape
        return x.reshape(b,c//4,2,2,h,w).transpose(0,1,4,2,5,3).reshape(b,c//4,h*2,w*2)

    def detail(self,coarse,refs,matte):
        small=resize(refs.reshape(len(refs),6,256,256),64);alpha=resize(matte,64)
        low=self.block(np.concatenate([coarse,small,alpha,np.broadcast_to(self.p['detail.coordinates'],(len(refs),2,64,64))],1),'detail.low')
        theta=np.asarray([[[1,0,0],[0,1,0]]],np.float32)+np.float32(1.5)*np.tanh(self.linear(low.mean((2,3)),'detail.affine')).reshape(-1,2,3)
        warped=grid_sample(refs[:,0]*matte,theta);warped_mask=grid_sample(matte,theta)
        feat=silu(self.shuffle(self.conv(low,'detail.up1.0')))
        feat=silu(self.shuffle(self.conv(feat,'detail.up2.0')))
        x=np.concatenate([feat,warped,refs[:,1],warped_mask],1)
        x=silu(self.conv(x,'detail.refine.0'));x=silu(self.conv(x,'detail.refine.2',groups=24))
        return np.tanh(self.conv(x,'detail.refine.4',padding=0))

    def sample(self,refs,matte,prompt,seed=42,steps=24,progress=None,cancel=None,initial=None):
        x=np.random.default_rng(seed).standard_normal((1,3,64,64)).astype(np.float32) if initial is None else initial.copy()
        ids=prompt_ids([prompt]);dt=np.float32(1/steps)
        for i in range(steps):
            if cancel is not None and cancel.is_set():raise ValueError('Image generation cancelled.')
            t=np.asarray([i/steps],np.float32);v=self.flow(x,t,refs,ids,matte)
            if i+1<steps:x+=dt*(v+self.flow(x+dt*v,t+dt,refs,ids,matte))*np.float32(.5)
            else:x+=dt*v
            np.clip(x,-4,4,out=x)
            if progress:progress('Composing image',int(20+60*(i+1)/steps))
        return x.clip(-1,1)
