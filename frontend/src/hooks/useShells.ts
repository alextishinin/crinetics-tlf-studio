"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { shells } from "@/lib/api";

export function useShells(studyId: string | undefined) {
  return useQuery({
    queryKey: ["shells", studyId],
    queryFn: () => shells.list(studyId as string),
    enabled: Boolean(studyId),
  });
}

export function useSaveShellSelection(studyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (optionalOutputs: Record<string, boolean>) =>
      shells.save(studyId, optionalOutputs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shells", studyId] });
      qc.invalidateQueries({ queryKey: ["study", studyId] });
    },
  });
}
