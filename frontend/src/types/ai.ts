export interface SapDefinitionField {
  value: string;
  source_excerpt: string;
  confidence: "high" | "medium" | "low";
}

export interface OptionalOutputDecision {
  flag: string;
  enabled: boolean;
  reason: string;
  source_excerpt: string;
  confidence: "high" | "medium" | "low";
}

export interface SapExtractionResponse {
  sap_definitions: Record<string, SapDefinitionField>;
  optional_outputs: OptionalOutputDecision[];
  primary_endpoint: SapDefinitionField | null;
  secondary_endpoints: string[];
  subgroup_analyses: string[];
  raw_excerpt_sample: string;
  error: string | null;
}

export interface NlShellChange {
  shell_id: string;
  action: "add" | "remove";
  reason: string;
}

export interface NlShellResponse {
  changes: NlShellChange[];
  summary: string;
  error: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Anomaly {
  severity: "warning" | "info";
  description: string;
  location: string;
  rule: string;
  source: "rule" | "ai";
}

export interface AnomalyResponse {
  anomalies: Anomaly[];
}
