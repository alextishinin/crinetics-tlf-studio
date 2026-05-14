export type Conditionality = "required" | "optional" | "conditional";

export interface ShellEntry {
  id: string;
  type: string;
  table_number: string;
  title_line1: string;
  title_line2: string;
  title_line3: string;
  population: string;
  adam_domains: string[];
  domain_group: string;
  conditionality: Conditionality;
  optional_flag: string | null;
  selected: boolean;
  available: boolean;
  condition_reason: string | null;
}

export interface ShellGroup {
  name: string;
  shells: ShellEntry[];
}

export interface ShellListResponse {
  groups: ShellGroup[];
  auto_selected: string[];
  auto_deselected: string[];
}
