"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowRight, FlaskConical, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusBadge } from "@/components/ui/badge";
import { useDeleteStudy } from "@/hooks/useStudy";
import { formatTimestamp } from "@/lib/utils";
import type { StudySummary } from "@/types/study";

export function StudyCard({ study }: { study: StudySummary }) {
  const deleteStudy = useDeleteStudy();
  const [confirming, setConfirming] = useState(false);

  const handleDelete = () => {
    deleteStudy.mutate(study.study_id, {
      onSuccess: () => {
        setConfirming(false);
        toast.success(`Deleted "${study.title}"`);
      },
      onError: (err) =>
        toast.error(`Could not delete study: ${err instanceof Error ? err.message : err}`),
    });
  };

  return (
    <>
      <Link href={`/studies/${study.study_id}`} className="block">
        <Card className="transition-shadow hover:shadow-md relative">
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-2 right-2 h-8 w-8 text-slate-400 hover:text-rose-700 hover:bg-rose-50"
            onClick={(e) => {
              // Don't let the click bubble up to the wrapping <Link>.
              e.preventDefault();
              e.stopPropagation();
              setConfirming(true);
            }}
            disabled={deleteStudy.isPending}
            aria-label="Delete study"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <CardHeader>
            <div className="flex items-start justify-between gap-2 pr-8">
              <div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <FlaskConical className="h-3.5 w-3.5" />
                  {study.protocol_number || "—"}
                </div>
                <CardTitle className="mt-1">{study.title}</CardTitle>
                <CardDescription className="mt-1">
                  {[study.drug, study.indication].filter(Boolean).join(" · ") || "Drug / indication not set"}
                </CardDescription>
              </div>
              <StatusBadge status={study.status} />
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between text-slate-600">
              <span>Treatment arms</span>
              <span className="font-medium">{study.n_arms}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Total N</span>
              <span className="font-medium">{study.total_n}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>TFLs selected</span>
              <span className="font-medium">
                {study.selected_tables} / {study.available_tables}
              </span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Last generated</span>
              <span className="font-medium">{formatTimestamp(study.last_generated_at)}</span>
            </div>
            <div className="flex items-center justify-end gap-1 text-primary text-xs pt-2">
              Open <ArrowRight className="h-3 w-3" />
            </div>
          </CardContent>
        </Card>
      </Link>
      <ConfirmDialog
        open={confirming}
        title={`Delete "${study.title}"?`}
        description="This permanently removes all uploaded ADaM data, generated outputs, and audit records for this study from disk. This cannot be undone."
        confirmLabel="Delete study"
        busy={deleteStudy.isPending}
        onConfirm={handleDelete}
        onCancel={() => setConfirming(false)}
      />
    </>
  );
}
