# Offline Wheelhouse

Keep the exact wheel files listed in [`../manifest.json`](../manifest.json) committed in this directory.

[`scripts/build_windows.ps1`](../../../scripts/build_windows.ps1) installs from this wheelhouse with `--no-index`, so no network access occurs during the authoritative Windows build.
