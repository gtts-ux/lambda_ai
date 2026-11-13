# lambda terra 4.1

Experimental English chat-only continuation of the owner's own **lambda venus
2.4** (legacy ID `lambda-2.4`). No external pretrained model weights, search tools
or programming branch. Published at the owner's explicit request.

| Property | Value |
| --- | --- |
| ID / family | `lambda-terra-4.1` / Terra |
| Parameters | 15,350,401 |
| Architecture | 8-layer, 6-head pointer Transformer, width 384 |
| Context / vocabulary | 512 tokens / 2,048 locally learned UTF-8 byte BPE tokens |
| Selected checkpoint | 2,000 continuation updates; total lineage step 33,650 |
| Runtime | CPU / NumPy float32, v4; app >=0.8.5 |
| Weight license | CC BY-SA 4.0; see attribution below |
| SHA-256 and size | [Inference manifest](lambda-terra-4.1.json) |

## Measured comparison

The same frozen small authored checks were applied to the original 2.4 and the
selected 4.1, with temperature 0.4, top-k 8 and fixed seeds. Marked conversation
histories use each model's own generated prior replies.

| Check | Venus 2.4 | Terra 4.1 |
| --- | --- | --- |
| Development | 23/64 | 61/64 |
| Separate final split | 22/64 | 55/64 |

The final result is **2.5x as many correct responses on this specific check**.
It does not establish 2.5x intelligence or general conversation quality. The
automated rubric checks required concepts, exact literals, repetition and topic
intrusions. It can misgrade semantics. Topic/template families overlap training;
complete prompts, histories and instruction literals are split. The final split
did not select weights. See [actual before/after replies](lambda-terra-4.1-results.json).

Final category scores: facts 31/32, chat 8/8, memory 7/8, topic changes 6/8 and
exact instructions 3/8. The low instruction score is a material limitation.
Unfamiliar wording, names, long conversations and ordinary open-ended questions
can still fail. Generated replies may be nonsensical or repetitive.

## Training and attribution

All model weights descend from the owner's locally initialized 2.4 model.
Full-weight continuation uses 35,320 lessons: authored facts/conversations,
memory after distraction, literal instructions, old training replay and 2,320
short human-authored instructions from **Databricks Dolly 15k**. Repeated authored
templates are not independent knowledge sources. No SQuAD or coding-model weights
are used. Training data, optimizer state and training scripts are not distributed.

Dolly: Databricks, [databricks-dolly-15k](https://huggingface.co/datasets/databricks/databricks-dolly-15k),
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). The training
selection filters short, context-free instructions and adapts the own model.
This release's weights are distributed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), with attribution
and share-alike terms retained. The application and original 2.4 keep their MIT
license; this does not relicense earlier model files. See
[weight license notice](lambda-terra-4.1-LICENSE.txt).

## Use

Run `/update`, restart the app, then `/model use lambda-terra-4.1`.
F3 lists it under **lambda terra**. The shared token allowance and saved local
chats are preserved. Replies come from the neural model; the application does
not substitute factual answers or conversation templates.
