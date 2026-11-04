# lambda 2.5.2 — generative reading snapshot

An owner-requested experimental snapshot taken while the longer lambda 2.5 training
continues. It contains the best inference export available at capture: **8500 new
updates**, reported lineage step 40150. Selection used mean local development loss
on source QA, natural instructions and conversation replay. A lower loss does not
establish better reasoning or reliable web comprehension.

The running trainer and its best/last checkpoints were not modified. The inference
archive was read once from its atomic export, pinned privately, and renamed through
metadata only. Every inference array matches that snapshot exactly.

## Architecture and data

16,235,172 parameters; eight layers, width 384, six heads, 512-token context and
2048-token vocabulary. Own lambda 2.4 initializes the base. Unlike 2.5.1, the base
is trainable and the evidence-conditioned decoder generates answers token by token.
It does not use the earlier answer-span decoder. Search routing reuses the own
2.5.1 classifier and remains fallible. No external pretrained model weights or
remote text-generation API are used.

The private prepared training split has 109395 reading examples, 5668 natural
instructions and 36166 replay examples. Long examples are filtered to fit context.
Local reading development data are split by article; instructions/replay by question
hash. These are local splits, not official SQuAD leaderboard scores.

Data attribution:

- **SQuAD 2.0**, Pranav Rajpurkar, Robin Jia, Percy Liang and contributors.
  [Dataset and paper](https://rajpurkar.github.io/SQuAD-explorer/).
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Databricks Dolly 15k**, Databricks and its contributing employees.
  [Original dataset and documentation](https://huggingface.co/datasets/databricks/databricks-dolly-15k).
  [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
- Owner's existing Lambda conversation replay.

The new **2.5.2 inference weights are distributed under CC BY-SA 4.0** with these
attributions. Training filters, tokenization and model adaptation are modifications.
Keep the attribution, license links and modification notice on redistribution.
The application code and earlier model releases retain their existing licenses.
No training dataset or optimizer state is included in this release.

## Results and limitations

See [actual generated outputs](lambda-2.5.2-results.json). This is a small descriptive
check rather than an accuracy benchmark. Responses may be incorrect, repetitive or
unsupported by the evidence. A 512-token window holds only short excerpts; retrieval
can omit relevant facts. Source QA training does not establish multi-page synthesis
or protection against instructions inside retrieved pages. The router can miss
questions needing search. Earlier model behavior may regress because the base is
now trainable. This mid-training release has not passed a broad quality gate.

## Install

Requires **application 0.8.2** for automatic search under the new name. Run `/update`,
restart Lambda after the application update, then:

```text
/model use lambda-2.5.2
```

F3 lists it under lambda 2. Search is automatic; the chat displays the neural answer
and research progress. Queries selected for search go to search providers; ordinary
chat history stays local. Source context and generated output use the shared token
allowance. Existing conversations retain their selected model until changed.
