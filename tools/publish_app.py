"""Stage an immutable application wheel and its update manifest before git push."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lambda_cli import __version__
from lambda_cli.app_updates import RELEASE_ROOT,validate_wheel,validate_manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('wheel',type=Path);args=p.parse_args()
    name=f'lambda_ai_terminal-{__version__}-py3-none-any.whl'
    if args.wheel.name!=name:p.error('Wheel filename must match the application version.')
    content=args.wheel.read_bytes()
    release=dict(schema=1,version=__version__,minimum_python=[3,11],url=RELEASE_ROOT+name,
                 bytes=len(content),sha256=hashlib.sha256(content).hexdigest())
    validate_manifest(release);validate_wheel(args.wheel,release)
    target=ROOT/'releases';target.mkdir(exist_ok=True)
    destination=target/name
    if destination.exists() and destination.read_bytes()!=content:
        p.error('Never replace a released wheel. Bump the application version first.')
    shutil.copyfile(args.wheel,destination)
    (target/'app.json').write_text(json.dumps(release,indent=2)+'\n')
    print(f'Staged app {__version__}: {len(content):,} bytes; SHA256 {release["sha256"]}')


if __name__=='__main__':main()
