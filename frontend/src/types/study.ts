// Mirrors backend Pydantic models in backend/models/study.py.

export type StudyStatus = "draft" | "ready" | "generating" | "complete";

export interface TreatmentArm {
  label: string;
  trtpn: number;
  column_header: string;
  target_daily_dose_mg: number | null;
}

export interface AnalysisSet {
  label: string;
  flag_var: string | null;
  flag_val: string | null;
  n: Record<string, number | null>;
}

export interface SapDefinitions {
  teae_definition: string;
  baseline_definition: string;
  related_ae_definition: string;
  exposure_duration_definition: string;
  compliance_definition?: string;
  prior_medication_definition?: string;
  concomitant_medication_definition?: string;
  primary_endpoint?: string;
  secondary_endpoints?: string[];
  subgroup_analyses?: string[];
}

export interface StudyMeta {
  study_id: string;
  title: string;
  drug: string;
  indication: string;
  status: StudyStatus;
  created_at: string;
  updated_at: string;
  last_generated_at: string | null;
}

export interface StudySummary {
  study_id: string;
  title: string;
  protocol_number: string;
  drug: string;
  indication: string;
  status: StudyStatus;
  n_arms: number;
  total_n: number;
  selected_tables: number;
  available_tables: number;
  last_generated_at: string | null;
  updated_at: string;
}

export interface StudyConfig {
  study_id: string;
  protocol_number: string;
  protocol_title: string;
  drug?: string;
  indication?: string;
  data_extract_date?: string;
  data_cut_date?: string;
  sas_version?: string;
  meddra_version?: string;
  who_drug_version?: string;
  treatment_arms?: TreatmentArm[];
  pooled_active?: boolean;
  include_total_column?: boolean;
  analysis_sets?: Record<string, AnalysisSet>;
  sap_definitions?: SapDefinitions;
  optional_outputs?: Record<string, boolean>;
  exposure_duration_bins?: unknown[];
  common_ae_cutoff_pct?: number;
}

export interface StudyDetail {
  meta: StudyMeta;
  config: StudyConfig;
}

export interface StudyCreate {
  title: string;
  protocol_number?: string;
  drug?: string;
  indication?: string;
}

export interface DomainSummary {
  filename: string;
  domain: string;
  n_rows: number;
  n_subjects: number;
  columns: string[];
  notes: string[];
}

export interface UploadResult {
  study_id: string;
  domains: DomainSummary[];
  detected_arms: TreatmentArm[];
  detected_analysis_sets: Record<string, AnalysisSet>;
  visit_schedule: string[];
  available_paramcds: Record<string, string[]>;
  study_id_value: string | null;
}
