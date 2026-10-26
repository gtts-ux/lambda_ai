# Lambda AI maintenance instructions

- The app, its UI, documentation, default prompts and bundled model must be English.
- The approved model names are **lambda 1.0** (`lambda-1.0`),
  **lambda 1.5** (`lambda-1.5`), and **lambda 1.6** (`lambda-1.6`).
- Lambda 1.6 has exactly 2,614,528 parameters including its learned intent head;
  its v2 inference format requires app 0.2.0 or newer. Keep v1 models supported.
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
