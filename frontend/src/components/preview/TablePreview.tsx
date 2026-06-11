"use client";
import { cn } from "@/lib/utils";
import type { TablePreviewData } from "@/types/job";

export function TablePreview({ data }: { data: TablePreviewData }) {
  // The first column is the row-label column; everything after is an arm.
  // Monospace to match the real RTF output (Courier New) — a serif preview
  // misrepresents the column alignment reviewers are checking.
  return (
    <div className="rounded-md border bg-white p-6 font-mono text-sm">
      <div className="text-xs text-slate-500 mb-4">{data.header_text}</div>

      <div className="text-center mb-4 leading-tight">
        <div className="font-semibold">{data.title[0]}</div>
        <div>{data.title[1]}</div>
        <div className="italic">{data.title[2]}</div>
      </div>

      <div className="overflow-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b-2 border-slate-400">
              {data.column_headers.map((h, i) => (
                <th key={i} className="whitespace-pre-line p-1 text-center align-bottom">{h}</th>
              ))}
            </tr>
            {data.arm_n_labels.some((n) => n) && (
              <tr className="border-b border-slate-400">
                {data.arm_n_labels.map((n, i) => (
                  <th key={i} className="p-1 text-center text-xs font-normal">{n}</th>
                ))}
              </tr>
            )}
          </thead>
          <tbody>
            {data.body_rows.map((row, r) => {
              const label = String(row[0] ?? "");
              const indent = (label.length - label.trimStart().length) / 3;
              return (
                <tr key={r} className="border-b border-slate-100">
                  {row.map((cell, c) => (
                    <td
                      key={c}
                      className={cn(
                        "p-1",
                        c === 0 ? "whitespace-pre-wrap" : "text-center font-mono",
                      )}
                      style={c === 0 ? { paddingLeft: `${indent * 12}px` } : undefined}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {data.footnotes.length > 0 && (
        <>
          <div className="my-4 border-t border-slate-300" />
          <div className="space-y-1 text-xs">
            {data.footnotes.map((f, i) => (
              <p key={i}>{f.text}</p>
            ))}
          </div>
        </>
      )}

      <div className="mt-4 flex justify-between text-xs text-slate-500">
        <span>Source: {data.source}</span>
        <span>{data.page_indicator}</span>
      </div>
    </div>
  );
}
