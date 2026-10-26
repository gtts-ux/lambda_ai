"""Versioned model catalog and atomic, checksum-verified model installation."""

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import __version__
from .engine import DEFAULT_MODEL, Engine
from .paths import data_dir

CATALOG_URL = "https://raw.githubusercontent.com/gtts-ux/lambda_ai/main/models/catalog.json"
BUNDLED_CATALOG = Path(__file__).resolve().parent/"assets/catalog.json"
DEFAULT_ID = "lambda-1.0"
MAX_MODEL_BYTES = 50 * 1024 * 1024


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+"-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def validate_catalog(data):
    if data.get("schema") != 1 or not isinstance(data.get("models"), list) or not data["models"]:
        raise ValueError("Unsupported or empty model catalog.")
    identifiers = set()
    for model in data["models"]:
        identifier = model.get("id", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", identifier) or identifier in identifiers:
            raise ValueError("Invalid or duplicate model identifier.")
        identifiers.add(identifier)
        if not isinstance(model.get("name"), str) or not model["name"].strip():
            raise ValueError("A model name is required.")
        if not isinstance(model.get("revision"), int) or model["revision"] < 1:
            raise ValueError("Invalid model revision.")
        if not re.fullmatch(r"[0-9a-f]{64}", model.get("sha256", "")):
            raise ValueError("Missing or invalid model checksum.")
        if not isinstance(model.get("bytes"), int) or not 0 < model["bytes"] <= MAX_MODEL_BYTES:
            raise ValueError("Invalid model size.")
        if not re.fullmatch(r"\d+\.\d+\.\d+", model.get("min_app_version", "")):
            raise ValueError("A minimum app version is required.")
        url = urlparse(model.get("url", ""))
        if url.scheme != "https" or url.hostname not in ("raw.githubusercontent.com", "github.com"):
            raise ValueError("Model downloads must use HTTPS GitHub URLs.")
    return data


class ModelManager:
    def __init__(self, directory=None, catalog_url=None):
        self.directory = Path(directory) if directory is not None else data_dir()
        self.catalog_url = catalog_url or CATALOG_URL
        self.bundled = validate_catalog(json.loads(BUNDLED_CATALOG.read_text(encoding="utf-8")))

    def state(self):
        path = self.directory/"models.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"active": DEFAULT_ID, "installed": {}}

    def catalog(self):
        path = self.directory/"catalog.json"
        if path.exists():
            try:
                return validate_catalog(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                pass
        return self.bundled

    def entries(self):
        state = self.state()
        bundled = self.bundled["models"][0]
        result = []
        for entry in self.catalog()["models"]:
            entry = dict(entry)
            installed = state["installed"].get(entry["id"])
            revision = installed["revision"] if installed else bundled["revision"] if entry["id"] == DEFAULT_ID else None
            if installed and not self.installed_path(installed).exists():
                revision = bundled["revision"] if entry["id"] == DEFAULT_ID else None
            if entry["id"] == DEFAULT_ID:
                revision = max(revision or 0, bundled["revision"])
            entry.update(installed_revision=revision, active=entry["id"] == state["active"],
                         update_available=revision is not None and revision < entry["revision"])
            result.append(entry)
        return result

    def installed_path(self, item):
        filename = item.get("filename", "")
        if Path(filename).name != filename or not filename.endswith(".npz"):
            raise ValueError("Invalid installed model path.")
        return self.directory/"models"/filename

    def resolve(self, identifier=None):
        state = self.state()
        identifier = identifier or state["active"]
        if identifier in state["installed"]:
            installed = state["installed"][identifier]
            path = self.installed_path(installed)
            bundled_is_newer = identifier == DEFAULT_ID and self.bundled["models"][0]["revision"] > installed["revision"]
            if path.exists() and not bundled_is_newer:
                return path
        if identifier == DEFAULT_ID:
            return DEFAULT_MODEL
        raise ValueError(f"Model '{identifier}' is not installed. Use /model install {identifier}.")

    def activate(self, identifier):
        engine = Engine(self.resolve(identifier))
        state = self.state()
        state["active"] = identifier
        atomic_json(self.directory/"models.json", state)
        return engine

    def refresh_catalog(self):
        request = Request(self.catalog_url, headers={"User-Agent": f"LambdaAI/{__version__}"})
        with urlopen(request, timeout=15) as response:
            content = response.read(1024*1024+1)
        if len(content) > 1024*1024:
            raise ValueError("Model catalog is too large.")
        catalog = validate_catalog(json.loads(content))
        atomic_json(self.directory/"catalog.json", catalog)
        return catalog

    def install(self, identifier, progress=None, cancel=None):
        entry = next((e for e in self.entries() if e["id"] == identifier), None)
        if entry is None:
            raise ValueError(f"Unknown model '{identifier}'. Use /update to refresh the list.")
        required = tuple(map(int, entry["min_app_version"].split(".")))
        current = tuple(map(int, __version__.split(".")))
        if current < required:
            raise ValueError(f"This model requires Lambda app {entry['min_app_version']} or newer.")
        if entry["installed_revision"] == entry["revision"]:
            return self.resolve(identifier)
        target_dir = self.directory/"models"
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="download-", suffix=".tmp", dir=target_dir)
        checksum = hashlib.sha256()
        received = 0
        try:
            request = Request(entry["url"], headers={"User-Agent": f"LambdaAI/{__version__}"})
            with os.fdopen(fd, "wb") as output, urlopen(request, timeout=15) as response:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise ValueError("Download cancelled.")
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > entry["bytes"]:
                        raise ValueError("Downloaded model exceeds the expected size.")
                    checksum.update(chunk)
                    output.write(chunk)
                    if progress:
                        progress(f"Downloading {entry['name']}: {received*100//entry['bytes']}%")
            if received != entry["bytes"] or checksum.hexdigest() != entry["sha256"]:
                raise ValueError("Model checksum or size mismatch. The previous model was kept.")
            Engine(temporary)  # Validate all matrices before recording an installation.
            filename = f"{identifier}-r{entry['revision']}.npz"
            target = target_dir/filename
            os.replace(temporary, target)
            state = self.state()
            state["installed"][identifier] = {"filename": filename, "revision": entry["revision"], "sha256": entry["sha256"]}
            atomic_json(self.directory/"models.json", state)
            return target
        finally:
            Path(temporary).unlink(missing_ok=True)

    def update(self, progress=None, cancel=None):
        if progress:
            progress("Checking the model catalog…")
        self.refresh_catalog()
        changed = []
        for entry in self.entries():
            if entry["update_available"]:
                self.install(entry["id"], progress, cancel)
                changed.append(entry["name"])
        return "Updated: " + ", ".join(changed) if changed else "All installed models are up to date."
