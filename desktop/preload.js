"use strict";

// Minimal preload. contextIsolation is on and nodeIntegration is off, so the
// renderer (the Next app) runs as an ordinary web page with no Node access.
// Exposes only a tiny, read-only surface for app metadata.

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("tlfStudio", {
  isDesktop: true,
});
