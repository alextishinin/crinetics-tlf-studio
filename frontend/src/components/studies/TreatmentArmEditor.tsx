"use client";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TreatmentArm } from "@/types/study";

interface Props {
  arms: TreatmentArm[];
  onChange: (arms: TreatmentArm[]) => void;
}

export function TreatmentArmEditor({ arms, onChange }: Props) {
  const swap = (i: number, j: number) => {
    if (j < 0 || j >= arms.length) return;
    const next = [...arms];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  const remove = (i: number) => onChange(arms.filter((_, idx) => idx !== i));
  const patch = (i: number, p: Partial<TreatmentArm>) => {
    const next = [...arms];
    next[i] = { ...next[i], ...p };
    onChange(next);
  };
  return (
    <div className="space-y-3">
      {arms.map((arm, i) => (
        <div key={i} className="grid grid-cols-12 gap-2 items-end rounded-md border p-3">
          <div className="col-span-4">
            <Label className="text-xs">Label</Label>
            <Input value={arm.label} onChange={(e) => patch(i, { label: e.target.value })} />
          </div>
          <div className="col-span-2">
            <Label className="text-xs">TRTPN</Label>
            <Input type="number" value={arm.trtpn} onChange={(e) => patch(i, { trtpn: Number(e.target.value) })} />
          </div>
          <div className="col-span-3">
            <Label className="text-xs">Column header</Label>
            <Input value={arm.column_header} onChange={(e) => patch(i, { column_header: e.target.value })} />
          </div>
          <div className="col-span-2">
            <Label className="text-xs">Target dose (mg)</Label>
            <Input
              type="number"
              value={arm.target_daily_dose_mg ?? ""}
              onChange={(e) =>
                patch(i, {
                  target_daily_dose_mg: e.target.value === "" ? null : Number(e.target.value),
                })
              }
            />
          </div>
          <div className="col-span-1 flex justify-end gap-1">
            <Button type="button" size="icon" variant="ghost" onClick={() => swap(i, i - 1)}>
              <ArrowUp className="h-4 w-4" />
            </Button>
            <Button type="button" size="icon" variant="ghost" onClick={() => swap(i, i + 1)}>
              <ArrowDown className="h-4 w-4" />
            </Button>
            <Button type="button" size="icon" variant="ghost" onClick={() => remove(i)}>
              <Trash2 className="h-4 w-4 text-rose-600" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
