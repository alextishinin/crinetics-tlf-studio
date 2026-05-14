"use client";
import { AlertTriangle, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Anomaly } from "@/types/ai";

interface Props {
  anomaly: Anomaly;
  onDismiss?: () => void;
}

export function AnomalyBadge({ anomaly, onDismiss }: Props) {
  const Icon = anomaly.severity === "warning" ? AlertTriangle : Info;
  return (
    <div
      className={cn(
        "rounded-md border p-3 text-sm",
        anomaly.severity === "warning"
          ? "border-amber-200 bg-amber-50"
          : "border-blue-200 bg-blue-50",
      )}
    >
      <div className="flex items-start gap-2">
        <Icon
          className={cn(
            "h-4 w-4 mt-0.5 shrink-0",
            anomaly.severity === "warning" ? "text-amber-700" : "text-blue-700",
          )}
        />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <Badge className={anomaly.source === "ai" ? "bg-violet-100 text-violet-700" : "bg-slate-200 text-slate-600"}>
              {anomaly.source}
            </Badge>
            <span className="font-medium">{anomaly.description}</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {anomaly.location} · {anomaly.rule}
          </div>
        </div>
        {onDismiss && (
          <button className="text-xs text-slate-500 hover:text-slate-700" onClick={onDismiss}>
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}
