export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  ready: "Ready",
  generating: "Generating",
  complete: "Complete",
  queued: "Queued",
  running: "Running",
  failed: "Failed",
  cancelled: "Cancelled",
  approved: "Approved",
  pending: "Pending Review",
};

export const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-200 text-slate-700",
  ready: "bg-blue-100 text-blue-700",
  generating: "bg-amber-100 text-amber-700",
  complete: "bg-emerald-100 text-emerald-700",
  queued: "bg-slate-200 text-slate-700",
  running: "bg-amber-100 text-amber-700",
  failed: "bg-rose-100 text-rose-700",
  cancelled: "bg-slate-200 text-slate-500",
  approved: "bg-emerald-100 text-emerald-700",
  pending: "bg-slate-200 text-slate-700",
};
