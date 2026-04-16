# NSIS Placeholder

Place `makensis.exe` and any supporting NSIS files here when vendoring the optional installer toolchain.

If this directory remains empty, [`scripts/build_windows.ps1`](../../../scripts/build_windows.ps1) still builds the canonical onedir bundle and stages [`packaging/mobile_typer_win7.nsi`](../../../packaging/mobile_typer_win7.nsi) for later use.
