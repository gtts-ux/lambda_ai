# Desktop app 1.4.0 — Orion 1.2 and image model selection

- Choose an individually downloaded image model directly in Image Playground.
  The choice persists after restart and is separate from the chat model. Settings
  still controls optional downloads; startup never downloads every model.
- Optional **orion 1.2** uses full descriptions and whole-reference conditioning
  to reduce destructive object crops and affine distortions. Outputs can closely
  resemble the source photo: this is reference-guided reconstruction/variation,
  not a general text-to-image foundation. The previous Orion Image 1 is retained.
- Each saved image keeps its own model name. Browsing older images does not switch
  the current generator. Selection is disabled during a running batch.
- Strict Safe Search, bundled HTTPS trust, native 256 output, labelled 512/1024
  enlargements and the existing per-word image pricing/refunds are preserved.
- Core 0.11.1 reads cached reference titles explicitly as UTF-8, including on
  Windows code pages. Repeated generations can reuse non-English search results.
- Chat history, installed models, profile, allowance and verified update/restart
  remain compatible. Technical tests cover model switching and persistence.

## Included 1.3.0 improvements — Reliable HTTPS and image batches

- General image-reference search with strict Safe Search, rather than a closed
  subject list or NASA-only search. If filtering is unavailable, stop and refund
  unfinished images; never retry through an unfiltered provider.

- Includes trusted CA certificates in the packaged Python engine. Image/reference
  downloads and model lists work outside the build machine without disabling TLS
  verification. Native checks use missing host CA paths and real network requests.
- Replace Variation with image count (1–8) and 256/512/1024 export size.
- Show the price before generation: 1,000 tokens per prompt word at 256, ×2 at
  512, ×4 at 1024, multiplied by image count. Reserve the batch and charge only
  completed images; failed/cancelled unfinished images are refunded.
- Orion still renders natively at 256; larger exports are explicitly labelled
  enlargements, not newly learned detail. Model weights and existing data stay intact.

## Included reference and Terra changes from 1.2.1

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

For M1/M2/M3/M4 Macs, download **Lambda-1.3.0-macos-arm64.zip**. Extract Lambda.app
and replace the previous app in Applications or another writable location. Do not
merge the contents of the old and new app bundles.

These community packages have an ad-hoc signature, not an Apple Developer ID or
notarization ticket. If macOS asks for approval, try opening Lambda, then go to
System Settings → Privacy & Security → Open Anyway. This approval is specific to
the application. Apple instructions: https://support.apple.com/guide/mac-help/mh40617/mac .

Users whose old application opens can use Settings → Updates → Update & restart.
A blocked old installation needs this replacement once to acquire the fix.
Windows and Linux retain their existing native installers and in-app updater.
