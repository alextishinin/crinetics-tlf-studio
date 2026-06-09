// Ensure the Next standalone build exists before the desktop app starts.
//
// The dev app (launch.bat -> `next dev`) and the desktop app share
// frontend/.next/. Running the dev app wipes the standalone build, so this
// guard rebuilds + assembles it automatically when missing. It's a no-op when
// the build is already present, so `npm start` stays fast on the common path.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const desktop = join(here, "..");
const frontend = join(desktop, "..", "frontend");
const serverJs = join(frontend, ".next", "standalone", "server.js");
const staticDir = join(frontend, ".next", "standalone", ".next", "static");

if (existsSync(serverJs) && existsSync(staticDir)) {
  console.log("Frontend standalone build present.");
  process.exit(0);
}

console.log("Frontend standalone build missing — building it now (~30s)…");

const build = spawnSync("npm", ["run", "build"], {
  cwd: frontend,
  stdio: "inherit",
  shell: true,
});
if (build.status !== 0) {
  console.error("\nFrontend build failed. Run `npm install` in frontend/ if you haven't.");
  process.exit(build.status || 1);
}

const assemble = spawnSync("node", [join(here, "assemble-frontend.mjs")], {
  stdio: "inherit",
  shell: true,
});
process.exit(assemble.status || 0);
