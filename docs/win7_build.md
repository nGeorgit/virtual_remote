# Windows 7 Build Workflow

This document is the authoritative maintainer workflow for producing Windows 7 artifacts.

## Short version

- Build on a Windows 10 maintainer machine or inside a Windows 7 VM.
- [`vendor/windows/`](../vendor/windows/) is only for the maintainer who prepares the build. It is just the offline ingredient box for the build machine.
- The normal artifact you hand to an end user is `dist/windows/mobile-typer-win7-setup.exe`.
- End users should not be told to browse `vendor/windows/` or manually run the PowerShell installer scripts in the normal path.

## Maintainer checklist

1. Put the Windows build ingredients into [`vendor/windows/`](../vendor/windows/).
2. Treat [`vendor/windows/`](../vendor/windows/) as maintainer-only material:
   - `python/` holds the Windows Python 3.8 runtime used for the build
   - `wheels/` holds the offline Python packages used for the build
   - `nsis/` holds the optional NSIS toolchain used to make the final installer `.exe`
3. Build on either of these maintainer environments:
   - a Windows 10 machine you control
   - a Windows 7 VM using the workflow in [`docs/win7_vm.md`](win7_vm.md)
4. Run [`scripts/build_windows.ps1`](../scripts/build_windows.ps1) or [`scripts/build_windows.bat`](../scripts/build_windows.bat).
5. If NSIS is vendored, confirm that the build produced `dist/windows/mobile-typer-win7-setup.exe`.
6. Deliver that NSIS installer to the Windows 7 user as the normal handoff.

## End-user handoff

The simplest supported end-user story is:

1. A maintainer prepares the build.
2. The maintainer gives the Windows 7 user `mobile-typer-win7-setup.exe`.
3. The Windows 7 user runs that installer.
4. The user opens `Mobile Remote` from the created shortcut.

That is the blessed path. The fallback scripts are for maintainer recovery cases, packaging validation, or situations where the NSIS installer could not be produced.

## What `vendor/windows/` means in plain language

[`vendor/windows/`](../vendor/windows/) is not an end-user folder.

It is simply the maintainer's local stash of Windows build ingredients that the repo expects to find in a fixed layout. Those files are used on the build machine so the build can run without downloading tools from the network.

End users do not need to copy it, understand it, or touch it.

## Goal

Produce a deterministic-first, offline, repo-local Windows bundle whose main deliverable for users is the NSIS installer `dist/windows/mobile-typer-win7-setup.exe`.

The onedir payload in `dist/windows/mobile-typer/` remains the canonical staged application payload used to build and support that installer.

## Authoritative inputs

The authoritative build inputs are laid out under [`vendor/windows/`](../vendor/windows/):

- [`vendor/windows/manifest.json`](../vendor/windows/manifest.json)
- [`vendor/windows/SHA256SUMS.txt`](../vendor/windows/SHA256SUMS.txt)
- [`vendor/windows/python/`](../vendor/windows/python/)
- [`vendor/windows/wheels/`](../vendor/windows/wheels/)
- [`vendor/windows/nsis/`](../vendor/windows/nsis/)

Populate those directories with the exact binaries and wheels listed in the manifest. Do not change the layout after downstream documentation or automation starts depending on it.

## Why this flow replaced `uv`

Previous Windows packaging relied on `uv` to download or resolve the active toolchain. That is not authoritative enough for a Windows 7 compatibility branch.

The current build flow instead:

1. requires a vendored Python 3.8 runtime from the repository itself
2. installs pinned build requirements from the repo-local wheelhouse with `--no-index`
3. builds from the checked-in PyInstaller spec file
4. emits hashes and a build manifest into `dist/windows/`
5. builds the NSIS installer when the optional vendored NSIS toolchain is present

`uv` can still be used for day-to-day development, but it is not part of this Windows 7 build path.

## Before you start

Before running the build, make sure all of the following are true:

1. The repository checkout already contains the exact offline inputs declared in [`vendor/windows/manifest.json`](../vendor/windows/manifest.json).
2. The placeholder hashes in [`vendor/windows/SHA256SUMS.txt`](../vendor/windows/SHA256SUMS.txt) and [`vendor/windows/manifest.json`](../vendor/windows/manifest.json) have been replaced with real digests once the artifacts are vendored.
3. You have read [`vendor/windows/README.md`](../vendor/windows/README.md) so the `python/`, `wheels/`, and optional `nsis/` layout matches what the scripts expect.
4. If you want the normal Windows installer `.exe`, `vendor/windows/nsis/makensis.exe` is present.

## Build command

From a Windows 10 maintainer machine or from inside the Windows 7 VM:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

or:

```bat
scripts\build_windows.bat
```

The script intentionally fails if required vendored inputs are missing.

## What the script does

[`scripts/build_windows.ps1`](../scripts/build_windows.ps1):

1. validates [`vendor/windows/manifest.json`](../vendor/windows/manifest.json)
2. verifies that the vendored Python runtime exists and reports Python 3.8
3. verifies that the offline wheelhouse files exist
4. creates `.build/windows/venv`
5. installs [`packaging/windows-build-requirements.txt`](../packaging/windows-build-requirements.txt) from `vendor/windows/wheels` with `--no-index`
6. runs PyInstaller with [`packaging/mobile_typer.spec`](../packaging/mobile_typer.spec)
7. stages installer scripts plus vendor manifests into `dist/windows/`
8. optionally builds [`packaging/mobile_typer_win7.nsi`](../packaging/mobile_typer_win7.nsi) if `vendor/windows/nsis/makensis.exe` is present
9. writes `dist/windows/SHA256SUMS.txt` and `dist/windows/build-manifest.json`

## Main artifact for users

When NSIS is vendored, the main file to deliver to a Windows 7 user is:

```text
dist/windows/mobile-typer-win7-setup.exe
```

That is the intended normal install experience.

## Supporting output layout

A successful build also produces or stages:

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

The onedir payload remains important for reproducibility, inspection, and maintainer troubleshooting, but it is not the normal thing handed to the end user when the installer exists.

## If NSIS is not vendored

If NSIS is not vendored yet, the build still stages the checked-in installer definition into `dist/windows/mobile_typer_win7.nsi` and keeps the fallback installer scripts beside the payload.

That is a maintainer limitation, not the preferred end-user story. When possible, vendor NSIS and ship the final installer `.exe`.

## Signing

The build script keeps the existing optional signing hook:

- `MOBILE_TYPER_SIGN_PFX`
- `MOBILE_TYPER_SIGN_PFX_PASSWORD`
- optional `MOBILE_TYPER_SIGN_TIMESTAMP_URL`

Signing is optional and local. The build does not fetch certificates or timestamp tooling.

## KB2533623 note in simple terms

The installer is intended to be a one-click experience on Windows 7. However, some older Windows 7 systems still do not have update `KB2533623`. If that system component is missing, the bundled Python 3.8 runtime may fail to start even though the installer itself ran.

That is a real Windows 7 platform limit and should be treated as such.

## Reproducibility notes

The build script fixes `PYTHONHASHSEED=0`, sets `SOURCE_DATE_EPOCH` when it is unset, uses pinned requirements, and depends only on repo-local inputs. Exact binary reproducibility still depends on the final vendored toolchain staying unchanged, including wheel contents and the Python runtime bits.
