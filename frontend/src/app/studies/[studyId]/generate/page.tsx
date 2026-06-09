"use client";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PlayCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Header } from "@/components/layout/Header";
import { JobStatusBadge } from "@/components/generation/JobStatusBadge";
import { useShells } from "@/hooks/useShells";
import { useCancelJob, useJobs, useSubmitJobs } from "@/hooks/useJobs";
import { formatTimestamp } from "@/lib/utils";

export default function GeneratePage() {
  const params = useParams<{ studyId: string }>();
  const { data: shellList } = useShells(params.studyId);
  const { data: jobs } = useJobs(params.studyId, 2000);
  const submit = useSubmitJobs(params.studyId);
  const cancel = useCancelJob(params.studyId);

  const selectableShells = useMemo(() => {
    const out: { id: string; number: string; title: string }[] = [];
    for (const g of shellList?.groups ?? []) {
      for (const s of g.shells) {
        if (s.selected && s.available && s.type !== "generic_layout") {
          out.push({ id: s.id, number: s.table_number, title: s.title_line2 });
        }
      }
    }
    return out;
  }, [shellList]);

  const [batchSel, setBatchSel] = useState<Record<string, boolean>>({});
  useEffect(() => {
    // Default: check everything selected
    const init: Record<string, boolean> = {};
    for (const s of selectableShells) init[s.id] = true;
    setBatchSel(init);
  }, [selectableShells]);

  const handleGenerate = () => {
    const ids = Object.entries(batchSel).filter(([_, v]) => v).map(([k]) => k);
    if (ids.length === 0) return;
    submit.mutate(ids);
  };

  const recentJobs = (jobs ?? []).slice().sort((a, b) => (a.submitted_at < b.submitted_at ? 1 : -1));
  const running = recentJobs.filter((j) => j.status === "queued" || j.status === "running");
  const complete = recentJobs.filter((j) => j.status === "complete").length;
  const total = recentJobs.length;
  const progress = total === 0 ? 0 : Math.round((complete / total) * 100);

  return (
    <div className="flex min-h-full flex-col">
      <Header
        title="Generate"
        sticky
        action={
          <Button onClick={handleGenerate} disabled={submit.isPending}>
            <PlayCircle className="h-4 w-4" /> Generate Selected
          </Button>
        }
      />
      <div className="p-6 space-y-6">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Batch Generation</CardTitle>
              {selectableShells.length > 0 && (() => {
                const checkedCount = selectableShells.filter((s) => batchSel[s.id]).length;
                const allChecked = checkedCount === selectableShells.length;
                return (
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">
                      {checkedCount} of {selectableShells.length} selected
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        setBatchSel(
                          Object.fromEntries(
                            selectableShells.map((s) => [s.id, !allChecked]),
                          ),
                        )
                      }
                    >
                      {allChecked ? "Deselect all" : "Select all"}
                    </Button>
                  </div>
                );
              })()}
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {selectableShells.length === 0 && (
              <p className="text-sm text-slate-500">
                No selectable shells. Go to <a className="underline" href={`/studies/${params.studyId}/shells`}>Select TFLs</a> first.
              </p>
            )}
            {selectableShells.map((s) => (
              <div key={s.id} className="flex items-center gap-3 rounded-md border p-2">
                <Checkbox
                  checked={!!batchSel[s.id]}
                  onCheckedChange={(c) => setBatchSel((x) => ({ ...x, [s.id]: !!c }))}
                />
                <div className="flex-1 text-sm">
                  <span className="font-mono text-slate-500 mr-2">{s.number}</span>
                  {s.title}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {total > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-base">Progress</CardTitle></CardHeader>
            <CardContent>
              <Progress value={progress} />
              <div className="mt-2 text-xs text-slate-500">
                {complete} of {total} complete · {running.length} running
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader><CardTitle className="text-base">Job History</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500 border-b">
                <tr>
                  <th className="p-2">Submitted</th>
                  <th className="p-2">Table</th>
                  <th className="p-2">Status</th>
                  <th className="p-2">Duration</th>
                  <th className="p-2"></th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.length === 0 && (
                  <tr><td colSpan={5} className="p-3 text-center text-slate-500">No jobs yet.</td></tr>
                )}
                {recentJobs.map((j) => (
                  <tr key={j.job_id} className="border-b">
                    <td className="p-2 text-xs text-slate-500">{formatTimestamp(j.submitted_at)}</td>
                    <td className="p-2 font-mono">{j.table_id}</td>
                    <td className="p-2"><JobStatusBadge status={j.status} /></td>
                    <td className="p-2 text-xs text-slate-500">
                      {j.started_at && j.completed_at
                        ? `${Math.round((new Date(j.completed_at).getTime() - new Date(j.started_at).getTime()) / 1000)}s`
                        : "—"}
                    </td>
                    <td className="p-2 text-right">
                      {(j.status === "queued" || j.status === "running") && (
                        <Button size="sm" variant="ghost" onClick={() => cancel.mutate(j.job_id)}>
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {j.status === "failed" && (
                        <Button size="sm" variant="outline" onClick={() => submit.mutate([j.table_id])}>
                          Retry
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
