"""Inference-only BPE: decode and apply the locally learned merge rules."""

import re

PIECES = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)


class Tokenizer:
    def __init__(self, tokens, merges):
        self.tokens = tuple(tokens)
        self.ids = {token: i for i, token in enumerate(tokens)}
        self.ranks = {tuple(pair): rank for rank, pair in enumerate(merges)}
        self.cache = {}

    def piece(self, text):
        if text in self.cache:
            return self.cache[text]
        try:
            ids = [self.ids[char] for char in text]
        except KeyError as error:
            raise ValueError(f"This model does not support the character {error.args[0]!r}. Try rephrasing your question.") from None
        while len(ids) > 1:
            pairs = list(zip(ids, ids[1:]))
            pair = min(pairs, key=lambda p: self.ranks.get(p, float("inf")))
            if pair not in self.ranks:
                break
            merged = self.ids[self.tokens[pair[0]] + self.tokens[pair[1]]]
            result = []
            i = 0
            while i < len(ids):
                if i + 1 < len(ids) and (ids[i], ids[i+1]) == pair:
                    result.append(merged)
                    i += 2
                else:
                    result.append(ids[i])
                    i += 1
            ids = result
        result = tuple(ids)
        if len(self.cache) < 10000:
            self.cache[text] = result
        return result

    def encode(self, text):
        return [idx for piece in PIECES.findall(text) for idx in self.piece(piece)]

    def decode(self, ids):
        return "".join(self.tokens[int(i)] for i in ids)
