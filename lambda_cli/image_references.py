"""General image references from explicitly filtered Safe Search results only."""
import hashlib
import html
import io
import json
from pathlib import Path
import re
import ssl
import time
from urllib.parse import urlencode,urlparse
from urllib.request import Request,urlopen
from PIL import Image,ImageOps
from . import __version__
from .models import atomic_json
from .tls import https_context

THUMB_HOSTS={f'tse{i}.mm.bing.net' for i in range(1,5)}|{'external-content.duckduckgo.com'}
HOSTS=THUMB_HOSTS|{'duckduckgo.com','safe.duckduckgo.com'}

def cancelled(cancel):
    if cancel is not None and cancel.is_set():raise ValueError('Image generation cancelled.')

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
        request=Request(url,headers={'User-Agent':'Mozilla/5.0 LambdaAI/'+__version__,
            'Referer':'https://safe.duckduckgo.com/'})
        with urlopen(request,timeout=15,context=https_context()) as response:
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

    @staticmethod
    def record_error(error):
        if isinstance(getattr(error,'reason',error),ssl.SSLCertVerificationError):
            raise ValueError('A secure connection to the image service failed. Update Lambda or check this network’s certificate settings.') from error

    def safe_results(self,query,cancel):
        # This separate namespace never reuses the older unfiltered providers.
        key=hashlib.sha256(('safe-images-v1:'+query).encode()).hexdigest()
        cache=self.directory/(key+'.json')
        if cache.exists() and time.time()-cache.stat().st_mtime<21600:
            value=json.loads(cache.read_text())
            if value.get('safeSearch')=='strict' and isinstance(value.get('results'),list):return value['results']
        landing='https://safe.duckduckgo.com/?'+urlencode(dict(q=query,iax='images',ia='images',kp=1))
        page=self.fetcher(landing,cancel).decode('utf-8',errors='replace')
        match=re.search(r'vqd=["\x27]?([A-Za-z0-9_-]{1,200})',page)
        if not match:raise ValueError('Safe Search is temporarily unavailable. Try again later.')
        # The image endpoint is on the main search host; both explicit filter
        # parameters accompany every query, including queries with operators.
        url='https://duckduckgo.com/i.js?'+urlencode(dict(l='wt-wt',o='json',q=query,vqd=match[1],p=1,kp=1))
        response=json.loads(self.fetcher(url,cancel))
        rows=response.get('results')
        if not isinstance(rows,list):raise ValueError('Safe Search is temporarily unavailable. Try again later.')
        rows=rows[:40]
        atomic_json(cache,dict(safeSearch='strict',results=rows))
        return rows

    def search(self,query,role,cancel):
        variants=list(dict.fromkeys([re.sub(r'\s*,\s*',' ',query)]+[part.strip() for part in query.split(',') if part.strip()]))[:4]
        deadline=time.monotonic()+60
        for variant in variants:
            cancelled(cancel)
            if time.monotonic()>deadline:break
            results=self.search_phrase(variant,role,cancel,deadline)
            if results:return results
        cancelled(cancel)
        raise ValueError(f'No reference photos could be downloaded for “{query}”. Try a simpler subject or try again later.')

    def search_phrase(self,query,role,cancel,deadline):
        try:raw=self.safe_results(query,cancel)
        except (OSError,ValueError) as error:
            cancelled(cancel);self.record_error(error)
            # Never retry through an unfiltered provider when filtering fails.
            raise ValueError('Safe Search is temporarily unavailable. Try again later.') from error
        results=[];seen=set()
        for index,item in enumerate(raw):
            cancelled(cancel)
            if time.monotonic()>deadline:break
            if not isinstance(item,dict):continue
            preview=item.get('thumbnail','');source=item.get('url','');parsed=urlparse(source)
            if urlparse(preview).scheme!='https' or urlparse(preview).hostname not in THUMB_HOSTS:continue
            if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:continue
            identifier='safe:'+hashlib.sha256(preview.encode()).hexdigest()
            path=self.directory/(hashlib.sha256(identifier.encode()).hexdigest()+'.png')
            try:
                if not path.exists():
                    with Image.open(io.BytesIO(self.fetcher(preview,cancel))) as original:
                        if original.width*original.height>16_000_000 or min(original.size)<64:continue
                        image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((512,512));image.save(path)
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                if digest in seen:continue
                title=html.unescape(re.sub('<[^>]+>','',str(item.get('title',''))))[:500]
                results.append(dict(id=identifier,title=title,image_url=preview,source_url=source,
                    credit=parsed.hostname,license='See original source',provider='DuckDuckGo Safe Search',
                    safeSearch='strict',relevance=20-index*.25,path=str(path),sha256=digest))
                seen.add(digest)
            except (OSError,ValueError) as error:self.record_error(error)
            if len(results)>=10:break
        return results
