"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { jobs } from "@/lib/api";

export function useJobs(studyId: string | undefined, pollMs = 2000) {
  return useQuery({
    queryKey: ["jobs", studyId],
    queryFn: () => jobs.list(studyId as string),
    enabled: Boolean(studyId),
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!Array.isArray(data)) return false;
      const stillRunning = data.some(
        (j) => j.status === "queued" || j.status === "running",
      );
      return stillRunning ? pollMs : false;
    },
  });
}

export function useSubmitJobs(studyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tableIds: string[]) => jobs.submit(studyId, tableIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs", studyId] }),
  });
}

export function useCancelJob(studyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => jobs.cancel(studyId, jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs", studyId] }),
  });
}
