"use client";
import { useParams } from "next/navigation";

import { StudySidebar } from "@/components/layout/StudySidebar";

export default function StudyLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ studyId: string }>();
  return (
    <div className="flex h-full">
      <StudySidebar studyId={params.studyId} />
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}
