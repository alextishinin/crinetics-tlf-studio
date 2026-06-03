"use client";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Sparkles, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Header } from "@/components/layout/Header";
import { ShellCard } from "@/components/shells/ShellCard";
import { useShells, useSaveShellSelection } from "@/hooks/useShells";
import { useNlShells } from "@/hooks/useAi";
import { useShellStore } from "@/store/shellStore";

const SUGGESTIONS = [
  "All standard safety tables",
  "Add DILI plot",
  "Remove all optional tables",
  "Select everything needed for an NDA submission",
];

export default function ShellsPage() {
  const params = useParams<{ studyId: string }>();
  const { data, error, isError, isLoading, refetch } = useShells(params.studyId);
  const save = useSaveShellSelection(params.studyId);
  const nlMutation = useNlShells(params.studyId);

  const { selections, setSelections, toggle, pendingChanges, setPendingChanges, applyPending, clearPending } =
    useShellStore();

  const [showBanner, setShowBanner] = useState(false);
  const [instruction, setInstruction] = useState("");

  // Seed Zustand from API.
  useEffect(() => {
    if (!data) return;
    const initial: Record<string, boolean> = {};
    for (const group of data.groups) {
      for (const s of group.shells) {
        initial[s.id] = s.selected;
      }
    }
    setSelections(initial);
    setShowBanner(data.auto_selected.length + data.auto_deselected.length > 0);
  }, [data, setSelections]);

  const summary = useMemo(() => {
    if (!data) return { selected: 0, byGroup: {} as Record<string, number> };
    const byGroup: Record<string, number> = {};
    let total = 0;
    for (const g of data.groups) {
      let n = 0;
      for (const s of g.shells) if (selections[s.id]) n++;
      byGroup[g.name] = n;
      total += n;
    }
    return { selected: total, byGroup };
  }, [data, selections]);

  const handleSave = () => {
    // Only optional shells are persisted via optional_outputs.
    const optionalFlags: Record<string, boolean> = {};
    for (const g of data?.groups ?? []) {
      for (const s of g.shells) {
        if (s.optional_flag) optionalFlags[s.optional_flag] = !!selections[s.id];
      }
    }
    save.mutate(optionalFlags);
  };

  const handleNl = async () => {
    if (!instruction.trim()) return;
    const result = await nlMutation.mutateAsync({ instruction, current: selections });
    setPendingChanges(result.changes);
  };

  if (isLoading) return <div className="p-6 text-sm">Loading shells...</div>;

  if (isError || !data) {
    return (
      <div className="p-6">
        <Card className="border-rose-200 bg-rose-50">
          <CardContent className="flex items-start gap-3 pt-4 text-sm text-rose-900">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="space-y-3">
              <div>
                <div className="font-medium">Could not load shells</div>
                <div className="text-rose-800">
                  {error instanceof Error ? error.message : "The shells API did not return data."}
                </div>
              </div>
              <Button size="sm" variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Select TFLs"
        action={
          <Button onClick={handleSave} disabled={save.isPending}>
            <Save className="h-4 w-4" /> Save selection
          </Button>
        }
      />
      <div className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          {showBanner && (
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="pt-4 text-sm">
                We auto-selected {data.auto_selected.length} table(s) and auto-deselected{" "}
                {data.auto_deselected.length} based on your data. Review and adjust below.
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" /> Describe what you need…
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder="e.g. Add the DILI scatter and remove ECG tables"
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleNl()}
                />
                <Button onClick={handleNl} disabled={nlMutation.isPending}>Apply</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="rounded-full border bg-white px-3 py-1 text-xs hover:bg-slate-50"
                    onClick={() => setInstruction(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
              {pendingChanges.length > 0 && (
                <div className="rounded-md border bg-slate-50 p-3 text-sm">
                  <div className="font-medium mb-2">Proposed changes</div>
                  <ul className="space-y-1 text-xs">
                    {pendingChanges.map((c) => (
                      <li key={c.shell_id}>
                        <span className={c.action === "add" ? "text-emerald-700" : "text-rose-700"}>
                          {c.action === "add" ? "+" : "−"}
                        </span>{" "}
                        <span className="font-mono">{c.shell_id}</span> — {c.reason}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" onClick={applyPending}>Apply</Button>
                    <Button size="sm" variant="outline" onClick={clearPending}>Discard</Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {data.groups.map((g) => (
            <Card key={g.name}>
              <CardHeader><CardTitle className="text-base">{g.name}</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {g.shells.map((s) => (
                  <ShellCard
                    key={s.id}
                    shell={s}
                    studyId={params.studyId}
                    checked={!!selections[s.id]}
                    onToggle={() => toggle(s.id)}
                  />
                ))}
              </CardContent>
            </Card>
          ))}
        </div>

        <div>
          <Card className="sticky top-4">
            <CardHeader><CardTitle className="text-base">Selection summary</CardTitle></CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex justify-between border-b pb-1 font-medium">
                <span>Total selected</span>
                <span>{summary.selected}</span>
              </div>
              {Object.entries(summary.byGroup).map(([name, n]) => (
                <div key={name} className="flex justify-between text-slate-600">
                  <span>{name}</span>
                  <span>{n}</span>
                </div>
              ))}
              <div className="mt-3 text-xs text-slate-500">
                Estimated generation time: ~{Math.max(5, summary.selected * 5)} seconds
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
