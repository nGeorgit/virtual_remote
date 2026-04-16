# Windows 7 Build Workflow

This document is the authoritative build procedure for Windows 7 artifacts.

## Goal

Produce a deterministic-first, offline, repo-local Windows bundle whose canonical output is the onedir directory `dist/windows/mobile-typer/`.

## Authoritative inputs

The authoritative build inputs are checked in as layout plus metadata under [`vendor/windows/`](../vendor/windows/):

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
5. optionally builds the NSIS installer only when the NSIS binary has also been vendored

`uv` can still be used for day-to-day development, but it is not part of this Windows 7 build path.

## Before you start

Before running the build, make sure all of the following are true:

1. The repository checkout already contains the exact offline inputs declared in [`vendor/windows/manifest.json`](../vendor/windows/manifest.json).
2. The placeholder hashes in [`vendor/windows/SHA256SUMS.txt`](../vendor/windows/SHA256SUMS.txt) and [`vendor/windows/manifest.json`](../vendor/windows/manifest.json) have been replaced with real digests once the artifacts are vendored.
3. You have read [`vendor/windows/README.md`](../vendor/windows/README.md) so the `python/`, `wheels/`, and optional `nsis/` layout matches what the scripts expect.
4. If you want a standard installer `.exe`, `vendor/windows/nsis/makensis.exe` is present; otherwise the build will stop at the fallback scriptable installer outputs.

## Build command

From a Windows machine with the repository checked out:

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

## Canonical artifact

The canonical Windows 7 artifact is the onedir bundle:

```text
dist/windows/mobile-typer/
```

That choice is deliberate:

- it reduces fragility compared with a onefile self-extractor
- it is easier to inspect and hash
- it is friendlier to legacy Windows troubleshooting
- it keeps the installer and fallback script paths aligned around the same payload directory

## Optional installer output

If NSIS is vendored, the same build also emits:

```text
dist/windows/mobile-typer-win7-setup.exe
```

If NSIS is not vendored yet, the build still stages the checked-in installer definition into `dist/windows/mobile_typer_win7.nsi` and leaves the PowerShell installer as the practical fallback.

## Signing

The build script keeps the existing optional signing hook:

- `MOBILE_TYPER_SIGN_PFX`
- `MOBILE_TYPER_SIGN_PFX_PASSWORD`
- optional `MOBILE_TYPER_SIGN_TIMESTAMP_URL`

Signing is optional and local. The build does not fetch certificates or timestamp tooling.

## What to hand to the installer operator

After a successful build, hand over the whole `dist/windows/` directory as one unit. Do not send only `mobile-typer.exe` by itself for the Windows 7 path.

The minimum practical handoff is:

- `dist/windows/mobile-typer/`
- `dist/windows/install_mobile_typer.bat`
- `dist/windows/install_mobile_typer.ps1`
- `dist/windows/SHA256SUMS.txt`
- optionally `dist/windows/mobile-typer-win7-setup.exe` if NSIS was vendored

That preserves the authoritative onedir payload plus the fallback installer path described in [`docs/win7_install.md`](win7_install.md).

## Reproducibility notes

The build script fixes `PYTHONHASHSEED=0`, sets `SOURCE_DATE_EPOCH` when it is unset, uses pinned requirements, and depends only on repo-local inputs. Exact binary reproducibility still depends on the final vendored toolchain staying unchanged, including wheel contents and the Python runtime bits.
