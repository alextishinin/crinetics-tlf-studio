import { create } from "zustand";

import type { StudyConfig } from "@/types/study";

interface StudyState {
  activeStudyId: string | null;
  configDraft: Partial<StudyConfig> | null;
  setActiveStudy: (id: string | null) => void;
  setConfigDraft: (draft: Partial<StudyConfig> | null) => void;
  patchConfigDraft: (patch: Partial<StudyConfig>) => void;
  clear: () => void;
}

export const useStudyStore = create<StudyState>((set) => ({
  activeStudyId: null,
  configDraft: null,
  setActiveStudy: (id) => set({ activeStudyId: id }),
  setConfigDraft: (draft) => set({ configDraft: draft }),
  patchConfigDraft: (patch) =>
    set((s) => ({ configDraft: { ...(s.configDraft ?? {}), ...patch } })),
  clear: () => set({ activeStudyId: null, configDraft: null }),
}));
