export interface SettingsInfo {
  key_present: boolean;
  key_masked: string;
  model: string;
  app_version: string;
}

export interface ApiKeySaveResult {
  saved: boolean;
  key_present: boolean;
  valid: boolean;
  message: string;
}

export interface ModelOption {
  id: string;
  display_name: string;
}

export interface ModelsResponse {
  models: ModelOption[];
  current: string;
  error: string | null;
}

export interface ModelSaveResult {
  saved: boolean;
  model: string;
  message: string;
}
