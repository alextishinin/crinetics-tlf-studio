"use client";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { Copy, Download, Flag, PlayCircle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/Header";
import { TablePreview } from "@/components/preview/TablePreview";
import { FigurePreview } from "@/components/preview/FigurePreview";
import { AiPanel } from "@/components/preview/AiPanel";
import { useAnomalies, usePreview } from "@/hooks/usePreview";
import { preview } from "@/lib/api";

export default function TablePreviewPage() {
  const params = useParams<{ studyId: string; tableId: string }>();
  const previewMutation = usePreview(params.studyId, params.tableId);
  const anomaliesMutation = useAnomalies(params.studyId, params.tableId);

  const data = previewMutation.data;
  const isFigure = data?.kind === "figure";

  // Auto-scan anomalies once a TABLE preview returns. Figures have no rows.
  useEffect(() => {
    if (data && !isFigure && !anomaliesMutation.isPending) {
      anomaliesMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewMutation.data]);

  const handleCopy = () => {
    if (!data || data.kind === "figure") return;
    const rows = data.body_rows.map((r) => r.join("\t")).join("\n");
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
            <Button variant="outline" disabled={!data || isFigure} onClick={handleCopy}>
              <Copy className="h-4 w-4" /> Copy
            </Button>
            <Button variant="outline" disabled={!data || isFigure} asChild>
              {/* Generates the RTF on demand from current data, then downloads it. */}
              <a href={preview.rtfUrl(params.studyId, params.tableId)}>
                <Download className="h-4 w-4" /> Download RTF
              </a>
            </Button>
            <Button variant="outline" disabled={!data}>
              <Flag className="h-4 w-4" /> Flag Issue
            </Button>
          </div>
        }
      />
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-6 lg:grid-cols-[1fr_360px]">
        <div className="min-h-0 overflow-auto">
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
          {data &&
            (data.kind === "figure" ? (
              <FigurePreview data={data} />
            ) : (
              <TablePreview data={data} />
            ))}
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
