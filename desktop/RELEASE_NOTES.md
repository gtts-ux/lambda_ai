# Desktop app 1.2.1 — Image references and Terra 4.1

- Comma-separated image tags fall back to shorter reference searches instead of
  requiring every synonym in every source caption. Portraits remain eligible.
- Image failures appear beside the prompt without duplicate Electron IPC errors.
- Terra 4.1 revision 2 is an optional model download under the full requested name.
  It is a new own-foundation continuation, still experimental with unreliable
  arithmetic, name recall and topic returns. The older demo remains available.
- Chats, image history, optional models, quota and update/restart are preserved.

## Included Image Playground features from 1.2.0

- New Image Playground with optional orion image 1 download in Settings.
- Native 256 × 256 local images, progress, stop, variation seed, persistent image
  history, reference credits and Save PNG.
- Terra gets an own learned image-request head; clear requests can open Playground.
  Some requests are missed; the explicit mode is always available.
- NASA/Wikimedia references are online; neural image generation runs locally.
- Experimental preview: objects can be distorted or unrecognizable. See the model card.
- Chats, downloaded chat models, profile, allowance and verified update/restart remain
  compatible. Orion downloads only on explicit request.

Native packages: Intel/Apple Silicon macOS, Windows x64 and Linux x64. Native builds
and packaged-app tests must pass before the desktop release is published.

## Included macOS packaging fix from 1.1.4

Fixes a macOS packaging error that could report Lambda as damaged on Apple Silicon.
The previous ARM64 app retained an invalid resource signature. macOS packages now
receive a complete ad-hoc signature after packaging, including the bundled Python
engine, Electron helpers and native libraries. CI validates the final extracted
ZIP on native Intel and Apple Silicon, checks relocation/quarantine metadata, and
confirms that changing app.asar is detected. The updater also validates the macOS
bundle before replacing a working application.

Chat families, one-click updates, local conversations, downloaded models, settings
and token allowance are preserved.

For M1/M2/M3/M4 Macs, download **Lambda-1.2.0-macos-arm64.zip**. Extract Lambda.app
and replace the previous app in Applications or another writable location. Do not
merge the contents of the old and new app bundles.

These community packages have an ad-hoc signature, not an Apple Developer ID or
notarization ticket. If macOS asks for approval, try opening Lambda, then go to
System Settings → Privacy & Security → Open Anyway. This approval is specific to
the application. Apple instructions: https://support.apple.com/guide/mac-help/mh40617/mac .

Users whose old application opens can use Settings → Updates → Update & restart.
A blocked old installation needs this replacement once to acquire the fix.
Windows and Linux retain their existing native installers and in-app updater.
