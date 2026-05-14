"use client";
import Link from "next/link";
import { Eye, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ConditionBadge } from "./ConditionBadge";
import { cn } from "@/lib/utils";
import type { ShellEntry } from "@/types/shell";

interface Props {
  shell: ShellEntry;
  studyId: string;
  checked: boolean;
  onToggle: () => void;
}

export function ShellCard({ shell, studyId, checked, onToggle }: Props) {
  const disabled = !shell.available || shell.conditionality === "required";
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-md border p-3",
        !shell.available && "opacity-50",
      )}
    >
      <Checkbox checked={checked} onCheckedChange={onToggle} disabled={disabled} />
      <div className="flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-mono text-slate-500">{shell.table_number}</span>
          <span className="text-sm font-medium">{shell.title_line2}</span>
          <ConditionBadge value={shell.conditionality} />
          {!shell.available && (
            <span className="text-xs text-rose-700">data missing</span>
          )}
        </div>
        <div className="text-xs text-slate-500 mt-0.5">{shell.population}</div>
        {shell.condition_reason && (
          <div className="text-xs text-slate-500 mt-1 flex items-start gap-1">
            <Info className="h-3 w-3 mt-0.5 shrink-0" />
            {shell.condition_reason}
          </div>
        )}
      </div>
      <Button asChild size="sm" variant="ghost">
        <Link href={`/studies/${studyId}/preview/${shell.id}`}>
          <Eye className="h-3.5 w-3.5" /> Preview
        </Link>
      </Button>
    </div>
  );
}
