"use strict";

// electron-builder strips `node_modules` out of directories copied via
// `extraResources`, which leaves the bundled Next standalone server unable to
// `require('next')` ("interface did not start"). Copy it back in here, after
// the app is packed but before the target (NSIS) wraps it.

const fs = require("fs");
const path = require("path");

exports.default = async function afterPack(context) {
  const src = path.join(
    __dirname,
    "..",
    "frontend",
    ".next",
    "standalone",
    "node_modules"
  );
  const dst = path.join(
    context.appOutDir,
    "resources",
    "frontend",
    "node_modules"
  );

  if (!fs.existsSync(src)) {
    throw new Error(
      `Frontend standalone node_modules not found:\n${src}\n` +
        "Build the frontend first: cd frontend && npm run build"
    );
  }

  fs.cpSync(src, dst, { recursive: true });
  console.log(`  • afterPack: bundled frontend node_modules -> ${dst}`);
};
