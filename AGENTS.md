# Lambda AI maintenance instructions

- The app, its UI, documentation, default prompts and bundled model must be English.
- The currently approved model name is **lambda 1.0**, ID `lambda-1.0`.
- The owner will supply the name of every future model. If a new model is requested
  without a name, ask the owner before assigning or publishing one. Never invent a name.
- Do not ship training scripts, training data or optimizer state in this repository.
  Only inference weights and their locally learned tokenizer belong in the app bundle.
- Preserve the per-OS-user 1,000,000-token allowance and 10-hour reset, shared across
  sessions, CLI entry points and model choices. Do not add a user-facing reset command.
- Validate every model download with size, SHA-256 and the supported inference format.
  Keep the previous working model if validation fails.
- Keep `models/catalog.json` and `lambda_cli/assets/catalog.json` identical.
- Run `python -m unittest discover -s tests -v` and build a wheel before publishing changes.
- Repository: https://github.com/gtts-ux/lambda_ai . Do not force-push shared branches.
