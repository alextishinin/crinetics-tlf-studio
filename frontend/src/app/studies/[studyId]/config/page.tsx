"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Header } from "@/components/layout/Header";
import { TreatmentArmEditor } from "@/components/studies/TreatmentArmEditor";
import { AnalysisSetEditor } from "@/components/studies/AnalysisSetEditor";
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
  }, [data]);

  const patchSapDefinition = (key: keyof SapDefinitions, value: string) => {
    setSapDefinitions((current) => ({ ...current, [key]: value }));
  };

  const splitLines = (value: string) =>
    value.split("\n").map((line) => line.trim()).filter(Boolean);

  const save = () =>
    update.mutate({
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
    });

  if (!data) return <div className="p-6">Loading…</div>;

  return (
    <div className="flex h-full flex-col">
      <Header title="Study Config" action={<Button onClick={save} disabled={update.isPending}>Save</Button>} />
      <div className="p-6 max-w-4xl space-y-4">
        <Card>
          <CardHeader><CardTitle>Identifiers</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs">Protocol number</Label><Input value={protocol} onChange={(e) => setProtocol(e.target.value)} /></div>
            <div><Label className="text-xs">Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div><Label className="text-xs">Drug</Label><Input value={drug} onChange={(e) => setDrug(e.target.value)} placeholder="e.g. Xanomeline" /></div>
            <div><Label className="text-xs">Indication</Label><Input value={indication} onChange={(e) => setIndication(e.target.value)} placeholder="e.g. Alzheimer's Disease" /></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Dictionaries & Tooling</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs">MedDRA version</Label><Input value={meddra} onChange={(e) => setMeddra(e.target.value)} /></div>
            <div><Label className="text-xs">WHO Drug version</Label><Input value={whoDrug} onChange={(e) => setWhoDrug(e.target.value)} placeholder="(optional)" /></div>
            <div><Label className="text-xs">SAS version</Label><Input value={sasVersion} onChange={(e) => setSasVersion(e.target.value)} placeholder="9.4" /></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Data Dates</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs">Data extract date</Label><Input type="date" value={extract} onChange={(e) => setExtract(e.target.value)} /></div>
            <div><Label className="text-xs">Data cut date (optional)</Label><Input type="date" value={cutDate} onChange={(e) => setCutDate(e.target.value)} /></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>SAP Definitions</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {SAP_DEFINITION_FIELDS.map((field) => (
              <div key={field.key} className="space-y-1">
                <Label className="text-xs">{field.label}</Label>
                <Textarea
                  rows={field.rows ?? 3}
                  value={(sapDefinitions[field.key] as string | undefined) ?? ""}
                  onChange={(e) => patchSapDefinition(field.key, e.target.value)}
                />
              </div>
            ))}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">Secondary endpoints</Label>
                <Textarea
                  rows={5}
                  value={secondaryEndpoints}
                  onChange={(e) => setSecondaryEndpoints(e.target.value)}
                  placeholder="One endpoint per line"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Subgroup analyses</Label>
                <Textarea
                  rows={5}
                  value={subgroupAnalyses}
                  onChange={(e) => setSubgroupAnalyses(e.target.value)}
                  placeholder="One subgroup per line"
                />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Treatment Arms</CardTitle></CardHeader>
          <CardContent><TreatmentArmEditor arms={arms} onChange={setArms} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Analysis Sets</CardTitle></CardHeader>
          <CardContent><AnalysisSetEditor sets={sets} onChange={setSets} /></CardContent>
        </Card>
      </div>
    </div>
  );
}
