"use strict";

// Minimal preload. contextIsolation is on and nodeIntegration is off, so the
// renderer (the Next app + the loading/error screen) runs as an ordinary web
// page with no Node access — it gets only this small, explicit bridge.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tlfStudio", {
  isDesktop: true,
  // Settings page
  getVersion: () => ipcRenderer.invoke("app:getVersion"),
  checkForUpdates: () => ipcRenderer.invoke("app:checkForUpdates"),
  // Error screen
  retry: () => ipcRenderer.invoke("app:retry"),
  openLogs: () => ipcRenderer.invoke("app:openLogs"),
});
