/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produce a minimal self-contained server (.next/standalone/server.js) so
  // the desktop app can run the full Next app — including runtime-dynamic
  // routes like /studies/[studyId] — via Electron's bundled Node.
  output: "standalone",
  // Serve images as-is. Avoids the native `sharp` dependency in standalone
  // mode (we bundle local assets, so on-the-fly optimization isn't needed).
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
