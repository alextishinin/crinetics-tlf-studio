"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import {
  ClipboardCheck,
  Download,
  Eye,
  FileSignature,
  FileText,
  History,
  Package,
  Undo2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/badge";
import { Header } from "@/components/layout/Header";
import { QcDialog, ReviewTrailDialog, SignoffDialog } from "@/components/outputs/ReviewDialogs";
import { useOutputs } from "@/hooks/usePreview";
import { outputs } from "@/lib/api";
import { formatBytes, formatTimestamp } from "@/lib/utils";
import type { OutputRecord } from "@/types/job";

export default function OutputsPage() {
  const params = useParams<{ studyId: string }>();
  const { data, refetch } = useOutputs(params.studyId);
  const [search, setSearch] = useState("");
  const [signedOffOnly, setSignedOffOnly] = useState(false);

  // Which output a dialog is open for (null = closed).
  const [qcFor, setQcFor] = useState<OutputRecord | null>(null);
  const [signoffFor, setSignoffFor] = useState<OutputRecord | null>(null);
  const [trailFor, setTrailFor] = useState<OutputRecord | null>(null);
  const [resetFor, setResetFor] = useState<OutputRecord | null>(null);
  const [resetting, setResetting] = useState(false);

  const filtered = (data ?? []).filter((o) =>
    `${o.table_number} ${o.filename}`.toLowerCase().includes(search.toLowerCase()),
  );
  const signedOffCount = (data ?? []).filter((o) => o.status === "approved").length;
  const packageEmpty = signedOffOnly ? signedOffCount === 0 : (data ?? []).length === 0;

  const resetReview = async () => {
    if (!resetFor) return;
    setResetting(true);
    try {
      await outputs.resetReview(params.studyId, resetFor.output_id);
      toast.success(`${resetFor.table_number} reset to Pending QC`);
      refetch();
    } catch (err) {
      toast.error(`Could not reset review: ${err instanceof Error ? err.message : err}`);
    } finally {
      setResetting(false);
      setResetFor(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Outputs"
        action={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={signedOffOnly}
                onChange={(e) => setSignedOffOnly(e.target.checked)}
              />
              Signed off only ({signedOffCount})
            </label>
            {packageEmpty ? (
              <Button disabled title={signedOffOnly ? "No signed-off outputs yet" : "No outputs yet"}>
                <Package className="h-4 w-4" /> Download Package
              </Button>
            ) : (
              <Button asChild>
                <a href={outputs.packageUrl(params.studyId, signedOffOnly)}>
                  <Package className="h-4 w-4" /> Download Package
                </a>
              </Button>
            )}
          </div>
        }
      />
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <Input
            placeholder="Search by table number or filename"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-md"
          />
          <p className="text-xs text-slate-500">
            Workflow: <span className="font-medium">Pending QC</span> → QC review by a second
            programmer → <span className="font-medium">QC Passed</span> → biostatistician sign-off →{" "}
            <span className="font-medium">Signed Off</span>.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Generated Files ({filtered.length})</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500 border-b">
                <tr>
                  <th className="p-3">Table</th>
                  <th className="p-3">Filename</th>
                  <th className="p-3">Generated</th>
                  <th className="p-3">Size</th>
                  <th className="p-3">Status</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-slate-500">
                      <FileText className="mx-auto mb-2 h-6 w-6" />
                      No outputs yet. Generate some tables first.
                    </td>
                  </tr>
                )}
                {filtered.map((o) => (
                  <tr key={o.output_id} className="border-b">
                    <td className="p-3 font-mono">{o.table_number}</td>
                    <td className="p-3">{o.filename}</td>
                    <td className="p-3 text-xs text-slate-500">{formatTimestamp(o.generated_at)}</td>
                    <td className="p-3 text-xs text-slate-500">{formatBytes(o.size_bytes)}</td>
                    <td className="p-3"><StatusBadge status={o.status} /></td>
                    <td className="p-3 flex justify-end gap-1">
                      <Button asChild size="sm" variant="ghost">
                        <a
                          href={outputs.downloadUrl(params.studyId, o.output_id)}
                          aria-label={`Download ${o.filename}`}
                          title="Download"
                        >
                          <Download className="h-3.5 w-3.5" />
                        </a>
                      </Button>
                      <Button asChild size="sm" variant="ghost">
                        <Link
                          href={`/studies/${params.studyId}/preview/${o.table_id}`}
                          aria-label={`Preview ${o.table_number}`}
                          title="Preview"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Link>
                      </Button>
                      {o.status !== "approved" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setQcFor(o)}
                          aria-label={`QC review ${o.table_number}`}
                          title={o.status === "pending" ? "QC review" : "Redo QC review"}
                        >
                          <ClipboardCheck className="h-3.5 w-3.5 text-blue-700" />
                        </Button>
                      )}
                      {o.status === "qc_passed" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSignoffFor(o)}
                          aria-label={`Sign off ${o.table_number}`}
                          title="Biostatistician sign-off"
                        >
                          <FileSignature className="h-3.5 w-3.5 text-emerald-700" />
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setTrailFor(o)}
                        aria-label={`Review trail for ${o.table_number}`}
                        title="Review trail"
                      >
                        <History className="h-3.5 w-3.5 text-slate-500" />
                      </Button>
                      {o.status !== "pending" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setResetFor(o)}
                          aria-label={`Reset review for ${o.table_number}`}
                          title="Reset review to Pending QC"
                        >
                          <Undo2 className="h-3.5 w-3.5 text-slate-500" />
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

      {qcFor && (
        <QcDialog
          studyId={params.studyId}
          output={qcFor}
          onClose={() => setQcFor(null)}
          onDone={() => {
            toast.success(`QC recorded for ${qcFor.table_number}`);
            setQcFor(null);
            refetch();
          }}
        />
      )}
      {signoffFor && (
        <SignoffDialog
          studyId={params.studyId}
          output={signoffFor}
          onClose={() => setSignoffFor(null)}
          onDone={() => {
            toast.success(`${signoffFor.table_number} signed off`);
            setSignoffFor(null);
            refetch();
          }}
        />
      )}
      {trailFor && (
        <ReviewTrailDialog
          studyId={params.studyId}
          output={trailFor}
          onClose={() => setTrailFor(null)}
        />
      )}
      <ConfirmDialog
        open={resetFor !== null}
        title={`Reset review for ${resetFor?.table_number ?? ""}?`}
        description="The output returns to Pending QC. Existing QC and sign-off records are archived in the review trail (not deleted)."
        confirmLabel="Reset review"
        busy={resetting}
        onConfirm={resetReview}
        onCancel={() => setResetFor(null)}
      />
    </div>
  );
}
