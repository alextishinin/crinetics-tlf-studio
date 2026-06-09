// Copy the Next build's static assets + public/ into the standalone output.
//
// `next build` (output: "standalone") emits .next/standalone/server.js with a
// minimal node_modules, but NOT the static chunks or public files — those must
// be copied in alongside it. Run this after every `next build`.

import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = join(here, "..", "..", "frontend");
const standalone = join(frontend, ".next", "standalone");

if (!existsSync(join(standalone, "server.js"))) {
  console.error("Standalone build not found. Run `npm run build` in frontend/ first.");
  process.exit(1);
}

// .next/static -> standalone/.next/static
const staticSrc = join(frontend, ".next", "static");
const staticDst = join(standalone, ".next", "static");
mkdirSync(dirname(staticDst), { recursive: true });
cpSync(staticSrc, staticDst, { recursive: true });
console.log("  copied .next/static");

// public -> standalone/public (optional)
const publicSrc = join(frontend, "public");
if (existsSync(publicSrc)) {
  cpSync(publicSrc, join(standalone, "public"), { recursive: true });
  console.log("  copied public/");
}

console.log("Frontend standalone assembled at", standalone);
