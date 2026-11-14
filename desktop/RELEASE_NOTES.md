Lambda Desktop app 1.1.1 fixes the logo’s exterior white corners with a transparent SVG mask and native icons. The original orange face and white lambda are retained. Linux update checks also recognize the native x86_64 package name.

Includes the features introduced in Desktop app 1.1.0:

- Supplied orange Lambda logo, orange accent and warm charcoal dark theme.
- Local saved chats with search, pinning, archives, a scrollable sidebar and delete controls.
- Settings for appearance, individually downloaded models, response length and profile.
- Optional name, age, location and interests supplied as neural input context.
- Shared 1,000,000-token allowance with the terminal app, including reset countdown.
- Streaming real model replies, stop, saved regeneration branches and colored code blocks.
- Settings → Updates → Check for updates checks desktop releases separately from models.

Download the package for your device:

| System | Package | Installation |
| --- | --- | --- |
| macOS, Intel | `Lambda-1.1.1-macos-x64.zip` | Extract, then drag Lambda.app to Applications. |
| macOS, Apple Silicon | `Lambda-1.1.1-macos-arm64.zip` | Extract, then drag Lambda.app to Applications. |
| Windows x64 | `Lambda-1.1.1-windows-x64.exe` | Run the installer. |
| Linux x64 | `Lambda-1.1.1-linux-x86_64.AppImage` | Make executable with `chmod +x`, then run it. |

The app includes its Python runtime and one small starter model. Download other
models individually in Settings → Models. Existing terminal chats, models and
allowance remain available. Profile context requires a memory-capable model;
answer quality still depends on the selected weights. This is an app release,
not a new model or a claim of improved intelligence.

Packages are currently unsigned. macOS may require Open Anyway in Privacy & Security;
Windows may show an unrecognized-publisher prompt. Linux requires a graphical desktop
and FUSE 2, or run the AppImage with `--appimage-extract-and-run`.

Each package is built and tested on its target operating system in GitHub Actions.
SHA256SUMS.txt contains download checksums. Use `lambda desktop` or `/desktop` in the
terminal app (0.8.6+; the current link is in 0.8.7+) to find this desktop release. Update the desktop by installing
the newer package; model refresh does not replace application code.
