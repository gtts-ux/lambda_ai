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
  **lambda 2.1** (`lambda-2.1`), and **lambda 2.2** (`lambda-2.2`).
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
