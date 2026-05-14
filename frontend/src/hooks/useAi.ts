"use client";
import { useMutation } from "@tanstack/react-query";

import { ai } from "@/lib/api";

export function useSapExtraction() {
  return useMutation({
    mutationFn: (file: File) => ai.sap(file),
  });
}

export function useNlShells(studyId: string) {
  return useMutation({
    mutationFn: ({
      instruction,
      current,
    }: {
      instruction: string;
      current: Record<string, boolean>;
    }) => ai.shells(studyId, instruction, current),
  });
}
