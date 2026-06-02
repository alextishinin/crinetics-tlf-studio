"use client";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import type { AnalysisSet } from "@/types/study";

interface Props {
  sets: Record<string, AnalysisSet>;
  onChange: (sets: Record<string, AnalysisSet>) => void;
}

export function AnalysisSetEditor({ sets, onChange }: Props) {
  const patch = (name: string, set: AnalysisSet) =>
    onChange({ ...sets, [name]: set });
  return (
    <div className="space-y-3">
      {Object.entries(sets).map(([name, set]) => (
        <div key={name} className="rounded-md border p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{name} — {set.label}</span>
            <span className="text-xs text-slate-500">
              Flag: {set.flag_var ?? "(none)"} = {set.flag_val ?? "—"}
            </span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {Object.entries(set.n).map(([trtpn, n]) => (
              <div key={trtpn}>
                <Label className="text-xs">Arm {trtpn}</Label>
                <Input
                  type="number"
                  value={n ?? ""}
                  onChange={(e) =>
                    patch(name, {
                      ...set,
                      n: { ...set.n, [trtpn]: e.target.value === "" ? null : Number(e.target.value) },
                    })
                  }
                />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
