"""Real HTTPS/model/reference generation in a packaged engine without CI CA paths."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--engine',type=Path)
    parser.add_argument('--prompts',nargs='+',default=['bicycle']);args=parser.parse_args()
    engine=args.engine or ROOT/'backend-dist/lambda-backend'/('lambda-backend.exe' if os.name=='nt' else 'lambda-backend')
    roots=engine.parent/'_internal/certifi/cacert.pem'
    assert roots.exists() and roots.read_text().count('BEGIN CERTIFICATE')>100,'Distributed engine must contain trusted CA roots.'
    with tempfile.TemporaryDirectory(prefix='lambda-native-network-') as folder:
        env=dict(os.environ,LAMBDA_DATA_HOME=folder,SSL_CERT_FILE=str(Path(folder)/'no-host-certificates.pem'),SSL_CERT_DIR=str(Path(folder)/'no-host-certificates'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
        process=subprocess.Popen([str(engine)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        messages=queue.Queue()
        def read():
            for line in process.stdout:
                try:messages.put(json.loads(line))
                except ValueError:pass
        threading.Thread(target=read,daemon=True).start();sequence=0
        def ask(method,params=None,timeout=180):
            nonlocal sequence
            sequence+=1;process.stdin.write(json.dumps(dict(id=sequence,method=method,params=params or {}))+'\n');process.stdin.flush()
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                row=messages.get(timeout=max(.1,end-time.monotonic()))
                if row.get('id')!=sequence:continue
                if row.get('error'):raise RuntimeError(row['error'])
                return row['result']
            raise RuntimeError('Packaged network request timed out.')
        try:
            ask('refresh_catalog');ask('refresh_image_catalog');records=[];charged=0
            for identifier in ['orion-image-1','orion-1.2']:
                ask('download',dict(id=identifier));ask('select_image_model',dict(id=identifier))
                for prompt in args.prompts:
                    result=ask('generate_image',dict(prompt=prompt,size=256,count=1,seed=42,modelId=identifier))
                    row=result['images'][0];raw=base64.b64decode(row['dataUrl'].split(',',1)[1])
                    assert row['model']==identifier and result['selectedImageModel']==identifier
                    assert row['safeSearch']=='strict' and all(ref['provider']=='DuckDuckGo Safe Search' for ref in row['references'])
                    with Image.open(io.BytesIO(raw)) as image:assert image.size==(256,256)
                    assert len(result['images'])==len(records)+1
                    charged+=len(prompt.split())*(1500 if identifier=='orion-1.2' else 1000)
                    assert result['quota']['used']==charged
                    records.append(dict(model=identifier,prompt=prompt,width=256,height=256,charged=row['tokenCost'],references=len(row['references'])))
                    print(json.dumps(records[-1]),flush=True)
            report=dict(passed=True,engine_version=result['engineVersion'],empty_host_ca_paths=True,model_catalog_https=True,image_catalog_https=True,optional_model_download=True,images=records)
            target=ROOT/'test-artifacts/network.json';target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(report,indent=2)+'\n')
        finally:
            process.stdin.close()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)
if __name__=='__main__':main()
