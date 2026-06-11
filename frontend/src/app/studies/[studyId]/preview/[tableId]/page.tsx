"use client";
import { useParams } from "next/navigation";
import { useEffect, useMemo } from "react";
import { Copy, Download, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/Header";
import { TablePreview } from "@/components/preview/TablePreview";
import { FigurePreview } from "@/components/preview/FigurePreview";
import { AiPanel } from "@/components/preview/AiPanel";
import { useAnomalies, usePreview } from "@/hooks/usePreview";
import { useShells } from "@/hooks/useShells";
import { preview } from "@/lib/api";

export default function TablePreviewPage() {
  const params = useParams<{ studyId: string; tableId: string }>();
  const previewMutation = usePreview(params.studyId, params.tableId);
  const anomaliesMutation = useAnomalies(params.studyId, params.tableId);
  const { data: shellList } = useShells(params.studyId);

  // Resolve the human-readable name ("Table 14.3.1.2 — Summary of ...")
  // instead of showing the raw shell id in the header.
  const shellInfo = useMemo(() => {
    for (const g of shellList?.groups ?? []) {
      for (const s of g.shells) {
        if (s.id === params.tableId) return s;
      }
    }
    return null;
  }, [shellList, params.tableId]);
  const heading = shellInfo
    ? `${shellInfo.type === "figure" ? "Figure" : "Table"} ${shellInfo.table_number}`
    : `Preview · ${params.tableId}`;

  const data = previewMutation.data;
  const isFigure = data?.kind === "figure";

  // Users arrive from a "Preview" button — run the aggregation immediately
  // instead of presenting a second button.
  useEffect(() => {
    previewMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.studyId, params.tableId]);

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
    toast.success("Table rows copied to clipboard");
  };

  return (
    <div className="flex h-full flex-col">
      <Header
        title={heading}
        action={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending}
            >
              <RefreshCw className="h-4 w-4" /> Regenerate
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
          </div>
        }
      />
      {shellInfo && (
        <div className="border-b bg-white px-6 py-2 text-sm text-slate-600">
          {shellInfo.title_line2}
          {shellInfo.title_line3 && (
            <span className="text-slate-400"> · {shellInfo.title_line3}</span>
          )}
        </div>
      )}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-6 lg:grid-cols-[1fr_360px]">
        <div className="min-h-0 overflow-auto">
          {previewMutation.isPending && (
            <div className="rounded-md border-2 border-dashed p-12 text-center">
              <RefreshCw className="mx-auto mb-3 h-8 w-8 animate-spin text-slate-400" />
              <p className="text-sm text-slate-500">
                Running the aggregation against the study&apos;s ADaM data…
              </p>
            </div>
          )}
          {previewMutation.error && !previewMutation.isPending && (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              <p className="font-medium">Preview failed</p>
              <p className="mt-1">{String(previewMutation.error)}</p>
              <Button
                size="sm"
                variant="outline"
                className="mt-3"
                onClick={() => previewMutation.mutate()}
              >
                Try again
              </Button>
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
