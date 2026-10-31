"""Read-only Transformer inference in NumPy. No PyTorch dependency in the app."""
import json
import math
from pathlib import Path
from time import perf_counter
import numpy as np

from .byte_tokenizer import ByteTokenizer, SPECIAL, PAD, BOS, USER, ASSISTANT, END

FORMAT = "lambda-ai-transformer-v3"
POINTER_FORMAT = "lambda-ai-pointer-transformer-v4"
GROUNDED_FORMAT = "lambda-ai-grounded-transformer-v5"


def weight_shapes(config):
    d, n, v, t = (int(config[k]) for k in ("width", "layers", "vocabulary", "context"))
    h = int(config["heads"])
    if not (1 <= n <= 16 and 8 <= d <= 1024 and 1 <= h <= 32 and d % h == 0
            and 16 <= t <= 2048 and 261 <= v <= 16384):
        raise ValueError("Invalid Transformer dimensions.")
    shapes = {"token": (v, d), "position": (t, d), "norm_w": (d,), "norm_b": (d,)}
    for i in range(n):
        for name, shape in {"ln1_w": (d,), "ln1_b": (d,), "qkv": (d, 3*d),
                            "proj": (d, d), "ln2_w": (d,), "ln2_b": (d,),
                            "up": (d, 4*d), "down": (4*d, d)}.items():
            shapes[f"b{i}_{name}"] = shape
    if config.get("format") in (POINTER_FORMAT,GROUNDED_FORMAT):
        p = int(config["pointer_width"])
        if not 8 <= p <= 256:
            raise ValueError("Invalid pointer dimensions.")
        shapes.update({"pointer_norm_w": (d,), "pointer_norm_b": (d,),
                       "pointer_q": (2*d, p), "pointer_k": (2*d, p),
                       "pointer_gate_w": (3*d, 1), "pointer_gate_b": (1,)})
    if config.get('format')==GROUNDED_FORMAT:
        rank=int(config['evidence_rank']);count=int(config['evidence_layers']);features=int(config['search_features'])
        if not (1<=rank<=64 and 1<=count<=n and 128<=features<=16384):raise ValueError('Invalid grounded model dimensions.')
        shapes.update(search_w=(features,2),search_b=(2,),evidence_gate_bias=(1,))
        targets={f'b{i}_{name}':shapes[f'b{i}_{name}'] for i in range(n-count,n) for name in ('qkv','proj','up','down')}
        targets.update(pointer_q=shapes['pointer_q'],pointer_k=shapes['pointer_k'],pointer_gate_w=shapes['pointer_gate_w'])
        for key,(a,b) in targets.items():
            shapes['evidence_'+key+'_a']=(a,rank);shapes['evidence_'+key+'_b']=(rank,b)
        if config.get('span_reader'):
            shapes.update(span_end_q=(2*d,p),span_end_k=(2*d,p),span_answerable_w=(d,2),span_answerable_b=(2,))
    if sum(np.prod(s) for s in shapes.values()) > 30000000:
        raise ValueError("Transformer exceeds the supported parameter budget.")
    return shapes


def norm(x, w, b):
    centered = x - x.mean(axis=-1, keepdims=True)
    return centered / np.sqrt((centered*centered).mean(axis=-1, keepdims=True)+1e-5)*w+b


def gelu(x):
    # Python scalars preserve float32 arrays under NumPy 2 scalar promotion.
    return 0.5*x*(1+np.tanh(math.sqrt(2/math.pi)*(x+0.044715*x*x*x)))


class TransformerEngine:
    supported_format = FORMAT

    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        try:
            with np.load(self.path, allow_pickle=False) as data:
                self.metadata = json.loads(str(data["metadata"].item()))
                if self.metadata.get("format") != self.supported_format:
                    raise ValueError("Expected a supported Transformer model.")
                shapes = weight_shapes(self.metadata)
                if set(data.files) != set(shapes) | {"metadata"}:
                    raise ValueError("Unexpected or missing Transformer arrays.")
                self.weights = {}
                for key, shape in shapes.items():
                    value = np.asarray(data[key], dtype=np.float32)
                    if value.shape != shape or not np.isfinite(value).all():
                        raise ValueError(f"Invalid Transformer weights: {key}.")
                    value.flags.writeable = False
                    self.weights[key] = value
                self.tokenizer = ByteTokenizer(self.metadata["tokenizer"])
                if len(self.tokenizer.tokens) != int(self.metadata["vocabulary"]):
                    raise ValueError("Tokenizer size does not match the Transformer.")
                self.context = int(self.metadata["context"])
                self.embedding = self.hidden = int(self.metadata["width"])
                self.layers = int(self.metadata["layers"])
                self.heads = int(self.metadata["heads"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid Transformer model file.") from error
        self.router = None
        self.question_features = None
        self.supports_memory = True

    @property
    def all_weights(self):
        return self.weights

    @property
    def parameter_count(self):
        return sum(a.size for a in self.weights.values())

    def classify(self, question):
        return {"intent": None, "math_probability": None}

    def info(self):
        return {"name": self.metadata.get("name", "Unnamed experimental model"),
                "architecture": f"Causal Transformer · {self.layers} layers · {self.heads} heads",
                "parameters": self.parameter_count, "vocabulary": len(self.tokenizer.tokens),
                "context": self.context, "embedding": self.embedding, "hidden": self.hidden,
                "layers": self.layers, "training_step": self.metadata.get("training_step", 0),
                "weight_bytes": sum(a.nbytes for a in self.weights.values()),
                "file_bytes": self.path.stat().st_size, "path": str(self.path),
                "dtype": "float32", "device": "CPU", "tokenizer": "UTF-8 byte BPE · learned locally",
                "language": "en", "model_id": self.metadata.get("model_id"),
                "generator_parameters": self.parameter_count, "router_parameters": 0,
                "intent_routing": False, "question_features": None, "conversation_memory": True}

    def hidden_states(self, ids, cache=None):
        """Prefill or append using a per-generation KV cache."""
        ids = np.asarray(ids, dtype=np.int64)
        start = cache[0][0].shape[1] if cache else 0
        if start+len(ids) > self.context:
            raise ValueError("Transformer context exceeded.")
        w = self.weights
        x = w["token"][ids] + w["position"][start:start+len(ids)]
        next_cache = []
        for i in range(self.layers):
            prefix = f"b{i}_"
            z = norm(x, w[prefix+"ln1_w"], w[prefix+"ln1_b"])
            q, k, v = np.split(z @ w[prefix+"qkv"], 3, axis=-1)
            q, k, v = (a.reshape(len(ids), self.heads, -1).transpose(1, 0, 2) for a in (q, k, v))
            if cache:
                k = np.concatenate((cache[i][0], k), axis=1)
                v = np.concatenate((cache[i][1], v), axis=1)
            next_cache.append((k, v))
            scores = (q @ k.transpose(0, 2, 1)) / math.sqrt(self.embedding//self.heads)
            mask = np.arange(k.shape[1])[None, :] > (start+np.arange(len(ids)))[:, None]
            scores = np.where(mask[None, :, :], -np.inf, scores)
            scores -= scores.max(axis=-1, keepdims=True)
            p = np.exp(scores)
            p /= p.sum(axis=-1, keepdims=True)
            attended = (p @ v).transpose(1, 0, 2).reshape(len(ids), self.embedding)
            x = x + attended @ w[prefix+"proj"]
            z = norm(x, w[prefix+"ln2_w"], w[prefix+"ln2_b"])
            x = x + gelu(z @ w[prefix+"up"]) @ w[prefix+"down"]
        x = norm(x, w["norm_w"], w["norm_b"])
        return x, next_cache

    def logits(self, ids, cache=None):
        x, next_cache = self.hidden_states(ids, cache)
        return x @ self.weights["token"].T, next_cache

    def generate(self, prompt, settings=None, on_text=None, cancel=None):
        from .engine import Settings, GeneratedToken, Result
        from .byte_tokenizer import conversation_prompt
        settings = settings or Settings()
        settings.validate()
        if isinstance(prompt, str):
            question = prompt[10:-9] if prompt.startswith("Question: ") and prompt.endswith("\nAnswer: ") else prompt
            prompt = conversation_prompt(self.tokenizer, [], question, self.context)
        prompt_ids = list(prompt)
        ids = prompt_ids[-self.context:]
        start = perf_counter()
        cache, pending = None, ids
        generated, output = [], []
        rng = np.random.default_rng(settings.seed)
        reason = "limit"
        for _ in range(settings.max_tokens):
            if cancel is not None and cancel.is_set():
                reason = "cancelled"
                break
            values, cache = self.logits(pending, cache)
            values = values[-1].astype(np.float64)/settings.temperature
            values[[PAD, BOS, USER, ASSISTANT]] = -np.inf
            if 0 < settings.top_k < len(values):
                keep = np.argpartition(values, -settings.top_k)[-settings.top_k:]
                masked = np.full_like(values, -np.inf)
                masked[keep] = values[keep]
                values = masked
            values -= values.max()
            p = np.exp(values)
            p /= p.sum()
            token = int(rng.choice(len(values), p=p))
            generated.append(GeneratedToken(token, self.tokenizer.tokens[token]))
            if token == END:
                reason = "stop"
                break
            output.append(token)
            ids.append(token)
            if on_text:
                on_text(self.tokenizer.decode(output).strip(), len(generated))
            if len(ids) > self.context:
                # A sliding window needs positions and cache recomputed together.
                ids = ids[-self.context:]
                cache, pending = None, ids
            else:
                pending = [token]
        text = self.tokenizer.decode(output).strip()
        if on_text:
            on_text(text, len(generated))
        return Result(text, prompt_ids, generated, perf_counter()-start,
                      min(len(prompt_ids), self.context), max(0, len(prompt_ids)-self.context), reason)
