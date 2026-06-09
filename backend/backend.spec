# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the TLF Studio backend.

Freezes run_server.py (uvicorn + FastAPI app + the vendored tlf library)
into a self-contained backend.exe (one-dir build). Build from backend/:

    uv run pyinstaller backend.spec --noconfirm

Output: dist/backend/backend.exe
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = []
binaries = []
hiddenimports = []

# --- Vendored tlf data files (shell specs + default study config) ----------
# Keep the vendor/ layout so the registry's relative shell_files resolve.
datas += [
    ("vendor/shells", "vendor/shells"),
    ("vendor/config", "vendor/config"),
]

# --- Scientific stack: pull code + data + native libs ----------------------
# These are the packages that PyInstaller's static analysis tends to miss
# data files or compiled extensions for.
for _pkg in ("rtflite", "pyreadstat", "matplotlib", "pdfplumber", "pdfminer", "mammoth"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# polars / lxml ship single native extensions handled by contrib hooks; make
# sure they're pulled in regardless.
hiddenimports += ["polars", "polars.polars", "lxml", "lxml._elementpath", "markdownify"]

# --- Dynamic imports our code does at runtime ------------------------------
# The vendored tlf package and uvicorn protocol modules are imported by name
# / inside functions, so collect every submodule explicitly.
hiddenimports += collect_submodules("tlf")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("anthropic")

# Our own backend modules that are reached only via importlib / string refs.
hiddenimports += [
    "main",
    "config",
    "routers.ai",
    "routers.jobs",
    "routers.outputs",
    "routers.preview",
    "routers.settings",
    "routers.shells",
    "routers.studies",
]


a = Analysis(
    ["run_server.py"],
    pathex=[".", "vendor/src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PySide2", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="backend",
)
