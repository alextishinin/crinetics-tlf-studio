"use client";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ClipboardList, Download, PlayCircle, Settings, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { Header } from "@/components/layout/Header";
import { useDeleteStudy, useStudy } from "@/hooks/useStudy";
import { useJobs } from "@/hooks/useJobs";
import { useOutputs } from "@/hooks/usePreview";
import { formatTimestamp } from "@/lib/utils";

export default function StudyOverviewPage() {
  const params = useParams<{ studyId: string }>();
  const router = useRouter();
  const { data, isLoading } = useStudy(params.studyId);
  const { data: jobs } = useJobs(params.studyId);
  const { data: outputs } = useOutputs(params.studyId);
  const deleteStudy = useDeleteStudy();

  const handleDelete = async () => {
    if (!data) return;
    const ok = window.confirm(
      `Delete "${data.meta.title}"?\n\nThis removes all uploaded ADaM data, generated outputs, and audit records from disk. This cannot be undone.`,
    );
    if (!ok) return;
    await deleteStudy.mutateAsync(params.studyId);
    router.push("/studies");
  };

  if (isLoading || !data) return <div className="p-6 text-sm text-slate-500">Loading…</div>;

  const cfg = data.config;
  const totalN = Object.values(cfg.analysis_sets?.SAF?.n ?? {}).reduce<number>(
    (a, b) => a + (Number(b) || 0),
    0,
  );
  const optional = cfg.optional_outputs ?? {};
  const selected = Object.values(optional).filter(Boolean).length;
  const total = Object.keys(optional).length;
  const generated = (outputs ?? []).length;
  const failed = (jobs ?? []).filter((j) => j.status === "failed").length;

  return (
    <div className="flex h-full flex-col">
      <Header
        title={cfg.protocol_title || data.meta.title}
        action={<StatusBadge status={data.meta.status} />}
      />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <SummaryCard title="Protocol" lines={[cfg.protocol_number || "—", cfg.indication || ""]} />
          <SummaryCard
            title="Population"
            lines={[`${cfg.treatment_arms?.length ?? 0} arms`, `N = ${totalN}`]}
          />
          <SummaryCard
            title="TFL Selection"
            lines={[`${selected} of ${total} selected`, `${generated} generated · ${failed} failed`]}
          />
        </div>

        <div className="flex gap-2 flex-wrap">
          <Button asChild variant="outline">
            <Link href={`/studies/${params.studyId}/config`}><Settings className="h-4 w-4" /> Edit Config</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/studies/${params.studyId}/shells`}><ClipboardList className="h-4 w-4" /> Select TFLs</Link>
          </Button>
          <Button asChild>
            <Link href={`/studies/${params.studyId}/generate`}><PlayCircle className="h-4 w-4" /> Generate</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/studies/${params.studyId}/outputs`}><Download className="h-4 w-4" /> Outputs</Link>
          </Button>
          <div className="grow" />
          <Button
            variant="outline"
            className="text-rose-700 hover:bg-rose-50 border-rose-200"
            onClick={handleDelete}
            disabled={deleteStudy.isPending}
          >
            <Trash2 className="h-4 w-4" /> {deleteStudy.isPending ? "Deleting…" : "Delete Study"}
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Last Activity</CardTitle>
            <CardDescription>{formatTimestamp(data.meta.updated_at)}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}

function SummaryCard({ title, lines }: { title: string; lines: string[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm text-slate-600">
        {lines.map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </CardContent>
    </Card>
  );
}
