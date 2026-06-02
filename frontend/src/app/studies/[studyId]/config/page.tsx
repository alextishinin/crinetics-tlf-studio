"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Header } from "@/components/layout/Header";
import { TreatmentArmEditor } from "@/components/studies/TreatmentArmEditor";
import { AnalysisSetEditor } from "@/components/studies/AnalysisSetEditor";
import { useStudy, useUpdateStudy } from "@/hooks/useStudy";
import type { AnalysisSet, TreatmentArm } from "@/types/study";

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
  }, [data]);

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
