"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CheckCircle2, Download, Eye, FileText, Package, Undo2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/badge";
import { Header } from "@/components/layout/Header";
import { useOutputs } from "@/hooks/usePreview";
import { outputs } from "@/lib/api";
import { formatBytes, formatTimestamp } from "@/lib/utils";

export default function OutputsPage() {
  const params = useParams<{ studyId: string }>();
  const { data, refetch } = useOutputs(params.studyId);
  const [search, setSearch] = useState("");
  const [approvedOnly, setApprovedOnly] = useState(false);

  const filtered = (data ?? []).filter((o) =>
    `${o.table_number} ${o.filename}`.toLowerCase().includes(search.toLowerCase()),
  );
  const approvedCount = (data ?? []).filter((o) => o.status === "approved").length;
  const packageEmpty = approvedOnly ? approvedCount === 0 : (data ?? []).length === 0;

  const setStatus = async (outputId: string, status: "approved" | "pending") => {
    try {
      await outputs.setStatus(params.studyId, outputId, status);
      toast.success(status === "approved" ? "Output approved" : "Approval removed");
      refetch();
    } catch (err) {
      toast.error(`Could not update status: ${err instanceof Error ? err.message : err}`);
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
                checked={approvedOnly}
                onChange={(e) => setApprovedOnly(e.target.checked)}
              />
              Approved only ({approvedCount})
            </label>
            {packageEmpty ? (
              <Button disabled title={approvedOnly ? "No approved outputs yet" : "No outputs yet"}>
                <Package className="h-4 w-4" /> Download Package
              </Button>
            ) : (
              <Button asChild>
                <a href={outputs.packageUrl(params.studyId, approvedOnly)}>
                  <Package className="h-4 w-4" /> Download Package
                </a>
              </Button>
            )}
          </div>
        }
      />
      <div className="p-6 space-y-4">
        <Input
          placeholder="Search by table number or filename"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-md"
        />

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
                      {o.status !== "approved" ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setStatus(o.output_id, "approved")}
                          aria-label={`Approve ${o.table_number}`}
                          title="Approve"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" />
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setStatus(o.output_id, "pending")}
                          aria-label={`Remove approval from ${o.table_number}`}
                          title="Remove approval"
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
    </div>
  );
}
