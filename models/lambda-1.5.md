# lambda 1.5

An English model focused on elementary integer arithmetic, trained from random weights.
It uses the same inference format as lambda 1.0 and works with app 0.1.0.

| Property | Value |
| --- | --- |
| Model ID | `lambda-1.5` |
| Parameters | **1,867,520 — exactly 2.5× lambda 1.0 (747,008)** |
| Architecture | Autoregressive MLP, two tanh hidden layers |
| Context | 64 tokens |
| Embedding | 24 |
| Hidden layers | 560 → 560 |
| Vocabulary | 1,184 locally learned BPE tokens |
| Numbers | Individual digit tokens, including inside multi-digit numbers |
| Precision / device | float32 / local CPU |
| Selected checkpoint step | 37,500 |
| Inference file | 6.63 MiB |

## Install and select

```text
/update
/model use lambda-1.5
```

CLI equivalent: `lambda update`, then `lambda model use lambda-1.5`.
Lambda 1.0 remains available. Usage is shared across models and is not reset.

## What was trained

The curriculum covers small integer addition and subtraction, multiplication
tables, exact division, negative subtraction results, simple word problems,
and short English chat. It includes both natural questions and short expressions.
Primary arithmetic ranges are operands 0–20 for addition/subtraction, 0–12 for
multiplication, and quotients 0–12 with divisors 1–12 for exact division.
Additional double/half examples extend those particular cases.

The final curriculum contains 11,153 training math examples
and 2,653 English training examples. Arithmetic operand families
were assigned to training, validation or test before paraphrases were generated.
Commutative additions and multiplications share the same family, so reversing
their operands does not move a held-out problem into training.
Complete one-digit arithmetic tables and corresponding exact-division facts
are intentionally part of training. Held-out operand tests therefore concern
larger combinations, rather than withholding fundamentals such as 2 + 2.

The English material extends the original curriculum described in
[the lambda 1.0 card](../MODEL_CARD.md), including original rule-generated
examples and public-domain English prose. A dialogue rehearsal stage emphasizes
English chat and short mathematical expressions. The vocabulary and weights
were learned locally; no external pretrained model was used.

The runtime generates answers through the neural network. It has no calculator,
arithmetic lookup table, query evaluator or correction step. The exported file
contains inference weights and the tokenizer; no training data or optimizer is shipped.

## Measured arithmetic results

Settings: temperature 0.4, top-k 8, seed 7, at most 48 generated tokens.
Both models receive the same questions. A response must give the exact integer
or a matching equation with that result. Malformed or contradictory responses
count as incorrect. The scorer does not calculate or repair generated answers.

| Test | lambda 1.0 | lambda 1.5 |
| --- | --- | --- |
| Familiar operands, new wording | 1/96 (1.0%) | 64/96 (66.7%) |
| Held-out operand families + new wording | 0/46 (0.0%) | 16/46 (34.8%) |

| Operation, held-out operands | Correct / total |
| --- | --- |
| add | 3/10 (30.0%) |
| sub | 9/24 (37.5%) |
| mul | 1/3 (33.3%) |
| div | 3/9 (33.3%) |

Raw questions, targets and unedited outputs from both models are in
[lambda-1.5-benchmark.json](lambda-1.5-benchmark.json). Its model SHA-256
matches [lambda-1.5.json](lambda-1.5.json). The benchmark is small and
limited to this curriculum. Held-out families refer to the lambda 1.5 split;
lambda 1.0 used its own earlier dataset.

## Limitations

Arithmetic remains fallible, including within the training range. Familiar
patterns can be memorized, and unfamiliar numbers or wording can fail.
This is not a general calculator or a claim of reliable mathematical reasoning.
Check important results independently.

English chat can also be incorrect or nonsensical. There is no conversational
memory, internet access or tool execution. The 64-token context is separate
from the application’s one-million-token allowance.

Code and these inference weights are distributed under the repository’s MIT license.
