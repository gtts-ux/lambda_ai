"""Learned pointer-generator output distribution. No question or answer rules."""
import numpy as np
from .transformer import TransformerEngine, POINTER_FORMAT, norm


def softmax(values):
    values = values - values.max(axis=-1, keepdims=True)
    result = np.exp(values)
    return result / result.sum(axis=-1, keepdims=True)


class PointerEngine(TransformerEngine):
    supported_format = POINTER_FORMAT

    def info(self):
        result = super().info()
        result["architecture"] += " · learned pointer-generator"
        return result

    def logits(self, ids, cache=None):
        ids = np.asarray(ids, dtype=np.int64)
        h, base_cache = self.hidden_states(ids, cache["base"] if cache else None)
        w = self.weights
        e = norm(w["token"][ids], w["pointer_norm_w"], w["pointer_norm_b"])
        features = np.concatenate((h, e), axis=-1)
        q, k = features @ w["pointer_q"], features @ w["pointer_k"]
        all_ids, all_h = ids, h
        start = 0
        if cache:
            start = len(cache["ids"])
            k = np.concatenate((cache["k"], k))
            all_h = np.concatenate((cache["h"], h))
            all_ids = np.concatenate((cache["ids"], ids))
        scores = q @ k.T / np.sqrt(q.shape[-1])
        future = np.arange(len(all_ids))[None, :] > (start + np.arange(len(ids)))[:, None]
        # Ordinary causal attention, including role tokens. Roles are never answers.
        attention = softmax(np.where(future, -np.inf, scores))
        attended = attention @ all_h
        gate_logits = np.concatenate((h, attended, e), axis=-1) @ w["pointer_gate_w"] + w["pointer_gate_b"]
        gate = 1 / (1 + np.exp(-np.clip(gate_logits, -80, 80)))
        copied = np.zeros((len(ids), len(self.tokenizer.tokens)), dtype=np.float32)
        for i in range(len(ids)):
            np.add.at(copied[i], all_ids, attention[i])
        probabilities = (1-gate) * softmax(h @ w["token"].T) + gate * copied
        next_cache = {"base": base_cache, "k": k, "h": all_h, "ids": all_ids}
        return np.log(np.maximum(probabilities, np.finfo(np.float32).tiny)), next_cache
