"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Header } from "@/components/layout/Header";
import { TreatmentArmEditor } from "@/components/studies/TreatmentArmEditor";
import { AnalysisSetEditor } from "@/components/studies/AnalysisSetEditor";
import { DocumentExtracts, type DocumentExtractsValue } from "@/components/documents/DocumentExtracts";
import { useStudy, useUpdateStudy } from "@/hooks/useStudy";
import type { AnalysisSet, SapDefinitions, TreatmentArm } from "@/types/study";

const SAP_DEFINITION_FIELDS: { key: keyof SapDefinitions; label: string; rows?: number }[] = [
  { key: "teae_definition", label: "TEAE definition" },
  { key: "baseline_definition", label: "Baseline definition" },
  { key: "related_ae_definition", label: "Related AE definition" },
  { key: "exposure_duration_definition", label: "Exposure duration definition" },
  { key: "compliance_definition", label: "Compliance definition" },
  { key: "prior_medication_definition", label: "Prior medication definition" },
  { key: "concomitant_medication_definition", label: "Concomitant medication definition" },
  { key: "primary_endpoint", label: "Primary endpoint" },
];

const EMPTY_SAP_DEFINITIONS: SapDefinitions = {
  teae_definition: "",
  baseline_definition: "",
  related_ae_definition: "",
  exposure_duration_definition: "",
  compliance_definition: "",
  prior_medication_definition: "",
  concomitant_medication_definition: "",
  primary_endpoint: "",
  secondary_endpoints: [],
  subgroup_analyses: [],
};

export default function ConfigPage() {
  const params = useParams<{ studyId: string }>();
  const { data } = useStudy(params.studyId);
  const update = useUpdateStudy(params.studyId);

  const [protocol, setProtocol] = useState("");
  const [title, setTitle] = useState("");
  const [drug, setDrug] = useState("");
  const [indication, setIndication] = useState("");
  const [meddra, setMeddra] = useState("");
  const [whoDrug, setWhoDrug] = useState("");
  const [sasVersion, setSasVersion] = useState("");
  const [extract, setExtract] = useState("");
  const [cutDate, setCutDate] = useState("");
  const [arms, setArms] = useState<TreatmentArm[]>([]);
  const [sets, setSets] = useState<Record<string, AnalysisSet>>({});
  const [sapDefinitions, setSapDefinitions] = useState<SapDefinitions>(EMPTY_SAP_DEFINITIONS);
  const [secondaryEndpoints, setSecondaryEndpoints] = useState("");
  const [subgroupAnalyses, setSubgroupAnalyses] = useState("");
  const [documentExtracts, setDocumentExtracts] = useState<DocumentExtractsValue>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!data) return;
    setProtocol(data.config.protocol_number ?? "");
    setTitle(data.config.protocol_title ?? "");
    // Drug / indication live on the study meta record — the dashboard
    // cards read them from there. Editing them here mirrors the wizard.
    setDrug(data.meta.drug ?? "");
    setIndication(data.meta.indication ?? "");
    setMeddra(data.config.meddra_version ?? "");
    setWhoDrug(data.config.who_drug_version ?? "");
    setSasVersion(data.config.sas_version ?? "");
    setExtract(data.config.data_extract_date ?? "");
    setCutDate(data.config.data_cut_date ?? "");
    setArms(data.config.treatment_arms ?? []);
    setSets(data.config.analysis_sets ?? {});
    const sap = { ...EMPTY_SAP_DEFINITIONS, ...(data.config.sap_definitions ?? {}) };
    setSapDefinitions(sap);
    setSecondaryEndpoints((sap.secondary_endpoints ?? []).join("\n"));
    setSubgroupAnalyses((sap.subgroup_analyses ?? []).join("\n"));
    setDocumentExtracts((data.config.document_extracts as DocumentExtractsValue) ?? {});
  }, [data]);

  // Clear the "Saved" confirmation after a moment.
  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 2500);
    return () => clearTimeout(t);
  }, [saved]);

  const patchSapDefinition = (key: keyof SapDefinitions, value: string) => {
    setSapDefinitions((current) => ({ ...current, [key]: value }));
  };

  const splitLines = (value: string) =>
    value.split("\n").map((line) => line.trim()).filter(Boolean);

  const save = () =>
    update.mutate(
      {
        protocol_number: protocol,
        protocol_title: title,
        drug,
        indication,
        meddra_version: meddra,
        who_drug_version: whoDrug,
        sas_version: sasVersion,
        data_extract_date: extract,
        data_cut_date: cutDate,
        treatment_arms: arms,
        analysis_sets: sets,
        sap_definitions: {
          ...sapDefinitions,
          secondary_endpoints: splitLines(secondaryEndpoints),
          subgroup_analyses: splitLines(subgroupAnalyses),
        },
        document_extracts: documentExtracts as Record<string, unknown>,
      },
      { onSuccess: () => setSaved(true) },
    );

  if (!data) return <div className="p-6 text-sm text-slate-500">Loading…</div>;

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Study Config"
        action={
          <div className="flex items-center gap-3">
            {saved && (
              <span className="flex items-center gap-1 text-sm font-medium text-emerald-600">
                <CheckCircle2 className="h-4 w-4" /> Saved
              </span>
            )}
            <Button onClick={save} disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="mx-auto max-w-4xl space-y-6 p-6">
          {/* Identifiers */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Identifiers</CardTitle>
              <CardDescription>Study number, title, and what is being studied. Printed in output titles and headers.</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Protocol number">
                <Input value={protocol} onChange={(e) => setProtocol(e.target.value)} />
              </Field>
              <Field label="Title">
                <Input value={title} onChange={(e) => setTitle(e.target.value)} />
              </Field>
              <Field label="Drug">
                <Input value={drug} onChange={(e) => setDrug(e.target.value)} placeholder="e.g. Xanomeline" />
              </Field>
              <Field label="Indication">
                <Input value={indication} onChange={(e) => setIndication(e.target.value)} placeholder="e.g. Alzheimer's Disease" />
              </Field>
            </CardContent>
          </Card>

          {/* Dictionaries + Data dates side by side */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Dictionaries &amp; Versions</CardTitle>
                <CardDescription>Coding-dictionary and tooling versions cited in footnotes.</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="MedDRA version">
                  <Input value={meddra} onChange={(e) => setMeddra(e.target.value)} placeholder="e.g. 25.0" />
                </Field>
                <Field label="WHO Drug version">
                  <Input value={whoDrug} onChange={(e) => setWhoDrug(e.target.value)} placeholder="(optional)" />
                </Field>
                <Field label="SAS version">
                  <Input value={sasVersion} onChange={(e) => setSasVersion(e.target.value)} placeholder="9.4" />
                </Field>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Data Dates</CardTitle>
                <CardDescription>The data snapshot these outputs are run against.</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Data extract date" hint="Required — printed in output footers.">
                  <Input type="date" value={extract} onChange={(e) => setExtract(e.target.value)} />
                </Field>
                <Field label="Data cut date" hint="Optional — protocol database cutoff.">
                  <Input type="date" value={cutDate} onChange={(e) => setCutDate(e.target.value)} />
                </Field>
              </CardContent>
            </Card>
          </div>

          {/* SAP definitions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">SAP Definitions</CardTitle>
              <CardDescription>Wording interpolated into footnotes and used to drive derivations.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {SAP_DEFINITION_FIELDS.map((field) => (
                  <Field key={field.key} label={field.label}>
                    <Textarea
                      rows={field.rows ?? 2}
                      value={(sapDefinitions[field.key] as string | undefined) ?? ""}
                      onChange={(e) => patchSapDefinition(field.key, e.target.value)}
                    />
                  </Field>
                ))}
              </div>
              <div className="grid grid-cols-1 gap-4 border-t pt-4 md:grid-cols-2">
                <Field label="Secondary endpoints">
                  <Textarea
                    rows={5}
                    value={secondaryEndpoints}
                    onChange={(e) => setSecondaryEndpoints(e.target.value)}
                    placeholder="One endpoint per line"
                  />
                </Field>
                <Field label="Subgroup analyses">
                  <Textarea
                    rows={5}
                    value={subgroupAnalyses}
                    onChange={(e) => setSubgroupAnalyses(e.target.value)}
                    placeholder="One subgroup per line"
                  />
                </Field>
              </div>
            </CardContent>
          </Card>

          {/* Source documents */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Source Documents</CardTitle>
              <CardDescription>Upload the Protocol and CRF to extract identifiers and category orderings with AI.</CardDescription>
            </CardHeader>
            <CardContent>
              <DocumentExtracts
                value={documentExtracts}
                onChange={setDocumentExtracts}
                onApplyProtocol={(fields) => {
                  if (fields.protocol_number) setProtocol(fields.protocol_number);
                  if (fields.protocol_title) setTitle(fields.protocol_title);
                  if (fields.drug) setDrug(fields.drug);
                  if (fields.indication) setIndication(fields.indication);
                }}
              />
            </CardContent>
          </Card>

          {/* Treatment arms */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Treatment Arms</CardTitle>
              <CardDescription>Column order, headers, and target doses for the output tables.</CardDescription>
            </CardHeader>
            <CardContent><TreatmentArmEditor arms={arms} onChange={setArms} /></CardContent>
          </Card>

          {/* Analysis sets */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Analysis Sets</CardTitle>
              <CardDescription>Population flags and per-arm N counts.</CardDescription>
            </CardHeader>
            <CardContent><AnalysisSetEditor sets={sets} onChange={setSets} /></CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-slate-600">{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-slate-400">{hint}</p>}
    </div>
  );
}
