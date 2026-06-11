"use strict";

// TLF Studio desktop shell.
//
// Spawns two sidecars on localhost — the frozen Python backend (backend.exe)
// and the Next.js standalone server (run with Electron's own Node) — waits for
// both to answer, then opens the app window. Kills the sidecars on quit.
// It's launch.bat, but hidden and bundled.

const { app, BrowserWindow, shell, ipcMain, Menu } = require("electron");
const { autoUpdater } = require("electron-updater");

// No native menu bar (File / Edit / View / Window) — this is a single-purpose
// app and doesn't need it.
Menu.setApplicationMenu(null);
const path = require("path");
const fs = require("fs");
const http = require("http");
const { spawn } = require("child_process");

// Backend port is fixed: the frontend bundles http://localhost:8000 as its API
// base at build time. The frontend's own port can be anything we like.
const BACKEND_PORT = Number(process.env.TLF_STUDIO_BACKEND_PORT || 8000);
const FRONTEND_PORT = Number(process.env.TLF_STUDIO_FRONTEND_PORT || 3000);
const HOST = "127.0.0.1";
const STARTUP_TIMEOUT_MS = 60_000;

const isDev = !app.isPackaged;
let backendProc = null;
let frontendProc = null;
let mainWindow = null;
let shuttingDown = false;

// GET a URL and resolve with { ok, body } so we can tell "our backend is
// already there" apart from "some other app owns the port".
function fetchBody(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve({ ok: (res.statusCode || 500) < 500, body }));
    });
    req.on("error", () => resolve({ ok: false, body: "" }));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve({ ok: false, body: "" });
    });
  });
}

// The frontend bakes http://localhost:8000 in at build time, so the backend
// port is not negotiable. If something else already owns it, starting our
// sidecar would silently talk to the wrong server — fail with a clear
// message instead.
async function portConflict() {
  const { ok, body } = await fetchBody(`http://${HOST}:${BACKEND_PORT}/health`);
  if (!ok) return null; // port free (or unresponsive — startup will retry)
  if (body.includes("tlf-studio")) {
    return (
      `TLF Studio's data engine is already running on port ${BACKEND_PORT} ` +
      "(another copy of the app, or a dev server). Close it and press Retry."
    );
  }
  return (
    `Another application is using port ${BACKEND_PORT}, which TLF Studio needs. ` +
    "Close it and press Retry."
  );
}

// --- resource locations ----------------------------------------------------
function resolvePaths() {
  if (isDev) {
    const root = path.join(__dirname, "..");
    return {
      backendExe: path.join(root, "backend", "dist", "backend", "backend.exe"),
      frontendDir: path.join(root, "frontend", ".next", "standalone"),
    };
  }
  // Packaged (Phase 3 arranges these under resources/ via extraResources).
  const res = process.resourcesPath;
  return {
    backendExe: path.join(res, "backend", "backend.exe"),
    frontendDir: path.join(res, "frontend"),
  };
}

function logDir() {
  const dir = path.join(app.getPath("userData"), "logs");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function pipeToLog(child, name) {
  const out = fs.createWriteStream(path.join(logDir(), `${name}.log`), { flags: "a" });
  out.write(`\n--- ${name} started ${new Date().toISOString()} ---\n`);
  child.stdout?.pipe(out);
  child.stderr?.pipe(out);
}

// --- sidecar processes -----------------------------------------------------
function startBackend(backendExe) {
  if (!fs.existsSync(backendExe)) {
    throw new Error(
      `Backend not built.\n\nExpected: ${backendExe}\n\n` +
        "Freeze it first — see backend/BUILD.md:\n" +
        "  cd backend\n" +
        "  .venv\\Scripts\\pyinstaller.exe backend.spec --noconfirm"
    );
  }
  const child = spawn(backendExe, [], {
    env: {
      ...process.env,
      TLF_STUDIO_HOST: HOST,
      TLF_STUDIO_PORT: String(BACKEND_PORT),
    },
    windowsHide: true,
  });
  pipeToLog(child, "backend");
  child.on("exit", (code) => {
    if (!shuttingDown) console.error(`[backend] exited early with code ${code}`);
  });
  return child;
}

function startFrontend(frontendDir) {
  const serverJs = path.join(frontendDir, "server.js");
  if (!fs.existsSync(serverJs)) {
    throw new Error(
      `Frontend not built.\n\nExpected: ${serverJs}\n\n` +
        "Running the dev app (launch.bat) wipes this build. Rebuild it:\n" +
        "  cd frontend && npm run build\n" +
        "  cd ../desktop && npm run build:frontend\n\n" +
        "(`npm start` normally rebuilds it automatically.)"
    );
  }
  // Run the Next standalone server using Electron's bundled Node — no system
  // Node required on the target machine.
  const child = spawn(process.execPath, [serverJs], {
    cwd: frontendDir,
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: "1",
      NODE_ENV: "production",
      HOSTNAME: HOST,
      PORT: String(FRONTEND_PORT),
    },
    windowsHide: true,
  });
  pipeToLog(child, "frontend");
  child.on("exit", (code) => {
    if (!shuttingDown) console.error(`[frontend] exited early with code ${code}`);
  });
  return child;
}

// --- readiness polling -----------------------------------------------------
function ping(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode !== undefined && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForUrl(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await ping(url)) return true;
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

// --- window ----------------------------------------------------------------
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    show: true,
    backgroundColor: "#ffffff",
    title: "TLF Studio",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Open external links in the system browser, not inside the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http")) shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  return mainWindow;
}

function showStatus(message, isError) {
  if (!mainWindow) return;
  const file = path.join(__dirname, "loading.html");
  mainWindow.loadFile(file, { query: { msg: message, error: isError ? "1" : "" } });
}

// --- boot sequence ---------------------------------------------------------
async function boot() {
  createWindow();
  await startServices();
}

// Spawn the sidecars, wait for them, then load the app — or show a friendly
// error. Safe to call again (Retry): it cleans up any previous attempt first.
async function startServices() {
  showStatus("Starting TLF Studio…", false);

  for (const proc of [backendProc, frontendProc]) {
    try {
      if (proc && !proc.killed) proc.kill();
    } catch (_) {
      /* ignore */
    }
  }
  backendProc = null;
  frontendProc = null;
  shuttingDown = false;

  const conflict = await portConflict();
  if (conflict) {
    showStatus(conflict, true);
    return;
  }

  let paths;
  try {
    paths = resolvePaths();
    backendProc = startBackend(paths.backendExe);
    frontendProc = startFrontend(paths.frontendDir);
  } catch (err) {
    showStatus(String(err.message || err), true);
    return;
  }

  showStatus("Starting services…", false);
  const backendOk = await waitForUrl(`http://${HOST}:${BACKEND_PORT}/health`, STARTUP_TIMEOUT_MS);
  if (!backendOk) {
    showStatus("The data engine didn't start. Try again, or open the logs for details.", true);
    return;
  }

  const frontendOk = await waitForUrl(`http://${HOST}:${FRONTEND_PORT}/studies`, STARTUP_TIMEOUT_MS);
  if (!frontendOk) {
    showStatus("The interface didn't start. Try again, or open the logs for details.", true);
    return;
  }

  if (mainWindow) mainWindow.loadURL(`http://${HOST}:${FRONTEND_PORT}/studies`);
  checkForUpdates();
}

// --- auto-update -----------------------------------------------------------
// Checks GitHub Releases (configured under build.publish). Downloads any new
// version in the background and installs it on the next quit. Only runs in the
// packaged app — a dev checkout has no update feed.
let updaterWired = false;

function wireUpdater() {
  if (updaterWired) return;
  updaterWired = true;
  autoUpdater.autoDownload = true;
  autoUpdater.on("error", (err) => console.error("[updater]", err?.message || err));
  autoUpdater.on("update-available", (info) =>
    console.log(`[updater] update available: ${info?.version}`)
  );
  autoUpdater.on("update-downloaded", (info) =>
    console.log(`[updater] update ${info?.version} downloaded; will install on quit`)
  );
}

function checkForUpdates() {
  if (!app.isPackaged) return;
  wireUpdater();
  autoUpdater.checkForUpdatesAndNotify().catch((err) =>
    console.error("[updater] check failed:", err?.message || err)
  );
}

// Invoked by the in-app Settings "Check for updates" button (via IPC).
async function checkForUpdatesManual() {
  const current = app.getVersion();
  if (!app.isPackaged) {
    return { status: "dev", message: "Updates only apply to the installed app." };
  }
  wireUpdater();
  try {
    const result = await autoUpdater.checkForUpdates();
    const latest = result && result.updateInfo && result.updateInfo.version;
    if (latest && latest !== current) {
      return {
        status: "available",
        version: latest,
        message: `Update ${latest} found — downloading; it installs when you next quit.`,
      };
    }
    return { status: "current", message: `You're up to date (v${current}).` };
  } catch (err) {
    return { status: "error", message: `Couldn't check for updates: ${err?.message || err}` };
  }
}

// --- lifecycle -------------------------------------------------------------
function killSidecars() {
  shuttingDown = true;
  for (const proc of [backendProc, frontendProc]) {
    if (proc && !proc.killed) {
      try {
        if (process.platform === "win32") {
          // proc.kill() only signals the immediate child on Windows; the
          // frozen backend's own children (e.g. a hung WINWORD.EXE during a
          // PDF export) would survive and hold file locks. /T takes the tree.
          const { execSync } = require("child_process");
          execSync(`taskkill /PID ${proc.pid} /T /F`, { stdio: "ignore" });
        } else {
          proc.kill();
        }
      } catch (_) {
        /* ignore */
      }
    }
  }
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  // IPC for the preload bridge (renderer ↔ main).
  ipcMain.handle("app:getVersion", () => app.getVersion());
  ipcMain.handle("app:checkForUpdates", () => checkForUpdatesManual());
  ipcMain.handle("app:retry", () => startServices());
  ipcMain.handle("app:openLogs", () => shell.openPath(logDir()));

  app.whenReady().then(boot);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) boot();
  });

  app.on("window-all-closed", () => {
    killSidecars();
    if (process.platform !== "darwin") app.quit();
  });

  app.on("before-quit", killSidecars);
  process.on("exit", killSidecars);
}
