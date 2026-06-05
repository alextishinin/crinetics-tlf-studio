"use client";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, FileText, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Header } from "@/components/layout/Header";
import { TreatmentArmEditor } from "@/components/studies/TreatmentArmEditor";
import { AnalysisSetEditor } from "@/components/studies/AnalysisSetEditor";
import { SapReviewPanel } from "@/components/ai/SapReviewPanel";
import { DocumentExtracts, type DocumentExtractsValue } from "@/components/documents/DocumentExtracts";
import {
  useCreateStudy,
  useUpdateStudy,
} from "@/hooks/useStudy";
import { useSapExtraction } from "@/hooks/useAi";
import { studies as studiesApi } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import type { AnalysisSet, TreatmentArm, UploadResult } from "@/types/study";
import type { SapExtractionResponse } from "@/types/ai";

const STEPS = [
  { id: 1, label: "Select Data" },
  { id: 2, label: "Configuration" },
  { id: 3, label: "Documents" },
  { id: 4, label: "Review" },
];

// ADaM dataset extensions we pull out of the selected folder.
const DATA_EXTENSIONS = [".parquet", ".sas7bdat", ".xpt"];

export default function NewStudyPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [studyId, setStudyId] = useState<string | null>(null);

  // Step 1 state
  const [files, setFiles] = useState<File[]>([]);
  const [folderName, setFolderName] = useState<string>("");
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);

  // Step 2 state
  const [title, setTitle] = useState("");
  const [protocol, setProtocol] = useState("");
  const [drug, setDrug] = useState("");
  const [indication, setIndication] = useState("");
  const [meddra, setMeddra] = useState("25.0");
  const [whoDrug, setWhoDrug] = useState("");
  const [sasVersion, setSasVersion] = useState("9.4");
  const [dataExtractDate, setDataExtractDate] = useState("");
  const [dataCutDate, setDataCutDate] = useState("");
  const [arms, setArms] = useState<TreatmentArm[]>([]);
  const [sets, setSets] = useState<Record<string, AnalysisSet>>({});
  const [includeTotal, setIncludeTotal] = useState(true);
  const [pooledActive, setPooledActive] = useState(false);

  // Step 3 state
  const [sapFile, setSapFile] = useState<File | null>(null);
  const [sapExtraction, setSapExtraction] = useState<SapExtractionResponse | null>(null);
  const [documentExtracts, setDocumentExtracts] = useState<DocumentExtractsValue>({});

  const createStudy = useCreateStudy();
  const updateStudy = useUpdateStudy(studyId ?? "");
  const sapMutation = useSapExtraction();
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Sets the non-standard folder-picker attributes on the file input so the
  // browser shows a "select folder" dialog instead of a file dialog.
  const folderInputRef = useCallback((node: HTMLInputElement | null) => {
    if (node) {
      node.setAttribute("webkitdirectory", "");
      node.setAttribute("directory", "");
    }
  }, []);

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const all = Array.from(e.target.files ?? []);
    // Keep only recognised ADaM datasets; ignore anything else in the folder.
    const dataFiles = all.filter((f) =>
      DATA_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext)),
    );
    setFiles(dataFiles);
    // The first path segment of webkitRelativePath is the chosen folder name.
    const first = all[0] as (File & { webkitRelativePath?: string }) | undefined;
    const rel = first?.webkitRelativePath ?? "";
    setFolderName(rel ? rel.split("/")[0] : "");
    setUploadError(null);
    setUploadResult(null);
  };

  const ensureStudy = async () => {
    if (studyId) return studyId;
    const created = await createStudy.mutateAsync({
      title: title || "Untitled study",
      protocol_number: protocol,
      drug,
      indication,
    });
    setStudyId(created.meta.study_id);
    return created.meta.study_id;
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploadError(null);
    setUploading(true);
    try {
      // Call API directly with the freshly created study id rather than
      // routing through a hook closure that captured the previous (empty)
      // studyId. Avoids /api/studies//upload → 404.
      const sid = await ensureStudy();
      const result = await studiesApi.upload(sid, files);
      queryClient.invalidateQueries({ queryKey: ["study", sid] });
      setUploadResult(result);
      setArms(result.detected_arms);
      setSets(result.detected_analysis_sets);
      if (result.study_id_value) setProtocol(result.study_id_value);
      setStep(2);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  };

  const handleSapUpload = async () => {
    if (!sapFile) return;
    const result = await sapMutation.mutateAsync(sapFile);
    setSapExtraction(result);
  };

  const handleCreate = async () => {
    const sid = await ensureStudy();
    const sapDefinitions = sapExtraction
      ? Object.fromEntries(
          Object.entries(sapExtraction.sap_definitions).map(([k, v]) => [k, v.value]),
        )
      : undefined;
    const optionalOutputs = sapExtraction
      ? Object.fromEntries(sapExtraction.optional_outputs.map((o) => [o.flag, o.enabled]))
      : undefined;
    await updateStudy.mutateAsync({
      protocol_number: protocol,
      protocol_title: title,
      indication,
      meddra_version: meddra,
      who_drug_version: whoDrug,
      sas_version: sasVersion,
      data_extract_date: dataExtractDate,
      data_cut_date: dataCutDate,
      treatment_arms: arms,
      analysis_sets: sets,
      pooled_active: pooledActive,
      include_total_column: includeTotal,
      sap_definitions: sapDefinitions as any,
      optional_outputs: optionalOutputs,
      document_extracts: documentExtracts as Record<string, unknown>,
    });
    router.push(`/studies/${sid}`);
  };

  return (
    <div className="flex h-full flex-col">
      <Header title="New Study" />
      <div className="border-b bg-white">
        <div className="flex items-center justify-center gap-2 py-4">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center">
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium",
                  step === s.id
                    ? "bg-primary text-primary-foreground"
                    : step > s.id
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-slate-200 text-slate-500",
                )}
              >
                {step > s.id ? <CheckCircle2 className="h-4 w-4" /> : s.id}
              </div>
              <span className={cn("ml-2 mr-4 text-sm", step === s.id ? "font-semibold" : "text-slate-500")}>
                {s.label}
              </span>
              {i < STEPS.length - 1 && <ArrowRight className="mr-4 h-4 w-4 text-slate-300" />}
            </div>
          ))}
        </div>
      </div>

      <div className="overflow-auto p-6">
        {step === 1 && (
          <Card className="mx-auto max-w-3xl">
            <CardHeader>
              <CardTitle>Step 1 — Select Data Folder</CardTitle>
              <CardDescription>
                Choose the folder that holds your ADaM datasets. We&apos;ll find every
                .parquet, .sas7bdat, and .xpt file inside it and auto-identify each domain.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                ref={folderInputRef}
                type="file"
                multiple
                onChange={handleFolderSelect}
              />
              <div className="text-sm text-slate-600">
                {!folderName ? (
                  "No folder selected"
                ) : files.length === 0 ? (
                  <span className="text-amber-700">
                    No .parquet, .sas7bdat, or .xpt files found in &ldquo;{folderName}&rdquo;.
                  </span>
                ) : (
                  <>
                    <span className="font-medium">{folderName}</span> — {files.length} data file
                    {files.length === 1 ? "" : "s"} found
                  </>
                )}
              </div>
              {uploadResult && (
                <div className="space-y-2">
                  {uploadResult.domains.map((d) => (
                    <div key={d.filename} className="rounded-md border p-3 text-sm">
                      <div className="flex justify-between">
                        <span className="font-medium">{d.filename}</span>
                        <span className="text-slate-500">{d.domain || "unknown"}</span>
                      </div>
                      <div className="text-slate-500 text-xs mt-1">
                        {d.n_rows.toLocaleString()} rows · {d.n_subjects} subjects · {d.columns.length} columns
                      </div>
                      {d.notes.map((n, i) => (
                        <div key={i} className="text-xs text-amber-700 mt-1">{n}</div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
              {uploadError && (
                <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                  {uploadError}
                </div>
              )}
              <div className="flex justify-end gap-2">
                <Button onClick={handleUpload} disabled={files.length === 0 || uploading}>
                  <Upload className="h-4 w-4" /> {uploading ? "Uploading…" : "Upload & Continue"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card className="mx-auto max-w-4xl">
            <CardHeader>
              <CardTitle>Step 2 — Study Configuration</CardTitle>
              <CardDescription>Review and edit the auto-detected configuration.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <Field label="Protocol number" value={protocol} onChange={setProtocol} />
                <Field label="Protocol title" value={title} onChange={setTitle} />
                <Field label="Drug" value={drug} onChange={setDrug} />
                <Field label="Indication" value={indication} onChange={setIndication} />
                <Field label="MedDRA version" value={meddra} onChange={setMeddra} />
                <Field label="WHO Drug version" value={whoDrug} onChange={setWhoDrug} />
                <Field label="SAS version" value={sasVersion} onChange={setSasVersion} />
                <Field type="date" label="Data extract date" value={dataExtractDate} onChange={setDataExtractDate} />
                <Field type="date" label="Data cut date (optional)" value={dataCutDate} onChange={setDataCutDate} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold">Treatment Arms</h3>
                <TreatmentArmEditor arms={arms} onChange={setArms} />
              </div>
              <div className="flex items-center gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={includeTotal} onChange={(e) => setIncludeTotal(e.target.checked)} /> Include Total column
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={pooledActive} onChange={(e) => setPooledActive(e.target.checked)} /> Include pooled active arm
                </label>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold">Analysis Sets</h3>
                <AnalysisSetEditor sets={sets} onChange={setSets} />
              </div>
              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(1)}>
                  <ArrowLeft className="h-4 w-4" /> Back
                </Button>
                <Button onClick={() => setStep(3)}>Continue <ArrowRight className="h-4 w-4" /></Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 3 && (
          <Card className="mx-auto max-w-4xl">
            <CardHeader>
              <CardTitle>Step 3 — Source Documents</CardTitle>
              <CardDescription>
                Upload the Protocol, CRF, and SAP (PDF or Word .docx). AI reads each and extracts
                the info used to generate and label the TLFs — you can review and edit everything
                here and later on the Config page.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <DocumentExtracts
                value={documentExtracts}
                onChange={setDocumentExtracts}
                onApplyProtocol={(f) => {
                  if (f.protocol_number) setProtocol(f.protocol_number);
                  if (f.protocol_title) setTitle(f.protocol_title);
                  if (f.indication) setIndication(f.indication);
                }}
              />

              <div className="border-t pt-4">
                <Label className="text-xs font-semibold">Statistical Analysis Plan (SAP)</Label>
                <p className="mb-2 text-xs text-slate-500">
                  Extracts SAP definitions and proposes which optional tables to include.
                </p>
                <Input type="file" accept=".pdf,.docx" onChange={(e) => setSapFile(e.target.files?.[0] ?? null)} />
              <div className="flex gap-2">
                <Button onClick={handleSapUpload} disabled={!sapFile || sapMutation.isPending}>
                  <FileText className="h-4 w-4" /> Extract with AI
                </Button>
                <Button variant="outline" onClick={() => setStep(4)}>Skip — configure manually</Button>
              </div>
                {sapMutation.isPending && <p className="text-sm text-slate-500">Extracting…</p>}
                {sapExtraction && (
                  <SapReviewPanel extraction={sapExtraction} onChange={setSapExtraction} />
                )}
              </div>
              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(2)}>
                  <ArrowLeft className="h-4 w-4" /> Back
                </Button>
                <Button onClick={() => setStep(4)}>Continue <ArrowRight className="h-4 w-4" /></Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 4 && (
          <Card className="mx-auto max-w-3xl">
            <CardHeader>
              <CardTitle>Step 4 — Review & Create</CardTitle>
              <CardDescription>One last look before we write study_config.yaml.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Summary label="Protocol" value={protocol || "—"} />
              <Summary label="Title" value={title || "—"} />
              <Summary label="Treatment arms" value={`${arms.length} arms`} />
              <Summary label="Analysis sets" value={Object.keys(sets).join(", ") || "—"} />
              <Summary
                label="Uploaded domains"
                value={uploadResult ? uploadResult.domains.map((d) => d.domain).filter(Boolean).join(", ") : "—"}
              />
              <Summary
                label="SAP imported"
                value={sapExtraction ? "Yes (AI review applied)" : "No — manual configuration"}
              />
              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(3)}>
                  <ArrowLeft className="h-4 w-4" /> Back
                </Button>
                <Button onClick={handleCreate} disabled={updateStudy.isPending}>
                  Create Study
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <div>
      <Label className="text-xs">{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b pb-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
