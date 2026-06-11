"use client";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import {
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Download,
  FileText,
  FlaskConical,
  PlayCircle,
  Settings,
  Trash2,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Header } from "@/components/layout/Header";
import { useDeleteStudy, useStudy } from "@/hooks/useStudy";
import { useJobs } from "@/hooks/useJobs";
import { useOutputs } from "@/hooks/usePreview";
import { cn, formatTimestamp } from "@/lib/utils";

export default function StudyOverviewPage() {
  const params = useParams<{ studyId: string }>();
  const router = useRouter();
  const { data, isLoading } = useStudy(params.studyId);
  const { data: jobs } = useJobs(params.studyId);
  const { data: outputs } = useOutputs(params.studyId);
  const deleteStudy = useDeleteStudy();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const handleDelete = async () => {
    if (!data) return;
    try {
      await deleteStudy.mutateAsync(params.studyId);
      toast.success(`Deleted "${data.meta.title}"`);
      router.push("/studies");
    } catch (err) {
      toast.error(`Could not delete study: ${err instanceof Error ? err.message : err}`);
    }
  };

  if (isLoading || !data) return <div className="p-6 text-sm text-slate-500">Loading…</div>;

  const cfg = data.config;
  const meta = data.meta;
  const arms = cfg.treatment_arms ?? [];
  const totalN = Object.values(cfg.analysis_sets?.SAF?.n ?? {}).reduce<number>(
    (a, b) => a + (Number(b) || 0),
    0,
  );
  const optional = cfg.optional_outputs ?? {};
  const selected = Object.values(optional).filter(Boolean).length;
  const total = Object.keys(optional).length;
  const selectedPct = total > 0 ? (selected / total) * 100 : 0;
  const generated = (outputs ?? []).length;
  const approved = (outputs ?? []).filter((o) => o.status === "approved").length;
  const failed = (jobs ?? []).filter((j) => j.status === "failed").length;

  return (
    <div className="flex h-full flex-col">
      <Header title="Study Overview" action={<StatusBadge status={meta.status} />} />
      <div className="space-y-6 p-6">
        {/* ---- Identity strip ---- */}
        <div className="space-y-1">
          <h2 className="text-lg font-semibold leading-snug text-foreground">
            {cfg.protocol_title || meta.title}
          </h2>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-500">
            <span className="font-medium text-slate-700">{cfg.protocol_number || "—"}</span>
            {cfg.drug && (
              <>
                <Dot />
                <span>{cfg.drug}</span>
              </>
            )}
            {(cfg.indication || meta.indication) && (
              <>
                <Dot />
                <span className="truncate">{cfg.indication || meta.indication}</span>
              </>
            )}
          </div>
        </div>

        {/* ---- KPI cards ---- */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            icon={<Users className="h-5 w-5" />}
            label="Population"
            value={totalN > 0 ? totalN.toLocaleString() : "—"}
            sub={`${arms.length} treatment arm${arms.length === 1 ? "" : "s"} · Safety set`}
          />
          <KpiCard
            icon={<ClipboardList className="h-5 w-5" />}
            label="TFLs Selected"
            value={`${selected} / ${total || "—"}`}
            sub={
              <Progress value={selectedPct} className="mt-2 h-1.5" />
            }
          />
          <KpiCard
            icon={<FileText className="h-5 w-5" />}
            label="Outputs Generated"
            value={String(generated)}
            sub={`${approved} signed off · ${failed} failed`}
            tone={failed > 0 ? "warn" : "default"}
          />
          <KpiCard
            icon={<CalendarDays className="h-5 w-5" />}
            label="Data Extract"
            value={cfg.data_extract_date || "Not set"}
            sub={cfg.data_extract_date ? "Used in output footers" : "Required before generating"}
            tone={cfg.data_extract_date ? "default" : "warn"}
          />
        </div>

        {/* ---- Actions ---- */}
        <div className="flex flex-wrap gap-2">
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
            className="border-rose-200 text-rose-700 hover:bg-rose-50"
            onClick={() => setConfirmingDelete(true)}
            disabled={deleteStudy.isPending}
          >
            <Trash2 className="h-4 w-4" /> {deleteStudy.isPending ? "Deleting…" : "Delete Study"}
          </Button>
          <ConfirmDialog
            open={confirmingDelete}
            title={`Delete "${data.meta.title}"?`}
            description={
              <>
                This permanently removes all uploaded ADaM data,{" "}
                <span className="font-medium">{generated}</span> generated output
                {generated === 1 ? "" : "s"}, and the audit records for this study from disk.
                This cannot be undone.
              </>
            }
            confirmLabel="Delete study"
            busy={deleteStudy.isPending}
            onConfirm={handleDelete}
            onCancel={() => setConfirmingDelete(false)}
          />
        </div>

        {/* ---- Detail panels ---- */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Study details */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FlaskConical className="h-4 w-4 text-primary" /> Study Details
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
                <Detail label="Protocol number" value={cfg.protocol_number} />
                <Detail label="Drug" value={cfg.drug} />
                <Detail label="Indication" value={cfg.indication || meta.indication} />
                <Detail label="MedDRA version" value={cfg.meddra_version} />
                <Detail label="WHO Drug version" value={cfg.who_drug_version} />
                <Detail label="SAS version" value={cfg.sas_version} />
                <Detail label="Data extract date" value={cfg.data_extract_date} warn={!cfg.data_extract_date} />
                <Detail label="Data cut date" value={cfg.data_cut_date} />
              </dl>

              {arms.length > 0 && (
                <div className="border-t pt-4">
                  <p className="mb-2 text-xs font-medium text-slate-500">Treatment arms</p>
                  <div className="flex flex-wrap gap-2">
                    {arms.map((arm, i) => (
                      <Badge
                        key={i}
                        className="border-border bg-accent text-accent-foreground"
                      >
                        {arm.label}
                        {arm.target_daily_dose_mg != null && (
                          <span className="ml-1 font-normal opacity-70">· {arm.target_daily_dose_mg} mg</span>
                        )}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Activity */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <CheckCircle2 className="h-4 w-4 text-primary" /> Activity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <TimelineRow label="Created" value={formatTimestamp(meta.created_at)} />
              <TimelineRow label="Last updated" value={formatTimestamp(meta.updated_at)} />
              <TimelineRow
                label="Last generated"
                value={meta.last_generated_at ? formatTimestamp(meta.last_generated_at) : "Never"}
                muted={!meta.last_generated_at}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  icon,
  label,
  value,
  sub,
  tone = "default",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: React.ReactNode;
  tone?: "default" | "warn";
}) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            tone === "warn" ? "bg-amber-100 text-amber-700" : "bg-accent text-accent-foreground",
          )}
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className={cn("truncate text-2xl font-semibold", tone === "warn" && "text-amber-700")}>
            {value}
          </p>
          {typeof sub === "string" ? (
            <p className="truncate text-xs text-slate-400">{sub}</p>
          ) : (
            sub
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Detail({ label, value, warn }: { label: string; value?: string | null; warn?: boolean }) {
  const empty = !value;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={cn("text-sm font-medium", empty && (warn ? "text-amber-600" : "text-slate-400"))}>
        {value || (warn ? "Not set" : "—")}
      </dd>
    </div>
  );
}

function TimelineRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className={cn("font-medium", muted && "text-slate-400")}>{value}</span>
    </div>
  );
}

function Dot() {
  return <span className="text-slate-300">•</span>;
}
