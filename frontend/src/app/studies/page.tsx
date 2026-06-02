"use client";
import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Header } from "@/components/layout/Header";
import { StudyCard } from "@/components/studies/StudyCard";
import { useStudies } from "@/hooks/useStudy";

export default function StudiesPage() {
  const { data, isLoading, error } = useStudies();
  return (
    <div className="flex h-full flex-col">
      <Header
        title="Studies"
        action={
          <Button asChild>
            <Link href="/studies/new"><Plus className="h-4 w-4" /> New Study</Link>
          </Button>
        }
      />
      <div className="p-6">
        {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
        {error && <p className="text-sm text-rose-600">Failed to load studies: {String(error)}</p>}
        {data && data.length === 0 && (
          <Card className="mx-auto max-w-md text-center">
            <CardHeader>
              <CardTitle>No studies yet</CardTitle>
              <CardDescription>
                Start by uploading your ADaM data and configuring your first study.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild>
                <Link href="/studies/new"><Plus className="h-4 w-4" /> Create your first study</Link>
              </Button>
            </CardContent>
          </Card>
        )}
        {data && data.length > 0 && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.map((s) => (
              <StudyCard key={s.study_id} study={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
