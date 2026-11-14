# Lambda AI maintenance instructions

- The app, its UI, documentation, default prompts and bundled model must be English.
- On 2026-10-29 the owner requested fixing the recorded conversation failures and
  publishing the result as **lambda 2.2** (`lambda-2.2`). Keep the old releases and
  checkpoints. Compare real generated conversations before release, including the
  application's default sampling; report remaining failures honestly. The private
  `../conversation_training/release_22` continuation trains all layers of the owner's
  own 2.1 weights. No external weights or application-side answer substitution.
  The owner subsequently explicitly said to publish 2.2 even if it does not meet
  quality expectations. This supersedes performance gates for this release only;
  still finish technical validation and disclose actual scores and remaining errors.
- The approved model names are **lambda 1.0** (`lambda-1.0`),
  **lambda 1.5** (`lambda-1.5`), **lambda 1.6** (`lambda-1.6`), **lambda 2** (`lambda-2`),
  **lambda 2.1** (`lambda-2.1`), **lambda 2.2** (`lambda-2.2`), and **lambda 2.4** (`lambda-2.4`).
- Lambda 2 has 4,553,728 parameters and uses the compatible v2 format (app >=0.2.0).
  Release its trained step-100000 checkpoint; the old step-0 export is not the release.
- Lambda 1.6 has exactly 2,614,528 parameters including its learned intent head;
  its v2 inference format requires app 0.2.0 or newer. Keep v1 models supported.
- The owner will supply the name of every future model. If a new model is requested
  without a name, ask the owner before assigning or publishing one. Never invent a name.
- A private conversation-training kit is prepared in `../conversation_training`.
  Its 11,609,856-parameter Transformer originally started from random weights.
  The owner approved **lambda 2.5** (`lambda-2.5`) on 2026-10-28 for a repair experiment.
  The owner explicitly authorized starting that repair and conditional publication
  after quality checks, without waiting in Codex. Preserve the original main run.
  Local app 0.3.0 supports its v3 NPZ export and recent conversation context.
  Automatic publication requires the documented gates. The explicit owner-requested
  experimental lambda 2.1 release is the exception documented below.
  The owner trains independently in resumable sessions; preserve all checkpoints.
- The failed repair remains local. A separate neural-only `../conversation_training/language_pilot`
  experiment uses the owner's final repair weights (7000 + 12000 source updates),
  shared instruction vocabulary with held-out full combinations, and fresh test names.
  It is capped at 1000 new updates / 25 minutes, with a before/after comparison.
  Do not silently extend it into another long run or lower publication thresholds.
- After the owner's request for a broader neural-only improvement, `attention_pilot`
  adds training-only supervision of existing attention heads, copy exercises,
  recovery from earlier mistaken assistant replies and worked arithmetic examples.
  It adds no inference parameters or answer rules. The existing v3 export is unchanged.
  First progress gate: 1000 steps; extend only after measured copy/memory gains with
  retained skills, to at most 3000 steps / 60 minutes. Preserve every earlier run.
- Do not ship training scripts, training data or optimizer state in this repository.
  After the failed attention-only trial, the owner authorized inspecting and fixing it.
  The private `pointer_pilot` uses new randomly initialized neural pointer/gate weights
  with the own step-20500 backbone frozen for the entire trial. Its v4 inference is a
  learned probability distribution, with no question parsing or answer substitution.
  App 0.4.0 supports both v3 and v4. Keep the failed attention run intact. A separate
  bounded trial stops at 1000 unless copy/memory gains and prior skills pass the same
  progress gate; maximum 3000 updates / 60 minutes. Publication thresholds stay unchanged.
  Only inference weights and their locally learned tokenizer belong in the app bundle.
- The subsequent owner-authorized `joint_pilot` trains the existing v4 pointer and
  last two Transformer blocks with an own frozen replay checkpoint as a training-only
  distillation teacher. It uses a short-to-long copying curriculum; inference is still
  one neural model. Preserve previous trials. Same 1000-step progress gate and
  maximum 3000 updates / 60 minutes, with unchanged publication thresholds.
- The owner then authorized a different data strategy in `conversation_pilot`, starting
  from the best own joint checkpoint at total step 22250. It adds clean intermediate
  turns, topic changes, recall after distraction and balanced factual examples.
  Context stays 512; no inference rules are added. Maximum 3000 updates / 60 minutes,
  with a documented progress check at 1500 on the best saved candidate. Release
  thresholds remain unchanged; preserve all prior runs.
- The owner requires every answer to come from their neural model. Do not substitute
  calculator output, canned replies, retrieval answers or a different model selected
  by topic. Conversation history may be supplied as input context. Correct labels may
  be computed offline to create training data; never use that computation to answer a
  live user question. No external pretrained model weights are authorized.
- Preserve the per-OS-user 1,000,000-token allowance and 10-hour reset, shared across
  sessions, CLI entry points and model choices. Do not add a user-facing reset command.
- Validate every model download with size, SHA-256 and the supported inference format.
  Keep the previous working model if validation fails.
- Keep `models/catalog.json` and `lambda_cli/assets/catalog.json` identical.
- Run `python -m unittest discover -s tests -v` and build a wheel before publishing changes.
- Repository: https://github.com/gtts-ux/lambda_ai . Do not force-push shared branches.

- Latest owner instruction: publish the best preserved 2.5 trial as **lambda 2.1**
  (`lambda-2.1`). This explicit request supersedes the earlier 2.5 name and conditional
  publication requirement for this release only. Publish as experimental, keep the
  failed quality-gate results truthful, and do not claim universal superiority to 1.6.
  It requires v4/app >=0.4.0. Future model names still come from the owner.

- The owner requested a richer terminal UI and `/update` for application code as well
  as models. App 0.5.0 adds an always-visible remaining-quota bar, F5 Updates, and
  checksum-verified wheel updates from `releases/app.json`. Keep versioned wheels
  immutable; use `tools/publish_app.py` after tests/build. A restart loads new code;
  on Windows the installer waits for the running launcher to exit. Do not clear
  conversation memory on a catalog-only refresh or alter the shared quota.
- Before publishing 0.5.0 the owner also requested persistent local conversations.
  Interactive sessions now autosave to `chats.sqlite3`; F6 and `/chats` browse them,
  `/chat <number or id>` restores text/model/settings and `/new` preserves the old
  chat. Saved text is model input context, never a substitute answer or training.
  Keep the chat database out of git and app wheels. `lambda ask` remains standalone.

- The owner's latest model-release instruction is **lambda 2.4** (`lambda-2.4`),
  superseding the private 2.3 working name. Publish the selected step-7000 checkpoint
  from `../conversation_training/runs/release_23/best.pt` (total step 31650), not the
  final step-8000 weights. Preserve private run files and their historical names.
  It has 15,350,401 parameters, 8 layers, v4 format and 512-token context. App 0.5.1
  raises the checked download budget to 64 MiB for this model; require >=0.5.1.
  Keep all earlier named models available. Training data/optimizer remain private.

- On 2026-10-30 the owner named the next model **lambda 2.5** (`lambda-2.5`).
  Private `../conversation_training/release_25` continues the selected own 2.4
  checkpoint, expands learned positions from 512 to 1024 and adds authored natural
  conversations, worked arithmetic, replay and long-context fixtures. No external
  pretrained weights or live answer rules. Keep previous checkpoints and releases.
  Prepare, verify and launch a bounded resumable background run; do not keep a Codex
  turn waiting for training. Do not list an untrained model in the public catalog.
- App 0.6.0 groups F3 model choices by family/version with arrow navigation. F6 adds
  local text search and pinning. Edits/regenerations create separate saved branches,
  exclude subsequent turns from the revised prompt and charge actual tokens normally.
  Keep the legacy chats table compatible; pins use a separate table. Preserve chats,
  model bindings and the shared quota. The owner excluded the proposed comparison UI.

- On 2026-10-31 the owner explicitly said NOT to publish the failed `release_25`
  training trial. Its publication_policy.json remains authoritative for those weights.
  The subsequent request is a web-search skill for a future lambda 2.5, with visible
  search/read/generation progress. App 0.7.0 implements an explicit opt-in reader,
  source excerpts and experimental model generation. The model probe failed grounded
  answering; do not claim reliable synthesis or rename 2.4 weights as a trained 2.5.
  Source evidence stays distinct from the neural answer. No other pretrained AI,
  canned answer or application calculator is authorized. Offline mode stays default.
- The owner requested an English-narrated, English-captioned TikTok-format MP4 demo
  on their Desktop after this work. Generate the file only; do not upload to TikTok.

- Latest owner instruction (2026-10-31): no conversational approval questions for
  routine authorized work in this chat. Continue autonomously; environment-enforced
  permission requirements still apply. The name lambda 2.5 is already supplied.
- App 0.8.0 supersedes the manual 0.7 web preview: remove /web, /read, /sources,
  --web, the Web tab/toggle and citation/excerpt cards from ordinary chat. Only
  lambda-2.5 with the v5 learned router may search automatically. Restore old saved
  chats without honoring their legacy web_enabled flag. Older models stay offline.
- New private `grounded_span_25` trains new evidence adapters, neural answer-boundary
  heads and search routing on the frozen own 2.4 base. A separate `grounded_25`
  autoregressive attempt failed development checks; preserve its files and do not
  release it. Old `release_25` publication prohibition also remains in force.
  Neural answer boundaries are model predictions, not application answer selection.
  No hardcoded factual answers, app calculator or external pretrained AI is allowed.
  Preserve exact baseline arrays and perform source-reading/routing checks before
  registering any new 2.5 file. Do not claim arbitrary web comprehension from a
  small synthetic development set. Training runs are bounded and resumable.
- The owner clarified that 2.5 means **2.4 plus the research skill**. Preserve the
  exact 2.4 base arrays and 512-token context. The separate `grounded_refine_25`
  continuation varies source grammar and missing-property examples, starting from
  `grounded_span_25/best.pt`. It is capped at 600 updates / 20 minutes per session;
  do not automatically publish it or extend training without reviewing its results.
- Latest owner instruction: publish the selected `grounded_refine_25` step-200
  weights as **lambda 2.5.1** (`lambda-2.5.1`) despite the reviewed development
  failure. This explicitly overrides performance gates for this release only.
  Preserve the failed results and all private checkpoints; do not resume training.
  Publish as experimental, with the frozen 2.4 base and learned research skill.
  App 0.8.1 enables automatic research only for lambda-2.5.1 in v5 format.
  Finish technical checks, document measured failures, preserve older models,
  chats and usage, and keep training/optimizer data out of the public repository.
- On 2026-11-04 the owner requested a new **lambda 2.5** (not 2.5.1), with more
  coherent conversation and better use of internet evidence, allowing a larger
  training effort and requesting a Desktop demo video at completion. Private
  `understanding_25` continues own 2.4 weights with trainable base and generative
  evidence adapters, natural Dolly instructions, SQuAD 2.0 reading/abstention and
  own conversation replay. Preserve public 2.4/2.5.1 unchanged. The earlier
  frozen-base rule applies to the already released 2.5.1, not this new trial.
  Preserve downloaded data attribution/licensing in its SOURCES.md. A bounded
  resumable background session creates an English narrated/captioned video of
  actual outputs after training; never fabricate successful conversations.
  Model quality must be measured before claiming improvement. This request does
  not authorize automatic publication of a failed candidate under the old waiver.
- The owner now explicitly requests publishing a snapshot of the current best
  `understanding_25` inference weights as **lambda 2.5.2** (`lambda-2.5.2`),
  without interrupting training. Read the atomically replaced best.npz once and
  pin that copy; never read optimizer state or modify the running trainer.
  App 0.8.2 enables the new identity. This is an experimental mid-training release,
  not proof of improved reasoning. Preserve source-data attribution and share-alike
  terms for this model separately from the MIT application and previous weights.
- On 2026-11-11 the owner requested improving research use and preventing loops.
  The project moved to Desktop/Janek/lambda_ai. `reading_repair` verifies train/export
  parity and trains source-only neural copy attention plus unlikelihood on authored
  reading lessons, preserving the own 2.4 offline base. The source_pointer_only
  metadata flag requires matched train/runtime masking and future app >=0.8.3.
  Keep earlier releases unchanged. Cap 2000 updates / 90 minutes; measure generated
  answers every 250 updates, label previously exposed cases as development, and
  require independent checks before publication. No automatic long extension.
- On 2026-11-12 the owner explicitly authorized a new roughly five-hour effort.
  `reader_25` supersedes the failed reading_repair trial for this new run only:
  260 minutes plus final checks, no automatic step-1000 progress stop. It learns
  bidirectional evidence adapters and source-span boundaries on own frozen 2.4,
  authored multi-fact lessons and SQuAD 2.0 (CC BY-SA 4.0). No external weights.
  `bidirectional_reader` applies only during neural span encoding, never causal
  generation/caching. Require train/runtime parity and app >=0.8.3 on release.
  Preserve the old checkpoints, installed model, chats and quota. Finish with
  selected local weights and an honest held-out Desktop report, not automatic
  publication or claims that extractive reading equals general synthesis.
- Latest owner request (2026-11-12): the next model is **lambda code 3**
  (`lambda-code-3`), with no web search. Add beginner Python/JavaScript, learned
  code/language recognition (including “do a hello world”), preserve ordinary
  lambda 2.4 behavior, and color fenced code distinctly. Private `code_3` trains
  new conditional adapters and a three-class learned router on the frozen own
  2.4 base. No external pretrained weights or application code-answer templates.
  v6/app >=0.8.4 supports these local inference weights. Bound training to 16000
  updates / 240 minutes; checkpoint and evaluate actual generated snippets,
  retain a held-out final report. No automatic installation/publication of
  unreviewed weights. The terminal changes are available locally after restart.
- The owner then requested a local snapshot of the running coding model named
  **lambda 3 code demo** (`lambda-code-3-demo`), without stopping training. Pin
  the atomically exported best inference artifact once; never modify the worker,
  optimizer or original code_3 checkpoints. The local snapshot captured update
  9000, retains identical numerical arrays and requires app >=0.8.4. Keep the
  final running model's approved name lambda code 3. No GitHub publication was
  requested for this local demo. Snapshot records live in ../diagnostics/code_demo_snapshots.
- After reproducing corrupted multi-turn coding replies, the owner explicitly
  authorized stopping the old training and starting a corrected one. Old code_3
  safely paused at update 10713. `code_3_conversation` pins its own selected
  update-10000 checkpoint, continues coding adapters with chat/code histories,
  current-request literal copy supervision, varied print requests and learned
  clarification. Preserve frozen 2.4 arrays and the immutable installed demo.
  Cap the new run at 12000 updates / 180 minutes plus final checks. Selection
  must include actual multi-turn outputs with default sampling, not only fresh
  greedy prompts. Exposed screenshot regressions do not count as unseen tests.
  No application answer substitution, automatic publication or budget extension.
- The owner requested replacing the local demo with the current best ongoing
  conversation-repair snapshot. Installed local revision 2 of lambda-code-3-demo
  captures code_3_conversation update 3500 (total step 45150), retaining the
  previous demo file and snapshot record. Training continues unchanged; this
  is a local owner-requested replacement, not public publication or proof of
  reliable arbitrary coding. Preserve each pinned artifact as an immutable file.
- Latest local demo replacement: the owner requested the completed run's best
  weights as the same lambda 3 code demo. Local revision 3 captures
  code_3_conversation update 11500 (total step 53150), with the previous revision
  preserved. Search remains disabled. Final held-out default-sampling results:
  retention 36/44, novel print 12/22, clarification 5/12; exposed regressions 6/6.
  This local experimental installation is not a public release or a reliability claim.
- Owner portability requirement (2026-11-12): future app updates/installers must
  never embed the maintainer's personal home or Desktop checkout paths.
  The repaired ~/.local/bin/lambda wrapper with that absolute project path is
  local to this computer and must not be copied into GitHub, wheels, installers
  or update payloads. Resolve each user's installation location dynamically;
  retain the pyproject console entry point and the installer's derived root,
  HOME/LAMBDA_BIN_DIR-based launcher location. App updates use the active
  environment's sys.executable. Do not make other devices depend on this checkout.
- Latest owner instruction: publish the completed selected weights as **lambda
  code 3** (`lambda-code-3`), superseding the demo identity for this public release.
  Use code_3_conversation update 11500 / total step 53150. Keep older releases,
  demo files, chats and quota. Publish app 0.8.4 with v6 support, code colors,
  code-family browsing and local-model metadata fixes. Document actual scores
  and trained-on screenshot regressions. Do not ship private training files or
  machine-specific launcher paths. This explicit publication request supersedes
  the earlier no-automatic-publication instruction for this selected artifact.
- Owner request (2026-11-13): **lambda 4.1** (`lambda-4.1`) is a chat-only own
  2.4 continuation; no research tools or coding branch. Train toward twice as
  many correct responses on frozen authored checks, not a claim of twice the
  intelligence. Private ../conversation_training/chat_41 uses full-weight low-LR
  continuation, authored multi-turn lessons, old replay and a small Dolly subset.
  Keep data attribution/share-alike requirements for any future distribution.
  Require matched before/after default-sampling answers, two consecutive development
  successes and a separate final check; preserve all prior weights and user data.
  Bound each audited session to 8 hours / 30000 updates. Budget exhaustion without
  the result is not success and does not authorize silent indefinite extensions.
  No automatic publication or installation. Existing v4 runtime suffices.
- Latest owner request: publish the selected chat_41 update-2000 weights (total
  33650) as **lambda terra 4.1** (`lambda-terra-4.1`) and organize model families
  as Mercury (1), Venus (2), Code (3), Terra (4). Preserve legacy IDs, artifact
  bytes, download hashes and chat bindings; provide Mercury/Venus aliases and
  display the renamed families in app 0.8.5. Terra 4.1 weights use CC BY-SA 4.0
  with Dolly CC BY-SA 3.0 attribution; software and old model licenses remain.
  Actual final comparison is 55/64 versus Venus 2.4's 22/64 on a narrow authored
  rubric, not general intelligence. The owner explicitly authorized publication.
- Also start **lambda terra 4.2** (`lambda-terra-4.2`) from own selected 4.1.
  Because 55/64 cannot be doubled, the stated new target is at least 2x fewer
  errors on new frozen development/final checks with retention guards. Private
  terra_42 adds exact instruction copying, corrected/multiple-person memory and
  old training replay; no old evaluation inputs as labels. Bound the audited
  session to 8 hours / 30000 updates, retain all checkpoints, default-sampling
  generated replies and final reports. No automatic publication or installation.
- The owner then demonstrated Terra 4.1 corrupting ordinary `hello`/`hi` replies.
  This regression was reproduced in 4.1 and the ongoing 4.2's selected snapshot;
  the earlier authored 61/64 quiz omitted these basic conversation guards and
  does not establish superior general chat. Original terra_42 was safely paused
  at step 757; preserve its checkpoints and published 4.1 artifact bytes.
  The owner requested fixing Terra's actual conversation, not canned app replies.
  Private `terra_42_repair` continues own 4.1 with frozen embeddings/first four
  blocks, guaranteed fresh/contextual old-chat replay in every update and KL
  distillation from own frozen Venus 2.4 on old-chat rows. Broader generated guards
  check actual default sampling, multiple seeds, greetings, identity, old facts,
  math, repeated characters and model-generated multi-turn histories. Known
  exposed cases are regression guards, never unseen benchmark claims. The
  separate challenge final split and full final dialogue rollout do not select
  checkpoints. Keep the 8-hour/30000-update cap, resumable optimizer/RNG saves,
  honest raw-answer reports and no automatic publication/installation.
- Latest owner naming instruction (2026-11-13): the ongoing `terra_42_repair`
  candidate is intended as a corrected **lambda terra 4.1** (`lambda-terra-4.1`),
  replacing the current 4.1 offering, not a new public 4.2. This supersedes the
  intended release name above. Keep the running trainer/config/fingerprint and
  historical paths unchanged so resumability is preserved. At release preparation
  rename inference metadata and publish a new catalog revision of the same model
  ID with a new immutable artifact filename/hash; preserve the old revision,
  checkpoints and chat bindings. Do not overwrite the previously published NPZ
  in place or silently install/release unreviewed weights. This message records
  the future replacement instruction; it does not request interrupting training.
- The owner subsequently requested continuing from the selected repair update
  2000, concentrating on memory/topic errors while protecting ALL existing skills.
  Private `terra_41_retention` pins that own checkpoint/NPZ and retains the name
  **lambda terra 4.1**. Only the last two blocks, norm and pointer may train;
  embeddings/positions/first six blocks and an identical retention teacher are
  frozen. Replay/distillation covers chat, facts, math, memory and instructions;
  training-only attention/gate labels point to the appropriate user's personal
  fact, including distractors, corrections, third parties and wrong prior bot
  echoes. No application-side factual parsing or response substitution.
  Selection is casewise: reject ANY lost previously correct regression/focus
  case or newly degenerate output, even when totals improve. This protects only
  the finite measured cases and must never be described as guaranteed zero loss
  on all prompts. All inspected old final cases are now exposed regressions;
  new final identities/wording are separate from checkpoint selection. Keep the
  pinned source if no qualified improvement survives. Bound this separate run
  to 240 minutes / 12000 updates plus final checks, save model/optimizer/RNG,
  and do not automatically install or publish the result.
- On 2026-11-14 the owner requested ten different real conversations comparing
  Venus 2.4 and the preserved repair update-2000 Terra 4.1 candidate. Private
  `../diagnostics/chat_comparison_2026_11_14` records 120 raw replies, frozen
  prompts/rubrics, identical UI sampling and each model's own generated history.
  Manual 0/1/2 scoring gave Venus 50/120 and Terra 56/120; conversation wins were
  Venus 3, Terra 4, ties 3. Both still fail arithmetic, relation-aware memory,
  follow-ups and object tracking, and can produce semantic gibberish. Do not
  claim reliable ordinary chat or general superiority from earlier keyword-only
  counts: 'Your name is green' is wrong even when 'green' matches a memory key.
  These inspected conversations are now exposed diagnostics, not future unseen
  evaluation cases. Full English transcript/report is also on the Desktop.
- The owner then requested substantially training Terra 4.1 toward a 2x
  improvement over Venus 2.4 after the small real-conversation advantage. The
  new private `terra_41_dialogue` preserves own repaired update 2000 and adds one
  identity-initialized residual block (9 blocks, 17,121,409 parameters). Verify
  unchanged initial source probabilities/arrays and v4 runtime/export parity;
  keep exports within the existing 64 MiB app download limit. First six original
  blocks and embeddings remain frozen; the new block and slow last-two/pointer
  adaptation learn complete conversations, including each acknowledgement,
  relational recall, corrected/friend identities, object tracking, arithmetic,
  exact instructions, natural follow-ups and study planning. Some training-only
  prior assistant replies are corrupted while USER facts stay intact.
  Short human OASST1 English dialogues supplement language learning; official
  revision/checksum/Apache 2.0 notice and human/synthetic filtering are documented
  in its SOURCES.md. No external pretrained weights or app-side answer rules.
  New generated dev/final conversations use full-response conservative grading,
  not keyword hits; source retention remains casewise. The stated target is at
  least 2x fewer errors vs 2.4, twice the correct replies where reachable and
  >=80% on that limited rubric, never twice general intelligence. Retain human
  language outputs for review. Bound this separate resumable run to 480 minutes
  / 24000 updates plus final checks; no silent extension or automatic release.
  The approved future identity remains **lambda terra 4.1**, replacing the
  offering only through a reviewed new immutable artifact/catalog revision.
- `terra_41_dialogue` completed 24000 updates in ~355 minutes with NO qualified
  candidate and no installation/publication. Development peaked at 37/60
  (updates 11000/15000/16000) vs Venus 22/60 and repaired source 25/60; the last
  update fell to 33/60. Update 16000 reached 6/6 on simple attribute recall,
  literal instructions and object tracking, but still had real arithmetic,
  name-binding and fluency failures plus old-skill regressions. No independent
  final conversation score exists because retention gates never passed.
  Important checkpoint limitation: only QUALIFIED best weights were archived,
  so update-16000 response logs exist but its exact weights do NOT. Keep the
  source-2000 and final-24000 artifacts unchanged. A future experiment should
  archive developmental progress separately from release qualification, while
  never representing rejected progress as an approved model. Do not claim the
  16000 model can be installed from the logs. Post-training cached NumPy/full
  Torch parity passed on inspected prompts (<2e-6 probability difference);
  the examined malformed replies are in the model, not explained by a cache
  mismatch. See ../conversation_training/runs/terra_41_dialogue/completion_audit.md.
- Latest owner instruction: fix checkpoint retention, continue from the best
  available 4.1 weights, and increase capacity to approximately 35M parameters.
  Private `terra_41_35m` compares four actual available repaired checkpoints:
  repair-2000 25/60, repair-4000 28/60, retention-4000 23/60, dialogue-24000 33/60;
  all scored 9/9 on the separate sampled core checks. It pins dialogue-24000
  (total step 59650), while explicitly retaining its known failures. Missing
  update-16000 weights cannot be recovered from logs or represented as available.
  The new model has 35,028,097 parameters, 19 blocks, pointer width 256, 512
  context. Identity residual blocks and Q/K rescaling preserve source behavior
  initially; preflight verifies full/cached probabilities and actual learning.
  EVERY evaluated update must be atomically archived with inference weights,
  optimizer/RNG checkpoint and checksums BEFORE quality gating. Keep independent
  progress_best and qualified_best pointers: release rejection never discards
  a developmental record. Snapshot restore/immutability/interrupted-export tests
  passed. End-of-run review evaluates preserved progress even if unqualified,
  without installing/publishing it. Run cap: 480 minutes / 24000 new updates.
  Local runtime preparation raises limits to 24 layers / 40M parameters and
  160 MiB downloads; 118 app tests passed. No app release was made. Public 35M
  weights require the matching future app update (min 0.8.6), with portable
  launchers unchanged. Preserve current artifacts/chats/quota and keep the
  approved future model identity **lambda terra 4.1**.
- The owner requested a desktop chat app while the 35M trainer continues. The
  separate `desktop/` Electron UI and packaged Python bridge use the existing
  engine, ChatStore, ModelManager and Quota. Keep all text English, real neural
  streaming replies, shared token settlement and portable resource paths. Do not
  embed personal launchers, private training files or the user's downloaded models.
  The standalone bundle includes only the small Mercury 1.0 starter. Additional
  model downloads must be explicit, individual, validated and cancellable; catalog
  refresh is metadata-only, and the chat picker lists available models only.
  Preserve archived chats in the existing DB, appearance preferences and CLI data.
  Desktop 1.0.0 is separate from the terminal package version and is not a published
  CLI update. Only Intel macOS packaging has been tested; do not claim verified
  Windows/Linux packages. GUI tests must use isolated temporary data and quota.
  No GitHub/model publication or training interruption was requested for this UI.
- Latest desktop request supersedes the preview-only publication rule: publish
  **Desktop app 1.1.0** as a separate `desktop-v1.1.0` GitHub release in this repo,
  with native Windows/Linux and Intel/Apple Silicon macOS packages. The provided
  orange Lambda image is the approved logo. Models live under Settings; remove
  the Explore models sidebar shortcut. Orange is the default accent and dark
  surfaces use warm charcoal. Profile name/age/location/interests may be supplied
  as bounded neural input context, with an off switch; never fabricate model
  answers from these fields. Keep profile information local and out of update
  requests. Deletion requires an explicit UI action and confirmation, removes
  only the selected chat and must not reset quota or delete models. Keep sidebar
  chats independently scrollable. Settings → Updates checks only `desktop-v*`
  releases and offers a matching native download; do not claim silent installation.
  Terminal 0.8.6 adds `lambda desktop`, `/desktop` and download information. It
  includes the already-tested large-model runtime bounds without changing the
  currently running 35M training fingerprint. Keep personal launchers portable,
  preserve old public artifacts and publish no new model in this app release.

- After Desktop app 1.1.0 passed all four native builds and was published, the
  owner requested removing the logo's white exterior corners. Desktop 1.1.1
  preserves the supplied raster inside an SVG corner mask; icon generation
  must verify fully transparent exterior and fully opaque orange interior.
  Do not ship background-removal attempts with holes in the orange tile. Keep
  1.1.0 release assets immutable. The patch also recognizes electron-builder's
  Linux x86_64 filename in desktop update checks. Terminal 0.8.7 updates its
  desktop release link; retain its previous wheel and all model artifacts.

- Latest owner instruction: publish the existing step-4000 **lambda terra 4.1
  demo** (`lambda-terra-4.1-demo`) publicly and remove non-demo Terra 4.1 from
  model choices. This explicitly supersedes the private-only rule and quality
  gate for this demo release only. Preserve its exact numerical update-4000
  weights (35,028,097 parameters, total step 63650), failed development/retention
  results, inherited CC BY-SA 4.0/Dolly and OASST1 Apache attribution. Public
  revision 2 follows the owner's private revision 1. Its ~130 MB NPZ belongs in
  GitHub release assets, not Git blobs or app wheels. Both catalogs replace the
  old offering with the demo; preserve immutable old NPZ files/IDs for existing
  saved chats. Do not rename or interrupt the running trainer or change its
  fingerprinted models.py/transformer.py. Existing Desktop 1.1.0+ can refresh
  the model list; terminal 0.8.8 bundles the new catalog. No desktop rebuild is
  needed for this data-only catalog change. Future final-model publication
  still requires a separate instruction or the applicable quality policy.
