"use client";
import { StatusBadge } from "@/components/ui/badge";
import type { JobStatus } from "@/types/job";

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <StatusBadge status={status} />;
}
