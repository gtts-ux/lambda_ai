# Publishing model updates

Repository: https://github.com/gtts-ux/lambda_ai

The approved model names are **lambda 1.0** (`lambda-1.0`),
**lambda 1.5** (`lambda-1.5`), **lambda 1.6** (`lambda-1.6`), **lambda 2** (`lambda-2`),
**lambda 2.1** (`lambda-2.1`), **lambda 2.2** (`lambda-2.2`), **lambda 2.4** (`lambda-2.4`),
and **lambda 2.5.1** (`lambda-2.5.1`).
The owner will name future models. **Ask the owner if a new model is requested
without a name; do not invent or automatically increment model names.**

Training is kept outside this app repository. To distribute a better model,
export an already trained compatible checkpoint, explicitly providing its
owner-approved name and ID:

```bash
python tools/export_model.py /path/to/checkpoint.npz models/FILE.npz \
  --id OWNER_APPROVED_ID --name "OWNER APPROVED NAME"

python tools/register_model.py models/FILE.npz \
  --id OWNER_APPROVED_ID --name "OWNER APPROVED NAME" --revision 1
```

For an update to an existing named model, keep its ID/name and **increase its
revision**. Do not publish changed weights under the same existing revision.
For a new named model, add a new entry. Never remove previous entries merely
because a new model exists: users must be able to select previous models.

`register_model.py` updates both `models/catalog.json` and the bundled
`lambda_cli/assets/catalog.json`, using the actual file size and SHA-256.
Its URL points to this repository's `main` branch. Keep the model file in
the repository at that path; app 0.5.1 accepts compatible model downloads up to 64 MiB (older apps cap downloads at 50 MiB).
Set `--min-app-version` when a model needs newer app support. A different
architecture requires an engine change and an app update before publication.

The v2 format used by lambda 1.6 includes a learned mode-conditioned bias and
an intent classifier. The final model also uses fixed hashed question features
in chat mode, learned through the generator's existing first layer. Export it
with `--router /path/to/router.npz --question-features` and register
it with `--min-app-version 0.2.0`. Count both generator and router weights.

Lambda 2 uses the same v2 format and minimum app version. Its released file is
the final trained checkpoint at step 100,000. The mixed validation criterion
preferred the untrained step-0 expansion; do not accidentally distribute that
baseline as the trained release. Preserve the selection explanation and measured
regressions in its model card. The bundled default remains lambda 1.0.

To replace the default bundled model, export to `lambda_cli/assets/model.npz`
and register that file with the approved ID/name. Update its model card too.

Before pushing:

```bash
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . -w dist
lambda ask "What is a cat?" --seed 7
```

Commit the inference file, checksum manifest, both catalogs and documentation
together. Push to `main`. Existing users then run `/update`; new named models
appear in `/model`, while higher revisions of installed models are downloaded.
Verify the published catalog and download after pushing. Never force-push.

Model updates do not reset usage or alter the 1,000,000-token / 10-hour rule.
The local allowance is intentionally not presented as a server-enforced plan.

Lambda 2.1 is the owner-authorized experimental conversation release (v4, app >=0.4.0).
It supersedes the private 2.5 trial name. The owner explicitly requested publication
despite failed automatic quality gates; retain that fact and the raw benchmark.
See models/lambda-2.1.md for selection, provenance and measured limitations.
Do not publish training data, optimizer state or the frozen training teacher.
Keep older models, the default selection and shared quota intact.

Lambda 2.2 is the owner-named conversation repair (2026-10-29), v4/app >=0.4.1.
It preserves earlier releases. The app's float32 fix must be installed before
claiming the numerical warning repair. Keep the measured comparisons and limitations
in models/lambda-2.2.md; do not replace them with a general intelligence claim.

## Application wheel releases

`/update` reads `releases/app.json`, then installs the verified universal wheel
from the same directory. Keep previous versioned wheels immutable. This flow is
separate from model naming and model catalogs; do not rename a model for a UI update.

For each application release:

1. Bump `lambda_cli/__init__.py` and `pyproject.toml` together.
2. Run the unit tests and build a wheel with `python -m pip wheel . --no-deps -w dist`.
3. Stage it: `python tools/publish_app.py dist/lambda_ai_terminal-VERSION-py3-none-any.whl`.
4. Commit the code, wheel and `releases/app.json` together, then push and verify a download.

The update command executes pip in a subprocess using the current Python interpreter,
following the [pip embedding guidance](https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program).
A running process uses its old imports until restart. Windows installs are deferred
until the launcher exits. No token ledger/model state belongs in the wheel or installer.

Lambda 2.4 is the owner-approved public name for the selected private 2.3 trial.
Release total step 31650 (7000 additional updates), with 15,350,401 parameters.
Require app >=0.5.1, whose bounded model-download budget is 64 MiB. Do not rewrite
private checkpoint identities or remove earlier model releases and saved chats.


App 0.6.0 adds model-family navigation, searchable/pinned chats and branched question
editing/regeneration. No model comparison UI was requested. Pins are in a separate
SQLite table so older running windows can still write the unchanged chats schema.
Keep all user data out of wheels and git.

The owner named the next private model lambda 2.5 on 2026-10-30. Its private
`release_25` continuation expands the own selected 2.4 checkpoint to 1024 positions;
all answers still come from its learned distribution. Do not register this model
until trained weights and their generated-answer checks are ready for review.


App 0.7.0 adds opt-in `/web`, `/read`, and F7 `/sources`, plus activity phases.
Keep evidence separate from generated model text, source URLs attached by application
metadata, cancellation/quota accounting, and restored old chat schemas working.
The owner declined publication of the failed 2.5 trial. No new model weights are
part of this application release. The existing 2.4 failed the supplied-evidence
probe; document this limitation instead of calling the tool a reliable 2.5 model.
The future 2.5 name is reserved pending grounded-answer validation.


App 0.8.0 removes the manual web preview controls and source cards. Automatic search
is gated by both lambda-2.5 identity and its v5 neural search head; old snapshots
cannot enable web on other models. V5 contains conditional low-rank evidence
adapters and learned answer-boundary/answerability heads. Plain chat keeps the
frozen 2.4 arrays; model-predicted answer spans are decoded inside inference.
No new 2.5 model should be published before separate reading/routing checks. The
failed release_25 and grounded_25 trials remain private and preserved.

The owner subsequently explicitly requested publishing the reviewed best research
checkpoint as **lambda 2.5.1**, despite its failed quality gate. This exception
applies only to the selected `grounded_refine_25` step-200 inference weights
(total lineage step 32550). Do not publish the final step-600 weights, relabel the
failed older `release_25` run, or alter private checkpoint identities. The 2.4
base arrays remain identical. App **0.8.1** enables automatic research under the
exact lambda-2.5.1 identity and v5 format; older models remain offline. Publish
the measured reading/routing scores and limitations in the model card, including
the failed development gate. No general intelligence or reliable-web claim.
