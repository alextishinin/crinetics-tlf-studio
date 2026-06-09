# Freezing the backend (`backend.exe`)

Phase 1 of desktop packaging: the FastAPI backend is bundled into a
self-contained `backend.exe` with PyInstaller — no Python/uv required on the
target machine. (Electron wrapping + installer + auto-update are later phases.)

## How it's made self-contained

- **Vendored library.** The `crinetics-tlf-automation` `tlf` package plus its
  `shells/` registry and default `config/` are copied into `backend/vendor/`
  by `scripts/vendor_tlf.py`. The backend prefers this vendored copy and only
  falls back to the sibling repo when `vendor/` is absent (see `config.py`).
- **Per-user storage.** When frozen, studies live in
  `%APPDATA%\TLF Studio\studies` (Program Files is read-only) and the
  Anthropic API key is read from `%APPDATA%\TLF Studio\config.json` or `.env`.
  In dev nothing changes (`.env` + `./studies`).

## Build steps

From `backend/`:

```cmd
:: 1. Refresh the vendored library from the sibling automation repo
uv run python ..\scripts\vendor_tlf.py

:: 2. Freeze (one-dir build)
.venv\Scripts\pyinstaller.exe backend.spec --noconfirm
```

Output: `dist/backend/backend.exe` (+ `dist/backend/_internal/`). The whole
`dist/backend/` folder is the shippable unit (~300 MB).

## Verify standalone

```cmd
set TLF_STUDIO_PORT=8131
dist\backend\backend.exe
```

Then check `http://127.0.0.1:8131/health` → `{"status":"ok",...}`. Table,
figure, and RTF generation all run inside the frozen exe (polars / matplotlib
/ pyreadstat / rtflite are bundled).

## Notes / gotchas

- `dist/` and `build/` are git-ignored; `vendor/` is committed.
- The scientific stack drives the bundle size and is the main freeze risk;
  `backend.spec` pulls them in via `collect_all` + `collect_submodules`.
- `run_server.py` is the frozen entrypoint (in-process uvicorn, Agg backend).
- Re-run `vendor_tlf.py` after changing the automation repo so the build and
  dev both pick up the change.
