/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produce a minimal self-contained server (.next/standalone/server.js) so
  // the desktop app can run the full Next app — including runtime-dynamic
  // routes like /studies/[studyId] — via Electron's bundled Node.
  output: "standalone",
};

export default nextConfig;
