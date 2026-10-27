# lambda 2

A local English model continued from the owner's lambda 1.6. The released file
contains the **trained final state at step 100,000**, with **4,553,728 learned
parameters**. No external pretrained model or text-generation API was used.

| Property | Value |
| --- | --- |
| Model ID / revision | `lambda-2` / 1 |
| Generator / intent head | 4,552,390 / 1,338 parameters |
| Architecture | Mode-conditioned autoregressive MLP, two tanh hidden layers |
| Hidden layers / embedding | 1,024 → 1,024 / 24 |
| Generation context | 80 tokens |
| Question features | Last 64 question tokens; fixed hashed features in chat mode |
| Vocabulary | 1,462 locally learned BPE tokens; individual digits |
| Precision / device | float32 / CPU |
| Additional generator steps | 100,000 |
| Training session duration | About 3 hours 12 minutes on the owner's machine |
| Inference file | 16.15 MiB |
| Format / minimum app | `lambda-ai-inference-v2` / 0.2.0 |

## Install and select

In an existing app 0.2.0+ installation:

```text
/update
/model use lambda-2
```

CLI equivalent: `lambda update`, then `lambda model use lambda-2`.
Older applications need an app upgrade first. Models 1.0, 1.5 and 1.6 remain
available, and lambda 1.0 remains bundled by default. Installing or selecting
lambda 2 preserves the shared one-million-token / ten-hour allowance.

## Training and checkpoint selection

The owner's 1.6 checkpoint at step 25,000 was expanded from hidden width 640 to
1,024. The tokenizer, embedding width and context were retained. Training used
NumPy, the project's manual backpropagation and AdamW, with batches of 40 chat
and 24 arithmetic samples, dropout 0.04 and a peak learning rate of 0.0004.
The owner's existing intent head was also trained locally on labelled questions.

The prepared dataset contains 30,403 distinct normalized questions: 14,265 chat
and 13,965 math training examples, plus 1,545 chat and 628 math validation examples.
It extends the original English definitions, paraphrases, short instructions,
conversation and elementary arithmetic curriculum. Validation rehearses familiar
1.6 facts; it is not evidence of unseen knowledge. No training data, optimizer
state or trainer is included in the published inference file.

The mixed validation objective (65% chat, 35% math) preferred the expanded
**step-0 baseline**, with loss 0.1772. The final trained state had loss 0.2310
(chat 0.0005, math 0.6591). The original automatic export therefore contained
step 0. That file was replaced before publication: this release explicitly uses
`last.npz` at **100,000 updates**, and its checksums identify that trained state.
It is not described as the minimum-validation-loss checkpoint. The separate
raw-output evaluation below records its gains and regressions.

## Measured comparison with lambda 1.6

These are reused development benchmarks, not a new blind test. Both models use
temperature 0.4, top-k 8 and seed 7, with an output cap of 100 tokens for the
40 conversation/intent cases and 48 for the 142 arithmetic cases. The additional
training excludes the exact 40 conversation questions. Topic facts and most
operand patterns are familiar. Answers are generated without calculation tools,
lookup, retrieval or correction.

| Test | lambda 1.6 | lambda 2 |
| --- | --- | --- |
| Chat/math routing | 39/40 (97.5%) | 39/40 (97.5%) |
| Familiar arithmetic operands, new wording | 75/96 (78.1%) | 87/96 (90.6%) |
| Held-out operand families, new wording | 17/46 (37.0%) | 18/46 (39.1%) |

The held-out family label follows the existing arithmetic curriculum split.
The samples are small: held-out multiplication regressed from **1/3 to 0/3**.
Chat containing digits still sometimes produces a number-only reply: **3/15**
cases for lambda 2, versus **2/15** for 1.6, even with correct intent routing.
The classifier's score measures intent, not answer truth or fluency.

All questions, expected arithmetic results and unedited responses from both
models are in [lambda-2-benchmark.json](lambda-2-benchmark.json). Its per-model
SHA-256 matches [lambda-2.json](lambda-2.json). The report also retains a narrow
topic-keyword proxy; that proxy is not a semantic correctness score.

## Limitations

More training and a larger network do not guarantee better answers. Unfamiliar
wording can still produce unrelated, broken or numerically incorrect text.
For example, `Tell me who you are.` can return a definition of a noun, and
`Could you describe a 2D shape for me?` can return `8.`. Arithmetic outside
familiar patterns remains unreliable. Check important answers independently.

Each question is processed separately. There is no conversation memory, live
internet lookup or tool execution. Chat never changes weights. Code and these
inference weights use the repository's MIT license.
