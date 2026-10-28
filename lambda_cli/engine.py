"""Read-only NumPy inference. No optimizer, gradients or training interface."""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from threading import Event
from time import perf_counter

os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")

import numpy as np

from .tokenizer import Tokenizer
from .intent import IntentRouter

DEFAULT_MODEL = Path(__file__).resolve().parent / "assets" / "model.npz"
STOP_MARKERS = ("\n\n", "\nQuestion:", "\nAnswer:")


@dataclass
class Settings:
    temperature: float = 0.4
    max_tokens: int = 120
    top_k: int = 8
    seed: int | None = None

    def validate(self):
        if not math.isfinite(self.temperature) or not 0.05 <= self.temperature <= 2:
            raise ValueError("Temperature must be between 0.05 and 2.")
        if not 1 <= self.max_tokens <= 2048:
            raise ValueError("The output limit must be between 1 and 2048 tokens.")
        if not 0 <= self.top_k <= 100000:
            raise ValueError("Top-k must be between 0 and 100000; 0 uses the entire vocabulary.")


@dataclass(frozen=True)
class GeneratedToken:
    id: int
    piece: str


@dataclass
class Result:
    text: str
    prompt_ids: list[int]
    generated: list[GeneratedToken]
    seconds: float
    context_used: int
    context_dropped: int
    finish_reason: str
    charged_tokens: int = 0
    intent: str | None = None
    intent_math_probability: float | None = None

    @property
    def tokens_per_second(self):
        return len(self.generated) / self.seconds if self.seconds > 0 else 0

    def to_dict(self):
        return {
            "text": self.text, "prompt_tokens": len(self.prompt_ids),
            "context_used": self.context_used, "context_dropped": self.context_dropped,
            "generated_tokens": len(self.generated), "seconds": round(self.seconds, 4),
            "tokens_per_second": round(self.tokens_per_second, 2),
            "finish_reason": self.finish_reason,
            "charged_tokens": self.charged_tokens,
            "intent": self.intent, "intent_math_probability": self.intent_math_probability,
            "prompt_token_ids": self.prompt_ids,
            "output_tokens": [{"id": t.id, "text": t.piece} for t in self.generated],
        }


def prompt_for(question):
    return f"Question: {question}\nAnswer: "


class Engine:
    def __new__(cls, path=None):
        candidate = Path(path or os.environ.get("LAMBDA_MODEL", DEFAULT_MODEL)).expanduser()
        with np.load(candidate, allow_pickle=False) as data:
            try:
                metadata = json.loads(str(data["metadata"].item()))
            except (KeyError, TypeError, json.JSONDecodeError) as error:
                raise ValueError("Invalid model file contents.") from error
        if metadata.get("format") == "lambda-ai-transformer-v3":
            from .transformer import TransformerEngine
            return TransformerEngine(candidate)
        if metadata.get("format") == "lambda-ai-pointer-transformer-v4":
            from .pointer import PointerEngine
            return PointerEngine(candidate)
        return super().__new__(cls)

    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("LAMBDA_MODEL", DEFAULT_MODEL)).expanduser().resolve()
        self.router = None
        self.router_weights = {}
        self.question_features = None
        try:
            with np.load(self.path, allow_pickle=False) as data:
                self.metadata = json.loads(str(data["metadata"].item()))
                format_name = self.metadata.get("format")
                if format_name not in ("lambda-ai-inference-v1", "lambda-ai-inference-v2"):
                    raise ValueError("Expected a supported Lambda inference model (v1 or v2).")
                info = self.metadata
                self.context = int(info["context"])
                self.embedding = int(info["embedding"])
                self.hidden = int(info["hidden"])
                self.tokenizer = Tokenizer(info["tokens"], info["merges"])
                v = len(self.tokenizer.tokens)
                if min(self.context, self.embedding, self.hidden, v) < 1:
                    raise ValueError("Invalid model dimensions.")
                shapes = {"E": (v, self.embedding), "W1": (self.context*self.embedding, self.hidden),
                          "b1": (self.hidden,), "W2": (self.hidden, self.hidden),
                          "b2": (self.hidden,), "W3": (self.hidden, v), "b3": (v,)}
                if format_name == "lambda-ai-inference-v2":
                    shapes["mode_bias"] = (2, self.hidden)
                self.weights = {}
                for key, shape in shapes.items():
                    array = np.asarray(data[key], dtype=np.float32)
                    if array.shape != shape or not np.isfinite(array).all():
                        raise ValueError(f"Invalid weight matrix: {key}.")
                    array.flags.writeable = False
                    self.weights[key] = array
                if format_name == "lambda-ai-inference-v2":
                    config = info["router"]
                    if not isinstance(config, dict) or config.get("feature_version") != 1 or config.get('labels') != ['chat','math']:
                        raise ValueError("Unsupported intent feature format. Upgrade the app.")
                    self.router = IntentRouter(data["intent_W"], data["intent_b"], config["threshold"])
                    if len(self.router.weights) != config["features"]:
                        raise ValueError("Intent feature count does not match the weights.")
                    self.router_weights = {"intent_W": self.router.weights, "intent_b": self.router.bias}
                    self.question_features = info.get('question_features')
                    if self.question_features is not None and self.question_features != {
                        'version':1,'dimensions':768,'scale':4.0,'context':64,'mode':'chat'
                    }:
                        raise ValueError('Unsupported question feature format. Upgrade the app.')
                    if self.question_features and (self.context < 64 or self.context*self.embedding < 768):
                        raise ValueError('Question features exceed the model input dimensions.')
                self.pad = self.tokenizer.ids["\n"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid model file contents.") from error

    @property
    def parameter_count(self):
        return sum(w.size for w in self.all_weights.values())

    @property
    def all_weights(self):
        return {**self.weights, **self.router_weights}

    def classify(self, question):
        return self.router.predict(question).to_dict() if self.router else {
            "intent": None, "math_probability": None}

    def info(self):
        return {
            "name": self.metadata.get("name", "Lambda"),
            "architecture": "Mode-conditioned MLP + learned intent router" if self.router else "Autoregressive MLP · 2 × tanh",
            "parameters": self.parameter_count, "vocabulary": len(self.tokenizer.tokens),
            "context": self.context, "embedding": self.embedding, "hidden": self.hidden,
            "training_step": self.metadata.get("training_step", 0),
            "weight_bytes": sum(w.nbytes for w in self.all_weights.values()),
            "file_bytes": self.path.stat().st_size, "path": str(self.path),
            "dtype": "float32", "device": "CPU", "tokenizer": "BPE · locally learned vocabulary",
            "language": self.metadata.get("language", "en"), "model_id": self.metadata.get("model_id", "lambda-1.0"),
            "generator_parameters": sum(w.size for w in self.weights.values()),
            "router_parameters": sum(w.size for w in self.router_weights.values()),
            "intent_routing": self.router is not None,
            "question_features": self.question_features,
        }

    def logits(self, ids, mode=0, question_features=None):
        x = np.asarray([ids[-self.context:]], dtype=np.int32)
        w = self.weights
        flat = w["E"][x].reshape(1, -1)
        if question_features is not None:
            flat = flat.copy()
            flat[0,:768] += 4.0 * question_features
        activation = flat @ w["W1"] + w["b1"]
        if self.router is not None:
            activation += w["mode_bias"][mode]
        h1 = np.tanh(activation)
        h2 = np.tanh(h1 @ w["W2"] + w["b2"])
        return (h2 @ w["W3"] + w["b3"])[0]

    def generate(self, prompt, settings=None, on_text=None, cancel=None):
        settings = settings or Settings()
        settings.validate()
        start = perf_counter()
        prompt_ids = self.tokenizer.encode(prompt)
        question = prompt[10:-9] if prompt.startswith("Question: ") and prompt.endswith("\nAnswer: ") else prompt
        decision = self.router.predict(question) if self.router else None
        mode = decision.index if decision else 0
        features = None
        if self.question_features and mode == 0:
            bounded = self.tokenizer.decode(self.tokenizer.encode(question)[-64:])
            features = IntentRouter.features(bounded,768)
        ids = [self.pad] * max(0, self.context-len(prompt_ids)) + prompt_ids
        rng = np.random.default_rng(settings.seed)
        generated = []
        raw = ""
        visible = ""
        reason = "limit"
        for _ in range(settings.max_tokens):
            if cancel is not None and cancel.is_set():
                reason = "cancelled"
                break
            values = self.logits(ids, mode, features).astype(np.float64) / settings.temperature
            if 0 < settings.top_k < len(values):
                keep = np.argpartition(values, -settings.top_k)[-settings.top_k:]
                masked = np.full_like(values, -np.inf)
                masked[keep] = values[keep]
                values = masked
            values -= values.max()
            p = np.exp(values)
            p /= p.sum()
            token = int(rng.choice(len(values), p=p))
            piece = self.tokenizer.tokens[token]
            ids.append(token)
            generated.append(GeneratedToken(token, piece))
            raw += piece
            boundaries = [raw.find(marker) for marker in STOP_MARKERS if marker in raw]
            if boundaries:
                visible = raw[:min(boundaries)].strip()
                reason = "stop"
                break
            # Hold partial stop markers until the remaining tokens arrive.
            hold = max((n for marker in STOP_MARKERS for n in range(1, len(marker))
                        if raw.endswith(marker[:n])), default=0)
            visible = raw[:-hold] if hold else raw
            if on_text:
                on_text(visible.lstrip(), len(generated))
        else:
            visible = raw
        if reason == "cancelled":
            visible = raw
        visible = visible.strip()
        if on_text:
            on_text(visible, len(generated))
        return Result(visible, prompt_ids, generated, perf_counter()-start,
                      min(len(prompt_ids), self.context), max(0, len(prompt_ids)-self.context), reason,
                      intent=decision.name if decision else None,
                      intent_math_probability=decision.math_probability if decision else None)
