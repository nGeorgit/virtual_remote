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

- build inputs live under [`vendor/windows/`](vendor/windows/)
- the canonical artifact is the onedir bundle at `dist/windows/mobile-typer/`
- the authoritative builder is [`scripts/build_windows.ps1`](scripts/build_windows.ps1) or [`scripts/build_windows.bat`](scripts/build_windows.bat)
- the checked-in PyInstaller definition is [`packaging/mobile_typer.spec`](packaging/mobile_typer.spec)
- the checked-in NSIS definition is [`packaging/mobile_typer_win7.nsi`](packaging/mobile_typer_win7.nsi)

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
- The repository ships the vendor manifest and placeholder hash files now; fill them in when the actual artifacts are vendored.
- The PowerShell installer remains the reliable fallback because it also handles optional auto-start and the Windows Firewall rule.
- The NSIS installer definition is checked in for deterministic packaging, but its binary toolchain must be vendored before it becomes fully buildable.
- Some Windows 7 machines need update `KB2533623` before newer Python 3.8 runtime files can load correctly.

### GitHub Actions status

The repository workflow no longer claims to publish a trusted Windows 7 binary. It validates the repo scaffolding only. A trusted Windows 7 bundle should be built from the vendored offline toolchain on a Windows machine or a Windows 7 VM that you control.

### Practical deployment summary

1. Populate [`vendor/windows/`](vendor/windows/) exactly as described in [`vendor/windows/manifest.json`](vendor/windows/manifest.json) and [`vendor/windows/README.md`](vendor/windows/README.md).
2. Build on Windows with [`scripts/build_windows.ps1`](scripts/build_windows.ps1) or inside the Windows 7 VM workflow from [`docs/win7_vm.md`](docs/win7_vm.md).
3. Hand over the entire `dist/windows/` output directory, preserving the sibling layout of `mobile-typer/`, `install_mobile_typer.bat`, `install_mobile_typer.ps1`, and the manifest/hash files.
4. On the destination Windows 7 machine, prefer `mobile-typer-win7-setup.exe` when it exists. Otherwise run `install_mobile_typer.bat` from the unpacked `dist/windows/` directory.
5. If the phone cannot connect after install, rerun [`install_mobile_typer.ps1`](scripts/install_mobile_typer.ps1) as Administrator so it can add the firewall rule.
6. Launch `Mobile Remote`, open the shown LAN URL or QR code from the phone, and keep the target Windows app focused and non-elevated while sending keys.
