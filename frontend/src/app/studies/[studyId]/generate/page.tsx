"use client";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ChevronDown, ChevronRight, PlayCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Header } from "@/components/layout/Header";
import { JobStatusBadge } from "@/components/generation/JobStatusBadge";
import { useShells } from "@/hooks/useShells";
import { useCancelJob, useJobs, useSubmitJobs } from "@/hooks/useJobs";
import { formatTimestamp } from "@/lib/utils";
import type { JobRecord } from "@/types/job";

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

  // Progress is scoped to the most recent batch — measuring across the whole
  // job history made the bar meaningless after a couple of runs.
  const latestBatch = useMemo(() => {
    if (recentJobs.length === 0) return [] as JobRecord[];
    const newest = recentJobs[0];
    if (newest.batch_id) return recentJobs.filter((j) => j.batch_id === newest.batch_id);
    return [newest];
  }, [recentJobs]);
  const batchDone = latestBatch.filter(
    (j) => j.status === "complete" || j.status === "failed" || j.status === "cancelled",
  ).length;
  const batchFailed = latestBatch.filter((j) => j.status === "failed").length;
  const batchActive = latestBatch.some((j) => j.status === "queued" || j.status === "running");
  const progress = latestBatch.length === 0 ? 0 : Math.round((batchDone / latestBatch.length) * 100);

  return (
    <div className="flex min-h-full flex-col">
      <Header
        title="Generate"
        sticky
        action={
          <Button onClick={handleGenerate} disabled={submit.isPending}>
            <PlayCircle className="h-4 w-4" />
            {submit.isPending ? "Submitting…" : "Generate Selected"}
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
              <label key={s.id} className="flex cursor-pointer items-center gap-3 rounded-md border p-2">
                <Checkbox
                  checked={!!batchSel[s.id]}
                  onCheckedChange={(c) => setBatchSel((x) => ({ ...x, [s.id]: !!c }))}
                  aria-label={`Include ${s.number} in the batch`}
                />
                <div className="flex-1 text-sm">
                  <span className="font-mono text-slate-500 mr-2">{s.number}</span>
                  {s.title}
                </div>
              </label>
            ))}
          </CardContent>
        </Card>

        {latestBatch.length > 0 && (batchActive || batchDone > 0) && (
          <Card>
            <CardHeader><CardTitle className="text-base">Latest Batch</CardTitle></CardHeader>
            <CardContent>
              <Progress value={progress} />
              <div className="mt-2 text-xs text-slate-500">
                {batchDone} of {latestBatch.length} finished
                {batchFailed > 0 && <span className="text-rose-600"> · {batchFailed} failed</span>}
                {batchActive && <span> · {running.length} in progress</span>}
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
                  <JobRow
                    key={j.job_id}
                    job={j}
                    onDismiss={() => cancel.mutate(j.job_id)}
                    onRetry={() => submit.mutate([j.table_id])}
                  />
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function JobRow({
  job,
  onDismiss,
  onRetry,
}: {
  job: JobRecord;
  onDismiss: () => void;
  onRetry: () => void;
}) {
  const [showError, setShowError] = useState(false);
  const duration =
    job.started_at && job.completed_at
      ? `${Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)}s`
      : "—";
  // First line of the captured error, without the traceback noise.
  const errorSummary = job.error ? job.error.split("\n")[0] : null;

  return (
    <>
      <tr className="border-b">
        <td className="p-2 text-xs text-slate-500">{formatTimestamp(job.submitted_at)}</td>
        <td className="p-2">
          <span className="font-mono text-xs text-slate-500 mr-2">{job.table_number}</span>
          <span className="font-mono text-xs">{job.table_id}</span>
        </td>
        <td className="p-2"><JobStatusBadge status={job.status} /></td>
        <td className="p-2 text-xs text-slate-500">{duration}</td>
        <td className="p-2 text-right">
          {(job.status === "queued" || job.status === "running") && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onDismiss}
              aria-label="Dismiss job"
              title="Dismiss — a job already running is not interrupted"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
          {job.status === "failed" && (
            <Button size="sm" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          )}
        </td>
      </tr>
      {job.status === "failed" && errorSummary && (
        <tr className="border-b bg-rose-50/60">
          <td colSpan={5} className="px-2 pb-2 pt-1">
            <button
              className="flex w-full items-start gap-2 text-left text-xs text-rose-700"
              onClick={() => setShowError((s) => !s)}
              aria-expanded={showError}
            >
              {showError ? (
                <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              ) : (
                <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              )}
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span className="min-w-0 break-words">{errorSummary}</span>
            </button>
            {showError && (
              <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-white p-3 text-[11px] leading-snug text-slate-700 border">
                {job.error}
              </pre>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
