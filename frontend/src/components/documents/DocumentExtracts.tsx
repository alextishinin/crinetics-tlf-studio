"use client";
import { useState } from "react";
import { FileText, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ai } from "@/lib/api";
import type { ExtractedField } from "@/types/ai";

// Shape stored under study_config.yaml -> document_extracts.
export interface CrfCategory {
  label?: string;
  values: string[];
  source_excerpt?: string;
}
export interface DocumentExtractsValue {
  protocol?: { source_file?: string; fields?: Record<string, ExtractedField> };
  crf?: { source_file?: string; category_lists?: Record<string, CrfCategory> };
}

// Protocol fields we surface for review (besides the identifiers, which are
// applied to the main study fields via onApplyProtocol).
const PROTOCOL_FIELD_ORDER = [
  "protocol_number",
  "protocol_title",
  "indication",
  "phase",
  "study_design",
  "primary_objective",
  "treatment_summary",
];
const PROTOCOL_LABELS: Record<string, string> = {
  protocol_number: "Protocol number",
  protocol_title: "Protocol title",
  indication: "Indication",
  phase: "Phase",
  study_design: "Study design",
  primary_objective: "Primary objective",
  treatment_summary: "Treatment arms & doses",
};

interface Props {
  value: DocumentExtractsValue;
  onChange: (next: DocumentExtractsValue) => void;
  // Called when the user clicks "Apply to study fields" so the parent can
  // copy protocol_number / protocol_title / indication into the real config.
  onApplyProtocol?: (fields: Record<string, string>) => void;
}

export function DocumentExtracts({ value, onChange, onApplyProtocol }: Props) {
  const [busy, setBusy] = useState<"protocol" | "crf" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleProtocol = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setBusy("protocol");
    try {
      const res = await ai.protocol(file);
      if (res.error) throw new Error(res.error);
      onChange({ ...value, protocol: { source_file: file.name, fields: res.fields } });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const handleCrf = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setBusy("crf");
    try {
      const res = await ai.crf(file);
      if (res.error) throw new Error(res.error);
      const dict: Record<string, CrfCategory> = {};
      for (const cl of res.category_lists) {
        dict[cl.variable.toUpperCase()] = {
          label: cl.label,
          values: cl.values,
          source_excerpt: cl.source_excerpt,
        };
      }
      onChange({ ...value, crf: { source_file: file.name, category_lists: dict } });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const protocolFields = value.protocol?.fields ?? {};
  const crfLists = value.crf?.category_lists ?? {};

  const setProtocolField = (key: string, v: string) => {
    onChange({
      ...value,
      protocol: {
        ...value.protocol,
        fields: { ...protocolFields, [key]: { ...(protocolFields[key] ?? { source_excerpt: "", confidence: "medium" }), value: v } },
      },
    });
  };

  const setCrfValues = (variable: string, text: string) => {
    const values = text.split("\n").map((l) => l.trim()).filter(Boolean);
    onChange({
      ...value,
      crf: {
        ...value.crf,
        category_lists: { ...crfLists, [variable]: { ...(crfLists[variable] ?? {}), values } },
      },
    });
  };

  const removeCrfVariable = (variable: string) => {
    const next = { ...crfLists };
    delete next[variable];
    onChange({ ...value, crf: { ...value.crf, category_lists: next } });
  };

  const orderedProtocolKeys = [
    ...PROTOCOL_FIELD_ORDER.filter((k) => k in protocolFields),
    ...Object.keys(protocolFields).filter((k) => !PROTOCOL_FIELD_ORDER.includes(k)),
  ];

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>
      )}

      {/* ---- Protocol ---- */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Protocol</CardTitle>
          <CardDescription>
            Upload the protocol (PDF/DOCX). AI extracts study metadata — review and edit below.
            {value.protocol?.source_file ? ` Source: ${value.protocol.source_file}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <Input
              type="file"
              accept=".pdf,.docx"
              className="max-w-xs"
              disabled={busy !== null}
              onChange={(e) => handleProtocol(e.target.files?.[0])}
            />
            {busy === "protocol" && <span className="text-xs text-slate-500">Extracting…</span>}
          </div>
          {orderedProtocolKeys.length > 0 && (
            <div className="space-y-3">
              {orderedProtocolKeys.map((key) => (
                <div key={key} className="space-y-1">
                  <Label className="text-xs flex items-center gap-2">
                    {PROTOCOL_LABELS[key] ?? key}
                    <ConfidenceTag c={protocolFields[key]?.confidence} />
                  </Label>
                  <Input value={protocolFields[key]?.value ?? ""} onChange={(e) => setProtocolField(key, e.target.value)} />
                  {protocolFields[key]?.source_excerpt && (
                    <p className="text-[11px] italic text-slate-400">“{protocolFields[key].source_excerpt}”</p>
                  )}
                </div>
              ))}
              {onApplyProtocol && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onApplyProtocol({
                      protocol_number: protocolFields.protocol_number?.value ?? "",
                      protocol_title: protocolFields.protocol_title?.value ?? "",
                      indication: protocolFields.indication?.value ?? "",
                    })
                  }
                >
                  <FileText className="h-4 w-4" /> Apply identifiers to study fields
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ---- CRF ---- */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">CRF Categories</CardTitle>
          <CardDescription>
            Upload the CRF (PDF/DOCX). AI extracts category lists/order for key variables. These
            drive the order of disposition reasons, race, ethnicity, etc. in the generated tables —
            edit them to match the CRF exactly.
            {value.crf?.source_file ? ` Source: ${value.crf.source_file}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <Input
              type="file"
              accept=".pdf,.docx"
              className="max-w-xs"
              disabled={busy !== null}
              onChange={(e) => handleCrf(e.target.files?.[0])}
            />
            {busy === "crf" && <span className="text-xs text-slate-500">Extracting…</span>}
          </div>
          {Object.keys(crfLists).length === 0 ? (
            <p className="text-xs text-slate-500">No CRF categories yet. Upload a CRF to extract them.</p>
          ) : (
            <div className="space-y-4">
              {Object.entries(crfLists).map(([variable, cat]) => (
                <div key={variable} className="space-y-1">
                  <Label className="text-xs flex items-center justify-between">
                    <span>
                      {variable}
                      {cat.label ? ` — ${cat.label}` : ""}
                    </span>
                    <button
                      type="button"
                      className="text-slate-400 hover:text-rose-600"
                      onClick={() => removeCrfVariable(variable)}
                      title="Remove this variable"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </Label>
                  <Textarea
                    rows={Math.min(8, Math.max(3, cat.values.length))}
                    value={cat.values.join("\n")}
                    onChange={(e) => setCrfValues(variable, e.target.value)}
                    placeholder="One category per line, in CRF order"
                  />
                  {cat.source_excerpt && (
                    <p className="text-[11px] italic text-slate-400">“{cat.source_excerpt}”</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ConfidenceTag({ c }: { c?: "high" | "medium" | "low" }) {
  if (!c) return null;
  const color =
    c === "high" ? "text-emerald-600" : c === "low" ? "text-rose-600" : "text-amber-600";
  return <span className={`text-[10px] uppercase ${color}`}>{c}</span>;
}
