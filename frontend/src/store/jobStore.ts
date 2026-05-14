import { create } from "zustand";

import type { JobRecord } from "@/types/job";

interface JobState {
  jobs: JobRecord[];
  polling: boolean;
  setJobs: (jobs: JobRecord[]) => void;
  upsertJob: (job: JobRecord) => void;
  setPolling: (polling: boolean) => void;
}

export const useJobStore = create<JobState>((set) => ({
  jobs: [],
  polling: false,
  setJobs: (jobs) => set({ jobs }),
  upsertJob: (job) =>
    set((s) => {
      const idx = s.jobs.findIndex((j) => j.job_id === job.job_id);
      if (idx === -1) return { jobs: [...s.jobs, job] };
      const next = [...s.jobs];
      next[idx] = job;
      return { jobs: next };
    }),
  setPolling: (polling) => set({ polling }),
}));
