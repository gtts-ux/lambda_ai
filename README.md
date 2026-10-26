# λ Lambda AI

**A local English AI chat application for your terminal.**
Type `lambda` to open a full-screen chat, inspect actual BPE tokens, explore
model parameters, and check your allowance. The bundled **lambda 1.0** model
was trained from random weights with a locally learned tokenizer.

```text
  λ  L A M B D A   /   local English AI
  1,000,000 / 1,000,000 tokens left · reset after first message

  F1 Chat       F2 Tokens       F3 Models       F4 Usage
  ──────────────────────────────────────────────────────
  YOU
  What is a cat?

  λ LAMBDA
  A cat is a mammal with fur, whiskers, and paws with claws.

  › Message or command
```

This is a small educational model, not a general-purpose assistant. It can
give incorrect or nonsensical answers. Each question is processed separately;
the visible conversation is not additional model memory.

## Install

Requires **Python 3.11+**. On macOS or Linux:

```bash
git clone https://github.com/gtts-ux/lambda_ai.git
cd lambda_ai
bash install.sh
lambda
```

The installer creates `.venv` inside the project and links `lambda` into
`~/.local/bin`, without `sudo`. If needed, it prints the PATH setting to add.
Keep the project in its installation location; if you move it, recreate the
environment and install again. Dependencies require internet during installation.
The English model is included, so chat then works offline.

Standard Python installation, also usable on Windows:

```bash
python -m venv .venv
# macOS / Linux:
.venv/bin/python -m pip install .
.venv/bin/lambda
# Windows:
# .venv\Scripts\python -m pip install .
# .venv\Scripts\lambda
```

Distribution name: `lambda-ai-terminal`. Installing the package adds the
standard `lambda` console entry point to that Python environment.

## Terminal controls

| Key | Action |
| --- | --- |
| F1 | Chat |
| F2 | Live token inspector, including IDs and generated tokens |
| F3 | Model choices, parameter count and matrix shapes |
| F4 | Remaining allowance, reset time and session usage |
| Enter | Send a message or run a command |
| PgUp / PgDn | Scroll |
| Ctrl+C | Cancel an operation or clear the input |
| Ctrl+D | Exit |

The sidebar adapts to terminal width. Slash commands support completion,
and the input supports session history with the arrow keys.

```text
/help
/tokens What is a cat?
/model
/model use lambda-1.0
/update
/stats
/temperature 0.4
/limit 120
/topk 8
/new
/save conversation.json
/exit
```

`/model` offers **lambda 1.0** and **lambda 1.5**. In that view, enter a model's
number or use `/model use <id>`. Lambda 1.0 remains included with the app;
lambda 1.5 is an optional download. Future models appear after `/update` when
the maintainer adds them to the catalog. New models are not given automatic names.

### lambda 1.5: elementary mathematics

Lambda 1.5 has **1,867,520 parameters — exactly 2.5× lambda 1.0**. Its English
training includes small integer addition, subtraction, multiplication and exact
division, with digits tokenized individually. Answers come from the neural
model; no calculator or answer lookup is used during generation.

```text
/update
/model use lambda-1.5
```

The same commands work in an existing installation; the inference format is
compatible with app 0.1.0. Both models remain selectable. Arithmetic is still
fallible: see the [lambda 1.5 model card](models/lambda-1.5.md) and its measured
benchmark results before relying on it. Switching models preserves the allowance.

## Token allowance

Each local OS user receives **1,000,000 tokens per 10-hour window**. The window
starts with the first message. This is approximately **5,000 exchanges at
200 input + output tokens each**, not a guarantee of exactly 5,000 messages.

- Used input context and actually generated tokens count toward the allowance.
- Stop-marker tokens count; padding and input discarded beyond the context do not.
- Unused output reservations are refunded. Near the limit, the output cap shrinks.
- Chat is blocked when there are not enough tokens for the input and one output token.
- The allowance resets automatically after 10 hours.
- Restarting, `/new`, switching models and model updates do not reset usage.
- SQLite transactions coordinate concurrent `lambda` processes.

This is a **local limit per OS account**, not a server-enforced account or
subscription shared across devices. State is stored under
`~/.local/share/lambda-ai` on macOS/Linux, or `%LOCALAPPDATA%\LambdaAI` on Windows.
`XDG_DATA_HOME` and `LAMBDA_DATA_HOME` can set the application data location.
No account, API key, telemetry or paid text-generation API is used.

The model's **64-token context** is separate from the allowance. A larger
allowance does not increase how much of one question the model can see.

## Model updates

```bash
lambda update
lambda model list
lambda model use lambda-1.0
```

`/update` and `lambda update` explicitly fetch
[`models/catalog.json`](https://github.com/gtts-ux/lambda_ai/blob/main/models/catalog.json)
and update revisions of already installed models. Newly named models appear
in `/model`; choose one to install and use it. Model files are downloaded
to the user data directory and checked against their size, SHA-256 and
supported inference format before installation. Failed downloads keep the
previous working model. Switching back to an installed model works offline.

These commands update **model weights and the model list**, not executable
application code. If a future model requires a newer application, Lambda
reports the required version. Update the repository and reinstall the package
to upgrade the app itself. Current model names and future release rules are in
[MAINTAINER.md](MAINTAINER.md).

## Scriptable commands

```bash
lambda ask "What is a cat?"
lambda ask "What is the internet?" --seed 7 --json
lambda tokens "Hello, world!" --json
lambda info --json
lambda usage --json
lambda chat --plain
lambda --version
```

`ask --json` reports text, actual output token IDs, used/dropped context,
charged tokens, speed, elapsed time and finish reason. All chat entry points
use the same allowance. Token inspection and model information are free.
Pipes automatically use plain mode. A custom inference model can be specified
with `lambda --model file.npz` or `LAMBDA_MODEL`.

Conversations remain in memory unless explicitly exported with `/save`.
An existing export is not overwritten. Usage counts persist without storing
the text of conversations.

## Model and source

The bundled model is an autoregressive MLP with **747,008 parameters**, two
hidden `tanh` layers, a **1,024-token BPE vocabulary**, and **64-token context**.
Inference uses float32 NumPy arrays on CPU. The application includes no
training loop, gradients or optimizer state. Chat never modifies model weights.

[MODEL_CARD.md](MODEL_CARD.md) documents the English dataset and limitations.
The model checksum and checkpoint step are included in
`lambda_cli/assets/model.json`. Code and included inference weights are
licensed under [MIT](LICENSE).

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . -w dist
```

The wheel includes the app and default model. GitHub Actions runs tests on
Linux and Windows. No training dataset, trainer or saved optimizer is shipped.
