"use client";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ai, outputs, preview } from "@/lib/api";

export function usePreview(studyId: string, tableId: string) {
  return useMutation({
    mutationFn: () => preview.generate(studyId, tableId),
  });
}

export function useAnomalies(studyId: string, tableId: string) {
  return useMutation({
    mutationFn: () => ai.anomalies(studyId, tableId),
  });
}

export function useOutputs(studyId: string | undefined) {
  return useQuery({
    queryKey: ["outputs", studyId],
    queryFn: () => outputs.list(studyId as string),
    enabled: Boolean(studyId),
  });
}
