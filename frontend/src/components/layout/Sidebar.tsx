"use client";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { History, LayoutGrid, Settings } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV = [
  { href: "/studies", label: "Studies", icon: LayoutGrid },
  { href: "/updates", label: "Updates", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden w-56 shrink-0 border-r bg-white md:flex md:flex-col">
      <div className="flex flex-col items-start gap-2 px-4 py-4 border-b">
        <Image
          src="/crinetics-logo.png"
          alt="Crinetics Pharmaceuticals"
          width={140}
          height={40}
          priority
        />
        <span className="text-sm font-medium text-crinetics-slate">
          TLF Studio
        </span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-crinetics-tealLight text-primary font-medium"
                  : "text-crinetics-slate hover:bg-slate-50",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-3 py-3 text-xs text-slate-400 border-t">
        Internal &middot; Crinetics
      </div>
    </aside>
  );
}
