"use client";
import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, ShieldCheck, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ai, outputs as outputsApi } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";
import type { Anomaly } from "@/types/ai";
import type { OutputAudit, OutputRecord, QcChecklistItem } from "@/types/job";

// The standard statistical-programmer QC checks for a TLF output.
const QC_CHECKLIST: { id: string; label: string }[] = [
  { id: "titles", label: "Title and table number match the shell / TFL map" },
  { id: "population", label: "Correct analysis set; column Ns match ADSL counts" },
  { id: "values", label: "Body values verified against the source ADaM data" },
  { id: "precision", label: "Precision and rounding follow the General Instructions" },
  { id: "footnotes", label: "Footnotes complete, correctly ordered, no unresolved placeholders" },
  { id: "layout", label: "Layout matches the shell (columns, indentation, pagination)" },
];

type ItemResult = "pass" | "fail" | "na";

interface DialogProps {
  studyId: string;
  output: OutputRecord;
  onClose: () => void;
  onDone: () => void;
}

// ---------------------------------------------------------------------------
// Shared modal shell (same pattern as ConfirmDialog)
// ---------------------------------------------------------------------------

function DialogShell({
  title,
  subtitle,
  onClose,
  children,
  wide,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`flex max-h-[85vh] w-full flex-col rounded-lg border bg-white shadow-xl ${wide ? "max-w-2xl" : "max-w-md"}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b px-5 py-4">
          <h2 className="text-base font-semibold">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        <div className="min-h-0 flex-1 overflow-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// QC review dialog (statistical programmer)
// ---------------------------------------------------------------------------

export function QcDialog({ studyId, output, onClose, onDone }: DialogProps) {
  const [reviewer, setReviewer] = useState("");
  const [results, setResults] = useState<Record<string, ItemResult | undefined>>({});
  const [itemComments, setItemComments] = useState<Record<string, string>>({});
  const [comments, setComments] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Automated pre-check: run the anomaly scan for the reviewer to consider.
  const [scan, setScan] = useState<{ loading: boolean; anomalies: Anomaly[]; error?: string }>({
    loading: true,
    anomalies: [],
  });
  useEffect(() => {
    let cancelled = false;
    ai.anomalies(studyId, output.table_id)
      .then((r) => !cancelled && setScan({ loading: false, anomalies: r.anomalies }))
      .catch((e) =>
        !cancelled &&
        setScan({ loading: false, anomalies: [], error: e instanceof Error ? e.message : String(e) }),
      );
    return () => {
      cancelled = true;
    };
  }, [studyId, output.table_id]);

  const allAnswered = QC_CHECKLIST.every((c) => results[c.id]);
  const anyFail = QC_CHECKLIST.some((c) => results[c.id] === "fail");
  const canSubmit = allAnswered && reviewer.trim().length > 0 && !submitting;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    const items: QcChecklistItem[] = QC_CHECKLIST.map((c) => ({
      id: c.id,
      label: c.label,
      result: results[c.id] as ItemResult,
      comment: itemComments[c.id] ?? "",
    }));
    const auto_checks = scan.error
      ? { anomaly_scan: { error: scan.error } }
      : {
          anomaly_scan: {
            count: scan.anomalies.length,
            findings: scan.anomalies.map((a) => ({
              severity: a.severity,
              description: a.description,
              location: a.location,
              rule: a.rule,
              source: a.source,
            })),
          },
        };
    try {
      await outputsApi.qc(studyId, output.output_id, {
        reviewer: reviewer.trim(),
        items,
        comments,
        auto_checks,
      });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  };

  return (
    <DialogShell
      title={`QC Review — ${output.table_number}`}
      subtitle={output.filename}
      onClose={onClose}
      wide
    >
      <div className="space-y-4">
        {/* Automated pre-checks */}
        <div className="rounded-md border bg-slate-50 p-3">
          <p className="mb-1 text-xs font-semibold text-slate-600">Automated checks</p>
          {scan.loading ? (
            <p className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Running anomaly scan…
            </p>
          ) : scan.error ? (
            <p className="text-xs text-amber-700">Anomaly scan unavailable: {scan.error}</p>
          ) : scan.anomalies.length === 0 ? (
            <p className="flex items-center gap-1.5 text-xs text-emerald-700">
              <CheckCircle2 className="h-3.5 w-3.5" /> No findings from the rule-based / AI anomaly scan.
            </p>
          ) : (
            <ul className="space-y-1">
              {scan.anomalies.map((a, i) => (
                <li key={i} className="text-xs text-slate-700">
                  <span className={a.severity === "warning" ? "font-medium text-amber-700" : "text-slate-500"}>
                    [{a.severity}]
                  </span>{" "}
                  {a.description} <span className="text-slate-400">({a.location})</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Checklist */}
        <div className="space-y-3">
          {QC_CHECKLIST.map((c) => (
            <div key={c.id} className="rounded-md border p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm">{c.label}</p>
                <div className="flex shrink-0 gap-1">
                  {(["pass", "fail", "na"] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setResults((cur) => ({ ...cur, [c.id]: r }))}
                      className={`rounded px-2 py-0.5 text-xs font-medium border ${
                        results[c.id] === r
                          ? r === "pass"
                            ? "border-emerald-300 bg-emerald-100 text-emerald-700"
                            : r === "fail"
                              ? "border-rose-300 bg-rose-100 text-rose-700"
                              : "border-slate-300 bg-slate-100 text-slate-600"
                          : "border-slate-200 text-slate-400 hover:bg-slate-50"
                      }`}
                    >
                      {r === "na" ? "N/A" : r === "pass" ? "Pass" : "Fail"}
                    </button>
                  ))}
                </div>
              </div>
              {results[c.id] === "fail" && (
                <Input
                  className="mt-2"
                  placeholder="Describe the finding (required for the primary programmer)"
                  value={itemComments[c.id] ?? ""}
                  onChange={(e) => setItemComments((cur) => ({ ...cur, [c.id]: e.target.value }))}
                />
              )}
            </div>
          ))}
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">Overall comments (optional)</Label>
          <Textarea rows={2} value={comments} onChange={(e) => setComments(e.target.value)} />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">QC reviewer (your name) *</Label>
          <Input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="e.g. J. Smith"
          />
        </div>

        {error && (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">{error}</div>
        )}

        <div className="flex items-center justify-between border-t pt-3">
          <p className="text-xs text-slate-500">
            {allAnswered
              ? anyFail
                ? "Result: QC Failed — goes back to the primary programmer."
                : "Result: QC Passed — ready for biostatistician sign-off."
              : "Answer every checklist item to submit."}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={!canSubmit}>
              {submitting ? "Submitting…" : "Submit QC"}
            </Button>
          </div>
        </div>
      </div>
    </DialogShell>
  );
}

// ---------------------------------------------------------------------------
// Biostatistician sign-off dialog
// ---------------------------------------------------------------------------

export function SignoffDialog({ studyId, output, onClose, onDone }: DialogProps) {
  const [name, setName] = useState("");
  const [comment, setComment] = useState("");
  const [attested, setAttested] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<OutputAudit | null>(null);

  useEffect(() => {
    outputsApi.audit(studyId, output.output_id).then(setAudit).catch(() => setAudit(null));
  }, [studyId, output.output_id]);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await outputsApi.signoff(studyId, output.output_id, { name: name.trim(), comment });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  };

  return (
    <DialogShell
      title={`Biostatistician Sign-off — ${output.table_number}`}
      subtitle={output.filename}
      onClose={onClose}
    >
      <div className="space-y-4">
        {audit?.qc && (
          <div className="rounded-md border bg-slate-50 p-3 text-xs text-slate-600">
            <p className="flex items-center gap-1.5 font-medium text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" /> QC passed
            </p>
            <p className="mt-1">
              Reviewed by <span className="font-medium">{audit.qc.reviewer}</span> on{" "}
              {formatTimestamp(audit.qc.performed_at)}.
            </p>
            {audit.qc.comments && <p className="mt-1 italic">“{audit.qc.comments}”</p>}
          </div>
        )}

        <div className="space-y-1.5">
          <Label className="text-xs">Biostatistician (your name) *</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. A. Tishinin" />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">Comment (optional)</Label>
          <Textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
        </div>

        <label className="flex items-start gap-2 text-xs text-slate-600">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={attested}
            onChange={(e) => setAttested(e.target.checked)}
          />
          I have reviewed this output and confirm the statistical methods, populations, and results
          are correct for the purposes of this study.
        </label>

        {error && (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">{error}</div>
        )}

        <div className="flex justify-end gap-2 border-t pt-3">
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!attested || name.trim().length === 0 || submitting}>
            {submitting ? "Signing…" : "Sign Off"}
          </Button>
        </div>
      </div>
    </DialogShell>
  );
}

// ---------------------------------------------------------------------------
// Review trail viewer
// ---------------------------------------------------------------------------

export function ReviewTrailDialog({
  studyId,
  output,
  onClose,
}: Omit<DialogProps, "onDone">) {
  const [audit, setAudit] = useState<OutputAudit | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    outputsApi
      .audit(studyId, output.output_id)
      .then(setAudit)
      .catch(() => setAudit(null))
      .finally(() => setLoading(false));
  }, [studyId, output.output_id]);

  return (
    <DialogShell
      title={`Review Trail — ${output.table_number}`}
      subtitle={output.filename}
      onClose={onClose}
      wide
    >
      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : !audit || Object.keys(audit).length === 0 ? (
        <p className="text-sm text-slate-500">No review records yet for this output.</p>
      ) : (
        <div className="space-y-4 text-sm">
          {audit.generated && (
            <TrailSection title="Generated">
              <TrailRow label="When" value={formatTimestamp(audit.generated.at)} />
              <TrailRow label="Data extract date" value={audit.generated.data_extract_date || "—"} />
            </TrailSection>
          )}
          {audit.qc && (
            <TrailSection title={`QC Review — ${audit.qc.result === "pass" ? "Passed" : "Failed"}`}>
              <TrailRow label="Reviewer" value={audit.qc.reviewer} />
              <TrailRow label="When" value={formatTimestamp(audit.qc.performed_at)} />
              {audit.qc.comments && <TrailRow label="Comments" value={audit.qc.comments} />}
              <ul className="mt-2 space-y-1">
                {audit.qc.items.map((item) => (
                  <li key={item.id} className="flex items-start gap-1.5 text-xs">
                    {item.result === "pass" ? (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                    ) : item.result === "fail" ? (
                      <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-600" />
                    ) : (
                      <span className="mt-0.5 w-3.5 shrink-0 text-center text-slate-400">–</span>
                    )}
                    <span>
                      {item.label}
                      {item.comment && <span className="italic text-slate-500"> — {item.comment}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </TrailSection>
          )}
          {audit.signoff && (
            <TrailSection title="Biostatistician Sign-off">
              <TrailRow label="Signed by" value={`${audit.signoff.name} (${audit.signoff.role})`} />
              <TrailRow label="When" value={formatTimestamp(audit.signoff.signed_at)} />
              {audit.signoff.comment && <TrailRow label="Comment" value={audit.signoff.comment} />}
            </TrailSection>
          )}
          {(audit.review_history?.length ?? 0) > 0 && (
            <p className="text-xs text-slate-400">
              {audit.review_history!.length} archived review record
              {audit.review_history!.length === 1 ? "" : "s"} (kept for the audit trail).
            </p>
          )}
        </div>
      )}
    </DialogShell>
  );
}

function TrailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      {children}
    </div>
  );
}

function TrailRow({ label, value }: { label: string; value: string }) {
  return (
    <p className="text-xs">
      <span className="text-slate-500">{label}:</span> <span className="font-medium">{value}</span>
    </p>
  );
}
