"""UTF-8 byte BPE with explicit role tokens; inference only."""
import re

SPECIAL = ("<pad>", "<bos>", "<user>", "<assistant>", "<end>")
PAD, BOS, USER, ASSISTANT, END = range(5)
PIECES = re.compile(r"[^\W\d_]+|\d|\s+|[^\w\s]|_", re.UNICODE)


class ByteTokenizer:
    def __init__(self, config):
        if config.get("type") != "lambda-byte-bpe-v1":
            raise ValueError("Unsupported byte tokenizer.")
        self.byte_tokens = [bytes.fromhex(x) for x in config["bytes"]]
        if self.byte_tokens[:256] != [bytes([i]) for i in range(256)]:
            raise ValueError("The tokenizer must cover all UTF-8 bytes.")
        self.merges = [tuple(p) for p in config["merges"]]
        if len(self.byte_tokens) != 256 + len(self.merges):
            raise ValueError("Invalid BPE vocabulary size.")
        for i, pair in enumerate(self.merges, 256):
            if len(pair) != 2 or any(type(x) is not int or not 0 <= x < i for x in pair):
                raise ValueError("Invalid BPE merge.")
            if self.byte_tokens[pair[0]] + self.byte_tokens[pair[1]] != self.byte_tokens[i]:
                raise ValueError("Invalid BPE merge bytes.")
        self.ranks = {p: i for i, p in enumerate(self.merges)}
        if len(self.ranks) != len(self.merges):
            raise ValueError("Duplicate BPE merge.")
        self.tokens = list(SPECIAL) + [repr(b)[2:-1] for b in self.byte_tokens]
        self.cache = {}

    @staticmethod
    def merge(ids, pair, joined):
        result, i = [], 0
        while i < len(ids):
            if i+1 < len(ids) and (ids[i], ids[i+1]) == pair:
                result.append(joined)
                i += 2
            else:
                result.append(ids[i])
                i += 1
        return tuple(result)

    def encode(self, text):
        output = []
        for piece in PIECES.findall(text):
            if piece not in self.cache:
                ids = tuple(piece.encode("utf-8"))
                while len(ids) > 1:
                    pair = min(zip(ids, ids[1:]), key=lambda p: self.ranks.get(p, float("inf")))
                    if pair not in self.ranks:
                        break
                    ids = self.merge(ids, pair, 256+self.ranks[pair])
                if len(self.cache) > 50000:
                    self.cache.clear()
                self.cache[piece] = tuple(i+len(SPECIAL) for i in ids)
            output.extend(self.cache[piece])
        return output

    def decode(self, ids):
        return b"".join(self.byte_tokens[int(i)-len(SPECIAL)] for i in ids
                        if int(i) >= len(SPECIAL)).decode("utf-8", errors="replace")

    def to_dict(self):
        return {"type": "lambda-byte-bpe-v1", "bytes": [b.hex() for b in self.byte_tokens],
                "merges": [list(p) for p in self.merges]}


def conversation_prompt(tokenizer, turns, question, context):
    """Keep whole recent exchanges; clip only a single oversized current question."""
    current = [USER] + tokenizer.encode(question) + [END, ASSISTANT]
    # Leave room for BOS, even for very long user input.
    if len(current) > context-1:
        current = [USER] + current[1:-2][-(context-4):] + [END, ASSISTANT]
    blocks = []
    used = 1 + len(current)
    for q, a in reversed(turns):
        block = [USER] + tokenizer.encode(q) + [END, ASSISTANT] + tokenizer.encode(a) + [END]
        if used+len(block) > context:
            break
        blocks.append(block)
        used += len(block)
    return [BOS] + [i for block in reversed(blocks) for i in block] + current
