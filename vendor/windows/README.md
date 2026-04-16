# Vendored Windows Build Inputs

This directory is the authoritative, offline, repo-local input root for Windows 7 builds.

The repository currently contains only the structure, manifest, and placeholder hash list. Add the actual third-party binaries and wheels later without changing the directory layout.

## Required layout

- `python/python.exe`: a vendored CPython 3.8.x runtime used to create the build venv.
- `wheels/*.whl`: the exact offline wheelhouse declared in [`vendor/windows/manifest.json`](manifest.json).
- `nsis/makensis.exe`: optional. If present, [`scripts/build_windows.ps1`](../../scripts/build_windows.ps1) also builds the NSIS installer from [`packaging/mobile_typer_win7.nsi`](../../packaging/mobile_typer_win7.nsi).

## Determinism rules

1. Keep artifact filenames exactly as listed in [`manifest.json`](manifest.json).
2. Replace every `TO_BE_FILLED` digest in [`SHA256SUMS.txt`](SHA256SUMS.txt) and [`manifest.json`](manifest.json) after vendoring.
3. Do not let the Windows build pull tools from the network. The build script intentionally fails instead.
4. Treat [`scripts/build_windows.ps1`](../../scripts/build_windows.ps1) plus this directory as the only authoritative Windows 7 build path.
