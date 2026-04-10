# Mobile Typer

`mobile-typer` starts a small local web server that serves:

- a portrait hardware-style virtual remote with buttons `A` through `R`
- a local JSON API used by that page

When you tap a button from your phone, the page now waits briefly before sending it so it can detect a combo. Each additional button tapped during that window is added to the same combo and restarts the delay. When the delay expires, the computer running the server sends the full combo to the currently focused app on that computer. The `P` stop button is the exception: it bypasses the delay, clears any pending combo on the page, ignores secondary mode, and is sent immediately. By default the app also opens a small desktop window that shows the QR code and local phone URL.

## Requirements

- `uv`
- Python 3.11+
- Your phone and computer must be on the same Wi-Fi network
- Keep the target app focused on your computer

### Platform notes

- Linux: this implementation uses X11/XTest. It is intended for X11 sessions.
- macOS: uses `osascript` and requires accessibility permissions for terminal/apps that send input.
- Windows: uses the native Win32 keyboard event API.

## Run

```bash
uv run run_mobile_typer.py
```

By default the server binds to `0.0.0.0:8000` so devices on the same network can reach it.
When it starts, it opens a desktop window with the QR code for the preferred local URL so your phone can open it directly.

You can also choose a custom port:

```bash
uv run run_mobile_typer.py --port 8765
```

If you only want to test the webpage and API without sending real keypresses:

```bash
uv run run_mobile_typer.py --dry-run
```

If you want the old terminal-only mode instead of the QR window:

```bash
uv run run_mobile_typer.py --no-gui
```

If you want the app to fail instead of switching to another free port when the chosen port is busy:

```bash
uv run run_mobile_typer.py --port 8000 --strict-port
```

If you prefer the package entrypoint, `uv run mobile-typer` is also configured in `pyproject.toml`.

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
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Build A Windows EXE

The Windows build now produces a windowed `.exe`, not a console executable. The QR code and the local URLs appear in the app window itself.

### Build on Windows locally

On a Windows machine, run:

```bat
scripts\build_windows.bat
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

The build script checks for everything it needs. If `uv` is missing, it downloads a local copy into the repository. If a supported Python is missing, it installs it through `uv`. Then it runs the PyInstaller build. You do not need to preinstall `uv` on the Windows build machine.

That produces:

```text
dist\mobile-typer.exe
```

It also stages:

```text
dist\install_mobile_typer.ps1
dist\install_mobile_typer.bat
```

That `.exe` is what you send to the client. The client does not need `uv` or Python installed.

### Install on the client machine

You can give the client the files from `dist\`.

- `mobile-typer.exe`: the app itself
- `install_mobile_typer.bat`: a simple installer launcher
- `install_mobile_typer.ps1`: the installer logic

The installer copies the app into `%LocalAppData%\MobileTyper`, creates Start Menu and Desktop shortcuts, can enable auto-start on login, and can add a Windows Firewall rule when run as Administrator.

### Optional code signing prep

The Windows build script already includes version metadata and an optional signing hook.

- Set `MOBILE_TYPER_SIGN_PFX` to a `.pfx` certificate path.
- Set `MOBILE_TYPER_SIGN_PFX_PASSWORD` to the certificate password.
- Optionally set `MOBILE_TYPER_SIGN_TIMESTAMP_URL` for timestamping.

If those variables are not set, the build still works and simply skips signing.

### Build on GitHub Actions

This repo now includes a workflow at `.github/workflows/build-windows-exe.yml`.

1. Push the repository to GitHub.
2. Open the `build-windows-exe` workflow.
3. Run it manually with `workflow_dispatch`.
4. Download the `mobile-typer-windows-bundle` artifact.

### Client behavior on Windows

- The client runs `mobile-typer.exe`.
- A desktop window opens and shows the QR code and local URL.
- The focused Windows app receives the matching `a` through `r` keypresses.
- Closing the app window stops the server.
- If the preferred port is busy, the app automatically switches to another free port unless you built or ran it with strict port expectations.
