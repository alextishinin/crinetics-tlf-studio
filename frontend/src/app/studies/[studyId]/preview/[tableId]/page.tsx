"use client";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { Copy, Download, Flag, PlayCircle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/Header";
import { TablePreview } from "@/components/preview/TablePreview";
import { AiPanel } from "@/components/preview/AiPanel";
import { useAnomalies, usePreview } from "@/hooks/usePreview";
import { outputs } from "@/lib/api";

export default function TablePreviewPage() {
  const params = useParams<{ studyId: string; tableId: string }>();
  const previewMutation = usePreview(params.studyId, params.tableId);
  const anomaliesMutation = useAnomalies(params.studyId, params.tableId);

  // Auto-scan anomalies once the preview returns.
  useEffect(() => {
    if (previewMutation.data && !anomaliesMutation.isPending) {
      anomaliesMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewMutation.data]);

  const handleCopy = () => {
    if (!previewMutation.data) return;
    const rows = previewMutation.data.body_rows
      .map((r) => r.join("\t"))
      .join("\n");
    void navigator.clipboard.writeText(rows);
  };

  return (
    <div className="flex h-full flex-col">
      <Header
        title={`Preview · ${params.tableId}`}
        action={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending}
            >
              <RefreshCw className="h-4 w-4" /> {previewMutation.data ? "Regenerate" : "Generate"}
            </Button>
            <Button variant="outline" disabled={!previewMutation.data} onClick={handleCopy}>
              <Copy className="h-4 w-4" /> Copy
            </Button>
            <Button variant="outline" disabled={!previewMutation.data} asChild>
              {/* Download link is best-effort — assumes the user has generated the RTF previously. */}
              <a
                href={outputs.downloadUrl(
                  params.studyId,
                  `CDISCPILOT01_Table_${params.tableId.replace(/^t_/, "").replace(/_/g, ".")}`,
                )}
              >
                <Download className="h-4 w-4" /> Download RTF
              </a>
            </Button>
            <Button variant="outline" disabled={!previewMutation.data}>
              <Flag className="h-4 w-4" /> Flag Issue
            </Button>
          </div>
        }
      />
      <div className="grid grid-cols-1 gap-4 overflow-auto p-6 lg:grid-cols-[1fr_360px]">
        <div>
          {!previewMutation.data && !previewMutation.isPending && (
            <div className="rounded-md border-2 border-dashed p-12 text-center">
              <PlayCircle className="mx-auto mb-3 h-8 w-8 text-slate-400" />
              <p className="text-sm text-slate-500 mb-3">
                Generate a preview to run the aggregation against real ADaM data.
              </p>
              <Button onClick={() => previewMutation.mutate()}>Generate Preview</Button>
            </div>
          )}
          {previewMutation.isPending && <p className="text-sm text-slate-500">Running aggregation…</p>}
          {previewMutation.error && (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              {String(previewMutation.error)}
            </div>
          )}
          {previewMutation.data && <TablePreview data={previewMutation.data} />}
        </div>
        <AiPanel
          studyId={params.studyId}
          tableId={params.tableId}
          anomalies={anomaliesMutation.data?.anomalies ?? []}
          onScanAnomalies={() => anomaliesMutation.mutate()}
          isScanning={anomaliesMutation.isPending}
        />
      </div>
    </div>
  );
}
