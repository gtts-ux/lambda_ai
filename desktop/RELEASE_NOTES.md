# Desktop app 1.1.3

Settings → Updates now offers **Update & restart**. Lambda downloads the native package, verifies its SHA-256 and exact size, closes safely, updates the existing installation, and opens again. Downloading and preparation show progress. Chats, installed models, profile, token allowance and the terminal launcher are preserved.

- macOS: replaces the application bundle in its current writable location; restores the previous bundle if the new application fails to start.
- Windows: applies the native installer in silent update mode in the existing installation directory, then starts Lambda.
- Linux: replaces the running AppImage at its original path; restores the previous AppImage if startup fails.
- The chat model picker keeps its expandable families and keyboard navigation.

The installed application must be writable by your user. On Linux, launch the AppImage rather than an extracted executable to use in-app updates. Versions 1.1.2 and earlier need one installation of this release to gain the updater; later updates can be applied from the app.

Download the package for your device: macOS Intel (`macos-x64.zip`), macOS Apple Silicon (`macos-arm64.zip`), Windows (`windows-x64.exe`), or Linux (`linux-x86_64.AppImage`). For a first macOS installation, extract Lambda.app and move it to Applications or another writable folder. Linux: make the AppImage executable and launch it. These community builds are unsigned; the operating system may request confirmation on first launch.
