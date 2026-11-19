# lambda terra 4.1 — revision 2

Published under the owner's requested name **lambda terra 4.1**, without “demo”.
This is still an **experimental** model; the name is not a quality certification.
It is a different own-weight lineage from the older public Terra demo and is not
a relabelled demo file. Existing demo and legacy files remain immutable.

34,819,200 parameters, 8 Transformer blocks, width 576, 4096-token locally trained
byte BPE and 1024-token context. Own random-weight foundation, own conversation
continuations and the retention-selected chat/math repair update 7000, total
47462. No external pretrained model or tokenizer, no app calculator or canned
answers. Optional download; requires core 0.9.1 / Desktop 1.2.1 for this release.

## Measured limitations

The completed repair's final constrained test scored 11/21 on identity/roles/age/
unknown-information repairs and **3/51 on arithmetic**. Exposed old conversation
regressions scored 23/26, with no loss among the source's known-correct fixed cases.
These are small diagnostic sets, not general chat benchmarks. They do not establish
twice the capability of Venus 2.4 or reliable arithmetic.

A fresh six-conversation release smoke test produced a correct greeting and
identity, but failed a new name recall, a topic return and multiplication; literal
copying was incomplete. All 13 replies stopped naturally within the 96-token cap.
Natural stopping does not make those answers correct. Open responses may remain
short, incoherent or factually wrong. There is no automatic web search or coding
branch. The application's separate learned image-request head can open Orion's
Image Playground; it does not teach this chat model image understanding.

## Provenance and distribution

Foundation text: **TinyStories**, Ronen Eldan and Yuanzhi Li,
https://huggingface.co/datasets/roneneldan/TinyStories , revision
`f54c09fd23315a6f9c86f9dc80f725de7d8f9c64`, V2 GPT-4 train/validation text,
CDLA-Sharing-1.0. Only text was used; tokenizer and weights were learned locally.
Conversation text: **OASST2**, LAION/OpenAssistant and contributors,
https://huggingface.co/datasets/OpenAssistant/oasst2 , Apache-2.0, revision
`179dd21fc55192153d94adb0e0ce8f69e222bf75`; **Dolly 15k**, Databricks,
https://huggingface.co/datasets/databricks/databricks-dolly-15k , CC BY-SA 3.0.
Selected English paths/short instructions were repacked with the new tokenizer
and combined with authored conversation, copying, topic-return and arithmetic
lessons and own language replay. Original datasets retain their own terms.

Inference weights: CC BY-SA 4.0, Lambda AI project contributors / gtts-ux.
See [notices](lambda-terra-4.1-r2-NOTICES.txt). Application code remains MIT.
No training scripts, datasets, optimizer or private conversations are distributed.
Only release metadata changes from the preserved selected artifact; all numerical
tensor members and the learned tokenizer are byte-identical to that source.

Source inference SHA-256:
`d327fd536ff1550d85fd50a20872c4b6a296c5ecd7173bd57cd53ceab4ac9c0b`.
Release: `lambda-terra-4.1-r2.npz`, 129,449,855 bytes, SHA-256
`810baa43b5a2a10b4643ca5288d0694653b0c3d893f28a5f080c02f3cd5acad5`.
