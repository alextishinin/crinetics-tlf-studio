"use client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Header } from "@/components/layout/Header";
import changelogData from "@/data/changelog.json";

type Area = "Studio" | "Automation" | "Desktop";
interface Change {
  area: Area;
  text: string;
}
interface Release {
  version: string;
  date: string;
  title?: string;
  changes: Change[];
}

const releases = changelogData as Release[];
const current = releases[0]?.version ?? "";

const AREA_STYLES: Record<Area, string> = {
  Studio: "bg-crinetics-tealLight text-primary",
  Automation: "bg-slate-100 text-slate-600",
  Desktop: "bg-blue-100 text-blue-700",
};

function AreaTag({ area }: { area: Area }) {
  return (
    <span
      className={`mt-0.5 inline-block shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
        AREA_STYLES[area] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {area}
    </span>
  );
}

export default function UpdatesPage() {
  return (
    <div className="flex min-h-full flex-col">
      <Header title="Updates" />
      <div className="max-w-3xl space-y-5 p-6">
        <p className="text-sm text-slate-500">
          Everything that&apos;s changed in TLF Studio and the underlying TLF automation library,
          newest first. The app is currently <span className="font-medium text-slate-700">v{current}</span>.
        </p>

        {releases.map((r) => (
          <Card key={r.version}>
            <CardHeader>
              <CardTitle className="flex items-baseline gap-2 text-base">
                <span>v{r.version}</span>
                {r.title && <span className="text-sm font-normal text-slate-600">— {r.title}</span>}
                <span className="ml-auto text-xs font-normal text-slate-400">{r.date}</span>
              </CardTitle>
              {r.title && <CardDescription className="sr-only">{r.title}</CardDescription>}
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                {r.changes.map((c, i) => (
                  <li key={i} className="flex gap-2">
                    <AreaTag area={c.area} />
                    <span className="text-slate-700">{c.text}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}

        <p className="pb-4 text-center text-xs text-slate-400">
          Crinetics Pharmaceuticals · Internal
        </p>
      </div>
    </div>
  );
}
