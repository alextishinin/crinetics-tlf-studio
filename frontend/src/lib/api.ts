// Typed API client. All endpoints share the same base URL and JSON error
// handling. Errors raise an ApiError so React Query can surface them to UI.

import { API_BASE_URL } from "./constants";
import type {
  StudyCreate,
  StudyDetail,
  StudySummary,
  StudyConfig,
  UploadResult,
} from "@/types/study";
import type { ShellListResponse } from "@/types/shell";
import type {
  JobRecord,
  JobSubmitResponse,
  OutputRecord,
  PreviewData,
} from "@/types/job";
import type {
  AnomalyResponse,
  CrfExtractionResponse,
  NlShellResponse,
  ProtocolExtractionResponse,
  SapExtractionResponse,
} from "@/types/ai";
import type {
  ApiKeySaveResult,
  ModelSaveResult,
  ModelsResponse,
  SettingsInfo,
} from "@/types/settings";

export class ApiError extends Error {
  status: number;
  payload: unknown;
  constructor(status: number, message: string, payload: unknown = null) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

async function http<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    ...init,
  });
  if (!resp.ok) {
    let payload: unknown = null;
    try {
      payload = await resp.json();
    } catch {
      payload = await resp.text();
    }
    const message =
      (typeof payload === "object" && payload && "detail" in payload)
        ? String((payload as { detail: unknown }).detail)
        : `Request failed: ${resp.status}`;
    throw new ApiError(resp.status, message, payload);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ---- studies ----
export const studies = {
  list: () => http<StudySummary[]>("/api/studies"),
  create: (payload: StudyCreate) =>
    http<StudyDetail>("/api/studies", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  get: (id: string) => http<StudyDetail>(`/api/studies/${id}`),
  update: (id: string, payload: Partial<StudyConfig>) =>
    http<StudyDetail>(`/api/studies/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    http<void>(`/api/studies/${id}`, { method: "DELETE" }),
  upload: async (id: string, files: File[]): Promise<UploadResult> => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    const resp = await fetch(`${API_BASE_URL}/api/studies/${id}/upload`, {
      method: "POST",
      body: form,
    });
    if (!resp.ok) {
      throw new ApiError(resp.status, `Upload failed: ${resp.status}`);
    }
    return (await resp.json()) as UploadResult;
  },
};

// ---- shells ----
export const shells = {
  list: (studyId: string) =>
    http<ShellListResponse>(`/api/studies/${studyId}/shells`),
  save: (studyId: string, optionalOutputs: Record<string, boolean>) =>
    http<Record<string, boolean>>(`/api/studies/${studyId}/shells`, {
      method: "PUT",
      body: JSON.stringify({ optional_outputs: optionalOutputs }),
    }),
};

// ---- jobs ----
export const jobs = {
  submit: (studyId: string, tableIds: string[]) =>
    http<JobSubmitResponse>(`/api/studies/${studyId}/jobs`, {
      method: "POST",
      body: JSON.stringify({ table_ids: tableIds }),
    }),
  list: (studyId: string) =>
    http<JobRecord[]>(`/api/studies/${studyId}/jobs`),
  get: (studyId: string, jobId: string) =>
    http<JobRecord>(`/api/studies/${studyId}/jobs/${jobId}`),
  cancel: (studyId: string, jobId: string) =>
    http<JobRecord>(`/api/studies/${studyId}/jobs/${jobId}`, {
      method: "DELETE",
    }),
};

// ---- preview ----
export const preview = {
  generate: (studyId: string, tableId: string) =>
    http<PreviewData>(`/api/studies/${studyId}/preview/${tableId}`, {
      method: "POST",
    }),
  rtfUrl: (studyId: string, tableId: string) =>
    `${API_BASE_URL}/api/studies/${studyId}/preview/${tableId}/rtf`,
};

// ---- settings ----
export const settings = {
  get: () => http<SettingsInfo>("/api/settings"),
  setApiKey: (apiKey: string) =>
    http<ApiKeySaveResult>("/api/settings/api-key", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey }),
    }),
  getModels: () => http<ModelsResponse>("/api/settings/models"),
  setModel: (model: string) =>
    http<ModelSaveResult>("/api/settings/model", {
      method: "POST",
      body: JSON.stringify({ model }),
    }),
};

// ---- outputs ----
export const outputs = {
  list: (studyId: string) =>
    http<OutputRecord[]>(`/api/studies/${studyId}/outputs`),
  setStatus: (studyId: string, outputId: string, status: string) =>
    http<{ status: string }>(
      `/api/studies/${studyId}/outputs/${outputId}/status`,
      { method: "POST", body: JSON.stringify({ status }) },
    ),
  downloadUrl: (studyId: string, outputId: string) =>
    `${API_BASE_URL}/api/studies/${studyId}/outputs/${outputId}/download`,
  packageUrl: (studyId: string) =>
    `${API_BASE_URL}/api/studies/${studyId}/outputs/package`,
  audit: (studyId: string, outputId: string) =>
    http<Record<string, unknown>>(
      `/api/studies/${studyId}/outputs/${outputId}/audit`,
    ),
};

// ---- ai ----
export const ai = {
  sap: async (file: File): Promise<SapExtractionResponse> => {
    const form = new FormData();
    form.append("file", file, file.name);
    const resp = await fetch(`${API_BASE_URL}/api/ai/sap`, {
      method: "POST",
      body: form,
    });
    if (!resp.ok) {
      throw new ApiError(resp.status, `SAP extraction failed: ${resp.status}`);
    }
    return (await resp.json()) as SapExtractionResponse;
  },
  protocol: async (file: File): Promise<ProtocolExtractionResponse> => {
    const form = new FormData();
    form.append("file", file, file.name);
    const resp = await fetch(`${API_BASE_URL}/api/ai/protocol`, { method: "POST", body: form });
    if (!resp.ok) throw new ApiError(resp.status, `Protocol extraction failed: ${resp.status}`);
    return (await resp.json()) as ProtocolExtractionResponse;
  },
  crf: async (file: File): Promise<CrfExtractionResponse> => {
    const form = new FormData();
    form.append("file", file, file.name);
    const resp = await fetch(`${API_BASE_URL}/api/ai/crf`, { method: "POST", body: form });
    if (!resp.ok) throw new ApiError(resp.status, `CRF extraction failed: ${resp.status}`);
    return (await resp.json()) as CrfExtractionResponse;
  },
  shells: (studyId: string, instruction: string, current: Record<string, boolean>) =>
    http<NlShellResponse>("/api/ai/shells", {
      method: "POST",
      body: JSON.stringify({
        study_id: studyId,
        instruction,
        current_selection: current,
      }),
    }),
  anomalies: (studyId: string, tableId: string) =>
    http<AnomalyResponse>("/api/ai/anomalies", {
      method: "POST",
      body: JSON.stringify({ study_id: studyId, table_id: tableId }),
    }),
  chatStream: async (
    studyId: string,
    tableId: string,
    messages: { role: "user" | "assistant"; content: string }[],
    onChunk: (chunk: string) => void,
  ): Promise<void> => {
    const resp = await fetch(`${API_BASE_URL}/api/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ study_id: studyId, table_id: tableId, messages }),
    });
    if (!resp.body) throw new ApiError(500, "No streaming body");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      onChunk(decoder.decode(value, { stream: true }));
    }
  },
};
