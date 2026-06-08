"use client";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileText, Loader2, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { SapReviewPanel } from "@/components/ai/SapReviewPanel";
import { ai } from "@/lib/api";
import type { ExtractedField, SapExtractionResponse } from "@/types/ai";

// Shape stored under study_config.yaml -> document_extracts.
export interface CrfCategory {
  label?: string;
  values: string[];
  source_excerpt?: string;
}
export interface DocumentExtractsValue {
  protocol?: { source_file?: string; fields?: Record<string, ExtractedField> };
  crf?: { source_file?: string; category_lists?: Record<string, CrfCategory> };
  sap?: { source_file?: string; extraction?: SapExtractionResponse };
}

type BusyKind = "protocol" | "crf" | "sap";
const BUSY_LABELS: Record<BusyKind, string> = {
  protocol: "protocol",
  crf: "CRF",
  sap: "SAP",
};

// Protocol fields we surface for review (besides the identifiers, which are
// applied to the main study fields via onApplyProtocol).
const PROTOCOL_FIELD_ORDER = [
  "protocol_number",
  "protocol_title",
  "drug",
  "indication",
  "phase",
  "study_design",
  "primary_objective",
  "treatment_summary",
];
const PROTOCOL_LABELS: Record<string, string> = {
  protocol_number: "Protocol number",
  protocol_title: "Protocol title",
  drug: "Drug",
  indication: "Indication",
  phase: "Phase",
  study_design: "Study design",
  primary_objective: "Primary objective",
  treatment_summary: "Treatment arms & doses",
};

interface Props {
  value: DocumentExtractsValue;
  onChange: (next: DocumentExtractsValue) => void;
  // Called when the user clicks "Apply identifiers to study fields" so the
  // parent can copy protocol_number / title / drug / indication into config.
  onApplyProtocol?: (fields: Record<string, string>) => void;
  // When true, the SAP upload card is shown. The reviewed extraction is stored
  // in value.sap.extraction (persisted), mirroring how protocol fields persist.
  showSap?: boolean;
  // When provided, an "Apply to SAP definitions" button is shown; receives the
  // reviewed extraction so the parent can map it into its canonical editor.
  onApplySap?: (extraction: SapExtractionResponse) => void;
}

export function DocumentExtracts({
  value,
  onChange,
  onApplyProtocol,
  showSap,
  onApplySap,
}: Props) {
  const [busy, setBusy] = useState<BusyKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<"protocol" | "sap" | null>(null);

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

  const handleSap = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setBusy("sap");
    try {
      const res = await ai.sap(file);
      onChange({ ...value, sap: { source_file: file.name, extraction: res } });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const protocolFields = value.protocol?.fields ?? {};
  const crfLists = value.crf?.category_lists ?? {};
  const sapExtraction = value.sap?.extraction;

  const setProtocolField = (key: string, v: string) => {
    onChange({
      ...value,
      protocol: {
        ...value.protocol,
        fields: { ...protocolFields, [key]: { ...(protocolFields[key] ?? { source_excerpt: "", confidence: "medium" }), value: v } },
      },
    });
  };

  const handleApplyProtocol = () => {
    onApplyProtocol?.({
      protocol_number: protocolFields.protocol_number?.value ?? "",
      protocol_title: protocolFields.protocol_title?.value ?? "",
      drug: protocolFields.drug?.value ?? "",
      indication: protocolFields.indication?.value ?? "",
    });
    setApplied("protocol");
  };

  const handleApplySap = () => {
    if (sapExtraction) onApplySap?.(sapExtraction);
    setApplied("sap");
  };

  // Clear the transient "Applied" confirmation after a moment.
  useEffect(() => {
    if (!applied) return;
    const t = setTimeout(() => setApplied(null), 2000);
    return () => clearTimeout(t);
  }, [applied]);

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
      {busy && <ExtractionOverlay label={BUSY_LABELS[busy]} />}

      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>
      )}

      {/* ---- Protocol ---- */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Protocol</CardTitle>
          <CardDescription>
            Upload the protocol (PDF/DOCX). AI extracts study metadata — review and edit below.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <FileUpload
            currentFile={value.protocol?.source_file}
            disabled={busy !== null}
            onPick={handleProtocol}
          />
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
                <ApplyButton
                  applied={applied === "protocol"}
                  idleLabel="Apply identifiers to study fields"
                  appliedLabel="Applied to study fields"
                  onClick={handleApplyProtocol}
                />
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
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <FileUpload
            currentFile={value.crf?.source_file}
            disabled={busy !== null}
            onPick={handleCrf}
          />
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

      {/* ---- SAP (only when the parent wires it up) ---- */}
      {showSap && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Statistical Analysis Plan (SAP)</CardTitle>
            <CardDescription>
              Upload the SAP (PDF/DOCX). AI extracts SAP definitions and proposes which optional
              tables to include — review and edit below.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <FileUpload
              currentFile={value.sap?.source_file}
              disabled={busy !== null}
              onPick={handleSap}
            />
            {sapExtraction && (
              <SapReviewPanel
                extraction={sapExtraction}
                onChange={(next) => onChange({ ...value, sap: { ...value.sap, extraction: next } })}
              />
            )}
            {sapExtraction && !sapExtraction.error && onApplySap && (
              <ApplyButton
                applied={applied === "sap"}
                idleLabel="Apply to SAP definitions"
                appliedLabel="Applied to SAP definitions"
                onClick={handleApplySap}
              />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function FileUpload({
  currentFile,
  disabled,
  onPick,
}: {
  currentFile?: string;
  disabled?: boolean;
  onPick: (file: File | undefined) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-3">
      <input
        ref={ref}
        type="file"
        accept=".pdf,.docx"
        className="hidden"
        disabled={disabled}
        onChange={(e) => {
          onPick(e.target.files?.[0]);
          e.target.value = ""; // allow re-selecting the same filename
        }}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => ref.current?.click()}
      >
        <Upload className="h-4 w-4" /> {currentFile ? "Change file" : "Upload file"}
      </Button>
      <span className="truncate text-xs text-slate-500" title={currentFile}>
        {currentFile || "No file uploaded yet"}
      </span>
    </div>
  );
}

function ApplyButton({
  applied,
  idleLabel,
  appliedLabel,
  onClick,
}: {
  applied: boolean;
  idleLabel: string;
  appliedLabel: string;
  onClick: () => void;
}) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
      className={applied ? "border-emerald-300 text-emerald-700" : ""}
    >
      {applied ? (
        <>
          <CheckCircle2 className="h-4 w-4 text-emerald-600" /> {appliedLabel}
        </>
      ) : (
        <>
          <FileText className="h-4 w-4" /> {idleLabel}
        </>
      )}
    </Button>
  );
}

export function ExtractionOverlay({ label }: { label: string }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/20 backdrop-blur-sm animate-in fade-in">
      <div className="flex flex-col items-center gap-3 rounded-xl border bg-white px-12 py-10 shadow-2xl animate-in zoom-in-95">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-sm font-medium text-slate-700">Extracting {label}…</p>
        <p className="text-xs text-slate-400">The AI is reading your document. This can take a moment.</p>
      </div>
    </div>
  );
}

function ConfidenceTag({ c }: { c?: "high" | "medium" | "low" }) {
  if (!c) return null;
  const color =
    c === "high" ? "text-emerald-600" : c === "low" ? "text-rose-600" : "text-amber-600";
  return <span className={`text-[10px] uppercase ${color}`}>{c}</span>;
}
