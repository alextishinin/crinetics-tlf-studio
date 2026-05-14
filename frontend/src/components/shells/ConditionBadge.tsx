"use client";
import { Badge } from "@/components/ui/badge";
import type { Conditionality } from "@/types/shell";

const COLORS: Record<Conditionality, string> = {
  required: "bg-blue-100 text-blue-700",
  optional: "bg-slate-200 text-slate-700",
  conditional: "bg-amber-100 text-amber-700",
};

export function ConditionBadge({ value }: { value: Conditionality }) {
  return <Badge className={COLORS[value]}>{value}</Badge>;
}
