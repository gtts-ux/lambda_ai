# Lambda Desktop

Image Playground includes a persistent **Image model** selector for individually
downloaded models. Get Orion 1.2 or the older Orion Image 1 in Settings → Models.
Saved images show which model created them. Orion 1.2 preserves whole references
and can closely resemble the source photo; native output stays 256 × 256.

A desktop home for local Lambda conversations, built with Electron and the
existing Lambda inference engine. The interface is English.

## Using the app

Download the package for your system from [Desktop app 1.4.1](https://github.com/gtts-ux/lambda_ai/releases/tag/desktop-v1.4.1). Open `Lambda.app` on macOS, run the installer on Windows, or make the Linux AppImage executable and launch it. The standalone build includes its own Python runtime,
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
- **Image Playground** creates experimental 256×256 images with **orion image 1**.
  Download this one optional model in Settings → Models. Describe a subject or
  scene, such as “Generate a photo of Saturn V in space”.
  General reference search uses DuckDuckGo with strict Safe Search and needs an
  internet connection. Any subject description may be searched; there is no closed
  three-object list. If filtered search is unavailable, generation stops instead
  of falling back to an unfiltered source. Neural image generation runs on
  your device. Choose 1–8 images and 256/512/1024 export size. Progress, Stop,
  local image history and Save PNG are included. Larger sizes enlarge the model's
  native 256px output; they do not add newly learned detail.
  The price is shown before generation: Orion Image 1 costs 1,000 tokens per
  prompt word at 256; Orion 1.2 costs 1,500 (1.5×). Both use ×2 at 512 and ×4 at
  1024. Five words at 512 cost 10,000 / 15,000 tokens per image respectively.
  The full batch is reserved against the shared allowance; only completed saved
  images are charged. Cancelled/failed unfinished images are refunded.
  Reference credits are available under the preview. Objects can be blurred,
  distorted or misplaced; this first model is not a reliable photorealistic generator.
- In a **Terra** chat, an independently trained local intent head can recognize
  direct image requests and open Image Playground. It does not replace chat weights
  or improve general conversation. Ambiguous requests may be missed; the sidebar
  mode is always available. Other chat families do not automatically generate images.

`Enter` sends, `Shift+Enter` inserts a line, `Cmd/Ctrl+N` starts a chat,
`Cmd/Ctrl+K` searches and `Cmd/Ctrl+,` opens settings.

**Settings → Updates → Check for updates** checks only desktop releases and offers
the matching download for your operating system. It never sends your profile or
conversation content. Click **Update & restart** to download and verify the matching package. Lambda closes, applies the update in its existing location, and opens again. Chats, models, profile and usage stay in the shared data directory. On Linux, run the AppImage to enable this action. An unwritable installation must first be moved to a location your user can update.

Desktop and CLI share the existing Lambda data directory, including downloaded
models, chats and allowance. Desktop preferences are in `desktop.json` there.
`LAMBDA_DATA_HOME` can select a separate data directory before launch. Installation
paths are resolved relative to the app; no maintainer-specific directory is needed.

The packaged engine includes its HTTPS CA roots, so reference and model downloads
do not depend on a Python/certificate installation on the build machine. Hostname
and certificate verification remain enabled. CI tests real packaged downloads and
image generation with deliberately missing host CA paths.

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
Windows/Linux packages are unsigned; macOS uses an ad-hoc integrity signature,
without Apple Developer ID/notarization. No store upload is configured.
The `desktop-v*` tag workflow publishes a separate desktop release only after
every native build and its tests pass.

PyInstaller packages the engine into the app's resources. The build verifies that
it contains only the starter chat NPZ and the small learned image-intent NPZ,
with no chat database or training checkpoint. Orion image weights are optional.
Downloaded models and private training files are not packaged. All generated
build trees, environments, test profiles and installers are excluded from Git.

Desktop version 1.4.1 and terminal package versions are separate. CLI `/update`
updates the CLI package. Desktop Settings → Updates → Update & restart updates
the bundled desktop engine in place. It does not overwrite the terminal launcher.
Versions 1.1.2 and earlier need one package installation to gain the new updater;
subsequent desktop updates use the in-app action.

## Verification

```sh
.build-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
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

## macOS first launch and package integrity

Mac builds now carry an ad-hoc code signature covering the app, Python engine,
Electron helpers and native libraries. CI unpacks each distributed ZIP, verifies
all Mach-O signatures, verifies a relocated/quarantined copy and checks that
modifying app.asar is rejected. The updater verifies the bundle before replacing
an installation. These checks distinguish package integrity from Apple trust.

The project does not currently have an Apple Developer ID/notarization certificate.
A browser-downloaded build can still require **System Settings → Privacy & Security
→ Open Anyway** after trying to open it. Use the `macos-arm64.zip` package for an
M1/M2/M3/M4 Mac. Replace the old Lambda.app rather than merging its contents.

Official Apple instructions: https://support.apple.com/guide/mac-help/mh40617/mac .
