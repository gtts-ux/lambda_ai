"""Register an explicitly named inference model in both published catalogs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lambda_cli.engine import Engine
from lambda_cli.models import validate_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file",type=Path)
    parser.add_argument("--id",required=True)
    parser.add_argument("--name",required=True)
    parser.add_argument("--revision",required=True,type=int)
    parser.add_argument("--min-app-version",default="0.1.0")
    args = parser.parse_args()
    path = args.file.resolve()
    relative = path.relative_to(ROOT).as_posix()
    engine = Engine(path)
    if engine.metadata.get("model_id") != args.id or engine.metadata.get("name") != args.name:
        parser.error("Model metadata must match the owner-approved ID and name. Export it again with those names.")
    catalog_path = ROOT/"models/catalog.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {"schema":1,"models":[]}
    entry = {"id":args.id,"name":args.name,"revision":args.revision,"language":"en",
             "min_app_version":args.min_app_version,"format":"lambda-ai-inference-v1",
             "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size,
             "url":"https://raw.githubusercontent.com/gtts-ux/lambda_ai/main/"+relative,
             "description":"Small English language model trained from random weights."}
    previous = next((e for e in catalog["models"] if e["id"]==args.id),None)
    if previous is not None and args.revision < previous["revision"]:
        parser.error("A model revision cannot decrease.")
    if previous is not None:
        catalog["models"][catalog["models"].index(previous)] = entry
    else:
        catalog["models"].append(entry)
    validate_catalog(catalog)
    for target in [catalog_path,ROOT/"lambda_cli/assets/catalog.json"]:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(catalog,indent=2)+"\n",encoding="utf-8")
    print(f"Registered {args.name}, revision {args.revision}: {relative}")


if __name__ == "__main__":
    main()
