# Publishing model updates

Repository: https://github.com/gtts-ux/lambda_ai

The approved model names are **lambda 1.0** (`lambda-1.0`),
**lambda 1.5** (`lambda-1.5`), **lambda 1.6** (`lambda-1.6`), and **lambda 2** (`lambda-2`).
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
the repository at that path; compatible downloaded files are limited to 50 MiB.
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
