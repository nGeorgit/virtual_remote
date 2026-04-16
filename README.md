# Mobile Typer

`mobile-typer` starts a small local web server that serves:

- a portrait hardware-style virtual remote with buttons `A` through `R`
- a local JSON API used by that page

When you tap a button from your phone, the page waits briefly before sending it so it can detect a combo. Each additional button tapped during that window is added to the same combo and restarts the delay. When the delay expires, the computer running the server sends the full combo to the currently focused app on that computer. The `P` stop button is the exception: it bypasses the delay, clears any pending combo on the page, ignores secondary mode, and is sent immediately. By default the app also opens a small desktop window that shows the QR code and local phone URL.

## Requirements

- Python 3.8+
- `qrcode>=7.4,<8`
- Your phone and computer must be on the same Wi-Fi network
- Keep the target app focused on your computer

### Platform notes

- Linux: this implementation uses X11/XTest. It is intended for X11 sessions.
- macOS: uses `osascript` and requires accessibility permissions for terminal/apps that send input.
- Windows: uses the native Win32 `SendInput` keyboard API.

### Windows 7 branch note

The `win7-spike` branch lowers the runtime and build baseline so the app can be tested on Windows 7 SP1. It is a legacy-compatibility branch, not the preferred branch for Windows 10 or 11.

If you do not have a physical Windows 7 machine, use the VM workflow in [`docs/win7_vm.md`](docs/win7_vm.md).

## Windows 7 quick checklist

### Maintainer: prepare the installer

1. Keep the checked-in Windows build toolchain under [`vendor/windows/`](vendor/windows/). It is repo-committed offline build material for maintainers, not something end users interact with directly.
2. Build on a Windows 10 maintainer machine or inside a Windows 7 VM by running [`scripts/build_windows.ps1`](scripts/build_windows.ps1) or [`scripts/build_windows.bat`](scripts/build_windows.bat).
3. If the optional NSIS toolchain is vendored, the build produces `dist/windows/mobile-typer-win7-setup.exe`.
4. Deliver that installer to the Windows 7 user as the normal handoff artifact.

### End user: install on Windows 7

1. Double-click `mobile-typer-win7-setup.exe`.
2. Finish the installer.
3. Open `Mobile Remote` from the Start Menu or Desktop shortcut.
4. Keep the Windows 7 computer and the phone on the same network, open the QR code or local web address shown by the app, keep the target app focused, and use the phone buttons.

### Important Windows 7 note

The installer is meant to be the simple one-click path. However, some very old Windows 7 systems are still missing update `KB2533623`. Without it, the bundled Python 3.8 runtime may not start. That is a real Windows 7 platform limit, not a step the installer can fully work around.

## Run

Development convenience with `uv`:

```bash
uv run run_mobile_typer.py
```

Plain Python:

```bash
python3 run_mobile_typer.py
```

By default the server binds to `0.0.0.0:8000` so devices on the same network can reach it. When it starts, it opens a desktop window with the QR code for the preferred local URL so your phone can open it directly.

Common options:

```bash
python3 run_mobile_typer.py --port 8765
python3 run_mobile_typer.py --dry-run
python3 run_mobile_typer.py --no-gui
python3 run_mobile_typer.py --port 8000 --strict-port
```

`uv` remains in the repository for developer convenience only. It is not the authoritative Windows 7 build path.

## Use

1. Start the server on your computer.
2. Scan the QR code shown in the desktop window, or use the printed local network URL such as `http://192.168.1.23:8000`.
3. Open the page on your phone.
4. Focus the app on your computer that should receive the keypresses.
5. Tap any remote button from `A` through `R` on your phone. A single tap waits for the combo delay before it is sent.
6. Tap additional different buttons during that delay window to keep extending the combo. The delay restarts after each added button.
7. Tap `E / 2nd` to switch secondary mode on or off immediately. While the `2nd` switch is armed, the next button press keeps the old one-shot behavior and the switch then returns to off.
8. Tap `P` at any time to send it immediately as the stop button. It cancels any pending combo on the page and does not use the `2nd` mode.

## Test

```bash
PYTHONPATH=src python3 -m unittest tests.test_app
```

## Authoritative Windows 7 build and install

The authoritative Windows 7 packaging path is offline, repo-local, and deterministic-first:

- maintainer-only build ingredients live under [`vendor/windows/`](vendor/windows/)
- the checked-in PyInstaller definition is [`packaging/mobile_typer.spec`](packaging/mobile_typer.spec)
- the checked-in NSIS definition is [`packaging/mobile_typer_win7.nsi`](packaging/mobile_typer_win7.nsi)
- the build is prepared by [`scripts/build_windows.ps1`](scripts/build_windows.ps1) or [`scripts/build_windows.bat`](scripts/build_windows.bat)
- the normal artifact handed to an end user is `dist/windows/mobile-typer-win7-setup.exe`

Use these documents as the source of truth:

- [`docs/win7_build.md`](docs/win7_build.md)
- [`docs/win7_install.md`](docs/win7_install.md)
- [`docs/win7_vm.md`](docs/win7_vm.md)
- [`vendor/windows/README.md`](vendor/windows/README.md)

### Output layout

A successful authoritative Windows build produces:

```text
dist/windows/mobile-typer/
dist/windows/install_mobile_typer.ps1
dist/windows/install_mobile_typer.bat
dist/windows/mobile_typer_win7.nsi
dist/windows/vendor-manifest.json
dist/windows/vendor-SHA256SUMS.txt
dist/windows/build-manifest.json
dist/windows/SHA256SUMS.txt
```

If `vendor/windows/nsis/makensis.exe` has been vendored, the build also produces:

```text
dist/windows/mobile-typer-win7-setup.exe
```

### Important Windows 7 notes

- The build script does **not** download `uv`, Python, PyInstaller, NSIS, or any other tools.
- [`vendor/windows/`](vendor/windows/) is repo-committed maintainer/build material. It is not part of the normal end-user install story.
- The preferred end-user path is the NSIS installer `mobile-typer-win7-setup.exe`.
- [`scripts/install_mobile_typer.bat`](scripts/install_mobile_typer.bat) and [`scripts/install_mobile_typer.ps1`](scripts/install_mobile_typer.ps1) remain in the repo as maintainer and fallback tools, not the normal instructions for end users.
- Some Windows 7 machines still need update `KB2533623` before the bundled Python 3.8 runtime can load correctly.

### GitHub Actions status

The repository workflow no longer claims to publish a trusted Windows 7 binary. It validates the repo scaffolding only. A trusted Windows 7 installer should be built from the vendored offline toolchain on a Windows 10 machine you control or inside a Windows 7 VM that you control.

### Practical deployment summary

1. The repository carries the vendored Windows build toolchain under [`vendor/windows/`](vendor/windows/) as described in [`vendor/windows/manifest.json`](vendor/windows/manifest.json) and [`vendor/windows/README.md`](vendor/windows/README.md).
2. The maintainer builds on Windows 10 or inside the Windows 7 VM workflow from [`docs/win7_vm.md`](docs/win7_vm.md).
3. The maintainer delivers `dist/windows/mobile-typer-win7-setup.exe` as the normal installer for the Windows 7 user.
4. The Windows 7 user runs that installer and then launches `Mobile Remote` from the created shortcut.
5. If the installer cannot be produced or a special recovery case is needed, the maintainer may fall back to [`scripts/install_mobile_typer.bat`](scripts/install_mobile_typer.bat) or [`scripts/install_mobile_typer.ps1`](scripts/install_mobile_typer.ps1).
