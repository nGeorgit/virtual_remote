# Windows 7 Install Workflow

This document is the authoritative install procedure for artifacts produced by the Windows 7 build flow.

## Files produced by the build

The bundle in `dist/windows/` always contains:

- `mobile-typer/` — the canonical onedir application payload
- `install_mobile_typer.ps1` — reliable fallback installer logic
- `install_mobile_typer.bat` — launcher for the PowerShell installer
- `mobile_typer_win7.nsi` — checked-in NSIS installer definition
- `vendor-manifest.json` — copy of the authoritative vendored input manifest
- `vendor-SHA256SUMS.txt` — copy of the vendored input hash list
- `build-manifest.json` — generated output manifest
- `SHA256SUMS.txt` — generated hashes for the built bundle

If NSIS is vendored and available during the build, the bundle also contains:

- `mobile-typer-win7-setup.exe`

## What to hand to someone else

When deploying to another Windows 7 machine, send the whole `dist/windows/` directory or a zip created from it. Keep these files side by side after extraction:

- `mobile-typer/`
- `install_mobile_typer.bat`
- `install_mobile_typer.ps1`
- `SHA256SUMS.txt`
- `build-manifest.json`
- optional `mobile-typer-win7-setup.exe`

Do not separate `install_mobile_typer.bat` from the sibling `mobile-typer/` directory, because the batch launcher assumes that relative layout.

## Preferred install choices

### 1. If `mobile-typer-win7-setup.exe` exists

Run the NSIS installer when you want a standard Windows installer experience and the vendored NSIS toolchain has already been trusted.

### 2. Otherwise use the fallback installer scripts

Run:

```bat
install_mobile_typer.bat
```

or:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_mobile_typer.ps1 -SourcePath .\mobile-typer -LaunchAfterInstall
```

The fallback installer remains important even after NSIS support exists because it also supports optional firewall and auto-start integration.

## Exact fallback install steps on the target Windows 7 machine

1. Copy the built `dist/windows/` directory to the target machine.
2. If it was transferred as a zip, extract it fully before running anything.
3. Open the extracted folder and confirm that `install_mobile_typer.bat` sits next to the `mobile-typer/` directory.
4. Double-click `install_mobile_typer.bat` for the normal per-user install path.
5. If you want the firewall rule to be created automatically, rerun the PowerShell installer from an Administrator shell instead of the batch file.
6. After install, start `Mobile Remote` from the Start Menu or Desktop shortcut.

Example Administrator rerun:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_mobile_typer.ps1 -SourcePath .\mobile-typer -LaunchAfterInstall
```

Add `-AutoStart` if that Windows 7 user wants the app to start at login.

## What the fallback installer does

[`scripts/install_mobile_typer.ps1`](../scripts/install_mobile_typer.ps1):

- accepts the canonical onedir directory first and falls back to a single `mobile-typer.exe` if needed
- clears the previous `%LocalAppData%\MobileTyper` contents before copying the new payload
- creates Start Menu and Desktop shortcuts
- can enable auto-start on login with `-AutoStart`
- can add or refresh the firewall rule when run as Administrator
- falls back from `NetSecurity` cmdlets to `netsh advfirewall` for older Windows installations

## Manual verification after install

1. Launch `Mobile Remote` from the Start Menu or Desktop.
2. Confirm that the window opens and shows a QR code and at least one local URL.
3. Open the displayed URL from a phone on the same LAN.
4. Focus a non-elevated target application in the Windows 7 session.
5. Confirm that button presses from the phone arrive in that target application.
6. If firewall access fails, rerun the PowerShell installer as Administrator without `-SkipFirewallRule`.

## Network and usage notes for the recipient

- The Windows 7 machine and the phone must be on the same LAN.
- `Mobile Remote` shows the phone URL and QR code when it starts.
- Keep the target application focused while sending keys.
- Prefer a non-elevated target app; Windows can block `SendInput` into elevated targets.

## Windows 7 caveats

- Some Windows 7 systems need update `KB2533623` before the bundled Python 3.8 runtime will start.
- `SendInput` can fail when the target app is elevated or otherwise blocks injected input.
- When troubleshooting, prefer the onedir bundle because every shipped file is directly inspectable.
