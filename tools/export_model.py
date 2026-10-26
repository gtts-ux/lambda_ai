"""Convert a local Lambda training checkpoint to a read-only inference bundle."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def export(source, destination, model_id, name, router_path=None, question_features=False):
    with np.load(source, allow_pickle=False) as archive:
        if question_features and 'p_mode_bias' not in archive:
            raise ValueError('Question conditioning requires a v2 mode-conditioned checkpoint.')
        original = json.loads(str(archive["metadata"].item()))
        if not original.get("tokenizer"):
            raise ValueError("The app export requires a BPE model.")
        tokenizer = original["tokenizer"]
        metadata = {
            "format": "lambda-ai-inference-v1", "name": name, "model_id": model_id, "language": "en",
            "context": original["context"], "embedding": original["embedding"],
            "hidden": original["hidden"], "tokens": tokenizer["tokens"], "merges": tokenizer["merges"],
            "training_step": original["step"], "data_sha256": original.get("data_hash", ""),
            "source_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        }
        arrays = {key: archive["p_" + key].astype(np.float32)
                  for key in ("E", "W1", "b1", "W2", "b2", "W3", "b3")}
        if 'p_mode_bias' in archive:
            if router_path is None:
                raise ValueError('This checkpoint requires its learned router file (--router).')
            arrays['mode_bias']=archive['p_mode_bias'].astype(np.float32)
            with np.load(router_path,allow_pickle=False) as router:
                arrays['intent_W']=router['weights'].astype(np.float32)
                arrays['intent_b']=router['bias'].astype(np.float32)
                threshold=float(router['threshold'])
            metadata['format']='lambda-ai-inference-v2'
            metadata['router']={'features':int(arrays['intent_W'].shape[0]),'feature_version':1,
                                'threshold':threshold,'labels':['chat','math']}
            metadata['router_source_sha256']=hashlib.sha256(Path(router_path).read_bytes()).hexdigest()
            if question_features:
                metadata['question_features']={'version':1,'dimensions':768,'scale':4.0,'context':64,'mode':'chat'}
            lineage=Path(source).parent/'lineage.json'
            if lineage.exists():
                metadata['lineage']=json.loads(lineage.read_text())
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        np.savez_compressed(file, metadata=np.array(json.dumps(metadata, ensure_ascii=False)), **arrays)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest = {"filename": destination.name, "sha256": digest,
                "bytes": destination.stat().st_size, "training_step": metadata["training_step"],
                "parameters": sum(a.size for a in arrays.values()), "format": metadata["format"]}
    destination.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("--id", required=True, help="Owner-approved model ID")
    p.add_argument("--name", required=True, help="Owner-approved display name; do not invent one")
    p.add_argument('--router',type=Path,help='Learned intent head for v2 model exports')
    p.add_argument('--question-features',action='store_true',help='Checkpoint trained with hashed question conditioning')
    args = p.parse_args()
    export(args.source, args.destination, args.id, args.name,args.router,args.question_features)
