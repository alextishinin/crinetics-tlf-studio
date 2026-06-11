"use client";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, ScrollText, ShieldAlert, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Header } from "@/components/layout/Header";
import { auditTrail } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";
import type { AuditEvent } from "@/types/audit";

const ACTION_LABELS: Record<string, string> = {
  "study.created": "Study created",
  "study.config_updated": "Config updated",
  "data.uploaded": "Data uploaded",
  "tfl.selection_updated": "TFL selection",
  "generation.submitted": "Generation submitted",
  "generation.completed": "Generation completed",
  "generation.failed": "Generation failed",
  "output.qc_recorded": "QC recorded",
  "output.signed_off": "Signed off",
  "output.review_reset": "Review reset",
  "output.downloaded": "Output downloaded",
  "package.downloaded": "Package downloaded",
};

const ACTION_COLORS: Record<string, string> = {
  "study.created": "bg-slate-200 text-slate-700",
  "study.config_updated": "bg-blue-100 text-blue-700",
  "data.uploaded": "bg-violet-100 text-violet-700",
  "tfl.selection_updated": "bg-blue-100 text-blue-700",
  "generation.submitted": "bg-amber-100 text-amber-700",
  "generation.completed": "bg-emerald-100 text-emerald-700",
  "generation.failed": "bg-rose-100 text-rose-700",
  "output.qc_recorded": "bg-blue-100 text-blue-700",
  "output.signed_off": "bg-emerald-100 text-emerald-700",
  "output.review_reset": "bg-slate-200 text-slate-700",
  "output.downloaded": "bg-slate-200 text-slate-700",
  "package.downloaded": "bg-slate-200 text-slate-700",
};

const CATEGORIES: { value: string; label: string }[] = [
  { value: "", label: "All events" },
  { value: "study.", label: "Study & config" },
  { value: "data.", label: "Data uploads" },
  { value: "tfl.", label: "TFL selection" },
  { value: "generation.", label: "Generation" },
  { value: "output.", label: "Review & outputs" },
  { value: "package.", label: "Packages" },
];

// One-line human summary of an event's details.
function summarize(e: AuditEvent): React.ReactNode {
  const d = e.details as Record<string, any>;
  switch (e.action) {
    case "study.created":
      return `"${d.title}" (${d.protocol_number || "no protocol number"})`;
    case "study.config_updated":
      return (
        <ul className="space-y-0.5">
          {(d.changes ?? []).map((c: { field: string; old: string; new: string }, i: number) => (
            <li key={i} className="break-all">
              <span className="font-medium">{c.field}</span>:{" "}
              <span className="text-slate-400 line-through">{c.old || "—"}</span> →{" "}
              <span>{c.new || "—"}</span>
            </li>
          ))}
        </ul>
      );
    case "data.uploaded":
      return `${(d.files ?? []).length} file(s): ${(d.files ?? [])
        .map((f: { filename: string }) => f.filename)
        .join(", ")}`;
    case "tfl.selection_updated": {
      const on = (d.enabled ?? []) as string[];
      const off = (d.disabled ?? []) as string[];
      return [on.length ? `enabled ${on.join(", ")}` : "", off.length ? `disabled ${off.join(", ")}` : ""]
        .filter(Boolean)
        .join("; ");
    }
    case "generation.submitted":
      return `${(d.table_ids ?? []).length} table(s): ${(d.table_ids ?? []).join(", ")}`;
    case "generation.completed":
      return d.filename;
    case "generation.failed":
      return `${d.table_id} — ${d.error}`;
    case "output.qc_recorded":
      return `${d.output_id} — ${d.result === "pass" ? "passed" : "failed"} (reviewer: ${d.reviewer})`;
    case "output.signed_off":
      return `${d.output_id} — signed by ${d.name}`;
    case "output.review_reset":
      return `${d.output_id} (${d.reason})`;
    case "output.downloaded":
      return d.output_id;
    case "package.downloaded":
      return `${d.filename}${d.signed_off_only ? " (signed-off only)" : ""}`;
    default:
      return JSON.stringify(d);
  }
}

export default function AuditTrailPage() {
  const params = useParams<{ studyId: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["audit-trail", params.studyId],
    queryFn: () => auditTrail.list(params.studyId),
  });

  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const entries = [...(data?.entries ?? [])].reverse(); // newest first
    return entries.filter((e) => {
      if (category && !e.action.startsWith(category)) return false;
      if (search) {
        const haystack = `${e.actor} ${e.action} ${JSON.stringify(e.details)}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [data, category, search]);

  const chain = data?.chain;

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Audit Trail"
        action={
          <div className="flex items-center gap-3">
            {chain &&
              (chain.valid ? (
                <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                  <ShieldCheck className="h-4 w-4" /> Chain verified ({chain.entries} entries)
                </span>
              ) : (
                <span
                  className="flex items-center gap-1.5 text-xs font-medium text-rose-700"
                  title={`First invalid entry: #${chain.first_invalid_seq}`}
                >
                  <ShieldAlert className="h-4 w-4" /> Integrity check FAILED at entry #
                  {chain.first_invalid_seq}
                </span>
              ))}
            <Button asChild variant="outline">
              <a href={auditTrail.exportUrl(params.studyId)}>
                <Download className="h-4 w-4" /> Export CSV
              </a>
            </Button>
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-auto p-6">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <select
              className="h-9 rounded-md border border-input bg-white px-2 text-sm"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            <Input
              placeholder="Search actor, action, or details"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-sm"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Events ({filtered.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-xs text-slate-500">
                  <tr>
                    <th className="w-10 p-3">#</th>
                    <th className="w-44 p-3">When</th>
                    <th className="w-28 p-3">Actor</th>
                    <th className="w-44 p-3">Action</th>
                    <th className="p-3">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-slate-500">
                        Loading…
                      </td>
                    </tr>
                  )}
                  {!isLoading && filtered.length === 0 && (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-slate-500">
                        <ScrollText className="mx-auto mb-2 h-6 w-6" />
                        No audit events{category || search ? " match the filter" : " yet"}.
                      </td>
                    </tr>
                  )}
                  {filtered.map((e) => (
                    <tr key={e.seq} className="border-b align-top">
                      <td className="p-3 text-xs text-slate-400">{e.seq}</td>
                      <td className="p-3 text-xs text-slate-500">{formatTimestamp(e.at)}</td>
                      <td className="p-3 text-xs">{e.actor}</td>
                      <td className="p-3">
                        <Badge
                          className={`border-transparent ${ACTION_COLORS[e.action] ?? "bg-slate-200 text-slate-700"}`}
                        >
                          {ACTION_LABELS[e.action] ?? e.action}
                        </Badge>
                      </td>
                      <td className="p-3 text-xs text-slate-600">{summarize(e)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
