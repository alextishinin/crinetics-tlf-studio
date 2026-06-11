export type JobStatus = "queued" | "running" | "complete" | "failed" | "cancelled";

export interface JobRecord {
  job_id: string;
  study_id: string;
  table_id: string;
  table_number: string;
  status: JobStatus;
  submitted_at: string;
  started_at: string | null;
  completed_at: string | null;
  output_path: string | null;
  error: string | null;
  triggered_by: string;
  batch_id: string | null;
}

export interface JobSubmitResponse {
  batch_id: string | null;
  jobs: JobRecord[];
}

export interface TablePreviewData {
  kind?: "table";
  shell_id: string;
  title: [string, string, string];
  header_text: string;
  column_headers: string[];
  arm_n_labels: string[];
  body_rows: string[][];
  footnotes: { kind: string; text: string }[];
  source: string;
  page_indicator: string;
}

export interface FigurePreviewData {
  kind: "figure";
  shell_id: string;
  title: [string, string, string];
  header_text: string;
  image: string; // data URL (data:image/png;base64,...)
  source: string;
  page_indicator: string;
}

export type PreviewData = TablePreviewData | FigurePreviewData;

// Review workflow: pending (QC outstanding) -> qc_passed | qc_failed ->
// approved (biostat signed off).
export type OutputStatus = "pending" | "qc_passed" | "qc_failed" | "approved";

export interface OutputRecord {
  output_id: string;
  filename: string;
  table_number: string;
  table_id: string;
  population: string;
  generated_at: string;
  size_bytes: number;
  status: OutputStatus;
  audit_path: string | null;
}

export interface QcChecklistItem {
  id: string;
  label: string;
  result: "pass" | "fail" | "na";
  comment: string;
}

export interface QcRecord {
  reviewer: string;
  performed_at: string;
  result: "pass" | "fail";
  items: QcChecklistItem[];
  comments: string;
  auto_checks: Record<string, unknown>;
}

export interface SignoffRecord {
  name: string;
  role: string;
  signed_at: string;
  comment: string;
  qc_reviewer: string;
  qc_performed_at: string;
}

export interface OutputAudit {
  generated?: {
    at: string;
    table_id: string;
    filename: string;
    data_extract_date: string;
  };
  qc?: QcRecord;
  signoff?: SignoffRecord;
  review_history?: Record<string, unknown>[];
}
