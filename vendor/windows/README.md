# Vendored Windows Build Inputs

This directory is the authoritative, offline, repo-local input root for Windows 7 builds.

The intended workflow is that the real third-party Windows build toolchain artifacts live here in git under [`vendor/windows/`](./). [`scripts/build_windows.ps1`](../../scripts/build_windows.ps1) reads this checked-in directory directly by default.

If the repository currently contains only the manifest, hashes, and README scaffolding, the real payload still needs to be added manually before the authoritative Windows build can run.

## Required layout

- `python/python.exe`: a vendored full CPython 3.8.x runtime used to create the build venv.
- `python/Lib/tkinter`, `python/DLLs/_tkinter.pyd`, `python/DLLs/tcl86t.dll`, `python/DLLs/tk86t.dll`, and `python/tcl/`: required GUI runtime pieces that must be present in the committed CPython tree.
- `wheels/*.whl`: the exact offline wheelhouse declared in [`vendor/windows/manifest.json`](manifest.json).
- `nsis/makensis.exe`: optional. If present, [`scripts/build_windows.ps1`](../../scripts/build_windows.ps1) also builds the NSIS installer from [`packaging/mobile_typer_win7.nsi`](../../packaging/mobile_typer_win7.nsi).

## Determinism rules

1. Keep artifact filenames exactly as listed in [`manifest.json`](manifest.json).
2. When the vendored toolchain is updated, commit the matching digest changes in [`SHA256SUMS.txt`](SHA256SUMS.txt) and [`manifest.json`](manifest.json) in the same change.
3. Do not let the Windows build pull tools from the network. The build script intentionally fails instead.
4. Treat [`scripts/build_windows.ps1`](../../scripts/build_windows.ps1) plus this directory as the only authoritative Windows 7 build path.
