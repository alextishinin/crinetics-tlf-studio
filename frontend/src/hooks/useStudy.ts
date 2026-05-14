"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { studies } from "@/lib/api";
import type { StudyConfig, StudyCreate } from "@/types/study";

export function useStudies() {
  return useQuery({
    queryKey: ["studies"],
    queryFn: () => studies.list(),
  });
}

export function useStudy(studyId: string | undefined) {
  return useQuery({
    queryKey: ["study", studyId],
    queryFn: () => studies.get(studyId as string),
    enabled: Boolean(studyId),
  });
}

export function useCreateStudy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StudyCreate) => studies.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["studies"] }),
  });
}

export function useUpdateStudy(studyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<StudyConfig>) => studies.update(studyId, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["study", studyId] });
      qc.invalidateQueries({ queryKey: ["studies"] });
    },
  });
}

export function useDeleteStudy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (studyId: string) => studies.delete(studyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["studies"] }),
  });
}

export function useUploadFiles(studyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => studies.upload(studyId, files),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["study", studyId] }),
  });
}
