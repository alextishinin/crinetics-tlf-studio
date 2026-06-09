export {};

// Exposed by the Electron preload (desktop app only). In the web/dev app
// `window.tlfStudio` is undefined, so always guard with `?.`.
declare global {
  interface Window {
    tlfStudio?: {
      isDesktop?: boolean;
      getVersion?: () => Promise<string>;
      checkForUpdates?: () => Promise<{ status: string; version?: string; message?: string }>;
    };
  }
}
