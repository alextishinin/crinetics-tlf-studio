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
