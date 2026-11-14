# lambda terra 4.1 demo

Public experimental English chat demo, explicitly requested by the owner. This is
the preserved **update-4000** snapshot of the 35M continuation, matching the
numerical weights of the owner's previous private demo. It is not a qualified
production release. It replaces the old Terra 4.1 offering in model choices;
legacy files remain available for existing saved conversations.

| Property | Value |
| --- | --- |
| ID / family | `lambda-terra-4.1-demo` / Terra |
| Public revision | 2; revision 1 was the owner's private demo |
| Parameters | 35,028,097 |
| Architecture | 19 residual blocks, width 384, 6 heads, learned pointer width 256 |
| Context / vocabulary | 512 tokens / 2,048 locally learned UTF-8 byte BPE tokens |
| Selected update / total lineage step | 4,000 / 63,650 |
| Runtime | CPU / NumPy float32, v4; terminal engine >=0.8.6 |
| Desktop compatibility | Desktop app 1.1.0+; refresh the model list in Settings |
| Tools | Offline conversation; no web-search or programming branch |
| Download / checksum | [Release assets](https://github.com/gtts-ux/lambda_ai/releases/tag/model-terra-4.1-demo-r2), [inference manifest](lambda-terra-4.1-demo.json) |
| Weight license | CC BY-SA 4.0; application software remains MIT |

## Measured results and limits

The same ten exposed development conversations (60 graded replies, using each
model's own generated history) were used to compare the selected snapshot:

| Model | Correct development replies |
| --- | --- |
| Venus 2.4 | 22/60 |
| Starting checkpoint for this continuation | 33/60 |
| Selected update 4000 | 43/60 |

These are development/selection results, not an independent unseen final test.
The selected snapshot lost **19 previously correct retention cases** and produced
**7 new degenerate outputs** in the retention checks. It did not pass the original
release gates or the complete twofold goal. It is published as a demo at the
owner's request despite those failures. Do not interpret these counts as twice
the intelligence, reliable normal conversation or guaranteed memory.

Replies can still be incorrect, repetitive, nonsensical or lose facts from the
conversation. Later updates did not automatically replace these selected weights.
No training/optimizer state, private user chats or application-side answer
templates are included. Every assistant reply comes from the neural model.

## Lineage and attribution

All weights descend from the project's own randomly initialized Lambda lineage;
no external pretrained model weights are used. This continuation starts from the
preserved dialogue checkpoint at total step 59,650, expands to 19 blocks and pointer
width 256, and trains on authored dialogue/replay plus filtered short English
human-authored OASST1 conversations. Source arrays were transferred with
probability-preserving residual/pointer initialization before continuation.

Inherited human-data attribution: **Databricks Dolly 15k**, Databricks,
[dataset](https://huggingface.co/datasets/databricks/databricks-dolly-15k),
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Selected short,
context-free human instruction/response pairs were used in the earlier own Terra
lineage. The original Venus 2.4 and application MIT notices remain unchanged.

Additional human-data attribution: **OpenAssistant Conversations Dataset
(OASST1)**, LAION/OpenAssistant and contributors,
[official dataset](https://huggingface.co/datasets/OpenAssistant/oasst1), Apache
License 2.0, revision `fdf72ae`, `2023-04-12_oasst_ready.trees.jsonl.gz`.
Verified upstream SHA-256:
`2a9a8fd343e9b28e04a895a669d3253f82d93e9c174d440199ae19d5fafbdff7`.
Only filtered short English human conversation paths were used; synthetic/model
nodes were excluded. This is text training data, not another model or AI service.

Weights are distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
Retain attribution/share-alike terms and the [license notices](lambda-terra-4.1-demo-LICENSE.txt).
This does not relicense old artifacts or the MIT application.

## Install

In Desktop app 1.1.0+, open **Settings → Models → Refresh list**, then download
**Terra 4.1 demo** and choose it in the chat model picker. Downloads are optional
and validated before installation. The old Terra 4.1 is no longer offered there.

In the terminal, update/restart the app and run:

```sh
lambda model use lambda-terra-4.1-demo
```

Or use `/update`, then `/model use lambda-terra-4.1-demo` in chat. Existing local
conversations and the shared token allowance remain intact. Previously installed
legacy Terra 4.1 files can still reopen their saved conversations.
