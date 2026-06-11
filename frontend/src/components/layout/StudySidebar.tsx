"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeft,
  ClipboardList,
  Download,
  FlaskConical,
  PlayCircle,
  ScrollText,
  Settings,
} from "lucide-react";

import { useStudy } from "@/hooks/useStudy";
import { cn } from "@/lib/utils";

const ITEMS = (sid: string) => [
  { href: `/studies/${sid}`, label: "Overview", icon: FlaskConical },
  { href: `/studies/${sid}/config`, label: "Config", icon: Settings },
  { href: `/studies/${sid}/shells`, label: "Select TFLs", icon: ClipboardList },
  { href: `/studies/${sid}/generate`, label: "Generate", icon: PlayCircle },
  { href: `/studies/${sid}/outputs`, label: "Outputs", icon: Download },
  { href: `/studies/${sid}/audit`, label: "Audit Trail", icon: ScrollText },
];

export function StudySidebar({ studyId }: { studyId: string }) {
  const pathname = usePathname();
  const { data } = useStudy(studyId);
  const protocol = data?.config?.protocol_number || "";
  const title = data?.config?.protocol_title || data?.meta?.title || "";

  return (
    <nav className="flex w-48 shrink-0 flex-col border-r bg-white">
      {/* Which study am I in? — protocol + title pinned at the top, with a
          way back to the studies list. */}
      <div className="border-b px-3 py-3">
        <Link
          href="/studies"
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-primary"
        >
          <ArrowLeft className="h-3 w-3" /> All studies
        </Link>
        <p className="mt-2 truncate text-sm font-semibold" title={title}>
          {protocol || "—"}
        </p>
        {title && (
          <p className="mt-0.5 line-clamp-2 text-xs text-slate-500" title={title}>
            {title}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-1 px-2 py-3">
        {ITEMS(studyId).map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname.startsWith(item.href) &&
            (item.href === `/studies/${studyId}` ? pathname === item.href : true);
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
      </div>
    </nav>
  );
}
