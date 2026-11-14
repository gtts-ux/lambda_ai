# Lambda Desktop

A desktop home for local Lambda conversations, built with Electron and the
existing Lambda inference engine. The interface is English.

## Using the app

Download the package for your system from [Desktop app 1.1.2](https://github.com/gtts-ux/lambda_ai/releases/tag/desktop-v1.1.2). Open `Lambda.app` on macOS, run the installer on Windows, or make the Linux AppImage executable and launch it. The standalone build includes its own Python runtime,
the inference engine and the small Mercury 1.0 starter model. It does not need a
terminal, a checkout or a separately installed Python to run.

- **New chat** starts a separate conversation. Existing chats save automatically.
  Search, rename, pin, archive and reopen them from the sidebar. Archived chats
  remain on the device; the archive button switches the sidebar to that list.
  The red trash button deletes a conversation after confirmation.
- **Settings → Models** manages model downloads. Download an individual model, watch
  its progress or cancel. Refresh list retrieves catalog metadata only. Downloads
  use the existing size, SHA-256 and format validation before installation.
- The chat's **model picker** lists models available on the device, grouped by
  Mercury, Venus, Code and Terra. Expand a family to reveal its versions; only
  one family opens at a time. Arrow keys navigate/open/close sections; Enter
  selects, and Escape returns to the chat. Selecting a model does not download
  other models.
- **Appearance** offers light, dark and system themes, five accent colors, with orange as the default, text
  size and comfortable or compact spacing. Settings persist after restart.
- **Profile & usage** lets you optionally share your name, age, location and interests as model input context. You can disable this without deleting your profile. It also shows the exact remaining tokens, percentage, used tokens,
  reset countdown and reset date. The existing 1,000,000-token / 10-hour allowance
  is shared with the terminal app and all conversations and models.
- Replies stream from the selected neural model. Stop cancels generation.
  Try again creates a saved conversation branch, preserving the original reply.
  Markdown code blocks use syntax colors and have a Copy code button.

`Enter` sends, `Shift+Enter` inserts a line, `Cmd/Ctrl+N` starts a chat,
`Cmd/Ctrl+K` searches and `Cmd/Ctrl+,` opens settings.

**Settings → Updates → Check for updates** checks only desktop releases and offers
the matching download for your operating system. It never sends your profile or
conversation content. Install the downloaded package to update the desktop app.

Desktop and CLI share the existing Lambda data directory, including downloaded
models, chats and allowance. Desktop preferences are in `desktop.json` there.
`LAMBDA_DATA_HOME` can select a separate data directory before launch. Installation
paths are resolved relative to the app; no maintainer-specific directory is needed.

The desktop UI does not improve model weights or replace answers with templates.
Model quality remains that of the selected model. Training runs are separate.

## Building from source

Use Node.js 22+ and Python 3.12 on the target operating system. From this directory:

```sh
python3.12 -m venv .build-venv
.build-venv/bin/python -m pip install -r requirements-build.txt
npm ci
# If npm skipped Electron's install script:
node node_modules/electron/install.js
npm run build:backend
npm start
```

On Windows, use `.build-venv\Scripts\python` for pip and the Python checks.
`LAMBDA_BUILD_PYTHON` can specify the build environment's interpreter.

Build standalone packages on their target OS:

```sh
npm run build:mac    # macOS 14+, native Intel/Apple Silicon ZIP
npm run build:win    # Windows x64 NSIS installer
npm run build:linux  # Linux x64 AppImage
```

The release workflow builds and tests native packages on Windows x64, Linux x64,
macOS Intel and macOS Apple Silicon before publishing the desktop release.
See its Actions run for platform-specific verification results.
Packages are unsigned; no store upload or signing identity is configured.
The `desktop-v*` tag workflow publishes a separate desktop release only after
every native build and its tests pass.

PyInstaller packages the engine into the app's resources. The build verifies that
it contains exactly the starter NPZ and no chat database or training checkpoint.
Downloaded models and private training files are not packaged. All generated
build trees, environments, test profiles and installers are excluded from Git.

Desktop version 1.1.2 and terminal package versions are separate. CLI `/update`
updates the CLI package. Desktop Settings → Updates finds a new package; install it
to update the bundled desktop engine. It does not silently overwrite the terminal launcher.

## Verification

```sh
.build-venv/bin/python -m unittest discover -s tests -p 'test_backend.py' -v
npm run test:desktop
npm run test:updates
# Test the standalone macOS build instead of development Electron:
LAMBDA_PACKAGED_EXECUTABLE="$PWD/release/mac/Lambda.app/Contents/MacOS/Lambda" npm run test:desktop
```

The GUI test creates an isolated temporary profile, seeds conversations using real
model replies, explicitly downloads one small model, checks installed-only choices,
chat persistence, archives, themes, syntax highlighting, quota display and a narrow
window. Its sample profile allowance never changes the user's real quota. Tests
also check model-text sanitization and cancellation settlement. Screenshots and
the result report are written under `test-artifacts/`.
