# Vendored Python Runtime

Commit the authoritative Windows build Python runtime here as `python.exe` plus the rest of the full CPython 3.8.x directory tree.

This vendored runtime must include Tk/Tcl support for the GUI build, including `Lib/tkinter/`, `DLLs/_tkinter.pyd`, `DLLs/tcl86t.dll`, `DLLs/tk86t.dll`, and the `tcl/` subtree.

The build script expects the interpreter at `vendor/windows/python/python.exe` and verifies that it reports Python 3.8 before building.
