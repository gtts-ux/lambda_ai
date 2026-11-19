"""Fetch one immutable published Orion artifact for explicit native integration tests."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
entry=json.loads((ROOT/'models/image_catalog.json').read_text())['models'][0]
raw=urlopen(entry['url'],timeout=30).read(entry['bytes']+1)
if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise SystemExit('Orion test artifact failed validation')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(raw)
print(a.output.resolve())
