"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import type { SapExtractionResponse, SapDefinitionField, OptionalOutputDecision } from "@/types/ai";

interface Props {
  extraction: SapExtractionResponse;
  onChange: (next: SapExtractionResponse) => void;
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-rose-100 text-rose-700",
};

export function SapReviewPanel({ extraction, onChange }: Props) {
  if (extraction.error) {
    return (
      <Card className="border-rose-200 bg-rose-50">
        <CardHeader><CardTitle>AI extraction failed</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-rose-700">{extraction.error}</p>
          {extraction.raw_excerpt_sample && (
            <pre className="mt-2 max-h-40 overflow-auto text-xs">{extraction.raw_excerpt_sample}</pre>
          )}
        </CardContent>
      </Card>
    );
  }

  const patchDef = (k: string, patch: Partial<SapDefinitionField>) =>
    onChange({
      ...extraction,
      sap_definitions: {
        ...extraction.sap_definitions,
        [k]: { ...extraction.sap_definitions[k], ...patch },
      },
    });

  const patchOpt = (i: number, patch: Partial<OptionalOutputDecision>) => {
    const next = [...extraction.optional_outputs];
    next[i] = { ...next[i], ...patch };
    onChange({ ...extraction, optional_outputs: next });
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>SAP Definitions</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {Object.entries(extraction.sap_definitions).map(([key, field]) => (
            <div key={key} className="space-y-1">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">{key.replace(/_/g, " ")}</Label>
                <Badge className={CONFIDENCE_COLOR[field.confidence] ?? ""}>{field.confidence}</Badge>
              </div>
              <Textarea
                rows={2}
                value={field.value}
                onChange={(e) => patchDef(key, { value: e.target.value })}
              />
              {field.source_excerpt && (
                <p className="text-xs text-slate-500 italic border-l-2 pl-2 border-slate-200">
                  &ldquo;{field.source_excerpt}&rdquo;
                </p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Optional Outputs (AI-reasoned)</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {extraction.optional_outputs.map((o, i) => (
            <div key={o.flag} className="flex items-start gap-3 border-b pb-2">
              <Checkbox
                checked={o.enabled}
                onCheckedChange={(c) => patchOpt(i, { enabled: Boolean(c) })}
              />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{o.flag}</span>
                  <Badge className={CONFIDENCE_COLOR[o.confidence] ?? ""}>{o.confidence}</Badge>
                </div>
                <p className="text-xs text-slate-600">{o.reason}</p>
                {o.source_excerpt && (
                  <p className="text-xs text-slate-500 italic mt-1 border-l-2 pl-2 border-slate-200">
                    &ldquo;{o.source_excerpt}&rdquo;
                  </p>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
