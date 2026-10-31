# lambda 2.5.1 — experimental research skill

Published at the owner's explicit request **despite failing development quality
checks**. This release is the selected refinement step **200**, not the final
step 600. It is not a claim of reliable web answering or improved general reasoning.

## Model

- Own lambda 2.4 base, with all 74 base weight arrays preserved exactly.
- 16,432,550 parameters: 15,350,401 base parameters plus 1,082,149 research parameters.
- Eight Transformer layers, width 384, six heads, 512-token context, vocabulary 2048.
- Learned search classifier, conditional evidence adapters and neural answer-boundary
  and answerability heads. No external pretrained AI or remote language-model API.
- v5 inference format; **Lambda application 0.8.1 or newer is required**.

The public file contains inference arrays and the locally learned tokenizer only.
The private source is the selected `grounded_refine_25` checkpoint at refinement
step 200 (reported lineage step 32550), continued from the own span-reader trial.
Private checkpoint names, optimizer state and datasets are preserved outside this
repository. The previously declined 1024-token `release_25` trial is not published.

## Measured results

All scores below use the exported release weights. Reading scores compare normalized
answers exactly; punctuation and case are ignored. They measure prepared source
contexts, not end-to-end web search accuracy.

| Check | Correct | Accuracy |
| --- | ---: | ---: |
| Synthetic development reading | 19 / 32 | 59.4% |
| Additional authored development contexts | 6 / 8 | 75.0% |
| Separate final reading test | 17 / 48 | 35.4% |
| Development search decisions | 94 / 100 | 94.0% |
| Separate final search decisions | 187 / 200 | 93.5% |

The routing cases include repeated templates and questions; these counts do not
represent 200 unique natural user requests. Development cases were used for
checkpoint selection. Final cases were checked only after that selection, without
weight updates. The original development gate remains **failed**, rather than
being lowered to qualify this release. See the [measurement summary](lambda-2.5.1-benchmark.json).

Two offline generation checks (`Hello` and `What is 5 x 6?`, fixed seed with ordinary
sampling) produced identical output token IDs to 2.4. Exact base-array equality is
the stronger preservation check; the search router may still send a question down
a different path.

## Known failures

The reader can select the wrong entity, an incomplete word or a fragment containing
multiple unrelated facts. One control question returned `ra` instead of its expected
answer. A context lacking the requested fact produced `4.2.1.` rather than uncertainty.
Correct source text does not guarantee a correct answer.

The classifier can fail to search when needed. In one integration probe, `What is the
hottest planet?` stayed offline and produced an unrelated identity response. It did
choose search for a question about the latest Python version. Search availability
also depends on external providers and readable public pages. The small synthetic
benchmarks do not establish general web comprehension, multi-source synthesis or
resistance to instructions embedded in pages.

A live integration run successfully read three public pages, displayed all research
phases and charged the isolated test allowance for actual context/output. Its
answer was a rough span (`3.15 Python 3.15.2`), demonstrating remaining formatting
problems. This network smoke check is not a verified current-version benchmark.

## Use

Run `/update`, restart Lambda after the app upgrade, then:

```text
/model use lambda-2.5.1
```

In F3, choose **lambda 2**, then **2.5.1**, using arrows and Enter. Search is automatic
only for this model; manual `/web` controls and numbered citation cards are absent.
The status shows Searching, Reading and Thinking when those phases occur. The neural
reader predicts an answer span from supplied text; ordinary offline replies use the
unchanged 2.4 base. No application calculator or factual answer table is used.

Queries selected for research are sent to search providers; full chat history stays
local. Source context and decoded output consume the usual shared allowance. Earlier
models and saved local conversations remain available. Existing chats retain their
model until you select the new version inside that chat.
