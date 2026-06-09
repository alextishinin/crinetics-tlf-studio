// One-command desktop build: turns the current source (tlf library + backend +
// frontend + Electron shell) into a fresh installer.
//
//   npm run build:app                 # build installer locally (no publish)
//   npm run release:app               # build + publish to GitHub Releases
//
// The app version is the version of the newest entry in
// frontend/src/data/changelog.json — the single source of truth. This script
// syncs it into desktop/package.json and backend APP_VERSION before building,
// so the installer filename and the in-app Settings/Updates version all match.
// To ship a new version: add a changelog entry with a higher version, then run.
//
// Flags (after `--`):
//   --release        publish the build to GitHub Releases (needs GH_TOKEN)
//   --skip-vendor    don't re-copy the tlf library (use the committed backend/vendor)
//
// Steps: sync version -> vendor tlf -> freeze backend.exe -> build frontend ->
//        assemble standalone -> package installer (electron-builder).

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const desktop = join(here, "..");
const studioRoot = join(desktop, "..");
const backend = join(studioRoot, "backend");
const frontend = join(studioRoot, "frontend");

const args = new Set(process.argv.slice(2));
const release = args.has("--release");
const skipVendor = args.has("--skip-vendor");

const pyExe = join(backend, ".venv", "Scripts", "python.exe");
const pyInstaller = join(backend, ".venv", "Scripts", "pyinstaller.exe");
const vendorDir = join(backend, "vendor");
const automationSrc =
  process.env.TLF_AUTOMATION_PATH || join(studioRoot, "..", "crinetics-tlf-automation");

function run(label, cmd, cmdArgs, { cwd, shell = false } = {}) {
  console.log(`\n=== ${label} ===`);
  const r = spawnSync(cmd, cmdArgs, { cwd, stdio: "inherit", shell });
  if (r.status !== 0) {
    console.error(`\n✗ Step failed: ${label} (exit ${r.status ?? "signal"})`);
    process.exit(r.status || 1);
  }
}

function fail(msg) {
  console.error(`\n✗ ${msg}`);
  process.exit(1);
}

// Version = newest changelog entry. Sync it into package.json + APP_VERSION.
function syncVersionFromChangelog() {
  console.log("\n=== Sync version from changelog ===");
  const clPath = join(frontend, "src", "data", "changelog.json");
  if (!existsSync(clPath)) {
    console.warn(`  (no changelog at ${clPath} — keeping existing version)`);
    return;
  }
  const releases = JSON.parse(readFileSync(clPath, "utf8"));
  const version = releases?.[0]?.version;
  if (!version) {
    console.warn("  (changelog has no top version — keeping existing version)");
    return;
  }
  const pkgPath = join(desktop, "package.json");
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
  if (pkg.version !== version) {
    pkg.version = version;
    writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
  }
  const cfgPath = join(backend, "config.py");
  const cfg = readFileSync(cfgPath, "utf8").replace(
    /APP_VERSION\s*=\s*"[^"]*"/,
    `APP_VERSION = "${version}"`
  );
  writeFileSync(cfgPath, cfg);
  console.log(`  version -> ${version}`);
}

// --- 0. sync version --------------------------------------------------------
syncVersionFromChangelog();

// --- 1. vendor the tlf library ---------------------------------------------
if (skipVendor) {
  console.log("\n=== Vendor tlf library (skipped: --skip-vendor) ===");
} else if (existsSync(automationSrc)) {
  if (!existsSync(pyExe)) fail(`Python venv not found: ${pyExe}\n  Run: cd backend && uv sync`);
  run("Vendor tlf library", pyExe, [join(studioRoot, "scripts", "vendor_tlf.py")], {
    cwd: studioRoot,
  });
} else if (existsSync(vendorDir)) {
  console.log(
    `\n=== Vendor tlf library (skipped: ${automationSrc} not found; using committed backend/vendor) ===`
  );
} else {
  fail(`tlf-automation not found at ${automationSrc} and no backend/vendor present.`);
}

// --- 2. freeze the backend --------------------------------------------------
if (!existsSync(pyInstaller)) {
  fail(`pyinstaller not found: ${pyInstaller}\n  Run: cd backend && uv sync`);
}
run("Freeze backend (PyInstaller)", pyInstaller, ["backend.spec", "--noconfirm"], {
  cwd: backend,
});

// --- 3. build + assemble the frontend --------------------------------------
run("Build frontend (Next standalone)", "npm", ["run", "build"], { cwd: frontend, shell: true });
run("Assemble frontend standalone", "node", [join(desktop, "scripts", "assemble-frontend.mjs")], {
  cwd: desktop,
});

// --- 4. package the installer ----------------------------------------------
const publish = release ? "always" : "never";
run(`Package installer (publish=${publish})`, "npx", ["electron-builder", "--publish", publish], {
  cwd: desktop,
  shell: true,
});

console.log(`\n✓ Done. Installer in ${join(desktop, "dist-installer")}`);
if (release) console.log("  Published to GitHub Releases (requires GH_TOKEN).");
