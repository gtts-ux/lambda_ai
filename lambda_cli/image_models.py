"""Optional image weights, isolated from chat-model selection and immutable old files."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import Request,urlopen
from . import __version__
from .models import atomic_json,validate_catalog
from .paths import data_dir
from .image_network import OrionNetwork
from .tls import https_context
from .image_pricing import TOKENS_PER_WORD

BUNDLED=Path(__file__).resolve().parent/'assets/image_catalog.json'
URL='https://raw.githubusercontent.com/gtts-ux/lambda_ai/main/models/image_catalog.json'

class ImageModels:
    def __init__(self,directory=None):
        self.directory=Path(directory) if directory is not None else data_dir()
        self.bundled=validate_catalog(json.loads(BUNDLED.read_text(encoding='utf-8')))
    def state(self):
        try:return json.loads((self.directory/'image-models.json').read_text(encoding='utf-8'))
        except FileNotFoundError:return {'installed':{}}
    def catalog(self):
        try:
            cached=validate_catalog(json.loads((self.directory/'image-catalog.json').read_text(encoding='utf-8')))
            # A cached catalog from the previous app must not hide newly bundled
            # releases. Keep newer remote revisions while preserving old models.
            merged={row['id']:row for row in self.bundled['models']}
            for row in cached['models']:
                if row['id'] not in merged or row['revision']>=merged[row['id']]['revision']:merged[row['id']]=row
            return dict(schema=1,models=list(merged.values()))
        except (OSError,ValueError):return self.bundled
    def path(self,item):
        name=item.get('filename','')
        if Path(name).name!=name or not name.endswith('.npz'):raise ValueError('Invalid image model path')
        return self.directory/'image-models'/name
    def entries(self):
        installed=self.state()['installed'];result=[]
        for entry in self.catalog()['models']:
            row=dict(entry);local=installed.get(row['id'])
            revision=local['revision'] if local and self.path(local).is_file() else None
            row.update(installed_revision=revision,update_available=revision is not None and revision<row['revision'],
                       tokens_per_word=TOKENS_PER_WORD.get(row['id'],1000))
            result.append(row)
        return result
    def selected(self):
        state=self.state();identifier=state.get('active')
        installed=state.get('installed',{})
        if identifier in installed and self.path(installed[identifier]).is_file():return identifier
        for row in reversed(self.entries()):
            if row['installed_revision'] is not None:return row['id']
        return None
    def select(self,identifier):
        self.resolve(identifier)
        state=self.state();state['active']=identifier
        atomic_json(self.directory/'image-models.json',state)
    def resolve(self,identifier=None):
        identifier=identifier or self.selected()
        item=self.state()['installed'].get(identifier)
        if not item or not self.path(item).is_file():raise ValueError('Download this image model in Settings → Models first.')
        return self.path(item)
    def refresh(self):
        with urlopen(Request(URL,headers={'User-Agent':'LambdaAI/'+__version__}),timeout=15,context=https_context()) as response:
            raw=response.read(1_048_577)
        if len(raw)>1_048_576:raise ValueError('Image catalog is too large')
        data=validate_catalog(json.loads(raw));atomic_json(self.directory/'image-catalog.json',data)
        return data
    def install(self,identifier,progress=None,cancel=None):
        row=next((x for x in self.entries() if x['id']==identifier),None)
        if row is None or row.get('kind')!='image':raise ValueError('Unknown image model')
        if tuple(map(int,__version__.split('.')))<tuple(map(int,row['min_app_version'].split('.'))):
            raise ValueError('Update the application before downloading this image model')
        if row['installed_revision']==row['revision']:return self.resolve(identifier)
        folder=self.directory/'image-models';folder.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(dir=folder,prefix='download-',suffix='.tmp');received=0;checksum=hashlib.sha256()
        try:
            with os.fdopen(fd,'wb') as out,urlopen(Request(row['url'],headers={'User-Agent':'LambdaAI/'+__version__}),timeout=20,context=https_context()) as source:
                while True:
                    if cancel is not None and cancel.is_set():raise ValueError('Download cancelled.')
                    chunk=source.read(65536)
                    if not chunk:break
                    received+=len(chunk)
                    if received>row['bytes']:raise ValueError('Image model exceeds its expected size')
                    out.write(chunk);checksum.update(chunk)
                    if progress:progress(f'Downloading {row["name"]}: {received*100//row["bytes"]}%')
            if received!=row['bytes'] or checksum.hexdigest()!=row['sha256']:
                raise ValueError('Image model checksum or size mismatch. Previous weights were kept.')
            network=OrionNetwork(temp)
            if network.metadata['model_id']!=identifier:raise ValueError('Image model identity mismatch. Previous weights were kept.')
            filename=f'{identifier}-r{row["revision"]}.npz';target=folder/filename;os.replace(temp,target)
            state=self.state();state['installed'][identifier]=dict(filename=filename,revision=row['revision'],sha256=row['sha256'])
            atomic_json(self.directory/'image-models.json',state);return target
        finally:Path(temp).unlink(missing_ok=True)
