import "./globals.css";
import type { Metadata } from "next";

import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/Sidebar";

export const metadata: Metadata = {
  title: "TLF Studio — Crinetics Pharmaceuticals",
  description: "Configure, generate, preview, and manage clinical TLFs.",
  icons: {
    icon: "/crinetics-logo.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background antialiased">
        <Providers>
          <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
