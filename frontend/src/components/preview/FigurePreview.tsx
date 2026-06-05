"use client";
import type { FigurePreviewData } from "@/types/job";

export function FigurePreview({ data }: { data: FigurePreviewData }) {
  return (
    <div className="rounded-md border bg-white p-6 font-serif text-sm">
      <div className="text-xs text-slate-500 mb-4">{data.header_text}</div>

      <div className="text-center mb-4 leading-tight">
        <div className="font-semibold">{data.title[0]}</div>
        <div>{data.title[1]}</div>
        <div className="italic">{data.title[2]}</div>
      </div>

      <div className="flex justify-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={data.image}
          alt={data.title.filter(Boolean).join(" — ") || "Figure preview"}
          className="max-w-full rounded border border-slate-200"
        />
      </div>

      <div className="mt-4 flex justify-between text-xs text-slate-500">
        <span>Source: {data.source}</span>
        <span>{data.page_indicator}</span>
      </div>
    </div>
  );
}
