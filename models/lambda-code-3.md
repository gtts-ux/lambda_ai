# lambda code 3

Experimental English conversation and beginner Python/JavaScript generation,
published at the owner's explicit request. It can still generate malformed code,
wrong values, repetitions or incomplete code fences and mishandle history.
It is not a general-purpose coding assistant.

| Property | Value |
| --- | --- |
| ID | `lambda-code-3` |
| Parameters | 17,029,797 |
| Base | Own frozen lambda 2.4, checked for exact array equality |
| Coding | Conditional rank-32 adapters in all eight blocks and pointer layers |
| Routing | Learned chat / Python / JavaScript classifier |
| Context / vocabulary | 512 tokens / 2,048 locally learned UTF-8 byte BPE tokens |
| Runtime | CPU / NumPy float32, v6 format; app >=0.8.4 |
| Selected update | Repair 11,500; total lineage step 53,150 |
| File | `lambda-code-3.npz`, 63,313,878 bytes |
| SHA-256 | `3c273e8aec9eee7e6a9f7c6b0b96f8454724f643eb634837b936793c063f01ee` |
| Search | Disabled |
| Weight license | MIT, like the own 2.4 base |

## Training and scope

Initialization uses only the owner's own 2.4 weights, descending from local random
initialization. No external pretrained model or tokenizer is used. The original
coding trial had 3,245 authored lessons in 20 narrow task families. The repair
continued its selected update-10000 checkpoint with 22,180 lessons, about 81% with
prior chat/code turns. These include malformed earlier replies, varied print
requests, retained elementary coding tasks and requests requiring clarification.
Copy attention receives offline supervision toward literals in the current request.
The application does not substitute answer templates or execute generated programs.

Ordinary conversation uses the frozen own 2.4 base when the classifier chooses
chat; misclassification can still alter replies. Unspecified simple coding lessons
use Python as the taught default. Language classification alone does not guarantee
correct code. This coding path does not use the SQuAD/Dolly research experiments
or their weights. Those optional research models retain their separate licenses.
Training data, checkpoints and optimizer state are not included in the release.

## Results and limitations

The final check used 78 authored cases with complete question/history inputs
distinct from training and development. Many tasks share template families, so this
is a narrow benchmark, not HumanEval or proof of arbitrary program synthesis.
Python is compared by parsed AST; JavaScript conservatively against the expected
snippet. Generated programs are not run.

| Final category | Greedy | Normal app sampling (top-k 8, temperature 0.4) |
| --- | --- | --- |
| Retained elementary coding | 35/44 (79.5%) | 36/44 (81.8%) |
| New print requests | 12/22 (54.5%) | 12/22 (54.5%) |
| Clarification | 5/12 (41.7%) | 5/12 (41.7%) |

Six screenshot regressions passed in both settings. They were included in repair
training and are **not unseen tests**. Four conversation probes matched own 2.4;
all exported base arrays were identical. Its original limitations remain.
See [actual generated answers](lambda-code-3-results.json), including failures.
Routing probabilities do not measure code correctness. Review generated code
before using it; strings, syntax and follow-up requests remain unreliable.

## Install

Run `/update` and restart after the app upgrade, then:

```text
/model use lambda-code-3
```

F3 lists it under **lambda code**. Starting prompts include:

```text
make a code in python printing hello
Write JavaScript code that prints "Hello Janek".
Write a Python function named add that returns the sum of a and b.
```

Fenced code is colored gold. Coloring is presentation, not code validation.
The shared 1,000,000-token / 10-hour allowance is unchanged.
