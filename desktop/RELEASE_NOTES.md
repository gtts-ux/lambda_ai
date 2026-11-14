Desktop app 1.1.2 improves the model picker beside the chat input.

- The picker starts with collapsed model families: Mercury, Venus, Code and Terra, as available on the device.
- Expand a family to reveal its downloaded versions. Opening another family collapses the previous one.
- The current family and selected version are marked clearly; selection still uses the same neural engine.
- Arrow keys navigate, Right/Left expand and collapse, Enter selects, Escape closes.
- Model downloads remain in Settings → Models. Opening or expanding the chat picker never downloads a model.
- The expanded popup stays within the window, including at the minimum layout size.

Includes the transparent orange logo, warm dark theme, local saved chats, profile context, usage counter and desktop update checker from previous releases. The bundled catalog now offers Terra 4.1 demo instead of the retired non-demo Terra 4.1. Previously installed files remain usable by old saved chats.

| System | Package |
| --- | --- |
| macOS, Intel | `Lambda-1.1.2-macos-x64.zip` |
| macOS, Apple Silicon | `Lambda-1.1.2-macos-arm64.zip` |
| Windows x64 | `Lambda-1.1.2-windows-x64.exe` |
| Linux x64 | `Lambda-1.1.2-linux-x86_64.AppImage` |

macOS: extract and drag Lambda.app to Applications. Windows: run the installer. Linux: make the AppImage executable, then run it; FUSE 2 is required, or use `--appimage-extract-and-run`. Packages are unsigned; macOS may require Open Anyway in Privacy & Security, and Windows may show an unrecognized-publisher prompt.

All native packages are tested in GitHub Actions before publication. SHA256SUMS.txt contains download checksums. Chats, models, profile and shared allowance stay on the device. The app includes its runtime and one small starter; other models are individual optional downloads. This update does not change model weights or claim improved intelligence.
