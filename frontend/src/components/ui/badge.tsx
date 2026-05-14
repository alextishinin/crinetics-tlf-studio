import { cn } from "@/lib/utils";
import { STATUS_COLORS, STATUS_LABELS } from "@/lib/constants";

export function Badge({ className, children, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge className={cn("border-transparent", STATUS_COLORS[status] ?? "bg-slate-200 text-slate-700")}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}
