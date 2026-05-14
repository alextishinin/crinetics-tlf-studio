"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ClipboardList,
  Download,
  FlaskConical,
  PlayCircle,
  Settings,
} from "lucide-react";

import { cn } from "@/lib/utils";

const ITEMS = (sid: string) => [
  { href: `/studies/${sid}`, label: "Overview", icon: FlaskConical },
  { href: `/studies/${sid}/config`, label: "Config", icon: Settings },
  { href: `/studies/${sid}/shells`, label: "Select TFLs", icon: ClipboardList },
  { href: `/studies/${sid}/generate`, label: "Generate", icon: PlayCircle },
  { href: `/studies/${sid}/outputs`, label: "Outputs", icon: Download },
];

export function StudySidebar({ studyId }: { studyId: string }) {
  const pathname = usePathname();
  return (
    <nav className="flex w-48 shrink-0 flex-col gap-1 border-r bg-white px-2 py-4">
      {ITEMS(studyId).map((item) => {
        const Icon = item.icon;
        const isActive = pathname.startsWith(item.href) && (item.href === `/studies/${studyId}` ? pathname === item.href : true);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
              isActive
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
  );
}
