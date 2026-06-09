"use client";

import { cn } from "@/lib/utils";

export function Header({
  title,
  action,
  sticky,
}: {
  title: string;
  action?: React.ReactNode;
  // When true, the header pins to the top of the scrolling area so its
  // action button (e.g. Save / Generate) stays visible while scrolling.
  // Requires the page wrapper to use `min-h-full` (not `h-full`) so the
  // sticky range spans the full content, not just one viewport.
  sticky?: boolean;
}) {
  return (
    <header
      className={cn(
        "flex items-center justify-between border-b bg-white px-6 py-4",
        sticky && "sticky top-0 z-20",
      )}
    >
      <h1 className="text-xl font-semibold">{title}</h1>
      <div>{action}</div>
    </header>
  );
}
