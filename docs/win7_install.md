# Windows 7 Install Workflow

This document is the authoritative install procedure for artifacts produced by the Windows 7 build flow.

## The normal end-user path

The normal supported user experience is intentionally simple:

1. A maintainer builds the Windows 7 package.
2. The maintainer gives the user `mobile-typer-win7-setup.exe`.
3. The user double-clicks that installer.
4. The installer copies the app, creates shortcuts, and tries to add the normal firewall rule when it is allowed to do so.
5. The user opens `Mobile Remote` from the created shortcut.

End users should not normally be told to browse [`vendor/windows/`](../vendor/windows/), unpack installer ingredients, or manually run [`scripts/install_mobile_typer.bat`](../scripts/install_mobile_typer.bat) or [`scripts/install_mobile_typer.ps1`](../scripts/install_mobile_typer.ps1).

## Simple end-user checklist

### What the maintainer sends

- `mobile-typer-win7-setup.exe`

### What the Windows 7 user does

1. Double-click `mobile-typer-win7-setup.exe`.
2. Complete the installer.
3. Open `Mobile Remote` from the Start Menu or Desktop shortcut.
4. Keep the Windows 7 computer and the phone on the same network.
5. Open the QR code or local web address shown by `Mobile Remote`.
6. Keep the Windows program you want to control focused.
7. Tap buttons on the phone.

## Important Windows 7 limit

The installer is meant to be the one-click path. However, some older Windows 7 machines still do not have update `KB2533623`. If that system component is missing, the bundled Python 3.8 runtime may not start even though the installer copied the files correctly.

That is a real platform limit on some old Windows 7 systems. This repo cannot fully solve it from inside the installer.

## Files produced by the build

The bundle in `dist/windows/` always contains:

- `mobile-typer/` — the canonical onedir application payload
- `install_mobile_typer.ps1` — maintainer and fallback installer logic
- `install_mobile_typer.bat` — launcher for the PowerShell fallback installer
- `mobile_typer_win7.nsi` — checked-in NSIS installer definition
- `vendor-manifest.json` — copy of the authoritative vendored input manifest
- `vendor-SHA256SUMS.txt` — copy of the vendored input hash list
- `build-manifest.json` — generated output manifest
- `SHA256SUMS.txt` — generated hashes for the built bundle

If NSIS is vendored and available during the build, the bundle also contains:

- `mobile-typer-win7-setup.exe`

## What the NSIS installer now covers

The installer in [`packaging/mobile_typer_win7.nsi`](../packaging/mobile_typer_win7.nsi) is the preferred end-user path because it handles the normal install work directly on the target machine without needing PowerShell:

- copies the onedir payload into `%LocalAppData%\MobileTyper`
- creates the Start Menu shortcut
- creates the Desktop shortcut
- writes an uninstaller
- registers the app in Add/Remove Programs for the current user
- tries to add the inbound Windows Firewall rule with `netsh advfirewall` when the installer is allowed to run elevated

That covers the normal installer story for most users.

## What to hand to someone else

For the normal supported user path, send the NSIS installer:

- `dist/windows/mobile-typer-win7-setup.exe`

For maintainer validation, archive, or recovery use, keep the whole `dist/windows/` directory together.

## Maintainer-only fallback path

[`scripts/install_mobile_typer.bat`](../scripts/install_mobile_typer.bat) and [`scripts/install_mobile_typer.ps1`](../scripts/install_mobile_typer.ps1) still exist, but they are now maintainer and fallback tools.

Use them only when one of these applies:

- NSIS was not vendored, so the build could not produce the final installer
- you are validating packaging internals as a maintainer
- you need a recovery install path during troubleshooting
- you specifically need options from the PowerShell installer such as `-AutoStart`

They are no longer the normal instructions for end users.

## What the fallback installer still does

[`scripts/install_mobile_typer.ps1`](../scripts/install_mobile_typer.ps1):

- accepts the canonical onedir directory first and falls back to a single `mobile-typer.exe` if needed
- clears the previous `%LocalAppData%\MobileTyper` contents before copying the new payload
- creates Start Menu and Desktop shortcuts
- can enable auto-start on login with `-AutoStart`
- can add or refresh the firewall rule when run as Administrator
- falls back from `NetSecurity` cmdlets to `netsh advfirewall` for older Windows installations

Those features are still useful for maintainers, but they are not the primary Windows 7 user story.

## Manual verification after install

1. Launch `Mobile Remote` from the Start Menu or Desktop.
2. Confirm that the window opens and shows a QR code and at least one local URL.
3. Open the displayed URL from a phone on the same LAN.
4. Focus a non-elevated target application in the Windows 7 session.
5. Confirm that button presses from the phone arrive in that target application.
6. If the app does not start on an older machine, treat missing `KB2533623` as a possible hard platform limit.

## Network and usage notes for the recipient

- The Windows 7 machine and the phone must be on the same LAN.
- `Mobile Remote` shows the phone URL and QR code when it starts.
- Keep the target application focused while sending keys.
- Prefer a non-elevated target app; Windows can block `SendInput` into elevated targets.

## Maintainer summary

The workflow is intentionally split:

- Maintainer side: prepare [`vendor/windows/`](../vendor/windows/), build on Windows 10 or in a Windows 7 VM, and produce the NSIS installer.
- End-user side: run `mobile-typer-win7-setup.exe` and use the created shortcut.

That keeps PowerShell and repo build details away from the normal Windows 7 user.
