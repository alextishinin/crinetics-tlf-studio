# TLF Studio — desktop shell (Electron)

Phase 2 of desktop packaging. Electron wraps the two sidecars into one
window:

```
Electron main (main.js)
  ├─ spawns backend.exe            (frozen FastAPI, port 8000)
  ├─ spawns Next standalone server (run with Electron's Node, port 3000)
  ├─ waits for /health + /studies, then opens the window
  └─ kills both sidecars on quit
```

It's `launch.bat`, but hidden, bundled, and self-cleaning. No Python, uv,
Node, or git needed on the target machine (Electron brings its own Node;
the backend is frozen).

## Why a Next *server* (not static export)

The app's routes — `/studies/[studyId]`, `…/preview/[tableId]` — are
client-rendered with **runtime** IDs (studies are created in the app), and
there's no `generateStaticParams`. App-Router static export requires every
dynamic param to be known at build time, so it can't represent these routes
without a large routing refactor. `output: "standalone"` runs the real Next
server and supports them with zero changes. Confirmed: the standalone server
serves `/studies/<any-id>` with HTTP 200.

## Run it in dev

Prerequisites (built once):

```cmd
:: 1. Freeze the backend  (see ../backend/BUILD.md)
cd ..\backend
.venv\Scripts\pyinstaller.exe backend.spec --noconfirm

:: 2. Build + assemble the frontend standalone
cd ..\frontend
npm run build
cd ..\desktop
npm run build:frontend     :: copies static/ + public/ into the standalone

:: 3. Launch the desktop app
npm install                :: first time only (installs Electron)
npm start
```

> Ports 8000 (backend) and 3000 (frontend) must be free — close the dev
> `launch.bat` app first, since it uses the same ports.
>
> The dev app (`next dev`) and the desktop app share `frontend/.next/`, so
> running the dev app **wipes the standalone build**. `npm start` detects this
> and rebuilds automatically (via the `prestart` hook), so you normally don't
> have to think about it — the first launch after running the dev app just
> takes ~30s longer.

Sidecar logs are written to the Electron `userData/logs/` directory
(`backend.log`, `frontend.log`) for troubleshooting.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `TLF_STUDIO_BACKEND_PORT` | 8000 | Backend port (must match the value the frontend was built with). |
| `TLF_STUDIO_FRONTEND_PORT` | 3000 | Next server port (any free port). |

## Packaging — installer + auto-update (Phase 3)

`electron-builder` builds a one-click NSIS installer; `electron-updater`
auto-updates from the public GitHub Releases of
`alextishinin/crinetics-tlf-studio`. The packaged app places `backend/` and
`frontend/` under `resources/` (matching the path logic in `main.js`).

### Build the installer

**One command** (from `desktop/`) — turns the current source into a fresh
installer. It re-vendors the tlf library, freezes the backend, builds the
frontend, and packages the installer:

```cmd
npm run build:app
```

Flags: `--skip-vendor` (use the committed `backend/vendor` instead of the
sibling repo). Re-run this whenever you change the **tlf library**, the
**backend**, the **frontend**, or the **Electron shell** — it rebuilds only
what's needed downstream and always repackages.

<details>
<summary>…or run the steps manually</summary>

```cmd
:: re-vendor the tlf library (only if you changed crinetics-tlf-automation)
cd ..\ && backend\.venv\Scripts\python.exe scripts\vendor_tlf.py
:: freeze the backend (only if you changed the backend / re-vendored)
cd backend && .venv\Scripts\pyinstaller.exe backend.spec --noconfirm
:: build the frontend (only if you changed it)
cd ..\frontend && npm run build
:: package
cd ..\desktop && npm run dist
```
</details>

Output → `desktop/dist-installer/`:

| File | Purpose |
|---|---|
| `TLF-Studio-Setup-<version>.exe` | the installer users run (~190 MB) |
| `latest.yml` | the update feed electron-updater reads |
| `*.exe.blockmap` | enables differential (delta) downloads |

The installer is **one-click, per-user** (installs to
`%LOCALAPPDATA%\Programs\TLF Studio`, no admin/UAC), and creates Desktop +
Start-menu shortcuts.

### Publish a release (enables auto-update)

**One command** — bumps the patch version, syncs `backend/config.py`
`APP_VERSION`, builds everything, and uploads to a GitHub Release:

```cmd
set GH_TOKEN=<token>     :: a GitHub token with repo scope, e.g. `gh auth token`
npm run release:app
```

For a minor/major bump, set the version first then skip the auto-bump:

```cmd
npm version minor --no-git-tag-version
node scripts/build-app.mjs --release --no-bump
```

On launch, the installed app checks the latest GitHub Release, downloads a
newer version in the background, and installs it on the next quit (a native
"update ready" notification appears). Because the repo is **public**, users
need no token.

### Notes / current gaps

- **Unsigned (v1).** No code-signing cert, so the first run shows a Windows
  SmartScreen "unknown publisher" prompt → *More info → Run anyway*. Add a
  cert later via electron-builder's `win.certificateFile` / `CSC_LINK`.
- **Default icon.** No app icon yet — drop a 256×256+ `build/icon.ico` (or
  `.png`) in `desktop/` and rebuild to brand it.
- **API key.** Set it in-app under **Settings** — paste the key and it's
  saved to `%APPDATA%\TLF Studio\config.json`, applied live, and verified with
  a test request. A first-run banner on the Studies page prompts for it when
  it's missing. (Editing that JSON by hand still works as a fallback.)
- **Updates / version.** Settings shows the app version and a "Check for
  updates" button; updates otherwise install automatically on quit.
- **Startup failures** show a friendly screen with **Try again** + **Open
  logs** instead of a blank window.
