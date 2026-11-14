# Desktop app 1.1.4

Fixes a macOS packaging error that could report Lambda as damaged on Apple Silicon.
The previous ARM64 app retained an invalid resource signature. macOS packages now
receive a complete ad-hoc signature after packaging, including the bundled Python
engine, Electron helpers and native libraries. CI validates the final extracted
ZIP on native Intel and Apple Silicon, checks relocation/quarantine metadata, and
confirms that changing app.asar is detected. The updater also validates the macOS
bundle before replacing a working application.

Chat families, one-click updates, local conversations, downloaded models, settings
and token allowance are preserved. No model or training changes are included.

For M1/M2/M3/M4 Macs, download **Lambda-1.1.4-macos-arm64.zip**. Extract Lambda.app
and replace the previous app in Applications or another writable location. Do not
merge the contents of the old and new app bundles.

These community packages have an ad-hoc signature, not an Apple Developer ID or
notarization ticket. If macOS asks for approval, try opening Lambda, then go to
System Settings → Privacy & Security → Open Anyway. This approval is specific to
the application. Apple instructions: https://support.apple.com/guide/mac-help/mh40617/mac .

Users whose old application opens can use Settings → Updates → Update & restart.
A blocked old installation needs this replacement once to acquire the fix.
Windows and Linux retain their existing native installers and in-app updater.
